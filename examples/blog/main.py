"""
Blog Example - Main Application

A complete blogging backend with Aksara.

Quick Start:
    cd examples/blog
    aksara dbsetup
    aksara makemigrations --app examples.blog.models
    aksara migrate
    aksara dev

Endpoints:
    Welcome:   http://localhost:8000/
    API Docs:  http://localhost:8000/docs
    Admin:     http://localhost:8000/admin
    Studio:    http://localhost:8000/studio/ui
    AI Tools:  http://localhost:8000/ai/tools
    
    Posts:     http://localhost:8000/api/posts/
    Comments:  http://localhost:8000/api/comments/
"""

# Import admin to register model admin classes (models are auto-loaded by Aksara)
from . import admin  # noqa: F401

from aksara import Aksara
from aksara.middleware.request_id import RequestIDMiddleware
from aksara.middleware.logging import LoggingMiddleware

from .urls import register_routes
from .settings import DATABASE_URL, DEBUG


# Create the Aksara app
# Aksara automatically provides: GET /, /docs, /redoc, /openapi.json
app = Aksara(
    database_url=DATABASE_URL,
    title="Blog API",
    description="A complete blogging backend powered by Aksara",
    version="0.1.0",
    debug=DEBUG,
    enable_admin=True,
    middlewares=[
        (RequestIDMiddleware, {}),
        (LoggingMiddleware, {}),
    ],
)

# Register routes
register_routes(app)


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "app": "blog"}
