# AI and MCP Security Boundaries

## Core Principle

AI/MCP schemas are not security controls. Server-side runtime policy is the
security boundary.

Aksara can hide sensitive fields from AI/MCP-visible schemas and prompt context,
but a malicious or misconfigured client can still send crafted payloads.
Covered write paths must validate payloads against the resolved principal before
database writes.

## MCP Credential Controls

MCP credentials can be validated with:

- Scopes
- Audience
- Tenant binding
- Expiration
- Token IDs

Relevant helpers include `MCPCredentialClaims`, `principal_from_mcp_claims()`,
`require_scope()`, `require_any_scope()`, `require_all_scopes()`,
`require_mcp_audience()`, and `require_mcp_tenant()`.

## Field Controls

AI/MCP-facing field controls include:

- `ai_sensitive` fields, which are excluded from AI/MCP-visible schemas and AI
  context
- `ai_agent_writable=False`, which prevents AI/MCP principals from writing a
  field through runtime policy
- Read-only, tenant-owned, and system-only fields
- Runtime payload enforcement through `PolicyEngine.validate_payload()` and
  enforcement helpers

## Diagnostics

MCP is disabled by default through `mcp_enabled=False`.

When MCP is enabled, doctor checks report or block unsafe configuration:

- MCP enabled without authentication
- MCP enabled without scoped-token requirements
- MCP enabled without token TTL configuration
- MCP token TTL longer than 3600 seconds
- MCP enabled without audience requirements
- Multi-tenant MCP enabled without tenant-bound token requirements

Production diagnostics block critical MCP misconfiguration where applicable.

## Covered Behavior

- MCP disabled by default
- MCP exposure diagnostics
- MCP scope, audience, tenant, expiration, and token metadata helper coverage
- AI-sensitive field exclusion from generated AI/MCP schemas
- Runtime rejection of forbidden fields in covered REST create/update paths
- Tenant ID mutation denied in covered write paths
- Bounded adversarial tests for generated filters, ordering, serializers,
  runtime field enforcement, migration identifiers/defaults, malformed payloads,
  and oversized payloads

## Known Limitations

- Replay protection storage is not implemented by core MCP helpers.
- Field-level MCP audit logs are planned.
- Direct MCP tool-call runtime enforcement is limited where calls bypass covered
  REST write paths.
- OpenAPI fuzzing is a placeholder unless Schemathesis is installed.
- Supply-chain CI, release gates, and external review are planned before a
  production-mode claim.
