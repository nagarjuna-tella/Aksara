# Tutorial: Multi-Tenant SaaS Application

Build a SaaS application where multiple customers (tenants) share the same codebase but have isolated data.

---

## What You'll Build

A multi-tenant application with:

- ✅ Tenant isolation (customers can't see each other's data)
- ✅ Subdomain-based tenant routing (acme.yourapp.com)
- ✅ Per-tenant configuration
- ✅ Tenant admin interface

**Time:** ~45 minutes

**Difficulty:** Intermediate

---

## What is Multi-Tenancy?

**Multi-tenancy** means one application serves multiple customers (tenants), each with their own isolated data.

```
                         Your SaaS App
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
   ┌──────────┐        ┌──────────┐        ┌──────────┐
   │  Acme    │        │  Globex  │        │  Initech │
   │  Corp    │        │  Inc     │        │  LLC     │
   ├──────────┤        ├──────────┤        ├──────────┤
   │ Users: 50│        │ Users: 20│        │ Users: 5 │
   │ Data: 1GB│        │ Data: 500MB       │ Data: 100MB
   └──────────┘        └──────────┘        └──────────┘
   
   acme.yourapp.com    globex.yourapp.com  initech.yourapp.com
```

**Each tenant:**
- Has their own users
- Has their own data
- Can't see other tenants' data
- May have different plans/features

---

## Tenant Isolation Strategies

| Strategy | How It Works | Best For |
|----------|--------------|----------|
| **Shared Database** | All tenants in one DB, filtered by tenant_id | Simple apps, cost-effective |
| **Schema per Tenant** | Separate PostgreSQL schema per tenant | Medium isolation |
| **Database per Tenant** | Completely separate database | Maximum isolation, enterprise |

This tutorial uses **Shared Database** — the most common approach.

---

## Step 1: Set Up the Project

```bash
# Create project
aksara startproject saas_app
cd saas_app

# Install dependencies
pip install aksara[all]

# Create apps
aksara startapp tenants
aksara startapp core
```

### Configure Settings

```python
# saas_app/settings.py
import os

AKSARA = {
    "DEBUG": True,
    "DATABASE_URL": os.getenv("DATABASE_URL"),
    "INSTALLED_APPS": ["tenants", "core"],
    
    # Multi-tenant settings
    "MULTI_TENANT": True,
    "TENANT_MODEL": "tenants.Tenant",
    "TENANT_HEADER": "X-Tenant-ID",      # Header-based routing
    "TENANT_SUBDOMAIN": True,             # Also support subdomains
}
```

---

## Step 2: Create the Tenant Model

The Tenant model represents a customer organization.

```python
# tenants/models.py
from aksara import Model, fields

class Tenant(Model):
    """
    A tenant (customer organization) in the SaaS application.
    
    Each tenant has their own:
    - Users
    - Data
    - Settings
    - Subscription plan
    """
    
    # Identity
    name = fields.String(max_length=100)
    slug = fields.String(max_length=50, unique=True)  # acme, globex, etc.
    domain = fields.String(max_length=100, nullable=True, unique=True)
    
    # Subscription
    plan = fields.String(
        max_length=20,
        default="free"
    )
    
    # Status
    is_active = fields.Boolean(default=True, ai_agent_writable=False)
    
    # Custom settings per tenant
    settings = fields.JSON(default=dict)
    
    class Meta:
        table_name = "tenants"
    
    def __str__(self):
        return self.name


class TenantUser(Model):
    """
    Links users to tenants with roles.
    
    A user can belong to multiple tenants with different roles.
    """
    
    tenant = fields.ForeignKey(
        Tenant,
        on_delete="CASCADE",
        related_name="members"
    )
    user = fields.ForeignKey(
        "core.User",
        on_delete="CASCADE",
        related_name="memberships"
    )
    role = fields.String(
        max_length=20,
        default="member"
    )
    
    class Meta:
        table_name = "tenant_users"
        unique_together = [("tenant", "user")]  # User can only be in tenant once
```

**Understanding the models:**

| Model | Purpose |
|-------|---------|
| `Tenant` | Represents a customer organization |
| `TenantUser` | Links users to tenants with roles |

