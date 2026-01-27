"""
Tests for ViewSet auto-registration helpers (v0.3.14).

Tests that:
- discover_viewsets finds all ModelViewSet subclasses in a module
- include_app_viewsets registers ViewSets from an app's api module
- include_all_app_viewsets registers ViewSets from all configured apps
"""

import sys
import pytest
from types import ModuleType
from unittest.mock import patch, MagicMock

from fastapi import APIRouter
from starlette.testclient import TestClient

from aksara import Aksara, Model, fields
from aksara.api import (
    ModelViewSet,
    discover_viewsets,
    include_app_viewsets,
    include_all_app_viewsets,
    include_viewset,
)
from aksara.registry import ModelRegistry


class TestDiscoverViewsets:
    """Tests for discover_viewsets function."""
    
    def test_discover_viewsets_finds_viewsets(self):
        """Test that discover_viewsets finds all ModelViewSet subclasses."""
        # Clear registry
        ModelRegistry.clear()
        
        # Create a test model
        class TestModel(Model):
            name = fields.String()
        
        # Create a test ViewSet
        class TestViewSet(ModelViewSet):
            model = TestModel
            prefix = "/test"
            tags = ["Test"]
        
        # Create a fake module with the ViewSet
        fake_module = ModuleType("fake_module")
        fake_module.TestViewSet = TestViewSet
        fake_module.TestModel = TestModel  # Not a ViewSet
        fake_module.some_function = lambda: None  # Not a ViewSet
        fake_module._private = TestViewSet  # Should be skipped (private)
        
        viewsets = discover_viewsets(fake_module)
        
        assert len(viewsets) == 1
        assert viewsets[0] is TestViewSet
    
    def test_discover_viewsets_excludes_base_class(self):
        """Test that discover_viewsets excludes ModelViewSet base class."""
        fake_module = ModuleType("fake_module")
        fake_module.ModelViewSet = ModelViewSet
        
        viewsets = discover_viewsets(fake_module)
        
        assert ModelViewSet not in viewsets
    
    def test_discover_viewsets_empty_module(self):
        """Test that discover_viewsets handles empty modules."""
        fake_module = ModuleType("empty_module")
        
        viewsets = discover_viewsets(fake_module)
        
        assert viewsets == []


class TestIncludeAppViewsets:
    """Tests for include_app_viewsets function."""
    
    def setup_method(self):
        """Clear registry before each test."""
        ModelRegistry.clear()
    
    def test_include_app_viewsets_registers_viewsets(self):
        """Test that include_app_viewsets registers ViewSets with the app."""
        # Create test model and viewset
        class Article(Model):
            title = fields.String()
        
        class ArticleViewSet(ModelViewSet):
            model = Article
            prefix = "/articles"
            tags = ["Articles"]
        
        # Create a fake module
        fake_api_module = ModuleType("test_blog.api")
        fake_api_module.ArticleViewSet = ArticleViewSet
        
        # Patch import_module to return our fake module
        with patch.dict(sys.modules, {"test_blog.api": fake_api_module}):
            router = APIRouter()
            registered = include_app_viewsets(router, "test_blog")
        
        assert len(registered) == 1
        assert ArticleViewSet in registered
    
    def test_include_app_viewsets_custom_module_name(self):
        """Test that include_app_viewsets uses custom module name."""
        class Item(Model):
            name = fields.String()
        
        class ItemViewSet(ModelViewSet):
            model = Item
            prefix = "/items"
            tags = ["Items"]
        
        fake_views_module = ModuleType("myapp.views")
        fake_views_module.ItemViewSet = ItemViewSet
        
        with patch.dict(sys.modules, {"myapp.views": fake_views_module}):
            router = APIRouter()
            registered = include_app_viewsets(router, "myapp", module_name="views")
        
        assert len(registered) == 1
        assert ItemViewSet in registered
    
    def test_include_app_viewsets_missing_module(self):
        """Test that include_app_viewsets handles missing modules gracefully."""
        router = APIRouter()
        
        # App doesn't have an api module - should return empty list
        registered = include_app_viewsets(router, "nonexistent_app")
        
        assert registered == []


class TestIncludeAllAppViewsets:
    """Tests for include_all_app_viewsets function."""
    
    def setup_method(self):
        """Clear registry before each test."""
        ModelRegistry.clear()
    
    def test_include_all_app_viewsets(self):
        """Test that include_all_app_viewsets registers ViewSets from all apps."""
        # Create models and viewsets for two apps
        class User(Model):
            name = fields.String()
        
        class UserViewSet(ModelViewSet):
            model = User
            prefix = "/users"
            tags = ["Users"]
        
        class Post(Model):
            title = fields.String()
        
        class PostViewSet(ModelViewSet):
            model = Post
            prefix = "/posts"
            tags = ["Posts"]
        
        # Create fake modules
        fake_users_api = ModuleType("users.api")
        fake_users_api.UserViewSet = UserViewSet
        
        fake_blog_api = ModuleType("blog.api")
        fake_blog_api.PostViewSet = PostViewSet
        
        # Patch settings.apps and sys.modules
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.apps = ["users", "blog"]
            
            with patch.dict(sys.modules, {
                "users.api": fake_users_api,
                "blog.api": fake_blog_api,
            }):
                router = APIRouter()
                result = include_all_app_viewsets(router)
        
        assert "users" in result
        assert "blog" in result
        assert UserViewSet in result["users"]
        assert PostViewSet in result["blog"]


class TestViewsetAutoRegistrationIntegration:
    """Integration tests for ViewSet auto-registration with Aksara app."""
    
    def setup_method(self):
        """Clear registry before each test."""
        ModelRegistry.clear()
    
    def test_auto_registered_viewsets_have_routes(self):
        """Test that auto-registered ViewSets create proper routes."""
        # Create model and viewset
        class Widget(Model):
            name = fields.String()
        
        class WidgetViewSet(ModelViewSet):
            model = Widget
            prefix = "/widgets"
            tags = ["Widgets"]
        
        # Create fake module
        fake_module = ModuleType("widgets.api")
        fake_module.WidgetViewSet = WidgetViewSet
        
        # Create Aksara app without auto-discover
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
        )
        
        # Manually register via include_app_viewsets
        with patch.dict(sys.modules, {"widgets.api": fake_module}):
            include_app_viewsets(app, "widgets")
        
        # Check that routes were created
        route_paths = [route.path for route in app.routes]
        
        assert "/widgets/" in route_paths
        assert "/widgets/{pk}" in route_paths
