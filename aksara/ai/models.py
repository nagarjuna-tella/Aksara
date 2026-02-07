"""
Aksara AI Models

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


# =============================================================================
# v0.5.13: Per-View AI Hints (Route-Level AI Metadata)
# =============================================================================

AiRiskLevel = Literal["low", "medium", "high"]
"""Risk level classification for AI operations."""

AiUsageKind = Literal["read_only", "write", "admin"]
"""Usage kind classification for AI operations.

- read_only: Only reads data, no side effects
- write: Modifies data
- admin: Sensitive/administrative operations
"""


class AiRouteHint(BaseModel):
    """
    Per-route/view AI hint metadata.
    
    Provides structured information about what a route does, how it should
    be used by LLMs, and how risky it is. This is metadata-only and 
    LLM-agnostic - no provider coupling.
    
    Attributes:
        app_label: Application label for namespacing
        view_name: ViewSet/View class name (e.g., "PostViewSet")
        route_name: Route identifier (e.g., "post-list", "post-publish")
        path: Full URL path (e.g., "/api/posts/{id}/publish/")
        methods: HTTP methods (e.g., ["GET"], ["POST"])
        title: Short label for the route (e.g., "Publish blog post")
        description: 1-3 sentence AI-facing description
        usage_kind: Read-only, write, or admin classification
        risk_level: Low, medium, or high risk level
        example_prompt: Example user prompt that would trigger this route
        example_input: Example request body/parameters
        example_output: Example response body
        recommended_model: Optional recommended model name
        recommended_provider: Optional recommended provider name
    """
    
    # Identity
    app_label: str = Field("", description="Application label")
    view_name: str = Field(..., description="ViewSet/View class name")
    route_name: str = Field(..., description="Route identifier")
    path: str = Field(..., description="Full URL path")
    methods: List[str] = Field(default_factory=list, description="HTTP methods")
    
    # Semantics
    title: str = Field(..., description="Short label for the route")
    description: str = Field("", description="AI-facing description")
    usage_kind: AiUsageKind = Field("read_only", description="Usage classification")
    risk_level: AiRiskLevel = Field("low", description="Risk level")
    
    # Examples (for LLMs)
    example_prompt: Optional[str] = Field(None, description="Example user prompt")
    example_input: Optional[Dict[str, Any]] = Field(None, description="Example request")
    example_output: Optional[Dict[str, Any]] = Field(None, description="Example response")
    
    # Optional recommendations
    recommended_model: Optional[str] = Field(None, description="Recommended AI model")
    recommended_provider: Optional[str] = Field(None, description="Recommended AI provider")
    
    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "example": {
                "app_label": "blog",
                "view_name": "PostViewSet",
                "route_name": "post-publish",
                "path": "/api/posts/{id}/publish/",
                "methods": ["POST"],
                "title": "Publish a blog post",
                "description": "Marks the given post as published. Call once user confirms publishing.",
                "usage_kind": "write",
                "risk_level": "medium",
                "example_prompt": "User says: 'Publish my draft about async APIs'",
                "example_input": {"id": 42},
                "example_output": {"id": 42, "is_published": True},
            }
        }
    }


class AiHintSet(BaseModel):
    """
    Collection of AI route hints.
    
    Groups all hints discovered from the application for easy export/display.
    """
    
    routes: List[AiRouteHint] = Field(default_factory=list, description="Route hints")
    total_count: int = Field(default=0, description="Total hint count")
    
    # Stats
    read_only_count: int = Field(default=0, description="Read-only routes")
    write_count: int = Field(default=0, description="Write routes")
    admin_count: int = Field(default=0, description="Admin routes")
    low_risk_count: int = Field(default=0, description="Low risk routes")
    medium_risk_count: int = Field(default=0, description="Medium risk routes")
    high_risk_count: int = Field(default=0, description="High risk routes")
    
    model_config = {
        "extra": "forbid",
    }