# Aksara v0.7.1 Public Truth Audit

## Executive Summary

Work in progress; this is an audit baseline, not release approval.

The starting source is v0.7.0 at
`b7ac75f4b1bd4b262824e828601168336b4ecf7f`. PyPI reports `0.7.0` and the
matching tag exists. The initial strict documentation build and 114 existing
documentation tests pass. Those checks establish syntax/import and selected
contract consistency, not that a beginner can follow every tutorial.

Initial inspection finds an information-design and execution gap: legacy
configuration remains at the start of the production tutorial, ordinary tasks
and durable Operations need clearer differentiation, and the main example
catalog does not list the production reference app. No functional fix is
proposed by this audit.

## Inventory

The complete starting file inventory is recorded in
[audit-evidence/v071/public-docs-inventory.json](audit-evidence/v071/public-docs-inventory.json):
157 public Markdown files with 902 Python fences, headings, content hashes, and
navigation membership. Content review is explicitly pending on those records.
Historical changelogs and notes will be classified separately from current
instructions. The baseline generated project contains 18 files; its hashes and
local comparison directory are recorded there without copying generated secrets.

Public surfaces also include `pyproject.toml`, `aksara/_version.py`,
`aksara/cli/scaffold.py`, CLI help, `aksara/conf.py`, and six example application
directories: basic_app, blog, crm, multitenant, support_desk, and ai_providers.

## Capability Truth Matrix

This initial map identifies source and test anchors for the detailed audit.
Stability applies only within the published v0.6/v0.7 contracts. Existence of a
module does not prove all its attributes are stable. Installed-wheel coverage
must be established by this candidate's journeys; older release results are
baseline evidence only.

| Capability | Exists? / stability | Public surface and implementation anchor | Docs / runnable anchor | Candidate wheel verified? |
| --- | --- | --- | --- | --- |
| ORM, queries | Yes / Stable bounded contract | `aksara.Model`, `aksara/manager.py` | `orm/`, basic_app | Pending |
| Fields, relations | Yes / Stable with declared exclusions | `aksara.fields`, `aksara/model/` | `orm/fields.md`, `orm/relations.md` | Pending |
| Migrations | Yes / Stable | `aksara migrate`, `aksara/migrations/` | `orm/migrations.md`, `tests/migrations/` | Pending |
| Serializers | Yes / Stable documented API | `aksara/api/serializers.py` | `api/serializers.md`, blog | Pending |
| REST/ViewSets | Yes / Stable | `aksara.ModelViewSet`, `aksara/api/` | `api/`, basic_app | Pending |
| Authentication | Yes / Stable covered paths | `aksara/contrib/auth/` | `api/authentication.md`, support_desk/auth.py | Pending |
| Principal | Yes / Stable authority model | `aksara.security.principal.Principal` | `security/`, `tests/security/` | Pending |
| Permissions / policy / fields | Yes / Stable covered enforcement | `aksara/security/policy.py`, `aksara/permissions.py` | `api/permissions.md`, `tests/security/` | Pending |
| Tenancy / RLS | Yes / Stable restricted-role contract | `aksara/tenancy.py`, `aksara/db/` | `security/multi-tenancy.md`, support_desk | Pending |
| Admin | Yes / Evolving details within production foundation | `aksara/contrib/admin/` | `admin/`, support_desk/admin.py | Pending |
| Tasks | Yes / Stable unlinked task behavior | `aksara.tasks.task`, `enqueue_task`, `TaskWorker` | `advanced/background-tasks.md`, `tests/test_tasks.py` | Pending |
| Durable Operations | Yes / Stable semantic contract | `aksara/durable/__init__.py` exports | `advanced/durable-operations.md`, `tests/durable/` | Pending |
| Approvals | Yes / Stable distinct sync/durable boundaries | `aksara/mcp/`, `aksara/durable/` | MCP quickstart; durable guide | Pending |
| External effects | Yes / Stable declared recovery classes | `aksara/durable/external.py` | durable guide; `tests/durable/test_external_effects.py` | Pending |
| Audit / outbox | Yes / Stable bounded export; storage internal | `DurableOutboxExporter`, MCP audit | durable contract; `tests/durable/test_outbox.py` | Pending |
| CLI / scaffold | Yes / Stable core commands | `aksara/cli/` | `cli/`, generated README | Pending |
| Doctor | Yes / Stable production surfaces | `aksara/cli/`, `check_durable_operations` | `diagnostics.md`, `tests/diagnostics/` | Pending |
| Media / storage | Yes / Evolving integrations | `aksara/storage.py`, media fields | `advanced/media-and-email.md` | Pending |
| TypeScript SDK | Yes / Evolving | `aksara/sdk/` | CLI/reference coverage needs audit | Pending |
| MCP | Yes / Stable synchronous Streamable HTTP | `aksara/mcp/` | `getting-started/mcp.md`, `tests/mcp/` | Pending |
| AI providers/runtime | Yes / Experimental | `aksara/ai/` | `ai-mode/`, ai_providers | Pending |
| Studio | Yes / Experimental | `aksara/studio/` | `studio/` | Pending |
| DurableStep/workflows | Yes / Evolving; no Operation guarantees | `aksara/workflows.py` | `advanced/generic-relations-and-durable-workflows.md` | Pending |

