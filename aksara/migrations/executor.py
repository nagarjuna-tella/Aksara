"""
Aksara Migration Executor

Handles loading, tracking, and executing migrations against the database.
Includes support for migration graph building and conflict detection.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, TYPE_CHECKING

from aksara.migrations.base import Migration
from aksara.migrations.graph import MigrationGraph, MigrationNode, find_conflicts

if TYPE_CHECKING:
    from aksara.migrations.graph import MigrationGraph

logger = logging.getLogger(__name__)


# =============================================================================
# Migration History Table
# =============================================================================

MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS aksara_migrations (
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
            ALTER TABLE aksara_migrations 
            ALTER COLUMN checksum DROP NOT NULL
        """)
    except Exception:
        pass  # Column already nullable or doesn't exist


def _compute_file_checksum(path: Path) -> str:
    """SHA-256 checksum of a migration file, truncated to 16 hex chars."""
    import hashlib

    data = _normalize_checksum_bytes(path.read_bytes())
    return hashlib.sha256(data).hexdigest()[:16]


def _normalize_checksum_bytes(data: bytes) -> bytes:
    """Normalise migration file line endings before checksum hashing."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


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
        "SELECT name FROM aksara_migrations ORDER BY applied_at, id"
    )
    return [row['name'] for row in rows]


async def get_applied_migration_records(connection) -> Dict[str, Optional[str]]:
    """
    Get applied migrations with their stored checksums.

    Returns:
        Dict mapping migration name → stored checksum (or None if not stored).
    """
    await ensure_migrations_table(connection)
    rows = await connection.fetch(
        "SELECT name, checksum FROM aksara_migrations ORDER BY applied_at, id"
    )
    return {row["name"]: row["checksum"] for row in rows}


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
        "INSERT INTO aksara_migrations (name, checksum) VALUES ($1, $2)",
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
        "DELETE FROM aksara_migrations WHERE name = $1",
        name,
    )


# =============================================================================
# Migration Discovery
# =============================================================================

# Internal migration packages (auto-discovered)
INTERNAL_MIGRATION_PACKAGES = [
    "aksara.contrib.auth.migrations",
]


def discover_migrations(migrations_path: Path) -> List[Tuple[str, Path]]:
    """
    Discover all migration files in a directory.

    Supports both:
        - Python migrations (.py files with Migration class)
        - Legacy SQL migrations (.sql files)

    Args:
        migrations_path: Path to migrations directory

    Returns:
        List of (migration_name, file_path) tuples sorted by name.
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

    # Sort once by name (includes timestamp for proper ordering).
    migrations.sort(key=lambda x: x[0])
    return migrations


def discover_internal_migrations() -> List[Tuple[str, Path]]:
    """
    Discover internal migrations from aksara packages.
    
    These are migrations bundled with aksara (e.g., aksara.contrib.auth)
    and are automatically applied when the package is used.
    
    Returns:
        List of (migration_name, file_path) tuples sorted by name
    """
    migrations = []
    
    for package_name in INTERNAL_MIGRATION_PACKAGES:
        try:
            # Import the migrations package
            package = importlib.import_module(package_name)
            package_path = Path(package.__file__).parent
            
            # Discover migrations in the package
            for f in package_path.glob("*.py"):
                if f.name.startswith("_"):
                    continue
                
                # Prefix with package name to avoid collisions
                name = f"{package_name.replace('.', '_')}_{f.stem}"
                migrations.append((name, f))
                
        except ImportError:
            # Package not available, skip
            continue
        except Exception as e:
            logger.warning(f"Error discovering migrations from {package_name}: {e}")
            continue

    migrations.sort(key=lambda x: x[0])
    return migrations


def discover_all_migrations(
    user_migrations_path: Optional[Path] = None,
    include_internal: bool = True,
) -> List[Tuple[str, Path]]:
    """
    Discover all migrations (user + internal).

    Internal migrations are applied first, then user migrations.

    Args:
        user_migrations_path: Path to user's migrations directory
        include_internal: Whether to include internal migrations

    Returns:
        List of (migration_name, file_path) tuples with internal migrations first
    """
    all_migrations: List[Tuple[str, Path]] = []

    # Internal migrations first (if enabled)
    if include_internal:
        all_migrations.extend(discover_internal_migrations())

    # User migrations
    if user_migrations_path is not None:
        all_migrations.extend(discover_migrations(user_migrations_path))

    return all_migrations


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
    module_name = f"aksara_migration_{file_path.stem}"
    
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
# Migration Graph Building
# =============================================================================

