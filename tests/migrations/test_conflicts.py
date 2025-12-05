"""
Tests for Migration Conflict Detection and Resolution (v0.3.16)

Tests the migration graph, conflict detection, and merge migration creation.
"""

import pytest
import os
import tempfile
from pathlib import Path

from vidyut.migrations.graph import (
    MigrationNode,
    MigrationGraph,
    find_conflicts,
    format_conflict_message,
)
from vidyut.migrations.executor import (
    build_migration_graph,
    check_migration_conflicts,
    discover_migrations,
)


# =============================================================================
# MigrationNode Tests
# =============================================================================

class TestMigrationNode:
    """Tests for MigrationNode dataclass."""
    
    def test_node_creation(self):
        node = MigrationNode(app_label="blog", name="0001_initial")
        assert node.app_label == "blog"
        assert node.name == "0001_initial"
        assert node.dependencies == []
        assert node.children == []
    
    def test_node_key(self):
        node = MigrationNode(app_label="blog", name="0001_initial")
        assert node.key == ("blog", "0001_initial")
    
    def test_node_with_dependencies(self):
        node = MigrationNode(
            app_label="blog",
            name="0002_add_author",
            dependencies=[("blog", "0001_initial")]
        )
        assert len(node.dependencies) == 1
        assert node.dependencies[0] == ("blog", "0001_initial")
    
    def test_node_equality(self):
        node1 = MigrationNode(app_label="blog", name="0001_initial")
        node2 = MigrationNode(app_label="blog", name="0001_initial")
        node3 = MigrationNode(app_label="blog", name="0002_add_author")
        
        assert node1 == node2
        assert node1 != node3
    
    def test_node_hash(self):
        node1 = MigrationNode(app_label="blog", name="0001_initial")
        node2 = MigrationNode(app_label="blog", name="0001_initial")
        
        # Should be usable in sets
        nodes = {node1, node2}
        assert len(nodes) == 1
    
    def test_node_repr(self):
        node = MigrationNode(app_label="blog", name="0001_initial")
        assert "blog" in repr(node)
        assert "0001_initial" in repr(node)


# =============================================================================
# MigrationGraph Tests
# =============================================================================

