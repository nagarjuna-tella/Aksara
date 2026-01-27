"""
Tests for RequestIDMiddleware.

Tests the request ID generation, header handling, and context propagation.
"""

from __future__ import annotations

import uuid
import pytest
from starlette.requests import Request as StarletteRequest
from starlette.testclient import TestClient

from aksara import Aksara
from aksara.middleware import RequestIDMiddleware, request_id_var


class TestRequestIDMiddleware:
    """Tests for RequestIDMiddleware."""
    
    def test_generates_request_id_when_not_provided(self):
        """Test that a request ID is generated when not in headers."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (RequestIDMiddleware, {}),
            ],
        )
        
        @app.get("/ping")
        async def ping():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/ping")
        
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        # Should be a valid UUID
        request_id = response.headers["X-Request-ID"]
        uuid.UUID(request_id)  # Raises if invalid
    
    def test_uses_provided_request_id(self):
        """Test that a provided request ID is used."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (RequestIDMiddleware, {}),
            ],
        )
        
        @app.get("/ping")
        async def ping():
            return {"status": "ok"}
        
        client = TestClient(app)
        provided_id = "my-custom-request-id-123"
        response = client.get("/ping", headers={"X-Request-ID": provided_id})
        
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == provided_id
    
    def test_request_id_in_request_state(self):
        """Test that request ID is available in request.state."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (RequestIDMiddleware, {}),
            ],
        )
        
        captured_id = None
        
        @app.get("/check-state")
        async def check_state(request: StarletteRequest):
            nonlocal captured_id
            captured_id = request.state.request_id
            return {"request_id": captured_id}
        
        client = TestClient(app)
        provided_id = "state-test-123"
        response = client.get("/check-state", headers={"X-Request-ID": provided_id})
        
        assert response.status_code == 200
        assert captured_id == provided_id
        assert response.json()["request_id"] == provided_id
    
    def test_request_id_in_contextvar(self):
        """Test that request ID is available via contextvar."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (RequestIDMiddleware, {}),
            ],
        )
        
        captured_id = None
        
        @app.get("/check-contextvar")
        async def check_contextvar():
            nonlocal captured_id
            captured_id = request_id_var.get()
            return {"request_id": captured_id}
        
        client = TestClient(app)
        provided_id = "contextvar-test-456"
        response = client.get("/check-contextvar", headers={"X-Request-ID": provided_id})
        
        assert response.status_code == 200
        assert captured_id == provided_id
    
    def test_custom_header_name(self):
        """Test using a custom header name."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (RequestIDMiddleware, {"header_name": "X-Correlation-ID"}),
            ],
        )
        
        @app.get("/ping")
        async def ping():
            return {"status": "ok"}
        
        client = TestClient(app)
        provided_id = "correlation-123"
        response = client.get("/ping", headers={"X-Correlation-ID": provided_id})
        
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == provided_id
        # Default header should not be present
        assert "X-Request-ID" not in response.headers
    
    def test_contextvar_reset_after_request(self):
        """Test that contextvar is reset after request completes."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (RequestIDMiddleware, {}),
            ],
        )
        
        @app.get("/ping")
        async def ping():
            return {"status": "ok"}
        
        # Before request
        assert request_id_var.get() is None
        
        client = TestClient(app)
        client.get("/ping")
        
        # After request - should be reset
        assert request_id_var.get() is None


class TestRequestIDMiddlewareIntegration:
    """Integration tests for RequestIDMiddleware with Aksara app."""
    
    def test_middleware_registered_via_aksara(self):
        """Test that middleware is correctly registered via Aksara constructor."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (RequestIDMiddleware, {}),
            ],
        )
        
        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
    
    def test_multiple_requests_get_different_ids(self):
        """Test that different requests get different IDs."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (RequestIDMiddleware, {}),
            ],
        )
        
        @app.get("/ping")
        async def ping():
            return {"status": "ok"}
        
        client = TestClient(app)
        
        ids = set()
        for _ in range(10):
            response = client.get("/ping")
            ids.add(response.headers["X-Request-ID"])
        
        # All should be unique
        assert len(ids) == 10
