# API Reference

Complete reference for Aksara's API layer.

---

## ViewSets

### ModelViewSet

Full CRUD ViewSet for a model.

```python
from aksara.api import ModelViewSet

class UserViewSet(ModelViewSet):
    model = User
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["is_active", "role"]
    search_fields = ["name", "email"]
    ordering_fields = ["created_at", "name"]
    ordering = ["-created_at"]
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `model` | Model | The model class |
| `serializer_class` | Serializer | Default serializer |
| `permission_classes` | list | Permission classes |
| `filterset_fields` | list | Filterable fields |
| `search_fields` | list | Searchable fields |
| `ordering_fields` | list | Fields for ordering |
| `ordering` | list | Default ordering |
| `pagination_class` | Pagination | Pagination class |
| `lookup_field` | str | Lookup field (default: "id") |

#### Methods

| Method | Description |
|--------|-------------|
| `get_queryset()` | Return the queryset |
| `get_object()` | Get single object |
| `get_serializer_class()` | Return serializer class |
| `get_permissions()` | Return permission instances |
| `perform_create(serializer)` | Called on create |
| `perform_update(serializer)` | Called on update |
| `perform_destroy(instance)` | Called on delete |

#### Actions

| Action | Method | URL |
|--------|--------|-----|
| `list` | GET | `/` |
| `create` | POST | `/` |
| `retrieve` | GET | `/{id}/` |
| `update` | PUT | `/{id}/` |
| `partial_update` | PATCH | `/{id}/` |
| `destroy` | DELETE | `/{id}/` |

### ViewSet

Base ViewSet without default actions.

```python
from aksara.api import ViewSet, action

class CustomViewSet(ViewSet):
    @action(detail=False, methods=["get"])
    async def custom_list(self, request):
        return {"data": []}
    
    @action(detail=True, methods=["post"])
    async def custom_action(self, request, pk=None):
        return {"id": pk}
```

### ReadOnlyModelViewSet

Read-only ViewSet (list and retrieve only).

```python
from aksara.api import ReadOnlyModelViewSet

class PostViewSet(ReadOnlyModelViewSet):
    model = Post
    serializer_class = PostSerializer
```

---

## Actions

### @action Decorator

```python
from aksara.api import action

@action(
    detail=True,           # True for /items/{id}/action
    methods=["post"],      # HTTP methods
    url_path="custom-path", # Custom URL path
    url_name="custom_name", # Custom URL name
    permission_classes=[IsAdmin],  # Override permissions
    serializer_class=CustomSerializer,  # Override serializer
)
async def my_action(self, request, pk=None):
    return {"success": True}
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `detail` | bool | Required | True for detail route |
| `methods` | list | `["get"]` | HTTP methods |
| `url_path` | str | Method name | URL path |
| `url_name` | str | Method name | URL name |
| `permission_classes` | list | None | Override permissions |
| `serializer_class` | class | None | Override serializer |

---

## Serializers

### ModelSerializer

```python
from aksara.api import ModelSerializer

class UserSerializer(ModelSerializer):
    full_name = SerializerMethodField()
    
    class Meta:
        model = User
        fields = ["id", "email", "name", "full_name", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            "password": {"write_only": True},
        }
    
    async def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
```

#### Meta Options

| Option | Type | Description |
|--------|------|-------------|
| `model` | Model | Model class |
| `fields` | list/str | Fields to include (`"__all__"` for all) |
| `exclude` | list | Fields to exclude |
| `read_only_fields` | list | Read-only fields |
| `extra_kwargs` | dict | Per-field options |

#### Methods

| Method | Description |
|--------|-------------|
| `validate_<field>(value)` | Validate single field |
| `validate(data)` | Cross-field validation |
| `create(validated_data)` | Create instance |
| `update(instance, validated_data)` | Update instance |
| `to_representation(instance)` | Convert to output |
| `to_internal_value(data)` | Convert from input |

### Serializer

Aksara serializers use Pydantic under the hood, so fields are inferred from your model automatically:

```python
from aksara.api import ModelSerializer

class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "is_active"]
        read_only_fields = ["id", "created_at"]
    
    def validate_email(self, value):
        # Custom field validation
        return value.lower()
    
    async def validate(self, data):
        # Cross-field validation
        return data
```

### Meta Class Options

| Option | Type | Description |
|--------|------|-------------|
| `model` | Model class | The Aksara model to serialize |
| `fields` | list or `"__all__"` | Fields to include |
| `exclude` | list | Fields to exclude |
| `read_only_fields` | list | Fields in output only |
| `expand` | list or dict | FK expansion configuration |

### SerializerMethodField

For computed fields:

```python
class PostSerializer(ModelSerializer):
    author_name = SerializerMethodField()
    
    class Meta:
        model = Post
        fields = ["id", "title", "author_name"]
    
    async def get_author_name(self, obj):
        author = await obj.author
        return author.name
```
```

---

## Permissions

### Built-in Permissions

```python
from aksara.api.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAdminUser,
    IsAuthenticatedOrReadOnly,
)
```

| Permission | Description |
|------------|-------------|
| `AllowAny` | Allow all requests |
| `IsAuthenticated` | Require authentication |
| `IsAdminUser` | Require admin user |
| `IsAuthenticatedOrReadOnly` | Auth for writes |

### Custom Permission

```python
from aksara.api.permissions import BasePermission

class IsOwner(BasePermission):
    async def has_object_permission(self, request, view, obj):
        return obj.owner_id == request.user.id

class HasSubscription(BasePermission):
    async def has_permission(self, request, view):
        return request.user.has_active_subscription
```

### Permission Methods

| Method | Description |
|--------|-------------|
| `has_permission(request, view)` | Check view-level access |
| `has_object_permission(request, view, obj)` | Check object-level access |

---

## Authentication

### Token Authentication

```python
from aksara.api.authentication import TokenAuthentication

# In settings
"DEFAULT_AUTHENTICATION_CLASSES": [
    "aksara.api.authentication.TokenAuthentication",
]
```

### Custom Authentication

```python
from aksara.api.authentication import BaseAuthentication

class APIKeyAuthentication(BaseAuthentication):
    async def authenticate(self, request):
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return None
        
        user = await User.objects.filter(api_key=api_key).first()
        if user:
            return (user, None)
        return None
```

---

## Pagination

### PageNumberPagination

```python
from aksara.api.pagination import PageNumberPagination

class CustomPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
```

Response format:

```json
{
    "count": 100,
    "next": "/api/posts/?page=2",
    "previous": null,
    "results": [...]
}
```

### LimitOffsetPagination

```python
from aksara.api.pagination import LimitOffsetPagination

class CustomPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100
```

### CursorPagination

```python
from aksara.api.pagination import CursorPagination

class CustomPagination(CursorPagination):
    ordering = "-created_at"
    page_size = 20
```

---

## Filtering

### FilterSet

```python
from aksara.api.filters import FilterSet, Filter

class PostFilterSet(FilterSet):
    author = Filter(field_name="author_id")
    published = Filter(field_name="is_published")
    created_after = Filter(field_name="created_at", lookup="gte")
    title_contains = Filter(field_name="title", lookup="contains")
    
    class Meta:
        model = Post

class PostViewSet(ModelViewSet):
    filterset_class = PostFilterSet
```

### Filter Lookups

| Lookup | SQL | Example |
|--------|-----|---------|
| `exact` | `=` | `?status=active` |
| `iexact` | `ILIKE` | `?name__iexact=john` |
| `contains` | `LIKE %x%` | `?title__contains=python` |
| `icontains` | `ILIKE %x%` | `?title__icontains=python` |
| `gt` | `>` | `?price__gt=100` |
| `gte` | `>=` | `?price__gte=100` |
| `lt` | `<` | `?price__lt=100` |
| `lte` | `<=` | `?price__lte=100` |
| `in` | `IN` | `?status__in=a,b,c` |
| `isnull` | `IS NULL` | `?deleted_at__isnull=true` |

---

## Routing

### Router

```python
from aksara.api import Router

router = Router()
router.register("users", UserViewSet)
router.register("posts", PostViewSet)

# Get routes
routes = router.routes
```

### Include ViewSet

```python
from aksara.api import include_viewset

# In urls.py
routes = [
    include_viewset("/users", UserViewSet),
    include_viewset("/posts", PostViewSet, basename="post"),
]
```

### Manual Routes

```python
from aksara.api import APIRouter

router = APIRouter()

@router.get("/custom")
async def custom_endpoint(request):
    return {"data": "value"}

@router.post("/custom/{id}")
async def custom_action(request, id: str):
    return {"id": id}
```

---

## Request & Response

### Request Object

```python
async def my_view(request):
    # User
    user = request.user
    is_auth = request.user.is_authenticated
    
    # Data
    data = request.data  # Parsed body
    query = request.query_params  # Query string
    
    # Headers
    auth = request.headers.get("Authorization")
    
    # Method
    method = request.method  # GET, POST, etc.
```

### Response Formats

```python
from aksara.api import Response

# JSON response (default)
return {"data": "value"}

# Custom status
return {"error": "Not found"}, 404

# Response object
return Response(
    data={"key": "value"},
    status=201,
    headers={"X-Custom": "header"}
)
```

---

## Throttling

### Built-in Throttles

```python
from aksara.api.throttling import AnonRateThrottle, UserRateThrottle

class PostViewSet(ModelViewSet):
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
```

### Custom Throttle

```python
from aksara.api.throttling import BaseThrottle

class BurstThrottle(BaseThrottle):
    rate = "60/minute"
    
    def get_cache_key(self, request, view):
        return f"throttle:{request.user.id}"
```

---

## Related Documentation

- [ViewSets Guide](../api/viewsets.md)
- [Serializers Guide](../api/serializers.md)
- [Permissions Guide](../api/permissions.md)