class TestMigrationGraph:
    """Tests for MigrationGraph class."""
    
    def test_empty_graph(self):
        graph = MigrationGraph()
        assert len(graph) == 0
        assert graph.get_app_labels() == set()
    
    def test_add_node(self):
        graph = MigrationGraph()
        node = MigrationNode(app_label="blog", name="0001_initial")
        graph.add_node(node)
        
        assert len(graph) == 1
        assert graph.get_node("blog", "0001_initial") is not None
    
    def test_add_duplicate_node(self):
        graph = MigrationGraph()
        node1 = MigrationNode(app_label="blog", name="0001_initial")
        node2 = MigrationNode(app_label="blog", name="0001_initial")
        
        graph.add_node(node1)
        graph.add_node(node2)  # Should be ignored
        
        assert len(graph) == 1
    
    def test_get_app_labels(self):
        graph = MigrationGraph()
        graph.add_node(MigrationNode(app_label="blog", name="0001_initial"))
        graph.add_node(MigrationNode(app_label="users", name="0001_initial"))
        graph.add_node(MigrationNode(app_label="blog", name="0002_add_author"))
        
        labels = graph.get_app_labels()
        assert labels == {"blog", "users"}
    
    def test_nodes_for_app(self):
        graph = MigrationGraph()
        graph.add_node(MigrationNode(app_label="blog", name="0001_initial"))
        graph.add_node(MigrationNode(app_label="blog", name="0002_add_author"))
        graph.add_node(MigrationNode(app_label="users", name="0001_initial"))
        
        blog_nodes = graph.nodes_for_app("blog")
        assert len(blog_nodes) == 2
        
        users_nodes = graph.nodes_for_app("users")
        assert len(users_nodes) == 1
    
    def test_build_children(self):
        graph = MigrationGraph()
        
        node1 = MigrationNode(app_label="blog", name="0001_initial")
        node2 = MigrationNode(
            app_label="blog", 
            name="0002_add_author",
            dependencies=[("blog", "0001_initial")]
        )
        
        graph.add_node(node1)
        graph.add_node(node2)
        graph.build_children()
        
        # node1 should have node2 as a child
        assert ("blog", "0002_add_author") in node1.children
        # node2 should have no children
        assert len(node2.children) == 0
    
    def test_roots_for_app(self):
        graph = MigrationGraph()
        
        # Root node (no dependencies)
        node1 = MigrationNode(app_label="blog", name="0001_initial")
        # Non-root (has dependency)
        node2 = MigrationNode(
            app_label="blog",
            name="0002_add_author",
            dependencies=[("blog", "0001_initial")]
        )
        
        graph.add_node(node1)
        graph.add_node(node2)
        graph.build_children()
        
        roots = graph.roots_for_app("blog")
        assert len(roots) == 1
        assert roots[0].name == "0001_initial"
    
    def test_heads_for_app_single_head(self):
        """Test linear chain has single head."""
        graph = MigrationGraph()
        
        node1 = MigrationNode(app_label="blog", name="0001_initial")
        node2 = MigrationNode(
            app_label="blog",
            name="0002_add_author",
            dependencies=[("blog", "0001_initial")]
        )
        node3 = MigrationNode(
            app_label="blog",
            name="0003_add_title",
            dependencies=[("blog", "0002_add_author")]
        )
        
        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_node(node3)
        graph.build_children()
        
        heads = graph.heads_for_app("blog")
        assert len(heads) == 1
        assert heads[0].name == "0003_add_title"
    
    def test_heads_for_app_multiple_heads(self):
        """Test branching creates multiple heads (conflict)."""
        graph = MigrationGraph()
        
        # Common ancestor
        node1 = MigrationNode(app_label="blog", name="0001_initial")
        node2 = MigrationNode(
            app_label="blog",
            name="0002_add_body",
            dependencies=[("blog", "0001_initial")]
        )
        
        # Two branches from node2
        node3a = MigrationNode(
            app_label="blog",
            name="0003_add_title",
            dependencies=[("blog", "0002_add_body")]
        )
        node3b = MigrationNode(
            app_label="blog",
            name="0003_add_status",
            dependencies=[("blog", "0002_add_body")]
        )
        
        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_node(node3a)
        graph.add_node(node3b)
        graph.build_children()
        
        heads = graph.heads_for_app("blog")
        assert len(heads) == 2
        head_names = {h.name for h in heads}
        assert head_names == {"0003_add_title", "0003_add_status"}
    
    def test_execution_order_linear(self):
        graph = MigrationGraph()
        
        node3 = MigrationNode(
            app_label="blog",
            name="0003_add_title",
            dependencies=[("blog", "0002_add_body")]
        )
        node1 = MigrationNode(app_label="blog", name="0001_initial")
        node2 = MigrationNode(
            app_label="blog",
            name="0002_add_body",
            dependencies=[("blog", "0001_initial")]
        )
        
        # Add in wrong order
        graph.add_node(node3)
        graph.add_node(node1)
        graph.add_node(node2)
        graph.build_children()
        
        order = graph.execution_order("blog")
        names = [n.name for n in order]
        
        # Should be in dependency order
        assert names.index("0001_initial") < names.index("0002_add_body")
        assert names.index("0002_add_body") < names.index("0003_add_title")


# =============================================================================
# Conflict Detection Tests
# =============================================================================

class TestFindConflicts:
    """Tests for find_conflicts function."""
    
    def test_no_conflicts_linear(self):
        graph = MigrationGraph()
        
        node1 = MigrationNode(app_label="blog", name="0001_initial")
        node2 = MigrationNode(
            app_label="blog",
            name="0002_add_author",
            dependencies=[("blog", "0001_initial")]
        )
        
        graph.add_node(node1)
        graph.add_node(node2)
        graph.build_children()
        
        conflicts = find_conflicts(graph)
        assert conflicts == {}
    
    def test_conflict_detected(self):
        """Test that branching migrations are detected as conflicts."""
        graph = MigrationGraph()
        
        node1 = MigrationNode(app_label="blog", name="0001_initial")
        node2 = MigrationNode(
            app_label="blog",
            name="0002_add_body",
            dependencies=[("blog", "0001_initial")]
        )
        node3a = MigrationNode(
            app_label="blog",
            name="0003_add_title",
            dependencies=[("blog", "0002_add_body")]
        )
        node3b = MigrationNode(
            app_label="blog",
            name="0003_add_status",
            dependencies=[("blog", "0002_add_body")]
        )
        
        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_node(node3a)
        graph.add_node(node3b)
        graph.build_children()
        
        conflicts = find_conflicts(graph)
        
        assert "blog" in conflicts
        assert len(conflicts["blog"]) == 2
        conflict_names = {h.name for h in conflicts["blog"]}
        assert conflict_names == {"0003_add_title", "0003_add_status"}
    
    def test_multiple_apps_one_conflict(self):
        """Test that only conflicting apps are reported."""
        graph = MigrationGraph()
        
        # Blog has conflict
        graph.add_node(MigrationNode(app_label="blog", name="0001_initial"))
        graph.add_node(MigrationNode(
            app_label="blog",
            name="0002_a",
            dependencies=[("blog", "0001_initial")]
        ))
        graph.add_node(MigrationNode(
            app_label="blog",
            name="0002_b",
            dependencies=[("blog", "0001_initial")]
        ))
        
        # Users is linear (no conflict)
        graph.add_node(MigrationNode(app_label="users", name="0001_initial"))
        graph.add_node(MigrationNode(
            app_label="users",
            name="0002_add_email",
            dependencies=[("users", "0001_initial")]
        ))
        
        graph.build_children()
        
        conflicts = find_conflicts(graph)
        
        assert "blog" in conflicts
        assert "users" not in conflicts
    
    def test_empty_graph_no_conflicts(self):
        graph = MigrationGraph()
        conflicts = find_conflicts(graph)
        assert conflicts == {}


