# ModelAdmin

Control how your data appears and behaves in the admin interface.

---

## What is ModelAdmin?

A **ModelAdmin** is a configuration class that tells the admin interface how to display and handle a specific model. Without it, the admin uses sensible defaults. With it, you can customize everything.

```python
from aksara.contrib.admin import ModelAdmin

@admin.register(Post)
class PostAdmin(ModelAdmin):
    # What columns appear in the list
    list_display = ["title", "author", "is_published", "created_at"]
    
    # What fields users can search
    search_fields = ["title", "content"]
    
    # Sidebar filters for narrowing results
    list_filter = ["is_published", "category"]
```

---

## List View Options

The **list view** shows all records in a table format. These options control that table.

### list_display

**What it does**: Specifies which columns appear in the list table.

**Default**: Shows all fields (can be cluttered for models with many fields).

```python
class PostAdmin(ModelAdmin):
    # Show these 4 columns in the table
    list_display = ["title", "author", "is_published", "created_at"]
```

**Result**:
```
┌──────────────┬─────────┬───────────┬────────────┐
│ Title        │ Author  │ Published │ Created    │
├──────────────┼─────────┼───────────┼────────────┤
│ Hello World  │ Alice   │ ✓         │ 2024-01-15 │
│ My Draft     │ Bob     │ ✗         │ 2024-01-14 │
└──────────────┴─────────┴───────────┴────────────┘
```

#### Custom Columns

You can add columns that don't exist as fields—computed values like word counts or formatted badges:

```python
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "word_count", "status_badge"]
    
    def word_count(self, obj):
        """Count words in the content field."""
        return len(obj.content.split())
    word_count.short_description = "Words"  # Column header
    
    def status_badge(self, obj):
        """Show a colored badge instead of True/False."""
        if obj.is_published:
            return '<span class="badge green">Published</span>'
        return '<span class="badge gray">Draft</span>'
    status_badge.allow_html = True  # Allow HTML rendering
```

---

### list_display_links

**What it does**: Specifies which columns are clickable links to the edit page.

**Default**: The first column is a link.

```python
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "created_at"]
    list_display_links = ["title"]  # Only title is clickable
```

Set to `None` to make no columns clickable (view-only list).

---

### list_filter

**What it does**: Adds a sidebar with filters to narrow down the list.

**Why use it**: When you have hundreds of records, filters help find specific subsets quickly.

```python
class PostAdmin(ModelAdmin):
    list_filter = [
        "is_published",      # Checkbox: Published? Yes/No
        "category",          # Dropdown: all categories
        "created_at",        # Date picker: Today, Past 7 days, This month, etc.
        "author__is_staff",  # Filter by a related model's field
    ]
```

**Result**: A sidebar appears with filter options:
```
Filters
─────────────────
Published
  ○ All
  ● Yes
  ○ No

Category
  ○ All
  ○ Tech
  ○ News
  ○ Tutorial
```

#### Custom Filters

For complex filtering logic, create a custom filter class:

```python
from aksara.contrib.admin import SimpleListFilter
from datetime import date, timedelta

class RecentlyPublishedFilter(SimpleListFilter):
    title = "Published"              # Sidebar section title
    parameter_name = "published"     # URL query parameter
    
    def lookups(self, request, model_admin):
        """Define the filter options."""
        return [
            ("today", "Today"),
            ("week", "This Week"),
            ("month", "This Month"),
        ]
    
    def queryset(self, request, queryset):
        """Filter the queryset based on selected option."""
        today = date.today()
        
        if self.value() == "today":
            return queryset.filter(published_at__date=today)
        if self.value() == "week":
            return queryset.filter(published_at__gte=today - timedelta(days=7))
        if self.value() == "month":
            return queryset.filter(published_at__gte=today - timedelta(days=30))
        
        return queryset  # No filter applied

class PostAdmin(ModelAdmin):
    list_filter = ["is_published", RecentlyPublishedFilter]
```

---

### search_fields

**What it does**: Enables a search box and specifies which fields to search.

**How it works**: When a user types "hello", the admin finds records where any search field contains "hello".

```python
class PostAdmin(ModelAdmin):
    search_fields = [
        "title",           # Search in post title
        "content",         # Search in post content
        "author__name",    # Search in related author's name
        "author__email",   # Search in related author's email
    ]
```

**Syntax for related fields**: Use double underscores (`__`) to search fields on related models. `author__name` means "the name field of the related author".

---

### ordering

**What it does**: Sets the default sort order for the list.

**Syntax**: Prefix with `-` for descending (newest first), no prefix for ascending (oldest first).

