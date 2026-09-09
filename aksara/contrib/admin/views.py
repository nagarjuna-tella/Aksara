"""
Admin Views

Server-rendered views for the admin interface. Each view receives the
``AdminSite`` it belongs to so multiple sites can be mounted independently.
"""

from __future__ import annotations

import hmac
import inspect
import logging
import secrets
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type
from urllib.parse import urlencode, urlparse, urlsplit, urlunsplit, parse_qsl

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette import status

from aksara.contrib.admin.actions import (
    clear_messages_cookie,
    pop_messages,
    write_messages_cookie,
)
from aksara.contrib.admin.filters import FieldListFilter, SimpleListFilter

if TYPE_CHECKING:
    from aksara.model.base import Model
    from aksara.contrib.admin.options import ModelAdmin
    from aksara.contrib.admin.site import AdminSite

# Resolve templates directory within the package
_package_dir = Path(__file__).parent
_templates_dir = _package_dir / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))

ADMIN_CSRF_COOKIE_NAME = "aksara_admin_csrf"
ADMIN_CSRF_FORM_FIELD = "csrf_token"

logger = logging.getLogger("aksara.contrib.admin")


# -----------------------------------------------------------------------------
# Small async/sync helpers
# -----------------------------------------------------------------------------

async def _maybe_await(value: Any) -> Any:
    """Await ``value`` if it is awaitable, supporting sync or async overrides."""
    if inspect.isawaitable(value):
        return await value
    return value


async def _check_permission_callable(
    checker: Any,
    request: Request,
    obj: Optional["Model"] = None,
) -> bool:
    """Call a ModelAdmin permission hook with ``obj`` when the hook accepts it."""
    if obj is None:
        return bool(await _maybe_await(checker(request)))

    try:
        signature = inspect.signature(checker)
    except (TypeError, ValueError):
        return bool(await _maybe_await(checker(request, obj)))

    positional = [
        param
        for param in signature.parameters.values()
        if param.kind
        in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD, param.VAR_POSITIONAL)
    ]
    accepts_obj = any(param.kind == param.VAR_POSITIONAL for param in positional)
    accepts_obj = accepts_obj or len(positional) >= 2

    if accepts_obj:
        return bool(await _maybe_await(checker(request, obj)))
    return bool(await _maybe_await(checker(request)))


def _resolve_site(site: Optional["AdminSite"]) -> "AdminSite":
    if site is not None:
        return site
    from aksara.contrib.admin import site as default_site
    return default_site


def _url_path(url: Any) -> str:
    """Return a same-origin path/query string from a URL-like object."""
    parsed = urlparse(str(url))
    path = parsed.path or "/"
    return f"{path}?{parsed.query}" if parsed.query else path


def _request_path_with_query(request: Request) -> str:
    path = request.url.path or "/"
    return f"{path}?{request.url.query}" if request.url.query else path


def _append_query_param(url: str, **params: str) -> str:
    split = urlsplit(url)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    query.update({key: value for key, value in params.items() if value is not None})
    return urlunsplit(
        (split.scheme, split.netloc, split.path, urlencode(query), split.fragment)
    )


def _validate_next_url(url: str, default: str = "/admin/") -> str:
    """Validate a redirect URL to prevent open-redirect attacks."""
    if not url:
        return default
    parsed = urlparse(url)
    if parsed.scheme or parsed.netloc:
        return default
    if url.startswith("//"):
        return default
    if not url.startswith("/"):
        return default
    return url


def _with_params(request: Request, **changes: Any) -> str:
    """
    Build a path + querystring for the current request with some params changed.

    A value of ``None`` removes the param. Used to construct filter, sort and
    pagination links without losing other active query parameters.
    """
    params = dict(request.query_params)
    for key, value in changes.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = str(value)
    query = urlencode(params)
    path = request.url.path
    return f"{path}?{query}" if query else path


# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------

async def _check_site_permission(
    site: "AdminSite",
    request: Request,
) -> Tuple[bool, Optional[str]]:
    """Evaluate admin site access, including async permission classes."""
    if not site.permission_classes:
        return site.check_site_permission(request)

    for permission in site.permission_classes:
        perm = permission() if isinstance(permission, type) else permission
        allowed = await _maybe_await(perm.has_permission(request, None))
        if not allowed:
            return False, getattr(perm, "message", "Permission denied.")
    return True, None


