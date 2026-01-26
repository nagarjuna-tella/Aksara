"""
Vidyut AI Models

Core data structures for AI tool descriptors.

These Pydantic models define the canonical representation of AI tools
that can be exported to various agent frameworks (MCP, OpenAI, LangChain, etc.).
"""

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field

# Tool kind classification
ToolKind = Literal["query", "mutation", "action", "admin", "utility"]


class AiToolParam(BaseModel):
    """
    Describes a single parameter for an AI tool.
    
    Used within AiTool.input_schema to provide detailed parameter information.
    """
    name: str = Field(..., description="Parameter name")
    description: str = Field("", description="Human-readable parameter description")
    required: bool = Field(False, description="Whether this parameter is required")
    json_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema fragment for this parameter"
    )


class AiTool(BaseModel):
    """
    Canonical AI tool descriptor.
    
    Represents a single API endpoint/action that can be invoked by AI agents.
    This structure is designed to be convertible to various agent framework formats.
    
    Attributes:
        name: Unique tool identifier (e.g., "users_list", "posts_create")
        title: Human-readable title
        description: Brief natural-language description for AI reasoning
        http_method: HTTP method (GET, POST, PATCH, DELETE)
        path: API path (e.g., "/api/users/", "/api/users/{id}/publish")
        kind: Tool classification (query, mutation, action, admin, utility)
        model: Associated model name (e.g., "User", "Post")
        app_label: Application label if app discovery is used
        input_schema: JSON Schema for request body/params
        output_schema: Optional JSON Schema for response
        requires_auth: Whether authentication is required
        requires_admin: Whether admin privileges are required
        permissions: List of permission class names
        ai_tags: Free-form tags for AI reasoning ("safe", "read_only", "write", etc.)
        ai_exposed: Final decision after all checks (False if filtered out)
        model_schema_endpoint: Optional reference to model schema endpoint
    
    Example:
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
                    "offset": {"type": "integer", "default": 0}
                }
            },
            requires_auth=True,
            permissions=["IsAuthenticated"],
            ai_tags=["read_only", "safe"]
        )
    """
    
    # Identity
    name: str = Field(..., description="Unique tool identifier")
    title: str = Field(..., description="Human-readable title")
    description: str = Field("", description="Brief natural-language description")
    
    # HTTP/API details
    http_method: str = Field(..., description="HTTP method (GET, POST, etc.)")
    path: str = Field(..., description="API path")
    
    # Classification
    kind: ToolKind = Field("query", description="Tool type classification")
    model: Optional[str] = Field(None, description="Associated model name")
    app_label: Optional[str] = Field(None, description="Application label")
    
    # Schemas
    input_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for request body/params"
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional JSON Schema for response"
    )
    
    # Security
    requires_auth: bool = Field(False, description="Whether authentication is required")
    requires_admin: bool = Field(False, description="Whether admin privileges are required")
    permissions: List[str] = Field(
        default_factory=list,
        description="Permission class names"
    )
    
    # AI metadata
    ai_tags: List[str] = Field(
        default_factory=list,
        description="Free-form tags for AI reasoning"
    )
    ai_exposed: bool = Field(True, description="Whether tool is exposed to AI agents")
    
    # Optional references
    model_schema_endpoint: Optional[str] = Field(
        None,
        description="Endpoint for model schema (e.g., /ai/schema/User)"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "users_list",
                "title": "List Users",
                "description": "Get a paginated list of users",
                "http_method": "GET",
                "path": "/api/users/",
                "kind": "query",
                "model": "User",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20},
                        "offset": {"type": "integer", "default": 0}
                    }
                },
                "requires_auth": True,
                "permissions": ["IsAuthenticated"],
                "ai_tags": ["read_only", "safe"]
            }
        }
    }