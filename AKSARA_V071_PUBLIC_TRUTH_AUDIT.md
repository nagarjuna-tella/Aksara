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

This matrix separates 34 capability areas rather than combining independent
contracts into a feature checklist. Stability follows the published v0.6/v0.7
contracts and `concepts/stability.md`; existence alone does not establish stability.
Public-wheel entries below describe **only the exercised public 0.7.0 slice**.
Every candidate-wheel entry remains pending until the final candidate is built
and the release gates are rerun. “Pending” is not an absence of historical tests.

| Capability | Exists? | Stability | Public API / source anchor | Docs quality | Runnable example / test anchor | Installed public wheel | Notes / remaining proof |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ORM | Yes | Stable bounded contract | `aksara.Model` | Reviewed core flow | Ticket desk | CRUD slice | Lifecycle/signals and bulk methods still need candidate coverage. |
| Query API | Yes | Stable documented methods | `Model.objects`, `Q`, `F` | Core counts/filters exercised | Ticket report | Counts/filter slice | See `tests/test_queryset_order_by.py`; full query breadth remains a regression gate. |
| Fields | Yes | Stable declared types | `aksara.fields` | Partial audit | Ticket desk | String/Boolean/UUID slice | Advanced Array/Vector/JSON contracts require their separate field suite. |
| Relations | Yes | Stable with exclusions | `fields.ForeignKey`, `OneToOne`, `ManyToManyField` | Reviewed FK flow | Ticket assignee | Nullable FK / SET NULL | Stored forward ID is not a lazy object; custom M2M through models remain unsupported. |
| Migrations | Yes | Stable | `aksara makemigrations`, `migrate`, `aksara.migrations` | Core journey rewritten | Ticket desk; upgrade recipe | Additive relation and tenant backfill | Full historical/data-bearing upgrade and failure campaigns remain candidate gates. |
| Serializers | Yes | Stable documented API | `aksara.api.serializers.ModelSerializer` | Core journey rewritten | Ticket subject validation | Create and PATCH validation | Public `ValidationError` gives 422; background ORM writes do not automatically run HTTP serializers. |
| Generated REST/ViewSets | Yes | Stable | `aksara.ModelViewSet`, `include_viewset`, `action` | Core journey rewritten | Ticket desk | CRUD and custom routes | OpenAPI, pagination and every action variant still require full regression coverage. |
| Authentication | Yes | Stable covered backend paths | `aksara.contrib.auth`, application adapters | Partial audit | Local adapter; Support Desk | Local adapter only | A local bearer mapping is not production login/provider certification. |
| Principal | Yes | Stable | `aksara.security.principal.Principal` | Reviewed identity explanation | Ticket identity + durable resolver | Human and tenant context | MCP-agent identity, scope, expiry and human-owner membership are now exercised too. |
| Permissions | Yes | Stable | `BasePermission`, `IsAuthenticated`, `check_permissions` | Reviewed application pattern | Reader/editor ticket policy | Request/object denial | Custom endpoints must explicitly call their policy; they do not inherit ViewSet permissions. |
| PolicyEngine | Yes | Stable documented methods | `aksara.security.policy.PolicyEngine` | Partial audit; boundaries clarified | Generated CRUD; durable authorizer | Covered query/write policy slice | `tests/security/test_policy_engine.py` remains the broader authority. |
| Field-level policy | Yes | Stable covered write paths | `PolicyEngine.validate_payload`, enforcement helpers | Partial audit | Tenant-owned field; durable resolved field | Owned-field denial | Schema 422 and runtime permission denial are distinct enforcement points. |
| Multi-tenancy | Yes | Stable covered context paths | `TenantModel`, `aksara.middleware.context` | Runnable chapter added | Two-customer ticket desk | HTTP and ordinary-task context | Tenant identity comes from server-owned membership, not request headers. |
| PostgreSQL RLS | Yes | Stable restricted-role contract | `aksara.tenancy` helpers; migration SQL | Runnable chapter added | Forced-RLS ticket tables | Raw SQL plus HTTP denial | Actual NOSUPERUSER/NOBYPASSRLS posture checked; raw cross-tenant INSERT rejected. |
| Admin | Yes | Evolving details | `aksara.contrib.admin` | Needs detailed audit | Support Desk admin | Pending | Do not infer all Admin APIs are frozen from backend production readiness. |
| Ordinary tasks | Yes | Stable unlinked behavior | `aksara.task`, `aksara.tasks.TaskWorker` | Guide corrected; runnable chapter | Queued ticket report | Enqueue, worker, guarded result | Persists tenant, not full Principal; separate task recovery/retention gates remain. |
| Durable Operations | Yes | Stable v0.7 semantic contract | `aksara.durable` action/service/router/worker exports | Runnable chapter added | Durable ticket resolution | Admission, rollback/retry, cancel, revocation | New process per one-shot attempt; not a full crash campaign or fleet scheduler. |
| Approvals | Yes | Stable distinct boundaries | Signed MCP grants; durable approval decisions | Needs complete how-to review | Support Desk / durable guide | Pending new journey | Sync grants and durable decisions are different; neither overrides current authority. |
| External effects | Yes | Stable declared effect classes | `ExternalEffectAdapter`, `ExternalOperationExecutor` | Concept reviewed; examples pending | Durable reference guide | Pending new journey | No exactly-once external-effect promise; uncertainty can remain explicit. |
| Audit history | Yes | Stable bounded semantics | Service history; MCP audit sinks | Needs how-to audit | Durable guide | Pending new journey | Not a tamper-resistant ledger or application retention service. |
| Outbox export | Yes | Stable bounded semantics | `DurableOutboxExporter` | Needs runnable operator example | `tests/durable/test_outbox.py` | Pending | Raw outbox row layout is internal; operator owns durable export/retention. |
| CLI | Yes | Stable core commands | `aksara` command groups | Partial help audit | Tutorial commands | Startproject/run/migrate/launch-check slice | Every major subcommand still needs discoverability and documented-command review. |
| Scaffold | Yes | Experimental template layout | `aksara startproject` output | README rewritten | Generated ticket_desk | Executed; equivalence baseline recorded | v0.6 contract explicitly excludes template layout from stability; no defaults changed. |
| Doctor | Yes | Stable exit/JSON contract | Doctor CLI; `check_durable_operations` | Production path rewritten | Launch check; production guide | Launch-check slice | PARTIAL only for optional services; production release profile remains a separate gate. |
| File/Image fields | Yes | Stable bounded field contract | `fields.FileField`, `ImageField` | Partial audit | Media guide | Pending new journey | Field correctness is distinct from storage integration and protected download design. |
| Storage integrations | Yes | Evolving | `aksara.storage` | Rewritten media guide and STORAGE-001 limitation | Complete local storage/email script | Nine local checks pass | No SMTP/S3 or persisted model-file lifecycle claim; direct filesystem containment needs a separate patch. |
| TypeScript SDK | Yes | Evolving | `aksara.sdk.generate_typescript_sdk` | New how-to and explicit type-checking limitation | Ticket ViewSet generator script | Generation passes; TypeScript fails | SDK-001: generated list params lack required index signature; separate patch required. |
| MCP | Yes | Stable synchronous contract | `aksara.mcp`; `/mcp/` Streamable HTTP | Quickstart consolidated; runnable chapter | Ticket desk official client | Generated execution and denial | SDK 2.0.1 verified; no protocol Tasks or automatic durable agent dispatch. |
| AI/provider/runtime | Yes | Experimental | `aksara.ai` | Needs full stability/copy audit | ai_providers | Pending | Planner and provider quality are outside backend production guarantees. |
| Studio | Yes | Experimental | Studio UI and internal HTTP surfaces | Needs full stability/copy audit | Studio guides | Pending | Not a substitute for production Admin or a durable investigation store. |
| Workflows/DurableStep | Yes | Evolving | `aksara.workflows.DurableStep` | Boundary explained | Generic-relations/workflow guide | Pending | Step cache does not inherit Operation leases, fences or current reauthorization. |
| Configuration | Yes | Stable documented contract | `Settings`, `settings`, `configure` | Reference rewritten and checked | Settings/upgrade examples | Explicit overrides and upgrade recipe | POSIX origin-list env parsing defect documented with explicit-list workaround. |
| Durable persistence internals | Yes | Internal | Repositories, raw rows and failure hooks | Separated from public contract | Framework tests only | Not a public API gate | Do not expose raw provenance/fences as application contract merely because imports exist. |
| Legacy provider configuration | Yes | Deprecated | `Settings.ai_default_provider`, `ai_providers`, `ai_secret_hints` | Reference labels compatibility fields | Settings reference | Not recommended example | Retained metadata fields, not recommended provider setup. |

