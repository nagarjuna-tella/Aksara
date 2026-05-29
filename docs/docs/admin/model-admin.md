# ModelAdmin

Control how your data appears and behaves in the admin interface.

---

## What is ModelAdmin?

A **ModelAdmin** is a configuration class that tells the admin how to display and
handle a specific model. Without it, the admin uses sensible defaults; with it,
you customize the list view, the form, permissions, and bulk actions.

```python
from aksara.contrib.admin import site, ModelAdmin

@site.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "is_published", "created_at"]
    search_fields = ["title", "content"]
    list_filter = ["is_published", "category"]
    ordering = ["-created_at"]
```

---

## List View Options

### list_display

Which columns appear in the list table. Defaults to the first few model fields.

```python
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "is_published", "created_at"]
```

#### Custom columns

A name in `list_display` that is **not** a model field but **is** a method on the
admin becomes a computed column. Set `short_description` for the header and
`allow_html` to render markup:

```python
class PostAdmin(ModelAdmin):
    list_display = ["title", "word_count", "status_badge"]

    def word_count(self, obj):
        return len((obj.content or "").split())
    word_count.short_description = "Words"

    def status_badge(self, obj):
        cls = "green" if obj.is_published else "gray"
        label = "Published" if obj.is_published else "Draft"
        return f'<span class="badge {cls}">{label}</span>'
    status_badge.short_description = "Status"
    status_badge.allow_html = True
```

Custom columns are not database-sortable, so they render without a sort link.

### list_display_links

Which columns link to the change form. Defaults to the first column.

```python
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "created_at"]
    list_display_links = ["title"]
```

### list_filter

Adds a sidebar of filters. Each entry is either a **field name** (auto-generates
options from boolean values, `choices`, or distinct values) or a
**`SimpleListFilter`** subclass for custom logic.

```python
class PostAdmin(ModelAdmin):
    list_filter = ["is_published", "category"]
```

Custom filter:

```python
from aksara.contrib.admin import SimpleListFilter
from datetime import date, timedelta

class RecentlyPublishedFilter(SimpleListFilter):
    title = "Published"
    parameter_name = "published"

    def lookups(self, request, model_admin):
        return [("week", "This week"), ("month", "This month")]

    def queryset(self, request, queryset):
        today = date.today()
        if self.value() == "week":
            return queryset.filter(published_at__gte=today - timedelta(days=7))
        if self.value() == "month":
            return queryset.filter(published_at__gte=today - timedelta(days=30))
        return queryset

class PostAdmin(ModelAdmin):
    list_filter = ["is_published", RecentlyPublishedFilter]
```

### search_fields

Adds a search box. Searching matches any listed field (case-insensitive,
combined with OR) against the model's own columns.

```python
class PostAdmin(ModelAdmin):
    search_fields = ["title", "content"]
```

!!! note "Related-field search"
    Own-table fields are fully supported. Related lookups (e.g. `author__name`)
    are applied on a best-effort basis and depend on the ORM's relation filtering,
    which is still maturing — prefer own-table fields for reliable search.

### ordering

Default sort order. Prefix with `-` for descending. Clicking a sortable column
header overrides it for that request.

```python
class PostAdmin(ModelAdmin):
    ordering = ["-created_at"]
```

### Pagination

```python
class PostAdmin(ModelAdmin):
    list_per_page = 50        # rows per page (default 100)
    list_max_show_all = 200   # cap for the optional "Show all" link
```

---

## Form (Detail View) Options

### fields / exclude

`fields` lists exactly which fields appear (and their order); `exclude` removes
fields from the default set.

```python
class PostAdmin(ModelAdmin):
    fields = ["title", "slug", "content", "author", "is_published"]

class DraftAdmin(ModelAdmin):
    exclude = ["internal_notes"]
```

By default the form shows all editable fields except the primary key and the
auto-managed `created_at` / `updated_at` timestamps.

### fieldsets

Group fields into sections. Each section is `(title_or_None, options)` where
options may include `fields`, `description`, and `classes` (use `"collapse"` to
start collapsed).

```python
class PostAdmin(ModelAdmin):
    fieldsets = [
        (None, {"fields": ["title", "slug", "content"]}),
        ("Metadata", {
            "fields": ["author", "category", "tags"],
            "description": "Who wrote this and how it's categorized",
        }),
        ("Publication", {
            "fields": ["is_published", "published_at"],
            "classes": ["collapse"],
        }),
    ]
```

`fields`/`exclude` and `fieldsets` are alternatives — when `fieldsets` is set it
determines the form layout.

### readonly_fields

Fields shown on the form but not editable. Listed readonly fields appear when
included via `fields`/`fieldsets`; otherwise they're omitted from the default form.

```python
class PostAdmin(ModelAdmin):
    readonly_fields = ["created_at", "updated_at"]
```

### prepopulated_fields

Auto-fill a field from others as you type (commonly slugs). Stops updating once
the target field is edited manually.

