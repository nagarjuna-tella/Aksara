"""
Vidyut Field Types

Field definitions for model columns with PostgreSQL type mappings.
"""

from __future__ import annotations

import json
import uuid as uuid_lib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional, Type, Union, Callable


class Field(ABC):
    """
    Base class for all field types.
    
    All fields support these common arguments:
        - nullable: Whether the field can be NULL (default: False)
        - default: Default value for the field
        - unique: Whether the field should have a UNIQUE constraint
        - primary_key: Whether this field is the primary key
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
    ):
        self.nullable = nullable
        self.default = default
        self.unique = unique
        self.primary_key = primary_key
        
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
    """
    
    def __init__(
        self,
        max_length: int = 255,
        *,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
    ):
        super().__init__(nullable=nullable, default=default, unique=unique)
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
    """
    
    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
    ):
        super().__init__(nullable=nullable, default=default, unique=unique)
    
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
    """
    
    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Any = None,
    ):
        super().__init__(nullable=nullable, default=default)
    
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
    """
    
    def __init__(
        self,
        *,
        auto_now: bool = False,
        auto_now_add: bool = False,
        nullable: bool = False,
    ):
        super().__init__(nullable=nullable)
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
    """
    
    def __init__(
        self,
        *,
        primary_key: bool = False,
        nullable: bool = False,
        default: Any = None,
    ):
        # If primary_key and no default, auto-generate UUIDs
        if primary_key and default is None:
            default = uuid_lib.uuid4
        super().__init__(primary_key=primary_key, nullable=nullable, default=default)
    
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
    """
    
    def __init__(
        self,
        *,
        nullable: bool = True,
        default: Any = None,
    ):
        super().__init__(nullable=nullable, default=default)
    
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


# Convenience aliases
StringField = String
IntegerField = Integer
BooleanField = Boolean
DateTimeField = DateTime
UUIDField = UUID
JSONField = JSON
