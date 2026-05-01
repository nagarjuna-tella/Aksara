"""
Multitenant Example - Main Application

A minimal multi-tenant SaaS backend with Aksara.

Quick Start:
    cd examples/multitenant
    aksara dbsetup
    aksara makemigrations --app examples.multitenant.models
    aksara migrate
    aksara dev

Endpoints:
    Welcome:   http://localhost:8000/
    API Docs:  http://localhost:8000/docs
    Admin:     http://localhost:8000/admin
    
    Tenants:   http://localhost:8000/api/tenants/
    Users:     http://localhost:8000/api/users/ (requires tenant header)
    Projects:  http://localhost:8000/api/projects/ (requires tenant header)

Headers for tenant context:
    X-Tenant-ID: <uuid>
    X-Tenant-Slug: <slug>
"""

from . import admin  # noqa: F401

from aksara import Aksara
from aksara.middleware.request_id import RequestIDMiddleware
from aksara.middleware.logging import LoggingMiddleware

from .urls import register_routes
from .middleware import TenantMiddleware
from .settings import DATABASE_URL, DEBUG


# Create the Aksara app
# Aksara automatically provides: GET /, /docs, /redoc, /openapi.json
app = Aksara(
    database_url=DATABASE_URL,
    title="Multitenant API",
    description="A multi-tenant SaaS backend powered by Aksara",
    version="0.1.0",
    debug=DEBUG,
    enable_admin=True,
    middlewares=[
        (RequestIDMiddleware, {}),
        (LoggingMiddleware, {}),
    ],
)

# Add tenant middleware
app.add_middleware(TenantMiddleware)

# Register routes
register_routes(app)


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "app": "multitenant"}
