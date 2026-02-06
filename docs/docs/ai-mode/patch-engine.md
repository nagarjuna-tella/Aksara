# Patch Engine

Safe code modifications with preview and rollback.

---

## Overview

The Patch Engine modifies existing code safely:

- **Preview changes** before applying
- **Automatic backups** for rollback
- **Syntax validation** before save
- **Conflict detection** for concurrent changes

```python
from aksara.ai import PatchEngine

engine = PatchEngine()
patch = await engine.create_patch(
    file="models.py",
    instruction="Add 'is_featured' boolean field to Post model"
)
await engine.apply(patch)
```

---

## Quick Start

### Create a Patch

```python
from aksara.ai import PatchEngine

engine = PatchEngine()

# Create patch from instruction
patch = await engine.create_patch(
    file="models.py",
    instruction="Add email_verified boolean field to User"
)

print(patch.diff)  # See what will change
```

### Preview Changes

```python
# Dry run - see changes without applying
result = await engine.apply(patch, dry_run=True)

print(result.diff)
print(result.before)
print(result.after)
```

### Apply Changes

```python
# Apply the patch
result = await engine.apply(patch)

if result.success:
    print("Patch applied successfully")
else:
    print(f"Failed: {result.error}")
```

### Rollback

```python
# Undo the last patch
await engine.rollback()
```

---

## Creating Patches

### From Instruction

```python
patch = await engine.create_patch(
    file="models.py",
    instruction="Add phone_number field after email in User model"
)
```

### From Code Diff

```python
patch = await engine.create_patch_from_diff(
    file="models.py",
    old_code="email = fields.Email()",
    new_code="""email = fields.Email()
    phone = fields.String(max_length=20, null=True)"""
)
```

### From Template

```python
patch = await engine.create_patch_from_template(
    file="models.py",
    template="add_field",
    params={
        "model": "User",
        "field_name": "phone",
        "field_type": "String",
        "field_args": {"max_length": 20, "null": True},
    }
)
```

### Multiple Files

```python
patches = await engine.create_patches(
    instructions=[
        ("models.py", "Add status field to Order"),
        ("serializers.py", "Include status in OrderSerializer"),
        ("viewsets.py", "Add filter by status to OrderViewSet"),
    ]
)

# Apply all
for patch in patches:
    await engine.apply(patch)
```

---

## Patch Object

### Properties

```python
patch = await engine.create_patch(...)

print(patch.file)           # Target file path
print(patch.instruction)    # Original instruction
print(patch.diff)           # Unified diff format
print(patch.hunks)          # Individual change hunks
print(patch.additions)      # Lines added
print(patch.deletions)      # Lines removed
print(patch.is_valid)       # Syntax check passed
```

### Diff Format

```python
print(patch.diff)
# --- models.py (original)
# +++ models.py (modified)
# @@ -10,6 +10,7 @@
#  class User(Model):
#      email = fields.Email(unique=True)
# +    phone = fields.String(max_length=20, null=True)
#      name = fields.String(max_length=100)
```

### Hunks

```python
for hunk in patch.hunks:
    print(f"Lines {hunk.start}-{hunk.end}")
    print(f"Context: {hunk.context}")
    print(f"Changes: {hunk.changes}")
```

---

## Applying Patches

### Basic Apply

```python
result = await engine.apply(patch)

print(result.success)      # True/False
print(result.file)         # Modified file
print(result.backup_path)  # Backup location
```

### Dry Run

```python
result = await engine.apply(patch, dry_run=True)

# No file changes, just preview
print(result.would_succeed)
print(result.diff)
```

### Force Apply

```python
# Skip validation (use with caution)
result = await engine.apply(patch, force=True)
```

### With Backup

```python
# Custom backup location
result = await engine.apply(
    patch,
    backup_dir="/tmp/backups",
)

print(f"Backup at: {result.backup_path}")
```

---

## Validation

### Syntax Validation

Patches are validated before applying:

```python
patch = await engine.create_patch(
    file="models.py",
    instruction="Add invalid syntax"
)

if not patch.is_valid:
    print(f"Invalid: {patch.validation_error}")
```

### Import Validation

```python
patch = await engine.create_patch(
    file="viewsets.py",
    instruction="Add permission class",
    validate_imports=True,  # Check imports exist
)
```

### Test Validation

```python
# Run tests after applying
result = await engine.apply(
    patch,
    run_tests=True,
    test_command="pytest tests/test_models.py",
)

if not result.tests_passed:
    await engine.rollback()
```

---

## Rollback

### Rollback Last

```python
await engine.rollback()
```

