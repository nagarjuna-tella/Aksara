# Aksara Threat Model

> **Status:** Updated through Round 5 of the Aksara security-hardening milestone.
> Some controls described here are implemented today; others are planned for upcoming rounds.
> This threat model will be expanded as the hardening milestone progresses.

## Purpose

Aksara generates multiple surfaces from model definitions — REST APIs, MCP tools, Studio UI,
AI prompt exports, serializers, migrations, and background tasks. Each generated surface is a
potential attack vector. This threat model tracks how those surfaces may expose or mutate data
and what controls exist or are planned.

## Assets

The following assets require protection:

| Asset | Sensitivity | Notes |
|-------|-------------|-------|
| Application data (records) | High | Core business objects stored per tenant |
| Tenant data | Critical | Cross-tenant access is a critical violation |
| Auth credentials (sessions, tokens) | Critical | Compromise enables impersonation |
| AI/MCP agent tokens | High | Short-lived HMAC tokens; compromise allows AI surface access |
| AI/MCP metadata (schemas, field descriptions) | Medium–High | `ai_sensitive` fields must not leak |
| Generated schemas (OpenAPI, MCP tool defs) | Medium | Exposes model structure; must exclude sensitive fields |
| Migration SQL | High | DDL errors can cause data loss or injection |
| Background task context | High | Must carry trusted tenant provenance |
| Audit/security logs | High | Must not be tampered with or suppressed |
| Signing material (SECRET_KEY) | Critical | Used for sessions and CSRF; compromise is catastrophic |

## Trust Boundaries

```
External world
    │
    ├── REST clients (browser, mobile, API consumers)
    │       → Enter at: HTTP endpoints
    │       → Trust level: Authenticated user (after session/token validation)
    │
    ├── Browser users → Studio UI
    │       → Enter at: Studio endpoints
    │       → Trust level: Studio auth token (bearer) + session
    │       → Extra guard: studio_expose_in_production=False by default
    │
    ├── AI/MCP agents → MCP tools / AI prompt surfaces
    │       → Enter at: MCP tool endpoints
    │       → Trust level: HMAC agent token (X-Aksara-AI-Token)
    │       → Extra guard: mcp_enabled=False by default
    │
    └── Migration tooling / CLI → migration execution
            → Trust level: Operator (local or CI)
            → Risk: destructive DDL; no runtime auth check

Internal boundaries
    │
    ├── Generated schemas → runtime server enforcement
    │       ✓ Round 3: enforce_request_payload_policy() wired into
    │         ViewSet.create() and ViewSet.update(). Forbidden fields
    │         are rejected with 403 + denied_fields before any DB write.
    │       ✓ Round 5: nested/raw payload fuzzing and helper-level
    │         bulk/upsert payload validation added.
    │         Remaining: Studio, manager-level bulk/upsert integration,
    │         direct MCP tool calls.
    │
    ├── Client-supplied tenant header → trusted tenant context
    │       ⚠ Tenant context must be resolved server-side.
    │         Client headers must not be trusted as authoritative.
    │
    ├── Background workers → request context
    │       tenant_id is captured server-side at enqueue time.
    │       Workers must restore from that, not from headers.
    │
    └── Migration generation → database execution
            Generated SQL must use safe identifiers.
            Defaults must be properly escaped.
```

## Primary Risks (OWASP API Top 10 Alignment)

| Risk ID | OWASP Category | Description | Severity |
|---------|---------------|-------------|----------|
| missing_auth | API2: Broken Authentication | Surface accessible without auth | Critical |
| broken_object_level_authorization | API1: BOLA | User accesses object they don't own | Critical |
| cross_tenant_read | API1: BOLA | User reads another tenant's data | Critical |
| cross_tenant_write | API1: BOLA | User mutates another tenant's data | Critical |
| restricted_field_read | API3: BOPLA | Hidden/sensitive field exposed | High |
| restricted_field_write | API3: BOPLA | Read-only/AI-restricted field written | High |
| schema_bypass | API3: BOPLA | Client sends raw JSON bypassing schema | High |
| ai_metadata_leak | API3: BOPLA | AI surface leaks sensitive field metadata | High |
| studio_auth_bypass | API2: Broken Authentication | Studio bypasses auth in debug/prod | Critical |
| mcp_unauthenticated_access | API2: Broken Authentication | MCP tools accessible without credentials | Critical |
| forged_tenant_context | API2: Broken Authentication | Client forges tenant header | Critical |
| empty_tenant_fail_open | API2: Broken Authentication | No tenant = broad access | Critical |
| sql_injection | API8: Security Misconfiguration | User input reaches SQL unsafely | Critical |
| weak_secret_key | API8: Security Misconfiguration | Missing or default SECRET_KEY | Critical |
| debug_mode_exposed | API8: Security Misconfiguration | debug=True in production | High |
| unsafe_production_surface | API8: Security Misconfiguration | Studio/MCP exposed without safeguards | High |

## Current Controls (Round 1-5 baseline)

