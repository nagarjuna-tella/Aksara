"""Value objects for Durable Authorized Operations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, cast
from uuid import UUID

from aksara.durable.states import AttemptState, OperationState
from aksara.security.principal import Principal

GLOBAL_TENANT_SCOPE = "__aksara_global__"
PRINCIPAL_REFERENCE_VERSION = 1


class EffectClass(str, Enum):
    """Honest durability classification for an action's side effects."""

    POSTGRES_ATOMIC = "postgres_atomic"
    EXTERNAL_IDEMPOTENT = "external_idempotent"
    EXTERNAL_AT_LEAST_ONCE = "external_at_least_once"
    EXTERNAL_NONRETRYABLE = "external_nonretryable"
    READ_ONLY = "read_only"


def _json_default(value: Any) -> Any:
    if isinstance(value, (UUID, datetime)):
        return value.isoformat() if isinstance(value, datetime) else str(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return asdict(cast(Any, value))
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def normalize_json(value: Any) -> Any:
    """Return JSON primitives using one deterministic encoding policy."""

    return json.loads(json.dumps(value, default=_json_default, allow_nan=False))


def canonical_json(value: Any) -> str:
    """Serialize semantic data for stable hashing."""

    return json.dumps(
        normalize_json(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def tenant_scope(tenant_id: str | None) -> str:
    return str(tenant_id) if tenant_id is not None else GLOBAL_TENANT_SCOPE


@dataclass(frozen=True)
class PrincipalReference:
    """Versioned, non-secret locator used to resolve current authority.

    Roles, scopes, credentials and the admission-time Principal are excluded.
    A credential identifier may be retained solely as a revocation lookup key.
    """

    resolver_key: str
    resolver_version: str
    identity_namespace: str
    principal_kind: str
    subject_id: str | None
    tenant_id: str | None
    human_owner_id: str | None = None
    agent_id: str | None = None
    credential_id: str | None = None
    version: int = PRINCIPAL_REFERENCE_VERSION

    def __post_init__(self) -> None:
        if not self.resolver_key or not self.resolver_version:
            raise ValueError("resolver_key and resolver_version are required")
        if not self.identity_namespace or not self.principal_kind:
            raise ValueError("identity_namespace and principal_kind are required")
        if self.version != PRINCIPAL_REFERENCE_VERSION:
            raise ValueError(
                f"Unsupported principal reference version: {self.version}"
            )
        if not any((self.subject_id, self.human_owner_id, self.agent_id, self.credential_id)):
            raise ValueError("principal reference requires at least one stable identity")

    @classmethod
    def from_principal(
        cls,
        principal: Principal,
        *,
        resolver_key: str,
        resolver_version: str = "1",
        identity_namespace: str = "application",
        credential_id: str | None = None,
    ) -> PrincipalReference:
        """Create a locator without persisting roles, scopes, tokens or metadata."""

        subject = principal.user_id
        stable_credential = credential_id
        if stable_credential is None and principal.token_id:
            stable_credential = principal.token_id
        kind = "system" if principal.is_system else (
            "agent" if principal.is_ai_agent else "user"
        )
        return cls(
            resolver_key=resolver_key,
            resolver_version=resolver_version,
            identity_namespace=identity_namespace,
            principal_kind=kind,
            subject_id=subject,
            tenant_id=principal.tenant_id,
            human_owner_id=principal.human_owner_id,
            agent_id=principal.agent_id,
            credential_id=stable_credential,
        )

    def to_dict(self) -> dict[str, Any]:
        return normalize_json(asdict(self))

    @property
    def integrity_hash(self) -> str:
        return stable_hash(self.to_dict())


@dataclass(frozen=True)
class OperationRecord:
    """Stable semantic projection of an operation row."""

    id: UUID
    application_namespace: str
    tenant_id: str | None
    action_name: str
    action_version: str
    effect_class: EffectClass
    state: OperationState
    state_version: int
    attempt_count: int
    max_attempts: int
    available_at: datetime
    deadline_at: datetime | None
    cancellation_requested_at: datetime | None
    result: Any
    result_expires_at: datetime | None
    error: Any
    error_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    retain_until: datetime

    @property
    def terminal(self) -> bool:
        from aksara.durable.states import TERMINAL_OPERATION_STATES

        return self.state in TERMINAL_OPERATION_STATES


@dataclass(frozen=True)
class OperationAdmission:
    operation: OperationRecord
    created: bool


@dataclass(frozen=True)
class OperationClaim:
    operation_id: UUID
    attempt_id: UUID
    tenant_id: str | None
    tenant_scope: str
    action_name: str
    action_version: str
    effect_class: EffectClass
    worker_id: str
    fence: int
    ordinal: int
    lease_expires_at: datetime
    command: Mapping[str, Any]
    principal_reference: PrincipalReference


@dataclass(frozen=True)
class AttemptRecord:
    id: UUID
    operation_id: UUID
    ordinal: int
    fence: int
    worker_id: str
    state: AttemptState
    lease_expires_at: datetime
    started_at: datetime
    completed_at: datetime | None
    retryable: bool | None
    error_code: str | None
    error: Any
    usage_summary: Mapping[str, Any]


@dataclass(frozen=True)
class TransitionRecord:
    id: int
    operation_id: UUID
    state_version: int
    from_state: OperationState | None
    event: str
    to_state: OperationState
    reason_code: str | None
    attempt_id: UUID | None
    created_at: datetime
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class OutboxRecord:
    id: int
    operation_id: UUID
    transition_id: int
    topic: str
    payload: Mapping[str, Any]
    export_attempts: int
    created_at: datetime


__all__ = [
    "GLOBAL_TENANT_SCOPE",
    "PRINCIPAL_REFERENCE_VERSION",
    "AttemptRecord",
    "EffectClass",
    "OperationAdmission",
    "OperationClaim",
    "OperationRecord",
    "OutboxRecord",
    "PrincipalReference",
    "TransitionRecord",
    "canonical_json",
    "normalize_json",
    "stable_hash",
    "tenant_scope",
]