async def _check_site_permission_for_user(
    site: "AdminSite",
    request: Request,
    user: Any,
) -> Tuple[bool, Optional[str]]:
    """Evaluate site access for an authenticated login candidate."""
    request.state.user = user
    return await _check_site_permission(site, request)


async def require_admin_user(
    request: Request, site: "AdminSite"
) -> Tuple[Any, Optional[RedirectResponse]]:
    """
    Resolve the admin user, redirecting to login when access is not allowed.

    Returns (user, None) when access is granted, else (None, RedirectResponse).
    Access is governed by the site's ``permission_classes`` if set, otherwise by
    the default staff-only rule.
    """
    allowed, _message = await _check_site_permission(site, request)
    if allowed:
        return getattr(request.state, "user", None), None

    next_url = _request_path_with_query(request)
    login_url = site.login_url or str(request.url_for(f"{site.name}:login"))
    login_url = _append_query_param(login_url, next=next_url)
    return None, RedirectResponse(url=login_url, status_code=status.HTTP_302_FOUND)


def _get_model_and_admin(
    app_label: str, model_name: str, site: "AdminSite"
) -> Tuple[Type["Model"], "ModelAdmin"]:
    """Look up model and its ModelAdmin by app_label and model_name."""
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


# -----------------------------------------------------------------------------
# CSRF / settings / rendering
# -----------------------------------------------------------------------------

def _get_settings():
    from aksara.conf import settings
    return settings


def _generate_admin_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _get_or_create_admin_csrf_token(request: Request) -> str:
    token = request.cookies.get(ADMIN_CSRF_COOKIE_NAME)
    if token:
        return token
    return _generate_admin_csrf_token()


def _is_same_origin(request: Request, origin_value: str) -> bool:
    parsed = urlparse(origin_value)
    request_url = urlparse(str(request.base_url))
    return bool(parsed.scheme and parsed.netloc) and (
        parsed.scheme == request_url.scheme and parsed.netloc == request_url.netloc
    )


def _set_admin_csrf_cookie(response: HTMLResponse, request: Request, token: str) -> None:
    settings = _get_settings()
    cookie_path = getattr(request.state, "admin_csrf_cookie_path", "/admin")
    response.set_cookie(
        key=ADMIN_CSRF_COOKIE_NAME,
        value=token,
        secure=settings.cookie_secure and request.url.scheme == "https",
        httponly=False,
        samesite="strict",
        path=cookie_path,
    )


def _render_admin_template(
    request: Request,
    site: "AdminSite",
    template_name: str,
    context: Dict[str, Any],
) -> HTMLResponse:
    """Render an admin template with site branding, CSRF and flash messages."""
    settings = _get_settings()
    csrf_token = _get_or_create_admin_csrf_token(request)
    messages = pop_messages(request)

    merged = {
        "url_namespace": site.name,
        "messages": messages,
        "csrf_token": csrf_token,
        "studio_enabled": getattr(settings, "enable_studio", False),
        "debug": settings.debug,
        **site.base_context(request),
        **context,
    }
    response = templates.TemplateResponse(request, template_name, merged)
    if settings.admin_csrf_enabled:
        _set_admin_csrf_cookie(response, request, csrf_token)
    if messages:
        clear_messages_cookie(response)
    return response


async def _read_admin_form(request: Request) -> Any:
    """Read and validate admin POST form data (origin + CSRF token)."""
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
# Index / app index
# -----------------------------------------------------------------------------

async def _visible_models_by_app(
    request: Request, site: "AdminSite"
) -> Dict[str, List[Type["Model"]]]:
    """Group registered models by app, honouring has_module_permission."""
    apps: Dict[str, List[Type["Model"]]] = {}
    for model, model_admin in site.registry.items():
        if not await _maybe_await(model_admin.has_module_permission(request)):
            continue
        app_label = model.meta.app_label or "default"
        apps.setdefault(app_label, []).append(model)
    return apps


