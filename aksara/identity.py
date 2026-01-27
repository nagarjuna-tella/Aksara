"""
Aksara Identity Protocol

Defines the standard interface for user objects in Aksara.
Permissions and other components depend on this protocol,
not on concrete User implementations.

Usage:
    from aksara.identity import AksaraUserProtocol
    
    # Check if object implements the protocol
    def check_permissions(user: AksaraUserProtocol):
        if user.is_authenticated and user.is_active:
            return True
        return False
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Protocol, runtime_checkable, Any, Optional


__all__ = [
    "AksaraUserProtocol",
    "AnonymousUser",
]


@runtime_checkable
class AksaraUserProtocol(Protocol):
    """
    Protocol defining the interface for Aksara user objects.
    
    Any user model used with Aksara permissions should implement
    this protocol. The built-in User and AbstractUser classes
    implement this protocol.
    
    Attributes:
        id: Unique identifier for the user.
        is_active: Whether the user account is active.
        is_staff: Whether the user has staff/admin access.
        is_superuser: Whether the user has superuser privileges.
        is_authenticated: Whether the user is authenticated (not anonymous).
    
    Usage:
        from aksara.identity import AksaraUserProtocol
        
        class MyCustomUser:
            id: int
            is_active: bool = True
            is_staff: bool = False
            is_superuser: bool = False
            
            @property
            def is_authenticated(self) -> bool:
                return True
        
        # MyCustomUser implements AksaraUserProtocol
        user = MyCustomUser()
        assert isinstance(user, AksaraUserProtocol)
    """
    
    @property
    @abstractmethod
    def id(self) -> Any:
        """Unique identifier for the user."""
        ...
    
    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Whether the user account is active."""
        ...
    
    @property
    @abstractmethod
    def is_staff(self) -> bool:
        """Whether the user has staff/admin access."""
        ...
    
    @property
    @abstractmethod
    def is_superuser(self) -> bool:
        """Whether the user has superuser privileges."""
        ...
    
    @property
    @abstractmethod
    def is_authenticated(self) -> bool:
        """Whether the user is authenticated (not anonymous)."""
        ...


class AnonymousUser:
    """
    Represents an unauthenticated/anonymous user.
    
    Used as a placeholder when no user is authenticated.
    Implements AksaraUserProtocol with default values.
    
    Usage:
        from aksara.identity import AnonymousUser
        
        user = AnonymousUser()
        assert not user.is_authenticated
        assert not user.is_active
    """
    
    __slots__ = ()
    
    @property
    def id(self) -> None:
        """Anonymous users have no ID."""
        return None
    
    @property
    def is_active(self) -> bool:
        """Anonymous users are not active."""
        return False
    
    @property
    def is_staff(self) -> bool:
        """Anonymous users are not staff."""
        return False
    
    @property
    def is_superuser(self) -> bool:
        """Anonymous users are not superusers."""
        return False
    
    @property
    def is_authenticated(self) -> bool:
        """Anonymous users are not authenticated."""
        return False
    
    def __str__(self) -> str:
        return "AnonymousUser"
    
    def __repr__(self) -> str:
        return "AnonymousUser()"
    
    def __eq__(self, other: object) -> bool:
        return isinstance(other, AnonymousUser)
    
    def __hash__(self) -> int:
        return hash(type(self))
    
    def __bool__(self) -> bool:
        """Anonymous users are falsy."""
        return False


def get_user_from_request(request: Any) -> Optional[AksaraUserProtocol]:
    """
    Extract user from a request object.
    
    Checks common locations for user objects:
    - request.state.user (Starlette/FastAPI)
    - request.user (Django-style)
    
    Returns:
        User object or None if not found.
    """
    # Check Starlette/FastAPI style
    if hasattr(request, "state") and hasattr(request.state, "user"):
        return request.state.user
    
    # Check Django style
    if hasattr(request, "user"):
        return request.user
    
    return None
