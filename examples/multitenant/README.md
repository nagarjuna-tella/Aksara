# Multitenant Example

A minimal multi-tenant SaaS backend demonstrating Aksara patterns.

## Features

- **Tenant model** with:
  - Name, slug (unique URL identifier)
  - Custom domain support
  - Subscription plan
  - Active status

- **User model** (tenant-scoped) with:
  - Foreign key to Tenant
  - Email, name, role
  - Roles: admin, member, viewer

- **Project model** (tenant-scoped) with:
  - Foreign key to Tenant
  - Name, description
  - Public visibility flag

- **TenantMiddleware** for:
  - Automatic tenant resolution from headers
  - Domain-based tenant resolution
  - Query scoping to current tenant

## Quick Start

```bash
cd examples/multitenant
export DATABASE_URL=postgresql://postgres:password@localhost:5432/aksara_multitenant
createdb aksara_multitenant
aksara makemigrations --app examples.multitenant.models
aksara migrate
uvicorn examples.multitenant.main:app --reload
```

## Tenant Resolution

The middleware resolves tenant from (in order):

1. `X-Tenant-ID` header (UUID)
2. `X-Tenant-Slug` header (string)
3. `Host` header (domain-based)

## Example Requests

### Create a tenant

```bash
curl -X POST http://localhost:8000/api/tenants/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "slug": "acme-corp",
    "plan": "pro"
  }'
```

### Create a user (with tenant context)

```bash
curl -X POST http://localhost:8000/api/users/ \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Slug: acme-corp" \
  -d '{
    "email": "admin@acme.com",
    "name": "Admin User",
    "role": "admin"
  }'
```

### List users (scoped to tenant)

```bash
curl http://localhost:8000/api/users/ \
  -H "X-Tenant-Slug: acme-corp"
```

## Isolation Strategy

This example uses **Row-Level Isolation**:
- All tenant-scoped models have a `tenant_id` foreign key
- Queries are automatically scoped by the middleware
- Simple to implement and scale

### Future: Multi-Schema

In v1.x, Aksara will support schema-based isolation:
- Each tenant gets its own PostgreSQL schema
- Better data isolation for compliance
- Use `SET search_path` for tenant switching

## Endpoints

| Endpoint | Scoped | Description |
|----------|--------|-------------|
| `/api/tenants/` | No | Tenant management |
| `/api/users/` | Yes | Users within tenant |
| `/api/projects/` | Yes | Projects within tenant |

## Headers

| Header | Description |
|--------|-------------|
| `X-Tenant-ID` | Tenant UUID |
| `X-Tenant-Slug` | Tenant slug (e.g., "acme-corp") |
