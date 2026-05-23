# Multi-Tenancy Security

## Goal

Tenant data must not leak across tenants through generated or internal surfaces.

## Current Controls

- Principal tenant context through `Principal.tenant_id`
- Tenant-aware policy checks through `PolicyEngine.can()`
- Tenant query constraints through `PolicyEngine.query_filter()`
- Runtime denial for `tenant_id` mutation in covered write paths
- Client-forged tenant headers are not treated as authoritative by principal
  resolution
- `TenantMiddleware` can establish trusted tenant context from configured
  server-side resolution rules
- PostgreSQL RLS helpers and DB session variables are available through
  tenant-aware model and connection utilities
- Background task tenant provenance can be captured at enqueue time and restored
  for task execution

## Required Invariants

- Tenant A cannot read tenant B data.
- Tenant A cannot write tenant B data.
- Tenant context cannot be forged by the client.
- Missing tenant context fails closed where tenant context is required.
- System principals must use explicit trusted tenant context for tenant-scoped
  work.
- Tenant fields such as `tenant_id` cannot be overwritten through covered
  request payload paths.

## Tenant Context

Tenant context should come from trusted middleware or server-side context, not
from raw client headers. Aksara's principal resolution intentionally ignores raw
tenant headers as authoritative identity.

For tenant-aware policy checks, `tenant_required=True` denies non-system
principals that do not carry tenant context.

## Database Isolation

For multi-tenant deployments, enable and test database-level isolation where it
is required:

```bash
AKSARA_MULTI_TENANT=true
AKSARA_RLS_ENABLED=true
```

`TenantModel`, RLS policy helpers, and `apply_tenant_context()` provide
defense-in-depth when PostgreSQL RLS is part of the deployment posture.

## Application Responsibilities

- Configure tenant middleware correctly.
- Avoid trusting raw tenant headers.
- Enable and test RLS where required.
- Ensure custom query paths apply tenant filters.
- Ensure custom write paths call runtime payload enforcement helpers.
- Use private matrix/release gates if needed by the release process.

## Known Limitations

- Policy-layer checks do not replace database RLS for deployments that require
  database-enforced tenant isolation.
- System principals can intentionally operate across tenants unless given an
  explicit tenant context; application code must use that power carefully.
- Studio, direct MCP tools, custom endpoints, and background tasks need explicit
  integration when they perform tenant-scoped reads or writes outside covered
  generated paths.
