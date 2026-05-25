"""
Aksara Migration Operations

Defines all operation classes for schema changes:
- Field operations (UUIDField, StringField, etc.) for SQL generation
- Table operations (CreateTable, DropTable)
- Column operations (AddField, RemoveField, AlterFieldType)
- Index operations (AddIndex, RemoveIndex)
- Raw SQL escape hatch (RunSQL)

NOTE:
These are migration-time field definitions/operations.
They are separate from runtime fields in aksara.fields, but conceptually aligned.
Keep them in sync when adding new field types or options.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# =============================================================================
# Security: SQL Identifier Quoting
# =============================================================================

# Valid FK referential actions
_VALID_FK_ACTIONS = frozenset({
    "CASCADE", "SET NULL", "SET DEFAULT", "RESTRICT", "NO ACTION",
})


def _quote_ident(name: str) -> str:
    """
    Safely quote a SQL identifier by escaping embedded double quotes.

    PostgreSQL identifier quoting: wrap in double quotes and double
    any embedded ``"`` characters.  This prevents SQL injection via
    table/column/index names supplied to DDL operations.
    """
    return '"' + name.replace('"', '""') + '"'


def _validate_fk_action(action: str) -> str:
    """
    Validate a foreign-key referential action against an allowlist.

    Raises ValueError if the action is not a recognised PostgreSQL
    referential action keyword.
    """
    normalised = action.strip().upper()
    if normalised not in _VALID_FK_ACTIONS:
        raise ValueError(
            f"Invalid FK action: {action!r}. "
            f"Allowed: {', '.join(sorted(_VALID_FK_ACTIONS))}"
        )
    return normalised


def _make_constraint_name(*parts: str, max_length: int = 63) -> str:
    """Build a deterministic PostgreSQL-safe constraint identifier.

    Joins *parts* with underscores.  If the result is within *max_length*
    bytes it is returned as-is.  When it exceeds the limit the name is
    truncated to leave room for an 8-character stable hash suffix so that:

      * The result is always <= *max_length* characters.
      * Different long names produce different constraint names (no silent
        collision).
      * The output is deterministic across runs.

    Callers must pass the result through ``_quote_ident()`` before embedding
    in SQL.
    """
    full = "_".join(p for p in parts if p)
    if len(full) <= max_length:
        return full
    # Hash the full name for a stable suffix; use first 8 hex chars.
    suffix = hashlib.sha256(full.encode()).hexdigest()[:8]
    # Trim to make room: max_length - 1 underscore - 8 hash chars
    prefix = full[: max_length - 9]
    return f"{prefix}_{suffix}"


# DDL/DML keywords that must never appear in a partial-index predicate.
_UNSAFE_PREDICATE_KEYWORDS = frozenset({
    "DROP", "ALTER", "DELETE", "INSERT", "UPDATE", "CREATE",
    "TRUNCATE", "GRANT", "REVOKE", "EXECUTE", "CALL", "COPY",
})


def _validate_sql_predicate(predicate: str, *, context: str = "SQL predicate") -> str:
    """Validate a developer-authored SQL predicate (e.g. for a partial index).

    Does **not** attempt to fully parse SQL — only rejects the most obvious
    multi-statement and DDL/DML patterns that have no place in a WHERE clause:

      * Semicolons (``;``).
      * Line comments (``--``).
      * Block comments (``/* … */``).
      * DDL/DML keywords (DROP, ALTER, DELETE, INSERT, UPDATE, CREATE,
        TRUNCATE, GRANT, REVOKE, EXECUTE, CALL, COPY).

    Returns *predicate* unchanged when it looks safe.
    Raises ``ValueError`` with a clear message otherwise.
    """
    if not isinstance(predicate, str):
        raise ValueError(f"Unsafe {context}: must be a string, got {type(predicate).__name__!r}")
    if ";" in predicate:
        raise ValueError(f"Unsafe {context} for partial index: semicolons are not allowed.")
    if "--" in predicate:
        raise ValueError(f"Unsafe {context} for partial index: line comments (--) are not allowed.")
    if "/*" in predicate or "*/" in predicate:
        raise ValueError(f"Unsafe {context} for partial index: block comments are not allowed.")
    # Word-boundary keyword check — case-insensitive
    upper = predicate.upper()
    for kw in _UNSAFE_PREDICATE_KEYWORDS:
        # Match whole-word only to avoid rejecting 'created_at' for CREATE etc.
        if re.search(rf"\b{re.escape(kw)}\b", upper):
            raise ValueError(
                f"Unsafe {context} for partial index: keyword {kw!r} is not allowed in predicates."
            )
    return predicate


# Allowed PostgreSQL base types for array columns.
# Normalised to uppercase; matched after stripping the trailing [] and optional
# length specifier (e.g. VARCHAR(255)).
_ALLOWED_ARRAY_BASE_TYPES = frozenset({
    "TEXT", "INTEGER", "INT", "BIGINT", "SMALLINT",
    "DOUBLE PRECISION", "REAL", "FLOAT",
    "BOOLEAN", "UUID",
    "DATE", "TIMESTAMP", "TIMESTAMPTZ",
    "TIMESTAMP WITH TIME ZONE", "TIMESTAMP WITHOUT TIME ZONE",
    "JSONB", "JSON",
    "NUMERIC", "DECIMAL",
    "VARCHAR", "CHARACTER VARYING",
})

# Patterns that are never safe inside a sql_type value.
_UNSAFE_SQL_TYPE_RE = re.compile(r";|--|/\*|\*/|'|\"")
_UNSAFE_SQL_TYPE_KEYWORDS = frozenset({
    "DROP", "ALTER", "DELETE", "INSERT", "UPDATE", "CREATE",
    "TRUNCATE", "GRANT", "REVOKE", "EXECUTE", "CALL", "COPY", "SELECT",
})


def _validate_array_sql_type(sql_type: str) -> str:
    """Validate and normalise an ArrayField sql_type value.

    Requirements:
      * Must be a non-empty string.
      * Must end with ``[]`` (case-insensitive normalised to uppercase).
      * Base type (everything before the final ``[]``) must be on the allowed
        list after stripping an optional ``(length)`` specifier.
      * Must not contain semicolons, comments, quotes, or DDL/DML keywords.

    Returns the normalised (uppercased) sql_type string.
    Raises ``ValueError`` on violation.
    """
    if not isinstance(sql_type, str) or not sql_type.strip():
        raise ValueError(
            f"ArrayField sql_type must be a non-empty string; got {sql_type!r}"
        )
    upper = sql_type.strip().upper()
    # Reject inline injection patterns
    if _UNSAFE_SQL_TYPE_RE.search(sql_type):
        raise ValueError(
            f"ArrayField sql_type contains unsafe characters: {sql_type!r}"
        )
    # Keyword check
    for kw in _UNSAFE_SQL_TYPE_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", upper):
            raise ValueError(
                f"ArrayField sql_type contains disallowed keyword {kw!r}: {sql_type!r}"
            )
    # Must end with []
    if not upper.endswith("[]"):
        raise ValueError(
            f"ArrayField sql_type must end with '[]', got {sql_type!r}"
        )
    # Strip [] and optional (length) to get the base type
    base = upper[:-2].strip()
    # Allow optional length specifier like VARCHAR(255)
    base_no_len = re.sub(r"\(\d+\)$", "", base).strip()
    if base_no_len not in _ALLOWED_ARRAY_BASE_TYPES:
        raise ValueError(
            f"ArrayField sql_type has unknown base type {base_no_len!r}. "
            f"Allowed base types: {', '.join(sorted(_ALLOWED_ARRAY_BASE_TYPES))}"
        )
    return upper


def _escape_sql_string(value: str) -> str:
    """Escape a SQL string literal for inline DDL defaults."""
    return value.replace("'", "''")


def _format_jsonb_default(value: Any) -> str:
    """Format a Python value as a JSONB default literal."""
    payload = json.dumps(value)
    return f"'{_escape_sql_string(payload)}'::jsonb"


def _format_array_default(value: Any, sql_type: str) -> str:
    """Format a Python sequence as a PostgreSQL array default literal."""
    if not isinstance(value, (list, tuple)):
        return f"'{_escape_sql_string(str(value))}'"

    if not value:
        return f"'{{}}'::{sql_type}"

    base_type = sql_type[:-2].upper() if sql_type.endswith("[]") else sql_type.upper()
    formatted_items = []
    for item in value:
        if item is None:
            formatted_items.append("NULL")
        elif base_type in {"TEXT", "UUID"}:
            formatted_items.append(f"'{_escape_sql_string(str(item))}'")
        elif base_type == "BOOLEAN":
            formatted_items.append("TRUE" if item else "FALSE")
        else:
            formatted_items.append(str(item))

    return f"ARRAY[{','.join(formatted_items)}]::{sql_type}"


def _format_default_sql(value: Any, *, field_op: Any = None) -> str:
    """Format a Python default as a SQL literal consistent with the field type."""
    if value is None:
        return "NULL"

    field_kind = type(field_op).__name__ if field_op is not None else None

    if field_kind == "ArrayField":
        return _format_array_default(value, field_op.sql_type)

    # Structured defaults need explicit JSONB literals; plain str(value)
    # produces invalid SQL for JSON columns.
    if field_kind == "JSONField" or isinstance(value, (dict, list)):
        return _format_jsonb_default(value)

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"

    if isinstance(value, str):
        return f"'{_escape_sql_string(value)}'"

    if isinstance(value, (int, float)):
        return str(value)

    return str(value)


# =============================================================================
# Field Operations - For SQL Generation
# =============================================================================

class FieldOp(ABC):
    """
    Base class for field type definitions used in migrations.
    
    These are NOT the runtime Field classes from aksara.fields.
    They are lightweight representations for SQL generation in migrations.
    """
    
    @abstractmethod
    def to_sql(self) -> str:
        """Return the SQL column definition snippet."""
        raise NotImplementedError
    
    def get_default_sql(self) -> Optional[str]:
        """Return the DEFAULT clause if applicable."""
        return None


class UUIDField(FieldOp):
    """UUID field type for migrations."""
    
    def __init__(
        self,
        *,
        primary_key: bool = False,
        nullable: bool = False,
        unique: bool = False,
        default: Any = None,
    ):
        self.primary_key = primary_key
        self.nullable = nullable
        self.unique = unique
        self.default = default
    
    def to_sql(self) -> str:
        parts = ["UUID"]
        
        if self.primary_key:
            parts.append("PRIMARY KEY")
            parts.append("DEFAULT gen_random_uuid()")
        else:
            if not self.nullable:
                parts.append("NOT NULL")
            if self.unique:
                parts.append("UNIQUE")
            if self.default is not None:
                parts.append(f"DEFAULT '{_escape_sql_string(str(self.default))}'")
        
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return f"UUIDField(primary_key={self.primary_key})"


class StringField(FieldOp):
    """String/VARCHAR field type for migrations."""
    
    def __init__(
        self,
        max_length: int = 255,
        *,
        nullable: bool = False,
        unique: bool = False,
        default: Optional[str] = None,
    ):
        self.max_length = max_length
        self.nullable = nullable
        self.unique = unique
        self.default = default
    
    def to_sql(self) -> str:
        parts = [f"VARCHAR({self.max_length})"]
        
        if not self.nullable:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.default is not None:
            # Escape single quotes
            escaped = str(self.default).replace("'", "''")
            parts.append(f"DEFAULT '{escaped}'")
        
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return f"StringField(max_length={self.max_length})"


class TextField(FieldOp):
    """Text field type for migrations (unlimited length)."""
    
    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Optional[str] = None,
    ):
        self.nullable = nullable
        self.default = default
    
    def to_sql(self) -> str:
        parts = ["TEXT"]
        
        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            escaped = str(self.default).replace("'", "''")
            parts.append(f"DEFAULT '{escaped}'")
        
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return "TextField()"


class IntegerField(FieldOp):
    """Integer field type for migrations."""
    
    def __init__(
        self,
        *,
        nullable: bool = False,
        unique: bool = False,
        default: Optional[int] = None,
    ):
        self.nullable = nullable
        self.unique = unique
        self.default = default
    
    def to_sql(self) -> str:
        parts = ["INTEGER"]
        
        if not self.nullable:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.default is not None:
            parts.append(f"DEFAULT {self.default}")
        
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return "IntegerField()"


class BigIntegerField(FieldOp):
    """Big integer field type for migrations."""
    
    def __init__(
        self,
        *,
        nullable: bool = False,
        unique: bool = False,
        default: Optional[int] = None,
    ):
        self.nullable = nullable
        self.unique = unique
        self.default = default
    
    def to_sql(self) -> str:
        parts = ["BIGINT"]
        
        if not self.nullable:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.default is not None:
            parts.append(f"DEFAULT {self.default}")
        
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return "BigIntegerField()"


class BooleanField(FieldOp):
    """Boolean field type for migrations."""
    
    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Optional[bool] = None,
    ):
        self.nullable = nullable
        self.default = default
    
    def to_sql(self) -> str:
        parts = ["BOOLEAN"]
        
        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            parts.append(f"DEFAULT {'TRUE' if self.default else 'FALSE'}")
        
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return f"BooleanField(default={self.default})"


class DateTimeField(FieldOp):
    """DateTime field type for migrations."""
    
    def __init__(
        self,
        *,
        auto_now_add: bool = False,
        auto_now: bool = False,
        nullable: bool = False,
        default: Any = None,
    ):
        self.auto_now_add = auto_now_add
        self.auto_now = auto_now
        self.nullable = nullable
        self.default = default
    
    def to_sql(self) -> str:
        parts = ["TIMESTAMP WITH TIME ZONE"]
        
        if not self.nullable:
            parts.append("NOT NULL")
        
        if self.auto_now_add:
            parts.append("DEFAULT CURRENT_TIMESTAMP")
        elif self.default is not None:
            parts.append(f"DEFAULT '{_escape_sql_string(str(self.default))}'")
        
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return f"DateTimeField(auto_now_add={self.auto_now_add})"


class DateField(FieldOp):
    """Date field type for migrations."""
    
    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Any = None,
    ):
        self.nullable = nullable
        self.default = default
    
    def to_sql(self) -> str:
        parts = ["DATE"]
        
        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            parts.append(f"DEFAULT '{_escape_sql_string(str(self.default))}'")
        
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return "DateField()"


class JSONField(FieldOp):
    """JSON/JSONB field type for migrations."""
    
    def __init__(
        self,
        *,
        nullable: bool = True,
        default: Any = None,
    ):
        self.nullable = nullable
        self.default = default
    
    def to_sql(self) -> str:
        parts = ["JSONB"]
        
        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            parts.append(f"DEFAULT {_format_default_sql(self.default, field_op=self)}")
        
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return "JSONField()"


class ArrayField(FieldOp):
    """PostgreSQL array field type for migrations."""

    def __init__(
        self,
        sql_type: str = "TEXT[]",
        *,
        nullable: bool = True,
        default: Any = None,
    ):
        self.sql_type = _validate_array_sql_type(sql_type)
        self.nullable = nullable
        self.default = default

    def to_sql(self) -> str:
        parts = [self.sql_type]

        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            parts.append(f"DEFAULT {_format_default_sql(self.default, field_op=self)}")

        return " ".join(parts)

    def __repr__(self) -> str:
        return f"ArrayField(sql_type={self.sql_type!r})"


class VectorField(FieldOp):
    """pgvector field type for migrations."""

    def __init__(
        self,
        dimensions: Optional[int] = None,
        *,
        nullable: bool = False,
        default: Optional[Any] = None,
    ):
        self.dimensions = dimensions
        self.nullable = nullable
        self.default = default

    def to_sql(self) -> str:
        sql_type = "VECTOR" if self.dimensions is None else f"VECTOR({self.dimensions})"
        parts = [sql_type]

        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            if isinstance(self.default, (list, tuple)):
                default_literal = "[" + ",".join(format(float(item), "g") for item in self.default) + "]"
            else:
                default_literal = str(self.default)
            parts.append(f"DEFAULT '{default_literal}'::vector")

        return " ".join(parts)

    def __repr__(self) -> str:
        return f"VectorField(dimensions={self.dimensions!r})"


class FloatField(FieldOp):
    """Float/Double precision field type for migrations."""
    
    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Optional[float] = None,
    ):
        self.nullable = nullable
        self.default = default
    
    def to_sql(self) -> str:
        parts = ["DOUBLE PRECISION"]
        
        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            parts.append(f"DEFAULT {self.default}")
        
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return "FloatField()"


class DecimalField(FieldOp):
    """Decimal/Numeric field type for migrations."""
    
    def __init__(
        self,
        max_digits: int = 10,
        decimal_places: int = 2,
        *,
        nullable: bool = False,
        unique: bool = False,
        default: Optional[float] = None,
    ):
        self.max_digits = max_digits
        self.decimal_places = decimal_places
        self.nullable = nullable
        self.unique = unique
        self.default = default
    
    def to_sql(self) -> str:
        parts = [f"NUMERIC({self.max_digits}, {self.decimal_places})"]
        
        if not self.nullable:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.default is not None:
            parts.append(f"DEFAULT {self.default}")
        
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return f"DecimalField(max_digits={self.max_digits}, decimal_places={self.decimal_places})"


class EmailField(FieldOp):
    """Email field type for migrations (VARCHAR with format=email)."""
    
    def __init__(
        self,
        max_length: int = 254,
        *,
        nullable: bool = False,
        unique: bool = False,
        default: Optional[str] = None,
    ):
        self.max_length = max_length
        self.nullable = nullable
        self.unique = unique
        self.default = default
    
    def to_sql(self) -> str:
        parts = [f"VARCHAR({self.max_length})"]
        
        if not self.nullable:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.default is not None:
            escaped = str(self.default).replace("'", "''")
            parts.append(f"DEFAULT '{escaped}'")
        
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return f"EmailField(max_length={self.max_length})"


class FileField(FieldOp):
    """File field type for migrations (VARCHAR storing storage-relative paths)."""

    def __init__(
        self,
        max_length: int = 500,
        *,
        nullable: bool = False,
        unique: bool = False,
        default: Optional[str] = None,
    ):
        self.max_length = max_length
        self.nullable = nullable
        self.unique = unique
        self.default = default

    def to_sql(self) -> str:
        parts = [f"VARCHAR({self.max_length})"]

        if not self.nullable:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.default is not None:
            escaped = str(self.default).replace("'", "''")
            parts.append(f"DEFAULT '{escaped}'")

        return " ".join(parts)

    def __repr__(self) -> str:
        return f"FileField(max_length={self.max_length})"


class ImageField(FileField):
    """Image field type for migrations (same storage representation as FileField)."""

    def __repr__(self) -> str:
        return f"ImageField(max_length={self.max_length})"


class URLField(FieldOp):
    """URL field type for migrations (TEXT with format=uri)."""
    
    def __init__(
        self,
        *,
        nullable: bool = False,
        unique: bool = False,
        default: Optional[str] = None,
    ):
        self.nullable = nullable
        self.unique = unique
        self.default = default
    
    def to_sql(self) -> str:
        parts = ["TEXT"]
        
        if not self.nullable:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.default is not None:
            escaped = str(self.default).replace("'", "''")
            parts.append(f"DEFAULT '{escaped}'")
        
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return "URLField()"


class EnumField(FieldOp):
    """Enum field type for migrations (TEXT storing enum values)."""
    
    def __init__(
        self,
        allowed_values: Optional[list] = None,
        *,
        enum_name: Optional[str] = None,
        nullable: bool = False,
        default: Optional[str] = None,
    ):
        self.allowed_values = allowed_values or []
        self.enum_name = enum_name
        self.nullable = nullable
        self.default = default
    
    def to_sql(self) -> str:
        parts = ["TEXT"]
        
        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            escaped = str(self.default).replace("'", "''")
            parts.append(f"DEFAULT '{escaped}'")
        
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return f"EnumField(allowed_values={self.allowed_values})"


class OneToOneField(FieldOp):
    """One-to-one relationship field type for migrations (FK with unique)."""
    
    def __init__(
        self,
        to_table: str,
        to_column: str = "id",
        *,
        on_delete: str = "CASCADE",
        on_update: str = "CASCADE",
        nullable: bool = False,
        column_type: str = "UUID",
    ):
        self.to_table = to_table
        self.to_column = to_column
        self.on_delete = on_delete
        self.on_update = on_update
        self.nullable = nullable
        self.column_type = column_type
    
    def to_sql(self) -> str:
        parts = [self.column_type]
        
        if not self.nullable:
            parts.append("NOT NULL")
        parts.append("UNIQUE")
        
        return " ".join(parts)
    
    def get_constraint_sql(self, column_name: str, table_name: str = "") -> str:
        """Generate the FOREIGN KEY constraint SQL."""
        prefix = f"{table_name}_" if table_name else ""
        on_del = _validate_fk_action(self.on_delete)
        on_upd = _validate_fk_action(self.on_update)
        return (
            f"CONSTRAINT fk_{prefix}{column_name} "
            f"FOREIGN KEY ({column_name}) "
            f"REFERENCES {_quote_ident(self.to_table)}({self.to_column}) "
            f"ON DELETE {on_del} ON UPDATE {on_upd}"
        )
    
    def __repr__(self) -> str:
        return f"OneToOneField(to_table='{self.to_table}')"


class ManyToManyField(FieldOp):
    """
    Many-to-many relationship for migrations.
    
    Note: ManyToMany is a virtual field - it doesn't create a column,
    instead it creates a separate join table.
    """
    
    def __init__(
        self,
        source_table: str,
        target_table: str,
        field_name: str,
        *,
        source_column: str = "id",
        target_column: str = "id",
    ):
        self.source_table = source_table
        self.target_table = target_table
        self.field_name = field_name
        self.source_column = source_column
        self.target_column = target_column
    
    @property
    def join_table_name(self) -> str:
        """Return the name of the join table."""
        return f"{self.source_table}_{self.field_name}"
    
    def to_sql(self) -> str:
        """M2M doesn't create a column, returns empty."""
        return ""
    
    def get_join_table_sql(self) -> str:
        """Generate CREATE TABLE SQL for the join table."""
        jtn = _quote_ident(self.join_table_name)
        st = _quote_ident(self.source_table)
        tt = _quote_ident(self.target_table)
        src_constraint = _quote_ident(_make_constraint_name("fk", self.join_table_name, "source"))
        tgt_constraint = _quote_ident(_make_constraint_name("fk", self.join_table_name, "target"))
        src_col = _quote_ident(self.source_column)
        tgt_col = _quote_ident(self.target_column)
        return f'''CREATE TABLE IF NOT EXISTS {jtn} (
    "id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "source_id" UUID NOT NULL,
    "target_id" UUID NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT {src_constraint}
        FOREIGN KEY ("source_id") REFERENCES {st}({src_col}) ON DELETE CASCADE,
    CONSTRAINT {tgt_constraint}
        FOREIGN KEY ("target_id") REFERENCES {tt}({tgt_col}) ON DELETE CASCADE,
    UNIQUE ("source_id", "target_id")
)'''
    
    def get_drop_join_table_sql(self) -> str:
        """Generate DROP TABLE SQL for the join table."""
        return f'DROP TABLE IF EXISTS {_quote_ident(self.join_table_name)} CASCADE'
    
    def __repr__(self) -> str:
        return f"ManyToManyField(source='{self.source_table}', target='{self.target_table}')"


