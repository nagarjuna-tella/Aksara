# Admin Permissions

Control who can access and modify data in the admin.

---

## Overview

Admin permissions work at multiple levels:

1. **Site-level** — Who can access the admin at all
2. **Model-level** — Who can see a model in admin
3. **Object-level** — Who can edit specific objects
4. **Action-level** — Who can perform specific actions

---

## Site-Level Permissions

### Default: Staff Only

By default, only users with `is_staff=True` can access admin:

```python
# Make user a staff member
user.is_staff = True
await user.save()
```

### Custom Permission Class

```python
from vidyut.permissions import BasePermission

class IsSuperuser(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.is_superuser
        )

admin = AdminSite(
    permission_classes=[IsSuperuser],
)
```

### Multiple Permissions (AND)

```python
admin = AdminSite(
    permission_classes=[IsAuthenticated, IsStaff, IsNotBanned],
)
```

---

## Model-Level Permissions

### has_module_permission

Control if model appears in admin index:

```python
class SensitiveDataAdmin(ModelAdmin):
    def has_module_permission(self, request):
        """Only show to superusers."""
        return request.user.is_superuser
```

### Standard CRUD Permissions

```python
class PostAdmin(ModelAdmin):
    def has_view_permission(self, request, obj=None):
        """Can user view this model/object?"""
        return True  # Everyone can view
    
    def has_add_permission(self, request):
        """Can user create new objects?"""
        return request.user.is_staff
    
    def has_change_permission(self, request, obj=None):
        """Can user edit objects?"""
        return request.user.is_staff
    
    def has_delete_permission(self, request, obj=None):
        """Can user delete objects?"""
        return request.user.is_superuser
```

---

## Object-Level Permissions

### Owner-Only Editing

```python
class PostAdmin(ModelAdmin):
    def has_change_permission(self, request, obj=None):
        # obj is None for list view
        if obj is None:
            return request.user.is_staff
        
        # Superusers can edit anything
        if request.user.is_superuser:
            return True
        
        # Others can only edit their own posts
        return str(obj.author_id) == str(request.user.id)
    
    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return request.user.is_staff
        
        # Only superusers and owners can delete
        if request.user.is_superuser:
            return True
        return str(obj.author_id) == str(request.user.id)
```

### Team-Based Permissions

```python
class ProjectAdmin(ModelAdmin):
    async def has_change_permission(self, request, obj=None):
        if obj is None:
            return request.user.is_staff
        
        # Check team membership
        is_member = await obj.team.members.filter(
            id=str(request.user.id)
        ).exists()
        
        return is_member or request.user.is_superuser
```

---

## Action Permissions

### Restrict Actions

```python
class PostAdmin(ModelAdmin):
    actions = ["publish", "feature", "delete_permanently"]
    
    @admin.action(description="Publish selected")
    async def publish(self, request, queryset):
        ...
    publish.allowed_permissions = ["change"]  # Requires change permission
    
    @admin.action(description="Feature selected")
    async def feature(self, request, queryset):
        ...
    feature.allowed_permissions = ["change"]
    
    @admin.action(description="Delete permanently")
    async def delete_permanently(self, request, queryset):
        ...
    delete_permanently.allowed_permissions = ["delete"]
```

### Custom Action Permissions

```python
class PostAdmin(ModelAdmin):
    @admin.action(description="Export to CSV")
    async def export_csv(self, request, queryset):
        ...
    
    def has_export_csv_permission(self, request):
        """Custom permission method for action."""
        return request.user.has_perm("posts.export")
    
    export_csv.allowed_permissions = ["export_csv"]
```

---

## Field-Level Permissions

### Read-Only for Non-Superusers

```python
class PostAdmin(ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        
        if not request.user.is_superuser:
            # Regular staff can't edit these
            readonly.extend(["is_featured", "view_count"])
        
        return readonly
```

### Hide Fields

```python
class UserAdmin(ModelAdmin):
    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        
        if not request.user.is_superuser:
            # Hide sensitive fields
            fields = [f for f in fields if f not in ["password", "api_key"]]
        
        return fields
```

### Conditional Fieldsets

```python
class PostAdmin(ModelAdmin):
    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            (None, {"fields": ["title", "content"]}),
            ("Metadata", {"fields": ["author", "category"]}),
        ]
        
        # Only superusers see advanced options
        if request.user.is_superuser:
            fieldsets.append((
                "Advanced",
                {"fields": ["seo_title", "seo_description", "canonical_url"]}
            ))
        
        return fieldsets
```

