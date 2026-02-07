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


# =============================================================================
# v0.5.4: Studio ↔ AI Integration Models
# =============================================================================

class StudioAiProjectMeta(BaseModel):
    """
    Project metadata for AI context export.
    
    v0.5.4: Safe subset of project info for AI tools.
    """
    
    name: str = Field(
        ...,
        description="Project/app name"
    )
    version: str = Field(
        ...,
        description="Aksara version"
    )
    environment: str = Field(
        default="development",
        description="Environment (development, staging, production)"
    )
    debug: bool = Field(
        default=False,
        description="Whether debug mode is enabled"
    )


class StudioAiModelSummary(BaseModel):
    """
    Lightweight model summary for AI context.
    
    v0.5.4: Contains only what AI needs to understand the schema.
    """
    
    name: str = Field(..., description="Model class name")
    table_name: str = Field(..., description="Database table name")
    app_label: Optional[str] = Field(default=None, description="App label")
    fields: List[str] = Field(default_factory=list, description="Field names")
    primary_key: str = Field(default="id", description="Primary key field")
    has_timestamps: bool = Field(default=False, description="Has created_at/updated_at")


class StudioAiRouteSummary(BaseModel):
    """
    Lightweight route summary for AI context.
    
    v0.5.4: Contains only what AI needs to understand available routes.
    """
    
    path: str = Field(..., description="Route path pattern")
    methods: List[str] = Field(default_factory=list, description="HTTP methods")
    name: Optional[str] = Field(default=None, description="Route name")
    is_authenticated: bool = Field(default=False, description="Requires auth")


class StudioAiToolInfo(BaseModel):
    """
    AI tool summary for context export.
    
    v0.5.4: Describes a tool/endpoint AI can use.
    """
    
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="What the tool does")
    endpoint: Optional[str] = Field(default=None, description="API endpoint if applicable")
    safe: bool = Field(default=True, description="Whether tool is read-only/safe")


class StudioAiContextExport(BaseModel):
    """
    Complete AI context bundle for export.
    
    v0.5.4: Everything an external AI agent needs to understand the app.
    This is a Studio-friendly, secrets-stripped version of the full AI context.
    """
    
    project: StudioAiProjectMeta = Field(
        ...,
        description="Project metadata"
    )
    models: List[StudioAiModelSummary] = Field(
        default_factory=list,
        description="Model summaries"
    )
    routes: List[StudioAiRouteSummary] = Field(
        default_factory=list,
        description="Route summaries"
    )
    tools: List[StudioAiToolInfo] = Field(
        default_factory=list,
        description="Available AI tools"
    )
    apps: List[str] = Field(
        default_factory=list,
        description="Installed app labels"
    )
    migration_status: StudioMigrationStatus = Field(
        default_factory=StudioMigrationStatus,
        description="Migration health snapshot"
    )
    schema_checksum: str = Field(
        default="",
        description="Schema checksum for change detection"
    )
    exported_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Export timestamp"
    )


class StudioAiSchemas(BaseModel):
    """
    JSON schemas for AI operations.
    
    v0.5.4: Contains schemas AI agents can use to generate valid requests.
    """
    
    plan_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for AiPlan requests"
    )
    patch_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for AiPatchRequest"
    )
    query_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for AiQueryPlan"
    )
    codegen_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for AiCodegenRequest"
    )
    context_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for AiFullContext (reference)"
    )


class StudioAiPromptTemplate(BaseModel):
    """
    A reusable prompt template for AI interactions.
    
    v0.5.4: Templates contain placeholders like {context_json}, {plan_schema}.
    """
    
    id: str = Field(
        ...,
        description="Unique template identifier (e.g., 'add-field')"
    )
    title: str = Field(
        ...,
        description="Human-friendly title"
    )
    description: str = Field(
        ...,
        description="What this prompt template is for"
    )
    template: str = Field(
        ...,
        description="The actual prompt text with placeholders"
    )
    placeholders: List[str] = Field(
        default_factory=list,
        description="List of placeholder names used in template"
    )
    category: str = Field(
        default="general",
        description="Category (general, schema, migration, query)"
    )


class StudioAiPrompts(BaseModel):
    """
    Container for multiple prompt templates.
    
    v0.5.4: Returns all available prompt templates.
    """
    
    prompts: List[StudioAiPromptTemplate] = Field(
        default_factory=list,
        description="Available prompt templates"
    )
    version: str = Field(
        default="1.0",
        description="Prompt template version"
    )


# =============================================================================
# v0.5.10: Query Inspector & Profiler Models
# =============================================================================