---

## Step 3: Create the User Model

```python
# core/models.py
from aksara import Model, fields

class User(Model):
    """
    A user in the SaaS application.
    
    Users can belong to multiple tenants.
    """
    
    email = fields.Email(unique=True, ai_sensitive=True)
    name = fields.String(max_length=100)
    password = fields.String(max_length=128)
    is_active = fields.Boolean(default=True, ai_agent_writable=False)
    
    class Meta:
        table_name = "users"
```

---

## Step 4: Create Tenant-Aware Base Model

This is the key to multi-tenancy: a base model that automatically filters by tenant.

```python
# core/models.py (continued)
from aksara.middleware import get_current_tenant

class TenantModel(Model):
    """
    Base model for data that belongs to a tenant.
    
    All queries are automatically filtered by the current tenant.
    You never need to manually filter by tenant!
    """
    
    # Every tenant-scoped record has a tenant
    tenant = fields.ForeignKey(
        "tenants.Tenant",
        on_delete="CASCADE",
        related_name="+"  # Don't create reverse relation
    )
    
    class Meta:
        abstract = True  # Don't create a table for this
    
    @classmethod
    def get_queryset(cls):
        """
        Automatically filter by current tenant.
        
        This means:
        - Project.objects.all() → Only projects for current tenant
        - Project.objects.filter(name="X") → Only matches in current tenant
        """
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs
    
    async def save(self, **kwargs):
        """
        Automatically set tenant on save.
        
        New objects get the current tenant automatically.
        """
        if not self.tenant_id:
            tenant = get_current_tenant()
            if tenant:
                self.tenant_id = tenant.id
        await super().save(**kwargs)
```

**How automatic filtering works:**

```python
# Without TenantModel (manual filtering):
projects = await Project.objects.filter(tenant=current_tenant).all()

# With TenantModel (automatic filtering):
projects = await Project.objects.all()  # Automatically filtered!
```

---

## Step 5: Create Tenant-Scoped Models

Now create models that use TenantModel as their base.

```python
# core/models.py (continued)

class Project(TenantModel):
    """
    A project that belongs to a tenant.
    
    Inherits from TenantModel, so it's automatically
    filtered by tenant and has a tenant_id field.
    """
    
    name = fields.String(max_length=200)
    description = fields.Text(nullable=True)
    is_active = fields.Boolean(default=True)
    
    class Meta:
        table_name = "projects"


class Task(TenantModel):
    """A task within a project."""
    
    project = fields.ForeignKey(
        Project,
        on_delete="CASCADE",
        related_name="tasks"
    )
    title = fields.String(max_length=200)
    completed = fields.Boolean(default=False)
    assigned_to = fields.ForeignKey(
        User,
        on_delete="SET_NULL",
        nullable=True,
        related_name="tasks"
    )
    
    class Meta:
        table_name = "tasks"
```

---

## Step 6: Create Tenant Middleware

Middleware identifies the current tenant from each request.

```python
# tenants/middleware.py
from aksara.middleware import BaseMiddleware, set_current_tenant
from tenants.models import Tenant

class TenantMiddleware(BaseMiddleware):
    """
    Identifies the tenant for each request.
    
    Checks (in order):
    1. X-Tenant-ID header
    2. Subdomain (acme.yourapp.com → acme)
    3. Custom domain (acme.com → maps to tenant)
    """
    
    async def __call__(self, request, call_next):
        tenant = None
        
        # Method 1: Check header
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            tenant = await Tenant.objects.filter(id=tenant_id).first()
        
        # Method 2: Check subdomain
        if not tenant:
            host = request.headers.get("host", "")
            subdomain = host.split(".")[0]
            if subdomain and subdomain not in ["www", "api", "localhost"]:
                tenant = await Tenant.objects.filter(slug=subdomain).first()
        
        # Method 3: Check custom domain
        if not tenant:
            host = request.headers.get("host", "")
            tenant = await Tenant.objects.filter(domain=host).first()
        
        # Set the current tenant for this request
        if tenant:
            set_current_tenant(tenant)
        
        # Continue processing
        response = await call_next(request)
        
        return response
```