## Documentation Architecture

Implemented reader routes: Home for evaluation, Start for the six-chapter
ticket desk, Build for concepts and application guides, Operate for deployment
and diagnostics, MCP for the stable protocol, and Reference for exact usage.
Experimental AI/Studio and contributor internals have separate sections; Roadmap
retains release contracts and changelog. All 157 prior navigation destinations
remain reachable. Home, Getting Started, First App, Ten Minutes and Tutorials
now lead to the same executable application rather than competing toy projects.
Automated navigation checks verify destinations and the principal reader routes.
Full page-by-page usability review is still pending.

## Contradictions Found

| ID | Severity | Evidence | Required disposition | Status |
| --- | --- | --- | --- | --- |
| PT-001 | P1 | `tutorials/deployment.md` Step 1 leads with an unsupported `AKSARA` dictionary, labeled conceptual | Replaced operational instructions with real configuration, role separation, workers and recovery guidance; clean-room execution still pending | Docs fixed |
| PT-002 | P2 | `roadmap.md` calls v0.6.1 the current adoption patch after v0.7.0 | Replaced with current v0.7.0, v0.7.1 work, evidence-gated v0.8 thesis and bounded 1.0 criteria | Docs fixed |
| PT-003 | P2 | `examples/README.md` omits support_desk from its catalog | Rewrote catalog using actual models and execution boundaries, including Support Desk and EX-001 | Docs fixed |
| PT-005 | P1 | Settings reference lists shortened task environment names without `_SECONDS` | Correct to installed names and verify the settings table | Docs fixed |
| PT-006 | P1 | Settings pages imply dataclass constructor overrides always beat environment, and that the global database URL starts an `Aksara()` database lifespan | Explain keyword overrides and explicit settings-to-constructor handoff | Docs fixed |
| PT-007 | P2 | Glossary claims memory/Redis cache backends and omits Operation/Attempt/Principal distinctions | Removed unsupported cache claim and added authority/execution terminology | Docs fixed |
| PT-008 | P1 | Durable guide mounts the generic router without explaining application admission permissions or the connected-database lifecycle | Added explicit admission boundary explanation and runnable factory/resolver/worker tutorial | Docs fixed |
| PT-009 | P2 | Older MCP quickstart duplicates an unrelated app and uses `httpx.AsyncClient` rather than the installed SDK 2.0 transport type | Consolidated entry around the tested ticket desk and `httpx2.AsyncClient`; no dependency change | Docs fixed |
| PT-004 | P2 | Navigation promotes experimental AI before the backend journey; entry pages teach competing starter apps | Added Start/Build/Operate/MCP/Reference/Experimental/Contribute paths, retained every page destination, and consolidated entry pages around the tested ticket desk | Docs fixed |
| PT-014 | P1 | Standalone Blog and Multi-Tenant tutorials combine legacy configuration/request APIs with incomplete authentication and strong isolation claims | Merged runnable learning into the tested ticket desk; retained task-specific mapping and explicit tenancy requirements at existing URLs | Docs fixed |
| PT-013 | P1 | Schema Doctor guide advertised nonexistent `ai doctor --fix`; AI tools implied universal executable tool names | Replaced with installed schema commands and generated MCP discovery; route hints now use executable public APIs | Docs fixed |
| PT-011 | P1 | Doctor page mixes launch exit codes with check descriptions and omits strict production/durable preflight entry points | Separate command policies and link the matrix and service preflight | Docs fixed |
| PT-010 | P2 | Docs home calls released v0.7.0 a candidate; tutorial index directs readers to a separate `aksara/examples` repository rather than the documented source | Corrected released status and linked the canonical source-bearing chapters and repository example catalog | Docs fixed |
| PT-016 | P1 | Authentication guide claims ordinary `objects.create(password=...)` hashes passwords and documents nonexistent login/JWT/reset APIs | Replaced with built-in `create_user`, `authenticate`, hashing/session primitives and explicit application-owned identity adaptation | Docs fixed; installed PostgreSQL proof |
| PT-017 | P0 | Permission examples use async hooks although ModelViewSet calls hooks synchronously, so an unawaited denial coroutine is truthy; examples also assume an unset DRF-style `self.action` | Replaced with synchronous active-owner permission and explicit list/create/object boundaries; verified owner, non-owner, inactive and anonymous outcomes | Docs fixed; no runtime behavior change |
| PT-018 | P1 | ViewSet guide advertised ignored DRF-style attributes, unsupported handler helpers, PUT routes, and action-removal switches | Replaced with actual registration, PATCH/detail paths, per-operation serializers, synchronous list query hook and explicit permission boundaries | Docs fixed; installed route/default checks |
| PT-020 | P1 | API overview and duplicate API reference repeated unsupported DRF attributes, routes, serializer hooks, and custom HTTP authorization claims | Consolidated entry pages around checked references and clarified the registered HTTP action limitation in security/stability guidance | Docs fixed; public import, CLI, and rendered-link gates |
| PT-021 | P1 | Routing reference passed dotted strings to module discovery, invented prefix/name options and PUT/detail paths, and assumed nested parent filtering | Replaced with actual module discovery, in-place registration and explicit nested-resource/security boundaries | Docs fixed; installed registration/discovery checks |
| PT-022 | P2 | Throttling page calls all rate limiting future work and shows an incomplete third-party decorator example | Documented existing Admin POST limits, process-local counters, proxy assumptions, and application-owned API limits | Docs fixed; existing Admin HTTP regression |
| PT-023 | P1 | Signal guides invent decorators, lifecycle events, and created/update_fields payloads; external effects lack commit qualification | Replaced with explicit subscriptions, exact lifecycle payloads, runnable dispatch example, and transaction/side-effect limits | Docs fixed; installed dispatcher and PostgreSQL lifecycle/rollback probes |
| PT-024 | P1 | Duplicate ORM reference advertises nonexistent query methods, awaitable/sliceable query construction, Django field options and object-valued lazy foreign keys | Replaced with actual query boundary, concurrency qualification and links to detailed contracts | Docs fixed; installed query-shape example; no database execution claimed |
| PT-025 | P1 | Querying guide repeats unsupported await/slice/projection/exclude patterns and positional aggregate calls | Rewrote around tutorial Ticket, explicit terminal methods, Q negation, bounded pagination and named aggregates | Docs fixed; all eight Python blocks executed against installed-wheel PostgreSQL; 18 assertions |
| PT-026 | P1 | Eighteen remaining ORM overview/model/field/relation examples directly await query builders, including unsupported exclude | Added explicit all terminals and Q negation across four guides | Docs corrected for this API shape; broader surrounding semantics still under review |
| PT-027 | P1 | Advanced validation guide teaches async serializer hooks, nonexistent validator APIs and implicit clean behavior; type example uses null=True | Replaced with explicit layer-specific validation contracts and corrected nullable option | Docs fixed; existing installed serializer/tenant examples support linked paths |
| PT-028 | P1 | Type reference invents async permission/serializer interfaces, return shapes and mypy plugin/stub guarantees | Replaced sketches with actual sync/async contracts and qualified annotation support | Docs fixed; existing installed signature and import checks |
| PT-029 | P1 | Performance guide promises missing projection/profiling/explain APIs, lazy relations and unsupported serializer patterns | Replaced with supported query controls and scoped measurement/transaction guidance | Docs fixed; no performance improvement or capacity claim |
| PT-030 | P2 | Model guide omits inherited timestamps, implies schema creation from declaration, and uses undeclared fields in a uniqueness example | Clarified defaults/migration boundary and removed invalid example constraint | Docs fixed; installed model-default checks |

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

