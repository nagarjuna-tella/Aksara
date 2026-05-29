"""
Admin URL Router

Builds the route table for an admin site. Each site gets its own router whose
route names are namespaced by ``site.name`` (e.g. ``admin:index``), so multiple
admin sites can be mounted on one app without route-name collisions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request

from aksara.contrib.admin.views import (
    admin_index,
    admin_login,
    admin_logout,
    app_index,
    model_list,
    model_add,
    model_change,
    model_delete,
)

if TYPE_CHECKING:
    from aksara.contrib.admin.site import AdminSite


def _normalise_cookie_path(prefix: str) -> str:
    """Return a stable cookie path for an admin router prefix."""
    path = (prefix or "/admin").strip() or "/admin"
    if not path.startswith("/"):
        path = f"/{path}"
    return path.rstrip("/") or "/"


def build_admin_router(site: "AdminSite", prefix: str = "/admin") -> APIRouter:
    """Create an APIRouter bound to ``site`` with namespaced route names."""
    router = APIRouter(tags=["Admin"])
    ns = site.name
    csrf_cookie_path = _normalise_cookie_path(prefix)

    def bind_request(request: Request) -> None:
        request.state.admin_csrf_cookie_path = csrf_cookie_path

    async def login_view(request: Request):
        bind_request(request)
        return await admin_login(request, site)

    async def logout_view(request: Request):
        bind_request(request)
        return await admin_logout(request, site)

    async def index_view(request: Request):
        bind_request(request)
        return await admin_index(request, site)

    async def app_index_view(request: Request, app_label: str):
        bind_request(request)
        return await app_index(request, app_label, site)

    async def model_list_view(request: Request, app_label: str, model_name: str):
        bind_request(request)
        return await model_list(request, app_label, model_name, site)

    async def model_add_view(request: Request, app_label: str, model_name: str):
        bind_request(request)
        return await model_add(request, app_label, model_name, site)

    async def model_change_view(
        request: Request, app_label: str, model_name: str, pk: str
    ):
        bind_request(request)
        return await model_change(request, app_label, model_name, pk, site)

    async def model_delete_view(
        request: Request, app_label: str, model_name: str, pk: str
    ):
        bind_request(request)
        return await model_delete(request, app_label, model_name, pk, site)

    # Auth routes (must be before the catch-all model routes)
    router.add_api_route(
        "/login/", login_view, methods=["GET", "POST"], name=f"{ns}:login"
    )
    router.add_api_route(
        "/logout/", logout_view, methods=["POST"], name=f"{ns}:logout"
    )

    # Index routes
    router.add_api_route("/", index_view, methods=["GET"], name=f"{ns}:index")
    router.add_api_route(
        "/{app_label}/", app_index_view, methods=["GET"], name=f"{ns}:app_index"
    )

    # Model CRUD routes
    router.add_api_route(
        "/{app_label}/{model_name}/",
        model_list_view,
        methods=["GET", "POST"],
        name=f"{ns}:model_list",
    )
    router.add_api_route(
        "/{app_label}/{model_name}/add/",
        model_add_view,
        methods=["GET", "POST"],
        name=f"{ns}:model_add",
    )
    router.add_api_route(
        "/{app_label}/{model_name}/{pk}/change/",
        model_change_view,
        methods=["GET", "POST"],
        name=f"{ns}:model_change",
    )
    router.add_api_route(
        "/{app_label}/{model_name}/{pk}/delete/",
        model_delete_view,
        methods=["POST"],
        name=f"{ns}:model_delete",
    )

    return router
