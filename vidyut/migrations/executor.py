"""
Vidyut Migration Executor

Handles loading, tracking, and executing migrations against the database.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

from vidyut.migrations.base import Migration

logger = logging.getLogger(__name__)


# =============================================================================
# Migration History Table
# =============================================================================

MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS vidyut_migrations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    checksum VARCHAR(64),
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
)
"""


async def ensure_migrations_table(connection) -> None:
    """Create the migrations tracking table if it doesn't exist."""
    await connection.execute(MIGRATION_TABLE_SQL)
    
    # Ensure checksum column is nullable (for migrations that upgrade from older schema)
    try:
        await connection.execute("""
            ALTER TABLE vidyut_migrations 
            ALTER COLUMN checksum DROP NOT NULL
        """)
    except Exception:
        pass  # Column already nullable or doesn't exist


async def get_applied_migrations(connection) -> List[str]:
    """
    Get list of applied migration names from the database.
    
    Args:
        connection: Database connection
        
    Returns:
        List of migration names that have been applied
    """
    await ensure_migrations_table(connection)
    
    rows = await connection.fetch(
        "SELECT name FROM vidyut_migrations ORDER BY applied_at, id"
    )
    return [row['name'] for row in rows]


async def record_migration(
    connection,
    name: str,
    checksum: Optional[str] = None,
) -> None:
    """
    Record a migration as applied in the database.
    
    Args:
        connection: Database connection
        name: Migration name
        checksum: Optional checksum for the migration
    """
    await connection.execute(
        "INSERT INTO vidyut_migrations (name, checksum) VALUES ($1, $2)",
        name,
        checksum,
    )


async def unrecord_migration(connection, name: str) -> None:
    """
    Remove a migration record (for rollbacks).
    
    Args:
        connection: Database connection
        name: Migration name to remove
    """
    await connection.execute(
        "DELETE FROM vidyut_migrations WHERE name = $1",
        name,
    )


# =============================================================================
# Migration Discovery
# =============================================================================

def discover_migrations(migrations_path: Path) -> List[Tuple[str, Path]]:
    """
    Discover all migration files in a directory.
    
    Supports both:
        - Python migrations (.py files with Migration class)
        - Legacy SQL migrations (.sql files)
    
    Args:
        migrations_path: Path to migrations directory
        
    Returns:
        List of (migration_name, file_path) tuples sorted by name
    """
    if not migrations_path.exists():
        return []
    
    migrations = []
    
    # Find Python migration files
    for f in migrations_path.glob("*.py"):
        if f.name.startswith("_"):
            continue
        name = f.stem
        migrations.append((name, f))
    
    # Find SQL migration files (legacy support)
    for f in migrations_path.glob("*.sql"):
        name = f.stem
        migrations.append((name, f))
    
    # Sort by name (includes timestamp for proper ordering)
    return sorted(migrations, key=lambda x: x[0])


def load_migration_module(file_path: Path) -> Type[Migration]:
    """
    Load a Migration class from a Python file.
    
    Args:
        file_path: Path to the migration file
        
    Returns:
        The Migration class from the module
        
    Raises:
        ImportError: If the module can't be loaded
        AttributeError: If the module doesn't have a Migration class
    """
    module_name = f"vidyut_migration_{file_path.stem}"
    
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load migration from {file_path}")
    
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        del sys.modules[module_name]
        raise ImportError(f"Error loading migration {file_path}: {e}") from e
    
    # Get the Migration class
    if not hasattr(module, "Migration"):
        del sys.modules[module_name]
        raise AttributeError(
            f"Migration file {file_path} does not define a Migration class"
        )
    
    return module.Migration


def get_pending_migrations(
    all_migrations: List[Tuple[str, Path]],
    applied: List[str],
) -> List[Tuple[str, Path]]:
    """
    Determine which migrations are pending (not yet applied).
    
    Args:
        all_migrations: All discovered migrations
        applied: Names of applied migrations
        
    Returns:
        List of pending (name, path) tuples
    """
    applied_set = set(applied)
    return [(name, path) for name, path in all_migrations if name not in applied_set]


# =============================================================================
# Migration Execution
# =============================================================================

