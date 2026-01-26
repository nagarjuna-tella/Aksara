"""
AI Debug Assistant for Vidyut.

This module provides AI-friendly error context and rule-based suggestions
to help diagnose and fix errors quickly.
"""
from __future__ import annotations

import re
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from starlette.requests import Request
    from vidyut.debug.handlers import DebugContext


# =============================================================================
# Pydantic Models for AI Debug Context
# =============================================================================


class AiStackFrame(BaseModel):
    """A single stack frame in the traceback."""
    
    filename: str = Field(..., description="File path where the frame occurred")
    lineno: int = Field(..., description="Line number in the file")
    name: str = Field(..., description="Function or method name")
    line: str = Field(default="", description="Source code line")
    is_library: bool = Field(default=False, description="Whether this is library code")
    module: Optional[str] = Field(default=None, description="Module name if available")
    locals_preview: Optional[dict[str, str]] = Field(
        default=None,
        description="Preview of local variables (string representations)"
    )
    
    model_config = {"extra": "forbid"}


class AiExceptionInfo(BaseModel):
    """Structured exception information."""
    
    type: str = Field(..., description="Exception class name (e.g., 'ValueError')")
    message: str = Field(..., description="Exception message")
    full_type: str = Field(..., description="Full qualified type (e.g., 'builtins.ValueError')")
    detail: Optional[str] = Field(default=None, description="Additional detail if available")
    
    # Classification flags
    is_validation_error: bool = Field(default=False, description="Pydantic/FastAPI validation error")
    is_db_error: bool = Field(default=False, description="Database-related error")
    is_auth_error: bool = Field(default=False, description="Authentication/authorization error")
    is_not_found: bool = Field(default=False, description="Resource not found error")
    is_timeout: bool = Field(default=False, description="Timeout error")
    is_connection_error: bool = Field(default=False, description="Connection-related error")
    
    model_config = {"extra": "forbid"}


class AiRequestInfo(BaseModel):
    """Request information for debugging."""
    
    method: str = Field(..., description="HTTP method (GET, POST, etc.)")
    url: str = Field(..., description="Full request URL")
    path: str = Field(..., description="Request path")
    path_params: dict[str, Any] = Field(default_factory=dict, description="Path parameters")
    query_params: dict[str, Any] = Field(default_factory=dict, description="Query parameters")
    headers: dict[str, str] = Field(default_factory=dict, description="Request headers (filtered)")
    body_preview: Optional[str] = Field(default=None, description="Request body preview (truncated)")
    content_type: Optional[str] = Field(default=None, description="Content-Type header")
    
    model_config = {"extra": "forbid"}


class AiViewInfo(BaseModel):
    """Information about the view/viewset handling the request."""
    
    viewset_name: Optional[str] = Field(default=None, description="ViewSet class name")
    action_name: Optional[str] = Field(default=None, description="Action method name")
    route_name: Optional[str] = Field(default=None, description="Named route")
    endpoint_path: Optional[str] = Field(default=None, description="Endpoint path pattern")
    
    model_config = {"extra": "forbid"}


class AiMigrationInfo(BaseModel):
    """Migration status information."""
    
    pending_migrations: list[str] = Field(default_factory=list, description="List of pending migrations")
    last_applied: Optional[str] = Field(default=None, description="Last applied migration")
    
    model_config = {"extra": "forbid"}


class AiEnvInfo(BaseModel):
    """Environment information for debugging."""
    
    python_version: str = Field(..., description="Python version")
    vidyut_version: str = Field(..., description="Vidyut framework version")
    debug_mode: bool = Field(..., description="Whether debug mode is enabled")
    database_url_masked: Optional[str] = Field(default=None, description="Masked database URL")
    installed_apps: list[str] = Field(default_factory=list, description="Installed Vidyut apps")
    
    model_config = {"extra": "forbid"}


