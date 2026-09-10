# Executive Summary

**Verdict: PROVEN WITH REQUIRED IMPLEMENTATION CONSTRAINTS.**

The test-only prototype proves both foundational invariants of ADR 0001 against
real PostgreSQL and Aksara's current transaction/session machinery:

1. A framework-controlled application mutation, Attempt success, and Operation
   success commit or roll back together when they execute on one Aksara-pinned
   connection and transaction.
2. After a database-time lease expiry and an atomic N to N+1 takeover, stale
   worker N cannot heartbeat, write progress, mutate the application row, or
   finalize. The decisive ownership check occurs while the Operation row is
   locked inside the same transaction as the application mutation.

This is a conditional result. A future `postgres_atomic` executor must enforce
the constraints identified below. A caller can bypass the active transaction by
acquiring `Database.pool` directly or opening an independent connection. The
negative controls demonstrate that such an escape creates the split durable
truth that ADR 0001 forbids. Concurrent child tasks also inherit the session
`ContextVar`; they must not perform concurrent work on the same asyncpg
connection.

The experiment added no production code, migrations, public API, version
change, task/MCP integration, durable approval, or final Operation schema. The
three tables and restricted role were created and removed by test fixtures.

# Environment

| Item | Value |
| --- | --- |
| Branch | `codex/v07-operation-invariant-prototype` |
| Base SHA | `0abd0ada6e8b776d06f2586551e10a461d6d4ea3` |
| Base | current `origin/main` when the experiment began |
| Python | 3.11.5 |
| PostgreSQL | 18.4 (Debian 18.4-1.pgdg13+1) |
| asyncpg | 0.31.0 |
| Aksara | 0.6.1 |
| Database | local `aksara_test` |
| Application role | ephemeral restricted role; `NOSUPERUSER`, `NOBYPASSRLS` |
| Pool | min 1, max 4 |
| RLS | enabled and forced on all prototype tables |
| Focused result | 24 passed in 6.40 seconds |
| Related regression result | 57 passed in 6.73 seconds |
| Full suite result | 8,034 passed, 2 expected skips in 52.97 seconds |

Credentials are absent from the evidence. See
`audit-evidence/v070-invariants/environment.json`.

# Existing Transaction Semantics

`TransactionManager.__aenter__()` reads the session `ContextVar`. With no
session, it acquires and owns a pool connection, applies tenant context, pushes
the connection, and begins an asyncpg transaction. With an existing session, it
uses that connection and begins a nested asyncpg transaction. In PostgreSQL,
that nested transaction is a savepoint.

`Database.acquire()` also checks the session first. Its `execute`, `fetch`,
`fetchrow`, and `fetchval` methods all pass through `acquire()`. The tested
`Model.save()`, `Manager.create()`, and QuerySet update paths use those Database
methods. The real integration test observed one backend PID for the Operation
lock, ORM read, model save, Attempt update, and Operation update.

`TransactionManager.__aexit__()` rolls back whenever an exception type is
present. This includes `asyncio.CancelledError`. It resets the session token and
uses shielded connection release. A real terminated backend and four injected
cancellations left no committed split state; a later query succeeded.

The answers from the code trace and executable checks are:

1. Nested supported ORM work reuses the pinned connection.
2. The tested manager/query paths do not silently acquire another connection.
3. ORM writes are covered only when they continue through the active Aksara
   Database session.
4. Direct `db.pool.acquire()`, independent connections/drivers, subprocesses,
   threads, and external systems bypass the transaction. Concurrent child
   tasks inherit the ContextVar and can incorrectly share one asyncpg
   connection.
5. Cancellation rolls back the outer transaction.
6. A caught inner error rolls back its savepoint and permits the outer
   transaction to continue and commit. Future executor error policy must not
   swallow an error intended to abort the operation boundary.
7. `postgres_atomic` must prohibit independent commits, transaction escapes,
   mutation before the ownership lock/check, finalization-only fencing, and
   concurrent use of the pinned connection.

The detailed trace is recorded in
`audit-evidence/v070-invariants/existing-transaction-semantics.json`.

# Prototype Model

The fixture creates three disposable tenant-scoped tables:

- Prototype Operation: state, current Attempt, fence, worker, database-time
  lease, progress, and completion backend PID.
