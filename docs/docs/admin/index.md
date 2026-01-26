# Admin Interface

Automatic admin panels for your Vidyut models.

---

## Overview

Vidyut provides a built-in admin interface for managing your data:

```python
from vidyut.contrib.admin import AdminSite, ModelAdmin
from myapp.models import Post, Author

admin = AdminSite()

@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "is_published", "created_at"]
    search_fields = ["title", "content"]

# Mount on your app
app.mount("/admin", admin)
```

---

## Quick Start

### 1. Create Admin Site

```python
# admin.py
from vidyut.contrib.admin import AdminSite

admin = AdminSite(
    title="My Admin",
    site_header="My Application Admin",
)
```

### 2. Register Models

```python
from vidyut.contrib.admin import ModelAdmin
from myapp.models import Post, Author, Category

@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "is_published"]

@admin.register(Author)
class AuthorAdmin(ModelAdmin):
    list_display = ["name", "email"]

# Or simple registration
admin.register(Category)
```

### 3. Mount Admin

```python
# main.py
from vidyut import Vidyut
from myapp.admin import admin

app = Vidyut()
app.mount("/admin", admin)
```

### 4. Access Admin

Navigate to `http://localhost:8000/admin/`

---

## Key Features

- **Auto-generated UI** — CRUD interface from models
- **Search and filter** — Find records quickly
- **Permissions** — Control who can access what
- **Customizable** — Tailor the interface to your needs
- **Responsive** — Works on mobile devices

---

## Section Contents

<div class="grid cards" markdown>

-   :material-cog: **[AdminSite](admin-site.md)**
    
    Configure your admin instance

-   :material-view-list: **[ModelAdmin](model-admin.md)**
    
    Customize model administration

-   :material-shield-lock: **[Permissions](admin-permissions.md)**
    
    Control admin access

</div>

---

## Example: Complete Admin Setup

```python
# admin.py
from vidyut.contrib.admin import AdminSite, ModelAdmin
from vidyut.permissions import IsAdminUser
from myapp.models import Post, Author, Category, Tag


# Create admin site
admin = AdminSite(
    title="Blog Admin",
    site_header="Blog Administration",
    index_title="Dashboard",
)


@admin.register(Post)
class PostAdmin(ModelAdmin):
    """Admin for blog posts."""
    
    # List view
    list_display = ["title", "author", "category", "is_published", "created_at"]
    list_filter = ["is_published", "category", "created_at"]
    search_fields = ["title", "content"]
    ordering = ["-created_at"]
    
    # Detail view
    fields = [
        "title", "slug", "content",
        "author", "category", "tags",
        "is_published", "is_featured",
    ]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Author)
class AuthorAdmin(ModelAdmin):
    """Admin for authors."""
    
    list_display = ["name", "email", "post_count", "created_at"]
    search_fields = ["name", "email"]
    
    def post_count(self, obj):
        """Custom column showing post count."""
        return len(obj.posts)


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    """Admin for categories."""
    
    list_display = ["name", "slug", "parent"]
    prepopulated_fields = {"slug": ("name",)}


# Simple registration (defaults)
admin.register(Tag)
```

```python
# main.py
from vidyut import Vidyut
from vidyut.contrib.auth.middleware import AuthenticationMiddleware
from myapp.admin import admin

app = Vidyut()

# Auth middleware (required for admin)
app.add_middleware(AuthenticationMiddleware)

# Mount admin
app.mount("/admin", admin)
```

---

## Related Documentation

- [Authentication](../api/authentication.md) — User authentication
- [Permissions](../api/permissions.md) — Access control
- [Models](../orm/models.md) — Model definition
