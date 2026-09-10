# Dev Tools

Development-focused CLI commands for inspecting your project, running the local server, and driving code-quality tooling.

---

## Overview

The current Aksara dev-tool surface covers four areas:

- **Project inspection** — `routes`, `models`, `info`, `status`
- **Local server workflow** — `dev`, `run`, `collectstatic`
- **Code generation** — `generate sdk`
- **Code quality** — `format`, `lint`, `typecheck`, `test`

Global output flags apply to every command and must be placed before the subcommand: `aksara --quiet dev`, `aksara --plain test`, `aksara --no-color info`.

---

## Project Inspection

### List Routes

```bash
aksara routes
aksara routes --format json
aksara routes --filter api/posts
aksara routes --method GET
```

Use this to inspect the registered HTTP surface without starting Studio.

> **Note:** `--filter` and `--method` are planned and not yet available.

**Example output:**

```
Method  Path                    Name                Handler
------  ----------------------  ------------------  ----------------------
GET     /api/users/             users-list          UserViewSet.list
POST    /api/users/             users-create        UserViewSet.create
GET     /api/users/{id}/        users-detail        UserViewSet.retrieve
PUT     /api/users/{id}/        users-update        UserViewSet.update
DELETE  /api/users/{id}/        users-delete        UserViewSet.destroy
```

### List Models

```bash
aksara models
aksara models --app blog.models --ai
aksara models --detail
```

`--ai` includes model and field AI metadata in the output. `--detail` shows full field definitions.

> **Note:** `--detail` is planned and not yet available.

**Example output:**

```
⚡ Aksara Models
----------------------------------------
Registered Models (3):

📦 User
   Table: users
   Fields:
     • id: UUID (PK)
     • email: VARCHAR unique
     • name: VARCHAR

📦 Post
   Table: posts
   Fields:
     • id: UUID (PK)
     • title: VARCHAR
     • body: TEXT
     • author_id: UUID
```

### Show Project Info

```bash
aksara info
aksara info --database-url postgresql://postgres:password@localhost:5432/myapp
```

This prints the framework version, environment, installed apps, feature toggles, registered models, and migration counts.

### Show Migration Status

```bash
aksara status
aksara status --database-url postgresql://postgres:password@localhost:5432/myapp
```

Use `status` when you want an applied-versus-pending migration view without running `migrate`.

### Preview Migrations (dry-run)

```bash
aksara migrate --dry-run
```

Shows every SQL statement that *would* be executed without actually applying any changes. Useful for reviewing auto-generated migrations before committing them to a shared database.

**Example output:**

```
⚡ Aksara — Migration Preview (dry-run)

  Pending: 2 migration(s)

  [blog] 0003_add_slug
    → ALTER TABLE posts ADD COLUMN slug VARCHAR(255);
    → CREATE UNIQUE INDEX posts_slug_uniq ON posts (slug);

  [users] 0002_add_bio
    → ALTER TABLE users ADD COLUMN bio TEXT;

  (dry-run) No changes applied.
```

---

## Development Server

### Preferred Local Server

```bash
aksara dev
aksara dev --port 3000
aksara dev myproject.main:app --log-level debug
aksara run dev
```

`aksara dev` is the preferred local workflow. It defaults to `main:app`, enables auto-reload, and prints the richer startup banner with the App, Admin, Studio, and Docs URLs.

### Direct ASGI Launch

```bash
aksara run main:app
aksara run main:app --host 0.0.0.0 --port 8080
aksara run myproject.main:app --workers 4
```

Use `run` when you want to point directly at an ASGI import path or exercise multi-worker behavior.

### Static Asset Bootstrap

```bash
aksara collectstatic
```

This creates missing project static assets such as `static/welcome.html`. The same step also runs automatically before `aksara dev` and `aksara run`.

---

## Code Generation

### Generate TypeScript SDK

```bash
aksara generate sdk --language typescript --output frontend/api.ts
aksara generate sdk --language typescript --views-module myapp.viewsets --stdout
```

This inspects discovered `ModelViewSet` classes and emits a typed fetch client.

### Generate Model

> **Planned** — not yet available.

```bash
aksara generate model "User with email, name, role, created_at"
aksara generate model "Post with title, body, author(FK:User), published_at"
```

Generates an Aksara `Model` class from a natural-language description.

### Generate ViewSet

> **Planned** — not yet available.

```bash
aksara generate viewset User
aksara generate viewset Post --prefix /api/posts
```

Generates a `ModelViewSet` for an existing model.

### Generate Serializer

> **Planned** — not yet available.

```bash
aksara generate serializer User
aksara generate serializer Post --fields title,body,author
```

Generates a `ModelSerializer` for an existing model.

### Generate Test

> **Planned** — not yet available.

```bash
aksara generate test User --output tests/test_users.py
aksara generate test PostViewSet
```

Generates a pytest test file for a model or viewset.

### Generate CRUD

> **Planned** — not yet available.

```bash
aksara generate crud User
aksara generate crud Post --prefix /api/v2/posts
```

Generates the full CRUD stack (model, viewset, serializer, migrations, tests) from a single command.

---

## Code Quality

### Format

```bash
aksara format
aksara format src/
aksara format --check
```

Runs Black against the target path.

### Lint

```bash
aksara lint
aksara lint src/
aksara lint --fix
```

Runs Ruff and optionally applies safe fixes.

