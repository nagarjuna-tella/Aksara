# Executive Summary

Decision record: [ADR 0001 — Durable Authorized Operations](docs/adr/0001-durable-authorized-operations.md).

Aksara should implement v0.7 as **Durable Authorized Operations**: an additive,
PostgreSQL-backed logical `Operation` with separate physical `Attempt` records,
optional durable approval decisions, fenceable leases, scoped idempotency,
current-principal resolution, durable cancellation intent, and bounded
transition history.

The design exists to close a specific split in current code. MCP has the
identity, authorization, policy, approval, transaction, error, and audit
semantics, but loses execution state when the process disappears. Background
tasks have PostgreSQL persistence, claims, retries, and worker recovery, but
persist only tenant identity and cannot atomically connect user work to task
completion. `DurableStep` caches a completed result, but has no worker-death
recovery or ownership fencing. None can authoritatively answer whether one
authorized mutation committed after the response was lost.

The selected model joins those missing semantics without turning the task queue
into a public security model or Aksara into a workflow engine. Existing tasks
remain tasks and can optionally link to operations. Existing synchronous REST
and MCP calls remain synchronous. Durable behavior is explicit and opt-in.
Planner state, investigation sessions, provider calls, and business workflows
remain executor/application concerns.

For framework-controlled mutations in the same PostgreSQL database, v0.7 can
guarantee that the application mutation and authoritative operation success
commit or roll back together. It cannot make an arbitrary external effect
exactly once. External adapters receive stable idempotency context when the
provider supports it. Before a mutating call they persist executor-owned intent
with a stable effect identity and ordinal, so recovery can retry the same
provider key, reconcile from provider authority, or record an unknown outcome
instead of blindly repeating the call.

The MCP 2026-07-28 protocol has an official
`io.modelcontextprotocol/tasks` extension whose lifecycle maps well to the
operation model. The official Python SDK 2.0 roadmap currently lists that
extension as not implemented. Aksara should preserve synchronous `tools/call`,
avoid the obsolete experimental task API, and gate standards-based durable MCP
on an official SDK release and conformance tests.

No production code, schema, migration, or public API is implemented by this
review.

# Current Execution Systems

The review used the released v0.6.1 source at `f47f5c1`, including the release
evidence, stability contract, source, tests, and user documentation. The table
describes what each current subsystem can actually prove.

| Subsystem | Execution identity | Persisted state | Lost on restart | Authorization carried | Retry/recovery | Authoritative/atomic completion |
| --- | --- | --- | --- | --- | --- | --- |
| MCP runtime | Request ID, run ID, tool-call ID, tool/action name in immutable `AgentInvocationContext` | No operation state | Invocation context, replay set, session state, runtime budget, cancellation task | Full current `Principal`; audience, scope, tenant, permission, object, field, and RLS enforcement | Process-local duplicate guard; no cross-worker resume | Generated write runs in `atomic()`, but no durable success record; audit occurs afterward |
| MCP approval | Approval ID in signed HMAC token | Nothing server-side | Consumption/reuse knowledge | Token binds principal hash, tenant, tool, args, approver, expiry | Token can be presented again while valid | Proof for one exact synchronous invocation shape; not durable decision state |
| MCP audit | Request/run/tool-call correlation | Logging/JSONL/application sink if configured | Default logging and memory sink continuity | Redacted principal/tenant/decision fields | Sink errors are swallowed | Observable record; never operation authority |
| Task queue | UUID task ID | Name, queue, tenant, JSON payload, status, attempts, max attempts, availability, `locked_at`, result/error | Worker/callable state and full principal | Tenant only | `SKIP LOCKED`, retry delay/backoff, stale `locked_at` reset | Task row is task authority; user effect and `completed` update are separate |
| Recurring tasks | Registered task name | Last enqueue time | In-process registry | No requester principal | Atomic schedule slot; enqueues task | Cron state is scheduling authority only |
| `DurableStep` | `(workflow_id, step_name)` | Running/failed/completed, result/error/timestamps | Callable state and owner | None | Failed may re-run; running never recovers without force | Row is cache authority; effect and completion are separate |
| Investigation sessions | In-memory session/step IDs | Nothing durable | Entire session, plan, findings, step progress | No durable principal | Resume only in same process; failed steps are local data | Experimental in-memory object |
| AI prompt runtime | Current call/budget object | Nothing | Steps/tool-call IDs/tokens/cost and timeout state | Caller context outside durable model | Provider errors returned; no durable retry | Experimental call result only |
| `Principal`/`PolicyEngine` | User/agent/token/tenant identity in immutable runtime object | No durable execution record | Resolved roles/scopes/expiry/metadata | It is the live authorization input | Re-resolved per request, not per delayed task | Policy decision is current evaluation, not durable permission |
| ORM transaction/session | Pinned async context connection | PostgreSQL transaction state | Context variable/connection ownership | Tenant GUC applied to connection | Rollback/cleanup under error/cancellation | PostgreSQL commit is authoritative within one connection |
| Migration executor | Migration name/checksum and advisory-lock owner | Applied migration rows | In-process discovery state | Trusted operator/system path | Session advisory lock serializes migration work | Transaction/migration record semantics, not runtime work |

## Repository evidence anchors

| Source | Decisive evidence used |
| --- | --- |
| `aksara/mcp/context.py` | `AgentInvocationContext` is immutable but lives only in a `ContextVar` |
| `aksara/mcp/server.py` | Process-local replay guard; current authorization path; generated REST reuse; mutation `atomic()`; audit after execution |
| `aksara/mcp/approval.py` | Exact signed grant binding and absence of durable consumption/state |
| `aksara/mcp/audit.py` | Redacted deterministic event shape and application sink; sink is not authority |
| `aksara/tasks.py` | `SKIP LOCKED` claim, tenant-only provenance, aggregate attempts, timestamp stale recovery, unfenced completion |
| `aksara/core/migrations/0001_runtime_tables.py` | Tasks are framework-owned through internal migrations |
| `aksara/workflows.py` and `tests/test_durable_workflows.py` | Sequential result cache, runtime DDL, failed retry, running rejection, and `force=True` overwrite semantics |
| `aksara/ai/session_store.py`, `investigation.py`, `investigation_runner.py` | Investigation/session/step state is process-local and experimental |
| `aksara/ai/limits.py` and `runtime.py` | Tool/step/token/cost budgets and timeouts are in-memory execution state |
| `aksara/security/principal.py`, `policy.py`, and `enforcement.py` | Runtime Principal contains mutable authorization facts; current action/tenant/field decisions are reusable seams |
| `aksara/db/transaction.py` and `session.py` | Nested work reuses the pinned connection; rollback and cancellation cleanup are exception-safe |
| `aksara/migrations/executor.py` | PostgreSQL advisory lock serializes framework/application migrations, not per-operation work |
| `docs/docs/advanced/background-tasks.md` | Stable documentation explicitly limits tasks to tenant provenance and application-owned delayed authorization |
| `docs/docs/ai-mode/mcp.md` | Stable synchronous MCP scope and explicit process-local replay/approval-workflow limits |
| `README.md` and `docs/docs/roadmap/v0-6-stability-contract.md` | v0.6 stable/evolving/experimental compatibility boundary |
| `RELEASE_EVIDENCE_v0.6.0-rc2.md`, `RELEASE_EVIDENCE_v0.6.0.md`, and `RELEASE_EVIDENCE_v0.6.1.md` | Real PostgreSQL, installed-wheel, official MCP-client, rollback, and bounded-state validation baseline |

## MCP execution

`aksara/mcp/server.py` creates an immutable `AgentInvocationContext` from the SDK
request context and current server-resolved principal. It checks authentication,
AI-agent type, expiry, audience, tenant, and required scope before dispatch. The
generated REST path then reuses ViewSet permission/object/payload policy and ORM
tenant/RLS behavior. This reuse is an architectural asset: durable execution
should call the same policy and generated action seams instead of inventing an
authorization system.

For POST/PUT/PATCH/DELETE, `_invoke_generated_api()` surrounds the internal ASGI
request with `transaction.atomic(db=self.app.db)`. An HTTP failure raises a
private exception so partial writes roll back. The transaction ends before the
outer `finally` emits `MCPExecutionAuditEvent`. Thus synchronous database
rollback is strong, while audit and response loss are not connected to a
durable outcome.

`_ReplayGuard` is a locked dictionary with a monotonic TTL and 10,000-entry
bound. Its key is token ID, tool name, and explicit tool-call ID. It prevents a
duplicate in one process while the entry lives. It cannot correlate another
worker, a restart, or a client that changed tool-call ID after losing a
response.

The approval manager signs a canonical payload containing tool, argument hash,
principal hash, tenant, approver, decision, and expiry. Verification correctly
happens before execution. It has no durable consumption, supersession, inbox,
or cross-worker reuse record. The user docs explicitly describe those limits.

Audit events contain redacted/hashed arguments, identity/correlation, policy,
approval, outcome, error, status, and duration. Sink failures are logged and
swallowed so observability does not break the request. This is appropriate for
an export sink and insufficient for authoritative execution state.

Cancellation is Python coroutine cancellation for the active request. Runtime,
tool, provider, token, cost, step, and tool-call limits live in mutable in-memory
budgets. Those controls are valid for one process lifetime but cannot resume.
Tool failures already have the stable `client`, `authorization`, `transient`,
and `internal` categories plus a retryable flag; the operation model should
reuse that distinction rather than infer retryability from exception text.

## Background tasks

`aksara_tasks` is installed through the internal runtime migration and also has
legacy runtime `CREATE TABLE IF NOT EXISTS` compatibility. It stores a UUID,
registered name, queue, tenant, JSON payload, four-state status, aggregate
attempt count, max attempts, availability/lock/completion times, last error,
and result. `enqueue_task()` captures only `tenant_id_var`; the released docs
state that it does not capture a full `Principal`, role, scope, credential, or
authorization decision.

Claims are a sound queue primitive: a CTE selects an eligible pending row with
`FOR UPDATE SKIP LOCKED`, and one statement moves it to running, increments
attempts, and sets `locked_at`. Queues filter that selection. Recurring
scheduling uses atomic `INSERT ... ON CONFLICT ... WHERE` state, avoiding double
enqueue among workers.

The stronger operation guarantee exposes four gaps:

1. `locked_at` is a timestamp, not a lease with a worker/attempt owner or
   heartbeat.
2. stale recovery resets every old running row to pending without fencing the
   old worker;
