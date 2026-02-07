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
        
        # Check required fields exist in _fields (dict)
        field_names = list(Post._fields.keys())
        assert "title" in field_names
        assert "slug" in field_names
        assert "content" in field_names
        assert "is_published" in field_names
        assert "view_count" in field_names
        assert "tags" in field_names
    
    def test_comment_model_fields(self):
        """Comment model should have correct fields."""
        from blog.models import Comment
        
        assert hasattr(Comment, "Meta")
        assert Comment.Meta.table_name == "comments"
        
        # Check required fields in _fields (dict)
        field_names = list(Comment._fields.keys())
        assert "post" in field_names
        assert "author_name" in field_names
        assert "body" in field_names or "text" in field_names
        assert "is_approved" in field_names


class TestBlogViewSets:
    """Test blog ViewSet definitions."""
    
    def test_post_viewset_config(self):
        """PostViewSet should have correct configuration."""
        from blog.views import PostViewSet
        from blog.models import Post
        
        assert PostViewSet.model == Post
        assert PostViewSet.prefix == "/api/posts"
        assert "Blog API" in PostViewSet.tags
    
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


class TestBlogAuth:
    """Test blog auth module (v0.5.8)."""
    
    def test_auth_module_importable(self):
        """auth module should be importable."""
        from blog import auth
        assert hasattr(auth, "verify_api_key")
        assert hasattr(auth, "require_api_key")
    
    def test_verify_api_key_function(self):
        """verify_api_key should work correctly."""
        from blog.auth import verify_api_key
        from blog import settings
        
        # Should verify against configured key
        assert verify_api_key(settings.BLOG_API_KEY) is True
        assert verify_api_key("wrong-key") is False
    
    def test_require_api_key_is_async(self):
        """require_api_key should be async."""
        from blog.auth import require_api_key
        import inspect
        
        assert inspect.iscoroutinefunction(require_api_key)
    
    def test_settings_has_api_key(self):
        """settings should have BLOG_API_KEY."""
        from blog import settings
        
        assert hasattr(settings, "BLOG_API_KEY")
        assert settings.BLOG_API_KEY  # Should be non-empty
    
    def test_viewset_has_dependencies(self):
        """ViewSets should have auth dependencies."""
        from blog.views import PostViewSet, CommentViewSet
        
        assert hasattr(PostViewSet, "dependencies")
        assert PostViewSet.dependencies is not None
        assert len(PostViewSet.dependencies) > 0
        
        assert hasattr(CommentViewSet, "dependencies")
        assert CommentViewSet.dependencies is not None


class TestBlogPagination:
    """Test blog pagination settings (v0.5.8)."""
    
    def test_settings_has_page_size(self):
        """settings should have DEFAULT_PAGE_SIZE."""
        from blog import settings
        
        assert hasattr(settings, "DEFAULT_PAGE_SIZE")
        assert settings.DEFAULT_PAGE_SIZE == 10
    
    def test_settings_has_max_page_size(self):
        """settings should have MAX_PAGE_SIZE."""
        from blog import settings
        
        assert hasattr(settings, "MAX_PAGE_SIZE")
        assert settings.MAX_PAGE_SIZE == 100
    
    def test_viewset_has_list_override(self):
        """PostViewSet should have custom list method."""
        from blog.views import PostViewSet
        
        assert hasattr(PostViewSet, "list")
        # Check it's overridden (not just inherited)
        import inspect
        assert inspect.iscoroutinefunction(PostViewSet.list)


class TestBlogAI:
    """Test blog AI endpoint (v0.5.8)."""
    
    def test_ai_suggest_tags_action(self):
        """PostViewSet should have ai_suggest_tags action."""
        from blog.views import PostViewSet
        
        assert hasattr(PostViewSet, "ai_suggest_tags")
    
    def test_ai_suggest_tags_has_ai_attributes(self):
        """ai_suggest_tags should have AI exposure attributes."""
        from blog.views import PostViewSet
        
        method = getattr(PostViewSet, "ai_suggest_tags")
        # Check for action metadata (stored in _aksara_action)
        assert hasattr(method, "_aksara_action")
        meta = method._aksara_action
        assert meta.get("ai_exposed") is True
    
    def test_stopwords_defined(self):
        """STOPWORDS should be defined for keyword extraction."""
        from blog.views import STOPWORDS
        
        assert isinstance(STOPWORDS, set)
        assert "the" in STOPWORDS
        assert "and" in STOPWORDS


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
    
    def test_auth_exists(self):
        """auth.py should exist (v0.5.8)."""
        auth = examples_path / "blog" / "auth.py"
        assert auth.exists(), "blog/auth.py should exist"
    
    def test_migrations_folder_exists(self):
        """migrations folder should exist."""
        migrations = examples_path / "blog" / "migrations"
        assert migrations.exists(), "blog/migrations/ should exist"
        assert migrations.is_dir()
