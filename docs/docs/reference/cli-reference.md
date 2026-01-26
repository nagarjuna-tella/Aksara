# CLI Reference

Complete reference for Vidyut CLI commands.

---

## Usage

```bash
vidyut [OPTIONS] COMMAND [ARGS]...
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

Create a new Vidyut project.

```bash
vidyut startproject NAME [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--directory DIR` | Target directory |
| `--template TEMPLATE` | Project template |

**Example:**

```bash
vidyut startproject myproject
vidyut startproject myproject --directory /path/to/dir
```

### startapp

Create a new application.

```bash
vidyut startapp NAME [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--directory DIR` | Target directory |

**Example:**

```bash
vidyut startapp users
vidyut startapp blog --directory apps/
```

---

## Database Commands

### makemigrations

Create new migrations.

```bash
vidyut makemigrations [APP] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--name NAME` | Migration name |
| `--empty` | Create empty migration |
| `--check` | Check only, don't create |
| `--dry-run` | Show without creating |

**Example:**

```bash
vidyut makemigrations
vidyut makemigrations users --name add_bio_field
vidyut makemigrations --check
```

### migrate

Apply migrations.

```bash
vidyut migrate [APP] [MIGRATION] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--fake` | Mark as applied without running |
| `--list` | Show migration status |
| `--plan` | Show migration plan |

**Example:**

```bash
vidyut migrate
vidyut migrate users
vidyut migrate users 0005
vidyut migrate --list
```

### dbshell

Open database shell.

```bash
vidyut dbshell [OPTIONS]
```

**Example:**

```bash
vidyut dbshell
```

### inspectdb

Generate models from existing database.

```bash
vidyut inspectdb [TABLE] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--output FILE` | Output file |

**Example:**

```bash
vidyut inspectdb
vidyut inspectdb users
vidyut inspectdb --output models.py
```

---

## Server Commands

### runserver

Start development server.

```bash
vidyut runserver [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host HOST` | `127.0.0.1` | Bind host |
| `--port PORT` | `8000` | Bind port |
| `--reload` | True | Auto-reload |
| `--workers N` | `1` | Worker count |

**Example:**

```bash
vidyut runserver
vidyut runserver --port 3000
vidyut runserver --host 0.0.0.0 --port 8080
vidyut runserver --no-reload
```

---

## Shell Commands

### shell

Start interactive Python shell.

```bash
vidyut shell [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--ipython` | Use IPython |
| `--bpython` | Use bpython |
| `--plain` | Use plain Python |

**Example:**

```bash
vidyut shell
vidyut shell --ipython
```

---

## Utility Commands

### routes

List all routes.

```bash
vidyut routes [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--format FMT` | Output format (table, json) |

**Example:**

```bash
vidyut routes
vidyut routes --format json
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
vidyut info [OPTIONS]
```

**Output:**

```
Vidyut Project Information
==========================
Version: 0.4.9
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
vidyut check [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--tag TAG` | Check specific tag |
| `--deploy` | Deployment checks |

**Example:**

```bash
vidyut check
vidyut check --deploy
```

### test

Run tests.

```bash
vidyut test [PATH] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Verbose output |
| `--cov APP` | Coverage for app |
| `--cov-report TYPE` | Coverage report type |
| `-k EXPR` | Test selection expression |

**Example:**

```bash
vidyut test
vidyut test tests/test_users.py
vidyut test -v --cov=myapp
vidyut test -k "test_create"
```

### collectstatic

Collect static files.

```bash
vidyut collectstatic [OPTIONS]
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
vidyut createsuperuser [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--email EMAIL` | User email |
| `--username USERNAME` | Username |
| `--no-input` | Use defaults |

**Example:**

```bash
vidyut createsuperuser
vidyut createsuperuser --email admin@example.com
```

### changepassword

Change user password.

```bash
vidyut changepassword USERNAME [OPTIONS]
```

**Example:**

```bash
vidyut changepassword admin
```

---

## AI Commands

### ai query

Query data with natural language.

```bash
vidyut ai query "QUERY" [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--output FMT` | Output format (table, json, csv) |
| `--limit N` | Result limit |

**Example:**

```bash
vidyut ai query "Show all active users"
vidyut ai query "Posts created this week" --output json
```

### ai generate

Generate code.

```bash
vidyut ai generate TYPE DESCRIPTION [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--output FILE` | Output file |
| `--preview` | Preview only |

**Example:**

```bash
vidyut ai generate model "User with email, name, role"
vidyut ai generate viewset User
vidyut ai generate test User --output tests/test_users.py
```

### ai doctor

Analyze schema for issues.

```bash
vidyut ai doctor [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--fix` | Auto-fix issues |
| `--interactive` | Confirm each fix |

**Example:**

```bash
vidyut ai doctor
vidyut ai doctor --fix --interactive
```

### ai plan

Plan complex tasks.

```bash
vidyut ai plan "TASK" [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--execute` | Execute the plan |
| `--preview` | Preview only |

**Example:**

```bash
vidyut ai plan "Add user profile feature with avatar upload"
vidyut ai plan "Refactor auth to use JWT" --preview
```

### ai agent

Run AI agent.

```bash
vidyut ai agent "TASK" [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--tools TOOLS` | Allowed tools (comma-separated) |
| `--max-steps N` | Maximum steps |

**Example:**

```bash
vidyut ai agent "Analyze the codebase and suggest improvements"
vidyut ai agent "Fix failing tests" --max-steps 10
```

### ai patch

Apply code changes.

```bash
vidyut ai patch "CHANGE" [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--preview` | Preview changes |
| `--dry-run` | Don't apply |

**Example:**

```bash
vidyut ai patch "Add logging to all viewsets" --preview
```

### ai ask

Ask questions about the codebase.

```bash
vidyut ai ask "QUESTION"
```

**Example:**

```bash
vidyut ai ask "How is authentication implemented?"
vidyut ai ask "What models have soft delete?"
```

### ai config

Configure AI settings.

```bash
vidyut ai config [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--provider NAME` | Set provider |
| `--model NAME` | Set model |
| `--show` | Show current config |

**Example:**

```bash
vidyut ai config --show
vidyut ai config --provider openai --model gpt-4
```

---

## Custom Commands

### Creating Commands

```python
# myapp/management/commands/mycommand.py
from vidyut.cli import Command, argument, option

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
vidyut mycommand World --count 3
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VIDYUT_SETTINGS_MODULE` | Settings module path |
| `VIDYUT_DEBUG` | Enable debug mode |
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
