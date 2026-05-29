# v0.6 Stability Contract (Draft)

*Draft — May 2026. This document will be finalized before v0.6.0 ships.*

---

Aksara is pre-1.0 and actively evolving. Before v1.0, API surfaces may change.
This document defines which areas are stable and intended to be preserved,
which are still evolving, how breaking changes are communicated, and what
migration support looks like in practice. It is a commitment to predictable
change, not a promise of no change.

---

## Stable / Intended to Preserve

These areas have been in use across multiple releases, have documented
behavior, and are intended to remain compatible across v0.6.x. Breaking
changes in these areas are not expected without a strong reason and clear
migration guidance.

### ORM Core

- `Model`, `TenantModel`, and `fields.*` field types
- `Model.objects` queryset interface: `get()`, `filter()`, `all()`, `create()`,
  `update()`, `delete()`, `bulk_create()`, `bulk_update()`, and `upsert()`
- `Q()`, `F()`, and aggregation expression objects
- Transaction context managers
- `ForeignKey`, `ManyToManyField`, `GenericForeignKey`, and relation traversal
- `signals.pre_save`, `signals.post_save`, `signals.pre_delete`,
  `signals.post_delete`
- `Model.Meta` options: `table_name`, `ordering`, `indexes`, `constraints`,
  `tenant_field`, `soft_delete_field`

### Migration System

- `aksara makemigrations` and `aksara migrate` commands
- Migration file format and migration dependency tracking
- Existing generated migrations are not re-generated or altered by framework
  upgrades

### ViewSets and API

- `ModelViewSet` class interface and standard action methods
- `@action` decorator and action registration
- Standard serializer behavior for model fields
- Filtering, ordering, and pagination query parameter conventions
- Permission class protocol: `has_permission()` and `has_object_permission()`
- Authentication class protocol: `authenticate()`

### CLI

- `aksara dev`, `aksara migrate`, `aksara makemigrations`, `aksara shell`
- `aksara doctor launch-check`, `aksara doctor security-check`,
  `aksara doctor production-check`, `aksara doctor fix-plan`
- `aksara examples validate`

### Security Policy Model

- `Principal` class and its four types: `User`, `AIAgent`, `Anonymous`,
  `System`
- `PolicyEngine` method signatures: `can()`, `visible_fields()`,
  `writable_fields()`, `query_filter()`, `validate_payload()`
- `enforce_payload_policy()` and `enforce_request_payload_policy()` helpers
- `PolicyDenied` exception and `policy_denied_to_error_payload()` helper
- Field annotations: `ai_sensitive`, `ai_agent_writable`, and their runtime
  enforcement semantics

### MCP/AI Credential Helpers

- `MCPCredentialClaims` structure
- `principal_from_mcp_claims()` and the scope/audience/tenant helper family
- MCP credential validation semantics (scopes, audience, tenant binding,
  expiration)

### Settings Protocol

- `AksaraSettings` key names and types for all settings documented in the
  Settings Reference
- Environment variable naming convention: `AKSARA_*`

---

## Still Evolving

These areas are functional and usable, but their interfaces may change in
minor or patch releases before v1.0. Plan for possible migration when using
them.

### AI Debugger, Architecture Review, Performance Analyzer

The analysis engines and Studio APIs for these features are operational but
their output schemas, API paths, and scoring models are not frozen. Do not
build automation that depends on specific output formats from these tools.

### Migration Tracking Metadata

The migration *commands*, the migration *file* format, and existing generated
migrations are stable (see above). The internal `aksara_migrations` tracking
table is not. Its columns may evolve in a future release — for example, metadata
schema versioning or an app-label / name identity split — so do not build
automation against the tracking table's column layout. Migration execution
safety, integrity (checksums), and the SQL-generation guardrails are intended to
remain in place; the metadata-schema redesign that would change the tracking
table is deferred future work.

### Long-Running AI Session State