**SDK-001 / P1:** the public 0.7.0 generator emits a `TicketListParams`
interface that is not assignable to its helper's `Record<string, QueryValue>`.
Using the unchanged first-project Ticket model/ViewSet, generation succeeds but
TypeScript 5.9.3 exits 2 with TS2322 at `api.ts(89,75)`. The reproducible
`scripts/check_public_sdk.py --python <wheel-python> --tsc <typescript-compiler>
--output audit-evidence/v071/typescript-sdk-probe.json` preserves that failing
exit code; it is not counted as a passing SDK gate. Evidence and exact
commands are in `audit-evidence/v071/typescript-sdk-probe.json`; the new public
TypeScript how-to exposes this limitation. Recommend a separate generator patch
with actual TypeScript compilation, followed by HTTP client validation. No
runtime fix or suppression is made here. Direct CLI discovery also requires an
importable application module; an explicit public Python script succeeds in the
isolated project where the console entry point did not find `app.views`.

**STORAGE-001 / P1:** public 0.7.0 `FileSystemStorage.save()` accepts
`../media-private/probe.txt` when its root is a sibling named `media`. Both
paths were created inside a fresh temporary directory and removed afterward;
the probe wrote only disposable content. String-prefix containment accepts the
sibling. Evidence is `audit-evidence/v071/storage-boundary.json`. `FileField`
separately rejects parent traversal; this does not claim a bypass of that
validation or data disclosure in an application. Recommend a separate shared
path-helper fix with path-component and symlink regressions. No runtime fix is
included here.

