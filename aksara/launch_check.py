"""
Launch readiness checks for first-time Aksara projects.

The launch check is intentionally narrower than the full diagnostics engine:
it answers "can a new developer run this project, open Studio, inspect MCP,
and understand what to do next?"
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import platform
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit


CHECK_STATUSES = {"ok", "warning", "error", "skipped"}
CATEGORY_ORDER = [
    "environment",
    "project",
    "database",
    "studio",
    "ai",
    "examples",
    "security",
]


@dataclass
class LaunchCheckItem:
    category: str
    name: str
    status: str
    message: str
    hint: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in CHECK_STATUSES:
            raise ValueError(f"Unknown launch check status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "hint": self.hint,
            "details": self.details,
        }


@dataclass
class LaunchCheckReport:
    ok: bool
    status: str
    version: str
    checks: list[LaunchCheckItem]
    next_steps: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "version": self.version,
            "checks": [check.to_dict() for check in self.checks],
            "next_steps": self.next_steps,
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @property
    def exit_code(self) -> int:
        if self.status == "ready":
            return 0
        if self.status == "partial":
            return 1
        return 2


def run_launch_check(
    project_root: str | Path | None = None,
    *,
    check_database: bool = True,
    database_timeout: float = 2.0,
) -> LaunchCheckReport:
    """Run launch readiness checks for the current Aksara project."""

    root = Path(project_root or Path.cwd()).resolve()
    checks: list[LaunchCheckItem] = []
    loaded_settings_module: Any | None = None
    loaded_app: Any | None = None
    database_connected = False

    def add(
        category: str,
        name: str,
        status: str,
        message: str,
        hint: str | None = None,
        **details: Any,
    ) -> None:
        checks.append(
            LaunchCheckItem(
                category=category,
                name=name,
                status=status,
                message=message,
                hint=hint,
                details={key: value for key, value in details.items() if value is not None},
            )
        )

    version = _get_aksara_version()

    # Environment
    py_version = platform.python_version()
    if sys.version_info >= (3, 11):
        add("environment", "python_version", "ok", f"Python {py_version} detected")
    else:
        add(
            "environment",
            "python_version",
            "error",
            f"Python {py_version} is below Aksara's supported baseline",
            "Use Python 3.11 or newer",
        )

    add("environment", "aksara_version", "ok", f"Aksara {version} installed")

    # Project structure and settings
    if _is_project_root(root):
        add("project", "project_detected", "ok", "aksara project detected", path=str(root))
    else:
        add(
            "project",
            "project_detected",
            "error",
            "No Aksara project detected",
            "Run from a project containing main.py/settings.py or use aksara startproject",
            path=str(root),
        )

    settings_module_name = _preferred_module_name(root, "settings")
    if settings_module_name:
        try:
            loaded_settings_module = _import_from_root(root, settings_module_name)
            add("project", "settings_module", "ok", "settings module found", module=settings_module_name)
        except Exception as exc:
            add(
                "project",
                "settings_module",
                "error",
                "settings module cannot load",
                "Fix settings.py import/configuration errors",
                error=repr(exc),
                module=settings_module_name,
            )
    else:
        add(
            "project",
            "settings_module",
            "warning",
            "settings module not found",
            "Create settings.py or configure Aksara before launch",
        )

    app_module_name = _preferred_module_name(root, "main")
    if app_module_name:
        try:
            loaded_app_module = _import_from_root(root, app_module_name)
            loaded_app = getattr(loaded_app_module, "app", None)
            add("project", "app_registry", "ok", "app registry loaded", module=app_module_name)
        except Exception as exc:
            add(
                "project",
                "app_registry",
                "error",
                "app registry cannot load",
                "Fix main.py imports before running aksara dev",
                error=repr(exc),
                module=app_module_name,
            )
    else:
        add(
            "project",
            "app_registry",
            "warning",
            "main.py not found",
            "Create main.py with an Aksara app",
        )

    # Database
    database_url = _get_database_url(loaded_settings_module)
    migration_files = _find_migration_files(root, loaded_settings_module)
    applied_migrations: set[str] | None = None

    if database_url:
        add(
            "database",
            "database_url",
            "ok",
            "DATABASE_URL configured",
            redacted_url=_redact_database_url(database_url),
        )
        if check_database:
            try:
                applied_migrations = _run_database_probe(database_url, database_timeout)
                database_connected = True
                add("database", "connection", "ok", "PostgreSQL connection successful")
            except Exception as exc:
                add(
                    "database",
                    "connection",
                    "error",
                    "PostgreSQL connection failed",
                    "Check that PostgreSQL is running and DATABASE_URL credentials are correct",
                    error=repr(exc),
                )
        else:
            add("database", "connection", "skipped", "Database probe skipped")
    else:
        add(
            "database",
            "database_url",
            "error",
            "DATABASE_URL not configured",
            "Set DATABASE_URL or AKSARA_DATABASE_URL",
        )

    if migration_files:
        if database_connected and applied_migrations is not None:
            pending = [name for name in migration_files if name not in applied_migrations]
            if pending:
                add(
                    "database",
                    "migrations",
                    "warning",
                    f"{len(pending)} pending migration{'s' if len(pending) != 1 else ''}",
                    "Run aksara migrate",
                    pending=pending,
                )
            else:
                add("database", "migrations", "ok", "Migrations are up to date")
        else:
            add(
                "database",
                "migrations",
                "skipped",
                "Migration status skipped until database is reachable",
                "Run aksara migrate after fixing database access",
                migration_count=len(migration_files),
            )
    else:
        add(
            "database",
            "migrations",
            "warning",
            "No migration files found",
            "Run aksara makemigrations before sharing the app",
        )

    # Studio/API/MCP route readiness
    route_paths = _route_paths(loaded_app)
    if route_paths:
        if _has_path(route_paths, "/studio/ui"):
            add("studio", "studio_ui", "ok", "Studio UI available")
        else:
            add(
                "studio",
                "studio_ui",
                "warning",
                "Studio UI route not registered",
                "Enable Studio in local debug mode and run aksara dev",
            )

        docs_url = getattr(loaded_app, "docs_url", None) or "/docs"
        if docs_url and (_has_path(route_paths, docs_url) or docs_url == "/docs"):
            add("studio", "api_docs", "ok", "API docs available", path=docs_url)
        else:
            add("studio", "api_docs", "warning", "API docs route not registered", "Enable docs_url on the app")

        if _has_path(route_paths, "/ai/tools/mcp"):
            add("studio", "mcp_catalog", "ok", "MCP catalog route registered")
        else:
            add(
                "studio",
                "mcp_catalog",
                "warning",
                "MCP catalog route not registered",
                "Ensure AI routes are mounted by the Aksara app",
            )
    else:
        add(
            "studio",
            "routes",
            "skipped",
            "Route checks skipped because app could not be inspected",
            "Fix project imports, then rerun launch-check",
        )

    # AI readiness is optional for launch.
    if _has_ai_provider_configured(loaded_settings_module):
        add("ai", "provider_configured", "ok", "AI provider configured")
    else:
        add(
            "ai",
            "provider_configured",
            "warning",
            "No AI provider configured",
            "Run aksara ai-hub configure",
        )

    # Bundled examples
    examples_root = find_examples_root(root)
    required_examples = ["basic_app", "blog", "crm", "multitenant", "ai_providers"]
    if examples_root:
        for example_name in required_examples:
            example_path = examples_root / example_name
            if example_path.exists():
                add("examples", example_name, "ok", f"{example_name} available", path=str(example_path))
            else:
                add(
                    "examples",
                    example_name,
                    "warning",
                    f"{example_name} example not found",
                    "Install Aksara from a package that includes bundled examples",
                )
    else:
        add(
            "examples",
            "examples_root",
            "warning",
            "Bundled examples not found",
            "Reinstall aksara-framework or use the GitHub source checkout",
        )

    # Security / dev-mode clarity
    debug = _get_setting_bool(loaded_settings_module, "DEBUG", "debug", default=False)
    if debug:
        add("security", "dev_mode", "ok", "Development mode enabled")
    else:
        add(
            "security",
            "dev_mode",
            "warning",
            "Debug/dev mode is off",
            "Set AKSARA_DEBUG=true for a first local Studio run",
        )

    next_steps = _build_next_steps(checks)
    status = _status_from_checks(checks)
    return LaunchCheckReport(
        ok=status == "ready",
        status=status,
        version=version,
        checks=checks,
        next_steps=next_steps,
    )


def find_examples_root(start: str | Path | None = None) -> Path | None:
    """Find examples in source checkout or wheel-installed layouts."""

    root = Path(start or Path.cwd()).resolve()
    candidates: list[Path] = []
    for parent in [root, *root.parents]:
        candidates.append(parent / "examples")
        if parent.name == "examples":
            candidates.append(parent)

    try:
        import aksara

        package_examples = Path(aksara.__file__).resolve().parent / "_examples"
        candidates.append(package_examples)
    except Exception:
        pass

    for candidate in candidates:
        if (candidate / "basic_app").exists() and (candidate / "blog").exists():
            return candidate
    return None


def _get_aksara_version() -> str:
    try:
        from aksara import __version__

        return __version__
    except Exception:
        return "unknown"


def _is_project_root(root: Path) -> bool:
    if (root / "main.py").exists() or (root / "settings.py").exists():
        return True
    if (root / "pyproject.toml").exists() and (root / "aksara").is_dir():
        return True
    return False


def _preferred_module_name(root: Path, stem: str) -> str | None:
    if not (root / f"{stem}.py").exists():
        return None
    package_parts: list[str] = []
    cursor = root
    while (cursor / "__init__.py").exists():
        package_parts.insert(0, cursor.name)
        cursor = cursor.parent
    if package_parts:
        return ".".join([*package_parts, stem])
    return stem


def _import_base_path(root: Path) -> Path:
    cursor = root
    while (cursor / "__init__.py").exists():
        cursor = cursor.parent
    return cursor


@contextmanager
def _temporary_sys_path(path: Path):
    value = str(path)
    added = value not in sys.path
    if added:
        sys.path.insert(0, value)
    try:
        yield
    finally:
        if added:
            try:
                sys.path.remove(value)
            except ValueError:
                pass


def _import_from_root(root: Path, module_name: str) -> Any:
    with _temporary_sys_path(_import_base_path(root)):
        return importlib.import_module(module_name)


def _get_database_url(settings_module: Any | None) -> str | None:
    module_url = getattr(settings_module, "DATABASE_URL", None) if settings_module else None
    if module_url:
        return str(module_url)
    module_settings = getattr(settings_module, "settings", None) if settings_module else None
    module_settings_url = getattr(module_settings, "database_url", None)
    if module_settings_url:
        return str(module_settings_url)
    if settings_module is not None:
        return os.environ.get("AKSARA_DATABASE_URL") or os.environ.get("DATABASE_URL")
    try:
        from aksara.conf import settings

        if settings.database_url:
            return str(settings.database_url)
    except Exception:
        pass
    return os.environ.get("AKSARA_DATABASE_URL") or os.environ.get("DATABASE_URL")


def _run_database_probe(database_url: str, timeout: float) -> set[str]:
    async def _probe() -> set[str]:
        import asyncpg

        conn = await asyncpg.connect(database_url, timeout=timeout)
        try:
            await conn.fetchval("SELECT 1")
            table_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'aksara_migrations'
                )
                """
            )
            if not table_exists:
                return set()
            rows = await conn.fetch("SELECT name FROM aksara_migrations")
            return {str(row["name"]) for row in rows}
        finally:
            await conn.close()

    return asyncio.run(_probe())


