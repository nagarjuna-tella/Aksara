from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from aksara.security.enforcement import (
    validate_bulk_payload_policy,
    validate_upsert_payload_policy,
)
from aksara.security.exceptions import PolicyDenied

from .conftest import FUZZ_SETTINGS


pytestmark = [pytest.mark.security, pytest.mark.fuzz]


def test_bulk_payload_fuzz_any_item_with_forbidden_field_denies_whole_batch(
    user_principal,
    policy_model,
):
    with pytest.raises(PolicyDenied) as exc_info:
        validate_bulk_payload_policy(
            principal=user_principal,
            action="update",
            model=policy_model,
            payloads=[{"name": "a"}, {"name": "b", "tenant_id": "tenant-b"}],
        )

    assert "tenant_id" in exc_info.value.denied_fields
    assert exc_info.value.decision.metadata["denied_items"] == (1,)


def test_bulk_payload_fuzz_reports_denied_fields(user_principal, policy_model):
    with pytest.raises(PolicyDenied) as exc_info:
        validate_bulk_payload_policy(
            principal=user_principal,
            action="update",
            model=policy_model,
            payloads=[{"created_at": "now"}, {"system_flag": True}],
        )

    assert {"created_at", "system_flag"} <= set(exc_info.value.denied_fields)


def test_bulk_payload_fuzz_empty_batch_safe(user_principal, policy_model):
    decision = validate_bulk_payload_policy(
        principal=user_principal,
        action="update",
        model=policy_model,
        payloads=[],
    )

    assert decision.allowed
    assert decision.metadata["items"] == 0


def test_upsert_payload_fuzz_forbidden_insert_field_denied(user_principal, policy_model):
    with pytest.raises(PolicyDenied) as exc_info:
        validate_upsert_payload_policy(
            principal=user_principal,
            model=policy_model,
            insert_payload={"name": "safe", "tenant_id": "tenant-b"},
            update_payload={"name": "safe"},
            conflict_target=("name",),
        )

    assert "tenant_id" in exc_info.value.denied_fields


def test_upsert_payload_fuzz_forbidden_update_field_denied(ai_principal, policy_model):
    with pytest.raises(PolicyDenied) as exc_info:
        validate_upsert_payload_policy(
            principal=ai_principal,
            model=policy_model,
            insert_payload={"name": "safe"},
            update_payload={"locked_note": "override"},
            conflict_target=("name",),
        )

    assert "locked_note" in exc_info.value.denied_fields


@pytest.mark.parametrize(
    "target",
    ["name; DROP TABLE users; --", "tenant_id->>'x'", "__class__", "missing"],
)
def test_upsert_payload_fuzz_conflict_target_unsafe_identifier_rejected_if_helper_exists(
    user_principal,
    policy_model,
    target,
):
    with pytest.raises(PolicyDenied) as exc_info:
        validate_upsert_payload_policy(
            principal=user_principal,
            model=policy_model,
            insert_payload={"name": "safe"},
            conflict_target=(target,),
        )

    assert target in exc_info.value.denied_fields


@FUZZ_SETTINGS
@given(
    batch=st.lists(
        st.dictionaries(
            keys=st.text(min_size=0, max_size=32),
            values=st.one_of(st.none(), st.text(max_size=64), st.integers()),
            max_size=6,
        ),
        max_size=6,
    )
)
def test_bulk_payload_fuzz_malformed_batch_shapes_fail_safely(
    user_principal,
    policy_model,
    batch,
):
    try:
        decision = validate_bulk_payload_policy(
            principal=user_principal,
            action="update",
            model=policy_model,
            payloads=batch,
        )
    except PolicyDenied as exc:
        assert exc.denied_fields
        return

    assert decision.allowed
    for item in batch:
        assert set(item) <= {"name", "metadata", "locked_note", "secret_note"}
