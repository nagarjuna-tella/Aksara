# Migrations

Manage database schema changes with Aksara's migration system.

---

## Overview

Aksara uses a **project-wide** migration system. All migrations live in a single `migrations/` directory at your project root, regardless of how many models or modules you have.

```bash
# Create migrations from your models
aksara makemigrations --app app.models

# Apply migrations to the database
aksara migrate
```

### Project Structure

```
myproject/
├── main.py
├── settings.py
├── app/
│   ├── models.py
│   ├── views.py
│   └── ...
└── migrations/           # All migrations go here
    ├── __init__.py
    ├── 0001_auto_initial.py
    └── 0002_auto_add_email_verification.py
```

The migrations directory is configured via `AKSARA_MIGRATIONS_DIR` in your `.env` or `settings.py` (default: `migrations`).

---

## Creating Migrations

### makemigrations

Generate migration files from your models:

```bash
# Scan models from a module and generate a migration
aksara makemigrations --app app.models

# With a custom name
aksara makemigrations --app app.models --name add_email_verification

# Output to a custom directory
aksara makemigrations --app app.models --output my_migrations

# Preview without writing (print to stdout)
aksara makemigrations --app app.models --stdout

# Generate legacy SQL format instead of Python
aksara makemigrations --app app.models --sql
```

This creates a migration file in your `migrations/` directory:

```
migrations/0001_auto_add_email_verification.py
```

### Migration File Structure

```python
"""
Migration: add_email_verification
Generated: 2026-02-07T10:30:00
"""

from aksara.migrations import Migration
from aksara.migrations import operations as op


class Migration(Migration):
    """
    Auto-generated migration for models: User
    """

    dependencies = []

    operations = [
        op.AddField(
            model_name="User",
            name="email_verified",
            field=fields.Boolean(default=False),
        ),
        op.AddField(
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
aksara migrate

# Specify a database URL
aksara migrate --database-url postgresql://localhost/mydb

# Preview without applying
aksara migrate --dry-run

# Mark migrations as applied without running SQL
aksara migrate --fake

# Use a custom migrations directory
aksara migrate --migrations-dir my_migrations
```

### Check Migration Status

```bash
aksara status

# Output:
# 📁 Migrations directory: migrations
# 📊 Applied migrations: 2
#
#  [X] 0001_auto_initial
#  [X] 0002_auto_add_email_verification
#  [ ] 0003_auto_add_avatar              # Not applied
```

### How Migrations Are Applied Safely

`aksara migrate` and the testing helpers apply migrations through one canonical
executor that wraps each migration in a transaction, takes a PostgreSQL advisory
lock so two processes cannot migrate at once, executes multi-statement SQL
statement-by-statement, and verifies the checksum of every already-applied
migration before running new ones.

See [Migration Safety](migration-safety.md) for the full behavior, including what
happens when a migration fails, what a checksum mismatch means, and how historical
migrations without a stored checksum are handled.

---

## Migration Operations

Aksara provides Python-based operations for schema changes.

### CreateTable

Create a new database table:

```python
from aksara.migrations.operations import CreateTable
from aksara import fields

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
from aksara.migrations.operations import DropTable

DropTable(name="old_posts")
```

### AddField

Add a field to an existing table:

```python
from aksara.migrations.operations import AddField

AddField(
    model_name="User",
    name="phone",
    field=fields.String(max_length=20, nullable=True),
)
```

### RemoveField

Remove a field:

```python
from aksara.migrations.operations import RemoveField

RemoveField(
    model_name="User",
    name="phone",
)
```

### AlterField

Modify field properties:

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.migrations.operations import AlterField

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
from aksara.migrations.operations import RenameField

RenameField(
    model_name="User",
    old_name="username",
    new_name="handle",
)
```

### AddIndex

Create an index:

```python
from aksara.migrations.operations import AddIndex

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
from aksara.migrations.operations import RemoveIndex

RemoveIndex(
    model_name="Post",
    name="idx_posts_created_at",
)
```

### AddConstraint

Add a database constraint:

```python
from aksara.migrations.operations import AddConstraint

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
from aksara.migrations.operations import RemoveConstraint

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

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.migrations import Migration
from aksara.migrations.operations import RunPython


async def populate_slugs(db):
    """Generate slugs for existing posts."""
    rows = await db.fetch("SELECT id, title FROM posts WHERE slug IS NULL")
    for row in rows:
        slug = row["title"].lower().replace(" ", "-")
        await db.execute("UPDATE posts SET slug = $1 WHERE id = $2", slug, row["id"])


async def reverse_slugs(db):
    """Reverse migration: clear slugs."""
    await db.execute("UPDATE posts SET slug = NULL")


class Migration(Migration):
    dependencies = ["0002_auto_add_slug"]

    operations = [
        RunPython(populate_slugs, reverse_slugs),
    ]
