"""
Tests for AI exporters.

Tests:
- export_tools_as_generic
- export_tools_as_mcp
- export_tools_as_openai_functions
- export_tools_as_langchain
"""

import pytest
from typing import List

from aksara.ai.models import AiTool
from aksara.ai.exporters import (
    export_tools_as_generic,
    export_tools_as_mcp,
    export_tools_as_openai_functions,
    export_tools_as_langchain,
)


# =============================================================================
# Test Data
# =============================================================================

def create_test_tools() -> List[AiTool]:
    """Create a set of test tools for export testing."""
    return [
        AiTool(
            name="users_list",
            title="List Users",
            description="Get a paginated list of users",
            http_method="GET",
            path="/api/users/",
            kind="query",
            model="User",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 20},
                    "offset": {"type": "integer", "default": 0},
                },
            },
            requires_auth=True,
            permissions=["IsAuthenticated"],
            ai_tags=["read_only", "safe"],
        ),
        AiTool(
            name="users_create",
            title="Create User",
            description="Create a new user account",
            http_method="POST",
            path="/api/users/",
            kind="mutation",
            model="User",
            input_schema={
                "type": "object",
                "properties": {
                    "email": {"type": "string", "format": "email"},
                    "password": {"type": "string", "minLength": 8},
                },
                "required": ["email", "password"],
            },
            requires_auth=True,
            requires_admin=True,
            permissions=["IsAuthenticated", "IsAdminUser"],
            ai_tags=["write", "mutation"],
        ),
        AiTool(
            name="posts_publish",
            title="Publish Post",
            description="Publish a draft post",
            http_method="POST",
            path="/api/posts/{pk}/publish",
            kind="action",
            model="Post",
            input_schema={
                "type": "object",
                "properties": {
                    "pk": {"type": "string", "description": "Post ID"},
                },
                "required": ["pk"],
            },
            requires_auth=True,
            permissions=["IsAuthenticated"],
            ai_tags=["write", "action"],
        ),
    ]


# =============================================================================
# Generic Export Tests
# =============================================================================

class TestExportToolsAsGeneric:
    """Tests for export_tools_as_generic."""
    
    def test_export_returns_list_of_dicts(self):
        """Export returns a list of dictionaries."""
        tools = create_test_tools()
        result = export_tools_as_generic(tools)
        
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(item, dict) for item in result)
    
    def test_export_preserves_all_fields(self):
        """Export preserves all tool fields."""
        tools = create_test_tools()
        result = export_tools_as_generic(tools)
        
        user_list = result[0]
        
        assert user_list["name"] == "users_list"
        assert user_list["title"] == "List Users"
        assert user_list["description"] == "Get a paginated list of users"
        assert user_list["http_method"] == "GET"
        assert user_list["path"] == "/api/users/"
        assert user_list["kind"] == "query"
        assert user_list["model"] == "User"
        assert user_list["requires_auth"] is True
        assert user_list["ai_exposed"] is True
        assert "read_only" in user_list["ai_tags"]
    
    def test_export_empty_list(self):
        """Export handles empty list."""
        result = export_tools_as_generic([])
        
        assert result == []
    
    def test_export_input_schema_preserved(self):
        """Input schema is fully preserved."""
        tools = create_test_tools()
        result = export_tools_as_generic(tools)
        
        create_tool = result[1]
        input_schema = create_tool["input_schema"]
        
        assert input_schema["type"] == "object"
        assert "email" in input_schema["properties"]
        assert input_schema["required"] == ["email", "password"]


# =============================================================================
# MCP Export Tests
# =============================================================================

