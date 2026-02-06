"""
Aksara Studio FastAPI Endpoints

HTTP endpoints for Studio IDE integration.

v0.5.0 Endpoints:
- GET /studio/handshake - Complete project handshake for Studio
- GET /studio/context/summary - Lightweight schema summary
- GET /studio/health - Simple health check with DB status
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from aksara.studio.models import (
    StudioContextSummary,
    StudioHandshake,
    StudioHealthResponse,
)
from aksara.studio.utils import (
    build_context_summary,
    build_health_response,
    build_studio_handshake,
)


router = APIRouter(tags=["Studio"])


@router.get("/studio/handshake", response_model=StudioHandshake)
async def studio_handshake(request: Request) -> StudioHandshake:
    """
    Complete handshake endpoint for Studio IDE.
    
    Returns:
        StudioHandshake with:
        - Project metadata (name, version, aksara_version, python_version)
        - Database status (connected, pool info, latency)
        - Available capabilities (read, write, ai_tools, etc.)
        - Checksums for caching (schema, migrations, settings, routes)
        - API endpoint URLs
    
    Example response:
        {
            "protocol_version": "1.0",
            "timestamp": "2024-01-15T10:30:00Z",
            "project": {
                "name": "My App",
                "version": "1.0.0",
                "aksara_version": "0.5.0",
                "python_version": "3.11.5",
                "debug_mode": true,
                "environment": "development"
            },
            "database": {
                "connected": true,
                "dialect": "postgresql",
                "pool_size": 10,
                "pool_available": 8
            },
            "capabilities": ["read_schema", "read_data", "ai_tools", ...],
            "checksums": {
                "schema_checksum": "abc123...",
                "migrations_checksum": "def456...",
                ...
            },
            "endpoints": {
                "context_full": "/ai/context/full",
                "tools": "/ai/tools",
                ...
            }
        }
    """
    return await build_studio_handshake(request.app)


@router.get("/studio/context/summary", response_model=StudioContextSummary)
async def studio_context_summary(request: Request) -> StudioContextSummary:
    """
    Lightweight context summary endpoint.
    
    Use this for quick status checks without transferring full schema.
    For full context, use GET /ai/context/full instead.
    
    Returns:
        StudioContextSummary with:
        - Counts (models, viewsets, routes, ai_tools, migrations)
        - Model list with name, table_name, field_count
        - Checksums for cache invalidation
    
    Example response:
        {
            "model_count": 5,
            "viewset_count": 3,
            "route_count": 25,
            "ai_tool_count": 15,
            "migration_count": 10,
            "pending_migrations": 0,
            "models": [
                {
                    "name": "User",
                    "table_name": "users",
                    "field_count": 6,
                    "has_relations": true
                },
                ...
            ],
            "checksums": { ... }
        }
    """
    return await build_context_summary(request.app)


@router.get("/studio/health", response_model=StudioHealthResponse)
async def studio_health(request: Request) -> StudioHealthResponse:
    """
    Simple health check endpoint for Studio.
    
    Returns:
        StudioHealthResponse with:
        - status: "healthy" or "degraded"
        - aksara_version
        - database status
        - timestamp
    
    Example response:
        {
            "status": "healthy",
            "aksara_version": "0.5.0",
            "database": {
                "connected": true,
                "dialect": "postgresql",
                "pool_size": 10,
                "pool_available": 8
            },
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    return await build_health_response(request.app)
