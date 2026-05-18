# Changelog

All notable changes to Aksara are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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

- **DjangoFilterBackend** (`aksara/api/filters.py`): Automatic query parameter filtering with Django ORM lookup syntax support
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
  - `BaseFilterBackend`, `DjangoFilterBackend`, `SearchFilter`, `OrderingFilter`
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
