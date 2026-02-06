"""
Multitenant Example - Admin Registration
"""

from aksara.contrib.admin import ModelAdmin, admin_site
from .models import Tenant, User, Project


@admin_site.register(Tenant)
class TenantAdmin(ModelAdmin):
    """Admin configuration for Tenant model."""
    
    list_display = ["name", "slug", "domain", "plan", "is_active", "created_at"]
    list_filter = ["plan", "is_active"]
    search_fields = ["name", "slug", "domain"]


@admin_site.register(User)
class UserAdmin(ModelAdmin):
    """Admin configuration for User model."""
    
    list_display = ["email", "name", "role", "is_active", "created_at"]
    list_filter = ["role", "is_active"]
    search_fields = ["email", "name"]


@admin_site.register(Project)
class ProjectAdmin(ModelAdmin):
    """Admin configuration for Project model."""
    
    list_display = ["name", "is_public", "created_at"]
    list_filter = ["is_public"]
    search_fields = ["name"]