3. completion/failure updates use only `WHERE id = ...`, so a late old worker can
   overwrite newer state;
4. the registered callable completes before the task row is updated, and the
   two are not in one transaction.

Worker shutdown drains in-flight tasks gracefully, but kill/crash recovery
depends on the stale timestamp. A killed worker after an application commit and
before task completion can cause the callable to run again. The v0.6 contract
properly requires applications to make external task effects idempotent and
does not claim exactly once. There is no task cancellation state or cancellation
API in the current model.

## DurableStep and workflows

`DurableStep` lazily creates `aksara_durable_state` and atomically claims a
missing or failed `(workflow_id, step_name)` with `INSERT ... ON CONFLICT`. A
completed row returns cached JSON. A running row rejects another caller, while
`force=True` overwrites any state and executes again.

It is a sequential memoized-step primitive. It has no tenant, principal,
approval, attempt history, owner, lease, heartbeat, fence, cancellation,
deadline, or stale-running recovery. The callable and completed-row update are
separate. A worker death leaves running forever unless application code clears
or forces it. Its public `force=True` and cached-result semantics do not match
the operation state machine.

## AI runtime, planner, and investigations

Investigation `Session` and `Step` objects use created/planning/running/paused/
completed/failed and pending/running/done/failed/skipped states, respectively,
but `session_store.py` is a process-local dictionary. Its own module notes say
multi-worker persistence is future work. The runner updates the dictionary
between sequential steps.

`AgentRuntimeBudget` tracks steps, tool calls, seen tool-call IDs, tokens, and
cost in memory. Provider and run timeouts use `asyncio.timeout`. Planner,
provider, investigation, and Studio behavior are experimental and have several
different run/session vocabularies. `ai/workflows.py` produces read-only,
human-applied plans rather than executing pushes. `ai/planner.py` can
topologically order an in-memory `AiPlan`, execute step handlers, and collect
results under current limits, but it persists neither plan nor attempt truth.
These are evidence that executor-specific state must stay outside the shared
substrate, not evidence for a general agent workflow model.

## Security

`Principal` is immutable and includes stable-looking identifiers plus mutable
authorization facts: roles, scopes, expiry, flags, and metadata. MCP credential
claims include subject, human owner, agent, tenant, audience, token ID, issue/
expiry, roles, and scopes. Persisting the full object would turn a point-in-time
snapshot into an ambient grant.

The release material sometimes calls this boundary `AgentPrincipal`; the
current implementation has one `Principal` type with `for_ai_agent()` and
`for_mcp_agent()` constructors rather than a distinct durable `AgentPrincipal`
class. The durable design therefore references `Principal` identity fields and
does not invent a second runtime authority type.

`PolicyEngine.can()` checks expiry, anonymous protected actions, scopes,
audience, tenant presence, cross-tenant resources, and principal type.
`validate_payload()` combines action authorization with field write policy.
Generated endpoints also apply permission classes, object rules, serializers,
ORM validation, tenant query filters, and PostgreSQL RLS. Durable work must
reconstruct a current `Principal` and reuse all these enforcement layers at the
effect boundary.

The existing identity code resolves principals from current request/session/
claims. It does not define a durable resolver from stable identity references.
That resolver is a required new application/framework integration seam.

## Migrations and transactions

Framework-owned runtime tables are versioned internal migrations discovered
before application migrations. That is the production-safe path for new
operation state; `DurableStep` runtime DDL is not a precedent to extend.

`TransactionManager` acquires or reuses the active session connection, applies
tenant context when it owns the connection, pushes it to a `ContextVar`, and
starts an asyncpg transaction. Nested use reuses the connection and therefore
creates nested asyncpg transaction/savepoint semantics. It rolls back on any
exception and carefully releases/reset connections on `BaseException`,
including cancellation. This is the code seam needed for same-database atomic
completion, subject to a prototype proving all executor writes use the pinned
connection.

Migrations use a PostgreSQL advisory lock because they serialize a database-wide
administrative action. Runtime operation ownership is per row and should use
row locks and fencing conditions; per-operation advisory locks would be harder
to recover and observe.

# Duplication and Architectural Seams

The duplication is semantic rather than merely naming:

* MCP `request_id`/`run_id`/`tool_call_id`, task UUID, workflow ID/step name, and
  investigation IDs all identify work, but only task/step IDs persist.
* MCP replay IDs, task aggregate attempts, `DurableStep` failed re-entry, and AI
  seen-tool-call IDs all approximate retry/duplicate behavior without one
  logical-operation rule.
* MCP has authorization provenance but no persistence; tasks persist tenant but
  no authorization provenance; workflows persist neither.
* Tasks and `DurableStep` both write running/completed/failed status but neither
  can fence a dead worker or atomically bind effects to completion.
* MCP audit describes an outcome but cannot prove it; task state records an
  outcome but can disagree with committed application data.
* MCP cancellation and budgets are bounded to a live coroutine, while delayed
  tasks have neither durable cancellation nor resumable counters.

The seam is therefore not “store more agent state.” It is “give every opted-in
authorized side effect one logical database authority and fence each physical
execution against it.”

# Derived Requirements

The classifications are intentionally narrower than a workflow-engine
checklist.

| Candidate | Classification | Reason derived from current code/guarantee |
| --- | --- | --- |
| Durable logical operation ID | REQUIRED | Current IDs do not survive consistently; lost response needs one authority |
| Separate attempts | REQUIRED | Task retries and worker death create multiple physical executions of one request |
| Small state machine/timestamps | REQUIRED | Status and terminal truth must survive/recover and be queryable |
| Bounded result/error envelope | REQUIRED | Lost clients need the eventual answer; current tasks already persist both |
| Tenant | REQUIRED | Aksara's stable isolation contract must cover lookup, claim, execution, and export |
| Principal provenance | REQUIRED | Delayed work must identify the initiator without storing authority/credentials |
| Current principal resolver | REQUIRED | Current roles/tenant/policy cannot be reconstructed from an admission snapshot |
| Reauthorization at effects | REQUIRED | v0.6 execution-time authorization must remain true after delay/restart |
| Scoped idempotency | REQUIRED for mutating durable admission; OPTIONAL for safe reads | Lost admission/commit responses otherwise create a second logical mutation |
| Retry policy/backoff | REQUIRED minimum | Worker loss/transient DB or resolver failure must recover; executor decides which errors retry |
| Lease, heartbeat, owner | REQUIRED | `locked_at` recovery alone admits a late-worker race |
| Monotonic fencing token | REQUIRED | Conditional completion must reject the stale claimant |
| Cancellation intent | REQUIRED | v0.7 promise includes durable cancellation, bounded to controlled boundaries |
| Approval decision | OPTIONAL per action; REQUIRED when action declares approval | Current signed token cannot represent delayed pending/decision/supersession |
| Core attempt/deadline counters | REQUIRED | Retry and total-duration bounds must survive workers |
| Tool/provider/token/cost counters | EXECUTOR-SPECIFIC | They matter to AI/MCP adapters and would pollute ordinary operations |
| Planner/session state | EXECUTOR-SPECIFIC and DEFERRED | Experimental; not required for one durable authorized effect |
| Correlation IDs | REQUIRED | Existing request/run/tool-call audit continuity should not disappear on dispatch |
| Attempts and bounded transitions | REQUIRED | Needed to explain claims/recovery/decisions without event sourcing |
| Long-term audit retention | APPLICATION-OWNED | Existing sink contract and compliance policy are application-specific |
| Retention/pruning | REQUIRED framework policy | Bounded tables, results, and idempotency promises require explicit windows |
| Executor/action reference and version | REQUIRED | Restart must resolve a safe registered handler and unchanged semantics |
| Executor command body | EXECUTOR-SPECIFIC but durably REQUIRED | Task payload and generated action args have different storage/security needs |
| External-effect classification | REQUIRED at action registration | Retry safety differs fundamentally between same-DB and external effects |
| External pre-effect intent/identity | EXECUTOR-SPECIFIC but REQUIRED for mutating external actions | A crash after provider execution but before local result recording must leave durable evidence that the effect may have been attempted |
| External idempotency adapter/context | OPTIONAL framework helper | Useful when providers accept a key; cannot create provider guarantees |
| Workflow graph/DAG/dependencies | UNNECESSARY | No v0.7 guarantee or stable code requires orchestration |
| Event-sourced state derivation | UNNECESSARY | Current-state row plus bounded evidence answers the requirement more simply |
| Redis/Kafka/Celery/Temporal | UNNECESSARY now | PostgreSQL already supplies required locking, uniqueness, transactions, and queue claims |
| Approval UI/inbox/notifications/escalation/quorum | APPLICATION-OWNED | No current framework business model can define these generically |
| Business quotas/SLAs | APPLICATION-OWNED | They depend on domain/customer policy |
| Durable conversations/agent memory | DEFERRED | Explicitly outside v0.7 and irrelevant to non-LLM operations |

# Guarantee Definition

The stable v0.7 guarantee should be stated before tables or endpoint names:

> Once Aksara returns a durable operation ID, PostgreSQL contains the
> authoritative logical request, immutable identity provenance, canonical input
> identity, current state, and retention deadline. Process restart and worker
> loss do not erase them. Each claim creates a separately identifiable,
> lease-bound, monotonically fenced attempt. Before every Aksara-controlled
> side effect, the framework resolves a current Principal and reapplies current
> permission, tenant, object, field, policy, and approval rules. For an Aksara
> PostgreSQL mutation performed on the same database through the operation
> context, the mutation and operation success commit or roll back in one
> transaction. A duplicate with the same scoped idempotency key and canonical
> input returns the same operation during the retention window. Cancellation is
> durable intent checked at controlled boundaries. External effects follow the
> declared executor/provider idempotency contract and may have an unknown
> outcome; Aksara never describes them as exactly once.

Consequences of the words in that guarantee:

* **Durable** means committed PostgreSQL state survives request completion,
  process restart, worker replacement, and transport loss for a documented
  retention window. It does not mean infinite retention.
* **Authoritative** means the operation row is the current answer. Logs,
  callbacks, task projections, and HTTP responses do not override it.
* **Succeeded** for a same-database executor proves both the application
  mutation and operation/attempt terminal success committed. For an external
  executor it proves only the declared adapter success condition.
* **Retry** means a new Attempt for the same Operation, after current
  authorization and ownership checks. It never means a new logical operation.
