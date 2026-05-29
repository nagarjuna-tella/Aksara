# Admin Interface

A web-based dashboard that lets you view, create, edit, and delete your data without writing code.

---

## What is an Admin Interface?

An **admin interface** (or admin panel) is a private website where you manage your application's data. Instead of writing database queries or building forms manually, Aksara generates a complete management interface automatically from your models.

```python
from aksara.contrib.admin import site, ModelAdmin, include_admin
from myapp.models import Post

# Register a model with the admin site
@site.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "is_published", "created_at"]
    search_fields = ["title", "content"]
    list_filter = ["is_published"]

# Mount the admin onto your app at /admin/
include_admin(app)
```

---

## Quick Start

### 1. Register Models

There is a ready-to-use global admin site, `site`. **Registering** a model tells the admin: "I want to manage this type of data." Once registered, the admin creates pages to list, add, edit, and delete records.

```python
# admin.py
from aksara.contrib.admin import site, ModelAdmin
from myapp.models import Post, Author, Category

# Full control: customize how Post appears in admin
@site.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "is_published"]

# Quick registration: use all defaults
site.register(Category)
```

### 2. Mount the Admin

`include_admin()` attaches the admin routes (and the required session/CSRF middleware and static files) to your application.

```python
# main.py
from aksara import Aksara
from aksara.contrib.admin import include_admin
import myapp.admin  # noqa: F401 — registers models with `site`

app = Aksara(database_url="postgresql://localhost/myapp")
include_admin(app)              # Admin at /admin/
# include_admin(app, prefix="/manage")   # …or a custom prefix
```

!!! note "Auto-mount in development"
    When `debug=True` (and the auth contrib is available), Aksara auto-mounts the
    admin at `/admin/`, so an explicit `include_admin(app)` is optional in
    development. Set `enable_admin=True` to mount it in production.

### 3. Access the Admin

Start your server and navigate to `http://localhost:8000/admin/`. You'll see a dashboard listing the apps and models you can manage. Admin access requires an authenticated **staff** user (`is_staff=True`).

---

## Key Features

| Feature | What It Does |
|---------|--------------|
| **Auto-generated UI** | List, add, edit, and delete pages generated from your models |
| **Search** | `search_fields` adds a search box across model fields |
| **Filters** | `list_filter` adds a sidebar to narrow records by field value |
| **Ordering & pagination** | `ordering`, sortable columns, and `list_per_page` |
| **Bulk actions** | Run an operation on selected rows (incl. built-in delete) |
| **Permissions** | Per-model and per-object access control |
| **Custom columns** | Computed/formatted columns from `ModelAdmin` methods |
| **Structured widgets** | JSON and array editors for complex fields |

---

## Core Concepts

### Models vs. ModelAdmin

- A **Model** defines your data structure (what fields exist, what types they are).
- A **ModelAdmin** controls how that model appears in the admin (which columns show, what's searchable, how forms are laid out).

```python
class Post(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    is_published = fields.Boolean(default=False)

@site.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "is_published"]   # columns in the list
    search_fields = ["title", "content"]        # fields to search
```

### List View vs. Detail View

- **List View**: a paginated table of records, with optional search, filters, sortable columns and bulk actions.
- **Detail View**: a form for creating or editing a single record, optionally grouped into fieldsets.

### Admin vs. Studio

Aksara ships two browser UIs with different jobs:

| UI | Path | Use it for |
|----|------|------------|
| **Admin** | `/admin/` | Day-to-day data management by authenticated staff users: create records, edit content, run bulk actions, and review model data. |
| **Studio** | `/studio/ui` | Developer/operator inspection: models, routes, migrations, diagnostics, AI tools, and project health. |

Use Admin when a user is managing application data. Use Studio when a developer
or operator is inspecting how the application is built and running. They share
the same app process, but their security settings are separate.

---

## Security Defaults

Admin access requires a staff user by default. Form POSTs use a same-site CSRF
cookie and hidden form token, and login/action POSTs are rate-limited.

!!! warning "Do not disable CSRF in production"
    `AKSARA_ADMIN_CSRF_ENABLED=false` is intended only for controlled tests or
    local debugging. Leave CSRF enabled for deployed admin sites.

---

## Complete Example

```python
# admin.py
from aksara.contrib.admin import site, ModelAdmin, action
from myapp.models import Post, Author, Category, Tag


@site.register(Post)
class PostAdmin(ModelAdmin):
    """Manage blog posts."""

    list_display = ["title", "author", "category", "is_published", "created_at"]
    list_display_links = ["title"]
    list_filter = ["is_published", "category"]
    search_fields = ["title", "content"]
    ordering = ["-created_at"]
    list_per_page = 25

    fieldsets = [
        (None, {"fields": ["title", "slug", "content"]}),
        ("Publication", {
            "fields": ["author", "category", "tags", "is_published"],
            "classes": ["collapse"],
        }),
    ]
    readonly_fields = ["created_at", "updated_at"]
    prepopulated_fields = {"slug": ("title",)}
    actions = ["publish_selected"]

    @action(description="Publish selected posts", permissions=["change"])
    async def publish_selected(self, request, queryset):
        count = await queryset.update(is_published=True)
        self.message_user(request, f"Published {count} posts.")


site.register(Author)
site.register(Category)
site.register(Tag)
```

```python
# main.py
from aksara import Aksara
from aksara.contrib.admin import include_admin
import myapp.admin  # noqa: F401

app = Aksara(database_url="postgresql://localhost/myapp")
include_admin(app)
```

---

## Related Documentation

- [AdminSite](admin-site.md) — Configure and mount admin sites
- [ModelAdmin](model-admin.md) — Customize how each model appears
- [Permissions](admin-permissions.md) — Control who can access what
- [Actions](actions.md) — Define and guard bulk operations
- [Widgets](widgets.md) — Configure JSON and array form widgets
- [Models](../orm/models.md) — Define your data structure
