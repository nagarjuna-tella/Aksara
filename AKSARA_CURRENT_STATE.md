# Executive Summary

**Verdict: NO — do not label this checkout v0.6 Production Mode yet. Closest maturity: beta, with experimental developer/AI surfaces.**

This is a bounded evidence-based audit, not a certification or a completed exhaustive manual feature audit. Existing tests were exercised against the requested local PostgreSQL database, supplemented with static checks, CLI discovery, benchmarks and targeted failure injection. Unexercised claims remain explicitly unverified.

At HEAD `dccef5ddf3b8ad9c5fee1ccdc39cf753bbf9032e`, the full suite on freshly resolved allowed dependencies produced **7,831 passed, 15 failed, 3 skipped, 26 warnings in 43.46s**. With FastAPI 0.136.1 / Starlette 1.0.1, it produced **7,846 passed, 3 skipped, 25 warnings in 43.18s**. The latter is a changed-environment experiment, not a flaky retry or replacement for the first result.

Two independent release blockers are established: allowed newer dependencies break route discovery and related checks; failed session/transaction setup leaks acquired connections, with transaction startup also leaving session context installed. The 52-case benchmark smoke passes. Strict docs, distribution build and metadata checks pass. Ruff and mypy fail.

Evidence is preserved in [audit-evidence/current-state](audit-evidence/current-state/). Test evidence proves the assertions exercised, not every edge case or deployment topology. No production code changes, merges, version bumps or publication were performed.

# Repository Snapshot

- Local audit date: September 8, 2026 America/Detroit; benchmark filenames use September 9 UTC.
- Branch: `fix/advanced-field-policy-v055`.
- HEAD: `dccef5ddf3b8ad9c5fee1ccdc39cf753bbf9032e`.
- Working tree before report generation: clean, verified after file hydration.
- Local main / origin-main snapshot: `b89bfa6`; branch is 5 ahead, 0 behind local main.
- Latest local release tag: `v0.5.54`; pyproject version: `0.5.54`.
- Remote-tracking references are cached local evidence, not refreshed live GitHub state. No public-release/PyPI claim is made.
- GitHub PR/check/review lookup blocked: `gh` is not authenticated (exit 4).

Five commits after local main:

1. `bc37857`: Advanced Field Policy docs/navigation.
2. `7fe1320`: Array/Vector/JSON policy implementation.
3. `c42ff26`: review-gap fixes.
4. `bf388ac`: review-comment fixes.
5. `dccef5d`: benchmark workload overhaul.

The branch changes 64 files, with 6,760 insertions and 1,967 deletions against main. This combines correctness work and a substantial benchmark rewrite. Local branch names alone do not prove that a branch is abandoned or unmerged upstream.

```text
  fix/admin-correctness-v052
* fix/advanced-field-policy-v055
  fix/migration-safety-v050
  fix/orm-primitive-correctness-v051
  fix/orm-query-semantics-v053
  fix/orm-write-path-consistency-v054
  main
  remotes/origin/HEAD -> origin/main
  remotes/origin/dependabot/github_actions/actions/checkout-6
  remotes/origin/dependabot/github_actions/actions/checkout-7
  remotes/origin/dependabot/github_actions/actions/setup-python-6
  remotes/origin/dependabot/github_actions/actions/upload-artifact-7
  remotes/origin/dependabot/github_actions/github/codeql-action-4
  remotes/origin/fix/admin-correctness-v052
  remotes/origin/fix/advanced-field-policy-v055
  remotes/origin/fix/migration-safety-v050
  remotes/origin/fix/orm-primitive-correctness-v051
  remotes/origin/fix/orm-query-semantics-v053
  remotes/origin/fix/orm-write-path-consistency-v054
  remotes/origin/gh-pages
  remotes/origin/main
  remotes/origin/optimize-orm-tracing-serializers-12612761980575634627
```

Local tags:

```text
v0.5.54
v0.5.53
v0.5.52
v0.5.51
v0.5.50
v0.5.49
v0.5.48
v0.5.47
v0.5.46
v0.5.45
```

Historical commit anchors inspected: v0.5.50 migration safety (`2a9aa3b` release), v0.5.51 primitive coercion (`2c3301d`, `eb98efb` release), v0.5.52 Admin correctness (`f5b4980`, `a0c9280` release), v0.5.53 query/migration generation (`911f79f`, `161d0f7` release), v0.5.54 writes/relations (`7b26811`, `b89bfa6` release). `a03e5c7` introduces the v0.6 stability direction. This identifies history; it does not independently replay each historical release.

Outstanding-looking refs include Advanced Field Policy and `origin/optimize-orm-tracing-serializers-12612761980575634627`. Five dependency-update refs target GitHub Actions. Their current PR state, conflicts and review disposition are UNKNOWN. Release-named fix branches remain present; age alone is insufficient grounds to abandon them.

`aksara/ai/planner.py:1187` and nearby lines contain generated test TODO placeholders; these are not executable coverage. A full TODO disposition audit remains uncompleted.

# Codebase by the Numbers

Counts use `git ls-files`; LOC includes comments/blank lines and is computed from parsed tracked Python files. Documentation means tracked Markdown files. CLI count refers to command-tree nodes, including groups.

| Metric | Measured value |
| --- | ---: |
| Tracked files | 728 |
| Tracked Python files | 527 |
| Framework Python LOC | 86,322 |
| Test Python files | 276 |
| Test LOC | 98,928 |
| Source:test LOC ratio | 0.87:1 |
| Markdown files | 163 |
| Benchmark tracked files | 36 |
| CLI implementation files | 5 |
| Paths containing migration | 29 |
| Example tracked files | 49 |
| AST test function definitions | 7,500 |
| Collected cases including skips | 7,849 |
| CLI help nodes / failures | 117 / 0 |
| Package `__all__` exports | 158 |
| Architecture areas mapped below | 29 |

