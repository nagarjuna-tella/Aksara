# Aksara v0.7.1 Public Truth Audit

## Executive Summary

Work in progress; this is not release approval. The
[requirement review](audit-evidence/v071/requirement-review.md) maps all 63 phases,
release boundaries and named deliverables to current evidence and open work.
The dated/checkpoint sections below retain historical results; they are not
current-head or candidate certification. The capability matrix is the current
summary; individual artifacts define each check's limits.

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

This matrix separates 35 capability areas rather than combining independent
contracts into a feature checklist. Stability follows the published v0.6/v0.7
contracts and `concepts/stability.md`; existence alone does not establish stability.
Installed-wheel entries identify the exercised slice. Unless labeled development,
they use the public 0.7.0 wheel. Development evidence also reports version 0.7.0,
so the scaffold build/equivalence artifacts identify it separately.
Every candidate-wheel entry remains pending until the final candidate is built
and the release gates are rerun. “Pending” is not an absence of historical tests.

| Capability | Exists? | Stability | Public API / source anchor | Docs quality | Runnable example / test anchor | Installed wheel evidence | Notes / remaining proof |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ORM | Yes | Stable bounded contract | `aksara.Model` | Reviewed models, query and signal guides | Ticket desk; exact signal helper | CRUD plus signal/transaction slice ([evidence](audit-evidence/v071/query-execution.json)) | Post-save runs before outer commit; rollback does not undo observed callbacks. Bulk create, text update and upsert now have installed evidence; Boolean/timestamp bulk_update fails (BULK-001). Candidate coverage remains open. |
| Query API | Yes | Stable documented methods | `Model.objects`, `Q`, `F` | Query guide rewritten and executed | All eight query-guide Python blocks | Filters, Q/negation, ordering, aggregate and projection ([evidence](audit-evidence/v071/query-execution.json)) | Seeded PostgreSQL fixture; not concurrency, RLS or every query method. Full query regression remains required. |
| Fields | Yes | Stable declared types | `aksara.fields` | Reference declarations/defaults corrected | Exact JSON/Array/Vector guide blocks | PostgreSQL/pgvector round trips and rejection slice ([evidence](audit-evidence/v071/advanced-field-execution.json)) | Seven advanced-field blocks, the validation fragment and complete catalog declarations execute; separate full field regressions and candidate coverage remain required. |
| Relations | Yes | Stable with exclusions | `fields.ForeignKey`, `OneToOne`, `ManyToManyField` | Forward/reverse/eager contracts corrected | Ticket assignee; real Admin relation fixture | Nullable/eager FK plus complete FK/O2O/self/M2M example ([evidence](audit-evidence/v071/admin-relation-execution.json)) | Synchronous cached get_related; stored forward ID is not a lazy object. The gate now executes M2M membership/reverse access; it does not prove every M2M operation or migration. RELATION001: first() omits requested eager loading; use the documented all() path. |
| Migrations | Yes | Stable | `aksara makemigrations`, `migrate`, `aksara.migrations` | Reference and safety boundaries corrected | Two exact versioned migrations; ticket desk | 12 executor checks: backfill, repeat, rollback and checksum ([evidence](audit-evidence/v071/migration-doc-execution.json)) | Canonical executor under an owned schema; not a historical v0.6 application upgrade, concurrent CLI or candidate certification. MIGRATION-001: CLI model-name collision omits the historical template User table; domain-template evidence records that failure. |
| Serializers | Yes | Stable documented API | `aksara.api.serializers.ModelSerializer` | Core journey rewritten | Ticket subject validation | Create and PATCH validation | Public `ValidationError` gives 422; background ORM writes do not automatically run HTTP serializers. |
| Generated REST/ViewSets | Yes | Stable declared surface; known defects | `aksara.ModelViewSet`, `include_viewset`, `action` | Registration, filters and pagination corrected | Ticket desk; exact search and pagination ViewSets | CRUD plus 11 filter checks and 8 pagination observations ([filter evidence](audit-evidence/v071/filter-doc-execution.json), [pagination evidence](audit-evidence/v071/pagination-doc-execution.json)) | PAGINATION-001 strips page/cursor metadata at HTTP serialization; ACTION-001 requires explicit custom-action checks. Full candidate regressions remain required. |
| Authentication | Yes | Stable covered backend paths | `aksara.contrib.auth`, application adapters | Account/session and adapter boundaries corrected | Exact account/session helper; local HTTP adapter | 19 primitive/permission checks ([evidence](audit-evidence/v071/auth-permission-execution.json)) | Database account/session behavior is exercised; no production HTTP login, JWT or provider certification. |
| Principal | Yes | Stable | `aksara.security.principal.Principal` | Reviewed identity explanation | Ticket identity + durable resolver | Human and tenant context | MCP-agent identity, scope, expiry and human-owner membership are now exercised too. |
| Permissions | Yes | Stable | `BasePermission`, `IsAuthenticated`, `check_permissions` | Reviewed application pattern | Reader/editor ticket policy | Request/object denial | Custom endpoints must explicitly call their policy; they do not inherit ViewSet permissions. |
| PolicyEngine | Yes | Stable documented methods | `aksara.security.policy.PolicyEngine` | Reviewed decision/enforcement separation | Generated CRUD; durable authorizer | Covered query/write policy slice | Existing policy regressions cover metadata fallback; decisions alone do not enforce every ORM write. |
| Field-level policy | Yes | Stable covered write paths | `PolicyEngine.validate_payload`, enforcement helpers | Reviewed metadata and path-dependent enforcement | Tenant-owned field; durable resolved field | Owned-field denial | Schema 422 and runtime permission denial are distinct; absent field metadata allows payload after action checks. Custom handlers own integration. |
| Multi-tenancy | Yes | Stable covered context paths | `TenantModel`, `aksara.middleware.context` | Runnable chapter added | Two-customer ticket desk | HTTP and ordinary-task context | Tenant identity comes from server-owned membership, not request headers. |
| PostgreSQL RLS | Yes | Stable restricted-role contract | `aksara.tenancy` helpers; migration SQL | Runnable chapter added | Forced-RLS ticket tables | Raw SQL plus HTTP denial | Actual NOSUPERUSER/NOBYPASSRLS posture checked; raw cross-tenant INSERT rejected. |
| Admin | Yes | Evolving details | `aksara.contrib.admin` | Mount, permission, relation, widget and action guidance corrected | Anonymous mount/login; exact owner permission hook | Mount plus 16 real database relation/example checks ([evidence](audit-evidence/v071/admin-relation-execution.json)) | Installed action fragment and widget checks add mocked update/message and escaping/mutation evidence; not full authenticated Admin CRUD or RLS coverage. ADMINWIDGET001 preserves the input-mutation defect. |
| Ordinary tasks | Yes | Stable unlinked behavior | `aksara.task`, `aksara.tasks.TaskWorker` | Guide corrected; runnable chapter | Queued ticket report | Enqueue, worker, guarded result | Persists tenant, not full Principal; separate task recovery/retention gates remain. |
| Durable Operations | Yes | Stable v0.7 semantic contract | `aksara.durable` action/service/router/worker exports | Runnable chapter added | Durable ticket resolution | Admission, rollback/retry, cancel, revocation | New process per one-shot attempt; not a full crash campaign or fleet scheduler. |
| Approvals | Yes | Stable distinct boundaries | Signed MCP grants; durable approval decisions | Durable decision how-to added | Exact decision helper | 12 installed PostgreSQL checks | Service decisions tested; no approval UI or HTTP/worker execution claim. Sync grants remain distinct. |
| External effects | Yes | Stable declared effect classes | `ExternalEffectAdapter`, `ExternalOperationExecutor` | Recovery how-to added | Exact notification adapter and action | 13 installed PostgreSQL checks | Simulated provider only; no real delivery, RLS or process-crash guarantee. |
| Audit history | Yes | Stable bounded semantics | Service history; MCP audit sinks | History how-to added | Exact status/history projection | 13 installed PostgreSQL checks | Limited newest-first reads; retired terminal actions retain tenant reads without removed action policy. |
| Outbox export | Yes | Stable bounded semantics | `DurableOutboxExporter` | Operator how-to added | Exact helper plus PostgreSQL admission/export | 12 installed-wheel checks | Admin-role fixture and simulated sink only; operator owns durable remote delivery/retention. |
| CLI | Yes | Stable core commands | `aksara` command groups | Generated reference and literal command audit | 117 command definitions; tutorial and operator commands | 292 documented commands parse ([evidence](audit-evidence/v071/cli-docs-syntax.json)) | Parsing does not execute callbacks; 7 exclusions are explicit. Tutorial, operator and local AI executions provide narrower behavioral proof. |
| Scaffold | Yes | Experimental template layout | `aksara startproject` output | README corrected; editable-install defect documented | Fresh generated stubs; six-stage tutorial | Development-wheel startup and 18-file comparison ([evidence](audit-evidence/v071/scaffold-wheel-equivalence.json)) | Only README differs after token normalization. Exact install/dev path runs; editable packaging still fails (SCAFFOLD-001). Three domain copies now have installed command/HTTP evidence; the historical tenant schema remains incomplete (MIGRATION-001). This is not a candidate wheel. |
| Doctor | Yes | Stable exit/JSON contract | Doctor CLI; `check_durable_operations` | Production policy, fix-plan filters and optional-service outcomes clarified | Launch check; packaged Support Desk | Baseline production profile plus launch checks ([evidence](audit-evidence/v071/support-desk-baseline.json)) | Production acceptance is scoped to the reference configuration; final candidate profile and operator environment remain separate gates. |
| File/Image fields | Yes | Stable bounded field contract | `fields.FileField`, `ImageField` | Upload/storage ownership and persisted lifecycle corrected | Media helper; historical field suite | Local File/Image persistence and lifecycle ([evidence](audit-evidence/v071/media-lifecycle.json)) | Installed local lifecycle proof is recorded in media-lifecycle.json; no protected HTTP upload, S3 or complete image-processing claim. Separate advanced field regressions remain required. |
| Storage integrations | Yes | Evolving | `aksara.storage` | Rewritten media guide and STORAGE-001 limitation | Complete local storage/email script | Nine local checks pass | This nine-check storage gate does not cover SMTP/S3; the separate File/Image row covers persisted local lifecycle. Direct filesystem containment needs a separate patch. |
| TypeScript SDK | Yes | Evolving | `aksara.sdk.generate_typescript_sdk` | New how-to and explicit type-checking limitation | Ticket ViewSet generator script | Generation passes; TypeScript fails | SDK-001: generated list params lack required index signature; separate patch required. |
| MCP | Yes | Stable synchronous contract | `aksara.mcp`; `/mcp/` Streamable HTTP | Quickstart consolidated; runnable chapter | Ticket desk official client | Generated execution and denial | SDK 2.0.1 verified; no protocol Tasks or automatic durable agent dispatch. |
| AI/provider/runtime | Yes | Experimental | `aksara.ai` | Experimental status, CLI examples and execution lifetimes corrected | Route hint; local greeting and plan template | 12 local CLI checks ([evidence](audit-evidence/v071/ai-cli-execution.json)) | Sockets forbidden in this gate; no provider/planner quality or autonomous execution claim. Installed deterministic planner/codegen/patch-preview checks also pass; full experimental behavior is not certified. |
| Studio | Yes | Experimental | Studio UI and internal HTTP surfaces | Experimental boundary, origin and credential behavior clarified | Scaffold default-route probe; Studio guides | Default UI disabled ([evidence](audit-evidence/v071/scaffold-startup.json)) | Eight installed dependency-level HTTP cases cover Origin and bearer rules; neither these nor disabled-route proof certify enabled Studio workflows. Not a production investigation or audit store. |
| Workflows/DurableStep | Yes | Evolving | `aksara.workflows.DurableStep` | Force, cancellation, identity and codec boundaries corrected | Exact generic/step helpers | 23 installed PostgreSQL observations ([evidence](audit-evidence/v071/generic-step-execution.json)) | Normal claim exclusion, forced overlap and cancelled running state are exercised; no process-death, RLS, authorization or Operation guarantee. |
| Configuration | Yes | Stable documented contract | `Settings`, `settings`, `configure` | Reference rewritten and checked | Settings/upgrade examples | Explicit overrides and upgrade recipe | POSIX origin-list env parsing defect documented with explicit-list workaround. |
| Durable persistence internals | Yes | Internal | Repositories, raw rows and failure hooks | Separated from public contract | Framework tests only | Not a public API gate | Do not expose raw provenance/fences as application contract merely because imports exist. |
| Legacy provider configuration | Yes | Deprecated | `Settings.ai_default_provider`, `ai_providers`, `ai_secret_hints` | Reference labels compatibility fields | Settings reference | Not recommended example | Retained metadata fields, not recommended provider setup. |
| Application testing | Yes, limited helpers | Evolving | `aksara.testing`; standard pytest/unittest | Rewritten with explicit fixture ownership | Exact standalone serializer/permission tests | 3 development-wheel tests ([evidence](audit-evidence/v071/testing-execution.json)) | TESTING-001: cleanup helper is not general rollback isolation; source-confirmed, negative runtime probe pending. |

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
| PT-004 | P2 | Navigation promotes experimental AI before the backend journey; entry pages teach competing starter apps | Added Start/Build/Operate/MCP/Reference/Experimental/Contribute paths, retained every page destination, and consolidated entry pages around the tested ticket desk | Docs fixed |
| PT-005 | P1 | Settings reference lists shortened task environment names without `_SECONDS` | Correct to installed names and verify the settings table | Docs fixed |
| PT-006 | P1 | Settings pages imply dataclass constructor overrides always beat environment, and that the global database URL starts an `Aksara()` database lifespan | Explain keyword overrides and explicit settings-to-constructor handoff | Docs fixed |
| PT-007 | P2 | Glossary claims memory/Redis cache backends and omits Operation/Attempt/Principal distinctions | Removed unsupported cache claim and added authority/execution terminology | Docs fixed |
| PT-008 | P1 | Durable guide mounts the generic router without explaining application admission permissions or the connected-database lifecycle | Added explicit admission boundary explanation and runnable factory/resolver/worker tutorial | Docs fixed |
| PT-009 | P2 | Older MCP quickstart duplicates an unrelated app and uses `httpx.AsyncClient` rather than the installed SDK 2.0 transport type | Consolidated entry around the tested ticket desk and `httpx2.AsyncClient`; no dependency change | Docs fixed |
| PT-010 | P2 | Docs home calls released v0.7.0 a candidate; tutorial index directs readers to a separate `aksara/examples` repository rather than the documented source | Corrected released status and linked the canonical source-bearing chapters and repository example catalog | Docs fixed |
| PT-011 | P1 | Doctor page mixes launch exit codes with check descriptions and omits strict production/durable preflight entry points | Separate command policies and link the matrix and service preflight | Docs fixed |
| PT-012 | P1 | Media upload example lacked identity, object and tenant checks | Replaced unsafe route with explicit application responsibilities; see Media and Email Review | Docs fixed; scoped primitive checks |
| PT-013 | P1 | Schema Doctor guide advertised nonexistent `ai doctor --fix`; AI tools implied universal executable tool names | Replaced with installed schema commands and generated MCP discovery; route hints now use executable public APIs | Docs fixed |
| PT-014 | P1 | Standalone Blog and Multi-Tenant tutorials combine legacy configuration/request APIs with incomplete authentication and strong isolation claims | Merged runnable learning into the tested ticket desk; retained task-specific mapping and explicit tenancy requirements at existing URLs | Docs fixed |
| PT-015 | P1 | CLI references advertised unsupported commands | Actual command reference and installed parsing/execution checks; see detailed checkpoint below | Docs fixed; scope retained |
| PT-016 | P1 | Authentication guide claims ordinary `objects.create(password=...)` hashes passwords and documents nonexistent login/JWT/reset APIs | Replaced with built-in `create_user`, `authenticate`, hashing/session primitives and explicit application-owned identity adaptation | Docs fixed; installed PostgreSQL proof |
| PT-017 | P0 | Permission examples use async hooks although ModelViewSet calls hooks synchronously, so an unawaited denial coroutine is truthy; examples also assume an unset DRF-style `self.action` | Replaced with synchronous active-owner permission and explicit list/create/object boundaries; verified owner, non-owner, inactive and anonymous outcomes | Docs fixed; no runtime behavior change |
| PT-018 | P1 | ViewSet guide advertised ignored DRF-style attributes, unsupported handler helpers, PUT routes, and action-removal switches | Replaced with actual registration, PATCH/detail paths, per-operation serializers, synchronous list query hook and explicit permission boundaries | Docs fixed; installed route/default checks |
| PT-019 | P1 | Serializer examples used unsupported constructor/options/hooks | Supported serializers and PATCH limits documented; see detailed checkpoint below | Docs fixed; scope retained |
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
| PT-031 | P1 | Admin async permission example treats a forward FK as a loaded object | Replaced with explicit Author query and fail-closed staff/owner checks; clarified form CSRF and process-local rate limits | Exact hook now verified with installed PostgreSQL; initial get_related mock was invalid and superseded |
| PT-032 | P1 | Relation guide advertised unsupported access/manager behavior | Stored IDs and explicit relation APIs documented; see detailed checkpoint below | Docs fixed; scope retained |
| PT-033 | P1 | Testing guide promised automatic rollback isolation | Fixture ownership and TESTING-001 disclosed; see detailed checkpoint below | Docs fixed; scope retained |
| PT-034 | P1 | Bulk guide overstated atomicity and write behavior | Batch boundaries and BULK-001 disclosed; see detailed checkpoint below | Docs fixed; scope retained |
| PT-035 | P1 | Custom field guide used nonexistent lifecycle APIs | Actual conversion/preparation hooks documented; see detailed checkpoint below | Docs fixed; scope retained |
| PT-036 | P1 | Field/filter examples used unsupported options | Constructors and validation examples corrected; see detailed checkpoint below | Docs fixed; scope retained |
| PT-037 | P1 | Migration examples mixed runtime and migration fields | Actual migration constructors and execution checked; see detailed checkpoint below | Docs fixed; scope retained |
| PT-038 | P1 | Filtering implied configuration alone restricted queries | Actual filtering behavior and limits documented; see detailed checkpoint below | Docs fixed; scope retained |
| PT-039 | P1 | Pagination overstated cost and response metadata | Observed metadata loss PAGINATION-001 disclosed; see detailed checkpoint below | Docs fixed; scope retained |
| PT-040 | P1 | Generic workflows implied production durability | DurableStep boundaries and forced/cancel behavior documented; see detailed checkpoint below | Docs fixed; scope retained |
| PT-041 | P2 | Localization examples lacked coherent application setup | Executable conversion/HTTP examples supplied; see detailed checkpoint below | Docs fixed; scope retained |
| PT-042 | P1 | Exception reference implied universal hierarchy | Actual exception and HTTP boundaries documented; see detailed checkpoint below | Docs fixed; scope retained |
| PT-043 | P0 | Debug guide claimed unsupported IP protection | Actual debug exposure and address behavior documented; see detailed checkpoint below | Docs fixed; scope retained |
| PT-044 | P1 | Profiling claimed automatic integration | Explicit profiler behavior and limitations documented; see detailed checkpoint below | Docs fixed; scope retained |
| PT-045 | P0 | AI debug implied provider analysis and protection | Local advisor/context behavior and exposure documented; see detailed checkpoint below | Docs fixed; scope retained |
| PT-046 | P0 | Patterns promoted historical examples as protected apps | Limits and canonical alternatives documented; see detailed checkpoint below | Docs fixed; scope retained |
| PT-047 | P1 | Entry hubs taught divergent setup paths | Canonical tutorial navigation reconciled; see detailed checkpoint below | Docs fixed; scope retained |
| PT-048 | P1 | Middleware options/logging claims exceeded implementation | Actual signatures, order and log behavior documented; see detailed checkpoint below | Docs fixed; scope retained |
| PT-049 | P0 | Tenant extraction was presented as trusted isolation | Trusted identity and extraction separated; see detailed checkpoint below | Docs fixed; scope retained |
| PT-050 | P1 | Starter instructions diverged from generated files | Installation/layout/startapp guidance verified; see detailed checkpoint below | Docs fixed; scope retained |
| PT-051 | P1 | Database/startup examples overstated behavior | Actual setup and lifecycle instructions verified; see detailed checkpoint below | Docs fixed; scope retained |
| PT-052 | P1 | Soft-delete examples hid query and helper limitations | Actual deletion APIs and SOFTDELETE001 documented; see detailed checkpoint below | Docs fixed; scope retained |
| PT-053 | P1 | Fixtures promised unsupported restore semantics | Fixture limits and three defects documented; see detailed checkpoint below | Docs fixed; scope retained |
| PT-054 | P1 | Metadata reference described nonexistent interface | Public meta shape and supported options verified; see detailed checkpoint below | Docs fixed; scope retained |
| PT-055 | P1 | Inspector implied catalog and real ANALYZE proof | Declaration/synthetic boundaries and INSPECTOR001 disclosed; see detailed checkpoint below | Docs fixed; scope retained |
| PT-056 | P2 | Widget limits implied server enforcement | UI limits and ADMINWIDGET001 documented; see detailed checkpoint below | Docs fixed; scope retained |
| PT-057 | P1 | Admin actions omitted permission/transaction ownership | Action registration and caller responsibility clarified; see detailed checkpoint below | Docs fixed; scope retained |
| PT-058 | P1 | Diagnostic suggestions implied execution/complete coverage | Suggestion and filtered exit-code behavior verified; see detailed checkpoint below | Docs fixed; scope retained |
| PT-059 | P1 | Search overstated semantic/provider/cache guarantees | Local search and process scope documented; see detailed checkpoint below | Docs fixed; scope retained |
| PT-060 | P1 | Studio conflated Origin and credentials | Exact dependency behavior documented and tested; see detailed checkpoint below | Docs fixed; scope retained |
| PT-061 | P1 | AI safety called released durability deferred | Experimental runtime and durable Operations separated; see detailed checkpoint below | Docs fixed; scope retained |
| PT-062 | P2 | Gap analysis claimed eight parallel categories | Nine sequential categories and failure paths verified; see detailed checkpoint below | Docs fixed; scope retained |
| PT-063 | P1 | Security references blurred parsing and enforcement | Credential and field integration boundaries clarified; see detailed checkpoint below | Docs fixed; scope retained |
| PT-064 | P1 | Security overview lagged release automation/policy | Current workflow and matrix boundaries reconciled; see detailed checkpoint below | Docs fixed; scope retained |
| PT-065 | P1 | MCP/field/query guidance mixed versions and limits | Synchronous approval, historical policy and query limits clarified; see detailed checkpoint below | Docs fixed; scope retained |
| PT-066 | P2 | Release guide omitted candidate-specific validation | Exact-ref evidence and historical guidance clarified; see detailed checkpoint below | Docs fixed; scope retained |
| PT-067 | P1 | ORM overview and glossary retained unsupported query, relation, database and helper claims | Rebuilt overview around the tutorial and corrected terminology; see conceptual review below | Docs fixed; candidate validation open |

