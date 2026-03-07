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
from typing import Any, Dict, List, Literal, Optional

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


# =============================================================================
# v0.5.20: Agent Playbooks Models
# =============================================================================

# Reuse Literal types compatible with aksara.ai.models
AgentPlaybookKind = Literal[
    "add_field", "add_endpoint", "fix_migrations",
    "add_validation", "refactor_viewset", "debug_queries",
    "harden_permissions",
]


class AgentPlaybookStep(BaseModel):
    """One step within an Agent Playbook."""

    id: str = Field(description="Step identifier")
    title: str = Field(description="Human-readable step title")
    description: str = Field(description="What this step does")
    recommended_sections: List[str] = Field(
        default_factory=list,
        description="Context section keys relevant to this step",
    )
    estimated_impact: Optional[str] = Field(
        default=None,
        description="Short impact note (e.g. 'schema change', 'low risk')",
    )


class AgentPlaybook(BaseModel):
    """A reusable Agent Playbook recipe for LLM-assisted tasks."""

    key: str = Field(description="Unique slug identifier")
    label: str = Field(description="Human-readable name")
    kind: AgentPlaybookKind = Field(description="Playbook kind")
    description: str = Field(description="What this playbook does")
    category: str = Field(description="Category: schema, api, migrations, diagnostics")
    default_goal_template: str = Field(
        description="Goal template with {placeholders}",
    )
    risk_level: str = Field(
        default="low",
        description="Risk level: low, medium, high",
    )
    usage_kind: str = Field(
        default="read_only",
        description="Usage kind: read_only, write, admin",
    )
    default_sections: List[str] = Field(
        default_factory=list,
        description="Context sections selected by default",
    )
    steps: List[AgentPlaybookStep] = Field(
        default_factory=list,
        description="Ordered list of playbook steps",
    )
    tags: List[str] = Field(default_factory=list, description="Search tags")
    notes: Optional[str] = Field(default=None, description="Additional notes")


class AgentPlaybookSet(BaseModel):
    """Collection of playbooks with aggregate counts."""

    playbooks: List[AgentPlaybook] = Field(default_factory=list)
    total_count: int = Field(default=0)
    by_category: Dict[str, int] = Field(default_factory=dict)
    by_risk_level: Dict[str, int] = Field(default_factory=dict)
    by_usage_kind: Dict[str, int] = Field(default_factory=dict)


class StudioAgentPlaybookPromptRequest(BaseModel):
    """Request body for playbook-driven prompt generation."""

    playbook_key: str = Field(description="Key of the playbook to use")
    user_goal: Optional[str] = Field(
        default=None,
        description="Optional goal override (else uses playbook default)",
    )
    selected_sections: Optional[List[str]] = Field(
        default=None,
        description="Section keys override (else uses playbook defaults)",
    )
    custom_system_prompt: Optional[str] = Field(
        default=None,
        description="Optional custom prefix for the system prompt",
    )


# =============================================================================
# v0.5.21: Query & Model Inspector Models
# =============================================================================


class StudioQueryPlanRequest(BaseModel):
    """Request body for EXPLAIN plan generation via Studio API."""

    sql: str = Field(description="The SQL query to explain")
    analyze: bool = Field(
        default=False,
        description="Run EXPLAIN ANALYZE (actually executes the query)",
    )


class StudioQueryPlanResult(BaseModel):
    """EXPLAIN plan result for Studio API."""

    sql: str = Field(description="Original SQL query")
    plan: List[str] = Field(
        default_factory=list,
        description="Lines of the EXPLAIN output",
    )
    estimated_cost: Optional[float] = Field(
        default=None,
        description="Total estimated cost from the planner",
    )
    plan_type: str = Field(
        default="EXPLAIN",
        description="Type: EXPLAIN or EXPLAIN ANALYZE",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings or notes about the plan",
    )


class StudioModelInspectorField(BaseModel):
    """Per-field metadata from model inspection."""

    name: str = Field(description="Field name")
    column_name: str = Field(description="Database column name")
    field_type: str = Field(description="Aksara field class name")
    python_type: str = Field(default="Any", description="Python type")
    nullable: bool = Field(default=False)
    primary_key: bool = Field(default=False)
    unique: bool = Field(default=False)
    has_default: bool = Field(default=False)
    default_repr: Optional[str] = Field(default=None)
    max_length: Optional[int] = Field(default=None)
    choices: Optional[List[str]] = Field(default=None)
    is_relation: bool = Field(default=False)
    ai_description: str = Field(default="")
    ai_sensitive: bool = Field(default=False)
    auto_generated: str = Field(default="")


