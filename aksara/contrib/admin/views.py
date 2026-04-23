"""
Admin Views

Server-rendered views for the admin interface.
"""

from __future__ import annotations

import hmac
import logging
import secrets
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type
from urllib.parse import urlencode, urlparse

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette import status

if TYPE_CHECKING:
    from aksara.model.base import Model
    from aksara.contrib.admin.options import ModelAdmin

# Resolve templates directory within the package
_package_dir = Path(__file__).parent
_templates_dir = _package_dir / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))

ADMIN_CSRF_COOKIE_NAME = "aksara_admin_csrf"
ADMIN_CSRF_FORM_FIELD = "csrf_token"

logger = logging.getLogger("aksara.contrib.admin")


def _validate_next_url(url: str) -> str:
    """
    Validate a redirect URL to prevent open-redirect attacks.

    Only relative paths starting with '/' are allowed.
    Any absolute URL (with scheme or netloc) is rejected and replaced
    with the safe default '/admin/'.
    """
    if not url:
        return "/admin/"
    parsed = urlparse(url)
    # Reject absolute URLs: must have no scheme and no netloc
    if parsed.scheme or parsed.netloc:
        return "/admin/"
    # Reject protocol-relative URLs like //evil.com
    if url.startswith("//"):
        return "/admin/"
    # Must start with /
    if not url.startswith("/"):
        return "/admin/"
    return url


def get_admin_user(request: Request, redirect_to_login: bool = True):
    """
    Get the authenticated admin user from request state.
    
    Args:
        request: The FastAPI request
        redirect_to_login: If True, redirect to login page instead of raising 403
    
    Returns:
        User object if authenticated, None otherwise
        
    Raises:
        HTTPException: 403 if user is not staff and redirect_to_login is False
    """
    user = getattr(request.state, "user", None)
    if user and getattr(user, "is_staff", False):
        return user
    
    if redirect_to_login:
        return None  # Will trigger redirect in view
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access forbidden. Staff access required.",
    )


def require_admin_user(request: Request):
    """
    Get the authenticated admin user, redirecting to login if not authenticated.
    
    Returns a tuple of (user, redirect_response).
    If user is authenticated, returns (user, None).
    If user is not authenticated, returns (None, RedirectResponse).
    """
    user = get_admin_user(request, redirect_to_login=True)
    if user is None:
        # Build login URL with next parameter
        next_url = str(request.url)
        login_url = str(request.url_for("admin:login")) + "?" + urlencode({"next": next_url})
        return None, RedirectResponse(url=login_url, status_code=status.HTTP_302_FOUND)
    return user, None


def _get_model_and_admin(
    app_label: str,
    model_name: str,
) -> Tuple[Type["Model"], "ModelAdmin"]:
    """
    Look up model and its ModelAdmin by app_label and model_name.
    
    Args:
        app_label: The app label
        model_name: The model name (case-insensitive)
        
    Returns:
        Tuple of (Model class, ModelAdmin instance)
        
    Raises:
        HTTPException: 404 if not found
    """
    from aksara.contrib.admin import site
    
    model = site.get_model_by_name(app_label, model_name)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' not found in app '{app_label}'",
        )
    
    model_admin = site.get_model_admin(model)
    if model_admin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' is not registered with admin",
        )
    
    return model, model_admin


def _get_settings():
    """Get Aksara settings (import here to avoid circular imports)."""
    from aksara.conf import settings
    return settings


def _generate_admin_csrf_token() -> str:
    """Generate a CSRF token for the admin UI."""
    return secrets.token_urlsafe(32)


def _get_or_create_admin_csrf_token(request: Request) -> str:
    """Return the admin CSRF token for this request."""
    token = request.cookies.get(ADMIN_CSRF_COOKIE_NAME)
    if token:
        return token
    return _generate_admin_csrf_token()


