# Glossary

Common terms used in Aksara documentation. Read the
[application boundaries](concepts/application-boundaries.md) for how these terms
fit together, and [stability](concepts/stability.md) for their supported scope.
AI development tools below remain experimental; a glossary entry is not a
stability promise.

---

## A

### Action
A ViewSet action is a custom endpoint defined with `@action`, operating on an
object or collection. A **durable action** is a separately registered
`DurableAction` with a name/version, effect class, handler and policy. Registering
one does not automatically turn a ViewSet action into durable execution.

### Approval
Recorded intent to permit a particular invocation or Operation to proceed. It is
not permanent permission: current authorization still applies. Synchronous MCP
grants and durable Operation decisions have different storage/replay boundaries.

### Attempt
One physical execution claim for a durable Operation. A retry or replacement
worker creates a new Attempt; the logical Operation remains the same.

### AI Mode
Experimental planning, structured query plans, code generation and debugging assistance; separate from stable backend and MCP execution. Aksara does not itself turn arbitrary natural language into authorized database queries.

### Agent
A machine actor represented by a server-owned Principal when it invokes an
application tool. Experimental Agent Mode can assemble context, prompts,
playbooks, and ordered development-workflow data; Aksara v0.7 does not provide
an autonomous multi-step agent runtime. See [Agent Runtime](ai-mode/agent-runtime.md).

### Annotation
Adding computed values to queryset results, typically using aggregate functions like `Count`, `Sum`, `Avg`.

### Authentication
The process of verifying identity. Application credential verification supplies a server-owned Principal; account/session primitives do not automatically install login routes.

---

## B

### Backend
A component that supplies a particular service, such as a storage or email backend. It can also mean the application server as a whole; the surrounding context should distinguish them.

### Bulk Operations
Database operations that affect multiple records at once (`bulk_create`, `bulk_update`).

---

## C

### Cache
Temporary storage used to avoid repeated work. Internal schema/content caches do not imply a supported general-purpose Redis cache service.

### Codegen
Experimental generation of code artifacts. Some handlers are deterministic templates; generated code still requires review and tests.

### Context Engine
Component that gathers relevant code context for AI operations.

### CRUD
Create, Read, Update, Delete — the four basic operations for persistent storage.

---

## D

### Decorator
A Python pattern that wraps functions or classes. Aksara uses decorators such as `@action` and `@task`; this does not imply a public cache decorator or signal-decorator API.

### Defer
A term for omitting fields from a query in some ORMs. Aksara does not expose a QuerySet `defer()` method; use the documented projection methods instead.

### Durable Operation
A persisted logical application command with identity, bounded retention and
authoritative execution state. It can survive request or worker loss. It is not
a generic workflow graph. See [Durable Operations](advanced/durable-operations.md).

### DurableStep
An evolving higher-level workflow/checkpoint abstraction. It does not inherit
v0.7 Operation ownership, authorization and recovery guarantees merely because
its name includes "durable."

### Detail Route
A ViewSet endpoint that operates on a single object, using the lookup field (usually `id`).

---

## E

### Eager Loading
Loading related objects along with the main query to avoid N+1 queries. See `select_related` and `prefetch_related`.

### Endpoint
A URL path that accepts HTTP requests and returns responses.

---

## F

### Fence
A monotonically increasing ownership value for an Operation claim. When a newer
Attempt owns the Operation, a stale worker cannot write through the supported
guarded mutation/finalization boundary.

### Field
A class that defines a database column and its behavior. Examples: `String`, `Integer`, `ForeignKey`.

### Filter
Constraining queryset results based on field values.

### FilterSet
A class-based filter configuration concept used by some frameworks. Aksara does not provide a public `FilterSet` class; see its [filtering reference](api/filtering.md).

### Foreign Key (FK)
A database relationship where one model references another model's primary key.

---

## G

### Generator
A Python construct that yields values lazily. Do not infer support for asynchronous QuerySet iteration from this term; execute documented terminal methods.

---

## H

### Handler
A function that responds to events (signals) or processes requests.

### Hook
A point in the lifecycle where custom code can be executed. Example: `pre_save`, `post_delete`.

---

## I

### Idempotency
For durable admission, a scoped identity makes repeated identical submissions
return the same Operation during its window. Reusing the identity with changed
input conflicts. It is not unlimited deduplication or exactly-once external delivery.

### Index
A database structure that improves query performance on specific columns.

### Instance
A single object of a model class.

### Installed Apps
The list of applications registered in Aksara settings.

---

## J

### JSON Field
A field that stores JSON data, allowing nested structures.

### JWT
JSON Web Token — a compact, URL-safe token format used for authentication.

---

## K

### Key (Primary)
The unique identifier for a model instance, usually a UUID.

---

## L

### Lease
Temporary worker ownership measured against database time. Expiry permits
recovery; it does not kill an old process. Fencing rejects the old owner's writes.

### Lazy Loading
Deferring data loading until needed. Aksara forward foreign-key attributes expose stored IDs, not lazily fetched objects.

### List Route
A ViewSet endpoint that operates on the entire collection of objects.

