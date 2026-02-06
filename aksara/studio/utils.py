"""
Aksara Studio Utilities

Helper functions for building Studio responses.
Builds on top of existing AI context functions.

v0.5.0: Studio Core & Handshake
v0.5.1: Studio Core Polish - richer summaries, migrations endpoint
v0.5.2: Runtime & DX - runtime info, routes endpoint
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from aksara.studio.models import (
    StudioCapability,
    StudioChecksums,
    StudioContextSummary,
    StudioDatabaseStatus,
    StudioHandshake,
    StudioHealthResponse,
    StudioModelSummary,
    StudioProjectInfo,
    # v0.5.1: New models
    StudioMigrationStatus,
    StudioAppMigrationSummary,
    StudioMigrationConflict,
    StudioMigrationSummary,
    # v0.5.2: Runtime models
    StudioRuntimeInfo,
    StudioRouteInfo,
    # v0.5.4: AI Integration models
    StudioAiProjectMeta,
    StudioAiModelSummary,
    StudioAiRouteSummary,
    StudioAiToolInfo,
    StudioAiContextExport,
    StudioAiSchemas,
    StudioAiPromptTemplate,
    StudioAiPrompts,
)

if TYPE_CHECKING:
    from fastapi import FastAPI


# =============================================================================
# v0.5.2: Process Start Time Tracking
# =============================================================================

# Record when the module is first imported (approximates process start)
_PROCESS_START_TIME = datetime.now(timezone.utc)


def compute_schema_checksum(models: List[Any]) -> str:
    """
    Compute SHA-256 checksum of model schema.
    
    Args:
        models: List of model info dicts or objects
        
    Returns:
        16-character hex checksum
    """
    # Serialize models to deterministic JSON
    def serialize(obj):
        if hasattr(obj, 'model_dump'):
            return obj.model_dump()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return str(obj)
    
    data = [serialize(m) for m in models]
    json_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


def compute_migrations_checksum(migrations_dir: Optional[Path] = None) -> str:
    """
    Compute checksum of migration file list.
    
    Args:
        migrations_dir: Path to migrations directory
        
    Returns:
        16-character hex checksum
    """
    if migrations_dir is None:
        from aksara.conf import settings
        migrations_dir = Path(settings.migrations_dir)
    
    if not migrations_dir.exists():
        return "0" * 16
    
    # List migration files
    migration_files = sorted(
        f.name for f in migrations_dir.glob("*.sql")
    )
    
    json_str = json.dumps(migration_files, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


def compute_settings_checksum() -> str:
    """
    Compute checksum of non-sensitive settings.
    
    Returns:
        16-character hex checksum
    """
    from aksara.conf import settings
    
    # Only include non-sensitive settings
    safe_settings = {
        "debug": settings.debug,
        "log_level": settings.log_level,
        "pool_min_size": settings.pool_min_size,
        "pool_max_size": settings.pool_max_size,
        "migrations_dir": settings.migrations_dir,
        "ai_enabled": settings.ai_enabled,
        "mcp_enabled": settings.mcp_enabled,
        "apps": settings.apps,
    }
    
    json_str = json.dumps(safe_settings, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


def compute_routes_checksum(app: "FastAPI") -> str:
    """
    Compute checksum of route definitions.
    
    Args:
        app: FastAPI application
        
    Returns:
        16-character hex checksum
    """
    routes = []
    for route in app.routes:
        route_info = {
            "path": getattr(route, "path", str(route)),
            "methods": sorted(getattr(route, "methods", [])),
        }
        routes.append(route_info)
    
    routes.sort(key=lambda r: r["path"])
    json_str = json.dumps(routes, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


def _get_database_status(app: "FastAPI") -> StudioDatabaseStatus:
    """
    Get current database status.
    
    Args:
        app: FastAPI application
        
    Returns:
        StudioDatabaseStatus instance
    """
    db = getattr(app, '_db', None) or getattr(app.state, 'db', None)
    
    if db is None:
        return StudioDatabaseStatus(
            connected=False,
            dialect="postgresql",
            pool_size=0,
            pool_available=0,
        )
    
    # Get pool info if available
    pool = getattr(db, '_pool', None)
    pool_size = 0
    pool_available = 0
    
    if pool is not None:
        pool_size = getattr(pool, 'get_size', lambda: 0)()
        pool_available = getattr(pool, 'get_idle_size', lambda: 0)()
    
    return StudioDatabaseStatus(
        connected=pool is not None,
        dialect="postgresql",
        pool_size=pool_size,
        pool_available=pool_available,
    )


def _get_capabilities(app: "FastAPI") -> List[StudioCapability]:
    """
    Determine available Studio capabilities.
    
    Args:
        app: FastAPI application
        
    Returns:
        List of available capabilities
    """
    from aksara.conf import settings
    
    capabilities = [
        StudioCapability.READ_SCHEMA,
        StudioCapability.READ_MIGRATIONS,
    ]
    
    # Check database connection
    db = getattr(app, '_db', None) or getattr(app.state, 'db', None)
    if db is not None and getattr(db, '_pool', None) is not None:
        capabilities.append(StudioCapability.READ_DATA)
        
        # Write capabilities in debug mode only (by default)
        if settings.debug:
            capabilities.append(StudioCapability.WRITE_DATA)
            capabilities.append(StudioCapability.APPLY_MIGRATIONS)
    
    # AI capabilities
    if settings.ai_enabled:
        capabilities.extend([
            StudioCapability.AI_TOOLS,
            StudioCapability.AI_QUERY,
            StudioCapability.AI_CODEGEN,
            StudioCapability.AI_PATCH,
            StudioCapability.AI_PLANNER,
        ])
    
    # Admin capability
    enable_admin = getattr(app, 'enable_admin', None)
    if enable_admin or (enable_admin is None and settings.debug):
        capabilities.append(StudioCapability.ADMIN_ACCESS)
    
    # Debug panels
    if settings.debug:
        capabilities.append(StudioCapability.DEBUG_PANELS)
    
    return capabilities


def _get_environment() -> str:
    """Determine current environment."""
    from aksara.conf import settings
    
    # Check environment variable first
    import os
    env = os.environ.get("AKSARA_ENV") or os.environ.get("ENV")
    if env:
        return env.lower()
    
    # Default based on debug mode
    if settings.debug:
        return "development"
    
    return "production"


async def build_studio_handshake(app: "FastAPI") -> StudioHandshake:
    """
    Build complete Studio handshake response.
    
    This is the main function called by GET /studio/handshake.
    It aggregates all necessary information for Studio IDE.
    
    Args:
        app: FastAPI application
        
    Returns:
        StudioHandshake with complete project info
    """
    import aksara
    from aksara.conf import settings
    from aksara.registry import ModelRegistry
    
    # Get models for checksum
    models = list(ModelRegistry.all().values())
    
    # Build checksums
    checksums = StudioChecksums(
        schema_checksum=compute_schema_checksum(models),
        migrations_checksum=compute_migrations_checksum(),
        settings_checksum=compute_settings_checksum(),
        routes_checksum=compute_routes_checksum(app),
    )
    
    # Build project info
    project = StudioProjectInfo(
        name=settings.app_title or app.title or "Aksara App",
        version=settings.app_version or app.version or "0.0.0",
        aksara_version=aksara.__version__,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        debug_mode=settings.debug,
        environment=_get_environment(),
    )
    
    # Build database status
    database = _get_database_status(app)
    
    # Build capabilities
    capabilities = _get_capabilities(app)
    
    # Build handshake
    return StudioHandshake(
        protocol_version="1.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        project=project,
        database=database,
        capabilities=capabilities,
        checksums=checksums,
    )


async def build_context_summary(app: "FastAPI") -> StudioContextSummary:
    """
    Build lightweight context summary.
    
    This provides counts and basic info without full schema transfer.
    
    v0.5.1: Added app_count, database_status, migration_status.
    
    Args:
        app: FastAPI application
        
    Returns:
        StudioContextSummary with counts and model list
    """
    from aksara.registry import ModelRegistry
    from aksara.conf import settings
    from aksara.migrations import discover_all_migrations
    
    # Get models
    model_classes = list(ModelRegistry.all().values())
    
    # Build model summaries
    model_summaries = []
    for model_cls in model_classes:
        # Count fields and check for relations
        fields = getattr(model_cls, '_fields', {})
        field_count = len(fields)
        has_relations = any(
            getattr(f, '_is_relation', False) or
            f.__class__.__name__ in ('ForeignKey', 'ManyToMany')
            for f in fields.values()
        )
        
        model_summaries.append(StudioModelSummary(
            name=model_cls.__name__,
            table_name=getattr(model_cls, '_table_name', model_cls.__name__.lower()),
            field_count=field_count,
            has_relations=has_relations,
        ))
    
    # Sort deterministically
    model_summaries.sort(key=lambda m: m.name)
    
    # Count viewsets
    viewset_registry = getattr(app.state, 'viewset_registry', [])
    viewset_count = len(list(viewset_registry)) if viewset_registry else 0
    
    # Count routes
    route_count = len(app.routes)
    
    # Count AI tools
    ai_registry = getattr(app, 'ai_registry', None)
    ai_tool_count = len(ai_registry) if ai_registry else 0
    
    # v0.5.1: Discover all migrations (not just .sql)
    migrations_dir = Path(settings.migrations_dir)
    all_migrations = discover_all_migrations(migrations_dir, include_internal=True)
    migration_count = len(all_migrations)
    
    # v0.5.1: Get app count from settings
    app_count = len(settings.installed_apps) if settings.installed_apps else len(settings.apps)
    
    # v0.5.1: Get database status
    database_status = _get_database_status(app)
    
    # v0.5.1: Build migration status (lightweight version)
    migration_status = StudioMigrationStatus(
        total=migration_count,
        applied=0,  # Would require DB check - filled in async endpoint
        pending=0,  # Would require DB check - filled in async endpoint
        has_conflicts=False,  # Would require graph check
        last_applied=None,
    )
    
    # Build checksums
    checksums = StudioChecksums(
        schema_checksum=compute_schema_checksum(model_classes),
        migrations_checksum=compute_migrations_checksum(),
        settings_checksum=compute_settings_checksum(),
        routes_checksum=compute_routes_checksum(app),
    )
    
    return StudioContextSummary(
        app_count=app_count,
        model_count=len(model_classes),
        viewset_count=viewset_count,
        route_count=route_count,
        ai_tool_count=ai_tool_count,
        migration_count=migration_count,
        pending_migrations=0,  # Would require DB check
        database_status=database_status,
        migration_status=migration_status,
        models=model_summaries,
        checksums=checksums,
    )


async def build_migration_summary(app: "FastAPI") -> StudioMigrationSummary:
    """
    Build detailed migration summary with per-app statistics.
    
    v0.5.1: New endpoint response builder.
    
    This requires database access to check applied migrations and
    may be slower than build_context_summary.
    
    Args:
        app: FastAPI application
        
    Returns:
        StudioMigrationSummary with per-app stats and conflicts
    """
    from aksara.conf import settings
    from aksara.migrations import (
        discover_all_migrations,
        build_migration_graph,
        check_migration_conflicts,
        get_applied_migrations,
    )
    from aksara.migrations.executor import extract_app_label_from_name
    
    migrations_dir = Path(settings.migrations_dir)
    
    # Discover all migrations
    all_migrations = discover_all_migrations(migrations_dir, include_internal=True)
    
    # Build migration graph
    graph = build_migration_graph(migrations_dir, include_internal=True, migrations_list=all_migrations)
    
    # Try to get applied migrations from DB
    applied_names: List[str] = []
    last_applied: Optional[str] = None
    
    db = getattr(app, '_db', None) or getattr(app.state, 'db', None)
    if db:
        try:
            async with db.acquire() as conn:
                applied_names = await get_applied_migrations(conn)
                if applied_names:
                    last_applied = applied_names[-1]
        except Exception:
            pass  # DB not available, proceed with empty list
    
    applied_set = set(applied_names)
    
    # Check for conflicts
    conflicts_dict = check_migration_conflicts(graph, applied_names)
    
    # Build per-app summaries
    app_migrations: Dict[str, Dict[str, Any]] = {}
    
    for name, file_path in all_migrations:
        app_label = extract_app_label_from_name(name, file_path)
        
        if app_label not in app_migrations:
            app_migrations[app_label] = {
                "total": 0,
                "applied": 0,
                "pending": 0,
                "has_conflicts": app_label in conflicts_dict,
                "head_migrations": [],
            }
        
        app_migrations[app_label]["total"] += 1
        if name in applied_set:
            app_migrations[app_label]["applied"] += 1
        else:
            app_migrations[app_label]["pending"] += 1
    
    # Get head migrations for each app
    for app_label in app_migrations:
        heads = graph.heads_for_app(app_label)
        app_migrations[app_label]["head_migrations"] = [h.name for h in heads]
    
    # Build app summaries list
    app_summaries = [
        StudioAppMigrationSummary(
            app_label=app_label,
            total=data["total"],
            applied=data["applied"],
            pending=data["pending"],
            has_conflicts=data["has_conflicts"],
            head_migrations=data["head_migrations"],
        )
        for app_label, data in sorted(app_migrations.items())
    ]
    
    # Build conflict details
    conflict_details = [
        StudioMigrationConflict(
            app_label=app_label,
            heads=[h.name for h in heads],
            message=f"App '{app_label}' has {len(heads)} conflicting head migrations that need to be merged.",
        )
        for app_label, heads in conflicts_dict.items()
    ]
    
    # Totals
    total_migrations = len(all_migrations)
    applied_migrations = len(applied_names)
    pending_migrations = total_migrations - applied_migrations
    
    return StudioMigrationSummary(
        total_migrations=total_migrations,
        applied_migrations=applied_migrations,
        pending_migrations=pending_migrations,
        apps=app_summaries,
        conflicts=conflict_details,
        migrations_checksum=compute_migrations_checksum(),
        last_applied=last_applied,
    )


async def build_health_response(app: "FastAPI") -> StudioHealthResponse:
    """
    Build simple health check response.
    
    Args:
        app: FastAPI application
        
    Returns:
        StudioHealthResponse with health status
    """
    import aksara
    
    database = _get_database_status(app)
    
    # Determine overall status
    status = "healthy" if database.connected else "degraded"
    
    return StudioHealthResponse(
        status=status,
        aksara_version=aksara.__version__,
        database=database,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# =============================================================================
# v0.5.2: Runtime Info Functions
# =============================================================================

async def build_runtime_info(app: "FastAPI") -> StudioRuntimeInfo:
    """
    Build runtime diagnostics information.
    
    v0.5.2: Read-only runtime info for Studio and CLI.
    
    Args:
        app: FastAPI application
        
    Returns:
        StudioRuntimeInfo with process and environment details
    """
    import aksara
    from aksara.conf import settings
    
    # Get database status
    db_status = _get_database_status(app)
    if db_status.connected:
        database_status_str = "ok"
    elif db_status.last_error:
        database_status_str = "degraded"
    else:
        database_status_str = "disconnected"
    
    # Count pending migrations (simplified - full count requires DB)
    pending_migrations = 0
    try:
        from aksara.migrations import discover_all_migrations
        migrations_dir = Path(settings.migrations_dir)
        all_migrations = discover_all_migrations(migrations_dir, include_internal=True)
        pending_migrations = len(all_migrations)  # Approximation without DB check
    except Exception:
        pass
    
    # Get installed apps
    installed_apps = list(settings.installed_apps) if settings.installed_apps else list(settings.apps)
    
    # Calculate uptime
    now = datetime.now(timezone.utc)
    uptime_seconds = (now - _PROCESS_START_TIME).total_seconds()
    
    # Check if Studio is enabled
    studio_enabled = getattr(settings, 'enable_studio', True)
    
    # Get environment name
    env = getattr(settings, 'env', None) or _get_environment()
    
    return StudioRuntimeInfo(
        app_version=aksara.__version__,
        python_version=sys.version.split()[0],
        debug=settings.debug,
        env=env,
        pid=os.getpid(),
        start_time=_PROCESS_START_TIME,
        uptime_seconds=uptime_seconds,
        database_status=database_status_str,
        pending_migrations=pending_migrations,
        installed_apps=installed_apps,
        studio_enabled=studio_enabled,
        studio_base_path="/studio",
    )


def build_routes_info(app: "FastAPI") -> List[StudioRouteInfo]:
    """
    Build route metadata for all registered routes.
    
    v0.5.2: Read-only route info for Studio.
    
    Args:
        app: FastAPI application
        
    Returns:
        List of StudioRouteInfo for all routes
    """
    routes_info = []
    
    for route in app.routes:
        # Get route path
        path = getattr(route, 'path', str(route))
        
        # Get HTTP methods
        methods = list(getattr(route, 'methods', []))
        if not methods:
            methods = ["GET"]  # Default for Mount routes
        
        # Get route name
        name = getattr(route, 'name', None)
        
        # Determine route classification
        is_studio = path.startswith("/studio")
        is_admin = path.startswith("/admin")
        is_ai = path.startswith("/ai")
        
        # Try to derive app label from path
        app_label = None
        if is_studio:
            app_label = "studio"
        elif is_admin:
            app_label = "admin"
        elif is_ai:
            app_label = "ai"
        elif path.startswith("/api/"):
            # Try to extract app from /api/{app}/... pattern
            parts = path.split("/")
            if len(parts) >= 3:
                app_label = parts[2]
        
        routes_info.append(StudioRouteInfo(
            path=path,
            methods=sorted(methods),
            name=name,
            app_label=app_label,
            is_studio=is_studio,
            is_admin=is_admin,
            is_ai=is_ai,
        ))
    
    # Sort by path for consistent ordering
    routes_info.sort(key=lambda r: r.path)
    
    return routes_info


# =============================================================================
# v0.5.4: Studio ↔ AI Integration Utilities
# =============================================================================

async def build_ai_context_export(app: "FastAPI") -> StudioAiContextExport:
    """
    Build AI context export bundle for Studio.
    
    v0.5.4: Creates a safe, secrets-stripped context bundle that external
    AI tools can consume. Uses existing AI context functions internally.
    
    Args:
        app: FastAPI application
        
    Returns:
        StudioAiContextExport with project meta, models, routes, tools
    """
    import aksara
    from aksara.conf import settings
    from aksara.registry import ModelRegistry
    
    # Get project metadata
    env = getattr(settings, 'env', None) or _get_environment()
    project = StudioAiProjectMeta(
        name=getattr(settings, 'app_title', 'Aksara App'),
        version=aksara.__version__,
        environment=env,
        debug=settings.debug,
    )
    
    # Build model summaries
    models = []
    all_models = ModelRegistry.all()
    for name, model_cls in all_models.items():
        try:
            meta = getattr(model_cls, '_meta', None)
            table_name = meta.table_name if meta else name.lower()
            app_label = meta.app_label if meta else None
            
            # Get field names
            field_names = []
            if meta and hasattr(meta, 'fields'):
                field_names = list(meta.fields.keys())
            
            # Check for timestamps
            has_timestamps = 'created_at' in field_names or 'updated_at' in field_names
            
            # Get primary key
            pk = 'id'
            if meta and hasattr(meta, 'primary_key'):
                pk = meta.primary_key
            
            models.append(StudioAiModelSummary(
                name=name,
                table_name=table_name,
                app_label=app_label,
                fields=field_names,
                primary_key=pk,
                has_timestamps=has_timestamps,
            ))
        except Exception:
            # Skip models that fail to introspect
            continue
    
    # Build route summaries (stripped down)
    routes = []
    for route in app.routes:
        path = getattr(route, 'path', str(route))
        methods = list(getattr(route, 'methods', ['GET']))
        name = getattr(route, 'name', None)
        
        # Skip internal/static routes
        if path.startswith('/openapi') or path.startswith('/docs') or path.startswith('/redoc'):
            continue
        
        # Check if authenticated (heuristic: has dependencies)
        is_authenticated = bool(getattr(route, 'dependencies', None))
        
        routes.append(StudioAiRouteSummary(
            path=path,
            methods=sorted(methods),
            name=name,
            is_authenticated=is_authenticated,
        ))
    
    routes.sort(key=lambda r: r.path)
    
    # Build available AI tools
    tools = _get_ai_tools_summary()
    
    # Get installed apps
    apps = list(settings.installed_apps) if settings.installed_apps else list(settings.apps)
    
    # Get migration status
    migration_status = StudioMigrationStatus()
    try:
        migrations_dir = getattr(settings, 'migrations_dir', 'migrations')
        from aksara.migrations import discover_all_migrations
        all_migrations = discover_all_migrations(Path(migrations_dir), include_internal=True)
        migration_status = StudioMigrationStatus(
            total=len(all_migrations),
            pending=len(all_migrations),  # Approximation
            applied=0,
        )
    except Exception:
        pass
    
    # Compute schema checksum
    checksum = compute_schema_checksum(list(all_models.values()))
    
    return StudioAiContextExport(
        project=project,
        models=models,
        routes=routes,
        tools=tools,
        apps=apps,
        migration_status=migration_status,
        schema_checksum=checksum,
    )


def _get_ai_tools_summary() -> List[StudioAiToolInfo]:
    """
    Get summary of available AI tools/endpoints.
    
    v0.5.4: Returns info about AI operations available.
    """
    tools = [
        StudioAiToolInfo(
            name="ai_query",
            description="Execute natural language queries against the database",
            endpoint="/ai/query",
            safe=True,  # Read-only
        ),
        StudioAiToolInfo(
            name="ai_plan",
            description="Generate structured plans for schema changes",
            endpoint="/ai/plan",
            safe=True,  # Planning is safe
        ),
        StudioAiToolInfo(
            name="ai_patch_validate",
            description="Validate patch operations before applying",
            endpoint="/ai/patch/validate",
            safe=True,  # Validation is safe
        ),
        StudioAiToolInfo(
            name="ai_patch_apply",
            description="Apply validated patches to the codebase",
            endpoint="/ai/patch/apply",
            safe=False,  # Modifies files
        ),
        StudioAiToolInfo(
            name="ai_codegen",
            description="Generate code from model specifications",
            endpoint="/ai/codegen",
            safe=True,  # Returns code, doesn't write
        ),
        StudioAiToolInfo(
            name="studio_context",
            description="Get full application context for AI",
            endpoint="/studio/ai/context",
            safe=True,
        ),
    ]
    return tools


def build_ai_schemas() -> StudioAiSchemas:
    """
    Build JSON schemas for AI operations.
    
    v0.5.4: Returns schemas AI agents can use to generate valid requests.
    """
    plan_schema = {}
    patch_schema = {}
    query_schema = {}
    codegen_schema = {}
    context_schema = {}
    
    try:
        from aksara.ai.planner import AiPlan
        plan_schema = AiPlan.model_json_schema()
    except Exception:
        pass
    
    try:
        from aksara.ai.patch import AiPatchRequest
        patch_schema = AiPatchRequest.model_json_schema()
    except Exception:
        pass
    
    try:
        from aksara.ai.query import AiQueryPlan
        query_schema = AiQueryPlan.model_json_schema()
    except Exception:
        pass
    
    try:
        from aksara.ai.codegen import AiCodegenRequest
        codegen_schema = AiCodegenRequest.model_json_schema()
    except Exception:
        pass
    
    try:
        from aksara.ai.context import AiFullContext
        context_schema = AiFullContext.model_json_schema()
    except Exception:
        pass
    
    return StudioAiSchemas(
        plan_schema=plan_schema,
        patch_schema=patch_schema,
        query_schema=query_schema,
        codegen_schema=codegen_schema,
        context_schema=context_schema,
    )


def build_ai_prompts() -> StudioAiPrompts:
    """
    Build prompt templates for AI interactions.
    
    v0.5.4: Returns pre-built prompt templates with placeholders.
    These are text templates only - no AI calls are made.
    """
    prompts = [
        StudioAiPromptTemplate(
            id="add-field",
            title="Add Model Field",
            description="Generate a plan to add a new field to an existing model",
            category="schema",
            placeholders=["context_json", "plan_schema", "model_name", "field_name", "field_type"],
            template="""You are an expert in the Aksara framework. Given the application context and plan schema below, generate a valid AiPlan JSON to add a new field to a model.

