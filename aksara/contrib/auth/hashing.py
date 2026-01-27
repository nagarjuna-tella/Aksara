"""
Password Hashing Utilities

Secure password hashing using bcrypt.
"""

import secrets
import string

import bcrypt


__all__ = [
    "hash_password",
    "verify_password",
    "make_random_password",
]


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
        password.encode("utf-8"),
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
            password.encode("utf-8"),
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