class ForeignKeyField(FieldOp):
    """Foreign key field type for migrations."""
    
    def __init__(
        self,
        to_table: str,
        to_column: str = "id",
        *,
        on_delete: str = "CASCADE",
        on_update: str = "CASCADE",
        nullable: bool = False,
        column_type: str = "UUID",
    ):
        self.to_table = to_table
        self.to_column = to_column
        self.on_delete = on_delete
        self.on_update = on_update
        self.nullable = nullable
        self.column_type = column_type
    
    def to_sql(self) -> str:
        parts = [self.column_type]
        
        if not self.nullable:
            parts.append("NOT NULL")
        
        # Note: The REFERENCES clause is added separately as a constraint
        return " ".join(parts)
    
    def get_constraint_sql(self, column_name: str, table_name: str = "") -> str:
        """Generate the FOREIGN KEY constraint SQL."""
        prefix = f"{table_name}_" if table_name else ""
        on_del = _validate_fk_action(self.on_delete)
        on_upd = _validate_fk_action(self.on_update)
        return (
            f"CONSTRAINT fk_{prefix}{column_name} "
            f"FOREIGN KEY ({column_name}) "
            f"REFERENCES {_quote_ident(self.to_table)}({self.to_column}) "
            f"ON DELETE {on_del} ON UPDATE {on_upd}"
        )
    
    def __repr__(self) -> str:
        return f"ForeignKeyField(to_table='{self.to_table}')"



