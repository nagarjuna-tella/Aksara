# Custom ViewSet actions

`@action` registers an additional HTTP endpoint when its ViewSet is included.
A detail action uses `{pk}`; a collection action does not. It does not create a
`get_object()` or `get_request_data()` helper.

!!! warning "Explicit HTTP authorization required in 0.7.0"
    Custom HTTP actions are registered as bound methods. Unlike generated CRUD
    handlers, they do not automatically run ViewSet or decorator permission
    checks. A local installed-wheel probe returned 200 from an anonymous custom
    action declaring `IsAuthenticated`, while the generated list returned 403.
    Put the required checks in the handler or delegate to a checked CRUD method.
    This limitation is recorded for a separate runtime patch; this documentation
    release does not change it.

## A checked detail action

In the [ticket-desk application](../getting-started/first-project.md), this action
returns a summary after the standard retrieve path performs its checks:

```python title="app/views.py"
from starlette.requests import Request
from aksara import ModelViewSet
from aksara.api import action
from aksara.permissions import IsAuthenticated
from .models import Ticket


class TicketViewSet(ModelViewSet):
    model = Ticket
    prefix = "/api/tickets"
    permission_classes = [IsAuthenticated]
    ai_exposed = False
    stream_enabled = False

    @action(detail=True, methods=["GET"], path="summary", ai_exposed=False)
    async def summary(self, pk: str, request: Request):
        record = await self.retrieve(pk=pk, request=request)
        return {"id": record["id"], "subject": record["subject"]}
```

Register the ViewSet through the tutorial's `include_viewset` flow. The added
path is `GET /api/tickets/{pk}/summary`, without a trailing slash. The handler
receives `pk`, matching the generated path parameter. A parameter named `id`
does not automatically rename that path parameter.

The example delegates to `retrieve`, so it uses the ViewSet's permission list.
For other handlers, call the relevant view and object checks explicitly and
establish the application's tenant and policy boundary. `self.check_permissions`
uses the ViewSet list; it does not inspect an action's decorator override.

## Decorator arguments

| Argument | Contract |
|---|---|
| `detail` | Required boolean: detail or collection route |
| `methods` | Required list of HTTP method names; normalized to uppercase |
| `path` | Optional route segment, default method name |
| `name` | Optional route name, default method name |
| `summary`, `description` | Optional OpenAPI text; otherwise derived from the docstring |
| `permission_classes` | Action permission metadata used by generated tool execution; not automatic HTTP enforcement |
| `ai_exposed` | Action exposure metadata, default true; other ViewSet/model/registration conditions still apply |
| `requires_approval` | MCP signed approval-grant requirement, default false; not an HTTP approval workflow |

The keywords are `path` and `name`, not `url_path` and `url_name`. There is no
implicit default GET method when `methods` is omitted.

## Inputs, writes, and transactions

FastAPI inspects the bound method signature. Annotate `request` as `Request`
and define typed body/query parameters for your actual endpoint. A docstring
is not input validation. For writes, validate fields and related objects, apply
current authority and tenant rules, and use a transaction for database changes
that must commit together.

Do not perform a direct ORM update and assume the action decorator applies all
CRUD field-write restrictions. Replacing a generated handler with application
code means owning those checks. A collection action also needs an explicit
query scope; object permission does not filter an entire list automatically.

## MCP is a separate execution path

Eligible custom actions can appear in generated MCP discovery when the model,
ViewSet, action, and application exposure settings permit it. Discovery is
permission-filtered, and the MCP executor performs its own execution-time
checks. Do not infer equivalent HTTP wrapping from MCP metadata.

`requires_approval=True` concerns signed, bounded MCP grants. It neither stores
a durable approval workflow nor automatically gates direct HTTP calls. For
work that must survive approval delay and worker loss, use
[Durable Operations](../advanced/durable-operations.md).

Start with the [official MCP client tutorial](../tutorials/ticket-desk-mcp.md)
for authenticated tool execution and the
[permissions guide](permissions.md) for synchronous application checks.
