"""
ModelViewSet - Auto-generated CRUD endpoints

Provides Django-like ViewSet functionality for Vidyut models.
Each ViewSet generates list, retrieve, create, update, delete endpoints.

Usage:
    class UserViewSet(ModelViewSet):
        model = User
        prefix = "/users"
        tags = ["Users"]
        
    # Customize behavior by overriding methods:
    class UserViewSet(ModelViewSet):
        model = User
        prefix = "/users"
        
        async def list(self, request, limit, offset, **filters):
            # Custom list logic
            queryset = self.model.objects.filter(is_active=True)
            return await self._paginate(queryset, limit, offset)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type, TYPE_CHECKING

from fastapi import Request, HTTPException

from vidyut.model.base import Model
from vidyut.manager import DoesNotExist
from vidyut.api.schemas import (
    generate_create_schema,
    generate_update_schema,
    generate_read_schema,
    model_to_dict,
)

if TYPE_CHECKING:
    from vidyut.manager import QuerySet


class ModelViewSet:
    """
    Base ViewSet for auto-generating CRUD endpoints.
    
    Class Attributes:
        model: The Vidyut Model class
        prefix: URL prefix (e.g., "/users")
        tags: FastAPI tags for documentation
        lookup_field: Field used for single-item lookups (default: "id")
    
    Generated Endpoints:
        - GET {prefix}/ → list
        - GET {prefix}/{pk} → retrieve
        - POST {prefix}/ → create
        - PATCH {prefix}/{pk} → update
        - DELETE {prefix}/{pk} → delete
    
    Override Methods:
        Override list(), retrieve(), create(), update(), delete()
        for custom business logic.
    """
    
    model: Type[Model] = None  # type: ignore
    prefix: str = ""
    tags: Optional[List[str]] = None
    lookup_field: str = "id"
    
    # Pagination defaults
    default_limit: int = 20
    max_limit: int = 100
    
    def __init__(self):
        """Initialize the ViewSet."""
        if self.model is None:
            raise ValueError(f"{self.__class__.__name__} must define 'model' attribute")
        
        if not self.prefix:
            # Auto-generate prefix from model name
            self.prefix = f"/{self.model.__tablename__}"
        
        if self.tags is None:
            self.tags = [self.model.__name__]
        
        # Generate schemas
        self._create_schema = generate_create_schema(self.model)
        self._update_schema = generate_update_schema(self.model)
        self._read_schema = generate_read_schema(self.model)
    
    @property
    def create_schema(self) -> Type:
        """Get the Pydantic Create schema."""
        return self._create_schema
    
    @property
    def update_schema(self) -> Type:
        """Get the Pydantic Update schema."""
        return self._update_schema
    
    @property
    def read_schema(self) -> Type:
        """Get the Pydantic Read schema."""
        return self._read_schema
    
    # =========================================================================
    # CRUD Operations (Override these for custom logic)
    # =========================================================================
    
    async def list(
        self,
        request: Request,
        limit: int = 20,
        offset: int = 0,
        **filters: Any,
    ) -> Dict[str, Any]:
        """
        List all items with pagination.
        
        Args:
            request: FastAPI Request object
            limit: Maximum number of items to return
            offset: Number of items to skip
            **filters: Query parameter filters (field=value or field__lookup=value)
            
        Returns:
            Paginated response with count and results
        """
        queryset = self.get_queryset(**filters)
        return await self._paginate(queryset, limit, offset)
    
    async def retrieve(
        self,
        pk: str,
        request: Request,
    ) -> Dict[str, Any]:
        """
        Retrieve a single item by primary key.
        
        Args:
            pk: Primary key value
            request: FastAPI Request object
            
        Returns:
            Item data
            
        Raises:
            HTTPException: 404 if not found, 400 if invalid UUID
        """
        try:
            instance = await self.model.objects.get(**{self.lookup_field: pk})
            return self._serialize(instance)
        except DoesNotExist:
            raise HTTPException(
                status_code=404,
                detail=f"{self.model.__name__} not found"
            )
        except ValueError as e:
            # Invalid UUID format
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {self.lookup_field} format: {pk}"
            )
    
    async def create(
        self,
        data: Dict[str, Any],
        request: Request,
    ) -> Dict[str, Any]:
        """
        Create a new item.
        
        Args:
            data: Validated data from Create schema
            request: FastAPI Request object
            
        Returns:
            Created item data
        """
        instance = await self.model.objects.create(**data)
        return self._serialize(instance)
    
    async def update(
        self,
        pk: str,
        data: Dict[str, Any],
        request: Request,
    ) -> Dict[str, Any]:
        """
        Update an existing item (partial update).
        
        Args:
            pk: Primary key value
            data: Validated data from Update schema (only non-None fields)
            request: FastAPI Request object
            
        Returns:
            Updated item data
            
        Raises:
            HTTPException: 404 if not found, 400 if invalid UUID
        """
        try:
            instance = await self.model.objects.get(**{self.lookup_field: pk})
        except DoesNotExist:
            raise HTTPException(
                status_code=404,
                detail=f"{self.model.__name__} not found"
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {self.lookup_field} format: {pk}"
            )
        
        # Apply updates (only non-None values)
        for key, value in data.items():
            if value is not None:
                setattr(instance, key, value)
        
        await instance.save()
        return self._serialize(instance)
    
    async def delete(
        self,
        pk: str,
        request: Request,
    ) -> Dict[str, Any]:
        """
        Delete an item.
        
        Args:
            pk: Primary key value
            request: FastAPI Request object
            
        Returns:
            Deletion confirmation
            
        Raises:
            HTTPException: 404 if not found, 400 if invalid UUID
        """
        try:
            instance = await self.model.objects.get(**{self.lookup_field: pk})
        except DoesNotExist:
            raise HTTPException(
                status_code=404,
                detail=f"{self.model.__name__} not found"
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {self.lookup_field} format: {pk}"
            )
        
        await instance.delete()
        return {"deleted": True, "id": pk}
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def get_queryset(self, **filters: Any) -> "QuerySet":
        """
        Get the base queryset for list operations.
        
        Override this to customize filtering logic.
        
        Args:
            **filters: Filter parameters from query string
            
        Returns:
            QuerySet instance
        """
        # Remove None values from filters
        valid_filters = {k: v for k, v in filters.items() if v is not None}
        
        if valid_filters:
            return self.model.objects.filter(**valid_filters)
        return self.model.objects.filter()
    
    async def _paginate(
        self,
        queryset: "QuerySet",
        limit: int,
        offset: int,
    ) -> Dict[str, Any]:
        """
        Apply pagination to a queryset.
        
        Args:
            queryset: The queryset to paginate
            limit: Maximum items to return
            offset: Items to skip
            
        Returns:
            Dict with count and results
        """
        # Enforce max limit
        limit = min(limit, self.max_limit)
        
        # Get total count
        total = await queryset.count()
        
        # Get paginated results
        # Build the query with LIMIT and OFFSET
        results = await self._fetch_with_pagination(queryset, limit, offset)
        
        return {
            "count": total,
            "limit": limit,
            "offset": offset,
            "results": [self._serialize(item) for item in results],
        }
    
    async def _fetch_with_pagination(
        self,
        queryset: "QuerySet",
        limit: int,
        offset: int,
    ) -> List[Model]:
        """
        Fetch results with pagination applied.
        
        This is a workaround since QuerySet doesn't have limit/offset yet.
        """
        from vidyut.db import Database
        
        db = Database.get_instance()
        
        where_clause, values = queryset._build_where_clause()
        
        # Add LIMIT and OFFSET
        param_idx = len(values) + 1
        query = f"""
            SELECT * FROM {self.model.__tablename__}
            {where_clause}
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        values.extend([limit, offset])
        
        records = await db.fetch(query, *values)
        return [self.model._from_record(record) for record in records]
    
    def _serialize(self, instance: Model) -> Dict[str, Any]:
        """
        Serialize a model instance to a dictionary.
        
        Args:
            instance: Model instance
            
        Returns:
            Dictionary suitable for JSON response
        """
        return model_to_dict(instance)
    
    def get_filter_fields(self) -> List[str]:
        """
        Get list of fields that can be filtered on.
        
        Override to restrict filterable fields.
        
        Returns:
            List of field names
        """
        return list(self.model._fields.keys())


__all__ = ["ModelViewSet"]