class StudioModelInspectorRelationship(BaseModel):
    """Relationship metadata from model inspection."""

    field_name: str = Field(description="Field name")
    kind: str = Field(description="fk, m2m, o2o")
    target_model: str = Field(description="Target model name")
    target_table: str = Field(default="")
    on_delete: str = Field(default="CASCADE")
    through_table: Optional[str] = Field(default=None)
    related_name: Optional[str] = Field(default=None)
    nullable: bool = Field(default=False)


class StudioModelInspectorConstraint(BaseModel):
    """Constraint / index info from model inspection."""

    kind: str = Field(description="primary_key, unique, index, check")
    columns: List[str] = Field(default_factory=list)
    name: Optional[str] = Field(default=None)
    description: str = Field(default="")


class StudioModelInspectorSummary(BaseModel):
    """Full model inspection result for Studio API."""

    name: str = Field(description="Model class name")
    table_name: str = Field(description="Database table name")
    app_label: Optional[str] = Field(default=None)
    num_fields: int = Field(default=0)
    num_relationships: int = Field(default=0)
    has_timestamps: bool = Field(default=False)
    pk_field: Optional[str] = Field(default=None)
    pk_type: str = Field(default="IntegerField")
    fields: List[StudioModelInspectorField] = Field(default_factory=list)
    relationships: List[StudioModelInspectorRelationship] = Field(default_factory=list)
    constraints: List[StudioModelInspectorConstraint] = Field(default_factory=list)
    ai_description: str = Field(default="")
    ai_agent_exposed: bool = Field(default=True)
    create_table_sql: str = Field(default="")
    comments: List[str] = Field(default_factory=list)


class StudioModelInspectorAll(BaseModel):
    """All inspected models response."""

    models: List[StudioModelInspectorSummary] = Field(default_factory=list)
    total_count: int = Field(default=0)
    total_fields: int = Field(default=0)
    total_relationships: int = Field(default=0)


# =============================================================================
# v0.5.22: Semantic Search & AI Index
# =============================================================================


class StudioSearchRequest(BaseModel):
    """Request body for search query endpoint."""

    query: str = Field(description="Search query string")
    top_k: int = Field(default=10, ge=1, le=100, description="Max results")
    kind: Optional[str] = Field(default=None, description="Filter by document kind")
    kinds: Optional[List[str]] = Field(default=None, description="Filter by multiple kinds")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags")
    min_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum score threshold")
    mode: str = Field(default="hybrid", description="Search mode: keyword, semantic, hybrid")


class StudioSearchResultItem(BaseModel):
    """A single search result item for Studio API."""

    id: str = Field(description="Document ID")
    kind: str = Field(description="Document kind")
    title: str = Field(description="Document title")
    summary: str = Field(description="Short summary")
    score: float = Field(description="Relevance score 0-1")
    highlights: List[str] = Field(default_factory=list, description="Matched snippets")
    match_type: str = Field(default="keyword", description="Match method")
    source: str = Field(default="", description="Source identifier")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Extra metadata")
    tags: List[str] = Field(default_factory=list)


class StudioSearchResultSet(BaseModel):
    """Response for search query endpoint."""

    query: str = Field(description="Original query")
    total_results: int = Field(default=0, description="Number of results returned")
    results: List[StudioSearchResultItem] = Field(default_factory=list)
    mode: str = Field(default="hybrid", description="Search mode used")
    index_size: int = Field(default=0, description="Total documents in index")


class StudioSearchIndexInfo(BaseModel):
    """Response for search index info endpoint."""

    total_documents: int = Field(default=0)
    by_kind: Dict[str, int] = Field(default_factory=dict)
    vocabulary_size: int = Field(default=0)
    kinds_available: List[str] = Field(default_factory=list)
    embedding_provider: str = Field(default="local_tfidf")


# =============================================================================
# v0.5.23: Agentic Workflows — Plans, Not Pushes
# =============================================================================


AgentWorkflowStepKind = Literal[
    "inspect",
    "search",
    "edit_file",
    "run_migration",
    "run_query",
    "run_test",
    "environment",
    "config",
    "diagnostics",
    "doc_reading",
]


