"""
CLI Main Entry Point

Command-line interface for Aksara ORM.
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

# Load .env file from current directory
# This must happen before any settings are read
try:
    from dotenv import load_dotenv
    # Always load from current working directory
    load_dotenv(Path.cwd() / ".env")
except ImportError:
    pass  # python-dotenv not installed

# Version for CLI
CLI_VERSION = "0.4.11"


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
CREATE TABLE IF NOT EXISTS aksara_migrations (
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
        "SELECT name FROM aksara_migrations ORDER BY applied_at"
    )
    return [row['name'] for row in rows]


async def record_migration(db, name: str, checksum: str) -> None:
    """Record a migration as applied."""
    await db.execute(
        "INSERT INTO aksara_migrations (name, checksum) VALUES ($1, $2)",
        name, checksum
    )


def _handle_merge_migration(
    app_label: Optional[str], 
    output: Optional[str], 
    settings,
) -> None:
    """
    Create a merge migration to resolve conflicting heads.
    
    This creates an empty migration that depends on all current heads
    for the specified app, effectively linearizing the migration history.
    """
    from aksara.migrations.executor import (
        discover_migrations,
        build_migration_graph,
    )
    from aksara.migrations.graph import find_conflicts
    
    click.echo("⚡ Aksara Makemigrations --merge")
    click.echo("-" * 40)
    
    # Get migrations directory
    mig_dir = Path(output) if output else Path(settings.migrations_dir)
    
    if not mig_dir.exists():
        click.echo(f"\n❌ Migrations directory not found: {mig_dir}")
        return
    
    # Build migration graph
    migration_files = discover_migrations(mig_dir)
    if not migration_files:
        click.echo(f"\n⚠️  No migrations found in {mig_dir}")
        return
    
    graph = build_migration_graph(migrations_list=migration_files)
    conflicts = find_conflicts(graph)
    
    if not conflicts:
        click.echo("\n✓ No conflicts detected. Nothing to merge.")
        return
    
    # If app_label specified, only merge that app
    if app_label:
        if app_label not in conflicts:
            click.echo(f"\n✓ No conflicts in app '{app_label}'.")
            return
        conflicts = {app_label: conflicts[app_label]}
    
    # Create merge migrations for each conflicting app
    for target_app, heads in conflicts.items():
        click.echo(f"\nMerging conflicts for '{target_app}':")
        for head in heads:
            click.echo(f"  • {head.name}")
        
        # Determine next migration number
        app_migrations = [
            node for node in graph.nodes.values() 
            if node.app_label == target_app
        ]
        
        # Extract numbers from migration names
        numbers = []
        for node in app_migrations:
            # Try to extract leading number (e.g., 0001 from 0001_initial)
            parts = node.name.split("_")
            if parts and parts[0].isdigit():
                numbers.append(int(parts[0]))
        
        if numbers:
            next_num = max(numbers) + 1
        else:
            next_num = len(app_migrations) + 1
        
        new_name = f"{next_num:04d}_merge"
        
        # Build dependencies list
        dependencies = [(h.app_label, h.name) for h in heads]
        deps_code = ",\n        ".join(
            f'("{app}", "{name}")' for app, name in dependencies
        )
        
        # Generate merge migration content
        timestamp = datetime.now().isoformat()
        content = f'''"""
Migration: {new_name}
Generated: {timestamp}

