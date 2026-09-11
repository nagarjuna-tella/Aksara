# ModelViewSet and generated routes

**Stable within the documented generated API contract.** A `ModelViewSet`
connects a model to CRUD handlers, validation, permissions, and policy. Defining
a subclass alone is not route registration. Register it with
`include_viewset(app_or_router, YourViewSet)` or the documented application
registration flow.

Follow the [ticket-desk tutorial](../getting-started/first-project.md) for a
complete model, migration, authentication adapter, and route registration.
The [next chapter](../tutorials/ticket-desk.md) adds relationships and serializer
validation to that same application.

## Minimal protected ViewSet

In that project, `app/views.py` can contain:

```python title="app/views.py"
from aksara import ModelViewSet
from aksara.permissions import IsAuthenticated
from .models import Ticket


class TicketViewSet(ModelViewSet):
    model = Ticket
    prefix = "/api/tickets"
    permission_classes = [IsAuthenticated]
    ai_exposed = False
    stream_enabled = False
```

This requires the server-side identity adapter from the tutorial. Permissions
do not authenticate a bearer token themselves. Setting `ai_exposed = False`
and `stream_enabled = False` deliberately keeps this learning example focused
on ordinary HTTP CRUD; these are explicit example settings, not framework defaults.

## Generated HTTP contract

For the prefix above, `include_viewset` registers:

| Method | Path | Handler | Successful response |
|---|---|---|---|
| GET | `/api/tickets/` | `list` | 200, paginated results |
| POST | `/api/tickets/` | `create` | 201, created record |
| GET | `/api/tickets/{pk}` | `retrieve` | 200, record |
| PATCH | `/api/tickets/{pk}` | `update` | 200, updated record |
| DELETE | `/api/tickets/{pk}` | `delete` | 200, deletion confirmation |

Collection routes end in `/`; detail routes do not. The generated update method
is PATCH, not PUT, and the delete handler is `delete`, not DRF's `destroy`.
Server redirect behavior should not be confused with the registered paths.

When `stream_enabled` is true (the default), registration also adds
`GET /api/tickets/stream`. This is an SSE lifecycle-event surface. Its permission
and tenant requirements deserve a separate review; it is not a durable event
log or a substitute for outbox retention.

## Configuration that the implementation reads

| Attribute | Purpose / default |
|---|---|
| `model` | Required model class |
| `prefix` | URL prefix; empty defaults to the model table name with a leading `/` |
| `tags` | OpenAPI tags; defaults to the model class name |
| `lookup_field` | Detail lookup field; default `id` |
| `permission_classes` | Permission classes or instances; default empty list |
| `ai_exposed` | AI access setting; default true, subject to other exposure and authorization controls |
| `stream_enabled` | Register the SSE route; default true |
| `default_limit`, `max_limit` | Generated limit/offset pagination defaults: 20 and 100 |
| `pagination_class` | Optional paginator |
| `filter_backends` | Explicit filter backend classes; default empty list |
| `search_fields`, `ordering_fields`, `ordering` | Configuration consumed by the relevant filter backends |
| `list_serializer_class`, `retrieve_serializer_class` | Response serializers for the named operations |
| `create_serializer_class`, `update_serializer_class` | Write serializers for the named operations |
| `create_schema_class`, `update_schema_class`, `read_schema_class` | Optional Pydantic schema overrides |

`serializer_class`, `authentication_classes`, `queryset`, `filterset_fields`,
`page_size`, `max_page_size`, `allowed_actions`, and `excluded_actions` are not
implemented configuration switches on this class in 0.7.0. Assigning such an
attribute in Python can succeed while having no effect. In particular, do not
use `allowed_actions` as a security control or assume `serializer_class` installs
validation.

Use operation-specific serializer attributes. The
[serializer tutorial](../tutorials/ticket-desk.md) demonstrates
`create_serializer_class` and preserves omitted fields during partial updates.
A custom serializer and the generated route's Pydantic response schema must
agree; returning extra fields does not automatically change OpenAPI or the
response model.

## Restrict operations and filtering

Use [permissions](permissions.md) to deny unsupported operations. For example,
`OperationPermission(allow=["read"])` permits safe HTTP methods; combine it with
identity requirements when reads are private. This denies writes at execution
time but does not remove their registered routes. To publish only a selected
set of routes, define application-owned endpoints with explicit authorization.

Override `get_filter_fields()` to choose which model fields clients may filter.
The default exposes model field names to filter extraction. Install appropriate
`filter_backends` when using search and ordering; assigning `search_fields` alone
does not install a search backend.

`get_queryset(request=None, **filters)` is synchronous and controls **list**
queries. Call the base implementation to preserve required policy filters before
adding application restrictions or ORM query optimization. It is not the lookup
path for every detail operation, and an owner-filtered list does not prove that
a guessed detail URL is protected. Use object permission and the documented
tenant/RLS boundary too.

## Customize handlers without losing checks

The async handler signatures are:

- `list(request, limit=20, offset=0, **filters)`
- `retrieve(pk, request)`
- `create(data, request)`
- `update(pk, data, request)`
- `delete(pk, request)`

Preserve these arguments when overriding a handler and delegate to `super()`
where the standard behavior remains appropriate. Replacing the handler body
means owning the checks and persistence it previously performed. There is no
`get_request_data()` convenience method or automatically populated `self.action`
attribute matching the older examples on this page.

Permission hooks are synchronous. Custom `@action` methods have their own
request and path-parameter contract and can override permission classes. See
[custom actions](actions.md), and retain every prerequisite permission
when replacing the ViewSet's permission list.

## Errors and execution boundaries

Generated permission denials are HTTP 403. Route input validation and Aksara
`ValidationError` map to 422; their detail shapes are not identical. Missing
records return 404, invalid detail identifiers can return 400, uniqueness
violations map to 409, and foreign-key violations map to 400. Database errors
map to 500. Application exceptions outside these mappings are not automatically
converted into validation errors.

Generated REST and MCP share important execution checks, including policy and
field restrictions. A direct ORM call or arbitrary custom endpoint does not
inherit that whole boundary merely because its model also has a ViewSet.
Use [authentication](authentication.md), [permissions](permissions.md),
[tenant isolation](../tutorials/ticket-desk-tenancy.md), and
[MCP execution](../tutorials/ticket-desk-mcp.md) together when exposing data-changing
operations.
