"""Prompt-independent limits for Aksara AI planning and provider execution."""

from __future__ import annotations

from dataclasses import dataclass, field


class RuntimeLimitExceeded(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class AgentRuntimeLimits:
    max_tool_calls: int = 20
    max_steps: int = 50
    run_timeout_seconds: float = 120.0
    tool_timeout_seconds: float = 30.0
    provider_timeout_seconds: float = 60.0
    token_budget: int | None = None
    cost_budget_usd: float | None = None

    def __post_init__(self) -> None:
        for name in (
            "max_tool_calls", "max_steps", "run_timeout_seconds",
            "tool_timeout_seconds", "provider_timeout_seconds",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if self.token_budget is not None and self.token_budget <= 0:
            raise ValueError("token_budget must be greater than zero")
        if self.cost_budget_usd is not None and self.cost_budget_usd <= 0:
            raise ValueError("cost_budget_usd must be greater than zero")


@dataclass(slots=True)
class AgentRuntimeBudget:
    limits: AgentRuntimeLimits
    steps: int = 0
    tool_calls: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    _tool_call_ids: set[str] = field(default_factory=set)

    def consume_step(self) -> None:
        self.steps += 1
        if self.steps > self.limits.max_steps:
            raise RuntimeLimitExceeded("max_steps_exceeded", "Maximum planning/execution steps exceeded.")

    def consume_tool_call(self, tool_call_id: str | None = None) -> None:
        if tool_call_id and tool_call_id in self._tool_call_ids:
            raise RuntimeLimitExceeded("repeated_tool_call", "A tool-call ID was repeated.")
        if tool_call_id:
            self._tool_call_ids.add(tool_call_id)
        self.tool_calls += 1
        if self.tool_calls > self.limits.max_tool_calls:
            raise RuntimeLimitExceeded("max_tool_calls_exceeded", "Maximum tool calls exceeded.")

    def consume_usage(self, *, tokens: int = 0, cost_usd: float = 0.0) -> None:
        self.tokens += max(0, tokens)
        self.cost_usd += max(0.0, cost_usd)
        if self.limits.token_budget is not None and self.tokens > self.limits.token_budget:
            raise RuntimeLimitExceeded("token_budget_exceeded", "Provider token budget exceeded.")
        if self.limits.cost_budget_usd is not None and self.cost_usd > self.limits.cost_budget_usd:
            raise RuntimeLimitExceeded("cost_budget_exceeded", "Provider cost budget exceeded.")


__all__ = ["AgentRuntimeBudget", "AgentRuntimeLimits", "RuntimeLimitExceeded"]
