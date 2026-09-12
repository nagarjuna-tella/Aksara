# Changelog

All notable changes to Aksara are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## v0.7.1 — Documentation & Developer Experience

Released 2026-09-12.

This release brings Aksara's public documentation and developer experience into
line with actual installed behavior. It adds no runtime capability and makes no
intentional runtime semantic or dependency change.

### Public truth and onboarding

- Reframed Aksara as a PostgreSQL-backed Python application framework where
  human and machine actors share the same identity, policy, tenant, transaction,
  approval, audit, and durable-execution boundaries.
- Rebuilt the Quick Start and progressive Ticket Desk tutorial around an
  installed package, PostgreSQL, migrations, generated REST, local identity,
  permissions, tenancy, tasks, Durable Operations, and optional MCP.
- Added a coherent configuration reference, production runbook, v0.6-to-v0.7
  upgrade guide, glossary, stability guidance, and task-oriented how-to paths.
- Improved generated-project README and CLI guidance while preserving generated
  runtime defaults, security settings, middleware, service enablement, and
  dependency behavior.

### Executable documentation and evidence

- Added installed-wheel, PostgreSQL, scaffold, application-journey, import,
  CLI, JSON, code-fence, rendered-link, and external-link gates for public docs.
- Audited every public page and bundled example, with explicit evidence scopes
  and retained negative controls for functional defects found during the review.
- Kept those runtime defects out of this documentation release; each requires a
  separately reviewed functional patch.
- Preserved all 22 disclosed functional findings without fixing or masking them
  in this release.

### Strategy and roadmap

- Published an evidence-driven post-v0.7 market and capability review.
- Populated the public roadmap around operating the existing authorized-action
  contract, targeted integrations, bounded pre-1.0 stabilization, and explicit
  non-goals such as a general workflow engine or broad database portability.

## v0.7.0 — Durable Authorized Operations

Released 2026-09-11.

This release adds an opt-in PostgreSQL execution substrate for authorized
application work that must outlive its request, process, or worker.

### Durable execution truth

- Added one authoritative logical Operation with separate physical Attempts,
  database-time leases, monotonic fences, bounded results/errors, and retained
  status after restart.
- Added a guarded `postgres_atomic` executor that commits supported
  same-database application mutation, Attempt success, Operation success,
  result, transition, and outbox intent in one Aksara-pinned transaction.
- Preserved deterministic lost-response recovery: an ambiguous acknowledgement
  causes an authoritative PostgreSQL reread, and the same idempotency identity
  resolves the existing Operation.

### Safe retries and current authority

- Added tenant, principal, application, action-version, and canonical-input
  scoped idempotency with deterministic conflict and concurrency behavior.
- Added claims, heartbeats, reclaim, retry eligibility, deadlines, Attempt
  limits, and stale-owner fencing across process replacement.
- Added versioned non-secret `PrincipalReference` provenance and code-registered
  resolvers. Delayed effects resolve a current `Principal` and recheck scopes,
  tenant, action policy, and `PolicyEngine`; approval never restores revoked
  permission.

### Decisions, tasks, and external systems

- Added durable approval decisions bound to the exact Operation, input,
  action/version, requester, approver, tenant, and expiry, plus durable
  cancellation intent with deterministic same-database completion races.
- Added optional task-backed execution while keeping Operation Attempt/fence
  authority and all existing unlinked task behavior.
- Added explicit external idempotent, reconcilable at-least-once,
  nonretryable, and read-only classifications. Unreconcilable ambiguity becomes
  `external_outcome_unknown`; Aksara does not claim exactly-once provider
  effects.

### Operational surface and compatibility

- Added explicit Python and REST dispatch/status/cancel/decision surfaces,
  bounded transition history, retryable outbox export, pruning/tombstones, and
  machine-readable deployment diagnostics.
- Added production fault injection, multi-process kill/restart, restricted-role
  forced-RLS, security-abuse, contention, migration, and installed-wheel Support
  Desk gates.
- Kept generated REST and MCP synchronous by default. Existing signed MCP
  approval grants, `Principal`, generated authorization, RLS, task IDs/APIs,
  CLI behavior, and applications that never adopt durability remain compatible.
- Kept PostgreSQL as the only required durable service.

### MCP status

Existing official-client Streamable HTTP MCP behavior at `/mcp/` remains in
the release gate. Protocol-level durable MCP Tasks are deferred because the
current official Python SDK does not implement the current
`io.modelcontextprotocol/tasks` extension. Aksara does not add a competing
wire protocol.

### Stable boundary and limits

The stable additions are the documented Operation semantics, scoped
idempotency, Attempts/leases/fencing, current reauthorization, approval and
cancellation binding, same-database atomic executor, external-effect recovery
classes, task adapter, bounded history/export/retention, and deployment
diagnostics. Internal tables, repositories, raw commands/provenance, worker and
fence values, and transition storage remain internal.

Planner quality, persistent AI sessions or memory, multi-agent/autonomous
workflows, provider quality, Studio AI internals, generic DAG composition,
application approval UX, and durable compliance retention remain experimental,
application-owned, or deferred. `DurableStep` remains available but does not
gain the v0.7 Operation guarantees.

## v0.6.1 — Installed-Package Truth

Prepared 2026-09-10.

This adoption and trust patch aligns Aksara's public documentation, generated
project, configuration guidance, and package metadata with the behavior shipped
in the v0.6 stable contract.

### Changed

- Replaced stale importable-looking `AgentRuntime`, `Planner`, provider,
  code-generation, patch, query, and cache examples with real exported APIs or
  clearly labeled conceptual and experimental material.
- Defined `/mcp/` as the official-client Streamable HTTP protocol endpoint and
  `/ai/tools/mcp` as the HTTP JSON tool inspection catalog throughout public
  docs, examples, CLI output, and generated projects.
- Narrowed background-task identity wording to the persisted `tenant_id`
  contract; complete Principal provenance and delayed reauthorization remain
  deferred to v0.7.
- Made environment variables plus the global `aksara.conf.settings` object the
  canonical configuration path, while documenting compatibility aliases and
  the separate experimental provider configuration.
- Updated the basic scaffold to use the global settings object, keep MCP,
  provider-backed AI, and Studio opt-in, and point developers to the canonical
  authenticated MCP journey.
- Refreshed the project description and public README for the v0.6.1 package.

### Fixed

- Made database CLI options honor `AKSARA_DATABASE_URL` ahead of the compatible
  `DATABASE_URL` alias, matching runtime settings precedence.
- Allowed Principal resolution to return anonymous safely when a Starlette
  application has no `AuthenticationMiddleware`, so MCP discovery follows the
  normal authorization path rather than raising a framework assertion.

