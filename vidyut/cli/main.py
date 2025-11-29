"""
CLI Main Entry Point

Command-line interface for Vidyut ORM.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import click

# Version for CLI
CLI_VERSION = "0.3.3"


def discover_models(app_path: Optional[str] = None) -> None:
    """
    Discover and import model modules to populate the registry.
    
    Args:
        app_path: Optional path to the application directory
    """
    # Add current directory to path
    cwd = Path.cwd()
    if str(cwd) not in sys.path:
        sys.path.insert(0, str(cwd))
    
    # Try to import common model locations
    model_paths = [
        "models",
        "app.models",
        "src.models",
    ]
    
    if app_path:
        model_paths.insert(0, app_path)
    
    for path in model_paths:
        try:
            __import__(path)
            click.echo(f"  ✓ Discovered models from '{path}'")
        except ImportError:
            pass


# =============================================================================
# Migration History System
# =============================================================================

MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS vidyut_migrations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    checksum VARCHAR(64) NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def compute_checksum(sql: str) -> str:
    """Compute SHA-256 checksum of SQL content."""
    return hashlib.sha256(sql.strip().encode()).hexdigest()[:16]


def generate_migration_name(prefix: str = "migration") -> str:
    """Generate a timestamped migration name."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{prefix}"


def get_migration_files(migrations_dir: Path) -> List[Tuple[str, Path]]:
    """
    Get all migration files sorted by name.
    
    Returns:
        List of (migration_name, file_path) tuples
    """
    if not migrations_dir.exists():
        return []
    
    files = []
    for f in migrations_dir.glob("*.sql"):
        # Extract migration name (filename without .sql)
        name = f.stem
        files.append((name, f))
    
    # Sort by name (which includes timestamp)
    return sorted(files, key=lambda x: x[0])


async def ensure_migrations_table(db) -> None:
    """Create the migrations tracking table if it doesn't exist."""
    await db.execute(MIGRATION_TABLE_SQL)


async def get_applied_migrations(db) -> List[str]:
    """Get list of applied migration names."""
    rows = await db.fetch(
        "SELECT name FROM vidyut_migrations ORDER BY applied_at"
    )
    return [row['name'] for row in rows]


async def record_migration(db, name: str, checksum: str) -> None:
    """Record a migration as applied."""
    await db.execute(
        "INSERT INTO vidyut_migrations (name, checksum) VALUES ($1, $2)",
        name, checksum
    )


# =============================================================================
# CLI Commands
# =============================================================================

@click.group()
@click.version_option(version=CLI_VERSION, prog_name="vidyut")
def cli():
    """⚡ Vidyut - Async Framework"""
    pass


@cli.command()
@click.option("--app", "-a", help="Path to application models module")
@click.option("--output", "-o", help="Output directory for migrations (default: ./migrations)")
@click.option("--name", "-n", default="auto", help="Migration name prefix")
@click.option("--stdout", is_flag=True, help="Output to stdout instead of file")
@click.option("--sql", is_flag=True, help="Generate legacy SQL migration (default: Python)")
def makemigrations(app: Optional[str], output: Optional[str], name: str, stdout: bool, sql: bool):
    """Generate migration from models (Python or SQL)."""
    from vidyut.registry import ModelRegistry
    from vidyut.conf import settings
    from vidyut.migrations.executor import (
        generate_migration_filename,
        models_to_migration_code,
    )
    
    click.echo("⚡ Vidyut Makemigrations")
    click.echo("-" * 40)
    
    # Discover models
    click.echo("\nDiscovering models...")
    discover_models(app)
    
    models = ModelRegistry.all()
    
    if not models:
        click.echo("\n⚠️  No models found!")
        click.echo("   Make sure your models are in a 'models.py' file")
        click.echo("   or specify the module with --app")
        return
    
    click.echo(f"\nFound {len(models)} model(s):")
    for model_name in models:
        click.echo(f"  • {model_name}")
    
    if sql:
        # Legacy SQL mode
        sql_statements = []
        for model_name, model in models.items():
            sql_stmt = model.get_create_table_sql()
            sql_statements.append(f"-- Model: {model_name}")
            sql_statements.append(sql_stmt)
        
        full_sql = "\n\n".join(sql_statements)
        
        if stdout:
            click.echo("\n" + "=" * 40)
            click.echo("Generated SQL:")
            click.echo("=" * 40 + "\n")
            click.echo(full_sql)
            return
        
        # Write to migrations directory
        migrations_dir = Path(output) if output else Path(settings.migrations_dir)
        migrations_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate migration filename
        migration_name = generate_migration_name(name)
        migration_file = migrations_dir / f"{migration_name}.sql"
        
        # Add header to migration file
        header = f"""-- Migration: {migration_name}
-- Generated: {datetime.now().isoformat()}
-- Models: {', '.join(models.keys())}

"""
        
        with open(migration_file, "w") as f:
            f.write(header + full_sql)
        
        click.echo(f"\n✓ SQL Migration created: {migration_file}")
        click.echo(f"  Checksum: {compute_checksum(full_sql)}")
    
    else:
        # Python migration mode (v0.3.3 default)
        operations_code = models_to_migration_code(models)
        
        if stdout:
            click.echo("\n" + "=" * 40)
            click.echo("Generated Python Migration:")
            click.echo("=" * 40 + "\n")
            
            timestamp = datetime.now().isoformat()
            click.echo(f'''"""
Migration: {name}
Generated: {timestamp}
"""

from vidyut.migrations import Migration
from vidyut.migrations import operations as op


class Migration(Migration):
    """
    Auto-generated migration for models: {', '.join(models.keys())}
    """
    
    dependencies = []
    
    operations = [
{operations_code},
    ]
''')
            return
        
        # Write to migrations directory
        migrations_dir = Path(output) if output else Path(settings.migrations_dir)
        migrations_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate migration filename
        filename = generate_migration_filename(name)
        migration_file = migrations_dir / filename
        
        timestamp = datetime.now().isoformat()
        description = f"Auto-generated migration for models: {', '.join(models.keys())}"
        
        content = f'''"""
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
{operations_code},
    ]
'''
        
        with open(migration_file, "w") as f:
            f.write(content)
        
        click.echo(f"\n✓ Python Migration created: {migration_file}")
        click.echo(f"  Operations: {len(models)} CreateTable(s)")
        click.echo("\n  To apply: vidyut migrate")


