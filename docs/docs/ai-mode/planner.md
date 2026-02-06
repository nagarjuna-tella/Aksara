# Planner

Multi-step task planning for complex operations.

---

## Overview

The Planner breaks down complex tasks into executable steps:

```python
from aksara.ai import Planner

planner = Planner()
plan = await planner.create("Add a tagging system to the blog")

for step in plan.steps:
    print(f"{step.order}. {step.description}")
```

---

## Quick Start

### Create a Plan

```python
from aksara.ai import Planner

planner = Planner()

plan = await planner.create(
    "Add user authentication with email verification"
)

print(plan.summary)
# 1. Create User model with email, password, is_verified fields
# 2. Create EmailVerification model with token, user FK, expires_at
# 3. Add UserSerializer with password hashing
# 4. Create AuthViewSet with register, login, verify endpoints
# 5. Add email sending utility
# 6. Create migration for new models
# 7. Add tests for authentication flow
```

### Execute a Plan

```python
result = await planner.execute(plan)

print(f"Completed: {result.completed_steps}/{result.total_steps}")
```

---

## Plan Structure

### Steps

```python
plan = await planner.create("Add commenting to posts")

for step in plan.steps:
    print(step.order)        # 1, 2, 3, ...
    print(step.type)         # "create_model", "create_viewset", etc.
    print(step.description)  # Human-readable description
    print(step.file)         # Target file
    print(step.code)         # Generated code (if applicable)
    print(step.dependencies) # Steps this depends on
```

### Step Types

| Type | Description |
|------|-------------|
| `create_model` | Create a new model class |
| `modify_model` | Add/change fields on existing model |
| `create_viewset` | Create a new ViewSet |
| `modify_viewset` | Add actions/modify ViewSet |
| `create_serializer` | Create a serializer |
| `create_migration` | Generate migration |
| `create_test` | Create test file |
| `modify_file` | General file modification |
| `run_command` | Execute shell command |

### Dependencies

```python
# Steps can depend on other steps
step = plan.steps[3]  # Create ViewSet

print(step.dependencies)
# [1, 2]  # Depends on Model and Serializer creation
```

---

## Creating Plans

### From Description

```python
plan = await planner.create(
    "Add a rating system where users can rate products 1-5 stars"
)
```

### With Constraints

```python
plan = await planner.create(
    "Add user profiles",
    constraints={
        "models_only": False,  # Include API
        "include_tests": True,
        "include_migrations": True,
    }
)
```

### With Context

```python
from aksara.ai import ContextEngine

context = await ContextEngine().gather("existing models")

plan = await planner.create(
    "Add order history to users",
    context=context,  # Aware of existing models
)
```

### Incremental Planning

```python
# Plan builds on previous work
plan1 = await planner.create("Create Product model")
await planner.execute(plan1)

plan2 = await planner.create(
    "Add reviews to products",
    previous_plans=[plan1],  # Knows about Product
)
```

---

## Plan Execution

### Execute All Steps

```python
result = await planner.execute(plan)

print(result.success)        # True if all steps completed
print(result.completed_steps)
print(result.failed_steps)
print(result.skipped_steps)
```

### Execute Step by Step

```python
for step in plan.steps:
    print(f"Executing: {step.description}")
    
    result = await planner.execute_step(step)
    
    if not result.success:
        print(f"Failed: {result.error}")
        break
```

### Dry Run

```python
# Preview all changes
result = await planner.execute(plan, dry_run=True)

for step_result in result.step_results:
    print(f"Would: {step_result.description}")
    if step_result.diff:
        print(step_result.diff)
```

### Interactive Execution

```python
result = await planner.execute(
    plan,
    interactive=True,  # Confirm each step
)
```

CLI equivalent:

```bash
aksara ai plan "Add tagging" --interactive

Step 1/5: Create Tag model
  + class Tag(Model):
  +     name = fields.String(max_length=50, unique=True)

Execute this step? [y/N/s(kip)/q(uit)]
```

---

## Plan Modification

### Add Steps

```python
plan.add_step(
    type="create_test",
    description="Add integration tests",
    file="tests/test_integration.py",
    after=4,  # After step 4
)
```

### Remove Steps

```python
plan.remove_step(5)  # Remove step 5
```

### Reorder Steps

```python
plan.move_step(from_order=5, to_order=2)
```

### Edit Steps

```python
step = plan.steps[2]
step.code = "# Modified code..."
```

---

## Plan Templates

### Use Built-in Templates