async def admin_index(request: Request, site: "AdminSite" = None) -> HTMLResponse:
    """Admin dashboard showing accessible apps and models. Route: GET /admin/"""
    site = _resolve_site(site)
    user, redirect = await require_admin_user(request, site)
    if redirect:
        return redirect

    apps = await _visible_models_by_app(request, site)

    extra: Dict[str, Any] = {}
    if site._index_view_func is not None:
        result = await _maybe_await(site._index_view_func(request))
        if isinstance(result, dict):
            extra = result

    template_name = site.index_template or "admin/index.html"
    return _render_admin_template(
        request,
        site,
        template_name,
        {"apps": apps, "user": user, **extra},
    )


async def app_index(
    request: Request, app_label: str, site: "AdminSite" = None
) -> HTMLResponse:
    """Show accessible models for a specific app. Route: GET /admin/{app_label}/"""
    site = _resolve_site(site)
    user, redirect = await require_admin_user(request, site)
    if redirect:
        return redirect

    apps = await _visible_models_by_app(request, site)
    app_models = apps.get(app_label, [])
    if not app_models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{app_label}' not found or has no registered models",
        )

    return _render_admin_template(
        request,
        site,
        "admin/app_index.html",
        {"app_label": app_label, "models": app_models, "user": user},
    )


# -----------------------------------------------------------------------------
# Model list (with search, filters, ordering, pagination, actions)
# -----------------------------------------------------------------------------

async def _build_filters(
    request: Request, model_admin: "ModelAdmin"
) -> List[Any]:
    """Instantiate each entry in ``list_filter`` into a filter object."""
    built: List[Any] = []
    for entry in model_admin.list_filter or []:
        if isinstance(entry, type) and issubclass(entry, SimpleListFilter):
            built.append(entry(request, model_admin))
        elif isinstance(entry, str):
            built.append(await FieldListFilter.create(entry, request, model_admin))
    return built


def _apply_filter(filt: Any, request: Request, queryset: Any) -> Any:
    if isinstance(filt, SimpleListFilter):
        if filt.value() in (None, ""):
            return queryset
        try:
            return filt.queryset(request, queryset)
        except Exception:
            return queryset
    return filt.apply(queryset)


def _filter_context(request: Request, filters: List[Any]) -> List[Dict[str, Any]]:
    specs: List[Dict[str, Any]] = []
    for filt in filters:
        if not filt.has_output():
            continue
        options = []
        for choice in filt.choices_for_template():
            options.append(
                {
                    "label": choice["label"],
                    "selected": choice["selected"],
                    "url": _with_params(
                        request,
                        **{filt.parameter_name: choice["value"], "p": None},
                    ),
                }
            )
        specs.append({"title": filt.title, "choices": options})
    return specs


def _resolve_ordering(request: Request, model_admin: "ModelAdmin") -> List[str]:
    """Ordering from the ?o= sort param if valid, else the admin default."""
    o = request.query_params.get("o")
    if o:
        field = o[1:] if o.startswith("-") else o
        valid = {f.name for f in model_admin.model.meta.fields}
        if field in valid:
            return [o]
    return model_admin.get_ordering(request)


async def _run_list_action(
    request: Request,
    model: Type["Model"],
    model_admin: "ModelAdmin",
    site: "AdminSite",
    app_label: str,
    model_name: str,
) -> Optional[RedirectResponse]:
    """Handle an action POST from the list view. Returns a redirect or None."""
    form = await _read_admin_form(request)
    action_name = form.get("action", "")
    selected_ids = form.getlist("_selected")

    actions = model_admin.get_actions(request)
    spec = actions.get(action_name)
    redirect = RedirectResponse(
        url=str(
            request.url_for(
                f"{site.name}:model_list",
                app_label=app_label,
                model_name=model_name.lower(),
            )
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )

    if spec is None:
        model_admin.message_user(request, "Unknown action.", level="error")
        write_messages_cookie(request, redirect)
        return redirect

    if not selected_ids:
        model_admin.message_user(request, "No items selected.", level="warning")
        write_messages_cookie(request, redirect)
        return redirect

    base_qs = await _maybe_await(model_admin.get_queryset(request))
    queryset = base_qs.filter(id__in=selected_ids)
    selected_objects = await queryset.all()

    if len(selected_objects) != len(set(str(pk) for pk in selected_ids)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied for action '{action_name}'.",
        )

    # Action-level permission gate (allowed_permissions -> has_X_permission).
    # The list-level check controls whether the action is generally available;
    # object-level checks prevent bulk actions from bypassing per-row rules.
    for perm in spec["allowed_permissions"]:
        checker = getattr(model_admin, f"has_{perm}_permission", None)
        if checker is None:
            continue
        if not await _check_permission_callable(checker, request):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied for action '{action_name}'.",
            )
        for obj in selected_objects:
            if not await _check_permission_callable(checker, request, obj):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied for action '{action_name}'.",
                )

    # A bound ModelAdmin method already carries ``self``; a module-level action
    # function (e.g. delete_selected) needs the admin passed explicitly.
    func = spec["func"]
    if inspect.ismethod(func):
        result = func(request, queryset)
    else:
        result = func(model_admin, request, queryset)
    await _maybe_await(result)

    write_messages_cookie(request, redirect)
    return redirect