def extract_app_label_from_name(migration_name: str, file_path: Path) -> str:
    """
    Extract the app label from a migration name or path.
    
    For user migrations, the app label is typically the parent directory name.
    For internal migrations, it's extracted from the prefixed name.
    
    Args:
        migration_name: The migration name
        file_path: Path to the migration file
        
    Returns:
        The app label string
    """
    # Check if this is an internal migration (has package prefix)
    for pkg in INTERNAL_MIGRATION_PACKAGES:
        prefix = pkg.replace(".", "_") + "_"
        if migration_name.startswith(prefix):
            # Extract the app label from the package name (last component)
            return pkg.split(".")[-2] if len(pkg.split(".")) > 2 else pkg.split(".")[-1]
    
    # For user migrations, use the parent directory name
    parent = file_path.parent.name
    if parent == "migrations":
        # Go up one more level to get the app name
        grandparent = file_path.parent.parent.name
        return grandparent if grandparent else "default"
    
    return parent if parent else "default"


def build_migration_graph(
    migrations_path: Optional[Path] = None,
    include_internal: bool = True,
    migrations_list: Optional[List[Tuple[str, Path]]] = None,
    strict: bool = True,
) -> MigrationGraph:
    """
    Build a migration graph from discovered migrations.
    
    The graph tracks all migrations and their dependencies, enabling
    conflict detection and proper execution ordering.
    
    Args:
        migrations_path: Path to user's migrations directory
        include_internal: Whether to include internal migrations
        migrations_list: Optional pre-discovered list of migrations.
                        If provided, migrations_path is ignored.
        strict: When True, raise ValueError if a Python migration file
                cannot be loaded. When False, keep legacy best-effort
                behavior and add a dependency-less node.
        
    Returns:
        A MigrationGraph with all discovered migrations

    Raises:
        ValueError: If strict=True and a Python migration file cannot be loaded.
        
    Example:
        graph = build_migration_graph(Path("./migrations"))
        
        # Check for conflicts
        conflicts = find_conflicts(graph)
        if conflicts:
            print("Conflicts detected!")
            for app, heads in conflicts.items():
                print(f"  {app}: {[h.name for h in heads]}")
    """
    graph = MigrationGraph()
    
    # Discover or use provided migrations
    if migrations_list is not None:
        all_migrations = migrations_list
    else:
        all_migrations = discover_all_migrations(
            user_migrations_path=migrations_path,
            include_internal=include_internal,
        )
    
    # First pass: create nodes for all migrations
    migration_modules: Dict[str, Type[Migration]] = {}
    
    for name, path in all_migrations:
        if path.suffix != ".py":
            # SQL migrations don't have dependencies
            app_label = extract_app_label_from_name(name, path)
            node = MigrationNode(app_label=app_label, name=name)
            graph.add_node(node)
            continue
        
        try:
            # Load the migration module to get dependencies
            migration_class = load_migration_module(path)
            migration_modules[name] = migration_class
            
            # Get app label
            app_label = extract_app_label_from_name(name, path)
            
            # Get dependencies from the Migration class
            deps = getattr(migration_class, "dependencies", [])
            
            # Create node with dependencies
            node = MigrationNode(
                app_label=app_label,
                name=name,
                dependencies=list(deps) if deps else [],
            )
            graph.add_node(node)
            
        except Exception as e:
            app_label = extract_app_label_from_name(name, path)
            if strict:
                raise ValueError(
                    f"Could not load migration {app_label}.{name} from {path}: {e}"
                ) from e
            # Non-strict: warn and continue without dependencies (best-effort graph).
            logger.warning(f"Could not load migration {app_label}.{name} from {path}: {e}")
            node = MigrationNode(app_label=app_label, name=name)
            graph.add_node(node)
    
    # Build children relationships
    graph.build_children()
    
    return graph


