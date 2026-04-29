# Admin Interface

A web-based dashboard that lets you view, create, edit, and delete your data without writing code.

---

## What is an Admin Interface?

An **admin interface** (or admin panel) is a private website where you manage your application's data. Instead of writing database queries or building forms manually, Aksara generates a complete management interface automatically from your models.

Think of it like a spreadsheet for your database—but with forms, search, filters, and user permissions built in.

```python
from aksara.contrib.admin import AdminSite, ModelAdmin
from myapp.models import Post, Author

# Create an admin site (the main admin dashboard)
admin = AdminSite()

# Register a model (tell admin to manage this data)
@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "is_published", "created_at"]
    search_fields = ["title", "content"]

# Attach admin to your app at the /admin/ URL
app.mount("/admin", admin)
```

---

## Quick Start

### 1. Create an Admin Site

An **AdminSite** is the main container for your admin interface. It holds all the models you want to manage.

```python
# admin.py
from aksara.contrib.admin import AdminSite

admin = AdminSite(
    title="My Admin",           # Browser tab title
    site_header="My App Admin", # Header text shown on every page
)
```

### 2. Register Models

**Registering** a model tells the admin: "I want to manage this type of data." Once registered, the admin creates pages to list, add, edit, and delete records.

```python
from aksara.contrib.admin import ModelAdmin
from myapp.models import Post, Author, Category

# Full control: customize how Post appears in admin
@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "is_published"]

# Another customized model
@admin.register(Author)
class AuthorAdmin(ModelAdmin):
    list_display = ["name", "email"]

# Quick registration: use all defaults
admin.register(Category)
```

### 3. Mount the Admin

**Mounting** attaches the admin to your application at a URL path. This makes the admin accessible via your web server.

```python
# main.py
from aksara import Aksara
from myapp.admin import admin

app = Aksara()
app.mount("/admin", admin)  # Admin is now at /admin/
```

### 4. Access the Admin

Start your server and navigate to `http://localhost:8000/admin/`

You'll see a dashboard listing all your registered models, with options to manage each one.

---

## Key Features

| Feature | What It Does |
|---------|--------------|
| **Auto-generated UI** | Creates list, add, edit, delete pages automatically from your models |
| **Search** | Find records by typing keywords |
| **Filters** | Narrow down records by field values (like "show only published posts") |
| **Permissions** | Control who can view, add, edit, or delete data |
| **Responsive** | Works on phones, tablets, and desktops |

---

## Core Concepts

### Models vs. ModelAdmin

- A **Model** defines your data structure (what fields exist, what types they are)
- A **ModelAdmin** controls how that model appears in the admin (which columns show, what's searchable)

```python
# This is a MODEL - defines the data
class Post(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    is_published = fields.Boolean(default=False)

# This is a MODELADMIN - controls the admin interface
@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "is_published"]  # Columns in the list
    search_fields = ["title", "content"]       # Fields to search
```

### List View vs. Detail View

The admin has two main views for each model:

- **List View**: A table showing all records (like a spreadsheet)
- **Detail View**: A form for viewing/editing a single record

```
List View (all posts)          Detail View (editing one post)
┌────────────────────────┐     ┌────────────────────────┐
│ Title     │ Published  │     │ Title: [My Post     ]  │
├───────────┼────────────┤     │ Content:               │
│ My Post   │ ✓          │────▶│ [                   ]  │
│ Draft     │ ✗          │     │ Published: [✓]         │
│ News      │ ✓          │     │ [Save] [Delete]        │
└────────────────────────┘     └────────────────────────┘
```

---

## Section Contents

<div class="grid cards" markdown>

-   :material-cog: **[AdminSite](admin-site.md)**
    
    Configure the main admin dashboard

-   :material-view-list: **[ModelAdmin](model-admin.md)**
    
    Customize how each model appears

-   :material-shield-lock: **[Permissions](admin-permissions.md)**
    
    Control who can access what

</div>

---

## Complete Example

Here's a full admin setup for a blog application:

```python
# admin.py
from aksara.contrib.admin import AdminSite, ModelAdmin
from myapp.models import Post, Author, Category, Tag


# Create the admin site
admin = AdminSite(
    title="Blog Admin",
    site_header="Blog Administration",
    index_title="Dashboard",
)


@admin.register(Post)
class PostAdmin(ModelAdmin):
    """Manage blog posts."""
    
    # List view: what columns to show
    list_display = ["title", "author", "category", "is_published", "created_at"]
    
    # List view: sidebar filters
    list_filter = ["is_published", "category", "created_at"]
    
    # List view: searchable fields
    search_fields = ["title", "content"]
    
    # List view: default sort order (- means descending)
    ordering = ["-created_at"]
    
    # Detail view: which fields to show on the edit form
    fields = [
        "title", "slug", "content",
        "author", "category", "tags",
        "is_published", "is_featured",
    ]
    
    # Detail view: fields that can't be edited
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Author)
class AuthorAdmin(ModelAdmin):
    """Manage authors."""
    
    list_display = ["name", "email", "post_count", "created_at"]
    search_fields = ["name", "email"]
    
    def post_count(self, obj):
        """Custom column: count how many posts this author has."""
        return len(obj.posts)


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    """Manage categories."""
    
    list_display = ["name", "slug", "parent"]
    
    # Auto-fill slug when typing name
    prepopulated_fields = {"slug": ("name",)}


# Simple registration with all defaults
admin.register(Tag)
```

```python
# main.py
from aksara import Aksara
from aksara.contrib.auth.middleware import AuthenticationMiddleware
from myapp.admin import admin

app = Aksara()

# Required: authentication so admin knows who's logged in
app.add_middleware(AuthenticationMiddleware)

# Mount admin at /admin/
app.mount("/admin", admin)
```

---

## Related Documentation

- [Models](../orm/models.md) — Define your data structure
- [Authentication](../api/authentication.md) — User login system
- [Permissions](admin-permissions.md) — Control access to admin
