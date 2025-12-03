"""
FastAPI integration helpers for Vidyut authentication.

Provides FastAPI dependencies for user authentication.

Usage:
    from fastapi import FastAPI, Depends
    from vidyut.contrib.auth import get_current_user
    from vidyut.contrib.auth.models import User
    
    app = FastAPI()
    
    @app.get("/me")
    async def get_me(user: User = Depends(get_current_user)):
        if user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return {"email": user.email}
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Callable, Any

if TYPE_CHECKING:
    from starlette.requests import Request

# v0.3.13: Import user_id_var for context propagation
from vidyut.middleware.context import user_id_var


__all__ = [
    "get_current_user",
    "get_current_active_user",
    "require_auth",
    "require_staff",
    "require_superuser",
]


async def get_current_user(request: "Request") -> Optional[Any]:
    """
    FastAPI dependency to get the current authenticated user.
    
    Checks for user ID in:
    1. request.state.user (if set by middleware)
    2. X-User-Id header
    
    Returns:
        User instance or None if not authenticated.
    
    Usage:
        @app.get("/profile")
        async def profile(user = Depends(get_current_user)):
            if user is None:
                raise HTTPException(status_code=401)
            return {"email": user.email}
    """
    # Check if user already attached by middleware
    if hasattr(request.state, "user") and request.state.user is not None:
        # v0.3.13: Set user_id_var for logging/context propagation
        user_id_var.set(str(request.state.user.id))
        return request.state.user
    
    # Check for user ID header
    user_id = request.headers.get("X-User-Id")
    if user_id is None:
        return None
    
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return None
    
    # Import here to avoid circular imports
    from vidyut.contrib.auth.models import User
    
    try:
        user = await User.objects.get(id=user_id)
        # Cache on request state
        request.state.user = user
        # v0.3.13: Set user_id_var for logging/context propagation
        user_id_var.set(str(user.id))
        return user
    except Exception:
        return None


async def get_current_active_user(request: "Request") -> Optional[Any]:
    """
    FastAPI dependency to get the current active user.
    
    Returns None if user is not authenticated or is inactive.
    
    Usage:
        @app.get("/dashboard")
        async def dashboard(user = Depends(get_current_active_user)):
            if user is None:
                raise HTTPException(status_code=401)
            return {"email": user.email}
    """
    user = await get_current_user(request)
    if user is None:
        return None
    
    if not getattr(user, "is_active", True):
        return None
    
    return user


def require_auth(
    detail: str = "Not authenticated",
    status_code: int = 401,
) -> Callable:
    """
    Create a FastAPI dependency that requires authentication.
    
    Raises HTTPException if user is not authenticated.
    
    Args:
        detail: Error message for unauthenticated requests.
        status_code: HTTP status code (default 401).
    
    Returns:
        FastAPI dependency function.
    
    Usage:
        @app.get("/protected")
        async def protected(user = Depends(require_auth())):
            return {"email": user.email}
    """
    async def dependency(request: "Request"):
        from starlette.exceptions import HTTPException
        
        user = await get_current_active_user(request)
        if user is None:
            raise HTTPException(status_code=status_code, detail=detail)
        return user
    
    return dependency


def require_staff(
    detail: str = "Staff access required",
    status_code: int = 403,
) -> Callable:
    """
    Create a FastAPI dependency that requires staff access.
    
    Raises HTTPException if user is not staff.
    
    Usage:
        @app.get("/admin/users")
        async def list_users(user = Depends(require_staff())):
            return await User.objects.all()
    """
    async def dependency(request: "Request"):
        from starlette.exceptions import HTTPException
        
        user = await get_current_active_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        if not getattr(user, "is_staff", False):
            raise HTTPException(status_code=status_code, detail=detail)
        
        return user
    
    return dependency


def require_superuser(
    detail: str = "Superuser access required",
    status_code: int = 403,
) -> Callable:
    """
    Create a FastAPI dependency that requires superuser access.
    
    Raises HTTPException if user is not a superuser.
    
    Usage:
        @app.delete("/admin/users/{id}")
        async def delete_user(id: int, user = Depends(require_superuser())):
            await User.objects.filter(id=id).delete()
    """
    async def dependency(request: "Request"):
        from starlette.exceptions import HTTPException
        
        user = await get_current_active_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        if not getattr(user, "is_superuser", False):
            raise HTTPException(status_code=status_code, detail=detail)
        
        return user
    
    return dependency
