# Soft deletes

Soft deletion keeps a row and marks it with `deleted_at`. It supports application
recovery, but is not an audit trail, retention policy, or authorization boundary.
Database constraints still apply to retained rows, including unique constraints.

## Define the model

Put the mixin before `Model` so its instance deletion method takes precedence.
Generate and review a migration before using the added nullable timestamp column.

```python title="soft_delete_models.py"
from aksara import Model, fields
from aksara.contrib.soft_delete import SoftDeleteModel


class ArchivedDocument(SoftDeleteModel, Model):
    title = fields.String()
```

## Delete and restore one record

The following application function assumes the model above has been imported,
its migration has been applied, and the application's database is connected.
Pass the UUID of an existing record.

```python title="restore_document.py"
async def delete_and_restore(document_id):
    document = await ArchivedDocument.objects.get(id=document_id)
    await document.delete()

    deleted = await ArchivedDocument.objects.only_deleted().filter(
        id=document_id
    ).first()
    if deleted is None:
        raise LookupError("Deleted document was not found")
    await deleted.undelete()
    return deleted
```

Instance `delete()` sets a UTC timestamp and sends `pre_delete` and `post_delete`
signals. `undelete()` clears the timestamp. Both reject an unsaved instance with
`ValueError`. They update by primary key; perform your application's permission
and tenant checks before calling them, and retain database RLS where required.

## Select active, deleted, or all rows

Start with the manager's desired visibility mode, then apply every application
filter. These expressions are query builders; call and await `.all()` to fetch lists.

```python title="soft_delete_queries.py"
active = ArchivedDocument.objects.filter(title="Draft")
including_deleted = ArchivedDocument.objects.with_deleted().filter(title="Draft")
deleted_only = ArchivedDocument.objects.only_deleted().filter(title="Draft")
```

Ordinary manager queries exclude deleted rows. `with_deleted()` includes active
and deleted rows; `only_deleted()` selects rows with a non-null timestamp.
A queryset is not directly awaitable. `await queryset.all()` returns a list. Use `first()`
and handle `None` when restoring a selected record.

The module-level `with_deleted(queryset)` and `only_deleted(queryset)` helpers
clone the supplied queryset and preserve its filters, Q expressions, ordering,
limits, annotations, and relation-loading state. Changing visibility therefore
does not broaden an already restricted tenant or customer selection. The
manager-first forms shown above remain the clearest starting point for new code.

!!! warning "Queryset deletion is physical deletion"
    `ArchivedDocument.objects.filter(...).delete()` executes SQL `DELETE`.
    It does not call each instance's soft-delete method. To mark a record deleted,
    load the authorized instance and call its `delete()` method as shown above.
    Soft deletion also does not make database cascades into logical deletion.

See [transactions](expressions-and-transactions.md) for transaction boundaries and
[multi-tenancy](../security/multi-tenancy.md) for tenant enforcement.