class StudioQueryTrace(BaseModel):
    """
    Single database query execution trace.
    
    v0.5.10: Captures SQL, timing, and call site info.
    """
    
    sql: str = Field(
        ...,
        description="The SQL query that was executed"
    )
    params: Optional[Any] = Field(
        default=None,
        description="Query parameters (if any)"
    )
    duration_ms: float = Field(
        ...,
        description="Query execution time in milliseconds"
    )
    rows_affected: Optional[int] = Field(
        default=None,
        description="Number of rows affected/returned"
    )
    operation: str = Field(
        ...,
        description="Query type: SELECT, INSERT, UPDATE, DELETE, OTHER"
    )
    table: Optional[str] = Field(
        default=None,
        description="Primary table being queried"
    )
    timestamp: datetime = Field(
        ...,
        description="When the query was executed"
    )
    stack_summary: Optional[str] = Field(
        default=None,
        description="Short call site info (file:line:function)"
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Associated request ID"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Additional categorization tags"
    )
    is_slow: bool = Field(
        ...,
        description="Whether this query exceeded the slow threshold"
    )


class StudioQueryBatch(BaseModel):
    """
    Collection of queries from a single request.
    
    v0.5.10: Groups queries by request with aggregations.
    """
    
    request_id: Optional[str] = Field(
        default=None,
        description="Request correlation ID"
    )
    path: Optional[str] = Field(
        default=None,
        description="HTTP request path"
    )
    method: Optional[str] = Field(
        default=None,
        description="HTTP method"
    )
    status_code: Optional[int] = Field(
        default=None,
        description="HTTP response status code"
    )
    started_at: datetime = Field(
        ...,
        description="When the request started"
    )
    ended_at: Optional[datetime] = Field(
        default=None,
        description="When the request completed"
    )
    total_duration_ms: float = Field(
        ...,
        description="Total time spent in database queries"
    )
    total_queries: int = Field(
        ...,
        description="Total number of queries executed"
    )
    slow_queries: int = Field(
        ...,
        description="Number of queries exceeding slow threshold"
    )
    n_plus_one_suspicions: List[str] = Field(
        default_factory=list,
        description="Warnings about potential N+1 query patterns"
    )
    queries: List[StudioQueryTrace] = Field(
        default_factory=list,
        description="Individual query traces"
    )


class StudioQueryStats(BaseModel):
    """
    Aggregate query statistics.
    
    v0.5.10: Overview of query performance across requests.
    """
    
    total_batches: int = Field(
        ...,
        description="Number of request batches stored"
    )
    total_queries: int = Field(
        ...,
        description="Total queries across all batches"
    )
    avg_queries_per_request: float = Field(
        ...,
        description="Average queries per request"
    )
    total_slow_queries: int = Field(
        ...,
        description="Total slow queries across all batches"
    )
    requests_with_slow_queries: int = Field(
        ...,
        description="Number of requests with at least one slow query"
    )
    requests_with_n_plus_one: int = Field(
        ...,
        description="Number of requests with potential N+1 patterns"
    )


class StudioQueryInspector(BaseModel):
    """
    Combined response for query inspector endpoint.
    
    v0.5.10: Includes stats, recent batches, and slow queries.
    """
    
    enabled: bool = Field(
        ...,
        description="Whether query tracing is enabled"
    )
    slow_threshold_ms: float = Field(
        ...,
        description="Current slow query threshold in milliseconds"
    )
    stats: StudioQueryStats = Field(
        ...,
        description="Aggregate statistics"
    )
    recent_batches: List[StudioQueryBatch] = Field(
        default_factory=list,
        description="Recent request query batches (summary only)"
    )
    top_slow_queries: List[StudioQueryTrace] = Field(
        default_factory=list,
        description="Slowest queries across all batches"
    )


# =============================================================================
# v0.5.11: AI Profiles & Provider Contracts Models
# =============================================================================

class StudioAiModelProfileSummary(BaseModel):
    """
    Summary view of an AI model profile for Studio UI.
    
    v0.5.11: Lightweight representation of AiModelProfile.
    """
    
    name: str = Field(
        ...,
        description="Model identifier (e.g., 'gpt-4o')"
    )
    display_name: str = Field(
        ...,
        description="Human-readable model name"
    )
    kind: str = Field(
        ...,
        description="Model capability type (chat, embedding, etc.)"
    )
    max_input_tokens: Optional[int] = Field(
        default=None,
        description="Maximum input context length"
    )
    max_output_tokens: Optional[int] = Field(
        default=None,
        description="Maximum output length"
    )
    supports_tools: bool = Field(
        default=False,
        description="Whether model supports tool/function calling"
    )
    supports_streaming: bool = Field(
        default=True,
        description="Whether model supports streaming"
    )
    supports_vision: bool = Field(
        default=False,
        description="Whether model supports image inputs"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Model tags for filtering"
    )


