"""
Tests for Migration Executor

Tests migration loading, execution, ordering, and database integration.
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from aksara.migrations import operations as op
from aksara.migrations import executor as migration_executor
from aksara.migrations.base import Migration
from aksara.migrations.executor import (
    discover_all_migrations,
    discover_migrations,
    load_migration_module,
    get_pending_migrations,
    generate_migration_filename,
    model_to_create_table,
    models_to_migration_code,
    ensure_migrations_table,
    get_applied_migrations,
    record_migration,
    apply_migration,
    apply_migrations,
)


# =============================================================================
# Discovery Tests
# =============================================================================

class TestDiscoverMigrations:
    """Tests for migration discovery."""
    
    def test_empty_directory(self, tmp_path):
        migrations = discover_migrations(tmp_path)
        assert migrations == []
    
    def test_nonexistent_directory(self, tmp_path):
        nonexistent = tmp_path / "nonexistent"
        migrations = discover_migrations(nonexistent)
        assert migrations == []
    
    def test_discover_python_migrations(self, tmp_path):
        # Create test migration files
        (tmp_path / "20250101_120000_initial.py").write_text("# migration")
        (tmp_path / "20250101_130000_add_users.py").write_text("# migration")
        
        migrations = discover_migrations(tmp_path)
        assert len(migrations) == 2
        assert migrations[0][0] == "20250101_120000_initial"
        assert migrations[1][0] == "20250101_130000_add_users"
    
    def test_discover_sql_migrations(self, tmp_path):
        (tmp_path / "20250101_120000_initial.sql").write_text("-- migration")
        
        migrations = discover_migrations(tmp_path)
        assert len(migrations) == 1
        assert migrations[0][0] == "20250101_120000_initial"
    
    def test_discover_mixed_migrations(self, tmp_path):
        (tmp_path / "20250101_120000_initial.py").write_text("# migration")
        (tmp_path / "20250101_130000_add_users.sql").write_text("-- migration")
        
        migrations = discover_migrations(tmp_path)
        assert len(migrations) == 2
    
    def test_ignore_underscored_files(self, tmp_path):
        (tmp_path / "__init__.py").write_text("")
        (tmp_path / "_helper.py").write_text("")
        (tmp_path / "20250101_120000_initial.py").write_text("# migration")
        
        migrations = discover_migrations(tmp_path)
        assert len(migrations) == 1
        assert migrations[0][0] == "20250101_120000_initial"
    
    def test_sorted_by_name(self, tmp_path):
        # Create in reverse order
        (tmp_path / "20250103_third.py").write_text("# 3")
        (tmp_path / "20250101_first.py").write_text("# 1")
        (tmp_path / "20250102_second.py").write_text("# 2")
        
        migrations = discover_migrations(tmp_path)
        assert migrations[0][0] == "20250101_first"
        assert migrations[1][0] == "20250102_second"
        assert migrations[2][0] == "20250103_third"

    def test_discover_all_migrations_keeps_internal_before_user(self, tmp_path, monkeypatch):
        internal_dir = tmp_path / "internal"
        internal_dir.mkdir()
        internal_path = internal_dir / "zz_internal.py"
        internal_path.write_text("# internal migration")
        user_path = tmp_path / "0001_user.py"
        user_path.write_text("# user migration")

        monkeypatch.setattr(
            migration_executor,
            "discover_internal_migrations",
            lambda: [("zz_internal", internal_path)],
        )

        migrations = discover_all_migrations(tmp_path, include_internal=True)

        assert [name for name, _ in migrations] == ["zz_internal", "0001_user"]


class TestLoadMigrationModule:
    """Tests for loading migration modules."""
    
    def test_load_valid_migration(self, tmp_path):
        migration_code = '''
from aksara.migrations import Migration
from aksara.migrations import operations as op

class Migration(Migration):
    operations = [
        op.CreateTable(
            name="test_table",
            fields=[("id", op.UUIDField(primary_key=True))],
        ),
    ]
'''
        file_path = tmp_path / "0001_test.py"
        file_path.write_text(migration_code)
        
        MigrationClass = load_migration_module(file_path)
        migration = MigrationClass()
        
        assert len(migration.operations) == 1
        assert isinstance(migration.operations[0], op.CreateTable)
    
    def test_load_migration_no_class(self, tmp_path):
        file_path = tmp_path / "0001_invalid.py"
        file_path.write_text("# No Migration class here")
        
        with pytest.raises(AttributeError, match="Migration"):
            load_migration_module(file_path)
    
    def test_load_migration_syntax_error(self, tmp_path):
        file_path = tmp_path / "0001_syntax.py"
        file_path.write_text("def broken( :")  # syntax error
        
        with pytest.raises(ImportError):
            load_migration_module(file_path)


class TestGetPendingMigrations:
    """Tests for determining pending migrations."""
    
    def test_all_pending(self, tmp_path):
        (tmp_path / "0001_first.py").write_text("")
        (tmp_path / "0002_second.py").write_text("")
        
        all_migrations = discover_migrations(tmp_path)
        applied = []
        
        pending = get_pending_migrations(all_migrations, applied)
        assert len(pending) == 2
    
    def test_none_pending(self, tmp_path):
        (tmp_path / "0001_first.py").write_text("")
        (tmp_path / "0002_second.py").write_text("")
        
        all_migrations = discover_migrations(tmp_path)
        applied = ["0001_first", "0002_second"]
        
        pending = get_pending_migrations(all_migrations, applied)
        assert len(pending) == 0
    
    def test_partial_pending(self, tmp_path):
        (tmp_path / "0001_first.py").write_text("")
        (tmp_path / "0002_second.py").write_text("")
        
        all_migrations = discover_migrations(tmp_path)
        applied = ["0001_first"]
        
        pending = get_pending_migrations(all_migrations, applied)
        assert len(pending) == 1
        assert pending[0][0] == "0002_second"


# =============================================================================
# Filename Generation Tests
# =============================================================================

class TestGenerateMigrationFilename:
    """Tests for migration filename generation."""
    
    def test_with_timestamp(self):
        filename = generate_migration_filename("initial")
        assert filename.endswith("_initial.py")
        # Should start with date like 20250129
        assert filename[:4].isdigit()
    
    def test_without_timestamp(self):
        filename = generate_migration_filename("initial", include_timestamp=False)
        assert filename == "initial.py"


# =============================================================================
# Model to Operations Tests
# =============================================================================

class TestModelToCreateTable:
    """Tests for converting models to CreateTable operations."""
    
    def test_basic_model(self):
        from aksara.model.base import Model
        from aksara import fields
        from aksara.registry import ModelRegistry
        
        # Clear registry to avoid conflicts
        ModelRegistry._models.clear()
        
        class SimpleModel(Model):
            id = fields.UUID(primary_key=True)
            name = fields.String(max_length=100)
        
        code = model_to_create_table(SimpleModel)
        
        assert "CreateTable" in code
        assert "UUIDField(primary_key=True)" in code
        assert "StringField" in code
        assert "100" in code  # max_length
        
        # Clean up
        ModelRegistry._models.clear()
    
    def test_model_with_boolean(self):
        from aksara.model.base import Model
        from aksara import fields
        from aksara.registry import ModelRegistry
        
        ModelRegistry._models.clear()
        
        class BoolModel(Model):
            id = fields.UUID(primary_key=True)
            is_active = fields.Boolean(default=True)
        
        code = model_to_create_table(BoolModel)
        
        assert "BooleanField" in code
        assert "default=True" in code
        
        ModelRegistry._models.clear()
    
    def test_model_with_datetime(self):
        from aksara.model.base import Model
        from aksara import fields
        from aksara.registry import ModelRegistry
        
        ModelRegistry._models.clear()
        
        class TimestampModel(Model):
            id = fields.UUID(primary_key=True)
            created_at = fields.DateTime(auto_now_add=True)
        
        code = model_to_create_table(TimestampModel)
        
        assert "DateTimeField" in code
        assert "auto_now_add=True" in code
        
        ModelRegistry._models.clear()


class TestModelsToMigrationCode:
    """Tests for converting multiple models to migration code."""
    
    def test_multiple_models(self):
        from aksara.model.base import Model
        from aksara import fields
        from aksara.registry import ModelRegistry
        
        ModelRegistry._models.clear()
        
        class UserTest(Model):
            id = fields.UUID(primary_key=True)
            email = fields.String(unique=True)
        
        class PostTest(Model):
            id = fields.UUID(primary_key=True)
            title = fields.String()
        
        models = {"UserTest": UserTest, "PostTest": PostTest}
        code = models_to_migration_code(models)
        
        assert "CreateTable" in code
        # Check for table names (lowercase pluralized)
        assert code.count("CreateTable") == 2
        
        ModelRegistry._models.clear()


# =============================================================================
# Database Integration Tests
# =============================================================================

@pytest.fixture
async def db():
    """Create a database connection for testing."""
    from aksara.db import Database
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set")
    
    database = Database(db_url)
    await database.connect()
    
    # Clean up any existing test tables
    await database.execute("DROP TABLE IF EXISTS test_migration_table CASCADE")
    await database.execute("DROP TABLE IF EXISTS test_users CASCADE")
    await database.execute("DROP TABLE IF EXISTS test_posts CASCADE")
    
    yield database
    
    # Cleanup
    await database.execute("DROP TABLE IF EXISTS test_migration_table CASCADE")
    await database.execute("DROP TABLE IF EXISTS test_users CASCADE")
    await database.execute("DROP TABLE IF EXISTS test_posts CASCADE")
    await database.execute("DELETE FROM aksara_migrations WHERE name LIKE 'test_%'")
    await database.disconnect()


@pytest.mark.asyncio
async def test_ensure_migrations_table(db):
    """Test that migrations table is created."""
    await ensure_migrations_table(db)
    
    # Verify table exists
    result = await db.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'aksara_migrations'
        )
    """)
    assert result is True


