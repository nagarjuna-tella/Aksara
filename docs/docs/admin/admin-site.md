# AdminSite

The main container for your admin interface—where you configure how the admin looks and which models it manages.

---

## What is AdminSite?

An **AdminSite** is like the headquarters of your admin interface. It:

- Holds all the models you want to manage
- Controls the appearance (title, header, theme)
- Manages authentication (who can access)
- Gets mounted to your app at a URL like `/admin/`

```python
from aksara.contrib.admin import AdminSite

admin = AdminSite(
    title="My Admin",            # Browser tab text
    site_header="My Application", # Header shown on every page
)
```

---

## Configuration Options

### Basic Setup

```python
admin = AdminSite(
    # What users see
    title="Admin",              # Browser tab: "Admin"
    site_header="Site Admin",   # Top of page: "Site Admin"
    index_title="Dashboard",    # Homepage heading: "Dashboard"
    
    # Where admin lives
    url_prefix="/admin",        # URL: yoursite.com/admin/
    
    # Look and feel
    theme="default",            # "default" or "dark"
)
```

### All Configuration Options

| Option | What It Does | Default | Example |
|--------|--------------|---------|---------|
| `title` | Browser tab text | `"Admin"` | `"Blog Admin"` |
| `site_header` | Header at top of every page | `"Site Admin"` | `"My Blog"` |
| `index_title` | Heading on dashboard page | `"Dashboard"` | `"Welcome"` |
| `url_prefix` | Base URL path | `"/admin"` | `"/manage"` |
| `login_url` | Where to go to log in | `"/admin/login/"` | `"/auth/login"` |
| `logout_url` | Where to go after logout | `"/admin/logout/"` | `"/auth/logout"` |
| `theme` | Visual theme | `"default"` | `"dark"` |
| `permission_classes` | Who can access | `[IsAdminUser]` | `[IsSuperuser]` |

---

## Registering Models

**Registering** tells the admin: "I want to manage this model." There are several ways to do it.

### Method 1: Decorator (Recommended)

The `@admin.register()` decorator is clean and keeps the model and its admin config together:

```python
from aksara.contrib.admin import ModelAdmin

@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "author"]
```

### Method 2: Register Method

Call `admin.register()` directly—useful when the admin class is defined elsewhere:

```python
from aksara.contrib.admin import ModelAdmin

class PostAdmin(ModelAdmin):
    list_display = ["title", "author"]

# Register separately
admin.register(Post, PostAdmin)
```

### Method 3: Simple Registration

For basic models that don't need customization, just pass the model:

```python
admin.register(Post)      # Uses default settings
admin.register(Author)
admin.register(Category)
```

### Method 4: Multiple Models, Same Config

When several models should share the same admin configuration:

```python
@admin.register(Post, Draft, Archive)
class ContentAdmin(ModelAdmin):
    """Same admin for all content-type models."""
    list_display = ["title", "created_at"]
    search_fields = ["title"]
```

---

## Mounting the Admin

**Mounting** connects your admin to your application so it's accessible via a URL.

### Basic Mount

```python
from aksara import Aksara
from myapp.admin import admin

app = Aksara()
app.mount("/admin", admin)  # Admin at: http://localhost:8000/admin/
```

### Custom URL Path

```python
app.mount("/manage", admin)    # Admin at: http://localhost:8000/manage/
app.mount("/backend", admin)   # Admin at: http://localhost:8000/backend/
```

### Multiple Admin Sites

You can have separate admin interfaces for different purposes:

```python
# Public admin: for content editors
public_admin = AdminSite(
    title="Content Admin",
    site_header="Content Management",
)
public_admin.register(Post)
public_admin.register(Category)

# Private admin: for superusers with full access
private_admin = AdminSite(
    title="Full Admin",
    site_header="System Administration",
)
private_admin.register(Post)
private_admin.register(User)
private_admin.register(Settings)
private_admin.register(AuditLog)

# Mount both at different URLs
app.mount("/admin", public_admin)        # /admin/ for editors
app.mount("/superadmin", private_admin)  # /superadmin/ for admins
```

---

## Customizing the Dashboard

The **dashboard** (index page) is the first thing users see when they open the admin.

### Custom Dashboard with Statistics

Override the index view to show custom data:

```python
admin = AdminSite()

@admin.index_view
async def custom_dashboard(request):
    """Show statistics on the dashboard."""
    return {
        # These become available in the template
        "recent_posts": await Post.objects.order_by("-created_at")[:5],
        "total_users": await User.objects.count(),
        "pending_reviews": await Post.objects.filter(status="pending").count(),
        "today_signups": await User.objects.filter(created_at__date=today).count(),
    }
```

