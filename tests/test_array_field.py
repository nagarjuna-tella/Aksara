"""
Tests for Array Field

Tests the Array field type for PostgreSQL arrays.
"""

import pytest
import uuid as uuid_lib
from aksara.fields import Array


def test_array_field_initialization():
    """Test Array field initialization."""
    field = Array(item_type=str)
    
    assert field.item_type == str
    assert field.nullable == True  # Default for Array
    assert field.sql_type == "TEXT[]"


def test_array_field_sql_types():
    """Test Array field SQL type mapping."""
    # String arrays
    str_field = Array(item_type=str)
    assert str_field.sql_type == "TEXT[]"
    
    # Integer arrays
    int_field = Array(item_type=int)
    assert int_field.sql_type == "INTEGER[]"
    
    # Float arrays
    float_field = Array(item_type=float)
    assert float_field.sql_type == "DOUBLE PRECISION[]"
    
    # Boolean arrays
    bool_field = Array(item_type=bool)
    assert bool_field.sql_type == "BOOLEAN[]"
    
    # UUID arrays
    uuid_field = Array(item_type=uuid_lib.UUID)
    assert uuid_field.sql_type == "UUID[]"


def test_array_field_to_python():
    """Test Array field conversion to Python."""
    field = Array(item_type=str)
    
    # List input (most common from asyncpg)
    assert field.to_python(['a', 'b', 'c']) == ['a', 'b', 'c']
    
    # None input
    assert field.to_python(None) is None
    
    # String input (PostgreSQL format)
    assert field.to_python('{a,b,c}') == ['a', 'b', 'c']
    
    # Empty array
    assert field.to_python('{}') == []
    assert field.to_python([]) == []


def test_array_field_to_python_int():
    """Test Array field conversion for integers."""
    field = Array(item_type=int)
    
    assert field.to_python([1, 2, 3]) == [1, 2, 3]
    assert field.to_python('{1,2,3}') == [1, 2, 3]


def test_array_field_to_python_bool():
    """Test Array field conversion for booleans."""
    field = Array(item_type=bool)
    
    assert field.to_python([True, False, True]) == [True, False, True]
    assert field.to_python('{true,false,true}') == [True, False, True]


def test_array_field_to_db():
    """Test Array field conversion to database (list-only core ORM)."""
    field = Array(item_type=str)

    # List to list (asyncpg handles this)
    assert field.to_db(['a', 'b', 'c']) == ['a', 'b', 'c']

    # None (nullable by default)
    assert field.to_db(None) is None

    # Empty list means an empty array, not NULL
    assert field.to_db([]) == []


def test_array_field_to_db_int():
    """Test Array field conversion for integers to database."""
    field = Array(item_type=int)

    assert field.to_db([1, 2, 3]) == [1, 2, 3]


def test_array_field_to_db_rejects_strings():
    """v0.5.55: core ORM no longer parses delimited strings into arrays."""
    field = Array(item_type=str)

    with pytest.raises(ValueError, match="requires a Python list"):
        field.to_db('a,b,c')
    with pytest.raises(ValueError, match="requires a Python list"):
        field.to_db('')


def test_array_field_default_list():
    """Test Array field with default list."""
    field = Array(item_type=str, default=['tag1', 'tag2'])
    
    assert field.default == ['tag1', 'tag2']


def test_array_field_default_callable():
    """Test Array field with callable default."""
    field = Array(item_type=str, default=list)
    
    assert callable(field.default)
    assert field.get_default_value() == []


def test_array_field_format_default_empty():
    """Test Array field formats empty default."""
    field = Array(item_type=str, default=[])
    
    formatted = field._format_default()
    assert formatted == "'{}'"


def test_array_field_format_default_strings():
    """Test Array field formats string array default."""
    field = Array(item_type=str, default=['apple', 'banana'])
    
    formatted = field._format_default()
    assert "ARRAY[" in formatted
    assert "'apple'" in formatted
    assert "'banana'" in formatted


def test_array_field_format_default_integers():
    """Test Array field formats integer array default."""
    field = Array(item_type=int, default=[1, 2, 3])
    
    formatted = field._format_default()
    assert "ARRAY[" in formatted
    assert "1,2,3" in formatted


def test_array_field_format_default_booleans():
    """Test Array field formats boolean array default."""
    field = Array(item_type=bool, default=[True, False])
    
    formatted = field._format_default()
    assert "ARRAY[" in formatted
    assert "TRUE" in formatted
    assert "FALSE" in formatted


def test_array_field_nullable():
    """Test Array field nullable attribute."""
    nullable_field = Array(item_type=str, nullable=True)
    assert nullable_field.nullable is True
    
    not_null_field = Array(item_type=str, nullable=False)
    assert not_null_field.nullable is False