- Prototype Attempt: Operation, fence, worker, state, lease, progress, start and
  completion timestamps, and backend PIDs.
- Prototype Counter: an application row with `mutation_counter`. One legitimate
  execution changes 0 to 1; a stale or duplicate execution would make it 2.

A database trigger records `pg_backend_pid()` on each counter insert/update.
This permits database-side connection identity comparison without relying on a
mock. The schema is deliberately smaller than the ADR model and has no migration.

# Connection-Pinning Proof

The normal completion observed a single backend PID across:

1. Operation `SELECT ... FOR UPDATE` and ownership validation;
2. ORM application-row read;
3. `Model.save()` application mutation;
4. Attempt success update;
5. Operation success update; and
6. the counter trigger's database-side observation.

The test also used `Manager.create()` and a QuerySet `F()` update in a nested
`atomic()` block. The inner block received the identical connection object and
backend PID. Its injected error rolled back only the savepoint; the outer work
committed after the error was caught.

An explicit `db.pool.acquire()` during the outer transaction returned a
different backend PID. That is a known escape, is reproduced by the harness,
and must be rejected by executor eligibility and implementation review.

# Atomic Completion Invariant

The test-only completion boundary performs these steps in one outer
`transaction.atomic(db=...)` block:

1. lock the Operation;
2. validate running state, current Attempt, worker, fence, and unexpired lease;
3. mutate the application counter through the ORM;
4. conditionally mark the Attempt succeeded;
5. conditionally mark the Operation succeeded; and
6. commit once.

Fresh connections inspected PostgreSQL after failures before begin, after the
lock, during a real CHECK-constraint violation, after the mutation statement,
after Attempt success, and after Operation success but before commit. Every
precommit failure left the counter at 0, Operation running, and Attempt running.

`CancelledError` was injected after the lock, application mutation, Attempt
update, and Operation update. All four cases rolled back and cleared the active
session. Terminating the actual PostgreSQL backend after the mutation also
rolled back, caused the pool to replace the connection, and allowed a subsequent
query.

The prototype intentionally leaves the Operation running after these failures.
Final failure recording and retry policy are outside this experiment; the lease
and reclaim tests establish the recovery path.

# Lost Commit-Acknowledgement Experiment

The deterministic experiment allowed the transaction context to receive a
successful commit response, discarded that local result, and raised a client
error. A new restricted-role connection then read:

```text
Operation = succeeded
Attempt = succeeded
application mutation counter = 1
```

This proves the recovery rule: after an ambiguous outcome, reconnect and read
the authoritative Operation before any retry. It does not deterministically
inject packet loss between the PostgreSQL server's commit and asyncpg's receipt
of the acknowledgement. A real backend termination before commit was tested
separately and rolled back. Exact network loss during commit remains a future
fault-proxy or network-level integration test; PostgreSQL atomicity means the
post-reconnect states remain jointly committed or jointly absent.

# Atomicity Negative Control

Two deliberately broken flows produced the forbidden state:

- the application counter committed in transaction A, followed by a simulated
  crash before Operation completion in transaction B;
- an independent connection committed the counter while the outer Operation
  transaction later failed.

Both produced counter 1 with Operation and Attempt still running. The harness
therefore detects split application/operation commits and connection escape.
The reverse broken flow committed Attempt and Operation success without running
the application mutation; the harness observed counter 0 with both records
succeeded. The checks are sensitive to both directions of the biconditional.

# Lease / Claim Prototype

Claim uses PostgreSQL `clock_timestamp()` and `SELECT ... FOR UPDATE`. It rejects
a live running owner. For a ready row, or a running row whose database-time
lease expired, one transaction:

1. marks the prior current Attempt abandoned when reclaiming;
2. increments the fence;
3. creates a new running Attempt;
4. assigns the current Attempt, worker, fence, and lease to the Operation; and
5. commits the transfer.

Fifteen simultaneous races used two independent PostgreSQL connections. Every
iteration produced exactly one claimant and fence 1. The losing claimant
returned no ownership.

# N/N+1 Fencing Proof

Worker A claimed fence 1 with a short lease. After PostgreSQL time passed the
deadline, Worker B locked and reclaimed the Operation at fence 2. The transfer
atomically left A abandoned, B running, B current, and fence 2 authoritative.

