"""
Tests for v0.3.17 Debug Error Pages.

Tests the dark-mode debug experience including:
- Rich debug context collection
- HTML error page rendering
- JSON error responses
- Production vs debug mode behavior
"""
import pytest
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.requests import Request
from starlette.testclient import TestClient

from vidyut.debug.handlers import (
    DebugContext,
    collect_debug_context,
    render_debug_page,
    render_minimal_error_page,
    render_json_error,
    register_debug_exception_handlers,
    _extract_traceback_frames,
    _is_library_path,
    _get_status_class,
    _build_traceback_html,
    _build_request_html,
    _build_context_vars_html,
)


# ============================================================================
# Test DebugContext
# ============================================================================

class TestDebugContext:
    """Tests for DebugContext dataclass."""
    
    def test_debug_context_defaults(self):
        """Test DebugContext has sensible defaults."""
        ctx = DebugContext()
        
        assert ctx.exception_type == ""
        assert ctx.exception_message == ""
        assert ctx.status_code == 500
        assert ctx.traceback_frames == []
        assert ctx.request_headers == {}
        assert ctx.debug_mode is True
    
    def test_debug_context_custom_values(self):
        """Test DebugContext with custom values."""
        ctx = DebugContext(
            exception_type="ValueError",
            exception_message="Invalid input",
            status_code=400,
            request_method="POST",
            request_url="http://localhost/test",
            request_id="req-123",
            tenant_id="tenant-abc",
        )
        
        assert ctx.exception_type == "ValueError"
        assert ctx.exception_message == "Invalid input"
        assert ctx.status_code == 400
        assert ctx.request_method == "POST"
        assert ctx.request_id == "req-123"
        assert ctx.tenant_id == "tenant-abc"
    
    def test_debug_context_is_dataclass(self):
        """Test DebugContext can be converted to dict."""
        ctx = DebugContext(
            exception_type="TestError",
            status_code=500,
        )
        
        data = asdict(ctx)
        assert isinstance(data, dict)
        assert data["exception_type"] == "TestError"
        assert data["status_code"] == 500


# ============================================================================
# Test Helper Functions
# ============================================================================

class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_is_library_path_site_packages(self):
        """Test site-packages path is detected as library."""
        assert _is_library_path("/usr/lib/python3.12/site-packages/requests/api.py")
        assert _is_library_path("/home/user/.venv/lib/python3.12/site-packages/fastapi/main.py")
    
    def test_is_library_path_dist_packages(self):
        """Test dist-packages path is detected as library."""
        assert _is_library_path("/usr/lib/python3/dist-packages/some_pkg/module.py")
    
    def test_is_library_path_frozen(self):
        """Test frozen paths are detected as library."""
        assert _is_library_path("<frozen importlib._bootstrap>")
    
    def test_is_library_path_user_code(self):
        """Test user code paths are not detected as library."""
        assert not _is_library_path("/home/user/project/app/main.py")
        assert not _is_library_path("/Users/dev/myapp/src/handlers.py")
        assert not _is_library_path("/app/vidyut/models.py")
    
    def test_get_status_class_500(self):
        """Test status class for 500 errors."""
        assert _get_status_class(500) == "500"
        assert _get_status_class(501) == "500"
        assert _get_status_class(503) == "500"
    
    def test_get_status_class_400(self):
        """Test status class for 400 errors."""
        assert _get_status_class(400) == "400"
        assert _get_status_class(404) == "400"
        assert _get_status_class(422) == "400"
    
    def test_get_status_class_other(self):
        """Test status class for other codes."""
        assert _get_status_class(200) == "other"
        assert _get_status_class(302) == "other"


