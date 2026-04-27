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

v0.5.12 Additions:
- GET /studio/ai/health - AI profile validation and health status

v0.5.13 Additions:
- GET /studio/ai/hints - Per-route AI hints for LLM guidance

v0.5.17 Additions:
- GET /studio/diagnostics - Full self-diagnostics report

v0.5.19 Additions:
- GET /studio/agent/context - Agent context gathering
- POST /studio/agent/prompt - Agent prompt generation

v0.5.20 Additions:
- GET /studio/agent/playbooks - List available agent playbooks
- POST /studio/agent/playbooks/prompt - Playbook-driven prompt generation

v0.5.21 Additions:
- POST /studio/db/plan - EXPLAIN query plan
- GET /studio/models/inspect/{model_name} - Inspect a single model
- GET /studio/models/inspect/all - Inspect all registered models

v0.5.25 Additions:
- GET /studio/ai/hub/providers - Unified provider status & detection
- POST /studio/ai/hub/providers/save - Save provider configuration
- POST /studio/ai/hub/providers/ping - Test provider connectivity
- POST /studio/ai/hub/agent/run - Run AI agent with prompt

v0.5.26 Additions:
- GET /studio/gaps - Run gap analysis and return issues explorer report
- POST /studio/gaps/run - Trigger a fresh gap analysis run

v0.5.29 Additions:
- GET /studio/ai/flows/actions - List available AI flow actions
- POST /studio/ai/flows/model - AI flow for model actions
- POST /studio/ai/flows/route - AI flow for route actions
- POST /studio/ai/flows/query - AI flow for query actions
- POST /studio/ai/flows/migration - AI flow for migration actions
- POST /studio/ai/flows/diagnostic - AI flow for diagnostic actions

v0.5.33 Additions:
- POST /studio/ai/debug - AI Debugger root-cause analysis

v0.5.40 Additions:
- GET /studio/ai/daily-briefing - Daily system health briefing
- POST /studio/ai/investigate/{id}/next - Execute next investigation step
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

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
    # v0.5.12: AI Profile Health models
    StudioAiProfileHealth,
    # v0.5.13: AI Hints models
    StudioAiHintSet,
    # v0.5.19: Agent Mode models
    StudioAgentContext,
    StudioAgentPromptRequest,
    StudioAgentPromptResponse,
    # v0.5.20: Agent Playbooks models
    AgentPlaybookSet,
    StudioAgentPlaybookPromptRequest,
    # v0.5.21: Query & Model Inspector models
    StudioQueryPlanRequest,
    StudioQueryPlanResult,
    StudioModelInspectorSummary,
    StudioModelInspectorAll,
    # v0.5.22: Semantic Search models
    StudioSearchRequest,
    StudioSearchResultSet,
    StudioSearchIndexInfo,
    # v0.5.23: Agentic Workflows models
    AgentWorkflowRequest,
    AgentWorkflowResponse,
    AgentWorkflow,
    # v0.5.25: AI Hub models
    StudioAiProvidersSummary,
    StudioAiProviderSaveRequest,
    StudioAiProviderSaveResponse,
    StudioAiProviderPingRequest,
    StudioAiProviderPingResponse,
    StudioAiAgentRunRequest,
    StudioAiAgentRunResponse,
    # v0.5.26: Gap Analysis models
    StudioGapAnalysisReport,
    StudioGapAnalysisRunResponse,
    # v0.5.29: AI Flows models
    StudioAiFlowModelRequest,
    StudioAiFlowRouteRequest,
    StudioAiFlowQueryRequest,
    StudioAiFlowMigrationRequest,
    StudioAiFlowDiagnosticRequest,
    StudioAiFlowResponse,
    StudioAiFlowActionsResponse,
    # v0.5.33: AI Debugger models
    StudioDebugRequest,
    StudioDebugResponse,
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
    # v0.5.12: AI Profile Health utils
    build_ai_profile_health,
    # v0.5.13: AI Hints utils
    build_ai_hints,
    # v0.5.19: Agent Mode utils
    build_agent_context,
    build_agent_prompt,
    # v0.5.20: Agent Playbooks utils
    build_agent_prompt_from_playbook,
    # v0.5.21: Query & Model Inspector utils
    build_query_plan,
    build_model_inspector,
    build_all_models_inspector,
    # v0.5.22: Semantic Search utils
    build_search_index_info,
    build_search_results,
    # v0.5.23: Agentic Workflows utils
    build_agent_workflow,
    summarize_agent_workflow,
    workflow_stats,
    # v0.5.25: AI Hub utils
    build_ai_hub_providers,
    build_ai_hub_provider_save,
    build_ai_hub_provider_ping,
    build_ai_hub_agent_run,
    # v0.5.26: Gap Analysis utils
    run_and_build_gap_analysis,
)
from aksara.ai.playbooks import get_builtin_playbooks, get_playbook_by_key
from aksara.diagnostics import DiagnosticReport, run_all_checks

# v0.5.3: Static files directory
STATIC_DIR = Path(__file__).parent / "static"


# =============================================================================
# v0.5.1: Origin Security
# =============================================================================

async def _check_studio_origin(request: Request) -> None:
    """Reject requests whose Origin header is not in studio_allowed_origins.

    Rules:
    - No Origin header → allow (same-origin request or CLI)
    - ``studio_allowed_origins = []`` → allow all origins
    - ``"*"`` in allowed list → allow all origins
    - Otherwise the origin must match exactly

    Raises HTTP 403 when the origin is disallowed.
    """
    from aksara.conf import settings

    origin = request.headers.get("Origin")
    if not origin:
        return  # no Origin header — same-origin or CLI, allow through

    allowed_origins: list = getattr(settings, "studio_allowed_origins", [])
    if not allowed_origins:
        return  # empty list means unrestricted
    if "*" in allowed_origins:
        return  # wildcard — allow all
    if origin in allowed_origins:
        return  # exact match — allow

    raise HTTPException(
        status_code=403,
        detail=f"Origin {origin!r} is not allowed",
    )


