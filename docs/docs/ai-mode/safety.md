# AI Mode Safety

Security and safety features for AI-powered operations.

---

## Overview

AI Mode includes multiple safety layers to prevent:

- **Accidental data loss** — Confirmation prompts, dry runs
- **Unauthorized access** — Tool permissions, audit logging
- **Runaway operations** — Rate limits, timeouts
- **Code injection** — Input sanitization, sandboxing

---

## Safety Layers

```
┌─────────────────────────────────────────────────────────┐
│                    User Request                          │
├─────────────────────────────────────────────────────────┤
│  1. Input Validation      - Sanitize inputs             │
├─────────────────────────────────────────────────────────┤
│  2. Permission Check      - User has access?            │
├─────────────────────────────────────────────────────────┤
│  3. Rate Limiting         - Within limits?              │
├─────────────────────────────────────────────────────────┤
│  4. Confirmation Prompt   - User approves?              │
├─────────────────────────────────────────────────────────┤
│  5. Dry Run (optional)    - Preview changes             │
├─────────────────────────────────────────────────────────┤
│  6. Execution             - Perform operation           │
├─────────────────────────────────────────────────────────┤
│  7. Audit Logging         - Record action               │
├─────────────────────────────────────────────────────────┤
│  8. Rollback (if needed)  - Undo on failure             │
└─────────────────────────────────────────────────────────┘
```

---

## Confirmation Prompts

### CLI Confirmations

Destructive operations require explicit confirmation:

```bash
vidyut ai query "Delete inactive users"

⚠️  Destructive Operation Detected

This query will DELETE 1,234 records from the 'users' table.

Proceed? [y/N]
```

### Configuration

```python
VIDYUT = {
    "AI_SAFETY": {
        "require_confirmation": True,
        "confirmation_for": [
            "delete",
            "update",
            "migrate",
            "patch",
        ],
    },
}
```

### Programmatic Confirmation

```python
from vidyut.ai import QueryEngine

engine = QueryEngine()

result = await engine.query(
    "Delete inactive users",
    require_confirmation=True,
)

if result.requires_confirmation:
    print(f"Will delete {result.affected_count} records")
    if user_confirms():
        await result.execute()
```

### Skip Confirmation (Use with Caution)

```python
# Only for automated scripts with proper safeguards
result = await engine.query(
    "Delete inactive users",
    require_confirmation=False,  # Skip confirmation
)
```

---

## Dry Run Mode

### Preview Before Executing

```bash
vidyut ai patch models.py "Add phone field" --dry-run

Dry Run - No changes will be made

Would modify: models.py

--- models.py (original)
+++ models.py (modified)
@@ -10,6 +10,7 @@
 class User(Model):
     email = fields.EmailField(unique=True)
+    phone = fields.StringField(max_length=20, null=True)
     name = fields.StringField(max_length=100)
```

### Programmatic Dry Run

```python
from vidyut.ai import PatchEngine

engine = PatchEngine()

patch = await engine.create_patch(
    file="models.py",
    instruction="Add phone field"
)

# Preview without applying
result = await engine.apply(patch, dry_run=True)

print(result.diff)        # See changes
print(result.would_work)  # Would it succeed?

# Then apply for real
await engine.apply(patch)
```

---

## Read-Only Mode

### Query-Only Operations

```python
VIDYUT = {
    "AI_QUERY_ENGINE": {
        "read_only": True,  # Default
    },
}
```

With `read_only=True`:
- SELECT queries work
- INSERT/UPDATE/DELETE are blocked
- Queries run in read-only transactions

### Production Safety

```python
# settings/production.py
VIDYUT = {
    "AI_SAFETY": {
        "read_only_mode": True,  # No writes via AI in production
    },
}
```

---

## Audit Logging

### Enable Audit Log

```python
VIDYUT = {
    "AI_SAFETY": {
        "audit_log": True,
        "audit_log_file": "logs/ai_audit.log",
    },
}
```

### Log Format

```
2024-01-15 10:30:00 | user=john | action=query | 
    query="Delete inactive users" | 
    affected=1234 | 
    status=confirmed | 
    ip=192.168.1.1

2024-01-15 10:31:00 | user=john | action=patch | 
    file=models.py | 
    instruction="Add phone field" | 
    status=applied | 
    backup=/backups/models.py.20240115103100
```

### Custom Audit Handler

```python
from vidyut.ai.safety import register_audit_handler

@register_audit_handler
async def my_audit_handler(event):
    # Send to your logging system
    await send_to_splunk(event)
    await notify_slack_channel(event)
```

### Query Audit Log

```python
from vidyut.ai.safety import get_audit_log

# Get recent actions
log = await get_audit_log(
    user="john",
    action_type="delete",
    since=datetime.now() - timedelta(days=7),
)

for entry in log:
    print(f"{entry.timestamp}: {entry.action} by {entry.user}")
```

---

## Rate Limiting

### Configuration

```python
VIDYUT = {
    "AI_SAFETY": {
        "rate_limit_enabled": True,
        "rate_limit_requests": 100,   # Max requests
        "rate_limit_window": 3600,    # Per hour
        "rate_limit_tokens": 100000,  # Max tokens per window
    },
}
```

### Per-User Limits

```python
VIDYUT = {
    "AI_SAFETY": {
        "rate_limits": {
            "default": {"requests": 100, "window": 3600},
            "admin": {"requests": 1000, "window": 3600},
            "api": {"requests": 50, "window": 3600},
        },
    },
}
```