The register consolidates all 67 findings. “Docs fixed” describes the recorded
correction, not candidate acceptance or a fix to underlying runtime defects.
Detailed sections retain commands, failures, limitations and historical results.

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
precedes `DATABASE_URL`. The corrected deployment tutorial uses this explicit
configuration path. Defaults are checked against `aksara/conf.py`, not copied
from legacy prose.

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
`audit-evidence/v071/ai-cli-execution.json`. The current parser-only scan checks
316 literal Aksara commands from public shell fences with zero syntax errors. Eleven pipeline/redirection or usage
examples are explicitly excluded in `cli-docs-syntax.json`; this does not
validate file existence, application imports, runtime effects, or forwarded
pytest flags. It does check required arguments and declared choices; this
caught missing provider names in seven setup commands, now corrected.
Corrected `ai flows debug/graph`, migration status, and model inspection
examples. Replaced the nonexistent custom-command framework with an explicit
application-owned Python command pattern. The current isolated-wheel
syntax/import gate checks 521 Python fences and documented Aksara imports.
`installed-doc-imports.json` binds that result to the public pages and selected
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
durable agent resolver or model-provider behavior. The separate operator
reading review is recorded above; candidate-wheel certification remains incomplete.

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

**No functional runtime changes.** Three production files have instructional
changes: `aksara/cli/scaffold.py` changes generated README text;
`aksara/cli/main.py` changes the `startproject` and `startapp` docstrings and existing
UI/Click message string literals; `aksara/cli/templates/__init__.py` changes four template
descriptions. The AST audit preserves all other logic, template names/sources,
flags, defaults and dependencies. Four-template installed-wheel comparison
permits only the prior README changes in generated output. Package version
remains `0.7.0` until candidate readiness is proven.

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
Candidate version/build, hosted checks and the remaining public-page audit
are still incomplete. The later local compatibility checkpoint is recorded below.

## Durable Outbox Operator Guidance

Added `how-to/export-durable-transitions.md` to the operator navigation. It
documents the public exporter's explicit namespace/tenant scope, callback
contract, ambiguous false result, at-least-once acknowledgement window, lease
versus timeout, payload limits and application-owned sink retention. These
claims were checked against `aksara/durable/outbox.py` and repository transition
payload construction. The source regression test covers sink failure/retry
without changing authoritative Operation state. The exact helper now executes against the isolated public wheel and PostgreSQL:
12 checks cover migrations, configured defaults, tenant/non-tenant/namespace
selection, sink failure, retry delay, duplicate payload after simulated
acknowledgement loss, and unchanged authoritative state. Evidence is
`audit-evidence/v071/outbox-execution.json`; the uniquely named schema was
removed and removal verified. The fixture uses an admin role and an in-process
sink, so restricted-role RLS, process-crash behavior and remote durable delivery
are not claimed.

## Local Compatibility Matrix Checkpoint

At `f7547fed5d9190d110f90177bbb76d60bc630171`, all four supported
Python/web combinations passed the full source suite against local PostgreSQL
18.4 (`aksara_test`) with required database tests enabled.

| Python | Web boundary | Result |
| --- | --- | --- |
| 3.11.5 | latest-supported | 8313 passed, 2 skipped, 25 warnings in 110.15s |
| 3.11.5 | minimum | 8313 passed, 2 skipped, 25 warnings in 102.66s (0:01:42) |
| 3.14.4 | latest-supported | 8313 passed, 2 skipped, 25 warnings in 106.54s (0:01:46) |
| 3.14.4 | minimum | 8313 passed, 2 skipped, 25 warnings in 101.54s (0:01:41) |

Minimum means FastAPI 0.136.1 / Starlette 1.0.1; latest-supported means
FastAPI 0.141.1 / Starlette 1.6.0. Each command runs the selected environment
Python with `-m pytest --tb=short -q`. JSON metadata and hashed logs are
`audit-evidence/v071/matrix-*.json` and matching `.log` files. Three cells use
`scripts/run_v071_regression.py`; the Python 3.11 latest-supported cell was
run directly before that wrapper was added. All four log hashes were verified
and the supplied database password was absent from each log.

This is a source checkout checkpoint, not final candidate-wheel evidence or
hosted PostgreSQL 16 validation. The general suite uses
`AKSARA_REQUIRE_SECURITY_MATRIX=false`; strict Doctor/release profiles remain
separate gates. The increase from 8,312 to 8,313 tests is the added outbox
evidence freshness test. No production behavior or dependency range changed.

## Durable Approval How-to Evidence

`how-to/require-durable-approval.md` explains registering an approval-required
action, the separate reviewer callback, current server-owned identity/reference,
required action scopes, waiting/ready/rejected/expired outcomes, conflicts and
application-owned reviewer policy. It explicitly excludes implicit separation
of duties and distinguishes durable decisions from synchronous MCP grants.

`scripts/check_public_approvals.py` extracts its exact helper and executes it
against the isolated public 0.7.0 wheel and local PostgreSQL. Twelve checks
cover migrations, waiting admission, claim eligibility, reviewer role and action
scope denials, mismatched provenance, tenant selection, approval, repeated
conflicting decisions, rejection and approval expiry. Its uniquely named schema
is removed and removal verified. `approval-execution.json` binds the page and
runner hashes; a documentation test detects stale evidence. The fixture uses an
admin database role and service calls. It does not prove restricted-role RLS,
HTTP authentication, reviewer UI usability, worker execution or process loss.
Those are separate tutorial/regression or application responsibilities.