def test_array_field_ai_metadata():
    """Test Array field AI metadata."""
    field = Array(
        item_type=str,
        ai_description="User tags",
        ai_sensitive=False,
        ai_agent_writable=True,
    )
    field.name = "tags"
    
    metadata = field.get_ai_metadata()
    assert metadata["name"] == "tags"
    assert metadata["type"] == "Array"
    assert metadata["description"] == "User tags"
    assert metadata["sensitive"] is False
    assert metadata["agent_writable"] is True


def test_array_field_float_conversion():
    """Test Array field handles float arrays (mixed int/float allowed)."""
    field = Array(item_type=float)

    assert field.to_db([1.5, 2.5, 3.5]) == [1.5, 2.5, 3.5]
    assert field.to_db([1, 2.5]) == [1.0, 2.5]


# ---------------------------------------------------------------------------
# v0.5.55 Advanced Field Policy: item validation
# ---------------------------------------------------------------------------


def test_array_int_rejects_non_integral_float():
    field = Array(item_type=int)
    with pytest.raises(ValueError, match="integral"):
        field.to_db([1.9])


def test_array_int_rejects_bool():
    field = Array(item_type=int)
    with pytest.raises(ValueError, match="boolean"):
        field.to_db([True])


def test_array_int_accepts_integral_float():
    field = Array(item_type=int)
    assert field.to_db([2.0, 3]) == [2, 3]


def test_array_int_accepts_32bit_bounds():
    field = Array(item_type=int)
    assert field.to_db([2147483647]) == [2147483647]
    assert field.to_db([-2147483648]) == [-2147483648]


def test_array_int_rejects_above_max():
    field = Array(item_type=int)
    with pytest.raises(ValueError, match="range"):
        field.to_db([2147483648])


def test_array_int_rejects_below_min():
    field = Array(item_type=int)
    with pytest.raises(ValueError, match="range"):
        field.to_db([-2147483649])


def test_array_int_rejects_large_python_int():
    field = Array(item_type=int)
    with pytest.raises(ValueError, match="range"):
        field.to_db([2 ** 40])


def test_array_int_rejects_out_of_range_decimal():
    from decimal import Decimal

    field = Array(item_type=int)
    with pytest.raises(ValueError, match="range"):
        field.to_db([Decimal("2147483648")])


def test_array_float_rejects_nan():
    field = Array(item_type=float)
    with pytest.raises(ValueError, match="finite"):
        field.to_db([float("nan")])


def test_array_float_rejects_infinity():
    field = Array(item_type=float)
    with pytest.raises(ValueError, match="finite"):
        field.to_db([float("inf")])


def test_array_bool_accepts_real_bools():
    field = Array(item_type=bool)
    assert field.to_db([True, False]) == [True, False]


def test_array_bool_rejects_strings():
    field = Array(item_type=bool)
    with pytest.raises(ValueError, match="bool items"):
        field.to_db(["false"])


def test_array_str_accepts_strings():
    field = Array(item_type=str)
    assert field.to_db(["a"]) == ["a"]


def test_array_str_rejects_non_strings():
    field = Array(item_type=str)
    with pytest.raises(ValueError, match="str items"):
        field.to_db([1])


def test_array_uuid_accepts_uuid_strings():
    field = Array(item_type=uuid_lib.UUID)
    raw = "12345678-1234-5678-1234-567812345678"
    result = field.to_db([raw])
    assert result == [uuid_lib.UUID(raw)]


def test_array_uuid_accepts_uuid_instances():
    field = Array(item_type=uuid_lib.UUID)
    value = uuid_lib.uuid4()
    assert field.to_db([value]) == [value]


def test_array_uuid_rejects_invalid_string():
    field = Array(item_type=uuid_lib.UUID)
    with pytest.raises(ValueError, match="invalid UUID"):
        field.to_db(["not-a-uuid"])


def test_array_rejects_nested_lists():
    field = Array(item_type=int)
    with pytest.raises(ValueError, match="Nested Array"):
        field.to_db([[1, 2]])


def test_array_rejects_null_items():
    field = Array(item_type=str)
    with pytest.raises(ValueError, match="null items"):
        field.to_db([None])


def test_array_nullable_allows_none():
    field = Array(item_type=str, nullable=True)
    assert field.to_db(None) is None


def test_array_non_nullable_rejects_none():
    field = Array(item_type=str, nullable=False)
    with pytest.raises(ValueError, match="not nullable"):
        field.to_db(None)


def test_array_rejects_nested_item_type():
    with pytest.raises(ValueError, match="Nested Array"):
        Array(item_type=list)
    with pytest.raises(ValueError, match="Nested Array"):
        Array(item_type=Array(item_type=int))


def test_array_rejects_tuple_value():
    field = Array(item_type=int)
    with pytest.raises(ValueError, match="requires a list"):
        field.to_db((1, 2))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
