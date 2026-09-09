# Aksara Roadmap

Maintained by [Nagarjuna Tella](https://github.com/nagarjuna-tella).

> Updated May 2026

Aksara is public and pre-1.0. The near-term roadmap prioritizes trust, first-user success, and production readiness over feature sprawl.

---

## Current Stable Version

### v0.5.54 - ORM Write & Relation Correctness

- `bulk_create()` now prepares rows before insert, applies auto-managed
  timestamps, runs field preparation hooks, and preserves mixed
  implicit/explicit `auto_now_add` values.
- `QuerySet.update()` now refreshes `auto_now` fields such as `updated_at` when
  regular fields change, while respecting explicit `updated_at` values.
- `bulk_update()` now casts Vector values inside CASE branches.
- `ForeignKey` and `OneToOne` now share normalized `on_delete` validation, and
  invalid actions are rejected before DDL generation.
- `SET_NULL` / `SET NULL` now requires `nullable=True`.
- Custom `ManyToMany(..., through=...)` models now fail clearly because custom
  through models are not supported yet.
- The forward FK access contract is documented: field and `*_id` attributes
  expose the stored FK id; load related objects explicitly or with
  `select_related()` plus `get_related()`.
- This release focuses on ORM write-path consistency and relation safety.
  It does not claim production readiness or external security review.

---

## Recent Releases

### v0.5.53 - ORM Query Semantics & Migration Generation Correctness

- `filter(field=None)` and `filter(field__exact=None)` now compile to `IS NULL`
  instead of equality against a NULL parameter.
- `__isnull` filters use strict boolean parsing; `"False"` and `"0"` are treated
  as false, and invalid values raise a validation error.
- FK/O2O column aliases like `author_id` are accepted in filters when they
  correspond to a real relation database column.
- Reverse FK filters now work through the corrected alias handling.
- `CreateTable` migration operations are ordered by FK/O2O dependencies.
- `DropTable` operations use reverse dependency order.
- Legacy `makemigrations --sql` output uses FK dependency ordering.
- `Array(nullable=False)` fields emit `nullable=False` correctly in generated
  migration code.
- Migration codegen supports additional field operations.
- This release focuses on query semantics and migration generation correctness.
  It does not claim production readiness or external security review.

### v0.5.52 - Admin Correctness & Permissions

- Admin mounting now honors custom prefixes, custom login/logout redirects,
  multi-site route namespaces, and prefix-scoped CSRF cookie paths.
- Site permission classes now apply consistently during login and access, and
  bulk actions check object-level permissions before running.
- Admin writes now enforce readonly fields on create/update, validate
  many-to-many ids, update relations transactionally, and render Boolean
  `False` checkboxes correctly.
- Admin docs now cover Admin vs Studio, setup, CSRF, permissions, actions,
  widgets, filters, pagination, and compatibility notes.
- `AksaraFilterBackend` is the preferred API filter backend name;
  `DjangoFilterBackend` remains as a compatibility alias.
- This release improves admin correctness and permissions. It does not claim
  production readiness or external security review.

### v0.5.51 - ORM Primitive Correctness

- Integer-family fields now reject non-integral numeric inputs instead of
  truncating them, and validate PostgreSQL range boundaries before persistence.
- Boolean fields now parse strict true/false forms instead of treating arbitrary
  non-empty strings as `True`.
- Decimal fields enforce `max_digits` and `decimal_places` before database
  writes, finite float validation rejects `NaN`/infinity, and email validation
  rejects invalid local-part dot placement.
- Unit and DB-backed regression coverage protects the primitive field behavior.
- This is a primitive correctness release only. Query semantics, write-path
  consistency, relation safety, and advanced Array/vector/file field policy
  remain planned work.

### v0.5.50 - Migration Safety & Correctness

- File-based CLI and test-helper migrations now use one canonical executor with
  transactions, advisory locking, SQL statement splitting, checksum recording,
  and checksum verification.
- Migration graph loading is strict by default, cycles are reported clearly, and
  pending migrations skipped after a failure are surfaced.
- SQL-generation guardrails cover many-to-many constraint names, partial-index
  predicates, and array SQL type validation.
- The migration file format is unchanged. The legacy model-based CLI fallback
  remains for bootstrap scenarios and does not provide the full file-based
  migration integrity model.
- Migration metadata schema versioning, an app-label / name identity split,
  automatic checksum backfill, and a migration verify/backfill command remain
  future work.

### v0.5.49 - Security Hardening & Release Trust

- Added centralized Principal and PolicyEngine foundations.
- Added runtime field enforcement for covered generated write paths.
- Added tenant isolation and MCP credential hardening helpers.
- Added bounded security, diagnostics, and fuzz/adversarial test coverage.
- Added public-safe security docs and private security matrix handling.
- Added Security CI, Release Gate, CodeQL, Dependabot, secret scanning,
  static analysis, dependency audit, SBOM generation, package verification,
  and PyPI Trusted Publishing prep.
- Does not claim production readiness or replace external security review.

### v0.5.48 - Launch Hardening & Golden Path

- Added `aksara doctor launch-check` for first-run readiness.
- Added `aksara examples validate` for bundled example sanity checks.
- Promoted `basic_app`, `blog`, `crm`, `multitenant`, and `ai_providers` as golden-path examples.
- Refreshed README, getting-started docs, roadmap, and changelog for public launch clarity.
- Added packaging, docs, examples, launch-check, and no-secrets test coverage.
- Kept AI provider setup optional for first launch.

### v0.5.47 - ORM/Admin/Write-path/Security Stabilization

- Fixed AI metadata propagation across tool schemas, MCP export, and console prompt packs.
- Hardened ORM write paths for field conversion, bulk operations, and upsert behavior.
- Improved migration ordering and generated DDL correctness.
- Fixed API schema output and pagination behavior.
- Tightened Studio/auth and tenant/task handling.

### v0.5.46 - Packaging and Docs Release Polish

- Aligned package metadata, CLI version output, scaffold templates, and docs.
- Fixed PyPI README asset rendering.
- Hardened docs deployment with required MkDocs plugins.

### v0.5.45 - ORM Expressions, Native Multi-Tenancy, SDK Generation, and Real-Time Streams

- Added `Q()` objects, `F()` expressions, aggregation, transactions, tenant-aware models, TypeScript SDK generation, SSE streams, media/email, i18n/timezones, generic relations, durable workflows, and additional field types.

---

## v0.5.55 Candidate (Unpublished)

Advanced Array/Vector/JSON/File policy is implemented in the candidate, including
stricter API inputs and validated defaults. Failed-start connection cleanup and
supported web route traversal are under the release gate. The independent
benchmark overhaul is outside this correctness release. See the
[runtime compatibility contract](reference/runtime-compatibility.md).

## Future Roadmap

### Remaining ORM Correctness Work

Planned ORM correctness work remains:

- Lazy forward FK object loading, if desired.
- Custom ManyToMany through model support.
- Relation features not implemented by the current relation manager APIs.

### v0.5.x - Durable AI Session Store

Persist investigation sessions, AI Console transcripts, and AI review state so multi-step analysis can resume reliably across process restarts.

### v0.5.x - AI Memory Foundation

Introduce a minimal, explicit memory foundation for project-level AI context.

### v0.5.x - AI System Radar

Add system-level monitoring surfaces for AI-assisted project health.

### v0.6.0-alpha.1 - Stability, Auditability, and Reference App

First alpha toward v0.6. Focus is on stability contracts, operational
auditability, and validating the stack against something that looks like real
use — not new features.

Planned items:

- **v0.6 stability contract** — published commitment to stable vs. evolving
  areas, compatibility policy before v1.0, security-fix behavior, generated
  surface change policy, and migration note expectations. Draft available:
  [v0.6 Stability Contract](roadmap/v0-6-stability-contract.md).
- **Multi-tenant support desk reference app** — a deployable Aksara application
  using multi-tenancy, AI tools, and the security controls stack. Intended to
  validate the framework against real deployment patterns.
- **AI/MCP audit logging** — field-level and action-level audit logs for AI
  agent writes, so tenant administrators can see what AI agents have done.
- **Production checklist to doctor mapping** — each item on a production
  readiness checklist corresponds to a specific `aksara doctor` check. Machine-
  checkable, not just human-readable.
- **External review package** — bundled scope, threat model, and findings
  template ready for an external security reviewer.
- **Benchmark plan** — performance baseline and regression detection before
  v0.6.0 ships.

### v0.6.0 - Production Mode

Focus on production safety: connection-pool guidance, read-only Studio posture, deployment checks, stronger security defaults, and operational documentation.

---

## Long-Term Direction

- Keep the first ten minutes simple and inspectable.
- Make generated APIs, Studio, MCP, and AI context feel like one system.
- Preserve local-first and provider-optional workflows.
- Graduate toward stable production contracts before 1.0.
