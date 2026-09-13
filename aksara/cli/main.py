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
from typing import TYPE_CHECKING, List, Optional, Tuple

import click

from aksara.cli.ui import build_ui, get_ui, resolve_ui_config

if TYPE_CHECKING:
    from fastapi import FastAPI

# Load .env file from current directory
# This must happen before any settings are read
try:
    from dotenv import load_dotenv
    # Always load from current working directory
    load_dotenv(Path.cwd() / ".env")
except ImportError:
    pass  # python-dotenv not installed

# Version for CLI
from aksara._version import __version__ as CLI_VERSION


# Keep command-line database discovery aligned with ``aksara.conf.Settings``.
# The names are ordered by precedence; DATABASE_URL remains supported for
# compatibility and is the value emitted by ``startproject``.
_DATABASE_ENVVARS = ["AKSARA_DATABASE_URL", "DATABASE_URL"]


def discover_models(app_path: Optional[str] = None, *, silent: bool = False) -> None:
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

    # Walk settings.installed_apps too so model-oriented commands cover
    # the apps the operator actually configured (built-in aksara.contrib.*
    # included). Imports here are kept silent — they are framework
    # internals, not user-driven discoveries, and surfacing them in
    # `--format json` outputs would corrupt machine-readable streams.
    installed_app_paths: list[str] = []
    try:
        from aksara.conf import settings
        for app_label in getattr(settings, 'installed_apps', None) or []:
            candidate = f"{app_label}.models"
            if candidate not in model_paths:
                installed_app_paths.append(candidate)
    except Exception:
        # Settings may be unavailable in some bootstrap contexts.
        pass

    ui = get_ui()

    for path in model_paths:
        try:
            __import__(path)
            if not silent:
                ui.success(f"Discovered models from '{path}'")
        except ImportError:
            pass

    for path in installed_app_paths:
        try:
            __import__(path)
        except ImportError:
            pass


# =============================================================================
# Migration History System
# =============================================================================

MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS aksara_migrations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    checksum VARCHAR(64),
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""


def compute_checksum(sql: str) -> str:
    """Compute SHA-256 checksum of SQL content."""
    return hashlib.sha256(sql.strip().encode()).hexdigest()[:16]


def generate_migration_name(prefix: str = "migration") -> str:
    """Generate a timestamped migration name."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{prefix}"


def _run_async_command(coro):
    """Run a coroutine from sync CLI code and always close the object."""

    try:
        return asyncio.run(coro)
    finally:
        close = getattr(coro, "close", None)
        if callable(close):
            close()


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


# ---------------------------------------------------------------------------
# Legacy CLI-level helpers
#
# MIGRATION_TABLE_SQL, compute_checksum, ensure_migrations_table,
# get_applied_migrations, and record_migration below are compatibility
# shims kept so that external code importing them from aksara.cli.main
# continues to work.
#
# The canonical implementations live in aksara.migrations.executor and are
# what the `aksara migrate` command now uses internally.  Do not call these
# CLI-level helpers from new code.
# ---------------------------------------------------------------------------
async def record_migration(db, name: str, checksum: str | None = None) -> None:
    """Legacy shim — canonical implementation is aksara.migrations.executor.record_migration."""
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
    ui = get_ui()
    
    ui.aksara_banner(f"v{CLI_VERSION}", "Makemigrations --merge")
    
    # Get migrations directory
    mig_dir = Path(output) if output else Path(settings.migrations_dir)
    
    if not mig_dir.exists():
        ui.error(f"Migrations directory not found: {mig_dir}")
        return
    
    # Build migration graph
    migration_files = discover_migrations(mig_dir)
    if not migration_files:
        ui.warning(f"No migrations found in {mig_dir}")
        return
    
    graph = build_migration_graph(migrations_list=migration_files)
    conflicts = find_conflicts(graph)
    
    if not conflicts:
        ui.success("No conflicts detected. Nothing to merge.")
        return
    
    # If app_label specified, only merge that app
    if app_label:
        if app_label not in conflicts:
            ui.success(f"No conflicts in app '{app_label}'.")
            return
        conflicts = {app_label: conflicts[app_label]}
    
    # Create merge migrations for each conflicting app
    for target_app, heads in conflicts.items():
        ui.blank()
        ui.section(f"Merging conflicts for '{target_app}'")
        for head in heads:
            ui.bullet(head.name)
        
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
        
        ui.success(f"Created merge migration: {merge_path}")
        ui.text(f"  Dependencies: {len(heads)} heads merged")
    
    ui.blank()
    ui.separator(40)
    ui.success("Merge migration(s) created!")
    ui.blank()
    ui.command("aksara migrate")


# =============================================================================
# CLI Commands
# =============================================================================

@click.group()
@click.option("--quiet", is_flag=True, help="Suppress non-error output.")
@click.option("--plain", is_flag=True, help="Disable rich rendering and animations.")
@click.option("--no-color", is_flag=True, help="Disable colored terminal output.")
@click.option("--force-color", is_flag=True, help="Force colored output when supported.")
@click.version_option(version=CLI_VERSION, prog_name="aksara")
@click.pass_context
def cli(
    ctx: click.Context,
    quiet: bool,
    plain: bool,
    no_color: bool,
    force_color: bool,
):
    """⚡ Aksara - Async Framework"""
    ctx.ensure_object(dict)
    ctx.obj["ui"] = build_ui(
        resolve_ui_config(
            quiet=quiet,
            plain=plain,
            no_color=no_color,
            force_color=force_color,
        )
    )

    # Propagate color flags via env vars so commands that still emit raw ANSI
    # via click.echo get the same treatment as ui-based commands. Click's
    # echo automatically strips ANSI when NO_COLOR is set.
    _prev_no_color = os.environ.get("NO_COLOR")
    _prev_force_color = os.environ.get("FORCE_COLOR")

    if no_color or plain:
        os.environ["NO_COLOR"] = "1"
    if force_color:
        os.environ["FORCE_COLOR"] = "1"

    def _restore_color_env() -> None:
        if _prev_no_color is None:
            os.environ.pop("NO_COLOR", None)
        else:
            os.environ["NO_COLOR"] = _prev_no_color
        if _prev_force_color is None:
            os.environ.pop("FORCE_COLOR", None)
        else:
            os.environ["FORCE_COLOR"] = _prev_force_color

    ctx.call_on_close(_restore_color_env)

    # --quiet: silence non-error click.echo output across every command.
    # Errors (err=True) and warnings still pass through.
    if quiet:
        _original_echo = click.echo

        def _quiet_echo(message=None, file=None, nl=True, err=False, color=None):
            if err:
                _original_echo(message, file=file, nl=nl, err=err, color=color)

        click.echo = _quiet_echo  # type: ignore[assignment]
        ctx.call_on_close(lambda: setattr(click, "echo", _original_echo))


@cli.command()
@click.argument("project_name")
@click.option("--directory", "-d", default=".", help="Directory to create project in (default: current)")
@click.option("--template", "-t", default="basic", help="Template to use: basic, blog, crm, multitenant")
def startproject(project_name: str, directory: str, template: str):
    """Create a project shell or copy a bundled domain example.

    PROJECT_NAME must be a Python identifier.

    The default basic template creates main.py, settings.py, an app/ package,
    migrations/, .env and project metadata, with commented model/API examples.
    Blog, CRM and multitenant copy flat example modules instead; they do not
    create an app/ package or .env. Their generated pyproject.toml explicitly
    packages those flat modules. Their defaults differ.

    Domain examples require application-specific authentication and policy.
    The historical multitenant example has known isolation and migration
    limitations; use the Ticket Desk tenancy tutorial for a supported path.

    After generation, follow the template-specific dependency and database
    instructions. For basic, discover models with --app app.models; for a
    domain copy, use --app models --output migrations. Review generated
    migrations before applying them. Studio and MCP remain optional.

    Setup guide: https://nagarjuna-tella.github.io/Aksara/getting-started/patterns/

    Examples:
        aksara startproject myapp
        aksara startproject blog_demo --template blog
        aksara startproject crm_demo --template crm
    """
    from aksara.cli.scaffold import write_scaffold_files
    from aksara.cli.templates import get_template_info, copy_template_project, list_templates
    ui = get_ui()
    
    # Validate project name
    if not project_name.isidentifier():
        ui.error(f"Invalid project name: '{project_name}'")
        ui.dim("Project name must be a valid Python identifier")
        ui.dim("(letters, numbers, underscores, cannot start with number)")
        return
    
    # Validate template
    template_info = get_template_info(template)
    if not template_info:
        ui.error(f"Unknown template: '{template}'")
        ui.blank()
        click.echo(list_templates())
        return
    
    base_path = Path(directory).resolve()
    project_path = base_path / project_name
    
    # Check if project already exists
    if project_path.exists():
        ui.error(f"Directory already exists: {project_path}")
        return
    
    subtitle = (
        f"Creating new project from template: {template}"
        if template != "basic"
        else "Creating new project"
    )
    ui.aksara_banner(f"v{CLI_VERSION}", subtitle)

    if template != "basic":
        subtitle = f"Using template: {template}"

    try:
        # Generate and write scaffold files using template
        with ui.status("Scaffolding project files", animate=False):
            files = copy_template_project(template, project_name, base_path)
            write_scaffold_files(files)

        ui.success(f"Created project: {project_name}")
        if template != "basic":
            ui.success(
                f"Using template: {template} ({template_info['description']})"
            )

        ui.blank()
        ui.section("Project structure")
        ui.text(f"  {project_name}/")
        ui.text("  ├── main.py              # App entry point")
        ui.text("  ├── settings.py          # Global settings configuration")
        ui.text("  ├── pyproject.toml        # explicit application packaging")
        ui.text("  ├── .env                  # basic template only")
        ui.text("  ├── README.md")
        ui.text("  ├── app/                  # basic only; domain modules live at project root")
        ui.text("  │   ├── models.py        # Define your models here (Post example in comments)")
        ui.text("  │   ├── views.py         # Define your ViewSets here (PostViewSet example in comments)")
        ui.text("  │   ├── serializers.py   # Define your serializers here (PostSerializer example in comments)")
        ui.text("  │   ├── urls.py")
        ui.text("  │   └── admin.py         # Admin registrations (example in comments)")
        ui.text("  └── migrations/")
        ui.blank()
        ui.separator(40)
        ui.blank()
        ui.section("What's included")
        ui.bullet("Basic: commented model/API stubs. Domain templates: example application modules.")
        ui.bullet("Admin at /admin")
        ui.bullet("Studio at /studio/ui: optional; disabled in basic, inspect domain settings.")
        ui.bullet("Tool inspection catalog at /ai/tools/mcp")
        ui.bullet("Optional MCP protocol endpoint at /mcp/")
        ui.next_steps(
            [
                f"cd {project_name}",
                'pip install -e ".[dev]"',
                "Follow the setup guide for your template.",
                "Set DATABASE_URL for a dedicated local PostgreSQL database.",
                "Generate migrations with the template-specific command in the setup guide; review before applying.",
                "aksara migrate --migrations-dir migrations",
                "aksara run main:app --reload",
            ]
        )
        ui.blank()
        ui.text("  Setup: https://nagarjuna-tella.github.io/Aksara/getting-started/patterns/ | API: http://localhost:8000/docs")
        ui.blank()
        
    except Exception as e:
        ui.error(f"Error creating project: {e}")
        return


# =============================================================================
# Database Setup Command
# =============================================================================

def _mask_password(url: str) -> str:
    """Mask the password in a DATABASE_URL for display."""
    # postgresql://user:pass@host:port/db → postgresql://user:***@host:port/db
    import re as _re
    return _re.sub(r"(://[^:]+:)[^@]+(@)", r"\1***\2", url)


def _read_env_database_url(env_path: Path) -> Optional[str]:
    """Read DATABASE_URL from a .env file, if present."""
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.strip() == "DATABASE_URL":
            return value.strip()
    return None


def _parse_database_url_host_port(url: str):
    """Extract (host, port) from a postgresql:// URL. Returns (None, None) on failure."""
    try:
        from urllib.parse import urlparse as _urlparse
        parsed = _urlparse(url)
        return parsed.hostname or None, parsed.port or None
    except Exception:
        return None, None


def _write_env_database_url(env_path: Path, url: str) -> None:
    """Write or update DATABASE_URL in a .env file.
    
    - If .env does not exist, create it with DATABASE_URL.
    - If .env exists but has no DATABASE_URL, append it.
    - If .env exists and already has DATABASE_URL, replace the line.
    """
    if not env_path.exists():
        env_path.write_text(f"DATABASE_URL={url}\n")
        return

    lines = env_path.read_text().splitlines(keepends=True)
    found = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("#") and "=" in stripped:
            key, _, _ = stripped.partition("=")
            if key.strip() == "DATABASE_URL":
                new_lines.append(f"DATABASE_URL={url}\n")
                found = True
                continue
        new_lines.append(line)

    if not found:
        # Ensure trailing newline before appending
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"DATABASE_URL={url}\n")

    env_path.write_text("".join(new_lines))


@cli.command()
@click.option("--host", default="localhost", help="PostgreSQL host (default: localhost)")
@click.option("--port", default=5432, type=int, help="PostgreSQL port (default: 5432)")
def dbsetup(host: str, port: int):
    """Set up a PostgreSQL database for this project.

    Interactively configure database credentials, test the connection,
    create the database, and write DATABASE_URL to .env.

    Run this immediately after `aksara startproject`:

        aksara startproject myapp
        cd myapp
        aksara dbsetup
        aksara migrate

    Example:
        aksara dbsetup
        aksara dbsetup --host db.example.com --port 5433
    """
    import getpass as _getpass
    ui = get_ui()

    env_path = Path.cwd() / ".env"

    # --- Banner ---
    ui.aksara_banner(f"v{CLI_VERSION}", "Database Setup")

    # --- Check for existing DATABASE_URL ---
    existing_url = _read_env_database_url(env_path)
    if existing_url:
        ui.info("DATABASE_URL is already set in .env:")
        ui.text(f"  {_mask_password(existing_url)}")
        ui.blank()
        overwrite = click.confirm("  Overwrite it?", default=False)
        if not overwrite:
            ui.blank()
            ui.info("Keeping existing configuration.")
            ui.blank()
            return
        ui.blank()

    # --- Resolve host/port silently (use --host/--port flags as defaults,
    # falling back to values parsed from an existing URL when overwriting).
    # The interactive Host/Port prompts used to live here; they now run
    # AFTER credential collection so the documented input flow of
    # "database name → username → password" isn't shifted into integer
    # parsing failures when operators feed two values into stdin.
    db_host = host
    db_port = port
    if existing_url:
        parsed_host, parsed_port = _parse_database_url_host_port(existing_url)
        if parsed_host:
            db_host = parsed_host
        if parsed_port:
            db_port = parsed_port

    # --- Step 1: Check PostgreSQL reachability ---
    async def _check_pg():
        import asyncpg as _asyncpg
        try:
            conn = await _asyncpg.connect(
                host=db_host, port=db_port,
                user="postgres", password="postgres",
                database="postgres",
                timeout=5,
            )
            await conn.close()
            return True
        except _asyncpg.InvalidPasswordError:
            # Server is reachable but password wrong — that's fine,
            # it means PG is running. We'll get the real creds next.
            return True
        except (OSError, ConnectionRefusedError, _asyncpg.CannotConnectNowError):
            return False
        except Exception:
            return False

    try:
        with ui.status("Checking for PostgreSQL"):
            pg_reachable = _run_async_command(_check_pg())
    except Exception:
        pg_reachable = False

    if not pg_reachable:
        ui.error(f"not found on {db_host}:{db_port}")
        ui.blank()
        ui.text("  PostgreSQL is not running or not reachable.")
        ui.blank()
        ui.section("Start it with one of these")
        ui.blank()
        ui.text("  macOS (Homebrew):")
        ui.command("brew services start postgresql@15")
        ui.blank()
        ui.text("  Linux:")
        ui.command("sudo systemctl start postgresql")
        ui.blank()
        ui.text("  Docker:")
        ui.command("docker run -d --name postgres \\")
        ui.command("  -e POSTGRES_PASSWORD=postgres \\")
        ui.command("  -p 5432:5432 postgres:15")
        ui.blank()
        ui.text("  Then run aksara dbsetup again.")
        ui.blank()
        sys.exit(1)

    ui.success(f"found ({db_host}:{db_port})")

    # --- Step 2: Collect credentials ---
    # Default database name: current directory name
    default_dbname = Path.cwd().name.lower().replace("-", "_")
    if not default_dbname.isidentifier():
        default_dbname = "aksara_app"

    db_name = click.prompt(
        "  > Database name",
        default=default_dbname,
    )
    import re as _re
    if not _re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', db_name):
        ui.error("Invalid database name")
        ui.text(
            "  Database name must start with a letter or underscore "
            "and contain only letters, numbers, and underscores."
        )
        sys.exit(1)
    db_user = click.prompt(
        "  > Username",
        default="postgres",
    )
    db_password = _getpass.getpass(
        "  > Password: ",
    )

    # --- Step 3: Test connection ---
    async def _test_connection():
        import asyncpg as _asyncpg
        conn = await _asyncpg.connect(
            host=db_host, port=db_port,
            user=db_user, password=db_password,
            database="postgres",  # Connect to default db first
            timeout=5,
        )
        await conn.close()

    try:
        with ui.status("Testing connection"):
            _run_async_command(_test_connection())
    except Exception as e:
        ui.error("failed")
        ui.blank()
        err_msg = str(e)
        if "password authentication failed" in err_msg.lower():
            ui.text(
                f"  Could not connect: password authentication failed for user \"{db_user}\""
            )
        elif "does not exist" in err_msg.lower() and "role" in err_msg.lower():
            ui.text(f"  Could not connect: role \"{db_user}\" does not exist")
        else:
            ui.text(f"  Could not connect: {err_msg}")
        ui.blank()
        ui.text("  Check your username and password and try again.")
        ui.blank()
        sys.exit(1)

    ui.success("connected")

    # --- Step 4: Create database ---
    async def _create_database():
        import asyncpg as _asyncpg
        conn = await _asyncpg.connect(
            host=db_host, port=db_port,
            user=db_user, password=db_password,
            database="postgres",
            timeout=5,
        )
        try:
            # Check if database already exists
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", db_name
            )
            if exists:
                return "exists"
            # CREATE DATABASE cannot run inside a transaction block
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            return "created"
        finally:
            await conn.close()

    try:
        with ui.status(f"Creating database \"{db_name}\""):
            result = _run_async_command(_create_database())
    except Exception as e:
        ui.error("failed")
        ui.blank()
        ui.text(f"  Could not create database: {e}")
        ui.blank()
        sys.exit(1)

    if result == "exists":
        ui.warning("already exists, skipping")
    else:
        ui.success("created")

    # --- Step 5: Write .env ---
    # Build the DATABASE_URL
    # URL-encode password in case it contains special characters
    from urllib.parse import quote as _url_quote
    encoded_password = _url_quote(db_password, safe="")
    database_url = f"postgresql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"

    try:
        with ui.status("Writing DATABASE_URL to .env"):
            _write_env_database_url(env_path, database_url)
    except Exception as e:
        ui.error("failed")
        ui.blank()
        ui.text(f"  Could not write .env: {e}")
        ui.blank()
        sys.exit(1)

    ui.success("done")

    # --- Done ---
    ui.blank()
    ui.success("Ready. Run aksara migrate to continue.")
    ui.blank()


# =============================================================================
# Templates Commands (v0.5.7)
# =============================================================================

@cli.group()
def templates():
    """Project template management.
    
    Commands for listing and using project templates.
    """
    pass


@templates.command("list")
def templates_list():
    """
    List available project templates.
    
    Templates can be used with:
        aksara startproject myproj --template <name>
    
    Example:
        aksara templates list
    """
    from aksara.cli.templates import get_available_templates
    
    templates_dict = get_available_templates()
    
    click.echo()
    click.echo(f"  ⚡ \033[1mAksara\033[0m v{CLI_VERSION}")
    click.echo("  \033[90mAvailable project templates\033[0m")
    click.echo()
    click.echo("  \033[90m" + "─" * 50 + "\033[0m")
    click.echo()
    
    for name, info in templates_dict.items():
        default = " \033[33m(default)\033[0m" if name == "basic" else ""
        click.echo(f"  \033[36m{name:<12}\033[0m {info['description']}{default}")
    
    click.echo()
    click.echo("  \033[90m" + "─" * 50 + "\033[0m")
    click.echo()
    click.echo("  \033[1mUsage:\033[0m")
    click.echo("    aksara startproject myproj --template blog")
    click.echo("    aksara startproject mycrm -t crm")
    click.echo()


# =============================================================================
# Examples Commands
# =============================================================================


@cli.group("examples")
def examples_group():
    """Validate and inspect bundled golden-path examples."""
    pass


@examples_group.command("validate")
@click.option("--format", "-f", "output_format", type=click.Choice(["pretty", "json"]), default="pretty", help="Output format")
def examples_validate(output_format: str):
    """Validate bundled example projects for first-user completeness."""
    from aksara.examples_validation import validate_examples

    report = validate_examples()
    if output_format == "json":
        click.echo(report.to_json(indent=2))
        raise click.exceptions.Exit(report.exit_code)

    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara Examples Validation\033[0m")
    click.echo()

    for example in report.examples:
        click.echo(f"  \033[1m{example.name}\033[0m")
        for check in example.checks:
            symbol = {
                "ok": "\033[32m✓\033[0m",
                "warning": "\033[33m⚠\033[0m",
                "error": "\033[31m✗\033[0m",
                "skipped": "\033[90m-\033[0m",
            }.get(check.status, "-")
            click.echo(f"    {symbol} {check.message}")
            if check.hint:
                click.echo(f"      \033[90mNext: {check.hint}\033[0m")
        click.echo()

    status_label = {
        "ready": "READY",
        "partial": "PARTIAL",
        "blocked": "BLOCKED",
    }.get(report.status, report.status.upper())
    click.echo(f"  Result: {status_label}")
    click.echo(
        "  "
        f"{report.summary.get('ok', 0)} ok, "
        f"{report.summary.get('warnings', 0)} warnings, "
        f"{report.summary.get('errors', 0)} errors, "
        f"{report.summary.get('skipped', 0)} skipped"
    )
    click.echo()
    raise click.exceptions.Exit(report.exit_code)


# =============================================================================
# SDK Generation Commands (v0.5.45)
# =============================================================================


@cli.group("generate")
def generate_group():
    """Code and SDK generation commands."""
    pass


@generate_group.command("sdk")
@click.option("--language", type=click.Choice(["typescript"]), default="typescript", show_default=True)
@click.option("--output", "output_path", default="api.ts", show_default=True, help="File path for the generated SDK")
@click.option("--views-module", default=None, help="Optional views module to inspect instead of settings.apps")
@click.option("--stdout", "to_stdout", is_flag=True, help="Print the SDK instead of writing a file")
def generate_sdk(language: str, output_path: str, views_module: Optional[str], to_stdout: bool):
    """Generate a frontend SDK from discovered Aksara ViewSets."""
    from aksara.sdk.typescript import discover_viewset_sdk_specs, generate_typescript_sdk

    if language != "typescript":
        click.echo("❌ Only TypeScript SDK generation is currently supported.")
        raise SystemExit(1)

    specs = discover_viewset_sdk_specs(views_module=views_module)
    if not specs:
        click.echo("❌ No ViewSets discovered. Nothing to generate.")
        raise SystemExit(1)
    content = generate_typescript_sdk(specs)

    if to_stdout:
        click.echo(content, nl=False)
        return

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content)

    click.echo()
    click.echo(f"  \033[32m✓\033[0m Generated TypeScript SDK: \033[1m{output}\033[0m")
    click.echo()


@cli.command()
@click.argument("app_name")
@click.option("--directory", "-d", default=".", help="Directory to create app in (default: current)")
def startapp(app_name: str, directory: str):
    """Create a Python application module within an existing project.

    APP_NAME must be a Python identifier. Creates __init__.py, models.py,
    admin.py, views.py and serializers.py. It does not create urls.py or
    update settings, register routes, or apply migrations.

    In a basic generated project, add the module to INSTALLED_APPS in
    settings.py. Its existing configure(installed_apps=INSTALLED_APPS) call
    applies that list. Other layouts should configure the full importable
    module path through aksara.configure(installed_apps=[...]).

    Define models and ViewSets, register routes explicitly, then generate
    and review migrations before applying them. Keep loaded model class
    names distinct across application modules.

    Examples:
        aksara startapp inventory
        aksara startapp inventory --directory apps

    Layout guide: https://nagarjuna-tella.github.io/Aksara/getting-started/project-layout/
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
        click.echo("  ├── admin.py")
        click.echo("  ├── models.py")
        click.echo("  ├── views.py")
        click.echo("  └── serializers.py")
        click.echo()
        click.echo("  \033[90m" + "─" * 40 + "\033[0m")
        click.echo()
        click.echo("  \033[1mNext steps:\033[0m")
        click.echo()
        click.echo(f"  1. Add '{app_name}' to INSTALLED_APPS in the basic project's settings.py:")
        click.echo()
        click.echo("     INSTALLED_APPS = [")
        click.echo(f'         "aksara.contrib.auth", "aksara.contrib.admin", "app", "{app_name}",')
        click.echo("     ]  # used by configure(installed_apps=INSTALLED_APPS)")
        click.echo()
        click.echo(f"  2. Define your models in {app_name}/models.py")
        click.echo(f"  3. Create ViewSets in {app_name}/views.py and register their routes explicitly")
        click.echo("  4. Generate and review migrations, then apply:")
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
        discover_migrations,
    )
    ui = get_ui()
    
    # Handle --merge mode
    if merge:
        _handle_merge_migration(merge_app, output, settings)
        return
    
    ui.aksara_banner(f"v{CLI_VERSION}", "Makemigrations")
    
    # Discover models
    with ui.status("Discovering models"):
        discover_models(app)
    
    models = ModelRegistry.all()
    
    if not models:
        ui.warning("No models found!")
        ui.dim("Make sure your models are in a 'models.py' file")
        ui.dim("or specify the module with --app")
        return
    
    ui.blank()
    ui.info(f"Found {len(models)} model(s):")
    for model_name in models:
        ui.bullet(model_name)
    
    # Get migrations directory
    migrations_dir = Path(output) if output else Path(settings.migrations_dir)
    
    if sql:
        # Legacy SQL mode — no autodetection, always dumps all models
        from aksara.migrations.autodetector import sort_model_items_by_fk_dependencies

        sql_statements = []
        for model_name, model in sort_model_items_by_fk_dependencies(models):
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
        
        migrations_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate migration filename
        migration_name = generate_migration_name(name)
        migration_file = migrations_dir / f"{migration_name}.sql"
        
        # Add header to migration file
        header = f"""-- Migration: {migration_name}
