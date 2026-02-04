# ModelAdmin

Customize how models appear in the admin interface.

---

## Overview

`ModelAdmin` controls the admin interface for a specific model:

```python
from aksara.contrib.admin import ModelAdmin

@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "is_published", "created_at"]
    search_fields = ["title", "content"]
    list_filter = ["is_published", "category"]
```

---

## List View Options

### list_display

Columns to show in the list view:

```python
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "is_published", "created_at"]
```

#### Custom Columns

```python
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "word_count", "status_badge"]
    
    def word_count(self, obj):
        """Custom column: word count."""
        return len(obj.content.split())
    word_count.short_description = "Words"
    
    def status_badge(self, obj):
        """Custom column with HTML."""
        if obj.is_published:
            return '<span class="badge green">Published</span>'
        return '<span class="badge gray">Draft</span>'
    status_badge.allow_html = True
```

### list_display_links

Which columns link to the edit page:

```python
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "created_at"]
    list_display_links = ["title"]  # Only title links to edit
```

### list_filter

Sidebar filters:

```python
class PostAdmin(ModelAdmin):
    list_filter = [
        "is_published",      # Boolean filter
        "category",          # ForeignKey filter
        "created_at",        # Date filter
        "author__is_staff",  # Related field filter
    ]
```

#### Custom Filters

```python
from aksara.contrib.admin import SimpleListFilter

class PublishedRecentlyFilter(SimpleListFilter):
    title = "Published Recently"
    parameter_name = "recent"
    
    def lookups(self, request, model_admin):
        return [
            ("today", "Today"),
            ("week", "This Week"),
            ("month", "This Month"),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == "today":
            return queryset.filter(published_at__date=date.today())
        if self.value() == "week":
            return queryset.filter(published_at__gte=week_ago)
        if self.value() == "month":
            return queryset.filter(published_at__gte=month_ago)
        return queryset

class PostAdmin(ModelAdmin):
    list_filter = ["is_published", PublishedRecentlyFilter]
```

### search_fields

Fields to search:

```python
class PostAdmin(ModelAdmin):
    search_fields = [
        "title",              # Exact field
        "content",            # Text search
        "author__name",       # Related field
        "author__email",
    ]
```

### ordering

Default sort order:

```python
class PostAdmin(ModelAdmin):
    ordering = ["-created_at"]  # Newest first
```

### list_per_page

Items per page:

```python
class PostAdmin(ModelAdmin):
    list_per_page = 25  # Default: 20
```

### list_max_show_all

Maximum for "Show all":

```python
class PostAdmin(ModelAdmin):
    list_max_show_all = 500  # Default: 200
```

---

## Detail View Options

### fields

Fields to show on edit form:

```python
class PostAdmin(ModelAdmin):
    fields = ["title", "slug", "content", "author", "category", "tags"]
```

### exclude

Fields to hide:

```python
class PostAdmin(ModelAdmin):
    exclude = ["internal_notes", "created_at"]
```

### readonly_fields

Non-editable fields:

```python
class PostAdmin(ModelAdmin):
    fields = ["title", "slug", "content", "created_at", "updated_at"]
    readonly_fields = ["created_at", "updated_at"]
```

### fieldsets

Group fields into sections:

```python
class PostAdmin(ModelAdmin):
    fieldsets = [
        (None, {
            "fields": ["title", "slug", "content"],
        }),
        ("Metadata", {
            "fields": ["author", "category", "tags"],
            "classes": ["collapse"],  # Collapsible
        }),
        ("Publication", {
            "fields": ["is_published", "published_at", "is_featured"],
        }),
        ("Advanced", {
            "fields": ["seo_title", "seo_description"],
            "classes": ["collapse"],
            "description": "SEO settings for this post",
        }),
    ]
```

### prepopulated_fields

Auto-fill fields based on others:

```python
class PostAdmin(ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
```

### raw_id_fields

Use ID input instead of dropdown for relations:

```python
class PostAdmin(ModelAdmin):
    raw_id_fields = ["author"]  # For large tables
```