Public field subclasses observed: String, Integer, Boolean, DateTime, UUID, JSON, Vector, Array, Text, FileField, ImageField, Email, URL, Decimal, Enum, Float, Date, Slug, SmallInteger, BigInteger, PositiveInteger, PositiveSmallInteger, PositiveBigInteger, Time, Duration, IPAddress, Binary, FilePath, ForeignKey, OneToOne, ManyToMany. GenericForeignKey additionally exists outside this subclass count; helpers and managers are not field types.

Largest source modules:

| Module | LOC |
| --- | ---: |
| `aksara/cli/main.py` | 8111 |
| `aksara/fields.py` | 3849 |
| `aksara/studio/utils.py` | 3402 |
| `aksara/studio/fastapi.py` | 2577 |
| `aksara/studio/models.py` | 2337 |
| `aksara/migrations/operations.py` | 2300 |
| `aksara/ai/patch.py` | 2150 |
| `aksara/manager.py` | 1987 |
| `aksara/ai/planner.py` | 1632 |
| `aksara/migrations/autodetector.py` | 1560 |

Largest test modules:

| Module | LOC | Test definitions |
| --- | ---: | ---: |
| `tests/ai/test_schema_doctor.py` | 1953 | 111 |
| `tests/studio/test_studio_sanity_sweep.py` | 1482 | 163 |
| `tests/test_gapanalysis.py` | 1433 | 112 |
| `tests/admin/test_admin_features_v051.py` | 1375 | 57 |
| `tests/studio/test_studio_endpoints.py` | 1300 | 65 |
| `tests/ai/test_ai_context.py` | 1207 | 64 |
| `tests/ai/test_ai_patch.py` | 1162 | 79 |
| `tests/ai/test_ai_agent.py` | 1118 | 50 |
| `tests/test_v039_investigation_engine.py` | 1076 | 86 |
| `tests/studio/test_aihub_api.py` | 1055 | 93 |

The CLI concentrates 8,111 lines in one module; field behavior concentrates 3,849 lines, and Studio is spread across several very large modules. High aggregate test density does not cover failure cleanup: a short injected setup error exposed leakage despite thousands of passing tests. Counts by subsystem are below; they measure test volume rather than branch coverage. Coverage instrumentation was not run.

# Automated Validation Baseline

Environment: macOS ARM64, Python 3.14.4, asyncpg 0.31.0; PostgreSQL 18.4 at `127.0.0.1:5432`, database `aksara_test`, role `postgres`. `vector` and `pgcrypto` were already installed; public schema had 32 tables before tests. The role has `rolsuper=true`, `rolbypassrls=true`. CI uses Python 3.11 and PostgreSQL 16; those versions were not executed here.

The database password was supplied only to process environments/probes and is redacted from saved evidence. Do not commit it to environment files. Reproduction assumes the operator sets `DATABASE_URL` to the supplied local credentials.

```sh
uv venv /tmp/aksara-audit-venv --python /opt/homebrew/bin/python3
uv pip install --python /tmp/aksara-audit-venv/bin/python -e '.[dev]' build twine pip-audit bandit mkdocs-material mkdocs-autorefs mike 'pymdown-extensions>=10.21.3' psutil sqlalchemy
export PATH=/tmp/aksara-audit-venv/bin:$PATH
export AKSARA_REQUIRE_DATABASE_TESTS=1
export PYTHONPYCACHEPREFIX=/tmp/aksara-audit-pycache
export HYPOTHESIS_STORAGE_DIRECTORY=/tmp/aksara-audit-hypothesis
# DATABASE_URL is set by the operator; password intentionally omitted.
```

`tests/conftest.py` otherwise permits unusable database configuration to be converted into skips. Required-database mode was enabled for every completed full-suite run.

| Command (with environment above) | Exit | Results | Time / limitation |
| --- | ---: | --- | --- |
| `python -m pytest --tb=short -q --junitxml=/tmp/aksara-audit-evidence/pytest.xml` | 1 | 7831 pass, 15 fail, 3 skip, 0 xfail, 26 warnings | 43.46s; FastAPI 0.141.1 / Starlette 1.6.0 |
| `uv pip install --python /tmp/aksara-audit-venv/bin/python 'fastapi==0.136.1' 'starlette==1.0.1'` | 0 | controlled dependency change | ~0.5s |
| `python -m pytest --tb=short -q --junitxml=/tmp/aksara-audit-evidence/pytest-minimum.xml` | 0 | 7846 pass, 0 fail, 3 skip, 0 xfail, 25 warnings | 43.18s; minimum web dependencies |
| `ruff check aksara tests --output-format concise` | 1 | 7290 findings | runtime not separately measured; no fixes applied |
| `mypy aksara` | 1 | 504 errors in 62 files; 176 source files checked | runtime not separately measured |
| `bandit -r aksara -x tests,.venv,docs --severity-level high --skip B324` | 0 | no high-severity findings at configured threshold | not a complete security review |
| `pip-audit --desc auto --format json --output /tmp/aksara-audit-evidence/dependencies.json` | 0 | no known vulnerabilities found | audits installed environment, not CI's exact `pip-audit --desc auto .` command |
| `mkdocs build --strict -f docs/mkdocs.yml --site-dir /tmp/aksara-audit-evidence/site` | 0 | strict build passed | 103.05s including file availability delays |
| `python -m build --outdir /tmp/aksara-audit-evidence/dist` | 0 | wheel and sdist built | wall time not separately measured |
| `twine check /tmp/aksara-audit-evidence/dist/*` | 0 | both distributions passed | ~2.8s |
| `aksara --help` and recursive Click command help | 0 | 117 help nodes passed | ~0.4s; help is not command execution |
| `aksara examples validate --format json` | 0 | 63 checks OK, 2 skipped | static/readiness checks, not every example served live |
| `aksara doctor production-check --format json` | 0 | status WARN | CI production settings; warnings detailed below |
| `python -m benchmarks.runner --mode smoke --impl aksara --concurrency 1,5 --output-dir /tmp/aksara-audit-evidence/benchmarks` | 0 | 52 pass, 0 fail, 0 unsupported | tiny profile; not a sustained load test |
| `python /tmp/aksara-audit-evidence/repro_cleanup.py` | 0 | reproduced 3 cleanup failures | ~0.2s; prints bad behavior intentionally |

