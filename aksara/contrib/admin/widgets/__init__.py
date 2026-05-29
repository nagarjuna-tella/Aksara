"""
Admin Widget System

Base widget classes and built-in widgets for Aksara admin forms.
"""

from __future__ import annotations

import html as _html
from typing import TYPE_CHECKING, Any, Dict, Optional
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from aksara.fields import Field


class Widget(ABC):
    """
    Base widget class for admin form fields.
    
    Widgets control how fields are rendered in admin forms.
    """
    
    template_name: str = "admin/widgets/input.html"
    
    def __init__(self, attrs: Optional[Dict[str, Any]] = None):
        """
        Initialize the widget.
        
        Args:
            attrs: HTML attributes for the widget element
        """
        self.attrs = attrs or {}
    
    @abstractmethod
    def render(self, name: str, value: Any, field: "Field") -> str:
        """
        Render the widget HTML.
        
        Args:
            name: Field name
            value: Current value
            field: Field instance
            
        Returns:
            HTML string
        """
        pass
    
    def get_context(
        self,
        name: str,
        value: Any,
        field: "Field"
    ) -> Dict[str, Any]:
        """
        Get template context for rendering.
        
        Args:
            name: Field name
            value: Current value
            field: Field instance
            
        Returns:
            Context dictionary
        """
        return {
            "widget": self,
            "name": name,
            "value": value,
            "field": field,
            "attrs": self.attrs,
            "required": not field.nullable,
        }


class TextInput(Widget):
    """Standard text input widget."""
    
    template_name = "admin/widgets/text_input.html"
    
    def render(self, name: str, value: Any, field: "Field") -> str:
        attrs_str = " ".join(f'{k}="{_html.escape(str(v))}"' for k, v in self.attrs.items())
        input_type = _html.escape(self.attrs.get("type", "text"))
        value_str = _html.escape(str(value)) if value is not None else ""
        required = " required" if not field.nullable else ""
        
        return f'''<input type="{input_type}" name="{_html.escape(name)}" value="{value_str}" {attrs_str}{required} class="form-input" />'''


class TextArea(Widget):
    """Textarea widget for longer text."""
    
    template_name = "admin/widgets/textarea.html"
    
    def __init__(self, attrs: Optional[Dict[str, Any]] = None, rows: int = 6):
        super().__init__(attrs)
        self.rows = rows
    
    def render(self, name: str, value: Any, field: "Field") -> str:
        attrs_str = " ".join(f'{k}="{_html.escape(str(v))}"' for k, v in self.attrs.items())
        value_str = _html.escape(str(value)) if value is not None else ""
        required = " required" if not field.nullable else ""
        
        return f'''<textarea name="{_html.escape(name)}" rows="{self.rows}" {attrs_str}{required} class="form-textarea">{value_str}</textarea>'''


class CheckboxInput(Widget):
    """Checkbox widget for boolean fields."""
    
    template_name = "admin/widgets/checkbox.html"
    
    def render(self, name: str, value: Any, field: "Field") -> str:
        checked = " checked" if value else ""
        return f'''<input type="checkbox" name="{name}" value="true"{checked} class="form-checkbox" />'''


class DateTimeInput(Widget):
    """HTML5 datetime-local input widget."""
    
    template_name = "admin/widgets/datetime.html"
    
    def render(self, name: str, value: Any, field: "Field") -> str:
        # Format datetime for HTML5 input
        value_str = ""
        if value:
            try:
                # Handle both datetime and string formats
                if hasattr(value, "strftime"):
                    value_str = value.strftime("%Y-%m-%dT%H:%M")
                else:
                    import datetime as _dt
                    # Only output if parseable as a datetime — rejects arbitrary strings
                    _dt.datetime.fromisoformat(str(value))
                    value_str = str(value).replace(" ", "T")[:16]
            except:
                value_str = ""
        
        required = " required" if not field.nullable else ""
        return f'''<input type="datetime-local" name="{_html.escape(name)}" value="{value_str}"{required} class="form-input" />'''


class Select(Widget):
    """Select dropdown widget."""
    
    template_name = "admin/widgets/select.html"
    
    def __init__(
        self,
        attrs: Optional[Dict[str, Any]] = None,
        choices: Optional[list] = None
    ):
        super().__init__(attrs)
        self.choices = choices or []
    
    def render(self, name: str, value: Any, field: "Field") -> str:
        required = " required" if not field.nullable else ""
        options = []
        
        if field.nullable:
            selected = " selected" if value is None else ""
            options.append(f'<option value=""{selected}>---------</option>')
        
        for choice_value, choice_label in self.choices:
            selected = " selected" if value == choice_value else ""
            options.append(
                f'<option value="{_html.escape(str(choice_value))}"{selected}>{_html.escape(str(choice_label))}</option>'
            )
        
        options_html = "\n".join(options)
        return f'''<select name="{name}"{required} class="form-select">\n{options_html}\n</select>'''


class EmailInput(TextInput):
    """Email input widget with validation."""
    
    def __init__(self, attrs: Optional[Dict[str, Any]] = None):
        attrs = attrs or {}
        attrs["type"] = "email"
        super().__init__(attrs)


class URLInput(TextInput):
    """URL input widget with validation."""
    
    def __init__(self, attrs: Optional[Dict[str, Any]] = None):
        attrs = attrs or {}
        attrs["type"] = "url"
        super().__init__(attrs)


class NumberInput(TextInput):
    """Number input widget."""
    
    def __init__(self, attrs: Optional[Dict[str, Any]] = None):
        attrs = attrs or {}
        attrs["type"] = "number"
        super().__init__(attrs)


from aksara.contrib.admin.widgets.array import ArrayAdminWidget
from aksara.contrib.admin.widgets.json import JSONAdminWidget


__all__ = [
    "Widget",
    "TextInput",
    "TextArea",
    "CheckboxInput",
    "DateTimeInput",
    "Select",
    "EmailInput",
    "URLInput",
    "NumberInput",
    "ArrayAdminWidget",
    "JSONAdminWidget",
]
