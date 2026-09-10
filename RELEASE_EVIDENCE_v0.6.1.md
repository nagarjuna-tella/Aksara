# Aksara v0.6.1 release-candidate evidence

## Candidate identity

| Item | Value |
| --- | --- |
| Package | `aksara-framework` |
| Candidate version | `0.6.1` |
| Candidate implementation SHA | `8036b49c0eb5457428f122af8d6273b70cc44dee` |
| Candidate tree | `367a62ce3f82770cab022ef2116067963c3c109c` |
| Base | `origin/main` at `51eb65274059bdc63da98fe4d9a6851d1ba07d4c` |
| Branch | `codex/v061-installed-package-truth` |

The implementation SHA contains the package, documentation, scaffold, tests,
and release-gate workflow represented by the tested wheel. This evidence file
and the machine-readable gate result are committed afterward so that evidence
can name the immutable implementation it validates.

## Scope and result

v0.6.1 is an adoption and trust patch. It aligns public documentation,
generated projects, configuration guidance, endpoint names, package metadata,
and task identity claims with the package developers actually install. It adds
semantic documentation tests and an installed-wheel release gate.

The patch does not introduce an operation ledger, durable attempts,
idempotency, leases, durable approvals, Principal provenance storage, durable
sessions, a new planner/runtime abstraction, provider redesign, new
infrastructure, or another MCP transport. Those remain outside v0.6.1.

## Validation environment

- macOS 26.6.2, arm64
- CPython 3.11.15 and 3.14.4
- PostgreSQL 18.4, local `aksara_test` database
- FastAPI 0.136.1 / Starlette 1.0.1 minimum boundary
- FastAPI 0.141.1 / Starlette 1.6.0 latest-supported boundary
- official MCP Python SDK 2.0.1

Hosted release-gate jobs use PostgreSQL 16 with pgvector and repeat the full
Python/web matrix. Their PR results are independent evidence and are not
claimed by this local file before the branch is pushed.

## Exact validation results

| Gate | Scope | Result |
| --- | --- | --- |
| Full suite | Python 3.11.15, minimum web boundary | **PASS:** 8,010 passed, 2 expected provider skips |
| Full suite | Python 3.11.15, latest web boundary | **PASS:** 8,010 passed, 2 expected provider skips |
| Full suite | Python 3.14.4, minimum web boundary | **PASS:** 8,010 passed, 2 expected provider skips |
| Full suite | Python 3.14.4, latest web boundary | **PASS:** 8,010 passed, 2 expected provider skips |
| Migration regression | migrations plus migration CLI | **PASS:** 461 passed |
| Security | `tests/security/` | **PASS:** 429 passed |
| Fuzz | `tests/security/fuzz/` | **PASS:** 162 passed, 3 expected skips |
| Diagnostics | `tests/diagnostics/` | **PASS:** 314 passed |
| MCP boundary | protocol, credentials, diagnostics, agent auth | **PASS:** 81 passed |
| Documentation contracts | executable/import/semantic checks | **PASS:** 8 passed |
| Public example audit | 1,704 public code blocks | **PASS:** 0 broken or stale classifications |
| Strict documentation | MkDocs strict build | **PASS** |
| Installed-wheel journey | 15 end-to-end checks | **PASS** |
| Doctor release policy | production release profile | **PASS:** 12 passed; 0 warnings, failures, or blocks |
| Static ratchet | reviewed source baseline | **PASS:** Ruff 7,211/7,218; mypy 466/501 |
| Distribution build | sdist plus wheel-from-sdist | **PASS** |
| Twine | both distributions | **PASS** |
| Bandit | package source, high severity | **PASS:** 0 high-severity findings |
| Dependency audit | candidate dependency environment | **PASS:** no known vulnerabilities |
| Gitleaks | exact candidate Git archive | **PASS:** no findings |
| SBOM | CycloneDX 1.6 | **PASS:** 139 components |
| Workflow syntax | all GitHub workflow YAML | **PASS** |

Each full matrix run emitted 25 known deprecation warnings from Click's
`isolated_filesystem` helper and Starlette's AnyIO `BlockingPortal` alias. No
test failed.

## Commands

The full database-required suite was run for each supported dependency pair:

```bash
AKSARA_DATABASE_URL='postgresql://<local-test-server>/aksara_test' \
DATABASE_URL='postgresql://<local-test-server>/aksara_test' \
AKSARA_REQUIRE_DATABASE_TESTS=1 \
python -m pytest --tb=short -q
```

The minimum and latest web boundaries were installed explicitly before their
respective runs:

```bash
python -m pip install 'fastapi==0.136.1' 'starlette==1.0.1'
python -m pip install 'fastapi==0.141.1' 'starlette==1.6.0'
```

Release slices and checks used:

```bash
python -m pytest tests/migrations/ tests/cli/test_migrations_cli.py -q
python -m pytest tests/security/ -q
python -m pytest tests/security/fuzz/ -q
python -m pytest tests/diagnostics/ -q
python -m pytest tests/mcp/ tests/security/test_mcp_credentials.py \
  tests/diagnostics/test_mcp_security_checks.py tests/ai/test_agent_auth.py -q
python -m pytest tests/docs/ -q
mkdocs build --strict --config-file docs/mkdocs.yml
python scripts/check_static_baseline.py
python -m build
twine check dist/*
bandit -r aksara -x tests,.venv,docs --severity-level high --skip B324
pip-audit --desc auto .
cyclonedx-py environment -o sbom.json
```

