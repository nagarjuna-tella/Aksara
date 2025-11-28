"""
⚡ Vidyut - Async Postgres ORM for FastAPI

A lightweight, async-native ORM designed specifically for PostgreSQL and FastAPI.
"""

from vidyut.model.base import Model
from vidyut import fields
from vidyut.db import Database
from vidyut.registry import ModelRegistry
from vidyut.manager import DoesNotExist, MultipleObjectsReturned

# Re-export FastAPI components with Vidyut enhancements
from vidyut.app import (
    Vidyut,
    FastAPI,
    APIRouter,
    Request,
    Response,
    HTTPException,
    Depends,
    Query,
    Path,
    Header,
    File,
    Form,
    UploadFile,
    BackgroundTasks,
    WebSocket,
    status,
    JSONResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    FileResponse,
    StreamingResponse,
    StaticFiles,
    Jinja2Templates,
    Middleware,
)

__version__ = "0.1.0"
__all__ = [
    # Vidyut ORM
    "Model",
    "fields", 
    "Database",
    "ModelRegistry",
    "DoesNotExist",
    "MultipleObjectsReturned",
    # Vidyut App (enhanced FastAPI)
    "Vidyut",
    # FastAPI re-exports
    "FastAPI",
    "APIRouter",
    "Request",
    "Response",
    "HTTPException",
    "Depends",
    "Query",
    "Path",
    "Header",
    "File",
    "Form",
    "UploadFile",
    "BackgroundTasks",
    "WebSocket",
    "status",
    "JSONResponse",
    "HTMLResponse",
    "PlainTextResponse",
    "RedirectResponse",
    "FileResponse",
    "StreamingResponse",
    "StaticFiles",
    "Jinja2Templates",
    "Middleware",
]
