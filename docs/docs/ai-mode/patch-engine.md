# Patch engine

!!! warning "Experimental"
    Code generation and patch application are outside the stable v0.6
    contract. Aksara does not expose a `PatchEngine` class.

The actual API uses declarative patch models and functions. Preview is the
recommended first step:

```python
from aksara.ai.patch import (
    AiPatchOperation,
    AiPatchRequest,
    apply_ai_patches,
)

request = AiPatchRequest(
    reason="Add a developer note",
    operations=[
        AiPatchOperation(
            type="insert_text",
            path="app/models.py",
            start_line=1,
            text="# Reviewed before application\n",
        )
    ],
)

preview = apply_ai_patches(request, project_root=".", preview=True)
assert preview.preview_only
for change in preview.files_changed.values():
    print(change.diff)
```

Applying a request requires an explicit confirmation value:

```python
applied = apply_ai_patches(
    request,
    project_root=".",
    confirm_header="true",
)
print(applied.applied)
```

`validate_patch_request()`, `preview_patch_diff()`, and `rollback_patches()` are
also available from `aksara.ai.patch`. Protected paths, path containment,
syntax, and dangerous-code checks reduce accidental damage, but callers remain
responsible for review, tests, source control, and authorization. This API is
not an autonomous code-maintenance system.
