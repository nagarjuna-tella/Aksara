"""
Array Admin Widget

Repeater-style widget for PostgreSQL array fields.
"""

from __future__ import annotations

import html as _html
import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from aksara.contrib.admin.widgets import Widget

if TYPE_CHECKING:
    from aksara.fields import Field


class ArrayAdminWidget(Widget):
    """
    Repeater-style widget for array fields.
    
    Features:
    - Dynamic add/remove rows
    - Type validation (text vs numeric)
    - Maintains ordering
    - Supports empty arrays
    - Nullable array handling
    
    Example:
        class MyModelAdmin(ModelAdmin):
            form_widgets = {
                "tags": ArrayAdminWidget(item_type="text"),
                "scores": ArrayAdminWidget(item_type="number")
            }
    """
    
    template_name = "admin/widgets/array.html"
    
    def __init__(
        self,
        attrs: Optional[Dict[str, Any]] = None,
        item_type: str = "text",
        min_rows: int = 1,
        max_rows: Optional[int] = None
    ):
        """
        Initialize the array widget.
        
        Args:
            attrs: HTML attributes
            item_type: Type of array items ("text", "number", "email", "url")
            min_rows: Minimum number of visible rows (default: 1)
            max_rows: Maximum number of rows (optional)
        """
        super().__init__(attrs)
        self.item_type = item_type
        self.min_rows = min_rows
        self.max_rows = max_rows
    
    def normalize_value(self, value: Any) -> List[Any]:
        """
        Normalize value to a list.
        
        Args:
            value: Raw value (list, string, or None)
            
        Returns:
            List of items
        """
        if value is None:
            return []
        
        if isinstance(value, list):
            return value
        
        if isinstance(value, str):
            # Try to parse as JSON
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                # Treat as comma-separated string
                return [item.strip() for item in value.split(",") if item.strip()]
        
        return []
    
    def render(self, name: str, value: Any, field: "Field") -> str:
        """
        Render the array widget.
        
        Args:
            name: Field name
            value: Current value (list or None)
            field: Field instance
            
        Returns:
            HTML for the widget
        """
        items = self.normalize_value(value)
        
        # Ensure at least min_rows
        while len(items) < self.min_rows:
            items.append("")
        
        field_id = f"id_{name}"
        required = " required" if not field.nullable else ""
        
        # Build rows HTML
        rows_html = []
        for i, item in enumerate(items):
            item_value = str(item) if item is not None else ""
            # Escape HTML
            item_value = (
                item_value
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )
            
            rows_html.append(f'''
        <div class="array-item" data-index="{i}" draggable="true">
            <span class="array-drag-handle" title="Drag to reorder">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/>
                    <circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/>
                </svg>
            </span>
            <input
                type="{self.item_type}"
                name="{name}_item"
                value="{item_value}"
                class="form-input array-input"
                data-array-item="true"
                placeholder="Enter value..."
            />
            <button
                type="button"
                class="btn-remove-item"
                onclick="removeArrayItem(this)"
                title="Remove item"
            >
                <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 6L6 18M6 6l12 12"/>
                </svg>
            </button>
        </div>
            '''.strip())
        
        rows_joined = "\n        ".join(rows_html)
        
        max_rows_attr = f' data-max-rows="{self.max_rows}"' if self.max_rows else ""
        
        html = f'''
<div class="array-widget-container" id="{field_id}_container" data-field="{name}" data-item-type="{self.item_type}"{max_rows_attr}>
    <div class="array-items">
        {rows_joined}
    </div>
    <button
        type="button"
        class="btn-add-item"
        onclick="addArrayItem('{field_id}_container', '{name}', '{self.item_type}')"
    >
        <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 5v14M5 12h14"/>
        </svg>
        Add item
    </button>
    <input type="hidden" name="{name}" id="{field_id}" value="{_html.escape(self._serialize_value(items))}"{required} />
</div>
'''
        
        return html.strip()
    
    def _serialize_value(self, items: List[Any]) -> str:
        """
        Serialize array items to JSON string.
        
        Args:
            items: List of items
            
        Returns:
            JSON string
        """
        return json.dumps(items)
    
    def get_context(
        self,
        name: str,
        value: Any,
        field: "Field"
    ) -> Dict[str, Any]:
        """Get template context."""
        context = super().get_context(name, value, field)
        context.update({
            "item_type": self.item_type,
            "min_rows": self.min_rows,
            "max_rows": self.max_rows,
            "items": self.normalize_value(value),
        })
        return context
