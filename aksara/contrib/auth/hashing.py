"""
Password Hashing Utilities

Secure password hashing using bcrypt.
"""

import hashlib
import secrets
import string

import bcrypt


__all__ = [
    "hash_password",
    "verify_password",
    "make_random_password",
]

# Pre-computed dummy hash for timing-safe user-not-found responses.
# authenticate() functions call verify_password against this when the
# user doesn't exist, so the response time is the same as for a real
# (wrong) password attempt.
_DUMMY_HASH = "$2b$12$LJ3m4ys1LaQvVhIxnHVawe3rvyAMwBSJlNQoOEgJr1VdDnCjkh4vy"


def _prehash(password: str) -> bytes:
    """
    SHA-256 pre-hash to work around bcrypt's 72-byte truncation.

    Bcrypt silently ignores everything after byte 72.  By first hashing
    through SHA-256 we compress any-length password into a fixed 64-char
    hex string, which fits comfortably inside the 72-byte window while
    preserving full entropy of the original password.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Bcrypt hash string
        
    Example:
        hashed = hash_password("secret123")
        # Returns something like: $2b$12$...
    """
    return bcrypt.hashpw(
        _prehash(password),
        bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against a bcrypt hash.
    
    Args:
        password: Plain text password to check
        hashed: Bcrypt hash to check against
        
    Returns:
        True if password matches, False otherwise
        
    Example:
        if verify_password("secret123", user.hashed_password):
            print("Login successful!")
    """
    try:
        return bcrypt.checkpw(
            _prehash(password),
            hashed.encode("utf-8")
        )
    except Exception:
        return False


def make_random_password(length: int = 12) -> str:
    """
    Generate a cryptographically secure random password.
    
    Args:
        length: Password length (default 12)
        
    Returns:
        Random password string with letters, digits, and punctuation
        
    Example:
        password = make_random_password()  # "xK9#mL2$pQ7!"
        password = make_random_password(20)  # Longer password
    """
    # Use letters, digits, and some safe punctuation
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))