## External Effect How-to Evidence

`how-to/handle-external-effects.md` explains honest adapter capability flags,
effect classes, stable effect identities, provider idempotency windows,
reconciliation outcomes, current authority and explicit uncertainty. Its
notification adapter expects an application-owned provider client rather than
claiming Aksara bundles one. The guide calls out recipient validation, command
normalization and domain authorization as application responsibilities.

`scripts/check_public_external_effects.py` extracts the exact adapter/action
helper and runs against the isolated 0.7.0 wheel with PostgreSQL. Thirteen checks
cover internal migrations, acceptance followed by simulated acknowledgement
loss, a replacement Attempt with an advanced fence and identical downstream
key, one simulated provider effect, persisted result, unsafe recovery becoming
`external_outcome_unknown`, no automatic reclaim of that failed Operation,
and current-scope revocation preventing a send. Evidence hashes bind the helper
page and runner; a docs test checks freshness. The disposable schema is removed
and absence verified. This admin-role, simulated-client test does not establish
real-provider delivery/retention, restricted-role RLS or process-loss behavior.
Reconciliation is described from implementation but is not exercised by this
particular public helper gate; existing dedicated regressions remain separate.

## Durable History How-to Evidence

`how-to/inspect-durable-history.md` explains current state versus retained
transitions, default/maximum limits, newest-first order, absent cursor pagination,
JSON projection and separate-read consistency. It explicitly documents that
terminal records remain readable after their action code is unregistered:
authentication and tenant checks remain, while the removed action's scope/custom
policy does not execute. Stricter product access policies require an application
boundary; stored requester provenance does not imply owner-only access.

`scripts/check_public_history.py` runs the exact helper with the isolated public
0.7.0 wheel and PostgreSQL. Thirteen checks cover migrations, initial/cancelled
state, JSON serialization, registered-action scope denial, tenant/non-tenant and
namespace isolation, order, limits and retired terminal-action reads. Page and
runner hashes are bound by `history-execution.json` and a freshness test. The
owned schema is removed and its absence checked. This admin-role service fixture
does not prove HTTP authentication, restricted-role RLS, a retention campaign,
a tamper-resistant audit store or atomic multi-read snapshots.

## Admin Permission and Mount Audit

Reviewed Admin registration, permission, action and mounting guidance against
the corresponding implementation. Corrected the asynchronous related-object permission example,
clarified that form handlers enforce CSRF, qualified process-local rate limiting,
and labeled Studio experimental in the Admin comparison. Installed public-wheel
checks execute the exact permission hook using a controlled async related-object
fixture and verify owner/non-owner/nonstaff/anonymous decisions. They also mount
a custom site on FastAPI and check anonymous redirect, login rendering and the
prefix-scoped CSRF cookie. These checks run in the existing installed import
contract runner. They do not prove database-backed relation loading,
authenticated Admin CRUD, every widget, or tenant/RLS isolation. Those remain
separate reference-application and regression evidence, not implied by a page
render or a hook fixture.

Admin validation at this checkpoint: `.venv/bin/python -m pytest tests/admin -q`
with local PostgreSQL and required database tests enabled passed **142 tests**
(1 dependency deprecation warning). The docs/packaging set passed **160 tests**;
strict MkDocs, installed imports/selected contracts, CLI parsing and rendered
local links passed. These are source regression and public-wheel checks, not
final candidate-wheel validation.

## Important External Reference Validation

`scripts/check_external_doc_links.py --output
 audit-evidence/v071/external-links.json` checks inline Markdown and HTML HTTP
links in the README, docs home, installation, production deployment, roadmap,
runtime compatibility reference and strategic review. All **42 distinct targets
returned successful HTTP responses**, with **0 broken and 0 unverified** results.
The evidence records UTC check time, final redirect targets, source-page hashes
and runner hash. A docs test rejects stale evidence after those inputs change.
Network requests run only when the explicit checker is invoked, not during the
ordinary offline docs tests.

Aksara's hosted documentation URLs are excluded from this network check because
they target the older published site; the rendered candidate checker validates
those paths locally. This check proves reachability at the recorded time, not
page-content truth, fragment anchors, future availability, or every external
link across the documentation corpus. Strategic claim verification and source
citations remain a separate research responsibility.

## Scaffold Editable Packaging Defect

**SCAFFOLD-001 / P1:** a fresh generated project fails at `pip install -e
".[dev]"` with Hatchling's file-selection error. The project name is
`scaffold_probe`, while the generated Python package is `app/`, and the emitted
`pyproject.toml` provides no explicit Hatch wheel file selection. Reproduced in
a fresh Python 3.11 environment using a locally built 0.7.0 development wheel.
`probe_scaffold_editable_install.py` records this negative result in
`scaffold-editable-defect.json`; its nonzero exit is intentional evidence of a
real failure, not a passing installation gate.

The README now installs framework/server/test dependencies directly for the
local development path and explicitly discloses the application packaging
limitation. No generated pyproject, dependency constraint, security setting,
application code or framework runtime was changed. A separately scoped scaffold
packaging patch should establish an intentional application package layout and
verify editable and wheel installation. Full fresh-wheel execution of the
corrected README startup path remains required before candidate readiness.

## Current-Wheel Scaffold Startup Checkpoint

A development wheel built at `f43c198` (still version `0.7.0`, not a release
candidate) is identified by SHA256 in `development-wheel-build.json`. Installed
in an isolated Python 3.11 environment, it generated a project whose exact README
dependency-install command succeeded. Editing only DATABASE_URL in its `.env`
selected a unique schema in local `aksara_test`; `makemigrations --app app.models`
and `migrate` succeeded on the generated stubs. `aksara dev --no-reload` on an
ephemeral port served welcome/docs/Admin login/catalog, while MCP transport and
Studio remained 404. The process stopped and the schema was removed and checked.
Doctor returned **PARTIAL (exit 1)** solely for disabled Studio and no AI provider;
database, registry and migration checks passed. This is not production Doctor
release readiness, interactive dbsetup or reload-watcher validation.

`scaffold-startup.json` records these five checks. Comparing generated output
against the public 0.7.0 wheel verified **18 files**, with **only README changed**.
The comparison normalizes only generated Studio tokens, not executable code,
settings or dependency declarations (`scaffold-wheel-equivalence.json`).

The six-stage progressive tutorial also ran against this development wheel:
**86 test executions**, **28 tests in the final stage**, with required local
PostgreSQL and an ephemeral restricted application role. The separate
`development-wheel-tutorial.json` preserves that current-wheel result without
overwriting historical public-wheel evidence. Its earlier documented limits
remain: no real external provider, full crash campaign or production upgrade
claim. Freshness tests bind these results to templates, guide files and runners.
The SCAFFOLD-001 editable packaging failure remains documented and unfixed.

## Consolidated Truth and Completion Checkpoint

`audit-evidence/v071/public-docs-truth.json` now indexes 40 evidence artifacts
and the objective's 63 named phases. It records each artifact's own result and
scope, source-head metadata where available, and hash; it checks linked page
hashes without treating historical source-suite runs as current candidate
validation. The first run found **0 stale linked page inputs**. This is not a
semantic audit of every claim, nor a pass for all 63 phases.

The assessment remains **NOT READY**. Remaining work is explicitly ordered in
the report: semantic/reference and usability completion audit, current matrix
reconciliation, known-defect disposition, candidate version/changelog,
final candidate packaging and release-profile regression, installed candidate
journeys, release evidence and the final unmerged PR with hosted checks.
The machine-readable index can be regenerated with
`scripts/summarize_public_truth.py --objective <original-goal-file> --output
audit-evidence/v071/public-docs-truth.json`. Its successful exit only means its
linked-page integrity check passed. It never grants release approval.

The strategy's adoption-debt assessment now includes SCAFFOLD-001 alongside the
previously documented boundaries. Important external references were rechecked
after that change: 42 reachable, 0 broken, 0 unverified. No production source or
release behavior changed in this reporting checkpoint.

## Relation Access Corrections and Stronger Admin Evidence

**PT-032 / P1:** the relation guide advertised nonexistent forward M2M
`contains()` and reverse M2M `filter()`, described callable reverse one-to-one
absence incorrectly, used an inaccurate hand-written junction schema and
claimed direct category queries include descendants. Corrected these to actual
manager methods, callable-versus-get absence behavior, migration-generated
junction naming, and direct-category semantics. Clarified standalone reverse
relation finalization and synchronous eager access. The delete example now
requires reloading an object to observe a SET NULL change.

The earlier PT-031 Admin edit introduced an error: it awaited `get_related()`,
and its mock incorrectly made that method asynchronous. That mock did not prove
the installed ORM contract. It has been removed. The example now explicitly
queries `Author.objects.get_or_none(id=obj.author_id)`. The new installed
PostgreSQL gate executes this exact hook against real Author/Post models.
Ten checks prove staff/owner denial paths, nullable absence, stored FK values,
unloaded-access errors, synchronous eager access, eager NULL and reverse-FK
filtering. The first probe omitted standalone `finalize_relations()`; adding
the public setup call resolved the missing reverse descriptor and the guide now
explains it. No runtime change was made to accommodate the example.

`admin-relation-execution.json` binds the two pages and runner; its fixture uses
owned DDL and an admin database role, not migrations, HTTP authentication, RLS
or full M2M execution. Installed shape checks separately confirm which manager
methods exist. This supersedes the earlier synthetic Admin relation-hook claim;
the independently exercised anonymous Admin mount/login check remains valid.

Relation correction validation: **77 passed** across `tests/test_relations.py`,
`tests/test_v038_relations.py`, and `tests/perf/test_select_related.py` with
required local PostgreSQL; **165 docs/packaging tests passed**. Strict MkDocs,
Ruff and rendered links passed. The consolidated report indexes 41 artifacts
with no stale linked page hashes; candidate readiness remains unproven.

## Application Testing Guide Corrections

**PT-033 / P1:** the testing guide promised automatic per-test rollback and
runner setup through a plain `AksaraTestCase`, advertised an absent `test` extra,
and mixed nonexistent factory/fixture/mocking APIs with runnable Python fences.
Replaced the guide with three executable serializer/permission unit tests,
links to the existing PostgreSQL-backed progressive application tests, explicit
lifespan/authentication requirements, and isolation choices appropriate to
same-task transactions versus HTTP requests and worker processes. Removed the
legacy pseudocode instead of retaining it as an apparent application recipe.

The exact standalone pytest file passes **3 tests** outside the checkout using
the installed development wheel. This proves normalization, exclusion of a
server-owned input field, structured validation failure, and the synchronous
permission predicate. It does not prove credential verification or database
isolation; those boundaries are explicitly separated in the guide.

**TESTING-001 / P1, source-confirmed functional limitation:**
`aksara.testing.test_database(cleanup=True)` acquires a raw pool transaction,
yields a `Database` without pinning application queries to that connection, and
does not disconnect the pool in that branch. Consequently its rollback must not
be presented as general ORM/HTTP test isolation. This turn inspected the source;
it did not execute a negative database probe or claim a measured resource leak.
A separate patch should bind supported same-task queries correctly, guarantee
pool teardown, and test failure/cancellation paths. No runtime fix is included.
The plain `AksaraTestCase` setup and header-only `with_user()` limitations are
also stated explicitly; applications should use their own fixtures and actual
authentication adapter rather than assuming these conveniences enforce them.

Testing-guide validation: **166 docs/packaging tests passed** and **21 existing
helper unit tests passed**, each with one upstream AnyIO deprecation warning.
The latter use mocks and do not disprove TESTING-001. Installed syntax/import
checks cover 581 Python fences; CLI parsing covers 335 commands with 0 errors
and 11 explicit exclusions. Strict MkDocs, Ruff and 47,586 rendered local
links/assets passed. The truth index records 43 scoped artifacts with no stale
linked inputs. Release readiness and the final requirement audit remain open.

## Capability Matrix Reconciliation

The matrix above now reflects the scoped evidence available at `9668c08`,
including query/signals, real Admin relations, account/session helpers, CLI
parsing, scaffold startup/equivalence, local AI execution and testing guidance.
Old blanket “pending” entries were replaced only where an artifact proves a
specific slice. Public-release and development wheels are distinguished even
though both currently carry 0.7.0 metadata. Added application testing as the
35th area because its helper limitations affect onboarding directly.

The remaining evidence gaps are still explicit: advanced fields, complete M2M
behavior, bulk methods, authenticated Admin workflows, persisted file/image
lifecycles, enabled Studio workflows, a data-bearing historical application
upgrade, and final candidate-wide regression. Provider quality and experimental
workflow behavior are not promoted into stable guarantees. This reconciliation
is an evidence inventory, not the final requirement-by-requirement audit.

## Bulk Write Contracts and PostgreSQL Type Failure

**PT-034 / P1:** the bulk guide implied all-batches atomicity, fixed query
counts, and normal scalar CASE updates without qualification. It omitted
signal/validation differences, partial-return hydration, database-default
requirements for upsert, and the non-read-only keys-only upsert path. Replaced
it with a complete Ticket helper, explicit transaction ownership, current
method contracts and supported text-update behavior. The expression reference
now explicitly excludes `bulk_update()` from supported F-expression paths.

**BULK-001 / P1, reproduced on the installed public 0.7.0 wheel and PostgreSQL:**
`bulk_update()` generates CASE branches with untyped parameters; ordinary
Boolean and timestamp updates fail with asyncpg `DatatypeMismatchError` mapped
to Aksara `DatabaseError`. PostgreSQL infers the CASE result as text. The first
probe failed while updating `resolved`; separate probes reproduce both
`resolved` and `updated_at`. The guide now states this failure prominently.
The replacement text-only helper does not certify other scalar types. A
separate patch should provide correct typed CASE generation with real database
coverage across the declared field types; no production fix is included here.

The new installed PostgreSQL gate executes the exact bulk helper and records
**16 checks**, including the two expected defect reproductions. It exercises
create/update/upsert results, input validation, returned defaults, no save
signals, ignored-conflict hydration, explicit timestamp behavior, an atomic
helper rolling back its first batch after a later CHECK failure, and an
unwrapped call retaining its first batch. The CHECK failures must unwrap to
actual asyncpg `CheckViolationError`; unrelated exceptions cannot satisfy them.

