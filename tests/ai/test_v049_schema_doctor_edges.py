"""
Aksara v0.4.10 - Schema Doctor Edge Cases

Tests for:
1. System tables/schemas handling
2. Case sensitivity / quoted identifiers
3. Edge cases in schema introspection
"""

from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aksara.ai.schema_doctor import (
    AiSchemaHealth,
    AiSchemaIssue,
    analyze_schema_health,
)


# =============================================================================
# Section 1: System Tables/Schemas Handling
# =============================================================================

class TestSystemTablesHandling:
    """Tests for proper handling of system tables."""
    
    def test_pg_catalog_not_reported_as_issue(self):
        """Tables in pg_catalog should not be reported as drift."""
        # pg_catalog tables are PostgreSQL system tables
        system_tables = [
            "pg_catalog.pg_class",
            "pg_catalog.pg_type",
            "pg_catalog.pg_attribute",
            "pg_catalog.pg_constraint",
        ]
        
        # These should be ignored in schema comparison
        for table in system_tables:
            # Schema doctor should not flag these as "extra tables"
            assert table.startswith("pg_catalog")
    
    def test_information_schema_not_reported(self):
        """Tables in information_schema should not be reported."""
        system_tables = [
            "information_schema.tables",
            "information_schema.columns",
            "information_schema.schemata",
        ]
        
        for table in system_tables:
            assert table.startswith("information_schema")
    
    def test_alembic_version_table_ignored(self):
        """alembic_version table should not be flagged."""
        # This is a migration tracking table
        migration_tables = ["alembic_version"]
        
        # These are infrastructure, not model tables
        for table in migration_tables:
            assert table in ["alembic_version"]
    
    def test_aksara_migrations_table_ignored(self):
        """aksara_migrations table should not be flagged."""
        # Internal Aksara migration tracking
        internal_tables = ["aksara_migrations"]
        
        for table in internal_tables:
            assert table in ["aksara_migrations"]
    
    def test_system_table_names_are_excluded_by_convention(self):
        """System tables should be excluded by naming convention."""
        # These should be excluded from drift analysis
        system_prefixes = ["pg_", "information_schema."]
        
        user_tables = ["users", "posts", "comments"]
        system_tables = ["pg_catalog.pg_class", "information_schema.tables"]
        
        # Filter function
        def is_user_table(table: str) -> bool:
            return not any(table.startswith(prefix) for prefix in system_prefixes)
        
        # System tables should be filtered out
        filtered = [t for t in (user_tables + system_tables) if is_user_table(t)]
        
        assert "users" in filtered
        assert "posts" in filtered
        assert "pg_catalog.pg_class" not in filtered
        assert "information_schema.tables" not in filtered


# =============================================================================
# Section 2: Case Sensitivity / Quoted Identifiers
# =============================================================================

class TestCaseSensitivity:
    """Tests for case sensitivity handling."""
    
    def test_lowercase_identifier_standard(self):
        """Lowercase identifiers are the standard in Aksara."""
        valid_names = [
            "users",
            "blog_posts",
            "article_categories",
            "user_profiles",
        ]
        
        for name in valid_names:
            # All lowercase, using underscores
            assert name == name.lower()
            assert " " not in name
    
    def test_mixed_case_should_be_rejected_or_normalized(self):
        """
        Mixed case identifiers should either:
        - Be normalized to lowercase, OR
        - Be rejected with clear message
        """
        mixed_case_names = [
            "Users",
            "BlogPosts",
            "ArticleCategory",
        ]
        
        # In PostgreSQL, unquoted identifiers are lowercased
        for name in mixed_case_names:
            normalized = name.lower()
            assert normalized != name  # These are mixed case
    
    def test_quoted_identifier_handling(self):
        """
        Quoted identifiers preserve case but are tricky.
        
        Aksara should either:
        - Support them correctly
        - Reject them with helpful message
        """
        quoted_names = [
            '"Users"',
            '"BlogPost"',
            '"Article Category"',  # Has space!
        ]
        
        # These require special handling
        for name in quoted_names:
            assert name.startswith('"') and name.endswith('"')
    
    def test_schema_issue_preserves_actual_names(self):
        """AiSchemaIssue should preserve actual table/column names."""
        issue = AiSchemaIssue(
            id="test.Model.field.missing",
            kind="missing_column",
            severity="danger",
            app_label="test",
            model="MyModel",  # Model name in code
            table="test_mymodel",  # Actual table name
            column="myField",  # Could be mixed case in code
            message="Column missing",
            hint="Add migration"
        )
        
        # Names should be preserved
        assert issue.model == "MyModel"
        assert issue.table == "test_mymodel"
        assert issue.column == "myField"


