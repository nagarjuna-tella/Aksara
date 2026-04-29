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
| `--settings PATH` | Settings module path |
| `--pythonpath PATH` | Add to Python path |

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

### dbshell

Open database shell.

```bash
aksara dbshell [OPTIONS]
```

**Example:**

```bash
aksara dbshell
```

### inspectdb

Generate models from existing database.

```bash
aksara inspectdb [TABLE] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--output FILE` | Output file |

**Example:**

```bash
aksara inspectdb
aksara inspectdb users
aksara inspectdb --output models.py
```

---

## Server Commands

### run

Start development server.

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
| `--ipython` | Use IPython |
| `--bpython` | Use bpython |
| `--plain` | Use plain Python |

**Example:**

```bash
aksara shell
aksara shell --ipython
```

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

**Output:**

```
Aksara Project Information
==========================
Version: 0.5.43
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

### check

Run system checks.

```bash
aksara check [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--tag TAG` | Check specific tag |
| `--deploy` | Deployment checks |

**Example:**

```bash
aksara check
aksara check --deploy
```

### test

Run tests.

```bash
aksara test [PATH] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Verbose output |
| `--cov APP` | Coverage for app |
| `--cov-report TYPE` | Coverage report type |
| `-k EXPR` | Test selection expression |

**Example:**

```bash
aksara test
aksara test tests/test_users.py
aksara test -v --cov=myapp
aksara test -k "test_create"
```

### collectstatic

Collect static files.

```bash
aksara collectstatic [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--no-input` | Skip confirmation |
| `--clear` | Clear before collecting |

---

## Auth Commands

### createsuperuser

Create admin user.

```bash
aksara createsuperuser [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--email EMAIL` | User email |
| `--username USERNAME` | Username |
| `--no-input` | Use defaults |

**Example:**

```bash
aksara createsuperuser
aksara createsuperuser --email admin@example.com
```

### changepassword

Change user password.

```bash
aksara changepassword USERNAME [OPTIONS]
```

**Example:**

```bash
aksara changepassword admin
```

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