@cli.command()
@click.option("--app", "-a", help="Path to application models module")
@click.option("--database-url", "-d", envvar="DATABASE_URL",
              help="PostgreSQL connection URL (or set DATABASE_URL env var)")
@click.option("--migrations-dir", "-m", help="Migrations directory (default: ./migrations)")
@click.option("--dry-run", is_flag=True, help="Print operations without executing")
@click.option("--fake", is_flag=True, help="Mark migrations as applied without running")
def migrate(
    app: Optional[str],
    database_url: Optional[str],
    migrations_dir: Optional[str],
    dry_run: bool,
    fake: bool,
):
    """Apply migrations to the database."""
    from vidyut.registry import ModelRegistry
    from vidyut.db import Database
    from vidyut.conf import settings
    from vidyut.migrations.executor import (
        apply_migrations,
        discover_migrations,
        get_pending_migrations,
        ensure_migrations_table,
        get_applied_migrations as get_applied_migs,
        record_migration,
        load_migration_module,
    )
    
    click.echo("⚡ Vidyut Migrate")
    click.echo("-" * 40)
    
    # Get database URL from args or settings
    db_url = database_url or settings.database_url
    if not db_url:
        click.echo("\n❌ No database URL provided!")
        click.echo("   Set DATABASE_URL or use --database-url")
        return
    
    # Get migrations directory
    mig_dir = Path(migrations_dir) if migrations_dir else Path(settings.migrations_dir)
    
    # Check for migration files
    migration_files = discover_migrations(mig_dir)
    
    if migration_files:
        click.echo(f"\nFound {len(migration_files)} migration file(s) in {mig_dir}")
    else:
        # Fall back to model-based migration (v0.1 behavior)
        click.echo(f"\nNo migration files in {mig_dir}")
        click.echo("Falling back to model-based migration...")
        
        # Discover models
        click.echo("\nDiscovering models...")
        discover_models(app)
        
        models = ModelRegistry.all()
        
        if not models:
            click.echo("\n⚠️  No models found!")
            return
        
        click.echo(f"Found {len(models)} model(s)")
    
    async def run_migrations():
        db = Database(db_url)
        
        try:
            await db.connect()
            click.echo(f"\n✓ Connected to database")
            
            # Ensure migrations table exists
            await ensure_migrations_table(db)
            
            if migration_files:
                # File-based migrations (v0.3.3 path)
                applied = await get_applied_migs(db)
                click.echo(f"  {len(applied)} migration(s) already applied")
                
                pending = get_pending_migrations(migration_files, applied)
                
                if not pending:
                    click.echo("\n✓ All migrations already applied!")
                    return
                
                click.echo(f"\n{len(pending)} pending migration(s):")
                
                for name, path in pending:
                    if path.suffix == ".py":
                        # Python migration
                        if dry_run:
                            click.echo(f"\n[DRY RUN] Would apply: {name}")
                            try:
                                migration_class = load_migration_module(path)
                                migration = migration_class()
                                for op in migration.operations:
                                    click.echo(f"    → {op.describe()}")
                            except Exception as e:
                                click.echo(f"    ⚠️  Error loading: {e}")
                        elif fake:
                            click.echo(f"\n→ Marking as applied: {name}")
                            await record_migration(db, name)
                            click.echo(f"  ✓ Marked (not executed)")
                        else:
                            click.echo(f"\n→ Applying: {name}")
                            try:
                                migration_class = load_migration_module(path)
                                migration = migration_class()
                                for op in migration.operations:
                                    click.echo(f"    → {op.describe()}")
                                    await op.apply(db)
                                await record_migration(db, name)
                                click.echo(f"  ✓ Applied successfully")
                            except Exception as e:
                                click.echo(f"  ✗ Error: {e}")
                                return
                    
                    elif path.suffix == ".sql":
                        # Legacy SQL migration
                        sql = path.read_text()
                        checksum = compute_checksum(sql)
                        
                        if dry_run:
                            click.echo(f"\n[DRY RUN] Would apply SQL: {name}")
                            lines = sql.strip().split('\n')[:5]
                            for line in lines:
                                click.echo(f"    {line}")
                            if len(sql.strip().split('\n')) > 5:
                                click.echo(f"    ... ({len(sql.strip().split(chr(10)))} lines)")
                        elif fake:
                            click.echo(f"\n→ Marking as applied: {name}")
                            await record_migration(db, name, checksum)
                            click.echo(f"  ✓ Marked (not executed)")
                        else:
                            click.echo(f"\n→ Applying SQL: {name}")
                            try:
                                await db.execute(sql)
                                await record_migration(db, name, checksum)
                                click.echo(f"  ✓ Applied successfully")
                            except Exception as e:
                                click.echo(f"  ✗ Error: {e}")
                                return
            else:
                # Model-based migrations (v0.1 behavior - fallback)
                models = ModelRegistry.all()
                applied = await get_applied_migs(db)
                
                for model_name, model in models.items():
                    sql = model.get_create_table_sql()
                    migration_name = f"model_{model_name.lower()}"
                    
                    if migration_name in applied:
                        click.echo(f"\n→ Table '{model._table_name}' already migrated")
                        continue
                    
                    if dry_run:
                        click.echo(f"\n[DRY RUN] Would create table '{model._table_name}':")
                        click.echo(sql)
                    else:
                        click.echo(f"\n→ Creating table '{model._table_name}'...")
                        try:
                            await db.execute(sql)
                            await record_migration(db, migration_name, compute_checksum(sql))
                            click.echo(f"  ✓ Table '{model._table_name}' created/verified")
                        except Exception as e:
                            click.echo(f"  ✗ Error: {e}")
            
            if not dry_run:
                click.echo("\n" + "=" * 40)
                click.echo("✓ Migrations complete!")
        finally:
            await db.disconnect()
    
    asyncio.run(run_migrations())


