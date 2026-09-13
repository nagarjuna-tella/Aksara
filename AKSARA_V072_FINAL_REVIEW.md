# Aksara v0.7.2 Final Review

## Executive Summary

**READY FOR v0.7.2rc1 REVIEW.** All 22 defects disclosed by the v0.7.1 Public
Truth audit were reproduced against the public v0.7.1 wheel, repaired at their
root cause, covered by permanent regressions, and shown absent from an isolated
installed `0.7.2rc1` wheel. The result is 22 `FIXED`, zero `DISPROVED`, zero
`ALREADY_RESOLVED`, and zero unresolved.

This is a finite correctness candidate. It adds no dependency or v0.8
capability. It does not merge ordinary Tasks with Durable Operations, expand
provider families, add databases, redesign Admin, or promote experimental AI
surfaces. Publication, tagging, and merge remain unauthorized.

## Starting State

The released base is `main` commit
`a0422cf8fa004b41a2ccdaa9aa91c8036357159d`. Its tree is identical to the tree
tagged `v0.7.1`, and PyPI's public `aksara-framework==0.7.1` wheel has SHA-256
`42a3a42be08ee5be1075d4f6da3b22fea6acaa5bf678a57db7ecc00ce4fdd197`.
All negative reproductions used that installed public wheel. The protected
untracked historical evidence and benchmark directories were left unchanged.

## 22-Finding Closure Matrix

The complete row-by-row matrix, root causes, compatibility effects, and linked
baseline/candidate artifacts are in
[`AKSARA_V072_AUDIT_CLOSURE.md`](AKSARA_V072_AUDIT_CLOSURE.md). Its
machine-readable authority is
[`audit-evidence/v072/findings-closure.json`](audit-evidence/v072/findings-closure.json).

## Security-Relevant Fixes

Custom actions now enforce their declared authorization, filesystem storage is
component-contained, soft-delete transformations preserve predicates, and the
historical multitenant example no longer treats `/` as a universal prefix.
Configuration ambiguity, silent model loss, and stale task writes now fail
closed. The scoped assessment and exploit prerequisites are in
[`AKSARA_V072_SECURITY_REVIEW.md`](AKSARA_V072_SECURITY_REVIEW.md).

## Authorization

ViewSet-level permissions apply to custom actions unless the action declares an
explicit override. Authentication/request checks precede handler execution;
detail actions also enforce object checks under the request tenant. Denial keeps
the handler uncalled and returns the established structured HTTP response.
Generated REST, generated MCP, and Durable execution retain their existing
policy paths. No caller can use a custom action to bypass the same declared
authorization intent.

## Storage

`FileSystemStorage` resolves the configured root and candidate path, then uses
path components for containment. Save, open/read, exists, delete, size, path,
and URL-related local conversion reject traversal, sibling prefixes, absolute
escapes, and symlinks that resolve outside the root. Symlinks resolving inside
remain supported. FileField's independent validation is unchanged.

## Tenant/Query Scope

Soft-delete visibility is now QuerySet state carried by the canonical clone
path. Filters, Q objects, tenant predicates, ordering, limits, annotations,
relation loading, and database/session context survive `with_deleted()` and
`only_deleted()`. A restricted-role forced-RLS test with two tenants proves the
application predicate and database policy both remain effective.

## Model Registry and Migrations

The canonical identity after v0.7.2 is the module-qualified class name. Simple
names remain a compatibility convenience only when exactly one registered model
uses that name. Ambiguity raises `AmbiguousModelError`, independent of import
order. Migration discovery, fields/relations, fixtures, Admin and CLI inspection
propagate that ambiguity instead of choosing or dropping a model. Built-in and
application `User` models, two application modules with the same class name,
reversed/repeated discovery, replay, and non-colliding legacy applications are
covered.

## Relations

`select_related(...).first()` now runs the same requested eager-loading phase as
`all()`. No-result, nullable/non-null foreign keys, one-to-one relations,
multiple fields, ordering, missing relations, and query-count behavior pass.

## Bulk Writes

