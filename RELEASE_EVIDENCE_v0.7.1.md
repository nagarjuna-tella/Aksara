# Aksara v0.7.1 final release evidence

## Recommendation

**READY FOR v0.7.1 RELEASE.**

The exact reviewed and merged `0.7.1rc1` documentation/DX candidate is promoted
to package version `0.7.1`. All local release gates pass against fresh final
artifacts. All 21 hosted checks on the finalization PR's validated evidence head
pass, including PostgreSQL 16. No tag, GitHub Release, or PyPI publication has
occurred.

## Evaluated release source

| Item | Value |
| --- | --- |
| Release | `v0.7.1` / package version `0.7.1` |
| Finalization source commit | `e2ef47dd32a67229a55e2f0e2047d196ec2071e9` |
| Merged candidate base | `c84c1a3a40c4f7868ce536b242ac537f87f5db9c` |
| Branch | `release/v0.7.1` |
| Local database | PostgreSQL 18.4 database `aksara_test` |
| Supported Python | 3.11 and 3.14 |
| Supported web boundary | FastAPI 0.136.1 / Starlette 1.0.1 through FastAPI 0.141.1 / Starlette 1.6.0 |
| MCP dependency | `mcp>=2.0.0,<2.1.0`; local gates exercised 2.0.1 |

Database credentials and complete connection URLs are absent from this evidence.

## Finalization scope

- Promoted package, CLI, scaffold, examples, current docs, and version-sensitive
  tests from `0.7.1rc1` to `0.7.1`.
- Converted current candidate wording to **Aksara v0.7.1 — Documentation &
  Developer Experience** and added final public release notes.
- Preserved historical RC evidence and the public audit's chronological record.
- Rebuilt the final wheel and sdist; no RC distribution or RC hash was reused.
- Preserved all 22 disclosed functional findings without changing production
  behavior, dependencies, schema, migrations, security policy, or public APIs.

The semantic scope guard compares this tree with released v0.7.0 and with the
merged v0.7.1 candidate. It reports `runtime_logic_changed: false` and
`dependencies_changed: false`. The v0.7.0 tag tree equals its corresponding
mainline release tree even though the signed release branch and mainline merge
have different commit identities.

## Exact local validation

| Gate | Environment or scope | Result | Evidence |
| --- | --- | --- | --- |
| Full source regression | Python 3.14.4, latest supported web stack, required local PostgreSQL | **PASS:** 8,389 passed, 2 expected provider skips | [`pytest-full.log`](audit-evidence/v071-final/pytest-full.log) |
| Python 3.11 minimum | FastAPI 0.136.1 / Starlette 1.0.1 | **PASS:** 8,389 passed, 2 skipped | [`record`](audit-evidence/v071-final/matrix-py311-minimum.json), [`log`](audit-evidence/v071-final/matrix-py311-minimum.log) |
| Python 3.11 latest | FastAPI 0.141.1 / Starlette 1.6.0 | **PASS:** 8,389 passed, 2 skipped | [`record`](audit-evidence/v071-final/matrix-py311-latest.json), [`log`](audit-evidence/v071-final/matrix-py311-latest.log) |
| Python 3.14 minimum | FastAPI 0.136.1 / Starlette 1.0.1 | **PASS:** 8,389 passed, 2 skipped | [`record`](audit-evidence/v071-final/matrix-py314-minimum.json), [`log`](audit-evidence/v071-final/matrix-py314-minimum.log) |
| Python 3.14 latest | FastAPI 0.141.1 / Starlette 1.6.0 | **PASS:** 8,389 passed, 2 skipped | [`record`](audit-evidence/v071-final/matrix-py314-latest.json), [`log`](audit-evidence/v071-final/matrix-py314-latest.log) |
| Hosted release matrix | GitHub Actions with PostgreSQL 16 | **PASS:** 21/21 checks on `6a2a4a08708fb9d82baa67143875f4121a3f63d4` | [`hosted-ci.json`](audit-evidence/v071-final/hosted-ci.json) |
| Durable operation campaign | Durable and production-bound invariant suites | **PASS:** 258 passed | [`durable-targeted.log`](audit-evidence/v071-final/durable-targeted.log) |
| Invariant prototype | Production-bound v0.7 invariants | **PASS:** 24 passed | [`invariant-prototype.log`](audit-evidence/v071-final/invariant-prototype.log) |
| MCP | Protocol, lifecycle, schema, credential, and diagnostic boundary tests | **PASS:** 68 passed | [`mcp-targeted.log`](audit-evidence/v071-final/mcp-targeted.log) |
| Task compatibility | Ordinary tasks and durable task integration | **PASS:** 40 passed | [`task-targeted.log`](audit-evidence/v071-final/task-targeted.log) |
| RLS and tenancy | Tenant isolation, restricted role, and v0.4.5 tenancy contracts | **PASS:** 21 passed | [`rls-targeted.log`](audit-evidence/v071-final/rls-targeted.log) |
| Security suite | Repository security tests, including fuzz | **PASS:** 429 passed | [`security.log`](audit-evidence/v071-final/security.log) |
| Fuzz suite | Generated API fuzz suite rerun independently | **PASS:** 165 passed | [`fuzz.log`](audit-evidence/v071-final/fuzz.log) |
| Diagnostics | Diagnostic contract tests | **PASS:** 314 passed | [`diagnostics.log`](audit-evidence/v071-final/diagnostics.log) |
| Migrations | Fresh, upgrade, checksum, idempotency, and durable schema tests | **PASS:** 455 passed | [`migrations.log`](audit-evidence/v071-final/migrations.log) |
| Doctor release policy | Final installed package with production release configuration | **PASS:** 12 checks, no warnings or failures | [`doctor-release.json`](audit-evidence/v071-final/doctor-release.json) |
| Static ratchet | Python 3.11.15; Ruff 0.16.6 and mypy 2.3.1 | **PASS:** Ruff 7,207 <= 7,218; mypy 465 <= 501 | [`static-analysis.log`](audit-evidence/v071-final/static-analysis.log) |
| Bandit | Production source, high-severity gate | **PASS:** no high-severity findings | [`bandit.log`](audit-evidence/v071-final/bandit.log) |
| Dependency audit | Final dependency graph | **PASS:** no known vulnerabilities | [`pip-audit.log`](audit-evidence/v071-final/pip-audit.log) |
| Secret scan | Exact intended finalization tree | **PASS:** Gitleaks 8.28.0 scanned 13.30 MB with no leaks found | `audit-evidence/v071-final/gitleaks.log` and `.sarif` |
| Package validation | Fresh sdist, wheel from sdist, and Twine | **PASS** | [`package-build.log`](audit-evidence/v071-final/package-build.log), [`twine.log`](audit-evidence/v071-final/twine.log) |
| Installed package | Isolated final wheel, generated app, PostgreSQL, official MCP client | **PASS:** 15 checks | [`installed-package-gate.json`](audit-evidence/v071-final/installed-package-gate.json) |
| Packaged Support Desk | Wheel-only app, restricted role, RLS, REST/MCP/durable journeys | **PASS:** 66 checks | [`support-desk-gate.json`](audit-evidence/v071-final/support-desk-gate.json) |
| Performance sanity | 256 Operations, 8 workers, 3,000 terminal-noise rows | **PASS:** all 7 invariants | [`performance-sanity.json`](audit-evidence/v071-final/performance-sanity.json) |
| Documentation contract | Focused documentation assertions | **PASS:** 123 passed | [`docs-contract.log`](audit-evidence/v071-final/docs-contract.log) |
| Documentation build | MkDocs strict mode, 162 rendered pages | **PASS** | [`docs-strict.log`](audit-evidence/v071-final/docs-strict.log) |
| Runtime/no-functional-change scope | v0.7.0 and merged v0.7.1rc1 comparisons | **PASS:** no runtime logic or dependency change | [`runtime-scope.json`](audit-evidence/v071-final/runtime-scope.json) |

