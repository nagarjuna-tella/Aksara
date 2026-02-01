"""
Tests for Admin UI/UX Integration

Tests the integration of widgets with ModelAdmin and views.
"""

import pytest
from aksara.contrib.admin.options import ModelAdmin
from aksara.contrib.admin.widgets.json import JSONAdminWidget
from aksara.contrib.admin.widgets.array import ArrayAdminWidget


class MockField:
    """Mock field for testing."""
    
    def __init__(self, name, field_type="String", nullable=False):
        self.name = name
        self.field_type = field_type
        self.nullable = nullable
        self.primary_key = False
    
    @property
    def __class__(self):
        # Create a mock class with the correct __name__
        class _MockFieldClass:
            def __init__(self, name):
                self.__name__ = name
        return _MockFieldClass(self.field_type)


class MockModel:
    """Mock model for testing."""
    
    class meta:
        fields = []
        many_to_many = {}
        app_label = "test"
        
        @classmethod
        def get_field(cls, name):
            for field in cls.fields:
                if field.name == name:
                    return field
            return None


def test_model_admin_formfield_overrides():
    """Test ModelAdmin.formfield_overrides attribute."""
    
    class TestAdmin(ModelAdmin):
        formfield_overrides = {
            "config": JSONAdminWidget(),
            "tags": ArrayAdminWidget(),
        }
    
    # Create mock model and site
    model = MockModel()
    site = None
    
    admin = TestAdmin(model, site)
    
    assert "config" in admin.formfield_overrides
    assert "tags" in admin.formfield_overrides
    assert isinstance(admin.formfield_overrides["config"], JSONAdminWidget)
    assert isinstance(admin.formfield_overrides["tags"], ArrayAdminWidget)


def test_model_admin_get_widget_explicit():
    """Test ModelAdmin.get_widget with explicit override."""
    
    json_widget = JSONAdminWidget()
    
    class TestAdmin(ModelAdmin):
        formfield_overrides = {
            "config": json_widget,
        }
    
    model = MockModel()
    admin = TestAdmin(model, None)
    
    field = MockField("config", "JSON")
    widget = admin.get_widget("config", field)
    
    assert widget is json_widget


def test_model_admin_get_widget_auto_json():
    """Test ModelAdmin.get_widget auto-selects JSONAdminWidget for JSON fields."""
    
    class TestAdmin(ModelAdmin):
        pass
    
    model = MockModel()
    admin = TestAdmin(model, None)
    
    field = MockField("data", "JSON")
    widget = admin.get_widget("data", field)
    
    assert widget is not None
    assert isinstance(widget, JSONAdminWidget)


def test_model_admin_get_widget_auto_array():
    """Test ModelAdmin.get_widget auto-selects ArrayAdminWidget for Array fields."""
    
    class TestAdmin(ModelAdmin):
        pass
    
    model = MockModel()
    admin = TestAdmin(model, None)
    
    field = MockField("items", "Array")
    widget = admin.get_widget("items", field)
    
    assert widget is not None
    assert isinstance(widget, ArrayAdminWidget)


def test_model_admin_get_widget_no_override():
    """Test ModelAdmin.get_widget returns None for fields without widgets."""
    
    class TestAdmin(ModelAdmin):
        pass
    
    model = MockModel()
    admin = TestAdmin(model, None)
    
    field = MockField("name", "String")
    widget = admin.get_widget("name", field)
    
    assert widget is None


def test_model_admin_get_field_type():
    """Test ModelAdmin.get_field_type for various field types."""
    
    class TestAdmin(ModelAdmin):
        pass
    
    model = MockModel()
    model.meta.fields = [
        MockField("email", "Email"),
        MockField("website", "URL"),
        MockField("age", "Integer"),
        MockField("price", "Float"),
        MockField("is_active", "Boolean"),
        MockField("created_at", "DateTime"),
        MockField("bio", "Text"),
        MockField("config", "JSON"),
    ]
    
    admin = TestAdmin(model, None)
    
    assert admin.get_field_type("email") == "email"
    assert admin.get_field_type("website") == "url"
    assert admin.get_field_type("age") == "number"
    assert admin.get_field_type("price") == "number"
    assert admin.get_field_type("is_active") == "checkbox"
    assert admin.get_field_type("created_at") == "datetime-local"
    assert admin.get_field_type("bio") == "textarea"
    assert admin.get_field_type("config") == "textarea"


def test_model_admin_inherits_widgets():
    """Test that custom ModelAdmin can inherit and extend formfield_overrides."""
    
    class BaseAdmin(ModelAdmin):
        formfield_overrides = {
            "config": JSONAdminWidget(),
        }
    
    class ExtendedAdmin(BaseAdmin):
        # This should have access to parent's overrides
        pass
    
    model = MockModel()
    admin = ExtendedAdmin(model, None)
    
    # Should inherit parent's overrides
    assert "config" in admin.formfield_overrides


def test_widget_rendering_in_field_info():
    """Test that widget HTML is included in field info."""
    
    class TestAdmin(ModelAdmin):
        formfield_overrides = {
            "data": JSONAdminWidget(),
        }
    
    model = MockModel()
    model.meta.fields = [MockField("data", "JSON")]
    
    admin = TestAdmin(model, None)
    
    # Get widget and render
    field = model.meta.get_field("data")
    widget = admin.get_widget("data", field)
    
    assert widget is not None
    
    html = widget.render("data", {"key": "value"}, field)
    assert html is not None
    assert "data" in html
    assert "key" in html


def test_json_widget_integrates_with_form():
    """Test that JSON widget renders proper form HTML."""
    widget = JSONAdminWidget()
    field = MockField("config", "JSON")
    
    data = {
        "name": "Test",
        "settings": {
            "enabled": True,
            "count": 42
        }
    }
    
    html = widget.render("config", data, field)
    
    assert 'name="config"' in html
    assert '"name"' in html or 'Test' in html


def test_array_widget_integrates_with_form():
    """Test that Array widget renders proper form HTML."""
    widget = ArrayAdminWidget()
    field = MockField("fruits", "Array")
    
    items = ["apple", "banana", "cherry"]
    
    html = widget.render("fruits", items, field)
    
    assert 'name="fruits"' in html or 'fruits' in html
    assert 'apple' in html
    assert 'banana' in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