### Custom Dashboard Template

Use your own HTML template for complete control:

```python
admin = AdminSite(
    index_template="admin/my_dashboard.html",
)
```

Then create `templates/admin/my_dashboard.html`:

```html
{% extends "admin/base.html" %}

{% block content %}
<div class="dashboard">
    <h1>Welcome, {{ user.name }}!</h1>
    
    <div class="stats-grid">
        <div class="stat-card">
            <h3>{{ total_users }}</h3>
            <p>Total Users</p>
        </div>
        <div class="stat-card">
            <h3>{{ pending_reviews }}</h3>
            <p>Pending Reviews</p>
        </div>
    </div>
    
    <h2>Recent Posts</h2>
    <ul>
    {% for post in recent_posts %}
        <li>{{ post.title }} by {{ post.author.name }}</li>
    {% endfor %}
    </ul>
</div>
{% endblock %}
```

---

## Authentication

The admin must know who's logged in and whether they're allowed access.

### Default: Staff Users Only

By default, only users with `is_staff=True` can access the admin:

```python
# Give a user admin access
user.is_staff = True
await user.save()
```

### Require Superuser

To restrict to superusers only:

```python
from aksara.permissions import BasePermission

class IsSuperuser(BasePermission):
    """Only allow superusers."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.is_superuser
        )

admin = AdminSite(
    permission_classes=[IsSuperuser],
)
```

### Use Your App's Login

If your app already has login/logout pages, use those instead of the admin's:

```python
admin = AdminSite(
    login_url="/auth/login",    # Redirect here to log in
    logout_url="/auth/logout",  # Redirect here to log out
)
```

### Multiple Permission Requirements

All permissions must pass (AND logic):

```python
admin = AdminSite(
    permission_classes=[
        IsAuthenticated,  # Must be logged in
        IsStaff,          # AND must be staff
        IsNotBanned,      # AND must not be banned
    ],
)
```

---

## Themes

### Built-in Themes

```python
# Light theme (default)
admin = AdminSite(theme="default")

# Dark theme
admin = AdminSite(theme="dark")
```

### Custom CSS

Add your own styles:

```python
admin = AdminSite(
    extra_css=["/static/admin/custom.css"],
)
```

---

## Unregistering Models

Remove a model from the admin (useful for overriding third-party admin configs):

```python
# Remove if previously registered
admin.unregister(Post)

# Then re-register with your own config
@admin.register(Post)
class MyPostAdmin(ModelAdmin):
    list_display = ["title", "custom_field"]
```

---

## Getting Registered Models

Access the list of registered models:

```python
# Get all registered models
for model, model_admin in admin.registry.items():
    print(f"{model.__name__}: {model_admin.__class__.__name__}")

# Check if a model is registered
if Post in admin.registry:
    print("Post is registered")

# Get the ModelAdmin for a model
post_admin = admin.registry.get(Post)
```

---

## Complete Example

```python
# admin.py
from aksara.contrib.admin import AdminSite, ModelAdmin
from aksara.permissions import BasePermission
from myapp.models import Post, Author, Category, Settings


# Custom permission
class IsEditorOrAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.role in ["editor", "admin", "superuser"]


# Create admin site
admin = AdminSite(
    title="Blog Admin",
    site_header="Blog Content Management",
    index_title="Dashboard",
    permission_classes=[IsEditorOrAdmin],
)


# Custom dashboard
@admin.index_view
async def dashboard(request):
    return {
        "post_count": await Post.objects.count(),
        "draft_count": await Post.objects.filter(is_published=False).count(),
        "author_count": await Author.objects.count(),
    }


# Register models
@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "is_published", "created_at"]
    list_filter = ["is_published", "category"]
    search_fields = ["title", "content"]


@admin.register(Author)
class AuthorAdmin(ModelAdmin):
    list_display = ["name", "email", "post_count"]
    search_fields = ["name", "email"]


# Simple registration
admin.register(Category)
```

```python
# main.py
from aksara import Aksara
from aksara.contrib.auth.middleware import AuthenticationMiddleware
from myapp.admin import admin

app = Aksara()
app.add_middleware(AuthenticationMiddleware)
app.mount("/admin", admin)
```

---

## Related Documentation

- [ModelAdmin](model-admin.md) — Customize how models appear
- [Permissions](admin-permissions.md) — Fine-grained access control
- [Models](../orm/models.md) — Define your data structure
