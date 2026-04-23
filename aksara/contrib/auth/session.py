"""
Session Management for Aksara Auth

Provides session-based authentication for admin and other cookie-based auth needs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
from typing import Any, Optional

SESSIONS_TABLE = "aksara_sessions"


def _parse_affected_rows(result: Any) -> int:
    """Parse row counts from asyncpg-style status strings."""
    if isinstance(result, str):
        parts = result.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return int(parts[1])
    return 0


async def _ensure_sessions_table(db: Any) -> None:
    """Create the session table if it does not already exist."""
    if db is None:
        return

    await db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SESSIONS_TABLE} (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL
        )
        """
    )


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
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    await db.execute(
        f"INSERT INTO {SESSIONS_TABLE} (token, user_id, expires_at) VALUES ($1, $2, $3)",
        token,
        str(user.id),
        expires_at,
    )
    
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

    session = await db.fetchrow(
        f"SELECT user_id, expires_at FROM {SESSIONS_TABLE} WHERE token = $1",
        token,
    )
    if session is None:
        return None

    if datetime.now(timezone.utc) > session["expires_at"]:
        await invalidate_session_token(db, token)
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
    await db.execute(f"DELETE FROM {SESSIONS_TABLE} WHERE token = $1", token)


async def cleanup_expired_sessions(db: Any) -> int:
    """
    Clean up expired sessions from the database.
    
    Returns:
        Number of sessions cleaned up
    """
    result = await db.execute(f"DELETE FROM {SESSIONS_TABLE} WHERE expires_at < NOW()")
    return _parse_affected_rows(result)
