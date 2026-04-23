"""
Aksara Contrib Auth

Built-in, optional user authentication for Aksara applications.

Usage:
    from aksara.contrib.auth import User, get_current_user
    from aksara.contrib.auth.hashing import hash_password, verify_password
    
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

from aksara.contrib.auth.models import AbstractUser, User
from aksara.contrib.auth.manager import UserManager
from aksara.contrib.auth.hashing import (
    hash_password,
    verify_password,
    make_random_password,
)
from aksara.contrib.auth.session import (
    cleanup_expired_sessions,
    authenticate,
    create_session_token,
    get_user_from_session_token,
    invalidate_session_token,
)

__all__ = [
    "AbstractUser",
    "User",
    "UserManager",
    "hash_password",
    "verify_password",
    "make_random_password",
    "authenticate",
    "cleanup_expired_sessions",
    "create_session_token",
    "get_user_from_session_token",
    "invalidate_session_token",
]

# Conditional FastAPI imports
try:
    from aksara.contrib.auth.fastapi import (
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
