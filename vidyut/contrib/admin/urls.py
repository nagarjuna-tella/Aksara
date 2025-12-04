"""
Admin URL Router

Defines routes for the admin interface.
"""

from fastapi import APIRouter

from vidyut.contrib.admin.views import (
    admin_index,
    app_index,
    model_list,
    model_add,
    model_change,
    model_delete,
)

# Create the admin router
router = APIRouter(tags=["Admin"])

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
