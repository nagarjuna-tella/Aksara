"""
Model Admin Options

ModelAdmin configuration class for customizing admin behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type

if TYPE_CHECKING:
    from aksara.model.base import Model
    from aksara.contrib.admin.site import AdminSite
    from fastapi import Request


# A fieldset is (title_or_None, {"fields": [...], "description": str, "classes": [...]})
Fieldset = Tuple[Optional[str], Dict[str, Any]]


class ModelAdmin:
    """
    Configuration class for model admin behavior.

    Subclass this to customize how a model appears and behaves in the admin.

    Example:
        @site.register(Article)
        class ArticleAdmin(ModelAdmin):
            list_display = ["title", "author", "created_at"]
            list_display_links = ["title"]
            list_filter = ["status"]
            search_fields = ["title", "body"]
            ordering = ["-created_at"]
            list_per_page = 25
            readonly_fields = ["created_at", "updated_at"]
            actions = ["publish_selected"]
    """

    # --- List view configuration ---------------------------------------------
    list_display: List[str] = []
    list_display_links: Optional[List[str]] = None
    search_fields: List[str] = []
    list_filter: List[Any] = []
    ordering: List[str] = []
    list_per_page: int = 100
    list_max_show_all: int = 200

    # --- Form configuration ---------------------------------------------------
    readonly_fields: List[str] = []
    form_fields: Optional[List[str]] = None  # Legacy alias; None means auto-infer
    fields: Optional[List[str]] = None       # Explicit ordered subset for the form
    exclude: Optional[List[str]] = None       # Fields to drop from the default form
    fieldsets: Optional[List[Fieldset]] = None
    formfield_overrides: Dict[str, Any] = {}  # Map field_name -> widget instance
    prepopulated_fields: Dict[str, Tuple[str, ...]] = {}  # slug -> (source, ...)
    raw_id_fields: List[str] = []             # Relation fields rendered as a text id
    autocomplete_fields: List[str] = []       # Relation fields rendered searchable

    # --- Actions --------------------------------------------------------------
    actions: List[Any] = []

    # Fields that are always excluded from the auto-inferred form (ORM-managed).
    AUTO_EXCLUDE_FIELDS = {"created_at", "updated_at"}

    def __init__(self, model: Type["Model"], site: "AdminSite"):
        self.model = model
        self.site = site

    # -------------------------------------------------------------------------
    # Query Helpers
    # -------------------------------------------------------------------------

    async def get_queryset(self, request: "Request") -> Any:
        """
        Get the base queryset for list views.

        Override to customize filtering based on request/user. When overriding,
        await ``super().get_queryset(request)`` and chain queryset methods:

            async def get_queryset(self, request):
                qs = await super().get_queryset(request)
                return qs.filter(owner_id=str(request.state.user.id))
        """
        return self.model.objects.filter()

    async def get_object(self, request: "Request", pk: str) -> "Model":
        """Get a single object by primary key."""
        return await self.model.objects.get(id=pk)

    def get_ordering(self, request: "Request") -> List[str]:
        """Return the default ordering for the list view."""
        return list(self.ordering or [])

    def get_search_results(self, request: "Request", queryset: Any, term: str) -> Any:
        """
        Apply ``search_fields`` to the queryset for the given term.

        Uses the ORM's OR-across-fields ``search()`` for own-table fields, which
        is the reliably supported path. Related (``a__b``) search fields are
        applied best-effort and skipped if the ORM cannot resolve them.
        """
        term = (term or "").strip()
        if not term or not self.search_fields:
            return queryset

        direct_fields = [f for f in self.search_fields if "__" not in f]
        related_fields = [f for f in self.search_fields if "__" in f]

        if direct_fields:
            queryset = queryset.search(term, direct_fields)

        # Related-field search depends on relation filtering, which is still
        # maturing in the ORM; apply it without letting failures break the view.
        for field in related_fields:
            try:
                queryset = queryset.filter(**{f"{field}__icontains": term})
            except Exception:
                continue
        return queryset

    # -------------------------------------------------------------------------
    # Permissions
    # -------------------------------------------------------------------------

    def has_module_permission(self, request: "Request") -> bool:
        """
        Whether this model appears in the admin index/sidebar for the user.

        Defaults to the view permission. Override to hide a model entirely.
        """
        return self.has_view_permission(request)

    def has_view_permission(
        self, request: "Request", obj: Optional["Model"] = None
    ) -> bool:
        """Check if the user can view objects in admin."""
        user = getattr(request.state, "user", None)
        return bool(user and getattr(user, "is_staff", False))

    def has_add_permission(self, request: "Request") -> bool:
        """Check if the user can add new objects."""
        return self.has_view_permission(request)

    def has_change_permission(
        self, request: "Request", obj: Optional["Model"] = None
    ) -> bool:
        """Check if the user can change objects."""
        return self.has_view_permission(request, obj)

    def has_delete_permission(
        self, request: "Request", obj: Optional["Model"] = None
    ) -> bool:
        """Check if the user can delete objects."""
        return self.has_view_permission(request, obj)

    # -------------------------------------------------------------------------
    # Field Configuration
    # -------------------------------------------------------------------------

    def get_list_display(self, request: "Request") -> List[str]:
        """Get fields/columns to display in the list view."""
        if self.list_display:
            return list(self.list_display)

        names: List[str] = [field.name for field in self.model.meta.fields]
        if "id" in names:
            names.remove("id")
            names.insert(0, "id")
        return names[:4]

    def get_list_display_links(
        self, request: "Request", list_display: List[str]
    ) -> List[str]:
        """Return which columns link to the change view."""
        if self.list_display_links is not None:
            return list(self.list_display_links)
        return [list_display[0]] if list_display else []

    def is_callable_column(self, name: str) -> bool:
        """True if ``name`` is a custom column method rather than a model field."""
        if self.model.meta.get_field(name) is not None:
            return False
        if name in self.model.meta.many_to_many:
            return False
        attr = getattr(self, name, None)
        return callable(attr)

    def get_column_label(self, name: str) -> str:
        """Header label for a list column (field or custom method)."""
        if self.is_callable_column(name):
            method = getattr(self, name)
            label = getattr(method, "short_description", None)
            if label:
                return str(label)
        return name.replace("_", " ").title()

    def column_allows_html(self, name: str) -> bool:
        if self.is_callable_column(name):
            return bool(getattr(getattr(self, name), "allow_html", False))
        return False

    def get_readonly_fields(
        self, request: "Request", obj: Optional["Model"] = None
    ) -> List[str]:
        """Get fields that cannot be edited."""
        return list(self.readonly_fields or [])

    def get_fields(
        self, request: "Request", obj: Optional["Model"] = None
    ) -> List[str]:
        """
        Get the flat list of fields shown on the add/change form.

        Resolution order:
        1. Explicit ``fields`` (verbatim, ordered).
        2. Legacy ``form_fields`` (verbatim).
        3. Auto-inferred (non-pk, non-timestamp, non-readonly + M2M), then
           with ``exclude`` removed.
        """
        if self.fields is not None:
            return list(self.fields)
        if self.form_fields is not None:
            return list(self.form_fields)

        readonly = set(self.get_readonly_fields(request, obj))
        fields: List[str] = []
        for field in self.model.meta.fields:
            if getattr(field, "primary_key", False):
                continue
            if field.name in self.AUTO_EXCLUDE_FIELDS:
                continue
            if field.name in readonly:
                continue
            fields.append(field.name)

        for m2m_name in self.model.meta.many_to_many.keys():
            if m2m_name not in readonly:
                fields.append(m2m_name)

        if self.exclude:
            excluded = set(self.exclude)
            fields = [f for f in fields if f not in excluded]
        return fields

    def get_fieldsets(
        self, request: "Request", obj: Optional["Model"] = None
    ) -> List[Fieldset]:
        """
        Get fieldsets (grouped form sections).

        If ``fieldsets`` is declared it is used as-is; otherwise a single
        unnamed section is built from :meth:`get_fields`.
        """
        if self.fieldsets:
            return list(self.fieldsets)
        return [(None, {"fields": self.get_fields(request, obj)})]

    def get_form_fields(
        self, request: "Request", obj: Optional["Model"] = None
    ) -> List[str]:
        """Flat list of field names the form parses and saves."""
        if self.fieldsets:
            names: List[str] = []
            for _title, opts in self.fieldsets:
                names.extend(opts.get("fields", []))
            return names
        return self.get_fields(request, obj)

    def get_field_type(self, field_name: str) -> str:
        """Get the HTML input type for a field."""
        if field_name in self.model.meta.many_to_many:
            return "multiselect"

        if field_name in self.raw_id_fields:
            return "text"

        field = self.model.meta.get_field(field_name)
        if not field:
            return "text"

        field_type = field.__class__.__name__
        type_map = {
            "Email": "email",
            "URL": "url",
            "Integer": "number",
            "Float": "number",
            "Decimal": "number",
            "Boolean": "checkbox",
            "DateTime": "datetime-local",
            "Date": "date",
            "Time": "time",
            "Text": "textarea",
            "JSON": "textarea",
            "ForeignKey": "select",
        }
        return type_map.get(field_type, "text")

    def get_widget(self, field_name: str, field: Any) -> Optional[Any]:
        """Get custom widget for a field if configured."""
        if field_name in self.formfield_overrides:
            return self.formfield_overrides[field_name]

        field_type = field.__class__.__name__
        if field_type == "JSON":
            from aksara.contrib.admin.widgets.json import JSONAdminWidget
            return JSONAdminWidget()
        elif field_type == "Array":
            from aksara.contrib.admin.widgets.array import ArrayAdminWidget
            return ArrayAdminWidget()
        return None

    async def get_field_choices(
        self, field_name: str, request: "Request"
    ) -> List[tuple]:
        """Get (value, label) choices for a ForeignKey or ManyToMany field."""
        from aksara.fields import ForeignKey

        m2m_fields = self.model.meta.many_to_many
        if field_name in m2m_fields:
            related_model = m2m_fields[field_name].to_model
            objects = await related_model.objects.all()
            return [(str(obj.id), self._get_object_display(obj)) for obj in objects]

        field = self.model.meta.get_field(field_name)
        if not field or not isinstance(field, ForeignKey):
            return []

        related_model = field.to_model
        objects = await related_model.objects.all()
        return [(str(obj.id), self._get_object_display(obj)) for obj in objects]

    def _get_object_display(self, obj: "Model") -> str:
        """Display string for a model instance (custom __str__, then common fields)."""
        str_repr = str(obj)
        if str_repr and not str_repr.startswith("<"):
            return str_repr

        for attr in ["name", "title", "email", "username", "label", "description"]:
            val = getattr(obj, attr, None)
            if val:
                return str(val)
        return str(obj.id)

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def get_actions(self, request: "Request") -> Dict[str, Dict[str, Any]]:
        """
        Resolve declared actions into an ordered mapping.

        Each entry: name -> {"func": callable, "description": str,
        "allowed_permissions": [..]}. The callable is invoked as
        ``func(self, request, queryset)``.
        """
        from aksara.contrib.admin.actions import delete_selected

        resolved: Dict[str, Dict[str, Any]] = {}
        for entry in self.actions or []:
            func = None
            name = None
            if isinstance(entry, str):
                if entry == "delete_selected":
                    func, name = delete_selected, "delete_selected"
                else:
                    candidate = getattr(self, entry, None)
                    if candidate is None:
                        continue
                    func, name = candidate, entry
            elif callable(entry):
                func, name = entry, getattr(entry, "__name__", "action")

            if func is None:
                continue

            resolved[name] = {
                "func": func,
                "description": getattr(
                    func, "action_description", name.replace("_", " ").capitalize()
                ),
                "allowed_permissions": list(getattr(func, "allowed_permissions", [])),
            }
        return resolved

    def message_user(
        self, request: "Request", message: str, level: str = "info"
    ) -> None:
        """Queue a flash message shown on the next list render."""
        from aksara.contrib.admin.actions import queue_message
        queue_message(request, message, level)

    # -------------------------------------------------------------------------
    # Save / Delete Hooks
    # -------------------------------------------------------------------------

    async def save_model(
        self,
        request: "Request",
        obj: "Model",
        form_data: Dict[str, Any],
        is_created: bool,
    ) -> None:
        """
        Save the model instance and its many-to-many relations.

        Raises ``ValueError`` if any submitted M2M id does not resolve, so the
        form can surface the problem instead of silently dropping selections.
        """
        m2m_fields = self.model.meta.many_to_many
        m2m_data: Dict[str, Any] = {}
        related_by_field: Dict[str, List[Any]] = {}

        for name, value in form_data.items():
            if name in m2m_fields:
                m2m_data[name] = value
            else:
                setattr(obj, name, value)

        for m2m_name, related_ids in m2m_data.items():
            related_model = m2m_fields[m2m_name].to_model
            related_objects = []
            missing: List[str] = []
            for rid in related_ids or []:
                try:
                    related_objects.append(await related_model.objects.get(id=rid))
                except Exception:
                    missing.append(str(rid))
            if missing:
                raise ValueError(
                    f"{m2m_name}: could not find related "
                    f"{related_model.__name__} for id(s): {', '.join(missing)}"
                )
            related_by_field[m2m_name] = related_objects

        if not m2m_data:
            await obj.save()
            return

        from aksara.db.transaction import atomic

        async with atomic():
            await obj.save()
            for m2m_name, related_objects in related_by_field.items():
                m2m_manager = getattr(obj, m2m_name)
                await m2m_manager.clear()
                if related_objects:
                    await m2m_manager.add(*related_objects)

    async def delete_model(self, request: "Request", obj: "Model") -> None:
        """Delete the model instance."""
        await obj.delete()
