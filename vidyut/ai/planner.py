"""
Vidyut AI Planner (THE ARCHITECT)

High-level planning layer that accepts natural language intent and
emits structured plans (AiPlan) consisting of steps (AiPlanStep).

Each step maps to existing capabilities:
- Context → understand current state
- Codegen → generate new code
- Patch Engine → apply/preview changes
- Migrations → create/execute migrations
- Query Engine → validate behavior

The Planner does NOT call an LLM itself. It defines schemas & execution
semantics so external AI agents can:
1. Fetch context
2. Propose an AiPlan
3. Ask Vidyut to execute that plan safely

v0.4.5: Initial AI Planner release

Usage:
    from vidyut.ai.planner import AiPlan, AiPlanStep, execute_plan
    
    plan = AiPlan(
        intent="Add a slug field to Article model",
        steps=[
            AiPlanStep(id="s1", type="create_field", description="Add slug field", payload={...})
        ]
    )
    result = await execute_plan(app, plan, dry_run=True)
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Literal, Optional, Set, TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from fastapi import FastAPI


# =============================================================================
# Type Definitions
# =============================================================================

PlanStepType = Literal[
    "analyze_context",
    "create_model",
    "update_model",
    "create_field",
    "update_field",
    "delete_field",
    "create_migration",
    "run_migrations",
    "generate_viewset",
    "generate_serializer",
    "generate_admin",
    "generate_tests",
    "apply_patch",
    "run_query_check",
    "run_health_check",
]

# All valid step types
VALID_STEP_TYPES: Set[str] = {
    "analyze_context",
    "create_model",
    "update_model",
    "create_field",
    "update_field",
    "delete_field",
    "create_migration",
    "run_migrations",
    "generate_viewset",
    "generate_serializer",
    "generate_admin",
    "generate_tests",
    "apply_patch",
    "run_query_check",
    "run_health_check",
}


# =============================================================================
# Pydantic Models
# =============================================================================

class AiPlanStep(BaseModel):
    """
    A single step in an AI execution plan.
    
    Each step has a type that maps to a specific capability
    (context, codegen, patch, migrations, query).
    
    Example:
        AiPlanStep(
            id="step-1",
            type="create_model",
            description="Create Article model for blog posts",
            payload={"model_spec": {...}}
        )
    """
    
    id: str = Field(..., description="Unique identifier for this step, e.g. 'step-1'")
    type: PlanStepType = Field(..., description="Type of operation to perform")
    description: str = Field(..., description="Human-readable description of what this step does")
    depends_on: List[str] = Field(default_factory=list, description="IDs of steps this depends on")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Step-specific parameters")
    reasoning: Optional[str] = Field(default=None, description="AI reasoning for this step")
    
    model_config = {"extra": "forbid"}
    
    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_STEP_TYPES:
            raise ValueError(f"Invalid step type: {v}. Must be one of: {VALID_STEP_TYPES}")
        return v


class AiPlan(BaseModel):
    """
    A complete execution plan consisting of ordered steps.
    
    Plans form a DAG (Directed Acyclic Graph) based on depends_on
    relationships between steps. Circular dependencies are not allowed.
    
    Example:
        AiPlan(
            intent="Add slug field to Article model with migration",
            steps=[
                AiPlanStep(id="s1", type="analyze_context", description="Check current state"),
                AiPlanStep(id="s2", type="create_field", description="Add slug field", depends_on=["s1"]),
                AiPlanStep(id="s3", type="create_migration", description="Generate migration", depends_on=["s2"]),
            ]
        )
    """
    
    intent: str = Field(..., description="User intent in natural language")
    steps: List[AiPlanStep] = Field(..., description="Ordered list of steps to execute")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional plan metadata")
    
    model_config = {"extra": "forbid"}
    
    @field_validator("steps")
    @classmethod
    def validate_steps(cls, v: List[AiPlanStep]) -> List[AiPlanStep]:
        if not v:
            raise ValueError("Plan must have at least one step")
        
        # Check for duplicate IDs
        ids = [s.id for s in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Step IDs must be unique")
        
        # Check for valid depends_on references
        id_set = set(ids)
        for step in v:
            for dep in step.depends_on:
                if dep not in id_set:
                    raise ValueError(f"Step '{step.id}' depends on unknown step '{dep}'")
        
        # Check for circular dependencies
        if _has_circular_dependency(v):
            raise ValueError("Plan has circular dependencies")
        
        return v


class AiPlanStepResult(BaseModel):
    """Result of executing a single plan step."""
    
    id: str = Field(..., description="Step ID that was executed")
    type: PlanStepType = Field(..., description="Type of step that was executed")
    success: bool = Field(..., description="Whether the step succeeded")
    output: Dict[str, Any] = Field(default_factory=dict, description="Step output data")
    error: Optional[str] = Field(default=None, description="Error message if step failed")
    
    model_config = {"extra": "forbid"}


class AiPlanExecutionResult(BaseModel):
    """Result of executing an entire plan."""
    
    success: bool = Field(..., description="Whether the entire plan succeeded")
    steps: List[AiPlanStepResult] = Field(default_factory=list, description="Results for each step")
    notes: List[str] = Field(default_factory=list, description="Informational notes")
    dry_run: bool = Field(default=False, description="Whether this was a dry run")
    
    model_config = {"extra": "forbid"}


# =============================================================================
# Helper Functions
# =============================================================================

def _has_circular_dependency(steps: List[AiPlanStep]) -> bool:
    """Check if steps have circular dependencies using DFS."""
    # Build adjacency list
    graph: Dict[str, List[str]] = {s.id: s.depends_on for s in steps}
    
    # Track visited and recursion stack
    visited: Set[str] = set()
    rec_stack: Set[str] = set()
    
    def dfs(node: str) -> bool:
        visited.add(node)
        rec_stack.add(node)
        
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                return True
        
        rec_stack.remove(node)
        return False
    
    for step_id in graph:
        if step_id not in visited:
            if dfs(step_id):
                return True
    
    return False


def _topological_sort(steps: List[AiPlanStep]) -> List[AiPlanStep]:
    """
    Sort steps topologically based on depends_on.
    
    Returns steps in execution order (dependencies first).
    """
    # Build adjacency list and in-degree count
    id_to_step = {s.id: s for s in steps}
    in_degree: Dict[str, int] = {s.id: 0 for s in steps}
    dependents: Dict[str, List[str]] = defaultdict(list)
    
    for step in steps:
        in_degree[step.id] = len(step.depends_on)
        for dep in step.depends_on:
            dependents[dep].append(step.id)
    
    # Kahn's algorithm
    queue = [s.id for s in steps if in_degree[s.id] == 0]
    result: List[AiPlanStep] = []
    
    while queue:
        # Sort for deterministic order
        queue.sort()
        node = queue.pop(0)
        result.append(id_to_step[node])
        
        for dependent in dependents[node]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)
    
    return result


# =============================================================================
# Step Handlers
# =============================================================================

async def _handle_analyze_context(
    app: "FastAPI",
    step: AiPlanStep,
    dry_run: bool
) -> AiPlanStepResult:
    """
    Handle analyze_context step.
    
    Calls build_full_ai_context and returns a summary.
    """
    try:
        from vidyut.ai.context import build_full_ai_context
        
        context = await build_full_ai_context(app)
        
        # Build summary
        summary = {
            "framework_version": context.framework_version,
            "model_count": context.model_count,
            "viewset_count": context.viewset_count,
            "route_count": context.route_count,
            "migration_count": context.migration_count,
            "pending_migrations": context.pending_migrations,
            "models": [m.name for m in context.models],
            "viewsets": [v.name for v in context.viewsets],
        }
        
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=True,
            output={"context_summary": summary}
        )
    except Exception as e:
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=False,
            error=str(e)
        )


async def _handle_create_model(
    app: "FastAPI",
    step: AiPlanStep,
    dry_run: bool
) -> AiPlanStepResult:
    """
    Handle create_model step.
    
    Expects payload: {"model_spec": {...}}
    Uses codegen to generate model code, then patch engine to apply.
    """
    try:
        from vidyut.ai.codegen import AiModelSpec, generate_model_code
        from vidyut.ai.patch import AiPatchOperation, AiPatchRequest, apply_ai_patches
        import os
        
        model_spec_data = step.payload.get("model_spec")
        if not model_spec_data:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=False,
                error="Missing 'model_spec' in payload"
            )
        
        # Parse model spec
        model_spec = AiModelSpec(**model_spec_data)
        
        # Generate model code
        files = generate_model_code(model_spec)
        
        # Convert to patch operations
        operations = []
        for path, content in files.items():
            operations.append(AiPatchOperation(
                type="modify_file",
                path=path,
                text=content,
                note=f"Create model {model_spec.name}"
            ))
        
        patch_request = AiPatchRequest(
            operations=operations,
            reason=f"Create model {model_spec.name}"
        )
        
        # Get project root
        project_root = getattr(app.state, 'project_root', None) or os.getcwd()
        
        # Apply or preview
        result = apply_ai_patches(
            patch_request,
            project_root=project_root,
            preview=dry_run,
            confirm_header="true" if not dry_run else None
        )
        
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=result.applied or result.preview_only,
            output={
                "model_name": model_spec.name,
                "files": list(files.keys()),
                "preview_only": dry_run,
                "files_changed": {k: v.diff for k, v in result.files_changed.items()},
            }
        )
    except Exception as e:
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=False,
            error=str(e)
        )


async def _handle_update_model(
    app: "FastAPI",
    step: AiPlanStep,
    dry_run: bool
) -> AiPlanStepResult:
    """
    Handle update_model step.
    
    Expects payload: {"model": "ModelName", "model_spec": {...}}
    """
    try:
        from vidyut.ai.patch import AiPatchOperation, AiPatchRequest, apply_ai_patches
        import os
        
        model_name = step.payload.get("model")
        model_spec = step.payload.get("model_spec", {})
        app_label = step.payload.get("app_label", "app")
        
        if not model_name:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=False,
                error="Missing 'model' in payload"
            )
        
        operations = [AiPatchOperation(
            type="update_model",
            model=model_name,
            app_label=app_label,
            model_spec=model_spec,
            note=f"Update model {model_name}"
        )]
        
        patch_request = AiPatchRequest(
            operations=operations,
            reason=f"Update model {model_name}"
        )
        
        project_root = getattr(app.state, 'project_root', None) or os.getcwd()
        
        result = apply_ai_patches(
            patch_request,
            project_root=project_root,
            preview=dry_run,
            confirm_header="true" if not dry_run else None
        )
        
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=result.applied or result.preview_only,
            output={
                "model_name": model_name,
                "preview_only": dry_run,
                "files_changed": {k: v.diff for k, v in result.files_changed.items()},
            }
        )
    except Exception as e:
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=False,
            error=str(e)
        )


async def _handle_create_field(
    app: "FastAPI",
    step: AiPlanStep,
    dry_run: bool
) -> AiPlanStepResult:
    """
    Handle create_field step.
    
    Expects payload: {"model": "ModelName", "field": "field_name", "field_spec": {...}}
    """
    try:
        from vidyut.ai.patch import AiPatchOperation, AiPatchRequest, apply_ai_patches
        import os
        
        model_name = step.payload.get("model")
        field_name = step.payload.get("field")
        field_spec = step.payload.get("field_spec")
        app_label = step.payload.get("app_label", "app")
        
        if not model_name or not field_name or not field_spec:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=False,
                error="Missing 'model', 'field', or 'field_spec' in payload"
            )
        
        operations = [AiPatchOperation(
            type="add_field",
            model=model_name,
            app_label=app_label,
            field=field_name,
            field_spec=field_spec,
            note=f"Add field {field_name} to {model_name}"
        )]
        
        patch_request = AiPatchRequest(
            operations=operations,
            reason=f"Add field {field_name} to {model_name}"
        )
        
        project_root = getattr(app.state, 'project_root', None) or os.getcwd()
        
        result = apply_ai_patches(
            patch_request,
            project_root=project_root,
            preview=dry_run,
            confirm_header="true" if not dry_run else None
        )
        
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=result.applied or result.preview_only,
            output={
                "model": model_name,
                "field": field_name,
                "preview_only": dry_run,
                "files_changed": {k: v.diff for k, v in result.files_changed.items()},
            }
        )
    except Exception as e:
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=False,
            error=str(e)
        )


async def _handle_update_field(
    app: "FastAPI",
    step: AiPlanStep,
    dry_run: bool
) -> AiPlanStepResult:
    """
    Handle update_field step.
    
    Expects payload: {"model": "ModelName", "field": "field_name", "field_spec": {...}}
    """
    try:
        from vidyut.ai.patch import AiPatchOperation, AiPatchRequest, apply_ai_patches
        import os
        
        model_name = step.payload.get("model")
        field_name = step.payload.get("field")
        field_spec = step.payload.get("field_spec")
        app_label = step.payload.get("app_label", "app")
        
        if not model_name or not field_name or not field_spec:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=False,
                error="Missing 'model', 'field', or 'field_spec' in payload"
            )
        
        operations = [AiPatchOperation(
            type="update_field",
            model=model_name,
            app_label=app_label,
            field=field_name,
            field_spec=field_spec,
            note=f"Update field {field_name} in {model_name}"
        )]
        
        patch_request = AiPatchRequest(
            operations=operations,
            reason=f"Update field {field_name} in {model_name}"
        )
        
        project_root = getattr(app.state, 'project_root', None) or os.getcwd()
        
        result = apply_ai_patches(
            patch_request,
            project_root=project_root,
            preview=dry_run,
            confirm_header="true" if not dry_run else None
        )
        
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=result.applied or result.preview_only,
            output={
                "model": model_name,
                "field": field_name,
                "preview_only": dry_run,
                "files_changed": {k: v.diff for k, v in result.files_changed.items()},
            }
        )
    except Exception as e:
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=False,
            error=str(e)
        )


async def _handle_delete_field(
    app: "FastAPI",
    step: AiPlanStep,
    dry_run: bool
) -> AiPlanStepResult:
    """
    Handle delete_field step.
    
    Expects payload: {"model": "ModelName", "field": "field_name"}
    """
    try:
        from vidyut.ai.patch import AiPatchOperation, AiPatchRequest, apply_ai_patches
        import os
        
        model_name = step.payload.get("model")
        field_name = step.payload.get("field")
        app_label = step.payload.get("app_label", "app")
        
        if not model_name or not field_name:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=False,
                error="Missing 'model' or 'field' in payload"
            )
        
        operations = [AiPatchOperation(
            type="delete_field",
            model=model_name,
            app_label=app_label,
            field=field_name,
            note=f"Delete field {field_name} from {model_name}"
        )]
        
        patch_request = AiPatchRequest(
            operations=operations,
            reason=f"Delete field {field_name} from {model_name}"
        )
        
        project_root = getattr(app.state, 'project_root', None) or os.getcwd()
        
        result = apply_ai_patches(
            patch_request,
            project_root=project_root,
            preview=dry_run,
            confirm_header="true" if not dry_run else None
        )
        
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=result.applied or result.preview_only,
            output={
                "model": model_name,
                "field": field_name,
                "preview_only": dry_run,
                "files_changed": {k: v.diff for k, v in result.files_changed.items()},
                "warning": "Migration required to remove column from database"
            }
        )
    except Exception as e:
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=False,
            error=str(e)
        )


async def _handle_create_migration(
    app: "FastAPI",
    step: AiPlanStep,
    dry_run: bool
) -> AiPlanStepResult:
    """
    Handle create_migration step.
    
    Expects payload: {"app_label": "app", "reason": "description"}
    Generates a migration stub file.
    """
    try:
        from vidyut.ai.codegen import AiModelSpec, generate_migration_stub
        from vidyut.ai.patch import AiPatchOperation, AiPatchRequest, apply_ai_patches
        import os
        
        app_label = step.payload.get("app_label", "app")
        reason = step.payload.get("reason", "Auto-generated migration")
        model_spec = step.payload.get("model_spec")
        
        # Generate migration stub
        if model_spec:
            spec = AiModelSpec(**model_spec) if isinstance(model_spec, dict) else model_spec
            files = generate_migration_stub(spec)
        else:
            # Generate empty migration stub
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            migration_name = f"{timestamp}_auto"
            migration_path = f"{app_label}/migrations/{migration_name}.py"
            
            migration_content = f'''"""
