from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from aksara.ai.limits import AgentRuntimeBudget, AgentRuntimeLimits
from aksara.ai.planner import AiPlan, AiPlanStep, AiPlanStepResult, execute_plan
from aksara.ai.runtime import run_prompt_pack


class FakeConnector:
    def __init__(self, result=None, *, delay: float = 0, error: Exception | None = None):
        self.result = result
        self.delay = delay
        self.error = error
        self.max_tokens = None

    async def chat(self, **kwargs):
        self.max_tokens = kwargs["max_tokens"]
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.result


def _pack() -> dict[str, object]:
    return {"provider": "fake", "model": "deterministic", "user_prompt": "hello", "max_tokens": 100}


@pytest.mark.asyncio
async def test_normal_structured_and_tool_call_provider_response() -> None:
    connector = FakeConnector(
        {
            "ok": True,
            "text": "done",
            "structured": {"answer": 42},
            "tokens": {"total": 9},
            "raw": {"tool_calls": [{"id": "call-1", "name": "ticket_list"}]},
        }
    )
    limits = AgentRuntimeLimits(token_budget=10, max_tool_calls=1)
    with patch("aksara.ai.connectors.registry.get_connector", return_value=connector):
        result = await run_prompt_pack(_pack(), limits=limits)
    assert result["ok"] is True
    assert result["structured_response"] == {"answer": 42}
    assert result["tool_calls"][0]["id"] == "call-1"
    assert connector.max_tokens == 10


@pytest.mark.asyncio
async def test_malformed_provider_response_is_classified() -> None:
    for malformed in (None, [], {}, {"ok": True, "text": object(), "tokens": {}}):
        with patch("aksara.ai.connectors.registry.get_connector", return_value=FakeConnector(malformed)):
            result = await run_prompt_pack(_pack())
        assert result["ok"] is False
        assert result["error_code"] == "MALFORMED_PROVIDER_RESPONSE"


@pytest.mark.asyncio
async def test_provider_timeout_exception_and_cancellation() -> None:
    limits = AgentRuntimeLimits(provider_timeout_seconds=0.01)
    with patch(
        "aksara.ai.connectors.registry.get_connector",
        return_value=FakeConnector({"ok": True}, delay=1),
    ):
        result = await run_prompt_pack(_pack(), limits=limits)
    assert result["error_code"] == "PROVIDER_TIMEOUT"

    with patch(
        "aksara.ai.connectors.registry.get_connector",
        return_value=FakeConnector(error=RuntimeError("provider exploded")),
    ):
        result = await run_prompt_pack(_pack())
    assert result["error_code"] == "PROVIDER_ERROR"

    blocker = asyncio.Event()

    class BlockingConnector:
        async def chat(self, **kwargs):
            await blocker.wait()

    with patch("aksara.ai.connectors.registry.get_connector", return_value=BlockingConnector()):
        task = asyncio.create_task(run_prompt_pack(_pack()))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_excessive_and_repeated_tool_calls_are_limited() -> None:
    excessive = {
        "ok": True,
        "text": "",
        "tokens": {},
        "tool_calls": [{"id": "one"}, {"id": "two"}],
    }
    with patch("aksara.ai.connectors.registry.get_connector", return_value=FakeConnector(excessive)):
        result = await run_prompt_pack(_pack(), limits=AgentRuntimeLimits(max_tool_calls=1))
    assert result["error_code"] == "MAX_TOOL_CALLS_EXCEEDED"

    repeated = {"ok": True, "text": "", "tokens": {}, "tool_calls": [{"id": "one"}]}
    budget = AgentRuntimeBudget(AgentRuntimeLimits(max_tool_calls=3))
    with patch("aksara.ai.connectors.registry.get_connector", return_value=FakeConnector(repeated)):
        assert (await run_prompt_pack(_pack(), budget=budget))["ok"] is True
        result = await run_prompt_pack(_pack(), budget=budget)
    assert result["error_code"] == "REPEATED_TOOL_CALL"


@pytest.mark.asyncio
async def test_planner_limits_steps_timeouts_and_cancellation_before_continuing() -> None:
    steps = [
        AiPlanStep(id=f"step-{index}", type="analyze_context", description="bounded")
        for index in range(2)
    ]
    rejected = await execute_plan(
        object(),
        AiPlan(intent="too many", steps=steps),
        limits=AgentRuntimeLimits(max_steps=1),
    )
    assert rejected.success is False
    assert rejected.steps == []
    assert "maximum planning/execution steps" in rejected.notes[-1]

    started: list[str] = []

    async def slow_handler(app, step, dry_run):
        started.append(step.id)
        await asyncio.sleep(1)
        return AiPlanStepResult(id=step.id, type=step.type, success=True)

    with patch.dict("aksara.ai.planner.STEP_HANDLERS", {"analyze_context": slow_handler}):
        timed_out = await execute_plan(
            object(),
            AiPlan(intent="timeout", steps=[steps[0]]),
            limits=AgentRuntimeLimits(tool_timeout_seconds=0.01),
        )
    assert timed_out.success is False
    assert timed_out.steps[0].error == "Runtime limit exceeded: step or overall plan timeout"
    assert started == ["step-0"]

    blocker = asyncio.Event()

    async def blocking_handler(app, step, dry_run):
        await blocker.wait()
        return AiPlanStepResult(id=step.id, type=step.type, success=True)

    with patch.dict("aksara.ai.planner.STEP_HANDLERS", {"analyze_context": blocking_handler}):
        task = asyncio.create_task(
            execute_plan(object(), AiPlan(intent="cancel", steps=[steps[0]]))
        )
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
