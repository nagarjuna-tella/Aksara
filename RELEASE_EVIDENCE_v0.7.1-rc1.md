# Aksara v0.7.1-rc1 release evidence

## Recommendation

**READY FOR FINAL PR AND HOSTED VALIDATION.**

The v0.7.1 release candidate is a public-truth, documentation, developer-
experience, and roadmap release. It adds no runtime capability and makes no
intentional production semantic change. The complete local release suite passes
against PostgreSQL with required database tests enabled. Hosted PostgreSQL 16
and human review remain required before any release decision.

No merge, tag, GitHub release, or package publication has occurred.

## Evaluated candidate

| Item | Value |
| --- | --- |
| Release | `v0.7.1-rc1` / package version `0.7.1rc1` |
| Released base | `b7ac75f4b1bd4b262824e828601168336b4ecf7f` (`v0.7.0`) |
| Validated source commit | `b751187d77af0486dda656e3b28d33cfe3efe981` |
| Branch | `codex/v071-public-truth-and-roadmap` |
| Local database | PostgreSQL 18.4 database `aksara_test` |
| Supported Python | 3.11 and 3.14 |
| Supported web boundary | FastAPI 0.136.1 / Starlette 1.0.1 through FastAPI 0.141.1 / Starlette 1.6.0 |
| Hosted PostgreSQL 16 | Pending the final pull request |

Database credentials and complete connection URLs are absent from committed
evidence.

## Release scope

- Rebuilt onboarding, the user manual, configuration and production guidance,
  Durable Operations guidance, examples, scaffold instructions, upgrade advice,
  and stable/experimental labeling around current v0.7 behavior.
- Added a complete public sample census and executable evidence for current
  Python, JSON, CLI, example, scaffold, tutorial, and packaged-application paths.
- Added the evidence-gated post-v0.7 market and product roadmap without starting
  v0.8 implementation.
- Moved only package/version-facing metadata from `0.7.0` to `0.7.1rc1` after
  the documentation acceptance was complete.

The detailed truth audit records 80 corrected documentation contradictions and
22 disclosed functional findings. The implementation of those findings is
outside this release.

## No-functional-change assessment

The semantic scope guard compares the candidate with released v0.7.0 and passes.
The only production-source or package-metadata changes are:

| File | Classification |
| --- | --- |
| `aksara/_version.py` | Candidate version declaration only |
| `aksara/cli/main.py` | Existing CLI docstrings, help, bullets, and next-step text only |
| `aksara/cli/scaffold.py` | Generated README instructions, candidate labels, and candidate dependency floor only |
| `aksara/cli/templates/__init__.py` | Four template description strings only |
| `pyproject.toml` | Candidate project version only; dependency declarations unchanged |

The guard reports `runtime_logic_changed: false` and
`dependencies_changed: false`. Generated-project comparison covers all 18 files;
after exact release-version and generated-token normalization, only README
guidance differs from the released wheel. The candidate startup gate retains a
raw generated README digest for direct comparison.

Evidence: [runtime scope](audit-evidence/v071-rc1/runtime-scope.json),
[startproject guidance](audit-evidence/v071/startproject-guidance.json), and
[scaffold equivalence](audit-evidence/v071/scaffold-wheel-equivalence.json).

## Local release gates

