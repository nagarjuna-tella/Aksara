"""Durable authorized operation primitives."""

from aksara.durable.api import create_durable_operations_router
from aksara.durable.diagnostics import check_durable_operations
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
    ReadOnlyExecutor,
)
from aksara.durable.external import (
    ExternalEffectAdapter,
    ExternalEffectContext,
    ExternalEffectResult,
    ExternalOperationExecutor,
    ExternalOutcomeUnknown,
    ReconciliationResult,
    ReconciliationStatus,
)
from aksara.durable.outbox import DurableOutboxExporter
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
from aksara.durable.worker import DurableOperationWorker

__all__ = [
    "ActionNotRegistered",
    "ApprovalConflict",
    "AuthorizationDenied",
    "CancellationConflict",
    "create_durable_operations_router",
    "check_durable_operations",
    "DurableAction",
    "DurableActionRegistry",
    "DurableConfigurationError",
    "DurableOperationError",
    "DurableOperationService",
    "DurableOperationWorker",
    "DurableOutboxExporter",
    "EffectClass",
    "ExternalEffectAdapter",
    "ExternalEffectContext",
    "ExternalEffectResult",
    "ExternalOperationExecutor",
    "ExternalOutcomeUnknown",
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
    "ReadOnlyExecutor",
    "PrincipalReference",
    "PrincipalResolution",
    "PrincipalResolverRegistry",
    "ReconciliationResult",
    "ReconciliationStatus",
    "ResolutionStatus",
]
