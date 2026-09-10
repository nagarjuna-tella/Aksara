"""Validated production configuration for the support desk reference app."""

from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from aksara import configure

PACKAGE_ROOT = Path(__file__).resolve().parent
ENVIRONMENT = os.getenv("AKSARA_ENV", "development").strip().lower()
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("AKSARA_DATABASE_URL")


def _require_production_configuration() -> None:
    """Fail fast when a production process is missing security-critical config."""
    if ENVIRONMENT != "production":
        return

    missing = [
        name
        for name in (
            "DATABASE_URL",
            "SUPPORT_DESK_TENANT_A_ID",
            "SUPPORT_DESK_TENANT_B_ID",
            "SUPPORT_DESK_TENANT_A_TOKEN",
            "SUPPORT_DESK_TENANT_B_TOKEN",
            "SUPPORT_DESK_MCP_TOKEN",
            "SUPPORT_DESK_MCP_TOKEN_EXPIRES_AT",
            "SUPPORT_DESK_MCP_AUDIENCE",
        )
        if not os.getenv(name)
    ]
    if missing:
        raise RuntimeError(
            "Support desk production configuration is incomplete: "
            + ", ".join(sorted(missing))
        )

    assert DATABASE_URL is not None
    parsed = urlsplit(DATABASE_URL)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname or not parsed.path.strip("/"):
        raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL")

    for name in ("SUPPORT_DESK_TENANT_A_ID", "SUPPORT_DESK_TENANT_B_ID"):
        try:
            UUID(os.environ[name])
        except ValueError as exc:
            raise RuntimeError(f"{name} must be a UUID") from exc

    secret_names = (
        "SUPPORT_DESK_TENANT_A_TOKEN",
        "SUPPORT_DESK_TENANT_B_TOKEN",
        "SUPPORT_DESK_MCP_TOKEN",
    )
    secrets = [os.environ[name] for name in secret_names]
    if any(len(secret) < 24 for secret in secrets):
        raise RuntimeError("Support desk bearer tokens must be at least 24 characters")
    if len(set(secrets)) != len(secrets):
        raise RuntimeError("Support desk bearer tokens must be distinct")

    try:
        mcp_expires_at = float(os.environ["SUPPORT_DESK_MCP_TOKEN_EXPIRES_AT"])
    except (KeyError, ValueError) as exc:
        raise RuntimeError(
            "SUPPORT_DESK_MCP_TOKEN_EXPIRES_AT must be a Unix timestamp"
        ) from exc
    remaining_seconds = mcp_expires_at - time.time()
    if remaining_seconds <= 0 or remaining_seconds > 3600:
        raise RuntimeError(
            "SUPPORT_DESK_MCP_TOKEN_EXPIRES_AT must be within the next 3600 seconds"
        )



_require_production_configuration()

configure(
    database_url=DATABASE_URL,
    debug=False,
    log_level=os.getenv("AKSARA_LOG_LEVEL", "INFO"),
    pool_min_size=int(os.getenv("AKSARA_POOL_MIN_SIZE", "2")),
    pool_max_size=int(os.getenv("AKSARA_POOL_MAX_SIZE", "10")),
    migrations_dir=str(PACKAGE_ROOT / "migrations"),
    apps=[__package__ or "examples.support_desk"],
    installed_apps=[
        "aksara.contrib.auth",
        "aksara.contrib.admin",
        __package__ or "examples.support_desk",
    ],
    enable_studio=False,
    studio_expose_in_production=False,
    ai_enabled=False,
    mcp_enabled=True,
    mcp_token_audience=os.getenv("SUPPORT_DESK_MCP_AUDIENCE", "support-desk"),
    mcp_approval_secret=os.getenv("SUPPORT_DESK_MCP_APPROVAL_SECRET"),
    tasks_enabled=True,
    task_poll_interval_seconds=float(os.getenv("AKSARA_TASK_POLL_INTERVAL", "0.1")),
    task_retry_delay_seconds=float(os.getenv("AKSARA_TASK_RETRY_DELAY", "0.1")),
    task_retry_backoff_base=1.0,
    task_retry_max_delay_seconds=1.0,
    task_concurrency=int(os.getenv("AKSARA_TASK_CONCURRENCY", "2")),
)