```python
# CRUD feature template
plan = await planner.from_template(
    "crud_feature",
    model_name="Product",
    fields=["name", "price", "description"],
)

# Auth feature template
plan = await planner.from_template(
    "authentication",
    include_social=True,
    include_2fa=False,
)
```

### Available Templates

| Template | Description |
|----------|-------------|
| `crud_feature` | Model + Serializer + ViewSet + Tests |
| `authentication` | User + Auth endpoints |
| `multi_tenant` | Tenant model + middleware |
| `tagging` | Tag model + M2M relation |
| `commenting` | Comment model + nested serializer |
| `rating` | Rating model + aggregation |

### Create Custom Templates

```python
from aksara.ai.planner import PlanTemplate

@planner.register_template
class AuditLogTemplate(PlanTemplate):
    name = "audit_log"
    
    steps = [
        {"type": "create_model", "description": "Create AuditLog model"},
        {"type": "create_middleware", "description": "Create audit middleware"},
        {"type": "create_migration", "description": "Generate migration"},
    ]
    
    async def customize(self, params):
        # Customize steps based on params
        ...
```

---

## Error Handling

### Step Failures

```python
result = await planner.execute(plan)

if not result.success:
    for failure in result.failures:
        print(f"Step {failure.step} failed: {failure.error}")
```

### Rollback on Failure

```python
result = await planner.execute(
    plan,
    rollback_on_failure=True,  # Default: True
)

# If step 3 fails, steps 1-2 are rolled back
```

### Continue on Failure

```python
result = await planner.execute(
    plan,
    continue_on_failure=True,
    skip_dependent=True,  # Skip steps that depend on failed step
)
```

### Retry Failed Steps

```python
if not result.success:
    # Retry just the failed steps
    retry_result = await planner.retry_failed(result)
```

---

## CLI Usage

### Create Plan

```bash
aksara ai plan "Add user profiles"

📋 Plan: Add user profiles

Step 1: Create UserProfile model
  File: models.py
  Type: create_model

Step 2: Create UserProfileSerializer
  File: serializers.py
  Type: create_serializer

Step 3: Create UserProfileViewSet
  File: viewsets.py
  Type: create_viewset

Step 4: Generate migration
  File: migrations/0005_userprofile.py
  Type: create_migration

Execute plan? [y/N]
```

### Execute Plan

```bash
aksara ai plan "Add tagging" --execute
```

### Save Plan

```bash
aksara ai plan "Add tagging" --save tagging-plan.json
```

### Load and Execute

```bash
aksara ai plan --load tagging-plan.json --execute
```

---

## Integration

### With Patch Engine

```python
from aksara.ai import Planner, PatchEngine

planner = Planner()
patch_engine = PatchEngine()

plan = await planner.create("Add field to User")

for step in plan.steps:
    if step.type == "modify_model":
        patch = await patch_engine.create_patch(
            file=step.file,
            instruction=step.description,
        )
        await patch_engine.apply(patch)
```

### With Agent Runtime

```python
from aksara.ai import AgentRuntime

runtime = AgentRuntime()

# Agent uses planner internally for complex tasks
result = await runtime.execute(
    "Add a complete e-commerce checkout flow"
)
# Internally creates and executes a plan
```

---

## Configuration

```python
# settings.py
AKSARA = {
    "AI_PLANNER": {
        # Execution
        "rollback_on_failure": True,
        "max_steps": 20,
        "step_timeout_seconds": 60,
        
        # Validation
        "validate_each_step": True,
        "run_tests_after": False,
        
        # Interactive
        "default_interactive": False,
        "confirm_destructive": True,
    },
}
```

---

## Best Practices

### 1. Start with Dry Run

```python
# Preview first
result = await planner.execute(plan, dry_run=True)
print(result.summary)

# Then execute
await planner.execute(plan)
```

### 2. Use Context for Better Plans

```python
context = await ContextEngine().gather("related code")
plan = await planner.create(task, context=context)
```

### 3. Review Generated Code

```python
for step in plan.steps:
    if step.code:
        print(f"Step {step.order}:")
        print(step.code)
        input("Press Enter to continue...")
```

### 4. Keep Plans Focused

```python
# Better: focused plans
plan1 = await planner.create("Add Tag model")
plan2 = await planner.create("Add tagging to Posts")

# Worse: too broad
plan = await planner.create("Add complete tagging with search, filters, and analytics")
```

---

## Related Documentation

- [AI Mode Overview](index.md)
- [Codegen](codegen.md)
- [Patch Engine](patch-engine.md)
- [Agent Runtime](agent-runtime.md)