---

## QuerySet Filtering

### Filter by User

```python
class PostAdmin(ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Superusers see everything
        if request.user.is_superuser:
            return qs
        
        # Staff see only their posts
        return qs.filter(author_id=str(request.user.id))
```

### Filter by Role/Team

```python
class ProjectAdmin(ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        if request.user.is_superuser:
            return qs
        
        # Filter by user's teams
        user_team_ids = [str(t.id) for t in request.user.teams]
        return qs.filter(team_id__in=user_team_ids)
```

---

## Built-in Permission Classes

### IsAuthenticated

```python
from vidyut.permissions import IsAuthenticated

admin = AdminSite(permission_classes=[IsAuthenticated])
```

### IsAdminUser

```python
from vidyut.permissions import IsAdminUser

# Requires is_staff=True
admin = AdminSite(permission_classes=[IsAdminUser])
```

### Custom Classes

```python
from vidyut.permissions import BasePermission

class IsEditor(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == "editor"
        )

class IsNotBanned(BasePermission):
    def has_permission(self, request, view):
        return not getattr(request.user, "is_banned", False)

class HasVerifiedEmail(BasePermission):
    def has_permission(self, request, view):
        return getattr(request.user, "email_verified", False)
```

---

## Permission Messages

### Custom Denial Messages

```python
class PostAdmin(ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_published:
            self.message_user(
                request,
                "Cannot delete published posts. Unpublish first.",
                level="error",
            )
            return False
        return request.user.is_staff
```

---

## Complete Example

```python
from vidyut.contrib.admin import AdminSite, ModelAdmin
from vidyut.permissions import BasePermission
from myapp.models import Post, Category, User


class IsStaffOrEditor(BasePermission):
    """Allow staff or users with editor role."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return (
            request.user.is_staff or
            request.user.role == "editor"
        )


admin = AdminSite(
    title="Blog Admin",
    permission_classes=[IsStaffOrEditor],
)


@admin.register(Post)
class PostAdmin(ModelAdmin):
    """Post admin with granular permissions."""
    
    list_display = ["title", "author", "is_published", "created_at"]
    
    def has_module_permission(self, request):
        """Everyone who can access admin can see posts."""
        return True
    
    def has_view_permission(self, request, obj=None):
        """Everyone can view."""
        return True
    
    def has_add_permission(self, request):
        """Staff and editors can create."""
        return True
    
    def has_change_permission(self, request, obj=None):
        """Can edit own posts or all if superuser."""
        if obj is None:
            return True
        if request.user.is_superuser:
            return True
        return str(obj.author_id) == str(request.user.id)
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete, and not published posts."""
        if not request.user.is_superuser:
            return False
        if obj and obj.is_published:
            return False
        return True
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Non-superusers only see their posts
        return qs.filter(author_id=str(request.user.id))
    
    def get_readonly_fields(self, request, obj=None):
        readonly = ["created_at", "updated_at"]
        if not request.user.is_superuser:
            readonly.append("is_featured")
        return readonly
    
    actions = ["publish_selected", "feature_selected"]
    
    @admin.action(description="Publish selected")
    async def publish_selected(self, request, queryset):
        count = await queryset.update(is_published=True)
        self.message_user(request, f"Published {count} posts")
    publish_selected.allowed_permissions = ["change"]
    
    @admin.action(description="Feature selected")
    async def feature_selected(self, request, queryset):
        count = await queryset.update(is_featured=True)
        self.message_user(request, f"Featured {count} posts")
    
    def has_feature_selected_permission(self, request):
        """Only superusers can feature posts."""
        return request.user.is_superuser
    feature_selected.allowed_permissions = ["feature_selected"]


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    """Categories: view all, edit only for superusers."""
    
    list_display = ["name", "slug"]
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(User)
class UserAdmin(ModelAdmin):
    """User admin: superusers only."""
    
    list_display = ["email", "is_staff", "is_active"]
    
    def has_module_permission(self, request):
        return request.user.is_superuser
    
    def get_fields(self, request, obj=None):
        # Never show password hash
        fields = super().get_fields(request, obj)
        return [f for f in fields if f != "password"]
```

---

## Related Documentation

- [AdminSite](admin-site.md) — Admin configuration
- [ModelAdmin](model-admin.md) — Model customization
- [API Permissions](../api/permissions.md) — API access control
