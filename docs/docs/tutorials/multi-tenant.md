# Tutorial: Multi-Tenant Application

Build a SaaS application with tenant isolation.

---

## What You'll Build

A multi-tenant SaaS application with:

- Tenant isolation at the database level
- Subdomain-based tenant routing
- Per-tenant configuration
- Admin interface for tenant management

**Time:** ~45 minutes

---

## Multi-Tenancy Concepts

### Tenant Isolation Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| **Shared Database** | All tenants in one DB, filtered by tenant_id | Simple apps, cost-effective |
| **Schema per Tenant** | Separate schema for each tenant | Medium isolation needs |
| **Database per Tenant** | Separate database for each tenant | Maximum isolation, enterprise |

This tutorial uses **Shared Database** with row-level filtering.

---

## Setup

### Create Project

```bash
vidyut startproject saas_app
cd saas_app
pip install vidyut[all]
```

### Configure Settings

```python
# saas_app/settings.py
import os

VIDYUT = {
    "DEBUG": True,
    "DATABASE_URL": os.getenv("DATABASE_URL", "postgresql://localhost/saas_app"),
    "INSTALLED_APPS": ["tenants", "core"],
    
    # Multi-tenant settings
    "MULTI_TENANT": True,
    "TENANT_MODEL": "tenants.Tenant",
    "TENANT_HEADER": "X-Tenant-ID",  # or use subdomain
    "TENANT_SUBDOMAIN": True,
}
```

### Create Apps

```bash
vidyut startapp tenants
vidyut startapp core
```

---

## Step 1: Create Tenant Model

```python
# tenants/models.py
from vidyut import Model, fields

class Tenant(Model):
    """A tenant (organization) in the SaaS application."""
    
    name = fields.StringField(max_length=100)
    slug = fields.StringField(max_length=50, unique=True)
    domain = fields.StringField(max_length=100, null=True, unique=True)
    
    # Subscription
    plan = fields.StringField(
        max_length=20,
        default="free",
        choices=["free", "starter", "pro", "enterprise"]
    )
    is_active = fields.BooleanField(default=True)
    
    # Settings
    settings = fields.JSONField(default=dict)
    
    class Meta:
        table_name = "tenants"
    
    def __str__(self):
        return self.name


class TenantUser(Model):
    """User membership in a tenant."""
    
    tenant = fields.ForeignKey(Tenant, on_delete="CASCADE", related_name="members")
    user = fields.ForeignKey("core.User", on_delete="CASCADE", related_name="memberships")
    role = fields.StringField(
        max_length=20,
        default="member",
        choices=["owner", "admin", "member", "viewer"]
    )
    
    class Meta:
        table_name = "tenant_users"
        unique_together = [("tenant", "user")]
```

---

## Step 2: Create Tenant-Aware Base Model

```python
# core/models.py
from vidyut import Model, fields
from vidyut.middleware import get_current_tenant

class TenantModel(Model):
    """Base model for tenant-scoped data."""
    
    tenant = fields.ForeignKey(
        "tenants.Tenant",
        on_delete="CASCADE",
        related_name="+"
    )
    
    class Meta:
        abstract = True
    
    @classmethod
    def get_queryset(cls):
        """Filter by current tenant automatically."""
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs
    
    async def save(self, **kwargs):
        """Set tenant on save if not set."""
        if not self.tenant_id:
            tenant = get_current_tenant()
            if tenant:
                self.tenant = tenant
        return await super().save(**kwargs)


class User(Model):
    """Application user (shared across tenants)."""
    
    email = fields.EmailField(unique=True)
    name = fields.StringField(max_length=100)
    password = fields.StringField(max_length=128)
    is_active = fields.BooleanField(default=True)
    
    class Meta:
        table_name = "users"


class Project(TenantModel):
    """A project within a tenant."""
    
    name = fields.StringField(max_length=200)
    description = fields.TextField(null=True)
    owner = fields.ForeignKey(User, on_delete="CASCADE", related_name="projects")
    
    class Meta:
        table_name = "projects"


class Task(TenantModel):
    """A task within a project."""
    
    project = fields.ForeignKey(Project, on_delete="CASCADE", related_name="tasks")
    title = fields.StringField(max_length=200)
    description = fields.TextField(null=True)
    status = fields.StringField(
        max_length=20,
        default="todo",
        choices=["todo", "in_progress", "review", "done"]
    )
    assignee = fields.ForeignKey(User, on_delete="SET_NULL", null=True)
    due_date = fields.DateTimeField(null=True)
    
    class Meta:
        table_name = "tasks"
```

---

## Step 3: Configure Tenant Middleware

```python
# saas_app/middleware.py
from vidyut.middleware import TenantMiddleware

class SubdomainTenantMiddleware(TenantMiddleware):
    """Resolve tenant from subdomain."""
    
    async def get_tenant(self, request):
        # Get subdomain from host
        host = request.headers.get("host", "")
        subdomain = host.split(".")[0]
        
        # Skip for main domain
        if subdomain in ["www", "api", "localhost"]:
            return None
        
        # Look up tenant
        from tenants.models import Tenant
        tenant = await Tenant.objects.filter(
            slug=subdomain,
            is_active=True
        ).first()
        
        return tenant
```

