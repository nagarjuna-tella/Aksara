"""
Aksara Migrations Package

Operation-based migration system for Aksara ORM.
Provides Django-style migrations with Python files and structured operations.

Example usage:
    from aksara.migrations import Migration, operations as op
    
    class Migration(Migration):
        dependencies = []
        operations = [
            op.CreateTable(
                name="users",
                fields=[
                    ("id", op.UUIDField(primary_key=True)),
                    ("email", op.StringField(unique=True)),
                    ("is_active", op.BooleanField(default=True)),
                ],
            ),
        ]
"""

from aksara.migrations.base import Migration
from aksara.migrations import operations
from aksara.migrations.executor import (
    apply_migrations,
    get_applied_migrations,
    get_pending_migrations,
    discover_migrations,
    discover_internal_migrations,
    discover_all_migrations,
    build_migration_graph,
    check_migration_conflicts,
)
from aksara.migrations.graph import (
    MigrationGraph,
    MigrationNode,
    find_conflicts,
    format_conflict_message,
)
from aksara.migrations.autodetector import (
    detect_changes,
    build_state_from_migrations,
    build_state_from_models,
    diff_states,
)

__all__ = [
    "Migration",
    "operations",
    "apply_migrations",
    "get_applied_migrations",
    "get_pending_migrations",
    "discover_migrations",
    "discover_internal_migrations",
    "discover_all_migrations",
    # v0.3.16: Graph and conflict detection
    "build_migration_graph",
    "check_migration_conflicts",
    "MigrationGraph",
    "MigrationNode",
    "find_conflicts",
    "format_conflict_message",
    # v0.5.26: Autodetector
    "detect_changes",
    "build_state_from_migrations",
    "build_state_from_models",
    "diff_states",
]
