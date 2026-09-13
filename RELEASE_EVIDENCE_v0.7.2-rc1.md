# Aksara v0.7.2-rc1 release evidence

## Recommendation

**READY FOR v0.7.2rc1 REVIEW.**

All 22 functional findings disclosed by the v0.7.1 Public Truth audit are
closed in the installed candidate: 22 `FIXED`, zero `DISPROVED`, zero
`ALREADY_RESOLVED`, and zero unresolved. Every local source, PostgreSQL,
installed-wheel, upgrade, security, documentation, packaging, and compatibility
gate passes. The independent hosted PostgreSQL 16 release matrix also passes in
full on the final candidate-content commit.

No merge, tag, GitHub Release, or PyPI publication is authorized or has occurred.

## Source

| Item | Value |
| --- | --- |
| Candidate | `v0.7.2-rc1` / package version `0.7.2rc1` |
| Released base | `a0422cf8fa004b41a2ccdaa9aa91c8036357159d` (`main`, tree-equivalent to `v0.7.1`) |
| Implementation source | `4240c86d39f02fdcc4b506bf07c0326f52df34a7` |
| Local evidence assembly | Recorded by the evidence commit that adds this document |
| Branch | `codex/v072-audit-closure` |
| Local database | PostgreSQL 18.4 database `aksara_test` |
| Supported Python | 3.11 through 3.14 |
| Supported web boundary | FastAPI 0.136.1 / Starlette 1.0.1 through FastAPI 0.141.1 / Starlette 1.6.0 |

Database credentials and complete connection URLs are absent from committed
evidence.

## Finding closure

The public `aksara-framework==0.7.1` wheel independently reproduced all 22
findings before production changes. The installed candidate reverses every
negative result, and permanent regressions cover externally meaningful behavior.

| Disposition | Count |
| --- | ---: |
| `FIXED` | 22 |
| `DISPROVED` | 0 |
| `ALREADY_RESOLVED` | 0 |
| Unresolved | 0 |

The human-readable matrix is
[`AKSARA_V072_AUDIT_CLOSURE.md`](AKSARA_V072_AUDIT_CLOSURE.md), and its
machine-readable authority is
[`findings-closure.json`](audit-evidence/v072/findings-closure.json).
The production change map covers 36 production/package files, maps every file
to at least one finding, has no unmapped file, and confirms runtime dependency
declarations are unchanged. The only schema migration is the additive internal
ordinary-task ownership migration for TASK-001.

## Runtime matrix

| Cell | Exact versions | Result | Evidence |
| --- | --- | --- | --- |
| Python 3.11 minimum | Python 3.11.5; FastAPI 0.136.1; Starlette 1.0.1 | **PASS:** 8,545 passed, 2 expected provider skips | [`record`](audit-evidence/v072/matrix-py311-min.json), [`log`](audit-evidence/v072/matrix-py311-min.log) |
| Python 3.11 latest | Python 3.11.5; FastAPI 0.141.1; Starlette 1.6.0 | **PASS:** 8,545 passed, 2 expected provider skips | [`record`](audit-evidence/v072/matrix-py311-latest.json), [`log`](audit-evidence/v072/matrix-py311-latest.log) |
| Python 3.14 minimum | Python 3.14.4; FastAPI 0.136.1; Starlette 1.0.1 | **PASS:** 8,545 passed, 2 expected provider skips | [`record`](audit-evidence/v072/matrix-py314-min.json), [`log`](audit-evidence/v072/matrix-py314-min.log) |
| Python 3.14 latest | Python 3.14.4; FastAPI 0.141.1; Starlette 1.6.0 | **PASS:** 8,545 passed, 2 expected provider skips | [`record`](audit-evidence/v072/matrix-py314-latest.json), [`log`](audit-evidence/v072/matrix-py314-latest.log) |

The final source regression, including the release-ledger contract tests, reports **8,545
passed, 2 expected provider skips, 29 warnings**. The warnings are known
Starlette AnyIO alias and Click isolated-filesystem deprecations.

## Dedicated correctness and security gates