- **`aksara doctor security-check`** — Checks SECRET_KEY, debug mode, CORS, Studio, MCP, cookies, rate limits, tenancy/RLS configuration, security matrix validity, and MCP credential hardening.
- **`aksara doctor production-check`** — Stricter version; blocks deployment on critical issues.
- **Studio production guard** — `studio_expose_in_production=False` by default; `studio_require_auth=True` by default.
- **MCP disabled by default** — `mcp_enabled=False`; requires explicit opt-in.
- **AI metadata controls** — `ai_sensitive` and `ai_agent_writable` field metadata excludes sensitive fields from generated schemas at schema-generation time.
- **Agent token auth** — HMAC-SHA256 tokens with TTL (default 300s) for AI/MCP surfaces.
- **Multi-tenant middleware** — Application-layer tenant filtering via `TenantMiddleware`.
- **PostgreSQL RLS** — `TenantModel` base class with RLS policies and `apply_tenant_context()` per connection.
- **Background task tenant binding** — `tenant_id` captured at enqueue time from `tenant_id_var`.
- **Admin rate limiting and CSRF** — Enabled by default on admin endpoints.
- **Security regression tests** — 33+ targeted regression tests for v0.5.47 fixes.
- **`security_matrix.yml`** — Canonical inventory of surfaces, actors, risks, and adversarial scenarios.
- **Round 2: Centralized `Principal` / `PolicyEngine`** — Unified principal object and policy engine for all surfaces. `PolicyEngine.can()`, `visible_fields()`, `writable_fields()`, `validate_payload()`.
- **Round 3: Runtime REST enforcement** — `enforce_request_payload_policy()` wired into `ViewSet.create()` and `ViewSet.update()`. Forbidden fields rejected with 403 + structured `denied_fields` response.
- **Round 4: Tenant isolation adversarial tests** — `test_tenant_isolation.py` covers cross-tenant resource access, AI/MCP agent cross-tenant, tenant_required fail-closed, forged header ignored, body tenant_id override denied.
- **Round 4: MCP credential hardening** — `MCPCredentialClaims`, `require_scope()`, `require_mcp_audience()`, `require_mcp_tenant()` in `aksara/security/mcp.py`. `principal_from_mcp_claims()` normalizes `aud` → `audience`. `PolicyEngine.can()` extended with `required_audience` and `tenant_required`. Doctor check `security.mcp_hardening` blocks production deployments with misconfigured MCP credentials.
- **Round 5: Fuzzing and generated-surface hardening** — `tests/security/fuzz/` adds bounded Hypothesis and adversarial coverage for filters, ordering, pagination/cursors, serializers, runtime field enforcement bypass attempts, JSON path-like inputs, helper-level bulk/upsert payload shapes, migration identifiers/defaults, malformed payloads, and oversized payloads. Schemathesis/OpenAPI fuzzing is represented as an explicit skipped placeholder because Schemathesis is not installed.

## Round 5: Fuzzing and Generated Surface Hardening

Round 5 adds adversarial and fuzzing coverage for generated framework surfaces.

Covered:

- Filters and generated query construction.
- Ordering parameters, including tenant and AI-sensitive field ordering attempts.
- Pagination and cursors where applicable.
- Serializer payloads and raw runtime field enforcement bypass attempts.
- Nested payloads, aliases, casing variants, dotted keys, and JSON path-like keys.
- Helper-level bulk/upsert payload shapes, including unsafe conflict targets.
- Migration identifiers/defaults.
- Malformed and oversized payloads.
- OpenAPI fuzzing placeholder when Schemathesis is unavailable.

Security invariants:

- Forbidden fields never mutate.
- Tenant isolation is not bypassed.
- Hidden/sensitive fields do not leak through denied generated surfaces.
- Unsafe identifiers do not become unsafe SQL.
- Malformed inputs fail safely.
- Oversized inputs fail safely.

Remaining:

- Supply-chain CI.
- Release gates.
- External review.
- Full production-mode claim.

## Planned Controls (Future Rounds)

| Round | Control |
|-------|---------|
| Round 6 | Wire fuzzing into release gates / CI |
| Round 6 | Supply-chain hardening (CodeQL, Semgrep, Bandit, SBOM, PyPI Trusted Publishing) |
| Future | Field-level audit logging for AI/MCP tool calls |
| Future | Direct MCP tool call enforcement (without REST) |
| Future | Manager-level bulk update / upsert principal enforcement |
| Future | Scoped/audience-bound MCP token issuance in core |
| Pre-v0.6 | External security review before production-mode claim |

## Known Gaps (as of Round 5)

1. **Studio write surfaces not enforced.** Studio is internal tooling without user-data CRUD in the current codebase. When public Studio write paths are added, enforcement must be wired.
2. **Manager-level bulk update / upsert principal enforcement not wired.** Round 5 adds helper-level validation for bulk/upsert-shaped payloads, but direct manager calls remain trusted internal operations.
3. **OpenAPI fuzzing is not active.** A skipped Schemathesis placeholder exists; Schemathesis is not installed.
4. **Fuzzing is not wired into CI release gates.** Round 5 keeps fuzzing separately runnable with `python -m pytest tests/security/fuzz/ -q`.
5. **No supply-chain hardening.** No CodeQL, Semgrep, pip-audit, SBOM, or signed release provenance yet.
6. **No external review.** Planned before v0.6 Production Mode.