# =============================================================================
# Extended Field Operations — Django parity
# =============================================================================


class SmallIntegerField(FieldOp):
    """Small integer field type for migrations."""

    def __init__(
        self,
        *,
        nullable: bool = False,
        unique: bool = False,
        default: Optional[int] = None,
    ):
        self.nullable = nullable
        self.unique = unique
        self.default = default

    def to_sql(self) -> str:
        parts = ["SMALLINT"]
        if not self.nullable:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.default is not None:
            parts.append(f"DEFAULT {self.default}")
        return " ".join(parts)

    def __repr__(self) -> str:
        return "SmallIntegerField()"


class SlugField(FieldOp):
    """Slug field type for migrations (VARCHAR)."""

    def __init__(
        self,
        max_length: int = 50,
        *,
        nullable: bool = False,
        unique: bool = False,
        default: Optional[str] = None,
    ):
        self.max_length = max_length
        self.nullable = nullable
        self.unique = unique
        self.default = default

    def to_sql(self) -> str:
        parts = [f"VARCHAR({self.max_length})"]
        if not self.nullable:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.default is not None:
            escaped = str(self.default).replace("'", "''")
            parts.append(f"DEFAULT '{escaped}'")
        return " ".join(parts)

    def __repr__(self) -> str:
        return f"SlugField(max_length={self.max_length})"


