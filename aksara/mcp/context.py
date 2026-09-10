"""Immutable identity and correlation context for an MCP tool invocation."""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar, Token
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any

from aksara.security.principal import Principal


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_value(item) for item in value)
    return value


def _freeze(values: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return _freeze_value(values or {})


@dataclass(frozen=True, slots=True)
class AgentInvocationContext:
    """Request-scoped context propagated from MCP through policy and storage."""

    principal: Principal
    request_id: str
    run_id: str
    tool_call_id: str
    tool_name: str
    operation: str
    policy_context: Mapping[str, Any] = field(default_factory=dict)
    approval_context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        principal = replace(
            self.principal,
            roles=tuple(self.principal.roles),
            scopes=tuple(self.principal.scopes),
            metadata=_freeze(self.principal.metadata),
        )
        object.__setattr__(self, "principal", principal)
        object.__setattr__(self, "policy_context", _freeze(self.policy_context))
        object.__setattr__(self, "approval_context", _freeze(self.approval_context))


_invocation_context: ContextVar[AgentInvocationContext | None] = ContextVar(
    "aksara_mcp_invocation_context", default=None
)


def get_agent_invocation_context() -> AgentInvocationContext | None:
    """Return the current invocation without falling back to global state."""

    return _invocation_context.get()


def push_agent_invocation_context(context: AgentInvocationContext) -> Token:
    """Install an invocation in the current async context."""

    return _invocation_context.set(context)


def reset_agent_invocation_context(token: Token) -> None:
    """Restore the exact context that preceded this invocation."""

    _invocation_context.reset(token)


__all__ = [
    "AgentInvocationContext",
    "get_agent_invocation_context",
    "push_agent_invocation_context",
    "reset_agent_invocation_context",
]
