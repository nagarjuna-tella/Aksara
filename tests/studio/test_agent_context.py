"""
Tests for Agent Mode — Context Builder.

v0.5.19: Tests for build_agent_context() and AgentContextSection model.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock

from aksara.studio.models import (
    AgentContextSection,
    StudioAgentContext,
)


# =============================================================================
# Model Tests
# =============================================================================


class TestAgentContextSection:
    """Tests for AgentContextSection model."""

    def test_create_minimal(self):
        s = AgentContextSection(
            title="Test", description="A test section", key="test", data={}
        )
        assert s.title == "Test"
        assert s.key == "test"
        assert s.data == {}
        assert s.size_kb == 0.0

    def test_create_with_size(self):
        s = AgentContextSection(
            title="Models", description="All models", key="models",
            data=[{"name": "User"}], size_kb=1.5,
        )
        assert s.size_kb == 1.5
        assert s.data == [{"name": "User"}]

    def test_data_accepts_any_type(self):
        for val in [42, "hello", [1, 2], {"a": 1}, None, True]:
            s = AgentContextSection(
                title="T", description="D", key="k", data=val
            )
            assert s.data == val

    def test_model_dump(self):
        s = AgentContextSection(
            title="T", description="D", key="k", data={"x": 1}, size_kb=0.5,
        )
        d = s.model_dump()
        assert d["title"] == "T"
        assert d["key"] == "k"
        assert d["data"] == {"x": 1}
        assert d["size_kb"] == 0.5


class TestStudioAgentContext:
    """Tests for StudioAgentContext model."""

    def test_create_empty(self):
        ctx = StudioAgentContext()
        assert ctx.total_sections == 0
        assert ctx.total_size_kb == 0.0
        assert ctx.sections == []
        assert isinstance(ctx.generated_at, datetime)

    def test_create_with_sections(self):
        sections = [
            AgentContextSection(title="A", description="D", key="a", data={}, size_kb=1.0),
            AgentContextSection(title="B", description="D", key="b", data={}, size_kb=2.0),
        ]
        ctx = StudioAgentContext(
            total_sections=2, total_size_kb=3.0, sections=sections,
        )
        assert ctx.total_sections == 2
        assert ctx.total_size_kb == 3.0
        assert len(ctx.sections) == 2

    def test_generated_at_is_utc(self):
        ctx = StudioAgentContext()
        assert ctx.generated_at.tzinfo is not None

    def test_model_dump_roundtrip(self):
        ctx = StudioAgentContext(
            total_sections=1, total_size_kb=0.5,
            sections=[AgentContextSection(
                title="T", description="D", key="k", data="v", size_kb=0.5,
            )],
        )
        d = ctx.model_dump(mode="json")
        assert d["total_sections"] == 1
        assert len(d["sections"]) == 1


# =============================================================================
# Builder Tests
# =============================================================================


class TestBuildAgentContext:
    """Tests for build_agent_context()."""

    @pytest.fixture
    def mock_app(self):
        return MagicMock()

    @pytest.mark.asyncio
    async def test_returns_studio_agent_context(self, mock_app):
        with patch("aksara.registry.ModelRegistry") as mock_reg, \
             patch("aksara.studio.utils.build_routes_info", return_value=[]), \
             patch("aksara.studio.utils.build_migration_summary", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_profile_set_summary", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_hints", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_query_inspector", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.compute_schema_checksum", return_value="abc123"), \
             patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda **kw: {})):
            mock_reg.all.return_value = {}

            from aksara.studio.utils import build_agent_context
            ctx = await build_agent_context(mock_app)

            assert isinstance(ctx, StudioAgentContext)
            assert ctx.total_sections == 9
            assert len(ctx.sections) == 9

    @pytest.mark.asyncio
    async def test_section_keys_are_correct(self, mock_app):
        expected_keys = {
            "project_info", "models", "routes", "migrations",
            "diagnostics", "ai_profiles", "ai_hints", "db_queries",
            "schema_checksum",
        }
        with patch("aksara.registry.ModelRegistry") as mock_reg, \
             patch("aksara.studio.utils.build_routes_info", return_value=[]), \
             patch("aksara.studio.utils.build_migration_summary", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_profile_set_summary", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_hints", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_query_inspector", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.compute_schema_checksum", return_value="abc123"), \
             patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda **kw: {})):
            mock_reg.all.return_value = {}

            from aksara.studio.utils import build_agent_context
            ctx = await build_agent_context(mock_app)
            keys = {s.key for s in ctx.sections}
            assert keys == expected_keys

    @pytest.mark.asyncio
    async def test_total_size_is_sum(self, mock_app):
        with patch("aksara.registry.ModelRegistry") as mock_reg, \
             patch("aksara.studio.utils.build_routes_info", return_value=[]), \
             patch("aksara.studio.utils.build_migration_summary", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_profile_set_summary", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_hints", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_query_inspector", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.compute_schema_checksum", return_value="abc123"), \
             patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda **kw: {})):
            mock_reg.all.return_value = {}

            from aksara.studio.utils import build_agent_context
            ctx = await build_agent_context(mock_app)
            expected_total = round(sum(s.size_kb for s in ctx.sections), 2)
            assert ctx.total_size_kb == expected_total

    @pytest.mark.asyncio
    async def test_project_info_section_has_version(self, mock_app):
        with patch("aksara.registry.ModelRegistry") as mock_reg, \
             patch("aksara.studio.utils.build_routes_info", return_value=[]), \
             patch("aksara.studio.utils.build_migration_summary", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_profile_set_summary", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_hints", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_query_inspector", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.compute_schema_checksum", return_value="abc123"), \
             patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda **kw: {})):
            mock_reg.all.return_value = {}

            from aksara.studio.utils import build_agent_context
            ctx = await build_agent_context(mock_app)
            pi = next(s for s in ctx.sections if s.key == "project_info")
            assert "aksara_version" in pi.data
            assert "python_version" in pi.data

    @pytest.mark.asyncio
    async def test_size_kb_computed_correctly(self, mock_app):
        """Each section's size_kb should match json-serialized length / 1024."""
        import json
        with patch("aksara.registry.ModelRegistry") as mock_reg, \
             patch("aksara.studio.utils.build_routes_info", return_value=[]), \
             patch("aksara.studio.utils.build_migration_summary", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_profile_set_summary", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_hints", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_query_inspector", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.compute_schema_checksum", return_value="abc123"), \
             patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda **kw: {})):
            mock_reg.all.return_value = {}

            from aksara.studio.utils import build_agent_context
            ctx = await build_agent_context(mock_app)
            for s in ctx.sections:
                expected = round(len(json.dumps(s.data, default=str)) / 1024.0, 2)
                assert s.size_kb == expected

    @pytest.mark.asyncio
    async def test_handles_model_registry_error(self, mock_app):
        with patch("aksara.registry.ModelRegistry") as mock_reg, \
             patch("aksara.studio.utils.build_routes_info", return_value=[]), \
             patch("aksara.studio.utils.build_migration_summary", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_profile_set_summary", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_hints", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_query_inspector", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.compute_schema_checksum", return_value="abc123"), \
             patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda **kw: {})):
            mock_reg.all.side_effect = Exception("Registry broken")

            from aksara.studio.utils import build_agent_context
            ctx = await build_agent_context(mock_app)
            models_section = next(s for s in ctx.sections if s.key == "models")
            assert models_section.data == []

    @pytest.mark.asyncio
    async def test_handles_diagnostics_error(self, mock_app):
        with patch("aksara.registry.ModelRegistry") as mock_reg, \
             patch("aksara.studio.utils.build_routes_info", return_value=[]), \
             patch("aksara.studio.utils.build_migration_summary", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_profile_set_summary", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_hints", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_query_inspector", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.compute_schema_checksum", return_value="abc123"), \
             patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, side_effect=Exception("diag fail")):
            mock_reg.all.return_value = {}

            from aksara.studio.utils import build_agent_context
            ctx = await build_agent_context(mock_app)
            diag = next(s for s in ctx.sections if s.key == "diagnostics")
            assert diag.data == {}


