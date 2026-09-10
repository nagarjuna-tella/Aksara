"""Allowlisted action and principal-resolver registries."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from aksara.durable.errors import (
    ActionNotRegistered,
    InvalidDurableCommand,
    ResolverNotRegistered,
)
from aksara.durable.types import EffectClass, PrincipalReference, normalize_json
from aksara.security.principal import Principal

CommandNormalizer = Callable[[Mapping[str, Any]], Any]
ActionHandler = Callable[..., Any]
ActionAuthorizer = Callable[..., bool | Any | Awaitable[bool | Any]]
PrincipalResolver = Callable[
    [PrincipalReference], "PrincipalResolution | Principal | Awaitable[PrincipalResolution | Principal]"
]


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    DELETED = "deleted"
    DISABLED = "disabled"
    MEMBERSHIP_REMOVED = "membership_removed"
    MALFORMED = "malformed"
    REVOKED = "revoked"


@dataclass(frozen=True)
class PrincipalResolution:
    status: ResolutionStatus
    principal: Principal | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        if self.status is ResolutionStatus.RESOLVED and self.principal is None:
            raise ValueError("resolved principal outcome requires a Principal")
        if self.status is not ResolutionStatus.RESOLVED and self.principal is not None:
            raise ValueError("unresolved principal outcome cannot carry a Principal")

    @classmethod
    def resolved(cls, principal: Principal) -> "PrincipalResolution":
        return cls(ResolutionStatus.RESOLVED, principal=principal)


@dataclass(frozen=True)
class DurableAction:
    """Code-registered durable action definition.

    Persisted rows select only this allowlisted name/version pair. They cannot
    name imports, functions, SQL or shell commands.
    """

    name: str
    version: str
    handler: ActionHandler
    effect_class: EffectClass
    command_normalizer: CommandNormalizer | type[Any] | None = None
    result_normalizer: Callable[[Any], Any] | None = None
    retry_classifier: Callable[[BaseException], bool] | None = None
    authorizer: ActionAuthorizer | None = None
    approval_authorizer: ActionAuthorizer | None = None
    approval_required: bool = False
    executor_type: str = "inline"
    required_scopes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name or not self.version:
            raise ValueError("durable action name and version are required")
        if self.executor_type not in {"inline", "task"}:
            raise ValueError("executor_type must be 'inline' or 'task'")
        if not callable(self.handler):
            raise TypeError("durable action handler must be callable")

    def normalize_command(self, command: Mapping[str, Any]) -> dict[str, Any]:
        try:
            value: Any = dict(command)
            normalizer = self.command_normalizer
            if normalizer is not None:
                if inspect.isclass(normalizer) and hasattr(normalizer, "model_validate"):
                    value = normalizer.model_validate(value)
                else:
                    value = normalizer(value)
            if hasattr(value, "model_dump"):
                value = value.model_dump(mode="json", exclude_none=False)
            normalized = normalize_json(value)
        except Exception as exc:
            raise InvalidDurableCommand(
                f"Command validation failed for {self.name}@{self.version}: {exc}"
            ) from exc
        if not isinstance(normalized, dict):
            raise InvalidDurableCommand("durable command must normalize to a JSON object")
        return normalized

    def normalize_result(self, result: Any) -> Any:
        if self.result_normalizer is not None:
            result = self.result_normalizer(result)
        return normalize_json(result)

    def is_retryable(self, error: BaseException) -> bool:
        if self.retry_classifier is None:
            return False
        return bool(self.retry_classifier(error))


class DurableActionRegistry:
    """In-process allowlist for deployed action versions."""

    def __init__(self) -> None:
        self._actions: dict[tuple[str, str], DurableAction] = {}

    def register(self, action: DurableAction, *, replace: bool = False) -> DurableAction:
        key = (action.name, action.version)
        if key in self._actions and not replace:
            raise ValueError(f"Durable action already registered: {action.name}@{action.version}")
        self._actions[key] = action
        return action

    def unregister(self, name: str, version: str) -> None:
        self._actions.pop((name, version), None)

    def get(self, name: str, version: str) -> DurableAction:
        try:
            return self._actions[(name, version)]
        except KeyError as exc:
            raise ActionNotRegistered(
                f"Durable action is not registered: {name}@{version}"
            ) from exc

    def contains(self, name: str, version: str) -> bool:
        return (name, version) in self._actions

    def versions(self) -> frozenset[tuple[str, str]]:
        return frozenset(self._actions)

    def clear(self) -> None:
        self._actions.clear()


class PrincipalResolverRegistry:
    """Code-controlled mapping from durable locators to current Principals."""

    def __init__(self) -> None:
        self._resolvers: dict[tuple[str, str], PrincipalResolver] = {}

    def register(
        self,
        key: str,
        version: str,
        resolver: PrincipalResolver,
        *,
        replace: bool = False,
    ) -> PrincipalResolver:
        identity = (key, version)
        if identity in self._resolvers and not replace:
            raise ValueError(f"Principal resolver already registered: {key}@{version}")
        self._resolvers[identity] = resolver
        return resolver

    def unregister(self, key: str, version: str) -> None:
        self._resolvers.pop((key, version), None)

    def contains(self, key: str, version: str) -> bool:
        return (key, version) in self._resolvers

    def versions(self) -> frozenset[tuple[str, str]]:
        return frozenset(self._resolvers)

    async def resolve(self, reference: PrincipalReference) -> PrincipalResolution:
        try:
            resolver = self._resolvers[(reference.resolver_key, reference.resolver_version)]
        except KeyError as exc:
            raise ResolverNotRegistered(
                "Principal resolver is not registered: "
                f"{reference.resolver_key}@{reference.resolver_version}"
            ) from exc

        outcome = resolver(reference)
        if inspect.isawaitable(outcome):
            outcome = await outcome
        if isinstance(outcome, Principal):
            outcome = PrincipalResolution.resolved(outcome)
        if not isinstance(outcome, PrincipalResolution):
            raise TypeError("principal resolver must return Principal or PrincipalResolution")
        return outcome

    def clear(self) -> None:
        self._resolvers.clear()


default_action_registry = DurableActionRegistry()
default_principal_resolver_registry = PrincipalResolverRegistry()


__all__ = [
    "DurableAction",
    "DurableActionRegistry",
    "PrincipalResolution",
    "PrincipalResolverRegistry",
    "ResolutionStatus",
    "default_action_registry",
    "default_principal_resolver_registry",
]