| Gate | Result | Evidence |
| --- | --- | --- |
| 22-finding focused source closure | **PASS:** 232 passed | [`closure-targeted.log`](audit-evidence/v072/closure-targeted.log) |
| Installed candidate closure selection | **PASS:** 213 passed | [`installed-closure-pytest.log`](audit-evidence/v072/installed-closure-pytest.log) |
| Ordinary Tasks, including real processes and migration | **PASS:** 54 passed | [`task-targeted.log`](audit-evidence/v072/task-targeted.log) |
| Installed process ownership campaign | **PASS:** 5 scenarios, 10 invariants, zero stale authoritative writes | [`task-process-gate.json`](audit-evidence/v072/task-process-gate.json) |
| Durable Operations | **PASS:** 234 passed | [`durable-targeted.log`](audit-evidence/v072/durable-targeted.log) |
| Production-bound invariant prototype | **PASS:** 24 passed | [`invariant-prototype.log`](audit-evidence/v072/invariant-prototype.log) |
| MCP protocol/security boundary | **PASS:** 68 passed | [`mcp-targeted.log`](audit-evidence/v072/mcp-targeted.log) |
| Restricted-role/RLS/tenancy | **PASS:** 22 passed | [`rls-targeted.log`](audit-evidence/v072/rls-targeted.log) |
| Security suite | **PASS:** 430 passed | [`security.log`](audit-evidence/v072/security.log) |
| Generated API fuzz | **PASS:** 165 passed | [`fuzz.log`](audit-evidence/v072/fuzz.log) |
| Diagnostics | **PASS:** 314 passed | [`diagnostics.log`](audit-evidence/v072/diagnostics.log) |
| Migrations | **PASS:** 458 passed | [`migrations.log`](audit-evidence/v072/migrations.log) |
| Doctor release policy | **PASS:** 12 checks, no warnings or failures | [`doctor-release.json`](audit-evidence/v072/doctor-release.json) |
| Static ratchets | **PASS:** Ruff 7,111 ≤ 7,218; mypy 490 ≤ 501 | [`static-analysis.log`](audit-evidence/v072/static-analysis.log) |
| Ruff on release-evidence tooling | **PASS** | Commands recorded in the PR validation summary |
| Bandit | **PASS:** no high-severity findings under repository policy | [`bandit.log`](audit-evidence/v072/bandit.log) |
| Dependency audit | **PASS:** no known vulnerabilities; unpublished candidate itself excluded | [`pip-audit.log`](audit-evidence/v072/pip-audit.log) |
| Secret/credential scan | **PASS:** Gitleaks found no leaks; evidence contains no credential-bearing PostgreSQL URL | [`gitleaks.log`](audit-evidence/v072/gitleaks.log), [`credential-scan.json`](audit-evidence/v072/credential-scan.json) |

The security assessment is
[`AKSARA_V072_SECURITY_REVIEW.md`](AKSARA_V072_SECURITY_REVIEW.md). It records
the exploit prerequisites and avoids treating unsafe primitives as universal
remote vulnerabilities.

## Installed candidate and reference applications

- The isolated candidate wheel passes all 15 installed-package checks, including
  generated PostgreSQL migration, REST/OpenAPI, official MCP discovery/call,
  cross-interface persistence, clean shutdown, and pool cleanup.
- Packaged Support Desk passes 66 production-shaped checks with a restricted
  `NOSUPERUSER NOBYPASSRLS` role, forced RLS, two tenants, REST/MCP authorization,
  Durable Operations, tasks, startup/recovery/concurrency, Doctor, Admin, and
  connection cleanup.
- Ticket Desk passes all six progressive stages and 86 public API assertions.
- Basic, Blog, CRM, and multitenant scaffolds pass editable install, wheel build,
  isolated wheel import, and arbitrary project-name checks. The basic template
  additionally passes migration, tests, live HTTP, build/install, and restart.
- The canonical TypeScript SDK passes strict TypeScript 5.9.3 compilation and a
  live Ticket Desk HTTP contract for list/detail/create/update/filter/pagination.
- Four clean installed-wheel workflow import orders and the packaged historical
  multitenant exemption matcher pass.
- Five retained source examples start using the installed candidate framework.

Evidence: [`installed-package-gate.json`](audit-evidence/v072/installed-package-gate.json),
[`support-desk-gate.json`](audit-evidence/v072/support-desk-gate.json),
[`tutorial-gate.json`](audit-evidence/v072/tutorial-gate.json),
[`scaffold-gate.json`](audit-evidence/v072/scaffold-gate.json),
[`typescript-sdk-gate.json`](audit-evidence/v072/typescript-sdk-gate.json),
[`installed-boundaries.json`](audit-evidence/v072/installed-boundaries.json), and
[`example-execution.json`](audit-evidence/v072/example-execution.json).

## v0.7.1 to candidate upgrade

A clean public v0.7.1 installation created and seeded a Support Desk schema with
an organization, tenant user/agent, foreign-key ticket, queued ordinary task,
and succeeded Durable Operation. The installed candidate applied the additive
task ownership migration, preserved every row and relation, claimed the queued
task with the new ownership fields, replayed migrations idempotently, and
served the preserved ticket through authorized REST. Anonymous REST remained
denied; Admin and MCP discovery remained present. The candidate packaged
Support Desk gate separately proves Doctor and live Durable execution against
the same wheel. Evidence: [`upgrade-gate.json`](audit-evidence/v072/upgrade-gate.json).

