"""
Tests for auto-discovery of ViewSets across multiple apps.
"""

import sys
import types
import pytest
from unittest.mock import patch, MagicMock

from aksara.core.discovery import auto_discover_viewsets
from aksara.api.viewsets import ModelViewSet


# Create mock models for testing
class BlogModel:
    __tablename__ = "blogs"
    __name__ = "Blog"
    _fields = {}


class UserModel:
    __tablename__ = "users"
    __name__ = "User"
    _fields = {}


class OrderModel:
    __tablename__ = "orders"
    __name__ = "Order"
    _fields = {}


class BlogViewSet(ModelViewSet):
    model = BlogModel
    prefix = "/blogs"


class UserViewSet(ModelViewSet):
    model = UserModel
    prefix = "/users"


class OrderViewSet(ModelViewSet):
    model = OrderModel
    prefix = "/orders"


class AdminUserViewSet(ModelViewSet):
    """Admin-specific user viewset."""
    model = UserModel
    prefix = "/admin/users"


class TestMultiAppDiscovery:
    """Tests for discovering ViewSets from multiple apps."""
    
    def test_discovers_from_multiple_apps(self):
        """Should discover ViewSets from all apps in settings.apps."""
        # Create fake modules for each app
        blog_views = types.ModuleType("blog.views")
        blog_views.BlogViewSet = BlogViewSet
        
        users_views = types.ModuleType("users.views")
        users_views.UserViewSet = UserViewSet
        
        orders_views = types.ModuleType("orders.views")
        orders_views.OrderViewSet = OrderViewSet
        
        def mock_import(path):
            modules = {
                "blog.views": blog_views,
                "users.views": users_views,
                "orders.views": orders_views,
            }
            return modules.get(path)
        
        with patch("aksara.core.discovery.import_module_safely", side_effect=mock_import):
            with patch("aksara.conf.settings") as mock_settings:
                mock_settings.apps = ["blog", "users", "orders"]
                viewsets = auto_discover_viewsets()
        
        assert len(viewsets) == 3
        assert BlogViewSet in viewsets
        assert UserViewSet in viewsets
        assert OrderViewSet in viewsets
    
    def test_discovers_multiple_viewsets_per_app(self):
        """Should discover multiple ViewSets from a single app."""
        admin_views = types.ModuleType("admin.views")
        admin_views.UserViewSet = UserViewSet
        admin_views.AdminUserViewSet = AdminUserViewSet
        admin_views.OrderViewSet = OrderViewSet
        
        with patch("aksara.core.discovery.import_module_safely", return_value=admin_views):
            with patch("aksara.conf.settings") as mock_settings:
                mock_settings.apps = ["admin"]
                viewsets = auto_discover_viewsets()
        
        assert len(viewsets) == 3
        assert UserViewSet in viewsets
        assert AdminUserViewSet in viewsets
        assert OrderViewSet in viewsets
    
    def test_handles_partial_app_failures(self):
        """Should continue discovery even if some apps fail to load."""
        blog_views = types.ModuleType("blog.views")
        blog_views.BlogViewSet = BlogViewSet
        
        def mock_import(path):
            if path == "blog.views":
                return blog_views
            elif path == "broken.views":
                # Simulate module that fails to import
                return None
            elif path == "users.views":
                return None  # Missing module
            return None
        
        with patch("aksara.core.discovery.import_module_safely", side_effect=mock_import):
            with patch("aksara.conf.settings") as mock_settings:
                mock_settings.apps = ["blog", "broken", "users"]
                viewsets = auto_discover_viewsets()
        
        # Should find BlogViewSet despite broken and users failing
        assert len(viewsets) == 1
        assert BlogViewSet in viewsets
    
    def test_preserves_order_of_apps(self):
        """ViewSets should be discovered in order of apps."""
        blog_views = types.ModuleType("blog.views")
        blog_views.BlogViewSet = BlogViewSet
        
        users_views = types.ModuleType("users.views")
        users_views.UserViewSet = UserViewSet
        
        def mock_import(path):
            if path == "blog.views":
                return blog_views
            elif path == "users.views":
                return users_views
            return None
        
        with patch("aksara.core.discovery.import_module_safely", side_effect=mock_import):
            with patch("aksara.conf.settings") as mock_settings:
                mock_settings.apps = ["blog", "users"]
                viewsets = auto_discover_viewsets()
        
        # Order should be: BlogViewSet, UserViewSet
        assert viewsets[0] == BlogViewSet
        assert viewsets[1] == UserViewSet


class TestAppNamingConventions:
    """Tests for various app naming conventions."""
    
    def test_nested_app_paths(self):
        """Should work with nested app paths like 'apps.blog'."""
        blog_views = types.ModuleType("apps.blog.views")
        blog_views.BlogViewSet = BlogViewSet
        
        def mock_import(path):
            if path == "apps.blog.views":
                return blog_views
            return None
        
        with patch("aksara.core.discovery.import_module_safely", side_effect=mock_import):
            with patch("aksara.conf.settings") as mock_settings:
                mock_settings.apps = ["apps.blog"]
                viewsets = auto_discover_viewsets()
        
        assert len(viewsets) == 1
        assert BlogViewSet in viewsets
    
    def test_underscored_app_names(self):
        """Should work with underscored app names."""
        views = types.ModuleType("my_blog_app.views")
        views.BlogViewSet = BlogViewSet
        
        def mock_import(path):
            if path == "my_blog_app.views":
                return views
            return None
        
        with patch("aksara.core.discovery.import_module_safely", side_effect=mock_import):
            with patch("aksara.conf.settings") as mock_settings:
                mock_settings.apps = ["my_blog_app"]
                viewsets = auto_discover_viewsets()
        
        assert len(viewsets) == 1


class TestSettingsIntegration:
    """Tests for integration with Aksara settings."""
    
    def test_uses_default_app_when_not_configured(self):
        """Should use 'app' as default when apps not specified."""
        app_views = types.ModuleType("app.views")
        app_views.BlogViewSet = BlogViewSet
        
        def mock_import(path):
            if path == "app.views":
                return app_views
            return None
        
        with patch("aksara.core.discovery.import_module_safely", side_effect=mock_import):
            with patch("aksara.conf.settings") as mock_settings:
                # Default apps value
                mock_settings.apps = ["app"]
                viewsets = auto_discover_viewsets()
        
        assert len(viewsets) == 1
        assert BlogViewSet in viewsets
