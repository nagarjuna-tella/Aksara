"""
Application Settings (v0.5.5)

Demonstrates how to configure Aksara using the settings system.
Settings are loaded from environment variables with sensible defaults.

Available Endpoints (when running):
    - API Docs: http://localhost:8000/docs
    - Admin: http://localhost:8000/admin (debug mode)
    - Studio: http://localhost:8000/studio/ui
    - AI Tools: http://localhost:8000/ai/tools
"""

import os
from aksara import configure

# =============================================================================
# Configure Aksara
# =============================================================================
# 
# Option 1: Environment variables (recommended for production)
#   DATABASE_URL or AKSARA_DATABASE_URL
#   AKSARA_DEBUG=true
#   AKSARA_POOL_SIZE=20
#
# Option 2: Explicit configuration (useful for development)
#   Call configure() with your settings
#
# =============================================================================

# Get database URL from environment with a development default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv(
        "AKSARA_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/aksara_example"
    )
)

# Debug mode from environment
DEBUG = os.getenv("AKSARA_DEBUG", "true").lower() in ("true", "1", "yes")

# Configure Aksara with our settings
configure(
    database_url=DATABASE_URL,
    debug=DEBUG,
    pool_min_size=5,
    pool_max_size=20,
    migrations_dir="migrations",
    # AI Mode (v0.4.0+)
    ai_enabled=True,
    mcp_enabled=True,
    # Studio (v0.5.0+) - enabled by default
    enable_studio=True,
    studio_ui_enabled=True,
)

# =============================================================================
# App-specific settings (non-Aksara)
# =============================================================================

APP_NAME = "Aksara Example App"
APP_VERSION = "dev"  # Example app version (not tied to framework version)
APP_DESCRIPTION = "Demo application using Aksara async ORM"

# CORS settings (if needed)
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# =============================================================================
# Using Settings
# =============================================================================
# After calling configure(), import settings from aksara:
#
#   from aksara import settings
#   print(settings.database_url)  # Your configured URL
#   print(settings.debug)         # True/False
#
# =============================================================================
