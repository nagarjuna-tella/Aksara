# Gap Analysis

!!! info "v0.5.26 — Gap Analysis Engine"
    The gap analysis engine is a **static pre-flight scanner** that surfaces
    actionable issues across nine categories *without* requiring a live database
    connection.  It complements the
    [Diagnostics & Doctor](diagnostics.md) system, which tests live connectivity.

---

## Scope and failure handling

Gap analysis is a pre-flight heuristic scanner, not the production release gate.
It imports packages and inspects available configuration/project metadata; its
database check does not prove live connectivity, RLS, or migration application.
Use [Doctor production checks](diagnostics.md) for the separate release policy.

The categories are `imports`, `db`, `migrations`, `routers`, `providers`, `studio`,
`environment`, `ai_pipeline`, and `ai_hub`. They run sequentially. A checker
exception becomes a warning issue; it does not fail the whole scan. Unknown
category names raise a validation error before scanning; an empty category list
selects all categories.

Fix commands are suggested text. Review them for your current configuration and
permissions; the scanner does not execute them. Some historical suggestions may
need adaptation. Never automatically apply the generated fix plan.

## Overview

Before deploying — or when onboarding a new developer — run the gap analysis to
catch common configuration problems early:

```bash
aksara gaps run
```

The engine checks nine categories sequentially and produces a prioritised
issue list with remediation commands included.

---

## Quick-Start

```bash
# Full scan — pretty output
aksara gaps run

# Machine-readable JSON (for CI / scripting)
aksara gaps json

# Count by severity
aksara gaps summary

# Only show errors and criticals
aksara gaps list-errors

# Critical-only filter — exits 1 if a critical issue is found
aksara gaps list-critical

# Structured fix plan with one-liner commands
aksara gaps fix-plan
```

---

## Check Categories

| Category | What it checks |
|---|---|
| `imports` | Required Python packages are importable in the current environment |
| `db` | `DATABASE_URL` presence, URL scheme, pool settings sanity |
| `migrations` | Migrations directory, empty migrations, conflict detection |
| `routers` | Apps in `settings.apps` have `models.py` and `views.py` |
| `providers` | AI provider profiles, required secrets present |
| `studio` | Studio panel enabled, static assets exist, secret key set |
| `environment` | Required env vars present, Python version ≥ 3.10, no debug-in-prod |
| `ai_pipeline` | AI modules importable, MCP package when enabled, exposed models |
| `ai_hub` | AI Hub provider/default/embedding configuration; no live provider call |

---

## Severity Levels

Gap issues use four severity levels — one more than the standard diagnostics system:

| Severity | Meaning |
|---|---|
| `critical` | Prevents the application from starting or running |
| `error` | Will impair functionality in a meaningful way |
| `warning` | Worth fixing before going to production |
| `info` | Informational note; no immediate action required |

Issues with severity `error` or `critical` cause **non-zero exit codes** on the
relevant CLI commands.

---

## CLI Commands

### `aksara gaps run`

Runs all (or selected) categories and prints a rich grouped table.

```bash
aksara gaps run
aksara gaps run --format json
aksara gaps run --categories db,migrations,environment
```

**Options:**

| Flag | Description |
|---|---|
| `--format pretty\|json` | Output format (default: `pretty`) |
| `--categories` | Comma-separated list of categories (default: all nine) |

---

### `aksara gaps summary`

Compact count of issues grouped by severity and category.

```bash
aksara gaps summary
```

**Example output:**

```
  ⚡ Aksara Gap Analysis — Summary

  Severity     Count
  ──────────── ──────
  critical          1
  warning           2
  ──────────── ──────
  TOTAL             3

  Category               Issues
  ─────────────────────  ───────
  db                           1
  environment                  1
  providers                    1
```

---

### `aksara gaps json`

Writes the full report as JSON to stdout.  Suitable for CI pipelines or
saving to a file for later processing.

```bash
aksara gaps json > gaps.json
aksara gaps json --categories imports,environment
```

---

### `aksara gaps list-errors`

Lists only `error` and `critical` severity issues.

```bash
aksara gaps list-errors
aksara gaps list-errors --format json
```

Exit code is `1` when any blocking issues are found.

---

### `aksara gaps list-critical`

Lists only `critical` issues.  This is only a critical-severity filter, not the full release gate:

