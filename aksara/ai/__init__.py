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

v0.4.0: Initial AI Mode release
v0.4.1: AI Debug Assistant
v0.4.2: AI Query Assistant & CodeGen (Provider-Agnostic)
v0.4.3: AI Context Engine (THE BRAIN DATA)
v0.4.4: AI Patch Engine (THE SURGEON)
v0.4.5: AI Planner (THE ARCHITECT)
v0.4.6: AI Runtime (Mini Agent Loop)
v0.4.7: AI Schema Doctor & Migration Guardrails
"""

from aksara.ai.models import AiTool, AiToolParam, ToolKind
from aksara.ai.registry import (
    AiToolRegistry,
    discover_tools_from_viewset,
    get_ai_tools_for_request,
)
from aksara.ai.exporters import (
    export_tools_as_generic,
    export_tools_as_mcp,
)
from aksara.ai.fastapi import router as ai_router

# v0.4.1: AI Debug exports
from aksara.ai.debug import (
    AiDebugContext,
    AiDebugSuggestion,
    AiExceptionInfo,
    AiRequestInfo,
    AiStackFrame,
    BaseAiDebugAdvisor,
    RuleBasedAiDebugAdvisor,
    build_ai_debug_context,
    classify_exception,
    default_advisor,
)

# v0.4.2: AI Query Assistant exports
from aksara.ai.query import (
    AiFilterCondition,
    AiQueryPagination,
    AiQueryPlan,
    AiQueryRequest,
    AiQueryResult,
    AiSortField,
    execute_ai_query_plan,
    get_available_models_for_query,
    get_query_plan_schema,
    SUPPORTED_LOOKUPS,
)

# v0.4.2: AI CodeGen exports
from aksara.ai.codegen import (
    AiCodegenRequest,
    AiCodegenResult,
    AiCodegenTarget,
    AiFieldSpec,
    AiModelSpec,
    FIELD_TYPE_MAPPING,
    generate_admin_code,
    generate_app_skeleton,
    generate_code,
    generate_migration_stub,
    generate_model_code,
    generate_serializer_code,
    generate_viewset_code,
    get_codegen_schemas,
)

# v0.4.2: AI Client protocol
from aksara.ai.client import (
    BaseAiClient,
    AiClientConfig,
    ChatMessage,
    ToolCall,
    ChatResponse,
)

# v0.4.3: AI Context Engine exports
from aksara.ai.context import (
    # Field types
    AiFieldType,
    # Model info
    AiModelFieldInfo,
    AiRelationInfo,
    AiModelInfo,
    # ViewSet info
    AiActionInfo,
    AiViewSetInfo,
    # Route info
    AiRouteInfo,
    # Migration info
    AiMigrationOperationInfo,
    AiMigrationInfo,
    # Admin info
    AiAdminModelInfo,
    AiAdminInfo,
    # Settings & Middleware
    AiSettingsInfo,
    AiMiddlewareInfo,
    # AI Tools & Schemas
    AiToolSummary,
    AiSchemaInfo,
    # Full context
    AiFullContext,
    # Builder functions
    build_full_ai_context,
    build_full_ai_context_sync,
)

# v0.4.4: AI Patch Engine exports
from aksara.ai.patch import (
    # Enums
    PatchOperationType,
    PatchValidationError,
    # Models
    AiPatchOperation,
    AiPatchRequest,
    AiPatchValidationResult,
    AiPatchFileChange,
    AiPatchResult,
    # Validation
    validate_operation,
    validate_patch_request,
    # Orchestrator
    apply_ai_patches,
    apply_ai_patches_async,
    # Utilities
    rollback_patches,
    preview_patch_diff,
    # Constants
    ALLOWED_OPERATIONS,
    PROTECTED_PATTERNS,
)

# v0.4.5: AI Planner exports
from aksara.ai.planner import (
    # Types
    PlanStepType,
    VALID_STEP_TYPES,
    # Models
    AiPlanStep,
    AiPlan,
    AiPlanStepResult,
    AiPlanExecutionResult,
    # Execution
    execute_plan,
    validate_plan,
    get_plan_schema,
)

# v0.4.6: AI Runtime (Mini Agent Loop) exports
from aksara.ai.agent import (
    # Models
    AgentIntent,
    AgentContextBundle,
    AgentPlanExecutionRequest,
    AgentPlanPreviewResponse,
    AgentPlanApplyRequest,
    AgentPlanApplyResponse,
    # Builder
    build_agent_context_bundle,
    build_agent_context_bundle_sync,
)

# v0.4.7: AI Schema Doctor exports
from aksara.ai.schema_doctor import (
    # Type Literals
    DriftKind,
    IssueSeverity,
    # Models
    AiSchemaIssue,
    AiSchemaHealth,
    AiSchemaIssuesResponse,
    DbColumnInfo,
    DbTableInfo,
    # Functions
    introspect_db_schema,
    build_model_schema_map,
    detect_schema_drift,
    classify_severity,
    analyze_schema_health,
)

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
]
