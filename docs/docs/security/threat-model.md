# Threat Model

## Purpose

Aksara generates multiple application surfaces from model definitions. This
threat model describes the main assets, trust boundaries, attacker goals, and
implemented controls.

## Assets

- Application data
- Tenant data
- Authentication credentials
- AI/MCP credentials
- Generated schemas
- Generated APIs
- Studio/admin surfaces
- Migration SQL/DDL
- Background task context
- Security diagnostics and logs

## Trust Boundaries

- External clients to generated REST APIs
- Browser users to Studio/admin surfaces
- AI/MCP agents to generated tools
- Generated schemas to runtime enforcement
- Request tenant context to trusted server-side tenant context
- Background task payloads to trusted task context
- Migration generation to database execution

## Primary Risks

- Broken authentication
- Broken object-level authorization
- Cross-tenant access
- Restricted field read/write
- Schema bypass through raw payloads
- MCP overbroad credentials
- Studio/admin exposure
- SQL injection or unsafe identifier handling
- Malformed or oversized payloads
- Secret leakage
- Insecure production configuration

## Implemented Controls

- `aksara doctor security-check` reports security configuration issues.
- `aksara doctor production-check` treats blocking production issues as
  deployment blockers.
- `studio_expose_in_production=False` and `studio_require_auth=True` are secure
  Studio defaults.
- `mcp_enabled=False` keeps MCP disabled unless explicitly enabled.
- HMAC AI/MCP agent tokens support short-lived credential validation.
- `Principal` provides a central identity model for users, AI/MCP agents,
  anonymous callers, and system tasks.
- `PolicyEngine` evaluates authorization, field visibility, field writability,
  tenant filters, required scopes, required audience, and tenant-required
  operations.
- Runtime payload enforcement rejects forbidden fields with structured
  `denied_fields` responses in covered generated REST create/update paths.
- Tenant-aware policy checks deny cross-tenant resource access and fail closed
  when tenant context is required but missing.
- MCP helpers validate scopes, audience, tenant binding, token expiration, and
  token metadata.
- PostgreSQL RLS helpers and tenant context utilities are available for
  multi-tenant deployments that enable database-level tenant isolation.
- Background tasks can carry trusted tenant provenance captured at enqueue time.
- Bounded adversarial tests cover generated filters, ordering, pagination,
  serializers, migration identifiers/defaults, runtime field enforcement, and
  malformed or oversized payloads.

## Known Limitations

- Aksara does not currently make a blanket production-readiness claim.
- Generated schemas are not security controls; applications must rely on
  server-side runtime enforcement.
- Direct MCP tool-call enforcement is limited where tool calls bypass REST
  write paths.
- Manager-level bulk update/upsert principal enforcement is not universal;
  helper-level validation is available for application paths that integrate it.
- OpenAPI fuzzing requires optional tooling such as Schemathesis.
- Private security matrix enforcement is warning-only unless
  `AKSARA_REQUIRE_SECURITY_MATRIX=true`.
- Supply-chain gates, release-security automation, and external review remain
  planned before a production-mode claim.