def _find_migration_files(root: Path, settings_module: Any | None) -> list[str]:
    configured_dir = getattr(settings_module, "MIGRATIONS_DIR", None) if settings_module else None
    if configured_dir is None:
        try:
            from aksara.conf import settings

            configured_dir = settings.migrations_dir
        except Exception:
            configured_dir = "migrations"

    migrations_dir = Path(str(configured_dir))
    if not migrations_dir.is_absolute():
        migrations_dir = root / migrations_dir

    files: list[Path] = []
    if migrations_dir.exists():
        files.extend(path for path in migrations_dir.iterdir() if _is_migration_file(path))
    else:
        for child in root.iterdir() if root.exists() else []:
            child_migrations = child / "migrations"
            if child_migrations.exists():
                files.extend(path for path in child_migrations.iterdir() if _is_migration_file(path))

    return sorted(path.stem for path in files)


def _is_migration_file(path: Path) -> bool:
    if not path.is_file() or path.name == "__init__.py":
        return False
    return path.suffix in {".py", ".sql"}


def _route_paths(app: Any | None) -> set[str]:
    paths: set[str] = set()
    for route in getattr(app, "routes", []) or []:
        path = getattr(route, "path", None)
        if path:
            paths.add(path)
    return paths


def _has_path(paths: Iterable[str], expected: str) -> bool:
    return expected in set(paths)


