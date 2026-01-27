# Schema Doctor

Analyze and fix database schema issues.

---

## Overview

Schema Doctor examines your models and database for:

- **Missing indexes** — Slow queries
- **Constraint issues** — Data integrity problems
- **Naming inconsistencies** — Convention violations
- **Relationship problems** — FK and M2M issues
- **Performance anti-patterns** — Problematic designs

```bash
aksara ai doctor
```

---

## Quick Start

### Run Analysis

```bash
aksara ai doctor
```

Output:
```
🔍 Analyzing schema...

✓ 12 models analyzed
⚠️ 5 issues found

Issues:
  1. [HIGH] Post.author has no index (FK without index)
  2. [MEDIUM] User.email should have unique constraint
  3. [LOW] Comment.created_at missing default value
  4. [LOW] Tag.name exceeds recommended length (255 vs 100)
  5. [INFO] Order uses BigInteger PK instead of UUID

Run `aksara ai doctor --fix` to auto-fix issues.
```

### Auto-Fix Issues

```bash
aksara ai doctor --fix
```

### Python API

```python
from aksara.ai import SchemaDoctor

doctor = SchemaDoctor()
report = await doctor.analyze()

for issue in report.issues:
    print(f"[{issue.severity}] {issue.message}")
```

---

## Issue Categories

### Missing Indexes

```
[HIGH] Post.author_id has no index

ForeignKey columns should be indexed for JOIN performance.

Fix: Add index on author_id

SQL: CREATE INDEX idx_posts_author_id ON posts(author_id);
```

### Constraint Issues

```
[MEDIUM] User.email should be unique

The email field is used for authentication but lacks a 
unique constraint.

Fix: Add unique constraint

Model change:
  email = fields.EmailField(unique=True)  # Add unique=True
```

### Naming Inconsistencies

```
[LOW] Table 'BlogPosts' uses PascalCase

Convention: Use snake_case for table names.

Current: BlogPosts
Suggested: blog_posts
```

### Relationship Issues

```
[MEDIUM] Comment.post has no on_delete specified

ForeignKey without explicit on_delete behavior may cause
unexpected cascading or errors.

Fix: Add on_delete="CASCADE" or "PROTECT"
```

### Performance Anti-Patterns

```
[HIGH] User.metadata uses JSONField for structured data

The metadata field appears to store predictable keys that
could be separate columns.

Detected keys: ['phone', 'address', 'preferences']

Suggestion: Consider separate fields for frequently queried data
```

---

## Severity Levels

| Level | Description | Action |
|-------|-------------|--------|
| `CRITICAL` | Will cause data loss or errors | Must fix immediately |
| `HIGH` | Significant performance/integrity issue | Fix soon |
| `MEDIUM` | Potential problems | Plan to fix |
| `LOW` | Minor issues | Nice to fix |
| `INFO` | Suggestions only | Optional |

---

## Analysis Options

### Specific Models

```bash
aksara ai doctor --models User,Post,Comment
```

```python
report = await doctor.analyze(models=["User", "Post", "Comment"])
```

### Severity Filter

```bash
aksara ai doctor --min-severity medium
```

```python
report = await doctor.analyze(min_severity="medium")
```

### Category Filter

```bash
aksara ai doctor --categories indexes,constraints
```

```python
report = await doctor.analyze(
    categories=["indexes", "constraints", "naming", "relations", "performance"]
)
```

---

## Auto-Fix

### Interactive Fix

```bash
aksara ai doctor --fix --interactive

Issue 1/5: Post.author_id has no index
  Fix: CREATE INDEX idx_posts_author_id ON posts(author_id)
  
Apply this fix? [y/N/a(ll)/s(kip)]
```

### Fix Specific Severities

```bash
# Only fix high and critical
aksara ai doctor --fix --min-severity high
```

### Dry Run

```bash
aksara ai doctor --fix --dry-run

Would apply these fixes:
  1. Add index on posts.author_id
  2. Add unique constraint on users.email
  3. Set default for comments.created_at
```

### Python API

```python
doctor = SchemaDoctor()
report = await doctor.analyze()

# Fix all issues
fixes = await doctor.fix_all(report, dry_run=True)

for fix in fixes:
    print(f"Would: {fix.description}")
    print(f"SQL: {fix.sql}")

# Apply fixes
await doctor.fix_all(report)
```

---

## Report Format

### Console Output

```bash
aksara ai doctor
```

### JSON Report

```bash
aksara ai doctor --output report.json
```