```python
class PostAdmin(ModelAdmin):
    ordering = ["-created_at"]  # Newest posts first
```

```python
class PostAdmin(ModelAdmin):
    ordering = ["title"]  # Alphabetical by title (A-Z)
```

```python
class PostAdmin(ModelAdmin):
    ordering = ["-is_featured", "-created_at"]  # Featured first, then by date
```

---

### list_per_page

**What it does**: How many records to show per page.

**Default**: 20

```python
class PostAdmin(ModelAdmin):
    list_per_page = 50  # Show 50 records per page
```

---

### list_max_show_all

**What it does**: Maximum records for the "Show all" link (disables pagination).

**Default**: 200

```python
class PostAdmin(ModelAdmin):
    list_max_show_all = 500  # Allow showing up to 500 at once
```

---

## Detail View Options

The **detail view** is the form for creating or editing a single record.

### fields

**What it does**: Specifies which fields appear on the edit form and in what order.

**Default**: All fields appear.

```python
class PostAdmin(ModelAdmin):
    fields = ["title", "slug", "content", "author", "category", "tags"]
```

---

### exclude

**What it does**: Hides specific fields from the form (opposite of `fields`).

**When to use**: When you want most fields but need to hide a few.

```python
class PostAdmin(ModelAdmin):
    exclude = ["internal_notes", "legacy_id"]  # Hide these fields
```

---

### readonly_fields

**What it does**: Shows fields on the form but prevents editing.

**When to use**: For auto-generated fields like timestamps, or computed values.

```python
class PostAdmin(ModelAdmin):
    fields = ["title", "content", "created_at", "updated_at", "view_count"]
    readonly_fields = ["created_at", "updated_at", "view_count"]
```

---

### fieldsets

**What it does**: Groups fields into collapsible sections with headers.

**When to use**: For models with many fields—organizing them improves usability.

```python
class PostAdmin(ModelAdmin):
    fieldsets = [
        # Section 1: No header (None), always visible
        (None, {
            "fields": ["title", "slug", "content"],
        }),
        
        # Section 2: "Metadata" header
        ("Metadata", {
            "fields": ["author", "category", "tags"],
            "description": "Who wrote this and how it's categorized",
        }),
        
        # Section 3: Collapsed by default
        ("Publication Settings", {
            "fields": ["is_published", "published_at", "is_featured"],
            "classes": ["collapse"],  # Start collapsed
        }),
        
        # Section 4: SEO settings, also collapsed
        ("SEO", {
            "fields": ["seo_title", "seo_description"],
            "classes": ["collapse"],
            "description": "Search engine optimization settings",
        }),
    ]
```

**Result**:
```
┌─────────────────────────────────────┐
│ Title: [___________________________]│
│ Slug:  [___________________________]│
│ Content:                            │
│ [                                  ]│
├─────────────────────────────────────┤
│ ▼ Metadata                          │
│   Who wrote this and how...         │
│   Author:   [Dropdown ▼]            │
│   Category: [Dropdown ▼]            │
│   Tags:     [___________]           │
├─────────────────────────────────────┤
│ ▶ Publication Settings (click to expand)
├─────────────────────────────────────┤
│ ▶ SEO (click to expand)             │
└─────────────────────────────────────┘
```

---

### prepopulated_fields

**What it does**: Auto-fills a field based on another field's value.

**Common use**: Generating URL slugs from titles.

```python
class PostAdmin(ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
```

**Result**: When you type "Hello World" in the title, the slug auto-fills with "hello-world".

---

### raw_id_fields

**What it does**: Shows a text input for IDs instead of a dropdown for related fields.

**When to use**: When the related table has thousands of records (dropdowns would be slow).

```python
class PostAdmin(ModelAdmin):
    raw_id_fields = ["author"]  # Type author ID instead of picking from dropdown
```

---

### autocomplete_fields

**What it does**: Shows a searchable autocomplete box for related fields.

**When to use**: Best of both worlds—handles large tables but still user-friendly.

```python
class PostAdmin(ModelAdmin):
    autocomplete_fields = ["author", "category"]
```

**Requirement**: The related ModelAdmin must have `search_fields` defined.

---

## Widgets

**Widgets** control how individual form fields are rendered. Most fields have sensible defaults, but you can customize them.

### formfield_overrides

**What it does**: Assigns custom widgets to specific fields.

```python
from aksara.contrib.admin import ModelAdmin
from aksara.contrib.admin.widgets import JSONAdminWidget, ArrayAdminWidget

class ProductAdmin(ModelAdmin):
    formfield_overrides = {
        "metadata": JSONAdminWidget(),  # Interactive JSON editor
        "tags": ArrayAdminWidget(),     # Dynamic list editor
    }
```

