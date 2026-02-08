"""
Aksara Studio - Bridge for Aksara Studio IDE integration.

v0.5.0: Studio Core & Handshake
v0.5.1: Studio Core Polish - richer summaries, security, migrations endpoint
v0.5.2: Runtime & DX - runtime info, routes endpoint
v0.5.4: Studio ↔ AI Integration - AI context export, schemas, prompts

This module provides the Studio API endpoints and utilities for
integrating Aksara applications with Aksara Studio IDE.

Endpoints:
- GET /studio/handshake - Complete project handshake for Studio
- GET /studio/context/summary - Lightweight schema summary
- GET /studio/health - Simple health check with DB status
- GET /studio/migrations/summary - Per-app migration statistics (v0.5.1)
- GET /studio/schema/handshake - JSON schema for handshake model (v0.5.1)
- GET /studio/runtime/info - Runtime diagnostics (v0.5.2)
- GET /studio/runtime/routes - Route metadata (v0.5.2)
- GET /studio/ai/context - AI context export (v0.5.4)
- GET /studio/ai/schemas - AI operation schemas (v0.5.4)
- GET /studio/ai/prompts - Prompt templates (v0.5.4)

CLI:
- aksara studio handshake - Test handshake locally
- aksara studio url - Show Studio URLs
- aksara studio ai-context - Export AI context (v0.5.4)
"""

from aksara.studio.models import (
    StudioHandshake,
    StudioCapability,
    StudioDatabaseStatus,
    StudioProjectInfo,
    StudioChecksums,
    StudioContextSummary,
    StudioHealthResponse,
    # v0.5.1: New models
    StudioMigrationStatus,
    StudioAppMigrationSummary,
    StudioMigrationConflict,
    StudioMigrationSummary,
    # v0.5.2: Runtime models
    StudioRuntimeInfo,
    StudioRouteInfo,
    # v0.5.4: AI Integration models
    StudioAiProjectMeta,
    StudioAiModelSummary,
    StudioAiRouteSummary,
    StudioAiToolInfo,
    StudioAiContextExport,
    StudioAiSchemas,
    StudioAiPromptTemplate,
    StudioAiPrompts,
    # v0.5.19: Agent Mode models
    AgentContextSection,
    StudioAgentContext,
    StudioAgentPromptRequest,
    StudioAgentPromptResponse,
    # v0.5.20: Agent Playbooks models
    AgentPlaybookStep,
    AgentPlaybook,
    AgentPlaybookSet,
    StudioAgentPlaybookPromptRequest,
)
from aksara.studio.utils import (
    build_studio_handshake,
    build_context_summary,
    build_health_response,
    compute_schema_checksum,
    # v0.5.1: New util
    build_migration_summary,
    # v0.5.2: Runtime utils
    build_runtime_info,
    build_routes_info,
    # v0.5.4: AI Integration utils
    build_ai_context_export,
    build_ai_schemas,
    build_ai_prompts,
    # v0.5.19: Agent Mode utils
    build_agent_context,
    build_agent_prompt,
    # v0.5.20: Agent Playbooks utils
    build_agent_prompt_from_playbook,
)
from aksara.studio.fastapi import router as studio_router

__all__ = [
    # Models
    "StudioHandshake",
    "StudioCapability",
    "StudioDatabaseStatus",
    "StudioProjectInfo",
    "StudioChecksums",
    "StudioContextSummary",
    "StudioHealthResponse",
    # v0.5.1: New models
    "StudioMigrationStatus",
    "StudioAppMigrationSummary",
    "StudioMigrationConflict",
    "StudioMigrationSummary",
    # v0.5.2: Runtime models
    "StudioRuntimeInfo",
    "StudioRouteInfo",
    # v0.5.4: AI Integration models
    "StudioAiProjectMeta",
    "StudioAiModelSummary",
    "StudioAiRouteSummary",
    "StudioAiToolInfo",
    "StudioAiContextExport",
    "StudioAiSchemas",
    "StudioAiPromptTemplate",
    "StudioAiPrompts",
    # v0.5.19: Agent Mode models
    "AgentContextSection",
    "StudioAgentContext",
    "StudioAgentPromptRequest",
    "StudioAgentPromptResponse",
    # v0.5.20: Agent Playbooks models
    "AgentPlaybookStep",
    "AgentPlaybook",
    "AgentPlaybookSet",
    "StudioAgentPlaybookPromptRequest",
    # Utils
    "build_studio_handshake",
    "build_context_summary",
    "build_health_response",
    "compute_schema_checksum",
    "build_migration_summary",  # v0.5.1
    "build_runtime_info",  # v0.5.2
    "build_routes_info",  # v0.5.2
    "build_ai_context_export",  # v0.5.4
    "build_ai_schemas",  # v0.5.4
    "build_ai_prompts",  # v0.5.4
    "build_agent_context",  # v0.5.19
    "build_agent_prompt",  # v0.5.19
    "build_agent_prompt_from_playbook",  # v0.5.20
    # Router
    "studio_router",
]
