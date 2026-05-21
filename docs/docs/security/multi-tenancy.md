# Multi-Tenancy Security

> **Status:** This document is part of the Aksara security-hardening milestone (Round 1).
> Current multi-tenancy controls are documented here. Cross-tenant adversarial tests
> are planned for Round 3.

## Goal

Tenant data must not leak across tenants through any generated or internal surface — REST,
Studio, MCP, AI Console, background tasks, or the admin dashboard.

## Current Controls

Aksara implements defense-in-depth for tenant isolation:

### 1. Application-layer tenant filtering (`TenantMiddleware`)

`TenantMiddleware` resolves tenant identity from the request (header, subdomain, path, or
custom resolver) and stores it in `request.state.tenant_id` and the `tenant_id_var`
context variable.

```python
# Accessing tenant in endpoints
from aksara.middleware.tenant import tenant_id_var
tenant_id = tenant_id_var.get()
```

Tenant context is resolved **server-side** from trusted sources. Client-supplied
tenant headers must not be accepted as authoritative.

### 2. PostgreSQL Row-Level Security (RLS)

`TenantModel` base class adds a `tenant_id` UUID field and supports RLS policies:

```sql
-- RLS policy (applied per connection)
CREATE POLICY tenant_isolation ON invoices
    USING (tenant_id = current_setting('aksara.current_tenant_id')::uuid);
```

Applied per-connection via `apply_tenant_context(connection)` from
`aksara/db/tenant_context.py`.

### 3. Database session variable

`build_enable_rls_sql()` and `apply_tenant_context()` set a PostgreSQL session
variable `aksara.current_tenant_id` for each connection, so RLS policies can
reference it.

### 4. Background task tenant binding

`tenant_id` is captured from `tenant_id_var` at task enqueue time and stored in
`TaskRecord.tenant_id`. Workers restore this context before task execution.

This ensures background tasks run with the tenant context of the enqueuing request —
not an empty context that would fail open.

```python
# From aksara/tasks.py — tenant captured at enqueue time
task_record = TaskRecord(
    tenant_id=tenant_id_var.get(),  # captured server-side
    ...
)
```

## Required Invariants

The following must hold for all surfaces. These are the cross-tenant test invariants
that adversarial tests (planned Round 3) must verify:

| Invariant | Surface | Status |
|-----------|---------|--------|
| Tenant A cannot read tenant B's records | REST read/list | Planned test |
| Tenant A cannot write tenant B's records | REST update/delete | Planned test |
| Tenant A cannot find tenant B's records via filter | REST list | Planned test |
| Tenant A cannot read via MCP tool | MCP list/read | Planned test |
| Tenant A cannot write via MCP tool | MCP update/delete | Planned test |
| Tenant A cannot access via Studio | Studio list/read | Planned test |
| Background tasks cannot access other tenants | Task mutation | Planned test |
| Empty/missing tenant context fails closed | All surfaces | Partial test |
| Client-forged tenant header is rejected | REST/MCP/Studio | Planned test |

## Planned Tests (Round 3)

Cross-tenant property-based tests will verify isolation across all surfaces:

```python
# Planned test structure
for user_a in tenant_a.users:
    for obj_b in tenant_b.objects:
        assert cannot_read(user_a, obj_b)           # REST read
        assert cannot_update(user_a, obj_b)         # REST update
        assert cannot_delete(user_a, obj_b)         # REST delete
        assert cannot_find_via_filter(user_a, obj_b)  # REST list filter
        assert cannot_find_via_mcp(user_a, obj_b)   # MCP list tool
        assert cannot_access_via_studio(user_a, obj_b)  # Studio
```

## Configuration

For multi-tenant deployments, set these environment variables:

```bash
AKSARA_MULTI_TENANT=true
AKSARA_RLS_ENABLED=true
```

The `aksara doctor production-check` command will warn if `AKSARA_MULTI_TENANT=true`
but `AKSARA_RLS_ENABLED` is not set.

## Known Risks

| Risk | Severity | Notes |
|------|----------|-------|
| Client forging tenant header | Critical | Must use server-side resolution only |
| Empty tenant context failing open | Critical | Middleware should fail closed |
| Background task losing tenant context | High | Fixed in v0.5.47; regression-tested |
| Cross-tenant access via ORM filter | Critical | Property tests planned Round 3 |
| Cross-tenant access via AI/MCP surfaces | Critical | Planned Round 3 |