A then attempted every prototype-authoritative path with its old Operation,
Attempt, worker, and fence identity. Heartbeat, progress, success, failure, and
cancellation-like updates affected zero rows. Atomic completion raised
ownership lost before application mutation. B subsequently completed; the
fresh final read showed counter 1, A abandoned, B succeeded, Operation
succeeded, and fence 2.

# Stale Heartbeat Results

Heartbeat conditions both Attempt and Operation writes on Operation ID, tenant,
current Attempt, worker, fence, and running state. A heartbeat at fence N after
N+1 takeover updated zero rows and could not extend either lease.

The broken heartbeat control omitted Attempt and fence identity. A stale
request then extended the current owner's lease. The harness detected this,
showing that every authoritative write needs full ownership identity.

# Stale Mutation Results

The correct stale path locks the Operation and validates ownership before any
application SQL in the same transaction. After B owned N+1, A's check failed,
the mutation counter remained 0, and B's state was unchanged.

Two negative controls committed stale application state:

- mutate first, then discover the stale fence during finalization;
- lock/check only the Operation's running state while omitting current Attempt,
  worker, and fence.

In both cases the counter became 1 while B remained authoritative. This proves
that a finalization-only check and an incomplete ownership predicate are
insufficient.

# Lease-Expiry-During-Transaction Race

A locked and validated the Operation before its lease deadline. The deadline
passed while A continued holding the row lock, and B attempted reclaim on an
independent connection. B remained blocked until A ended its transaction.

- When A committed mutation and success, B woke, observed a terminal Operation,
  and did not reclaim.
- When A rolled back, B woke, observed the expired lease, reclaimed at N+1, and
  the application counter remained 0.

There was no state where A mutated under N while B had already committed N+1.
The lease is validated at the protected boundary; row locking serializes the
completion/takeover decision after that point.

# Multi-Process Results

The subprocess experiment used independent Python processes and independent
PostgreSQL connections:

1. two claim processes raced and exactly one won;
2. process A claimed and was hard-killed by the parent process;
3. after database-time lease expiry, process B reclaimed at N+1;
4. a new process carrying A's stale Attempt/worker/fence identity simulated a
   paused or restarted stale holder and could not mutate; and
5. a parent fresh connection inspected committed state.

A literally killed operating-system process cannot later wake. The last step
therefore uses a separate process with A's stale credentials, which exercises
the same database authorization predicate as a suspended or restarted worker.

# Transaction Escape Findings

`Model.save()`, `Manager.create()`, QuerySet update, and normal Database methods
participated in the pinned transaction. No tested supported ORM path silently
opened another connection.

The following are outside that guarantee and must be prohibited for a
`postgres_atomic` action:

- direct `Database.pool.acquire()`;
- an independently created asyncpg or other database connection;
- a different PostgreSQL database or nontransactional store;
- application work in a subprocess or thread outside the operation transaction;
- external network effects;
- concurrent asyncio child tasks doing database work with an inherited session;
- rebinding or otherwise bypassing the intended Database instance; and
- catching an exception that should abort the outer operation transaction.

Generated API helpers, relation mutation, every bulk path, and user-defined raw
SQL wrappers were not exhaustively tested. Production eligibility needs an
allowlisted executor boundary and escape-focused tests, rather than a claim
that arbitrary application Python is atomic.

# Pool / Session Cleanup Results

Four repeated cancellations cleared `get_session()`. The pool returned to full
idle capacity, a later transaction succeeded, and the connection killed during
the termination test was replaced. No fault injection left a poisoned session
or a committed partial mutation.

# Tenant Context Results

All three prototype tables used forced RLS under a restricted application role.
Tenant A could not read Tenant B's counter and Tenant B could not read Tenant
A's. A no-tenant context read no rows. After connection reuse, the custom tenant
GUC was empty. Claim/reclaim connections explicitly received the selected
tenant, and stale credentials could not cross the RLS boundary.

This is a tenant-context sanity check. Principal provenance and delayed
reauthorization remain explicitly deferred.

# Performance Sanity

This was a pathology check, not a benchmark. In one local evidence run:

| Transaction | Samples | Median ms | Max ms |
| --- | ---: | ---: | ---: |
| Claim | 8 | 17.950 | 19.194 |
| Heartbeat | 8 | 17.232 | 17.642 |
| Fence validation plus atomic completion | 8 | 3.264 | 4.614 |
| Reclaim | 1 | 25.709 | 25.709 |

The claim and heartbeat figures include opening and closing an independent
connection, so they are not pool-throughput claims. No correctness-critical
transaction held a lock across external work.

# Required Future Executor Constraints

An action may be classified `postgres_atomic` only when all of these are true:

1. Operation tables and application rows use the same Aksara Database instance
   and same PostgreSQL database.
2. The executor opens one outer Aksara transaction and verifies the expected
   active session/connection.
3. It locks the Operation row before the mutation.
4. Under that lock it validates current Operation, Attempt, worker, fence,
   running state, lease, cancellation/deadline, approval binding, tenant, and
   freshly resolved authorization as required by the eventual design.
5. Every application write goes through the pinned session. Direct pool access,
   independent connections/commits, subprocess database writes, and concurrent
   use of the inherited connection are prohibited.
6. Attempt success, Operation success/result, transition, and audit outbox are
   written before the same commit.
7. Any failed ownership/finalization predicate raises and aborts the whole
   transaction.
8. Nested savepoint exceptions that invalidate execution are not swallowed.
9. No external side effect is included in the PostgreSQL atomic guarantee.
10. An ambiguous commit outcome triggers an authoritative PostgreSQL read before
    retry or reclaim logic.

The production implementation should make these constraints enforceable and
testable. Documentation alone is too weak for an atomicity classification.

# Contradictions With ADR 0001

**NONE.**

The experiment confirms the ADR's stated conditional guarantee and its warning
that an executor must participate in the Operation transaction. It also
confirms the ADR's N/N+1 row-locking argument.

# Risks Discovered

- Aksara currently exposes `Database.pool`; code can bypass session reuse.
- The session `ContextVar` carries a connection, but no metadata proves which
  Database or executor boundary owns it.
- asyncio child tasks inherit ContextVars. Concurrent database work on one
  asyncpg connection is invalid even though each child sees the session.
- Nested savepoint errors can be caught while the outer transaction commits.
  Executor exception policy matters.
- Final production helpers must condition every authoritative write, including
  heartbeat and progress, on full ownership identity.
- Exact commit-ack packet loss needs a network-level integration environment;
  the deterministic test covers the authoritative reread rule.
- A broad promise covering arbitrary user code would be false. Eligibility must
  be narrow and allowlisted.

# What This Prototype Does NOT Prove

It does not prove or implement the final Operation/Attempt schema, migrations,
repositories, public API, transition/outbox retention, idempotency admission,
Principal provenance, current reauthorization, approval decisions, durable
cancellation, task integration, MCP Tasks, external-effect reconciliation,
packaged-wheel behavior, multi-host performance, or production observability.

It does not prove exactly-once external effects. It does not exhaust every ORM,
relation, bulk, generated API, raw SQL, or application-defined code path. It
does not inject literal network packet loss during commit. It does not validate
planner, Studio, memory, workflow, or multi-agent behavior.

# Recommendation

**PROVEN WITH REQUIRED IMPLEMENTATION CONSTRAINTS.**

The architecture is ready for a separately reviewed first production milestone
limited to versioned internal migrations and repositories for Operation,
Attempt, transition/outbox, idempotency identity, and optional approval-decision
storage. That milestone should include upgrade/replay, restricted-role DML,
invalid-transition, concurrency, and repository transaction tests.

It should still defer public REST/Python APIs, task and MCP integration, durable
dispatch, external-effect adapters, application approval workflow, retention
productization, planner/Studio/memory work, and broad executor registration.

# Invariant Matrix