-- Generated: {datetime.now().isoformat()}
-- Models: {', '.join(models.keys())}

"""

        with ui.status("Writing SQL migration", animate=False):
            with open(migration_file, "w") as f:
                f.write(header + full_sql)

        ui.success(f"SQL Migration created: {migration_file}")
        ui.text(f"  Checksum: {compute_checksum(full_sql)}")
    
    else:
        # Python migration mode with AUTODETECTION (v0.5.26)
        from aksara.migrations.autodetector import detect_changes, operations_to_code
        
        # Discover existing migrations
        existing_migrations = discover_migrations(migrations_dir) if migrations_dir.exists() else []
        
        ui.blank()
        ui.info(f"Existing migrations: {len(existing_migrations)}")
        
        # Run autodetector: compare existing migrations vs current models
        with ui.status("Diffing models against migration state"):
            diff, operations = detect_changes(existing_migrations, models)
        
        if not diff.has_changes:
            ui.blank()
            ui.success("No changes detected.")
            ui.dim("Your models match the current migration state.")
            return
        
        # Report what was detected
        ui.blank()
        ui.section("Detected changes")
        if diff.new_tables:
            for t in diff.new_tables:
                ui.text(f"  + New table: {t}")
        if diff.added_fields:
            for t, fields in diff.added_fields.items():
                for f in fields:
                    ui.text(f"  + Add field: {t}.{f}")
        if diff.removed_fields:
            for t, fields in diff.removed_fields.items():
                for f in fields:
                    ui.text(f"  - Remove field: {t}.{f}")
        if diff.removed_tables:
            for t in diff.removed_tables:
                ui.text(f"  - Drop table: {t}")
        if diff.altered_fields:
            for t, fields in diff.altered_fields.items():
                for f in fields:
                    ui.text(f"  ~ Alter field: {t}.{f}")
        
        # Generate operations code
        operations_code = operations_to_code(operations)
        
        # Determine dependencies — depend on the last migration if any exist
        deps_code = "[]"
        if existing_migrations:
            last_name = existing_migrations[-1][0]
            last_path = existing_migrations[-1][1]
            # Extract app label
            from aksara.migrations.executor import extract_app_label_from_name
            app_label = extract_app_label_from_name(last_name, last_path)
            deps_code = f'[("{app_label}", "{last_name}")]'
        
        # Build the operation description
        desc_parts = []
        if diff.new_tables:
            desc_parts.append(f"Create: {', '.join(diff.new_tables)}")
        if diff.added_fields:
            for t, fields in diff.added_fields.items():
                desc_parts.append(f"Add to {t}: {', '.join(fields)}")
        if diff.removed_fields:
            for t, fields in diff.removed_fields.items():
                desc_parts.append(f"Remove from {t}: {', '.join(fields)}")
        if diff.removed_tables:
            desc_parts.append(f"Drop: {', '.join(diff.removed_tables)}")
        description = "; ".join(desc_parts) if desc_parts else name
        
        timestamp = datetime.now().isoformat()
        
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
    
    dependencies = {deps_code}
    
    operations = [
{operations_code},
    ]
'''
        
        if stdout:
            click.echo("\n" + "=" * 40)
            click.echo("Generated Python Migration:")
            click.echo("=" * 40 + "\n")
            click.echo(content)
            return
        
        # Write to migrations directory
        migrations_dir.mkdir(parents=True, exist_ok=True)
        
        filename = generate_migration_filename(name)
        migration_file = migrations_dir / filename

        with ui.status("Writing Python migration", animate=False):
            with open(migration_file, "w") as f:
                f.write(content)

        ui.blank()
        ui.success(f"Python Migration created: {migration_file}")
        ui.text(f"  Operations: {len(operations)}")
        ui.blank()
        ui.command("aksara migrate")


def _display_pending_skipped(ui, pending_skipped: list[str]) -> None:
    """Display the migrations that were not attempted because of a prior failure."""
    if pending_skipped:
        ui.blank()
        ui.warning(
            f"Skipped {len(pending_skipped)} pending migration(s) after failure:"
        )
        for name in pending_skipped:
            ui.text(f"  - {name}")


@cli.command()
@click.option("--app", "-a", help="Path to application models module")
@click.option("--database-url", "-d", envvar=_DATABASE_ENVVARS,
              help="PostgreSQL connection URL (or set AKSARA_DATABASE_URL / DATABASE_URL)")
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
        get_applied_migrations as get_applied_migs,
        record_migration,
        load_migration_module,
        build_migration_graph,
        check_migration_conflicts,
    )
    from aksara.migrations.graph import format_conflict_message
    ui = get_ui()
    
    ui.aksara_banner(f"v{CLI_VERSION}", "Migrate")
    
    # Get database URL from args or settings
    db_url = database_url or settings.database_url
    if not db_url:
        ui.error("No database URL provided!", err=True)
        ui.dim("Set DATABASE_URL or use --database-url")
        sys.exit(1)
    
    # Get migrations directory
    mig_dir = Path(migrations_dir) if migrations_dir else Path(settings.migrations_dir)
    
    # Check for migration files
    migration_files = discover_migrations(mig_dir)
    
    if migration_files:
        ui.info(f"Found {len(migration_files)} migration file(s) in {mig_dir}")
        
        # v0.3.16: Build migration graph and check for conflicts
        try:
            with ui.status("Building migration graph", animate=False):
                graph = build_migration_graph(migrations_list=migration_files)
        except ValueError as e:
            ui.error(f"Could not build migration graph: {e}")
            sys.exit(1)
        
    else:
        # Fall back to model-based migration (v0.1 behavior)
        ui.warning(f"No migration files in {mig_dir}")
        ui.info("Falling back to model-based migration...")
        
        # Discover models
        with ui.status("Discovering models"):
            discover_models(app)
        
        models = ModelRegistry.all()
        
        if not models:
            ui.warning("No models found!")
            return
        
        ui.info(f"Found {len(models)} model(s)")
        graph = None  # No graph for model-based migrations
    
    async def run_migrations():
        db = Database(db_url)
        
        try:
            with ui.status("Connecting to database"):
                await db.connect()
            ui.success("Connected to database")
            
            if migration_files:
                # File-based migrations (v0.3.3 path)
                applied = await get_applied_migs(db)
                ui.info(f"{len(applied)} migration(s) already applied")
                
                # v0.3.16: Check for conflicts before proceeding
                if graph is not None:
                    conflicts = check_migration_conflicts(graph, applied)
                    if conflicts:
                        ui.blank()
                        ui.error("Migration Conflicts Detected!")
                        ui.text(format_conflict_message(conflicts))
                        ui.blank()
                        ui.text("Migration aborted. Resolve conflicts first.")
                        return
                
                if dry_run:
                    # Dry-run: preview what would be applied, nothing is executed or recorded.
                    pending = get_pending_migrations(migration_files, applied)
                    if not pending:
                        ui.blank()
                        ui.success("All migrations already applied!")
                        return
                    ui.blank()
                    ui.info(f"{len(pending)} pending migration(s) [DRY RUN]:")
                    for name, path in pending:
                        ui.blank()
                        if path.suffix == ".py":
                            ui.info(f"[DRY RUN] Would apply: {name}")
                            try:
                                migration_class = load_migration_module(path)
                                migration = migration_class()
                                for op in migration.operations:
                                    ui.text(f"    > {op.describe()}")
                            except Exception as e:
                                ui.warning(f"Error loading: {e}")
                        elif path.suffix == ".sql":
                            ui.info(f"[DRY RUN] Would apply SQL: {name}")
                            sql = path.read_text()
                            lines = sql.strip().split('\n')[:5]
                            for line in lines:
                                ui.text(f"    {line}")
                            if len(sql.strip().split('\n')) > 5:
                                ui.text(
                                    f"    ... ({len(sql.strip().split(chr(10)))} lines)"
                                )
                    return
                else:
                    # Canonical executor path: advisory lock per run, transaction per
                    # migration, SQL statement splitting, checksum recording and
                    # verification.  This is the same path used by apply_migrations().
                    try:
                        results = await apply_migrations(
                            db, mig_dir, fake=fake, verbose=False, include_internal=True,
                        )
                    except (RuntimeError, ValueError) as e:
                        ui.blank()
                        ui.error(f"Migration failed: {e}")
                        sys.exit(1)
                    except Exception as e:
                        ui.blank()
                        ui.error(f"Migration failed unexpectedly: {e}")
                        sys.exit(1)

                    if not results["applied"] and not results["errors"]:
                        ui.blank()
                        ui.success("All migrations already applied!")
                        return

                    if results["applied"]:
                        ui.blank()
                        action = "marked as applied" if fake else "applied successfully"
                        for name in results["applied"]:
                            ui.success(f"  ✓ {name} — {action}")

                    if results["errors"]:
                        ui.blank()
                        for name, err in results["errors"]:
                            ui.error(f"  ✗ {name}: {err}")
                        _display_pending_skipped(ui, results["pending_skipped"])
                        sys.exit(1)
            else:
                # Model-based migrations (v0.1 behavior - fallback)
                models = ModelRegistry.all()
                applied = await get_applied_migs(db)

                with ui.progress(len(models), "Applying model migrations") as progress:
                    for model_name, model in models.items():
                        sql = model.get_create_table_sql()
                        migration_name = f"model_{model_name.lower()}"

                        if migration_name in applied:
                            ui.blank()
                            ui.info(f"Table '{model.__tablename__}' already migrated")
                            progress.advance(description=f"Skipped {model.__tablename__}")
                            continue

                        if dry_run:
                            ui.blank()
                            ui.info(
                                f"[DRY RUN] Would create table '{model.__tablename__}':"
                            )
                            ui.text(sql)
                            progress.advance(description=f"Scanned {model.__tablename__}")
                        else:
                            ui.blank()
                            ui.info(f"Creating table '{model.__tablename__}'")
                            try:
                                await db.execute(sql)
                                await record_migration(
                                    db,
                                    migration_name,
                                    compute_checksum(sql),
                                )
                                ui.success(
                                    f"Table '{model.__tablename__}' created/verified"
                                )
                                progress.advance(
                                    description=f"Applied {model.__tablename__}"
                                )
                            except Exception as e:
                                ui.error(f"Error: {e}")
            
            if not dry_run:
                ui.blank()
                ui.separator(40)
                ui.success("Migrations complete!")
        finally:
            await db.disconnect()
    
    _run_async_command(run_migrations())


@cli.command()
@click.option("--database-url", "-d", envvar=_DATABASE_ENVVARS,
              help="PostgreSQL connection URL (or set AKSARA_DATABASE_URL / DATABASE_URL)")
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
        click.echo("\n❌ No database URL provided!", err=True)
        click.echo("   Try: set DATABASE_URL or use --database-url", err=True)
        sys.exit(1)
    
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
@click.option("--database-url", "-d", envvar=_DATABASE_ENVVARS,
              help="PostgreSQL connection URL (or set AKSARA_DATABASE_URL / DATABASE_URL)")
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
@click.option("--database-url", "-d", envvar=_DATABASE_ENVVARS,
              help="PostgreSQL connection URL (or set AKSARA_DATABASE_URL / DATABASE_URL)")
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
@click.option("--database-url", "-d", envvar=_DATABASE_ENVVARS,
              help="PostgreSQL connection URL (or set AKSARA_DATABASE_URL / DATABASE_URL)")
def info(database_url: Optional[str]):
    """
    Show Aksara environment information.
    
    Displays version, environment, database connection status, 
    configured apps, features, and pending migrations.
    Useful for debugging configuration issues.
    """
    from aksara import __version__
    from aksara.conf import settings
    from aksara.registry import ModelRegistry
    
    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara Info\033[0m")
    click.echo("  " + "-" * 40)
    
    # Framework section
    click.echo(f"\n  \033[1mFramework\033[0m")
    click.echo(f"    Version:      Aksara {__version__}")
    click.echo(f"    CLI Version:  {CLI_VERSION}")
    
    # Environment section
    env = "dev" if settings.debug else "prod"
    click.echo(f"\n  \033[1mEnvironment\033[0m")
    click.echo(f"    Env:          {env}")
    click.echo(f"    Debug:        {settings.debug}")
    click.echo(f"    Migrations:   {settings.migrations_dir}")
    
    # Database section
    db_url = database_url or settings.database_url
    click.echo(f"\n  \033[1mDatabase\033[0m")
    if db_url:
        # Redact password from URL
        redacted = _redact_db_url(db_url)
        # Detect backend
        backend = "PostgreSQL" if "postgresql" in db_url.lower() else "Unknown"
        click.echo(f"    Backend:      {backend}")
        click.echo(f"    URL:          {redacted}")
    else:
        click.echo(f"    Backend:      \033[90mNot configured\033[0m")
    
    # Apps section
    # Show installed_apps (the Django-style list that includes the
    # built-in aksara.contrib apps) instead of `settings.apps`, which is
    # only the multi-app shortlist and silently hides built-ins.
    click.echo(f"\n  \033[1mInstalled Apps\033[0m")
    apps_to_show = getattr(settings, 'installed_apps', None) or settings.apps
    for app in apps_to_show:
        click.echo(f"    • {app}")

    # Features section (v0.5.6)
    admin_enabled = getattr(settings, 'enable_admin', False) or settings.debug
    # Mirror Aksara._should_enable_studio(): Studio is gated in
    # production unless studio_expose_in_production is True, so
    # reporting `enable_studio=True` alone misleads operators.
    studio_enabled = bool(getattr(settings, 'enable_studio', True))
    if studio_enabled and not settings.debug:
        if not getattr(settings, 'studio_expose_in_production', False):
            studio_enabled = False
    ai_mode_enabled = getattr(settings, 'AI_MODE_ENABLED', True)
    
    click.echo(f"\n  \033[1mFeatures\033[0m")
    admin_status = "\033[32m✓ enabled\033[0m" if admin_enabled else "\033[90m✗ disabled\033[0m"
    studio_status = "\033[32m✓ enabled\033[0m" if studio_enabled else "\033[90m✗ disabled\033[0m"
    ai_status = "\033[32m✓ enabled\033[0m" if ai_mode_enabled else "\033[90m✗ disabled\033[0m"
    click.echo(f"    Admin:        {admin_status}")
    click.echo(f"    Studio:       {studio_status}")
    click.echo(f"    AI Mode:      {ai_status}")
    
    # Discover models
    for app in settings.apps:
        try:
            import importlib
            importlib.import_module(f"{app}.models")
        except ImportError:
            pass
    
    all_models = ModelRegistry.all()
    click.echo(f"\n  \033[1mRegistered Models\033[0m ({len(all_models)})")
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
                
                click.echo(f"\n  \033[1mMigrations\033[0m")
                click.echo(f"    Applied:      {len(applied)}")
                click.echo(f"    Pending:      {len(pending)}")
                
                if pending:
                    click.echo(f"\n  \033[1mPending Migrations\033[0m")
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
        click.echo(f"   Table: {model.__tablename__}")
        
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
            nullable = " nullable" if getattr(field, "nullable", False) else ""
            unique = " unique" if field.unique else ""
            
            field_info = f"     • {field_name}: {field.sql_type}{pk}{unique}{nullable}"
            
            if ai and field.ai_description:
                field_info += f"\n       AI: {field.ai_description}"
                if field.ai_sensitive:
                    field_info += " [SENSITIVE]"
            
            click.echo(field_info)
        click.echo()


# =============================================================================
# Static File Collection
# =============================================================================

def _ensure_static_files() -> None:
    """
    Ensure static files exist before starting the server.
    
    If the project has a main.py (Aksara project) but is missing
    static/welcome.html, auto-generate it. This handles:
    - Projects scaffolded before v0.5.24 (inline HTML in main.py)
    - Projects where static/ was accidentally deleted
    """
    cwd = Path.cwd()
    main_py = cwd / "main.py"
    static_dir = cwd / "static"
    welcome_html = static_dir / "welcome.html"
    
    # Only act if this looks like an Aksara project (has main.py)
    if not main_py.exists():
        return
    
    if welcome_html.exists():
        return
    
    # Derive project name from directory name
    project_name = cwd.name
    
    try:
        from aksara.cli.scaffold import get_welcome_html_template
        static_dir.mkdir(parents=True, exist_ok=True)
        welcome_html.write_text(get_welcome_html_template(project_name))
        click.echo(f"  \033[32m✓\033[0m Created static/welcome.html")
    except Exception as e:
        click.echo(f"  \033[33m⚠\033[0m Could not create static/welcome.html: {e}", err=True)


@cli.command()
def collectstatic():
    """
    Collect and generate static files for the Aksara project.
    
    Creates missing static files (e.g., welcome.html) in the static/ directory.
    This runs automatically before `aksara dev` and `aksara run`, but can also
    be invoked manually.
    
    Example:
        aksara collectstatic
    """
    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m — Collect Static Files")
    click.echo()
    _ensure_static_files()
    click.echo("  \033[32m✓\033[0m Done.")
    click.echo()


def _is_valid_asgi_app_path(app_path: str) -> bool:
    """Return True when an ASGI import string looks well-formed."""

    return ":" in app_path and not app_path.startswith(":") and not app_path.endswith(":")


def _print_invalid_app_path(command_name: str, app_path: str) -> None:
    """Print a user-friendly error for invalid ASGI app paths."""

    ui = get_ui()
    ui.error(f"Invalid app path '{app_path}'. Expected '<module>:<attribute>'.")
    ui.blank()
    ui.section("Try one of these:")
    ui.command("aksara dev")
    if command_name == "run":
        ui.command("aksara run main:app --reload")
        ui.command("aksara run myproject.main:app --host 0.0.0.0 --port 8080")
    else:
        ui.command("aksara dev main:app")
        ui.command("aksara dev myproject.main:app --log-level debug")


def _run_dev_server(
    app_path: str,
    host: str,
    port: int,
    reload: bool,
    no_reload: bool,
    log_level: str,
) -> None:
    """Run the development server with Aksara's DX defaults."""
    ui = get_ui()

    try:
        import uvicorn
    except ImportError:
        click.echo("❌ uvicorn not installed in the current Python environment\n", err=True)
        click.echo(f"   Python: {sys.executable}", err=True)

        # Check if we're in a venv
        in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        if in_venv:
            click.echo(f"   Virtual environment detected, but 'aksara' command may be from global install", err=True)
            click.echo(f"   Try: python -m aksara dev  (uses venv's Python)", err=True)
            click.echo(f"   Or:  pip install -e . && hash -r  (reinstall aksara in venv)", err=True)
        else:
            click.echo(f"   Try: python -m pip install uvicorn", err=True)
            click.echo(f"   Or:  python -m aksara dev", err=True)
        sys.exit(1)

    # Auto-collect static files
    _ensure_static_files()

    # Ensure current directory is in Python path for module imports
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    # Determine actual reload state
    actual_reload = reload and not no_reload

    # Build URLs
    base_url = f"http://{host}:{port}"

    # Print enhanced banner (v0.5.6)
    _print_dev_banner(base_url, actual_reload, log_level)

    previous_runtime_brand = os.environ.get("AKSARA_SUPPRESS_RUNTIME_BRAND")
    os.environ["AKSARA_SUPPRESS_RUNTIME_BRAND"] = "1"

    try:
        # Configure and run uvicorn
        uvicorn.run(
            app_path,
            host=host,
            port=port,
            reload=actual_reload,
            workers=1,  # Always 1 in dev mode
            log_level=log_level.lower(),
            access_log=True,
            app_dir=cwd,
        )
    except KeyboardInterrupt:
        click.echo()
        click.echo("  \033[33mShutting down Aksara dev server… Bye 👋\033[0m")
        click.echo()
    finally:
        if previous_runtime_brand is None:
            os.environ.pop("AKSARA_SUPPRESS_RUNTIME_BRAND", None)
        else:
            os.environ["AKSARA_SUPPRESS_RUNTIME_BRAND"] = previous_runtime_brand


@cli.command()
@click.argument("app_path")
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind to")
@click.option("--port", "-p", default=8000, type=int, help="Port to bind to")
@click.option("--reload", "-r", is_flag=True, help="Enable auto-reload")
@click.option("--workers", "-w", default=1, type=int, help="Number of workers")
def run(app_path: str, host: str, port: int, reload: bool, workers: int):
    """
    Run an Aksara application with uvicorn.
    
    APP_PATH: Import path to the app (e.g., 'main:app' or 'myproject.main:app')
    
    Example:
        aksara run main:app --reload
        aksara run myproject.main:app --host 0.0.0.0 --port 8080
    """
    normalized_app_path = app_path.strip().lower()
    if normalized_app_path in {"dev", "development"}:
        if workers != 1:
            ui = get_ui()
            ui.warning("Ignoring --workers in dev mode; Aksara dev always uses a single worker.")
        _run_dev_server(
            app_path="main:app",
            host=host,
            port=port,
            reload=True,
            no_reload=False,
            log_level="info",
        )
        return

    if not _is_valid_asgi_app_path(app_path):
        _print_invalid_app_path("run", app_path)
        raise click.exceptions.Exit(2)

    try:
        import uvicorn
    except ImportError:
        click.echo("❌ uvicorn not installed. Run: pip install uvicorn")
        return
    
    # Auto-collect static files
    _ensure_static_files()
    
    # Ensure current directory is in Python path for module imports
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    
    # Print Aksara banner
    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m v{CLI_VERSION}")
    click.echo("  \033[90mAsync PostgreSQL backend — REST APIs and optional MCP\033[0m")
    click.echo()
    click.echo(f"  \033[36m→\033[0m Running: {app_path}")
    click.echo(f"  \033[36m→\033[0m Server:  http://{host}:{port}")
    if reload:
        click.echo(f"  \033[36m→\033[0m Reload:  \033[32menabled\033[0m")
    click.echo()
    click.echo("  \033[90m" + "─" * 40 + "\033[0m")
    click.echo()

    previous_runtime_brand = os.environ.get("AKSARA_SUPPRESS_RUNTIME_BRAND")
    os.environ["AKSARA_SUPPRESS_RUNTIME_BRAND"] = "1"
    
    try:
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
    finally:
        if previous_runtime_brand is None:
            os.environ.pop("AKSARA_SUPPRESS_RUNTIME_BRAND", None)
        else:
            os.environ["AKSARA_SUPPRESS_RUNTIME_BRAND"] = previous_runtime_brand


# =============================================================================
# v0.5.2: Enhanced Dev Command
# =============================================================================

def _check_studio_enabled() -> bool:
    """Check if Studio endpoints will be enabled."""
    try:
        from aksara.conf import settings
        if not getattr(settings, 'enable_studio', True):
            return False
        if not settings.debug and not getattr(settings, 'studio_expose_in_production', False):
            return False
        return True
    except Exception:
        return True  # Default to enabled in debug


def _check_admin_enabled() -> bool:
    """Check if Admin panel will be enabled."""
    try:
        from aksara.conf import settings
        if getattr(settings, 'enable_admin', False):
            return True
        # Also enabled in debug mode by default
        if settings.debug:
            return True
        return False
    except Exception:
        return True  # Default to enabled in debug


def _get_debug_mode() -> bool:
    """Get debug mode from settings."""
    try:
        from aksara.conf import settings
        return settings.debug
    except Exception:
        return True  # Assume dev mode


def _print_dev_banner(base_url: str, actual_reload: bool, log_level: str) -> None:
    """
    Print enhanced dev server banner (v0.5.6).
    
    Shows:
    - Aksara version
    - Environment and debug status
    - All relevant URLs (App, Admin, Studio, API, Docs)
    """
    from aksara import __version__
    
    admin_enabled = _check_admin_enabled()
    studio_enabled = _check_studio_enabled()
    debug = _get_debug_mode()
    env = "dev" if debug else "prod"

    ui = get_ui()
    ui.dev_server_banner(
        __version__,
        env=env,
        debug=debug,
        base_url=base_url,
        admin_enabled=admin_enabled,
        studio_enabled=studio_enabled,
        actual_reload=actual_reload,
        log_level=log_level,
    )


@cli.command()
@click.argument("app_path", default="main:app")
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind to")
@click.option("--port", "-p", default=8000, type=int, help="Port to bind to")
@click.option("--reload", "-r", is_flag=True, default=True, help="Enable auto-reload (default: True)")
@click.option("--no-reload", is_flag=True, help="Disable auto-reload")
@click.option("--log-level", "-l", default="info", 
              type=click.Choice(["debug", "info", "warning", "error"], case_sensitive=False),
              help="Uvicorn log level")