class TimeField(FieldOp):
    """Time field type for migrations."""

    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Any = None,
    ):
        self.nullable = nullable
        self.default = default

    def to_sql(self) -> str:
        parts = ["TIME"]
        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            parts.append(f"DEFAULT '{_escape_sql_string(str(self.default))}'")
        return " ".join(parts)

    def __repr__(self) -> str:
        return "TimeField()"


class DurationField(FieldOp):
    """Duration/Interval field type for migrations."""

    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Any = None,
    ):
        self.nullable = nullable
        self.default = default

    def to_sql(self) -> str:
        parts = ["INTERVAL"]
        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            parts.append(f"DEFAULT '{_escape_sql_string(str(self.default))}'")
        return " ".join(parts)

    def __repr__(self) -> str:
        return "DurationField()"


class IPAddressField(FieldOp):
    """IP address field type for migrations (INET)."""

    def __init__(
        self,
        *,
        nullable: bool = False,
        unique: bool = False,
        default: Optional[str] = None,
    ):
        self.nullable = nullable
        self.unique = unique
        self.default = default

    def to_sql(self) -> str:
        parts = ["INET"]
        if not self.nullable:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.default is not None:
            escaped = str(self.default).replace("'", "''")
            parts.append(f"DEFAULT '{escaped}'")
        return " ".join(parts)

    def __repr__(self) -> str:
        return "IPAddressField()"


