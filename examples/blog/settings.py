"""
Blog Example - Settings

Configuration for the blog example app.
"""

import os
from aksara import configure

# Database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/aksara_blog"
)

# Debug mode
DEBUG = os.getenv("AKSARA_DEBUG", "true").lower() in ("true", "1", "yes")

# Configure Aksara
configure(
    database_url=DATABASE_URL,
    debug=DEBUG,
    pool_min_size=5,
    pool_max_size=20,
    migrations_dir="migrations",
    apps=["examples.blog"],
    # Enable features
    enable_admin=True,
    enable_studio=True,
    AI_MODE_ENABLED=True,
)

# Access settings
from aksara import settings  # noqa: E402
