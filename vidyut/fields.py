"""
Vidyut Field Types

Field definitions for model columns with PostgreSQL type mappings.
"""

from __future__ import annotations

import json
import uuid as uuid_lib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional, Type, Union, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from vidyut.model.base import Model


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


# Convenience aliases
StringField = String
IntegerField = Integer
BooleanField = Boolean
DateTimeField = DateTime
UUIDField = UUID
JSONField = JSON


class ForeignKey(Field):
    """
    Foreign key field that references another model.
    
    Creates a column that stores the primary key of the referenced model
    and adds a FOREIGN KEY constraint.
    
    Args:
        to: The model class being referenced (or string name for lazy reference)
        column_name: Name for the FK column (default: "{field_name}_id")
        on_delete: Action on delete ("CASCADE", "SET NULL", "RESTRICT", etc.)
        nullable: Whether the field can be NULL
        ai_description: Description for AI agents
        ai_sensitive: Whether field contains sensitive data
        ai_agent_writable: Whether AI agents can modify this
    
    Usage:
        class Post(Model):
            author = fields.ForeignKey(User)  # Creates author_id column
            
        # Access the FK value
        post.author_id  # The UUID of the referenced User
    """
    
    def __init__(
        self,
        to: Union[Type["Model"], str],
        *,
        column_name: Optional[str] = None,
        on_delete: str = "CASCADE",
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
        self.on_delete = on_delete
        
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
            from vidyut.registry import ModelRegistry
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
        # Default to UUID (most common PK type in Vidyut)
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
        
        return f"CONSTRAINT {constraint_name} FOREIGN KEY ({col_name}) REFERENCES {target_table}(id) ON DELETE {self.on_delete}"
    
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
