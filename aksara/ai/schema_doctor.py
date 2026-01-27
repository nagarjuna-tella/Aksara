"""
AI Schema Doctor & Migration Guardrails - v0.4.7

Provides schema health and drift detection:
- Compares models vs DB schema vs migrations
- Detects drift & inconsistencies
- Classifies severity (info, warning, danger)
- Exposes via /ai/schema/* endpoints

This module is fully deterministic and JSON-serializable.
It does NOT generate migrations - that's Planner + Codegen territory.
This is the doctor + X-ray that everything else uses.

Usage:
    from aksara.ai.schema_doctor import (
        analyze_schema_health,
        AiSchemaHealth,
        AiSchemaIssue,
    )
    
    # Get full schema health report
    health = await analyze_schema_health(app)
    
    if health.status == "danger":
        print(f"Found {health.issue_counts['danger']} critical issues!")
        for issue in health.issues:
            print(f"  [{issue.severity}] {issue.message}")
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Type

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from fastapi import FastAPI
    from aksara.db.engine import Database


# =============================================================================
# Type Literals
# =============================================================================

DriftKind = Literal[
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

IssueSeverity = Literal["info", "warning", "danger"]


# =============================================================================
# Schema Issue Model
# =============================================================================

class AiSchemaIssue(BaseModel):
    """
    Represents a single schema drift or inconsistency.
    
    Each issue has a deterministic ID based on the location and kind,
    making it easy to track issues across multiple runs.
    
    Attributes:
        id: Deterministic identifier (e.g., "blog.Article.slug.missing_column")
        kind: The type of drift detected
        severity: How critical this issue is (info/warning/danger)
        app_label: The application label if applicable
        model: The model name if applicable
        table: The database table name
        column: The column name if applicable
        expected: What models/migrations expect
        actual: What the database actually has
        message: Human-readable description of the issue
        hint: Short actionable suggestion
        tags: Additional classification tags
    
    Example:
        {
            "id": "blog.Article.slug.missing_column",
            "kind": "missing_column",
            "severity": "danger",
            "app_label": "blog",
            "model": "Article",
            "table": "blog_articles",
            "column": "slug",
            "expected": {"type": "varchar(255)", "nullable": true},
            "actual": null,
            "message": "Column 'slug' defined in model Article is missing from table 'blog_articles'",
            "hint": "Run makemigrations/migrate to create the missing column",
            "tags": ["migration", "data_loss_risk"]
        }
    """
    
    id: str = Field(..., description="Deterministic identifier for this issue")
    kind: DriftKind = Field(..., description="Type of drift detected")
    severity: IssueSeverity = Field(..., description="Severity level")
    app_label: Optional[str] = Field(None, description="Application label")
    model: Optional[str] = Field(None, description="Model name")
    table: Optional[str] = Field(None, description="Database table name")
    column: Optional[str] = Field(None, description="Column name if applicable")
    expected: Optional[Dict[str, Any]] = Field(
        None, description="What models/migrations expect"
    )
    actual: Optional[Dict[str, Any]] = Field(
        None, description="What the database actually has"
    )
    message: str = Field(..., description="Human-readable description")
    hint: Optional[str] = Field(None, description="Short actionable suggestion")
    tags: List[str] = Field(default_factory=list, description="Classification tags")
    
    model_config = {"extra": "forbid"}


# =============================================================================
# Schema Health Model
# =============================================================================

class AiSchemaHealth(BaseModel):
    """
    Overall schema health report.
    
    Aggregates all detected issues and provides a status summary.
    
    Status rules:
        - healthy: 0 danger and 0 warning issues
        - degraded: at least 1 warning, but 0 danger
        - danger: at least 1 danger issue
    
    Attributes:
        status: Overall health status
        issue_counts: Count of issues by severity
        issues: List of all detected issues
        inspected_at: ISO timestamp of inspection
        db_version: PostgreSQL version
        db_name: Database name
        app_version: Aksara framework version
    
    Example:
        {
            "status": "degraded",
            "issue_counts": {"info": 0, "warning": 2, "danger": 0},
            "issues": [...],
            "inspected_at": "2026-01-25T12:00:00Z",
            "db_version": "PostgreSQL 16.1",
            "db_name": "myapp_prod",
            "app_version": "0.4.7"
        }
    """
    
    status: Literal["healthy", "degraded", "danger"] = Field(
        ..., description="Overall health status"
    )
    issue_counts: Dict[IssueSeverity, int] = Field(
        ..., description="Count of issues by severity"
    )
    issues: List[AiSchemaIssue] = Field(
        default_factory=list, description="All detected issues"
    )
    inspected_at: str = Field(..., description="ISO timestamp of inspection")
    db_version: Optional[str] = Field(None, description="PostgreSQL version")
    db_name: Optional[str] = Field(None, description="Database name")
    app_version: str = Field(..., description="Aksara framework version")
    
    model_config = {"extra": "forbid"}


# =============================================================================
# Internal DB Introspection Models
# =============================================================================

class DbColumnInfo(BaseModel):
    """
    Information about a database column from introspection.
    
    This is an internal model used for comparing DB schema against models.
    """
    
    name: str = Field(..., description="Column name")
    type: str = Field(..., description="PostgreSQL data type")
    is_nullable: bool = Field(..., description="Whether NULL is allowed")
    default: Optional[str] = Field(None, description="Default value expression")
    is_primary_key: bool = Field(False, description="Whether this is the primary key")
    
    model_config = {"extra": "forbid"}


class DbTableInfo(BaseModel):
    """
    Information about a database table from introspection.
    
    This is an internal model used for comparing DB schema against models.
    """
    
    name: str = Field(..., description="Table name")
    columns: Dict[str, DbColumnInfo] = Field(
        default_factory=dict, description="Column name -> column info"
    )
    
    model_config = {"extra": "forbid"}


# =============================================================================
# DB Introspection
# =============================================================================

async def introspect_db_schema(db: "Database") -> Dict[str, DbTableInfo]:
    """
    Introspect the database schema using PostgreSQL catalogs.
    
    Queries information_schema.columns and pg_catalog for:
    - Table names
    - Column names, types, nullability, defaults
    - Primary key information
    
    Args:
        db: The Aksara Database instance
        
    Returns:
        Mapping of table_name -> DbTableInfo
    """
    # Query all tables and columns
    columns_query = """
        SELECT 
            c.table_name,
            c.column_name,
            c.data_type,
            c.udt_name,
            c.is_nullable,
            c.column_default,
            c.character_maximum_length
        FROM information_schema.columns c
        JOIN information_schema.tables t 
            ON c.table_name = t.table_name 
            AND c.table_schema = t.table_schema
        WHERE c.table_schema = 'public'
            AND t.table_type = 'BASE TABLE'
        ORDER BY c.table_name, c.ordinal_position
    """
    
    # Query primary keys
    pk_query = """
        SELECT
            tc.table_name,
            kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_schema = 'public'
    """
    
    # Execute queries
    columns_rows = await db.fetch(columns_query)
    pk_rows = await db.fetch(pk_query)
    
    # Build primary key lookup
    pk_lookup: Dict[str, set] = {}
    for row in pk_rows:
        table_name = row["table_name"]
        column_name = row["column_name"]
        if table_name not in pk_lookup:
            pk_lookup[table_name] = set()
        pk_lookup[table_name].add(column_name)
    
    # Build table info
    tables: Dict[str, DbTableInfo] = {}
    
    for row in columns_rows:
        table_name = row["table_name"]
        column_name = row["column_name"]
        
        # Construct full type string
        data_type = row["data_type"]
        udt_name = row["udt_name"]
        max_length = row["character_maximum_length"]
        
        # Normalize type string
        if data_type == "character varying":
            type_str = f"varchar({max_length})" if max_length else "varchar"
        elif data_type == "character":
            type_str = f"char({max_length})" if max_length else "char"
        elif data_type == "ARRAY":
            type_str = f"{udt_name}[]"
        elif data_type == "USER-DEFINED":
            type_str = udt_name
        else:
            type_str = data_type
        
        # Check nullability
        is_nullable = row["is_nullable"] == "YES"
        
        # Check if primary key
        is_pk = (
            table_name in pk_lookup and 
            column_name in pk_lookup[table_name]
        )
        
        # Get default
        default = row["column_default"]
        
        # Create column info
        col_info = DbColumnInfo(
            name=column_name,
            type=type_str,
            is_nullable=is_nullable,
            default=default,
            is_primary_key=is_pk,
        )
        
        # Add to table
        if table_name not in tables:
            tables[table_name] = DbTableInfo(name=table_name)
        tables[table_name].columns[column_name] = col_info
    
    return tables


# =============================================================================
# Model Schema Mapping
# =============================================================================

def build_model_schema_map() -> Dict[str, Dict[str, Any]]:
    """
    Build a schema map from all registered Aksara models.
    
    Iterates all registered models and extracts:
    - app_label, table_name, fields
    - Primary key, nullability, types
    - Relations (FKs)
    
    Returns:
        Mapping of table_name -> model schema info
    """
    from aksara.registry import ModelRegistry
    
    result: Dict[str, Dict[str, Any]] = {}
    
    for model_name, model in ModelRegistry.all().items():
        # Skip the base Model class
        if model_name == "Model":
            continue
        
        meta = model.meta
        table_name = meta.table_name
        app_label = meta.app_label
        
        # Build column info from fields
        columns: Dict[str, Dict[str, Any]] = {}
        
        for field in meta.fields:
            col_name = getattr(field, "column_name", None) or field.name
            
            # Map Aksara field types to PostgreSQL types
            field_type = _map_field_to_pg_type(field)
            
            columns[col_name] = {
                "name": col_name,
                "field_name": field.name,
                "type": field_type,
                "is_nullable": getattr(field, "nullable", False),
                "default": _get_field_default(field),
                "is_primary_key": getattr(field, "primary_key", False),
                "field_class": field.__class__.__name__,
            }
        
        result[table_name] = {
            "model_name": model_name,
            "app_label": app_label,
            "table_name": table_name,
            "columns": columns,
            "pk_name": meta.pk_name,
        }
    
    return result


def _map_field_to_pg_type(field) -> str:
    """
    Map a Aksara field to its PostgreSQL type.
    
    This is approximate and used for comparison purposes.
    """
    from aksara import fields as f
    
    field_class = field.__class__.__name__
    
    # Map field classes to PostgreSQL types
    type_map = {
        "UUID": "uuid",
        "String": "varchar",
        "Text": "text",
        "Integer": "integer",
        "BigInteger": "bigint",
        "SmallInteger": "smallint",
        "Float": "double precision",
        "Decimal": "numeric",
        "Boolean": "boolean",
        "DateTime": "timestamp with time zone",
        "Date": "date",
        "Time": "time",
        "JSON": "jsonb",
        "JSONB": "jsonb",
        "Array": "array",
        "ForeignKey": "uuid",  # Assuming UUID FKs
        "OneToOne": "uuid",
    }
    
    pg_type = type_map.get(field_class, "unknown")
    
    # Handle varchar with max_length
    if field_class == "String":
        max_length = getattr(field, "max_length", None)
        if max_length:
            pg_type = f"varchar({max_length})"
    
    return pg_type


def _get_field_default(field) -> Optional[str]:
    """
    Get the default value expression for a field.
    
    Returns None if no default, or a string representation.
    """
    default = getattr(field, "default", None)
    
    if default is None:
        return None
    
    # Check for callable defaults
    if callable(default):
        # Common patterns
        default_str = str(default)
        if "uuid4" in default_str:
            return "gen_random_uuid()"
        if "now" in default_str or "utcnow" in default_str:
            return "CURRENT_TIMESTAMP"
        return "<callable>"
    
    # Primitive defaults
    if isinstance(default, bool):
        return "true" if default else "false"
    if isinstance(default, (int, float)):
        return str(default)
    if isinstance(default, str):
        return f"'{default}'"
    
    return str(default)


# =============================================================================
# Drift Detection
# =============================================================================

def detect_schema_drift(
    models_map: Dict[str, Dict[str, Any]],
    db_map: Dict[str, DbTableInfo],
) -> List[AiSchemaIssue]:
    """
    Detect schema drift between models and database.
    
    Compares the model schema map against the introspected DB schema
    and generates issues for any differences found.
    
    Args:
        models_map: Model schema map from build_model_schema_map()
        db_map: DB schema map from introspect_db_schema()
        
    Returns:
        List of detected schema issues
    """
    issues: List[AiSchemaIssue] = []
    
    # Get all model table names
    model_tables = set(models_map.keys())
    db_tables = set(db_map.keys())
    
    # Filter out known system/internal tables
    system_tables = {
        "alembic_version",
        "aksara_migrations",
        "django_migrations",
        "spatial_ref_sys",
    }
    db_tables = db_tables - system_tables
    
    # 1. Check for missing tables (model exists, DB doesn't have it)
    missing_tables = model_tables - db_tables
    for table_name in missing_tables:
        model_info = models_map[table_name]
        issue = _create_issue(
            kind="missing_table",
            app_label=model_info.get("app_label"),
            model=model_info.get("model_name"),
            table=table_name,
            expected={"exists": True},
            actual={"exists": False},
            message=f"Table '{table_name}' defined in model {model_info.get('model_name')} does not exist in database",
            hint="Run migrations to create the table",
            tags=["migration", "critical"],
        )
        issues.append(issue)
    
    # 2. Check for extra tables (DB has it, no model)
    extra_tables = db_tables - model_tables
    for table_name in extra_tables:
        # Skip M2M junction tables (they usually have two FK columns)
        db_table = db_map[table_name]
        if _is_likely_junction_table(db_table):
            continue
        
        issue = _create_issue(
            kind="extra_table",
            table=table_name,
            expected={"exists": False},
            actual={"exists": True, "columns": list(db_table.columns.keys())},
            message=f"Table '{table_name}' exists in database but has no corresponding model",
            hint="Consider creating a model or removing the table if unused",
            tags=["legacy", "cleanup"],
        )
        issues.append(issue)
    
    # 3. Check columns for tables that exist in both
    common_tables = model_tables & db_tables
    for table_name in common_tables:
        model_info = models_map[table_name]
        db_table = db_map[table_name]
        
        model_cols = set(model_info["columns"].keys())
        db_cols = set(db_table.columns.keys())
        
        app_label = model_info.get("app_label")
        model_name = model_info.get("model_name")
        
        # 3a. Missing columns
        missing_cols = model_cols - db_cols
        for col_name in missing_cols:
            col_info = model_info["columns"][col_name]
            issue = _create_issue(
                kind="missing_column",
                app_label=app_label,
                model=model_name,
                table=table_name,
                column=col_name,
                expected={
                    "type": col_info["type"],
                    "nullable": col_info["is_nullable"],
                },
                actual=None,
                message=f"Column '{col_name}' defined in model {model_name} is missing from table '{table_name}'",
                hint="Run makemigrations and migrate to create the missing column",
                tags=["migration", "data_loss_risk"],
            )
            issues.append(issue)
        
        # 3b. Extra columns
        extra_cols = db_cols - model_cols
        for col_name in extra_cols:
            db_col = db_table.columns[col_name]
            issue = _create_issue(
                kind="extra_column",
                app_label=app_label,
                model=model_name,
                table=table_name,
                column=col_name,
                expected=None,
                actual={
                    "type": db_col.type,
                    "nullable": db_col.is_nullable,
                },
                message=f"Column '{col_name}' exists in table '{table_name}' but is not defined in model {model_name}",
                hint="Consider adding the field to the model or dropping the column",
                tags=["legacy", "cleanup"],
            )
            issues.append(issue)
        
        # 3c. Check common columns for mismatches
        common_cols = model_cols & db_cols
        for col_name in common_cols:
            model_col = model_info["columns"][col_name]
            db_col = db_table.columns[col_name]
            
            # Type mismatch
            if not _types_compatible(model_col["type"], db_col.type):
                issue = _create_issue(
                    kind="type_mismatch",
                    app_label=app_label,
                    model=model_name,
                    table=table_name,
                    column=col_name,
                    expected={"type": model_col["type"]},
                    actual={"type": db_col.type},
                    message=f"Column '{col_name}' in table '{table_name}' has type mismatch: model expects '{model_col['type']}', DB has '{db_col.type}'",
                    hint="Alter the column type or update the model field",
                    tags=["type", "potential_data_loss"],
                )
                issues.append(issue)
            
            # Nullability mismatch
            model_nullable = model_col["is_nullable"]
            db_nullable = db_col.is_nullable
            
            if model_nullable != db_nullable:
                # Danger if model says NOT NULL but DB allows NULL
                # (data might be missing)
                # Warning if model says NULL but DB says NOT NULL
                # (writes might fail)
                if not model_nullable and db_nullable:
                    severity_hint = "danger"
                    msg_detail = "model expects NOT NULL but DB allows NULL"
                else:
                    severity_hint = "warning"
                    msg_detail = "model allows NULL but DB requires NOT NULL"
                
                issue = _create_issue(
                    kind="nullability_mismatch",
                    app_label=app_label,
                    model=model_name,
                    table=table_name,
                    column=col_name,
                    expected={"nullable": model_nullable},
                    actual={"nullable": db_nullable},
                    message=f"Column '{col_name}' in table '{table_name}' has nullability mismatch: {msg_detail}",
                    hint="Alter the column constraint or update the model field",
                    tags=["constraint"],
                    severity_override=severity_hint,
                )
                issues.append(issue)
            
            # Primary key mismatch
            model_pk = model_col["is_primary_key"]
            db_pk = db_col.is_primary_key
            
            if model_pk != db_pk:
                issue = _create_issue(
                    kind="pk_mismatch",
                    app_label=app_label,
                    model=model_name,
                    table=table_name,
                    column=col_name,
                    expected={"is_primary_key": model_pk},
                    actual={"is_primary_key": db_pk},
                    message=f"Column '{col_name}' in table '{table_name}' has primary key mismatch: model says PK={model_pk}, DB says PK={db_pk}",
                    hint="Recreate the table with correct primary key constraint",
                    tags=["pk", "critical"],
                )
                issues.append(issue)
    
    return issues


def _is_likely_junction_table(table_info: DbTableInfo) -> bool:
    """
    Check if a table looks like a M2M junction table.
    
    Junction tables typically have:
    - 2-3 columns (id + 2 FKs)
    - Column names ending in _id
    """
    cols = list(table_info.columns.values())
    if len(cols) < 2 or len(cols) > 4:
        return False
    
    fk_like_cols = sum(1 for c in cols if c.name.endswith("_id"))
    return fk_like_cols >= 2


def _types_compatible(model_type: str, db_type: str) -> bool:
    """
    Check if model type and DB type are compatible.
    
    This is a fuzzy comparison since exact type strings may differ.
    """
    # Normalize types for comparison
    model_normalized = model_type.lower().strip()
    db_normalized = db_type.lower().strip()
    
    # Direct match
    if model_normalized == db_normalized:
        return True
    
    # Handle varchar variations
    if model_normalized.startswith("varchar") and db_normalized.startswith("varchar"):
        return True
    if model_normalized.startswith("varchar") and db_normalized == "character varying":
        return True
    
    # Handle timestamp variations
    if "timestamp" in model_normalized and "timestamp" in db_normalized:
        return True
    
    # Handle integer variations
    int_types = {"integer", "int", "int4", "serial", "serial4"}
    if model_normalized in int_types and db_normalized in int_types:
        return True
    
    # Handle bigint variations
    bigint_types = {"bigint", "int8", "bigserial", "serial8"}
    if model_normalized in bigint_types and db_normalized in bigint_types:
        return True
    
    # Handle boolean variations
    bool_types = {"boolean", "bool"}
    if model_normalized in bool_types and db_normalized in bool_types:
        return True
    
    # Handle json variations
    json_types = {"json", "jsonb"}
    if model_normalized in json_types and db_normalized in json_types:
        return True
    
    # Handle float/double variations
    float_types = {"float", "double precision", "float8", "real", "float4"}
    if model_normalized in float_types and db_normalized in float_types:
        return True
    
    return False


def _create_issue(
    kind: DriftKind,
    message: str,
    hint: str,
    app_label: Optional[str] = None,
    model: Optional[str] = None,
    table: Optional[str] = None,
    column: Optional[str] = None,
    expected: Optional[Dict[str, Any]] = None,
    actual: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    severity_override: Optional[IssueSeverity] = None,
) -> AiSchemaIssue:
    """
    Create an AiSchemaIssue with deterministic ID and severity.
    """
    # Build deterministic ID
    id_parts = []
    if app_label:
        id_parts.append(app_label)
    if model:
        id_parts.append(model)
    if table and not model:
        id_parts.append(table)
    if column:
        id_parts.append(column)
    id_parts.append(kind)
    
    issue_id = ".".join(id_parts)
    
    # Determine severity
    severity = severity_override or classify_severity(kind, expected, actual)
    
    return AiSchemaIssue(
        id=issue_id,
        kind=kind,
        severity=severity,
        app_label=app_label,
        model=model,
        table=table,
        column=column,
        expected=expected,
        actual=actual,
        message=message,
        hint=hint,
        tags=tags or [],
    )


def classify_severity(
    kind: DriftKind,
    expected: Optional[Dict[str, Any]] = None,
    actual: Optional[Dict[str, Any]] = None,
) -> IssueSeverity:
    """
    Classify the severity of a schema issue.
    
    Rules:
    - missing_table → danger
    - missing_column → danger (data not being stored)
    - extra_table → warning (legacy table)
    - extra_column → warning
    - type_mismatch → danger if types incompatible
    - nullability_mismatch → depends on direction
    - default_mismatch → warning
    - pk_mismatch → danger
    - fk_mismatch → warning or danger
    - index_mismatch → info
    - unique_mismatch → warning
    """
    severity_map: Dict[DriftKind, IssueSeverity] = {
        "missing_table": "danger",
        "extra_table": "warning",
        "missing_column": "danger",
        "extra_column": "warning",
        "type_mismatch": "danger",
        "nullability_mismatch": "warning",  # Can be overridden
        "default_mismatch": "warning",
        "pk_mismatch": "danger",
        "fk_mismatch": "warning",
        "index_mismatch": "info",
        "unique_mismatch": "warning",
    }
    
    return severity_map.get(kind, "warning")


# =============================================================================
# Schema Health Analysis
# =============================================================================

async def analyze_schema_health(app: "FastAPI") -> AiSchemaHealth:
    """
    Analyze schema health by comparing models vs database.
    
    This is the main entry point for schema health checks.
    It:
    1. Gets the DB instance
    2. Introspects the database schema
    3. Builds the model schema map
    4. Detects schema drift
    5. Aggregates results into AiSchemaHealth
    
    Args:
        app: The FastAPI application instance
        
    Returns:
        AiSchemaHealth with status, issues, and metadata
    """
    import aksara
    from aksara.db.engine import Database
    
    # Get database instance
    try:
        db = Database.get_instance()
    except RuntimeError:
        # No database configured
        return AiSchemaHealth(
            status="danger",
            issue_counts={"info": 0, "warning": 0, "danger": 1},
            issues=[
                AiSchemaIssue(
                    id="system.database.not_configured",
                    kind="missing_table",  # Using as proxy for missing DB
                    severity="danger",
                    message="Database is not configured or connected",
                    hint="Initialize the database connection before checking schema health",
                    tags=["configuration"],
                )
            ],
            inspected_at=datetime.now(timezone.utc).isoformat(),
            app_version=aksara.__version__,
        )
    
    # Get DB metadata
    try:
        db_version = await db.fetchval("SELECT version()")
        db_name = await db.fetchval("SELECT current_database()")
    except Exception:
        db_version = None
        db_name = None
    
    # Introspect database
    db_map = await introspect_db_schema(db)
    
    # Build model map
    models_map = build_model_schema_map()
    
    # Detect drift
    issues = detect_schema_drift(models_map, db_map)
    
    # Count issues by severity
    issue_counts: Dict[IssueSeverity, int] = {
        "info": 0,
        "warning": 0,
        "danger": 0,
    }
    for issue in issues:
        issue_counts[issue.severity] += 1
    
    # Determine status
    if issue_counts["danger"] > 0:
        status = "danger"
    elif issue_counts["warning"] > 0:
        status = "degraded"
    else:
        status = "healthy"
    
    return AiSchemaHealth(
        status=status,
        issue_counts=issue_counts,
        issues=issues,
        inspected_at=datetime.now(timezone.utc).isoformat(),
        db_version=db_version,
        db_name=db_name,
        app_version=aksara.__version__,
    )


# =============================================================================
# Response Models for Endpoints
# =============================================================================

class AiSchemaIssuesResponse(BaseModel):
    """
    Response model for /ai/schema/issues endpoint.
    
    Returns just the status and issues list (lighter than full health).
    """
    
    status: Literal["healthy", "degraded", "danger"] = Field(
        ..., description="Overall health status"
    )
    issues: List[AiSchemaIssue] = Field(
        default_factory=list, description="All detected issues"
    )
    
    model_config = {"extra": "forbid"}
