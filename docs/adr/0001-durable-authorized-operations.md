# ADR 0001: Durable Authorized Operations

## Status

Accepted

## Context

Aksara v0.6.1 has several execution-shaped subsystems, but none is an
authoritative record for authorized work that outlives its initiating process.

* MCP assigns request, run, and tool-call IDs in `AgentInvocationContext`, but
  the context is a `ContextVar`. Replay protection and runtime budgets are also
  process-local.
* MCP mutations reuse the generated REST path and wrap that path in
  `transaction.atomic()`. This gives one synchronous invocation a sound
  rollback boundary, but audit emission happens after the transaction and no
  durable operation survives a lost response.
* The task queue persists payload, tenant, status, retries, results, and a
  `locked_at` timestamp. A claim uses `FOR UPDATE SKIP LOCKED`, but the row has
  no principal provenance, attempt identity, lease owner, heartbeat, or fencing
  token. User work and the final `completed` update are separate transactions.
* `DurableStep` persists a result for `(workflow_id, step_name)`. A process that
  dies while the row is `running` leaves it permanently blocked; `force=True`
  can overwrite an active claimant; and completion is not atomic with the
  step's effects.
* Investigation sessions, planner state, and AI budgets are in memory and are
  explicitly experimental.
* `Principal` and `PolicyEngine` provide the current authorization boundary.
  Persisting a `Principal` snapshot would preserve stale roles, scopes, expiry,
  and metadata as if they remained authority.

The v0.6 stable APIs must continue to work. Durable execution must be opt-in
and useful for ordinary application operations without involving a planner or
an LLM.

## Problem

Aksara needs the smallest framework-owned abstraction that can answer, after a
request, process, or worker is lost:

1. Which logical operation was accepted?
2. Who initiated it and in which tenant, without storing reusable credentials?
3. Which physical executions occurred and which worker currently owns one?
4. Was the application mutation committed?
5. May the work still run under current authorization?
6. Is an approval required, granted, rejected, expired, or already bound?
7. Was cancellation requested, and did it take effect before a side effect?
8. Can a duplicate submission safely return the existing answer?
9. What bounded operational history can be exported to an audit sink?

The existing task row cannot answer these questions without becoming a second
public operation model and coupling every operation to queue scheduling.

## Decision

Introduce an additive, PostgreSQL-backed **Durable Operation** substrate with a
separate **Operation Attempt** record. The operation is the authoritative
logical request. Attempts are physical claims to execute that request.

The substrate also requires:

* a scoped idempotency identity on admission;
* immutable principal provenance plus an application/framework resolver for a
  current `Principal`;
* a monotonically increasing fencing token, expiring lease, and attempt owner;
* a small current-state machine plus bounded transition records;
* a separate, operation-bound approval-decision record when approval is
  required;
* durable cancellation intent, an overall deadline, and attempt limits;
* a registered executor reference and effect classification;
* an executor-owned durable command body referenced by the operation.

Existing background tasks remain a queue/executor and may optionally reference
an operation. An operation can execute in the initiating request or through a
task, so neither concept owns the other universally. Task-only work remains
valid. Operation-backed task work uses the operation lease and fence as the
authority; the task lock becomes a scheduling projection and must not create a
second ownership regime.

Current operation state is stored in the operation row. Attempts, approval
decisions, and bounded transitions explain that state; they do not replace it
with event sourcing. Table names, columns, storage layout, and executor command
format remain internal implementation details.

## Guarantees

For an operation admitted through the durable API, Aksara will make these
testable guarantees:

1. **Durable admission.** A returned operation ID identifies committed
   PostgreSQL state. A status read can resolve it after process or worker
   restart until its documented retention deadline.
2. **One logical identity.** A scoped idempotency key plus the same canonical
   input resolves to the same operation during the retention window, including
   concurrent submissions.
3. **Attempt truth.** Each physical claim creates one immutable attempt identity
   with an ordinal and fencing token. Expired ownership is recorded as an
   abandoned attempt before a new attempt is claimed.
4. **Fenceable ownership.** Only the current attempt and fencing token may renew
   the lease, record progress, perform a framework-controlled mutation boundary,
   or finalize the operation.
