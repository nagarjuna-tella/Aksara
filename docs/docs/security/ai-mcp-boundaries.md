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
- AI/MCP mutation enabled without an explicit writable-field review assertion

Production release diagnostics require every result to pass. Set
`AKSARA_AI_WRITABLE_FIELDS_REVIEWED=true` only after every field on every
AI-exposed model has an explicit `ai_agent_writable` decision.

## Covered Behavior

- MCP disabled by default
- MCP exposure diagnostics
- MCP scope, audience, tenant, expiration, and token metadata helper coverage
- AI-sensitive field exclusion from generated AI/MCP schemas
- Runtime rejection of forbidden fields in covered REST create/update paths
- Tenant ID mutation denied in covered write paths
- Bounded adversarial tests against an actual generated CRUD application,
  including invalid relations, malformed and oversized payloads, forbidden and
  server-controlled fields, and unauthorized mutation
- A packaged reference-app gate that permits an authorized same-tenant
  catalog-described REST mutation and rejects the cross-tenant equivalent

## Known Limitations

- Replay protection storage is not implemented by core MCP helpers.
- Field-level MCP audit logs are planned.
- Aksara v0.6 provides an MCP-shaped catalog, not protocol transport or a
  protocol tool-call endpoint.
- Replay protection storage and token issuance are application concerns; core
  helpers validate claims but do not issue or revoke credentials.
- The stable execution claim covers catalog-described generated REST paths.
  Custom execution paths must integrate application authorization explicitly.
- External review is scoped in the release evidence and does not become an
  implied audit certification.