class TestFormatConflictMessage:
    """Tests for format_conflict_message function."""
    
    def test_no_conflicts_message(self):
        message = format_conflict_message({})
        assert "No conflicts" in message
    
    def test_single_app_conflict_message(self):
        conflicts = {
            "blog": [
                MigrationNode(app_label="blog", name="0003_add_title"),
                MigrationNode(app_label="blog", name="0003_add_status"),
            ]
        }
        
        message = format_conflict_message(conflicts)
        
        assert "blog" in message
        assert "0003_add_title" in message
        assert "0003_add_status" in message
        assert "vidyut makemigrations --merge" in message
    
    def test_multiple_apps_conflict_message(self):
        conflicts = {
            "blog": [
                MigrationNode(app_label="blog", name="0002_a"),
                MigrationNode(app_label="blog", name="0002_b"),
            ],
            "users": [
                MigrationNode(app_label="users", name="0003_x"),
                MigrationNode(app_label="users", name="0003_y"),
            ],
        }
        
        message = format_conflict_message(conflicts)
        
        assert "blog" in message
        assert "users" in message


# =============================================================================
# Build Migration Graph Tests
# =============================================================================

class TestBuildMigrationGraph:
    """Tests for build_migration_graph function."""
    
    def test_build_from_empty_directory(self, tmp_path):
        graph = build_migration_graph(
            migrations_path=tmp_path,
            include_internal=False,
        )
        assert len(graph) == 0
    
    def test_build_from_single_migration(self, tmp_path):
        # Create a migration file
        migration_code = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = []
    operations = []
'''
        (tmp_path / "0001_initial.py").write_text(migration_code)
        
        graph = build_migration_graph(
            migrations_path=tmp_path,
            include_internal=False,
        )
        
        assert len(graph) == 1
    
    def test_build_with_dependencies(self, tmp_path):
        # Create a migrations subdirectory to control app_label
        mig_dir = tmp_path / "blog" / "migrations"
        mig_dir.mkdir(parents=True)
        
        # Create migration 1
        mig1 = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = []
    operations = []
'''
        (mig_dir / "0001_initial.py").write_text(mig1)
        
        # Create migration 2 with dependency
        mig2 = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = [("blog", "0001_initial")]
    operations = []
'''
        (mig_dir / "0002_add_author.py").write_text(mig2)
        
        graph = build_migration_graph(
            migrations_path=mig_dir,
            include_internal=False,
        )
        
        assert len(graph) == 2
        
        # Check dependencies are parsed
        node2 = graph.get_node("blog", "0002_add_author")
        assert node2 is not None
        assert len(node2.dependencies) == 1
    
    def test_build_detects_conflicts(self, tmp_path):
        """Integration test: build graph and detect conflicts."""
        # Create a migrations subdirectory
        mig_dir = tmp_path / "blog" / "migrations"
        mig_dir.mkdir(parents=True)
        
        # Create branching migrations
        mig1 = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = []
    operations = []
'''
        mig2 = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = [("blog", "0001_initial")]
    operations = []
'''
        mig3a = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = [("blog", "0002_add_body")]
    operations = []
'''
        mig3b = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = [("blog", "0002_add_body")]
    operations = []
'''
        
        (mig_dir / "0001_initial.py").write_text(mig1)
        (mig_dir / "0002_add_body.py").write_text(mig2)
        (mig_dir / "0003_add_title.py").write_text(mig3a)
        (mig_dir / "0003_add_status.py").write_text(mig3b)
        
        graph = build_migration_graph(
            migrations_path=mig_dir,
            include_internal=False,
        )
        
        conflicts = find_conflicts(graph)
        
        assert "blog" in conflicts
        assert len(conflicts["blog"]) == 2


class TestCheckMigrationConflicts:
    """Tests for check_migration_conflicts with applied filter."""
    
    def test_no_conflicts_all_applied(self, tmp_path):
        """If all conflicting heads are applied, no real conflict."""
        # Create a migrations subdirectory
        mig_dir = tmp_path / "blog" / "migrations"
        mig_dir.mkdir(parents=True)
        
        mig1 = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = []
    operations = []
'''
        mig2a = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = [("blog", "0001_initial")]
    operations = []
