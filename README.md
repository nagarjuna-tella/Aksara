# ⚡ Vidyut

> Async Postgres ORM for FastAPI

Vidyut (meaning "electricity" in Sanskrit) is a lightweight, async-native ORM designed specifically for PostgreSQL and FastAPI. It provides a clean, Django-like API for defining models and performing CRUD operations.

## Features

- 🚀 **Async-first**: Built from the ground up for async/await
- 🐘 **Postgres-native**: Designed specifically for PostgreSQL
- ⚡ **FastAPI integration**: Seamless dependency injection and lifecycle management
- 🎯 **Django-like API**: Familiar model definition and query syntax
- 🔧 **Simple migrations**: Generate and apply CREATE TABLE SQL
- 📦 **Unified imports**: Everything you need from a single package

---

## 🚀 Quick Start (10 minutes)

### Step 1: Install Vidyut

```bash
# Clone and install in development mode
git clone https://github.com/yourusername/vidyut.git
cd vidyut
pip install -e .
```

Or if published to PyPI:
```bash
pip install vidyut
```

### Step 2: Start Postgres

Using Docker (recommended):
```bash
docker run --name vidyut-postgres \
    -e POSTGRES_PASSWORD=secret \
    -p 5432:5432 \
    -d postgres

# Create your database
docker exec vidyut-postgres psql -U postgres -c "CREATE DATABASE myapp;"
```

### Step 3: Set DATABASE_URL

```bash
export DATABASE_URL="postgresql://postgres:secret@localhost:5432/myapp"
```

### Step 4: Create Your App (`main.py`)

```python
import os
from vidyut import Vidyut, Model, fields

# Define your model
class User(Model):
    email = fields.String(max_length=255, unique=True)
    name = fields.String(max_length=100, nullable=True)
    is_active = fields.Boolean(default=True)

# Create the app (DB connection is automatic!)
app = Vidyut(
    database_url=os.environ["DATABASE_URL"],
    title="My API",
)

# ===== CRUD Routes =====

@app.post("/users")
async def create_user(email: str, name: str = None):
    user = await User.objects.create(email=email, name=name)
    return {"id": str(user.id), "email": user.email, "name": user.name}

@app.get("/users")
async def list_users():
    users = await User.objects.filter(is_active=True).all()
    return [{"id": str(u.id), "email": u.email} for u in users]

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    user = await User.objects.get(id=user_id)
    return {"id": str(user.id), "email": user.email, "name": user.name}

@app.delete("/users/{user_id}")
async def delete_user(user_id: str):
    user = await User.objects.get(id=user_id)
    await user.delete()
    return {"deleted": True}
```

### Step 5: Run Migrations

```bash
# Generate and apply CREATE TABLE SQL
vidyut migrate --app main

# Output:
# ⚡ Vidyut Migrate
# ----------------------------------------
# ✓ Discovered models from 'main'
# Found 1 model(s)
# ✓ Connected to database
# → Creating table 'users'...
#   ✓ Table 'users' created/verified
# ========================================
# ✓ Migrations complete!
```

### Step 6: Run Your App

```bash
vidyut run main:app --reload

# Output:
#   ⚡ Vidyut v0.3.1
#   Async Framework
#
#   → Running: main:app
#   → Server:  http://127.0.0.1:8000
#   → Reload:  enabled
#
#   ⚡ Vidyut - Async Framework
#   ✓ Database connected
```

### Step 7: Test Your API

```bash
# Create a user
curl -X POST "http://localhost:8000/users?email=hello@vidyut.dev&name=Alice"
# {"id":"abc123...","email":"hello@vidyut.dev","name":"Alice"}

# List users
curl http://localhost:8000/users
# [{"id":"abc123...","email":"hello@vidyut.dev"}]

# Get single user
curl http://localhost:8000/users/abc123...

# Delete user  
curl -X DELETE http://localhost:8000/users/abc123...
```

**That's it!** You now have a fully async FastAPI app with PostgreSQL. 🎉

---

## CRUD Operations

```python
# Create
user = await User.objects.create(email="hello@example.com", name="Alice")

# Get by ID
user = await User.objects.get(id="uuid-here")

# Get by any field
user = await User.objects.get(email="hello@example.com")

# Get or None (no exception if not found)
user = await User.objects.get_or_none(email="maybe@exists.com")

# Get or Create
user, created = await User.objects.get_or_create(
    email="hello@example.com",
    defaults={"name": "Default Name"}
)

# Filter and fetch all
users = await User.objects.filter(is_active=True).all()

# Filter and fetch first
user = await User.objects.filter(email="hello@example.com").first()

# Count
count = await User.objects.filter(is_active=True).count()

# Update (modify and save)
user.name = "New Name"
await user.save()  # updated_at is auto-updated

# Delete
await user.delete()
```

---

## Model Fields

| Field | PostgreSQL Type | Key Arguments |
|-------|-----------------|---------------|
| `String` | `VARCHAR(n)` | `max_length=255`, `unique`, `nullable`, `default` |
| `Integer` | `INTEGER` | `unique`, `nullable`, `default` |
| `Boolean` | `BOOLEAN` | `nullable`, `default` |
| `DateTime` | `TIMESTAMP WITH TIME ZONE` | `auto_now`, `auto_now_add`, `nullable` |
| `UUID` | `UUID` | `primary_key` |
| `JSON` | `JSONB` | `nullable`, `default` |

### Built-in Fields (auto-added to every model)

```python
id         # UUID primary key (auto-generated)
created_at # TIMESTAMP - set once on insert
updated_at # TIMESTAMP - updated on every save()
```

---

## Unified Imports

Everything you need comes from one place:

```python
from vidyut import (
    # ORM Core
    Model, fields, Database,
    DoesNotExist, MultipleObjectsReturned,
    
    # Vidyut App (FastAPI + auto-DB)
    Vidyut,
    
    # FastAPI (re-exported for convenience)
    FastAPI, APIRouter, Depends,
    HTTPException, Request, Response,
    Query, Path, Header, status,
    JSONResponse, HTMLResponse,
)
```

---

## CLI Commands

```bash
# Run your app
vidyut run main:app --reload
vidyut run main:app --host 0.0.0.0 --port 8080

# Migrations
vidyut makemigrations --app mymodule          # Preview CREATE TABLE SQL
vidyut migrate --app mymodule                  # Apply to database
vidyut migrate --app mymodule --dry-run        # Preview without executing

# Inspect
vidyut models --app mymodule                   # List all models and fields

# Interactive shell
vidyut shell                                   # Async REPL with DB access
```

---

## Example Project Structure

```
myproject/
├── main.py              # App + models
├── pyproject.toml       # Dependencies
└── .env                 # DATABASE_URL=postgresql://...
```

Or for larger projects:

```
myproject/
├── app/
│   ├── __init__.py
│   ├── main.py          # Vidyut app
│   ├── models.py        # Model definitions
│   └── routes/
│       ├── users.py
│       └── posts.py
├── pyproject.toml
└── .env
```

---

## Requirements

- Python 3.11+
- PostgreSQL 12+
- FastAPI 0.104+
- asyncpg 0.29+

---

## License

MIT License
