"""
JSON Admin Widget

Enhanced widget for JSON fields with syntax highlighting, validation, and formatting.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, Optional

from aksara.contrib.admin.widgets import Widget

if TYPE_CHECKING:
    from aksara.fields import Field


class JSONAdminWidget(Widget):
    """
    Advanced widget for JSON fields.
    
    Features:
    - Pretty-printed JSON display
    - Syntax validation on submit
    - Auto-format button
    - Monospace font styling
    - Auto-expanding textarea
    - Clear error messages
    
    Example:
        class MyModelAdmin(ModelAdmin):
            form_widgets = {
                "metadata": JSONAdminWidget(rows=12)
            }
    """
    
    template_name = "admin/widgets/json.html"
    
    def __init__(
        self,
        attrs: Optional[Dict[str, Any]] = None,
        rows: int = 12,
        pretty_print: bool = True
    ):
        """
        Initialize the JSON widget.
        
        Args:
            attrs: HTML attributes
            rows: Number of textarea rows (default: 12)
            pretty_print: Whether to pretty-print on initial render (default: True)
        """
        super().__init__(attrs)
        self.rows = rows
        self.pretty_print = pretty_print
    
    def format_value(self, value: Any) -> str:
        """
        Format value for display in textarea.
        
        Args:
            value: Raw JSON value (dict, list, or string)
            
        Returns:
            Formatted JSON string
        """
        if value is None:
            return ""
        
        # If it's already a string, try to parse and reformat
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return json.dumps(parsed, indent=2, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                # Return as-is if can't parse
                return value
        
        # If it's a dict/list, format it
        try:
            return json.dumps(value, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value)
    
    def render(self, name: str, value: Any, field: "Field") -> str:
        """
        Render the JSON widget.
        
        Args:
            name: Field name
            value: Current value
            field: Field instance
            
        Returns:
            HTML for the widget
        """
        # Format the value for display
        if self.pretty_print:
            formatted_value = self.format_value(value)
        else:
            formatted_value = str(value) if value is not None else ""
        
        # Escape HTML entities
        formatted_value = (
            formatted_value
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        
        required = " required" if not field.nullable else ""
        field_id = f"id_{name}"
        
        html = f'''
<div class="json-widget-container" data-field="{name}">
    <div class="json-widget-toolbar">
        <button
            type="button"
            class="btn-format-json"
            onclick="formatJSON('{field_id}')"
            title="Format JSON (Ctrl+Shift+F)"
        >
            <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 7h16M4 12h16M4 17h16"/>
            </svg>
            Format JSON
        </button>
        <span class="json-hint">Use Ctrl+Shift+F to format</span>
    </div>
    <textarea
        id="{field_id}"
        name="{name}"
        rows="{self.rows}"
        class="form-textarea json-textarea"
        spellcheck="false"
        data-json-widget="true"{required}
    >{formatted_value}</textarea>
    <div class="json-error" id="{field_id}_error" style="display: none;"></div>
    <div class="json-info">
        <small class="text-muted">Enter valid JSON. Use the Format button to auto-indent.</small>
    </div>
</div>
'''
        
        return html.strip()
    
    def get_context(
        self,
        name: str,
        value: Any,
        field: "Field"
    ) -> Dict[str, Any]:
        """Get template context."""
        context = super().get_context(name, value, field)
        context.update({
            "rows": self.rows,
            "pretty_print": self.pretty_print,
            "formatted_value": self.format_value(value) if self.pretty_print else value,
        })
        return context