## Documentation and public-truth gates

- Documentation contract: **127 passed**.
- Current Python fences: **348**, all compile/import from the installed wheel.
- Current JSON fences: **15**, all parse; five selected objects validate against
  installed response models.
- Literal CLI forms: **295** parsed, seven explicit non-command exclusions,
  zero errors.
- Public sample census: 165 current Markdown files and 595 current fences.
- Strict MkDocs: **PASS**, 162 rendered pages.
- Internal links/assets: **42,339**, zero errors.
- Selected external documentation links: **41**, zero broken/unverified.

Evidence: [`docs-contract.log`](audit-evidence/v072/docs-contract.log),
[`installed-doc-imports.json`](audit-evidence/v072/installed-doc-imports.json),
[`cli-docs-syntax.json`](audit-evidence/v072/cli-docs-syntax.json),
[`snippet-coverage.json`](audit-evidence/v072/snippet-coverage.json),
[`docs-strict.log`](audit-evidence/v072/docs-strict.log),
[`rendered-links.json`](audit-evidence/v072/rendered-links.json), and
[`external-links.json`](audit-evidence/v072/external-links.json).

## Performance sanity

The established local campaign uses 256 Operations, eight workers, and 3,000
terminal-noise rows. All seven invariants pass: concurrent idempotency,
completion, reclaim fences, partial-index claim plan, mutation accounting,
bounded pruning, and idle-pool cleanup. The result is a pathology check, not a
capacity or latency SLO. Evidence:
[`performance-sanity.json`](audit-evidence/v072/performance-sanity.json).

## Package artifacts

| Artifact | SHA-256 |
| --- | --- |
| `aksara_framework-0.7.2rc1-py3-none-any.whl` | `a3ab5b8930dad1adb92a5c7610624f3d94768e0f51740bbe61d17bab8aacb982` |
| `aksara_framework-0.7.2rc1.tar.gz` | `5e881e01e1679bde0d725672120a1883dfd6945d0aaf4ac37050702894e179c4` |

Fresh isolated build produced the sdist and built the wheel from it. Twine
validates both. A validated CycloneDX 1.6 SBOM from the isolated candidate
environment contains 52 components. Evidence:
[`package-build.log`](audit-evidence/v072/package-build.log),
[`twine.log`](audit-evidence/v072/twine.log),
[`artifact-hashes.sha256`](audit-evidence/v072/artifact-hashes.sha256),
[`sbom.json`](audit-evidence/v072/sbom.json), and
[`sbom.log`](audit-evidence/v072/sbom.log).

## Hosted CI

PR #33 completed **21 of 21 hosted checks successfully** on candidate-content
commit `33f253ba30b9d66713603ef8c0c1250d1f0960f6`, with zero failed and zero
pending checks. The matrix includes all four Python/FastAPI/Starlette full-suite
cells against PostgreSQL 16, package construction, installed-wheel documentation,
packaged Support Desk, strict docs, security/fuzz/diagnostics, dependency audit,
SBOM, static analysis, two secret scans, and CodeQL. The first hosted run exposed
six false positives where Gitleaks classified committed SHA-256 evidence digests
as API keys; six exact, reviewable fingerprints were added to `.gitleaksignore`,
and both hosted secret scans then passed. No credential was suppressed.

The machine-readable check inventory, conclusions, and GitHub job URLs are in
[`hosted-ci.json`](audit-evidence/v072/hosted-ci.json). The evidence-only commit
that records this result changes no runtime or package content; the complete
hosted matrix is verified again on that final PR head before review handoff.

## Known limitations outside the closed ledger

The existing stability boundary remains: planner/provider quality, persistent AI
state or memory, multi-agent/autonomous workflows, Studio AI internals, generic
DAG composition, application approval UX, cross-worker MCP replay storage, and
durable compliance retention are Experimental, application-owned, or deferred.
None is one of the closed 22 defects. The release retains existing static debt
ratchets and known third-party deprecation warnings.

## Publication state

As of 2026-09-13, PyPI serves `0.7.1` and returns 404 for `0.7.2rc1`. No local
or remote `v0.7.2*` tag exists, and GitHub's public API returns 404 for
`v0.7.2` and `v0.7.2-rc1` releases. Human review is required. This evidence
authorizes no merge, tag, GitHub Release, or PyPI upload.