### Release trust

- Added factually scoped final v0.6.0 release evidence and a classified audit
  of public Python examples.
- Added semantic documentation tests and an isolated installed-wheel gate that
  scaffolds an application, migrates PostgreSQL, exercises REST and an official
  MCP client, runs Doctor, and verifies clean shutdown.

This release does not add durable operations, a stable planner or agent
runtime, persistent agent state, provider integrations, or new infrastructure.

---

## v0.6.0 — Production Mode

Released 2026-09-10.

Aksara v0.6.0 is the first Production Mode release within a bounded, documented
stable contract. Aksara remains pre-1.0; AI planning, durable agent state,
provider quality, and Studio AI surfaces remain experimental.

### Production foundation

- Hardened Array, Vector, JSON, file/image, primitive, relation, query, and bulk
  write contracts across ORM, API, migration, and database codec paths.
- Made session and transaction acquisition exception-safe, including cleanup
  after setup failure, cancellation, startup failure, and connection reuse.
- Strengthened migration ordering, checksum validation, advisory locking,
  runtime-table bootstrapping, and the separate migration-role deployment path.
- Defined the supported Python 3.11–3.14 and FastAPI/Starlette compatibility
  matrix and exercised its minimum and latest boundaries.
- Validated restricted PostgreSQL roles, forced RLS tenant isolation, generated
  API abuse invariants, and packaged support desk startup, shutdown, recovery,
  concurrency, migration, task, and pool-reuse behavior.
- Added strict `aksara doctor production-check --release` diagnostics for the
  documented Production Mode configuration.

### AI-native execution

- Integrated the official MCP Python SDK and mounted Streamable HTTP at
  `/mcp/`; `/ai/tools/mcp` remains the permission-filtered inspection catalog.
- Generated executable CRUD and custom action tools from registered,
  AI-exposed ViewSets.
- Propagated immutable AgentPrincipal and invocation identity into tool
  execution and correlated audit events.
- Rechecked scopes, audience, expiry, permissions, PolicyEngine decisions,
  tenant ownership, field-write rules, ORM validation, and PostgreSQL RLS when
  each MCP tool executes.
- Added signed, short-lived approval grants bound to the exact principal,
  tenant, tool, arguments, approver, and expiry.
- Added deterministic audit events, transactional rollback, cancellation,
  structured tool failure categories, and runtime/tool/provider budgets.

### Release trust

- Exercised the supported runtime matrix against hosted PostgreSQL 16 and a real
  official SDK MCP client, including packaged wheel integration.
- Added security, fuzz, diagnostics, migration, packaged reference, and strict
  Doctor release gates.
- Added dependency audit, CodeQL, secret scanning, SBOM generation, package and
  Twine verification, isolated-wheel checks, and Ruff/mypy debt ratchets.
- Kept PyPI publication in a separately authorized Trusted Publishing workflow
  using GitHub OIDC.

### Known limitations

- Planner behavior, investigation quality and session state, persistent AI
  conversations, agent memory, multi-agent workflows, durable autonomous
  workflows, provider-specific model quality, and Studio AI internals remain
  experimental.
- Investigation and MCP session/replay state is process-local; restart-safe or
  cross-worker replay/idempotency is outside the stable contract.
- Applications remain responsible for durable approval workflow state, durable
  audit retention, and exactly-once handling of external side effects.
- Custom many-to-many through models and object-valued lazy forward foreign-key
  attributes remain unsupported.
- The release evidence does not claim external security certification,
  penetration testing, soak testing, or provider certification.

### Upgrade

1. Install the final release with
   `python -m pip install --upgrade "aksara-framework==0.6.0"`.
2. Run `aksara migrate` with a migration role before starting v0.6 application
   processes, then grant the application role the required DML privileges on
   migrated runtime tables.
3. For tenant data, use a `NOSUPERUSER NOBYPASSRLS` application role and force
   RLS on tenant tables.
4. Run `aksara doctor production-check --release` with the deployment's
   security matrix and resolve every non-pass result.
5. Review every AI/MCP-exposed writable field before setting
   `AKSARA_AI_WRITABLE_FIELDS_REVIEWED=true`.
6. Point MCP clients at `/mcp/`; use `/ai/tools/mcp` only for inspection or
   compatibility adapters.

---

## Unreleased — v0.5.55 — Correctness and Hardening

### Release-candidate hardening (not published)

- Connection ownership is established before tenant/transaction setup. Setup,
  reset and cancellation failures return owned connections and restore session
  context; cleanup failures do not replace the original error.
- Route metadata traversal supports flat and included-router FastAPI layouts,
  including nested prefixes, Studio/AI discovery and media mounts.
- Web dependencies are bounded by tested FastAPI 0.136.1 / Starlette 1.0.1 and
  FastAPI 0.141.1 / Starlette 1.6.0 pairs. CI exercises both endpoints.
- Advanced validation runs before API numeric coercion in both schema builders.
  JSON scalar inputs work in generated CRUD as well as ModelSerializer.
- Array defaults use write validation, preserve empty strings and quote text/UUID
  values safely. Unsupported item types now fail explicitly. Canonical migration
  defaults follow the same policy; non-finite JSON defaults are rejected.
- Vector dimensions must be positive integers (or unspecified), and migration
  string defaults are validated rather than interpolated unchecked.
- Stored file references reject malformed values, parent traversal and null bytes.
- Generated projects depend on the `aksara-framework` distribution.

The benchmark overhaul is independently reviewable and is not part of this
correctness candidate. These changes do not declare Production Mode.


Tightens correctness for advanced ORM field types. This does not claim that all
ORM correctness work is complete; lazy forward FK object loading and custom
ManyToMany through models remain deferred. Aksara is pre-1.0, so some ambiguous
behaviors are replaced with explicit validation errors.

### Changed

- `Array` validates each element against `item_type` on every write path and
  rejects nested lists/tuples, `None` items, `bool` in `int`/`float` arrays,
  non-integral values in `int` arrays, out-of-range values for the 32-bit
  `INTEGER[]` type, and `NaN`/infinity in `float` arrays. `item_type` is the
  canonical constructor option (`str`, `int`, `float`, `bool`, `uuid.UUID`).
- Core ORM `Array` validation no longer splits delimited strings into arrays;
  assign explicit Python lists. The admin array form converts its input to a
  typed list at the form boundary.
- `Vector` write paths reject `NaN`, `Infinity`, `-Infinity`, boolean items, and
  empty vectors, and enforce the configured `dimensions` length.
- `Vector` serialization uses high-precision `repr(float)` instead of a
  six-significant-digit format, shared by `Vector.to_db`, the asyncpg vector
  codec, and vector-distance expression helpers.
