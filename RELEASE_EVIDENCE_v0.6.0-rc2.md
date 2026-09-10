# Aksara v0.6.0-rc2 release evidence

## Recommendation

**1. READY FOR v0.6.0.**

The evaluated candidate implements and proves the bounded AI/MCP execution
contract required for v0.6.0. The packaged Support Desk application used an
official MCP client to initialize a Streamable HTTP session, discover generated
tools, inspect schemas, read and mutate authorized tenant data, reject forbidden
and cross-tenant work, and emit correlated redacted audit records. All existing
release gates and the supported runtime matrix remained green against local
PostgreSQL.

This recommendation covers the documented stable execution boundary. Planner
quality, durable agent workflows, provider-specific behavior, investigation
sessions, memory, and Studio AI internals remain experimental. Nothing was
published as part of this work.

## Evaluated candidate

| Item | Value |
| --- | --- |
| Release | `0.6.0-rc2` / package version `0.6.0rc2` |
| Candidate commit | `ff30ad3a5f1c4a25a257ab0b11ac69be10cf2342` |
| RC1 base | `b7c8f5a900815b42785c506eb550c3d33c973396` |
| Branch | `codex/v060-rc2-mcp-ai` |
| Database | Local PostgreSQL database `aksara_test`; required database tests enabled |
| MCP dependency | `mcp>=2.0.0,<2.1.0` |
| Packaged reference client | `mcp==2.0.0` |
| Matrix MCP version | `mcp==2.0.1` |
| Negotiated protocol | `2026-07-28` |
| Transport | Streamable HTTP at `/mcp/` |

Database credentials and connection URLs are intentionally absent from this
evidence. Each candidate-bound log starts with the exact commit. The packaged
gate records the database name and wheel digest, while the package log links
that wheel digest to the exact candidate.

## Execution boundary delivered

- The maintained Model Context Protocol Python SDK now owns protocol
  initialization, capability negotiation, `tools/list`, `tools/call`, structured
  content, sessions, cancellation, and Streamable HTTP mechanics.
- Generated create, retrieve, list/filter, update, delete, and custom-action
  tools expose strict JSON Schemas derived from the model contract. Schemas
  preserve required, optional, nullable, enum, JSON, array, vector, relation,
  description, constraint, read-only, server-controlled, and forbidden-field
  behavior where applicable.
- MCP execution resolves through the same generated REST route used by API
  callers. Authentication, agent type, credential scope/audience/expiry,
  tenant, roles, PolicyEngine, object access, validation, field restrictions,
  and transaction behavior are therefore checked again at invocation time.
- `AgentInvocationContext` takes immutable snapshots of the agent, initiator,
  tenant, scope, policy, request, run, tool-call, and approval context. Context
  variables isolate concurrent sessions, and the packaged two-tenant
  concurrency test proves no principal or tenant leakage.
- Approval-required operations accept signed, expiring grants bound to the
  exact principal, tenant, tool, arguments, approver, and decision. Missing,
  rejected, expired, invalid, or changed-argument approvals cannot mutate data;
  authorization is rechecked when the approved call executes.
- Every resolved invocation emits one deterministic audit event containing the
  decision and correlation context with a safe argument summary. Approval
  tokens and argument values are excluded. Logging, JSONL, and application-owned
  sink hooks are available.
- Runtime budgets enforce tool-call, planning-step, per-tool, provider, and
  overall time limits, cancellation, replay rejection, and provider-reported
  token/cost limits independently of model prompts.
- Errors use stable `client`, `authorization`, `transient`, and `internal`
  categories. Any MCP operation that returns an error rolls back its database
  transaction, including partial mutations before internal failure.

## Exact validation results

