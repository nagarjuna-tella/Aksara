# Diagnostics & Doctor Mode

**v0.5.17** — Aksara includes a built-in self-diagnostics engine that checks your project's health across database, migrations, AI providers, settings, security, file-system, and cache.

**v0.5.18** — Every diagnostic issue now includes structured **autoremediation actions** — machine-readable fix instructions that the Studio UI, CLI, and future agents can surface. See [Autoremediation Hints](debugging/autoremediation.md) for the full guide.

## Quick Start

### CLI

```bash
# Run all checks
aksara doctor run

# First-user launch readiness
aksara doctor launch-check
aksara doctor launch-check --format json

# JSON output (for CI/CD)
aksara doctor run --format json

# Quick summary
aksara doctor summary

# AI-specific checks
aksara doctor ai

# Database-specific checks
aksara doctor db

# v0.5.18: Generate a fix-plan with structured actions
aksara doctor fix-plan
aksara doctor fix-plan --format json
aksara doctor fix-plan --only-errors --only-with-actions
```

### Studio Dashboard

Navigate to **Diagnostics** in the Studio sidebar (or press <kbd>d</kbd>) to see a live diagnostics panel with:

- **Summary banner** — overall status with error/warning/info counts
- **Issue cards** — each issue with severity, category, message, and fix hints
- **Filters** — filter by severity (All / Errors / Warnings / Info)
- **Search** — press <kbd>/</kbd> to focus the search field
- **Auto-refresh** — updates every 10 seconds (toggle Live/Paused)

### Python API

```python
from aksara.diagnostics import run_all_checks

report = await run_all_checks()
print(f"Status: {report.overall_status}")
print(f"Errors: {report.stats['errors']}, Warnings: {report.stats['warnings']}")

for issue in report.issues:
    print(f"[{issue.severity}] {issue.title}: {issue.message}")
    if issue.hint:
        print(f"  Hint: {issue.hint}")
    # v0.5.18: Autoremediation actions
    for action in issue.actions:
        print(f"  → [{action.kind}] {action.title}")
```

## What Gets Checked

| Check | Kind | Description |
|-------|------|-------------|
| Database Connectivity | `database_connectivity` | Tries an actual connection to your PostgreSQL database |
| Migrations Status | `migrations_pending` | Detects unapplied migrations |
| Migration Conflicts | `migrations_conflict` | Finds duplicate migration prefixes |
| AI Profiles | `ai_profile_issue` | Validates AI provider profiles (v0.5.12 validator) |
| AI Provider Secrets | `ai_secret_missing` | Checks required env vars for AI providers |
| Required Settings | `settings_invalid` | Validates DATABASE_URL, pool sizes, thresholds |

## Launch Check

`aksara doctor launch-check` is the first-user readiness check. It reports Python, Aksara version, project structure, settings import, database connection, migrations, Studio, API docs, MCP, AI Hub, examples, and local dev-mode warnings.

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Ready |
| `1` | Partial with warnings |
| `2` | Blocked by errors |
| Cache Availability | `cache_unavailable` | Checks AKSARA_CACHE_URL / CACHE_URL |
| File-System Permissions | `file_system_unwritable` | Writes a probe file to temp and migrations dirs |
| Security | `security_warning` | Checks debug mode, Studio exposure, allowed origins |

## Severity Levels

- **error** — Something is broken and must be fixed
- **warning** — Something is misconfigured or risky
- **info** — Informational, no action required

## Exit Codes (CLI)

| Code | Meaning |
|------|---------|
| `0` | No errors (warnings and info are OK) |
| `1` | One or more errors detected |

## CI/CD Integration

```yaml
# GitHub Actions example
- name: Health Check
  run: aksara doctor run --format json
```

```bash
# Shell script
if aksara doctor run --format json | jq -e '.stats.errors == 0'; then
    echo "All clear"
else
    echo "Issues found"
    exit 1
fi
```

## Data Models

### DiagnosticIssue

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `str` | Issue category (e.g., `database_connectivity`) |
| `severity` | `"error" \| "warning" \| "info"` | Severity level |
| `title` | `str` | Short human-readable title |
| `message` | `str` | Detailed explanation |
| `hint` | `str \| None` | Suggested fix |
| `meta` | `dict \| None` | Extra metadata |

### DiagnosticReport

| Field | Type | Description |
|-------|------|-------------|
| `issues` | `List[DiagnosticIssue]` | All findings, sorted by severity |
| `stats` | `dict` | `{errors, warnings, info}` counts |
| `timestamp` | `datetime` | UTC timestamp |
| `duration_ms` | `float` | Total check duration in ms |
| `system` | `dict` | Aksara version, Python version, OS, arch |

## Studio Endpoint

```
GET /studio/diagnostics
```

Returns a `DiagnosticReport` JSON object with all check results.

## Keyboard Shortcuts (Studio)

| Key | Action |
|-----|--------|
| <kbd>d</kbd> | Navigate to Diagnostics |
| <kbd>/</kbd> | Focus search input |
| <kbd>Esc</kbd> | Clear search and unfocus |
| <kbd>7</kbd> | Navigate to Diagnostics (number key) |
