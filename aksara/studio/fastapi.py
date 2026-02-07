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

v0.5.3 Additions:
- GET /studio/ui - Static dashboard UI
- GET /studio/assets/* - Static assets (CSS, JS, icons)

v0.5.4 Additions:
- GET /studio/ai/context - AI context export for external AI tools
- GET /studio/ai/schemas - JSON schemas for AI operations
- GET /studio/ai/prompts - Prompt templates for AI interactions

v0.5.10 Additions:
- GET /studio/db/queries - Query inspector with stats and recent batches
- GET /studio/db/queries/{request_id} - Detailed query batch for a request

v0.5.11 Additions:
- GET /studio/ai/profiles - AI provider profiles and model configurations
- GET /studio/ai/secrets - AI secret hints (env var names, not values)
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from aksara.studio.models import (
    StudioContextSummary,
    StudioHandshake,
    StudioHealthResponse,
    StudioMigrationSummary,
    # v0.5.2: Runtime models
    StudioRuntimeInfo,
    StudioRouteInfo,
    # v0.5.4: AI Integration models
    StudioAiContextExport,
    StudioAiSchemas,
    StudioAiPrompts,
    # v0.5.10: Query Inspector models
    StudioQueryInspector,
    StudioQueryBatch,
    # v0.5.11: AI Profiles models
    StudioAiProfileSetSummary,
    StudioAiSecretsInfo,
)
from aksara.studio.utils import (
    build_context_summary,
    build_health_response,
    build_migration_summary,
    build_studio_handshake,
    # v0.5.2: Runtime utils
    build_runtime_info,
    build_routes_info,
    # v0.5.4: AI Integration utils
    build_ai_context_export,
    build_ai_schemas,
    build_ai_prompts,
    # v0.5.10: Query Inspector utils
    build_query_inspector,
    build_query_batch_detail,
    # v0.5.11: AI Profiles utils
    build_ai_profile_set_summary,
    build_ai_secrets_info,
)

# v0.5.3: Static files directory
STATIC_DIR = Path(__file__).parent / "static"


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


# =============================================================================
# v0.5.4: Studio ↔ AI Integration Endpoints
# =============================================================================

@router.get("/studio/ai/context", response_model=StudioAiContextExport)
async def studio_ai_context(request: Request) -> StudioAiContextExport:
    """
    Export AI-friendly context bundle.
    
    v0.5.4: Returns a secrets-stripped context bundle that external AI tools
    can consume. Includes project metadata, models, routes, and available tools.
    
    This endpoint does NOT call any AI/LLM providers - it only formats
    existing application context for use with external AI tools.
    
    Returns:
        StudioAiContextExport with:
        - project: Basic metadata (name, version, environment)
        - models: Summarized model information
        - routes: Available API routes
        - tools: Available AI tools/operations
        - apps: Installed app labels
        - migration_status: Migration health snapshot
        - schema_checksum: For change detection
    
    Example Response:
        {
            "project": {
                "name": "My App",
                "version": "0.5.4",
                "environment": "development",
                "debug": true
            },
            "models": [
                {
                    "name": "User",
                    "table_name": "users",
                    "fields": ["id", "email", "name", "created_at"]
                }
            ],
            "routes": [
                {"path": "/api/users", "methods": ["GET", "POST"]}
            ],
            "tools": [
                {"name": "ai_query", "endpoint": "/ai/query", "safe": true}
            ],
            "schema_checksum": "abc123..."
        }
    """
    return await build_ai_context_export(request.app)


@router.get("/studio/ai/schemas", response_model=StudioAiSchemas)
async def studio_ai_schemas(request: Request) -> StudioAiSchemas:
    """
    Get JSON schemas for AI operations.
    
    v0.5.4: Returns schemas AI agents can use to generate valid requests
    for planning, patching, querying, and code generation.
    
    This endpoint does NOT call any AI/LLM providers - it returns
    static JSON schemas defining the expected request/response formats.
    
    Returns:
        StudioAiSchemas with:
        - plan_schema: JSON Schema for AiPlan requests
        - patch_schema: JSON Schema for AiPatchRequest
        - query_schema: JSON Schema for AiQueryPlan
        - codegen_schema: JSON Schema for AiCodegenRequest
        - context_schema: JSON Schema for AiFullContext (reference)
    
    Usage:
        External AI tools can:
        1. Fetch these schemas
        2. Use them to validate generated JSON
        3. Generate code/plans that conform to Aksara's API
    
    Example Response:
        {
            "plan_schema": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "steps": {"type": "array", ...}
                }
            },
            "query_schema": {...},
            ...
        }
    """
    return build_ai_schemas()


@router.get("/studio/ai/prompts", response_model=StudioAiPrompts)
async def studio_ai_prompts(request: Request) -> StudioAiPrompts:
    """
    Get prompt templates for AI interactions.
    
    v0.5.4: Returns pre-built prompt templates with placeholders
    that users can copy and use with external AI tools.
    
    This endpoint does NOT call any AI/LLM providers - it returns
    static text templates with placeholders like {context_json}.
    
    Returns:
        StudioAiPrompts with list of prompt templates, each containing:
        - id: Unique identifier (e.g., "add-field")
        - title: Human-friendly title
        - description: What the prompt is for
        - template: The prompt text with placeholders
        - placeholders: List of placeholder names
        - category: general, schema, migration, query, codegen
    
    Available Templates:
        - add-field: Generate plan to add a field to a model
        - refactor-model: Generate plan to refactor/split a model
        - fix-migrations: Generate plan to fix migration issues
        - natural-query: Convert natural language to query plan
        - generate-model: Generate code for a new model
        - explain-schema: Get explanation of current schema
    
    Example Response:
        {
            "prompts": [
                {
                    "id": "add-field",
                    "title": "Add Model Field",
                    "template": "Given this context: {context_json}...",
                    "placeholders": ["context_json", "plan_schema"]
                }
            ],
            "version": "1.0"
        }
    """
    return build_ai_prompts()


# =============================================================================
# v0.5.10: Query Inspector & Profiler Endpoints
# =============================================================================

@router.get("/studio/db/queries", response_model=StudioQueryInspector)
async def studio_db_queries(
    request: Request,
    include_queries: bool = False,
    limit_batches: int = 20,
    limit_slow: int = 20,
) -> StudioQueryInspector:
    """
    Query inspector endpoint for database profiling.
    
    v0.5.10: Returns query tracing stats, recent request batches, and slow queries.
    
    Args:
        include_queries: Include full query lists in batches (default: False)
        limit_batches: Max recent batches to return (default: 20)
        limit_slow: Max slow queries to return (default: 20)
        
    Returns:
        StudioQueryInspector with:
        - enabled: Whether tracing is currently enabled
        - slow_threshold_ms: Current slow query threshold
        - stats: Aggregate statistics
        - recent_batches: Recent request query batches
        - top_slow_queries: Slowest queries across all batches
    
    Example response:
        {
            "enabled": true,
            "slow_threshold_ms": 100.0,
            "stats": {
                "total_batches": 42,
                "total_queries": 187,
                "avg_queries_per_request": 4.45,
                "total_slow_queries": 3,
                "requests_with_slow_queries": 2,
                "requests_with_n_plus_one": 1
            },
            "recent_batches": [
                {
                    "request_id": "abc123",
                    "path": "/api/users",
                    "method": "GET",
                    "status_code": 200,
                    "total_duration_ms": 45.2,
                    "total_queries": 3,
                    "slow_queries": 0,
                    "n_plus_one_suspicions": []
                }
            ],
            "top_slow_queries": [
                {
                    "sql": "SELECT * FROM users WHERE ...",
                    "duration_ms": 152.3,
                    "operation": "SELECT",
                    "table": "users",
                    "is_slow": true
                }
            ]
        }
    
    Notes:
        - Requires db_trace_enabled=True in settings
        - Recent batches are stored in a ring buffer (last 100 requests)
        - Use include_queries=true to get full query lists (larger response)
    """
    return build_query_inspector(
        include_queries=include_queries,
        limit_batches=limit_batches,
        limit_slow=limit_slow,
    )


@router.get("/studio/db/queries/{request_id}", response_model=StudioQueryBatch)
async def studio_db_query_detail(
    request: Request,
    request_id: str,
) -> StudioQueryBatch:
    """
    Get detailed query batch for a specific request.
    
    v0.5.10: Returns full query list for a single request.
    
    Args:
        request_id: The request ID to look up
        
    Returns:
        StudioQueryBatch with full query list
        
    Raises:
        404 if request_id not found in trace storage
    
    Example response:
        {
            "request_id": "abc123",
            "path": "/api/users/1",
            "method": "GET",
            "status_code": 200,
            "started_at": "2024-01-15T10:30:00Z",
            "ended_at": "2024-01-15T10:30:00.045Z",
            "total_duration_ms": 45.2,
            "total_queries": 3,
            "slow_queries": 0,
            "n_plus_one_suspicions": [],
            "queries": [
                {
                    "sql": "SELECT * FROM users WHERE id = $1",
                    "params": [1],
                    "duration_ms": 12.5,
                    "operation": "SELECT",
                    "table": "users",
                    "timestamp": "2024-01-15T10:30:00.010Z",
                    "stack_summary": "views.py:42:get_user",
                    "is_slow": false
                }
            ]
        }
    """
    batch = build_query_batch_detail(request_id)
    if batch is None:
        raise HTTPException(
            status_code=404,
            detail=f"No trace found for request_id: {request_id}",
        )
    return batch


# =============================================================================
# v0.5.11: AI Profiles & Provider Contracts Endpoints
# =============================================================================

@router.get("/studio/ai/profiles", response_model=StudioAiProfileSetSummary)
async def studio_ai_profiles(request: Request) -> StudioAiProfileSetSummary:
    """
    Get AI provider profiles and model configurations.
    
    v0.5.11: Vendor-agnostic AI profile discovery endpoint.
    
    Returns:
        StudioAiProfileSetSummary with:
        - enabled: Whether AI profiles are enabled
        - providers: List of available AI providers
        - default_provider: Name of default provider
        - total_models: Total available models
        - environment: Current environment (dev/stage/prod)
    
    Example response:
        {
            "enabled": true,
            "providers": [
                {
                    "name": "example_openai_like",
                    "display_name": "Example OpenAI-like Provider (Demo)",
                    "kind": "openai",
                    "model_count": 3,
                    "default_model": "gpt-4o",
                    "has_custom_base_url": false,
                    "is_example": true,
                    "models": [
                        {
                            "name": "gpt-4o",
                            "display_name": "GPT-4 Omni",
                            "kind": "chat",
                            "max_input_tokens": 128000,
                            "max_output_tokens": 4096,
                            "supports_tools": true,
                            "supports_streaming": true,
                            "tags": ["fast", "multimodal"]
                        }
                    ]
                }
            ],
            "default_provider": "example_openai_like",
            "total_models": 6,
            "environment": "development"
        }
    """
    return build_ai_profile_set_summary(request.app)


@router.get("/studio/ai/secrets", response_model=StudioAiSecretsInfo)
async def studio_ai_secrets(request: Request) -> StudioAiSecretsInfo:
    """
    Get AI secret hints (env var names, never values).
    
    v0.5.11: Shows what environment variables are needed for AI providers.
    
    SECURITY: This endpoint NEVER returns actual secret values.
    Only env var names and whether they are configured are exposed.
    
    Returns:
        StudioAiSecretsInfo with:
        - secrets: List of secret hints with env var names
        - configured_count: Number of configured secrets
        - total_count: Total secrets required
    
    Example response:
        {
            "secrets": [
                {
                    "provider_name": "example_openai_like",
                    "env_var": "OPENAI_API_KEY",
                    "required": true,
                    "description": "OpenAI API key from platform.openai.com",
                    "is_configured": false
                }
            ],
            "configured_count": 0,
            "total_count": 2
        }
    """
    return build_ai_secrets_info()


# =============================================================================
# v0.5.3: Studio UI Endpoints
# =============================================================================

def _check_studio_ui_enabled() -> None:
    """
    Check if Studio UI is enabled.
    
    Raises HTTPException if:
    - Studio is disabled (enable_studio=False)
    - Studio UI is disabled (studio_ui_enabled=False)
    - Production mode without explicit exposure
    """
    from aksara.conf import settings
    
    # Check if Studio is enabled at all
    if not getattr(settings, 'enable_studio', True):
        raise HTTPException(
            status_code=404,
            detail="Studio is disabled. Set enable_studio=True to enable.",
        )
    
    # Check if Studio UI specifically is enabled
    if not getattr(settings, 'studio_ui_enabled', True):
        raise HTTPException(
            status_code=404,
            detail="Studio UI is disabled. Set studio_ui_enabled=True to enable.",
        )
    
    # Check production mode
    debug = getattr(settings, 'debug', False)
    expose_in_prod = getattr(settings, 'studio_expose_in_production', False)
    
    if not debug and not expose_in_prod:
        raise HTTPException(
            status_code=403,
            detail="Studio UI is not available in production mode. "
                   "Set studio_expose_in_production=True to expose in production.",
        )


@router.get("/studio/ui", response_class=HTMLResponse, include_in_schema=False)
async def studio_ui(request: Request) -> HTMLResponse:
    """
    Serve the Studio dashboard UI.
    
    v0.5.3: Static embedded dashboard.
    
    Returns:
        HTML page for the Studio dashboard.
    """
    _check_studio_ui_enabled()
    await verify_studio_origin(request)
    
    index_path = STATIC_DIR / "index.html"
    
    if not index_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Studio UI files not found. Package may be incomplete.",
        )
    
    # Read and return HTML
    import aksara
    content = index_path.read_text(encoding="utf-8")
    
    return HTMLResponse(
        content=content,
        headers={
            "Cache-Control": "no-store",
            "X-Aksara-Studio-Version": aksara.__version__,
        },
    )


@router.get("/studio/assets/{path:path}", include_in_schema=False)
async def studio_assets(request: Request, path: str) -> FileResponse:
    """
    Serve static assets for Studio UI.
    
    v0.5.3: CSS, JS, fonts, icons.
    
    Args:
        path: Asset path relative to static directory
        
    Returns:
        Static file with appropriate Content-Type.
    """
    _check_studio_ui_enabled()
    await verify_studio_origin(request)
    
    # Security: prevent directory traversal
    safe_path = Path(path).as_posix()
    if ".." in safe_path or safe_path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    
    file_path = STATIC_DIR / safe_path
    
    # Ensure file exists and is within STATIC_DIR
    try:
        file_path = file_path.resolve()
        if not str(file_path).startswith(str(STATIC_DIR.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")
    except (ValueError, OSError):
        raise HTTPException(status_code=400, detail="Invalid path")
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(str(file_path))
    
    # Override common types for accuracy
    suffix = file_path.suffix.lower()
    mime_overrides = {
        ".css": "text/css",
        ".js": "application/javascript",
        ".svg": "image/svg+xml",
        ".woff2": "font/woff2",
        ".woff": "font/woff",
        ".ttf": "font/ttf",
        ".json": "application/json",
    }
    
    media_type = mime_overrides.get(suffix, mime_type or "application/octet-stream")
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=3600",
        },
    )


def get_static_dir() -> Path:
    """
    Get the path to the Studio static assets directory.
    
    v0.5.3: For CLI ui-path command.
    
    Returns:
        Path to the static directory
    """
    return STATIC_DIR
