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
from aksara.conf import configure, reset_settings
from aksara.registry import ModelRegistry


def _get_admin_csrf_cookie(client: TestClient) -> str:
    """Fetch the admin login page and return the CSRF cookie value."""
    response = client.get("/admin/login/")
    assert response.status_code == 200
    assert 'name="csrf_token"' in response.text
    csrf_token = client.cookies.get("aksara_admin_csrf")
    assert csrf_token is not None
    return csrf_token


class TestAdminLogin:
    """Tests for admin login functionality."""
    
    def setup_method(self):
        """Clear registries before each test."""
        ModelRegistry.clear()
        reset_settings()
        from aksara.contrib.admin import site
        site.clear()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()
    
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
        assert 'name="csrf_token"' in response.text
        assert 'type="submit"' in response.text or 'Sign In' in response.text

    def test_login_cookie_secure_defaults_true_in_debug(self):
        """Admin login should still set Secure cookies when debug is enabled."""
        from aksara.contrib.admin import site

        class TestModel(Model):
            name = fields.String()

            class Meta:
                app_label = "test"

        site.register(TestModel)
        configure(cookie_secure=True)

        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
            enable_admin=True,
        )

        client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
        csrf_token = _get_admin_csrf_cookie(client)

        mock_user = MagicMock()
        mock_user.is_staff = True

        with patch("aksara.contrib.auth.authenticate", new=AsyncMock(return_value=mock_user)):
            with patch("aksara.contrib.auth.create_session_token", new=AsyncMock(return_value="token-123")):
                response = client.post(
                    "/admin/login/",
                    data={
                        "username": "admin@test.com",
                        "password": "secret",
                        "next": "/admin/",
                        "csrf_token": csrf_token,
                    },
                )

        assert response.status_code == 302
        assert "Secure" in response.headers["set-cookie"]

    def test_login_cookie_secure_can_be_disabled(self):
        """Admin login should allow explicit Secure cookie opt-out."""
        from aksara.contrib.admin import site

        class TestModel(Model):
            name = fields.String()

            class Meta:
                app_label = "test"

        site.register(TestModel)
        configure(cookie_secure=False)

        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
            enable_admin=True,
        )

        client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
        csrf_token = _get_admin_csrf_cookie(client)

        mock_user = MagicMock()
        mock_user.is_staff = True

        with patch("aksara.contrib.auth.authenticate", new=AsyncMock(return_value=mock_user)):
            with patch("aksara.contrib.auth.create_session_token", new=AsyncMock(return_value="token-123")):
                response = client.post(
                    "/admin/login/",
                    data={
                        "username": "admin@test.com",
                        "password": "secret",
                        "next": "/admin/",
                        "csrf_token": csrf_token,
                    },
                )

        assert response.status_code == 302
        assert "Secure" not in response.headers["set-cookie"]

    def test_login_rejects_missing_csrf_token(self):
        """Admin login should reject POSTs without a CSRF token."""
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
            enable_admin=True,
        )

        client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)

        response = client.post(
            "/admin/login/",
            data={"username": "admin@test.com", "password": "secret", "next": "/admin/"},
        )

        assert response.status_code == 403

    def test_login_rate_limit_returns_429(self):
        """Repeated admin POSTs should hit the admin rate limit."""
        from aksara.contrib.admin import site

        class TestModel(Model):
            name = fields.String()

            class Meta:
                app_label = "test"

        site.register(TestModel)
        configure(admin_rate_limit_requests=1, admin_rate_limit_window_seconds=60)

        app = Aksara(
            database_url=None,
            debug=True,
            auto_discover_views=False,
            enable_admin=True,
        )

        client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
        csrf_token = _get_admin_csrf_cookie(client)

        with patch("aksara.contrib.auth.authenticate", new=AsyncMock(return_value=None)):
            first_response = client.post(
                "/admin/login/",
                data={
                    "username": "admin@test.com",
                    "password": "secret",
                    "next": "/admin/",
                    "csrf_token": csrf_token,
                },
            )
            second_response = client.post(
                "/admin/login/",
                data={
                    "username": "admin@test.com",
                    "password": "secret",
                    "next": "/admin/",
                    "csrf_token": csrf_token,
                },
            )

        assert first_response.status_code == 200
        assert second_response.status_code == 429
        assert int(second_response.headers.get("retry-after", "0")) >= 1


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
