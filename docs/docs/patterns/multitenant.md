# Multitenant Pattern

A tenant-scoped SaaS backend with automatic query isolation based on request context.

## Quick Start

```bash
aksara startproject mysaas --template multitenant
cd mysaas
pip install -e ".[dev]"
aksara makemigrations --app app.models
aksara migrate
aksara run main:app --reload
```

## Concepts

### Row-Level Multitenancy

This pattern uses **row-level isolation**:

- All tenant-scoped models have a `tenant_id` foreign key
- Middleware extracts tenant from request headers
- Queries are filtered to the current tenant's data
- Simple to implement and scale horizontally

### Tenant Resolution

Tenants are resolved from requests in this order:

1. `X-Tenant-ID` header (UUID)
2. `X-Tenant-Slug` header (slug string)
3. `Host` header (domain-based routing)

## Models

### Tenant

```python
class Tenant(Model):
    """SaaS tenant/organization."""
    
    name = fields.String(max_length=200, ai_description="Tenant name")
    slug = fields.String(
        max_length=100,
        unique=True,
        ai_description="URL-friendly identifier",
    )
    domain = fields.String(
        max_length=255,
        nullable=True,
        unique=True,
        ai_description="Custom domain (e.g., acme.example.com)",
    )
    plan = fields.String(
        max_length=50,
        default="free",
        ai_description="Subscription plan: free, pro, enterprise",
    )
    is_active = fields.Boolean(default=True, ai_description="Tenant active status")
    created_at = fields.DateTime(auto_now_add=True)
    
    class Meta:
        table_name = "tenants"
        ai_name = "Tenant"
```

### User (Tenant-Scoped)

```python
class User(Model):
    """User within a tenant."""
    
    tenant = fields.ForeignKey(
        Tenant,
        on_delete="CASCADE",
        related_name="users",
        ai_description="User's tenant",
    )
    email = fields.Email(ai_description="User email")
    name = fields.String(max_length=200, ai_description="User name")
    role = fields.String(
        max_length=50,
        default="member",
        ai_description="Tenant role: admin, member, viewer",
    )
    is_active = fields.Boolean(default=True)
    created_at = fields.DateTime(auto_now_add=True)
    
    class Meta:
        table_name = "tenant_users"
        ai_name = "TenantUser"
```

### Project (Tenant-Scoped)

```python
class Project(Model):
    """Project within a tenant."""
    
    tenant = fields.ForeignKey(
        Tenant,
        on_delete="CASCADE",
        related_name="projects",
        ai_description="Project's tenant",
    )
    name = fields.String(max_length=200, ai_description="Project name")
    description = fields.Text(nullable=True)
    is_public = fields.Boolean(
        default=False,
        ai_description="Public projects visible across tenants",
    )
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)
    
    class Meta:
        table_name = "projects"
        ai_name = "Project"
```

## Tenant Middleware

```python
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Context variable for current tenant
current_tenant: ContextVar[Optional["Tenant"]] = ContextVar(
    "current_tenant", 
    default=None
)


def get_current_tenant() -> Optional["Tenant"]:
    """Get the current tenant from context."""
    return current_tenant.get()


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to resolve and set the current tenant.
    
    Resolution order:
    1. X-Tenant-ID header (UUID)
    2. X-Tenant-Slug header (slug)
    3. Host header (domain-based)
    """
    
    async def dispatch(self, request: Request, call_next):
        from .models import Tenant
        
        tenant = None
        
        # Try X-Tenant-ID header
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            try:
                tenant = await Tenant.objects.get(id=tenant_id)
            except Exception:
                pass
        
        # Try X-Tenant-Slug header
        if not tenant:
            tenant_slug = request.headers.get("X-Tenant-Slug")
            if tenant_slug:
                try:
                    tenant = await Tenant.objects.filter(slug=tenant_slug).first()
                except Exception:
                    pass
        
        # Try Host header (domain-based)
        if not tenant:
            host = request.headers.get("Host", "").split(":")[0]
            if host and host not in ("localhost", "127.0.0.1"):
                try:
                    tenant = await Tenant.objects.filter(domain=host).first()
                except Exception:
                    pass
        
        # Set tenant in context
        token = current_tenant.set(tenant)
        try:
            response = await call_next(request)
            return response
        finally:
            current_tenant.reset(token)
```

## Tenant-Scoped ViewSets

