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

Apply database migrations.

```bash
aksara migrate [app] [migration] [options]
```

**Arguments:**
- `app` — App name (optional)
- `migration` — Target migration name/number (optional)

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--fake` | Mark as applied without running | `false` |
| `--fake-initial` | Fake initial migrations if tables exist | `false` |
| `--plan` | Show migration plan | `false` |
| `--database` | Database alias | `default` |

**Examples:**
```bash
# Apply all pending migrations
aksara migrate

# Migrate specific app
aksara migrate blog

# Migrate to specific version
aksara migrate blog 0003

# Rollback to zero
aksara migrate blog zero

# Show plan without applying
aksara migrate --plan
```

---

### dbshell

Open database shell.

```bash
aksara dbshell [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--database` | Database alias | `default` |

Opens the appropriate shell for your database (psql, mysql, sqlite3).

---

### inspectdb

Generate models from existing database tables.

```bash
aksara inspectdb [table ...] [options]
```

**Arguments:**
- `table` — Specific tables (optional, default: all)

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--database` | Database alias | `default` |
| `--include-views` | Include views | `false` |

**Example:**
```bash
aksara inspectdb users posts > models.py
```

---

## Development Commands

### run

Start the development server.

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
| `--ipython` | Use IPython | Auto-detect |
| `--bpython` | Use bpython | Auto-detect |
| `--plain` | Use plain Python | `false` |
| `--command`, `-c` | Execute command | None |

**Examples:**
```bash
# Interactive shell
aksara shell

# Execute command
aksara shell -c "print(await User.objects.count())"
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
| `--filter` | Filter by pattern | None |

**Example:**
```bash
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
| `--format`, `-f` | Output format (text, json) | `text` |
| `--check` | Run health checks | `false` |

**Example:**
```bash
aksara info --check
```

---

### check

Validate project configuration.

```bash
aksara check [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--fail-level` | Min severity to fail | `error` |
| `--deploy` | Check deployment settings | `false` |

**Example:**
```bash
aksara check --deploy
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

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--verbose`, `-v` | Verbose output | `false` |
| `--failfast`, `-x` | Stop on first failure | `false` |
| `--parallel`, `-n` | Parallel test count | `1` |
| `--coverage` | Enable coverage | `false` |

**Examples:**
```bash
# All tests
aksara test

# Specific file
aksara test tests/test_models.py

# With coverage
aksara test --coverage
```

---

## Static Files Commands

### collectstatic

Collect static files.

```bash
aksara collectstatic [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--no-input` | Don't prompt | `false` |
| `--clear` | Clear existing | `false` |
| `--dry-run` | Preview only | `false` |

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
| `--email` | User email | Prompt |
| `--password` | User password | Prompt |
| `--no-input` | Use defaults | `false` |

---

### changepassword

Change user password.

```bash
aksara changepassword <email>
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

## Global Options

These options work with all commands:

| Option | Description |
|--------|-------------|
| `--help` | Show help |
| `--version` | Show version |
| `--settings` | Settings module |
| `--verbose` | Verbose output |
| `--quiet` | Suppress output |
| `--no-color` | Disable colors |

**Example:**
```bash
aksara --settings myproject.settings migrate
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
