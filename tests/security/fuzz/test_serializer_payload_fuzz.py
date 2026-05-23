from __future__ import annotations

import pytest
from hypothesis import given

from aksara.security.enforcement import enforce_payload_policy
from aksara.security.exceptions import PolicyDenied

from .conftest import FUZZ_SETTINGS, PAYLOADS, FuzzAccount, FuzzAccountSerializer


pytestmark = [pytest.mark.security, pytest.mark.fuzz]


def test_serializer_fuzz_forbidden_fields_rejected_or_ignored_safely(ai_principal, policy_model):
    payload = {
        "name": "ok",
        "tenant_id": "tenant-b",
        "locked_note": "override",
        "created_at": "2026-01-01T00:00:00Z",
    }

    with pytest.raises(PolicyDenied) as exc_info:
        enforce_payload_policy(
            principal=ai_principal,
            action="update",
            model=policy_model,
            payload=payload,
        )

    assert {"tenant_id", "locked_note", "created_at"} <= set(exc_info.value.denied_fields)


def test_serializer_fuzz_extra_fields_do_not_mutate_model():
    serializer = FuzzAccountSerializer(
        data={
            "name": "visible",
            "status": "draft",
            "not_a_field": "must not survive",
            "tenant_id.raw": "tenant-b",
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert "not_a_field" not in serializer.validated_data
    assert "tenant_id.raw" not in serializer.validated_data


def test_serializer_fuzz_nested_forbidden_fields_do_not_bypass_policy(user_principal, policy_model):
    payload = {
        "name": "visible",
        "metadata": {
            "tenant_id": "tenant-b",
            "children": [{"created_at": "yesterday"}],
        },
    }

    with pytest.raises(PolicyDenied) as exc_info:
        enforce_payload_policy(
            principal=user_principal,
            action="update",
            model=policy_model,
            payload=payload,
        )

    denied = set(exc_info.value.denied_fields)
    assert "metadata.tenant_id" in denied
    assert "metadata.children[0].created_at" in denied


def test_serializer_fuzz_large_strings_fail_safely():
    large_value = "x" * 100_000
    serializer = FuzzAccountSerializer(data={"name": large_value})

    assert serializer.is_valid(), serializer.errors
    with pytest.raises(ValueError, match="too long"):
        FuzzAccount._fields["name"].to_db(serializer.validated_data["name"])


def test_serializer_fuzz_malformed_shapes_fail_safely():
    serializer = FuzzAccountSerializer(data={"name": {"not": "a string"}})

    assert serializer.is_valid() is False
    assert serializer.errors


@FUZZ_SETTINGS
@given(payload=PAYLOADS)
def test_serializer_fuzz_payload_keys_never_mutate_forbidden_fields(payload, user_principal, policy_model):
    payload.setdefault("name", "safe")

    try:
        enforce_payload_policy(
            principal=user_principal,
            action="update",
            model=policy_model,
            payload=payload,
        )
    except PolicyDenied as exc:
        assert any(field not in {"name", "metadata"} for field in exc.denied_fields)
        return

    assert "tenant_id" not in payload
    assert "created_at" not in payload
    assert "system_flag" not in payload
