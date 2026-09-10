# Aksara v0.6.0 final release evidence

## Scope

This file records evidence that can be established for the final public
v0.6.0 release. It supplements, and does not rewrite,
[`RELEASE_EVIDENCE_v0.6.0-rc2.md`](RELEASE_EVIDENCE_v0.6.0-rc2.md).

The RC2 file describes pre-release validation of commit
`ff30ad3a5f1c4a25a257ab0b11ac69be10cf2342`. The hosted checks below ran on the
final release commit. The fresh-install checks ran later against the public
PyPI artifact. Those are three distinct evidence sets.

## Final release identity

| Item | Value |
| --- | --- |
| Package | `aksara-framework` |
| Package version | `0.6.0` |
| Tag | `v0.6.0` |
| Final tagged commit | `6bb2e81249c38d31332a8041e1755b765ed60c39` |
| Tagged tree | `cb3a3bb8bcb3df6ab65c09ba97a952842e01b032` |
| GitHub Release | <https://github.com/nagarjuna-tella/Aksara/releases/tag/v0.6.0> |
| PyPI release | <https://pypi.org/project/aksara-framework/0.6.0/> |
| GitHub Release published | 2026-09-10 04:47:36 UTC |
| PyPI artifacts published | 2026-09-10 04:51 UTC |

The `main` integration commit `7f3c6de81b055323e8786ff32572d0f0d188c1f9`
has the same tree as the tagged commit. This evidence uses the tagged commit as
the final release identity rather than treating the duplicate commit as another
artifact build.

## Published artifacts

The following SHA-256 values are the digests reported by PyPI for the public
files and were retrieved after publication.

| Artifact | SHA-256 |
| --- | --- |
| `aksara_framework-0.6.0-py3-none-any.whl` | `d4fa02c13e25a3acdb97099c46dec1e2e15727f561bb4955a96ce9d01a6d152d` |
| `aksara_framework-0.6.0.tar.gz` | `a92de2f4d4603a7495789891f7ca33265c8ca2d80cc4355df131ce3b382e1c79` |

PyPI metadata declares Python 3.11 or later and the official MCP SDK dependency
range `mcp>=2.0.0,<2.1.0`. The long description came from the release README;
it therefore also carried the documentation drift recorded in the v0.6.1
installed-package baseline.

## Hosted final-commit validation

All rows below are GitHub-hosted results whose `head_sha` is the final tagged
commit.

| Workflow | Trigger | Result | Run |
| --- | --- | --- | --- |
| Release Gate | pull request | PASS | [34437918009](https://github.com/nagarjuna-tella/Aksara/actions/runs/34437918009) |
| Security CI | pull request | PASS | [34437918072](https://github.com/nagarjuna-tella/Aksara/actions/runs/34437918072) |
| CodeQL | pull request | PASS | [34437918011](https://github.com/nagarjuna-tella/Aksara/actions/runs/34437918011) |
| Release Gate | tag push | PASS | [34438470661](https://github.com/nagarjuna-tella/Aksara/actions/runs/34438470661) |
| Publish Package | manual dispatch on tag | PASS | [34438715003](https://github.com/nagarjuna-tella/Aksara/actions/runs/34438715003) |

The Release Gate definition exercised Python 3.11 and 3.14 against both tested
web boundaries, using PostgreSQL 16 with pgvector. It also ran the security,
fuzz, diagnostics, strict Doctor, distribution build/Twine, isolated-wheel,
packaged Support Desk, dependency-audit, static-analysis, and secret-scan jobs.
The hosted workflow result establishes that those jobs passed on the final SHA;
the detailed pre-release counts and local artifact logs remain in the RC2
evidence rather than being retroactively attributed here.

## Pre-release RC2 validation

Before the final release commit, RC2 recorded:

- 7,995 passing tests and 2 expected provider skips on each supported
  Python/web boundary;
- 97 targeted MCP/AI tests;
- 51 passing packaged Support Desk checks with a real official MCP client;
- 428 security tests, 162 fuzz tests plus 3 expected skips, and 314 diagnostics
  tests;
- strict docs, package/Twine, installed-wheel, Doctor release policy, Bandit,
  dependency audit, Gitleaks, SBOM, and Ruff/mypy ratchet results.

Those numbers describe the RC2 commit named above. They are useful provenance,
but they are not presented as local reruns on the final tag.

## Public artifact fresh-install verification

On 2026-09-10, `aksara-framework==0.6.0` was installed from PyPI into a clean
CPython 3.11.15 virtual environment with no editable checkout. The verification
covered package import and version, CLI help/version/command discovery,
`startproject`, generated settings inspection, a small PostgreSQL model,
migration generation/application, application startup, health, OpenAPI,
generated REST routes, `/ai/tools/mcp`, official-client initialization at
`/mcp/`, Doctor, and clean SIGINT shutdown.

Core installation, migrations, startup, REST reads, catalog inspection, and
shutdown succeeded. The reproduction also found that the v0.6.0 scaffold taught
a configuration object that did not control the global runtime, omitted the
authenticated REST/MCP journey, and caused MCP tool discovery without
Starlette `AuthenticationMiddleware` to raise. These are recorded without
correction in
[`audit-evidence/v061/installed-package-baseline.md`](audit-evidence/v061/installed-package-baseline.md)
and are the adoption defects addressed by v0.6.1.

The public artifact check used a local PostgreSQL 18.4 test server. The final
hosted release gate independently used PostgreSQL 16. Aksara requires
PostgreSQL; SQLite is not a supported substitute for this release contract.

## Stable v0.6 contract

The stable boundary comprises the async PostgreSQL ORM and migrations,
generated REST APIs, authentication and server-owned principals, permissions
and `PolicyEngine`, tenant isolation, Admin/core CLI/Doctor production surfaces,
PostgreSQL background task mechanics, generated MCP discovery and execution,
execution-time MCP authorization, exact signed approval grants, deterministic
audit events, structured failures, transactional rollback, cancellation, and
bounded runtime limits.

The supported MCP transport is Streamable HTTP at `/mcp/`. The
`/ai/tools/mcp` route is an HTTP JSON inspection catalog; it is not the protocol
endpoint for official MCP clients.

## Experimental and application-owned boundaries

- Planner behavior, provider quality and selection, investigation/session
  shape, persistent AI state, memory, multi-agent and autonomous workflows,
  code/patch generation, and Studio AI internals are experimental.
- MCP sessions and replay protection are bounded and process-local; durable
  cross-worker replay and idempotency are not provided.
- Signed approval grants do not constitute an application-level durable human
  approval workflow.
- Durable audit retention, external side-effect idempotency, and long-term
  credential provenance remain application responsibilities.
- Background tasks persist and restore tenant identity, not a complete
  Principal with roles, scopes, or a prior authorization decision.
- Custom many-to-many through models and object-valued lazy forward foreign-key
  attributes remain unsupported.
- No external audit, penetration-test certification, soak-test certification,
  or live-provider quality certification is claimed.

This final evidence records what shipped and what can be verified. It does not
erase the public-documentation defects found after release or imply validation
that did not occur on the final tag.
