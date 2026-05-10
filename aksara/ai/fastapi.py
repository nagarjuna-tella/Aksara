"""
Aksara AI FastAPI Endpoints

HTTP endpoints for AI tool discovery, query execution, code generation,
and full context export for LLM consumption.

v0.4.0 Endpoints:
- GET /ai/tools - List all tools the current user can access
- GET /ai/tools/mcp - List tools in MCP format
- GET /ai/tools/openai - List tools in OpenAI format
- GET /ai/tools/{name} - Get a specific tool by name

v0.4.2 Endpoints:
- POST /ai/query/plan/schema - Get JSON schema for AiQueryPlan
- POST /ai/query/execute - Execute an AI-generated query plan
- POST /ai/codegen/schema - Get JSON schemas for codegen models
- POST /ai/codegen/preview - Generate code from structured specs

v0.4.3 Endpoints:
- GET /ai/context/full - Complete application context for LLM consumption
- GET /ai/context/models - Models and relationships only
- GET /ai/context/viewsets - ViewSets and actions only
- GET /ai/context/settings - Settings and configuration only

v0.4.4 Endpoints:
- POST /ai/patch/preview - Preview patch operations without applying
- POST /ai/patch/apply - Apply patch operations (requires confirmation)
- GET /ai/patch/schema - Get JSON schema for patch operations

v0.4.5 Endpoints:
- GET /ai/plan/schema - Get JSON schema for AI plans
- POST /ai/plan/preview - Preview plan execution without applying
- POST /ai/plan/apply - Execute plan (requires confirmation)

v0.4.6 Endpoints:
- POST /ai/agent/context - Get full context bundle for external AI
- POST /ai/agent/plan/preview - Preview plan execution (always dry run)
- POST /ai/agent/plan/apply - Apply plan (requires confirm + header)

v0.4.7 Endpoints:
- GET /ai/schema/health - Full schema health report (models vs DB)
- GET /ai/schema/issues - Schema issues with filtering
- GET /ai/schema/diff - Detailed schema diff between models and DB
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

from aksara._version import __version__
from aksara.ai.registry import get_ai_tools_for_request
from aksara.ai.exporters import export_tools_as_generic, export_tools_as_mcp


router = APIRouter(tags=["AI"])


@router.get("/ai/tools")
async def list_ai_tools(request: Request) -> Dict[str, Any]:
    """
    List all AI tools the current user can access.
    
    Returns tools filtered by:
    - ai_exposed=True on ViewSet and actions
    - Permission checks (authentication, admin, etc.)
    - No DenyAI permission blocking
    
    Response:
        {
            "tools": [...],
            "count": N,
            "version": __version__
        }
    """
    tools = await get_ai_tools_for_request(request, request.app)
    
    return {
        "tools": [t.model_dump() for t in tools],
        "count": len(tools),
        "version": __version__,
    }


@router.get("/ai/tools/mcp")
async def list_ai_tools_mcp(request: Request) -> Dict[str, Any]:
    """
    List AI tools in MCP (Model Context Protocol) format.
    
    This endpoint returns tools formatted for MCP-compatible
    agent frameworks. The format includes:
    - name: Tool identifier
    - description: What the tool does
    - inputSchema: JSON Schema for parameters
    - metadata: HTTP details, permissions, etc.
    
    Response:
        {
            "tools": [...],
            "count": N,
            "version": __version__
        }
    """
    tools = await get_ai_tools_for_request(request, request.app)
    
    return {
        "tools": export_tools_as_mcp(tools),
        "count": len(tools),
        "version": __version__,
    }


@router.get("/ai/tools/openai")
async def list_ai_tools_openai(request: Request) -> Dict[str, Any]:
    """
    List AI tools in OpenAI function calling format.
    
    Compatible with OpenAI's function calling API and Assistants API.
    
    Response:
        {
            "functions": [...],
            "count": N,
            "version": __version__
        }
    """
    from aksara.ai.exporters import export_tools_as_openai_functions
    
    tools = await get_ai_tools_for_request(request, request.app)
    
    return {
        "functions": export_tools_as_openai_functions(tools),
        "count": len(tools),
        "version": __version__,
    }


@router.get("/ai/tools/{tool_name}")
async def get_ai_tool(tool_name: str, request: Request) -> Dict[str, Any]:
    """
    Get a specific AI tool by name.
    
    Returns 404 if the tool doesn't exist or the user
    doesn't have permission to access it.
    
    Args:
        tool_name: The unique tool identifier
        
    Response:
        Full tool details including input/output schemas
    """
    tools = await get_ai_tools_for_request(request, request.app)
    
    for tool in tools:
        if tool.name == tool_name:
            return {
                "tool": tool.model_dump(),
                "version": __version__,
            }
    
    raise HTTPException(
        status_code=404,
        detail=f"Tool '{tool_name}' not found or not accessible"
    )


# =============================================================================
# v0.4.2: Query Assistant Endpoints
# =============================================================================


@router.post("/ai/query/plan/schema")
async def get_ai_query_plan_schema() -> Dict[str, Any]:
    """
    Get JSON schema for AiQueryPlan.
    
    LLMs/providers can use this schema to understand how to
    structure query plans that Aksara can execute.
    
    Response:
        JSON Schema for AiQueryPlan including:
        - model: Target model name
        - filters: List of filter conditions
        - sorting: List of sort specifications
        - pagination: Limit/offset settings
        - select_fields: Optional field subset
    """
    from aksara.ai.query import get_query_plan_schema
    
    return {
        "schema": get_query_plan_schema(),
        "supported_lookups": [
            "exact", "gt", "gte", "lt", "lte", 
            "in", "isnull", "icontains", "contains"
        ],
        "version": "0.4.2",
    }


@router.post("/ai/query/execute")
async def execute_query_plan(request: Request) -> Dict[str, Any]:
    """
    Execute a structured AiQueryPlan against the database.
    
    This endpoint receives a query plan (usually generated by an LLM)
    and executes it against the Aksara ORM, returning serialized results.
    
    Request body:
        {
            "model": "User",
            "filters": [
                {"field": "is_active", "lookup": "exact", "value": true}
            ],
            "sorting": [
                {"field": "created_at", "direction": "desc"}
            ],
            "pagination": {"limit": 20, "offset": 0}
        }
    
    Response:
        {
            "plan": {...},
            "rows": [...],
            "count": N,
            "limited": bool
        }
    """
    from aksara.ai.query import AiQueryPlan, execute_ai_query_plan
    from aksara.exceptions import ConfigurationError
    
    try:
        body = await request.json()
        plan = AiQueryPlan.model_validate(body)
        result = await execute_ai_query_plan(plan)
        return result.model_dump()
    except ConfigurationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid query plan: {e}")


@router.get("/ai/query/models")
async def list_queryable_models() -> Dict[str, Any]:
    """
    List all models available for AI queries with their field information.
    
    Response:
        {
            "models": [
                {
                    "name": "User",
                    "description": "...",
                    "fields": [{"name": "email", "type": "Email", ...}],
                    "supported_lookups": [...]
                }
            ],
            "count": N,
            "version": "0.4.2"
        }
    """
    from aksara.ai.query import get_available_models_for_query
    
    models = get_available_models_for_query()
    
    return {
        "models": models,
        "count": len(models),
        "version": "0.4.2",
    }


# =============================================================================
# v0.4.2: CodeGen Endpoints
# =============================================================================


@router.post("/ai/codegen/schema")
async def get_ai_codegen_schema() -> Dict[str, Any]:
    """
    Get JSON schemas for code generation models.
    
    LLMs can use these schemas to understand how to format
    codegen requests that Aksara can execute.
    
    Response:
        {
            "schemas": {
                "AiFieldSpec": {...},
                "AiModelSpec": {...},
                "AiCodegenRequest": {...},
                "AiCodegenResult": {...}
            },
            "supported_targets": [...],
            "supported_field_types": [...],
            "version": "0.4.2"
        }
    """
    from aksara.ai.codegen import get_codegen_schemas, AiCodegenTarget, FIELD_TYPE_MAPPING
    
    return {
        "schemas": get_codegen_schemas(),
        "supported_targets": [
            AiCodegenTarget.MODEL,
            AiCodegenTarget.VIEWSET,
            AiCodegenTarget.SERIALIZER,
            AiCodegenTarget.APP,
            AiCodegenTarget.MIGRATION,
        ],
        "supported_field_types": list(FIELD_TYPE_MAPPING.keys()),
        "version": "0.4.2",
    }


@router.post("/ai/codegen/preview")
async def codegen_preview(request: Request) -> Dict[str, Any]:
    """
    Generate Aksara code from a structured specification.
    
    This endpoint receives a codegen request (usually formatted by an LLM)
    and deterministically generates Aksara-compatible code artifacts.
    
    Request body:
        {
            "target": "model",
            "model_spec": {
                "app_label": "blog",
                "name": "Article",
                "fields": [
                    {"name": "title", "type": "string", "max_length": 200},
                    {"name": "body", "type": "text"}
                ],
                "add_viewset": true,
                "add_serializer": true
            }
        }
    
    Response:
        {
            "files": {
                "blog/models.py": "...",
                "blog/views.py": "...",
                "blog/serializers.py": "..."
            },
            "notes": ["Add 'blog' to INSTALLED_APPS", ...]
        }
    """
    from aksara.ai.codegen import AiCodegenRequest, generate_code
    
    try:
        body = await request.json()
        codegen_request = AiCodegenRequest.model_validate(body)
        result = generate_code(codegen_request)
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid codegen request: {e}")


# =============================================================================
# v0.4.3: Context Engine Endpoints
# =============================================================================


@router.get("/ai/context/full")
async def get_full_ai_context(request: Request) -> Dict[str, Any]:
    """
    Get complete application context for LLM consumption.
    
    This is the single most important endpoint for AI-native development.
    It provides a complete structured snapshot of the entire application:
    
    - All models with fields, types, relationships, and AI metadata
    - All ViewSets with actions, permissions, and serializers
    - All API routes with methods and documentation
    - Migration history and pending migrations
    - Admin site configuration
    - Application settings (safe subset, no credentials)
    - Middleware stack
    - Available AI tools and schemas
    
    The response is:
    - Deterministic: Same app state = same output (except timestamp)
    - Stable: Fields are sorted alphabetically
    - Safe: No sensitive data (passwords, secrets) included
    - Checksummed: Content hash for change detection
    
    Response:
        {
            "framework": "aksara",
            "framework_version": "0.4.3",
            "context_version": "1.0.0",
            "generated_at": "2024-01-15T10:30:00Z",
            "checksum": "abc123...",
            "models": [...],
            "model_count": N,
            "viewsets": [...],
            "viewset_count": N,
            "routes": [...],
            "route_count": N,
            ...
        }
    """
    from aksara.ai.context import build_full_ai_context
    
    context = await build_full_ai_context(request.app)
    return context.model_dump()


@router.get("/ai/context/models")
async def get_ai_context_models(request: Request) -> Dict[str, Any]:
    """
    Get models and relationships context only.
    
    A focused subset of the full context containing:
    - All registered models
    - Field information with types and constraints
    - Relationship mappings (FK, M2M)
    - AI metadata (descriptions, permissions, sensitivity)
    
    Use this endpoint when you only need model/schema information.
    
    Response:
        {
            "models": [...],
            "model_count": N,
            "version": "0.4.3"
        }
    """
    from aksara.registry import ModelRegistry
    from aksara.ai.context import _extract_model_info
    import aksara
    
    models = []
    for model_cls in ModelRegistry.all().values():
        models.append(_extract_model_info(model_cls))
    
    # Sort deterministically
    models.sort(key=lambda m: (m.app_label, m.name))
    
    return {
        "models": [m.model_dump() for m in models],
        "model_count": len(models),
        "version": aksara.__version__,
    }


@router.get("/ai/context/viewsets")
async def get_ai_context_viewsets(request: Request) -> Dict[str, Any]:
    """
    Get ViewSets and actions context only.
    
    A focused subset of the full context containing:
    - All registered ViewSets
    - Custom @action methods
    - Permission configurations
    - Serializer mappings
    
    Use this endpoint when you only need API structure information.
    
    Response:
        {
            "viewsets": [...],
            "viewset_count": N,
            "version": "0.4.3"
        }
    """
    from aksara.ai.context import _extract_viewset_info
    import aksara
    
    viewsets = []
    viewset_registry = getattr(request.app.state, 'viewset_registry', None)
    if viewset_registry:
        for vs_cls in viewset_registry:
            viewsets.append(_extract_viewset_info(vs_cls))
    
    # Sort deterministically
    viewsets.sort(key=lambda v: v.name)
    
    return {
        "viewsets": [v.model_dump() for v in viewsets],
        "viewset_count": len(viewsets),
        "version": aksara.__version__,
    }


@router.get("/ai/context/settings")
async def get_ai_context_settings(request: Request) -> Dict[str, Any]:
    """
    Get application settings context only.
    
    Returns safe configuration values (no secrets/credentials):
    - App metadata (title, version)
    - Debug mode
    - Pool configuration
    - AI feature flags
    - Installed apps
    - Logging configuration
    
    Response:
        {
            "settings": {...},
            "middleware": [...],
            "middleware_count": N,
            "version": "0.4.3"
        }
    """
    from aksara.ai.context import _extract_settings_info, _extract_middleware_info
    import aksara
    
    settings_info = _extract_settings_info()
    middleware = _extract_middleware_info(request.app)
    
    return {
        "settings": settings_info.model_dump(),
        "middleware": [m.model_dump() for m in middleware],
        "middleware_count": len(middleware),
        "version": aksara.__version__,
    }


@router.get("/ai/context/routes")
async def get_ai_context_routes(request: Request) -> Dict[str, Any]:
    """
    Get all API routes context only.
    
    Returns complete route information:
    - Path and methods
    - OpenAPI summary and description
    - Tags for categorization
    - Source type (manual, viewset, admin, ai)
    
    Response:
        {
            "routes": [...],
            "route_count": N,
            "version": "0.4.3"
        }
    """
    from aksara.ai.context import _extract_routes_from_app
    import aksara
    
    routes = _extract_routes_from_app(request.app)
    
    return {
        "routes": [r.model_dump() for r in routes],
        "route_count": len(routes),
        "version": aksara.__version__,
    }


@router.get("/ai/context/admin")
async def get_ai_context_admin(request: Request) -> Dict[str, Any]:
    """
    Get admin site context only.
    
    Returns admin configuration:
    - Site name
    - Registered models
    - List display, filters, search fields
    - Ordering and readonly fields
    
    Response:
        {
            "admin": {...},
            "version": "0.4.3"
        }
    """
    from aksara.ai.context import _extract_admin_info
    import aksara
    
    admin = _extract_admin_info()
    
    return {
        "admin": admin.model_dump(),
        "version": aksara.__version__,
    }


# =============================================================================
# v0.4.4: AI Patch Engine Endpoints
# =============================================================================


@router.get("/ai/patch/schema")
async def get_ai_patch_schema() -> Dict[str, Any]:
    """
    Get JSON schema for AI patch operations.
    
    LLMs/agents can use this schema to understand how to
    structure patch requests that Aksara can safely apply.
    
    Response:
        {
            "operation_schema": {...},
            "request_schema": {...},
            "allowed_operations": [...],
            "version": "0.4.4"
        }
    """
    from aksara.ai.patch import (
        AiPatchOperation,
        AiPatchRequest,
        ALLOWED_OPERATIONS,
    )
    import aksara
    
    return {
        "operation_schema": AiPatchOperation.model_json_schema(),
        "request_schema": AiPatchRequest.model_json_schema(),
        "allowed_operations": list(ALLOWED_OPERATIONS),
        "safety_rules": {
            "blocked": [
                "Editing outside project directory",
                "Modifying migration files directly",
                "Dangerous code patterns (eval, exec, etc.)",
                "Invalid Python syntax after patch",
            ],
            "allowed": [
                "Editing app directories",
                "Adding/updating/deleting models",
                "Adding/updating/deleting fields",
                "Adding/updating/deleting viewsets",
                "Adding imports",
                "Text replacement and insertion",
            ]
        },
        "version": aksara.__version__,
    }


@router.post("/ai/patch/preview")
async def preview_ai_patch(request: Request) -> Dict[str, Any]:
    """
    Preview patch operations without applying them.
    
    This endpoint validates all operations and returns a preview
    of what would change, including unified diffs for each file.
    No files are modified on disk.
    
    Request body:
        {
            "operations": [
                {"type": "add_field", "model": "User", "field": "bio", "field_spec": {"type": "text"}}
            ],
            "reason": "Add bio field to user profile"
        }
    
    Response:
        {
            "applied": false,
            "preview_only": true,
            "files_changed": {
                "app/models.py": {
                    "path": "app/models.py",
                    "diff": "...",
                    "created": false
                }
            },
            "operations_applied": 1,
            "checksum": "abc123...",
            "version": "0.4.4"
        }
    """
    from aksara.ai.patch import AiPatchRequest, apply_ai_patches
    import aksara
    
    body = await request.json()
    
    try:
        patch_request = AiPatchRequest(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    # Get project root from app state or use default
    project_root = getattr(request.app.state, 'project_root', None)
    
    result = apply_ai_patches(
        patch_request,
        project_root=project_root,
        preview=True
    )
    
    return {
        **result.model_dump(),
        "version": aksara.__version__,
    }


@router.post("/ai/patch/apply")
async def apply_ai_patch(request: Request) -> Dict[str, Any]:
    """
    Apply patch operations to the codebase.
    
    ⚠️ WARNING: This endpoint modifies files on disk.
    
    Requires the header `X-AI-Apply: true` for safety.
    Without this header, the request will be rejected.
    
    Request body:
        {
            "operations": [
                {"type": "add_field", "model": "User", "field": "bio", "field_spec": {"type": "text"}}
            ],
            "reason": "Add bio field to user profile"
        }
    
    Headers:
        X-AI-Apply: true (required)
    
    Response:
        {
            "applied": true,
            "files_changed": {...},
            "operations_applied": 1,
            "rollback_available": true,
            "checksum": "abc123...",
            "version": "0.4.4"
        }
    """
    from aksara.ai.patch import AiPatchRequest, apply_ai_patches
    import aksara
    
    # Check for confirmation header
    confirm_header = request.headers.get("X-AI-Apply", "").lower()
    
    body = await request.json()
    
    try:
        patch_request = AiPatchRequest(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    # Get project root from app state or use default
    project_root = getattr(request.app.state, 'project_root', None)
    
    result = apply_ai_patches(
        patch_request,
        project_root=project_root,
        preview=False,
        confirm_header=confirm_header
    )
    
    if not result.applied and "X-AI-Apply" in str(result.errors):
        raise HTTPException(
            status_code=403,
            detail="Apply mode requires X-AI-Apply: true header"
        )
    
    return {
        **result.model_dump(),
        "version": aksara.__version__,
    }


# =============================================================================
# v0.4.5: AI Planner Endpoints (THE ARCHITECT)
# =============================================================================


@router.get("/ai/plan/schema")
async def get_ai_plan_schema() -> Dict[str, Any]:
    """
    Get JSON schema for AI plans.
    
    LLMs/agents can use this schema to understand how to
    structure multi-step plans that Aksara can execute.
    
    Response:
        {
            "AiPlan": {...},
            "AiPlanStep": {...},
            "valid_step_types": [...],
            "version": "0.4.5"
        }
    """
    from aksara.ai.planner import get_plan_schema
    import aksara
    
    return {
        **get_plan_schema(),
        "version": aksara.__version__,
    }


@router.post("/ai/plan/preview")
async def preview_ai_plan(request: Request) -> Dict[str, Any]:
    """
    Preview plan execution without applying changes.
    
    This endpoint validates and executes the plan in dry-run mode.
    Steps are executed but no files are modified on disk.
    
    Request body:
        {
            "intent": "Add slug field to Article model",
            "steps": [
                {"id": "s1", "type": "analyze_context", "description": "Check current state"},
                {"id": "s2", "type": "create_field", "description": "Add slug field", 
                 "depends_on": ["s1"], 
                 "payload": {"model": "Article", "field": "slug", "field_spec": {"type": "slug"}}}
            ]
        }
    
    Response:
        {
            "success": true,
            "steps": [...step results...],
            "notes": [...],
            "dry_run": true,
            "version": "0.4.5"
        }
    """
    from aksara.ai.planner import AiPlan, execute_plan, validate_plan
    import aksara
    
    body = await request.json()
    
    try:
        plan = AiPlan(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    # Validate plan first
    errors = validate_plan(plan)
    if errors:
        raise HTTPException(status_code=400, detail={"validation_errors": errors})
    
    # Execute in dry-run mode
    result = await execute_plan(request.app, plan, dry_run=True)
    
    return {
        **result.model_dump(),
        "version": aksara.__version__,
    }


@router.post("/ai/plan/apply")
async def apply_ai_plan(request: Request) -> Dict[str, Any]:
    """
    Execute a plan and apply changes to the codebase.
    
    ⚠️ WARNING: This endpoint modifies files on disk.
    
    Requires the header `X-AI-Apply: true` for safety.
    Without this header, the request will be rejected.
    
    Steps are executed in topological order based on depends_on.
    Execution stops on first failure (fail-fast).
    
    Request body:
        {
            "intent": "Add slug field to Article model",
            "steps": [
                {"id": "s1", "type": "analyze_context", "description": "Check current state"},
                {"id": "s2", "type": "create_field", "description": "Add slug field",
                 "depends_on": ["s1"],
                 "payload": {"model": "Article", "field": "slug", "field_spec": {"type": "slug"}}}
            ]
        }
    
    Headers:
        X-AI-Apply: true (required)
    
    Response:
        {
            "success": true,
            "steps": [...step results...],
            "notes": [...],
            "dry_run": false,
            "version": "0.4.5"
        }
    """
    from aksara.ai.planner import AiPlan, execute_plan, validate_plan
    import aksara
    
    # Check for confirmation header
    confirm_header = request.headers.get("X-AI-Apply", "").lower()
    if confirm_header != "true":
        raise HTTPException(
            status_code=403,
            detail="Apply mode requires X-AI-Apply: true header"
        )
    
    body = await request.json()
    
    try:
        plan = AiPlan(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    # Validate plan first
    errors = validate_plan(plan)
    if errors:
        raise HTTPException(status_code=400, detail={"validation_errors": errors})
    
    # Execute for real
    result = await execute_plan(request.app, plan, dry_run=False)
    
    return {
        **result.model_dump(),
        "version": aksara.__version__,
    }


# =============================================================================
# v0.4.6: AI Runtime (Mini Agent Loop) Endpoints
# =============================================================================


@router.post("/ai/agent/context")
async def get_agent_context(request: Request) -> Dict[str, Any]:
    """
    Get full context bundle for an external AI agent.
    
    This is step 1 of the agent loop:
    User says something → client calls this → gets all info to build a plan.
    
    The bundle includes:
    - Full application context (models, routes, migrations, admin, settings)
    - Available AI tools
    - Plan schema (for constructing AiPlan)
    - Patch schema (for understanding patch operations)
    - Query plan schema (for database queries)
    - Codegen schema (for code generation)
    
    This endpoint is always safe (read-only, no side effects).
    
    Request body:
        {
            "user_message": "Add a slug field to Article model",
            "mode": "modify",
            "scope": ["models", "migrations"],
            "hints": {"model": "Article"}
        }
    
    Response:
        AgentContextBundle with full context and all schemas
    """
    from aksara.ai.agent import AgentIntent, build_agent_context_bundle
    import aksara
    
    body = await request.json()
    
    try:
        intent = AgentIntent(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    bundle = await build_agent_context_bundle(request.app, intent)
    
    return bundle.model_dump()


@router.post("/ai/agent/plan/preview")
async def preview_agent_plan(request: Request) -> Dict[str, Any]:
    """
    Preview plan execution without applying changes (always dry run).
    
    This is step 2 of the agent loop:
    External AI constructs a plan → calls this to preview → shows user.
    
    This endpoint:
    - Always runs in dry_run=True mode (ignores payload.dry_run)
    - Does NOT modify any files on disk
    - Returns execution result with step outputs
    - Includes a summary for UI display
    
    Request body:
        {
            "intent": {...},
            "plan": {
                "intent": "Add slug field",
                "steps": [
                    {"id": "s1", "type": "analyze_context", "description": "..."}
                ]
            },
            "dry_run": true
        }
    
    Response:
        {
            "intent": {...},
            "plan": {...},
            "execution": {...step results...},
            "summary": {"success": true, "step_count": 1, "failed_steps": []}
        }
    """
    from aksara.ai.agent import (
        AgentIntent,
        AgentPlanExecutionRequest,
        AgentPlanPreviewResponse,
    )
    from aksara.ai.planner import AiPlan, execute_plan, validate_plan
    
    body = await request.json()
    
    try:
        payload = AgentPlanExecutionRequest(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    # Parse and validate the plan
    try:
        plan = AiPlan(**payload.plan)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid plan: {e}")
    
    errors = validate_plan(plan)
    if errors:
        raise HTTPException(status_code=400, detail={"validation_errors": errors})
    
    # Always dry_run=True for preview, ignore payload.dry_run
    execution = await execute_plan(request.app, plan, dry_run=True)
    
    # Build summary for UI
    summary = {
        "success": execution.success,
        "step_count": len(execution.steps),
        "failed_steps": [s.id for s in execution.steps if not s.success],
        "completed_steps": [s.id for s in execution.steps if s.success],
    }
    
    response = AgentPlanPreviewResponse(
        intent=payload.intent,
        plan=payload.plan,
        execution=execution.model_dump(),
        summary=summary,
    )
    
    return response.model_dump()


@router.post("/ai/agent/plan/apply")
async def apply_agent_plan(request: Request) -> Dict[str, Any]:
    """
    Apply a plan and make actual changes to the codebase.
    
    ⚠️ WARNING: This endpoint modifies files on disk.
    
    This is step 3 of the agent loop:
    User confirms preview → calls this with confirm=True + header.
    
    Safety requirements:
    1. payload.confirm must be True
    2. X-AI-Apply: true header must be present
    
    Both safeguards must pass for changes to be applied.
    
    Layered safety:
    - Planner decides WHAT to do (steps)
    - Patch Engine validates + AST-checks HOW (syntax, safety)
    - Headers & confirm flag gate WHEN (user consent)
    
    Request body:
        {
            "intent": {...},
            "plan": {...},
            "confirm": true
        }
    
    Headers:
        X-AI-Apply: true (required)
    
    Response:
        {
            "intent": {...},
            "plan": {...},
            "execution": {...step results...}
        }
    """
    from aksara.ai.agent import (
        AgentIntent,
        AgentPlanApplyRequest,
        AgentPlanApplyResponse,
    )
    from aksara.ai.planner import AiPlan, execute_plan, validate_plan
    
    body = await request.json()
    
    try:
        payload = AgentPlanApplyRequest(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    # Check confirmation requirements
    x_ai_apply = request.headers.get("X-AI-Apply", "").lower()
    
    if not payload.confirm or x_ai_apply != "true":
        raise HTTPException(
            status_code=400,
            detail="Plan application requires confirm=true and X-AI-Apply: true header."
        )
    
    # Parse and validate the plan
    try:
        plan = AiPlan(**payload.plan)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid plan: {e}")
    
    errors = validate_plan(plan)
    if errors:
        raise HTTPException(status_code=400, detail={"validation_errors": errors})
    
    # Execute for real (dry_run=False)
    execution = await execute_plan(request.app, plan, dry_run=False)
    
    response = AgentPlanApplyResponse(
        intent=payload.intent,
        plan=payload.plan,
        execution=execution.model_dump(),
    )
    
    return response.model_dump()


# =============================================================================
# v0.4.7 Endpoints - Schema Doctor & Migration Guardrails
# =============================================================================


@router.get("/ai/schema/health")
async def get_schema_health(request: Request) -> Dict[str, Any]:
    """
    Get full schema health report.
    
    Compares models vs database schema and returns:
    - Overall health status (healthy/degraded/danger)
    - Issue counts by severity
    - Detailed list of all schema issues
    - Database metadata
    
    Status rules:
    - healthy: No warnings or danger issues
    - degraded: Has warnings but no danger issues
    - danger: Has at least one danger issue
    
    Response:
        {
            "status": "healthy|degraded|danger",
            "issue_counts": {"info": 0, "warning": 0, "danger": 0},
            "issues": [...],
            "inspected_at": "2026-01-25T12:00:00Z",
            "db_version": "PostgreSQL 16.1",
            "db_name": "myapp_prod",
            "app_version": "0.4.7"
        }
    """
    from aksara.ai.schema_doctor import analyze_schema_health
    
    health = await analyze_schema_health(request.app)
    return health.model_dump()


@router.get("/ai/schema/issues")
async def get_schema_issues(
    request: Request,
    severity: Optional[str] = None,
    kind: Optional[str] = None,
    table: Optional[str] = None,
    app_label: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get schema issues with optional filtering.
    
    A lighter endpoint that returns just status and issues,
    with support for filtering by severity, kind, table, or app.
    
    Query Parameters:
        severity: Filter by severity (info, warning, danger)
        kind: Filter by drift kind (missing_table, extra_column, etc.)
        table: Filter by table name
        app_label: Filter by application label
    
    Response:
        {
            "status": "healthy|degraded|danger",
            "issues": [...],
            "total_count": N,
            "filtered_count": N
        }
    """
    from aksara.ai.schema_doctor import analyze_schema_health, AiSchemaIssue
    
    health = await analyze_schema_health(request.app)
    
    # Start with all issues
    filtered_issues = health.issues
    total_count = len(filtered_issues)
    
    # Apply severity filter
    if severity:
        valid_severities = {"info", "warning", "danger"}
        if severity not in valid_severities:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid severity: {severity}. Must be one of: {valid_severities}"
            )
        filtered_issues = [i for i in filtered_issues if i.severity == severity]
    
    # Apply kind filter
    if kind:
        valid_kinds = {
            "missing_table", "extra_table", "missing_column", "extra_column",
            "type_mismatch", "nullability_mismatch", "default_mismatch",
            "pk_mismatch", "fk_mismatch", "index_mismatch", "unique_mismatch"
        }
        if kind not in valid_kinds:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid kind: {kind}. Must be one of: {valid_kinds}"
            )
        filtered_issues = [i for i in filtered_issues if i.kind == kind]
    
    # Apply table filter
    if table:
        filtered_issues = [i for i in filtered_issues if i.table == table]
    
    # Apply app_label filter
    if app_label:
        filtered_issues = [i for i in filtered_issues if i.app_label == app_label]
    
    return {
        "status": health.status,
        "issues": [i.model_dump() for i in filtered_issues],
        "total_count": total_count,
        "filtered_count": len(filtered_issues),
    }


