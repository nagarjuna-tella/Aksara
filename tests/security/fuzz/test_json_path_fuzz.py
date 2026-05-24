from __future__ import annotations

import re

import pytest
from hypothesis import given, strategies as st

from aksara.manager import QuerySet

from .conftest import FUZZ_SETTINGS, MALICIOUS_IDENTIFIERS, FuzzAccount


pytestmark = [pytest.mark.security, pytest.mark.fuzz]

_POSTGRES_PLACEHOLDER_RE = re.compile(r"\$\d+\b")
_SAFE_STRUCTURAL_SQL = (
    '"metadata"',
    "WHERE",
    "AND",
    "OR",
    "NOT",
    "IS",
    "NULL",
    "->>",
    "->",
    "#>>",
    "#>",
    "=",
    "(",
    ")",
    ",",
)


def _sql_without_safe_parameter_markers(where: str) -> str:
    """Remove SQL emitted by the query builder, not user-controlled content."""
    stripped = _POSTGRES_PLACEHOLDER_RE.sub("", where)
    for token in _SAFE_STRUCTURAL_SQL:
        stripped = stripped.replace(token, "")
    return stripped


def assert_raw_input_not_in_sql(raw_input: str, where: str) -> None:
    """
    Assert raw user input was parameterized instead of embedded in SQL.

    PostgreSQL placeholders such as ``$1`` are safe bind markers. Known quoted
    structural identifiers emitted by the query builder are also not attacker
    input, even when a generated fuzz value happens to match their text.
    """
    if not raw_input or raw_input.isspace():
        return
    searchable_sql = _sql_without_safe_parameter_markers(where)
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", raw_input):
        leaked_identifier = re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(raw_input)}(?![A-Za-z0-9_])",
            searchable_sql,
        )
        assert leaked_identifier is None
    else:
        assert raw_input not in searchable_sql


@pytest.mark.parametrize("path_fragment", MALICIOUS_IDENTIFIERS)
def test_json_path_fuzz_rejects_unsafe_path_fragments(path_fragment):
    qs = QuerySet(FuzzAccount).filter(**{f"name__{path_fragment}": "x"})

    with pytest.raises(ValueError):
        qs._build_where_clause()


def test_json_path_fuzz_deep_paths_fail_safely():
    key = "metadata__" + "__".join(f"k{i}" for i in range(50))
    qs = QuerySet(FuzzAccount).filter(**{key: "value"})

    where, values = qs._build_where_clause()

    assert "metadata" in where
    assert where.count("->") >= 49
    assert values[-1] == "value"


@pytest.mark.parametrize("path_fragment", MALICIOUS_IDENTIFIERS)
def test_json_path_fuzz_sql_like_paths_not_used_as_raw_sql(path_fragment):
    qs = QuerySet(FuzzAccount).filter(**{f"metadata__{path_fragment}": "value"})

    where, values = qs._build_where_clause()

    if path_fragment:
        assert_raw_input_not_in_sql(path_fragment, where)
    assert "DROP TABLE" not in where.upper()
    assert ";" not in where
    assert all(segment in values for segment in path_fragment.split("__"))
    assert "value" in values


@FUZZ_SETTINGS
@given(path_fragment=st.text(min_size=0, max_size=64), value=st.text(max_size=128))
def test_json_path_fuzz_generated_paths_are_parameterized(path_fragment, value):
    qs = QuerySet(FuzzAccount).filter(**{f"metadata__{path_fragment}": value})

    try:
        where, values = qs._build_where_clause()
    except ValueError:
        return

    if path_fragment:
        assert_raw_input_not_in_sql(path_fragment, where)
    if value:
        assert_raw_input_not_in_sql(value, where)
    assert value in values


def test_json_path_fuzz_placeholder_number_is_not_raw_input_leakage():
    where = 'WHERE "metadata" ->> $1 = $2'

    assert_raw_input_not_in_sql("1", where)


def test_json_path_fuzz_sql_injection_fragment_not_embedded_raw():
    path_fragment = "tenant_id; DROP TABLE users; --"
    qs = QuerySet(FuzzAccount).filter(**{f"metadata__{path_fragment}": "value"})

    where, values = qs._build_where_clause()

    assert_raw_input_not_in_sql(path_fragment, where)
    assert "DROP TABLE" not in where.upper()
    assert ";" not in where
    assert path_fragment in values


def test_json_path_fuzz_sql_operator_path_not_embedded_raw():
    path_fragment = "metadata->>'tenant_id'"
    qs = QuerySet(FuzzAccount).filter(**{f"metadata__{path_fragment}": "value"})

    where, values = qs._build_where_clause()

    assert_raw_input_not_in_sql(path_fragment, where)
    assert "->>'tenant_id'" not in where
    assert path_fragment in values