The evidence marks the Boolean/timestamp runtime contract false even though
the documentation probe passes. The fixture owns a disposable schema and
adds a CHECK solely for failure injection; it is not application migration,
RLS, advanced-field, concurrency or remote-storage proof. Schema removal is
verified. No package, dependency, runtime or security default changed.

Bulk-guide checkpoint validation: the installed query/signal gate was rerun
because the transaction reference changed (**25 checks passed**). The related
`tests/test_manager.py`, `tests/test_v044_features.py`, and
`tests/test_bug_hunt_phase1_fixes.py` set passed **76 tests** with required local
PostgreSQL enabled. Their green result does not cover away BULK-001.
Docs/packaging checks passed **167 tests**, with one upstream AnyIO deprecation
warning. Ruff, strict MkDocs, 578 Python-fence syntax/import checks, 335 literal
CLI parses (11 explicit exclusions), and 47,596 local rendered links/assets
passed. The index records 44 artifacts with no stale linked inputs. Candidate
readiness remains unproven; the production defect needs its own patch scope.

## Custom Field Extension Guide

**PT-035 / P1:** the custom-field page taught nonexistent `from_db()`,
`get_db_type()`, `contribute_to_class()` and Django-style `deconstruct()` hooks,
`self.null`/`null=True`, generic `Field[T]`, and invented encrypted-field
configuration. Several examples could not even instantiate the abstract base
field. Removed these recipes and replaced them with one complete built-in
String subclass and model, using the actual synchronous conversion and async
preparation contracts. The guide distinguishes validation from normalization,
model validation from HTTP input, and SQL representation from custom migration
or serializer support.

The exact field and model execute against the public 0.7.0 wheel and PostgreSQL:
**14 checks** cover conversion, invalid inputs, nullable conversion, autodetected
VARCHAR(24) schema, normalized uniqueness, save/reload, direct update, text bulk
update, bulk create and upsert. The fixture applies the autodetected CreateTable
operation; it does not prove the entire migration CLI/history workflow or HTTP
serializer behavior. The first upsert probe omitted the inherited non-null
`updated_at`; supplying it, as required by the existing upsert contract, fixed
the fixture. This requirement is now explicit in the guide. No runtime change
was made to accommodate the example. The broader built-in field reference audit
remains incomplete.

Custom-field checkpoint validation: **469 tests passed** across docs/packaging
and the four field unit suites (`test_fields`, `test_field_params`,
`test_fields_new`, `test_fields_extended`), with one upstream AnyIO deprecation
warning. The installed probe separately supplies real PostgreSQL evidence.
Ruff, strict MkDocs, 569 Python-fence syntax/import checks, 335 CLI parses
(11 explicit exclusions), and 47,155 local rendered links/assets passed.
The truth index contains 45 artifacts with no stale linked inputs; this remains
a pre-candidate checkpoint.

## Built-in Field Reference Corrections

**PT-036 / P1:** the field reference and filtering example passed unsupported
`precision`/`scale` arguments to `Decimal`; its Vector example supplied three
values to a 384-dimensional declaration; the complete Product module omitted
`SET_NULL` and Category; Enum storage was labeled VARCHAR rather than TEXT.
Corrected these against the installed constructors and conversion behavior.
The complete module now defines its relation target and imports its delete rule.

Also corrected the `ai_description=None` default and String validation order,
qualified URL validation and constructor-option availability, and explained
that declared constraints require migrations. The AI metadata sections now
identify the PolicyEngine boundary instead of implying universal redaction,
encryption or protection from arbitrary ORM code. The illustrative role field
is service-owned. These are example/documentation changes, not runtime defaults.

The installed import gate now executes the exact Product module, checks Decimal
and Enum conversion, validates the Vector literal against its declaration, and
compares documented per-field default tables to installed signatures. It does
not use syntax success as a claim of database persistence, pgvector availability,
HTTP validation or universal AI metadata enforcement. Advanced-field database
and persisted media paths still require their own scoped coverage.

Built-in reference checkpoint validation: **470 docs/packaging and field tests
passed**, with one upstream AnyIO deprecation warning. Installed syntax/import
and selected declaration checks cover 569 Python fences; literal CLI parsing
covers 335 commands with 11 explicit exclusions. Ruff, strict MkDocs and
47,160 rendered local links/assets passed. The truth index has no stale linked
inputs. No production source or package metadata changed.

## Persisted Media Lifecycle Evidence

The exact Asset model from the media guide now runs against the installed public
0.7.0 wheel, PostgreSQL and disposable local storage. **14 checks** cover file
and Pillow image uploads, FieldFile wrappers, byte/size reads, database reload,
image decoding, replacement, explicit nullable clearing, rollback and model
deletion, invalid image rejection, and orphan cleanup. The generated CreateTable
operation is applied directly; this is not a full migration CLI/history campaign.

The guide now explicitly explains that replacing references and deleting models
do not automatically remove stored bytes, rollback can leave uploads behind,
and deleting a wrapper before saving its cleared reference can leave a database
row pointing to a missing object. These are verified external-effect boundaries,
not new production defects or runtime changes. The test deletes its own files
and verifies disposable schema removal. Protected uploads/downloads, RLS, S3,
SMTP and content-safety certification remain outside this probe.

Persisted-media checkpoint validation: **14 installed lifecycle checks**, the
existing **9 local storage/email checks**, **10 related storage/schema/mounting
regressions**, and **170 docs/packaging tests** passed (the latter with one
upstream AnyIO deprecation warning). Ruff, strict MkDocs, 569 Python-fence
syntax/import checks, 335 CLI parses with 11 exclusions, and 47,160 local
rendered links/assets passed. The index records 46 scoped artifacts with no
stale linked inputs. Production code and release behavior remain unchanged.

## Advanced Field Persistence Evidence

All seven Python blocks in the field reference's JSON, Array and Vector sections
now execute against the installed public 0.7.0 wheel and local PostgreSQL with
an existing pgvector extension. The runner applies an autodetected CreateTable
operation immediately after each documented model declaration, supplying the
page's explicit prerequisite of an installed schema. It executes the remaining
statements unchanged, including the JSON nested-key query and Array append/save.

**15 checks** also cover JSON scalar/nested round trips, nonfinite JSON rejection,
Array invalid element shapes/types, Vector reload and invalid dimensions/values,
queryset Vector update, and Vector's explicitly cast CASE update. This does not
contradict BULK-001: the failing Boolean/timestamp branches do not use that cast.
The gate requires pgvector rather than silently skipping it; its installed
version is recorded. It uses an isolated schema before the extension's namespace
in the search path and verifies schema removal afterward.

This is real persistence evidence for the documented examples and selected
negative cases, not all write paths, API serializers, RLS, extension installation
or complete migration history. No documentation or runtime change was needed
to make the seven blocks pass. The capability matrix now links this evidence
instead of describing only the original String/Boolean/UUID slice.

Advanced-field checkpoint validation: **91 related Array/JSON/Vector policy
regressions passed** with required local PostgreSQL enabled; **171 docs/packaging
tests passed** with one upstream AnyIO deprecation warning. Ruff and whitespace
checks passed. Public documentation bytes were unchanged, so the existing strict
docs/link artifacts remain applicable; the evidence index has 47 artifacts and
no stale linked inputs. The known Boolean/timestamp bulk-update defect remains
unfixed and separately reported.

## Migration Reference Corrections and Execution

**PT-037 / P1:** the migration reference used runtime `fields.*` where migration
FieldOp objects are required, supplied nonexistent `model_name=` arguments,
and advertised generic AlterField/RunPython recipes absent from the release.
Replaced it with accurate operation shapes and two complete migration files,
including nullable-add/backfill/NOT NULL/default/index sequencing. Clarified
merge limitations, fake application, reviewed SQL and transactional index limits.

The safety guide now distinguishes pending application preview from database
metadata initialization, verifies checksums only for present applied files with
stored digests, and states that earlier migrations remain committed when a
later one fails. Removed a false blanket assertion that asyncpg executes only
the first statement of a multi-statement string. Replaced a volatile partial-index
predicate example with an immutable one; SQL guard acceptance is not PostgreSQL
index-validity proof.

The two exact public migration files pass **12 installed executor/PostgreSQL
checks**: fresh application, representative existing-row preservation/backfill,
future defaults, catalog nullability, index, checksums, repeat run, injected
failure rollback/tracking, and edited-file rejection. The failing fixture is
explicitly test-owned, and unrelated errors cannot satisfy its named division-by-
zero assertion. This is not the CLI path, bundled internal migrations, a full
historical application upgrade, or concurrent migrator/RLS proof. The gate uses
and removes a disposable schema; no production implementation changed.

Migration-reference checkpoint validation: **455 migration regression tests**
passed with required local PostgreSQL enabled, and **172 docs/packaging tests**
passed with one upstream AnyIO deprecation warning. Ruff, strict MkDocs, 555
Python-fence syntax/import checks, 316 CLI parses (11 explicit exclusions),
and 46,807 local rendered links/assets passed. The evidence index has 48
artifacts with no stale linked inputs. No migration engine, production schema,
package metadata or runtime default changed.

## Generated Filter and Search Reference

**PT-038 / P1:** the filtering reference implied `filterable_fields` alone
restricted generated URL filters and claimed model-aware coercion and relation
search. The router actually uses `get_filter_fields()` independently; its default
includes all model fields. The replacement Ticket ViewSet shares an explicit
allowlist across both entry points. The guide describes heuristic coercion,
unsupported relation search, ignored parameters/order terms and pagination
bounds without inventing uniform invalid-filter status codes.

The exact documented model and ViewSet pass **11 installed HTTP/PostgreSQL
checks** for anonymous denial, boolean filters, direct text search, combined
parameters, ascending/default and descending ordering, router allowlist,
pagination/counts, invalid pagination bounds, ignored ordering and rejection of
a relation search path. The fixture attaches a test identity and owns an admin-
role schema; it does not prove credential validation, RLS, every coercion or
adversarial filter syntax. The schema is removed and verified afterward.
No production filter/default behavior changed to match the documentation.

Filtering-reference checkpoint validation: **93 related filtering/pagination/
ordering regression and fuzz tests passed**, and **173 docs/packaging tests
passed** with one upstream AnyIO deprecation warning. Ruff, strict MkDocs, 552
Python-fence syntax/import checks, 316 CLI parses with 11 exclusions, and 46,761
rendered local links/assets passed. The evidence index records 49 artifacts
with no stale linked inputs. Release readiness is still not established.

## Pagination Integration and Reference Correction

**PT-039 / P1:** the pagination reference claimed universal O(1) cursor cost,
stability under data changes and HTTP response metadata that the generated
router does not preserve. Replaced it with the verified default path, actual
paginator defaults/parsing, ascending-ID cursor restrictions, remaining-row
counts and explicit concurrency/performance limits.

**PAGINATION-001 / P1, reproduced on the installed public 0.7.0 wheel:** the
fixed generated paginated response schema discards `page`, `size`,
`total_pages` and `next_cursor`. Direct ViewSet calls retain those fields; real
HTTP calls lose them and can return null limit/offset. This prevents a normal
generated cursor client from getting its continuation token. A separate patch
should preserve the selected paginator's response contract and OpenAPI shape,
with HTTP-level tests for every built-in paginator. No runtime fix is included.

The new gate records **8 HTTP/direct-call checks**, including the two expected
defect reproductions. Default and explicit limit/offset work; direct ascending-ID
cursor continuation advances and counts remaining rows. The evidence explicitly
marks custom-pagination metadata false while its documentation probe passes.
Synthetic identity and an admin-role disposable schema are test prerequisites,
not credential, RLS, load or changing-dataset certification. The filtering guide
now links the same limitation instead of implying arbitrary metadata survives.

Pagination checkpoint validation: **217 docs/packaging and related pagination/
ordering tests passed**, with one upstream AnyIO deprecation warning. The exact
filtering HTTP gate was rerun (**11 checks**) after its limitation link changed.
Ruff, strict MkDocs, 549 Python-fence syntax/import checks, 316 CLI parses with
11 exclusions, and 46,729 rendered local links/assets passed. The index contains
50 artifacts with no stale linked inputs. PAGINATION-001 remains an explicit
unfixed runtime issue; green unit tests do not establish the missing HTTP metadata.

## Requirement Review Checkpoint

The [requirement review](audit-evidence/v071/requirement-review.md) preserves
all 63 objective phases, requirements outside those headings, named artifacts
and remaining acceptance work. It distinguishes scoped evidence from full
completion. The final per-subitem audit, remaining semantic/usability review and
actual candidate campaign are still open; version remains 0.7.0.

Reconciled current CLI/import counts, migration/filter/pagination/media evidence
and operator-reading status in the report. The strategy now accounts for all
nine functional findings without changing its thesis or authorizing fixes.
Fresh validation: 174 documentation/packaging tests passed with one upstream
AnyIO deprecation warning; 42 important external links were reachable with zero
broken or unverified targets. Ruff and diff whitespace checks passed. The source
AST audit again confines production changes to the scaffold README return text;
dependencies remain unchanged. The evidence index has 50 artifacts and zero
stale linked inputs. No candidate, release or final PR is claimed by this check.

## Generic Relations and Persisted Steps

**PT-040 / P1:** the combined guide implied production-ready resumable workflows
and unconditional concurrent exclusion despite `force=True` bypassing claims.
Its pickle encoder treated `serializer` as a whole-result transform although
the implementation passes it as JSON's fallback encoder. Replaced with exact
model/helper examples and a Decimal-specific codec; documented identity keys,
cached target resolution, dangling references, migration/DDL prerequisites,
force overlap, cancellation and explicit cleanup. No runtime behavior changed.

`scripts/check_public_generic_steps.py` executes all four named Python blocks
from the guide in an isolated installed public 0.7.0 process, with model tables
created through autodetected migration operations in an owned PostgreSQL schema.
It records 23 observations, including actual generic resolution after reload,
cache behavior after target deletion, step reuse/retry/force, a deterministic
concurrent claim, forced overlap without a completion fence, and task cancellation
leaving a running row. The schema is dropped and catalog absence verified.
This uses an admin-role fixture; it does not establish RLS, application
authorization, process-death recovery, or Durable Operation guarantees.

The first runner attempt imported DoesNotExist from the wrong module and failed
before any example executed. Source inspection identified `aksara.manager`; the
runner and public error name now use that installed class. The successful result
is recorded in `audit-evidence/v071/generic-step-execution.json`.

