"""
Aksara AI Module

AI-native abstractions for exposing models, ViewSets, and actions as structured AI tools.

This module provides:
- AiTool: Canonical AI tool descriptors
- AiToolRegistry: Central registry for AI tools
- Permission-aware tool filtering
- Export functions for MCP, OpenAI, LangChain integrations
- AI Debug Assistant for error analysis (v0.4.1)
- AI Query Assistant for structured querying (v0.4.2)
- AI CodeGen for code generation (v0.4.2)
- AI Context Engine for full app state export (v0.4.3)
- AI Patch Engine for safe code modifications (v0.4.4)
- AI Planner for multi-step execution plans (v0.4.5)
- AI Runtime (Mini Agent Loop) for external AI coordination (v0.4.6)
- AI Schema Doctor for schema health & drift detection (v0.4.7)
- AI Profiles & Provider Contracts (v0.5.11)
- AI Profiles Validation & Linting (v0.5.12)
- Per-View AI Hints (v0.5.13)

Usage:
    from aksara.ai import AiTool, AiToolRegistry, get_ai_tools_for_request
    from aksara.ai.exporters import export_tools_as_mcp, export_tools_as_generic

    # Get tools for the current request (permission-filtered)
    tools = await get_ai_tools_for_request(request, app)

    # Export as MCP format
    mcp_tools = export_tools_as_mcp(tools)

    # AI Debug (v0.4.1)
    from aksara.ai.debug import build_ai_debug_context, AiDebugContext

    # AI Query Assistant (v0.4.2)
    from aksara.ai.query import AiQueryPlan, execute_ai_query_plan

    # AI CodeGen (v0.4.2)
    from aksara.ai.codegen import AiModelSpec, generate_code

    # AI Context Engine (v0.4.3)
    from aksara.ai.context import build_full_ai_context, AiFullContext

    # AI Patch Engine (v0.4.4)
    from aksara.ai.patch import apply_ai_patches, AiPatchRequest

    # AI Planner (v0.4.5)
    from aksara.ai.planner import AiPlan, AiPlanStep, execute_plan

    # AI Runtime (v0.4.6)
    from aksara.ai.agent import AgentIntent, AgentContextBundle, build_agent_context_bundle

    # AI Schema Doctor (v0.4.7)
    from aksara.ai.schema_doctor import analyze_schema_health, AiSchemaHealth

    # AI Profiles & Provider Contracts (v0.5.11)
    from aksara.ai.providers import (
        AiProviderProfile, AiModelProfile, AiProfileSet,
        AiProviderRegistry, get_ai_provider_registry,
    )

    # Per-View AI Hints (v0.5.13)
    from aksara.ai import ai_route_hint, AiRouteHint, AiHintSet

    @ai_route_hint(
        title="Publish blog post",
        description="Marks a post as published.",
        usage_kind="write",
        risk_level="medium",
    )
    async def publish(request, id: int): ...

v0.4.0: Initial AI Mode release
v0.4.1: AI Debug Assistant
v0.4.2: AI Query Assistant & CodeGen (Provider-Agnostic)
v0.4.3: AI Context Engine (THE BRAIN DATA)
v0.4.4: AI Patch Engine (THE SURGEON)
v0.4.5: AI Planner (THE ARCHITECT)
v0.4.6: AI Runtime (Mini Agent Loop)
v0.4.7: AI Schema Doctor & Migration Guardrails
v0.5.11: AI Profiles & Provider Contracts
v0.5.12: AI Profiles Validation & Linting
v0.5.13: Per-View AI Hints (Route-Level AI Metadata)
v0.5.25: Unified AI Provider System & LLM Client Adapters

    # Unified AI Provider (v0.5.25)
    from aksara.ai.providers_unified import (
        UnifiedAiProvider, detect_all_providers, get_active_provider,
    )
    from aksara.ai.llm_clients import BaseLlmClient, get_client_for_provider
"""

# ---------------------------------------------------------------------------
# PEP 562 lazy-import map
#
# All submodule imports are deferred until the attribute is first accessed.
# This avoids importing 20+ heavy submodules on every `import aksara`.
# The first access caches the resolved value in module globals so subsequent
# accesses are plain dict lookups.
# ---------------------------------------------------------------------------

import importlib
from typing import Any