def _has_ai_provider_configured(settings_module: Any | None) -> bool:
    provider_envs = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "OLLAMA_BASE_URL",
        "AKSARA_OLLAMA_BASE_URL",
    ]
    if any(os.environ.get(name) for name in provider_envs):
        return True

    for attr in ("AI_DEFAULT_PROVIDER", "ai_default_provider", "default_provider"):
        value = getattr(settings_module, attr, None) if settings_module else None
        if value:
            return True

    module_settings = getattr(settings_module, "settings", None) if settings_module else None
    if module_settings is not None:
        for attr in ("AI_DEFAULT_PROVIDER", "ai_default_provider", "default_provider"):
            if getattr(module_settings, attr, None):
                return True
        return False
    if settings_module is not None:
        return False

    try:
        from aksara.conf import settings

        if getattr(settings, "ai_default_provider", None):
            return True
        providers = getattr(settings, "ai_providers", None)
        if providers:
            return True
    except Exception:
        pass

    return False


def _get_setting_bool(
    settings_module: Any | None,
    module_attr: str,
    settings_attr: str,
    *,
    default: bool,
) -> bool:
    if settings_module is not None and hasattr(settings_module, module_attr):
        return bool(getattr(settings_module, module_attr))
    try:
        from aksara.conf import settings

        return bool(getattr(settings, settings_attr, default))
    except Exception:
        return default


