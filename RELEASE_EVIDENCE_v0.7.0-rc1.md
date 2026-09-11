# Aksara v0.7.0-rc1 release evidence

## Recommendation

**READY FOR FINAL REVIEW.**

The evaluated candidate implements the bounded Durable Authorized Operations
contract defined by ADR 0001 while preserving the stable v0.6 ORM, REST, MCP,
identity, permission, tenant, task, CLI, and diagnostic surfaces. Local release
gates are green against PostgreSQL with required database tests enabled.

Hosted PostgreSQL 16 and the complete hosted release matrix passed for the
candidate implementation. Human approval remains required. Nothing was merged,
tagged, published, or released as part of this validation.

## Evaluated candidate

| Item | Value |
| --- | --- |
| Release | `v0.7.0-rc1` / package version `0.7.0rc1` |
| Candidate implementation commit | `f61ce5cdfffce81d9eced512e9a63226ad86c251` |
| Base commit | `9a09a12f7a200884f09a0262fd23209cd8282e8b` |
| Branch | `codex/v070-durable-authorized-operations` |
| Local database | PostgreSQL 18.4 database `aksara_test` |
| Application database role | Ephemeral `NOSUPERUSER NOBYPASSRLS` role with forced RLS |
| Supported Python | 3.11 and 3.14 |
| Supported web boundary | FastAPI 0.136.1 / Starlette 1.0.1 through FastAPI 0.141.1 / Starlette 1.6.0 |
| MCP dependency | `mcp>=2.0.0,<2.1.0`; local matrix used `mcp==2.0.1` |

Database credentials and complete connection URLs are absent from the evidence.

## Delivered contract

- PostgreSQL stores one authoritative logical Operation and separate physical
  Attempts. Claim, lease, heartbeat, reclaim, and completion writes use database
  time, row locking, and monotonically increasing fences.
- Idempotency binds the application namespace, tenant, stable initiating
  principal, action/version, client key, and normalized semantic input. Exact
  concurrent duplicates resolve one Operation and semantic conflicts fail.
- Stored principal provenance is non-secret and immutable. Current identity,
  tenant, scope, action authorization, and `PolicyEngine` decisions are resolved
  again before supported effects.
- Durable approval decisions bind the exact Operation and decision provenance.
  Cancellation intent, deadlines, eligibility, attempt limits, and backoff
  survive process loss and compete under the authoritative Operation row lock.
- `postgres_atomic` application mutation, Attempt success, Operation success,
  result, transition, and outbox intent share one guarded PostgreSQL transaction.
  Database escape attempts invalidate the boundary.
- External effects declare idempotent, reconcilable at-least-once, or
  nonretryable semantics. Ambiguous unreconcilable outcomes are explicit; no
  external exactly-once claim is made.
- Existing background tasks can optionally project a durable Operation while
  unlinked tasks retain their prior behavior. The REST router is opt-in and
  existing synchronous `/mcp/` tools remain compatible.
- Transition/outbox evidence, retention, tombstones, diagnostics, and bounded
  pruning are implemented without making history replay authoritative.

The detailed decision audit is in
[`AKSARA_V07_ADR_CONFORMANCE.md`](AKSARA_V07_ADR_CONFORMANCE.md). Its verdict is
**PROVEN WITH REQUIRED IMPLEMENTATION CONSTRAINTS**, with no contradictions.

## Exact local validation