### Type Check

```bash
aksara typecheck
aksara typecheck src/
aksara typecheck --strict
```

Runs mypy against the target path.

### Test

```bash
aksara test
aksara test tests/
aksara test -v --tb=short
aksara test tests/test_models.py -k "test_create"
aksara test --failfast
aksara test --parallel
aksara test --cov=myapp --cov-report=html
```

All extra arguments are passed straight through to pytest. Common flags:

| Flag | Description |
|------|-------------|
| `-v` / `--verbose` | Verbose output |
| `--failfast` | Stop on first failure |
| `--parallel` | Parallel execution (requires `pytest-xdist`) |
| `--cov` | Coverage measurement (requires `pytest-cov`) |
| `-k EXPRESSION` | Filter tests by name |
| `--tb=short` | Shorter tracebacks |

---

## Shell Enhancements

### Shell

```bash
aksara shell
aksara shell --no-ipython
```

Opens an interactive Python shell with the project context pre-loaded (database, models, `arun()` helper). Uses IPython if installed, falls back to standard Python REPL.

```pycon
>>> users = arun(User.objects.filter(active=True).all())
>>> for u in users[:5]:
...     print(u.email)
```

### Shell Plus (Planned)

> **Planned** — not yet available.

An enhanced shell with automatic model imports, richer output formatting, history persistence, and tab completion.

```bash
aksara shell_plus
```

---

## File Watch & Automation

### Watch (Planned)

> **Planned** — not yet available.

Watch for file changes and re-run tests automatically.

```bash
aksara watch
aksara watch tests/
```

---

## Data Commands

### Dump Data (Planned)

> **Planned** — not yet available.

Export database content to a JSON or YAML fixture file.

```bash
aksara dumpdata
aksara dumpdata blog --output blog_fixture.json --indent 2
aksara dumpdata --all --format yaml
```

### Load Data (Planned)

> **Planned** — not yet available.

Load fixture data into the database.

```bash
aksara loaddata fixtures.json
aksara loaddata blog_fixture.yaml
```

---

## Power-User Output Controls

```bash
aksara --quiet dev
aksara --plain dev
aksara --no-color info
aksara --force-color dev
```

`--quiet` suppresses non-error Aksara UI output such as banners and success summaries. It does not suppress subprocess output or Uvicorn logs. `--plain` disables Rich rendering and animation. `--no-color` keeps the same content without ANSI color, and `--force-color` is useful when terminal color detection is too conservative.

---

## Related Documentation

- [CLI Overview](index.md)
- [Commands Reference](commands.md)
- [CLI Reference](../reference/cli-reference.md)
- [AI Commands](ai-commands.md)

## Debugging Tools

### SQL Logging

Enable detailed SQL logging by setting DEBUG=True in settings:

**Conceptual legacy configuration (the runtime does not read an `AKSARA` dictionary):**

```text title="Conceptual legacy configuration"
# settings.py
AKSARA = {
    "DEBUG": True,
    "SQL_LOG": True,  # Log all SQL queries
}
```

Output:
```
[SQL] SELECT * FROM posts WHERE is_published = true (12ms)
[SQL] SELECT * FROM users WHERE id = 'abc-123' (3ms)
```

---

### Profile Request

Profile a specific endpoint:

```bash
aksara profile /api/posts/
```

Output:
```
Profile: GET /api/posts/

Total time: 145ms

Breakdown:
  Database: 89ms (15 queries)
  Python: 45ms
  Serialization: 11ms

Slowest queries:
  1. SELECT * FROM posts... (45ms)
  2. SELECT * FROM users... (12ms)
```

---

### Query Count

Check query count for endpoints:

```bash
aksara querycount /api/posts/
```

Output:
```
Endpoint: GET /api/posts/

Queries: 15
  - SELECT: 12
  - INSERT: 0
  - UPDATE: 0
  - DELETE: 0

Potential N+1: Yes (12 similar queries to users table)
```

---

## Scaffolding

### New App

```bash
aksara startapp blog
```

Creates:
```
blog/
├── __init__.py
├── models.py
├── viewsets.py
├── serializers.py
├── admin.py
├── urls.py
└── tests/
    ├── __init__.py
    ├── test_models.py
    └── test_api.py
```

---

### New Migration

```bash
aksara makemigrations --empty --name populate_data
```

Creates empty migration for data operations:

```python
async def forwards(apps, schema_editor):
    # Add your data migration here
    pass

async def backwards(apps, schema_editor):
    # Add reverse migration here
    pass

class Migration:
    dependencies = [("blog", "0002_add_slug")]
    operations = [
        RunPython(forwards, backwards),
    ]
```

---

## Configuration

### Dev Tools Settings

**Conceptual legacy configuration (the runtime does not read an `AKSARA` dictionary):**

```text title="Conceptual legacy configuration"
# settings.py
AKSARA = {
    "DEV_TOOLS": {
        "SQL_LOGGING": True,
        "SQL_LOG_LEVEL": "DEBUG",
        "QUERY_WARNINGS": True,
        "QUERY_WARNING_THRESHOLD": 100,  # ms
        "PROFILE_REQUESTS": False,
    },
}
```

---

## Related Documentation

- [CLI Overview](index.md)
- [Commands](commands.md)
- [AI Commands](ai-commands.md)
- [Debugging](../debugging/index.md)