### Lookup
A query operator that specifies how to match values. Example: `exact`, `contains`, `gt`.

---

## M

### Manager
A class that provides the database query interface for a model (`Model.objects`).

### Many-to-Many (M2M)
A relationship where multiple instances of one model can be related to multiple instances of another.

### Meta
An inner class on models and serializers that defines configuration options.

### Middleware
Code that processes requests and responses globally, before and after view handling.

### Migration
A file that describes database schema changes, allowing version control of the database structure.

### Model
A Python class that represents a database table.

### ModelAdmin
Configuration class for displaying a model in the admin interface.

### ModelSerializer
A serializer that automatically generates fields from a model definition.

### ModelViewSet
A ViewSet that provides complete CRUD operations for a model.

---

## N

### N+1 Problem
A performance issue where querying N related objects results in N+1 database queries instead of 1-2.

---

## O

### Operation
See **Durable Operation**. Use "operation" generically only where it cannot be
confused with this persisted application command.

### Outbox
Transactional export intent recorded with a durable state change. An exporter
delivers it to an application-owned destination. It is not an indefinite,
tamper-resistant audit archive.

### ORM
Object-Relational Mapping — the system that maps Python objects to database tables.

### Only
Loading a model instance with only specific fields, ignoring others.

---

## P

### Pagination
Dividing large result sets into smaller pages.

### Patch Engine
Experimental AI development component for proposing/applying code changes. It is outside the stable backend contract.

### PolicyEngine
The shared application policy surface for resource decisions, query filtering
and field read/write rules. Applications supply their business policy and must
invoke it through the supported entry points.

### Principal
Server-owned identity and authority context used for permission decisions. It
can represent a human, service or agent; client-supplied roles are not authority.
A durable PrincipalReference is a locator for resolving current identity, not a
persisted credential or permanent permission.

### Permission
A class that determines whether a user can perform an action.

### Prefetch Related
Loading reverse foreign key or many-to-many relations efficiently using a separate query.

### Primary Key (PK)
The unique identifier field for a model instance.

---

## Q

### Query
A request to retrieve or modify data in the database.

### Query Engine
Aksara's experimental structured `AiQueryPlan` executor. It does not export a `QueryEngine` class or parse natural language; application authorization is required before use.

### QuerySet
An object describing a database query. Chain supported builders, then await a terminal method such as `all()`; do not await QuerySet itself.

---

## R

### Read-Only
A serializer or field that can only output data, not accept input.

### Related Name
The attribute name for accessing related objects from the reverse side of a relationship.

### Request
An object containing information about an HTTP request (method, headers, body, user).

### Response
An object containing information about an HTTP response (status, headers, body).

### Routing
The process of connecting ViewSets to the application. In Aksara, this is done via `urlpatterns` lists in `urls.py` and `include_viewset(app, ViewSet)` — there is no separate `Router` class.

---

## S

### Schema Doctor
AI tool that analyzes database schema and suggests improvements.

### Select Related
Requesting batched loading of foreign-key/one-to-one objects after the parent query. Use the documented `all()` path; it is not a single-JOIN guarantee.

### Serializer
A class that converts between Python objects and JSON (and validates input).

### Signal
A notification sent when certain events occur, allowing decoupled code to respond.

### Slug
A URL-friendly string, typically derived from a title (e.g., "hello-world").

---

## T

### Task
Queued background function execution. Ordinary task records retain tenant
context, not a complete requester Principal. A task may be explicitly linked to
an Operation; queue scheduling alone is not durable authorization.

### Tenant
An organization or customer in a multi-tenant application.

### Throttling
Rate limiting to prevent abuse of API endpoints.

### Through Model
An intermediate model in a many-to-many relationship for storing extra data. Custom through models remain outside Aksara's declared supported relation contract.

### Token
A string used to authenticate API requests.

### Transaction
A group of database operations that succeed or fail together.

---

## U

### UUID
Universally Unique Identifier — Aksara uses UUIDs as default primary keys.

---

## V

### Validation
Checking that data meets required criteria before processing.

### ValidationError
An exception raised when data fails validation.

### ViewSet
A class that groups related API endpoints (list, create, retrieve, update, delete, custom actions).

---

## W

### Worker
A process or component that claims and executes work. `TaskWorker` runs ordinary
tasks; `DurableOperationWorker` executes registered Operations for an explicitly
selected tenant. They are not interchangeable names for an AI agent.

### Write-Only
An input-only field concept. Aksara ModelSerializer does not support a `write_only_fields` option; explicitly select safe output fields instead.

---

## Other execution terms

**MCP tool:** a callable exposed through the Model Context Protocol. Aksara's
stable synchronous transport is Streamable HTTP at `/mcp/`; the inspection
catalog is a different endpoint. Tool registration is not blanket authorization.

**Cancellation:** a recorded request to stop future eligible work, not undo of
committed database changes or external effects.

**External outcome unknown:** the provider effect cannot safely be classified
as confirmed or absent. Preserve uncertainty and reconcile; do not blindly retry.

## Related

- [Getting Started](getting-started/index.md)
- [ORM Guide](orm/index.md)
- [API Guide](api/index.md)
