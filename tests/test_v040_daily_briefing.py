"""
v0.5.40 — Daily Briefing Engine Tests

Tests for the daily briefing engine: data model, generation,
score calculation, and CLI/API integration.
"""

from __future__ import annotations

import pytest


# =============================================================================
# 1. Import Tests
# =============================================================================


class TestImports:
    """Verify all daily briefing symbols are importable."""

    def test_import_daily_briefing(self):
        from aksara.ai.daily_briefing import (
            DailyBriefing,
            generate_daily_briefing,
        )
        assert DailyBriefing is not None
        assert callable(generate_daily_briefing)

    def test_import_internal_helpers(self):
        from aksara.ai.daily_briefing import (
            _score_to_grade,
            _build_summary,
            _build_recommendations,
            _collect_project_graph,
            _collect_performance,
            _collect_architecture,
            _collect_debug,
            _collect_recent_investigations,
        )
        assert callable(_score_to_grade)
        assert callable(_build_summary)
        assert callable(_build_recommendations)
        assert callable(_collect_project_graph)


# =============================================================================
# 2. DailyBriefing Model Tests
# =============================================================================


class TestDailyBriefingModel:
    """Test the DailyBriefing dataclass."""

    def test_default_construction(self):
        from aksara.ai.daily_briefing import DailyBriefing

        briefing = DailyBriefing()
        assert briefing.summary == ""
        assert briefing.performance_score == -1.0
        assert briefing.architecture_score == -1.0
        assert briefing.issues == []
        assert briefing.recommendations == []
        assert briefing.debug_signals == []
        assert briefing.recent_investigations == []

    def test_custom_construction(self):
        from aksara.ai.daily_briefing import DailyBriefing

        briefing = DailyBriefing(
            summary="All good",
            performance_score=85.0,
            architecture_score=90.0,
            issues=["Missing index"],
            recommendations=["Add index"],
        )
        assert briefing.summary == "All good"
        assert briefing.performance_score == 85.0
        assert len(briefing.issues) == 1

    def test_to_dict(self):
        from aksara.ai.daily_briefing import DailyBriefing

        briefing = DailyBriefing(
            summary="Test",
            performance_score=72.567,
            architecture_score=88.1,
            issues=["Slow query"],
            recommendations=["Optimize"],
            elapsed_ms=123.456,
            generated_at="2026-01-01T00:00:00+00:00",
        )
        d = briefing.to_dict()
        assert d["summary"] == "Test"
        assert d["performance_score"] == 72.567
        assert d["elapsed_ms"] == 123.5
        assert len(d["issues"]) == 1
        assert d["generated_at"] == "2026-01-01T00:00:00+00:00"

    def test_to_summary_dict(self):
        from aksara.ai.daily_briefing import DailyBriefing

        briefing = DailyBriefing(
            summary="Summary",
            performance_score=80.0,
            architecture_score=85.0,
            issues=["a", "b"],
            recommendations=["c"],
        )
        s = briefing.to_summary_dict()
        assert s["issue_count"] == 2
        assert s["recommendation_count"] == 1
        assert "summary" in s


# =============================================================================
# 3. Score to Grade Tests
# =============================================================================


class TestScoreToGrade:
    """Test the _score_to_grade helper."""

    def test_grade_a(self):
        from aksara.ai.daily_briefing import _score_to_grade

        assert _score_to_grade(95) == "A"
        assert _score_to_grade(90) == "A"

    def test_grade_b(self):
        from aksara.ai.daily_briefing import _score_to_grade

        assert _score_to_grade(85) == "B"
        assert _score_to_grade(80) == "B"

    def test_grade_c(self):
        from aksara.ai.daily_briefing import _score_to_grade

        assert _score_to_grade(75) == "C"
        assert _score_to_grade(70) == "C"

    def test_grade_d(self):
        from aksara.ai.daily_briefing import _score_to_grade

        assert _score_to_grade(65) == "D"
        assert _score_to_grade(60) == "D"

    def test_grade_f(self):
        from aksara.ai.daily_briefing import _score_to_grade

        assert _score_to_grade(50) == "F"
        assert _score_to_grade(0) == "F"


# =============================================================================
# 4. Summary Builder Tests
# =============================================================================


