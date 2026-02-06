"""
Aksara Studio - Bridge for Aksara Studio IDE integration.

v0.5.0: Studio Core & Handshake

This module provides the Studio API endpoints and utilities for
integrating Aksara applications with Aksara Studio IDE.

Endpoints:
- GET /studio/handshake - Complete project handshake for Studio
- GET /studio/context/summary - Lightweight schema summary
- GET /studio/health - Simple health check with DB status

CLI:
- aksara studio handshake - Test handshake locally
- aksara studio url - Show Studio URLs
"""

from aksara.studio.models import (
    StudioHandshake,
    StudioCapability,
    StudioDatabaseStatus,
    StudioProjectInfo,
    StudioChecksums,
    StudioContextSummary,
    StudioHealthResponse,
)
from aksara.studio.utils import (
    build_studio_handshake,
    build_context_summary,
    build_health_response,
    compute_schema_checksum,
)
from aksara.studio.fastapi import router as studio_router

__all__ = [
    # Models
    "StudioHandshake",
    "StudioCapability",
    "StudioDatabaseStatus",
    "StudioProjectInfo",
    "StudioChecksums",
    "StudioContextSummary",
    "StudioHealthResponse",
    # Utils
    "build_studio_handshake",
    "build_context_summary",
    "build_health_response",
    "compute_schema_checksum",
    # Router
    "studio_router",
]
