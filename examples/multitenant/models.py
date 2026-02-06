"""
Multitenant Example - Models

Demonstrates:
- Tenant model for SaaS multi-tenancy
- User model scoped to Tenant
- TenantQuerySetMixin for automatic filtering
"""

from aksara import Model, fields


class Tenant(Model):
    """
    Tenant (organization/workspace) in a multi-tenant system.
    
    Each tenant has:
    - A unique slug for URLs
    - A domain for domain-based routing
    - Plan information for billing
    """
    
    name = fields.String(
        max_length=200,
        ai_description="Organization or workspace name",
    )
    slug = fields.String(
        max_length=100,
        unique=True,
        ai_description="URL-friendly identifier (e.g., 'acme-corp')",
    )
    domain = fields.String(
        max_length=255,
        nullable=True,
        unique=True,
        ai_description="Custom domain (e.g., 'app.acme.com')",
    )
    plan = fields.String(
        max_length=50,
        default="free",
        ai_description="Subscription plan: free, starter, pro, enterprise",
    )
    is_active = fields.Boolean(
        default=True,
        ai_description="Whether the tenant is active",
    )
    metadata = fields.JSON(
        nullable=True,
        ai_description="Custom metadata for the tenant",
    )
    created_at = fields.DateTime(
        auto_now_add=True,
        ai_description="When the tenant was created",
    )
    
    class Meta:
        table_name = "tenants"
        ai_name = "Tenant"
        ai_description = "Organization/workspace in a multi-tenant system"
        ai_agent_exposed = True


class User(Model):
    """
    User within a tenant.
    
    Each user belongs to exactly one tenant and has a role
    within that tenant.
    """
    
    # Role constants
    ROLE_ADMIN = "admin"
    ROLE_MEMBER = "member"
    ROLE_VIEWER = "viewer"
    
    tenant = fields.ForeignKey(
        "Tenant",
        on_delete="CASCADE",
        ai_description="The tenant this user belongs to",
    )
    email = fields.String(
        max_length=255,
        ai_description="User's email address (unique within tenant)",
    )
    name = fields.String(
        max_length=200,
        ai_description="User's display name",
    )
    role = fields.String(
        max_length=50,
        default="member",
        ai_description="User's role: admin, member, viewer",
    )
    is_active = fields.Boolean(
        default=True,
        ai_description="Whether the user is active",
    )
    last_login = fields.DateTime(
        nullable=True,
        ai_description="Last login timestamp",
    )
    created_at = fields.DateTime(
        auto_now_add=True,
        ai_description="When the user was created",
    )
    
    class Meta:
        table_name = "tenant_users"
        ai_name = "User"
        ai_description = "User within a tenant with role-based access"
        ai_agent_exposed = True


class Project(Model):
    """
    Example tenant-scoped resource.
    
    Demonstrates how to create data that belongs to a tenant.
    """
    
    tenant = fields.ForeignKey(
        "Tenant",
        on_delete="CASCADE",
        ai_description="The tenant this project belongs to",
    )
    name = fields.String(
        max_length=200,
        ai_description="Project name",
    )
    description = fields.Text(
        nullable=True,
        ai_description="Project description",
    )
    is_public = fields.Boolean(
        default=False,
        ai_description="Whether the project is public",
    )
    created_at = fields.DateTime(
        auto_now_add=True,
        ai_description="When the project was created",
    )
    
    class Meta:
        table_name = "projects"
        ai_name = "Project"
        ai_description = "Tenant-scoped project"
        ai_agent_exposed = True
