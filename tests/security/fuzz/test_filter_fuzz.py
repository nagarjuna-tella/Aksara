from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from aksara.api.filters import DjangoFilterBackend
from aksara.api.viewsets import ModelViewSet
from aksara.manager import QuerySet

from .conftest import FUZZ_SETTINGS, MALICIOUS_IDENTIFIERS, FakeRequest, FakeState, FuzzAccount


pytestmark = [pytest.mark.security, pytest.mark.fuzz]


class FuzzAccountViewSet(ModelViewSet):
    model = FuzzAccount
    prefix = "/security-fuzz-accounts"
    filter_backends = [DjangoFilterBackend]
    filterable_fields = ["name", "tenant_id", "metadata"]


@pytest.mark.parametrize("field_name", MALICIOUS_IDENTIFIERS)
def test_filter_fuzz_rejects_unknown_or_unsafe_fields(field_name):
    qs = QuerySet(FuzzAccount).filter(**{field_name: "value"})

    if field_name in {"tenant_id", "metadata__tenant_id"}:
        where, values = qs._build_where_clause()
        assert "$" in where
        assert "value" in values or "tenant_id" in values
        return

    with pytest.raises((ValueError, TypeError)):
        qs._build_where_clause()


def test_filter_fuzz_does_not_allow_tenant_filter_override(user_principal):
    view = FuzzAccountViewSet()
    request = FakeRequest(
        query_params={"tenant_id": "tenant-b"},
        state=FakeState(principal=user_principal),
    )

    queryset = view.get_queryset(request=request, tenant_id="tenant-b")

    assert queryset._filters["tenant_id"] == "tenant-a"


@pytest.mark.parametrize(
    "value",
    [
        "' OR '1'='1",
        '"; SELECT * FROM users; --',
        "tenant-b",
        "x%'; DROP TABLE accounts; --",
    ],
)
def test_filter_fuzz_sql_like_values_are_treated_as_values_not_identifiers(value):
    qs = QuerySet(FuzzAccount).filter(name=value)

    where, values = qs._build_where_clause()

    assert where == 'WHERE "name" = $1'
    assert values == [value]
    assert value not in where


@pytest.mark.parametrize("field_name", MALICIOUS_IDENTIFIERS)
def test_filter_fuzz_never_generates_unescaped_identifier_for_unknown_field(field_name):
    qs = QuerySet(FuzzAccount).filter(**{field_name: "x"})

    try:
        where, values = qs._build_where_clause()
    except (ValueError, TypeError):
        return

    if field_name == "tenant_id":
        assert where == 'WHERE "tenant_id" = $1'
        assert values == ["x"]
        return

    assert field_name not in where
    assert all(str(part) not in where for part in ("DROP TABLE", " OR 1=1", ";--"))
    assert values


@FUZZ_SETTINGS
@given(field_name=st.text(min_size=0, max_size=128), value=st.text(max_size=128))
def test_filter_fuzz_malformed_input_fails_safely(field_name, value):
    qs = QuerySet(FuzzAccount).filter(**{field_name: value})

    try:
        where, values = qs._build_where_clause()
    except (ValueError, TypeError, AttributeError):
        return

    assert "DROP TABLE" not in where.upper()
    assert ";" not in where
    if value:
        assert value in values or f"%{value}%" in values
