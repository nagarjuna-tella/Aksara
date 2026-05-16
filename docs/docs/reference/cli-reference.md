# CLI Reference

Complete reference for Aksara CLI commands.

---

## Usage

```bash
aksara [OPTIONS] COMMAND [ARGS]...
```

### Global Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message |
| `--version` | Show version |
| `--quiet` | Suppress non-error Aksara UI output |
| `--plain` | Disable Rich rendering and animations |
| `--no-color` | Disable colored terminal output |
| `--force-color` | Force colored output when supported |
| `--settings PATH` | Settings module path *(planned)* |
| `--pythonpath PATH` | Add a path to `sys.path` *(planned)* |
| `--verbose` | Increase output verbosity *(planned)* |

Global output flags must be placed before the subcommand. Examples: `aksara --quiet migrate`, `aksara --plain dev`, `aksara --no-color info`.

> **Note:** `--settings`, `--pythonpath`, and `--verbose` are planned. Use the `AKSARA_SETTINGS` environment variable in the meantime.

---

## Project Commands

### startproject

Create a new Aksara project.

```bash
aksara startproject NAME [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--directory DIR` | Target directory |
| `--template TEMPLATE` | Project template |

**Example:**

```bash
aksara startproject myproject
aksara startproject myproject --directory /path/to/dir
```

### startapp

Create a new application.

```bash
aksara startapp NAME [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--directory DIR` | Target directory |

**Example:**

```bash
aksara startapp users
aksara startapp blog --directory apps/
```

---

## Database Commands

### makemigrations

Create new migrations.

```bash
aksara makemigrations [APP] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--name NAME` | Migration name |
| `--empty` | Create empty migration |
| `--check` | Check only, don't create |
| `--dry-run` | Show without creating |

**Example:**

```bash
aksara makemigrations
aksara makemigrations users --name add_bio_field
aksara makemigrations --check
```

### migrate

Apply migrations from the project-wide `migrations/` directory.

```bash
aksara migrate [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--database-url`, `-d` | PostgreSQL connection URL |
| `--migrations-dir`, `-m` | Migrations directory (default: `./migrations`) |
| `--dry-run` | Preview without applying |
| `--fake` | Mark as applied without running |

**Example:**

```bash
aksara migrate
aksara migrate --dry-run
aksara migrate --fake
aksara migrate --migrations-dir custom_migrations
```

### status

Show migration status.

```bash
aksara status [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--database-url`, `-d` | PostgreSQL connection URL |

**Example:**

```bash
aksara status
aksara status --database-url postgresql://postgres:password@localhost:5432/myapp
```

---

## Server Commands

### dev

Start the preferred local development server with the Aksara hero banner.

```bash
aksara dev [APP_PATH] [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host HOST` | `127.0.0.1` | Bind host |
| `--port PORT` | `8000` | Bind port |
| `--reload` | True | Enable auto-reload |
| `--no-reload` | False | Disable auto-reload |
| `--log-level LEVEL` | `info` | Uvicorn log level |

**Example:**

```bash
aksara dev
aksara dev myproject.main:app --log-level debug
aksara dev --no-reload --port 3000
aksara run dev
```

### run

Start a specific ASGI app path directly.

```bash
aksara run APP_PATH [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host HOST` | `127.0.0.1` | Bind host |
| `--port PORT` | `8000` | Bind port |
| `--reload` | True | Auto-reload |
| `--workers N` | `1` | Worker count |

**Example:**

```bash
aksara run main:app
aksara run main:app --port 3000
aksara run main:app --host 0.0.0.0 --port 8080
aksara run myproject.main:app --reload
```

---

## Shell Commands

### shell

Start interactive Python shell.

```bash
aksara shell [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--database-url`, `-d` | PostgreSQL connection URL |
| `--no-ipython` | Disable IPython even if available |
| `--bpython` | Use BPython instead of IPython *(planned)* |
| `--command`, `-c` | Execute a Python command and exit *(planned)* |

**Example:**

```bash
aksara shell
aksara shell --database-url postgresql://postgres:password@localhost:5432/myapp
aksara shell --no-ipython
```

### dbshell

> **Planned** — not yet available.

```bash
aksara dbshell [OPTIONS]
```

Open a raw `psql` session connected to the project database.

### inspectdb

> **Planned** — not yet available.

```bash
aksara inspectdb [OPTIONS]
```

Generate Aksara model definitions by introspecting an existing PostgreSQL schema.

---

## Utility Commands

### routes

List all routes.

```bash
aksara routes [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--format FMT` | Output format (table, json) |
| `--filter PATTERN` | Filter routes by path pattern *(planned)* |
| `--method METHOD` | Filter routes by HTTP method *(planned)* |

**Example:**