class BinaryField(FieldOp):
    """Binary/BYTEA field type for migrations."""

    def __init__(
        self,
        *,
        nullable: bool = False,
    ):
        self.nullable = nullable

    def to_sql(self) -> str:
        parts = ["BYTEA"]
        if not self.nullable:
            parts.append("NOT NULL")
        return " ".join(parts)

    def __repr__(self) -> str:
        return "BinaryField()"


class FilePathField(FieldOp):
    """File path field type for migrations (VARCHAR)."""

    def __init__(
        self,
        max_length: int = 100,
        *,
        nullable: bool = False,
        unique: bool = False,
        default: Optional[str] = None,
    ):
        self.max_length = max_length
        self.nullable = nullable
        self.unique = unique
        self.default = default

    def to_sql(self) -> str:
        parts = [f"VARCHAR({self.max_length})"]
        if not self.nullable:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.default is not None:
            escaped = str(self.default).replace("'", "''")
            parts.append(f"DEFAULT '{escaped}'")
        return " ".join(parts)

    def __repr__(self) -> str:
        return f"FilePathField(max_length={self.max_length})"


# =============================================================================
# Index Operation
# =============================================================================

class IndexOp:
    """
    Index definition for migrations.
    
    Example:
        IndexOp(
            name="idx_users_email",
            table="users",
            columns=["email"],
            unique=True,
        )
    """
    
    def __init__(
        self,
        name: str,
        table: str,
        columns: List[str],
        *,
        unique: bool = False,
        where: Optional[str] = None,
        method: str = "btree",
    ):
        self.name = name
        self.table = table
        self.columns = columns
        self.unique = unique
        self.where = _validate_sql_predicate(where, context="IndexOp.where") if where is not None else None
        self.method = method
    
    def to_sql(self) -> str:
        """Generate CREATE INDEX SQL."""
        unique_str = "UNIQUE " if self.unique else ""
        cols = ", ".join(_quote_ident(c) for c in self.columns)
        sql = f'CREATE {unique_str}INDEX {_quote_ident(self.name)} ON {_quote_ident(self.table)} USING {self.method} ({cols})'
        
        if self.where:
            sql += f" WHERE {self.where}"
        
        return sql
    
    def __repr__(self) -> str:
        return f"IndexOp(name='{self.name}', table='{self.table}')"


# =============================================================================
# Base Operation Class
# =============================================================================

class Operation(ABC):
    """
    Base class for all schema operations.
    
    Subclasses must implement:
        - apply(connection): Execute the operation against the database
    
    Optional:
        - state_forwards(state): Update in-memory state (for future use)
        - reverse(): Return the reverse operation (for rollbacks)
    """
    
    def state_forwards(self, state: Any) -> Any:
        """
        Update in-memory state representation.
        
        For v0.3.3, this is a no-op. Future versions may use this
        for schema diffing and auto-migration generation.
        """
        return state
    
    @abstractmethod
    async def apply(self, connection) -> None:
        """
        Apply this operation to the live database.
        
        Args:
            connection: Database connection (asyncpg connection or Aksara Database)
        """
        raise NotImplementedError
    
    def reverse(self) -> Optional["Operation"]:
        """
        Return the reverse of this operation for rollbacks.
        
        Returns None if not reversible.
        """
        return None
    
    def describe(self) -> str:
        """Return a human-readable description of this operation."""
        return self.__class__.__name__


# =============================================================================
# Table Operations
# =============================================================================

class CreateTable(Operation):
    """
    Create a new database table.
    
    Example:
        CreateTable(
            name="users",
            fields=[
                ("id", UUIDField(primary_key=True)),
                ("email", StringField(unique=True)),
                ("is_active", BooleanField(default=True)),
                ("created_at", DateTimeField(auto_now_add=True)),
            ],
            indexes=[
                IndexOp(name="idx_users_email", table="users", columns=["email"]),
            ],
        )
    """
    
    def __init__(
        self,
        name: str,
        fields: List[Tuple[str, FieldOp]],
        *,
        indexes: Optional[List[IndexOp]] = None,
        if_not_exists: bool = True,
    ):
        self.name = name
        self.fields = fields
        self.indexes = indexes or []
        self.if_not_exists = if_not_exists
    
    async def apply(self, connection) -> None:
        """Create the table and any associated indexes."""
        # Build column definitions
        columns = []
        constraints = []
        
        for col_name, field in self.fields:
            columns.append(f'{_quote_ident(col_name)} {field.to_sql()}')
            
            # Handle ForeignKey and OneToOne constraints
            if isinstance(field, (ForeignKeyField, OneToOneField)):
                constraints.append(field.get_constraint_sql(col_name, self.name))
        
        # Build CREATE TABLE SQL
        all_parts = columns + constraints
        columns_sql = ",\n    ".join(all_parts)
        
        exists_clause = "IF NOT EXISTS " if self.if_not_exists else ""
        sql = f'CREATE TABLE {exists_clause}{_quote_ident(self.name)} (\n    {columns_sql}\n)'
        
        # Execute table creation
        if hasattr(connection, 'execute'):
            await connection.execute(sql)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
        
        # Create indexes
        for index in self.indexes:
            index_sql = index.to_sql()
            try:
                await connection.execute(index_sql)
            except Exception as e:
                # Index might already exist
                if "already exists" not in str(e).lower():
                    raise
    
    def reverse(self) -> "DropTable":
        """Return a DropTable operation to reverse this."""
        return DropTable(name=self.name)
    
    def describe(self) -> str:
        # Count only user-defined fields (exclude auto fields: id, created_at, updated_at)
        auto_fields = {"id", "created_at", "updated_at"}
        user_field_count = sum(1 for name, _ in self.fields if name not in auto_fields)
        return f"Create table '{self.name}' with {user_field_count} field(s)"
    
    def __repr__(self) -> str:
        return f"CreateTable(name='{self.name}')"


class CreateManyToManyTable(Operation):
    """
    Create a join table for ManyToMany relationships.
    
    Example:
        CreateManyToManyTable(
            source_table="articles",
            target_table="tags",
            field_name="tags",
        )
    """
    
    def __init__(
        self,
        source_table: str,
        target_table: str,
        field_name: str,
        *,
        source_column: str = "id",
        target_column: str = "id",
    ):
        self.source_table = source_table
        self.target_table = target_table
        self.field_name = field_name
        self.source_column = source_column
        self.target_column = target_column
    
    @property
    def join_table_name(self) -> str:
        return f"{self.source_table}_{self.field_name}"
    
    async def apply(self, connection) -> None:
        """Create the ManyToMany join table."""
        jtn = _quote_ident(self.join_table_name)
        st = _quote_ident(self.source_table)
        tt = _quote_ident(self.target_table)
        sql = f'''CREATE TABLE IF NOT EXISTS {jtn} (
    "id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "source_id" UUID NOT NULL,
    "target_id" UUID NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_{self.join_table_name}_source 
        FOREIGN KEY (source_id) REFERENCES {st}({self.source_column}) ON DELETE CASCADE,
    CONSTRAINT fk_{self.join_table_name}_target 
        FOREIGN KEY (target_id) REFERENCES {tt}({self.target_column}) ON DELETE CASCADE,
    UNIQUE (source_id, target_id)
)'''
        
        if hasattr(connection, 'execute'):
            await connection.execute(sql)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
    
    def reverse(self) -> "DropTable":
        """Return a DropTable operation to reverse this."""
        return DropTable(name=self.join_table_name, cascade=True)
    
    def describe(self) -> str:
        return f"Create ManyToMany join table '{self.join_table_name}'"
    
    def __repr__(self) -> str:
        return f"CreateManyToManyTable(source='{self.source_table}', target='{self.target_table}')"


