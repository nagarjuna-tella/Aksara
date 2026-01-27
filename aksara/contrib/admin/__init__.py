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
- Permission checks (requires is_staff=True)
- Form generation from model fields
"""

from aksara.contrib.admin.site import AdminSite
from aksara.contrib.admin.options import ModelAdmin
from aksara.contrib.admin.urls import router as admin_router
from aksara.contrib.admin.mount import include_admin

# Global admin site instance
site = AdminSite()

__all__ = [
    "site",
    "AdminSite",
    "ModelAdmin",
    "admin_router",
    "include_admin",
]
