"""
Blog Example - Serializers

Pydantic-based serializers for data validation and transformation.
"""

from aksara.api import ModelSerializer
from .models import Post, Comment


class PostSerializer(ModelSerializer):
    """Serializer for Post model."""
    
    class Meta:
        model = Post
        fields = [
            "id", "title", "slug", "content", "excerpt", "tags",
            "is_published", "published_at", "view_count",
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "view_count", "created_at", "updated_at"]


class PostListSerializer(ModelSerializer):
    """Minimal serializer for post listings."""
    
    class Meta:
        model = Post
        fields = [
            "id", "title", "slug", "excerpt", "tags",
            "is_published", "published_at", "view_count"
        ]


class CommentSerializer(ModelSerializer):
    """Serializer for Comment model."""
    
    class Meta:
        model = Comment
        fields = [
            "id", "post_id", "author_name", "author_email",
            "text", "is_approved", "created_at"
        ]
        read_only_fields = ["id", "created_at"]