```bash
aksara routes
aksara routes --format json
```

**Output:**

```
Method  Path                    Name                Handler
------  ----------------------  ------------------  ----------------------
GET     /api/users/             users-list          UserViewSet.list
POST    /api/users/             users-create        UserViewSet.create
GET     /api/users/{id}/        users-detail        UserViewSet.retrieve
PUT     /api/users/{id}/        users-update        UserViewSet.update
DELETE  /api/users/{id}/        users-delete        UserViewSet.destroy
```

### info

Show project information.

```bash
aksara info [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--database-url`, `-d` | PostgreSQL connection URL |

**Output:**

```
Aksara Project Information
==========================
Version: 0.5.46
Python: 3.11.0
Settings: myproject.settings

Database: postgresql://localhost/myproject
Apps: users, posts, comments

Models:
  - users.User
  - users.Profile
  - posts.Post
  - posts.Comment
```

### models

List registered models.

```bash
aksara models [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--app APP` | Application models module to import |
| `--ai` | Show AI metadata |
| `--detail` | Show detailed field definitions *(planned)* |

**Example:**

```bash
aksara models
aksara models --app blog.models --ai
```

### test

Run tests.

```bash
aksara test [PATH] [OPTIONS]
```

Additional arguments are passed through to pytest.

| Flag | Description |
|------|-------------|
| `-v` / `--verbose` | Verbose output |
| `--failfast` | Stop on first failure |
| `--parallel` | Run in parallel (requires `pytest-xdist`) |
| `--cov` / `--coverage` | Measure coverage (requires `pytest-cov`) |
| `-k EXPRESSION` | Filter by name expression |
| `--tb=short` | Shorter tracebacks |

**Example:**

```bash
aksara test
aksara test tests/test_users.py
aksara test -v --tb=short
aksara test -k "test_create"
aksara test --failfast
aksara test --parallel
```

### collectstatic

Collect static files.

```bash
aksara collectstatic [OPTIONS]
```

Creates missing project static assets such as `static/welcome.html`. This also runs automatically before `aksara dev` and `aksara run`.

| Option | Description |
|--------|-------------|
| `--no-input` | Skip confirmation prompts *(planned)* |
| `--clear` | Delete existing static files first *(planned)* |
| `--dry-run` | Preview without writing files *(planned)* |

---

### check

> **Planned** — not yet available.

```bash
aksara check [OPTIONS]
```

Validate the project configuration and run system checks.

| Option | Description |
|--------|-------------|
| `--deploy` | Run stricter production-safety checks |

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

### settings

> **Planned** — not yet available.

```bash
aksara settings [OPTIONS]
```

Display the current project settings.

| Option | Description |
|--------|-------------|
| `--setting NAME` | Show only the specified setting |

---

## Watch & Automation

### watch

> **Planned** — not yet available.

```bash
aksara watch [PATH]
```

Watch for file changes and re-run tests automatically.

---

## Data Commands

### dumpdata

> **Planned** — not yet available.

```bash
aksara dumpdata [APP] [OPTIONS]
```

Export database content to a fixture file.

| Option | Description |
|--------|-------------|
| `--output FILE` | Output file path |
| `--format FMT` | Output format (json, yaml) |
| `--all` | Include all apps |
| `--indent N` | JSON indentation |

### loaddata

> **Planned** — not yet available.

```bash
aksara loaddata FIXTURE [OPTIONS]
```

Load fixture data into the database.

---

## Auth Commands

### createsuperuser

Create admin user.

```bash
aksara createsuperuser [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--database-url`, `-d` | PostgreSQL connection URL |
| `--email EMAIL`, `-e` | User email |
| `--password PASSWORD`, `-p` | User password |
| `--no-input` | Use provided values without prompts *(planned)* |
| `--username USERNAME` | Username for username-based auth *(planned)* |

**Example:**

```bash
aksara createsuperuser
aksara createsuperuser --email admin@example.com
```

### changepassword

> **Planned** — not yet available.

```bash
aksara changepassword <email>
```

Change the password for an existing user.

---

## AI Commands

### ai query

Query data with natural language.

```bash
aksara ai query "QUERY" [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--output FMT` | Output format (table, json, csv) |
| `--limit N` | Result limit |

**Example:**

```bash
aksara ai query "Show all active users"
aksara ai query "Posts created this week" --output json
```

### ai generate

Generate code.

```bash
aksara ai generate TYPE DESCRIPTION [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--output FILE` | Output file |
| `--preview` | Preview only |

**Example:**

```bash
aksara ai generate model "User with email, name, role"
aksara ai generate viewset User
aksara ai generate test User --output tests/test_users.py
```

### ai doctor

Analyze schema for issues.