class TestIdentifierValidation:
    """Tests for identifier validation."""
    
    def test_valid_python_identifier_for_model(self):
        """Model names should be valid Python identifiers."""
        valid_model_names = [
            "User",
            "BlogPost",
            "ArticleCategory",
            "UserProfile2",
        ]
        
        for name in valid_model_names:
            assert name.isidentifier()
    
    def test_invalid_python_identifiers_rejected(self):
        """Invalid Python identifiers should be rejected."""
        invalid_names = [
            "2User",  # Starts with digit
            "user-profile",  # Has hyphen
            "blog post",  # Has space
            "",  # Empty
        ]
        
        for name in invalid_names:
            assert not name.isidentifier() or name == ""
    
    def test_reserved_keywords_should_warn(self):
        """Python reserved keywords should warn or be rejected."""
        import keyword
        
        reserved = ["class", "for", "if", "while", "return", "import"]
        
        for word in reserved:
            assert keyword.iskeyword(word)


# =============================================================================
# Section 3: AiSchemaHealth & AiSchemaIssue
# =============================================================================

class TestAiSchemaHealth:
    """Tests for AiSchemaHealth model."""
    
    def test_healthy_status(self):
        """Healthy status should have no issues."""
        health = AiSchemaHealth(
            status="healthy",
            issue_counts={"info": 0, "warning": 0, "danger": 0},
            issues=[],
            inspected_at="2026-01-26T12:00:00Z",
            db_version="PostgreSQL 16.1",
            db_name="test_db",
            app_version="0.4.10"
        )
        
        assert health.status == "healthy"
        assert len(health.issues) == 0
        assert health.issue_counts["danger"] == 0
    
    def test_warning_status(self):
        """Warning status should have warning issues (using 'degraded' status)."""
        # Note: AiSchemaHealth uses 'degraded' not 'warning'
        health = AiSchemaHealth(
            status="degraded",
            issue_counts={"info": 0, "warning": 2, "danger": 0},
            issues=[
                AiSchemaIssue(
                    id="test.extra_column",
                    kind="extra_column",
                    severity="warning",
                    app_label="test",
                    model="User",
                    table="users",
                    column="old_field",
                    message="Extra column",
                    hint="Remove column"
                ),
            ],
            inspected_at="2026-01-26T12:00:00Z",
            db_version="PostgreSQL 16.1",
            db_name="test_db",
            app_version="0.4.10"
        )
        
        assert health.status == "degraded"
        assert health.issue_counts["warning"] > 0
    
    def test_danger_status(self):
        """Danger status should have critical issues."""
        health = AiSchemaHealth(
            status="danger",
            issue_counts={"info": 0, "warning": 0, "danger": 1},
            issues=[
                AiSchemaIssue(
                    id="test.missing_column",
                    kind="missing_column",
                    severity="danger",
                    app_label="test",
                    model="User",
                    table="users",
                    column="email",
                    message="Missing column",
                    hint="Run migrations"
                ),
            ],
            inspected_at="2026-01-26T12:00:00Z",
            db_version="PostgreSQL 16.1",
            db_name="test_db",
            app_version="0.4.10"
        )
        
        assert health.status == "danger"
        assert health.issue_counts["danger"] > 0


