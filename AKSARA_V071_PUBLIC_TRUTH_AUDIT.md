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
| PT-002 | P2 | `roadmap.md` calls v0.6.1 the current adoption patch after v0.7.0 | Replace with evidence-derived current/next horizons | Open |
| PT-003 | P2 | `examples/README.md` omits support_desk from its catalog | Describe minimal, application-pattern, production, durable, and experimental purposes accurately | Open |
| PT-004 | P2 | `docs/mkdocs.yml` gives experimental AI a large top-level section; durability is under Advanced | Provide an application learning path and prominent production/durability entry points | Open |

## Broken Examples Found

Execution audit pending. The initial syntax/import checks pass; this does not
prove the complete examples work against a clean installed wheel.

## Missing User Journeys

Existing tutorials teach separate blog, multitenant, and AI examples. A single
progressive application covering relations, validation, identity, tenancy,
tasks, durability, and optional MCP must be built and executed. Deployment
reading and beginner tests must use only published instructions.

## README Findings

The existing first screen correctly describes a PostgreSQL framework and scopes
AI as experimental. Evaluate its audience, concrete use case, FastAPI comparison,
and navigation after capability and market research; do not assume AI-native is
the right lead category.

## Quick Start Findings

Existing gate coverage is useful but insufficient to certify the new full
beginner/auth/testing journey. Rerun from an isolated installed wheel after edits.

## Configuration Findings

`reference/settings-reference.md` documents the global `aksara.conf.settings`
and explicit configuration above environment values. `AKSARA_DATABASE_URL`
precedes `DATABASE_URL`. The deployment tutorial does not follow this usable
path. Defaults must be checked against `aksara/conf.py`, not copied from prose.

## Scaffold Findings

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

Not yet run for v0.7.1. Do not interpret the v0.7.0 release's 15-step wheel gate
or 66-check reference gate as completion of the new journeys.

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

All candidate journeys, full content/example audit, navigation implementation,
market research, strategic report, roadmap, candidate packaging, compatibility
regression and hosted checks remain pending.

## Runtime Changes

**NONE.** Package version remains `0.7.0` until candidate readiness is proven.
