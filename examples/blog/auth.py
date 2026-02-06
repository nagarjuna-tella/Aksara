"""
Blog Example - Auth (v0.5.8)

Simple header-based authentication using X-API-Key.
Demonstrates a minimal auth pattern for Aksara APIs.

Usage:
    # Set API key in settings.py
    BLOG_API_KEY = os.getenv("BLOG_API_KEY", "dev-blog-key")
    
    # Use dependency in routes
    from .auth import require_api_key
    
Configuration:
    Set BLOG_API_KEY environment variable in production.
"""

from fastapi import HTTPException, Request, Depends
from fastapi.security import APIKeyHeader
from typing import Optional
import os


# API key header name
API_KEY_HEADER = "X-API-Key"

# Get API key from environment (default for development)
BLOG_API_KEY = os.getenv("BLOG_API_KEY", "dev-blog-key")

# FastAPI security scheme
api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


async def get_api_key(api_key: Optional[str] = Depends(api_key_header)) -> str:
    """
    Extract and validate API key from request header.
    
    Returns the API key if valid, raises 401 if invalid/missing.
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    if api_key != BLOG_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return api_key


async def require_api_key(request: Request) -> str:
    """
    FastAPI dependency for requiring API key authentication.
    
    Usage in ViewSet or route:
        from .auth import require_api_key
        
        # Apply to all routes via router
        router = APIRouter(dependencies=[Depends(require_api_key)])
        
        # Or apply to specific endpoint
        @app.get("/protected", dependencies=[Depends(require_api_key)])
        async def protected_endpoint():
            ...
    """
    api_key = request.headers.get(API_KEY_HEADER)
    
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    if api_key != BLOG_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return api_key


def verify_api_key(api_key: str) -> bool:
    """
    Verify an API key without raising exceptions.
    
    Returns True if valid, False otherwise.
    Useful for optional auth or logging.
    """
    return api_key == BLOG_API_KEY