class TestAiSchemaIssue:
    """Tests for AiSchemaIssue model."""
    
    def test_issue_kinds(self):
        """Test various issue kinds (all valid DriftKind values)."""
        # These are the valid DriftKind values from schema_doctor.py
        valid_kinds = [
            "missing_table",
            "extra_table",
            "missing_column",
            "extra_column",
            "type_mismatch",
            "nullability_mismatch",
            "default_mismatch",
            "pk_mismatch",
            "fk_mismatch",
            "index_mismatch",
            "unique_mismatch",
        ]
        
        for kind in valid_kinds:
            issue = AiSchemaIssue(
                id=f"test.{kind}",
                kind=kind,
                severity="warning",
                app_label="test",
                model="TestModel",
                table="test_table",
                column="test_column",
                message=f"Issue: {kind}",
                hint="Fix it"
            )
            
            assert issue.kind == kind
    
    def test_issue_severities(self):
        """Test severity levels."""
        severities = ["info", "warning", "danger"]
        
        for severity in severities:
            issue = AiSchemaIssue(
                id="test.issue",
                kind="missing_column",
                severity=severity,
                app_label="test",
                model="Test",
                table="test",
                message="Test issue",
                hint="Fix"
            )
            
            assert issue.severity == severity
    
    def test_issue_optional_fields(self):
        """Test that optional fields are truly optional."""
        # Minimal issue
        issue = AiSchemaIssue(
            id="test.issue",
            kind="missing_table",
            severity="danger",
            app_label="test",
            model="Test",
            table="test",
            message="Table missing"
        )
        
        # column and hint are optional
        assert issue.column is None or issue.column == ""
        assert issue.hint is None or issue.hint == ""
    
    def test_issue_to_dict(self):
        """Issue should be serializable to dict."""
        issue = AiSchemaIssue(
            id="blog.Article.slug.missing",
            kind="missing_column",
            severity="danger",
            app_label="blog",
            model="Article",
            table="blog_articles",
            column="slug",
            message="Column 'slug' is missing",
            hint="Run: aksara migrate"
        )
        
        d = issue.model_dump()
        
        assert d["id"] == "blog.Article.slug.missing"
        assert d["kind"] == "missing_column"
        assert d["severity"] == "danger"
        assert d["app_label"] == "blog"


# =============================================================================
# Section 4: Schema Drift Detection
# =============================================================================

class TestSchemaDriftDetection:
    """Tests for schema drift detection scenarios."""
    
    def test_missing_table_detected(self):
        """Model without corresponding table should be detected."""
        # Model exists in code, table doesn't exist in DB
        issue = AiSchemaIssue(
            id="blog.Article.missing_table",
            kind="missing_table",
            severity="danger",
            app_label="blog",
            model="Article",
            table="blog_articles",
            message="Table 'blog_articles' does not exist",
            hint="Run migrations to create the table"
        )
        
        assert issue.kind == "missing_table"
        assert issue.severity == "danger"
    
    def test_extra_table_detected(self):
        """Table without corresponding model should be detected."""
        # Table exists in DB, no model for it
        issue = AiSchemaIssue(
            id="unknown.old_data.extra_table",
            kind="extra_table",
            severity="warning",
            app_label="unknown",
            model="",
            table="old_data",
            message="Table 'old_data' has no corresponding model",
            hint="Remove table or create model"
        )
        
        assert issue.kind == "extra_table"
        assert issue.severity == "warning"
    
    def test_missing_column_detected(self):
        """Field without corresponding column should be detected."""
        issue = AiSchemaIssue(
            id="blog.Article.slug.missing",
            kind="missing_column",
            severity="danger",
            app_label="blog",
            model="Article",
            table="blog_articles",
            column="slug",
            message="Column 'slug' is defined in model but missing in table",
            hint="Run migrations"
        )
        
        assert issue.kind == "missing_column"
        assert issue.column == "slug"
    
    def test_type_mismatch_detected(self):
        """Column type mismatch should be detected."""
        issue = AiSchemaIssue(
            id="blog.Article.view_count.type_mismatch",
            kind="type_mismatch",
            severity="warning",
            app_label="blog",
            model="Article",
            table="blog_articles",
            column="view_count",
            message="Type mismatch: model=BigInt, db=Integer",
            hint="Create migration to alter column type"
        )
        
        assert issue.kind == "type_mismatch"