```python
# saas_app/app.py
from vidyut import Vidyut
from .middleware import SubdomainTenantMiddleware

app = Vidyut()

# Add tenant middleware
app.add_middleware(SubdomainTenantMiddleware)
```

---

## Step 4: Create Tenant-Aware Serializers

```python
# core/serializers.py
from vidyut.api import ModelSerializer
from .models import User, Project, Task

class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "created_at"]

class TaskSerializer(ModelSerializer):
    assignee = UserSerializer(read_only=True)
    
    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "status",
            "assignee", "due_date", "created_at"
        ]

class ProjectSerializer(ModelSerializer):
    owner = UserSerializer(read_only=True)
    task_count = SerializerMethodField()
    
    class Meta:
        model = Project
        fields = ["id", "name", "description", "owner", "task_count", "created_at"]
    
    async def get_task_count(self, obj):
        return await obj.tasks.count()

class ProjectDetailSerializer(ProjectSerializer):
    tasks = TaskSerializer(many=True, read_only=True)
    
    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ["tasks"]
```

---

## Step 5: Create Tenant-Aware ViewSets

```python
# core/viewsets.py
from vidyut.api import ModelViewSet, action
from vidyut.api.permissions import IsAuthenticated
from vidyut.middleware import get_current_tenant
from .models import Project, Task
from .serializers import (
    ProjectSerializer, ProjectDetailSerializer, TaskSerializer
)

class TenantViewSetMixin:
    """Mixin for tenant-scoped viewsets."""
    
    def get_queryset(self):
        """Filter by current tenant."""
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs
    
    async def perform_create(self, serializer):
        """Set tenant on create."""
        tenant = get_current_tenant()
        await serializer.save(tenant=tenant)


class ProjectViewSet(TenantViewSetMixin, ModelViewSet):
    model = Project
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProjectDetailSerializer
        return ProjectSerializer
    
    async def perform_create(self, serializer):
        tenant = get_current_tenant()
        await serializer.save(
            tenant=tenant,
            owner=self.request.user
        )


class TaskViewSet(TenantViewSetMixin, ModelViewSet):
    model = Task
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["project", "status", "assignee"]
    
    @action(detail=True, methods=["post"])
    async def assign(self, request, pk=None):
        """Assign task to user."""
        task = await self.get_object()
        user_id = request.data.get("user_id")
        
        # Verify user is in tenant
        from tenants.models import TenantUser
        membership = await TenantUser.objects.filter(
            tenant=get_current_tenant(),
            user_id=user_id
        ).first()
        
        if not membership:
            return {"error": "User not in tenant"}, 400
        
        task.assignee_id = user_id
        await task.save()
        
        return TaskSerializer(task).data
    
    @action(detail=True, methods=["post"])
    async def transition(self, request, pk=None):
        """Change task status."""
        task = await self.get_object()
        new_status = request.data.get("status")
        
        valid_transitions = {
            "todo": ["in_progress"],
            "in_progress": ["review", "todo"],
            "review": ["done", "in_progress"],
            "done": ["in_progress"],
        }
        
        if new_status not in valid_transitions.get(task.status, []):
            return {"error": f"Cannot transition from {task.status} to {new_status}"}, 400
        
        task.status = new_status
        await task.save()
        
        return TaskSerializer(task).data
```

---

## Step 6: Tenant Management API

```python
# tenants/viewsets.py
from vidyut.api import ModelViewSet, action
from vidyut.api.permissions import IsAuthenticated
from .models import Tenant, TenantUser
from .serializers import TenantSerializer, TenantUserSerializer

class TenantViewSet(ModelViewSet):
    model = Tenant
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Only show tenants user belongs to."""
        return Tenant.objects.filter(
            members__user=self.request.user
        )
    
    @action(detail=True, methods=["get"])
    async def members(self, request, pk=None):
        """List tenant members."""
        tenant = await self.get_object()
        members = await TenantUser.objects.filter(
            tenant=tenant
        ).select_related("user").all()
        return TenantUserSerializer(members, many=True).data
    
    @action(detail=True, methods=["post"])
    async def invite(self, request, pk=None):
        """Invite user to tenant."""
        tenant = await self.get_object()
        
        # Check permission
        membership = await TenantUser.objects.filter(
            tenant=tenant,
            user=request.user,
            role__in=["owner", "admin"]
        ).first()
        
        if not membership:
            return {"error": "Not authorized"}, 403
        
        email = request.data.get("email")
        role = request.data.get("role", "member")
        
        # Find or create user
        from core.models import User
        user = await User.objects.filter(email=email).first()
        if not user:
            return {"error": "User not found"}, 404
        
        # Add to tenant
        tenant_user, created = await TenantUser.objects.get_or_create(
            tenant=tenant,
            user=user,
            defaults={"role": role}
        )
        
        if not created:
            return {"error": "User already in tenant"}, 400
        
        return TenantUserSerializer(tenant_user).data
```

