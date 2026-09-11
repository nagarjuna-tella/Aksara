# Aksara v0.7.0 — Durable Authorized Operations

## Durable execution

Aksara v0.7.0 adds opt-in Durable Authorized Operations. PostgreSQL stores one
authoritative logical Operation and a separate Attempt for each physical claim,
so accepted work remains identifiable, queryable, and recoverable after a
response, process, or worker is lost.

## Safe retries and recovery

Scoped idempotency binds application, tenant, initiating principal,
action/version, client key, and normalized input. Identical submissions resolve
the same Operation; changed input conflicts. Database-time leases, bounded
Attempts, and monotonic fences reject stale workers. Ambiguous commit
acknowledgements recover by rereading PostgreSQL instead of issuing a blind
replacement mutation.

## Authorization across time

Stored principal provenance is non-secret and is never treated as permission.
Before a delayed effect, Aksara resolves a current `Principal` and rechecks the
tenant, scopes, action authorization, and `PolicyEngine` decision.

## Approval and cancellation

Approval decisions are durable and bound to the exact Operation, input,
action/version, tenant, requester, approver, and expiry. Approval never restores
revoked authority. Cancellation is durable intent that competes with completion
under the authoritative Operation row lock; it does not undo a committed effect.

## PostgreSQL atomic execution

For a supported `postgres_atomic` action, the application mutation, Attempt and
Operation success, result, transition, and outbox intent commit in one guarded
Aksara transaction. The guarantee requires the same Aksara `Database`, the same
PostgreSQL database, an explicit tenant, and mutation through the supplied
execution context. Independent connections, commits, subprocesses, threads,
other databases, and network effects are outside this atomic boundary.

## External effects

External actions declare idempotent, reconcilable at-least-once, nonretryable,
or read-only behavior. Stable operation-scoped identity supports provider
idempotency and reconciliation. An ambiguous outcome that cannot be reconciled
becomes `external_outcome_unknown`; Aksara does not claim exactly-once external
effects or cross-system atomic transactions.

## Background tasks

Existing background tasks can optionally schedule durable execution. The
Operation Attempt and fence remain authoritative, while unlinked task behavior
and APIs remain unchanged.

## Compatibility

Durability is additive and opt-in. Existing v0.6 ORM, migrations, synchronous
REST and MCP, identity, permission, tenant, task, CLI, and diagnostic contracts
remain in force. PostgreSQL remains the only mandatory durability service.

## Deferred

Protocol-level MCP Tasks, planner quality, persistent AI sessions and memory,
multi-agent and autonomous workflows, provider quality, Studio AI internals,
generic workflow/DAG composition, application approval UX, and long-term
compliance retention remain experimental, application-owned, or deferred.

## Upgrade notes

1. Install `aksara-framework==0.7.0` and run `aksara migrate` with the migration
   role before application startup.
2. Grant the restricted application role the required DML and sequence
   privileges on the new internal tables.
3. Register every deployed durable action and principal resolver version before
   workers claim work.
4. Start explicitly tenant-scoped workers and the application-owned outbox
   exporter, and configure retention, backups, and monitoring for accepted work.
5. Run `check_durable_operations()` and
   `aksara doctor production-check --release` for each production deployment.

See the [v0.7 stability contract](docs/docs/roadmap/v0-7-stability-contract.md)
for the complete guarantees and limits.