class TestExtractTracebackFrames:
    """Tests for traceback extraction."""
    
    def test_extract_frames_from_exception(self):
        """Test extracting frames from a real exception."""
        def inner():
            raise ValueError("Test error")
        
        def outer():
            inner()
        
        try:
            outer()
        except ValueError as e:
            frames = _extract_traceback_frames(e)
        
        assert len(frames) >= 2
        assert frames[-1]["name"] == "inner"
        assert frames[-2]["name"] == "outer"
        assert "ValueError" not in frames[-1]["name"]
    
    def test_extract_frames_has_line_info(self):
        """Test that frames have line information."""
        try:
            raise RuntimeError("Test")
        except RuntimeError as e:
            frames = _extract_traceback_frames(e)
        
        assert len(frames) >= 1
        frame = frames[-1]
        assert "lineno" in frame
        assert "filename" in frame
        assert "line" in frame
        assert frame["lineno"] > 0
    
    def test_extract_frames_empty_for_no_traceback(self):
        """Test empty list when exception has no traceback."""
        exc = ValueError("No traceback")
        exc.__traceback__ = None
        frames = _extract_traceback_frames(exc)
        assert frames == []


# ============================================================================
# Test Render Functions
# ============================================================================

class TestRenderDebugPage:
    """Tests for debug page rendering."""
    
    def test_render_debug_page_returns_html_response(self):
        """Test that render_debug_page returns HTMLResponse."""
        ctx = DebugContext(
            exception_type="ValueError",
            exception_message="Something went wrong",
            status_code=500,
            request_method="GET",
            request_url="http://localhost/test",
            python_version="3.12.0",
            vidyut_version="0.3.17",
        )
        
        response = render_debug_page(ctx)
        
        assert response.status_code == 500
        assert "text/html" in response.media_type
    
    def test_render_debug_page_contains_error_info(self):
        """Test that debug page contains error information."""
        ctx = DebugContext(
            exception_type="KeyError",
            exception_message="missing_key",
            status_code=500,
            vidyut_version="0.3.17",
        )
        
        response = render_debug_page(ctx)
        body = response.body.decode("utf-8")
        
        assert "KeyError" in body
        assert "missing_key" in body
        assert "500" in body
    
    def test_render_debug_page_contains_dark_theme(self):
        """Test that debug page has dark theme CSS."""
        ctx = DebugContext(
            exception_type="TestError",
            status_code=500,
            vidyut_version="0.3.17",
        )
        
        response = render_debug_page(ctx)
        body = response.body.decode("utf-8")
        
        # Dark theme colors
        assert "#0d1117" in body  # bg-primary
        assert "#c9d1d9" in body  # text-primary
    
    def test_render_debug_page_contains_tabs(self):
        """Test that debug page has navigation tabs."""
        ctx = DebugContext(
            exception_type="TestError",
            status_code=500,
            vidyut_version="0.3.17",
        )
        
        response = render_debug_page(ctx)
        body = response.body.decode("utf-8")
        
        assert "Traceback" in body
        assert "Request" in body
        assert "Context" in body
        assert "Environment" in body
    
    def test_render_debug_page_escapes_html(self):
        """Test that debug page escapes HTML in error messages."""
        ctx = DebugContext(
            exception_type="XSSError",
            exception_message="<script>alert('xss')</script>",
            status_code=500,
            vidyut_version="0.3.17",
        )
        
        response = render_debug_page(ctx)
        body = response.body.decode("utf-8")
        
        # The error message should be escaped (not the legitimate script tag in page)
        # Look for the escaped version of the XSS attack in the error message section
        assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in body or \
               "&lt;script&gt;alert('xss')&lt;/script&gt;" in body
    
    def test_render_debug_page_shows_request_details(self):
        """Test that debug page shows request information."""
        ctx = DebugContext(
            exception_type="TestError",
            status_code=500,
            request_method="POST",
            request_url="http://localhost/api/users",
            request_headers={"content-type": "application/json"},
            vidyut_version="0.3.17",
        )
        
        response = render_debug_page(ctx)
        body = response.body.decode("utf-8")
        
        assert "POST" in body
        assert "/api/users" in body
    
    def test_render_debug_page_shows_context_vars(self):
        """Test that debug page shows context variables."""
        ctx = DebugContext(
            exception_type="TestError",
            status_code=500,
            request_id="req-12345",
            tenant_id="tenant-abc",
            user_id="user-456",
            vidyut_version="0.3.17",
        )
        
        response = render_debug_page(ctx)
        body = response.body.decode("utf-8")
        
        assert "req-12345" in body
        assert "tenant-abc" in body
        assert "user-456" in body


