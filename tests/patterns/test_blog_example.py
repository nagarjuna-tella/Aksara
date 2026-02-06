"""
Tests for Blog Example Pattern

Tests the blog example app structure and imports.
"""

import pytest
import importlib
import sys
from pathlib import Path


# Add examples to path
examples_path = Path(__file__).parent.parent.parent / "examples"
if str(examples_path) not in sys.path:
    sys.path.insert(0, str(examples_path))


class TestBlogExampleStructure:
    """Test blog example has correct structure."""
    
    def test_blog_package_exists(self):
        """Blog example should be importable."""
        spec = importlib.util.find_spec("blog")
        assert spec is not None, "blog package should exist"
    
    def test_blog_models_importable(self):
        """Blog models should be importable."""
        from blog import models
        assert hasattr(models, "Post")
        assert hasattr(models, "Comment")
    
    def test_blog_serializers_importable(self):
        """Blog serializers should be importable."""
        from blog import serializers
        assert hasattr(serializers, "PostSerializer")
        assert hasattr(serializers, "PostListSerializer")
        assert hasattr(serializers, "CommentSerializer")
    
    def test_blog_views_importable(self):
        """Blog views should be importable."""
        from blog import views
        assert hasattr(views, "PostViewSet")
        assert hasattr(views, "CommentViewSet")
    
    def test_blog_admin_importable(self):
        """Blog admin should be importable."""
        from blog import admin
        assert hasattr(admin, "PostAdmin")
        assert hasattr(admin, "CommentAdmin")
    
    def test_blog_urls_importable(self):
        """Blog urls should be importable."""
        from blog import urls
        assert hasattr(urls, "register_routes")
        assert hasattr(urls, "urlpatterns")


class TestBlogModels:
    """Test blog model definitions."""
    
    def test_post_model_fields(self):
        """Post model should have correct fields."""
        from blog.models import Post
        
        # Check model has Meta
        assert hasattr(Post, "Meta")
        assert Post.Meta.table_name == "posts"
        
        # Check required fields exist
        assert hasattr(Post, "title")
        assert hasattr(Post, "slug")
        assert hasattr(Post, "content")
        assert hasattr(Post, "is_published")
        assert hasattr(Post, "view_count")
        assert hasattr(Post, "tags")
    
    def test_comment_model_fields(self):
        """Comment model should have correct fields."""
        from blog.models import Comment
        
        assert hasattr(Comment, "Meta")
        assert Comment.Meta.table_name == "comments"
        
        # Check required fields
        assert hasattr(Comment, "post")
        assert hasattr(Comment, "author_name")
        assert hasattr(Comment, "body")
        assert hasattr(Comment, "is_approved")


class TestBlogViewSets:
    """Test blog ViewSet definitions."""
    
    def test_post_viewset_config(self):
        """PostViewSet should have correct configuration."""
        from blog.views import PostViewSet
        from blog.models import Post
        
        assert PostViewSet.model == Post
        assert PostViewSet.prefix == "/api/posts"
        assert "Posts" in PostViewSet.tags
    
    def test_post_viewset_actions(self):
        """PostViewSet should have custom actions."""
        from blog.views import PostViewSet
        
        # Check for custom action methods
        assert hasattr(PostViewSet, "publish")
        assert hasattr(PostViewSet, "unpublish")
        assert hasattr(PostViewSet, "view")
    
    def test_comment_viewset_config(self):
        """CommentViewSet should have correct configuration."""
        from blog.views import CommentViewSet
        from blog.models import Comment
        
        assert CommentViewSet.model == Comment
        assert CommentViewSet.prefix == "/api/comments"
    
    def test_comment_viewset_actions(self):
        """CommentViewSet should have moderation actions."""
        from blog.views import CommentViewSet
        
        assert hasattr(CommentViewSet, "approve")
        assert hasattr(CommentViewSet, "reject")


class TestBlogFiles:
    """Test blog example file structure."""
    
    def test_readme_exists(self):
        """README.md should exist."""
        readme = examples_path / "blog" / "README.md"
        assert readme.exists(), "blog/README.md should exist"
    
    def test_main_exists(self):
        """main.py should exist."""
        main = examples_path / "blog" / "main.py"
        assert main.exists(), "blog/main.py should exist"
    
    def test_settings_exists(self):
        """settings.py should exist."""
        settings = examples_path / "blog" / "settings.py"
        assert settings.exists(), "blog/settings.py should exist"
    
    def test_migrations_folder_exists(self):
        """migrations folder should exist."""
        migrations = examples_path / "blog" / "migrations"
        assert migrations.exists(), "blog/migrations/ should exist"
        assert migrations.is_dir()
