"""
Aksara Field Types

Field definitions for model columns with PostgreSQL type mappings.

NOTE:
These are runtime model fields used by the ORM (Model, QuerySet, etc.).
Migration field operations live separately in aksara.migrations.operations.
If you change behavior or supported options here, check if migrations also need updates.
"""

from __future__ import annotations

import json
import re
import uuid as uuid_lib
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal as PyDecimal, InvalidOperation
from enum import Enum as PyEnum
from typing import Any, Optional, Type, Union, Callable, TYPE_CHECKING, List

if TYPE_CHECKING:
    from aksara.model.base import Model
    from aksara.relations import OnDelete as OnDeleteType


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

# URL validation regex (http/https only)
URL_REGEX = re.compile(
    r"^https?://[^\s/$.?#].[^\s]*$",
    re.IGNORECASE
)


class Field(ABC):
    """
    Base class for all field types.
    
    All fields support these common arguments:
        - nullable: Whether the field can be NULL (default: False)
        - default: Default value for the field
        - unique: Whether the field should have a UNIQUE constraint
        - primary_key: Whether this field is the primary key
        
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
        # AI metadata
        ai_description: Optional[str] = None,
        ai_sensitive: bool = False,
        ai_agent_writable: bool = True,
    ):
        self.nullable = nullable
        self.default = default
        self.unique = unique
        self.primary_key = primary_key
        
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


class String(Field):
    """
    String field mapping to VARCHAR.
    
    Args:
        max_length: Maximum string length (default: 255)
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    """
    
    def __init__(
        self,
        max_length: int = 255,
        *,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
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
    
    def to_python(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)
    
    def to_db(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)


class Integer(Field):
    """
    Integer field mapping to INTEGER.
    
    Args:
        nullable: Whether the field can be NULL
        default: Default value
        unique: Whether the field should be unique
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
        return "INTEGER"
    
    def to_python(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        return int(value)
    
    def to_db(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        return int(value)


class Boolean(Field):
    """
    Boolean field mapping to BOOLEAN.
    
    Args:
        nullable: Whether the field can be NULL
        default: Default value
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    """
    
    def __init__(
        self,
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
    
    @property
    def sql_type(self) -> str:
        return "BOOLEAN"
    
    def to_python(self, value: Any) -> Optional[bool]:
        if value is None:
            return None
        return bool(value)
    
    def to_db(self, value: Any) -> Optional[bool]:
        if value is None:
            return None
        return bool(value)


class DateTime(Field):
    """
    DateTime field mapping to TIMESTAMP WITH TIME ZONE.
    
    Args:
        auto_now: Automatically set to current time on every save
        auto_now_add: Automatically set to current time on creation
        nullable: Whether the field can be NULL
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
        self.auto_now = auto_now
        self.auto_now_add = auto_now_add
    
    @property
    def sql_type(self) -> str:
        return "TIMESTAMP WITH TIME ZONE"
    
    def get_column_definition(self) -> str:
        """Generate the SQL column definition with default for auto_now_add."""
        parts = [self.name, self.sql_type]
        
        if not self.nullable:
            parts.append("NOT NULL")
        
        if self.auto_now_add:
            parts.append("DEFAULT CURRENT_TIMESTAMP")
        
        return " ".join(parts)
    
    def to_python(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        return value
    
    def to_db(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None
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
        elif not self.nullable:
            parts.append("NOT NULL")
        
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
ArrayField = Array


# =============================================================================
# v0.3.5: New Field Types
# =============================================================================


class Text(Field):
    """
    Text field mapping to TEXT (unlimited length string).
    
    Use this for long-form text content instead of String when you don't
    need a maximum length constraint.
    
    Args:
        nullable: Whether the field can be NULL
        default: Default value
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    """
    
    def __init__(
        self,
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
        return str(value)


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
        except InvalidOperation:
            raise ValueError(f"Invalid decimal value: {value}")
        
        # Check precision
        sign, digits, exponent = dec.as_tuple()
        integer_digits = len(digits) + min(exponent, 0)
        
        if integer_digits > (self.max_digits - self.decimal_places):
            raise ValueError(
                f"Decimal value {value} exceeds maximum integer digits "
                f"({self.max_digits - self.decimal_places})"
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
        self.enum_class = enum_class
    
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
        # Normalize on_delete to string (handles both string and OnDelete enum)
        self.on_delete = on_delete.upper() if isinstance(on_delete, str) else str(on_delete)
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
                if name.endswith('y'):
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
            column_name=column_name,
            on_delete=on_delete,
            nullable=nullable,
            ai_description=ai_description,
            ai_sensitive=ai_sensitive,
            ai_agent_writable=ai_agent_writable,
        )
        self.related_name = related_name
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
            singular = table_name.rstrip('s')
            if table_name.endswith('ies'):
                singular = table_name[:-3] + 'y'
            return f"{singular}_id"
        return "source_id"
    
    @property
    def target_column(self) -> str:
        """Get the target column name in join table."""
        try:
            target_table = self.to_model.__tablename__
            singular = target_table.rstrip('s')
            if target_table.endswith('ies'):
                singular = target_table[:-3] + 'y'
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
                if name.endswith('y'):
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
