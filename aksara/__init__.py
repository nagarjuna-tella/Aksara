"""
⚡ Aksara - Async Framework

A lightweight, async-native ORM designed specifically for PostgreSQL and FastAPI.
"""

from aksara.model.base import Model
from aksara import fields
from aksara.db import (
    Aggregate,
    Avg,
    Count,
    Database,
    F,
    Max,
    Min,
    Q,
    Sum,
    TransactionManager,
    atomic,
    transaction,
)
from aksara.registry import (
    ModelRegistry,
    get_models,
    get_model_meta,
    get_model_fields,
    get_model_schema_for_ai,
    get_all_schemas_for_ai,
)
from aksara.manager import DoesNotExist, MultipleObjectsReturned
from aksara.conf import Settings, settings, configure
from aksara.i18n import (
    LazyString,
    _,
    activate_locale,
    activate_timezone,
    get_locale,
    get_timezone,
    get_timezone_name,
    localtime,
    parse_accept_language,
    reset_locale,
    reset_timezone,
    translate,
)
from aksara.contenttypes import (
    ContentType,
    clear_content_type_cache,
    get_content_type_by_id,
    get_content_type_for_model,
    get_model_for_content_type,
    sync_content_types,
)
from aksara.workflows import DurableStep, DurableStepState
from aksara.storage import FieldFile, Storage, FileSystemStorage, S3Storage, get_default_storage
from aksara.exceptions import (
    AksaraError,
    DatabaseError,
    ConnectionError,
    QueryError,
    UniqueConstraintError,
    ForeignKeyConstraintError,
    NotNullConstraintError,
    CheckConstraintError,
    ValidationError,
    ConfigurationError,
)

# on_delete constants (Django-style)
from aksara.fields import CASCADE, SET_NULL, RESTRICT, PROTECT

# v0.3: API layer
from aksara.api import (
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
from aksara.migrations import (
    Migration,
    operations as migration_operations,
)

# v0.3.6: Core discovery
from aksara.core.discovery import (
    discover_viewsets_from_module,
    auto_discover_viewsets,
)
from aksara.core.mail import (
    EmailMessage,
    BaseEmailBackend,
    ConsoleBackend,
    LocMemBackend,
    SMTPBackend,
    get_email_backend,
    send_mail,
    send_mass_mail,
    outbox,
    reset_outbox,
)

# v0.3.14: App discovery
from aksara.apps import (
    load_app_models,
    get_app_models,
    get_all_app_labels,
)

# Re-export FastAPI components with Aksara enhancements
from aksara.app import (
    Aksara,
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

# v0.5.44: DX Features
from aksara.fixtures import dump_data, load_data, dump_database
from aksara.contrib.soft_delete import SoftDeleteModel, with_deleted, only_deleted
from aksara.tenancy import TenantModel

# v0.3.8: Relationships & Delete Semantics
from aksara.relations import (
    OnDelete,
    RelationRegistry,
    RelationMeta,
)
from aksara.exceptions import RestrictedError
from aksara.model.base import finalize_relations

# v0.3.10: Identity & Permissions
from aksara.identity import AksaraUserProtocol, AnonymousUser
from aksara.permissions import (
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

# v0.4.0: AI Mode
from aksara.ai import (
    AiTool,
    AiToolParam,
    AiToolRegistry,
    discover_tools_from_viewset,
    get_ai_tools_for_request,
    export_tools_as_generic,
    export_tools_as_mcp,
)

# v0.4.1: AI Debug exports
from aksara.ai.debug import (
    AiDebugContext,
    AiDebugSuggestion,
    build_ai_debug_context,
    RuleBasedAiDebugAdvisor,
)

from aksara._version import __version__
__all__ = [
    # Aksara ORM
    "Model",
    "fields", 
    "Database",
    "Q",
    "F",
    "Aggregate",
    "Count",
    "Sum",
    "Avg",
    "Min",
    "Max",
    "TransactionManager",
    "atomic",
    "transaction",
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
    "LazyString",
    "_",
    "activate_locale",
    "activate_timezone",
    "FieldFile",
    "Storage",
    "FileSystemStorage",
    "S3Storage",
    "get_locale",
    "get_default_storage",
    "get_timezone",
    "get_timezone_name",
    "localtime",
    "parse_accept_language",
    "EmailMessage",
    "BaseEmailBackend",
    "ConsoleBackend",
    "LocMemBackend",
    "SMTPBackend",
    "get_email_backend",
    "send_mail",
    "send_mass_mail",
    "outbox",
    "reset_locale",
    "reset_outbox",
    "reset_timezone",
    "translate",
    "ContentType",
    "clear_content_type_cache",
    "get_content_type_by_id",
    "get_content_type_for_model",
    "get_model_for_content_type",
    "sync_content_types",
    "DurableStep",
    "DurableStepState",
    # Exceptions
    "AksaraError",
    "DatabaseError",
    "ConnectionError",
    "QueryError",
    "UniqueConstraintError",
    "ForeignKeyConstraintError",
    "NotNullConstraintError",
    "CheckConstraintError",
    "ValidationError",
    "ConfigurationError",
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
    # Aksara App (enhanced FastAPI)
    "Aksara",
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
    "AksaraUserProtocol",
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
    # v0.4.0: AI Mode
    "AiTool",
    "AiToolParam",
    "AiToolRegistry",
    "discover_tools_from_viewset",
    "get_ai_tools_for_request",
    "export_tools_as_generic",
    "export_tools_as_mcp",
    # v0.5.44: DX Features
    "dump_data",
    "load_data",
    "dump_database",
    "SoftDeleteModel",
    "TenantModel",
    "with_deleted",
    "only_deleted",
]
