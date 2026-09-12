# Admin Actions

Bulk actions let staff users run an operation against selected rows from an
admin list view.

---

## Defining an Action

Use the `@action` decorator on a `ModelAdmin` method and list the method name in
`actions`.

The following configuration fragment assumes your registered Post model has an
`is_published` Boolean field. Add `PostAdmin` to your existing AdminSite.

```python title="post_actions.py"
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

Only names with an implemented `has_<name>_permission` hook are checked.
Unknown names are skipped in v0.7.0, so a spelling mistake does not deny access.
Use the established `change`/`delete` names shown here and test denial paths;
the decorator alone does not validate permission names.

## Transactions and side effects

The bulk-action dispatcher does not wrap action bodies in a transaction.
The built-in delete loops over instances; an exception after earlier deletions
can leave partial work. For an action that must commit all its PostgreSQL writes
together, use an explicit supported [transaction](../orm/expressions-and-transactions.md)
inside the action. External effects require their own retry/reconciliation design.
A queryset `update()` bypasses per-instance `save_model()` hooks; use an explicit
instance workflow when those hooks are required.

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