async def verify_studio_auth(request: Request) -> None:
    """
    Verify Studio authentication.

    Checks ``settings.studio_require_auth``.  When True, accepts either:
    - ``Authorization: Bearer <token>`` matching ``settings.studio_auth_token``
    - A valid staff session cookie

    Raises HTTP 401 when authentication is required but not provided.
    """
    from aksara.conf import settings

    if not getattr(settings, "studio_require_auth", False):
        return

    # In debug mode with no auth token configured, allow through automatically.
    # This prevents a misconfiguration from locking developers out of Studio
    # in local development environments.
    debug = getattr(settings, "debug", False)
    expected_token = getattr(settings, "studio_auth_token", None)
    if debug and not expected_token:
        return

    # --- Bearer token check ---
    auth_header = request.headers.get("Authorization", "")
    expected_token = getattr(settings, "studio_auth_token", None)
    if auth_header.startswith("Bearer ") and expected_token:
        import hmac
        provided = auth_header[7:]
        if hmac.compare_digest(provided, expected_token):
            return

    # --- Session cookie check ---
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            from aksara.contrib.auth import get_user_from_session_token
            user = await get_user_from_session_token(session_token)
            if user and getattr(user, "is_staff", False):
                return
        except Exception:
            pass

    raise HTTPException(
        status_code=401,
        detail="Studio requires authentication",
    )

router = APIRouter(
    tags=["Studio"],
    dependencies=[Depends(_check_studio_origin), Depends(verify_studio_auth)],
)


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


@router.get("/studio/ai/health", response_model=StudioAiProfileHealth)
async def studio_ai_health(request: Request) -> StudioAiProfileHealth:
    """
    Get AI profile configuration health status.
    
    v0.5.12: Validates AI profile configuration and returns any issues found.
    
    This endpoint runs validation checks on the current AI profile 
    configuration, detecting:
    - Duplicate provider or model names
    - Invalid provider or model kinds
    - Missing or invalid default provider/model references
    - Empty profile sets
    
    Returns:
        StudioAiProfileHealth with:
        - is_valid: True if no errors found
        - error_count, warning_count, info_count: Issue counts by severity
        - issues: List of validation issues
        - provider_count, model_count: Configuration summary
        - default_provider: Current default provider name
    
    Example response:
        {
            "is_valid": true,
            "error_count": 0,
            "warning_count": 1,
            "info_count": 0,
            "issues": [
                {
                    "id": "missing_default_provider:none",
                    "kind": "missing_default_provider",
                    "severity": "warning",
                    "message": "No default provider is set",
                    "field": "default_provider"
                }
            ],
            "provider_count": 3,
            "model_count": 6,
            "default_provider": null
        }
    """
    return build_ai_profile_health(request.app)


@router.get("/studio/ai/hints", response_model=StudioAiHintSet)
async def studio_ai_hints(request: Request) -> StudioAiHintSet:
    """
    Get per-route AI hints for LLM guidance.
    
    v0.5.13: Returns route-level AI hints declared via @ai_route_hint decorator.
    
    These hints help LLMs understand:
    - What each route does (title, description)
    - How risky/sensitive it is (risk_level)
    - Whether it reads or writes data (usage_kind)
    - Example prompts and inputs/outputs for guidance
    - Recommended AI model/provider for the operation
    
    Returns:
        StudioAiHintSet with:
        - routes: List of route hints with metadata
        - total_count: Total number of hinted routes
        - Usage stats: read_only_count, write_count, admin_count
        - Risk stats: low_risk_count, medium_risk_count, high_risk_count
    
    Example response:
        {
            "routes": [
                {
                    "view_name": "PostViewSet",
                    "route_name": "post-publish",
                    "path": "/api/posts/{id}/publish/",
                    "methods": ["POST"],
                    "title": "Publish a blog post",
                    "description": "Marks the given post as published.",
                    "usage_kind": "write",
                    "risk_level": "medium",
                    "example_prompt": "User says: 'Publish my draft about async APIs'",
                    "example_input": {"id": 42},
                    "example_output": {"id": 42, "is_published": true}
                }
            ],
            "total_count": 1,
            "read_only_count": 0,
            "write_count": 1,
            "admin_count": 0,
            "low_risk_count": 0,
            "medium_risk_count": 1,
            "high_risk_count": 0
        }
    """
    return build_ai_hints(request.app)


# =============================================================================
# v0.5.17: Diagnostics Endpoint
# =============================================================================


@router.get("/studio/diagnostics", response_model=DiagnosticReport)
async def studio_diagnostics(request: Request) -> DiagnosticReport:
    """
    Full self-diagnostics report.

    v0.5.17: Runs all diagnostic checks and returns a comprehensive report
    covering database connectivity, migrations, AI profiles, settings,
    security, file-system, and cache.

    Returns:
        DiagnosticReport with:
        - issues: List of DiagnosticIssue (sorted by severity)
        - stats: {errors, warnings, info} counts
        - timestamp: UTC timestamp of the check
        - duration_ms: How long the check took
        - system: {aksara_version, python_version, os, arch}
    """
    return await run_all_checks()


# =============================================================================
# v0.5.19: Agent Mode Endpoints
# =============================================================================