def _redact_database_url(database_url: str) -> str:
    try:
        parts = urlsplit(database_url)
        if not parts.password:
            return database_url
        username = parts.username or ""
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
        netloc = f"{username}:***@{host}{port}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return "<redacted>"


def _status_from_checks(checks: list[LaunchCheckItem]) -> str:
    if any(check.status == "error" for check in checks):
        return "blocked"
    if any(check.status in {"warning", "skipped"} for check in checks):
        return "partial"
    return "ready"


def _build_next_steps(checks: list[LaunchCheckItem]) -> list[str]:
    steps: list[str] = []

    def add_step(step: str) -> None:
        if step not in steps:
            steps.append(step)

    for check in checks:
        if check.status not in {"warning", "error", "skipped"}:
            continue
        if check.category == "database" and check.name == "database_url":
            add_step("Configure DATABASE_URL")
        elif check.category == "database" and check.name == "connection":
            add_step("Verify PostgreSQL is running and credentials are correct")
        elif check.category == "database" and check.name == "migrations":
            add_step("Run aksara migrate")
        elif check.category == "ai":
            add_step("Configure AI provider optionally")
        elif check.category == "studio":
            add_step("Start Studio with aksara dev")
        elif check.category == "project":
            add_step("Fix project imports and settings")
        elif check.category == "security":
            add_step("Set AKSARA_DEBUG=true for local first-run checks")
        elif check.hint:
            add_step(check.hint)

    return steps
