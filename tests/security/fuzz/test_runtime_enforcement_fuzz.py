from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from aksara.security.enforcement import enforce_payload_policy
from aksara.security.exceptions import PolicyDenied

from .conftest import FUZZ_SETTINGS


pytestmark = [pytest.mark.security, pytest.mark.fuzz]


FIELD_NAME_VARIANTS = [
    "tenant_id",
    "Tenant_Id",
    "TENANT_ID",
    "tenant.id",
    "tenant_id ",
    " tenant_id",
    "tenant_id\0",
    "tenant_id.__class__",
    "tenant_id[0]",
    "tenant_id->>'x'",
]


@pytest.mark.parametrize("field_name", FIELD_NAME_VARIANTS)
def test_runtime_enforcement_fuzz_forbidden_field_variants(user_principal, policy_model, field_name):
    with pytest.raises(PolicyDenied) as exc_info:
        enforce_payload_policy(
            principal=user_principal,
            action="update",
            model=policy_model,
            payload={"name": "ok", field_name: "tenant-b"},
        )

    assert field_name in exc_info.value.denied_fields


@pytest.mark.parametrize("field_name", FIELD_NAME_VARIANTS)
def test_runtime_enforcement_fuzz_tenant_id_variants(mcp_principal, policy_model, field_name):
    with pytest.raises(PolicyDenied) as exc_info:
        enforce_payload_policy(
            principal=mcp_principal,
            action="update",
            model=policy_model,
            payload={field_name: "tenant-b"},
        )

    assert field_name in exc_info.value.denied_fields


@FUZZ_SETTINGS
@given(value=st.one_of(st.text(max_size=256), st.booleans(), st.integers()))
def test_runtime_enforcement_fuzz_ai_agent_writable_false_never_allowed(
    ai_principal,
    policy_model,
    value,
):
    with pytest.raises(PolicyDenied) as exc_info:
        enforce_payload_policy(
            principal=ai_principal,
            action="update",
            model=policy_model,
            payload={"locked_note": value},
        )

    assert "locked_note" in exc_info.value.denied_fields


def test_runtime_enforcement_fuzz_read_only_fields_never_allowed(user_principal, policy_model):
    with pytest.raises(PolicyDenied) as exc_info:
        enforce_payload_policy(
            principal=user_principal,
            action="update",
            model=policy_model,
            payload={"created_at": "2026-01-01T00:00:00Z"},
        )

    assert "created_at" in exc_info.value.denied_fields


def test_runtime_enforcement_fuzz_system_only_fields_never_allowed_for_user(
    user_principal,
    policy_model,
):
    with pytest.raises(PolicyDenied) as exc_info:
        enforce_payload_policy(
            principal=user_principal,
            action="update",
            model=policy_model,
            payload={"system_flag": True},
        )

    assert "system_flag" in exc_info.value.denied_fields


def test_runtime_enforcement_fuzz_nested_payload_does_not_bypass_top_level_policy(
    user_principal,
    policy_model,
):
    payload = {"metadata": {"items": [{"tenant_id": "tenant-b"}]}}

    with pytest.raises(PolicyDenied) as exc_info:
        enforce_payload_policy(
            principal=user_principal,
            action="update",
            model=policy_model,
            payload=payload,
        )

    assert "metadata.items[0].tenant_id" in exc_info.value.denied_fields


def test_runtime_enforcement_fuzz_malformed_payload_shape_fails_safely(
    user_principal,
    policy_model,
):
    with pytest.raises(PolicyDenied):
        enforce_payload_policy(
            principal=user_principal,
            action="update",
            model=policy_model,
            payload=["tenant_id", "tenant-b"],  # type: ignore[arg-type]
        )


def test_oversized_string_payload_fails_safely(user_principal, policy_model):
    payload = {"name": "x" * 100_000, "tenant_id": "tenant-b"}

    with pytest.raises(PolicyDenied) as exc_info:
        enforce_payload_policy(
            principal=user_principal,
            action="update",
            model=policy_model,
            payload=payload,
        )

    assert "tenant_id" in exc_info.value.denied_fields


def test_deeply_nested_payload_fails_safely(user_principal, policy_model):
    current = nested = {}
    for _ in range(20):
        current["child"] = {}
        current = current["child"]
    current["tenant_id"] = "tenant-b"

    with pytest.raises(PolicyDenied):
        enforce_payload_policy(
            principal=user_principal,
            action="update",
            model=policy_model,
            payload={"metadata": nested},
        )


def test_many_extra_fields_payload_fails_safely(user_principal, policy_model):
    payload = {f"extra_{i}": i for i in range(200)}
    payload["name"] = "ok"

    with pytest.raises(PolicyDenied) as exc_info:
        enforce_payload_policy(
            principal=user_principal,
            action="update",
            model=policy_model,
            payload=payload,
        )

    assert "extra_0" in exc_info.value.denied_fields