'''
        mig2b = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = [("blog", "0001_initial")]
    operations = []
'''
        
        (mig_dir / "0001_initial.py").write_text(mig1)
        (mig_dir / "0002_add_a.py").write_text(mig2a)
        (mig_dir / "0002_add_b.py").write_text(mig2b)
        
        graph = build_migration_graph(
            migrations_path=mig_dir,
            include_internal=False,
        )
        
        # All applied - no conflict
        applied = ["0001_initial", "0002_add_a", "0002_add_b"]
        conflicts = check_migration_conflicts(graph, applied)
        
        # When everything is applied, we shouldn't block
        # (the conflict message is informational)
        assert conflicts == {} or len(conflicts.get("blog", [])) == 0


# =============================================================================
# Merge Migration Tests
# =============================================================================

class TestMergeMigration:
    """Tests for merge migration creation."""
    
    def test_merge_resolves_conflict(self, tmp_path):
        """After creating merge migration, there should be one head."""
        # Create a migrations subdirectory
        mig_dir = tmp_path / "blog" / "migrations"
        mig_dir.mkdir(parents=True)
        
        # Create conflicting migrations
        mig1 = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = []
    operations = []
'''
        mig2a = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = [("blog", "0001_initial")]
    operations = []
'''
        mig2b = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = [("blog", "0001_initial")]
    operations = []
'''
        
        (mig_dir / "0001_initial.py").write_text(mig1)
        (mig_dir / "0002_add_a.py").write_text(mig2a)
        (mig_dir / "0002_add_b.py").write_text(mig2b)
        
        # Verify conflict exists
        graph = build_migration_graph(
            migrations_path=mig_dir,
            include_internal=False,
        )
        conflicts = find_conflicts(graph)
        assert "blog" in conflicts
        
        # Create merge migration manually (simulating CLI)
        merge_code = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = [
        ("blog", "0002_add_a"),
        ("blog", "0002_add_b"),
    ]
    operations = []
'''
        (mig_dir / "0003_merge.py").write_text(merge_code)
        
        # Rebuild graph
        graph = build_migration_graph(
            migrations_path=mig_dir,
            include_internal=False,
        )
        
        # Should now have single head
        heads = graph.heads_for_app("blog")
        assert len(heads) == 1
        assert heads[0].name == "0003_merge"
        
        # No conflicts
        conflicts = find_conflicts(graph)
        assert conflicts == {}


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_cross_app_dependencies(self, tmp_path):
        """Test migrations depending on other apps."""
        mig1 = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = []
    operations = []
'''
        mig2 = '''
from vidyut.migrations import Migration

class Migration(Migration):
    dependencies = [("users", "0001_initial")]  # Cross-app dependency
    operations = []
'''
        
        (tmp_path / "0001_initial.py").write_text(mig1)
        (tmp_path / "0002_add_author.py").write_text(mig2)
        
        # Should not crash
        graph = build_migration_graph(
            migrations_path=tmp_path,
            include_internal=False,
        )
        
        assert len(graph) == 2
    
    def test_sql_migrations_no_dependencies(self, tmp_path):
        """SQL migrations have no dependency tracking."""
        (tmp_path / "0001_initial.sql").write_text("CREATE TABLE test (id INT);")
        
        graph = build_migration_graph(
            migrations_path=tmp_path,
            include_internal=False,
        )
        
        assert len(graph) == 1
        node = list(graph.nodes.values())[0]
        assert node.dependencies == []
    
    def test_invalid_migration_file(self, tmp_path):
        """Invalid migration files should be handled gracefully."""
        (tmp_path / "0001_broken.py").write_text("this is not valid python :{")
        
        # Should not crash, but migration won't be loaded properly
        graph = build_migration_graph(
            migrations_path=tmp_path,
            include_internal=False,
        )
        
        # Node should still be added (but without dependencies)
        assert len(graph) == 1
    
    def test_migration_without_dependencies_attr(self, tmp_path):
        """Migration without dependencies attribute."""
        mig = '''
from vidyut.migrations import Migration

class Migration(Migration):
    operations = []
    # Note: no dependencies attribute
'''
        (tmp_path / "0001_initial.py").write_text(mig)
        
        graph = build_migration_graph(
            migrations_path=tmp_path,
            include_internal=False,
        )
        
        assert len(graph) == 1
        node = list(graph.nodes.values())[0]
        assert node.dependencies == []