`bulk_update()` casts searched-CASE value parameters through each field's
declared PostgreSQL type. Boolean and timestamp negative reproductions now pass,
along with strings, integers, floats, decimal, UUID, date, time, datetime,
duration, Enum, nullable values, and supported advanced PostgreSQL fields.
Transactions, batching, row matching, empty input, and mixed values are retained.

## Fixtures

JSON restore now inserts an explicit primary key when it is absent and updates
the matching row when present under the documented conflict mode. YAML emits
portable safe scalars for UUID and temporal values and continues to use
`safe_load`. Default database dumping enumerates canonical registry model
classes. JSON and YAML round trips cover UUID identity, foreign key, Boolean,
timestamp, null, JSON, and Array data. This is fixture/data-movement evidence,
not disaster-recovery certification.

## Pagination

Generated HTTP models now reflect the selected built-in paginator. Page, size,
total-page, limit/offset, cursor and `next_cursor` metadata survive response
serialization and appear in OpenAPI. Empty, first, middle, final, custom-size,
invalid-bound and cursor continuation cases pass. The generated TypeScript
types agree with the live payload.

## Ordinary Tasks

Ordinary Tasks use a worker ID, random claim token, database-time lease,
heartbeat, atomic stale recovery, and conditional success/failure updates.
Transfer clears the old claim and creates a new token; the old heartbeat cannot
renew it, and stale success/failure updates affect zero authoritative rows.

Five installed-candidate process scenarios record PIDs, claim/heartbeat/lease
timestamps, owner identity, transfer, and terminal state. A healthy task
heartbeats beyond the stale interval without recovery; a paused worker loses to
its replacement; a hard-killed worker is recovered; competing workers yield one
owner/effect; and a stale failure cannot overwrite a later retry success.
Ordinary Tasks remain at-least-once. Applications must make irreversible
external effects repeat-safe.

## SDK

The canonical Ticket Desk TypeScript SDK compiles with TypeScript 5.9.3 in
strict mode at exit 0, without `any` expansion or error suppression. Generated
models, nullable/optional fields, create/update payloads, list parameters,
filters, search, ordering, pagination and custom actions are checked. A live
candidate HTTP application passes list, detail, create, update, and query
serialization, including cursor metadata.

## Scaffold

Basic, Blog, CRM, and multitenant templates generate explicit Hatchling package
selection for arbitrary project names. Each passes documented editable install,
wheel build, isolated wheel install, and import. The basic clean-room journey
also passes dependencies, migrations, tests, startup, health, REST create/list,
shutdown, and restart from its installed project wheel.

## Testing

`test_database(cleanup=True)` pins supported same-task `Database` and model work
to the helper's owned transaction. Success, exception, cancellation, nested
transaction, execute/query/model save, independent-observer visibility,
rollback, pool closure, and repeated use pass on PostgreSQL. HTTP requests and
separate processes are explicitly outside that transaction boundary.

## Configuration

List-valued environment settings use a portable grammar: JSON arrays are
canonical, and unambiguous comma-separated values are supported for convenience.
URLs with schemes and ports, host/port, IPv4, bracketed IPv6/port, whitespace,
empty input, explicit Python lists, malformed input, and POSIX/Windows behavior
pass. `os.pathsep` is no longer a URI-list delimiter. Python compatibility now
comes from one policy: 3.9/3.10 fail, 3.11-3.14 pass, and later versions are
explicitly unsupported pending validation.

## Diagnostics

Environment actions store a name and raw example value. One renderer produces a
coherent display assignment for database URLs, provider secrets, quoted values,
spaces, empty values, and legacy already-formatted values. Tests never execute
the generated command or a real secret. The Doctor release policy passes all 12
checks.

## Experimental AI/Workflow

Provider detection distinguishes explicit configuration from adapter defaults,
reachability, authentication and health. A clean environment configures no
provider; an explicit Ollama URL, API-key provider, keyless custom endpoint, and
custom endpoint plus key behave as documented; malformed URLs fail. Public
workflow imports work in either order and repeatedly from clean installed-wheel
processes. These repairs do not promote provider or workflow quality to Stable.

## Inspector

