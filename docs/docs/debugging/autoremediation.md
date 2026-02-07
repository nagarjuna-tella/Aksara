# Autoremediation Hints

> **v0.5.18** — Every diagnostic issue now includes structured **fix actions**
> that the Studio UI, CLI, and future agents can surface and apply.

---

## Overview

In v0.5.17, Aksara introduced Doctor Mode with `DiagnosticIssue` objects
containing free-text `hint` strings. In v0.5.18, every issue also carries
a list of **`DiagnosticAction`** objects — machine-readable instructions
that UIs and automation tools can render, copy, or execute.

```python
from aksara.diagnostics import run_all_checks

report = await run_all_checks()
for issue in report.issues:
    print(f"[{issue.severity}] {issue.title}")
    for action in issue.actions:
        print(f"  → [{action.kind}] {action.title}")
        if action.example:
            print(f"    $ {action.example}")
```

---

## DiagnosticAction Model

| Field         | Type                          | Description                          |
|---------------|-------------------------------|--------------------------------------|
| `kind`        | `Literal[...]`                | Action type (see below)              |
| `target`      | `str`                         | Env var, command, URL, file, setting |
| `title`       | `str`                         | Human-readable title                 |
| `example`     | `Optional[str]`               | Full runnable/pasteable example      |
| `description` | `Optional[str]`               | Extra details                        |

### Action Kinds

| Kind           | Meaning                           | Target example           |
|----------------|-----------------------------------|--------------------------|
| `set_env`      | Set an environment variable       | `DATABASE_URL`           |
| `run_command`   | Run a shell command               | `aksara migrate`         |
| `open_doc`     | Open a documentation URL          | `https://aksara.dev/...` |
| `edit_file`    | Edit a specific file              | `settings.py`            |
| `add_setting`  | Add/change an Aksara setting      | `pool_max_size`          |

---

## build_action() Helper

```python
from aksara.diagnostics import build_action

action = build_action(
    kind="set_env",
    target="DATABASE_URL",
    title="Set DATABASE_URL",
    example='export DATABASE_URL="postgresql://user:pass@localhost:5432/db"',
)
```

---

## Studio UI

Every issue card now has an expandable **"Fix This Issue"** section showing
action cards with:

- **Kind icon** and label (ENV, CMD, DOC, FILE, CFG)
- **Title** describing the fix
- **Example snippet** with a **Copy** button for one-click clipboard copy

Click the toggle to expand/collapse actions per issue.

---

## CLI: `aksara doctor fix-plan`

Generate a full remediation plan:

```bash
# Text output (default)
aksara doctor fix-plan

# JSON output for scripts/CI
aksara doctor fix-plan --format json

# Only errors
aksara doctor fix-plan --only-errors

# Only issues with fix actions
aksara doctor fix-plan --only-with-actions

# Combined
aksara doctor fix-plan --only-errors --only-with-actions
```

### Text Output Example

```
  ⚡ Aksara Doctor — Fix Plan

  ✗ 1. [ERROR] No database URL configured
     DATABASE_URL or database_url setting is not set.
     Hint: Set DATABASE_URL environment variable...
     Actions:
       → [ENV] Set DATABASE_URL
         $ export DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"
       → [DOC] Open database configuration docs

  1 issue(s), 2 fix action(s)
```

### JSON Output Structure

```json
{
  "issues": [
    {
      "kind": "database_connectivity",
      "severity": "error",
      "title": "No database URL configured",
      "message": "...",
      "hint": "...",
      "actions": [
        {
          "kind": "set_env",
          "target": "DATABASE_URL",
          "title": "Set DATABASE_URL",
          "example": "export DATABASE_URL=\"...\"",
          "description": null
        }
      ]
    }
  ],
  "stats": { "errors": 1, "warnings": 0, "info": 0 },
  "duration_ms": 42.0,
  "system": { ... }
}
```

---

## Actions by Checker

| Checker                       | Action Kinds Emitted                  |
|-------------------------------|---------------------------------------|
| `check_database_connectivity` | `set_env`, `open_doc`, `run_command`  |
| `check_migrations_status`     | `run_command`                         |
| `check_ai_profiles`           | `add_setting`                         |
| `check_ai_provider_secrets`   | `set_env`                             |
| `check_required_settings`     | `set_env`, `add_setting`              |
| `check_cache_available`       | `set_env`                             |
| `check_file_system_permissions`| `run_command`                        |
| `check_security`              | `set_env`, `add_setting`              |

---

## CI/CD Integration

Use the JSON fix-plan in CI pipelines:

```bash
# Fail CI on errors, capture fix plan
aksara doctor fix-plan --format json --only-errors > fix-plan.json
```

Parse in scripts:

```python
import json

with open("fix-plan.json") as f:
    plan = json.load(f)

for issue in plan["issues"]:
    for action in issue["actions"]:
        if action["kind"] == "run_command":
            print(f"Suggested: {action['example']}")
```
