"""
Aksara Field Types

Field definitions for model columns with PostgreSQL type mappings.

NOTE:
These are runtime model fields used by the ORM (Model, QuerySet, etc.).
Migration field operations live separately in aksara.migrations.operations.
If you change behavior or supported options here, check if migrations also need updates.
"""

from __future__ import annotations

import io
import json
import math
import os
import ipaddress
import re
import uuid as uuid_lib
from abc import ABC, abstractmethod
from datetime import date, datetime, time as py_time, timedelta
from decimal import Decimal as PyDecimal, InvalidOperation
from enum import Enum as PyEnum
from typing import Any, Optional, Type, Union, Callable, TYPE_CHECKING, List

if TYPE_CHECKING:
    from aksara.model.base import Model
    from aksara.relations import OnDelete as OnDeleteType

from aksara.i18n import normalize_datetime_for_storage, normalize_datetime_from_storage
from aksara.relations import normalize_on_delete
from aksara.storage import FieldFile, build_upload_name, get_default_storage, read_uploaded_content


# =============================================================================
# on_delete constants (Django-style API)
# =============================================================================
# NOTE:
# on_delete may be specified using these string constants (CASCADE, SET_NULL, etc.)
# or via the OnDelete enum in aksara.relations.
# Both are supported for now; the string form is friendlier for devs,
# while the enum provides stronger typing internally.
# =============================================================================

class OnDelete:
    """
    Delete behavior policies for FK and OneToOne relations.
    
    Use these constants for the on_delete parameter:
    
        author = ForeignKey(User, on_delete=CASCADE)
        owner = ForeignKey(User, on_delete=SET_NULL, nullable=True)
        parent = ForeignKey(Category, on_delete=RESTRICT)
    
    Values:
        CASCADE: Delete related objects when parent is deleted
        SET_NULL: Set FK to NULL when parent is deleted (requires nullable=True)
        RESTRICT: Prevent deletion if related objects exist
        PROTECT: Alias for RESTRICT
    """
    CASCADE = "CASCADE"
    SET_NULL = "SET NULL"
    RESTRICT = "RESTRICT"
    PROTECT = "RESTRICT"  # Alias


# Module-level exports for convenience (Django-style)
CASCADE = OnDelete.CASCADE
SET_NULL = OnDelete.SET_NULL
RESTRICT = OnDelete.RESTRICT
PROTECT = OnDelete.PROTECT


# Email validation regex (basic RFC-style check)
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

INTEGER_MIN = -(2**31)
INTEGER_MAX = 2**31 - 1
BIGINT_MIN = -(2**63)
BIGINT_MAX = 2**63 - 1
SMALLINT_MIN = -32_768
SMALLINT_MAX = 32_767
INTEGER_STRING_REGEX = re.compile(r"^[+-]?\d+$")

# URL validation regex (http/https only)
URL_REGEX = re.compile(
    r"^https?://[^\s/$.?#].[^\s]*$",
    re.IGNORECASE
)


def _singularize(table_name: str) -> str:
    """Convert a plural table name to singular form."""
    if table_name.endswith('ies') and len(table_name) > 3 and table_name[-4] not in 'aeiou':
        return table_name[:-3] + 'y'
    if table_name.endswith('ses') or table_name.endswith('xes') or table_name.endswith('zes'):
        return table_name[:-2]
    if table_name.endswith('ches') or table_name.endswith('shes'):
        return table_name[:-2]
    if table_name.endswith('s') and not table_name.endswith('ss'):
        return table_name[:-1]
    return table_name


