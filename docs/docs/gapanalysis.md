# Gap Analysis

!!! info "v0.5.26 — Gap Analysis Engine"
    The gap analysis engine is a **static pre-flight scanner** that surfaces
    actionable issues across eight categories *without* requiring a live database
    connection.  It complements the
    [Diagnostics & Doctor](diagnostics.md) system, which tests live connectivity.

---

## Overview

Before deploying — or when onboarding a new developer — run the gap analysis to
catch common configuration problems early:

```bash
aksara gaps run
```

The engine checks eight categories in parallel and produces a prioritised
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

# CI gate — exits 1 if any critical issue is found
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
| `--categories` | Comma-separated list of categories (default: all eight) |

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

Lists only `critical` issues.  Designed as a **CI gate**:

```bash
# In a CI script:
if ! aksara gaps list-critical --format json > /dev/null 2>&1; then
  echo "Critical gaps found — aborting deployment."
  exit 1
fi
```

---

### `aksara gaps fix-plan`

Generates a prioritised list of shell commands to remediate each issue.

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

Both endpoints accept an optional `categories` query parameter:

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

## Writing a Custom Checker

The gap analysis engine is fully extensible.  Register a custom checker
with the `_CATEGORY_CHECKERS` dict or call `run_gap_analysis_for_category`
with your own coroutine:

```python
from aksara.gapanalysis import GapIssue, GapAnalysisReport, _make_issue

async def my_custom_check() -> list[GapIssue]:
    issues = []
    if not some_condition():
        issues.append(_make_issue(
            category="environment",
            severity="warning",
            code="MY_CUSTOM_CHECK_FAILED",
            title="Custom check: something is missing",
            message="Explanation of what is wrong.",
            hint="How to fix it.",
        ))
    return issues
```

!!! tip
    Custom checkers can use any of the eight built-in categories.
    Group related checks together to keep the output organised.

---

## Comparison with Doctor

| Feature | `aksara doctor` | `aksara gaps` |
|---|---|---|
| Requires live DB | ✅ Yes | ❌ No |
| Checks database connectivity | ✅ Yes | ❌ Config only |
| Checks import availability | ❌ No | ✅ Yes |
| Checks migration conflicts | ✅ Yes | ✅ Yes |
| Checks AI providers | ✅ Yes | ✅ Yes |
| Fix commands included | ✅ Yes | ✅ Yes |
| CI-gate exit codes | ✅ Yes | ✅ Yes |
| Runs offline | ❌ No | ✅ Yes |

Use **`aksara gaps`** for local development pre-flight and CI checks.
Use **`aksara doctor`** after the application has started to verify live connectivity.
