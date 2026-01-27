# Tenant Middleware

Multi-tenant application support.

---

## Overview

`TenantMiddleware` enables multi-tenancy by identifying the current tenant from requests:

```python
from aksara import Aksara
from aksara.middleware import TenantMiddleware

app = Aksara()
app.add_middleware(
    TenantMiddleware,
    header_name="X-Tenant-ID",
)
```

---

## Tenant Resolution

Tenants can be identified from multiple sources:

### Header-Based

```python
app.add_middleware(
    TenantMiddleware,
    header_name="X-Tenant-ID",
)

# Client sends: X-Tenant-ID: acme-corp
```

### Subdomain-Based

```python
app.add_middleware(
    TenantMiddleware,
    resolver="subdomain",
)

# acme.myapp.com → tenant_id = "acme"
# beta.myapp.com → tenant_id = "beta"
```

### Path-Based

```python
app.add_middleware(
    TenantMiddleware,
    resolver="path",
    path_prefix="/tenant/",
)

# /tenant/acme/api/users → tenant_id = "acme"
```

### Custom Resolver

```python
async def resolve_tenant(request):
    # Custom logic: check JWT, database, etc.
    token = request.headers.get("Authorization")
    if token:
        payload = decode_jwt(token)
        return payload.get("tenant_id")
    return None

app.add_middleware(
    TenantMiddleware,
    resolver=resolve_tenant,
)
```

---

## Configuration

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `header_name` | `str` | `"X-Tenant-ID"` | Header for tenant ID |
| `resolver` | `str\|callable` | `"header"` | Resolution strategy |
| `default_tenant` | `str` | `None` | Fallback tenant |
| `required` | `bool` | `False` | Require tenant ID |

### With Default Tenant

```python
app.add_middleware(
    TenantMiddleware,
    header_name="X-Tenant-ID",
    default_tenant="default",  # Use if no tenant specified
)
```

### Required Tenant

```python
app.add_middleware(
    TenantMiddleware,
    header_name="X-Tenant-ID",
    required=True,  # Return 400 if no tenant
)
```

---

## Accessing Tenant ID

### Context Variable

```python
from aksara.middleware import tenant_id_var

@app.get("/api/data")
async def get_data(request):
    tenant_id = tenant_id_var.get()
    print(f"Tenant: {tenant_id}")
    ...
```

### Request State

```python
@app.get("/api/data")
async def get_data(request):
    tenant_id = request.state.tenant_id
    ...
```

---

## Multi-Tenant Queries

### Automatic Filtering

```python
from aksara.middleware import tenant_id_var

class TenantManager:
    """Custom manager that filters by tenant."""
    
    def get_queryset(self):
        tenant_id = tenant_id_var.get()
        return super().get_queryset().filter(tenant_id=tenant_id)

class Post(Model):
    tenant_id = fields.String(max_length=100)
    title = fields.String(max_length=200)
    
    objects = TenantManager()
```

### Manual Filtering

```python
from aksara.middleware import tenant_id_var

@app.get("/api/posts")
async def list_posts(request):
    tenant_id = tenant_id_var.get()
    posts = await Post.objects.filter(tenant_id=tenant_id).all()
    return [{"id": str(p.id), "title": p.title} for p in posts]
```

### Creating with Tenant

```python
from aksara.middleware import tenant_id_var

@app.post("/api/posts")
async def create_post(request):
    tenant_id = tenant_id_var.get()
    data = await request.json()
    
    post = await Post.objects.create(
        tenant_id=tenant_id,
        **data,
    )
    return {"id": str(post.id)}
```

---

## Tenant Validation

### Validate Against Database

```python
async def validate_tenant(request):
    """Resolve and validate tenant."""
    tenant_id = request.headers.get("X-Tenant-ID")
    
    if not tenant_id:
        return None
    
    # Check tenant exists and is active
    tenant = await Tenant.objects.filter(
        id=tenant_id,
        is_active=True,
    ).first()
    
    if not tenant:
        return None  # Invalid tenant
    
    return tenant.id

app.add_middleware(
    TenantMiddleware,
    resolver=validate_tenant,
    required=True,
)
```

### Tenant Context Object

