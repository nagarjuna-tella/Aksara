"""
CLI Main Entry Point

Command-line interface for Vidyut ORM.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import click


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


@click.group()
@click.version_option(version="0.1.0", prog_name="vidyut")
def cli():
    """⚡ Vidyut - Async Postgres ORM for FastAPI"""
    pass


@cli.command()
@click.option("--app", "-a", help="Path to application models module")
@click.option("--output", "-o", help="Output file for SQL (default: stdout)")
def makemigrations(app: Optional[str], output: Optional[str]):
    """Generate CREATE TABLE SQL from models."""
    from vidyut.registry import ModelRegistry
    
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
    for name in models:
        click.echo(f"  • {name}")
    
    # Generate SQL
    click.echo("\n" + "=" * 40)
    click.echo("Generated SQL:")
    click.echo("=" * 40 + "\n")
    
    sql_statements = []
    for name, model in models.items():
        sql = model.get_create_table_sql()
        sql_statements.append(sql)
        click.echo(sql)
        click.echo()
    
    # Write to file if specified
    if output:
        with open(output, "w") as f:
            f.write("\n\n".join(sql_statements))
        click.echo(f"✓ SQL written to {output}")


@cli.command()
@click.option("--app", "-a", help="Path to application models module")
@click.option("--database-url", "-d", envvar="DATABASE_URL", required=True,
              help="PostgreSQL connection URL (or set DATABASE_URL env var)")
@click.option("--dry-run", is_flag=True, help="Print SQL without executing")
def migrate(app: Optional[str], database_url: str, dry_run: bool):
    """Apply migrations to the database."""
    from vidyut.registry import ModelRegistry
    from vidyut.db import Database
    
    click.echo("⚡ Vidyut Migrate")
    click.echo("-" * 40)
    
    # Discover models
    click.echo("\nDiscovering models...")
    discover_models(app)
    
    models = ModelRegistry.all()
    
    if not models:
        click.echo("\n⚠️  No models found!")
        return
    
    click.echo(f"\nFound {len(models)} model(s)")
    
    async def run_migrations():
        db = Database(database_url)
        
        try:
            await db.connect()
            click.echo(f"\n✓ Connected to database")
            
            for name, model in models.items():
                sql = model.get_create_table_sql()
                
                if dry_run:
                    click.echo(f"\n[DRY RUN] Would create table '{model.__tablename__}':")
                    click.echo(sql)
                else:
                    click.echo(f"\n→ Creating table '{model.__tablename__}'...")
                    try:
                        await db.execute(sql)
                        click.echo(f"  ✓ Table '{model.__tablename__}' created/verified")
                    except Exception as e:
                        click.echo(f"  ✗ Error: {e}")
            
            if not dry_run:
                click.echo("\n" + "=" * 40)
                click.echo("✓ Migrations complete!")
        finally:
            await db.disconnect()
    
    asyncio.run(run_migrations())


@cli.command()
@click.option("--database-url", "-d", envvar="DATABASE_URL", required=True,
              help="PostgreSQL connection URL (or set DATABASE_URL env var)")
def shell(database_url: str):
    """Open an interactive async shell with Vidyut."""
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
    
    db = Database(database_url)
    
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
def models(app: Optional[str]):
    """List all registered models."""
    from vidyut.registry import ModelRegistry
    
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
        click.echo(f"   Table: {model.__tablename__}")
        click.echo("   Fields:")
        for field_name, field in model._fields.items():
            pk = " (PK)" if field.primary_key else ""
            nullable = " nullable" if field.nullable else ""
            unique = " unique" if field.unique else ""
            click.echo(f"     • {field_name}: {field.sql_type}{pk}{unique}{nullable}")
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
    click.echo("  \033[33m⚡\033[0m \033[1mVidyut\033[0m v0.1.0")
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
