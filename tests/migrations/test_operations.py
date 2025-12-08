"""
Tests for Migration Operations

Tests all Operation classes in vidyut.migrations.operations.
"""

import pytest
from vidyut.migrations import operations as op


# =============================================================================
# Field Operation Tests
# =============================================================================

class TestUUIDField:
    """Tests for UUIDField operation."""
    
    def test_primary_key(self):
        field = op.UUIDField(primary_key=True)
        sql = field.to_sql()
        assert "UUID" in sql
        assert "PRIMARY KEY" in sql
        assert "gen_random_uuid()" in sql
    
    def test_nullable(self):
        field = op.UUIDField(nullable=True)
        sql = field.to_sql()
        assert "NOT NULL" not in sql
    
    def test_not_nullable(self):
        field = op.UUIDField(nullable=False)
        sql = field.to_sql()
        assert "NOT NULL" in sql
    
    def test_unique(self):
        field = op.UUIDField(unique=True)
        sql = field.to_sql()
        assert "UNIQUE" in sql


class TestStringField:
    """Tests for StringField operation."""
    
    def test_default_max_length(self):
        field = op.StringField()
        sql = field.to_sql()
        assert "VARCHAR(255)" in sql
    
    def test_custom_max_length(self):
        field = op.StringField(max_length=100)
        sql = field.to_sql()
        assert "VARCHAR(100)" in sql
    
    def test_unique(self):
        field = op.StringField(unique=True)
        sql = field.to_sql()
        assert "UNIQUE" in sql
    
    def test_nullable(self):
        field = op.StringField(nullable=True)
        sql = field.to_sql()
        assert "NOT NULL" not in sql
    
    def test_default_value(self):
        field = op.StringField(default="hello")
        sql = field.to_sql()
        assert "DEFAULT 'hello'" in sql
    
    def test_default_value_with_quotes(self):
        field = op.StringField(default="it's")
        sql = field.to_sql()
        assert "DEFAULT 'it''s'" in sql


class TestIntegerField:
    """Tests for IntegerField operation."""
    
    def test_basic(self):
        field = op.IntegerField()
        sql = field.to_sql()
        assert "INTEGER" in sql
        assert "NOT NULL" in sql
    
    def test_nullable(self):
        field = op.IntegerField(nullable=True)
        sql = field.to_sql()
        assert "NOT NULL" not in sql
    
    def test_default(self):
        field = op.IntegerField(default=0)
        sql = field.to_sql()
        assert "DEFAULT 0" in sql


class TestBooleanField:
    """Tests for BooleanField operation."""
    
    def test_basic(self):
        field = op.BooleanField()
        sql = field.to_sql()
        assert "BOOLEAN" in sql
    
    def test_default_true(self):
        field = op.BooleanField(default=True)
        sql = field.to_sql()
        assert "DEFAULT TRUE" in sql
    
    def test_default_false(self):
        field = op.BooleanField(default=False)
        sql = field.to_sql()
        assert "DEFAULT FALSE" in sql


class TestDateTimeField:
    """Tests for DateTimeField operation."""
    
    def test_basic(self):
        field = op.DateTimeField()
        sql = field.to_sql()
        assert "TIMESTAMP WITH TIME ZONE" in sql
    
    def test_auto_now_add(self):
        field = op.DateTimeField(auto_now_add=True)
        sql = field.to_sql()
        assert "DEFAULT CURRENT_TIMESTAMP" in sql
    
    def test_nullable(self):
        field = op.DateTimeField(nullable=True)
        sql = field.to_sql()
        assert "NOT NULL" not in sql


class TestJSONField:
    """Tests for JSONField operation."""
    
    def test_basic(self):
        field = op.JSONField()
        sql = field.to_sql()
        assert "JSONB" in sql
    
    def test_default_dict(self):
        field = op.JSONField(default={"key": "value"})
        sql = field.to_sql()
        assert "::jsonb" in sql
    
    def test_nullable_default(self):
        # JSONField is nullable by default
        field = op.JSONField()
        sql = field.to_sql()
        assert "NOT NULL" not in sql


class TestForeignKeyField:
    """Tests for ForeignKeyField operation."""
    
    def test_basic(self):
        field = op.ForeignKeyField("users")
        sql = field.to_sql()
        assert "UUID" in sql
    
    def test_nullable(self):
        field = op.ForeignKeyField("users", nullable=True)
        sql = field.to_sql()
        assert "NOT NULL" not in sql
    
    def test_constraint_sql(self):
        field = op.ForeignKeyField("users", on_delete="CASCADE")
        constraint = field.get_constraint_sql("author_id")
        assert "FOREIGN KEY (author_id)" in constraint
        assert 'REFERENCES "users"(id)' in constraint
        assert "ON DELETE CASCADE" in constraint