class AiToolRef(BaseModel):
    """Reference to a related AI tool that might help."""
    
    tool_name: str = Field(..., description="Name of the AI tool")
    reason: str = Field(..., description="Why this tool might help")
    
    model_config = {"extra": "forbid"}


class AiDebugSuggestion(BaseModel):
    """A suggestion for fixing the error."""
    
    title: str = Field(..., description="Short title for the suggestion")
    description: str = Field(..., description="Detailed explanation")
    code_snippet: Optional[str] = Field(default=None, description="Example code to fix the issue")
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence level (0.0-1.0)"
    )
    category: str = Field(
        default="general",
        description="Category: 'code', 'config', 'database', 'permission', 'validation'"
    )
    doc_url: Optional[str] = Field(default=None, description="Documentation URL if relevant")
    
    model_config = {"extra": "forbid"}


class AiDebugContext(BaseModel):
    """
    Complete AI-friendly debug context.
    
    This is the main payload that can be passed to an LLM for analysis.
    It contains structured information about the error, request, environment,
    and any rule-based suggestions.
    """
    
    # Identifiers
    request_id: Optional[str] = Field(default=None, description="Unique request identifier")
    timestamp: str = Field(..., description="ISO timestamp when error occurred")
    
    # Exception details
    exception: AiExceptionInfo = Field(..., description="Exception information")
    traceback_frames: list[AiStackFrame] = Field(
        default_factory=list,
        description="Stack trace frames (most recent last)"
    )
    traceback_text: str = Field(default="", description="Full traceback as text")
    
    # HTTP context
    status_code: int = Field(..., description="HTTP status code")
    request: AiRequestInfo = Field(..., description="Request information")
    
    # Application context
    view: AiViewInfo = Field(default_factory=AiViewInfo, description="View/ViewSet information")
    tenant_id: Optional[str] = Field(default=None, description="Tenant identifier if multi-tenant")
    user_id: Optional[str] = Field(default=None, description="User identifier if authenticated")
    
    # Environment
    environment: AiEnvInfo = Field(..., description="Environment information")
    migrations: Optional[AiMigrationInfo] = Field(default=None, description="Migration status")
    
    # AI assistance
    suggestions: list[AiDebugSuggestion] = Field(
        default_factory=list,
        description="Rule-based suggestions for fixing the error"
    )
    related_tools: list[AiToolRef] = Field(
        default_factory=list,
        description="AI tools that might help investigate"
    )
    
    # LLM prompt hint
    prompt_hint: str = Field(
        default="",
        description="A hint for the LLM on how to analyze this error"
    )
    
    model_config = {"extra": "forbid"}
    
    def to_llm_prompt(self) -> str:
        """Generate a formatted prompt for an LLM to analyze this error."""
        parts = [
            "# Error Analysis Request",
            "",
            f"## Exception: {self.exception.type}",
            f"**Message:** {self.exception.message}",
            f"**Status Code:** {self.status_code}",
            "",
            f"## Request",
            f"- Method: {self.request.method}",
            f"- URL: {self.request.url}",
        ]
        
        if self.request.path_params:
            parts.append(f"- Path Params: {self.request.path_params}")
        if self.request.query_params:
            parts.append(f"- Query Params: {self.request.query_params}")
        
        parts.extend([
            "",
            "## Traceback",
            "```",
            self.traceback_text or "(no traceback)",
            "```",
            "",
        ])
        
        if self.suggestions:
            parts.append("## Suggestions")
            for i, s in enumerate(self.suggestions, 1):
                parts.append(f"{i}. **{s.title}** (confidence: {s.confidence:.0%})")
                parts.append(f"   {s.description}")
            parts.append("")
        
        if self.prompt_hint:
            parts.extend([
                "## Analysis Hint",
                self.prompt_hint,
                "",
            ])
        
        parts.append("Please analyze this error and provide:")
        parts.append("1. Root cause explanation")
        parts.append("2. Step-by-step fix")
        parts.append("3. Prevention tips")
        
        return "\n".join(parts)


# =============================================================================
# Debug Advisors
# =============================================================================


