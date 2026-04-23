"""
Debug exception handlers and context collection.

v0.3.17: Provides rich error context and beautiful error pages.
"""
from __future__ import annotations

import html
import os
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.types import ASGIApp

if TYPE_CHECKING:
    from aksara.app import Aksara


@dataclass
class DebugContext:
    """
    Rich debug context for error pages.
    
    Contains all relevant information about the error,
    request, and application state.
    """
    # Error info
    exception_type: str = ""
    exception_message: str = ""
    exception_detail: Optional[str] = None
    status_code: int = 500
    
    # Traceback
    traceback_frames: list[dict[str, Any]] = field(default_factory=list)
    traceback_text: str = ""
    
    # Request info
    request_method: str = ""
    request_url: str = ""
    request_path: str = ""
    request_headers: dict[str, str] = field(default_factory=dict)
    request_query_params: dict[str, str] = field(default_factory=dict)
    request_path_params: dict[str, Any] = field(default_factory=dict)
    request_body: Optional[str] = None
    request_client: Optional[str] = None
    
    # Context vars
    request_id: Optional[str] = None
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    
    # Environment
    python_version: str = ""
    aksara_version: str = ""
    debug_mode: bool = True
    timestamp: str = ""
    
    # DB queries (for future integration)
    db_queries: list[dict[str, Any]] = field(default_factory=list)


def _extract_traceback_frames(exc: BaseException) -> list[dict[str, Any]]:
    """Extract structured traceback frames from exception."""
    frames = []
    tb = traceback.extract_tb(exc.__traceback__)
    
    for frame in tb:
        frame_info = {
            "filename": frame.filename,
            "lineno": frame.lineno,
            "name": frame.name,
            "line": frame.line or "",
            "is_library": _is_library_path(frame.filename),
        }
        
        # Try to get context lines
        try:
            context_lines = _get_context_lines(frame.filename, frame.lineno)
            frame_info["context_lines"] = context_lines
        except Exception:
            frame_info["context_lines"] = []
        
        frames.append(frame_info)
    
    return frames


def _is_library_path(filepath: str) -> bool:
    """Check if a file path is from a library (not user code)."""
    # Common library paths
    library_indicators = [
        "site-packages",
        "dist-packages",
        "/lib/python",
        "\\lib\\python",
        "<frozen",
        "<string>",
    ]
    return any(indicator in filepath for indicator in library_indicators)


def _get_context_lines(
    filepath: str, 
    lineno: int, 
    context: int = 5
) -> list[dict[str, Any]]:
    """Get context lines around the error line."""
    try:
        path = Path(filepath)
        if not path.exists() or not path.is_file():
            return []
        
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        
        start = max(0, lineno - context - 1)
        end = min(len(lines), lineno + context)
        
        context_lines = []
        for i in range(start, end):
            context_lines.append({
                "number": i + 1,
                "content": lines[i].rstrip("\n\r"),
                "is_error_line": i + 1 == lineno,
            })
        
        return context_lines
    except Exception:
        return []


