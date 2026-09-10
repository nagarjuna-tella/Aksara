# Production Hardening

## Status

Aksara includes production diagnostics and security hardening controls, but does
not currently make a blanket production-readiness claim.

## Required Checks

Before deploying, run:

```bash
aksara doctor security-check
aksara doctor production-check
```

`production-check` exits with code `1` when blocking or failing production
conditions are detected. Warnings remain visible but do not change its exit
code, so an operator must review them before deployment.

Release candidates use the stricter policy:

```bash
aksara doctor production-check --release
```

Release mode exits with code `1` for every warning, failure, block, skipped
check, or unknown result. It also requires a valid security matrix in which no
scenario remains `planned` or `partial` and every implemented surface has at
least one `covered` scenario.

## Required Production Settings

| Setting | Required production posture |
|---------|-----------------------------|
| `AKSARA_DEBUG` | `false` |
| `SECRET_KEY` or `AKSARA_SECRET_KEY` | Strong random value, at least 32 characters |
| `CORS_ALLOW_ALL_ORIGINS` | `false` for credentialed deployments |
| `CORS_ALLOW_CREDENTIALS` | Do not combine with wildcard origins |
| `AKSARA_COOKIE_SECURE` | `true` |
| `AKSARA_STUDIO_EXPOSE_IN_PRODUCTION` | `false`, unless explicitly needed |
| `AKSARA_STUDIO_REQUIRE_AUTH` | `true` whenever Studio is exposed |
| `AKSARA_MCP_ENABLED` | `false`, unless explicitly needed |
| `AKSARA_AI_AGENT_TOKEN` | Strong token when MCP/AI agents are enabled |
| `AKSARA_MCP_REQUIRE_AUTH` | `true` when MCP is enabled without another auth mechanism |
| `AKSARA_MCP_REQUIRE_SCOPED_TOKENS` | `true` when MCP is enabled |
| `AKSARA_MCP_TOKEN_TTL_SECONDS` | Configured when MCP is enabled; 300-900 seconds recommended |
| `AKSARA_MCP_REQUIRE_AUDIENCE` | `true` when MCP is enabled |
| `AKSARA_MCP_TOKEN_AUDIENCE` | Stable service identifier when audience checks are enabled |
| `AKSARA_MCP_REQUIRE_TENANT_BOUND_TOKENS` | `true` for multi-tenant MCP deployments |
| `AKSARA_MULTI_TENANT` | `true` for multi-tenant deployments |
| `AKSARA_RLS_ENABLED` | `true` when database-level RLS is required |
| `AKSARA_ADMIN_RATE_LIMIT_ENABLED` | `true` |
| `AKSARA_REQUIRE_SECURITY_MATRIX` | Optional strict/private matrix enforcement for deployment checks |
| `AKSARA_SECURITY_MATRIX_PATH` | Explicit matrix path for a project or release process |

## Blocking Conditions

`aksara doctor production-check` blocks production deployment when it detects:

- `debug=True`
- Missing or weak `SECRET_KEY`
- CORS wildcard combined with credentials
- Studio exposed in production without required authentication
- MCP enabled without an authentication mechanism
- MCP enabled without scoped-token requirements
- MCP enabled without token TTL configuration
- MCP enabled without audience requirements
- Multi-tenant MCP enabled without tenant-bound token requirements
- Missing private security matrix when
  `AKSARA_REQUIRE_SECURITY_MATRIX=true`
- Invalid private security matrix when
  `AKSARA_REQUIRE_SECURITY_MATRIX=true`

## Warning Conditions

Warnings should be reviewed before production deployment:

- CORS wildcard without credentials
- Studio exposed in production with authentication
- `cookie_secure=False`
- Admin rate limiting disabled
- Multi-tenant mode without confirmed RLS
- AI fields broadly writable by default when AI, MCP, or AI Console exposure is
  enabled and `AKSARA_AI_WRITABLE_FIELDS_REVIEWED=true` has not been set after
  a concrete field review
- Missing private security matrix when strict matrix enforcement is disabled
- MCP token TTL longer than 3600 seconds

## Security Matrix Enforcement

The public repository includes:

```text
security/security_matrix.example.yml
```

This file demonstrates the structure of a matrix without publishing internal
project coverage details.

Private projects and release processes may maintain:

```text
security/security_matrix.yml
```

That file is intentionally git-ignored. By default, a missing private matrix is
a warning. To make a missing or invalid private matrix blocking, set:

```bash
AKSARA_REQUIRE_SECURITY_MATRIX=true
```

Do not publish private matrices accidentally.

The framework repository uses the public-safe
`security/security_matrix.release.yml` for its own release-candidate workflow.
Applications can point `AKSARA_SECURITY_MATRIX_PATH` at a project-specific
matrix. `--release` makes that matrix mandatory and also requires completed
coverage entries.

## Additional Validation

Security and fuzz tests can be run separately during release preparation:

```bash
python -m pytest tests/security/ -q
python -m pytest tests/security/fuzz/ -q
```

The generated CRUD abuse invariants use a real PostgreSQL database and run in
the required security suite without an unconditional placeholder skip.

## Release-Trust Gates

Before a production-mode claim, release candidates should also pass the
release-security workflow:

- Full test suite
- Security, diagnostics, and fuzz tests
- Strict docs build
- Dependency audit
- Static analysis
- Secret scanning
- Package build and `twine check`
- SBOM generation
- `aksara doctor production-check --release`

These checks prepare releases for stronger review. They do not replace external
security review and do not create a blanket production-readiness claim.