### Built-in Widgets

#### JSONAdminWidget

**What it does**: Provides an interactive JSON editor with syntax highlighting.

**When to use**: For JSON/JSONB fields that store structured data.

```python
from aksara.contrib.admin.widgets import JSONAdminWidget

class SettingsAdmin(ModelAdmin):
    formfield_overrides = {
        "config": JSONAdminWidget(),
    }
```

**Features**:

- Syntax highlighting (colors for keys, values, brackets)
- Real-time validation (shows errors as you type)
- Pretty-print formatting (auto-indents JSON)
- Collapsible sections for nested objects

#### ArrayAdminWidget

**What it does**: Provides a dynamic list editor for array fields.

**When to use**: For PostgreSQL array fields (like tags, categories).

```python
from aksara.contrib.admin.widgets import ArrayAdminWidget

class ArticleAdmin(ModelAdmin):
    formfield_overrides = {
        "tags": ArrayAdminWidget(),
    }
```

**Features**:

- Add/remove items with buttons
- Drag-and-drop reordering
- Validates each item individually
- Shows placeholder for empty lists

!!! tip "Auto-Detection"
    JSON and Array fields automatically use their respective widgets. You only need `formfield_overrides` for custom configuration or to override the default widget for a field.

---

## Actions

**Actions** are operations you can perform on multiple selected records at once.

### Built-in Actions

```python
class PostAdmin(ModelAdmin):
    actions = ["delete_selected"]  # Bulk delete (enabled by default)
```

### Custom Actions

```python
class PostAdmin(ModelAdmin):
    actions = ["publish_selected", "unpublish_selected", "export_csv"]
    
    @admin.action(description="Publish selected posts")
    async def publish_selected(self, request, queryset):
        """Mark all selected posts as published."""
        count = await queryset.update(is_published=True)
        self.message_user(request, f"Published {count} posts")
    
    @admin.action(description="Unpublish selected posts")
    async def unpublish_selected(self, request, queryset):
        """Mark all selected posts as unpublished."""
        count = await queryset.update(is_published=False)
        self.message_user(request, f"Unpublished {count} posts")
    
    @admin.action(description="Export as CSV")
    async def export_csv(self, request, queryset):
        """Download selected posts as a CSV file."""
        posts = await queryset.all()
        csv_data = generate_csv(posts)
        return FileResponse(csv_data, filename="posts.csv")
```

**How users see this**: A dropdown above the list + checkboxes on each row:

```
Action: [Publish selected posts ▼] [Go]

☑ Title           Author    Published
☐ Hello World     Alice     ✓
☑ My Draft        Bob       ✗
☑ Breaking News   Carol     ✗
```

---

## Permissions

Control who can do what in the admin.

### Object-Level Permissions

Override these methods to control access per-record:

```python
class PostAdmin(ModelAdmin):
    def has_view_permission(self, request, obj=None):
        """Can this user view posts?"""
        return True  # Everyone can view
    
    def has_add_permission(self, request):
        """Can this user create new posts?"""
        return request.user.is_staff
    
    def has_change_permission(self, request, obj=None):
        """Can this user edit this post?"""
        if obj is None:
            # General permission (for the list view)
            return request.user.is_staff
        # Specific permission: can only edit own posts
        return (
            request.user.is_superuser or
            str(obj.author_id) == str(request.user.id)
        )
    
    def has_delete_permission(self, request, obj=None):
        """Can this user delete posts?"""
        return request.user.is_superuser  # Only superusers
```

---

## Hooks

Hooks let you run custom code at specific points.

### save_model

**When it runs**: Before saving a new or updated record.

```python
class PostAdmin(ModelAdmin):
    async def save_model(self, request, obj, form, change):
        """
        obj: the model instance being saved
        form: the submitted form data
        change: True if editing, False if creating
        """
        if not change:
            # Creating new post: set the author automatically
            obj.author_id = str(request.user.id)
        
        # Always track who last modified
        obj.updated_by_id = str(request.user.id)
        
        await obj.save()
```

### delete_model

**When it runs**: Before deleting a record.

```python
class PostAdmin(ModelAdmin):
    async def delete_model(self, request, obj):
        """Soft delete instead of actually deleting."""
        obj.is_deleted = True
        obj.deleted_at = datetime.now()
        await obj.save()
        # Note: we don't call obj.delete()
```

---

## QuerySet Customization

### get_queryset

