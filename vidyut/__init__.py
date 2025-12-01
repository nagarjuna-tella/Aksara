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
)

# v0.3.3: Migration layer
from vidyut.migrations import (
    Migration,
    operations as migration_operations,
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

__version__ = "0.3.5"
__all__ = [
    # Vidyut ORM
    "Model",
    "fields", 
    "Database",
    "ModelRegistry",
    "DoesNotExist",
    "MultipleObjectsReturned",
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
]
