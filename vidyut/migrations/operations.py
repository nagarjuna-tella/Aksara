"""
Vidyut Migration Operations

Defines all operation classes for schema changes:
- Field operations (UUIDField, StringField, etc.) for SQL generation
- Table operations (CreateTable, DropTable)
- Column operations (AddField, RemoveField, AlterFieldType)
- Index operations (AddIndex, RemoveIndex)
- Raw SQL escape hatch (RunSQL)
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# =============================================================================
# Field Operations - For SQL Generation
# =============================================================================

class FieldOp(ABC):
    """
    Base class for field type definitions used in migrations.
    
    These are NOT the runtime Field classes from vidyut.fields.
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
                parts.append(f"DEFAULT '{self.default}'")
        
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
            parts.append(f"DEFAULT '{self.default}'")
        
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
            parts.append(f"DEFAULT '{self.default}'")
        
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
        import json as json_lib
        
        parts = ["JSONB"]
        
        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            if isinstance(self.default, (dict, list)):
                parts.append(f"DEFAULT '{json_lib.dumps(self.default)}'::jsonb")
            else:
                parts.append(f"DEFAULT '{self.default}'::jsonb")
        
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return "JSONField()"


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
        nullable: bool = False,
        default: Optional[str] = None,
    ):
        self.allowed_values = allowed_values or []
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
    
    def get_constraint_sql(self, column_name: str) -> str:
        """Generate the FOREIGN KEY constraint SQL."""
        return (
            f"CONSTRAINT fk_{column_name} "
            f"FOREIGN KEY ({column_name}) "
            f"REFERENCES {self.to_table}({self.to_column}) "
            f"ON DELETE {self.on_delete} ON UPDATE {self.on_update}"
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
        return f'''CREATE TABLE IF NOT EXISTS "{self.join_table_name}" (
    "id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "source_id" UUID NOT NULL,
    "target_id" UUID NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_{self.join_table_name}_source 
        FOREIGN KEY (source_id) REFERENCES "{self.source_table}"({self.source_column}) ON DELETE CASCADE,
    CONSTRAINT fk_{self.join_table_name}_target 
        FOREIGN KEY (target_id) REFERENCES "{self.target_table}"({self.target_column}) ON DELETE CASCADE,
    UNIQUE (source_id, target_id)
)'''
    
    def get_drop_join_table_sql(self) -> str:
        """Generate DROP TABLE SQL for the join table."""
        return f'DROP TABLE IF EXISTS "{self.join_table_name}" CASCADE'
    
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
    
    def get_constraint_sql(self, column_name: str) -> str:
        """Generate the FOREIGN KEY constraint SQL."""
        return (
            f"CONSTRAINT fk_{column_name} "
            f"FOREIGN KEY ({column_name}) "
            f"REFERENCES {self.to_table}({self.to_column}) "
            f"ON DELETE {self.on_delete} ON UPDATE {self.on_update}"
        )
    
    def __repr__(self) -> str:
        return f"ForeignKeyField(to_table='{self.to_table}')"


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
        self.where = where
        self.method = method
    
    def to_sql(self) -> str:
        """Generate CREATE INDEX SQL."""
        unique_str = "UNIQUE " if self.unique else ""
        cols = ", ".join(f'"{c}"' for c in self.columns)
        sql = f'CREATE {unique_str}INDEX "{self.name}" ON "{self.table}" USING {self.method} ({cols})'
        
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
            connection: Database connection (asyncpg connection or Vidyut Database)
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
            columns.append(f'"{col_name}" {field.to_sql()}')
            
            # Handle ForeignKey constraints
            if isinstance(field, ForeignKeyField):
                constraints.append(field.get_constraint_sql(col_name))
        
        # Build CREATE TABLE SQL
        all_parts = columns + constraints
        columns_sql = ",\n    ".join(all_parts)
        
        exists_clause = "IF NOT EXISTS " if self.if_not_exists else ""
        sql = f'CREATE TABLE {exists_clause}"{self.name}" (\n    {columns_sql}\n)'
        
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
        sql = f'''CREATE TABLE IF NOT EXISTS "{self.join_table_name}" (
    "id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "source_id" UUID NOT NULL,
    "target_id" UUID NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_{self.join_table_name}_source 
        FOREIGN KEY (source_id) REFERENCES "{self.source_table}"({self.source_column}) ON DELETE CASCADE,
    CONSTRAINT fk_{self.join_table_name}_target 
        FOREIGN KEY (target_id) REFERENCES "{self.target_table}"({self.target_column}) ON DELETE CASCADE,
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
        sql = f'DROP TABLE {exists_clause}"{self.name}"{cascade_clause}'
        
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
        sql = f'ALTER TABLE "{self.old_name}" RENAME TO "{self.new_name}"'
        
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
        sql = f'ALTER TABLE "{self.table}" ADD COLUMN "{self.name}" {self.field.to_sql()}'
        
        # Handle ForeignKey constraints
        if isinstance(self.field, ForeignKeyField):
            constraint_sql = self.field.get_constraint_sql(self.name)
            sql += f';\nALTER TABLE "{self.table}" ADD {constraint_sql}'
        
        if hasattr(connection, 'execute'):
            await connection.execute(sql)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")
    
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
        sql = f'ALTER TABLE "{self.table}" DROP COLUMN {exists_clause}"{self.name}"'
        
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
        # Extract just the type from the field definition
        type_sql = self.new_field.to_sql().split()[0]  # First word is the type
        
        using_clause = f" USING {self.using}" if self.using else ""
        sql = f'ALTER TABLE "{self.table}" ALTER COLUMN "{self.name}" TYPE {type_sql}{using_clause}'
        
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
        sql = f'ALTER TABLE "{self.table}" RENAME COLUMN "{self.old_name}" TO "{self.new_name}"'
        
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
            sql = f'ALTER TABLE "{self.table}" ALTER COLUMN "{self.name}" DROP NOT NULL'
        else:
            sql = f'ALTER TABLE "{self.table}" ALTER COLUMN "{self.name}" SET NOT NULL'
        
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
        drop_default: bool = False,
    ):
        self.table = table
        self.name = name
        self.new_default = new_default
        self.drop_default = drop_default
    
    async def apply(self, connection) -> None:
        """Alter the column's default value."""
        if self.drop_default:
            sql = f'ALTER TABLE "{self.table}" ALTER COLUMN "{self.name}" DROP DEFAULT'
        else:
            # Format the default value
            if self.new_default is None:
                default_sql = "NULL"
            elif isinstance(self.new_default, bool):
                default_sql = "TRUE" if self.new_default else "FALSE"
            elif isinstance(self.new_default, str):
                escaped = self.new_default.replace("'", "''")
                default_sql = f"'{escaped}'"
            elif isinstance(self.new_default, (int, float)):
                default_sql = str(self.new_default)
            else:
                default_sql = str(self.new_default)
            
            sql = f'ALTER TABLE "{self.table}" ALTER COLUMN "{self.name}" SET DEFAULT {default_sql}'
        
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
        
        # Add CONCURRENTLY if requested (note: can't be used in transaction)
        if self.concurrently:
            sql = sql.replace("CREATE ", "CREATE CONCURRENTLY ", 1)
        
        # Add IF NOT EXISTS
        if self.if_not_exists:
            sql = sql.replace("INDEX ", "INDEX IF NOT EXISTS ", 1)
        
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
        sql = f'DROP INDEX {concurrent_clause}{exists_clause}"{self.name}"'
        
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
        sql = f'ALTER TABLE "{self.table}" ADD CONSTRAINT "{self.name}" {self.constraint_sql}'
        
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
        sql = f'ALTER TABLE "{self.table}" DROP CONSTRAINT "{self.name}"'
        
        if hasattr(connection, 'execute'):
            try:
                await connection.execute(sql)
            except Exception as e:
                if self.if_exists and "does not exist" in str(e).lower():
                    pass  # Ignore if it doesn't exist
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
            allow_dangerous = os.environ.get("VIDYUT_ALLOW_DANGEROUS_MIGRATIONS", "").lower()
            if allow_dangerous not in ("1", "true", "yes"):
                logger.warning(
                    f"⚠️  DANGEROUS MIGRATION DETECTED: {self.sql[:100]}..."
                    f"\nSet VIDYUT_ALLOW_DANGEROUS_MIGRATIONS=1 to allow."
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
    "BooleanField",
    "DateTimeField",
    "DateField",
    "JSONField",
    "FloatField",
    "DecimalField",
    "ForeignKeyField",
    # v0.3.5: New field types
    "EmailField",
    "URLField",
    "EnumField",
    "OneToOneField",
    "ManyToManyField",
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
