# Migrations

Manage database schema changes with Vidyut's migration system.

---

## Overview

Vidyut uses a Python-based migration system similar to Django's, with automatic change detection and conflict resolution:

```bash
# Create migrations for model changes
vidyut makemigrations

# Apply migrations to database
vidyut migrate
```

---

## Creating Migrations

### makemigrations

Generate migration files from model changes:

```bash
# Generate migrations for all apps
vidyut makemigrations

# Generate for specific app
vidyut makemigrations myapp

# With custom name
vidyut makemigrations --name add_email_verification
```

This creates a migration file like:

```
myapp/migrations/0002_add_email_verification.py
```

### Migration File Structure

```python
"""Add email verification fields."""

from vidyut.migrations import Migration
from vidyut.migrations.operations import AddField
from vidyut import fields


class Migration(Migration):
    """Add email_verified and verification_token to User model."""
    
    dependencies = [
        ("myapp", "0001_initial"),
    ]
    
    operations = [
        AddField(
            model_name="User",
            name="email_verified",
            field=fields.Boolean(default=False),
        ),
        AddField(
            model_name="User",
            name="verification_token",
            field=fields.String(max_length=100, nullable=True),
        ),
    ]
```

---

## Applying Migrations

### migrate

Apply pending migrations:

```bash
# Apply all pending migrations
vidyut migrate

# Apply migrations for specific app
vidyut migrate myapp

# Migrate to specific migration
vidyut migrate myapp 0001_initial

# Roll back all migrations for an app
vidyut migrate myapp zero
```

### Check Migration Status

```bash
# Show migration status
vidyut showmigrations

# Output:
# myapp
#  [X] 0001_initial
#  [X] 0002_add_email_verification
#  [ ] 0003_add_avatar  # Not applied
```

---

## Migration Operations

Vidyut provides Python-based operations for schema changes.

### CreateTable

Create a new database table:

```python
from vidyut.migrations.operations import CreateTable
from vidyut import fields

CreateTable(
    name="posts",
    fields=[
        ("id", fields.UUID(primary_key=True)),
        ("title", fields.String(max_length=200)),
        ("content", fields.Text()),
        ("author_id", fields.UUID()),
        ("created_at", fields.DateTime(auto_now_add=True)),
    ],
)
```

### DropTable

Remove a table:

```python
from vidyut.migrations.operations import DropTable

DropTable(name="old_posts")
```

### AddField

Add a field to an existing table:

```python
from vidyut.migrations.operations import AddField

AddField(
    model_name="User",
    name="phone",
    field=fields.String(max_length=20, nullable=True),
)
```

### RemoveField

Remove a field:

```python
from vidyut.migrations.operations import RemoveField

RemoveField(
    model_name="User",
    name="phone",
)
```

### AlterField

Modify field properties:

```python
from vidyut.migrations.operations import AlterField

# Change max_length
AlterField(
    model_name="User",
    name="name",
    field=fields.String(max_length=200),  # Was 100
)

# Make field nullable
AlterField(
    model_name="Post",
    name="category_id",
    field=fields.UUID(nullable=True),  # Was required
)
```

### RenameField

Rename a field:

```python
from vidyut.migrations.operations import RenameField

RenameField(
    model_name="User",
    old_name="username",
    new_name="handle",
)
```

### AddIndex

Create an index:

```python
from vidyut.migrations.operations import AddIndex

AddIndex(
    model_name="Post",
    name="idx_posts_created_at",
    fields=["created_at"],
)

# Composite index
AddIndex(
    model_name="Post",
    name="idx_posts_author_date",
    fields=["author_id", "created_at"],
)
```

### RemoveIndex

Drop an index:

```python
from vidyut.migrations.operations import RemoveIndex

RemoveIndex(
    model_name="Post",
    name="idx_posts_created_at",
)
```

### AddConstraint

Add a database constraint:

```python
from vidyut.migrations.operations import AddConstraint

# Unique constraint
AddConstraint(
    model_name="User",
    name="unique_email",
    type="unique",
    fields=["email"],
)

# Check constraint
AddConstraint(
    model_name="Product",
    name="positive_price",
    type="check",
    expression="price > 0",
)
```

### RemoveConstraint

Remove a constraint:

```python
from vidyut.migrations.operations import RemoveConstraint

RemoveConstraint(
    model_name="User",
    name="unique_email",
)
```

---

## Data Migrations

Migrations can include data changes alongside schema changes.

### RunPython

Execute Python code during migration:

```python
from vidyut.migrations import Migration
from vidyut.migrations.operations import RunPython

def populate_slugs(apps, schema_editor):
    """Generate slugs for existing posts."""
    Post = apps.get_model("myapp", "Post")
    for post in Post.objects.filter(slug__isnull=True):
        post.slug = slugify(post.title)
        post.save()

def reverse_slugs(apps, schema_editor):
    """Reverse migration: clear slugs."""
    Post = apps.get_model("myapp", "Post")
    Post.objects.update(slug=None)

class Migration(Migration):
    dependencies = [("myapp", "0002_add_slug")]
    
    operations = [
        RunPython(populate_slugs, reverse_slugs),
    ]
```

### RunSQL

Execute raw SQL:

```python
from vidyut.migrations.operations import RunSQL

RunSQL(
    sql="CREATE EXTENSION IF NOT EXISTS pg_trgm;",
    reverse_sql="DROP EXTENSION IF EXISTS pg_trgm;",
)
```

---

## Migration Dependencies

### Declaring Dependencies

```python
class Migration(Migration):
    dependencies = [
        # Same app: previous migration
        ("myapp", "0001_initial"),
        
        # Other app: specific migration
        ("users", "0003_add_profile"),
    ]
```

### Cross-App Dependencies

When models in different apps are related:

```python
# posts/migrations/0001_initial.py
class Migration(Migration):
    dependencies = [
        # Ensure users app's User model exists
        ("users", "0001_initial"),
    ]
    
    operations = [
        CreateTable(
            name="posts",
            fields=[
                # ... other fields
                ("author_id", fields.ForeignKey("users.User")),
            ],
        ),
    ]
```

---

## Conflict Detection

Vidyut automatically detects migration conflicts when multiple developers create migrations from the same base.

### What is a Conflict?

```
0001_initial
    │
    ├── 0002_add_email (Developer A)
    │
    └── 0002_add_phone (Developer B)  ← CONFLICT
```

### Detecting Conflicts

```bash
vidyut makemigrations --check
# Error: Conflicting migrations detected
```

### Resolving Conflicts

Option 1: **Merge migrations**

```bash
vidyut makemigrations --merge
# Creates: 0003_merge_add_email_add_phone.py
```

Option 2: **Renumber manually**

Rename Developer B's migration to `0003_add_phone.py` and update its dependencies.

### Merge Migration Example

```python
# 0003_merge_add_email_add_phone.py
class Migration(Migration):
    """Merge migration to resolve conflict."""
    
    dependencies = [
        ("myapp", "0002_add_email"),
        ("myapp", "0002_add_phone"),
    ]
    
    operations = []  # Just resolves the dependency graph
```

---

## Best Practices

### Keep Migrations Small

```python
# Good: One logical change per migration
AddField(model_name="User", name="avatar_url", ...)

# Avoid: Multiple unrelated changes in one migration
```

### Name Migrations Descriptively

```bash
vidyut makemigrations --name add_user_profile_fields
vidyut makemigrations --name rename_username_to_handle
```

### Test Migrations

```python
# In tests
async def test_migration_0002():
    # Apply migration
    await migrate("myapp", "0002")
    
    # Verify schema
    user = await User.objects.create(email="test@example.com")
    assert user.email_verified == False
```

### Don't Edit Applied Migrations

Once a migration is in production:
- ❌ Don't modify it
- ✅ Create a new migration for changes

### Use Data Migrations Carefully

```python
# Include reverse operations
RunPython(forward_func, reverse_func)

# Handle empty tables
def forward(apps, schema_editor):
    Model = apps.get_model("myapp", "Model")
    if Model.objects.exists():
        # Only if there's data
        ...
```

---

## Squashing Migrations

Combine multiple migrations into one for a cleaner history:

```bash
vidyut squashmigrations myapp 0001 0010
# Creates: 0001_squashed_0010.py
```

The squashed migration:
- Combines all operations
- Sets `replaces = [...]` to track original migrations
- Works seamlessly with existing databases

---

## Migration Graph

Vidyut maintains a directed acyclic graph (DAG) of migrations:

```bash
vidyut showmigrations --graph

# Output:
# myapp
#    0001_initial
#    │
#    └── 0002_add_email
#        │
#        ├── 0003_add_profile
#        │
#        └── 0004_add_avatar
#            │
#            └── 0005_add_bio
```

---

## Troubleshooting

### Migration Not Detected

```bash
# Force detection
vidyut makemigrations --force

# Check model registration
vidyut info --models
```

### Migration Fails to Apply

```bash
# Show SQL without applying
vidyut sqlmigrate myapp 0002

# Apply with verbose output
vidyut migrate --verbosity=2
```

### Database Out of Sync

```bash
# Fake a migration (mark as applied without running)
vidyut migrate --fake myapp 0002

# Fake initial migration
vidyut migrate --fake-initial myapp
```

---

## Complete Example

A full migration workflow:

```python
# 1. models.py - Add new field
class User(Model):
    email = fields.Email(unique=True)
    name = fields.String(max_length=100)
    avatar_url = fields.URL(nullable=True)  # NEW FIELD
```

```bash
# 2. Generate migration
vidyut makemigrations --name add_avatar_url
# Created: myapp/migrations/0005_add_avatar_url.py
```

```python
# 3. Review generated migration
# myapp/migrations/0005_add_avatar_url.py
from vidyut.migrations import Migration
from vidyut.migrations.operations import AddField
from vidyut import fields

class Migration(Migration):
    dependencies = [("myapp", "0004_add_bio")]
    
    operations = [
        AddField(
            model_name="User",
            name="avatar_url",
            field=fields.URL(nullable=True),
        ),
    ]
```

```bash
# 4. Apply migration
vidyut migrate

# Output:
# Applying myapp.0005_add_avatar_url... OK
```

```bash
# 5. Verify
vidyut showmigrations myapp
# [X] 0005_add_avatar_url
```

---

## Related Documentation

- [Models](models.md) — Model definition
- [Fields](fields.md) — Field types
- [CLI Reference](../cli/commands.md) — Migration commands
