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
    
    # v0.3.2: Use serializers for validation and serialization:
    class UserViewSet(ModelViewSet):
        model = User
        prefix = "/users"
        create_serializer_class = UserCreateSerializer
        retrieve_serializer_class = UserDetailSerializer
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
    from vidyut.api.serializers import ModelSerializer


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
    
    v0.3.2 Serializer Attributes:
        - list_serializer_class: Serializer for list responses
        - retrieve_serializer_class: Serializer for retrieve responses
        - create_serializer_class: Serializer for create input/output
        - update_serializer_class: Serializer for update input/output
    
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
    
    # v0.3.2: Serializer classes (optional, takes precedence over schemas)
    list_serializer_class: Optional[Type["ModelSerializer"]] = None
    retrieve_serializer_class: Optional[Type["ModelSerializer"]] = None
    create_serializer_class: Optional[Type["ModelSerializer"]] = None
    update_serializer_class: Optional[Type["ModelSerializer"]] = None
    
    # v0.3: Schema classes (optional, fallback if no serializer)
    list_schema_class: Optional[Type] = None
    read_schema_class: Optional[Type] = None
    create_schema_class: Optional[Type] = None
    update_schema_class: Optional[Type] = None
    
    def __init__(self):
        """Initialize the ViewSet."""
        if self.model is None:
            raise ValueError(f"{self.__class__.__name__} must define 'model' attribute")
        
        if not self.prefix:
            # Auto-generate prefix from model name
            self.prefix = f"/{self.model.__tablename__}"
        
        if self.tags is None:
            self.tags = [self.model.__name__]
        
        # Generate schemas (used as fallback if no serializers defined)
        self._create_schema = self.create_schema_class or generate_create_schema(self.model)
        self._update_schema = self.update_schema_class or generate_update_schema(self.model)
        self._read_schema = self.read_schema_class or generate_read_schema(self.model)
    
    # =========================================================================
    # v0.3.6: OpenAPI Tag Support
    # =========================================================================
    
    @classmethod
    def get_tags(cls) -> List[str]:
        """
        Get the OpenAPI tags for this ViewSet.
        
        If tags are explicitly set, returns those.
        Otherwise, derives tags from the model name.
        
        Returns:
            List of tag strings for OpenAPI documentation.
        """
        if cls.tags is not None:
            return cls.tags
        
        if cls.model is not None:
            return [cls.model.__name__]
        
        return [cls.__name__.replace("ViewSet", "")]
    
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
    # v0.3.2: Serializer/Schema Resolution
    # =========================================================================
    
    def get_serializer_class(self, action: str) -> Optional[Type["ModelSerializer"]]:
        """
        Get the serializer class for a given action.
        
        Args:
            action: One of 'list', 'retrieve', 'create', 'update'
            
        Returns:
            Serializer class or None if not defined
        """
        mapping = {
            'list': self.list_serializer_class,
            'retrieve': self.retrieve_serializer_class,
            'create': self.create_serializer_class,
            'update': self.update_serializer_class,
        }
        return mapping.get(action)
    
    def get_serializer(
        self,
        action: str,
        instance: Optional[Model] = None,
        data: Optional[Dict[str, Any]] = None,
        many: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional["ModelSerializer"]:
        """
        Get an instantiated serializer for a given action.
        
        Args:
            action: One of 'list', 'retrieve', 'create', 'update'
            instance: Model instance for serialization
            data: Data for deserialization
            many: Whether handling multiple items
            context: Additional context (e.g., request)
            
        Returns:
            Serializer instance or None if no serializer defined
        """
        serializer_cls = self.get_serializer_class(action)
        if serializer_cls is None:
            return None
        
        return serializer_cls(
            instance=instance,
            data=data,
            many=many,
            context=context,
        )
    
    def uses_serializer(self, action: str) -> bool:
        """Check if an action uses a serializer (vs Pydantic schema)."""
        return self.get_serializer_class(action) is not None
    
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
        return await self._paginate(queryset, limit, offset, request=request)
    
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
            return self._serialize(instance, action='retrieve', request=request)
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
        
        If create_serializer_class is defined, uses serializer for validation
        and creation. Otherwise uses the data directly.
        
        Args:
            data: Validated data from Create schema or raw data for serializer
            request: FastAPI Request object
            
        Returns:
            Created item data
        """
        serializer = self.get_serializer(
            'create',
            data=data,
            context={'request': request},
        )
        
        if serializer is not None:
            # Use serializer flow
            serializer.is_valid(raise_exception=True)
            instance = await serializer.save()
            return self._serialize(instance, action='retrieve', request=request)
        else:
            # Schema flow (original behavior)
            instance = await self.model.objects.create(**data)
            return self._serialize(instance, action='retrieve', request=request)
    
    async def update(
        self,
        pk: str,
        data: Dict[str, Any],
        request: Request,
    ) -> Dict[str, Any]:
        """
        Update an existing item (partial update).
        
        If update_serializer_class is defined, uses serializer for validation
        and update. Otherwise applies changes directly.
        
        Args:
            pk: Primary key value
            data: Validated data from Update schema or raw data for serializer
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
        
        serializer = self.get_serializer(
            'update',
            instance=instance,
            data=data,
            context={'request': request},
        )
        
        if serializer is not None:
            # Use serializer flow
            serializer.is_valid(raise_exception=True)
            instance = await serializer.save()
            return self._serialize(instance, action='retrieve', request=request)
        else:
            # Schema flow (original behavior)
            # Apply updates (only non-None values)
            for key, value in data.items():
                if value is not None:
                    setattr(instance, key, value)
            
            await instance.save()
            return self._serialize(instance, action='retrieve', request=request)
    
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
        request: Optional[Request] = None,
    ) -> Dict[str, Any]:
        """
        Apply pagination to a queryset.
        
        Args:
            queryset: The queryset to paginate
            limit: Maximum items to return
            offset: Items to skip
            request: Optional request for serializer context
            
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
            "results": [
                self._serialize(item, action='list', request=request)
                for item in results
            ],
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
    
    def _serialize(
        self,
        instance: Model,
        action: str = 'retrieve',
        request: Optional[Request] = None,
    ) -> Dict[str, Any]:
        """
        Serialize a model instance to a dictionary.
        
        Uses serializer if defined for the action, otherwise uses model_to_dict.
        
        Args:
            instance: Model instance
            action: One of 'list', 'retrieve', 'create', 'update'
            request: Optional request for serializer context
            
        Returns:
            Dictionary suitable for JSON response
        """
        serializer = self.get_serializer(
            action,
            instance=instance,
            context={'request': request} if request else None,
        )
        
        if serializer is not None:
            return serializer.to_representation()
        else:
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