**What it does**: Customize which records appear in the list.

```python
class PostAdmin(ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Optimization: load related data in one query
        qs = qs.select_related("author", "category")
        
        # Security: non-superusers only see their own posts
        if not request.user.is_superuser:
            qs = qs.filter(author_id=str(request.user.id))
        
        return qs
```

---

## Complete Example

```python
from aksara.contrib.admin import ModelAdmin, SimpleListFilter
from aksara.contrib.admin.widgets import JSONAdminWidget
from datetime import date, timedelta


class RecentFilter(SimpleListFilter):
    """Filter posts by publication date."""
    title = "Published"
    parameter_name = "when"
    
    def lookups(self, request, model_admin):
        return [
            ("today", "Today"),
            ("week", "This Week"),
            ("month", "This Month"),
        ]
    
    def queryset(self, request, queryset):
        today = date.today()
        if self.value() == "today":
            return queryset.filter(published_at__date=today)
        if self.value() == "week":
            return queryset.filter(published_at__gte=today - timedelta(days=7))
        if self.value() == "month":
            return queryset.filter(published_at__gte=today - timedelta(days=30))
        return queryset


@admin.register(Post)
class PostAdmin(ModelAdmin):
    """Full-featured Post admin."""
    
    # ─── List View ─────────────────────────────────────
    list_display = [
        "title", "author", "category", "status_badge",
        "view_count", "created_at",
    ]
    list_display_links = ["title"]
    list_filter = ["is_published", "is_featured", "category", RecentFilter]
    search_fields = ["title", "content", "author__name"]
    ordering = ["-created_at"]
    list_per_page = 25
    
    # ─── Detail View ───────────────────────────────────
    fieldsets = [
        (None, {
            "fields": ["title", "slug", "content"],
        }),
        ("Categorization", {
            "fields": ["author", "category", "tags"],
        }),
        ("Publication", {
            "fields": ["is_published", "is_featured", "published_at"],
            "classes": ["collapse"],
        }),
        ("SEO", {
            "fields": ["seo_title", "seo_description"],
            "classes": ["collapse"],
        }),
    ]
    readonly_fields = ["created_at", "updated_at", "view_count"]
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ["author", "category"]
    
    # ─── Widgets ───────────────────────────────────────
    formfield_overrides = {
        "metadata": JSONAdminWidget(),
    }
    
    # ─── Actions ───────────────────────────────────────
    actions = ["publish_selected", "feature_selected"]
    
    def status_badge(self, obj):
        """Custom column: colored status badge."""
        if obj.is_featured:
            return '<span class="badge gold">Featured</span>'
        if obj.is_published:
            return '<span class="badge green">Published</span>'
        return '<span class="badge gray">Draft</span>'
    status_badge.allow_html = True
    status_badge.short_description = "Status"
    
    @admin.action(description="Publish selected")
    async def publish_selected(self, request, queryset):
        count = await queryset.update(is_published=True)
        self.message_user(request, f"Published {count} posts")
    
    @admin.action(description="Feature selected")
    async def feature_selected(self, request, queryset):
        count = await queryset.update(is_featured=True)
        self.message_user(request, f"Featured {count} posts")
    
    def get_queryset(self, request):
        """Optimize queries and filter by user."""
        qs = super().get_queryset(request)
        qs = qs.select_related("author", "category")
        if not request.user.is_superuser:
            qs = qs.filter(author_id=str(request.user.id))
        return qs
    
    def has_change_permission(self, request, obj=None):
        """Users can only edit their own posts."""
        if request.user.is_superuser:
            return True
        if obj and str(obj.author_id) == str(request.user.id):
            return True
        return False
    
    async def save_model(self, request, obj, form, change):
        """Auto-set author on create."""
        if not change:
            obj.author_id = str(request.user.id)
        await obj.save()
```

---

## Quick Reference

| Option | Purpose | Example |
|--------|---------|---------|
| `list_display` | Columns in list | `["title", "author"]` |
| `list_filter` | Sidebar filters | `["status", "category"]` |
| `search_fields` | Searchable fields | `["title", "content"]` |
| `ordering` | Default sort | `["-created_at"]` |
| `fields` | Form fields | `["title", "content"]` |
| `readonly_fields` | Non-editable fields | `["created_at"]` |
| `fieldsets` | Grouped sections | See example above |
| `actions` | Bulk operations | `["publish", "delete"]` |

---

## Related Documentation

- [AdminSite](admin-site.md) — Configure the admin dashboard
- [Permissions](admin-permissions.md) — Control access
- [Models](../orm/models.md) — Define your data
