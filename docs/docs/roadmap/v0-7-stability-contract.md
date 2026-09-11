# v0.7 Durable Operations Stability Contract

This contract defines the additive production surface introduced by
`v0.7.0rc1`. It extends the [v0.6 stability and production
contract](v0-6-stability-contract.md); all stable v0.6 ORM, migration, REST,
identity, permission, tenant, task, MCP, CLI, and diagnostic behavior remains
in force.

## Required production profile

The v0.7 durable-operation guarantees apply when:

- the deployment follows the v0.6 restricted-role, forced-RLS, migration, and
  supported-runtime profile;
- the v0.7 internal migrations have been applied before application startup;
- each nonterminal action name/version and principal resolver version remains
  registered in the deployment;
- every `postgres_atomic` action uses the same Aksara `Database` and PostgreSQL
  database as the operation tables and writes only through its guarded
  execution context;
- external actions use an accurate effect classification and adapter; and
- operators run workers, outbox export, retention, backups, and monitoring for
  the workloads their applications accept.

## Stable v0.7 additions

The stable semantic surface consists of:

- `DurableAction` and `DurableActionRegistry` for code-controlled action
  name/version registration;
- `PrincipalReference`, `PrincipalResolution`, and
  `PrincipalResolverRegistry` for non-secret provenance and current authority;
- `DurableOperationService` admission, lookup, status, approval decision,
  cancellation, history, deployment check, and bounded pruning semantics;
- `OperationRecord`, `OperationAdmission`, `OperationState`, and `EffectClass`;
- `create_durable_operations_router()` as an explicit generic dispatch,
  status, decision, and cancellation boundary;
- `DurableOperationWorker`, `PostgresAtomicExecutor`, `ReadOnlyExecutor`, and
  their documented effect-class selection;
- `ExternalEffectContext`, `ExternalEffectAdapter`, result/reconciliation
  values, `ExternalOperationExecutor`, and `ExternalOutcomeUnknown`;
- `enqueue_operation_task()` for optional task-backed execution;
- `DurableOutboxExporter`; and
- `check_durable_operations()` and its machine-readable deployment result.

These names expose application semantics. Internal repositories, tables,
columns, raw commands, transition/outbox rows, attempt IDs, worker IDs, fence
tokens, lease SQL, raw provenance, and failure-campaign hooks are not public
contracts.

## Guaranteed behavior

### Durable truth and recovery

A returned Operation ID refers to committed PostgreSQL state. Until its
retention deadline, an authorized caller can query that state after request,
worker, or process loss. The Operation is one logical request; each physical
claim is a separately recorded Attempt.

For `postgres_atomic`, supported application mutation, Attempt success,
Operation success, result, transition, and outbox intent share one transaction.
After an ambiguous local commit acknowledgement, the caller rereads that
Operation or resubmits the same idempotency identity. It does not gain authority
to perform a blind replacement mutation.

### Scoped idempotency

A client key is scoped by application namespace, tenant, stable initiating
principal, action/version, and normalized semantic input. During the configured
window, identical submissions return the same Operation, including under
concurrency. Reusing the identity with changed input or action version fails
with a deterministic conflict. No infinite deduplication promise is made.

### Claims, leases, and fencing

PostgreSQL time controls eligibility and lease expiry. A claim locks the
Operation, validates eligibility, creates an Attempt, increments the fence, and
establishes one owner atomically. A replacement records expired ownership as
abandoned before advancing the fence. Once fence N+1 owns the Operation, N
cannot heartbeat, mutate through the guarded database boundary, retry, cancel,
or finalize.

### Current authorization

Stored provenance is never permission. Before a supported side effect, Aksara
resolves a current `Principal`, verifies the immutable provenance binding, and
rechecks current tenant, scope, action authorization, and `PolicyEngine`
decisions. Applications use the action authorizer for their current object,
permission, field, and validation policy. RLS remains defense in depth and the
production tenant boundary. A missing, malformed, deleted, disabled,
membership-removed, or revoked identity fails closed; explicitly temporary
resolution failure can use bounded retry.

