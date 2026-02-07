# AI Route Hints

> **v0.5.13** Per-View AI Hints (Route-Level AI Metadata)

AI Route Hints provide structured metadata for each view/route in your Aksara application. This metadata helps LLMs understand what each endpoint does, how risky operations are, and how to use them effectively.

## Overview

Route hints are pure metadata—they don't affect request handling but provide:

- **Title & Description**: Human-readable info for LLMs
- **Usage Kind**: Whether the route reads, writes, or requires admin access
- **Risk Level**: How risky the operation is (low/medium/high)
- **Examples**: Sample prompts, inputs, and outputs
- **Recommendations**: Suggested models/providers for the operation

## Quick Start

### Basic Decorator Usage

```python
from aksara.ai import ai_route_hint
from aksara.api import AksaraViewSet

class UserViewSet(AksaraViewSet):
    model = User
    
    @ai_route_hint(
        title="List Users",
        description="Returns a paginated list of active users.",
        usage_kind="read_only",
        risk_level="low",
        example_prompt="Show me all users",
    )
    def list(self, request):
        return super().list(request)
    
    @ai_route_hint(
        title="Delete User Account",
        description="Permanently removes a user and all associated data.",
        usage_kind="admin",
        risk_level="high",
        example_prompt="Delete the user with email john@example.com",
    )
    def destroy(self, request, pk=None):
        return super().destroy(request, pk)
```

### Class-Level Defaults

Set default risk/usage for all actions in a viewset:

```python
from aksara.ai import ai_route_hint, set_view_default_hint

class AdminViewSet(AksaraViewSet):
    model = AdminConfig
    
set_view_default_hint(AdminViewSet, risk_level="high", usage_kind="admin")
```

Actions in `AdminViewSet` will inherit `risk_level="high"` and `usage_kind="admin"` unless overridden.

## Decorator Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `title` | `str` | Required | Human-readable title for the action |
| `description` | `str` | `None` | Detailed description of what the action does |
| `usage_kind` | `"read_only" \| "write" \| "admin"` | `"read_only"` | Type of operation |
| `risk_level` | `"low" \| "medium" \| "high"` | `"low"` | Risk assessment |
| `example_prompt` | `str` | `None` | Example natural language prompt |
| `example_input` | `str` | `None` | Example input (JSON string) |
| `example_output` | `str` | `None` | Example output (JSON string) |
| `recommended_model` | `str` | `None` | Suggested AI model for this operation |
| `recommended_provider` | `str` | `None` | Suggested AI provider for this operation |

## Risk Levels

| Level | Color | Description | Examples |
|-------|-------|-------------|----------|
| `low` | 🟢 Green | Safe, read-only operations | List, retrieve, search |
| `medium` | 🟡 Yellow | Modifying operations with safeguards | Create, update |
| `high` | 🔴 Red | Destructive or admin operations | Delete, bulk delete, config changes |

## Usage Kinds

| Kind | Description | Typical Actions |
|------|-------------|-----------------|
| `read_only` | Only reads data, no side effects | list, retrieve, search |
| `write` | Creates or modifies data | create, update, partial_update |
| `admin` | Admin-level operations | destroy, bulk_delete, config |

## CLI Integration

View all hints via the CLI:

```bash
# List all hints
aksara ai hints

# Filter by view
aksara ai hints --view UserViewSet

# Filter by route
aksara ai hints --route destroy

# Show only high-risk hints
aksara ai hints --risk high

# JSON output
aksara ai hints --format json
```

### Example Output

```
  ⚡ Aksara - AI Route Hints (env: development)

  Total: 5 hints
  Risk breakdown: 1 high | 2 medium | 2 low

  [HIGH] Delete User Account
      Path: /api/users/{id}
      View: UserViewSet.destroy | Usage: admin
      Desc: Permanently removes a user and all associated data.
      Example: "Delete the user with email john@example.com"

  [MEDIUM] Create User
      Path: /api/users
      View: UserViewSet.create | Usage: write
      ...
```

## Studio Integration

Hints appear in the Aksara Studio UI under the **AI Profiles** section:

1. Navigate to Studio (`/studio/`)
2. Click **AI Profiles** in the sidebar
3. Scroll to the **AI Route Hints** panel

The panel shows:
- Total hint count
- Risk level breakdown
- Searchable/filterable list of all hints
- Expandable details for each hint

## Context Integration

Hints are automatically included in the AI context:

```python
from aksara.ai import build_full_ai_context

context = build_full_ai_context(settings)

# Access hints
print(f"Total hints: {context.ai_hint_count}")
for hint in context.ai_hints:
    print(f"  - {hint.title}: {hint.risk_level}")
```

The `AiFullContext` model includes:
- `ai_hints: List[AiRouteHintInfo]` — List of all route hints
- `ai_hint_count: int` — Total number of hints

## Best Practices

### 1. Annotate Risky Operations

Always add hints to destructive or admin operations:

```python
@ai_route_hint(
    title="Bulk Delete Users",
    description="Permanently deletes multiple users. Cannot be undone.",
    risk_level="high",
    usage_kind="admin",
)
def bulk_destroy(self, request):
    ...
```

### 2. Provide Examples

Examples help LLMs understand expected usage:

```python
@ai_route_hint(
    title="Create Product",
    example_prompt="Create a new product called 'Widget' priced at $9.99",
    example_input='{"name": "Widget", "price": 9.99}',
    example_output='{"id": 1, "name": "Widget", "price": 9.99}',
)
def create(self, request):
    ...
```

### 3. Use Descriptive Titles

Titles should be action-oriented and clear:

- ✅ "List Active Users"
- ✅ "Delete User Account"
- ❌ "list"
- ❌ "UserViewSet action"

### 4. Set Class Defaults for Admin Views

```python
class AuditLogViewSet(AksaraViewSet):
    model = AuditLog
    
set_view_default_hint(AuditLogViewSet, risk_level="medium", usage_kind="read_only")
```

## API Reference

### Models

```python
from aksara.ai import AiRouteHint, AiHintSet, AiRiskLevel, AiUsageKind

# Type literals
AiRiskLevel = Literal["low", "medium", "high"]
AiUsageKind = Literal["read_only", "write", "admin"]

# Route hint model
class AiRouteHint(AksaraModel):
    title: str
    description: Optional[str]
    view_name: Optional[str]
    route_name: Optional[str]
    path: Optional[str]
    http_method: Optional[str]
    usage_kind: AiUsageKind
    risk_level: AiRiskLevel
    example_prompt: Optional[str]
    example_input: Optional[str]
    example_output: Optional[str]
    recommended_model: Optional[str]
    recommended_provider: Optional[str]

# Hint set model
class AiHintSet(AksaraModel):
    hints: List[AiRouteHint]
    total_count: int  # computed
    hints_by_risk: Dict[str, int]  # computed
```

### Functions

```python
from aksara.ai import (
    ai_route_hint,          # Decorator
    set_view_default_hint,  # Set class defaults
    get_ai_route_hint,      # Get hint from function
    extract_hints_from_viewset,  # Extract from viewset class
    extract_hints_from_app,      # Extract from app module
    build_ai_hint_set,           # Build complete hint set
)
```

## See Also

- [AI Profiles & Providers](providers.md) — Configure AI providers
- [Context Engine](context-engine.md) — AI context building
- [CLI Reference](../cli/index.md) — Full CLI documentation