**ACTION-001 / P1:** installed 0.7.0 registers custom HTTP actions as bound
methods without automatically executing ViewSet/decorator permission checks.
An anonymous-state probe receives 403 from generated list and 200 from an inert
custom action, both declaring `IsAuthenticated`. The reproducible
`probe_custom_action_boundary.py` exits 1 for this failed boundary;
`custom-action-boundary.json` records `runtime_boundary_pass: false`. No database,
external provider, or application data was involved. The action guide now
requires explicit checks or delegation to a checked handler; its example denies
anonymous access in an installed-wheel HTTP check. Recommend a separate shared
HTTP action authorization patch with view/action override, object, tenant,
field-write, and REST/MCP parity regressions. No runtime fix is included.

**PT-019 / P1:** serializer guidance advertised unsupported `partial=True`,
`write_only_fields`, nested field declarations, and misleading validation/error
semantics. Replaced with supported Meta configuration, synchronous hooks,
explicit output selection, and documented PATCH limitations. Installed checks
prove normalization, read-only input omission, blank-input rejection and actual
constructor/default contracts. This is not full persistence or bulk atomicity
proof; the progressive tutorial remains the separate database-backed example.

## Broken Examples Found

**EX-001 / P1:** `examples/multitenant/middleware.py` contains `/` in
`EXEMPT_PATHS` and tests every exemption with `path.startswith`. A direct
`dispatch` probe for `/api/projects/` called downstream once and the mocked
tenant resolver zero times. This proves the middleware bypass, not database
exfiltration. Its README now discloses the defect and points to Support Desk.
Fixing middleware semantics is outside this release; recommend a separately
scoped correctness/security patch with authenticated tenant and denial tests.
The example cannot count as a successful tenant-isolation journey.