- `JSON` consistently supports top-level scalars (`str`, `int`, `float`, `bool`)
  in addition to objects and arrays, serializing every non-`None` value with
  `json.dumps(..., allow_nan=False)`. Top-level `None` remains SQL `NULL`.
- Generated API/Pydantic schemas describe `JSON` fields as any JSON value and
  expose `Array`/`Vector` fields as typed lists; file/image fields stay
  string-typed.

### Fixed

- `JSON` now rejects `NaN`/infinity and non-JSON-serializable values before SQL
  execution instead of emitting invalid JSONB or silently passing scalars.
  Invalid `JSON` field defaults raise before DDL generation instead of silently
  becoming `DEFAULT NULL`.
- The asyncpg vector codec, vector-distance expressions, and migration
  `VectorField` defaults now share the same vector validation (rejecting
  boolean/non-finite/empty values) and high-precision serialization as
  `Vector.to_db`, so invalid vectors fail before SQL execution at every entry
  point.
- `update()` and `bulk_update()` reject unresolved upload-like values for
  `FileField`/`ImageField` with a clear error; use `save()`/`create()`/
  `bulk_create()` for uploads. `to_python()` returns a normalized path string
  while model attribute access returns a `FieldFile` wrapper.

### Deferred

- Lazy forward FK object loading remains deferred; forward FK/O2O attributes and
  `*_id` aliases expose the stored FK id.
- Custom `ManyToMany(..., through=...)` models remain unsupported and fail
  clearly.

---

## v0.5.54 — ORM Write & Relation Correctness

Released 2026-05-30.

This release focuses on targeted write-path consistency and relation safety
fixes. It does not claim that all ORM correctness issues are fixed.

### Fixed

- `bulk_create()` now aligns more closely with `create()` and `save()` for
  auto-managed fields. It prepares rows before insert, applies non-null
  `updated_at` values for default timestamp fields, runs field preparation
  hooks such as `Slug(auto_from=...)`, and preserves explicit per-row
  `auto_now_add` values such as `created_at`.
- `bulk_update()` now casts `Vector` field CASE branch parameters with
  `CAST($n AS vector)`.
- `ForeignKey` and `OneToOne` now validate `on_delete` values and reject
  unknown actions before DDL generation. Valid actions are normalized from
  supported casing and alias variants.
- `on_delete=SET NULL` now requires `nullable=True` for `ForeignKey`,
  `OneToOne`, and migration relation field operations.
- Migration relation DDL now validates `ON DELETE` and `ON UPDATE` actions
  before emitting SQL.
- `ManyToMany(..., through=...)` now fails clearly because custom through
  models are not supported yet.
- The forward FK access contract is documented: forward FK/O2O attributes
  expose the stored FK value/id; load related objects explicitly or via
  `select_related()` plus `get_related()`.

### Changed

- `QuerySet.update()` now refreshes `auto_now` fields such as `updated_at` when
  regular fields are updated. Explicit `updated_at` values are respected, and
  `update(updated_at=...)` does not override itself.

### Compatibility / Behavior Changes

- `ForeignKey(..., on_delete="SET_NULL")` and
  `ForeignKey(..., on_delete="SET NULL")` now require `nullable=True` because
  `SET NULL` on a non-nullable relation creates contradictory runtime and DDL
  behavior.

  Before:

  ```python
  author = fields.ForeignKey(User, on_delete="SET_NULL")
  ```

  Now:

  ```python
  author = fields.ForeignKey(User, on_delete="SET_NULL", nullable=True)
  ```

- `QuerySet.update()` may now include `auto_now` fields such as `updated_at`
  when regular fields change. Explicit `updated_at` values remain respected.
- Invalid or arbitrary `on_delete` text now raises instead of being emitted into
  relation DDL.
- `ManyToMany(..., through=...)` now raises a clear unsupported-feature error
  instead of implying custom through model support.
- `bulk_update()` SQL for Vector fields now includes `CAST($n AS vector)`
  inside CASE branches.
- Aksara remains pre-1.0, and additional ORM correctness work remains planned.

### Tests

- Added regression coverage for write-path timestamp hydration, vector
  subclass casting, relation `on_delete` validation, nullable `SET NULL`
  enforcement, migration DDL action validation, custom through rejection, and
  forward FK id access.

### Remaining Known ORM Correctness Work

- Lazy forward FK object loading, if desired.
- Custom ManyToMany through model support.
- Array item typing and nested array policy.
- Vector precision policy.
- FileField/ImageField `to_python()` contract.
- JSON scalar behavior.
- Relation features not implemented by the current relation manager APIs.

---

## v0.5.53 — ORM Query Semantics & Migration Generation Correctness

Released 2026-05-29.

This release focuses on ORM query semantics correctness and migration generation
correctness. It does not claim that all ORM correctness work is complete,
and intentionally leaves write-path consistency, relation DDL safety, and
advanced field policy as planned follow-up work.

### Fixed

- `filter(field=None)` and `filter(field__exact=None)` now compile to `IS NULL`
  instead of SQL equality against a `NULL` parameter.
- `__isnull` filters now use strict boolean parsing; string values like `"False"`
  and `"0"` are treated as false, and invalid values raise a validation error.
- FK/O2O column aliases such as `author_id` are accepted in filters when they
  correspond to a real relation database column.
- Reverse FK filters now work through the corrected alias handling.
- `CreateTable` migration operations are now ordered by FK/O2O dependencies so
  referenced tables are emitted before dependent tables.
- `DropTable` operations use reverse dependency order so dependent tables are
  dropped before referenced tables.
- Legacy `makemigrations --sql` output now uses FK dependency ordering.
- `models_to_migration_code()` delegates through the autodetector path.
- `Array(nullable=False)` fields now emit `op.ArrayField(..., nullable=False)` in
  generated migration code.
- Migration codegen now supports `SmallIntegerField`, `TimeField`,
  `DurationField`, `SlugField`, `IPAddressField`, `BinaryField`, and
  `FilePathField`.

### Tests

- Added regression coverage for FK dependency ordering across `CreateTable`,
  `DropTable`, legacy SQL output, executor delegation, Array nullability, and
  extended FieldOp code generation.

### Compatibility Notes

- `filter(field=None)` now returns `NULL` rows instead of returning no rows.
- `__isnull` parsing is stricter; invalid values now raise instead of being
  treated as truthy.
- FK column aliases are now accepted in filters.
- Generated migration ordering may change for apps with FK/O2O relationships.
- Generated migration code for `Array(nullable=False)` is now stricter.
- Package remains pre-1.0 and additional ORM correctness work remains planned.

---

## v0.5.52 — Admin Correctness & Permissions

