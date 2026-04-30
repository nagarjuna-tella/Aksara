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

from . import settings as _  # noqa: F401
from . import models  # noqa: F401
from . import admin  # noqa: F401

from aksara import Aksara, __version__ as aksara_version
from aksara.middleware.request_id import RequestIdMiddleware
from aksara.middleware.logging import LoggingMiddleware
from fastapi.responses import HTMLResponse

from .urls import register_routes
from .settings import settings, DATABASE_URL, DEBUG


app = Aksara(
    database_url=DATABASE_URL,
    title="CRM API",
    description="A simple CRM backend powered by Aksara",
    version="0.1.0",
    debug=DEBUG,
    enable_admin=True,
    middlewares=[
        (RequestIdMiddleware, {}),
        (LoggingMiddleware, {"log_request_body": False}),
    ],
)

register_routes(app)


WELCOME_HTML = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CRM API - Aksara</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #e4e4e7;
        }}
        .container {{
            text-align: center;
            padding: 2rem;
            max-width: 600px;
        }}
        .logo {{ font-size: 3rem; margin-bottom: 1rem; }}
        h1 {{ font-size: 2rem; margin-bottom: 0.5rem; color: #fbbf24; }}
        .version {{ color: #9ca3af; font-size: 0.9rem; margin-bottom: 1.5rem; }}
        .success {{ color: #4ade80; font-size: 1.1rem; margin-bottom: 2rem; }}
        .links {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            margin-bottom: 2rem;
        }}
        .links a {{
            background: rgba(255,255,255,0.1);
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            color: #e4e4e7;
            text-decoration: none;
            transition: background 0.2s;
        }}
        .links a:hover {{ background: rgba(255,255,255,0.2); }}
        .links a span {{ color: #9ca3af; font-size: 0.85rem; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">💼</div>
        <h1>CRM API</h1>
        <p class="version">Powered by Aksara {aksara_version}</p>
        <p class="success">Your CRM backend is running 🚀</p>
        <div class="links">
            <a href="/admin/">Admin Panel <span>→ Manage customers & deals</span></a>
            <a href="/studio/ui">Studio <span>→ Interactive dashboard</span></a>
            <a href="/api/customers/">Customers API <span>→ /api/customers/</span></a>
            <a href="/api/deals/">Deals API <span>→ /api/deals/</span></a>
            <a href="/api/deals/pipeline/">Pipeline <span>→ Sales pipeline summary</span></a>
            <a href="/docs">API Docs <span>→ OpenAPI / Swagger</span></a>
        </div>
    </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def welcome():
    """Welcome page."""
    return WELCOME_HTML


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "app": "crm"}
