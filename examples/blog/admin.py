"""
Blog Example - Admin Registration

Register models with Aksara Admin for management UI.
"""

from aksara.contrib.admin import ModelAdmin, admin_site
from .models import Post, Comment


@admin_site.register(Post)
class PostAdmin(ModelAdmin):
    """Admin configuration for Post model."""
    
    list_display = ["title", "slug", "is_published", "view_count", "created_at"]
    list_filter = ["is_published"]
    search_fields = ["title", "content"]


@admin_site.register(Comment)
class CommentAdmin(ModelAdmin):
    """Admin configuration for Comment model."""
    
    list_display = ["author_name", "text", "is_approved", "created_at"]
    list_filter = ["is_approved"]
    search_fields = ["author_name", "text"]