This release focuses on admin correctness, permission semantics, and API naming
compatibility. It makes the generated admin more predictable under custom
prefixes, multiple admin sites, object-level permission hooks, readonly fields,
and bulk actions. It does not claim production readiness or external security
review, and intentionally leaves broader ORM correctness work on the roadmap.

### Fixed

- Custom admin prefixes now scope the admin CSRF cookie to the mounted prefix,
  so forms under paths such as `/manage/` receive the right cookie path.
- Multi-site admin routing now builds routes bound to the mounted `AdminSite`,
  keeping route names, branding, registry lookups, and permission checks
  isolated per site.
- Custom `login_url` and `logout_url` settings are honored for admin redirects.
- Site `permission_classes` are honored consistently during login and normal
  admin access, including async permission checks in the admin request path.
- Admin session lookup errors are logged and treated as unauthenticated
  requests instead of failing silently.
- Bulk actions now perform object-level permission checks for selected objects
  before running the action. The built-in delete action does not bypass
  per-object delete permissions.
- Many-to-many admin saves now validate submitted related ids and apply relation
  updates transactionally instead of silently dropping invalid ids.
- `readonly_fields` are enforced on both create and update POSTs, even when a
  readonly field is included explicitly via `fields` or `fieldsets`.
- Boolean admin checkboxes now render saved `False` values unchecked.

### Improved

- Admin list views now support database-backed search, field/custom filters,
  ordering, pagination, "show all" caps, sortable headers, custom columns,
  actions, and flash messages.
- Admin form layout now supports `fields`, `exclude`, `fieldsets`,
  `readonly_fields`, `prepopulated_fields`, `raw_id_fields`, and JSON/array
  widgets where implemented.
- Admin site configuration now supports branding, themes, custom index
  templates, extra CSS, custom login/logout redirects, multiple sites, and
  site-level permission classes.
- The public API filter backend name is now `AksaraFilterBackend`.
  `DjangoFilterBackend` remains available as a backward-compatible alias.

### Documentation

- Expanded admin docs for Admin vs Studio guidance, `include_admin()` setup,
  custom prefixes, CSRF behavior, permissions, actions, widgets, filters,
  pagination, form layout, and bulk action permission checks.
- Updated API filtering docs to prefer `AksaraFilterBackend` and describe
  `DjangoFilterBackend` only as a compatibility alias.

### Tests

- Added focused admin coverage for custom admin prefixes, multi-site routing,
  custom login/logout redirects, site and object permission checks, bulk
  actions, list filters, pagination, readonly fields, Boolean checkbox
  rendering, M2M validation, and admin HTTP integration.
- Added API compatibility tests proving `DjangoFilterBackend is
  AksaraFilterBackend` from both `aksara.api.filters` and `aksara.api`.

### Compatibility Notes

- `AksaraFilterBackend` is the preferred public name for new code.
- `DjangoFilterBackend` remains importable as a compatibility alias.
- Admin `permission_classes` now apply consistently to login and access. Sites
  with custom permission policies may see login behavior match their policy more
  strictly than before.
- Admin readonly fields are now enforced more strictly on create and update.
- Bulk actions may now reject a selection when any selected object fails the
  relevant object-level permission check.
- Custom admin prefixes should now receive CSRF cookies scoped to the correct
  path.

---

## v0.5.51 — ORM Primitive Correctness

This release focuses on ORM primitive field correctness. It makes field
conversion stricter and more predictable before values reach PostgreSQL, while
leaving broader query semantics, relation behavior, and advanced field policy as
planned follow-up work.

### Fixed

- Integer-family fields now reject non-integral numeric inputs instead of
  truncating them with `int(value)`.
- Integer-family fields mapped to PostgreSQL `INTEGER`, `SMALLINT`, and `BIGINT`
  now validate database range boundaries before persistence.
- Boolean fields now parse strict true/false forms instead of applying
  `bool(value)` to arbitrary strings.
- Decimal fields now enforce `max_digits` and `decimal_places` before
  persistence and do not rely on PostgreSQL rounding.
- Float fields now reject `NaN`, positive infinity, and negative infinity.
- Email validation now rejects local parts that start with a dot, end with a
  dot, or contain consecutive dots.

### Tests

- Added unit and DB-backed regression coverage for integer coercion and
  database bounds, boolean string parsing, decimal precision/scale enforcement,
  finite float handling, and email local-part dot validation.

### Community

- Added a Code of Conduct.
- Added a contribution guide.
- Added bug-report and feature-request issue templates.
- Added a pull request template covering tests, docs impact, changelog impact,
  and secret-safety checks.

### Compatibility Notes

- Stricter validation may reject values that previous releases accepted through
  permissive coercion.
- Integer fields no longer truncate non-integral numeric inputs.
- Boolean fields no longer treat arbitrary non-empty strings as `True`.
- Decimals with extra scale are rejected instead of allowing PostgreSQL to
  round them.
- `NaN` and infinity float values are rejected.
- Aksara remains pre-1.0, and additional ORM correctness work remains planned.

### Known Remaining ORM Correctness Work

- `NULL` filtering and `__isnull` query semantics.
- FK alias filtering and reverse FK filters.
- `bulk_create`/write-path consistency.
- Relation DDL safety.
- Array/vector/file advanced field policy.

---

## v0.5.50 — Migration Safety & Correctness

File-based migrations now apply safely and consistently across the CLI and test
helper entry points, the integrity of already-applied migrations is verified,
and the SQL the framework generates is hardened. The migration file format is
unchanged and no action is required on existing projects.

### Migration execution safety

- Python migrations are transactional — every operation and the recording of the
  migration run in one transaction and roll back together on failure.
- SQL migrations execute statement-by-statement inside that same transaction, so
  multi-statement files apply completely.
- Applying migrations acquires a PostgreSQL advisory lock so two processes cannot
  migrate at the same time; the lock is always released.
- The migration dependency graph detects circular dependencies and reports the
  cycle clearly.

### Migration integrity

- Python and SQL migrations store a checksum when applied.
- Already-applied migrations are verified against their stored checksum before new
  migrations run; a mismatch fails with the migration name and next steps.
- Historical rows with no stored checksum remain valid and produce a warning, not
  an error.
- Generated migrations that add a non-null field without a default include a
  warning comment pointing to a safe rollout (temporary default, backfill, or a
  nullable-first data migration). Primary keys are exempt.

### Failure reporting

- Migration graph loading is strict by default — a file that cannot be loaded
  raises a clear error instead of being silently skipped.
- When a migration fails, the pending migrations that were skipped are reported,
  and the CLI shows them.

### SQL-generation guardrails

- Many-to-many join-table constraint names are deterministic, quoted, and bounded
  to PostgreSQL's identifier length limit; source/target columns are quoted.