@pytest.mark.asyncio
async def test_get_applied_migrations_empty(db):
    """Test getting applied migrations when none exist."""
    await ensure_migrations_table(db)
    
    # Clear any existing test migrations
    await db.execute("DELETE FROM aksara_migrations WHERE name LIKE 'test_%'")
    
    applied = await get_applied_migrations(db)
    test_applied = [m for m in applied if m.startswith('test_')]
    assert test_applied == []


@pytest.mark.asyncio
async def test_record_and_get_migrations(db):
    """Test recording and retrieving migrations."""
    await ensure_migrations_table(db)
    
    # Record a test migration
    await record_migration(db, "test_20250101_initial")
    
    applied = await get_applied_migrations(db)
    assert "test_20250101_initial" in applied


@pytest.mark.asyncio
async def test_create_table_operation(db):
    """Test CreateTable operation execution."""
    create_op = op.CreateTable(
        name="test_users",
        fields=[
            ("id", op.UUIDField(primary_key=True)),
            ("email", op.StringField(unique=True)),
            ("is_active", op.BooleanField(default=True)),
            ("created_at", op.DateTimeField(auto_now_add=True)),
        ],
    )
    
    await create_op.apply(db)
    
    # Verify table exists
    result = await db.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'test_users'
        )
    """)
    assert result is True
    
    # Verify columns
    columns = await db.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'test_users'
        ORDER BY ordinal_position
    """)
    column_names = [c['column_name'] for c in columns]
    assert 'id' in column_names
    assert 'email' in column_names
    assert 'is_active' in column_names
    assert 'created_at' in column_names


