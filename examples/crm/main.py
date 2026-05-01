"""
CRM Example - Main Application

A simple CRM backend with Aksara.

Quick Start:
    cd examples/crm
    aksara dbsetup
    aksara makemigrations --app examples.crm.models
    aksara migrate
    aksara dev

Endpoints:
    Welcome:    http://localhost:8000/
    API Docs:   http://localhost:8000/docs
    Admin:      http://localhost:8000/admin
    
    Customers:  http://localhost:8000/api/customers/
    Deals:      http://localhost:8000/api/deals/
    Pipeline:   http://localhost:8000/api/deals/pipeline/
"""

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
    title="CRM API",
    description="A simple CRM backend powered by Aksara",
    version="0.1.0",
    debug=DEBUG,
    enable_admin=True,
    middlewares=[
        (RequestIDMiddleware, {}),
        (LoggingMiddleware, {}),
    ],
)

register_routes(app)


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "app": "crm"}
