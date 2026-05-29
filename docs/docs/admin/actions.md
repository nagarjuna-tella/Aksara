# Admin Actions

Bulk actions let staff users run an operation against selected rows from an
admin list view.

---

## Defining an Action

Use the `@action` decorator on a `ModelAdmin` method and list the method name in
`actions`.

```python
from aksara.contrib.admin import ModelAdmin, action

class PostAdmin(ModelAdmin):
    actions = ["publish_selected"]

    @action(description="Publish selected posts", permissions=["change"])
    async def publish_selected(self, request, queryset):
        count = await queryset.update(is_published=True)
        self.message_user(request, f"Published {count} posts.", level="success")
```

The method receives:

| Argument | Meaning |
|----------|---------|
| `request` | The current admin request |
| `queryset` | A queryset containing the selected rows |

Actions may be `async def` or regular functions. Use `message_user()` to show a
flash message after the redirect back to the list view.

---

## Built-in Delete

`delete_selected` is available by name:

```python
class PostAdmin(ModelAdmin):
    actions = ["delete_selected"]
```

The built-in delete action calls `delete_model()` for each selected object, so
custom delete hooks still run.

---

## Permission Checks

The `permissions` argument maps names to `ModelAdmin` permission methods:

```python
@action(description="Archive selected", permissions=["change"])
async def archive_selected(self, request, queryset):
    await queryset.update(is_archived=True)
```

`permissions=["change"]` checks `has_change_permission()`. Similarly,
`permissions=["delete"]` checks `has_delete_permission()`.

Checks run at two levels:

- List-level: `has_change_permission(request)` before the action starts.
- Object-level: `has_change_permission(request, obj)` for every selected object
  when the hook accepts an `obj` argument.

If any selected object fails the relevant object-level permission check, the
whole action is rejected before the action body runs.

---

## Selection Semantics

The admin verifies that all submitted ids resolve through the current
`get_queryset()` result before running an action. Use `get_queryset()` to limit
which rows a user can list and select.

```python
class PostAdmin(ModelAdmin):
    async def get_queryset(self, request):
        qs = await super().get_queryset(request)
        if request.state.user.is_superuser:
            return qs
        return qs.filter(author_id=str(request.state.user.id))
```

---

## Related Documentation

- [ModelAdmin](model-admin.md) — Configure actions on a model
- [Admin Permissions](admin-permissions.md) — Permission hooks and object checks
