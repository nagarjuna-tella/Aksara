"""
Session Management for Aksara Auth

Provides session-based authentication for admin and other cookie-based auth needs.
"""

from __future__ import annotations

import secrets
import hashlib
from typing import TYPE_CHECKING, Optional, Any
from datetime import datetime, timedelta, timezone

if TYPE_CHECKING:
    from asyncpg import Connection


# In-memory session store (simple implementation)
# For production, consider using Redis or database-backed sessions
_sessions: dict[str, dict] = {}


async def authenticate(
    db: Any,
    username: str,
    password: str,
) -> Optional[Any]:
    """
    Authenticate a user by username/email and password.
    
    Args:
        db: Database connection pool
        username: Username or email address
        password: Plain text password
        
    Returns:
        User instance if credentials are valid, None otherwise
    """
    from aksara.contrib.auth.models import User
    from aksara.contrib.auth.hashing import verify_password
    
    # Try to find user by email (case-insensitive)
    username_lower = username.lower().strip()
    
    try:
        # First try email
        user = await User.objects.filter(email=username_lower).first()
        
        # If not found by email, try username if the model has it
        if user is None and hasattr(User, 'username'):
            user = await User.objects.filter(username=username_lower).first()
        
        if user is None:
            return None
        
        if not user.is_active:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        return user
        
    except Exception:
        return None


async def create_session_token(
    db: Any,
    user: Any,
    expires_in: int = 60 * 60 * 24 * 7,  # 7 days
) -> str:
    """
    Create a session token for a user.
    
    Args:
        db: Database connection pool (for future DB-backed sessions)
        user: User instance
        expires_in: Token expiry in seconds (default 7 days)
        
    Returns:
        Session token string
    """
    # Generate a secure random token
    token = secrets.token_urlsafe(32)
    
    # Store session (in-memory for now)
    _sessions[token] = {
        "user_id": str(user.id),
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
    }
    
    return token


async def get_user_from_session_token(
    db: Any,
    token: str,
) -> Optional[Any]:
    """
    Get user from session token.
    
    Args:
        db: Database connection pool
        token: Session token
        
    Returns:
        User instance if valid token, None otherwise
    """
    from aksara.contrib.auth.models import User
    
    session = _sessions.get(token)
    if session is None:
        return None
    
    # Check expiry
    if datetime.now(timezone.utc) > session["expires_at"]:
        # Token expired, clean it up
        del _sessions[token]
        return None
    
    try:
        user = await User.objects.get(id=session["user_id"])
        if not user.is_active:
            return None
        return user
    except Exception:
        return None


async def invalidate_session_token(
    db: Any,
    token: str,
) -> None:
    """
    Invalidate/delete a session token.
    
    Args:
        db: Database connection pool (for future DB-backed sessions)
        token: Session token to invalidate
    """
    _sessions.pop(token, None)


def cleanup_expired_sessions() -> int:
    """
    Clean up expired sessions from memory.
    
    Returns:
        Number of sessions cleaned up
    """
    now = datetime.now(timezone.utc)
    expired = [
        token for token, session in _sessions.items()
        if now > session["expires_at"]
    ]
    for token in expired:
        del _sessions[token]
    return len(expired)
