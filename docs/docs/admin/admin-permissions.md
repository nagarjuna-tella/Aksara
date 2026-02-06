# Admin Permissions

Control who can see, add, edit, and delete data in the admin interface.

---

## What are Permissions?

**Permissions** determine what users can do. Without permissions, anyone could access your admin and modify data—which would be a security disaster.

Aksara admin permissions work at four levels:

| Level | What It Controls | Example |
|-------|------------------|---------|
| **Site** | Who can access the admin at all | "Only staff members can open `/admin/`" |
| **Model** | Who can see a model in the admin | "Only superusers can see the Settings model" |
| **Object** | Who can edit specific records | "Authors can only edit their own posts" |
| **Action** | Who can perform bulk operations | "Only admins can bulk-delete posts" |

---

## Site-Level Permissions

Site-level permissions control who can access the admin interface at all.

### Default: Staff Only

By default, users need `is_staff=True` to access admin:

```python
# Give a user admin access
user = await User.objects.get(email="alice@example.com")
user.is_staff = True
await user.save()
# Now Alice can access /admin/
```

### Superuser Only

Restrict to superusers (users with full system access):

```python
from aksara.permissions import BasePermission

class IsSuperuser(BasePermission):
    """Only superusers can access."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.is_superuser
        )

admin = AdminSite(
    permission_classes=[IsSuperuser],
)
```

### Custom Role Check

Check for specific roles or attributes:

```python
class IsEditorOrHigher(BasePermission):
    """Editors, admins, and superusers can access."""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Check user's role
        return request.user.role in ["editor", "admin", "superuser"]

admin = AdminSite(
    permission_classes=[IsEditorOrHigher],
)
```

### Multiple Requirements (AND)

When you pass multiple permission classes, ALL must pass:

```python
admin = AdminSite(
    permission_classes=[
        IsAuthenticated,  # Must be logged in
        IsStaff,          # AND must be staff
        HasVerifiedEmail, # AND must have verified email
    ],
)
```

---

## Model-Level Permissions

Model-level permissions control which models appear in the admin and what users can do with them.

### has_module_permission

**What it does**: Controls whether the model appears in the admin sidebar/index.

**When to use**: To completely hide sensitive models from certain users.

```python
class SettingsAdmin(ModelAdmin):
    def has_module_permission(self, request):
        """Only superusers can see Settings in the admin."""
        return request.user.is_superuser
```

**Result**: Non-superusers won't see "Settings" in the admin menu at all.

### CRUD Permissions

These four methods control Create, Read, Update, Delete access:

```python
class PostAdmin(ModelAdmin):
    
    def has_view_permission(self, request, obj=None):
        """Can user VIEW posts in the admin?"""
        return True  # Everyone can view
    
    def has_add_permission(self, request):
        """Can user CREATE new posts?"""
        return request.user.is_staff  # Staff only
    
    def has_change_permission(self, request, obj=None):
        """Can user EDIT posts?"""
        return request.user.is_staff  # Staff only
    
    def has_delete_permission(self, request, obj=None):
        """Can user DELETE posts?"""
        return request.user.is_superuser  # Superusers only
```

**Note**: The `obj` parameter is `None` for list views (checking general permission) and contains the specific object for detail views (checking permission on that specific record).

---

## Object-Level Permissions

Object-level permissions let you control access to specific records, not just the model as a whole.

### "Edit Your Own" Pattern

The most common pattern: users can only edit records they created.

```python
class PostAdmin(ModelAdmin):
    
    def has_change_permission(self, request, obj=None):
        """Users can only edit their own posts."""
        
        # List view: check general permission
        if obj is None:
            return request.user.is_staff
        
        # Detail view: check specific object
        # Superusers can edit anything
        if request.user.is_superuser:
            return True
        
        # Others can only edit their own posts
        return str(obj.author_id) == str(request.user.id)
    
    def has_delete_permission(self, request, obj=None):
        """Users can only delete their own posts."""
        
        if obj is None:
            return request.user.is_staff
        
        if request.user.is_superuser:
            return True
        
        return str(obj.author_id) == str(request.user.id)
```