### Handling Rate Limits

```python
from vidyut.ai.exceptions import RateLimitError

try:
    result = await engine.query("...")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
```

---

## Tool Permissions

### Restrict Available Tools

```python
VIDYUT = {
    "AI_TOOLS": {
        # Disable dangerous tools
        "data_tools": True,
        "schema_tools": True,
        "code_tools": False,    # Disable code generation
        "system_tools": False,  # Disable system commands
    },
}
```

### Require Approval for Specific Tools

```python
VIDYUT = {
    "AI_AGENT_RUNTIME": {
        "require_approval_for": [
            "delete_record",
            "run_command",
            "run_migration",
            "patch_file",
        ],
    },
}
```

### Custom Tool Permissions

```python
from vidyut.ai.tools import Tool, register_tool

@register_tool(permissions=["admin"])
class DangerousTool(Tool):
    """Requires admin permission to use."""
    
    async def check_permission(self, user):
        return user.is_admin
```

---

## Input Sanitization

### SQL Injection Prevention

All queries are parameterized:

```python
# User input
result = await engine.query("Users named 'Robert'; DROP TABLE users;--'")

# Internally becomes:
# SELECT * FROM users WHERE name = %s
# Parameter: "Robert'; DROP TABLE users;--'"
```

### Code Injection Prevention

```python
# Patch instructions are validated
patch = await engine.create_patch(
    file="models.py",
    instruction="Add field; import os; os.system('rm -rf /')",
)

# Generated code is syntax-validated before applying
if not patch.is_valid:
    print(f"Invalid: {patch.validation_error}")
```

---

## Sandboxing

### Isolated Execution

```python
VIDYUT = {
    "AI_AGENT_RUNTIME": {
        "sandbox_mode": True,  # Run in isolated environment
    },
}
```

### Resource Limits

```python
VIDYUT = {
    "AI_AGENT_RUNTIME": {
        # Prevent runaway operations
        "max_iterations": 20,
        "max_tool_calls": 50,
        "timeout_seconds": 300,
        "max_memory_mb": 512,
    },
}
```

---

## Rollback Capabilities

### Automatic Backups

```python
VIDYUT = {
    "AI_PATCH_ENGINE": {
        "create_backups": True,
        "backup_dir": ".vidyut/backups",
    },
}
```

### Manual Rollback

```bash
# Rollback last change
vidyut ai rollback

# Rollback specific patch
vidyut ai rollback --patch-id abc123

# List available rollbacks
vidyut ai rollback --list
```

### Programmatic Rollback

```python
from vidyut.ai import PatchEngine

engine = PatchEngine()

# Apply patch
result = await engine.apply(patch)

# Something went wrong? Rollback
await engine.rollback()
```

---

## Environment-Specific Safety

### Development

```python
# settings/development.py
VIDYUT = {
    "AI_MODE": True,
    "AI_SAFETY": {
        "require_confirmation": False,  # Faster iteration
        "read_only_mode": False,
        "audit_log": False,
    },
}
```

### Staging

```python
# settings/staging.py
VIDYUT = {
    "AI_MODE": True,
    "AI_SAFETY": {
        "require_confirmation": True,
        "read_only_mode": False,
        "audit_log": True,
    },
}
```

### Production

```python
# settings/production.py
VIDYUT = {
    "AI_MODE": True,
    "AI_SAFETY": {
        "require_confirmation": True,
        "read_only_mode": True,  # No writes!
        "audit_log": True,
        "rate_limit_enabled": True,
    },
}
```

---

## Security Best Practices

### 1. Use Environment Variables for API Keys

```python
# Good
"AI_API_KEY": os.getenv("OPENAI_API_KEY")

# Bad - never commit API keys!
"AI_API_KEY": "sk-abc123..."
```

### 2. Enable Audit Logging in Production

```python
"AI_SAFETY": {
    "audit_log": True,
}
```

### 3. Use Read-Only Mode for Data Exploration

```python
engine = QueryEngine(read_only=True)
```

### 4. Require Approval for Destructive Operations

```python
"AI_AGENT_RUNTIME": {
    "require_approval_for": ["delete_record", "run_migration"],
}
```

### 5. Set Appropriate Rate Limits

```python
"AI_SAFETY": {
    "rate_limit_requests": 100,
    "rate_limit_window": 3600,
}
```

### 6. Restrict Tool Access by Role

```python
@register_tool(permissions=["admin"])
class AdminOnlyTool(Tool):
    ...
```

### 7. Always Test with Dry Run First

```bash
vidyut ai patch ... --dry-run
```

---

## Monitoring and Alerts

### Alert on Suspicious Activity

```python
from vidyut.ai.safety import register_alert_handler

@register_alert_handler
async def alert_handler(event):
    if event.type == "high_risk_operation":
        await send_slack_alert(
            f"High risk AI operation by {event.user}: {event.action}"
        )
```

### Metrics Integration

```python
from vidyut.ai.safety import get_metrics

metrics = await get_metrics()
print(f"Total AI requests: {metrics.total_requests}")
print(f"Failed requests: {metrics.failed_requests}")
print(f"Rate limited: {metrics.rate_limited}")
```

---

## Related Documentation

- [AI Mode Overview](index.md)
- [Configuration](config.md)
- [Agent Runtime](agent-runtime.md)
- [Tools](tools.md)