# =============================================================================
# Index Operation Tests
# =============================================================================

class TestIndexOp:
    """Tests for IndexOp."""
    
    def test_basic_index(self):
        index = op.IndexOp(
            name="idx_users_email",
            table="users",
            columns=["email"],
        )
        sql = index.to_sql()
        assert 'CREATE INDEX "idx_users_email"' in sql
        assert 'ON "users"' in sql
        assert '"email"' in sql
    
    def test_unique_index(self):
        index = op.IndexOp(
            name="idx_unique_email",
            table="users",
            columns=["email"],
            unique=True,
        )
        sql = index.to_sql()
        assert "UNIQUE INDEX" in sql
    
    def test_multi_column_index(self):
        index = op.IndexOp(
            name="idx_compound",
            table="users",
            columns=["first_name", "last_name"],
        )
        sql = index.to_sql()
        assert '"first_name", "last_name"' in sql
    
    def test_partial_index(self):
        index = op.IndexOp(
            name="idx_active_users",
            table="users",
            columns=["email"],
            where="is_active = TRUE",
        )
        sql = index.to_sql()
        assert "WHERE is_active = TRUE" in sql


# =============================================================================
# Table Operation Tests
# =============================================================================

class TestCreateTable:
    """Tests for CreateTable operation."""
    
    def test_describe(self):
        create = op.CreateTable(
            name="users",
            fields=[
                ("id", op.UUIDField(primary_key=True)),
                ("email", op.StringField(unique=True)),
            ],
        )
        desc = create.describe()
        assert "users" in desc
        # Only counts user-defined fields (excludes auto fields like id, created_at, updated_at)
        assert "1" in desc  # email is the only user-defined field
    
    def test_reverse(self):
        create = op.CreateTable(
            name="users",
            fields=[("id", op.UUIDField(primary_key=True))],
        )
        reverse = create.reverse()
        assert isinstance(reverse, op.DropTable)
        assert reverse.name == "users"


class TestDropTable:
    """Tests for DropTable operation."""
    
    def test_describe(self):
        drop = op.DropTable(name="old_table")
        desc = drop.describe()
        assert "old_table" in desc


class TestRenameTable:
    """Tests for RenameTable operation."""
    
    def test_describe(self):
        rename = op.RenameTable(old_name="users", new_name="accounts")
        desc = rename.describe()
        assert "users" in desc
        assert "accounts" in desc
    
    def test_reverse(self):
        rename = op.RenameTable(old_name="users", new_name="accounts")
        reverse = rename.reverse()
        assert isinstance(reverse, op.RenameTable)
        assert reverse.old_name == "accounts"
        assert reverse.new_name == "users"


# =============================================================================
# Column Operation Tests
# =============================================================================

class TestAddField:
    """Tests for AddField operation."""
    
    def test_describe(self):
        add = op.AddField(
            table="users",
            name="phone",
            field=op.StringField(max_length=20, nullable=True),
        )
        desc = add.describe()
        assert "phone" in desc
        assert "users" in desc
    
    def test_reverse(self):
        add = op.AddField(
            table="users",
            name="phone",
            field=op.StringField(nullable=True),
        )
        reverse = add.reverse()
        assert isinstance(reverse, op.RemoveField)
        assert reverse.table == "users"
        assert reverse.name == "phone"


class TestRemoveField:
    """Tests for RemoveField operation."""
    
    def test_describe(self):
        remove = op.RemoveField(table="users", name="deprecated")
        desc = remove.describe()
        assert "deprecated" in desc
        assert "users" in desc


class TestRenameField:
    """Tests for RenameField operation."""
    
    def test_describe(self):
        rename = op.RenameField(
            table="users",
            old_name="username",
            new_name="user_name",
        )
        desc = rename.describe()
        assert "username" in desc
        assert "user_name" in desc
    
    def test_reverse(self):
        rename = op.RenameField(
            table="users",
            old_name="username",
            new_name="user_name",
        )
        reverse = rename.reverse()
        assert isinstance(reverse, op.RenameField)
        assert reverse.old_name == "user_name"
        assert reverse.new_name == "username"


class TestAlterFieldNull:
    """Tests for AlterFieldNull operation."""
    
    def test_describe_nullable(self):
        alter = op.AlterFieldNull(table="users", name="phone", nullable=True)
        desc = alter.describe()
        assert "nullable" in desc
    
    def test_describe_not_nullable(self):
        alter = op.AlterFieldNull(table="users", name="email", nullable=False)
        desc = alter.describe()
        assert "non-nullable" in desc
    
    def test_reverse(self):
        alter = op.AlterFieldNull(table="users", name="phone", nullable=True)
        reverse = alter.reverse()
        assert isinstance(reverse, op.AlterFieldNull)
        assert reverse.nullable is False


