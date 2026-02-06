"""
Multitenant Example - Views

ViewSets with tenant-scoped queries.
Demonstrates:
- Tenant management (not scoped)
- User and Project views scoped to current tenant
"""

from aksara import ModelViewSet, action, Request
from .models import Tenant, User, Project
from .serializers import TenantSerializer, UserSerializer, ProjectSerializer
from .middleware import get_current_tenant


class TenantViewSet(ModelViewSet):
    """
    ViewSet for tenants (not scoped).
    
    Used for tenant management by super-admins.
    
    Endpoints:
        GET    /api/tenants/           - List all tenants
        POST   /api/tenants/           - Create a tenant
        GET    /api/tenants/{id}/      - Get a tenant
        PUT    /api/tenants/{id}/      - Update a tenant
        DELETE /api/tenants/{id}/      - Delete a tenant
    """
    
    model = Tenant
    serializer_class = TenantSerializer
    prefix = "/api/tenants"
    tags = ["Tenants"]
    ai_exposed = True


class UserViewSet(ModelViewSet):
    """
    ViewSet for users (scoped to current tenant).
    
    Requires X-Tenant-ID or X-Tenant-Slug header.
    
    Endpoints:
        GET    /api/users/           - List users in current tenant
        POST   /api/users/           - Create a user in current tenant
        GET    /api/users/{id}/      - Get a user
        PUT    /api/users/{id}/      - Update a user
        DELETE /api/users/{id}/      - Delete a user
    """
    
    model = User
    serializer_class = UserSerializer
    prefix = "/api/users"
    tags = ["Users"]
    ai_exposed = True
    
    async def get_queryset(self, request: Request):
        """Override to scope queries to current tenant."""
        tenant = get_current_tenant()
        if tenant:
            return self.model.objects.filter(tenant_id=tenant.id)
        # Return empty queryset if no tenant
        return self.model.objects.filter(id="00000000-0000-0000-0000-000000000000")
    
    async def perform_create(self, data: dict, request: Request):
        """Override to set tenant on create."""
        tenant = get_current_tenant()
        if tenant:
            data["tenant_id"] = str(tenant.id)
        return await super().perform_create(data, request)
    
    @action(detail=False, methods=["GET"])
    async def me(self, request: Request):
        """Get current user info (placeholder)."""
        tenant = get_current_tenant()
        return {
            "tenant_id": str(tenant.id) if tenant else None,
            "tenant_name": tenant.name if tenant else None,
        }
    
    @action(detail=False, methods=["GET"])
    async def admins(self, request: Request):
        """List admin users in current tenant."""
        tenant = get_current_tenant()
        if not tenant:
            return {"error": "Tenant required"}
        
        users = await self.model.objects.filter(
            tenant_id=tenant.id,
            role="admin"
        ).all()
        return [UserSerializer.from_model(u) for u in users]


class ProjectViewSet(ModelViewSet):
    """
    ViewSet for projects (scoped to current tenant).
    
    Requires X-Tenant-ID or X-Tenant-Slug header.
    
    Endpoints:
        GET    /api/projects/           - List projects in current tenant
        POST   /api/projects/           - Create a project in current tenant
        GET    /api/projects/{id}/      - Get a project
        PUT    /api/projects/{id}/      - Update a project
        DELETE /api/projects/{id}/      - Delete a project
    """
    
    model = Project
    serializer_class = ProjectSerializer
    prefix = "/api/projects"
    tags = ["Projects"]
    ai_exposed = True
    
    async def get_queryset(self, request: Request):
        """Override to scope queries to current tenant."""
        tenant = get_current_tenant()
        if tenant:
            return self.model.objects.filter(tenant_id=tenant.id)
        return self.model.objects.filter(id="00000000-0000-0000-0000-000000000000")
    
    async def perform_create(self, data: dict, request: Request):
        """Override to set tenant on create."""
        tenant = get_current_tenant()
        if tenant:
            data["tenant_id"] = str(tenant.id)
        return await super().perform_create(data, request)