```bash
# In a CI script:
if ! aksara gaps list-critical --format json > /dev/null 2>&1; then
  echo "Critical gaps found — aborting deployment."
  exit 1
fi
```

---

### `aksara gaps fix-plan`

Lists suggested fix commands for review; not every issue has a command and
commands are not executed.

```bash
aksara gaps fix-plan
aksara gaps fix-plan --format json
aksara gaps fix-plan --only-blocking
```

**Example output:**

```
  ⚡ Aksara Gaps — Fix Plan

  1. [CRITICAL] No database URL configured
     Category: db | Code: DB_NO_URL
     → Add DATABASE_URL to your .env file
       $ echo "DATABASE_URL=postgresql://user:pass@localhost/mydb" >> .env

  2. [WARNING] AKSARA_SECRET_KEY is not set
     Category: studio | Code: STUDIO_NO_SECRET_KEY
     → Generate and set a secret key
       $ echo "AKSARA_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')" >> .env
```

---

## Studio Panel

In addition to the CLI, the gap analysis engine is accessible from the
Studio dashboard.

### API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/studio/gaps` | Run the analysis and return the full report |
| `POST` | `/studio/gaps/run` | Trigger a fresh analysis run |

Studio must be mounted and its access requirements satisfied; see
[Studio configuration](studio/configuration.md). GET accepts an optional
`categories` query parameter. POST runs all categories and reports scan failures
in its response body.

```bash
# HTTP API — specific categories only
curl http://localhost:8000/studio/gaps?categories=db,migrations
```

### Python API

```python
from aksara.gapanalysis import run_gap_analysis

# Full scan
report = await run_gap_analysis()
print(report.summary_line)
# → "3 issues (1 critical, 2 warnings)"

# Specific categories
report = await run_gap_analysis(categories=["db", "environment"])

# Iterate over issues
for issue in report.issues:
    if issue.is_blocking:
        print(f"BLOCKING: {issue.title}")
        for cmd in issue.fix_commands:
            print(f"  Fix: {cmd.command}")

# Access stats
print(report.stats.critical)     # 1
print(report.stats.has_blocking) # True
print(report.overall_status)     # "critical"
```

---

## Data Models

### `GapAnalysisReport`

```python
class GapAnalysisReport(BaseModel):
    issues: List[GapIssue]
    stats: GapAnalysisStats
    categories_checked: List[GapIssueCategory]
    timestamp: datetime
    duration_ms: float
    system: Dict[str, str]

    # Convenience helpers
    def by_severity(severity) -> List[GapIssue]: ...
    def by_category(category) -> List[GapIssue]: ...

    @property
    def summary_line(self) -> str: ...
    @property
    def has_critical(self) -> bool: ...
    @property
    def has_errors(self) -> bool: ...
    @property
    def overall_status(self) -> str: ...  # "clean" | "warning" | "error" | "critical"
```

### `GapIssue`

```python
class GapIssue(BaseModel):
    category: GapIssueCategory   # "imports" | "db" | ...
    severity: GapIssueSeverity   # "info" | "warning" | "error" | "critical"
    code: str                    # "DB_NO_URL", "IMPORT_MISSING_ASYNCPG", ...
    title: str
    message: str
    hint: Optional[str]
    fix_commands: List[GapFixCommand]
    meta: Optional[Dict[str, Any]]

    @property
    def is_blocking(self) -> bool: ...  # critical or error
```

### `GapFixCommand`

```python
class GapFixCommand(BaseModel):
    description: str
    command: str                 # Shell command (may contain placeholders)
    env_required: List[str]      # Env vars needed before running
```

---

## Single-category helper

`run_gap_analysis_for_category(category)` accepts one built-in category name and
returns its issues. It does not accept or register a custom coroutine. Unlike
`run_gap_analysis`, it returns an empty list for an unknown category; a checker
exception is logged and also returns an empty list. An empty result therefore
cannot distinguish a clean scan from these failures.

The `_CATEGORY_CHECKERS` registry and `_make_issue` helper are internal. Do not
use registry mutation as a supported application extension API.

---

## Comparison with Doctor

Use `aksara gaps` for heuristic configuration checks. Doctor has separate
static and live checks, so whether it needs a database depends on the selected
command/checks. The application web server need not already be running. Follow
[Diagnostics & Doctor](diagnostics.md) for production release policy and
connectivity validation rather than treating either command family as one
interchangeable gate.