Validation: `pytest tests/docs tests/test_v048_docs_lock.py
 tests/test_v048_packaging_sanity.py -q` passed 175 tests (one upstream AnyIO
warning); required-database `pytest tests/test_generic_foreign_key.py
 tests/test_durable_workflows.py -q` passed 8. Ruff, strict MkDocs, 543 Python
fence/import checks, 316 CLI parses with 11 exclusions, and 46,714 rendered local
link/asset checks passed. The index now contains 51 scoped artifacts with no
stale linked inputs. These are public 0.7.0/checkpoint results, not a candidate
or production workflow certification.

## Locale and Timezone Guide Verification

**PT-041 / P2:** the localization guide used separate incomplete application
fragments, legacy phase language and `TIME_ZONE` without distinguishing the
actual setting from the timezone middleware's independent UTC default. Replaced
with one complete no-database request example and an exact standalone field
conversion example. Clarified explicit middleware installation, valid default
configuration, lazy translation/catalog ownership, context reset, storage versus
output conversion and application ownership of scheduling preferences.

`tests/docs/test_localization_reference.py` executes both named guide blocks.
The installed import runner now executes this contract in its isolated public
0.7.0 process: real ASGI requests select French/New York, then default English/UTC,
and an unsupported locale/unknown zone falls back. The exact conversion example
normalizes the specified New York local time to UTC and resets its context.
Evidence is included in `installed-doc-imports.json`, with the localization
contract hash checked by the evidence-integrity suite. This does not exercise
PostgreSQL persistence, real translation catalogs, daylight-saving business
policy or malformed-header conformance. No production changes were made.

Validation: `pytest tests/docs tests/test_v048_docs_lock.py
 tests/test_v048_packaging_sanity.py tests/test_i18n.py
 tests/middleware/test_locale.py tests/middleware/test_timezone.py -q` passed
189 tests with one upstream AnyIO warning. Ruff and strict MkDocs passed;
540 Python fences/imports, 316 CLI parses (11 exclusions), and 46,719 rendered
local links/assets passed. The 51-artifact index has zero stale linked inputs.

## Exception Reference and HTTP Error Contracts

**PT-042 / P1:** the exception reference claimed one universal hierarchy,
listed nonexistent DRF-style and migration classes, imported lookup exceptions
from the wrong module, assigned status 400 and `detail` to ORM ValidationError,
and awaited synchronous serializer validation. Its generic response examples
also concealed the distinct ORM and HTTP error envelopes. Replaced with actual
classes, constructor fields, mapper limits and registered HTTP handlers. The
AI-debug page's duplicate invalid lookup example now points to this reference.

`tests/docs/test_exception_reference.py` checks the documented hierarchy and
executes the exact five-route application example, plus direct registered
handler/schema and HTML-negotiation observations. The installed import runner
executes these checks against public 0.7.0 outside checkout. It verifies 404,
409, 422, explicit 403, a 500 multiple-match response, custom fixed-message
handling and distinct request-validation JSON. The CHECK mapper check constructs
a driver exception without executing SQL; real database CHECK behavior is
separately recorded by the existing bulk gate. No production change or new
functional defect is claimed by correcting the documentation.

Validation: `pytest tests/docs tests/test_v048_docs_lock.py
 tests/test_v048_packaging_sanity.py tests/test_v02_features.py::TestExceptions
 tests/test_debug_error_pages.py -q` passed 247 tests with one upstream AnyIO
warning. Ruff, strict MkDocs, 531 Python fence/import checks, 316 CLI parses
(11 exclusions), and 46,483 rendered local links/assets passed. The evidence
index retains 51 artifacts with no stale linked inputs. Final candidate gates
remain open.

## Debug Error Page Security Guidance

**PT-043 / P0:** the debug guide claimed that unsupported `debug_allowed_ips`
restricted pages to staff/local clients and that `debug_hide_vars` provided
configurable masking. It also advertised nonexistent template, local-variable
and expression-evaluation controls. These instructions could encourage exposing
debug HTML under a false access-control assumption. Replaced them with actual
constructor behavior, fixed-header masking limits and explicit HTML/JSON
response boundaries. This is a documentation correction, not a new security
feature or runtime fix.

The exact no-database factory now runs in the installed public 0.7.0 contract
gate. Eight ASGI requests cross debug on/off, loopback/non-loopback client
addresses and HTML/JSON Accept headers. Debug HTML includes the deliberate
exception marker for both addresses; JSON adds debug detail only for loopback
in debug mode. Production-mode responses omit that marker. This establishes
the documented presentation boundary, not exhaustive redaction, proxy safety,
authorization or provider behavior.

Validation: the documentation/packaging selection plus
`tests/test_v02_features.py::TestExceptions` and `tests/test_debug_error_pages.py`
passed 248 tests with one upstream AnyIO warning. Ruff, strict MkDocs, 521
Python fence/import checks, 316 CLI parses (11 exclusions), and 46,313 rendered
local links/assets passed. The 51-artifact index has zero stale linked inputs.
The candidate/version/full final release campaign remains open.

## Debugging Overview Follow-through

The overview now follows PT-043's verified error-page boundary: removed the
unsupported frame-local inspector, `/__debug__/` inspector, `debug_print` and
`query_profiler` recipes, and the unverified `DATABASE_ECHO` configuration.
It directs readers by diagnostic task and distinguishes explicit query tracing
configuration from the debug constructor flag. The detailed query-profiling
page still requires its own semantic review; this edit does not certify it.

Validation: installed-package syntax/import checks passed for 515 Python fences;
316 CLI forms parsed with zero errors and 11 exclusions. Strict MkDocs passed;
162 rendered pages and 46,248 local links/assets validated. An initial test run
started before rendered evidence regeneration and correctly rejected its stale
page hash; the sequential rerun after regeneration passed all 179 documentation
and packaging tests (one upstream AnyIO deprecation warning). No Python or
runtime source changed in this checkpoint.

## Query Profiling and AI Advisor Public Contracts

**PT-044 / P1:** the profiling guide described automatic debug-mode profiling,
nonexistent `aksara.debug` helpers and `aksara.testing.QueryCounter`, automatic
EXPLAIN output, and invalid forward-relation access. Replaced those recipes with
an exact standalone read-only script and an explicit request middleware factory.
The guide separates process-global query capture from context-based tracing,
explains positive count limits and timing scope, and states that raw driver calls
bypass instrumentation. It documents unredacted parameters, bounded per-process
history, and client-controlled correlation IDs without presenting these as
production observability or authorization guarantees.

`query-profiling-execution.json` records 19 observations against the installed
public 0.7.0 wheel and PostgreSQL with `default_transaction_read_only=on`.
The standalone script is also executed as a file. Coverage includes exact query
results/counts, capture events without timing, trace timing/parameters, absent
row-count population, identified/anonymous retention, disabled tracing,
snapshotted cap/threshold, raw-driver bypass, actual failed SQL recording,
nested/global capture behavior, HTTP correlation and ID replacement, explicit
EXPLAIN, and clearing history. No database objects are created; no N+1 benchmark,
streaming/cancellation guarantee or Studio execution is claimed.

**PT-045 / P0:** the AI Debug guide described automatic provider analysis and
unsupported `debug_ai_privacy`/provider constructor settings, alongside a claim
that credentials and request bodies could not be shared. Replaced it with the
actual rule-based local advisor, separate constructor/global debug controls,
`Settings.ai_debug_enabled`, and explicit context disclosure limits. This fixes
a false privacy/configuration promise; it does not add a runtime privacy feature.

The exact advisor factory now executes in the installed-wheel contract runner.
Six HTTP requests cover advisor enabled, disabled and global-debug-disabled
states with HTML/JSON responses. Socket connection attempts are blocked during
the example/context test. A direct context-builder check confirms masked
Authorization and preserved deliberate query/body/exception markers, with no
populated local-variable previews. This verifies the default local path, not
provider integration, comprehensive redaction or production access controls.

Validation commands:

- `.venv/bin/python scripts/check_public_query_profiling.py --python /tmp/aksara-v071-public-baseline/bin/python --output audit-evidence/v071/query-profiling-execution.json` with the local test database supplied privately: 19 checks and standalone script passed.
- `.venv/bin/python scripts/check_installed_doc_imports.py --python /tmp/aksara-v071-public-baseline/bin/python --output audit-evidence/v071/installed-doc-imports.json`: 502 Python fences/imports plus selected contracts passed.
- `.venv/bin/python scripts/check_public_cli_docs.py --python /tmp/aksara-v071-public-baseline/bin/python --output audit-evidence/v071/cli-docs-syntax.json`: 316 parses, zero errors, 11 exclusions.
- `/Users/nagarjunatella/miniconda3/bin/mkdocs build --strict -f docs/mkdocs.yml -d /tmp/aksara-v071-profiling-site`: passed.
- `.venv/bin/python scripts/check_rendered_docs_links.py --site /tmp/aksara-v071-profiling-site --base-url https://nagarjuna-tella.github.io/Aksara/ --output audit-evidence/v071/rendered-links.json`: 162 pages, 45,819 local links/assets, zero errors.
- `.venv/bin/python -m pytest tests/docs tests/test_v048_docs_lock.py tests/test_v048_packaging_sanity.py tests/db/test_tracing.py tests/ai/test_ai_debug.py -q`: 242 passed, one upstream AnyIO deprecation warning.
- Ruff on the five changed/new Python files: passed.

The debugging section's four pages now have source-backed public treatment and
selected installed execution evidence. This does not complete the remaining
site-wide semantic/usability audit, candidate versioning, final regression
campaign, or release PR. No production source or database schema changed.

## Domain Patterns and Template Setup

**PT-046 / P0:** the pattern/selection pages presented historical examples as
complete protected applications and the multitenant template as an isolation
foundation. They also mixed the basic scaffold with flat domain copies,
listed nonexistent CRM Pipeline/Stage models, advertised PUT updates, and
prescribed `pip install -e` and `app.models` for copies without that package
layout or build metadata. The five pattern/selection pages now distinguish the
canonical protected tutorial from domain demonstrations and historical code.
Duplicated, inaccurate model/action sketches were replaced with the actual
example inventory, checked setup commands, links to the validated contracts,
and explicit authentication/custom-action/tenant limitations.

The generic tree and next steps printed by `startproject` still do not describe
the domain copies correctly; this is remaining CLI instructional debt. The
pattern pages explicitly direct users to the correct flat-module commands. No
CLI callback or generation logic was altered by this correction.

`scripts/check_domain_template_docs.py` runs the exact page command blocks
against an installed public 0.7.0 wheel outside the checkout. It executes template
listing, generation, migration generation/application and the local server;
substitutes only an ephemeral port; and executes the documented curl checks.
All three copies serve health/OpenAPI and register PATCH updates. Blog/CRM
valid anonymous creates return 403. The initial blog probe omitted required
content and correctly returned 422; supplying a valid request tests the intended
permission boundary. This is not positive CRUD or custom-action certification.
All three owned PostgreSQL schemas and server processes are cleaned up.

### MIGRATION-001 / P1 — discovery silently replaces an application model

The installed multitenant template declares `models.User` with table
`tenant_users`. Before discovery, that class occupies the `User` registry entry.
`discover_models('models')` then imports configured built-ins; the entry becomes
`aksara.contrib.auth.models.User` with table `aksara_users`. The registry is keyed
by Python class name, not module or table name. Both migration CLI commands exit
zero, but the resulting schema lacks `tenant_users`.

`domain-template-execution.json` records the before/after class identities,
actual PostgreSQL table list, `missing_declared_tables: ["tenant_users"]`,
`template_schema_complete: false`, and `all_template_schemas_complete: false`.
The gate's pass means these observations reproduced; it does not mean that the
multitenant schema is complete. The existing example startup gate had never
claimed per-model schema completeness and did not expose this omission.

The model guide, historical pattern page and example README now describe the
limitation. Recommend a separate reviewed model-discovery/migration fix with
same-name and import-order coverage that prevents silent model omission.
Do not change registry semantics in v0.7.1. Choosing distinct application model
names avoids this particular collision; it is not a general migration or
isolation guarantee. The strategic review and machine-readable defect index now
track ten functional findings without changing the roadmap thesis.

### Validation

- `.venv/bin/python scripts/check_domain_template_docs.py --python /tmp/aksara-v071-public-baseline/bin/python --output audit-evidence/v071/domain-template-execution.json`: three generated-template observations verified, with the multitenant schema failure explicitly retained.
- `.venv/bin/python scripts/audit_public_examples.py --python /tmp/aksara-v071-public-baseline/bin/python --output audit-evidence/v071/example-execution.json`: five application startups, 12 selected GETs returning 200, six generated-create attempts returning 403; no provider calls. Local test database supplied privately to both runners.
- `.venv/bin/python -m pytest tests/docs tests/test_v048_docs_lock.py tests/test_v048_packaging_sanity.py tests/patterns/test_startproject_templates.py -q`: 202 passed, three upstream deprecation warnings.
- `.venv/bin/python -m pytest tests/cli/test_migrations_cli.py tests/cli/test_models_cli.py tests/migrations/test_autodetector.py -q` with required local database configuration: 43 passed. These regressions do not negate MIGRATION-001.
- Installed doc checks: 463 Python fences/imports; 309 CLI forms parsed, zero errors and 11 exclusions.
- Strict MkDocs passed; 162 rendered pages and 44,576 local links/assets validated. All 42 selected important external links reachable.
- Ruff passed for the new runner/test and updated evidence indexer. No production source, migration semantics, or example runtime code changed.

The remaining whole-site semantic/usability review, final requirement audit,
CLI instructional debt, actual candidate build and release campaign remain open.


## CLI and generated README guidance follow-up

The CLI instructional debt recorded above is now addressed. `startproject`
help and existing output strings distinguish the basic package layout from
flat domain copies, remove the broken editable-install suggestion, and direct
users to the checked template-specific setup guide. Template descriptions no
longer promise a complete protected application. This changes instructional
strings only; options, callbacks, generation, defaults and dependencies remain
unchanged.

