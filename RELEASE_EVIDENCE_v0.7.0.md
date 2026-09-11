# Aksara v0.7.0 final release evidence

## Recommendation

**READY FOR v0.7.0 RELEASE.**

The exact finalization source commit implements the previously reviewed Durable
Authorized Operations contract with only version, release-documentation, and
version-sensitive test changes from the merged `0.7.0rc1` tree. Local release
gates pass against PostgreSQL with required database tests enabled. Hosted
PostgreSQL 16 and the complete hosted release matrix also pass. No tag, GitHub
release, or PyPI publication has occurred.

## Evaluated release source

| Item | Value |
| --- | --- |
| Release | `v0.7.0` / package version `0.7.0` |
| Finalization source commit | `75310e8f5d058dd652e0dc26ed2713c2493774e1` |
| Base commit | `3de21899e2bc76a495f5b2a3932805a412b6b5b3` |
| Branch | `release/v0.7.0` |
| Local database | PostgreSQL 18.4 database `aksara_test` |
| Supported Python | 3.11 and 3.14 |
| Supported web boundary | FastAPI 0.136.1 / Starlette 1.0.1 through FastAPI 0.141.1 / Starlette 1.6.0 |
| MCP dependency | `mcp>=2.0.0,<2.1.0`; local gates exercised 2.0.0 and 2.0.1 |

Database credentials and complete connection URLs are absent from this evidence.

## Finalization scope

- Promoted package, CLI, scaffold, examples, current docs, and version-sensitive
  tests from `0.7.0rc1` to `0.7.0`.
- Converted the v0.7 changelog and roadmap from candidate wording to final
  release wording and added public release notes.
- Preserved ADR 0001, the stability contract's guarantees and limits, production
  behavior, migrations, public APIs, dependency ranges, and historical RC
  evidence.
- Built a new final wheel and sdist from the finalization source commit. No RC
  distribution or RC digest was reused.

The ADR conformance verdict remains **PROVEN WITH REQUIRED IMPLEMENTATION
CONSTRAINTS**, with no contradictions.

## Exact local validation