# =============================================================================
# Helper Tests
# =============================================================================


class TestSectionSizeKb:
    """Tests for _section_size_kb helper."""

    def test_empty_dict(self):
        from aksara.studio.utils import _section_size_kb
        assert _section_size_kb({}) == pytest.approx(len("{}") / 1024.0)

    def test_string_data(self):
        from aksara.studio.utils import _section_size_kb
        result = _section_size_kb("hello")
        assert result > 0

    def test_none_data(self):
        from aksara.studio.utils import _section_size_kb
        result = _section_size_kb(None)
        assert result == pytest.approx(len("null") / 1024.0)

    def test_non_serializable_returns_small_value(self):
        from aksara.studio.utils import _section_size_kb
        # object() is serialized via default=str, so it returns a small nonzero value
        result = _section_size_kb(object())
        assert result >= 0


class TestMakeSection:
    """Tests for _make_section helper."""

    def test_creates_section_with_computed_size(self):
        from aksara.studio.utils import _make_section
        s = _make_section("test", "Test", "A test", {"key": "value"})
        assert s.key == "test"
        assert s.title == "Test"
        assert s.size_kb > 0

    def test_size_matches_json_length(self):
        import json
        from aksara.studio.utils import _make_section
        data = {"a": 1, "b": [2, 3]}
        s = _make_section("k", "T", "D", data)
        expected = round(len(json.dumps(data, default=str)) / 1024.0, 2)
        assert s.size_kb == expected
