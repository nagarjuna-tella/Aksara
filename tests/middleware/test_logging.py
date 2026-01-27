"""
Tests for LoggingMiddleware.

Tests the request logging, timing, and context correlation.
"""

from __future__ import annotations

import logging
import pytest
from starlette.testclient import TestClient

from aksara import Aksara
from aksara.middleware import (
    LoggingMiddleware,
    RequestIDMiddleware,
    TenantMiddleware,
    request_id_var,
    tenant_id_var,
    user_id_var,
)
import aksara.conf as conf


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware."""
    
    def setup_method(self):
        """Reset settings before each test."""
        conf.reset_settings()
        # Ensure logging is enabled for tests
        conf.settings.log_requests = True
        conf.settings.log_json = False
    
    def teardown_method(self):
        """Reset settings after each test."""
        conf.reset_settings()
    
    def test_logs_request(self, caplog):
        """Test that requests are logged."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (LoggingMiddleware, {}),
            ],
        )
        
        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        with caplog.at_level(logging.INFO, logger="aksara.request"):
            client = TestClient(app)
            response = client.get("/test")
        
        assert response.status_code == 200
        
        # Check log was emitted
        assert len(caplog.records) >= 1
        log_record = caplog.records[-1]
        assert log_record.name == "aksara.request"
        assert "GET" in log_record.message
        assert "/test" in log_record.message
        assert "200" in log_record.message
    
    def test_logs_timing(self, caplog):
        """Test that request timing is logged."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (LoggingMiddleware, {}),
            ],
        )
        
        @app.get("/slow")
        async def slow_endpoint():
            import asyncio
            await asyncio.sleep(0.01)  # 10ms
            return {"status": "ok"}
        
        with caplog.at_level(logging.INFO, logger="aksara.request"):
            client = TestClient(app)
            response = client.get("/slow")
        
        assert response.status_code == 200
        
        # Check timing is logged
        log_record = caplog.records[-1]
        assert "ms" in log_record.message.lower()
    
    def test_logs_request_id(self, caplog):
        """Test that request ID is included in logs."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (RequestIDMiddleware, {}),
                (LoggingMiddleware, {}),
            ],
        )
        
        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        with caplog.at_level(logging.INFO, logger="aksara.request"):
            client = TestClient(app)
            response = client.get("/test", headers={"X-Request-ID": "test-req-123"})
        
        assert response.status_code == 200
        
        log_record = caplog.records[-1]
        assert "test-req-123" in log_record.message
    
    def test_logs_tenant_id(self, caplog):
        """Test that tenant ID is included in logs."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TenantMiddleware, {}),
                (LoggingMiddleware, {}),
            ],
        )
        
        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        with caplog.at_level(logging.INFO, logger="aksara.request"):
            client = TestClient(app)
            response = client.get("/test", headers={"X-Tenant-Id": "acme"})
        
        assert response.status_code == 200
        
        log_record = caplog.records[-1]
        assert "acme" in log_record.message
    
    def test_log_requests_disabled(self, caplog):
        """Test that logging can be disabled via settings."""
        conf.settings.log_requests = False
        
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (LoggingMiddleware, {}),
            ],
        )
        
        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        with caplog.at_level(logging.INFO, logger="aksara.request"):
            client = TestClient(app)
            response = client.get("/test")
        
        assert response.status_code == 200
        
        # No logs should be emitted
        aksara_logs = [r for r in caplog.records if r.name == "aksara.request"]
        assert len(aksara_logs) == 0
    
    def test_logs_error_status(self, caplog):
        """Test that error status codes are logged appropriately."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (LoggingMiddleware, {}),
            ],
        )
        
        @app.get("/error")
        async def error_endpoint():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        
        with caplog.at_level(logging.WARNING, logger="aksara.request"):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/error")
        
        assert response.status_code == 404
        
        # Check log was emitted at WARNING level
        log_record = caplog.records[-1]
        assert log_record.levelno >= logging.WARNING
        assert "404" in log_record.message


class TestLoggingMiddlewareJsonFormat:
    """Tests for LoggingMiddleware JSON output."""
    
    def setup_method(self):
        """Reset settings before each test."""
        conf.reset_settings()
        conf.settings.log_requests = True
        conf.settings.log_json = True
    
    def teardown_method(self):
        """Reset settings after each test."""
        conf.reset_settings()
    
    def test_json_format_logs_dict(self, caplog):
        """Test that JSON format logs a dict."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (LoggingMiddleware, {}),
            ],
        )
        
        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        with caplog.at_level(logging.INFO, logger="aksara.request"):
            client = TestClient(app)
            response = client.get("/test")
        
        assert response.status_code == 200
        
        # Check log was emitted with dict message
        log_record = caplog.records[-1]
        # When log_json=True, the message is a dict
        msg = log_record.msg
        assert isinstance(msg, dict)
        assert msg["event"] == "http_request"
        assert msg["method"] == "GET"
        assert msg["path"] == "/test"
        assert msg["status_code"] == 200
        assert "duration_ms" in msg


class TestLoggingMiddlewareUserContext:
    """Tests for LoggingMiddleware user ID correlation."""
    
    def setup_method(self):
        """Reset settings before each test."""
        conf.reset_settings()
        conf.settings.log_requests = True
        conf.settings.log_json = False
    
    def teardown_method(self):
        """Reset settings after each test."""
        conf.reset_settings()
        # Reset user_id_var
        user_id_var.set(None)
    
    def test_logs_user_id_when_set(self, caplog):
        """Test that user ID is included when set."""
        from starlette.middleware.base import BaseHTTPMiddleware
        
        # Create a middleware that sets user_id (simulating auth)
        class SetUserMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                user_id_var.set("42")
                try:
                    return await call_next(request)
                finally:
                    user_id_var.set(None)
        
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (SetUserMiddleware, {}),
                (LoggingMiddleware, {}),
            ],
        )
        
        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        with caplog.at_level(logging.INFO, logger="aksara.request"):
            client = TestClient(app)
            response = client.get("/test")
        
        assert response.status_code == 200
        
        log_record = caplog.records[-1]
        assert "42" in log_record.message or "user=42" in log_record.message


class TestContextVariables:
    """Tests for context variable exports."""
    
    def test_context_vars_importable(self):
        """Test that context vars can be imported from middleware package."""
        from aksara.middleware import request_id_var, tenant_id_var, user_id_var
        
        assert request_id_var is not None
        assert tenant_id_var is not None
        assert user_id_var is not None
    
    def test_context_vars_default_none(self):
        """Test that context vars default to None."""
        from aksara.middleware import request_id_var, tenant_id_var, user_id_var
        
        # Outside of a request context
        assert request_id_var.get() is None
        assert tenant_id_var.get() is None
        assert user_id_var.get() is None
    
    def test_context_vars_can_be_set(self):
        """Test that context vars can be set and reset."""
        from aksara.middleware import request_id_var
        
        token = request_id_var.set("test-123")
        assert request_id_var.get() == "test-123"
        
        request_id_var.reset(token)
        assert request_id_var.get() is None
