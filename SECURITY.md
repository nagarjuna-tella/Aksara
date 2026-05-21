# Security Policy

Aksara takes security seriously. If you find something that looks wrong, please tell us —
we'd rather hear it from you first.

> **Note:** Aksara is currently undergoing a dedicated security-hardening milestone before
> claiming production-mode status. See [Security Posture](#security-posture) below.

## Supported Versions

Security fixes are maintained on the current release. Upgrade to the latest version before
reporting a vulnerability.

| Version | Supported |
|---------|-----------|
| 0.5.x (current) | ✅ Active security fixes |
| < 0.5 | ❌ No longer supported |

A formal supported-version policy will be finalized as part of the v0.6.0 production-mode milestone.

## Reporting a Vulnerability

**Please don't open a public issue.**

Use GitHub's [private security advisory](../../security/advisories/new) instead — it is
visible only to you and the maintainers until a fix is released, then published automatically
alongside the patch.

When you report, we will:

- Acknowledge within **48 hours**
- Target a patch within **7 days** for critical issues
- Credit you in the release notes if you'd like

## What's In Scope

- Authentication or authorization bypass
- SQL injection or unsafe query construction
- AI prompt injection or unsafe code execution
- Cross-tenant or cross-user data leakage
- MCP/AI surface overexposure (unauthorized field access or mutation)
- Unsafe field handling in generated schemas or ORM
- Session/cookie security issues
- Dependency vulnerabilities with a direct exploit path in Aksara
- Docker or configuration issues that expose sensitive data

## What's Out of Scope

- Theoretical attacks with no proof of concept
- Vulnerabilities in example apps or documentation
- Issues introduced by deliberate misconfiguration (e.g., `debug=True` in production)
- Upstream dependency vulnerabilities with no Aksara-specific impact (report those upstream)
- Denial-of-service attacks not related to Aksara's code

## Security Posture

Aksara is undergoing a dedicated security-hardening milestone before v0.6.0 production-mode claims.
The current release (v0.5.x) is suitable for development and internal use. Production deployment
should be preceded by running the security diagnostics:

```bash
aksara doctor security-check
aksara doctor production-check
```

`production-check` exits 1 when blocking issues are found. Fix all blocking conditions before
deploying.

## Current Security Controls

The following controls are implemented as of v0.5.48:

### Diagnostics

- `aksara doctor security-check` — reports on SECRET_KEY, debug mode, CORS, Studio, MCP, cookies, rate limits, RLS configuration, and security matrix validity
- `aksara doctor production-check` — stricter; blocks on critical issues; exits 1 when unsafe

### Configuration guards

- **Studio** — `studio_expose_in_production=False` by default; `studio_require_auth=True` by default
- **MCP** — `mcp_enabled=False` by default; requires explicit opt-in with agent token
- **Debug mode** — CORS wildcard, debug mode, and weak SECRET_KEY detected and reported

### AI and MCP field controls

- `ai_sensitive=True` — excludes field from AI/MCP schemas and AI prompt pack exports
- `ai_agent_writable=False` — marks field as not writable by AI agents (schema-time enforcement)
- HMAC-SHA256 agent tokens with configurable TTL for AI/MCP authentication
- `DenyAI` permission class to block AI agents from specific endpoints

### Multi-tenancy

- Application-layer tenant filtering via `TenantMiddleware`
- PostgreSQL Row-Level Security (RLS) via `TenantModel` and `apply_tenant_context()`
- Tenant-bound DB session variable (`aksara.current_tenant_id`)
- Background task tenant provenance captured at enqueue time

### Admin

- Admin CSRF protection enabled by default
- Admin rate limiting enabled by default

### Security baseline

- `security/security_matrix.yml` — canonical inventory of surfaces, actors, risks, and adversarial scenarios
- 6,744+ test suite including 33+ targeted security regression tests

## Known Hardening Areas (Active Work)

The following are known gaps being addressed in the hardening milestone:

| Area | Status | Planned Round |
|------|--------|---------------|
| Centralized `Principal` / policy engine | In planning | Round 2 |
| Runtime field enforcement (schema bypass) | In planning | Round 2 |
| MCP scoped, audience-bound credentials | In planning | Round 3 |
| Cross-surface adversarial test matrix | Round 1 baseline done | Round 3 (tests) |
| Cross-tenant property-based tests | In planning | Round 3 |
| ORM/migration/serializer fuzzing | In planning | Round 4 |
| Supply-chain hardening (CodeQL, Semgrep, SBOM) | In planning | Round 5 |
| External security review | In planning | Pre-v0.6.0 |
| Release gates in CI | In planning | Round 5 |

## Disclosure and Patch Expectations

- **Critical issues** (auth bypass, SQL injection, cross-tenant data leak): patch within 7 days
- **High issues** (field exposure, Studio bypass, weak defaults): patch within 14 days
- **Medium issues** (misconfiguration, missing rate limits): patch within 30 days
- **Low issues**: addressed in regular releases

Security issues will be documented in [CHANGELOG.md](CHANGELOG.md) under `security` entries.

## Security Fix History

Past security fixes are documented in [CHANGELOG.md](CHANGELOG.md). Look for `security`
entries within each version section.

Notable fixes:
- **v0.5.47**: Fixed X-User-Id impersonation, AI metadata leakage across MCP/AI surfaces, Studio auth bypass in debug mode, tenant context issues in background tasks, and several ORM/migration correctness bugs.
- **v0.5.48**: Added launch checks, example validation, no-secret checks; 6,744 passing tests.