Startup and selected HTTP execution are now recorded for every example below.
This does not prove every custom action, live provider or security integration.

## Missing User Journeys

The six-chapter ticket desk now covers relations, validation, identity, tenancy,
tasks, durability and optional MCP through executed public instructions. The
production reading review is recorded below; candidate-wheel reruns remain pending.

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

Generated command/parameter inventory now covers all 117 registered commands
and groups in the isolated public 0.7.0 wheel. `cli-contract.json` records
parser declarations without environment values; the generated reference is
verified by `generate_public_cli_reference.py --check`. This is syntax/default
evidence, not execution of all commands. Rewrote CLI overview, workflow and
development-tool pages; removed nonexistent routes, dbshell, fixture, and
natural-language generator commands and corrected pytest flag guidance.
The AI command and console guides also now use actual `ai flows chat` and
file-oriented `ai plan` subcommands. Twelve extracted provider-free commands
passed in the isolated public wheel with socket connections forbidden: help,
the local greeting response, and a read-mode plan template. This does not prove
provider-backed execution or plan application. Evidence is
`audit-evidence/v071/ai-cli-execution.json`. A broader parser-only scan now checks 341 literal Aksara commands from public
shell fences with zero syntax errors. Eleven pipeline/redirection or usage
examples are explicitly excluded in `cli-docs-syntax.json`; this does not
validate file existence, application imports, runtime effects, or forwarded
pytest flags. It does check required arguments and declared choices; this
caught missing provider names in seven setup commands, now corrected.
Corrected `ai flows debug/graph`, migration status, and model inspection
examples. Replaced the nonexistent custom-command framework with an explicit
application-owned Python command pattern. An isolated-wheel run of the existing public syntax/import contracts now
passes all 738 Python fences and every documented Aksara import. Evidence in
`installed-doc-imports.json` binds the result to the current public pages and
contract tests. Import resolution does not establish API stability or execute
snippet bodies; remaining page semantics still require audit.

**PT-015 / P1:** duplicate CLI references advertised unsupported commands and
flags (`makemigrations --check/--empty`, `shell -c`, `routes`, and others).
The four central CLI pages now follow installed declarations; no runtime
commands or aliases were added. The original scan also misclassified forwarded
pytest flags, which must be checked against pytest rather than Click options.

 The pre-existing local
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