- Partial-index `where` predicates are validated for obvious unsafe patterns.
- Array field SQL types are validated against an allowlist and normalised.
  `ArrayField(sql_type="text[]")` now normalises to `"TEXT[]"`.

### Unified execution path

- `aksara migrate` and the testing helpers apply migrations through the same
  canonical executor, so file-based CLI and test runs get the same transactions,
  advisory lock, SQL splitting, checksum recording, and checksum verification.
  The legacy model-based CLI fallback remains for bootstrap scenarios and does
  not provide the full file-based migration integrity model. The dry-run preview
  path is unchanged.

### Compatibility notes

- The migration file format is unchanged; existing migrations are not
  re-generated or altered.
- Legacy CLI helpers (`MIGRATION_TABLE_SQL`, `compute_checksum`,
  `ensure_migrations_table`, `get_applied_migrations`, `record_migration`) remain
  importable from `aksara.cli.main` as compatibility shims; new code should import
  from `aksara.migrations.executor`.

### Deferred work

These migration-metadata items are intentionally not part of this patch:

- Migration metadata schema versioning (`schema_version` column).
- App-label / name identity split (`app_label` column and `UNIQUE(app_label, name)`).
- Automatic checksum backfill for historical rows (unsafe to automate — it would
  bless already-edited files and defeat tamper detection).
- A dedicated migration verify/backfill command.

---

## v0.5.49 — Security Hardening & Release Trust

### Security

- Added centralized `Principal` and `PolicyEngine` foundations for consistent authorization decisions.
- Added runtime payload enforcement for covered generated write paths.
- Added field-level policy handling for AI-sensitive, non-agent-writable, read-only, tenant-owned, and system-only fields.
- Added tenant-aware policy checks and runtime rejection of tenant override attempts.
- Added MCP credential validation helpers for scopes, audience, tenant binding, expiration, and token metadata.
- Added bounded adversarial/fuzz tests for generated filters, ordering, pagination, serializers, runtime enforcement, JSON path-like inputs, migration defaults, and malformed payloads.

### Diagnostics

- Added `aksara doctor security-check`.
- Added `aksara doctor production-check`.
- Added security diagnostics for secrets, debug mode, CORS, Studio exposure, MCP hardening, cookies, rate limits, RLS, AI defaults, and private matrix enforcement.
- Added public-safe `security/security_matrix.example.yml`.
- Private `security/security_matrix.yml` is now git-ignored and optional unless `AKSARA_REQUIRE_SECURITY_MATRIX=true`.

### Supply Chain and Release Trust

- Added Security CI workflow.
- Added Release Gate workflow.
- Added CodeQL workflow.
- Added Dependabot configuration.
- Added Gitleaks secret scanning.
- Added Bandit static-analysis gate.
- Added `pip-audit` dependency audit.
- Added CycloneDX SBOM generation.
- Added package build, `twine check`, and wheel import verification.
- Added manual PyPI Trusted Publishing workflow using OIDC and a protected `pypi` environment.

### Documentation

- Added public security overview, production hardening, threat model, authentication/principals, field-level permissions, multi-tenancy, AI/MCP boundaries, security coverage, and release-security docs.
- Added release instructions.
- Added external review scope and hardening report template.
- Moved internal hardening history to `security/hardening-history.md`.
- Removed internal security-round language from public docs.

### Testing

- Added security, diagnostics, runtime enforcement, MCP credential, tenant isolation, and fuzz/adversarial test coverage.
- Latest validation: security tests `424 passed, 1 skipped`; diagnostics tests `305 passed`; full suite `7120 passed, 165 skipped`; MkDocs strict build passed; package build and `twine check` passed.

### Notes

- This release improves security posture and release trust infrastructure.
- This release does not constitute an external audit.
- This release does not make a blanket production-readiness claim.

---

## v0.5.48 — Launch Hardening & Golden Path

- Added `aksara doctor launch-check`
- Added `aksara examples validate`
- Polished golden-path examples
- Improved first-user docs
- Added packaging sanity tests
- Updated roadmap
- Improved first-run Studio/AI guidance docs

---

## [0.5.47] — AI Metadata Enforcement & ORM Write-Path Fixes

### Fixed — AI Metadata Propagation

- `ai_sensitive=True` fields are now excluded from **all** AI surfaces:
  tool schemas, MCP export, and console prompt-packs. Previously these
  fields leaked through visible-model create/update schemas, MCP input
  schemas, and console-generated prompt packs.
- `ai_agent_writable=False` fields are now excluded from create and update
  tool schemas and MCP input schemas. Read schemas are unaffected.
- Regression coverage added in `tests/ai/test_ai_metadata_propagation.py`
  covering all three surfaces.

### Fixed — ORM Core (Phase 1)

- `String.to_db()` now enforces `max_length` before persistence, raising
  `ValidationError` instead of relying on PostgreSQL to reject the value
- `bulk_update()` now emits valid `CASE WHEN id = $n THEN $v END` SQL —
  previously the `WHEN` condition was a bare value, not a boolean expression
- `bulk_create()` now uses DB column names for FK fields (`owner_id` not
  `owner`) in the INSERT column list
- `upsert()` now calls `field.to_db()` for all values — previously raw
  Python values were sent to asyncpg, breaking JSON, Enum, DateTime, and
  other serialized field types
- `upsert()` now emits `DO NOTHING` when no update fields are provided,
  instead of invalid `DO UPDATE SET` with no assignments
- `upsert()` now uses DB column names for FK fields in both the INSERT
  column list and the `ON CONFLICT` target

### Fixed — Migrations (Phase 2)

- Array fields now preserve PostgreSQL array types in generated migrations
- JSON defaults with apostrophes are now correctly escaped in migration SQL
- `AlterFieldDefault` now emits valid JSONB literal SQL for JSON defaults
- Decimal defaults are now preserved correctly in generated migrations
- Internal migrations are now ordered before user migrations during discovery
- `apply_migrations()` now respects declared dependency order

### Fixed — API Layer (Phase 3)

- Auto-generated ViewSet routes now publish concrete response models in
  OpenAPI schema instead of `Any`
- `model_to_dict()` now includes ManyToMany fields declared in read schemas
- Cursor pagination now correctly applies page size and cursor filtering
- Serializer type mapping now uses concrete Python types instead of `Any`

### Fixed — Security (Phase 4)

- `get_current_user()` no longer trusts the client-controlled `X-User-Id`
  header for user resolution — previously this allowed arbitrary
  user impersonation
- Studio auth is no longer bypassed by `debug=True` when auth is required
- Studio session-cookie auth path now uses DB-backed user lookup
- `AIAgentMiddleware` now auto-registers so `DenyAI` can function correctly