Doctor used CI's production environment: debug off, a non-default CI secret, MCP/AI console/Studio exposure off, Studio authentication and secure cookies on, Admin rate limiting on, CORS allow-all and credentials off, security matrix requirement disabled. No external provider credentials were supplied.

Skips: OpenAPI fuzz collection requires optional schemathesis; the file additionally contains two unconditional placeholder skips, so installing the dependency alone will not implement fuzzing. Two OpenAI example checks require `OPENAI_API_KEY`. There are no xfails. Warnings are mainly Click deprecations; see full logs for exact text.

Earlier invocations stalled before test execution on macOS `dataless` source/cache reads and were terminated. Initially 587/728 tracked files were dataless. Reads hydrated the tracked files; a traceback then located a Hypothesis cache read hang. Temporary Python/Hypothesis cache paths resolved it. Those attempts are environmental interruptions, not test passes or flakes.

Gitleaks/Docker secret scan, SBOM generation, Python 3.11 CI replay, isolated wheel-install import, installed-wheel example execution and current GitHub release gates were NOT RUN. No claim of an entirely green release gate is made.

Initial full-suite results by test namespace (aggregated from JUnit; top-level files retain separate rows):

| Namespace | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| `collection skip` | 0 | 0 | 1 |
| `tests.admin` | 136 | 6 | 0 |
| `tests.ai` | 1814 | 0 | 0 |
| `tests.api` | 218 | 2 | 0 |
| `tests.benchmarks` | 19 | 0 | 0 |
| `tests.cli` | 466 | 0 | 0 |
| `tests.db` | 31 | 0 | 0 |
| `tests.diagnostics` | 305 | 0 | 0 |
| `tests.dx` | 203 | 0 | 0 |
| `tests.examples` | 38 | 0 | 2 |
| `tests.fields` | 61 | 0 | 0 |
| `tests.inspectors` | 52 | 0 | 0 |
| `tests.integration` | 46 | 2 | 0 |
| `tests.middleware` | 42 | 0 | 0 |
| `tests.migrations` | 452 | 0 | 0 |
| `tests.models` | 18 | 0 | 0 |
| `tests.patterns` | 105 | 0 | 0 |
| `tests.perf` | 41 | 0 | 0 |
| `tests.search` | 172 | 0 | 0 |
| `tests.security` | 424 | 0 | 0 |
| `tests.studio` | 1141 | 3 | 0 |
| `tests.test_advanced_field_policy` | 48 | 0 | 0 |
| `tests.test_aihub_gaps` | 29 | 0 | 0 |
| `tests.test_app_output` | 2 | 0 | 0 |
| `tests.test_array_field` | 40 | 0 | 0 |
| `tests.test_auth` | 32 | 0 | 0 |
| `tests.test_bug_hunt_phase1_fixes` | 8 | 0 | 0 |
| `tests.test_bug_hunt_phase3_fixes` | 11 | 0 | 0 |
| `tests.test_bug_hunt_phase5_fixes` | 5 | 0 | 0 |
| `tests.test_bug_hunt_phase7_fixes` | 7 | 0 | 0 |
| `tests.test_debug_error_pages` | 61 | 0 | 0 |
| `tests.test_durable_workflows` | 6 | 0 | 0 |
| `tests.test_field_params` | 95 | 0 | 0 |
| `tests.test_fields` | 39 | 0 | 0 |
| `tests.test_fields_extended` | 117 | 0 | 0 |
| `tests.test_fields_new` | 50 | 0 | 0 |
| `tests.test_gapanalysis` | 112 | 0 | 0 |
| `tests.test_generic_foreign_key` | 2 | 0 | 0 |
| `tests.test_i18n` | 5 | 0 | 0 |
| `tests.test_integration` | 21 | 0 | 0 |
| `tests.test_integration_m2m` | 15 | 0 | 0 |
| `tests.test_jsonb_vector_features` | 3 | 0 | 0 |
| `tests.test_mail` | 5 | 0 | 0 |
| `tests.test_manager` | 44 | 0 | 0 |
| `tests.test_media_mounting` | 0 | 2 | 0 |
| `tests.test_models` | 25 | 0 | 0 |
| `tests.test_no_secrets_in_examples` | 10 | 0 | 0 |
| `tests.test_permissions` | 35 | 0 | 0 |
| `tests.test_queryset_order_by` | 44 | 0 | 0 |
| `tests.test_relations` | 33 | 0 | 0 |
| `tests.test_sanity_audit` | 45 | 0 | 0 |
| `tests.test_security_phase1` | 23 | 0 | 0 |
| `tests.test_security_phase2` | 22 | 0 | 0 |
| `tests.test_security_phase4` | 17 | 0 | 0 |
| `tests.test_security_round2` | 55 | 0 | 0 |
| `tests.test_shell` | 21 | 0 | 0 |
| `tests.test_soft_delete` | 3 | 0 | 0 |
| `tests.test_storage` | 4 | 0 | 0 |
| `tests.test_tasks` | 23 | 0 | 0 |
| `tests.test_testing` | 21 | 0 | 0 |
| `tests.test_v025_ai_hub` | 92 | 0 | 0 |
| `tests.test_v02_features` | 56 | 0 | 0 |
| `tests.test_v037_ai_consolidation` | 73 | 0 | 0 |
| `tests.test_v037_features` | 44 | 0 | 0 |
| `tests.test_v038_relations` | 32 | 0 | 0 |
| `tests.test_v039_investigation_engine` | 86 | 0 | 0 |
| `tests.test_v040_console_flow` | 22 | 0 | 0 |
| `tests.test_v040_daily_briefing` | 30 | 0 | 0 |
| `tests.test_v040_intent_engine` | 40 | 0 | 0 |
| `tests.test_v040_investigation_continuation` | 27 | 0 | 0 |
| `tests.test_v044_features` | 24 | 0 | 0 |
| `tests.test_v044_filter_backends` | 18 | 0 | 0 |
| `tests.test_v044_pagination` | 19 | 0 | 0 |
| `tests.test_v045_multitenancy` | 5 | 0 | 0 |
| `tests.test_v045_orm_expressions` | 14 | 0 | 0 |
| `tests.test_v045_transactions` | 5 | 0 | 0 |
| `tests.test_v048_docs_lock` | 64 | 0 | 0 |
| `tests.test_v048_examples_validate` | 80 | 0 | 0 |
| `tests.test_v048_launch_check` | 39 | 0 | 0 |
| `tests.test_v048_packaging_sanity` | 36 | 0 | 0 |
| `tests.test_v049_debug_cli_extensions` | 26 | 0 | 0 |
| `tests.test_v049_global_invariants` | 38 | 0 | 0 |
| `tests.test_v049_orm_edges` | 39 | 0 | 0 |

