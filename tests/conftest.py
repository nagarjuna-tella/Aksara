"""Shared test configuration."""

from __future__ import annotations

import asyncio
import os

import pytest


_DATABASE_PROBE_DONE = False


def _mark_database_unavailable_if_needed() -> None:
    """Skip DB integration tests cleanly when DATABASE_URL is unusable."""

    global _DATABASE_PROBE_DONE

    if _DATABASE_PROBE_DONE:
        return

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return
    if os.environ.get("AKSARA_REQUIRE_DATABASE_TESTS"):
        _DATABASE_PROBE_DONE = True
        return

    async def _probe() -> None:
        import asyncpg

        conn = await asyncpg.connect(database_url, timeout=1)
        try:
            await conn.fetchval("SELECT 1")
        finally:
            await conn.close()

    try:
        asyncio.run(_probe())
        _DATABASE_PROBE_DONE = True
    except Exception as exc:
        _DATABASE_PROBE_DONE = True
        os.environ["AKSARA_TEST_DATABASE_UNAVAILABLE"] = repr(exc)
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("AKSARA_DATABASE_URL", None)


def pytest_configure(config):
    _mark_database_unavailable_if_needed()


@pytest.fixture(autouse=True)
def _clear_unavailable_database_url(monkeypatch):
    """Keep .env reloads from re-enabling unavailable DB tests mid-run."""

    if os.environ.get("AKSARA_TEST_DATABASE_UNAVAILABLE"):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("AKSARA_DATABASE_URL", raising=False)


def pytest_runtest_setup(item):
    """Clear unavailable DB URLs before fixtures resolve DATABASE_URL."""

    if not os.environ.get("AKSARA_TEST_DATABASE_UNAVAILABLE"):
        _mark_database_unavailable_if_needed()

    if os.environ.get("AKSARA_TEST_DATABASE_UNAVAILABLE"):
        if "db" in getattr(item, "fixturenames", ()):
            pytest.skip("DATABASE_URL is unavailable for live database tests")
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("AKSARA_DATABASE_URL", None)