5. **Current authorization.** The initiator is resolved to a current `Principal`
   and authorization, tenant, object, and field rules are checked immediately
   before every framework-controlled side-effect boundary. Approval cannot
   bypass this check.
6. **Atomic PostgreSQL completion.** When the application mutation and operation
   tables use the same Aksara PostgreSQL database and the executor participates
   in the operation transaction, the mutation, attempt success, operation
   success, and transition/outbox record commit or roll back together.
7. **Deterministic lost-response recovery.** After an ambiguous commit response,
   the same idempotency key finds the existing operation. `succeeded` proves
   that the framework-owned database mutation and authoritative completion
   committed together. A nonterminal state proves neither and is recovered by
   lease rules rather than by creating a second operation.
8. **Durable intent.** Approval decisions, cancellation requests, deadlines,
   attempt limits, and core attempt counters survive process restart.
9. **Bounded auditability.** Current state, attempts, decisions, and a bounded
   transition history remain queryable and can be retried to an application
   audit sink without making that sink authoritative.

"Current authorization" means the decision made from the resolver's current
identity and the database/policy state observed at the side-effect boundary. It
does not promise instantaneous global revocation linearizability across an
external identity provider.

## Non-Guarantees

* Aksara does not guarantee exactly-once delivery or exactly-once effects for
  email, payments, webhooks, LLM calls, or arbitrary external APIs.
* Aksara cannot undo an external effect or a PostgreSQL transaction that already
  committed before cancellation won the ownership check.
* Without a client-supplied idempotency key, Aksara cannot correlate a retried
  submission when the client lost the first admission response and operation
  ID.
* Atomic mutation/completion is unavailable across a different database,
  nontransactional resource, or executor that bypasses the operation context.
* Provenance is not an authorization grant. A role/scope snapshot from admission
  never authorizes resumed work.
* Operation history is bounded operational evidence, not application-owned
  compliance retention or a general event ledger.
* The substrate does not provide workflows, DAGs, conversations, agent memory,
  distributed scheduling, or provider reliability.

## Conceptual Model

`Operation` owns:

* an opaque, high-entropy operation ID;
* an application namespace, tenant scope, registered action reference and
  version, executor kind, and opaque command reference;
* immutable initiating-principal provenance and a resolver reference;
* canonical semantic input hash and optional client idempotency key/scope hash;
* effect classification;
* authoritative state, current attempt, current fence, next eligible time,
  deadline, attempt count, and maximum attempts;
* durable cancellation fields;
* bounded result or structured error envelope;
* correlation IDs and timestamps;
* a state/version value for conditional transitions.

`OperationAttempt` owns:

* a unique attempt ID, operation ID, ordinal, and fencing token;
* worker identity, state, lease expiry, heartbeat, start, and completion times;
* a structured outcome/error and retry classification;
* executor-specific usage summaries, where applicable.

`OperationApprovalDecision`, present only when needed, owns a decision bound to
the operation, input hash, tenant, requester, action, approver provenance, and
expiry. `OperationTransition` records bounded, redacted state changes and the
correlation/actor that caused them.

The durable command body is executor-owned. It is created in the same admission
transaction and addressed by the operation's opaque command reference. For a
task executor, the existing task payload can serve this role. For a generated
database action, an internal command store can hold versioned, validated input.
This prevents the shared operation row from becoming a universal workflow
payload while still making restart possible.

An executor that issues external mutations also owns a small durable
effect-intent entry. Before the network call, it records an operation-scoped
effect identity/ordinal, canonical request hash, provider reference, and stable
downstream idempotency key when available. That entry is executor-specific and
is not a public generic `ExternalEffect` model.

A non-binding schema sketch belongs in the design review. This ADR intentionally
does not freeze table or column names.

## Operation State Model

The operation states are:

* `waiting_for_approval`: admitted, but no valid approval decision is bound;
* `ready`: eligible now or after `available_at` for a first/retry attempt;
* `running`: one current attempt holds the lease;
* `succeeded`: terminal; the executor's success boundary committed;
* `failed`: terminal; a structured error explains denial, exhausted retries,
  invalid command, or an unknown external outcome;
* `cancelled`: terminal; cancellation won before a framework-controlled effect
  committed;
* `expired`: terminal; the operation/approval deadline passed before work could
  validly begin.