| Scenario | Application mutation | Operation state | Attempt state | Current fence | Expected | Pass? |
| --- | ---: | --- | --- | ---: | --- | --- |
| Normal success | 1 | succeeded | succeeded | 1 | All commit together | Yes |
| Failure before mutation | 0 | running | running | 1 | No success truth | Yes |
| Failure after mutation statement | 0 | running | running | 1 | Entire transaction rolls back | Yes |
| Failure after Attempt update | 0 | running | running | 1 | Attempt success also rolls back | Yes |
| Failure after Operation update | 0 | running | running | 1 | Precommit success writes roll back | Yes |
| Cancellation | 0 | running | running | 1 | Mutation and success roll back | Yes |
| Real database CHECK error | 0 | running | running | 1 | PostgreSQL aborts boundary | Yes |
| Commit response lost simulation | 1 | succeeded | succeeded | 1 | Fresh read resolves committed truth | Yes |
| A claim | 0 | running | A running | 1 | A is sole owner | Yes |
| B claim race | 0 | running | one winner running | 1 | Exactly one owner/Attempt | Yes |
| A lease expiry before reclaim | 0 | running | A running | 1 | Expiry alone does not rewrite state | Yes |
| B reclaim | 0 | running | A abandoned; B running | 2 | Transfer is atomic and monotonic | Yes |
| Stale A heartbeat | 0 | running, B current | A abandoned; B running | 2 | Zero rows updated | Yes |
| Stale A mutation | 0 | running, B current | A abandoned; B running | 2 | Ownership fails before mutation | Yes |
| Stale A finalization | 0 | running, B current | A abandoned; B running | 2 | Zero rows updated | Yes |
| B valid mutation | 1 | succeeded | A abandoned; B succeeded | 2 | B commits exactly once | Yes |
| Connection loss before commit | 0 | running | running | 1 | Partial work rolls back | Yes |
| Pool reuse after failures | unchanged | unchanged | unchanged | unchanged | Capacity and clean session return | Yes |

# Required Negative Controls

| Deliberately broken design | Observed defect | Harness response |
| --- | --- | --- |
| Split application and Operation commits | Counter 1 while Operation/Attempt running | Detected |
| Application uses independent connection | Escaped mutation survives outer rollback | Detected |
| Operation/Attempt success commits without mutation | Success truth with counter 0 | Detected |
| Finalization-only fence check | Stale mutation commits; finalization updates zero rows | Detected |
| Removed fence/current-Attempt condition | Stale A mutates while B owns N+1 | Detected |
| Heartbeat ignores Attempt identity | Stale request extends B's current lease | Detected |
| Reclaim does not increment fence | New candidate fence is not greater than N | Detected |

# Answers to Required Questions

1. **Does current `transaction.atomic()` support atomic mutation plus Operation
   completion?** Yes, when every write uses the one pinned Aksara connection and
   transaction.
2. **What constraints are necessary?** The ten constraints in “Required Future
   Executor Constraints,” especially same database, pinned session, ownership
   lock/check before mutation, one commit, and no escape or external effect.
3. **Can a common ORM path escape?** The tested Model, Manager, QuerySet, and
   Database paths did not. Direct pool/raw/independent connection use can escape.
4. **What if commit succeeds but acknowledgement is lost?** Treat the local
   outcome as ambiguous, reconnect, and read the Operation before retrying.
5. **Can stale A mutate after B owns N+1?** Not through the correct boundary; A
   fails ownership validation before application mutation.
6. **Where is the fence checked?** On the locked Operation row inside the same
   outer transaction, before application SQL, alongside current Attempt,
   worker, running state, and lease.
7. **What if the lease expires while A holds the row lock?** B waits. A's commit
   wins and prevents reclaim, or A rolls back and B then reclaims.
8. **Does the design depend on worker clocks?** No. Claim, expiry, heartbeat,
   and reclaim use PostgreSQL `clock_timestamp()`.
9. **Did fault injection leak pool/session state?** No leak was observed; the
   pool returned to idle capacity and later queries succeeded.
10. **Did tenant context remain safe?** Yes in the restricted-role forced-RLS
    sanity test; reused connections cleared the tenant GUC.
11. **Did negative controls detect broken designs?** Yes, including all three
    required controls and three additional escape/identity controls.
12. **Did evidence contradict ADR 0001?** No.
13. **Is the architecture ready for the first production milestone?** Yes, with
    the required constraints treated as acceptance criteria.
14. **What should that milestone implement and defer?** Implement versioned
    internal migrations/repositories for Operation, Attempt, transition/outbox,
    idempotency identity, and optional approval decisions. Defer public APIs,
    integration, durable dispatch, external adapters, application workflows,
    retention productization, and AI/Studio work.
