"""
Vidyut Contrib Auth

Built-in, optional user authentication for Vidyut applications.

Usage:
    from vidyut.contrib.auth import User, get_current_user
    from vidyut.contrib.auth.hashing import hash_password, verify_password
    
    # Create a user
    user = await User.objects.create_user(
        email="user@example.com",
        password="secret123"
    )
    
    # Verify password
    if verify_password("secret123", user.hashed_password):
        print("Password matches!")
    
    # FastAPI integration
    from fastapi import FastAPI, Depends
    
    app = FastAPI()
    
    @app.get("/me")
    async def get_me(user = Depends(get_current_user)):
        return {"email": user.email}
"""

from vidyut.contrib.auth.models import AbstractUser, User
from vidyut.contrib.auth.manager import UserManager
from vidyut.contrib.auth.hashing import (
    hash_password,
    verify_password,
    make_random_password,
)

__all__ = [
    "AbstractUser",
    "User",
    "UserManager",
    "hash_password",
    "verify_password",
    "make_random_password",
]

# Conditional FastAPI imports
try:
    from vidyut.contrib.auth.fastapi import (
        get_current_user,
        get_current_active_user,
        require_auth,
        require_staff,
        require_superuser,
    )
    __all__.extend([
        "get_current_user",
        "get_current_active_user",
        "require_auth",
        "require_staff",
        "require_superuser",
    ])
except ImportError:
    pass  # FastAPI/Starlette not installed