@router.get("/studio/agent/context", response_model=StudioAgentContext)
async def studio_agent_context(request: Request) -> StudioAgentContext:
    """
    Gather full project context for an LLM agent.

    v0.5.19: Collects 9 sections (project_info, models, routes,
    migrations, diagnostics, ai_profiles, ai_hints, db_queries,
    schema_checksum) into a single response suitable for agent
    consumption.

    Returns:
        StudioAgentContext with all available sections.
    """
    return await build_agent_context(request.app)


@router.post("/studio/agent/prompt", response_model=StudioAgentPromptResponse)
async def studio_agent_prompt(
    request: Request,
    body: StudioAgentPromptRequest,
) -> StudioAgentPromptResponse:
    """
    Generate a system prompt for an LLM agent.

    v0.5.19: Accepts a goal, optional section filter, and optional
    custom system prompt prefix.  Returns the assembled system prompt,
    recommended temperature/model, and a rough token estimate.

    Args:
        body: StudioAgentPromptRequest with goal and section selection.

    Returns:
        StudioAgentPromptResponse with prompt and recommendations.
    """
    context = await build_agent_context(request.app)
    return build_agent_prompt(body, context)


# =============================================================================
# v0.5.20: Agent Playbooks Endpoints
# =============================================================================


@router.get("/studio/agent/playbooks", response_model=AgentPlaybookSet)
async def studio_agent_playbooks(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    usage_kind: Optional[str] = Query(None, description="Filter by usage kind"),
) -> AgentPlaybookSet:
    """
    List available agent playbooks.

    v0.5.20: Returns built-in playbooks with optional filtering by
    category, risk_level, and/or usage_kind.  Includes aggregate counts
    by_category, by_risk_level, and by_usage_kind.

    Query Parameters:
        category: Filter by category (e.g. "schema", "api", "migrations").
        risk_level: Filter by risk level ("low", "medium", "high").
        usage_kind: Filter by usage kind ("read_only", "write", "admin").

    Returns:
        AgentPlaybookSet with matching playbooks.
    """
    return get_builtin_playbooks(
        category=category,
        risk_level=risk_level,
        usage_kind=usage_kind,
    )


@router.post("/studio/agent/playbooks/prompt", response_model=StudioAgentPromptResponse)
async def studio_agent_playbook_prompt(
    request: Request,
    body: StudioAgentPlaybookPromptRequest,
) -> StudioAgentPromptResponse:
    """
    Generate a system prompt using a playbook recipe.

    v0.5.20: Looks up the playbook by key, gathers project context,
    and builds a playbook-aware prompt with step listing.

    Args:
        body: StudioAgentPlaybookPromptRequest with playbook_key and
              optional goal/sections overrides.

    Returns:
        StudioAgentPromptResponse with assembled prompt.

    Raises:
        HTTPException 404 if playbook_key not found.
    """
    playbook = get_playbook_by_key(body.playbook_key)
    if playbook is None:
        raise HTTPException(
            status_code=404,
            detail=f"Playbook not found: {body.playbook_key}",
        )
    context = await build_agent_context(request.app)
    return build_agent_prompt_from_playbook(
        playbook=playbook,
        user_goal=body.user_goal,
        selected_sections=body.selected_sections,
        custom_system_prompt=body.custom_system_prompt,
        context=context,
    )


# =============================================================================
# v0.5.21: Query & Model Inspector Endpoints
# =============================================================================


@router.post("/studio/db/plan", response_model=StudioQueryPlanResult)
async def studio_db_plan(
    request: Request,
    body: StudioQueryPlanRequest,
) -> StudioQueryPlanResult:
    """
    Generate an EXPLAIN plan for a SQL query.

    v0.5.21: Returns the query plan with estimated cost and warnings.
    Uses a synthetic plan when no live database connection is available.

    Args:
        body: StudioQueryPlanRequest with sql and optional analyze flag.

    Returns:
        StudioQueryPlanResult with plan lines and estimated cost.
    """
    return build_query_plan(body.sql, analyze=body.analyze)


@router.get(
    "/studio/models/inspect/all",
    response_model=StudioModelInspectorAll,
)
async def studio_models_inspect_all(
    request: Request,
) -> StudioModelInspectorAll:
    """
    Inspect all registered models.

    v0.5.21: Returns a list of inspection summaries for every registered
    model, plus aggregate counts.

    Returns:
        StudioModelInspectorAll with all model inspections.
    """
    return build_all_models_inspector()


@router.get(
    "/studio/models/inspect/{model_name}",
    response_model=StudioModelInspectorSummary,
)
async def studio_model_inspect(
    request: Request,
    model_name: str,
) -> StudioModelInspectorSummary:
    """
    Inspect a single model by name.

    v0.5.21: Returns fields, relationships, constraints, SQL, and
    auto-generated comments for the specified model.

    Args:
        model_name: Model class name (e.g. "User", "Post").

    Returns:
        StudioModelInspectorSummary with full inspection data.

    Raises:
        HTTPException 404 if the model is not found in the registry.
    """
    result = build_model_inspector(model_name)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model not found: {model_name}",
        )
    return result


# =============================================================================
# v0.5.22: Semantic Search & AI Index Endpoints
# =============================================================================


@router.get("/studio/search/index", response_model=StudioSearchIndexInfo)
async def studio_search_index(request: Request) -> StudioSearchIndexInfo:
    """
    Get search index info and statistics.

    v0.5.22: Returns document counts, available kinds, vocabulary size.
    """
    return build_search_index_info(request.app)


@router.post("/studio/search/query", response_model=StudioSearchResultSet)
async def studio_search_query(
    request: Request,
    body: StudioSearchRequest,
) -> StudioSearchResultSet:
    """
    Run a search query against the project index.

    v0.5.22: Supports keyword, semantic, and hybrid search modes.
    """
    return build_search_results(
        query=body.query,
        app=request.app,
        top_k=body.top_k,
        kind=body.kind,
        kinds=body.kinds,
        tags=body.tags,
        min_score=body.min_score,
        mode=body.mode,
    )