| Gate | Environment or scope | Result | Evidence |
| --- | --- | --- | --- |
| Full source regression | Python 3.14.4, latest supported web stack, required local PostgreSQL | **PASS:** 8,389 passed, 2 expected provider skips | [log](audit-evidence/v071-rc1/matrix-py314-latest.log), [record](audit-evidence/v071-rc1/matrix-py314-latest.json) |
| Minimum web stack | Python 3.11.15; FastAPI 0.136.1; Starlette 1.0.1 | **PASS:** 8,389 passed, 2 skipped | [log](audit-evidence/v071-rc1/matrix-py311-minimum.log), [record](audit-evidence/v071-rc1/matrix-py311-minimum.json) |
| Latest web stack | Python 3.11.15; FastAPI 0.141.1; Starlette 1.6.0 | **PASS:** 8,389 passed, 2 skipped | [log](audit-evidence/v071-rc1/matrix-py311-latest.log), [record](audit-evidence/v071-rc1/matrix-py311-latest.json) |
| Minimum web stack | Python 3.14.4; FastAPI 0.136.1; Starlette 1.0.1 | **PASS:** 8,389 passed, 2 skipped | [log](audit-evidence/v071-rc1/matrix-py314-minimum.log), [record](audit-evidence/v071-rc1/matrix-py314-minimum.json) |
| Latest web stack | Python 3.14.4; FastAPI 0.141.1; Starlette 1.6.0 | **PASS:** 8,389 passed, 2 skipped | [log](audit-evidence/v071-rc1/matrix-py314-latest.log), [record](audit-evidence/v071-rc1/matrix-py314-latest.json) |
| Durable operation campaign | Durable and production-bound invariant suites | **PASS:** 258 passed | [log](audit-evidence/v071-rc1/durable-targeted.log) |
| Invariant prototype | Production-bound v0.7 invariants | **PASS:** 24 passed | [log](audit-evidence/v071-rc1/invariant-prototype.log) |
| MCP | Protocol, lifecycle, schema, credential, and diagnostic boundary tests | **PASS:** 68 passed | [log](audit-evidence/v071-rc1/mcp-targeted.log) |
| Task compatibility | Ordinary tasks and durable task integration | **PASS:** 40 passed | [log](audit-evidence/v071-rc1/task-targeted.log) |
| RLS and tenancy | Tenant isolation, restricted role, and v0.4.5 tenancy contracts | **PASS:** 21 passed | [log](audit-evidence/v071-rc1/rls-targeted.log) |
| Security suite | Repository security tests | **PASS:** 429 passed | [log](audit-evidence/v071-rc1/security.log) |
| Fuzz suite | Generated API fuzz tests | **PASS:** 165 passed | [log](audit-evidence/v071-rc1/fuzz.log) |
| Diagnostics | Diagnostic contract tests | **PASS:** 314 passed | [log](audit-evidence/v071-rc1/diagnostics.log) |
| Migrations | Fresh, upgrade, checksum, idempotency, and durable schema tests | **PASS:** 455 passed | [log](audit-evidence/v071-rc1/migrations.log) |
| Doctor release policy | Installed candidate with production release configuration | **PASS:** 12 checks, no warnings or failures | [record](audit-evidence/v071-rc1/doctor-release.json) |
| Static ratchet | Python 3.11.15; Ruff 0.16.6 and mypy 2.3.1 | **PASS:** Ruff 7,207 <= 7,218; mypy 465 <= 501 | [log](audit-evidence/v071-rc1/static-analysis.log) |
| Bandit | Production source, high-severity gate | **PASS:** no high-severity findings | [log](audit-evidence/v071-rc1/bandit.log) |
| Dependency audit | Candidate dependency graph | **PASS:** no known vulnerabilities | [log](audit-evidence/v071-rc1/pip-audit.log) |
| Secret scan | Exact tracked source; generated evidence digests individually reviewed | **PASS:** no findings after 41 exact false-positive fingerprints | [log](audit-evidence/v071-rc1/gitleaks.log), [SARIF](audit-evidence/v071-rc1/gitleaks.sarif) |
| Package validation | sdist, wheel from sdist, and Twine | **PASS** | [build](audit-evidence/v071-rc1/package-build.log), [Twine](audit-evidence/v071-rc1/twine.log) |
| Installed package | Isolated candidate wheel, generated application, PostgreSQL, official MCP client | **PASS:** 15 checks | [record](audit-evidence/v071-rc1/installed-package-gate.json) |
| Packaged Support Desk | Wheel-only app, restricted role, RLS, REST/MCP/durable journeys | **PASS:** 66 checks | [record](audit-evidence/v071-rc1/support-desk-gate.json) |
| Performance sanity | 256 Operations, 8 workers, 3,000 terminal-noise rows, task/reclaim/prune checks | **PASS:** all 7 invariants | [record](audit-evidence/v071-rc1/performance-sanity.json) |
| Documentation contract | Focused documentation assertions | **PASS:** 123 passed | [log](audit-evidence/v071-rc1/docs-contract.log) |
| Documentation build | MkDocs strict mode, 162 rendered pages | **PASS** | [log](audit-evidence/v071-rc1/docs-strict.log) |
| Rendered links | Local href/src and fragment targets | **PASS:** 42,322 links/assets, zero errors | [record](audit-evidence/v071/rendered-links.json) |
| External links | Selected important live targets | **PASS:** 41 reachable, zero broken or unverified | [record](audit-evidence/v071/external-links.json) |
| Public sample census | 165 current Markdown files and 595 current fences | **PASS:** 348 Python, 15 JSON, 295 CLI forms, 31 evidence artifacts | [record](audit-evidence/v071/snippet-coverage-review.json) |