@router.get("/ai/schema/diff")
async def get_schema_diff(
    request: Request,
    table: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get a detailed schema diff between models and database.
    
    Returns a side-by-side comparison of model definitions vs
    actual database schema for analysis.
    
    Query Parameters:
        table: Filter to a specific table
    
    Response:
        {
            "tables": {
                "blog_articles": {
                    "model": {...},
                    "database": {...},
                    "drift": [...]
                }
            },
            "model_only": [...],
            "db_only": [...],
            "inspected_at": "..."
        }
    """
    from datetime import datetime, timezone
    from aksara.ai.schema_doctor import (
        introspect_db_schema,
        build_model_schema_map,
        detect_schema_drift,
    )
    from aksara.db.engine import Database
    
    # Get database instance
    try:
        db = Database.get_instance()
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="Database is not configured or connected"
        )
    
    # Get both schemas
    db_map = await introspect_db_schema(db)
    models_map = build_model_schema_map()
    
    # Filter by table if requested
    if table:
        if table not in models_map and table not in db_map:
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table}' not found in models or database"
            )
        if table in models_map:
            models_map = {table: models_map[table]}
        else:
            models_map = {}
        if table in db_map:
            db_map = {table: db_map[table]}
        else:
            db_map = {}
    
    # Get drift issues
    issues = detect_schema_drift(models_map, db_map)
    
    # Build response structure
    model_tables = set(models_map.keys())
    db_tables = set(db_map.keys())
    
    # System tables to exclude
    system_tables = {
        "alembic_version",
        "aksara_migrations",
        "django_migrations",
        "spatial_ref_sys",
    }
    db_tables = db_tables - system_tables
    
    common_tables = model_tables & db_tables
    model_only = list(model_tables - db_tables)
    db_only = list(db_tables - model_tables)
    
    tables_diff = {}
    for tbl in common_tables:
        model_info = models_map.get(tbl, {})
        db_info = db_map.get(tbl)
        
        table_issues = [i.model_dump() for i in issues if i.table == tbl]
        
        tables_diff[tbl] = {
            "model": model_info,
            "database": db_info.model_dump() if db_info else None,
            "drift": table_issues,
        }
    
    return {
        "tables": tables_diff,
        "model_only": model_only,
        "db_only": db_only,
        "inspected_at": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# v0.5.37: AI Consolidation & Orchestration Endpoints
# =============================================================================


@router.post("/ai/intent/handle")
async def ai_intent_handle(request: Request) -> Dict[str, Any]:
    """Handle a natural-language prompt through the Intent Engine.

    Routes the prompt through the full orchestration pipeline:
    classify intent → build execution plan → execute plan → return result.

    Request body::

        {"prompt": "why is /api/users slow?"}

    Returns
    -------
    dict
        Unified orchestration result.
    """
    body = await request.json()
    prompt = body.get("prompt", "")
    if not prompt:
        raise HTTPException(status_code=422, detail="prompt is required")

    from aksara.ai.intent_engine import handle_prompt

    result = handle_prompt(prompt)
    return result.to_dict()


@router.post("/ai/investigate")
async def ai_investigate(request: Request) -> Dict[str, Any]:
    """Run the full AI Investigation pipeline.

    Executes all analysis steps and returns a System Intelligence Report:
    - build_project_graph
    - run_architecture_review
    - run_performance_analysis
    - run_debugger
    - run_diagnostics

    Returns
    -------
    dict
        Complete investigation report.
    """
    from aksara.ai.intent_engine import run_investigation

    result = run_investigation()
    return result.to_dict()


@router.get("/ai/hub/overview")
async def ai_hub_overview(request: Request) -> Dict[str, Any]:
    """AI Hub overview — status, default provider, active models, routing.

    Returns a dashboard-style summary of the AI system configuration.
    """
    overview: Dict[str, Any] = {
        "ai_status": "active",
        "default_provider": None,
        "active_models": [],
        "routing": {},
        "version": "0.5.37",
    }

    try:
        from aksara.ai.providers_unified import detect_all_providers, get_active_provider
        providers = detect_all_providers()
        active = get_active_provider()
        overview["default_provider"] = active.name if active else None
        overview["active_models"] = [
            {"provider": p.name, "models": p.models}
            for p in providers
            if p.available
        ]
    except Exception:
        overview["ai_status"] = "not_configured"

    try:
        from aksara.ai.intent_classifier import list_supported_intents
        overview["routing"] = {
            "supported_intents": list_supported_intents(),
            "engine": "intent_engine_v1",
        }
    except Exception:
        pass

    return overview


@router.get("/ai/inspector/summary")
async def ai_inspector_summary(request: Request) -> Dict[str, Any]:
    """AI Inspector summary — unified view of debug, architecture, performance.

    Returns a lightweight summary suitable for the Inspector overview tab.
    """
    summary: Dict[str, Any] = {
        "debugger": {"available": True},
        "architecture": {"available": True},
        "performance": {"available": True},
    }

    try:
        from aksara.ai.project_graph import build_project_graph
        graph = build_project_graph()
        summary["graph_summary"] = graph.to_summary_dict()
    except Exception:
        summary["graph_summary"] = None

    return summary


@router.get("/ai/graph/enhanced")
async def ai_graph_enhanced(request: Request) -> Dict[str, Any]:
    """AI Graph with summary panel metrics.

    Returns the Project Context Graph plus computed summary metrics
    suitable for the Graph system explorer view.
    """
    try:
        from aksara.ai.project_graph import build_project_graph
        graph = build_project_graph()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Graph build failed: {exc}")

    m = graph.metadata
    return {
        "summary": {
            "models": m.model_count,
            "routes": m.route_count,
            "queries": m.query_count,
            "migrations": m.migration_count,
            "diagnostics": m.diagnostic_count,
            "gaps": m.gap_count,
            "events": m.event_count,
        },
        "graph": graph.to_summary_dict(),
        "model_names": [mod.name for mod in graph.models],
        "route_paths": [f"{r.method} {r.path}" for r in graph.routes],
        "generated_at": m.generated_at,
    }


@router.post("/ai/intent/classify")
async def ai_intent_classify(request: Request) -> Dict[str, Any]:
    """Classify a prompt without executing (preview mode).

    Request body::

        {"prompt": "explain my architecture"}

    Returns
    -------
    dict
        Intent match and planned execution steps.
    """
    body = await request.json()
    prompt = body.get("prompt", "")
    if not prompt:
        raise HTTPException(status_code=422, detail="prompt is required")

    from aksara.ai.intent_engine import classify_and_plan

    match, plan = classify_and_plan(prompt)
    return {
        "intent": match.intent,
        "confidence": match.confidence,
        "entities": match.entities,
        "planned_steps": plan.steps,
    }