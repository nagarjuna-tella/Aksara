"""
User Manager

Custom manager for User model with helper methods.
"""

from __future__ import annotations

from typing import Any, Optional, Type, TYPE_CHECKING

from aksara.manager import Manager
from aksara.contrib.auth.hashing import hash_password

if TYPE_CHECKING:
    from aksara.contrib.auth.models import AbstractUser


class UserManager(Manager):
    """
    Manager for User models with authentication helpers.
    
    Provides:
    - create_user(): Create a regular user with hashed password
    - create_superuser(): Create an admin user
    - get_by_email(): Lookup user by email
    - authenticate(): Verify email/password and return user
    
    Usage:
        # Create a user
        user = await User.objects.create_user(
            email="user@example.com",
            password="secret123"
        )
        
        # Authenticate
        user = await User.objects.authenticate(
            email="user@example.com",
            password="secret123"
        )
    """
    
    async def create_user(
        self,
        email: str,
        password: str,
        is_active: bool = True,
        is_staff: bool = False,
        is_superuser: bool = False,
        **extra_fields: Any,
    ) -> "AbstractUser":
        """
        Create and save a new user with a hashed password.
        
        Args:
            email: User's email address
            password: Plain text password (will be hashed)
            is_active: Whether user can log in (default True)
            is_staff: Whether user has staff access (default False)
            is_superuser: Whether user has all permissions (default False)
            **extra_fields: Additional fields to set on the user
            
        Returns:
            The created User instance
            
        Example:
            user = await User.objects.create_user(
                email="user@example.com",
                password="secret123",
                metadata={"name": "John Doe"}
            )
        """
        hashed = hash_password(password)
        
        return await self.create(
            email=email.lower().strip(),
            hashed_password=hashed,
            is_active=is_active,
            is_staff=is_staff,
            is_superuser=is_superuser,
            **extra_fields,
        )
    
    async def create_superuser(
        self,
        email: str,
        password: str,
        **extra_fields: Any,
    ) -> "AbstractUser":
        """
        Create and save a superuser with all permissions.
        
        Args:
            email: User's email address
            password: Plain text password (will be hashed)
            **extra_fields: Additional fields to set on the user
            
        Returns:
            The created User instance with is_staff=True, is_superuser=True
            
        Example:
            admin = await User.objects.create_superuser(
                email="admin@example.com",
                password="admin123"
            )
        """
        return await self.create_user(
            email=email,
            password=password,
            is_active=True,
            is_staff=True,
            is_superuser=True,
            **extra_fields,
        )
    
    async def get_by_email(self, email: str) -> Optional["AbstractUser"]:
        """
        Get a user by their email address.
        
        Args:
            email: Email address to lookup
            
        Returns:
            User instance or None if not found
            
        Example:
            user = await User.objects.get_by_email("user@example.com")
        """
        try:
            return await self.get(email=email.lower().strip())
        except Exception:
            return None
    
    async def authenticate(
        self,
        email: str,
        password: str,
    ) -> Optional["AbstractUser"]:
        """
        Authenticate a user by email and password.
        
        Args:
            email: User's email address
            password: Plain text password to verify
            
        Returns:
            User instance if credentials are valid, None otherwise
            
        Example:
            user = await User.objects.authenticate(
                email="user@example.com",
                password="secret123"
            )
            if user:
                print("Login successful!")
            else:
                print("Invalid credentials")
        """
        from aksara.contrib.auth.hashing import verify_password
        
        user = await self.get_by_email(email)
        if user is None:
            return None
        
        if not user.is_active:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        return user
