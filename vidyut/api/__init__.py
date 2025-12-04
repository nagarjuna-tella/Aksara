"""
⚡ Vidyut API Layer (v0.3.10)

Auto-generate CRUD REST APIs from Vidyut models.

This module provides:
- ModelViewSet: Base class for auto-generated CRUD endpoints
- ModelSerializer: Django/DRF-style serializer abstraction (v0.3.2)
- @action decorator: Define custom endpoints on ViewSets
- Auto-generated Pydantic schemas from models
- Router utilities for registering viewsets
- Permission support on ViewSets and actions (v0.3.10)

Usage:
    from vidyut import Model, fields
    from vidyut.api import ModelViewSet, ModelSerializer, include_viewset, action
    from vidyut.permissions import IsAuthenticated, IsAdminUser

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
        permission_classes = [IsAuthenticated]  # v0.3.10
        create_serializer_class = UserSerializer
        
        @action(
            detail=True, 
            methods=["post"], 
            summary="Deactivate user",
            permission_classes=[IsAdminUser],  # v0.3.10
        )
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
from vidyut.api.router import (
    include_viewset,
    discover_viewsets,
    include_app_viewsets,
    include_all_app_viewsets,
)
from vidyut.api.actions import (
    action,
    get_action_metadata,
    is_action,
    get_action_permissions,
    is_action_ai_exposed,
)
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
    # Action decorator & utilities (v0.3.10)
    "action",
    "get_action_metadata",
    "is_action",
    "get_action_permissions",
    "is_action_ai_exposed",
    # Router
    "include_viewset",
    # ViewSet Auto-Registration (v0.3.14)
    "discover_viewsets",
    "include_app_viewsets",
    "include_all_app_viewsets",
    # Schema generation
    "generate_create_schema",
    "generate_update_schema",
    "generate_read_schema",
    "get_schemas_for_model",
    "clear_schema_cache",
]