Merge migration to resolve conflicting heads:
{chr(10).join(f"  - {h.app_label}.{h.name}" for h in heads)}
"""

from aksara.migrations import Migration


class Migration(Migration):
    """
    Merge migration - resolves conflicts by depending on all heads.
    """
    
    dependencies = [
        {deps_code},
    ]
    
    operations = []
'''
        
        # Write the merge migration file
        merge_filename = f"{new_name}.py"
        merge_path = mig_dir / merge_filename
        
        merge_path.write_text(content)
        
        click.echo(f"\n✓ Created merge migration: {merge_path}")
        click.echo(f"  Dependencies: {len(heads)} heads merged")
    
    click.echo("\n" + "=" * 40)
    click.echo("✓ Merge migration(s) created!")
    click.echo("\nRun 'aksara migrate' to apply.")


# =============================================================================
# CLI Commands
# =============================================================================

@click.group()
@click.version_option(version=CLI_VERSION, prog_name="aksara")
def cli():
    """⚡ Aksara - Async Framework"""
    pass


@cli.command()
@click.argument("project_name")
@click.option("--directory", "-d", default=".", help="Directory to create project in (default: current)")
def startproject(project_name: str, directory: str):
    """
    Create a new Aksara project with scaffolded structure.
    
    PROJECT_NAME: Name of the project to create
    
    Creates a complete project structure with:
    - main.py (Aksara app entry point)
    - settings.py (AksaraSettings configuration)
    - app/ (models, views, serializers)
    - migrations/ (database migrations)
    - .env (environment configuration)
    - README.md (documentation)
    
    Example:
        aksara startproject blogapi
        cd blogapi
        aksara makemigrations --app app.models
        aksara migrate
        aksara run main:app --reload
    """
    from aksara.cli.scaffold import create_project_scaffold, write_scaffold_files
    
    # Validate project name
    if not project_name.isidentifier():
        click.echo(f"❌ Invalid project name: '{project_name}'")
        click.echo("   Project name must be a valid Python identifier")
        click.echo("   (letters, numbers, underscores, cannot start with number)")
        return
    
    base_path = Path(directory).resolve()
    project_path = base_path / project_name
    
    # Check if project already exists
    if project_path.exists():
        click.echo(f"❌ Directory already exists: {project_path}")
        return
    
    click.echo()
    click.echo(f"  ⚡ \033[1mAksara\033[0m v{CLI_VERSION}")
    click.echo("  \033[90mCreating new project...\033[0m")
    click.echo()
    
    try:
        # Generate and write scaffold files
        files = create_project_scaffold(project_name, base_path)
        write_scaffold_files(files)
        
        click.echo(f"  \033[32m✓\033[0m Created project: \033[1m{project_name}\033[0m")
        click.echo()
        click.echo("  Project structure:")
        click.echo(f"  \033[36m{project_name}/\033[0m")
        click.echo("  ├── main.py")
        click.echo("  ├── settings.py")
        click.echo("  ├── pyproject.toml")
        click.echo("  ├── .env")
        click.echo("  ├── .pre-commit-config.yaml")
        click.echo("  ├── .editorconfig")
        click.echo("  ├── requirements.txt")
        click.echo("  ├── README.md")
        click.echo("  ├── app/")
        click.echo("  │   ├── models.py")
        click.echo("  │   ├── views.py")
        click.echo("  │   ├── urls.py")
        click.echo("  │   └── serializers.py")
        click.echo("  └── migrations/")
        click.echo()
        click.echo("  \033[90m" + "─" * 40 + "\033[0m")
        click.echo()
        click.echo("  \033[1mNext steps:\033[0m")
        click.echo()
        click.echo(f"    cd {project_name}")
        click.echo('    pip install -e ".[dev]"       # Install with dev tools')
        click.echo("    pre-commit install            # Enable git hooks")
        click.echo("    # Edit .env with your database URL")
        click.echo("    aksara makemigrations --app app.models")
        click.echo("    aksara migrate")
        click.echo("    aksara run main:app --reload")
        click.echo()
        
    except Exception as e:
        click.echo(f"❌ Error creating project: {e}")
        return


@cli.command()
@click.argument("app_name")
@click.option("--directory", "-d", default=".", help="Directory to create app in (default: current)")
def startapp(app_name: str, directory: str):
    """
    Create a new Aksara app within an existing project.
    
    APP_NAME: Name of the app to create (e.g., 'blog', 'users', 'orders')
    
    Creates an app structure with:
    - models.py (Aksara ORM models)
    - views.py (ModelViewSet classes)
    - serializers.py (ModelSerializer classes)
    
    Example:
        aksara startapp blog
        aksara startapp users
        
    After creating the app, add it to settings.apps:
        settings = AksaraSettings(
            apps=["app", "blog", "users"],
        )
    """
    from aksara.cli.scaffold import create_app_scaffold, write_scaffold_files
    
    # Validate app name
    if not app_name.isidentifier():
        click.echo(f"❌ Invalid app name: '{app_name}'")
        click.echo("   App name must be a valid Python identifier")
        click.echo("   (letters, numbers, underscores, cannot start with number)")
        return
    
    base_path = Path(directory).resolve()
    app_path = base_path / app_name
    
    # Check if app already exists
    if app_path.exists():
        click.echo(f"❌ Directory already exists: {app_path}")
        return
    
    click.echo()
    click.echo(f"  ⚡ \033[1mAksara\033[0m v{CLI_VERSION}")
    click.echo("  \033[90mCreating new app...\033[0m")
    click.echo()
    
    try:
        # Generate and write scaffold files
        files = create_app_scaffold(app_name, base_path)
        write_scaffold_files(files)
        
        click.echo(f"  \033[32m✓\033[0m Created app: \033[1m{app_name}\033[0m")
        click.echo()
        click.echo("  App structure:")
        click.echo(f"  \033[36m{app_name}/\033[0m")
        click.echo("  ├── __init__.py")
        click.echo("  ├── models.py")
        click.echo("  ├── views.py")
        click.echo("  └── serializers.py")
        click.echo()
        click.echo("  \033[90m" + "─" * 40 + "\033[0m")
        click.echo()
        click.echo("  \033[1mNext steps:\033[0m")
        click.echo()
        click.echo(f"  1. Add '{app_name}' to settings.apps in settings.py:")
        click.echo()
        click.echo("     settings = AksaraSettings(")
        click.echo(f'         apps=["app", "{app_name}"],')
        click.echo("     )")
        click.echo()
        click.echo(f"  2. Define your models in {app_name}/models.py")
        click.echo(f"  3. Create ViewSets in {app_name}/views.py")
        click.echo("  4. Run migrations:")
        click.echo(f"     aksara makemigrations --app {app_name}.models")
        click.echo("     aksara migrate")
        click.echo()
        
    except Exception as e:
        click.echo(f"❌ Error creating app: {e}")
        return


@cli.command()
@click.option("--app", "-a", help="Path to application models module")
@click.option("--output", "-o", help="Output directory for migrations (default: ./migrations)")
@click.option("--name", "-n", default="auto", help="Migration name prefix")
@click.option("--stdout", is_flag=True, help="Output to stdout instead of file")
@click.option("--sql", is_flag=True, help="Generate legacy SQL migration (default: Python)")
@click.option("--merge", is_flag=True, help="Create a merge migration to resolve conflicts")
@click.argument("merge_app", required=False)
def makemigrations(
    app: Optional[str], 
    output: Optional[str], 
    name: str, 
    stdout: bool, 
    sql: bool,
    merge: bool,
    merge_app: Optional[str],
):
    """Generate migration from models (Python or SQL).
    
    Use --merge APP_LABEL to create a merge migration that resolves
    conflicting migrations (multiple heads) for the specified app.
    """
    from aksara.registry import ModelRegistry
    from aksara.conf import settings
    from aksara.migrations.executor import (
        generate_migration_filename,
        models_to_migration_code,
        discover_migrations,
        build_migration_graph,
    )
    from aksara.migrations.graph import find_conflicts
    
    # Handle --merge mode
    if merge:
        _handle_merge_migration(merge_app, output, settings)
        return
    
    click.echo("⚡ Aksara Makemigrations")
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

from aksara.migrations import Migration
from aksara.migrations import operations as op


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

from aksara.migrations import Migration
from aksara.migrations import operations as op


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
        click.echo("\n  To apply: aksara migrate")


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
    from aksara.registry import ModelRegistry
    from aksara.db import Database
    from aksara.conf import settings
    from aksara.migrations.executor import (
        apply_migrations,
        discover_migrations,
        get_pending_migrations,
        ensure_migrations_table,
        get_applied_migrations as get_applied_migs,
        record_migration,
        load_migration_module,
        build_migration_graph,
        check_migration_conflicts,
    )
    from aksara.migrations.graph import format_conflict_message
    
    click.echo("⚡ Aksara Migrate")
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
        
        # v0.3.16: Build migration graph and check for conflicts
        graph = build_migration_graph(migrations_list=migration_files)
        
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
        graph = None  # No graph for model-based migrations
    
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
                
                # v0.3.16: Check for conflicts before proceeding
                if graph is not None:
                    conflicts = check_migration_conflicts(graph, applied)
                    if conflicts:
                        click.echo("\n" + click.style("❌ Migration Conflicts Detected!", fg="red", bold=True))
                        click.echo(format_conflict_message(conflicts))
                        click.echo("\nMigration aborted. Resolve conflicts first.")
                        return
                
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
                            click.echo(f"\nApplying {name}...")
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
    from aksara.db import Database
    from aksara.conf import settings
    from aksara.migrations.executor import (
        discover_migrations,
        ensure_migrations_table,
        get_applied_migrations as get_applied_migs,
    )
    
    click.echo("⚡ Aksara Migration Status")
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
@click.option("--no-ipython", is_flag=True, help="Disable IPython even if available")
def shell(database_url: Optional[str], no_ipython: bool):
    """
    Open an interactive async shell with Aksara.
    
    Starts a Python shell with Aksara imports pre-loaded, database
    connection ready, and the arun() helper for running async code.
    
    Uses IPython if available, falls back to standard Python shell.
    
    Examples:
    
        $ aksara shell
        
        # In the shell:
        aksara> users = arun(User.objects.all())
        aksara> user = arun(User.objects.get(id=1))
        aksara> arun(user.posts.all())
    """
    from aksara.shell import run_shell
    
    db_url = database_url or None
    run_shell(database_url=db_url, use_ipython=not no_ipython)


@cli.command()
@click.option("--database-url", "-d", envvar="DATABASE_URL",
              help="PostgreSQL connection URL (or set DATABASE_URL env var)")
@click.option("--email", "-e", prompt="Email", help="Admin user email address")
@click.option("--password", "-p", prompt=True, hide_input=True, 
              confirmation_prompt=True, help="Admin user password")
def createsuperuser(database_url: Optional[str], email: str, password: str):
    """
    Create a superuser for the admin interface.
    
    Creates a new user with is_staff=True and is_superuser=True,
    which grants full access to the admin interface.
    
    Example:
        aksara createsuperuser
        aksara createsuperuser --email admin@example.com
    """
    from aksara.conf import settings
    from aksara.db import Database
    
    click.echo()
    click.echo(f"  ⚡ \033[1mAksara\033[0m v{CLI_VERSION}")
    click.echo("  \033[90mCreating superuser...\033[0m")
    click.echo()
    
    # Get database URL
    db_url = database_url or settings.database_url
    if not db_url:
        click.echo("❌ No database URL provided!")
        click.echo("   Set DATABASE_URL or use --database-url")
        return
    
    async def create_user():
        try:
            from aksara.contrib.auth import User
        except ImportError:
            click.echo("❌ aksara.contrib.auth is not available.")
            click.echo("   Make sure auth tables are migrated.")
            return False
        
        db = Database(db_url)
        
        try:
            await db.connect()
            
            # Check if aksara_users table exists, create if not
            table_exists = await db.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'aksara_users'
                )
            """)
            
            if not table_exists:
                click.echo("  📦 Creating auth tables...")
                # Create the aksara_users table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS aksara_users (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        email VARCHAR(255) UNIQUE NOT NULL,
                        hashed_password VARCHAR(255) NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        is_staff BOOLEAN DEFAULT FALSE,
                        is_superuser BOOLEAN DEFAULT FALSE,
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                # Create index on email
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_aksara_users_email 
                    ON aksara_users(email)
                """)
                click.echo("  \033[32m✓\033[0m Auth tables created.")
            
            # Check if user already exists
            existing = await User.objects.get_by_email(email)
            if existing:
                click.echo(f"  ⚠️  User with email '{email}' already exists.")
                if existing.is_superuser:
                    click.echo("     User is already a superuser.")
                else:
                    click.echo("     Updating to superuser status...")
                    existing.is_staff = True
                    existing.is_superuser = True
                    await existing.save()
                    click.echo(f"  \033[32m✓\033[0m User updated to superuser.")
                return True
            
            # Create new superuser
            user = await User.objects.create_superuser(
                email=email,
                password=password,
            )
            
            click.echo(f"  \033[32m✓\033[0m Superuser created: {user.email}")
            click.echo()
            click.echo("  You can now log in to the admin interface.")
            return True
            
        except Exception as e:
            click.echo(f"  ❌ Error: {e}")
            return False
        finally:
            await db.disconnect()
    
    success = asyncio.run(create_user())
    if not success:
        sys.exit(1)


@cli.command()
@click.option("--database-url", "-d", envvar="DATABASE_URL",
              help="PostgreSQL connection URL (or set DATABASE_URL env var)")
def info(database_url: Optional[str]):
    """
    Show Aksara environment information.
    
    Displays version, database connection status, configured apps,
    and pending migrations. Useful for debugging configuration issues.
    """
    from aksara import __version__
    from aksara.conf import settings
    from aksara.registry import ModelRegistry
    
    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara Info\033[0m")
    click.echo("  " + "-" * 36)
    
    # Version info
    click.echo(f"\n  \033[1mVersion:\033[0m {__version__}")
    click.echo(f"  \033[1mCLI Version:\033[0m {CLI_VERSION}")
    
    # Database URL (redacted)
    db_url = database_url or settings.database_url
    if db_url:
        # Redact password from URL
        redacted = _redact_db_url(db_url)
        click.echo(f"  \033[1mDatabase:\033[0m {redacted}")
    else:
        click.echo(f"  \033[1mDatabase:\033[0m \033[90mNot configured\033[0m")
    
    # Settings
    click.echo(f"  \033[1mDebug:\033[0m {settings.debug}")
    click.echo(f"  \033[1mMigrations Dir:\033[0m {settings.migrations_dir}")
    
    # Apps
    click.echo(f"\n  \033[1mConfigured Apps:\033[0m")
    for app in settings.apps:
        click.echo(f"    • {app}")
    
    # Discover models
    for app in settings.apps:
        try:
            import importlib
            importlib.import_module(f"{app}.models")
        except ImportError:
            pass
    
    all_models = ModelRegistry.all()
    click.echo(f"\n  \033[1mRegistered Models:\033[0m {len(all_models)}")
    if all_models:
        for name in sorted(all_models.keys())[:10]:
            click.echo(f"    • {name}")
        if len(all_models) > 10:
            click.echo(f"    ... and {len(all_models) - 10} more")
    
    # Pending migrations (if DB is configured)
    if db_url:
        async def check_migrations():
            from aksara.migrations.executor import (
                discover_migrations,
                get_pending_migrations,
                ensure_migrations_table,
                get_applied_migrations as get_applied_migs,
                discover_internal_migrations,
            )
            from aksara.db import Database
            
            try:
                db = Database(db_url)
                await db.connect()
                await ensure_migrations_table(db)
                applied = await get_applied_migs(db)
                await db.disconnect()
                
                # Discover migrations
                mig_dir = Path(settings.migrations_dir)
                user_migrations = discover_migrations(mig_dir) if mig_dir.exists() else []
                internal_migrations = discover_internal_migrations()
                all_migrations = user_migrations + internal_migrations
                
                pending = get_pending_migrations(all_migrations, applied)
                
                click.echo(f"\n  \033[1mMigrations:\033[0m")
                click.echo(f"    Applied: {len(applied)}")
                click.echo(f"    Pending: {len(pending)}")
                
                if pending:
                    click.echo(f"\n  \033[1mPending Migrations:\033[0m")
                    for name, _ in pending[:5]:
                        click.echo(f"    • {name}")
                    if len(pending) > 5:
                        click.echo(f"    ... and {len(pending) - 5} more")
                        
            except Exception as e:
                click.echo(f"\n  \033[33m⚠️  Could not check migrations:\033[0m {e}")
        
        asyncio.run(check_migrations())
    
    click.echo()


def _redact_db_url(url: str) -> str:
    """Redact password from database URL for display."""
    import re
    # Match postgresql://user:password@host... pattern
    pattern = r"(postgresql(?:\+\w+)?://[^:]+:)([^@]+)(@.+)"
    match = re.match(pattern, url)
    if match:
        return f"{match.group(1)}****{match.group(3)}"
    return url


@cli.command()
@click.option("--app", "-a", help="Path to application models module")
@click.option("--ai", is_flag=True, help="Show AI metadata")
def models(app: Optional[str], ai: bool):
    """List all registered models."""
    from aksara.registry import ModelRegistry, get_model_meta
    
    click.echo("⚡ Aksara Models")
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
    Run a Aksara application with uvicorn.
    
    APP_PATH: Import path to the app (e.g., 'main:app' or 'myproject.main:app')
    
    Example:
        aksara run main:app --reload
        aksara run myproject.main:app --host 0.0.0.0 --port 8080
    """
    try:
        import uvicorn
    except ImportError:
        click.echo("❌ uvicorn not installed. Run: pip install uvicorn")
        return
    
    # Ensure current directory is in Python path for module imports
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    
    # Print Aksara banner
    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m v{CLI_VERSION}")
    click.echo("  \033[90mAsync Postgres ORM for FastAPI\033[0m")
    click.echo()
    click.echo(f"  \033[36m→\033[0m Running: {app_path}")
    click.echo(f"  \033[36m→\033[0m Server:  http://{host}:{port}")
    if reload:
        click.echo(f"  \033[36m→\033[0m Reload:  \033[32menabled\033[0m")
    click.echo()
    click.echo("  \033[90m" + "─" * 40 + "\033[0m")
    click.echo()
    
    # Configure uvicorn - use app_dir for proper module resolution
    uvicorn.run(
        app_path,
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        log_level="info",
        access_log=True,
        app_dir=cwd,  # Ensure uvicorn can find the app module
    )