class TestExportToolsAsMcp:
    """Tests for export_tools_as_mcp."""
    
    def test_mcp_export_structure(self):
        """MCP export has correct structure."""
        tools = create_test_tools()
        result = export_tools_as_mcp(tools)
        
        assert isinstance(result, list)
        assert len(result) == 3
        
        # Check first tool structure
        tool = result[0]
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert "metadata" in tool
    
    def test_mcp_input_schema_format(self):
        """MCP inputSchema has correct format."""
        tools = create_test_tools()
        result = export_tools_as_mcp(tools)
        
        tool = result[1]  # users_create
        input_schema = tool["inputSchema"]
        
        assert input_schema["type"] == "object"
        assert "properties" in input_schema
        assert "required" in input_schema
        assert "email" in input_schema["properties"]
    
    def test_mcp_metadata_contains_http_info(self):
        """MCP metadata contains HTTP information."""
        tools = create_test_tools()
        result = export_tools_as_mcp(tools)
        
        tool = result[0]
        metadata = tool["metadata"]
        
        assert metadata["http_method"] == "GET"
        assert metadata["path"] == "/api/users/"
        assert metadata["kind"] == "query"
        assert metadata["model"] == "User"
        assert metadata["requires_auth"] is True
        assert "tags" in metadata
    
    def test_mcp_metadata_permissions(self):
        """MCP metadata includes permissions."""
        tools = create_test_tools()
        result = export_tools_as_mcp(tools)
        
        admin_tool = result[1]  # users_create
        metadata = admin_tool["metadata"]
        
        assert "IsAuthenticated" in metadata["permissions"]
        assert "IsAdminUser" in metadata["permissions"]
        assert metadata["requires_admin"] is True
    
    def test_mcp_empty_list(self):
        """MCP export handles empty list."""
        result = export_tools_as_mcp([])
        assert result == []


# =============================================================================
# OpenAI Functions Export Tests
# =============================================================================

class TestExportToolsAsOpenAI:
    """Tests for export_tools_as_openai_functions."""
    
    def test_openai_export_structure(self):
        """OpenAI export has correct structure."""
        tools = create_test_tools()
        result = export_tools_as_openai_functions(tools)
        
        assert isinstance(result, list)
        assert len(result) == 3
        
        func = result[0]
        assert "name" in func
        assert "description" in func
        assert "parameters" in func
    
    def test_openai_parameters_format(self):
        """OpenAI parameters match expected format."""
        tools = create_test_tools()
        result = export_tools_as_openai_functions(tools)
        
        func = result[1]  # users_create
        params = func["parameters"]
        
        assert params["type"] == "object"
        assert "properties" in params
        assert "required" in params
        assert "email" in params["properties"]
    
    def test_openai_function_name_and_desc(self):
        """OpenAI function has correct name and description."""
        tools = create_test_tools()
        result = export_tools_as_openai_functions(tools)
        
        func = result[0]
        
        assert func["name"] == "users_list"
        assert func["description"] == "Get a paginated list of users"


# =============================================================================
# LangChain Export Tests
# =============================================================================

class TestExportToolsAsLangChain:
    """Tests for export_tools_as_langchain."""
    
    def test_langchain_export_structure(self):
        """LangChain export has correct structure."""
        tools = create_test_tools()
        result = export_tools_as_langchain(tools)
        
        assert isinstance(result, list)
        assert len(result) == 3
        
        tool = result[0]
        assert "name" in tool
        assert "description" in tool
        assert "args_schema" in tool
        assert "metadata" in tool
    
    def test_langchain_metadata_contains_http_info(self):
        """LangChain metadata contains HTTP information."""
        tools = create_test_tools()
        result = export_tools_as_langchain(tools)
        
        tool = result[2]  # posts_publish
        metadata = tool["metadata"]
        
        assert metadata["http_method"] == "POST"
        assert metadata["path"] == "/api/posts/{pk}/publish"
        assert metadata["kind"] == "action"
        assert metadata["model"] == "Post"
    
    def test_langchain_args_schema(self):
        """LangChain args_schema is correct."""
        tools = create_test_tools()
        result = export_tools_as_langchain(tools)
        
        tool = result[1]
        args_schema = tool["args_schema"]
        
        assert args_schema["type"] == "object"
        assert "email" in args_schema["properties"]
    
    def test_langchain_return_direct(self):
        """LangChain tools have return_direct=False by default."""
        tools = create_test_tools()
        result = export_tools_as_langchain(tools)
        
        for tool in result:
            assert tool["return_direct"] is False
