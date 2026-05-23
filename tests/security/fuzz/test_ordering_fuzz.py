from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from aksara.api.filters import OrderingFilter
from aksara.api.viewsets import ModelViewSet
from aksara.manager import QuerySet

from .conftest import FUZZ_SETTINGS, MALICIOUS_IDENTIFIERS, FakeRequest, FakeState, FuzzAccount


pytestmark = [pytest.mark.security, pytest.mark.fuzz]


class FuzzOrderingViewSet(ModelViewSet):
    model = FuzzAccount
    prefix = "/security-fuzz-ordering"
    ordering_fields = ["name", "status", "tenant_id", "secret_note"]


def test_ordering_fuzz_rejects_unknown_fields():
    for field_name in MALICIOUS_IDENTIFIERS:
        if field_name in FuzzAccount._fields or field_name == "id":
            continue
        with pytest.raises(Exception):
            QuerySet(FuzzAccount).order_by(field_name)


@pytest.mark.parametrize("field_name", MALICIOUS_IDENTIFIERS)
def test_ordering_fuzz_rejects_sql_fragments(field_name):
    view = FuzzOrderingViewSet()
    request = FakeRequest(query_params={"ordering": field_name})
    qs = OrderingFilter().filter_queryset(request, QuerySet(FuzzAccount), view)

    assert qs._order_by is None


def test_ordering_fuzz_rejects_hidden_or_sensitive_fields_if_policy_denies(ai_principal):
    view = FuzzOrderingViewSet()
    request = FakeRequest(
        query_params={"ordering": "secret_note"},
        state=FakeState(principal=ai_principal),
    )

    qs = OrderingFilter().filter_queryset(request, QuerySet(FuzzAccount), view)

    assert qs._order_by is None


def test_ordering_fuzz_does_not_allow_tenant_context_override(user_principal):
    view = FuzzOrderingViewSet()
    request = FakeRequest(
        query_params={"ordering": "tenant_id"},
        state=FakeState(principal=user_principal),
    )

    qs = OrderingFilter().filter_queryset(request, QuerySet(FuzzAccount), view)

    assert qs._order_by is None


def test_large_ordering_parameter_fails_safely():
    view = FuzzOrderingViewSet()
    request = FakeRequest(query_params={"ordering": "name" + (";DROP" * 10_000)})

    qs = OrderingFilter().filter_queryset(request, QuerySet(FuzzAccount), view)

    assert qs._order_by is None


@FUZZ_SETTINGS
@given(ordering=st.text(min_size=0, max_size=128))
def test_ordering_fuzz_malformed_values_fail_safely(ordering):
    view = FuzzOrderingViewSet()
    request = FakeRequest(query_params={"ordering": ordering})

    try:
        qs = OrderingFilter().filter_queryset(request, QuerySet(FuzzAccount), view)
        clause = qs._build_order_by_clause()
    except Exception:
        return

    assert "DROP TABLE" not in clause.upper()
    assert ";" not in clause
    if qs._order_by:
        assert all(field.lstrip("-") in FuzzAccount._fields or field.lstrip("-") == "id" for field in qs._order_by)