class BaseAiDebugAdvisor(ABC):
    """Base class for AI debug advisors."""
    
    @abstractmethod
    def analyze(self, context: AiDebugContext) -> list[AiDebugSuggestion]:
        """
        Analyze the debug context and return suggestions.
        
        Args:
            context: The AI debug context to analyze.
            
        Returns:
            A list of suggestions for fixing the error.
        """
        pass
    
    @abstractmethod
    def get_related_tools(self, context: AiDebugContext) -> list[AiToolRef]:
        """
        Get AI tools that might help investigate the error.
        
        Args:
            context: The AI debug context to analyze.
            
        Returns:
            A list of related AI tools.
        """
        pass


class RuleBasedAiDebugAdvisor(BaseAiDebugAdvisor):
    """Rule-based advisor that provides suggestions based on error patterns."""
    
    def analyze(self, context: AiDebugContext) -> list[AiDebugSuggestion]:
        """Analyze context and return rule-based suggestions."""
        suggestions: list[AiDebugSuggestion] = []
        
        exc = context.exception
        msg_lower = exc.message.lower()
        
        # Validation errors
        if exc.is_validation_error:
            suggestions.extend(self._analyze_validation_error(context))
        
        # Database errors
        if exc.is_db_error:
            suggestions.extend(self._analyze_db_error(context))
        
        # Authentication/Authorization errors
        if exc.is_auth_error:
            suggestions.extend(self._analyze_auth_error(context))
        
        # Not found errors
        if exc.is_not_found:
            suggestions.extend(self._analyze_not_found_error(context))
        
        # Connection errors
        if exc.is_connection_error:
            suggestions.extend(self._analyze_connection_error(context))
        
        # Timeout errors
        if exc.is_timeout:
            suggestions.append(AiDebugSuggestion(
                title="Timeout Detected",
                description="The operation timed out. Consider increasing timeout settings or optimizing the operation.",
                confidence=0.8,
                category="config",
            ))
        
        # Generic pattern matching
        suggestions.extend(self._analyze_patterns(context))
        
        # Sort by confidence
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        
        return suggestions[:5]  # Return top 5 suggestions
    
    def get_related_tools(self, context: AiDebugContext) -> list[AiToolRef]:
        """Get related AI tools based on the error type."""
        tools: list[AiToolRef] = []
        exc = context.exception
        
        if exc.is_db_error:
            tools.append(AiToolRef(
                tool_name="list",
                reason="Check if the model/table exists and has the expected schema"
            ))
        
        if exc.is_validation_error:
            tools.append(AiToolRef(
                tool_name="retrieve",
                reason="Verify the expected data format for this resource"
            ))
        
        if exc.is_auth_error:
            tools.append(AiToolRef(
                tool_name="list",
                reason="Check what permissions are required for this action"
            ))
        
        return tools
    
    def _analyze_validation_error(self, context: AiDebugContext) -> list[AiDebugSuggestion]:
        """Analyze validation errors."""
        suggestions = []
        msg = context.exception.message
        
        # Missing required field
        if "required" in msg.lower() or "missing" in msg.lower():
            suggestions.append(AiDebugSuggestion(
                title="Missing Required Field",
                description="The request is missing a required field. Check the request body against the schema.",
                confidence=0.9,
                category="validation",
            ))
        
        # Type errors
        if "type" in msg.lower() or "expected" in msg.lower():
            suggestions.append(AiDebugSuggestion(
                title="Type Mismatch",
                description="A field has the wrong type. Check that all fields match the expected types.",
                confidence=0.85,
                category="validation",
            ))
        
        # Extra fields
        if "extra" in msg.lower() or "unexpected" in msg.lower():
            suggestions.append(AiDebugSuggestion(
                title="Unexpected Field",
                description="The request contains a field that is not expected. Remove extra fields or check for typos.",
                confidence=0.85,
                category="validation",
            ))
        
        return suggestions
    
    def _analyze_db_error(self, context: AiDebugContext) -> list[AiDebugSuggestion]:
        """Analyze database errors."""
        suggestions = []
        msg = context.exception.message.lower()
        exc_type = context.exception.type.lower()
        
        # Table/relation does not exist
        if "does not exist" in msg or "no such table" in msg:
            suggestions.append(AiDebugSuggestion(
                title="Missing Database Table",
                description="The database table does not exist. Run migrations to create it.",
                code_snippet="python -m vidyut migrate",
                confidence=0.95,
                category="database",
            ))
        
        # Column does not exist
        if "column" in msg and ("does not exist" in msg or "unknown" in msg):
            suggestions.append(AiDebugSuggestion(
                title="Missing Database Column",
                description="A database column is missing. Create a new migration to add the column.",
                code_snippet="python -m vidyut makemigrations\npython -m vidyut migrate",
                confidence=0.9,
                category="database",
            ))
        
        # Unique constraint violation
        if "unique" in msg or "duplicate" in msg:
            suggestions.append(AiDebugSuggestion(
                title="Duplicate Entry",
                description="A record with this unique value already exists. Use a different value or update the existing record.",
                confidence=0.9,
                category="database",
            ))
        
        # Foreign key constraint
        if "foreign key" in msg or "violates" in msg:
            suggestions.append(AiDebugSuggestion(
                title="Foreign Key Constraint",
                description="The referenced record does not exist. Ensure the related record exists before creating this one.",
                confidence=0.85,
                category="database",
            ))
        
        # Connection errors
        if "connection" in msg or "connect" in msg:
            suggestions.append(AiDebugSuggestion(
                title="Database Connection Issue",
                description="Cannot connect to the database. Check DATABASE_URL and ensure the database server is running.",
                confidence=0.9,
                category="config",
            ))
        
        # IntegrityError
        if "integrity" in exc_type:
            suggestions.append(AiDebugSuggestion(
                title="Data Integrity Error",
                description="The data violates a database constraint (unique, foreign key, not null, etc.).",
                confidence=0.8,
                category="database",
            ))
        
        return suggestions
    
    def _analyze_auth_error(self, context: AiDebugContext) -> list[AiDebugSuggestion]:
        """Analyze authentication/authorization errors."""
        suggestions = []
        status = context.status_code
        
        if status == 401:
            suggestions.append(AiDebugSuggestion(
                title="Authentication Required",
                description="This endpoint requires authentication. Include a valid authentication token.",
                code_snippet='headers = {"Authorization": "Bearer <your-token>"}',
                confidence=0.95,
                category="permission",
            ))
        
        if status == 403:
            suggestions.append(AiDebugSuggestion(
                title="Permission Denied",
                description="The authenticated user does not have permission for this action. Check role/permission requirements.",
                confidence=0.9,
                category="permission",
            ))
        
        return suggestions
    
    def _analyze_not_found_error(self, context: AiDebugContext) -> list[AiDebugSuggestion]:
        """Analyze not found errors."""
        suggestions = []
        path = context.request.path
        
        suggestions.append(AiDebugSuggestion(
            title="Resource Not Found",
            description=f"The requested resource at '{path}' was not found. Verify the ID/path is correct.",
            confidence=0.9,
            category="general",
        ))
        
        # Check for common URL issues
        if "//" in path:
            suggestions.append(AiDebugSuggestion(
                title="Double Slash in URL",
                description="The URL contains double slashes. This might cause routing issues.",
                confidence=0.7,
                category="general",
            ))
        
        return suggestions
    
    def _analyze_connection_error(self, context: AiDebugContext) -> list[AiDebugSuggestion]:
        """Analyze connection errors."""
        suggestions = []
        msg = context.exception.message.lower()
        
        if "refused" in msg:
            suggestions.append(AiDebugSuggestion(
                title="Connection Refused",
                description="The connection was refused. Check if the service is running and the port is correct.",
                confidence=0.9,
                category="config",
            ))
        
        if "timeout" in msg or "timed out" in msg:
            suggestions.append(AiDebugSuggestion(
                title="Connection Timeout",
                description="The connection timed out. The service may be overloaded or unreachable.",
                confidence=0.85,
                category="config",
            ))
        
        if "dns" in msg or "name resolution" in msg:
            suggestions.append(AiDebugSuggestion(
                title="DNS Resolution Failed",
                description="Cannot resolve the hostname. Check the hostname is correct and DNS is working.",
                confidence=0.9,
                category="config",
            ))
        
        return suggestions
    
    def _analyze_patterns(self, context: AiDebugContext) -> list[AiDebugSuggestion]:
        """Analyze common error patterns."""
        suggestions = []
        msg = context.exception.message
        exc_type = context.exception.type
        
        # AttributeError patterns
        if exc_type == "AttributeError":
            match = re.search(r"'(\w+)' object has no attribute '(\w+)'", msg)
            if match:
                obj_type, attr = match.groups()
                suggestions.append(AiDebugSuggestion(
                    title=f"Missing Attribute: {attr}",
                    description=f"The '{obj_type}' object does not have an attribute '{attr}'. Check for typos or ensure the attribute exists.",
                    confidence=0.85,
                    category="code",
                ))
        
        # KeyError patterns
        if exc_type == "KeyError":
            suggestions.append(AiDebugSuggestion(
                title="Missing Dictionary Key",
                description="The key does not exist in the dictionary. Use .get() with a default or check if key exists first.",
                code_snippet="value = my_dict.get('key', default_value)",
                confidence=0.9,
                category="code",
            ))
        
        # TypeError patterns
        if exc_type == "TypeError":
            if "NoneType" in msg:
                suggestions.append(AiDebugSuggestion(
                    title="NoneType Error",
                    description="An operation was attempted on None. Check for null values before the operation.",
                    code_snippet="if value is not None:\n    # proceed with operation",
                    confidence=0.85,
                    category="code",
                ))
            if "argument" in msg:
                suggestions.append(AiDebugSuggestion(
                    title="Function Argument Error",
                    description="Wrong number or type of arguments passed to a function. Check the function signature.",
                    confidence=0.8,
                    category="code",
                ))
        
        # ImportError patterns
        if exc_type in ("ImportError", "ModuleNotFoundError"):
            match = re.search(r"No module named '([^']+)'", msg)
            if match:
                module = match.group(1)
                suggestions.append(AiDebugSuggestion(
                    title=f"Missing Module: {module}",
                    description=f"The module '{module}' is not installed. Install it with pip.",
                    code_snippet=f"pip install {module.split('.')[0]}",
                    confidence=0.9,
                    category="config",
                ))
        
        # Pydantic ValidationError
        if "ValidationError" in exc_type:
            suggestions.append(AiDebugSuggestion(
                title="Pydantic Validation Failed",
                description="Input data does not match the expected schema. Check field types and required fields.",
                confidence=0.9,
                category="validation",
            ))
        
        # Async errors
        if "await" in msg.lower() or "coroutine" in msg.lower():
            suggestions.append(AiDebugSuggestion(
                title="Async/Await Issue",
                description="An async function was not awaited or a coroutine was used incorrectly.",
                code_snippet="result = await async_function()",
                confidence=0.85,
                category="code",
            ))
        
        return suggestions