Added direct-entry Experimental labels to 15 previously unlabeled AI/Studio
pages. Replaced misleading generic AI-tool JSON with the real generated MCP
discovery path; rewrote route hints as a complete executable metadata example.
Replaced the nonexistent `aksara ai doctor --fix` and fictional SchemaDoctor
class with `schema-health`, `schema-issues` and `analyze_schema_health`. Public
0.7.0 executes the hint snippet and exposes all three documented command groups;
`ai doctor --help` returns 2. Evidence: `audit-evidence/v071/ai-docs-review.json`.
This proves those corrected entry points, not every experimental page's contents.

## Production Documentation Findings

A reading review from Home → Operate → Production Deployment now locates all
11 operator questions in `audit-evidence/v071/operator-reading.json`: migration
and application roles, RLS, services, ordinary/durable workers, Doctor, durable
preflight, retention, backups/monitoring and upgrades. It required no ADR.

The review exposed a malformed Doctor exit-code table and missing production
and durability entry points (PT-011 / P1: misleading gate selection). Rewrote
Doctor around the distinct command policies, linked the matrix format, and
explained that planned template scenarios intentionally fail release policy.
The production guide now links an executed RLS example and the separate durable
preflight recipe. This is a discoverability review by the documentation author,
not independent operator usability evidence or a live production deployment.

`check_public_operator_docs.py --python <isolated-wheel-python> --output
audit-evidence/v071/operator-cli.json` verifies 11 Doctor command forms and
their documented flags against public 0.7.0. Help availability does not prove
command execution or a passing deployment. Documentation/packaging plus the
production-check and security-matrix regressions pass 199 tests; strict MkDocs
and Ruff pass. Candidate production/reference gates remain required.

## Durable Operations Documentation Findings

The current package exports explicit service, worker, executor, registry,
principal-reference, outbox and diagnostic primitives. The user guide must make
these usable without requiring ADR knowledge. Ordinary `TaskRecord` persists
tenant identity, not a complete Principal; task scheduling is not Operation
execution authority.

## Example Findings

All six repository examples are classified in `audit-evidence/v071/example-review.json`.

| Example | Decision | Reason and verified scope |
| --- | --- | --- |
| basic_app | REPLACE minimal-starter role | Keep historical code for comparison; ticket desk supplies the tested minimal path. Startup works, but old seed request is denied and custom lifespan attempts DDL. |
| blog | REWRITE guidance | Correct model inventory, generate migrations, use explicit package entry point and explain missing Principal adapter. |
| crm | REWRITE guidance | Same setup/auth clarification; retain Customer/Deal/Activity learning purpose. |
| multitenant | REPLACE isolation-reference role | Keep historical code; use Support Desk/ticket desk for authenticated forced-RLS isolation. EX-001 remains a separate runtime patch. |
| ai_providers | REWRITE guidance | Experimental application-owned adapters and status only; no Ollama adapter or live provider claim. |
| support_desk | KEEP | Production-oriented packaged reference; clarify migration directory, role separation and ordinary tasks versus Operations. |

`audit_public_examples.py` copies the five demonstration apps into temporary
application directories and imports Aksara from public 0.7.0. It generates or
applies migrations in isolated PostgreSQL schemas, exercises each lifespan and
selected HTTP endpoints, then drops the schemas. All five start. Twelve GET
observations return 200; six generated-write observations return the documented
403 (including Blog/CRM requests with their example API-key headers). These are
startup and denial checks under a schema-owner login, not RLS certification or
full feature tests. The gate fails if these observed contracts change.

The built 0.7.0 Support Desk wheel passes its separate 66-check production gate;
all 12 application Python files match the current source. Candidate-wheel reruns
remain required. No provider is called; provider quality and availability remain
outside this baseline. No example runtime or security behavior was changed.
The related example, pattern, documentation and packaging test selection passes
350 tests with two optional OpenAI-SDK skips. Ruff and strict MkDocs pass.
Evidence JSON parses and contains no connection URL or generated-password
patterns. Tests bind the execution/review evidence to the current source hashes.

EX-002 / P1: old Basic/Blog/CRM READMEs claimed unauthenticated seeding worked;
those generated requests return 403. Documentation now points to the complete
Principal adapter in the ticket desk rather than weakening permissions.
EX-003 / P1: Blog/CRM/Multitenant setup omitted generation of their absent
application migrations. Explicit `makemigrations --app` and migration directories
are now included. EX-004 / P2: provider README conflated framework AI Hub/Ollama
with its three application-owned adapters; corrected scope and configuration.


