"""
Vidyut Permissions

DRF-inspired permission system for Vidyut APIs.

Provides base permission class and common permission implementations
for controlling access to API endpoints.

Usage:
    from vidyut.permissions import IsAuthenticated, IsAdminUser
    from vidyut.viewsets import ModelViewSet
    
    class ArticleViewSet(ModelViewSet):
        model = Article
        permission_classes = [IsAuthenticated]
    
    # Or combine permissions
    class AdminViewSet(ModelViewSet):
        model = User
        permission_classes = [IsAuthenticated, IsAdminUser]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional, List, Type

if TYPE_CHECKING:
    from vidyut.identity import VidyutUserProtocol


__all__ = [
    "BasePermission",
    "AllowAny",
    "IsAuthenticated",
    "IsAdminUser",
    "IsActiveUser",
    "IsOwnerOrReadOnly",
    "DenyAI",
    "OperationPermission",
    "AND",
    "OR",
    "check_permissions",
]


class BasePermission(ABC):
    """
    Base class for all permissions.
    
    Permissions control access to API views based on the request
    and/or the object being accessed.
    
    Subclass this to create custom permissions.
    
    Attributes:
        message: Default error message when permission is denied.
        ai_allow: Whether this permission allows AI agent access.
                  Set to False to block AI agents from this resource.
    
    Example:
        class IsTeamMember(BasePermission):
            message = "You must be a team member to access this resource."
            
            def has_permission(self, request, view=None):
                user = self.get_user(request)
                return user and user.is_authenticated
            
            def has_object_permission(self, request, view, obj):
                user = self.get_user(request)
                return obj.team_id == user.team_id
    """
    
    message: str = "Permission denied."
    ai_allow: bool = True  # Default: allow AI access
    
    def get_user(self, request: Any) -> Optional["VidyutUserProtocol"]:
        """
        Extract user from request object.
        
        Checks common locations:
        - request.state.user (Starlette/FastAPI)
        - request.user (Django-style)
        """
        # Starlette/FastAPI style
        if hasattr(request, "state") and hasattr(request.state, "user"):
            return request.state.user
        
        # Django style
        if hasattr(request, "user"):
            return request.user
        
        return None
    
    def is_safe_method(self, request: Any) -> bool:
        """Check if request method is safe (read-only)."""
        method = getattr(request, "method", "GET")
        return method.upper() in ("GET", "HEAD", "OPTIONS")
    
    @abstractmethod
    def has_permission(self, request: Any, view: Any = None) -> bool:
        """
        Check if request has permission for the view.
        
        Called before the view handler is executed.
        
        Args:
            request: The incoming request.
            view: The view being accessed (optional).
        
        Returns:
            True if permission is granted, False otherwise.
        """
        ...
    
    def has_object_permission(
        self, request: Any, view: Any, obj: Any
    ) -> bool:
        """
        Check if request has permission for a specific object.
        
        Called after has_permission() when accessing a specific object.
        
        Args:
            request: The incoming request.
            view: The view being accessed.
            obj: The object being accessed.
        
        Returns:
            True if permission is granted, False otherwise.
        """
        # Default: defer to has_permission
        return True
    
    def __and__(self, other: "BasePermission") -> "AND":
        """Combine permissions with AND logic."""
        return AND(self, other)
    
    def __or__(self, other: "BasePermission") -> "OR":
        """Combine permissions with OR logic."""
        return OR(self, other)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


class AllowAny(BasePermission):
    """
    Allow any access (no restrictions).
    
    Use this for public endpoints that don't require authentication.
    
    Usage:
        class PublicViewSet(ModelViewSet):
            model = Article
            permission_classes = [AllowAny]
    """
    
    message = "Access allowed."
    
    def has_permission(self, request: Any, view: Any = None) -> bool:
        return True


class IsAuthenticated(BasePermission):
    """
    Require user to be authenticated.
    
    Denies access to anonymous/unauthenticated users.
    
    Usage:
        class ProtectedViewSet(ModelViewSet):
            model = Profile
            permission_classes = [IsAuthenticated]
    """
    
    message = "Authentication required."
    
    def has_permission(self, request: Any, view: Any = None) -> bool:
        user = self.get_user(request)
        return user is not None and getattr(user, "is_authenticated", False)


class IsAdminUser(BasePermission):
    """
    Require user to be staff or superuser.
    
    Grants access only to users with is_staff=True or is_superuser=True.
    
    Usage:
        class AdminViewSet(ModelViewSet):
            model = User
            permission_classes = [IsAuthenticated, IsAdminUser]
    """
    
    message = "Admin access required."
    
    def has_permission(self, request: Any, view: Any = None) -> bool:
        user = self.get_user(request)
        if user is None:
            return False
        
        return (
            getattr(user, "is_staff", False) or
            getattr(user, "is_superuser", False)
        )


class IsActiveUser(BasePermission):
    """
    Require user to be authenticated and active.
    
    Denies access if user.is_active is False.
    
    Usage:
        class UserViewSet(ModelViewSet):
            model = Profile
            permission_classes = [IsActiveUser]
    """
    
    message = "Active user required."
    
    def has_permission(self, request: Any, view: Any = None) -> bool:
        user = self.get_user(request)
        if user is None:
            return False
        
        return (
            getattr(user, "is_authenticated", False) and
            getattr(user, "is_active", True)
        )


class IsOwnerOrReadOnly(BasePermission):
    """
    Allow read access to anyone, write access only to object owner.
    
    Requires objects to have a user_id, owner_id, author_id, or created_by
    attribute matching the current user's ID.
    
    Usage:
        class PostViewSet(ModelViewSet):
            model = Post
            permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    """
    
    message = "You can only modify your own objects."
    owner_field_names = ("user_id", "owner_id", "author_id", "created_by")
    
    def has_permission(self, request: Any, view: Any = None) -> bool:
        # Allow all at the view level
        return True
    
    def has_object_permission(
        self, request: Any, view: Any, obj: Any
    ) -> bool:
        # Allow safe methods (read-only)
        if self.is_safe_method(request):
            return True
        
        user = self.get_user(request)
        if user is None:
            return False
        
        user_id = getattr(user, "id", None)
        if user_id is None:
            return False
        
        # Check common owner field names
        for field_name in self.owner_field_names:
            owner_id = getattr(obj, field_name, None)
            if owner_id is not None:
                return owner_id == user_id
        
        # No owner field found - deny by default
        return False


class DenyAI(BasePermission):
    """
    Deny access to AI agents.
    
    Use this to protect sensitive endpoints from AI agent access.
    This checks for the X-AI-Agent header or ai_agent flag on request.
    
    Usage:
        class SensitiveViewSet(ModelViewSet):
            model = Secret
            permission_classes = [IsAuthenticated, DenyAI]
    """
    
    message = "AI agent access denied."
    ai_allow = False  # Explicitly deny AI
    
    def has_permission(self, request: Any, view: Any = None) -> bool:
        # Check for AI agent indicators
        
        # Check header
        ai_header = getattr(request, "headers", {}).get("X-AI-Agent")
        if ai_header and ai_header.lower() in ("true", "1", "yes"):
            return False
        
        # Check request state
        if hasattr(request, "state"):
            if getattr(request.state, "is_ai_agent", False):
                return False
        
        # Check request attribute
        if getattr(request, "is_ai_agent", False):
            return False
        
        return True


class OperationPermission(BasePermission):
    """
    Permission based on CRUD operation type.
    
    Allows fine-grained control over which operations are permitted.
    
    Args:
        allow: List of allowed operations ('create', 'read', 'update', 'delete').
    
    Usage:
        class ReadOnlyViewSet(ModelViewSet):
            model = Log
            permission_classes = [OperationPermission(allow=['read'])]
    """
    
    OPERATION_MAP = {
        "GET": "read",
        "HEAD": "read",
        "OPTIONS": "read",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }
    
    def __init__(self, allow: List[str]):
        self.allow = set(allow)
        self.message = f"Only {', '.join(allow)} operations are allowed."
    
    def has_permission(self, request: Any, view: Any = None) -> bool:
        method = getattr(request, "method", "GET").upper()
        operation = self.OPERATION_MAP.get(method, "read")
        return operation in self.allow
    
    def __repr__(self) -> str:
        return f"OperationPermission(allow={list(self.allow)})"


class AND(BasePermission):
    """
    Combine multiple permissions with AND logic.
    
    All permissions must pass for access to be granted.
    
    Usage:
        perm = IsAuthenticated() & IsAdminUser()
        # or
        perm = AND(IsAuthenticated(), IsAdminUser())
    """
    
    def __init__(self, *permissions: BasePermission):
        self.permissions = permissions
        self.ai_allow = all(p.ai_allow for p in permissions)
    
    def has_permission(self, request: Any, view: Any = None) -> bool:
        for perm in self.permissions:
            if not perm.has_permission(request, view):
                self.message = perm.message
                return False
        return True
    
    def has_object_permission(
        self, request: Any, view: Any, obj: Any
    ) -> bool:
        for perm in self.permissions:
            if not perm.has_object_permission(request, view, obj):
                self.message = perm.message
                return False
        return True
    
    def __repr__(self) -> str:
        perms = " & ".join(repr(p) for p in self.permissions)
        return f"AND({perms})"


class OR(BasePermission):
    """
    Combine multiple permissions with OR logic.
    
    At least one permission must pass for access to be granted.
    
    Usage:
        perm = IsAdminUser() | IsOwnerOrReadOnly()
        # or
        perm = OR(IsAdminUser(), IsOwnerOrReadOnly())
    """
    
    def __init__(self, *permissions: BasePermission):
        self.permissions = permissions
        self.ai_allow = any(p.ai_allow for p in permissions)
    
    def has_permission(self, request: Any, view: Any = None) -> bool:
        messages = []
        for perm in self.permissions:
            if perm.has_permission(request, view):
                return True
            messages.append(perm.message)
        
        self.message = " OR ".join(messages)
        return False
    
    def has_object_permission(
        self, request: Any, view: Any, obj: Any
    ) -> bool:
        for perm in self.permissions:
            if perm.has_object_permission(request, view, obj):
                return True
        return False
    
    def __repr__(self) -> str:
        perms = " | ".join(repr(p) for p in self.permissions)
        return f"OR({perms})"


def check_permissions(
    permissions: List[Type[BasePermission] | BasePermission],
    request: Any,
    view: Any = None,
    obj: Any = None,
) -> tuple[bool, Optional[str]]:
    """
    Check if a request passes all permissions.
    
    Args:
        permissions: List of permission classes or instances.
        request: The incoming request.
        view: The view being accessed (optional).
        obj: The object being accessed (optional).
    
    Returns:
        Tuple of (allowed: bool, error_message: Optional[str]).
    
    Usage:
        allowed, message = check_permissions(
            [IsAuthenticated, IsAdminUser],
            request,
            view,
        )
        if not allowed:
            raise HTTPException(status_code=403, detail=message)
    """
    for perm in permissions:
        # Instantiate if it's a class
        if isinstance(perm, type):
            perm = perm()
        
        # Check view-level permission
        if not perm.has_permission(request, view):
            return False, perm.message
        
        # Check object-level permission if object provided
        if obj is not None:
            if not perm.has_object_permission(request, view, obj):
                return False, perm.message
    
    return True, None


def check_ai_allowed(
    permissions: List[Type[BasePermission] | BasePermission],
) -> bool:
    """
    Check if AI agent access is allowed by all permissions.
    
    Args:
        permissions: List of permission classes or instances.
    
    Returns:
        True if all permissions allow AI access.
    """
    for perm in permissions:
        if isinstance(perm, type):
            perm = perm()
        
        if not perm.ai_allow:
            return False
    
    return True