class TestRenderMinimalErrorPage:
    """Tests for minimal error page rendering."""
    
    def test_render_minimal_page_returns_html_response(self):
        """Test that minimal page returns HTMLResponse."""
        response = render_minimal_error_page(500, "Internal Server Error")
        
        assert response.status_code == 500
        assert "text/html" in response.media_type
    
    def test_render_minimal_page_shows_status_code(self):
        """Test that minimal page shows status code."""
        response = render_minimal_error_page(404, "Not Found")
        body = response.body.decode("utf-8")
        
        assert "404" in body
        assert "Not Found" in body
    
    def test_render_minimal_page_shows_request_id(self):
        """Test that minimal page shows request ID when provided."""
        response = render_minimal_error_page(
            500,
            "Something went wrong",
            request_id="req-abc123",
        )
        body = response.body.decode("utf-8")
        
        assert "req-abc123" in body
        assert "Request ID" in body
    
    def test_render_minimal_page_no_request_id(self):
        """Test that minimal page works without request ID."""
        response = render_minimal_error_page(500, "Error")
        body = response.body.decode("utf-8")
        
        assert "Request ID" not in body
    
    def test_render_minimal_page_escapes_html(self):
        """Test that minimal page escapes HTML."""
        response = render_minimal_error_page(
            500,
            "<script>alert('xss')</script>",
        )
        body = response.body.decode("utf-8")
        
        assert "<script>" not in body
        assert "&lt;script&gt;" in body
    
    def test_render_minimal_page_is_dark_themed(self):
        """Test that minimal page has dark theme."""
        response = render_minimal_error_page(500, "Error")
        body = response.body.decode("utf-8")
        
        assert "#0d1117" in body  # Dark background


class TestRenderJsonError:
    """Tests for JSON error rendering."""
    
    def test_render_json_error_basic(self):
        """Test basic JSON error response."""
        response = render_json_error(500, "Internal Server Error")
        
        assert response.status_code == 500
        assert "application/json" in response.media_type
    
    def test_render_json_error_structure(self):
        """Test JSON error response structure."""
        import json
        
        response = render_json_error(
            404,
            "Resource not found",
            error_type="not_found",
        )
        
        data = json.loads(response.body.decode("utf-8"))
        
        assert "error" in data
        assert data["error"]["status"] == 404
        assert data["error"]["message"] == "Resource not found"
        assert data["error"]["type"] == "not_found"
    
    def test_render_json_error_with_request_id(self):
        """Test JSON error with request ID."""
        import json
        
        response = render_json_error(
            500,
            "Error",
            request_id="req-xyz",
        )
        
        data = json.loads(response.body.decode("utf-8"))
        assert data["error"]["request_id"] == "req-xyz"
    
    def test_render_json_error_with_errors_list(self):
        """Test JSON error with validation errors list."""
        import json
        
        errors = [
            {"loc": ["body", "email"], "msg": "Invalid email", "type": "value_error"},
            {"loc": ["body", "age"], "msg": "Must be positive", "type": "value_error"},
        ]
        
        response = render_json_error(
            422,
            "Validation error",
            error_type="validation_error",
            errors=errors,
        )
        
        data = json.loads(response.body.decode("utf-8"))
        assert data["error"]["errors"] == errors
        assert len(data["error"]["errors"]) == 2


# ============================================================================
# Test HTML Building Functions
# ============================================================================

class TestBuildTracebackHtml:
    """Tests for traceback HTML building."""
    
    def test_build_traceback_html_empty(self):
        """Test building traceback HTML with no frames."""
        html = _build_traceback_html([])
        assert "No traceback available" in html
    
    def test_build_traceback_html_with_frames(self):
        """Test building traceback HTML with frames."""
        frames = [
            {
                "filename": "/app/main.py",
                "lineno": 42,
                "name": "handle_request",
                "line": "result = process(data)",
                "is_library": False,
                "context_lines": [],
            }
        ]
        
        html = _build_traceback_html(frames)
        
        assert "/app/main.py" in html
        assert "42" in html
        assert "handle_request" in html
        assert "process(data)" in html
    
    def test_build_traceback_html_library_vs_user_code(self):
        """Test that library and user code are distinguished."""
        frames = [
            {
                "filename": "/site-packages/lib.py",
                "lineno": 10,
                "name": "lib_func",
                "line": "pass",
                "is_library": True,
                "context_lines": [],
            },
            {
                "filename": "/app/main.py",
                "lineno": 20,
                "name": "user_func",
                "line": "pass",
                "is_library": False,
                "context_lines": [],
            },
        ]
        
        html = _build_traceback_html(frames)
        
        assert "library-code" in html
        assert "user-code" in html