## Clean-Room Journey Results

Six consecutive chapters now run from exact Markdown file fences in a
temporary scaffold using the independently installed public 0.7.0 wheel,
local PostgreSQL and an ephemeral NOSUPERUSER/NOBYPASSRLS application role:

| Stage | Public application tests | Evidence |
| --- | --- | --- |
| First project | 3 passed | Authenticated CRUD, anonymous denial, field validation |
| Relationships | 5 passed | Existing tests plus normalization, nullable FK and SET NULL |
| Tenant boundary | 12 passed | Existing tests plus two-tenant reads/writes, role denial, missing tenant, forged headers/payloads, cross-tenant assignee validation |
| Queued report and CSV export | 16 passed | Existing tests plus worker completion, tenant provenance, current read permission and protected download |
| Durable ticket resolution | 22 passed | Existing tests plus idempotency, post-SQL rollback/retry, separate worker processes, cancellation, role revocation and command allowlist |
| Optional MCP client | 28 passed | Existing tests plus official SDK negotiation and generated CRUD, scope/expiry/tenant/field/current-role denial, Principal type and no protocol Tasks |

These are **86 test executions, 28 unique final-stage tests**, not 86 unique
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
The durable baseline journey now covers action/resolver registration, protected
admission, idempotency/conflict, status, cancellation before claim, post-SQL
failure rollback, retry in a new process and role revocation before execution.
It does not certify a full process-death campaign, approval UI, external effects
or a production identity integration. The MCP baseline journey now uses the installed official SDK 2.0.1 with its
`httpx2` transport. It verifies current-role denial after discovery and the same
validation through REST. It does not certify a production OAuth integration,
durable agent resolver or model-provider behavior. The operator journey and
candidate-wheel certification remain incomplete.

Observed friction and corrections: tenant migration generation needs an explicit
backfill for existing rows; the chapter replaces only the generated operations
and keeps dependencies. The tenant payload denial is HTTP 422 from the generated
schema on both create and PATCH, rather than the initially assumed 403. Tests
now assert that actual boundary and verify ownership remains unchanged. Foreign
keys alone do not enforce customer membership; the tutorial explicitly checks
assignee accessibility before saving. Durable retries return to `ready`, not an
invented retry state. The action service needs an explicit application admission
gate; the built-in router requires authentication but does not replace that
permission. The tutorial supplies both admission and execution checks. Router
construction needs the connected application database, so the documented factory
registers it during one application lifespan and creates a fresh app for another
lifecycle. No runtime fix was made for these items.

## Media and Email Review

Replaced the unauthenticated custom upload route with an explicit explanation
of application identity, record permission, tenant scope and private download
responsibilities. The old route directly loaded and saved arbitrary Asset IDs
and returned storage URLs without those checks (PT-012 / P1). Clarified that
file bytes and email effects are not rolled back by PostgreSQL, and that
`FieldFile.delete()` clears the in-memory reference without saving the model.

The complete public `check_media.py` runs from installed 0.7.0 without a
network or database. Nine checks cover storage save/read/size/URL/delete,
FileField name validation and in-memory email. The runner handles macOS's
resolved temporary-directory path before containment assertions. This does not
prove authenticated upload, SMTP delivery, S3 policy or database-file atomicity.
The existing storage/media mounting/migration-field tests pass 9 tests.

## Automated Truth Gates

The installed import runner also executes the documented ViewSet class body
with a supplied model prerequisite and checks real FastAPI route registration,
OpenAPI success statuses, explicit permissions, disabled example SSE/AI settings,
and base-class defaults/hooks. This is registration evidence, not CRUD database
execution; the progressive tutorial separately supplies the real HTTP/DB checks.

Authentication and permissions guidance now has a dedicated installed-wheel
PostgreSQL gate: `scripts/check_public_auth.py`. It executes the exact account
service and active-owner snippets. Nineteen checks cover normalized account
creation, hashed storage, correct/wrong/unknown/inactive authentication, session
lookup and revocation, attached-user dependencies, and actual ViewSet hook
acceptance/denial. The schema is created under a random name and removed with
catalog verification. This is not a complete HTTP login, external JWT/provider,
or RLS certification; the ticket-desk journey supplies the separate HTTP/RLS
proof. Evidence is `audit-evidence/v071/auth-permission-execution.json`.