def dev(app_path: str, host: str, port: int, reload: bool, no_reload: bool, log_level: str):
    """
    Run Aksara in development mode with enhanced DX.
    
    v0.5.6: Improved developer experience with richer banner showing
    all relevant URLs, environment, and debug status.
    
    APP_PATH: Import path to the app (default: 'main:app')
    
    Examples:
        aksara dev                  # Uses main:app by default
        aksara dev main:app
        aksara dev myproject.main:app --log-level debug
        aksara dev main:app --no-reload --port 3000
    """
    if not _is_valid_asgi_app_path(app_path):
        _print_invalid_app_path("dev", app_path)
        raise click.exceptions.Exit(2)

    _run_dev_server(
        app_path=app_path,
        host=host,
        port=port,
        reload=reload,
        no_reload=no_reload,
        log_level=log_level,
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
        click.echo(f"     pip install aksara-framework[dev]")
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
    - AI provider and model configuration (v0.5.11)
    - Per-view AI route hints (v0.5.13)
    
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


# =============================================================================
# v0.5.29: AI Flows CLI Subgroup
# =============================================================================


@ai.group("flows")
def ai_flows_group():
    """AI flow prompt-pack generation (v0.5.29).

    Generate deterministic prompt packs for in-context AI actions.
    No external API calls are made — output is a prompt pack you can
    send to any LLM client.

    Examples:
        aksara ai flows model User --action explain_model
        aksara ai flows route GET:/api/users --action review_endpoint
        aksara ai flows query --sql "SELECT * FROM users" --action explain_plan
        aksara ai flows migration --app blog --action explain_migration
        aksara ai flows actions  # list all available actions
    """
    pass


@ai_flows_group.command("actions")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", help="Output format")
def ai_flows_list_actions(fmt):
    """List all available AI flow actions."""
    from aksara.studio.ai_flows import list_flow_actions

    actions = list_flow_actions()
    if fmt == "json":
        import json as _json
        click.echo(_json.dumps(actions, indent=2))
        return

    click.echo(f"\n  AI Flow Actions ({len(actions)} available)\n")
    for a in actions:
        risk_color = {"low": "green", "medium": "yellow", "high": "red"}.get(a["risk"], "white")
        click.echo(f"  {click.style(a['action_key'], bold=True):30s}  [{click.style(a['risk'], fg=risk_color)}]  {a['title']}")
        click.echo(f"  {'':30s}  {a['description']}")
        click.echo()


@ai_flows_group.command("model")
@click.argument("model_name")
@click.option("--action", "action_key", required=True, help="Action key (e.g. explain_model)")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", help="Output format")
def ai_flows_model(model_name, action_key, fmt):
    """Generate an AI flow prompt pack for a model."""
    from aksara.studio.ai_flows import build_model_flow

    discover_models()
    resp = build_model_flow(model_name=model_name, action_key=action_key)
    _print_flow_response(resp, fmt)


@ai_flows_group.command("route")
@click.argument("route_spec", required=True)
@click.option("--action", "action_key", required=True, help="Action key (e.g. review_endpoint)")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", help="Output format")
def ai_flows_route(route_spec, action_key, fmt):
    """Generate an AI flow prompt pack for a route. ROUTE_SPEC = METHOD:/path"""
    from aksara.studio.ai_flows import build_route_flow

    if ":" in route_spec:
        method, path = route_spec.split(":", 1)
    else:
        method, path = "GET", route_spec
    resp = build_route_flow(path=path, method=method, action_key=action_key)
    _print_flow_response(resp, fmt)


@ai_flows_group.command("query")
@click.option("--sql", required=True, help="SQL query text")
@click.option("--action", "action_key", required=True, help="Action key (e.g. explain_plan)")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", help="Output format")
def ai_flows_query(sql, action_key, fmt):
    """Generate an AI flow prompt pack for a SQL query."""
    from aksara.studio.ai_flows import build_query_flow

    resp = build_query_flow(sql=sql, action_key=action_key)
    _print_flow_response(resp, fmt)


@ai_flows_group.command("migration")
@click.option("--app", default=None, help="App label")
@click.option("--name", default=None, help="Migration name")
@click.option("--action", "action_key", required=True, help="Action key (e.g. explain_migration)")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", help="Output format")
def ai_flows_migration(app, name, action_key, fmt):
    """Generate an AI flow prompt pack for a migration."""
    from aksara.studio.ai_flows import build_migration_flow

    resp = build_migration_flow(action_key=action_key, app=app, name=name)
    _print_flow_response(resp, fmt)


@ai_flows_group.command("diagnostic")
@click.option("--issue-id", default=None, help="Diagnostic issue ID")
@click.option("--action", "action_key", required=True, help="Action key (e.g. diagnostic_prioritize)")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", help="Output format")
def ai_flows_diagnostic(issue_id, action_key, fmt):
    """Generate an AI flow prompt pack for a diagnostic issue."""
    from aksara.studio.ai_flows import build_diagnostic_flow

    resp = build_diagnostic_flow(action_key=action_key, issue_id=issue_id)
    _print_flow_response(resp, fmt)


def _print_flow_response(resp, fmt: str):
    """Print an AI flow response in the requested format."""
    if fmt == "json":
        import json as _json
        click.echo(_json.dumps(resp.model_dump(), indent=2, default=str))
        return

    if not resp.ok:
        click.echo(click.style(f"  ✗ Error: {resp.error}", fg="red"))
        return

    click.echo(f"\n  ─── {resp.action_key} ({'risk: ' + resp.risk}) ───\n")
    click.echo(f"  Provider: {resp.provider}  |  Model: {resp.model}")
    if resp.what_it_does:
        click.echo(f"  ✓ {resp.what_it_does}")
    if resp.what_it_cannot_do:
        click.echo(f"  ✗ {resp.what_it_cannot_do}")
    click.echo()
    click.echo("  ── System Prompt ──")
    click.echo(f"  {resp.system_prompt}")
    click.echo()
    click.echo("  ── User Prompt ──")
    click.echo(f"  {resp.user_prompt}")
    if resp.suggested_next:
        click.echo(f"\n  Suggested next: {', '.join(resp.suggested_next)}")
    click.echo()


# ── v0.5.30: AI execution group ──────────────────────────────────────────────


@ai.group("run")
def ai_run_group():
    """Execute AI flows through a configured connector (v0.5.30).

    Unlike 'aksara ai flows' which produces prompt packs only,
    'aksara ai run' actually sends the prompt pack to an AI provider
    (OpenAI, Anthropic, Ollama, or a custom HTTP endpoint).

    Requires at least one connector configured via AI Hub or env vars.

    Examples:
        aksara ai run model User --action explain_model
        aksara ai run route GET:/api/users --action review_endpoint
        aksara ai run query --sql "SELECT 1" --action explain_plan
        aksara ai run migration --app blog --action explain_migration
        aksara ai run diagnostic --issue-id DB_NO_URL --action diagnostic_prioritize
    """
    pass


def _run_async(coro):
    """Run an async coroutine from sync Click context."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _print_execution_result(result: dict, fmt: str):
    """Print an AI execution result."""
    ui = get_ui()

    if fmt == "json":
        ui.print_json(result)
        return

    if not result.get("ok"):
        ui.error(f"Execution failed: {result.get('error', 'Unknown error')}")
        return

    execution = result.get("execution", {})
    pack = result.get("prompt_pack", {})

    ui.blank()
    ui.section(f"{pack.get('action_key', '?')} (executed)")
    ui.text(
        f"  Provider: {execution.get('provider', '?')}  |  Model: {execution.get('model', '?')}"
    )
    elapsed = execution.get("elapsed_ms", 0)
    tokens = execution.get("tokens", {})
    ui.text(f"  Elapsed: {elapsed:.0f}ms  |  Tokens: {tokens.get('total', '?')}")
    ui.blank()
    ui.section("AI Response")
    ui.text(f"  {execution.get('response', '(no response)')}")
    ui.blank()


@ai_run_group.command("model")
@click.argument("model_name")
@click.option("--action", "action_key", required=True, help="Action key (e.g. explain_model)")
@click.option("--provider", "provider_override", default=None, help="Override AI provider")
@click.option("--model", "model_override", default=None, help="Override AI model")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", help="Output format")
def ai_run_model(model_name, action_key, provider_override, model_override, fmt):
    """Execute an AI flow for a model."""
    from aksara.studio.ai_flows import execute_model_flow
    ui = get_ui()

    if fmt == "json":
        discover_models(silent=True)
    else:
        with ui.status("Discovering models"):
            discover_models()

    if fmt == "json":
        result = _run_async(execute_model_flow(
            model_name=model_name,
            action_key=action_key,
            provider_override=provider_override,
            model_override=model_override,
        ))
    else:
        with ui.status(f"Executing AI action '{action_key}'"):
            result = _run_async(execute_model_flow(
                model_name=model_name,
                action_key=action_key,
                provider_override=provider_override,
                model_override=model_override,
            ))
    _print_execution_result(result, fmt)


@ai_run_group.command("route")
@click.argument("route_spec", required=True)
@click.option("--action", "action_key", required=True, help="Action key (e.g. review_endpoint)")
@click.option("--provider", "provider_override", default=None, help="Override AI provider")
@click.option("--model", "model_override", default=None, help="Override AI model")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", help="Output format")
def ai_run_route(route_spec, action_key, provider_override, model_override, fmt):
    """Execute an AI flow for a route. ROUTE_SPEC = METHOD:/path"""
    from aksara.studio.ai_flows import execute_route_flow
    ui = get_ui()

    if ":" in route_spec:
        method, path = route_spec.split(":", 1)
    else:
        method, path = "GET", route_spec

    if fmt == "json":
        result = _run_async(execute_route_flow(
            path=path, method=method, action_key=action_key,
            provider_override=provider_override, model_override=model_override,
        ))
    else:
        with ui.status(f"Executing AI action '{action_key}'"):
            result = _run_async(execute_route_flow(
                path=path, method=method, action_key=action_key,
                provider_override=provider_override, model_override=model_override,
            ))
    _print_execution_result(result, fmt)


@ai_run_group.command("query")
@click.option("--sql", required=True, help="SQL query text")
@click.option("--action", "action_key", required=True, help="Action key (e.g. explain_plan)")
@click.option("--provider", "provider_override", default=None, help="Override AI provider")
@click.option("--model", "model_override", default=None, help="Override AI model")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", help="Output format")
def ai_run_query(sql, action_key, provider_override, model_override, fmt):
    """Execute an AI flow for a SQL query."""
    from aksara.studio.ai_flows import execute_query_flow
    ui = get_ui()

    if fmt == "json":
        result = _run_async(execute_query_flow(
            sql=sql, action_key=action_key,
            provider_override=provider_override, model_override=model_override,
        ))
    else:
        with ui.status(f"Executing AI action '{action_key}'"):
            result = _run_async(execute_query_flow(
                sql=sql, action_key=action_key,
                provider_override=provider_override, model_override=model_override,
            ))
    _print_execution_result(result, fmt)


@ai_run_group.command("migration")
@click.option("--app", default=None, help="App label")
@click.option("--name", default=None, help="Migration name")
@click.option("--action", "action_key", required=True, help="Action key (e.g. explain_migration)")
@click.option("--provider", "provider_override", default=None, help="Override AI provider")
@click.option("--model", "model_override", default=None, help="Override AI model")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", help="Output format")
def ai_run_migration(app, name, action_key, provider_override, model_override, fmt):
    """Execute an AI flow for a migration."""
    from aksara.studio.ai_flows import execute_migration_flow
    ui = get_ui()

    if fmt == "json":
        result = _run_async(execute_migration_flow(
            action_key=action_key, app=app, name=name,
            provider_override=provider_override, model_override=model_override,
        ))
    else:
        with ui.status(f"Executing AI action '{action_key}'"):
            result = _run_async(execute_migration_flow(
                action_key=action_key, app=app, name=name,
                provider_override=provider_override, model_override=model_override,
            ))
    _print_execution_result(result, fmt)


@ai_run_group.command("diagnostic")
@click.option("--issue-id", default=None, help="Diagnostic issue ID")
@click.option("--action", "action_key", required=True, help="Action key (e.g. diagnostic_prioritize)")
@click.option("--provider", "provider_override", default=None, help="Override AI provider")
@click.option("--model", "model_override", default=None, help="Override AI model")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", help="Output format")
def ai_run_diagnostic(issue_id, action_key, provider_override, model_override, fmt):
    """Execute an AI flow for a diagnostic issue."""
    from aksara.studio.ai_flows import execute_diagnostic_flow
    ui = get_ui()

    if fmt == "json":
        result = _run_async(execute_diagnostic_flow(
            action_key=action_key, issue_id=issue_id,
            provider_override=provider_override, model_override=model_override,
        ))
    else:
        with ui.status(f"Executing AI action '{action_key}'"):
            result = _run_async(execute_diagnostic_flow(
                action_key=action_key, issue_id=issue_id,
                provider_override=provider_override, model_override=model_override,
            ))
    _print_execution_result(result, fmt)


# ─── v0.5.31: aksara ai chat ────────────────────────────────────────────────


@ai_flows_group.command("chat")
@click.argument("message")
@click.option("--provider", "provider_override", default=None, help="Override AI provider")
@click.option("--model", "model_override", default=None, help="Override AI model")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text",
              help="Output format (text or json)")
def ai_chat(message, provider_override, model_override, fmt):
    """Send a natural-language command to the Interactive AI Console.

    Examples:

        aksara ai chat "explain the User model"

        aksara ai chat "review GET /api/users" --format json
    """
    from aksara.ai.console_engine import run_console_query
    ui = get_ui()

    if fmt == "json":
        result = _run_async(run_console_query(
            message,
            provider_override=provider_override,
            model_override=model_override,
        ))
    else:
        with ui.status("Consulting AI console"):
            result = _run_async(run_console_query(
                message,
                provider_override=provider_override,
                model_override=model_override,
            ))
    _print_console_result(result, fmt)


def _print_console_result(result: dict, fmt: str):
    """Print an AI Console result to the terminal."""
    ui = get_ui()

    if fmt == "json":
        ui.print_json(result)
        return

    if not result.get("ok"):
        ui.error(result.get("error", "Unknown error"))
        return

    intent = result.get("intent", "?")
    flow_type = result.get("flow_type", "?")
    confidence = result.get("confidence", 0)
    elapsed = result.get("elapsed_ms", 0)
    execution = result.get("execution", {})

    ui.blank()
    ui.section(f"AI Console ({flow_type}/{intent})")
    ui.text(f"  Confidence: {confidence * 100:.0f}%  |  Elapsed: {elapsed:.0f}ms")

    if execution:
        ui.text(
            f"  Provider: {execution.get('provider', '?')}  |  Model: {execution.get('model', '?')}"
        )
        tokens = execution.get("tokens", {})
        if tokens:
            ui.text(f"  Tokens: {tokens.get('total', '?')}")
        ui.blank()
        ui.section("AI Response")
        ui.text(f"  {execution.get('response', '(no response)')}")
    else:
        ui.text("  (no execution result)")

    suggestions = result.get("suggestions", [])
    if suggestions:
        ui.blank()
        ui.text(f"  Suggested next: {', '.join(suggestions)}")
    ui.blank()


# ─── v0.5.32: aksara ai graph ───────────────────────────────────────────────


@ai_flows_group.command("graph")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output full graph as JSON")
@click.option("--summary", "summary", is_flag=True, default=False, help="Compact summary only")
@click.option("--events", "events", is_flag=True, default=False, help="Show recent events only")
@click.option("--rebuild", is_flag=True, default=False, help="Force graph rebuild (ignore cache)")
def ai_graph(as_json, summary, events, rebuild):
    """Show the Project Context Graph.

    Examples:

        aksara ai graph

        aksara ai graph --summary

        aksara ai graph --json

        aksara ai graph --events
    """
    import json as _json
    from aksara.ai.project_graph import build_project_graph
    ui = get_ui()

    if as_json:
        graph = build_project_graph(rebuild=rebuild)
    else:
        with ui.status("Building project graph"):
            graph = build_project_graph(rebuild=rebuild)

    if as_json:
        if events:
            click.echo(_json.dumps({"events": graph.events}, indent=2, default=str))
        elif summary:
            click.echo(_json.dumps(graph.to_summary_dict(), indent=2, default=str))
        else:
            click.echo(_json.dumps(graph.to_dict(), indent=2, default=str))
        return

    if events:
        _print_graph_events(graph)
        return

    if summary:
        _print_graph_summary(graph)
        return

    # Default: text summary
    _print_graph_summary(graph)


def _print_graph_summary(graph):
    ui = get_ui()
    m = graph.metadata
    ui.blank()
    ui.section("Project Graph")
    ui.separator(30)
    ui.text(f"  Models:      {m.model_count}")
    ui.text(f"  Routes:      {m.route_count}")
    ui.text(f"  Queries:     {m.query_count}")
    ui.text(f"  Migrations:  {m.migration_count}")
    ui.text(f"  Diagnostics: {m.diagnostic_count}")
    ui.text(f"  Gaps:        {m.gap_count}")
    ui.text(f"  Events:      {m.event_count}")
    hub = graph.ai_hub
    if hub:
        ui.text(f"  AI Hub:      {hub.status}")
    ui.blank()
    ui.text(f"  Version: {m.version}  |  Generated: {m.generated_at}")
    ui.blank()


def _print_graph_events(graph):
    ui = get_ui()
    evts = graph.events
    if not evts:
        ui.text("  No recent events.")
        return
    ui.blank()
    ui.section(f"Recent Events ({len(evts)})")
    ui.separator(50)
    for e in reversed(evts[-20:]):
        sev = e.get("severity", "info")
        kind = e.get("kind", "?")
        msg = e.get("message", "")
        ts = e.get("timestamp", "")
        color = "red" if sev == "error" else "yellow" if sev == "warning" else None
        prefix = f"  [{sev:7s}] {kind}"
        if ui.is_rich and not ui.config.no_color and color is not None:
            prefix = click.style(prefix, fg=color)
        ui.text(prefix + f"  {msg}  ({ts})")
    ui.blank()


def _styled_grade_label(ui, grade: str) -> str:
    """Return a styled grade label for AI reports."""

    colors = {"A": "green", "B": "blue", "C": "yellow", "D": "red", "F": "red"}
    label = f"({grade})"
    if ui.is_rich and not ui.config.no_color:
        return click.style(label, fg=colors.get(grade), bold=True)
    return label


# ─── v0.5.33: aksara ai debug ───────────────────────────────────────────────


@ai_flows_group.command("debug")
@click.option("--query", default=None, help="Debug question, e.g. 'why is /api/users failing?'")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output full report as JSON")
@click.option("--summary", "summary_only", is_flag=True, default=False, help="Compact summary only")
@click.option("--model", "model_filter", default=None, help="Filter issues by model name")
@click.option("--route", "route_filter", default=None, help="Filter issues by route path")
def ai_debug(query, as_json, summary_only, model_filter, route_filter):
    """Run the AI Debugger root-cause analysis.

    Analyses the Project Context Graph, diagnostics, gaps, and event
    timeline to identify, cluster, and rank issues.

    Examples:

        aksara ai debug

        aksara ai debug --query "why is /api/users failing?"

        aksara ai debug --json

        aksara ai debug --summary
    """
    import json as _json
    from aksara.ai.debugger import run_debugger
    ui = get_ui()

    # Build query from filters if not explicitly provided
    if not query:
        parts = []
        if model_filter:
            parts.append(f"model {model_filter}")
        if route_filter:
            parts.append(f"route {route_filter}")
        if parts:
            query = "debug " + " ".join(parts)

    if as_json:
        report = run_debugger(query=query)
        if summary_only:
            click.echo(_json.dumps(report.to_summary_dict(), indent=2, default=str))
        else:
            click.echo(_json.dumps(report.to_dict(), indent=2, default=str))
        return

    with ui.status("Running AI debugger"):
        report = run_debugger(query=query)

    if not report.ok:
        ui.error(f"Debugger failed: {report.summary}")
        return

    ui.aksara_banner(f"v{CLI_VERSION}", "AI Debugger — Root Cause Analysis")
    ui.text(f"  Issues:      {report.issue_count}")
    ui.text(f"  Clusters:    {report.cluster_count}")
    ui.text(f"  Root Causes: {report.root_cause_count}")
    ui.text(f"  Elapsed:     {report.elapsed_ms:.0f}ms")

    if summary_only:
        ui.blank()
        ui.text(f"  {report.summary}")
        ui.blank()
        return

    if report.root_causes:
        ui.blank()
        ui.section("Root Causes (ranked by confidence)")
        ui.separator(40)
        for rc in report.root_causes:
            sev = rc.severity
            color = "red" if sev == "error" else "yellow" if sev == "warning" else None
            conf_pct = f"{rc.confidence * 100:.0f}%"
            prefix = f"  [{sev}]"
            if ui.is_rich and not ui.config.no_color and color is not None:
                prefix = click.style(prefix, fg=color)
            ui.text(prefix + f" {rc.title}  ({conf_pct} confidence)")
            ui.text(f"    {rc.description}")
            if rc.fix_suggestions:
                for fix in rc.fix_suggestions[:2]:
                    ui.text(f"    > {fix}")

    if report.clusters:
        ui.blank()
        ui.section(f"Clusters ({report.cluster_count})")
        ui.separator(40)
        for cl in report.clusters[:10]:
            ui.text(f"  {cl.label}  ({cl.size} issues, {cl.severity})")

    ui.blank()


# ─── v0.5.34: aksara ai review ──────────────────────────────────────────────


@ai_flows_group.command("review")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output full report as JSON")
@click.option("--summary", "summary_only", is_flag=True, default=False, help="Compact summary only")
@click.option("--metrics", "show_metrics", is_flag=True, default=False, help="Show architecture metrics")
def ai_review(as_json, summary_only, show_metrics):
    """Run the AI Architecture Review.

    Analyses the Project Context Graph to detect anti-patterns, coupling
    risks, schema design issues, and performance concerns.

    Examples:

        aksara ai review

        aksara ai review --json

        aksara ai review --summary

        aksara ai review --metrics
    """
    import json as _json
    from aksara.ai.architecture_review import run_architecture_review
    ui = get_ui()

    if as_json:
        report = run_architecture_review()
        if summary_only:
            click.echo(_json.dumps(report.to_summary_dict(), indent=2, default=str))
        else:
            click.echo(_json.dumps(report.to_dict(), indent=2, default=str))
        return

    with ui.status("Running architecture review"):
        report = run_architecture_review()

    if not report.ok:
        ui.error("Architecture review failed")
        return

    ui.aksara_banner(f"v{CLI_VERSION}", "AI Architecture Review")
    ui.text(
        f"  Architecture Score: {report.score}  {_styled_grade_label(ui, report.grade)}"
    )
    ui.text(f"  Findings:    {report.finding_count}")
    ui.text(f"  Suggestions: {report.suggestion_count}")
    ui.text(f"  Elapsed:     {report.elapsed_ms:.0f}ms")

    if show_metrics:
        m = report.metrics
        ui.blank()
        ui.section("Metrics")
        ui.separator(40)
        ui.text(f"  Models:          {m.model_count}")
        ui.text(f"  Routes:          {m.route_count}")
        ui.text(f"  Queries:         {m.query_count}")
        ui.text(f"  Migrations:      {m.migration_count}")
        ui.text(f"  Diagnostics:     {m.diagnostic_count}")
        ui.text(f"  Avg models/route: {m.avg_models_per_route:.1f}")
        ui.text(f"  Avg queries/route: {m.avg_queries_per_route:.1f}")
        ui.text(f"  Coupling score:  {m.coupling_score:.2f}")

    if summary_only:
        ui.blank()
        return

    if report.findings:
        ui.blank()
        ui.section("Top Findings")
        ui.separator(40)
        for i, f in enumerate(report.findings[:10], 1):
            sev = f.severity
            color = "red" if sev in ("error", "critical") else "yellow" if sev == "warning" else None
            prefix = f"  {i}. [{sev}]"
            if ui.is_rich and not ui.config.no_color and color is not None:
                prefix = click.style(prefix, fg=color)
            ui.text(prefix + f" {f.title}")
            ui.text(f"     {f.description}")

    if report.suggestions:
        ui.blank()
        ui.section("Suggestions")
        ui.separator(40)
        for i, s in enumerate(report.suggestions[:5], 1):
            ui.text(f"  {i}. {s.title}")
            ui.text(f"     {s.description}")

    ui.blank()


@ai_flows_group.command("performance")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--summary", "summary_only", is_flag=True, help="Show summary only")
@click.option("--issues", "show_issues", is_flag=True, help="Show issues list")
@click.option("--metrics", "show_metrics", is_flag=True, help="Show computed metrics")
def ai_performance(as_json, summary_only, show_issues, show_metrics):
    """Run the AI Performance Analyzer.

    Analyses the Project Context Graph, query inspector data, and diagnostics
    to detect slow queries, N+1 patterns, missing indexes, and route hotspots.

    Examples:

        aksara ai flows performance

        aksara ai flows performance --json

        aksara ai flows performance --summary

        aksara ai flows performance --metrics
    """
    import json as _json

    from aksara.ai.performance_analyzer import run_performance_analysis
    ui = get_ui()

    if as_json:
        report = run_performance_analysis()
        click.echo(_json.dumps(report.to_dict(), indent=2, default=str))
        return

    with ui.status("Running performance analysis"):
        report = run_performance_analysis()

    ui.blank()
    ui.section("AI Performance Analyzer")
    ui.separator(40)
    ui.text(f"  Grade:           {report.grade}")
    ui.text(f"  Score:           {report.score}/100")
    ui.text(f"  Issues:          {report.issue_count}")
    ui.text(f"  Recommendations: {report.recommendation_count}")
    ui.text(f"  Elapsed:         {report.elapsed_ms:.0f}ms")

    if show_metrics:
        m = report.metrics
        ui.blank()
        ui.section("Metrics:")
        ui.separator(40)
        ui.text(f"  Total routes:      {m.total_routes}")
        ui.text(f"  Total queries:     {m.total_queries}")
        ui.text(f"  Slow queries:      {m.slow_queries}")
        ui.text(f"  N+1 candidates:    {m.n_plus_one_candidates}")
        ui.text(f"  Missing indexes:   {m.missing_indexes}")
        ui.text(f"  Avg queries/route: {m.avg_queries_per_route:.1f}")
        if m.max_queries_route:
            ui.text(f"  Max queries route: {m.max_queries_route}")

    if summary_only:
        ui.blank()
        return

    if show_issues and report.issues:
        ui.blank()
        ui.section("Issues")
        ui.separator(40)
        for i, issue in enumerate(report.issues[:15], 1):
            sev = issue.severity
            color = "red" if sev in ("critical", "high") else "yellow" if sev == "medium" else None
            prefix = f"  {i}. [{sev}]"
            if ui.is_rich and not ui.config.no_color and color is not None:
                prefix = click.style(prefix, fg=color)
            ui.text(prefix + f" {issue.title}")
            ui.text(f"     {issue.description}")

    if report.recommendations:
        ui.blank()
        ui.section("Recommendations")
        ui.separator(40)
        for i, r in enumerate(report.recommendations[:5], 1):
            ui.text(f"  {i}. {r.title}")
            ui.text(f"     {r.description}")

    ui.blank()


# ─── v0.5.37: aksara ai investigate ─────────────────────────────────────────


@ai.command("investigate")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output full report as JSON")
@click.option("--summary", "summary_only", is_flag=True, default=False, help="Compact summary only")
def ai_investigate(as_json, summary_only):
    """Run the full AI Investigation pipeline.

    Executes all analysis steps and produces a System Intelligence Report:

    - build_project_graph
    - run_architecture_review
    - run_performance_analysis
    - run_debugger
    - run_diagnostics

    Examples:

        aksara ai investigate

        aksara ai investigate --json

        aksara ai investigate --summary
    """
    import json as _json
    from aksara.ai.intent_engine import run_investigation
    ui = get_ui()

    if as_json:
        result = run_investigation()
        if summary_only:
            click.echo(_json.dumps(result.to_summary_dict(), indent=2, default=str))
        else:
            click.echo(_json.dumps(result.to_dict(), indent=2, default=str))
        return

    with ui.status("Running full AI investigation"):
        result = run_investigation()

    ui.aksara_banner(f"v{CLI_VERSION}", "AI Investigation — System Intelligence Report")

    if not result.ok:
        ui.error("Investigation failed")
        ui.text(f"  {result.summary}")
        ui.blank()
        return

    # Step results summary
    ok_count = sum(1 for s in result.step_results if s.ok)
    total = len(result.step_results)
    ui.text(f"  Pipeline:    {ok_count}/{total} steps succeeded")
    ui.text(f"  Elapsed:     {result.elapsed_ms:.0f}ms")

    for sr in result.step_results:
        status = "OK" if not ui.config.unicode else "✓"
        if not sr.ok:
            status = "X" if not ui.config.unicode else "✗"
        if ui.is_rich and not ui.config.no_color:
            status = click.style(status, fg="green" if sr.ok else "red")
        ui.text(f"  {status} {sr.step}  ({sr.elapsed_ms:.0f}ms)")

    # Architecture section
    arch = result.report.get("architecture_report")
    if arch:
        grade = arch.get("grade", "?")
        score = arch.get("score", "?")
        ui.blank()
        ui.text(f"  Architecture Score: {score}  {_styled_grade_label(ui, grade)}")
        findings = arch.get("finding_count", 0)
        ui.text(f"  Findings: {findings}")

    # Performance section
    perf = result.report.get("performance_report")
    if perf:
        grade = perf.get("grade", "?")
        score = perf.get("score", "?")
        issues = perf.get("issue_count", 0)
        ui.blank()
        ui.text(f"  Performance Score: {score}  {_styled_grade_label(ui, grade)}")
        ui.text(f"  Issues: {issues}")
        for ti in perf.get("top_issues", [])[:3]:
            ui.text(f"    - {ti.get('title', '')}")

    # Debug section
    debug = result.report.get("debug_report")
    if debug:
        rc_count = debug.get("root_cause_count", 0)
        ui.blank()
        ui.text(f"  Root Causes: {rc_count}")
        for rc in debug.get("top_root_causes", [])[:3]:
            conf = f"{rc.get('confidence', 0) * 100:.0f}%"
            ui.text(f"    - {rc.get('title', '')}  ({conf})")

    # Diagnostics section
    diag_count = result.report.get("diagnostic_count", 0)
    gap_count = result.report.get("gap_count", 0)
    if diag_count or gap_count:
        ui.blank()
        ui.text(f"  Diagnostics: {diag_count}  |  Gaps: {gap_count}")

    if not summary_only:
        # Graph summary
        gs = result.report.get("graph_summary")
        if gs:
            counts = gs.get("counts", {})
            ui.blank()
            ui.section("Project Graph")
            ui.text(
                f"    Models: {counts.get('models', 0)}  "
                f"Routes: {counts.get('routes', 0)}  "
                f"Queries: {counts.get('queries', 0)}  "
                f"Migrations: {counts.get('migrations', 0)}"
            )

    ui.blank()


# ─── v0.5.40: aksara ai investigate --continue ──────────────────────────────


@ai.command("continue")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON")
def ai_investigate_continue(as_json):
    """Continue the most recent active investigation.

    Resumes the last active investigation session and executes its next
    pending step.  Equivalent to typing "continue" in the AI Console.

    Examples:

        aksara ai continue

        aksara ai continue --json
    """
    import json as _json
    from aksara.ai.session_store import get_active_session
    from aksara.ai.investigation_runner import execute_next_step
    ui = get_ui()

    session = get_active_session()
    if session is None:
        ui.warning("No active investigation session to continue.")
        ui.text("  Start one with: aksara ai investigate")
        ui.blank()
        return

    if as_json:
        session = execute_next_step(session)
        click.echo(_json.dumps(session.to_dict(), indent=2, default=str))
        return

    ui.aksara_banner(f"v{CLI_VERSION}", f"Continuing investigation: {session.goal}")

    with ui.status("Executing next investigation step"):
        session = execute_next_step(session)

    # Show step results
    if session.plan and session.plan.steps:
        for step in session.plan.steps:
            if step.status == "done":
                ui.success(step.label)
            elif step.status == "running":
                ui.warning(step.label)
            elif step.status == "failed":
                ui.error(f"{step.label}: {step.error}")
            elif step.status == "pending":
                ui.text(f"  o {step.label}")

    pending = sum(1 for s in (session.plan.steps if session.plan else []) if s.status == "pending")
    if pending:
        ui.blank()
        ui.text(
            f"  {pending} step(s) remaining. Run 'aksara ai continue' for the next step."
        )
    else:
        ui.blank()
        ui.success("Investigation complete.")

    if session.findings:
        ui.separator(40)
        ui.section("Findings")
        for f in session.findings:
            ui.text(f"    - {f}")

    ui.blank()


# ─── v0.5.40: aksara ai briefing ────────────────────────────────────────────


@ai.command("briefing")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output full briefing as JSON")
@click.option("--summary", "summary_only", is_flag=True, default=False, help="Compact summary only")
def ai_briefing(as_json, summary_only):
    """Generate a daily system health briefing.

    Aggregates performance, architecture, debug signals, and recent
    investigations into a single report.

    Examples:

        aksara ai briefing

        aksara ai briefing --json

        aksara ai briefing --summary
    """
    import json as _json
    from aksara.ai.daily_briefing import generate_daily_briefing
    ui = get_ui()

    if as_json:
        briefing = generate_daily_briefing()
        if summary_only:
            click.echo(_json.dumps(briefing.to_summary_dict(), indent=2, default=str))
        else:
            click.echo(_json.dumps(briefing.to_dict(), indent=2, default=str))
        return

    with ui.status("Generating daily briefing"):
        briefing = generate_daily_briefing()

    ui.aksara_banner(f"v{CLI_VERSION}", "Daily Briefing — System Health Summary")

    ui.blank()
    ui.text(f"  {briefing.summary}")

    # Scores
    if briefing.performance_score >= 0:
        p_grade = "A" if briefing.performance_score >= 90 else "B" if briefing.performance_score >= 80 else "C" if briefing.performance_score >= 70 else "D" if briefing.performance_score >= 60 else "F"
        ui.blank()
        ui.text(
            f"  Performance: {briefing.performance_score:.0f}/100  {_styled_grade_label(ui, p_grade)}"
        )

    if briefing.architecture_score >= 0:
        a_grade = "A" if briefing.architecture_score >= 90 else "B" if briefing.architecture_score >= 80 else "C" if briefing.architecture_score >= 70 else "D" if briefing.architecture_score >= 60 else "F"
        ui.text(
            f"  Architecture: {briefing.architecture_score:.0f}/100  {_styled_grade_label(ui, a_grade)}"
        )

    if not summary_only:
        # Issues
        if briefing.issues:
            ui.blank()
            ui.section(f"Top Issues ({len(briefing.issues)})")
            for issue in briefing.issues[:5]:
                ui.text(f"    - {issue}")

        # Debug signals
        if briefing.debug_signals:
            ui.blank()
            ui.section(f"Debug Signals ({len(briefing.debug_signals)})")
            for sig in briefing.debug_signals[:3]:
                ui.text(f"    - {sig}")

        # Recommendations
        if briefing.recommendations:
            ui.blank()
            ui.section("Recommendations")
            for i, rec in enumerate(briefing.recommendations, 1):
                ui.text(f"    {i}. {rec}")

        # Recent investigations
        if briefing.recent_investigations:
            ui.blank()
            ui.section(
                f"Recent Investigations ({len(briefing.recent_investigations)})"
            )
            for inv in briefing.recent_investigations[:3]:
                status = inv.get("status", "?")
                goal = inv.get("goal", "?")
                ui.text(f"    - [{status}] {goal}")

    ui.blank()


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
@click.option("--database-url", envvar=_DATABASE_ENVVARS, help="Database URL")
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
@click.option("--database-url", envvar=_DATABASE_ENVVARS, help="Database URL")
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
@click.option("--database-url", envvar=_DATABASE_ENVVARS, help="Database URL")
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
@click.option("--database-url", envvar=_DATABASE_ENVVARS, help="Database URL")
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
@click.option("--database-url", envvar=_DATABASE_ENVVARS, help="Database URL")
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


# =============================================================================
# Studio Commands (v0.5.0)
# =============================================================================


@cli.group()
def studio():
    """Studio IDE integration commands.
    
    Commands for testing and managing Aksara Studio integration.
    """
    pass


@studio.command("handshake")
@click.option("--app", "-a", default="main:app", help="App path (e.g., main:app)")
@click.option("--format", "-f", "output_format", type=click.Choice(["json", "pretty"]), default="pretty", help="Output format")
def studio_handshake(app: str, output_format: str):
    """Test the Studio handshake locally.
    
    Simulates what Aksara Studio would receive when connecting to your app.
    Useful for debugging integration issues.
    
    Examples:
        aksara studio handshake
        aksara studio handshake --app myapp:app
        aksara studio handshake --format json
    """
    import json as json_module
    
    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara Studio\033[0m - Handshake Test")
    click.echo()
    
    # Try to load the app
    try:
        module_path, app_name = app.split(":")
        module = __import__(module_path, fromlist=[app_name])
        app_instance = getattr(module, app_name)
    except (ValueError, ImportError, AttributeError) as e:
        click.echo(f"  \033[31m✗\033[0m Failed to load app '{app}': {e}")
        click.echo()
        click.echo("  Make sure your app path is correct (e.g., main:app)")
        sys.exit(1)
    
    # Build handshake
    try:
        from aksara.studio.utils import build_studio_handshake
        
        # Run async function
        handshake = asyncio.get_event_loop().run_until_complete(
            build_studio_handshake(app_instance)
        )
        
        if output_format == "json":
            click.echo(json_module.dumps(handshake.model_dump(), indent=2))
        else:
            # Pretty print
            click.echo("  \033[32m✓\033[0m Handshake successful!")
            click.echo()
            click.echo("  \033[1mProject:\033[0m")
            click.echo(f"    Name:           {handshake.project.name}")
            click.echo(f"    Version:        {handshake.project.version}")
            click.echo(f"    Aksara:         {handshake.project.aksara_version}")
            click.echo(f"    Python:         {handshake.project.python_version}")
            click.echo(f"    Environment:    {handshake.project.environment}")
            click.echo(f"    Debug:          {handshake.project.debug_mode}")
            click.echo()
            click.echo("  \033[1mDatabase:\033[0m")
            click.echo(f"    Connected:      {handshake.database.connected}")
            click.echo(f"    Pool Size:      {handshake.database.pool_size}")
            click.echo(f"    Available:      {handshake.database.pool_available}")
            click.echo()
            click.echo("  \033[1mCapabilities:\033[0m")
            for cap in handshake.capabilities:
                click.echo(f"    • {cap.value}")
            click.echo()
            click.echo("  \033[1mChecksums:\033[0m")
            click.echo(f"    Schema:         {handshake.checksums.schema_checksum}")
            click.echo(f"    Migrations:     {handshake.checksums.migrations_checksum}")
            click.echo(f"    Settings:       {handshake.checksums.settings_checksum}")
            click.echo(f"    Routes:         {handshake.checksums.routes_checksum}")
            click.echo()
        
    except Exception as e:
        click.echo(f"  \033[31m✗\033[0m Handshake failed: {e}")
        import traceback
        if output_format == "pretty":
            click.echo()
            click.echo("  \033[90mStacktrace:\033[0m")
            for line in traceback.format_exc().split('\n'):
                click.echo(f"    {line}")
        sys.exit(1)


@studio.command("url")
@click.option("--host", "-h", default="localhost", help="Server host")
@click.option("--port", "-p", default=8000, type=int, help="Server port")
@click.option("--https/--no-https", default=False, help="Use HTTPS")
@click.option("--section", "-s", default=None, type=click.Choice([
    "overview", "models", "routes", "migrations",
    "db-queries", "ai-profiles", "diagnostics",
], case_sensitive=False), help="Open a specific Studio section")
def studio_url(host: str, port: int, https: bool, section: str):
    """Show Studio endpoint URLs.
    
    Displays the URLs for Studio integration endpoints.
    
    Examples:
        aksara studio url
        aksara studio url --port 8080
        aksara studio url --https
        aksara studio url --section migrations
    """
    protocol = "https" if https else "http"
    base_url = f"{protocol}://{host}:{port}"
    
    # v0.5.16: Build dashboard URL with optional section hash
    dashboard_url = f"{base_url}/studio/ui"
    if section:
        dashboard_url += f"#/{section}"
    
    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara Studio\033[0m - Endpoint URLs")
    click.echo()
    click.echo("  \033[1mStudio UI:\033[0m")
    click.echo(f"    Dashboard:       {dashboard_url}")
    click.echo()
    click.echo("  \033[1mStudio Endpoints:\033[0m")
    click.echo(f"    Handshake:       {base_url}/studio/handshake")
    click.echo(f"    Context Summary: {base_url}/studio/context/summary")
    click.echo(f"    Health:          {base_url}/studio/health")
    click.echo(f"    Runtime Info:    {base_url}/studio/runtime/info")
    click.echo(f"    Routes:          {base_url}/studio/runtime/routes")
    click.echo()
    click.echo("  \033[1mAI Endpoints (full context):\033[0m")
    click.echo(f"    Full Context:    {base_url}/ai/context/full")
    click.echo(f"    Tools:           {base_url}/ai/tools")
    click.echo(f"    Tool Catalog:    {base_url}/ai/tools/mcp")
    click.echo(f"    MCP Protocol:    {base_url}/mcp/ (when enabled)")
    click.echo()
    click.echo("  \033[90mTip: Use --https for production URLs\033[0m")
    click.echo()


# =============================================================================
# v0.5.3: Studio UI Commands
# =============================================================================

@studio.command("open")
@click.option("--host", "-h", default="127.0.0.1", help="Server host")
@click.option("--port", "-p", default=8000, type=int, help="Server port")
@click.option("--https/--no-https", default=False, help="Use HTTPS")
def studio_open(host: str, port: int, https: bool):
    """Open the Studio UI in your browser.
    
    Opens the embedded Studio dashboard in your default web browser.
    Make sure your Aksara server is running first.
    
    Examples:
        aksara studio open
        aksara studio open --port 8080
        aksara studio open --host 192.168.1.100
    """
    import webbrowser
    
    protocol = "https" if https else "http"
    url = f"{protocol}://{host}:{port}/studio/ui"
    
    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara Studio\033[0m")
    click.echo()
    click.echo(f"  Opening: {url}")
    click.echo()
    
    try:
        webbrowser.open(url)
        click.echo("  \033[32m✓\033[0m Browser opened successfully")
    except Exception as e:
        click.echo(f"  \033[31m✗\033[0m Failed to open browser: {e}")
        click.echo(f"  \033[90mPlease open this URL manually: {url}\033[0m")
        sys.exit(1)
    
    click.echo()


@studio.command("ui-path")
def studio_ui_path():
    """Show the path to Studio UI static assets.
    
    Displays the filesystem path where Studio UI files are located.
    Useful for debugging or customization.
    
    Examples:
        aksara studio ui-path
    """
    from aksara.studio.fastapi import get_static_dir
    
    static_dir = get_static_dir()
    
    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara Studio\033[0m - Static Assets Path")
    click.echo()
    click.echo(f"  Path: {static_dir}")
    click.echo()
    
    # Check if directory exists and list contents
    if static_dir.exists():
        click.echo("  \033[1mContents:\033[0m")
        for item in sorted(static_dir.iterdir()):
            icon = "📁" if item.is_dir() else "📄"
            click.echo(f"    {icon} {item.name}")
    else:
        click.echo("  \033[31m✗\033[0m Directory does not exist!")
    
    click.echo()


@studio.command("ai-context")
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["json", "summary"]),
    default="json",
    help="Output format (default: json)"
)
def studio_ai_context(output_format):
    """Export AI context for external AI tools.
    
    v0.5.4: Outputs the same JSON as GET /studio/ai/context.
    Use this to pipe context to AI assistants or save for later use.
    
    Examples:
        aksara studio ai-context
        aksara studio ai-context --format summary
        aksara studio ai-context > context.json
    """
    import json
    import asyncio
    
    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara Studio\033[0m - AI Context Export")
    click.echo()
    
    try:
        # We need to create a minimal context without a full app
        # Use the utils directly with mock data
        import aksara
        from aksara.conf import settings
        from aksara.registry import ModelRegistry
        from aksara.studio.models import (
            StudioAiProjectMeta,
            StudioAiModelSummary,
            StudioAiContextExport,
            StudioMigrationStatus,
        )
        from aksara.studio.utils import _get_ai_tools_summary, compute_schema_checksum
        
        # Get project metadata
        env = getattr(settings, 'env', None) or 'development'
        project = StudioAiProjectMeta(
            name=getattr(settings, 'app_title', 'Aksara App'),
            version=aksara.__version__,
            environment=env,
            debug=settings.debug,
        )
        
        # Build model summaries
        models = []
        all_models = ModelRegistry.all()
        for name, model_cls in all_models.items():
            try:
                meta = getattr(model_cls, '_meta', None)
                table_name = meta.table_name if meta else name.lower()
                app_label = meta.app_label if meta else None
                
                field_names = []
                if meta and hasattr(meta, 'fields'):
                    field_names = list(meta.fields.keys())
                
                has_timestamps = 'created_at' in field_names or 'updated_at' in field_names
                pk = 'id'
                if meta and hasattr(meta, 'primary_key'):
                    pk = meta.primary_key
                
                models.append(StudioAiModelSummary(
                    name=name,
                    table_name=table_name,
                    app_label=app_label,
                    fields=field_names,
                    primary_key=pk,
                    has_timestamps=has_timestamps,
                ))
            except Exception:
                continue
        
        # Get tools
        tools = _get_ai_tools_summary()
        
        # Get apps
        apps = list(settings.installed_apps) if settings.installed_apps else list(settings.apps)
        
        # Compute checksum
        checksum = compute_schema_checksum(list(all_models.values()))
        
        # Build export
        context_export = StudioAiContextExport(
            project=project,
            models=models,
            routes=[],  # No routes without running app
            tools=tools,
            apps=apps,
            migration_status=StudioMigrationStatus(),
            schema_checksum=checksum,
        )
        
        if output_format == "summary":
            click.echo(f"  \033[1mProject:\033[0m {project.name} v{project.version}")
            click.echo(f"  \033[1mEnvironment:\033[0m {project.environment}")
            click.echo(f"  \033[1mDebug:\033[0m {project.debug}")
            click.echo()
            click.echo(f"  \033[1mModels:\033[0m {len(models)}")
            for model in models[:5]:  # Show first 5
                click.echo(f"    - {model.name} ({model.table_name})")
            if len(models) > 5:
                click.echo(f"    ... and {len(models) - 5} more")
            click.echo()
            click.echo(f"  \033[1mTools:\033[0m {len(tools)}")
            for tool in tools[:3]:
                safe_icon = "🔒" if tool.safe else "⚠️"
                click.echo(f"    {safe_icon} {tool.name}")
            click.echo()
            click.echo(f"  \033[1mApps:\033[0m {', '.join(apps) if apps else 'None'}")
            click.echo(f"  \033[1mSchema Checksum:\033[0m {checksum[:16]}...")
        else:
            # JSON output
            output = context_export.model_dump(mode='json')
            # Convert datetime to ISO string
            if 'exported_at' in output:
                output['exported_at'] = context_export.exported_at.isoformat()
            click.echo(json.dumps(output, indent=2))
        
        click.echo()
        
    except Exception as e:
        click.echo(f"  \033[31m✗\033[0m Error: {e}", err=True)
        raise click.Abort()


def main():
    """Main entry point for CLI."""
    cli()


# =============================================================================
# v0.5.10: Database Profiler Commands
# =============================================================================

@cli.group()
def db():
    """Database tools and profiling.
    
    Commands for database inspection, profiling, and diagnostics.
    
    v0.5.10: Query Inspector & ORM Profiler
    """
    pass


@db.command("stats")
@click.option("--app", "-a", default=None, help="App path (e.g., main:app)")
@click.option("--format", "-f", "output_format", type=click.Choice(["pretty", "json"]), default="pretty", help="Output format")
def db_stats(app: Optional[str], output_format: str):
    """Show database query statistics.
    
    Displays aggregate statistics from the query tracer including:
    - Total queries and requests tracked
    - Average queries per request
    - Slow query counts
    - N+1 detection stats
    
    Note: Requires db_trace_enabled=True in settings.
    
    Examples:
        aksara db stats
        aksara db stats --format json
    """
    import json
    
    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara\033[0m - Database Statistics")
    click.echo()
    
    try:
        from aksara.db.tracing import is_tracing_enabled, get_trace_stats
        from aksara.conf import settings
        
        # Check if tracing is enabled
        if not is_tracing_enabled():
            click.echo("  \033[33m⚠\033[0m Query tracing is disabled.")
            click.echo()
            click.echo("  To enable, set one of:")
            click.echo("    - AKSARA_DB_TRACE_ENABLED=true (environment)")
            click.echo("    - db_trace_enabled=True (settings)")
            click.echo()
            sys.exit(0)
        
        # Get stats
        stats = get_trace_stats()
        
        if output_format == "json":
            click.echo(json.dumps(stats, indent=2))
        else:
            # Pretty print
            click.echo("  \033[32m✓\033[0m Query tracing is enabled")
            click.echo(f"  \033[1mSlow threshold:\033[0m {settings.db_trace_slow_threshold_ms}ms")
            click.echo()
            
            if stats["total_batches"] == 0:
                click.echo("  No data collected yet. Run some queries with tracing enabled.")
                click.echo()
            else:
                click.echo("  \033[1mOverall Statistics:\033[0m")
                click.echo(f"    Requests tracked:        {stats['total_batches']}")
                click.echo(f"    Total queries:           {stats['total_queries']}")
                click.echo(f"    Avg queries per request: {stats['avg_queries_per_request']:.2f}")
                click.echo()
                click.echo("  \033[1mPerformance Issues:\033[0m")
                slow_count = stats['total_slow_queries']
                n1_count = stats['requests_with_n_plus_one']
                
                if slow_count > 0:
                    click.echo(f"    \033[33m⚠\033[0m Slow queries:        {slow_count}")
                    click.echo(f"       Requests affected:    {stats['requests_with_slow_queries']}")
                else:
                    click.echo(f"    \033[32m✓\033[0m No slow queries")
                
                if n1_count > 0:
                    click.echo(f"    \033[31m⚠\033[0m N+1 detected in:     {n1_count} requests")
                else:
                    click.echo(f"    \033[32m✓\033[0m No N+1 patterns detected")
            
            click.echo()
            
    except Exception as e:
        click.echo(f"  \033[31m✗\033[0m Error: {e}", err=True)
        raise click.Abort()


@db.command("profile")
@click.option("--app", "-a", default=None, help="App path (e.g., main:app)")
@click.option("--limit", "-n", default=20, help="Number of items to show")
@click.option("--format", "-f", "output_format", type=click.Choice(["pretty", "json"]), default="pretty", help="Output format")
@click.option("--slow", is_flag=True, help="Show slowest queries")
@click.option("--recent", is_flag=True, help="Show recent request batches")
def db_profile(app: Optional[str], limit: int, output_format: str, slow: bool, recent: bool):
    """Show detailed query profile data.
    
    Displays recent query batches and slowest queries from the tracer.
    
    Use --slow to see the slowest queries across all requests.
    Use --recent to see recent request batches with query counts.
    
    Note: Requires db_trace_enabled=True in settings.
    
    Examples:
        aksara db profile
        aksara db profile --slow --limit 10
        aksara db profile --recent
        aksara db profile --format json
    """
    import json
    
    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara\033[0m - Database Profile")
    click.echo()
    
    # Default to showing both if neither specified
    if not slow and not recent:
        slow = True
        recent = True
    
    try:
        from aksara.db.tracing import (
            is_tracing_enabled,
            get_recent_traces,
            get_top_slow_queries,
        )
        from aksara.conf import settings
        
        # Check if tracing is enabled
        if not is_tracing_enabled():
            click.echo("  \033[33m⚠\033[0m Query tracing is disabled.")
            click.echo()
            click.echo("  To enable, set one of:")
            click.echo("    - AKSARA_DB_TRACE_ENABLED=true (environment)")
            click.echo("    - db_trace_enabled=True (settings)")
            click.echo()
            sys.exit(0)
        
        if output_format == "json":
            output = {}
            if slow:
                slow_queries = get_top_slow_queries(limit)
                output["slow_queries"] = [q.to_dict() for q in slow_queries]
            if recent:
                batches = get_recent_traces(limit)
                output["recent_batches"] = [b.to_dict() for b in batches]
            click.echo(json.dumps(output, indent=2, default=str))
        else:
            # Pretty print
            if slow:
                click.echo("  \033[1mSlowest Queries:\033[0m")
                click.echo(f"  (Threshold: {settings.db_trace_slow_threshold_ms}ms)")
                click.echo()
                
                slow_queries = get_top_slow_queries(limit)
                if not slow_queries:
                    click.echo("    No slow queries recorded.")
                else:
                    for i, q in enumerate(slow_queries, 1):
                        sql_preview = q.sql.replace('\n', ' ')[:60]
                        if len(q.sql) > 60:
                            sql_preview += "..."
                        
                        click.echo(f"  {i:3}. \033[33m{q.duration_ms:8.2f}ms\033[0m  {q.operation:8} {q.table or 'unknown':15}")
                        click.echo(f"       {sql_preview}")
                        if q.stack_summary:
                            click.echo(f"       \033[90m{q.stack_summary}\033[0m")
                        click.echo()
                
                if recent:
                    click.echo("  " + "─" * 60)
                    click.echo()
            
            if recent:
                click.echo("  \033[1mRecent Requests:\033[0m")
                click.echo()
                
                batches = get_recent_traces(limit)
                if not batches:
                    click.echo("    No requests recorded.")
                else:
                    for b in batches:
                        method_color = "\033[32m" if b.method == "GET" else "\033[33m"
                        status_color = "\033[32m" if (b.status_code or 0) < 400 else "\033[31m"
                        
                        warnings = []
                        if b.slow_queries > 0:
                            warnings.append(f"\033[33m{b.slow_queries} slow\033[0m")
                        if b.n_plus_one_suspicions:
                            warnings.append(f"\033[31mN+1\033[0m")
                        warning_str = f" [{', '.join(warnings)}]" if warnings else ""
                        
                        click.echo(f"    {method_color}{b.method or '-':6}\033[0m {b.path or '/':30} {status_color}{b.status_code or '-':3}\033[0m  {b.total_queries:3} queries  {b.total_duration_ms:8.2f}ms{warning_str}")
                        
                        # Show N+1 warnings
                        for warning in b.n_plus_one_suspicions:
                            click.echo(f"           \033[31m⚠ {warning}\033[0m")
                
                click.echo()
            
    except Exception as e:
        click.echo(f"  \033[31m✗\033[0m Error: {e}", err=True)
        raise click.Abort()


@db.command("clear")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def db_clear(force: bool):
    """Clear stored query trace data.
    
    Removes all collected query traces from the in-memory ring buffer.
    
    Examples:
        aksara db clear
        aksara db clear --force
    """
    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara\033[0m - Clear Query Traces")
    click.echo()
    
    try:
        from aksara.db.tracing import clear_traces, get_trace_stats
        
        stats = get_trace_stats()
        count = stats.get("total_batches", 0)
        
        if count == 0:
            click.echo("  No traces to clear.")
            click.echo()
            return
        
        if not force:
            click.echo(f"  This will clear {count} request batches from memory.")
            if not click.confirm("  Continue?"):
                click.echo("  Aborted.")
                return
        
        clear_traces()
        click.echo(f"  \033[32m✓\033[0m Cleared {count} request batches.")
        click.echo()
        
    except Exception as e:
        click.echo(f"  \033[31m✗\033[0m Error: {e}", err=True)
        raise click.Abort()


# =============================================================================
# v0.5.11: AI Profiles & Provider Contracts Commands
# =============================================================================


@ai.command("providers")
@click.option("--format", "-f", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def ai_providers(output_format: str):
    """List configured AI providers.
    
    Displays all AI provider profiles including:
    - Provider name and type (kind)
    - Number of available models
    - Whether it's the default provider
    
    Note: Uses built-in example providers if none configured.
    
    Examples:
        aksara ai providers
        aksara ai providers --format json
    """
    import json
    
    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara\033[0m - AI Providers")
    click.echo()
    
    try:
        from aksara.conf import settings
        from aksara.ai.providers import build_default_ai_profile_set
        
        # Check if profiles are enabled
        ai_profiles_enabled = getattr(settings, 'ai_profiles_enabled', True)
        
        if not ai_profiles_enabled:
            click.echo("  \033[33m⚠\033[0m AI profiles are disabled.")
            click.echo()
            click.echo("  To enable, set:")
            click.echo("    - ai_profiles_enabled=True (settings)")
            click.echo()
            sys.exit(0)
        
        # Get profile set
        profile_set = build_default_ai_profile_set(settings)
        
        if output_format == "json":
            data = {
                "providers": [
                    {
                        "name": p.name,
                        "display_name": p.display_name,
                        "kind": p.kind,
                        "model_count": len(p.models),
                        "default_model": p.default_model,
                        "is_default": p.name == profile_set.default_provider,
                        "is_example": p.metadata.get("_example", False),
                    }
                    for p in profile_set.providers
                ],
                "default_provider": profile_set.default_provider,
                "environment": profile_set.environment,
            }
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            if not profile_set.providers:
                click.echo("  No AI providers configured.")
                click.echo()
                return
            
            click.echo(f"  Found {len(profile_set.providers)} provider(s):")
            click.echo()
            
            # Print header
            click.echo(f"  {'NAME':<25} {'KIND':<12} {'MODELS':<8} {'DEFAULT':<8} {'EXAMPLE':<8}")
            click.echo(f"  {'-'*25} {'-'*12} {'-'*8} {'-'*8} {'-'*8}")
            
            for provider in profile_set.providers:
                is_default = "\033[32m✓\033[0m" if provider.name == profile_set.default_provider else ""
                is_example = "yes" if provider.metadata.get("_example", False) else ""
                
                click.echo(
                    f"  {provider.name:<25} "
                    f"{provider.kind:<12} "
                    f"{len(provider.models):<8} "
                    f"{is_default:<8} "
                    f"{is_example:<8}"
                )
            
            click.echo()
            
            if profile_set.default_provider:
                click.echo(f"  Default provider: \033[1m{profile_set.default_provider}\033[0m")
            
            # Show example warning if all are examples
            all_examples = all(p.metadata.get("_example", False) for p in profile_set.providers)
            if all_examples:
                click.echo()
                click.echo("  \033[33m⚠\033[0m All providers are built-in examples.")
                click.echo("    Configure real providers via ai_providers setting.")
            
            click.echo()
            
    except Exception as e:
        click.echo(f"  \033[31m✗\033[0m Error: {e}", err=True)
        raise click.Abort()


@ai.command("models")
@click.option("--provider", "-p", default=None, help="Filter by provider name")
@click.option("--format", "-f", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def ai_models(provider: Optional[str], output_format: str):
    """List available AI models.
    
    Displays all AI models from configured providers including:
    - Model name and kind
    - Provider it belongs to
    - Capability flags (tools, streaming, vision)
    - Tags
    
    Use --provider to filter models by a specific provider.
    
    Examples:
        aksara ai models
        aksara ai models --provider example_openai_like
        aksara ai models --format json
    """
    import json
    
    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara\033[0m - AI Models")
    click.echo()
    
    try:
        from aksara.conf import settings
        from aksara.ai.providers import build_default_ai_profile_set
        
        # Check if profiles are enabled
        ai_profiles_enabled = getattr(settings, 'ai_profiles_enabled', True)
        
        if not ai_profiles_enabled:
            click.echo("  \033[33m⚠\033[0m AI profiles are disabled.")
            click.echo()
            sys.exit(0)
        
        # Get profile set
        profile_set = build_default_ai_profile_set(settings)
        
        # Collect models
        models = []
        for p in profile_set.providers:
            if provider and p.name != provider:
                continue
            for m in p.models:
                models.append({
                    "provider": p.name,
                    "name": m.name,
                    "display_name": m.display_name,
                    "kind": m.kind,
                    "supports_tools": m.supports_tools,
                    "supports_streaming": m.supports_streaming,
                    "supports_vision": getattr(m, 'supports_vision', False),
                    "max_input_tokens": m.max_input_tokens,
                    "max_output_tokens": m.max_output_tokens,
                    "tags": m.tags,
                })
        
        if output_format == "json":
            click.echo(json.dumps({"models": models}, indent=2))
        else:
            # Table format
            if not models:
                if provider:
                    click.echo(f"  No models found for provider '{provider}'.")
                else:
                    click.echo("  No models configured.")
                click.echo()
                return
            
            click.echo(f"  Found {len(models)} model(s):")
            click.echo()
            
            # Print header
            click.echo(f"  {'NAME':<22} {'PROVIDER':<22} {'KIND':<12} {'TOOLS':<6} {'STREAM':<7} {'TAGS'}")
            click.echo(f"  {'-'*22} {'-'*22} {'-'*12} {'-'*6} {'-'*7} {'-'*20}")
            
            for m in models:
                tools = "✓" if m["supports_tools"] else ""
                stream = "✓" if m["supports_streaming"] else ""
                tags = ", ".join(m["tags"][:3]) if m["tags"] else ""
                if len(m["tags"]) > 3:
                    tags += "..."
                
                click.echo(
                    f"  {m['name']:<22} "
                    f"{m['provider']:<22} "
                    f"{m['kind']:<12} "
                    f"{tools:<6} "
                    f"{stream:<7} "
                    f"{tags}"
                )
            
            click.echo()
            
    except Exception as e:
        click.echo(f"  \033[31m✗\033[0m Error: {e}", err=True)
        raise click.Abort()


@ai.command("secrets")
@click.option("--format", "-f", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def ai_secrets(output_format: str):
    """Show required AI secrets status.
    
    Displays environment variables needed for AI providers:
    - Environment variable name
    - Provider it's associated with
    - Whether it's required
    - Whether it's currently set (not the value!)
    
    Note: This command NEVER shows actual secret values.
    
    Examples:
        aksara ai secrets
        aksara ai secrets --format json
    """
    import json
    import os
    
    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara\033[0m - AI Secrets")
    click.echo()
    
    try:
        from aksara.conf import settings
        from aksara.ai.providers import build_secret_hints_from_settings
        
        # Get secret hints
        hints = build_secret_hints_from_settings(settings)
        
        if not hints:
            click.echo("  No secret hints configured.")
            click.echo()
            return
        
        # Check which are configured
        secrets = []
        configured_count = 0
        for hint in hints:
            is_configured = os.environ.get(hint.env_var) is not None
            if is_configured:
                configured_count += 1
            
            secrets.append({
                "provider_name": hint.provider_name,
                "env_var": hint.env_var,
                "required": hint.required,
                "description": hint.description,
                "is_configured": is_configured,
            })
        
        if output_format == "json":
            click.echo(json.dumps({
                "secrets": secrets,
                "configured_count": configured_count,
                "total_count": len(secrets),
            }, indent=2))
        else:
            # Table format
            click.echo(f"  Found {len(secrets)} secret(s) ({configured_count} configured):")
            click.echo()
            
            # Print header
            click.echo(f"  {'ENV_VAR':<30} {'PROVIDER':<25} {'REQUIRED':<9} {'STATUS'}")
            click.echo(f"  {'-'*30} {'-'*25} {'-'*9} {'-'*12}")
            
            for s in secrets:
                required = "yes" if s["required"] else "no"
                if s["is_configured"]:
                    status = "\033[32m✓ Set\033[0m"
                else:
                    status = "\033[33m✗ Not set\033[0m" if s["required"] else "\033[90m✗ Not set\033[0m"
                
                click.echo(
                    f"  {s['env_var']:<30} "
                    f"{s['provider_name']:<25} "
                    f"{required:<9} "
                    f"{status}"
                )
            
            click.echo()
            
            # Summary
            if configured_count == len(secrets):
                click.echo("  \033[32m✓\033[0m All secrets are configured.")
            else:
                missing = len(secrets) - configured_count
                click.echo(f"  \033[33m⚠\033[0m {missing} secret(s) not configured.")
            
            click.echo()
            
    except Exception as e:
        click.echo(f"  \033[31m✗\033[0m Error: {e}", err=True)
        raise click.Abort()


@ai.command("validate")
@click.option("--format", "-f", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def ai_validate(output_format: str):
    """Validate AI profile configuration.
    
    v0.5.12: Runs validation checks on the AI profile configuration.
    
    Checks include:
    - Provider names are unique
    - Model names are unique within providers
    - Provider and model kinds are valid
    - Default provider exists and has models
    - Profile set is non-empty
    
    Exit codes:
    - 0: Configuration is valid (no errors)
    - 1: Configuration has errors
    
    Examples:
        aksara ai validate
        aksara ai validate --format json
    """
    import json
    
    try:
        from aksara.conf import settings
        from aksara.ai.providers import build_default_ai_profile_set, validate_profile_set
        
        # Get environment info
        environment = "development" if getattr(settings, "debug", False) else "production"
        
        click.echo()
        click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m - AI Profiles Validation (env: {environment})")
        click.echo()
        
        # Check if profiles are enabled
        ai_profiles_enabled = getattr(settings, 'ai_profiles_enabled', True)
        
        if not ai_profiles_enabled:
            health_data = {
                "is_valid": True,
                "error_count": 0,
                "warning_count": 0,
                "info_count": 1,
                "issues": [{
                    "id": "ai_profiles_disabled",
                    "kind": "info",
                    "severity": "info",
                    "message": "AI profiles are disabled",
                    "field": "ai_profiles_enabled",
                }],
            }
            
            if output_format == "json":
                click.echo(json.dumps(health_data, indent=2))
            else:
                click.echo("  Status: \033[32mOK\033[0m (AI profiles disabled)")
                click.echo()
                click.echo("  - [INFO] AI profiles are disabled.")
                click.echo()
            sys.exit(0)
        
        # Build and validate profile set
        profile_set = build_default_ai_profile_set(settings)
        health = validate_profile_set(profile_set)
        
        if output_format == "json":
            click.echo(json.dumps(health.model_dump(), indent=2))
        else:
            # Text format
            if health.is_valid:
                if health.warning_count > 0:
                    click.echo(f"  Status: \033[32mOK\033[0m ({health.warning_count} warning(s))")
                else:
                    click.echo("  Status: \033[32mOK\033[0m")
            else:
                parts = []
                if health.error_count > 0:
                    parts.append(f"{health.error_count} error(s)")
                if health.warning_count > 0:
                    parts.append(f"{health.warning_count} warning(s)")
                click.echo(f"  Status: \033[31mERROR\033[0m ({', '.join(parts)})")
            
            click.echo()
            
            # Show issues
            if health.issues:
                for issue in health.issues:
                    if issue.severity == "error":
                        severity_badge = "\033[31m[ERROR]\033[0m"
                    elif issue.severity == "warning":
                        severity_badge = "\033[33m[WARNING]\033[0m"
                    else:
                        severity_badge = "\033[90m[INFO]\033[0m"
                    
                    click.echo(f"  - {severity_badge} {issue.kind}: {issue.message}")
                
                click.echo()
            else:
                click.echo("  No issues found.")
                click.echo()
            
            # Show summary
            provider_count = len(profile_set.providers)
            model_count = profile_set.total_models()
            click.echo(f"  Providers: {provider_count}")
            click.echo(f"  Models: {model_count}")
            if profile_set.default_provider:
                click.echo(f"  Default: {profile_set.default_provider}")
            click.echo()
        
        # Exit code based on validity
        sys.exit(0 if health.is_valid else 1)
        
    except Exception as e:
        click.echo(f"  \033[31m✗\033[0m Error: {e}", err=True)
        raise click.Abort()


@ai.command("hints")
@click.option("--view", "-v", "view_name", default=None, help="Filter by view/viewset name")
@click.option("--route", "-r", "route_name", default=None, help="Filter by route/action name")
@click.option("--risk", type=click.Choice(["low", "medium", "high"]), default=None, help="Filter by risk level")
@click.option("--format", "-f", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def ai_hints(view_name: Optional[str], route_name: Optional[str], risk: Optional[str], output_format: str):
    """List AI route hints defined in the application.
    
    v0.5.13: Shows per-view/per-route AI metadata for LLM guidance.
    
    AI hints provide structured information about what each route does,
    how risky it is, and how to use it effectively with LLMs.
    
    Examples:
        aksara ai hints
        aksara ai hints --view UserViewSet
        aksara ai hints --route create
        aksara ai hints --risk high
        aksara ai hints --format json
    """
    import json
    
    try:
        from aksara.conf import settings
        from aksara.ai.hints import build_ai_hint_set
        
        environment = "development" if getattr(settings, "debug", False) else "production"
        
        click.echo()
        click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m - AI Route Hints (env: {environment})")
        click.echo()
        
        # Discover and build hints
        app_module = getattr(settings, 'app_module', None)
        if app_module:
            discover_models(app_module)
        
        hint_set = build_ai_hint_set(settings)
        
        # Filter hints
        filtered_hints = hint_set.routes
        
        if view_name:
            filtered_hints = [h for h in filtered_hints if view_name.lower() in (h.view_name or "").lower()]
        
        if route_name:
            filtered_hints = [h for h in filtered_hints if route_name.lower() in (h.route_name or "").lower()]
        
        if risk:
            filtered_hints = [h for h in filtered_hints if h.risk_level == risk]
        
        # Sort by risk level (high -> medium -> low), then by view/route name
        risk_order = {"high": 0, "medium": 1, "low": 2}
        filtered_hints = sorted(filtered_hints, key=lambda h: (
            risk_order.get(h.risk_level, 3),
            h.view_name or "",
            h.route_name or ""
        ))
        
        if output_format == "json":
            output_data = {
                "total_count": hint_set.total_count,
                "filtered_count": len(filtered_hints),
                "hints_by_risk": {
                    "high": hint_set.high_risk_count,
                    "medium": hint_set.medium_risk_count,
                    "low": hint_set.low_risk_count,
                },
                "hints": [h.model_dump() for h in filtered_hints],
            }
            click.echo(json.dumps(output_data, indent=2, default=str))
        else:
            # Text format
            total = hint_set.total_count
            shown = len(filtered_hints)
            
            # Show stats
            high_count = hint_set.high_risk_count
            medium_count = hint_set.medium_risk_count
            low_count = hint_set.low_risk_count
            
            click.echo(f"  Total: {total} hints")
            click.echo(f"  Risk breakdown: \033[31m{high_count} high\033[0m | \033[33m{medium_count} medium\033[0m | \033[32m{low_count} low\033[0m")
            
            if view_name or route_name or risk:
                click.echo(f"  Showing: {shown} (filtered)")
            click.echo()
            
            if not filtered_hints:
                click.echo("  No hints found matching the filter.")
                click.echo()
            else:
                for hint in filtered_hints:
                    # Risk badge colors
                    if hint.risk_level == "high":
                        risk_badge = "\033[31m[HIGH]\033[0m"
                    elif hint.risk_level == "medium":
                        risk_badge = "\033[33m[MEDIUM]\033[0m"
                    else:
                        risk_badge = "\033[32m[LOW]\033[0m"
                    
                    # Usage badge
                    if hint.usage_kind == "admin":
                        usage_badge = "\033[35madmin\033[0m"
                    elif hint.usage_kind == "write":
                        usage_badge = "\033[33mwrite\033[0m"
                    else:
                        usage_badge = "\033[36mread\033[0m"
                    
                    # Title and location
                    title = hint.title or f"{hint.view_name}.{hint.route_name}"
                    path = hint.path or "N/A"
                    
                    click.echo(f"  {risk_badge} {title}")
                    click.echo(f"      Path: \033[90m{path}\033[0m")
                    click.echo(f"      View: \033[90m{hint.view_name}.{hint.route_name}\033[0m | Usage: {usage_badge}")
                    
                    if hint.description:
                        desc = hint.description[:80] + "..." if len(hint.description) > 80 else hint.description
                        click.echo(f"      Desc: \033[90m{desc}\033[0m")
                    
                    if hint.example_prompt:
                        click.echo(f"      Example: \033[90m\"{hint.example_prompt}\"\033[0m")
                    
                    click.echo()
        
    except Exception as e:
        click.echo(f"  \033[31m✗\033[0m Error: {e}", err=True)
        raise click.Abort()


@ai.command("examples")
@click.option("--provider", "-p", type=click.Choice(["openai", "azure", "anthropic"]), default=None, help="Show example for specific provider")
@click.option("--output-dir", "-o", default=None, help="Directory to copy example files to")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing files")
@click.option("--list", "-l", "list_only", is_flag=True, help="List available example files")
def ai_examples(provider: Optional[str], output_dir: Optional[str], force: bool, list_only: bool):
    """Show real-world AI provider wiring examples.
    
    v0.5.14: Demonstrates how to wire Aksara's AI contracts to popular
    LLM providers (OpenAI, Azure OpenAI, Anthropic) without adding
    hard dependencies to your project.
    
    Examples:
        aksara ai examples                    # Show overview
        aksara ai examples --provider openai  # Show OpenAI example
        aksara ai examples --list             # List available example files
        aksara ai examples -o ./ai_adapters   # Copy examples to folder
    
    The examples package includes:
        - settings.py     Environment-based provider configuration
        - adapters.py     Protocol-based LLM client adapters
        - prompting.py    Prompt building from AiRouteHint
        - views.py        End-to-end view examples
        - main.py         App wiring example
    """
    import os
    import shutil
    from pathlib import Path
    
    # Find the examples package
    try:
        import examples.ai_providers as ai_examples_pkg
        examples_path = Path(ai_examples_pkg.__file__).parent
    except ImportError:
        examples_path = None
    
    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m - AI Provider Wiring Examples (v0.5.14)")
    click.echo()
    
    # Define example files
    example_files = [
        ("settings.py", "Environment-based provider configuration"),
        ("adapters.py", "Protocol-based LLM client adapters with soft SDK imports"),
        ("prompting.py", "Prompt building utilities from AiRouteHint"),
        ("views.py", "End-to-end example views with @ai_route_hint"),
        ("main.py", "Complete app wiring example"),
        ("__init__.py", "Package exports"),
    ]
    
    if list_only:
        click.echo("  Available example files:")
        click.echo()
        for filename, desc in example_files:
            click.echo(f"    \033[36m{filename:15}\033[0m - {desc}")
        click.echo()
        
        if examples_path and examples_path.exists():
            click.echo(f"  Source: {examples_path}")
        else:
            click.echo("  \033[33mNote:\033[0m Examples package not found in current environment.")
            click.echo("        View examples at: https://github.com/nagarjuna-tella/Aksara/tree/main/examples/ai_providers")
        click.echo()
        return
    
    if output_dir:
        # Copy examples to output directory
        output_path = Path(output_dir).resolve()
        
        if not examples_path or not examples_path.exists():
            click.echo(f"  \033[31m✗\033[0m Examples package not found. Cannot copy files.")
            click.echo("    Install from source or download from GitHub.")
            raise click.Abort()
        
        click.echo(f"  Copying examples to: {output_path}")
        click.echo()
        
        output_path.mkdir(parents=True, exist_ok=True)
        
        copied = 0
        for filename, desc in example_files:
            src = examples_path / filename
            dst = output_path / filename
            
            if src.exists():
                if dst.exists() and not force:
                    click.echo(f"    \033[33m⚠\033[0m {filename} - already exists (use --force to overwrite)")
                else:
                    shutil.copy2(src, dst)
                    click.echo(f"    \033[32m✓\033[0m {filename}")
                    copied += 1
            else:
                click.echo(f"    \033[90m-\033[0m {filename} - not found in source")
        
        click.echo()
        click.echo(f"  Copied {copied} files.")
        click.echo()
        click.echo("  Next steps:")
        click.echo(f"    1. cd {output_dir}")
        click.echo("    2. Set environment variables (OPENAI_API_KEY, etc.)")
        click.echo("    3. pip install openai  (or anthropic)")
        click.echo("    4. Import adapters into your views")
        click.echo()
        return
    
    # Show overview
    click.echo("  The examples/ai_providers package demonstrates how to wire")
    click.echo("  Aksara's AI contracts to real LLM providers without adding")
    click.echo("  hard dependencies to your project.")
    click.echo()
    click.echo("  \033[1mKey Pattern:\033[0m Protocol-based adapters with soft SDK imports")
    click.echo()
    
    # Show provider-specific info if requested
    if provider:
        click.echo(f"  \033[1mProvider: {provider.upper()}\033[0m")
        click.echo()
        
        if provider == "openai":
            click.echo("  \033[36mEnvironment Variables:\033[0m")
            click.echo("    OPENAI_API_KEY=<OPENAI_API_KEY>")
            click.echo("    OPENAI_DEFAULT_MODEL=gpt-4o-mini  (optional)")
            click.echo("    OPENAI_ORG_ID=org-...            (optional)")
            click.echo()
            click.echo("  \033[36mInstall SDK:\033[0m")
            click.echo("    pip install openai")
            click.echo()
            click.echo("  \033[36mUsage:\033[0m")
            click.echo('    from your_adapters import get_llm_client')
            click.echo('    client = get_llm_client("openai", api_key=os.environ["OPENAI_API_KEY"])')
            click.echo('    response = await client.complete("Hello!", model=profile)')
            
        elif provider == "azure":
            click.echo("  \033[36mEnvironment Variables:\033[0m")
            click.echo("    AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/")
            click.echo("    AZURE_OPENAI_API_KEY=<AZURE_OPENAI_API_KEY>")
            click.echo("    AZURE_OPENAI_DEPLOYMENT=your-deployment-name")
            click.echo("    AZURE_OPENAI_API_VERSION=2024-02-01  (optional)")
            click.echo()
            click.echo("  \033[36mInstall SDK:\033[0m")
            click.echo("    pip install openai")
            click.echo()
            click.echo("  \033[36mUsage:\033[0m")
            click.echo('    from your_adapters import get_llm_client')
            click.echo('    client = get_llm_client("azure",')
            click.echo('        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],')
            click.echo('        api_key=os.environ["AZURE_OPENAI_API_KEY"],')
            click.echo('        deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"])')
            click.echo('    response = await client.complete("Hello!", model=profile)')
            
        elif provider == "anthropic":
            click.echo("  \033[36mEnvironment Variables:\033[0m")
            click.echo("    ANTHROPIC_API_KEY=<ANTHROPIC_API_KEY>")
            click.echo("    ANTHROPIC_DEFAULT_MODEL=claude-3-sonnet-20240229  (optional)")
            click.echo()
            click.echo("  \033[36mInstall SDK:\033[0m")
            click.echo("    pip install anthropic")
            click.echo()
            click.echo("  \033[36mUsage:\033[0m")
            click.echo('    from your_adapters import get_llm_client')
            click.echo('    client = get_llm_client("anthropic", api_key=os.environ["ANTHROPIC_API_KEY"])')
            click.echo('    response = await client.complete("Hello!", model=profile)')
        
        click.echo()
    else:
        click.echo("  \033[36mSupported Providers:\033[0m")
        click.echo("    - openai     OpenAI (GPT-4, GPT-3.5, etc.)")
        click.echo("    - azure      Azure OpenAI Service")
        click.echo("    - anthropic  Anthropic Claude")
        click.echo()
        click.echo("  \033[36mCommands:\033[0m")
        click.echo("    aksara ai examples --list             List example files")
        click.echo("    aksara ai examples --provider openai  Show OpenAI setup")
        click.echo("    aksara ai examples -o ./adapters      Copy to project")
        click.echo()
    
    click.echo("  \033[36mExample Files:\033[0m")
    for filename, desc in example_files[:3]:  # Show first 3
        click.echo(f"    {filename:15} - {desc}")
    click.echo("    ... use --list to see all")
    click.echo()
    
    click.echo("  \033[36mDocumentation:\033[0m")
    click.echo("    https://aksara.dev/ai-mode/bring-your-own-llm/")
    click.echo()


# =============================================================================
# v0.5.17: Doctor — Self-Diagnostics CLI
# =============================================================================


@cli.group()
def doctor():
    """Self-diagnostics and health checks.

    Runs comprehensive checks on your Aksara project including database
    connectivity, migrations, AI providers, settings, security, and more.

    v0.5.17: Doctor Mode
    """
    pass


def _render_launch_check_text(report) -> None:
    """Render launch-check output for humans."""
    from aksara.launch_check import CATEGORY_ORDER

    category_titles = {
        "environment": "Environment",
        "project": "Project",
        "database": "Database",
        "studio": "Studio",
        "ai": "AI",
        "examples": "Examples",
        "security": "Security",
    }
    symbols = {
        "ok": "\033[32m✓\033[0m",
        "warning": "\033[33m⚠\033[0m",
        "error": "\033[31m✗\033[0m",
        "skipped": "\033[90m-\033[0m",
    }

    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara Launch Check\033[0m")
    click.echo()

    grouped = {}
    for check in report.checks:
        grouped.setdefault(check.category, []).append(check)

    for category in CATEGORY_ORDER:
        checks = grouped.get(category)
        if not checks:
            continue
        click.echo(f"  \033[1m{category_titles.get(category, category.title())}\033[0m")
        for check in checks:
            click.echo(f"    {symbols.get(check.status, '-')} {check.message}")
            if check.hint:
                click.echo(f"      \033[90mNext: {check.hint}\033[0m")
        click.echo()

    click.echo("  \033[1mResult\033[0m")
    click.echo(f"    Launch readiness: {report.status.upper()}")
    if report.next_steps:
        click.echo()
        click.echo("  \033[1mNext steps\033[0m")
        for index, step in enumerate(report.next_steps, start=1):
            click.echo(f"    {index}. {step}")
    click.echo()


@doctor.command("launch-check")
@click.option("--format", "-f", "output_format", type=click.Choice(["pretty", "json"]), default="pretty", help="Output format")
def doctor_launch_check(output_format: str):
    """Check whether this project is ready for a first local launch."""
    from aksara.launch_check import run_launch_check

    report = run_launch_check()
    if output_format == "json":
        click.echo(report.to_json(indent=2))
    else:
        _render_launch_check_text(report)
    raise click.exceptions.Exit(report.exit_code)


@doctor.command("run")
@click.option("--format", "-f", "output_format", type=click.Choice(["pretty", "json"]), default="pretty", help="Output format")
def doctor_run(output_format: str):
    """Run all diagnostic checks.

    Performs a comprehensive health check of your Aksara project.
    Exit code 0 = all clear, exit code 1 = errors found.

    Examples:
        aksara doctor run
        aksara doctor run --format json
    """
    import json as json_mod

    async def _run():
        from aksara.diagnostics import run_all_checks
        return await run_all_checks()

    try:
        report = asyncio.run(_run())
    except Exception as e:
        click.echo(f"❌ Diagnostics failed: {e}", err=True)
        click.echo("   Try: check your DATABASE_URL or run aksara doctor db", err=True)
        sys.exit(1)

    if output_format == "json":
        click.echo(report.model_dump_json(indent=2))
    else:
        click.echo()
        click.echo("  \033[33m⚡\033[0m \033[1mAksara Doctor\033[0m — Self-Diagnostics")
        click.echo()

        # Summary
        status = report.overall_status
        status_colors = {"ok": "\033[32m", "warning": "\033[33m", "error": "\033[31m"}
        status_labels = {"ok": "ALL CLEAR", "warning": "WARNINGS", "error": "ERRORS FOUND"}
        c = status_colors.get(status, "\033[0m")
        click.echo(f"  Status: {c}{status_labels.get(status, status)}\033[0m")
        click.echo(f"  Errors: {report.stats.get('errors', 0)}  Warnings: {report.stats.get('warnings', 0)}  Info: {report.stats.get('info', 0)}")
        click.echo(f"  Duration: {report.duration_ms:.0f} ms")
        click.echo()

        if report.system:
            s = report.system
            click.echo(f"  System: Aksara {s.get('aksara_version', '?')} · Python {s.get('python_version', '?')} · {s.get('os', '?')}")
            click.echo()

        # Issues
        severity_symbols = {"error": "\033[31m✗\033[0m", "warning": "\033[33m!\033[0m", "info": "\033[36m·\033[0m"}
        for issue in report.issues:
            sym = severity_symbols.get(issue.severity, "·")
            click.echo(f"  {sym} [{issue.severity.upper():7s}] {issue.title}")
            click.echo(f"            {issue.message}")
            if issue.hint:
                click.echo(f"            \033[90mHint: {issue.hint}\033[0m")
            if issue.actions:
                for action in issue.actions:
                    kind_sym = {"set_env": "ENV", "run_command": "CMD", "open_doc": "DOC", "edit_file": "FILE", "add_setting": "CFG"}.get(action.kind, action.kind.upper())
                    click.echo(f"            \033[36m→ [{kind_sym}]\033[0m {action.title}")
                    if action.example:
                        click.echo(f"              \033[90m$ {action.example}\033[0m")
            click.echo()

        if not report.issues:
            click.echo("  \033[32mNo issues found — everything looks good!\033[0m")
            click.echo()

    sys.exit(1 if report.has_errors else 0)


@doctor.command("summary")
def doctor_summary():
    """Show categorized issue counts.

    Quick overview of how many issues exist per category.

    Example:
        aksara doctor summary
    """

    async def _run():
        from aksara.diagnostics import run_all_checks
        return await run_all_checks()

    report = asyncio.run(_run())

    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara Doctor Summary\033[0m")
    click.echo()

    # Group by kind
    by_kind = {}
    for issue in report.issues:
        kind = issue.kind
        by_kind.setdefault(kind, {"error": 0, "warning": 0, "info": 0})
        by_kind[kind][issue.severity] += 1

    if not by_kind:
        click.echo("  \033[32mNo issues found — everything looks good!\033[0m")
    else:
        click.echo(f"  {'Category':<30s} {'Errors':>7s} {'Warns':>7s} {'Info':>7s}")
        click.echo(f"  {'─' * 30} {'─' * 7} {'─' * 7} {'─' * 7}")
        for kind, counts in sorted(by_kind.items()):
            label = kind.replace("_", " ").title()
            e = counts["error"]
            w = counts["warning"]
            i = counts["info"]
            ec = f"\033[31m{e}\033[0m" if e else str(e)
            wc = f"\033[33m{w}\033[0m" if w else str(w)
            click.echo(f"  {label:<30s} {ec:>16s} {wc:>16s} {i:>7d}")

    click.echo()
    click.echo(f"  Total: {report.stats.get('errors', 0)} errors, {report.stats.get('warnings', 0)} warnings, {report.stats.get('info', 0)} info")
    click.echo(f"  Duration: {report.duration_ms:.0f} ms")
    click.echo()


@doctor.command("ai")
def doctor_ai():
    """Run AI-specific diagnostic checks.

    Checks AI profiles, provider secrets, and configuration.

    Example:
        aksara doctor ai
    """

    async def _run():
        from aksara.diagnostics import check_ai_profiles, check_ai_provider_secrets, check_ai_hub_config
        issues = []
        issues.extend(await check_ai_profiles())
        issues.extend(await check_ai_provider_secrets())
        issues.extend(await check_ai_hub_config())
        return issues

    issues = asyncio.run(_run())

    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara Doctor — AI Checks\033[0m")
    click.echo()

    severity_symbols = {"error": "\033[31m✗\033[0m", "warning": "\033[33m!\033[0m", "info": "\033[36m·\033[0m"}
    for issue in issues:
        sym = severity_symbols.get(issue.severity, "·")
        click.echo(f"  {sym} [{issue.severity.upper():7s}] {issue.title}")
        click.echo(f"            {issue.message}")
        if issue.hint:
            click.echo(f"            \033[90mHint: {issue.hint}\033[0m")
        click.echo()

    if not issues:
        click.echo("  \033[32mNo AI issues found.\033[0m")
    click.echo()


@doctor.command("db")
def doctor_db():
    """Run database-specific diagnostic checks.

    Checks database connectivity, migrations, and schema.

    Example:
        aksara doctor db
    """

    async def _run():
        from aksara.diagnostics import check_database_connectivity, check_migrations_status
        issues = []
        issues.extend(await check_database_connectivity())
        issues.extend(await check_migrations_status())
        return issues

    issues = asyncio.run(_run())

    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara Doctor — Database Checks\033[0m")
    click.echo()

    severity_symbols = {"error": "\033[31m✗\033[0m", "warning": "\033[33m!\033[0m", "info": "\033[36m·\033[0m"}
    for issue in issues:
        sym = severity_symbols.get(issue.severity, "·")
        click.echo(f"  {sym} [{issue.severity.upper():7s}] {issue.title}")
        click.echo(f"            {issue.message}")
        if issue.hint:
            click.echo(f"            \033[90mHint: {issue.hint}\033[0m")
        click.echo()

    if not issues:
        click.echo("  \033[32mNo database issues found.\033[0m")
    click.echo()


@doctor.command("fix-plan")
@click.option("--format", "-f", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format")
@click.option("--only-errors", is_flag=True, default=False, help="Only show error-severity issues")
@click.option("--only-with-actions", is_flag=True, default=False, help="Only show issues that have fix actions")
def doctor_fix_plan(output_format: str, only_errors: bool, only_with_actions: bool):
    """Generate a remediation fix-plan from diagnostics.

    Shows every issue with its machine-readable fix actions. Useful for
    scripting, automation, and AI agents.

    v0.5.18: Autoremediation Hints

    Examples:
        aksara doctor fix-plan
        aksara doctor fix-plan --format json
        aksara doctor fix-plan --only-errors
        aksara doctor fix-plan --only-with-actions
    """
    import json as json_mod

    async def _run():
        from aksara.diagnostics import run_all_checks
        return await run_all_checks()

    report = asyncio.run(_run())

    # Filter issues
    issues = list(report.issues)
    if only_errors:
        issues = [i for i in issues if i.severity == "error"]
    if only_with_actions:
        issues = [i for i in issues if i.actions]

    if output_format == "json":
        data = {
            "issues": [i.model_dump() for i in issues],
            "stats": report.stats,
            "duration_ms": report.duration_ms,
            "system": report.system,
        }
        click.echo(json_mod.dumps(data, indent=2, default=str))
    else:
        click.echo()
        click.echo("  \033[33m⚡\033[0m \033[1mAksara Doctor — Fix Plan\033[0m")
        click.echo()

        if not issues:
            filters = []
            if only_errors:
                filters.append("--only-errors")
            if only_with_actions:
                filters.append("--only-with-actions")
            filter_note = f" (filters: {', '.join(filters)})" if filters else ""
            click.echo(f"  \033[32mNo issues to fix{filter_note}.\033[0m")
            click.echo()
            sys.exit(0)

        kind_sym = {
            "set_env": "ENV", "run_command": "CMD", "open_doc": "DOC",
            "edit_file": "FILE", "add_setting": "CFG",
        }
        severity_symbols = {"error": "\033[31m✗\033[0m", "warning": "\033[33m!\033[0m", "info": "\033[36m·\033[0m"}

        for idx, issue in enumerate(issues, 1):
            sym = severity_symbols.get(issue.severity, "·")
            click.echo(f"  {sym} {idx}. [{issue.severity.upper()}] {issue.title}")
            click.echo(f"     {issue.message}")
            if issue.hint:
                click.echo(f"     \033[90mHint: {issue.hint}\033[0m")
            if issue.actions:
                click.echo(f"     \033[1mActions:\033[0m")
                for action in issue.actions:
                    ks = kind_sym.get(action.kind, action.kind.upper())
                    click.echo(f"       \033[36m→ [{ks}]\033[0m {action.title}")
                    if action.example:
                        click.echo(f"         \033[90m$ {action.example}\033[0m")
            else:
                click.echo(f"     \033[90m(no fix actions available)\033[0m")
            click.echo()

        total_actions = sum(len(i.actions) for i in issues)
        click.echo(f"  {len(issues)} issue(s), {total_actions} fix action(s)")
        click.echo()

    sys.exit(1 if any(i.severity == "error" for i in issues) else 0)


# =============================================================================
# Security Baseline Commands
# =============================================================================


def _render_security_check_text(report, command_name: str = "security-check") -> None:
    """Render security check output for humans."""
    status_colors = {
        "pass": "\033[32m",
        "warn": "\033[33m",
        "fail": "\033[31m",
        "block": "\033[31m",
        "skip": "\033[90m",
        "unknown": "\033[90m",
    }
    status_labels = {
        "pass": "PASS",
        "warn": "WARN",
        "fail": "FAIL",
        "block": "BLOCK",
        "skip": "SKIP",
        "unknown": "UNKNOWN",
    }

    click.echo()
    if report.release_candidate:
        cmd_label = "Release Candidate Check"
    else:
        cmd_label = "Production Check" if report.is_production else "Security Check"
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara Doctor — {cmd_label}\033[0m")
    click.echo()

    for result in report.results:
        c = status_colors.get(result.status, "\033[0m")
        label = status_labels.get(result.status, result.status.upper())
        click.echo(f"  {c}[{label:7s}]\033[0m {result.title}")
        click.echo(f"           {result.message}")
        if result.recommendation:
            click.echo(f"           \033[90mFix: {result.recommendation}\033[0m")

    click.echo()
    overall = report.overall_status
    overall_c = status_colors.get(overall, "\033[0m")
    overall_label = status_labels.get(overall, overall.upper())
    click.echo(f"  Overall: {overall_c}{overall_label}\033[0m")

    blocks = sum(1 for r in report.results if r.status == "block")
    fails = sum(1 for r in report.results if r.status == "fail")
    warns = sum(1 for r in report.results if r.status == "warn")
    passes = sum(1 for r in report.results if r.status == "pass")
    click.echo(f"  Blocks: {blocks}  Failures: {fails}  Warnings: {warns}  Pass: {passes}")
    click.echo()

    if report.is_production and report.has_blocks:
        click.echo("  \033[31m⛔  Blocking issues found. Fix these before production deployment.\033[0m")
        click.echo()
    elif report.release_candidate and report.should_exit_nonzero:
        click.echo("  \033[31m⛔  Release candidates require every check to pass.\033[0m")
        click.echo()


@doctor.command("security-check")
@click.option("--format", "-f", "output_format", type=click.Choice(["pretty", "json"]), default="pretty", help="Output format")
def doctor_security_check(output_format: str):
    """Run security posture diagnostics for the current Aksara project.

    Reports on security configuration, unsafe defaults, missing settings,
    and validates the security matrix. Useful in development and CI.

    Does NOT enforce blocking exit codes for all issues — use
    production-check for stricter enforcement.

    Examples:
        aksara doctor security-check
        aksara doctor security-check --format json
    """
    import json as json_mod
    from aksara.security.checks import run_security_checks

    report = run_security_checks(is_production=False)

    if output_format == "json":
        data = {
            "check": "security-check",
            "status": report.overall_status,
            "results": [
                {
                    "id": r.id,
                    "title": r.title,
                    "severity": r.severity,
                    "status": r.status,
                    "message": r.message,
                    "recommendation": r.recommendation,
                }
                for r in report.results
            ],
            "summary": {
                "blocks": sum(1 for r in report.results if r.status == "block"),
                "failures": sum(1 for r in report.results if r.status == "fail"),
                "warnings": sum(1 for r in report.results if r.status == "warn"),
                "passes": sum(1 for r in report.results if r.status == "pass"),
            },
        }
        click.echo(json_mod.dumps(data, indent=2))
    else:
        _render_security_check_text(report, "security-check")

    sys.exit(1 if report.should_exit_nonzero else 0)


@doctor.command("production-check")
@click.option("--format", "-f", "output_format", type=click.Choice(["pretty", "json"]), default="pretty", help="Output format")
@click.option(
    "--release",
    "release_candidate",
    is_flag=True,
    help="Require a valid security matrix and fail on warnings, skips, or unknown results.",
)
def doctor_production_check(output_format: str, release_candidate: bool):
    """Run strict production-readiness security diagnostics.

    Checks for unsafe settings that MUST be fixed before production
    deployment. Exits with code 1 when any blocking issue is found. With
    --release, every check must pass and a valid security matrix is required.

    Blocking conditions include:
      - DEBUG=True
      - Missing or weak SECRET_KEY
      - CORS wildcard with credentials
      - Studio exposed without auth
      - MCP enabled without auth
      - Missing or invalid security_matrix.yml

    Examples:
        aksara doctor production-check
        aksara doctor production-check --format json
        aksara doctor production-check --release --format json
    """
    import json as json_mod
    from aksara.security.checks import run_security_checks

    report = run_security_checks(
        is_production=True,
        release_candidate=release_candidate,
    )

    if output_format == "json":
        data = {
            "check": "production-check",
            "policy": "release-candidate" if release_candidate else "deployment",
            "status": report.overall_status,
            "results": [
                {
                    "id": r.id,
                    "title": r.title,
                    "severity": r.severity,
                    "status": r.status,
                    "message": r.message,
                    "recommendation": r.recommendation,
                }
                for r in report.results
            ],
            "summary": {
                "blocks": sum(1 for r in report.results if r.status == "block"),
                "failures": sum(1 for r in report.results if r.status == "fail"),
                "warnings": sum(1 for r in report.results if r.status == "warn"),
                "passes": sum(1 for r in report.results if r.status == "pass"),
            },
            "exit_code": 1 if report.should_exit_nonzero else 0,
            "release_ready": (
                not report.should_exit_nonzero if release_candidate else None
            ),
        }
        click.echo(json_mod.dumps(data, indent=2))
    else:
        _render_security_check_text(report, "production-check")

    sys.exit(1 if report.should_exit_nonzero else 0)


# =============================================================================
# v0.5.19: Agent Mode CLI
# =============================================================================


@cli.group()
def agent():
    """Agent context and prompt generation.

    Gather project context and build LLM-ready system prompts for
    AI agents working with your Aksara application.

    v0.5.19: Agent Mode
    """
    pass


@agent.command("context")
@click.option("--sections", "-s", default="", help="Comma-separated section keys to include (empty = all)")
@click.option("--output", "-o", type=click.Choice(["json", "pretty"]), default="pretty", help="Output format")
@click.option("--summary", is_flag=True, default=False, help="Show only section titles and sizes")
@click.option("--size", is_flag=True, default=False, help="Show total size in KB")
def agent_context(sections: str, output: str, summary: bool, size: bool):
    """Gather project context for an LLM agent.

    Collects project info, models, routes, migrations, diagnostics,
    AI profiles, AI hints, DB queries, and schema checksum.
    """
    import asyncio
    import json as json_mod
    from unittest.mock import MagicMock

    app = MagicMock()
    app_module = getattr(_get_settings(), "app_module", None)
    if app_module:
        try:
            from aksara.apps import Aksara
            real_app = Aksara.instance
            if real_app:
                app = real_app
        except Exception:
            pass

    try:
        ctx = asyncio.run(_run_agent_context(app))
    except Exception as e:
        click.echo(f"  \033[31m✗ Error gathering context: {e}\033[0m")
        sys.exit(1)

    # Filter sections if requested
    if sections:
        keys = [k.strip() for k in sections.split(",") if k.strip()]
        ctx_sections = [s for s in ctx.sections if s.key in keys]
    else:
        ctx_sections = ctx.sections

    if size:
        total = sum(s.size_kb for s in ctx_sections)
        click.echo(f"  Total size: {total:.2f} KB ({len(ctx_sections)} section(s))")
        return

    if summary:
        click.echo(f"  Agent Context — {len(ctx_sections)} section(s)")
        click.echo()
        for s in ctx_sections:
            click.echo(f"  • {s.title} ({s.key}) — {s.size_kb:.2f} KB")
        click.echo()
        total = sum(s.size_kb for s in ctx_sections)
        click.echo(f"  Total: {total:.2f} KB")
        return

    if output == "json":
        data = ctx.model_dump(mode="json")
        if sections:
            keys = [k.strip() for k in sections.split(",") if k.strip()]
            data["sections"] = [s for s in data["sections"] if s["key"] in keys]
            data["total_sections"] = len(data["sections"])
        click.echo(json_mod.dumps(data, indent=2, default=str))
    else:
        click.echo(f"  Agent Context — {len(ctx_sections)} section(s)")
        click.echo()
        for s in ctx_sections:
            click.echo(f"  \033[1m{s.title}\033[0m ({s.key}) — {s.size_kb:.2f} KB")
            click.echo(f"  {s.description}")
            click.echo()


@agent.command("prompt")
@click.option("--goal", "-g", required=True, help="What the agent should accomplish")
@click.option("--sections", "-s", default="", help="Comma-separated section keys (empty = all)")
@click.option("--custom-system-prompt", "-c", default=None, help="Custom prefix for the system prompt")
@click.option("--format", "-f", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def agent_prompt(goal: str, sections: str, custom_system_prompt: str | None, output_format: str):
    """Generate an LLM system prompt from project context.

    Requires --goal to specify the agent's task.
    """
    import asyncio
    import json as json_mod
    from unittest.mock import MagicMock

    from aksara.studio.models import StudioAgentPromptRequest
    from aksara.studio.utils import build_agent_prompt as _build_prompt

    app = MagicMock()
    app_module = getattr(_get_settings(), "app_module", None)
    if app_module:
        try:
            from aksara.apps import Aksara
            real_app = Aksara.instance
            if real_app:
                app = real_app
        except Exception:
            pass

    try:
        ctx = asyncio.run(_run_agent_context(app))
    except Exception as e:
        click.echo(f"  \033[31m✗ Error gathering context: {e}\033[0m")
        sys.exit(1)

    selected = [k.strip() for k in sections.split(",") if k.strip()] if sections else []

    req = StudioAgentPromptRequest(
        selected_sections=selected,
        custom_system_prompt=custom_system_prompt,
        goal=goal,
    )

    result = _build_prompt(req, ctx)

    if output_format == "json":
        click.echo(json_mod.dumps(result.model_dump(), indent=2, default=str))
    else:
        click.echo(result.system_prompt)
        click.echo()
        click.echo(f"  \033[90mModel: {result.recommended_model}  |  "
                    f"Temp: {result.recommended_temperature}  |  "
                    f"~{result.tokens_estimate} tokens\033[0m")


async def _run_agent_context(app):
    """Run build_agent_context in async context."""
    from aksara.studio.utils import build_agent_context
    return await build_agent_context(app)


# =============================================================================
# v0.5.20: Agent Playbooks CLI
# =============================================================================


@agent.command("playbooks")
@click.option("--format", "-f", "output_format", type=click.Choice(["pretty", "json"]), default="pretty", help="Output format")
@click.option("--category", "-c", default=None, help="Filter by category (schema, api, migrations, diagnostics)")
@click.option("--risk", "-r", default=None, help="Filter by risk level (low, medium, high)")
@click.option("--usage", "-u", default=None, help="Filter by usage kind (read_only, write, admin)")
def agent_playbooks(output_format: str, category: str | None, risk: str | None, usage: str | None):
    """List available agent playbooks.

    Shows built-in playbook recipes for common LLM-assisted tasks.
    Use --category, --risk, or --usage to filter.
    """
    import json as json_mod
    from aksara.ai.playbooks import get_builtin_playbooks

    result = get_builtin_playbooks(category=category, risk_level=risk, usage_kind=usage)

    if output_format == "json":
        click.echo(json_mod.dumps(result.model_dump(mode="json"), indent=2, default=str))
    else:
        click.echo(f"  Agent Playbooks — {result.total_count} playbook(s)")
        click.echo()
        for pb in result.playbooks:
            risk_color = {"low": "32", "medium": "33", "high": "31"}.get(pb.risk_level, "0")
            click.echo(f"  \033[1m{pb.label}\033[0m  [{pb.key}]")
            click.echo(f"  {pb.description}")
            click.echo(f"  Category: {pb.category}  |  "
                        f"Risk: \033[{risk_color}m{pb.risk_level}\033[0m  |  "
                        f"Usage: {pb.usage_kind}  |  "
                        f"Steps: {len(pb.steps)}")
            click.echo()

        if result.by_category:
            cats = ", ".join(f"{k}: {v}" for k, v in sorted(result.by_category.items()))
            click.echo(f"  Categories: {cats}")


@agent.command("playbook-run")
@click.argument("key")
@click.option("--goal", "-g", default=None, help="Override the playbook's default goal template")
@click.option("--sections", "-s", default="", help="Comma-separated section keys (empty = playbook defaults)")
@click.option("--format", "-f", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def agent_playbook_run(key: str, goal: str | None, sections: str, output_format: str):
    """Run a playbook to generate an LLM system prompt.

    KEY is the playbook key (e.g. add_field_to_model).
    Use `aksara agent playbooks` to list available keys.
    """
    import asyncio
    import json as json_mod
    from unittest.mock import MagicMock
    from aksara.ai.playbooks import get_playbook_by_key
    from aksara.studio.utils import build_agent_prompt_from_playbook

    playbook = get_playbook_by_key(key)
    if playbook is None:
        click.echo(f"  \033[31m✗ Playbook not found: {key}\033[0m")
        click.echo("  Run `aksara agent playbooks` to see available playbooks.")
        sys.exit(1)

    app = MagicMock()
    app_module = getattr(_get_settings(), "app_module", None)
    if app_module:
        try:
            from aksara.apps import Aksara
            real_app = Aksara.instance
            if real_app:
                app = real_app
        except Exception:
            pass

    try:
        ctx = asyncio.run(_run_agent_context(app))
    except Exception as e:
        click.echo(f"  \033[31m✗ Error gathering context: {e}\033[0m")
        sys.exit(1)

    selected = [k.strip() for k in sections.split(",") if k.strip()] if sections else None

    result = build_agent_prompt_from_playbook(
        playbook=playbook,
        user_goal=goal,
        selected_sections=selected,
        custom_system_prompt=None,
        context=ctx,
    )

    if output_format == "json":
        click.echo(json_mod.dumps(result.model_dump(), indent=2, default=str))
    else:
        click.echo(result.system_prompt)
        click.echo()
        click.echo(f"  \033[90mPlaybook: {playbook.label}  |  "
                    f"Model: {result.recommended_model}  |  "
                    f"Temp: {result.recommended_temperature}  |  "
                    f"~{result.tokens_estimate} tokens\033[0m")


def _get_settings():
    """Get Aksara settings with fallback."""
    try:
        from aksara.conf import settings
        return settings
    except Exception:
        from unittest.mock import MagicMock
        return MagicMock()


# =============================================================================
# v0.5.23: Agent Workflow Command
# =============================================================================


@agent.command("workflow")
@click.argument("goal")
@click.option("--playbook", "-p", default=None, help="Playbook key to guide the workflow")
@click.option("--no-diagnostics", is_flag=True, default=False, help="Skip diagnostics")
@click.option("--no-search", is_flag=True, default=False, help="Skip semantic search")
@click.option("--search-query", default=None, help="Custom search query (defaults to goal)")
@click.option("--limit-search", default=10, type=int, help="Max search results")
@click.option("--limit-diagnostics", default=10, type=int, help="Max diagnostic issues")
@click.option("--format", "-f", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def agent_workflow(
    goal: str,
    playbook: str | None,
    no_diagnostics: bool,
    no_search: bool,
    search_query: str | None,
    limit_search: int,
    limit_diagnostics: int,
    output_format: str,
):
    """Generate a structured workflow plan for a goal.

    GOAL is the task you want to accomplish (e.g. "Fix slow queries on /api/posts/").

    The workflow combines diagnostics, inspectors, semantic search, and playbooks
    into an ordered list of actionable steps.  Nothing is auto-applied — all
    commands are for display and human review.

    v0.5.23: Agentic Workflows — Plans, Not Pushes
    """
    import json as json_mod
    from aksara.ai.workflows import (
        build_agent_workflow,
        summarize_agent_workflow,
        workflow_stats,
    )
    from aksara.studio.models import AgentWorkflowResponse

    try:
        workflow = build_agent_workflow(
            goal=goal,
            playbook=playbook,
            include_diagnostics=not no_diagnostics,
            include_search=not no_search,
            search_query=search_query,
            search_limit=limit_search,
            diagnostics_limit=limit_diagnostics,
        )
    except Exception as e:
        click.echo(f"❌ Failed to build workflow: {e}", err=True)
        click.echo("   Try: aksara doctor run", err=True)
        sys.exit(1)

    if output_format == "json":
        response = AgentWorkflowResponse(
            workflow=workflow,
            summary=summarize_agent_workflow(workflow),
            stats=workflow_stats(workflow),
        )
        click.echo(json_mod.dumps(response.model_dump(), indent=2, default=str))
        return

    # Text format — rich outline
    click.echo()
    click.echo(f"  🎯 Goal: {goal}")
    if workflow.playbook:
        click.echo(f"  📋 Playbook: {workflow.playbook}")
    click.echo(f"  📊 Source: {workflow.source} | Steps: {len(workflow.steps)}")
    click.echo()

    for step in workflow.steps:
        risk_str = step.risk or "—"
        click.echo(
            f"  {step.order}. [{step.kind}, {risk_str} risk] {step.title}"
        )
        if step.description:
            click.echo(f"     {step.description[:120]}")
        for cmd in step.commands:
            click.echo(f"     \033[36m$ {cmd}\033[0m")
        for note in step.notes:
            click.echo(f"     \033[90m• {note}\033[0m")
        click.echo()

    summary = summarize_agent_workflow(workflow)
    click.echo(f"  \033[90m{summary}\033[0m")
    click.echo()


# =============================================================================
# v0.5.21: Inspect Commands
# =============================================================================


@cli.group()
def inspect():
    """Model and query inspection tools.

    Deep introspection for schema analysis, query profiling, and
    diagnostics.  Pipe JSON output to agent mode for AI analysis.

    v0.5.21: Query & Model Inspector
    """
    pass


@inspect.command("models")
@click.option("--model", "-m", default=None, help="Inspect a single model by name")
@click.option("--fields", is_flag=True, help="Show field details")
@click.option("--relationships", is_flag=True, help="Show relationship details")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def inspect_models(model: Optional[str], fields: bool, relationships: bool, as_json: bool):
    """Inspect registered models.

    Shows model metadata including fields, relationships, constraints,
    timestamps, primary keys, and auto-generated comments.

    Examples:
        aksara inspect models
        aksara inspect models --model User
        aksara inspect models --fields --relationships
        aksara inspect models --json
        aksara inspect models --json | aksara agent prompt -g "Review schema"
    """
    import json as json_mod
    from aksara.inspectors.models import inspect_model as _inspect, inspect_all_models

    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara\033[0m — Model Inspector")
    click.echo()

    if model:
        # Single model inspection
        from aksara.registry import AmbiguousModelError, ModelRegistry
        try:
            model_cls = ModelRegistry.get(model)
        except AmbiguousModelError as exc:
            click.echo(f"  \033[31m✗\033[0m {exc}")
            sys.exit(1)
        except KeyError:
            click.echo(f"  \033[31m✗\033[0m Model not found: {model}")
            click.echo()
            available = sorted(ModelRegistry.all().keys())
            if available:
                click.echo(f"  Available models: {', '.join(available)}")
            sys.exit(1)

        result = _inspect(model_cls)
        results = [result]
    else:
        results = inspect_all_models()

    if not results:
        click.echo("  No models registered.")
        click.echo()
        return

    if as_json:
        data = [r.model_dump(mode="json") for r in results]
        if model:
            click.echo(json_mod.dumps(data[0], indent=2, default=str))
        else:
            click.echo(json_mod.dumps(data, indent=2, default=str))
        return

    for r in results:
        click.echo(f"  \033[1m{r.name}\033[0m  ({r.table_name})")
        if r.app_label:
            click.echo(f"  App: {r.app_label}")
        click.echo(f"  Fields: {r.num_fields}  |  Relations: {r.num_relationships}  |  "
                    f"Timestamps: {'✓' if r.has_timestamps else '✗'}  |  "
                    f"PK: {r.pk_field or 'none'} ({r.pk_type})")

        if r.comments:
            for c in r.comments:
                click.echo(f"  {c}")

        if fields or model:
            click.echo()
            click.echo(f"  \033[1mFields:\033[0m")
            for f in r.fields:
                flags = []
                if f.primary_key:
                    flags.append("PK")
                if f.unique:
                    flags.append("UQ")
                if f.nullable:
                    flags.append("NULL")
                if f.ai_sensitive:
                    flags.append("⚠️SENSITIVE")
                flag_str = f" [{', '.join(flags)}]" if flags else ""
                default_str = f" = {f.default_repr}" if f.has_default else ""
                click.echo(f"    {f.name}: {f.field_type} ({f.python_type}){flag_str}{default_str}")

        if relationships or model:
            if r.relationships:
                click.echo()
                click.echo(f"  \033[1mRelationships:\033[0m")
                for rel in r.relationships:
                    extra = ""
                    if rel.through_table:
                        extra = f" via {rel.through_table}"
                    click.echo(f"    {rel.field_name} → {rel.target_model} ({rel.kind.upper()}, {rel.on_delete}){extra}")

        click.echo()

    click.echo(f"  Total: {len(results)} model(s)")
    click.echo()


@inspect.command("queries")
@click.option("--limit", "-n", default=10, help="Number of slow queries to show")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def inspect_queries(limit: int, as_json: bool):
    """Inspect query statistics and slow queries.

    Shows aggregate query stats, slow queries, and N+1 detections
    from the trace storage.

    Examples:
        aksara inspect queries
        aksara inspect queries --limit 5
        aksara inspect queries --json
        aksara inspect queries --json | aksara agent prompt -g "Optimize queries"
    """
    import json as json_mod

    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara\033[0m — Query Inspector")
    click.echo()

    try:
        from aksara.inspectors.queries import get_query_stats
        stats = get_query_stats(limit_slow=limit)
    except Exception as exc:
        click.echo(f"  \033[31m✗\033[0m Failed to load query data: {exc}", err=True)
        click.echo()
        click.echo("  Pro tip: Ensure DATABASE_URL is set and db tracing is enabled.")
        click.echo("           Run `aksara doctor db` for a detailed check.")
        click.echo()
        sys.exit(1)

    if as_json:
        click.echo(json_mod.dumps(stats.model_dump(mode="json"), indent=2, default=str))
        return

    click.echo(f"  \033[1mAggregate Statistics:\033[0m")
    click.echo(f"    Total queries:      {stats.total_queries}")
    click.echo(f"    Total batches:      {stats.total_batches}")
    click.echo(f"    Slow queries:       {stats.total_slow_queries}")
    click.echo(f"    Avg duration:       {stats.avg_duration_ms:.2f}ms")
    click.echo(f"    Max duration:       {stats.max_duration_ms:.2f}ms")
    click.echo(f"    Slow threshold:     {stats.slow_threshold_ms}ms")
    click.echo(f"    N+1 suspicions:     {stats.n_plus_one_count}")
    click.echo()

    if stats.by_operation:
        click.echo(f"  \033[1mBy Operation:\033[0m")
        for op, count in sorted(stats.by_operation.items()):
            click.echo(f"    {op}: {count}")
        click.echo()

    if stats.top_slow:
        click.echo(f"  \033[1mTop Slow Queries:\033[0m")
        for i, sq in enumerate(stats.top_slow, 1):
            sql_preview = sq["sql"][:80] + "..." if len(sq["sql"]) > 80 else sq["sql"]
            click.echo(f"    {i}. [{sq['duration_ms']:.2f}ms] {sq.get('operation', '?')} on "
                        f"{sq.get('table', 'unknown')}")
            click.echo(f"       {sql_preview}")
        click.echo()

    if stats.total_queries == 0:
        click.echo("  No query data. Enable tracing: AKSARA_DB_TRACE_ENABLED=true")
        click.echo()


# =============================================================================
# v0.5.22: Search Commands
# =============================================================================


@cli.group()
def search():
    """Semantic search across your project.

    Search models, routes, settings, playbooks, migrations, and queries.
    Supports keyword, semantic (TF-IDF), and hybrid search modes.

    v0.5.22: Semantic Search & AI Index
    """
    pass


@search.command("query")
@click.argument("query_text")
@click.option("--kind", "-k", default=None, help="Filter by kind (model, route, setting, playbook, migration, query)")
@click.option("--top", "-n", default=10, type=int, help="Max results (default 10)")
@click.option("--semantic", "-s", is_flag=True, help="Use semantic search mode (TF-IDF)")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON (pipe to agent mode)")
@click.option("--min-score", default=0.0, type=float, help="Minimum score threshold (0.0-1.0)")
def search_query(query_text: str, kind: str, top: int, semantic: bool, json_out: bool, min_score: float):
    """Search across project models, routes, settings, and more.

    Examples:

      aksara search query "User model"

      aksara search query "auth" --kind route --semantic

      aksara search query "database" --json | aksara agent
    """
    import json as json_mod

    from aksara.search.engine import SearchIndex
    from aksara.search.indexers import build_full_index

    mode = "semantic" if semantic else "hybrid"
    kind_filter = kind if kind else None

    try:
        index = build_full_index()
        results = index.search(
            query_text,
            top_k=top,
            kind=kind_filter,
            min_score=min_score,
            mode=mode,
        )
    except Exception as e:
        click.echo(f"❌ Search failed: {e}", err=True)
        click.echo("   Try: aksara search index --json", err=True)
        sys.exit(1)

    if json_out:
        output = {
            "query": query_text,
            "mode": mode,
            "total_results": len(results),
            "results": [r.to_dict() for r in results],
        }
        click.echo(json_mod.dumps(output, indent=2, default=str))
        return

    if not results:
        click.echo(f"  No results for: {query_text}")
        click.echo()
        return

    click.echo(f"\n  Search: \"{query_text}\" ({mode} mode)")
    click.echo(f"  Found {len(results)} results\n")

    for i, r in enumerate(results, 1):
        score_pct = f"{r.score * 100:.0f}%"
        click.echo(f"  {i}. [{r.document.kind.upper():10s}] {r.document.title}")
        click.echo(f"     Score: {score_pct}  |  {r.match_type}  |  {r.document.source}")
        if r.document.summary:
            click.echo(f"     {r.document.summary[:100]}")
        if r.highlights:
            for hl in r.highlights[:2]:
                click.echo(f"     > {hl[:100]}")
        click.echo()


@search.command("index")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def search_index(json_out: bool):
    """Show search index statistics.

    Displays document counts by kind, vocabulary size, and
    available categories.
    """
    import json as json_mod

    from aksara.search.indexers import build_full_index

    try:
        index = build_full_index()
        stats = index.stats()
    except Exception as e:
        click.echo(f"❌ Failed to build search index: {e}", err=True)
        sys.exit(1)

    if json_out:
        click.echo(json_mod.dumps(stats, indent=2, default=str))
        return

    click.echo(f"\n  Search Index Statistics")
    click.echo(f"  {'=' * 40}")
    click.echo(f"  Total Documents: {stats['total_documents']}")
    click.echo(f"  Vocabulary Size: {stats['vocabulary_size']}")
    click.echo()

    by_kind = stats.get("by_kind", {})
    if by_kind:
        click.echo(f"  Documents by Kind:")
        for kind_name, count in sorted(by_kind.items()):
            click.echo(f"    {kind_name:15s}  {count}")
    click.echo()


# =============================================================================
# v0.5.25: AI Provider CLI Commands
# =============================================================================


@cli.group("ai-provider")
def ai_provider_group():
    """Unified AI provider management.

    Detect, configure, test, and list AI provider configurations
    using the unified provider system.

    Examples:
        aksara ai-provider list
        aksara ai-provider detect
        aksara ai-provider ping
        aksara ai-provider configure openai --api-key <API_KEY>
    """
    pass


@ai_provider_group.command("list")
@click.option("--format", "-f", "output_format", type=click.Choice(["pretty", "json"]),
              default="pretty", help="Output format")
def ai_provider_list(output_format: str):
    """List all detected AI providers and their status.

    Scans environment variables for configured providers and shows
    which ones are available.

    Examples:
        aksara ai-provider list
        aksara ai-provider list --format json
    """
    import json as json_mod
    from aksara.ai.providers_unified import detect_all_providers, get_active_provider

    providers = detect_all_providers()
    active = get_active_provider()
    active_key = active.provider if active else None

    if output_format == "json":
        data = {
            "active_provider": active_key,
            "providers": [p.to_safe_dict() for p in providers],
        }
        click.echo(json_mod.dumps(data, indent=2))
        return

    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara\033[0m - AI Providers")
    click.echo()

    if not providers:
        click.echo("  No providers detected.")
        click.echo("  Set environment variables like OPENAI_API_KEY to configure.")
        click.echo()
        return

    for p in providers:
        is_active = p.provider == active_key
        configured = p.is_configured()
        marker = "\033[32m●\033[0m" if configured else "\033[90m○\033[0m"
        active_tag = " \033[36m[active]\033[0m" if is_active else ""
        click.echo(f"  {marker} \033[1m{p.provider:12s}\033[0m{active_tag}")
        if p.model:
            click.echo(f"      Model:    {p.model}")
        if p.base_url:
            click.echo(f"      Base URL: {p.base_url}")
        key_status = "***" + p.api_key[-4:] if p.api_key and len(p.api_key) > 4 else ("(set)" if p.api_key else "(not set)")
        click.echo(f"      API Key:  {key_status}")
        click.echo()


@ai_provider_group.command("detect")
def ai_provider_detect():
    """Auto-detect providers from environment variables.

    Scans all known env var patterns and reports what's found.

    Examples:
        aksara ai-provider detect
    """
    from aksara.ai.providers_unified import detect_all_providers

    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara\033[0m - Provider Detection")
    click.echo()

    providers = detect_all_providers()
    configured = [p for p in providers if p.is_configured()]

    if not configured:
        click.echo("  No providers detected from environment.")
        click.echo()
        click.echo("  Supported environment variables:")
        click.echo("    OPENAI_API_KEY         → OpenAI")
        click.echo("    ANTHROPIC_API_KEY      → Anthropic")
        click.echo("    AZURE_OPENAI_API_KEY   → Azure OpenAI")
        click.echo("    OLLAMA_BASE_URL        → Ollama (or localhost:11434)")
        click.echo("    CUSTOM_LLM_BASE_URL    → Custom HTTP endpoint")
    else:
        click.echo(f"  Found {len(configured)} provider(s):")
        click.echo()
        for p in configured:
            click.echo(f"    \033[32m✓\033[0m {p.provider:12s}  model={p.model or '(default)'}")
    click.echo()


@ai_provider_group.command("ping")
@click.option("--provider", "-p", default=None, help="Provider to ping (default: active)")
def ai_provider_ping(provider: Optional[str]):
    """Test connectivity to an AI provider.

    Sends a ping request to verify the provider is reachable
    and the API key is valid.

    Examples:
        aksara ai-provider ping
        aksara ai-provider ping --provider openai
    """
    import time
    from aksara.ai.providers_unified import get_active_provider, detect_all_providers

    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara\033[0m - Provider Ping")
    click.echo()

    prov = None
    if provider:
        found = [p for p in detect_all_providers() if p.provider == provider]
        prov = found[0] if found else None
        if not prov:
            click.echo(f"  \033[31m✗\033[0m Provider '{provider}' not found or not configured.")
            click.echo()
            return
    else:
        prov = get_active_provider()
        if not prov:
            click.echo("  \033[31m✗\033[0m No active provider configured.")
            click.echo()
            return

    click.echo(f"  Pinging \033[1m{prov.provider}\033[0m...")
    start = time.monotonic()
    try:
        ping_result = prov.ping()
        ok = ping_result.get("ok", False) if isinstance(ping_result, dict) else bool(ping_result)
        latency = (time.monotonic() - start) * 1000
        if ok:
            click.echo(f"  \033[32m✓\033[0m Reachable ({latency:.0f}ms)")
        else:
            msg = ping_result.get("message", "") if isinstance(ping_result, dict) else ""
            click.echo(f"  \033[31m✗\033[0m Not reachable ({latency:.0f}ms){': ' + msg if msg else ''}")
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        click.echo(f"  \033[31m✗\033[0m Error ({latency:.0f}ms): {e}")
    click.echo()


@ai_provider_group.command("configure")
@click.argument("provider_name", type=click.Choice(["openai", "azure", "anthropic", "ollama", "custom"]))
@click.option("--api-key", default=None, help="API key")
@click.option("--model", default=None, help="Model name")
@click.option("--base-url", default=None, help="Base URL override")
@click.option("--save-to", type=click.Choice(["env", "json"]), default="env", help="Where to save")
def ai_provider_configure(provider_name: str, api_key: Optional[str], model: Optional[str],
                           base_url: Optional[str], save_to: str):
    """Configure and save an AI provider.

    Prompts for missing values and writes config to .env or provider.json.

    Examples:
        aksara ai-provider configure openai --api-key <API_KEY> --model gpt-4o
        aksara ai-provider configure ollama --model llama3
        aksara ai-provider configure anthropic --save-to json
    """
    from aksara.ai.providers_unified import UnifiedAiProvider

    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara\033[0m - Configure Provider")
    click.echo()

    # Interactive prompts for missing values
    if not api_key and provider_name not in ("ollama",):
        api_key = click.prompt(f"  API Key for {provider_name}", hide_input=True, default="", show_default=False)

    if not model:
        defaults = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "azure": "gpt-4o",
            "ollama": "llama3",
            "custom": "",
        }
        model = click.prompt(f"  Model name", default=defaults.get(provider_name, ""))

    try:
        prov = UnifiedAiProvider(
            provider=provider_name,
            base_url=base_url or "",
            api_key=api_key or "",
            model=model or "",
        )

        if save_to == "json":
            path = prov.save_to_json()
        else:
            path = prov.save_to_env_file()

        click.echo(f"  \033[32m✓\033[0m Saved to {path}")
        click.echo()
        click.echo(f"  Provider: {provider_name}")
        click.echo(f"  Model:    {model}")
        if base_url:
            click.echo(f"  Base URL: {base_url}")
    except Exception as e:
        click.echo(f"  \033[31m✗\033[0m Error: {e}")
    click.echo()


# =============================================================================
# v0.5.28: AI Hub CLI Commands
# =============================================================================


@cli.group("ai-hub")
def ai_hub_group():
    """Unified AI Hub management.

    Central CLI for AI provider configuration, model defaults,
    and health checks — powered by the AI Hub 2.0 engine.

    Examples:
        aksara ai-hub status
        aksara ai-hub providers
        aksara ai-hub models
        aksara ai-hub defaults --chat-model gpt-4o
        aksara ai-hub configure openai --api-key <API_KEY>
        aksara ai-hub doctor

    v0.5.28: AI Hub 2.0
    """
    pass


@ai_hub_group.command("status")
@click.option("--format", "-f", "output_format",
              type=click.Choice(["pretty", "json"]),
              default="pretty", help="Output format")
def ai_hub_status(output_format: str):
    """Show overall AI Hub status.

    Displays the active provider, configured provider count,
    default model assignments, and readiness state.

    Examples:
        aksara ai-hub status
        aksara ai-hub status --format json
    """
    import json as json_mod
    from aksara.ai.hub_settings import load_aihub_settings, resolve_defaults

    hub = load_aihub_settings()
    defaults = resolve_defaults(hub)
    configured = hub.configured_providers()

    if output_format == "json":
        status = hub.to_safe_dict()
        click.echo(json_mod.dumps(status, indent=2, default=str))
        return

    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m — AI Hub Status  (v{CLI_VERSION})")
    click.echo()

    # Readiness
    if configured:
        click.echo(f"  Status:          \033[32m● Ready\033[0m")
    else:
        click.echo(f"  Status:          \033[90m○ No providers configured\033[0m")

    click.echo(f"  Active Provider: {hub.active_provider or '(none)'}")
    click.echo(f"  Configured:      {len(configured)} provider(s)")
    click.echo()

    # Defaults
    click.echo("  \033[1mDefault Models\033[0m")
    click.echo("  " + "─" * 40)
    click.echo(f"  Chat:       {defaults.chat_model or '(not set)'}")
    click.echo(f"  Code:       {defaults.code_model or '(not set)'}")
    click.echo(f"  Embeddings: {defaults.embeddings_model or '(not set)'}")
    click.echo()

    # Provider list
    if configured:
        click.echo("  \033[1mConfigured Providers\033[0m")
        click.echo("  " + "─" * 40)
        for p in configured:
            marker = "\033[36m[active]\033[0m " if p.kind == hub.active_provider else ""
            modes = ", ".join(p.get_supported_modes()) if hasattr(p, "get_supported_modes") else ""
            click.echo(f"  \033[32m●\033[0m {p.kind:12s} {marker}{modes}")
        click.echo()


@ai_hub_group.command("providers")
@click.option("--format", "-f", "output_format",
              type=click.Choice(["pretty", "json"]),
              default="pretty", help="Output format")
def ai_hub_providers(output_format: str):
    """List all AI Hub providers and their configuration.

    Shows each provider kind, whether it's configured, enabled,
    and its supported modes (chat, code, embeddings).

    Examples:
        aksara ai-hub providers
        aksara ai-hub providers --format json
    """
    import json as json_mod
    from aksara.ai.hub_settings import load_aihub_settings

    hub = load_aihub_settings()

    if output_format == "json":
        data = [p.to_safe_dict() for p in hub.providers]
        click.echo(json_mod.dumps(data, indent=2, default=str))
        return

    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m — AI Hub Providers")
    click.echo()

    if not hub.providers:
        click.echo("  No providers registered.")
        click.echo("  Configure via: aksara ai-hub configure <provider> --api-key <key>")
        click.echo()
        return

    for p in hub.providers:
        configured = p.is_configured
        enabled = p.enabled
        marker = "\033[32m●\033[0m" if configured else "\033[90m○\033[0m"
        state = ""
        if not enabled:
            state = " \033[90m(disabled)\033[0m"
        elif p.kind == hub.active_provider:
            state = " \033[36m[active]\033[0m"
        modes = ", ".join(p.get_supported_modes()) if hasattr(p, "get_supported_modes") else ""
        click.echo(f"  {marker} \033[1m{p.kind:12s}\033[0m{state}")
        if modes:
            click.echo(f"      Modes:   {modes}")
        if p.base_url:
            click.echo(f"      URL:     {p.base_url}")
        key_val = p.api_key
        if key_val and len(key_val) > 4:
            click.echo(f"      API Key: ***{key_val[-4:]}")
        elif key_val:
            click.echo(f"      API Key: (set)")
        else:
            click.echo(f"      API Key: (not set)")
        click.echo()


@ai_hub_group.command("models")
@click.option("--format", "-f", "output_format",
              type=click.Choice(["pretty", "json"]),
              default="pretty", help="Output format")
def ai_hub_models(output_format: str):
    """Show available models from all configured providers.

    Lists the default model assignments and the full model
    catalog from each provider.

    Examples:
        aksara ai-hub models
        aksara ai-hub models --format json
    """
    import json as json_mod
    from aksara.ai.hub_settings import load_aihub_settings, resolve_defaults

    hub = load_aihub_settings()
    defaults = resolve_defaults(hub)

    if output_format == "json":
        data = {
            "defaults": {
                "chat_model": defaults.chat_model,
                "chat_provider": defaults.chat_provider,
                "code_model": defaults.code_model,
                "code_provider": defaults.code_provider,
                "embeddings_model": defaults.embeddings_model,
                "embeddings_provider": defaults.embeddings_provider,
            },
            "providers": [],
        }
        for p in hub.configured_providers():
            entry = {"kind": p.kind, "modes": p.get_supported_modes() if hasattr(p, "get_supported_modes") else []}
            if p.model:
                entry["model"] = p.model
            data["providers"].append(entry)
        click.echo(json_mod.dumps(data, indent=2, default=str))
        return

    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m — AI Hub Models")
    click.echo()

    click.echo("  \033[1mDefault Assignments\033[0m")
    click.echo("  " + "─" * 50)
    click.echo(f"  {'Role':<16} {'Model':<24} {'Provider'}")
    click.echo(f"  {'─' * 16} {'─' * 24} {'─' * 12}")
    click.echo(f"  {'Chat':<16} {defaults.chat_model or '(not set)':<24} {defaults.chat_provider or ''}")
    click.echo(f"  {'Code':<16} {defaults.code_model or '(not set)':<24} {defaults.code_provider or ''}")
    click.echo(f"  {'Embeddings':<16} {defaults.embeddings_model or '(not set)':<24} {defaults.embeddings_provider or ''}")
    click.echo()


@ai_hub_group.command("defaults")
@click.option("--chat-model", default=None, help="Default chat model")
@click.option("--code-model", default=None, help="Default code model")
@click.option("--embeddings-model", default=None, help="Default embeddings model")
@click.option("--chat-provider", default=None, help="Provider for chat")
@click.option("--code-provider", default=None, help="Provider for code")
@click.option("--embeddings-provider", default=None, help="Provider for embeddings")
@click.option("--format", "-f", "output_format",
              type=click.Choice(["pretty", "json"]),
              default="pretty", help="Output format")
def ai_hub_defaults(
    chat_model: Optional[str],
    code_model: Optional[str],
    embeddings_model: Optional[str],
    chat_provider: Optional[str],
    code_provider: Optional[str],
    embeddings_provider: Optional[str],
    output_format: str,
):
    """Get or set default model assignments.

    Without arguments, shows current defaults.  With --chat-model etc.,
    updates the defaults and saves to settings.

    Examples:
        aksara ai-hub defaults
        aksara ai-hub defaults --chat-model gpt-4o --code-model gpt-4o
        aksara ai-hub defaults --embeddings-model text-embedding-3-large
        aksara ai-hub defaults --format json
    """
    import json as json_mod
    from aksara.ai.hub_settings import load_aihub_settings, save_aihub_settings, resolve_defaults

    hub = load_aihub_settings()
    any_set = any([chat_model, code_model, embeddings_model, chat_provider, code_provider, embeddings_provider])

    if any_set:
        # Update defaults
        if chat_model:
            hub.defaults.chat_model = chat_model
        if code_model:
            hub.defaults.code_model = code_model
        if embeddings_model:
            hub.defaults.embeddings_model = embeddings_model
        if chat_provider:
            hub.defaults.chat_provider = chat_provider
        if code_provider:
            hub.defaults.code_provider = code_provider
        if embeddings_provider:
            hub.defaults.embeddings_provider = embeddings_provider
        save_aihub_settings(hub)

        if output_format == "json":
            click.echo(json_mod.dumps({"saved": True, "defaults": hub.defaults.model_dump()}, indent=2))
        else:
            click.echo()
            click.echo(f"  \033[32m✓\033[0m Defaults saved.")
            click.echo()
        return

    # Show current defaults
    defaults = resolve_defaults(hub)
    if output_format == "json":
        click.echo(json_mod.dumps(defaults.model_dump(), indent=2, default=str))
        return

    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m — AI Hub Defaults")
    click.echo()
    click.echo(f"  Chat Model:       {defaults.chat_model or '(not set)'}")
    click.echo(f"  Chat Provider:    {defaults.chat_provider or '(auto)'}")
    click.echo(f"  Code Model:       {defaults.code_model or '(not set)'}")
    click.echo(f"  Code Provider:    {defaults.code_provider or '(auto)'}")
    click.echo(f"  Embeddings Model: {defaults.embeddings_model or '(not set)'}")
    click.echo(f"  Embeddings Prov:  {defaults.embeddings_provider or '(auto)'}")
    click.echo()


@ai_hub_group.command("configure")
@click.argument("provider_name", type=click.Choice(["openai", "azure", "anthropic", "ollama", "custom"]))
@click.option("--api-key", default=None, help="API key")
@click.option("--model", default=None, help="Default model name")
@click.option("--base-url", default=None, help="Base URL override")
@click.option("--enable/--disable", default=True, help="Enable or disable the provider")
def ai_hub_configure(provider_name: str, api_key: Optional[str], model: Optional[str],
                     base_url: Optional[str], enable: bool):
    """Configure an AI Hub provider.

    Sets credentials and options for the specified provider.
    Saves to the hub settings file.

    Examples:
        aksara ai-hub configure openai --api-key <API_KEY>
        aksara ai-hub configure ollama --base-url http://gpu-server:11434
        aksara ai-hub configure anthropic --disable
    """
    from aksara.ai.hub_settings import (
        load_aihub_settings, save_aihub_settings,
        OpenAIConfig, AzureOpenAIConfig, AnthropicConfig, OllamaConfig, CustomHttpConfig,
        ProviderConfig,
    )

    hub = load_aihub_settings()
    existing = hub.get_provider(provider_name)

    if existing is None:
        # Create new provider config
        cfg_map = {
            "openai": ("openai", OpenAIConfig),
            "azure": ("azure", AzureOpenAIConfig),
            "anthropic": ("anthropic", AnthropicConfig),
            "ollama": ("ollama", OllamaConfig),
            "custom": ("custom", CustomHttpConfig),
        }
        field_name, cfg_cls = cfg_map[provider_name]
        kwargs = {}
        if api_key:
            kwargs["api_key"] = api_key
        if model:
            kwargs["model"] = model
        if base_url:
            kwargs["base_url"] = base_url
        cfg = cfg_cls(**kwargs)
        pc = ProviderConfig(kind=provider_name, enabled=enable, **{field_name: cfg})
        hub.providers.append(pc)
    else:
        cfg = existing.active_config
        if cfg:
            if api_key:
                if hasattr(cfg, "api_key"):
                    cfg.api_key = api_key
            if model:
                if hasattr(cfg, "model"):
                    cfg.model = model
            if base_url:
                if hasattr(cfg, "base_url"):
                    cfg.base_url = base_url
        existing.enabled = enable

    save_aihub_settings(hub)

    click.echo()
    status = "\033[32m✓\033[0m" if enable else "\033[33m⚠\033[0m"
    click.echo(f"  {status} Provider '{provider_name}' {'enabled' if enable else 'disabled'} and saved.")
    if api_key:
        click.echo(f"      API Key: ***{api_key[-4:]}" if len(api_key) > 4 else "      API Key: (set)")
    if model:
        click.echo(f"      Model:   {model}")
    if base_url:
        click.echo(f"      URL:     {base_url}")
    click.echo()


@ai_hub_group.command("doctor")
@click.option("--format", "-f", "output_format",
              type=click.Choice(["pretty", "json"]),
              default="pretty", help="Output format")
def ai_hub_doctor(output_format: str):
    """Run AI Hub health checks.

    Validates provider configuration, tests connectivity where
    possible, and checks that defaults are properly resolved.

    Examples:
        aksara ai-hub doctor
        aksara ai-hub doctor --format json
    """
    import json as json_mod
    from aksara.ai.hub_settings import load_aihub_settings, resolve_defaults

    hub = load_aihub_settings()
    configured = hub.configured_providers()
    defaults = resolve_defaults(hub)
    issues = []

    # Check 1: Any providers configured?
    if not configured:
        issues.append({
            "severity": "warning",
            "check": "providers",
            "message": "No AI providers configured. AI features unavailable.",
            "hint": "aksara ai-hub configure openai --api-key <API_KEY>",
        })

    # Check 2: Active provider set?
    if configured and not hub.active_provider:
        issues.append({
            "severity": "info",
            "check": "active_provider",
            "message": "No active provider set. Will use first configured provider.",
            "hint": "Set active_provider in hub settings.",
        })

    # Check 3: Default chat model?
    if not defaults.chat_model:
        issues.append({
            "severity": "warning",
            "check": "chat_model",
            "message": "No default chat model configured.",
            "hint": "aksara ai-hub defaults --chat-model gpt-4o",
        })

    # Check 4: Default embeddings model?
    if not defaults.embeddings_model:
        issues.append({
            "severity": "info",
            "check": "embeddings_model",
            "message": "No embeddings model set. Semantic search will use local TF-IDF.",
            "hint": "aksara ai-hub defaults --embeddings-model text-embedding-3-large",
        })

    if output_format == "json":
        data = {
            "ok": len(issues) == 0,
            "providers_configured": len(configured),
            "active_provider": hub.active_provider,
            "issues": issues,
        }
        click.echo(json_mod.dumps(data, indent=2))
        sys.exit(1 if any(i["severity"] in ("error", "critical") for i in issues) else 0)

    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m — AI Hub Doctor  (v{CLI_VERSION})")
    click.echo()

    if not issues:
        click.echo("  \033[32m✓ AI Hub is healthy. All checks passed.\033[0m")
        click.echo()
        click.echo(f"  Active Provider: {hub.active_provider}")
        click.echo(f"  Configured:      {len(configured)}")
        click.echo(f"  Chat Model:      {defaults.chat_model}")
        click.echo(f"  Embeddings:      {defaults.embeddings_model or '(local TF-IDF)'}")
        click.echo()
        return

    click.echo(f"  Found {len(issues)} issue{'s' if len(issues) != 1 else ''}:")
    click.echo()

    for iss in issues:
        sev = iss["severity"]
        c = _SEVERITY_COLORS.get(sev, "")
        sym = _SEVERITY_SYMBOLS.get(sev, "·")
        click.echo(f"  {c}{sym} [{sev.upper():8s}]{_RESET} {iss['message']}")
        if iss.get("hint"):
            click.echo(f"               \033[90mHint: {iss['hint']}\033[0m")
    click.echo()

    sys.exit(1 if any(i["severity"] in ("error", "critical") for i in issues) else 0)


# =============================================================================
# v0.5.26: Gap Analysis CLI Commands
# =============================================================================


@cli.group()
def gaps():
    """Pre-flight gap analysis for your Aksara project.

    Scans eight categories of potential issues:
      imports, db, migrations, routers, providers,
      studio, environment, ai_pipeline

    Exit codes:
      0  –  no blocking issues (clean or warnings only)
      1  –  at least one error or critical issue found

    v0.5.26: Gap Analysis Engine
    """
    pass


def _run_gap_analysis_sync(categories: Optional[List[str]] = None):
    """Run the gap analysis engine synchronously."""
    from aksara.gapanalysis import run_gap_analysis
    return asyncio.run(run_gap_analysis(categories=categories))  # type: ignore[arg-type]


_SEVERITY_COLORS = {
    "critical": "\033[35m",   # Magenta
    "error": "\033[31m",      # Red
    "warning": "\033[33m",    # Yellow
    "info": "\033[36m",       # Cyan
}
_SEVERITY_SYMBOLS = {
    "critical": "✗",
    "error": "✗",
    "warning": "!",
    "info": "·",
}
_RESET = "\033[0m"


def _severity_badge(severity: str) -> str:
    """Format a severity badge with color."""
    color = _SEVERITY_COLORS.get(severity, "")
    return f"{color}[{severity.upper():8s}]{_RESET}"


@gaps.command("run")
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["pretty", "json"]),
    default="pretty",
    help="Output format (default: pretty)",
)
@click.option(
    "--categories", "-c",
    default=None,
    help="Comma-separated categories to check (default: all)",
)
def gaps_run(output_format: str, categories: Optional[str]):
    """Run the full gap analysis and display a rich issue table.

    Examples:
        aksara gaps run
        aksara gaps run --format json
        aksara gaps run --categories db,migrations,environment
    """
    import json as json_mod

    cat_list = [c.strip() for c in categories.split(",")] if categories else None
    report = _run_gap_analysis_sync(categories=cat_list)

    if output_format == "json":
        from aksara.studio.utils import build_studio_gap_analysis_report
        studio_report = build_studio_gap_analysis_report(report)
        click.echo(json_mod.dumps(studio_report.model_dump(mode="json"), indent=2, default=str))
        sys.exit(1 if report.has_errors else 0)

    click.echo()
    click.echo(f"  \033[33m⚡\033[0m \033[1mAksara\033[0m — Gap Analysis  (v{CLI_VERSION})")
    click.echo()

    # Summary header
    status_c = _SEVERITY_COLORS.get(report.overall_status, "")
    click.echo(f"  Status:    {status_c}{report.overall_status.upper()}{_RESET}")
    click.echo(f"  Summary:   {report.summary_line}")
    click.echo(f"  Duration:  {report.duration_ms:.0f} ms")
    click.echo()

    if not report.issues:
        click.echo("  \033[32m✓ No gaps found — your project looks good!\033[0m")
        click.echo()
        sys.exit(0)

    # Group by category
    by_cat: dict = {}
    for issue in report.issues:
        by_cat.setdefault(issue.category, []).append(issue)

    for cat, issues in sorted(by_cat.items()):
        click.echo(f"  \033[1m{cat.upper()}\033[0m ({len(issues)} issue{'s' if len(issues) != 1 else ''})")
        click.echo("  " + "─" * 56)
        for issue in issues:
            sym = _SEVERITY_SYMBOLS.get(issue.severity, "·")
            c = _SEVERITY_COLORS.get(issue.severity, "")
            click.echo(f"  {c}{sym}{_RESET} {_severity_badge(issue.severity)} {issue.title}")
            click.echo(f"               {issue.message}")
            if issue.hint:
                click.echo(f"               \033[90mHint: {issue.hint}\033[0m")
            if issue.fix_commands:
                for cmd in issue.fix_commands[:2]:
                    click.echo(f"               \033[36m→ {cmd.command}\033[0m")
            click.echo()

    # Stat line
    s = report.stats
    counts = []
    if s.critical:
        counts.append(f"\033[35m{s.critical} critical{_RESET}")
    if s.error:
        counts.append(f"\033[31m{s.error} error{'s' if s.error != 1 else ''}{_RESET}")
    if s.warning:
        counts.append(f"\033[33m{s.warning} warning{'s' if s.warning != 1 else ''}{_RESET}")
    if s.info:
        counts.append(f"{s.info} info")
    click.echo("  " + "  ".join(counts))
    click.echo()

    sys.exit(1 if report.has_errors else 0)


@gaps.command("summary")
def gaps_summary():
    """Show a compact count of issues by severity and category.

    Example:
        aksara gaps summary
    """
    report = _run_gap_analysis_sync()

    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara Gap Analysis — Summary\033[0m")
    click.echo()

    if report.stats.total == 0:
        click.echo("  \033[32m✓ All clear — no gaps detected.\033[0m")
        click.echo()
        sys.exit(0)

    # Severity totals
    s = report.stats
    click.echo(f"  {'Severity':<12} {'Count':>6}")
    click.echo(f"  {'─' * 12} {'─' * 6}")
    if s.critical:
        click.echo(f"  \033[35m{'critical':<12}{s.critical:>6}\033[0m")
    if s.error:
        click.echo(f"  \033[31m{'error':<12}{s.error:>6}\033[0m")
    if s.warning:
        click.echo(f"  \033[33m{'warning':<12}{s.warning:>6}\033[0m")
    if s.info:
        click.echo(f"  {'info':<12}{s.info:>6}")
    click.echo(f"  {'─' * 12} {'─' * 6}")
    click.echo(f"  {'TOTAL':<12}{s.total:>6}")
    click.echo()

    # Category breakdown
    by_cat: dict = {}
    for issue in report.issues:
        by_cat.setdefault(issue.category, 0)
        by_cat[issue.category] += 1

    click.echo(f"  {'Category':<20} {'Issues':>7}")
    click.echo(f"  {'─' * 20} {'─' * 7}")
    for cat, count in sorted(by_cat.items()):
        click.echo(f"  {cat:<20} {count:>7}")
    click.echo()

    sys.exit(1 if report.has_errors else 0)


@gaps.command("json")
@click.option(
    "--categories", "-c",
    default=None,
    help="Comma-separated categories to check (default: all)",
)
def gaps_json(categories: Optional[str]):
    """Output the full gap analysis report as JSON.

    Suitable for piping to other tools or saving to a file.

    Examples:
        aksara gaps json
        aksara gaps json --categories imports,environment
        aksara gaps json > gaps.json
    """
    import json as json_mod

    cat_list = [c.strip() for c in categories.split(",")] if categories else None
    report = _run_gap_analysis_sync(categories=cat_list)

    from aksara.studio.utils import build_studio_gap_analysis_report
    studio_report = build_studio_gap_analysis_report(report)
    click.echo(json_mod.dumps(studio_report.model_dump(mode="json"), indent=2, default=str))

    sys.exit(1 if report.has_errors else 0)


@gaps.command("list-errors")
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["pretty", "json"]),
    default="pretty",
    help="Output format (default: pretty)",
)
def gaps_list_errors(output_format: str):
    """List only error and critical severity gap issues.

    Example:
        aksara gaps list-errors
        aksara gaps list-errors --format json
    """
    import json as json_mod

    report = _run_gap_analysis_sync()
    errors = report.by_severity("error") + report.by_severity("critical")

    if output_format == "json":
        data = [
            {
                "severity": i.severity,
                "category": i.category,
                "code": i.code,
                "title": i.title,
                "message": i.message,
                "hint": i.hint,
            }
            for i in errors
        ]
        click.echo(json_mod.dumps(data, indent=2))
        sys.exit(1 if errors else 0)

    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara Gaps — Errors & Criticals\033[0m")
    click.echo()

    if not errors:
        click.echo("  \033[32m✓ No error or critical issues found.\033[0m")
        click.echo()
        sys.exit(0)

    click.echo(f"  Found {len(errors)} blocking issue{'s' if len(errors) != 1 else ''}:\n")
    for issue in errors:
        c = _SEVERITY_COLORS.get(issue.severity, "")
        sym = _SEVERITY_SYMBOLS.get(issue.severity, "✗")
        click.echo(f"  {c}{sym} [{issue.severity.upper()}] {issue.title}{_RESET}")
        click.echo(f"     Category: {issue.category} | Code: {issue.code}")
        click.echo(f"     {issue.message}")
        if issue.hint:
            click.echo(f"     \033[90mHint: {issue.hint}\033[0m")
        click.echo()

    sys.exit(1)


@gaps.command("list-critical")
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["pretty", "json"]),
    default="pretty",
    help="Output format (default: pretty)",
)
def gaps_list_critical(output_format: str):
    """List only critical severity gap issues.

    Exit code is non-zero if any critical issues are found.
    Suitable for CI/CD gates.

    Examples:
        aksara gaps list-critical
        aksara gaps list-critical --format json
        if ! aksara gaps list-critical --format json > /dev/null; then exit 1; fi
    """
    import json as json_mod

    report = _run_gap_analysis_sync()
    critical = report.by_severity("critical")

    if output_format == "json":
        data = [
            {
                "severity": i.severity,
                "category": i.category,
                "code": i.code,
                "title": i.title,
                "message": i.message,
                "hint": i.hint,
            }
            for i in critical
        ]
        click.echo(json_mod.dumps(data, indent=2))
        sys.exit(1 if critical else 0)

    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara Gaps — Critical Issues\033[0m")
    click.echo()

    if not critical:
        click.echo("  \033[32m✓ No critical issues found.\033[0m")
        click.echo()
        sys.exit(0)

    click.echo(f"  Found {len(critical)} critical issue{'s' if len(critical) != 1 else ''}:\n")
    for issue in critical:
        click.echo(f"  \033[35m✗ [CRITICAL] {issue.title}\033[0m")
        click.echo(f"     Category: {issue.category} | Code: {issue.code}")
        click.echo(f"     {issue.message}")
        if issue.hint:
            click.echo(f"     \033[90mHint: {issue.hint}\033[0m")
        click.echo()

    sys.exit(1)


@gaps.command("fix-plan")
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["pretty", "json"]),
    default="pretty",
    help="Output format (default: pretty)",
)
@click.option(
    "--only-blocking", is_flag=True, default=False,
    help="Only include error and critical issues",
)
def gaps_fix_plan(output_format: str, only_blocking: bool):
    """Generate a structured fix plan for all discovered gaps.

    Prints every issue that has associated fix commands, sorted by
    severity (critical first).  Use --only-blocking to skip
    warnings and info.

    Examples:
        aksara gaps fix-plan
        aksara gaps fix-plan --format json
        aksara gaps fix-plan --only-blocking
    """
    import json as json_mod
    from aksara.gapanalysis import build_fix_plan

    report = _run_gap_analysis_sync()

    if only_blocking:
        from aksara.gapanalysis import GapAnalysisReport
        # Filter to a temporary report-like object
        filtered_issues = [i for i in report.issues if i.is_blocking]
        report.issues = filtered_issues

    plan = build_fix_plan(report)

    if output_format == "json":
        click.echo(json_mod.dumps(plan, indent=2))
        sys.exit(1 if report.has_errors else 0)

    click.echo()
    click.echo("  \033[33m⚡\033[0m \033[1mAksara Gaps — Fix Plan\033[0m")
    click.echo()

    if not plan:
        click.echo("  \033[32m✓ No actionable fixes needed.\033[0m")
        click.echo()
        sys.exit(0 if not report.has_errors else 1)

    click.echo(f"  {len(plan)} fix action{'s' if len(plan) != 1 else ''} available:\n")
    for idx, item in enumerate(plan, 1):
        c = _SEVERITY_COLORS.get(item["severity"], "")
        click.echo(f"  {idx}. {c}[{item['severity'].upper()}]{_RESET} {item['title']}")
        click.echo(f"     Category: {item['category']} | Code: {item['code']}")
        for cmd in item["commands"]:
            click.echo(f"     \033[36m→ {cmd['description']}\033[0m")
            click.echo(f"       \033[90m$ {cmd['command']}\033[0m")
        click.echo()

    total_cmds = sum(len(i["commands"]) for i in plan)
    click.echo(f"  {len(plan)} issue(s), {total_cmds} command(s)")
    click.echo()

    sys.exit(1 if report.has_errors else 0)


# =============================================================================
# Tasks Commands
# =============================================================================

def _tasks_db():
    """Open a database connection using the documented environment precedence."""
    import os
    from aksara.db import Database

    url = os.getenv("AKSARA_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        env_path = Path.cwd() / ".env"
        url = _read_env_database_url(env_path)
    if not url:
        click.echo("  Error: DATABASE_URL is not set. Run aksara dbsetup first.", err=True)
        sys.exit(1)
    return Database(url)


@cli.group()
def tasks():
    """Inspect and manage the background task queue."""
    pass


@tasks.command("stats")
def tasks_stats():
    """Show task queue counts grouped by status and queue."""

    async def _run():
        db = _tasks_db()
        await db.connect()
        try:
            from aksara.tasks import ensure_tasks_table, TASKS_TABLE
            await ensure_tasks_table(db)
            rows = await db.fetch(
                f'''
                SELECT queue, status, COUNT(*) AS count
                FROM "{TASKS_TABLE}"
                GROUP BY queue, status
                ORDER BY queue, status
                '''
            )
            return rows
        finally:
            await db.disconnect()

    ui = get_ui()
    ui.aksara_banner(f"v{CLI_VERSION}", "Task Queue Stats")

    rows = _run_async_command(_run())

    if not rows:
        ui.info("No tasks in the queue.")
        ui.blank()
        return

    # Group by queue for display
    from collections import defaultdict
    by_queue: dict = defaultdict(dict)
    totals: dict = defaultdict(int)
    for row in rows:
        by_queue[row["queue"]][row["status"]] = row["count"]
        totals[row["status"]] += row["count"]

    STATUS_COLORS = {
        "pending":   "\033[33m",
        "running":   "\033[36m",
        "completed": "\033[32m",
        "failed":    "\033[31m",
    }
    RESET = "\033[0m"

    for queue_name, statuses in sorted(by_queue.items()):
        ui.section(f"Queue: {queue_name}")
        for status in ("pending", "running", "completed", "failed"):
            count = statuses.get(status, 0)
            color = STATUS_COLORS.get(status, "")
            click.echo(f"    {color}{status:<12}{RESET} {count:>6}")
        ui.blank()

    ui.section("Total")
    for status in ("pending", "running", "completed", "failed"):
        count = totals.get(status, 0)
        color = STATUS_COLORS.get(status, "")
        click.echo(f"    {color}{status:<12}{RESET} {count:>6}")
    ui.blank()


@tasks.command("list")
@click.option("--status", "-s", default="failed",
              type=click.Choice(["pending", "running", "completed", "failed"]),
              help="Filter by task status (default: failed)")
@click.option("--queue", "-q", default=None, help="Filter by queue name")
@click.option("--task-name", "-t", default=None, help="Filter by task name (substring match)")
@click.option("--limit", "-n", default=20, type=int, help="Max results (default: 20)")
def tasks_list(status, queue, task_name, limit):
    """List tasks — defaults to showing failed tasks."""

    async def _run():
        db = _tasks_db()
        await db.connect()
        try:
            from aksara.tasks import ensure_tasks_table, TASKS_TABLE
            await ensure_tasks_table(db)

            conditions = ["status = $1"]
            params: list = [status]

            if queue:
                params.append(queue)
                conditions.append(f"queue = ${len(params)}")
            if task_name:
                params.append(f"%{task_name}%")
                conditions.append(f"task_name ILIKE ${len(params)}")

            params.append(limit)
            where = " AND ".join(conditions)
            rows = await db.fetch(
                f'''
                SELECT id, task_name, queue, status, attempts, max_attempts,
                       last_error, available_at, created_at, updated_at
                FROM "{TASKS_TABLE}"
                WHERE {where}
                ORDER BY updated_at DESC
                LIMIT ${len(params)}
                ''',
                *params,
            )
            return rows
        finally:
            await db.disconnect()

    ui = get_ui()
    rows = _run_async_command(_run())

    if not rows:
        ui.info(f"No {status} tasks found.")
        ui.blank()
        return

    click.echo()
    click.echo(f"  {len(rows)} {status} task(s):\n")
    for row in rows:
        err = (row["last_error"] or "")[:80]
        err_suffix = "…" if len(row["last_error"] or "") > 80 else ""
        click.echo(f"  \033[1m{row['id']}\033[0m")
        click.echo(f"    task  : {row['task_name']}")
        click.echo(f"    queue : {row['queue']}")
        click.echo(f"    status: {row['status']}  attempts: {row['attempts']}/{row['max_attempts']}")
        if err:
            click.echo(f"    error : {err}{err_suffix}")
        click.echo(f"    updated: {row['updated_at']}")
        click.echo()


@tasks.command("reenqueue")
@click.argument("task_id", required=False)
@click.option("--all", "all_failed", is_flag=True, help="Re-enqueue ALL failed tasks")
@click.option("--queue", "-q", default=None, help="Filter by queue when using --all")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def tasks_reenqueue(task_id, all_failed, queue, yes):
    """Re-enqueue a failed task by ID, or all failed tasks with --all.

    Examples:

        aksara tasks reenqueue <uuid>
        aksara tasks reenqueue --all
        aksara tasks reenqueue --all --queue emails
    """
    if not task_id and not all_failed:
        click.echo("  Provide a TASK_ID or use --all.", err=True)
        sys.exit(1)

    async def _run():
        db = _tasks_db()
        await db.connect()
        try:
            from aksara.tasks import ensure_tasks_table, TASKS_TABLE
            await ensure_tasks_table(db)

            if task_id:
                import uuid as _uuid
                try:
                    tid = _uuid.UUID(task_id)
                except ValueError:
                    click.echo(f"  Invalid task ID: {task_id}", err=True)
                    sys.exit(1)

                row = await db.fetchrow(
                    f"SELECT id, status FROM \"{TASKS_TABLE}\" WHERE id = $1", tid
                )
                if row is None:
                    click.echo(f"  Task {task_id} not found.", err=True)
                    sys.exit(1)
                if row["status"] not in ("failed", "completed"):
                    click.echo(
                        f"  Task is '{row['status']}', not failed/completed — skipping.", err=True
                    )
                    sys.exit(1)

                await db.execute(
                    f'''
                    UPDATE "{TASKS_TABLE}"
                    SET status = 'pending',
                        attempts = 0,
                        locked_at = NULL,
                        locked_by = NULL,
                        claim_token = NULL,
                        lock_expires_at = NULL,
                        last_error = NULL,
                        available_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $1
                    ''',
                    tid,
                )
                return 1

            # --all path
            conditions = ["status = 'failed'"]
            params: list = []
            if queue:
                params.append(queue)
                conditions.append(f"queue = ${len(params)}")

            where = " AND ".join(conditions)
            result = await db.fetchrow(
                f'''
                WITH requeued AS (
                    UPDATE "{TASKS_TABLE}"
                    SET status = 'pending',
                        attempts = 0,
                        locked_at = NULL,
                        locked_by = NULL,
                        claim_token = NULL,
                        lock_expires_at = NULL,
                        last_error = NULL,
                        available_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE {where}
                    RETURNING id
                )
                SELECT COUNT(*) AS count FROM requeued
                ''',
                *params,
            )
            return int(result["count"]) if result else 0
        finally:
            await db.disconnect()

    ui = get_ui()

    if all_failed and not yes:
        queue_msg = f" in queue '{queue}'" if queue else ""
        if not click.confirm(f"  Re-enqueue all failed tasks{queue_msg}?", default=False):
            ui.info("Aborted.")
            return

    count = _run_async_command(_run())
    ui.success(f"Re-enqueued {count} task(s).")
    ui.blank()


@tasks.command("purge")
@click.option("--status", "-s", "statuses", multiple=True,
              default=["completed"],
              type=click.Choice(["completed", "failed"]),
              help="Status(es) to purge (default: completed)")
@click.option("--older-than-days", "-d", default=7.0, type=float,
              help="Delete records last updated more than N days ago (default: 7)")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def tasks_purge(statuses, older_than_days, yes):
    """Delete old task records from the database.

    Examples:

        aksara tasks purge
        aksara tasks purge --status failed --older-than-days 30
        aksara tasks purge --status completed --status failed -d 1
    """

    async def _run():
        db = _tasks_db()
        await db.connect()
        try:
            from aksara.tasks import TaskWorker
            worker = TaskWorker(db)
            return await worker.purge_old_tasks(
                statuses=tuple(statuses),
                older_than_seconds=older_than_days * 86400,
            )
        finally:
            await db.disconnect()

    ui = get_ui()

    if not yes:
        status_str = ", ".join(statuses)
        if not click.confirm(
            f"  Delete {status_str} tasks older than {older_than_days:.0f} days?",
            default=False,
        ):
            ui.info("Aborted.")
            return

    count = _run_async_command(_run())
    ui.success(f"Purged {count} task record(s).")
    ui.blank()


if __name__ == "__main__":
    main()
