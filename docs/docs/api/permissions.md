# Permissions

Control API access with permission classes.

---

## Overview

Permissions determine whether a request should be granted or denied access:

```python
from aksara.api import ModelViewSet
from aksara.permissions import IsAuthenticated

class PostViewSet(ModelViewSet):
    model = Post
    permission_classes = [IsAuthenticated]
```

---

## Built-in Permissions

### AllowAny

Unrestricted access:

```python
from aksara.permissions import AllowAny

class PublicViewSet(ModelViewSet):
    model = Post
    permission_classes = [AllowAny]
```

### IsAuthenticated

Only authenticated users:

```python
from aksara.permissions import IsAuthenticated

class PostViewSet(ModelViewSet):
    model = Post
    permission_classes = [IsAuthenticated]
```

### IsAdminUser

Only staff/admin users:

```python
from aksara.permissions import IsAdminUser

class AdminViewSet(ModelViewSet):
    model = Settings
    permission_classes = [IsAdminUser]
```

### IsAuthenticatedOrReadOnly

Authenticated for writes, anyone can read:

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.permissions import IsAuthenticatedOrReadOnly

class PostViewSet(ModelViewSet):
    model = Post
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    # GET /posts/ - anyone
    # POST /posts/ - authenticated only
```

---

## Action-Specific Permissions

Override permissions for specific actions:

```python
from aksara.permissions import IsAuthenticated, IsAdminUser

class PostViewSet(ModelViewSet):
    model = Post
    permission_classes = [IsAuthenticated]  # Default
    
    def get_permissions(self):
        """Different permissions per action."""
        if self.action in ["list", "retrieve"]:
            # Public read access
            return []
        
        if self.action == "destroy":
            # Only admins can delete
            return [IsAdminUser()]
        
        # Default: authenticated
        return [IsAuthenticated()]
```

### Using action Decorator

```python
from aksara.api import action
from aksara.permissions import IsAdminUser

class PostViewSet(ModelViewSet):
    model = Post
    
    @action(detail=True, methods=["POST"], permission_classes=[IsAdminUser])
    async def feature(self, request, id: str):
        """Admin-only action."""
        ...
```

---

## Custom Permissions

### Basic Custom Permission

```python
from aksara.permissions import BasePermission

class IsOwner(BasePermission):
    """Only allow owners of an object to edit it."""
    
    def has_permission(self, request, view):
        # Called for all requests
        return request.user.is_authenticated
    
    async def has_object_permission(self, request, view, obj):
        # Called for object-level actions
        return str(obj.author_id) == str(request.user.id)
```

### Using Custom Permission

```python
class PostViewSet(ModelViewSet):
    model = Post
    permission_classes = [IsOwner]
```

### Permission Methods

| Method | Called | Purpose |
|--------|--------|---------|
| `has_permission(request, view)` | All requests | View-level check |
| `has_object_permission(request, view, obj)` | Object operations | Object-level check |

---

## Common Permission Patterns

### Owner or Admin

```python
class IsOwnerOrAdmin(BasePermission):
    """Allow access to owner or admin."""
    
    async def has_object_permission(self, request, view, obj):
        # Admin can access all
        if request.user.is_staff:
            return True
        
        # Owner can access their own
        return str(obj.author_id) == str(request.user.id)
```

### Role-Based Access

```python
class HasRole(BasePermission):
    """Check if user has required role."""
    
    def __init__(self, *roles):
        self.roles = roles
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.role in self.roles

# Usage
class EditorViewSet(ModelViewSet):
    permission_classes = [HasRole("editor", "admin")]
```

### Team/Organization Access

```python
class IsTeamMember(BasePermission):
    """Allow access only to team members."""
    
    async def has_object_permission(self, request, view, obj):
        # Get the project/team
        team = await obj.team
        
        # Check membership
        is_member = await team.members.filter(
            id=str(request.user.id)
        ).exists()
        
        return is_member
```

### Read-Only for Non-Owners

```python
class IsOwnerOrReadOnly(BasePermission):
    """Owner can edit, others can only read."""
    
    SAFE_METHODS = ["GET", "HEAD", "OPTIONS"]
    
    async def has_object_permission(self, request, view, obj):
        # Allow read-only for everyone
        if request.method in self.SAFE_METHODS:
            return True
        
        # Write only for owner
        return str(obj.author_id) == str(request.user.id)
```

### Premium Features

```python
class IsPremiumUser(BasePermission):
    """Only premium subscribers can access."""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.subscription_tier == "premium"
```

---

## Combining Permissions

### AND Logic (All must pass)

```python
class PostViewSet(ModelViewSet):
    model = Post
    permission_classes = [IsAuthenticated, IsOwner]
    # User must be authenticated AND be the owner
```

### OR Logic (Any can pass)

```python
from aksara.permissions import BasePermission

class IsOwnerOrAdmin(BasePermission):
    async def has_object_permission(self, request, view, obj):
        return (
            str(obj.author_id) == str(request.user.id) or
            request.user.is_staff
        )
