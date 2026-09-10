"""Internal state vocabulary for durable authorized operations.

The operation row is authoritative current state.  Transition records are
diagnostic/export facts and are never replayed to reconstruct that state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OperationState(str, Enum):
    """Authoritative logical operation states."""

    WAITING_FOR_APPROVAL = "waiting_for_approval"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AttemptState(str, Enum):
    """Physical execution attempt states."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABANDONED = "abandoned"
    CANCELLED = "cancelled"


class OperationEvent(str, Enum):
    """Stable internal events that may change or confirm operation state."""

    ADMITTED = "admitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPROVAL_EXPIRED = "approval_expired"
    CLAIMED = "claimed"
    HEARTBEAT = "heartbeat"
    LEASE_RECLAIMED = "lease_reclaimed"
    RETRY_SCHEDULED = "retry_scheduled"
    TERMINAL_FAILURE = "terminal_failure"
    CANCELLATION_REQUESTED = "cancellation_requested"
    CANCELLATION_OBSERVED = "cancellation_observed"
    DEADLINE_EXPIRED = "deadline_expired"
    SUCCEEDED = "succeeded"


class FailureReason(str, Enum):
    """Stable machine-readable reasons for unsuccessful durable work."""

    INVALID_COMMAND = "invalid_command"
    ACTION_UNAVAILABLE = "action_unavailable"
    ACTION_VERSION_UNAVAILABLE = "action_version_unavailable"
    RESOLVER_UNAVAILABLE = "identity_resolution_unavailable"
    RESOLVER_MISSING = "identity_resolver_missing"
    MALFORMED_PROVENANCE = "malformed_principal_provenance"
    PRINCIPAL_DELETED = "principal_deleted"
    PRINCIPAL_DISABLED = "principal_disabled"
    IDENTITY_REVOKED = "identity_revoked"
    TENANT_MEMBERSHIP_REMOVED = "tenant_membership_removed"
    AUTHORIZATION_REQUIRED = "authorization_required"
    AUTHORIZATION_DENIED = "authorization_denied"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_EXPIRED = "approval_expired"
    DEADLINE_EXPIRED = "deadline_expired"
    CANCELLED = "cancelled"
    ATTEMPTS_EXHAUSTED = "attempts_exhausted"
    OWNERSHIP_LOST = "ownership_lost"
    LEASE_EXPIRED = "lease_expired"
    EXECUTOR_ERROR = "executor_error"
    DATABASE_ERROR = "database_error"
    EXTERNAL_OUTCOME_UNKNOWN = "external_outcome_unknown"
    LIMIT_EXCEEDED = "limit_exceeded"
    INTERNAL_ERROR = "internal_error"


class TransactionSemantics(str, Enum):
    """Transaction boundary required by a transition."""

    ADMISSION = "admission"
    ROW_LOCKED = "row_locked"
    OWNERSHIP_GUARDED = "ownership_guarded"


TERMINAL_OPERATION_STATES = frozenset(
    {
        OperationState.SUCCEEDED,
        OperationState.FAILED,
        OperationState.CANCELLED,
        OperationState.EXPIRED,
    }
)
TERMINAL_ATTEMPT_STATES = frozenset(
    {
        AttemptState.SUCCEEDED,
        AttemptState.FAILED,
        AttemptState.ABANDONED,
        AttemptState.CANCELLED,
    }
)


@dataclass(frozen=True)
class TransitionRule:
    """One legal operation transition and its enforcement requirements."""

    source: OperationState | None
    event: OperationEvent
    target: OperationState
    preconditions: tuple[str, ...]
    ownership_required: bool
    transaction_semantics: TransactionSemantics
    retryable: bool

    @property
    def terminal(self) -> bool:
        return self.target in TERMINAL_OPERATION_STATES


def _rule(
    source: OperationState | None,
    event: OperationEvent,
    target: OperationState,
    *preconditions: str,
    ownership: bool = False,
    transaction: TransactionSemantics = TransactionSemantics.ROW_LOCKED,
    retryable: bool = False,
) -> TransitionRule:
    return TransitionRule(
        source=source,
        event=event,
        target=target,
        preconditions=preconditions,
        ownership_required=ownership,
        transaction_semantics=transaction,
        retryable=retryable,
    )