**How it works**:
- Alice creates a post → Alice and superusers can edit/delete it
- Bob creates a post → Bob and superusers can edit/delete it
- Alice cannot edit Bob's post (unless she's a superuser)

### Team-Based Permissions

For collaborative apps where teams share access:

```python
class ProjectAdmin(ModelAdmin):
    
    async def has_change_permission(self, request, obj=None):
        """Team members can edit their team's projects."""
        
        if obj is None:
            return request.user.is_staff
        
        if request.user.is_superuser:
            return True
        
        # Check if user is a member of the project's team
        is_member = await obj.team.members.filter(
            id=str(request.user.id)
        ).exists()
        
        return is_member
```

### Manager/Subordinate Permissions

For hierarchical organizations:

```python
class EmployeeAdmin(ModelAdmin):
    
    async def has_change_permission(self, request, obj=None):
        """Managers can edit their direct reports."""
        
        if obj is None:
            return request.user.is_staff
        
        if request.user.is_superuser:
            return True
        
        # Check if this employee reports to the current user
        return str(obj.manager_id) == str(request.user.id)
```

---

## Action Permissions

Control who can perform bulk actions (operations on multiple selected records).

### Restrict by CRUD Permission

Link actions to existing permission methods:

```python
class PostAdmin(ModelAdmin):
    actions = ["publish", "feature", "archive"]
    
    @admin.action(description="Publish selected posts")
    async def publish(self, request, queryset):
        await queryset.update(is_published=True)
    # Requires "change" permission (has_change_permission)
    publish.allowed_permissions = ["change"]
    
    @admin.action(description="Feature selected posts")
    async def feature(self, request, queryset):
        await queryset.update(is_featured=True)
    # Also requires "change" permission
    feature.allowed_permissions = ["change"]
    
    @admin.action(description="Archive selected posts")
    async def archive(self, request, queryset):
        await queryset.update(is_archived=True)
    # Requires "delete" permission (more restrictive)
    archive.allowed_permissions = ["delete"]
```

### Custom Action Permissions

Create custom permission methods for specific actions:

```python
class PostAdmin(ModelAdmin):
    actions = ["export_csv"]
    
    @admin.action(description="Export to CSV")
    async def export_csv(self, request, queryset):
        """Export selected posts to a CSV file."""
        # ... export logic ...
    
    def has_export_csv_permission(self, request):
        """Custom permission: only users with export role."""
        return (
            request.user.is_superuser or
            "exporter" in request.user.roles
        )
    
    # Link action to custom permission
    export_csv.allowed_permissions = ["export_csv"]
```

---

## Field-Level Permissions

Control which fields users can see or edit.

### Read-Only Fields for Some Users

```python
class PostAdmin(ModelAdmin):
    
    def get_readonly_fields(self, request, obj=None):
        """Some fields are read-only for non-superusers."""
        
        # Start with base readonly fields
        readonly = list(self.readonly_fields)
        
        if not request.user.is_superuser:
            # Regular staff can't edit these sensitive fields
            readonly.extend([
                "is_featured",   # Only admins can feature posts
                "view_count",    # System-managed
                "author",        # Can't reassign posts
            ])
        
        return readonly
```

### Hide Fields Entirely

```python
class UserAdmin(ModelAdmin):
    
    def get_fields(self, request, obj=None):
        """Hide sensitive fields from non-superusers."""
        
        # Default fields
        fields = ["email", "name", "role", "is_active"]
        
        if request.user.is_superuser:
            # Superusers can see everything
            fields.extend(["password_hash", "api_key", "internal_notes"])
        
        return fields
```

### Different Fields for Add vs. Edit

```python
class PostAdmin(ModelAdmin):
    
    def get_fields(self, request, obj=None):
        """Different fields when creating vs. editing."""
        
        if obj is None:
            # Creating new post: minimal fields
            return ["title", "content", "category"]
        else:
            # Editing existing post: all fields
            return [
                "title", "slug", "content", "category",
                "is_published", "published_at", "is_featured",
            ]
```

---

## Filtering What Users Can See

### QuerySet Filtering

Users only see records they have access to:

