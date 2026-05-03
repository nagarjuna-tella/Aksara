# Soft Deletes

Real applications rarely delete data permanently. Audit trails, compliance requirements, and data recovery all require logical deletion rather than hard removal. 

Aksara provides a native `SoftDeleteModel` pattern.

---

## Usage

Inherit from `SoftDeleteModel` instead of `Model`.

```python
from aksara.contrib.soft_delete import SoftDeleteModel, with_deleted, only_deleted
from aksara import fields

class User(SoftDeleteModel):
    email = fields.String(unique=True)
    name = fields.String()
    # A `deleted_at` DateTime field is automatically added
```

### Deleting Records

Calling `.delete()` on a soft-delete model will set the `deleted_at` timestamp instead of removing the record from the database.

```python
user = await User.objects.get(id=123)

# Sets deleted_at, doesn't remove record from PostgreSQL
await user.delete() 
```

### Querying

Standard ORM queries automatically filter out soft-deleted records.

```python
# Only returns users where deleted_at IS NULL
active_users = await User.objects.all()  
```

### Accessing Deleted Records

Aksara provides helper functions to bypass the automatic filtering:

```python
from aksara.contrib.soft_delete import with_deleted, only_deleted

# Include soft-deleted records alongside active ones
all_users = await with_deleted(User.objects.all())

# Query ONLY deleted records
deleted_users = await only_deleted(User.objects.all())
```

### Restoring Records

You can restore a soft-deleted record by querying for it with `with_deleted` and calling `.undelete()`.

```python
# Restore a soft-deleted record
user = await with_deleted(User.objects.filter(id=123))
await user.undelete()  # Clears the deleted_at timestamp
```