```python
class PostAdmin(ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
```

### raw_id_fields

Render a relation field as a plain id text input instead of a dropdown — useful
when the related table is large.

```python
class PostAdmin(ModelAdmin):
    raw_id_fields = ["author"]
```

---

## Widgets

`formfield_overrides` assigns a custom widget to a field. JSON and Array fields
get their dedicated widgets automatically, but you can configure them explicitly
when you need different rows, item types, or limits.

```python
from aksara.contrib.admin import ModelAdmin
from aksara.contrib.admin.widgets import JSONAdminWidget, ArrayAdminWidget

class ProductAdmin(ModelAdmin):
    formfield_overrides = {
        "metadata": JSONAdminWidget(rows=16),              # JSON textarea + formatter
        "tags": ArrayAdminWidget(item_type="text"),        # ordered list editor
        "scores": ArrayAdminWidget(item_type="number"),    # numeric list editor
    }
```

### JSONAdminWidget

Use this for `JSON` fields. It renders a monospace textarea, pretty-prints the
initial value when possible, and includes a client-side format button. Submitted
values are still parsed by the admin form handling before save.

```python
JSONAdminWidget(rows=12, pretty_print=True)
```

### ArrayAdminWidget

Use this for PostgreSQL-style array fields. It renders repeatable rows, supports
add/remove and drag reorder controls, and stores the resulting list in a hidden
field submitted with the form.

```python
ArrayAdminWidget(item_type="text", min_rows=1, max_rows=20)
```

Supported `item_type` values are regular HTML input types such as `"text"`,
`"number"`, `"email"`, and `"url"`.

---

## Bulk Actions

Declare actions by name in `actions` and define them with the `@action`
decorator. Each action receives the request and a queryset of the selected rows.
Use `message_user` to report results; `permissions` ties the action to a
permission check (`["change"]` requires `has_change_permission`).

```python
from aksara.contrib.admin import ModelAdmin, action

class PostAdmin(ModelAdmin):
    actions = ["publish_selected", "delete_selected"]   # delete_selected is built in

    @action(description="Publish selected posts", permissions=["change"])
    async def publish_selected(self, request, queryset):
        count = await queryset.update(is_published=True)
        self.message_user(request, f"Published {count} posts.", level="success")
```

The list view shows an action dropdown and per-row checkboxes; `delete_selected`
is provided out of the box.

Action permissions are checked twice: once at the list level and again for each
selected object when the permission hook accepts `obj`. This prevents bulk
actions from bypassing object-level `has_change_permission` or
`has_delete_permission` rules.

---

## Permissions

Override the permission methods to control access. They may be **sync or async**
and read the user from `request.state.user`.

```python
class PostAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return request.state.user.is_staff

    def has_change_permission(self, request, obj=None):
        user = request.state.user
        if obj is None or user.is_superuser:
            return user.is_staff
        return str(obj.author_id) == str(user.id)
```

`has_module_permission(self, request)` controls whether the model appears in the
dashboard/sidebar at all. See [Permissions](admin-permissions.md) for the full
picture.

---

## Hooks

### get_queryset

Customize the records shown. It is **async** — await `super().get_queryset()` and
chain queryset methods:

```python
class PostAdmin(ModelAdmin):
    async def get_queryset(self, request):
        qs = await super().get_queryset(request)
        if not request.state.user.is_superuser:
            qs = qs.filter(author_id=str(request.state.user.id))
        return qs
```

### save_model / delete_model

```python
class PostAdmin(ModelAdmin):
    async def save_model(self, request, obj, form_data, is_created):
        if is_created:
            obj.author_id = str(request.state.user.id)
        await super().save_model(request, obj, form_data, is_created)

    async def delete_model(self, request, obj):
        await obj.delete()
```

`save_model` validates submitted many-to-many ids before mutating relations. If a
related id can't be resolved it raises `ValueError`, which the form surfaces
rather than silently dropping the selection. When many-to-many data is present,
the save and relation update run inside one transaction so relation updates roll
back if a later step fails.

---

## Quick Reference

| Option | Purpose |
|--------|---------|
| `list_display` | Columns in the list (fields or custom methods) |
| `list_display_links` | Which columns link to the change form |
| `list_filter` | Sidebar filters (field names or `SimpleListFilter`) |
| `search_fields` | Searchable fields |
| `ordering` | Default sort |
| `list_per_page` / `list_max_show_all` | Pagination |
| `fields` / `exclude` / `fieldsets` | Form layout |
| `readonly_fields` | Non-editable fields |
| `prepopulated_fields` | Auto-filled fields (e.g. slug) |
| `raw_id_fields` | Relation as id text input |
| `formfield_overrides` | Custom widgets |
| `actions` | Bulk operations |

---

## Related Documentation

- [AdminSite](admin-site.md) — Configure and mount the admin
- [Permissions](admin-permissions.md) — Control access
- [Models](../orm/models.md) — Define your data