@cli.command()
@click.option("--database-url", "-d", envvar="DATABASE_URL",
              help="PostgreSQL connection URL (or set DATABASE_URL env var)")
def status(database_url: Optional[str]):
    """Show migration status."""
    from vidyut.db import Database
    from vidyut.conf import settings
    from vidyut.migrations.executor import (
        discover_migrations,
        ensure_migrations_table,
        get_applied_migrations as get_applied_migs,
    )
    
    click.echo("⚡ Vidyut Migration Status")
    click.echo("-" * 40)
    
    # Get database URL
    db_url = database_url or settings.database_url
    if not db_url:
        click.echo("\n❌ No database URL provided!")
        return
    
    # Get migrations directory
    mig_dir = Path(settings.migrations_dir)
    migration_files = discover_migrations(mig_dir)
    
    async def show_status():
        db = Database(db_url)
        
        try:
            await db.connect()
            
            # Ensure migrations table exists
            await ensure_migrations_table(db)
            
            applied = await get_applied_migs(db)
            
            click.echo(f"\n📁 Migrations directory: {mig_dir}")
            click.echo(f"📊 Applied migrations: {len(applied)}")
            
            if migration_files:
                click.echo(f"\n{'Migration':<50} {'Type':<8} {'Status':<12}")
                click.echo("-" * 70)
                
                for name, path in migration_files:
                    mig_type = "Python" if path.suffix == ".py" else "SQL"
                    if name in applied:
                        status_str = click.style("✓ applied", fg="green")
                    else:
                        status_str = click.style("○ pending", fg="yellow")
                    click.echo(f"{name:<50} {mig_type:<8} {status_str}")
            
            # Show applied migrations not in files (orphaned migrations)
            file_names = {name for name, _ in migration_files}
            orphaned = [m for m in applied if m not in file_names]
            
            if orphaned:
                click.echo(f"\n⚠️  Orphaned migrations (applied but file missing):")
                for name in orphaned:
                    click.echo(f"  • {name}")
                    
        finally:
            await db.disconnect()
    
    asyncio.run(show_status())


