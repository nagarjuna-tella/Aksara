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
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from aksara.routing import iter_routes
from aksara.studio.models import (
    # v0.5.19: Agent Mode models
    AgentContextSection,
    AgentWorkflow,
    # v0.5.20: Agent Playbooks models
    AgentPlaybook,
    StudioAgentContext,
    StudioAgentPlaybookPromptRequest,
    StudioAgentPromptRequest,
    StudioAgentPromptResponse,
    StudioAiContextExport,
    StudioAiModelSummary,
    # v0.5.4: AI Integration models
    StudioAiProjectMeta,
    StudioAiPrompts,
    StudioAiPromptTemplate,
    StudioAiRouteSummary,
    StudioAiSchemas,
    StudioAiToolInfo,
    StudioAppMigrationSummary,
    StudioCapability,
    StudioChecksums,
    StudioContextSummary,
    StudioDatabaseStatus,
    StudioHandshake,
    StudioHealthResponse,
    StudioMigrationConflict,
    # v0.5.1: New models
    StudioMigrationStatus,
    StudioMigrationSummary,
    StudioModelSummary,
    StudioProjectInfo,
    StudioRouteInfo,
    # v0.5.2: Runtime models
    StudioRuntimeInfo,
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
    for route in iter_routes(app):
        route_info = {
            "path": getattr(route, "path", str(route)),
            "methods": sorted(getattr(route, "methods", None) or []),
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
    # Check environment variable first
    import os

    from aksara.conf import settings
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
    from aksara.conf import settings
    from aksara.migrations import discover_all_migrations
    from aksara.registry import ModelRegistry
    
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
    route_count = len(list(iter_routes(app)))
    
    # Count AI tools
    ai_registry = getattr(app, 'ai_registry', None)
    ai_tool_count = len(ai_registry) if ai_registry else 0
    
    # v0.5.1: Discover all migrations (not just .sql)
    migrations_dir = Path(settings.migrations_dir)
    all_migrations = discover_all_migrations(
        user_migrations_path=migrations_dir, include_internal=True,
    )
    migration_count = len(all_migrations)
    
    # v0.5.1: Get app count from settings
    app_count = len(settings.installed_apps) if settings.installed_apps else len(settings.apps)
    
    # v0.5.1: Get database status
    database_status = _get_database_status(app)
    
    # v0.5.45: Query DB for real applied/pending counts
    from aksara.migrations import get_applied_migrations
    applied_count = 0
    pending_count = migration_count
    last_applied_name: Optional[str] = None
    db = getattr(app, '_db', None) or getattr(app.state, 'db', None)
    if db:
        try:
            async with db.acquire() as conn:
                applied_names = await get_applied_migrations(conn)
                applied_count = len(applied_names)
                pending_count = max(0, migration_count - applied_count)
                if applied_names:
                    last_applied_name = applied_names[-1]
        except Exception:
            pass  # DB unavailable — fall back to 0 applied
    
    # v0.5.1: Build migration status
    migration_status = StudioMigrationStatus(
        total=migration_count,
        applied=applied_count,
        pending=pending_count,
        has_conflicts=False,  # Full conflict check is on /studio/migrations/summary
        last_applied=last_applied_name,
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
        pending_migrations=pending_count,
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
        build_migration_graph,
        check_migration_conflicts,
        discover_all_migrations,
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
    
    # v0.5.45: Count pending migrations using real DB query
    pending_migrations = 0
    try:
        from aksara.migrations import discover_all_migrations, get_applied_migrations
        migrations_dir = Path(settings.migrations_dir)
        all_migrations = discover_all_migrations(
            user_migrations_path=migrations_dir, include_internal=True,
        )
        total = len(all_migrations)
        db = getattr(app, '_db', None) or getattr(app.state, 'db', None)
        if db:
            async with db.acquire() as conn:
                applied = await get_applied_migrations(conn)
                pending_migrations = max(0, total - len(applied))
        else:
            pending_migrations = total  # No DB pool = assume all pending
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


def build_routes_info(app: Optional["FastAPI"] = None) -> List[StudioRouteInfo]:
    """
    Build route metadata for all registered routes.

    v0.5.2: Read-only route info for Studio.

    Args:
        app: FastAPI application. Returns an empty list when None.

    Returns:
        List of StudioRouteInfo for all routes
    """
    if app is None:
        return []

    routes_info = []

    for route in iter_routes(app):
        # Get route path
        path = getattr(route, 'path', str(route))
        
        # Get HTTP methods
        methods = list(getattr(route, 'methods', None) or [])
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
    for route in iter_routes(app):
        path = getattr(route, 'path', str(route))
        methods = list(getattr(route, 'methods', None) or ['GET'])
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
    
    # Build available AI tools from the actually-mounted /ai/* surface so
    # the export reflects live capabilities, not a hand-maintained list.
    tools = _get_ai_tools_summary(app)
    
    # Get installed apps
    apps = list(settings.installed_apps) if settings.installed_apps else list(settings.apps)
    
    # v0.5.45: Get migration status with real DB query
    migration_status = StudioMigrationStatus()
    try:
        migrations_dir = getattr(settings, 'migrations_dir', 'migrations')
        from aksara.migrations import discover_all_migrations, get_applied_migrations
        all_migrations = discover_all_migrations(
            user_migrations_path=Path(migrations_dir), include_internal=True,
        )
        total = len(all_migrations)
        applied_count = 0
        db = getattr(app, '_db', None) or getattr(app.state, 'db', None)
        if db:
            try:
                async with db.acquire() as conn:
                    applied_names = await get_applied_migrations(conn)
                    applied_count = len(applied_names)
            except Exception:
                pass
        migration_status = StudioMigrationStatus(
            total=total,
            applied=applied_count,
            pending=max(0, total - applied_count),
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


def _get_ai_tools_summary(app: Optional["FastAPI"] = None) -> List[StudioAiToolInfo]:
    """
    Build a summary of available AI tools by inspecting the actual mounted
    routes under ``/ai/*`` and ``/studio/ai/*``.

    Why dynamic: a hand-maintained list drifts as endpoints are added,
    renamed, or split (e.g. ``/ai/patch`` → ``/ai/patch/preview`` +
    ``/ai/patch/apply``).  Reading from ``app.routes`` keeps the export
    aligned with what's actually callable on this instance.

    Falls back to an empty list when no app is provided.
    """
    if app is None:
        return []

    # Heuristic: a tool is "safe" when it cannot mutate code/data.
    # Path-segment based, conservative — anything we don't recognise as
    # read-only is marked unsafe.
    UNSAFE_SEGMENTS = ("/apply", "/execute")
    # Explicit exceptions: paths whose final segment matches an unsafe keyword
    # but are actually read-only by contract (e.g. AiQueryPlan is defined as
    # a read-only plan that the caller may or may not act on).
    SAFE_PATH_EXCEPTIONS = {"/ai/query/execute"}

    def _is_safe(method: str, path: str) -> bool:
        m = (method or "GET").upper()
        if m in ("GET", "HEAD", "OPTIONS"):
            return True
        if path in SAFE_PATH_EXCEPTIONS:
            return True
        if any(seg in path for seg in UNSAFE_SEGMENTS):
            return False
        # Preview / schema / discovery paths are read-only by convention.
        if any(seg in path for seg in ("/preview", "/schema", "/context", "/tools", "/health", "/issues", "/diff")):
            return True
        return False

    def _tool_name(path: str) -> str:
        # /ai/query/execute → ai_query_execute, /studio/ai/context → studio_ai_context
        return path.strip("/").replace("/", "_").replace("-", "_") or "root"

    seen: set = set()
    tools: List[StudioAiToolInfo] = []
    for route in iter_routes(app):
        path = getattr(route, "path", "") or ""
        if not (path.startswith("/ai/") or path.startswith("/studio/ai/")):
            continue
        # Skip parameterised lookup helpers like /ai/tools/{tool_name}
        if "{" in path:
            continue
        methods = sorted(getattr(route, "methods", None) or ["GET"])
        for method in methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            key = (method, path)
            if key in seen:
                continue
            seen.add(key)
            description = (getattr(route, "name", None) or "").replace("_", " ").strip()
            if not description:
                description = f"{method} {path}"
            tools.append(StudioAiToolInfo(
                name=_tool_name(path) + (f"_{method.lower()}" if len(methods) > 1 else ""),
                description=description,
                endpoint=path,
                safe=_is_safe(method, path),
            ))

    tools.sort(key=lambda t: (t.endpoint, t.name))
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


# =============================================================================
# v0.5.10: Query Inspector & Profiler
# =============================================================================

def build_query_inspector(
    include_queries: bool = False,
    limit_batches: int = 20,
    limit_slow: int = 20,
) -> "StudioQueryInspector":
    """
    Build query inspector response.
    
    v0.5.10: Returns query tracing stats, recent batches, and slow queries.
    
    Args:
        include_queries: Whether to include full query lists in batches
        limit_batches: Max number of recent batches to return
        limit_slow: Max number of slow queries to return
        
    Returns:
        StudioQueryInspector with stats and data
    """
    from aksara.conf import settings
    from aksara.db.tracing import (
        get_recent_traces,
        get_top_slow_queries,
        get_trace_stats,
        is_tracing_enabled,
    )
    from aksara.studio.models import (
        StudioQueryBatch,
        StudioQueryInspector,
        StudioQueryStats,
        StudioQueryTrace,
    )
    
    enabled = is_tracing_enabled()
    slow_threshold = getattr(settings, 'db_trace_slow_threshold_ms', 100.0)
    
    # Get stats
    raw_stats = get_trace_stats()
    stats = StudioQueryStats(
        total_batches=raw_stats.get("total_batches", 0),
        total_queries=raw_stats.get("total_queries", 0),
        avg_queries_per_request=raw_stats.get("avg_queries_per_request", 0.0),
        total_slow_queries=raw_stats.get("total_slow_queries", 0),
        requests_with_slow_queries=raw_stats.get("requests_with_slow_queries", 0),
        requests_with_n_plus_one=raw_stats.get("requests_with_n_plus_one", 0),
    )
    
    # Get recent batches
    raw_batches = get_recent_traces(limit_batches)
    recent_batches = []
    for batch in raw_batches:
        batch_dict = batch.to_summary_dict() if not include_queries else batch.to_dict()
        
        # Convert queries if included
        queries = []
        if include_queries and hasattr(batch, 'queries'):
            for q in batch.queries:
                queries.append(StudioQueryTrace(
                    sql=q.sql,
                    params=q.params,
                    duration_ms=q.duration_ms,
                    rows_affected=q.rows_affected,
                    operation=q.operation,
                    table=q.table,
                    timestamp=q.timestamp,
                    stack_summary=q.stack_summary,
                    request_id=q.request_id,
                    tags=q.tags,
                    is_slow=q.is_slow,
                ))
        
        recent_batches.append(StudioQueryBatch(
            request_id=batch.request_id,
            path=batch.path,
            method=batch.method,
            status_code=batch.status_code,
            started_at=batch.started_at,
            ended_at=batch.ended_at,
            total_duration_ms=batch.total_duration_ms,
            total_queries=batch.total_queries,
            slow_queries=batch.slow_queries,
            n_plus_one_suspicions=batch.n_plus_one_suspicions,
            queries=queries,
        ))
    
    # Get top slow queries
    raw_slow = get_top_slow_queries(limit_slow)
    top_slow_queries = [
        StudioQueryTrace(
            sql=q.sql,
            params=q.params,
            duration_ms=q.duration_ms,
            rows_affected=q.rows_affected,
            operation=q.operation,
            table=q.table,
            timestamp=q.timestamp,
            stack_summary=q.stack_summary,
            request_id=q.request_id,
            tags=q.tags,
            is_slow=q.is_slow,
        )
        for q in raw_slow
    ]
    
    return StudioQueryInspector(
        enabled=enabled,
        slow_threshold_ms=slow_threshold,
        stats=stats,
        recent_batches=recent_batches,
        top_slow_queries=top_slow_queries,
    )


def build_query_batch_detail(request_id: str) -> Optional["StudioQueryBatch"]:
    """
    Build detailed query batch response for a specific request.
    
    v0.5.10: Returns full query list for a single request.
    
    Args:
        request_id: The request ID to look up
        
    Returns:
        StudioQueryBatch with full query list, or None if not found
    """
    from aksara.db.tracing import get_trace_by_request_id
    from aksara.studio.models import StudioQueryBatch, StudioQueryTrace
    
    batch = get_trace_by_request_id(request_id)
    if batch is None:
        return None
    
    queries = [
        StudioQueryTrace(
            sql=q.sql,
            params=q.params,
            duration_ms=q.duration_ms,
            rows_affected=q.rows_affected,
            operation=q.operation,
            table=q.table,
            timestamp=q.timestamp,
            stack_summary=q.stack_summary,
            request_id=q.request_id,
            tags=q.tags,
            is_slow=q.is_slow,
        )
        for q in batch.queries
    ]
    
    return StudioQueryBatch(
        request_id=batch.request_id,
        path=batch.path,
        method=batch.method,
        status_code=batch.status_code,
        started_at=batch.started_at,
        ended_at=batch.ended_at,
        total_duration_ms=batch.total_duration_ms,
        total_queries=batch.total_queries,
        slow_queries=batch.slow_queries,
        n_plus_one_suspicions=batch.n_plus_one_suspicions,
        queries=queries,
    )


# =============================================================================
# v0.5.11: AI Profiles & Provider Contracts
# =============================================================================

def _check_provider_ready(kind: str, settings) -> bool:
    """
    Check if a provider is ready (SDK installed + credentials configured).
    
    v0.5.14: Used by Studio to show "Client Ready?" status.
    
    Args:
        kind: Provider kind (openai, anthropic, etc.)
        settings: Application settings
        
    Returns:
        True if both SDK and credentials are available
    """
    import os
    
    # Check SDK availability
    sdk_available = False
    if kind in ("openai", "azure"):
        try:
            import openai  # noqa: F401
            sdk_available = True
        except ImportError:
            sdk_available = False
    elif kind == "anthropic":
        try:
            import anthropic  # noqa: F401
            sdk_available = True
        except ImportError:
            sdk_available = False
    else:
        # Unknown provider kind - assume ready if configured
        sdk_available = True
    
    if not sdk_available:
        return False
    
    # Check credentials
    if kind == "openai":
        return bool(os.environ.get("OPENAI_API_KEY"))
    elif kind == "azure":
        return all([
            os.environ.get("AZURE_OPENAI_ENDPOINT"),
            os.environ.get("AZURE_OPENAI_API_KEY"),
        ])
    elif kind == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    
    # Unknown kind - assume ready
    return True


def build_ai_profile_set_summary(app: "FastAPI") -> "StudioAiProfileSetSummary":
    """
    Build AI profile set summary for Studio.
    
    v0.5.11: Gathers all AI provider profiles and builds a summary.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        StudioAiProfileSetSummary with provider and model info
    """
    from aksara.ai.providers import (
        build_default_ai_profile_set,
        get_ai_provider_registry,
    )
    from aksara.conf import settings
    from aksara.studio.models import (
        StudioAiModelProfileSummary,
        StudioAiProfileSetSummary,
        StudioAiProviderSummary,
    )
    
    # Check if profiles are enabled
    ai_profiles_enabled = getattr(settings, 'ai_profiles_enabled', True)
    
    if not ai_profiles_enabled:
        return StudioAiProfileSetSummary(
            enabled=False,
            providers=[],
            default_provider=None,
            total_models=0,
            environment=None,
            version="disabled",
        )
    
    # Try to get registry from app first
    registry = get_ai_provider_registry(app)
    
    # If registry is empty, use default profile set from settings
    if len(registry) == 0:
        profile_set = build_default_ai_profile_set(settings)
    else:
        profile_set = registry.get_profile_set()
    
    # Build provider summaries
    providers = []
    for provider in profile_set.providers:
        # Build model summaries
        models = [
            StudioAiModelProfileSummary(
                name=model.name,
                display_name=model.display_name,
                kind=model.kind,
                max_input_tokens=model.max_input_tokens,
                max_output_tokens=model.max_output_tokens,
                supports_tools=model.supports_tools,
                supports_streaming=model.supports_streaming,
                supports_vision=getattr(model, 'supports_vision', False),
                tags=model.tags,
            )
            for model in provider.models
        ]
        
        # Check if this is an example provider
        is_example = provider.metadata.get('_example', False)
        
        # v0.5.14: Check if provider is ready (SDK + credentials)
        client_ready = _check_provider_ready(provider.kind, settings)
        
        providers.append(StudioAiProviderSummary(
            name=provider.name,
            display_name=provider.display_name,
            kind=provider.kind,
            model_count=len(provider.models),
            default_model=provider.default_model,
            has_custom_base_url=provider.base_url is not None,
            is_example=is_example,
            client_ready=client_ready,
            models=models,
        ))
    
    return StudioAiProfileSetSummary(
        enabled=True,
        providers=providers,
        default_provider=profile_set.default_provider,
        total_models=profile_set.total_models(),
        environment=profile_set.environment,
        version=profile_set.version,
    )


def build_ai_secrets_info() -> "StudioAiSecretsInfo":
    """
    Build AI secrets info for Studio.
    
    v0.5.11: Lists env var names and whether they are configured.
    NEVER includes actual secret values.
    
    Returns:
        StudioAiSecretsInfo with secret hints
    """
    import os

    from aksara.ai.providers import build_secret_hints_from_settings
    from aksara.conf import settings
    from aksara.studio.models import StudioAiSecretHint, StudioAiSecretsInfo
    
    # Get secret hints from settings
    raw_hints = build_secret_hints_from_settings(settings)
    
    # Build Studio hints with configured status
    secrets = []
    configured_count = 0
    
    for hint in raw_hints:
        # Check if env var is set (but don't expose the value!)
        is_configured = os.environ.get(hint.env_var) is not None
        if is_configured:
            configured_count += 1
        
        secrets.append(StudioAiSecretHint(
            provider_name=hint.provider_name,
            env_var=hint.env_var,
            required=hint.required,
            description=hint.description,
            is_configured=is_configured,
        ))
    
    return StudioAiSecretsInfo(
        secrets=secrets,
        configured_count=configured_count,
        total_count=len(secrets),
    )


def build_ai_profile_health(app: "FastAPI") -> "StudioAiProfileHealth":
    """
    Build AI profile health status for Studio.
    
    v0.5.12: Validates AI profile configuration and returns health status.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        StudioAiProfileHealth with validation results
    """
    from aksara.ai.providers import (
        build_default_ai_profile_set,
        validate_profile_set,
    )
    from aksara.conf import settings
    from aksara.studio.models import (
        StudioAiProfileHealth,
        StudioAiProfileIssue,
    )
    
    # Check if profiles are enabled
    ai_profiles_enabled = getattr(settings, 'ai_profiles_enabled', True)
    
    if not ai_profiles_enabled:
        return StudioAiProfileHealth(
            is_valid=True,
            error_count=0,
            warning_count=0,
            info_count=1,
            issues=[
                StudioAiProfileIssue(
                    id="ai_profiles_disabled",
                    kind="info",
                    severity="info",
                    message="AI profiles are disabled",
                    field="ai_profiles_enabled",
                )
            ],
            provider_count=0,
            model_count=0,
            default_provider=None,
        )
    
    # Prefer the live app registry — same priority as build_ai_profile_set_summary.
    from aksara.ai.providers import get_ai_provider_registry
    registry = get_ai_provider_registry(app)
    if len(registry) > 0:
        profile_set = registry.get_profile_set()
    else:
        profile_set = build_default_ai_profile_set(settings)
    health = validate_profile_set(profile_set)
    
    # Convert issues to Studio format
    studio_issues = [
        StudioAiProfileIssue(
            id=issue.id,
            kind=issue.kind,
            severity=issue.severity,
            message=issue.message,
            provider_name=issue.provider_name,
            model_name=issue.model_name,
            field=issue.field,
        )
        for issue in health.issues
    ]
    
    return StudioAiProfileHealth(
        is_valid=health.is_valid,
        error_count=health.error_count,
        warning_count=health.warning_count,
        info_count=health.info_count,
        issues=studio_issues,
        provider_count=len(profile_set.providers),
        model_count=profile_set.total_models(),
        default_provider=profile_set.default_provider,
    )


# =============================================================================
# v0.5.13: AI Hints
# =============================================================================

def build_ai_hints(app: "FastAPI") -> "StudioAiHintSet":
    """
    Build AI hints information for Studio.
    
    v0.5.13: Extracts route-level AI hints from the application.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        StudioAiHintSet with all discovered hints
    """
    from aksara.ai.hints import build_ai_hint_set
    from aksara.studio.models import (
        StudioAiHintSet,
        StudioAiRouteHint,
    )
    
    hint_set = build_ai_hint_set(app)
    
    # Convert to Studio format
    studio_hints = [
        StudioAiRouteHint(
            view_name=h.view_name,
            route_name=h.route_name,
            path=h.path,
            methods=h.methods,
            title=h.title,
            description=h.description,
            usage_kind=h.usage_kind,
            risk_level=h.risk_level,
            example_prompt=h.example_prompt,
            example_input=h.example_input,
            example_output=h.example_output,
            recommended_model=h.recommended_model,
            recommended_provider=h.recommended_provider,
        )
        for h in hint_set.routes
    ]
    
    return StudioAiHintSet(
        routes=studio_hints,
        total_count=hint_set.total_count,
        read_only_count=hint_set.read_only_count,
        write_count=hint_set.write_count,
        admin_count=hint_set.admin_count,
        low_risk_count=hint_set.low_risk_count,
        medium_risk_count=hint_set.medium_risk_count,
        high_risk_count=hint_set.high_risk_count,
    )


# =============================================================================
# v0.5.19: Agent Mode — Context Builder
# =============================================================================


def _section_size_kb(data: Any) -> float:
    """Compute approximate size of a data payload in KB."""
    try:
        return len(json.dumps(data, default=str)) / 1024.0
    except (TypeError, ValueError):
        return 0.0


def _make_section(key: str, title: str, description: str, data: Any) -> AgentContextSection:
    """Create an AgentContextSection with auto-computed size."""
    return AgentContextSection(
        key=key,
        title=title,
        description=description,
        data=data,
        size_kb=round(_section_size_kb(data), 2),
    )


async def build_agent_context(app: "FastAPI") -> StudioAgentContext:
    """
    Gather all available project context for an LLM agent.

    v0.5.19: Collects 9 sections:
    - project_info: app name, version, environment, debug flag
    - models: registered model names, fields, relations
    - routes: all API endpoints with methods
    - migrations: migration status per app
    - diagnostics: latest self-diagnostics report
    - ai_profiles: configured AI providers and models
    - ai_hints: per-route AI hints and risk levels
    - db_queries: recent query inspector stats
    - schema_checksum: current schema fingerprint

    v0.5.21: Adds 2 more sections (11 total):
    - query_stats: aggregate slow/avg/top-slow query statistics
    - schema_analysis: deep model inspection with comments

    Returns:
        StudioAgentContext with all sections populated.
    """
    import aksara
    from aksara.conf import settings
    from aksara.registry import ModelRegistry
    aksara_ver = aksara.__version__

    sections: List[AgentContextSection] = []

    # 1. project_info
    project_data = {
        "app_title": getattr(settings, "app_title", None) or "Aksara App",
        "app_version": getattr(settings, "app_version", None) or "0.0.0",
        "debug": getattr(settings, "debug", False),
        "environment": _get_environment(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "aksara_version": aksara_ver,
    }
    sections.append(_make_section(
        "project_info",
        "Project Info",
        "Application name, version, environment, and runtime details",
        project_data,
    ))

    # 2. models
    try:
        all_models = ModelRegistry.all()
        models_data = []
        for name, model_cls in all_models.items():
            fields_info = []
            for fname, fobj in getattr(model_cls, '_fields', {}).items():
                fields_info.append({
                    "name": fname,
                    "type": getattr(fobj, 'field_type', type(fobj).__name__),
                })
            models_data.append({
                "name": name,
                "table_name": getattr(model_cls, '_table_name', name.lower()),
                "field_count": len(fields_info),
                "fields": fields_info,
                "has_relations": any(
                    getattr(f, 'is_relation', False) for f in getattr(model_cls, '_fields', {}).values()
                ),
            })
    except Exception:
        models_data = []
    sections.append(_make_section(
        "models",
        "Models",
        "Registered database models with fields and relations",
        models_data,
    ))

    # 3. routes
    try:
        routes_list = build_routes_info(app)
        routes_data = [r.model_dump() for r in routes_list]
    except Exception:
        routes_data = []
    sections.append(_make_section(
        "routes",
        "Routes",
        "All registered API endpoints with methods and labels",
        routes_data,
    ))

    # 4. migrations
    try:
        mig_summary = await build_migration_summary(app)
        migrations_data = mig_summary.model_dump()
    except Exception:
        migrations_data = {}
    sections.append(_make_section(
        "migrations",
        "Migrations",
        "Database migration status per application",
        migrations_data,
    ))

    # 5. diagnostics
    try:
        from aksara.diagnostics import run_all_checks
        diag_report = await run_all_checks()
        diagnostics_data = diag_report.model_dump(mode="json")
    except Exception:
        diagnostics_data = {}
    sections.append(_make_section(
        "diagnostics",
        "Diagnostics",
        "Latest self-diagnostics report with issues and stats",
        diagnostics_data,
    ))

    # 6. ai_profiles
    try:
        profiles = build_ai_profile_set_summary(app)
        ai_profiles_data = profiles.model_dump()
    except Exception:
        ai_profiles_data = {}
    sections.append(_make_section(
        "ai_profiles",
        "AI Profiles",
        "Configured AI providers, models, and readiness status",
        ai_profiles_data,
    ))

    # 7. ai_hints
    try:
        hints = build_ai_hints(app)
        ai_hints_data = hints.model_dump()
    except Exception:
        ai_hints_data = {}
    sections.append(_make_section(
        "ai_hints",
        "AI Hints",
        "Per-route AI hints with risk levels and example prompts",
        ai_hints_data,
    ))

    # 8. db_queries
    try:
        inspector = build_query_inspector(include_queries=False)
        db_queries_data = inspector.model_dump()
    except Exception:
        db_queries_data = {}
    sections.append(_make_section(
        "db_queries",
        "DB Queries",
        "Recent database query stats and slow-query detection",
        db_queries_data,
    ))

    # 9. schema_checksum
    try:
        model_classes = list(ModelRegistry.all().values())
        checksum = compute_schema_checksum(model_classes)
    except Exception:
        checksum = "unknown"
    sections.append(_make_section(
        "schema_checksum",
        "Schema Checksum",
        "SHA-256 fingerprint of the current model schema",
        {"checksum": checksum},
    ))

    # 10. query_stats (v0.5.21)
    try:
        from aksara.inspectors.queries import get_query_stats as _get_qstats
        qstats = _get_qstats(limit_slow=5)
        query_stats_data = qstats.model_dump()
    except Exception:
        query_stats_data = {}
    sections.append(_make_section(
        "query_stats",
        "Query Stats",
        "Aggregate query statistics: slow count, avg duration, top slow queries",
        query_stats_data,
    ))

    # 11. schema_analysis (v0.5.21)
    try:
        from aksara.inspectors.models import inspect_all_models as _inspect_all
        all_inspections = _inspect_all()
        schema_analysis_data = {
            "total_models": len(all_inspections),
            "total_fields": sum(m.num_fields for m in all_inspections),
            "total_relationships": sum(m.num_relationships for m in all_inspections),
            "models": [
                {
                    "name": m.name,
                    "table": m.table_name,
                    "fields": m.num_fields,
                    "relationships": m.num_relationships,
                    "has_timestamps": m.has_timestamps,
                    "comments": m.comments,
                }
                for m in all_inspections
            ],
        }
    except Exception:
        schema_analysis_data = {}
    sections.append(_make_section(
        "schema_analysis",
        "Schema Analysis",
        "Deep model inspection: fields, relationships, constraints, and auto-comments",
        schema_analysis_data,
    ))

    # 12. semantic_index (v0.5.22)
    try:
        from aksara.search.indexers import build_full_index
        search_index = build_full_index(app)
        semantic_index_data = search_index.stats()
    except Exception:
        semantic_index_data = {}
    sections.append(_make_section(
        "semantic_index",
        "Semantic Index",
        "Cross-referenced search index: models, routes, settings, playbooks, migrations, queries",
        semantic_index_data,
    ))

    total_size = round(sum(s.size_kb for s in sections), 2)

    return StudioAgentContext(
        generated_at=datetime.now(timezone.utc),
        total_sections=len(sections),
        total_size_kb=total_size,
        sections=sections,
    )


def build_agent_context_summary(app: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Return lightweight section metadata for the Context tab.

    Computes only trivially-cheap sections (project_info, models, routes,
    schema_checksum, ai_profiles, ai_hints) so the tab load stays fast.
    Sections that require expensive subsystems — async (migrations, diagnostics)
    or CPU/IO-intensive (db_queries, query_stats, schema_analysis,
    semantic_index) — are listed as placeholders (size_kb=None) with accurate
    descriptions of what they contain during full agent runs.
    """
    import json as _json

    sections: List[Dict[str, Any]] = []

    def _add(name: str, title: str, description: str, data: Any) -> None:
        size_kb = round(len(_json.dumps(data)) / 1024, 2)
        sections.append({"name": name, "title": title, "description": description, "size_kb": size_kb})

    def _placeholder(name: str, title: str, description: str) -> None:
        sections.append({"name": name, "title": title, "description": description, "size_kb": None})

    # 1. project_info — same payload as full context (project_info section)
    try:
        import aksara as _aksara
        from aksara.conf import settings
        _add("project_info", "Project Info", "Application name, version, environment, and runtime details", {
            "app_title": getattr(settings, "app_title", None) or "Aksara App",
            "app_version": getattr(settings, "app_version", None) or "0.0.0",
            "debug": getattr(settings, "debug", False),
            "environment": _get_environment(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "aksara_version": _aksara.__version__,
        })
    except Exception:
        _placeholder("project_info", "Project Info", "Application name, version, environment, and runtime details")

    # 2. models — same payload as full context (per-model fields list)
    try:
        from aksara.registry import ModelRegistry
        models_data = []
        for name, model_cls in ModelRegistry.all().items():
            fields_info = []
            for fname, fobj in getattr(model_cls, '_fields', {}).items():
                fields_info.append({
                    "name": fname,
                    "type": getattr(fobj, 'field_type', type(fobj).__name__),
                })
            models_data.append({
                "name": name,
                "table_name": getattr(model_cls, '_table_name', name.lower()),
                "field_count": len(fields_info),
                "fields": fields_info,
                "has_relations": any(
                    getattr(f, 'is_relation', False) for f in getattr(model_cls, '_fields', {}).values()
                ),
            })
        _add("models", "Models", "Registered database models with fields and relations", models_data)
    except Exception:
        _placeholder("models", "Models", "Registered database models with fields and relations")

    # 3. routes — same payload as full context (r.model_dump() per route)
    try:
        routes = build_routes_info(app)
        _add("routes", "Routes", "All registered API endpoints with methods and labels",
             [r.model_dump() for r in routes])
    except Exception:
        _placeholder("routes", "Routes", "All registered API endpoints with methods and labels")

    # 4. migrations — async; built on agent run
    _placeholder("migrations", "Migrations", "Database migration status per application (built on agent run)")

    # 5. diagnostics — async; built on agent run
    _placeholder("diagnostics", "Diagnostics", "Latest self-diagnostics report (built on agent run)")

    # 6. ai_profiles
    try:
        profiles = build_ai_profile_set_summary(app)
        _add("ai_profiles", "AI Profiles", "Configured AI providers and readiness status",
             profiles.model_dump())
    except Exception:
        _placeholder("ai_profiles", "AI Profiles", "Configured AI providers and readiness status")

    # 7. ai_hints
    try:
        hints = build_ai_hints(app)
        _add("ai_hints", "AI Hints", "Per-route AI hints with risk levels",
             hints.model_dump())
    except Exception:
        _placeholder("ai_hints", "AI Hints", "Per-route AI hints with risk levels")

    # 8. db_queries — excluded: QueryInspector traversal can be non-trivial
    _placeholder("db_queries", "DB Queries",
                 "Recent database query stats and slow-query detection")

    # 9. schema_checksum — cheap: SHA-256 over model field names only
    try:
        from aksara.registry import ModelRegistry as _MR
        _checksum = compute_schema_checksum(list(_MR.all().values()))
        _add("schema_checksum", "Schema Checksum",
             "SHA-256 fingerprint of the current model schema",
             {"checksum": _checksum})
    except Exception:
        _add("schema_checksum", "Schema Checksum",
             "SHA-256 fingerprint of the current model schema", {})

    # 10. query_stats — excluded: may involve DB round-trips
    _placeholder("query_stats", "Query Stats",
                 "Aggregate query statistics: slow count, avg duration, top slow queries")

    # 11–12. excluded: schema inspection and full index rebuild are expensive
    _placeholder("schema_analysis", "Schema Analysis",
                 "Deep model inspection: fields, relationships, constraints, and auto-comments")
    _placeholder("semantic_index", "Semantic Index",
                 "Cross-referenced search index: models, routes, settings, playbooks, migrations, queries")

    return sections


# =============================================================================
# v0.5.19: Agent Mode — Prompt Generator
# =============================================================================


def build_agent_prompt(
    request: StudioAgentPromptRequest,
    context: StudioAgentContext,
) -> StudioAgentPromptResponse:
    """
    Generate a system prompt for an LLM agent based on selected context.

    v0.5.19: Filters sections by request.selected_sections (empty = all),
    builds a structured system prompt with the goal and section data,
    recommends temperature and model, and estimates token count.

    Args:
        request: The prompt generation request with goal and section selection.
        context: The full agent context to draw from.

    Returns:
        StudioAgentPromptResponse with assembled prompt and recommendations.
    """
    # Filter sections
    if request.selected_sections:
        selected = [
            s for s in context.sections
            if s.key in request.selected_sections
        ]
    else:
        selected = list(context.sections)

    # Build system prompt
    parts: List[str] = []

    if request.custom_system_prompt:
        parts.append(request.custom_system_prompt)
        parts.append("")

    parts.append("You are an expert assistant for an Aksara web application.")
    parts.append(f"Goal: {request.goal}")
    parts.append("")

    for section in selected:
        parts.append(f"## {section.title}")
        parts.append(f"{section.description}")
        parts.append("")
        try:
            data_str = json.dumps(section.data, indent=2, default=str)
        except (TypeError, ValueError):
            data_str = str(section.data)
        parts.append(f"```json\n{data_str}\n```")
        parts.append("")

    system_prompt = "\n".join(parts)

    # Determine temperature
    has_high_risk = False
    for section in selected:
        if section.key == "ai_hints":
            high_count = 0
            if isinstance(section.data, dict):
                high_count = section.data.get("high_risk_count", 0)
            if high_count > 0:
                has_high_risk = True
                break
        if section.key == "diagnostics":
            if isinstance(section.data, dict):
                stats = section.data.get("stats", {})
                if stats.get("errors", 0) > 0:
                    has_high_risk = True
                    break

    temperature = 0.3 if has_high_risk else 0.5

    # Pick recommended model from AI profiles
    recommended_model = "gpt-4o"
    for section in selected:
        if section.key == "ai_profiles" and isinstance(section.data, dict):
            providers = section.data.get("providers", [])
            for provider in providers:
                if isinstance(provider, dict) and provider.get("client_ready"):
                    models = provider.get("models", [])
                    if models:
                        first_model = models[0]
                        if isinstance(first_model, dict):
                            recommended_model = first_model.get("name", recommended_model)
                        break
            break

    # Token estimate (rough word count)
    tokens_estimate = len(system_prompt.split())

    return StudioAgentPromptResponse(
        system_prompt=system_prompt,
        recommended_temperature=temperature,
        recommended_model=recommended_model,
        tokens_estimate=tokens_estimate,
    )


# =============================================================================
# v0.5.20: Agent Playbooks — Prompt from Playbook
# =============================================================================


def build_agent_prompt_from_playbook(
    playbook: AgentPlaybook,
    user_goal: Optional[str],
    selected_sections: Optional[List[str]],
    custom_system_prompt: Optional[str],
    context: StudioAgentContext,
) -> StudioAgentPromptResponse:
    """
    Generate a system prompt driven by a playbook recipe.

    v0.5.20: Builds a playbook-aware prompt header and delegates to
    the standard build_agent_prompt() pipeline.

    Steps:
    1. Use playbook.default_sections if selected_sections is not provided.
    2. Use playbook.default_goal_template if user_goal is empty.
    3. Build a structured playbook header with label, kind, risk,
       usage, and step listing.
    4. Combine custom_system_prompt (if any) + playbook header
       into a single prefix.
    5. Delegate to build_agent_prompt() for final assembly.

    Args:
        playbook: The AgentPlaybook to use.
        user_goal: Optional user-provided goal (overrides template).
        selected_sections: Optional section keys (overrides defaults).
        custom_system_prompt: Optional extra prefix.
        context: The full agent context.

    Returns:
        StudioAgentPromptResponse with prompt and recommendations.
    """
    # Resolve goal — use default template if no user goal
    goal = user_goal.strip() if user_goal and user_goal.strip() else playbook.default_goal_template

    # Resolve sections — use playbook defaults if not overridden
    sections = selected_sections if selected_sections is not None else list(playbook.default_sections)

    # Build playbook header
    header_parts: List[str] = []
    header_parts.append(f"# Playbook: {playbook.label}")
    header_parts.append(f"Kind: {playbook.kind}")
    header_parts.append(f"Risk: {playbook.risk_level}  |  Usage: {playbook.usage_kind}")
    header_parts.append(f"Category: {playbook.category}")
    header_parts.append("")
    header_parts.append(f"{playbook.description}")
    header_parts.append("")

    if playbook.steps:
        header_parts.append("## Steps")
        for i, step in enumerate(playbook.steps, 1):
            header_parts.append(f"{i}. **{step.title}** — {step.description}")
            if step.estimated_impact:
                header_parts.append(f"   Impact: {step.estimated_impact}")
        header_parts.append("")

    if playbook.notes:
        header_parts.append(f"Note: {playbook.notes}")
        header_parts.append("")

    playbook_header = "\n".join(header_parts)

    # Combine custom + playbook header
    prefix_parts: List[str] = []
    if custom_system_prompt and custom_system_prompt.strip():
        prefix_parts.append(custom_system_prompt.strip())
        prefix_parts.append("")
    prefix_parts.append(playbook_header)
    combined_prefix = "\n".join(prefix_parts)

    # Delegate to standard prompt builder
    request = StudioAgentPromptRequest(
        goal=goal,
        selected_sections=sections,
        custom_system_prompt=combined_prefix,
    )
    return build_agent_prompt(request, context)


# =============================================================================
# v0.5.21: Query & Model Inspector Builders
# =============================================================================


def build_query_plan(sql: str, analyze: bool = False) -> "StudioQueryPlanResult":
    """
    Build a Studio query plan response.

    v0.5.21: Delegates to aksara.inspectors.queries.explain_query.
    """
    from aksara.inspectors.queries import explain_query
    from aksara.studio.models import StudioQueryPlanResult

    result = explain_query(sql=sql, analyze=analyze)
    return StudioQueryPlanResult(
        sql=result.sql,
        plan=result.plan,
        estimated_cost=result.estimated_cost,
        plan_type=result.plan_type,
        warnings=result.warnings,
        provenance=result.provenance,
        analyze_executed=result.analyze_executed,
    )


async def build_query_plan_async(
    sql: str,
    analyze: bool = False,
) -> Any:
    """Build a Studio query plan without blocking the application event loop."""

    from aksara.inspectors.queries import explain_query_async
    from aksara.studio.models import StudioQueryPlanResult

    result = await explain_query_async(sql=sql, analyze=analyze)
    return StudioQueryPlanResult(**result.model_dump())


def build_model_inspector(model_name: str) -> Optional["StudioModelInspectorSummary"]:
    """
    Inspect a single model by name and return a Studio response.

    v0.5.21: Wraps aksara.inspectors.models.inspect_model.

    Returns None if the model is not found in the registry.
    """
    from aksara.inspectors.models import inspect_model
    from aksara.registry import ModelRegistry
    from aksara.studio.models import (
        StudioModelInspectorConstraint,
        StudioModelInspectorField,
        StudioModelInspectorRelationship,
        StudioModelInspectorSummary,
    )

    try:
        model_cls = ModelRegistry.get(model_name)
    except KeyError:
        return None

    result = inspect_model(model_cls)
    return _convert_inspector_to_studio(result)


def build_all_models_inspector() -> "StudioModelInspectorAll":
    """
    Inspect all registered models and return a Studio response.

    v0.5.21: Wraps aksara.inspectors.models.inspect_all_models.
    """
    from aksara.inspectors.models import inspect_all_models
    from aksara.studio.models import StudioModelInspectorAll

    results = inspect_all_models()
    studio_models = [_convert_inspector_to_studio(r) for r in results]

    return StudioModelInspectorAll(
        models=studio_models,
        total_count=len(studio_models),
        total_fields=sum(m.num_fields for m in studio_models),
        total_relationships=sum(m.num_relationships for m in studio_models),
    )


def _convert_inspector_to_studio(result) -> "StudioModelInspectorSummary":
    """Convert an inspectors.ModelInspectorSummary to Studio Pydantic model."""
    from aksara.studio.models import (
        StudioModelInspectorConstraint,
        StudioModelInspectorField,
        StudioModelInspectorRelationship,
        StudioModelInspectorSummary,
    )

    fields = [
        StudioModelInspectorField(
            name=f.name,
            column_name=f.column_name,
            field_type=f.field_type,
            python_type=f.python_type,
            nullable=f.nullable,
            primary_key=f.primary_key,
            unique=f.unique,
            has_default=f.has_default,
            default_repr=f.default_repr,
            max_length=f.max_length,
            choices=f.choices,
            is_relation=f.is_relation,
            ai_description=f.ai_description,
            ai_sensitive=f.ai_sensitive,
            auto_generated=f.auto_generated,
        )
        for f in result.fields
    ]

    relationships = [
        StudioModelInspectorRelationship(
            field_name=r.field_name,
            kind=r.kind,
            target_model=r.target_model,
            target_table=r.target_table,
            on_delete=r.on_delete,
            through_table=r.through_table,
            related_name=r.related_name,
            nullable=r.nullable,
        )
        for r in result.relationships
    ]

    constraints = [
        StudioModelInspectorConstraint(
            kind=c.kind,
            columns=c.columns,
            name=c.name,
            description=c.description,
        )
        for c in result.constraints
    ]

    return StudioModelInspectorSummary(
        name=result.name,
        table_name=result.table_name,
        app_label=result.app_label,
        num_fields=result.num_fields,
        num_relationships=result.num_relationships,
        has_timestamps=result.has_timestamps,
        pk_field=result.pk_field,
        pk_type=result.pk_type,
        fields=fields,
        relationships=relationships,
        constraints=constraints,
        ai_description=result.ai_description,
        ai_agent_exposed=result.ai_agent_exposed,
        create_table_sql=result.create_table_sql,
        comments=result.comments,
    )


# =============================================================================
# v0.5.22: Semantic Search & AI Index
# =============================================================================

# Module-level search index singleton (lazy-built)
_search_index_cache: Optional[Any] = None


def _get_search_index(app: Optional[Any] = None, *, force_rebuild: bool = False) -> Any:
    """Get or build the search index singleton."""
    global _search_index_cache
    from aksara.search.indexers import build_full_index

    if _search_index_cache is None or force_rebuild:
        _search_index_cache = build_full_index(app)
    return _search_index_cache


def build_search_index_info(app: Optional[Any] = None) -> "StudioSearchIndexInfo":
    """
    Build search index info for the Studio API.

    v0.5.22: Returns index stats (document counts, kinds, vocabulary size).
    """
    from aksara.studio.models import StudioSearchIndexInfo

    index = _get_search_index(app)
    stats = index.stats()

    return StudioSearchIndexInfo(
        total_documents=stats["total_documents"],
        by_kind=stats["by_kind"],
        vocabulary_size=stats["vocabulary_size"],
        kinds_available=index.kinds(),
        embedding_provider="local_tfidf",
    )


def build_search_results(
    query: str,
    app: Optional[Any] = None,
    *,
    top_k: int = 10,
    kind: Optional[str] = None,
    kinds: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    min_score: float = 0.0,
    mode: str = "hybrid",
) -> "StudioSearchResultSet":
    """
    Run a search query and return Studio-formatted results.

    v0.5.22: Builds the index if needed, runs search, wraps in Pydantic models.
    """
    from aksara.studio.models import StudioSearchResultItem, StudioSearchResultSet

    index = _get_search_index(app)
    results = index.search(
        query, top_k=top_k, kind=kind, kinds=kinds,
        tags=tags, min_score=min_score, mode=mode,
    )

    items = [
        StudioSearchResultItem(
            id=r.document.id,
            kind=r.document.kind,
            title=r.document.title,
            summary=r.document.summary,
            score=round(r.score, 4),
            highlights=r.highlights,
            match_type=r.match_type,
            source=r.document.source,
            metadata=r.document.metadata,
            tags=r.document.tags,
        )
        for r in results
    ]

    return StudioSearchResultSet(
        query=query,
        total_results=len(items),
        results=items,
        mode=mode,
        index_size=index.size,
    )


# =============================================================================
# v0.5.23: Agentic Workflows — Plans, Not Pushes
# =============================================================================

def build_agent_workflow(
    goal: str,
    *,
    playbook: Optional[str] = None,
    include_diagnostics: bool = True,
    include_search: bool = True,
    search_query: Optional[str] = None,
    search_limit: int = 10,
    diagnostics_limit: int = 10,
) -> AgentWorkflow:
    """Forward lazily so importing workflows does not re-enter this module."""
    from aksara.ai.workflows import build_agent_workflow as build

    return build(
        goal,
        playbook=playbook,
        include_diagnostics=include_diagnostics,
        include_search=include_search,
        search_query=search_query,
        search_limit=search_limit,
        diagnostics_limit=diagnostics_limit,
    )


def summarize_agent_workflow(workflow: AgentWorkflow) -> str:
    """Forward lazily so either public import order remains valid."""
    from aksara.ai.workflows import summarize_agent_workflow as summarize

    return summarize(workflow)


def workflow_stats(workflow: AgentWorkflow) -> Dict[str, Any]:
    """Forward lazily so either public import order remains valid."""
    from aksara.ai.workflows import workflow_stats as stats

    return stats(workflow)

# =============================================================================
# v0.5.25: AI Hub & Unified Provider System
# =============================================================================


def build_ai_hub_providers() -> "StudioAiProvidersSummary":
    """
    Build AI hub providers summary.

    v0.5.25: Detects all providers via env, pings them, returns status.
    """
    from aksara.ai.providers_unified import detect_all_providers, get_active_provider
    from aksara.studio.models import StudioAiProvidersSummary, StudioAiProviderStatus

    active = get_active_provider()
    detected = detect_all_providers()

    statuses: list = []
    for prov in detected:
        reachable = False
        error_msg = None

        if prov.is_configured():
            try:
                ping_result = prov.ping()
                reachable = ping_result.get("ok", False) if isinstance(ping_result, dict) else bool(ping_result)
                if not reachable:
                    error_msg = ping_result.get("message") if isinstance(ping_result, dict) else None
            except Exception as exc:
                error_msg = str(exc)

        safe = prov.to_safe_dict()
        statuses.append(StudioAiProviderStatus(
            provider=prov.provider,
            configured=prov.is_configured(),
            reachable=reachable,
            model=safe.get("model") or "",
            base_url=safe.get("base_url") or "",
            error=error_msg,
        ))

    configured_count = sum(1 for s in statuses if s.configured)

    return StudioAiProvidersSummary(
        active_provider=active.provider if active else None,
        active_model=active.model if active else "",
        providers=statuses,
        configured_count=configured_count,
        total_count=len(statuses),
    )


def build_ai_hub_provider_save(
    provider: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    extra: Optional[Dict] = None,
    save_to: str = "env",
) -> "StudioAiProviderSaveResponse":
    """
    Save a provider config to .env or provider.json.

    v0.5.25: Writes config to disk.
    """
    from aksara.ai.providers_unified import UnifiedAiProvider
    from aksara.studio.models import StudioAiProviderSaveResponse

    try:
        prov = UnifiedAiProvider(
            provider=provider,
            base_url=base_url or "",
            api_key=api_key or "",
            model=model or "",
            extra=extra or {},
        )

        if save_to == "json":
            path = prov.save_to_json()
        else:
            path = prov.save_to_env_file()

        return StudioAiProviderSaveResponse(
            saved=True,
            provider=provider,
            file_path=str(path),
            message=f"Provider '{provider}' saved to {path}",
        )
    except Exception as exc:
        return StudioAiProviderSaveResponse(
            saved=False,
            provider=provider,
            message=f"Failed to save: {exc}",
        )


def build_ai_hub_provider_ping(
    provider_key: Optional[str] = None,
) -> "StudioAiProviderPingResponse":
    """
    Ping a specific provider or the active one.

    v0.5.25: Tests connectivity and returns latency.
    """
    import time

    from aksara.ai.hub_settings import load_aihub_settings, resolve_defaults
    from aksara.ai.providers_unified import UnifiedAiProvider
    from aksara.studio.models import StudioAiProviderPingResponse

    hub = load_aihub_settings()
    prov: Optional[UnifiedAiProvider] = None

    if provider_key:
        configured_kinds = {p.kind for p in hub.configured_providers()}
        if provider_key in configured_kinds:
            pc = hub.get_provider(provider_key)
            if pc:
                prov = pc.to_unified_provider()
    else:
        active_key = _resolve_effective_chat_provider(hub)
        if active_key:
            configured_kinds = {p.kind for p in hub.configured_providers()}
            if active_key in configured_kinds:
                pc = hub.get_provider(active_key)
                if pc:
                    prov = pc.to_unified_provider()

    if prov is None:
        return StudioAiProviderPingResponse(
            provider=provider_key or "unknown",
            reachable=False,
            error="No provider configured",
        )

    start = time.monotonic()
    try:
        ping_result = prov.ping()
        reachable = ping_result.get("ok", False) if isinstance(ping_result, dict) else bool(ping_result)
        latency = (time.monotonic() - start) * 1000
        ping_msg = ping_result.get("message") if isinstance(ping_result, dict) else None
        return StudioAiProviderPingResponse(
            provider=prov.provider,
            reachable=reachable,
            latency_ms=round(latency, 2),
            model=prov.model or "",
            error=None if reachable else (ping_msg or "Ping returned False"),
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return StudioAiProviderPingResponse(
            provider=prov.provider,
            reachable=False,
            latency_ms=round(latency, 2),
            model=prov.model or "",
            error=str(exc),
        )


def build_ai_hub_agent_run(
    prompt: str,
    app: Optional[Any] = None,
    *,
    provider_key: Optional[str] = None,
    model_override: Optional[str] = None,
    include_context: bool = True,
    context_sections: Optional[List[str]] = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> "StudioAiAgentRunResponse":
    """
    Run the AI agent with a user prompt.

    v0.5.25: Uses the unified provider to generate a response.
    """
    from aksara.ai.providers_unified import UnifiedAiProvider
    from aksara.studio.models import StudioAiAgentRunResponse

    # Resolve provider and model from AI Hub settings so this endpoint is
    # consistent with the routing table, overview, and provider tests that all
    # read from the same AiHubSettings source of truth.
    hub = _get_hub_settings()
    configured_kinds = {p.kind for p in hub.configured_providers()}

    prov: Optional[UnifiedAiProvider] = None
    effective_model: Optional[str] = model_override

    if provider_key:
        # Explicit provider override from the UI dropdown.
        if provider_key in configured_kinds:
            pc = hub.get_provider(provider_key)
            if pc:
                prov = pc.to_unified_provider()
                if not effective_model:
                    # Use chat default model when the selected provider matches
                    # the pinned chat provider; otherwise fall back to provider's own default.
                    if hub.defaults.chat_provider == provider_key:
                        effective_model = hub.defaults.chat_model or pc.model
                    else:
                        effective_model = pc.model
    else:
        # Blank selection: use Hub chat defaults (the same source as the routing table).
        chat_kind = hub.defaults.chat_provider
        if chat_kind and chat_kind in configured_kinds:
            pc = hub.get_provider(chat_kind)
            if pc and pc.is_configured:
                prov = pc.to_unified_provider()
                effective_model = model_override or hub.defaults.chat_model or pc.model
        else:
            # No pinned provider — fall back to first configured provider using
            # _resolve_effective_chat_provider for consistency with the routing table.
            # Do NOT use hub.defaults.chat_model here: it may have been saved for a
            # different provider, producing an incoherent pairing (e.g. claude-3-opus
            # sent to openai). Let the resolved provider use its own default model.
            configured = hub.configured_providers()
            if configured:
                pc = configured[0]
                prov = pc.to_unified_provider()
                effective_model = model_override or pc.model

    if prov is None or not prov.is_configured():
        return StudioAiAgentRunResponse(
            provider=provider_key or "none",
            model=model_override or "",
            error="No AI provider configured. Set up a provider in AI Hub.",
        )

    # Apply effective model (hub default or explicit override).
    if effective_model:
        prov = UnifiedAiProvider(
            provider=prov.provider,
            base_url=prov.base_url,
            api_key=prov.api_key,
            model=effective_model,
            extra=prov.extra,
        )

    # Build system prompt with real project context when requested.
    # context_sections controls which sections to include; None means all.
    system_parts: list = []
    if include_context:
        wanted = set(context_sections) if context_sections else {"app_info", "models", "routes"}
        ctx_lines = [
            "You are an AI assistant for an Aksara web application.",
            "Answer questions about the project, suggest improvements, and help with code generation.",
            "",
        ]
        if "app_info" in wanted:
            try:
                from aksara.conf import settings as _s
                env = getattr(_s, "env", None) or "unknown"
                apps = list(getattr(_s, "installed_apps", None) or getattr(_s, "apps", []))
                ctx_lines += [
                    "## Application",
                    f"Environment: {env}",
                    f"Installed apps: {', '.join(apps) if apps else 'unknown'}",
                    "",
                ]
            except Exception:
                pass
        if "models" in wanted:
            try:
                from aksara.registry import ModelRegistry
                model_names = list(ModelRegistry.all().keys())
                if model_names:
                    ctx_lines += [
                        "## Models",
                        ", ".join(model_names[:30]) + ("..." if len(model_names) > 30 else ""),
                        "",
                    ]
            except Exception:
                pass
        if "routes" in wanted and app is not None:
            try:
                api_routes = [
                    r for r in build_routes_info(app)
                    if r.path.startswith("/api/") and not r.is_studio and not r.is_ai
                ]
                if api_routes:
                    ctx_lines.append("## API Routes")
                    for r in api_routes[:20]:
                        ctx_lines.append(f"- {', '.join(r.methods)} {r.path}")
                    if len(api_routes) > 20:
                        ctx_lines.append(f"  ... and {len(api_routes) - 20} more")
                    ctx_lines.append("")
            except Exception:
                pass
        system_parts.append("\n".join(ctx_lines))

    full_prompt = prompt
    if system_parts:
        full_prompt = "\n".join(system_parts) + "\n\nUser: " + prompt

    try:
        client = prov.get_llm_client()
        output = client.generate(
            full_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return StudioAiAgentRunResponse(
            provider=prov.provider,
            model=prov.model,
            output=output,
            tokens_estimated=len(output.split()) * 2,  # rough estimate
        )
    except Exception as exc:
        return StudioAiAgentRunResponse(
            provider=prov.provider,
            model=prov.model,
            error=str(exc),
        )


def build_ai_hub_ollama_models(base_url: Optional[str] = None) -> "StudioOllamaModelsResponse":
    """Discover available models from a running Ollama instance.

    v0.5.43: Thin wrapper around OllamaAdapter.list_models() that queries the
    Ollama /api/tags endpoint.  Returns running=False + empty list when Ollama
    is not reachable so callers can degrade gracefully.

    Args:
        base_url: Optional override for Ollama base URL.  Defaults to the value
            stored in the environment (OLLAMA_BASE_URL) or localhost:11434.

    Returns:
        StudioOllamaModelsResponse with running status, model list, and the URL
        that was actually queried.
    """
    from aksara.ai.llm_clients.ollama_adapter import OllamaAdapter
    from aksara.ai.providers_unified import UnifiedAiProvider
    from aksara.studio.models import StudioOllamaModelsResponse

    provider = UnifiedAiProvider.from_env(provider="ollama")
    if base_url:
        provider = provider.model_copy(update={"base_url": base_url})
    adapter = OllamaAdapter(provider)
    running = adapter.is_available()
    models = adapter.list_models() if running else []
    return StudioOllamaModelsResponse(
        running=running,
        models=models,
        base_url=provider.base_url or "http://localhost:11434",
    )


# =============================================================================
# v0.5.26: Gap Analysis Builder Functions
# =============================================================================


def build_studio_gap_issue(issue: Any) -> "StudioGapIssue":
    """Convert a :class:`~aksara.gapanalysis.GapIssue` to its Studio representation."""
    from aksara.studio.models import StudioGapFixCommand, StudioGapIssue

    return StudioGapIssue(
        category=issue.category,
        severity=issue.severity,
        code=issue.code,
        title=issue.title,
        message=issue.message,
        hint=issue.hint,
        fix_commands=[
            StudioGapFixCommand(
                description=cmd.description,
                command=cmd.command,
                env_required=cmd.env_required,
            )
            for cmd in issue.fix_commands
        ],
        meta=issue.meta,
        is_blocking=issue.is_blocking,
    )


def build_studio_gap_analysis_report(report: Any) -> "StudioGapAnalysisReport":
    """Convert a :class:`~aksara.gapanalysis.GapAnalysisReport` to its Studio representation."""
    from aksara.studio.models import (
        StudioGapAnalysisReport,
        StudioGapAnalysisStats,
    )

    stats = StudioGapAnalysisStats(
        critical=report.stats.critical,
        error=report.stats.error,
        warning=report.stats.warning,
        info=report.stats.info,
        total=report.stats.total,
        has_blocking=report.stats.has_blocking,
        overall_status=report.stats.overall_status,
    )

    issues = [build_studio_gap_issue(i) for i in report.issues]

    ts = report.timestamp.isoformat() if hasattr(report.timestamp, "isoformat") else str(report.timestamp)

    return StudioGapAnalysisReport(
        issues=issues,
        stats=stats,
        categories_checked=list(report.categories_checked),
        summary_line=report.summary_line,
        timestamp=ts,
        duration_ms=report.duration_ms,
        system=dict(report.system),
    )


async def run_and_build_gap_analysis(
    categories: Optional[List[str]] = None,
) -> "StudioGapAnalysisReport":
    """
    Run the gap analysis engine and return a Studio-formatted report.

    Parameters
    ----------
    categories:
        Optional list of category names to check.  ``None`` means all.
    """
    from aksara.gapanalysis import run_gap_analysis

    # Cast categories to the Literal type if provided
    report = await run_gap_analysis(categories=categories)  # type: ignore[arg-type]
    return build_studio_gap_analysis_report(report)


# =============================================================================
# v0.5.28: AI Hub 2.0 Utilities
# =============================================================================


def _get_hub_settings():
    """Lazy-load AiHubSettings to avoid circular imports."""
    from aksara.ai.hub_settings import load_aihub_settings
    return load_aihub_settings()


def _resolve_effective_chat_provider(hub: Any) -> Optional[str]:
    """Return the concrete provider kind that will handle chat/agent requests.

    When ``hub.defaults.chat_provider`` is pinned, returns it directly.
    When auto-routing (chat_provider=None), returns the first configured
    provider's kind — the same deterministic order used by
    ``build_ai_hub_agent_run`` — so that the routing table always shows the
    actual execution provider rather than ``None``.
    """
    if hub.defaults.chat_provider:
        return hub.defaults.chat_provider
    configured = hub.configured_providers()
    return configured[0].kind if configured else None


def build_aihub_status() -> "AiHubStatus":
    """Build the AI Hub status response."""
    from aksara.studio.models import AiHubOnboardingStatus, AiHubStatus

    hub = _get_hub_settings()
    configured = hub.configured_providers()
    configured_kinds = {p.kind for p in configured}
    warnings: List[str] = []

    # "ready" requires a chat_model and a valid chat provider.
    # Auto-routing (chat_provider=None) is now fully coherent because flow resolution
    # automatically falls back to the resolved provider's own default model.
    effective_chat_provider = _resolve_effective_chat_provider(hub)
    chat_provider_ok = (
        effective_chat_provider is not None
        and effective_chat_provider in configured_kinds
    )
    if not configured:
        overall = "disabled"
    elif hub.defaults.chat_model and chat_provider_ok:
        overall = "ready"
    else:
        overall = "partial"

    # Warnings for common issues
    if configured and not hub.defaults.embeddings_model:
        warnings.append("No embedding model configured — semantic search will use local TF-IDF fallback")
    if configured and not hub.defaults.chat_model:
        warnings.append("No chat model default set — agents will not work")
    if (hub.defaults.chat_provider and
            hub.defaults.chat_provider not in configured_kinds):
        warnings.append(
            f"Chat provider '{hub.defaults.chat_provider}' is set as default but not configured"
            " — agents will not work"
        )

    # Onboarding status.
    # keys_entered: a provider in configured_providers() has already passed its
    # is_configured check (api_key for cloud providers, base_url for Ollama),
    # so presence in the list IS the "credentials set" signal — no api_key
    # field check needed.
    onboarding = AiHubOnboardingStatus(
        providers_selected=len(configured) > 0,
        keys_entered=len(configured) > 0,
        providers_tested=False,  # not tracked; requires explicit ping history
        defaults_set=hub.defaults.chat_model is not None and chat_provider_ok,
        sample_query_run=False,  # not tracked; requires run-history storage
    )
    # completed is derived directly from overall so the two signals cannot diverge.
    onboarding.completed = (overall == "ready")

    return AiHubStatus(
        overall=overall,
        active_provider=_resolve_effective_chat_provider(hub),
        configured_count=len(configured),
        total_count=len(hub.providers),
        defaults=hub.defaults.model_dump(),
        onboarding=onboarding,
        warnings=warnings,
    )


def build_aihub_providers() -> "AiHubProvidersResponse":
    """Build the AI Hub providers list response.

    v0.5.45: Now pings each configured provider so the ``reachable`` and
    ``error`` fields are populated.  Previously both fields were left as
    ``None``, which caused the Studio UI to display every configured
    provider as ⚠ "Configured" (status-warn) even when the provider was
    fully reachable.  Uses the same ``pc.to_unified_provider().ping()``
    pattern as :func:`build_aihub_test`.
    """
    from aksara.studio.models import AiHubProvider, AiHubProvidersResponse

    hub = _get_hub_settings()
    items: List["AiHubProvider"] = []
    for p in hub.providers:
        # v0.5.45: Ping configured providers so reachable/error are accurate.
        reachable: Optional[bool] = None
        error: Optional[str] = None
        is_actually_configured = p.enabled and p.is_configured
        if is_actually_configured:
            try:
                unified = p.to_unified_provider()
                ping_result = unified.ping()
                reachable = ping_result.get("ok", False)
                if not reachable:
                    error = ping_result.get("message")
            except Exception as exc:
                reachable = False
                error = str(exc)

        items.append(AiHubProvider(
            kind=p.kind,
            enabled=p.enabled,
            configured=is_actually_configured,
            reachable=reachable,
            model=p.model or "",
            base_url=p.base_url or "",
            modes=p.get_supported_modes(),
            error=error,
        ))

    return AiHubProvidersResponse(
        providers=items,
        active_provider=_resolve_effective_chat_provider(hub),
        configured_count=sum(1 for i in items if i.configured),
        total_count=len(items),
    )


def build_aihub_models() -> "AiHubModelsResponse":
    """Build the AI Hub models response.

    v0.5.43: For ollama providers, uses live model discovery instead of
    hardcoded defaults so the Available Models table reflects what is
    actually running.
    """
    from aksara.ai.hub_settings import _PROVIDER_DEFAULT_MODELS
    from aksara.studio.models import AiHubModel, AiHubModelsResponse

    hub = _get_hub_settings()
    models: List["AiHubModel"] = []

    for p in hub.providers:
        if not (p.enabled and p.is_configured):
            continue

        # v0.5.43: Live discovery for Ollama — use the saved base_url from AI Hub
        # config rather than environment state so a non-default host works correctly.
        if p.kind == "ollama":
            try:
                from aksara.ai.llm_clients.ollama_adapter import OllamaAdapter
                from aksara.ai.providers_unified import UnifiedAiProvider

                provider = UnifiedAiProvider(
                    provider="ollama",
                    base_url=p.base_url or "http://localhost:11434",
                )
                adapter = OllamaAdapter(provider)
                if adapter.is_available():
                    live_models = adapter.list_models()
                    if live_models:
                        embed_candidates = [m for m in live_models if any(k in m.lower() for k in ("embed", "nomic"))]
                        chat_model = live_models[0]
                        embed_model = embed_candidates[0] if embed_candidates else live_models[-1]
                        for mode in ("chat", "code"):
                            models.append(AiHubModel(model_id=chat_model, provider="ollama", mode=mode))
                        models.append(AiHubModel(model_id=embed_model, provider="ollama", mode="embeddings"))
                        continue
            except Exception:
                pass  # Fall through to hardcoded defaults

        defaults = _PROVIDER_DEFAULT_MODELS.get(p.kind, {})
        for mode, model_name in defaults.items():
            if model_name:
                models.append(AiHubModel(
                    model_id=model_name,
                    provider=p.kind,
                    mode=mode,
                ))

    return AiHubModelsResponse(
        defaults=hub.defaults.model_dump(),
        models=models,
    )


def build_aihub_configure(
    provider: str,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    enabled: bool = True,
) -> "AiHubConfigureResponse":
    """Configure a provider (non-secret fields)."""
    from aksara.studio.models import AiHubConfigureResponse

    try:
        from aksara.ai.hub_settings import (
            AnthropicConfig,
            AzureOpenAIConfig,
            CustomHttpConfig,
            OllamaConfig,
            OpenAIConfig,
            ProviderConfig,
            load_aihub_settings,
            save_aihub_settings,
        )

        config_map = {
            "openai": OpenAIConfig,
            "azure": AzureOpenAIConfig,
            "anthropic": AnthropicConfig,
            "ollama": OllamaConfig,
            "custom": CustomHttpConfig,
        }
        if provider not in config_map:
            return AiHubConfigureResponse(ok=False, message=f"Unknown provider: {provider}", provider=provider)

        # Load from file only — env overlay is skipped so we never bake
        # env-sourced API keys (masked as "****") into the persisted config.
        hub = load_aihub_settings(include_env=False)
        existing = hub.get_provider(provider)  # type: ignore[arg-type]

        # Resolve a clear ("") vs. leave-unchanged (None) for each field.
        # base_url: "" resets to the provider's Pydantic default (which is the
        # canonical API URL for that provider, e.g. "https://api.openai.com/v1").
        # model: "" → None is safe because model is Optional[str] on all providers.
        def _resolve_base_url(raw: Optional[str]) -> Optional[str]:
            """None → unchanged sentinel; "" → provider's default base URL."""
            if raw is None:
                return None  # caller passes unchanged sentinel through
            if raw:
                return raw
            field = config_map[provider].model_fields.get("base_url")
            return field.default if (field is not None and field.default is not None) else None

        resolved_base_url = _resolve_base_url(base_url)
        resolved_model = (model or None) if model is not None else None  # "" → None

        if existing is not None:
            inner_cfg = getattr(existing, provider, None)
            if inner_cfg is None:
                inner_cfg = config_map[provider]()
                setattr(existing, provider, inner_cfg)
            if base_url is not None:
                inner_cfg.base_url = resolved_base_url
            if model is not None:
                inner_cfg.model = resolved_model
            existing.enabled = enabled
        else:
            kwargs: Dict[str, Any] = {}
            if base_url is not None:
                kwargs["base_url"] = resolved_base_url
            if model is not None:
                kwargs["model"] = resolved_model
            cfg = config_map[provider](**kwargs)
            hub.providers.append(
                ProviderConfig(kind=provider, enabled=enabled, **{provider: cfg})  # type: ignore[arg-type]
            )

        save_aihub_settings(hub)
        return AiHubConfigureResponse(
            ok=True,
            message=f"Provider '{provider}' configured (non-secret fields)",
            provider=provider,
        )
    except Exception as exc:
        return AiHubConfigureResponse(ok=False, message=str(exc), provider=provider)


def build_aihub_configure_secret(
    provider: str,
    api_key: str,
) -> "AiHubConfigureResponse":
    """Configure a provider's API key (secret handling, no logging).

    When ``api_key`` is an empty string the stored key is *removed* from the
    .env file and from os.environ.  This is the only Studio path for clearing
    a previously-saved credential.
    """
    from aksara.studio.models import AiHubConfigureResponse

    try:
        if not api_key:
            from aksara.ai.hub_settings import clear_provider_api_key
            clear_provider_api_key(provider)
            return AiHubConfigureResponse(
                ok=True,
                message=f"API key for '{provider}' cleared",
                provider=provider,
            )

        from aksara.ai.providers_unified import UnifiedAiProvider

        p = UnifiedAiProvider(provider=provider, api_key=api_key)  # type: ignore[arg-type]
        p.save_to_env_file()
        return AiHubConfigureResponse(
            ok=True,
            message=f"API key for '{provider}' saved to .env",
            provider=provider,
        )
    except Exception as exc:
        return AiHubConfigureResponse(ok=False, message=str(exc), provider=provider)


def build_aihub_defaults(
    chat_model: Optional[str] = None,
    chat_provider: Optional[str] = None,
    code_model: Optional[str] = None,
    code_provider: Optional[str] = None,
    embeddings_model: Optional[str] = None,
    embeddings_provider: Optional[str] = None,
) -> "AiHubConfigureResponse":
    """Update default model assignments."""
    from aksara.studio.models import AiHubConfigureResponse

    try:
        from aksara.ai.hub_settings import load_aihub_settings, save_aihub_settings

        # Load from file only — same reason as build_aihub_configure: avoid
        # baking env-sourced secrets (masked) into the persisted defaults.
        hub = load_aihub_settings(include_env=False)
        # For models: "" clears (→ None); None means "don't change".
        # For providers: same — "" clears the stored override back to unset;
        # None (element absent from request) means "don't change".
        if chat_model is not None:
            hub.defaults.chat_model = chat_model or None
        if chat_provider is not None:
            hub.defaults.chat_provider = chat_provider or None  # type: ignore[assignment]
        if code_model is not None:
            hub.defaults.code_model = code_model or None
        if code_provider is not None:
            hub.defaults.code_provider = code_provider or None  # type: ignore[assignment]
        if embeddings_model is not None:
            hub.defaults.embeddings_model = embeddings_model or None
        if embeddings_provider is not None:
            hub.defaults.embeddings_provider = embeddings_provider or None  # type: ignore[assignment]

        save_aihub_settings(hub)
        return AiHubConfigureResponse(
            ok=True,
            message="Default models updated",
        )
    except Exception as exc:
        return AiHubConfigureResponse(ok=False, message=str(exc))


def build_aihub_test(provider: str) -> "AiHubTestResponse":
    """Test a single provider's connectivity."""
    import time

    from aksara.studio.models import AiHubTestResponse

    hub = _get_hub_settings()
    pc = hub.get_provider(provider)  # type: ignore[arg-type]

    configured_kinds = {p.kind for p in hub.configured_providers()}
    if pc is None or provider not in configured_kinds:
        return AiHubTestResponse(
            provider=provider,
            reachable=False,
            error=f"Provider '{provider}' is not configured or is disabled",
        )

    try:
        unified = pc.to_unified_provider()
        start = time.monotonic()
        ping_result = unified.ping()
        elapsed = (time.monotonic() - start) * 1000

        return AiHubTestResponse(
            provider=provider,
            reachable=ping_result.get("ok", False),
            latency_ms=round(elapsed, 1),
            model=unified.model or "",
            modes=pc.get_supported_modes(),
            error=ping_result.get("message") if not ping_result.get("ok") else None,
        )
    except Exception as exc:
        return AiHubTestResponse(
            provider=provider,
            reachable=False,
            error=str(exc),
        )


def build_aihub_routes(reachable_kinds: Optional[set] = None) -> "AiHubRoutes":
    """Build the AI Hub routing table.

    Args:
        reachable_kinds: Set of provider kinds that passed a live ping.  When
            supplied, routes whose pinned provider is configured but unreachable
            are marked ``unreachable`` rather than ``ok``.  Pass ``None`` to skip
            the reachability check (configuration-only validation).
    """
    from aksara.studio.models import AiHubRouteMapping, AiHubRoutes

    hub = _get_hub_settings()
    routes: List["AiHubRouteMapping"] = []
    warnings: List[str] = []

    configured_kinds = {p.kind for p in hub.configured_providers()}

    def _route_status(provider: Optional[str], feature: str) -> tuple:
        """Return (status, warning_or_None) for a route whose model field is set."""
        if provider and provider not in configured_kinds:
            return "missing", f"Provider '{provider}' is not configured — {feature} will not work"
        if not provider and not configured_kinds:
            return "missing", f"No AI provider configured — {feature} will not work"
        # Reachability check: only when the caller supplied live ping results.
        if reachable_kinds is not None and provider and provider not in reachable_kinds:
            return "unreachable", f"Provider '{provider}' is configured but currently unreachable — {feature} may fail"
        if reachable_kinds is not None and not provider:
            # Auto-routing: at least one configured provider must be reachable.
            if not (configured_kinds & reachable_kinds):
                return "unreachable", f"No configured provider is currently reachable — {feature} may fail"
        return "ok", None

    # Agents — always resolve a concrete provider so the routing table matches
    # what build_ai_hub_agent_run will actually execute against.
    if hub.defaults.chat_model:
        effective_chat_provider = _resolve_effective_chat_provider(hub)
        _status, _warn = _route_status(effective_chat_provider, "agents")
        # For auto-routing the stored chat_model may belong to a different
        # provider; show the resolved provider's own configured model instead so
        # the routing table reflects what will actually run.
        if hub.defaults.chat_provider is None:
            resolved_pc = hub.get_provider(effective_chat_provider) if effective_chat_provider else None
            effective_chat_model = (resolved_pc.model if (resolved_pc and resolved_pc.model)
                                    else hub.defaults.chat_model)
        else:
            effective_chat_model = hub.defaults.chat_model
        routes.append(AiHubRouteMapping(
            feature="agents",
            provider=effective_chat_provider,
            model=effective_chat_model,
            status=_status,
            warning=_warn,
        ))
    else:
        routes.append(AiHubRouteMapping(
            feature="agents",
            status="missing",
            warning="No chat model configured — agents disabled",
        ))
        warnings.append("Agents: no chat model")

    # Playbooks
    if hub.defaults.code_model:
        _status, _warn = _route_status(hub.defaults.code_provider, "playbooks")
        routes.append(AiHubRouteMapping(
            feature="playbooks",
            provider=hub.defaults.code_provider,
            model=hub.defaults.code_model,
            status=_status,
            warning=_warn,
        ))
    else:
        routes.append(AiHubRouteMapping(
            feature="playbooks",
            status="fallback",
            warning="No code model configured — playbooks will use chat model if available",
        ))

    # Search embeddings
    if hub.defaults.embeddings_model:
        _status, _warn = _route_status(hub.defaults.embeddings_provider, "search")
        routes.append(AiHubRouteMapping(
            feature="search_embeddings",
            provider=hub.defaults.embeddings_provider,
            model=hub.defaults.embeddings_model,
            status=_status,
            warning=_warn,
        ))
    else:
        routes.append(AiHubRouteMapping(
            feature="search_embeddings",
            status="fallback",
            warning="No embedding model — using local TF-IDF fallback",
        ))
        warnings.append("Search: local TF-IDF fallback")

    # Diagnostics suggestions — same effective-provider resolution as agents
    if hub.defaults.chat_model:
        effective_diag_provider = _resolve_effective_chat_provider(hub)
        _status, _warn = _route_status(effective_diag_provider, "diagnostics")
        if hub.defaults.chat_provider is None:
            resolved_pc = hub.get_provider(effective_diag_provider) if effective_diag_provider else None
            effective_diag_model = (resolved_pc.model if (resolved_pc and resolved_pc.model)
                                    else hub.defaults.chat_model)
        else:
            effective_diag_model = hub.defaults.chat_model
        routes.append(AiHubRouteMapping(
            feature="diagnostics",
            provider=effective_diag_provider,
            model=effective_diag_model,
            status=_status,
            warning=_warn,
        ))
    else:
        routes.append(AiHubRouteMapping(
            feature="diagnostics",
            status="missing",
            warning="No chat model — diagnostic suggestions disabled",
        ))

    return AiHubRoutes(routes=routes, warnings=warnings)
