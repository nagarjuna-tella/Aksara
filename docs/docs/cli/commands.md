# CLI Commands Reference

Complete reference for all Aksara CLI commands.

---

## Project Commands

### startproject

Create a new Aksara project.

```bash
aksara startproject <name> [options]
```

**Arguments:**
- `name` — Project name (required)

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--directory`, `-d` | Target directory | Current directory |
| `--template`, `-t` | Project template | `standard` |

**Templates:**
- `minimal` — Minimal setup (settings + app)
- `standard` — Standard setup with tests
- `full` — Full setup with admin, API, tests

**Example:**
```bash
aksara startproject myblog --template full
```

---

### startapp

Create a new app within a project.

```bash
aksara startapp <name> [options]
```

**Arguments:**
- `name` — App name (required)

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--directory`, `-d` | Target directory | Current directory |

**Example:**
```bash
aksara startapp blog
```

---

## Database Commands

### dbsetup

Interactively set up a PostgreSQL database for the current project.

```bash
aksara dbsetup [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--host` | PostgreSQL host | `localhost` |
| `--port` | PostgreSQL port | `5432` |

Checks for PostgreSQL, prompts for database name, username, and password, tests the connection, creates the database if needed, and writes `DATABASE_URL` to `.env`.

**Examples:**
```bash
# Default (localhost:5432)
aksara dbsetup

# Custom host and port
aksara dbsetup --host db.example.com --port 5433
```

---

### makemigrations

Generate migrations from model changes.

```bash
aksara makemigrations [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--app`, `-a` | Specific app | All apps |
| `--name`, `-n` | Migration name | Auto-generated |
| `--empty` | Create empty migration | `false` |
| `--dry-run` | Preview without creating | `false` |
| `--check` | Exit non-zero if changes needed | `false` |

**Examples:**
```bash
# All apps
aksara makemigrations

# Specific app with custom name
aksara makemigrations --app blog --name add_post_views

# Check for pending changes (useful in CI)
aksara makemigrations --check
```

---

### migrate

Apply database migrations from the project-wide `migrations/` directory.

```bash
aksara migrate [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--app`, `-a` | Models module to discover | auto |
| `--database-url`, `-d` | PostgreSQL connection URL | `DATABASE_URL` env |
| `--migrations-dir`, `-m` | Migrations directory | `./migrations` |
| `--dry-run` | Preview without applying | `false` |
| `--fake` | Mark as applied without running | `false` |

**Examples:**
```bash
# Apply all pending migrations
aksara migrate

# Preview what would be applied
aksara migrate --dry-run

# Mark as applied without running SQL
aksara migrate --fake

# Use a custom migrations directory
aksara migrate --migrations-dir custom_migrations
```

**Behavior:**

- Migrations are applied through the canonical migration executor.
- Each migration runs inside a transaction; a failed migration rolls back and is
  not recorded as applied.
- A PostgreSQL advisory lock prevents two runners from migrating concurrently.
- Already-applied migrations are skipped. Their checksums are verified first, and
  a mismatch (an applied migration was edited) fails the run with a clear message.
- Migrations recorded before checksums existed may warn but are not rejected.
- If a migration fails, the pending migrations that were skipped are reported.

`--dry-run` only previews; it does not apply migrations. See
[Migration Safety](../orm/migration-safety.md) for details.

---

### status

Show migration status.

```bash
aksara status [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--database-url`, `-d` | PostgreSQL connection URL | `DATABASE_URL` env |

**Examples:**
```bash
aksara status
aksara status --database-url postgresql://postgres:password@localhost:5432/myapp
```

---

## Development Commands

### dev

Preferred development server for local work.

```bash
aksara dev [APP_PATH] [options]
```

