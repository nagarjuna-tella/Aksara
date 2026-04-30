"""
Blog Example - Settings (v0.5.8)

Configuration for the blog example app.
Includes API key auth, pagination defaults, and AI mode settings.
"""

import os
from aksara import configure

# Database URL from environment (set via `aksara dbsetup` or .env)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Run `aksara dbsetup` or add it to .env"
    )

# Debug mode
DEBUG = os.getenv("AKSARA_DEBUG", "true").lower() in ("true", "1", "yes")

# =============================================================================
# Auth Configuration (v0.5.8)
# =============================================================================
# Simple API key authentication for the Blog API.
# In production, set BLOG_API_KEY environment variable to a secure value.
BLOG_API_KEY = os.getenv("BLOG_API_KEY", "dev-blog-key")

# =============================================================================
# Pagination Defaults (v0.5.8)
# =============================================================================
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100

# Configure Aksara
configure(
    database_url=DATABASE_URL,
    debug=DEBUG,
    pool_min_size=5,
    pool_max_size=20,
    migrations_dir="migrations",
    apps=["examples.blog"],
    # Enable features
    enable_studio=True,
    ai_enabled=True,
)

# Access settings
from aksara import settings  # noqa: E402