The four full matrix cells emitted 25 known deprecation warnings from
Starlette's AnyIO portal alias and Click's `isolated_filesystem` helper. They
produced no failures.

## Documentation and developer-experience gates

- All 348 current Python fences compile and import from the final wheel; all 15
  current JSON fences parse, and five selected JSON objects validate against
  installed response models.
- All 295 literal CLI forms parse, with seven explicit non-command exclusions.
- Five retained examples start from the final wheel and preserve their expected
  access boundaries.
- The six-stage Ticket Desk tutorial passes 86 public API assertions.
- The final scaffold passes five startup checks; generated output preserves the
  reviewed defaults and differs from public v0.7.0 only in README guidance after
  version and secret normalization.
- Strict MkDocs renders 162 pages. All 42,322 local links/assets and all 41
  selected external documentation links pass.

Current detailed public-truth records are under [`audit-evidence/v071/`](audit-evidence/v071/).
Final release-gate records are under [`audit-evidence/v071-final/`](audit-evidence/v071-final/).

## Package artifacts

| Artifact | SHA-256 |
| --- | --- |
| `aksara_framework-0.7.1-py3-none-any.whl` | `42a3a42be08ee5be1075d4f6da3b22fea6acaa5bf678a57db7ecc00ce4fdd197` |
| `aksara_framework-0.7.1.tar.gz` | `d3ce8e4b8c735bfcf61b41f2df90c7cc7a448722e8329b7f074bb9840653cb94` |

Twine validates both artifacts. A fresh, isolated Python 3.11 environment
produced a validated CycloneDX 1.6 SBOM containing 74 components:
[`sbom.json`](audit-evidence/v071-final/sbom.json) and
[`sbom.log`](audit-evidence/v071-final/sbom.log).

## Disclosed functional findings

The audit retains all 22 functional findings, and this release fixes none of
them. The disclosed boundaries include ordinary task stale-lock behavior,
TypeScript SDK strict compilation, generated-project editable installation,
AI workflow import behavior, relation inconsistencies, pagination, fixtures,
storage, migration/model discovery, testing helpers, configuration parsing, and
the other entries in [`AKSARA_V071_PUBLIC_TRUTH_AUDIT.md`](AKSARA_V071_PUBLIC_TRUTH_AUDIT.md).
The final full regression and package gates found no evidence that these already
disclosed findings make the reviewed documentation/DX release unsafe to publish.

## Publication state

As of this evidence run, `v0.7.1` is absent locally and remotely, GitHub has no
`v0.7.1` Release, and PyPI serves `0.7.0` as latest while the `0.7.1` JSON
endpoint returns 404. Publication remains unauthorized. Human review and merge
of the finalization PR are required before the merged-tree safety checkpoint;
tagging and publication additionally require explicit authorization.
