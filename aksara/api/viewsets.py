"""
ModelViewSet - Auto-generated CRUD endpoints

Provides Django-like ViewSet functionality for Aksara models.
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
    
    # v0.3.10: Use permissions for access control:
    from aksara.permissions import IsAuthenticated, IsAdminUser
    
    class UserViewSet(ModelViewSet):
        model = User
        prefix = "/users"
        permission_classes = [IsAuthenticated]
        
        # Action-specific permissions
        @action(detail=False, permission_classes=[IsAdminUser])
        async def admin_only(self, request):
            return {"secret": "admin data"}
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Type, Union, cast

from fastapi import Request, HTTPException

from aksara.model.base import Model
from aksara.manager import DoesNotExist
from aksara.api.streaming import build_model_stream_response
from aksara.api.schemas import (
    generate_create_schema,
    generate_update_schema,
    generate_read_schema,
    model_to_dict,
)
from aksara.security.enforcement import enforce_request_payload_policy, policy_denied_to_error_payload
from aksara.security.exceptions import PolicyDenied
from aksara.security.context import principal_from_request
from aksara.security.policy import get_policy_engine
from aksara.security.principal import Principal
from aksara.tenancy import is_tenant_model

if TYPE_CHECKING:
    from aksara.manager import QuerySet
    from aksara.api.serializers import ModelSerializer
    from aksara.permissions import BasePermission
    from aksara.api.filters import BaseFilterBackend
    from aksara.api.pagination import BasePagination


class ModelViewSet:
    """
    Base ViewSet for auto-generating CRUD endpoints.
    
    Class Attributes:
        model: The Aksara Model class
        prefix: URL prefix (e.g., "/users")
        tags: FastAPI tags for documentation
        lookup_field: Field used for single-item lookups (default: "id")
        permission_classes: List of permission classes for access control
        ai_exposed: Whether this ViewSet is exposed to AI agents (default: True)
    
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
    
    v0.3.10 Permission Attributes:
        - permission_classes: List of permission classes to check
        - ai_exposed: Whether to expose to AI agents
    
    Override Methods:
        Override list(), retrieve(), create(), update(), delete()
        for custom business logic.
    """
    
    model: Type[Model] = None  # type: ignore
    prefix: str = ""
    tags: Optional[List[str]] = None
    lookup_field: str = "id"
    
    # Pagination
    default_limit: int = 20
    max_limit: int = 100
    pagination_class: Optional[Type["BasePagination"]] = None
    
    # Filtering
    filter_backends: List[Type["BaseFilterBackend"]] = []
    search_fields: List[str] = []
    ordering_fields: List[str] = []
    ordering: Optional[Union[str, List[str]]] = None
    
    # v0.3.10: Permission classes
    permission_classes: List[Type["BasePermission"]] = []
    ai_exposed: bool = True  # Whether exposed to AI agents
    mcp_approval_required_actions: ClassVar[set[str]] = set()
    stream_enabled: bool = True
    
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

        # v0.5.45: Cache permission instances so they are not rebuilt on every
        # call within a request (check_permissions, check_ai_access, and
        # check_object_permissions each hit get_permissions()).
        self._permission_instances: Optional[List["BasePermission"]] = None
    
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
    # v0.3.10: Permission Methods
    # =========================================================================
    
    def get_permissions(self) -> List["BasePermission"]:
        """
        Get instantiated permission instances.

        Override this for dynamic permission selection. Instances are cached
        on the viewset so repeated lifecycle checks within one request reuse
        the same permission objects.

        Returns:
            List of permission instances.
        """
        if self._permission_instances is None:
            permissions: List["BasePermission"] = []
            for perm_cls in self.permission_classes:
                if isinstance(perm_cls, type):
                    permissions.append(perm_cls())
                else:
                    permissions.append(perm_cls)
            self._permission_instances = permissions
        return self._permission_instances

    def get_action_permissions(self, action_method: Any) -> list[BasePermission]:
        """Resolve permissions for a custom action.

        An explicit ``permission_classes`` value on ``@action`` replaces the
        ViewSet permission list. ``None`` inherits ``get_permissions()``, so
        applications that override that hook retain their custom behavior.
        """
        from aksara.api.actions import get_action_metadata

        metadata = get_action_metadata(action_method) or {}
        configured = metadata.get("permission_classes")
        if configured is None:
            return self.get_permissions()

        permissions: list[BasePermission] = []
        for permission_class in configured:
            permissions.append(
                permission_class()
                if isinstance(permission_class, type)
                else permission_class
            )
        return permissions
    
    def check_permissions(
        self,
        request: Request,
        permissions: list[BasePermission] | None = None,
    ) -> None:
        """
        Check view-level permissions.
        
        Raises HTTPException if permission denied.
        
        Args:
            request: The incoming request.
        
        Raises:
            HTTPException: 403 if permission denied.
        """
        active_permissions = self.get_permissions() if permissions is None else permissions
        for permission in active_permissions:
            if not permission.has_permission(request, self):
                raise HTTPException(
                    status_code=403,
                    detail=permission.message,
                )
    
    def check_object_permissions(
        self,
        request: Request,
        obj: Model,
        permissions: list[BasePermission] | None = None,
    ) -> None:
        """
        Check object-level permissions.
        
        Called after retrieving an object.
        
        Args:
            request: The incoming request.
            obj: The object being accessed.
        
        Raises:
            HTTPException: 403 if permission denied.
        """
        active_permissions = self.get_permissions() if permissions is None else permissions
        for permission in active_permissions:
            if not permission.has_object_permission(request, self, obj):
                raise HTTPException(
                    status_code=403,
                    detail=permission.message,
                )

    def _payload_policy_context(self) -> Dict[str, Any]:
        """
        Return permission context for runtime field enforcement.

        Non-empty permission classes have already been evaluated before this
        helper is used. The policy engine may then treat an explicit public
        permission such as AllowAny as the route-level gate while it continues
        to enforce field-level writability.
        """
        return {
            "route_permission_granted": bool(self.get_permissions()),
        }
    
    def check_ai_access(
        self,
        request: Request,
        permissions: list[BasePermission] | None = None,
        *,
        ai_exposed: bool | None = None,
    ) -> None:
        """
        Check if AI agent access is allowed.
        
        Args:
            request: The incoming request.
        
        Raises:
            HTTPException: 403 if AI access denied.
        """
        # Check viewset-level ai_exposed
        effective_ai_exposed = self.ai_exposed if ai_exposed is None else ai_exposed
        if not effective_ai_exposed:
            if self._is_ai_request(request):
                raise HTTPException(
                    status_code=403,
                    detail="AI agent access denied.",
                )
        
        # Check permission-level ai_allow
        active_permissions = self.get_permissions() if permissions is None else permissions
        for permission in active_permissions:
            if not permission.ai_allow and self._is_ai_request(request):
                raise HTTPException(
                    status_code=403,
                    detail="AI agent access denied.",
                )
    
    def _is_ai_request(self, request: Request) -> bool:
        """Check if request is from an AI agent."""
        return getattr(getattr(request, "state", None), "is_ai_agent", False) is True
    
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
        # Check permissions
        self.check_permissions(request)
        self.check_ai_access(request)
        
        queryset = self.get_queryset(request=request, **filters)
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
        # Check view permissions
        self.check_permissions(request)
        self.check_ai_access(request)
        
        try:
            instance = await self.model.objects.get(**{self.lookup_field: pk})
            
            # Check object permissions
            self.check_object_permissions(request, instance)
            
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
        # Check permissions
        self.check_permissions(request)
        self.check_ai_access(request)

        # Runtime field-level enforcement (Round 3).
        # Generated schemas are not security controls — validate the payload
        # against the resolved Principal's writable fields before any save.
        try:
            enforce_request_payload_policy(
                request=request,
                action="create",
                model=self.model,
                payload=data,
                surface="rest_create",
                context=self._payload_policy_context(),
            )
        except PolicyDenied as exc:
            raise HTTPException(
                status_code=403,
                detail=policy_denied_to_error_payload(exc),
            )

        server_fields = self._server_controlled_create_fields(request)

        serializer = self.get_serializer(
            'create',
            data=data,
            context={'request': request},
        )

        if serializer is not None:
            # Use serializer flow
            serializer.is_valid(raise_exception=True)
            instance = await serializer.save(**server_fields)
            return self._serialize(instance, action='retrieve', request=request)
        else:
            # Schema flow (original behavior)
            instance = await self.model.objects.create(**data, **server_fields)
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
        # Check view permissions
        self.check_permissions(request)
        self.check_ai_access(request)
        
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
        
        # Check object permissions
        self.check_object_permissions(request, instance)

        # Runtime field-level enforcement (Round 3).
        try:
            enforce_request_payload_policy(
                request=request,
                action="update",
                model=self.model,
                payload=data,
                surface="rest_update",
                context=self._payload_policy_context(),
            )
        except PolicyDenied as exc:
            raise HTTPException(
                status_code=403,
                detail=policy_denied_to_error_payload(exc),
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
        # Check view permissions
        self.check_permissions(request)
        self.check_ai_access(request)
        
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
        
        # Check object permissions
        self.check_object_permissions(request, instance)
        
        await instance.delete()
        return {"deleted": True, "id": pk}

    async def stream(self, request: Request):
        """Stream model lifecycle events as server-sent events."""
        self.check_permissions(request)
        self.check_ai_access(request)
        return build_model_stream_response(request, self.model)
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def get_queryset(self, request: Optional[Request] = None, **filters: Any) -> "QuerySet":
        """
        Get the base queryset for list operations.
        
        Override this to customize filtering logic.
        
        Args:
            request: Optional FastAPI request for filter backends
            **filters: Filter parameters from query string
            
        Returns:
            QuerySet instance
        """
        policy_filters: Dict[str, Any] = {}
        if request is not None:
            principal = self._resolve_query_principal(request)
            if principal is not None:
                decision = get_policy_engine().query_filter(principal, self.model)
                if decision.denied:
                    raise HTTPException(status_code=403, detail=decision.reason)
                policy_filters = dict(decision.metadata.get("filters", {}) or {})

        # Remove None values from filters
        valid_filters = {k: v for k, v in filters.items() if v is not None}
        valid_filters.update(policy_filters)

        queryset = self.model.objects.filter(**valid_filters)

        # Apply filter backends
        if request and self.filter_backends:
            for backend_class in self.filter_backends:
                backend = backend_class()
                queryset = backend.filter_queryset(request, queryset, self)

        # Re-apply required policy filters after filter backends so query
        # parameters cannot override tenant constraints.
        if policy_filters:
            queryset = queryset.filter(**policy_filters)
                
        return queryset
    
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
        if self.pagination_class and request:
            paginator = self.pagination_class()
            queryset = await paginator.paginate_queryset(queryset, request)
            
            # Use limit/offset from paginator for fetch_with_pagination
            limit = getattr(paginator, "limit", limit)
            offset = getattr(paginator, "offset", offset)
            
            results = await self._fetch_with_pagination(queryset, limit, offset)
            serialized_data = [
                self._serialize(item, action='list', request=request)
                for item in results
            ]
            
            return paginator.get_paginated_response(serialized_data)
        
        # Fallback to default limit/offset pagination if no class defined
        # Enforce max limit
        if limit < 0:
            raise HTTPException(status_code=400, detail="limit must be non-negative")
        if offset < 0:
            raise HTTPException(status_code=400, detail="offset must be non-negative")
        limit = min(limit, self.max_limit)

        # Single round-trip: COUNT(*) OVER() returns the total alongside the
        # paginated rows so we don't issue a separate SELECT COUNT(*).
        paginated = queryset.limit(limit).offset(offset)
        results, total = await paginated.fetch_with_count()

        return {
            "count": total,
            "limit": limit,
            "offset": offset,
            "results": [
                self._serialize(item, action='list', request=request)
                for item in results
            ],
        }

    def _resolve_query_principal(self, request: Request) -> Optional[Principal]:
        """Resolve a principal for read/query policy checks without trusting headers."""
        state = getattr(request, "state", None)
        if state is not None:
            cached = getattr(state, "principal", None)
            if isinstance(cached, Principal):
                return cached
        try:
            return principal_from_request(request)
        except Exception:
            return None

    def _server_controlled_create_fields(self, request: Request) -> Dict[str, Any]:
        """Return trusted fields injected into generated create operations."""
        if not is_tenant_model(self.model):
            return {}

        principal = self._resolve_query_principal(request)
        tenant_id = principal.tenant_id if principal is not None else None
        if not tenant_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "tenant_context_required",
                    "message": "Tenant-scoped creates require an authenticated tenant context.",
                },
            )
        return {"tenant_id": tenant_id}
    
    async def _fetch_with_pagination(
        self,
        queryset: "QuerySet",
        limit: int,
        offset: int,
    ) -> List[Model]:
        """
        Fetch results with pagination applied.

        Pagination is layered on the queryset itself, so ordering, joins,
        annotations, and select_related/prefetch_related continue to apply.
        """
        return await queryset.limit(limit).offset(offset).all()
    
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
            result = cast(dict[str, Any], serializer.to_representation())
        else:
            result = model_to_dict(instance)

        # The generated API and MCP share this serialization path. AI-sensitive
        # fields therefore stay hidden at execution time as well as in schemas.
        if request is not None:
            principal = self._resolve_query_principal(request)
            if principal is not None and principal.is_ai_agent:
                decision = get_policy_engine().visible_fields(principal, self.model)
                allowed = set(decision.allowed_fields)
                from aksara.fields import ForeignKey  # type: ignore[attr-defined]

                for field_name, field in self.model._fields.items():
                    if field_name in allowed and isinstance(field, ForeignKey):
                        allowed.add(field.db_column_name)
                result = {key: value for key, value in result.items() if key in allowed}
        return result
    
    def get_filter_fields(self) -> List[str]:
        """
        Get list of fields that can be filtered on.
        
        Override to restrict filterable fields.
        
        Returns:
            List of field names
        """
        return list(self.model._fields.keys())


__all__ = ["ModelViewSet"]