@router.post("/studio/search/rebuild")
async def studio_search_rebuild(request: Request) -> Dict[str, Any]:
    """
    Force rebuild the search index.

    v0.5.22: Clears cache and rebuilds from scratch.
    """
    from aksara.studio.utils import _get_search_index
    index = _get_search_index(request.app, force_rebuild=True)
    return {
        "status": "rebuilt",
        "total_documents": index.size,
        "by_kind": index.count_by_kind(),
    }


# =============================================================================
# v0.5.23: Agentic Workflows — Plans, Not Pushes
# =============================================================================


@router.post("/studio/agent/workflow", response_model=AgentWorkflowResponse)
async def studio_agent_workflow(
    request: Request,
    body: AgentWorkflowRequest,
) -> AgentWorkflowResponse:
    """
    Generate a structured agent workflow.

    v0.5.23: Combines diagnostics, search, inspectors, and playbooks
    into an ordered sequence of actionable steps.
    """
    workflow = build_agent_workflow(
        goal=body.goal,
        playbook=body.playbook,
        include_diagnostics=body.include_diagnostics,
        include_search=body.include_search,
        search_query=body.search_query,
        search_limit=body.limit_search_results,
        diagnostics_limit=body.limit_diagnostics,
    )
    return AgentWorkflowResponse(
        workflow=workflow,
        summary=summarize_agent_workflow(workflow),
        stats=workflow_stats(workflow),
    )


@router.get("/studio/agent/workflow/sample", response_model=AgentWorkflow)
async def studio_agent_workflow_sample(
    request: Request,
) -> AgentWorkflow:
    """
    Return a sample workflow for demo and testing.

    v0.5.23: Uses a canned goal to showcase the workflow structure.
    """
    return build_agent_workflow(
        goal="Fix slow queries on /api/posts/",
        include_diagnostics=False,
        include_search=True,
        search_limit=5,
    )


# =============================================================================
# v0.5.25: AI Hub & Unified Provider System Endpoints
# =============================================================================


@router.get("/studio/ai/hub/providers", response_model=StudioAiProvidersSummary)
async def studio_ai_hub_providers(request: Request) -> StudioAiProvidersSummary:
    """
    Get unified AI provider status and detection results.

    v0.5.25: Detects all configured providers from environment variables,
    pings each to check connectivity, and returns the active provider.

    Returns:
        StudioAiProvidersSummary with provider statuses and active provider.
    """
    return build_ai_hub_providers()


@router.post("/studio/ai/hub/providers/save", response_model=StudioAiProviderSaveResponse)
async def studio_ai_hub_providers_save(
    request: Request,
    body: StudioAiProviderSaveRequest,
) -> StudioAiProviderSaveResponse:
    """
    Save AI provider configuration to .env or provider.json.

    v0.5.25: Writes provider config to the project root.

    Args:
        body: Provider config with save_to target.

    Returns:
        StudioAiProviderSaveResponse with save status.
    """
    return build_ai_hub_provider_save(
        provider=body.provider,
        api_key=body.api_key,
        base_url=body.base_url,
        model=body.model,
        extra=body.extra,
        save_to=body.save_to,
    )


@router.post("/studio/ai/hub/providers/ping", response_model=StudioAiProviderPingResponse)
async def studio_ai_hub_providers_ping(
    request: Request,
    body: StudioAiProviderPingRequest,
) -> StudioAiProviderPingResponse:
    """
    Test connectivity to an AI provider.

    v0.5.25: Pings the specified provider (or active) and returns latency.

    Args:
        body: Optional provider key to ping.

    Returns:
        StudioAiProviderPingResponse with reachability and latency.
    """
    return build_ai_hub_provider_ping(provider_key=body.provider)


@router.post("/studio/ai/hub/agent/run", response_model=StudioAiAgentRunResponse)
async def studio_ai_hub_agent_run(
    request: Request,
    body: StudioAiAgentRunRequest,
) -> StudioAiAgentRunResponse:
    """
    Run the AI agent with a prompt.

    v0.5.25: Uses the unified provider to generate a response.
    Optionally includes project context in the system prompt.

    Args:
        body: Prompt, provider/model overrides, context settings.

    Returns:
        StudioAiAgentRunResponse with generated output or error.
    """
    return build_ai_hub_agent_run(
        prompt=body.prompt,
        app=request.app,
        provider_key=body.provider,
        model_override=body.model,
        include_context=body.include_context,
        context_sections=body.context_sections,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )


# =============================================================================
# v0.5.26: Gap Analysis Endpoints
# =============================================================================


@router.get("/studio/gaps", response_model=StudioGapAnalysisReport)
async def studio_gaps(
    request: Request,
    categories: Optional[str] = Query(
        default=None,
        description="Comma-separated list of categories to check (default: all)",
    ),
    _dep: None = Depends(verify_studio_auth),
) -> StudioGapAnalysisReport:
    """
    Run the gap analysis engine and return the report.

    v0.5.26: Returns a full gap analysis report across up to eight
    check categories.  Pass ``?categories=db,migrations`` to limit
    the scan to specific categories.

    Returns:
        StudioGapAnalysisReport with all discovered issues and stats.
    """
    cats = None
    if categories:
        cats = [c.strip() for c in categories.split(",") if c.strip()]
    return await run_and_build_gap_analysis(categories=cats)