async def apply_migration(
    connection,
    name: str,
    file_path: Path,
    *,
    fake: bool = False,
    verbose: bool = True,
) -> bool:
    """
    Apply a single migration.
    
    Args:
        connection: Database connection
        name: Migration name
        file_path: Path to migration file
        fake: If True, record as applied without executing
        verbose: If True, print progress messages
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if file_path.suffix == ".py":
            # Python migration
            migration_class = load_migration_module(file_path)
            migration = migration_class()
            
            if not fake:
                for i, op in enumerate(migration.operations):
                    if verbose:
                        logger.info(f"  → {op.describe()}")
                    await op.apply(connection)
            
            await record_migration(connection, name)
            
        elif file_path.suffix == ".sql":
            # Legacy SQL migration
            sql = file_path.read_text()
            
            if not fake:
                await connection.execute(sql)
            
            # Compute simple checksum for SQL
            import hashlib
            checksum = hashlib.sha256(sql.encode()).hexdigest()[:16]
            await record_migration(connection, name, checksum)
        
        else:
            raise ValueError(f"Unknown migration type: {file_path.suffix}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error applying migration {name}: {e}")
        raise


async def apply_migrations(
    connection,
    migrations_path: str | Path,
    *,
    fake: bool = False,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Apply all pending migrations.
    
    Args:
        connection: Database connection (Database instance or asyncpg connection)
        migrations_path: Path to migrations directory
        fake: If True, record as applied without executing
        verbose: If True, print progress messages
        
    Returns:
        Dict with results:
            - applied: List of applied migration names
            - skipped: List of already-applied migrations
            - errors: List of (name, error) tuples if any
    """
    migrations_path = Path(migrations_path)
    
    # Ensure migrations table exists
    await ensure_migrations_table(connection)
    
    # Get applied migrations
    applied = await get_applied_migrations(connection)
    
    # Discover all migrations
    all_migrations = discover_migrations(migrations_path)
    
    # Get pending migrations
    pending = get_pending_migrations(all_migrations, applied)
    
    results = {
        "applied": [],
        "skipped": applied,
        "errors": [],
        "total_discovered": len(all_migrations),
    }
    
    if not pending:
        if verbose:
            logger.info("No pending migrations.")
        return results
    
    if verbose:
        logger.info(f"Found {len(pending)} pending migration(s).")
    
    for name, path in pending:
        try:
            if verbose:
                action = "Marking" if fake else "Applying"
                logger.info(f"\n{action}: {name}")
            
            await apply_migration(
                connection,
                name,
                path,
                fake=fake,
                verbose=verbose,
            )
            
            results["applied"].append(name)
            
            if verbose:
                status = "marked as applied" if fake else "applied successfully"
                logger.info(f"  ✓ {status}")
                
        except Exception as e:
            results["errors"].append((name, str(e)))
            if verbose:
                logger.error(f"  ✗ Error: {e}")
            # Stop on first error
            break
    
    return results


# =============================================================================
# Utility Functions
# =============================================================================

def generate_migration_filename(
    prefix: str = "auto",
    *,
    include_timestamp: bool = True,
) -> str:
    """
    Generate a migration filename.
    
    Args:
        prefix: Prefix for the migration name
        include_timestamp: Whether to include timestamp
        
    Returns:
        Filename like "20250301_120000_auto.py"
    """
    if include_timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{timestamp}_{prefix}.py"
    return f"{prefix}.py"


def get_migration_template() -> str:
    """
    Get the template for a new migration file.
    
    Returns:
        Python code template for a migration
    """
    return '''"""
Migration: {name}
Generated: {timestamp}
"""

from vidyut.migrations import Migration
from vidyut.migrations import operations as op


class Migration(Migration):
    """
    {description}
    """
    
    dependencies = []
    
    operations = [
        # Add your operations here
        # op.CreateTable(
        #     name="example",
        #     fields=[
        #         ("id", op.UUIDField(primary_key=True)),
        #         ("name", op.StringField()),
        #     ],
        # ),
    ]
'''


def create_migration_file(
    migrations_path: Path,
    name: str,
    operations_code: str,
    *,
    description: str = "",
) -> Path:
    """
    Create a new migration file.
    
    Args:
        migrations_path: Directory for migrations
        name: Migration name (without timestamp)
        operations_code: Python code for the operations list
        description: Description for the migration docstring
        
    Returns:
        Path to the created file
    """
    migrations_path = Path(migrations_path)
    migrations_path.mkdir(parents=True, exist_ok=True)
    
    filename = generate_migration_filename(name)
    file_path = migrations_path / filename
    
    timestamp = datetime.now().isoformat()
    
    content = f'''"""
Migration: {name}
Generated: {timestamp}
"""

from vidyut.migrations import Migration
from vidyut.migrations import operations as op


class Migration(Migration):
    """
    {description or name}
    """
    
    dependencies = []
    
    operations = [
{operations_code}
    ]
'''
    
    file_path.write_text(content)
    return file_path


# =============================================================================
# Model to Operations Conversion
# =============================================================================