@pytest.mark.asyncio
async def test_drop_table_operation(db):
    """Test DropTable operation execution."""
    # First create a table
    await db.execute("CREATE TABLE IF NOT EXISTS test_drop_me (id SERIAL)")
    
    drop_op = op.DropTable(name="test_drop_me")
    await drop_op.apply(db)
    
    # Verify table is gone
    result = await db.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'test_drop_me'
        )
    """)
    assert result is False


@pytest.mark.asyncio
async def test_add_field_operation(db):
    """Test AddField operation execution."""
    # Create initial table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS test_add_field (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid()
        )
    """)
    
    add_op = op.AddField(
        table="test_add_field",
        name="new_column",
        field=op.StringField(max_length=100, nullable=True),
    )
    await add_op.apply(db)
    
    # Verify column exists
    result = await db.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_name = 'test_add_field' AND column_name = 'new_column'
        )
    """)
    assert result is True
    
    # Cleanup
    await db.execute("DROP TABLE test_add_field")


@pytest.mark.asyncio
async def test_remove_field_operation(db):
    """Test RemoveField operation execution."""
    # Create table with column
    await db.execute("""
        CREATE TABLE IF NOT EXISTS test_remove_field (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            to_remove VARCHAR(100)
        )
    """)
    
    remove_op = op.RemoveField(table="test_remove_field", name="to_remove")
    await remove_op.apply(db)
    
    # Verify column is gone
    result = await db.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_name = 'test_remove_field' AND column_name = 'to_remove'
        )
    """)
    assert result is False
    
    # Cleanup
    await db.execute("DROP TABLE test_remove_field")