@router.post("/studio/gaps/run", response_model=StudioGapAnalysisRunResponse)
async def studio_gaps_run(
    request: Request,
    _dep: None = Depends(verify_studio_auth),
) -> StudioGapAnalysisRunResponse:
    """
    Trigger a fresh gap analysis run and return the full report.

    v0.5.26: Runs all eight check categories and returns the
    analysis result immediately (synchronous).

    Returns:
        StudioGapAnalysisRunResponse with the completed analysis.
    """
    from datetime import datetime, timezone

    triggered_at = datetime.now(timezone.utc).isoformat()
    try:
        report = await run_and_build_gap_analysis()
        return StudioGapAnalysisRunResponse(
            triggered_at=triggered_at,
            status="ok",
            report=report,
        )
    except Exception as exc:
        return StudioGapAnalysisRunResponse(
            triggered_at=triggered_at,
            status="error",
            error=str(exc),
        )


# =============================================================================
# v0.5.28: AI Hub 2.0 Endpoints
# =============================================================================


@router.get("/studio/ai-hub/status")
async def studio_aihub_status(request: Request):
    """
    Overall AI Hub status — readiness, onboarding progress, warnings.

    v0.5.28: Central status endpoint for the AI Hub 2.0 panel.
    """
    from aksara.studio.utils import build_aihub_status
    return build_aihub_status()


@router.get("/studio/ai-hub/providers")
async def studio_aihub_providers(request: Request):
    """
    List all detected providers with configuration and reachability status.

    v0.5.28: Full provider inventory for the AI Hub panel.
    """
    from aksara.studio.utils import build_aihub_providers
    return build_aihub_providers()


@router.get("/studio/ai-hub/models")
async def studio_aihub_models(request: Request):
    """
    Default model assignments and available models per provider.

    v0.5.28: Model listing for the AI Hub Models tab.
    """
    from aksara.studio.utils import build_aihub_models
    return build_aihub_models()


@router.post("/studio/ai-hub/configure")
async def studio_aihub_configure(request: Request):
    """
    Configure a provider (non-secret fields like base_url, model, enabled).

    v0.5.28: Accepts provider kind + config fields.
    """
    from aksara.studio.utils import build_aihub_configure

    body = await request.json()
    return build_aihub_configure(
        provider=body.get("provider", ""),
        base_url=body.get("base_url"),
        model=body.get("model"),
        enabled=body.get("enabled", True),
    )


@router.post("/studio/ai-hub/configure/secret")
async def studio_aihub_configure_secret(request: Request):
    """
    Handle API key configuration securely (no logging).

    v0.5.28: Saves API key to .env without exposing it in logs.
    """
    from aksara.studio.utils import build_aihub_configure_secret

    body = await request.json()
    return build_aihub_configure_secret(
        provider=body.get("provider", ""),
        api_key=body.get("api_key", ""),
    )


@router.post("/studio/ai-hub/defaults")
async def studio_aihub_defaults(request: Request):
    """
    Update default model assignments (chat, code, embeddings).

    v0.5.28: Set which model/provider to use for each AI mode.
    """
    from aksara.studio.utils import build_aihub_defaults

    body = await request.json()
    return build_aihub_defaults(
        chat_model=body.get("chat_model"),
        chat_provider=body.get("chat_provider"),
        code_model=body.get("code_model"),
        code_provider=body.get("code_provider"),
        embeddings_model=body.get("embeddings_model"),
        embeddings_provider=body.get("embeddings_provider"),
    )


@router.post("/studio/ai-hub/test")
async def studio_aihub_test(request: Request):
    """
    Test a single provider's connectivity (ping).

    v0.5.28: Returns reachability, latency, and supported modes.
    """
    from aksara.studio.utils import build_aihub_test

    body = await request.json()
    return build_aihub_test(provider=body.get("provider", ""))


@router.get("/studio/ai-hub/routes")
async def studio_aihub_routes(request: Request):
    """
    AI feature routing table — which provider/model serves each feature.

    v0.5.28: Returns per-feature route mapping (agents, playbooks,
    search_embeddings, diagnostics) with status and warnings.
    """
    from aksara.studio.utils import build_aihub_routes
    return build_aihub_routes()


# =============================================================================
# v0.5.29: Studio AI Flows Endpoints
# =============================================================================


@router.get("/studio/ai/flows/actions")
async def studio_ai_flow_actions(request: Request):
    """
    List all available AI flow actions with metadata.

    v0.5.29: Returns action keys, titles, risk levels, descriptions.
    """
    from aksara.studio.ai_flows import list_flow_actions
    from aksara.studio.models import StudioAiFlowActionDescriptor, StudioAiFlowActionsResponse

    raw = list_flow_actions()
    descriptors = [StudioAiFlowActionDescriptor(**a) for a in raw]
    return StudioAiFlowActionsResponse(actions=descriptors, total=len(descriptors))


@router.post("/studio/ai/flows/model")
async def studio_ai_flow_model(request: Request):
    """
    AI flow for model actions: explain, suggest constraints, refactor.

    v0.5.29: Returns a prompt pack (system + user prompt) for the chosen action.
    """
    from aksara.studio.ai_flows import build_model_flow

    body = await request.json()
    return build_model_flow(
        model_name=body.get("model_name", ""),
        action_key=body.get("action_key", ""),
        hub_overrides=body.get("hub_overrides"),
    )


@router.post("/studio/ai/flows/route")
async def studio_ai_flow_route(request: Request):
    """
    AI flow for route actions: review, harden, generate examples.

    v0.5.29: Returns a prompt pack for the chosen action.
    """
    from aksara.studio.ai_flows import build_route_flow

    body = await request.json()
    path = body.get("path", "")
    method = body.get("method", "GET")
    # Support route_id as "METHOD:/path"
    route_id = body.get("route_id")
    if route_id and ":" in route_id and not path:
        method, path = route_id.split(":", 1)
    return build_route_flow(
        path=path,
        method=method,
        action_key=body.get("action_key", ""),
        hub_overrides=body.get("hub_overrides"),
    )


