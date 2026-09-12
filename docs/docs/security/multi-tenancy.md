# Multi-Tenancy Security

## Goal

Tenant data must not leak across tenants through generated or internal surfaces.

## Current Controls

- Principal tenant context through `Principal.tenant_id`
- Tenant-aware policy checks through `PolicyEngine.can()`
- Tenant query constraints through `PolicyEngine.query_filter()`
- Runtime denial for `tenant_id` mutation in covered write paths
- Principal resolution does not read raw tenant headers directly; application
  middleware must validate any tenant value it places in trusted request state
- `TenantMiddleware` extracts a header or optional subdomain value; it does not
  verify membership or accept a custom resolver
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
from raw client headers. Aksara's principal resolution does not read those
headers directly, but its legacy user/agent paths can consume
`request.state.tenant_id`. Installing the extracting TenantMiddleware alongside
a user adapter does not add a membership check. Validate tenant selection before
placing it in trusted state, and keep the Principal and database context
consistent. See the [middleware boundary](../middleware/tenant.md) and the
[executable tenancy tutorial](../tutorials/ticket-desk-tenancy.md).

For tenant-aware policy checks, `tenant_required=True` denies non-system
principals that do not carry tenant context.

## Database Isolation

For multi-tenant deployments, apply reviewed migrations that enable/force RLS
and create the required policies. Run the application under a restricted role,
and test missing and cross-tenant reads/writes. The [tenancy tutorial](../tutorials/ticket-desk-tenancy.md) demonstrates this against PostgreSQL.

These environment variables declare deployment posture to security diagnostics:

```bash
AKSARA_MULTI_TENANT=true
AKSARA_RLS_ENABLED=true
```

The variables do **not** create policies, change database roles or prove RLS is
enforced. The environment-only `security.rls` check is not a database inspection.

`TenantModel`, RLS policy helpers, and `apply_tenant_context()` provide
defense-in-depth when PostgreSQL RLS is part of the deployment posture.

## Application Responsibilities

- Verify identity and membership before establishing trusted tenant context.
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