### Rollback Specific

```python
# By patch ID
await engine.rollback(patch_id="abc123")

# By file
await engine.rollback(file="models.py")
```

### Rollback Multiple

```python
# Rollback last N patches
await engine.rollback(count=3)
```

### View History

```python
history = await engine.get_history()

for entry in history:
    print(f"{entry.id}: {entry.file} - {entry.instruction}")
    print(f"  Applied: {entry.applied_at}")
    print(f"  Backup: {entry.backup_path}")
```

---

## Conflict Handling

### Detection

```python
result = await engine.apply(patch)

if result.has_conflicts:
    print("Conflicts detected:")
    for conflict in result.conflicts:
        print(f"  Line {conflict.line}: {conflict.reason}")
```

### Resolution

```python
# Auto-resolve (use AI)
result = await engine.apply(
    patch,
    resolve_conflicts="auto",
)

# Manual resolution
if result.has_conflicts:
    resolved = await engine.resolve_conflicts(
        patch,
        resolutions={
            "line_15": "keep_theirs",
            "line_20": "keep_ours",
        }
    )
    await engine.apply(resolved)
```

### Merge Strategy

```python
result = await engine.apply(
    patch,
    merge_strategy="ours",    # Keep our changes on conflict
    # or "theirs", "union", "manual"
)
```

---

## Batch Operations

### Apply Multiple Patches

```python
patches = [
    await engine.create_patch("models.py", "Add field A"),
    await engine.create_patch("models.py", "Add field B"),
    await engine.create_patch("serializers.py", "Add fields to serializer"),
]

# Apply all or none
result = await engine.apply_batch(
    patches,
    atomic=True,  # Rollback all if any fails
)
```

### Transaction Mode

```python
async with engine.transaction() as tx:
    await tx.apply(patch1)
    await tx.apply(patch2)
    await tx.apply(patch3)
    # All applied on exit, or all rolled back on error
```

---

## CLI Usage

### Create and Apply

```bash
aksara ai patch models.py "Add phone field to User"
```

### Preview Only

```bash
aksara ai patch models.py "Add phone field" --dry-run
```

### Interactive Mode

```bash
aksara ai patch models.py "Add phone field" --interactive

Preview:
  + phone = fields.String(max_length=20, null=True)

Apply this change? [y/N/e(dit)]
```

### From File

```bash
# Apply patch from file
aksara ai patch --file changes.patch
```

---

## Integration

### With Codegen

```python
from aksara.ai import Codegen, PatchEngine

gen = Codegen()
engine = PatchEngine()

# Generate new code
new_code = await gen.model("Comment with text, author, post")

# Create patch to add it
patch = await engine.create_patch_from_code(
    file="models.py",
    code=new_code,
    position="end",  # Add at end of file
)

await engine.apply(patch)
```

### With Planner

```python
from aksara.ai import Planner, PatchEngine

planner = Planner()
engine = PatchEngine()

# Create plan
plan = await planner.create("Add tagging system")

# Execute patches from plan
for step in plan.steps:
    if step.type == "patch":
        patch = await engine.create_patch(
            file=step.file,
            instruction=step.instruction,
        )
        await engine.apply(patch)
```

---

## Configuration

```python
# settings.py
AKSARA = {
    "AI_PATCH_ENGINE": {
        # Validation
        "validate_syntax": True,
        "validate_imports": True,
        "run_tests_after": False,
        
        # Backups
        "create_backups": True,
        "backup_dir": ".aksara/backups",
        "max_backup_age_days": 30,
        
        # Conflicts
        "default_merge_strategy": "manual",
        
        # Safety
        "require_dry_run_first": False,
        "max_changes_per_patch": 100,  # Lines
    },
}
```

---

## Best Practices

### 1. Always Preview First

```python
result = await engine.apply(patch, dry_run=True)
print(result.diff)  # Review before applying
await engine.apply(patch)
```

### 2. Use Atomic Batches

```python
# Don't leave partial changes
async with engine.transaction():
    await engine.apply(model_patch)
    await engine.apply(serializer_patch)
    await engine.apply(viewset_patch)
```

### 3. Keep Patches Small

```python
# Better: multiple small patches
patch1 = await engine.create_patch(file, "Add field A")
patch2 = await engine.create_patch(file, "Add field B")

# Worse: one large patch
patch = await engine.create_patch(file, "Add fields A, B, C, D, E")
```

---

## Related Documentation

- [AI Mode Overview](index.md)
- [Codegen](codegen.md)
- [Planner](planner.md)
- [Safety](safety.md)