```bash
aksara ai doctor [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--fix` | Auto-fix issues |
| `--interactive` | Confirm each fix |

**Example:**

```bash
aksara ai doctor
aksara ai doctor --fix --interactive
```

### ai plan

Plan complex tasks.

```bash
aksara ai plan "TASK" [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--execute` | Execute the plan |
| `--preview` | Preview only |

**Example:**

```bash
aksara ai plan "Add user profile feature with avatar upload"
aksara ai plan "Refactor auth to use JWT" --preview
```

### ai agent

Run AI agent.

```bash
aksara ai agent "TASK" [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--tools TOOLS` | Allowed tools (comma-separated) |
| `--max-steps N` | Maximum steps |

**Example:**

```bash
aksara ai agent "Analyze the codebase and suggest improvements"
aksara ai agent "Fix failing tests" --max-steps 10
```

### ai patch

Apply code changes.

```bash
aksara ai patch "CHANGE" [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--preview` | Preview changes |
| `--dry-run` | Don't apply |

**Example:**

```bash
aksara ai patch "Add logging to all viewsets" --preview
```

### ai ask

Ask questions about the codebase.

```bash
aksara ai ask "QUESTION"
```

**Example:**

```bash
aksara ai ask "How is authentication implemented?"
aksara ai ask "What models have soft delete?"
```

### ai config

Configure AI settings.

```bash
aksara ai config [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--provider NAME` | Set provider |
| `--model NAME` | Set model |
| `--show` | Show current config |

**Example:**

```bash
aksara ai config --show
aksara ai config --provider openai --model gpt-4
```

---

## Task Queue Commands

### tasks stats

Show task queue counts grouped by status and queue.

```bash
aksara tasks stats
```

**Example output:**

```
  Queue: default
    pending          3
    running          1
    completed      412
    failed           2

  Queue: emails
    pending          0
    running          0
    completed       87
    failed           1

  Total
    pending          3
    running          1
    completed      499
    failed           3
```

### tasks list

List task records. Defaults to showing `failed` tasks.

```bash
aksara tasks list [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--status`, `-s` | `failed` | Filter by status (`pending`, `running`, `completed`, `failed`) |
| `--queue`, `-q` | — | Filter by queue name |
| `--task-name`, `-t` | — | Substring match on `task_name` |
| `--limit`, `-n` | `20` | Maximum rows returned |

**Examples:**

```bash
aksara tasks list
aksara tasks list --status pending
aksara tasks list --status failed --queue emails --limit 50
aksara tasks list --task-name send_welcome
```

### tasks reenqueue

Re-enqueue a failed task by ID, or all failed tasks at once.
Re-enqueuing resets `attempts`, `locked_at`, `last_error`, and `available_at`
so the task is treated as brand-new.

```bash
aksara tasks reenqueue [TASK_ID] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--all` | Re-enqueue all failed tasks |
| `--queue`, `-q` | Filter by queue when using `--all` |
| `--yes`, `-y` | Skip confirmation prompt |

**Examples:**

```bash
aksara tasks reenqueue 3f2a1c4e-...          # one task by UUID
aksara tasks reenqueue --all                  # all failed tasks
aksara tasks reenqueue --all --queue emails
aksara tasks reenqueue --all --yes            # skip confirmation
```

### tasks purge

Delete old task records from the database.

```bash
aksara tasks purge [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--status`, `-s` | `completed` | Status(es) to purge (repeatable) |
| `--older-than-days`, `-d` | `7` | Delete rows last updated more than N days ago |
| `--yes`, `-y` | — | Skip confirmation prompt |

**Examples:**

```bash
aksara tasks purge                                           # completed, >7 days
aksara tasks purge --status failed --older-than-days 30
aksara tasks purge --status completed --status failed -d 1 --yes
```

---

## Custom Commands

### Creating Commands

```python
# myapp/management/commands/mycommand.py
from aksara.cli import Command, argument, option

class MyCommand(Command):
    """Description of my command."""
    
    name = "mycommand"
    
    @argument("name", help="The name argument")
    @option("--count", "-c", default=1, help="Count option")
    async def handle(self, name: str, count: int):
        for i in range(count):
            self.output(f"Hello, {name}!")
```

### Running Custom Commands

```bash
aksara mycommand World --count 3
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `AKSARA_SETTINGS_MODULE` | Settings module path |
| `AKSARA_DEBUG` | Enable debug mode |
| `DATABASE_URL` | Database connection URL |

---

## Exit Codes

| Code | Description |
|------|-------------|
| `0` | Success |
| `1` | General error |
| `2` | Command not found |
| `3` | Invalid arguments |

---

## Related Documentation

- [CLI Guide](../cli/index.md)
- [Commands](../cli/commands.md)
- [Dev Tools](../cli/dev-tools.md)