The four full matrix cells emitted 25 known deprecation warnings from
Starlette's AnyIO portal alias and Click's `isolated_filesystem` helper. They
produced no failures.

## Clean-room documentation and application evidence

- Five copied repository examples start from the candidate wheel, migrations
  apply, health/OpenAPI checks pass, and documented anonymous writes remain
  denied: [example evidence](audit-evidence/v071/example-execution.json).
- The progressive Ticket Desk executes all six tutorial stages and 86 public API
  assertions against the installed candidate: [tutorial evidence](audit-evidence/v071/development-wheel-tutorial.json).
- The fresh scaffold executes exact README setup, migration, Doctor, startup,
  route, shutdown, and schema-cleanup checks: [scaffold evidence](audit-evidence/v071/scaffold-startup.json).
- All 348 current Python fences compile and import from the installed candidate,
  all 15 JSON fences parse, five selected JSON objects validate against installed
  models, and the corrected Agent Workflow block runs in a fresh process:
  [installed snippet evidence](audit-evidence/v071/installed-doc-imports.json).
- All 295 literal CLI forms parse, with seven explicit non-command exclusions:
  [CLI evidence](audit-evidence/v071/cli-docs-syntax.json).

## Package artifacts

| Artifact | SHA-256 |
| --- | --- |
| `aksara_framework-0.7.1rc1-py3-none-any.whl` | `117cb40348c223ca15e2e922bb7f039a501a165034341c167a64bfd513c86fb0` |
| `aksara_framework-0.7.1rc1.tar.gz` | `4a22a7455ab0e074887fcac2e7d65f059dd7798a1838d3d719d97c016014cf0e` |

Twine validates both artifacts. The installed-package and Support Desk gates use
the wheel digest above. A CycloneDX 1.6 SBOM from an isolated Python 3.11
candidate environment contains 96 components: [SBOM](audit-evidence/v071-rc1/sbom.json)
and [generation record](audit-evidence/v071-rc1/sbom.log).

The machine-readable rollup is [release-summary.json](audit-evidence/v071-rc1/release-summary.json),
and the environment record is [environment.json](audit-evidence/v071-rc1/environment.json).

## Disclosed limits

The audit retains all 22 functional findings; this release does not implement
them. In particular, direct first import of `aksara.ai.workflows` remains broken
while the documented `aksara.studio` aggregate import works, workflow diagnostics
can duplicate an `export` prefix for built-in `set_env`, ordinary task stale-lock
recovery can duplicate active work, the generated TypeScript list parameter does
not pass strict compilation, and editable installation of a generated application
remains unsupported. The complete register and evidence boundaries are in
[AKSARA_V071_PUBLIC_TRUTH_AUDIT.md](AKSARA_V071_PUBLIC_TRUTH_AUDIT.md).

Hosted GitHub Actions, including PostgreSQL 16, remain the independent final
environment check. Human review is required. This document authorizes no merge,
tag, release, or publication.
