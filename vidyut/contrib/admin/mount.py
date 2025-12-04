"""
Admin Mount Helper

Helper function to mount admin routes on a FastAPI/Vidyut app.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI


def include_admin(app: "FastAPI", prefix: str = "/admin") -> None:
    """
    Mount the admin interface on a FastAPI/Vidyut application.
    
    Args:
        app: The FastAPI/Vidyut application instance
        prefix: URL prefix for admin (default: "/admin")
        
    Example:
        from vidyut import Vidyut
        from vidyut.contrib.admin import include_admin
        
        app = Vidyut(database_url="...")
        include_admin(app)  # Mounts at /admin/
        
        # Or with custom prefix
        include_admin(app, prefix="/dashboard")
    """
    from vidyut.contrib.admin.urls import router as admin_router
    
    app.include_router(admin_router, prefix=prefix)
