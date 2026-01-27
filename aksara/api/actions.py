"""
Aksara API Actions Module

Provides the @action decorator for defining custom endpoints on ModelViewSet.

Usage:
    from aksara.api import ModelViewSet, action

    class UserViewSet(ModelViewSet):
        model = User
        prefix = "/users"

        @action(detail=True, methods=["post"], summary="Deactivate user")
        async def deactivate(self, pk: UUID, request: Request):
            '''Deactivate a specific user account.'''
            user = await self.model.objects.get(id=pk)
            user.is_active = False
            await user.save()
            return {"status": "deactivated"}

        @action(detail=False, methods=["get"], summary="List active users")
        async def active(self, request: Request):
            '''Return all active users.'''
            return await self.model.objects.filter(is_active=True).all()
        
        # v0.3.10: Action-specific permissions
        @action(
            detail=False,
            methods=["get"],
            permission_classes=[IsAdminUser],
        )
        async def admin_only(self, request: Request):
            '''Endpoint only accessible to admin users.'''
            return {"secret": "admin data"}
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, List, Optional, TypeVar, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from aksara.permissions import BasePermission

F = TypeVar("F", bound=Callable[..., Any])


def action(
    *,
    detail: bool,
    methods: List[str],
    path: Optional[str] = None,
    name: Optional[str] = None,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    permission_classes: Optional[List[Type["BasePermission"]]] = None,
    ai_exposed: bool = True,
) -> Callable[[F], F]:
    """
    Decorator to mark a ModelViewSet method as a custom action endpoint.
    
    The decorated method will be registered as a FastAPI route when the
    ViewSet is included via include_viewset(). The route will appear in
    Swagger/OpenAPI documentation.
    
    Args:
        detail: If True, the action operates on a single resource (includes {pk} in path).
                If False, it's a collection-level action.
        methods: List of HTTP methods (e.g., ["get"], ["post", "put"]).
        path: Custom path segment. Defaults to the function name.
        name: Route name for reverse URL lookup. Defaults to function name.
        summary: Short summary for OpenAPI docs. Defaults to first line of docstring.
        description: Full description for OpenAPI docs. Defaults to full docstring.
        permission_classes: Override permission classes for this action.
                           If None, uses the ViewSet's permission_classes.
        ai_exposed: Whether this action is exposed to AI agents.
                   Defaults to True. Set to False to hide from AI.
    
    Returns:
        Decorated function with _aksara_action metadata attached.
    
    Examples:
        # Detail action: POST /users/{pk}/deactivate
        @action(detail=True, methods=["post"])
        async def deactivate(self, pk: UUID, request: Request):
            ...
        
        # Collection action: GET /users/active
        @action(detail=False, methods=["get"])
        async def active(self, request: Request):
            ...
        
        # Custom path: GET /users/{pk}/full-profile
        @action(detail=True, methods=["get"], path="full-profile")
        async def get_full_profile(self, pk: UUID, request: Request):
            ...
        
        # Action with specific permissions (v0.3.10)
        @action(
            detail=False,
            methods=["get"],
            permission_classes=[IsAuthenticated, IsAdminUser],
        )
        async def admin_dashboard(self, request: Request):
            ...
        
        # Action hidden from AI agents (v0.3.10)
        @action(
            detail=True,
            methods=["post"],
            ai_exposed=False,
        )
        async def sensitive_action(self, pk: UUID, request: Request):
            ...
    """
    def decorator(func: F) -> F:
        # Normalize methods to uppercase
        normalized_methods = [m.upper() for m in methods]
        
        # Attach metadata to the function
        func._aksara_action = {
            "detail": detail,
            "methods": normalized_methods,
            "path": path or func.__name__,
            "name": name or func.__name__,
            "summary": summary,
            "description": description,
            "permission_classes": permission_classes,
            "ai_exposed": ai_exposed,
        }
        
        return func
    
    return decorator


def get_action_metadata(func: Callable) -> Optional[dict]:
    """
    Get the action metadata from a function, if it exists.
    
    Args:
        func: The function to check
        
    Returns:
        The action metadata dict, or None if not an action
    """
    meta = getattr(func, "_aksara_action", None)
    
    # Verify it's actually our metadata dict (not a MagicMock or similar)
    if meta is None:
        return None
    
    # Check that it's a dict with the expected structure
    if not isinstance(meta, dict):
        return None
    
    # Verify required keys exist
    required_keys = {"detail", "methods", "path", "name"}
    if not required_keys.issubset(meta.keys()):
        return None
    
    return meta


def is_action(func: Callable) -> bool:
    """
    Check if a function is decorated with @action.
    
    Args:
        func: The function to check
        
    Returns:
        True if the function has action metadata
    """
    return hasattr(func, "_aksara_action")


def get_action_permissions(func: Callable) -> Optional[List[Type["BasePermission"]]]:
    """
    Get the permission classes for an action.
    
    Args:
        func: The action function
        
    Returns:
        List of permission classes, or None if not specified
    """
    meta = get_action_metadata(func)
    if meta is None:
        return None
    
    return meta.get("permission_classes")


def is_action_ai_exposed(func: Callable) -> bool:
    """
    Check if an action is exposed to AI agents.
    
    Args:
        func: The action function
        
    Returns:
        True if action is AI-exposed (default), False otherwise
    """
    meta = get_action_metadata(func)
    if meta is None:
        return True
    
    return meta.get("ai_exposed", True)


def extract_docstring_summary(func: Callable) -> Optional[str]:
    """
    Extract the first line of a function's docstring as a summary.
    
    Args:
        func: The function to extract from
        
    Returns:
        First non-empty line of the docstring, or None
    """
    if not func.__doc__:
        return None
    
    lines = func.__doc__.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped:
            return stripped
    
    return None


def extract_docstring_description(func: Callable) -> Optional[str]:
    """
    Extract the full docstring as a description.
    
    Args:
        func: The function to extract from
        
    Returns:
        The full docstring (stripped), or None
    """
    if not func.__doc__:
        return None
    
    return func.__doc__.strip()


__all__ = [
    "action",
    "get_action_metadata",
    "is_action",
    "get_action_permissions",
    "is_action_ai_exposed",
    "extract_docstring_summary",
    "extract_docstring_description",
]