The three domain READMEs previously described repository module paths. Copying
those instructions could produce `--app app.models` despite a flat generated
`models.py`. Blog, CRM and multitenant READMEs now separate repository-to-copy
steps from the generated directory startup flow and use `--app models --output
migrations`. The generated README startup blocks match the checked public
pattern commands. Authentication limitations and EX-001/MIGRATION-001 remain
explicit; the historical tenant template remains unsuitable as an isolation
reference.

A rebuilt development wheel (still version 0.7.0, not a candidate) was compared
with the public 0.7.0 wheel outside the checkout. All four templates were
generated: 51 files in total, with only README.md differing in each template.
The comparison normalizes only generated Studio token values. Executable
files, settings and file inventories match. The basic documented startup
passed five checks. All three domain README command sequences were executed
against local PostgreSQL; the known missing tenant_users table is still
recorded as a negative result, not interpreted as schema success.

Validation and evidence:

- `scripts/check_startproject_guidance.py --baseline-python /tmp/aksara-v071-public-baseline/bin/python --development-python /tmp/aksara-v071-cli-help-env/bin/python --output audit-evidence/v071/startproject-guidance.json`: four templates, 51 files, README-only differences.
- `scripts/check_domain_template_docs.py --python /tmp/aksara-v071-cli-help-env/bin/python --require-updated-readme --output audit-evidence/v071/cli-help-domain-template-execution.json`: three observed startup flows; all generated README command blocks verified, known tenant schema omission retained.
- `scripts/check_scaffold_startup.py --python /tmp/aksara-v071-cli-help-env/bin/python --output audit-evidence/v071/cli-help-scaffold-startup.json`: five checks passed. Runners used privately supplied local test database configuration and removed their schemas/processes.
- `.venv/bin/python -m pytest tests/docs tests/test_v048_docs_lock.py tests/test_v048_packaging_sanity.py tests/patterns/test_startproject_templates.py tests/dx/test_startproject_scaffold.py tests/dx/test_scaffold_importable.py -q`: 287 passed, three upstream deprecation warnings.
- Ruff passed on the three affected runners and two new test files. Negative controls verify that the AST scope guard rejects executable CLI argument/call changes and template source/name changes.
- `scripts/check_v071_runtime_scope.py`: production AST unchanged outside the scaffold README return, startproject help/output string literals and four template descriptions. These are the three production-source files changed from v0.7.0; no functional runtime change is claimed.
- Installed checks: 463 Python fences/imports and 312 CLI forms, zero CLI errors, 11 explicit exclusions. Strict MkDocs passed; rendered-link validation covers 162 pages and 44,576 local links/assets.
- Python 3.11.5 static ratchet with Ruff 0.16.6 and mypy 2.3.1 passed: Ruff 7,207/7,218 and mypy 495/501. The Python 3.14 run has an existing category excess (20 index errors against 19 allowed). A before/after comparison reports identical 497 mypy errors and categories, proving no new debt from these changes; it does not turn that Python 3.14 ratchet failure into a pass. No accepted baseline was edited. See cli-help-static-comparison.json and cli-help-static-ratchet.json.

The build artifact records the wheel and all six instructional input hashes.
These checks close this CLI/README gap; whole-site semantic/usability review,
final requirement acceptance and actual candidate release gates remain open.


## Entry-hub usability review — PT-047 / P1

Reviewed getting-started/index.md, tutorials/index.md, cli/index.md,
advanced/index.md and reference/index.md for entry tasks, jargon, duplication,
copyable examples and links to prerequisites. The first three already provide
clear tutorial/workflow routes and explicit optional-AI boundaries. The latter
two retained misleading duplicated examples despite corrected destination pages.

The Advanced hub advertised a decorator-style signal example with an undefined
slugify, a custom field skeleton and several nonexistent legacy APIs. Merely
labeling the latter pseudocode still left the section teaching unsupported
approaches. It now groups actual guides by work/recovery, data behavior and
measurement. Ordinary tasks, durable Operations and evolving persisted steps
have distinct descriptions. Caching is explicitly application-owned.

The Reference hub claimed completeness for every class and option while
repeating partial model/ViewSet code and context-free migration commands. It
now supplies a concise lookup table, directs installation to the complete
first-project or template flow, distinguishes declarations from command effects,
and uses the installed version command rather than a hard-coded version claim.
No underlying API, example implementation or navigation destination was changed.

Installed documentation validation now checks 457 Python fences and 308 CLI
forms (zero errors, 11 exclusions). Strict MkDocs passed and 162 rendered pages
contain 44,452 checked local links/assets, with zero errors. The first focused
test run raced the link-artifact refresh and reported one stale-hash assertion;
the completed rerun of `.venv/bin/python -m pytest tests/docs tests/test_v048_docs_lock.py -q` passed all 150 tests with one upstream deprecation warning. This five-page review is scoped
progress toward C6, not a whole-manual usability certification.

## Middleware contract and tenant-trust review

Five pages were checked against the middleware classes, application registration,
Principal resolution and security diagnostic implementation. Their scoped
semantic dispositions and current page/source hashes are recorded in
`audit-evidence/v071/middleware-page-review.json`.

### PT-048 / P1 — middleware options and logging behavior overstated

The overview used an unread legacy settings dictionary and a nonexistent
`aksara.middleware.BaseMiddleware`. It conflated list registration order with
successive `add_middleware` calls. Request-ID documentation promised generators
and validators that the constructor does not accept. Nonempty client IDs are
actually preserved, not checked for UUID validity. The old logging reference
invented masking, exclusions, body capture, custom logger/status options and
other constructor parameters. `log_body` is reserved, and `log_json=True` passes
a dictionary to Python logging; a normal formatter does not guarantee JSON.

The four middleware pages now describe actual signatures, context lifetime,
ordering and operational limits. Four complete HTTP examples replace the
incomplete CRUD/legacy examples. The logging sample supplies a real JSON
formatter and teaches the existing record fields. It does not claim redaction,
stream transmission timing or durable audit evidence.

### PT-049 / P0 — tenant extraction represented as trusted isolation

The tenant guide promised custom resolution, required/default tenant and
exclusion options absent from the constructor, automatic query scoping and
schema/database routing. Its schema example interpolated request data into
search_path and set a connection-local value on a separately acquired
connection. The security overview incorrectly described the extracting
middleware as a server-side membership resolver. The implementation extracts a
header/subdomain and permits a missing value; membership is application-owned.

A negative integration control confirms that a legacy user adapter can consume
an unverified extracted value through `request.state.tenant_id`. Principal
resolution not reading raw headers directly is therefore insufficient to make
that stack safe. Documentation now requires validated membership before trusted
state and database context are established. The executable Ticket Desk tenant
chapter remains the recommended protected path. The generic middleware demo
only echoes context and accesses no tenant records.

The security page also clarifies that AKSARA_MULTI_TENANT and AKSARA_RLS_ENABLED
are posture declarations read by diagnostics. They do not install database
policies, change roles or prove RLS enforcement. Actual migrations, restricted
roles and database tests remain required. This review changes documentation,
not the extraction/Principal/diagnostic contracts, and does not claim a new
functional fix or silently add a runtime guarantee.

### Verification

- `.venv/bin/python scripts/check_installed_doc_imports.py --python /tmp/aksara-v071-public-baseline/bin/python --output audit-evidence/v071/installed-doc-imports.json`: passed 405 Python fence/import checks plus the selected behavior contracts. The new middleware contract executes 24 in-process HTTP requests against the installed public wheel: timing, request-ID reuse/generation/error behavior, tenant absence/whitespace/host precedence, unverified legacy state, logging fields/levels/JSON, ignored body capture and disabled logging. It checks context reset in the same async caller, including an exception; no database or external service is used.
- `.venv/bin/python -m pytest tests/docs tests/test_v048_docs_lock.py tests/middleware/test_logging.py tests/middleware/test_request_id.py tests/middleware/test_tenant.py tests/security/test_tenant_isolation.py -q`: 199 passed, one upstream deprecation warning.
- `.venv/bin/ruff check tests/docs/test_middleware_reference.py scripts/check_installed_doc_imports.py`: passed.
- `.venv/bin/python scripts/check_public_cli_docs.py --python /tmp/aksara-v071-public-baseline/bin/python --output audit-evidence/v071/cli-docs-syntax.json`: 308 forms parsed, zero errors, 11 exclusions.
- `/Users/nagarjunatella/miniconda3/bin/mkdocs build --strict -f docs/mkdocs.yml -d /tmp/aksara-v071-middleware-site`: passed.
- `.venv/bin/python scripts/check_rendered_docs_links.py --site /tmp/aksara-v071-middleware-site --base-url https://nagarjuna-tella.github.io/Aksara/ --output audit-evidence/v071/rendered-links.json`: 162 pages, 43,514 local links/assets, zero errors.

An initial test-helper call incorrectly passed request content to HTTPX's `get`
shortcut; using its general `request` method fixed the test harness before the
successful installed and focused runs. No production source changed in this
review. Whole-site semantic/readability acceptance and candidate gates remain
open; this five-page slice does not stand in for them.

## Installation, layout and database setup review

Reviewed installation.md, project-layout.md, database-setup.md,
running-your-app.md and reference/runtime-compatibility.md against package
metadata, the CLI, scaffold generators, settings precedence and Database
construction/lifecycle. The installed setup gate records current hashes for
all five pages in setup-doc-execution.json.

### PT-050 / P1 — starter instructions diverged from generated files

Installation troubleshooting used `pip show/uninstall aksara` rather than the
actual distribution `aksara-framework`. The source clone and subsequent `cd`
used different case, extras were unquoted, and optional development/runtime
package roles were mixed. The corrected guide uses a virtual environment, the
actual distribution, quoted extras and an explicit source directory. It points
to one configuration reference and the full Ticket Desk tutorial.

The layout guide omitted generated files, supplied unrelated replacement
entry/settings code and invalid manual migration constructors, and claimed
`startapp` created urls.py and a route-registration function. The installed CLI
now verifies the exact trees parsed from the page: 18 basic files and five new
application files, with no settings or route edits. The guide explains stubs,
explicit registration, tests and the separate flat-domain layouts without
inventing another application tutorial.

`startapp` itself still prints legacy AksaraSettings/apps instructions. This is
remaining CLI instructional debt, explicitly identified in the page and A18
checkpoint. Its text must be corrected within the help-only scope before
candidate acceptance; generation/runtime semantics need not change.

### PT-051 / P1 — database and startup examples overstated behavior

The database guide passed unsupported pool_min_size/pool_max_size keywords to
Database, presented additional Database instances as transparent replicas,
suggested automatic environment-file variants and showed a health handler that
returned raw database errors with HTTP 200. Fixed traffic-based pool sizing and
libpq-style parameter assumptions were not a supported performance/driver
contract. The replacement identifies all three pool interfaces and the
singleton/lifecycle boundary, provides a read-only standalone connectivity
probe and links real migrations/RLS/role separation to their canonical guides.

The interactive helper was executed against the existing local aksara_test
database. It connected through postgres, retained the existing database and
wrote only a temporary .env. The exact documented probe then loaded that file,
ran SELECT 1 and closed its pool. A separate process verified that
AKSARA_DATABASE_URL overrides DATABASE_URL and the file value. No application
table, role or migration was created by this setup gate.

The running guide distinguishes development surfaces from readiness, describes
the generated health endpoint's actual limitations, separates migration-role
and application-role commands and avoids promising cleanup after forced process
loss. The compatibility page now names the v0.7 line and current contract while
preserving the already tested Python/web boundaries.

### Validation

- `.venv/bin/python scripts/check_setup_docs.py --python /tmp/aksara-v071-public-baseline/bin/python --output audit-evidence/v071/setup-doc-execution.json`, with the local database supplied privately: five checks passed. This is an installed public 0.7.0 environment; no framework imports from the checkout. It verifies CLI/file/database paths, not OS installation, new database creation, source editable installation or production RLS.
- The reused baseline environment initially lacked pip. Standard-library `ensurepip` supplied it, after which the documented package inspection succeeded. This environment preparation did not change Aksara or its runtime dependencies.
- `.venv/bin/python -m pytest tests/docs tests/test_v048_docs_lock.py tests/test_v048_packaging_sanity.py tests/cli/test_dbsetup.py tests/dx/test_startapp_scaffold.py tests/dx/test_scaffold_importable.py -q`: 283 passed, one upstream deprecation warning. The first run correctly rejected stale external-link hashes; the final run passed after regeneration.
- Ruff passed for check_setup_docs.py, check_external_doc_links.py and test_setup_evidence.py.
- Installed documentation checks: 388 Python fences/imports plus selected behavior contracts; 302 CLI forms, zero errors and 11 exclusions.
- Strict MkDocs passed. Rendered validation checked 162 pages and 43,023 local links/assets with zero errors.
- The selected external-link gate was expanded to database-setup.md and regenerated: all 42 targets reachable. The official PostgreSQL download page was inspected directly for the platform-installer link; no untested OS installer commands are presented as local execution evidence.

No production source, migration or runtime defaults changed in this review.
Whole-site review, the identified startapp help correction, final subitem
acceptance and actual candidate release gates remain required.


## startapp instructional correction — PT-050 follow-up

The remaining startapp help/output issue identified above is now corrected.
The command describes the actual five-file module, explains that settings and
routes are not automatically edited, points to INSTALLED_APPS and the existing
configure(installed_apps=INSTALLED_APPS) handoff in a basic project, and requires
explicit route registration and migration review. The public layout page now
identifies AksaraSettings suggestions as older-version guidance.

Only the command's docstring and string literals in existing click.echo calls
changed. The runtime-scope guard now recognizes these specific instructional
locations in addition to the previous startproject/README/template-description
locations. Negative controls reject generator argument changes, added calls and
executable help expressions for both commands. All validation branches, options,
return behavior and generator calls remain identical to released source.

A rebuilt development wheel, still 0.7.0, was installed without dependency
changes. The normal guidance comparison now covers five startapp files as well
as all four project templates. startapp files match the public wheel byte for
byte. Invalid-name and existing-directory invocations retain their original
exit behavior and leave files unchanged. The four project templates continue
to differ only in README.md after generated-token normalization. No generation
behavior was changed to make a help claim true.

The installed setup, basic startup and three domain-template observations were
repeated using that development wheel. The setup helper retained aksara_test;
its temporary .env was removed. Startup runners removed their own schemas and
server processes. The historical multitenant schema still omits tenant_users,
and the negative evidence remains explicit. These are development-wheel checks,
not final candidate certification.