# =============================================================================
# v0.3.18: Developer Workflow Commands
# =============================================================================

def _run_tool(tool_name: str, module: str, args: List[str], install_hint: str) -> int:
    """
    Run a dev tool via subprocess.
    
    Args:
        tool_name: Display name of the tool (e.g., "Black")
        module: Python module to run (e.g., "black")
        args: Arguments to pass to the tool
        install_hint: Package name for pip install hint
    
    Returns:
        Exit code from the tool
    """
    import subprocess
    
    cmd = [sys.executable, "-m", module] + args
    
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        click.echo(f"\n❌ {tool_name} is not installed.")
        click.echo(f"   Install dev tools via:")
        click.echo(f"     pip install aksara[dev]")
        click.echo(f"   or:")
        click.echo(f"     pip install {install_hint}")
        click.echo()
        return 1


@cli.command()
@click.argument("path", default=".", required=False)
@click.option("--check", is_flag=True, help="Check formatting without making changes")
def format(path: str, check: bool):
    """Format code using Black.
    
    Runs Black formatter on the specified path (default: current directory).
    
    Examples:
        aksara format
        aksara format src/
        aksara format --check
    """
    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m - Formatting code...")
    click.echo()
    
    args = [path]
    if check:
        args.append("--check")
    
    exit_code = _run_tool("Black", "black", args, "black")
    sys.exit(exit_code)