class AgentWorkflowStep(BaseModel):
    """A single step in an agent workflow.

    v0.5.23: Structured task for humans or external agents.
    Commands and notes are display-only — nothing is auto-executed.
    """

    id: str = Field(description="Unique step identifier")
    kind: AgentWorkflowStepKind = Field(description="Step category")
    title: str = Field(description="Short human-readable title")
    description: str = Field(default="", description="Detailed explanation")
    references: Dict[str, Any] = Field(
        default_factory=dict,
        description="References to models, routes, diagnostics, etc.",
    )
    estimated_effort: Literal["low", "medium", "high"] = Field(
        default="low", description="Estimated effort"
    )
    risk: Optional[str] = Field(
        default=None, description="Risk level (low/medium/high)"
    )
    commands: List[str] = Field(
        default_factory=list,
        description="Shell/CLI commands for display only",
    )
    notes: List[str] = Field(
        default_factory=list, description="Extra hints and gotchas"
    )
    order: int = Field(default=0, description="Sort order in the workflow")


class AgentWorkflow(BaseModel):
    """A complete agent workflow — structured plan of tasks.

    v0.5.23: Read-only workflow; no auto-mutation of user code.
    """

    id: str = Field(description="Workflow identifier")
    goal: str = Field(description="User's stated goal")
    playbook: Optional[str] = Field(
        default=None, description="Playbook key, if derived from one"
    )
    source: Literal["doctor", "search", "manual", "mixed"] = Field(
        default="mixed", description="How the workflow was generated"
    )
    steps: List[AgentWorkflowStep] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Diagnostic IDs, search queries, etc.",
    )


class AgentWorkflowRequest(BaseModel):
    """Request body for generating an agent workflow."""

    goal: str = Field(description="What the user wants to accomplish")
    playbook: Optional[str] = Field(
        default=None, description="Optional playbook key"
    )
    include_diagnostics: bool = Field(
        default=True, description="Include diagnostics in workflow"
    )
    include_search: bool = Field(
        default=True, description="Include semantic search results"
    )
    search_query: Optional[str] = Field(
        default=None, description="Custom search query (defaults to goal)"
    )
    limit_search_results: int = Field(
        default=10, ge=1, le=50, description="Max search results"
    )
    limit_diagnostics: int = Field(
        default=10, ge=1, le=50, description="Max diagnostic issues"
    )


class AgentWorkflowResponse(BaseModel):
    """Response from workflow generation."""

    workflow: AgentWorkflow
    summary: str = Field(default="", description="1-3 sentence summary")
    stats: Dict[str, Any] = Field(
        default_factory=dict,
        description="Step counts by kind, risk, effort",
    )


# =============================================================================
# v0.5.25: AI Hub & Unified Provider System
# =============================================================================


class StudioAiProviderStatus(BaseModel):
    """Status summary for a single AI provider."""

    provider: str = Field(description="Provider key (openai, azure, anthropic, ollama, custom)")
    configured: bool = Field(default=False, description="Whether env vars are set")
    reachable: bool = Field(default=False, description="Whether ping succeeded")
    model: str = Field(default="", description="Currently configured model")
    base_url: str = Field(default="", description="Base URL (redacted if needed)")
    error: Optional[str] = Field(default=None, description="Error message if unreachable")


class StudioAiProvidersSummary(BaseModel):
    """Response for GET /studio/ai/hub/providers."""

    active_provider: Optional[str] = Field(default=None, description="Currently active provider key")
    active_model: str = Field(default="", description="Active model name")
    providers: List[StudioAiProviderStatus] = Field(default_factory=list, description="All detected providers")
    configured_count: int = Field(default=0, description="Number of configured providers")
    total_count: int = Field(default=0, description="Total providers checked")


class StudioAiProviderSaveRequest(BaseModel):
    """Request body for POST /studio/ai/hub/providers/save."""

    provider: str = Field(description="Provider key")
    api_key: Optional[str] = Field(default=None, description="API key (if applicable)")
    base_url: Optional[str] = Field(default=None, description="Base URL override")
    model: Optional[str] = Field(default=None, description="Model name")
    extra: Dict[str, Any] = Field(default_factory=dict, description="Extra config (deployment, api_version, etc.)")
    save_to: str = Field(default="env", description="Where to save: 'env' (.env) or 'json' (provider.json)")