class StudioAiProviderSummary(BaseModel):
    """
    Summary view of an AI provider profile for Studio UI.
    
    v0.5.11: Lightweight representation of AiProviderProfile.
    """
    
    name: str = Field(
        ...,
        description="Provider identifier"
    )
    display_name: str = Field(
        ...,
        description="Human-readable provider name"
    )
    kind: str = Field(
        ...,
        description="Provider type (openai, anthropic, local, etc.)"
    )
    model_count: int = Field(
        ...,
        description="Number of models available"
    )
    default_model: Optional[str] = Field(
        default=None,
        description="Default model name for this provider"
    )
    has_custom_base_url: bool = Field(
        default=False,
        description="Whether provider uses custom endpoint URL"
    )
    is_example: bool = Field(
        default=False,
        description="Whether this is a built-in example provider"
    )
    client_ready: bool = Field(
        default=False,
        description="v0.5.14: Whether SDK is installed and credentials configured"
    )
    models: List[StudioAiModelProfileSummary] = Field(
        default_factory=list,
        description="Available models for this provider"
    )


class StudioAiProfileSetSummary(BaseModel):
    """
    Summary of the complete AI profile configuration.
    
    v0.5.11: Overview of all providers and models for Studio.
    """
    
    enabled: bool = Field(
        ...,
        description="Whether AI profiles are enabled"
    )
    providers: List[StudioAiProviderSummary] = Field(
        default_factory=list,
        description="Available AI providers"
    )
    default_provider: Optional[str] = Field(
        default=None,
        description="Name of the default provider"
    )
    total_models: int = Field(
        ...,
        description="Total models across all providers"
    )
    environment: Optional[str] = Field(
        default=None,
        description="Environment name (dev, stage, prod)"
    )
    version: Optional[str] = Field(
        default=None,
        description="Profile configuration version"
    )


class StudioAiSecretHint(BaseModel):
    """
    Secret hint for Studio UI display.
    
    v0.5.11: Shows what env vars are needed, never actual values.
    """
    
    provider_name: str = Field(
        ...,
        description="Provider this secret is for"
    )
    env_var: str = Field(
        ...,
        description="Environment variable name"
    )
    required: bool = Field(
        default=True,
        description="Whether this secret is required"
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description"
    )
    is_configured: bool = Field(
        default=False,
        description="Whether the env var is set (not the value!)"
    )


class StudioAiSecretsInfo(BaseModel):
    """
    Information about required AI secrets.
    
    v0.5.11: Lists env var names and whether they are configured.
    NEVER includes actual secret values.
    """
    
    secrets: List[StudioAiSecretHint] = Field(
        default_factory=list,
        description="List of secret hints"
    )
    configured_count: int = Field(
        ...,
        description="Number of secrets that are configured"
    )
    total_count: int = Field(
        ...,
        description="Total number of secrets required"
    )


# =============================================================================
# v0.5.12: AI Profile Health Models
# =============================================================================

class StudioAiProfileIssue(BaseModel):
    """
    A single validation issue in AI profile configuration.
    
    v0.5.12: Used by /studio/ai/health endpoint.
    """
    
    id: str = Field(
        ...,
        description="Stable identifier for this issue"
    )
    kind: str = Field(
        ...,
        description="Classification of the issue type"
    )
    severity: str = Field(
        ...,
        description="How critical this issue is (info/warning/error)"
    )
    message: str = Field(
        ...,
        description="Human-readable description of the issue"
    )
    provider_name: Optional[str] = Field(
        default=None,
        description="Provider involved (if applicable)"
    )
    model_name: Optional[str] = Field(
        default=None,
        description="Model involved (if applicable)"
    )
    field: Optional[str] = Field(
        default=None,
        description="Specific field with issue"
    )


class StudioAiProfileHealth(BaseModel):
    """
    Health status of AI profile configuration.
    
    v0.5.12: Result of /studio/ai/health endpoint.
    """
    
    is_valid: bool = Field(
        ...,
        description="True if no errors were found"
    )
    error_count: int = Field(
        default=0,
        description="Number of error-level issues"
    )
    warning_count: int = Field(
        default=0,
        description="Number of warning-level issues"
    )
    info_count: int = Field(
        default=0,
        description="Number of info-level issues"
    )
    issues: List[StudioAiProfileIssue] = Field(
        default_factory=list,
        description="List of all discovered issues"
    )
    provider_count: int = Field(
        default=0,
        description="Number of configured providers"
    )
    model_count: int = Field(
        default=0,
        description="Total number of models"
    )
    default_provider: Optional[str] = Field(
        default=None,
        description="Name of the default provider"
    )


