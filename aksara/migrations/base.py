"""
Aksara Migration Base Class

Defines the base Migration class that all migration files subclass.
"""

from __future__ import annotations

from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from aksara.migrations.operations import Operation


class Migration:
    """
    A single migration consisting of an ordered list of operations.
    
    Each migration file defines a subclass of this class with:
        - dependencies: List of (app_label, migration_name) tuples for ordering
        - operations: List of Operation instances to apply
    
    Example:
        from aksara.migrations import Migration, operations as op
        
        class Migration(Migration):
            dependencies = []
            operations = [
                op.CreateTable(
                    name="users",
                    fields=[
                        ("id", op.UUIDField(primary_key=True)),
                        ("email", op.StringField(unique=True)),
                    ],
                ),
            ]
    """
    
    # List of dependencies as (app_label, migration_name) tuples
    # For future multi-app support
    dependencies: List[Tuple[str, str]] = []
    
    # List of operations to apply in this migration
    operations: List["Operation"] = []
    
    def __init__(self):
        """Initialize the migration instance."""
        # Ensure operations is a copy to avoid shared state
        if not hasattr(self, '_initialized'):
            self._initialized = True
    
    def __repr__(self) -> str:
        return f"<Migration operations={len(self.operations)}>"