### Register the Middleware

```python
# saas_app/app.py
from aksara import Aksara
from tenants.middleware import TenantMiddleware

app = Aksara(
    database_url="postgresql://localhost/saas_app",
    debug=True,
)

# Add tenant middleware
app.add_middleware(TenantMiddleware)
```

---

## Step 7: Create ViewSets

### Tenant Management

```python
# tenants/views.py
from aksara.api import ModelViewSet, ViewSet, action
from aksara.permissions import IsAuthenticated, IsAdminUser
from .models import Tenant, TenantUser
from .serializers import TenantSerializer, TenantUserSerializer

class TenantViewSet(ModelViewSet):
    """
    Manage tenants (admin only).
    
    Regular users can't create tenants directly.
    """
    model = Tenant
    serializer_class = TenantSerializer
    permission_classes = [IsAdminUser]


class TenantMemberViewSet(ViewSet):
    """
    Manage members of the current tenant.
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=["GET"])
    async def list(self, request):
        """List all members of the current tenant."""
        from aksara.middleware import get_current_tenant
        
        tenant = get_current_tenant()
        if not tenant:
            return {"error": "No tenant context"}, 400
        
        members = await TenantUser.objects.filter(
            tenant=tenant
        ).select_related("user").all()
        
        return TenantUserSerializer(members, many=True).data
    
    @action(detail=False, methods=["POST"])
    async def invite(self, request):
        """Invite a user to the current tenant."""
        from aksara.middleware import get_current_tenant
        
        tenant = get_current_tenant()
        email = request.data.get("email")
        role = request.data.get("role", "member")
        
        # Find or create user
        user = await User.objects.filter(email=email).first()
        if not user:
            return {"error": "User not found"}, 404
        
        # Add to tenant
        membership, created = await TenantUser.objects.get_or_create(
            tenant=tenant,
            user=user,
            defaults={"role": role}
        )
        
        if not created:
            return {"error": "User is already a member"}, 400
        
        return TenantUserSerializer(membership).data, 201
```

### Tenant-Scoped ViewSets

```python
# core/views.py
from aksara.api import ModelViewSet
from aksara.permissions import IsAuthenticated
from .models import Project, Task
from .serializers import ProjectSerializer, TaskSerializer

class ProjectViewSet(ModelViewSet):
    """
    Manage projects.
    
    Because Project inherits from TenantModel,
    users only see their tenant's projects automatically!
    """
    model = Project
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    
    # No need to filter by tenant - TenantModel does it automatically!


class TaskViewSet(ModelViewSet):
    """Manage tasks within projects."""
    model = Task
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["project_id", "completed", "assigned_to_id"]
```

---

## Step 8: Create Serializers

```python
# tenants/serializers.py
from aksara.api import ModelSerializer
from .models import Tenant, TenantUser

class TenantSerializer(ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "slug", "domain", "plan", "is_active", "created_at"]

class TenantUserSerializer(ModelSerializer):
    class Meta:
        model = TenantUser
        fields = ["id", "tenant_id", "user_id", "role", "created_at"]
```

```python
# core/serializers.py
from aksara.api import ModelSerializer
from .models import Project, Task

class ProjectSerializer(ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "description", "is_active", "created_at"]
        # Note: tenant_id is automatically set, not exposed

class TaskSerializer(ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "project_id", "title", "completed", "assigned_to_id", "created_at"]
```

---

## Step 9: Configure Routes

```python
# saas_app/app.py
from aksara import Aksara
from aksara.api import Router
from tenants.middleware import TenantMiddleware
from tenants.views import TenantViewSet, TenantMemberViewSet
from core.views import ProjectViewSet, TaskViewSet

app = Aksara(
    database_url="postgresql://localhost/saas_app",
    debug=True,
)

# Add middleware
app.add_middleware(TenantMiddleware)

# Create router
router = Router()

# Admin routes (no tenant context needed)
router.register("admin/tenants", TenantViewSet)

# Tenant-scoped routes
router.register("members", TenantMemberViewSet, basename="members")
router.register("projects", ProjectViewSet)
router.register("tasks", TaskViewSet)

app.include_router(router, prefix="/api")
```