**Arguments:**
- `APP_PATH` — Import path to the app (optional, default: `main:app`)

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--host`, `-h` | Host to bind | `127.0.0.1` |
| `--port`, `-p` | Port to bind | `8000` |
| `--reload`, `-r` | Enable auto-reload | `true` |
| `--no-reload` | Disable auto-reload | `false` |
| `--log-level`, `-l` | Uvicorn log level | `info` |

**Examples:**
```bash
aksara dev
aksara dev --port 3000
aksara dev myproject.main:app --log-level debug
aksara run dev  # alias
```

---

### run

Start a specific ASGI app path directly.

```bash
aksara run APP_PATH [options]
```

**Arguments:**
- `APP_PATH` — Import path to the app (e.g., 'main:app')

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--host`, `-h` | Host to bind | `127.0.0.1` |
| `--port`, `-p` | Port to bind | `8000` |
| `--reload` / `--no-reload` | Auto-reload on changes | `--reload` |
| `--workers`, `-w` | Number of workers | `1` |

**Examples:**
```bash
# Default
aksara run main:app

# Custom port
aksara run main:app --port 3000

# All interfaces
aksara run main:app --host 0.0.0.0

# Production-like (multiple workers)
aksara run myproject.main:app --workers 4
```

---

### shell

Interactive Python shell with project context.

```bash
aksara shell [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--database-url`, `-d` | PostgreSQL connection URL | `DATABASE_URL` env |
| `--no-ipython` | Disable IPython even if available | `false` |
| `--bpython` | Use BPython instead of IPython | `false` |
| `--command`, `-c` | Execute a Python command and exit | None |

**Examples:**
```bash
# Interactive shell
aksara shell

# Use an explicit database URL
aksara shell --database-url postgresql://postgres:password@localhost:5432/myapp

# Force the standard Python shell
aksara shell --no-ipython

# Execute a one-liner
aksara shell -c "print(await User.objects.count())"
```

> **Note:** `--bpython` and `--command` / `-c` are planned and not yet available in the current release.

---

### dbshell

> **Planned** — not yet available.

Open a raw `psql` session connected to the project database.

```bash
aksara dbshell
aksara dbshell --database-url postgresql://postgres:password@localhost:5432/mydb
```

---

### inspectdb

> **Planned** — not yet available.

Generate Aksara model definitions by introspecting an existing PostgreSQL schema.

```bash
aksara inspectdb
aksara inspectdb --schema public --output models_generated.py
```

---

### routes

List registered routes.

```bash
aksara routes [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--format`, `-f` | Output format (table, json) | `table` |
| `--filter` | Filter routes by path pattern | None |
| `--method` | Filter routes by HTTP method | None |

> **Note:** `--filter` and `--method` are planned and not yet available in the current release.

**Example:**
```bash
aksara routes
aksara routes --format json
aksara routes --filter api/posts
```

---

### info

Show project information.

```bash
aksara info [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--database-url`, `-d` | PostgreSQL connection URL | `DATABASE_URL` env |

**Example:**
```bash
aksara info
aksara info --database-url postgresql://postgres:password@localhost:5432/myapp
```

---

### models

List registered models.

```bash
aksara models [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--app`, `-a` | Application models module to import | None |
| `--ai` | Show AI metadata for models and fields | `false` |
| `--detail` | Show detailed field information | `false` |

> **Note:** `--detail` is planned and not yet available in the current release.

**Example:**
```bash
aksara models
aksara models --app blog.models --ai
```

---

## Testing Commands

### test

Run the test suite.

```bash
aksara test [path] [options]
```

**Arguments:**
- `path` — Test path (optional)

Any extra arguments are passed through to pytest.

**Common flags (passed to pytest):**

| Flag | Description |
|------|-------------|
| `-v` / `--verbose` | Verbose output |
| `--failfast` | Stop on first failure |
| `--parallel` | Run tests in parallel (requires `pytest-xdist`) |
| `--coverage` / `--cov` | Measure coverage (requires `pytest-cov`) |
| `-k EXPRESSION` | Filter tests by name expression |
| `--tb=short` | Shorter traceback format |

**Examples:**
```bash
# All tests
aksara test

# Specific file
aksara test tests/test_models.py

# Pytest passthrough arguments
aksara test -v --tb=short
aksara test tests/test_models.py -k "test_create"
aksara test --failfast
aksara test --parallel
```

---

## Static Files Commands

### collectstatic

Collect static files.

```bash
aksara collectstatic [options]
```

Creates missing project static assets such as `static/welcome.html`. This also runs automatically before `aksara dev` and `aksara run`.

