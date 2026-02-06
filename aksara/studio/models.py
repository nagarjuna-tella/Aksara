"""
Aksara Studio Models

Pydantic models for Studio API responses.

v0.5.0: Studio Core & Handshake
v0.5.1: Studio Core Polish - richer summaries, migration endpoint
v0.5.2: Runtime & DX - runtime info, routes endpoint
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StudioCapability(str, Enum):
    """
    Capabilities that Studio can use when interacting with the app.
    
    These indicate what operations Studio is allowed to perform.
    """
    
    # Core capabilities
    READ_SCHEMA = "read_schema"
    READ_DATA = "read_data"
    WRITE_DATA = "write_data"
    
    # Migration capabilities
    READ_MIGRATIONS = "read_migrations"
    APPLY_MIGRATIONS = "apply_migrations"
    
    # AI capabilities
    AI_TOOLS = "ai_tools"
    AI_QUERY = "ai_query"
    AI_CODEGEN = "ai_codegen"
    AI_PATCH = "ai_patch"
    AI_PLANNER = "ai_planner"
    
    # Admin capabilities
    ADMIN_ACCESS = "admin_access"
    
    # Debug capabilities
    DEBUG_PANELS = "debug_panels"


class StudioDatabaseStatus(BaseModel):
    """
    Database connection and health status.
    """
    
    connected: bool = Field(
        ..., 
        description="Whether database is currently connected"
    )
    dialect: str = Field(
        default="postgresql",
        description="Database dialect (e.g., postgresql)"
    )
    pool_size: int = Field(
        default=0,
        description="Current connection pool size"
    )
    pool_available: int = Field(
        default=0,
        description="Available connections in pool"
    )
    latency_ms: Optional[float] = Field(
        default=None,
        description="Last measured query latency in milliseconds"
    )
    last_error: Optional[str] = Field(
        default=None,
        description="Last database error message if any"
    )


# =============================================================================
# v0.5.1: Migration Summary Models
# =============================================================================

class StudioMigrationStatus(BaseModel):
    """
    Migration status summary for context endpoint.
    
    v0.5.1: Provides quick migration health overview.
    """
    
    total: int = Field(
        default=0,
        description="Total number of migrations discovered"
    )
    applied: int = Field(
        default=0,
        description="Number of applied migrations"
    )
    pending: int = Field(
        default=0,
        description="Number of pending migrations"
    )
    has_conflicts: bool = Field(
        default=False,
        description="Whether migration conflicts exist"
    )
    last_applied: Optional[str] = Field(
        default=None,
        description="Name of the last applied migration"
    )


class StudioAppMigrationSummary(BaseModel):
    """
    Per-app migration statistics.
    
    v0.5.1: Used in /studio/migrations/summary endpoint.
    """
    
    app_label: str = Field(
        ...,
        description="Application label (e.g., 'auth', 'blog')"
    )
    total: int = Field(
        default=0,
        description="Total migrations for this app"
    )
    applied: int = Field(
        default=0,
        description="Applied migrations for this app"
    )
    pending: int = Field(
        default=0,
        description="Pending migrations for this app"
    )
    has_conflicts: bool = Field(
        default=False,
        description="Whether this app has migration conflicts"
    )
    head_migrations: List[str] = Field(
        default_factory=list,
        description="Current head migrations (should be 1 if no conflicts)"
    )


class StudioMigrationConflict(BaseModel):
    """
    Migration conflict details.
    
    v0.5.1: Describes a detected migration conflict.
    """
    
    app_label: str = Field(
        ...,
        description="Application with conflict"
    )
    heads: List[str] = Field(
        default_factory=list,
        description="Conflicting head migration names"
    )
    message: str = Field(
        ...,
        description="Human-readable conflict description"
    )


class StudioMigrationSummary(BaseModel):
    """
    Complete migration summary response.
    
    v0.5.1: New endpoint response model for /studio/migrations/summary.
    """
    
    total_migrations: int = Field(
        default=0,
        description="Total migrations across all apps"
    )
    applied_migrations: int = Field(
        default=0,
        description="Total applied migrations"
    )
    pending_migrations: int = Field(
        default=0,
        description="Total pending migrations"
    )
    apps: List[StudioAppMigrationSummary] = Field(
        default_factory=list,
        description="Per-app migration summaries"
    )
    conflicts: List[StudioMigrationConflict] = Field(
        default_factory=list,
        description="Detected migration conflicts"
    )
    migrations_checksum: str = Field(
        ...,
        description="SHA-256 of migration file list"
    )
    last_applied: Optional[str] = Field(
        default=None,
        description="Name of the most recently applied migration"
    )


class StudioProjectInfo(BaseModel):
    """
    Project metadata for Studio display.
    """
    
    name: str = Field(
        ...,
        description="Project/app name"
    )
    version: str = Field(
        default="0.0.0",
        description="Project version"
    )
    aksara_version: str = Field(
        ...,
        description="Aksara framework version"
    )
    python_version: str = Field(
        ...,
        description="Python runtime version"
    )
    debug_mode: bool = Field(
        default=False,
        description="Whether app is in debug mode"
    )
    environment: str = Field(
        default="development",
        description="Environment name (development, staging, production)"
    )


class StudioChecksums(BaseModel):
    """
    Checksums for change detection.
    
    Studio uses these to detect when it needs to refresh
    its cached data.
    """
    
    schema_checksum: str = Field(
        ...,
        description="SHA-256 of serialized model schema"
    )
    migrations_checksum: str = Field(
        ...,
        description="SHA-256 of migration file list"
    )
    settings_checksum: str = Field(
        ...,
        description="SHA-256 of non-sensitive settings"
    )
    routes_checksum: str = Field(
        ...,
        description="SHA-256 of route definitions"
    )


class StudioModelSummary(BaseModel):
    """
    Lightweight model summary for context endpoint.
    """
    
    name: str = Field(..., description="Model class name")
    table_name: str = Field(..., description="Database table name")
    field_count: int = Field(default=0, description="Number of fields")
    has_relations: bool = Field(default=False, description="Has FK or M2M relations")


class StudioContextSummary(BaseModel):
    """
    Lightweight context summary (no full schema).
    
    Used for quick status checks without transferring full context.
    
    v0.5.1: Added app_count, database_status, migration_status, schema_checksum.
    """
    
    # v0.5.1: New app count field
    app_count: int = Field(
        default=1,
        description="Number of installed/configured apps"
    )
    model_count: int = Field(
        ...,
        description="Total number of registered models"
    )
    viewset_count: int = Field(
        ...,
        description="Total number of registered viewsets"
    )
    route_count: int = Field(
        ...,
        description="Total number of API routes"
    )
    ai_tool_count: int = Field(
        ...,
        description="Total number of AI tools"
    )
    migration_count: int = Field(
        ...,
        description="Total number of migrations"
    )
    pending_migrations: int = Field(
        default=0,
        description="Number of unapplied migrations"
    )
    
    # v0.5.1: New database and migration status fields
    database_status: StudioDatabaseStatus = Field(
        default_factory=lambda: StudioDatabaseStatus(connected=False),
        description="Current database connection status"
    )
    migration_status: StudioMigrationStatus = Field(
        default_factory=StudioMigrationStatus,
        description="Migration health summary"
    )
    
    models: List[StudioModelSummary] = Field(
        default_factory=list,
        description="Summary of all models"
    )
    checksums: StudioChecksums = Field(
        ...,
        description="Checksums for change detection"
    )
    
    # v0.5.1: Convenience accessor for schema_checksum
    @property
    def schema_checksum(self) -> str:
        """SHA-256 checksum of the model schema."""
        return self.checksums.schema_checksum


class StudioHandshake(BaseModel):
    """
    Complete handshake response for Studio IDE integration.
    
    This is the main response sent when Studio connects to
    an Aksara application. It provides:
    - Project metadata
    - Database status
    - Available capabilities
    - Checksums for caching
    - API endpoint information
    """
    
    # Protocol version for compatibility
    protocol_version: str = Field(
        default="1.0",
        description="Studio protocol version"
    )
    
    # Timestamp
    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp of handshake"
    )
    
    # Project info
    project: StudioProjectInfo = Field(
        ...,
        description="Project metadata"
    )
    
    # Database status
    database: StudioDatabaseStatus = Field(
        ...,
        description="Database connection status"
    )
    
    # Capabilities
    capabilities: List[StudioCapability] = Field(
        default_factory=list,
        description="Available Studio capabilities"
    )
    
    # Checksums
    checksums: StudioChecksums = Field(
        ...,
        description="Checksums for cache invalidation"
    )
    
    # API endpoints info
    endpoints: Dict[str, str] = Field(
        default_factory=lambda: {
            "context_full": "/ai/context/full",
            "context_summary": "/studio/context/summary",
            "health": "/studio/health",
            "tools": "/ai/tools",
            "tools_mcp": "/ai/tools/mcp",
            "query_execute": "/ai/query/execute",
            "codegen_preview": "/ai/codegen/preview",
            "patch_preview": "/ai/patch/preview",
            "patch_apply": "/ai/patch/apply",
            "plan_preview": "/ai/plan/preview",
            "plan_apply": "/ai/plan/apply",
            "schema_health": "/ai/schema/health",
        },
        description="Available API endpoints"
    )
    
    # Extra metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


class StudioHealthResponse(BaseModel):
    """
    Simple health check response.
    """
    
    status: str = Field(
        default="healthy",
        description="Overall health status"
    )
    aksara_version: str = Field(
        ...,
        description="Aksara framework version"
    )
    database: StudioDatabaseStatus = Field(
        ...,
        description="Database connection status"
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp"
    )


# =============================================================================
# v0.5.2: Runtime Info Models
# =============================================================================

class StudioRuntimeInfo(BaseModel):
    """
    Runtime diagnostics information.
    
    v0.5.2: Read-only runtime info for Studio and CLI.
    """
    
    app_version: str = Field(
        ...,
        description="Aksara framework version"
    )
    python_version: str = Field(
        ...,
        description="Python interpreter version"
    )
    debug: bool = Field(
        default=False,
        description="Whether debug mode is enabled"
    )
    env: Optional[str] = Field(
        default=None,
        description="Environment name (e.g., development, production)"
    )
    pid: int = Field(
        ...,
        description="Process ID of the running server"
    )
    start_time: datetime = Field(
        ...,
        description="When the server process started"
    )
    uptime_seconds: float = Field(
        default=0.0,
        description="Seconds since process started"
    )
    database_status: str = Field(
        default="disconnected",
        description="Database status: 'ok', 'degraded', or 'disconnected'"
    )
    pending_migrations: int = Field(
        default=0,
        description="Number of pending migrations"
    )
    installed_apps: List[str] = Field(
        default_factory=list,
        description="List of installed app labels"
    )
    studio_enabled: bool = Field(
        default=True,
        description="Whether Studio endpoints are enabled"
    )
    studio_base_path: str = Field(
        default="/studio",
        description="Base path for Studio endpoints"
    )


class StudioRouteInfo(BaseModel):
    """
    Route metadata for a single API route.
    
    v0.5.2: Read-only route info for Studio.
    """
    
    path: str = Field(
        ...,
        description="Route path pattern"
    )
    methods: List[str] = Field(
        default_factory=list,
        description="HTTP methods this route handles"
    )
    name: Optional[str] = Field(
        default=None,
        description="Route name if set"
    )
    app_label: Optional[str] = Field(
        default=None,
        description="App label if derivable"
    )
    is_studio: bool = Field(
        default=False,
        description="Whether this is a Studio endpoint"
    )
    is_admin: bool = Field(
        default=False,
        description="Whether this is an Admin endpoint"
    )
    is_ai: bool = Field(
        default=False,
        description="Whether this is an AI endpoint"
    )