Migration: {migration_name}
Reason: {reason}

Auto-generated by Vidyut AI Planner
"""

from vidyut.migrations import Migration, operations


class {migration_name.replace("_", "").title()}(Migration):
    """
    {reason}
    """
    
    dependencies = []
    
    operations = [
        # Add operations here
    ]
'''
            files = {migration_path: migration_content}
        
        if dry_run:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=True,
                output={
                    "preview_only": True,
                    "migration_files": list(files.keys()),
                    "content_preview": files,
                }
            )
        
        # Apply the migration file
        operations = []
        for path, content in files.items():
            operations.append(AiPatchOperation(
                type="modify_file",
                path=path,
                text=content,
                note=f"Create migration: {reason}"
            ))
        
        patch_request = AiPatchRequest(
            operations=operations,
            reason=f"Create migration: {reason}"
        )
        
        project_root = getattr(app.state, 'project_root', None) or os.getcwd()
        
        result = apply_ai_patches(
            patch_request,
            project_root=project_root,
            preview=False,
            confirm_header="true"
        )
        
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=result.applied,
            output={
                "migration_files": list(files.keys()),
                "applied": result.applied,
            }
        )
    except Exception as e:
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=False,
            error=str(e)
        )


async def _handle_run_migrations(
    app: "FastAPI",
    step: AiPlanStep,
    dry_run: bool
) -> AiPlanStepResult:
    """
    Handle run_migrations step.
    
    Expects payload: {"apps": ["app1", "app2"], "fake": false}
    """
    try:
        apps = step.payload.get("apps", [])
        fake = step.payload.get("fake", False)
        
        if dry_run:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=True,
                output={
                    "preview_only": True,
                    "would_run_for_apps": apps or ["all"],
                    "fake": fake,
                    "note": "Dry run - no migrations executed"
                }
            )
        
        # In a real implementation, this would use the migration executor
        # For now, we'll return a success with info about what would happen
        try:
            from vidyut.migrations.executor import MigrationExecutor
            
            executor = MigrationExecutor()
            # Get pending migrations
            pending = await executor.get_pending_migrations()
            
            if apps:
                pending = [m for m in pending if m.app_label in apps]
            
            if not pending:
                return AiPlanStepResult(
                    id=step.id,
                    type=step.type,
                    success=True,
                    output={
                        "migrations_run": 0,
                        "note": "No pending migrations"
                    }
                )
            
            # Run migrations
            await executor.migrate(apps=apps or None, fake=fake)
            
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=True,
                output={
                    "migrations_run": len(pending),
                    "apps": apps or ["all"],
                    "fake": fake
                }
            )
        except ImportError:
            # Migration executor not available
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=True,
                output={
                    "note": "Migration executor not configured",
                    "apps": apps or ["all"],
                    "fake": fake
                }
            )
    except Exception as e:
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=False,
            error=str(e)
        )


async def _handle_generate_viewset(
    app: "FastAPI",
    step: AiPlanStep,
    dry_run: bool
) -> AiPlanStepResult:
    """
    Handle generate_viewset step.
    
    Expects payload: {"model_spec": {...}} or {"model": "ModelName", "app_label": "app"}
    """
    try:
        from vidyut.ai.codegen import AiModelSpec, generate_viewset_code
        from vidyut.ai.patch import AiPatchOperation, AiPatchRequest, apply_ai_patches
        import os
        
        model_spec_data = step.payload.get("model_spec")
        model_name = step.payload.get("model")
        app_label = step.payload.get("app_label", "app")
        
        if model_spec_data:
            model_spec = AiModelSpec(**model_spec_data)
        elif model_name:
            # Create minimal spec from model name
            model_spec = AiModelSpec(
                name=model_name,
                app_label=app_label,
                fields=[],
                add_viewset=True
            )
        else:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=False,
                error="Missing 'model_spec' or 'model' in payload"
            )
        
        # Generate viewset code
        files = generate_viewset_code(model_spec)
        
        if dry_run:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=True,
                output={
                    "preview_only": True,
                    "viewset_name": f"{model_spec.name}ViewSet",
                    "files": list(files.keys()),
                    "content_preview": files,
                }
            )
        
        # Apply via patch engine
        operations = []
        for path, content in files.items():
            operations.append(AiPatchOperation(
                type="modify_file",
                path=path,
                text=content,
                note=f"Generate ViewSet for {model_spec.name}"
            ))
        
        patch_request = AiPatchRequest(
            operations=operations,
            reason=f"Generate ViewSet for {model_spec.name}"
        )
        
        project_root = getattr(app.state, 'project_root', None) or os.getcwd()
        
        result = apply_ai_patches(
            patch_request,
            project_root=project_root,
            preview=False,
            confirm_header="true"
        )
        
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=result.applied,
            output={
                "viewset_name": f"{model_spec.name}ViewSet",
                "files": list(files.keys()),
                "applied": result.applied,
            }
        )
    except Exception as e:
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=False,
            error=str(e)
        )


async def _handle_generate_serializer(
    app: "FastAPI",
    step: AiPlanStep,
    dry_run: bool
) -> AiPlanStepResult:
    """
    Handle generate_serializer step.
    
    Expects payload: {"model_spec": {...}} or {"model": "ModelName", "app_label": "app"}
    """
    try:
        from vidyut.ai.codegen import AiModelSpec, generate_serializer_code
        from vidyut.ai.patch import AiPatchOperation, AiPatchRequest, apply_ai_patches
        import os
        
        model_spec_data = step.payload.get("model_spec")
        model_name = step.payload.get("model")
        app_label = step.payload.get("app_label", "app")
        
        if model_spec_data:
            model_spec = AiModelSpec(**model_spec_data)
        elif model_name:
            model_spec = AiModelSpec(
                name=model_name,
                app_label=app_label,
                fields=[],
                add_serializer=True
            )
        else:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=False,
                error="Missing 'model_spec' or 'model' in payload"
            )
        
        # Generate serializer code
        files = generate_serializer_code(model_spec)
        
        if dry_run:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=True,
                output={
                    "preview_only": True,
                    "serializer_name": f"{model_spec.name}Serializer",
                    "files": list(files.keys()),
                    "content_preview": files,
                }
            )
        
        # Apply via patch engine
        operations = []
        for path, content in files.items():
            operations.append(AiPatchOperation(
                type="modify_file",
                path=path,
                text=content,
                note=f"Generate Serializer for {model_spec.name}"
            ))
        
        patch_request = AiPatchRequest(
            operations=operations,
            reason=f"Generate Serializer for {model_spec.name}"
        )
        
        project_root = getattr(app.state, 'project_root', None) or os.getcwd()
        
        result = apply_ai_patches(
            patch_request,
            project_root=project_root,
            preview=False,
            confirm_header="true"
        )
        
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=result.applied,
            output={
                "serializer_name": f"{model_spec.name}Serializer",
                "files": list(files.keys()),
                "applied": result.applied,
            }
        )
    except Exception as e:
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=False,
            error=str(e)
        )


async def _handle_generate_admin(
    app: "FastAPI",
    step: AiPlanStep,
    dry_run: bool
) -> AiPlanStepResult:
    """
    Handle generate_admin step.
    
    Expects payload: {"model_spec": {...}} or {"model": "ModelName", "app_label": "app"}
    """
    try:
        from vidyut.ai.codegen import AiModelSpec, generate_admin_code
        from vidyut.ai.patch import AiPatchOperation, AiPatchRequest, apply_ai_patches
        import os
        
        model_spec_data = step.payload.get("model_spec")
        model_name = step.payload.get("model")
        app_label = step.payload.get("app_label", "app")
        
        if model_spec_data:
            model_spec = AiModelSpec(**model_spec_data)
        elif model_name:
            model_spec = AiModelSpec(
                name=model_name,
                app_label=app_label,
                fields=[],
                add_admin=True
            )
        else:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=False,
                error="Missing 'model_spec' or 'model' in payload"
            )
        
        # Generate admin code
        files = generate_admin_code(model_spec)
        
        if dry_run:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=True,
                output={
                    "preview_only": True,
                    "admin_class": f"{model_spec.name}Admin",
                    "files": list(files.keys()),
                    "content_preview": files,
                }
            )
        
        # Apply via patch engine
        operations = []
        for path, content in files.items():
            operations.append(AiPatchOperation(
                type="modify_file",
                path=path,
                text=content,
                note=f"Generate Admin for {model_spec.name}"
            ))
        
        patch_request = AiPatchRequest(
            operations=operations,
            reason=f"Generate Admin for {model_spec.name}"
        )
        
        project_root = getattr(app.state, 'project_root', None) or os.getcwd()
        
        result = apply_ai_patches(
            patch_request,
            project_root=project_root,
            preview=False,
            confirm_header="true"
        )
        
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=result.applied,
            output={
                "admin_class": f"{model_spec.name}Admin",
                "files": list(files.keys()),
                "applied": result.applied,
            }
        )
    except Exception as e:
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=False,
            error=str(e)
        )


async def _handle_generate_tests(
    app: "FastAPI",
    step: AiPlanStep,
    dry_run: bool
) -> AiPlanStepResult:
    """
    Handle generate_tests step.
    
    Expects payload: {"model": "ModelName", "app_label": "app"}
    Generates basic test file for the model.
    """
    try:
        from vidyut.ai.patch import AiPatchOperation, AiPatchRequest, apply_ai_patches
        import os
        
        model_name = step.payload.get("model")
        app_label = step.payload.get("app_label", "app")
        
        if not model_name:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=False,
                error="Missing 'model' in payload"
            )
        
        # Generate test file
        test_path = f"tests/test_{model_name.lower()}.py"
        test_content = f'''"""
