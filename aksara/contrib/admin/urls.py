"""
Admin URL Router

Defines routes for the admin interface.
"""

import os
from fastapi import APIRouter
from starlette.staticfiles import StaticFiles

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

# Create the admin router
router = APIRouter(tags=["Admin"])

# Mount static files for admin
admin_dir = os.path.dirname(__file__)
static_dir = os.path.join(admin_dir, "static")

if os.path.exists(static_dir):
    router.mount(
        "/static/admin",
        StaticFiles(directory=static_dir),
        name="admin_static"
    )

# Auth routes (must be before the catch-all routes)
router.add_api_route(
    "/login/",
    admin_login,
    methods=["GET", "POST"],
    name="admin:login",
)

router.add_api_route(
    "/logout/",
    admin_logout,
    methods=["GET", "POST"],
    name="admin:logout",
)

# Index routes
router.add_api_route(
    "/",
    admin_index,
    methods=["GET"],
    name="admin:index",
)

router.add_api_route(
    "/{app_label}/",
    app_index,
    methods=["GET"],
    name="admin:app_index",
)

# Model CRUD routes
router.add_api_route(
    "/{app_label}/{model_name}/",
    model_list,
    methods=["GET"],
    name="admin:model_list",
)

router.add_api_route(
    "/{app_label}/{model_name}/add/",
    model_add,
    methods=["GET", "POST"],
    name="admin:model_add",
)

router.add_api_route(
    "/{app_label}/{model_name}/{pk}/change/",
    model_change,
    methods=["GET", "POST"],
    name="admin:model_change",
)

router.add_api_route(
    "/{app_label}/{model_name}/{pk}/delete/",
    model_delete,
    methods=["POST"],
    name="admin:model_delete",
)