### autocomplete_fields

Use autocomplete for relations:

```python
class PostAdmin(ModelAdmin):
    autocomplete_fields = ["author", "category"]
```

---

## Form Customization

### formfield_overrides

Customize widgets for specific fields:

```python
from aksara.contrib.admin import ModelAdmin
from aksara.contrib.admin.widgets import JSONAdminWidget, ArrayAdminWidget

class ProductAdmin(ModelAdmin):
    formfield_overrides = {
        "metadata": JSONAdminWidget(),
        "tags": ArrayAdminWidget(),
    }
```

### Built-in Widgets

Aksara provides specialized widgets for complex field types:

#### JSONAdminWidget

Interactive JSON editor with syntax highlighting and validation:

```python
from aksara.contrib.admin.widgets import JSONAdminWidget

class SettingsAdmin(ModelAdmin):
    formfield_overrides = {
        "config": JSONAdminWidget(),
    }
```

Features:

- Syntax-highlighted JSON editing
- Real-time validation
- Pretty-print formatting
- Collapsible tree view

#### ArrayAdminWidget

Dynamic list editor for array fields:

```python
from aksara.contrib.admin.widgets import ArrayAdminWidget

class ArticleAdmin(ModelAdmin):
    formfield_overrides = {
        "tags": ArrayAdminWidget(),
    }
```

Features:

- Add/remove items dynamically
- Drag-and-drop reordering
- Individual item validation
- Empty state handling

!!! tip "Auto-Detection"
    JSON and Array fields automatically use their respective widgets.
    Use `formfield_overrides` only when you need custom configuration.

### Custom Form

```python
from aksara.contrib.admin import ModelForm

class PostForm(ModelForm):
    class Meta:
        model = Post
        fields = "__all__"
    
    def clean_title(self):
        title = self.cleaned_data["title"]
        if len(title) < 10:
            raise ValidationError("Title too short")
        return title

class PostAdmin(ModelAdmin):
    form = PostForm
```

### Validation

```python
class PostAdmin(ModelAdmin):
    def clean(self, request, obj):
        """Custom validation."""
        if obj.is_published and not obj.content:
            raise ValidationError("Cannot publish without content")
        return obj
```

---

## Actions

### Built-in Actions

```python
class PostAdmin(ModelAdmin):
    actions = ["delete_selected"]  # Default delete action
```

### Custom Actions

```python
class PostAdmin(ModelAdmin):
    actions = ["publish_selected", "unpublish_selected", "export_csv"]
    
    @admin.action(description="Publish selected posts")
    async def publish_selected(self, request, queryset):
        count = await queryset.update(is_published=True)
        self.message_user(request, f"Published {count} posts")
    
    @admin.action(description="Export as CSV")
    async def export_csv(self, request, queryset):
        posts = await queryset.all()
        csv_data = generate_csv(posts)
        return FileResponse(csv_data, filename="posts.csv")
```

### Action Permissions

```python
@admin.action(description="Delete permanently")
async def delete_permanently(self, request, queryset):
    ...

delete_permanently.allowed_permissions = ["delete"]
```

---

## Permissions

### Object-Level Permissions

```python
class PostAdmin(ModelAdmin):
    def has_view_permission(self, request, obj=None):
        return True  # Everyone can view
    
    def has_add_permission(self, request):
        return request.user.is_staff
    
    def has_change_permission(self, request, obj=None):
        if obj is None:
            return request.user.is_staff
        # Can only edit own posts (unless admin)
        return (
            request.user.is_superuser or
            str(obj.author_id) == str(request.user.id)
        )
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
```

### Module-Level Permissions

```python
class PostAdmin(ModelAdmin):
    def has_module_permission(self, request):
        """Can user see this model in admin index?"""
        return request.user.has_perm("posts.view_post")
```

---

## QuerySet Customization

### get_queryset