There is no `retrying` state. A retryable operation is `ready` with a future
`available_at` and a failed or abandoned prior attempt. Authorization failures
are structured codes rather than extra states: `identity_resolution_unavailable`
is retryable; `authorization_required` and `authorization_denied` are terminal
unless a future explicit administrative retry policy is designed.

| Current state | Event | Preconditions | Next state | Transaction boundary | Failure behavior |
| --- | --- | --- | --- | --- | --- |
| none | admit, no approval | Unique idempotency scope; valid registered action/command | `ready` | Insert operation, command, transition atomically | Duplicate resolves existing row; hash mismatch conflicts |
| none | admit, approval required | Same as above | `waiting_for_approval` | Same admission transaction | No executor may claim |
| `waiting_for_approval` | approve | Current approver authorized; bindings and expiry valid | `ready` | Decision insert and operation transition atomically | Concurrent/superseded decision loses condition |
| `waiting_for_approval` | reject | Current approver authorized | `cancelled` | Decision and terminal transition atomically | Rejection cannot be changed into approval |
| `waiting_for_approval` | approval/deadline expires | Database time past deadline | `expired` | Conditional transition | Claim remains impossible |
| `ready` | claim | Eligible; not cancelled/expired; attempts remain; required approval valid or already consumed | `running` | Lock row, consume first approval use, increment fence/count, insert attempt, set lease | Claim races use `SKIP LOCKED`; one wins |
| `ready` | cancel | Authorized caller; not terminal | `cancelled` | Cancellation and terminal transition atomically | Later claims see terminal state |
| `ready` | deadline expires | Database time past deadline | `expired` | Conditional transition | No new attempt |
| `running` | heartbeat | Matching current attempt, worker, fence; lease unexpired | `running` | Conditional update | Zero rows means ownership lost |
| `running` | retryable failure | Matching fence; retry budget/deadline remain | `ready` | Attempt failure, next time, operation transition atomically | If ownership lost, stale worker cannot write |
| `running` | terminal failure/denial | Matching fence | `failed` | Attempt and operation terminal transition atomically | Structured failure retained |
| `running` | lease expires and reclaim occurs | Database time past lease; same row locked | `ready`, then `running` under new claim | Mark old attempt abandoned; increment fence; claim atomically | Old worker is fenced |
| `running` | cancellation observed | Matching fence; effect has not committed | `cancelled` | Attempt and operation terminal transition atomically | If success transaction won first, state stays succeeded |
| `running` | success | Current auth/approval/cancel/fence checks pass | `succeeded` | Same transaction as framework DB mutation | Any exception/connection loss rolls back both or leaves commit outcome queryable |
| terminal | any execution transition | Never valid | unchanged | Reject/no-op | Terminal states never reopen implicitly |

## Attempt / Ownership Model

Attempts use `running`, `succeeded`, `failed`, `abandoned`, and `cancelled`.
An attempt is created only when claimed; there is no pending attempt.

| Attempt state | Event | Preconditions | Next state | Meaning |
| --- | --- | --- | --- | --- |
| none | claim | Operation `ready`; row lock held | `running` | New physical execution and fence |
| `running` | success | Still current; matching fence | `succeeded` | Operation success committed in same boundary |
| `running` | retryable/terminal error | Still current; matching fence | `failed` | Error recorded; operation becomes ready or failed |
| `running` | lease reclaimed | Lease expired; operation row locked | `abandoned` | Outcome before any external reconciliation is not assumed |
| `running` | cancellation observed | Matching fence; cancellation won | `cancelled` | Work stopped before framework-controlled commit |
| terminal | any | Never valid | unchanged | Attempts are immutable after terminal transition |

A claim transaction uses PostgreSQL time, locks the candidate operation, and
increments a monotonically increasing fencing token. It inserts the attempt and
sets `current_attempt_id`, worker ID, and lease deadline together. Heartbeats
renew only with all of `(operation_id, current_attempt_id, worker_id,
fencing_token, running state)` matching.

If Worker A owns token N, its lease expires, and Worker B claims token N+1,
Worker A's heartbeat, progress write, and completion update affect zero rows.
For a database mutation, A must validate and lock ownership inside the same
transaction as the mutation; a zero-row finalization raises and rolls back the
mutation. Worker B therefore remains authoritative.

