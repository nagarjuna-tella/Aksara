# v0.6 Stability and Production Contract

This contract defines the production surface provided by `v0.6.0` and the
compatibility commitment intended for the v0.6.x line. Aksara remains pre-1.0,
so a stable surface can still change when correctness or security requires it.
Such changes will be called out with an upgrade path.

Production Mode means that the declared stable backend surfaces are tested in
a production-shaped PostgreSQL deployment. It does not make Studio, the AI
analysis suite, or autonomous agents production-stable.

## Required production profile

The v0.6 production claim applies when all of these conditions hold:

- Python, FastAPI, Starlette, PostgreSQL, and pgvector use the documented
  [runtime compatibility matrix](../reference/runtime-compatibility.md).
- Schema changes run as a separate deployment step. Application startup does
  not create or alter tables.
- The application login is `NOSUPERUSER NOBYPASSRLS`, has only the required
  runtime privileges, and tenant tables use forced PostgreSQL row-level
  security.
- Authentication resolves a server-owned `Principal`; a client cannot select
  its tenant through a request field or header.
- `aksara doctor production-check --release` passes with a complete security
  matrix. Release mode treats every warning, skip, unknown, failure, or block
  as a nonzero result.
- Operators use normal process supervision, database backups, TLS, secret
  rotation, and service monitoring appropriate to their deployment.

The packaged support desk app under `examples/support_desk` is the executable
example for this profile.

## Stable public surfaces for v0.6.x

These are the interfaces Aksara intends to preserve through compatible v0.6.x
releases.

### ORM and relations

- `Model`, `TenantModel`, and the documented `fields.*` types
- The documented `Model.objects` query and write methods, including `get()`,
  `filter()`, `all()`, `create()`, `update()`, `delete()`, `bulk_create()`,
  `bulk_update()`, and `upsert()`
- `Q()`, `F()`, aggregations, and transaction context managers
- `ForeignKey`, `OneToOne`, `ManyToManyField`, `GenericForeignKey`, documented
  relation traversal, and supported `on_delete` behavior
- Model lifecycle signals and documented `Model.Meta` options

The stored ID is the forward foreign-key value. Load an object explicitly or
use the documented relation helpers. Custom many-to-many through models and
object-valued lazy forward foreign keys are unsupported in v0.6.

### Migrations

- `aksara makemigrations` and `aksara migrate`
- File-based migration dependencies, checksums, advisory locking, transaction
  behavior, and existing migration-file compatibility
- Fresh bootstrap, upgrade from a supported existing schema, and idempotent
  replay

The columns of the internal `aksara_migrations` tracking table are not a public
API. Runtime tables used by sessions, content types, tasks, and cron are
provisioned by migrations; a current application process needs DML access and
does not need DDL access.

### Generated REST API and serializers

- `ModelViewSet`, standard CRUD actions, `@action`, and registered prefixes
- `ModelSerializer` model-field validation and serialization
- Documented filtering, ordering, pagination, relations, and structured client
  errors
- Runtime enforcement of read-only, tenant-owned, system-owned,
  `ai_sensitive`, and `ai_agent_writable` field policy on covered generated
  create and update paths

Applications still own their authentication and permission policy. Generated
routes do not make an unauthenticated model safe by themselves.

### Configuration, identity, and authorization

- `aksara.conf.Settings`, the `settings` object, `configure()`, and documented
  `AKSARA_*` environment variables
- `Principal` and its `anonymous()`, `for_user()`, `for_ai_agent()`,
  `for_mcp_agent()`, and `system()` constructors
- `BasePermission.has_permission()` and `has_object_permission()`
- `PolicyEngine.can()`, `visible_fields()`, `writable_fields()`,
  `query_filter()`, and `validate_payload()`
- The documented payload-policy enforcement helpers, `PolicyDenied`, and
  structured denied-field results

Authorization is evaluated on the server. Schemas, hidden UI controls, prompt
instructions, and client-supplied tenant values are never authorization
controls.

### Tenancy

- Request and task tenant context propagation for covered framework paths
- Tenant filtering in the ORM and generated API
- PostgreSQL session context reset on pool reuse
- Forced PostgreSQL RLS as the database boundary for the production profile

Application filtering is useful defense in depth. The production isolation
claim depends on the restricted database role and forced RLS as well.

