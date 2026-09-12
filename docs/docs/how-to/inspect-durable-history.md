# Inspect an Operation and its recent history

**Stable bounded surface:** `DurableOperationService.get()` reads current
Operation state; `history()` reads retained transition records. History is
diagnostic evidence, not an event log used to rebuild the Operation and not a
tamper-resistant compliance ledger.

Use your existing application service from the
[durable tutorial](../tutorials/ticket-desk-durable.md). Obtain the viewer's
current Principal and tenant from authenticated server-side context. The helper
below does not authenticate a request or define an HTTP endpoint.

```python title="app/operation_history.py"
from uuid import UUID

from aksara.durable import DurableOperationService
from aksara.security.principal import Principal


async def inspect_operation(
    service: DurableOperationService,
    operation_id: UUID,
    *,
    tenant_id: str | None,
    viewer: Principal,
    limit: int = 50,
):
    operation = await service.get(
        operation_id, tenant_id=tenant_id, principal=viewer
    )
    transitions = await service.history(
        operation_id, tenant_id=tenant_id, principal=viewer, limit=limit
    )
    return {
        "operation_id": str(operation.id),
        "state": operation.state.value,
        "recent_transitions": [
            {
                "state_version": item.state_version,
                "from_state": item.from_state.value if item.from_state else None,
                "event": item.event,
                "to_state": item.to_state.value,
                "reason_code": item.reason_code,
                "attempt_id": str(item.attempt_id) if item.attempt_id else None,
                "created_at": item.created_at.isoformat(),
            }
            for item in transitions
        ],
    }
```

The projection intentionally omits command, result, error-message and arbitrary
metadata bodies. Choose what your own viewers should see; serialized UUIDs
and timestamps do not themselves make information safe to disclose.

## Read the result correctly

`history()` defaults to 50 records and accepts limits from 1 through 200.
It returns the newest transition first, ordered by the stored transition ID.
The initial transition can have `from_state=None`. The helper converts enums,
UUIDs and timestamps into JSON-friendly values without exposing raw rows.

There is no cursor/offset argument on this service method. A full page does not
prove you obtained the entire history. Do not build a loop that repeatedly
requests the same 200 records and calls that complete pagination. If you need
long-term event export, use the
[outbox exporter](export-durable-transitions.md) and an application-owned sink.

The two reads in this helper are separate database operations. A worker can
advance the Operation between them; the state and recent transitions are not
one atomic snapshot. Refresh when investigating an active Operation. Use the
Operation's current authoritative state for decisions rather than inferring it
from a possibly truncated history list.

## Understand access and retention

The service restricts lookup to its application namespace and the supplied
tenant. `None` selects the non-tenant scope; it is not an all-tenant query.
Missing or differently scoped Operations raise `OperationNotFound`.
Authentication/tenant/policy failures can raise `AuthorizationDenied`.
An invalid history limit raises `ValueError`.

While an action is registered, reads apply its current action policy and
requester authorizer. A retained terminal Operation whose action/version has
been unregistered remains readable after authentication and tenant checks;
the removed action's scope and custom policy are not executed. If your product
requires owner-only or other stricter access after retiring action code,
enforce that policy in your application before calling this helper. Do not
assume a stored requester identity automatically imposes owner-only reads.

Retention can remove old terminal Operations and their history. Results/errors
may expire sooner. Aksara does not supply your organization's audit retention,
backup, redaction, legal hold or remote sink durability policy. Synchronous MCP
audit events are another surface; this history is not a merged audit stream of
all REST, MCP and background activity.

For outcome interpretation, see
[approval decisions](require-durable-approval.md),
[external uncertainty](handle-external-effects.md), and the
[durable reference](../advanced/durable-operations.md#history-export-and-retention).