# =============================================================================
# Index Operation Tests
# =============================================================================

class TestAddIndex:
    """Tests for AddIndex operation."""
    
    def test_describe(self):
        add = op.AddIndex(
            index=op.IndexOp(
                name="idx_users_email",
                table="users",
                columns=["email"],
            )
        )
        desc = add.describe()
        assert "idx_users_email" in desc
    
    def test_reverse(self):
        add = op.AddIndex(
            index=op.IndexOp(
                name="idx_users_email",
                table="users",
                columns=["email"],
            )
        )
        reverse = add.reverse()
        assert isinstance(reverse, op.RemoveIndex)
        assert reverse.name == "idx_users_email"


class TestRemoveIndex:
    """Tests for RemoveIndex operation."""
    
    def test_describe(self):
        remove = op.RemoveIndex(name="idx_old", table="users")
        desc = remove.describe()
        assert "idx_old" in desc


# =============================================================================
# Constraint Operation Tests
# =============================================================================

class TestAddConstraint:
    """Tests for AddConstraint operation."""
    
    def test_describe(self):
        add = op.AddConstraint(
            table="users",
            name="check_age",
            constraint_sql="CHECK (age >= 0)",
        )
        desc = add.describe()
        assert "check_age" in desc
    
    def test_reverse(self):
        add = op.AddConstraint(
            table="users",
            name="check_age",
            constraint_sql="CHECK (age >= 0)",
        )
        reverse = add.reverse()
        assert isinstance(reverse, op.RemoveConstraint)
        assert reverse.name == "check_age"


class TestRemoveConstraint:
    """Tests for RemoveConstraint operation."""
    
    def test_describe(self):
        remove = op.RemoveConstraint(table="users", name="check_age")
        desc = remove.describe()
        assert "check_age" in desc


# =============================================================================
# RunSQL Operation Tests
# =============================================================================

class TestRunSQL:
    """Tests for RunSQL operation."""
    
    def test_describe(self):
        run = op.RunSQL(sql="SELECT 1")
        desc = run.describe()
        assert "SELECT 1" in desc
    
    def test_long_sql_truncated(self):
        run = op.RunSQL(sql="SELECT " + "x" * 100)
        desc = run.describe()
        assert "..." in desc
    
    def test_reverse_with_reverse_sql(self):
        run = op.RunSQL(
            sql="CREATE EXTENSION uuid",
            reverse_sql="DROP EXTENSION uuid",
        )
        reverse = run.reverse()
        assert reverse is not None
        assert "DROP EXTENSION" in reverse.sql
    
    def test_reverse_without_reverse_sql(self):
        run = op.RunSQL(sql="SELECT 1")
        reverse = run.reverse()
        assert reverse is None
    
    def test_auto_detect_dangerous_drop(self):
        run = op.RunSQL(sql="DROP TABLE users")
        assert run.dangerous is True
    
    def test_auto_detect_dangerous_truncate(self):
        run = op.RunSQL(sql="TRUNCATE users")
        assert run.dangerous is True
    
    def test_safe_sql_not_dangerous(self):
        run = op.RunSQL(sql="SELECT * FROM users")
        assert run.dangerous is False
    
    def test_explicit_dangerous(self):
        run = op.RunSQL(sql="UPDATE users SET foo=bar", dangerous=True)
        assert run.dangerous is True


# =============================================================================
# Migration Base Class Tests
# =============================================================================

class TestMigrationClass:
    """Tests for Migration base class."""
    
    def test_empty_migration(self):
        from vidyut.migrations.base import Migration
        
        class EmptyMigration(Migration):
            pass
        
        m = EmptyMigration()
        assert m.operations == []
        assert m.dependencies == []
    
    def test_migration_with_operations(self):
        from vidyut.migrations.base import Migration
        
        class TestMigration(Migration):
            operations = [
                op.CreateTable(
                    name="test",
                    fields=[("id", op.UUIDField(primary_key=True))],
                ),
            ]
        
        m = TestMigration()
        assert len(m.operations) == 1
        assert isinstance(m.operations[0], op.CreateTable)
    
    def test_migration_with_dependencies(self):
        from vidyut.migrations.base import Migration
        
        class TestMigration(Migration):
            dependencies = [("app", "0001_initial")]
            operations = []
        
        m = TestMigration()
        assert len(m.dependencies) == 1
        assert m.dependencies[0] == ("app", "0001_initial")