Validation:

- `.venv/bin/python scripts/check_startproject_guidance.py --baseline-python /tmp/aksara-v071-public-baseline/bin/python --development-python /tmp/aksara-v071-cli-help-env/bin/python --output audit-evidence/v071/startproject-guidance.json`: four project comparisons plus five-file startapp/help/error-path comparison passed.
- `check_setup_docs.py`, `check_scaffold_startup.py` and `check_domain_template_docs.py --require-updated-readme`, each using `--python /tmp/aksara-v071-cli-help-env/bin/python`: five setup checks, five basic startup checks and three scoped domain observations passed. Database credentials supplied privately; no candidate or production readiness inferred.
- `.venv/bin/python -m pytest tests/docs tests/test_v048_docs_lock.py tests/test_v048_packaging_sanity.py tests/cli/test_dbsetup.py tests/dx/test_startapp_scaffold.py tests/dx/test_startproject_scaffold.py tests/dx/test_scaffold_importable.py tests/patterns/test_startproject_templates.py -q`: 331 passed, three upstream deprecation warnings. The old test assertion requiring settings.apps was updated to the current configuration instructions.
- Ruff passed on changed documentation tooling and scope/evidence tests. The pinned Python 3.11 static ratchet passed at Ruff 7,207/7,218 and mypy 495/501. Python 3.14 still reports identical before/after 497 mypy errors, including the existing index category excess (20/19); no accepted baseline was changed and that interpreter's ratchet is not reported as passing.
- Runtime-scope AST check passed; package dependencies unchanged. Wheel metadata records current source hashes and precommit build provenance.
- Installed public-doc checks: 388 Python fences/imports and selected behavior contracts; 302 CLI forms, zero errors and 11 exclusions. Strict docs passed; 162 pages and 43,023 local links/assets passed.

This closes the identified startapp help debt. Whole-site semantic/usability
review, final requirement acceptance and release-candidate gates remain open.

## Soft-delete reference follow-up (2026-09-11)

PT052 / P1: `orm/soft-deletes.md` previously instructed inheritance from the
mixin alone and awaited a queryset before calling an instance method; that queryset is not directly awaitable. The guide now uses `(SoftDeleteModel, Model)`, UUID lookup,
`first()` with a missing-row check, and manager visibility modes before filters.
It explicitly distinguishes instance soft deletion from queryset SQL deletion.

SOFTDELETE001 / P1 — separate runtime patch recommended: module-level
`with_deleted(existing_queryset)` and `only_deleted(existing_queryset)` discard
existing restrictions by constructing a fresh manager queryset. Source inspection
and `tests/docs/test_soft_delete_reference.py` reproduce loss of the title
predicate in compiled SQL. The same mechanism can discard application tenant
predicates; this is not a demonstrated RLS bypass. Use manager visibility modes
before applying restrictions. No production fix is included.

Focused checkout validation: `python -m pytest
tests/docs/test_soft_delete_reference.py tests/test_soft_delete.py -q` — 4 passed.
The new test executes the guide's exact model and query-builder fences and retains
an explicit negative control. It does not execute the delete/restore function
against PostgreSQL. The installed-wheel PostgreSQL runner now executes deletion/restoration, all three
visibility modes, both helper filter-loss negative controls, physical queryset
deletion, and unsaved-instance rejection: 10 checks passed. Evidence is in
`audit-evidence/v071/soft-delete-execution.json`; its disposable schema was removed.
Broader validation: `.venv/bin/python -m pytest tests/docs
tests/test_v048_docs_lock.py tests/test_v048_packaging_sanity.py
tests/test_soft_delete.py -q` — 197 passed, one existing dependency deprecation
warning. Strict docs, 43,016 local link/asset references across 162 pages,
42 selected external URLs, 386 Python fences/imports, and 302 CLI command forms
passed. Ruff passed for the added runner/test and evidence indexer. This closes
the scoped reference correction; whole-manual acceptance remains open.

## Fixture reference follow-up (2026-09-11)

PT053 / P1: the fixture guide incorrectly promised backups, missing-primary-key
inserts, and lenient error logging. It now distinguishes development seeding,
existing-row updates, explicit-model export, and transaction ownership.

Three separate P1 runtime defects were reproduced against the installed 0.7.0
wheel and local PostgreSQL using an owned disposable schema:

- FIXTURE001: JSON export retains primary keys, but load rejects missing keys
  instead of restoring exported rows into an empty table.
- FIXTURE002: single-model YAML export emits UUID tags rejected by its safe loader.
- FIXTURE003: default `dump_database()` iterates registry names as model classes.

Recommend separately scoped patches, with explicit import/identity contracts and
safe serialization tests. No functional changes are included. Nine API-level
observations passed, including existing-key updates, omitted-key inserts,
explicit-model exports, strict-mode partial writes, and mapping fallback.
`audit-evidence/v071/fixture-execution.json` records these observations and schema
cleanup. The final runner additionally executes the exact guide seed/export helpers,
proves outer atomic rollback, and checks malformed JSON under both strict modes:
13 installed-wheel PostgreSQL observations passed. `.venv/bin/python -m pytest
tests/docs tests/test_v048_docs_lock.py tests/test_v048_packaging_sanity.py -q`
passed 195 tests with one existing dependency deprecation warning. Strict docs,
384 Python fences/imports, 302 CLI forms, 43,002 local references across 162 pages,
and 42 selected external URLs passed. Ruff passed for the new runner/test and
indexer. This is scoped fixture validation, not final candidate acceptance.

## Model metadata reference follow-up (2026-09-11)

PT054 / P1: `orm/model-meta.md` described a nonexistent `_meta` interface,
FieldInfo abstractions, unsupported nested Meta options, and incomplete schema
and form generators. It now documents `Model.meta`, concrete field objects,
forward relation dictionaries, missing-field behavior, declared versus database
state, and safe metadata handling. The database-free inspection example passes
against both the checkout and isolated installed wheel. The installed import gate
now executes this exact example. No runtime change or new functional defect is
claimed; this is correction of unsupported documentation promises.

Metadata validation: `.venv/bin/python -m pytest tests/docs
tests/test_v048_docs_lock.py tests/test_v048_packaging_sanity.py -q` — 196 passed,
one existing dependency deprecation warning. Strict docs, 367 Python fences/imports,
302 CLI command forms, and 42,623 local references across 162 pages passed.
Ruff passed for the changed runner and new test. Whole-manual review remains open.

## Current page inventory reconciliation (2026-09-11)

The historical 157-page baseline remains unchanged. A new current census,
`public-page-review-inventory.json`, records 163 README/manual Markdown pages,
38 unchanged since v0.7.0 and 46 with matching scoped evidence candidates.
Those counts are navigation for the remaining audit, not acceptance claims:
changed files can still contain errors and an artifact may cover only one example.
All entries retain an explicit semantic-review requirement. The next review
queue starts with inspector model/query/overview pages, including query-plan
fallback and execution claims. No new product behavior is introduced.

## Inspector reference follow-up (2026-09-11)

PT055 / P1: inspector pages blurred declared model constraints with catalog
verification and presented synthetic costs alongside live-plan claims. The three
pages now distinguish process traces, declaration inference, and measured plans;
examples use defined models and avoid unverified Studio/UI and agent pipelines.

INSPECTOR001 / P1: with no database, `explain_query(..., analyze=True)` produces
synthetic output labeled EXPLAIN ANALYZE without a synthetic warning. The focused
negative control uses deliberately invalid SQL and proves identical synthetic
plan lines with and without analyze, while only the latter loses its warning.
Recommend a separate patch exposing provenance and database errors explicitly.
No production fix is included. Two focused tests pass in the checkout and
installed wheel. This is offline behavior, not a live pool/thread safety proof.
Installed import evidence now executes both inspector checks and records
`runtime_synthetic_analyze_warning_present: false`. Broader validation:
`.venv/bin/python -m pytest tests/docs tests/test_v048_docs_lock.py
tests/test_v048_packaging_sanity.py -q` — 198 passed, one existing dependency
deprecation warning. Strict docs, 366 Python fences/imports, 296 CLI forms,
42,501 local references across 162 pages, and 42 selected external URLs passed.
Ruff passed. The strategy inventory now tracks fifteen functional findings for
separate maintenance; this does not change the roadmap thesis or release scope.

## Admin widget follow-up (2026-09-11)

PT056 / P2: widget UI row limits needed explicit distinction from server-side
validation. The guide now states that boundary and a reproduced rendering side
effect. ADMINWIDGET001 / P2: ArrayAdminWidget.render appends blank strings to the
caller's list when padding to min_rows. Recommend a separate defensive-copy
patch; no persistence or permission bypass is claimed and no runtime fix is made.

An initial JSON escaping concern was disproved by execution and full source
inspection: values are HTML-escaped. The focused test positively verifies that
an inert closing-textarea marker remains escaped; no XSS defect is claimed.
Twenty-one checkout widget tests and two isolated installed-wheel checks pass.
The installed import gate now runs both checks and records input preservation
as false. `.venv/bin/python -m pytest tests/docs tests/test_v048_docs_lock.py
tests/test_v048_packaging_sanity.py tests/admin/test_widgets.py -q` — 219 passed,
one existing dependency deprecation warning. Strict docs, 366 Python fences,
296 CLI forms, 42,504 local references across 162 pages, and 42 selected external
URLs passed. Ruff passed. Broader Admin action/ModelAdmin review remains open.

## Admin action follow-up (2026-09-11)

PT057 / P1: the action guide lacked transaction ownership and unknown-permission
name limits; ModelAdmin implied built-in delete availability despite an empty
default action list. The docs now distinguish explicit action registration,
per-instance hooks, queryset writes, and all-or-nothing transaction ownership.
Source review of `_run_list_action` confirms selection resolution and list/object
permission checking for implemented hooks, and skipping of missing hook names.
That last behavior is a documented sharp edge requiring denial-path tests; this
turn does not claim a separately reproduced authorization bypass.

The exact published action fragment passes in checkout and installed wheel,
verifying method registration, update arguments and the queued message. It is a
mocked query-write check, not proof of authorization or persistence. The existing
Admin suite ran with required database tests enabled against local aksara_test:
142 passed, one existing dependency deprecation warning. The installed import
gate now executes the action fragment. `.venv/bin/python -m pytest tests/docs
tests/test_v048_docs_lock.py tests/test_v048_packaging_sanity.py -q` — 201 passed,
one existing dependency deprecation warning. Strict docs, 366 Python fences,
296 CLI forms and 42,510 local references across 162 pages passed. Ruff passed.
No production code changed. This establishes the scoped action clarification;
it is not final whole-manual or release-candidate acceptance.

## Diagnostic suggestion follow-up (2026-09-11)

PT058 / P1: the autoremediation page implied every issue had executable fixes
and did not distinguish filtered exit status from unfiltered report statistics.
The replacement documents optional suggestions, operator responsibility, service
inspection, checker-failure warnings, and the separate production release gate.
A deterministic CLI check proves that an error without actions is excluded by
`--only-with-actions`, producing exit 0 while JSON stats retain one error. This
is documented filter behavior, not a new functional defect or repair capability.
The exact suggestion example and focused diagnostics tests passed (44 checkout
checks; two installed-wheel checks). No real diagnostic commands or repairs were
executed by the focused mock-report tests. The installed import gate now
executes both checks. `.venv/bin/python -m pytest tests/docs
tests/test_v048_docs_lock.py tests/test_v048_packaging_sanity.py
tests/diagnostics/test_cli_fix_plan.py tests/diagnostics/test_actions_model.py -q`
— 245 passed, one existing dependency deprecation warning. Strict docs, 364
Python fences/imports, 295 CLI forms, and 42,431 local references across 162 pages
passed. Ruff passed. No production code changed; whole-manual acceptance remains open.

## Search reference follow-up (2026-09-11)

PT059 / P1: the search pages overstated semantic quality, provider configuration
and project-wide discovery while omitting experimental status and cache scope.
Three pages now explain local TF-IDF, provider-registry separation, explicit
source discovery, any-tag filtering, ID replacement, lazy vocabulary rebuild,
and Studio's process-global cache. No tenant-filtered search guarantee is made.
The exact local example and collection/query options pass in checkout and an
isolated installed wheel. Studio routes/cache were source-inspected, not browser
or HTTP-tested this turn. No new functional defect or production change is
claimed. The installed import gate now executes the example.
`.venv/bin/python -m pytest tests/docs tests/search tests/test_v048_docs_lock.py
tests/test_v048_packaging_sanity.py -q` — 376 passed, one existing dependency
deprecation warning. Strict docs, 359 Python fences/imports, 292 CLI forms, and
42,287 local references across 162 pages passed. Ruff passed. This is scoped
search validation; whole-manual and candidate acceptance remain open.

## Studio access follow-up (2026-09-12)

PT060 / P1: Studio setup/configuration needed explicit distinction between the
required secret and router bearer authentication, origin policy exceptions,
and local credential bypass. The quickstart now binds development to loopback;
the overview no longer claims a complete live backend view or uses v0.6 status.
Eight in-process HTTP requests verify absent/wrong credentials, exact bearer,
same/allowed/denied origins, empty allowlist and disabled credential checks.
The dependency test passes in checkout and installed wheel. It does not prove
staff-session database lookup, full Studio mounting, browser UI, or production
exposure. The installed import gate now runs the access cases.
`.venv/bin/python -m pytest tests/docs tests/api/test_studio_auth.py
tests/test_v048_docs_lock.py tests/test_v048_packaging_sanity.py -q` — 210 passed,
one existing dependency deprecation warning. Strict docs, 359 Python fences,
292 CLI forms, and 42,291 local references across 162 pages passed. Ruff passed.
No production settings or behavior changed; final whole-manual review remains open.

## AI execution boundary follow-up (2026-09-12)

PT061 / P1: AI safety still described durable operation identity, reauthorization,
and cancellation as deferred to v0.7. The page now distinguishes the released
Durable Authorized Operations path from process-local prompt calls, synchronous
MCP replay, and experimental planner/session state. Related experimental pages
now reference the current v0.7 boundary without promoting their APIs to stable.