class StudioAiProviderSaveResponse(BaseModel):
    """Response for POST /studio/ai/hub/providers/save."""

    saved: bool = Field(default=False, description="Whether save succeeded")
    provider: str = Field(description="Provider key saved")
    file_path: str = Field(default="", description="Path of the file written")
    message: str = Field(default="", description="Human-readable status message")


class StudioAiProviderPingRequest(BaseModel):
    """Request body for POST /studio/ai/hub/providers/ping."""

    provider: Optional[str] = Field(default=None, description="Provider key to ping (None = active)")


class StudioAiProviderPingResponse(BaseModel):
    """Response for POST /studio/ai/hub/providers/ping."""

    provider: str = Field(description="Provider that was pinged")
    reachable: bool = Field(default=False)
    latency_ms: Optional[float] = Field(default=None, description="Ping latency in milliseconds")
    model: str = Field(default="", description="Model used for ping")
    error: Optional[str] = Field(default=None, description="Error if unreachable")


class StudioAiAgentRunRequest(BaseModel):
    """Request body for POST /studio/ai/hub/agent/run."""

    prompt: str = Field(description="User prompt text")
    provider: Optional[str] = Field(default=None, description="Provider override (None = active)")
    model: Optional[str] = Field(default=None, description="Model override")
    include_context: bool = Field(default=True, description="Include project context in system prompt")
    context_sections: Optional[List[str]] = Field(default=None, description="Sections to include")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=2048, ge=1, le=32000, description="Max tokens in response")


class StudioAiAgentRunResponse(BaseModel):
    """Response for POST /studio/ai/hub/agent/run."""

    provider: str = Field(description="Provider used")
    model: str = Field(description="Model used")
    output: str = Field(default="", description="Generated text output")
    tokens_estimated: Optional[int] = Field(default=None, description="Rough token count")
    error: Optional[str] = Field(default=None, description="Error if generation failed")


# =============================================================================
# v0.5.29: Studio AI Flows Models
# =============================================================================


class StudioAiFlowRequest(BaseModel):
    """Generic request body for POST /studio/ai/flows/*."""

    action_key: str = Field(description="Flow action key, e.g. explain_model")
    hub_overrides: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional provider/model overrides: {provider, model}",
    )


class StudioAiFlowModelRequest(StudioAiFlowRequest):
    """Request for POST /studio/ai/flows/model."""

    model_name: str = Field(description="Registered model class name")


class StudioAiFlowRouteRequest(StudioAiFlowRequest):
    """Request for POST /studio/ai/flows/route."""

    path: Optional[str] = Field(default=None, description="Route path, e.g. /api/users")
    method: Optional[str] = Field(default="GET", description="HTTP method")
    route_id: Optional[str] = Field(default=None, description="Alternative: route identifier")


class StudioAiFlowQueryRequest(StudioAiFlowRequest):
    """Request for POST /studio/ai/flows/query."""

    sql: str = Field(description="SQL query text")
    include_explain: bool = Field(default=True, description="Include EXPLAIN plan context")


class StudioAiFlowMigrationRequest(StudioAiFlowRequest):
    """Request for POST /studio/ai/flows/migration."""

    migration_id: Optional[str] = Field(default=None, description="Migration identifier")
    app: Optional[str] = Field(default=None, description="App label")
    name: Optional[str] = Field(default=None, description="Migration name")


class StudioAiFlowDiagnosticRequest(StudioAiFlowRequest):
    """Request for POST /studio/ai/flows/diagnostic."""

    issue_id: Optional[str] = Field(default=None, description="Diagnostic issue ID")
    issue_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Full issue object (category, severity, title, message, actions)",
    )


class StudioAiFlowResponse(BaseModel):
    """Unified response for all AI flow endpoints."""

    ok: bool = Field(default=True)
    action_key: str = Field(default="", description="Action that was executed")
    risk: str = Field(default="low", description="low | medium | high")
    provider: str = Field(default="", description="AI provider used")
    model: str = Field(default="", description="Model used")
    system_prompt: str = Field(default="", description="System prompt for LLM")
    user_prompt: str = Field(default="", description="User prompt for LLM")
    result_markdown: str = Field(default="", description="Markdown-formatted result")
    result_json: Optional[Dict[str, Any]] = Field(default=None, description="Structured result data")
    suggested_next: List[str] = Field(default_factory=list, description="Recommended follow-up actions")
    what_it_does: str = Field(default="", description="What this action does")
    what_it_cannot_do: str = Field(default="", description="Limitations of this action")
    error_code: Optional[str] = Field(default=None, description="Error code if ok=false")
    error: Optional[str] = Field(default=None, description="Error message if ok=false")


