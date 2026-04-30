# Multitenant Example

A minimal multi-tenant SaaS backend demonstrating Aksara patterns.

## Features

- **Tenant model** with:
  - Name, slug (unique URL identifier)
  - Custom domain support
  - Subscription plan
  - Active status (`ai_agent_writable=False` — admin decisions only)

- **User model** (tenant-scoped) with:
  - Foreign key to Tenant
  - Email (`ai_sensitive=True` — PII excluded from AI context)
  - Name, role (`ai_agent_writable=False` — access control is human-managed)
  - Roles: admin, member, viewer

- **Project model** (tenant-scoped) with:
  - Foreign key to Tenant
  - Name, description
  - Public visibility flag

- **TenantMiddleware** for:
  - Automatic tenant resolution from headers
  - Domain-based tenant resolution
  - Query scoping to current tenant

## AI Metadata Patterns

| Attribute | Used On | Why |
|-----------|---------|-----|
| `ai_description` | Every field | Tells AI Console and MCP what each field means |
| `ai_sensitive=True` | `User.email` | PII — excluded from AI context |
| `ai_agent_writable=False` | `User.role`, `Tenant.is_active` | Access control and activation are human decisions |

## GDPR / DPDPA — AI Context Isolation

> **Important for SaaS developers**: In a multi-tenant system, AI context
> (the data sent to the AI Console, MCP exports, and LLM prompts) **must**
> be scoped to the current tenant. If your AI queries cross tenant boundaries,
> you leak data between organizations.
>
> Aksara's tenant middleware + query scoping handles this at the ORM level,
> but you must also ensure that any custom AI endpoints or prompt builders
> filter by `tenant_id` before sending data to an LLM.

## Quick Start

```bash
cd examples/multitenant

# Set up database interactively
aksara dbsetup

# Run migrations
aksara makemigrations --app examples.multitenant.models
aksara migrate

# Start server
aksara dev
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