## Application Context
```json
{context_json}
```

## Plan Schema (your response must conform to this)
```json
{plan_schema}
```

## Task
Add a new field named "{field_name}" of type "{field_type}" to the "{model_name}" model.

## Requirements
1. Return ONLY valid JSON conforming to the plan schema
2. Include steps for: analyzing current schema, adding the field, generating migration
3. Set appropriate `depends_on` relationships between steps
4. Add helpful descriptions for each step

## Response
Return the AiPlan JSON:""",
        ),
        StudioAiPromptTemplate(
            id="refactor-model",
            title="Refactor Model",
            description="Generate a plan to refactor or split a model",
            category="schema",
            placeholders=["context_json", "plan_schema", "model_name", "refactor_description"],
            template="""You are an expert in the Aksara framework. Given the application context and plan schema below, generate a valid AiPlan JSON to refactor a model.

## Application Context
```json
{context_json}
```

## Plan Schema (your response must conform to this)
```json
{plan_schema}
```

## Task
Refactor the "{model_name}" model: {refactor_description}

## Requirements
1. Return ONLY valid JSON conforming to the plan schema
2. Include steps for: analysis, structural changes, data migration, cleanup
3. Ensure backward compatibility where possible
4. Set appropriate `depends_on` relationships

## Response
Return the AiPlan JSON:""",
        ),
        StudioAiPromptTemplate(
            id="fix-migrations",
            title="Fix Migration Issues",
            description="Generate a plan to resolve migration conflicts or drift",
            category="migration",
            placeholders=["context_json", "plan_schema", "migration_issues"],
            template="""You are an expert in the Aksara framework. Given the application context and migration issues below, generate a valid AiPlan JSON to resolve them.