class StudioAiFlowActionDescriptor(BaseModel):
    """Describes a single available AI flow action."""

    action_key: str = Field(description="Unique action key")
    kind: str = Field(description="Flow kind: model, route, query, migration, diagnostic")
    title: str = Field(description="Human-readable title")
    description: str = Field(description="What the action does")
    risk: str = Field(description="low | medium | high")
    what_it_does: str = Field(default="")
    what_it_cannot_do: str = Field(default="")
    recommended_next: List[str] = Field(default_factory=list)


class StudioAiFlowActionsResponse(BaseModel):
    """Response for GET /studio/ai/flows/actions."""

    actions: List[StudioAiFlowActionDescriptor] = Field(default_factory=list)
    total: int = Field(default=0)


# v0.5.30: AI Flow Execution models

class StudioAiFlowRunRequest(BaseModel):
    """Request for POST /studio/ai/flows/run — execute a prompt pack via connector."""

    flow_type: str = Field(description="Flow type: model, route, query, migration, diagnostic")
    action_key: str = Field(description="Action key, e.g. explain_model")
    context: Dict[str, Any] = Field(default_factory=dict, description="Flow context (model_name, path, sql, etc.)")
    provider_override: Optional[str] = Field(default=None, description="Override AI provider")
    model_override: Optional[str] = Field(default=None, description="Override AI model")


class StudioAiFlowRunResponse(BaseModel):
    """Response for POST /studio/ai/flows/run — execution result."""

    ok: bool = Field(default=True)
    prompt_pack: Optional[Dict[str, Any]] = Field(default=None, description="The built prompt pack")
    execution: Optional[Dict[str, Any]] = Field(default=None, description="Connector execution result")
    error: Optional[str] = Field(default=None)
    error_code: Optional[str] = Field(default=None)


# =============================================================================
# v0.5.28: AI Hub 2.0 Models
# =============================================================================


class AiHubProvider(BaseModel):
    """Provider card — used in AI Hub panel."""

    kind: str = Field(description="Provider type key")
    enabled: bool = Field(default=True)
    configured: bool = Field(default=False)
    reachable: Optional[bool] = Field(default=None)
    model: str = Field(default="")
    base_url: str = Field(default="")
    modes: List[str] = Field(default_factory=list, description="chat, code, embeddings")
    error: Optional[str] = Field(default=None)


class AiHubModel(BaseModel):
    """An available model as reported by a provider."""

    model_id: str = Field(description="Model identifier")
    provider: str = Field(description="Owning provider kind")
    mode: str = Field(default="chat", description="Primary mode: chat, code, embeddings")


class AiHubRouteMapping(BaseModel):
    """Describes which provider/model a feature uses."""

    feature: str = Field(description="agents, playbooks, search_embeddings, diagnostics")
    provider: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)
    status: str = Field(default="ok", description="ok | fallback | missing")
    warning: Optional[str] = Field(default=None)


class AiHubOnboardingStatus(BaseModel):
    """Step-by-step onboarding progress."""

    providers_selected: bool = Field(default=False)
    keys_entered: bool = Field(default=False)
    providers_tested: bool = Field(default=False)
    defaults_set: bool = Field(default=False)
    sample_query_run: bool = Field(default=False)
    completed: bool = Field(default=False)


class AiHubStatus(BaseModel):
    """Top-level AI Hub status — response for GET /studio/ai-hub/status."""

    overall: str = Field(default="disabled", description="ready | partial | disabled")
    active_provider: Optional[str] = Field(default=None)
    configured_count: int = Field(default=0)
    total_count: int = Field(default=0)
    defaults: Dict[str, Any] = Field(default_factory=dict)
    onboarding: AiHubOnboardingStatus = Field(default_factory=AiHubOnboardingStatus)
    warnings: List[str] = Field(default_factory=list)


class AiHubRoutes(BaseModel):
    """Routing table for AI features — response for GET /studio/ai-hub/routes."""

    routes: List[AiHubRouteMapping] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class AiHubConfigureRequest(BaseModel):
    """Request body for POST /studio/ai-hub/configure."""

    provider: str = Field(description="Provider kind to configure")
    base_url: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)
    enabled: bool = Field(default=True)