@router.post("/studio/ai/flows/query")
async def studio_ai_flow_query(request: Request):
    """
    AI flow for query actions: explain plan, suggest indexes, rewrite.

    v0.5.29: Returns a prompt pack for SQL query analysis.
    """
    from aksara.studio.ai_flows import build_query_flow

    body = await request.json()
    return build_query_flow(
        sql=body.get("sql", ""),
        action_key=body.get("action_key", ""),
        include_explain=body.get("include_explain", True),
        hub_overrides=body.get("hub_overrides"),
    )


@router.post("/studio/ai/flows/migration")
async def studio_ai_flow_migration(request: Request):
    """
    AI flow for migration actions: explain impact, safe rollout plan.

    v0.5.29: Returns a prompt pack for migration analysis.
    """
    from aksara.studio.ai_flows import build_migration_flow

    body = await request.json()
    return build_migration_flow(
        action_key=body.get("action_key", ""),
        migration_id=body.get("migration_id"),
        app=body.get("app"),
        name=body.get("name"),
        hub_overrides=body.get("hub_overrides"),
    )


@router.post("/studio/ai/flows/diagnostic")
async def studio_ai_flow_diagnostic(request: Request):
    """
    AI flow for diagnostic actions: explain & prioritize issues.

    v0.5.29: Returns a prompt pack for diagnostic triage.
    """
    from aksara.studio.ai_flows import build_diagnostic_flow

    body = await request.json()
    return build_diagnostic_flow(
        action_key=body.get("action_key", ""),
        issue_id=body.get("issue_id"),
        issue_payload=body.get("issue_payload"),
        hub_overrides=body.get("hub_overrides"),
    )


@router.post("/studio/ai/flows/run")
async def studio_ai_flow_run(request: Request):
    """
    Execute an AI flow through a connector (v0.5.30).

    Builds the prompt pack, sends it to the configured AI provider,
    and returns both the prompt pack and the execution result.

    Body:
        flow_type: model | route | query | migration | diagnostic
        action_key: e.g. explain_model
        context: { model_name?, path?, method?, sql?, app?, name?, issue_id? }
        provider_override: optional provider override
        model_override: optional model override
    """
    from aksara.studio.ai_flows import execute_flow

    body = await request.json()
    flow_type = body.get("flow_type", "")
    action_key = body.get("action_key", "")
    context = body.get("context", {})
    provider_override = body.get("provider_override")
    model_override = body.get("model_override")

    result = await execute_flow(
        flow_type=flow_type,
        action_key=action_key,
        context=context,
        provider_override=provider_override,
        model_override=model_override,
    )
    return result


# =============================================================================
# v0.5.31: Interactive AI Console
# =============================================================================


@router.post("/studio/ai/console")
async def studio_ai_console(request: Request):
    """
    Interactive AI Console endpoint (v0.5.31).

    Accepts a natural-language message, detects intent, routes to the
    matching AI Flow, executes via runtime, and returns a structured response.

    Body:
        message: str — e.g. "explain the User model"
        provider_override: optional provider override
        model_override: optional model override
    """
    try:
        from aksara.ai.console_engine import run_console_query

        body = await request.json()
        message = body.get("message", "")
        provider_override = body.get("provider_override")
        model_override = body.get("model_override")

        result = await run_console_query(
            message,
            provider_override=provider_override,
            model_override=model_override,
        )
        return result
    except Exception as exc:
        import traceback

        from starlette.responses import JSONResponse

        return JSONResponse(
            {
                "ok": False,
                "error": str(exc),
                "error_code": "SERVER_ERROR",
                "detail": traceback.format_exc(),
            },
            status_code=500,
        )


@router.get("/studio/ai/console/suggest")
async def studio_ai_console_suggest(request: Request):
    """
    Command suggestion endpoint for the AI Console (v0.5.31).

    Query params:
        q: prefix string for autocomplete
    """
    from aksara.ai.intent_router import suggest_commands, list_intents

    q = request.query_params.get("q", "")
    return {
        "suggestions": suggest_commands(q),
        "intents": list_intents(),
    }


# =============================================================================
# v0.5.32: Project Context Graph Endpoints
# =============================================================================


@router.get("/studio/ai/project-graph")
async def studio_ai_project_graph(request: Request):
    """
    Return the full Project Context Graph (v0.5.32).

    Query params:
        summary: if "true", return compact summary only
        rebuild: if "true", bypass cache and rebuild
    """
    from aksara.ai.project_graph import build_project_graph

    rebuild = request.query_params.get("rebuild", "").lower() == "true"
    summary = request.query_params.get("summary", "").lower() == "true"

    graph = build_project_graph(rebuild=rebuild, app=request.app)
    if summary:
        return graph.to_summary_dict()
    return graph.to_dict()


@router.get("/studio/ai/project-graph/events")
async def studio_ai_project_graph_events(request: Request):
    """
    Return recent graph events (v0.5.32).

    Query params:
        limit: max events to return (default 100)
    """
    from aksara.ai.graph_events import get_recent_graph_events

    try:
        limit = int(request.query_params.get("limit", "100"))
    except (ValueError, TypeError):
        limit = 100

    events = get_recent_graph_events(limit=limit)
    return {"events": [e.to_dict() for e in events], "count": len(events)}


@router.get("/studio/ai/project-graph/summary")
async def studio_ai_project_graph_summary(request: Request):
    """
    Compact graph summary optimised for UI cards (v0.5.32).
    """
    from aksara.ai.project_graph import build_project_graph

    graph = build_project_graph(app=request.app)
    return graph.to_summary_dict()


