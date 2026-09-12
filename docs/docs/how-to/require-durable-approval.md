# Require approval for a durable action

**Stable boundary:** a durable approval records a decision for one logical
Operation. It does not grant the requester new permissions. Your application
owns the review screen, notifications and who may approve.

Start with the [Ticket Desk durable tutorial](../tutorials/ticket-desk-durable.md)
for migrations, admission, a current-identity resolver and worker setup. This
helper adds a decision boundary to an application that already has those parts.
It does not install an HTTP endpoint or authenticate requests.

## Register an approval-required action

Keep the action name, version, handler, effect class and requester authorization
from your existing action registration. Set `approval_required=True` and add
an `approval_authorizer` that checks the current approver. For example, the
function below requires your application's `ticket-reviewer` role. The service
also checks authentication, tenant and the action's required scopes through
PolicyEngine; the role check does not replace those checks.

```python title="app/approval_decisions.py"
from uuid import UUID

from aksara.durable import DurableOperationService, PrincipalReference
from aksara.security.principal import Principal


def can_review_ticket(principal: Principal, command) -> bool:
    return principal.has_role("ticket-reviewer")


async def decide_ticket(
    service: DurableOperationService,
    operation_id: UUID,
    *,
    tenant_id: str,
    current_approver: Principal,
    approver_reference: PrincipalReference,
    approve: bool,
    reason: str | None = None,
):
    return await service.decide_approval(
        operation_id,
        tenant_id=tenant_id,
        approver=current_approver,
        approver_reference=approver_reference,
        approve=approve,
        reason=reason,
    )
```

Use `approval_authorizer=can_review_ticket` in the `DurableAction` constructor.
This callback receives the stored command, so you can add command-specific
business rules. It is separate from the action's requester `authorizer`.
A reviewer must still possess any action-level required scopes.

## Admit, review and run

1. Authorize admission using your application's current requester identity,
   then admit the registered action with a server-created requester reference.
   Its initial state is `waiting_for_approval`; workers cannot claim it yet.
2. Load the current approver from your authenticated identity store at decision
   time. Build the approver reference on the server for that same identity.
   Never accept a Principal, roles, scopes or reference from a request body.
   Select the tenant from the authenticated application context.
3. Call `decide_ticket` with the Operation ID, the current identity and its
   matching reference. Inspect the returned Operation state.
4. An accepted approval moves the Operation to `ready`. The normal worker can
   claim it, resolve the requester again and check current execution authority.
   Revoking the requester's access still prevents execution after approval.

A reference identifies whose decision is being recorded; it is not an
authentication credential. The service rejects mismatched principal/reference
provenance. Its application namespace and explicit tenant constrain lookup;
a wrong scope cannot select an Operation in another tenant or namespace.

This example does not enforce separation of duties or multiple reviewers.
Add those business policies explicitly if required. Do not assume a reviewer
role automatically prohibits someone from approving their own request.

## Handle outcomes honestly

| Outcome | Meaning and application response |
| --- | --- |
| `ready` | Approval accepted; execution has not succeeded yet. |
| `cancelled` | Rejection accepted. Show the rejected decision, not a failed handler. |
| `expired` | The approval window or Operation deadline elapsed; approval did not make it runnable. |
| `AuthorizationDenied` | Current identity, tenant, policy, scope or reviewer checks failed. |
| `OperationNotFound` | No Operation is visible in this service namespace and tenant. |
| `ApprovalConflict` | It is no longer waiting, the active decision is missing, or its immutable binding does not match. Refresh status; do not overwrite the winner. |

Set `approval_expires_at` at admission when your business process needs an
explicit window; use a timezone-aware timestamp. Deadline and approval expiry
are checked using database time. A decision can return `expired` rather than
raise, so a successful function call is not sufficient evidence of approval.

The first successful claim consumes the approval for this logical Operation.
A replacement worker does not need a second decision for that same approved
work. Concurrent approve/reject requests have one winner; repeated decisions
are not a generic idempotent success response. If a response is lost, read the
current authorized status/history before deciding what to show or retry.

Reasons are stored with a 1,000-character limit. Keep credentials and unnecessary
personal information out of them. Application retention and access controls
still apply. For history and cancellation semantics, see the
[durable reference](../advanced/durable-operations.md#approval-and-cancellation).
These decisions are distinct from signed synchronous MCP approval grants;
do not reuse an MCP grant as a durable approval record.