---

## Step 10: Run Migrations and Test

```bash
# Create tables
aksara makemigrations
aksara migrate

# Start server
aksara dev
```

### Create a Tenant

```bash
curl -X POST http://localhost:8000/api/admin/tenants/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -d '{"name": "Acme Corp", "slug": "acme", "plan": "pro"}'
```

### Create a Project (Tenant-Scoped)

```bash
# Using header
curl -X POST http://localhost:8000/api/projects/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer USER_TOKEN" \
  -H "X-Tenant-ID: TENANT_UUID" \
  -d '{"name": "Website Redesign"}'

# Using subdomain
curl -X POST http://acme.localhost:8000/api/projects/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer USER_TOKEN" \
  -d '{"name": "Website Redesign"}'
```

### List Projects (Automatically Filtered)

```bash
curl http://localhost:8000/api/projects/ \
  -H "Authorization: Bearer USER_TOKEN" \
  -H "X-Tenant-ID: TENANT_UUID"
# Only shows projects for this tenant!
```

---

## Per-Tenant Features

### Feature Flags Based on Plan

```python
# core/views.py
from aksara.middleware import get_current_tenant

class ProjectViewSet(ModelViewSet):
    model = Project
    
    async def create(self, request):
        tenant = get_current_tenant()
        
        # Check plan limits
        if tenant.plan == "free":
            project_count = await Project.objects.count()
            if project_count >= 3:
                return {"error": "Free plan limited to 3 projects"}, 403
        
        # Continue with creation
        return await super().create(request)
```

### Tenant-Specific Settings

```python
# Access tenant settings
tenant = get_current_tenant()

# Get setting with default
max_users = tenant.settings.get("max_users", 10)
feature_enabled = tenant.settings.get("feature_x_enabled", False)
```

---

## Testing Multi-Tenancy

```python
# tests/test_multi_tenant.py
import pytest
from aksara.testing import AksaraTestCase
from aksara.middleware import set_current_tenant
from tenants.models import Tenant
from core.models import Project

class TestMultiTenancy(AksaraTestCase):
    
    async def asyncSetUp(self):
        # Create two tenants
        self.tenant_a = await Tenant.objects.create(
            name="Tenant A",
            slug="tenant-a"
        )
        self.tenant_b = await Tenant.objects.create(
            name="Tenant B",
            slug="tenant-b"
        )
        
        # Create projects in each tenant
        set_current_tenant(self.tenant_a)
        self.project_a = await Project.objects.create(name="Project A")
        
        set_current_tenant(self.tenant_b)
        self.project_b = await Project.objects.create(name="Project B")
    
    async def test_tenant_isolation(self):
        """Tenants can only see their own data."""
        # As Tenant A
        set_current_tenant(self.tenant_a)
        projects = await Project.objects.all()
        assert len(projects) == 1
        assert projects[0].name == "Project A"
        
        # As Tenant B
        set_current_tenant(self.tenant_b)
        projects = await Project.objects.all()
        assert len(projects) == 1
        assert projects[0].name == "Project B"
    
    async def test_cannot_access_other_tenant_data(self):
        """Cannot access another tenant's specific record."""
        set_current_tenant(self.tenant_a)
        
        # Try to get Tenant B's project
        project = await Project.objects.filter(id=self.project_b.id).first()
        assert project is None  # Not found!
```

---

## What You Built

| Feature | How It Works |
|---------|--------------|
| Tenant isolation | TenantModel automatically filters queries |
| Subdomain routing | TenantMiddleware extracts tenant from subdomain |
| Header routing | X-Tenant-ID header for API clients |
| Per-tenant settings | JSON settings field on Tenant model |
| Plan-based limits | Check tenant.plan before allowing actions |

---

## Next Steps

- Add billing integration (Stripe)
- Add custom domain support
- Add tenant onboarding flow
- Add tenant admin dashboard
- Add usage tracking and limits

---

## Related Documentation

- [Middleware](../middleware/index.md) — Custom request processing
- [Permissions](../api/permissions.md) — Access control
- [Models](../orm/models.md) — Custom model base classes