class AiHubConfigureSecretRequest(BaseModel):
    """Request body for POST /studio/ai-hub/configure/secret."""

    provider: str = Field(description="Provider kind")
    api_key: str = Field(description="API key — handled securely, never logged")


class AiHubDefaultsRequest(BaseModel):
    """Request body for POST /studio/ai-hub/defaults."""

    chat_model: Optional[str] = Field(default=None)
    chat_provider: Optional[str] = Field(default=None)
    code_model: Optional[str] = Field(default=None)
    code_provider: Optional[str] = Field(default=None)
    embeddings_model: Optional[str] = Field(default=None)
    embeddings_provider: Optional[str] = Field(default=None)


class AiHubConfigureResponse(BaseModel):
    """Response for configure / configure/secret / defaults."""

    ok: bool = Field(default=False)
    message: str = Field(default="")
    provider: Optional[str] = Field(default=None)


class AiHubTestRequest(BaseModel):
    """Request body for POST /studio/ai-hub/test."""

    provider: str = Field(description="Provider kind to test")


class AiHubTestResponse(BaseModel):
    """Response for POST /studio/ai-hub/test."""

    provider: str = Field(description="Provider tested")
    reachable: bool = Field(default=False)
    latency_ms: Optional[float] = Field(default=None)
    model: str = Field(default="")
    modes: List[str] = Field(default_factory=list)
    error: Optional[str] = Field(default=None)


class AiHubModelsResponse(BaseModel):
    """Response for GET /studio/ai-hub/models."""

    defaults: Dict[str, Any] = Field(default_factory=dict)
    models: List[AiHubModel] = Field(default_factory=list)


class AiHubProvidersResponse(BaseModel):
    """Response for GET /studio/ai-hub/providers."""

    providers: List[AiHubProvider] = Field(default_factory=list)
    active_provider: Optional[str] = Field(default=None)
    configured_count: int = Field(default=0)
    total_count: int = Field(default=0)


# =============================================================================
# v0.5.26: Gap Analysis Models
# =============================================================================


class StudioGapFixCommand(BaseModel):
    """A single shell command that can remedy a gap issue."""

    description: str = Field(description="Human-readable description of what this command does")
    command: str = Field(description="Shell command to run")
    env_required: List[str] = Field(default_factory=list, description="Env vars required before running")


class StudioGapIssue(BaseModel):
    """A single gap issue found during analysis — Studio API representation."""

    category: str = Field(description="Check category: imports, db, migrations, routers, providers, studio, environment, ai_pipeline")
    severity: str = Field(description="Severity: info, warning, error, critical")
    code: str = Field(description="Unique machine-readable code, e.g. 'DB_NO_URL'")
    title: str = Field(description="Short human-readable title")
    message: str = Field(description="Detailed explanation")
    hint: Optional[str] = Field(default=None, description="Suggested fix (plain English)")
    fix_commands: List[StudioGapFixCommand] = Field(default_factory=list, description="Ordered fix commands")
    meta: Optional[Dict[str, Any]] = Field(default=None, description="Extra metadata")
    is_blocking: bool = Field(default=False, description="True if severity is critical or error")


class StudioGapAnalysisStats(BaseModel):
    """Issue count breakdown by severity."""

    critical: int = Field(default=0)
    error: int = Field(default=0)
    warning: int = Field(default=0)
    info: int = Field(default=0)
    total: int = Field(default=0)
    has_blocking: bool = Field(default=False)
    overall_status: str = Field(default="clean", description="clean | warning | error | critical")


class StudioGapAnalysisReport(BaseModel):
    """Full gap analysis report — response for GET /studio/gaps."""

    issues: List[StudioGapIssue] = Field(default_factory=list)
    stats: StudioGapAnalysisStats = Field(default_factory=StudioGapAnalysisStats)
    categories_checked: List[str] = Field(default_factory=list)
    summary_line: str = Field(default="", description="Human-readable summary, e.g. '3 issues (1 critical)'")
    timestamp: str = Field(default="", description="ISO 8601 timestamp")
    duration_ms: float = Field(default=0.0, description="Total analysis duration in milliseconds")
    system: Dict[str, str] = Field(default_factory=dict)


class StudioGapAnalysisRunResponse(BaseModel):
    """Response for POST /studio/gaps/run — triggers a fresh analysis."""

    triggered_at: str = Field(default="", description="ISO 8601 timestamp when analysis was triggered")
    status: str = Field(default="ok", description="ok | error")
    report: Optional[StudioGapAnalysisReport] = Field(default=None, description="Analysis report if completed synchronously")
    error: Optional[str] = Field(default=None, description="Error message if analysis failed")


