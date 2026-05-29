"""
Aksara Contrib Admin

Django-style admin interface for Aksara applications.

Usage:
    from aksara.contrib.admin import site, ModelAdmin
    from myapp.models import Article
    
    # Simple registration
    site.register(Article)
    
    # Custom admin
    class ArticleAdmin(ModelAdmin):
        list_display = ["title", "author", "created_at"]
        search_fields = ["title", "body"]
    
    site.register(Article, ArticleAdmin)

The admin interface provides:
- Automatic model CRUD views
- Customizable list display
- Site, model, and object permission checks
- Form generation from model fields
"""

from aksara.contrib.admin.site import AdminSite
from aksara.contrib.admin.options import ModelAdmin
from aksara.contrib.admin.filters import SimpleListFilter
from aksara.contrib.admin.actions import action
from aksara.contrib.admin.urls import build_admin_router
from aksara.contrib.admin.mount import include_admin

# Global admin site instance
site = AdminSite()

# Backwards compatibility alias
admin_site = site

# Default router bound to the global site (route names: "admin:*").
admin_router = build_admin_router(site)

__all__ = [
    "site",
    "admin_site",  # Alias for backwards compatibility
    "AdminSite",
    "ModelAdmin",
    "SimpleListFilter",
    "action",
    "admin_router",
    "build_admin_router",
    "include_admin",
]