def check_migration_conflicts(
    graph: MigrationGraph,
    applied: Optional[List[str]] = None,
) -> Dict[str, List[MigrationNode]]:
    """
    Check for migration conflicts that would block execution.
    
    A conflict exists when:
    - An app has multiple heads (migrations with no children)
    - At least one of those heads is not yet applied
    
    Args:
        graph: The migration graph
        applied: Optional list of already-applied migration names
        
    Returns:
        Dict of app_label -> list of conflicting head nodes
    """
    conflicts = find_conflicts(graph)
    
    if not conflicts or applied is None:
        return conflicts
    
    # Filter to only include conflicts where at least one head is unapplied
    applied_set = set(applied)
    real_conflicts = {}
    
    for app_label, heads in conflicts.items():
        unapplied_heads = [h for h in heads if h.name not in applied_set]
        if len(unapplied_heads) > 1:
            # Multiple unapplied heads = real conflict
            real_conflicts[app_label] = heads
        elif len(unapplied_heads) == 1 and len(heads) > 1:
            # One unapplied, but there are other heads = still a conflict
            real_conflicts[app_label] = heads
    
    return real_conflicts


# =============================================================================
# Migration Execution
# =============================================================================


from contextlib import asynccontextmanager


@asynccontextmanager
async def _raw_connection(connection):
    """Yield a raw asyncpg connection.

    `connection` can be either:
      - an asyncpg Connection/PoolConnectionProxy (already has `.transaction()`)
      - an Aksara Database wrapper (has `.acquire()` but not `.transaction()`)

    Callers that need a single pinned connection for advisory locking or
    transactions must go through this helper so both cases are handled.
    """
    if hasattr(connection, "transaction"):
        # Already a raw asyncpg connection — use as-is.
        yield connection
    else:
        # Database wrapper — acquire a dedicated connection from the pool.
        async with connection.acquire() as conn:
            yield conn


