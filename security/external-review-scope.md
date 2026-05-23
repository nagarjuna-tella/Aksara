# External Security Review Scope

## Purpose

Define the scope for an external review before any production-mode claim.

## In Scope

- Principal and PolicyEngine
- Runtime field enforcement
- Tenant isolation
- MCP credential handling
- AI/MCP schema exposure
- Studio/admin access controls
- Generated REST CRUD authorization
- Filter/order/pagination query generation
- Serializer payload validation
- Migration SQL generation
- Background task tenant context
- Package release pipeline

## Out of Scope

- Application-specific business logic outside Aksara core
- Third-party services not controlled by Aksara
- Social engineering
- Physical attacks

## Review Questions

- Can forbidden fields be mutated through any generated surface?
- Can tenant boundaries be bypassed?
- Can MCP tokens gain broader access than intended?
- Can generated SQL be influenced unsafely?
- Can release artifacts be tampered with?

## Expected Deliverables

- Findings by severity
- Reproduction steps
- Affected components
- Recommended fixes
- Retest notes
