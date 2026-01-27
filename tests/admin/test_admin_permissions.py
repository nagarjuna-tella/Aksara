"""
Tests for admin view permissions (v0.3.15).

Tests that:
- Non-staff users are redirected to login
- Staff users can access admin routes
- Login page is accessible without auth
- Permission checks work for CRUD operations
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from starlette.testclient import TestClient

from aksara import Model, fields, Aksara
from aksara.registry import ModelRegistry


class TestAdminLogin:
    """Tests for admin login functionality."""
    
    def setup_method(self):
        """Clear registries before each test."""
        ModelRegistry.clear()
        from aksara.contrib.admin import site
        site.clear()
    
    def test_login_page_accessible_without_auth(self):
        """Test that login page is accessible without authentication."""
        from aksara.contrib.admin import site
        
        class TestModel(Model):
            name = fields.String()
            
            class Meta:
                app_label = "test"
        
        site.register(TestModel)
        
        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
        )
        
        client = TestClient(app, raise_server_exceptions=False)
        
        # Login page should be accessible without auth
        response = client.get("/admin/login/")
        assert response.status_code == 200
        assert "Sign in" in response.text or "Login" in response.text
    
    def test_login_page_has_form(self):
        """Test that login page has the login form."""
        from aksara.contrib.admin import site
        
        class TestModel(Model):
            name = fields.String()
            
            class Meta:
                app_label = "test"
        
        site.register(TestModel)
        
        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
        )
        
        client = TestClient(app, raise_server_exceptions=False)
        
        response = client.get("/admin/login/")
        assert response.status_code == 200
        assert 'name="username"' in response.text
        assert 'name="password"' in response.text
        assert 'type="submit"' in response.text or 'Sign In' in response.text


class TestAdminPermissions:
    """Tests for admin permission checks."""
    
    def setup_method(self):
        """Clear registries before each test."""
        ModelRegistry.clear()
        from aksara.contrib.admin import site
        site.clear()
    
    def test_admin_index_requires_staff(self):
        """Test that admin index redirects to login without staff user."""
        from aksara.contrib.admin import site
        
        class TestModel(Model):
            name = fields.String()
            
            class Meta:
                app_label = "test"
        
        site.register(TestModel)
        
        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
        )
        
        client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
        
        # No user set - should redirect to login
        response = client.get("/admin/")
        assert response.status_code == 302
        assert "/admin/login" in response.headers.get("location", "")
    
    def test_admin_index_accessible_for_staff(self):
        """Test that admin index is accessible for staff user."""
        from aksara.contrib.admin import site
        from starlette.middleware.base import BaseHTTPMiddleware
        
        class TestModel(Model):
            name = fields.String()
            
            class Meta:
                app_label = "test"
        
        site.register(TestModel)
        
        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
        )
        
        # Add middleware to inject staff user
        class MockUserMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                # Create mock staff user
                user = MagicMock()
                user.is_staff = True
                user.email = "admin@test.com"
                request.state.user = user
                return await call_next(request)
        
        app.add_middleware(MockUserMiddleware)
        
        client = TestClient(app, raise_server_exceptions=False)
        
        # Staff user should get 200
        response = client.get("/admin/")
        assert response.status_code == 200
        assert "Aksara Admin" in response.text
    
    def test_model_list_requires_staff(self):
        """Test that model list view redirects to login without staff user."""
        from aksara.contrib.admin import site
        
        class Book(Model):
            title = fields.String()
            
            class Meta:
                app_label = "library"
        
        site.register(Book)
        
        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
        )
        
        client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
        
        # No user - should redirect to login
        response = client.get("/admin/library/book/")
        assert response.status_code == 302
        assert "/admin/login" in response.headers.get("location", "")
    
    def test_non_staff_user_denied(self):
        """Test that non-staff users are redirected to login."""
        from aksara.contrib.admin import site
        from starlette.middleware.base import BaseHTTPMiddleware
        
        class TestModel(Model):
            name = fields.String()
            
            class Meta:
                app_label = "test"
        
        site.register(TestModel)
        
        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
        )
        
        # Add middleware to inject non-staff user
        class MockUserMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                # Create mock non-staff user
                user = MagicMock()
                user.is_staff = False
                user.email = "user@test.com"
                request.state.user = user
                return await call_next(request)
        
        app.add_middleware(MockUserMiddleware)
        
        client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
        
        # Non-staff user should be redirected to login
        response = client.get("/admin/")
        assert response.status_code == 302
        assert "/admin/login" in response.headers.get("location", "")


class TestModelAdminPermissions:
    """Tests for ModelAdmin permission methods."""
    
    def test_has_view_permission_requires_staff(self):
        """Test has_view_permission requires is_staff=True."""
        from aksara.contrib.admin import ModelAdmin
        
        class TestModel(Model):
            name = fields.String()
        
        admin = ModelAdmin(TestModel, None)
        
        # Mock request with no user
        request = MagicMock()
        request.state = MagicMock()
        request.state.user = None
        
        assert admin.has_view_permission(request) is False
        
        # Mock request with non-staff user
        request.state.user = MagicMock()
        request.state.user.is_staff = False
        
        assert admin.has_view_permission(request) is False
        
        # Mock request with staff user
        request.state.user.is_staff = True
        
        assert admin.has_view_permission(request) is True
    
    def test_permission_methods_cascade(self):
        """Test that add/change/delete permissions cascade from view."""
        from aksara.contrib.admin import ModelAdmin
        
        class TestModel(Model):
            name = fields.String()
        
        admin = ModelAdmin(TestModel, None)
        
        # Mock request with staff user
        request = MagicMock()
        request.state = MagicMock()
        request.state.user = MagicMock()
        request.state.user.is_staff = True
        
        assert admin.has_view_permission(request) is True
        assert admin.has_add_permission(request) is True
        assert admin.has_change_permission(request) is True
        assert admin.has_delete_permission(request) is True
        
        # Non-staff user
        request.state.user.is_staff = False
        
        assert admin.has_view_permission(request) is False
        assert admin.has_add_permission(request) is False
        assert admin.has_change_permission(request) is False
        assert admin.has_delete_permission(request) is False
