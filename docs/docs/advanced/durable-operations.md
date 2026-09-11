# Durable Authorized Operations

Aksara durable operations preserve an accepted application command and its
authoritative execution state in PostgreSQL. Use them when work must survive a
lost HTTP response, application restart, worker replacement, approval delay,
or retry. They are opt-in: existing generated REST routes, MCP tools, and
background tasks remain synchronous or task-only unless the application
registers and dispatches a durable action.

Ordinary synchronous REST or MCP remains the simpler choice when the caller can
wait for the result and request loss does not require restart-safe recovery.
Durable operations are an application execution primitive; they do not require
an LLM, planner, Studio, or agent.

For complete runnable files, continue the
[ticket-desk durable tutorial](../tutorials/ticket-desk-durable.md). It mounts the
router on the application's database, supplies a current identity resolver,
checks admission permissions, and tests retry, rollback, cancellation and
revocation with an installed package. The snippets below explain individual
integration points; `identity_store` represents your application's identity source.

## Operation and Attempt

An **Operation** is one logical request. Its opaque ID, state, result or error,
cancellation intent, deadline, attempt limit, and retention timestamps are the
PostgreSQL source of truth.

An **Attempt** is one physical claim by a worker. Each claim gets a new attempt
ID, ordinal, lease, and monotonically increasing fence. When a lease expires,
a replacement records the old attempt as abandoned and claims a higher fence.
The stale worker cannot heartbeat, mutate through the guarded PostgreSQL
boundary, or finalize after ownership advances.

The public operation representation intentionally omits command storage,
principal provenance, worker IDs, fence values, raw transition rows, resolver
details, and physical table names.

## Register an action

Applications register exact action name and semantic-version pairs in code.
Persisted commands cannot select Python imports, arbitrary functions, SQL, or
shell commands.

```python
import os
from uuid import UUID

from aksara.db import Database
from aksara.durable import (
    DurableAction,
    DurableActionRegistry,
    DurableOperationService,
    EffectClass,
    PrincipalResolution,
    PrincipalResolverRegistry,
)
from aksara.security.principal import Principal


database = Database(os.environ["DATABASE_URL"])


async def resolve_ticket(context, command):
    ticket_id = UUID(command["ticket_id"])
    await context.database.execute(
        """
        UPDATE support_tickets
        SET status = 'resolved', updated_at = clock_timestamp()
        WHERE id = $1 AND tenant_id = $2
        """,
        ticket_id,
        context.tenant_id,
    )
    return {"ticket_id": str(ticket_id), "status": "resolved"}


actions = DurableActionRegistry()
actions.register(
    DurableAction(
        name="support.ticket.resolve",
        version="1",
        handler=resolve_ticket,
        effect_class=EffectClass.POSTGRES_ATOMIC,
        required_scopes=("ticket:resolve",),
    )
)

resolvers = PrincipalResolverRegistry()


async def resolve_current_identity(reference):
    principal = await identity_store.current_principal(reference.subject_id)
    return PrincipalResolution.resolved(principal)


resolvers.register("support-identity", "1", resolve_current_identity)

operations = DurableOperationService(
    database,
    application_namespace="support-desk",
    actions=actions,
    resolvers=resolvers,
)
```

The resolver must rebuild the current `Principal`. The durable principal
reference is only a non-secret locator. Do not persist bearer tokens, API keys,
cookies, refresh tokens, signed approval grants, or admission-time roles and
scopes as authority.

Before every supported side-effect boundary, Aksara resolves that reference
and reapplies current identity, scope, tenant, action authorization, and
`PolicyEngine` checks. The action's authorizer is where an application can
recheck object ownership, permission classes, field policy, and model rules.
PostgreSQL RLS remains the database isolation boundary in the production
profile. A delayed operation fails closed when current permission has been
revoked.

## Dispatch and status API

Mount the explicit router. It does not alter any generated synchronous route.
The router requires an authenticated Principal, but your application must also
restrict who may dispatch each command. `DurableOperationService.admit()` stores
validated input and provenance; it does not invoke the action authorizer as an
admission permission check. Use a router dependency or application endpoint to
apply the appropriate admission permission. The registered authorizer runs at
execution and on protected status/cancellation paths. The complete tutorial
shows both layers; accepting a command is not a claim it will remain authorized.

```python
from aksara.durable import PrincipalReference, create_durable_operations_router


async def principal_reference(principal, request):
    return PrincipalReference.from_principal(
        principal,
        resolver_key="support-identity",
        resolver_version="1",
        identity_namespace="support-desk",
    )


app.include_router(
    create_durable_operations_router(
        operations,
        principal_reference_factory=principal_reference,
    )
)
```

Dispatch a command with an application-chosen idempotency key:

```http
POST /durable/operations
Idempotency-Key: example
Content-Type: application/json

{
  "action": "support.ticket.resolve",
  "action_version": "1",
  "command": {"ticket_id": "018f4f31-4464-7e2e-a9e8-090f6a413c65"}
}
```

A new nonterminal operation returns `202 Accepted` and a `Location` header.
During the configured idempotency window:

- the same key, initiating principal, tenant, action version, and canonical
  input return the same Operation;
- a terminal duplicate returns the existing terminal representation;
- changed input or action version returns `409` with
  `idempotency_conflict`; and
- concurrent identical submissions create one logical Operation.

The idempotency value is hashed before storage. Its scope includes the
application namespace, tenant scope, stable initiating-principal reference,
action name and version, and canonical normalized input. Dedupe is bounded by
the configured window; it is not permanent.