**Options:**

| Option | Description |
|--------|-------------|
| `--no-input` | Skip confirmation prompts |
| `--clear` | Delete existing static files before collecting |
| `--dry-run` | Show what would be collected without writing files |

> **Note:** `--no-input`, `--clear`, and `--dry-run` are planned and not yet available in the current release.

---

## User Commands

### createsuperuser

Create an admin user.

```bash
aksara createsuperuser [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--database-url`, `-d` | PostgreSQL connection URL | `DATABASE_URL` env |
| `--email`, `-e` | User email | Prompt |
| `--password`, `-p` | User password | Prompt |
| `--no-input` | Use provided values without interactive prompts | `false` |
| `--username` | Username (if username-based auth is enabled) | None |

> **Note:** `--no-input` and `--username` are planned and not yet available in the current release.

**Examples:**
```bash
aksara createsuperuser
aksara createsuperuser --email admin@example.com
```

---

### changepassword

> **Planned** — not yet available.

Change the password for an existing user.

```bash
aksara changepassword <email>
```

---

## Project Validation & Settings Commands

### check

> **Planned** — not yet available.

Validate the project configuration and run system checks.

```bash
aksara check
aksara check --deploy  # stricter production checks
```

**Example output:**

```
⚡ Aksara System Check

  ✓ Database connection OK
  ✓ Migrations up to date
  ✓ Settings valid
  ✓ Admin configured
  ✓ Static files present

  0 issues found.
```

With `--deploy`, additional production checks are run (e.g. `DEBUG=False`, `SECRET_KEY` strength, HTTPS settings).

---

### settings

> **Planned** — not yet available.

Display the current project settings.

```bash
aksara settings
aksara settings --setting DATABASE_URL
```

---

## Watch & Automation

### watch

> **Planned** — not yet available.

Watch for file changes and re-run tests automatically.

```bash
aksara watch
aksara watch tests/
```

---

## Data Commands

### dumpdata

> **Planned** — not yet available.

Export database content to a JSON or YAML fixture file.

```bash
aksara dumpdata
aksara dumpdata blog --output blog_fixture.json
aksara dumpdata --all --format yaml
```

---

### loaddata

> **Planned** — not yet available.

Load fixture data into the database.

```bash
aksara loaddata fixtures.json
aksara loaddata blog_fixture.yaml
```

---

## AI Commands

See [AI Commands](ai-commands.md) for details.

| Command | Description |
|---------|-------------|
| `aksara ai query` | Natural language queries |
| `aksara ai generate` | Code generation |
| `aksara ai doctor` | Schema analysis |
| `aksara ai plan` | Task planning |
| `aksara ai agent` | AI agent execution |

---

## Launch Commands

| Command | Description |
|---------|-------------|
| `aksara doctor launch-check` | First-user launch readiness check |
| `aksara doctor launch-check --format json` | Pure JSON launch readiness report |
| `aksara examples validate` | Validate bundled golden-path examples |
| `aksara examples validate --format json` | Pure JSON examples validation report |

---

## Global Options

These options work with all commands and **must be placed before the subcommand**:

| Option | Description |
|--------|-------------|
| `--help` | Show help |
| `--version` | Show version |
| `--quiet` | Suppress non-error Aksara UI output |
| `--plain` | Disable Rich rendering and animations |
| `--no-color` | Disable ANSI color |
| `--force-color` | Force ANSI color when supported |
| `--settings PATH` | Settings module path (planned) |
| `--pythonpath PATH` | Add a path to `sys.path` (planned) |
| `--verbose` | Increase verbosity (planned) |

> **Note:** `--settings`, `--pythonpath`, and `--verbose` are planned and not yet available. Use the `AKSARA_SETTINGS` environment variable to point to a custom settings module.

**Example:**
```bash
aksara --quiet migrate
aksara --plain dev
aksara --no-color info
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `AKSARA_SETTINGS` | Settings module path |
| `AKSARA_DEBUG` | Enable debug mode |
| `DATABASE_URL` | Database connection URL |

---

## Related Documentation

- [CLI Overview](index.md)
- [Dev Tools](dev-tools.md)
- [AI Commands](ai-commands.md)
