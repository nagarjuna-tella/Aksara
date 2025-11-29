"""
⚡ Vidyut API Layer (v0.3.1)

Auto-generate CRUD REST APIs from Vidyut models.

This module provides:
- ModelViewSet: Base class for auto-generated CRUD endpoints
- @action decorator: Define custom endpoints on ViewSets
- Auto-generated Pydantic schemas from models
- Router utilities for registering viewsets

Usage:
    from vidyut import Model, fields
    from vidyut.api import ModelViewSet, include_viewset, action

    class User(Model):
        email = fields.String(unique=True)
        name = fields.String(max_length=100)

    class UserViewSet(ModelViewSet):
        model = User
        prefix = "/users"
        tags = ["Users"]
        
        @action(detail=True, methods=["post"], summary="Deactivate user")
        async def deactivate(self, pk: UUID, request: Request):
            ...

    # Register with FastAPI router
    router = APIRouter()
    include_viewset(router, UserViewSet)
"""

from vidyut.api.schemas import (
    generate_create_schema,
    generate_update_schema,
    generate_read_schema,
    get_schemas_for_model,
    clear_schema_cache,
)
from vidyut.api.viewsets import ModelViewSet
from vidyut.api.router import include_viewset
from vidyut.api.actions import action

__all__ = [
    # ViewSet
    "ModelViewSet",
    # Action decorator
    "action",
    # Router
    "include_viewset",
    # Schema generation
    "generate_create_schema",
    "generate_update_schema",
    "generate_read_schema",
    "get_schemas_for_model",
    "clear_schema_cache",
]