def model_to_create_table(model_class) -> str:
    """
    Convert a Vidyut Model class to a CreateTable operation code string.
    
    Args:
        model_class: A Vidyut Model class
        
    Returns:
        Python code string for the CreateTable operation
    """
    from vidyut.fields import (
        String, Integer, Boolean, DateTime, UUID, JSON,
        ForeignKey,
    )
    
    # Get table name (try both attributes)
    table_name = getattr(model_class, '_table_name', None) or getattr(model_class, '__tablename__', None)
    if not table_name:
        # Generate from class name
        name = model_class.__name__.lower()
        if name.endswith('y'):
            table_name = name[:-1] + 'ies'
        elif name.endswith(('s', 'x', 'z', 'ch', 'sh')):
            table_name = name + 'es'
        else:
            table_name = name + 's'
    fields_code = []
    
    for field_name, field in model_class._fields.items():
        # Map Vidyut fields to migration FieldOps
        if isinstance(field, UUID):
            if field.primary_key:
                field_code = "op.UUIDField(primary_key=True)"
            else:
                parts = []
                if field.nullable:
                    parts.append("nullable=True")
                if field.unique:
                    parts.append("unique=True")
                opts = ", ".join(parts)
                field_code = f"op.UUIDField({opts})" if opts else "op.UUIDField()"
        
        elif isinstance(field, String):
            parts = [f"{field.max_length}"]
            if field.nullable:
                parts.append("nullable=True")
            if field.unique:
                parts.append("unique=True")
            if field.default is not None and not callable(field.default):
                parts.append(f"default={field.default!r}")
            field_code = f"op.StringField({', '.join(parts)})"
        
        elif isinstance(field, Integer):
            parts = []
            if field.nullable:
                parts.append("nullable=True")
            if field.unique:
                parts.append("unique=True")
            if field.default is not None and not callable(field.default):
                parts.append(f"default={field.default!r}")
            opts = ", ".join(parts)
            field_code = f"op.IntegerField({opts})" if opts else "op.IntegerField()"
        
        elif isinstance(field, Boolean):
            parts = []
            if field.nullable:
                parts.append("nullable=True")
            if field.default is not None:
                parts.append(f"default={field.default!r}")
            opts = ", ".join(parts)
            field_code = f"op.BooleanField({opts})" if opts else "op.BooleanField()"
        
        elif isinstance(field, DateTime):
            parts = []
            if field.auto_now_add:
                parts.append("auto_now_add=True")
            if field.auto_now:
                parts.append("auto_now=True")
            if field.nullable:
                parts.append("nullable=True")
            opts = ", ".join(parts)
            field_code = f"op.DateTimeField({opts})" if opts else "op.DateTimeField()"
        
        elif isinstance(field, JSON):
            parts = []
            if field.nullable:
                parts.append("nullable=True")
            if field.default is not None and not callable(field.default):
                parts.append(f"default={field.default!r}")
            opts = ", ".join(parts)
            field_code = f"op.JSONField({opts})" if opts else "op.JSONField()"
        
        elif isinstance(field, ForeignKey):
            # Get target table name (try __tablename__ first, then _table_name)
            try:
                target_model = field.to_model
                target_table = getattr(target_model, '__tablename__', None) or getattr(target_model, '_table_name', 'unknown')
            except Exception:
                target_table = "unknown"
            
            parts = [f"'{target_table}'"]
            parts.append(f"on_delete='{field.on_delete}'")
            if field.nullable:
                parts.append("nullable=True")
            
            # ForeignKey creates a column with _id suffix
            field_name = field.db_column_name
            field_code = f"op.ForeignKeyField({', '.join(parts)})"
        
        elif hasattr(field, '__class__') and 'Float' in field.__class__.__name__:
            parts = []
            if field.nullable:
                parts.append("nullable=True")
            if field.default is not None and not callable(field.default):
                parts.append(f"default={field.default!r}")
            opts = ", ".join(parts)
            field_code = f"op.FloatField({opts})" if opts else "op.FloatField()"
        
        else:
            # Fallback for unknown field types
            sql_type = field.sql_type if hasattr(field, 'sql_type') else 'VARCHAR(255)'
            parts = []
            if hasattr(field, 'nullable') and field.nullable:
                parts.append("nullable=True")
            opts = ", ".join(parts)
            field_code = f"op.StringField({opts})" if opts else "op.StringField()"
        
        fields_code.append(f'            ("{field_name}", {field_code})')
    
    fields_str = ",\n".join(fields_code)
    
    return f'''        op.CreateTable(
            name="{table_name}",
            fields=[
{fields_str},
            ],
        )'''


def models_to_migration_code(models: dict) -> str:
    """
    Convert multiple models to migration operations code.
    
    Args:
        models: Dict of model_name -> model_class
        
    Returns:
        Python code string for all CreateTable operations
    """
    operations = []
    for model_name, model_class in models.items():
        operations.append(model_to_create_table(model_class))
    
    return ",\n".join(operations)
