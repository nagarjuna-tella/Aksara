# Permissions

**Stable within the generated API and policy contracts.** Permission classes
check whether a request or an object operation is allowed. They consume trusted
identity attached by your [authentication adapter](authentication.md); they do
not validate passwords, tokens, or tenant membership by themselves.

For a runnable application, follow the
[ticket-desk permission and tenancy chapter](../tutorials/ticket-desk-tenancy.md).
It tests allowed and denied calls through real HTTP routes and PostgreSQL RLS.

## Choose a view-level permission

Set `permission_classes` on a `ModelViewSet` explicitly. The default list is
empty, but that is not a promise of unrestricted generated writes: PolicyEngine
still applies. `AllowAny` is the explicit public route-level permission and does
not disable field or tenant restrictions.

| Permission | View-level behavior |
|---|---|
| `AllowAny` | Grants this permission check |
| `IsAuthenticated` | Requires an attached user with `is_authenticated` true |
| `IsActiveUser` | Requires an authenticated user whose `is_active` is true (defaults true if absent) |
| `IsAdminUser` | Requires `is_staff` or `is_superuser`; combine with `IsActiveUser` when active status matters |
| `IsOwnerOrReadOnly` | Grants the view check; restricts unsafe object operations to a matching owner field |
| `DenyAI` | Rejects trusted server-side AI request state; client headers do not decide this |
| `OperationPermission(allow=[...])` | Maps HTTP methods to `create`, `read`, `update`, or `delete` |

`IsOwnerOrReadOnly` checks the first populated field among `user_id`, `owner_id`,
`author_id`, and `created_by`. It does not filter list rows, set an owner during
creation, or require authentication by itself. Use an explicit application
permission when your ownership rules differ.

## Write synchronous permission hooks

`has_permission(request, view)` and
`has_object_permission(request, view, obj)` are **synchronous** boolean methods.
`ModelViewSet` calls them directly; it does not await coroutines. Do not use
`async def` for these hooks. Resolve any asynchronous membership information in
your trusted request adapter or another supported application boundary first.

Here is an application-owned permission for an object with `owner_id`. Save it
as `app/permissions.py` if that is your model's ownership field:

```python title="app/permissions.py"
from aksara.permissions import BasePermission


class IsActiveOwner(BasePermission):
    message = "An active owner is required."

    def has_permission(self, request, view=None):
        user = self.get_user(request)
        return bool(
            user is not None
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
        )

    def has_object_permission(self, request, view, obj):
        if not self.has_permission(request, view):
            return False
        owner_id = getattr(obj, "owner_id", None)
        user_id = getattr(self.get_user(request), "id", None)
        return (
            owner_id is not None
            and user_id is not None
            and str(owner_id) == str(user_id)
        )
```

Use `permission_classes = [IsActiveOwner]` on the relevant ViewSet. This
permission deliberately checks both identity and ownership for object calls.
It is not a complete multi-tenant application policy.

## Separate list, create, and object rules

View-level permission runs before the operation. Object permission runs when a
ViewSet retrieves an object for a detail operation; it does not automatically
filter every row in a list. Apply your ownership/list scope in the query path,
and keep required tenant filters intact.

Creation has no existing object to check. Assign or validate ownership on the
server, make owner/tenant fields non-writable where appropriate, and reject
foreign related objects. A client-supplied owner field must not grant ownership.
The [tenancy tutorial](../tutorials/ticket-desk-tenancy.md) shows these separate
checks for related records and read-only fields.

Do not rely on a DRF-style `self.action` attribute: generated Aksara routes do
not set it as shown in older examples. For HTTP-method rules, inspect the request
in `has_permission` or use `OperationPermission`. For a custom action, the
`@action` decorator accepts `permission_classes`; its override replaces the
ViewSet list, so include every prerequisite permission needed by that action.

## Combine checks deliberately

Multiple entries in `permission_classes` must all pass. Permission instances
also support `&` and `|`:

```python
from aksara.permissions import IsActiveUser, IsAdminUser

active_admin = IsActiveUser() & IsAdminUser()
```

Use instances for composition, not class-level operators. Test both view and
object decisions for an OR expression: each phase evaluates its own checks,
and a permission's default object check grants access. An expression that looks
like “admin or owner” is not sufficient evidence of the intended whole-request
policy. A single explicit permission is often easier to review.

## Denials and policy

A failed `ModelViewSet` permission hook raises HTTP 403 with the permission's
`message` as the `detail`. Authentication dependencies can instead return 401;
other validation or lookup failures have their own response contracts.

Permission success does not disable PolicyEngine. Generated REST and MCP also
apply execution-time policy, field writability/visibility rules, and tenant
constraints. Your direct ORM scripts and custom endpoints must deliberately
establish equivalent boundaries; merely importing a permission class does not
install enforcement there.

For tools, see [MCP execution](../tutorials/ticket-desk-mcp.md). For delayed work,
see [Durable Operations](../advanced/durable-operations.md): admission permission
and later reauthorization are distinct checks, and approval is not a substitute
for current authority.
