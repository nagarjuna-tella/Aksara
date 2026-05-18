"""Regression tests for AI metadata propagation across AI-facing surfaces.

Verifies that fields marked as sensitive or non-writable do not leak into:
    - discovered AI CRUD tool schemas
    - MCP tool exports
    - console-generated model prompt packs
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _FakeDefaults:
    chat_model = "gpt-4o"
    chat_provider = "openai"
    code_model = "gpt-4o"
    code_provider = "openai"
    embeddings_model = "text-embedding-3-small"
    embeddings_provider = "openai"


class _FakeProvider:
    kind = "openai"
    enabled = True
    is_configured = True
    api_key = "sk-test"
    model = "gpt-4o"
    base_url = ""

    def get_supported_modes(self):
        return ["chat"]

    def to_unified_provider(self):
        return MagicMock()


class _FakeHub:
    providers = [_FakeProvider()]
    defaults = _FakeDefaults()
    active_provider = "openai"
    version = "0.5.47"

    def configured_providers(self):
        return [_FakeProvider()]

    def get_provider(self, kind):
        return _FakeProvider() if kind == "openai" else None

    def provider_status_summary(self):
        return {}

    def resolve_defaults(self):
        return {}

    def to_safe_dict(self):
        return {}


@pytest.fixture(autouse=True)
def clear_model_and_schema_state():
    """Reset model and schema caches around each test."""
    from aksara.api.schemas import clear_schema_cache
    from aksara.registry import ModelRegistry

    ModelRegistry.clear()
    clear_schema_cache()
    yield
    ModelRegistry.clear()
    clear_schema_cache()


def _build_probe_viewset():
    """Create a model/viewset pair with restricted AI field metadata."""
    from aksara import fields
    from aksara.api.viewsets import ModelViewSet
    from aksara.model.base import Model

    class AiMetadataProbe(Model):
        __tablename__ = "ai_metadata_probe"

        id = fields.UUID(primary_key=True)
        name = fields.String(max_length=255)
        secret = fields.String(max_length=255, ai_sensitive=True)
        internal_score = fields.Integer(default=0, ai_agent_writable=False)

    class AiMetadataProbeViewSet(ModelViewSet):
        model = AiMetadataProbe
        prefix = "/api/ai-metadata-probe"
        ai_exposed = True

    return AiMetadataProbe, AiMetadataProbeViewSet


def _get_crud_tool_map(viewset_cls):
    """Discover CRUD tools and index them by name."""
    from aksara.ai.registry import discover_tools_from_viewset

    return {
        tool.name: tool
        for tool in discover_tools_from_viewset(viewset_cls)
    }


def _assert_restricted_fields_are_absent(properties: set[str]) -> None:
    """Assert the regression surface omits restricted field names."""
    assert "secret" not in properties
    assert "internal_score" not in properties
    assert "name" in properties


class TestAiMetadataPropagation:
    """Regression coverage for AI metadata filtering on all exposed surfaces."""

    def test_tool_schemas_exclude_sensitive_and_non_writable_fields(self):
        model_cls, viewset_cls = _build_probe_viewset()
        tool_map = _get_crud_tool_map(viewset_cls)

        for action_name in ("create", "update"):
            tool = tool_map[f"{model_cls.__name__.lower()}_{action_name}"]
            _assert_restricted_fields_are_absent(set(tool.input_schema.get("properties", {})))

    def test_mcp_export_excludes_sensitive_and_non_writable_fields(self):
        from aksara.ai.exporters import export_tools_as_mcp

        model_cls, viewset_cls = _build_probe_viewset()
        tools = list(_get_crud_tool_map(viewset_cls).values())
        mcp_tools = {
            tool["name"]: tool
            for tool in export_tools_as_mcp(tools)
        }

        for action_name in ("create", "update"):
            tool = mcp_tools[f"{model_cls.__name__.lower()}_{action_name}"]
            _assert_restricted_fields_are_absent(set(tool["inputSchema"].get("properties", {})))

    @pytest.mark.asyncio
    async def test_console_prompt_pack_excludes_sensitive_and_non_writable_fields(self):
        from aksara.ai.console_engine import run_console_query

        model_cls, _viewset_cls = _build_probe_viewset()

        runtime_result = {
            "ok": True,
            "provider": "openai",
            "model": "gpt-4o",
            "response": "Model summary",
            "tokens": {"prompt": 10, "completion": 20, "total": 30},
            "elapsed_ms": 25.0,
            "error": None,
        }

        with patch(
            "aksara.ai.hub_settings.load_aihub_settings",
            return_value=_FakeHub(),
        ), patch(
            "aksara.ai.runtime.run_prompt_pack",
            new_callable=AsyncMock,
            return_value=runtime_result,
        ):
            result = await run_console_query(f"explain the {model_cls.__name__} model")

        prompt_pack = result["prompt_pack"] or {}
        user_prompt = prompt_pack.get("user_prompt", "")

        assert "secret" not in user_prompt
        assert "internal_score" not in user_prompt
        assert "name" in user_prompt