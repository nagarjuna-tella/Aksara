# Fixtures

Aksara provides tools to easily export and import your database data as JSON or YAML fixtures, useful for testing, development seeding, and simple backups.

---

## Exporting Data

You can export data for a single model or the entire database.

```python
from aksara.fixtures import dump_data, dump_database

# Export single model
json_data = await dump_data(User, format="json")

# Export with filters and specific fields
json_data = await dump_data(
    Post,
    filters={"published": True},
    fields=['id', 'title', 'author'],  # Only specific fields
    format="json"
)

# Export entire database
full_backup = await dump_database(format="json")

# Save to file
with open("users.json", "w") as f:
    f.write(json_data)
```

## Importing Fixtures

Importing fixtures gracefully handles both inserts (for new records) and updates (if a record with the same primary key already exists).

```python
from aksara.fixtures import load_data

# Load from JSON
with open("users.json") as f:
    json_data = f.read()

stats = await load_data(json_data, format="json")

print(f"Loaded {stats['loaded']} records")
print(f"Errors: {stats['errors']}")
print(f"Skipped: {stats['skipped']}")
```

### Strict Mode

By default, `load_data` operates leniently: if a record fails validation, it logs the error and continues. You can enforce strict validation to abort the process on the first error:

```python
# Strict mode raises on any error
try:
    await load_data(json_data, strict=True)
except Exception as e:
    print(f"Fixture load failed: {e}")
```
