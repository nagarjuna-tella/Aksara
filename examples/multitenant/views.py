"""
Multitenant Example - Views (v0.5.8)

ViewSets with tenant-scoped queries.
Demonstrates:
- Tenant management (not scoped)
- User and Project views scoped to current tenant
- AI-aware tenant overview endpoint
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
        GET    /api/tenants/                  - List all tenants
        POST   /api/tenants/                  - Create a tenant
        GET    /api/tenants/{id}/             - Get a tenant
        PUT    /api/tenants/{id}/             - Update a tenant
        DELETE /api/tenants/{id}/             - Delete a tenant
        GET    /api/tenants/{id}/ai-overview/ - AI: tenant model overview
    """
    
    model = Tenant
    serializer_class = TenantSerializer
    prefix = "/api/tenants"
    tags = ["Multitenant API"]
    ai_exposed = True
    
    # =========================================================================
    # AI-Aware Endpoint (v0.5.8)
    # =========================================================================
    
    @action(
        detail=True,
        methods=["GET"],
        path="ai-overview",
        name="tenant_model_overview",
        description="Get an overview of models and record counts for a specific tenant. Respects tenant isolation.",
        ai_exposed=True,
    )
    async def ai_overview(self, pk: str, request: Request):
        """
        AI Tool: Tenant model overview.
        
        Returns a summary of all tenant-scoped models and their record counts.
        This respects tenant isolation - only data for the specified tenant
        is included.
        
        Useful for LLMs to understand the data landscape of a tenant.
        
        Returns:
            tenant_id: Tenant UUID
            tenant_slug: Tenant slug
            tenant_name: Tenant display name
            plan: Subscription plan
            is_active: Whether tenant is active
            models: List of model names and their record counts
        """
        tenant = await self.model.objects.get(id=pk)
        
        # Count records for tenant-scoped models
        user_count = len(await User.objects.filter(tenant_id=pk).all())
        project_count = len(await Project.objects.filter(tenant_id=pk).all())
        
        # Public vs private projects
        public_projects = len(await Project.objects.filter(tenant_id=pk, is_public=True).all())
        
        # User role breakdown
        admin_count = len(await User.objects.filter(tenant_id=pk, role="admin").all())
        member_count = len(await User.objects.filter(tenant_id=pk, role="member").all())
        viewer_count = len(await User.objects.filter(tenant_id=pk, role="viewer").all())
        
        return {
            "tenant_id": str(tenant.id),
            "tenant_slug": tenant.slug,
            "tenant_name": tenant.name,
            "plan": tenant.plan,
            "is_active": tenant.is_active,
            "models": [
                {
                    "name": "User",
                    "count": user_count,
                    "breakdown": {
                        "admin": admin_count,
                        "member": member_count,
                        "viewer": viewer_count,
                    }
                },
                {
                    "name": "Project",
                    "count": project_count,
                    "breakdown": {
                        "public": public_projects,
                        "private": project_count - public_projects,
                    }
                },
            ],
            "summary": {
                "total_records": user_count + project_count,
                "active_users": admin_count + member_count,  # Excluding viewers
            }
        }


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
    tags = ["Multitenant API"]
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
        return [UserSerializer.from_model(u).model_dump() for u in users]


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
    tags = ["Multitenant API"]
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
