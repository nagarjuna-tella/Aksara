"""
Vidyut Migrations Package

Operation-based migration system for Vidyut ORM.
Provides Django-style migrations with Python files and structured operations.

Example usage:
    from vidyut.migrations import Migration, operations as op
    
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

from vidyut.migrations.base import Migration
from vidyut.migrations import operations
from vidyut.migrations.executor import (
    apply_migrations,
    get_applied_migrations,
    get_pending_migrations,
    discover_migrations,
    discover_internal_migrations,
    discover_all_migrations,
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
]