@pytest.mark.asyncio
async def test_run_sql_operation(db):
    """Test RunSQL operation execution."""
    run_op = op.RunSQL(sql="CREATE TABLE IF NOT EXISTS test_run_sql (id SERIAL)")
    await run_op.apply(db)
    
    # Verify table exists
    result = await db.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'test_run_sql'
        )
    """)
    assert result is True
    
    # Cleanup
    await db.execute("DROP TABLE test_run_sql")


@pytest.mark.asyncio
async def test_apply_migration_python(db, tmp_path):
    """Test applying a Python migration file."""
    migration_code = '''
from aksara.migrations import Migration
from aksara.migrations import operations as op

class Migration(Migration):
    operations = [
        op.CreateTable(
            name="test_python_mig",
            fields=[
                ("id", op.UUIDField(primary_key=True)),
                ("name", op.StringField()),
            ],
        ),
    ]
'''
    file_path = tmp_path / "test_0001_python.py"
    file_path.write_text(migration_code)
    
    await apply_migration(db, "test_0001_python", file_path)
    
    # Verify table exists
    result = await db.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'test_python_mig'
        )
    """)
    assert result is True
    
    # Verify recorded in migrations table
    applied = await get_applied_migrations(db)
    assert "test_0001_python" in applied
    
    # Cleanup
    await db.execute("DROP TABLE test_python_mig")


@pytest.mark.asyncio
async def test_apply_migration_sql(db, tmp_path):
    """Test applying a SQL migration file."""
    sql = "CREATE TABLE IF NOT EXISTS test_sql_mig (id SERIAL PRIMARY KEY)"
    file_path = tmp_path / "test_0002_sql.sql"
    file_path.write_text(sql)
    
    await apply_migration(db, "test_0002_sql", file_path)
    
    # Verify table exists
    result = await db.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'test_sql_mig'
        )
    """)
    assert result is True
    
    # Verify recorded
    applied = await get_applied_migrations(db)
    assert "test_0002_sql" in applied
    
    # Cleanup
    await db.execute("DROP TABLE test_sql_mig")


@pytest.mark.asyncio
async def test_apply_migrations_in_order(db, tmp_path):
    """Test that migrations are applied in correct order."""
    # Cleanup from any previous failed run
    await db.execute("DROP TABLE IF EXISTS test_ordered")
    await db.execute("DELETE FROM aksara_migrations WHERE name LIKE 'test_%'")
    
    # Create first migration (create table)
    mig1 = '''
from aksara.migrations import Migration
from aksara.migrations import operations as op

class Migration(Migration):
    operations = [
        op.CreateTable(
            name="test_ordered",
            fields=[("id", op.UUIDField(primary_key=True))],
        ),
    ]
'''
    (tmp_path / "test_0001_first.py").write_text(mig1)
    
    # Create second migration (add column)
    mig2 = '''
from aksara.migrations import Migration
from aksara.migrations import operations as op

class Migration(Migration):
    operations = [
        op.AddField(
            table="test_ordered",
            name="added_column",
            field=op.StringField(nullable=True),
        ),
    ]
'''
    (tmp_path / "test_0002_second.py").write_text(mig2)
    
    # Apply all migrations
    result = await apply_migrations(db, tmp_path)
    
    # Filter out internal migrations (auth, etc)
    test_migrations = [m for m in result["applied"] if m.startswith("test_")]
    assert len(test_migrations) == 2
    assert "test_0001_first" in test_migrations
    assert "test_0002_second" in test_migrations
    
    # Verify column exists (requires both migrations)
    exists = await db.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_name = 'test_ordered' AND column_name = 'added_column'
        )
    """)
    assert exists is True
    
    # Cleanup
    await db.execute("DROP TABLE test_ordered")