def _split_sql_statements(sql: str) -> list[str]:
    """Split a SQL script into individual statements on ';' boundaries.

    asyncpg's connection.execute() only runs the first statement in a
    multi-statement string.  This helper uses a character-level scanner that
    respects single-quoted strings, double-quoted identifiers, dollar-quoted
    blocks, line comments (--), and block comments (/* ... */) so that
    semicolons inside any of those constructs are never treated as statement
    delimiters.

    Raises:
        ValueError: If the SQL ends while still inside a block comment,
            single-quoted string, double-quoted identifier, or dollar-quoted
            block.
    """
    sql = sql.replace("\r\n", "\n").replace("\r", "\n")
    statements: list[str] = []
    current: list[str] = []
    i = 0
    n = len(sql)
    state = "normal"
    block_comment_depth = 0
    dollar_tag: str | None = None

    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        if state == "line_comment":
            if ch == "\n":
                current.append(ch)
                state = "normal"
            i += 1
            continue

        if state == "block_comment":
            if ch == "/" and nxt == "*":
                block_comment_depth += 1
                i += 2
                continue
            if ch == "*" and nxt == "/":
                block_comment_depth -= 1
                i += 2
                if block_comment_depth == 0:
                    state = "normal"
                continue
            i += 1
            continue

        if state == "single_quote":
            current.append(ch)
            i += 1
            if ch == "'":
                if i < n and sql[i] == "'":
                    current.append(sql[i])
                    i += 1
                else:
                    state = "normal"
            continue

        if state == "double_quote":
            current.append(ch)
            i += 1
            if ch == '"':
                if i < n and sql[i] == '"':
                    current.append(sql[i])
                    i += 1
                else:
                    state = "normal"
            continue

        if state == "dollar_quote":
            if dollar_tag is not None and sql.startswith(dollar_tag, i):
                current.extend(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                state = "normal"
                continue
            current.append(ch)
            i += 1
            continue

        # Line comment: skip to end of line (do not add to current statement)
        if ch == "-" and nxt == "-":
            state = "line_comment"
            i += 2
            continue

        # Block comment: skip /* ... */
        if ch == "/" and nxt == "*":
            state = "block_comment"
            block_comment_depth = 1
            current.append(" ")
            i += 2
            continue

        # Single-quoted string literal — copy verbatim, handling '' escape
        if ch == "'":
            state = "single_quote"
            current.append(ch)
            i += 1
            continue

        # Double-quoted identifier — copy verbatim, handling "" escape
        if ch == '"':
            state = "double_quote"
            current.append(ch)
            i += 1
            continue

        # Dollar-quoting: $$...$$  or  $tag$...$tag$
        if ch == "$":
            j = i + 1
            while j < n and sql[j] != "$":
                if not (sql[j].isalnum() or sql[j] == "_"):
                    break
                j += 1
            if j < n and sql[j] == "$":
                dollar_tag = sql[i : j + 1]
                current.extend(dollar_tag)
                state = "dollar_quote"
                i = j + 1
                continue

        # Statement delimiter
        if ch == ";":
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    if state == "block_comment":
        raise ValueError("Unterminated block comment in SQL migration")
    if state == "single_quote":
        raise ValueError("Unterminated single-quoted string in SQL migration")
    if state == "double_quote":
        raise ValueError("Unterminated double-quoted identifier in SQL migration")
    if state == "dollar_quote":
        raise ValueError("Unterminated dollar-quoted block in SQL migration")

    # Trailing statement without a terminating semicolon
    remainder = "".join(current).strip()
    if remainder:
        statements.append(remainder)

    return statements


async def apply_migration(
    connection,
    name: str,
    file_path: Path,
    *,
    fake: bool = False,
    verbose: bool = True,
    ensure_table: bool = True,
) -> bool:
    """
    Apply a single migration.
    
    Args:
        connection: Database connection
        name: Migration name
        file_path: Path to migration file
        fake: If True, record as applied without executing
        verbose: If True, print progress messages
        ensure_table: If True, ensure the migration tracking table exists
        
    Returns:
        True if successful, False otherwise
    """
    try:
        async with _raw_connection(connection) as conn:
            # ensure_migrations_table() is idempotent, and direct apply_migration()
            # calls need the tracking table before recording the migration.
            if ensure_table:
                await ensure_migrations_table(conn)

            if file_path.suffix == ".py":
                # Python migration: all operations + record_migration in one transaction
                # so a partial failure leaves the DB unchanged and the migration unrecorded.
                migration_class = load_migration_module(file_path)
                migration = migration_class()
                checksum = _compute_file_checksum(file_path)

                if not fake:
                    async with conn.transaction():
                        for op in migration.operations:
                            if verbose:
                                logger.info(f"  → {op.describe()}")
                            await op.apply(conn)
                        await record_migration(conn, name, checksum)
                else:
                    await record_migration(conn, name, checksum)

            elif file_path.suffix == ".sql":
                # SQL migration: split on statement boundaries so every statement runs,
                # then record_migration in the same transaction.
                # Use _compute_file_checksum so the checksum matches what integrity
                # verification will recompute from the file on disk.
                checksum = _compute_file_checksum(file_path)
                sql = file_path.read_text()

                if not fake:
                    statements = _split_sql_statements(sql)
                    async with conn.transaction():
                        for stmt in statements:
                            await conn.execute(stmt)
                        await record_migration(conn, name, checksum)
                else:
                    await record_migration(conn, name, checksum)

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
    include_internal: bool = True,
) -> Dict[str, Any]:
    """
    Apply all pending migrations.
    
    Args:
        connection: Database connection (Database instance or asyncpg connection)
        migrations_path: Path to migrations directory
        fake: If True, record as applied without executing
        verbose: If True, print progress messages
        include_internal: If True, include internal aksara migrations
        
    Returns:
        Dict with results:
            - applied: List of migrations applied in this run.
                        - skipped: List of migrations discovered for this run that were
                            already applied before this run.
            - pending_skipped: List of pending migrations not attempted
              because an earlier pending migration failed.
            - errors: List of (name, error) tuples.
                        - total_discovered: Total number of migrations discovered for this
                            run after include_internal filtering.
    """
    migrations_path = Path(migrations_path)

    # Pin to a single raw asyncpg connection for the entire migration run.
    # This is required because:
    #   1. Advisory locks are session-scoped — releasing the connection also
    #      releases the lock.
    #   2. The Database wrapper acquires a fresh pool connection per call, so
    #      we must hold one explicitly here.
    async with _raw_connection(connection) as conn:
        return await _apply_migrations_on_conn(
            conn,
            migrations_path,
            fake=fake,
            verbose=verbose,
            include_internal=include_internal,
        )


