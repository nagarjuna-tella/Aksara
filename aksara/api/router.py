"""
Router utilities for registering ViewSets with FastAPI

Provides include_viewset() to wire a ModelViewSet to a FastAPI router.

Usage:
    from fastapi import APIRouter
    from aksara.api import ModelViewSet, include_viewset, action

    class UserViewSet(ModelViewSet):
        model = User
        prefix = "/users"
        tags = ["Users"]
        
        @action(detail=True, methods=["post"], summary="Deactivate user")
        async def deactivate(self, pk: UUID, request: Request):
            ...

    router = APIRouter()
    include_viewset(router, UserViewSet)
    
    # Or with Aksara app:
    app = Aksara(...)
    include_viewset(app, UserViewSet)
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List, Optional, Type, Union
from uuid import UUID

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field as PydanticField, ValidationError, create_model

from aksara.api.viewsets import ModelViewSet
from aksara.api.schemas import generate_read_schema
from aksara.api.actions import (
    get_action_metadata,
    is_action,
    extract_docstring_summary,
    extract_docstring_description,
)
from aksara.exceptions import (
    ValidationError as AksaraValidationError,
    UniqueConstraintError,
    ForeignKeyConstraintError,
    DatabaseError,
)


# Cache of paginated response wrappers, keyed by the Read schema class so
# we don't recreate the wrapper Pydantic model on every viewset registration.
_paginated_schema_cache: Dict[Type[BaseModel], Type[BaseModel]] = {}
# Cache for the delete-response wrapper, keyed by model name.
_delete_schema_cache: Dict[str, Type[BaseModel]] = {}


def _build_paginated_schema(read_schema: Type[BaseModel]) -> Type[BaseModel]:
    """
    Construct (and cache) a Pydantic wrapper that documents the paginated
    list response shape `{count, limit, offset, results: [ReadSchema]}` so
    FastAPI emits a concrete OpenAPI schema instead of a generic object.
    """
    cached = _paginated_schema_cache.get(read_schema)
    if cached is not None:
        return cached
    wrapper = create_model(
        f"Paginated{read_schema.__name__}",
        count=(int, PydanticField(default=0)),
        limit=(Optional[int], PydanticField(default=None)),
        offset=(Optional[int], PydanticField(default=None)),
        results=(List[read_schema], PydanticField(default_factory=list)),
    )
    _paginated_schema_cache[read_schema] = wrapper
    return wrapper


def _build_delete_schema(model_name: str) -> Type[BaseModel]:
    cached = _delete_schema_cache.get(model_name)
    if cached is not None:
        return cached
    wrapper = create_model(
        f"{model_name}DeleteResponse",
        deleted=(bool, PydanticField(default=True)),
        id=(str, PydanticField(...)),
    )
    _delete_schema_cache[model_name] = wrapper
    return wrapper


def _create_create_endpoint(viewset: ModelViewSet, CreateSchema: Type) -> Callable:
    """
    Create a properly typed create endpoint function.
    
    FastAPI inspects the function signature to generate OpenAPI docs,
    so we need to create a function with the schema as a typed parameter.
    """
    async def create_item(request: Request, data: CreateSchema) -> Dict[str, Any]:
        """Create a new item."""
        try:
            # Check if viewset uses serializer for create
            if viewset.uses_serializer('create'):
                # Serializer handles validation internally
                return await viewset.create(data=data.model_dump(), request=request)
            else:
                return await viewset.create(
                    data=data.model_dump(exclude_unset=True),
                    request=request,
                )
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors())
        except Exception as e:
            _handle_exception(e)
    
    # Fix the type annotation for FastAPI to pick up
    create_item.__annotations__['data'] = CreateSchema
    return create_item


def _create_update_endpoint(viewset: ModelViewSet, UpdateSchema: Type) -> Callable:
    """
    Create a properly typed update endpoint function.
    
    FastAPI inspects the function signature to generate OpenAPI docs,
    so we need to create a function with the schema as a typed parameter.
    """
    async def update_item(pk: str, request: Request, data: UpdateSchema) -> Dict[str, Any]:
        """Update an existing item (partial update)."""
        try:
            # Check if viewset uses serializer for update
            if viewset.uses_serializer('update'):
                # Serializer handles validation internally
                return await viewset.update(pk=pk, data=data.model_dump(exclude_unset=True), request=request)
            else:
                return await viewset.update(
                    pk=pk,
                    data=data.model_dump(exclude_unset=True),
                    request=request,
                )
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors())
        except HTTPException:
            raise
        except Exception as e:
            _handle_exception(e)
    
    # Fix the type annotation for FastAPI to pick up
    update_item.__annotations__['data'] = UpdateSchema
    return update_item


def include_viewset(
    router: APIRouter,
    viewset_cls: Type[ModelViewSet],
) -> None:
    """
    Register a ModelViewSet with a FastAPI router.
    
    Creates routes for all CRUD operations:
        - GET {prefix}/ → list
        - GET {prefix}/{pk} → retrieve
        - POST {prefix}/ → create
        - PATCH {prefix}/{pk} → update
        - DELETE {prefix}/{pk} → delete
    
    Args:
        router: FastAPI APIRouter (or Aksara app)
        viewset_cls: ModelViewSet subclass
    """
    # Instantiate the viewset
    viewset = viewset_cls()
    
    prefix = viewset.prefix.rstrip("/")
    tags = viewset.tags
    
    # Get schemas
    CreateSchema = viewset.create_schema
    UpdateSchema = viewset.update_schema
    ReadSchema = viewset.read_schema
    PaginatedReadSchema = _build_paginated_schema(ReadSchema)
    DeleteResponseSchema = _build_delete_schema(viewset.model.__name__)

    # Get filterable fields for query params
    filter_fields = viewset.get_filter_fields()

    # =========================================================================
    # LIST endpoint (no {pk})
    # =========================================================================
    # Publish the paginated Read schema as the documented response so the
    # OpenAPI spec describes a concrete model instead of a generic dict.
    @router.get(
        f"{prefix}/",
        tags=tags,
        summary=f"List {viewset.model.__name__}",
        description=f"Get a paginated list of {viewset.model.__name__} records.",
        response_model=PaginatedReadSchema,
    )
    async def list_items(
        request: Request,
        limit: int = Query(
            default=viewset.default_limit,
            ge=1,
            le=viewset.max_limit,
            description="Maximum number of items to return",
        ),
        offset: int = Query(
            default=0,
            ge=0,
            description="Number of items to skip",
        ),
    ) -> Dict[str, Any]:
        """List all items with pagination."""
        # Extract filter params from query string
        filters = _extract_filters(request, filter_fields)
        
        try:
            return await viewset.list(
                request=request,
                limit=limit,
                offset=offset,
                **filters,
            )
        except Exception as e:
            return _handle_exception(e)
    
    # =========================================================================
    # CREATE endpoint (no {pk})
    # =========================================================================
    # Dynamically create a properly typed endpoint function
    # FastAPI needs the schema type in the signature for OpenAPI docs
    create_endpoint = _create_create_endpoint(viewset, CreateSchema)
    
    router.add_api_route(
        f"{prefix}/",
        create_endpoint,
        methods=["POST"],
        tags=tags,
        status_code=201,
        summary=f"Create {viewset.model.__name__}",
        description=f"Create a new {viewset.model.__name__}.",
        response_model=ReadSchema,
    )

    # =========================================================================
    # STREAM endpoint (no {pk}) - MUST come before {pk} routes!
    # =========================================================================
    if viewset.stream_enabled:
        @router.get(
            f"{prefix}/stream",
            tags=tags,
            summary=f"Stream {viewset.model.__name__}",
            description=f"Subscribe to real-time {viewset.model.__name__} lifecycle events via SSE.",
        )
        async def stream_items(request: Request):
            """Stream model lifecycle events as server-sent events."""
            try:
                return await viewset.stream(request=request)
            except HTTPException:
                raise
            except Exception as e:
                return _handle_exception(e)
    
    # =========================================================================
    # COLLECTION @action endpoints (no {pk}) - MUST come before {pk} routes!
    # =========================================================================
    _register_collection_actions(router, viewset, prefix, tags)
    
    # =========================================================================
    # RETRIEVE endpoint (with {pk})
    # =========================================================================
    @router.get(
        f"{prefix}/{{pk}}",
        tags=tags,
        summary=f"Get {viewset.model.__name__}",
        description=f"Retrieve a single {viewset.model.__name__} by ID.",
        response_model=ReadSchema,
    )
    async def retrieve_item(
        pk: str,
        request: Request,
    ) -> Dict[str, Any]:
        """Retrieve a single item by ID."""
        try:
            return await viewset.retrieve(pk=pk, request=request)
        except HTTPException:
            raise
        except Exception as e:
            return _handle_exception(e)
    
    # =========================================================================
    # UPDATE endpoint (with {pk})
    # =========================================================================
    # Dynamically create a properly typed endpoint function
    update_endpoint = _create_update_endpoint(viewset, UpdateSchema)
    
    router.add_api_route(
        f"{prefix}/{{pk}}",
        update_endpoint,
        methods=["PATCH"],
        tags=tags,
        summary=f"Update {viewset.model.__name__}",
        description=f"Partially update a {viewset.model.__name__}.",
        response_model=ReadSchema,
    )
    
    # =========================================================================
    # DELETE endpoint (with {pk})
    # =========================================================================
    @router.delete(
        f"{prefix}/{{pk}}",
        tags=tags,
        summary=f"Delete {viewset.model.__name__}",
        description=f"Delete a {viewset.model.__name__}.",
        response_model=DeleteResponseSchema,
    )
    async def delete_item(
        pk: str,
        request: Request,
    ) -> Dict[str, Any]:
        """Delete an item."""
        try:
            return await viewset.delete(pk=pk, request=request)
        except HTTPException:
            raise
        except Exception as e:
            _handle_exception(e)
    
    # =========================================================================
    # DETAIL @action endpoints (with {pk})
    # =========================================================================
    _register_detail_actions(router, viewset, prefix, tags)


def _register_collection_actions(
    router: APIRouter,
    viewset: ModelViewSet,
    prefix: str,
    tags: List[str],
) -> None:
    """
    Register collection-level @action methods (detail=False).
    
    These routes don't include {pk} and must be registered BEFORE
    the retrieve endpoint to avoid path conflicts.
    
    Args:
        router: FastAPI router to register routes on
        viewset: Instantiated viewset to scan for actions
        prefix: URL prefix for the viewset
        tags: OpenAPI tags for the routes
    """
    _register_actions_by_detail(router, viewset, prefix, tags, detail=False)


def _register_detail_actions(
    router: APIRouter,
    viewset: ModelViewSet,
    prefix: str,
    tags: List[str],
) -> None:
    """
    Register detail-level @action methods (detail=True).
    
    These routes include {pk} and are registered after CRUD routes.
    
    Args:
        router: FastAPI router to register routes on
        viewset: Instantiated viewset to scan for actions
        prefix: URL prefix for the viewset
        tags: OpenAPI tags for the routes
    """
    _register_actions_by_detail(router, viewset, prefix, tags, detail=True)


def _register_actions_by_detail(
    router: APIRouter,
    viewset: ModelViewSet,
    prefix: str,
    tags: List[str],
    detail: bool,
) -> None:
    """
    Scan viewset for @action decorated methods and register them as routes.
    
    Args:
        router: FastAPI router to register routes on
        viewset: Instantiated viewset to scan for actions
        prefix: URL prefix for the viewset
        tags: OpenAPI tags for the routes
        detail: If True, register detail actions. If False, register collection actions.
    """
    # Scan all attributes of the viewset instance
    for attr_name in dir(viewset):
        # Skip private/magic attributes
        if attr_name.startswith("_"):
            continue
        
        try:
            method = getattr(viewset, attr_name)
        except AttributeError:
            continue
        
        # Check if it's a callable with action metadata
        if not callable(method):
            continue
        
        meta = get_action_metadata(method)
        if meta is None:
            continue
        
        # Only process actions matching the requested detail type
        if meta["detail"] != detail:
            continue
        
        # Build the route path
        action_path = meta["path"]
        if meta["detail"]:
            # Detail action: /prefix/{pk}/action_path
            full_path = f"{prefix}/{{pk}}/{action_path}"
        else:
            # Collection action: /prefix/action_path
            full_path = f"{prefix}/{action_path}"
        
        # Determine summary and description
        summary = meta["summary"]
        if summary is None:
            summary = extract_docstring_summary(method)
        
        description = meta["description"]
        if description is None:
            description = extract_docstring_description(method)
        
        # Register the route
        # Use the bound method directly so FastAPI can inspect its signature
        router.add_api_route(
            path=full_path,
            endpoint=method,
            methods=meta["methods"],
            tags=tags,
            name=meta["name"],
            summary=summary,
            description=description,
        )


def _extract_filters(request: Request, allowed_fields: List[str]) -> Dict[str, Any]:
    """
    Extract filter parameters from request query string.
    
    Supports both exact matches and lookups:
        - ?email=test@example.com → exact match
        - ?name__icontains=john → case-insensitive contains
        - ?age__gte=18 → greater than or equal
    
    Args:
        request: FastAPI request
        allowed_fields: List of field names that can be filtered
        
    Returns:
        Dictionary of filter conditions
    """
    filters = {}
    
    for key, value in request.query_params.items():
        # Skip pagination params
        if key in ("limit", "offset"):
            continue
        
        # Check if the base field is allowed
        base_field = key.split("__")[0]
        if base_field in allowed_fields:
            filters[key] = value
    
    return filters


def _handle_exception(exc: Exception) -> None:
    """
    Map Aksara exceptions to HTTP responses.
    
    Exception → HTTP Code:
        UniqueConstraintError → 409
        ForeignKeyConstraintError → 400
        DatabaseError → 500
    """
    if isinstance(exc, UniqueConstraintError):
        field_info = f" on field '{exc.field_name}'" if exc.field_name else ""
        raise HTTPException(
            status_code=409,
            detail=f"Unique constraint violated{field_info}",
        )
    
    if isinstance(exc, ForeignKeyConstraintError):
        raise HTTPException(
            status_code=400,
            detail=f"Foreign key constraint violated: {exc.message}",
        )

    if isinstance(exc, AksaraValidationError):
        detail = exc.errors or {exc.field_name or "body": exc.message}
        raise HTTPException(
            status_code=422,
            detail={"code": "validation_error", "errors": detail},
        )

    if isinstance(exc, DatabaseError):
        raise HTTPException(
            status_code=500,
            detail="Database error occurred",
        )
    
    # Re-raise unknown exceptions
    raise exc


# =============================================================================
# ViewSet Auto-Registration Helpers (v0.3.14)
# =============================================================================

def discover_viewsets(module) -> List[Type[ModelViewSet]]:
    """
    Discover all ModelViewSet subclasses in a module.
    
    Scans the module for classes that are subclasses of ModelViewSet.
    Excludes the base ModelViewSet class itself.
    
    Args:
        module: Python module to scan
        
    Returns:
        List of ModelViewSet subclass types found in the module
    """
    viewsets: List[Type[ModelViewSet]] = []
    
    for attr_name in dir(module):
        # Skip private attributes
        if attr_name.startswith("_"):
            continue
        
        try:
            attr = getattr(module, attr_name)
        except AttributeError:
            continue
        
        # Check if it's a ModelViewSet subclass
        try:
            if (
                isinstance(attr, type)
                and issubclass(attr, ModelViewSet)
                and attr is not ModelViewSet
            ):
                viewsets.append(attr)
        except TypeError:
            # issubclass raises TypeError for non-class types
            continue
    
    return viewsets


def include_app_viewsets(
    app: Union[APIRouter, "Aksara"],
    app_label: str,
    module_name: str = "api",
) -> List[Type[ModelViewSet]]:
    """
    Auto-import and register all ModelViewSet subclasses from an app.
    
    Imports `<app_label>.<module_name>` (default: `<app>.api`) and registers
    all ModelViewSet subclasses found there with the given app/router.
    
    v0.3.14: Developer Delight Pack 2
    
    Args:
        app: FastAPI router or Aksara app to register viewsets with
        app_label: The app label (e.g., "blog", "users")
        module_name: Module name to import (default: "api"). Can also be
                    "views" for Django-style organization.
    
    Returns:
        List of ViewSet classes that were registered
    
    Example:
        from aksara import Aksara
        from aksara.api import include_app_viewsets
        
        app = Aksara(database_url="...")
        include_app_viewsets(app, "blog")           # imports blog.api
        include_app_viewsets(app, "users", "views") # imports users.views
    """
    from importlib import import_module
    
    registered = []
    
    # Try to import the module
    try:
        mod = import_module(f"{app_label}.{module_name}")
    except ModuleNotFoundError:
        # App doesn't have this module, silently skip
        return registered
    except ImportError as e:
        # Actual import error - warn but continue
        import warnings
        warnings.warn(
            f"Error importing viewsets from '{app_label}.{module_name}': {e}",
            ImportWarning,
            stacklevel=2,
        )
        return registered
    
    # Discover and register viewsets
    viewsets = discover_viewsets(mod)
    
    for vs_class in viewsets:
        include_viewset(app, vs_class)
        registered.append(vs_class)
    
    return registered


def include_all_app_viewsets(
    app: Union[APIRouter, "Aksara"],
    module_name: str = "api",
) -> Dict[str, List[Type[ModelViewSet]]]:
    """
    Auto-import and register ViewSets from all configured apps.
    
    Loops through settings.apps and calls include_app_viewsets for each.
    
    v0.3.14: Developer Delight Pack 2
    
    Args:
        app: FastAPI router or Aksara app to register viewsets with
        module_name: Module name to import from each app (default: "api")
    
    Returns:
        Dict mapping app_label to list of registered ViewSet classes
    
    Example:
        from aksara import Aksara
        from aksara.api import include_all_app_viewsets
        
        app = Aksara(database_url="...")
        
        # Register all viewsets from all apps
        registered = include_all_app_viewsets(app)
        # {'blog': [PostViewSet, CommentViewSet], 'users': [UserViewSet]}
    """
    from aksara.conf import settings
    
    result: Dict[str, List[Type[ModelViewSet]]] = {}
    
    for app_label in settings.apps:
        viewsets = include_app_viewsets(app, app_label, module_name)
        if viewsets:
            result[app_label] = viewsets
    
    return result


__all__ = [
    "include_viewset",
    "discover_viewsets",
    "include_app_viewsets",
    "include_all_app_viewsets",
]