# =============================================================================
# v0.5.33: AI Debugger Endpoint
# =============================================================================


@router.post("/studio/ai/debug")
async def studio_ai_debug(request: Request):
    """
    AI Debugger endpoint (v0.5.33).

    Runs the automated root-cause analysis pipeline: loads the Project
    Context Graph, builds an issue pool from diagnostics + gaps + events,
    clusters related issues, detects root causes, ranks by confidence,
    and suggests safe fix plans.

    Body (optional):
        query: str — e.g. "why is /api/users failing?"
    """
    try:
        from aksara.ai.debugger import run_debugger

        body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
        query = body.get("query") if isinstance(body, dict) else None

        report = run_debugger(query=query, app=request.app)
        return report.to_dict()
    except Exception as exc:
        import traceback

        from starlette.responses import JSONResponse

        return JSONResponse(
            {"error": str(exc), "detail": traceback.format_exc()},
            status_code=500,
        )


# =============================================================================
# v0.5.34: AI Architecture Review Endpoint
# =============================================================================


@router.post("/studio/ai/architecture-review")
async def studio_ai_architecture_review(request: Request):
    """
    AI Architecture Review endpoint (v0.5.34).

    Runs the automated architectural analysis pipeline: loads the Project
    Context Graph, computes metrics, detects coupling / schema / API /
    migration / performance anti-patterns, scores the architecture, and
    suggests improvements.
    """
    try:
        from aksara.ai.architecture_review import run_architecture_review

        report = run_architecture_review(app=request.app)
        return report.to_dict()
    except Exception as exc:
        import traceback

        from starlette.responses import JSONResponse

        return JSONResponse(
            {"error": str(exc), "detail": traceback.format_exc()},
            status_code=500,
        )


# =============================================================================
# v0.5.35: AI Performance Analyzer Endpoint
# =============================================================================


@router.post("/studio/ai/performance-analysis")
async def studio_ai_performance_analysis(request: Request):
    """
    AI Performance Analyzer endpoint (v0.5.35).

    Runs the automated performance analysis pipeline: loads the Project
    Context Graph, collects query data, detects slow queries / N+1 /
    missing indexes / query explosions / heavy joins / route hotspots,
    scores the performance, and recommends improvements.
    """
    try:
        from aksara.ai.performance_analyzer import run_performance_analysis

        report = run_performance_analysis(app=request.app)
        return report.to_dict()
    except Exception as exc:
        import traceback

        from starlette.responses import JSONResponse

        return JSONResponse(
            {"error": str(exc), "detail": traceback.format_exc()},
            status_code=500,
        )


# =============================================================================
# v0.5.38: AI Home & Inspector Endpoints
# =============================================================================


@router.get("/studio/ai/home")
async def studio_ai_home(request: Request):
    """
    AI Home endpoint (v0.5.38).

    Returns the data needed for the unified AI Home screen:
    - AI status (ready / partial / not_configured)
    - Provider metadata
    - System snapshot from the Project Context Graph
    - Recent observations from diagnostics / analyzers
    - Suggested prompts
    """
    data: dict = {
        "status": "not_configured",
        "provider": None,
        "model": None,
        "embeddings_model": None,
        "snapshot": {
            "models": 0,
            "routes": 0,
            "queries": 0,
            "migrations": 0,
            "diagnostics": 0,
        },
        "scores": {
            "architecture": None,
            "performance": None,
        },
        "observations": [],
        "suggested_prompts": [
            "Explain my architecture",
            "Investigate my project",
            "Why is /api/users slow?",
            "Review database schema",
        ],
    }

    # Provider status
    try:
        from aksara.ai.hub_settings import load_aihub_settings

        hub = load_aihub_settings()
        configured = hub.configured_providers()
        if configured:
            active = configured[0]
            data["provider"] = active.kind
            data["model"] = getattr(hub.defaults, "chat_model", None)
            data["embeddings_model"] = getattr(hub.defaults, "embeddings_model", None)
            data["status"] = "ready" if len(configured) >= 1 else "partial"
        else:
            data["status"] = "not_configured"
    except Exception:
        data["status"] = "not_configured"

    # System snapshot from project graph
    try:
        from aksara.ai.project_graph import build_project_graph

        graph = build_project_graph(app=request.app)
        m = graph.metadata
        data["snapshot"] = {
            "models": m.model_count,
            "routes": m.route_count,
            "queries": m.query_count,
            "migrations": m.migration_count,
            "diagnostics": m.diagnostic_count,
        }

        # Recent observations from diagnostics
        observations = []
        for d in graph.diagnostics[:3]:
            observations.append(d.message)
        data["observations"] = observations
    except Exception:
        pass

    # Architecture / performance scores (lightweight — only if cached)
    try:
        from aksara.ai.architecture_review import run_architecture_review

        arch = run_architecture_review(app=request.app)
        data["scores"]["architecture"] = {
            "score": arch.score,
            "grade": arch.grade,
        }
    except Exception:
        pass

    try:
        from aksara.ai.performance_analyzer import run_performance_analysis

        perf = run_performance_analysis(app=request.app)
        data["scores"]["performance"] = {
            "score": perf.score,
            "grade": perf.grade,
        }
    except Exception:
        pass

    return data


