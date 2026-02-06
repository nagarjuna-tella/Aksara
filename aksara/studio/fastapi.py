"""
Aksara Studio FastAPI Endpoints

HTTP endpoints for Studio IDE integration.

v0.5.0 Endpoints:
- GET /studio/handshake - Complete project handshake for Studio
- GET /studio/context/summary - Lightweight schema summary
- GET /studio/health - Simple health check with DB status

v0.5.1 Additions:
- GET /studio/migrations/summary - Per-app migration statistics
- GET /studio/schema/handshake - JSON schema for StudioHandshake model
- Origin-based security checks

v0.5.2 Additions:
- GET /studio/runtime/info - Runtime diagnostics
- GET /studio/runtime/routes - Route metadata
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request

from aksara.studio.models import (
    StudioContextSummary,
    StudioHandshake,
    StudioHealthResponse,
    StudioMigrationSummary,
    # v0.5.2: Runtime models
    StudioRuntimeInfo,
    StudioRouteInfo,
)
from aksara.studio.utils import (
    build_context_summary,
    build_health_response,
    build_migration_summary,
    build_studio_handshake,
    # v0.5.2: Runtime utils
    build_runtime_info,
    build_routes_info,
)


# =============================================================================
# v0.5.1: Origin Security
# =============================================================================

async def verify_studio_origin(request: Request) -> None:
    """
    Verify that the request Origin is allowed for Studio access.
    
    v0.5.1: Security dependency for Studio endpoints.
    
    Rules:
    - If studio_allowed_origins is empty or ["*"], allow all origins
    - Otherwise, check Origin header against the allowed list
    - Missing Origin header is allowed (same-origin requests, CLI)
    
    Raises:
        HTTPException 403 if origin is not allowed
    """
    from aksara.conf import settings
    
    allowed_origins = getattr(settings, 'studio_allowed_origins', [])
    
    # If no origins configured or wildcard, allow all
    if not allowed_origins or "*" in allowed_origins:
        return
    
    # Get the Origin header
    origin = request.headers.get("origin")
    
    # Allow requests without Origin (same-origin, CLI, server-to-server)
    if origin is None:
        return
    
    # Check if origin is in allowed list
    if origin in allowed_origins:
        return
    
    # Origin not allowed
    raise HTTPException(
        status_code=403,
        detail=f"Origin '{origin}' is not allowed. Allowed origins: {allowed_origins}",
    )


router = APIRouter(tags=["Studio"], dependencies=[Depends(verify_studio_origin)])


@router.get("/studio/handshake", response_model=StudioHandshake)
async def studio_handshake(request: Request) -> StudioHandshake:
    """
    Complete handshake endpoint for Studio IDE.
    
    Returns:
        StudioHandshake with:
        - Project metadata (name, version, aksara_version, python_version)
        - Database status (connected, pool info, latency)
        - Available capabilities (read, write, ai_tools, etc.)
        - Checksums for caching (schema, migrations, settings, routes)
        - API endpoint URLs
    
    Example response:
        {
            "protocol_version": "1.0",
            "timestamp": "2024-01-15T10:30:00Z",
            "project": {
                "name": "My App",
                "version": "1.0.0",
                "aksara_version": "0.5.0",
                "python_version": "3.11.5",
                "debug_mode": true,
                "environment": "development"
            },
            "database": {
                "connected": true,
                "dialect": "postgresql",
                "pool_size": 10,
                "pool_available": 8
            },
            "capabilities": ["read_schema", "read_data", "ai_tools", ...],
            "checksums": {
                "schema_checksum": "abc123...",
                "migrations_checksum": "def456...",
                ...
            },
            "endpoints": {
                "context_full": "/ai/context/full",
                "tools": "/ai/tools",
                ...
            }
        }
    """
    return await build_studio_handshake(request.app)


@router.get("/studio/context/summary", response_model=StudioContextSummary)
async def studio_context_summary(request: Request) -> StudioContextSummary:
    """
    Lightweight context summary endpoint.
    
    Use this for quick status checks without transferring full schema.
    For full context, use GET /ai/context/full instead.
    
    Returns:
        StudioContextSummary with:
        - Counts (models, viewsets, routes, ai_tools, migrations)
        - Model list with name, table_name, field_count
        - Checksums for cache invalidation
    
    Example response:
        {
            "model_count": 5,
            "viewset_count": 3,
            "route_count": 25,
            "ai_tool_count": 15,
            "migration_count": 10,
            "pending_migrations": 0,
            "models": [
                {
                    "name": "User",
                    "table_name": "users",
                    "field_count": 6,
                    "has_relations": true
                },
                ...
            ],
            "checksums": { ... }
        }
    """
    return await build_context_summary(request.app)


@router.get("/studio/health", response_model=StudioHealthResponse)
async def studio_health(request: Request) -> StudioHealthResponse:
    """
    Simple health check endpoint for Studio.
    
    Returns:
        StudioHealthResponse with:
        - status: "healthy" or "degraded"
        - aksara_version
        - database status
        - timestamp
    
    Example response:
        {
            "status": "healthy",
            "aksara_version": "0.5.0",
            "database": {
                "connected": true,
                "dialect": "postgresql",
                "pool_size": 10,
                "pool_available": 8
            },
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    return await build_health_response(request.app)


# =============================================================================
# v0.5.1: New Endpoints
# =============================================================================

@router.get("/studio/migrations/summary", response_model=StudioMigrationSummary)
async def studio_migrations_summary(request: Request) -> StudioMigrationSummary:
    """
    Per-app migration statistics endpoint.
    
    v0.5.1: New endpoint for detailed migration information.
    
    Returns:
        StudioMigrationSummary with:
        - Total, applied, pending migration counts
        - Per-app breakdown with head migrations
        - Detected conflicts with descriptions
        - Migrations checksum for caching
    
    Example response:
        {
            "total_migrations": 15,
            "applied_migrations": 12,
            "pending_migrations": 3,
            "apps": [
                {
                    "app_label": "auth",
                    "total": 5,
                    "applied": 5,
                    "pending": 0,
                    "has_conflicts": false,
                    "head_migrations": ["0005_add_last_login"]
                },
                {
                    "app_label": "blog",
                    "total": 10,
                    "applied": 7,
                    "pending": 3,
                    "has_conflicts": false,
                    "head_migrations": ["0010_add_tags"]
                }
            ],
            "conflicts": [],
            "migrations_checksum": "abc123...",
            "last_applied": "0005_add_last_login"
        }
    """
    return await build_migration_summary(request.app)


@router.get("/studio/schema/handshake", response_model=Dict[str, Any])
async def studio_schema_handshake(request: Request) -> Dict[str, Any]:
    """
    JSON Schema for the StudioHandshake model.
    
    v0.5.1: New endpoint for schema validation and documentation.
    
    Returns the Pydantic-generated JSON Schema for the StudioHandshake
    response model. Useful for:
    - TypeScript type generation
    - API documentation
    - Client-side validation
    
    Returns:
        JSON Schema object for StudioHandshake model
    
    Example response:
        {
            "$defs": { ... },
            "properties": {
                "protocol_version": {
                    "default": "1.0",
                    "description": "Studio protocol version",
                    "type": "string"
                },
                ...
            },
            "required": ["project", "database", "capabilities", "checksums"],
            "title": "StudioHandshake",
            "type": "object"
        }
    """
    return StudioHandshake.model_json_schema()


# =============================================================================
# v0.5.2: Runtime Endpoints
# =============================================================================

@router.get("/studio/runtime/info", response_model=StudioRuntimeInfo)
async def studio_runtime_info(request: Request) -> StudioRuntimeInfo:
    """
    Runtime diagnostics endpoint.
    
    v0.5.2: Read-only runtime info for Studio and CLI.
    
    Returns process information, environment details, and service status.
    Useful for debugging, monitoring, and development tools.
    
    Returns:
        StudioRuntimeInfo with:
        - app_version: Aksara version
        - python_version: Python interpreter version
        - debug: Whether debug mode is enabled
        - env: Environment name (development, production, etc.)
        - pid: Process ID
        - start_time: When the process started
        - uptime_seconds: Seconds since start
        - database_status: "ok", "degraded", or "disconnected"
        - pending_migrations: Number of pending migrations
        - installed_apps: List of installed app labels
        - studio_enabled: Whether Studio is enabled
        - studio_base_path: Base path for Studio endpoints
    
    Example response:
        {
            "app_version": "0.5.2",
            "python_version": "3.11.5",
            "debug": true,
            "env": "development",
            "pid": 12345,
            "start_time": "2026-02-06T10:00:00Z",
            "uptime_seconds": 3600.5,
            "database_status": "ok",
            "pending_migrations": 0,
            "installed_apps": ["aksara.contrib.auth", "app"],
            "studio_enabled": true,
            "studio_base_path": "/studio"
        }
    """
    return await build_runtime_info(request.app)


@router.get("/studio/runtime/routes", response_model=List[StudioRouteInfo])
async def studio_runtime_routes(request: Request) -> List[StudioRouteInfo]:
    """
    Route metadata endpoint.
    
    v0.5.2: Read-only route info for Studio.
    
    Returns metadata about all registered routes in the application.
    Useful for API documentation, debugging, and tooling.
    
    Returns:
        List of StudioRouteInfo with:
        - path: Route path pattern
        - methods: HTTP methods handled
        - name: Route name if set
        - app_label: Derived app label if possible
        - is_studio: Whether this is a Studio endpoint
        - is_admin: Whether this is an Admin endpoint
        - is_ai: Whether this is an AI endpoint
    
    Example response:
        [
            {
                "path": "/studio/handshake",
                "methods": ["GET"],
                "name": "studio_handshake",
                "app_label": "studio",
                "is_studio": true,
                "is_admin": false,
                "is_ai": false
            },
            {
                "path": "/ai/context/full",
                "methods": ["GET"],
                "name": "ai_context_full",
                "app_label": "ai",
                "is_studio": false,
                "is_admin": false,
                "is_ai": true
            }
        ]
    """
    return build_routes_info(request.app)