# Complete Feature Matrix

This table inventories requested areas; it is not a claim that every permutation was tested. WORKING WITH LIMITATIONS means existing relevant assertions passed, with identified scope boundaries. UNTESTED explicitly means no sufficient behavioral proof was obtained. Full JUnit files preserve individual test cases. New-dependency route failures take precedence over older-dependency passes.

| Area | Feature | Status | Evidence | Limitations / Bugs |
| ---- | ------- | ------ | -------- | ------------------ |
| Application | Creation/settings/lifecycle/middleware/errors | WORKING WITH LIMITATIONS | tests.dx, tests.middleware, tests.test_app_output; full suite | No process termination or dependency outage matrix; route discovery breaks on newer allowed web dependencies |
| ORM | Construction/defaults/validation/save/create/get/filter/exclude/order/pagination/count/exists | WORKING WITH LIMITATIONS | tests.models, tests.test_models, tests.test_manager, tests.test_v049_orm_edges; benchmark reads/single_ops | No claim of exhaustive concurrency/invalid-input combinations |
| ORM | update/delete/expressions/aggregates/upsert/bulk_create/bulk_update | WORKING WITH LIMITATIONS | tests.test_v045_orm_expressions, tests.test_advanced_field_policy, benchmark bulk_writes | Cross-path behavior limited to exercised cases |
| Transactions | Commit/rollback/nested savepoints | WORKING WITH LIMITATIONS | tests.test_v045_transactions; benchmark transactions 7 pass | Setup failure paths BROKEN; cancellation/deadlock/restart not comprehensively exercised |
| Transactions | Connection/session cleanup on setup failure | BROKEN | repro_cleanup.py; db/session.py and db/transaction.py | Tenant setup leaks connections; transaction.start failure leaks connection and ContextVar |
| Fields | Primitive/extended types and edge coercion | WORKING WITH LIMITATIONS | tests.fields and tests.test_fields*; test_field_params | Coverage is existing tests, not a new edge-case Cartesian product |
| Fields | JSON scalar/NaN; Vector precision/finite/bool/empty; Array item/nested policy | WORKING WITH LIMITATIONS | 48 advanced-field-policy tests, 40 Array tests, JSONB/Vector integration | Only current branch validated; database extension installed |
| Fields | File/Image wrapper versus path/update contracts | WORKING WITH LIMITATIONS | tests.test_advanced_field_policy; tests.test_storage | Remote object store and malicious image corpus not live-tested |
| Fields | Custom field hooks/extensions | WORKING WITH LIMITATIONS | field and write-path regression suites | Arbitrary third-party fields not validated |
| Fields | Generated/computed columns beyond expressions | UNKNOWN | No sufficient isolated probe | Do not equate ORM expressions with generated-column support |
| Relations | FK/reverse FK/O2O/reverse O2O/M2M/reverse M2M/loading/filtering | WORKING WITH LIMITATIONS | tests.test_relations, test_v038_relations, integration_m2m and relationship benchmark | Forward FK is an ID contract; custom PK/circular/cascade combinations not individually audited here |
| Relations | GenericForeignKey | WORKING WITH LIMITATIONS | tests.test_generic_foreign_key: 2 pass | Narrow test count; no exhaustive deletion/isolation proof |
| Relations | on_delete / nullable SET NULL / PROTECT | WORKING WITH LIMITATIONS | normalize_on_delete called by ForeignKey; relation regression tests | PROTECT/RESTRICT semantics should remain explicitly documented |
| Relations | Custom M2M through model | PARTIAL | fields.py:3380 raises ValueError for through | Explicitly unsupported; safe rejection is not implementation |
| Migrations | Generate/apply/order/track/checksum/rollback/index/FK/default operations | WORKING WITH LIMITATIONS | 452 migration tests, migration benchmark | Historical schema upgrades and concurrent real migrators not independently replayed |
| API | CRUD/serializers/filter/order/pagination/auth/permissions/OpenAPI | WORKING WITH LIMITATIONS | API suite 218 pass/2 fail on newest; all pass with minimum dependencies | Runtime request assertions pass in many tests, but route metadata compatibility is broken |
| API | Router discovery/autoregistration metadata | BROKEN | test_router and test_viewset_autoregistration failures | Allowed dependency versions introduce _IncludedRouter lacking path |
| Security | Principal/roles/policy/field denial/object permissions/MCP enforcement | WORKING WITH LIMITATIONS | 424 tests.security pass plus auth/permission suites | Not a comprehensive external attack review; production matrix optional in CI |
| Tenancy | ORM/middleware/security tenant contexts | WORKING WITH LIMITATIONS | test_v045_multitenancy; security suites | Postgres role bypasses RLS; no restricted-role end-to-end guarantee |
| MCP | Discovery/schema/CRUD/invalid arguments/principal/policy | WORKING WITH LIMITATIONS | AI/security test cases in JUnit | No external MCP client transport smoke; route-derived AI tools fail on newer dependencies |
| AI | Provider/metadata/console/planner/runtime normal and error cases | WORKING WITH LIMITATIONS | 1814 tests.ai cases plus AI top-level suites | Predominantly mocked; no live cloud/local model completion |
| AI | Investigation session durability | PARTIAL | ai/session_store.py _sessions dict and create/get implementation | Process-local; restart/multi-worker durability absent in this store |
| AI | Approval replay, durable approvals, budget/cancellation guarantees | UNTESTED | No sufficient end-to-end reproduction | Cannot certify safe unattended mutations |
| Admin | Auth/permissions/CRUD/widgets/relations/advanced fields | WORKING WITH LIMITATIONS | 136 Admin passes; minimum-version full suite green | 6 route-introspection test failures on newer dependencies; not proof all HTTP Admin operations fail |
| Studio | Route inventory/AI context | BROKEN | 3 Studio assertion failures on newest dependencies | Routes/tools missing from metadata; newer-dependency launch-check false negative |
| Studio | Development UI/authentication | WORKING WITH LIMITATIONS | 1141 initial Studio passes; minimum suite green; verify_studio_auth | Production exposure not approved by this audit; no browser-driven session |
| CLI | 117 root/group/subcommand help nodes | VERIFIED WORKING | cli-smoke.json, all exit 0 | Help only |
| CLI | Scaffolding/migrations/diagnostics/AI/SDK commands | WORKING WITH LIMITATIONS | 466 tests.cli, 105 patterns tests plus top-level CLI regressions | Not every command executed against a live generated app |
| Doctor | Production checks | WORKING WITH LIMITATIONS | exit 0 with status warn; 305 diagnostics passes | Broad AI writability and missing optional security matrix are warnings |
| Tasks | Queue/retry/results/recurrence/context | WORKING WITH LIMITATIONS | 23 task tests, 6 durable-workflow tests | Worker kill/recovery, duplicates, exactly-once external effects unverified |
| Cache | General configurable cache backend/Redis contract | UNKNOWN | No public general cache export located in initial targeted search | Internal caches do not establish a shipped application cache API |
| Media | Storage contracts and local paths | WORKING WITH LIMITATIONS | 4 storage tests plus advanced/security tests | 2 mounting-introspection failures on newer dependencies; S3 not live-tested |
| SDK | Generation/type mapping | WORKING WITH LIMITATIONS | SDK/codegen cases exercised in suite | Independent TypeScript compilation and generated-client requests not performed |
| Examples | Bundled validation | WORKING WITH LIMITATIONS | examples.json: 63 OK/2 skipped; full minimum suite | Newest dependencies fail first-app route/launch checks; not all apps served |
| Benchmarks | Tiny correctness smoke | VERIFIED WORKING | 52 rows pass; tests.benchmarks 19 pass | No comparative ranking, soak or production-load claim |

