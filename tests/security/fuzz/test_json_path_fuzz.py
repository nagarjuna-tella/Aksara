from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from aksara.manager import QuerySet

from .conftest import FUZZ_SETTINGS, MALICIOUS_IDENTIFIERS, FuzzAccount


pytestmark = [pytest.mark.security, pytest.mark.fuzz]


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
        assert path_fragment not in where
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
        assert path_fragment not in where
    if value:
        assert value not in where
    assert value in values