# =============================================================================
# Context Builder
# =============================================================================


def classify_exception(exc: BaseException) -> dict[str, bool]:
    """
    Classify an exception into categories.
    
    Args:
        exc: The exception to classify.
        
    Returns:
        A dictionary of classification flags.
    """
    exc_type = type(exc).__name__
    exc_module = type(exc).__module__
    full_type = f"{exc_module}.{exc_type}"
    msg = str(exc).lower()
    
    # Validation errors
    is_validation = any([
        "ValidationError" in exc_type,
        "RequestValidationError" in exc_type,
        "pydantic" in exc_module,
        "validation" in msg,
    ])
    
    # Database errors
    is_db = any([
        exc_module.startswith(("asyncpg", "psycopg", "sqlite", "sqlalchemy")),
        "database" in msg,
        "sql" in msg,
        "table" in msg,
        "column" in msg,
        "IntegrityError" in exc_type,
        "OperationalError" in exc_type,
        "ProgrammingError" in exc_type,
    ])
    
    # Auth errors
    is_auth = any([
        "Unauthorized" in exc_type,
        "Forbidden" in exc_type,
        "PermissionDenied" in exc_type,
        "authentication" in msg,
        "permission" in msg,
        "unauthorized" in msg,
        "forbidden" in msg,
    ])
    
    # Not found errors
    is_not_found = any([
        "NotFound" in exc_type,
        "DoesNotExist" in exc_type,
        "not found" in msg,
        "does not exist" in msg,
    ])
    
    # Timeout errors
    is_timeout = any([
        "Timeout" in exc_type,
        "timeout" in msg,
        "timed out" in msg,
    ])
    
    # Connection errors
    is_connection = any([
        "Connection" in exc_type,
        "connect" in msg,
        "refused" in msg,
        "unreachable" in msg,
    ])
    
    return {
        "is_validation_error": is_validation,
        "is_db_error": is_db,
        "is_auth_error": is_auth,
        "is_not_found": is_not_found,
        "is_timeout": is_timeout,
        "is_connection_error": is_connection,
    }


