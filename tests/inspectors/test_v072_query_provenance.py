"""PostgreSQL and offline provenance contracts for query-plan inspection."""

from __future__ import annotations

import os

import pytest

from aksara.db import Database
from aksara.inspectors import explain_query, explain_query_async


@pytest.mark.asyncio
async def test_offline_analyze_is_explicitly_synthetic_and_not_executed(monkeypatch):
    monkeypatch.setattr(Database, "_instance", None)

    result = await explain_query_async("SELECT 1", analyze=True)

    assert result.provenance == "synthetic"
    assert result.plan_type == "EXPLAIN ANALYZE"
    assert result.analyze_executed is False
    assert any("not executed" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_sync_api_inside_event_loop_uses_labelled_fallback():
    result = explain_query("SELECT 1", analyze=False)

    assert result.provenance == "synthetic"
    assert result.analyze_executed is False
    assert any("active event loop" in warning for warning in result.warnings)


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL is required")
async def test_live_explain_analyze_and_failure_provenance():
    previous = Database._instance
    database = Database(os.environ["DATABASE_URL"], min_size=1, max_size=1)
    await database.connect()
    try:
        explained = await explain_query_async("SELECT 1", analyze=False)
        assert explained.provenance == "live"
        assert explained.plan_type == "EXPLAIN"
        assert explained.analyze_executed is False
        assert explained.plan
        assert explained.estimated_cost is not None
        assert explained.warnings == []

        analyzed = await explain_query_async("SELECT 1", analyze=True)
        assert analyzed.provenance == "live"
        assert analyzed.plan_type == "EXPLAIN ANALYZE"
        assert analyzed.analyze_executed is True
        assert analyzed.plan
        assert any("actual time" in line for line in analyzed.plan)

        failed = await explain_query_async(
            "SELECT definitely_invalid_syntax",
            analyze=False,
        )
        assert failed.provenance == "failed"
        assert failed.analyze_executed is False
        assert failed.plan == []
        assert failed.estimated_cost is None
        assert any("failed" in warning.lower() for warning in failed.warnings)
    finally:
        await database.disconnect()
        Database._instance = previous