Status retrieval, cancellation, and decisions reauthorize the current caller.
An unknown ID and an ID hidden by another tenant both return the same
`operation_not_found` response. Possessing an Operation ID grants no access.

## Run work

An application can poll one tenant explicitly:

```python
from aksara.durable import DurableOperationWorker

worker = DurableOperationWorker(
    operations,
    worker_id="support-worker-1",
    lease_seconds=30,
)

await worker.run(tenant_id=current_tenant_id)
```

Claims use PostgreSQL time, row locks, and `SKIP LOCKED`. A running worker must
finish within its lease or heartbeat through the service. Attempt limits,
deadlines, retry eligibility, cancellation, and approval state survive process
replacement.

Deployments must retain every action and resolver version referenced by a
nonterminal Operation. `check_durable_operations()` reports missing versions
as release-blocking rather than routing stored work to a newer handler.

#### `postgres_atomic` guarantee

`EffectClass.POSTGRES_ATOMIC` is the strongest contract. It applies only when:

- application data and operation state use the same Aksara `Database` and
  PostgreSQL database;
- the handler uses `context.database` in the owning asyncio task;
- Aksara locks and validates the Operation, Attempt, owner, fence, lease,
  cancellation, deadline, approval, and current authorization before the
  mutation; and
- application mutation, Attempt success, Operation success, result,
  transition, and outbox intent commit in one outer Aksara transaction.

Direct pool acquisition, another `Database`, an independent asyncpg
connection or commit, a subprocess/thread database write, concurrent child
task database work, and external network effects invalidate this guarantee.
The runtime mechanically rejects covered database escapes. Application action
registration remains a trusted boundary, so review each `postgres_atomic`
handler for unsupported side effects.

After an ambiguous local commit acknowledgement, reconnect and read the
Operation by its ID or resubmit the same idempotency identity. Never start a
blind replacement mutation. For a `postgres_atomic` Operation, `succeeded`
proves the application mutation and authoritative completion committed
together.

## Approval and cancellation

Set `approval_required=True` on an action to admit it in
`waiting_for_approval`. A durable decision binds to the exact Operation,
canonical input, action/version, tenant, requester, approver, and expiry. The
first successful claim consumes the decision for that logical Operation;
worker replacement does not ask a human to approve it again.

Approval records intent. Execution still resolves and authorizes the requester
again, so approval cannot restore revoked access. Aksara supplies the durable
decision substrate, while applications own approval inboxes, notifications,
escalation, and multi-approver business policy. Existing v0.6 signed
synchronous MCP approval grants remain unchanged.

Cancellation is also durable intent. It prevents a waiting or ready Operation
from starting. A running handler observes it at guarded boundaries. If the
same-database success transaction commits first, cancellation cannot undo the
committed mutation. For an external call already issued, cancellation is best
effort and never rewrites the outcome as though the provider action was undone.

## External effects

External systems cannot participate atomically in the PostgreSQL transaction.
Register the honest effect class:

- `external_idempotent`: the provider accepts the same stable downstream key;
- `external_at_least_once`: the adapter can reconcile before any repeat;
- `external_nonretryable`: no blind retry is allowed after an ambiguous send;
- `read_only`: no mutation is expected.

External actions use `ExternalEffectContext.perform()` so Aksara records an
operation-scoped intent and stable effect identity before the call. On
recovery, an idempotent provider receives the same key. A reconcilable adapter
checks the prior result before sending again. When neither idempotency nor
reconciliation can establish the truth, the Operation fails with
`external_outcome_unknown`. Aksara does not claim exactly-once external effects.

## Existing tasks

An action registered with `executor_type="task"` may use
`enqueue_operation_task()`. The task row schedules the work, while the
Operation Attempt, lease, and fence remain authoritative. Repeated enqueue for
the same Operation returns the linked task. Existing unlinked `@task` jobs,
task IDs, APIs, queues, retry behavior, and CLI remain compatible.

## History, export, and retention

Each authoritative state change writes a bounded transition and transactional
outbox intent. `DurableOutboxExporter` retries delivery to an application sink;
sink failure does not invalidate a committed Operation. The Operation row is
current truth. History is diagnostic evidence and is never replayed to rebuild
state.

`prune()` uses PostgreSQL time and bounded batches. It never removes active
work, does not permit unsafe key reuse inside the idempotency window, and may
expire result or error bodies before removing terminal Operation metadata.
Applications own long-term compliance retention.

Run the machine-readable preflight after migrations and for each application
namespace/tenant profile:

```python
from aksara.durable import check_durable_operations

report = await check_durable_operations(operations, tenant_id=tenant_id)
if not report.release_ready:
    raise RuntimeError(report.to_dict())
```

The v0.7 durable schema is installed by Aksara's internal migrations. Apply
migrations as a deployment step and grant the restricted application role DML
access to the migrated internal tables. Normal durable execution requires no
runtime DDL and no Redis, Kafka, Celery, Temporal, or other coordination
service.

## MCP status

Existing synchronous MCP tools continue over Streamable HTTP at `/mcp/` with
their v0.6 authorization, approval-grant, transaction, budget, and audit
contract. Protocol-level durable MCP Tasks are deferred because the official
MCP Python SDK used by this candidate does not yet implement the current
`io.modelcontextprotocol/tasks` extension. Aksara does not ship a competing
wire protocol.
