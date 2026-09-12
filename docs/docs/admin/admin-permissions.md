# Admin Permissions

Control who can see, add, edit, and delete data in the admin interface.

---

## Levels of Permission

| Level | Controls | Where |
|-------|----------|-------|
| **Site** | Access to the admin at all | `AdminSite(permission_classes=...)` |
| **Module** | Whether a model appears in the dashboard/sidebar | `ModelAdmin.has_module_permission` |
| **Object** | View/add/change/delete records | `ModelAdmin.has_*_permission` |
| **Field** | Which fields are visible / editable | `get_fields`, `get_readonly_fields` |
| **Action** | Who can run a bulk action | `@action(permissions=[...])` |

The admin reads the current user from `request.state.user` (populated by the
admin session middleware from the `session_token` cookie).

---

## Site-Level Permissions

By default the admin requires an authenticated **staff** user (`is_staff=True`).
To customize, pass `permission_classes` — standard `aksara.permissions`
classes — to the site. When set, they replace the default staff gate for site
access.

```python
from aksara.contrib.admin import AdminSite
from aksara.permissions import BasePermission

class IsSuperuser(BasePermission):
    def has_permission(self, request, view=None):
        user = self.get_user(request)
        return bool(user and getattr(user, "is_superuser", False))

admin = AdminSite(permission_classes=[IsSuperuser])
```

Combine requirements with the built-in `IsAuthenticated`, `IsAdminUser`, etc., or
your own `BasePermission` subclasses. The built-in admin request handling honors
these checks during both login and subsequent admin page access, and supports
sync or async `has_permission()` methods.

---

## Module-Level Permissions

`has_module_permission(self, request)` controls whether a model shows up in the
dashboard and app index for the current user. It defaults to the view permission.

```python
class SettingsAdmin(ModelAdmin):
    def has_module_permission(self, request):
        return request.state.user.is_superuser
```

Non-superusers won't see the model listed (the underlying detail routes are also
guarded by the view/change permissions below).

---

## Object-Level (CRUD) Permissions

Override these to control Create, Read, Update, Delete. They may be **sync or
async**. `obj` is `None` for list-level checks and the specific record for
detail-level checks.

```python
class PostAdmin(ModelAdmin):
    def has_view_permission(self, request, obj=None):
        return request.state.user.is_staff

    def has_add_permission(self, request):
        return request.state.user.is_staff

    def has_change_permission(self, request, obj=None):
        user = request.state.user
        if obj is None or user.is_superuser:
            return user.is_staff
        return str(obj.author_id) == str(user.id)   # edit your own only

    def has_delete_permission(self, request, obj=None):
        return request.state.user.is_superuser
```

### Async permissions

When a check needs a database lookup, define it as `async def`:

```python title="app/admin_permissions.py"
from aksara.contrib.admin import ModelAdmin


class PostAdmin(ModelAdmin):
    async def has_change_permission(self, request, obj=None):
        user = request.state.user
        if not user or not user.is_staff:
            return False
        if obj is None or user.is_superuser:
            return True
        author = await obj.get_related("author")
        return author is not None and str(author.id) == str(user.id)
```

This example assumes `Post.author` is a forward foreign key. Its stored value
is an identifier; `get_related("author")` explicitly loads the related object.
A missing nullable author denies editing. For this simple ownership rule,
comparing the stored author identifier is cheaper; the asynchronous example
illustrates how to perform a related-object lookup when your policy needs one.

---

## Field-Level Permissions

### Read-only fields per user

Readonly fields are display-only on both create and update POSTs. Even if a
client submits a readonly field explicitly, the admin removes it before saving.

```python
class PostAdmin(ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if not request.state.user.is_superuser:
            readonly += ["is_featured", "author"]
        return readonly
```

### Show different fields per user or action

```python
class UserAdmin(ModelAdmin):
    def get_fields(self, request, obj=None):
        base = ["email", "name", "role", "is_active"]
        if request.state.user.is_superuser:
            base += ["api_key", "internal_notes"]
        return base
```

---

## Filtering Visible Records

Override `get_queryset` (async) so users only see records they should:

```python
class PostAdmin(ModelAdmin):
    async def get_queryset(self, request):
        qs = await super().get_queryset(request)
        user = request.state.user
        if user.is_superuser:
            return qs
        return qs.filter(author_id=str(user.id))
```

---

## Action Permissions

Tie a bulk action to a permission with the `permissions` argument of `@action`.
Each name `X` is checked against `has_X_permission(request)` before the action
runs.

```python
from aksara.contrib.admin import ModelAdmin, action

class PostAdmin(ModelAdmin):
    actions = ["publish", "archive"]

    @action(description="Publish selected", permissions=["change"])
    async def publish(self, request, queryset):
        await queryset.update(is_published=True)

    @action(description="Archive selected", permissions=["delete"])
    async def archive(self, request, queryset):
        await queryset.update(is_archived=True)
```

If the current user fails the required permission, the action is rejected with a
403.

For object-aware hooks such as `has_change_permission(request, obj)` and
`has_delete_permission(request, obj)`, bulk actions also check each selected
object before the action runs. If any selected object fails, the whole action is
rejected and no built-in delete is performed.

---

## Complete Pattern

This example combines module visibility, row filtering, object-level edit/delete
rules, readonly fields, and a guarded bulk action:

```python
from aksara.contrib.admin import ModelAdmin, action

class PostAdmin(ModelAdmin):
    list_display = ["title", "author", "is_published"]
    actions = ["publish_selected", "delete_selected"]

    def has_module_permission(self, request):
        return request.state.user.is_staff

    async def get_queryset(self, request):
        qs = await super().get_queryset(request)
        user = request.state.user
        if user.is_superuser:
            return qs
        return qs.filter(author_id=str(user.id))

    def has_change_permission(self, request, obj=None):
        user = request.state.user
        if obj is None:
            return user.is_staff
        return user.is_superuser or str(obj.author_id) == str(user.id)

    def has_delete_permission(self, request, obj=None):
        user = request.state.user
        if obj is None:
            return user.is_staff
        return user.is_superuser

    def get_readonly_fields(self, request, obj=None):
        if request.state.user.is_superuser:
            return ["created_at", "updated_at"]
        return ["created_at", "updated_at", "author"]

    @action(description="Publish selected", permissions=["change"])
    async def publish_selected(self, request, queryset):
        count = await queryset.update(is_published=True)
        self.message_user(request, f"Published {count} posts.", level="success")
```

---

## Security Notes

- Keep admin CSRF enabled in production. Disabling
  `AKSARA_ADMIN_CSRF_ENABLED` should be limited to tests or controlled local
  debugging.
- A model hidden by `has_module_permission()` is not shown in the dashboard, but
  direct model routes are still protected by `has_view_permission`,
  `has_change_permission`, and related hooks.
- Use `get_queryset()` for data visibility. Permission hooks decide whether an
  operation is allowed; the queryset decides which rows the user can list and
  select.

---

## Quick Reference

| Method | Controls | `obj=None` means |
|--------|----------|------------------|
| `has_module_permission(request)` | Model visibility in the dashboard | n/a |
| `has_view_permission(request, obj)` | View records | list-level check |
| `has_add_permission(request)` | Create records | n/a |
| `has_change_permission(request, obj)` | Edit records | list-level check |
| `has_delete_permission(request, obj)` | Delete records | list-level check |

---

## Related Documentation

- [AdminSite](admin-site.md) — Configure and mount the admin
- [ModelAdmin](model-admin.md) — Customize model display
- [Actions](actions.md) — Bulk action permission checks
- [Authentication](../api/authentication.md) — User login system