Query-plan results carry `live`, `synthetic`, `failed`, or `unavailable`
provenance plus `analyze_executed`. Live PostgreSQL EXPLAIN and ANALYZE use the
async execution path. Offline fallback stays clearly synthetic, retains its
warning, and cannot state that ANALYZE ran. Invalid SQL and unavailable database
paths remain distinguishable. Inspector remains Experimental.

## Admin

`ArrayAdminWidget.render()` copies list/tuple input before padding display rows.
Empty, short, equal, longer, repeated, shared-reference and escaping cases pass.
Server-side validation is unchanged, and this repair does not broaden Admin's
stability guarantee.

## Upgrade Compatibility

A realistic Support Desk schema was created by a clean public v0.7.1 package
and populated with an organization, tenant user/agent, foreign-key ticket,
queued ordinary task, and succeeded Durable Operation. The installed candidate
applied `aksara_core_migrations_0003_task_claim_ownership`, preserved every row
and relation, claimed the queued task with the new owner token, replayed
migrations idempotently, and served the preserved ticket through authorized
REST. Anonymous REST remained denied; Admin and MCP discovery remained present.

## PostgreSQL/RLS

Local authoritative tests use PostgreSQL 18.4 and the `aksara_test` database;
credentials are omitted from evidence. The production-shaped gate creates a
`NOSUPERUSER NOBYPASSRLS` role, forces RLS, and exercises two tenants. Hosted
PostgreSQL 16 remains the independent environment check on the PR.

## Durable Operations Non-Regression

The full Durable Operations suite passes 234 tests, and the production-bound
invariant prototype passes 24. The packaged Support Desk covers atomic mutation,
lost response, current authorization/revocation, approval, cancellation,
conflicting and duplicate submission, retry, reclaim/fence, external effects,
transition/outbox, pruning and task-backed execution. The Durable contract and
stable MCP semantics did not change.

## Installed-Wheel Results

The candidate wheel passes 15 installed-package checks, 66 packaged Support Desk
checks, 213 selected installed closure regressions, all five real-process task
scenarios, four clean workflow import orders, four scaffold template builds,
three strict TypeScript/live-client checks, and the six-stage/86-assertion Ticket
Desk journey. Framework imports in these gates resolve from isolated
site-packages.

## Reference Applications

Ticket Desk passes all six progressive stages and 86 public assertions. Support
Desk passes 66 production-shaped checks. The five retained public examples
start from the candidate wheel. Basic, Blog, CRM, and multitenant scaffold/model
registry paths also install and import under arbitrary project names.

## Performance Sanity

The established 256-operation, eight-worker, 3,000-noise-row campaign passes all
seven invariants: one operation per concurrent key, completion, monotonic
reclaim fences, indexed claim plan, mutation/accounting agreement, bounded
pruning and an idle pool. Targeted relation, bulk, pagination, storage and task
regressions found no pathological behavior. These measurements are a local
sanity gate, not an SLO.

## New Findings

Two release-process findings were corrected before evidence finalization: a
Studio display assumption exposed by provider-state tightening, and installed
documentation runner drift after two negative controls became positive. There
is no unresolved new blocker. See
[`AKSARA_V072_NEW_FINDINGS.md`](AKSARA_V072_NEW_FINDINGS.md).

## Remaining Technical Debt

Remaining debt is outside the closed 22-item ledger and outside this candidate:
existing static-analysis ratchets, deprecation warnings from supported third
party boundaries, and the broader experimental quality limits already described
by the stability contract. No closed defect is relabeled here as debt.

## v0.8 Architectural Inputs

Audit closure produced design observations about cross-interface authorization,
canonical identity, Task/Operation separation, generated schema/client proof,
tool provenance, and configuration grammars. They are recorded in
[`AKSARA_V08_ARCHITECTURAL_INPUTS.md`](AKSARA_V08_ARCHITECTURAL_INPUTS.md) and
were not implemented.

## Release Recommendation

The candidate is ready for human review once the final evidence commit is pushed
and the full hosted matrix passes. There is no known reproduced v0.7.1 audit
defect still present, no design decision requiring an rc2, and no justification
to continue audit-correctness development after hosted validation. Do not merge,
tag, publish, or begin v0.8 as part of this review.