### MCP protocol and execution boundary

- Official-SDK MCP initialization, capability negotiation, `tools/list`, and
  `tools/call` over Streamable HTTP at `/mcp/`
- Generated list, retrieve, create, update, and delete tools with JSON input and
  output schemas derived from registered ViewSets and model policy
- `MCPCredentialClaims`, `Principal`, immutable invocation context, scope,
  audience, tenant, expiry, role, permission, object, and field enforcement at
  actual invocation time
- Execution through the same generated API, `PolicyEngine`, ORM validation,
  transaction, tenancy, and RLS path used by REST
- Stable categorized tool errors and deterministic redacted audit events
- Signed stateless approval grants for operations explicitly marked as
  approval-required

`/ai/tools/mcp` remains a permission-filtered inspection catalog. It is not the
protocol endpoint. MCP sessions, replay IDs, and approval grants do not claim
durability or cross-worker exactly-once semantics.

### Background tasks

- `@task`, enqueue, PostgreSQL-backed task records, bounded retry, and worker
  restart recovery
- Principal and tenant propagation on covered enqueue and worker paths
- Task status access constrained by the application authorization policy

Task functions must be idempotent where retries can repeat external effects.
The framework does not supply exactly-once delivery for external systems.

### CLI and diagnostics

- Core commands: `dev`, `run`, `migrate`, `makemigrations`, `shell`, and
  `examples validate`
- Doctor commands: `launch-check`, `security-check`, `production-check`, and
  `fix-plan`
- Exit-code policy for Doctor commands
- For `production-check --format json`, the top-level `check`, `policy`,
  `status`, `results`, `summary`, `exit_code`, and `release_ready` fields, plus
  each result's `id`, `severity`, `status`, `message`, and `recommendation`

Pretty terminal text, ordering of diagnostic results, and additional JSON
fields may change. Automation should use the JSON keys and exit code.

## Experimental surfaces

Experimental features are usable, but their APIs, storage, and behavior may
change during v0.6.x without the compatibility guarantees above.

- Studio UI layout and Studio's internal HTTP APIs
- AI Console, AI Flows, AI Debugger, Architecture Review, Performance
  Analyzer, Schema Doctor analysis output, and provider-specific live calls
- Investigation sessions and transcript state
- `AgentRuntime`, planners, autonomous loops, code-generation suggestions,
  patch execution, and approval callback internals
- Generic, OpenAI, and third-party tool export adapters outside the MCP
  protocol contract stated above
- Generated project template layout

Investigation/session state is held in process memory. It does not survive
restart and does not provide continuity between workers. Use it for interactive
inspection, not durable case tracking.

Aksara v0.6 makes no production guarantee for autonomous mutation or durable
approval workflows. The bounded approval grant is safe only after an
application-owned human decision. Durable approval state, cross-worker replay,
idempotency for arbitrary tools, and multi-worker workflow races remain outside
the stable contract.

## Explicitly unsupported or deferred

- Custom many-to-many through models
- Object-valued lazy forward foreign-key attributes
- Durable or cross-worker MCP session and replay continuity
- Durable investigation sessions, AI memory, and cross-worker AI continuity
- Production-safe autonomous approval and mutation orchestration
- Exactly-once external side effects from retried background tasks
- Studio as a production administration contract
- A general application cache API or a Redis requirement
- Certification of provider integrations that are not continuously exercised
  by the release gate

## Compatibility and change policy

Patch releases in v0.6.x should be additive or restore documented behavior.
An intentional breaking change to a stable surface requires a changelog entry
and a migration path. Deprecation will normally precede removal when a security
or correctness fix does not require an immediate change.

Experimental surfaces may change in a patch or minor release. Their changelog
entries will describe material behavior changes, but a compatibility adapter is
not guaranteed.

Security fixes may tighten defaults or require new configuration without a
deprecation window. The changelog will identify the affected setting or API
and the operator action required.

Existing generated migration files are never rewritten by an upgrade.
Generated OpenAPI and tool catalogs may add metadata or descriptions. Removal
or reinterpretation of a documented stable field requires release notes.

Pin the v0.6 minor line in production, read the changelog before upgrading,
apply migrations before starting new application instances, and replay the
release diagnostics against the deployment configuration.