* **Idempotent admission** is scoped and time-bounded. It does not turn all
  executor effects into exactly once.
* **Approval** is a durable human/application decision bound to one operation.
  It never freezes or replaces current authorization.
* **Cancellation** can stop unclaimed work and can win an atomic database race;
  it cannot undo a committed or already-issued external effect.
* **Lost response** is resolved by reading the same operation. If the client
  lost admission before learning the operation ID, a client key is necessary.

# Architecture Alternatives

## Comparative assessment

| Rank | Alternative | Fit/compatibility | Correctness and recovery | Complexity/dependencies | Principal risks |
| ---: | --- | --- | --- | --- | --- |
| 1 | A. Shared Operation + Attempt | Additive; task/request/MCP adapters opt in | One authority, separate attempts, leases/fences, atomic DB completion | Moderate internal model; PostgreSQL only | Must constrain scope to avoid workflow creep |
| 2 | B. Evolve task table universally | Reuses queue but changes task meaning/API | Could add fences/idempotency, but sync work and approval become queue-shaped | Large task migration and compatibility burden | Universal queue abstraction; retry history still awkward |
| 3 | F. Transactional receipt + outbox | Excellent for synchronous DB mutation | Solves lost commit response and audit export only | Small | Cannot model waiting, worker attempts, leases, approval, or cancellation |
| 4 | C. Shared ID + separate states + ledger | Very additive | Correlates disagreements rather than preventing them | Multiple authorities plus reconciliation | Ambiguous status/ownership; accidental distributed transaction |
| 5 | D. Event-sourced operation | Extensible history | Can derive state if projections/replay are correct | High schema/versioning/projection burden | Replaces one failure problem with lag/rebuild consistency |
| 6 | E. External execution engine | Mature scheduling possible | Still needs Aksara DB authorization and atomic bridge | New service, SDK, operations, split transactions | Vendor coupling; engine becomes false authorization authority |

## Alternative A — shared Operation + Attempt

This is the only option that matches the observed separation between logical
identity and physical execution. It can reuse task claims as an executor without
making every operation a task. The same operation row can be locked in the
application mutation transaction, so fencing and success are enforceable where
Aksara already has its strongest guarantee. Approval, cancellation, and
idempotency attach to the logical operation and do not reset on retry.

Migration and maintenance cost are real: new internal models, transition code,
resolver registry, pruning, and fault tests. Compatibility remains additive
because existing APIs do not need to create operations.

## Alternative B — evolve the task table

This initially appears smallest because tasks already persist and use
`SKIP LOCKED`. In practice it overloads `task_name`, queue, `available_at`, and
aggregate `attempts` with a public authorized-operation contract. Synchronous
request execution would either create fake tasks or duplicate task-less paths.
Approval waiting and current-principal resolution would become properties of a
queue record. Task result cleanup could accidentally erase idempotency truth.
The current four states and `WHERE id` completion must change substantially,
and old task operators would observe new statuses/semantics.

Tasks remain a strong executor and scheduling primitive. They are the wrong
logical authority.

## Alternative C — shared execution ID and ledger

Adding one ID to MCP, tasks, and workflows improves correlation. A common event
ledger can record what each subsystem claims. It cannot decide which subsystem
owns success, how cancellation races with completion, or which worker is
current. Correctness would require a reconciliation protocol among MCP state,
task rows, workflow rows, and ledger projections. The design retains the exact
split v0.7 must remove.

## Alternative D — event-sourced operation

An append-only log naturally preserves history and could derive state. The
required state machine is small, while event sourcing adds projection lag,
event versioning, replay, snapshot, ordering, compaction, and repair concerns.
Conditional current-state transitions are much easier to put in the same
transaction as application mutation. Bounded transitions are retained as
evidence, not as the source of truth.

## Alternative E — external durable engine

Celery can distribute tasks and Temporal can express durable workflows, but
neither is Aksara's current authorization or application PostgreSQL transaction
authority. An external engine would still need the operation/provenance/
idempotency bridge, plus a two-system completion problem. It adds deployment
and operational burden to every adopter without a measured scale requirement.
It can be an application executor later; it should not be v0.7 infrastructure.

## Alternative F — transactional receipt and outbox

A receipt keyed by idempotency key, written with the database mutation, is a
strong smaller answer for synchronous calls. It cannot represent approval
waiting, a current worker, a dead attempt, lease renewal, delayed cancellation,
or retries before success. The outbox portion is valuable for transition/audit
export and is included in the selected design.

# Recommended Architecture

The architecture consists of a small shared kernel and adapters:

```text
durable admission
  -> Operation (logical authority, idempotency, provenance, state)
       -> optional OperationApprovalDecision
       -> OperationAttempt N (lease + fence + physical outcome)
       -> bounded OperationTransition / audit outbox
       -> executor binding
            -> request executor
            -> optional linked aksara_task
            -> future MCP Tasks projection
            -> application executor
```

The kernel owns admission identity, current state, attempts, ownership,
reauthorization seam, decision binding, cancellation intent, core limits,
history, and retention. An executor owns command serialization, actual work,
effect classification, executor-specific counters, and result normalization.
Executors are registered in code; a stored payload cannot name arbitrary Python
or SQL.

An operation has one immutable action/executor version. Deployments must retain
that version while nonterminal operations reference it or provide an explicit
migration/fail-closed policy. This is the durable equivalent of retaining a
registered task name across worker deployments.

The action declares one of these execution contracts:

| Effect class | Completion contract | Automated retry rule |
| --- | --- | --- |
| `postgres_atomic` | App mutation and operation completion share the same Aksara DB transaction | Safe after rollback/lease recovery; same operation only |
| `external_idempotent` | Provider accepts stable operation/effect key or supports authoritative reconciliation | Retry through adapter contract |
| `external_at_least_once` | Application explicitly accepts possible duplicates | Retry only under declared policy; surface duplicate risk |
| `external_nonretryable` | No safe dedupe/reconciliation | Ambiguous acknowledgement becomes `external_outcome_unknown`; manual/app recovery |
| `read_only` | No durable mutation contract | Retry under bounds, still reauthorize |

The command body is durably stored by the executor in the same admission
transaction. The shared operation stores only the action/version, opaque
command reference, and canonical input hash. This lets current task payloads
remain task-owned and permits stricter encrypted/redacted storage for generated
mutation arguments.

Before a mutating external call, its executor commits a small intent entry in
executor-owned durable state. The entry has an operation-scoped effect
identity/ordinal that remains stable across attempts, a canonical request hash,
provider reference, and deterministic downstream idempotency key where the
provider accepts one. It means the effect may have been attempted; it does not
claim that the provider received or completed it. This is part of the executor
adapter/context, not a generic public `ExternalEffect` subsystem.

## NON-BINDING schema sketch

The sketch tests responsibilities; it does not select public names or freeze
columns.

```text
operation
  id, app_namespace, tenant_id
  action_ref, action_version, executor_kind, command_ref, effect_class
  principal_ref_version, principal_ref, resolver_key, provenance_hash
  request_id, run_id, tool_call_id
  idempotency_scope_hash?, idempotency_key_hash?, input_hash
  state, state_version
  current_attempt_id?, fence_counter, attempt_count, max_attempts
  available_at, deadline_at
  cancel_requested_at?, cancel_requested_by?, cancel_reason?
  result_envelope?, error_envelope?
  created_at, updated_at, terminal_at?, retain_until

operation_attempt
  id, operation_id, ordinal, fence_token
  worker_id, state, lease_expires_at, heartbeat_at
  started_at, completed_at?
  retryable?, error_envelope?, usage_summary?

operation_approval_decision
  id, operation_id, input_hash, tenant_id, action_ref/version
  requester_ref_hash, approver_ref, state, decided_at?, expires_at
  consumed_at?, superseded_by?

operation_transition
  id, operation_id, attempt_id?, sequence
  from_state?, to_state, event, actor_ref?, occurred_at
  request/run/tool correlation, redacted_metadata

operation_export_outbox
  transition_id, sink_namespace, available_at, attempts, delivered_at?
```

A unique constraint covers the non-null idempotency scope hash. Another unique
constraint covers `(operation_id, ordinal)`, and fence tokens increase per
operation. Eligibility/retention/outbox indexes are narrow and batch-oriented.
The final schema may combine transition and outbox delivery metadata or use a
separate tombstone table after measurement.

# Detailed State Machine

## Operation states

`waiting_for_approval`, `ready`, `running`, `succeeded`, `failed`, `cancelled`,
and `expired` are sufficient.

There is no generic `pending`: admission can commit directly to waiting or
ready. There is no `retrying`: retry delay is `ready` plus `available_at`. There
is no `authorization_denied` state: denial is a stable error category on
`failed`. A temporary resolver outage is a failed attempt followed by `ready`;
a missing resolver or permanently unresolvable/revoked principal is terminal.
This keeps state useful for scheduling while structured errors explain why an
operation stopped.

Terminal states never reopen implicitly. An administrative retry, if eventually
supported, creates a new operation linked to the old one and receives a new
idempotency identity/authorization decision. It does not mutate history.

| Current | Event | Preconditions | Next | Atomic writes | If condition fails |
| --- | --- | --- | --- | --- | --- |
| none | admit | Registered versioned action; valid bounded command; unique scope | `ready` or `waiting_for_approval` | Command, operation, idempotency identity, transition | Read duplicate and compare input; otherwise reject |
| `waiting_for_approval` | approve | Authorized approver; exact binding; before expiry; not cancelled | `ready` | Decision, operation, transition/outbox | Losing/superseded decision rejected |
| `waiting_for_approval` | reject | Authorized approver; still pending | `cancelled` | Decision, operation, transition/outbox | Terminal result unchanged |
| `waiting_for_approval` | expire | DB time reaches approval/operation deadline | `expired` | Operation, transition/outbox | Concurrent approval/cancel winner remains |
| `waiting_for_approval` | cancel | Current caller authorized to cancel | `cancelled` | Cancel provenance, operation, transition/outbox | Terminal conflict |
| `ready` | claim | Due, deadline valid, attempts remain, no cancellation, required approval valid or consumed | `running` | First approval consumption, fence increment, attempt insert, current owner/lease, transition | Another worker continues/skip locked |
| `ready` | cancel | Current caller authorized | `cancelled` | Cancel provenance, terminal state, transition | Terminal conflict |
| `ready` | expire/exhaust | Deadline passed or attempts exhausted | `expired` or `failed` | Terminal error/transition | Claim condition fails |
| `running` | heartbeat | Current attempt/worker/fence; lease not expired | `running` | Lease and heartbeat time | Worker loses ownership and must stop |
| `running` | transient failure | Current fence; retry policy/deadline/attempts permit | `ready` | Attempt failed, error, available time, clear owner, transition | Stale worker cannot write |
| `running` | permanent failure/denial | Current fence | `failed` | Attempt failed, operation error, transition/outbox | Stale worker cannot write |
| `running` | lease reclaim | Lease expired under DB clock | `ready` then `running` for new claim | Old attempt abandoned, fence increment, new attempt/lease | Locked/current row decides one winner |
| `running` | cancel observed | Current fence; cancel won before effect commit | `cancelled` | Attempt cancelled, operation cancelled, transition/outbox | Success may already have won |
| `running` | succeed | Current auth/approval/fence/cancel/deadline checks; executor contract met | `succeeded` | Effect plus attempt/operation success and transition/outbox | Whole same-DB transaction rolls back |
| terminal | claim/retry/approve/cancel | None are valid | unchanged | Optional access audit only | Stable terminal conflict/not found response |