def _mask_sensitive_url(url: str) -> str:
    """Mask password in database URL."""
    # postgresql://user:password@host:port/db -> postgresql://user:***@host:port/db
    return re.sub(r"(:\/\/[^:]+:)[^@]+(@)", r"\1***\2", url)


def _filter_headers(headers: dict[str, str]) -> dict[str, str]:
    """Filter sensitive headers."""
    sensitive = {"authorization", "cookie", "x-api-key", "x-auth-token"}
    return {
        k: ("***" if k.lower() in sensitive else v)
        for k, v in headers.items()
    }


async def build_ai_debug_context(
    request: "Request",
    exc: BaseException,
    status_code: int,
    debug_context: Optional["DebugContext"] = None,
    advisor: Optional[BaseAiDebugAdvisor] = None,
) -> AiDebugContext:
    """
    Build an AI-friendly debug context from an exception.
    
    Args:
        request: The Starlette request object.
        exc: The exception that was raised.
        status_code: The HTTP status code.
        debug_context: Optional pre-built DebugContext for reuse.
        advisor: Optional advisor for generating suggestions.
        
    Returns:
        An AiDebugContext with structured error information.
    """
    import sys
    from datetime import datetime, timezone
    
    # Get versions
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    try:
        import vidyut
        vidyut_version = vidyut.__version__
    except Exception:
        vidyut_version = "unknown"
    
    # Exception info
    exc_type = type(exc).__name__
    exc_module = type(exc).__module__
    full_type = f"{exc_module}.{exc_type}"
    exc_msg = str(exc)
    
    # Get detail if HTTPException
    detail = None
    if hasattr(exc, "detail"):
        detail = str(exc.detail) if exc.detail else None
    
    # Classify exception
    classification = classify_exception(exc)
    
    exception_info = AiExceptionInfo(
        type=exc_type,
        message=exc_msg,
        full_type=full_type,
        detail=detail,
        **classification,
    )
    
    # Build traceback frames
    tb_frames: list[AiStackFrame] = []
    tb_text = ""
    
    try:
        tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tb_text = "".join(tb_lines)
        
        # Extract frames
        tb = exc.__traceback__
        while tb is not None:
            frame = tb.tb_frame
            filename = frame.f_code.co_filename
            is_lib = any(p in filename for p in ["site-packages", "lib/python", "dist-packages"])
            
            tb_frames.append(AiStackFrame(
                filename=filename,
                lineno=tb.tb_lineno,
                name=frame.f_code.co_name,
                line="",  # Could extract from linecache
                is_library=is_lib,
                module=frame.f_globals.get("__name__"),
            ))
            tb = tb.tb_next
    except Exception:
        pass
    
    # Request info
    headers = dict(request.headers) if request.headers else {}
    
    try:
        path_params = dict(request.path_params) if request.path_params else {}
    except Exception:
        path_params = {}
    
    try:
        query_params = dict(request.query_params) if request.query_params else {}
    except Exception:
        query_params = {}
    
    # Try to get body preview
    body_preview = None
    try:
        if hasattr(request, "_body"):
            body = request._body
            if body:
                body_preview = body[:1000].decode("utf-8", errors="replace")
    except Exception:
        pass
    
    request_info = AiRequestInfo(
        method=request.method,
        url=str(request.url),
        path=request.url.path,
        path_params=path_params,
        query_params=query_params,
        headers=_filter_headers(headers),
        body_preview=body_preview,
        content_type=headers.get("content-type"),
    )
    
    # View info
    view_info = AiViewInfo()
    try:
        route = request.scope.get("route")
        if route:
            view_info.route_name = route.name
            view_info.endpoint_path = route.path
    except Exception:
        pass
    
    # Environment info
    debug_mode = False
    db_url = None
    installed_apps: list[str] = []
    
    try:
        from vidyut.conf import settings
        debug_mode = settings.debug
        if settings.database_url:
            db_url = _mask_sensitive_url(settings.database_url)
        installed_apps = list(settings.installed_apps or [])
    except Exception:
        pass
    
    env_info = AiEnvInfo(
        python_version=python_version,
        vidyut_version=vidyut_version,
        debug_mode=debug_mode,
        database_url_masked=db_url,
        installed_apps=installed_apps,
    )
    
    # Get context IDs
    request_id = None
    tenant_id = None
    user_id = None
    
    if debug_context:
        request_id = debug_context.request_id
        tenant_id = debug_context.tenant_id
        user_id = debug_context.user_id
    else:
        try:
            from vidyut.middleware.context import request_id_var, tenant_id_var
            request_id = request_id_var.get()
            tenant_id = tenant_id_var.get()
        except Exception:
            pass
        
        try:
            if hasattr(request.state, "user") and request.state.user:
                user = request.state.user
                user_id = str(getattr(user, "id", None) or getattr(user, "identity", None))
        except Exception:
            pass
    
    # Build the context
    ai_context = AiDebugContext(
        request_id=request_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        exception=exception_info,
        traceback_frames=tb_frames,
        traceback_text=tb_text,
        status_code=status_code,
        request=request_info,
        view=view_info,
        tenant_id=tenant_id,
        user_id=user_id,
        environment=env_info,
    )
    
    # Generate prompt hint based on error type
    ai_context.prompt_hint = _generate_prompt_hint(ai_context)
    
    # Get suggestions from advisor
    if advisor is None:
        advisor = RuleBasedAiDebugAdvisor()
    
    ai_context.suggestions = advisor.analyze(ai_context)
    ai_context.related_tools = advisor.get_related_tools(ai_context)
    
    return ai_context


def _generate_prompt_hint(context: AiDebugContext) -> str:
    """Generate a prompt hint based on the error type."""
    exc = context.exception
    
    hints = []
    
    if exc.is_validation_error:
        hints.append("Focus on validating the request body/params against the expected schema.")
    
    if exc.is_db_error:
        hints.append("Check database schema, migrations, and query correctness.")
    
    if exc.is_auth_error:
        hints.append("Verify authentication token and user permissions.")
    
    if exc.is_not_found:
        hints.append("Verify the resource ID exists and the URL path is correct.")
    
    if exc.is_connection_error:
        hints.append("Check service connectivity and configuration.")
    
    if not hints:
        hints.append("Analyze the traceback to identify the root cause.")
    
    return " ".join(hints)


# =============================================================================
# Default advisor instance
# =============================================================================

default_advisor = RuleBasedAiDebugAdvisor()