Doctor used the same production profile as the hosted Release Gate:

```bash
aksara doctor production-check --release --format json
```

## Package artifacts

The distributions were built from the candidate implementation using
`python -m build`; the wheel was built from the generated sdist.

| Artifact | SHA-256 |
| --- | --- |
| `aksara_framework-0.6.1-py3-none-any.whl` | `4efadd612db62c3c19494b467ead427b34ab1ebd938b53f40dd89e94aa4bdb5b` |
| `aksara_framework-0.6.1.tar.gz` | `d2d05e2dc925f6d73e454bd66050c32632c76a44b7f6fd5e0a962fa405ecd443` |

Twine accepted both artifacts. The wheel reported version 0.6.1 from an
isolated virtual environment whose import path did not contain the source
checkout.

## Installed-package proof

[`audit-evidence/v061/installed-package-gate.json`](audit-evidence/v061/installed-package-gate.json)
records the structured result. The gate used only the built wheel for runtime
imports and a disposable PostgreSQL schema. It proved this journey:

```text
wheel install
  -> CLI help/version
  -> startproject
  -> global settings and stable-core defaults
  -> model and migration generation
  -> PostgreSQL migration
  -> generated app and Doctor
  -> OpenAPI and generated REST
  -> /ai/tools/mcp inspection catalog
  -> official MCP client at /mcp/
  -> task_create
  -> persisted row visible through REST
  -> SIGINT shutdown
  -> zero remaining application connections
```

All 15 checks passed. The official client discovered five generated tools and
invoked `task_create` without an MCP error. The resulting row was retrieved
through the generated REST endpoint. Health, OpenAPI, REST list, and catalog
requests returned HTTP 200. Doctor's generated-project launch check inspected
18 areas, had zero errors, and returned `partial` because optional AI and Studio
features remained disabled. Shutdown exited with code 0 and released every
application connection.

## Documentation and public examples

The public audit inventory is
[`audit-evidence/v061/public-example-audit.json`](audit-evidence/v061/public-example-audit.json).
It classified 1,704 fenced blocks: 1,233 executable, 149 conceptual, 204
experimental, and 118 unknown/textual. No block was left classified as broken
or stale. Semantic tests compile public Python fences, resolve Aksara imports,
reject nonexistent AI classes in executable examples, protect the endpoint
distinction, verify generated global configuration, and compare task identity
claims with `TaskRecord` fields.

The public v0.6.0 fresh-install reproduction remains in
[`audit-evidence/v061/installed-package-baseline.md`](audit-evidence/v061/installed-package-baseline.md).
Final v0.6.0 release archaeology is recorded separately in
[`RELEASE_EVIDENCE_v0.6.0.md`](RELEASE_EVIDENCE_v0.6.0.md); it distinguishes
RC2 checks, final-SHA hosted checks, and later PyPI-artifact verification.

## Changes from v0.6.0

- Public quickstarts now teach one installed-package path centered on the ORM,
  migrations, generated REST, server-resolved identity, and official MCP
  client execution.
- `/mcp/` is consistently identified as the Streamable HTTP protocol endpoint;
  `/ai/tools/mcp` is identified as an HTTP JSON inspection catalog.
- `AgentRuntime`, `Planner`, and related aspirational AI examples no longer
  appear as importable stable APIs. Real experimental primitives are named and
  scoped explicitly.
- Background-task documentation now states that `tenant_id` is persisted and
  restored while complete Principal roles/scopes are not.
- Generated projects configure the single global `aksara.conf.settings`
  authority and default MCP, provider-backed AI, and Studio to disabled.
- CLI database options now use the same namespaced-first environment precedence
  as core settings while preserving `DATABASE_URL` compatibility.
- Principal extraction now treats Starlette requests without authentication
  middleware as anonymous instead of allowing `Request.user` to raise before
  normal authorization handling.
- Source/PyPI metadata now describes the async PostgreSQL, generated REST, and
  authorized MCP product directly.
- CI now builds a wheel and repeats the canonical installed-package journey.

## Stable and experimental boundary

The stable v0.6 contract remains the async PostgreSQL ORM and migrations,
generated REST APIs, authentication and server-owned principals, permissions
and `PolicyEngine`, tenant isolation, Admin/core CLI/Doctor production
surfaces, PostgreSQL task mechanics, generated MCP discovery and execution,
execution-time authorization, bounded signed approvals, deterministic audit
events, transactional rollback, structured failures, cancellation, and runtime
limits.

Planner behavior, provider quality/selection, investigation/session shape,
persistent AI state, memory, multi-agent/autonomous workflows, code and patch
generation, and Studio AI internals remain experimental. Process-local replay
protection is not durable cross-worker idempotency. Approval grants are not an
application-level durable approval workflow. Background tasks do not persist a
complete Principal. Custom many-to-many through models, object-valued lazy
forward foreign keys, and a general cache API remain unsupported.

## Remaining release dependency

The branch must pass the hosted GitHub Actions Release Gate, Security CI, and
CodeQL checks after the PR is opened. No tag, package publication, merge, or
v0.7 implementation is authorized by this evidence.