```python
class UserViewSet(ModelViewSet):
    """User API - scoped to current tenant."""
    
    model = User
    serializer_class = UserSerializer
    prefix = "/api/users"
    tags = ["Users"]
    
    async def get_queryset(self):
        """Filter users to current tenant."""
        tenant = get_current_tenant()
        if not tenant:
            return []
        return await self.model.objects.filter(tenant_id=tenant.id).all()
    
    async def perform_create(self, data: dict) -> User:
        """Auto-assign tenant on create."""
        tenant = get_current_tenant()
        if not tenant:
            raise ValueError("Tenant context required")
        data["tenant_id"] = tenant.id
        return await super().perform_create(data)
```

## API Endpoints

### Tenants (Admin)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tenants/` | List all tenants |
| POST | `/api/tenants/` | Create a tenant |
| GET | `/api/tenants/{id}/` | Get tenant details |
| PUT | `/api/tenants/{id}/` | Update a tenant |
| DELETE | `/api/tenants/{id}/` | Delete a tenant |

### Users (Tenant-Scoped)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/` | List users in tenant |
| POST | `/api/users/` | Create a user in tenant |
| GET | `/api/users/{id}/` | Get user details |
| PUT | `/api/users/{id}/` | Update a user |
| DELETE | `/api/users/{id}/` | Delete a user |

### Projects (Tenant-Scoped)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/` | List projects in tenant |
| POST | `/api/projects/` | Create a project in tenant |
| GET | `/api/projects/{id}/` | Get project details |
| PUT | `/api/projects/{id}/` | Update a project |
| DELETE | `/api/projects/{id}/` | Delete a project |

## Example Requests

### Create a Tenant

```bash
curl -X POST http://localhost:8000/api/tenants/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "slug": "acme-corp",
    "plan": "pro"
  }'
```

### Create a User (with Tenant Context)

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

### List Users (Scoped to Tenant)

```bash
curl http://localhost:8000/api/users/ \
  -H "X-Tenant-Slug: acme-corp"
```

### Create a Project

```bash
curl -X POST http://localhost:8000/api/projects/ \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Slug: acme-corp" \
  -d '{
    "name": "Website Redesign",
    "description": "Q2 website refresh project"
  }'
```

## Request Headers

| Header | Format | Description |
|--------|--------|-------------|
| `X-Tenant-ID` | UUID | Tenant's UUID |
| `X-Tenant-Slug` | String | Tenant's URL slug |
| `Host` | Domain | Custom domain (for production) |

## Isolation Strategies

### 1. Row-Level (This Pattern)

- All data in same database
- Tenant ID column on all tables
- Filter queries by tenant
- **Pros**: Simple, easy to scale
- **Cons**: Requires discipline in queries

### 2. Schema-Level (Future)

- Separate PostgreSQL schema per tenant
- `SET search_path = tenant_schema`
- **Pros**: Better isolation
- **Cons**: More complex migrations

### 3. Database-Level

- Separate database per tenant
- Full isolation
- **Pros**: Maximum isolation
- **Cons**: Complex management, expensive

## Extending the Pattern

### Add Billing/Subscription

```python
class Subscription(Model):
    """Tenant subscription."""
    
    tenant = fields.OneToOneField(Tenant, on_delete="CASCADE")
    plan = fields.String(max_length=50)
    stripe_subscription_id = fields.String(max_length=100, nullable=True)
    current_period_start = fields.DateTime()
    current_period_end = fields.DateTime()
    status = fields.String(max_length=50)  # active, past_due, canceled
    
    class Meta:
        table_name = "subscriptions"
```

### Add Usage Tracking

```python
class UsageRecord(Model):
    """Track tenant resource usage."""
    
    tenant = fields.ForeignKey(Tenant, on_delete="CASCADE")
    metric = fields.String(max_length=100)  # api_calls, storage_bytes, users
    value = fields.Integer()
    recorded_at = fields.DateTime(auto_now_add=True)
    period_start = fields.Date()
    
    class Meta:
        table_name = "usage_records"
```

### Add Feature Flags

```python
class FeatureFlag(Model):
    """Per-tenant feature flags."""
    
    tenant = fields.ForeignKey(Tenant, on_delete="CASCADE")
    name = fields.String(max_length=100)
    enabled = fields.Boolean(default=False)
    
    class Meta:
        table_name = "feature_flags"
        unique_together = [("tenant", "name")]


def has_feature(tenant: Tenant, feature: str) -> bool:
    """Check if tenant has a feature enabled."""
    # Implementation...
```

## Security Considerations

1. **Always validate tenant context** - Never allow cross-tenant data access
2. **Use middleware consistently** - All tenant-scoped endpoints need tenant resolution
3. **Audit tenant access** - Log tenant ID with all operations
4. **Test isolation** - Write tests that verify data isolation

## Next Steps

- [Blog Pattern](blog.md) - Content management
- [CRM Pattern](crm.md) - Sales pipeline
- [Middleware](../middleware/index.md) - Custom middleware
