"""
Auth Models

AbstractUser and User models for authentication.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, ClassVar, TYPE_CHECKING

from vidyut import Model, fields

if TYPE_CHECKING:
    from vidyut.contrib.auth.manager import UserManager


class AbstractUser(Model):
    """
    Abstract base user model with common authentication fields.
    
    Provides:
    - email: Unique email address for login
    - hashed_password: Bcrypt-hashed password
    - is_active: Whether user can log in
    - is_staff: Whether user has admin access
    - is_superuser: Whether user has all permissions
    - metadata: Optional JSON for profile extensions
    
    Subclass this to add custom fields while keeping auth behavior.
    
    Example:
        class CustomUser(AbstractUser):
            __tablename__ = "custom_users"
            
            first_name = fields.String(max_length=100, nullable=True)
            last_name = fields.String(max_length=100, nullable=True)
    """
    
    __abstract__ = True
    
    # Authentication fields
    email = fields.Email(
        unique=True,
        nullable=False,
        ai_description="User's email address for login",
        ai_sensitive=True,
    )
    hashed_password = fields.String(
        max_length=255,
        nullable=False,
        ai_description="Bcrypt-hashed password (never expose)",
        ai_sensitive=True,
        ai_agent_writable=False,
    )
    
    # Status flags
    is_active = fields.Boolean(
        default=True,
        ai_description="Whether the user account is active",
    )
    is_staff = fields.Boolean(
        default=False,
        ai_description="Whether the user has admin/staff access",
    )
    is_superuser = fields.Boolean(
        default=False,
        ai_description="Whether the user has all permissions",
    )
    
    # Extensible profile data
    metadata = fields.JSON(
        nullable=True,
        ai_description="Additional user profile data",
    )
    
    class Meta:
        ai_agent_exposed = False  # Don't expose raw user data to AI by default
    
    @property
    def is_authenticated(self) -> bool:
        """
        Check if the user is authenticated.
        
        Always returns True for actual user instances.
        AnonymousUser returns False.
        """
        return True
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id} email={self.email}>"


class User(AbstractUser):
    """
    Default concrete user model for Vidyut applications.
    
    Use this for simple applications that don't need custom user fields.
    For custom fields, subclass AbstractUser instead.
    
    Usage:
        from vidyut.contrib.auth import User
        
        # Create a user
        user = await User.objects.create_user(
            email="user@example.com",
            password="secret123"
        )
        
        # Create a superuser
        admin = await User.objects.create_superuser(
            email="admin@example.com",
            password="admin123"
        )
        
        # Check authentication
        if user.is_authenticated:
            print(f"Logged in as {user.email}")
    """
    
    __tablename__ = "vidyut_users"
    
    class Meta:
        ai_agent_exposed = False
        ai_name = "User"
        ai_description = "Application user account"


# Attach UserManager after class definition to avoid circular imports
def _attach_user_manager():
    """Attach UserManager to User model."""
    from vidyut.contrib.auth.manager import UserManager
    User.objects = UserManager(User)

_attach_user_manager()
