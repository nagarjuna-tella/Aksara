"""
Multitenant Example - Settings
"""

import os
from aksara import configure

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Run `aksara dbsetup` or add it to .env"
    )

DEBUG = os.getenv("AKSARA_DEBUG", "true").lower() in ("true", "1", "yes")

configure(
    database_url=DATABASE_URL,
    debug=DEBUG,
    pool_min_size=5,
    pool_max_size=20,
    migrations_dir="migrations",
    apps=["examples.multitenant"],
    enable_admin=True,
    enable_studio=True,
    ai_enabled=True,
)

from aksara import settings  # noqa: E402