async def collect_debug_context(
    request: Request,
    exc: BaseException,
    status_code: int = 500,
) -> DebugContext:
    """
    Collect rich debug context from request and exception.
    
    Args:
        request: The Starlette/FastAPI request object.
        exc: The exception that was raised.
        status_code: HTTP status code for the error.
    
    Returns:
        DebugContext with all relevant information.
    """
    from aksara import __version__
    
    # Get context variables
    try:
        from aksara.middleware.context import (
            request_id_var,
            tenant_id_var,
            user_id_var,
        )
        request_id = request_id_var.get()
        tenant_id = tenant_id_var.get()
        user_id = user_id_var.get()
    except Exception:
        request_id = None
        tenant_id = None
        user_id = None
    
    # Extract traceback
    traceback_frames = _extract_traceback_frames(exc)
    traceback_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    
    # Get request body (if available and not too large)
    request_body = None
    try:
        body = await request.body()
        if len(body) <= 10000:  # 10KB limit
            request_body = body.decode("utf-8", errors="replace")
    except Exception:
        pass
    
    # Build headers dict (filter sensitive ones)
    sensitive_headers = {"authorization", "cookie", "x-api-key", "api-key"}
    headers = {}
    for key, value in request.headers.items():
        if key.lower() in sensitive_headers:
            headers[key] = "[REDACTED]"
        else:
            headers[key] = value
    
    # Get exception detail (for HTTPException)
    exception_detail = None
    if hasattr(exc, "detail"):
        exception_detail = str(exc.detail)
    
    context = DebugContext(
        # Error info
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        exception_detail=exception_detail,
        status_code=status_code,
        
        # Traceback
        traceback_frames=traceback_frames,
        traceback_text=traceback_text,
        
        # Request info
        request_method=request.method,
        request_url=str(request.url),
        request_path=request.url.path,
        request_headers=headers,
        request_query_params=dict(request.query_params),
        request_path_params=dict(request.path_params),
        request_body=request_body,
        request_client=f"{request.client.host}:{request.client.port}" if request.client else None,
        
        # Context vars
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        
        # Environment
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        aksara_version=__version__,
        debug_mode=True,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    
    return context


def render_debug_page(
    context: DebugContext,
    ai_context: Optional["AiDebugContext"] = None,
) -> HTMLResponse:
    """
    Render a beautiful dark-mode debug error page.
    
    Args:
        context: The DebugContext with error information.
        ai_context: Optional AI debug context with suggestions.
    
    Returns:
        HTMLResponse with the styled error page.
    """
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from aksara.ai.debug import AiDebugContext
    
    # Build traceback HTML
    traceback_html = _build_traceback_html(context.traceback_frames)
    
    # Build request info HTML
    request_html = _build_request_html(context)
    
    # Build context vars HTML
    context_vars_html = _build_context_vars_html(context)
    
    # Build AI debug HTML if context available
    ai_debug_html = _build_ai_debug_html(ai_context) if ai_context else ""
    ai_tab_button = '<button class="tab-btn ai-tab" data-tab="ai-debug">🤖 AI Debug</button>' if ai_context else ""
    
    # Escape for safe HTML
    exc_type = html.escape(context.exception_type)
    exc_message = html.escape(context.exception_message)
    exc_detail = html.escape(context.exception_detail or "")
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{context.status_code} - {exc_type}</title>
    <style>
{_get_debug_css()}
    </style>
</head>
<body>
    <div class="error-container">
        <header class="error-header">
            <div class="status-badge status-{_get_status_class(context.status_code)}">{context.status_code}</div>
            <div class="error-info">
                <h1 class="error-type">{exc_type}</h1>
                <p class="error-message">{exc_message}</p>
                {f'<p class="error-detail">{exc_detail}</p>' if exc_detail and exc_detail != exc_message else ''}
            </div>
        </header>
        
        <nav class="tab-nav">
            <button class="tab-btn active" data-tab="traceback">Traceback</button>
            <button class="tab-btn" data-tab="request">Request</button>
            <button class="tab-btn" data-tab="context">Context</button>
            <button class="tab-btn" data-tab="environment">Environment</button>
            {ai_tab_button}
        </nav>
        
        <div class="tab-content">
            <section id="traceback" class="tab-pane active">
                <h2>Traceback <span class="subtitle">(most recent call last)</span></h2>
                {traceback_html}
            </section>
            
            <section id="request" class="tab-pane">
                <h2>Request Details</h2>
                {request_html}
            </section>
            
            <section id="context" class="tab-pane">
                <h2>Context Variables</h2>
                {context_vars_html}
            </section>
            
            <section id="environment" class="tab-pane">
                <h2>Environment</h2>
                <div class="info-grid">
                    <div class="info-item">
                        <span class="info-label">Python</span>
                        <span class="info-value">{context.python_version}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Aksara</span>
                        <span class="info-value">{context.aksara_version}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Debug Mode</span>
                        <span class="info-value">{"Enabled" if context.debug_mode else "Disabled"}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Timestamp</span>
                        <span class="info-value">{context.timestamp}</span>
                    </div>
                </div>
            </section>
            
            {ai_debug_html}
        </div>
        
        <footer class="error-footer">
            <span class="footer-logo">⚡ Aksara v{context.aksara_version}</span>
            <span class="footer-note">Debug mode is enabled. Disable it in production.</span>
        </footer>
    </div>
    
    <script>
{_get_debug_js()}
    </script>
</body>
</html>"""
    
    return HTMLResponse(content=html_content, status_code=context.status_code)


def render_minimal_error_page(
    status_code: int,
    message: str = "An error occurred",
    request_id: Optional[str] = None,
) -> HTMLResponse:
    """
    Render a minimal, production-safe error page.
    
    Args:
        status_code: HTTP status code.
        message: User-friendly error message.
        request_id: Optional request ID for support.
    
    Returns:
        HTMLResponse with minimal error page.
    """
    message_escaped = html.escape(message)
    request_id_escaped = html.escape(request_id or "")
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error {status_code}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
            background: #09090B;
            color: #FAFAFA;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            -webkit-font-smoothing: antialiased;
        }}
        .container {{
            text-align: center;
            padding: 2rem;
            max-width: 420px;
        }}
        .status {{ font-size: 5rem; font-weight: 600; color: #F87171; letter-spacing: -0.03em; }}
        .message {{ font-size: 1.25rem; margin: 0.75rem 0; color: #A1A1AA; }}
        .request-id {{ font-size: 0.8125rem; color: #71717A; margin-top: 1.5rem; }}
        .request-id code {{ 
            background: #18181B; 
            padding: 0.25rem 0.5rem; 
            border-radius: 0.375rem;
            font-family: 'SF Mono', 'JetBrains Mono', Consolas, monospace;
            font-size: 0.75rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="status">{status_code}</div>
        <p class="message">{message_escaped}</p>
        {f'<p class="request-id">Request ID: <code>{request_id_escaped}</code></p>' if request_id else ''}
    </div>
</body>
</html>"""
    
    return HTMLResponse(content=html_content, status_code=status_code)


def render_json_error(
    status_code: int,
    message: str,
    error_type: Optional[str] = None,
    request_id: Optional[str] = None,
    errors: Optional[list[dict[str, Any]]] = None,
    debug_detail: Optional[str] = None,
) -> JSONResponse:
    """
    Render a JSON error response for API consumers.
    
    Args:
        status_code: HTTP status code.
        message: Error message.
        error_type: Optional error type/code.
        request_id: Optional request ID.
        errors: Optional list of detailed errors.
    
    Returns:
        JSONResponse with error details.
    """
    content: dict[str, Any] = {
        "error": {
            "status": status_code,
            "message": message,
        }
    }
    
    if error_type:
        content["error"]["type"] = error_type
    
    if request_id:
        content["error"]["request_id"] = request_id
    
    if errors:
        content["error"]["errors"] = errors

    if debug_detail:
        content["error"]["debug_detail"] = debug_detail
    
    return JSONResponse(content=content, status_code=status_code)


def _get_json_debug_detail(request: Request, exc: Exception, is_debug: bool) -> Optional[str]:
    """Return debug detail only for localhost JSON requests in debug mode."""
    client = getattr(request, "client", None)
    host = getattr(client, "host", None)

    if not is_debug or host not in {"127.0.0.1", "::1"}:
        return None

    return str(exc)


class AksaraDebugMiddleware:
    """
    Debug middleware that provides beautiful dark-mode error pages.
    
    This middleware catches exceptions and renders either:
    - Rich HTML debug pages in debug mode
    - Clean JSON or minimal HTML in production
    
    Note: This is added as an ASGI middleware to take priority over
    Starlette's ServerErrorMiddleware when debug=True.
    """
    
    def __init__(self, app: ASGIApp, debug: bool = False) -> None:
        self.app = app
        self.debug = debug
    
    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive, send)
        
        try:
            await self.app(scope, receive, send)
        except Exception as exc:
            # Handle the exception with our beautiful error pages
            response = await self._handle_exception(request, exc)
            await response(scope, receive, send)
    
    async def _handle_exception(self, request: Request, exc: Exception) -> Response:
        """Handle an exception and return appropriate response."""
        from fastapi import HTTPException as FastAPIHTTPException
        from fastapi.exceptions import RequestValidationError
        from starlette.exceptions import HTTPException as StarletteHTTPException
        
        # Determine status code
        if isinstance(exc, (StarletteHTTPException, FastAPIHTTPException)):
            status_code = exc.status_code
        elif isinstance(exc, RequestValidationError):
            status_code = 422
        else:
            status_code = 500
        
        # Check content preference
        wants_html = self._wants_html(request)
        
        if self.debug and wants_html:
            # Debug mode with HTML: rich error page
            context = await collect_debug_context(request, exc, status_code)
            
            # Build AI debug context if enabled
            ai_context = None
            try:
                from aksara.conf import settings
                if getattr(settings, 'ai_debug_enabled', True) and settings.debug:
                    from aksara.ai.debug import build_ai_debug_context, default_advisor
                    ai_context = await build_ai_debug_context(
                        request, exc, status_code, 
                        debug_context=context,
                        advisor=default_advisor
                    )
            except Exception:
                # Silently fail if AI debug is not available
                pass
            
            return render_debug_page(context, ai_context=ai_context)
        
        elif isinstance(exc, RequestValidationError):
            # Validation errors always return JSON
            errors = [
                {
                    "loc": list(err.get("loc", [])),
                    "msg": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
                for err in exc.errors()
            ]
            return render_json_error(
                422,
                "Validation error",
                error_type="validation_error",
                errors=errors,
            )
        
        elif isinstance(exc, (StarletteHTTPException, FastAPIHTTPException)):
            # HTTP exceptions
            detail = str(exc.detail) if hasattr(exc, "detail") and exc.detail else "An error occurred"
            
            if wants_html:
                request_id = self._get_request_id()
                return render_minimal_error_page(status_code, detail, request_id)
            else:
                return render_json_error(
                    status_code,
                    detail,
                    error_type="http_exception",
                )
        
        else:
            # Generic exceptions
            if wants_html:
                request_id = self._get_request_id()
                return render_minimal_error_page(500, "Internal Server Error", request_id)
            else:
                return render_json_error(
                    500,
                    "Internal Server Error",
                    error_type="internal_error",
                    debug_detail=_get_json_debug_detail(request, exc, self.debug),
                )
    
    def _wants_html(self, request: Request) -> bool:
        """Check if client prefers HTML response."""
        accept = request.headers.get("accept", "")
        if "application/json" in accept and "text/html" not in accept:
            return False
        return "text/html" in accept or "*/*" in accept
    
    def _get_request_id(self) -> Optional[str]:
        """Try to get request ID from context."""
        try:
            from aksara.middleware.context import request_id_var
            return request_id_var.get()
        except Exception:
            return None


def _get_status_class(status_code: int) -> str:
    """Get CSS class based on status code."""
    if status_code >= 500:
        return "500"
    elif status_code >= 400:
        return "400"
    else:
        return "other"


def _build_traceback_html(frames: list[dict[str, Any]]) -> str:
    """Build HTML for traceback frames."""
    if not frames:
        return "<p class='no-traceback'>No traceback available</p>"
    
    html_parts = ['<div class="traceback-list">']
    
    for i, frame in enumerate(frames):
        is_user_code = not frame.get("is_library", False)
        frame_class = "traceback-frame user-code" if is_user_code else "traceback-frame library-code"
        
        filename = html.escape(frame.get("filename", ""))
        lineno = frame.get("lineno", 0)
        name = html.escape(frame.get("name", ""))
        line = html.escape(frame.get("line", ""))
        
        html_parts.append(f'''
        <div class="{frame_class}" data-expanded="{"true" if i == len(frames) - 1 else "false"}">
            <div class="frame-header" onclick="toggleFrame(this)">
                <span class="frame-location">
                    <span class="frame-file">{filename}</span>
                    <span class="frame-lineno">:{lineno}</span>
                    in <span class="frame-func">{name}</span>
                </span>
                <span class="frame-toggle">▼</span>
            </div>
            <div class="frame-body">
                <code class="frame-line">{line}</code>
        ''')
        
        # Add context lines if available
        context_lines = frame.get("context_lines", [])
        if context_lines:
            html_parts.append('<div class="context-code"><pre>')
            for ctx in context_lines:
                line_num = ctx.get("number", 0)
                content = html.escape(ctx.get("content", ""))
                is_error = ctx.get("is_error_line", False)
                line_class = "line error-line" if is_error else "line"
                html_parts.append(
                    f'<span class="{line_class}"><span class="line-num">{line_num}</span>{content}</span>\n'
                )
            html_parts.append('</pre></div>')
        
        html_parts.append('</div></div>')
    
    html_parts.append('</div>')
    return "".join(html_parts)


def _build_request_html(context: DebugContext) -> str:
    """Build HTML for request details."""
    parts = [f'''
        <div class="request-summary">
            <span class="method method-{context.request_method.lower()}">{context.request_method}</span>
            <span class="url">{html.escape(context.request_url)}</span>
        </div>
    ''']
    
    # Path params
    if context.request_path_params:
        parts.append('<h3>Path Parameters</h3><table class="info-table">')
        for key, value in context.request_path_params.items():
            parts.append(f'<tr><td>{html.escape(str(key))}</td><td>{html.escape(str(value))}</td></tr>')
        parts.append('</table>')
    
    # Query params
    if context.request_query_params:
        parts.append('<h3>Query Parameters</h3><table class="info-table">')
        for key, value in context.request_query_params.items():
            parts.append(f'<tr><td>{html.escape(str(key))}</td><td>{html.escape(str(value))}</td></tr>')
        parts.append('</table>')
    
    # Headers
    if context.request_headers:
        parts.append('<h3>Headers</h3><table class="info-table">')
        for key, value in sorted(context.request_headers.items()):
            parts.append(f'<tr><td>{html.escape(key)}</td><td>{html.escape(value)}</td></tr>')
        parts.append('</table>')
    
    # Body
    if context.request_body:
        parts.append(f'''
        <h3>Request Body</h3>
        <pre class="request-body">{html.escape(context.request_body)}</pre>
        ''')
    
    # Client
    if context.request_client:
        parts.append(f'''
        <h3>Client</h3>
        <p class="client-info">{html.escape(context.request_client)}</p>
        ''')
    
    return "".join(parts)


def _build_context_vars_html(context: DebugContext) -> str:
    """Build HTML for context variables."""
    parts = ['<div class="context-grid">']
    
    vars_list = [
        ("Request ID", context.request_id),
        ("Tenant ID", context.tenant_id),
        ("User ID", context.user_id),
    ]
    
    for label, value in vars_list:
        value_display = html.escape(str(value)) if value else "<em>Not set</em>"
        value_class = "context-value" if value else "context-value not-set"
        parts.append(f'''
        <div class="context-item">
            <span class="context-label">{label}</span>
            <span class="{value_class}">{value_display}</span>
        </div>
        ''')
    
    parts.append('</div>')
    return "".join(parts)


def _build_ai_debug_html(ai_context: Optional[Any]) -> str:
    """Build HTML for AI debug section."""
    if ai_context is None:
        return ""
    
    import json
    
    parts = ['<section id="ai-debug" class="tab-pane">']
    parts.append('<h2>🤖 AI Debug Assistant</h2>')
    
    # Suggestions section
    if ai_context.suggestions:
        parts.append('<div class="ai-suggestions">')
        parts.append('<h3>💡 Suggestions</h3>')
        
        for i, suggestion in enumerate(ai_context.suggestions, 1):
            confidence_pct = int(suggestion.confidence * 100)
            confidence_class = "high" if suggestion.confidence >= 0.8 else "medium" if suggestion.confidence >= 0.5 else "low"
            
            parts.append(f'''
            <div class="ai-suggestion">
                <div class="suggestion-header">
                    <span class="suggestion-number">#{i}</span>
                    <span class="suggestion-title">{html.escape(suggestion.title)}</span>
                    <span class="confidence-badge {confidence_class}">{confidence_pct}% confidence</span>
                    <span class="category-badge">{html.escape(suggestion.category)}</span>
                </div>
                <p class="suggestion-description">{html.escape(suggestion.description)}</p>
            ''')
            
            if suggestion.code_snippet:
                parts.append(f'''
                <div class="suggestion-code">
                    <pre><code>{html.escape(suggestion.code_snippet)}</code></pre>
                </div>
                ''')
            
            if suggestion.doc_url:
                parts.append(f'''
                <a href="{html.escape(suggestion.doc_url)}" class="doc-link" target="_blank">📚 Documentation</a>
                ''')
            
            parts.append('</div>')
        
        parts.append('</div>')
    else:
        parts.append('<p class="no-suggestions">No suggestions available for this error type.</p>')
    
    # Exception classification
    exc = ai_context.exception
    classification_flags = []
    if exc.is_validation_error:
        classification_flags.append("Validation Error")
    if exc.is_db_error:
        classification_flags.append("Database Error")
    if exc.is_auth_error:
        classification_flags.append("Auth Error")
    if exc.is_not_found:
        classification_flags.append("Not Found")
    if exc.is_timeout:
        classification_flags.append("Timeout")
    if exc.is_connection_error:
        classification_flags.append("Connection Error")
    
    if classification_flags:
        parts.append('<div class="ai-classification">')
        parts.append('<h3>🏷️ Error Classification</h3>')
        parts.append('<div class="classification-tags">')
        for flag in classification_flags:
            parts.append(f'<span class="classification-tag">{html.escape(flag)}</span>')
        parts.append('</div>')
        parts.append('</div>')
    
    # LLM Prompt section
    parts.append('<div class="ai-prompt-section">')
    parts.append('<h3>🤖 LLM Prompt</h3>')
    parts.append('<p class="prompt-hint">Copy this prompt to analyze the error with an AI assistant:</p>')
    
    llm_prompt = ai_context.to_llm_prompt()
    parts.append(f'''
    <div class="prompt-container">
        <button class="copy-btn" onclick="copyPrompt()">📋 Copy Prompt</button>
        <pre class="llm-prompt" id="llm-prompt">{html.escape(llm_prompt)}</pre>
    </div>
    ''')
    parts.append('</div>')
    
    # JSON Context section
    parts.append('<div class="ai-json-section">')
    parts.append('<h3>📄 JSON Context</h3>')
    parts.append('<p class="json-hint">Structured JSON for programmatic use:</p>')
    
    try:
        json_context = ai_context.model_dump_json(indent=2)
    except Exception:
        json_context = "{}"
    
    parts.append(f'''
    <div class="json-container">
        <button class="copy-btn" onclick="copyJson()">📋 Copy JSON</button>
        <pre class="ai-json" id="ai-json">{html.escape(json_context)}</pre>
    </div>
    ''')
    parts.append('</div>')
    
    parts.append('</section>')
    return "".join(parts)


def _get_debug_css() -> str:
    """Get CSS for the debug error page."""
    return """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            /* Shadcn-inspired dark theme (zinc scale) */
            --bg-primary: #09090B;
            --bg-secondary: #18181B;
            --bg-tertiary: #27272A;
            --border-color: #27272A;
            --text-primary: #FAFAFA;
            --text-secondary: #A1A1AA;
            --text-muted: #71717A;
            --accent-blue: #818CF8;
            --accent-green: #34D399;
            --accent-red: #F87171;
            --accent-orange: #FBBF24;
            --accent-purple: #A78BFA;
            --ring-alpha: rgba(129, 140, 248, 0.3);
            --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
            --font-mono: 'SF Mono', 'JetBrains Mono', Consolas, monospace;
        }
        
        body {
            font-family: var(--font-sans);
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.5;
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
        }
        
        .error-container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 1.5rem;
        }
        
        /* Header */
        .error-header {
            display: flex;
            align-items: flex-start;
            gap: 1.25rem;
            padding: 1.5rem;
            background: var(--bg-secondary);
            border-radius: 0.75rem;
            border: 1px solid var(--border-color);
            margin-bottom: 1.25rem;
        }
        
        .status-badge {
            font-size: 2rem;
            font-weight: 600;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            min-width: 100px;
            text-align: center;
            letter-spacing: -0.02em;
        }
        
        .status-500 { background: rgba(248, 113, 113, 0.12); color: var(--accent-red); }
        .status-400 { background: rgba(251, 191, 36, 0.12); color: var(--accent-orange); }
        .status-other { background: rgba(129, 140, 248, 0.12); color: var(--accent-blue); }
        
        .error-info { flex: 1; }
        .error-type {
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 0.375rem;
            letter-spacing: -0.02em;
        }
        .error-message {
            font-size: 1rem;
            color: var(--text-secondary);
            word-break: break-word;
        }
        .error-detail {
            font-size: 0.875rem;
            color: var(--text-muted);
            margin-top: 0.375rem;
        }
        
        /* Tabs */
        .tab-nav {
            display: flex;
            gap: 0.25rem;
            margin-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.5rem;
        }
        
        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-size: 0.875rem;
            font-weight: 500;
            padding: 0.625rem 1rem;
            cursor: pointer;
            border-radius: 0.375rem;
            transition: all 0.15s ease;
        }
        
        .tab-btn:hover { background: var(--bg-tertiary); color: var(--text-primary); }
        .tab-btn.active { background: rgba(129, 140, 248, 0.15); color: var(--accent-blue); }
        
        .tab-pane { display: none; }
        .tab-pane.active { display: block; }
        
        .tab-content {
            background: var(--bg-secondary);
            border-radius: 0.75rem;
            border: 1px solid var(--border-color);
            padding: 1.25rem;
        }
        
        .tab-content h2 {
            font-size: 1.125rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: var(--text-primary);
            letter-spacing: -0.01em;
        }
        
        .tab-content h2 .subtitle {
            font-size: 0.8125rem;
            font-weight: 400;
            color: var(--text-muted);
        }
        
        .tab-content h3 {
            font-size: 0.875rem;
            font-weight: 500;
            margin: 1.25rem 0 0.625rem;
            color: var(--text-secondary);
        }
        
        /* Traceback */
        .traceback-list { display: flex; flex-direction: column; gap: 0.5rem; }
        
        .traceback-frame {
            background: var(--bg-primary);
            border-radius: 0.5rem;
            border: 1px solid var(--border-color);
            overflow: hidden;
        }
        
        .traceback-frame.user-code {
            border-left: 3px solid var(--accent-blue);
        }
        
        .traceback-frame.library-code {
            opacity: 0.7;
        }
        
        .frame-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.625rem 0.875rem;
            cursor: pointer;
            transition: background 0.15s ease;
        }
        
        .frame-header:hover { background: var(--bg-tertiary); }
        
        .frame-location { font-family: var(--font-mono); font-size: 0.8125rem; }
        .frame-file { color: var(--accent-blue); }
        .frame-lineno { color: var(--accent-purple); }
        .frame-func { color: var(--accent-green); }
        .frame-toggle { color: var(--text-muted); transition: transform 0.15s ease; }
        
        .traceback-frame[data-expanded="true"] .frame-toggle { transform: rotate(180deg); }
        .traceback-frame[data-expanded="false"] .frame-body { display: none; }
        
        .frame-body {
            padding: 0.625rem 0.875rem;
            border-top: 1px solid var(--border-color);
            background: var(--bg-tertiary);
        }
        
        .frame-line {
            font-family: var(--font-mono);
            font-size: 0.8125rem;
            color: var(--accent-orange);
            display: block;
            margin-bottom: 0.625rem;
        }
        
        .context-code {
            background: var(--bg-primary);
            border-radius: 0.375rem;
            overflow: hidden;
        }
        
        .context-code pre {
            margin: 0;
            padding: 0.5rem 0;
            overflow-x: auto;
        }
        
        .context-code .line {
            display: block;
            padding: 0.125rem 0.875rem;
            font-family: var(--font-mono);
            font-size: 0.75rem;
            white-space: pre;
        }
        
        .context-code .line.error-line {
            background: rgba(248, 113, 113, 0.12);
            color: var(--accent-red);
        }
        
        .context-code .line-num {
            display: inline-block;
            width: 2.5rem;
            color: var(--text-muted);
            text-align: right;
            margin-right: 0.875rem;
            user-select: none;
        }
        
        /* Request */
        .request-summary {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.875rem;
            background: var(--bg-primary);
            border-radius: 0.5rem;
            margin-bottom: 1rem;
        }
        
        .method {
            font-weight: 500;
            padding: 0.25rem 0.625rem;
            border-radius: 9999px;
            font-size: 0.6875rem;
            text-transform: uppercase;
            letter-spacing: 0.02em;
        }
        
        .method-get { background: rgba(52, 211, 153, 0.12); color: var(--accent-green); }
        .method-post { background: rgba(129, 140, 248, 0.12); color: var(--accent-blue); }
        .method-put, .method-patch { background: rgba(251, 191, 36, 0.12); color: var(--accent-orange); }
        .method-delete { background: rgba(248, 113, 113, 0.12); color: var(--accent-red); }
        
        .url {
            font-family: var(--font-mono);
            font-size: 0.8125rem;
            color: var(--text-secondary);
            word-break: break-all;
        }
        
        .info-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.8125rem;
        }
        
        .info-table td {
            padding: 0.5rem 0.875rem;
            border-bottom: 1px solid var(--border-color);
        }
        
        .info-table td:first-child {
            font-family: var(--font-mono);
            color: var(--accent-purple);
            width: 30%;
        }
        
        .info-table td:last-child {
            font-family: var(--font-mono);
            color: var(--text-secondary);
            word-break: break-all;
        }
        
        .request-body {
            background: var(--bg-primary);
            padding: 0.875rem;
            border-radius: 0.5rem;
            font-family: var(--font-mono);
            font-size: 0.75rem;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-all;
        }
        
        .client-info {
            font-family: var(--font-mono);
            color: var(--text-secondary);
        }
        
        /* Context */
        .context-grid, .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 0.75rem;
        }
        
        .context-item, .info-item {
            background: var(--bg-primary);
            padding: 0.875rem;
            border-radius: 0.5rem;
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }
        
        .context-label, .info-label {
            font-size: 0.6875rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.04em;
            font-weight: 500;
        }
        
        .context-value, .info-value {
            font-family: var(--font-mono);
            font-size: 0.875rem;
            color: var(--text-primary);
        }
        
        .context-value.not-set {
            color: var(--text-muted);
        }
        
        /* Footer */
        .error-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 1.25rem;
            padding: 0.875rem 0;
            border-top: 1px solid var(--border-color);
            font-size: 0.8125rem;
            color: var(--text-muted);
        }
        
        .footer-logo { color: var(--accent-blue); }
        .footer-note { color: var(--accent-orange); }
        
        .no-traceback { color: var(--text-muted); }
        
        /* AI Debug Tab */
        .ai-tab { 
            background: rgba(167, 139, 250, 0.1);
            border: 1px solid rgba(167, 139, 250, 0.3);
        }
        .ai-tab:hover { 
            background: rgba(167, 139, 250, 0.15);
        }
        
        .ai-suggestions { margin-bottom: 1.5rem; }
        .ai-suggestions h3 { margin-bottom: 0.875rem; color: var(--accent-orange); }
        
        .ai-suggestion {
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            padding: 0.875rem;
            margin-bottom: 0.75rem;
        }
        
        .suggestion-header {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.625rem;
            flex-wrap: wrap;
        }
        
        .suggestion-number {
            font-size: 0.6875rem;
            color: var(--text-muted);
            background: var(--bg-tertiary);
            padding: 0.125rem 0.375rem;
            border-radius: 0.25rem;
        }
        
        .suggestion-title {
            font-weight: 500;
            font-size: 0.875rem;
            color: var(--text-primary);
            flex: 1;
        }
        
        .confidence-badge {
            font-size: 0.6875rem;
            padding: 0.125rem 0.5rem;
            border-radius: 9999px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.02em;
        }
        .confidence-badge.high { background: rgba(52, 211, 153, 0.12); color: var(--accent-green); }
        .confidence-badge.medium { background: rgba(251, 191, 36, 0.12); color: var(--accent-orange); }
        .confidence-badge.low { background: rgba(248, 113, 113, 0.12); color: var(--accent-red); }
        
        .category-badge {
            font-size: 0.6875rem;
            padding: 0.125rem 0.5rem;
            border-radius: 9999px;
            background: rgba(129, 140, 248, 0.12);
            color: var(--accent-blue);
            text-transform: uppercase;
            letter-spacing: 0.02em;
        }
        
        .suggestion-description {
            color: var(--text-secondary);
            font-size: 0.8125rem;
            line-height: 1.5;
        }
        
        .suggestion-code {
            margin-top: 0.625rem;
            background: var(--bg-tertiary);
            border-radius: 0.375rem;
            padding: 0.625rem;
            overflow-x: auto;
        }
        
        .suggestion-code pre {
            margin: 0;
            font-family: var(--font-mono);
            font-size: 0.75rem;
            color: var(--accent-green);
        }
        
        .doc-link {
            display: inline-block;
            margin-top: 0.375rem;
            color: var(--accent-blue);
            text-decoration: none;
            font-size: 0.8125rem;
        }
        .doc-link:hover { text-decoration: underline; }
        
        .no-suggestions {
            color: var(--text-muted);
            padding: 1rem;
            text-align: center;
        }
        
        .ai-classification { margin-bottom: 1.5rem; }
        .ai-classification h3 { margin-bottom: 0.75rem; color: var(--accent-purple); }
        
        .classification-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.375rem;
        }
        
        .classification-tag {
            background: rgba(167, 139, 250, 0.12);
            color: var(--accent-purple);
            padding: 0.25rem 0.625rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
        }
        
        .ai-prompt-section, .ai-json-section {
            margin-bottom: 1.5rem;
        }
        
        .ai-prompt-section h3, .ai-json-section h3 {
            margin-bottom: 0.375rem;
            color: var(--accent-blue);
        }
        
        .prompt-hint, .json-hint {
            color: var(--text-muted);
            font-size: 0.8125rem;
            margin-bottom: 0.625rem;
        }
        
        .prompt-container, .json-container {
            position: relative;
        }
        
        .copy-btn {
            position: absolute;
            top: 0.5rem;
            right: 0.5rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 0.25rem 0.625rem;
            border-radius: 0.375rem;
            cursor: pointer;
            font-size: 0.6875rem;
            font-weight: 500;
            transition: all 0.15s ease;
            z-index: 1;
        }
        .copy-btn:hover {
            background: var(--bg-secondary);
            color: var(--accent-blue);
            border-color: var(--accent-blue);
        }
        
        .llm-prompt, .ai-json {
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            padding: 0.875rem;
            padding-top: 2.25rem;
            font-family: var(--font-mono);
            font-size: 0.75rem;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-word;
            color: var(--text-secondary);
            max-height: 350px;
            overflow-y: auto;
        }
    """


def _get_debug_js() -> str:
    """Get JavaScript for the debug error page."""
    return """
        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById(btn.dataset.tab).classList.add('active');
            });
        });
        
        // Frame toggle
        function toggleFrame(header) {
            const frame = header.parentElement;
            const expanded = frame.dataset.expanded === 'true';
            frame.dataset.expanded = expanded ? 'false' : 'true';
        }
        
        // Copy prompt to clipboard
        function copyPrompt() {
            const prompt = document.getElementById('llm-prompt');
            if (prompt) {
                navigator.clipboard.writeText(prompt.textContent).then(() => {
                    const btn = event.target;
                    const original = btn.textContent;
                    btn.textContent = '✓ Copied!';
                    setTimeout(() => btn.textContent = original, 2000);
                });
            }
        }
        
        // Copy JSON to clipboard
        function copyJson() {
            const json = document.getElementById('ai-json');
            if (json) {
                navigator.clipboard.writeText(json.textContent).then(() => {
                    const btn = event.target;
                    const original = btn.textContent;
                    btn.textContent = '✓ Copied!';
                    setTimeout(() => btn.textContent = original, 2000);
                });
            }
        }
    """


def register_debug_exception_handlers(app: "Aksara") -> None:
    """
    Register debug-aware exception handlers on the Aksara app.
    
    This adds the AksaraDebugMiddleware which provides:
    - Rich HTML error pages with dark theme in debug mode
    - Clean JSON or minimal HTML in production
    
    Args:
        app: The Aksara application instance.
    """
    is_debug = app._debug or getattr(app, "debug", False)
    
    # Add our debug middleware as an ASGI middleware
    # This wraps the entire app and catches exceptions before
    # Starlette's ServerErrorMiddleware can handle them
    app.add_middleware(AksaraDebugMiddleware, debug=is_debug)
    
    # Also register exception handlers for cases where middleware
    # doesn't catch the exception (e.g., inside the app itself)
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException
    from fastapi import HTTPException as FastAPIHTTPException
    
    # Check if we should use HTML or JSON
    def _wants_html(request: Request) -> bool:
        """Check if client prefers HTML response."""
        accept = request.headers.get("accept", "")
        # Prefer JSON for API-like requests
        if "application/json" in accept and "text/html" not in accept:
            return False
        # Default to HTML for browser-like requests
        return "text/html" in accept or "*/*" in accept
    
    @app.exception_handler(StarletteHTTPException)
    async def debug_http_exception_handler(
        request: Request, 
        exc: StarletteHTTPException
    ) -> Response:
        """Handle HTTP exceptions with debug awareness."""
        if is_debug and _wants_html(request):
            context = await collect_debug_context(request, exc, exc.status_code)
            return render_debug_page(context)
        elif _wants_html(request):
            # Production HTML
            try:
                from aksara.middleware.context import request_id_var
                request_id = request_id_var.get()
            except Exception:
                request_id = None
            
            return render_minimal_error_page(
                exc.status_code,
                str(exc.detail) if exc.detail else "An error occurred",
                request_id,
            )
        else:
            # JSON response
            return render_json_error(
                exc.status_code,
                str(exc.detail) if exc.detail else "An error occurred",
                error_type="http_exception",
            )
    
    @app.exception_handler(FastAPIHTTPException)
    async def debug_fastapi_http_exception_handler(
        request: Request,
        exc: FastAPIHTTPException
    ) -> Response:
        """Handle FastAPI HTTP exceptions."""
        if is_debug and _wants_html(request):
            context = await collect_debug_context(request, exc, exc.status_code)
            return render_debug_page(context)
        elif _wants_html(request):
            try:
                from aksara.middleware.context import request_id_var
                request_id = request_id_var.get()
            except Exception:
                request_id = None
            
            return render_minimal_error_page(
                exc.status_code,
                str(exc.detail) if exc.detail else "An error occurred",
                request_id,
            )
        else:
            return render_json_error(
                exc.status_code,
                str(exc.detail) if exc.detail else "An error occurred",
                error_type="http_exception",
            )
    
    @app.exception_handler(RequestValidationError)
    async def debug_validation_exception_handler(
        request: Request,
        exc: RequestValidationError
    ) -> Response:
        """Handle validation errors with debug awareness."""
        if is_debug and _wants_html(request):
            context = await collect_debug_context(request, exc, 422)
            return render_debug_page(context)
        else:
            # Always JSON for validation errors (even in production)
            errors = [
                {
                    "loc": list(err.get("loc", [])),
                    "msg": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
                for err in exc.errors()
            ]
            return render_json_error(
                422,
                "Validation error",
                error_type="validation_error",
                errors=errors,
            )