class DropTable(Operation):
    """
    Drop a database table.
    
    Example:
        DropTable(name="old_users", cascade=True)
    """
    
    def __init__(
        self,
        name: str,
        *,
        if_exists: bool = True,
        cascade: bool = False,
    ):
        self.name = name
        self.if_exists = if_exists
        self.cascade = cascade
    
    async def apply(self, connection) -> None:
        """Drop the table."""
        exists_clause = "IF EXISTS " if self.if_exists else ""
        cascade_clause = " CASCADE" if self.cascade else ""
        sql = f'DROP TABLE {exists_clause}{_quote_ident(self.name)}{cascade_clause}'
        
        if hasattr(connection, 'execute'):
            await connection.execute(sql)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
    
    def describe(self) -> str:
        return f"Drop table '{self.name}'"
    
    def __repr__(self) -> str:
        return f"DropTable(name='{self.name}')"


class RenameTable(Operation):
    """
    Rename a database table.
    
    Example:
        RenameTable(old_name="users", new_name="accounts")
    """
    
    def __init__(self, old_name: str, new_name: str):
        self.old_name = old_name
        self.new_name = new_name
    
    async def apply(self, connection) -> None:
        """Rename the table."""
        sql = f'ALTER TABLE {_quote_ident(self.old_name)} RENAME TO {_quote_ident(self.new_name)}'
        
        if hasattr(connection, 'execute'):
            await connection.execute(sql)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
    
    def reverse(self) -> "RenameTable":
        """Return the reverse rename operation."""
        return RenameTable(old_name=self.new_name, new_name=self.old_name)
    
    def describe(self) -> str:
        return f"Rename table '{self.old_name}' to '{self.new_name}'"
    
    def __repr__(self) -> str:
        return f"RenameTable(old_name='{self.old_name}', new_name='{self.new_name}')"


# =============================================================================
# Column Operations
# =============================================================================

class AddField(Operation):
    """
    Add a column to an existing table.
    
    Example:
        AddField(
            table="users",
            name="phone",
            field=StringField(max_length=20, nullable=True),
        )
    """
    
    def __init__(
        self,
        table: str,
        name: str,
        field: FieldOp,
    ):
        self.table = table
        self.name = name
        self.field = field
    
    async def apply(self, connection) -> None:
        """Add the column to the table."""
        sql = f'ALTER TABLE {_quote_ident(self.table)} ADD COLUMN {_quote_ident(self.name)} {self.field.to_sql()}'
        
        if hasattr(connection, 'execute'):
            await connection.execute(sql)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
        
        # Handle ForeignKey/OneToOne constraints as a separate statement
        if isinstance(self.field, (ForeignKeyField, OneToOneField)):
            constraint_sql = self.field.get_constraint_sql(self.name, self.table)
            constraint_stmt = f'ALTER TABLE {_quote_ident(self.table)} ADD {constraint_sql}'
            await connection.execute(constraint_stmt)
    
    def reverse(self) -> "RemoveField":
        """Return a RemoveField operation to reverse this."""
        return RemoveField(table=self.table, name=self.name)
    
    def describe(self) -> str:
        return f"Add field '{self.name}' to table '{self.table}'"
    
    def __repr__(self) -> str:
        return f"AddField(table='{self.table}', name='{self.name}')"


class RemoveField(Operation):
    """
    Remove a column from a table.
    
    Example:
        RemoveField(table="users", name="deprecated_field")
    """
    
    def __init__(
        self,
        table: str,
        name: str,
        *,
        if_exists: bool = True,
    ):
        self.table = table
        self.name = name
        self.if_exists = if_exists
    
    async def apply(self, connection) -> None:
        """Remove the column from the table."""
        exists_clause = "IF EXISTS " if self.if_exists else ""
        sql = f'ALTER TABLE {_quote_ident(self.table)} DROP COLUMN {exists_clause}{_quote_ident(self.name)}'
        
        if hasattr(connection, 'execute'):
            await connection.execute(sql)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
    
    def describe(self) -> str:
        return f"Remove field '{self.name}' from table '{self.table}'"
    
    def __repr__(self) -> str:
        return f"RemoveField(table='{self.table}', name='{self.name}')"


class AlterFieldType(Operation):
    """
    Change a column's type.
    
    Example:
        AlterFieldType(
            table="users",
            name="age",
            new_field=BigIntegerField(),
        )
    """
    
    def __init__(
        self,
        table: str,
        name: str,
        new_field: FieldOp,
        *,
        using: Optional[str] = None,
    ):
        self.table = table
        self.name = name
        self.new_field = new_field
        self.using = using  # USING clause for type conversion
    
    async def apply(self, connection) -> None:
        """Alter the column type."""
        # Extract the SQL type, stripping constraint keywords like NOT NULL, UNIQUE, DEFAULT etc.
        full_sql = self.new_field.to_sql()
        # Find the earliest constraint keyword and truncate there
        type_sql = full_sql
        constraint_keywords = ('NOT NULL', 'UNIQUE', 'DEFAULT ', 'PRIMARY KEY', 'REFERENCES ')
        min_idx = len(type_sql)
        for keyword in constraint_keywords:
            idx = type_sql.upper().find(keyword)
            if idx > 0 and idx < min_idx:
                min_idx = idx
        if min_idx < len(type_sql):
            type_sql = type_sql[:min_idx].strip()
        
        using_clause = f" USING {self.using}" if self.using else ""
        sql = f'ALTER TABLE {_quote_ident(self.table)} ALTER COLUMN {_quote_ident(self.name)} TYPE {type_sql}{using_clause}'
        
        if hasattr(connection, 'execute'):
            await connection.execute(sql)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
    
    def describe(self) -> str:
        return f"Alter type of field '{self.name}' in table '{self.table}'"
    
    def __repr__(self) -> str:
        return f"AlterFieldType(table='{self.table}', name='{self.name}')"


