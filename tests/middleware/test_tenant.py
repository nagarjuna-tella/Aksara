"""
Tests for TenantMiddleware.

Tests the tenant ID extraction from headers and subdomains.
"""

from __future__ import annotations

import pytest
from starlette.requests import Request as StarletteRequest
from starlette.testclient import TestClient

from vidyut import Vidyut
from vidyut.middleware import TenantMiddleware, tenant_id_var


class TestTenantMiddleware:
    """Tests for TenantMiddleware."""
    
    def test_extracts_tenant_from_header(self):
        """Test that tenant ID is extracted from header."""
        app = Vidyut(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TenantMiddleware, {}),
            ],
        )
        
        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"tenant_id": request.state.tenant_id}
        
        client = TestClient(app)
        response = client.get("/whoami", headers={"X-Tenant-Id": "acme"})
        
        assert response.status_code == 200
        assert response.json()["tenant_id"] == "acme"
    
    def test_custom_header_name(self):
        """Test using a custom header name."""
        app = Vidyut(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TenantMiddleware, {"header_name": "X-Tenant"}),
            ],
        )
        
        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"tenant_id": request.state.tenant_id}
        
        client = TestClient(app)
        response = client.get("/whoami", headers={"X-Tenant": "globex"})
        
        assert response.status_code == 200
        assert response.json()["tenant_id"] == "globex"
    
    def test_tenant_id_in_contextvar(self):
        """Test that tenant ID is available via contextvar."""
        app = Vidyut(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TenantMiddleware, {}),
            ],
        )
        
        captured_tenant = None
        
        @app.get("/check-contextvar")
        async def check_contextvar():
            nonlocal captured_tenant
            captured_tenant = tenant_id_var.get()
            return {"tenant_id": captured_tenant}
        
        client = TestClient(app)
        response = client.get("/check-contextvar", headers={"X-Tenant-Id": "initech"})
        
        assert response.status_code == 200
        assert captured_tenant == "initech"
    
    def test_no_tenant_header(self):
        """Test that tenant_id is None when header not provided."""
        app = Vidyut(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TenantMiddleware, {}),
            ],
        )
        
        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"tenant_id": request.state.tenant_id}
        
        client = TestClient(app)
        response = client.get("/whoami")
        
        assert response.status_code == 200
        assert response.json()["tenant_id"] is None
    
    def test_contextvar_reset_after_request(self):
        """Test that contextvar is reset after request completes."""
        app = Vidyut(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TenantMiddleware, {}),
            ],
        )
        
        @app.get("/ping")
        async def ping():
            return {"status": "ok"}
        
        # Before request
        assert tenant_id_var.get() is None
        
        client = TestClient(app)
        client.get("/ping", headers={"X-Tenant-Id": "test"})
        
        # After request - should be reset
        assert tenant_id_var.get() is None


class TestTenantMiddlewareSubdomain:
    """Tests for TenantMiddleware subdomain extraction."""
    
    def test_extracts_tenant_from_subdomain(self):
        """Test that tenant is extracted from subdomain."""
        app = Vidyut(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TenantMiddleware, {"use_subdomain": True}),
            ],
        )
        
        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"tenant_id": request.state.tenant_id}
        
        client = TestClient(app)
        response = client.get("/whoami", headers={"host": "acme.example.com"})
        
        assert response.status_code == 200
        assert response.json()["tenant_id"] == "acme"
    
    def test_header_takes_precedence_over_subdomain(self):
        """Test that header takes precedence over subdomain."""
        app = Vidyut(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TenantMiddleware, {"use_subdomain": True}),
            ],
        )
        
        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"tenant_id": request.state.tenant_id}
        
        client = TestClient(app)
        response = client.get(
            "/whoami",
            headers={
                "host": "acme.example.com",
                "X-Tenant-Id": "globex",
            }
        )
        
        assert response.status_code == 200
        assert response.json()["tenant_id"] == "globex"
    
    def test_ignores_www_subdomain(self):
        """Test that www subdomain is ignored."""
        app = Vidyut(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TenantMiddleware, {"use_subdomain": True}),
            ],
        )
        
        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"tenant_id": request.state.tenant_id}
        
        client = TestClient(app)
        response = client.get("/whoami", headers={"host": "www.example.com"})
        
        assert response.status_code == 200
        assert response.json()["tenant_id"] is None
    
    def test_ignores_api_subdomain(self):
        """Test that api subdomain is ignored."""
        app = Vidyut(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TenantMiddleware, {"use_subdomain": True}),
            ],
        )
        
        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"tenant_id": request.state.tenant_id}
        
        client = TestClient(app)
        response = client.get("/whoami", headers={"host": "api.example.com"})
        
        assert response.status_code == 200
        assert response.json()["tenant_id"] is None
    
    def test_handles_host_with_port(self):
        """Test that host with port is handled correctly."""
        app = Vidyut(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TenantMiddleware, {"use_subdomain": True}),
            ],
        )
        
        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"tenant_id": request.state.tenant_id}
        
        client = TestClient(app)
        response = client.get("/whoami", headers={"host": "acme.example.com:8000"})
        
        assert response.status_code == 200
        assert response.json()["tenant_id"] == "acme"
    
    def test_no_subdomain_for_two_part_host(self):
        """Test that two-part hosts don't yield tenant."""
        app = Vidyut(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TenantMiddleware, {"use_subdomain": True}),
            ],
        )
        
        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"tenant_id": request.state.tenant_id}
        
        client = TestClient(app)
        response = client.get("/whoami", headers={"host": "example.com"})
        
        assert response.status_code == 200
        assert response.json()["tenant_id"] is None