_LAZY_AI_ATTRS = {
    # aksara.ai.models
    "AiTool": ("aksara.ai.models", "AiTool"),
    "AiToolParam": ("aksara.ai.models", "AiToolParam"),
    "ToolKind": ("aksara.ai.models", "ToolKind"),
    "AiRiskLevel": ("aksara.ai.models", "AiRiskLevel"),
    "AiUsageKind": ("aksara.ai.models", "AiUsageKind"),
    "AiRouteHint": ("aksara.ai.models", "AiRouteHint"),
    "AiHintSet": ("aksara.ai.models", "AiHintSet"),
    # aksara.ai.registry
    "AiToolRegistry": ("aksara.ai.registry", "AiToolRegistry"),
    "discover_tools_from_viewset": ("aksara.ai.registry", "discover_tools_from_viewset"),
    "get_ai_tools_for_request": ("aksara.ai.registry", "get_ai_tools_for_request"),
    # aksara.ai.exporters
    "export_tools_as_generic": ("aksara.ai.exporters", "export_tools_as_generic"),
    "export_tools_as_mcp": ("aksara.ai.exporters", "export_tools_as_mcp"),
    # aksara.ai.fastapi (imported as 'router' → exposed as 'ai_router')
    "ai_router": ("aksara.ai.fastapi", "router"),
    # aksara.ai.debug
    "AiDebugContext": ("aksara.ai.debug", "AiDebugContext"),
    "AiDebugSuggestion": ("aksara.ai.debug", "AiDebugSuggestion"),
    "AiExceptionInfo": ("aksara.ai.debug", "AiExceptionInfo"),
    "AiRequestInfo": ("aksara.ai.debug", "AiRequestInfo"),
    "AiStackFrame": ("aksara.ai.debug", "AiStackFrame"),
    "BaseAiDebugAdvisor": ("aksara.ai.debug", "BaseAiDebugAdvisor"),
    "RuleBasedAiDebugAdvisor": ("aksara.ai.debug", "RuleBasedAiDebugAdvisor"),
    "build_ai_debug_context": ("aksara.ai.debug", "build_ai_debug_context"),
    "classify_exception": ("aksara.ai.debug", "classify_exception"),
    "default_advisor": ("aksara.ai.debug", "default_advisor"),
    # aksara.ai.query
    "AiFilterCondition": ("aksara.ai.query", "AiFilterCondition"),
    "AiQueryPagination": ("aksara.ai.query", "AiQueryPagination"),
    "AiQueryPlan": ("aksara.ai.query", "AiQueryPlan"),
    "AiQueryRequest": ("aksara.ai.query", "AiQueryRequest"),
    "AiQueryResult": ("aksara.ai.query", "AiQueryResult"),
    "AiSortField": ("aksara.ai.query", "AiSortField"),
    "execute_ai_query_plan": ("aksara.ai.query", "execute_ai_query_plan"),
    "get_available_models_for_query": ("aksara.ai.query", "get_available_models_for_query"),
    "get_query_plan_schema": ("aksara.ai.query", "get_query_plan_schema"),
    "SUPPORTED_LOOKUPS": ("aksara.ai.query", "SUPPORTED_LOOKUPS"),
    # aksara.ai.codegen
    "AiCodegenRequest": ("aksara.ai.codegen", "AiCodegenRequest"),
    "AiCodegenResult": ("aksara.ai.codegen", "AiCodegenResult"),
    "AiCodegenTarget": ("aksara.ai.codegen", "AiCodegenTarget"),
    "AiFieldSpec": ("aksara.ai.codegen", "AiFieldSpec"),
    "AiModelSpec": ("aksara.ai.codegen", "AiModelSpec"),
    "FIELD_TYPE_MAPPING": ("aksara.ai.codegen", "FIELD_TYPE_MAPPING"),
    "generate_admin_code": ("aksara.ai.codegen", "generate_admin_code"),
    "generate_app_skeleton": ("aksara.ai.codegen", "generate_app_skeleton"),
    "generate_code": ("aksara.ai.codegen", "generate_code"),
    "generate_migration_stub": ("aksara.ai.codegen", "generate_migration_stub"),
    "generate_model_code": ("aksara.ai.codegen", "generate_model_code"),
    "generate_serializer_code": ("aksara.ai.codegen", "generate_serializer_code"),
    "generate_viewset_code": ("aksara.ai.codegen", "generate_viewset_code"),
    "get_codegen_schemas": ("aksara.ai.codegen", "get_codegen_schemas"),
    # aksara.ai.client
    "BaseAiClient": ("aksara.ai.client", "BaseAiClient"),
    "AiClientConfig": ("aksara.ai.client", "AiClientConfig"),
    "ChatMessage": ("aksara.ai.client", "ChatMessage"),
    "ToolCall": ("aksara.ai.client", "ToolCall"),
    "ChatResponse": ("aksara.ai.client", "ChatResponse"),
    # aksara.ai.context
    "AiFieldType": ("aksara.ai.context", "AiFieldType"),
    "AiModelFieldInfo": ("aksara.ai.context", "AiModelFieldInfo"),
    "AiRelationInfo": ("aksara.ai.context", "AiRelationInfo"),
    "AiModelInfo": ("aksara.ai.context", "AiModelInfo"),
    "AiActionInfo": ("aksara.ai.context", "AiActionInfo"),
    "AiViewSetInfo": ("aksara.ai.context", "AiViewSetInfo"),
    "AiRouteInfo": ("aksara.ai.context", "AiRouteInfo"),
    "AiMigrationOperationInfo": ("aksara.ai.context", "AiMigrationOperationInfo"),
    "AiMigrationInfo": ("aksara.ai.context", "AiMigrationInfo"),
    "AiAdminModelInfo": ("aksara.ai.context", "AiAdminModelInfo"),
    "AiAdminInfo": ("aksara.ai.context", "AiAdminInfo"),
    "AiSettingsInfo": ("aksara.ai.context", "AiSettingsInfo"),
    "AiMiddlewareInfo": ("aksara.ai.context", "AiMiddlewareInfo"),
    "AiToolSummary": ("aksara.ai.context", "AiToolSummary"),
    "AiSchemaInfo": ("aksara.ai.context", "AiSchemaInfo"),
    "AiRouteHintInfo": ("aksara.ai.context", "AiRouteHintInfo"),
    "AiFullContext": ("aksara.ai.context", "AiFullContext"),
    "build_full_ai_context": ("aksara.ai.context", "build_full_ai_context"),
    "build_full_ai_context_sync": ("aksara.ai.context", "build_full_ai_context_sync"),
    # aksara.ai.patch
    "PatchOperationType": ("aksara.ai.patch", "PatchOperationType"),
    "PatchValidationError": ("aksara.ai.patch", "PatchValidationError"),
    "AiPatchOperation": ("aksara.ai.patch", "AiPatchOperation"),
    "AiPatchRequest": ("aksara.ai.patch", "AiPatchRequest"),
    "AiPatchValidationResult": ("aksara.ai.patch", "AiPatchValidationResult"),
    "AiPatchFileChange": ("aksara.ai.patch", "AiPatchFileChange"),
    "AiPatchResult": ("aksara.ai.patch", "AiPatchResult"),
    "validate_operation": ("aksara.ai.patch", "validate_operation"),
    "validate_patch_request": ("aksara.ai.patch", "validate_patch_request"),
    "apply_ai_patches": ("aksara.ai.patch", "apply_ai_patches"),
    "apply_ai_patches_async": ("aksara.ai.patch", "apply_ai_patches_async"),
    "rollback_patches": ("aksara.ai.patch", "rollback_patches"),
    "preview_patch_diff": ("aksara.ai.patch", "preview_patch_diff"),
    "ALLOWED_OPERATIONS": ("aksara.ai.patch", "ALLOWED_OPERATIONS"),
    "PROTECTED_PATTERNS": ("aksara.ai.patch", "PROTECTED_PATTERNS"),
    # aksara.ai.planner
    "PlanStepType": ("aksara.ai.planner", "PlanStepType"),
    "VALID_STEP_TYPES": ("aksara.ai.planner", "VALID_STEP_TYPES"),
    "AiPlanStep": ("aksara.ai.planner", "AiPlanStep"),
    "AiPlan": ("aksara.ai.planner", "AiPlan"),
    "AiPlanStepResult": ("aksara.ai.planner", "AiPlanStepResult"),
    "AiPlanExecutionResult": ("aksara.ai.planner", "AiPlanExecutionResult"),
    "validate_plan": ("aksara.ai.planner", "validate_plan"),
    "get_plan_schema": ("aksara.ai.planner", "get_plan_schema"),
    # aksara.ai.agent
    "AgentIntent": ("aksara.ai.agent", "AgentIntent"),
    "AgentContextBundle": ("aksara.ai.agent", "AgentContextBundle"),
    "AgentPlanExecutionRequest": ("aksara.ai.agent", "AgentPlanExecutionRequest"),
    "AgentPlanPreviewResponse": ("aksara.ai.agent", "AgentPlanPreviewResponse"),
    "AgentPlanApplyRequest": ("aksara.ai.agent", "AgentPlanApplyRequest"),
    "AgentPlanApplyResponse": ("aksara.ai.agent", "AgentPlanApplyResponse"),
    "build_agent_context_bundle": ("aksara.ai.agent", "build_agent_context_bundle"),
    "build_agent_context_bundle_sync": ("aksara.ai.agent", "build_agent_context_bundle_sync"),
    # aksara.ai.schema_doctor
    "DriftKind": ("aksara.ai.schema_doctor", "DriftKind"),
    "IssueSeverity": ("aksara.ai.schema_doctor", "IssueSeverity"),
    "AiSchemaIssue": ("aksara.ai.schema_doctor", "AiSchemaIssue"),
    "AiSchemaHealth": ("aksara.ai.schema_doctor", "AiSchemaHealth"),
    "AiSchemaIssuesResponse": ("aksara.ai.schema_doctor", "AiSchemaIssuesResponse"),
    "DbColumnInfo": ("aksara.ai.schema_doctor", "DbColumnInfo"),
    "DbTableInfo": ("aksara.ai.schema_doctor", "DbTableInfo"),
    "introspect_db_schema": ("aksara.ai.schema_doctor", "introspect_db_schema"),
    "build_model_schema_map": ("aksara.ai.schema_doctor", "build_model_schema_map"),
    "detect_schema_drift": ("aksara.ai.schema_doctor", "detect_schema_drift"),
    "classify_severity": ("aksara.ai.schema_doctor", "classify_severity"),
    "analyze_schema_health": ("aksara.ai.schema_doctor", "analyze_schema_health"),
    # aksara.ai.providers
    "AiModelKind": ("aksara.ai.providers", "AiModelKind"),
    "AiProviderKind": ("aksara.ai.providers", "AiProviderKind"),
    "AiModelProfile": ("aksara.ai.providers", "AiModelProfile"),
    "AiProviderProfile": ("aksara.ai.providers", "AiProviderProfile"),
    "AiProfileSet": ("aksara.ai.providers", "AiProfileSet"),
    "AiProviderSecretHint": ("aksara.ai.providers", "AiProviderSecretHint"),
    "AiProviderConfigInfo": ("aksara.ai.providers", "AiProviderConfigInfo"),
    "AiProfileIssueSeverity": ("aksara.ai.providers", "AiProfileIssueSeverity"),
    "AiProfileIssueKind": ("aksara.ai.providers", "AiProfileIssueKind"),
    "AiProfileIssue": ("aksara.ai.providers", "AiProfileIssue"),
    "AiProfileHealth": ("aksara.ai.providers", "AiProfileHealth"),
    "AiProviderRegistry": ("aksara.ai.providers", "AiProviderRegistry"),
    "get_ai_provider_registry": ("aksara.ai.providers", "get_ai_provider_registry"),
    "build_default_ai_profile_set": ("aksara.ai.providers", "build_default_ai_profile_set"),
    "build_secret_hints_from_settings": ("aksara.ai.providers", "build_secret_hints_from_settings"),
    "build_example_profile_set": ("aksara.ai.providers", "build_example_profile_set"),
    "classify_issue_severity": ("aksara.ai.providers", "classify_issue_severity"),
    "validate_profile_set": ("aksara.ai.providers", "validate_profile_set"),
    "validate_default_profile_set": ("aksara.ai.providers", "validate_default_profile_set"),
    # aksara.ai.hints
    "ai_route_hint": ("aksara.ai.hints", "ai_route_hint"),
    "set_view_default_hint": ("aksara.ai.hints", "set_view_default_hint"),
    "get_hint_from_callable": ("aksara.ai.hints", "get_hint_from_callable"),
    "get_default_hint_from_class": ("aksara.ai.hints", "get_default_hint_from_class"),
    "extract_hints_from_app": ("aksara.ai.hints", "extract_hints_from_app"),
    "build_ai_hint_set": ("aksara.ai.hints", "build_ai_hint_set"),
    "build_ai_hint_set_sync": ("aksara.ai.hints", "build_ai_hint_set_sync"),
    "HINT_ATTR": ("aksara.ai.hints", "HINT_ATTR"),
    "DEFAULT_HINT_ATTR": ("aksara.ai.hints", "DEFAULT_HINT_ATTR"),
    # aksara.ai.intent_classifier
    "OrchestratedIntentMatch": ("aksara.ai.intent_classifier", "IntentMatch"),
    "classify_intent": ("aksara.ai.intent_classifier", "classify_intent"),
    "SUPPORTED_INTENTS": ("aksara.ai.intent_classifier", "SUPPORTED_INTENTS"),
    "ARCHITECTURE_REVIEW": ("aksara.ai.intent_classifier", "ARCHITECTURE_REVIEW"),
    "PERFORMANCE_INVESTIGATION": ("aksara.ai.intent_classifier", "PERFORMANCE_INVESTIGATION"),
    "DEBUG_ANALYSIS": ("aksara.ai.intent_classifier", "DEBUG_ANALYSIS"),
    "PROJECT_ANALYSIS": ("aksara.ai.intent_classifier", "PROJECT_ANALYSIS"),
    "SCHEMA_EXPLANATION": ("aksara.ai.intent_classifier", "SCHEMA_EXPLANATION"),
    "ROUTE_ANALYSIS": ("aksara.ai.intent_classifier", "ROUTE_ANALYSIS"),
    # aksara.ai.execution_planner
    "ExecutionPlan": ("aksara.ai.execution_planner", "ExecutionPlan"),
    "build_execution_plan": ("aksara.ai.execution_planner", "build_execution_plan"),
    "build_investigation_plan": ("aksara.ai.execution_planner", "build_investigation_plan"),
    "INVESTIGATION_PIPELINE": ("aksara.ai.execution_planner", "INVESTIGATION_PIPELINE"),
    # aksara.ai.orchestrator (execute_plan here shadows aksara.ai.planner.execute_plan)
    "execute_plan": ("aksara.ai.orchestrator", "execute_plan"),
    "OrchestrationResult": ("aksara.ai.orchestrator", "OrchestrationResult"),
    "StepResult": ("aksara.ai.orchestrator", "StepResult"),
    # aksara.ai.intent_engine
    "handle_prompt": ("aksara.ai.intent_engine", "handle_prompt"),
    "run_investigation": ("aksara.ai.intent_engine", "run_investigation"),
    "classify_and_plan": ("aksara.ai.intent_engine", "classify_and_plan"),
    "classify_intent_v2": ("aksara.ai.intent_engine", "classify_intent_v2"),
    "IntentResult": ("aksara.ai.intent_engine", "IntentResult"),
    "INTENTS": ("aksara.ai.intent_engine", "INTENTS"),
    # aksara.ai.investigation
    "StepStatus": ("aksara.ai.investigation", "StepStatus"),
    "SessionStatus": ("aksara.ai.investigation", "SessionStatus"),
    "InvestigationStep": ("aksara.ai.investigation", "InvestigationStep"),
    "InvestigationPlan": ("aksara.ai.investigation", "InvestigationPlan"),
    "InvestigationSession": ("aksara.ai.investigation", "InvestigationSession"),
    # aksara.ai.session_store
    "create_session": ("aksara.ai.session_store", "create_session"),
    "get_session": ("aksara.ai.session_store", "get_session"),
    "update_session": ("aksara.ai.session_store", "update_session"),
    "list_sessions": ("aksara.ai.session_store", "list_sessions"),
    "delete_session": ("aksara.ai.session_store", "delete_session"),
    "clear_sessions": ("aksara.ai.session_store", "clear_sessions"),
    "get_active_session": ("aksara.ai.session_store", "get_active_session"),
    # aksara.ai.plan_builder
    "build_plan": ("aksara.ai.plan_builder", "build_plan"),
    "STEP_PROJECT_GRAPH": ("aksara.ai.plan_builder", "STEP_PROJECT_GRAPH"),
    "STEP_PERFORMANCE": ("aksara.ai.plan_builder", "STEP_PERFORMANCE"),
    "STEP_ARCHITECTURE": ("aksara.ai.plan_builder", "STEP_ARCHITECTURE"),
    "STEP_DEBUG": ("aksara.ai.plan_builder", "STEP_DEBUG"),
    "STEP_SUMMARISE": ("aksara.ai.plan_builder", "STEP_SUMMARISE"),
    "build_plan_from_intent": ("aksara.ai.plan_builder", "build_plan_from_intent"),
    "get_step_dependencies": ("aksara.ai.plan_builder", "get_step_dependencies"),
    "get_step_priority": ("aksara.ai.plan_builder", "get_step_priority"),
    # aksara.ai.investigation_runner
    "execute_investigation": ("aksara.ai.investigation_runner", "execute_investigation"),
    "execute_next_step": ("aksara.ai.investigation_runner", "execute_next_step"),
    "get_next_step": ("aksara.ai.investigation_runner", "get_next_step"),
    "run_step": ("aksara.ai.investigation_runner", "run_step"),
    # aksara.ai.daily_briefing
    "DailyBriefing": ("aksara.ai.daily_briefing", "DailyBriefing"),
    "generate_daily_briefing": ("aksara.ai.daily_briefing", "generate_daily_briefing"),
}


