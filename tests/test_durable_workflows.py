"""
Tests for DurableStep workflow state persistence.
"""

from __future__ import annotations

import os

import pytest

from aksara.workflows import DURABLE_STATE_TABLE, ConcurrentStepError, DurableStep


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


@pytest.fixture
async def db():
    """Create a database connection for durable workflow tests."""
    from aksara.db import Database

    database = Database(os.environ["DATABASE_URL"])
    await database.connect()

    yield database

    try:
        await database.execute(f'DROP TABLE IF EXISTS "{DURABLE_STATE_TABLE}" CASCADE')
    except Exception:
        pass

    await database.disconnect()


class TestDurableStep:
    """Integration tests for durable workflow execution."""

    @pytest.mark.asyncio
    async def test_reuses_completed_result_without_rerunning(self, db):
        calls = {"count": 0}
        step = DurableStep("workflow-one", db=db)

        async def generate_payload():
            calls["count"] += 1
            return {"count": calls["count"], "status": "ok"}

        first = await step.run("generate_code", generate_payload)
        second = await step.run("generate_code", generate_payload)

        assert first == {"count": 1, "status": "ok"}
        assert second == {"count": 1, "status": "ok"}
        assert calls["count"] == 1

        state = await step.get_state("generate_code")
        assert state is not None
        assert state.status == "completed"
        assert state.result == {"count": 1, "status": "ok"}

    @pytest.mark.asyncio
    async def test_failed_steps_can_retry(self, db):
        calls = {"count": 0}
        step = DurableStep("workflow-two", db=db)

        async def flaky_step():
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("boom")
            return {"status": "recovered"}

        with pytest.raises(RuntimeError, match="boom"):
            await step.run("generate_code", flaky_step)

        failed_state = await step.get_state("generate_code")
        assert failed_state is not None
        assert failed_state.status == "failed"
        assert failed_state.error == "boom"

        recovered = await step.run("generate_code", flaky_step)
        assert recovered == {"status": "recovered"}
        assert calls["count"] == 2

    @pytest.mark.asyncio
    async def test_force_reruns_completed_step(self, db):
        calls = {"count": 0}
        step = DurableStep("workflow-three", db=db)

        async def compute_value():
            calls["count"] += 1
            return {"count": calls["count"]}

        first = await step.run("summarize", compute_value)
        second = await step.run("summarize", compute_value, force=True)

        assert first == {"count": 1}
        assert second == {"count": 2}
        assert calls["count"] == 2

    @pytest.mark.asyncio
    async def test_concurrent_step_raises_concurrent_step_error(self, db):
        """A second concurrent caller targeting an already-running step raises ConcurrentStepError."""
        step = DurableStep("workflow-concurrent", db=db)
        await step.ensure_table()

        # Plant a 'running' row directly to simulate another caller mid-execution.
        from aksara.db import Database
        await db.execute(
            f"""
            INSERT INTO "{DURABLE_STATE_TABLE}" (workflow_id, step_name, status)
            VALUES ($1, $2, 'running')
            """,
            "workflow-concurrent",
            "locked_step",
        )

        async def should_not_run():
            return {"should": "not run"}

        with pytest.raises(ConcurrentStepError, match="already running concurrently"):
            await step.run("locked_step", should_not_run)

    @pytest.mark.asyncio
    async def test_concurrent_step_returns_cached_if_completed_between_calls(self, db):
        """If the concurrent holder completes before we re-read, return the cached result."""
        step = DurableStep("workflow-concurrent-complete", db=db)
        await step.ensure_table()

        # Plant a row that is 'running' at claim time but 'completed' by re-read.
        # We simulate this by inserting a completed row directly (the claim query
        # returns no row because status != 'failed', then the re-read finds 'completed').
        await db.execute(
            f"""
            INSERT INTO "{DURABLE_STATE_TABLE}" (workflow_id, step_name, status, result, completed_at)
            VALUES ($1, $2, 'completed', $3, CURRENT_TIMESTAMP)
            """,
            "workflow-concurrent-complete",
            "finished_step",
            '{"answer": 42}',
        )

        async def should_not_run():
            raise AssertionError("should not be called")

        result = await step.run("finished_step", should_not_run)
        assert result == {"answer": 42}

    @pytest.mark.asyncio
    async def test_failed_step_can_be_retried_without_concurrent_error(self, db):
        """A failed step must be retryable: atomic claim should allow re-entry after failure."""
        calls = {"count": 0}
        step = DurableStep("workflow-retry-after-fail", db=db)

        async def flaky():
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("first attempt fails")
            return {"ok": True}

        with pytest.raises(RuntimeError, match="first attempt fails"):
            await step.run("flaky_step", flaky)

        result = await step.run("flaky_step", flaky)
        assert result == {"ok": True}
        assert calls["count"] == 2