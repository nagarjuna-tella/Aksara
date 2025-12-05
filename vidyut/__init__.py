"""
⚡ Vidyut - Async Framework

A lightweight, async-native ORM designed specifically for PostgreSQL and FastAPI.
"""

from vidyut.model.base import Model
from vidyut import fields
from vidyut.db import Database
from vidyut.registry import (
    ModelRegistry,
    get_models,
    get_model_meta,
    get_model_fields,
    get_model_schema_for_ai,
    get_all_schemas_for_ai,
)
from vidyut.manager import DoesNotExist, MultipleObjectsReturned
from vidyut.conf import Settings, settings, configure
from vidyut.exceptions import (
    VidyutError,
    DatabaseError,
    ConnectionError,
    QueryError,
    UniqueConstraintError,
    ForeignKeyConstraintError,
    NotNullConstraintError,
    CheckConstraintError,
)

# on_delete constants (Django-style)
from vidyut.fields import CASCADE, SET_NULL, RESTRICT, PROTECT

# v0.3: API layer
from vidyut.api import (
    ModelViewSet,
    include_viewset,
    generate_create_schema,
    generate_update_schema,
    generate_read_schema,
    get_schemas_for_model,
    # v0.3.1: Action decorator
    action,
    # v0.3.2: Serializer
    ModelSerializer,
    # v0.3.14: ViewSet auto-registration
    discover_viewsets,
    include_app_viewsets,
    include_all_app_viewsets,
)

# v0.3.3: Migration layer
from vidyut.migrations import (
    Migration,
    operations as migration_operations,
)

# v0.3.6: Core discovery
from vidyut.core.discovery import (
    discover_viewsets_from_module,
    auto_discover_viewsets,
)

# v0.3.14: App discovery
from vidyut.apps import (
    load_app_models,
    get_app_models,
    get_all_app_labels,
)

# Re-export FastAPI components with Vidyut enhancements
from vidyut.app import (
    Vidyut,
    FastAPI,
    APIRouter,
    Request,
    Response,
    HTTPException,
    Depends,
    Query,
    Path,
    Header,
    File,
    Form,
    UploadFile,
    BackgroundTasks,
    WebSocket,
    status,
    JSONResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    FileResponse,
    StreamingResponse,
    StaticFiles,
    Jinja2Templates,
    Middleware,
)

# v0.3.8: Relationships & Delete Semantics
from vidyut.relations import (
    OnDelete,
    RelationRegistry,
    RelationMeta,
)
from vidyut.exceptions import RestrictedError
from vidyut.model.base import finalize_relations

# v0.3.10: Identity & Permissions
from vidyut.identity import VidyutUserProtocol, AnonymousUser
from vidyut.permissions import (
    BasePermission,
    AllowAny,
    IsAuthenticated,
    IsAdminUser,
    IsActiveUser,
    IsOwnerOrReadOnly,
    DenyAI,
    OperationPermission,
    AND,
    OR,
    check_permissions,
)

__version__ = "0.3.18"
__all__ = [
    # Vidyut ORM
    "Model",
    "fields", 
    "Database",
    "ModelRegistry",
    "DoesNotExist",
    "MultipleObjectsReturned",
    # on_delete constants (Django-style)
    "CASCADE",
    "SET_NULL",
    "RESTRICT",
    "PROTECT",
    # Settings & Configuration
    "Settings",
    "settings",
    "configure",
    # Exceptions
    "VidyutError",
    "DatabaseError",
    "ConnectionError",
    "QueryError",
    "UniqueConstraintError",
    "ForeignKeyConstraintError",
    "NotNullConstraintError",
    "CheckConstraintError",
    # AI Metadata Helpers
    "get_models",
    "get_model_meta",
    "get_model_fields",
    "get_model_schema_for_ai",
    "get_all_schemas_for_ai",
    # v0.3: API Layer
    "ModelViewSet",
    "include_viewset",
    "generate_create_schema",
    "generate_update_schema",
    "generate_read_schema",
    "get_schemas_for_model",
    # v0.3.1: Action decorator
    "action",
    # v0.3.2: Serializer
    "ModelSerializer",
    # v0.3.3: Migrations
    "Migration",
    "migration_operations",
    # v0.3.6: Core Discovery
    "discover_viewsets_from_module",
    "auto_discover_viewsets",
    # v0.3.14: App & ViewSet Auto-Discovery
    "load_app_models",
    "get_app_models",
    "get_all_app_labels",
    "discover_viewsets",
    "include_app_viewsets",
    "include_all_app_viewsets",
    # Vidyut App (enhanced FastAPI)
    "Vidyut",
    # FastAPI re-exports
    "FastAPI",
    "APIRouter",
    "Request",
    "Response",
    "HTTPException",
    "Depends",
    "Query",
    "Path",
    "Header",
    "File",
    "Form",
    "UploadFile",
    "BackgroundTasks",
    "WebSocket",
    "status",
    "JSONResponse",
    "HTMLResponse",
    "PlainTextResponse",
    "RedirectResponse",
    "FileResponse",
    "StreamingResponse",
    "StaticFiles",
    "Jinja2Templates",
    "Middleware",
    # v0.3.8: Relationships & Delete Semantics
    "OnDelete",
    "RelationRegistry",
    "RelationMeta",
    "RestrictedError",
    "finalize_relations",
    # v0.3.10: Identity & Permissions
    "VidyutUserProtocol",
    "AnonymousUser",
    "BasePermission",
    "AllowAny",
    "IsAuthenticated",
    "IsAdminUser",
    "IsActiveUser",
    "IsOwnerOrReadOnly",
    "DenyAI",
    "OperationPermission",
    "AND",
    "OR",
    "check_permissions",
]