```

### Complex Logic

```python
class ComplexPermission(BasePermission):
    """Complex permission logic."""
    
    async def has_permission(self, request, view):
        # Must be authenticated
        if not request.user.is_authenticated:
            return False
        
        # Admin can do anything
        if request.user.is_staff:
            return True
        
        # Check specific conditions
        if view.action == "create":
            # Rate limit check
            recent_count = await Post.objects.filter(
                author=request.user,
                created_at__gt=one_hour_ago,
            ).count()
            return recent_count < 10
        
        return True
```

---

## Permission Denied Responses

### Default Response

```json
{
    "detail": "You do not have permission to perform this action."
}
```

### Custom Messages

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.permissions import BasePermission, PermissionDenied

class IsOwner(BasePermission):
    message = "You can only modify your own content."
    
    async def has_object_permission(self, request, view, obj):
        if str(obj.author_id) != str(request.user.id):
            raise PermissionDenied(self.message)
        return True
```

### Action-Specific Messages

```python
class PostPermission(BasePermission):
    async def has_object_permission(self, request, view, obj):
        if view.action == "destroy":
            if not request.user.is_staff:
                raise PermissionDenied("Only admins can delete posts")
        
        if view.action in ["update", "partial_update"]:
            if str(obj.author_id) != str(request.user.id):
                raise PermissionDenied("You can only edit your own posts")
        
        return True
```

---

## Checking Permissions Manually

### In ViewSet Methods

```python
class PostViewSet(ModelViewSet):
    model = Post
    
    async def publish(self, request, id: str):
        post = await self.get_object(id)
        
        # Manual permission check
        if str(post.author_id) != str(request.user.id):
            raise PermissionDenied("You can only publish your own posts")
        
        ...
```

### Using Permission Class

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.permissions import IsOwner

class PostViewSet(ModelViewSet):
    model = Post
    
    async def custom_action(self, request, id: str):
        post = await self.get_object(id)
        
        # Check with permission class
        permission = IsOwner()
        if not await permission.has_object_permission(request, self, post):
            raise PermissionDenied()
        
        ...
```

---

## Request Object

Permissions receive the request object with useful attributes:

```python
class CustomPermission(BasePermission):
    def has_permission(self, request, view):
        # User info
        user = request.user
        user.is_authenticated  # bool
        user.is_staff          # bool
        user.id                # user ID
        
        # Request info
        request.method         # "GET", "POST", etc.
        request.path           # "/posts/123/"
        request.headers        # Headers dict
        request.query_params   # Query parameters
        
        # View info
        view.action            # "list", "create", etc.
        view.kwargs            # URL parameters
        
        return True
```

---

## Complete Example

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
# permissions.py
from aksara.permissions import BasePermission, PermissionDenied


class IsAuthenticated(BasePermission):
    """User must be logged in."""
    
    message = "Authentication required."
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsOwnerOrAdmin(BasePermission):
    """User must be owner or admin."""
    
    message = "You can only access your own resources."
    
    async def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        
        # Check owner field (could be author, user, owner, etc.)
        owner_field = getattr(obj, "author_id", None) or getattr(obj, "user_id", None)
        return str(owner_field) == str(request.user.id)


class CanPublish(BasePermission):
    """Check if user can publish content."""
    
    async def has_object_permission(self, request, view, obj):
        # Only author can publish
        if str(obj.author_id) != str(request.user.id):
            raise PermissionDenied("You can only publish your own posts")
        
        # Check if already published
        if obj.is_published:
            raise PermissionDenied("Post is already published")
        
        return True


class IsNotBanned(BasePermission):
    """Check user is not banned."""
    
    def has_permission(self, request, view):
        if request.user.is_authenticated and request.user.is_banned:
            raise PermissionDenied("Your account has been suspended")
        return True


# viewsets.py
from aksara.api import ModelViewSet, action
from myapp.permissions import IsAuthenticated, IsOwnerOrAdmin, CanPublish


class PostViewSet(ModelViewSet):
    """Post API with granular permissions."""
    
    model = Post
    permission_classes = [IsAuthenticated, IsNotBanned]
    
    def get_permissions(self):
        """Action-specific permissions."""
        if self.action in ["list", "retrieve"]:
            # Public read
            return []
        
        if self.action == "destroy":
            # Admin only
            return [IsAuthenticated(), IsAdminUser()]
        
        if self.action in ["update", "partial_update"]:
            # Owner or admin
            return [IsAuthenticated(), IsOwnerOrAdmin()]
        
        # Default
        return super().get_permissions()
    
    @action(detail=True, methods=["POST"], permission_classes=[CanPublish])
    async def publish(self, request, id: str):
        """Publish a post (owner only, not already published)."""
        post = await self.get_object(id)
        post.is_published = True
        await post.save()
        return {"status": "published"}
    
    @action(detail=True, methods=["POST"], permission_classes=[IsAdminUser])
    async def feature(self, request, id: str):
        """Feature a post (admin only)."""
        post = await self.get_object(id)
        post.is_featured = True
        await post.save()
        return {"status": "featured"}
```

---

## Related Documentation

- [Authentication](authentication.md) — User authentication
- [ViewSets](viewsets.md) — ViewSet configuration
- [Actions](actions.md) — Custom endpoints
