"""State vocabulary contract for Durable Authorized Operations."""

import pytest

from aksara.durable.states import (
    TERMINAL_OPERATION_STATES,
    TRANSITION_RULES,
    InvalidOperationTransition,
    OperationEvent,
    OperationState,
    transition_rule,
)


def test_operation_state_vocabulary_is_closed():
    assert {state.value for state in OperationState} == {
        "waiting_for_approval",
        "ready",
        "running",
        "succeeded",
        "failed",
        "cancelled",
        "expired",
    }


def test_every_rule_has_enforcement_metadata():
    for rule in TRANSITION_RULES:
        assert rule.preconditions
        assert rule.transaction_semantics
        assert rule.terminal is (rule.target in TERMINAL_OPERATION_STATES)


@pytest.mark.parametrize("state", sorted(TERMINAL_OPERATION_STATES, key=lambda item: item.value))
@pytest.mark.parametrize("event", list(OperationEvent))
def test_terminal_states_never_reopen(state, event):
    with pytest.raises(InvalidOperationTransition):
        transition_rule(state, event)


def test_admission_target_must_disambiguate_approval_requirement():
    with pytest.raises(InvalidOperationTransition, match="target state is required"):
        transition_rule(None, OperationEvent.ADMITTED)

    ready = transition_rule(
        None,
        OperationEvent.ADMITTED,
        target=OperationState.READY,
    )
    waiting = transition_rule(
        None,
        OperationEvent.ADMITTED,
        target=OperationState.WAITING_FOR_APPROVAL,
    )
    assert ready.target is OperationState.READY
    assert waiting.target is OperationState.WAITING_FOR_APPROVAL


def test_retry_returns_to_ready_without_inventing_retrying_state():
    rule = transition_rule(OperationState.RUNNING, OperationEvent.RETRY_SCHEDULED)
    assert rule.target is OperationState.READY
    assert rule.retryable is True
    assert rule.ownership_required is True