## Attempt states

| Current | Event | Next | Retry consequence |
| --- | --- | --- | --- |
| none | successful claim | `running` | Counts as one physical attempt |
| `running` | effect and completion commit | `succeeded` | Operation terminal |
| `running` | classified transient/permanent failure | `failed` | New attempt only if operation returned to ready |
| `running` | lease reclaimed | `abandoned` | New claimant creates next attempt and fence |
| `running` | cancellation wins | `cancelled` | Operation terminal unless external outcome is unknown |
| any terminal | any execution write | unchanged | Invalid; never reuse an attempt row |

An attempt count increments only when an operation claim succeeds. A task claim
that never reaches the operation claim is not an operation attempt. A retry
after a policy/resolver transient failure is a new attempt because physical
execution and authorization evaluation occurred. Heartbeats are not attempts.

## Required scenario

1. The initial request with key K creates Operation O.
2. Worker A claims Attempt O/1 with fence N.
3. A dies; O remains running until the lease expires.
4. Recovery marks O/1 abandoned. Worker B atomically claims O/2 with N+1.
5. B reauthorizes and commits the application mutation, O/2 success, and O
   success in one transaction.
6. B's response/ack is lost.
7. The client resubmits key K and the same input. Admission uniqueness returns O
   and its successful result.

Exactly one operation and two attempts exist. PostgreSQL O is authoritative. A
cannot later heartbeat, mutate through the framework boundary, or finalize
because N fails the current N+1 condition.

# Transaction Boundary Analysis

## Framework-owned PostgreSQL mutation boundary

The executor resolves the current principal first, then opens the Aksara
operation transaction on one pinned connection. Inside it:

1. select/lock O and current attempt;
2. require running state, matching attempt/worker/fence, and unexpired lease;
3. require no cancellation request and a valid operation deadline;
4. verify the durable approval binding when required;
5. re-run permission, `PolicyEngine`, tenant, object, field, ORM, and RLS checks;
6. execute the application mutation;
7. conditionally update the attempt and operation to succeeded;
8. append the redacted transition/outbox record;
9. commit once.

If finalization affects zero rows or any check raises, the entire transaction
rolls back. The implementation must not catch that exception inside a nested
savepoint and then commit outer application work.

Authorization should be as close to the effect as possible. Database-backed
membership/object checks should execute in this transaction. External identity
resolution may precede it; the guarantee is current at the evaluation boundary,
not a promise that an external administrator cannot revoke a role one
microsecond later. Applications that need revocation serialized with mutation
must store/lock their authority state in the same database transaction.

## Crash matrix for the atomic executor

| Boundary | Durable database outcome | What a new worker/client does |
| --- | --- | --- |
| Crash before operation claim | O stays ready; no attempt/effect | Another worker claims O |
| Crash after claim, before mutation transaction | O running; attempt lease eventually expires; no effect | Mark attempt abandoned; reauthorize in new attempt |
| Crash after transaction begins, before mutation | Transaction aborts | Same as above |
| Crash during mutation statement | Transaction aborts or database completes statement but not transaction | No visible committed effect; reclaim after lease |
| Crash after mutation statement, before operation update | Whole transaction aborts | No effect or success; reclaim |
| Crash after operation update, before commit | Whole transaction aborts | No effect or success; reclaim |
| Server commits, client/worker misses acknowledgement | Effect and success both visible | Query O; do not execute again |
| Lease expires before executor locks O | Ownership check fails | Current/new owner proceeds |
| Lease deadline passes while executor holds O lock | Reclaimer cannot supersede locked row; either success commits first or rollback permits reclaim | Observe committed state after lock release |
| Connection drops before commit reaches server | No commit | Lease recovery and retry |
| Connection drops after commit reaches server | Commit outcome uncertain locally, but DB has both effect and success | Re-read O by ID/key before retry |

Database disconnection does not justify immediately repeating an effect. The
recovery loop waits for database authority, reads O, and follows its state. For
same-database work, the atomic invariant means there is no durable state in
which the effect committed while O did not succeed.

For an external mutation, the analogous pre-call boundary is a separate short
database transaction: verify current attempt/fence, authorization, approval,
cancellation, and deadline; then commit executor-owned effect intent before the
network call. No database write can prove whether the subsequent network effect
occurred. The intent only makes the ambiguity visible and gives recovery the
same stable effect identity and provider key.

## Weaker modes

* A mutation in another PostgreSQL database cannot share this transaction. It
  is an external effect even if both use PostgreSQL.
* An application callable that opens a separate connection or commits directly
  cannot receive the `postgres_atomic` guarantee. Registration must reject that
  classification or tests must prove operation-context participation.
* Network services, email, payments, webhooks, filesystems, and model providers
  cannot be atomically coupled to operation success.
* If a provider supports idempotency, its adapter retries an uncertain call with
  the same recorded effect key. If it supports authoritative status lookup, the
  adapter reconciles before retry. If it supports neither, the operation records
  `external_outcome_unknown` and stops automatic retry.

# Idempotency Analysis

## Admission identity

The caller supplies a bounded opaque idempotency key. Aksara hashes it at rest
and derives a uniqueness scope from:

```text
application namespace
+ tenant (explicit null/system scope included)
+ stable initiating-principal reference
+ registered action and semantic version
+ caller key
```

Scoping by stable principal reference prevents one tenant user from colliding
with another. Including action/version prevents key reuse from silently calling
a different operation after deployment. Tenant remains explicit even when the
principal reference contains it so lookup/index policy cannot omit isolation.

The canonical input hash covers normalized semantic path parameters and body/
arguments after schema validation. Object key ordering, UUID/date encodings,
and model aliases have one versioned canonical form. It excludes bearer/session
credentials, approval tokens, request/run IDs, progress tokens, and headers
without business meaning. Canonicalization version is part of the action
version or stored explicitly.

## Outcomes

| Situation | Result |
| --- | --- |
| First valid submission | Create command + O atomically; return O |
| Same scope/key/hash, O waiting/ready/running | Return O with nonterminal status; create no attempt from admission |
| Same scope/key/hash, O terminal | Return the retained terminal result/error |
| Same scope/key, changed input/action version | `idempotency_conflict` / HTTP 409; disclose no other tenant data |
| Concurrent identical submissions | Unique constraint admits one; loser reads/compares and returns same O |
| Concurrent changed submissions | One admits; the other receives conflict |
| Client has no key | A new O is allowed; lost initial response cannot be correlated safely |
| Retention elapsed but tombstone remains | Same comparison/conflict semantics; result may be gone according to contract |
| Tombstone pruned after promised window | Key reuse may create a new O; documentation must state this |

Aksara-generated operation IDs are always unique and can serve as idempotency
context for downstream calls. They do not replace a caller key for the first
response-loss problem.

## Effects

For a `postgres_atomic` action, admission identity plus one-transaction
completion makes client retry deterministic. Multiple physical attempts may
start, but only the current fence can commit, and a retained succeeded O is
returned rather than executing again.

For an external adapter, derive a stable per-effect key such as a keyed hash of
operation ID, action version, and effect name/ordinal. Pass it through an
`OperationExecutionContext`; never assume a provider honors it. Before sending
the request, commit executor-owned intent containing that stable effect
identity/ordinal, request hash, provider reference, and key while the current
attempt/fence is valid. The same effect identity is reused after worker restart.

Recovery follows the provider contract: retry with the same key if the provider
deduplicates, reconcile first if it offers authoritative status lookup, and
record `external_outcome_unknown` without automatic retry if it offers neither.
The pre-effect record is deliberately conservative: a crash after recording
intent but before the network send is indistinguishable from a crash after the
provider performed the effect unless the provider can deduplicate or reconcile.
If the existing internal state machine represents that terminal outcome as
`failed`, it means Aksara cannot safely establish completion; it does not claim
the provider failed or the effect did not occur. A generic distributed-effect
engine is not required.

# Lease and Fencing Analysis

The existing task stale-lock reset is insufficient because it decides only
that time passed. It does not identify the old owner and later completion uses
only the task ID.

## Claim and renewal

* Candidate selection uses a narrow eligible index and `FOR UPDATE SKIP LOCKED`.
* PostgreSQL `CURRENT_TIMESTAMP` is the clock authority for claim, renewal, and
  expiry comparisons.
* Claim locks O, verifies ready/due/not cancelled/not expired/attempts remain,
  increments `fence_counter`, creates a running Attempt, and stores current
  attempt/worker/lease on O in one transaction.
* Worker ID is diagnostic. Possession of the attempt ID and matching fence is
  necessary; worker ID alone grants nothing.
* Heartbeat renewal is a conditional update for the current running attempt and
  unexpired lease. A delayed heartbeat after expiry cannot resurrect ownership.
* Executors stop immediately when renewal affects zero rows. External calls
  already in flight may finish, so their outcome contract still matters.

## N/N+1 race

Worker A holds O/attempt A/token N. Its lease expires. Worker B locks O, marks A
abandoned, increments the fence, and creates attempt B/token N+1. When A wakes:

* its heartbeat `WHERE current_attempt=A AND fence=N` updates zero rows;
* a progress/counter write with the same condition updates zero rows;
* before a database effect, locking O shows B/N+1 and A aborts;
* if A somehow reached finalization in an already-open transaction, the
  conditional success update fails and raises, rolling back A's application
  mutation;