## Transaction Semantics

For framework-owned mutations in the same PostgreSQL database, the executor
must use one pinned connection and transaction for:

1. locking the operation row;
2. verifying current attempt/fence, unexpired lease, cancellation, deadline,
   approval binding, and freshly resolved authorization;
3. applying the application mutation;
4. writing attempt success, operation success/result, transition, and audit
   outbox record;
5. committing once.

The current `transaction.atomic()` session reuse is a suitable mechanism, but a
prototype must prove that the executor cannot accidentally acquire a different
connection. Nested atomic blocks are PostgreSQL savepoints on the pinned
connection; they do not create a second commit authority.

| Failure point | PostgreSQL after recovery | Observation/recovery |
| --- | --- | --- |
| Before application mutation | Operation remains running until lease recovery; no mutation | Attempt becomes abandoned; retry reauthorizes |
| During application mutation | Transaction rolls back; no success state | Same recovery |
| After mutation, before success update | Transaction rolls back both | Same recovery |
| After success update, before commit | Transaction rolls back both | Same recovery |
| Commit succeeds, acknowledgement is lost | Mutation and `succeeded` both exist | Query/idempotent resubmit returns the operation/result |
| Lease lost before transaction starts | Ownership check fails; no mutation | Current owner continues |
| Lease would expire while success transaction holds the row lock | Reclaimer cannot supersede that locked row; commit success wins or rollback permits reclaim | No split-brain finalization |
| Connection drops during commit | Outcome initially uncertain to worker | Re-read by operation ID/key; atomic state distinguishes committed from retryable |

An external call cannot share this transaction. The action must declare its
effect class. Before issuing a mutating call, the executor commits its
executor-owned effect intent while its attempt/fence is current. The stable
effect identity and ordinal do not change across attempts; a deterministic
downstream idempotency key is derived from the operation and effect identity.
The intent means “this effect may have been attempted,” including if the worker
dies after recording intent but before or after sending the request.

After restart, an adapter with provider idempotency retries the same effect with
the same key. An adapter with authoritative provider status first reconciles
that identity before deciding whether to retry. If neither capability exists,
the operation becomes `failed` with `external_outcome_unknown`; Aksara must not
blindly retry or claim that the effect did or did not occur. This pre-effect
record narrows recovery ambiguity but cannot create a cross-system transaction.
Here `failed` means Aksara cannot safely establish completion; the reason code
does not assert that the provider failed or that the effect did not occur.

## Idempotency Semantics

Clients supply an idempotency key when they need safe recovery from a lost
admission response. Aksara always generates the operation ID, but a generated
key returned in that same lost response cannot help the client correlate a
retry.

Uniqueness is scoped by an internal hash of application namespace, tenant,
stable initiating-principal reference, registered action/version, and the
client key. Input is canonicalized from semantic path/body arguments after
schema normalization and excluding credentials, approval tokens, request IDs,
and other transport metadata.

* Same key and same input hash: return the existing operation and its current or
  terminal result; do not create an attempt merely because of resubmission.
* Same key and different input hash/action version: return a conflict; never
  reinterpret the old key.
* Concurrent duplicates: a PostgreSQL unique constraint selects one operation;
  the loser reads it and compares the hash.
* Expired keys: deduplication is promised only for the documented retention
  window. A tombstone must retain the scope and input hash for that entire
  window. After pruning, reuse may create a new operation and must be documented.
* Status reads: require current authorization and tenant filtering even when the
  caller knows the operation ID or idempotency key.

For operation-backed PostgreSQL mutations, this admission rule plus atomic
completion gives deterministic replay. For external systems it is only a stable
effect-identity and key-propagation pattern. The executor durably records intent
before the call, but the external provider's idempotency or reconciliation
contract determines whether a retry is safe.

## Identity Provenance and Reauthorization

Persist an immutable, versioned principal reference containing only stable
identifiers needed for resolution and audit: principal kind/auth method,
application identity namespace, stable subject/user ID, optional human owner
and agent IDs, tenant ID, non-secret token/credential ID where useful for
revocation lookup, resolver key, and correlation IDs. Persist the requested
action/resource/field policy context separately. Admission-time roles and
scopes may be recorded only as redacted audit provenance and never consumed as
authority.

