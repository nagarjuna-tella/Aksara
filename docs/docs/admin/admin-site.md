# AdminSite

Configure the admin interface.

---

## Overview

`AdminSite` is the main entry point for the admin interface:

```python
from aksara.contrib.admin import AdminSite

admin = AdminSite(
    title="My Admin",
    site_header="My Application",
)
```

---

## Configuration Options

### Basic Options

```python
admin = AdminSite(
    # Display settings
    title="Admin",              # Browser tab title
    site_header="Site Admin",   # Header text
    index_title="Dashboard",    # Index page title
    
    # URL configuration
    url_prefix="/admin",        # Base URL path
    
    # Theme
    theme="default",            # "default", "dark", or custom
)
```

### All Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `title` | `str` | `"Admin"` | Browser title |
| `site_header` | `str` | `"Site Admin"` | Page header |
| `index_title` | `str` | `"Dashboard"` | Index page heading |
| `url_prefix` | `str` | `"/admin"` | URL prefix |
| `login_url` | `str` | `"/admin/login/"` | Login page URL |
| `logout_url` | `str` | `"/admin/logout/"` | Logout URL |
| `theme` | `str` | `"default"` | UI theme |
| `permission_classes` | `list` | `[IsAdminUser]` | Access permissions |

---

## Registering Models

### Decorator Style

```python
from aksara.contrib.admin import ModelAdmin

@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "author"]
```

### Method Style

```python
from aksara.contrib.admin import ModelAdmin

class PostAdmin(ModelAdmin):
    list_display = ["title", "author"]

admin.register(Post, PostAdmin)
```

### Simple Registration

For default admin (no customization):

```python
admin.register(Post)
admin.register(Author)
admin.register(Category)
```

### Multiple Models

```python
@admin.register(Post, Draft)
class ContentAdmin(ModelAdmin):
    """Same admin for multiple similar models."""
    list_display = ["title", "created_at"]
```

---

## Mounting Admin

### On Aksara App

```python
from aksara import Aksara
from myapp.admin import admin

app = Aksara()
app.mount("/admin", admin)
```

### With Custom Path

```python
app.mount("/manage", admin)
# Admin at: http://localhost:8000/manage/
```

### Multiple Admin Sites

```python
# Public admin
public_admin = AdminSite(title="Content Admin")
public_admin.register(Post, PostAdmin)

# Private admin (more models)
private_admin = AdminSite(title="Full Admin")
private_admin.register(Post, PostAdmin)
private_admin.register(User, UserAdmin)
private_admin.register(Settings, SettingsAdmin)

# Mount both
app.mount("/admin", public_admin)
app.mount("/superadmin", private_admin)
```

---

## Customizing the Index

### Custom Index Template

```python
admin = AdminSite(
    index_template="admin/custom_index.html",
)
```

### Dashboard Widgets

```python
admin = AdminSite()

@admin.index_view
async def custom_index(request):
    """Custom dashboard with statistics."""
    return {
        "recent_posts": await Post.objects.order_by("-created_at")[:5],
        "total_users": await User.objects.count(),
        "pending_reviews": await Post.objects.filter(status="pending").count(),
    }
```

---

## Authentication

### Default Authentication

By default, admin requires `is_staff=True`:

```python
# User must have is_staff=True to access admin
user.is_staff = True
await user.save()
```

### Custom Permission

```python
from aksara.permissions import BasePermission

class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.is_superuser
        )

admin = AdminSite(
    permission_classes=[IsSuperAdmin],
)
```

### Custom Login View

```python
admin = AdminSite(
    login_url="/auth/login",  # Use app's login
    logout_url="/auth/logout",
)
```

---

## Theming

### Built-in Themes

```python
# Default light theme
admin = AdminSite(theme="default")

# Dark theme
admin = AdminSite(theme="dark")
```

### Custom Theme

```python
admin = AdminSite(
    theme="custom",
    theme_config={
        "primary_color": "#3498db",
        "secondary_color": "#2ecc71",
        "background": "#ffffff",
        "sidebar_bg": "#2c3e50",
        "font_family": "Inter, sans-serif",
    },
)
```

### Custom CSS

```python
admin = AdminSite(
    extra_css=[
        "/static/admin/custom.css",
    ],
)
```

---

## Admin Actions

### Global Actions

```python
admin = AdminSite()

@admin.action(name="Export All Data")
async def export_all(request):
    """Export all data as JSON."""
    data = {
        "posts": [p.to_dict() for p in await Post.objects.all()],
        "authors": [a.to_dict() for a in await Author.objects.all()],
    }
    return JSONResponse(data)
```

### Dashboard Links

```python
admin = AdminSite()

admin.add_link(
    name="View Site",
    url="/",
    icon="external-link",
)

admin.add_link(
    name="API Docs",
    url="/docs",
    icon="code",
)
```

---

## Hooks

### Before Request

```python
admin = AdminSite()

@admin.before_request
async def log_admin_access(request):
    """Log all admin accesses."""
    logger.info(f"Admin access: {request.user.email} -> {request.url}")
```

### After Request

```python
@admin.after_request
async def audit_changes(request, response):
    """Audit admin changes."""
    if request.method in ["POST", "PUT", "DELETE"]:
        await AuditLog.objects.create(
            user=request.user,
            action=request.method,
            path=request.url.path,
        )
```

---

## Complete Example

```python
# admin.py
from aksara.contrib.admin import AdminSite, ModelAdmin
from aksara.permissions import BasePermission
from myapp.models import Post, Author, Category, Tag, User, Settings


class IsStaffOrSuperuser(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            (request.user.is_staff or request.user.is_superuser)
        )


# Create admin site
admin = AdminSite(
    title="Blog Admin",
    site_header="Blog Administration",
    index_title="Dashboard",
    theme="default",
    permission_classes=[IsStaffOrSuperuser],
)


# Register models
@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "is_published", "created_at"]
    list_filter = ["is_published", "category"]
    search_fields = ["title", "content"]


@admin.register(Author)
class AuthorAdmin(ModelAdmin):
    list_display = ["name", "email"]
    search_fields = ["name", "email"]


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ["name", "slug"]


admin.register(Tag)  # Simple registration


# Custom dashboard
@admin.index_view
async def dashboard(request):
    return {
        "stats": {
            "total_posts": await Post.objects.count(),
            "published_posts": await Post.objects.filter(is_published=True).count(),
            "total_authors": await Author.objects.count(),
        },
        "recent_posts": await Post.objects.order_by("-created_at")[:5],
    }


# Audit logging
@admin.after_request
async def audit_log(request, response):
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        from myapp.models import AuditLog
        await AuditLog.objects.create(
            user_id=str(request.user.id),
            action=f"{request.method} {request.url.path}",
        )


# Add useful links
admin.add_link("View Site", "/", icon="home")
admin.add_link("API Docs", "/docs", icon="book")
```

---

## Related Documentation

- [ModelAdmin](model-admin.md) — Model customization
- [Admin Permissions](admin-permissions.md) — Access control
- [Authentication](../api/authentication.md) — User auth