```python
class PostAdmin(ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Optimize with select_related
        qs = qs.select_related("author", "category")
        
        # Non-superusers only see their posts
        if not request.user.is_superuser:
            qs = qs.filter(author_id=str(request.user.id))
        
        return qs
```

### get_search_results

```python
class PostAdmin(ModelAdmin):
    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )
        
        # Custom search logic
        if search_term.startswith("#"):
            tag_name = search_term[1:]
            queryset = queryset.filter(tags__name__icontains=tag_name)
        
        return queryset, use_distinct
```

---

## Hooks

### save_model

```python
class PostAdmin(ModelAdmin):
    async def save_model(self, request, obj, form, change):
        if not change:  # Creating new
            obj.author_id = str(request.user.id)
        
        obj.updated_by_id = str(request.user.id)
        await obj.save()
```

### delete_model

```python
class PostAdmin(ModelAdmin):
    async def delete_model(self, request, obj):
        # Soft delete instead
        obj.is_deleted = True
        obj.deleted_at = datetime.now()
        await obj.save()
```

### save_related

```python
class PostAdmin(ModelAdmin):
    async def save_related(self, request, form, formsets, change):
        await super().save_related(request, form, formsets, change)
        
        # Update tag counts
        for tag in form.instance.tags:
            tag.post_count = await tag.posts.count()
            await tag.save()
```

---

## Complete Example

```python
from aksara.contrib.admin import ModelAdmin, SimpleListFilter
from myapp.models import Post


class RecentFilter(SimpleListFilter):
    title = "Published"
    parameter_name = "published"
    
    def lookups(self, request, model_admin):
        return [
            ("today", "Today"),
            ("week", "This Week"),
            ("month", "This Month"),
        ]
    
    def queryset(self, request, queryset):
        from datetime import date, timedelta
        today = date.today()
        
        if self.value() == "today":
            return queryset.filter(published_at__date=today)
        if self.value() == "week":
            return queryset.filter(published_at__date__gte=today - timedelta(days=7))
        if self.value() == "month":
            return queryset.filter(published_at__date__gte=today - timedelta(days=30))
        return queryset


@admin.register(Post)
class PostAdmin(ModelAdmin):
    """Full-featured Post admin."""
    
    # List view
    list_display = [
        "title", "author", "category", "status_badge",
        "view_count", "created_at",
    ]
    list_display_links = ["title"]
    list_filter = ["is_published", "is_featured", "category", RecentFilter]
    search_fields = ["title", "content", "author__name"]
    ordering = ["-created_at"]
    list_per_page = 25
    
    # Detail view
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
    
    # Actions
    actions = ["publish_selected", "unpublish_selected", "feature_selected"]
    
    def status_badge(self, obj):
        """Show publication status as badge."""
        if obj.is_featured:
            return '<span class="badge gold">Featured</span>'
        if obj.is_published:
            return '<span class="badge green">Published</span>'
        return '<span class="badge gray">Draft</span>'
    status_badge.allow_html = True
    status_badge.short_description = "Status"
    
    @admin.action(description="Publish selected")
    async def publish_selected(self, request, queryset):
        count = await queryset.update(
            is_published=True,
            published_at=datetime.now(),
        )
        self.message_user(request, f"Published {count} posts")
    
    @admin.action(description="Unpublish selected")
    async def unpublish_selected(self, request, queryset):
        count = await queryset.update(is_published=False)
        self.message_user(request, f"Unpublished {count} posts")
    
    @admin.action(description="Feature selected")
    async def feature_selected(self, request, queryset):
        count = await queryset.update(is_featured=True)
        self.message_user(request, f"Featured {count} posts")
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("author", "category")
    
    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj and str(obj.author_id) == str(request.user.id):
            return True
        return False
    
    async def save_model(self, request, obj, form, change):
        if not change:
            obj.author_id = str(request.user.id)
        await obj.save()
```

---

## Related Documentation

- [AdminSite](admin-site.md) — Admin configuration
- [Admin Permissions](admin-permissions.md) — Access control
- [Models](../orm/models.md) — Model definition