class Field(ABC):
    """
    Base class for all field types.
    
    All fields support these common arguments:
        - nullable: Whether the field can be NULL (default: False)
        - default: Default value for the field
        - unique: Whether the field should have a UNIQUE constraint
        - primary_key: Whether this field is the primary key
        - db_index: Whether to create a database index on this field
        
    AI metadata arguments (v0.2):
        - ai_description: Human-readable description for AI agents
        - ai_sensitive: Whether this field contains sensitive data
        - ai_agent_writable: Whether AI agents can modify this field
    """
    
    # Counter for field ordering
    _creation_counter = 0
    
    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        primary_key: bool = False,
        db_index: bool = False,
        # AI metadata
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        self.nullable = nullable
        self.default = default
        self.unique = unique
        self.primary_key = primary_key
        self.db_index = db_index
        
        # AI metadata
        self.ai_description = ai_description
        self.ai_sensitive = ai_sensitive
        self.ai_agent_writable = ai_agent_writable
        
        # Track field name (set by Model metaclass)
        self.name: Optional[str] = None
        
        # Track creation order for consistent column ordering
        self._creation_order = Field._creation_counter
        Field._creation_counter += 1
    
    @property
    @abstractmethod
    def sql_type(self) -> str:
        """Return the PostgreSQL type for this field."""
        pass
    
    def get_column_definition(self) -> str:
        """Generate the SQL column definition."""
        parts = [self.name, self.sql_type]
        
        if self.primary_key:
            parts.append("PRIMARY KEY")
        
        if not self.nullable and not self.primary_key:
            parts.append("NOT NULL")
        
        if self.unique and not self.primary_key:
            parts.append("UNIQUE")
        
        if self.default is not None and not callable(self.default):
            parts.append(f"DEFAULT {self._format_default()}")
        
        return " ".join(parts)
    
    @property
    def column_name(self) -> str:
        """
        Get the actual database column name.
        
        For most fields, this is the same as self.name.
        ForeignKey overrides this to return {name}_id.
        """
        return self.name
    
    def _format_default(self) -> str:
        """Format the default value for SQL."""
        if self.default is None:
            return "NULL"
        if isinstance(self.default, bool):
            return "TRUE" if self.default else "FALSE"
        if isinstance(self.default, str):
            # Escape single quotes
            escaped = self.default.replace("'", "''")
            return f"'{escaped}'"
        if isinstance(self.default, (int, float)):
            return str(self.default)
        return str(self.default)
    
    def get_default_value(self) -> Any:
        """Get the default value, calling it if it's callable."""
        if callable(self.default):
            return self.default()
        return self.default
    
    def to_python(self, value: Any) -> Any:
        """Convert database value to Python type."""
        return value
    
    def to_db(self, value: Any) -> Any:
        """Convert Python value to database type."""
        return value

    async def async_prepare(self, value: Any, *, instance: Optional["Model"] = None) -> Any:
        """Prepare a value asynchronously before model persistence."""
        return value
    
    def get_ai_metadata(self) -> dict:
        """Get AI metadata for this field."""
        return {
            "name": self.name,
            "type": self.__class__.__name__,
            "sql_type": self.sql_type,
            "nullable": self.nullable,
            "unique": self.unique,
            "primary_key": self.primary_key,
            "description": self.ai_description,
            "sensitive": self.ai_sensitive,
            "agent_writable": self.ai_agent_writable,
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


def _normalize_choices(choices):
    """
    Normalize a choices list into (value, label) pairs.

    Accepts flat lists (``["a", "b"]``) and Django-style tuple-pair lists
    (``[("a", "Label A"), ("b", "Label B")]``).  Returns the set of valid
    values for fast membership testing.
    """
    if not choices:
        return None
    valid = set()
    for item in choices:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            valid.add(item[0])
        else:
            valid.add(item)
    return valid


def _slugify(value: str, *, allow_unicode: bool = False) -> str:
    """
    Convert a string into a URL-friendly slug.

    * Lowercases the value
    * Replaces non-alphanumeric characters with hyphens
    * Collapses consecutive hyphens
    * Strips leading/trailing hyphens

    When *allow_unicode* is ``False`` (the default) the value is
    transliterated to ASCII first via ``unicodedata.normalize('NFKD')``.
    """
    import unicodedata
    value = str(value).strip()
    if not allow_unicode:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = value.lower()
    value = re.sub(r'[^\w\s-]', '', value)
    value = re.sub(r'[-\s]+', '-', value)
    return value.strip('-_')


def _coerce_strict_integer(value: Any, field_name: str) -> int:
    """Coerce supported integer inputs without truncating fractional values."""
    if isinstance(value, bool):
        raise ValueError(f"{field_name} does not accept boolean values")

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        text = value.strip()
        if not INTEGER_STRING_REGEX.fullmatch(text):
            raise ValueError(
                f"{field_name} requires a base-10 integer string, got {value!r}"
            )
        return int(text, 10)

    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError(f"{field_name} requires an integral value, got {value!r}")
        return int(value)

    if isinstance(value, PyDecimal):
        if value.is_nan() or value.is_infinite() or value != value.to_integral_value():
            raise ValueError(f"{field_name} requires an integral value, got {value!r}")
        return int(value)

    raise ValueError(
        f"{field_name} requires an int, base-10 integer string, "
        "integral float, or integral Decimal"
    )


def _validate_integer_bounds(value: int, minimum: int, maximum: int, field_name: str) -> None:
    if not (minimum <= value <= maximum):
        raise ValueError(
            f"Value {value} is out of {field_name} range ({minimum}..{maximum})."
        )


def _coerce_strict_boolean(value: Any) -> bool:
    """Parse booleans from explicit true/false forms only."""
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        text = value.strip().lower()
        true_values = {"true", "1", "yes", "y", "on"}
        false_values = {"false", "0", "no", "n", "off"}
        if text in true_values:
            return True
        if text in false_values:
            return False
        raise ValueError(f"Boolean requires a strict true/false string, got {value!r}")

    if isinstance(value, (int, float, PyDecimal)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"Boolean numeric values must be 1 or 0, got {value!r}")
        if isinstance(value, PyDecimal) and (value.is_nan() or value.is_infinite()):
            raise ValueError(f"Boolean numeric values must be 1 or 0, got {value!r}")
        if value == 1:
            return True
        if value == 0:
            return False
        raise ValueError(f"Boolean numeric values must be 1 or 0, got {value!r}")

    raise ValueError(
        "Boolean requires bool, numeric 1/0, or a strict true/false string"
    )


class String(Field):
    """
    String field mapping to VARCHAR.
    
    Args:
        max_length: Maximum string length (default: 255)
        min_length: Minimum string length (default: None, no minimum)
        choices: Restrict values to this set. Accepts a flat list
            (["a", "b"]) or Django-style tuple pairs
            ([("a", "Label A"), ("b", "Label B")])
        regex: Regular expression pattern the value must match
        strip_whitespace: Strip leading/trailing whitespace on save
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    """

    _python_type = str

    def __init__(
        self,
        max_length: int = 255,
        *,
        min_length: Optional[int] = None,
        choices: Optional[list] = None,
        regex: Optional[str] = None,
        strip_whitespace: bool = False,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.max_length = max_length
        self.min_length = min_length
        self.choices = choices
        self._choices_valid = _normalize_choices(choices)
        self.strip_whitespace = strip_whitespace
        self.db_index = db_index
        self._regex_pattern = regex
        self._regex = re.compile(regex) if regex else None
    
    @property
    def sql_type(self) -> str:
        return f"VARCHAR({self.max_length})"
    
    def to_python(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)
    
    def to_db(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        v = str(value)
        if self.strip_whitespace:
            v = v.strip()
        if self.min_length is not None and len(v) < self.min_length:
            raise ValueError(
                f"String value is too short (minimum {self.min_length} characters, got {len(v)})"
            )
        # Enforce max_length before persistence so we raise a clear field
        # validation error instead of relying on Postgres VARCHAR(n) failures.
        if self.max_length is not None and len(v) > self.max_length:
            raise ValueError(
                f"String value is too long (maximum {self.max_length} characters, got {len(v)})"
            )
        if self._choices_valid is not None and v not in self._choices_valid:
            raise ValueError(
                f"Value {v!r} is not a valid choice. "
                f"Valid choices are: {sorted(self._choices_valid)}"
            )
        if self._regex is not None and not self._regex.fullmatch(v):
            raise ValueError(
                f"Value {v!r} does not match required pattern {self._regex_pattern!r}"
            )
        return v

    def get_ai_metadata(self) -> dict:
        """Get AI metadata with string-specific options."""
        base = super().get_ai_metadata()
        if self.min_length is not None:
            base["min_length"] = self.min_length
        if self.choices is not None:
            base["choices"] = self.choices
        if self._regex_pattern is not None:
            base["regex"] = self._regex_pattern
        return base


class Integer(Field):
    """
    Integer field mapping to INTEGER.
    
    Args:
        min_value: Minimum allowed value (default: None, no minimum)
        max_value: Maximum allowed value (default: None, no maximum)
        choices: Restrict values to this set
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    """
    
    def __init__(
        self,
        *,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        choices: Optional[list] = None,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.min_value = min_value
        self.max_value = max_value
        self.choices = choices
        self._choices_valid = _normalize_choices(choices)
        self.db_index = db_index
    
    @property
    def sql_type(self) -> str:
        return "INTEGER"
    
    def to_python(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        return _coerce_strict_integer(value, "Integer")
    
    def to_db(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        v = _coerce_strict_integer(value, "Integer")
        _validate_integer_bounds(v, INTEGER_MIN, INTEGER_MAX, "INTEGER")
        if self.min_value is not None and v < self.min_value:
            raise ValueError(
                f"Value {v} is below the minimum of {self.min_value}"
            )
        if self.max_value is not None and v > self.max_value:
            raise ValueError(
                f"Value {v} exceeds the maximum of {self.max_value}"
            )
        if self._choices_valid is not None and v not in self._choices_valid:
            raise ValueError(
                f"Value {v!r} is not a valid choice. "
                f"Valid choices are: {sorted(self._choices_valid)}"
            )
        return v

    def get_ai_metadata(self) -> dict:
        """Get AI metadata with integer-specific options."""
        base = super().get_ai_metadata()
        if self.min_value is not None:
            base["min_value"] = self.min_value
        if self.max_value is not None:
            base["max_value"] = self.max_value
        if self.choices is not None:
            base["choices"] = self.choices
        return base


class Boolean(Field):
    """
    Boolean field mapping to BOOLEAN.
    
    Args:
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    """
    
    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.db_index = db_index
    
    @property
    def sql_type(self) -> str:
        return "BOOLEAN"
    
    def to_python(self, value: Any) -> Optional[bool]:
        if value is None:
            return None
        return _coerce_strict_boolean(value)
    
    def to_db(self, value: Any) -> Optional[bool]:
        if value is None:
            return None
        return _coerce_strict_boolean(value)

    def validate(self, value: Any) -> bool:
        if value is None:
            if self.nullable:
                return None
            raise ValueError("Boolean cannot be null")
        return _coerce_strict_boolean(value)


class DateTime(Field):
    """
    DateTime field mapping to TIMESTAMP WITH TIME ZONE.
    
    Args:
        auto_now: Automatically set to current time on every save
        auto_now_add: Automatically set to current time on creation
        nullable: Whether the field can be NULL
        default: Default value (datetime or callable)
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    """
    
    def __init__(
        self,
        *,
        auto_now: bool = False,
        auto_now_add: bool = False,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.auto_now = auto_now
        self.auto_now_add = auto_now_add
        self.db_index = db_index
    
    @property
    def sql_type(self) -> str:
        return "TIMESTAMP WITH TIME ZONE"
    
    def get_column_definition(self) -> str:
        """Generate the SQL column definition with default for auto_now_add."""
        parts = [self.name, self.sql_type]
        
        if not self.nullable:
            parts.append("NOT NULL")
        
        if self.unique:
            parts.append("UNIQUE")
        
        if self.auto_now_add:
            parts.append("DEFAULT CURRENT_TIMESTAMP")
        elif self.default is not None and not callable(self.default):
            parts.append(f"DEFAULT {self._format_default()}")
        
        return " ".join(parts)
    
    def to_python(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        return normalize_datetime_from_storage(value)
    
    def to_db(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        normalized = normalize_datetime_for_storage(value)
        if isinstance(normalized, datetime):
            return normalized
        return value


class UUID(Field):
    """
    UUID field mapping to UUID type.
    
    Args:
        primary_key: Whether this is the primary key (default: False)
        nullable: Whether the field can be NULL
        default: Default value (use uuid.uuid4 for auto-generation)
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    """
    
    def __init__(
        self,
        *,
        primary_key: bool = False,
        nullable: bool = False,
        default: Any = None,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        # If primary_key and no default, auto-generate UUIDs
        if primary_key and default is None:
            default = uuid_lib.uuid4
        super().__init__(
            primary_key=primary_key,
            nullable=nullable,
            default=default,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
    
    @property
    def sql_type(self) -> str:
        return "UUID"
    
    def get_column_definition(self) -> str:
        """Generate the SQL column definition."""
        parts = [self.name, self.sql_type]
        
        if self.primary_key:
            parts.append("PRIMARY KEY")
            parts.append("DEFAULT gen_random_uuid()")
        else:
            if not self.nullable:
                parts.append("NOT NULL")
            if self.unique:
                parts.append("UNIQUE")
        
        return " ".join(parts)
    
    def to_python(self, value: Any) -> Optional[uuid_lib.UUID]:
        if value is None:
            return None
        if isinstance(value, uuid_lib.UUID):
            return value
        return uuid_lib.UUID(str(value))
    
    def to_db(self, value: Any) -> Optional[uuid_lib.UUID]:
        if value is None:
            return None
        if isinstance(value, uuid_lib.UUID):
            return value
        return uuid_lib.UUID(str(value))


class JSON(Field):
    """
    JSON field mapping to JSONB.
    
    Args:
        nullable: Whether the field can be NULL
        default: Default value (can be dict, list, or callable)
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    """
    
    def __init__(
        self,
        *,
        nullable: bool = True,
        default: Any = None,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
    
    @property
    def sql_type(self) -> str:
        return "JSONB"
    
    def _format_default(self) -> str:
        """Format the default value for SQL."""
        if self.default is None:
            return "NULL"
        if isinstance(self.default, (dict, list)):
            return f"'{json.dumps(self.default)}'::jsonb"
        return "NULL"
    
    def to_python(self, value: Any) -> Any:
        """JSONB is automatically parsed by asyncpg."""
        if value is None:
            return None
        # asyncpg returns dict/list directly from JSONB
        if isinstance(value, str):
            return json.loads(value)
        return value
    
    def to_db(self, value: Any) -> Any:
        """Serialize to JSON string for asyncpg."""
        if value is None:
            return None
        # asyncpg expects a JSON string for JSONB columns
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return value


class Vector(Field):
    """
    pgvector-backed embedding field.

    Stores numeric embeddings using PostgreSQL's optional `vector` extension.
    """

    def __init__(
        self,
        dimensions: Optional[int] = None,
        *,
        nullable: bool = False,
        default: Any = None,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.dimensions = dimensions

    @property
    def sql_type(self) -> str:
        if self.dimensions is None:
            return "VECTOR"
        return f"VECTOR({self.dimensions})"

    def _format_default(self) -> str:
        """Format vector defaults with an explicit pgvector cast."""
        if self.default is None:
            return "NULL"
        return f"'{self.to_db(self.default)}'::vector"

    def validate(self, value: Any) -> list[float]:
        if isinstance(value, str):
            value = self.to_python(value)

        if not isinstance(value, (list, tuple)):
            raise ValueError("Vector fields require a list or tuple of numbers")

        vector = [float(item) for item in value]
        if self.dimensions is not None and len(vector) != self.dimensions:
            raise ValueError(
                f"Vector field '{self.name}' requires {self.dimensions} dimensions, got {len(vector)}"
            )

        for item in vector:
            if not math.isfinite(item):
                raise ValueError("Vector fields only support finite numbers")

        return vector

    def to_python(self, value: Any) -> Optional[list[float]]:
        if value is None:
            return None
        if isinstance(value, list):
            return [float(item) for item in value]
        if isinstance(value, tuple):
            return [float(item) for item in value]
        if isinstance(value, str):
            stripped = value.strip().strip("[]")
            if not stripped:
                return []
            return [float(part.strip()) for part in stripped.split(",") if part.strip()]
        return self.validate(value)

    def to_db(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        vector = self.validate(value)
        return "[" + ",".join(format(item, "g") for item in vector) + "]"

    def get_ai_metadata(self) -> dict:
        base = super().get_ai_metadata()
        base["dimensions"] = self.dimensions
        return base


class Array(Field):
    """
    Array field mapping to PostgreSQL ARRAY type.
    
    Supports arrays of primitive types (text, integer, float, boolean, uuid).
    Use this for multi-valued fields like tags, labels, or lists.
    
    Args:
        item_type: Python type for array items (str, int, float, bool, uuid_lib.UUID)
        nullable: Whether the field can be NULL
        default: Default value (list or callable)
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
        
    Example:
        tags = Array(item_type=str)
        scores = Array(item_type=int)
        flags = Array(item_type=bool, default=list)
    """
    
    # Map Python types to PostgreSQL array types
    TYPE_MAP = {
        str: "TEXT[]",
        int: "INTEGER[]",
        float: "DOUBLE PRECISION[]",
        bool: "BOOLEAN[]",
        uuid_lib.UUID: "UUID[]",
    }
    
    def __init__(
        self,
        *,
        item_type: Type = str,
        nullable: bool = True,
        default: Any = None,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        self.item_type = item_type
        
        super().__init__(
            nullable=nullable,
            default=default,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
    
    @property
    def sql_type(self) -> str:
        """Return the PostgreSQL array type."""
        return self.TYPE_MAP.get(self.item_type, "TEXT[]")
    
    def _format_default(self) -> str:
        """Format the default value for SQL."""
        if self.default is None:
            return "NULL"
        if isinstance(self.default, list):
            # Format as PostgreSQL array literal
            if not self.default:
                return "'{}'"
            
            # Format items based on type
            if self.item_type == str:
                formatted_items = [f"'{item}'" if item else 'NULL' for item in self.default]
            elif self.item_type == bool:
                formatted_items = [str(item).upper() for item in self.default]
            else:
                formatted_items = [str(item) for item in self.default]
            
            return f"ARRAY[{','.join(formatted_items)}]"
        return "'{}'"
    
    def to_python(self, value: Any) -> Any:
        """Convert database array to Python list."""
        if value is None:
            return None
        # asyncpg returns lists directly from ARRAY columns
        if isinstance(value, list):
            return value
        # Handle string representation
        if isinstance(value, str):
            # Simple parsing for array strings like {1,2,3}
            if value.startswith('{') and value.endswith('}'):
                items = value[1:-1].split(',')
                if not items or items == ['']:
                    return []
                # Convert items based on type
                if self.item_type == int:
                    return [int(i.strip()) for i in items if i.strip()]
                elif self.item_type == float:
                    return [float(i.strip()) for i in items if i.strip()]
                elif self.item_type == bool:
                    return [i.strip().lower() == 'true' for i in items if i.strip()]
                else:
                    return [i.strip().strip('"') for i in items if i.strip()]
            return []
        return value
    
    def to_db(self, value: Any) -> Any:
        """Convert Python list to database array."""
        if value is None:
            return None
        # asyncpg handles Python lists directly for ARRAY columns
        if isinstance(value, list):
            return value
        # Handle comma-separated strings
        if isinstance(value, str):
            if not value.strip():
                return []
            # Split by comma and convert types
            items = [item.strip() for item in value.split(',')]
            if self.item_type == int:
                return [int(i) for i in items if i]
            elif self.item_type == float:
                return [float(i) for i in items if i]
            elif self.item_type == bool:
                return [i.lower() in ('true', '1', 'yes') for i in items if i]
            else:
                return items
        return value


# Convenience aliases
StringField = String
IntegerField = Integer
BooleanField = Boolean
DateTimeField = DateTime
UUIDField = UUID
JSONField = JSON
VectorField = Vector
ArrayField = Array


# =============================================================================
# v0.3.5: New Field Types
# =============================================================================


class Text(Field):
    """
    Text field mapping to TEXT (unlimited length string).
    
    Use this for long-form text content instead of String when you don't
    need a maximum length constraint. If max_length is provided, validation
    will enforce it but the database column remains TEXT.
    
    Args:
        max_length: Optional max length for validation (DB stays TEXT)
        min_length: Minimum string length (default: None, no minimum)
        strip_whitespace: Strip leading/trailing whitespace on save
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    """
    
    def __init__(
        self,
        max_length: Optional[int] = None,
        *,
        min_length: Optional[int] = None,
        strip_whitespace: bool = False,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.max_length = max_length
        self.min_length = min_length
        self.strip_whitespace = strip_whitespace
        self.db_index = db_index
    
    @property
    def sql_type(self) -> str:
        return "TEXT"
    
    def to_python(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)
    
    def to_db(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        s = str(value)
        if self.strip_whitespace:
            s = s.strip()
        if self.min_length is not None and len(s) < self.min_length:
            raise ValueError(
                f"Text value is too short (minimum {self.min_length} characters, got {len(s)})"
            )
        if self.max_length is not None and len(s) > self.max_length:
            raise ValueError(
                f"Text value exceeds maximum length of {self.max_length}"
            )
        return s

    def get_ai_metadata(self) -> dict:
        """Get AI metadata with text-specific options."""
        base = super().get_ai_metadata()
        if self.min_length is not None:
            base["min_length"] = self.min_length
        return base


class FileField(Field):
    """
    File field that stores a storage-relative file path in PostgreSQL.

    Accessing the field on a model instance returns a FieldFile wrapper with
    helpers for reading, sizing, and URL generation.
    """

    def __init__(
        self,
        max_length: int = 500,
        *,
        upload_to: Any = "",
        storage: Any = None,
        allowed_extensions: Optional[List[str]] = None,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            db_index=db_index,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.max_length = max_length
        self.upload_to = upload_to
        self.storage = storage
        self.allowed_extensions = {
            extension.lower().lstrip(".")
            for extension in (allowed_extensions or [])
            if extension
        } or None

    @property
    def sql_type(self) -> str:
        return f"VARCHAR({self.max_length})"

    def get_storage(self):
        """Return the field-specific or global storage backend."""
        if self.storage is not None:
            return self.storage
        return get_default_storage()

    def to_field_file(self, value: Any, *, instance: Optional["Model"] = None) -> FieldFile:
        """Wrap a stored path in a FieldFile helper object."""
        if isinstance(value, FieldFile):
            return value
        return FieldFile(instance=instance, field=self, name=value)

    def _normalize_name(self, name: Any) -> str:
        normalized = str(name or "").strip().replace("\\", "/")
        normalized = normalized.lstrip("/")
        if not normalized:
            raise ValueError("File name cannot be empty")
        if len(normalized) > self.max_length:
            raise ValueError(f"File path exceeds maximum length of {self.max_length}")
        return normalized

    def _validate_extension(self, name: str) -> None:
        if not self.allowed_extensions:
            return
        extension = os.path.splitext(name)[1].lstrip(".").lower()
        if extension not in self.allowed_extensions:
            allowed = ", ".join(sorted(self.allowed_extensions))
            raise ValueError(f"Invalid file extension for '{name}'. Allowed: {allowed}")

    def validate(self, value: Any) -> Any:
        """Validate stored file references or upload-like inputs."""
        if value is None:
            if self.nullable:
                return None
            raise ValueError("File cannot be null")

        if isinstance(value, FieldFile):
            value = value.name

        if isinstance(value, tuple):
            if len(value) != 2:
                raise ValueError("File uploads must be provided as (name, content)")
            upload_name = self._normalize_name(value[0])
            self._validate_extension(upload_name)
            return value

        filename = getattr(value, "filename", None)
        if filename:
            upload_name = self._normalize_name(filename)
            self._validate_extension(upload_name)
            return value

        if isinstance(value, (bytes, bytearray)):
            return value

        if hasattr(value, "read"):
            upload_name = getattr(value, "name", None)
            if upload_name:
                upload_name = self._normalize_name(upload_name)
                self._validate_extension(upload_name)
            return value

        stored_name = self._normalize_name(value)
        self._validate_extension(stored_name)
        return stored_name

    def to_python(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return self._normalize_name(value)

    def to_db(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, FieldFile):
            value = value.name
        if not isinstance(value, str):
            raise ValueError(
                "FileField values must be prepared before database writes; "
                "use model.save() or assign a stored path string"
            )
        return self._normalize_name(value)

    def _extract_upload(self, value: Any) -> tuple[Optional[str], Any]:
        """Normalize supported upload-like objects to a name/content pair."""
        if isinstance(value, FieldFile):
            return value.name, value.name
        if isinstance(value, tuple) and len(value) == 2:
            return str(value[0]), value[1]
        filename = getattr(value, "filename", None)
        if filename:
            return str(filename), value
        if hasattr(value, "read"):
            return getattr(value, "name", None), value
        if isinstance(value, (bytes, bytearray)):
            return None, value
        raise ValueError(f"Unsupported file upload value for field '{self.name}'")

    async def async_prepare(self, value: Any, *, instance: Optional["Model"] = None) -> Any:
        """Persist unresolved file uploads and return the stored path."""
        if value is None:
            return None
        if isinstance(value, FieldFile):
            return value.name
        if isinstance(value, str):
            return self._normalize_name(value)

        original_name, payload = self._extract_upload(value)
        data = await read_uploaded_content(payload)
        upload_name = build_upload_name(
            field_name=self.name or "file",
            upload_to=self.upload_to,
            original_name=original_name,
            instance=instance,
        )
        normalized_name = self._normalize_name(upload_name)
        self._validate_extension(normalized_name)
        return await self.get_storage().save(normalized_name, data)

    def get_ai_metadata(self) -> dict:
        """Get AI metadata with file-specific hints."""
        base = super().get_ai_metadata()
        base["format"] = "file"
        base["max_length"] = self.max_length
        return base


class ImageField(FileField):
    """Image-specialized file field validated with Pillow."""

    def __init__(
        self,
        max_length: int = 500,
        *,
        upload_to: Any = "",
        storage: Any = None,
        allowed_extensions: Optional[List[str]] = None,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            max_length=max_length,
            upload_to=upload_to,
            storage=storage,
            allowed_extensions=allowed_extensions or ["jpg", "jpeg", "png", "gif", "webp", "bmp"],
            nullable=nullable,
            default=default,
            unique=unique,
            db_index=db_index,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )

    def _validate_image_bytes(self, data: bytes) -> str:
        """Validate image binary content and return the detected format."""
        try:
            from PIL import Image
        except ImportError as exc:
            raise ValueError(
                "ImageField requires Pillow for validation. Install with: pip install pillow"
            ) from exc

        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
                return (image.format or "").lower()
        except Exception as exc:
            raise ValueError("Uploaded file is not a valid image") from exc

    async def async_prepare(self, value: Any, *, instance: Optional["Model"] = None) -> Any:
        if value is None or isinstance(value, (str, FieldFile)):
            return await super().async_prepare(value, instance=instance)

        original_name, payload = self._extract_upload(value)
        data = await read_uploaded_content(payload)
        image_format = self._validate_image_bytes(data)

        normalized_name = original_name or f"{self.name or 'image'}.{image_format}"
        if not os.path.splitext(normalized_name)[1]:
            normalized_name = f"{normalized_name}.{image_format}"

        upload_name = build_upload_name(
            field_name=self.name or "image",
            upload_to=self.upload_to,
            original_name=normalized_name,
            instance=instance,
        )
        final_name = self._normalize_name(upload_name)
        self._validate_extension(final_name)
        return await self.get_storage().save(final_name, data)

    def get_ai_metadata(self) -> dict:
        """Get AI metadata with image-specific hints."""
        base = super().get_ai_metadata()
        base["format"] = "image"
        return base


class Email(Field):
    """
    Email field with validation, mapping to VARCHAR.
    
    Validates email format using basic RFC-style regex.
    Automatically lowercases and strips whitespace.
    
    Args:
        max_length: Maximum length (default: 254 - RFC 5321 max)
        nullable: Whether the field can be NULL
        unique: Whether the field should be unique
        default: Default value
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    
    Usage:
        class User(Model):
            email = fields.Email(unique=True)
    """
    
    def __init__(
        self,
        max_length: int = 254,
        *,
        nullable: bool = False,
        unique: bool = False,
        default: Any = None,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.max_length = max_length
    
    @property
    def sql_type(self) -> str:
        return f"VARCHAR({self.max_length})"
    
    def validate(self, value: Any) -> str:
        """Validate and normalize the email address."""
        if value is None:
            if self.nullable:
                return None
            raise ValueError("Email cannot be null")
        
        # Normalize: strip and lowercase
        email = str(value).strip().lower()
        
        # Validate format
        if not EMAIL_REGEX.match(email):
            raise ValueError(f"Invalid email format: {value}")

        local_part = email.split("@", 1)[0]
        if (
            local_part.startswith(".")
            or local_part.endswith(".")
            or ".." in local_part
        ):
            raise ValueError(f"Invalid email format: {value}")
        
        # Check length
        if len(email) > self.max_length:
            raise ValueError(f"Email exceeds maximum length of {self.max_length}")
        
        return email
    
    def to_python(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value).strip().lower()
    
    def to_db(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return self.validate(value)
    
    def get_ai_metadata(self) -> dict:
        """Get AI metadata with format hint."""
        base = super().get_ai_metadata()
        base["format"] = "email"
        return base


class URL(Field):
    """
    URL field with validation, mapping to TEXT.
    
    Validates that URLs start with http:// or https://.
    
    Args:
        nullable: Whether the field can be NULL
        unique: Whether the field should be unique
        default: Default value
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    
    Usage:
        class Website(Model):
            homepage = fields.URL()
    """
    
    def __init__(
        self,
        *,
        nullable: bool = False,
        unique: bool = False,
        default: Any = None,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
    
    @property
    def sql_type(self) -> str:
        return "TEXT"
    
    def validate(self, value: Any) -> str:
        """Validate the URL."""
        if value is None:
            if self.nullable:
                return None
            raise ValueError("URL cannot be null")
        
        url = str(value).strip()
        
        # Validate format
        if not URL_REGEX.match(url):
            raise ValueError(f"Invalid URL format (must start with http:// or https://): {value}")
        
        return url
    
    def to_python(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value).strip()
    
    def to_db(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return self.validate(value)
    
    def get_ai_metadata(self) -> dict:
        """Get AI metadata with format hint."""
        base = super().get_ai_metadata()
        base["format"] = "uri"
        return base


class Decimal(Field):
    """
    Decimal field for precise numeric values, mapping to NUMERIC.
    
    Use this for monetary values and other cases requiring exact precision.
    
    Args:
        max_digits: Total number of digits (precision)
        decimal_places: Number of decimal places (scale)
        min_value: Minimum allowed value (default: None)
        max_value: Maximum allowed value (default: None)
        nullable: Whether the field can be NULL
        unique: Whether the field should be unique
        default: Default value
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    
    Usage:
        class Product(Model):
            price = fields.Decimal(max_digits=10, decimal_places=2)
    """
    
    def __init__(
        self,
        max_digits: int = 10,
        decimal_places: int = 2,
        *,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        nullable: bool = False,
        unique: bool = False,
        default: Any = None,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.max_digits = max_digits
        self.decimal_places = decimal_places
        self.min_value = PyDecimal(str(min_value)) if min_value is not None else None
        self.max_value = PyDecimal(str(max_value)) if max_value is not None else None
    
    @property
    def sql_type(self) -> str:
        return f"NUMERIC({self.max_digits}, {self.decimal_places})"
    
    def validate(self, value: Any) -> PyDecimal:
        """Validate decimal precision."""
        if value is None:
            if self.nullable:
                return None
            raise ValueError("Decimal cannot be null")
        
        try:
            dec = PyDecimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Invalid decimal value: {value}")
        
        # Reject NaN and Infinity
        if dec.is_nan() or dec.is_infinite():
            raise ValueError(f"Invalid decimal value: {value}")
        
        # Check precision and scale before persistence so PostgreSQL never
        # silently rounds values to fit NUMERIC(precision, scale).
        _sign, digits, exponent = dec.as_tuple()
        if exponent >= 0:
            integer_digits = len(digits) + exponent
            fractional_digits = 0
        else:
            integer_digits = max(len(digits) + exponent, 0)
            fractional_digits = -exponent

        if fractional_digits > self.decimal_places:
            raise ValueError(
                f"Decimal value {value} exceeds maximum decimal places "
                f"({self.decimal_places})"
            )

        if integer_digits > (self.max_digits - self.decimal_places):
            raise ValueError(
                f"Decimal value {value} exceeds maximum integer digits "
                f"({self.max_digits - self.decimal_places})"
            )

        if integer_digits + fractional_digits > self.max_digits:
            raise ValueError(
                f"Decimal value {value} exceeds maximum digits ({self.max_digits})"
            )

        # Range validation
        if self.min_value is not None and dec < self.min_value:
            raise ValueError(
                f"Value {value} is below the minimum of {self.min_value}"
            )
        if self.max_value is not None and dec > self.max_value:
            raise ValueError(
                f"Value {value} exceeds the maximum of {self.max_value}"
            )
        
        return dec
    
    def to_python(self, value: Any) -> Optional[PyDecimal]:
        if value is None:
            return None
        if isinstance(value, PyDecimal):
            return value
        return PyDecimal(str(value))
    
    def to_db(self, value: Any) -> Optional[PyDecimal]:
        if value is None:
            return None
        return self.validate(value)
    
    def _format_default(self) -> str:
        """Format default for SQL."""
        if self.default is None:
            return "NULL"
        return str(self.default)
    
    def get_ai_metadata(self) -> dict:
        """Get AI metadata with precision info."""
        base = super().get_ai_metadata()
        base["max_digits"] = self.max_digits
        base["decimal_places"] = self.decimal_places
        if self.min_value is not None:
            base["min_value"] = float(self.min_value)
        if self.max_value is not None:
            base["max_value"] = float(self.max_value)
        return base


class Enum(Field):
    """
    Enum field mapping to TEXT with validation.
    
    Stores enum values as their string name in the database.
    Validates that values are valid enum members.
    
    Args:
        enum_class: Python Enum class for validation
        nullable: Whether the field can be NULL
        default: Default value (enum member or None)
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    
    Usage:
        from enum import Enum as PyEnum
        
        class Status(PyEnum):
            DRAFT = "draft"
            PUBLISHED = "published"
            ARCHIVED = "archived"
        
        class Post(Model):
            status = fields.Enum(Status, default=Status.DRAFT)
    """
    
    def __init__(
        self,
        enum_class: Type[PyEnum],
        *,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.enum_class = enum_class
        self.db_index = db_index
    
    @property
    def sql_type(self) -> str:
        return "TEXT"
    
    def validate(self, value: Any) -> PyEnum:
        """Validate that value is a valid enum member."""
        if value is None:
            if self.nullable:
                return None
            raise ValueError("Enum value cannot be null")
        
        # If it's already an enum member, return it
        if isinstance(value, self.enum_class):
            return value
        
        # Try to convert from name or value
        if isinstance(value, str):
            # Try by name first
            try:
                return self.enum_class[value]
            except KeyError:
                pass
            
            # Try by value
            for member in self.enum_class:
                if member.value == value:
                    return member
        
        # Try direct value lookup
        try:
            return self.enum_class(value)
        except ValueError:
            pass
        
        valid_names = [m.name for m in self.enum_class]
        valid_values = [m.value for m in self.enum_class]
        raise ValueError(
            f"Invalid enum value: {value}. "
            f"Valid names: {valid_names}, valid values: {valid_values}"
        )
    
    def to_python(self, value: Any) -> Optional[PyEnum]:
        """Convert database value to enum member."""
        if value is None:
            return None
        
        # Database stores the value as TEXT
        for member in self.enum_class:
            if member.value == value or member.name == value:
                return member
        
        # Fallback: try direct value lookup
        try:
            return self.enum_class(value)
        except ValueError:
            pass
        
        # Return the string if we can't convert
        return value
    
    def to_db(self, value: Any) -> Optional[str]:
        """Convert enum to string value for database."""
        if value is None:
            return None
        
        validated = self.validate(value)
        if validated is None:
            return None
        
        # Store the enum's value (not name)
        return str(validated.value)
    
    def _format_default(self) -> str:
        """Format default for SQL."""
        if self.default is None:
            return "NULL"
        if isinstance(self.default, self.enum_class):
            return f"'{self.default.value}'"
        return f"'{self.default}'"
    
    def get_default_value(self) -> Any:
        """Get default value, keeping it as enum."""
        if callable(self.default):
            return self.default()
        return self.default
    
    def get_ai_metadata(self) -> dict:
        """Get AI metadata with allowed values."""
        base = super().get_ai_metadata()
        base["enum_values"] = [m.value for m in self.enum_class]
        base["enum_names"] = [m.name for m in self.enum_class]
        return base


# Convenience aliases for new fields
TextField = Text
EmailField = Email
URLField = URL
DecimalField = Decimal
EnumField = Enum
FileFieldType = FileField
ImageFieldType = ImageField


class Float(Field):
    """
    Float field mapping to DOUBLE PRECISION.
    
    Use this for floating-point numeric values. For exact precision
    (e.g., monetary values), use Decimal instead.
    
    Args:
        min_value: Minimum allowed value (default: None)
        max_value: Maximum allowed value (default: None)
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    
    Usage:
        class Measurement(Model):
            temperature = fields.Float()
            latitude = fields.Float(nullable=True)
    """
    
    def __init__(
        self,
        *,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.min_value = min_value
        self.max_value = max_value
        self.db_index = db_index
    
    @property
    def sql_type(self) -> str:
        return "DOUBLE PRECISION"
    
    def to_python(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        return float(value)
    
    def to_db(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        v = float(value)
        if not math.isfinite(v):
            raise ValueError("Float values must be finite")
        if self.min_value is not None and v < self.min_value:
            raise ValueError(
                f"Value {v} is below the minimum of {self.min_value}"
            )
        if self.max_value is not None and v > self.max_value:
            raise ValueError(
                f"Value {v} exceeds the maximum of {self.max_value}"
            )
        return v

    def get_ai_metadata(self) -> dict:
        """Get AI metadata with float-specific options."""
        base = super().get_ai_metadata()
        if self.min_value is not None:
            base["min_value"] = self.min_value
        if self.max_value is not None:
            base["max_value"] = self.max_value
        return base


class Date(Field):
    """
    Date field mapping to DATE (date without time).
    
    Args:
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    
    Usage:
        from datetime import date
        
        class Event(Model):
            event_date = fields.Date()
            deadline = fields.Date(nullable=True)
    """
    
    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.db_index = db_index
    
    @property
    def sql_type(self) -> str:
        return "DATE"
    
    def to_python(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            # Handle ISO format date strings
            if 'T' in value:
                return datetime.fromisoformat(value).date()
            return date.fromisoformat(value)
        return value
    
    def to_db(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        return value


FloatField = Float
DateField = Date


# =============================================================================
# Extended Fields — Django parity
# =============================================================================


class Slug(Field):
    """
    Slug field mapping to VARCHAR for URL-friendly short labels.

    Validates that the value contains only letters, numbers, hyphens,
    and underscores (the same character set Django's SlugField enforces).

    Args:
        max_length: Maximum character length (default 50)
        allow_unicode: Allow Unicode letters/numbers in addition to ASCII
        auto_from: Auto-generate slug from this field when the slug is
            empty or None.  Only runs on creation (when the slug has no
            existing value), so changing the source field later will not
            overwrite a previously set slug.
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this

    Usage:
        class Article(Model):
            title = fields.String(max_length=200)
            slug = fields.Slug(max_length=200, auto_from="title", unique=True)
    """

    def __init__(
        self,
        *,
        max_length: int = 50,
        allow_unicode: bool = False,
        auto_from: Optional[str] = None,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.max_length = max_length
        self.allow_unicode = allow_unicode
        self.auto_from = auto_from
        self.db_index = db_index
        self._slug_re = re.compile(r"^[-\w]+$", re.UNICODE if allow_unicode else re.ASCII)

    @property
    def sql_type(self) -> str:
        return f"VARCHAR({self.max_length})"

    def to_python(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)

    def to_db(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        v = str(value)
        if not self._slug_re.match(v):
            raise ValueError(
                f"Invalid slug {v!r}: only letters, numbers, hyphens, and underscores allowed."
            )
        if len(v) > self.max_length:
            raise ValueError(f"Slug exceeds max_length={self.max_length}: {v!r}")
        return v

    async def async_prepare(self, value: Any, *, instance: Optional["Model"] = None) -> Any:
        """
        Auto-generate a slug from *auto_from* when the current value is
        empty or None and the source field has a value.
        """
        if self.auto_from and not value and instance is not None:
            source = getattr(instance, self.auto_from, None)
            if source:
                slug = _slugify(str(source), allow_unicode=self.allow_unicode)
                # Truncate to max_length
                if len(slug) > self.max_length:
                    slug = slug[:self.max_length].rstrip('-')
                return slug
        return value


SlugField = Slug


class SmallInteger(Field):
    """
    Small integer field mapping to SMALLINT (-32 768 to 32 767).

    Use when the integer range of a regular INTEGER is more than needed
    and you want to save storage space.

    Args:
        choices: Restrict values to this set
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this

    Usage:
        class Product(Model):
            rating = fields.SmallIntegerField()
    """

    _SMALLINT_MIN = SMALLINT_MIN
    _SMALLINT_MAX = SMALLINT_MAX

    def __init__(
        self,
        *,
        choices: Optional[list] = None,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.choices = choices
        self._choices_valid = _normalize_choices(choices)
        self.db_index = db_index

    @property
    def sql_type(self) -> str:
        return "SMALLINT"

    def to_python(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        return _coerce_strict_integer(value, "SmallInteger")

    def to_db(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        v = _coerce_strict_integer(value, "SmallInteger")
        _validate_integer_bounds(v, self._SMALLINT_MIN, self._SMALLINT_MAX, "SMALLINT")
        if self._choices_valid is not None and v not in self._choices_valid:
            raise ValueError(
                f"Value {v!r} is not a valid choice. "
                f"Valid choices are: {sorted(self._choices_valid)}"
            )
        return v

    def get_ai_metadata(self) -> dict:
        """Get AI metadata with choices info."""
        base = super().get_ai_metadata()
        if self.choices is not None:
            base["choices"] = self.choices
        return base


SmallIntegerField = SmallInteger


class BigInteger(Field):
    """
    Big integer field mapping to BIGINT (-2^63 to 2^63 - 1).

    Use for very large integers such as row counts or external IDs.

    Args:
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this

    Usage:
        class Counter(Model):
            total_views = fields.BigIntegerField(default=0)
    """

    _BIGINT_MIN = BIGINT_MIN
    _BIGINT_MAX = BIGINT_MAX

    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.db_index = db_index

    @property
    def sql_type(self) -> str:
        return "BIGINT"

    def to_python(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        return _coerce_strict_integer(value, "BigInteger")

    def to_db(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        v = _coerce_strict_integer(value, "BigInteger")
        _validate_integer_bounds(v, self._BIGINT_MIN, self._BIGINT_MAX, "BIGINT")
        return v


BigIntegerField = BigInteger


class PositiveInteger(Field):
    """
    Positive integer field mapping to INTEGER with a >= 0 constraint.

    Python-level validation raises ValueError for negative values.
    For the CHECK constraint in the database, use a migration that
    adds ``CHECK (column >= 0)`` alongside this field.

    Args:
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this

    Usage:
        class Product(Model):
            stock = fields.PositiveIntegerField(default=0)
    """

    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.db_index = db_index

    @property
    def sql_type(self) -> str:
        return "INTEGER"

    def to_python(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        return _coerce_strict_integer(value, "PositiveInteger")

    def to_db(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        v = _coerce_strict_integer(value, "PositiveInteger")
        if v < 0:
            raise ValueError(
                f"PositiveIntegerField requires a non-negative value, got {v}."
            )
        _validate_integer_bounds(v, 0, INTEGER_MAX, "INTEGER")
        return v


PositiveIntegerField = PositiveInteger


class PositiveSmallInteger(Field):
    """
    Positive small integer field mapping to SMALLINT with a >= 0 constraint
    (range 0 to 32 767).

    Args:
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this

    Usage:
        class Task(Model):
            priority = fields.PositiveSmallIntegerField(default=0)
    """

    _MAX = SMALLINT_MAX

    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.db_index = db_index

    @property
    def sql_type(self) -> str:
        return "SMALLINT"

    def to_python(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        return _coerce_strict_integer(value, "PositiveSmallInteger")

    def to_db(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        v = _coerce_strict_integer(value, "PositiveSmallInteger")
        if not (0 <= v <= self._MAX):
            raise ValueError(
                f"Value {v} is out of POSITIVE SMALLINT range (0..{self._MAX})."
            )
        return v


PositiveSmallIntegerField = PositiveSmallInteger


class PositiveBigInteger(Field):
    """
    Positive big integer field mapping to BIGINT with a >= 0 constraint.

    Args:
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this

    Usage:
        class Analytics(Model):
            event_count = fields.PositiveBigIntegerField(default=0)
    """

    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.db_index = db_index

    @property
    def sql_type(self) -> str:
        return "BIGINT"

    def to_python(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        return _coerce_strict_integer(value, "PositiveBigInteger")

    def to_db(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        v = _coerce_strict_integer(value, "PositiveBigInteger")
        if v < 0:
            raise ValueError(
                f"PositiveBigIntegerField requires a non-negative value, got {v}."
            )
        _validate_integer_bounds(v, 0, BIGINT_MAX, "BIGINT")
        return v


PositiveBigIntegerField = PositiveBigInteger


class Time(Field):
    """
    Time field mapping to TIME (time of day without date or timezone).

    Args:
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this

    Usage:
        from datetime import time

        class Schedule(Model):
            open_at = fields.TimeField()
            close_at = fields.TimeField(nullable=True)
    """

    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.db_index = db_index

    @property
    def sql_type(self) -> str:
        return "TIME"

    def to_python(self, value: Any) -> Optional[py_time]:
        if value is None:
            return None
        if isinstance(value, py_time):
            return value
        if isinstance(value, datetime):
            return value.time()
        if isinstance(value, str):
            return py_time.fromisoformat(value)
        return value

    def to_db(self, value: Any) -> Optional[py_time]:
        if value is None:
            return None
        if isinstance(value, py_time):
            return value
        if isinstance(value, datetime):
            return value.time()
        if isinstance(value, str):
            return py_time.fromisoformat(value)
        return value


TimeField = Time


class Duration(Field):
    """
    Duration field mapping to INTERVAL for storing time spans.

    Stores Python ``datetime.timedelta`` values. asyncpg maps PostgreSQL
    ``INTERVAL`` to ``timedelta`` natively — no manual conversion needed
    at the database driver level.

    Args:
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this

    Usage:
        from datetime import timedelta

        class Subscription(Model):
            duration = fields.DurationField(default=timedelta(days=30))
    """

    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.db_index = db_index

    @property
    def sql_type(self) -> str:
        return "INTERVAL"

    def to_python(self, value: Any) -> Optional[timedelta]:
        if value is None:
            return None
        if isinstance(value, timedelta):
            return value
        if isinstance(value, (int, float)):
            return timedelta(seconds=value)
        return value

    def to_db(self, value: Any) -> Optional[timedelta]:
        if value is None:
            return None
        if isinstance(value, timedelta):
            return value
        if isinstance(value, (int, float)):
            return timedelta(seconds=value)
        return value


DurationField = Duration


class IPAddress(Field):
    """
    IP address field mapping to PostgreSQL INET (supports IPv4 and IPv6).

    PostgreSQL's INET type is more powerful than a plain VARCHAR —
    it can be indexed efficiently and supports subnet operations.

    Args:
        protocol: Accepted protocol — ``"both"`` (default), ``"ipv4"``, or ``"ipv6"``
        unpack_ipv4: When True and protocol is "both", an IPv4-mapped IPv6 address
            such as ``::ffff:192.0.2.1`` is unpacked to ``192.0.2.1``
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this

    Usage:
        class AccessLog(Model):
            ip = fields.GenericIPAddressField()
            ipv4_only = fields.IPAddressField(protocol="ipv4")
    """

    def __init__(
        self,
        *,
        protocol: str = "both",
        unpack_ipv4: bool = False,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        if protocol not in ("both", "ipv4", "ipv6"):
            raise ValueError("protocol must be 'both', 'ipv4', or 'ipv6'.")
        self.protocol = protocol
        self.unpack_ipv4 = unpack_ipv4
        self.db_index = db_index

    @property
    def sql_type(self) -> str:
        return "INET"

    def _validate(self, value: str) -> str:
        try:
            addr = ipaddress.ip_address(value)
        except ValueError:
            raise ValueError(f"Invalid IP address: {value!r}")
        if self.protocol == "ipv4" and not isinstance(addr, ipaddress.IPv4Address):
            raise ValueError(f"Expected an IPv4 address, got: {value!r}")
        if self.protocol == "ipv6" and not isinstance(addr, ipaddress.IPv6Address):
            raise ValueError(f"Expected an IPv6 address, got: {value!r}")
        if (
            self.unpack_ipv4
            and isinstance(addr, ipaddress.IPv6Address)
            and addr.ipv4_mapped is not None
        ):
            return str(addr.ipv4_mapped)
        return str(addr)

    def to_python(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        try:
            return str(ipaddress.ip_address(str(value)))
        except ValueError:
            return str(value)

    def to_db(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return self._validate(str(value))


IPAddressField = IPAddress
GenericIPAddressField = IPAddress


class Binary(Field):
    """
    Binary field mapping to BYTEA for raw byte storage.

    Accepts ``bytes``, ``bytearray``, ``memoryview``, or ``str`` (UTF-8 encoded).
    Returns ``bytes`` from ``to_python``.

    Args:
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_sensitive: Whether field contains sensitive data (default True —
            binary blobs are often sensitive)
        ai_agent_writable: Whether AI agents can modify this
        ai_description: Description for AI agents

    Usage:
        class Document(Model):
            content = fields.BinaryField()
    """

    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = True,
        ai_agent_writable: bool = False,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.db_index = db_index

    @property
    def sql_type(self) -> str:
        return "BYTEA"

    def to_python(self, value: Any) -> Optional[bytes]:
        if value is None:
            return None
        if isinstance(value, memoryview):
            return bytes(value)
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode("utf-8")
        return bytes(value)

    def to_db(self, value: Any) -> Optional[bytes]:
        if value is None:
            return None
        if isinstance(value, memoryview):
            return bytes(value)
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode("utf-8")
        return bytes(value)


BinaryField = Binary


class FilePath(Field):
    """
    File path field mapping to VARCHAR, listing files from a directory.

    Stores a file-system path as a string.  The ``choices()`` helper
    method returns ``(value, display)`` pairs by scanning ``path`` so
    the field can drive a select widget in admin or forms.

    Args:
        path: Directory to scan for file choices (may be empty string)
        match: Optional regex pattern to filter file names
        recursive: If True, walk subdirectories when building choices
        allow_files: Include regular files in choices (default True)
        allow_folders: Include directories in choices (default False)
        max_length: VARCHAR length for the stored path (default 100)
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        db_index: Whether to create a database index
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this

    Usage:
        class Config(Model):
            template_file = fields.FilePathField(path="/templates", match=r".*\\.html")
    """

    def __init__(
        self,
        *,
        path: str = "",
        match: Optional[str] = None,
        recursive: bool = False,
        allow_files: bool = True,
        allow_folders: bool = False,
        max_length: int = 100,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            default=default,
            unique=unique,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.path = path
        self.match = match
        self.recursive = recursive
        self.allow_files = allow_files
        self.allow_folders = allow_folders
        self.max_length = max_length
        self.db_index = db_index

    @property
    def sql_type(self) -> str:
        return f"VARCHAR({self.max_length})"

    def choices(self) -> list[tuple[str, str]]:
        """Scan ``self.path`` and return ``(path, path)`` pairs for each matching entry.

        Returns:
            Sorted list of ``(value, display)`` tuples suitable for select widgets.
        """
        result: list[tuple[str, str]] = []
        if not self.path:
            return result
        try:
            if self.recursive:
                for root, dirs, files in os.walk(self.path):
                    if self.allow_folders:
                        for d in dirs:
                            full = os.path.join(root, d)
                            result.append((full, full))
                    if self.allow_files:
                        for name in files:
                            if self.match and not re.match(self.match, name):
                                continue
                            full = os.path.join(root, name)
                            result.append((full, full))
            else:
                for name in os.listdir(self.path):
                    full = os.path.join(self.path, name)
                    if os.path.isfile(full) and self.allow_files:
                        if not self.match or re.match(self.match, name):
                            result.append((full, full))
                    elif os.path.isdir(full) and self.allow_folders:
                        result.append((full, full))
        except OSError:
            pass
        return sorted(result)

    def to_python(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)

    def to_db(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)


FilePathField = FilePath


class ForeignKey(Field):
    """
    Foreign key field that references another model.
    
    Creates a column that stores the primary key of the referenced model
    and adds a FOREIGN KEY constraint.
    
    Args:
        to: The model class being referenced (or string name for lazy reference)
        related_name: Name for reverse access on target model (default: "{model}_set")
        column_name: Name for the FK column (default: "{field_name}_id")
        on_delete: Action on delete - use CASCADE, SET_NULL, RESTRICT, or PROTECT
        nullable: Whether the field can be NULL
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    
    Usage:
        from aksara import fields
        from aksara.fields import CASCADE, SET_NULL, RESTRICT
        
        class Post(Model):
            # Using module constant (recommended)
            author = fields.ForeignKey(User, on_delete=CASCADE, related_name="posts")
            
            # Or using OnDelete class
            editor = fields.ForeignKey(User, on_delete=fields.OnDelete.SET_NULL, nullable=True)
            
        # Forward access
        post.author_id  # The UUID of the referenced User
        
        # Reverse access
        posts = await user.posts.all()
    """
    
    def __init__(
        self,
        to: Union[Type["Model"], str],
        *,
        related_name: Optional[str] = None,
        column_name: Optional[str] = None,
        on_delete: str = CASCADE,
        nullable: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            nullable=nullable,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self._to = to
        self._column_name = column_name
        self.on_delete = normalize_on_delete(on_delete, nullable=nullable)
        self.related_name = related_name
        
        # These will be set after model class creation
        self._resolved_model: Optional[Type["Model"]] = None
        self._actual_column_name: Optional[str] = None
    
    @property
    def to_model(self) -> Type["Model"]:
        """Get the referenced model class."""
        if self._resolved_model is not None:
            return self._resolved_model
        
        if isinstance(self._to, str):
            # Lazy resolution from registry
            from aksara.registry import ModelRegistry
            self._resolved_model = ModelRegistry.get(self._to)
            return self._resolved_model
        
        return self._to
    
    @property
    def db_column_name(self) -> str:
        """Get the actual database column name (e.g., 'author_id')."""
        if self._actual_column_name:
            return self._actual_column_name
        if self._column_name:
            return self._column_name
        if self.name:
            return f"{self.name}_id"
        return "fk_id"
    
    @property
    def column_name(self) -> str:
        """
        Get the actual database column name.
        
        For ForeignKey, this is {name}_id.
        """
        return self.db_column_name
    
    @property
    def sql_type(self) -> str:
        """Return the PostgreSQL type matching the referenced PK."""
        # Get the primary key field of the referenced model
        try:
            target_model = self.to_model
            # Find the field with primary_key=True
            for f in target_model._fields.values():
                if f.primary_key:
                    return f.sql_type
            # Fallback: try "id" field
            pk_field = target_model._fields.get("id")
            if pk_field:
                return pk_field.sql_type
        except Exception:
            pass
        # Default to UUID (most common PK type in Aksara)
        return "UUID"
    
    def get_column_definition(self) -> str:
        """Generate the SQL column definition."""
        col_name = self.db_column_name
        parts = [col_name, self.sql_type]
        
        if not self.nullable:
            parts.append("NOT NULL")
        
        return " ".join(parts)
    
    def get_constraint_definition(self) -> str:
        """Generate the FOREIGN KEY constraint definition."""
        try:
            target_model = self.to_model
            target_table = target_model.__tablename__
        except Exception:
            # Fallback for unresolved models
            if isinstance(self._to, str):
                # Convert model name to table name (simple pluralization)
                name = self._to.lower()
                if name.endswith('y') and len(name) > 1 and name[-2] not in 'aeiou':
                    target_table = name[:-1] + 'ies'
                elif name.endswith(('s', 'x', 'z', 'ch', 'sh')):
                    target_table = name + 'es'
                else:
                    target_table = name + 's'
            else:
                target_table = "unknown"
        
        col_name = self.db_column_name
        constraint_name = f"fk_{col_name}"
        
        return f'CONSTRAINT {constraint_name} FOREIGN KEY ({col_name}) REFERENCES "{target_table}"(id) ON DELETE {self.on_delete}'
    
    def to_python(self, value: Any) -> Optional[uuid_lib.UUID]:
        """Convert database value to Python UUID."""
        if value is None:
            return None
        if isinstance(value, uuid_lib.UUID):
            return value
        return uuid_lib.UUID(str(value))
    
    def to_db(self, value: Any) -> Optional[uuid_lib.UUID]:
        """Convert Python value to database UUID."""
        if value is None:
            return None
        if isinstance(value, uuid_lib.UUID):
            return value
        # Handle case where a model instance is passed
        if hasattr(value, 'id'):
            return value.id
        return uuid_lib.UUID(str(value))
    
    def get_ai_metadata(self) -> dict:
        """Get AI metadata for this field."""
        base = super().get_ai_metadata()
        try:
            target_name = self.to_model.__name__
        except Exception:
            target_name = str(self._to)
        
        base.update({
            "references": target_name,
            "on_delete": self.on_delete,
            "column_name": self.db_column_name,
        })
        return base


ForeignKeyField = ForeignKey


# =============================================================================
# v0.3.5: Relationship Fields
# =============================================================================


class OneToOne(ForeignKey):
    """
    One-to-one relationship field (FK with unique=True).
    
    Creates a foreign key column with a UNIQUE constraint, ensuring
    each record can only be referenced by one other record.
    
    Args:
        to: The model class being referenced (or string name)
        related_name: Name for reverse access on target model
        column_name: Name for the FK column (default: "{field_name}_id")
        on_delete: Action on delete - use CASCADE, SET_NULL, RESTRICT, or PROTECT
        nullable: Whether the field can be NULL
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    
    Usage:
        from aksara.fields import CASCADE
        
        class UserProfile(Model):
            user = fields.OneToOne(User, on_delete=CASCADE, related_name="profile")
            bio = fields.Text(nullable=True)
            
        # Reverse access
        profile = await user.profile()
    """
    
    def __init__(
        self,
        to: Union[Type["Model"], str],
        *,
        related_name: Optional[str] = None,
        column_name: Optional[str] = None,
        on_delete: str = CASCADE,
        nullable: bool = False,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        super().__init__(
            to,
            related_name=related_name,
            column_name=column_name,
            on_delete=on_delete,
            nullable=nullable,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        # Mark as unique (one-to-one)
        self.unique = True
    
    def get_column_definition(self) -> str:
        """Generate the SQL column definition with UNIQUE."""
        col_name = self.db_column_name
        parts = [col_name, self.sql_type]
        
        if not self.nullable:
            parts.append("NOT NULL")
        
        parts.append("UNIQUE")
        
        return " ".join(parts)
    
    def get_ai_metadata(self) -> dict:
        """Get AI metadata for this field."""
        base = super().get_ai_metadata()
        base["relationship"] = "one_to_one"
        base["related_name"] = self.related_name
        return base


OneToOneField = OneToOne


class ManyToMany(Field):
    """
    Many-to-many relationship field.
    
    Creates an intermediary join table to link two models.
    Provides a ManyToManyManager for managing the relationship.
    
    Join table structure:
        - id: UUID primary key
        - {source_table}_id: FK to source model
        - {target_table}_id: FK to target model
        - UNIQUE constraint on (source_id, target_id)
    
    Args:
        to: The model class being referenced (or string name)
        related_name: Name for reverse access (future use)
        through: Custom join table model (optional, future use)
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    
    Usage:
        class Post(Model):
            title = fields.String(max_length=200)
            tags = fields.ManyToMany("Tag", related_name="posts")
        
        # In code:
        post = await Post.objects.get(id=post_id)
        await post.tags.add(tag1, tag2)
        all_tags = await post.tags.all()
        await post.tags.remove(tag1)
        await post.tags.clear()
    """
    
    def __init__(
        self,
        to: Union[Type["Model"], str],
        *,
        related_name: Optional[str] = None,
        through: Optional[str] = None,
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        # ManyToMany doesn't have a direct column, so nullable doesn't apply
        if through is not None:
            raise ValueError("Custom through models are not supported yet")

        super().__init__(
            nullable=True,  # No actual column
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self._to = to
        self.related_name = related_name
        self.through = through
        
        # These will be set during model creation
        self._source_model: Optional[Type["Model"]] = None
        self._resolved_model: Optional[Type["Model"]] = None
        self._join_table_name: Optional[str] = None
    
    @property
    def to_model(self) -> Type["Model"]:
        """Get the referenced model class."""
        if self._resolved_model is not None:
            return self._resolved_model
        
        if isinstance(self._to, str):
            from aksara.registry import ModelRegistry
            self._resolved_model = ModelRegistry.get(self._to)
            return self._resolved_model
        
        return self._to
    
    @property
    def join_table_name(self) -> str:
        """Get the name of the join table."""
        if self._join_table_name:
            return self._join_table_name
        
        if self.through:
            return self.through
        
        # Generate: {source_table}_{field_name}
        if self._source_model and self.name:
            return f"{self._source_model.__tablename__}_{self.name}"
        
        return f"m2m_{self.name or 'rel'}"
    
    @property
    def source_column(self) -> str:
        """Get the source column name in join table."""
        if self._source_model:
            # Use singular form: users -> user_id
            table_name = self._source_model.__tablename__
            singular = _singularize(table_name)
            return f"{singular}_id"
        return "source_id"
    
    @property
    def target_column(self) -> str:
        """Get the target column name in join table."""
        try:
            target_table = self.to_model.__tablename__
            singular = _singularize(target_table)
            return f"{singular}_id"
        except Exception:
            return "target_id"
    
    @property
    def sql_type(self) -> str:
        """ManyToMany has no direct SQL type (it's a virtual field)."""
        return "VIRTUAL"
    
    @property
    def column_name(self) -> str:
        """ManyToMany has no column name (virtual field)."""
        return None
    
    def get_column_definition(self) -> str:
        """ManyToMany has no column definition."""
        return None
    
    def get_join_table_sql(self) -> str:
        """Generate CREATE TABLE SQL for the join table."""
        source_table = self._source_model.__tablename__ if self._source_model else "source"
        try:
            target_table = self.to_model.__tablename__
        except Exception:
            # Fallback for unresolved models
            if isinstance(self._to, str):
                name = self._to.lower()
                if name.endswith('y') and len(name) > 1 and name[-2] not in 'aeiou':
                    target_table = name[:-1] + 'ies'
                elif name.endswith(('s', 'x', 'z', 'ch', 'sh')):
                    target_table = name + 'es'
                else:
                    target_table = name + 's'
            else:
                target_table = "target"
        
        join_table = self.join_table_name
        source_col = self.source_column
        target_col = self.target_column
        
        return f'''CREATE TABLE IF NOT EXISTS "{join_table}" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    {source_col} UUID NOT NULL,
    {target_col} UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_{join_table}_{source_col} FOREIGN KEY ({source_col}) REFERENCES "{source_table}"(id) ON DELETE CASCADE,
    CONSTRAINT fk_{join_table}_{target_col} FOREIGN KEY ({target_col}) REFERENCES "{target_table}"(id) ON DELETE CASCADE,
    CONSTRAINT uq_{join_table} UNIQUE ({source_col}, {target_col})
);'''
    
    def to_python(self, value: Any) -> Any:
        """ManyToMany returns a manager, not a direct value."""
        return value
    
    def to_db(self, value: Any) -> Any:
        """ManyToMany doesn't store directly in the model table."""
        return None
    
    def get_ai_metadata(self) -> dict:
        """Get AI metadata for this field."""
        base = super().get_ai_metadata()
        try:
            target_name = self.to_model.__name__
        except Exception:
            target_name = str(self._to)
        
        base.update({
            "relationship": "many_to_many",
            "references": target_name,
            "related_name": self.related_name,
            "join_table": self.join_table_name,
        })
        return base


ManyToManyField = ManyToMany


class GenericForeignKeyAccessor:
    """Async accessor for a GenericForeignKey relation."""

    def __init__(
        self,
        field: "GenericForeignKey",
        instance: "Model",
    ):
        self._field = field
        self._instance = instance

    async def __call__(self) -> Optional["Model"]:
        """Resolve the related object for this generic relation."""
        cached = self._instance._generic_fk_cache.get(self._field.name)
        if cached is not None:
            return cached

        content_type_id = self._instance._data.get(self._field.content_type_field)
        object_id = self._instance._data.get(self._field.object_id_field)

        if content_type_id is None or object_id is None:
            return None

        from aksara.contenttypes import resolve_generic_related_object

        related = await resolve_generic_related_object(content_type_id, object_id)
        self._instance._generic_fk_cache[self._field.name] = related
        return related

    async def set(self, value: Optional["Model"]) -> None:
        """Assign and prepare a generic relation asynchronously."""
        self._field.__set__(self._instance, value)
        await self._field.async_prepare(self._instance)

    def __repr__(self) -> str:
        return f"<GenericForeignKeyAccessor: {self._instance.__class__.__name__}.{self._field.name}>"


class GenericForeignKey:
    """
    Virtual relation backed by content_type_id and object_id columns.

    The descriptor returns an async accessor, so callers use:

        related = await comment.content_object()
    """

    def __init__(
        self,
        *,
        content_type_field: str = "content_type_id",
        object_id_field: str = "object_id",
        nullable: bool = True,
        object_id_max_length: int = 255,
    ):
        self.name: Optional[str] = None
        self.content_type_field = content_type_field
        self.object_id_field = object_id_field
        self.nullable = nullable
        self.object_id_max_length = object_id_max_length

    def __set_name__(self, owner: Type["Model"], name: str) -> None:
        self.name = name

    def build_support_fields(self) -> dict[str, Field]:
        """Build the concrete fields required to store this relation."""
        content_type_field = UUID(nullable=self.nullable)
        content_type_field.name = self.content_type_field

        object_id_field = String(
            max_length=self.object_id_max_length,
            nullable=self.nullable,
        )
        object_id_field.name = self.object_id_field

        return {
            self.content_type_field: content_type_field,
            self.object_id_field: object_id_field,
        }

    def __get__(
        self,
        instance: Optional["Model"],
        owner: Type["Model"],
    ) -> Union["GenericForeignKey", GenericForeignKeyAccessor]:
        if instance is None:
            return self
        return GenericForeignKeyAccessor(self, instance)

    def __set__(self, instance: "Model", value: Optional["Model"]) -> None:
        if self.name is None:
            raise AttributeError("GenericForeignKey is not bound to a model field")

        if value is None:
            instance._generic_fk_pending[self.name] = None
            instance._generic_fk_cache.pop(self.name, None)
            instance._data[self.content_type_field] = None
            instance._data[self.object_id_field] = None
            return

        if not hasattr(value, "id"):
            raise TypeError(
                f"{self.name} expects a model instance or None, got {type(value).__name__}"
            )

        instance._generic_fk_pending[self.name] = value
        instance._generic_fk_cache[self.name] = value
        instance._data[self.object_id_field] = str(value.id)

    async def async_prepare(self, instance: "Model") -> None:
        """Resolve pending model assignments into stored content type fields."""
        if self.name is None or self.name not in instance._generic_fk_pending:
            return

        value = instance._generic_fk_pending.pop(self.name)
        if value is None:
            instance._data[self.content_type_field] = None
            instance._data[self.object_id_field] = None
            instance._generic_fk_cache.pop(self.name, None)
            return

        from aksara.contenttypes import get_content_type_for_model

        content_type = await get_content_type_for_model(value.__class__)
        instance._data[self.content_type_field] = content_type.id
        instance._data[self.object_id_field] = str(value.id)
        instance._generic_fk_cache[self.name] = value


GenericForeignKeyField = GenericForeignKey


# =============================================================================
# ManyToMany Manager
# =============================================================================


class ManyToManyManager:
    """
    Manager for ManyToMany relationships.
    
    Provides methods to add, remove, clear, and list related objects.
    
    Usage:
        # Add tags to a post
        await post.tags.add(tag1, tag2, tag3)
        
        # Get all tags for a post
        tags = await post.tags.all()
        
        # Remove specific tags
        await post.tags.remove(tag1)
        
        # Clear all tags
        await post.tags.clear()
    """
    
    def __init__(
        self,
        field: ManyToMany,
        source_instance: "Model",
    ):
        """
        Initialize the manager.
        
        Args:
            field: The ManyToMany field definition
            source_instance: The model instance this manager is attached to
        """
        self._field = field
        self._source = source_instance
    
    @property
    def _join_table(self) -> str:
        return self._field.join_table_name
    
    @property
    def _source_col(self) -> str:
        return self._field.source_column
    
    @property
    def _target_col(self) -> str:
        return self._field.target_column
    
    @property
    def _target_model(self) -> Type["Model"]:
        return self._field.to_model
    
    async def add(self, *instances: "Model") -> None:
        """
        Add instances to the relationship.
        
        Args:
            *instances: Model instances to add
        """
        from aksara.db import Database, quote_identifier
        
        if not instances:
            return
        
        db = Database.get_instance()
        source_id = self._source.id
        join_table = quote_identifier(self._join_table)
        
        for instance in instances:
            target_id = instance.id
            
            # Insert into join table (ignore if already exists)
            query = f"""
                INSERT INTO {join_table} ({self._source_col}, {self._target_col})
                VALUES ($1, $2)
                ON CONFLICT ({self._source_col}, {self._target_col}) DO NOTHING
            """
            await db.execute(query, source_id, target_id)
    
    async def remove(self, *instances: "Model") -> None:
        """
        Remove instances from the relationship.
        
        Args:
            *instances: Model instances to remove
        """
        from aksara.db import Database, quote_identifier
        
        if not instances:
            return
        
        db = Database.get_instance()
        source_id = self._source.id
        join_table = quote_identifier(self._join_table)
        
        for instance in instances:
            target_id = instance.id
            
            query = f"""
                DELETE FROM {join_table}
                WHERE {self._source_col} = $1 AND {self._target_col} = $2
            """
            await db.execute(query, source_id, target_id)
    
    async def clear(self) -> None:
        """Remove all instances from the relationship."""
        from aksara.db import Database, quote_identifier
        
        db = Database.get_instance()
        source_id = self._source.id
        join_table = quote_identifier(self._join_table)
        
        query = f"""
            DELETE FROM {join_table}
            WHERE {self._source_col} = $1
        """
        await db.execute(query, source_id)
    
    async def all(self) -> List["Model"]:
        """
        Get all related instances.
        
        Returns:
            List of related model instances
        """
        from aksara.db import Database, quote_identifier
        
        db = Database.get_instance()
        source_id = self._source.id
        target_model = self._target_model
        target_table = quote_identifier(target_model.__tablename__)
        join_table = quote_identifier(self._join_table)
        
        query = f"""
            SELECT t.* FROM {target_table} t
            INNER JOIN {join_table} j ON t.id = j.{self._target_col}
            WHERE j.{self._source_col} = $1
        """
        
        records = await db.fetch(query, source_id)
        return [target_model._from_record(r) for r in records]
    
    async def count(self) -> int:
        """
        Count related instances.
        
        Returns:
            Number of related instances
        """
        from aksara.db import Database, quote_identifier
        
        db = Database.get_instance()
        source_id = self._source.id
        join_table = quote_identifier(self._join_table)
        
        query = f"""
            SELECT COUNT(*) FROM {join_table}
            WHERE {self._source_col} = $1
        """
        
        count = await db.fetchval(query, source_id)
        return count or 0
    
    async def set(self, instances: List["Model"]) -> None:
        """
        Replace all related instances with the given list.
        
        Args:
            instances: List of model instances to set
        """
        await self.clear()
        if instances:
            await self.add(*instances)
    
    async def ids(self) -> List[uuid_lib.UUID]:
        """
        Get IDs of all related instances.
        
        Returns:
            List of UUIDs of related instances
        """
        from aksara.db import Database, quote_identifier
        
        db = Database.get_instance()
        source_id = self._source.id
        join_table = quote_identifier(self._join_table)
        
        query = f"""
            SELECT {self._target_col} FROM {join_table}
            WHERE {self._source_col} = $1
        """
        
        records = await db.fetch(query, source_id)
        return [r[self._target_col] for r in records]
