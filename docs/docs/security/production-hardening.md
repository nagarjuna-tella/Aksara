# Production Hardening Guide

> **Status:** Updated through Round 5 of the Aksara security-hardening milestone.
> Aksara is not yet claiming production-mode status. This guide documents the expected
> secure posture and the checks you must pass before deploying Aksara in production.

## Required Production Checks

Before deploying, run both security commands:

```bash
aksara doctor security-check
aksara doctor production-check
```

`production-check` will exit with code 1 when any blocking condition is detected.
Fix all blocking issues before deploying.

For security-hardening validation, run the Round 5 fuzz suite separately:

```bash
python -m pytest tests/security/fuzz/ -q
```

This suite is intentionally bounded and separate from the normal fast suite.
It is not yet a production-check requirement or CI release gate.

## Required Settings for Production

| Setting | Required Value | Notes |
|---------|---------------|-------|
| `AKSARA_DEBUG` | `false` | Never run `debug=True` in production |
| `SECRET_KEY` | Strong random value (≥ 32 chars) | `python3 -c 'import secrets; print(secrets.token_urlsafe(64))'` |
| `AKSARA_STUDIO_EXPOSE_IN_PRODUCTION` | `false` (default) | Set `true` only if Studio is explicitly needed |
| `AKSARA_STUDIO_REQUIRE_AUTH` | `true` (default) | Studio must always require auth when exposed |
| `AKSARA_MCP_ENABLED` | `false` (default) | Only enable if agent tokens are configured |
| `AKSARA_AI_AGENT_TOKEN` | Strong random value | Required when MCP is enabled |
| `AKSARA_MCP_REQUIRE_SCOPED_TOKENS` | `true` | Required when MCP is enabled (Round 4) |
| `AKSARA_MCP_REQUIRE_AUDIENCE` | `true` | Required when MCP is enabled (Round 4) |
| `AKSARA_MCP_TOKEN_TTL_SECONDS` | `300`–`900` | Required when MCP is enabled; max 3600 (Round 4) |
| `CORS_ALLOW_ALL_ORIGINS` | `false` | Never combine wildcard with credentials |
| `AKSARA_COOKIE_SECURE` | `true` (default) | Cookies must be HTTPS-only |
| `AKSARA_ADMIN_CSRF_ENABLED` | `true` (default) | CSRF must be enabled for admin |
| `AKSARA_ADMIN_RATE_LIMIT_ENABLED` | `true` (default) | Rate limits must be enabled |

### Multi-tenant deployments (additional)

| Setting | Required Value |
|---------|---------------|
| `AKSARA_MULTI_TENANT` | `true` |
| `AKSARA_RLS_ENABLED` | `true` |

## Blocking Conditions

`aksara doctor production-check` will **exit 1** and block deployment when:

| Condition | Why |
|-----------|-----|
| `debug=True` | Exposes stack traces and internal config |
| `SECRET_KEY` missing or weak | Sessions, CSRF, and tokens are insecure |
| CORS wildcard + credentials | Any site can make credentialed cross-origin requests |
| Studio exposed without `studio_require_auth=True` | Studio becomes a public data browser |
| MCP enabled without `AKSARA_AI_AGENT_TOKEN` | AI/MCP tools are accessible without credentials |
| MCP enabled without scoped tokens (`AKSARA_MCP_REQUIRE_SCOPED_TOKENS`) | Per-tool scope enforcement disabled |
| MCP enabled without audience check (`AKSARA_MCP_REQUIRE_AUDIENCE`) | Token may be accepted by unintended services |
| Multi-tenant MCP without tenant-bound tokens | MCP tokens may not carry required tenant context |
| `security_matrix.yml` missing | Security baseline inventory is absent |
| `security_matrix.yml` invalid | Security baseline is corrupted |

## Warnings (non-blocking but should be fixed)

| Condition | Recommendation |
|-----------|---------------|
| CORS wildcard without credentials | Restrict to trusted origins |
| Studio exposed in production (with auth) | Confirm this is intentional |
| `cookie_secure=False` | Set `AKSARA_COOKIE_SECURE=true` |
| Admin rate limiting disabled | Enable rate limiting |
| Multi-tenant without confirmed RLS | Enable PostgreSQL RLS |
| `ai_agent_writable` broadly true by default | Mark sensitive fields `ai_agent_writable=False` |

## Deployment Checklist

Use this checklist before each production deployment:

### Security checks
- [ ] `aksara doctor production-check` exits 0
- [ ] `aksara doctor security-check` shows no `fail` or `block` results
- [ ] `security_matrix.yml` loads without validation errors

### Configuration
- [ ] `AKSARA_DEBUG=false`
- [ ] `SECRET_KEY` is set and strong (≥ 32 chars, not a default value)
- [ ] `AKSARA_STUDIO_EXPOSE_IN_PRODUCTION=false` (or `AKSARA_STUDIO_REQUIRE_AUTH=true` if Studio is needed)
- [ ] `AKSARA_MCP_ENABLED=false` (or `AKSARA_AI_AGENT_TOKEN` set if MCP is needed)
- [ ] CORS origins are explicit, not wildcard
- [ ] Cookie settings are secure (`AKSARA_COOKIE_SECURE=true`)

### Database
- [ ] All migrations are applied
- [ ] RLS policies are in place (multi-tenant deployments)
- [ ] `DATABASE_URL` is set and tested

### Multi-tenancy (if applicable)
- [ ] `AKSARA_MULTI_TENANT=true`
- [ ] `AKSARA_RLS_ENABLED=true`
- [ ] RLS policies tested for cross-tenant isolation

### Future gates (planned for later rounds)
- [ ] External security review completed
- [ ] No open critical/high security issues
- [ ] Supply-chain scan (pip-audit, Bandit) passes
- [ ] Fuzz smoke tests pass in CI release gates

### Round 5 fuzzing and generated surface hardening

Round 5 adds adversarial and fuzzing coverage for generated framework surfaces.

Covered:

- Filters.
- Ordering.
- Pagination and cursors where applicable.
- Serializer payloads.
- Runtime field enforcement bypass attempts.
- Helper-level bulk/upsert payload shapes where applicable.
- Migration identifiers/defaults.
- Malformed and oversized payloads.
- OpenAPI fuzzing placeholder when Schemathesis is unavailable.

Security invariants:

- Forbidden fields never mutate.
- Tenant isolation is not bypassed.
- Hidden/sensitive fields do not leak.
- Unsafe identifiers do not become unsafe SQL.
- Malformed inputs fail safely.
- Oversized inputs fail safely.

Remaining:

- Supply-chain CI.
- Release gates.
- External review.
- Full production-mode claim.

## Notes

This guide will be updated as the hardening milestone progresses. Controls marked
"planned" will be enforced in future rounds before Aksara claims production-mode status.