@pytest.mark.asyncio
async def test_apply_migrations_honors_dependency_order(tmp_path, monkeypatch):
    """Pending migrations should be applied by graph dependencies, not filename order."""
    dependent_name = "0002_add_column"
    dependency_name = "0003_create_table"
    app_label = tmp_path.name

    (tmp_path / f"{dependent_name}.py").write_text(
        f'''
from aksara.migrations import Migration
from aksara.migrations import operations as op

class Migration(Migration):
    dependencies = [("{app_label}", "{dependency_name}")]
    operations = [
        op.AddField(
            table="dependency_order",
            name="name",
            field=op.StringField(50, nullable=True),
        ),
    ]
'''
    )
    (tmp_path / f"{dependency_name}.py").write_text(
        '''
from aksara.migrations import Migration
from aksara.migrations import operations as op

class Migration(Migration):
    operations = [
        op.CreateTable(
            name="dependency_order",
            fields=[("id", op.UUIDField(primary_key=True))],
        ),
    ]
'''
    )

    applied_order = []

    async def _record_apply(_connection, name, path, *, fake=False, verbose=True):
        applied_order.append(name)

    monkeypatch.setattr(migration_executor, "ensure_migrations_table", AsyncMock())
    monkeypatch.setattr(migration_executor, "get_applied_migrations", AsyncMock(return_value=[]))
    monkeypatch.setattr(migration_executor, "apply_migration", _record_apply)

    result = await apply_migrations(object(), tmp_path, verbose=False, include_internal=False)

    assert result["errors"] == []
    assert applied_order == [dependency_name, dependent_name]


@pytest.mark.asyncio
async def test_migrations_idempotent(db, tmp_path):
    """Test that running migrate twice doesn't reapply."""
    mig = '''
from aksara.migrations import Migration
from aksara.migrations import operations as op

class Migration(Migration):
    operations = [
        op.CreateTable(
            name="test_idempotent",
            fields=[("id", op.UUIDField(primary_key=True))],
        ),
    ]
'''
    (tmp_path / "test_0001_idem.py").write_text(mig)
    
    # Apply first time
    result1 = await apply_migrations(db, tmp_path)
    assert len(result1["applied"]) == 1
    
    # Apply second time
    result2 = await apply_migrations(db, tmp_path)
    assert len(result2["applied"]) == 0
    assert "test_0001_idem" in result2["skipped"]
    
    # Cleanup
    await db.execute("DROP TABLE test_idempotent")


@pytest.mark.asyncio
async def test_fake_migration(db, tmp_path):
    """Test fake migration mode."""
    mig = '''
from aksara.migrations import Migration
from aksara.migrations import operations as op

class Migration(Migration):
    operations = [
        op.CreateTable(
            name="test_fake_table",
            fields=[("id", op.UUIDField(primary_key=True))],
        ),
    ]
'''
    (tmp_path / "test_0001_fake.py").write_text(mig)
    
    # Apply with fake=True
    await apply_migration(db, "test_0001_fake", tmp_path / "test_0001_fake.py", fake=True)
    
    # Table should NOT exist
    result = await db.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'test_fake_table'
        )
    """)
    assert result is False
    
    # But migration should be recorded
    applied = await get_applied_migrations(db)
    assert "test_0001_fake" in applied