class RenameField(Operation):
    """
    Rename a column.
    
    Example:
        RenameField(table="users", old_name="username", new_name="user_name")
    """
    
    def __init__(
        self,
        table: str,
        old_name: str,
        new_name: str,
    ):
        self.table = table
        self.old_name = old_name
        self.new_name = new_name
    
    async def apply(self, connection) -> None:
        """Rename the column."""
        sql = f'ALTER TABLE {_quote_ident(self.table)} RENAME COLUMN {_quote_ident(self.old_name)} TO {_quote_ident(self.new_name)}'
        
        if hasattr(connection, 'execute'):
            await connection.execute(sql)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
    
    def reverse(self) -> "RenameField":
        """Return the reverse rename operation."""
        return RenameField(
            table=self.table,
            old_name=self.new_name,
            new_name=self.old_name,
        )
    
    def describe(self) -> str:
        return f"Rename field '{self.old_name}' to '{self.new_name}' in table '{self.table}'"
    
    def __repr__(self) -> str:
        return f"RenameField(table='{self.table}', old_name='{self.old_name}')"


class AlterFieldNull(Operation):
    """
    Change a column's nullability.
    
    Example:
        AlterFieldNull(table="users", name="phone", nullable=True)
    """
    
    def __init__(
        self,
        table: str,
        name: str,
        nullable: bool,
    ):
        self.table = table
        self.name = name
        self.nullable = nullable
    
    async def apply(self, connection) -> None:
        """Alter the column's nullability."""
        if self.nullable:
            sql = f'ALTER TABLE {_quote_ident(self.table)} ALTER COLUMN {_quote_ident(self.name)} DROP NOT NULL'
        else:
            sql = f'ALTER TABLE {_quote_ident(self.table)} ALTER COLUMN {_quote_ident(self.name)} SET NOT NULL'
        
        if hasattr(connection, 'execute'):
            await connection.execute(sql)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
    
    def reverse(self) -> "AlterFieldNull":
        """Return the reverse nullability change."""
        return AlterFieldNull(
            table=self.table,
            name=self.name,
            nullable=not self.nullable,
        )
    
    def describe(self) -> str:
        action = "nullable" if self.nullable else "non-nullable"
        return f"Make field '{self.name}' {action} in table '{self.table}'"
    
    def __repr__(self) -> str:
        return f"AlterFieldNull(table='{self.table}', name='{self.name}', nullable={self.nullable})"


class AlterFieldDefault(Operation):
    """
    Change or remove a column's default value.
    
    Example:
        AlterFieldDefault(table="users", name="is_active", new_default=True)
        AlterFieldDefault(table="users", name="is_active", drop_default=True)
    """
    
    def __init__(
        self,
        table: str,
        name: str,
        *,
        new_default: Any = None,
        field: Optional[FieldOp] = None,
        drop_default: bool = False,
    ):
        self.table = table
        self.name = name
        self.new_default = new_default
        self.field = field
        self.drop_default = drop_default
    
    async def apply(self, connection) -> None:
        """Alter the column's default value."""
        if self.drop_default:
            sql = f'ALTER TABLE {_quote_ident(self.table)} ALTER COLUMN {_quote_ident(self.name)} DROP DEFAULT'
        else:
            # Use field-aware formatting so structured defaults remain valid DDL.
            default_sql = _format_default_sql(self.new_default, field_op=self.field)
            
            sql = f'ALTER TABLE {_quote_ident(self.table)} ALTER COLUMN {_quote_ident(self.name)} SET DEFAULT {default_sql}'
        
        if hasattr(connection, 'execute'):
            await connection.execute(sql)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
    
    def describe(self) -> str:
        if self.drop_default:
            return f"Drop default from field '{self.name}' in table '{self.table}'"
        return f"Set default for field '{self.name}' in table '{self.table}'"
    
    def __repr__(self) -> str:
        return f"AlterFieldDefault(table='{self.table}', name='{self.name}')"


# =============================================================================
# Index Operations
# =============================================================================

class AddIndex(Operation):
    """
    Add an index to a table.
    
    Example:
        AddIndex(
            index=IndexOp(
                name="idx_users_email",
                table="users",
                columns=["email"],
                unique=True,
            )
        )
    """
    
    def __init__(
        self,
        index: IndexOp,
        *,
        concurrently: bool = False,
        if_not_exists: bool = True,
    ):
        self.index = index
        self.concurrently = concurrently
        self.if_not_exists = if_not_exists
    
    async def apply(self, connection) -> None:
        """Create the index."""
        sql = self.index.to_sql()
        
        # PostgreSQL syntax: CREATE INDEX [CONCURRENTLY] [IF NOT EXISTS] ...
        # Both must be inserted right after "INDEX " in the correct order.
        # We build the insert fragment and do a single replacement.
        insert_parts = []
        if self.concurrently:
            insert_parts.append("CONCURRENTLY")
        if self.if_not_exists:
            insert_parts.append("IF NOT EXISTS")
        if insert_parts:
            insert_str = " ".join(insert_parts) + " "
            sql = sql.replace("INDEX ", f"INDEX {insert_str}", 1)
        
        if hasattr(connection, 'execute'):
            try:
                await connection.execute(sql)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    raise
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
    
    def reverse(self) -> "RemoveIndex":
        """Return a RemoveIndex operation to reverse this."""
        return RemoveIndex(name=self.index.name, table=self.index.table)
    
    def describe(self) -> str:
        return f"Create index '{self.index.name}' on table '{self.index.table}'"
    
    def __repr__(self) -> str:
        return f"AddIndex(index={self.index!r})"


class RemoveIndex(Operation):
    """
    Remove an index from a table.
    
    Example:
        RemoveIndex(name="idx_users_email", table="users")
    """
    
    def __init__(
        self,
        name: str,
        table: str,
        *,
        if_exists: bool = True,
        concurrently: bool = False,
    ):
        self.name = name
        self.table = table
        self.if_exists = if_exists
        self.concurrently = concurrently
    
    async def apply(self, connection) -> None:
        """Drop the index."""
        exists_clause = "IF EXISTS " if self.if_exists else ""
        concurrent_clause = "CONCURRENTLY " if self.concurrently else ""
        sql = f'DROP INDEX {concurrent_clause}{exists_clause}{_quote_ident(self.name)}'
        
        if hasattr(connection, 'execute'):
            await connection.execute(sql)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
    
    def describe(self) -> str:
        return f"Drop index '{self.name}'"
    
    def __repr__(self) -> str:
        return f"RemoveIndex(name='{self.name}')"


# =============================================================================
# Constraint Operations
# =============================================================================

class AddConstraint(Operation):
    """
    Add a constraint to a table.
    
    Example:
        AddConstraint(
            table="users",
            name="check_age_positive",
            constraint_sql="CHECK (age >= 0)",
        )
    """
    
    def __init__(
        self,
        table: str,
        name: str,
        constraint_sql: str,
    ):
        self.table = table
        self.name = name
        self.constraint_sql = constraint_sql
    
    async def apply(self, connection) -> None:
        """Add the constraint."""
        sql = f'ALTER TABLE {_quote_ident(self.table)} ADD CONSTRAINT {_quote_ident(self.name)} {self.constraint_sql}'
        
        if hasattr(connection, 'execute'):
            await connection.execute(sql)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
    
    def reverse(self) -> "RemoveConstraint":
        """Return a RemoveConstraint operation to reverse this."""
        return RemoveConstraint(table=self.table, name=self.name)
    
    def describe(self) -> str:
        return f"Add constraint '{self.name}' to table '{self.table}'"
    
    def __repr__(self) -> str:
        return f"AddConstraint(table='{self.table}', name='{self.name}')"


