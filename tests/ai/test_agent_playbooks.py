"""
Tests for Agent Playbooks — Registry & Models.

v0.5.20: Tests for playbook models, built-in registry, and filtering.
"""

import pytest
from aksara.studio.models import (
    AgentPlaybook,
    AgentPlaybookSet,
    AgentPlaybookStep,
    StudioAgentPlaybookPromptRequest,
)
from aksara.ai.playbooks import (
    get_builtin_playbooks,
    get_playbook_by_key,
    build_playbook_set,
)


# =============================================================================
# Model Tests
# =============================================================================


class TestAgentPlaybookStep:
    """Tests for AgentPlaybookStep model."""

    def test_create_minimal(self):
        step = AgentPlaybookStep(
            id="s1", title="Step 1", description="Do something",
        )
        assert step.id == "s1"
        assert step.title == "Step 1"
        assert step.description == "Do something"
        assert step.recommended_sections == []
        assert step.estimated_impact is None

    def test_create_full(self):
        step = AgentPlaybookStep(
            id="s2", title="Step 2", description="Do more",
            recommended_sections=["models", "routes"],
            estimated_impact="schema change",
        )
        assert step.recommended_sections == ["models", "routes"]
        assert step.estimated_impact == "schema change"

    def test_model_dump(self):
        step = AgentPlaybookStep(
            id="s1", title="T", description="D",
            estimated_impact="low risk",
        )
        d = step.model_dump()
        assert d["id"] == "s1"
        assert d["estimated_impact"] == "low risk"
        assert d["recommended_sections"] == []


class TestAgentPlaybook:
    """Tests for AgentPlaybook model."""

    def test_create_minimal(self):
        pb = AgentPlaybook(
            key="test_pb",
            label="Test Playbook",
            kind="add_field",
            description="A test playbook",
            category="schema",
            default_goal_template="Do {thing}.",
        )
        assert pb.key == "test_pb"
        assert pb.kind == "add_field"
        assert pb.risk_level == "low"
        assert pb.usage_kind == "read_only"
        assert pb.default_sections == []
        assert pb.steps == []
        assert pb.tags == []
        assert pb.notes is None

    def test_create_full(self):
        pb = AgentPlaybook(
            key="full_pb",
            label="Full Playbook",
            kind="add_endpoint",
            description="Full featured",
            category="api",
            default_goal_template="Add {endpoint}.",
            risk_level="high",
            usage_kind="admin",
            default_sections=["routes", "models"],
            steps=[
                AgentPlaybookStep(id="s1", title="S1", description="D1"),
            ],
            tags=["tag1", "tag2"],
            notes="Be careful.",
        )
        assert pb.risk_level == "high"
        assert pb.usage_kind == "admin"
        assert len(pb.steps) == 1
        assert pb.tags == ["tag1", "tag2"]
        assert pb.notes == "Be careful."

    def test_model_dump_roundtrip(self):
        pb = AgentPlaybook(
            key="rt", label="RT", kind="debug_queries",
            description="D", category="diagnostics",
            default_goal_template="Debug.",
        )
        d = pb.model_dump()
        pb2 = AgentPlaybook(**d)
        assert pb2.key == pb.key
        assert pb2.kind == pb.kind


class TestAgentPlaybookSet:
    """Tests for AgentPlaybookSet model."""

    def test_empty(self):
        s = AgentPlaybookSet()
        assert s.playbooks == []
        assert s.total_count == 0
        assert s.by_category == {}
        assert s.by_risk_level == {}
        assert s.by_usage_kind == {}

    def test_with_playbooks(self):
        pb = AgentPlaybook(
            key="k", label="L", kind="add_field",
            description="D", category="schema",
            default_goal_template="G.",
        )
        s = AgentPlaybookSet(
            playbooks=[pb],
            total_count=1,
            by_category={"schema": 1},
            by_risk_level={"low": 1},
            by_usage_kind={"read_only": 1},
        )
        assert s.total_count == 1
        assert len(s.playbooks) == 1


class TestStudioAgentPlaybookPromptRequest:
    """Tests for StudioAgentPlaybookPromptRequest model."""

    def test_create_minimal(self):
        req = StudioAgentPlaybookPromptRequest(playbook_key="test_pb")
        assert req.playbook_key == "test_pb"
        assert req.user_goal is None
        assert req.selected_sections is None
        assert req.custom_system_prompt is None

    def test_create_full(self):
        req = StudioAgentPlaybookPromptRequest(
            playbook_key="add_field_to_model",
            user_goal="Add a name field",
            selected_sections=["models", "migrations"],
            custom_system_prompt="Be careful.",
        )
        assert req.user_goal == "Add a name field"
        assert req.selected_sections == ["models", "migrations"]


# =============================================================================
# Registry Tests
# =============================================================================


