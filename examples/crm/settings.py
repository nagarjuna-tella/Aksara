"""
CRM Example - Settings (v0.5.8)

Configuration for the CRM example app.
Includes API key auth, pagination defaults, and AI mode settings.
"""

import os
from aksara import configure

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/aksara_crm"
)

DEBUG = os.getenv("AKSARA_DEBUG", "true").lower() in ("true", "1", "yes")

# =============================================================================
# Auth Configuration (v0.5.8)
# =============================================================================
# Simple API key authentication for the CRM API.
# In production, set CRM_API_KEY environment variable to a secure value.
CRM_API_KEY = os.getenv("CRM_API_KEY", "dev-crm-key")

# =============================================================================
# Pagination Defaults (v0.5.8)
# =============================================================================
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100

configure(
    database_url=DATABASE_URL,
    debug=DEBUG,
    pool_min_size=5,
    pool_max_size=20,
    migrations_dir="migrations",
    apps=["examples.crm"],
    enable_studio=True,
    ai_enabled=True,
)

from aksara import settings  # noqa: E402