async def _apply_migrations_on_conn(
    conn,
    migrations_path: Path,
    *,
    fake: bool,
    verbose: bool,
    include_internal: bool,
) -> Dict[str, Any]:
    """Inner implementation of apply_migrations that works on a raw asyncpg connection."""
    # Acquire a session-level advisory lock so that two processes cannot run
    # migrations concurrently.  pg_try_advisory_lock() is non-blocking; if
    # another process holds the lock we fail fast rather than silently
    # double-applying.
    _ADVISORY_LOCK_KEY = "aksara_migrations"
    lock_acquired = await conn.fetchval(
        "SELECT pg_try_advisory_lock(hashtext($1))", _ADVISORY_LOCK_KEY
    )
    if not lock_acquired:
        raise RuntimeError(
            "Could not acquire Aksara migration advisory lock. Another migration "
            "process may already be running. Wait for that process to finish. If "
            "the lock appears stuck, identify the holding backend using "
            "pg_locks/pg_stat_activity and terminate that backend if appropriate."
        )

    try:
        # Ensure migrations table exists
        await ensure_migrations_table(conn)

        # Get applied migrations with checksums for integrity verification
        applied_records = await get_applied_migration_records(conn)
        applied = list(applied_records.keys())

        # Discover migrations used for this execution run.
        execution_migrations = discover_all_migrations(
            user_migrations_path=migrations_path,
            include_internal=include_internal,
        )
        execution_names = {name for name, _ in execution_migrations}
        skipped_for_run = [name for name in applied_records if name in execution_names]
        known_migrations = execution_migrations
        if not include_internal:
            known_migrations = discover_all_migrations(
                user_migrations_path=migrations_path,
                include_internal=True,
            )

        # Warn about applied migration records that no longer have a file on disk.
        # This is advisory: the migration ran successfully in the past, but the
        # file has since been deleted.  We warn rather than fail so that teams
        # can clean up tracking rows deliberately.
        discovered_names = {name for name, _ in known_migrations}
        for applied_name in applied_records:
            if applied_name not in discovered_names:
                logger.warning(
                    f"Applied migration {applied_name!r} is recorded in the database "
                    "but its file was not found on disk. "
                    "If you intentionally deleted the file, remove the tracking row "
                    "manually with a parameterized query: "
                    "DELETE FROM aksara_migrations WHERE name = $1; "
                    f"migration name: {applied_name!r}"
                )

        # Verify checksums of already-applied migrations whose files are still present.
        # A mismatch means an applied migration file was edited, which is unsafe.
        applied_by_name = {
            name: path for name, path in known_migrations if name in applied_records
        }
        for mig_name, mig_path in applied_by_name.items():
            stored = applied_records.get(mig_name)
            if stored is None:
                # Migrated before checksums were introduced — allow but warn.
                logger.warning(
                    f"Checksum unavailable for previously applied migration {mig_name!r}. "
                    "It will not be verified."
                )
                continue
            current = _compute_file_checksum(mig_path)
            if current != stored:
                raise ValueError(
                    f"Migration checksum mismatch for {mig_name!r}.\n"
                    "The migration has already been applied but the file contents have changed.\n"
                    "Do not edit applied migrations. Create a new migration instead."
                )

        # Get pending migrations
        pending = get_pending_migrations(execution_migrations, applied)

        results: Dict[str, Any] = {
            "applied": [],
            "skipped": skipped_for_run,
            "pending_skipped": [],
            "errors": [],
            "total_discovered": len(execution_migrations),
        }

        if not pending:
            if verbose:
                logger.info("No pending migrations.")
            return results

        # Apply only pending migrations, but do so in dependency order.
        pending_by_name = {name: path for name, path in pending}
        ordered_pending = [
            (node.name, pending_by_name[node.name])
            for node in build_migration_graph(
                migrations_path=migrations_path,
                include_internal=include_internal,
                migrations_list=execution_migrations,
            ).execution_order()
            if node.name in pending_by_name
        ]

        if verbose:
            logger.info(f"Found {len(pending)} pending migration(s).")

        for i, (name, path) in enumerate(ordered_pending):
            try:
                if verbose:
                    action = "Marking" if fake else "Applying"
                    logger.info(f"\n{action}: {name}")

                await apply_migration(
                    conn,
                    name,
                    path,
                    fake=fake,
                    verbose=verbose,
                    ensure_table=False,
                )

                results["applied"].append(name)

                if verbose:
                    status = "marked as applied" if fake else "applied successfully"
                    logger.info(f"  ✓ {status}")

            except Exception as e:
                results["errors"].append((name, str(e)))
                if verbose:
                    logger.error(f"  ✗ Error: {e}")
                # Collect remaining pending migrations that will not be attempted
                skipped_remaining = [n for n, _ in ordered_pending[i + 1:]]
                results["pending_skipped"] = skipped_remaining
                if verbose and skipped_remaining:
                    logger.warning(
                        f"Skipping {len(skipped_remaining)} pending migration(s) "
                        f"because {name!r} failed:"
                    )
                    for skipped_name in skipped_remaining:
                        logger.warning(f"  - {skipped_name}")
                # Stop on first error
                break

        return results

    finally:
        # Always release the advisory lock, even if an error occurred mid-run.
        try:
            released = await conn.fetchval(
                "SELECT pg_advisory_unlock(hashtext($1))", _ADVISORY_LOCK_KEY
            )
            if released is False:
                logger.warning(
                    "Migration advisory lock was not held or could not be released by this session."
                )
        except Exception as e:
            logger.warning("Failed to release migration advisory lock: %s", e)


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

