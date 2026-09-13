# Aksara v0.7.2 release evidence

## Recommendation

**READY FOR v0.7.2 FINALIZATION REVIEW.**

Aksara v0.7.2 closes the complete functional defect ledger exposed by the
v0.7.1 Public Truth audit. All 22 findings remain `FIXED`; none is unresolved,
disproved, deferred, or partially fixed. The final source, installed wheel,
public-v0.7.1 upgrade, PostgreSQL, documentation, security, packaging, and
four-cell compatibility gates pass.

This finalization adds no functional repair beyond the merged Audit Closure
implementation. It changes release identity, current release wording, tests
that assert that identity, and final evidence. It adds no v0.8 capability,
dependency, database-engine support, Durable Operations semantic change, or
stable MCP semantic change.

No merge, tag, GitHub Release, or PyPI publication is authorized or has
occurred.

## Source

| Item | Value |
| --- | --- |
| Release | `v0.7.2` / package version `0.7.2` |
| Merged implementation base | `e56cd56b7c247f38a10d6eb51ef688f7e79c9cfe` (`origin/main`, merged PR #33) |
| Finalization content | `f36306ee50e177495d806a5e6bc4aed7f5de0725` |
| Final evidence commit | Recorded by the Git commit containing this document |
| Final merge SHA | Pending human review and merge |
| Branch | `release/v0.7.2` |
| Local database | PostgreSQL 18.4 database `aksara_test` |
| Supported Python | 3.11 through 3.14 |
| Supported web boundary | FastAPI 0.136.1 / Starlette 1.0.1 through FastAPI 0.141.1 / Starlette 1.6.0 |

Database credentials and complete connection URLs are absent from committed
evidence.

## Audit closure

The authoritative candidate ledger remains historically accurate at
[`audit-evidence/v072/findings-closure.json`](audit-evidence/v072/findings-closure.json).
The final closure record verifies its hash and exact disposition without
rewriting it.

| Disposition | Count |
| --- | ---: |
| Total | 22 |
| `FIXED` | 22 |
| `DISPROVED` | 0 |
| `ALREADY_RESOLVED` | 0 |
| Unresolved | 0 |

The mapped source regression files pass **421 tests**. The same mapped files
pass **421 tests** under Python's isolated import mode with the final wheel
installed from `dist`, so the closure result does not depend on an editable
checkout. Evidence: [`closure-summary.json`](audit-evidence/v072-final/closure-summary.json),
[`source log`](audit-evidence/v072-final/closure-targeted.log), and
[`installed-wheel log`](audit-evidence/v072-final/installed-closure-pytest.log).

## No-functional-change result

The finalization scope guard compares the final tree with merged implementation
SHA `e56cd56b7c247f38a10d6eb51ef688f7e79c9cfe`. Four production/package files
change only after exact version normalization:

- `aksara/_version.py`
- `aksara/cli/scaffold.py`
- `examples/support_desk/main.py`
- `pyproject.toml`

The guard reports `runtime_logic_changed: false`, `dependencies_changed:
false`, and `schema_migrations_changed: false`. The candidate and final wheels
have the same 287 members and are byte-identical after normalizing the release
version, distribution metadata directory, and `RECORD` hashes. Evidence:
[`finalization-scope.json`](audit-evidence/v072-final/finalization-scope.json)
and [`wheel-equivalence.json`](audit-evidence/v072-final/wheel-equivalence.json).

All current version surfaces report exactly `0.7.2`. Historical RC evidence,
the historical closure generator, and RC comparison normalizers retain their
original spellings. Evidence:
[`current-version-surfaces.json`](audit-evidence/v072-final/current-version-surfaces.json)
and [`version-reference-audit.json`](audit-evidence/v072-final/version-reference-audit.json).

## Runtime matrix

All cells required PostgreSQL tests. The two skips in each cell are the expected
external-provider credential tests.

| Cell | Exact versions | Result | Evidence |
| --- | --- | --- | --- |
| Python 3.11 minimum | Python 3.11.5; FastAPI 0.136.1; Starlette 1.0.1 | **PASS:** 8,545 passed, 2 skipped, 29 warnings | [`record`](audit-evidence/v072-final/matrix-py311-min.json), [`log`](audit-evidence/v072-final/matrix-py311-min.log) |
| Python 3.11 latest | Python 3.11.5; FastAPI 0.141.1; Starlette 1.6.0 | **PASS:** 8,545 passed, 2 skipped, 29 warnings | [`record`](audit-evidence/v072-final/matrix-py311-latest.json), [`log`](audit-evidence/v072-final/matrix-py311-latest.log) |
| Python 3.14 minimum | Python 3.14.4; FastAPI 0.136.1; Starlette 1.0.1 | **PASS:** 8,545 passed, 2 skipped, 29 warnings | [`record`](audit-evidence/v072-final/matrix-py314-min.json), [`log`](audit-evidence/v072-final/matrix-py314-min.log) |
| Python 3.14 latest | Python 3.14.4; FastAPI 0.141.1; Starlette 1.6.0 | **PASS:** 8,545 passed, 2 skipped, 29 warnings | [`record`](audit-evidence/v072-final/matrix-py314-latest.json), [`log`](audit-evidence/v072-final/matrix-py314-latest.log) |

The warnings are the established Starlette AnyIO alias and Click
isolated-filesystem deprecations.

## Critical subsystem results

| Gate | Result | Evidence |
| --- | --- | --- |
| Ordinary Tasks and ownership migration | **PASS:** 57 passed | [`task-targeted.log`](audit-evidence/v072-final/task-targeted.log) |
| Installed real-process Task campaign | **PASS:** 5 scenarios, 10 invariants, zero stale authoritative writes | [`task-process-gate.json`](audit-evidence/v072-final/task-process-gate.json) |
| Durable Operations | **PASS:** 234 passed | [`durable-targeted.log`](audit-evidence/v072-final/durable-targeted.log) |
| Production-bound invariant prototype | **PASS:** 24 passed | [`invariant-prototype.log`](audit-evidence/v072-final/invariant-prototype.log) |
| MCP protocol/security boundary | **PASS:** 68 passed | [`mcp-targeted.log`](audit-evidence/v072-final/mcp-targeted.log) |
| Restricted-role/RLS/tenancy | **PASS:** 28 passed | [`rls-targeted.log`](audit-evidence/v072-final/rls-targeted.log) |
| Security suite | **PASS:** 430 passed | [`security.log`](audit-evidence/v072-final/security.log) |
| Generated API fuzz | **PASS:** 165 passed | [`fuzz.log`](audit-evidence/v072-final/fuzz.log) |
| Diagnostics | **PASS:** 314 passed | [`diagnostics.log`](audit-evidence/v072-final/diagnostics.log) |
| Migrations | **PASS:** 458 passed | [`migrations.log`](audit-evidence/v072-final/migrations.log) |
| Doctor release policy | **PASS:** 12 checks, no warnings, failures, or blocks | [`doctor-release.json`](audit-evidence/v072-final/doctor-release.json) |
| Static ratchets | **PASS:** Ruff 7,111 ≤ 7,218; mypy 490 ≤ 501 | [`static-analysis.log`](audit-evidence/v072-final/static-analysis.log) |
| Bandit | **PASS:** zero high-severity findings | [`bandit.log`](audit-evidence/v072-final/bandit.log) |
| Dependency audit | **PASS:** no known vulnerabilities | [`pip-audit.log`](audit-evidence/v072-final/pip-audit.log) |

## Task migration and public-v0.7.1 upgrade

The realistic upgrade gate starts with the public
`aksara-framework==0.7.1` wheel, creates and seeds a Support Desk schema, and
then upgrades it with the final local `0.7.2` wheel. It applies
`aksara_core_migrations_0003_task_claim_ownership`, verifies repeat migration
idempotency, and preserves the organization, tenant agent/auth principal,
ticket relation, queued ordinary Task, and succeeded Durable Operation.

The upgraded task gains `locked_by`, `claim_token`, and `lock_expires_at`, is
claimed with an owner token, and remains fenced from stale completion after
ownership transfer. Authorized REST sees the preserved ticket, anonymous REST
remains denied, and Admin and MCP discovery remain available. The packaged
Support Desk gate separately exercises Doctor and live Durable execution on
the same final wheel. Evidence:
[`upgrade-gate.json`](audit-evidence/v072-final/upgrade-gate.json) and
[`task-process-gate.json`](audit-evidence/v072-final/task-process-gate.json).

## Installed final wheel and reference applications

- The isolated final wheel passes all **15** installed-package checks, including
  migration generation, REST/OpenAPI, official MCP discovery and execution,
  cross-interface persistence, shutdown, and pool cleanup.
- Packaged Support Desk passes **66** production-shaped checks using a
  restricted `NOSUPERUSER NOBYPASSRLS` role and forced RLS.
- Ticket Desk passes all **6** progressive stages and **86** public API
  assertions.
- Basic, Blog, CRM, and multitenant scaffolds pass editable installation,
  wheel construction and isolated installation. The basic scaffold also passes
  migration, tests, live HTTP, and restart.
- The generated TypeScript SDK passes **3** checks with strict TypeScript 5.9.3
  compilation and a live Ticket Desk list/detail/create/update/filter/pagination
  contract.
- Four clean installed-wheel workflow import orders and the packaged
  multitenant route matcher pass.
- Five retained examples start against the installed final framework.

Evidence: [`installed-package-gate.json`](audit-evidence/v072-final/installed-package-gate.json),
[`support-desk-gate.json`](audit-evidence/v072-final/support-desk-gate.json),
[`tutorial-gate.json`](audit-evidence/v072-final/tutorial-gate.json),
[`scaffold-gate.json`](audit-evidence/v072-final/scaffold-gate.json),
[`typescript-sdk-gate.json`](audit-evidence/v072-final/typescript-sdk-gate.json),
[`installed-boundaries.json`](audit-evidence/v072-final/installed-boundaries.json),
and [`example-execution.json`](audit-evidence/v072-final/example-execution.json).

## Documentation and public-truth gates

- Documentation contracts: **127 passed**.
- Current Python fences: **348**, all compile/import from the installed wheel.
- Current JSON fences: **15**, all parse; selected response shapes validate
  against installed models.
- Literal CLI forms: **295** parsed, seven explicit non-command exclusions,
  zero errors.
- Public sample census: **165** current Markdown files and **595** current
  fences.
- Strict MkDocs: **PASS**, 162 rendered pages.
- Internal links/assets: **42,339**, zero errors.
- Selected external documentation links: **41**, zero broken or unverified.

Evidence: [`docs-contract.log`](audit-evidence/v072-final/docs-contract.log),
[`installed-doc-imports.json`](audit-evidence/v072-final/installed-doc-imports.json),
[`cli-docs-syntax.json`](audit-evidence/v072-final/cli-docs-syntax.json),
[`snippet-coverage.json`](audit-evidence/v072-final/snippet-coverage.json),
[`docs-strict.log`](audit-evidence/v072-final/docs-strict.log),
[`rendered-links.json`](audit-evidence/v072-final/rendered-links.json), and
[`external-links.json`](audit-evidence/v072-final/external-links.json).

## Performance sanity

The established local campaign uses 256 Operations, eight workers, and 3,000
terminal-noise rows. All seven invariants pass: concurrent idempotency,
completion, reclaim fences, partial-index claim plan, mutation accounting,
bounded pruning, and idle-pool cleanup. This is a pathology check rather than a
capacity or latency SLO. Evidence:
[`performance-sanity.json`](audit-evidence/v072-final/performance-sanity.json).

## Package artifacts and SBOM

| Artifact | SHA-256 |
| --- | --- |
| `aksara_framework-0.7.2-py3-none-any.whl` | `9f12a1e7df0a1b5e270beb6e4b49e12a03a3fa1e9a6914746af863428023ff8e` |
| `aksara_framework-0.7.2.tar.gz` | `2c9f7f9a9cdd48652f80af7eef606139063eb413a3507bea1c00f63f62a1135b` |

The sdist was built from committed finalization source, and the wheel was built
from that extracted sdist. Twine 7.0.0 validates both. The validated CycloneDX
1.6 SBOM contains 52 components and identifies the root package as `0.7.2`.
Evidence: [`package-build.log`](audit-evidence/v072-final/package-build.log),
[`twine.log`](audit-evidence/v072-final/twine.log),
[`artifact-hashes.sha256`](audit-evidence/v072-final/artifact-hashes.sha256),
and [`sbom.json`](audit-evidence/v072-final/sbom.json).

## Hosted CI

Merged candidate PR #33 completed **21 of 21** hosted checks successfully. The
finalization PR is [#34](https://github.com/nagarjuna-tella/Aksara/pull/34).
Its first complete run passed **21 of 21** checks, with zero failures and zero
pending checks, on PR head
`e490ba01ee0379676cdaa04889157877485153ce`. The matrix covers all four
Python/FastAPI/Starlette cells against hosted PostgreSQL 16, package construction,
installed-wheel documentation, packaged Support Desk, strict docs, security,
fuzz, diagnostics, dependency audit, SBOM, static analysis, both secret scans,
and CodeQL.

The content validated locally remains
`f36306ee50e177495d806a5e6bc4aed7f5de0725`. The commit containing this hosted
inventory is an evidence-only child of `e490ba01ee0379676cdaa04889157877485153ce`;
its exact SHA is recorded in PR #34 and the final handoff because a Git commit
cannot contain its own SHA. The complete hosted matrix must pass again on that
final evidence-only head. Evidence:
[`hosted-ci.json`](audit-evidence/v072-final/hosted-ci.json).

## Evidence integrity

The final artifact manifest covers this release-evidence document, the release
notes, local final evidence, and the exact local wheel and sdist. The dedicated
verifier checks every digest, rejects protected historical directories, and
scans final evidence for credential-bearing PostgreSQL URLs. Gitleaks and the
credential scan must both report zero findings before this branch is pushed.

## Publication state

As of 2026-09-13, PyPI serves `0.7.1` and does not contain `0.7.2`. No local or
remote `v0.7.2` tag exists, and GitHub has no `v0.7.2` release. Human review and
merge are required before the publication safety checkpoint. This evidence
authorizes no merge, tag, GitHub Release, or PyPI upload.