# Architecture Map

Status is scoped to the evidence above; no subsystem earns unconditional STABLE from test volume alone.

| Subsystem | Main implementation | Classification / evidence |
| --- | --- | --- |
| Application bootstrap | aksara/app.py | FUNCTIONAL BUT EVOLVING; app tests |
| Configuration | aksara/conf.py | FUNCTIONAL BUT EVOLVING; DX tests |
| ORM | aksara/model/base.py; aksara/manager.py | FUNCTIONAL BUT EVOLVING; ORM and benchmark tests |
| Fields | aksara/fields.py | FUNCTIONAL BUT EVOLVING; advanced policy branch |
| Query engine | aksara/db/expressions.py; aksara/manager.py | FUNCTIONAL BUT EVOLVING |
| Relations | aksara/relations.py; aksara/fields.py | PARTIAL; through unsupported |
| Transactions | aksara/db/transaction.py; session.py | BROKEN setup cleanup |
| Migrations | aksara/migrations/ | FUNCTIONAL BUT EVOLVING; 452 tests |
| ViewSets | aksara/api/ | FUNCTIONAL BUT EVOLVING; route compatibility failure |
| Serializers | aksara/api/serializers.py | FUNCTIONAL BUT EVOLVING |
| Auth | aksara/contrib/auth/ | FUNCTIONAL BUT EVOLVING; auth/security tests |
| Principals | aksara/security/principal.py | FUNCTIONAL BUT EVOLVING |
| Permissions | aksara/permissions.py | FUNCTIONAL BUT EVOLVING |
| PolicyEngine | aksara/security/policy.py | FUNCTIONAL BUT EVOLVING |
| Tenancy/RLS | aksara/tenancy.py; aksara/db/tenant_context.py | PARTIAL validation; privileged DB role |
| MCP | aksara/security/mcp.py; aksara/ai/ | FUNCTIONAL BUT EVOLVING |
| AI metadata | aksara/ai/registry.py; aksara/ai/context.py | FUNCTIONAL BUT EVOLVING |
| Providers | aksara/ai/providers.py; providers_unified.py; connectors/ | EXPERIMENTAL live-service validation |
| Agent/runtime/planner | aksara/ai/agent.py; runtime.py; planner.py | EXPERIMENTAL |
| Approval workflows | aksara/ai/; aksara/security/ | UNKNOWN durable execution semantics |
| Studio | aksara/studio/ | EXPERIMENTAL; route inventory broken with newest deps |
| Admin | aksara/contrib/admin/ | FUNCTIONAL BUT EVOLVING |
| CLI | aksara/cli/main.py | FUNCTIONAL BUT EVOLVING; 117 help nodes |
| Doctor | aksara/diagnostics.py; aksara/launch_check.py | FUNCTIONAL BUT EVOLVING; warn/exit distinction |
| Tasks/workflows | aksara/tasks.py; aksara/workflows.py | FUNCTIONAL BUT EVOLVING; crash semantics unverified |
| Cache | Internal caches in several modules | UNKNOWN general public subsystem |
| Media | aksara/storage.py | FUNCTIONAL BUT EVOLVING |
| SDK | aksara/sdk/typescript.py | FUNCTIONAL BUT EVOLVING |
| Benchmarks | benchmarks/runner.py and implementations/ | FUNCTIONAL BUT EVOLVING; new branch rewrite |