from aksara.migrations import Migration
from aksara.migrations import operations as op


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

from aksara.migrations import Migration
from aksara.migrations import operations as op


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
    Convert a Aksara Model class to a CreateTable operation code string.
    
    Args:
        model_class: A Aksara Model class
        
    Returns:
        Python code string for the CreateTable operation
    """
    from aksara.fields import (
        String, Integer, Boolean, DateTime, UUID, JSON,
        ForeignKey, OneToOne,
        Text, Email, URL, Decimal, Enum, Float, Date, Array,
        Vector,
        FileField as RuntimeFileField,
        ImageField as RuntimeImageField,
    )
    
    # Get table name (try both attributes)
    table_name = getattr(model_class, '__tablename__', None) or getattr(model_class, '_table_name', None)
    if not table_name:
        # Generate from class name
        name = model_class.__name__.lower()
        if name.endswith('y') and len(name) > 1 and name[-2] not in 'aeiou':
            table_name = name[:-1] + 'ies'
        elif name.endswith(('s', 'x', 'z', 'ch', 'sh')):
            table_name = name + 'es'
        else:
            table_name = name + 's'
    fields_code = []
    
    for field_name, field in model_class._fields.items():
        # Map Aksara fields to migration FieldOps
        # Note: OneToOne must be checked before ForeignKey (it inherits from FK)
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
        
        elif isinstance(field, OneToOne):
            # Must check before ForeignKey since OneToOne inherits from it
            try:
                target_model = field.to_model
                target_table = getattr(target_model, '__tablename__', None) or getattr(target_model, '_table_name', 'unknown')
            except Exception:
                target_table = "unknown"
            
            parts = [f"'{target_table}'"]
            parts.append(f"on_delete='{field.on_delete}'")
            if field.nullable:
                parts.append("nullable=True")
            
            field_name = field.db_column_name
            field_code = f"op.OneToOneField({', '.join(parts)})"
        
        elif isinstance(field, RuntimeImageField):
            parts = [f"{field.max_length}"]
            if field.nullable:
                parts.append("nullable=True")
            if field.unique:
                parts.append("unique=True")
            field_code = f"op.ImageField({', '.join(parts)})"

        elif isinstance(field, RuntimeFileField):
            parts = [f"{field.max_length}"]
            if field.nullable:
                parts.append("nullable=True")
            if field.unique:
                parts.append("unique=True")
            field_code = f"op.FileField({', '.join(parts)})"

        elif isinstance(field, Email):
            parts = [f"{field.max_length}"]
            if field.nullable:
                parts.append("nullable=True")
            if field.unique:
                parts.append("unique=True")
            field_code = f"op.EmailField({', '.join(parts)})"
        
        elif isinstance(field, URL):
            parts = []
            if field.nullable:
                parts.append("nullable=True")
            if field.unique:
                parts.append("unique=True")
            opts = ", ".join(parts)
            field_code = f"op.URLField({opts})" if opts else "op.URLField()"
        
        elif isinstance(field, String):
            parts = [f"{field.max_length}"]
            if field.nullable:
                parts.append("nullable=True")
            if field.unique:
                parts.append("unique=True")
            if field.default is not None and not callable(field.default):
                parts.append(f"default={field.default!r}")
            field_code = f"op.StringField({', '.join(parts)})"
        
        elif isinstance(field, Text):
            parts = []
            if field.nullable:
                parts.append("nullable=True")
            opts = ", ".join(parts)
            field_code = f"op.TextField({opts})" if opts else "op.TextField()"
        
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
        
        elif isinstance(field, Date):
            parts = []
            if field.nullable:
                parts.append("nullable=True")
            opts = ", ".join(parts)
            field_code = f"op.DateField({opts})" if opts else "op.DateField()"
        
        elif isinstance(field, JSON):
            parts = []
            if field.nullable:
                parts.append("nullable=True")
            if field.default is not None and not callable(field.default):
                parts.append(f"default={field.default!r}")
            opts = ", ".join(parts)
            field_code = f"op.JSONField({opts})" if opts else "op.JSONField()"

        elif isinstance(field, Vector):
            parts = []
            if field.dimensions is not None:
                parts.append(f"dimensions={field.dimensions}")
            if field.nullable:
                parts.append("nullable=True")
            if field.default is not None and not callable(field.default):
                parts.append(f"default={field.default!r}")
            opts = ", ".join(parts)
            field_code = f"op.VectorField({opts})" if opts else "op.VectorField()"
        
        elif isinstance(field, Decimal):
            parts = [f"{field.max_digits}", f"{field.decimal_places}"]
            if field.nullable:
                parts.append("nullable=True")
            if field.unique:
                parts.append("unique=True")
            field_code = f"op.DecimalField({', '.join(parts)})"
        
        elif isinstance(field, Float):
            parts = []
            if field.nullable:
                parts.append("nullable=True")
            if field.default is not None and not callable(field.default):
                parts.append(f"default={field.default!r}")
            opts = ", ".join(parts)
            field_code = f"op.FloatField({opts})" if opts else "op.FloatField()"
        
        elif isinstance(field, Enum):
            parts = []
            enum_name = field.enum_class.__name__ if field.enum_class else 'Unknown'
            # Get allowed values from the enum class
            try:
                allowed_values = [e.value for e in field.enum_class]
            except Exception:
                allowed_values = []
            if field.nullable:
                parts.append("nullable=True")
            if field.default is not None:
                if isinstance(field.default, field.enum_class):
                    parts.append(f"default='{field.default.value}'")
                else:
                    parts.append(f"default={field.default!r}")
            opts = ", ".join(parts)
            av_repr = repr(allowed_values)
            if opts:
                field_code = f"op.EnumField({av_repr}, enum_name='{enum_name}', {opts})"
            else:
                field_code = f"op.EnumField({av_repr}, enum_name='{enum_name}')"
        
        elif isinstance(field, Array):
            sql_type = Array.TYPE_MAP.get(field.item_type, "TEXT[]")
            parts = [f"sql_type={sql_type!r}"]
            if not field.nullable:
                parts.append("nullable=False")
            if field.default is not None and not callable(field.default):
                parts.append(f"default={field.default!r}")
            field_code = f"op.ArrayField({', '.join(parts)})"
        
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
        
        else:
            # Fallback for unknown field types
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
