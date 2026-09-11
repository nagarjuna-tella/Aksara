# API Reference

The API reference is organized by the public component you are configuring.
The linked guides describe installed behavior and include the supported
signatures, defaults, and limits. For a complete runnable application, start with
the [first project](../getting-started/first-project.md).

## ViewSets

Use [`ModelViewSet`](../api/viewsets.md) and `include_viewset(app, ViewSetClass)`
for generated CRUD. The guide lists the five CRUD routes, operation-specific
serializer attributes, synchronous queryset hook, and registration example.
Do not assume Django REST Framework attributes or lifecycle hooks exist because
the class names look familiar. There is no generated PUT route or supported
`serializer_class` switch.

## Actions

[`@action`](../api/actions.md) declares a custom method's route and metadata.
`detail` and `methods` are required; the route options are `path` and `name`.
Custom HTTP handlers must explicitly enforce authorization: neither ViewSet
permissions nor decorator permission metadata automatically wrap the handler
in v0.7.0. MCP execution checks are a separate path.

## Serializers

[`ModelSerializer`](../api/serializers.md) derives model input and output schemas.
Its constructor accepts `instance`, `data`, `many`, and `context`. Validation
hooks are synchronous. The guide documents `Meta` options, validation errors,
read-only input behavior, relation expansion, and update limits. DRF's
`partial=True`, `SerializerMethodField`, and `extra_kwargs` are not supported
contracts here.

## Permissions

[Permission classes](../api/permissions.md) implement synchronous
`has_permission(request, view)` and
`has_object_permission(request, view, obj)` hooks. The guide distinguishes
view checks, object checks, list filtering, and the custom HTTP action boundary.

## Authentication

[Authentication helpers](../api/authentication.md) provide account, password,
session, and dependency primitives. Applications own credential verification,
login endpoints, and attaching trusted request identity. There is no automatic
DRF authentication-class configuration.

## Pagination

Start with the [ViewSet pagination defaults](../api/viewsets.md) for generated
list behavior. Do not assume importing a pagination class changes an existing
route's response shape; configure and test the route you expose.

## Filtering

See [ViewSet filtering and queryset customization](../api/viewsets.md).
Filtering must be explicitly configured through supported hooks/backends.
It is separate from authorization and does not replace tenant isolation.

## Routing

[Routing](../api/routing.md) covers registration. The checked minimal registration
example is in [ViewSets](../api/viewsets.md). Custom FastAPI routes remain
application-owned handlers with application-owned authorization.

## Request & Response

HTTP handlers use FastAPI/Starlette request and response conventions.
Use `await request.json()` to read a JSON body, rather than a DRF-style
`request.data`. For custom status codes, return an explicit response or configure
the route; returning a `(body, status)` tuple is not a status-setting contract.
See the [generated routes and status codes](../api/viewsets.md) and
[serializer validation errors](../api/serializers.md).

## Throttling

[Throttling](../api/throttling.md) describes the available rate-limit integration.
Rate limits do not replace identity, permissions, or object-level policy.

## Next steps

The [API overview](../api/index.md) explains how these pieces fit together.
The [ticket desk tutorial](../tutorials/ticket-desk.md) provides the executable
path through validation and relationships; subsequent chapters cover tenant
isolation, background work, durable operations, and optional MCP access.