# =============================================================================
# v0.5.31: Interactive AI Console
# =============================================================================

class StudioAiConsoleRequest(BaseModel):
    """Request body for POST /studio/ai/console."""

    message: str = Field(..., description="Natural-language command, e.g. 'explain the User model'")
    provider_override: Optional[str] = Field(default=None, description="Override the AI provider")
    model_override: Optional[str] = Field(default=None, description="Override the AI model")


class StudioAiConsoleResponse(BaseModel):
    """Response from the Interactive AI Console."""

    ok: bool = Field(default=False)
    intent: str = Field(default="unknown", description="Detected intent / action key")
    flow_type: str = Field(default="", description="Flow type: model | route | query | migration | diagnostic")
    action_key: str = Field(default="", description="Resolved AI Flow action key")
    confidence: float = Field(default=0.0, description="Intent detection confidence 0..1")
    extracted_context: Dict[str, Any] = Field(default_factory=dict, description="Context extracted from the message")
    prompt_pack: Optional[Dict[str, Any]] = Field(default=None, description="The generated prompt pack")
    execution: Optional[Dict[str, Any]] = Field(default=None, description="Execution result from the AI runtime")
    suggestions: List[str] = Field(default_factory=list, description="Recommended follow-up action keys")
    elapsed_ms: float = Field(default=0.0, description="Total pipeline time in ms")
    error: Optional[str] = Field(default=None, description="Error message if not ok")
    error_code: Optional[str] = Field(default=None, description="Machine-readable error code")


class StudioAiConsoleSuggestResponse(BaseModel):
    """Response from GET /studio/ai/console/suggest."""

    suggestions: List[str] = Field(default_factory=list, description="Matching command suggestions")
    intents: List[Dict[str, str]] = Field(default_factory=list, description="Available intent descriptors")


# =============================================================================
# v0.5.32: Project Context Graph Models
# =============================================================================


class StudioProjectGraphEventsResponse(BaseModel):
    """Response from GET /studio/ai/project-graph/events."""

    events: List[Dict[str, Any]] = Field(default_factory=list, description="Recent graph events")
    count: int = Field(default=0, description="Number of events returned")


# =============================================================================
# v0.5.33: AI Debugger Models
# =============================================================================


class StudioDebugRequest(BaseModel):
    """Request body for POST /studio/ai/debug."""

    query: Optional[str] = Field(default=None, description="Natural-language debug question, e.g. 'why is /api/users failing?'")


class StudioDebugRootCause(BaseModel):
    """A single root cause in the debug report."""

    cause_id: str = Field(default="", description="Unique ID for this root cause")
    title: str = Field(default="", description="Short title")
    description: str = Field(default="", description="Detailed explanation")
    confidence: float = Field(default=0.0, description="Confidence score 0..1")
    severity: str = Field(default="info", description="error | warning | info")
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence strings")
    related_issues: List[str] = Field(default_factory=list, description="Related issue IDs")
    related_clusters: List[str] = Field(default_factory=list, description="Related cluster IDs")
    category: str = Field(default="general", description="Root cause category")
    fix_suggestions: List[str] = Field(default_factory=list, description="Safe fix suggestions")


class StudioDebugCluster(BaseModel):
    """A cluster of related issues."""

    cluster_id: str = Field(default="", description="Unique cluster ID")
    label: str = Field(default="", description="Human-readable label")
    component_type: str = Field(default="general", description="model | route | query | migration | general")
    component_name: str = Field(default="", description="Component identifier")
    issue_ids: List[str] = Field(default_factory=list, description="Issue IDs in this cluster")
    severity: str = Field(default="info", description="Worst severity in the cluster")
    size: int = Field(default=0, description="Number of issues")


class StudioDebugIssue(BaseModel):
    """A single issue in the debug report."""

    id: str = Field(default="", description="Issue ID")
    source: str = Field(default="", description="diagnostic | gap | event")
    severity: str = Field(default="info", description="error | warning | info")
    title: str = Field(default="", description="Issue title / code")
    message: str = Field(default="", description="Description")
    related_models: List[str] = Field(default_factory=list)
    related_routes: List[str] = Field(default_factory=list)
    related_queries: List[str] = Field(default_factory=list)