class TestGetBuiltinPlaybooks:
    """Tests for get_builtin_playbooks()."""

    def test_returns_all_playbooks(self):
        result = get_builtin_playbooks()
        assert isinstance(result, AgentPlaybookSet)
        assert result.total_count >= 7
        assert len(result.playbooks) == result.total_count

    def test_all_playbooks_have_required_fields(self):
        result = get_builtin_playbooks()
        for pb in result.playbooks:
            assert pb.key
            assert pb.label
            assert pb.kind
            assert pb.description
            assert pb.category
            assert pb.default_goal_template
            assert pb.risk_level in ("low", "medium", "high")
            assert pb.usage_kind in ("read_only", "write", "admin")
            assert len(pb.steps) >= 2

    def test_unique_keys(self):
        result = get_builtin_playbooks()
        keys = [pb.key for pb in result.playbooks]
        assert len(keys) == len(set(keys))

    def test_aggregate_counts(self):
        result = get_builtin_playbooks()
        assert sum(result.by_category.values()) == result.total_count
        assert sum(result.by_risk_level.values()) == result.total_count
        assert sum(result.by_usage_kind.values()) == result.total_count

    def test_filter_by_category(self):
        result = get_builtin_playbooks(category="schema")
        assert result.total_count >= 1
        for pb in result.playbooks:
            assert pb.category == "schema"

    def test_filter_by_category_empty(self):
        result = get_builtin_playbooks(category="nonexistent")
        assert result.total_count == 0
        assert result.playbooks == []

    def test_filter_by_risk_level(self):
        result = get_builtin_playbooks(risk_level="high")
        assert result.total_count >= 1
        for pb in result.playbooks:
            assert pb.risk_level == "high"

    def test_filter_by_usage_kind(self):
        result = get_builtin_playbooks(usage_kind="admin")
        assert result.total_count >= 1
        for pb in result.playbooks:
            assert pb.usage_kind == "admin"

    def test_filter_combined(self):
        result = get_builtin_playbooks(category="schema", risk_level="low")
        for pb in result.playbooks:
            assert pb.category == "schema"
            assert pb.risk_level == "low"

    def test_each_step_has_required_fields(self):
        result = get_builtin_playbooks()
        for pb in result.playbooks:
            for step in pb.steps:
                assert step.id
                assert step.title
                assert step.description


class TestGetPlaybookByKey:
    """Tests for get_playbook_by_key()."""

    def test_find_existing(self):
        pb = get_playbook_by_key("add_field_to_model")
        assert pb is not None
        assert pb.key == "add_field_to_model"
        assert pb.kind == "add_field"
        assert pb.category == "schema"

    def test_find_each_builtin(self):
        result = get_builtin_playbooks()
        for expected in result.playbooks:
            found = get_playbook_by_key(expected.key)
            assert found is not None
            assert found.key == expected.key

    def test_not_found(self):
        pb = get_playbook_by_key("nonexistent_playbook")
        assert pb is None

    def test_empty_key(self):
        pb = get_playbook_by_key("")
        assert pb is None


class TestBuildPlaybookSet:
    """Tests for build_playbook_set()."""

    def test_empty_list(self):
        result = build_playbook_set([])
        assert result.total_count == 0
        assert result.by_category == {}

    def test_single_playbook(self):
        pb = AgentPlaybook(
            key="x", label="X", kind="add_field",
            description="D", category="schema",
            default_goal_template="G.",
            risk_level="medium", usage_kind="write",
        )
        result = build_playbook_set([pb])
        assert result.total_count == 1
        assert result.by_category == {"schema": 1}
        assert result.by_risk_level == {"medium": 1}
        assert result.by_usage_kind == {"write": 1}

    def test_multiple_categories(self):
        pbs = [
            AgentPlaybook(
                key="a", label="A", kind="add_field",
                description="D", category="schema",
                default_goal_template="G.",
            ),
            AgentPlaybook(
                key="b", label="B", kind="add_endpoint",
                description="D", category="api",
                default_goal_template="G.",
            ),
        ]
        result = build_playbook_set(pbs)
        assert result.total_count == 2
        assert result.by_category == {"schema": 1, "api": 1}


# =============================================================================
# Known Playbook Spot-Checks
# =============================================================================


class TestKnownPlaybooks:
    """Spot-checks for specific built-in playbooks."""

    def test_add_field_to_model(self):
        pb = get_playbook_by_key("add_field_to_model")
        assert pb is not None
        assert pb.category == "schema"
        assert pb.risk_level == "medium"
        assert pb.usage_kind == "write"
        assert len(pb.steps) >= 3
        assert "models" in pb.default_sections
        assert "{field_name}" in pb.default_goal_template or "{model_name}" in pb.default_goal_template

    def test_fix_migration_conflicts(self):
        pb = get_playbook_by_key("fix_migration_conflicts")
        assert pb is not None
        assert pb.category == "migrations"
        assert pb.risk_level == "high"
        assert pb.usage_kind == "admin"

    def test_debug_slow_queries(self):
        pb = get_playbook_by_key("debug_slow_queries")
        assert pb is not None
        assert pb.category == "diagnostics"
        assert pb.risk_level == "low"
        assert pb.usage_kind == "read_only"
        assert "db_queries" in pb.default_sections

    def test_harden_endpoint_permissions(self):
        pb = get_playbook_by_key("harden_endpoint_permissions")
        assert pb is not None
        assert pb.category == "api"
        assert pb.usage_kind == "admin"

    def test_add_validation_rule(self):
        pb = get_playbook_by_key("add_validation_rule")
        assert pb is not None
        assert pb.risk_level == "low"
        assert pb.usage_kind == "write"

    def test_refactor_model_and_serializer(self):
        pb = get_playbook_by_key("refactor_model_and_serializer")
        assert pb is not None
        assert pb.category == "schema"
        assert len(pb.steps) >= 4

    def test_add_api_action_to_viewset(self):
        pb = get_playbook_by_key("add_api_action_to_viewset")
        assert pb is not None
        assert pb.category == "api"
        assert pb.kind == "add_endpoint"