```

### RunSQL

Execute raw SQL:

```python
from aksara.migrations.operations import RunSQL

RunSQL(
    sql="CREATE EXTENSION IF NOT EXISTS pg_trgm;",
    reverse_sql="DROP EXTENSION IF EXISTS pg_trgm;",
)
```

---

## Migration Dependencies

### Declaring Dependencies

Migrations can declare dependencies on previous migrations to ensure correct ordering:

```python
class Migration(Migration):
    dependencies = [
        "0001_auto_initial",
    ]
```

Dependencies are referenced by migration name (the filename stem). The migration executor builds a directed acyclic graph (DAG) from these dependencies and applies them in topological order.

---

## Conflict Detection

Aksara detects migration conflicts when multiple developers create migrations from the same base.

### What is a Conflict?

```
0001_auto_initial
    │
    ├── 0002_auto_add_email (Developer A)
    │
    └── 0002_auto_add_phone (Developer B)  ← CONFLICT: two heads
```

### Resolving Conflicts

Create a merge migration:

```bash
aksara makemigrations --merge
```

This creates an empty migration that depends on both heads, linearizing the history:

```python
# 0003_merge.py
class Migration(Migration):
    """Merge migration to resolve conflict."""

    dependencies = [
        "0002_auto_add_email",
        "0002_auto_add_phone",
    ]

    operations = []  # Just resolves the dependency graph
```

---

## Best Practices

### Keep Migrations Small

```text
# Good: One logical change per migration
AddField(model_name="User", name="avatar_url", ...)

# Avoid: Multiple unrelated changes in one migration
```

### Name Migrations Descriptively

```bash
aksara makemigrations --app app.models --name add_user_profile_fields
aksara makemigrations --app app.models --name rename_username_to_handle
```

### Test Migrations

```python
async def test_migration_applies():
    """Verify migration creates the expected schema."""
    # Apply migration
    await migrate()

    # Verify schema via model
    user = await User.objects.create(email="test@example.com")
    assert user.email_verified == False
```

### Don't Edit Applied Migrations

Once a migration has been applied to any environment:

- Don't modify it
- Create a new migration for further changes

Aksara enforces this: each applied migration's checksum is verified against the
file on disk before new migrations run, and an edited applied migration fails the
run with a clear error. See [Migration Safety](migration-safety.md).

### Preview Before Applying

```bash
# See what will happen without changing the database
aksara migrate --dry-run
```

---

## Migration Graph

Aksara maintains a directed acyclic graph (DAG) of migrations to determine execution order:

```
0001_auto_initial
│
└── 0002_auto_add_email
    │
    ├── 0003_auto_add_profile
    │
    └── 0004_auto_add_avatar
        │
        └── 0005_auto_add_bio
```

The graph ensures migrations are applied in the correct order, even when dependencies branch and merge.

---

## Environment Configuration

Configure the migrations directory in your `.env`:

```bash
# Default: migrations
AKSARA_MIGRATIONS_DIR=migrations
```

Or override per-command:

```bash
aksara makemigrations --app app.models --output custom_migrations
aksara migrate --migrations-dir custom_migrations
```

---

## Troubleshooting

### Migration Not Detected

```bash
# Make sure you specify the models module
aksara makemigrations --app app.models

# Check model registration
aksara models --app app.models
```

### Migration Fails to Apply

```bash
# Preview the migration operations
aksara migrate --dry-run

# Check what's already applied
aksara status
```

### Database Out of Sync

```bash
# Mark a migration as applied without running it
aksara migrate --fake
```

---

## Complete Example

A full migration workflow:

```python
# 1. app/models.py — Add new field
class User(Model):
    email = fields.Email(unique=True)
    name = fields.String(max_length=100)
    avatar_url = fields.URL(nullable=True)  # NEW FIELD
```

```bash
# 2. Generate migration
aksara makemigrations --app app.models --name add_avatar_url
# Created: migrations/0005_auto_add_avatar_url.py
```

```python
# 3. Review generated migration
# migrations/0005_auto_add_avatar_url.py
from aksara.migrations import Migration
from aksara.migrations import operations as op
from aksara import fields

class Migration(Migration):
    dependencies = ["0004_auto_add_bio"]

    operations = [
        op.AddField(
            model_name="User",
            name="avatar_url",
            field=fields.URL(nullable=True),
        ),
    ]
```

```bash
# 4. Apply migration
aksara migrate

# Output:
# Applying 0005_auto_add_avatar_url... ✓ Applied successfully
```

```bash
# 5. Verify
aksara status
# [X] 0005_auto_add_avatar_url
```

---

## Related Documentation

- [Migration Safety](migration-safety.md) — how migrations are applied and verified
- [Models](models.md) — Model definition
- [Fields](fields.md) — Field types
- [CLI Reference](../cli/index.md) — All CLI commands
