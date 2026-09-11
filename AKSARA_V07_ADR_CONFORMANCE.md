# Aksara v0.7 ADR 0001 Conformance

Release: `v0.7.0`

Architecture source: `docs/adr/0001-durable-authorized-operations.md`

Verdict: **PROVEN WITH REQUIRED IMPLEMENTATION CONSTRAINTS**

No implementation evidence contradicts ADR 0001. The prototype constraints
remain requirements of the production `postgres_atomic` executor.

## Decision classification

| ADR 0001 decision | Classification | Production evidence or constraint |
| --- | --- | --- |
| PostgreSQL-backed Operation is authoritative logical request | IMPLEMENTED | `aksara_operations` stores current state; services never reconstruct it from history. |
| Separate physical Operation Attempts | IMPLEMENTED | Each claim creates an ordinal, owner, lease, and fence; reclaim abandons the previous Attempt. |
| Central bounded state and transition vocabulary | IMPLEMENTED | Operation/Attempt states, allowed events, terminality, and failure reasons are centralized and state-machine tested. |
| Scoped, time-bounded idempotency with canonical input | IMPLEMENTED | Application, tenant, principal provenance, action/version, client key, and normalized input are hashed; concurrent duplicates resolve one Operation and changed semantics conflict. |
| Non-secret principal provenance and code-registered current resolver | IMPLEMENTED | `PrincipalReference` omits reusable credentials and runtime authority; resolver name/version comes from the deployed allowlist. |
| Current authorization before delayed effects | IMPLEMENTED WITH DOCUMENTED CONSTRAINT | Current identity, tenant, scope, action authorizer, and `PolicyEngine` run before supported effect boundaries. Application authorizers own object, permission, field, and model-specific policy. External identity revocation is subject to the documented current-resolution boundary. |
| Monotonic fencing and database-time leases | IMPLEMENTED | Claim/heartbeat/reclaim/finalization condition on current Attempt, owner, and fence; stale N is rejected after N+1. |
| Atomic same-PostgreSQL mutation and completion | IMPLEMENTED WITH DOCUMENTED CONSTRAINT | Production fault injection proves mutation, Attempt success, Operation success, result, transition, and outbox commit or roll back together when handlers use the guarded owning `Database` transaction. Arbitrary Python effects are outside this guarantee. |
| Ambiguous acknowledgement requires authoritative reread | IMPLEMENTED | A finalized commit-path exception rereads PostgreSQL; lost-response tests and idempotent resubmission recover the one Operation. |
| Durable approval binding | IMPLEMENTED | Pending/approved/rejected/expired/superseded storage binds Operation, input, action/version, tenant, requester, approver, and expiry; first claim consumes once for the logical Operation. |
| Durable cancellation intent and deterministic completion race | IMPLEMENTED | Waiting/ready cancellation is terminal; running cancellation is persisted and the Operation row lock selects it or success as the winner. No undo is claimed. |
| Attempt/deadline/backoff limits | IMPLEMENTED | Attempt count/max Attempts, deadline, and `available_at` survive restart; terminal states do not reopen implicitly. |
| Bounded transition evidence and transactional outbox | IMPLEMENTED WITH DOCUMENTED CONSTRAINT | Every authoritative transition emits outbox intent in the same transaction. The application sink and long-term retention are not operation authority. |
| Bounded pruning and idempotency tombstones | IMPLEMENTED | Active rows are protected; result/error bodies can expire separately; operations and identities are pruned in DB-time batches after their windows. |
| Existing tasks are optional executors | IMPLEMENTED | Linked tasks defer ownership to Operation Attempts and fences; unlinked task behavior and public task contracts remain unchanged. |
| Honest external effect classes and ambiguity | IMPLEMENTED WITH DOCUMENTED CONSTRAINT | Idempotent, reconcilable at-least-once, nonretryable, and read-only paths are explicit. Aksara preserves started-but-unconfirmed work as `external_outcome_unknown` across lease loss and lifecycle closure, and cannot provide an atomic PostgreSQL/provider transaction. |
| DurableStep is not silently redefined | DEFERRED BY ADR | The existing workflow-step cache remains functional and evolving, outside v0.7 Operation guarantees. |
| Workflow/DAG, memory, planner, Studio AI, autonomous orchestration | DEFERRED BY ADR | No such surface is stabilized or expanded. |
| Protocol-level durable MCP Tasks | DEFERRED DUE TO EXTERNAL STANDARD | MCP's current Tasks extension is not implemented by the official Python SDK used for the candidate. Existing synchronous `/mcp/` behavior remains tested. |
| No new mandatory service | IMPLEMENTED | PostgreSQL remains the only durable authority; Redis, Kafka, Celery, Temporal, and additional coordination systems were not added. |

## Prototype constraints retained

The `postgres_atomic` guarantee is valid only when the Operation tables and
application data use the same Aksara `Database` and PostgreSQL database, one
outer Aksara transaction owns completion, the active connection is pinned, the
Operation row is locked, all current ownership/decision/authorization checks
pass under that lock, and the application mutation uses the guarded execution
context in the owning asyncio task.

Admission requires an explicit tenant ID for `postgres_atomic` actions. This
keeps the internal global-operation storage sentinel out of UUID-backed
application RLS policies; global PostgreSQL mutation is outside this bounded
atomic contract.

Direct pool acquisition, independent connections or commits, another
`Database`, another database, subprocess/thread database mutation, concurrent
child-task use of the inherited connection, or network effects invalidate the
atomic classification. Fatal ownership or boundary errors cannot be swallowed
through nested savepoints. Every authoritative ownership write remains
conditioned on current Attempt and fence.

## Authority and audit boundary

The current Operation row is authoritative. Attempts and approval decisions
explain claims and intent. Transitions and outbox rows provide bounded
operational evidence. They are not replayed into truth and are not a
tamper-resistant compliance ledger. The application database role and deployed
action/resolver code remain trusted parts of the boundary.

## Contradictions

None.
