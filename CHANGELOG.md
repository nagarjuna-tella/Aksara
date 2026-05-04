# Changelog

All notable changes to Aksara are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.5.45] — ORM Expressions, Relation Aggregates, and Atomic Transactions

### Added
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

### Changed
- **Database connection reuse** (`aksara/db/engine.py`)
  - `Database.acquire()` now reuses the active session connection when one exists

- **Model hydration** (`aksara/model/base.py`)
  - `Model._from_record()` now preserves annotated columns by attaching undeclared fields to instances

- **Insert safeguards**
  - Expressions are rejected in insert-like operations (`Model._insert()`, `bulk_create()`, `bulk_update()`, `upsert()`) to prevent invalid SQL generation in create paths

### Documentation
- Added ORM documentation for query expressions, relation-aware aggregates, and `transaction.atomic`
- Updated the ORM docs navigation and release documentation to reflect v0.5.45

### Tests
- Added focused coverage for:
  - recursive `Q()` compilation
  - `F()` filters and updates
  - annotation hydration
  - reverse FK and M2M aggregate joins
  - transaction connection reuse and nested atomic scopes
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
