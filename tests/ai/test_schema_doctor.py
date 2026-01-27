"""
Tests for AI Schema Doctor & Migration Guardrails (v0.4.7)

Comprehensive test coverage for schema health detection:
- Drift detection (missing/extra tables, columns)
- Type mismatch detection
- Nullability checks
- Primary key validation
- Severity classification
- Health status computation
- DB introspection
- Model schema mapping
- Endpoint tests
"""

import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

# Import test utilities
from aksara.testing import AksaraTestCase


# =============================================================================
# Model & Type Tests
# =============================================================================


class TestDriftKindLiteral:
    """Test DriftKind type literal values."""
    
    def test_drift_kind_import(self):
        """DriftKind can be imported."""
        from aksara.ai.schema_doctor import DriftKind
        
        # Type checking only - no runtime validation for Literal
        assert DriftKind is not None
    
    def test_drift_kind_values(self):
        """All expected drift kinds should be defined."""
        from aksara.ai.schema_doctor import DriftKind
        from typing import get_args
        
        expected_kinds = {
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
        }
        
        actual_kinds = set(get_args(DriftKind))
        assert actual_kinds == expected_kinds


class TestIssueSeverityLiteral:
    """Test IssueSeverity type literal values."""
    
    def test_issue_severity_import(self):
        """IssueSeverity can be imported."""
        from aksara.ai.schema_doctor import IssueSeverity
        
        assert IssueSeverity is not None
    
    def test_issue_severity_values(self):
        """All expected severity levels should be defined."""
        from aksara.ai.schema_doctor import IssueSeverity
        from typing import get_args
        
        expected_severities = {"info", "warning", "danger"}
        actual_severities = set(get_args(IssueSeverity))
        assert actual_severities == expected_severities


# =============================================================================
# AiSchemaIssue Model Tests
# =============================================================================


class TestAiSchemaIssue:
    """Test AiSchemaIssue model."""
    
    def test_create_minimal_issue(self):
        """Create issue with only required fields."""
        from aksara.ai.schema_doctor import AiSchemaIssue
        
        issue = AiSchemaIssue(
            id="test.issue",
            kind="missing_table",
            severity="danger",
            message="Test issue message",
        )
        
        assert issue.id == "test.issue"
        assert issue.kind == "missing_table"
        assert issue.severity == "danger"
        assert issue.message == "Test issue message"
        assert issue.hint is None
        assert issue.tags == []
    
    def test_create_full_issue(self):
        """Create issue with all fields."""
        from aksara.ai.schema_doctor import AiSchemaIssue
        
        issue = AiSchemaIssue(
            id="blog.Article.slug.missing_column",
            kind="missing_column",
            severity="danger",
            app_label="blog",
            model="Article",
            table="blog_articles",
            column="slug",
            expected={"type": "varchar(255)", "nullable": True},
            actual=None,
            message="Column 'slug' is missing from table",
            hint="Run migrations to create the column",
            tags=["migration", "data_loss_risk"],
        )
        
        assert issue.app_label == "blog"
        assert issue.model == "Article"
        assert issue.table == "blog_articles"
        assert issue.column == "slug"
        assert issue.expected == {"type": "varchar(255)", "nullable": True}
        assert issue.actual is None
        assert "migration" in issue.tags
    
    def test_issue_serialization(self):
        """Issue can be serialized to dict."""
        from aksara.ai.schema_doctor import AiSchemaIssue
        
        issue = AiSchemaIssue(
            id="test.issue",
            kind="extra_table",
            severity="warning",
            table="legacy_users",
            message="Table exists without model",
        )
        
        data = issue.model_dump()
        
        assert data["id"] == "test.issue"
        assert data["kind"] == "extra_table"
        assert data["severity"] == "warning"
        assert data["table"] == "legacy_users"
        assert data["message"] == "Table exists without model"
    
    def test_issue_json_serialization(self):
        """Issue can be serialized to JSON."""
        from aksara.ai.schema_doctor import AiSchemaIssue
        import json
        
        issue = AiSchemaIssue(
            id="test.issue",
            kind="type_mismatch",
            severity="danger",
            message="Type mismatch detected",
        )
        
        json_str = issue.model_dump_json()
        data = json.loads(json_str)
        
        assert data["id"] == "test.issue"
        assert data["kind"] == "type_mismatch"
    
    def test_issue_forbids_extra_fields(self):
        """Issue should reject unknown fields."""
        from aksara.ai.schema_doctor import AiSchemaIssue
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            AiSchemaIssue(
                id="test",
                kind="missing_table",
                severity="danger",
                message="Test",
                unknown_field="value",
            )


# =============================================================================
# AiSchemaHealth Model Tests
# =============================================================================


class TestAiSchemaHealth:
    """Test AiSchemaHealth model."""
    
    def test_create_healthy_status(self):
        """Create health with healthy status."""
        from aksara.ai.schema_doctor import AiSchemaHealth
        
        health = AiSchemaHealth(
            status="healthy",
            issue_counts={"info": 0, "warning": 0, "danger": 0},
            issues=[],
            inspected_at="2026-01-25T12:00:00Z",
            app_version="0.4.7",
        )
        
        assert health.status == "healthy"
        assert health.issue_counts["danger"] == 0
        assert health.issue_counts["warning"] == 0
        assert len(health.issues) == 0
    
    def test_create_degraded_status(self):
        """Create health with degraded status."""
        from aksara.ai.schema_doctor import AiSchemaHealth, AiSchemaIssue
        
        health = AiSchemaHealth(
            status="degraded",
            issue_counts={"info": 0, "warning": 2, "danger": 0},
            issues=[
                AiSchemaIssue(
                    id="test.warning1",
                    kind="extra_table",
                    severity="warning",
                    message="Warning 1",
                ),
                AiSchemaIssue(
                    id="test.warning2",
                    kind="extra_column",
                    severity="warning",
                    message="Warning 2",
                ),
            ],
            inspected_at="2026-01-25T12:00:00Z",
            app_version="0.4.7",
        )
        
        assert health.status == "degraded"
        assert health.issue_counts["warning"] == 2
        assert len(health.issues) == 2
    
    def test_create_danger_status(self):
        """Create health with danger status."""
        from aksara.ai.schema_doctor import AiSchemaHealth, AiSchemaIssue
        
        health = AiSchemaHealth(
            status="danger",
            issue_counts={"info": 0, "warning": 1, "danger": 1},
            issues=[
                AiSchemaIssue(
                    id="test.danger",
                    kind="missing_table",
                    severity="danger",
                    message="Critical issue",
                ),
                AiSchemaIssue(
                    id="test.warning",
                    kind="extra_column",
                    severity="warning",
                    message="Warning",
                ),
            ],
            inspected_at="2026-01-25T12:00:00Z",
            app_version="0.4.7",
        )
        
        assert health.status == "danger"
        assert health.issue_counts["danger"] == 1
    
    def test_health_with_db_metadata(self):
        """Health can include database metadata."""
        from aksara.ai.schema_doctor import AiSchemaHealth
        
        health = AiSchemaHealth(
            status="healthy",
            issue_counts={"info": 0, "warning": 0, "danger": 0},
            issues=[],
            inspected_at="2026-01-25T12:00:00Z",
            db_version="PostgreSQL 16.1",
            db_name="myapp_prod",
            app_version="0.4.7",
        )
        
        assert health.db_version == "PostgreSQL 16.1"
        assert health.db_name == "myapp_prod"
    
    def test_health_serialization(self):
        """Health can be serialized to dict."""
        from aksara.ai.schema_doctor import AiSchemaHealth
        
        health = AiSchemaHealth(
            status="healthy",
            issue_counts={"info": 0, "warning": 0, "danger": 0},
            issues=[],
            inspected_at="2026-01-25T12:00:00Z",
            app_version="0.4.7",
        )
        
        data = health.model_dump()
        
        assert data["status"] == "healthy"
        assert data["issue_counts"] == {"info": 0, "warning": 0, "danger": 0}
        assert data["inspected_at"] == "2026-01-25T12:00:00Z"