@cli.command()
@click.option("--database-url", "-d", envvar="DATABASE_URL",
              help="PostgreSQL connection URL (or set DATABASE_URL env var)")
def shell(database_url: Optional[str]):
    """Open an interactive async shell with Vidyut."""
    from vidyut.conf import settings
    
    db_url = database_url or settings.database_url
    if not db_url:
        click.echo("❌ No database URL provided!")
        return
    
    click.echo("⚡ Vidyut Interactive Shell")
    click.echo("-" * 40)
    click.echo("Use 'await' for async operations")
    click.echo("Available: Model, fields, Database, db")
    click.echo("-" * 40)
    
    # Import everything needed
    import code
    import asyncio
    from vidyut import Model, fields
    from vidyut.db import Database
    from vidyut.registry import ModelRegistry
    
    db = Database(db_url)
    
    # Create async REPL
    async def async_shell():
        await db.connect()
        
        # Create namespace for shell
        namespace = {
            'Model': Model,
            'fields': fields,
            'Database': Database,
            'db': db,
            'ModelRegistry': ModelRegistry,
            'asyncio': asyncio,
        }
        
        # Add all registered models
        for name, model in ModelRegistry.all().items():
            namespace[name] = model
        
        # Start interactive console
        console = code.InteractiveConsole(namespace)
        console.interact(banner="")
        
        await db.disconnect()
    
    asyncio.run(async_shell())


@cli.command()
@click.option("--app", "-a", help="Path to application models module")
@click.option("--ai", is_flag=True, help="Show AI metadata")
def models(app: Optional[str], ai: bool):
    """List all registered models."""
    from vidyut.registry import ModelRegistry, get_model_meta
    
    click.echo("⚡ Vidyut Models")
    click.echo("-" * 40)
    
    # Discover models
    discover_models(app)
    
    all_models = ModelRegistry.all()
    
    if not all_models:
        click.echo("\n⚠️  No models found!")
        return
    
    click.echo(f"\nRegistered Models ({len(all_models)}):\n")
    
    for name, model in all_models.items():
        click.echo(f"📦 {name}")
        click.echo(f"   Table: {model._table_name}")
        
        if ai:
            # Show AI metadata
            meta = get_model_meta(model)
            if meta.get('description'):
                click.echo(f"   AI Description: {meta['description']}")
            click.echo(f"   AI Exposed: {meta.get('ai_agent_exposed', True)}")
            click.echo(f"   AI Permissions: {', '.join(meta.get('ai_permissions', []))}")
        
        click.echo("   Fields:")
        for field_name, field in model._fields.items():
            pk = " (PK)" if field.primary_key else ""
            nullable = " nullable" if field.null else ""
            unique = " unique" if field.unique else ""
            
            field_info = f"     • {field_name}: {field.sql_type}{pk}{unique}{nullable}"
            
            if ai and field.ai_description:
                field_info += f"\n       AI: {field.ai_description}"
                if field.ai_sensitive:
                    field_info += " [SENSITIVE]"
            
            click.echo(field_info)
        click.echo()


@cli.command()
@click.argument("app_path")
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind to")
@click.option("--port", "-p", default=8000, type=int, help="Port to bind to")
@click.option("--reload", "-r", is_flag=True, help="Enable auto-reload")
@click.option("--workers", "-w", default=1, type=int, help="Number of workers")
def run(app_path: str, host: str, port: int, reload: bool, workers: int):
    """
    Run a Vidyut application with uvicorn.
    
    APP_PATH: Import path to the app (e.g., 'main:app' or 'myproject.main:app')
    
    Example:
        vidyut run main:app --reload
        vidyut run myproject.main:app --host 0.0.0.0 --port 8080
    """
    try:
        import uvicorn
    except ImportError:
        click.echo("❌ uvicorn not installed. Run: pip install uvicorn")
        return
    
    # Print Vidyut banner
    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mVidyut\033[0m v{CLI_VERSION}")
    click.echo("  \033[90mAsync Postgres ORM for FastAPI\033[0m")
    click.echo()
    click.echo(f"  \033[36m→\033[0m Running: {app_path}")
    click.echo(f"  \033[36m→\033[0m Server:  http://{host}:{port}")
    if reload:
        click.echo(f"  \033[36m→\033[0m Reload:  \033[32menabled\033[0m")
    click.echo()
    click.echo("  \033[90m" + "─" * 40 + "\033[0m")
    click.echo()
    
    # Configure uvicorn with minimal output
    uvicorn.run(
        app_path,
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        log_level="info",
        access_log=True,
    )


def main():
    """Main entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