## Application Context
```json
{context_json}
```

## Plan Schema (your response must conform to this)
```json
{plan_schema}
```

## Migration Issues
{migration_issues}

## Requirements
1. Return ONLY valid JSON conforming to the plan schema
2. Start with diagnostic steps to understand the current state
3. Propose safe, reversible changes where possible
4. Include verification steps

## Response
Return the AiPlan JSON:""",
        ),
        StudioAiPromptTemplate(
            id="natural-query",
            title="Natural Language Query",
            description="Convert natural language to a database query plan",
            category="query",
            placeholders=["context_json", "query_schema", "natural_query"],
            template="""You are an expert in the Aksara framework. Given the application context and query schema below, convert a natural language query into a valid AiQueryPlan JSON.

## Application Context
```json
{context_json}
```

## Query Plan Schema (your response must conform to this)
```json
{query_schema}
```

## Natural Language Query
"{natural_query}"

## Requirements
1. Return ONLY valid JSON conforming to the query schema
2. Use only models and fields that exist in the context
3. Apply appropriate filters, sorting, and pagination
4. Use safe, read-only operations

## Response
Return the AiQueryPlan JSON:""",
        ),
        StudioAiPromptTemplate(
            id="generate-model",
            title="Generate New Model",
            description="Generate code for a new model based on requirements",
            category="codegen",
            placeholders=["context_json", "codegen_schema", "model_requirements"],
            template="""You are an expert in the Aksara framework. Given the application context and codegen schema below, generate a valid AiCodegenRequest JSON to create a new model.

## Application Context
```json
{context_json}
```

## Codegen Schema (your response must conform to this)
```json
{codegen_schema}
```

## Model Requirements
{model_requirements}

## Requirements
1. Return ONLY valid JSON conforming to the codegen schema
2. Follow Aksara model conventions (use `aksara.fields`, inherit from `AksaraModel`)
3. Include appropriate field types, defaults, and validations
4. Add timestamps if applicable

## Response
Return the AiCodegenRequest JSON:""",
        ),
        StudioAiPromptTemplate(
            id="explain-schema",
            title="Explain Schema",
            description="Get an explanation of the current schema and relationships",
            category="general",
            placeholders=["context_json"],
            template="""You are an expert in the Aksara framework. Given the application context below, provide a clear explanation of the schema.

## Application Context
```json
{context_json}
```

## Task
Analyze and explain:
1. What models exist and their purposes
2. Key relationships between models
3. Notable patterns or conventions used
4. Any potential issues or improvements

## Response
Provide a clear, structured explanation:""",
        ),
    ]
    
    return StudioAiPrompts(
        prompts=prompts,
        version="1.0",
    )