async def model_list(
    request: Request,
    app_label: str,
    model_name: str,
    site: "AdminSite" = None,
) -> HTMLResponse:
    """List objects for a model. Route: GET, POST /admin/{app_label}/{model_name}/"""
    site = _resolve_site(site)
    user, redirect = await require_admin_user(request, site)
    if redirect:
        return redirect

    model, model_admin = _get_model_and_admin(app_label, model_name, site)

    if not await _maybe_await(model_admin.has_view_permission(request)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    if request.method == "POST":
        return await _run_list_action(
            request, model, model_admin, site, app_label, model_name
        )

    # Base queryset + search + filters + ordering.
    queryset = await _maybe_await(model_admin.get_queryset(request))

    search_query = request.query_params.get("q", "").strip()
    if search_query:
        queryset = model_admin.get_search_results(request, queryset, search_query)

    filters = await _build_filters(request, model_admin)
    for filt in filters:
        queryset = _apply_filter(filt, request, queryset)

    # Count the filtered set *before* ordering — an ORDER BY on COUNT(*) is
    # rejected by PostgreSQL.
    per_page = max(int(model_admin.list_per_page or 100), 1)
    total = await queryset.count()
    max_show_all = int(model_admin.list_max_show_all or 200)
    show_all = (
        request.query_params.get("all") == "1"
        and total <= max_show_all
    )
    try:
        page = max(int(request.query_params.get("p", "1")), 1)
    except (TypeError, ValueError):
        page = 1

    num_pages = max((total + per_page - 1) // per_page, 1) if not show_all else 1
    page = min(page, num_pages)

    # Apply ordering only for the page fetch.
    ordering = _resolve_ordering(request, model_admin)
    ordered_qs = queryset
    if ordering:
        try:
            ordered_qs = queryset.order_by(*ordering)
        except Exception:
            ordered_qs = queryset

    page_qs = ordered_qs
    if not show_all:
        page_qs = ordered_qs.limit(per_page).offset((page - 1) * per_page)
    objects = await page_qs.all()

    # Build rows (custom columns + which columns link to the change view).
    list_display = model_admin.get_list_display(request)
    link_cols = set(model_admin.get_list_display_links(request, list_display))
    rows = []
    for obj in objects:
        cells = []
        for col in list_display:
            is_link = col in link_cols
            if model_admin.is_callable_column(col):
                raw = await _maybe_await(getattr(model_admin, col)(obj))
                cells.append(
                    {
                        "value": "" if raw is None else str(raw),
                        "is_html": model_admin.column_allows_html(col),
                        "is_link": is_link,
                    }
                )
            else:
                value = await _get_display_value(obj, col, model_admin)
                cells.append({"value": value, "is_html": False, "is_link": is_link})
        rows.append({"obj": obj, "cells": cells})

    pagination = _build_pagination(
        request, page, num_pages, total, per_page, show_all, max_show_all
    )

    return _render_admin_template(
        request,
        site,
        "admin/model_list.html",
        {
            "app_label": app_label,
            "model": model,
            "model_name": model.__name__,
            "rows": rows,
            "list_display": list_display,
            "list_headers": [
                {
                    "name": col,
                    "label": model_admin.get_column_label(col),
                    "sort_url": _sort_url(request, model_admin, col),
                    "sort_dir": _sort_dir(request, col),
                }
                for col in list_display
            ],
            "user": user,
            "can_add": await _maybe_await(model_admin.has_add_permission(request)),
            "search_query": search_query,
            "search_fields": model_admin.search_fields,
            "filters": _filter_context(request, filters),
            "pagination": pagination,
            "actions": [
                {"name": name, "description": spec["description"]}
                for name, spec in model_admin.get_actions(request).items()
            ],
            "clear_url": request.url_for(
                f"{site.name}:model_list",
                app_label=app_label,
                model_name=model_name.lower(),
            ),
        },
    )


def _sort_dir(request: Request, col: str) -> Optional[str]:
    o = request.query_params.get("o")
    if o == col:
        return "asc"
    if o == f"-{col}":
        return "desc"
    return None


def _sort_url(request: Request, model_admin: "ModelAdmin", col: str) -> Optional[str]:
    if model_admin.is_callable_column(col):
        return None  # Custom columns are not DB-sortable.
    current = _sort_dir(request, col)
    new_value = f"-{col}" if current == "asc" else col
    return _with_params(request, o=new_value, p=None)


def _build_pagination(
    request: Request,
    page: int,
    num_pages: int,
    total: int,
    per_page: int,
    show_all: bool,
    max_show_all: int,
) -> Dict[str, Any]:
    return {
        "page": page,
        "num_pages": num_pages,
        "total": total,
        "per_page": per_page,
        "show_all": show_all,
        "has_prev": page > 1 and not show_all,
        "has_next": page < num_pages and not show_all,
        "prev_url": _with_params(request, p=page - 1) if page > 1 else None,
        "next_url": _with_params(request, p=page + 1) if page < num_pages else None,
        "show_all_url": _with_params(request, all="1", p=None)
        if (not show_all and num_pages > 1 and total <= max_show_all)
        else None,
    }


# -----------------------------------------------------------------------------
# Model add / change / delete
# -----------------------------------------------------------------------------

async def model_add(
    request: Request,
    app_label: str,
    model_name: str,
    site: "AdminSite" = None,
) -> HTMLResponse:
    """Add a new object. Route: GET, POST /admin/{app_label}/{model_name}/add/"""
    site = _resolve_site(site)
    user, redirect = await require_admin_user(request, site)
    if redirect:
        return redirect

    model, model_admin = _get_model_and_admin(app_label, model_name, site)

    if not await _maybe_await(model_admin.has_add_permission(request)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    form_fields = model_admin.get_form_fields(request)
    readonly_fields = set(model_admin.get_readonly_fields(request))
    errors: Dict[str, str] = {}
    form_data: Dict[str, Any] = {}

    if request.method == "POST":
        raw_form = await _read_admin_form(request)
        form_data = _parse_form_data(raw_form, model, form_fields)
        for field_name in readonly_fields:
            form_data.pop(field_name, None)

        try:
            obj = model(**form_data)
            await model_admin.save_model(request, obj, form_data, True)
            return RedirectResponse(
                url=request.url_for(
                    f"{site.name}:model_list",
                    app_label=app_label,
                    model_name=model_name.lower(),
                ),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        except Exception as exc:
            errors["__all__"] = _safe_error_message(exc, "create")

    fieldsets = await _get_fieldsets_info(model, model_admin, form_data, request)

    return _render_admin_template(
        request,
        site,
        "admin/model_form.html",
        {
            "app_label": app_label,
            "model": model,
            "model_name": model.__name__,
            "fieldsets": fieldsets,
            "prepopulated": _prepopulated_map(model_admin),
            "obj": None,
            "is_add": True,
            "errors": errors,
            "user": user,
        },
    )


async def model_change(
    request: Request,
    app_label: str,
    model_name: str,
    pk: str,
    site: "AdminSite" = None,
) -> HTMLResponse:
    """Edit an object. Route: GET, POST /admin/{app_label}/{model_name}/{pk}/change/"""
    site = _resolve_site(site)
    user, redirect = await require_admin_user(request, site)
    if redirect:
        return redirect

    model, model_admin = _get_model_and_admin(app_label, model_name, site)

    try:
        obj = await model_admin.get_object(request, pk)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Object with pk={pk} not found",
        )

    if not await _maybe_await(model_admin.has_change_permission(request, obj)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    form_fields = model_admin.get_form_fields(request, obj)
    readonly_fields = set(model_admin.get_readonly_fields(request, obj))
    errors: Dict[str, str] = {}
    form_data: Dict[str, Any] = {}

    if request.method == "POST":
        raw_form = await _read_admin_form(request)
        form_data = _parse_form_data(raw_form, model, form_fields)
        for field_name in readonly_fields:
            form_data.pop(field_name, None)

        try:
            await model_admin.save_model(request, obj, form_data, False)
            return RedirectResponse(
                url=request.url_for(
                    f"{site.name}:model_list",
                    app_label=app_label,
                    model_name=model_name.lower(),
                ),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        except Exception as exc:
            errors["__all__"] = _safe_error_message(exc, "save")

    fieldsets = await _get_fieldsets_info(model, model_admin, form_data, request, obj)

    return _render_admin_template(
        request,
        site,
        "admin/model_form.html",
        {
            "app_label": app_label,
            "model": model,
            "model_name": model.__name__,
            "fieldsets": fieldsets,
            "prepopulated": _prepopulated_map(model_admin),
            "obj": obj,
            "is_add": False,
            "errors": errors,
            "user": user,
            "can_delete": await _maybe_await(
                model_admin.has_delete_permission(request, obj)
            ),
        },
    )


async def model_delete(
    request: Request,
    app_label: str,
    model_name: str,
    pk: str,
    site: "AdminSite" = None,
) -> RedirectResponse:
    """Delete an object. Route: POST /admin/{app_label}/{model_name}/{pk}/delete/"""
    site = _resolve_site(site)
    user, redirect = await require_admin_user(request, site)
    if redirect:
        return redirect

    model, model_admin = _get_model_and_admin(app_label, model_name, site)

    try:
        obj = await model_admin.get_object(request, pk)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Object with pk={pk} not found",
        )

    if not await _maybe_await(model_admin.has_delete_permission(request, obj)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    await _read_admin_form(request)
    await model_admin.delete_model(request, obj)

    return RedirectResponse(
        url=request.url_for(
            f"{site.name}:model_list",
            app_label=app_label,
            model_name=model_name.lower(),
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _safe_error_message(exc: Exception, action: str) -> str:
    """
    Return a user-safe error message and log the full exception.

    Validation errors (ValueError) carry user-actionable text and are shown;
    anything else is logged and replaced with a generic message to avoid
    leaking internal details into the UI.
    """
    logger.warning(
        "Admin %s failed: %s",
        action,
        exc,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    if isinstance(exc, (ValueError, TypeError)):
        return str(exc)
    return f"Could not {action} this record. Please check the values and try again."


def _prepopulated_map(model_admin: "ModelAdmin") -> Dict[str, List[str]]:
    """JSON-serialisable {target_field: [source_fields]} for client slugify."""
    return {
        target: list(sources)
        for target, sources in (model_admin.prepopulated_fields or {}).items()
    }


async def _get_display_value(
    obj: "Model", field_name: str, model_admin: "ModelAdmin"
) -> str:
    """Get display value for a field, handling FK relations and common types."""
    from aksara.fields import ForeignKey
    from datetime import datetime

    model = model_admin.model
    field = model.meta.get_field(field_name)
    value = getattr(obj, field_name, None)

    if value is None:
        return "-"

    if field and isinstance(field, ForeignKey):
        try:
            related_model = field.to_model
            related_obj = await related_model.objects.get(id=value)
            return model_admin._get_object_display(related_obj)
        except Exception:
            return str(value)

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")

    if isinstance(value, bool):
        return "✓" if value else "✗"

    if hasattr(value, "hex") and len(str(value)) == 36:
        return str(value)[:8] + "..."

    return str(value)


def _coerce_array_form_value(raw_value: Any, field: Any) -> Optional[List[Any]]:
    """Convert array widget form input into a typed Python list.

    The admin array widget serializes items as a JSON list (falling back to a
    comma-separated string). Core ORM Array fields now require explicit lists,
    so this adapter parses the submitted value and coerces each item to the
    field's ``item_type`` before the value reaches ``Array.to_db``.
    """
    import json
    import uuid as _uuid

    from aksara.fields import _coerce_strict_boolean, _coerce_strict_integer

    if raw_value is None:
        return None
    if isinstance(raw_value, list):
        items = raw_value
    elif isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            items = parsed if isinstance(parsed, list) else [parsed]
        except (json.JSONDecodeError, TypeError):
            items = [piece.strip() for piece in text.split(",") if piece.strip()]
    else:
        items = [raw_value]

    item_type = getattr(field, "item_type", str)
    coerced: List[Any] = []
    for item in items:
        # Preserve None items rather than silently dropping them; core Array
        # validation rejects null elements per the Advanced Field Policy.
        if item is None:
            coerced.append(None)
            continue
        if item_type is bool:
            # Strict boolean parsing: real bools pass through, recognized
            # true/false tokens convert, and anything else raises rather than
            # silently becoming False.
            coerced.append(item if isinstance(item, bool) else _coerce_strict_boolean(item))
        elif item_type is int:
            coerced.append(_coerce_strict_integer(item, "Array field (int)"))
        elif item_type is float:
            if isinstance(item, bool):
                raise ValueError("Array field (float) does not accept boolean values")
            coerced.append(float(item))
        elif item_type is _uuid.UUID:
            coerced.append(item if isinstance(item, _uuid.UUID) else _uuid.UUID(str(item)))
        else:
            if not isinstance(item, str):
                raise ValueError(
                    f"Array field (str) expects strings, got {type(item).__name__}"
                )
            coerced.append(item)
    # Reuse item validation after adapter-level parsing so finite numbers,
    # bounds, and nested values cannot diverge by write surface. Preserve None
    # for the caller so the core field reports the canonical null-item error.
    return [item if item is None else field._validate_item(item) for item in coerced]


def _parse_form_data(
    raw_form: Any, model: Type["Model"], form_fields: List[str]
) -> Dict[str, Any]:
    """Parse and convert form data to appropriate types."""
    data: Dict[str, Any] = {}
    m2m_fields = model.meta.many_to_many

    for field_name in form_fields:
        if field_name in m2m_fields:
            values = raw_form.getlist(field_name)
            data[field_name] = values if values else []
            continue

        field = model.meta.get_field(field_name)
        if not field:
            continue

        raw_value = raw_form.get(field_name, "")

        if raw_value == "" and getattr(field, "nullable", False):
            data[field_name] = None
            continue

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
            elif field_type == "Array":
                # The array widget submits a JSON-encoded list; convert it to a
                # typed Python list here (the adapter boundary) so core ORM
                # validation receives a real list, not a delimited string.
                data[field_name] = _coerce_array_form_value(raw_value, field)
            elif field_type == "ForeignKey":
                if raw_value:
                    import uuid
                    data[field_name] = uuid.UUID(raw_value)
                else:
                    data[field_name] = None
            else:
                data[field_name] = raw_value if raw_value else None
        except (ValueError, TypeError):
            data[field_name] = raw_value

    return data


async def _build_field_info(
    field_name: str,
    model: Type["Model"],
    model_admin: "ModelAdmin",
    form_data: Dict[str, Any],
    request: Request,
    obj: Optional["Model"],
    readonly: set,
) -> Optional[Dict[str, Any]]:
    """Build a single field's render info (shared by add/change forms)."""
    from datetime import datetime

    m2m_fields = model.meta.many_to_many
    is_m2m = field_name in m2m_fields

    if is_m2m:
        field = m2m_fields[field_name]
        field_type = "multiselect"
        nullable = True
        if form_data.get(field_name) is not None:
            value = form_data[field_name]
        elif obj is not None:
            m2m_manager = getattr(obj, field_name)
            related_ids = await m2m_manager.ids()
            value = [str(rid) for rid in related_ids]
        else:
            value = []
    else:
        field = model.meta.get_field(field_name)
        if not field:
            return None

        field_type = model_admin.get_field_type(field_name)
        nullable = getattr(field, "nullable", False)

        if form_data.get(field_name) is not None:
            value = form_data[field_name]
        elif obj is not None:
            value = getattr(obj, field_name, "")
        elif field_type == "checkbox":
            default = getattr(field, "default", None)
            value = default() if callable(default) else default
        else:
            value = ""

        if field_type == "datetime-local" and value:
            if isinstance(value, datetime):
                value = value.strftime("%Y-%m-%dT%H:%M")
            elif isinstance(value, str) and value:
                try:
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    value = dt.strftime("%Y-%m-%dT%H:%M")
                except (ValueError, AttributeError):
                    pass

        if field_type == "checkbox":
            value = value in (True, "true", "True", "1", "on", 1)
        elif not isinstance(value, list):
            value = str(value) if value is not None else ""

    field_info: Dict[str, Any] = {
        "name": field_name,
        "label": field_name.replace("_", " ").title(),
        "type": field_type,
        "value": value,
        "readonly": field_name in readonly,
        "required": not nullable,
        "choices": None,
        "widget_html": None,
    }

    if not is_m2m and field:
        widget = model_admin.get_widget(field_name, field)
        if widget:
            field_info["widget_html"] = widget.render(field_name, value, field)

    if field_type in ("select", "multiselect"):
        field_info["choices"] = await model_admin.get_field_choices(field_name, request)

    return field_info


async def _get_fieldsets_info(
    model: Type["Model"],
    model_admin: "ModelAdmin",
    form_data: Dict[str, Any],
    request: Request,
    obj: Optional["Model"] = None,
) -> List[Dict[str, Any]]:
    """
    Build render info grouped into fieldsets.

    Returns a list of sections: {title, description, classes, fields:[info...]}.
    """
    readonly = set(model_admin.get_readonly_fields(request, obj))
    sections: List[Dict[str, Any]] = []

    for title, opts in model_admin.get_fieldsets(request, obj):
        field_infos = []
        for field_name in opts.get("fields", []):
            info = await _build_field_info(
                field_name, model, model_admin, form_data, request, obj, readonly
            )
            if info is not None:
                field_infos.append(info)
        sections.append(
            {
                "title": title,
                "description": opts.get("description"),
                "classes": opts.get("classes", []),
                "fields": field_infos,
            }
        )
    return sections


# -----------------------------------------------------------------------------
# Login / Logout
# -----------------------------------------------------------------------------

async def admin_login(request: Request, site: "AdminSite" = None) -> HTMLResponse:
    """Admin login page. Route: GET, POST /admin/login/"""
    site = _resolve_site(site)
    settings = _get_settings()
    error = None
    username = ""
    default_next = _url_path(request.url_for(f"{site.name}:index"))
    next_url = _validate_next_url(
        request.query_params.get("next", default_next),
        default=default_next,
    )

    user = getattr(request.state, "user", None)
    if user:
        allowed, _message = await _check_site_permission(site, request)
        if allowed:
            return RedirectResponse(url=next_url, status_code=status.HTTP_302_FOUND)

    if request.method == "POST":
        form_data = await _read_admin_form(request)
        username = form_data.get("username", "")
        password = form_data.get("password", "")
        next_url = _validate_next_url(form_data.get("next", default_next), default=default_next)

        if username and password:
            try:
                from aksara.contrib.auth import authenticate

                user = await authenticate(
                    request.app.db, username=username, password=password
                )
                if user:
                    allowed, _message = await _check_site_permission_for_user(
                        site, request, user
                    )
                    if not allowed:
                        error = (
                            "You don't have permission to access the admin. "
                            "Staff access required."
                        )
                    else:
                        from aksara.contrib.auth import create_session_token

                        token = await create_session_token(request.app.db, user)
                        response = RedirectResponse(
                            url=next_url, status_code=status.HTTP_302_FOUND
                        )
                        response.set_cookie(
                            key="session_token",
                            value=token,
                            httponly=True,
                            secure=settings.cookie_secure,
                            samesite="strict",
                            max_age=60 * 60 * 24 * 7,
                        )
                        return response
                else:
                    error = "Invalid username or password."
            except ImportError:
                error = "Authentication module not configured. Please set up aksara.contrib.auth."
            except Exception:
                logger.exception("Admin login error")
                error = "Login failed. Please try again."
        else:
            error = "Please enter both username and password."

    return _render_admin_template(
        request,
        site,
        "admin/login.html",
        {"error": error, "username": username, "next": next_url},
    )


async def admin_logout(request: Request, site: "AdminSite" = None) -> RedirectResponse:
    """Admin logout - clears session and redirects to login. Route: POST /admin/logout/"""
    site = _resolve_site(site)
    await _read_admin_form(request)

    try:
        token = request.cookies.get("session_token")
        if token and request.app.db:
            from aksara.contrib.auth import invalidate_session_token
            await invalidate_session_token(request.app.db, token)
    except Exception:
        pass  # Session cleanup is best-effort

    response = RedirectResponse(
        url=site.logout_url or str(request.url_for(f"{site.name}:login")),
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