Durable AI session storage and AI Console transcript persistence are planned
but not finalized. Current in-memory session state is not a stable API.

### Agent Mode Internals

`AgentRuntime`, `AgentPlanner`, and the context engine interfaces are
considered internal. They may change significantly between minor versions as
agent workflows mature.

### Studio API Internals

Studio serves a built-in frontend and its REST API paths are not a public
contract. External automation that calls Studio API endpoints directly may
break on minor version bumps.

### Example Templates

`aksara startproject --template` templates are intended to evolve as framework
conventions improve. Generated project layouts may change between minor
versions. If you have customized a generated project, review the changelog
before upgrading.

### Diagnostics Output Format

`aksara doctor` command output format is human-readable and not guaranteed
stable for machine parsing. Use exit codes (0 = pass, non-zero = fail) for
automation rather than parsing stdout.

---

## Compatibility Policy Before v1.0

**Minor versions (v0.5 → v0.6):** Breaking changes to stable areas will be
documented in the changelog with a migration path. Changes to evolving areas
may occur without a migration path. Deprecations in stable areas will be
announced one minor version before removal where possible.

**Patch versions (for example, v0.5.52 → v0.5.53):** No intentional breaking changes to
stable areas. Bug fixes and additive changes only. If a patch inadvertently
breaks stable behavior, that is a bug and will be fixed in a follow-on patch.

**Before v1.0:** No API stability guarantee equivalent to semantic versioning
post-1.0 is made. The intent is to make breaking changes predictable and
migration-guided, not to make them impossible. If you are building on Aksara
pre-1.0, subscribe to the changelog and pin your minor version in production.

---

## Security-Fix Behavior

Security fixes are not bound by the compatibility policy. A security fix may
change default behavior, disable an insecure option, or require configuration
changes without a deprecation window.

When a security fix changes defaults or removes an option:

- The changelog entry will clearly label it as a security fix.
- The nature of the change and the affected configuration will be described.
- A migration path will be provided where one exists without compromising the
  fix.

Security fixes will be applied to the current stable minor version. Backports
to prior minor versions are at maintainer discretion based on severity and
deployment complexity.

---

## Generated Surface Change Policy

Aksara generates REST routes, OpenAPI schemas, MCP tool descriptions, Studio
admin surfaces, migration DDL, AI prompt context, and serializer behavior from
model definitions.

For generated surfaces:

- **Generated migration DDL** is treated as stable output. Framework upgrades
  will not retroactively alter existing generated migrations. New model changes
  will produce new migration files in the same format.
- **Generated OpenAPI schemas** may gain new fields, additional response
  properties, or improved descriptions between versions. Removal of fields
  requires a deprecation notice.
- **Generated MCP tool descriptions** may improve in clarity or add new
  metadata between versions. Tool names and input schemas for standard CRUD
  actions on a ViewSet are considered stable once the ViewSet is registered.
- **Generated Studio admin surfaces** are not a public contract. They will
  improve between versions and their visual layout and API paths may change.
- **Runtime enforcement semantics** (what is denied, what returns `denied_fields`,
  which paths are covered) are part of the stable security policy model. Changes
  to enforcement coverage will be documented.

---

## Migration Note Expectations

For each minor version:

- A changelog section describes what changed and what the migration path is.
- For breaking changes to stable areas: a before/after code example is
  provided where the change affects user code.
- For changes to generated surfaces: a description of what will look different
  after upgrading.
- For security-fix changes: a clear description of what changed, why, and what
  to do.

Migration notes will not be provided for:

- Changes to internal implementation details not in the stable API list.
- Improvements to generated output that do not break stable behavior.
- Bugfixes that restore documented behavior (the old behavior was wrong).

If a changelog entry is unclear or missing a migration path you need, open an
issue. That feedback improves the release process directly.

---

*This is a draft. It will be updated before v0.6.0 ships. The intent is to
publish a finalized version alongside the v0.6.0 release announcement.*