def __getattr__(name: str) -> Any:
    """PEP 562: lazily import ai submodule symbols on first access."""
    entry = _LAZY_AI_ATTRS.get(name)
    if entry is not None:
        module_path, attr_name = entry
        module = importlib.import_module(module_path)
        val = getattr(module, attr_name)
        # Cache in module globals so subsequent accesses skip __getattr__.
        globals()[name] = val
        return val
    raise AttributeError(f"module 'aksara.ai' has no attribute {name!r}")


def __dir__() -> list:
    return list(globals()) + list(_LAZY_AI_ATTRS)


__all__ = [
    # Models
    "AiTool",
    "AiToolParam",
    "ToolKind",
    # Registry
    "AiToolRegistry",
    "discover_tools_from_viewset",
    "get_ai_tools_for_request",
    # Exporters
    "export_tools_as_generic",
    "export_tools_as_mcp",
    # FastAPI
    "ai_router",
    # v0.4.1: AI Debug
    "AiDebugContext",
    "AiDebugSuggestion",
    "AiExceptionInfo",
    "AiRequestInfo",
    "AiStackFrame",
    "BaseAiDebugAdvisor",
    "RuleBasedAiDebugAdvisor",
    "build_ai_debug_context",
    "classify_exception",
    "default_advisor",
    # v0.4.2: AI Query Assistant
    "AiFilterCondition",
    "AiQueryPagination",
    "AiQueryPlan",
    "AiQueryRequest",
    "AiQueryResult",
    "AiSortField",
    "execute_ai_query_plan",
    "get_available_models_for_query",
    "get_query_plan_schema",
    "SUPPORTED_LOOKUPS",
    # v0.4.2: AI CodeGen
    "AiCodegenRequest",
    "AiCodegenResult",
    "AiCodegenTarget",
    "AiFieldSpec",
    "AiModelSpec",
    "FIELD_TYPE_MAPPING",
    "generate_admin_code",
    "generate_app_skeleton",
    "generate_code",
    "generate_migration_stub",
    "generate_model_code",
    "generate_serializer_code",
    "generate_viewset_code",
    "get_codegen_schemas",
    # v0.4.2: AI Client
    "BaseAiClient",
    "AiClientConfig",
    "ChatMessage",
    "ToolCall",
    "ChatResponse",
    # v0.4.3: AI Context Engine
    "AiFieldType",
    "AiModelFieldInfo",
    "AiRelationInfo",
    "AiModelInfo",
    "AiActionInfo",
    "AiViewSetInfo",
    "AiRouteInfo",
    "AiMigrationOperationInfo",
    "AiMigrationInfo",
    "AiAdminModelInfo",
    "AiAdminInfo",
    "AiSettingsInfo",
    "AiMiddlewareInfo",
    "AiToolSummary",
    "AiSchemaInfo",
    "AiRouteHintInfo",
    "AiFullContext",
    "build_full_ai_context",
    "build_full_ai_context_sync",
    # v0.4.4: AI Patch Engine
    "PatchOperationType",
    "PatchValidationError",
    "AiPatchOperation",
    "AiPatchRequest",
    "AiPatchValidationResult",
    "AiPatchFileChange",
    "AiPatchResult",
    "validate_operation",
    "validate_patch_request",
    "apply_ai_patches",
    "apply_ai_patches_async",
    "rollback_patches",
    "preview_patch_diff",
    "ALLOWED_OPERATIONS",
    "PROTECTED_PATTERNS",
    # v0.4.5: AI Planner
    "PlanStepType",
    "VALID_STEP_TYPES",
    "AiPlanStep",
    "AiPlan",
    "AiPlanStepResult",
    "AiPlanExecutionResult",
    "execute_plan",
    "validate_plan",
    "get_plan_schema",
    # v0.4.6: AI Runtime (Mini Agent Loop)
    "AgentIntent",
    "AgentContextBundle",
    "AgentPlanExecutionRequest",
    "AgentPlanPreviewResponse",
    "AgentPlanApplyRequest",
    "AgentPlanApplyResponse",
    "build_agent_context_bundle",
    "build_agent_context_bundle_sync",
    # v0.4.7: AI Schema Doctor
    "DriftKind",
    "IssueSeverity",
    "AiSchemaIssue",
    "AiSchemaHealth",
    "AiSchemaIssuesResponse",
    "DbColumnInfo",
    "DbTableInfo",
    "introspect_db_schema",
    "build_model_schema_map",
    "detect_schema_drift",
    "classify_severity",
    "analyze_schema_health",
    # v0.5.11: AI Profiles & Provider Contracts
    # v0.5.12: Added validation
    "AiModelKind",
    "AiProviderKind",
    "AiModelProfile",
    "AiProviderProfile",
    "AiProfileSet",
    "AiProviderSecretHint",
    "AiProviderConfigInfo",
    "AiProfileIssueSeverity",
    "AiProfileIssueKind",
    "AiProfileIssue",
    "AiProfileHealth",
    "AiProviderRegistry",
    "get_ai_provider_registry",
    "build_default_ai_profile_set",
    "build_secret_hints_from_settings",
    "build_example_profile_set",
    "classify_issue_severity",
    "validate_profile_set",
    "validate_default_profile_set",
    # v0.5.13: Per-View AI Hints
    "AiRiskLevel",
    "AiUsageKind",
    "AiRouteHint",
    "AiHintSet",
    "ai_route_hint",
    "set_view_default_hint",
    "get_hint_from_callable",
    "get_default_hint_from_class",
    "extract_hints_from_app",
    "build_ai_hint_set",
    "build_ai_hint_set_sync",
    "HINT_ATTR",
    "DEFAULT_HINT_ATTR",
    # v0.5.37: AI Consolidation & Orchestration
    "OrchestratedIntentMatch",
    "classify_intent",
    "SUPPORTED_INTENTS",
    "ARCHITECTURE_REVIEW",
    "PERFORMANCE_INVESTIGATION",
    "DEBUG_ANALYSIS",
    "PROJECT_ANALYSIS",
    "SCHEMA_EXPLANATION",
    "ROUTE_ANALYSIS",
    "ExecutionPlan",
    "build_execution_plan",
    "build_investigation_plan",
    "INVESTIGATION_PIPELINE",
    "OrchestrationResult",
    "StepResult",
    "handle_prompt",
    "run_investigation",
    "classify_and_plan",
    # v0.5.39: AI Investigation Engine
    "StepStatus",
    "SessionStatus",
    "InvestigationStep",
    "InvestigationPlan",
    "InvestigationSession",
    "create_session",
    "get_session",
    "update_session",
    "list_sessions",
    "delete_session",
    "clear_sessions",
    "build_plan",
    "STEP_PROJECT_GRAPH",
    "STEP_PERFORMANCE",
    "STEP_ARCHITECTURE",
    "STEP_DEBUG",
    "STEP_SUMMARISE",
    "execute_investigation",
    "execute_next_step",
    # v0.5.40: Intent Engine v2, Investigation Continuation, Daily Briefing
    "classify_intent_v2",
    "IntentResult",
    "INTENTS",
    "build_plan_from_intent",
    "get_step_dependencies",
    "get_step_priority",
    "get_active_session",
    "get_next_step",
    "run_step",
    "DailyBriefing",
    "generate_daily_briefing",
]
