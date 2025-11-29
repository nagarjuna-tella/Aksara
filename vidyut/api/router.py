"""
Router utilities for registering ViewSets with FastAPI

Provides include_viewset() to wire a ModelViewSet to a FastAPI router.

Usage:
    from fastapi import APIRouter
    from vidyut.api import ModelViewSet, include_viewset

    class UserViewSet(ModelViewSet):
        model = User
        prefix = "/users"
        tags = ["Users"]

    router = APIRouter()
    include_viewset(router, UserViewSet)
    
    # Or with Vidyut app:
    app = Vidyut(...)
    include_viewset(app, UserViewSet)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type, Union
from uuid import UUID

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from vidyut.api.viewsets import ModelViewSet
from vidyut.api.schemas import generate_read_schema
from vidyut.exceptions import (
    UniqueConstraintError,
    ForeignKeyConstraintError,
    DatabaseError,
)


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
        router: FastAPI APIRouter (or Vidyut app)
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
    
    # Get filterable fields for query params
    filter_fields = viewset.get_filter_fields()
    
    # =========================================================================
    # LIST endpoint
    # =========================================================================
    @router.get(
        f"{prefix}/",
        tags=tags,
        summary=f"List {viewset.model.__name__}",
        description=f"Get a paginated list of {viewset.model.__name__} records.",
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
    # RETRIEVE endpoint
    # =========================================================================
    @router.get(
        f"{prefix}/{{pk}}",
        tags=tags,
        summary=f"Get {viewset.model.__name__}",
        description=f"Retrieve a single {viewset.model.__name__} by ID.",
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
    # CREATE endpoint - use add_api_route for dynamic type
    # =========================================================================
    async def create_item(request: Request) -> Dict[str, Any]:
        """Create a new item."""
        try:
            body = await request.json()
            data = CreateSchema(**body)
            return await viewset.create(
                data=data.model_dump(exclude_unset=True),
                request=request,
            )
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors())
        except Exception as e:
            _handle_exception(e)
    
    router.add_api_route(
        f"{prefix}/",
        create_item,
        methods=["POST"],
        tags=tags,
        status_code=201,
        summary=f"Create {viewset.model.__name__}",
        description=f"Create a new {viewset.model.__name__}.",
    )
    
    # =========================================================================
    # UPDATE endpoint - use add_api_route for dynamic type
    # =========================================================================
    async def update_item(pk: str, request: Request) -> Dict[str, Any]:
        """Update an existing item (partial update)."""
        try:
            body = await request.json()
            data = UpdateSchema(**body)
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
    
    router.add_api_route(
        f"{prefix}/{{pk}}",
        update_item,
        methods=["PATCH"],
        tags=tags,
        summary=f"Update {viewset.model.__name__}",
        description=f"Partially update a {viewset.model.__name__}.",
    )
    
    # =========================================================================
    # DELETE endpoint
    # =========================================================================
    @router.delete(
        f"{prefix}/{{pk}}",
        tags=tags,
        summary=f"Delete {viewset.model.__name__}",
        description=f"Delete a {viewset.model.__name__}.",
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
    Map Vidyut exceptions to HTTP responses.
    
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
    
    if isinstance(exc, DatabaseError):
        raise HTTPException(
            status_code=500,
            detail="Database error occurred",
        )
    
    # Re-raise unknown exceptions
    raise exc


__all__ = ["include_viewset"]
