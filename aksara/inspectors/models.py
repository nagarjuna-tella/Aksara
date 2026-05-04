"""
Aksara Model Inspector

v0.5.21: Deep model introspection for schema analysis, AI context, and CLI.

Provides:
    - ModelInspectorField: Per-field metadata (type, null, default, etc.)
    - ModelInspectorRelationship: FK/M2M relationship metadata
    - ModelInspectorConstraint: Index/unique/check constraint info
    - ModelInspectorSummary: Full model inspection result
    - inspect_model(): Inspect a single model class
    - inspect_all_models(): Inspect all registered models
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field


# =============================================================================
# Inspector Models
# =============================================================================


class ModelInspectorField(BaseModel):
    """Detailed field metadata from model introspection."""

    name: str = Field(description="Field name as defined on the model class")
    column_name: str = Field(description="Database column name")
    field_type: str = Field(description="Aksara field class name (e.g. CharField, IntegerField)")
    python_type: str = Field(
        default="Any",
        description="Expected Python type (e.g. str, int, uuid.UUID)",
    )
    nullable: bool = Field(default=False, description="Whether NULL is allowed")
    primary_key: bool = Field(default=False, description="Is this the primary key")
    unique: bool = Field(default=False, description="Has a UNIQUE constraint")
    has_default: bool = Field(default=False, description="Whether a default value is set")
    default_repr: Optional[str] = Field(
        default=None,
        description="String representation of the default value",
    )
    max_length: Optional[int] = Field(default=None, description="Max length for string fields")
    choices: Optional[List[str]] = Field(default=None, description="Enum/choice values if any")
    is_relation: bool = Field(default=False, description="Whether this is a relation field")
    ai_description: str = Field(default="", description="AI-facing description")
    ai_sensitive: bool = Field(default=False, description="Whether field holds sensitive data")
    auto_generated: str = Field(
        default="",
        description="Auto-generated comment about this field",
    )


class ModelInspectorRelationship(BaseModel):
    """Relationship metadata from model introspection."""

    field_name: str = Field(description="Field name on the source model")
    kind: str = Field(description="Relationship kind: fk, m2m, o2o")
    target_model: str = Field(description="Target model class name")
    target_table: str = Field(
        default="",
        description="Target database table name",
    )
    on_delete: str = Field(
        default="CASCADE",
        description="ON DELETE behaviour (CASCADE, SET_NULL, RESTRICT)",
    )
    through_table: Optional[str] = Field(
        default=None,
        description="Junction table for M2M relationships",
    )
    related_name: Optional[str] = Field(
        default=None,
        description="Reverse accessor name on the target model",
    )
    nullable: bool = Field(default=False, description="Whether FK column is nullable")


class ModelInspectorConstraint(BaseModel):
    """Constraint / index info inferred from the model definition."""

    kind: str = Field(description="Type: primary_key, unique, index, check")
    columns: List[str] = Field(
        default_factory=list,
        description="Column names involved",
    )
    name: Optional[str] = Field(
        default=None,
        description="Constraint name (if derivable)",
    )
    description: str = Field(
        default="",
        description="Human-readable description",
    )


class ModelInspectorSummary(BaseModel):
    """Complete model inspection result."""

    name: str = Field(description="Model class name")
    table_name: str = Field(description="Database table name")
    app_label: Optional[str] = Field(default=None, description="Application label")
    num_fields: int = Field(default=0, description="Total number of fields")
    num_relationships: int = Field(default=0, description="Total number of relationships")
    has_timestamps: bool = Field(
        default=False,
        description="Has created_at / updated_at auto-fields",
    )
    pk_field: Optional[str] = Field(default=None, description="Primary key field name")
    pk_type: str = Field(default="IntegerField", description="Primary key field type")
    fields: List[ModelInspectorField] = Field(
        default_factory=list,
        description="All fields with metadata",
    )
    relationships: List[ModelInspectorRelationship] = Field(
        default_factory=list,
        description="All FK / M2M / O2O relationships",
    )
    constraints: List[ModelInspectorConstraint] = Field(
        default_factory=list,
        description="Inferred constraints and indexes",
    )
    ai_description: str = Field(
        default="",
        description="AI-level description of the model",
    )
    ai_agent_exposed: bool = Field(
        default=True,
        description="Whether AI agents can access this model",
    )
    create_table_sql: str = Field(
        default="",
        description="CREATE TABLE SQL statement",
    )
    comments: List[str] = Field(
        default_factory=list,
        description="Auto-generated inspector notes",
    )


# =============================================================================
# Helpers
# =============================================================================

_FIELD_TYPE_MAP: Dict[str, str] = {
    "AutoField": "int",
    "BigAutoField": "int",
    "IntegerField": "int",
    "BigIntegerField": "int",
    "SmallIntegerField": "int",
    "FloatField": "float",
    "DecimalField": "Decimal",
    "BooleanField": "bool",
    "CharField": "str",
    "TextField": "str",
    "FileField": "str",
    "ImageField": "str",
    "SlugField": "str",
    "EmailField": "str",
    "URLField": "str",
    "UUIDField": "uuid.UUID",
    "DateTimeField": "datetime",
    "DateField": "date",
    "TimeField": "time",
    "JSONField": "Any",
    "ArrayField": "list",
    "ForeignKey": "int",
    "OneToOne": "int",
    "ManyToMany": "list",
}


def _safe_default_repr(field: Any) -> Optional[str]:
    """Safely convert a field default to a string repr."""
    default = getattr(field, "default", None)
    if default is None:
        return None
    if callable(default):
        return f"{default.__name__}()"
    try:
        return repr(default)
    except Exception:
        return str(default)


def _infer_auto_comment(field: Any, fname: str) -> str:
    """Generate an auto-comment about a field based on its properties."""
    parts: List[str] = []
    if getattr(field, "primary_key", False):
        parts.append("Primary key")
    if getattr(field, "unique", False) and not getattr(field, "primary_key", False):
        parts.append("Unique")
    if getattr(field, "nullable", False):
        parts.append("Nullable")
    if getattr(field, "ai_sensitive", False):
        parts.append("⚠️ Sensitive")
    if fname in ("created_at", "updated_at"):
        parts.append("Auto-timestamp")
    return "; ".join(parts)


# =============================================================================
# Core Inspection Functions
# =============================================================================


def inspect_model(model: Type[Any]) -> ModelInspectorSummary:
    """
    Deeply inspect a model class and return structured metadata.

    Works with any Aksara Model subclass.

    Args:
        model: The model class to inspect.

    Returns:
        ModelInspectorSummary with full field, relationship, and
        constraint information.
    """
    from aksara.fields import ForeignKey, ManyToMany

    name = model.__name__
    table_name = getattr(model, "__tablename__", name.lower())
    ai_meta = getattr(model, "_ai_meta", None)
    ai_desc = ""
    ai_exposed = True
    if ai_meta:
        ai_desc = getattr(ai_meta, "ai_description", "") or ""
        ai_exposed = getattr(ai_meta, "ai_agent_exposed", True)

    # App label
    app_label: Optional[str] = None
    meta_info = getattr(model, "meta", None)
    if meta_info is not None:
        app_label = getattr(meta_info, "app_label", None)

    fields_dict = getattr(model, "_fields", {})
    fk_fields = getattr(model, "_fk_fields", {})
    m2m_fields = getattr(model, "_m2m_fields", {})

    # --- Fields ---
    inspector_fields: List[ModelInspectorField] = []
    for fname, fobj in fields_dict.items():
        ftype = fobj.__class__.__name__
        python_type = _FIELD_TYPE_MAP.get(ftype, "Any")

        col_name = fname
        if isinstance(fobj, ForeignKey):
            col_name = getattr(fobj, "db_column_name", f"{fname}_id")

        has_default = getattr(fobj, "default", None) is not None
        default_repr = _safe_default_repr(fobj) if has_default else None
        max_length = getattr(fobj, "max_length", None)
        choices_raw = getattr(fobj, "choices", None)
        choices = list(choices_raw) if choices_raw else None
        is_rel = isinstance(fobj, (ForeignKey, ManyToMany))

        inspector_fields.append(ModelInspectorField(
            name=fname,
            column_name=col_name,
            field_type=ftype,
            python_type=python_type,
            nullable=getattr(fobj, "nullable", False),
            primary_key=getattr(fobj, "primary_key", False),
            unique=getattr(fobj, "unique", False),
            has_default=has_default,
            default_repr=default_repr,
            max_length=max_length,
            choices=choices,
            is_relation=is_rel,
            ai_description=getattr(fobj, "ai_description", "") or "",
            ai_sensitive=getattr(fobj, "ai_sensitive", False),
            auto_generated=_infer_auto_comment(fobj, fname),
        ))

    # --- Relationships ---
    relationships: List[ModelInspectorRelationship] = []
    for fname, fobj in fk_fields.items():
        target = fobj._to if isinstance(fobj._to, str) else fobj._to.__name__
        target_table = ""
        if not isinstance(fobj._to, str):
            target_table = getattr(fobj._to, "__tablename__", "")
        relationships.append(ModelInspectorRelationship(
            field_name=fname,
            kind="fk",
            target_model=target,
            target_table=target_table,
            on_delete=getattr(fobj, "on_delete", "CASCADE"),
            related_name=getattr(fobj, "related_name", None),
            nullable=getattr(fobj, "nullable", False),
        ))

    for fname, fobj in m2m_fields.items():
        target = fobj._to if isinstance(fobj._to, str) else fobj._to.__name__
        target_table = ""
        if not isinstance(fobj._to, str):
            target_table = getattr(fobj._to, "__tablename__", "")
        through = getattr(fobj, "through_table", None)
        relationships.append(ModelInspectorRelationship(
            field_name=fname,
            kind="m2m",
            target_model=target,
            target_table=target_table,
            through_table=through,
            related_name=getattr(fobj, "related_name", None),
        ))

    # --- Constraints ---
    constraints: List[ModelInspectorConstraint] = []
    for f in inspector_fields:
        if f.primary_key:
            constraints.append(ModelInspectorConstraint(
                kind="primary_key",
                columns=[f.column_name],
                name=f"pk_{table_name}_{f.column_name}",
                description=f"Primary key on {f.column_name}",
            ))
        if f.unique and not f.primary_key:
            constraints.append(ModelInspectorConstraint(
                kind="unique",
                columns=[f.column_name],
                name=f"uq_{table_name}_{f.column_name}",
                description=f"Unique constraint on {f.column_name}",
            ))
    # FK constraints
    for rel in relationships:
        if rel.kind == "fk":
            col = f"{rel.field_name}_id"
            constraints.append(ModelInspectorConstraint(
                kind="index",
                columns=[col],
                name=f"ix_{table_name}_{col}",
                description=f"Foreign key index on {col} → {rel.target_model}",
            ))

    # --- Timestamps ---
    field_names = set(fields_dict.keys())
    has_timestamps = "created_at" in field_names and "updated_at" in field_names

    # --- PK ---
    pk_field: Optional[str] = None
    pk_type = "IntegerField"
    for f in inspector_fields:
        if f.primary_key:
            pk_field = f.name
            pk_type = f.field_type
            break

    # --- CREATE TABLE SQL ---
    create_sql = ""
    try:
        create_sql = model.get_create_table_sql()
    except Exception:
        pass

    # --- Comments ---
    comments: List[str] = []
    if not inspector_fields:
        comments.append("⚠️ Model has no fields defined")
    if not pk_field:
        comments.append("⚠️ No explicit primary key detected")
    if has_timestamps:
        comments.append("✓ Timestamps (created_at, updated_at) detected")
    if relationships:
        fk_count = sum(1 for r in relationships if r.kind == "fk")
        m2m_count = sum(1 for r in relationships if r.kind == "m2m")
        parts = []
        if fk_count:
            parts.append(f"{fk_count} FK(s)")
        if m2m_count:
            parts.append(f"{m2m_count} M2M(s)")
        comments.append(f"Relations: {', '.join(parts)}")
    if any(f.ai_sensitive for f in inspector_fields):
        comments.append("⚠️ Has sensitive fields — AI agents should not expose raw values")
    if not ai_exposed:
        comments.append("🔒 Not exposed to AI agents")

    return ModelInspectorSummary(
        name=name,
        table_name=table_name,
        app_label=app_label,
        num_fields=len(inspector_fields),
        num_relationships=len(relationships),
        has_timestamps=has_timestamps,
        pk_field=pk_field,
        pk_type=pk_type,
        fields=inspector_fields,
        relationships=relationships,
        constraints=constraints,
        ai_description=ai_desc,
        ai_agent_exposed=ai_exposed,
        create_table_sql=create_sql,
        comments=comments,
    )


def inspect_all_models() -> List[ModelInspectorSummary]:
    """
    Inspect every model in the ModelRegistry.

    Returns:
        List of ModelInspectorSummary for all registered models,
        sorted by model name.
    """
    from aksara.registry import ModelRegistry

    results: List[ModelInspectorSummary] = []
    for _name, model_cls in sorted(ModelRegistry.all().items()):
        try:
            results.append(inspect_model(model_cls))
        except Exception:
            pass
    return results
