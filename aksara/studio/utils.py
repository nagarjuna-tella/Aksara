"""
Aksara Studio Utilities

Helper functions for building Studio responses.
Builds on top of existing AI context functions.

v0.5.0: Studio Core & Handshake
"""

from __future__ import annotations

import hashlib
import json
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
)

if TYPE_CHECKING:
    from fastapi import FastAPI


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
    
    Args:
        app: FastAPI application
        
    Returns:
        StudioContextSummary with counts and model list
    """
    from aksara.registry import ModelRegistry
    from aksara.conf import settings
    
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
    
    # Count migrations
    migrations_dir = Path(settings.migrations_dir)
    migration_files = list(migrations_dir.glob("*.sql")) if migrations_dir.exists() else []
    migration_count = len(migration_files)
    
    # Build checksums
    checksums = StudioChecksums(
        schema_checksum=compute_schema_checksum(model_classes),
        migrations_checksum=compute_migrations_checksum(),
        settings_checksum=compute_settings_checksum(),
        routes_checksum=compute_routes_checksum(app),
    )
    
    return StudioContextSummary(
        model_count=len(model_classes),
        viewset_count=viewset_count,
        route_count=route_count,
        ai_tool_count=ai_tool_count,
        migration_count=migration_count,
        pending_migrations=0,  # Would require DB check
        models=model_summaries,
        checksums=checksums,
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
