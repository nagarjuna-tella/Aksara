# Changelog

Aksara is maintained by [Nagarjuna Tella](https://github.com/nagarjuna-tella).

All notable changes to Aksara.

---

## Unreleased — v0.6.0-rc1 — Production Contract Candidate

This candidate defines a bounded Production Mode contract for Aksara's stable
backend surfaces. It is not published.

### Added

- A packaged multi-tenant support desk reference application covering models,
  relations, migrations, generated APIs, authentication, permissions, forced
  PostgreSQL RLS, an MCP-shaped tool catalog, catalog-described REST mutation,
  PostgreSQL-backed tasks, Admin, Doctor, health endpoints, and production
  configuration.
- A bounded deployment gate covering invalid configuration, unavailable
  database, pending migrations, fresh install, existing-schema upgrade,
  idempotent migration replay, restricted runtime privileges, pool reuse,
  rollback, concurrent app instances, task retry and process restart, database
  reconnection, in-flight graceful shutdown, and connection cleanup.
- Internal runtime-table migration
  `aksara_core_migrations_0001_runtime_tables` for sessions, content types,
  tasks, and cron. A current application role can start with DML-only grants.
- Strict Doctor evidence for the reference production profile. Deployments with
  AI/MCP mutation surfaces can set
  `AKSARA_AI_WRITABLE_FIELDS_REVIEWED=true` only after explicitly reviewing
  every exposed field's `ai_agent_writable` policy.
- A public stability contract that separates stable backend APIs from
  experimental Studio/AI surfaces and unsupported behavior.

### Changed

- The supported runtime contract is Python 3.11–3.14, PostgreSQL 16 in release
  CI, and the paired FastAPI/Starlette boundaries documented in the runtime
  matrix.
- `/ai/tools/mcp` is documented as an MCP-shaped JSON catalog. Protocol-level
  MCP transport, sessions, and tool invocation are outside the v0.6 contract.
- Custom lifespan startup failures now release framework database and worker
  state while preserving the triggering exception.
- Runtime schema helpers preflight migrated tables and avoid DDL when the
  schema is current.
- Static analysis uses a reviewed debt ratchet: new Ruff or mypy findings may
  not increase the recorded baseline.

### Upgrade notes

1. Upgrade from the v0.5.55 candidate and run `aksara migrate` with a migration
   role before starting v0.6 application processes.
2. Grant the application role the required DML privileges on the migrated
   runtime tables; do not grant it schema-creation privileges.
3. For tenant data, use a `NOSUPERUSER NOBYPASSRLS` application role and force
   RLS on tenant tables.
4. Run `aksara doctor production-check --release` with the deployment's
   security matrix and resolve every non-pass result.
5. If exposing AI/MCP-described writes, review every exposed field explicitly
   before setting `AKSARA_AI_WRITABLE_FIELDS_REVIEWED=true`.
6. Add an adapter for MCP protocol clients; the catalog URL itself is not an MCP
   server endpoint.

### Experimental and deferred

- Studio internals, investigation sessions, planners, code-generation
  suggestions, provider-specific live integrations, and autonomous agent
  workflows remain experimental.
- Investigation/session state is process-local and has no restart or
  multi-worker continuity guarantee.
- Durable autonomous approval/mutation, custom many-to-many through models,
  object-valued lazy forward foreign keys, and protocol-level MCP execution
  remain outside the release.

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


This release tightens correctness for advanced ORM field types. It does not
claim that all ORM correctness work is complete; relation features below remain
deferred. Aksara is pre-1.0, so some ambiguous behaviors are replaced with
explicit validation errors.

### Advanced Field Policy

#### Array

- `Array` is documented as homogeneous and one-dimensional, with `item_type`
  as the canonical constructor option.
- Array elements are now validated against `item_type` on every write path:
  `str` requires strings, `int` excludes `bool`, rejects non-integral
  floats/Decimals, and enforces the 32-bit PostgreSQL `INTEGER` range, `float`
  rejects `NaN`/infinity and excludes `bool`, `bool` accepts only real booleans,
  and `uuid.UUID` accepts UUID instances or parseable UUID strings.
- Nested lists/tuples now raise a clear "use JSON for nested lists" error, and
  `Array(item_type=list)` / `Array(item_type=Array(...))` are rejected at
  construction.
- Null array items are rejected; use `JSON` if null elements are required.
- Core ORM `Array` validation no longer splits arbitrary delimited strings into
  arrays. Assign explicit Python lists; the admin array form converts its input
  to a typed list at the form boundary.

#### Vector

- `Vector` write paths now reject `NaN`, `Infinity`, `-Infinity`, boolean
  items, and empty vectors, and enforce the configured `dimensions` length.
- Vector serialization now uses a high-precision representation
  (`repr(float)`), replacing the previous six-significant-digit format. The
  `Vector.to_db` path, the asyncpg vector codec, vector-distance expression
  helpers, and migration `VectorField` defaults share the same validation
  (rejecting boolean/non-finite/empty values) and precision policy, so invalid
  vectors fail before SQL execution at every entry point.

#### JSON

- `JSON` now consistently supports top-level scalar values (`str`, `int`,
  `float`, `bool`) in addition to objects and arrays. Top-level `None` remains
  SQL `NULL`.
- All non-`None` JSON values are serialized with
  `json.dumps(..., allow_nan=False)`, so `NaN`/infinity and non-JSON-serializable
  objects fail before SQL execution. Invalid `JSON` field defaults now raise
  before DDL generation instead of silently becoming `DEFAULT NULL`.

#### File and Image

- The `FileField`/`ImageField` contract is documented: stored state and
  `to_python()` are normalized path strings, while model attribute access
  returns a `FieldFile` wrapper.
- `update()` and `bulk_update()` reject unresolved upload-like objects with a
  clear error because those paths cannot persist file content; use
  `save()`/`create()`/`bulk_create()` for uploads.

#### API schemas

- Generated API/Pydantic schemas now describe `JSON` fields as any JSON value
  (objects, arrays, and scalars) instead of object/array only, and expose
  `Array`/`Vector` fields as typed lists. File and image fields remain
  string-typed.

### Compatibility

- Code assigning comma-separated strings directly to `Array` fields must assign
  lists instead.
- Code relying on null array elements or undocumented nested arrays now fails
  clearly; use `JSON` for those shapes.
- Passing `NaN`, infinities, booleans, or empty vectors to `Vector` fields now
  fails before SQL execution; stored vector text may show more precision than
  before. Tests comparing exact vector formatting should compare numeric values.
- Non-finite or non-serializable `JSON` values now fail earlier.

### Deferred

- Lazy forward FK object loading remains deferred; forward FK/O2O attributes and
  their `*_id` aliases expose the stored FK id, loaded explicitly or via
  `select_related()` + `get_related()`.
- Custom `ManyToMany(..., through=...)` models remain unsupported and continue
  to fail clearly.

---

## v0.5.54 — ORM Write & Relation Correctness

Released 2026-05-30.

This release focuses on targeted write-path consistency and relation safety
fixes. It does not claim that all ORM correctness issues are fixed.

### ORM Write & Relation Correctness

#### Fixed

- `bulk_create()` now aligns more closely with `create()` and `save()` for
  auto-managed fields, including non-null `updated_at` values for default
  timestamp fields.
- `bulk_create()` now runs field preparation hooks before insertion, so fields
  such as `Slug(auto_from=...)` behave consistently with `save()`.
- `bulk_create()` now determines insert columns after row preparation and
  preserves explicit per-row `auto_now_add` values such as `created_at` instead
  of silently ignoring later-row values.
- `bulk_update()` now casts `Vector` field CASE branch parameters with
  `CAST($n AS vector)`, matching normal vector update behavior.
- `ForeignKey` and `OneToOne` now validate `on_delete` values, normalize
  supported casing/aliases, and reject unknown actions before DDL generation.
- `on_delete=SET NULL` now requires `nullable=True` for `ForeignKey`,
  `OneToOne`, and migration relation field operations.
- Migration relation DDL now validates `ON DELETE` and `ON UPDATE` actions
  before emitting SQL, so arbitrary text cannot be interpolated into relation
  constraints.
- `ManyToMany(..., through=...)` now fails clearly because custom through
  models are not supported yet.
- The forward FK access contract is documented: forward FK/O2O attributes
  expose the stored FK value/id, while related objects should be loaded
  explicitly or through `select_related()` plus `get_related()`.

#### Changed

- `QuerySet.update()` now refreshes `auto_now` fields such as `updated_at` when
  regular fields are updated, matching `save()` more closely. Explicit
  `updated_at` values are respected, and `update(updated_at=...)` does not
  override itself.

#### Compatibility / Behavior Changes

- `QuerySet.update()` may now include `auto_now` fields such as `updated_at`
  when regular fields change. Explicit `updated_at` values remain respected,
  and `update(updated_at=...)` does not override itself.
- `ForeignKey(..., on_delete="SET_NULL")` and
  `ForeignKey(..., on_delete="SET NULL")` now require `nullable=True`.
  `SET NULL` on a non-nullable relation creates contradictory runtime and DDL
  semantics: the delete policy needs to write `NULL`, while the column rejects
  `NULL`.

  Before:

  ```python
  author = fields.ForeignKey(User, on_delete="SET_NULL")
  ```

  Now:

  ```python
  author = fields.ForeignKey(User, on_delete="SET_NULL", nullable=True)
  ```

- Invalid or arbitrary `on_delete` text now raises instead of being emitted into
  relation DDL.
- `ManyToMany(..., through=...)` now raises a clear unsupported-feature error
  instead of implying custom through model support.
- `bulk_update()` SQL for Vector fields now includes `CAST($n AS vector)`
  inside CASE branches.
- Aksara remains pre-1.0, and additional ORM correctness work remains planned.

#### Tests

- Added SQL-level and DB-backed regression coverage for `bulk_create()`
  timestamp handling, async field preparation, mixed explicit/implicit
  `created_at`, `QuerySet.update()` `updated_at` policy, F-expression updates,
  vector `bulk_update()` casting, relation `on_delete` validation, nullable
  `SET NULL` enforcement, migration DDL action validation, custom through
  rejection, and forward FK id access.

#### Remaining Known ORM Correctness Work

- Lazy forward FK object loading is not implemented; use explicit queries or
  `select_related()` with `get_related()`.
- Custom ManyToMany through models remain intentionally unsupported.
- Array item typing and nested array policy.
- Vector precision policy.
- FileField/ImageField `to_python()` contract.
- JSON scalar behavior.
- Other relation features intentionally not implemented by the current
  relation manager APIs.

---

## v0.5.53 — ORM Query Semantics & Migration Generation Correctness

Released 2026-05-29.

This release focuses on ORM query semantics correctness and migration generation
correctness. It does not claim that all ORM correctness work is complete,
and intentionally leaves write-path consistency, relation DDL safety, and
advanced field policy as planned follow-up work.

### ORM Query Semantics & NULL Correctness

This section covers focused ORM query-semantics fixes.

#### Fixed

- Exact `None` filters such as `filter(email=None)` and
  `filter(email__exact=None)` now compile to `IS NULL` instead of SQL equality
  against a NULL parameter.
- `__isnull` filters now use strict boolean parsing. Supported string values
  include `true`, `false`, `1`, `0`, `yes`, `no`, `y`, `n`, `on`, and `off`;
  invalid values now raise a clear validation error.
- Foreign key column aliases such as `author_id` are accepted in filters when
  they correspond to an actual `ForeignKey` or `OneToOne` database column.
- Reverse foreign key filters now work with the corrected FK alias handling.

### Migration Generation Correctness

#### Fixed

- New `CreateTable` migration operations are now ordered by foreign-key and one-to-one dependencies so referenced tables are emitted before dependent tables.
- `DropTable` migration operations now use reverse dependency order so dependent tables are dropped before referenced tables.
- Legacy `makemigrations --sql` output now uses the same FK dependency ordering.
- `models_to_migration_code()` now uses the same model dependency ordering and delegates field conversion through the autodetector path.
- Runtime `Array(nullable=False)` fields now emit `op.ArrayField(..., nullable=False)` instead of becoming nullable in generated migrations.
- Migration code generation now supports additional field operations, including `SmallIntegerField`, `TimeField`, `DurationField`, `SlugField`, `IPAddressField`, `BinaryField`, and `FilePathField`.

#### Tests

- Added regression coverage for FK dependency ordering across `CreateTable`, `DropTable`, legacy SQL output, executor delegation, Array nullability, and extended FieldOp code generation.

#### Remaining Known ORM Correctness Work

- `bulk_create()` and other write paths still need consistency work.
- `QuerySet.update()` still needs an explicit `updated_at` policy.
- Vector `bulk_update()` casting still needs follow-up work.
- Relation DDL safety remains on the planned follow-up backlog.
- Array, vector, and file advanced-field policy decisions remain open.

### Compatibility Notes

- `filter(field=None)` and `filter(field__exact=None)` now return rows where the
  field is `NULL`. Previously these queries compiled to equality against a `NULL`
  parameter and returned no rows. Code that relied on the old behavior of
  returning no results must be updated.
- `__isnull` parsing is stricter. String values like `"False"` and `"0"` are now
  treated as false. Invalid values now raise a validation error instead of
  being treated as truthy. Only the documented boolean and string forms are
  accepted.
- Foreign key column aliases such as `author_id` are now accepted in filters
  when they correspond to a real FK or O2O database column.
- Generated migration table ordering may change for apps with FK or O2O
  relationships. `CreateTable` operations are now ordered by dependency, so
  referenced tables appear before dependent tables in migration output.
- Generated migration code for `Array(nullable=False)` fields is now stricter;
  these fields now emit `nullable=False` correctly in migration output.
- Aksara remains pre-1.0. Additional ORM correctness work is planned.

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

This patch makes file-based migrations apply safely and consistently across the
CLI and test helper entry points, verifies the integrity of already-applied
migrations, and hardens the SQL that the framework generates. It does not change
the migration file format and does not require any action on existing projects.

### Migration execution safety

- **Transactional Python migrations**: every operation in a Python migration and
  the row that records the migration as applied now run inside a single
  transaction. If any operation fails, the whole migration rolls back and is
  never recorded as applied.
- **Statement-by-statement SQL migrations**: SQL migrations are split into
  individual statements and executed one at a time inside the same transaction
  as the recording step, so multi-statement SQL files apply completely instead
  of stopping after the first statement.
- **Advisory lock**: applying migrations now acquires a PostgreSQL advisory lock
  before inspecting and running pending migrations, so two processes cannot run
  migrations at the same time. The lock is always released, even on failure.
- **Cycle detection**: the migration dependency graph detects circular
  dependencies and raises a clear error naming the cycle instead of silently
  producing an incorrect order.

### Migration integrity

- **Checksums for Python and SQL migrations**: both Python and SQL migrations now
  store a checksum when applied. Before running pending migrations, the checksum
  of every already-applied migration is verified against the file on disk. A
  mismatch fails with the migration name and clear next steps, so a quietly
  edited migration cannot be applied as if unchanged.
- **Backward compatibility**: migrations recorded before this version may have no
  stored checksum. These are reported as a warning and remain valid — they are
  not rejected.
- **Safer generated non-null fields**: adding a non-null field without a default
  fails on a table that already has rows. Generated migrations now include a
  warning comment on such fields, pointing to a temporary default, a backfill, or
  a nullable-first data migration. Primary keys are exempt.

### Failure reporting

- **Strict graph loading by default**: a migration file that cannot be loaded now
  raises a clear error naming the migration, its path, and the underlying cause,
  instead of being silently skipped. A non-strict mode remains available for
  tooling that needs to inspect a partially broken graph.
- **Pending migrations skipped after a failure**: when a migration fails, the
  remaining pending migrations that were not attempted are reported, and the CLI
  shows which migrations were skipped.

### SQL-generation guardrails

- **Many-to-many constraint and column quoting**: join-table constraint names are
  deterministic, double-quoted, and bounded to PostgreSQL's identifier length
  limit; source and target column references are quoted.
- **Partial-index predicate validation**: an index `where` predicate is validated
  when it is defined. Obvious unsafe patterns — statement terminators, comments,
  and DDL/DML keywords — are rejected. Ordinary predicates such as
  `created_at > NOW()` are unaffected.
- **Array field type validation**: an array field's SQL type is validated against
  an allowlist of PostgreSQL base types and normalised to a canonical form.
  Injection-style input is rejected when the field is defined.
  **Compatibility note**: `ArrayField(sql_type="text[]")` now normalises to
  `"TEXT[]"`. A base type that is not on the allowlist raises an error when the
  field is defined; open an issue to have additional types added.

### Unified execution path

- **One canonical executor for file-based migrations**: `aksara migrate` and the
  testing helpers now apply file-based migrations through the same canonical
  executor. Previously the CLI and the test helper each had their own apply loop
  that bypassed transactions, the advisory lock, SQL statement splitting, and
  checksum recording.
- **Consistent guarantees for file-based CLI and test runs**: because those
  entry points now share the same executor for file-based migrations, CLI runs
  and test runs get the same transactions, advisory lock, SQL splitting,
  checksum recording, and checksum verification. Test environments no longer
  record empty checksums or emit spurious checksum warnings on later runs. The
  legacy model-based CLI fallback remains available for bootstrap scenarios and
  does not provide the full file-based migration integrity model.
- The dry-run preview path is unchanged.

### Compatibility notes

- The migration file format is unchanged. Existing migrations are not
  re-generated or altered.
- Legacy CLI helpers (`MIGRATION_TABLE_SQL`, `compute_checksum`,
  `ensure_migrations_table`, `get_applied_migrations`, and `record_migration`)
  remain importable from `aksara.cli.main` as compatibility shims; new code
  should import from `aksara.migrations.executor`.

### Deferred work

The following migration-metadata items are intentionally **not** part of this
patch and remain future work:

- Migration metadata schema versioning (a `schema_version` column).
- An app-label / name identity split (an `app_label` column and a
  `UNIQUE(app_label, name)` redesign of the tracking table).
- Automatic checksum backfill for historical rows. Backfilling automatically is
  unsafe because it would bless already-edited files with their current checksum
  and defeat tamper detection.
- A dedicated migration verify/backfill command.

### Tests

- Added unit and DB-backed test coverage for the new migration behavior:
  transactional application and rollback, fake-mode behavior, multi-statement SQL
  splitting, cycle detection, advisory lock acquisition and release, checksum
  recording and verification, strict graph loading, skipped-migration reporting,
  the SQL-generation guardrails, and the unified executor path shared by the CLI
  and the testing helpers.

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

- Added `aksara doctor launch-check`.
- Added `aksara examples validate`.
- Polished golden-path examples.
- Improved first-user docs.
- Added packaging sanity tests.
- Updated roadmap.
- Improved first-run Studio/AI guidance.

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
  `ValidationError` instead of relying on PostgreSQL to reject the value.
- `bulk_update()` now emits valid `CASE WHEN id = $n THEN $v END` SQL —
  previously the `WHEN` condition was a bare value, not a boolean expression.
- `bulk_create()` now uses DB column names for FK fields (`owner_id` not
  `owner`) in the INSERT column list.
- `upsert()` now calls `field.to_db()` for all values — previously raw
  Python values were sent to asyncpg, breaking JSON, Enum, DateTime, and
  other serialized field types.
- `upsert()` now emits `DO NOTHING` when no update fields are provided,
  instead of invalid `DO UPDATE SET` with no assignments.
- `upsert()` now uses DB column names for FK fields in both the INSERT
  column list and the `ON CONFLICT` target.

### Fixed — Migrations (Phase 2)

- Array fields now preserve PostgreSQL array types in generated migrations.
- JSON defaults with apostrophes are now correctly escaped in migration SQL.
- `AlterFieldDefault` now emits valid JSONB literal SQL for JSON defaults.
- Decimal defaults are now preserved correctly in generated migrations.
- Internal migrations are now ordered before user migrations during discovery.
- `apply_migrations()` now respects declared dependency order.

### Fixed — API Layer (Phase 3)

- Auto-generated ViewSet routes now publish concrete response models in
  OpenAPI schema instead of `Any`.
- `model_to_dict()` now includes ManyToMany fields declared in read schemas.
- Cursor pagination now correctly applies page size and cursor filtering.
- Serializer type mapping now uses concrete Python types instead of `Any`.

### Fixed — Security (Phase 4)

- `get_current_user()` no longer trusts the client-controlled `X-User-Id`
  header for user resolution — previously this allowed arbitrary
  user impersonation.
- Studio auth is no longer bypassed by `debug=True` when auth is required.
- Studio session-cookie auth path now uses DB-backed user lookup.
- `AIAgentMiddleware` now auto-registers so `DenyAI` can function correctly.

### Fixed — CLI (Phase 5)

- `aksara dbsetup` prompt order no longer misroutes username input into
  the port prompt.
- `aksara info` now includes configured `installed_apps`.
- `aksara info` now reports Studio availability using runtime gating
  semantics, not a hardcoded flag.
- CLI model discovery now honors `installed_apps` instead of a hardcoded
  shortlist.

### Fixed — Multi-tenancy & Background Tasks (Phase 7)

- `enqueue_task()` now persists tenant provenance at enqueue time.
- `TaskWorker` now restores tenant context before task execution.
- Empty or whitespace-only tenant headers now fail closed with HTTP 400
  instead of silently disabling tenant scoping.
- Task record schema now includes `tenant_id` field.

### Tests

- 33 targeted regression tests added across Phases 1–7.
- AI metadata propagation regression suite added in
  `tests/ai/test_ai_metadata_propagation.py`.
- Total suite: **6507 passed, 3 skipped**.

## [0.5.46] — Packaging and Docs Release Polish

### Changed
- Bumped package metadata, CLI version output, scaffold templates, example app metadata, and user-facing version references to **0.5.46**.

### Fixed
- PyPI project description assets now use absolute URLs so images render correctly on package pages.
- Documentation deployment installs the required MkDocs plugins and deploys using the repository's `docs/mkdocs.yml`.
- Documentation favicon now uses the Aksara logo in browser tabs.

## [0.5.45] — ORM Expressions, Native Multi-Tenancy, SDK Generation, and Real-Time Streams

### Added
- **`Q()` objects** for nested boolean filtering with `&`, `|`, and `~`.
- **`F()` expressions** for database-side field references in filters and updates.
- **`annotate()` and `aggregate()`** for model-level and summary aggregation.
- **Relation-aware aggregates** for one-hop reverse FK/O2O, forward M2M, reverse M2M, and forward FK/O2O paths.
- **`transaction.atomic`** as both an async decorator and context manager.
- **`TenantModel`** with automatic PostgreSQL RLS policy generation for tenant-scoped tables.
- **Tenant-aware connection context** across pooled, session-owned, and transaction-owned database access.
- **`aksara generate sdk --language typescript`** for fetch-based TypeScript CRUD clients.
- **`GET /<prefix>/stream`** SSE endpoints backed by PostgreSQL `LISTEN/NOTIFY`.
- **`FileField` and `ImageField`** with `FieldFile` wrappers, filesystem/S3 storage backends, and debug-mode media mounting.
- **Async email backends** with `ConsoleBackend`, `LocMemBackend`, `SMTPBackend`, `send_mail()`, and `send_mass_mail()`.
- **Request-scoped locale and timezone context** with `LocaleMiddleware`, `TimezoneMiddleware`, lazy `_()` strings, and UTC-normalized `DateTime` serialization.
- **`fields.GenericForeignKey()` and `ContentType` syncing** for model-agnostic relations across registered models.
- **`DurableStep`** for PostgreSQL-backed workflow step reuse and retry-safe execution.
- **11 new ORM field types** for Django parity: `SlugField`, `SmallIntegerField`, `BigIntegerField`, `PositiveIntegerField`, `PositiveSmallIntegerField`, `PositiveBigIntegerField`, `TimeField`, `DurationField`, `IPAddressField` / `GenericIPAddressField`, `BinaryField`, and `FilePathField`.
- **7 new migration FieldOp subclasses** in `aksara/migrations/operations.py` with correct PostgreSQL DDL generation (`SMALLINT`, `TIME`, `INTERVAL`, `INET`, `BYTEA`, `VARCHAR`).
- **Autodetector integration** for all 11 new field types — `makemigrations` now produces correct column types instead of falling back to `StringField`.
- **Field parameters** — `choices`, `min_length`, `min_value` / `max_value`, `auto_from`, `regex`, and `strip_whitespace` on the relevant core field types.

### Added — Field Parameters

- **`choices`** on `String`, `Integer`, `SmallInteger` — flat lists or tuple-pairs `[("val", "Label")]` for Django developer compatibility. Validates on write, passes valid values through to MCP tool exports.
- **`min_length`** on `String`, `Text` — minimum character length validation.
- **`min_value` / `max_value`** on `Integer`, `Float`, `Decimal` — range validation at the Python level before database writes.
- **`auto_from`** on `Slug` — generates slug from a named field on creation only; skipped if slug is already set (safe for existing URLs).
- **`regex`** on `String` — custom pattern validation.
- **`strip_whitespace`** on `String`, `Text` — trims leading/trailing whitespace on write path only (`to_db`).

### Fixed
- **`BigInteger.to_db()`**: Added BIGINT range validation to prevent PostgreSQL overflow.
- **`Time.to_python()`**: Replaced brittle `strptime` with `fromisoformat()` for microsecond and datetime support.
- **`FilePath.choices()`**: Fixed recursive mode to include directories when `allow_folders=True`.
- **`Slug` regex**: Changed to `re.ASCII` flag so non-ASCII characters are properly rejected when `allow_unicode=False`.
- **`IPAddress.to_python()`**: Now normalizes through `ipaddress.ip_address()` for consistent round-tripping.

### Documentation
- Added a dedicated ORM page covering expressions, aggregates, relation paths, and transactions.
- Added field, advanced, and settings docs for storage-backed media fields and async email configuration.
- Added advanced and settings docs for locale/timezone middleware and request-aware datetime serialization.
- Added an advanced guide for generic relations and durable workflows.
- **Updated ORM fields documentation** with full sections for all 11 new field types including options tables, PostgreSQL type mappings, validation rules, and usage examples.
- **Updated ORM Reference** field tables with `SmallInteger`, `PositiveInteger` variants, `Binary`, and `FilePath`.
- Refreshed the CLI startup examples to match the current `aksara dev` hero banner and `aksara dbsetup` success output.
- Documented the global CLI output controls for power users: `--quiet`, `--plain`, `--no-color`, and `--force-color`.
- Refreshed the release notes, API docs, and CLI docs for the full v0.5.45 feature set.

---
## [0.5.44] — Framework DX Enhancements (Phase 1)

### Added
- **API Filtering**: Pluggable DRF-style `SearchFilter` and `OrderingFilter` for `ModelViewSet`.
- **QuerySet DX**: Added `search(term, fields)` method for robust multi-field OR conditions.
- **Pagination DX**: Pluggable `LimitOffsetPagination` and `PageNumberPagination` backends.
- **Event Signals**: Added `aksara.signals` with `pre_save`, `post_save`, `pre_delete`, and `post_delete` model lifecycle hooks.

---

## [0.5.43] — 2026-04-30

### Added — CLI Database Setup
- **`aksara dbsetup` Command**: Introduced a new interactive CLI command to securely configure PostgreSQL database connections during onboarding. Replaces manual `createdb` and raw `psql` instructions across the framework.
- **Environment Variables**: Enforced environment-variable-first configuration for `DATABASE_URL`, removing hardcoded credentials from project scaffold templates.

### Changed — Documentation & Pedagogy Modernization
- **AI Security Patterns**: Updated all tutorials (`Blog API`, `CRM`, `Multi-Tenant`, etc.) to explicitly teach `ai_sensitive` and `ai_agent_writable` metadata on fields. PII and mutation-restricted fields are now secure-by-default in examples.
- **Router Correction**: Purged widespread documentation hallucination involving a DRF-style `Router` class. All tutorials, quickstarts, and API references now correctly demonstrate Aksara's actual `urlpatterns` list and `include_viewset` auto-discovery paradigms.
- **Project Scaffold**: Overhauled the `aksara startproject` base template to include modern AI metadata parameters and rely on the new `aksara dbsetup` flow.

---

## [0.5.42] — 2026-04-27

### Studio UX Redesign & Accessibility

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
- **S1** — Added `validate_patch_ast()` which parses AI-generated code patches with `ast.parse` before applying them and rejects dangerous built-ins, imports, and attribute accesses.
- **S2** — Split Studio protection into two independent FastAPI router dependencies: `_check_studio_origin` (CSRF prevention via Origin/Referer) and `verify_studio_auth` (session credentials).
- **S3** — Added HMAC-SHA256 signed agent tokens using stdlib only. Prevents timing attacks with `hmac.compare_digest`.
- **S4** — Added `sanitize_identifier()` and `sanitize_column_type()` for strict input sanitization for AI-generated SQL to prevent SQL injection.

### Refactoring
- **A1** — Audited LLM client adapters to confirm all HTTP communication uses Python stdlib `urllib`.
- **A2** — Merged intent engine v2.

---

## [0.5.36] — 2026-03-04

### Fixed — AI Sanity Sweep & Integration Hardening

- **Intent Router**: Expanded `_extract_context()` to extract route/model
  context for `debug`, `architecture_review`, and `performance_analysis` flow
  types. Hoisted `_SKIP_MODEL_WORDS` to module level for reuse across
  branches. Updated module docstring to v0.5.36 with expanded intent listing.
- **Studio XSS Fixes**: Wrapped all dynamic content in architecture review
  and performance analyzer render functions (`_renderArchFindings`,
  `_renderArchSuggestions`, `_renderPerfIssues`, `_renderPerfRecommendations`)
  with `_esc()` to prevent cross-site scripting. Escaped error handler
  messages and grade values in score cards.
- **Studio CSS**: Fixed version header from `v0.6.0` to `v0.5.36`.
- **Console Engine**: Fixed self-referential suggestions — each analyzer flow
  now suggests the other two analyzers instead of itself.
- **Graph Events**: Added validation warning for unknown event kinds in
  `emit_graph_event()`. Moved `EVENT_KINDS` frozenset above emitter function.
- **CLI**: Expanded performance command help text with full docstring and
  examples matching the review/debug pattern.
- **Version Alignment**: Updated module docstrings in `debugger.py`,
  `architecture_review.py`, `performance_analyzer.py`, `console_engine.py`,
  and `graph_events.py` to v0.5.36.

### Added — Tests
- **94 new tests** across 3 test files:
    - `tests/ai/test_intent_router.py`: 34 new tests in `TestConflictResolution`
      (25 tests) and `TestNewFlowContextExtraction` (9 tests) covering
      cross-flow routing precision and context extraction.
    - `tests/studio/test_studio_sanity_sweep.py`: 25 new tests in
      `TestV036AiPanelEscaping` (11), `TestV036AiPanelStates` (10), and
      `TestV036CssVersionHeader` (4) covering XSS prevention and UI states.
    - `tests/integration/test_ai_stack_smoke.py`: 35 new integration tests
      verifying all three analyzers run coherently on the same realistic
      project graph, console dispatch, CLI JSON purity, intent routing
      reachability, and graph event validation.

---

## [0.5.35] — 2026-03-03

### Added — AI Performance Analyzer
- **AI Performance Analyzer** (`aksara/ai/performance_analyzer.py`): Automated
  performance analysis engine with a 10-step pipeline — loads the Project
  Graph, collects query data, detects slow queries (> 200 ms), N+1 patterns,
  query explosions, missing indexes, heavy joins, and route hotspots, computes
  metrics and a penalty-based performance score (A–F grading), and generates
  category-specific improvement recommendations.
- **Data models**: `PerformanceMetrics`, `PerformanceIssue`,
  `PerformanceRecommendation`, `PerformanceReport` with full serialisation
  (`to_dict`, `to_summary_dict`).
- **Studio API endpoint**: `POST /studio/ai/performance-analysis`.
  New Pydantic models: `StudioPerformanceMetrics`,
  `StudioPerformanceIssue`, `StudioPerformanceRecommendation`,
  `StudioPerformanceAnalysisResponse`.
- **Studio UI "Performance" panel**: Score card with letter grade, metrics
  grid, two tabbed views (Issues with severity badges, Recommendations with
  impact indicators), and colour-coded grading.
- **Console integration**: 16 new performance analysis intent patterns in the
  intent router (`analyze performance`, `slow queries`, `n+1`, `missing
  index`, `why is my app slow`, etc.) with dedicated
  `_run_performance_analysis_flow` handler in the console engine.
- **CLI `aksara ai flows performance`**: Text and JSON output, `--json`,
  `--summary`, `--metrics`, and `--issues` options.
- **235 new tests** across 5 test files covering the core analyzer module,
  metrics/scoring computation, Studio API endpoint, Studio UI templates, and
  CLI command / console integration.

---

## [0.5.34] — 2026-03-02

### Added — AI Architecture Review
- **AI Architecture Review** (`aksara/ai/architecture_review.py`): Automated
  architectural analysis engine with a 9-step pipeline — loads the Project
  Graph, computes metrics (counts, averages, coupling score), detects coupling
  risks, schema design issues, API design problems, migration risks, and
  performance concerns, computes a penalty-based health score (A–F grading),
  and generates category-specific improvement suggestions.
- **Data models**: `ArchitectureMetrics`, `ArchitectureFinding`,
  `ArchitectureSuggestion`, `ArchitectureReport` with full serialisation
  (`to_dict`, `to_summary_dict`).
- **Studio API endpoint**: `POST /studio/ai/architecture-review`.
  New Pydantic models: `StudioArchitectureMetrics`,
  `StudioArchitectureFinding`, `StudioArchitectureSuggestion`,
  `StudioArchitectureReviewResponse`.
- **Studio UI "Architecture" panel**: Score card with letter grade, metrics
  grid, two tabbed views (Findings with severity badges, Suggestions with
  impact indicators), and colour-coded grading.
- **Console integration**: 12 new architecture review intent patterns in the
  intent router (`architecture review`, `health check`, `anti-pattern`,
  `coupling`, `refactor`, `design review`, etc.) with dedicated
  `_run_architecture_review_flow` handler in the console engine.
- **CLI `aksara ai flows review`**: Text and JSON output, `--json`,
  `--summary`, and `--metrics` options.
- **206 new tests** across 5 test files covering the core review module,
  metrics computation, Studio API endpoint, Studio UI templates, and CLI
  command / console integration.

---

## [0.5.33] — 2026-03-01

### Added — AI Debugger
- **AI Debugger** (`aksara/ai/debugger.py`): Automated root-cause analysis
  engine with a 6-step pipeline — loads the Project Graph, extracts an issue
  pool from diagnostics/gaps/events, filters by optional query, clusters
  issues by shared component, detects root causes via 6 heuristic patterns
  (database, migration, AI provider, route errors, security, general),
  ranks by confidence, and generates safe fix suggestions.
- **Data models**: `DebugIssue`, `IssueCluster`, `RootCause`, `DebugReport`
  with full serialisation (`to_dict`, `to_summary_dict`).
- **Studio API endpoint**: `POST /studio/ai/debug` with optional query body.
  New Pydantic models: `StudioDebugRequest`, `StudioDebugResponse`,
  `StudioDebugIssue`, `StudioDebugCluster`, `StudioDebugRootCause`.
- **Studio UI "AI Debugger" panel**: Query toolbar, summary grid, 4 tabbed
  views (Root Causes, Clusters, Issues, Fix Plan) with severity colour-coding
  and confidence badges.
- **Console integration**: 12 new debug intent patterns in the intent router
  (`debug`, `root cause`, `why fails`, `diagnose`, `troubleshoot`, etc.)
  with dedicated `_run_debug_flow` handler in the console engine.
- **CLI `aksara ai debug`**: Text and JSON output, `--query`, `--json`,
  `--summary`, `--model`, and `--route` options.
- **187 new tests** across 5 test files covering the core debugger module,
  clustering logic, Studio API endpoint, Studio UI templates, and CLI command.

---

## [0.5.32] — 2026-02-28

### Added — Project Context Graph + Event Timeline
- **Project Graph** (`aksara/ai/project_graph.py`): Structured representation
  of the application as nodes and relationships.  9 collectors gather data from
  ModelRegistry, routes, DB tracing, migrations, diagnostics, gap analysis,
  AI Hub, AI Flows, and graph events.  Heuristic model inference from routes,
  SQL, and migration names.  Thread-safe 5-second cache with rebuild support.
- **Graph Events** (`aksara/ai/graph_events.py`): Lightweight in-memory event
  timeline (bounded deque, max 500).  `emit_graph_event()` records events;
  hooks in diagnostics, AI flows, runtime, gap analysis, and console engine.
  10 event kinds for AI correlation.
- **Graph Context** (`aksara/ai/graph_context.py`): Transforms ProjectGraph
  into AI-friendly payloads — summary, console (flow-type-aware), debug, and
  formatted prompt section.
- **Console Integration**: Graph context automatically injected into AI Console
  prompts.  Events emitted after each console execution.
- **API endpoints**: `GET /studio/ai/project-graph` (full or summary),
  `GET /studio/ai/project-graph/events` (with limit), and
  `GET /studio/ai/project-graph/summary`.
- **Graph Explorer UI**: New Studio sidebar page with counts grid, 7 tabbed
  panels (Models, Routes, Queries, Diagnostics, Migrations, Events,
  Relationships), Rebuild button, and Use in Console link.
- **CLI `aksara ai graph`**: Show graph summary, JSON output, events, or
  force rebuild from the terminal.
- **Event emission hooks**: Diagnostics, AI flows, runtime, gap analysis,
  and console engine emit graph events for AI correlation.
- **193 new tests** across 6 test files covering all new modules, endpoints,
  UI templates, and CLI commands.

---

## [0.5.31] — 2026-02-25

### Added — Interactive AI Console
- **Intent Router** (`aksara/ai/intent_router.py`): Rule-based intent
  detection mapping natural-language commands to AI Flow actions.
  `detect_intent()` returns `IntentMatch` with flow_type, action_key,
  confidence, and extracted context.  `suggest_commands()` for autocomplete.
  `list_intents()` for UI enumeration.
- **Console Engine** (`aksara/ai/console_engine.py`): Full pipeline
  orchestrator — `run_console_query()` detects intent → builds context →
  dispatches to AI Flow → executes via runtime → returns structured response.
- **Context Builder** (`aksara/ai/console_context.py`): Enriches extracted
  context with live registry data (model names, route defaults, etc.).
- **API endpoints**: `POST /studio/ai/console` (natural-language console
  query) and `GET /studio/ai/console/suggest` (autocomplete suggestions).
  New Pydantic models: `StudioAiConsoleRequest`, `StudioAiConsoleResponse`,
  `StudioAiConsoleSuggestResponse`.
- **Studio UI "AI Console" panel**: Interactive chat-style console with
  message bubbles, loading animation, example command buttons, command
  suggestions dropdown, and suggested next-action chips.  Sidebar nav item
  with terminal icon.
- **Keyboard shortcut**: `Ctrl+I` / `Cmd+I` opens the AI Console and focuses
  the input field.  `↑/↓` for history and suggestion navigation.
- **CLI `aksara ai chat`**: Send natural-language commands from the terminal.
  Supports `--provider`, `--model`, `--format text|json`.
- **150+ new tests** across 5 files: `test_intent_router.py`,
  `test_console_engine.py`, `test_console_context.py`,
  `test_ai_console.py`, `test_ai_chat_cli.py`.
- **Docs**: `ai-mode/console.md`, updated `mkdocs.yml`, `changelog.md`.

### Safety
- Console follows "AI suggests, developer confirms" — never auto-modifies
  code, executes migrations, or applies DB changes.
- Intent router uses local heuristics only — no LLM calls for routing.

---

## [0.5.30] — 2026-02-24

### Added — AI Connectors & Execution Runtime
- **AI Connectors** (`aksara/ai/connectors/`): Pluggable connector layer with
  4 providers — `OpenAIConnector`, `AnthropicConnector`, `OllamaConnector`,
  `HttpConnector`.  Common `AIConnector` base class with normalised response
  shape.  Connector registry with `get_connector()` factory.
- **Execution Runtime** (`aksara/ai/runtime.py`): `run_prompt_pack()` async
  function that resolves provider/model, selects connector, executes prompt
  pack, and returns normalised result.  Opt-in — existing prompt packs remain
  deterministic.
- **Flow Execution** (`aksara/studio/ai_flows.py`): 7 new functions —
  `execute_flow()`, `execute_model_flow()`, `execute_route_flow()`,
  `execute_query_flow()`, `execute_migration_flow()`,
  `execute_diagnostic_flow()`, `_dispatch_builder()`.
- **API endpoint** `POST /studio/ai/flows/run`: Execute a flow through a
  connector.  New Pydantic models: `StudioAiFlowRunRequest`,
  `StudioAiFlowRunResponse`.
- **Studio UI "Run AI" button**: Execute flows directly from the AI Flow
  panel.  Shows execution result with provider, model, elapsed time, and
  token usage.
- **CLI `aksara ai run`** subcommand group: `model`, `route`, `query`,
  `migration`, `diagnostic`.  Supports `--provider`, `--model`, `--format`.
- **120+ new tests** across 4 files: `test_connectors.py`, `test_runtime.py`,
  `test_ai_execution.py`, `test_ai_run_cli.py`.
- **Docs**: `ai-mode/connectors.md`, `ai-mode/runtime.md`, updated
  `flows.md`, `changelog.md`, `mkdocs.yml`.

### Safety
- Execution is **opt-in** — flows still return prompt packs by default.
- Runtime **never modifies code automatically** — only suggests/analyzes.

---

## [0.5.29] — 2026-02-23

### Added — Studio AI Flows
- **AI Flow Builders** (`aksara/studio/ai_flows.py`): 11 registered actions
  across 5 kinds (model, route, query, migration, diagnostic).  Each action
  returns a deterministic prompt pack (system prompt + user prompt) — no
  external API calls.  Risk-tagged (`low`/`medium`/`high`).
- **6 new API endpoints** under `/studio/ai/flows/`: `actions` (GET),
  `model`, `route`, `query`, `migration`, `diagnostic` (all POST).
  11 new Pydantic models in `aksara/studio/models.py`.
- **Studio UI**: AI Flow dropdown buttons in all 5 section headers (Models,
  Routes, Migrations, Diagnostics, DB Queries).  Reusable slide-over AI Flow
  Panel with 3-tab layout (Result, Prompt Pack, Raw JSON), copy buttons,
  risk badges, suggested next actions.  Buttons disabled until AI Hub
  configured.  `Shift+A` keyboard shortcut.
- **CLI `aksara ai flows`** subcommand group: `actions`, `model`, `route`,
  `query`, `migration`, `diagnostic`.  Supports `--format text|json`.
- **183 new tests** across 3 files: backend builders, UI wiring, CLI parity.

---

## [0.5.28] — 2026-02-22

### Added — AI Hub 2.0
- **Unified AI Hub Config** (`aksara/ai/hub_settings.py`): Pydantic models for
  centralised provider configuration — `AiHubSettings`, `ProviderConfig`,
  `AiDefaultModels`, per-provider configs (OpenAI, Azure, Anthropic, Ollama,
  Custom HTTP).  Functions: `load_aihub_settings()`, `save_aihub_settings()`,
  `resolve_defaults()`.
- **AI Hub API** (7 new endpoints under `/studio/ai-hub/`): `status`,
  `providers`, `models`, `configure`, `configure/secret`, `defaults`, `test`.
  15 new Pydantic models and 9 builder functions in Studio utils.
- **Studio UI AI Hub Panel**: 4 new tabs (Overview, Models, Routing, Onboarding)
  alongside existing 5 tabs.  Global sidebar AI status indicator with
  ready/partial/disabled states.  Alt+A keyboard shortcut.  Onboarding wizard
  with 5-step setup flow.
- **AI Hub wiring**: `AiFullContext.ai_hub_summary` field,
  `build_agent_workflow()` AI Hub metadata injection (try/except wrapped),
  `get_embedding_provider()` falls back to AI Hub defaults,
  `check_ai_hub_config()` diagnostics checker.
- **CLI `aksara ai-hub` group**: Subcommands `status`, `providers`, `models`,
  `defaults`, `configure`, `doctor`.  Supports `--format pretty|json`.
- **Gap Analysis**: New `ai_hub` category (ninth check) with 6 gap codes:
  `AI_HUB_NO_PROVIDER`, `AI_HUB_ACTIVE_PROVIDER_UNCONFIGURED`,
  `AI_HUB_DEFAULTS_NO_CHAT`, `AI_HUB_DEFAULTS_NO_EMBEDDINGS`,
  `AI_HUB_SEARCH_EMBEDDING_MISMATCH`, `AI_HUB_AGENT_NO_MODEL`.
  Fix-plan commands for each actionable gap.
- **Doctor**: `aksara doctor ai` now includes `check_ai_hub_config`.

### Deprecated
- `ai_profiles_enabled`, `ai_default_provider`, `ai_providers`,
  `ai_secret_hints` settings in `aksara/conf.py` — superseded by AI Hub 2.0.
  Will be removed in v0.6.
- `embedding_provider`/`embedding_model` settings now fall back to AI Hub
  defaults when set to `"local"`.

### Changed
- `aksara/search/embeddings.py`: `get_embedding_provider()` tries AI Hub
  defaults before falling back to `"local"` (only if provider is registered).
- `aksara/diagnostics.py`: Added `check_ai_hub_config` to `run_all_checks`.
- Gap Analysis engine now has 9 categories (was 8).

---

## [0.5.27] — 2026-02-21

### Fixed
- **CLI grammar**: "Run a Aksara" → "Run an Aksara" in `run` command help
- **CLI error handling**: `aksara inspect queries` now catches errors and shows
  a user-friendly message instead of a stack trace
- **Gap Analysis logging**: `run_gap_analysis_for_category` now logs warnings
  instead of silently swallowing exceptions
- **Studio `jsonPost` consolidation**: Removed 3 duplicate `jsonPost` definitions
  (copy-paste bug) and consolidated into one canonical definition near `jsonGet`
- **Studio UX**: Replaced `alert()` with `showToast()` in query plan explainer
  for consistent notification style
- **Stale version tag**: Removed obsolete `v0.5.0: Studio Core & Handshake`
  from CLI `studio` group docstring

### Added
- **Gap Analysis Studio panel**: Navigation item, template, `renderGaps()` and
  `loadGapAnalysis()` functions with severity filter buttons (All / Critical /
  Errors / Warnings / Info) and Re-scan action
- **Keyboard shortcuts**: `6` = Gap Analysis, `7` = DB Queries, `8` = AI Hub;
  `g` key navigates to Gap Analysis panel

### Changed
- Keyboard shortcut mapping reorganised to accommodate the new Gaps panel
- Docs and help text aligned with current behaviour

---

## [0.5.25] — 2026-02-21

### Added
- **Unified AI Provider System**: New `UnifiedAiProvider` class in `aksara.ai.providers_unified`
  — single configuration object for all AI features with `from_env()`, `from_dict()`,
  `from_json_file()`, `is_configured()`, `ping()`, `get_llm_client()`, `to_safe_dict()`,
  `save_to_env_file()`, `save_to_json()` methods
- **LLM Client Adapters**: 5 zero-dependency adapters (all use urllib, no SDK required):
  OpenAI, Azure OpenAI, Anthropic, Ollama, Custom HTTP — in `aksara.ai.llm_clients/`
- **AI Hub Studio Section**: New sidebar tab with 4 sub-tabs (Providers, Tools,
  Context Viewer, Agent) — keyboard shortcut `A`, agent prompt with `Cmd+Enter`
- **Studio API Endpoints**: 4 new endpoints under `/studio/ai/hub/`:
  `GET providers`, `POST providers/save`, `POST providers/ping`, `POST agent/run`
- **CLI `ai-provider` Commands**: `list`, `detect`, `ping`, `configure` subcommands
  for managing AI providers from the command line
- **Provider Auto-Detection**: Scans environment variables with priority order:
  OpenAI → Anthropic → Azure → Ollama → Custom

### Changed
- `aksara.conf` now auto-populates `ai_default_provider` from unified provider when not set
- `aksara.ai.__init__` exports new unified provider and LLM client types

### Docs
- New: `docs/ai-mode/hub.md` — AI Hub documentation
- New: `docs/ai-mode/custom-http.md` — Custom HTTP provider guide
- New: `docs/ai-mode/ollama.md` — Ollama local LLM guide
- Updated: `docs/ai-mode/providers.md` — unified provider section added
- Updated: `docs/changelog.md` — this entry

### Tests
- 90+ new tests in `tests/test_v025_ai_hub.py` covering: provider system,
  adapters (mocked HTTP), Studio models, build utilities, CLI commands,
  Studio UI templates, integration & non-regression

---

## [0.5.24] — 2026-02-20

### Changed
- **AI Circular Import Cleanup**: Introduced explicit `_get_*` lazy-import helpers in
  `aksara.ai.workflows` (`_get_run_all_checks`, `_get_search_index_and_builder`,
  `_get_playbook`) — same runtime behaviour, stable patch targets for tests
- **Search Indexer Import Hygiene**: Six `_get_*` helpers in `aksara.search.indexers`
  (`_get_model_registry`, `_get_routes_builder`, `_get_migration_graph`,
  `_get_query_stats`, `_get_settings`, `_get_builtin_playbooks`)
- **Diagnostics Import Helpers**: Three `_get_*` helpers in `aksara.diagnostics`
  (`_get_settings`, `_get_ai_profile_validators`, `_get_ai_secret_hints`)
- All test patch targets updated to use the new helpers

### Fixed
- **CLI Exit Codes**: `aksara migrate` and `aksara status` now exit with code 1
  (not 0) when `DATABASE_URL` is missing — includes actionable hints
- **CLI Error Handling**: `aksara doctor run`, `aksara agent workflow`,
  `aksara search query`, and `aksara search index` no longer show raw stack
  traces — wrapped in try/except with user-friendly messages and `sys.exit(1)`
- **Studio Error Feedback**: `fetchMigrations`, `loadAgentContext`,
  `loadAgentPlaybooks`, and `spotlightSearch` now show `showToast()` errors
  instead of silently failing

### Docs
- Roadmap updated to reflect v0.5.24 as current stable
- Changelog entry added

---

## [0.5.23] — 2026-02-20

### Added
- **Agentic Workflows v1 — Plans, Not Pushes**: Structured execution plans from free-text goals
  - **`AgentWorkflow` model**: Ordered list of steps with goal, playbook, source, and metadata
  - **`AgentWorkflowStep` model**: Actionable step with kind, risk, effort, commands, and notes
  - **`AgentWorkflowRequest` / `AgentWorkflowResponse` models**: API request/response types
  - **10 step kinds**: `inspect`, `search`, `edit_file`, `run_migration`, `run_query`, `run_test`, `environment`, `config`, `diagnostics`, `doc_reading`

- **Workflow Builder** (`aksara.ai.workflows`):
  - **`build_agent_workflow()`**: Combine diagnostics, inspectors, search, and playbooks into one plan
  - **`summarize_agent_workflow()`**: Natural-language summary of a workflow
  - **`workflow_stats()`**: Step counts by kind, risk, and effort
  - Five sub-builders: diagnostic steps, search steps, inspector steps, playbook steps, test step
  - Deterministic ordering: diagnostics (1–49), inspectors (50–99), search (100–199), playbooks (200–299), test (300)

- **Studio Workflow UI**:
  - **Generate Workflow** button in Agent panel alongside existing Generate Prompt
  - **Workflow tab** with step timeline, risk/effort badges, copy-able commands, and summary stats
  - Diagnostics/search toggle checkboxes and search query override input

- **Studio API Endpoints**:
  - **`POST /studio/agent/workflow`**: Generate a workflow from a goal
  - **`GET /studio/agent/workflow/sample`**: Sample workflow for demonstration

- **CLI `aksara agent workflow` command**:
  - `--playbook`, `--no-diagnostics`, `--no-search`, `--search-query`, `--limit-search`, `--limit-diagnostics`
  - `--format text|json` output modes

---

## [0.5.22] — 2026-02-19

### Added
- **Semantic Search & AI Index**: Cross-referenced code intelligence with unified search
  - **`SearchDocument` model**: Structured document with kind, title, summary, content, metadata, tags
  - **`SearchResult` model**: Ranked result with score, highlights, and match type
  - **`SearchIndex`**: In-memory TF-IDF search index with keyword, semantic, and hybrid modes
  - **`LocalTfIdfEmbedder`**: Built-in bag-of-words embedding provider (no external dependencies)
  - **`BaseEmbeddingProvider` protocol**: Extensible interface for pluggable embedding backends
  - **Index builders**: Auto-index models, routes, migrations, queries, settings, playbooks
  - **`build_full_index()`**: Build complete search index from all project artifacts

- **Studio Spotlight**: ⌘K / Ctrl+K command palette for instant project search
  - Fuzzy + semantic search across all indexed artifacts
  - Category filter buttons (All, Models, Routes, Settings, Playbooks, Migrations, Queries)
  - Keyboard navigation (↑↓ navigate, Enter open, Tab preview, Esc close)
  - Preview pane with document details and metadata
  - Real-time debounced search

- **Search Studio API**:
  - **`GET /studio/search/index`**: Index statistics and document counts
  - **`POST /studio/search/query`**: Full search with filters and scoring
  - **`StudioSearchRequest`, `StudioSearchResultSet`, `StudioSearchIndexInfo` models**

- **CLI `aksara search` command group**:
  - **`aksara search query`**: Search with `--kind`, `--semantic`, `--json`, `--min-score`
  - **`aksara search index`**: Show index statistics
  - JSON output for piping to agent mode

- **Agent Mode integration**:
  - **12th context section `semantic_index`**: Search index stats in agent context
  - **8th playbook `identify_root_cause_from_search`**: Cross-reference search for root cause analysis

- **Settings**: `semantic_search_enabled`, `embedding_provider`, `embedding_model`, `embedding_dimensions`, `search_index_backend`

- **`aksara/search/` package**: New module for semantic search engine, embeddings, and indexers

---

## [0.5.21] — 2026-02-18

### Added
- **Query Inspector 2.0**: Deep SQL plan analysis and aggregate statistics
  - **`QueryPlanRequest` / `QueryPlanResult` models**: EXPLAIN plan request/response with estimated cost and warnings
  - **`QueryStats` model**: Aggregate statistics with totals, averages, slow threshold, top slow queries, N+1 count, by-operation breakdown
  - **`explain_query()`**: Run EXPLAIN on SQL with real DB or synthetic fallback
  - **`get_query_stats()`**: Compute aggregate stats from trace storage
  - **`POST /studio/db/plan`**: EXPLAIN plan endpoint
  - **Studio UI slow query highlight**: Red border, 🔥 badge, "Explain Plan" button on slow queries
  - **Agent context `query_stats` section**: Section 10 of 11 with aggregate query stats

- **Model Inspector 1.0**: Deep model introspection for schema analysis
  - **`ModelInspectorField` model**: Per-field metadata (type, nullable, unique, default, max_length, choices, AI flags)
  - **`ModelInspectorRelationship` model**: FK/M2M relationship metadata with target model, on_delete, through table
  - **`ModelInspectorConstraint` model**: Inferred constraints (primary_key, unique, index)
  - **`ModelInspectorSummary` model**: Full inspection with fields, relationships, constraints, CREATE TABLE SQL, auto-comments
  - **`inspect_model()` / `inspect_all_models()`**: Deep model introspection functions
  - **`GET /studio/models/inspect/{model_name}`**: Single model inspection endpoint (404 if not found)
  - **`GET /studio/models/inspect/all`**: All models inspection with aggregate counts
  - **Studio UI Inspector tab**: Nav link, summary cards, model cards with field/relationship tables, keyboard shortcut (9)
  - **Agent context `schema_analysis` section**: Section 11 of 11 with deep schema analysis

- **`aksara/inspectors/` package**: New module for inspection utilities
  - `aksara/inspectors/models.py` — Model inspector models and functions
  - `aksara/inspectors/queries.py` — Query inspector models and functions

- **CLI `aksara inspect` commands**:
  - `aksara inspect models` — List all models with metadata, `--model`, `--fields`, `--relationships`, `--json` flags
  - `aksara inspect queries` — Query stats and slow queries, `--limit`, `--json` flags

- **~100+ new tests**: Model inspector, query inspector, Studio endpoint, CLI command tests

- **Documentation**: Inspectors section with Query Inspector and Model Inspector guides

### Changed
- Agent context now gathers 11 sections (was 9) — added `query_stats` and `schema_analysis`
- CLI version bumped to 0.5.21
- Studio `__init__.py` exports updated with inspector models and utils

### Technical Notes
- **No breaking changes**: All new endpoints, models, and CLI commands; existing API unchanged
- **Zero new dependencies**: Synthetic plan fallback eliminates need for live DB in tests
- **Vanilla JS maintained**: Inspector tab uses zero external dependencies

---

## [0.5.20] — 2026-02-17

### Added
- **Agent Playbooks**: Opinionated, reusable recipes for common LLM-assisted development tasks
  - **7 Built-in Playbooks**: `add_field_to_model`, `add_api_action_to_viewset`, `fix_migration_conflicts`, `add_validation_rule`, `harden_endpoint_permissions`, `debug_slow_queries`, `refactor_model_and_serializer`
  - **`AgentPlaybook` / `AgentPlaybookStep` models**: Playbook recipe with kind, category, risk level, usage kind, steps, tags, default goal template
  - **`AgentPlaybookSet` model**: Collection with aggregate counts by category/risk/usage
  - **`StudioAgentPlaybookPromptRequest` model**: Playbook-driven prompt request
  - **`aksara/ai/playbooks.py` registry**: `get_builtin_playbooks()` with category/risk/usage filters, `get_playbook_by_key()`, `build_playbook_set()`
  - **`build_agent_prompt_from_playbook()`**: Playbook-aware prompt builder with step listing, risk/usage header, and default goal/section fallback
  - **`GET /studio/agent/playbooks`**: List playbooks with optional category/risk_level/usage_kind filters
  - **`POST /studio/agent/playbooks/prompt`**: Playbook-driven prompt generation with 404 for unknown keys
  - **CLI `aksara agent playbooks`**: List playbooks with `--format`, `--category`, `--risk`, `--usage` flags
  - **CLI `aksara agent playbook-run <key>`**: Run a playbook with `--goal`, `--sections`, `--format` flags
  - **Studio UI Playbooks sidebar**: Search box, category filter pills, playbook cards with risk badges, click-to-select with auto-prefill of goal and sections, step preview, Shift+P keyboard shortcut
  - **~72 new tests**: Registry/model tests, prompt builder tests, endpoint tests, CLI tests, UI structure tests
  - **Documentation**: Playbooks section in Agent Mode guide

### Changed
- CLI version bumped to 0.5.20
- Studio `__init__.py` exports updated with Playbook models and utils
- Agent panel grid width increased from 300px to 320px for playbook sidebar

### Technical Notes
- **No breaking changes**: All new endpoints and models; existing API unchanged
- **Zero new dependencies**: Vanilla JS maintained throughout
- **Playbook registry is in-memory**: No database tables; all 7 playbooks are hardcoded for deterministic behavior

---

## [0.5.19] — 2026-02-16

### Added
- **Agent Mode**: Build LLM-ready system prompts from project context
  - **`AgentContextSection` model**: Section container with title, key, data payload, and auto-computed `size_kb`
  - **`StudioAgentContext` model**: Aggregated context with 9 sections, timestamp, and total size
  - **`StudioAgentPromptRequest` / `StudioAgentPromptResponse` models**: Goal-driven prompt generation with model/temperature recommendations
  - **`build_agent_context()`**: Async builder gathering project_info, models, routes, migrations, diagnostics, ai_profiles, ai_hints, db_queries, schema_checksum
  - **`build_agent_prompt()`**: Section-filtered system prompt assembly with token estimation
  - **`GET /studio/agent/context`**: Full agent context endpoint
  - **`POST /studio/agent/prompt`**: Prompt generation endpoint
  - **CLI `aksara agent context`**: Context inspection with `--sections`, `--output`, `--summary`, `--size` flags
  - **CLI `aksara agent prompt`**: Prompt generation with `--goal`, `--sections`, `--custom-system-prompt`, `--format` flags
  - **Studio UI Agent panel**: Section checkboxes, goal textarea, Prompt/Context JSON tabs, keyboard shortcuts (8, ⌘G/Ctrl+G), localStorage persistence
  - **~89 new tests**: Context builder, prompt generator, CLI commands, UI integration tests
  - **Documentation**: Agent Mode guide under AI Mode

### Changed
- CLI version bumped to 0.5.19
- Studio `__init__.py` exports updated with Agent Mode models and utils

### Technical Notes
- **No breaking changes**: All new endpoints and models; existing API unchanged
- **Zero new dependencies**: Vanilla JS maintained throughout
- **Smart recommendations**: Temperature lowers for high-risk hints or diagnostic errors; model picked from ready AI profiles

---

## [0.5.18] — 2026-02-15

### Added
- **Autoremediation Hints**: Every diagnostic issue now includes structured fix actions
  - **`DiagnosticAction` model**: Machine-readable fix instructions with `kind` (set_env, run_command, open_doc, edit_file, add_setting), `target`, `title`, `example`, and `description` fields
  - **`build_action()` helper**: Convenience function for creating `DiagnosticAction` instances
  - **`actions` field on `DiagnosticIssue`**: List of autoremediation actions attached to every issue
  - All 8 diagnostic checkers enhanced with contextual fix actions
  - **Studio UI "Fix This Issue"**: Expandable action cards per issue with kind icons, titles, example snippets, and copy-to-clipboard buttons
  - **CLI `aksara doctor fix-plan`**: New subcommand with `--format text|json`, `--only-errors`, `--only-with-actions` flags
  - **CLI `aksara doctor run`**: Now shows actions with kind labels and examples in pretty output
  - **Documentation**: Autoremediation guide with action model reference, CLI usage, and CI/CD integration
  - **~60 new tests**: Action model tests, checker action attachment tests, endpoint tests, CLI fix-plan tests

### Changed
- CLI version bumped to 0.5.18
- Diagnostics engine docstring updated for v0.5.18
- `__all__` exports updated with `DiagnosticAction`, `DiagnosticActionKind`, `build_action`

### Technical Notes
- **No breaking changes**: `actions` field defaults to empty list; existing code unaffected
- **Zero new dependencies**: Vanilla JS maintained, Pydantic auto-serializes new field
- **Backward compatible API**: `GET /studio/diagnostics` response gains `actions` array per issue

---

## [0.5.17] — 2026-02-14

### Added
- **Self-Diagnostics & Doctor Mode**: Complete self-diagnostics engine
  - **Core Engine** (`aksara/diagnostics.py`): Pydantic-based `DiagnosticIssue` and `DiagnosticReport` models with 8 checker functions covering database connectivity, migrations status, AI profiles, AI provider secrets, required settings, cache availability, file-system permissions, and security
  - **Studio Endpoint**: `GET /studio/diagnostics` returns full `DiagnosticReport` JSON
  - **Studio Diagnostics 2.0 Panel**: Summary banner with severity counts, issue cards with kind/severity badges and fix hints, category filters (All/Errors/Warnings/Info), search input, 10-second auto-refresh with Live/Paused toggle
  - **Keyboard Shortcuts**: `d` navigates to Diagnostics, `/` focuses search, `Esc` clears and blurs search
  - **CLI `aksara doctor`**: New command group with four subcommands:
    - `doctor run` — Run all checks (pretty or `--format json`; exit code 0/1)
    - `doctor summary` — Categorized issue counts table
    - `doctor ai` — AI-specific checks only
    - `doctor db` — Database-specific checks only
  - **Documentation**: Full diagnostics guide with data models, CI/CD integration, keyboard shortcuts

### Changed
- CLI version bumped to 0.5.17
- Studio app.js version header updated to v0.5.17
- Diagnostics panel upgraded from basic runtime info to full self-diagnostics engine

### Technical Notes
- **No breaking changes**: All existing Studio API endpoints unchanged
- **No new dependencies**: Zero-build vanilla JS maintained
- **~100 new tests**: Model tests, checker tests, CLI tests, endpoint tests, UI smoke tests

---

## [0.5.16] — 2026-02-13

### Added
- **Studio UX Pass #2**: Comprehensive dashboard polish release
  - **Migrations Panel**: Search toolbar with text filter and status dropdown (All / Applied / Pending / Conflict); colored status badges (APPLIED green, PENDING yellow, CONFLICT red) per app
  - **AI Profiles Tabs**: Reorganized into four tabs — Profiles, Secrets, Health, Hints — defaults to Health tab when validation errors exist
  - **Query Inspector Auto-Refresh**: Live/Paused toggle button with 5-second polling interval; "Updated HH:MM:SS" timestamp; auto-stops when navigating away
  - **Keyboard Shortcuts**: Keys 1–7 navigate to Overview, Models, Routes, Migrations, DB Queries, AI Profiles, Diagnostics; ignored when typing in input fields
  - **CLI `studio url --section`**: New `--section` flag accepts section names and appends `#/section` fragment to dashboard URL

### Changed
- CLI version bumped to 0.5.16
- Studio app.js version header updated to v0.5.16

### Technical Notes
- **No breaking changes**: All Studio API endpoints unchanged; HTML/CSS/JS only
- **No new dependencies**: Zero-build vanilla JS maintained

---

## [0.5.15] — 2026-02-13

### Added
- **"Hello World for Humans" DX Pass**: Documentation and discoverability improvements
  - **Refreshed README.md**:
    - Product-grade hero section with tagline
    - Features at a Glance with 6 key bullet points
    - 30-second Quickstart snippet
    - Patterns & Examples overview table
    - Clear status badge and version info
    - Streamlined Contributing and License sections
  
  - **"Your First 10 Minutes" Tutorial** (`docs/getting-started/ten-minutes.md`):
    - Step-by-step guide from install to running app
    - Prerequisites table (Python 3.11+, PostgreSQL 14+)
    - 8 clear steps: Install → Model → Admin → ViewSet → Register → Configure → Migrate/Run → Explore
    - What's Next section linking to patterns and examples
    - Common Questions FAQ
  
  - **"Choosing a Pattern" Guide** (`docs/getting-started/patterns.md`):
    - Quick decision table for pattern selection
    - Detailed sections for each pattern type
    - Comparison table with features matrix
    - Clear recommended paths based on use case
  
  - **Examples README** (`examples/README.md`):
    - Quick overview table of all examples
    - Detailed sections for: Blog, CRM, Multitenant, AI Providers, Basic App
    - Running instructions for each example
    - Contributing guidelines for new examples

### Changed
- CLI version bumped to 0.5.15
- Updated mkdocs nav with new Getting Started entries

### Technical Notes
- **No runtime changes**: This is a docs-only release with no changes to core ORM, migrations, or Studio

---

## [0.5.14] — 2026-02-13

### Added
- **Real-World AI Provider Wiring Examples**: Show developers how to wire Aksara's AI contracts to actual providers
  - **Protocol-Based Adapters** (`examples/ai_providers/adapters.py`):
    - `LlmClient` Protocol with `complete()` and `chat()` methods
    - `BaseLlmClient` abstract base class
    - `OpenAIClient` adapter for OpenAI API
    - `AzureOpenAIClient` adapter for Azure OpenAI Service
    - `AnthropicClient` adapter for Anthropic Claude
    - Soft SDK imports with clear error messages when SDK missing
    - `get_llm_client(provider, ...)` factory function
    - `get_llm_client_from_settings(settings)` helper
    - `check_sdk_availability()` utility
  
  - **Environment-Based Configuration** (`examples/ai_providers/settings.py`):
    - `Settings` class extending `AksaraSettings`
    - `AI_DEFAULT_PROVIDER` setting
    - `OPENAI_API_KEY`, `OPENAI_DEFAULT_MODEL`, `OPENAI_ORG_ID`
    - `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`
    - `ANTHROPIC_API_KEY`, `ANTHROPIC_DEFAULT_MODEL`
    - `is_provider_configured(provider)` validation method
    - `get_configured_providers()` helper
    - `validate_ai_config()` health check
  
  - **Prompt Building Utilities** (`examples/ai_providers/prompting.py`):
    - `build_prompt_for_route(hint, user_input)` - Build prompts from AI hints
    - `build_chat_messages_for_route(hint, user_input)` - Build chat messages
    - `format_structured_output_prompt(...)` - Request JSON responses
    - `parse_json_response(response)` - Parse JSON from LLM output
    - `extract_tags_from_response(response)` - Parse tag lists
    - Template helpers for common tasks
  
  - **Example Views** (`examples/ai_providers/views.py`):
    - `DemoPostViewSet` with AI-powered actions
    - `ai_suggest_tags` - Tag suggestion using AI hints
    - `ai_generate_summary` - Content summarization
    - `ai_analyze` - Content analysis with structured output
    - `get_ai_client_status()` utility for health checks
  
  - **Example App** (`examples/ai_providers/main.py`):
    - Complete FastAPI app with AI wiring
    - Lifespan manager for startup validation
    - `/ai/status` endpoint for provider readiness
    - `/ai/providers` endpoint listing configured providers
    - `/ai/test` endpoint for connection testing
  
  - **CLI Command** (`aksara ai examples`):
    - `aksara ai examples` - Show overview
    - `--provider openai|azure|anthropic` - Provider-specific setup info
    - `--list` / `-l` - List available example files
    - `--output-dir` / `-o` - Copy examples to project directory
    - `--force` / `-f` - Overwrite existing files
  
  - **Studio Enhancement**:
    - `client_ready` field on `StudioAiProviderSummary`
    - `_check_provider_ready(kind, settings)` utility
    - Providers panel now shows "Client Ready?" status
  
  - **Documentation** (`docs/ai-mode/bring-your-own-llm.md`):
    - Complete guide for wiring providers
    - Quick start guide
    - Adapter pattern explanation
    - Provider-specific setup instructions
    - Security best practices
    - Troubleshooting guide

### Changed
- CLI version bumped to 0.5.14
- `StudioAiProviderSummary` model now includes `client_ready` field
- `build_ai_profile_set_summary()` populates provider readiness

### Technical Notes
- **No hard SDK dependencies**: Provider SDKs (openai, anthropic) remain optional
- **Environment-first configuration**: All credentials from environment variables
- **Protocol-based design**: Easy to add new providers by implementing `LlmClient`

---

## [0.5.13] — 2026-02-12

### Added
- **Per-View AI Hints (Route-Level AI Metadata)**: Rich metadata for LLM guidance
  - **Core Hint Models** (`aksara/ai/models.py`):
    - `AiRiskLevel` type literal (low, medium, high)
    - `AiUsageKind` type literal (read_only, write, admin)
    - `AiRouteHint` model for per-route AI metadata
    - `AiHintSet` model with computed risk breakdown
  
  - **Developer API** (`aksara/ai/hints.py`):
    - `@ai_route_hint(title, description, ...)` decorator for viewset actions
    - `set_view_default_hint(cls, ...)` for class-level defaults
    - `get_ai_route_hint(func)` to retrieve hint from decorated function
    - `extract_hints_from_viewset(cls)` to extract hints from a viewset
    - `extract_hints_from_app(module)` to extract hints from entire app
    - `build_ai_hint_set(settings)` to build complete hint set
  
  - **Hint Metadata Fields**:
    - `title` - Human-readable action title
    - `description` - Detailed description
    - `view_name` / `route_name` - View and action identifiers
    - `path` / `http_method` - Route path and HTTP method
    - `usage_kind` - read_only, write, or admin
    - `risk_level` - low, medium, or high
    - `example_prompt` - Sample natural language prompt
    - `example_input` / `example_output` - Sample request/response
    - `recommended_model` / `recommended_provider` - Suggestions for LLM
  
  - **Context Integration**:
    - `AiRouteHintInfo` model for lightweight context export
    - `AiFullContext.ai_hints` - List of all route hints
    - `AiFullContext.ai_hint_count` - Total hint count
  
  - **CLI Command** (`aksara ai hints`):
    - `--view` / `-v` - Filter by view/viewset name
    - `--route` / `-r` - Filter by action/route name
    - `--risk` - Filter by risk level (low/medium/high)
    - `--format text|json` - Output format
    - Color-coded risk badges in text output
    - Risk breakdown summary (high/medium/low counts)
  
  - **Studio Backend**:
    - `GET /studio/ai/hints` - Returns `StudioAiHintSet`
    - `StudioAiRouteHint` and `StudioAiHintSet` models
    - `build_ai_hints(app)` utility function
  
  - **Studio UI**:
    - New "AI Route Hints" panel in AI Profiles section
    - Searchable/filterable hint list
    - Expandable hint cards with full details
    - Risk level badges (color-coded)
    - Usage kind badges

### Changed
- CLI version bumped to 0.5.13
- AI module exports updated with hints components
- Studio UI enhanced with hints panel

### Documentation
- New `docs/ai-mode/hints.md` - Complete AI hints documentation
- Changelog updated with v0.5.13 features

---

## [0.5.12] — 2026-02-11

### Added
- **AI Profiles Validation & Linting**: Hardened AI contracts with validation, linting, and health reporting
  - **Core Validation API** (`aksara/ai/providers.py`):
    - `AiProfileIssueSeverity` type literal (info, warning, error)
    - `AiProfileIssueKind` type literal (8 issue kinds)
    - `AiProfileIssue` model for individual validation issues
    - `AiProfileHealth` model for validation results
    - `validate_profile_set(profile_set)` - Validate any profile set
    - `validate_default_profile_set()` - Validate current app configuration
    - `classify_issue_severity(kind)` - Get severity for issue kind
  
  - **Detected Issues**:
    - `empty_profile_set` - No providers configured
    - `duplicate_provider_name` - Provider names must be unique
    - `duplicate_model_name` - Model names must be unique per provider
    - `unknown_provider_kind` - Provider kind not in valid set
    - `unknown_model_kind` - Model kind not in valid set
    - `missing_default_provider` - Default provider not set or invalid reference
    - `invalid_model_reference` - Default model doesn't exist in provider
    - `missing_required_field` - Required field not provided
  
  - **CLI Validation** (`aksara ai validate`):
    - `--format text|json` - Output format (default: text)
    - Exit code 0 on valid, 1 on errors
    - Color-coded severity badges in text output
    - Full health JSON export for CI/CD integration
  
  - **Studio Health Endpoint**:
    - `GET /studio/ai/health` - Returns `StudioAiProfileHealth`
    - `StudioAiProfileIssue` and `StudioAiProfileHealth` models
    - `build_ai_profile_health(app)` utility function
  
  - **Studio UI Health Badge**:
    - Health banner in AI Profiles panel
    - Green OK badge or red ERROR badge with counts
    - Issues list with severity indicators
    - Auto-loads on panel render

### Changed
- CLI version bumped to 0.5.12
- AI module exports updated with validation components

### Documentation
- Changelog updated with v0.5.12 AI Profiles Validation features

---

## [0.5.11] — 2026-02-10

### Added
- **AI Profiles & Provider Contracts**: Vendor-agnostic, pluggable AI configuration layer
  - **Core AI Provider Models** (`aksara/ai/providers.py`):
    - `AiModelProfile` - Individual model metadata (name, kind, token limits, capabilities)
    - `AiProviderProfile` - Provider with multiple models (OpenAI, Anthropic, local, etc.)
    - `AiProfileSet` - Collection of providers with default selection
    - `AiProviderSecretHint` - Safe env var hints (never exposes actual secrets)
    - `AiProviderConfigInfo` - Complete provider configuration info
    - Type aliases: `AiModelKind` (chat, completion, embedding, etc.), `AiProviderKind`
    
  - **AI Provider Registry**:
    - `AiProviderRegistry` class for runtime provider management
    - `get_ai_provider_registry(app)` - Get or create registry from FastAPI app
    - `build_default_ai_profile_set(settings)` - Build from settings or use examples
    - `build_example_profile_set()` - Demo providers for testing
    - Built-in example providers: `example_openai_like`, `example_anthropic_like`, `example_local`
  
  - **Studio Backend Endpoints**:
    - `GET /studio/ai/profiles` - List all configured AI providers and models
    - `GET /studio/ai/secrets` - List env var hints with configured status
    - New Pydantic models in `studio/models.py` for Studio responses
    - `build_ai_profile_set_summary()` and `build_ai_secrets_info()` utilities
  
  - **Studio UI Panel**:
    - New "AI Profiles" navigation item in Studio sidebar
    - Stats cards: Providers, Models, Configured Secrets, Default Provider
    - Provider cards with model lists, capabilities, token limits
    - Secrets panel showing env var configuration status
    - Export panel for JSON configuration
  
  - **CLI Commands** (`aksara ai` command group):
    - `aksara ai providers` - List providers with `--format table|json`
    - `aksara ai models` - List models with optional `--provider` filter
    - `aksara ai secrets` - Show secret configuration status

- **Configuration Options**:
  - `ai_profiles_enabled` / `AKSARA_AI_PROFILES_ENABLED` - Enable/disable profiles (default: True)
  - `ai_default_provider` / `AKSARA_AI_DEFAULT_PROVIDER` - Default provider name
  - `ai_providers` / `AKSARA_AI_PROVIDERS` - Explicit provider configurations (JSON)
  - `ai_secret_hints` / `AKSARA_AI_SECRET_HINTS` - Custom secret hints (JSON)

### Security
- AI secrets are NEVER exposed via Studio or CLI - only env var names and configured status
- No vendor SDK dependencies - pure metadata/configuration layer

### Changed
- CLI version bumped to 0.5.11
- AI module exports updated with new providers module components

### Documentation
- Changelog updated with v0.5.11 AI Profiles features

---

## [0.5.10] — 2026-02-09

### Added
- **Query Inspector & ORM Profiler**: Comprehensive database query tracing and visibility
  - **Core Tracing Layer** (`aksara/db/tracing.py`):
    - `DbQueryTrace` dataclass for individual query captures (SQL, params, timing, operation, table, call site, tags)
    - `DbQueryBatch` dataclass for per-request query collections with aggregations
    - Contextvar-based session management (`start_trace_session`, `stop_trace_session`, `record_query`)
    - In-memory ring buffer storage for recent traces (configurable max size)
    - Automatic SQL operation extraction (SELECT/INSERT/UPDATE/DELETE/etc.)
    - Automatic table name extraction from queries
    - SQL normalization for query grouping and N+1 detection
    - N+1 query pattern detection heuristics (configurable threshold)
  
  - **Request Lifecycle Integration**:
    - New `QueryTraceMiddleware` for automatic per-request tracing
    - Integration with `QueryLogger` to record all queries when tracing enabled
    - Request ID correlation via existing `request_id_var` contextvar
    - Automatic capture of HTTP method, path, and status code
  
  - **Studio Backend Endpoints**:
    - `GET /studio/db/queries` - Query inspector with stats, recent batches, slow queries
    - `GET /studio/db/queries/{request_id}` - Detailed query batch for specific request
    - New Pydantic models: `StudioQueryTrace`, `StudioQueryBatch`, `StudioQueryStats`, `StudioQueryInspector`
  
  - **Studio UI Panel**:
    - New "DB & Queries" navigation item in Studio sidebar
    - Stats cards: Total Queries, Avg Per Request, Slow Queries, N+1 Detected
    - Slowest Queries panel with SQL preview and call site info
    - Recent Requests panel with method, path, status, query count, timing
    - Warning highlights for slow queries and N+1 patterns
    - Disabled tracing banner with configuration instructions
  
  - **CLI Tools** (`aksara db` command group):
    - `aksara db stats` - Show aggregate query statistics
    - `aksara db profile` - Show detailed profile data (slow queries, recent batches)
    - `aksara db clear` - Clear stored trace data

- **Configuration Options**:
  - `db_trace_enabled` / `AKSARA_DB_TRACE_ENABLED` - Enable/disable tracing (default: False)
  - `db_trace_slow_threshold_ms` / `AKSARA_DB_TRACE_SLOW_THRESHOLD_MS` - Slow query threshold (default: 100ms)
  - `db_trace_max_queries` / `AKSARA_DB_TRACE_MAX_QUERIES` - Max queries per request (default: 500)

### Changed
- `QueryLogger` now always captures timing (not just in debug mode) for tracing integration
- CLI version bumped to 0.5.10

### Documentation
- Changelog updated with v0.5.10 Query Inspector features

---

## [0.5.9] — 2026-02-08

### Added
- **Admin UI 2.0 - DX & UX Pass**: Major admin interface overhaul
  - **Theme Toggle Button**: Visible dark/light mode toggle in header
    - Uses `localStorage` for persistence (`aksara-admin-theme`)
    - Respects `prefers-color-scheme` as default
    - Smooth icon transition between sun/moon
  - **Studio Link**: Header link to AI Studio when enabled
  - **Improved Breadcrumbs**: SVG chevron separators, aria-label support
  - **Record Count Badges**: Show count in list view headers
  - **Sticky Form Actions**: Form save/cancel/delete actions stick to bottom
  - **Search UX**: New search card with icon, clear button styling
  - **Empty States**: Improved SVG icons replacing emoji
  - **Dashboard Cards**: New `.dashboard-card` component with hover effects
  - **Model Links**: First column in list view is now clickable link to edit

- **JSON Widget Enhancements** (json_widget.js v0.5.9):
  - Auto-format JSON on blur
  - Auto-format on paste
  - JSON structure info (array/object count)
  - Improved error focus and scrolling

- **Array Widget Enhancements** (array_widget.js v0.5.9):
  - Drag-and-drop reordering
  - Drag handle with grip icon
  - Smooth remove animation
  - Enter key to add new item
  - Count badge support
  - Warning message for max items

- **Responsive Improvements**:
  - Mobile sidebar with overlay
  - Collapsible form actions
  - Mobile-friendly tables
  - Breakpoints at 1024px, 768px, 480px

### Changed
- CSS version updated to 0.5.9
- Badge for DEBUG mode changed from `badge-success` to `badge-warning`
- Form templates use `form-input` class instead of `form-control`
- Index template uses SVG icons instead of emoji
- Model list uses SVG icons in empty states and actions
- Theme localStorage key changed to `aksara-admin-theme`

### Fixed
- Theme toggle now updates icon visibility correctly on page load
- Array widget preserves value when clearing last item

### Documentation
- Admin UI 2.0 changes documented in changelog

---

## [0.5.8] — 2026-02-07

### Added
- **Example Hardening & Golden Paths**: Production-adjacent patterns for examples
- **API Key Authentication** for Blog and CRM examples:
  - New `auth.py` modules with `require_api_key` dependency
  - `X-API-Key` header authentication pattern
  - Environment variable support (`BLOG_API_KEY`, `CRM_API_KEY`)
- **Pagination & Ordering Support**:
  - `page` and `page_size` query parameters on list endpoints
  - `order_by` query parameter (prefix with `-` for descending)
  - `DEFAULT_PAGE_SIZE=10`, `MAX_PAGE_SIZE=100` settings
  - Filter parameters: `is_published` (Blog), `status`/`stage` (CRM)
- **AI-Ready Endpoints** on all example apps:
  - `POST /api/posts/{id}/ai-suggest-tags/` - Keyword-based tag suggestions (Blog)
  - `GET /api/customers/{id}/ai-context/` - Customer context summary (CRM)
  - `GET /api/tenants/{id}/ai-overview/` - Tenant model overview (Multitenant)
  - All endpoints marked with `ai_exposed=True`, `ai_name`, `ai_description`
  - Discoverable at `/ai/tools` for LLM integration
- **New Test Coverage**:
  - Auth module tests (verify_api_key, require_api_key)
  - Pagination settings tests
  - AI endpoint tests

### Changed
- ViewSet tags updated to "Blog API", "CRM API", "Multitenant API"
- STAGE_ORDER and STAGE_PROBABILITIES moved to module level in CRM
- Example ViewSets now use `dependencies` for auth
- UserSerializer returns `.model_dump()` in CRM views

### Documentation
- New "Authentication (v0.5.8)" sections in patterns docs
- New "Pagination & Ordering (v0.5.8)" sections with examples
- New "AI-Ready Endpoints (v0.5.8)" sections with usage examples
- Updated API endpoint tables with new AI endpoints

---

## [0.5.7] — 2026-02-06

### Added
- **Patterns & Example Packs**: Real-world starter templates
- **New Example Apps**:
  - `examples/blog/` - Full blogging backend with Post, Comment, tags, publish action
  - `examples/crm/` - Simple CRM with Customer, Deal, forecast endpoint
  - `examples/multitenant/` - Multi-tenant SaaS example with tenant middleware
- **Template Support for `aksara startproject`**:
  - `aksara startproject myblog --template blog`
  - `aksara startproject mycrm --template crm`
  - `aksara startproject mysaas --template multitenant`
- **New CLI Commands**:
  - `aksara templates list` - List available templates
- **New Documentation**:
  - `docs/patterns/` - Patterns & Recipes section
  - `patterns/blog.md` - Blog tutorial
  - `patterns/crm.md` - CRM patterns
  - `patterns/multitenant.md` - Multi-tenant patterns

### Changed
- Scaffold templates updated to v0.5.7
- `startproject` now supports `--template` option

### Documentation
- New "Patterns & Recipes" section with real-world examples
- Updated CLI help with template options

---

## [0.5.6] — 2026-02-06

### Added
- **Dev Server Banner Upgrade**: Enhanced `aksara dev` output with:
  - Aksara version display
  - Environment (dev/prod) and debug status
  - All relevant URLs: App, Admin, Studio, API, Docs
  - URLs only shown when feature is enabled
- **Welcome Page in Scaffold**: New projects include a welcome page at `/`:
  - Shows Aksara branding and version
  - "Your Aksara project is running 🚀" confirmation
  - Quick links to Admin, Studio, API, Docs, AI Tools
  - Note about how to customize
- **`aksara info` Polish**: Enhanced environment information display:
  - Framework section with version info
  - Environment section (dev/prod, debug, migrations dir)
  - Database section with backend detection and masked URL
  - Features section showing Admin/Studio/AI Mode status

### Changed
- Dev banner now shows version from `aksara.__version__`
- Scaffold templates updated to v0.5.6
- `aksara info` uses cleaner, aligned formatting

### Documentation
- Updated quickstart.md with new dev banner and welcome page
- Added v0.5.6 changelog entry

---

## [0.5.5] — 2026-02-06

### Added
- **Boilerplate Refresh & Starter Project**: Fresh scaffold for new projects
- **Updated `aksara startproject`**:
  - Creates working Post model + API + Admin out-of-the-box
  - Pre-configured for Admin, Studio, AI Mode
  - Includes middleware (Request ID, Logging)
  - AKSARA configuration dict in settings.py
- **New Scaffold Files**:
  - `models.py` - Working Post model with AI metadata
  - `views.py` - PostViewSet with custom actions
  - `serializers.py` - PostSerializer ready to use
  - `admin.py` - Post registered with ModelAdmin
  - `urls.py` - Post routes pre-registered
- **Updated Project Structure**:
  ```
  myproject/
  ├── main.py          # Admin, Studio, AI auto-mounted
  ├── settings.py      # AKSARA config dict
  ├── app/
  │   ├── models.py    # Working Post model
  │   ├── views.py     # PostViewSet
  │   ├── admin.py     # Post admin
  │   └── ...
  ```
- **Zero-Config Experience**:
  - `/admin` - Admin ready (debug mode)
  - `/studio/ui` - Studio dashboard ready
  - `/ai/tools` - Post ViewSet as AI tool
  - `/api/posts` - CRUD API ready

### Changed
- Scaffold pyproject.toml now requires `aksara>=0.5.5`
- README.md in scaffold now shows all available endpoints
- Example app (examples/basic_app) updated to v0.5.5 patterns
- Quickstart docs updated to match new scaffold

### Documentation
- Updated quickstart.md with new project structure
- Updated example app README.md

---

## [0.5.4] — 2026-02-06

### Added
- **Studio ↔ AI Integration**: Connect Studio with AI tools (LLM-agnostic)
- **New Endpoints**:
  - `GET /studio/ai/context` - AI context export (models, routes, tools, checksums)
  - `GET /studio/ai/schemas` - JSON Schemas for AI operations (plan, patch, query, codegen)
  - `GET /studio/ai/prompts` - Prompt templates for external AI tools
- **New Pydantic Models** (v0.5.4):
  - `StudioAiProjectMeta` - Project metadata for AI context
  - `StudioAiModelSummary` - Lightweight model info for AI
  - `StudioAiRouteSummary` - Route info for AI context
  - `StudioAiToolInfo` - Tool descriptions for AI agents
  - `StudioAiContextExport` - Complete AI context bundle
  - `StudioAiSchemas` - JSON schemas container
  - `StudioAiPromptTemplate` - Single prompt template
  - `StudioAiPrompts` - Prompt templates collection
- **Studio UI "AI Helpers" Panel**:
  - AI Context Export - Copy JSON context for AI assistants
  - AI Schemas - Browse/copy schemas for plan, patch, query, codegen
  - Prompt Templates - Pre-built prompts with placeholders
  - Copy buttons with toast notifications
- **New CLI Command**:
  - `aksara studio ai-context` - Export AI context from CLI
  - `--format json|summary` option

### Important
- **LLM-agnostic**: No AI providers bundled or called
- **No secrets exposed**: AI context filters sensitive data
- **Safe by default**: All new endpoints are read-only

---

## [0.5.3] — 2026-02-06

### Added
- **Studio UI (Phase 1: Static Dashboard)**
  - Embedded zero-build, zero-dependency admin dashboard
  - Clean HTML/CSS/Vanilla JS architecture
  - Light and dark theme support
  - Responsive layout (mobile-friendly)
- **Dashboard Sections**:
  - System Overview - Version info, uptime, environment status
  - Models & Schema - Browse models with field types and relations
  - Routes Explorer - All registered endpoints with filtering
  - Migrations - Status, pending count, conflicts
  - Diagnostics - Live monitoring with 5-second auto-refresh
  - API Explorer - Quick endpoint reference
- **New Endpoints**:
  - `GET /studio/ui` - Serves the dashboard HTML
  - `GET /studio/assets/*` - Serves static assets (CSS, JS, icons)
- **New CLI Commands**:
  - `aksara studio open` - Opens dashboard in browser
  - `aksara studio ui-path` - Shows static assets path
- **New Settings**:
  - `studio_ui_enabled` - Enable/disable the UI (default: True)
  - `studio_ui_auto_open` - Auto-open on server start (future)
  - `studio_ui_title` - Customizable UI title

### Changed
- Version bump from 0.5.2 to 0.5.3
- `aksara studio url` now includes dashboard URL
- Static assets bundled with package

### Security
- UI respects `studio_allowed_origins` setting
- UI disabled in production by default (requires `studio_expose_in_production`)
- Directory traversal protection on assets endpoint

---

## [0.5.2] — 2026-02-15


### Added
- **Runtime Diagnostics Endpoints**: Real-time server introspection
  - `GET /studio/runtime/info` - Process info, uptime, database status, pending migrations
  - `GET /studio/runtime/routes` - Complete route listing with metadata (studio/admin/ai flags)
- **New Pydantic Models**:
  - `StudioRuntimeInfo` - Runtime diagnostics (version, python, debug, env, pid, uptime, etc.)
  - `StudioRouteInfo` - Route metadata (path, methods, name, app_label, is_studio, is_admin, is_ai)
- **Enhanced `aksara dev` Command**:
  - Beautiful startup banner showing App name, URL, Studio URL, Docs URL
  - `--log-level` option (default: info)
  - Clean shutdown message on Ctrl+C
- **Smarter `aksara shell`**:
  - `aquery(Model, **filters)` - Async query helper for quick lookups
  - `run()` - Alias for `arun()` (simpler)
  - Auto-imports app and settings
  - Improved banner showing preloaded objects

### Changed
- Version bump from 0.5.1 to 0.5.2
- Shell now automatically connects to database from settings

---

## [0.5.1] — 2026-02-10

### Added
- **Studio Core Polish**: Richer summaries and security improvements
- **New Endpoints**:
  - `GET /studio/migrations/summary` - Per-app migration statistics with conflict detection
  - `GET /studio/schema/handshake` - JSON Schema for StudioHandshake model (TypeScript generation)
- **Enhanced Context Summary**: 
  - `app_count` - Number of installed/configured apps
  - `database_status` - Live database connection status
  - `migration_status` - Quick migration health overview
  - `schema_checksum` - Convenience property accessor
- **New Pydantic Models**:
  - `StudioMigrationStatus` - Migration health summary
  - `StudioAppMigrationSummary` - Per-app migration stats
  - `StudioMigrationConflict` - Conflict details
  - `StudioMigrationSummary` - Complete migration summary response
- **Origin-based Security**: 
  - Request `Origin` header validation against `studio_allowed_origins`
  - Wildcard (`*`) support for development
  - Missing origin allowed for same-origin/CLI requests

### Security
- Studio endpoints now validate incoming `Origin` header
- Requests from non-allowed origins receive 403 Forbidden
- Clear separation between development and production security

### Changed
- Improved migration discovery to include Python migrations (not just .sql)
- Studio router now applies origin check dependency to all endpoints

---

## [0.5.0] — 2026-02-01

### Added
- **Studio Core & Handshake**: Complete IDE integration foundation
- **Studio Endpoints**:
  - `GET /studio/handshake` - Complete project handshake for Studio IDE
  - `GET /studio/context/summary` - Lightweight schema summary
  - `GET /studio/health` - Health check with database status
- **Studio CLI Commands**:
  - `aksara studio handshake` - Test handshake locally
  - `aksara studio url` - Show Studio endpoint URLs
- **Studio Settings**:
  - `enable_studio` - Enable/disable Studio endpoints (default: True)
  - `studio_expose_in_production` - Allow Studio in non-debug mode
  - `studio_allowed_origins` - CORS origins for Studio access
- Pydantic models for Studio responses:
  - `StudioHandshake`, `StudioCapability`, `StudioDatabaseStatus`
  - `StudioProjectInfo`, `StudioChecksums`, `StudioContextSummary`
  - `StudioHealthResponse`, `StudioModelSummary`
- Checksum utilities for cache invalidation
- Comprehensive Studio documentation in `docs/docs/studio/`
- 21 new Studio unit tests

### Changed
- Version bump from 0.4.11 to 0.5.0
- Studio endpoints automatically enabled in debug mode
- AI registry setup now also mounts Studio router

### Security
- Studio endpoints disabled in production by default
- Requires explicit `studio_expose_in_production=True` to enable in production

---

## [0.4.11] — 2026-01-31

### Added
- **Admin UI/UX Overhaul**: Modern, responsive admin interface
- **JSONAdminWidget**: Interactive JSON editor with syntax highlighting
- **ArrayAdminWidget**: Dynamic list editor for array fields
- **Array Field**: Native PostgreSQL array support (`TEXT[]`, `INTEGER[]`, etc.)
- Auto-detection of JSON and Array fields for widget assignment
- Dark mode support in admin interface
- Mobile-responsive admin sidebar

### Changed
- Redesigned admin templates with modern CSS
- Improved admin navigation with collapsible sidebar
- Enhanced form field rendering with specialized widgets

### Fixed
- Template syntax errors in admin base template
- Widget render method signature consistency
- Admin URL generation for model list views

---

## [0.4.10] — 2026-01-20

### Added
- Aksara rename release (formerly Vidyut)
- Updated all package references and imports

### Changed
- Package name from `vidyut` to `aksara`
- CLI command from `vidyut` to `aksara`
- All internal module references updated

---

## [0.4.9] — 2025-01-14

### Fixed
- Version alignment across `__init__.py`, `pyproject.toml`, and documentation
- Test stability improvements across all 2015 tests
- Admin permission checks for model access
- Migration executor edge cases

### Changed
- Improved error messages for validation failures
- Enhanced debug page AI suggestions
- Better query profiling output format

### Documentation
- Complete documentation rewrite with MkDocs + Material
- Added comprehensive tutorials
- Added AI Mode documentation

---

## [0.4.8] — 2025-01-10

### Added
- AI Mode: Schema Doctor for automated schema analysis
- AI Mode: Patch Engine for safe code modifications
- Multi-app autodiscovery improvements

### Fixed
- M2M relationship expansion batching
- Query capture in debug mode
- Tenant middleware context propagation

---

## [0.4.7] — 2025-01-05

### Added
- AI Mode: Agent Runtime for executing AI agents
- AI Mode: Planner for multi-step task planning
- CLI `ai agent` and `ai plan` commands

### Fixed
- Select related with nested prefetch
- Admin site registration ordering
- Logging middleware request body handling

---

## [0.4.6] — 2024-12-28

### Added
- AI Mode: Codegen for generating models, viewsets, serializers
- AI Mode: Context Engine for gathering code context
- CLI `ai generate` command

### Changed
- Improved migration conflict detection
- Better error pages in debug mode

### Fixed
- ForeignKey on_delete behavior
- Serializer validation ordering

---

## [0.4.5] — 2024-12-20

### Added
- AI Mode: Query Engine for natural language queries
- CLI `ai query` command
- AI debug tab in error pages

### Changed
- Enhanced admin interface styling
- Improved ViewSet action routing

### Fixed
- Pagination with complex filters
- Request ID middleware propagation

---

## [0.4.4] — 2024-12-15

### Added
- Basic AI Mode infrastructure
- AI configuration settings
- OpenAI and Anthropic provider support

### Changed
- Refactored middleware stack
- Improved settings validation

---

## [0.4.3] — 2024-12-10

### Added
- Admin interface with ModelAdmin
- Admin permissions system
- Admin site customization

### Fixed
- Model Meta inheritance
- Many-to-many through models

---

## [0.4.2] — 2024-12-05

### Added
- Request ID middleware
- Tenant middleware
- Logging middleware with JSON format

### Changed
- Middleware execution order
- Request object attributes

---

## [0.4.1] — 2024-12-01

### Added
- Debug error pages with context
- Query profiling tools
- Development toolbar

### Fixed
- Hot reload in development
- Static file serving

---

## [0.4.0] — 2024-11-25

### Added
- Complete API framework
- ModelViewSet with full CRUD
- Custom actions with @action decorator
- Serializers with validation
- Permission classes
- Authentication backends
- Pagination classes
- Filtering and search

### Changed
- Major API redesign
- New routing system
- Improved type hints

### Breaking Changes
- ViewSet API changed
- Serializer API changed
- Router registration changed

---

## [0.3.0] — 2024-10-15

### Added
- Migration system
- Migration operations
- Migration executor
- CLI migration commands

### Changed
- Model field definitions
- Database schema generation

---

## [0.2.0] — 2024-09-01

### Added
- Full ORM implementation
- All field types
- QuerySet API
- Relationships (FK, M2M)
- Manager customization

### Changed
- Model base class
- Field descriptor protocol

---

## [0.1.0] — 2024-07-15

### Added
- Initial release
- Basic Model class
- Core field types
- Simple queries
- CLI scaffolding
- Project structure

---

## Version Numbering

Aksara follows [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes (backwards compatible)

---

## Upgrade Guides

### 0.3.x → 0.4.x

1. Update ViewSet imports:
```python
# Old
from aksara.views import ViewSet

# New
from aksara.api import ViewSet, ModelViewSet
```

2. Update serializer definitions:
```python
# Old
class UserSerializer(Serializer):
    class Meta:
        model = User

# New
class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name"]
```

3. Update router registration:
```python
# Old
router.add_route("/users", UserViewSet)

# New
include_viewset(app, UserViewSet)
```

### 0.2.x → 0.3.x

1. Create initial migration:
```bash
aksara makemigrations --initial
```

2. Apply migrations:
```bash
aksara migrate
```

---

## Links

- [GitHub Releases](https://github.com/aksara/aksara/releases)
- [Roadmap](roadmap.md)
- [Migration Guides](getting-started/index.md)