| Gate | Environment or scope | Result | Evidence |
| --- | --- | --- | --- |
| Full source regression | Python 3.14.4, latest supported web stack, local PostgreSQL | **PASS:** 8,271 passed, 2 expected provider skips | [`pytest-full.log`](audit-evidence/v070-final/pytest-full.log) |
| Durable operation campaign | Production durable and invariant suites | **PASS:** 258 passed | [`durable-targeted.log`](audit-evidence/v070-final/durable-targeted.log) |
| Invariant prototype | Production-bound v0.7 invariants | **PASS:** 24 passed | [`invariant-prototype.log`](audit-evidence/v070-final/invariant-prototype.log) |
| Minimum web stack | Python 3.11.5; FastAPI 0.136.1; Starlette 1.0.1 | **PASS:** 8,271 passed, 2 skipped | [`matrix-py311-min.log`](audit-evidence/v070-final/matrix-py311-min.log) |
| Latest web stack | Python 3.11.5; FastAPI 0.141.1; Starlette 1.6.0 | **PASS:** 8,271 passed, 2 skipped | [`matrix-py311-latest.log`](audit-evidence/v070-final/matrix-py311-latest.log) |
| Minimum web stack | Python 3.14.4; FastAPI 0.136.1; Starlette 1.0.1 | **PASS:** 8,271 passed, 2 skipped | [`matrix-py314-min.log`](audit-evidence/v070-final/matrix-py314-min.log) |
| Latest web stack | Python 3.14.4; FastAPI 0.141.1; Starlette 1.6.0 | **PASS:** 8,271 passed, 2 skipped | [`matrix-py314-latest.log`](audit-evidence/v070-final/matrix-py314-latest.log) |
| Hosted release matrix | GitHub Actions with PostgreSQL 16 | **PASS:** 21/21 checks on finalization source commit | [`hosted-ci.json`](audit-evidence/v070-final/hosted-ci.json) |
| Installed package | Isolated final wheel, generated app, real PostgreSQL, official MCP client | **PASS:** 15 checks | [`installed-package-gate.json`](audit-evidence/v070-final/installed-package-gate.json) |
| Packaged Support Desk | Wheel-only app, restricted role, RLS, REST/MCP/durable operation journeys | **PASS:** 66 checks | [`support-desk-gate.json`](audit-evidence/v070-final/support-desk-gate.json) |
| Performance sanity | 256 Operations, 8 workers, 3,000 terminal-noise rows, reclaim/task/prune checks | **PASS:** all 7 invariants | [`performance-sanity.json`](audit-evidence/v070-final/performance-sanity.json) |
| Security suite | Repository security tests | **PASS:** 429 passed | [`security.log`](audit-evidence/v070-final/security.log) |
| Fuzz suite | Generated API fuzz suite | **PASS:** 165 passed | [`fuzz.log`](audit-evidence/v070-final/fuzz.log) |
| Diagnostics | Diagnostic contract tests | **PASS:** 314 passed | [`diagnostics.log`](audit-evidence/v070-final/diagnostics.log) |
| Migration suite | Fresh, upgrade, checksum, idempotency, and v0.7 durable schema contracts | **PASS:** 455 passed | [`migrations.log`](audit-evidence/v070-final/migrations.log) |
| Static ratchet | Python 3.11.5; Ruff 0.16.6 and mypy 2.3.1 | **PASS:** Ruff 7,208 <= 7,218; mypy 465 <= 501 | [`static-analysis.log`](audit-evidence/v070-final/static-analysis.log) |
| Doctor release policy | Production release configuration | **PASS:** 12 checks; no warnings, failures, or blocks | [`doctor-release.json`](audit-evidence/v070-final/doctor-release.json) |
| Documentation contract | Focused docs/package assertions | **PASS:** 114 passed | [`docs-contract.log`](audit-evidence/v070-final/docs-contract.log) |
| Documentation build | MkDocs strict mode | **PASS** | [`docs-strict.log`](audit-evidence/v070-final/docs-strict.log) |
| Bandit | Production source, high-severity gate | **PASS:** no high-severity findings | [`bandit.log`](audit-evidence/v070-final/bandit.log) |
| Dependency audit | Final dependency graph | **PASS:** no known vulnerabilities | [`pip-audit.log`](audit-evidence/v070-final/pip-audit.log) |
| Secret scan | Exact tracked finalization source snapshot | **PASS:** no leaks | [`gitleaks.log`](audit-evidence/v070-final/gitleaks.log), [`gitleaks.sarif`](audit-evidence/v070-final/gitleaks.sarif) |
| Package validation | Final sdist, wheel-from-sdist, Twine | **PASS** | [`package-build.log`](audit-evidence/v070-final/package-build.log), [`twine.log`](audit-evidence/v070-final/twine.log) |
| SBOM | Validated CycloneDX 1.6 from a clean installed-wheel environment | **PASS:** 46 components | [`sbom.json`](audit-evidence/v070-final/sbom.json), [`sbom.log`](audit-evidence/v070-final/sbom.log) |

The four full matrix cells emitted 25 known deprecation warnings from
Starlette's AnyIO portal alias and Click's `isolated_filesystem` helper. They
produced no failures.

Package digests:

| Artifact | SHA-256 |
| --- | --- |
| `aksara_framework-0.7.0-py3-none-any.whl` | `b5ceaafb547bdf095011a2ab10138c5e596a012143dd25ae7b482ff164f7816e` |
| `aksara_framework-0.7.0.tar.gz` | `b52895d0b5f4443be6801f43d265d6520544ea1a3012edd1b7dac8d1379e34be` |

The machine-readable rollup is
[`release-summary.json`](audit-evidence/v070-final/release-summary.json), and
the environment record is
[`environment.json`](audit-evidence/v070-final/environment.json). Evidence and
distribution digests are sealed in
[`artifact-manifest.sha256`](audit-evidence/v070-final/artifact-manifest.sha256).

## Compatibility and limits

Durable Operations remain additive and opt-in. Existing v0.6 ORM, migration,
synchronous REST/MCP, identity, permission, tenant, task, CLI, and diagnostic
contracts remain in force. PostgreSQL is the only mandatory durability service.

The guarded atomic guarantee covers supported same-database Aksara mutations;
it does not cover arbitrary network, subprocess, thread, independent-database,
or provider effects. Cancellation is not undo. Approval never restores revoked
authority. Exactly-once external effects and cross-system atomic transactions
are not provided.

Protocol-level MCP Tasks remain deferred because the supported official Python
SDK does not implement the current Tasks extension. Planner quality, persistent
AI sessions and memory, multi-agent/autonomous workflows, provider quality,
Studio AI internals, generic workflow/DAG composition, application approval UX,
and long-term compliance retention remain experimental, application-owned, or
deferred.
