"""
Aksara AI Context Engine

Comprehensive JSON context export for LLM consumption.
Provides complete application state including models, fields, relationships,
viewsets, routes, migrations, admin, settings, middleware, and AI tools.

This is the single most important foundation for Aksara as an AI-native
backend framework - giving LLMs complete structured knowledge of your app.

v0.4.3: Initial AI Context Engine release

Usage:
    from aksara.ai.context import build_full_ai_context, AiFullContext
    
    # Build context from app
    context = await build_full_ai_context(app)
    
    # Serialize to JSON
    json_context = context.model_dump()
    
    # Or use the endpoint
    GET /ai/context/full
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TYPE_CHECKING, Union

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from fastapi import FastAPI
    from aksara.model.base import Model
    from aksara.api.viewsets import ModelViewSet


# =============================================================================
# Field & Model Information
# =============================================================================


class AiFieldType(str, Enum):
    """Supported field types for AI context."""
    
    INTEGER = "integer"
    STRING = "string"
    TEXT = "text"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    DATE = "date"
    TIME = "time"
    DECIMAL = "decimal"
    FLOAT = "float"
    UUID = "uuid"
    JSON = "json"
    EMAIL = "email"
    URL = "url"
    FOREIGN_KEY = "foreign_key"
    MANY_TO_MANY = "many_to_many"
    UNKNOWN = "unknown"


class AiModelFieldInfo(BaseModel):
    """Complete field information for AI context."""
    
    name: str = Field(..., description="Field name in Python")
    db_column: str = Field(..., description="Database column name")
    field_type: str = Field(..., description="Field type class name")
    python_type: str = Field(..., description="Python type annotation")
    nullable: bool = Field(default=False, description="Whether NULL is allowed")
    primary_key: bool = Field(default=False, description="Whether this is the primary key")
    unique: bool = Field(default=False, description="Whether values must be unique")
    indexed: bool = Field(default=False, description="Whether the field is indexed")
    default: Optional[Any] = Field(default=None, description="Default value if any")
    max_length: Optional[int] = Field(default=None, description="Maximum length for strings")
    
    # AI-specific metadata
    ai_description: str = Field(default="", description="Human-readable description for AI")
    ai_sensitive: bool = Field(default=False, description="Whether field contains sensitive data")
    ai_agent_writable: bool = Field(default=True, description="Whether AI agents can modify this field")
    
    # Foreign key information
    fk_to_model: Optional[str] = Field(default=None, description="Target model for FK")
    fk_on_delete: Optional[str] = Field(default=None, description="ON DELETE behavior")
    
    # M2M information
    m2m_to_model: Optional[str] = Field(default=None, description="Target model for M2M")
    m2m_through_model: Optional[str] = Field(default=None, description="Through/junction model for M2M")


class AiRelationInfo(BaseModel):
    """Relationship information between models."""
    
    name: str = Field(..., description="Relation name/accessor")
    relation_type: str = Field(..., description="Type: foreign_key, reverse_fk, many_to_many")
    from_model: str = Field(..., description="Source model name")
    to_model: str = Field(..., description="Target model name")
    through_model: Optional[str] = Field(default=None, description="Junction model for M2M")
    on_delete: Optional[str] = Field(default=None, description="ON DELETE behavior")
    nullable: bool = Field(default=False, description="Whether the relation is nullable")


class AiModelInfo(BaseModel):
    """Complete model information for AI context."""
    
    name: str = Field(..., description="Model class name")
    table_name: str = Field(..., description="Database table name")
    app_label: str = Field(default="default", description="App label for namespacing")
    
    # AI metadata
    ai_name: Optional[str] = Field(default=None, description="AI-friendly name override")
    ai_description: str = Field(default="", description="Human-readable model description")
    ai_agent_exposed: bool = Field(default=True, description="Whether AI agents can access this model")
    ai_permissions: List[str] = Field(default_factory=lambda: ["read", "write", "delete"], description="Allowed AI operations")
    
    # Schema information
    fields: List[AiModelFieldInfo] = Field(default_factory=list, description="All model fields")
    primary_key_field: str = Field(default="id", description="Primary key field name")
    
    # Relationships
    relations: List[AiRelationInfo] = Field(default_factory=list, description="Model relationships")


# =============================================================================
# ViewSet & Action Information
# =============================================================================


class AiActionInfo(BaseModel):
    """Custom action information for AI context."""
    
    name: str = Field(..., description="Action method name")
    url_path: str = Field(..., description="URL path for the action")
    methods: List[str] = Field(default_factory=lambda: ["GET"], description="HTTP methods")
    detail: bool = Field(default=False, description="Whether this is a detail action (requires pk)")
    summary: str = Field(default="", description="Short summary for docs")
    description: str = Field(default="", description="Full description")
    ai_exposed: bool = Field(default=True, description="Whether exposed to AI agents")
    permission_classes: List[str] = Field(default_factory=list, description="Permission class names")


class AiViewSetInfo(BaseModel):
    """Complete ViewSet information for AI context."""
    
    name: str = Field(..., description="ViewSet class name")
    model_name: str = Field(..., description="Associated model name")
    prefix: str = Field(..., description="URL prefix")
    tags: List[str] = Field(default_factory=list, description="OpenAPI tags")
    
    # Pagination
    default_limit: int = Field(default=20, description="Default page size")
    max_limit: int = Field(default=100, description="Maximum page size")
    
    # Permissions
    permission_classes: List[str] = Field(default_factory=list, description="ViewSet permission classes")
    ai_exposed: bool = Field(default=True, description="Whether exposed to AI agents")
    
    # CRUD operations
    supports_list: bool = Field(default=True)
    supports_retrieve: bool = Field(default=True)
    supports_create: bool = Field(default=True)
    supports_update: bool = Field(default=True)
    supports_delete: bool = Field(default=True)
    
    # Custom actions
    actions: List[AiActionInfo] = Field(default_factory=list, description="Custom @action methods")
    
    # Serializers
    list_serializer: Optional[str] = Field(default=None, description="List serializer class name")
    retrieve_serializer: Optional[str] = Field(default=None, description="Retrieve serializer class name")
    create_serializer: Optional[str] = Field(default=None, description="Create serializer class name")
    update_serializer: Optional[str] = Field(default=None, description="Update serializer class name")


# =============================================================================
# Route Information
# =============================================================================


class AiRouteInfo(BaseModel):
    """FastAPI route information for AI context."""
    
    path: str = Field(..., description="Full URL path")
    methods: List[str] = Field(default_factory=list, description="HTTP methods")
    name: Optional[str] = Field(default=None, description="Route name")
    summary: str = Field(default="", description="Route summary")
    description: str = Field(default="", description="Route description")
    tags: List[str] = Field(default_factory=list, description="OpenAPI tags")
    deprecated: bool = Field(default=False, description="Whether the route is deprecated")
    
    # Source information
    source_type: str = Field(default="manual", description="manual, viewset, admin, ai")
    viewset_name: Optional[str] = Field(default=None, description="Source ViewSet if applicable")


# =============================================================================
# Migration Information
# =============================================================================


class AiMigrationOperationInfo(BaseModel):
    """Single migration operation for AI context."""
    
    operation_type: str = Field(..., description="Type: CreateTable, AddColumn, etc.")
    table_name: Optional[str] = Field(default=None, description="Affected table")
    details: Dict[str, Any] = Field(default_factory=dict, description="Operation-specific details")


class AiMigrationInfo(BaseModel):
    """Migration file information for AI context."""
    
    name: str = Field(..., description="Migration name (e.g., 0001_initial)")
    app_label: str = Field(default="default", description="App label")
    dependencies: List[str] = Field(default_factory=list, description="Migration dependencies")
    operations_count: int = Field(default=0, description="Number of operations")
    operations_summary: List[str] = Field(default_factory=list, description="Summary of operations")
    applied: bool = Field(default=False, description="Whether migration has been applied")
    checksum: Optional[str] = Field(default=None, description="Migration checksum for change detection")


# =============================================================================
# Admin Information
# =============================================================================


class AiAdminModelInfo(BaseModel):
    """Admin configuration for a model."""
    
    model_name: str = Field(..., description="Model class name")
    app_label: str = Field(default="default", description="App label")
    list_display: List[str] = Field(default_factory=list, description="Fields shown in list view")
    list_filter: List[str] = Field(default_factory=list, description="Filter fields")
    search_fields: List[str] = Field(default_factory=list, description="Searchable fields")
    ordering: List[str] = Field(default_factory=list, description="Default ordering")
    readonly_fields: List[str] = Field(default_factory=list, description="Read-only fields")


class AiAdminInfo(BaseModel):
    """Complete admin site information."""
    
    site_name: str = Field(default="admin", description="Admin site name")
    enabled: bool = Field(default=False, description="Whether admin is enabled")
    registered_models: List[AiAdminModelInfo] = Field(default_factory=list, description="Registered models")
    total_models: int = Field(default=0, description="Total registered models")


# =============================================================================
# Settings & Middleware Information
# =============================================================================


class AiSettingsInfo(BaseModel):
    """Application settings (safe subset) for AI context."""
    
    # App metadata
    app_title: Optional[str] = Field(default=None, description="Application title")
    app_version: Optional[str] = Field(default=None, description="Application version")
    debug: bool = Field(default=False, description="Debug mode enabled")
    
    # Database (no credentials)
    database_configured: bool = Field(default=False, description="Whether database is configured")
    pool_min_size: int = Field(default=5, description="Connection pool min size")
    pool_max_size: int = Field(default=20, description="Connection pool max size")
    
    # AI settings
    ai_enabled: bool = Field(default=False, description="AI features enabled")
    mcp_enabled: bool = Field(default=False, description="MCP protocol enabled")
    ai_debug_enabled: bool = Field(default=True, description="AI debug assistant enabled")
    
    # Apps
    installed_apps: List[str] = Field(default_factory=list, description="Installed application modules")
    apps: List[str] = Field(default_factory=list, description="App labels")
    
    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    log_requests: bool = Field(default=True, description="Request logging enabled")
    log_json: bool = Field(default=False, description="JSON logging format")
    
    # Migrations
    migrations_dir: str = Field(default="migrations", description="Migrations directory")


class AiMiddlewareInfo(BaseModel):
    """Middleware configuration for AI context."""
    
    name: str = Field(..., description="Middleware class name")
    module: str = Field(..., description="Module path")
    order: int = Field(..., description="Execution order (lower = earlier)")
    config: Dict[str, Any] = Field(default_factory=dict, description="Configuration options")


# =============================================================================
# AI Tools & Schemas Information
# =============================================================================


class AiToolSummary(BaseModel):
    """Summary of an AI tool for context."""
    
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    kind: str = Field(..., description="Tool kind: query, mutation, action, admin")
    http_method: str = Field(default="GET", description="HTTP method")
    endpoint: str = Field(default="", description="API endpoint")
    requires_auth: bool = Field(default=False, description="Requires authentication")
    requires_admin: bool = Field(default=False, description="Requires admin")
    ai_tags: List[str] = Field(default_factory=list, description="AI categorization tags")


class AiSchemaInfo(BaseModel):
    """Schema information for AI endpoints."""
    
    name: str = Field(..., description="Schema name")
    description: str = Field(default="", description="Schema description")
    schema_type: str = Field(default="pydantic", description="Type: pydantic, json_schema")
    json_schema: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema representation")


# =============================================================================
# Full Context Model
# =============================================================================


class AiFullContext(BaseModel):
    """
    Complete application context for AI/LLM consumption.
    
    This is the main export model containing all application
    state in a structured, deterministic format.
    """
    
    # Metadata
    framework: str = Field(default="aksara", description="Framework identifier")
    framework_version: str = Field(..., description="Aksara version")
    context_version: str = Field(default="1.0.0", description="Context schema version")
    generated_at: str = Field(..., description="ISO 8601 timestamp")
    checksum: str = Field(..., description="Content checksum for change detection")
    
    # Models & Relationships
    models: List[AiModelInfo] = Field(default_factory=list, description="All registered models")
    model_count: int = Field(default=0, description="Total model count")
    
    # ViewSets & Actions
    viewsets: List[AiViewSetInfo] = Field(default_factory=list, description="All registered ViewSets")
    viewset_count: int = Field(default=0, description="Total ViewSet count")
    
    # Routes
    routes: List[AiRouteInfo] = Field(default_factory=list, description="All API routes")
    route_count: int = Field(default=0, description="Total route count")
    
    # Migrations
    migrations: List[AiMigrationInfo] = Field(default_factory=list, description="Migration history")
    migration_count: int = Field(default=0, description="Total migration count")
    pending_migrations: int = Field(default=0, description="Unapplied migrations")
    
    # Admin
    admin: AiAdminInfo = Field(default_factory=AiAdminInfo, description="Admin configuration")
    
    # Settings
    settings: AiSettingsInfo = Field(default_factory=AiSettingsInfo, description="Application settings")
    
    # Middleware
    middleware: List[AiMiddlewareInfo] = Field(default_factory=list, description="Middleware stack")
    middleware_count: int = Field(default=0, description="Total middleware count")
    
    # AI Tools & Schemas
    ai_tools: List[AiToolSummary] = Field(default_factory=list, description="Available AI tools")
    ai_tool_count: int = Field(default=0, description="Total AI tool count")
    ai_schemas: List[AiSchemaInfo] = Field(default_factory=list, description="AI-related schemas")
    
    # v0.5.13: Per-View AI Hints
    ai_hints: List["AiRouteHintInfo"] = Field(default_factory=list, description="Route-level AI hints")
    ai_hint_count: int = Field(default=0, description="Total AI hint count")
    
    # v0.5.28: AI Hub Summary
    ai_hub_summary: Optional[Dict[str, Any]] = Field(default=None, description="AI Hub provider/model summary")


# v0.5.13: AI Hint Info for Context (simplified version of AiRouteHint)
class AiRouteHintInfo(BaseModel):
    """AI hint information for context export."""
    
    view_name: str = Field(..., description="ViewSet/View class name")
    route_name: str = Field(..., description="Route identifier")
    path: str = Field(..., description="Full URL path")
    methods: List[str] = Field(default_factory=list, description="HTTP methods")
    title: str = Field(..., description="Short label")
    description: str = Field(default="", description="AI-facing description")
    usage_kind: str = Field(default="read_only", description="read_only, write, admin")
    risk_level: str = Field(default="low", description="low, medium, high")
    example_prompt: Optional[str] = Field(None, description="Example user prompt")
    has_example_input: bool = Field(default=False, description="Whether example input exists")
    has_example_output: bool = Field(default=False, description="Whether example output exists")
    recommended_model: Optional[str] = Field(None, description="Recommended AI model")
    recommended_provider: Optional[str] = Field(None, description="Recommended AI provider")


# Update AiFullContext to use forward reference
AiFullContext.model_rebuild()


# =============================================================================
# Context Building Functions
# =============================================================================


def _get_python_type(field: Any) -> str:
    """Get Python type string for a field."""
    from aksara import fields as aksara_fields
    
    type_mapping = {
        aksara_fields.Integer: "int",
        aksara_fields.String: "str",
        aksara_fields.Text: "str",
        aksara_fields.Boolean: "bool",
        aksara_fields.DateTime: "datetime",
        aksara_fields.Decimal: "Decimal",
        aksara_fields.UUID: "UUID",
        aksara_fields.JSON: "dict",
        aksara_fields.Email: "str",
        aksara_fields.URL: "str",
        aksara_fields.ForeignKey: "int",
        aksara_fields.Enum: "str",
        aksara_fields.OneToOne: "int",
        aksara_fields.ManyToMany: "list",
    }
    
    field_class = field.__class__
    return type_mapping.get(field_class, "Any")


def _extract_model_info(model: Type["Model"]) -> AiModelInfo:
    """Extract complete model information."""
    from aksara.fields import ForeignKey, ManyToMany
    
    # Get AI metadata
    ai_meta = getattr(model, '_ai_meta', None)
    
    # Build field info
    fields_info: List[AiModelFieldInfo] = []
    relations_info: List[AiRelationInfo] = []
    pk_field = "id"
    
    for name, field in model._fields.items():
        # Match registry AI export rules: sensitive fields are omitted entirely.
        if getattr(field, 'ai_sensitive', False):
            continue

        # Check if primary key
        if getattr(field, 'primary_key', False):
            pk_field = name
        
        # Build field info
        field_info = AiModelFieldInfo(
            name=name,
            db_column=getattr(field, 'db_column_name', name) if isinstance(field, ForeignKey) else name,
            field_type=field.__class__.__name__,
            python_type=_get_python_type(field),
            nullable=getattr(field, 'nullable', False),
            primary_key=getattr(field, 'primary_key', False),
            unique=getattr(field, 'unique', False),
            indexed=getattr(field, 'indexed', False) or getattr(field, 'db_index', False),
            default=str(field.default) if field.default is not None and not callable(field.default) else None,
            max_length=getattr(field, 'max_length', None),
            ai_description=getattr(field, 'ai_description', '') or '',
            ai_sensitive=getattr(field, 'ai_sensitive', False),
            ai_agent_writable=getattr(field, 'ai_agent_writable', True),
        )
        
        # Foreign key info
        if isinstance(field, ForeignKey):
            to_model = field._to
            if isinstance(to_model, str):
                field_info.fk_to_model = to_model
            else:
                field_info.fk_to_model = to_model.__name__
            field_info.fk_on_delete = getattr(field, 'on_delete', 'CASCADE')
            
            # Add relation
            relations_info.append(AiRelationInfo(
                name=name,
                relation_type="foreign_key",
                from_model=model.__name__,
                to_model=field_info.fk_to_model,
                on_delete=field_info.fk_on_delete,
                nullable=field_info.nullable,
            ))
        
        fields_info.append(field_info)
    
    # Check for M2M relations
    for name in dir(model):
        attr = getattr(model, name, None)
        if isinstance(attr, ManyToMany):
            # Get target model
            to_model = attr._to
            if isinstance(to_model, str):
                to_model_name = to_model
            else:
                to_model_name = to_model.__name__
            
            # Get through model
            through_model = getattr(attr, '_through', None)
            through_name = through_model.__name__ if through_model and not isinstance(through_model, str) else through_model
            
            relations_info.append(AiRelationInfo(
                name=name,
                relation_type="many_to_many",
                from_model=model.__name__,
                to_model=to_model_name,
                through_model=through_name,
            ))
    
    # Build model info
    return AiModelInfo(
        name=model.__name__,
        table_name=model.__tablename__,
        app_label=getattr(model.meta, 'app_label', 'default') if hasattr(model, 'meta') else 'default',
        ai_name=getattr(ai_meta, 'ai_name', None) if ai_meta else None,
        ai_description=(getattr(ai_meta, 'ai_description', None) or '') if ai_meta else '',
        ai_agent_exposed=getattr(ai_meta, 'ai_agent_exposed', True) if ai_meta else True,
        ai_permissions=(getattr(ai_meta, 'ai_permissions', None) or ['read', 'write', 'delete']) if ai_meta else ['read', 'write', 'delete'],
        fields=fields_info,
        primary_key_field=pk_field,
        relations=relations_info,
    )


def _extract_viewset_info(viewset_cls: Type["ModelViewSet"]) -> AiViewSetInfo:
    """Extract complete ViewSet information."""
    from aksara.api.actions import get_action_metadata, is_action
    
    # Instantiate to get resolved values
    try:
        viewset = viewset_cls()
    except Exception:
        # Can't instantiate, use class attributes
        viewset = None
    
    # Get permission class names
    perm_classes = getattr(viewset_cls, 'permission_classes', [])
    perm_names = [
        p.__name__ if isinstance(p, type) else p.__class__.__name__
        for p in perm_classes
    ]
    
    # Extract custom actions
    actions: List[AiActionInfo] = []
    for name in dir(viewset_cls):
        method = getattr(viewset_cls, name, None)
        if method and is_action(method):
            meta = get_action_metadata(method)
            if meta:
                action_perms = meta.get('permission_classes') or []
                action_perm_names = [
                    p.__name__ if isinstance(p, type) else p.__class__.__name__
                    for p in action_perms
                ]
                
                actions.append(AiActionInfo(
                    name=name,
                    url_path=meta.get('url_path', name) or name,
                    methods=meta.get('methods') or ['GET'],
                    detail=meta.get('detail', False),
                    summary=meta.get('summary') or '',
                    description=meta.get('description') or '',
                    ai_exposed=meta.get('ai_exposed', True),
                    permission_classes=action_perm_names,
                ))
    
    # Get serializer info
    list_ser = getattr(viewset_cls, 'list_serializer_class', None)
    retrieve_ser = getattr(viewset_cls, 'retrieve_serializer_class', None)
    create_ser = getattr(viewset_cls, 'create_serializer_class', None)
    update_ser = getattr(viewset_cls, 'update_serializer_class', None)
    
    return AiViewSetInfo(
        name=viewset_cls.__name__,
        model_name=viewset_cls.model.__name__ if viewset_cls.model else "Unknown",
        prefix=viewset.prefix if viewset else getattr(viewset_cls, 'prefix', ''),
        tags=viewset.tags if viewset else getattr(viewset_cls, 'tags', []) or [],
        default_limit=getattr(viewset_cls, 'default_limit', 20),
        max_limit=getattr(viewset_cls, 'max_limit', 100),
        permission_classes=perm_names,
        ai_exposed=getattr(viewset_cls, 'ai_exposed', True),
        actions=actions,
        list_serializer=list_ser.__name__ if list_ser else None,
        retrieve_serializer=retrieve_ser.__name__ if retrieve_ser else None,
        create_serializer=create_ser.__name__ if create_ser else None,
        update_serializer=update_ser.__name__ if update_ser else None,
    )


def _extract_routes_from_app(app: "FastAPI") -> List[AiRouteInfo]:
    """Extract all routes from FastAPI app."""
    routes: List[AiRouteInfo] = []
    
    for route in app.routes:
        # Skip internal/docs routes
        path = getattr(route, 'path', '')
        if path in ('/', '/docs', '/redoc', '/openapi.json'):
            continue
        
        methods = list(getattr(route, 'methods', [])) or ['GET']
        name = getattr(route, 'name', None)
        summary = getattr(route, 'summary', '') or ''
        description = getattr(route, 'description', '') or ''
        tags = list(getattr(route, 'tags', [])) or []
        deprecated = getattr(route, 'deprecated', False) or False
        
        # Determine source type
        source_type = "manual"
        viewset_name = None
        
        if '/admin/' in path:
            source_type = "admin"
        elif '/ai/' in path:
            source_type = "ai"
        elif any(tag for tag in tags):
            # Likely from a ViewSet
            source_type = "viewset"
        
        routes.append(AiRouteInfo(
            path=path,
            methods=methods,
            name=name,
            summary=summary,
            description=description,
            tags=tags,
            deprecated=deprecated,
            source_type=source_type,
            viewset_name=viewset_name,
        ))
    
    # Sort deterministically
    routes.sort(key=lambda r: (r.path, ','.join(sorted(r.methods))))
    
    return routes


def _extract_settings_info() -> AiSettingsInfo:
    """Extract safe settings information."""
    from aksara.conf import settings
    
    return AiSettingsInfo(
        app_title=settings.app_title,
        app_version=settings.app_version,
        debug=settings.debug,
        database_configured=settings.database_url is not None,
        pool_min_size=settings.pool_min_size,
        pool_max_size=settings.pool_max_size,
        ai_enabled=settings.ai_enabled,
        mcp_enabled=settings.mcp_enabled,
        ai_debug_enabled=getattr(settings, 'ai_debug_enabled', True),
        installed_apps=list(settings.installed_apps),
        apps=list(settings.apps),
        log_level=settings.log_level,
        log_requests=settings.log_requests,
        log_json=settings.log_json,
        migrations_dir=settings.migrations_dir,
    )


def _extract_admin_info() -> AiAdminInfo:
    """Extract admin site information."""
    try:
        from aksara.contrib.admin import site
        
        if not site.registry:
            return AiAdminInfo(enabled=False)
        
        registered_models: List[AiAdminModelInfo] = []
        
        for model, admin in site.registry.items():
            registered_models.append(AiAdminModelInfo(
                model_name=model.__name__,
                app_label=getattr(model.meta, 'app_label', 'default') if hasattr(model, 'meta') else 'default',
                list_display=list(getattr(admin, 'list_display', [])),
                list_filter=list(getattr(admin, 'list_filter', [])),
                search_fields=list(getattr(admin, 'search_fields', [])),
                ordering=list(getattr(admin, 'ordering', [])),
                readonly_fields=list(getattr(admin, 'readonly_fields', [])),
            ))
        
        # Sort deterministically
        registered_models.sort(key=lambda m: (m.app_label, m.model_name))
        
        return AiAdminInfo(
            site_name=site.name,
            enabled=True,
            registered_models=registered_models,
            total_models=len(registered_models),
        )
    except ImportError:
        return AiAdminInfo(enabled=False)


def _extract_middleware_info(app: "FastAPI") -> List[AiMiddlewareInfo]:
    """Extract middleware stack information."""
    middleware: List[AiMiddlewareInfo] = []
    
    # Check user_middleware attribute (Starlette/FastAPI)
    user_middleware = getattr(app, 'user_middleware', [])
    
    for i, mw in enumerate(user_middleware):
        mw_cls = getattr(mw, 'cls', None) or mw
        if hasattr(mw_cls, '__name__'):
            name = mw_cls.__name__
            module = mw_cls.__module__
        else:
            name = str(mw_cls)
            module = ""
        
        # Get config/kwargs
        config = dict(getattr(mw, 'kwargs', {})) if hasattr(mw, 'kwargs') else {}
        
        middleware.append(AiMiddlewareInfo(
            name=name,
            module=module,
            order=i,
            config=config,
        ))
    
    return middleware


def _extract_ai_tools_info(app: "FastAPI") -> List[AiToolSummary]:
    """Extract AI tools information from registry."""
    tools: List[AiToolSummary] = []
    
    # Get registry from app
    registry = getattr(app.state, 'ai_registry', None)
    if not registry:
        return tools
    
    for tool in registry.all_tools():
        tools.append(AiToolSummary(
            name=tool.name,
            description=tool.description or '',
            kind=tool.kind,
            http_method=tool.http_method,
            endpoint=tool.endpoint,
            requires_auth=tool.requires_auth,
            requires_admin=tool.requires_admin,
            ai_tags=list(tool.ai_tags) if tool.ai_tags else [],
        ))
    
    # Sort deterministically
    tools.sort(key=lambda t: t.name)
    
    return tools


def _extract_ai_schemas_info() -> List[AiSchemaInfo]:
    """Extract AI-related schema information."""
    schemas: List[AiSchemaInfo] = []
    
    try:
        # Query plan schema
        from aksara.ai.query import AiQueryPlan, get_query_plan_schema
        schemas.append(AiSchemaInfo(
            name="AiQueryPlan",
            description="Schema for structured query plans",
            schema_type="pydantic",
            json_schema=get_query_plan_schema(),
        ))
    except ImportError:
        pass
    
    try:
        # Codegen schemas
        from aksara.ai.codegen import get_codegen_schemas
        codegen_schemas = get_codegen_schemas()
        for name, schema in codegen_schemas.items():
            schemas.append(AiSchemaInfo(
                name=name,
                description=f"Code generation schema: {name}",
                schema_type="pydantic",
                json_schema=schema,
            ))
    except ImportError:
        pass
    
    return schemas


def _extract_ai_hints_info(app: "FastAPI") -> List["AiRouteHintInfo"]:
    """
    Extract AI hints from the application.
    
    v0.5.13: Looks for routes/viewsets decorated with @ai_route_hint
    and converts them to AiRouteHintInfo for context export.
    """
    hints_info: List[AiRouteHintInfo] = []
    
    try:
        from aksara.ai.hints import extract_hints_from_app
        
        hints = extract_hints_from_app(app)
        
        for hint in hints:
            hints_info.append(AiRouteHintInfo(
                view_name=hint.view_name,
                route_name=hint.route_name,
                path=hint.path,
                methods=hint.methods,
                title=hint.title,
                description=hint.description,
                usage_kind=hint.usage_kind,
                risk_level=hint.risk_level,
                example_prompt=hint.example_prompt,
                has_example_input=hint.example_input is not None,
                has_example_output=hint.example_output is not None,
                recommended_model=hint.recommended_model,
                recommended_provider=hint.recommended_provider,
            ))
    except ImportError:
        pass
    except Exception as e:
        # Log but don't fail context building
        import logging
        logging.getLogger("aksara.ai.context").warning(f"Error extracting AI hints: {e}")
    
    return hints_info


def _extract_ai_hub_summary() -> Optional[Dict[str, Any]]:
    """
    v0.5.28: Extract AI Hub configuration summary for context.

    Returns a safe dict with provider status and default model assignments,
    or None if the hub settings module is not available.
    """
    try:
        from aksara.ai.hub_settings import load_aihub_settings
        hub = load_aihub_settings()
        providers = []
        for p in hub.providers:
            providers.append({
                "kind": p.kind,
                "configured": p.is_configured,
                "modes": p.get_supported_modes(),
            })
        return {
            "active_provider": hub.active_provider,
            "configured_count": sum(1 for p in hub.providers if p.is_configured),
            "providers": providers,
            "defaults": hub.defaults.model_dump() if hub.defaults else {},
        }
    except Exception:
        return None


def _compute_checksum(data: Dict[str, Any]) -> str:
    """Compute deterministic checksum for context data."""
    # Remove volatile fields
    stable_data = {k: v for k, v in data.items() if k not in ('generated_at', 'checksum')}
    
    # Sort keys for determinism
    json_str = json.dumps(stable_data, sort_keys=True, default=str)
    
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


async def build_full_ai_context(
    app: "FastAPI",
    include_routes: bool = True,
    include_migrations: bool = True,
    include_admin: bool = True,
    include_ai_tools: bool = True,
) -> AiFullContext:
    """
    Build complete AI context from the application.
    
    This function aggregates all application state into a structured
    format suitable for LLM consumption.
    
    Args:
        app: The FastAPI/Aksara application instance
        include_routes: Whether to include route information
        include_migrations: Whether to include migration history
        include_admin: Whether to include admin configuration
        include_ai_tools: Whether to include AI tool registry
        
    Returns:
        AiFullContext with complete application state
    """
    import aksara
    from aksara.registry import get_models
    
    # Extract models
    models: List[AiModelInfo] = []
    # Match registry AI exposure rules: hidden models stay out of exported context.
    for model_cls in get_models(ai_exposed_only=True):
        models.append(_extract_model_info(model_cls))
    
    # Sort deterministically
    models.sort(key=lambda m: (m.app_label, m.name))
    
    # Extract ViewSets
    viewsets: List[AiViewSetInfo] = []
    viewset_registry = getattr(app.state, 'viewset_registry', None)
    if viewset_registry:
        for vs_cls in viewset_registry:
            viewsets.append(_extract_viewset_info(vs_cls))
    
    # Sort deterministically
    viewsets.sort(key=lambda v: v.name)
    
    # Extract routes
    routes: List[AiRouteInfo] = []
    if include_routes:
        routes = _extract_routes_from_app(app)
    
    # Extract migrations
    migrations: List[AiMigrationInfo] = []
    pending_count = 0
    if include_migrations:
        # Note: Full migration extraction requires async DB access
        # For now, just indicate migration directory
        pass
    
    # Extract admin
    admin = AiAdminInfo(enabled=False)
    if include_admin:
        admin = _extract_admin_info()
    
    # Extract settings
    settings_info = _extract_settings_info()
    
    # Extract middleware
    middleware = _extract_middleware_info(app)
    
    # Extract AI tools
    ai_tools: List[AiToolSummary] = []
    if include_ai_tools:
        ai_tools = _extract_ai_tools_info(app)
    
    # Extract AI schemas
    ai_schemas = _extract_ai_schemas_info()
    
    # v0.5.13: Extract AI hints
    ai_hints: List[AiRouteHintInfo] = []
    ai_hints = _extract_ai_hints_info(app)
    
    # v0.5.28: Extract AI Hub summary
    ai_hub_summary = _extract_ai_hub_summary()
    
    # Build context without checksum first
    context_data = {
        "framework": "aksara",
        "framework_version": aksara.__version__,
        "context_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "checksum": "",  # Placeholder
        "models": [m.model_dump() for m in models],
        "model_count": len(models),
        "viewsets": [v.model_dump() for v in viewsets],
        "viewset_count": len(viewsets),
        "routes": [r.model_dump() for r in routes],
        "route_count": len(routes),
        "migrations": [m.model_dump() for m in migrations],
        "migration_count": len(migrations),
        "pending_migrations": pending_count,
        "admin": admin.model_dump(),
        "settings": settings_info.model_dump(),
        "middleware": [m.model_dump() for m in middleware],
        "middleware_count": len(middleware),
        "ai_tools": [t.model_dump() for t in ai_tools],
        "ai_tool_count": len(ai_tools),
        "ai_schemas": [s.model_dump() for s in ai_schemas],
        "ai_hints": [h.model_dump() for h in ai_hints],
        "ai_hint_count": len(ai_hints),
        "ai_hub_summary": ai_hub_summary,
    }
    
    # Compute checksum
    checksum = _compute_checksum(context_data)
    
    return AiFullContext(
        framework="aksara",
        framework_version=aksara.__version__,
        context_version="1.0.0",
        generated_at=context_data["generated_at"],
        checksum=checksum,
        models=models,
        model_count=len(models),
        viewsets=viewsets,
        viewset_count=len(viewsets),
        routes=routes,
        route_count=len(routes),
        migrations=migrations,
        migration_count=len(migrations),
        pending_migrations=pending_count,
        admin=admin,
        settings=settings_info,
        middleware=middleware,
        middleware_count=len(middleware),
        ai_tools=ai_tools,
        ai_tool_count=len(ai_tools),
        ai_schemas=ai_schemas,
        ai_hints=ai_hints,
        ai_hint_count=len(ai_hints),
        ai_hub_summary=ai_hub_summary,
    )


def build_full_ai_context_sync(
    app: "FastAPI",
    include_routes: bool = True,
    include_migrations: bool = True,
    include_admin: bool = True,
    include_ai_tools: bool = True,
) -> AiFullContext:
    """
    Synchronous version of build_full_ai_context.
    
    Useful for non-async contexts like CLI tools.
    """
    import asyncio

    try:
        asyncio.get_running_loop()
        # Match other sync AI helpers: run in a worker thread if a loop exists.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(
                asyncio.run,
                build_full_ai_context(
                    app,
                    include_routes=include_routes,
                    include_migrations=include_migrations,
                    include_admin=include_admin,
                    include_ai_tools=include_ai_tools,
                ),
            )
            return future.result()
    except RuntimeError:
        return asyncio.run(
            build_full_ai_context(
                app,
                include_routes=include_routes,
                include_migrations=include_migrations,
                include_admin=include_admin,
                include_ai_tools=include_ai_tools,
            )
        )


__all__ = [
    # Field Types
    "AiFieldType",
    # Model info
    "AiModelFieldInfo",
    "AiRelationInfo",
    "AiModelInfo",
    # ViewSet info
    "AiActionInfo",
    "AiViewSetInfo",
    # Route info
    "AiRouteInfo",
    # Migration info
    "AiMigrationOperationInfo",
    "AiMigrationInfo",
    # Admin info
    "AiAdminModelInfo",
    "AiAdminInfo",
    # Settings & Middleware
    "AiSettingsInfo",
    "AiMiddlewareInfo",
    # AI Tools & Schemas
    "AiToolSummary",
    "AiSchemaInfo",
    # v0.5.13: AI Hints
    "AiRouteHintInfo",
    # Full context
    "AiFullContext",
    # Builder functions
    "build_full_ai_context",
    "build_full_ai_context_sync",
]