Never persist bearer tokens, API keys, session cookies, approval tokens, or
other reusable credentials.

Applications register a resolver by stable key. On every attempt and before
each framework-controlled effect, it resolves the reference to a current
`Principal`. The normal permissions, `PolicyEngine`, tenant, object, field, and
RLS paths then run again against the current object and payload.

* Deleted principal, expired identity with no renewable stable identity,
  revoked permission, changed tenant membership, object denial, or field-policy
  denial: terminal `failed` with `authorization_required` or
  `authorization_denied`, before the effect.
* Temporary identity-provider/resolver outage: attempt fails retryably and the
  operation returns to `ready` with backoff.
* Missing/unregistered resolver or malformed provenance: fail closed as a
  terminal configuration/integrity error.
* Policy changes while queued apply on the next boundary. Admission approval is
  not grandfathered.

## Approval Semantics

The v0.6 signed grant remains valid for synchronous MCP calls and is unchanged.
It is deliberately stateless and is not treated as a durable workflow record.

An operation requiring delayed approval uses a separate durable decision. The
record can be pending, approved, rejected, expired, or superseded. Approval is
bound to exactly one operation ID, canonical input hash, tenant, requester
reference, and action version, and records a stable approver reference and
expiry. Changed input requires a new operation/decision.

"Single use" means the decision can authorize only its bound logical operation,
not that a crash consumes permission for all later attempts. Approval changes
the operation from waiting to ready; the claim transaction verifies expiry and
atomically records first consumption when the operation first enters `running`.
Retries of the same operation may rely on that consumption, subject to the
operation deadline and fresh authorization. Approval expiry applies before the
first claim; after valid consumption it does not turn crash recovery into an
unauthorized new operation.

Approval records human intent. Current authorization remains mandatory for the
requester, action, tenant, object, and fields, and for the approver at decision
time. Approval after requester permission revocation cannot run the operation.

Applications own approval UI, inboxes, notifications, escalation, SLAs, and
business-specific quorum/multi-approver rules.

## Cancellation and Limits

Cancellation is a durable request with requester provenance, timestamp, and
reason. It is not proof that arbitrary running code stopped.

* Waiting, ready, and retry-delayed operations cancel atomically before claim.
* Running workers check cancellation on heartbeat, before opening each
  framework side-effect boundary, again while holding the operation row lock,
  and between separately declared external effects.
* In-process coroutine cancellation is a best-effort optimization after the
  durable request commits.
* If success holds the row lock and commits first, success wins and a later
  cancellation returns a terminal-state conflict. If cancellation wins before
  the mutation boundary, stale completion fails its fence/condition.
* An external effect already in flight may complete. Unknown outcome is reported
  honestly and is not rewritten as cancelled.

Core durable limits are maximum attempts, attempt count, next eligible time,
and an overall deadline. Retry count is derived from attempts. Per-call timeout,
tool-call count, planner steps, provider calls, tokens, and cost belong to
executor-specific durable state. Applications own business quotas. Any durable
counter is updated transactionally and aggregates across retries; process-local
budgets are never reconstructed by guessing.

## Audit / History

The operation row is authoritative current state. Attempts and approval
decisions are authoritative facts about execution and decision ownership. A
bounded transition table records admission, claims, retries, decisions,
cancellation, terminal state, actor/correlation, and redacted error metadata.
It is not replayed to derive current state.

Each state-changing transaction also writes an outbox/export marker. Sink
failure leaves export pending and does not roll back a valid operation commit.
The existing `MCPExecutionAuditEvent` remains compatible and may gain optional
operation/attempt correlation fields in a later implementation.

Inputs, results, and errors have size limits, redaction rules, and separate
retention. Active operations are never pruned. Terminal operations,
idempotency tombstones, attempts, and transitions are pruned only after their
documented windows. Long-term compliance retention is application-owned. All
reads and exports enforce tenant and current-principal visibility.

## MCP Integration

Existing synchronous `tools/call` remains the default and retains the v0.6
authorization, approval, transaction, error, and audit behavior.