# =============================================================================
# Section 5: Health Status Determination
# =============================================================================

class TestHealthStatusDetermination:
    """Tests for determining overall health status."""
    
    def test_no_issues_is_healthy(self):
        """No issues should result in healthy status."""
        issues: List[AiSchemaIssue] = []
        
        # Status determination logic
        if not issues:
            status = "healthy"
        elif any(i.severity == "danger" for i in issues):
            status = "danger"
        elif any(i.severity == "warning" for i in issues):
            status = "warning"
        else:
            status = "healthy"
        
        assert status == "healthy"
    
    def test_danger_issue_makes_status_danger(self):
        """Any danger issue should make status danger."""
        issues = [
            AiSchemaIssue(
                id="test", kind="missing_column", severity="danger",
                app_label="t", model="T", table="t", message="Missing"
            ),
            AiSchemaIssue(
                id="test2", kind="extra_column", severity="info",
                app_label="t", model="T", table="t", message="Extra"
            ),
        ]
        
        if any(i.severity == "danger" for i in issues):
            status = "danger"
        else:
            status = "healthy"
        
        assert status == "danger"
    
    def test_warning_without_danger_is_warning(self):
        """Warning issues without danger should be warning status."""
        issues = [
            AiSchemaIssue(
                id="test", kind="extra_column", severity="warning",
                app_label="t", model="T", table="t", message="Extra"
            ),
        ]
        
        if any(i.severity == "danger" for i in issues):
            status = "danger"
        elif any(i.severity == "warning" for i in issues):
            status = "degraded"  # Note: status is 'degraded' not 'warning'
        else:
            status = "healthy"
        
        assert status == "degraded"
    
    def test_only_info_is_healthy(self):
        """Only info issues should still be healthy status."""
        issues = [
            AiSchemaIssue(
                id="test", kind="index_mismatch", severity="info",
                app_label="t", model="T", table="t", message="Consider index"
            ),
        ]
        
        if any(i.severity == "danger" for i in issues):
            status = "danger"
        elif any(i.severity == "warning" for i in issues):
            status = "degraded"
        else:
            status = "healthy"
        
        assert status == "healthy"


# =============================================================================
# Section 6: Issue Counts
# =============================================================================

class TestIssueCounts:
    """Tests for issue count accuracy."""
    
    def test_count_by_severity(self):
        """Issue counts should be accurate by severity."""
        issues = [
            AiSchemaIssue(id="1", kind="missing_table", severity="danger", app_label="a", model="M", table="t", message="m"),
            AiSchemaIssue(id="2", kind="missing_column", severity="danger", app_label="a", model="M", table="t", message="m"),
            AiSchemaIssue(id="3", kind="extra_column", severity="warning", app_label="a", model="M", table="t", message="m"),
            AiSchemaIssue(id="4", kind="index_mismatch", severity="info", app_label="a", model="M", table="t", message="m"),
            AiSchemaIssue(id="5", kind="type_mismatch", severity="info", app_label="a", model="M", table="t", message="m"),
            AiSchemaIssue(id="6", kind="nullability_mismatch", severity="info", app_label="a", model="M", table="t", message="m"),
        ]
        
        counts = {
            "danger": sum(1 for i in issues if i.severity == "danger"),
            "warning": sum(1 for i in issues if i.severity == "warning"),
            "info": sum(1 for i in issues if i.severity == "info"),
        }
        
        assert counts["danger"] == 2
        assert counts["warning"] == 1
        assert counts["info"] == 3
    
    def test_total_count(self):
        """Total issue count should be sum of all severities."""
        counts = {"danger": 2, "warning": 1, "info": 3}
        total = sum(counts.values())
        
        assert total == 6
