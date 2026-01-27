"""
Tests for AI FastAPI endpoints.

Tests:
- GET /ai/tools
- GET /ai/tools/mcp
- GET /ai/tools/openai
- GET /ai/tools/{tool_name}
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from aksara.ai.models import AiTool
from aksara.ai.registry import AiToolRegistry
from aksara.ai.fastapi import router


# =============================================================================
# Test Setup
# =============================================================================

def create_test_app() -> FastAPI:
    """Create a test FastAPI app with AI router."""
    app = FastAPI()
    
    # Create and populate registry
    registry = AiToolRegistry()
    
    # Add test tools
    registry.register_tool(AiTool(
        name="users_list",
        title="List Users",
        description="Get all users",
        http_method="GET",
        path="/api/users/",
        kind="query",
        model="User",
        requires_auth=False,
        ai_tags=["read_only"],
    ))
    
    registry.register_tool(AiTool(
        name="users_create",
        title="Create User",
        description="Create a user",
        http_method="POST",
        path="/api/users/",
        kind="mutation",
        model="User",
        requires_auth=True,
        permissions=["IsAuthenticated"],
        ai_tags=["write"],
    ))
    
    registry.register_tool(AiTool(
        name="admin_panel",
        title="Admin Panel",
        description="Admin operations",
        http_method="GET",
        path="/api/admin/",
        kind="admin",
        requires_auth=True,
        requires_admin=True,
        permissions=["IsAdminUser"],
        ai_tags=["admin"],
    ))
    
    app.ai_registry = registry
    app.include_router(router)
    
    return app


# =============================================================================
# GET /ai/tools Tests
# =============================================================================

class TestListAiToolsEndpoint:
    """Tests for GET /ai/tools endpoint."""
    
    def test_list_tools_anonymous(self):
        """Anonymous user gets public tools only."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.get("/ai/tools")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "tools" in data
        assert "count" in data
        assert "version" in data
        assert data["version"] == "0.4.0"
        
        # Anonymous should only get public tools
        tool_names = [t["name"] for t in data["tools"]]
        assert "users_list" in tool_names
        # Auth-required tools should be filtered out
        assert "users_create" not in tool_names
        assert "admin_panel" not in tool_names
    
    def test_list_tools_authenticated(self):
        """Authenticated user gets auth-required tools."""
        app = create_test_app()
        
        # Add middleware to set authenticated user
        @app.middleware("http")
        async def add_user(request, call_next):
            user = MagicMock()
            user.is_authenticated = True
            user.is_staff = False
            user.is_superuser = False
            request.state.user = user
            return await call_next(request)
        
        client = TestClient(app)
        response = client.get("/ai/tools")
        
        assert response.status_code == 200
        data = response.json()
        
        tool_names = [t["name"] for t in data["tools"]]
        assert "users_list" in tool_names
        assert "users_create" in tool_names
        # Admin tools still filtered
        assert "admin_panel" not in tool_names
    
    def test_list_tools_admin(self):
        """Admin user gets all tools."""
        app = create_test_app()
        
        @app.middleware("http")
        async def add_admin_user(request, call_next):
            user = MagicMock()
            user.is_authenticated = True
            user.is_staff = True
            user.is_superuser = False
            request.state.user = user
            return await call_next(request)
        
        client = TestClient(app)
        response = client.get("/ai/tools")
        
        assert response.status_code == 200
        data = response.json()
        
        tool_names = [t["name"] for t in data["tools"]]
        assert "users_list" in tool_names
        assert "users_create" in tool_names
        assert "admin_panel" in tool_names
    
    def test_list_tools_response_structure(self):
        """Response has correct structure."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.get("/ai/tools")
        data = response.json()
        
        # Check tool structure
        if data["tools"]:
            tool = data["tools"][0]
            assert "name" in tool
            assert "title" in tool
            assert "description" in tool
            assert "http_method" in tool
            assert "path" in tool
            assert "kind" in tool
            assert "ai_exposed" in tool


# =============================================================================
# GET /ai/tools/mcp Tests
# =============================================================================

class TestListAiToolsMcpEndpoint:
    """Tests for GET /ai/tools/mcp endpoint."""
    
    def test_mcp_endpoint_returns_mcp_format(self):
        """MCP endpoint returns MCP-formatted tools."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.get("/ai/tools/mcp")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "tools" in data
        assert "count" in data
        assert "version" in data
        
        # Check MCP format
        if data["tools"]:
            tool = data["tools"][0]
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert "metadata" in tool
            
            # Check metadata structure
            metadata = tool["metadata"]
            assert "http_method" in metadata
            assert "path" in metadata
            assert "kind" in metadata
    
    def test_mcp_tools_filtered_by_permissions(self):
        """MCP tools are filtered by permissions."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.get("/ai/tools/mcp")
        data = response.json()
        
        # Anonymous should only see public tools
        tool_names = [t["name"] for t in data["tools"]]
        assert "users_list" in tool_names
        assert "users_create" not in tool_names


# =============================================================================
# GET /ai/tools/openai Tests
# =============================================================================

class TestListAiToolsOpenAIEndpoint:
    """Tests for GET /ai/tools/openai endpoint."""
    
    def test_openai_endpoint_returns_functions(self):
        """OpenAI endpoint returns function definitions."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.get("/ai/tools/openai")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "functions" in data
        assert "count" in data
        assert "version" in data
        
        # Check function format
        if data["functions"]:
            func = data["functions"][0]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func


# =============================================================================
# GET /ai/tools/{tool_name} Tests
# =============================================================================

class TestGetAiToolEndpoint:
    """Tests for GET /ai/tools/{tool_name} endpoint."""
    
    def test_get_existing_tool(self):
        """Can retrieve a specific tool by name."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.get("/ai/tools/users_list")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "tool" in data
        assert "version" in data
        
        tool = data["tool"]
        assert tool["name"] == "users_list"
        assert tool["title"] == "List Users"
    
    def test_get_nonexistent_tool(self):
        """Returns 404 for nonexistent tool."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.get("/ai/tools/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "nonexistent" in data["detail"]
    
    def test_get_unauthorized_tool(self):
        """Returns 404 for tool user can't access."""
        app = create_test_app()
        client = TestClient(app)
        
        # Try to get admin-only tool as anonymous user
        response = client.get("/ai/tools/admin_panel")
        
        assert response.status_code == 404


# =============================================================================
# Integration Tests
# =============================================================================

class TestAiEndpointsIntegration:
    """Integration tests for AI endpoints."""
    
    def test_endpoints_work_without_registry(self):
        """Endpoints handle missing registry gracefully."""
        app = FastAPI()
        app.ai_registry = None
        app.include_router(router)
        
        client = TestClient(app)
        
        response = client.get("/ai/tools")
        assert response.status_code == 200
        data = response.json()
        assert data["tools"] == []
        assert data["count"] == 0
    
    def test_tool_counts_match(self):
        """Tool count matches actual tool list length."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.get("/ai/tools")
        data = response.json()
        
        assert data["count"] == len(data["tools"])
    
    def test_mcp_and_generic_tool_counts_match(self):
        """MCP and generic endpoints return same number of tools."""
        app = create_test_app()
        client = TestClient(app)
        
        generic_response = client.get("/ai/tools")
        mcp_response = client.get("/ai/tools/mcp")
        
        generic_count = generic_response.json()["count"]
        mcp_count = mcp_response.json()["count"]
        
        assert generic_count == mcp_count