class TestBuildSummary:
    """Test the _build_summary helper."""

    def test_summary_with_scores(self):
        from aksara.ai.daily_briefing import _build_summary

        summary = _build_summary(85.0, 90.0, [], {"counts": {"models": 5, "routes": 10}})
        assert "5 models" in summary
        assert "10 routes" in summary
        assert "Performance" in summary
        assert "Architecture" in summary

    def test_summary_with_issues(self):
        from aksara.ai.daily_briefing import _build_summary

        summary = _build_summary(70.0, 80.0, ["issue1", "issue2"], {})
        assert "2 issue" in summary

    def test_summary_with_no_data(self):
        from aksara.ai.daily_briefing import _build_summary

        summary = _build_summary(-1.0, -1.0, [], {})
        assert "No critical issues" in summary

    def test_summary_negative_scores_omitted(self):
        from aksara.ai.daily_briefing import _build_summary

        summary = _build_summary(-1.0, -1.0, [], {"counts": {"models": 3, "routes": 2}})
        assert "Performance" not in summary
        assert "Architecture" not in summary


# =============================================================================
# 5. Recommendations Builder Tests
# =============================================================================


class TestBuildRecommendations:
    """Test the _build_recommendations helper."""

    def test_low_performance_recommendation(self):
        from aksara.ai.daily_briefing import _build_recommendations

        recs = _build_recommendations(50.0, 90.0, [])
        assert any("performance" in r.lower() for r in recs)

    def test_low_architecture_recommendation(self):
        from aksara.ai.daily_briefing import _build_recommendations

        recs = _build_recommendations(90.0, 50.0, [])
        assert any("architecture" in r.lower() for r in recs)

    def test_issues_recommendation(self):
        from aksara.ai.daily_briefing import _build_recommendations

        recs = _build_recommendations(90.0, 90.0, ["something"])
        assert any("issue" in r.lower() for r in recs)

    def test_healthy_recommendation(self):
        from aksara.ai.daily_briefing import _build_recommendations

        recs = _build_recommendations(90.0, 90.0, [])
        assert any("healthy" in r.lower() for r in recs)


# =============================================================================
# 6. Full Generation Tests
# =============================================================================


class TestGenerateDailyBriefing:
    """Test the full generate_daily_briefing function."""

    def test_generates_briefing(self):
        from aksara.ai.daily_briefing import generate_daily_briefing

        briefing = generate_daily_briefing()
        assert briefing is not None
        assert isinstance(briefing.summary, str)
        assert briefing.generated_at != ""
        assert briefing.elapsed_ms >= 0

    def test_briefing_has_recommendations(self):
        from aksara.ai.daily_briefing import generate_daily_briefing

        briefing = generate_daily_briefing()
        # Should always have at least one recommendation
        assert len(briefing.recommendations) >= 1

    def test_briefing_to_dict_is_json_safe(self):
        import json
        from aksara.ai.daily_briefing import generate_daily_briefing

        briefing = generate_daily_briefing()
        d = briefing.to_dict()
        # Should be JSON-serializable
        json_str = json.dumps(d)
        assert isinstance(json_str, str)

    def test_briefing_to_summary_dict_is_compact(self):
        from aksara.ai.daily_briefing import generate_daily_briefing

        briefing = generate_daily_briefing()
        s = briefing.to_summary_dict()
        assert "issue_count" in s
        assert "recommendation_count" in s
        # Summary dict should not contain full lists
        assert "issues" not in s
        assert "recommendations" not in s


# =============================================================================
# 7. Collector Resilience Tests
# =============================================================================


class TestCollectorResilience:
    """Test that individual collectors handle failures gracefully."""

    def test_collect_project_graph_returns_dict(self):
        from aksara.ai.daily_briefing import _collect_project_graph

        result = _collect_project_graph()
        assert isinstance(result, dict)

    def test_collect_performance_returns_dict(self):
        from aksara.ai.daily_briefing import _collect_performance

        result = _collect_performance()
        assert isinstance(result, dict)

    def test_collect_architecture_returns_dict(self):
        from aksara.ai.daily_briefing import _collect_architecture

        result = _collect_architecture()
        assert isinstance(result, dict)

    def test_collect_debug_returns_dict(self):
        from aksara.ai.daily_briefing import _collect_debug

        result = _collect_debug()
        assert isinstance(result, dict)

    def test_collect_recent_investigations_returns_list(self):
        from aksara.ai.daily_briefing import _collect_recent_investigations

        result = _collect_recent_investigations()
        assert isinstance(result, list)


# =============================================================================
# 8. CLI Integration Tests
# =============================================================================


class TestCLIBriefing:
    """Test the CLI briefing command is registered."""

    def test_briefing_command_exists(self):
        from aksara.cli.main import ai

        cmd_names = [c.name for c in ai.commands.values()]
        assert "briefing" in cmd_names

    def test_continue_command_exists(self):
        from aksara.cli.main import ai

        cmd_names = [c.name for c in ai.commands.values()]
        assert "continue" in cmd_names