@router.get("/studio/ai/inspector")
async def studio_ai_inspector(request: Request):
    """
    AI Inspector overview endpoint (v0.5.38).

    Returns a summary for the Inspector overview tab:
    architecture score, performance score, diagnostics count.
    """
    data: dict = {
        "architecture": {"score": None, "grade": None},
        "performance": {"score": None, "grade": None},
        "diagnostics_count": 0,
        "top_issues": [],
    }

    try:
        from aksara.ai.project_graph import build_project_graph

        graph = build_project_graph(app=request.app)
        data["diagnostics_count"] = graph.metadata.diagnostic_count
        data["top_issues"] = [
            {"severity": d.severity, "code": d.code, "message": d.message}
            for d in graph.diagnostics[:5]
        ]
    except Exception:
        pass

    try:
        from aksara.ai.architecture_review import run_architecture_review

        arch = run_architecture_review(app=request.app)
        data["architecture"] = {"score": arch.score, "grade": arch.grade}
    except Exception:
        pass

    try:
        from aksara.ai.performance_analyzer import run_performance_analysis

        perf = run_performance_analysis(app=request.app)
        data["performance"] = {"score": perf.score, "grade": perf.grade}
    except Exception:
        pass

    return data


# =============================================================================
# v0.5.39: AI Investigation Engine Endpoints
# =============================================================================


@router.post("/studio/ai/investigate")
async def studio_ai_investigate_start(request: Request):
    """Start a new AI investigation session.

    Body: ``{"goal": "Why is the app slow?"}``

    Returns the session with its plan (not yet executed).
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"error": "Invalid JSON body"}, status_code=400
        )

    goal = body.get("goal", "").strip()
    if not goal:
        return JSONResponse(
            {"error": "Missing 'goal' in request body"}, status_code=400
        )

    try:
        from aksara.ai.session_store import create_session
        from aksara.ai.plan_builder import build_plan

        session = create_session(goal)
        session.status = "planning"
        plan = build_plan(goal)
        session.plan = plan

        from aksara.ai.session_store import update_session

        update_session(session)
        return session.to_dict()
    except Exception as exc:
        return JSONResponse(
            {"error": f"Failed to create investigation: {exc}"},
            status_code=500,
        )


@router.post("/studio/ai/investigate/{session_id}/run")
async def studio_ai_investigate_run(request: Request, session_id: str):
    """Execute the next pending step (or all remaining steps) in a session.

    Body (optional): ``{"mode": "all"}`` or ``{"mode": "step"}``
    Default mode is ``"all"``.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    mode = body.get("mode", "all") if isinstance(body, dict) else "all"

    try:
        from aksara.ai.session_store import get_session

        session = get_session(session_id)
        if session is None:
            return JSONResponse(
                {"error": f"Session '{session_id}' not found"},
                status_code=404,
            )

        if mode == "step":
            from aksara.ai.investigation_runner import execute_next_step

            session = execute_next_step(session)
        else:
            from aksara.ai.investigation_runner import execute_investigation

            session = execute_investigation(session)

        return session.to_dict()
    except Exception as exc:
        return JSONResponse(
            {"error": f"Investigation execution failed: {exc}"},
            status_code=500,
        )


@router.get("/studio/ai/investigate/{session_id}")
async def studio_ai_investigate_get(request: Request, session_id: str):
    """Retrieve a single investigation session by ID."""
    try:
        from aksara.ai.session_store import get_session

        session = get_session(session_id)
        if session is None:
            return JSONResponse(
                {"error": f"Session '{session_id}' not found"},
                status_code=404,
            )
        return session.to_dict()
    except Exception as exc:
        return JSONResponse(
            {"error": f"Failed to retrieve session: {exc}"},
            status_code=500,
        )


@router.get("/studio/ai/investigate")
async def studio_ai_investigate_list(request: Request):
    """List all investigation sessions (newest first)."""
    try:
        from aksara.ai.session_store import list_sessions

        sessions = list_sessions()
        return {
            "sessions": [s.to_summary_dict() for s in sessions],
            "total": len(sessions),
        }
    except Exception as exc:
        return JSONResponse(
            {"error": f"Failed to list sessions: {exc}"},
            status_code=500,
        )


# =============================================================================
# v0.5.40: Daily Briefing + Investigation Continuation Endpoints
# =============================================================================


@router.get("/studio/ai/daily-briefing")
async def studio_ai_daily_briefing(request: Request):
    """Generate a daily system health briefing.

    Returns aggregated scores, issues, and recommendations from
    the performance analyser, architecture review, debugger, and
    recent investigation sessions.

    v0.5.40: New endpoint.
    """
    try:
        from aksara.ai.daily_briefing import generate_daily_briefing

        briefing = generate_daily_briefing()
        return briefing.to_dict()
    except Exception as exc:
        return JSONResponse(
            {"error": f"Failed to generate briefing: {exc}"},
            status_code=500,
        )


@router.post("/studio/ai/investigate/{session_id}/next")
async def studio_ai_investigate_next(request: Request, session_id: str):
    """Execute only the next pending step in an investigation session.

    This is the step-by-step interactive endpoint — the UI calls it
    repeatedly to advance the investigation one step at a time, showing
    progress between each step.

    v0.5.40: New endpoint for step-by-step investigation.
    """
    try:
        from aksara.ai.session_store import get_session
        from aksara.ai.investigation_runner import execute_next_step

        session = get_session(session_id)
        if session is None:
            return JSONResponse(
                {"error": f"Session '{session_id}' not found"},
                status_code=404,
            )

        session = execute_next_step(session)

        # Include progress information
        pending = sum(
            1 for s in (session.plan.steps if session.plan else [])
            if s.status == "pending"
        )
        done = sum(
            1 for s in (session.plan.steps if session.plan else [])
            if s.status == "done"
        )

        result = session.to_dict()
        result["progress"] = {
            "steps_done": done,
            "steps_pending": pending,
            "is_complete": session.status == "completed",
        }
        return result
    except Exception as exc:
        return JSONResponse(
            {"error": f"Failed to execute next step: {exc}"},
            status_code=500,
        )


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
            "Cache-Control": "no-cache, must-revalidate",
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