| Gate | Environment or scope | Result | Evidence |
| --- | --- | --- | --- |
| Full source regression | Python 3.11.5, local `aksara_test` | **PASS:** 7,995 passed, 2 skipped | [`pytest-full.log`](audit-evidence/v060-mcp-ai/pytest-full.log) |
| Targeted MCP/AI | Protocol, schemas, approval, audit, context, lifecycle, runtime limits | **PASS:** 97 passed | [`pytest-targeted.log`](audit-evidence/v060-mcp-ai/pytest-targeted.log) |
| Minimum web stack | Python 3.11.15; FastAPI 0.136.1; Starlette 1.0.1; MCP 2.0.1 | **PASS:** 7,995 passed, 2 skipped | [`matrix-py311-min.log`](audit-evidence/v060-mcp-ai/matrix-py311-min.log) |
| Latest web stack | Python 3.11.15; FastAPI 0.141.1; Starlette 1.6.0; MCP 2.0.1 | **PASS:** 7,995 passed, 2 skipped | [`matrix-py311-latest.log`](audit-evidence/v060-mcp-ai/matrix-py311-latest.log) |
| Minimum web stack | Python 3.14.4; FastAPI 0.136.1; Starlette 1.0.1; MCP 2.0.1 | **PASS:** 7,995 passed, 2 skipped | [`matrix-py314-min.log`](audit-evidence/v060-mcp-ai/matrix-py314-min.log) |
| Latest web stack | Python 3.14.4; FastAPI 0.141.1; Starlette 1.6.0; MCP 2.0.1 | **PASS:** 7,995 passed, 2 skipped | [`matrix-py314-latest.log`](audit-evidence/v060-mcp-ai/matrix-py314-latest.log) |
| Packaged Support Desk | Isolated wheel, restricted PostgreSQL role, official MCP client | **PASS:** 51 checks, 0 failures | [`support-desk-gate.json`](audit-evidence/v060-mcp-ai/support-desk-gate.json), [`support-desk-gate.log`](audit-evidence/v060-mcp-ai/support-desk-gate.log) |
| Package | sdist, wheel-from-sdist, Twine, isolated import | **PASS** | [`package-build.log`](audit-evidence/v060-mcp-ai/package-build.log) |
| Security, fuzz, diagnostics | Security 428; fuzz 162 plus 3 skipped; diagnostics 314 | **PASS** | [`security-diagnostics.log`](audit-evidence/v060-mcp-ai/security-diagnostics.log) |
| Static ratchet | Ruff 7,212 ≤ 7,218; mypy 496 ≤ 501 | **PASS:** no new accepted debt | [`static-analysis.log`](audit-evidence/v060-mcp-ai/static-analysis.log) |
| Doctor release policy | Exact packaged candidate | **PASS:** 12 checks; 0 warnings, failures, or blocks | [`doctor-release.json`](audit-evidence/v060-mcp-ai/doctor-release.json) |
| Docs strict build | MkDocs strict | **PASS** | [`docs-strict.log`](audit-evidence/v060-mcp-ai/docs-strict.log) |
| Bandit | Repository source | **PASS:** 0 high-severity findings | [`bandit.log`](audit-evidence/v060-mcp-ai/bandit.log) |
| Dependency audit | Packaged dependency environment | **PASS:** no known vulnerabilities | [`dependency-audit.log`](audit-evidence/v060-mcp-ai/dependency-audit.log) |
| Secret scan | Exact candidate Git archive | **PASS:** no leaks | [`gitleaks.log`](audit-evidence/v060-mcp-ai/gitleaks.log), [`gitleaks.sarif`](audit-evidence/v060-mcp-ai/gitleaks.sarif) |
| SBOM | CycloneDX 1.6 | **PASS:** 190 components | [`sbom.json`](audit-evidence/v060-mcp-ai/sbom.json), [`sbom.log`](audit-evidence/v060-mcp-ai/sbom.log) |

The four dependency-matrix runs each emitted 25 known deprecation warnings:
Click's `isolated_filesystem` helper and Starlette's AnyIO
`BlockingPortal` alias. They produced no test failures.

Package digests:

| Artifact | SHA-256 |
| --- | --- |
| `aksara_framework-0.6.0rc2-py3-none-any.whl` | `97fef0d66276968944f82756080189dbf07da7572180569fbea8c0386c3b7fcb` |
| `aksara_framework-0.6.0rc2.tar.gz` | `ce131eff348b0964ca1ce2a276376fb7db8f8311e3a30edc006c946d43d10949` |

