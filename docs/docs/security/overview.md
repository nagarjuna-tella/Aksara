# Security Overview

Aksara is an AI-native application framework that generates multiple surfaces
from model definitions, including APIs, schemas, Studio/admin surfaces, AI/MCP
tooling, and migration behavior. Because generated surfaces multiply security
exposure, Aksara treats authorization, tenant isolation, and AI/MCP boundaries
as first-class security concerns.

## Current Security Controls

- Security diagnostics through `aksara doctor security-check`
- Strict production diagnostics through `aksara doctor production-check`
- Central `Principal` representation for users, AI/MCP agents, anonymous
  callers, and system tasks
- `PolicyEngine` for authorization decisions, field visibility, field
  writability, tenant filters, and payload validation
- Runtime payload enforcement for covered generated write paths
- Field-level controls for AI-sensitive and non-agent-writable fields
- Tenant-aware policy checks and tenant-required fail-closed decisions
- MCP credential validation helpers for scopes, audience, tenant binding,
  expiration, and token metadata
- Studio/MCP production exposure diagnostics
- Bounded adversarial tests for generated surfaces
- Migration safety controls that improve the reliability and integrity of
  generated schema changes (transactional application, advisory locking,
  checksum verification of applied migrations, and SQL-generation guardrails)
- Public security matrix example with optional private matrix enforcement

## Generated Surfaces

Generated REST routes, serializers, filters, ordering, pagination, migrations,
Studio/admin surfaces, AI prompt context, and MCP tool descriptions can all
expose security-relevant behavior. Aksara's public security controls focus on
server-side policy decisions and runtime checks rather than trusting generated
schemas as the boundary.

## Current Limitations

- Production support is bounded by the
  [v0.6 contract](../roadmap/v0-6-stability-contract.md); it is not a blanket
  claim for Studio or AI/agent features.
- `production-check --release` always requires a complete matrix. Deployment
  checks without `--release` keep missing-matrix findings advisory unless
  `AKSARA_REQUIRE_SECURITY_MATRIX=true`.
- Bulk/upsert principal enforcement is helper-level unless integrated by the
  application path.
- The Streamable HTTP MCP endpoint at `/mcp/` provides protocol discovery and
  execution for generated tools. `/ai/tools/mcp` remains an inspection catalog;
  it is not a second execution boundary.
- No external security audit certification is claimed; the review scope and
  release evidence are published for assessment.

## Recommended Production Workflow

1. Apply migrations with a migration role.
2. Run the application with a restricted role and forced RLS for tenant tables.
3. Review generated surfaces and AI-writable fields.
4. Run `aksara doctor production-check --release` with the project's complete
   security matrix.
5. Deploy only when every release diagnostic passes.

## More Detail

- [Threat Model](threat-model.md)
- [Production Hardening](production-hardening.md)
- [Authentication and Principals](authentication.md)
- [Field-Level Permissions](field-level-permissions.md)
- [Multi-Tenancy Security](multi-tenancy.md)
- [AI and MCP Security Boundaries](ai-mcp-boundaries.md)
- [Security Coverage](security-coverage.md)
- [Release Security](release-security.md)