### Fixed — CLI (Phase 5)

- `aksara dbsetup` prompt order no longer misroutes username input into
  the port prompt
- `aksara info` now includes configured `installed_apps`
- `aksara info` now reports Studio availability using runtime gating
  semantics, not a hardcoded flag
- CLI model discovery now honors `installed_apps` instead of a hardcoded
  shortlist

### Fixed — Multi-tenancy & Background Tasks (Phase 7)

- `enqueue_task()` now persists tenant provenance at enqueue time
- `TaskWorker` now restores tenant context before task execution
- Empty or whitespace-only tenant headers now fail closed with HTTP 400
  instead of silently disabling tenant scoping
- Task record schema now includes `tenant_id` field

### Tests

- 33 targeted regression tests added across Phases 1–7
- AI metadata propagation regression suite added in
  `tests/ai/test_ai_metadata_propagation.py`
- Total suite: **6507 passed, 3 skipped**

## [0.5.46] — Packaging and Docs Release Polish

### Changed

- Bumped package metadata, CLI version output, scaffold templates, example app metadata, and user-facing version references to **0.5.46**

### Fixed

- PyPI project description assets now use absolute URLs so images render correctly on package pages
- Documentation deployment installs the required MkDocs plugins and deploys using the repository's `docs/mkdocs.yml`
- Documentation favicon now uses the Aksara logo in browser tabs

## [0.5.45] — ORM Expressions, Native Multi-Tenancy, SDK Generation, and Real-Time Streams

### Fixed

- **`BigInteger.to_db()`**: Added BIGINT range validation — previously accepted arbitrary Python ints that would overflow PostgreSQL
- **`Time.to_python()` / `to_db()`**: Replaced brittle `strptime("%H:%M:%S")` with `py_time.fromisoformat()` — now handles microseconds (`14:30:00.123456`) and `datetime` → `time` conversion
- **`FilePath.choices()` recursive mode**: Fixed bug where `os.walk` only yielded files, ignoring directories even when `allow_folders=True`
- **`Slug` regex**: Changed from `re.compile(r"^[-\w]+$", 0)` to `re.compile(..., re.ASCII)` when `allow_unicode=False` — Python 3's `\w` matches unicode by default, so non-ASCII characters were incorrectly accepted

### Improved

- **`IPAddress.to_python()`**: Now normalizes through `ipaddress.ip_address()` for consistent round-tripping instead of bare `str()`
- **Inspector type map** (`aksara/inspectors/models.py`): Already had entries for `SlugField`, `SmallIntegerField`, `BigIntegerField`, and `TimeField` — no changes needed

### Tests

- Added `tests/test_fields_extended.py` with **117 new tests** covering:
  - All 11 field types: `sql_type`, `to_python`, `to_db`, validation, edge cases, `None` handling
  - `FilePath.choices()` with temp directories: recursive/non-recursive, match filters, `allow_folders`
  - Migration FieldOp SQL generation for all 7 new operation types
  - Autodetector mapping verification: all 11 runtime fields → correct FieldOp types
- Total test suite: **6280 passed** (up from 6156)

### Added

- **11 new ORM field types** (`aksara/fields.py`) for Django parity:
  - `SlugField` — URL-safe slugs with ASCII/Unicode validation and `max_length` enforcement
  - `SmallIntegerField` — SMALLINT with range validation (`-32768..32767`)
  - `BigIntegerField` — BIGINT with range validation (`-2^63..2^63-1`)
  - `PositiveIntegerField` — INTEGER restricted to non-negative values
  - `PositiveSmallIntegerField` — SMALLINT restricted to `0..32767`
  - `PositiveBigIntegerField` — BIGINT restricted to non-negative values
  - `TimeField` — TIME (time of day without date)
  - `DurationField` — INTERVAL (stores `timedelta` via PostgreSQL INTERVAL)
  - `IPAddressField` / `GenericIPAddressField` — INET with IPv4/IPv6 protocol enforcement and `unpack_ipv4`
  - `BinaryField` — BYTEA for raw binary data (defaults to `ai_sensitive=True`)
  - `FilePathField` — VARCHAR with filesystem-backed `choices()` scanning

- **7 new migration `FieldOp` subclasses** (`aksara/migrations/operations.py`):
  - `SmallIntegerField`, `SlugField`, `TimeField`, `DurationField`, `IPAddressField`, `BinaryField`, `FilePathField`
  - All produce correct PostgreSQL DDL (`SMALLINT`, `TIME`, `INTERVAL`, `INET`, `BYTEA`, `VARCHAR(N)`)
  - Exported via `__all__`

- **Autodetector integration** (`aksara/migrations/autodetector.py`):
  - `_model_field_to_state()` and `_model_field_to_op()` now map all 11 new runtime field types to their correct migration operations
  - `PositiveInteger` → `IntegerField`, `PositiveSmallInteger` → `SmallIntegerField`, `PositiveBigInteger` → `BigIntegerField` at migration level

- **ORM expression primitives** (`aksara/db/expressions.py`)
  - `Q()` objects for nested boolean logic with `&`, `|`, and `~`
  - `F()` expressions for database-side field references and arithmetic
  - Aggregate classes: `Count`, `Sum`, `Avg`, `Min`, and `Max`

- **QuerySet expression support** (`aksara/manager.py`)
  - `filter(*q_objects, **kwargs)` now accepts positional `Q()` objects
  - `update(**kwargs)` supports `F()` expressions for atomic updates
  - `annotate(**kwargs)` adds computed values and aggregates to model instances
  - `aggregate(**kwargs)` returns summary dictionaries from database aggregates

- **Relation-aware aggregation** (`aksara/manager.py`)
  - One-hop aggregate paths now compile JOINs automatically
  - Supported paths include reverse FK/O2O related names, forward M2M fields, reverse M2M related names, and forward FK/O2O fields
  - Examples: `Count("comments")`, `Sum("comments__views")`, `Count("tags")`, `Count("posts")`

- **Atomic transaction DX** (`aksara/db/transaction.py`)
  - `transaction.atomic` works as an async context manager and decorator
  - Reuses the active request or transaction-scoped connection through `ContextVar`
  - Nested `atomic()` blocks use asyncpg nested transactions on the same connection

- **Native PostgreSQL multi-tenancy** (`aksara/tenancy.py`, `aksara/db/tenant_context.py`)
  - `TenantModel` adds a first-class tenant-scoped base model with a required `tenant_id`
  - Tenant context is applied automatically to pooled, request-scoped, and transaction-owned connections
  - Migration autodetection emits `RunSQL` operations to enable and disable PostgreSQL RLS policies for tenant tables