The first planner/codegen/patch-preview/safety examples execute in a disposable
project in checkout and installed wheel. Generated Python compiles; preview
returns diffs without applying them, and the original model file remains intact.
No provider calls, planner execution, patch application, or autonomous recovery
are certified by this test. The installed import gate now executes it.
Validation: `.venv/bin/python -m pytest tests/docs tests/test_v048_docs_lock.py
tests/test_v048_packaging_sanity.py tests/ai/test_ai_codegen.py
tests/ai/test_codegen_sanitization.py tests/ai/test_ai_planner.py
tests/ai/test_v049_planner_edges.py tests/ai/test_ai_patch.py
tests/ai/test_v049_patch_safety.py tests/ai/test_patch_security.py -q` — 500 passed,
one existing dependency deprecation warning. Strict docs, 359 Python fences,
292 CLI forms, and 42,293 local references across 162 pages passed. Ruff passed.
No production code changed; final whole-manual acceptance remains open.

## Gap analysis and historical navigation follow-up (2026-09-12)

PT062 / P2: gap analysis described eight parallel categories; the implementation
has nine and awaits each checker sequentially. The guide now states those facts,
warning-on-checker-failure behavior, unknown-category validation, empty-list default,
and the difference between fix suggestions and production release policy.
The roadmap index now links the released v0.7 stability contract. Historical
release notes, contracts, and evidence are preserved; no history was rewritten.
The page also corrects GET-only category selection and removes unsupported
custom-checker registration advice. The single-category helper logs checker
failures and returns an empty list, unlike the full report's warning issue.
Controlled installed-package tests prove both behaviors and invalid-category
handling; they do not certify live deployment health. The first test rejected
the draft unknown-category-skipping claim, which was corrected before commit.
Validation: 348 docs/packaging/gap tests passed with one dependency deprecation
warning; Ruff passed; 358 Python fences/imports and 292 CLI forms passed;
strict docs and 42,286 local references across 162 pages passed.
No runtime changes. Final whole-manual acceptance remains open.

## Security reference boundary review (2026-09-12)

PT063 / P1: authentication labels and claim normalization could be read as
credential-verification support, and field policy guidance omitted its no-field-
metadata fallback. The two security references now distinguish parsing from
verification, integrated route enforcement from arbitrary ORM writes, and
visibility metadata from universal redaction. They describe system/read-only
rules, generated MCP ASGI dispatch, and custom-handler responsibility. Studio
links to its exact access rules; ordinary tasks link to the distinct durable path.

Source review: `aksara/security/mcp.py`, `principal.py`, `policy.py`,
`enforcement.py`, `aksara/mcp/server.py`, `aksara/api/viewsets.py`, and Studio
settings/access guidance. Existing policy tests directly cover the metadata
fallback; no production behavior was changed or newly classified as a defect.

Validation: required local PostgreSQL run of policy engine, MCP credentials,
principal, MCP protocol boundary and advanced field policy tests: 199 passed.
The initial unconfigured run was 194 passed/5 skipped and is not the database
validation claim. Docs/packaging tests: 207 passed, one dependency deprecation
warning. Strict docs, 358 Python fences/imports, 292 CLI forms and 42,288 local
references passed. This checkpoint does not claim final whole-manual acceptance.

## Security overview and release-policy review (2026-09-12)

PT064 / P1: the threat model described existing supply-chain/release automation
as planned and described matrix enforcement without the release-mode exception.
The overview/release pages still led with the older stability boundary and could
make named environment configuration look like verified branch protection.
Four pages now link the v0.7 contract, describe durable ownership/external-effect
trust boundaries, separate application coverage from framework matrices, and
state that manual publication does not itself rerun the release gate. No external
audit or configured hosted protection is inferred from workflow YAML.

Reviewed `aksara/security/checks.py`, `.github/workflows/security.yml`,
`release-gate.yml`, `publish.yml`, and `.github/dependabot.yml`. Existing matrix
and production-policy tests: 69 passed. Docs/packaging tests: 207 passed with one
dependency warning. Strict docs, 358 Python fences/imports, 292 CLI forms and
42,292 local references across 162 pages passed. No production code changed.
These are page corrections and scoped checks; final candidate acceptance remains
incomplete, and publication was not dispatched.

## Remaining conceptual boundaries review (2026-09-12)

PT065 / P1: synchronous MCP approval limitations were phrased as a framework-wide
v0.6 limitation and the execution description implied RLS without deployment
configuration. The MCP page now distinguishes stateless grants from v0.7 durable
approval, states RLS prerequisites and explicitly excludes protocol MCP Tasks.
The advanced-field policy is labeled as a historical design/compatibility record
and links current references rather than presenting every “should” as current API.
The experimental query page now states its fetch-all-then-slice behavior, verified
in `execute_ai_query_plan`; no resource-bounded query claim is made.

Retained unchanged after review:

| Page | Disposition | Evidence and bounds |
| --- | --- | --- |
| `advanced/caching.md` | RETAIN | Installed 0.7.0 isolated `find_spec('aksara.cache')` returns None; no general cache contract claimed. |
| `ai-mode/planner.md` | RETAIN | `aksara/ai/planner.py` validation/handler execution and existing exact preview example checks; experimental, no planner-quality or persistence guarantee. |
| `ai-mode/runtime.md` | RETAIN | `run_prompt_pack` signature, connector dispatch, override resolution, timeout/token handling inspected; provider quality explicitly excluded. |

Validation: `pytest tests/mcp tests/docs/test_ai_developer_examples.py -q`:
23 passed with one dependency warning. Docs/packaging: 207 passed with the same
warning. Strict docs, 358 Python fences/imports, 292 CLI forms and 42,297 local
references passed. No production code changed. These dispositions do not imply
all 163 public pages have completed semantic acceptance.

## Release guide and historical entry points (2026-09-12)

PT066 / P2: the release guide omitted the established compatibility dimensions,
required database setting and packaged/reference journeys, and did not make
candidate-specific evidence ownership explicit. It now names the actual
Python 3.11/3.14 × minimum/latest-supported matrix, hosted PostgreSQL 16 profile,
installed-wheel separation and exact-ref checks before manual publication.
Workflow configuration was inspected; hosted protection is not inferred.

The notes index now identifies its entries as dated historical records. The
v0.5.49 note/announcement bodies, release changelog and v0.7 stability contract
are preserved. The latter remains the authoritative released contract, not a
new v0.7.1 guarantee. Historical narrative is not used as current setup advice.

Validation: 207 docs/packaging tests passed with one dependency warning; strict
docs, 358 Python fences/imports, 292 CLI forms and 42,302 local links/assets
passed. No production-source change and no publication action. The requirement
checkpoint's stale counts were reconciled without treating scoped evidence as
final candidate completion.

## Capability/register reconciliation (2026-09-12)

Reconciled the current matrix with the already verified policy, Admin,
Studio-dependency and deterministic AI preview checks. CLI counts now match
292 parsed commands and seven exclusions. The central contradiction register
contains PT-001 through PT-066 exactly once in order, including the media
finding formerly recorded only in prose. Detailed checkpoints remain intact.
No new functional finding or runtime success claim was introduced.

Validation: identifier coverage/uniqueness and five installed-evidence status
checks passed; 207 docs/packaging tests passed with one dependency warning.
Public-site content did not change in this checkpoint, so its existing build
and link evidence remains scoped to the same sources.

## Evaluator-to-first-project reading acceptance (2026-09-12)

Read README, docs home, getting-started index and the complete first-project
page as one path. Retain these four pages: the category/audience/tradeoff and
pre-1.0 limits are discoverable, the entry points lead to one six-stage Ticket
Desk, and chapter one supplies each file/command through protected CRUD tests.
Token sharing, loopback exposure, optional launch-check warnings and the next
chapter are explicit. This is an author reading review, not independent user
comprehension research or a measured ten-minute completion claim.

`entry-reading-review.json` records exact page hashes and reasons. Its
first-project source hash matches the existing installed-wheel journey's first
stage with three API tests; no new database execution is claimed here. Navigation
and docs-lock tests passed: 74. No public content or runtime behavior changed.
The broader manual and actual candidate execution still require acceptance.

## Conceptual manual and persistence entry review (2026-09-12)

PT067 / P1: the ORM overview still claimed database independence, default integer
IDs, directly awaitable QuerySets and object-valued lazy forward foreign keys.
Its unrelated Product/User snippets also used undeclared fields and called an
unawaited manager result a QuerySet. The overview now teaches the actual
PostgreSQL/model/migration/query/relation/transaction boundaries through the
existing Ticket Desk and links the detailed references. It explicitly separates
ORM writes from HTTP permissions, serializers and external-effect rollback.

The glossary repeated nonexistent FilterSet/defer/write-only configuration,
cache/signal decorators and natural-language query-engine claims. Those entries
now identify actual supported concepts or clearly say the named API is absent;
a duplicated execution-term block was removed. No runtime API was added.

Read the complete application-boundaries, stability and API overview pages;
retain them with their explicit application-owned policy and custom-action
limitations. This author reading does not replace independent usability research.
Source anchors: manager query/terminal methods, model defaults, actual AI query
and planner APIs, and existing installed ViewSet/field/relation contracts.
Validation: 207 docs/packaging tests passed with one dependency warning; strict
docs, 348 Python fences/imports, 292 CLI forms and 42,169 local references passed.
The single ORM query fragment is contextual to the connected tutorial; syntax
and imports are checked, not a new standalone database journey in this turn.

## Model guide consistency follow-up (2026-09-12)

Follow-up to PT054/PT026: the model guide still repeated ignored Meta ordering,
indexes and unique_together despite the corrected metadata reference. Removed
those declarations and explained explicit ordering and reviewed migrations.
The complete model example now uses select_related/get_related instead of
awaiting a forward FK ID. Its database setup and transaction prerequisites are
explicit, and UUID-default wording allows explicit primary-key overrides.
The central register's PT067 row was kept contiguous with the table.

Validation: installed model-default/metadata/relation shape checks and public
imports passed; docs/packaging tests: 207 passed with one dependency warning.
Strict docs, 348 Python fences, 292 CLI forms and 42,152 local references passed.
This turn does not claim database execution of the complete Product/Category
example; that remains a high-value snippet coverage item for final acceptance.
No production code changed.

## Complete model example execution (2026-09-12)

Extended check_public_queries.py to extract the exact complete Product/Category
block. Installed 0.7.0 execution on local PostgreSQL persists both records,
checks Decimal/stock/Array/JSON values, confirms forward FK IDs and eager access.
The combined gate now passes 31 checks and verifies disposable-schema removal.
Schema setup is test-owned DDL, not a migration or RLS proof. Ruff and 207
docs/packaging tests passed; no production implementation changed.

RELATION001 / P1: an additional installed probe found that
select_related(...).first() returns a model without the requested related
object; get_related raises ValueError. Source confirms first() calls _from_record
without the loading steps in all(). The runner records
runtime_first_populates_requested_relation=false and preserves this negative
control. Recommend a separate terminal-method relation-loading consistency patch
with first/all, empty-result, FK/O2O and prefetch tests. The documented complete
example uses select_related(...).all() and passes unchanged. The initial harness
also tried nonexistent QuerySet.get; that was a test mistake, not a framework
finding. Strategy/public-reference follow-up for RELATION001 remains open.

## Relation limitation public guidance (2026-09-12)

RELATION001 is now disclosed in the public relation guide and strategy report.
The guide/glossary also correct the single-JOIN claim: all() loads parent rows,
then batches requested FK/O2O relations. The roadmap thesis remains focused on
correctness/adoption; the seventeenth finding does not justify scope expansion.
No production fix was made. This updates the earlier pending follow-up.

Validation: 10 installed Admin/relation checks passed against local PostgreSQL;
disposable schema removed. 207 docs/packaging tests passed with one dependency
warning; strict docs, 348 Python fences/imports, 292 CLI forms, 42,152 local
references and 42 selected external links passed. External reachability is not
a new market-research claim. The model-example negative control remains false.

## Complete relation example execution (2026-09-12)

Follow-up to PT032/PT026: reading and running the full relation guide exposed
unsupported forward M2M `tags__name` filters and the unrecognized `"self"`
shortcut. The guide now resolves a tag and uses its reverse manager, and uses
the explicit category model name. The complete example uses distinct Blog*
model names and states setup/finalization prerequisites. No query API was added.

The Admin/relation runner extracts the exact complete example before finalizing
all models, creates test-owned tables/junction DDL, and executes demo(). Six new
assertions cover persisted post, M2M membership/reverse access, reverse FK/O2O
and self-reference. All 16 checks pass against installed 0.7.0 and local
PostgreSQL; schema removal is verified. The first harness attempt finalized the
initial fixture before loading the example; loading all models first corrected
that setup error. The unsupported filter/self examples were documentation errors
and were corrected rather than adding runtime features.

Ruff passed. Docs/packaging: 207 passed with one dependency warning. Strict docs,
348 Python fences/imports, 292 CLI forms and 42,153 local references passed.
This does not certify migration generation, delete-constraint behavior, RLS,
every relation operation or final candidate readiness.

## Expanded example evidence requirements (2026-09-12)

The query and Admin/relation evidence tests now require the new complete-example
checks and their source-page entries, rather than accepting only the older
subset. The query test also requires the explicit false RELATION001 runtime
flag. Three in-memory tampering controls removed a model check, removed a
relation check, or inverted that flag; each was rejected. Committed evidence
was not modified by these controls.

Validation: two focused tests and Ruff passed; the broader docs/packaging set
passed 207 tests with one dependency warning. This strengthens evidence
acceptance without claiming fresh PostgreSQL execution or whole-manual approval.
No public page, production code or historical evidence changed in this checkpoint.

## Field validation and catalog example execution (2026-09-12)

The advanced-field runner now extracts the exact field-validation fragment and
complete app/catalog_models.py declarations in addition to the seven advanced
blocks. Both caught validation errors are observed, then autodetected CreateTable
operations set up the catalog fixture. Persistence checks cover Decimal/Enum,
quantity/JSON defaults, nullable fields and the stored FK. All 19 installed
PostgreSQL/pgvector checks pass; disposable-schema removal is verified.
No documentation correction was required by these additional examples.

The evidence test requires all four new checks. Ruff and the full 207-test
docs/packaging set pass (one dependency warning). The gate uses an admin-role
fixture, not RLS, full migration CLI/history or every field/write-path proof.
No production code or public page changed; final candidate acceptance is open.
