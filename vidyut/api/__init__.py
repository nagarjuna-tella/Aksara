"""
⚡ Vidyut API Layer (v0.3.2)

Auto-generate CRUD REST APIs from Vidyut models.

This module provides:
- ModelViewSet: Base class for auto-generated CRUD endpoints
- ModelSerializer: Django/DRF-style serializer abstraction (v0.3.2)
- @action decorator: Define custom endpoints on ViewSets
- Auto-generated Pydantic schemas from models
- Router utilities for registering viewsets

Usage:
    from vidyut import Model, fields
    from vidyut.api import ModelViewSet, ModelSerializer, include_viewset, action

    class User(Model):
        email = fields.String(unique=True)
        name = fields.String(max_length=100)

    # v0.3.2: Use serializers for validation
    class UserSerializer(ModelSerializer):
        class Meta:
            model = User
            fields = ["id", "email", "name"]
            read_only_fields = ["id"]

    class UserViewSet(ModelViewSet):
        model = User
        prefix = "/users"
        tags = ["Users"]
        create_serializer_class = UserSerializer
        
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
from vidyut.api.serializers import (
    ModelSerializer,
    serialize_instance,
    serialize_many,
    clear_serializer_cache,
)
from vidyut.api.prefetch import (
    prefetch_many_to_many,
    prefetch_foreign_keys,
    prefetch_for_serializer,
)

__all__ = [
    # ViewSet
    "ModelViewSet",
    # Serializer (v0.3.2)
    "ModelSerializer",
    "serialize_instance",
    "serialize_many",
    "clear_serializer_cache",
    # Prefetch utilities (v0.3.9)
    "prefetch_many_to_many",
    "prefetch_foreign_keys",
    "prefetch_for_serializer",
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
