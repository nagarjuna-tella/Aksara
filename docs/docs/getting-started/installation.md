# Installation

This guide covers installing Vidyut and its dependencies.

---

## Requirements

| Dependency | Version | Notes |
|------------|---------|-------|
| Python | 3.11+ | Required for modern async features |
| PostgreSQL | 13+ | Vidyut is PostgreSQL-only |
| asyncpg | 0.29+ | Async PostgreSQL driver (auto-installed) |
| FastAPI | 0.104+ | Web framework (auto-installed) |
| Pydantic | 2.0+ | Data validation (auto-installed) |

---

## Install Vidyut

### Using pip

```bash
pip install vidyut
```

### Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package installer:

```bash
uv pip install vidyut
```

### Using Poetry

```bash
poetry add vidyut
```

### From Source

For development or the latest unreleased features:

```bash
git clone https://github.com/vidyut-orm/vidyut.git
cd vidyut
pip install -e ".[dev]"
```

---

## Verify Installation

After installation, verify Vidyut is available:

```bash
vidyut --version
```

Expected output:
```
vidyut, version 0.4.9
```

You can also check the Python package:

```python
>>> import vidyut
>>> vidyut.__version__
'0.4.9'
```

---

## Install Development Dependencies

For development, testing, and code quality tools:

```bash
pip install vidyut[dev]
```

This includes:

| Package | Purpose |
|---------|---------|
| pytest | Testing framework |
| pytest-asyncio | Async test support |
| httpx | HTTP client for testing |
| black | Code formatting |
| ruff | Fast linting |
| mypy | Type checking |
| pre-commit | Git hooks |

---

## PostgreSQL Setup

Vidyut requires PostgreSQL. Here are common setup methods:

### macOS (Homebrew)

```bash
brew install postgresql@15
brew services start postgresql@15
createdb myapp
```

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo -u postgres createdb myapp
```

### Docker

```bash
docker run -d \
  --name vidyut-postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=myapp \
  -p 5432:5432 \
  postgres:15
```

### Connection String Format

Vidyut uses standard PostgreSQL connection strings:

```
postgresql://user:password@host:port/database
```

Examples:
```bash
# Local with default user
postgresql://localhost/myapp

# With credentials
postgresql://postgres:password@localhost:5432/myapp

# Remote server
postgresql://user:secret@db.example.com:5432/production
```

---

## Environment Variables

Vidyut reads configuration from environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | None |
| `VIDYUT_DATABASE_URL` | Alternative DB URL (higher priority) | None |
| `VIDYUT_DEBUG` | Enable debug mode | `false` |
| `VIDYUT_LOG_LEVEL` | Logging level | `INFO` |
| `VIDYUT_POOL_MIN_SIZE` | Min connection pool size | `5` |
| `VIDYUT_POOL_MAX_SIZE` | Max connection pool size | `20` |

Create a `.env` file in your project root:

```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/myapp
VIDYUT_DEBUG=true
VIDYUT_LOG_LEVEL=DEBUG
```

---

## IDE Setup

### VS Code

Install the Python extension and add to `.vscode/settings.json`:

```json
{
    "python.analysis.typeCheckingMode": "basic",
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter"
    }
}
```

### PyCharm

1. Open Settings → Project → Python Interpreter
2. Add your virtual environment
3. Enable Django-style support for similar patterns

---

## Troubleshooting

### `asyncpg` Installation Issues

On some systems, you may need PostgreSQL development headers:

=== "macOS"

    ```bash
    brew install postgresql
    ```

=== "Ubuntu/Debian"

    ```bash
    sudo apt install libpq-dev python3-dev
    ```

=== "Windows"

    Use pre-built wheels:
    ```bash
    pip install asyncpg --only-binary=:all:
    ```

### Connection Refused

If you see "connection refused" errors:

1. Ensure PostgreSQL is running:
   ```bash
   pg_isready -h localhost -p 5432
   ```

2. Check your connection string format

3. Verify credentials and database exists

### Import Errors

If imports fail after installation:

```bash
# Ensure you're using the correct Python
which python
pip show vidyut

# Reinstall if needed
pip uninstall vidyut
pip install vidyut
```

---

## Next Steps

With Vidyut installed, proceed to:

- [Project Layout](project-layout.md) — Understand the recommended structure
- [Settings](settings.md) — Configure your application
- [First App](first-app.md) — Build your first Vidyut application