* A cannot change B or O through the operation API.

The subtle race is lease expiry during a database transaction. The transaction
must lock O before the mutation. A reclaimer either acquired the lock first and
fenced A, or waits until A commits/rolls back. It cannot create N+1 concurrently
with A holding the row lock. Long operations outside this short transaction
must heartbeat and then revalidate before each effect; they must not keep a
database transaction open while waiting on a provider.

Lease duration and heartbeat cadence are internal/configurable. The safety rule
is invariant: heartbeat comfortably precedes expiry, database time decides,
and every authoritative write includes the current fence condition. A
concurrency limit should cap claim batches and active work; lease length is not
a throughput control.

# Principal/Reauthorization Analysis

## Durable provenance

The minimum safe reference is a versioned mapping with:

* identity namespace/resolver key;
* principal kind/auth method;
* stable subject or user ID;
* optional agent ID and human/service owner ID;
* tenant ID at admission;
* optional non-secret credential/token identifier for revocation lookup;
* immutable request/run/tool-call correlation;
* hash/version for integrity and interpretation.

The operation also stores the registered action/version and requested policy
context: resource type/object locator, tenant requirement, required scopes,
and fields implied by the canonical command. These are requirements to check,
not grants that were once held.

Admission-time roles/scopes/audience/expiry may be exported as redacted audit
provenance, but execution must never construct a `Principal` by replaying those
values. No bearer token, API key, cookie, refresh token, or signed approval
token is stored.

## Resolver contract

The application/framework registers a resolver by stable key:

```text
resolve(principal_reference, operation_context) -> current Principal | outcome
```

The resolver validates that the stable subject still exists, still maps to the
same tenant/agent/owner relationship, and returns current roles/scopes/audience
and policy metadata. A system operation uses a separately registered trusted
system resolver and explicit tenant/reason; arbitrary persisted input can never
request `Principal.system()`.

The resolved `Principal` then flows through the same permission classes,
`PolicyEngine`, tenant filters, object checks, writable fields, ORM validation,
and RLS as current REST/MCP execution.

| Change/failure | Required result |
| --- | --- |
| Principal deleted/disabled | Terminal `authorization_required` or `authorization_denied`; no effect |
| Original bearer credential expired | Do not replay it; stable resolver resolves current identity or fails closed |
| Roles/scopes removed | Current policy denies; terminal authorization failure |
| Tenant membership removed/changed | Fail closed; no operation tenant rewrite |
| Permission/policy code changes | New policy applies at next effect boundary |
| Object ownership/access changes | Re-fetch/check current object in mutation transaction; deny if changed |
| Field restrictions change | Revalidate stored canonical payload against current field policy; deny changed fields |
| Resolver temporarily unavailable | Failed retryable attempt; ready with bounded backoff |
| Resolver key missing after deployment | Terminal configuration/integrity failure; operator remediation/new operation |
| Provenance malformed/tampered | Terminal integrity failure and security audit event |

Approval cannot override any row in this table. A current approver may approve
an operation whose requester later loses permission; execution still fails.

# Approval Analysis

The existing v0.6 HMAC grant remains the synchronous MCP mechanism. Its exact
principal/tool/arguments/tenant/expiry binding is useful and compatible, but a
server cannot query whether approval is pending, rejected, superseded, or used.

A durable operation that declares approval uses a separate
`OperationApprovalDecision`. Keeping it separate from O preserves multiple
facts (pending request, reject, supersession) without turning the operation row
into an approval workflow.

Decision rules:

* The decision is bound to O, canonical input hash, action/version, tenant, and
  requester reference.
* The approver is resolved and authorized at decision time; only stable
  approver provenance is stored.
* State is pending, approved, rejected, expired, or superseded.
* One current decision can satisfy an operation. Conditional updates/unique
  constraints decide concurrent approve/reject races.
* Rejection terminally cancels the waiting operation with an approval-rejected
  reason. Expiry before executable work moves it to expired.
* Changed input never reuses approval; it conflicts under idempotency or creates
  a new operation.
* Approved is single-use per logical operation. It cannot authorize another
  operation or tenant.
* Approval moves O from waiting to ready. The first claim verifies that the
  decision is still valid and atomically records consumption as O enters
  `running`. A later physical retry of the same O does not need a new human
  decision merely because the worker crashed, but it must still reauthorize the
  requester.
* Approval expiry controls the first claim. Operation deadline and current
  authorization bound subsequent recovery.
* Superseded and consumed decisions remain in bounded history and cannot become
  active again.

The framework owns decision integrity and state. The application owns how a
human sees a request, notifications, queues/inboxes, escalation, SLAs, delegation,
and quorum rules. An application can implement a quorum and submit one final
framework decision; the core does not become a business process engine.

# Cancellation/Budget Analysis

## Cancellation

`cancel_requested_at`, requester provenance, and a bounded reason are durable.
A cancellation API first authorizes the current caller against O and tenant.

| Timing | Semantics |
| --- | --- |
| Waiting for approval | Atomically terminal-cancel; later decisions cannot revive it |
| Ready/queued/retry delay | Atomically terminal-cancel before any new claim |
| Running before effect boundary | Persist request; worker observes on heartbeat/boundary and terminal-cancels |
| Racing same-DB success | O row lock orders events: cancellation first blocks/rolls back success; success first remains succeeded |
| External call already issued | Best effort; adapter may cancel provider call, but outcome may succeed or be unknown |
| After success/failure/expiry/cancel | Reject as terminal conflict/no-op according to public contract; never rewrite history |
| Active local coroutine | Signal/cancel as optimization after durable request commits |

Workers check cancellation on claim, heartbeat, before each framework side
effect while holding O's row lock, and between external effects. User code that
bypasses these boundaries receives no stronger guarantee.

## Budgets and counters

| Counter/limit | Class | Storage behavior |
| --- | --- | --- |
| Attempt count/max attempts | CORE | O + immutable attempt rows; survives all workers |
| Overall deadline | CORE | O; DB time enforced at claim/effect |
| Retry count | CORE-derived | Count failed/abandoned attempts; no duplicate column required |
| Next retry time/backoff | CORE | O eligibility field; error classifier chooses delay |
| Per-attempt execution timeout | OPTIONAL/executor-specific | Attempt/executor config; timeout becomes structured failure |
| Tool-call count | AI-SPECIFIC | Namespaced executor durable state, atomically incremented |
| Planner step count | AI-SPECIFIC | Planner executor state; outside core and deferred |
| Provider call count | AI-SPECIFIC | Adapter state; stable effect ordinal supports idempotency |
| Token/cost usage | AI-SPECIFIC | Aggregate across attempts from confirmed usage; unknown usage marked, not guessed |
| Business quota/SLA | APPLICATION-SPECIFIC | Application policy/store |

Core state must never reset on retry. Executor counters use conditional fence
writes or commit with effect/result transitions. An uncertain provider response
may make token/cost usage unknown; the framework should represent that rather
than invent a number.

# Audit/History Analysis

## Authority

* O is authoritative current logical state.
* Attempt rows are authoritative physical claim/outcome records.
* Approval decisions are authoritative durable human/application decisions.
* Transition rows are bounded evidence written with each state change.
* Task status, MCP audit, logs, notifications, and external sinks are projections
  or exports.

State is not rebuilt from transition rows. A failed export never rolls back a
valid operation commit. Each transition transaction inserts an outbox marker;
an exporter retries delivery and records sink-specific progress.

Transition data includes sequence, event/from/to state, operation/attempt IDs,
correlation, stable actor reference/hash, timestamp, error category, and safe
metadata. It excludes command values, credentials, approval tokens, and
unbounded stack traces. Argument/result summaries use type, size, and hash where
the current MCP audit already establishes that pattern.

## Retention and visibility

* Active/waiting/running operation state cannot be pruned.
* Terminal result bodies may have a shorter TTL than the operation/idempotency
  tombstone. A later status can say result expired while preserving terminal
  truth.
* Attempts/decisions/transitions have bounded framework retention sufficient for
  retry diagnosis and the documented v0.7 contract.
* Application audit sinks own longer compliance retention and legal holds.
* Pruning uses database time and bounded batches and never shortens the promised
  idempotency window.
* Every lookup/list/export applies current authorization and tenant filtering.
  Knowing an opaque ID is not permission.
* Unauthorized and nonexistent IDs should be indistinguishable where practical
  to reduce enumeration.

# Task Integration

The selected relationship is: **tasks remain separate and can optionally
reference an operation; an operation references an executor binding and can be
synchronous or task-backed.**

This gives precise answers:

* Existing task IDs keep their meaning and remain queryable through current
  APIs/CLI.
* Old task enqueue, queues, schedules, result/error fields, and task-only workers
  stay compatible.
* Tasks can exist without operations.
* Durable operations need a registered executor, not necessarily a task.
* A linked task claim may lead to an operation attempt. They are not inherently
  the same count because a task can be claimed before operation eligibility,
  authorization, or cancellation is resolved.
* Operation attempts are authoritative. The task aggregate `attempts` field is
  a compatibility/scheduling projection for linked work.
* Linked task stale recovery delegates to the operation lease. It must not reset
  a running task independently or create a competing lease.
* The task table stays internal. It is not exposed as the operation public API.

A safe incremental adapter flow is:

1. Admission creates O and executor command. If task-backed, create the task and
   immutable operation link in the same transaction.
2. Task worker claims the scheduling row using current queue mechanics.
3. Adapter claims O, creating Attempt and fence. If O is cancelled/terminal/not
   due, project that state back to the task and do not call user code.
4. The operation executor runs under current provenance/auth/fence semantics.
5. Terminal/retry state projects to the linked task for legacy inspection.
6. Recovery consults O first. The operation lease, not `locked_at`, decides
   whether an active linked execution is stale.

During transition, unlinked rows retain v0.6 semantics. No background task
silently acquires current-principal guarantees it cannot meet.

`DurableStep` remains untouched and functional-but-evolving. It may later gain
an explicit operation-backed adapter, but automatic migration would break
`force=True`, cached-result, runtime-DDL, and sequential concurrency semantics.
It must not be described as satisfying v0.7 worker recovery.

# MCP Integration

Aksara v0.6.1 uses official Python SDK `mcp>=2.0.0,<2.1.0`, with release
validation on 2.0.1. Synchronous Streamable HTTP `/mcp/` is stable. That path
must not change behavior for current generated tools.

