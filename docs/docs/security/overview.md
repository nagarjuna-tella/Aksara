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

- Aksara does not currently make a blanket production-readiness claim.
- Private security matrix enforcement is optional unless
  `AKSARA_REQUIRE_SECURITY_MATRIX=true`.
- OpenAPI fuzzing is a placeholder unless Schemathesis is installed.
- Bulk/upsert principal enforcement is helper-level unless integrated by the
  application path.
- Direct MCP tool-call runtime enforcement is limited where tool calls bypass
  REST write paths.
- Supply-chain CI/release gates are planned before a production-mode claim.
- External security review is planned before a production-mode claim.

## Recommended Production Workflow

1. Set secure production configuration.
2. Run `aksara doctor security-check`.
3. Run `aksara doctor production-check`.
4. Review generated surfaces exposed by the application.
5. Configure private security matrix enforcement if used in your release
   process.

## More Detail

- [Threat Model](threat-model.md)
- [Production Hardening](production-hardening.md)
- [Authentication and Principals](authentication.md)
- [Field-Level Permissions](field-level-permissions.md)
- [Multi-Tenancy Security](multi-tenancy.md)
- [AI and MCP Security Boundaries](ai-mcp-boundaries.md)
- [Security Coverage](security-coverage.md)
- [Release Security](release-security.md)