# Cross-Path Consistency Findings

1. **Confirmed setup cleanup inconsistency:** `Database.acquire()` uses the pool acquisition context manager, while `session_context.__aenter__` and `TransactionManager.__aenter__` manually acquire before fallible setup. Injected tenant setup failure releases zero of one acquired connections in both manual paths. Injected transaction start failure additionally leaves `get_session()` pointing to that connection. Source: `aksara/db/session.py:83`, `aksara/db/transaction.py:41`; reproduction saved with output.
2. Advanced field/write regression tests pass on this branch: JSON scalars, nonfinite rejection, Vector handling and File/Image boundaries are covered by 48 advanced-policy cases. This does not demonstrate every API/Admin/MCP/SDK combination.
3. New dependency route wrappers break inspection paths although many HTTP request tests pass. `launch_check._route_paths` only reads a direct `path` attribute; metadata may miss included routes. Do not misreport the 11 AttributeErrors in tests as proof that every corresponding HTTP route is unreachable.
4. Full new cross-surface equivalence matrices for timestamps, audit records, permissions and errors were not authored. Those combinations remain UNTESTED beyond existing regression assertions.

# Feature Interaction Findings

- Confirmed: newer allowed FastAPI/Starlette + Studio route discovery => missing Studio routes and empty exported AI tools.
- Confirmed: newer dependencies + first-app launch checker => expected Studio UI check missing.
- Confirmed: tenant setup error + session/transaction acquisition => leaked connection; transaction start error + ContextVar => stale session binding.
- Existing relation/transaction/bulk/advanced-field interaction tests and benchmark smoke pass.
- Tenant+MCP/Admin/tasks/agent restricted-role deployment, approval+retry races, SDK+advanced fields, and file+remote-storage combinations were not independently exercised end to end. Preserve these as validation gaps rather than invented vulnerabilities.

# Security Findings

**S1 — RLS evidence limitation (P1):** the requested database role is superuser/BYPASSRLS. Successful tenant tests do not demonstrate database-enforced isolation with an application role. Add a restricted-role validation job before making that guarantee. This is a test/deployment gap, not evidence that PostgreSQL RLS is broken.

**S2 — Incomplete OpenAPI fuzz contract (P1):** `tests/security/fuzz/test_openapi_fuzz.py` is a skipped skeleton, including the forbidden-field mutation invariant. A normal suite pass does not cover these advertised attack paths. Smallest remedy: an actual generated CRUD app and meaningful fuzz/property assertions, with a required job if claimed as a release gate.

**S3 — Advisory production diagnostics:** the CI-shaped production check returns warn for broad `ai_agent_writable=True` defaults and an absent optional security matrix while exiting 0. This behavior is explicit, but a release operator must not translate exit 0 into full security approval. Whether public AI write defaults should change requires a compatibility decision.

Bandit at the high threshold and installed-dependency audit passed. This does not establish absence of SSRF, credential leaks, SQL injection, authorization bypass or vulnerable transitive deployments. No such exploit is asserted without reproduction.

# Operational / Production Findings

**O1 — Failed-start resource safety (P0):** unreleased pooled connections can exhaust a long-running process after repeated tenant setup or transaction start errors. A stale ContextVar may route later work through an invalid connection. Repair acquisition/setup cleanup with exception-safe unwinding; also test reset failure and cancellation without hiding the original exception.

**O2 — Allowed dependency compatibility (P0):** a normal editable install resolves web dependencies that yield 15 failures. Pinning compatible versions is a temporary release mitigation; the durable fix is supported route traversal and a minimum/latest compatible dependency CI matrix. Both FastAPI and Starlette changed in the comparison, so causality is assigned to the pair, not uniquely to one package.

**O3 — Development state is not durable state:** investigation sessions are held in the process-local `_sessions` dict. Persist them only if durable multi-worker AI investigations are part of the v0.6 promise; otherwise explicitly keep this surface development-only/experimental.

Pool acquisition timeouts, shutdown deadlines, server restart recovery, cancellation, worker crashes and duplicate task side effects were not load/fault tested. `Database.disconnect()` awaits pool.close without an explicit local deadline; this source observation warrants a focused shutdown probe, not an unsupported assertion of unavoidable hangs.

Migration advisory locking and integrity checks already exist. Do not add duplicate mechanisms from a generic production checklist.

# Historical Bug Status