### Approval, cancellation, and limits

A durable approval decision is bound to the exact Operation, normalized input,
action/version, tenant, requester and approver provenance, and expiry. It is
consumed once per logical Operation and remains valid across replacement
Attempts. It never overrides current authorization.

Cancellation persists intent and deterministically competes with a guarded
effect through Operation-row locking. It prevents later work when it wins; it
does not undo an already committed PostgreSQL transaction or issued external
effect. Overall deadline, next eligibility, Attempt count, and maximum Attempts
survive restart.

### Tasks, external effects, history, and retention

Linked tasks schedule execution but do not become operation authority. The
Operation Attempt and fence control execution; task state is a compatibility
projection. Unlinked v0.6 tasks remain unchanged.

External effect intent and a stable operation-scoped identity are stored before
the provider boundary. Idempotent providers reuse the same key; reconcilable
providers are checked before repeat. An unreconcilable ambiguous result becomes
`external_outcome_unknown`. Exactly-once external effects are not guaranteed.

Transition history and its outbox explain state and support retryable export.
They are bounded evidence, not event sourcing or long-term compliance storage.
Pruning is batched, keeps active work, and preserves idempotency identities for
their full promised window. Result and error bodies may expire before terminal
Operation metadata.

#### Compatibility

Durable behavior is explicit and optional. Existing applications need not
register a durable action or mount its router. Generated REST remains
synchronous. Existing Streamable HTTP MCP tools and signed synchronous approval
grants keep the v0.6 contract. Existing unlinked background tasks, IDs, APIs,
queues, scheduling, and CLI continue to work. `Principal` remains the runtime
authority type.

`DurableStep` remains available as an evolving workflow-step cache. It does not
gain Operation/Attempt, lease, fencing, current authorization, cancellation, or
atomic-completion guarantees in v0.7.

## Documented limits

- The application process and its database role are trusted. Raw SQL with that
  role can alter application-owned operation/history rows; transition and
  outbox records are not a tamper-resistant compliance ledger.
- The guarded database runtime detects covered Aksara connection escapes, but
  action registration is code trust. Review handlers for arbitrary network,
  subprocess, thread, or independent-database effects.
- Current authorization does not promise instantaneous global revocation
  linearizability across an unavailable external identity provider.
- External exactly-once delivery, distributed transactions, and undo are not
  provided.
- Worker orchestration, tenant enumeration, approval user interfaces, business
  escalation, and long-term audit retention remain application/operator work.
- The PostgreSQL-first design does not define a universal throughput SLO.

## Experimental and deferred

The following remain outside the stable v0.7 contract:

- planner quality, investigation content and sessions, persistent
  conversations, agent memory, multi-agent/autonomous workflows, provider
  quality, code/patch execution, and Studio AI internals;
- generic workflow/DAG composition and `DurableStep` internals;
- application approval workflow UX and durable compliance retention;
- protocol-level MCP Tasks, because the current official Python SDK does not
  implement the `io.modelcontextprotocol/tasks` extension;
- custom many-to-many through models and object-valued lazy forward foreign
  keys; and
- Redis, Kafka, Celery, Temporal, or any additional mandatory coordination
  service.

## Upgrade and operation

1. Install the candidate and run `aksara migrate` with the migration role.
2. Grant the restricted application role required DML and sequence privileges
   on the newly migrated internal tables.
3. Register every durable action and principal resolver version before workers
   claim work.
4. Run `check_durable_operations()` for each deployed application namespace and
   tenant profile; treat missing schema/action/resolver results as blocking.
5. Start explicitly tenant-scoped workers and the application-owned outbox
   exporter.
6. Set and monitor Operation, result, error, idempotency, and audit-retention
   windows for the application workload.
7. Keep old action/resolver versions deployed while nonterminal Operations
   still reference them.