| Gate | Environment or scope | Result | Evidence |
| --- | --- | --- | --- |
| Full source regression | Current candidate, local PostgreSQL | **PASS:** 8,250 passed, 2 expected provider skips | [`pytest-full.log`](audit-evidence/v070/pytest-full.log) |
| Durable operation campaign | Production durable and invariant suites | **PASS:** 237 passed | [`durable-targeted.log`](audit-evidence/v070/durable-targeted.log) |
| Minimum web stack | Python 3.11.15; FastAPI 0.136.1; Starlette 1.0.1 | **PASS:** 8,250 passed, 2 skipped | [`matrix-py311-min.log`](audit-evidence/v070/matrix-py311-min.log) |
| Latest web stack | Python 3.11.15; FastAPI 0.141.1; Starlette 1.6.0 | **PASS:** 8,250 passed, 2 skipped | [`matrix-py311-latest.log`](audit-evidence/v070/matrix-py311-latest.log) |
| Minimum web stack | Python 3.14.4; FastAPI 0.136.1; Starlette 1.0.1 | **PASS:** 8,250 passed, 2 skipped | [`matrix-py314-min.log`](audit-evidence/v070/matrix-py314-min.log) |
| Latest web stack | Python 3.14.4; FastAPI 0.141.1; Starlette 1.6.0 | **PASS:** 8,250 passed, 2 skipped | [`matrix-py314-latest.log`](audit-evidence/v070/matrix-py314-latest.log) |
| Hosted release matrix | GitHub Actions with PostgreSQL 16 | **PASS:** 21/21 checks | PR #26 |
| Candidate-bound invariant matrix | 24 prototype invariants on all four supported runtime cells | **PASS:** 24/24 in every cell | [`matrix-current-prototype.log`](audit-evidence/v070/matrix-current-prototype.log) |
| Installed package | Isolated wheel, generated app, real PostgreSQL, official MCP client | **PASS:** 15 checks | [`installed-package-gate.json`](audit-evidence/v070/installed-package-gate.json) |
| Packaged Support Desk | Wheel-only app, restricted role, RLS, REST/MCP/durable operation journeys | **PASS:** 66 checks | [`support-desk-gate.json`](audit-evidence/v070/support-desk-gate.json) |
| Performance sanity | 256 Operations, 8 workers, 3,000 terminal-noise rows, reclaim/task/prune checks | **PASS:** all 7 invariants | [`performance-sanity.json`](audit-evidence/v070/performance-sanity.json) |
| Security suite | Repository security tests | **PASS:** 429 passed | [`security.log`](audit-evidence/v070/security.log) |
| Fuzz suite | Explicit generated API fuzz suite | **PASS:** 165 passed | [`fuzz.log`](audit-evidence/v070/fuzz.log) |
| Diagnostics | Diagnostic contract tests | **PASS:** 314 passed | [`diagnostics.log`](audit-evidence/v070/diagnostics.log) |
| Static ratchet | Python 3.11; pinned Ruff 0.16.6 and mypy 2.3.1 | **PASS:** Ruff 7,208 ≤ 7,218; mypy 465 ≤ 501 | [`static-analysis.log`](audit-evidence/v070/static-analysis.log) |
| Doctor release policy | Production release configuration | **PASS:** 12 checks; no warnings, failures, or blocks | [`doctor-release.json`](audit-evidence/v070/doctor-release.json) |
| Documentation contract | Focused docs/package assertions | **PASS:** 114 passed | [`docs-contract.log`](audit-evidence/v070/docs-contract.log) |
| Documentation build | MkDocs strict mode | **PASS** | [`docs-strict.log`](audit-evidence/v070/docs-strict.log) |
| Bandit | Production source, high-severity gate | **PASS:** no high-severity findings | [`bandit.log`](audit-evidence/v070/bandit.log) |
| Dependency audit | Candidate dependency graph | **PASS:** no known vulnerabilities | [`pip-audit.log`](audit-evidence/v070/pip-audit.log) |
| Secret scan | Exact tracked candidate snapshot | **PASS:** no leaks | [`gitleaks.log`](audit-evidence/v070/gitleaks.log), [`gitleaks.sarif`](audit-evidence/v070/gitleaks.sarif) |
| Package validation | sdist, wheel-from-sdist, Twine 7 | **PASS** | [`package-build.log`](audit-evidence/v070/package-build.log), [`twine.log`](audit-evidence/v070/twine.log) |
| SBOM | CycloneDX 1.6 | **PASS:** 96 components | [`sbom.json`](audit-evidence/v070/sbom.json) |

The four full matrix cells emitted 25 known deprecation warnings from
Starlette's AnyIO portal alias and Click's `isolated_filesystem` helper. They
produced no test failures.

Package digests:

| Artifact | SHA-256 |
| --- | --- |
| `aksara_framework-0.7.0rc1-py3-none-any.whl` | `e7ebb9497c003d2ede18e9a81bdbbeb19b15cb97f8ac6242f26fd115791b43d5` |
| `aksara_framework-0.7.0rc1.tar.gz` | `9f4c8ae4870a85478bc1d4f95768f28e0a9ad408db198ad33dce052b6d9efd62` |

The machine-readable rollup is
[`release-summary.json`](audit-evidence/v070/release-summary.json). Evidence
digests are recorded in
[`artifact-manifest.sha256`](audit-evidence/v070/artifact-manifest.sha256).

## Performance interpretation

The local campaign admitted 256 Operations in 254.931 ms and executed them in
452.720 ms. It also proved concurrent same-key deduplication, eight exclusive
claims, N-to-N+1 fencing, task-backed execution, bounded pruning, indexed claim
selection under 3,000 terminal rows, exact mutation counts, and a fully idle
pool. These figures detect obvious local pathology; they are not a capacity or
latency service-level objective.

## Compatibility and deferred surfaces

Durable Operations are additive and opt-in. Existing applications do not need
to register an action, mount the durable router, start a durable worker, or use
the task adapter. Existing generated REST, synchronous MCP, and unlinked task
contracts remain in force.

Protocol-level durable MCP Tasks remain **DEFERRED DUE TO EXTERNAL STANDARD**.
The current official Python SDK roadmap does not implement the
`io.modelcontextprotocol/tasks` extension, and the extension is wire-incompatible
with the earlier in-core experiment. Aksara does not hand-roll a competing wire
protocol. See the official [Python SDK roadmap](https://github.com/modelcontextprotocol/python-sdk/blob/main/ROADMAP.md)
and [Tasks extension specification](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2663-tasks-extension.md).

Planner quality, persistent AI sessions, memory, multi-agent and autonomous
workflows, provider-specific quality, Studio AI internals, generic workflow/DAG
composition, `DurableStep` internals, application approval UX, and long-term
compliance retention remain outside the stable v0.7 contract.

## Known limits

- The application process, registered handler/resolver code, and application
  database role are trusted. Application-owned history is not a tamper-resistant
  compliance ledger.
- The guarded database boundary covers Aksara connection use in the owning
  asyncio task. Arbitrary Python network, subprocess, thread, or independent
  database effects depend on accurate application registration and review.
- Current authorization does not promise instantaneous global revocation while
  an external identity provider is unavailable.
- PostgreSQL and an external provider cannot share one atomic transaction.
  Exactly-once external delivery and undo are not promised.
- Worker orchestration, tenant enumeration, escalation UX, backups, monitoring,
  and durable audit retention remain application and operator responsibilities.
- Hosted PostgreSQL 16 independently passed the complete release matrix for the
  candidate implementation.
