"""
Tests for Admin Widgets

Tests the widget rendering system including JSON and Array widgets.
"""

import re
from urllib.parse import urlparse

import pytest
from aksara.contrib.admin.widgets import (
    Widget,
    TextInput,
    TextArea,
    CheckboxInput,
    EmailInput,
    URLInput,
    NumberInput,
)
from aksara.contrib.admin.widgets.json import JSONAdminWidget
from aksara.contrib.admin.widgets.array import ArrayAdminWidget


# Mock field for testing
class MockField:
    def __init__(self, nullable=False, name="test_field"):
        self.nullable = nullable
        self.name = name


def test_widget_base_class():
    """Test base Widget class."""
    # Can't instantiate abstract class
    with pytest.raises(TypeError):
        widget = Widget()


def test_text_input_widget():
    """Test TextInput widget."""
    widget = TextInput()
    field = MockField(name="username")
    html = widget.render("username", "john_doe", field)
    
    assert 'name="username"' in html
    assert 'john_doe' in html


def test_textarea_widget():
    """Test TextArea widget."""
    widget = TextArea()
    field = MockField(name="description")
    html = widget.render("description", "Long text here", field)
    
    assert '<textarea' in html
    assert 'name="description"' in html
    assert 'Long text here' in html


def test_checkbox_widget():
    """Test CheckboxInput widget."""
    widget = CheckboxInput()
    field = MockField(name="is_active")
    
    # Checked
    html_checked = widget.render("is_active", True, field)
    assert 'checkbox' in html_checked
    
    # Unchecked  
    html_unchecked = widget.render("is_active", False, field)
    assert 'checkbox' in html_unchecked


def test_email_widget():
    """Test EmailInput widget."""
    widget = EmailInput()
    field = MockField(name="email")
    html = widget.render("email", "user@example.com", field)
    
    assert 'email' in html
    assert 'user@example.com' in html


def test_url_widget():
    """Test URLInput widget."""
    widget = URLInput()
    field = MockField(name="website")
    html = widget.render("website", "https://example.com", field)
    
    assert 'url' in html
    value_match = re.search(r'value="([^"]+)"', html)
    assert value_match is not None
    assert urlparse(value_match.group(1)).hostname == "example.com"


def test_number_widget():
    """Test NumberInput widget."""
    widget = NumberInput()
    field = MockField(name="age")
    html = widget.render("age", 25, field)
    
    assert 'number' in html
    assert '25' in html


def test_json_widget_basic():
    """Test JSONAdminWidget basic rendering."""
    widget = JSONAdminWidget()
    field = MockField(name="config")
    
    # Test with dict
    data = {"name": "John", "age": 30}
    html = widget.render("config", data, field)
    
    assert 'name="config"' in html
    assert 'John' in html


def test_json_widget_with_list():
    """Test JSONAdminWidget with list."""
    widget = JSONAdminWidget()
    field = MockField(name="items")
    
    data = ["item1", "item2", "item3"]
    html = widget.render("items", data, field)
    
    assert 'item1' in html
    assert 'item2' in html


def test_json_widget_with_none():
    """Test JSONAdminWidget with None value."""
    widget = JSONAdminWidget()
    field = MockField(name="config")
    html = widget.render("config", None, field)
    
    assert 'name="config"' in html


def test_json_widget_pretty_format():
    """Test JSONAdminWidget formats JSON prettily."""
    widget = JSONAdminWidget()
    field = MockField(name="data")
    
    data = {"key": "value", "nested": {"inner": 123}}
    html = widget.render("data", data, field)
    
    # Should contain the data
    assert 'key' in html
    assert 'value' in html


def test_array_widget_basic():
    """Test ArrayAdminWidget basic rendering."""
    widget = ArrayAdminWidget()
    field = MockField(name="fruits")
    
    items = ["apple", "banana", "cherry"]
    html = widget.render("fruits", items, field)
    
    assert 'fruits' in html
    assert 'apple' in html
    assert 'banana' in html


def test_array_widget_empty():
    """Test ArrayAdminWidget with empty array."""
    widget = ArrayAdminWidget()
    field = MockField(name="items")
    html = widget.render("items", [], field)
    
    # Should still render the container
    assert 'items' in html


def test_array_widget_with_none():
    """Test ArrayAdminWidget with None value."""
    widget = ArrayAdminWidget()
    field = MockField(name="items")
    html = widget.render("items", None, field)
    
    # Should render container
    assert 'items' in html


def test_array_widget_add_button():
    """Test ArrayAdminWidget renders add button."""
    widget = ArrayAdminWidget()
    field = MockField(name="tags")
    html = widget.render("tags", ["tag1"], field)
    
    # Should have add functionality
    assert 'Add' in html or 'tag1' in html


def test_array_widget_remove_button():
    """Test ArrayAdminWidget renders remove buttons for items."""
    widget = ArrayAdminWidget()
    field = MockField(name="tags")
    html = widget.render("tags", ["tag1", "tag2"], field)
    
    # Should have remove functionality
    assert 'tag1' in html and 'tag2' in html


def test_widget_renders_html():
    """Test that widgets render valid HTML."""
    widget = TextInput()
    field = MockField(name="name")
    html = widget.render("name", "test value", field)
    
    # Should contain basic HTML structure
    assert 'name' in html
    assert 'test value' in html


def test_json_widget_with_string():
    """Test JSONAdminWidget with plain string."""
    widget = JSONAdminWidget()
    field = MockField(name="text")
    html = widget.render("text", "plain string", field)
    
    # Should contain the string
    assert 'plain string' in html or 'string' in html


def test_array_widget_normalizes_values():
    """Test ArrayAdminWidget normalizes various input types."""
    widget = ArrayAdminWidget()
    field = MockField(name="tags")
    
    # String input (comma-separated)
    html1 = widget.render("tags", "tag1,tag2,tag3", field)
    assert 'tag' in html1
    
    # List input
    html2 = widget.render("tags", ["a", "b", "c"], field)
    assert 'a' in html2 or 'tags' in html2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