# =============================================================================
# DbColumnInfo & DbTableInfo Tests
# =============================================================================


class TestDbColumnInfo:
    """Test DbColumnInfo model."""
    
    def test_create_column_info(self):
        """Create basic column info."""
        from aksara.ai.schema_doctor import DbColumnInfo
        
        col = DbColumnInfo(
            name="id",
            type="uuid",
            is_nullable=False,
            is_primary_key=True,
        )
        
        assert col.name == "id"
        assert col.type == "uuid"
        assert col.is_nullable is False
        assert col.is_primary_key is True
        assert col.default is None
    
    def test_create_column_with_default(self):
        """Create column info with default value."""
        from aksara.ai.schema_doctor import DbColumnInfo
        
        col = DbColumnInfo(
            name="created_at",
            type="timestamp with time zone",
            is_nullable=False,
            default="CURRENT_TIMESTAMP",
            is_primary_key=False,
        )
        
        assert col.default == "CURRENT_TIMESTAMP"
    
    def test_create_nullable_column(self):
        """Create nullable column info."""
        from aksara.ai.schema_doctor import DbColumnInfo
        
        col = DbColumnInfo(
            name="bio",
            type="text",
            is_nullable=True,
            is_primary_key=False,
        )
        
        assert col.is_nullable is True