```json
{
  "analyzed_at": "2024-01-15T10:30:00Z",
  "models_analyzed": 12,
  "total_issues": 5,
  "issues_by_severity": {
    "high": 1,
    "medium": 2,
    "low": 2
  },
  "issues": [
    {
      "id": "idx-001",
      "severity": "high",
      "category": "indexes",
      "model": "Post",
      "field": "author_id",
      "message": "ForeignKey without index",
      "fix_sql": "CREATE INDEX ...",
      "fix_model": "..."
    }
  ]
}
```

### HTML Report

```bash
aksara ai doctor --output report.html
```

### Python Report Object

```python
report = await doctor.analyze()

print(report.summary)
print(report.models_analyzed)
print(report.total_issues)
print(report.issues_by_severity)

for issue in report.issues:
    print(issue.id)
    print(issue.severity)
    print(issue.category)
    print(issue.model)
    print(issue.field)
    print(issue.message)
    print(issue.fix_sql)
    print(issue.fix_model_code)
```

---

## Custom Rules

### Define Custom Rule

```python
from aksara.ai.doctor import Rule, register_rule

@register_rule
class RequireUUIDPrimaryKey(Rule):
    """All models should use UUID primary keys."""
    
    id = "custom-uuid-pk"
    severity = "medium"
    category = "conventions"
    
    def check(self, model) -> list[Issue]:
        issues = []
        pk_field = model._meta.pk
        
        if pk_field.type != "UUIDField":
            issues.append(Issue(
                rule=self,
                model=model,
                field=pk_field.name,
                message=f"{model.__name__} uses {pk_field.type} instead of UUIDField",
                fix_hint="Change primary key to UUIDField",
            ))
        
        return issues
```

### Disable Rules

```python
# settings.py
AKSARA = {
    "AI_DOCTOR": {
        "disabled_rules": [
            "idx-fk-without-index",  # We handle this differently
            "naming-snake-case",      # We use different convention
        ],
    },
}
```

### Rule Configuration

```python
AKSARA = {
    "AI_DOCTOR": {
        "rules": {
            "max-string-length": {
                "max_length": 200,  # Instead of default 100
            },
            "require-timestamps": {
                "fields": ["created_at"],  # Only require created_at
            },
        },
    },
}
```

---

## CI Integration

### GitHub Actions

```yaml
name: Schema Check

on: [push, pull_request]

jobs:
  schema-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Run Schema Doctor
        run: |
          aksara ai doctor --min-severity medium --exit-code
        
      # Fails if medium+ issues found
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: schema-doctor
        name: Schema Doctor
        entry: aksara ai doctor --min-severity high --exit-code
        language: system
        pass_filenames: false
```

### Python Test

```python
import pytest
from aksara.ai import SchemaDoctor

@pytest.mark.asyncio
async def test_no_critical_schema_issues():
    doctor = SchemaDoctor()
    report = await doctor.analyze(min_severity="critical")
    
    assert len(report.issues) == 0, \
        f"Critical issues found: {[i.message for i in report.issues]}"
```

---

## Common Issues and Fixes

### ForeignKey Without Index

**Issue:**
```
Post.author_id (FK to User) has no index
```

**Fix:**
```python
# models.py
author = fields.ForeignKey(
    "User",
    on_delete="CASCADE",
    db_index=True,  # Add this
)
```

### Missing Unique Constraint

**Issue:**
```
User.email should be unique
```

**Fix:**
```python
email = fields.EmailField(unique=True)
```

### No Default for Timestamp

**Issue:**
```
Comment.created_at has no default
```

**Fix:**
```python
created_at = fields.DateTimeField(auto_now_add=True)
```

### Missing on_delete

**Issue:**
```
Comment.post FK has no on_delete
```

**Fix:**
```python
post = fields.ForeignKey("Post", on_delete="CASCADE")
```

---

## Configuration

```python
# settings.py
AKSARA = {
    "AI_DOCTOR": {
        # Analysis
        "include_models": None,      # None = all models
        "exclude_models": ["Legacy"],
        "min_severity": "low",
        
        # Rules
        "disabled_rules": [],
        "custom_rules_module": "myapp.doctor_rules",
        
        # Conventions
        "table_naming": "snake_case",
        "require_timestamps": True,
        "require_uuid_pk": False,
        "max_string_length": 100,
        
        # Output
        "output_format": "console",  # or "json", "html"
    },
}
```

---

## Related Documentation

- [AI Mode Overview](index.md)
- [Models](../orm/models.md)
- [Migrations](../orm/migrations.md)
- [Fields](../orm/fields.md)
