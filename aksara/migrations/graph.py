"""
Aksara Migration Graph

Provides a directed graph model for migration dependencies,
enabling conflict detection and resolution for team workflows.

The graph tracks:
- Migration nodes with their app_label and name
- Dependencies between migrations
- Parent-child relationships for conflict detection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class MigrationNode:
    """
    Represents a single migration in the graph.
    
    Attributes:
        app_label: The application this migration belongs to
        name: Migration name (e.g., "0001_initial")
        dependencies: List of (app_label, migration_name) this migration depends on
        children: List of (app_label, migration_name) that depend on this migration
                  (populated after graph.build_children())
    """
    app_label: str
    name: str
    dependencies: List[Tuple[str, str]] = field(default_factory=list)
    children: List[Tuple[str, str]] = field(default_factory=list)
    
    @property
    def key(self) -> Tuple[str, str]:
        """Unique identifier for this migration: (app_label, name)."""
        return (self.app_label, self.name)
    
    def __repr__(self) -> str:
        return f"<MigrationNode {self.app_label}.{self.name}>"
    
    def __hash__(self) -> int:
        return hash(self.key)
    
    def __eq__(self, other: object) -> bool:
        if isinstance(other, MigrationNode):
            return self.key == other.key
        return False


class MigrationGraph:
    """
    A directed acyclic graph (DAG) of migrations.
    
    The graph enables:
    - Tracking dependencies between migrations
    - Finding root migrations (no dependencies within an app)
    - Finding head migrations (no children within an app) 
    - Detecting conflicts when multiple heads exist
    - Computing linear execution order
    
    Example:
        graph = MigrationGraph()
        
        # Add migrations
        node1 = MigrationNode(app_label="blog", name="0001_initial")
        node2 = MigrationNode(
            app_label="blog", 
            name="0002_add_author",
            dependencies=[("blog", "0001_initial")]
        )
        
        graph.add_node(node1)
        graph.add_node(node2)
        graph.build_children()
        
        # Check for conflicts
        heads = graph.heads_for_app("blog")  # Should be just 0002_add_author
    """
    
    def __init__(self):
        """Initialize an empty migration graph."""
        self.nodes: Dict[Tuple[str, str], MigrationNode] = {}
    
    def add_node(self, node: MigrationNode) -> None:
        """
        Add a migration node to the graph.
        
        If the node already exists (same key), it will be skipped
        to allow idempotent graph building.
        
        Args:
            node: The MigrationNode to add
        """
        if node.key in self.nodes:
            # Already exists, don't overwrite
            return
        self.nodes[node.key] = node
    
    def get_node(self, app_label: str, name: str) -> Optional[MigrationNode]:
        """
        Get a node by its app_label and name.
        
        Args:
            app_label: The application label
            name: The migration name
            
        Returns:
            The MigrationNode if found, None otherwise
        """
        return self.nodes.get((app_label, name))
    
    def add_dependency(
        self, 
        app_label: str, 
        name: str, 
        dep_app: str, 
        dep_name: str
    ) -> None:
        """
        Add a dependency to an existing node.
        
        Args:
            app_label: App label of the migration
            name: Name of the migration
            dep_app: App label of the dependency
            dep_name: Name of the dependency migration
        """
        key = (app_label, name)
        if key not in self.nodes:
            raise KeyError(f"Migration {app_label}.{name} not found in graph")
        
        node = self.nodes[key]
        dep = (dep_app, dep_name)
        if dep not in node.dependencies:
            node.dependencies.append(dep)
    
    def build_children(self) -> None:
        """
        Populate children lists for all nodes based on dependencies.

        This must be called after all nodes are added and before
        querying for heads or detecting conflicts.
        """
        # Reset and rebuild via per-node sets to deduplicate in O(1) per insert.
        children_sets: Dict[Tuple[str, str], Set[Tuple[str, str]]] = {
            key: set() for key in self.nodes
        }

        for node in self.nodes.values():
            for dep_key in node.dependencies:
                if dep_key in children_sets:
                    children_sets[dep_key].add(node.key)

        # Persist as lists to preserve the public API.
        for key, node in self.nodes.items():
            node.children = list(children_sets[key])
    
    def get_app_labels(self) -> Set[str]:
        """
        Get all unique app labels in the graph.
        
        Returns:
            Set of app label strings
        """
        return {node.app_label for node in self.nodes.values()}
    
    def nodes_for_app(self, app_label: str) -> List[MigrationNode]:
        """
        Get all migration nodes for a specific app.
        
        Args:
            app_label: The application label
            
        Returns:
            List of MigrationNode objects for the app
        """
        return [
            node for node in self.nodes.values()
            if node.app_label == app_label
        ]
    
    def roots_for_app(self, app_label: str) -> List[MigrationNode]:
        """
        Get root migrations for an app (no dependencies within the app).
        
        Root migrations are starting points that don't depend on 
        any other migration within the same app.
        
        Args:
            app_label: The application label
            
        Returns:
            List of root MigrationNode objects
        """
        roots = []
        for node in self.nodes.values():
            if node.app_label != app_label:
                continue
            
            # Check if any dependency is within the same app
            has_internal_dep = any(
                dep_app == app_label 
                for dep_app, dep_name in node.dependencies
            )
            
            if not has_internal_dep:
                roots.append(node)
        
        return roots
    
    def heads_for_app(self, app_label: str) -> List[MigrationNode]:
        """
        Get head migrations for an app (no children within the app).
        
        Head migrations are the "latest" migrations that no other
        migration in the same app depends on. Multiple heads 
        indicate a conflict (parallel development branches).
        
        Args:
            app_label: The application label
            
        Returns:
            List of head MigrationNode objects
        """
        heads = []
        for node in self.nodes.values():
            if node.app_label != app_label:
                continue
            
            # Check if any child is within the same app
            has_internal_child = any(
                child_app == app_label 
                for child_app, child_name in node.children
            )
            
            if not has_internal_child:
                heads.append(node)
        
        return heads
    
    def leaf_nodes_for_app(self, app_label: str) -> List[MigrationNode]:
        """
        Alias for heads_for_app - returns migrations with no children.
        """
        return self.heads_for_app(app_label)
    
    def execution_order(self, app_label: Optional[str] = None) -> List[MigrationNode]:
        """
        Get migrations in execution order (topological sort).
        
        This respects dependencies so that a migration is only executed
        after all its dependencies have been executed.
        
        Args:
            app_label: Optional filter to only include one app
            
        Returns:
            List of MigrationNode in execution order
        """
        # Nodes to process
        if app_label:
            nodes = {node.key: node for node in self.nodes_for_app(app_label)}
        else:
            nodes = dict(self.nodes)
        
        # Track visited and result
        visited: Set[Tuple[str, str]] = set()
        result: List[MigrationNode] = []
        
        def visit(key: Tuple[str, str]) -> None:
            if key in visited:
                return
            if key not in nodes:
                return  # External dependency
            
            visited.add(key)
            node = nodes[key]
            
            # Visit dependencies first
            for dep in node.dependencies:
                visit(dep)
            
            result.append(node)
        
        # Visit all nodes
        for key in nodes:
            visit(key)
        
        return result
    
    def __repr__(self) -> str:
        return f"<MigrationGraph nodes={len(self.nodes)}>"
    
    def __len__(self) -> int:
        return len(self.nodes)


def find_conflicts(graph: MigrationGraph) -> Dict[str, List[MigrationNode]]:
    """
    Find apps with conflicting migrations (multiple heads).
    
    When multiple developers add migrations in parallel without
    merging, an app can end up with multiple "heads" - migrations
    that nothing depends on. This is a conflict that must be
    resolved before migrations can be applied.
    
    Args:
        graph: The migration graph to check
        
    Returns:
        Dict mapping app_label to list of conflicting head nodes.
        Only apps with >1 head are included.
        
    Example:
        conflicts = find_conflicts(graph)
        if conflicts:
            for app, heads in conflicts.items():
                print(f"App '{app}' has conflicts:")
                for head in heads:
                    print(f"  - {head.name}")
    """
    conflicts: Dict[str, List[MigrationNode]] = {}
    
    for app_label in graph.get_app_labels():
        heads = graph.heads_for_app(app_label)
        if len(heads) > 1:
            conflicts[app_label] = heads
    
    return conflicts


def format_conflict_message(conflicts: Dict[str, List[MigrationNode]]) -> str:
    """
    Format a human-readable conflict message.
    
    Args:
        conflicts: Dict from find_conflicts()
        
    Returns:
        Formatted string describing the conflicts
    """
    if not conflicts:
        return "No conflicts detected."
    
    lines = ["Conflicting migrations detected:\n"]
    
    for app_label, heads in conflicts.items():
        lines.append(f"\n  App '{app_label}' has {len(heads)} conflicting heads:")
        for head in sorted(heads, key=lambda h: h.name):
            lines.append(f"    • {app_label}.{head.name}")
    
    lines.append("\n")
    lines.append("This usually happens when multiple branches add migrations independently.")
    lines.append("To resolve, run:")
    
    for app_label in conflicts:
        lines.append(f"  aksara makemigrations --merge {app_label}")
    
    return "\n".join(lines)