## Documentation Architecture

Proposed reader order: evaluate → quickstart → one progressive application
→ task-oriented how-tos → concepts → reference → operations. Stable MCP is an
optional application consumer and must be reachable without browsing experimental
AI internals. Contributor and experimental material remain accessible but do not
lead the beginner journey. Navigation implementation is pending.

## Contradictions Found

| ID | Severity | Evidence | Required disposition | Status |
| --- | --- | --- | --- | --- |
| PT-001 | P1 | `tutorials/deployment.md` Step 1 leads with an unsupported `AKSARA` dictionary, labeled conceptual | Replaced operational instructions with real configuration, role separation, workers and recovery guidance; clean-room execution still pending | Docs fixed |
| PT-002 | P2 | `roadmap.md` calls v0.6.1 the current adoption patch after v0.7.0 | Replaced with current v0.7.0, v0.7.1 work, evidence-gated v0.8 thesis and bounded 1.0 criteria | Docs fixed |
| PT-003 | P2 | `examples/README.md` omits support_desk from its catalog | Rewrote catalog using actual models and execution boundaries, including Support Desk and EX-001 | Docs fixed |
| PT-005 | P1 | Settings reference lists shortened task environment names without `_SECONDS` | Correct to installed names and verify the settings table | Docs fixed |
| PT-006 | P1 | Settings pages imply dataclass constructor overrides always beat environment, and that the global database URL starts an `Aksara()` database lifespan | Explain keyword overrides and explicit settings-to-constructor handoff | Docs fixed |
| PT-007 | P2 | Glossary claims memory/Redis cache backends and omits Operation/Attempt/Principal distinctions | Removed unsupported cache claim and added authority/execution terminology | Docs fixed |
| PT-004 | P2 | `docs/mkdocs.yml` gives experimental AI a large top-level section; durability is under Advanced | Provide an application learning path and prominent production/durability entry points | Open |

## Runtime Defects Exposed by the Documentation Audit

**CFG-001 / P1:** the shared environment-list parser replaces `os.pathsep`
with commas. On POSIX, `AKSARA_MCP_ALLOWED_ORIGINS=https://example.com` becomes
`["https", "//example.com"]`; host/port patterns are also affected. Verified
against installed `Settings` with a temporary environment patch. This proves
configuration corruption, not an authorization bypass. The settings reference
now recommends explicit `configure(mcp_allowed_origins=[...],
mcp_allowed_hosts=[...])` lists, which bypass environment parsing. Recommend a
separate functional parser patch with origin, port, IPv6 and platform tests;
production code is unchanged here.

## Broken Examples Found

**EX-001 / P1:** `examples/multitenant/middleware.py` contains `/` in
`EXEMPT_PATHS` and tests every exemption with `path.startswith`. A direct
`dispatch` probe for `/api/projects/` called downstream once and the mocked
tenant resolver zero times. This proves the middleware bypass, not database
exfiltration. Its README now discloses the defect and points to Support Desk.
Fixing middleware semantics is outside this release; recommend a separately
scoped correctness/security patch with authenticated tenant and denial tests.
The example cannot count as a successful tenant-isolation journey.


Execution audit pending. The initial syntax/import checks pass; this does not
prove the complete examples work against a clean installed wheel.

## Missing User Journeys

Existing tutorials teach separate blog, multitenant, and AI examples. A single
progressive application covering relations, validation, identity, tenancy,
tasks, durability, and optional MCP must be built and executed. Deployment
reading and beginner tests must use only published instructions.

## README Findings

The rewritten first screen leads with a Python application backend for SaaS
and internal applications, explains the choice relative to FastAPI, and keeps
AI optional. It scopes delayed authorized mutations and external-effect limits.
The README and short Quick Start share one canonical ticket-desk tutorial.

## Quick Start Findings

The canonical first-project page now supplies complete model, view, route,
local authentication adapter and HTTP test files. Its three tests pass through
a real server from the installed public package. The next chapter extends the
same database with relationships and custom validation. Production identity
and multi-tenancy are explicitly outside these first two stages.

## Configuration Findings