def _is_missing_constraint_error(exc: Exception) -> bool:
    """Return True when *exc* indicates the constraint does not exist.

    Prefers SQLSTATE 42704 (undefined_object) which asyncpg exposes on the
    exception as ``exc.sqlstate``.  Falls back to English message matching only
    when sqlstate is not available (e.g. wrapped exceptions, future drivers).
    """
    sqlstate = getattr(exc, "sqlstate", None)
    if sqlstate is not None:
        return sqlstate == "42704"
    return "does not exist" in str(exc).lower()


class RemoveConstraint(Operation):
    """
    Remove a constraint from a table.

    Example:
        RemoveConstraint(table="users", name="check_age_positive")
    """

    def __init__(
        self,
        table: str,
        name: str,
        *,
        if_exists: bool = True,
    ):
        self.table = table
        self.name = name
        self.if_exists = if_exists

    async def apply(self, connection) -> None:
        """Drop the constraint."""
        # PostgreSQL doesn't support IF EXISTS for constraints directly
        sql = f'ALTER TABLE {_quote_ident(self.table)} DROP CONSTRAINT {_quote_ident(self.name)}'

        if hasattr(connection, 'execute'):
            try:
                await connection.execute(sql)
            except Exception as e:
                if self.if_exists and _is_missing_constraint_error(e):
                    pass  # Constraint absent — suppress when if_exists=True
                else:
                    raise
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
    
    def describe(self) -> str:
        return f"Remove constraint '{self.name}' from table '{self.table}'"
    
    def __repr__(self) -> str:
        return f"RemoveConstraint(table='{self.table}', name='{self.name}')"


# =============================================================================
# Raw SQL Escape Hatch
# =============================================================================

class RunSQL(Operation):
    """
    Execute raw SQL statements.
    
    This is an escape hatch for operations that can't be expressed
    with the structured operations. Use with caution!
    
    Example:
        RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS 'uuid-ossp'",
            reverse_sql="DROP EXTENSION IF EXISTS 'uuid-ossp'",
        )
        
        # For dangerous operations, set dangerous=True
        RunSQL(
            sql="TRUNCATE TABLE users",
            dangerous=True,
        )
    """
    
    # Keywords that indicate potentially dangerous operations
    DANGEROUS_KEYWORDS = [
        "DROP TABLE",
        "DROP DATABASE",
        "TRUNCATE",
        "DELETE FROM",
        "DROP SCHEMA",
    ]
    
    def __init__(
        self,
        sql: str,
        *,
        reverse_sql: Optional[str] = None,
        dangerous: bool = False,
    ):
        self.sql = sql
        self.reverse_sql = reverse_sql
        self.dangerous = dangerous
        
        # Auto-detect dangerous operations
        if not dangerous:
            upper_sql = sql.upper()
            for keyword in self.DANGEROUS_KEYWORDS:
                if keyword in upper_sql:
                    self.dangerous = True
                    break
    
    async def apply(self, connection) -> None:
        """Execute the raw SQL."""
        # Check for dangerous operations
        if self.dangerous:
            allow_dangerous = os.environ.get("AKSARA_ALLOW_DANGEROUS_MIGRATIONS", "").lower()
            if allow_dangerous not in ("1", "true", "yes"):
                raise RuntimeError(
                    f"DANGEROUS MIGRATION BLOCKED: {self.sql[:100]}... "
                    f"Set AKSARA_ALLOW_DANGEROUS_MIGRATIONS=1 to allow."
                )
            else:
                logger.warning(f"⚠️  Executing dangerous migration: {self.sql[:100]}...")
        
        if hasattr(connection, 'execute'):
            await connection.execute(self.sql)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
    
    def reverse(self) -> Optional["RunSQL"]:
        """Return the reverse SQL operation if available."""
        if self.reverse_sql:
            return RunSQL(sql=self.reverse_sql, reverse_sql=self.sql)
        return None
    
    def describe(self) -> str:
        preview = self.sql[:50] + "..." if len(self.sql) > 50 else self.sql
        return f"Run SQL: {preview}"
    
    def __repr__(self) -> str:
        return f"RunSQL(sql='{self.sql[:30]}...')"


# =============================================================================
# Utility Operations
# =============================================================================

class SeparateDatabaseAndState(Operation):
    """
    Run different operations for database vs state.
    
    Useful when you need to perform data migrations or
    when the database operation differs from state tracking.
    """
    
    def __init__(
        self,
        database_operations: List[Operation],
        state_operations: Optional[List[Operation]] = None,
    ):
        self.database_operations = database_operations
        self.state_operations = state_operations or []
    
    async def apply(self, connection) -> None:
        """Apply only the database operations."""
        for op in self.database_operations:
            await op.apply(connection)
    
    def state_forwards(self, state: Any) -> Any:
        """Apply only the state operations."""
        for op in self.state_operations:
            state = op.state_forwards(state)
        return state
    
    def describe(self) -> str:
        return f"Separate database/state: {len(self.database_operations)} db ops"
    
    def __repr__(self) -> str:
        return f"SeparateDatabaseAndState(db_ops={len(self.database_operations)})"


# =============================================================================
# Convenience aliases for migration files
# =============================================================================

# Re-export all operations for easy access via `operations.CreateTable`, etc.
__all__ = [
    # Field types
    "FieldOp",
    "UUIDField",
    "StringField",
    "TextField",
    "IntegerField",
    "BigIntegerField",
    "SmallIntegerField",
    "BooleanField",
    "DateTimeField",
    "DateField",
    "JSONField",
    "VectorField",
    "FloatField",
    "DecimalField",
    "ForeignKeyField",
    # v0.3.5: New field types
    "EmailField",
    "FileField",
    "ImageField",
    "URLField",
    "EnumField",
    "OneToOneField",
    "ManyToManyField",
    "ArrayField",
    # Extended field types (Django parity)
    "SlugField",
    "TimeField",
    "DurationField",
    "IPAddressField",
    "BinaryField",
    "FilePathField",
    # Index
    "IndexOp",
    # Base operation
    "Operation",
    # Table operations
    "CreateTable",
    "CreateManyToManyTable",
    "DropTable",
    "RenameTable",
    # Column operations
    "AddField",
    "RemoveField",
    "AlterFieldType",
    "RenameField",
    "AlterFieldNull",
    "AlterFieldDefault",
    # Index operations
    "AddIndex",
    "RemoveIndex",
    # Constraint operations
    "AddConstraint",
    "RemoveConstraint",
    # Raw SQL
    "RunSQL",
    # Utility
    "SeparateDatabaseAndState",
]