---

## Step 7: Plan-Based Features

```python
# tenants/permissions.py
from vidyut.api.permissions import BasePermission
from vidyut.middleware import get_current_tenant

class PlanPermission(BasePermission):
    """Check if tenant plan allows this feature."""
    
    required_plan = "free"  # Override in subclass
    
    plan_hierarchy = ["free", "starter", "pro", "enterprise"]
    
    async def has_permission(self, request, view):
        tenant = get_current_tenant()
        if not tenant:
            return False
        
        tenant_level = self.plan_hierarchy.index(tenant.plan)
        required_level = self.plan_hierarchy.index(self.required_plan)
        
        return tenant_level >= required_level


class RequiresStarterPlan(PlanPermission):
    required_plan = "starter"


class RequiresProPlan(PlanPermission):
    required_plan = "pro"


class RequiresEnterprisePlan(PlanPermission):
    required_plan = "enterprise"
```

```python
# Usage in viewsets
from tenants.permissions import RequiresProPlan

class AdvancedReportsViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, RequiresProPlan]
    # ... only available to Pro and Enterprise plans
```

---

## Step 8: Tenant Settings

```python
# tenants/settings.py
from vidyut.middleware import get_current_tenant

def get_tenant_setting(key, default=None):
    """Get a setting for the current tenant."""
    tenant = get_current_tenant()
    if not tenant:
        return default
    return tenant.settings.get(key, default)


# Default settings per plan
PLAN_DEFAULTS = {
    "free": {
        "max_projects": 3,
        "max_users": 5,
        "features": ["basic_reports"],
    },
    "starter": {
        "max_projects": 10,
        "max_users": 20,
        "features": ["basic_reports", "export"],
    },
    "pro": {
        "max_projects": 50,
        "max_users": 100,
        "features": ["basic_reports", "export", "advanced_reports", "api"],
    },
    "enterprise": {
        "max_projects": -1,  # Unlimited
        "max_users": -1,
        "features": ["all"],
    },
}


def get_plan_limit(key):
    """Get a limit for the current tenant's plan."""
    tenant = get_current_tenant()
    if not tenant:
        return PLAN_DEFAULTS["free"].get(key)
    return PLAN_DEFAULTS.get(tenant.plan, {}).get(key)
```

---

## Step 9: Test Multi-Tenancy

### Create Test

```python
# tenants/tests/test_isolation.py
import pytest
from vidyut.testing import VidyutTestCase
from tenants.models import Tenant, TenantUser
from core.models import User, Project

class TestTenantIsolation(VidyutTestCase):
    async def asyncSetUp(self):
        # Create two tenants
        self.tenant1 = await Tenant.objects.create(
            name="Tenant 1",
            slug="tenant1"
        )
        self.tenant2 = await Tenant.objects.create(
            name="Tenant 2",
            slug="tenant2"
        )
        
        # Create user
        self.user = await User.objects.create(
            email="test@example.com",
            name="Test User"
        )
        
        # Add user to both tenants
        await TenantUser.objects.create(
            tenant=self.tenant1,
            user=self.user,
            role="owner"
        )
        await TenantUser.objects.create(
            tenant=self.tenant2,
            user=self.user,
            role="member"
        )
        
        # Create projects in each tenant
        self.project1 = await Project.objects.create(
            tenant=self.tenant1,
            name="Project 1",
            owner=self.user
        )
        self.project2 = await Project.objects.create(
            tenant=self.tenant2,
            name="Project 2",
            owner=self.user
        )
    
    async def test_tenant_isolation(self):
        """Projects should be isolated by tenant."""
        # Set current tenant to tenant1
        with self.tenant_context(self.tenant1):
            projects = await Project.objects.all()
            assert len(projects) == 1
            assert projects[0].id == self.project1.id
        
        # Set current tenant to tenant2
        with self.tenant_context(self.tenant2):
            projects = await Project.objects.all()
            assert len(projects) == 1
            assert projects[0].id == self.project2.id
```

### Run Tests

```bash
vidyut test
```

---

## Step 10: Test with Subdomains

### Local Development

Add to `/etc/hosts`:

```
127.0.0.1 tenant1.localhost
127.0.0.1 tenant2.localhost
```

### Start Server

```bash
vidyut runserver --host 0.0.0.0
```

### Test Endpoints

```bash
# Tenant 1
curl http://tenant1.localhost:8000/api/projects/

# Tenant 2
curl http://tenant2.localhost:8000/api/projects/
```

---

## Next Steps

1. **Billing integration** — Stripe for subscriptions
2. **Usage tracking** — Monitor tenant resource usage
3. **Custom domains** — Allow tenants to use their own domains
4. **Data export** — Let tenants export their data
5. **Tenant admin** — Super admin dashboard

---

## Related Documentation

- [Tenant Middleware](../middleware/tenant.md)
- [Permissions](../api/permissions.md)
- [Models](../orm/models.md)