- **TypeScript SDK generation** (`aksara/sdk/typescript.py`, `aksara/cli/main.py`)
  - New `aksara generate sdk --language typescript` command generates a fetch-based CRUD client from discovered `ModelViewSet` classes
  - Generated SDKs include resolved create, update, and read interfaces plus typed list parameter helpers and paginated response types

- **Real-time SSE broadcasting** (`aksara/api/streaming.py`, `aksara/api/router.py`)
  - `ModelViewSet` now exposes `GET /<prefix>/stream` by default for server-sent event subscriptions
  - Model lifecycle events publish through PostgreSQL `LISTEN/NOTIFY` from `post_save` and `post_delete`
  - Tenant-scoped stream payloads are filtered so subscribers only see events for their active tenant

- **Media storage abstraction** (`aksara/storage.py`, `aksara/fields.py`, `aksara/app.py`)
  - Added `FileField` and `ImageField` with storage-backed persistence through async model saves
  - Added `FieldFile` helpers for URLs, local paths, reads, deletes, existence checks, and file sizing
  - Added `FileSystemStorage` and `S3Storage`, plus debug-mode automatic mounting of `MEDIA_URL` for local media

- **Async email backends** (`aksara/core/mail.py`, `aksara/conf.py`)
  - Added `ConsoleBackend`, `LocMemBackend`, and `SMTPBackend`
  - Added `EmailMessage`, `send_mail()`, `send_mass_mail()`, and configurable `EMAIL_BACKEND` settings

- **Request-scoped locale and timezone context** (`aksara/i18n.py`, `aksara/middleware/locale.py`, `aksara/middleware/timezone.py`)
  - Added `LocaleMiddleware` and `TimezoneMiddleware`
  - Added lazy `_()` translations backed by gettext catalogs in `locale_paths`
  - Added UTC-normalized `DateTime` storage with request-timezone serialization in model and API exports

- **Generic relations and durable workflow state** (`aksara/contenttypes.py`, `aksara/fields.py`, `aksara/workflows.py`)
  - Added `ContentType` syncing and `fields.GenericForeignKey()` for model-agnostic relations
  - Added `DurableStep` with PostgreSQL-backed result reuse and retry-after-failure behavior

- **Built-in background tasks and advanced PostgreSQL ORM support** (`aksara/tasks.py`, `aksara/fields.py`, `aksara/manager.py`, `aksara/db/expressions.py`)
  - Added `@task`, `enqueue_task()`, `TaskWorker`, and `aksara_tasks` for PostgreSQL-backed background execution
  - Added nested JSONB path filtering with lookups like `metadata__preferences__theme="dark"`
  - Added `fields.Vector()` plus `CosineDistance()` and `EuclideanDistance()` for pgvector-backed embeddings

### Added — Field Parameters

- **`choices`** on `String`, `Integer`, `SmallInteger` — flat lists or tuple-pairs `[("val", "Label")]` for Django developer compatibility. Validates on write, passes valid values through to MCP tool exports.
- **`min_length`** on `String`, `Text` — minimum character length validation
- **`min_value` / `max_value`** on `Integer`, `Float`, `Decimal` — range validation at the Python level before database writes
- **`auto_from`** on `Slug` — generates slug from a named field on creation only; skipped if slug is already set (safe for existing URLs)
- **`regex`** on `String` — custom pattern validation
- **`strip_whitespace`** on `String`, `Text` — trims leading/trailing whitespace on write path only (`to_db`)

### Tests

- 95 new tests in `tests/test_field_params.py`
- 300 field tests passing, zero regressions
- Total test suite: **6375 passed** (up from 6280)

### Changed

- **Database connection reuse** (`aksara/db/engine.py`)
  - `Database.acquire()` now reuses the active session connection when one exists

- **Model hydration** (`aksara/model/base.py`)
  - `Model._from_record()` now preserves annotated columns by attaching undeclared fields to instances

- **Insert safeguards**
  - Expressions are rejected in insert-like operations (`Model._insert()`, `bulk_create()`, `bulk_update()`, `upsert()`) to prevent invalid SQL generation in create paths

### Documentation

- Added ORM documentation for query expressions, relation-aware aggregates, and `transaction.atomic`
- Updated API and CLI docs for stream endpoints, multi-tenant RLS behavior, and TypeScript SDK generation
- Refreshed CLI startup examples to match the current `aksara dev` hero banner and `aksara dbsetup` output
- Documented the global CLI output controls for power users: `--quiet`, `--plain`, `--no-color`, and `--force-color`
- Added advanced docs for generic relations and durable workflow execution
- Added docs for built-in background tasks, JSONB nested path filters, vector fields, and task worker settings
- Refreshed the README and release notes to reflect the full v0.5.45 feature set

### Tests

- Added focused coverage for:
  - recursive `Q()` compilation
  - `F()` filters and updates
  - annotation hydration
  - reverse FK and M2M aggregate joins
  - transaction connection reuse and nested atomic scopes
  - tenant connection context application and migration RLS SQL generation
  - TypeScript SDK generation and CLI output
  - SSE stream route wiring and PostgreSQL event publication
  - media storage persistence, image validation, schema typing, and migration mapping
  - console, locmem, and SMTP email backends
  - locale middleware, timezone middleware, and timezone-aware datetime serialization
  - GenericForeignKey resolution across multiple target models
  - DurableStep result reuse, retry handling, and force-rerun behavior
- Validated surrounding ORM, relation, and public export tests with PostgreSQL configured

## [0.5.44] — Enterprise DX Features: Filtering, Pagination, Bulk Operations, Soft Deletes, Fixtures

### Category 1: API & ViewSet DX

#### Added

- **AksaraFilterBackend** (`aksara/api/filters.py`): Automatic query parameter filtering with Django ORM lookup syntax support
  - Supports 9 lookup types: `exact`, `gt`, `gte`, `lt`, `lte`, `in`, `isnull`, `icontains`, `contains`
  - Example: `?price__gte=50&category__in=tech,news&in_stock=true`
  - Automatically coerces values (booleans, None, numbers)
  - Integrates seamlessly with `ModelViewSet` via `filter_backends` and `filterable_fields`

- **CursorPagination** (`aksara/api/pagination.py`): Keyset-based pagination for high-performance infinite scroll
  - Much more efficient than offset-based pagination for large datasets
  - Uses base64-encoded cursor values to track position
  - Ideal for mobile and infinite-scroll UIs
  - Includes `get_paginated_response()` with `next_cursor` support

- **Enhanced Filter/Search/Order Exports** (`aksara/api/__init__.py`): Centralized re-export of all pagination classes
  - `BaseFilterBackend`, `AksaraFilterBackend`, `SearchFilter`, `OrderingFilter`
  - `BasePagination`, `LimitOffsetPagination`, `PageNumberPagination`, `CursorPagination`

