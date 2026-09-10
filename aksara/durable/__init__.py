"""Durable authorized operation primitives."""

from aksara.durable.errors import (
    ActionNotRegistered,
    ApprovalConflict,
    AuthorizationDenied,
    CancellationConflict,
    DurableConfigurationError,
    DurableOperationError,
    IdempotencyConflict,
    IdempotencyIdentityExpired,
    InvalidDurableCommand,
    OperationNotFound,
    OperationTerminal,
)
from aksara.durable.execution import (
    PostgresAtomicExecutionContext,
    PostgresAtomicExecutor,
)
from aksara.durable.registry import (
    DurableAction,
    DurableActionRegistry,
    PrincipalResolution,
    PrincipalResolverRegistry,
    ResolutionStatus,
)
from aksara.durable.service import DurableOperationService
from aksara.durable.states import OperationState
from aksara.durable.types import (
    EffectClass,
    OperationAdmission,
    OperationRecord,
    PrincipalReference,
)

__all__ = [
    "ActionNotRegistered",
    "ApprovalConflict",
    "AuthorizationDenied",
    "CancellationConflict",
    "DurableAction",
    "DurableActionRegistry",
    "DurableConfigurationError",
    "DurableOperationError",
    "DurableOperationService",
    "EffectClass",
    "IdempotencyConflict",
    "IdempotencyIdentityExpired",
    "InvalidDurableCommand",
    "OperationAdmission",
    "OperationNotFound",
    "OperationRecord",
    "OperationState",
    "OperationTerminal",
    "PostgresAtomicExecutionContext",
    "PostgresAtomicExecutor",
    "PrincipalReference",
    "PrincipalResolution",
    "PrincipalResolverRegistry",
    "ResolutionStatus",
]
