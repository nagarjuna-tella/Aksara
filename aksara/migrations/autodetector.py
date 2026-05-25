"""
Aksara Migration Autodetector

Compares the current model state against existing migration state to determine
what changes need to be made. Generates only the operations needed for the delta.

This is the core of `aksara makemigrations` — it prevents duplicate/empty
migrations by computing a diff between "what migrations say the DB should
look like" and "what the current models say the DB should look like."

v0.5.26: Initial implementation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Type

from aksara.migrations.base import Migration

logger = logging.getLogger(__name__)


# =============================================================================
# State Representation
# =============================================================================

@dataclass
class FieldState:
    """Represents the state of a single field/column in a table."""
    name: str
    field_type: str  # e.g. "UUIDField", "StringField", "ForeignKeyField"
    primary_key: bool = False
    nullable: bool = False
    unique: bool = False
    default: Any = None
    max_length: Optional[int] = None
    auto_now: bool = False
    auto_now_add: bool = False
    # FK specific
    references_table: Optional[str] = None
    on_delete: Optional[str] = None
    # Decimal specific
    max_digits: Optional[int] = None
    decimal_places: Optional[int] = None
    # Enum specific
    enum_name: Optional[str] = None
    # Vector specific
    dimensions: Optional[int] = None
    # Array specific
    array_sql_type: Optional[str] = None

    def to_key(self) -> tuple:
        """Return a hashable representation for comparison."""
        return (
            self.name,
            self.field_type,
            self.primary_key,
            self.nullable,
            self.unique,
            self.default,
            self.max_length,
            self.auto_now,
            self.auto_now_add,
            self.references_table,
            self.on_delete,
            self.max_digits,
            self.decimal_places,
            self.enum_name,
            self.dimensions,
            self.array_sql_type,
        )


@dataclass
class TableState:
    """Represents the state of a single table."""
    name: str
    fields: Dict[str, FieldState] = dc_field(default_factory=dict)

    def field_names(self) -> Set[str]:
        return set(self.fields.keys())


@dataclass
class ProjectState:
    """Represents the complete database schema state."""
    tables: Dict[str, TableState] = dc_field(default_factory=dict)

    def table_names(self) -> Set[str]:
        return set(self.tables.keys())


# =============================================================================
# Build State from Existing Migrations
# =============================================================================

def _field_op_to_state(field_name: str, field_op) -> FieldState:
    """Convert a migration FieldOp to a FieldState."""
    from aksara.migrations import operations as op

    field_type = type(field_op).__name__

    state = FieldState(
        name=field_name,
        field_type=field_type,
        primary_key=getattr(field_op, 'primary_key', False),
        nullable=getattr(field_op, 'nullable', False),
        unique=getattr(field_op, 'unique', False),
        default=getattr(field_op, 'default', None),
        max_length=getattr(field_op, 'max_length', None),
        auto_now=getattr(field_op, 'auto_now', False),
        auto_now_add=getattr(field_op, 'auto_now_add', False),
    )

    # FK/O2O specific
    if isinstance(field_op, (op.ForeignKeyField, op.OneToOneField)):
        state.references_table = getattr(field_op, 'to_table', None)
        state.on_delete = getattr(field_op, 'on_delete', 'CASCADE')

    # Decimal specific
    if isinstance(field_op, op.DecimalField):
        state.max_digits = getattr(field_op, 'max_digits', None)
        state.decimal_places = getattr(field_op, 'decimal_places', None)

    # Enum specific
    if isinstance(field_op, op.EnumField):
        state.enum_name = getattr(field_op, 'enum_name', None) or getattr(field_op, 'enum_class', None)

    # Vector specific
    if isinstance(field_op, op.VectorField):
        state.dimensions = getattr(field_op, 'dimensions', None)

    if isinstance(field_op, op.ArrayField):
        state.array_sql_type = getattr(field_op, 'sql_type', None)

    return state


def build_state_from_migrations(
    migration_files: List[Tuple[str, Path]],
) -> ProjectState:
    """
    Replay all migration operations to build the current migration state.

    This reads each migration file, instantiates it, and applies its
    operations to a virtual state (no database involved).

    Args:
        migration_files: List of (name, path) tuples for migration files

    Returns:
        ProjectState representing what the DB schema should look like
        based on the existing migrations.
    """
    from aksara.migrations.executor import load_migration_module
    from aksara.migrations import operations as op

    state = ProjectState()

    for name, path in migration_files:
        if path.suffix != ".py":
            # Can't replay SQL migrations — skip but log
            logger.debug(f"Skipping SQL migration for state replay: {name}")
            continue

        try:
            migration_class = load_migration_module(path)
            migration = migration_class()
        except Exception as e:
            logger.warning(f"Could not load migration {name} for state replay: {e}")
            continue

        for operation in migration.operations:
            _apply_operation_to_state(state, operation)

    return state


def _apply_operation_to_state(state: ProjectState, operation) -> None:
    """Apply a single migration operation to the virtual state."""
    from aksara.migrations import operations as op

    if isinstance(operation, op.CreateTable):
        table = TableState(name=operation.name)
        for field_name, field_op in operation.fields:
            table.fields[field_name] = _field_op_to_state(field_name, field_op)
        state.tables[operation.name] = table

    elif isinstance(operation, op.DropTable):
        state.tables.pop(operation.name, None)

    elif isinstance(operation, op.RenameTable):
        if operation.old_name in state.tables:
            table = state.tables.pop(operation.old_name)
            table.name = operation.new_name
            state.tables[operation.new_name] = table

    elif isinstance(operation, op.AddField):
        table_name = operation.table
        if table_name in state.tables:
            field_state = _field_op_to_state(operation.name, operation.field)
            state.tables[table_name].fields[operation.name] = field_state

    elif isinstance(operation, op.RemoveField):
        table_name = operation.table
        if table_name in state.tables:
            state.tables[table_name].fields.pop(operation.name, None)

    elif isinstance(operation, op.RenameField):
        table_name = operation.table
        if table_name in state.tables:
            table = state.tables[table_name]
            if operation.old_name in table.fields:
                field = table.fields.pop(operation.old_name)
                field.name = operation.new_name
                table.fields[operation.new_name] = field

    elif isinstance(operation, op.AlterFieldType):
        # We can't fully track type changes without parsing the SQL type
        # back to a FieldOp. Mark the field type as changed.
        table_name = operation.table
        if table_name in state.tables:
            field = state.tables[table_name].fields.get(operation.name)
            if field:
                # Update the field type based on the new SQL type/field
                new_field = getattr(operation, 'new_field', None)
                if new_field:
                    state.tables[table_name].fields[operation.name] = \
                        _field_op_to_state(operation.name, new_field)

    elif isinstance(operation, op.AlterFieldNull):
        table_name = operation.table
        if table_name in state.tables:
            field = state.tables[table_name].fields.get(operation.name)
            if field:
                field.nullable = operation.nullable

    elif isinstance(operation, op.AlterFieldDefault):
        table_name = operation.table
        if table_name in state.tables:
            field = state.tables[table_name].fields.get(operation.name)
            if field:
                field.default = getattr(operation, 'new_default', None)

    # CreateManyToManyTable, AddIndex, RemoveIndex, AddConstraint,
    # RemoveConstraint, RunSQL, SeparateDatabaseAndState —
    # these don't affect the field-level state we track.


# =============================================================================
# Build State from Current Models
# =============================================================================

def _model_field_to_state(field_name: str, field) -> FieldState:
    """Convert a runtime Aksara field to a FieldState."""
    from aksara.fields import (
        String, Integer, Boolean, DateTime, UUID, JSON,
        ForeignKey, OneToOne,
        Text, Email, URL, Decimal, Enum, Float, Date, Array,
        Vector,
        FileField as RuntimeFileField,
        ImageField as RuntimeImageField,
        Slug, SmallInteger, BigInteger,
        PositiveInteger, PositiveSmallInteger, PositiveBigInteger,
        Time, Duration, IPAddress, Binary, FilePath,
    )

    # Map runtime field classes to migration operation names
    type_map = {
        UUID: "UUIDField",
        String: "StringField",
        Text: "TextField",
        Integer: "IntegerField",
        Boolean: "BooleanField",
        DateTime: "DateTimeField",
        Date: "DateField",
        JSON: "JSONField",
        Vector: "VectorField",
        Float: "FloatField",
        Decimal: "DecimalField",
        Email: "EmailField",
        RuntimeFileField: "FileField",
        RuntimeImageField: "ImageField",
        URL: "URLField",
        Enum: "EnumField",
        OneToOne: "OneToOneField",
        ForeignKey: "ForeignKeyField",
        Array: "ArrayField",
        # Extended fields (Django parity)
        Slug: "SlugField",
        SmallInteger: "SmallIntegerField",
        BigInteger: "BigIntegerField",
        PositiveInteger: "IntegerField",
        PositiveSmallInteger: "SmallIntegerField",
        PositiveBigInteger: "BigIntegerField",
        Time: "TimeField",
        Duration: "DurationField",
        IPAddress: "IPAddressField",
        Binary: "BinaryField",
        FilePath: "FilePathField",
    }

    # OneToOne must be checked before ForeignKey (it inherits from FK)
    if isinstance(field, OneToOne):
        field_type = "OneToOneField"
    elif isinstance(field, RuntimeImageField):
        field_type = "ImageField"
    elif isinstance(field, RuntimeFileField):
        field_type = "FileField"
    elif isinstance(field, Email):
        field_type = "EmailField"
    elif isinstance(field, URL):
        field_type = "URLField"
    else:
        field_type = "StringField"  # default fallback for unknown field types
        for cls, name in type_map.items():
            if isinstance(field, cls):
                field_type = name
                break

    state = FieldState(
        name=field_name,
        field_type=field_type,
        primary_key=getattr(field, 'primary_key', False),
        nullable=getattr(field, 'nullable', False),
        unique=getattr(field, 'unique', False),
        default=_normalize_default(getattr(field, 'default', None)),
        max_length=getattr(field, 'max_length', None),
        auto_now=getattr(field, 'auto_now', False),
        auto_now_add=getattr(field, 'auto_now_add', False),
    )

    # FK specific — use the actual DB column name for FK fields
    if isinstance(field, (ForeignKey, OneToOne)):
        try:
            target_model = field.to_model
            state.references_table = (
                getattr(target_model, '__tablename__', None)
                or getattr(target_model, '_table_name', 'unknown')
            )
        except Exception:
            state.references_table = "unknown"
        state.on_delete = getattr(field, 'on_delete', 'CASCADE')

    # Decimal specific
    if isinstance(field, Decimal):
        state.max_digits = getattr(field, 'max_digits', None)
        state.decimal_places = getattr(field, 'decimal_places', None)

    # Enum specific
    if isinstance(field, Enum):
        enum_cls = getattr(field, 'enum_class', None)
        state.enum_name = enum_cls.__name__ if enum_cls else None

    if isinstance(field, Vector):
        state.dimensions = getattr(field, 'dimensions', None)

    if isinstance(field, Array):
        state.array_sql_type = getattr(field, 'sql_type', None)

    return state


def _normalize_default(default):
    """Normalize a default value for comparison.
    
    Callables (auto_now, uuid4, etc.) are normalized to None since
    they can't be meaningfully compared.
    """
    if callable(default):
        return None
    return default


def _get_table_name_for_model(model_class) -> str:
    """Get the table name for a model class."""
    table_name = (
        getattr(model_class, '__tablename__', None)
        or getattr(model_class, '_table_name', None)
    )
    if not table_name:
        # Generate from class name (same logic as model/base.py pluralize)
        name = model_class.__name__.lower()
        if name.endswith('y') and len(name) > 1 and name[-2] not in 'aeiou':
            table_name = name[:-1] + 'ies'
        elif name.endswith(('s', 'x', 'z', 'ch', 'sh')):
            table_name = name + 'es'
        else:
            table_name = name + 's'
    return table_name


def build_state_from_models(models: Dict[str, type]) -> ProjectState:
    """
    Build a ProjectState from the current model definitions.

    Args:
        models: Dict of model_name -> model_class from ModelRegistry

    Returns:
        ProjectState representing what the DB schema should look like
        based on the current model definitions.
    """
    from aksara.fields import ForeignKey, OneToOne

    state = ProjectState()

    for model_name, model_class in models.items():
        table_name = _get_table_name_for_model(model_class)

        table = TableState(name=table_name)

        for field_name, field in model_class._fields.items():
            # For FK/O2O, use the DB column name (e.g., author_id)
            if isinstance(field, (ForeignKey, OneToOne)):
                col_name = field.db_column_name
            else:
                col_name = field_name

            table.fields[col_name] = _model_field_to_state(col_name, field)

        state.tables[table_name] = table

    return state


# =============================================================================
# Diff Engine
# =============================================================================

@dataclass
class MigrationDiff:
    """The result of diffing migration state vs model state."""
    new_tables: List[str] = dc_field(default_factory=list)
    removed_tables: List[str] = dc_field(default_factory=list)
    # Per-table field changes: table_name -> list of changes
    added_fields: Dict[str, List[str]] = dc_field(default_factory=dict)
    removed_fields: Dict[str, List[str]] = dc_field(default_factory=dict)
    altered_fields: Dict[str, List[str]] = dc_field(default_factory=dict)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.new_tables
            or self.removed_tables
            or self.added_fields
            or self.removed_fields
            or self.altered_fields
        )


def diff_states(
    migration_state: ProjectState,
    model_state: ProjectState,
) -> MigrationDiff:
    """
    Compute the diff between migration state and model state.

    Args:
        migration_state: What the DB should look like based on existing migrations
        model_state: What the DB should look like based on current models

    Returns:
        MigrationDiff describing what operations are needed
    """
    result = MigrationDiff()

    migration_tables = migration_state.table_names()
    model_tables = model_state.table_names()

    # New tables (in models but not in migrations)
    result.new_tables = sorted(model_tables - migration_tables)

    # Removed tables (in migrations but not in models)
    result.removed_tables = sorted(migration_tables - model_tables)

    # Tables that exist in both — check for field-level changes
    common_tables = migration_tables & model_tables
    for table_name in sorted(common_tables):
        mig_table = migration_state.tables[table_name]
        mod_table = model_state.tables[table_name]

        mig_fields = mig_table.field_names()
        mod_fields = mod_table.field_names()

        # Added fields
        added = sorted(mod_fields - mig_fields)
        if added:
            result.added_fields[table_name] = added

        # Removed fields
        removed = sorted(mig_fields - mod_fields)
        if removed:
            result.removed_fields[table_name] = removed

        # Altered fields (same name but different state)
        common_fields = mig_fields & mod_fields
        altered = []
        for field_name in sorted(common_fields):
            mig_field = mig_table.fields[field_name]
            mod_field = mod_table.fields[field_name]
            if mig_field.to_key() != mod_field.to_key():
                altered.append(field_name)
        if altered:
            result.altered_fields[table_name] = altered

    return result


# =============================================================================
# Generate Operations from Diff
# =============================================================================

def _model_field_to_op(field_name: str, field):
    """Convert a runtime Aksara field to a migration FieldOp instance."""
    from aksara.fields import (
        String, Integer, Boolean, DateTime, UUID, JSON,
        ForeignKey, OneToOne,
        Text, Email, URL, Decimal, Enum, Float, Date, Array,
        Vector,
        FileField as RuntimeFileField,
        ImageField as RuntimeImageField,
        Slug, SmallInteger, BigInteger,
        PositiveInteger, PositiveSmallInteger, PositiveBigInteger,
        Time, Duration, IPAddress, Binary, FilePath,
    )
    from aksara.migrations import operations as op

    if isinstance(field, UUID):
        if field.primary_key:
            return op.UUIDField(primary_key=True)
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        return op.UUIDField(**kwargs)

    elif isinstance(field, OneToOne):
        try:
            target_model = field.to_model
            target_table = (
                getattr(target_model, '__tablename__', None)
                or getattr(target_model, '_table_name', 'unknown')
            )
        except Exception:
            target_table = "unknown"
        kwargs = {'on_delete': field.on_delete}
        if field.nullable:
            kwargs['nullable'] = True
        return op.OneToOneField(target_table, **kwargs)

    elif isinstance(field, RuntimeImageField):
        kwargs = {}
        if hasattr(field, 'max_length') and field.max_length:
            kwargs['max_length'] = field.max_length
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.ImageField(**kwargs)

    elif isinstance(field, RuntimeFileField):
        kwargs = {}
        if hasattr(field, 'max_length') and field.max_length:
            kwargs['max_length'] = field.max_length
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.FileField(**kwargs)

    elif isinstance(field, Email):
        kwargs = {}
        if hasattr(field, 'max_length') and field.max_length:
            kwargs['max_length'] = field.max_length
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        return op.EmailField(**kwargs)

    elif isinstance(field, URL):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        return op.URLField(**kwargs)

    elif isinstance(field, Slug):
        kwargs = {'max_length': field.max_length}
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.SlugField(**kwargs)

    elif isinstance(field, SmallInteger):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.SmallIntegerField(**kwargs)

    elif isinstance(field, PositiveSmallInteger):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.SmallIntegerField(**kwargs)

    elif isinstance(field, PositiveInteger):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.IntegerField(**kwargs)

    elif isinstance(field, PositiveBigInteger):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.BigIntegerField(**kwargs)

    elif isinstance(field, Time):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        return op.TimeField(**kwargs)

    elif isinstance(field, Duration):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        return op.DurationField(**kwargs)

    elif isinstance(field, IPAddress):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        return op.IPAddressField(**kwargs)

    elif isinstance(field, Binary):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        return op.BinaryField(**kwargs)

    elif isinstance(field, FilePath):
        kwargs = {'max_length': field.max_length}
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.FilePathField(**kwargs)

    elif isinstance(field, String):
        kwargs = {'max_length': field.max_length}
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.StringField(**kwargs)

    elif isinstance(field, Text):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        return op.TextField(**kwargs)

    elif isinstance(field, BigInteger):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.BigIntegerField(**kwargs)

    elif isinstance(field, Integer):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.IntegerField(**kwargs)

    elif isinstance(field, Boolean):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.BooleanField(**kwargs)

    elif isinstance(field, DateTime):
        kwargs = {}
        if getattr(field, 'auto_now_add', False):
            kwargs['auto_now_add'] = True
        if getattr(field, 'auto_now', False):
            kwargs['auto_now'] = True
        if field.nullable:
            kwargs['nullable'] = True
        return op.DateTimeField(**kwargs)

    elif isinstance(field, Date):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        return op.DateField(**kwargs)

    elif isinstance(field, JSON):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.JSONField(**kwargs)

    elif isinstance(field, Vector):
        kwargs = {}
        if getattr(field, 'dimensions', None) is not None:
            kwargs['dimensions'] = field.dimensions
        if field.nullable:
            kwargs['nullable'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.VectorField(**kwargs)

    elif isinstance(field, Float):
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.FloatField(**kwargs)

    elif isinstance(field, Decimal):
        kwargs = {
            'max_digits': field.max_digits,
            'decimal_places': field.decimal_places,
        }
        if field.nullable:
            kwargs['nullable'] = True
        if field.unique:
            kwargs['unique'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.DecimalField(**kwargs)

    elif isinstance(field, Enum):
        enum_name = field.enum_class.__name__ if field.enum_class else 'Unknown'
        # Get allowed values from the enum class
        allowed_values = None
        if field.enum_class:
            try:
                allowed_values = [e.value for e in field.enum_class]
            except Exception:
                allowed_values = None
        kwargs = {'enum_name': enum_name}
        if field.nullable:
            kwargs['nullable'] = True
        default = _normalize_default(field.default)
        if default is not None:
            if hasattr(default, 'value'):
                kwargs['default'] = default.value
            else:
                kwargs['default'] = default
        return op.EnumField(allowed_values, **kwargs)

    elif isinstance(field, ForeignKey):
        try:
            target_model = field.to_model
            target_table = (
                getattr(target_model, '__tablename__', None)
                or getattr(target_model, '_table_name', 'unknown')
            )
        except Exception:
            target_table = "unknown"
        kwargs = {'on_delete': field.on_delete}
        if field.nullable:
            kwargs['nullable'] = True
        return op.ForeignKeyField(target_table, **kwargs)

    elif isinstance(field, Array):
        # Preserve PostgreSQL array semantics instead of downgrading to TEXT.
        kwargs = {}
        if field.nullable:
            kwargs['nullable'] = True
        default = _normalize_default(field.default)
        if default is not None:
            kwargs['default'] = default
        return op.ArrayField(getattr(field, 'sql_type', 'TEXT[]'), **kwargs)

    else:
        # Fallback
        kwargs = {}
        if hasattr(field, 'nullable') and field.nullable:
            kwargs['nullable'] = True
        return op.StringField(**kwargs)


def generate_operations_from_diff(
    diff: MigrationDiff,
    model_state: ProjectState,
    models: Dict[str, type],
    migration_state: Optional[ProjectState] = None,
) -> list:
    """
    Generate migration operations from a diff.

    Args:
        diff: The computed diff
        model_state: The model-based state (for field details)
        models: The actual model classes (for creating FieldOp instances)
        migration_state: The migration-based state (for altered field comparison)

    Returns:
        List of Operation instances
    """
    from aksara.migrations import operations as op
    from aksara.fields import ForeignKey, OneToOne
    from aksara.tenancy import build_disable_rls_sql, build_enable_rls_sql, is_tenant_model

    operations = []

    # 1. Create new tables
    # Build a table_name -> model_class mapping
    table_to_model = {}
    for model_name, model_class in models.items():
        tname = _get_table_name_for_model(model_class)
        table_to_model[tname] = model_class

    for table_name in diff.new_tables:
        model_class = table_to_model.get(table_name)
        if model_class is None:
            continue

        fields_list = []
        for field_name, field in model_class._fields.items():
            # For FK/O2O use DB column name
            if isinstance(field, (ForeignKey, OneToOne)):
                col_name = field.db_column_name
            else:
                col_name = field_name
            field_op = _model_field_to_op(col_name, field)
            fields_list.append((col_name, field_op))

        operations.append(op.CreateTable(name=table_name, fields=fields_list))

        if is_tenant_model(model_class):
            operations.append(
                op.RunSQL(
                    sql=build_enable_rls_sql(table_name),
                    reverse_sql=build_disable_rls_sql(table_name),
                )
            )

    # 2. Add fields to existing tables
    for table_name, added_fields in diff.added_fields.items():
        model_class = table_to_model.get(table_name)
        if model_class is None:
            continue

        for col_name in added_fields:
            # Find the corresponding runtime field
            runtime_field = None
            for fname, f in model_class._fields.items():
                if isinstance(f, (ForeignKey, OneToOne)):
                    if f.db_column_name == col_name:
                        runtime_field = f
                        break
                elif fname == col_name:
                    runtime_field = f
                    break

            if runtime_field is None:
                continue

            field_op = _model_field_to_op(col_name, runtime_field)
            operations.append(op.AddField(
                table=table_name,
                name=col_name,
                field=field_op,
            ))
            if col_name == "tenant_id" and is_tenant_model(model_class):
                operations.append(
                    op.RunSQL(
                        sql=build_enable_rls_sql(table_name),
                        reverse_sql=build_disable_rls_sql(table_name),
                    )
                )

    # 3. Remove fields from existing tables
    for table_name, removed_fields in diff.removed_fields.items():
        for col_name in removed_fields:
            operations.append(op.RemoveField(
                table=table_name,
                name=col_name,
            ))

    # 4. Alter fields (type, nullability, default changes)
    for table_name, altered_field_names in diff.altered_fields.items():
        model_class = table_to_model.get(table_name)
        if model_class is None:
            continue

        mig_table = migration_state.tables.get(table_name)
        mod_table = model_state.tables.get(table_name)
        if not mig_table or not mod_table:
            continue

        for col_name in altered_field_names:
            mig_field = mig_table.fields.get(col_name)
            mod_field = mod_table.fields.get(col_name)
            if not mig_field or not mod_field:
                continue

            runtime_field = None
            for fname, f in model_class._fields.items():
                if isinstance(f, (ForeignKey, OneToOne)):
                    if f.db_column_name == col_name:
                        runtime_field = f
                        break
                elif fname == col_name:
                    runtime_field = f
                    break

            # Determine what changed and generate appropriate operations
            if mig_field.field_type != mod_field.field_type:
                # Field type changed — generate AlterFieldType
                if runtime_field:
                    new_field_op = _model_field_to_op(col_name, runtime_field)
                    operations.append(op.AlterFieldType(
                        table=table_name,
                        name=col_name,
                        new_field=new_field_op,
                    ))

            if mig_field.nullable != mod_field.nullable:
                # Nullability changed
                operations.append(op.AlterFieldNull(
                    table=table_name,
                    name=col_name,
                    nullable=mod_field.nullable,
                ))

            if mig_field.default != mod_field.default:
                # Default changed
                operations.append(op.AlterFieldDefault(
                    table=table_name,
                    name=col_name,
                    new_default=mod_field.default,
                    field=_model_field_to_op(col_name, runtime_field) if runtime_field else None,
                ))

    # 5. Drop removed tables
    for table_name in diff.removed_tables:
        operations.append(op.DropTable(name=table_name))

    return operations


# =============================================================================
# Public API
# =============================================================================

def detect_changes(
    migration_files: List[Tuple[str, Path]],
    models: Dict[str, type],
) -> Tuple[MigrationDiff, list]:
    """
    Detect changes between existing migrations and current models.

    This is the main entry point for the autodetector.

    Args:
        migration_files: List of (name, path) tuples for existing migrations
        models: Dict of model_name -> model_class from ModelRegistry

    Returns:
        Tuple of (MigrationDiff, operations_list).
        If diff.has_changes is False, operations_list will be empty.
    """
    # Build state from existing migrations
    migration_state = build_state_from_migrations(migration_files)

    # Build state from current models
    model_state = build_state_from_models(models)

    # Compute diff
    diff = diff_states(migration_state, model_state)

    if not diff.has_changes:
        return diff, []

    # Generate operations
    operations = generate_operations_from_diff(
        diff, model_state, models, migration_state=migration_state
    )

    return diff, operations


def operations_to_code(operations: list) -> str:
    """
    Convert a list of Operation instances to Python source code for a migration file.

    Args:
        operations: List of Operation instances

    Returns:
        Python code string for the operations list (without the surrounding brackets)
    """
    from aksara.migrations import operations as op

    code_parts = []

    for operation in operations:
        if isinstance(operation, op.CreateTable):
            fields_code = []
            for fname, fop in operation.fields:
                fields_code.append(f'            ("{fname}", {_field_op_to_code(fop)})')
            fields_str = ",\n".join(fields_code)
            code_parts.append(
                f'        op.CreateTable(\n'
                f'            name="{operation.name}",\n'
                f'            fields=[\n'
                f'{fields_str},\n'
                f'            ],\n'
                f'        )'
            )

        elif isinstance(operation, op.DropTable):
            code_parts.append(f'        op.DropTable(name="{operation.name}")')

        elif isinstance(operation, op.AddField):
            field_code = _field_op_to_code(operation.field)
            f = operation.field
            is_primary_key = getattr(f, "primary_key", False)
            is_nullable = getattr(f, "nullable", True)
            has_default = getattr(f, "default", None) is not None
            if not is_primary_key and not is_nullable and not has_default:
                warning = (
                    f'        # WARNING: Adding non-null field "{operation.name}" without a default '
                    f'may fail on non-empty table "{operation.table}".\n'
                    f'        # Add a temporary default, backfill existing rows, or split this into '
                    f'a nullable field + data migration + nullability change.'
                )
                code_parts.append(warning)
            code_parts.append(
                f'        op.AddField(\n'
                f'            table="{operation.table}",\n'
                f'            name="{operation.name}",\n'
                f'            field={field_code},\n'
                f'        )'
            )

        elif isinstance(operation, op.RemoveField):
            code_parts.append(
                f'        op.RemoveField(\n'
                f'            table="{operation.table}",\n'
                f'            name="{operation.name}",\n'
                f'        )'
            )

        elif isinstance(operation, op.RenameField):
            code_parts.append(
                f'        op.RenameField(\n'
                f'            table="{operation.table}",\n'
                f'            old_name="{operation.old_name}",\n'
                f'            new_name="{operation.new_name}",\n'
                f'        )'
            )

        elif isinstance(operation, op.RenameTable):
            code_parts.append(
                f'        op.RenameTable(\n'
                f'            old_name="{operation.old_name}",\n'
                f'            new_name="{operation.new_name}",\n'
                f'        )'
            )

        elif isinstance(operation, op.AlterFieldType):
            field_code = _field_op_to_code(operation.new_field)
            code_parts.append(
                f'        op.AlterFieldType(\n'
                f'            table="{operation.table}",\n'
                f'            name="{operation.name}",\n'
                f'            new_field={field_code},\n'
                f'        )'
            )

        elif isinstance(operation, op.AlterFieldNull):
            code_parts.append(
                f'        op.AlterFieldNull(\n'
                f'            table="{operation.table}",\n'
                f'            name="{operation.name}",\n'
                f'            nullable={operation.nullable},\n'
                f'        )'
            )

        elif isinstance(operation, op.AlterFieldDefault):
            lines = [
                '        op.AlterFieldDefault(',
                f'            table="{operation.table}",',
                f'            name="{operation.name}",',
                f'            new_default={getattr(operation, "new_default", None)!r},',
            ]
            if getattr(operation, 'field', None) is not None:
                lines.append(f'            field={_field_op_to_code(operation.field)},')
            lines.append('        )')
            code_parts.append("\n".join(lines))

        elif isinstance(operation, op.RunSQL):
            kwargs = [f'sql={operation.sql!r}']
            if operation.reverse_sql is not None:
                kwargs.append(f'reverse_sql={operation.reverse_sql!r}')
            if operation.dangerous:
                kwargs.append('dangerous=True')
            joined = ",\n            ".join(kwargs)
            code_parts.append(
                f'        op.RunSQL(\n'
                f'            {joined},\n'
                f'        )'
            )

        else:
            # Generic fallback — use describe()
            code_parts.append(f'        # {operation.describe()}')

    return ",\n".join(code_parts)


def _field_op_to_code(field_op) -> str:
    """Convert a FieldOp instance to its Python source code representation."""
    from aksara.migrations import operations as op

    cls_name = type(field_op).__name__

    if isinstance(field_op, op.UUIDField):
        if field_op.primary_key:
            return "op.UUIDField(primary_key=True)"
        parts = []
        if field_op.nullable:
            parts.append("nullable=True")
        if field_op.unique:
            parts.append("unique=True")
        return f"op.UUIDField({', '.join(parts)})" if parts else "op.UUIDField()"

    elif isinstance(field_op, (op.ForeignKeyField, op.OneToOneField)):
        to_table = getattr(field_op, 'to_table', 'unknown')
        parts = [f"'{to_table}'"]
        parts.append(f"on_delete='{getattr(field_op, 'on_delete', 'CASCADE')}'")
        if field_op.nullable:
            parts.append("nullable=True")
        return f"op.{cls_name}({', '.join(parts)})"

    elif isinstance(field_op, op.StringField):
        parts = [str(field_op.max_length)]
        if field_op.nullable:
            parts.append("nullable=True")
        if field_op.unique:
            parts.append("unique=True")
        if field_op.default is not None:
            parts.append(f"default={field_op.default!r}")
        return f"op.StringField({', '.join(parts)})"

    elif isinstance(field_op, op.TextField):
        parts = []
        if field_op.nullable:
            parts.append("nullable=True")
        if getattr(field_op, 'default', None) is not None:
            parts.append(f"default={field_op.default!r}")
        return f"op.TextField({', '.join(parts)})" if parts else "op.TextField()"

    elif isinstance(field_op, op.IntegerField):
        parts = []
        if field_op.nullable:
            parts.append("nullable=True")
        if field_op.unique:
            parts.append("unique=True")
        if field_op.default is not None:
            parts.append(f"default={field_op.default!r}")
        return f"op.IntegerField({', '.join(parts)})" if parts else "op.IntegerField()"

    elif isinstance(field_op, op.BigIntegerField):
        parts = []
        if field_op.nullable:
            parts.append("nullable=True")
        if field_op.unique:
            parts.append("unique=True")
        if field_op.default is not None:
            parts.append(f"default={field_op.default!r}")
        return f"op.BigIntegerField({', '.join(parts)})" if parts else "op.BigIntegerField()"

    elif isinstance(field_op, op.BooleanField):
        parts = []
        if field_op.nullable:
            parts.append("nullable=True")
        if field_op.default is not None:
            parts.append(f"default={field_op.default!r}")
        return f"op.BooleanField({', '.join(parts)})" if parts else "op.BooleanField()"

    elif isinstance(field_op, op.DateTimeField):
        parts = []
        if getattr(field_op, 'auto_now_add', False):
            parts.append("auto_now_add=True")
        if getattr(field_op, 'auto_now', False):
            parts.append("auto_now=True")
        if field_op.nullable:
            parts.append("nullable=True")
        return f"op.DateTimeField({', '.join(parts)})" if parts else "op.DateTimeField()"

    elif isinstance(field_op, op.DateField):
        parts = []
        if field_op.nullable:
            parts.append("nullable=True")
        if getattr(field_op, 'default', None) is not None:
            parts.append(f"default={field_op.default!r}")
        return f"op.DateField({', '.join(parts)})" if parts else "op.DateField()"

    elif isinstance(field_op, op.JSONField):
        parts = []
        if field_op.nullable:
            parts.append("nullable=True")
        if field_op.default is not None:
            parts.append(f"default={field_op.default!r}")
        return f"op.JSONField({', '.join(parts)})" if parts else "op.JSONField()"

    elif isinstance(field_op, op.ArrayField):
        parts = [f"sql_type={field_op.sql_type!r}"]
        if not field_op.nullable:
            parts.append("nullable=False")
        if field_op.default is not None:
            parts.append(f"default={field_op.default!r}")
        return f"op.ArrayField({', '.join(parts)})"

    elif isinstance(field_op, op.FloatField):
        parts = []
        if field_op.nullable:
            parts.append("nullable=True")
        if field_op.default is not None:
            parts.append(f"default={field_op.default!r}")
        return f"op.FloatField({', '.join(parts)})" if parts else "op.FloatField()"

    elif isinstance(field_op, op.DecimalField):
        parts = [str(field_op.max_digits), str(field_op.decimal_places)]
        if field_op.nullable:
            parts.append("nullable=True")
        if field_op.unique:
            parts.append("unique=True")
        if field_op.default is not None:
            parts.append(f"default={field_op.default!r}")
        return f"op.DecimalField({', '.join(parts)})"

    elif isinstance(field_op, op.EmailField):
        parts = []
        ml = getattr(field_op, 'max_length', None)
        if ml:
            parts.append(str(ml))
        if field_op.nullable:
            parts.append("nullable=True")
        if field_op.unique:
            parts.append("unique=True")
        return f"op.EmailField({', '.join(parts)})" if parts else "op.EmailField()"

    elif isinstance(field_op, op.ImageField):
        parts = []
        ml = getattr(field_op, 'max_length', None)
        if ml:
            parts.append(str(ml))
        if field_op.nullable:
            parts.append("nullable=True")
        if field_op.unique:
            parts.append("unique=True")
        if getattr(field_op, 'default', None) is not None:
            parts.append(f"default={field_op.default!r}")
        return f"op.ImageField({', '.join(parts)})" if parts else "op.ImageField()"

    elif isinstance(field_op, op.FileField):
        parts = []
        ml = getattr(field_op, 'max_length', None)
        if ml:
            parts.append(str(ml))
        if field_op.nullable:
            parts.append("nullable=True")
        if field_op.unique:
            parts.append("unique=True")
        if getattr(field_op, 'default', None) is not None:
            parts.append(f"default={field_op.default!r}")
        return f"op.FileField({', '.join(parts)})" if parts else "op.FileField()"

    elif isinstance(field_op, op.URLField):
        parts = []
        if field_op.nullable:
            parts.append("nullable=True")
        if field_op.unique:
            parts.append("unique=True")
        return f"op.URLField({', '.join(parts)})" if parts else "op.URLField()"

    elif isinstance(field_op, op.EnumField):
        # allowed_values is the first positional arg
        av = getattr(field_op, 'allowed_values', None) or []
        enum_name = getattr(field_op, 'enum_name', None)
        parts = [repr(av)]
        if enum_name:
            parts.append(f"enum_name={enum_name!r}")
        if field_op.nullable:
            parts.append("nullable=True")
        if field_op.default is not None:
            parts.append(f"default={field_op.default!r}")
        return f"op.EnumField({', '.join(parts)})"

    else:
        # Fallback
        parts = []
        if getattr(field_op, 'nullable', False):
            parts.append("nullable=True")
        return f"op.{cls_name}({', '.join(parts)})" if parts else f"op.{cls_name}()"