The rendered-site link gate checks local page, fragment, stylesheet, script, and
image targets, including links under the published `/Aksara/` prefix. It found
a nonexistent `stylesheets/extra.css` referenced on all 158 HTML pages; removing
the stale MkDocs `extra_css` entry fixes those requests without changing any
framework behavior. The rebuilt site passes 49,040 local link/asset checks.
External links are counted but not fetched by this gate. Evidence is
`audit-evidence/v071/rendered-links.json`; source freshness and negative-control
tests prevent a missing asset or fragment from being mistaken for a pass.

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
pass after these edits. Six progressive public-baseline chapters now execute;
the candidate and remaining journeys still need proof. Functional runtime source
is unchanged.

## Remaining Documentation Debt

Candidate journeys, remaining public-page/snippet audit, full usability review, candidate
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
--output audit-evidence/v071/first-project-journey.json` passes 86 HTTP/protocol test
executions across six successive stages. The controller receives the local DB
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

Earlier progressive-tutorial validation: `pytest tests/docs tests/test_v048_docs_lock.py
 tests/test_v048_packaging_sanity.py -q` passes **132 tests**. Strict MkDocs and
Ruff on the runner and evidence tests pass. PostgreSQL catalog verification
finds zero leftover tutorial schemas or roles after the journey.

## Runtime Changes

**No functional runtime changes.** `aksara/cli/scaffold.py` changes only its
generated README text; equivalence evidence above covers all executable files,
settings, security defaults and dependencies. Package version remains `0.7.0` until candidate readiness is proven.

## Query Guide PostgreSQL Evidence

`scripts/check_public_queries.py --python <isolated-wheel-python> --output
audit-evidence/v071/query-execution.json` executes all eight querying-guide
Python fences unchanged, with the exact first-project Ticket model and a
seeded, uniquely named PostgreSQL schema. Eighteen assertions cover ordered
unresolved rows, identifier lookup, missing lookup handling, first selection,
OR/negation, conditional filters, offset pagination, count/existence/aggregate,
and explicit output projection. The runner verifies installed-package imports
and removes and checks removal of its own schema. No credentials are stored in
the evidence. Setup uses test-owned DDL; this is not migration, RLS, concurrent
access, or HTTP authorization evidence. The initial fixture omitted the base
model's `updated_at` column; that fixture error was corrected before the passing
run. No framework change was made.

The same installed PostgreSQL gate now executes the exact signal normalization
snippet and checks insert/update payloads, pre-commit callback timing, outer
rollback, nested savepoint rollback with outer commit, and disconnection.
It passes **25 assertions** including the 18 query assertions above. In-memory
callback observations remain after a database rollback, directly demonstrating
why `post_save` is not commit evidence. This probe makes no external network
calls and does not claim durable callback delivery. Its evidence is also bound
to the signal and transaction guide hashes.

## Full Source Regression Checkpoint

At `bb8e65c`, `.venv/bin/python -m pytest -q` with
`AKSARA_REQUIRE_DATABASE_TESTS=1` and the local `aksara_test` PostgreSQL database
passed **8,312 tests**, with **2 skips and 25 warnings**, in **119.97 seconds**.
`AKSARA_REQUIRE_SECURITY_MATRIX=false` matches the general suite profile; this
is not a substitute for the strict Doctor release gate. Runtime versions and
the credential-checked log hash are in
`audit-evidence/v071/full-regression-checkpoint.json`.

`scripts/check_v071_runtime_scope.py --output
audit-evidence/v071/runtime-scope.json` confirms the only changed production
file is the scaffold module, and its AST is identical to v0.7.0 outside the
README template return value. `pyproject.toml` is unchanged. This supplements,
but does not replace, generated-file equivalence and candidate startup checks.
Candidate version/build, compatibility matrix, hosted checks and the remaining
public-page audit are still incomplete.

## Durable Outbox Operator Guidance

Added `how-to/export-durable-transitions.md` to the operator navigation. It
documents the public exporter's explicit namespace/tenant scope, callback
contract, ambiguous false result, at-least-once acknowledgement window, lease
versus timeout, payload limits and application-owned sink retention. These
claims were checked against `aksara/durable/outbox.py` and repository transition
payload construction. The source regression test covers sink failure/retry
without changing authoritative Operation state. The new helper still needs
installed-wheel scenario execution; remote durable delivery is not claimed.