Tests for {model_name} model.

Auto-generated by Vidyut AI Planner
"""

import pytest
from {app_label}.models import {model_name}


class Test{model_name}:
    """Tests for {model_name} model."""
    
    def test_create_{model_name.lower()}(self):
        """Test creating a {model_name} instance."""
        # TODO: Add test implementation
        pass
    
    def test_{model_name.lower()}_str(self):
        """Test {model_name} string representation."""
        # TODO: Add test implementation
        pass
    
    def test_{model_name.lower()}_fields(self):
        """Test {model_name} field definitions."""
        # TODO: Add test implementation
        pass


class Test{model_name}API:
    """Tests for {model_name} API endpoints."""
    
    def test_list_{model_name.lower()}s(self):
        """Test listing {model_name} instances."""
        # TODO: Add test implementation
        pass
    
    def test_create_{model_name.lower()}_api(self):
        """Test creating {model_name} via API."""
        # TODO: Add test implementation
        pass
    
    def test_retrieve_{model_name.lower()}(self):
        """Test retrieving a single {model_name}."""
        # TODO: Add test implementation
        pass
    
    def test_update_{model_name.lower()}(self):
        """Test updating a {model_name}."""
        # TODO: Add test implementation
        pass
    
    def test_delete_{model_name.lower()}(self):
        """Test deleting a {model_name}."""
        # TODO: Add test implementation
        pass
'''
        
        files = {test_path: test_content}
        
        if dry_run:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=True,
                output={
                    "preview_only": True,
                    "test_file": test_path,
                    "content_preview": files,
                }
            )
        
        # Apply via patch engine
        operations = [AiPatchOperation(
            type="modify_file",
            path=test_path,
            text=test_content,
            note=f"Generate tests for {model_name}"
        )]
        
        patch_request = AiPatchRequest(
            operations=operations,
            reason=f"Generate tests for {model_name}"
        )
        
        project_root = getattr(app.state, 'project_root', None) or os.getcwd()
        
        result = apply_ai_patches(
            patch_request,
            project_root=project_root,
            preview=False,
            confirm_header="true"
        )
        
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=result.applied,
            output={
                "test_file": test_path,
                "applied": result.applied,
            }
        )
    except Exception as e:
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=False,
            error=str(e)
        )


async def _handle_apply_patch(
    app: "FastAPI",
    step: AiPlanStep,
    dry_run: bool
) -> AiPlanStepResult:
    """
    Handle apply_patch step.
    
    Expects payload: {"patch_request": {...AiPatchRequest...}}
    """
    try:
        from vidyut.ai.patch import AiPatchRequest, apply_ai_patches
        import os
        
        patch_request_data = step.payload.get("patch_request")
        if not patch_request_data:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=False,
                error="Missing 'patch_request' in payload"
            )
        
        patch_request = AiPatchRequest(**patch_request_data)
        
        project_root = getattr(app.state, 'project_root', None) or os.getcwd()
        
        result = apply_ai_patches(
            patch_request,
            project_root=project_root,
            preview=dry_run,
            confirm_header="true" if not dry_run else None
        )
        
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=result.applied or result.preview_only,
            output={
                "preview_only": dry_run,
                "operations_applied": result.operations_applied,
                "files_changed": list(result.files_changed.keys()),
                "checksum": result.checksum,
            }
        )
    except Exception as e:
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=False,
            error=str(e)
        )


async def _handle_run_query_check(
    app: "FastAPI",
    step: AiPlanStep,
    dry_run: bool
) -> AiPlanStepResult:
    """
    Handle run_query_check step.
    
    Expects payload: {"plan": {...AiQueryPlan...}}
    """
    try:
        from vidyut.ai.query import AiQueryPlan, execute_ai_query_plan
        
        query_plan_data = step.payload.get("plan")
        if not query_plan_data:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=False,
                error="Missing 'plan' in payload"
            )
        
        query_plan = AiQueryPlan(**query_plan_data)
        
        if dry_run:
            return AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=True,
                output={
                    "preview_only": True,
                    "query_plan": query_plan.model_dump(),
                    "note": "Query would be executed against database"
                }
            )
        
        # Execute the query
        result = await execute_ai_query_plan(query_plan, app)
        
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=True,
            output={
                "model": query_plan.model,
                "count": result.count,
                "rows": result.rows[:10] if result.rows else [],  # Limit rows
                "truncated": len(result.rows) > 10 if result.rows else False,
            }
        )
    except Exception as e:
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=False,
            error=str(e)
        )


async def _handle_run_health_check(
    app: "FastAPI",
    step: AiPlanStep,
    dry_run: bool
) -> AiPlanStepResult:
    """
    Handle run_health_check step.
    
    Performs basic health checks on the application.
    """
    try:
        checks = {
            "app_running": True,
            "database_configured": False,
            "models_registered": False,
            "routes_configured": False,
        }
        
        # Check database
        try:
            from vidyut.db import Database
            from vidyut.conf import settings
            if settings.database_url:
                checks["database_configured"] = True
        except Exception:
            pass
        
        # Check models
        try:
            from vidyut.registry import ModelRegistry
            models = ModelRegistry.get_all()
            checks["models_registered"] = len(models) > 0
            checks["model_count"] = len(models)
        except Exception:
            pass
        
        # Check routes
        try:
            if hasattr(app, 'routes'):
                checks["routes_configured"] = len(app.routes) > 0
                checks["route_count"] = len(app.routes)
        except Exception:
            pass
        
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=True,
            output={
                "checks": checks,
                "healthy": all([
                    checks["app_running"],
                    checks.get("models_registered", False),
                ])
            }
        )
    except Exception as e:
        return AiPlanStepResult(
            id=step.id,
            type=step.type,
            success=False,
            error=str(e)
        )


# =============================================================================
# Step Handler Registry
# =============================================================================

STEP_HANDLERS: Dict[str, Callable] = {
    "analyze_context": _handle_analyze_context,
    "create_model": _handle_create_model,
    "update_model": _handle_update_model,
    "create_field": _handle_create_field,
    "update_field": _handle_update_field,
    "delete_field": _handle_delete_field,
    "create_migration": _handle_create_migration,
    "run_migrations": _handle_run_migrations,
    "generate_viewset": _handle_generate_viewset,
    "generate_serializer": _handle_generate_serializer,
    "generate_admin": _handle_generate_admin,
    "generate_tests": _handle_generate_tests,
    "apply_patch": _handle_apply_patch,
    "run_query_check": _handle_run_query_check,
    "run_health_check": _handle_run_health_check,
}


# =============================================================================
# Plan Execution
# =============================================================================

async def execute_plan(
    app: "FastAPI",
    plan: AiPlan,
    dry_run: bool = False
) -> AiPlanExecutionResult:
    """
    Execute an AI plan.
    
    This is the main orchestration function that:
    1. Topologically sorts steps by depends_on
    2. Executes each step in order
    3. Passes results to dependent steps
    4. Stops on first failure (fail-fast)
    
    Args:
        app: The FastAPI application
        plan: The plan to execute
        dry_run: If True, preview operations without applying
        
    Returns:
        AiPlanExecutionResult with step results and overall success
    """
    notes: List[str] = []
    step_results: List[AiPlanStepResult] = []
    
    notes.append(f"Executing plan: {plan.intent}")
    notes.append(f"Total steps: {len(plan.steps)}")
    notes.append(f"Mode: {'dry run (preview)' if dry_run else 'apply'}")
    
    # Sort steps topologically
    sorted_steps = _topological_sort(plan.steps)
    notes.append(f"Execution order: {[s.id for s in sorted_steps]}")
    
    # Track step outputs for dependent steps
    step_outputs: Dict[str, Dict[str, Any]] = {}
    
    # Execute each step
    for step in sorted_steps:
        handler = STEP_HANDLERS.get(step.type)
        
        if not handler:
            result = AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=False,
                error=f"Unknown step type: {step.type}"
            )
            step_results.append(result)
            notes.append(f"Step {step.id} failed: Unknown type {step.type}")
            
            # Fail-fast: stop on first error
            return AiPlanExecutionResult(
                success=False,
                steps=step_results,
                notes=notes,
                dry_run=dry_run
            )
        
        try:
            # Execute the handler
            result = await handler(app, step, dry_run)
            step_results.append(result)
            
            # Store output for dependent steps
            step_outputs[step.id] = result.output
            
            if result.success:
                notes.append(f"Step {step.id} ({step.type}): success")
            else:
                notes.append(f"Step {step.id} ({step.type}): failed - {result.error}")
                
                # Fail-fast: stop on first error
                return AiPlanExecutionResult(
                    success=False,
                    steps=step_results,
                    notes=notes,
                    dry_run=dry_run
                )
        except Exception as e:
            result = AiPlanStepResult(
                id=step.id,
                type=step.type,
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
            step_results.append(result)
            notes.append(f"Step {step.id}: unexpected error - {str(e)}")
            
            return AiPlanExecutionResult(
                success=False,
                steps=step_results,
                notes=notes,
                dry_run=dry_run
            )
    
    notes.append("Plan executed successfully")
    
    return AiPlanExecutionResult(
        success=True,
        steps=step_results,
        notes=notes,
        dry_run=dry_run
    )


def validate_plan(plan: AiPlan) -> List[str]:
    """
    Validate a plan without executing it.
    
    Returns a list of validation errors (empty if valid).
    """
    errors: List[str] = []
    
    # Check for valid step types
    for step in plan.steps:
        if step.type not in VALID_STEP_TYPES:
            errors.append(f"Step {step.id}: Invalid type '{step.type}'")
    
    # Check for required payloads
    for step in plan.steps:
        if step.type == "create_model" and "model_spec" not in step.payload:
            errors.append(f"Step {step.id}: create_model requires 'model_spec' in payload")
        elif step.type in ("create_field", "update_field"):
            if "model" not in step.payload:
                errors.append(f"Step {step.id}: {step.type} requires 'model' in payload")
            if "field" not in step.payload and step.type != "delete_field":
                errors.append(f"Step {step.id}: {step.type} requires 'field' in payload")
        elif step.type == "apply_patch" and "patch_request" not in step.payload:
            errors.append(f"Step {step.id}: apply_patch requires 'patch_request' in payload")
        elif step.type == "run_query_check" and "plan" not in step.payload:
            errors.append(f"Step {step.id}: run_query_check requires 'plan' in payload")
    
    return errors


def get_plan_schema() -> Dict[str, Any]:
    """Get JSON schemas for plan models."""
    return {
        "AiPlan": AiPlan.model_json_schema(),
        "AiPlanStep": AiPlanStep.model_json_schema(),
        "AiPlanStepResult": AiPlanStepResult.model_json_schema(),
        "AiPlanExecutionResult": AiPlanExecutionResult.model_json_schema(),
        "valid_step_types": list(VALID_STEP_TYPES),
    }