def _is_same_origin(request: Request, origin_value: str) -> bool:
    """Validate an Origin or Referer header against the current request."""
    parsed = urlparse(origin_value)
    request_url = urlparse(str(request.base_url))
    return bool(parsed.scheme and parsed.netloc) and (
        parsed.scheme == request_url.scheme and parsed.netloc == request_url.netloc
    )


def _set_admin_csrf_cookie(response: HTMLResponse, request: Request, token: str) -> None:
    """Set the admin CSRF cookie on a response."""
    settings = _get_settings()
    response.set_cookie(
        key=ADMIN_CSRF_COOKIE_NAME,
        value=token,
        secure=settings.cookie_secure and request.url.scheme == "https",
        httponly=False,
        samesite="strict",
        path="/admin",
    )


def _render_admin_template(
    request: Request,
    template_name: str,
    context: Dict[str, Any],
) -> HTMLResponse:
    """Render an admin template with CSRF context and cookie."""
    settings = _get_settings()
    csrf_token = _get_or_create_admin_csrf_token(request)
    response = templates.TemplateResponse(
        request,
        template_name,
        {
            **context,
            "csrf_token": csrf_token,
        },
    )
    if settings.admin_csrf_enabled:
        _set_admin_csrf_cookie(response, request, csrf_token)
    return response


async def _read_admin_form(request: Request) -> Any:
    """Read and validate admin POST form data."""
    form_data = await request.form()
    settings = _get_settings()

    if not settings.admin_csrf_enabled:
        return form_data

    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if origin and not _is_same_origin(request, origin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin request origin.",
        )
    if referer and not _is_same_origin(request, referer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin request referer.",
        )

    cookie_token = request.cookies.get(ADMIN_CSRF_COOKIE_NAME)
    form_token = form_data.get(ADMIN_CSRF_FORM_FIELD)
    if not cookie_token or not form_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing admin CSRF token.",
        )
    if not hmac.compare_digest(str(cookie_token), str(form_token)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin CSRF token.",
        )

    return form_data


# -----------------------------------------------------------------------------
# Admin Index View: /admin/
# -----------------------------------------------------------------------------

async def admin_index(request: Request) -> HTMLResponse:
    """
    Admin dashboard showing all registered apps and models.
    
    Route: GET /admin/
    """
    from aksara.contrib.admin import site
    
    user, redirect = require_admin_user(request)
    if redirect:
        return redirect
    
    settings = _get_settings()
    
    # Group models by app_label
    apps: Dict[str, List[Type["Model"]]] = {}
    for model, model_admin in site.registry.items():
        app_label = model.meta.app_label or "default"
        apps.setdefault(app_label, []).append(model)
    
    return _render_admin_template(
        request,
        "admin/index.html",
        {
            "apps": apps,
            "user": user,
            "debug": settings.debug,
            "site_name": "Aksara Admin",
            "studio_enabled": getattr(settings, "enable_studio", False),
        },
    )


# -----------------------------------------------------------------------------
# App Index View: /admin/{app_label}/
# -----------------------------------------------------------------------------

async def app_index(request: Request, app_label: str) -> HTMLResponse:
    """
    Show all models for a specific app.
    
    Route: GET /admin/{app_label}/
    """
    from aksara.contrib.admin import site
    
    user, redirect = require_admin_user(request)
    if redirect:
        return redirect
    
    settings = _get_settings()
    
    # Find all models for this app
    app_models: List[Type["Model"]] = []
    for model, admin in site.registry.items():
        if (model.meta.app_label or "default") == app_label:
            app_models.append(model)
    
    if not app_models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{app_label}' not found or has no registered models",
        )
    
    return _render_admin_template(
        request,
        "admin/app_index.html",
        {
            "app_label": app_label,
            "models": app_models,
            "user": user,
            "site_name": "Aksara Admin",
            "studio_enabled": getattr(settings, "enable_studio", False),
        },
    )


# -----------------------------------------------------------------------------
# Model List View: /admin/{app_label}/{model_name}/
# -----------------------------------------------------------------------------