The machine-readable rollup is
[`release-summary.json`](audit-evidence/v060-mcp-ai/release-summary.json). SHA-256
digests for all 20 evidence artifacts are in
[`artifact-manifest.sha256`](audit-evidence/v060-mcp-ai/artifact-manifest.sha256).

## Real-client, equivalence, and abuse evidence

The packaged production gate proved these invariants against the wheel rather
than an editable checkout:

| Boundary | Proven behavior |
| --- | --- |
| Protocol | Official client initialized, negotiated `2026-07-28`, discovered tools, inspected schemas, invoked tools, and closed the session over Streamable HTTP. |
| Generated CRUD | Ticket create, retrieve, list, update, and approval-gated delete were discoverable according to policy; an authorized write persisted and an authorized read returned tenant rows. |
| API/MCP equivalence | REST and MCP accepted the same application values and persisted representation, rejected invalid values, enforced the same fields and tenants, and produced classified errors through their respective wire formats. |
| Authorization | Anonymous, missing-scope, policy-denied, revoked-after-discovery, wrong-audience, expired, cross-tenant, and nonexistent-resource calls were denied at execution time. |
| Field and input abuse | Tenant mass assignment, server-controlled fields, malformed nested input, schema mismatch, changed approval arguments, replayed call IDs, undiscovered tools, and oversized request bodies were rejected. |
| Approval | No mutation occurred without approval. A signed grant was limited to the intended principal, tenant, tool, arguments, approver, decision, and expiry; an exact approved operation succeeded. |
| Database state | Authorized work persisted. Forbidden work did not persist. A deliberately failing partial mutation rolled back fully. |
| Context isolation | Concurrent official-client sessions for distinct principals and tenants returned only their own tenant identifiers. |
| Audit | Twenty correlated execution records covered allowed and denied outcomes without storing argument values or approval tokens. |
| Shutdown | An in-flight invocation received cancellation, the application exited successfully, and all application database connections were released. |
| Provider boundary | Deterministic fake-provider tests covered normal and structured responses, malformed responses, timeout, cancellation, provider errors, unavailable providers, tool-call responses, and excessive/repeated calls. |

## Stable candidate and experimental surfaces

The v0.6 stable candidate comprises agent-principal identity and propagation,
metadata-derived generated MCP CRUD and custom actions, protocol discovery and
execution, invocation-time authentication and authorization, tenant and field
enforcement, PolicyEngine integration, deterministic error categories,
execution audit events, deterministic runtime limits, and the signed stateless
approval boundary described here.

The autonomous planner, investigation quality and session storage, persistent
conversations, agent memory, multi-agent workflows, durable autonomous
workflows, automatic code generation and patch execution, provider-specific
behavioral quality, and Studio AI internals remain experimental.

## Known limitations

- Approval is a signed stateless exact-operation grant, not a durable approval
  workflow. A grant can authorize the same exact operation again during its
  validity window if a caller supplies a new tool-call ID. Applications that
  need single-use or durable human review must store that state externally.
- MCP session and replay state is bounded and process-local. It does not provide
  restart-safe or cross-worker sessions, global idempotency, or cross-worker
  replay protection.
- The default audit sink emits structured logs. The JSONL sink is local, and
  durable retention, external storage, access control, and audit certification
  remain operator responsibilities.
- Streamable HTTP at `/mcp/` is the supported framework transport for v0.6.
  Aksara does not expose a stdio transport.
- Token and monetary budgets can enforce only the accounting reported by a
  provider. Deterministic fake-provider behavior is tested; live cloud-provider
  certification was outside scope.
- Planner behavior, Studio AI, and investigation/session state remain
  experimental and process-local. No claim of durable autonomous operation is
  made.

These limits are compatible with the v0.6 stable contract because the stable
guarantee surrounds invocation and application execution; it does not depend on
model intelligence or durable autonomous orchestration.