Old `orm-audit/summary.md` was consulted only as a list of hypotheses. Its counts are not reused as current results.

| Historical issue | Current assessment | Evidence / boundary |
| --- | --- | --- |
| Primitive bool/integer/decimal coercion | FIXED for exercised cases | Primitive field tests pass; v0.5.51 implementation anchor |
| NULL/query isnull/FK alias semantics | FIXED for exercised cases | Query/relation regressions and read benchmark pass; v0.5.53 anchor |
| bulk preparation/timestamps/defaults | FIXED for exercised cases | Write regressions and bulk benchmark; not every extension hook |
| Array item/nesting and Vector policy | FIXED for exercised branch cases | Advanced policy + Array tests; current branch only |
| JSON scalar behavior | FIXED for exercised branch cases | Advanced-policy scalar round trips |
| File/Image wrapper contract | FIXED for exercised branch cases | Advanced policy tests; uploads have intentional path restrictions |
| Forward FK returns ID | INTENTIONALLY DEFERRED object-loading feature | Documented ID access contract; not inherently a defect |
| Reverse FK filtering | FIXED for exercised cases | Relation/query regression suites |
| Unsafe on_delete / invalid SET NULL | FIXED for exercised cases | ForeignKey calls normalize_on_delete; regression suite |
| Custom M2M through | INTENTIONALLY DEFERRED | Explicit constructor ValueError |
| Migration metadata/order | FIXED for exercised cases | 452 migration tests; historical upgrade replay not done |
| Commit/rollback/nested transactions | PARTIALLY FIXED | Happy paths pass; setup cleanup reproduction remains OPEN |
| Broad concurrency correctness | UNKNOWN beyond smoke | 12 concurrency benchmark cases; no soak/deadlock/restart proof |

# v0.5.55 Investigation

**Recommendation: SPLIT INTO MULTIPLE CHANGES.** Keep Advanced Field Policy correctness and its documentation/tests as one reviewed change; isolate the large benchmark replacement as a separate change. This reduces review scope and avoids implying that performance tooling is required to fix field semantics.

Local branch is 5 ahead/0 behind main; 64 changed files. `tests/test_advanced_field_policy.py` currently passes 48 tests against local PostgreSQL with pgvector. Array adds 40 passing tests. Changes touch serializers, Admin coercion, database vector encoding, expressions and migration operations, so they are cross-surface contracts, not merely a new field helper.

Backward compatibility: stricter invalid-value rejection may break callers that relied on permissive behavior. Document accepted scalar/nested/null/upload behavior. Package remains 0.5.54 while branch docs describe upcoming work; no v0.5.55 tag was found locally.

Actual GitHub CI history, unresolved review comments, current mergeability and remote changes are BLOCKED by unauthenticated CLI. Commit messages mentioning closed review comments are not evidence that GitHub reviews are resolved. Main does not contain these five commits in the local snapshot; independently superseded behavior beyond ancestry was not fully checked. Historical defects were not replayed in a separate main worktree; recommendation is conditional on that remaining review, not MERGE AS-IS.

# Benchmark Findings

Current harness offers Aksara, asyncpg and SQLAlchemy implementations; smoke/correctness/performance/soak modes; deterministic profiles; concurrency and separate workloads. The executed Aksara tiny smoke covered single_ops 7, bulk_writes 5, read_queries 13, relationships 7, concurrency 12, transactions 7, migrations 1: **52 pass**. Harness tests: 19 pass.

Only Aksara at concurrency 1 and 5 was executed. No cross-framework rankings, large datasets, sustained memory growth, database connection saturation or historical performance comparisons were measured. The saved JSON/CSV/Markdown contain per-case measurements. Single-iteration smoke timings must not be used for performance claims. Setup/teardown contamination and metrics methodology were not exhaustively independently audited.

# Documentation vs Reality

- CONTRIBUTING asks for pytest, Ruff and mypy to pass. Current Ruff/mypy do not meet that contract.
- `pyproject.toml` permits newer web dependencies that break route metadata/launch checks; installability is broader than verified compatibility.
- The roadmap still lists advanced Array/Vector/File/JSON policy as future work; the current feature branch implements and tests substantial parts. Update upon release, retaining historical version context.
- The roadmap explicitly does not claim production readiness for v0.5.54. This aligns better with evidence than a v0.6 Production Mode label.
- Example validator says ready (63 OK) while newer-dependency first-app tests fail. Its output is a limited check, not a live application guarantee.
- Strict docs build passing proves rendering/navigation consistency, not behavioral accuracy.
- OpenAPI fuzz placeholders are not active fuzz coverage.
- PyPI metadata and current public release were not compared live.

# Broken Features

- Session/transaction failed-start cleanup: independently reproduced.
- Newer permitted web dependency route introspection/Studio AI context/launch-check behavior: 15 failing cases, eliminated with minimum versions.
- Ruff/typecheck developer gate: failing, though each finding is not necessarily a runtime bug.

# Partial Features

- Custom M2M through models: explicitly unsupported.
- Investigation sessions: process-local persistence only.
- SDK/provider/remote media support: existing unit coverage does not establish external interoperability.
- Production diagnostic exit status: advisory warnings remain even on exit 0.

# Untested / Unverifiable Features

Live cloud and Ollama providers; external MCP client transport; remote storage/email; browser UI flows; independently compiled/generated TypeScript clients; complete example serving; old-schema upgrade chain; restricted-role RLS; restart/deadlock/cancellation fault matrix; task kill/recovery; durable approval races; every cross-path combination. These were not proven broken and were not promoted to VERIFIED WORKING.

# Obvious Missing Capabilities