`reference/settings-reference.md` documents the global `aksara.conf.settings`
and explicit configuration above environment values. `AKSARA_DATABASE_URL`
precedes `DATABASE_URL`. The deployment tutorial does not follow this usable
path. Defaults must be checked against `aksara/conf.py`, not copied from prose.

The configuration rewrite corrects five task environment names, distinguishes
keyword overrides from the dataclass environment loader, and passes database
configuration explicitly into the Aksara constructor. New table checks compare
published defaults with installed dataclass and durable-service signatures.
Related media, task, locale and Studio examples now use keyword overrides;
the S3 installation command uses the actual distribution `aksara-framework[s3]`.

The upgrade guide documents the versioned CLI path and the legacy model-only
fallback separately. Its explicit public `apply_migrations()` recipe ran from
the public v0.7.0 wheel in a disposable PostgreSQL schema: all three bundled
migrations applied, and a repeat applied none. See
`audit-evidence/v071/upgrade-recipe.json`. This is not yet a real application
upgrade or the v0.7.1 candidate-wheel gate.

## Scaffold Findings

Instructional README now explains model/route ownership, permissions, testing,
Doctor, and optional background/durable execution. Comparing v0.7.0 and current
scaffolds with a fixed comparison token gives only `README.md` changed; all
other 17 files are byte-identical. ASTs outside `get_readme_template` are
identical. See `audit-evidence/v071/scaffold-equivalence.json`. The focused
semantic docs and first-hour scaffold tests pass: 37 tests. This does not yet
prove the full beginner journey.


Baseline generation captured 18 files. Compare generated Python ASTs (excluding
instructional docstrings), settings/environment defaults, dependencies, routes,
and service enablement before accepting instructional changes. Never publish
its generated `.env` secrets as evidence.

## CLI Findings

Command help inventory and invocation checks pending. The pre-existing local
`.venv/bin/aksara` fails to import `aksara.cli`; source-mode tests pass. A fresh
public-wheel environment is required to distinguish local editable-install
state from a product defect. That independent check passed: a fresh PyPI
`aksara-framework==0.7.0` installation in
`/tmp/aksara-v071-public-baseline` reports version 0.7.0 and renders CLI help
when invoked outside the checkout. The observed import failure is confined to
the pre-existing editable environment. Missing commands will be
roadmap input, not added to make documentation pass.

## Stable vs Experimental Findings

Published stability contracts are the starting boundary. Module exports alone
are insufficient evidence of stability. The same synchronous MCP and durable
approval terminology must not imply identical storage or replay guarantees.

## Production Documentation Findings

The production-hardening reference explains Doctor and restricted-role posture.
A coherent operator path must connect migrations, app roles, RLS, workers,
retention, deployment checks, backups, and monitoring responsibilities.

## Durable Operations Documentation Findings

The current package exports explicit service, worker, executor, registry,
principal-reference, outbox and diagnostic primitives. The user guide must make
these usable without requiring ADR knowledge. Ordinary `TaskRecord` persists
tenant identity, not a complete Principal; task scheduling is not Operation
execution authority.

## Example Findings

Initial classifications, subject to execution: KEEP basic_app as minimal;
REWRITE instructional material for blog/crm/multitenant; KEEP support_desk as
production reference; KEEP ai_providers explicitly experimental. No deletion is
justified yet. Durable example usability requires its own documented journey.

## Clean-Room Journey Results

Four consecutive chapters now run from exact Markdown file fences in a
temporary scaffold using the independently installed public 0.7.0 wheel,
local PostgreSQL and an ephemeral NOSUPERUSER/NOBYPASSRLS application role:

| Stage | Public application tests | Evidence |
| --- | --- | --- |
| First project | 3 passed | Authenticated CRUD, anonymous denial, field validation |
| Relationships | 5 passed | Existing tests plus normalization, nullable FK and SET NULL |
| Tenant boundary | 12 passed | Existing tests plus two-tenant reads/writes, role denial, missing tenant, forged headers/payloads, cross-tenant assignee validation |
| Queued report and CSV export | 16 passed | Existing tests plus worker completion, tenant provenance, current read permission and protected download |

These are **36 test executions, 16 unique final-stage tests**, not 36 unique
tests. Evidence is `audit-evidence/v071/first-project-journey.json`, with page,
snippet and runner hashes. A ticket created before the relationship migration
survives that migration and the subsequent tenant backfill. Separate raw SQL
checks verify the restricted role, forced RLS, zero visible rows with no tenant,
correct backfill ownership and a denied cross-tenant insert.