The current official protocol moved Tasks out of the 2025-11-25 experimental
core into the 2026-07-28
[`io.modelcontextprotocol/tasks`](https://tasks.extensions.modelcontextprotocol.io/specification/draft/tasks)
extension. The new extension is server-directed, returns a task handle instead
of `CallToolResult`, and uses `tasks/get`, `tasks/update`, and `tasks/cancel`;
it removed the enumeration-oriented `tasks/list` model. The specification
requires durable creation before returning the handle and capability
negotiation per request.

The [official Python SDK roadmap](https://github.com/modelcontextprotocol/python-sdk/blob/main/ROADMAP.md)
says the extension is not yet implemented in 2.0 because the new wire form is
incompatible with the earlier task API. Aksara should therefore:

1. preserve existing `tools/call` and its synchronous result;
2. make durable behavior an application-level opt-in on a separately registered
   durable action/tool, never infer it from a slow call;
3. wait for official Python SDK support rather than manually implementing a
   drifting extension or enabling old experimental Tasks;
4. map the protocol task ID to O ID when supported;
5. project `waiting_for_approval` to `input_required` only when the protocol
   interaction is actually represented as a supported input request; otherwise
   keep approval on the Aksara/application API and report `working`;
6. project ready/running to `working`, but translate a terminal operation using
   the underlying `tools/call` wire outcome rather than the Aksara state label;
7. use `tasks/cancel` as cancellation intent under the extension's cooperative
   semantics;
8. authorize every get/update/cancel by current principal and tenant, even
   though the task/O ID is high entropy;
9. cap protocol TTL by framework retention/resource limits; and
10. pass conformance and multi-client isolation tests before stability.

The terminal translation is:

| Underlying `tools/call` outcome | MCP Task projection |
| --- | --- |
| Successful `CallToolResult` with `isError` false or absent | `completed` with that result |
| `CallToolResult` with `isError: true` | `completed` with the tool-level error result |
| JSON-RPC/protocol execution error | `failed` with the JSON-RPC error |
| Aksara operation reaches terminal cancellation | `cancelled` |

The extension defines `completed` to include tool calls whose result has
`isError: true`; `failed` is reserved for a JSON-RPC error during execution and
must not represent a non-JSON-RPC tool error. Consequently,
`Operation.failed` is not sufficient by itself to select MCP `failed`. An
application-level terminal failure that Aksara's synchronous MCP path expresses
as `CallToolResult(isError=true)` becomes a completed Task carrying that same
error result. Only a protocol/execution JSON-RPC error becomes a failed Task.
Likewise, acknowledging `tasks/cancel` is only cooperative cancellation intent;
the Task projects `cancelled` when cancellation actually wins and O reaches its
terminal cancelled state. This is an MCP adapter translation boundary and does
not change Aksara's Operation states.

An ordinary generated “dispatch” tool returning a custom operation envelope may
be used only as a short-lived experimental bridge if users need early access.
It must not become a competing stable MCP workflow protocol.

# API Boundary

The smallest public semantic surface is:

* dispatch a registered durable action with optional/required idempotency key;
* retrieve O status and retained result/error;
* request cancellation.

Listing and attempt inspection are operationally useful but are not required
for the first stable client contract. If supplied, list uses opaque cursor
pagination and current tenant/policy filtering; attempt detail is privileged.

Existing generated REST stays synchronous. A separate opt-in durable endpoint
or explicit registered action avoids changing response types:

| Request outcome | Suggested HTTP result |
| --- | --- |
| New O committed, nonterminal | `202 Accepted`, opaque O ID and `Location` |
| Same key/hash, existing nonterminal | `202 Accepted`, same O and `Location` |
| Same key/hash, existing terminal | `200 OK`, same O/result/error representation |
| Same key, changed canonical input | `409 Conflict` with stable code |
| Status authorized/found | `200 OK` |
| Status result body pruned | `200 OK` terminal status plus result-expired marker |
| Cancel accepted for nonterminal O | `202 Accepted` or `200 OK` durable request/state |
| Cancel after terminal state | `409 Conflict` with current terminal status |
| Unauthorized/not visible | Non-enumerating `404` or policy-standard denial |

The exact route names and Python symbols require API design review and are not
fixed here. Public fields should be operation ID, semantic state, timestamps,
result/error, retry/poll hint, cancellation state, and retention information.
Internal table names, fence/lease/worker details, command/provenance bodies, and
transition storage are not public.

# PostgreSQL Suitability

PostgreSQL already supplies every primitive the selected guarantee needs:

* unique constraints for concurrent idempotent admission;
* row locks and `FOR UPDATE SKIP LOCKED` for scalable claims;
* conditional updates for heartbeat/fencing;
* database time for lease/deadline ordering;
* transactions/savepoints on Aksara's pinned session connection;
* JSONB for bounded/versioned envelopes where relational columns are not needed;
* partial/covering indexes for eligible work and outbox delivery;
* internal migrations and advisory-lock serialization for safe schema upgrade;
* restricted roles and RLS for tenant defense-in-depth.

Expected v0.7 scale is not defined as a global workflow platform. A single
operation table with a partial ready index, append-only attempts/transitions,
and batch cleanup is a reasonable starting point. Avoid hot aggregate rows
beyond the one O row that intentionally serializes ownership. Heartbeats update
only active rows. History/outbox indexes should not include large envelopes.

Before stability, benchmark claim throughput, heartbeat contention, terminal
write latency, and pruning against the task baseline on supported PostgreSQL 16
and a current local version. Partitioning, an external queue, or sharding is
justified only by measured failure to meet targets. Redis, Kafka, Celery, and
Temporal are not required by current evidence.

# Failure Matrix

For `Mutation may have committed?`, “No (atomic)” assumes a correctly registered
`postgres_atomic` executor using the same Aksara database. External outcomes are
called out separately.

| Scenario | Expected operation state | Attempt state | Can retry? | Authorization rerun? | Mutation may have committed? | Recovery action |
| --- | --- | --- | --- | --- | --- | --- |
| Process killed before admission commit | No operation | None | Client may resubmit | Yes on future attempt | No | Same client key creates/finds O |
| Admission commits; response lost before client sees O ID | Ready/waiting | None | Yes with client key | Yes | No | Same key/hash returns O; without key correlation is impossible |
| Process killed after admission, before claim | Ready/waiting | None | Yes | Yes | No | Another worker claims when eligible |
| Two workers race to claim | Running under one owner | One running | Loser does not retry independently | Winner reruns auth | No yet | Row lock/`SKIP LOCKED` selects winner |
| Worker killed immediately after claim | Running until lease recovery | Running then abandoned | Yes after lease | Yes | No | Reclaim with higher fence |
| Killed before DB mutation | Running until lease recovery | Running then abandoned | Yes | Yes | No | Reclaim with higher fence |
| Killed during DB mutation | Running until lease recovery | Running then abandoned | Yes | Yes | No (atomic) | PostgreSQL rollback; reclaim |
| Killed after mutation statement, before success update | Running until lease recovery | Running then abandoned | Yes | Yes | No (atomic) | Whole transaction rollback; reclaim |
| Killed after success update, before commit | Running until lease recovery | Running then abandoned | Yes | Yes | No (atomic) | Whole transaction rollback; reclaim |
| Commit succeeds; response/ack lost | Succeeded | Succeeded | No new execution; query/resubmit allowed | Status access auth only | Yes, and success proves it | Return retained O/result |
| DB connection drops before commit | Running until lease recovery | Running then abandoned | Yes | Yes | No | Wait for DB, read O, reclaim |
| DB connection drops with commit outcome uncertain | Succeeded or running, atomically with effect | Succeeded or later abandoned | Only if DB says nonterminal after recovery | Yes for new attempt | Deterministically same as O once DB reachable | Never immediately repeat; read authority |
| Lease expires without active worker | Running until recovery transaction | Abandoned | Yes | Yes | No known DB effect unless O succeeded | Claim N+1 |
| Worker A/N wakes after B/N+1 claim | State owned by B | A abandoned; B running/terminal | A cannot retry/finalize | B already reauthorized | A's same-DB transaction cannot commit | Conditional fence fails; A stops/rolls back |
| Heartbeat is delayed past lease | Running under newer owner or ready | Old abandoned | New attempt only | Yes | Old controlled effect blocked | Zero-row heartbeat signals loss |
| Duplicate submission, same key/input | Existing state | Unchanged | No new attempt from submit | Status access auth only | Whatever existing O proves | Return existing O |
| Duplicate submission concurrent, same key/input | One O | Unchanged/one claimant later | Normal execution only | Yes at execution | No at admission | Unique constraint loser reads winner |
| Same idempotency key, different input | Existing state unchanged | Unchanged | Only with a new key | No execution | No new mutation | Return conflict |
| Idempotency window expired and tombstone pruned | New O permitted | New attempts possible | Yes, documented as new work | Yes | Prior effect may exist | Caller must use a fresh semantic key/accept retention contract |
| Database unavailable during admission | No new committed O | None | Yes | Later | No | Return transient failure; client retries same key |
| Database unavailable during claim/heartbeat | Existing O unchanged; lease may expire | Running may become abandoned later | Yes after authority recovers | Yes | Controlled DB effect not newly committed | Stop worker; do not assume ownership |
| Cancellation before execution | Cancelled | None | No | Cancellation request authorized | No | Return cancelled; claims reject |
| Cancellation during retry delay | Cancelled | Prior failed/abandoned | No | Cancellation request authorized | Prior attempts follow their recorded truth | Remove eligibility atomically |
| Cancellation while running before DB boundary | Cancel requested then cancelled | Cancelled | No | Request and worker checks authorized | No | Worker observes and terminal-cancels |
| Cancellation races same-DB completion | Cancelled or succeeded by row-lock order | Cancelled or succeeded | No | Execution auth already rerun | Only if succeeded | Return actual terminal winner |
| Cancellation after external call issued | Running then succeeded/failed/cancelled per reconciliation | Matching terminal/unknown | Provider-specific | Yes before any next effect | Yes/unknown | Attempt provider cancel; reconcile; never claim undo |
| Cancellation after success | Succeeded | Succeeded | No | Cancellation caller auth checked | Yes | Return terminal conflict; do not rewrite |
| Approval pending | Waiting for approval | None | Not executable | Approver auth at decision; requester later | No | Poll/wait or cancel/expire |
| Approval rejected | Cancelled with approval-rejected reason | None | No | Approver checked; no executor auth needed | No | Return terminal decision |
| Approval expires before first effect | Expired | None or failed pre-effect attempt | No implicit retry | Yes if new O created | No | New operation/decision required |
| Approval replayed for another O/input/tenant | Target unchanged/denied | None | No with replay | Normal auth still applies | No | Binding mismatch security event |
| Approved O worker crashes and retries | Ready/running/succeeded | Old abandoned; new attempt | Yes within O limits | Yes | Atomic rule applies | Bound approval remains O-only; reauthorize requester |
| Principal revoked while queued | Failed `authorization_denied` | Failed | No automatic retry | Yes, causes denial | No | Surface terminal failure; new authorized request needed |
| Original credential expires while queued | Depends on stable resolver | Failed or running | Only resolver-outage class | Yes | No before authorization | Resolve stable identity; never replay credential |
| Tenant membership removed | Failed `authorization_denied` | Failed | No | Yes | No | Fail closed |
| Policy/permission changes | Allowed or failed under new rule | Succeeded/failed | Per result | Yes | Only if current rule allows | Current code/policy is authoritative |
| Object access changes after admission | Failed or succeeds under current object check | Failed/succeeded | Usually terminal on denial | Yes inside boundary | Only if allowed | Re-fetch/check under transaction |
| Field restrictions tighten | Failed `authorization_denied` | Failed | No | Yes | No | Revalidate stored command; do not strip silently |
| Identity resolver temporarily unavailable | Ready after backoff | Failed retryable | Yes within bounds | Yes each attempt | No | Retry with bounded backoff/deadline |
| Identity resolver missing/malformed provenance | Failed integrity/configuration | Failed | No automatic retry | Cannot safely resolve | No | Operator fixes deployment; submit new O |
| External intent committed; worker dies before network send | Running until lease recovery, then provider-dependent | Running then abandoned/failed | Same-key retry if provider deduplicates; reconcile if possible; otherwise no | Yes before any retry | No provider effect or unknown | Reuse recorded effect identity; never create a new ordinal |
| External provider timeout, idempotency supported | Ready or succeeded after reconciliation | Failed/retried/succeeded | Yes through adapter contract | Yes before retry | Provider may have committed; dedupe/reconcile governs | Query provider then retry stable effect key |
| External provider timeout, no dedupe | Failed `external_outcome_unknown` | Failed | No automatic retry | N/A until explicit recovery | Yes/unknown | Application/manual reconciliation |
| External effect succeeds; worker dies before local result recording | Running until recovery, then succeeded/retryable/unknown by provider contract | Running then abandoned/reconciled/failed | Same-key retry only with provider idempotency; otherwise reconcile or stop | Yes before any retry | Yes | Consult pre-effect intent; reuse its effect identity/key; otherwise `external_outcome_unknown` |
| Audit sink unavailable | Operation follows actual state | Attempt unchanged | Export retries independently | No execution change | Per operation | Outbox remains pending; sink is not authority |
| Application restart | Committed state unchanged | Running leases may expire | Yes by state/lease | Yes | Per committed O | New process resumes polling/claims |
| Worker graceful restart | State unchanged; in-flight may finish before stop | Normal terminal or later abandoned | As needed | Yes on new attempt | Per terminal state | Drain; lease recovery is fallback |
| Worker hard restart | Running until lease recovery | Abandoned then new | Yes | Yes | Atomic DB rule applies | Higher fence claims |
| Executor action version missing after deploy | Failed configuration or remains blocked by rollout policy | Failed | No automatic retry | No safe execution | No new effect | Keep versions deployed or explicit operator migration |
| Malicious/tampered command payload | Failed validation/integrity | Failed | No | Authorization would not legitimize tamper | No | Hash/schema/registry validation and security event |
| Result retention elapsed | Terminal state remains; result marked expired | Terminal | No execution retry | Status read authorized | Per terminal state | Return status without body; app audit may retain longer |

No unresolved same-database mutation state remains if the executor transaction
and fence invariants are upheld. Proving those invariants is the first mandatory
experiment. External outcome ambiguity is deliberately explicit.

# Threat Model

| Threat | Architectural control |
| --- | --- |
| Stale admission authorization | Persist reference, not grant; resolve current Principal and rerun full authorization at each effect |
| Replay of a completed mutation | Scoped unique idempotency identity returns retained O; no new attempt on resubmit |
| Same key with altered arguments | Versioned canonical input hash; conflict before execution |
| Key collision/guessing | Bounded high-entropy recommended keys, keyed/cryptographic hash, tenant/principal/action scope; compare full canonical hash |
| Cross-tenant operation lookup | Current principal authorization and tenant/RLS filtering on every read/cancel/list/export; opaque ID is defense only |
| Operation enumeration | High-entropy IDs, no mandatory list API, rate limits, indistinguishable unauthorized/not-found responses |
| Tampered provenance | Immutable versioned internal record, integrity hash, restricted DB roles, no public write path, fail-closed resolver |
| Stored credential leakage | Never persist reusable credentials; redact commands/results/history; separate retention/encryption where required |
| Late worker database commit | Monotonic fence and current-attempt check inside same transaction as mutation/finalization |
| Forged worker ownership | Worker ID alone insufficient; attempt ID + current fence + DB state required; conditional writes only |
| Approval reuse for another operation | Bind decision to O/input/action/tenant/requester; unique current decision and terminal supersession |
| Approval argument mutation | Input hash binding and immutable command; changed input conflicts |
| Approval after permission revocation | Fresh requester authorization is mandatory; approval cannot grant permission |
| Unauthorized approver | Resolve/current-authorize approver at decision transaction; record stable provenance |
| Privilege escalation on resume | Resolver cannot be selected by payload; stable registered key; same tenant/subject relation validated; no automatic system fallback |
| Malicious executor reference | Code allowlist of versioned registered actions; stored data cannot import code or inject SQL |
| Malicious executor payload | Size/schema/canonicalization validation on admission and revalidation before effect; no credential/approval material |
| Cancellation bypass | Claim and effect transaction both check durable cancel flag; transition ordered by row lock/fence |
| Result/error data leakage | Bounded/redacted envelopes, separate TTL, tenant/current access policy, privileged attempt detail |
| Transition tampering | State transitions are conditional internal functions, same transaction as current state, restricted DB permissions |
| Audit suppression | Transactional outbox marker; sink failure retried; operation state remains authoritative |
| External effect occurs before local result recording | Commit executor-owned intent first; reuse its stable operation/effect identity and provider key to deduplicate or reconcile, otherwise stop as `external_outcome_unknown` |
| Lease starvation/DoS | Per-principal/tenant concurrency and retention bounds, capped TTL, indexed bounded claims, polling rate limits |
| Heartbeat takeover via clock skew | PostgreSQL time is sole lease clock; attempt/fence condition required |
| RLS bypass by system work | System resolver is separately registered; explicit tenant/reason; restricted operational role and cross-tenant audit |
| Stale action code interprets old command differently | Persist action/canonicalization version; keep resolver/executor version or fail closed |

# Compatibility Analysis

| v0.6 surface | v0.7 compatibility decision |
| --- | --- |
| Generated synchronous REST | Unchanged by default; durable endpoint/action opt-in |
| MCP Streamable HTTP `/mcp/` | Synchronous `tools/call` remains default and stable |
| Generated MCP tool names/results | No silent conversion to task handles; durable tools/actions explicit |
| Signed approval grant | Retained for synchronous calls; separate durable decision only for durable operations |
| `Principal` | Remains live policy object; durable reference is a locator, not replacement |
| Permission/PolicyEngine/tenant/field/RLS | Reused at delayed effect boundaries |
| MCP audit event | Existing required fields remain; operation/attempt IDs can be optional additions |
| Task IDs/API/CLI/queues/schedules | Preserved; optional linked operations project compatible state |
| Unlinked task retry/stale recovery | Preserved until an application opts into operation-backed execution |
| `DurableStep` | Remains available and evolving; no automatic semantic change |
| Framework migrations | New tables later use ordered internal migrations; no runtime DDL requirement |
| Applications without durable operations | No new runtime service or adoption requirement |

The additive strategy permits an internal experimental operation kernel before
any stable REST/MCP surface. Migration rollout must create nullable links and
new tables without rewriting existing task rows. Downgrade/rollback policy must
leave old task and synchronous surfaces usable even if new operation tables are
ignored.

# Risks

| Risk | Impact | Mitigation/acceptance gate |
| --- | --- | --- |
| Executor bypasses pinned transaction | Mutation and success can disagree | Registration contract plus integration test that different-connection writes are rejected/not labeled atomic |
| Fence checked only at finalization | Stale worker might issue effect before discovering loss | Lock/check immediately before effect and finalize in same transaction |
| Long transaction used as lease | Lock contention/deadlocks | Do slow compute/provider work outside; short transaction at each controlled DB effect |
| Resolver APIs encourage persisting credentials | Secret exposure/stale grants | Typed stable reference, prohibited fields, security tests and docs |
| Policy change semantics surprise users | Queued work may be denied later | Make current-authorization rule stable/public; structured denial |
| Approval expiry/retry interpretation is unclear | Valid work stalls or old intent lasts too long | Bind once per O; expiry before first effect; overall deadline; document and test |
| Task and operation status drift | Operators see conflicting answers | O authoritative for linked work; transactional projection/reconciliation diagnostics |
| Action version removed during deploy | Nonterminal work cannot resume | Deployment preflight lists referenced versions; retain or fail closed |
| Idempotency retention too short | Client retry creates duplicate later | Public configured minimum, tombstones, metrics before pruning |
| Result/history grows without bound | Database/storage pressure | Size caps, separate TTLs, batch pruning, indexes and load tests |
| Heartbeats create hot-row load | Throughput degradation | Update only active rows, tune cadence/lease, benchmark, use current attempt row if needed |
| External ambiguity hidden as retryable failure | Duplicate payments/email | Persist pre-effect intent and stable effect identity/key; retry the same key, reconcile authoritatively, or stop as `external_outcome_unknown` |
| MCP extension/API changes upstream | Compatibility churn | Wait for official SDK implementation; conformance gate; no custom stable protocol |
| Scope expands into workflows/planners | v0.7 becomes unfinishable | No dependencies/DAG/planner state in core; action executes one logical operation |
| Generic public endpoint leaks internals | Long-term API lock-in/security exposure | Semantic response DTO; internal schema/attempt details hidden |

# Implementation Sequence

No step below is implementation authorization; it is the dependency order to
use after this ADR is approved.

1. **Invariant prototype and executable specification.** Prove one-connection
   atomic mutation/completion and N/N+1 fencing with minimal internal test-only
   records on local PostgreSQL. Finalize transition/error vocabulary from the
   tests.
2. **Versioned internal migration and repositories.** Add operation, attempt,
   transition/outbox, idempotency, and optional decision storage through
   framework migrations. Keep every API internal/experimental.
3. **Admission/state machine/idempotency.** Implement conditional transitions,
   canonicalization/versioning, concurrent duplicate behavior, terminal
   envelopes, and pruning/tombstones before executing user work.
4. **Claims, leases, heartbeats, and fences.** Implement DB-clock ownership and
   kill/restart recovery. Do not integrate tasks until late-worker tests pass.
5. **Principal reference/resolver and reauthorization.** Add fail-closed stable
   identity resolution and reuse current permission/policy/tenant/object/field/
   RLS enforcement at operation boundaries.
6. **PostgreSQL executor.** Bind registered generated/application database
   actions to the atomic transaction context. Prove every crash boundary and
   uncertain commit response.
7. **Status, cancellation, history/export, and core limits.** Add the minimal
   internal then experimental Python/REST representation, durable cancellation
   races, attempt/deadline bounds, redaction, and sink retries.
8. **Task adapter.** Add nullable operation linkage and operation-authoritative
   recovery/projection while preserving task-only behavior and CLI contracts.
9. **Durable approval decisions.** Add exact binding, decision authorization,
   expiry, supersession, and crash-retry semantics. Keep UI/business flows out.
10. **External-effect context and selected adapters.** Persist executor-owned
    pre-effect intent with a stable effect identity/ordinal, pass the derived
    key, and require effect classification. Validate idempotent,
    authoritatively reconcilable, and unknown-outcome paths without claiming
    generic delivery guarantees.
11. **Official MCP Tasks adapter when SDK support exists.** Negotiate the
    extension, map O to protocol Tasks, and run protocol/multi-client isolation
    conformance. Synchronous tools remain the baseline.
12. **Multi-process production gate and stability review.** Exercise hosted
    PostgreSQL 16, restricted roles/RLS, worker kill, restart, contention,
    pruning, installed wheel, compatibility, security, and documentation before
    declaring the public v0.7 contract stable.

Steps 1 through 6 form the first internal experimental milestone. A public API
before those invariants pass would freeze status without execution truth.

# Experiments Required

## Experiment 1: atomic effect and completion

Build a test-only registered executor using current `transaction.atomic()` and
session reuse. Lock a test operation/fence, mutate an application row, and
finalize in one transaction. Inject process/connection failure before mutation,
after mutation, after operation update, and around commit acknowledgement.
Acceptance: no database state contains mutation without success or success
without mutation; a reconnect can always decide from O.

## Experiment 2: lease/fence race

Use two real processes/connections and PostgreSQL time. A claims N and pauses;
its lease expires; B claims N+1. Resume A and attempt heartbeat, progress,
application mutation, and success. Acceptance: every A write fails its
condition, its mutation rolls back, and B alone can finalize.

## Experiment 3: principal resolver boundary

Create a stable user/agent reference, then alter roles, tenant membership,
object access, field policy, expiry, and deletion between admission and effect.
Simulate resolver outage and missing resolver. Acceptance: current allowed work
runs; revoked work performs no effect; transient outage retries; missing/
tampered provenance fails closed; no credential is stored.

## Experiment 4: idempotency and lost response

Submit hundreds of concurrent same-key/same-hash and same-key/different-hash
requests across processes, then drop responses after admission and commit.
Acceptance: one O for identical input, conflicts for changed input, one committed
database effect, and deterministic terminal retrieval.

## Experiment 5: task adapter recovery

Link a task to O and kill workers before/after task claim, operation claim,
effect, and projection. Acceptance: operation state remains authoritative,
unlinked tasks are unchanged, and no independent stale task reset can supersede
an active operation lease.

## Experiment 6: external pre-effect recovery

Use one selected external adapter and kill the worker after committing intent
but before network send, then after provider success but before local result
recording. Exercise providers with idempotency, authoritative lookup, and
neither capability. Acceptance: every physical attempt reuses the same logical
effect identity, ordinal, and derived provider key; recovery retries only the
same idempotency key, reconciles before retry where authoritative lookup exists,
and otherwise stops with `external_outcome_unknown` without asserting success
or failure. The prototype stays executor-owned and does not create a generic
public `ExternalEffect` subsystem.

## Experiment 7: MCP SDK extension readiness

Against the first official Python SDK release that implements
`io.modelcontextprotocol/tasks`, build a disposable adapter and use an official
client to test negotiation, durable creation before handle return, polling,
input/approval behavior, cancellation, TTL, result, and cross-client/tenant
isolation. Acceptance: conformance passes without private SDK hooks. Until then,
do not accept the MCP adapter as stable.

These experiments are required validation, not reasons to postpone the
Operation/Attempt decision. Only the exact public endpoint names and MCP adapter
timing depend on their results.

# Unknowns

The following implementation choices remain open without weakening the
decision:

* exact internal table/column/index names and whether outbox delivery metadata
  shares the transition table;
* whether executor commands are stored in one encrypted internal table or in
  executor-specific tables only;
* canonicalization version format and action deployment/version-retention
  tooling;
* default/max idempotency, terminal result, attempt, transition, and MCP TTLs;
* lease/heartbeat defaults and throughput targets;
* the exact public Python and REST names, and whether listing ships in the first
  stable slice;
* the physical direction of the nullable task/operation foreign key while
  retaining the conceptual one-to-one executor binding;
* whether approval rejection is publicly rendered as cancelled or failed while
  preserving the stable reason code;
* which external adapters, if any, are sufficiently useful to ship with v0.7;
* the official Python SDK version/timeline for the 2026-07-28 Tasks extension.

Questions already decided and not open: operations and attempts are separate;
the operation row is current authority; same-database completion is atomic;
fencing occurs inside the mutation transaction; provenance is not authority;
reauthorization is current; approval is separate; external exactly-once is not
promised; PostgreSQL remains the required infrastructure; synchronous v0.6
surfaces remain compatible.

# Final Recommendation

Approve ADR 0001 and begin only the invariant prototype described in Experiment
1 and the state-machine/fencing specification. Do not start with REST/MCP UI,
planner persistence, or task-table expansion. The critical proof is that an
Aksara-controlled PostgreSQL mutation and the operation's authoritative success
cannot disagree, even after worker death and an uncertain commit response.

The selected design is the smallest coherent model supported by current code:
it adds one logical authority and one physical-attempt vocabulary, reuses
PostgreSQL and current security enforcement, and lets current executors opt in.
It deliberately stops before orchestration.

## Plain answers

1. **What is the chosen architecture?** A PostgreSQL-backed shared Operation
   plus separate Attempt substrate, with scoped idempotency, lease/fence
   ownership, stable principal references and current reauthorization, optional
   operation-bound approval decisions, durable cancellation, core limits, and
   bounded transition/outbox history. Existing executors adapt to it.
2. **Why is it better than extending the existing task model directly?** An
   operation is logical authorization and outcome truth; a task is one queue/
   scheduling mechanism. Extending tasks would couple synchronous work,
   approval, security provenance, retention, and public status to queue fields
   while still needing separate attempt history and fence semantics.
3. **What becomes authoritative?** The Operation row is authoritative current
   logical state. Attempt and approval rows are authoritative execution/
   decision facts. Logs, MCP audit sinks, HTTP responses, and linked task status
   are exports/projections.
4. **What exactly can Aksara guarantee after a response is lost?** With a
   retained client idempotency key, the same canonical submission returns the
   same Operation. For a same-database atomic executor, `succeeded` proves the
   application mutation and success state committed together; nonterminal state
   recovers by lease without creating a second operation.
5. **How is duplicate execution prevented?** A unique scoped idempotency identity
   prevents duplicate logical operations, and current-attempt/fence checks
   prevent more than one claimant from committing a framework database effect.
   Before a mutating external call, its executor persists intent with a stable
   effect identity/ordinal and derived provider key. Recovery reuses that key,
   reconciles against provider authority, or stops as `external_outcome_unknown`;
   it does not blindly repeat an ambiguous effect.
6. **How is a late worker fenced?** Every claim increments a monotonic token.
   Heartbeat, progress, effect entry, and finalization require the current
   attempt and token. After N+1 is claimed, Worker A's N update affects zero rows;
   failure inside the same transaction rolls back A's database mutation.
7. **How is authorization safely reconstructed after restart?** Persist only a
   versioned stable principal reference and requested policy context. A
   registered resolver obtains a current `Principal`; current permissions,
   tenant, object, field, policy, and RLS checks run before each controlled
   effect. No reusable credential or old roles/scopes authorize work.
8. **What does approval mean?** A current authorized approver recorded intent
   for one exact operation/input/action/requester/tenant before expiry. It can be
   used only by that logical operation and survives its physical retries. It
   never overrides current requester authorization.
9. **What does cancellation mean?** It is durable, authorized intent checked on
   claim, heartbeat, and controlled effect boundaries. It prevents queued work
   and can win a database transaction race, but it cannot undo a committed or
   already-issued external effect.
10. **What does Aksara explicitly refuse to guarantee?** Exactly-once arbitrary
    external effects, undo of committed work, safe lost-admission recovery
    without a client key, cross-database atomicity, infinite retention, durable
    agent/planner/session behavior, or a generic workflow engine.
11. **Does PostgreSQL remain sufficient?** Yes. Existing required PostgreSQL
    provides transactions, unique constraints, row locks, `SKIP LOCKED`, DB
    time, JSONB, indexes, migrations, restricted roles, and RLS needed for this
    scope. No measured requirement justifies another service.
12. **What should be implemented first after the ADR is approved?** A test-only
    invariant prototype proving one-connection atomic mutation/completion and
    the N/N+1 late-worker fence, followed by the internal state machine and
    migrations only after those tests fix the contract.
13. **What finding from the code most changed the initial design hypothesis?**
    The task queue already has durable claims and recovery, but user work and
    `completed` are separate transactions and completion is guarded only by task
    ID. A stale worker can therefore overwrite a newer claimant, so adding
    provenance columns to `aksara_tasks` would not solve execution truth; a
    separate attempt/fence model tied to the mutation transaction is necessary.
