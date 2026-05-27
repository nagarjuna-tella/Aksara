# Installation

This guide covers installing Aksara and its dependencies.

---

## Requirements

| Dependency | Version | Notes |
|------------|---------|-------|
| Python | 3.11+ | Required for modern async features |
| PostgreSQL | 13+ | Aksara is PostgreSQL-only |
| asyncpg | 0.29+ | Async PostgreSQL driver (auto-installed) |
| FastAPI | 0.104+ | Web framework (auto-installed) |
| Pydantic | 2.0+ | Data validation (auto-installed) |

---

## Install Aksara

### Using pip

```bash
pip install aksara-framework
```

### Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package installer:

```bash
uv pip install aksara-framework
```

### Using Poetry

```bash
poetry add aksara-framework
```

### From Source

For development or the latest unreleased features:

```bash
git clone https://github.com/nagarjuna-tella/Aksara.git
cd aksara
pip install -e ".[dev]"
```

---

## Verify Installation

After installation, verify Aksara is available:

```bash
aksara --version
```

Expected output:
```
aksara, version 0.5.50
```

You can also check the Python package:

```python
>>> import aksara
>>> aksara.__version__
'0.5.50'
```

For a project-level readiness check, run this from inside an Aksara project:

```bash
aksara doctor launch-check
```

The JSON form is useful for CI or support reports:

```bash
aksara doctor launch-check --format json
```

---

## Install Development Dependencies

For development, testing, and code quality tools:

```bash
pip install aksara-framework[dev]
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

Aksara requires PostgreSQL. Here are common setup methods:

### macOS (Homebrew)

```bash
brew install postgresql@15
brew services start postgresql@15
```

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### Docker

```bash
docker run -d \
  --name aksara-postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=myapp \
  -p 5432:5432 \
  postgres:15
```

### Connection String Format

Aksara uses standard PostgreSQL connection strings:

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

Aksara reads configuration from environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | None |
| `AKSARA_DATABASE_URL` | Alternative DB URL (higher priority) | None |
| `AKSARA_DEBUG` | Enable debug mode | `false` |
| `AKSARA_LOG_LEVEL` | Logging level | `INFO` |
| `AKSARA_POOL_MIN_SIZE` | Min connection pool size | `5` |
| `AKSARA_POOL_MAX_SIZE` | Max connection pool size | `20` |

Create a `.env` file in your project root:

```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/myapp
AKSARA_DEBUG=true
AKSARA_LOG_LEVEL=DEBUG
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
pip show aksara

# Reinstall if needed
pip uninstall aksara
pip install aksara-framework
```

---

## Next Steps

With Aksara installed, proceed to:

- [Project Layout](project-layout.md) — Understand the recommended structure
- [Settings](settings.md) — Configure your application
- [First App](first-app.md) — Build your first Aksara application