### Category 2: Database & ORM DX

#### Added

- **Bulk Operations** (`aksara/manager.py`): High-performance batch insert/update
  - `bulk_create(objs, batch_size=1000, ignore_conflicts=False)`: Efficiently insert thousands of records
    - Automatically handles batching for very large datasets
    - `ignore_conflicts=True` uses PostgreSQL `ON CONFLICT DO NOTHING`
    - Returns created instances with populated IDs
  - `bulk_update(objs, fields, batch_size=1000)`: Efficiently update thousands of records
    - Uses PostgreSQL `CASE` statements for atomic multi-row updates
    - Returns total number of updated records

- **Upsert Operations** (`aksara/manager.py`): PostgreSQL-native insert-or-update
  - `upsert(defaults=None, update_fields=None, **kwargs)`: Insert or update in single operation
    - Uses native `ON CONFLICT` clause for atomicity
    - Automatically updates specified fields on conflict
    - Returns `(instance, created)` tuple indicating whether it was inserted or updated

- **Soft Deletes** (`aksara/contrib/soft_delete.py`): Logical deletion pattern
  - `SoftDeleteModel`: Mixin class with automatic `deleted_at` field
  - Overrides `.delete()` to set `deleted_at` timestamp instead of removing records
  - `Manager.filter()` automatically excludes soft-deleted records
  - `undelete()` method to restore deleted records
  - Helper functions: `with_deleted()` to include soft-deleted records, `only_deleted()` to query only deleted

- **Fixture Management** (`aksara/fixtures.py`): Export/import model data
  - `dump_data(model, filters=None, fields=None, format="json")`: Export single model to JSON/YAML
    - Supports filtering exported records
    - Supports selecting specific fields
    - Automatic `FixtureEncoder` handles UUID and datetime serialization
  - `load_data(data, models=None, format="json", strict=False)`: Import fixture data
    - Returns stats dict with `{"loaded": N, "errors": M, "skipped": K}`
    - Handles both inserts and updates based on presence of PK
    - Strict mode raises on validation errors, lenient mode logs and continues
  - `dump_database(app_label=None, models=None, filters=None, format="json")`: Export entire database or filtered subset
    - Optional JSON/YAML format selection
    - Optional app_label filtering
    - Optional model name filtering

#### Enhanced

- **Manager.filter()** now supports soft delete models automatically
  - Transparently excludes `deleted_at IS NOT NULL` for SoftDeleteModel subclasses
  - Can be overridden with `with_deleted()` helper

### Category 3: Integration & Documentation

#### Added

- Comprehensive test suite with 50+ test cases covering:
  - Filter backend parameter parsing and coercion
  - Search and ordering functionality
  - All three pagination backends
  - Bulk create/update with large datasets
  - Upsert with conflict scenarios
  - Soft delete lifecycle and queries
  - Fixture export/import with various formats
  - Database dumping and restoration
- Full documentation in `docs/dx-features-guide.md`
  - Step-by-step usage examples for all features
  - Enterprise blog application example
  - Migration guide for Django/DRF developers
  - Performance tips and best practices

### Breaking Changes

- None. All features are backward compatible and additive.

### Migration Path

- Existing code continues to work unchanged
- DX features are opt-in (use `filter_backends`, `SoftDeleteModel`, etc. when needed)
- Signals were already firing; no changes required for existing signal listeners

---

## [0.5.42] — Studio UX Redesign & Accessibility

### Studio

- **Nav IA**: Restructured sidebar navigation into 5 semantic groups: Understand, Operate, Diagnose, AI Assist, and Advanced.
- **Progressive Disclosure**: Advanced group collapsed by default with animated chevron toggle; auto-expands when navigating to an advanced section.
- **ARIA & Accessibility**: Added `role="navigation"`, `aria-label`, `aria-expanded`, and `aria-controls` attributes throughout the Studio sidebar.
- **Focus Management**: Replaced all `outline: none` with `outline-offset`/`focus-visible` rules for keyboard navigation compliance.
- **Mobile Accessibility**: Nav group labels hidden on compact mobile viewports; touch targets maintained.
- **Motion Sensitivity**: Added `@media (prefers-reduced-motion: reduce)` block to disable CSS transitions/animations.
- **AI Home Removed**: `ai-home` nav item removed; requests to `#/ai-home` redirect to `ai-console`. `renderAiHome()` retained for backward compatibility.

---

## [0.5.41] — Security Hardening & AI Module Consolidation

### Security

- **S1** — Added `validate_patch_ast()` in `aksara/ai/patch.py` to reject
  AI-generated patches containing dangerous imports or built-in calls before
  application. Introduces `PatchRejectedError`.
- **S2** — Split Studio protection into two independent FastAPI dependencies:
  `_check_studio_origin` (403) and `verify_studio_auth` (401).
- **S3** — Added HMAC-SHA256 signed agent tokens in `aksara/ai/auth.py` using
  stdlib only. Constant-time comparison via `hmac.compare_digest`.
- **S4** — Added `sanitize_identifier()` and `sanitize_column_type()` in
  `aksara/ai/codegen.py` to prevent SQL injection through AI-generated schema
  operations.

### Refactoring

- **A1** — Audited `aksara/ai/llm_clients/`; confirmed all HTTP adapters use
  stdlib `urllib` with no vendor SDK dependencies.
- **A2** — Merged `aksara/ai/intent_engine_v2.py` content into
  `aksara/ai/intent_engine.py`. The `intent_engine_v2` module is now a
  backward-compatibility shim re-exporting all symbols. Updated
  `aksara/ai/__init__.py` and `aksara/ai/plan_builder.py` to import directly
  from `intent_engine`.

### Added

- `aksara/exceptions.py`: `ImproperlyConfigured(ConfigurationError)` for
  configuration-time errors distinct from runtime `ConfigurationError`.
- `aksara/ai/patch.py`: `validate_patch_ast()`, `PatchRejectedError`
- `aksara/ai/auth.py`: `sign_agent_token()`, `verify_agent_token()`
- `aksara/ai/codegen.py`: `sanitize_identifier()`, `sanitize_column_type()`,
  `IDENTIFIER_PATTERN`, `_ALLOWED_COLUMN_TYPES`
- `SECURITY.md`: Documents all security fixes and responsible disclosure policy

---

## [0.5.40] — Intent Engine v2, Investigation Continuation, Daily Briefing

- Intent Engine v2 (`aksara/ai/intent_engine_v2.py`) with structured
  classification, entity extraction, and confidence scoring
- Investigation continuation session management
- Daily briefing AI flow
- Studio authentication hardening (origin + session checks)