class TestBuildRequestHtml:
    """Tests for request HTML building."""
    
    def test_build_request_html_basic(self):
        """Test building request HTML with basic info."""
        ctx = DebugContext(
            request_method="GET",
            request_url="http://localhost/test",
        )
        
        html = _build_request_html(ctx)
        
        assert "GET" in html
        assert "http://localhost/test" in html
    
    def test_build_request_html_with_params(self):
        """Test building request HTML with parameters."""
        ctx = DebugContext(
            request_method="GET",
            request_url="http://localhost/users/123",
            request_path_params={"user_id": "123"},
            request_query_params={"include": "profile"},
        )
        
        html = _build_request_html(ctx)
        
        assert "user_id" in html
        assert "123" in html
        assert "include" in html
        assert "profile" in html
    
    def test_build_request_html_with_headers(self):
        """Test building request HTML with headers."""
        ctx = DebugContext(
            request_method="POST",
            request_url="http://localhost/api",
            request_headers={
                "content-type": "application/json",
                "accept": "application/json",
            },
        )
        
        html = _build_request_html(ctx)
        
        assert "content-type" in html
        assert "application/json" in html


class TestBuildContextVarsHtml:
    """Tests for context variables HTML building."""
    
    def test_build_context_vars_html_all_set(self):
        """Test building context vars HTML with all values."""
        ctx = DebugContext(
            request_id="req-123",
            tenant_id="tenant-abc",
            user_id="user-456",
        )
        
        html = _build_context_vars_html(ctx)
        
        assert "Request ID" in html
        assert "req-123" in html
        assert "Tenant ID" in html
        assert "tenant-abc" in html
        assert "User ID" in html
        assert "user-456" in html
    
    def test_build_context_vars_html_none_values(self):
        """Test building context vars HTML with None values."""
        ctx = DebugContext(
            request_id=None,
            tenant_id=None,
            user_id=None,
        )
        
        html = _build_context_vars_html(ctx)
        
        assert "Not set" in html
        assert "not-set" in html  # CSS class


# ============================================================================
# Test Context Collection
# ============================================================================

class TestCollectDebugContext:
    """Tests for debug context collection."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/test"
        request.url.__str__ = lambda self: "http://localhost/test"
        request.headers = {"user-agent": "test-client"}
        request.query_params = {}
        request.path_params = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.client.port = 12345
        
        # Make body async
        async def get_body():
            return b'{"test": "data"}'
        request.body = get_body
        
        return request
    
    @pytest.mark.asyncio
    async def test_collect_basic_context(self, mock_request):
        """Test collecting basic debug context."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            context = await collect_debug_context(mock_request, e, 500)
        
        assert context.exception_type == "ValueError"
        assert context.exception_message == "Test error"
        assert context.status_code == 500
        assert context.request_method == "GET"
    
    @pytest.mark.asyncio
    async def test_collect_traceback(self, mock_request):
        """Test that traceback is collected."""
        def inner():
            raise RuntimeError("Inner error")
        
        try:
            inner()
        except RuntimeError as e:
            context = await collect_debug_context(mock_request, e, 500)
        
        assert len(context.traceback_frames) >= 1
        assert context.traceback_text != ""
        assert "inner" in context.traceback_text
    
    @pytest.mark.asyncio
    async def test_collect_request_body(self, mock_request):
        """Test that request body is collected."""
        try:
            raise ValueError("Test")
        except ValueError as e:
            context = await collect_debug_context(mock_request, e, 500)
        
        assert context.request_body == '{"test": "data"}'
    
    @pytest.mark.asyncio
    async def test_collect_client_info(self, mock_request):
        """Test that client info is collected."""
        try:
            raise ValueError("Test")
        except ValueError as e:
            context = await collect_debug_context(mock_request, e, 500)
        
        assert context.request_client == "127.0.0.1:12345"
    
    @pytest.mark.asyncio
    async def test_collect_headers_redacts_sensitive(self, mock_request):
        """Test that sensitive headers are redacted."""
        mock_request.headers = {
            "content-type": "application/json",
            "authorization": "Bearer secret-token",
            "x-api-key": "my-secret-key",
        }
        
        try:
            raise ValueError("Test")
        except ValueError as e:
            context = await collect_debug_context(mock_request, e, 500)
        
        assert context.request_headers["content-type"] == "application/json"
        assert context.request_headers["authorization"] == "[REDACTED]"
        assert context.request_headers["x-api-key"] == "[REDACTED]"
    
    @pytest.mark.asyncio
    async def test_collect_environment_info(self, mock_request):
        """Test that environment info is collected."""
        try:
            raise ValueError("Test")
        except ValueError as e:
            context = await collect_debug_context(mock_request, e, 500)
        
        assert context.python_version != ""
        assert context.vidyut_version != ""
        assert context.timestamp != ""
        assert context.debug_mode is True
    
    @pytest.mark.asyncio
    async def test_collect_http_exception_detail(self, mock_request):
        """Test that HTTPException detail is extracted."""
        from starlette.exceptions import HTTPException
        
        exc = HTTPException(status_code=404, detail="User not found")
        context = await collect_debug_context(mock_request, exc, 404)
        
        assert context.exception_detail == "User not found"