# =============================================================================
# v0.5.13: AI Route Hints Models
# =============================================================================

class StudioAiRouteHint(BaseModel):
    """
    AI hint for a specific route.
    
    v0.5.13: Route-level AI metadata for LLM guidance.
    """
    
    view_name: str = Field(
        ...,
        description="ViewSet/View class name"
    )
    route_name: str = Field(
        ...,
        description="Route identifier"
    )
    path: str = Field(
        ...,
        description="Full URL path"
    )
    methods: List[str] = Field(
        default_factory=list,
        description="HTTP methods"
    )
    title: str = Field(
        ...,
        description="Short label"
    )
    description: str = Field(
        default="",
        description="AI-facing description"
    )
    usage_kind: str = Field(
        default="read_only",
        description="read_only, write, or admin"
    )
    risk_level: str = Field(
        default="low",
        description="low, medium, or high"
    )
    example_prompt: Optional[str] = Field(
        default=None,
        description="Example user prompt"
    )
    example_input: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Example request body"
    )
    example_output: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Example response body"
    )
    recommended_model: Optional[str] = Field(
        default=None,
        description="Recommended AI model"
    )
    recommended_provider: Optional[str] = Field(
        default=None,
        description="Recommended AI provider"
    )


class StudioAiHintSet(BaseModel):
    """
    Collection of AI route hints.
    
    v0.5.13: Result of /studio/ai/hints endpoint.
    """
    
    routes: List[StudioAiRouteHint] = Field(
        default_factory=list,
        description="All discovered route hints"
    )
    total_count: int = Field(
        default=0,
        description="Total number of hints"
    )
    
    # Usage stats
    read_only_count: int = Field(
        default=0,
        description="Read-only routes"
    )
    write_count: int = Field(
        default=0,
        description="Write routes"
    )
    admin_count: int = Field(
        default=0,
        description="Admin routes"
    )
    
    # Risk stats
    low_risk_count: int = Field(
        default=0,
        description="Low risk routes"
    )
    medium_risk_count: int = Field(
        default=0,
        description="Medium risk routes"
    )
    high_risk_count: int = Field(
        default=0,
        description="High risk routes"
    )


# =============================================================================
# v0.5.19: Agent Mode Models
# =============================================================================


class AgentContextSection(BaseModel):
    """
    One section of gathered context for an LLM agent.

    v0.5.19: Each section represents a logical group of project data
    (e.g. models, routes, migrations) that can be selectively included
    in an agent prompt.
    """

    title: str = Field(description="Human-readable section title")
    description: str = Field(description="What this section contains")
    key: str = Field(description="Machine-readable section key")
    data: Any = Field(description="Section payload (models, routes, etc.)")
    size_kb: float = Field(
        default=0.0,
        description="Approximate size of this section in KB",
    )


class StudioAgentContext(BaseModel):
    """
    Full agent context gathered from all available sources.

    v0.5.19: Aggregates project_info, models, routes, migrations,
    diagnostics, ai_profiles, ai_hints, db_queries, and schema_checksum
    into a single response for LLM consumption.
    """

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when context was generated",
    )
    total_sections: int = Field(default=0, description="Number of sections")
    total_size_kb: float = Field(
        default=0.0,
        description="Total approximate size across all sections in KB",
    )
    sections: List[AgentContextSection] = Field(
        default_factory=list,
        description="All gathered context sections",
    )


class StudioAgentPromptRequest(BaseModel):
    """
    Request body for generating an agent system prompt.

    v0.5.19: The caller specifies which context sections to include,
    an optional goal, and an optional custom system prompt prefix.
    """

    selected_sections: List[str] = Field(
        default_factory=list,
        description="Section keys to include (empty = all)",
    )
    custom_system_prompt: Optional[str] = Field(
        default=None,
        description="Optional custom prefix for the system prompt",
    )
    goal: str = Field(
        description="What the agent should accomplish",
    )


class StudioAgentPromptResponse(BaseModel):
    """
    Generated system prompt and LLM recommendations.

    v0.5.19: Contains the assembled system prompt, recommended model
    parameters, and a rough token estimate.
    """

    system_prompt: str = Field(description="The assembled system prompt")
    recommended_temperature: float = Field(
        default=0.5,
        description="Suggested temperature (lower for high-risk tasks)",
    )
    recommended_model: str = Field(
        default="gpt-4o",
        description="Suggested model identifier",
    )
    tokens_estimate: int = Field(
        default=0,
        description="Rough word-count-based token estimate",
    )
