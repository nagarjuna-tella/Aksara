"""
Application Settings (v0.2)

Demonstrates how to configure Vidyut using the settings system.
Settings are loaded from environment variables with sensible defaults.
"""

import os
from vidyut import configure

# =============================================================================
# Configure Vidyut
# =============================================================================
# 
# Option 1: Environment variables (recommended for production)
#   DATABASE_URL or VIDYUT_DATABASE_URL
#   VIDYUT_DEBUG=true
#   VIDYUT_POOL_SIZE=20
#
# Option 2: Explicit configuration (useful for development)
#   Call configure() with your settings
#
# =============================================================================

# Get database URL from environment with a development default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv(
        "VIDYUT_DATABASE_URL",
        "postgresql://postgres:qwertyuiop@localhost:5432/vidyut_example"
    )
)

# Debug mode from environment
DEBUG = os.getenv("VIDYUT_DEBUG", "false").lower() in ("true", "1", "yes")

# Configure Vidyut with our settings
configure(
    database_url=DATABASE_URL,
    debug=DEBUG,
    pool_min_size=5,
    pool_max_size=20,
    migrations_dir="migrations",
    ai_enabled=True,
    mcp_enabled=False,
)

# =============================================================================
# App-specific settings (non-Vidyut)
# =============================================================================

APP_NAME = "Vidyut Example App"
APP_VERSION = "0.2.0"
APP_DESCRIPTION = "Demo application using Vidyut async ORM"

# CORS settings (if needed)
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# =============================================================================
# Using Settings
# =============================================================================
# After calling configure(), import settings from vidyut:
#
#   from vidyut import settings
#   print(settings.database_url)  # Your configured URL
#   print(settings.debug)         # True/False
#
# =============================================================================