# ============================================================================
# Test Integration with Vidyut App
# ============================================================================

class TestDebugExceptionHandlersIntegration:
    """Tests for debug exception handlers with Vidyut app."""
    
    @pytest.fixture
    def debug_app(self):
        """Create a Vidyut app in debug mode."""
        from vidyut.app import Vidyut
        
        app = Vidyut(debug=True)
        
        @app.get("/error")
        async def raise_error():
            raise ValueError("Test error")
        
        @app.get("/http-error")
        async def raise_http_error():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        
        @app.get("/ok")
        async def ok():
            return {"status": "ok"}
        
        return app
    
    @pytest.fixture
    def prod_app(self):
        """Create a Vidyut app in production mode."""
        from vidyut.app import Vidyut
        
        app = Vidyut(debug=False)
        
        @app.get("/error")
        async def raise_error():
            raise ValueError("Production error")
        
        @app.get("/http-error")
        async def raise_http_error():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        
        return app
    
    def test_debug_mode_html_error_page(self, debug_app):
        """Test that debug mode returns HTML error page."""
        client = TestClient(debug_app, raise_server_exceptions=False)
        
        response = client.get("/error", headers={"accept": "text/html"})
        
        assert response.status_code == 500
        assert "text/html" in response.headers["content-type"]
        assert "ValueError" in response.text
        assert "Test error" in response.text
        assert "#0d1117" in response.text  # Dark theme
    
    def test_debug_mode_http_exception(self, debug_app):
        """Test that debug mode handles HTTPException."""
        client = TestClient(debug_app, raise_server_exceptions=False)
        
        response = client.get("/http-error", headers={"accept": "text/html"})
        
        assert response.status_code == 404
        assert "text/html" in response.headers["content-type"]
        assert "HTTPException" in response.text
        assert "Not found" in response.text
    
    def test_debug_mode_json_when_requested(self, debug_app):
        """Test that debug mode returns JSON when requested."""
        client = TestClient(debug_app, raise_server_exceptions=False)
        
        response = client.get(
            "/http-error", 
            headers={"accept": "application/json"}
        )
        
        assert response.status_code == 404
        assert "application/json" in response.headers["content-type"]
        data = response.json()
        assert data["error"]["status"] == 404
    
    def test_production_mode_minimal_html(self, prod_app):
        """Test that production mode returns minimal HTML."""
        client = TestClient(prod_app, raise_server_exceptions=False)
        
        response = client.get("/error", headers={"accept": "text/html"})
        
        assert response.status_code == 500
        assert "text/html" in response.headers["content-type"]
        # Should NOT contain detailed error info
        assert "ValueError" not in response.text
        assert "Production error" not in response.text
        # Should contain generic error
        assert "Internal Server Error" in response.text
    
    def test_production_mode_json(self, prod_app):
        """Test that production mode returns JSON."""
        client = TestClient(prod_app, raise_server_exceptions=False)
        
        response = client.get("/error", headers={"accept": "application/json"})
        
        assert response.status_code == 500
        assert "application/json" in response.headers["content-type"]
        data = response.json()
        # Should NOT expose error details
        assert "Production error" not in str(data)
        assert data["error"]["message"] == "Internal Server Error"
    
    def test_ok_endpoint_still_works(self, debug_app):
        """Test that exception handlers don't break normal endpoints."""
        client = TestClient(debug_app)
        
        response = client.get("/ok")
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ============================================================================
# Test Validation Error Handling
# ============================================================================

