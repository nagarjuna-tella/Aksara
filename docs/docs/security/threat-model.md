# Aksara Threat Model

> **Status:** This document is part of the Aksara security-hardening milestone (Round 1).
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
    │       ⚠ Schemas are NOT security controls.
    │         A client can send fields absent from the schema.
    │         Runtime enforcement is required (planned Round 2).
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

## Current Controls (Round 1 baseline)

- **`aksara doctor security-check`** — Checks SECRET_KEY, debug mode, CORS, Studio, MCP, cookies, rate limits, tenancy/RLS configuration, and security matrix validity.
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

## Planned Controls (Future Rounds)

| Round | Control |
|-------|---------|
| Round 2 | Centralized `Principal` object — resolves actor identity for all surfaces |
| Round 2 | `policy.can()` / `policy.visible_fields()` / `policy.writable_fields()` — unified policy engine |
| Round 2 | Runtime field enforcement — strip/reject forbidden fields at REST, MCP, Studio, bulk, upsert |
| Round 2 | Field-level audit logging for AI/MCP tool calls |
| Round 3 | Cross-tenant property-based tests |
| Round 3 | MCP scoped, audience-bound credentials |
| Round 4 | ORM/migration/serializer fuzzing (Hypothesis, Schemathesis) |
| Round 5 | Supply-chain hardening (CodeQL, Semgrep, Bandit, SBOM, PyPI Trusted Publishing) |
| Pre-v0.6 | External security review before production-mode claim |

## Known Gaps (as of Round 1)

1. **Runtime field enforcement is missing.** Schema-time filtering is not a security control. A client sending a crafted payload with `ai_sensitive=True` fields will have them accepted.
2. **No centralized Principal/policy engine.** Each surface manages authorization independently.
3. **No cross-tenant adversarial tests.** Property-based tests are planned for Round 3.
4. **No supply-chain hardening.** No CodeQL, Semgrep, pip-audit, or signed releases.
5. **No external review.** Planned before v0.6 Production Mode.