@cli.command()
@click.argument("path", default=".", required=False)
@click.option("--fix", is_flag=True, help="Automatically fix fixable issues")
def lint(path: str, fix: bool):
    """Lint code using Ruff.
    
    Runs Ruff linter on the specified path (default: current directory).
    
    Examples:
        aksara lint
        aksara lint src/
        aksara lint --fix
    """
    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m - Linting code...")
    click.echo()
    
    args = ["check", path]
    if fix:
        args.append("--fix")
    
    exit_code = _run_tool("Ruff", "ruff", args, "ruff")
    sys.exit(exit_code)


@cli.command()
@click.argument("path", default=".", required=False)
@click.option("--strict", is_flag=True, help="Enable strict mode")
def typecheck(path: str, strict: bool):
    """Type-check code using mypy.
    
    Runs mypy type checker on the specified path (default: current directory).
    
    Examples:
        aksara typecheck
        aksara typecheck src/
        aksara typecheck --strict
    """
    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m - Type-checking code...")
    click.echo()
    
    args = [path]
    if strict:
        args.append("--strict")
    
    exit_code = _run_tool("mypy", "mypy", args, "mypy")
    sys.exit(exit_code)


@cli.command(context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def test(args: tuple):
    """Run tests using pytest.
    
    Runs pytest with any additional arguments passed through.
    
    Examples:
        aksara test
        aksara test tests/
        aksara test -v --tb=short
        aksara test tests/test_models.py -k "test_create"
    """
    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m - Running tests...")
    click.echo()
    
    exit_code = _run_tool("pytest", "pytest", list(args), "pytest")
    sys.exit(exit_code)


# Pre-commit configuration template
PRECOMMIT_CONFIG = '''# Aksara Pre-commit Configuration
# Install hooks: pre-commit install
# Run all hooks: aksara precommit run

repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: ["--fix"]

  - repo: https://github.com/psf/black
    rev: 24.4.2
    hooks:
      - id: black

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: []

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: check-yaml
'''


@cli.group()
def precommit():
    """Pre-commit hook management.
    
    Commands for managing pre-commit hooks in your project.
    """
    pass


@precommit.command("init")
def precommit_init():
    """Scaffold .pre-commit-config.yaml for your project.
    
    Creates a standard pre-commit configuration with:
    - Ruff (linting with auto-fix)
    - Black (formatting)
    - mypy (type checking)
    - Common pre-commit hooks (large files, merge conflicts, YAML)
    
    Example:
        aksara precommit init
        pre-commit install
    """
    config_path = Path.cwd() / ".pre-commit-config.yaml"
    
    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m - Pre-commit Setup")
    click.echo()
    
    if config_path.exists():
        click.echo("  \033[33m⚠️\033[0m  .pre-commit-config.yaml already exists; not overwriting.")
        click.echo()
        click.echo("  To regenerate, delete the file first:")
        click.echo(f"    rm {config_path}")
        click.echo()
        return
    
    # Write the config file
    with open(config_path, "w") as f:
        f.write(PRECOMMIT_CONFIG)
    
    click.echo("  \033[32m✓\033[0m Created .pre-commit-config.yaml")
    click.echo()
    click.echo("  \033[90m" + "─" * 40 + "\033[0m")
    click.echo()
    click.echo("  \033[1mNext steps:\033[0m")
    click.echo()
    click.echo("    pre-commit install        # Install git hooks")
    click.echo("    aksara precommit run      # Run on all files")
    click.echo()


@precommit.command("run")
@click.option("--hook", "-h", help="Run a specific hook by ID")
def precommit_run(hook: Optional[str]):
    """Run pre-commit hooks on all files.
    
    Runs all configured pre-commit hooks against all files in the repository.
    
    Examples:
        aksara precommit run
        aksara precommit run --hook ruff
        aksara precommit run --hook black
    """
    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m - Running pre-commit hooks...")
    click.echo()
    
    args = ["run", "--all-files"]
    if hook:
        args.extend(["--hook-stage", "manual", hook])
    
    exit_code = _run_tool("pre-commit", "pre_commit", args, "pre-commit")
    sys.exit(exit_code)


# =============================================================================
# AI CLI Commands (v0.4.8)
# =============================================================================

@cli.group()
def ai():
    """AI-powered development commands.
    
    Commands for interacting with Aksara's AI subsystems:
    - Context gathering for LLM agents
    - Schema health and drift detection
    - Plan preview and application
    
    These commands are LLM-provider-agnostic. They do NOT call any
    AI models directly; they provide structured data that external
    AI agents can use.
    
    Example workflow:
        aksara ai context --intent "Add Category model"  # Get context
        # ... external AI generates plan.json ...
        aksara ai plan preview plan.json               # Preview changes
        aksara ai plan apply plan.json --yes           # Apply changes
    """
    pass


def _setup_app_for_cli(database_url: Optional[str] = None) -> "FastAPI":
    """
    Set up a minimal FastAPI app for CLI commands.
    
    This loads settings, discovers models, and optionally connects to DB.
    """
    from fastapi import FastAPI
    from aksara.conf import settings
    from aksara.registry import ModelRegistry
    import importlib
    
    # Add current directory to path
    cwd = Path.cwd()
    if str(cwd) not in sys.path:
        sys.path.insert(0, str(cwd))
    
    # Discover models from configured apps
    for app_name in settings.apps:
        try:
            importlib.import_module(f"{app_name}.models")
        except ImportError:
            pass
    
    # Create a minimal FastAPI app
    app = FastAPI()
    
    # Store settings on app for context builders
    app.state.settings = settings
    
    return app


async def _connect_db_for_cli(database_url: Optional[str] = None):
    """Connect to database for CLI commands that need it."""
    from aksara.conf import settings
    from aksara.db import Database
    
    db_url = database_url or settings.database_url
    if db_url:
        db = Database(db_url)
        await db.connect()
        return db
    return None


@ai.command("context")
@click.option("--intent", "-i", help="The intent/request to get context for")
@click.option("--mode", "-m", type=click.Choice(["read", "design", "modify"]), 
              default="modify", help="Operation mode (default: modify)")
@click.option("--scope", "-s", help="Comma-separated scope (e.g., 'models,routes,admin')")
@click.option("--stdin", "use_stdin", is_flag=True, help="Read intent from stdin")
@click.option("--format", "-f", "output_format", type=click.Choice(["json", "summary"]),
              default="summary", help="Output format (default: summary)")
@click.option("--database-url", envvar="DATABASE_URL", help="Database URL")
def ai_context(
    intent: Optional[str],
    mode: str,
    scope: Optional[str],
    use_stdin: bool,
    output_format: str,
    database_url: Optional[str],
):
    """
    Get context bundle for an AI agent.
    
    Builds an AgentContextBundle containing everything an external AI needs
    to understand the application and generate plans.
    
    The bundle includes:
    - Full context (models, routes, migrations, admin, settings)
    - Schema definitions for plans, patches, queries
    - Available AI tools
    
    Examples:
        aksara ai context --intent "Add a Category model"
        aksara ai context --intent "What does this app look like?" --format json
        echo "Add slug to Article" | aksara ai context --stdin --format json
    """
    import json
    
    # Get intent from stdin or flag
    if use_stdin:
        intent_text = sys.stdin.read().strip()
    elif intent:
        intent_text = intent
    else:
        click.echo("❌ Error: --intent is required (or use --stdin)", err=True)
        sys.exit(1)
    
    if not intent_text:
        click.echo("❌ Error: Intent cannot be empty", err=True)
        sys.exit(1)
    
    # Parse scope
    scope_list = [s.strip() for s in scope.split(",")] if scope else None
    
    try:
        from aksara.ai.agent import AgentIntent, build_agent_context_bundle
        
        # Build intent
        agent_intent = AgentIntent(
            user_message=intent_text,
            mode=mode,
            scope=scope_list,
        )
        
        # Set up app and build context
        app = _setup_app_for_cli(database_url)
        
        async def get_context():
            # Connect to DB if available
            await _connect_db_for_cli(database_url)
            return await build_agent_context_bundle(app, agent_intent)
        
        bundle = asyncio.run(get_context())
        
        if output_format == "json":
            click.echo(json.dumps(bundle.model_dump(), indent=2))
        else:
            # Summary format
            click.echo()
            click.echo(f"  \033[33m⚡\033[0m \033[1mAksara AI Context\033[0m")
            click.echo("  " + "-" * 36)
            click.echo()
            click.echo(f"  \033[1mIntent:\033[0m {intent_text[:60]}{'...' if len(intent_text) > 60 else ''}")
            click.echo(f"  \033[1mMode:\033[0m {mode}")
            if scope_list:
                click.echo(f"  \033[1mScope:\033[0m {', '.join(scope_list)}")
            click.echo()
            
            ctx = bundle.full_context
            click.echo(f"  \033[1mContext Summary:\033[0m")
            click.echo(f"    Models:     {len(ctx.get('models', []))}")
            click.echo(f"    ViewSets:   {len(ctx.get('viewsets', []))}")
            click.echo(f"    Routes:     {len(ctx.get('routes', []))}")
            click.echo(f"    Migrations: {len(ctx.get('migrations', []))}")
            click.echo(f"    Tools:      {len(bundle.tools)}")
            click.echo()
            click.echo(f"  \033[1mVersion:\033[0m {bundle.version}")
            click.echo()
        
        sys.exit(0)
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@ai.command("schema-health")
@click.option("--format", "-f", "output_format", type=click.Choice(["table", "json"]),
              default="table", help="Output format (default: table)")
@click.option("--database-url", envvar="DATABASE_URL", help="Database URL")
def ai_schema_health(output_format: str, database_url: Optional[str]):
    """
    Check schema health (models vs database drift).
    
    Analyzes the database schema and compares it against registered models
    to detect drift and inconsistencies.
    
    Status levels:
    - healthy:  No warnings or danger issues
    - degraded: Has warnings but no danger issues
    - danger:   Has at least one danger-level issue
    
    Examples:
        aksara ai schema-health
        aksara ai schema-health --format json
    """
    import json
    
    try:
        from aksara.ai.schema_doctor import analyze_schema_health
        
        app = _setup_app_for_cli(database_url)
        
        async def get_health():
            await _connect_db_for_cli(database_url)
            return await analyze_schema_health(app)
        
        health = asyncio.run(get_health())
        
        if output_format == "json":
            click.echo(json.dumps(health.model_dump(), indent=2))
        else:
            # Table format
            click.echo()
            click.echo(f"  \033[33m⚡\033[0m \033[1mSchema Health\033[0m")
            click.echo("  " + "-" * 36)
            click.echo()
            
            # Color-code status
            status_colors = {
                "healthy": "\033[32m",   # Green
                "degraded": "\033[33m",  # Yellow
                "danger": "\033[31m",    # Red
            }
            color = status_colors.get(health.status, "")
            reset = "\033[0m"
            
            click.echo(f"  \033[1mStatus:\033[0m   {color}{health.status.upper()}{reset}")
            click.echo()
            click.echo(f"  \033[1mIssues:\033[0m")
            click.echo(f"    Info:     {health.issue_counts.get('info', 0)}")
            click.echo(f"    Warning:  {health.issue_counts.get('warning', 0)}")
            click.echo(f"    Danger:   {health.issue_counts.get('danger', 0)}")
            click.echo()
            
            if health.db_name:
                click.echo(f"  \033[1mDatabase:\033[0m {health.db_name}")
            if health.db_version:
                click.echo(f"  \033[1mDB Version:\033[0m {health.db_version}")
            click.echo(f"  \033[1mInspected:\033[0m {health.inspected_at}")
            click.echo()
        
        # Exit code based on status
        if health.status == "danger":
            sys.exit(1)
        sys.exit(0)
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@ai.command("schema-issues")
@click.option("--severity", "-s", help="Filter by severity (info, warning, danger)")
@click.option("--kind", "-k", help="Filter by kind (comma-separated: missing_table,extra_column,...)")
@click.option("--table", "-t", help="Filter by table name")
@click.option("--app-label", "-a", help="Filter by app label")
@click.option("--format", "-f", "output_format", type=click.Choice(["table", "json"]),
              default="table", help="Output format (default: table)")
@click.option("--database-url", envvar="DATABASE_URL", help="Database URL")
def ai_schema_issues(
    severity: Optional[str],
    kind: Optional[str],
    table: Optional[str],
    app_label: Optional[str],
    output_format: str,
    database_url: Optional[str],
):
    """
    List schema issues with optional filtering.
    
    Shows detailed drift and inconsistencies between models and database.
    
    Filter options:
        --severity: Filter by severity level (info, warning, danger)
        --kind: Filter by drift kind (missing_table, extra_column, type_mismatch, etc.)
        --table: Filter by specific table name
        --app-label: Filter by application label
    
    Examples:
        aksara ai schema-issues
        aksara ai schema-issues --severity danger
        aksara ai schema-issues --kind missing_column,type_mismatch
        aksara ai schema-issues --format json
    """
    import json
    
    # Validate severity
    valid_severities = {"info", "warning", "danger"}
    if severity and severity not in valid_severities:
        click.echo(f"❌ Error: Invalid severity '{severity}'. Must be one of: {valid_severities}", err=True)
        sys.exit(1)
    
    # Parse kind list
    kind_list = [k.strip() for k in kind.split(",")] if kind else None
    
    try:
        from aksara.ai.schema_doctor import analyze_schema_health
        
        app = _setup_app_for_cli(database_url)
        
        async def get_health():
            await _connect_db_for_cli(database_url)
            return await analyze_schema_health(app)
        
        health = asyncio.run(get_health())
        
        # Filter issues
        issues = health.issues
        
        if severity:
            issues = [i for i in issues if i.severity == severity]
        if kind_list:
            issues = [i for i in issues if i.kind in kind_list]
        if table:
            issues = [i for i in issues if i.table == table]
        if app_label:
            issues = [i for i in issues if i.app_label == app_label]
        
        if output_format == "json":
            click.echo(json.dumps([i.model_dump() for i in issues], indent=2))
        else:
            # Table format
            click.echo()
            click.echo(f"  \033[33m⚡\033[0m \033[1mSchema Issues\033[0m ({len(issues)} found)")
            click.echo("  " + "-" * 60)
            
            if not issues:
                click.echo()
                click.echo("  ✓ No issues found")
                click.echo()
            else:
                # Print header
                click.echo()
                click.echo(f"  {'SEV':<8} {'KIND':<20} {'TABLE':<20} {'COLUMN':<15}")
                click.echo("  " + "-" * 63)
                
                severity_colors = {
                    "info": "\033[34m",     # Blue
                    "warning": "\033[33m",  # Yellow
                    "danger": "\033[31m",   # Red
                }
                reset = "\033[0m"
                
                for issue in issues:
                    color = severity_colors.get(issue.severity, "")
                    sev = f"{color}{issue.severity:<8}{reset}"
                    kind_str = (issue.kind[:18] + "..") if len(issue.kind) > 20 else issue.kind
                    table_str = ((issue.table or "-")[:18] + "..") if len(issue.table or "") > 20 else (issue.table or "-")
                    col_str = ((issue.column or "-")[:13] + "..") if len(issue.column or "") > 15 else (issue.column or "-")
                    click.echo(f"  {sev} {kind_str:<20} {table_str:<20} {col_str:<15}")
                
                click.echo()
                
                # Show first few messages
                click.echo("  \033[1mDetails:\033[0m")
                for issue in issues[:5]:
                    click.echo(f"    • {issue.message[:70]}{'...' if len(issue.message) > 70 else ''}")
                if len(issues) > 5:
                    click.echo(f"    ... and {len(issues) - 5} more")
                click.echo()
        
        sys.exit(0)
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


# Plan subgroup
@ai.group()
def plan():
    """AI plan preview and application.
    
    Commands for working with AI-generated plans:
    - Preview plan execution (dry run)
    - Apply plans to the codebase
    - Generate plan templates
    
    Plans are JSON files containing an intent and execution steps.
    They are typically generated by external AI agents.
    """
    pass


@plan.command("preview")
@click.argument("path", required=False)
@click.option("--format", "-f", "output_format", type=click.Choice(["summary", "json"]),
              default="summary", help="Output format (default: summary)")
@click.option("--database-url", envvar="DATABASE_URL", help="Database URL")
def plan_preview(path: Optional[str], output_format: str, database_url: Optional[str]):
    """
    Preview a plan file (dry run).
    
    Executes the plan in dry-run mode without making any changes.
    Shows what would happen if the plan were applied.
    
    PATH: Path to plan.json file, or '-' to read from stdin
    
    Expected plan.json structure:
        {
            "intent": { "user_message": "...", "mode": "modify" },
            "plan": { "intent": "...", "steps": [...] }
        }
    
    Examples:
        aksara ai plan preview plan.json
        aksara ai plan preview plan.json --format json
        cat plan.json | aksara ai plan preview -
    """
    import json
    
    # Read plan from file or stdin
    try:
        if path == "-" or path is None:
            plan_data = json.loads(sys.stdin.read())
        else:
            with open(path, "r") as f:
                plan_data = json.load(f)
    except json.JSONDecodeError as e:
        click.echo(f"❌ Error: Invalid JSON: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.echo(f"❌ Error: File not found: {path}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error reading plan: {e}", err=True)
        sys.exit(1)
    
    try:
        from aksara.ai.agent import AgentIntent, AgentPlanPreviewResponse
        from aksara.ai.planner import AiPlan, execute_plan, validate_plan
        
        # Parse intent and plan
        intent_data = plan_data.get("intent", {})
        plan_dict = plan_data.get("plan", {})
        
        if not plan_dict:
            click.echo("❌ Error: Plan JSON must have a 'plan' key", err=True)
            sys.exit(1)
        
        intent = AgentIntent(**intent_data) if intent_data else AgentIntent(user_message="CLI preview")
        ai_plan = AiPlan(**plan_dict)
        
        # Validate plan
        errors = validate_plan(ai_plan)
        if errors:
            click.echo("❌ Plan validation failed:", err=True)
            for err in errors:
                click.echo(f"  • {err}", err=True)
            sys.exit(1)
        
        app = _setup_app_for_cli(database_url)
        
        async def run_preview():
            await _connect_db_for_cli(database_url)
            return await execute_plan(app, ai_plan, dry_run=True)
        
        execution = asyncio.run(run_preview())
        
        # Build response
        response = AgentPlanPreviewResponse(
            intent=intent,
            plan=plan_dict,
            execution=execution.model_dump(),
            summary={
                "success": execution.success,
                "step_count": len(execution.steps),
                "failed_steps": [s.id for s in execution.steps if not s.success],
            }
        )
        
        if output_format == "json":
            click.echo(json.dumps(response.model_dump(), indent=2))
        else:
            # Summary format
            click.echo()
            click.echo(f"  \033[33m⚡\033[0m \033[1mPlan Preview\033[0m (dry run)")
            click.echo("  " + "-" * 36)
            click.echo()
            click.echo(f"  \033[1mIntent:\033[0m {intent.user_message[:50]}{'...' if len(intent.user_message) > 50 else ''}")
            click.echo(f"  \033[1mPlan:\033[0m {ai_plan.intent[:50]}{'...' if len(ai_plan.intent) > 50 else ''}")
            click.echo(f"  \033[1mSteps:\033[0m {len(ai_plan.steps)}")
            click.echo()
            
            # Status color
            if execution.success:
                status = "\033[32m✓ WOULD SUCCEED\033[0m"
            else:
                status = "\033[31m✗ WOULD FAIL\033[0m"
            click.echo(f"  \033[1mResult:\033[0m {status}")
            click.echo()
            
            # Step details
            click.echo(f"  \033[1mStep Results:\033[0m")
            for step_result in execution.steps:
                if step_result.success:
                    icon = "\033[32m✓\033[0m"
                else:
                    icon = "\033[31m✗\033[0m"
                click.echo(f"    {icon} {step_result.id} ({step_result.type})")
                if not step_result.success and step_result.error:
                    click.echo(f"      Error: {step_result.error[:60]}...")
            click.echo()
            
            # Notes
            if execution.notes:
                click.echo(f"  \033[1mNotes:\033[0m")
                for note in execution.notes[:5]:
                    click.echo(f"    • {note}")
                click.echo()
        
        sys.exit(0 if execution.success else 1)
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@plan.command("apply")
@click.argument("path", required=False)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--format", "-f", "output_format", type=click.Choice(["summary", "json"]),
              default="summary", help="Output format (default: summary)")
@click.option("--database-url", envvar="DATABASE_URL", help="Database URL")
def plan_apply(path: Optional[str], yes: bool, output_format: str, database_url: Optional[str]):
    """
    Apply a plan file to the codebase.
    
    ⚠️  This will modify files on disk!
    
    Executes the plan for real, making actual changes.
    Requires confirmation unless --yes is provided.
    
    PATH: Path to plan.json file, or '-' to read from stdin
    
    Examples:
        aksara ai plan apply plan.json
        aksara ai plan apply plan.json --yes
        cat plan.json | aksara ai plan apply - --yes
    """
    import json
    
    # Read plan from file or stdin
    try:
        if path == "-" or path is None:
            plan_data = json.loads(sys.stdin.read())
        else:
            with open(path, "r") as f:
                plan_data = json.load(f)
    except json.JSONDecodeError as e:
        click.echo(f"❌ Error: Invalid JSON: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.echo(f"❌ Error: File not found: {path}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error reading plan: {e}", err=True)
        sys.exit(1)
    
    try:
        from aksara.ai.agent import AgentIntent, AgentPlanApplyResponse
        from aksara.ai.planner import AiPlan, execute_plan, validate_plan
        
        # Parse intent and plan
        intent_data = plan_data.get("intent", {})
        plan_dict = plan_data.get("plan", {})
        
        if not plan_dict:
            click.echo("❌ Error: Plan JSON must have a 'plan' key", err=True)
            sys.exit(1)
        
        intent = AgentIntent(**intent_data) if intent_data else AgentIntent(user_message="CLI apply")
        ai_plan = AiPlan(**plan_dict)
        
        # Validate plan
        errors = validate_plan(ai_plan)
        if errors:
            click.echo("❌ Plan validation failed:", err=True)
            for err in errors:
                click.echo(f"  • {err}", err=True)
            sys.exit(1)
        
        # Confirmation prompt
        if not yes:
            click.echo()
            click.echo(f"  \033[33m⚠️  WARNING\033[0m")
            click.echo()
            click.echo(f"  This will APPLY the plan to your codebase.")
            click.echo(f"  Intent: {intent.user_message[:50]}{'...' if len(intent.user_message) > 50 else ''}")
            click.echo(f"  Steps: {len(ai_plan.steps)}")
            click.echo()
            
            if not click.confirm("  Continue?", default=False):
                click.echo("  Aborted.")
                sys.exit(0)
        
        app = _setup_app_for_cli(database_url)
        
        async def run_apply():
            await _connect_db_for_cli(database_url)
            return await execute_plan(app, ai_plan, dry_run=False)
        
        execution = asyncio.run(run_apply())
        
        # Build response
        response = AgentPlanApplyResponse(
            intent=intent,
            plan=plan_dict,
            execution=execution.model_dump(),
        )
        
        if output_format == "json":
            click.echo(json.dumps(response.model_dump(), indent=2))
        else:
            # Summary format
            click.echo()
            click.echo(f"  \033[33m⚡\033[0m \033[1mPlan Applied\033[0m")
            click.echo("  " + "-" * 36)
            click.echo()
            
            # Status color
            if execution.success:
                status = "\033[32m✓ SUCCESS\033[0m"
            else:
                status = "\033[31m✗ FAILED\033[0m"
            click.echo(f"  \033[1mResult:\033[0m {status}")
            click.echo()
            
            # Step details
            click.echo(f"  \033[1mStep Results:\033[0m")
            for step_result in execution.steps:
                if step_result.success:
                    icon = "\033[32m✓\033[0m"
                else:
                    icon = "\033[31m✗\033[0m"
                click.echo(f"    {icon} {step_result.id} ({step_result.type})")
                if not step_result.success and step_result.error:
                    click.echo(f"      Error: {step_result.error[:60]}...")
            click.echo()
        
        sys.exit(0 if execution.success else 1)
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@plan.command("template")
@click.option("--intent", "-i", required=True, help="The intent for the plan template")
@click.option("--mode", "-m", type=click.Choice(["read", "design", "modify"]),
              default="modify", help="Operation mode (default: modify)")
@click.option("--include-schema", is_flag=True, help="Include plan JSON schema in output")
def plan_template(intent: str, mode: str, include_schema: bool):
    """
    Generate a plan template for external AI.
    
    Creates a starter JSON structure that can be filled in by an
    external AI agent and then used with `plan preview` or `plan apply`.
    
    Examples:
        aksara ai plan template --intent "Add Category model" > plan.json
        aksara ai plan template --intent "Add slug field" --include-schema
    """
    import json
    
    try:
        from aksara.ai.agent import AgentIntent
        from aksara.ai.planner import get_plan_schema
        
        agent_intent = AgentIntent(
            user_message=intent,
            mode=mode,
        )
        
        template = {
            "intent": agent_intent.model_dump(),
            "plan": {
                "intent": intent,
                "steps": [
                    {
                        "id": "step_1",
                        "type": "analyze_context",
                        "description": "Analyze current application state",
                        "payload": {}
                    }
                ]
            }
        }
        
        if include_schema:
            template["_plan_schema"] = get_plan_schema()
        
        click.echo(json.dumps(template, indent=2))
        sys.exit(0)
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


def main():
    """Main entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
