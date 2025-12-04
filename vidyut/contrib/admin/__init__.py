"""
Vidyut Contrib Admin

Django-style admin interface for Vidyut applications.

Usage:
    from vidyut.contrib.admin import site, ModelAdmin
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

from vidyut.contrib.admin.site import AdminSite
from vidyut.contrib.admin.options import ModelAdmin
from vidyut.contrib.admin.urls import router as admin_router
from vidyut.contrib.admin.mount import include_admin

# Global admin site instance
site = AdminSite()

__all__ = [
    "site",
    "AdminSite",
    "ModelAdmin",
    "admin_router",
    "include_admin",
]