Evidence supports missing **failure-safe acquisition cleanup**, **an enforced web-dependency compatibility boundary**, **non-placeholder OpenAPI attack validation**, and **a release decision that cannot confuse advisory checks with completed security approval**. Restricted-role isolation validation is also missing from this run. Durable investigation storage is missing in the specific process-local store, but can be deferred if scoped out of production guarantees.

No blanket requirements for Redis, a general cache API, Django parity, custom-through support, or cloud AI are introduced.

# v0.6.0 Gap Analysis

## P0 — Blocks v0.6.0

| Item | What fails / type | Smallest correct implementation | Validation | API / compatibility |
| --- | --- | --- | --- | --- |
| Failed-start cleanup | Pool exhaustion and stale session; correctness/operations bug | Unwind every acquired resource and ContextVar when setup/start/reset fails | Inject setup/start/reset failure and cancellation; verify pool capacity/session restored; real pool test | No public API change expected |
| Supported web dependency boundary | Ordinary allowed install yields 15 failures; compatibility bug | Temporarily constrain to tested pair, then implement supported included-route traversal and CI range checks | Full suite and route/API/Studio/launch contract checks at minimum and maximum supported versions | Constraints affect installers; traversal fix should preserve public metadata contracts |

## P1 — Should land before v0.6.0

| Item | What fails / type | Smallest correct implementation | Validation | API / compatibility |
| --- | --- | --- | --- | --- |
| RLS production-role proof | Superuser tests cannot prove isolation; security validation | Dedicated restricted-role CI fixture and documented role requirements | Attempt cross-tenant reads/writes through ORM/API/MCP/task paths | No required public API change |
| Executable OpenAPI fuzz invariants | Current skeleton always skips; test gap | Generated CRUD app with invalid input and forbidden-field mutation checks | Assert no unsafe mutation/500s and no silent skip in required job | No API change |
| Reproducible developer/release gates | Documented lint/type checks fail; release-engineering gap | Triage errors, fix substantive issues, explicitly baseline legacy style debt; run required checks on release revision | Clean agreed scoped checks; prevent new violations; record exact dependency versions | No broad refactor needed |
| Honest diagnostics/release scope | Exit 0 with warnings may be treated as full approval; operational/docs gap | Explicit production release policy for warn/fail and required security matrix where promised | Test unsafe and safe deployments, assert intended exit/report behavior | Changing default failures may require migration guidance |
| Stable/experimental contract | Local AI state and unverified surfaces cannot support broad production claims; docs requirement | Publish narrow supported surface and list experimental capabilities with limits | Link every claimed guarantee to an executed check | Avoid falsely promising durable sessions |

## P2 — Safe for v0.6.x

Custom M2M through support, optional cache services, broader provider integrations, full comparative performance work, and expanded SDK ergonomics can follow the core reliability release when documented as outside current guarantees. No speculative item is elevated to a blocker solely for feature parity.

## Intentionally Experimental

Investigation console/session memory, planner-generated code/test suggestions, live optional AI connectors not validated here, and production exposure of Studio. If durable autonomous AI execution becomes a v0.6 production promise, durability/approval/retry/tenant proofs must move ahead of that promise.

# Recommended Next Release

Prepare a narrowly scoped **v0.5.55 correctness release**: reviewed Advanced Field Policy contracts/tests/docs, failed-start resource cleanup, and a tested dependency compatibility boundary. Split benchmark overhaul for independent review. Do not publish until current review/CI state is inspected and the exact release revision passes required checks. Avoid adding AI memory or unrelated features to this release.

# Recommended Sequence to v0.6.0

1. Land the two reproduced P0 fixes and reviewed field-policy work with focused regressions; keep benchmark work independently reviewable.
2. Make the supported dependency/runtime matrix reproducible, activate OpenAPI attack checks, and validate tenant isolation with an actual application role. Resolve/baseline static gates explicitly.
3. Exercise one production-shaped reference deployment including restart/shutdown/migration/task recovery; publish only the guarantees that pass. Release an alpha/RC before applying Production Mode.

# Unknowns / Environmental Blockers

- GitHub PR/review/CI and live remote/PyPI state: BLOCKED / not authenticated or not queried.
- Real OpenAI calls: BLOCKED by missing credentials; other external services not provisioned/tested.
- OpenAPI fuzz: implementation placeholder, not merely environment blockage.
- Historical replay, browser examples, SDK compilation, fault/soak matrix and wheel-installed runtime: NOT RUN, not PASS.
- File hydration/cache blockers were resolved for completed runs; interrupted runs are retained as context.
- Source statistics cover tracked files only; benchmark archive and existing untracked app state are not production proof.

# Final Verdict

**NO.** If this checkout were labelled v0.6.0 today, I would not recommend it for an important production backend. The healthy minimum-dependency suite and benchmark smoke demonstrate substantial beta capability. Reproduced resource leakage, an overly broad dependency compatibility promise, and incomplete production-isolation/failure validation prevent a credible Production Mode claim.

Operator summary:

- **Now:** substantial beta; minimum web dependencies pass 7,846 tests, newest allowed pair fails 15.
- **Five biggest risks:** setup connection leaks; stale transaction session context; dependency-driven route/tool metadata failures; privileged-role isolation blind spot; unproven restart/approval/task recovery guarantees.
- **Five obvious misses:** exception-safe acquisition; enforced compatibility matrix; restricted-role security proof; real OpenAPI fuzz invariants; explicit warning-to-release and stable/experimental policy.
- **Next release:** small v0.5.55 correctness patch, field policy reviewed separately from benchmark rewrite.
- **Before v0.6:** fix reproduced failures, enforce supported install constraints, validate production role/failure behavior and publish an evidence-backed scope.
- **Defer:** optional cache integrations, custom-through relations, AI memory/radar, broad provider expansion and comparative performance optimization.