```python
class PostAdmin(ModelAdmin):
    
    def get_queryset(self, request):
        """Filter which posts appear in the list."""
        
        qs = super().get_queryset(request)
        
        if request.user.is_superuser:
            # Superusers see everything
            return qs
        
        # Others only see their own posts
        return qs.filter(author_id=str(request.user.id))
```

**Result**: When Alice views the post list, she only sees her posts. Bob only sees his. Superusers see all posts.

### Combining with Permissions

```python
class PostAdmin(ModelAdmin):
    
    def get_queryset(self, request):
        """Authors see own posts; editors see all."""
        
        qs = super().get_queryset(request)
        
        if request.user.is_superuser:
            return qs
        
        if request.user.role == "editor":
            # Editors see all posts but can only edit assigned ones
            return qs
        
        # Regular authors only see their own
        return qs.filter(author_id=str(request.user.id))
    
    def has_change_permission(self, request, obj=None):
        """Editors can only edit posts assigned to them."""
        
        if obj is None:
            return request.user.is_staff
        
        if request.user.is_superuser:
            return True
        
        if request.user.role == "editor":
            # Editors can edit posts assigned to them
            return str(obj.assigned_editor_id) == str(request.user.id)
        
        # Authors can edit their own posts
        return str(obj.author_id) == str(request.user.id)
```

---

## Permission Quick Reference

| Method | Controls | When `obj` is None |
|--------|----------|-------------------|
| `has_module_permission(request)` | Model visibility in admin | N/A |
| `has_view_permission(request, obj)` | Can view records | List view permission |
| `has_add_permission(request)` | Can create records | N/A (no object yet) |
| `has_change_permission(request, obj)` | Can edit records | List view permission |
| `has_delete_permission(request, obj)` | Can delete records | List view permission |

---

## Complete Example

```python
from aksara.contrib.admin import ModelAdmin, AdminSite
from aksara.permissions import BasePermission


class IsStaffOrReadOnly(BasePermission):
    """Staff can do anything; others can only view."""
    
    def has_permission(self, request, view):
        if request.user.is_authenticated:
            return True
        return False


admin = AdminSite(
    permission_classes=[IsStaffOrReadOnly],
)


@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "is_published"]
    actions = ["publish", "feature"]
    
    # ─── Model Permissions ─────────────────────────────
    
    def has_module_permission(self, request):
        """Everyone can see Posts in the menu."""
        return True
    
    def has_view_permission(self, request, obj=None):
        """Everyone can view posts."""
        return True
    
    def has_add_permission(self, request):
        """Only staff can create posts."""
        return request.user.is_staff
    
    def has_change_permission(self, request, obj=None):
        """Staff can edit; authors can edit their own."""
        if obj is None:
            return request.user.is_staff
        if request.user.is_superuser:
            return True
        return str(obj.author_id) == str(request.user.id)
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers and post authors can delete."""
        if obj is None:
            return request.user.is_staff
        if request.user.is_superuser:
            return True
        return str(obj.author_id) == str(request.user.id)
    
    # ─── QuerySet Filtering ────────────────────────────
    
    def get_queryset(self, request):
        """Superusers see all; others see own posts."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(author_id=str(request.user.id))
    
    # ─── Field Permissions ─────────────────────────────
    
    def get_readonly_fields(self, request, obj=None):
        """Regular users can't modify featured status."""
        readonly = ["created_at", "updated_at"]
        if not request.user.is_superuser:
            readonly.append("is_featured")
        return readonly
    
    # ─── Action Permissions ────────────────────────────
    
    @admin.action(description="Publish selected")
    async def publish(self, request, queryset):
        await queryset.update(is_published=True)
    publish.allowed_permissions = ["change"]
    
    @admin.action(description="Feature selected")
    async def feature(self, request, queryset):
        await queryset.update(is_featured=True)
    # Custom permission: only superusers can feature
    feature.allowed_permissions = ["feature"]
    
    def has_feature_permission(self, request):
        """Only superusers can feature posts."""
        return request.user.is_superuser
```

---

## Related Documentation

- [AdminSite](admin-site.md) — Configure the admin interface
- [ModelAdmin](model-admin.md) — Customize model display
- [Authentication](../getting-started/authentication.md) — User login system