The current MCP 2026-07-28 protocol moved durable tasks to the
[`io.modelcontextprotocol/tasks`](https://tasks.extensions.modelcontextprotocol.io/specification/draft/tasks)
extension. It uses server-directed task creation and `tasks/get`,
`tasks/update`, and `tasks/cancel`. The official Python SDK 2.0 roadmap states
that this extension is [not yet implemented](https://github.com/modelcontextprotocol/python-sdk/blob/main/ROADMAP.md)
because it is wire-incompatible with the earlier experimental core task
feature. Aksara will not hand-roll a custom MCP workflow protocol or revive the
older `tasks/list`/`tasks/result` design.

An application will explicitly mark a separately registered tool/action as
durable. Once a supported official SDK exposes the extension, the MCP adapter
maps its task ID to an Aksara operation ID and projects operation states into
the protocol task states. It returns a task handle only when the client declares
the extension per request. Existing generated tool names are not silently
changed from synchronous results to durable handles.

The adapter translates the terminal *underlying `tools/call` outcome*, not the
Aksara operation-state label by itself:

| Underlying outcome | MCP Task projection |
| --- | --- |
| Successful `CallToolResult` with `isError` false or absent | `completed`, carrying that result |
| `CallToolResult` with `isError: true` | `completed`, carrying the tool-level error result |
| JSON-RPC/protocol execution error | `failed`, carrying the JSON-RPC error |
| Aksara operation actually reaches terminal cancellation | `cancelled` |

The MCP specification reserves `failed` for JSON-RPC execution errors and says
it must not represent non-JSON-RPC errors. Therefore Aksara `Operation.failed`
does not blindly project to MCP `failed`: an application-level terminal failure
that the synchronous tool contract expresses as `CallToolResult(isError=true)`
projects to a completed MCP task containing that error result. A cancellation
request alone also does not force `cancelled`; the adapter projects `cancelled`
only if cancellation wins and the operation reaches that terminal state. This
translation is MCP-adapter behavior and does not change the core operation
state machine.

Until official SDK support exists and passes protocol conformance, the MCP
durable adapter remains an experimental milestone. The operation substrate and
REST/Python boundary do not depend on MCP task support.

## Task Integration

The task queue remains an internal PostgreSQL queue with its existing task IDs,
enqueue/status APIs, queues, schedules, retry settings, and task-only behavior.
Tasks may exist without operations; operations may run synchronously without a
task.

An operation-backed task has an optional immutable link to its operation and
uses the operation claim/attempt/lease/fence path when executing. Task attempt
count remains a compatibility field and is not the authoritative operation
attempt count. One task claim can become an operation attempt; stale scheduling
recovery that occurs before operation claim need not. Operation attempts are
the only source for durable execution counts.

For linked work, stale task recovery must consult/delegate to the operation
lease and may not reset ownership independently. The task row can project
`pending/running/completed/failed` for old APIs after operation transitions.
Unlinked tasks retain the v0.6 stale-lock semantics. No existing task is
automatically upgraded to a durable authorized operation.

`DurableStep` remains separate and functional-but-evolving through v0.7. Its
sequential cached-step semantics, runtime DDL, `force=True`, and public result
reuse do not match lease-backed authorized operations. It is neither removed
nor advertised as satisfying this ADR. A later opt-in adapter may execute a
step as an operation after compatibility and stale-running semantics are
designed.

## PostgreSQL and Infrastructure Decision

PostgreSQL remains sufficient for the intended guarantee. Aksara already
requires it and already proves internal migrations, transactions, tenant
session context, `FOR UPDATE SKIP LOCKED`, unique constraints, JSONB, and
multi-worker task claims. Operation admission, leasing, fencing, atomic
completion, bounded history, and pruning need those same primitives.

Claims use a partial/covering eligibility index and bounded batches. Heartbeats
use conditional updates and database time. Cleanup avoids active rows and uses
bounded batches. Advisory locks remain appropriate for migration serialization,
but row locks and fence conditions own per-operation execution.

Redis, Kafka, Celery, and Temporal add split-brain authorities and deployment
requirements without satisfying a code-derived need. Reconsider external
infrastructure only after measured PostgreSQL contention or scheduling needs
exceed documented targets.

## Public API Boundary

The eventual stable boundary is semantic:

* an opaque operation ID;
* explicit submit/dispatch for a registered operation action;
* status/result/error retrieval;
* cancellation request;
* idempotency conflict and retention behavior;
* current authorization and tenant visibility rules.

Existing synchronous generated REST routes stay synchronous. A separate
opt-in durable route/Python API returns `202 Accepted` with an operation ID and
`Location` for a new or existing nonterminal operation. An idempotent resubmit
of a terminal operation returns its existing representation with `200 OK`; a
changed input under the same key returns `409 Conflict`. Status/cancel require
current authorization. Listing is optional, cursor-paginated, tenant-filtered,
and may be deferred; attempt inspection is an administrative/diagnostic API,
not required for the minimal client contract.

The public representation does not expose table names, fence tokens, worker
IDs, command references, raw provenance, internal payloads, or transition row
shape.

## Compatibility

The architecture is additive:

* v0.6 REST behavior and status codes do not change unless an application opts
  into a new durable route/action;
* synchronous MCP `tools/call` and signed approval grants remain supported;
* `Principal` remains the runtime authorization object; the new reference is a
  durable locator, not a replacement;
* current MCP audit fields remain valid, with only optional correlation
  additions;
* current task IDs/APIs and unlinked task behavior remain valid;
* `DurableStep` remains available with its existing semantics;
* internal operation tables are created by versioned framework migrations, not
  runtime startup DDL;
* installed applications need not adopt durable operations.

## Security Considerations

* Reauthorization at each controlled effect prevents stale admission roles,
  scopes, tenant membership, policy, object access, and field rules from acting
  as authority.
* Unique scoped idempotency plus input hashing prevents replay with changed
  arguments. Keys are treated as untrusted bounded strings and stored hashed.
* Operation IDs are high entropy; tenant/current authorization remains the real
  lookup control. Unauthorized and nonexistent IDs return indistinguishable
  responses where enumeration risk requires it.
* Provenance and commands are immutable after admission, writable only through
  restricted framework code/database roles, versioned, and hashed for integrity
  checks. No reusable credential is stored.
* Executor references resolve only through an application allowlist; database
  payloads cannot select arbitrary imports or SQL.
* Approval binds operation, input, tenant, principals, action, and expiry;
  conditional decision transitions prevent reuse/supersession races.
* Lease/fence checks occur in the mutation transaction, preventing a late
  worker from committing a framework database effect.
* Cancellation is checked under the same row lock as the mutation/finalization.
* Result/error/audit fields are bounded, redacted, retained separately, and
  filtered by tenant and current authorization.
* Worker identity is not trusted by itself; ownership requires the unguessable
  attempt ID and current monotonic fence stored in PostgreSQL.
* Direct transition-table writes are denied to application callers. State
  changes use conditional transition functions and emit history in the same
  transaction.

## Failure Semantics

One client mutation, Worker A's death, Worker B's retry, a database commit, a
lost response, and a client resubmit produce **one operation and two attempts**.
A is `abandoned`; B and the operation are `succeeded`. The mutation and success
state committed together. The idempotent resubmit returns that same operation
and result. If A wakes, its token N no longer matches N+1, so its completion
fails and any same-database mutation in that transaction rolls back.

Retryable failures create a new attempt only after the prior attempt becomes
terminal/abandoned and the operation is `ready`. Terminal authorization,
validation, approval rejection, exhausted retry, and unknown non-idempotent
external outcome fail or cancel the operation with a stable structured code.
No recovery process infers success from a missing acknowledgement.

For an external mutation, recovery also consults the executor-owned durable
effect intent written before the call. Provider idempotency permits the same
stable-key retry; authoritative provider status permits reconciliation first;
otherwise a missing local result is `external_outcome_unknown`, even when the
worker may have died before the provider received the call.

The detailed design review contains the complete failure matrix.

## Alternatives Considered

1. **Shared Operation + Attempt substrate — selected.** It separates logical
   identity from queue mechanics, supplies atomic/fenceable truth, and lets
   task, request, REST, and MCP adapters opt in without universalizing any one
   executor.
2. **Extend `aksara_tasks` into the universal primitive — rejected.** It looks
   incremental, but it couples synchronous work to queue concepts, changes a
   stable task record into a security/public operation model, preserves one-row
   retry history, and creates awkward approval/status semantics for non-task
   calls.
3. **Shared ID plus separate state and an event ledger — rejected.** Correlation
   improves, but multiple subsystems can still disagree on current state,
   ownership, completion, and cancellation.
4. **Event-sourced operations — rejected.** It can model history but introduces
   projection consistency and replay/versioning as new correctness problems.
   Aksara needs a small state machine, not event sourcing.
5. **External durable engine — rejected.** It adds a mandatory service and a
   second transaction/authorization boundary while Aksara's critical mutation
   guarantee depends on its own PostgreSQL transaction.
6. **Transactional receipt/outbox only — rejected as the primary model.** A
   receipt solves committed-mutation/lost-response ambiguity, but cannot model
   worker attempts, leases, approval waiting, cancellation, or recovery. Its
   outbox idea is retained for audit export.

## Consequences

Positive consequences:

* one queryable authority spans request and task executors;
* crash recovery and lost responses have deterministic database answers;
* current security rules remain the execution authority;
* v0.6 APIs can coexist without mandatory migration of application behavior;
* PostgreSQL remains the only required runtime service;
* MCP can map to its official task extension rather than defining a protocol.

Costs and limitations:

* executor authors must classify effects and participate in the operation
  transaction/fence contract;
* applications must supply stable principal resolvers for delayed user/agent
  work;
* leases, heartbeats, pruning, result redaction, and status authorization create
  meaningful implementation and test burden;
* external effects remain provider-dependent and can have unknown outcomes;
* task projection and operation state must be tested against drift during the
  additive transition;
* official Python SDK support currently gates standards-based durable MCP.

## Explicit Non-Goals

This decision does not build a generic workflow/DAG engine, Temporal clone,
multi-agent orchestrator, agent memory, persistent conversation system,
planner stabilization, provider redesign, Studio workflow UI, generic event
sourcing, distributed scheduler platform, or general observability platform.
It does not promise exactly-once arbitrary external effects. It introduces no
Kafka, Redis, Celery, new ORM functionality, custom many-to-many through-model
support, or other deferred ORM feature.

## Validation Required Before Stability

1. Model/state-machine tests for every allowed and invalid transition.
2. PostgreSQL integration proof that application mutation, fence validation,
   operation/attempt success, history, and outbox share one connection and
   commit.
3. Two-process kill/restart tests at every transaction boundary, including
   uncertain commit acknowledgement.
4. Lease test where A/N expires, B/N+1 claims, and A cannot mutate/finalize.
5. Concurrent idempotency tests for same and conflicting canonical inputs.
6. Reauthorization tests for deleted principals, expired credentials, role,
   tenant, permission, policy, object, and field changes, plus resolver outage.
7. Approval binding, supersession, expiry, retry, and permission-revocation
   tests.
8. Cancellation races before claim, during delay, at the mutation lock, during
   external work, and after success.
9. Restricted-role/RLS tests for operation lookup, result visibility, transition
   writes, and audit export.
10. Task compatibility/projection tests with linked and unlinked tasks and stale
    recovery.
11. Result/payload size, redaction, retention, pruning, and outbox sink-failure
    tests.
12. External pre-effect tests for death before send, after provider effect, and
    before local result recording, covering idempotent, reconcilable, and
    neither-capability providers.
13. Load/contention benchmarks for eligible-claim indexes and heartbeat writes.
14. Official SDK and MCP conformance tests before enabling the Tasks extension;
    do not implement against the obsolete experimental core task API.
15. Installed-wheel and hosted PostgreSQL 16 validation across the supported
    Python/FastAPI/Starlette matrix.

## Open Questions

These implementation details do not change the selected architecture:

* What bounded/encrypted command and result storage policy should be the safe
  default, and which fields may an application redact before persistence?
* Should the first public durable REST surface be a generic registered-action
  endpoint or generated per-action endpoints? A prototype should compare
  authorization clarity and OpenAPI quality without changing current routes.
* Which physical foreign-key direction best links a task and operation while
  preserving independent retention?
* What default lease, heartbeat, idempotency, result, and transition retention
  values meet the production reference workload?
* Which official Python SDK release first supports the 2026-07-28 Tasks
  extension, and does it expose the server hooks Aksara needs?
* Should admin attempt inspection ship in v0.7 or remain diagnostics-only?