```python
from contextvars import ContextVar

tenant_var: ContextVar[Tenant] = ContextVar("tenant")

async def resolve_tenant_object(request):
    """Resolve full tenant object."""
    tenant_id = request.headers.get("X-Tenant-ID")
    
    if not tenant_id:
        return None
    
    tenant = await Tenant.objects.filter(id=tenant_id).first()
    if tenant:
        tenant_var.set(tenant)  # Store full object
        return tenant.id
    
    return None

# Access full tenant object
def get_current_tenant() -> Tenant:
    return tenant_var.get()
```

---

## Database Per Tenant

For complete isolation, use separate databases:

```python
from aksara.middleware import tenant_id_var

# Database URLs per tenant
TENANT_DATABASES = {
    "acme": "postgresql://localhost/acme_db",
    "beta": "postgresql://localhost/beta_db",
}

async def get_tenant_connection():
    tenant_id = tenant_id_var.get()
    db_url = TENANT_DATABASES.get(tenant_id)
    
    if not db_url:
        raise ValueError(f"No database for tenant: {tenant_id}")
    
    return await create_connection(db_url)
```

---

## Schema Per Tenant

For PostgreSQL schema-based isolation:

```python
from aksara.middleware import tenant_id_var

class TenantMiddleware:
    async def __call__(self, scope, receive, send):
        tenant_id = extract_tenant(scope)
        tenant_id_var.set(tenant_id)
        
        # Set PostgreSQL search_path
        async with db.connection() as conn:
            await conn.execute(f"SET search_path TO {tenant_id}, public")
        
        await self.app(scope, receive, send)
```

---

## Excluding Paths

Some paths shouldn't require tenant:

```python
app.add_middleware(
    TenantMiddleware,
    header_name="X-Tenant-ID",
    required=True,
    exclude_paths=[
        "/health",
        "/metrics",
        "/auth/login",
        "/docs",
    ],
)
```

---

## Complete Example

```python
from aksara import Aksara
from aksara.middleware import TenantMiddleware, tenant_id_var
from myapp.models import Tenant, Post


# Custom tenant resolver with validation
async def resolve_and_validate_tenant(request):
    """Resolve tenant from header and validate."""
    tenant_id = request.headers.get("X-Tenant-ID")
    
    if not tenant_id:
        return None
    
    # Validate tenant exists
    tenant = await Tenant.objects.filter(
        slug=tenant_id,
        is_active=True,
    ).first()
    
    if not tenant:
        return None
    
    # Store tenant slug as ID
    return tenant.slug


# Create app
app = Aksara()

# Add tenant middleware
app.add_middleware(
    TenantMiddleware,
    resolver=resolve_and_validate_tenant,
    required=True,
    exclude_paths=[
        "/health",
        "/docs",
        "/openapi.json",
    ],
)


# Tenant-aware endpoints
@app.get("/api/posts")
async def list_posts(request):
    """List posts for current tenant."""
    tenant_id = tenant_id_var.get()
    
    posts = await Post.objects.filter(
        tenant_id=tenant_id,
    ).order_by("-created_at").all()
    
    return {
        "tenant": tenant_id,
        "posts": [{"id": str(p.id), "title": p.title} for p in posts],
    }


@app.post("/api/posts")
async def create_post(request):
    """Create post for current tenant."""
    tenant_id = tenant_id_var.get()
    data = await request.json()
    
    post = await Post.objects.create(
        tenant_id=tenant_id,
        title=data["title"],
        content=data["content"],
    )
    
    return {"id": str(post.id), "tenant": tenant_id}


@app.get("/api/tenant/info")
async def tenant_info(request):
    """Get current tenant information."""
    tenant_id = tenant_id_var.get()
    
    tenant = await Tenant.objects.get(slug=tenant_id)
    
    return {
        "id": tenant_id,
        "name": tenant.name,
        "plan": tenant.plan,
        "features": tenant.features,
    }


# Health check (excluded from tenant requirement)
@app.get("/health")
async def health():
    return {"status": "healthy"}
```

**Usage:**
```bash
# Request with tenant header
curl -H "X-Tenant-ID: acme-corp" http://localhost:8000/api/posts

# Missing tenant (returns 400)
curl http://localhost:8000/api/posts

# Health check (no tenant needed)
curl http://localhost:8000/health
```

---

## Related Documentation

- [Middleware Overview](index.md) — All middleware
- [Request ID](request-id.md) — Request tracing
- [Logging](logging.md) — Request logging