TRANSITION_RULES = (
    _rule(
        None,
        OperationEvent.ADMITTED,
        OperationState.READY,
        "registered action and valid command",
        "unique or identical idempotency identity",
        transaction=TransactionSemantics.ADMISSION,
    ),
    _rule(
        None,
        OperationEvent.ADMITTED,
        OperationState.WAITING_FOR_APPROVAL,
        "registered action and valid command",
        "approval required",
        "unique or identical idempotency identity",
        transaction=TransactionSemantics.ADMISSION,
    ),
    _rule(
        OperationState.WAITING_FOR_APPROVAL,
        OperationEvent.APPROVED,
        OperationState.READY,
        "current approver authorized",
        "decision binding and expiry valid",
    ),
    _rule(
        OperationState.WAITING_FOR_APPROVAL,
        OperationEvent.REJECTED,
        OperationState.CANCELLED,
        "current approver authorized",
    ),
    _rule(
        OperationState.WAITING_FOR_APPROVAL,
        OperationEvent.CANCELLATION_REQUESTED,
        OperationState.CANCELLED,
        "current requester authorized",
    ),
    _rule(
        OperationState.WAITING_FOR_APPROVAL,
        OperationEvent.DEADLINE_EXPIRED,
        OperationState.EXPIRED,
        "database time is past deadline",
    ),
    _rule(
        OperationState.READY,
        OperationEvent.CLAIMED,
        OperationState.RUNNING,
        "eligible by database time",
        "deadline and cancellation permit execution",
        "attempt budget remains",
        "required approval is valid",
    ),
    _rule(
        OperationState.READY,
        OperationEvent.CANCELLATION_REQUESTED,
        OperationState.CANCELLED,
        "current requester authorized",
    ),
    _rule(
        OperationState.READY,
        OperationEvent.DEADLINE_EXPIRED,
        OperationState.EXPIRED,
        "database time is past deadline",
    ),
    _rule(
        OperationState.READY,
        OperationEvent.APPROVAL_EXPIRED,
        OperationState.EXPIRED,
        "unconsumed approval expired before the first attempt",
    ),
    _rule(
        OperationState.RUNNING,
        OperationEvent.HEARTBEAT,
        OperationState.RUNNING,
        "full ownership identity matches",
        "lease is unexpired",
        ownership=True,
        transaction=TransactionSemantics.OWNERSHIP_GUARDED,
    ),
    _rule(
        OperationState.RUNNING,
        OperationEvent.CANCELLATION_REQUESTED,
        OperationState.RUNNING,
        "current requester authorized",
    ),
    _rule(
        OperationState.RUNNING,
        OperationEvent.LEASE_RECLAIMED,
        OperationState.RUNNING,
        "database time proves prior lease expired",
        "old attempt abandoned and new attempt created",
        transaction=TransactionSemantics.ROW_LOCKED,
        retryable=True,
    ),
    _rule(
        OperationState.RUNNING,
        OperationEvent.RETRY_SCHEDULED,
        OperationState.READY,
        "full ownership identity matches",
        "attempt and deadline budget remain",
        ownership=True,
        transaction=TransactionSemantics.OWNERSHIP_GUARDED,
        retryable=True,
    ),
    _rule(
        OperationState.RUNNING,
        OperationEvent.TERMINAL_FAILURE,
        OperationState.FAILED,
        "full ownership identity matches",
        ownership=True,
        transaction=TransactionSemantics.OWNERSHIP_GUARDED,
    ),
    _rule(
        OperationState.RUNNING,
        OperationEvent.CANCELLATION_OBSERVED,
        OperationState.CANCELLED,
        "full ownership identity matches",
        "framework-controlled effect has not committed",
        ownership=True,
        transaction=TransactionSemantics.OWNERSHIP_GUARDED,
    ),
    _rule(
        OperationState.RUNNING,
        OperationEvent.SUCCEEDED,
        OperationState.SUCCEEDED,
        "full ownership identity matches",
        "current authorization and approval are valid",
        "same-database effect and finalization share one commit when classified atomic",
        ownership=True,
        transaction=TransactionSemantics.OWNERSHIP_GUARDED,
    ),
)

_TRANSITIONS_BY_SOURCE_EVENT: dict[
    tuple[OperationState | None, OperationEvent], tuple[TransitionRule, ...]
] = {}
for _transition in TRANSITION_RULES:
    _key = (_transition.source, _transition.event)
    _TRANSITIONS_BY_SOURCE_EVENT[_key] = (
        *_TRANSITIONS_BY_SOURCE_EVENT.get(_key, ()),
        _transition,
    )


class InvalidOperationTransition(ValueError):
    """Raised when an event is not legal from the current state."""


def transition_rule(
    source: OperationState | None,
    event: OperationEvent,
    *,
    target: OperationState | None = None,
) -> TransitionRule:
    """Return the unique matching rule or fail deterministically."""

    candidates = _TRANSITIONS_BY_SOURCE_EVENT.get((source, event), ())
    if target is not None:
        candidates = tuple(rule for rule in candidates if rule.target is target)
    if len(candidates) == 1:
        return candidates[0]

    source_label = "none" if source is None else source.value
    target_label = "" if target is None else f" -> {target.value}"
    if not candidates:
        raise InvalidOperationTransition(
            f"Invalid durable operation transition: {source_label} + {event.value}{target_label}"
        )
    raise InvalidOperationTransition(
        f"Ambiguous durable operation transition: {source_label} + {event.value}; "
        "a target state is required"
    )


__all__ = [
    "TERMINAL_ATTEMPT_STATES",
    "TERMINAL_OPERATION_STATES",
    "TRANSITION_RULES",
    "AttemptState",
    "FailureReason",
    "InvalidOperationTransition",
    "OperationEvent",
    "OperationState",
    "TransactionSemantics",
    "TransitionRule",
    "transition_rule",
]