class StudioDebugResponse(BaseModel):
    """Response from POST /studio/ai/debug."""

    ok: bool = Field(default=False)
    query: Optional[str] = Field(default=None, description="The original query if provided")
    issues: List[StudioDebugIssue] = Field(default_factory=list, description="All detected issues")
    clusters: List[StudioDebugCluster] = Field(default_factory=list, description="Issue clusters")
    root_causes: List[StudioDebugRootCause] = Field(default_factory=list, description="Detected root causes, ranked by confidence")
    summary: str = Field(default="", description="Human-readable summary")
    issue_count: int = Field(default=0)
    cluster_count: int = Field(default=0)
    root_cause_count: int = Field(default=0)
    elapsed_ms: float = Field(default=0.0)
    generated_at: str = Field(default="")


# =============================================================================
# v0.5.34: AI Architecture Review
# =============================================================================


class StudioArchitectureMetrics(BaseModel):
    """Computed architecture metrics."""

    model_count: int = Field(default=0)
    route_count: int = Field(default=0)
    query_count: int = Field(default=0)
    migration_count: int = Field(default=0)
    diagnostic_count: int = Field(default=0)
    avg_models_per_route: float = Field(default=0.0)
    avg_queries_per_route: float = Field(default=0.0)
    coupling_score: float = Field(default=0.0)


class StudioArchitectureFinding(BaseModel):
    """A single architectural finding."""

    id: str = Field(default="")
    severity: str = Field(default="info")
    title: str = Field(default="")
    description: str = Field(default="")
    related_nodes: List[str] = Field(default_factory=list)
    category: str = Field(default="general")


class StudioArchitectureSuggestion(BaseModel):
    """A refactoring suggestion."""

    suggestion_id: str = Field(default="")
    title: str = Field(default="")
    description: str = Field(default="")
    impact: str = Field(default="medium")
    related_findings: List[str] = Field(default_factory=list)


class StudioArchitectureReviewResponse(BaseModel):
    """Response from POST /studio/ai/architecture-review."""

    ok: bool = Field(default=False)
    score: int = Field(default=0, description="Architecture health score 0-100")
    grade: str = Field(default="F", description="Letter grade A-F")
    findings: List[StudioArchitectureFinding] = Field(default_factory=list)
    suggestions: List[StudioArchitectureSuggestion] = Field(default_factory=list)
    metrics: StudioArchitectureMetrics = Field(default_factory=StudioArchitectureMetrics)
    finding_count: int = Field(default=0)
    suggestion_count: int = Field(default=0)
    elapsed_ms: float = Field(default=0.0)
    generated_at: str = Field(default="")


# ─── v0.5.35: AI Performance Analyzer ────────────────────────────────────────


class StudioPerformanceMetrics(BaseModel):
    """Computed performance metrics."""

    total_routes: int = Field(default=0)
    total_queries: int = Field(default=0)
    slow_queries: int = Field(default=0)
    n_plus_one_candidates: int = Field(default=0)
    missing_indexes: int = Field(default=0)
    avg_queries_per_route: float = Field(default=0.0)
    max_queries_route: Optional[str] = Field(default=None)


class StudioPerformanceIssue(BaseModel):
    """A single performance issue."""

    issue_id: str = Field(default="")
    severity: str = Field(default="medium")
    title: str = Field(default="")
    description: str = Field(default="")
    route: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)
    query: Optional[str] = Field(default=None)
    category: str = Field(default="slow_query")


class StudioPerformanceRecommendation(BaseModel):
    """A performance improvement recommendation."""

    recommendation_id: str = Field(default="")
    title: str = Field(default="")
    description: str = Field(default="")
    impact: str = Field(default="medium")
    related_issue_ids: List[str] = Field(default_factory=list)


class StudioPerformanceAnalysisResponse(BaseModel):
    """Response from POST /studio/ai/performance-analysis."""

    ok: bool = Field(default=False)
    score: int = Field(default=0, description="Performance score 0-100")
    grade: str = Field(default="F", description="Letter grade A-F")
    issues: List[StudioPerformanceIssue] = Field(default_factory=list)
    recommendations: List[StudioPerformanceRecommendation] = Field(default_factory=list)
    metrics: StudioPerformanceMetrics = Field(default_factory=StudioPerformanceMetrics)
    issue_count: int = Field(default=0)
    recommendation_count: int = Field(default=0)
    elapsed_ms: float = Field(default=0.0)
    generated_at: str = Field(default="")