class TestDbTableInfo:
    """Test DbTableInfo model."""
    
    def test_create_table_info(self):
        """Create basic table info."""
        from aksara.ai.schema_doctor import DbTableInfo
        
        table = DbTableInfo(name="users")
        
        assert table.name == "users"
        assert table.columns == {}
    
    def test_create_table_with_columns(self):
        """Create table info with columns."""
        from aksara.ai.schema_doctor import DbTableInfo, DbColumnInfo
        
        table = DbTableInfo(
            name="users",
            columns={
                "id": DbColumnInfo(
                    name="id",
                    type="uuid",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                "email": DbColumnInfo(
                    name="email",
                    type="varchar(255)",
                    is_nullable=False,
                    is_primary_key=False,
                ),
            },
        )
        
        assert len(table.columns) == 2
        assert "id" in table.columns
        assert "email" in table.columns
        assert table.columns["id"].is_primary_key is True


# =============================================================================
# Severity Classification Tests
# =============================================================================


class TestClassifySeverity:
    """Test severity classification logic."""
    
    def test_missing_table_is_danger(self):
        """Missing table should be danger severity."""
        from aksara.ai.schema_doctor import classify_severity
        
        severity = classify_severity("missing_table")
        assert severity == "danger"
    
    def test_missing_column_is_danger(self):
        """Missing column should be danger severity."""
        from aksara.ai.schema_doctor import classify_severity
        
        severity = classify_severity("missing_column")
        assert severity == "danger"
    
    def test_extra_table_is_warning(self):
        """Extra table should be warning severity."""
        from aksara.ai.schema_doctor import classify_severity
        
        severity = classify_severity("extra_table")
        assert severity == "warning"
    
    def test_extra_column_is_warning(self):
        """Extra column should be warning severity."""
        from aksara.ai.schema_doctor import classify_severity
        
        severity = classify_severity("extra_column")
        assert severity == "warning"
    
    def test_type_mismatch_is_danger(self):
        """Type mismatch should be danger severity."""
        from aksara.ai.schema_doctor import classify_severity
        
        severity = classify_severity("type_mismatch")
        assert severity == "danger"
    
    def test_nullability_mismatch_is_warning(self):
        """Nullability mismatch should be warning by default."""
        from aksara.ai.schema_doctor import classify_severity
        
        severity = classify_severity("nullability_mismatch")
        assert severity == "warning"
    
    def test_pk_mismatch_is_danger(self):
        """Primary key mismatch should be danger severity."""
        from aksara.ai.schema_doctor import classify_severity
        
        severity = classify_severity("pk_mismatch")
        assert severity == "danger"
    
    def test_index_mismatch_is_info(self):
        """Index mismatch should be info severity."""
        from aksara.ai.schema_doctor import classify_severity
        
        severity = classify_severity("index_mismatch")
        assert severity == "info"
    
    def test_fk_mismatch_is_warning(self):
        """Foreign key mismatch should be warning severity."""
        from aksara.ai.schema_doctor import classify_severity
        
        severity = classify_severity("fk_mismatch")
        assert severity == "warning"
    
    def test_unique_mismatch_is_warning(self):
        """Unique constraint mismatch should be warning severity."""
        from aksara.ai.schema_doctor import classify_severity
        
        severity = classify_severity("unique_mismatch")
        assert severity == "warning"
    
    def test_default_mismatch_is_warning(self):
        """Default value mismatch should be warning severity."""
        from aksara.ai.schema_doctor import classify_severity
        
        severity = classify_severity("default_mismatch")
        assert severity == "warning"


# =============================================================================
# Type Compatibility Tests
# =============================================================================


class TestTypesCompatible:
    """Test type compatibility checking."""
    
    def test_exact_match(self):
        """Exact type matches should be compatible."""
        from aksara.ai.schema_doctor import _types_compatible
        
        assert _types_compatible("integer", "integer") is True
        assert _types_compatible("uuid", "uuid") is True
        assert _types_compatible("text", "text") is True
    
    def test_varchar_variations(self):
        """Varchar variations should be compatible."""
        from aksara.ai.schema_doctor import _types_compatible
        
        assert _types_compatible("varchar(255)", "varchar(255)") is True
        assert _types_compatible("varchar", "varchar(100)") is True
        assert _types_compatible("varchar(50)", "character varying") is True
    
    def test_integer_variations(self):
        """Integer variations should be compatible."""
        from aksara.ai.schema_doctor import _types_compatible
        
        assert _types_compatible("integer", "int4") is True
        assert _types_compatible("int", "integer") is True
        assert _types_compatible("serial", "integer") is True
    
    def test_bigint_variations(self):
        """Bigint variations should be compatible."""
        from aksara.ai.schema_doctor import _types_compatible
        
        assert _types_compatible("bigint", "int8") is True
        assert _types_compatible("bigserial", "bigint") is True
    
    def test_boolean_variations(self):
        """Boolean variations should be compatible."""
        from aksara.ai.schema_doctor import _types_compatible
        
        assert _types_compatible("boolean", "bool") is True
        assert _types_compatible("bool", "boolean") is True
    
    def test_timestamp_variations(self):
        """Timestamp variations should be compatible."""
        from aksara.ai.schema_doctor import _types_compatible
        
        assert _types_compatible(
            "timestamp with time zone",
            "timestamp without time zone"
        ) is True
    
    def test_json_variations(self):
        """JSON variations should be compatible."""
        from aksara.ai.schema_doctor import _types_compatible
        
        assert _types_compatible("json", "jsonb") is True
        assert _types_compatible("jsonb", "json") is True
    
    def test_float_variations(self):
        """Float/double variations should be compatible."""
        from aksara.ai.schema_doctor import _types_compatible
        
        assert _types_compatible("float", "double precision") is True
        assert _types_compatible("real", "float4") is True
    
    def test_incompatible_types(self):
        """Incompatible types should return False."""
        from aksara.ai.schema_doctor import _types_compatible
        
        assert _types_compatible("integer", "text") is False
        assert _types_compatible("varchar", "uuid") is False
        assert _types_compatible("boolean", "integer") is False


# =============================================================================
# Drift Detection Tests
# =============================================================================


class TestDetectSchemaDrift:
    """Test schema drift detection."""
    
    def test_no_drift_empty_schemas(self):
        """Empty schemas should have no drift."""
        from aksara.ai.schema_doctor import detect_schema_drift
        
        issues = detect_schema_drift({}, {})
        assert issues == []
    
    def test_detect_missing_table(self):
        """Detect table in models but not in DB."""
        from aksara.ai.schema_doctor import detect_schema_drift
        
        models_map = {
            "users": {
                "model_name": "User",
                "app_label": "auth",
                "table_name": "users",
                "columns": {},
                "pk_name": "id",
            }
        }
        db_map = {}
        
        issues = detect_schema_drift(models_map, db_map)
        
        assert len(issues) == 1
        assert issues[0].kind == "missing_table"
        assert issues[0].severity == "danger"
        assert issues[0].table == "users"
        assert issues[0].model == "User"
    
    def test_detect_extra_table(self):
        """Detect table in DB but not in models."""
        from aksara.ai.schema_doctor import detect_schema_drift, DbTableInfo, DbColumnInfo
        
        models_map = {}
        db_map = {
            "legacy_data": DbTableInfo(
                name="legacy_data",
                columns={
                    "id": DbColumnInfo(
                        name="id",
                        type="integer",
                        is_nullable=False,
                        is_primary_key=True,
                    ),
                },
            ),
        }
        
        issues = detect_schema_drift(models_map, db_map)
        
        assert len(issues) == 1
        assert issues[0].kind == "extra_table"
        assert issues[0].severity == "warning"
        assert issues[0].table == "legacy_data"
    
    def test_detect_missing_column(self):
        """Detect column in model but not in DB table."""
        from aksara.ai.schema_doctor import detect_schema_drift, DbTableInfo, DbColumnInfo
        
        models_map = {
            "users": {
                "model_name": "User",
                "app_label": "auth",
                "table_name": "users",
                "columns": {
                    "id": {"name": "id", "type": "uuid", "is_nullable": False, "is_primary_key": True},
                    "email": {"name": "email", "type": "varchar(255)", "is_nullable": False, "is_primary_key": False},
                },
                "pk_name": "id",
            }
        }
        db_map = {
            "users": DbTableInfo(
                name="users",
                columns={
                    "id": DbColumnInfo(
                        name="id",
                        type="uuid",
                        is_nullable=False,
                        is_primary_key=True,
                    ),
                },
            ),
        }
        
        issues = detect_schema_drift(models_map, db_map)
        
        missing_col_issues = [i for i in issues if i.kind == "missing_column"]
        assert len(missing_col_issues) == 1
        assert missing_col_issues[0].column == "email"
        assert missing_col_issues[0].severity == "danger"
    
    def test_detect_extra_column(self):
        """Detect column in DB but not in model."""
        from aksara.ai.schema_doctor import detect_schema_drift, DbTableInfo, DbColumnInfo
        
        models_map = {
            "users": {
                "model_name": "User",
                "app_label": "auth",
                "table_name": "users",
                "columns": {
                    "id": {"name": "id", "type": "uuid", "is_nullable": False, "is_primary_key": True},
                },
                "pk_name": "id",
            }
        }
        db_map = {
            "users": DbTableInfo(
                name="users",
                columns={
                    "id": DbColumnInfo(name="id", type="uuid", is_nullable=False, is_primary_key=True),
                    "deprecated_field": DbColumnInfo(name="deprecated_field", type="text", is_nullable=True, is_primary_key=False),
                },
            ),
        }
        
        issues = detect_schema_drift(models_map, db_map)
        
        extra_col_issues = [i for i in issues if i.kind == "extra_column"]
        assert len(extra_col_issues) == 1
        assert extra_col_issues[0].column == "deprecated_field"
        assert extra_col_issues[0].severity == "warning"
    
    def test_detect_type_mismatch(self):
        """Detect type mismatch between model and DB."""
        from aksara.ai.schema_doctor import detect_schema_drift, DbTableInfo, DbColumnInfo
        
        models_map = {
            "users": {
                "model_name": "User",
                "app_label": "auth",
                "table_name": "users",
                "columns": {
                    "id": {"name": "id", "type": "uuid", "is_nullable": False, "is_primary_key": True},
                    "age": {"name": "age", "type": "integer", "is_nullable": True, "is_primary_key": False},
                },
                "pk_name": "id",
            }
        }
        db_map = {
            "users": DbTableInfo(
                name="users",
                columns={
                    "id": DbColumnInfo(name="id", type="uuid", is_nullable=False, is_primary_key=True),
                    "age": DbColumnInfo(name="age", type="text", is_nullable=True, is_primary_key=False),
                },
            ),
        }
        
        issues = detect_schema_drift(models_map, db_map)
        
        type_issues = [i for i in issues if i.kind == "type_mismatch"]
        assert len(type_issues) == 1
        assert type_issues[0].column == "age"
        assert type_issues[0].severity == "danger"
        assert type_issues[0].expected["type"] == "integer"
        assert type_issues[0].actual["type"] == "text"
    
    def test_detect_nullability_mismatch(self):
        """Detect nullability mismatch."""
        from aksara.ai.schema_doctor import detect_schema_drift, DbTableInfo, DbColumnInfo
        
        models_map = {
            "users": {
                "model_name": "User",
                "app_label": "auth",
                "table_name": "users",
                "columns": {
                    "id": {"name": "id", "type": "uuid", "is_nullable": False, "is_primary_key": True},
                    "email": {"name": "email", "type": "varchar", "is_nullable": False, "is_primary_key": False},
                },
                "pk_name": "id",
            }
        }
        db_map = {
            "users": DbTableInfo(
                name="users",
                columns={
                    "id": DbColumnInfo(name="id", type="uuid", is_nullable=False, is_primary_key=True),
                    "email": DbColumnInfo(name="email", type="varchar", is_nullable=True, is_primary_key=False),
                },
            ),
        }
        
        issues = detect_schema_drift(models_map, db_map)
        
        null_issues = [i for i in issues if i.kind == "nullability_mismatch"]
        assert len(null_issues) == 1
        assert null_issues[0].column == "email"
        assert null_issues[0].expected["nullable"] is False
        assert null_issues[0].actual["nullable"] is True
    
    def test_detect_pk_mismatch(self):
        """Detect primary key mismatch."""
        from aksara.ai.schema_doctor import detect_schema_drift, DbTableInfo, DbColumnInfo
        
        models_map = {
            "users": {
                "model_name": "User",
                "app_label": "auth",
                "table_name": "users",
                "columns": {
                    "id": {"name": "id", "type": "uuid", "is_nullable": False, "is_primary_key": True},
                },
                "pk_name": "id",
            }
        }
        db_map = {
            "users": DbTableInfo(
                name="users",
                columns={
                    "id": DbColumnInfo(name="id", type="uuid", is_nullable=False, is_primary_key=False),
                },
            ),
        }
        
        issues = detect_schema_drift(models_map, db_map)
        
        pk_issues = [i for i in issues if i.kind == "pk_mismatch"]
        assert len(pk_issues) == 1
        assert pk_issues[0].column == "id"
        assert pk_issues[0].severity == "danger"
    
    def test_skip_system_tables(self):
        """System tables should be skipped."""
        from aksara.ai.schema_doctor import detect_schema_drift, DbTableInfo, DbColumnInfo
        
        models_map = {}
        db_map = {
            "alembic_version": DbTableInfo(
                name="alembic_version",
                columns={
                    "version_num": DbColumnInfo(name="version_num", type="varchar", is_nullable=False, is_primary_key=True),
                },
            ),
            "aksara_migrations": DbTableInfo(
                name="aksara_migrations",
                columns={},
            ),
        }
        
        issues = detect_schema_drift(models_map, db_map)
        
        # System tables should not be flagged as extra
        assert len(issues) == 0
    
    def test_multiple_issues_in_single_table(self):
        """Multiple issues can be detected in a single table."""
        from aksara.ai.schema_doctor import detect_schema_drift, DbTableInfo, DbColumnInfo
        
        models_map = {
            "users": {
                "model_name": "User",
                "app_label": "auth",
                "table_name": "users",
                "columns": {
                    "id": {"name": "id", "type": "uuid", "is_nullable": False, "is_primary_key": True},
                    "email": {"name": "email", "type": "varchar", "is_nullable": False, "is_primary_key": False},
                    "name": {"name": "name", "type": "varchar", "is_nullable": True, "is_primary_key": False},
                },
                "pk_name": "id",
            }
        }
        db_map = {
            "users": DbTableInfo(
                name="users",
                columns={
                    "id": DbColumnInfo(name="id", type="uuid", is_nullable=False, is_primary_key=True),
                    "old_email": DbColumnInfo(name="old_email", type="text", is_nullable=True, is_primary_key=False),
                },
            ),
        }
        
        issues = detect_schema_drift(models_map, db_map)
        
        # Should detect: missing email, missing name, extra old_email
        assert len(issues) >= 3
        
        issue_kinds = [i.kind for i in issues]
        assert "missing_column" in issue_kinds
        assert "extra_column" in issue_kinds


# =============================================================================
# Issue ID Generation Tests
# =============================================================================


class TestIssueIdGeneration:
    """Test deterministic issue ID generation."""
    
    def test_issue_id_includes_app_label(self):
        """Issue ID should include app_label when present."""
        from aksara.ai.schema_doctor import _create_issue
        
        issue = _create_issue(
            kind="missing_column",
            app_label="blog",
            model="Article",
            table="blog_articles",
            column="slug",
            message="Column missing",
            hint="Add column",
        )
        
        assert "blog" in issue.id
    
    def test_issue_id_includes_model(self):
        """Issue ID should include model when present."""
        from aksara.ai.schema_doctor import _create_issue
        
        issue = _create_issue(
            kind="missing_column",
            app_label="auth",
            model="User",
            table="auth_users",
            column="email",
            message="Column missing",
            hint="Add column",
        )
        
        assert "User" in issue.id
    
    def test_issue_id_includes_column(self):
        """Issue ID should include column when present."""
        from aksara.ai.schema_doctor import _create_issue
        
        issue = _create_issue(
            kind="type_mismatch",
            table="users",
            column="age",
            message="Type mismatch",
            hint="Fix type",
        )
        
        assert "age" in issue.id
    
    def test_issue_id_includes_kind(self):
        """Issue ID should include kind."""
        from aksara.ai.schema_doctor import _create_issue
        
        issue = _create_issue(
            kind="extra_table",
            table="legacy_data",
            message="Extra table",
            hint="Remove table",
        )
        
        assert "extra_table" in issue.id
    
    def test_issue_id_is_deterministic(self):
        """Same inputs should produce same issue ID."""
        from aksara.ai.schema_doctor import _create_issue
        
        issue1 = _create_issue(
            kind="missing_column",
            app_label="blog",
            model="Article",
            column="slug",
            message="Missing",
            hint="Add",
        )
        
        issue2 = _create_issue(
            kind="missing_column",
            app_label="blog",
            model="Article",
            column="slug",
            message="Missing",
            hint="Add",
        )
        
        assert issue1.id == issue2.id


# =============================================================================
# Model Schema Map Tests
# =============================================================================


class TestBuildModelSchemaMap:
    """Test model schema map building."""
    
    def test_build_model_schema_map_returns_dict(self):
        """build_model_schema_map should return a dict."""
        from aksara.ai.schema_doctor import build_model_schema_map
        
        result = build_model_schema_map()
        
        assert isinstance(result, dict)
    
    def test_model_schema_map_structure(self):
        """Schema map should have expected structure."""
        from aksara.ai.schema_doctor import build_model_schema_map
        
        result = build_model_schema_map()
        
        for table_name, info in result.items():
            assert "model_name" in info
            assert "app_label" in info
            assert "table_name" in info
            assert "columns" in info
            assert isinstance(info["columns"], dict)


# =============================================================================
# Field Type Mapping Tests
# =============================================================================


class TestFieldTypeMapping:
    """Test field to PostgreSQL type mapping."""
    
    def test_map_uuid_field(self):
        """UUID field should map to uuid type."""
        from aksara.ai.schema_doctor import _map_field_to_pg_type
        
        class MockUUIDField:
            pass
        MockUUIDField.__name__ = "UUID"
        
        field = MockUUIDField()
        
        result = _map_field_to_pg_type(field)
        assert result == "uuid"
    
    def test_map_string_field(self):
        """String field should map to varchar type."""
        from aksara.ai.schema_doctor import _map_field_to_pg_type
        
        class MockStringField:
            max_length = 100
        MockStringField.__name__ = "String"
        
        field = MockStringField()
        
        result = _map_field_to_pg_type(field)
        assert result == "varchar(100)"
    
    def test_map_string_field_no_length(self):
        """String field without max_length should map to varchar."""
        from aksara.ai.schema_doctor import _map_field_to_pg_type
        
        class MockStringField:
            pass
        MockStringField.__name__ = "String"
        
        field = MockStringField()
        
        result = _map_field_to_pg_type(field)
        assert result == "varchar"
    
    def test_map_text_field(self):
        """Text field should map to text type."""
        from aksara.ai.schema_doctor import _map_field_to_pg_type
        
        class MockTextField:
            pass
        MockTextField.__name__ = "Text"
        
        field = MockTextField()
        
        result = _map_field_to_pg_type(field)
        assert result == "text"
    
    def test_map_integer_field(self):
        """Integer field should map to integer type."""
        from aksara.ai.schema_doctor import _map_field_to_pg_type
        
        class MockIntField:
            pass
        MockIntField.__name__ = "Integer"
        
        field = MockIntField()
        
        result = _map_field_to_pg_type(field)
        assert result == "integer"
    
    def test_map_boolean_field(self):
        """Boolean field should map to boolean type."""
        from aksara.ai.schema_doctor import _map_field_to_pg_type
        
        class MockBoolField:
            pass
        MockBoolField.__name__ = "Boolean"
        
        field = MockBoolField()
        
        result = _map_field_to_pg_type(field)
        assert result == "boolean"
    
    def test_map_json_field(self):
        """JSON field should map to jsonb type."""
        from aksara.ai.schema_doctor import _map_field_to_pg_type
        
        class MockJSONField:
            pass
        MockJSONField.__name__ = "JSON"
        
        field = MockJSONField()
        
        result = _map_field_to_pg_type(field)
        assert result == "jsonb"
    
    def test_map_datetime_field(self):
        """DateTime field should map to timestamp with time zone."""
        from aksara.ai.schema_doctor import _map_field_to_pg_type
        
        class MockDateTimeField:
            pass
        MockDateTimeField.__name__ = "DateTime"
        
        field = MockDateTimeField()
        
        result = _map_field_to_pg_type(field)
        assert result == "timestamp with time zone"
    
    def test_map_unknown_field(self):
        """Unknown field should map to 'unknown'."""
        from aksara.ai.schema_doctor import _map_field_to_pg_type
        
        class MockCustomField:
            pass
        MockCustomField.__name__ = "CustomWeirdField"
        
        field = MockCustomField()
        
        result = _map_field_to_pg_type(field)
        assert result == "unknown"


# =============================================================================
# Field Default Mapping Tests
# =============================================================================


class TestFieldDefaultMapping:
    """Test field default value extraction."""
    
    def test_get_none_default(self):
        """Field with no default should return None."""
        from aksara.ai.schema_doctor import _get_field_default
        
        class MockField:
            pass
        
        field = MockField()
        
        result = _get_field_default(field)
        assert result is None
    
    def test_get_bool_default_true(self):
        """Boolean True default should be 'true'."""
        from aksara.ai.schema_doctor import _get_field_default
        
        class MockField:
            default = True
        
        field = MockField()
        
        result = _get_field_default(field)
        assert result == "true"
    
    def test_get_bool_default_false(self):
        """Boolean False default should be 'false'."""
        from aksara.ai.schema_doctor import _get_field_default
        
        class MockField:
            default = False
        
        field = MockField()
        
        result = _get_field_default(field)
        assert result == "false"
    
    def test_get_int_default(self):
        """Integer default should be string representation."""
        from aksara.ai.schema_doctor import _get_field_default
        
        class MockField:
            default = 42
        
        field = MockField()
        
        result = _get_field_default(field)
        assert result == "42"
    
    def test_get_string_default(self):
        """String default should be quoted."""
        from aksara.ai.schema_doctor import _get_field_default
        
        class MockField:
            default = "hello"
        
        field = MockField()
        
        result = _get_field_default(field)
        assert result == "'hello'"
    
    def test_get_uuid4_callable_default(self):
        """UUID4 callable should map to gen_random_uuid()."""
        from aksara.ai.schema_doctor import _get_field_default
        from uuid import uuid4
        
        class MockField:
            default = uuid4
        
        field = MockField()
        
        result = _get_field_default(field)
        assert result == "gen_random_uuid()"


# =============================================================================
# Junction Table Detection Tests
# =============================================================================


class TestJunctionTableDetection:
    """Test M2M junction table detection."""
    
    def test_detect_junction_table(self):
        """Table with 2 FK-like columns should be detected as junction."""
        from aksara.ai.schema_doctor import _is_likely_junction_table, DbTableInfo, DbColumnInfo
        
        table = DbTableInfo(
            name="article_tags",
            columns={
                "article_id": DbColumnInfo(name="article_id", type="uuid", is_nullable=False, is_primary_key=False),
                "tag_id": DbColumnInfo(name="tag_id", type="uuid", is_nullable=False, is_primary_key=False),
            },
        )
        
        assert _is_likely_junction_table(table) is True
    
    def test_detect_junction_table_with_id(self):
        """Junction table with explicit id column."""
        from aksara.ai.schema_doctor import _is_likely_junction_table, DbTableInfo, DbColumnInfo
        
        table = DbTableInfo(
            name="user_roles",
            columns={
                "id": DbColumnInfo(name="id", type="uuid", is_nullable=False, is_primary_key=True),
                "user_id": DbColumnInfo(name="user_id", type="uuid", is_nullable=False, is_primary_key=False),
                "role_id": DbColumnInfo(name="role_id", type="uuid", is_nullable=False, is_primary_key=False),
            },
        )
        
        assert _is_likely_junction_table(table) is True
    
    def test_not_junction_table(self):
        """Regular table should not be detected as junction."""
        from aksara.ai.schema_doctor import _is_likely_junction_table, DbTableInfo, DbColumnInfo
        
        table = DbTableInfo(
            name="users",
            columns={
                "id": DbColumnInfo(name="id", type="uuid", is_nullable=False, is_primary_key=True),
                "email": DbColumnInfo(name="email", type="varchar", is_nullable=False, is_primary_key=False),
                "name": DbColumnInfo(name="name", type="varchar", is_nullable=True, is_primary_key=False),
                "created_at": DbColumnInfo(name="created_at", type="timestamp", is_nullable=False, is_primary_key=False),
            },
        )
        
        assert _is_likely_junction_table(table) is False
    
    def test_single_column_not_junction(self):
        """Table with single column should not be junction."""
        from aksara.ai.schema_doctor import _is_likely_junction_table, DbTableInfo, DbColumnInfo
        
        table = DbTableInfo(
            name="settings",
            columns={
                "value_id": DbColumnInfo(name="value_id", type="uuid", is_nullable=False, is_primary_key=True),
            },
        )
        
        assert _is_likely_junction_table(table) is False


# =============================================================================
# AiSchemaIssuesResponse Tests
# =============================================================================


class TestAiSchemaIssuesResponse:
    """Test AiSchemaIssuesResponse model."""
    
    def test_create_response(self):
        """Create issues response."""
        from aksara.ai.schema_doctor import AiSchemaIssuesResponse, AiSchemaIssue
        
        response = AiSchemaIssuesResponse(
            status="degraded",
            issues=[
                AiSchemaIssue(
                    id="test.issue",
                    kind="extra_table",
                    severity="warning",
                    message="Test",
                ),
            ],
        )
        
        assert response.status == "degraded"
        assert len(response.issues) == 1
    
    def test_empty_response(self):
        """Create empty issues response."""
        from aksara.ai.schema_doctor import AiSchemaIssuesResponse
        
        response = AiSchemaIssuesResponse(
            status="healthy",
            issues=[],
        )
        
        assert response.status == "healthy"
        assert len(response.issues) == 0


# =============================================================================
# analyze_schema_health Integration Tests (with mocking)
# =============================================================================


class TestAnalyzeSchemaHealthWithMocking:
    """Test analyze_schema_health with mocked database."""
    
    @pytest.mark.asyncio
    async def test_analyze_returns_health_object(self):
        """analyze_schema_health should return AiSchemaHealth."""
        from aksara.ai.schema_doctor import analyze_schema_health, AiSchemaHealth
        
        mock_app = MagicMock()
        
        with patch("aksara.db.engine.Database") as MockDb:
            mock_instance = AsyncMock()
            MockDb.get_instance.return_value = mock_instance
            mock_instance.fetch.return_value = []
            mock_instance.fetchval.side_effect = ["PostgreSQL 16.1", "test_db"]
            
            with patch("aksara.ai.schema_doctor.build_model_schema_map") as mock_build:
                mock_build.return_value = {}
                
                result = await analyze_schema_health(mock_app)
                
                assert isinstance(result, AiSchemaHealth)
    
    @pytest.mark.asyncio
    async def test_analyze_healthy_when_no_issues(self):
        """Status should be healthy when no issues."""
        from aksara.ai.schema_doctor import analyze_schema_health
        
        mock_app = MagicMock()
        
        with patch("aksara.db.engine.Database") as MockDb:
            mock_instance = AsyncMock()
            MockDb.get_instance.return_value = mock_instance
            mock_instance.fetch.return_value = []
            mock_instance.fetchval.side_effect = ["PostgreSQL 16.1", "test_db"]
            
            with patch("aksara.ai.schema_doctor.build_model_schema_map") as mock_build:
                mock_build.return_value = {}
                
                result = await analyze_schema_health(mock_app)
                
                assert result.status == "healthy"
                assert result.issue_counts["danger"] == 0
                assert result.issue_counts["warning"] == 0
    
    @pytest.mark.asyncio
    async def test_analyze_danger_when_db_not_configured(self):
        """Status should be danger when DB not configured."""
        from aksara.ai.schema_doctor import analyze_schema_health
        
        mock_app = MagicMock()
        
        with patch("aksara.db.engine.Database") as MockDb:
            MockDb.get_instance.side_effect = RuntimeError("No database")
            
            result = await analyze_schema_health(mock_app)
            
            assert result.status == "danger"
            assert result.issue_counts["danger"] == 1
            assert len(result.issues) == 1
            assert "database" in result.issues[0].message.lower()
    
    @pytest.mark.asyncio
    async def test_analyze_includes_db_metadata(self):
        """Result should include db_version and db_name."""
        from aksara.ai.schema_doctor import analyze_schema_health
        
        mock_app = MagicMock()
        
        with patch("aksara.db.engine.Database") as MockDb:
            mock_instance = AsyncMock()
            MockDb.get_instance.return_value = mock_instance
            mock_instance.fetch.return_value = []
            mock_instance.fetchval.side_effect = ["PostgreSQL 16.1", "my_database"]
            
            with patch("aksara.ai.schema_doctor.build_model_schema_map") as mock_build:
                mock_build.return_value = {}
                
                result = await analyze_schema_health(mock_app)
                
                assert result.db_version == "PostgreSQL 16.1"
                assert result.db_name == "my_database"
    
    @pytest.mark.asyncio
    async def test_analyze_includes_timestamp(self):
        """Result should include inspected_at timestamp."""
        from aksara.ai.schema_doctor import analyze_schema_health
        
        mock_app = MagicMock()
        
        with patch("aksara.db.engine.Database") as MockDb:
            mock_instance = AsyncMock()
            MockDb.get_instance.return_value = mock_instance
            mock_instance.fetch.return_value = []
            mock_instance.fetchval.side_effect = ["PostgreSQL 16.1", "test_db"]
            
            with patch("aksara.ai.schema_doctor.build_model_schema_map") as mock_build:
                mock_build.return_value = {}
                
                result = await analyze_schema_health(mock_app)
                
                assert result.inspected_at is not None
                # Should be ISO format
                datetime.fromisoformat(result.inspected_at.replace("Z", "+00:00"))


# =============================================================================
# DB Introspection Tests (with mocking)
# =============================================================================


class TestIntrospectDbSchema:
    """Test database schema introspection."""
    
    @pytest.mark.asyncio
    async def test_introspect_empty_database(self):
        """Empty database should return empty dict."""
        from aksara.ai.schema_doctor import introspect_db_schema
        
        mock_db = AsyncMock()
        mock_db.fetch.return_value = []
        
        result = await introspect_db_schema(mock_db)
        
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_introspect_single_table(self):
        """Introspect a single table with columns."""
        from aksara.ai.schema_doctor import introspect_db_schema
        
        mock_db = AsyncMock()
        
        # Columns query result
        columns_result = [
            {
                "table_name": "users",
                "column_name": "id",
                "data_type": "uuid",
                "udt_name": "uuid",
                "is_nullable": "NO",
                "column_default": "gen_random_uuid()",
                "character_maximum_length": None,
            },
            {
                "table_name": "users",
                "column_name": "email",
                "data_type": "character varying",
                "udt_name": "varchar",
                "is_nullable": "NO",
                "column_default": None,
                "character_maximum_length": 255,
            },
        ]
        
        # PK query result
        pk_result = [
            {"table_name": "users", "column_name": "id"},
        ]
        
        mock_db.fetch.side_effect = [columns_result, pk_result]
        
        result = await introspect_db_schema(mock_db)
        
        assert "users" in result
        assert "id" in result["users"].columns
        assert "email" in result["users"].columns
        assert result["users"].columns["id"].is_primary_key is True
        assert result["users"].columns["email"].is_primary_key is False
    
    @pytest.mark.asyncio
    async def test_introspect_varchar_type_normalization(self):
        """Varchar types should be normalized."""
        from aksara.ai.schema_doctor import introspect_db_schema
        
        mock_db = AsyncMock()
        
        columns_result = [
            {
                "table_name": "test",
                "column_name": "name",
                "data_type": "character varying",
                "udt_name": "varchar",
                "is_nullable": "YES",
                "column_default": None,
                "character_maximum_length": 100,
            },
        ]
        
        mock_db.fetch.side_effect = [columns_result, []]
        
        result = await introspect_db_schema(mock_db)
        
        assert result["test"].columns["name"].type == "varchar(100)"
    
    @pytest.mark.asyncio
    async def test_introspect_nullable_detection(self):
        """Nullability should be correctly detected."""
        from aksara.ai.schema_doctor import introspect_db_schema
        
        mock_db = AsyncMock()
        
        columns_result = [
            {
                "table_name": "test",
                "column_name": "required",
                "data_type": "text",
                "udt_name": "text",
                "is_nullable": "NO",
                "column_default": None,
                "character_maximum_length": None,
            },
            {
                "table_name": "test",
                "column_name": "optional",
                "data_type": "text",
                "udt_name": "text",
                "is_nullable": "YES",
                "column_default": None,
                "character_maximum_length": None,
            },
        ]
        
        mock_db.fetch.side_effect = [columns_result, []]
        
        result = await introspect_db_schema(mock_db)
        
        assert result["test"].columns["required"].is_nullable is False
        assert result["test"].columns["optional"].is_nullable is True


# =============================================================================
# Status Calculation Tests
# =============================================================================


class TestStatusCalculation:
    """Test health status calculation rules."""
    
    def test_healthy_status_rules(self):
        """healthy = 0 danger AND 0 warning."""
        from aksara.ai.schema_doctor import AiSchemaHealth, AiSchemaIssue
        
        # With only info issues -> healthy
        health = AiSchemaHealth(
            status="healthy",
            issue_counts={"info": 5, "warning": 0, "danger": 0},
            issues=[
                AiSchemaIssue(id=f"info{i}", kind="index_mismatch", severity="info", message="info")
                for i in range(5)
            ],
            inspected_at="2026-01-25T12:00:00Z",
            app_version="0.4.7",
        )
        
        # Verify the model accepts this as valid
        assert health.status == "healthy"
    
    def test_degraded_status_rules(self):
        """degraded = at least 1 warning AND 0 danger."""
        from aksara.ai.schema_doctor import AiSchemaHealth, AiSchemaIssue
        
        health = AiSchemaHealth(
            status="degraded",
            issue_counts={"info": 0, "warning": 3, "danger": 0},
            issues=[
                AiSchemaIssue(id=f"warn{i}", kind="extra_table", severity="warning", message="warning")
                for i in range(3)
            ],
            inspected_at="2026-01-25T12:00:00Z",
            app_version="0.4.7",
        )
        
        assert health.status == "degraded"
    
    def test_danger_status_rules(self):
        """danger = at least 1 danger issue."""
        from aksara.ai.schema_doctor import AiSchemaHealth, AiSchemaIssue
        
        health = AiSchemaHealth(
            status="danger",
            issue_counts={"info": 0, "warning": 5, "danger": 1},
            issues=[
                AiSchemaIssue(id="danger1", kind="missing_table", severity="danger", message="danger"),
            ] + [
                AiSchemaIssue(id=f"warn{i}", kind="extra_column", severity="warning", message="warning")
                for i in range(5)
            ],
            inspected_at="2026-01-25T12:00:00Z",
            app_version="0.4.7",
        )
        
        assert health.status == "danger"


# =============================================================================
# Export/Import Tests
# =============================================================================


class TestSchemaDocorExports:
    """Test that all exports are available from aksara.ai."""
    
    def test_import_drift_kind(self):
        """DriftKind can be imported from aksara.ai."""
        from aksara.ai import DriftKind
        assert DriftKind is not None
    
    def test_import_issue_severity(self):
        """IssueSeverity can be imported from aksara.ai."""
        from aksara.ai import IssueSeverity
        assert IssueSeverity is not None
    
    def test_import_ai_schema_issue(self):
        """AiSchemaIssue can be imported from aksara.ai."""
        from aksara.ai import AiSchemaIssue
        assert AiSchemaIssue is not None
    
    def test_import_ai_schema_health(self):
        """AiSchemaHealth can be imported from aksara.ai."""
        from aksara.ai import AiSchemaHealth
        assert AiSchemaHealth is not None
    
    def test_import_ai_schema_issues_response(self):
        """AiSchemaIssuesResponse can be imported from aksara.ai."""
        from aksara.ai import AiSchemaIssuesResponse
        assert AiSchemaIssuesResponse is not None
    
    def test_import_db_column_info(self):
        """DbColumnInfo can be imported from aksara.ai."""
        from aksara.ai import DbColumnInfo
        assert DbColumnInfo is not None
    
    def test_import_db_table_info(self):
        """DbTableInfo can be imported from aksara.ai."""
        from aksara.ai import DbTableInfo
        assert DbTableInfo is not None
    
    def test_import_introspect_db_schema(self):
        """introspect_db_schema can be imported from aksara.ai."""
        from aksara.ai import introspect_db_schema
        assert introspect_db_schema is not None
    
    def test_import_build_model_schema_map(self):
        """build_model_schema_map can be imported from aksara.ai."""
        from aksara.ai import build_model_schema_map
        assert build_model_schema_map is not None
    
    def test_import_detect_schema_drift(self):
        """detect_schema_drift can be imported from aksara.ai."""
        from aksara.ai import detect_schema_drift
        assert detect_schema_drift is not None
    
    def test_import_classify_severity(self):
        """classify_severity can be imported from aksara.ai."""
        from aksara.ai import classify_severity
        assert classify_severity is not None
    
    def test_import_analyze_schema_health(self):
        """analyze_schema_health can be imported from aksara.ai."""
        from aksara.ai import analyze_schema_health
        assert analyze_schema_health is not None


# =============================================================================
# Endpoint Tests (with mocking)
# =============================================================================


class TestSchemaHealthEndpoint:
    """Test /ai/schema/health endpoint."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint_returns_200(self):
        """Health endpoint should return 200."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        with patch("aksara.ai.schema_doctor.analyze_schema_health") as mock_analyze:
            from aksara.ai.schema_doctor import AiSchemaHealth
            
            mock_analyze.return_value = AiSchemaHealth(
                status="healthy",
                issue_counts={"info": 0, "warning": 0, "danger": 0},
                issues=[],
                inspected_at="2026-01-25T12:00:00Z",
                app_version="0.4.7",
            )
            
            with TestClient(app) as client:
                response = client.get("/ai/schema/health")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_health_endpoint_returns_issues(self):
        """Health endpoint should return all issues."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        with patch("aksara.ai.schema_doctor.analyze_schema_health") as mock_analyze:
            from aksara.ai.schema_doctor import AiSchemaHealth, AiSchemaIssue
            
            mock_analyze.return_value = AiSchemaHealth(
                status="danger",
                issue_counts={"info": 0, "warning": 0, "danger": 1},
                issues=[
                    AiSchemaIssue(
                        id="test.missing",
                        kind="missing_table",
                        severity="danger",
                        message="Missing table",
                    )
                ],
                inspected_at="2026-01-25T12:00:00Z",
                app_version="0.4.7",
            )
            
            with TestClient(app) as client:
                response = client.get("/ai/schema/health")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "danger"
                assert len(data["issues"]) == 1


class TestSchemaIssuesEndpoint:
    """Test /ai/schema/issues endpoint."""
    
    @pytest.mark.asyncio
    async def test_issues_endpoint_returns_200(self):
        """Issues endpoint should return 200."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        with patch("aksara.ai.schema_doctor.analyze_schema_health") as mock_analyze:
            from aksara.ai.schema_doctor import AiSchemaHealth
            
            mock_analyze.return_value = AiSchemaHealth(
                status="healthy",
                issue_counts={"info": 0, "warning": 0, "danger": 0},
                issues=[],
                inspected_at="2026-01-25T12:00:00Z",
                app_version="0.4.7",
            )
            
            with TestClient(app) as client:
                response = client.get("/ai/schema/issues")
                
                assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_issues_filter_by_severity(self):
        """Issues endpoint should filter by severity."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        with patch("aksara.ai.schema_doctor.analyze_schema_health") as mock_analyze:
            from aksara.ai.schema_doctor import AiSchemaHealth, AiSchemaIssue
            
            mock_analyze.return_value = AiSchemaHealth(
                status="danger",
                issue_counts={"info": 0, "warning": 2, "danger": 1},
                issues=[
                    AiSchemaIssue(id="d1", kind="missing_table", severity="danger", message="Danger"),
                    AiSchemaIssue(id="w1", kind="extra_table", severity="warning", message="Warning 1"),
                    AiSchemaIssue(id="w2", kind="extra_column", severity="warning", message="Warning 2"),
                ],
                inspected_at="2026-01-25T12:00:00Z",
                app_version="0.4.7",
            )
            
            with TestClient(app) as client:
                response = client.get("/ai/schema/issues?severity=warning")
                
                assert response.status_code == 200
                data = response.json()
                assert data["total_count"] == 3
                assert data["filtered_count"] == 2
                for issue in data["issues"]:
                    assert issue["severity"] == "warning"
    
    @pytest.mark.asyncio
    async def test_issues_filter_by_kind(self):
        """Issues endpoint should filter by kind."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        with patch("aksara.ai.schema_doctor.analyze_schema_health") as mock_analyze:
            from aksara.ai.schema_doctor import AiSchemaHealth, AiSchemaIssue
            
            mock_analyze.return_value = AiSchemaHealth(
                status="degraded",
                issue_counts={"info": 0, "warning": 2, "danger": 0},
                issues=[
                    AiSchemaIssue(id="e1", kind="extra_table", severity="warning", message="Extra 1"),
                    AiSchemaIssue(id="e2", kind="extra_column", severity="warning", message="Extra 2"),
                ],
                inspected_at="2026-01-25T12:00:00Z",
                app_version="0.4.7",
            )
            
            with TestClient(app) as client:
                response = client.get("/ai/schema/issues?kind=extra_table")
                
                assert response.status_code == 200
                data = response.json()
                assert data["filtered_count"] == 1
                assert data["issues"][0]["kind"] == "extra_table"
    
    @pytest.mark.asyncio
    async def test_issues_invalid_severity_returns_400(self):
        """Invalid severity filter should return 400."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        with patch("aksara.ai.schema_doctor.analyze_schema_health") as mock_analyze:
            from aksara.ai.schema_doctor import AiSchemaHealth
            
            mock_analyze.return_value = AiSchemaHealth(
                status="healthy",
                issue_counts={"info": 0, "warning": 0, "danger": 0},
                issues=[],
                inspected_at="2026-01-25T12:00:00Z",
                app_version="0.4.7",
            )
            
            with TestClient(app) as client:
                response = client.get("/ai/schema/issues?severity=invalid")
                
                assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_issues_invalid_kind_returns_400(self):
        """Invalid kind filter should return 400."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        with patch("aksara.ai.schema_doctor.analyze_schema_health") as mock_analyze:
            from aksara.ai.schema_doctor import AiSchemaHealth
            
            mock_analyze.return_value = AiSchemaHealth(
                status="healthy",
                issue_counts={"info": 0, "warning": 0, "danger": 0},
                issues=[],
                inspected_at="2026-01-25T12:00:00Z",
                app_version="0.4.7",
            )
            
            with TestClient(app) as client:
                response = client.get("/ai/schema/issues?kind=invalid_kind")
                
                assert response.status_code == 400


class TestSchemaDiffEndpoint:
    """Test /ai/schema/diff endpoint."""
    
    @pytest.mark.asyncio
    async def test_diff_endpoint_returns_200(self):
        """Diff endpoint should return 200."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        with patch("aksara.db.engine.Database") as MockDb:
            mock_instance = AsyncMock()
            MockDb.get_instance.return_value = mock_instance
            mock_instance.fetch.return_value = []
            
            with patch("aksara.ai.schema_doctor.build_model_schema_map") as mock_build:
                mock_build.return_value = {}
                
                with TestClient(app) as client:
                    response = client.get("/ai/schema/diff")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert "tables" in data
                    assert "model_only" in data
                    assert "db_only" in data
    
    @pytest.mark.asyncio
    async def test_diff_endpoint_db_not_configured(self):
        """Diff endpoint should return 503 if DB not configured."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        with patch("aksara.db.engine.Database") as MockDb:
            MockDb.get_instance.side_effect = RuntimeError("No database")
            
            with TestClient(app) as client:
                response = client.get("/ai/schema/diff")
                
                assert response.status_code == 503
    
    @pytest.mark.asyncio
    async def test_diff_endpoint_table_not_found(self):
        """Diff endpoint should return 404 for unknown table."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        with patch("aksara.db.engine.Database") as MockDb:
            mock_instance = AsyncMock()
            MockDb.get_instance.return_value = mock_instance
            mock_instance.fetch.return_value = []
            
            with patch("aksara.ai.schema_doctor.build_model_schema_map") as mock_build:
                mock_build.return_value = {}
                
                with TestClient(app) as client:
                    response = client.get("/ai/schema/diff?table=nonexistent")
                    
                    assert response.status_code == 404
