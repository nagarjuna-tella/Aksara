"""
Admin list filters.

Provides the sidebar filtering system for admin list views:

- ``SimpleListFilter`` — subclass for custom filter logic with arbitrary lookups.
- ``FieldListFilter`` — internal helper that turns a plain field name in
  ``ModelAdmin.list_filter`` into a set of selectable values.

The list view builds a filter spec for each entry in ``list_filter`` and applies
the selected value to the queryset before pagination.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional, Tuple

if TYPE_CHECKING:
    from fastapi import Request
    from aksara.contrib.admin.options import ModelAdmin


# Maximum distinct values to offer for an auto-generated field filter. Beyond
# this, a free-form field is not a useful sidebar filter.
MAX_AUTO_FILTER_CHOICES = 50


class SimpleListFilter:
    """
    Base class for custom admin list filters.

    Subclass and define ``title``, ``parameter_name``, ``lookups()`` and
    ``queryset()``:

        class RecentFilter(SimpleListFilter):
            title = "Published"
            parameter_name = "when"

            def lookups(self, request, model_admin):
                return [("week", "This week"), ("month", "This month")]

            def queryset(self, request, queryset):
                if self.value() == "week":
                    return queryset.filter(published_at__gte=...)
                return queryset

    The selected value is read from the request query string using
    ``parameter_name``.
    """

    title: str = ""
    parameter_name: str = ""

    def __init__(self, request: "Request", model_admin: "ModelAdmin"):
        self.request = request
        self.model_admin = model_admin
        self._value: Optional[str] = request.query_params.get(self.parameter_name)
        self.lookup_choices: List[Tuple[str, str]] = list(
            self.lookups(request, model_admin) or []
        )

    def value(self) -> Optional[str]:
        """Return the selected filter value, or None if not set."""
        return self._value

    def lookups(
        self, request: "Request", model_admin: "ModelAdmin"
    ) -> List[Tuple[str, str]]:
        """Return a list of (value, label) options for the sidebar."""
        raise NotImplementedError(
            "SimpleListFilter subclasses must implement lookups()."
        )

    def queryset(self, request: "Request", queryset: Any) -> Any:
        """Return a filtered queryset based on the selected value."""
        raise NotImplementedError(
            "SimpleListFilter subclasses must implement queryset()."
        )

    def has_output(self) -> bool:
        return len(self.lookup_choices) > 0

    def choices_for_template(self) -> List[dict]:
        """Build the option list rendered in the sidebar (incl. an 'All' reset)."""
        current = self.value()
        options = [
            {"value": None, "label": "All", "selected": current in (None, "")}
        ]
        for value, label in self.lookup_choices:
            options.append(
                {
                    "value": str(value),
                    "label": str(label),
                    "selected": str(value) == str(current),
                }
            )
        return options


class FieldListFilter:
    """
    Auto-generated filter for a plain model field named in ``list_filter``.

    Boolean fields and fields with ``choices`` produce fixed options; other
    fields offer up to ``MAX_AUTO_FILTER_CHOICES`` distinct values pulled from
    the table. Applying the filter uses a direct ``field=value`` lookup, which
    the ORM supports reliably for own-table columns.
    """

    def __init__(self, field_name: str, title: str, parameter_name: str):
        self.field_name = field_name
        self.title = title
        self.parameter_name = parameter_name
        self.lookup_choices: List[Tuple[str, str]] = []
        self._value: Optional[str] = None
        self._field_type: str = "String"

    @classmethod
    async def create(
        cls,
        field_name: str,
        request: "Request",
        model_admin: "ModelAdmin",
    ) -> "FieldListFilter":
        title = field_name.replace("_", " ").title()
        instance = cls(field_name, title, field_name)
        instance._value = request.query_params.get(field_name)
        field = model_admin.model.meta.get_field(field_name)
        instance._field_type = field.__class__.__name__ if field else "String"
        instance.lookup_choices = await instance._build_choices(model_admin)
        return instance

    async def _build_choices(self, model_admin: "ModelAdmin") -> List[Tuple[str, str]]:
        model = model_admin.model
        field = model.meta.get_field(self.field_name)
        if field is None:
            return []

        field_type = field.__class__.__name__

        if field_type == "Boolean":
            return [("true", "Yes"), ("false", "No")]

        choices = getattr(field, "choices", None)
        if choices:
            return [(str(c), str(c).replace("_", " ").title()) for c in choices]

        # Fall back to distinct values present in the table (bounded).
        try:
            objects = await model.objects.all()
        except Exception:
            return []

        seen: List[str] = []
        for obj in objects:
            raw = getattr(obj, self.field_name, None)
            if raw is None:
                continue
            text = str(raw)
            if text not in seen:
                seen.append(text)
            if len(seen) > MAX_AUTO_FILTER_CHOICES:
                # Too many distinct values to be a useful sidebar filter.
                return []
        return [(v, v) for v in seen]

    def value(self) -> Optional[str]:
        return self._value

    def has_output(self) -> bool:
        return len(self.lookup_choices) > 0

    def apply(self, queryset: Any):
        """Apply the selected value to the queryset, if any."""
        value = self.value()
        if value in (None, ""):
            return queryset

        parsed: Any = value
        if self._field_type == "Boolean":
            parsed = value in ("true", "1", "on", "yes")
        elif self._field_type == "Integer":
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                return queryset

        try:
            return queryset.filter(**{self.field_name: parsed})
        except Exception:
            # Unsupported lookup (e.g. relation field) — leave queryset unfiltered
            # rather than raising a 500 in the admin.
            return queryset

    def choices_for_template(self) -> List[dict]:
        current = self.value()
        options = [
            {"value": None, "label": "All", "selected": current in (None, "")}
        ]
        for value, label in self.lookup_choices:
            options.append(
                {
                    "value": str(value),
                    "label": str(label),
                    "selected": str(value) == str(current),
                }
            )
        return options