async def model_list(
    request: Request,
    app_label: str,
    model_name: str,
) -> HTMLResponse:
    """
    List all objects for a model.
    
    Route: GET /admin/{app_label}/{model_name}/
    """
    user, redirect = require_admin_user(request)
    if redirect:
        return redirect
    
    settings = _get_settings()
    model, model_admin = _get_model_and_admin(app_label, model_name)
    
    if not model_admin.has_view_permission(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    
    # Get search query
    search_query = request.query_params.get("q", "").strip()
    
    # Get objects
    queryset = await model_admin.get_queryset(request)
    objects = await queryset.all()
    
    # Apply search filter in Python (OR across all search_fields)
    if search_query and model_admin.search_fields:
        search_lower = search_query.lower()
        filtered_objects = []
        for obj in objects:
            for field_name in model_admin.search_fields:
                value = getattr(obj, field_name, None)
                if value and search_lower in str(value).lower():
                    filtered_objects.append(obj)
                    break
        objects = filtered_objects
    
    # Get list display fields
    list_display = model_admin.get_list_display(request)
    
    # Prepare display values for each object
    objects_data = []
    for obj in objects:
        row = {"obj": obj, "values": []}
        for field_name in list_display:
            value = await _get_display_value(obj, field_name, model_admin)
            row["values"].append(value)
        objects_data.append(row)
    
    return _render_admin_template(
        request,
        "admin/model_list.html",
        {
            "app_label": app_label,
            "model": model,
            "model_name": model.__name__,
            "objects": objects_data,
            "list_display": list_display,
            "user": user,
            "can_add": model_admin.has_add_permission(request),
            "search_query": search_query,
            "search_fields": model_admin.search_fields,
            "site_name": "Aksara Admin",
            "studio_enabled": getattr(settings, "enable_studio", False),
        },
    )


# -----------------------------------------------------------------------------
# Model Add View: /admin/{app_label}/{model_name}/add/
# -----------------------------------------------------------------------------

async def model_add(
    request: Request,
    app_label: str,
    model_name: str,
) -> HTMLResponse:
    """
    Add a new object.
    
    Route: GET, POST /admin/{app_label}/{model_name}/add/
    """
    user, redirect = require_admin_user(request)
    if redirect:
        return redirect
    
    settings = _get_settings()
    model, model_admin = _get_model_and_admin(app_label, model_name)
    
    if not model_admin.has_add_permission(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    
    form_fields = model_admin.get_form_fields(request)
    errors: Dict[str, str] = {}
    form_data: Dict[str, Any] = {}
    
    if request.method == "POST":
        # Parse form data
        raw_form = await _read_admin_form(request)
        form_data = _parse_form_data(raw_form, model, form_fields)
        
        try:
            # Create new instance
            obj = model(**form_data)
            await model_admin.save_model(request, obj, form_data, is_created=True)
            
            # Redirect to list view
            return RedirectResponse(
                url=request.url_for(
                    "admin:model_list",
                    app_label=app_label,
                    model_name=model_name.lower(),
                ),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        except Exception as e:
            errors["__all__"] = str(e)
    
    # Prepare field info for template
    fields_info = await _get_fields_info(model, model_admin, form_fields, form_data, request)
    
    return _render_admin_template(
        request,
        "admin/model_form.html",
        {
            "app_label": app_label,
            "model": model,
            "model_name": model.__name__,
            "fields": fields_info,
            "obj": None,
            "is_add": True,
            "errors": errors,
            "user": user,
            "site_name": "Aksara Admin",
            "studio_enabled": getattr(settings, "enable_studio", False),
        },
    )


# -----------------------------------------------------------------------------
# Model Change View: /admin/{app_label}/{model_name}/{pk}/change/
# -----------------------------------------------------------------------------

async def model_change(
    request: Request,
    app_label: str,
    model_name: str,
    pk: str,
) -> HTMLResponse:
    """
    Edit an existing object.
    
    Route: GET, POST /admin/{app_label}/{model_name}/{pk}/change/
    """
    user, redirect = require_admin_user(request)
    if redirect:
        return redirect
    
    settings = _get_settings()
    model, model_admin = _get_model_and_admin(app_label, model_name)
    
    # Get the object
    try:
        obj = await model_admin.get_object(request, pk)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Object with pk={pk} not found",
        )
    
    if not model_admin.has_change_permission(request, obj):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    
    form_fields = model_admin.get_form_fields(request, obj)
    readonly_fields = set(model_admin.get_readonly_fields(request, obj))
    errors: Dict[str, str] = {}
    form_data: Dict[str, Any] = {}
    
    if request.method == "POST":
        # Parse form data
        raw_form = await _read_admin_form(request)
        form_data = _parse_form_data(raw_form, model, form_fields)
        
        # Remove readonly fields from form_data
        for field_name in readonly_fields:
            form_data.pop(field_name, None)
        
        try:
            await model_admin.save_model(request, obj, form_data, is_created=False)
            
            # Redirect to list view
            return RedirectResponse(
                url=request.url_for(
                    "admin:model_list",
                    app_label=app_label,
                    model_name=model_name.lower(),
                ),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        except Exception as e:
            errors["__all__"] = str(e)
    
    # Prepare field info with current values
    fields_info = await _get_fields_info(
        model, model_admin, form_fields, form_data, request, obj
    )
    
    return _render_admin_template(
        request,
        "admin/model_form.html",
        {
            "app_label": app_label,
            "model": model,
            "model_name": model.__name__,
            "fields": fields_info,
            "obj": obj,
            "is_add": False,
            "errors": errors,
            "user": user,
            "can_delete": model_admin.has_delete_permission(request, obj),
            "site_name": "Aksara Admin",
            "studio_enabled": getattr(settings, "enable_studio", False),
        },
    )


# -----------------------------------------------------------------------------
# Model Delete View: /admin/{app_label}/{model_name}/{pk}/delete/
# -----------------------------------------------------------------------------

async def model_delete(
    request: Request,
    app_label: str,
    model_name: str,
    pk: str,
) -> RedirectResponse:
    """
    Delete an object.
    
    Route: POST /admin/{app_label}/{model_name}/{pk}/delete/
    """
    user, redirect = require_admin_user(request)
    if redirect:
        return redirect
    model, model_admin = _get_model_and_admin(app_label, model_name)
    
    # Get the object
    try:
        obj = await model_admin.get_object(request, pk)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Object with pk={pk} not found",
        )
    
    if not model_admin.has_delete_permission(request, obj):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    await _read_admin_form(request)
    
    await model_admin.delete_model(request, obj)
    
    # Redirect to list view
    return RedirectResponse(
        url=request.url_for(
            "admin:model_list",
            app_label=app_label,
            model_name=model_name.lower(),
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

async def _get_display_value(
    obj: "Model",
    field_name: str,
    model_admin: "ModelAdmin",
) -> str:
    """
    Get display value for a field, handling FK relations.
    
    Args:
        obj: The model instance
        field_name: Name of the field
        model_admin: The ModelAdmin instance
        
    Returns:
        String representation of the value
    """
    from aksara.fields import ForeignKey
    from datetime import datetime
    
    model = model_admin.model
    field = model.meta.get_field(field_name)
    
    # Get raw value
    value = getattr(obj, field_name, None)
    
    if value is None:
        return "-"
    
    # Handle ForeignKey - show related object display
    if field and isinstance(field, ForeignKey):
        # value is the FK ID, we need to fetch the related object
        try:
            related_model = field.to_model
            related_obj = await related_model.objects.get(id=value)
            return model_admin._get_object_display(related_obj)
        except Exception:
            return str(value)
    
    # Handle datetime
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    
    # Handle boolean
    if isinstance(value, bool):
        return "✓" if value else "✗"
    
    # Handle UUID (shorten for display)
    if hasattr(value, "hex") and len(str(value)) == 36:
        return str(value)[:8] + "..."
    
    return str(value)


def _parse_form_data(
    raw_form: Any,
    model: Type["Model"],
    form_fields: List[str],
) -> Dict[str, Any]:
    """
    Parse and convert form data to appropriate types.
    
    Args:
        raw_form: The raw form data from request.form()
        model: The Model class
        form_fields: List of field names expected
        
    Returns:
        Dict of parsed field values
    """
    data: Dict[str, Any] = {}
    m2m_fields = model.meta.many_to_many
    
    for field_name in form_fields:
        # Handle ManyToMany fields (come as multiple values)
        if field_name in m2m_fields:
            # getlist returns all values for a multi-select
            values = raw_form.getlist(field_name)
            data[field_name] = values if values else []
            continue
        
        field = model.meta.get_field(field_name)
        if not field:
            continue
        
        raw_value = raw_form.get(field_name, "")
        
        # Skip empty strings for optional fields
        if raw_value == "" and getattr(field, "nullable", False):
            data[field_name] = None
            continue
        
        # Convert based on field type
        field_type = field.__class__.__name__
        
        try:
            if field_type == "Boolean":
                data[field_name] = raw_value in ("true", "on", "1", True)
            elif field_type == "Integer":
                data[field_name] = int(raw_value) if raw_value else None
            elif field_type in ("Float", "Decimal"):
                data[field_name] = float(raw_value) if raw_value else None
            elif field_type == "JSON":
                import json
                data[field_name] = json.loads(raw_value) if raw_value else None
            elif field_type == "ForeignKey":
                # FK needs UUID or None
                if raw_value:
                    import uuid
                    data[field_name] = uuid.UUID(raw_value)
                else:
                    # Empty means no selection
                    data[field_name] = None
            else:
                data[field_name] = raw_value if raw_value else None
        except (ValueError, TypeError):
            data[field_name] = raw_value
    
    return data


async def _get_fields_info(
    model: Type["Model"],
    model_admin: "ModelAdmin",
    form_fields: List[str],
    form_data: Dict[str, Any],
    request: Request,
    obj: Optional["Model"] = None,
) -> List[Dict[str, Any]]:
    """
    Build field info list for template rendering.
    
    Args:
        model: The Model class
        model_admin: The ModelAdmin instance
        form_fields: List of field names
        form_data: Current form data (for error re-rendering)
        request: The request object
        obj: Optional existing object (for change view)
        
    Returns:
        List of field info dicts
    """
    readonly = set(model_admin.get_readonly_fields(request, obj))
    fields_info = []
    m2m_fields = model.meta.many_to_many
    
    for field_name in form_fields:
        # Check if it's a ManyToMany field
        is_m2m = field_name in m2m_fields
        
        if is_m2m:
            field = m2m_fields[field_name]
            field_type = "multiselect"
            nullable = True  # M2M is always optional
            
            # Get current selected values for M2M
            if form_data.get(field_name) is not None:
                value = form_data[field_name]  # List of IDs from form
            elif obj is not None:
                # Fetch current related IDs
                m2m_manager = getattr(obj, field_name)
                related_ids = await m2m_manager.ids()
                value = [str(rid) for rid in related_ids]
            else:
                value = []
        else:
            field = model.meta.get_field(field_name)
            if not field:
                continue
            
            field_type = model_admin.get_field_type(field_name)
            nullable = getattr(field, "nullable", False)
            
            # Get current value
            if form_data.get(field_name) is not None:
                value = form_data[field_name]
            elif obj is not None:
                value = getattr(obj, field_name, "")
            else:
                value = ""
            
            # Format datetime values for HTML datetime-local input (YYYY-MM-DDTHH:MM)
            if field_type == "datetime-local" and value:
                from datetime import datetime
                if isinstance(value, datetime):
                    value = value.strftime("%Y-%m-%dT%H:%M")
                elif isinstance(value, str) and value:
                    try:
                        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        value = dt.strftime("%Y-%m-%dT%H:%M")
                    except (ValueError, AttributeError):
                        pass
            
            # Convert value to string for regular fields
            if not isinstance(value, list):
                value = str(value) if value is not None else ""
        
        field_info = {
            "name": field_name,
            "label": field_name.replace("_", " ").title(),
            "type": field_type,
            "value": value,
            "readonly": field_name in readonly,
            "required": not nullable,
            "choices": None,
            "widget_html": None,  # Will be set if custom widget exists
        }
        
        # Check for custom widget (for non-M2M fields)
        if not is_m2m and field:
            widget = model_admin.get_widget(field_name, field)
            if widget:
                # Render the widget and store HTML
                field_info["widget_html"] = widget.render(field_name, value, field)
        
        # Fetch choices for FK and M2M fields
        if field_type in ("select", "multiselect"):
            field_info["choices"] = await model_admin.get_field_choices(field_name, request)
        
        fields_info.append(field_info)
    
    return fields_info


# -----------------------------------------------------------------------------
# Login View: /admin/login/
# -----------------------------------------------------------------------------

async def admin_login(request: Request) -> HTMLResponse:
    """
    Admin login page.
    
    Route: GET, POST /admin/login/
    """
    settings = _get_settings()
    error = None
    username = ""
    next_url = _validate_next_url(request.query_params.get("next", "/admin/"))
    
    # Check if user is already logged in
    user = getattr(request.state, "user", None)
    if user and getattr(user, "is_staff", False):
        return RedirectResponse(url=next_url, status_code=status.HTTP_302_FOUND)
    
    if request.method == "POST":
        form_data = await _read_admin_form(request)
        username = form_data.get("username", "")
        password = form_data.get("password", "")
        next_url = _validate_next_url(form_data.get("next", "/admin/"))
        
        if username and password:
            # Try to authenticate
            try:
                from aksara.contrib.auth import authenticate
                
                user = await authenticate(
                    request.app.db,
                    username=username,
                    password=password,
                )
                
                if user:
                    if not getattr(user, "is_staff", False):
                        error = "You don't have permission to access the admin. Staff access required."
                    else:
                        # Create session token
                        from aksara.contrib.auth import create_session_token
                        
                        token = await create_session_token(request.app.db, user)
                        
                        # Set cookie and redirect
                        response = RedirectResponse(
                            url=next_url,
                            status_code=status.HTTP_302_FOUND,
                        )
                        response.set_cookie(
                            key="session_token",
                            value=token,
                            httponly=True,
                            secure=settings.cookie_secure,
                            samesite="strict",
                            max_age=60 * 60 * 24 * 7,  # 7 days
                        )
                        return response
                else:
                    error = "Invalid username or password."
            except ImportError:
                error = "Authentication module not configured. Please set up aksara.contrib.auth."
            except Exception as e:
                logger.exception("Admin login error: %s", e)
                error = "Login failed. Please try again."
        else:
            error = "Please enter both username and password."
    
    return _render_admin_template(
        request,
        "admin/login.html",
        {
            "error": error,
            "username": username,
            "next": next_url,
            "site_name": "Aksara Admin",
        },
    )


# -----------------------------------------------------------------------------
# Logout View: /admin/logout/
# -----------------------------------------------------------------------------

async def admin_logout(request: Request) -> RedirectResponse:
    """
    Admin logout - clears session and redirects to login.
    
    Route: POST /admin/logout/
    """
    await _read_admin_form(request)

    # Try to invalidate session in database
    try:
        token = request.cookies.get("session_token")
        if token and request.app.db:
            from aksara.contrib.auth import invalidate_session_token
            await invalidate_session_token(request.app.db, token)
    except Exception:
        pass  # Session cleanup is best-effort
    
    # Clear cookie and redirect to login
    response = RedirectResponse(
        url=str(request.url_for("admin:login")),
        status_code=status.HTTP_302_FOUND,
    )
    response.delete_cookie(
        key="session_token",
        path="/",
        httponly=True,
        secure=_get_settings().cookie_secure,
        samesite="strict",
    )
    
    return response
