"""
Vidyut AI Runtime (Mini Agent Loop) - v0.4.6

A minimal "agent runtime" inside Vidyut that coordinates:
    intent → context → plan → preview → apply

This module does NOT call any LLM itself. Instead, it provides structured
endpoints that an external agent (VS Code extension, CLI, or remote AI)
can use to drive Vidyut.

The flow:
1. External AI sends an AgentIntent
2. Vidyut returns an AgentContextBundle (full context + schemas)
3. External AI constructs an AiPlan
4. External AI calls preview endpoint (dry run)
5. On user confirmation, calls apply endpoint

Key Models:
- AgentIntent: User's natural language request with mode & scope
- AgentContextBundle: Everything an AI needs to understand the app
- AgentPlanExecutionRequest: Request to preview/execute a plan
- AgentPlanPreviewResponse: Result of plan preview
- AgentPlanApplyRequest: Request to apply a plan (requires confirmation)
- AgentPlanApplyResponse: Result of plan application

Usage:
    from vidyut.ai.agent import (
        AgentIntent,
        AgentContextBundle,
        build_agent_context_bundle,
    )
    
    intent = AgentIntent(
        user_message="Add a slug field to Article model",
        mode="modify"
    )
    bundle = await build_agent_context_bundle(app, intent)
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from fastapi import FastAPI

import vidyut


# =============================================================================
# Agent Intent - What the user/external AI wants
# =============================================================================

class AgentIntent(BaseModel):
    """
    Represents a user's intent sent by an external AI or UI.
    
    This is the starting point of the agent loop. The external AI
    sends this to Vidyut to get context and schemas for planning.
    
    Attributes:
        id: Optional client-generated ID for tracking
        user_message: Natural language request from the user
        mode: Operation mode - read, design, or modify
        scope: Optional list of areas to focus on
        hints: Arbitrary hints (e.g., preferred app, model name)
        metadata: Extra info (e.g., editor filename, cursor position)
    
    Modes:
        - "read": No structural changes (queries, analysis only)
        - "design": Planning only, no patch/apply yet
        - "modify": Can propose and apply changes
    
    Example:
        AgentIntent(
            user_message="Add a slug field to Article model",
            mode="modify",
            scope=["models", "migrations"],
            hints={"model": "Article", "app": "blog"}
        )
    """
    
    id: Optional[str] = Field(default=None, description="Client-generated ID for tracking")
    user_message: str = Field(..., description="Natural language request from user")
    mode: Literal["read", "design", "modify"] = Field(
        default="modify",
        description="Operation mode: read (queries only), design (planning), modify (can apply changes)"
    )
    scope: Optional[List[str]] = Field(
        default=None,
        description="Optional scope: ['models', 'views', 'migrations', 'tests', 'admin', ...]"
    )
    hints: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary hints for the AI (e.g., preferred app, model name)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extra metadata (e.g., editor filename, cursor position)"
    )
    
    model_config = {"extra": "forbid"}


# =============================================================================
# Agent Context Bundle - Everything AI needs to reason about the app
# =============================================================================

class AgentContextBundle(BaseModel):
    """
    Complete bundle of context and schemas for an external AI.
    
    This gives the AI everything it needs to:
    - Understand the Vidyut application structure
    - Understand valid plan structure (AiPlan schema)
    - Understand valid patch structure (AiPatchRequest schema)
    - Understand query/codegen schemas
    - Use available tools if needed
    
    The bundle is deterministic and provider-agnostic.
    
    Example response structure:
        {
            "intent": {...},
            "full_context": {...models, routes, migrations...},
            "tools": [...],
            "plan_schema": {...},
            "patch_schema": {...},
            "query_plan_schema": {...},
            "codegen_schema": {...},
            "version": "0.4.6"
        }
    """
    
    intent: AgentIntent = Field(..., description="The original intent that was sent")
    full_context: Dict[str, Any] = Field(
        ..., 
        description="Full application context (models, routes, migrations, admin, settings)"
    )
    tools: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Available AI tools from AiToolRegistry"
    )
    plan_schema: Dict[str, Any] = Field(
        ...,
        description="JSON schema for AiPlan (v0.4.5 Planner)"
    )
    patch_schema: Dict[str, Any] = Field(
        ...,
        description="JSON schema for AiPatchRequest (v0.4.4 Patch Engine)"
    )
    query_plan_schema: Dict[str, Any] = Field(
        ...,
        description="JSON schema for AiQueryPlan (v0.4.2 Query Assistant)"
    )
    codegen_schema: Dict[str, Any] = Field(
        ...,
        description="JSON schemas for codegen models (v0.4.2 CodeGen)"
    )
    version: str = Field(..., description="Vidyut framework version")
    
    model_config = {"extra": "forbid"}


# =============================================================================
# Plan Execution Request/Response Models
# =============================================================================

class AgentPlanExecutionRequest(BaseModel):
    """
    Request to execute (preview or apply) an AI plan.
    
    The external AI constructs an AiPlan based on the context bundle,
    then sends this request to preview or apply the plan.
    
    Attributes:
        intent: The original intent for tracking
        plan: The constructed AiPlan to execute
        dry_run: Whether to preview (True) or apply (False)
    """
    
    intent: AgentIntent = Field(..., description="Original intent for tracking")
    plan: Dict[str, Any] = Field(..., description="The AiPlan to execute")
    dry_run: bool = Field(default=True, description="If True, preview only; if False, apply changes")
    
    model_config = {"extra": "forbid"}


class AgentPlanPreviewResponse(BaseModel):
    """
    Response from previewing a plan (dry run).
    
    Contains the execution result and a summary for UI display.
    No files are modified on disk during preview.
    
    Attributes:
        intent: The original intent
        plan: The plan that was previewed
        execution: Detailed execution result from the planner
        summary: Simplified summary for UI display
    """
    
    intent: AgentIntent = Field(..., description="Original intent")
    plan: Dict[str, Any] = Field(..., description="The plan that was previewed")
    execution: Dict[str, Any] = Field(..., description="Execution result from planner")
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Simplified summary for UI (success, step_count, failed_steps)"
    )
    
    model_config = {"extra": "forbid"}


class AgentPlanApplyRequest(BaseModel):
    """
    Request to apply an AI plan (make actual changes).
    
    ⚠️ This can modify files on disk.
    
    Requires:
        - confirm=True in the payload
        - X-AI-Apply: true header
    
    Both safeguards must be present to apply changes.
    
    Attributes:
        intent: The original intent for tracking
        plan: The AiPlan to apply
        confirm: Must be True to proceed with application
    """
    
    intent: AgentIntent = Field(..., description="Original intent for tracking")
    plan: Dict[str, Any] = Field(..., description="The AiPlan to apply")
    confirm: bool = Field(default=False, description="Must be True to apply changes")
    
    model_config = {"extra": "forbid"}


class AgentPlanApplyResponse(BaseModel):
    """
    Response from applying a plan.
    
    Contains the execution result after changes were made.
    
    Attributes:
        intent: The original intent
        plan: The plan that was applied
        execution: Detailed execution result
    """
    
    intent: AgentIntent = Field(..., description="Original intent")
    plan: Dict[str, Any] = Field(..., description="The plan that was applied")
    execution: Dict[str, Any] = Field(..., description="Execution result")
    
    model_config = {"extra": "forbid"}


# =============================================================================
# Build Agent Context Bundle
# =============================================================================

async def build_agent_context_bundle(
    app: "FastAPI",
    intent: AgentIntent
) -> AgentContextBundle:
    """
    Build everything an external AI needs to reason about the app.
    
    This function aggregates:
    - Full context (models, routes, migrations, admin, settings) from v0.4.3
    - Tool definitions from v0.4.0
    - Plan schema from v0.4.5
    - Patch schema from v0.4.4
    - Query plan schema from v0.4.2
    - Codegen schema from v0.4.2
    
    The result is pure & deterministic (same app state = same output).
    
    Args:
        app: The FastAPI application instance
        intent: The user's intent
        
    Returns:
        AgentContextBundle with all context and schemas
    
    Example:
        bundle = await build_agent_context_bundle(app, intent)
        # External AI uses bundle to construct an AiPlan
    """
    from vidyut.ai.context import build_full_ai_context
    from vidyut.ai.planner import AiPlan, AiPlanStep, get_plan_schema
    from vidyut.ai.patch import AiPatchRequest, AiPatchOperation
    from vidyut.ai.query import get_query_plan_schema
    from vidyut.ai.codegen import get_codegen_schemas
    from vidyut.ai.registry import AiToolRegistry
    
    # Build full context from v0.4.3 Context Engine
    full_context = await build_full_ai_context(app)
    
    # Get tools from registry
    tools = []
    try:
        all_tools = AiToolRegistry.get_all()
        tools = [t.model_dump() for t in all_tools]
    except Exception:
        # Registry might be empty or not initialized
        pass
    
    # Get plan schema from v0.4.5 Planner
    plan_schema = get_plan_schema()
    
    # Get patch schema from v0.4.4 Patch Engine
    patch_schema = {
        "AiPatchOperation": AiPatchOperation.model_json_schema(),
        "AiPatchRequest": AiPatchRequest.model_json_schema(),
    }
    
    # Get query plan schema from v0.4.2 Query Assistant
    query_plan_schema = get_query_plan_schema()
    
    # Get codegen schema from v0.4.2 CodeGen
    codegen_schema = get_codegen_schemas()
    
    return AgentContextBundle(
        intent=intent,
        full_context=full_context.model_dump(),
        tools=tools,
        plan_schema=plan_schema,
        patch_schema=patch_schema,
        query_plan_schema=query_plan_schema,
        codegen_schema=codegen_schema,
        version=vidyut.__version__,
    )


def build_agent_context_bundle_sync(
    app: "FastAPI",
    intent: AgentIntent
) -> AgentContextBundle:
    """
    Synchronous version of build_agent_context_bundle.
    
    Useful for testing and non-async contexts.
    """
    import asyncio
    
    try:
        loop = asyncio.get_running_loop()
        # We're in an async context, create a new task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(
                asyncio.run,
                build_agent_context_bundle(app, intent)
            )
            return future.result()
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        return asyncio.run(build_agent_context_bundle(app, intent))