The runner uses the documented environment-variable database setup alternative,
not the interactive `dbsetup` wizard. Doctor reports PARTIAL (exit 1), with only
optional Studio/provider warnings; the gate also requires successful project,
database and migration checks. This is public-baseline evidence, not
candidate-wheel release certification. The intermediate journey covers relations,
permissions, tenancy, tasks and protected CSV export (the requested common
application feature alternative to media). It does not certify file storage.
Durable, MCP and operator journeys remain incomplete.

Observed friction and corrections: tenant migration generation needs an explicit
backfill for existing rows; the chapter replaces only the generated operations
and keeps dependencies. The tenant payload denial is HTTP 422 from the generated
schema on both create and PATCH, rather than the initially assumed 403. Tests
now assert that actual boundary and verify ownership remains unchanged. Foreign
keys alone do not enforce customer membership; the tutorial explicitly checks
assignee accessibility before saving. No runtime fix was made for these items.

## Automated Truth Gates

Baseline: strict MkDocs PASS; `pytest tests/docs tests/test_v048_docs_lock.py
 tests/test_v048_packaging_sanity.py -q`: 114 passed. The 902 Python fences
include partial snippets; import/syntax verification is not execution coverage.
Expand gates around complete public examples and record each coverage limit.

## Changes Made

Created the v0.7.1 branch, baseline inventory, scaffold comparison snapshot, and
this audit. Rewrote `tutorials/deployment.md` around real configuration, migration roles,
restricted application roles, RLS, diagnostics, worker supervision and recovery.
Added `concepts/application-boundaries.md` and `concepts/stability.md`, and
Concepts/Operations navigation. Strict MkDocs and the eight semantic docs tests
pass after these edits. End-to-end journey proof remains pending. Runtime source
is unchanged.

## Remaining Documentation Debt

Candidate journeys, full content/example audit, navigation completion, candidate
packaging, compatibility regression and hosted checks remain pending. The
market/roadmap review is now drafted from current primary documentation; its
user-demand and integration-cost hypotheses still require independent trials.

## Strategic Review and Roadmap

[The post-v0.7 review](AKSARA_POST_V07_MARKET_AND_ROADMAP_REVIEW.md) compares
application frameworks, backend platforms, task/durable systems, agent runtimes
and policy systems using primary documentation researched on 2026-09-11.
The source index is `audit-evidence/v071/strategy-research.json`. The public
roadmap now distinguishes released v0.7.0, in-development v0.7.1, a proposed
v0.8 operating-experience thesis, later work, experiments and non-goals.
It explicitly retains PostgreSQL and does not treat ordinary tasks as
Principal-preserving durable actions. No new runtime work is authorized.

Focused documentation/packaging validation after this change: 116 passed;
strict MkDocs passes. These are document consistency checks, not proof of
market demand or completion of the application journeys.

## Configuration and Upgrade Validation

After the configuration, glossary and upgrade edits:
`pytest tests/docs tests/test_v048_docs_lock.py tests/test_v048_packaging_sanity.py -q`
passes **124 tests**. Ruff on `tests/docs/test_configuration_reference.py` and
strict MkDocs both pass. The upgrade recipe's SHA-256 matches its executed
public-wheel evidence. All validation is scoped: a disposable internal-schema
bootstrap does not prove a data-bearing v0.6 application upgrade, and the full
candidate runtime matrix has not been run.

## Progressive Tutorial Validation

`python scripts/run_public_tutorial_gate.py --python <isolated-wheel-python>
--output audit-evidence/v071/first-project-journey.json` passes 36 HTTP test
executions across four successive stages. The controller receives the local DB
URL through the environment; generated credentials are not recorded. Fixtures
remove their schema and role after stopping the server. The script extracts
published files verbatim, runs `startproject`, `makemigrations`, `migrate`,
`doctor launch-check`, `run`, and the published unittest discovery command.
For tenancy it performs the documented replacement of the generated migration's
operations block, preserving the generated imports and dependencies.

`tests/docs/test_tutorial_evidence.py` verifies that the recorded evidence still
matches every executed page/snippet and the runner, parses every complete sample,
and rejects database credential patterns. These fast checks establish evidence
integrity, not fresh database execution. The full installed-wheel gate remains
required when the tutorial or runner changes.

Current focused validation: `pytest tests/docs tests/test_v048_docs_lock.py
 tests/test_v048_packaging_sanity.py -q` passes **127 tests**. Strict MkDocs and
Ruff on the runner and evidence tests pass. PostgreSQL catalog verification
finds zero leftover tutorial schemas or roles after the journey.

## Runtime Changes

**No functional runtime changes.** `aksara/cli/scaffold.py` changes only its
generated README text; equivalence evidence above covers all executable files,
settings, security defaults and dependencies. Package version remains `0.7.0` until candidate readiness is proven.
