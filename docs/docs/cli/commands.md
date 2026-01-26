# CLI Commands Reference

Complete reference for all Vidyut CLI commands.

---

## Project Commands

### startproject

Create a new Vidyut project.

```bash
vidyut startproject <name> [options]
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
vidyut startproject myblog --template full
```

---

### startapp

Create a new app within a project.

```bash
vidyut startapp <name> [options]
```

**Arguments:**
- `name` — App name (required)

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--directory`, `-d` | Target directory | Current directory |

**Example:**
```bash
vidyut startapp blog
```

---

## Database Commands

### makemigrations

Generate migrations from model changes.

```bash
vidyut makemigrations [options]
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
vidyut makemigrations

# Specific app with custom name
vidyut makemigrations --app blog --name add_post_views

# Check for pending changes (useful in CI)
vidyut makemigrations --check
```

---

### migrate

Apply database migrations.

```bash
vidyut migrate [app] [migration] [options]
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
vidyut migrate

# Migrate specific app
vidyut migrate blog

# Migrate to specific version
vidyut migrate blog 0003

# Rollback to zero
vidyut migrate blog zero

# Show plan without applying
vidyut migrate --plan
```

---

### dbshell

Open database shell.

```bash
vidyut dbshell [options]
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
vidyut inspectdb [table ...] [options]
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
vidyut inspectdb users posts > models.py
```

---

## Development Commands

### runserver

Start the development server.

```bash
vidyut runserver [address] [options]
```

**Arguments:**
- `address` — Host:port (optional)

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
vidyut runserver

# Custom port
vidyut runserver --port 3000

# All interfaces
vidyut runserver --host 0.0.0.0

# Production-like (no reload, multiple workers)
vidyut runserver --no-reload --workers 4
```

---

### shell

Interactive Python shell with project context.

```bash
vidyut shell [options]
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
vidyut shell

# Execute command
vidyut shell -c "print(await User.objects.count())"
```

---

### routes

List registered routes.

```bash
vidyut routes [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--format`, `-f` | Output format (table, json) | `table` |
| `--filter` | Filter by pattern | None |

**Example:**
```bash
vidyut routes --filter api/posts
```

---

### info

Show project information.

```bash
vidyut info [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--format`, `-f` | Output format (text, json) | `text` |
| `--check` | Run health checks | `false` |

**Example:**
```bash
vidyut info --check
```

---

### check

Validate project configuration.

```bash
vidyut check [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--fail-level` | Min severity to fail | `error` |
| `--deploy` | Check deployment settings | `false` |

**Example:**
```bash
vidyut check --deploy
```

---

## Testing Commands

### test

Run the test suite.

```bash
vidyut test [path] [options]
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
vidyut test

# Specific file
vidyut test tests/test_models.py

# With coverage
vidyut test --coverage
```

---

## Static Files Commands

### collectstatic

Collect static files.

```bash
vidyut collectstatic [options]
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
vidyut createsuperuser [options]
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
vidyut changepassword <email>
```

---

## AI Commands

See [AI Commands](ai-commands.md) for details.

| Command | Description |
|---------|-------------|
| `vidyut ai query` | Natural language queries |
| `vidyut ai generate` | Code generation |
| `vidyut ai doctor` | Schema analysis |
| `vidyut ai plan` | Task planning |
| `vidyut ai agent` | AI agent execution |

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
vidyut --settings myproject.settings migrate
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VIDYUT_SETTINGS` | Settings module path |
| `VIDYUT_DEBUG` | Enable debug mode |
| `DATABASE_URL` | Database connection URL |

---

## Related Documentation

- [CLI Overview](index.md)
- [Dev Tools](dev-tools.md)
- [AI Commands](ai-commands.md)
