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
    """Test Array field conversion to database."""
    field = Array(item_type=str)
    
    # List to list (asyncpg handles this)
    assert field.to_db(['a', 'b', 'c']) == ['a', 'b', 'c']
    
    # None
    assert field.to_db(None) is None
    
    # Empty list
    assert field.to_db([]) == []
    
    # Comma-separated string
    assert field.to_db('a,b,c') == ['a', 'b', 'c']


def test_array_field_to_db_int():
    """Test Array field conversion for integers to database."""
    field = Array(item_type=int)
    
    assert field.to_db([1, 2, 3]) == [1, 2, 3]
    assert field.to_db('1,2,3') == [1, 2, 3]


def test_array_field_to_db_empty_string():
    """Test Array field handles empty strings."""
    field = Array(item_type=str)
    
    assert field.to_db('') == []
    assert field.to_db('   ') == []


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


def test_array_field_handles_whitespace():
    """Test Array field handles whitespace in strings."""
    field = Array(item_type=str)
    
    # Comma-separated with spaces
    result = field.to_db('apple, banana, cherry')
    assert result == ['apple', 'banana', 'cherry']


def test_array_field_float_conversion():
    """Test Array field handles float arrays."""
    field = Array(item_type=float)
    
    assert field.to_db([1.5, 2.5, 3.5]) == [1.5, 2.5, 3.5]
    assert field.to_db('1.5,2.5,3.5') == [1.5, 2.5, 3.5]


def test_array_field_bool_conversion_variants():
    """Test Array field handles various boolean string formats."""
    field = Array(item_type=bool)
    
    # Various true values
    result = field.to_db('true,1,yes')
    assert result == [True, True, True]
    
    # Various false values
    result = field.to_db('false,0,no')
    assert result == [False, False, False]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
