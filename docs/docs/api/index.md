# API Layer

**Stable surface, with documented limits.** Aksara generates HTTP endpoints from
models. A ViewSet selects the model and configures the generated handlers;
a serializer validates and represents model data; permissions decide whether a
request may proceed. Your application authenticates the caller and attaches the
server-owned identity before those checks run.

## Build your first API

Follow the [first project](../getting-started/first-project.md) to create a
PostgreSQL-backed ticket API, apply its migration, attach a local development
identity, and exercise authenticated requests. Continue with the
[ticket desk tutorial](../tutorials/ticket-desk.md) for relationships and custom
validation, then [tenant isolation](../tutorials/ticket-desk-tenancy.md).

These chapters grow one executable application. They include the configuration,
registration, database setup, and request headers needed to run the examples.

## Generated endpoints

For a ViewSet explicitly registered with `prefix = "/api/tickets"`, the standard
CRUD routes are:

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/tickets/` | List records |
| POST | `/api/tickets/` | Create a record; success is 201 |
| GET | `/api/tickets/{pk}` | Retrieve one record |
| PATCH | `/api/tickets/{pk}` | Update supplied fields |
| DELETE | `/api/tickets/{pk}` | Delete a record; success is 200 |

There is no generated PUT handler. Detail routes have no trailing slash.
A lifecycle-event stream is also registered at `/api/tickets/stream` unless
`stream_enabled = False`. The introductory tutorial disables that stream and
MCP exposure explicitly. Consult [ViewSets](viewsets.md) for checked registration
examples and the actual customization hooks.

## Choose the layer to customize

| Need | Start here | Boundary |
| --- | --- | --- |
| Select a model, prefix, fields, or CRUD serializer | [ViewSets](viewsets.md) | Use the operation-specific serializer attributes; `serializer_class` is not a supported switch. |
| Normalize or validate model data | [Serializers](serializers.md) | Validation does not authenticate the caller or establish tenant ownership. Extra input is not universally rejected. |
| Establish identity | [Authentication](authentication.md) | Password/session helpers do not install login routes or token-verification middleware. |
| Restrict requests and objects | [Permissions](permissions.md) | Hooks are synchronous; list filtering and object access are separate concerns. |
| Add a custom endpoint | [Actions](actions.md) | Custom HTTP handlers must explicitly enforce authorization. |
| Register endpoints | [Routing](routing.md) | Registration makes routes available; it does not establish caller identity. |
| Understand identity, tenancy, and policy together | [Identity concepts](../concepts/application-boundaries.md) | Resolve identity and tenant membership on the server. |

## Custom HTTP action boundary

!!! warning "Known v0.7.0 limitation"
    A registered `@action` HTTP handler does not automatically run the ViewSet's
    permission checks or the decorator's `permission_classes` metadata. Merely
    adding `IsAuthenticated` to the class does not protect that custom handler.
    Follow the explicit checked example in [Actions](actions.md). Custom writes
    must also enforce object, tenant, payload, and transaction requirements.

Generated CRUD and MCP execution have their own enforcement paths. MCP approval
metadata does not install an HTTP approval workflow, and exposing a method over
both transports does not prove equivalent authorization behavior.

## Test the application boundary

Use the tutorial's authenticated HTTP tests and negative cases, including
anonymous requests, another tenant's identifiers, and forbidden fields. Route
registration or generated OpenAPI alone does not prove those controls work.
Interactive API documentation is available when enabled by the application's
FastAPI configuration; it is an exploration tool, not an authorization test.