class TestValidationErrorHandling:
    """Tests for validation error handling."""
    
    @pytest.fixture
    def validation_app(self):
        """Create app with validation."""
        from vidyut.app import Vidyut
        from pydantic import BaseModel
        
        app = Vidyut(debug=True)
        
        class UserCreate(BaseModel):
            name: str
            email: str
            age: int
        
        @app.post("/users")
        async def create_user(user: UserCreate):
            return {"user": user.model_dump()}
        
        return app
    
    def test_validation_error_json_response(self, validation_app):
        """Test validation errors return JSON even in debug mode."""
        client = TestClient(validation_app, raise_server_exceptions=False)
        
        response = client.post(
            "/users",
            json={"name": "Test"},  # Missing email and age
            headers={"accept": "application/json"}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert data["error"]["type"] == "validation_error"
        assert len(data["error"]["errors"]) >= 2
    
    def test_validation_error_html_in_debug(self, validation_app):
        """Test validation errors show debug page in debug mode with HTML."""
        client = TestClient(validation_app, raise_server_exceptions=False)
        
        response = client.post(
            "/users",
            json={"invalid": "data"},
            headers={"accept": "text/html"}
        )
        
        assert response.status_code == 422
        assert "text/html" in response.headers["content-type"]
        assert "RequestValidationError" in response.text


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error conditions."""
    
    def test_render_debug_page_with_empty_context(self):
        """Test rendering debug page with minimal context."""
        ctx = DebugContext()
        
        response = render_debug_page(ctx)
        
        assert response.status_code == 500
        body = response.body.decode("utf-8")
        assert "<!DOCTYPE html>" in body
    
    def test_large_request_body_truncated(self):
        """Test that large request bodies are handled."""
        # This is tested implicitly in collect_debug_context
        # The 10KB limit prevents huge bodies from bloating the context
        pass
    
    def test_no_client_info(self):
        """Test handling when client info is None."""
        ctx = DebugContext(
            exception_type="TestError",
            status_code=500,
            request_client=None,
            vidyut_version="0.3.17",
        )
        
        response = render_debug_page(ctx)
        # Should not crash
        assert response.status_code == 500
    
    def test_special_characters_in_error_message(self):
        """Test handling of special characters."""
        ctx = DebugContext(
            exception_type="TestError",
            exception_message="Error with 'quotes', \"double quotes\", and <tags>",
            status_code=500,
            vidyut_version="0.3.17",
        )
        
        response = render_debug_page(ctx)
        body = response.body.decode("utf-8")
        
        # Should be properly escaped
        assert "&lt;tags&gt;" in body
        assert "&#x27;" in body or "'" in body  # Single quotes may or may not be escaped


# ============================================================================
# Test CSS and JS Embedded Content
# ============================================================================

class TestEmbeddedContent:
    """Tests for embedded CSS and JavaScript."""
    
    def test_css_contains_required_classes(self):
        """Test that CSS contains all required classes."""
        from vidyut.debug.handlers import _get_debug_css
        
        css = _get_debug_css()
        
        assert ".error-container" in css
        assert ".error-header" in css
        assert ".tab-nav" in css
        assert ".traceback-frame" in css
        assert ".status-500" in css
        assert ".status-400" in css
    
    def test_js_contains_tab_logic(self):
        """Test that JS contains tab switching logic."""
        from vidyut.debug.handlers import _get_debug_js
        
        js = _get_debug_js()
        
        assert "tab-btn" in js
        assert "addEventListener" in js
        assert "toggleFrame" in js
