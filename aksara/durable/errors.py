"""Stable exceptions raised by durable operation services."""

from __future__ import annotations


class DurableOperationError(RuntimeError):
    """Base class for durable operation errors."""

    code = "durable_operation_error"


class DurableConfigurationError(DurableOperationError):
    code = "durable_configuration_error"


class ActionNotRegistered(DurableConfigurationError):
    code = "action_not_registered"


class ResolverNotRegistered(DurableConfigurationError):
    code = "identity_resolver_missing"


class InvalidDurableCommand(DurableOperationError, ValueError):
    code = "invalid_command"


class IdempotencyConflict(DurableOperationError):
    code = "idempotency_conflict"


class IdempotencyIdentityExpired(DurableOperationError):
    code = "idempotency_identity_expired"


class OperationNotFound(DurableOperationError):
    code = "operation_not_found"


class OperationTerminal(DurableOperationError):
    code = "operation_terminal"


class OwnershipLost(DurableOperationError):
    code = "ownership_lost"


class AuthorizationDenied(DurableOperationError):
    code = "authorization_denied"


class ApprovalConflict(DurableOperationError):
    code = "approval_conflict"


class CancellationConflict(DurableOperationError):
    code = "cancellation_conflict"


class AtomicBoundaryViolation(DurableOperationError):
    code = "atomic_boundary_violation"


class AmbiguousCommitOutcome(DurableOperationError):
    code = "ambiguous_commit_outcome"


__all__ = [
    "ActionNotRegistered",
    "AmbiguousCommitOutcome",
    "ApprovalConflict",
    "AtomicBoundaryViolation",
    "AuthorizationDenied",
    "CancellationConflict",
    "DurableConfigurationError",
    "DurableOperationError",
    "IdempotencyConflict",
    "IdempotencyIdentityExpired",
    "InvalidDurableCommand",
    "OperationNotFound",
    "OperationTerminal",
    "OwnershipLost",
    "ResolverNotRegistered",
]
