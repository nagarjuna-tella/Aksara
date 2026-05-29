"""Tests for the migration autodetector.

Verifies that the autodetector correctly:
- Detects new tables from fresh models
- Detects no changes when models match existing migrations
- Detects new models added alongside existing ones
- Detects added fields on existing tables
- Detects removed fields
- Detects removed models/tables
- Replays stacked migrations correctly
- Generates valid Python code via operations_to_code
- Handles idempotent double-runs (no false positives)
"""
import tempfile
from pathlib import Path

import pytest

from aksara import Model, fields
from aksara.migrations.autodetector import (
    detect_changes,
    operations_to_code,
    build_state_from_migrations,
    build_state_from_models,
    diff_states,
    FieldState,
    TableState,
    ProjectState,
)
from aksara.migrations import operations as op


# ---------------------------------------------------------------------------
# Migration file content used across tests
# ---------------------------------------------------------------------------

MIG_CREATE_POSTS = (
    'from aksara.migrations import Migration\n'
    'from aksara.migrations import operations as op\n'
    '\n'
    'class Migration(Migration):\n'
    '    dependencies = []\n'
    '    operations = [\n'
    '        op.CreateTable(\n'
    '            name="posts",\n'
    '            fields=[\n'
    '                ("id", op.UUIDField(primary_key=True)),\n'
    '                ("title", op.StringField(100)),\n'
    '                ("created_at", op.DateTimeField(auto_now_add=True)),\n'
    '                ("updated_at", op.DateTimeField(auto_now=True)),\n'
    '            ],\n'
    '        ),\n'
    '    ]\n'
)


# ---------------------------------------------------------------------------
# Model factories (fresh classes each call to avoid metaclass collisions)
# ---------------------------------------------------------------------------

def _make_post():
    """Post model matching MIG_CREATE_POSTS exactly."""
    class Post(Model):
        title = fields.String(max_length=100)
        class Meta:
            table_name = "posts"
    return Post


def _make_post_with_body():
    """Post model with an extra nullable 'body' field."""
    class PostBody(Model):
        title = fields.String(max_length=100)
        body = fields.Text(nullable=True)
        class Meta:
            table_name = "posts"
    return PostBody


def _make_post_with_array_field():
    """Post model with a PostgreSQL array field."""
    class PostArray(Model):
        title = fields.String(max_length=100)
        tags = fields.Array(item_type=str)

        class Meta:
            table_name = "posts"

    return PostArray


def _make_invoice_with_decimal_default():
    """Model with a decimal field default that must survive migrations."""
    class Invoice(Model):
        amount = fields.Decimal(max_digits=6, decimal_places=2, default=12.34)

        class Meta:
            table_name = "invoices"

    return Invoice


def _make_comment():
    """Separate Comment model."""
    class Comment(Model):
        text = fields.String(max_length=500)
        class Meta:
            table_name = "comments"
    return Comment


def _make_post_no_title():
    """Post without title (simulates field removal)."""
    class PostNoTitle(Model):
        class Meta:
            table_name = "posts"
    return PostNoTitle


def _models(*classes):
    return {c.__name__: c for c in classes}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAutodetector:
    """Core autodetector behaviour."""

    def test_fresh_project_detects_new_tables(self):
        """No migrations exist -> all models are new tables."""
        Post = _make_post()
        diff, ops = detect_changes([], _models(Post))
        assert diff.has_changes
        assert "posts" in diff.new_tables
        assert any(isinstance(o, op.CreateTable) for o in ops)

    def test_new_tables_are_ordered_by_foreign_key_dependencies(self):
        """Referenced new tables are created before tables with FK constraints."""
        class FKOrderRoom(Model):
            number = fields.String(max_length=20)

            class Meta:
                table_name = "rooms"

        class FKOrderGuest(Model):
            name = fields.String(max_length=100)
            room = fields.ForeignKey(FKOrderRoom)

            class Meta:
                table_name = "guests"

        class FKOrderStaffMember(Model):
            name = fields.String(max_length=100)

            class Meta:
                table_name = "staff_members"

        class FKOrderServiceRequest(Model):
            guest = fields.ForeignKey(FKOrderGuest)
            staff_member = fields.ForeignKey(FKOrderStaffMember, nullable=True)
            summary = fields.String(max_length=200)

            class Meta:
                table_name = "service_requests"

        diff, ops = detect_changes(
            [],
            _models(
                FKOrderGuest,
                FKOrderServiceRequest,
                FKOrderStaffMember,
                FKOrderRoom,
            ),
        )

        assert diff.has_changes
        create_order = [
            operation.name
            for operation in ops
            if isinstance(operation, op.CreateTable)
        ]

        assert create_order.index("rooms") < create_order.index("guests")
        assert create_order.index("guests") < create_order.index(
            "service_requests"
        )
        assert create_order.index("staff_members") < create_order.index(
            "service_requests"
        )

    def test_removed_tables_are_ordered_by_foreign_key_dependencies(self):
        """Dependent tables are dropped before referenced tables."""
        migration = (
            'from aksara.migrations import Migration\n'
            'from aksara.migrations import operations as op\n\n'
            'class Migration(Migration):\n'
            '    dependencies = []\n'
            '    operations = [\n'
            '        op.CreateTable(\n'
            '            name="rooms",\n'
            '            fields=[("id", op.UUIDField(primary_key=True))],\n'
            '        ),\n'
            '        op.CreateTable(\n'
            '            name="guests",\n'
            '            fields=[\n'
            '                ("id", op.UUIDField(primary_key=True)),\n'
            '                ("room_id", op.ForeignKeyField("rooms")),\n'
            '            ],\n'
            '        ),\n'
            '        op.CreateTable(\n'
            '            name="staff_members",\n'
            '            fields=[("id", op.UUIDField(primary_key=True))],\n'
            '        ),\n'
            '        op.CreateTable(\n'
            '            name="service_requests",\n'
            '            fields=[\n'
            '                ("id", op.UUIDField(primary_key=True)),\n'
            '                ("guest_id", op.ForeignKeyField("guests")),\n'
            '                ("staff_member_id", '
            'op.ForeignKeyField("staff_members")),\n'
            '            ],\n'
            '        ),\n'
            '    ]\n'
        )

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "0001_initial.py"
            p.write_text(migration)

            diff, ops = detect_changes([("0001_initial", p)], {})

        assert diff.has_changes
        drop_order = [
            operation.name
            for operation in ops
            if isinstance(operation, op.DropTable)
        ]

        assert drop_order.index("service_requests") < drop_order.index("guests")
        assert drop_order.index("service_requests") < drop_order.index(
            "staff_members"
        )
        assert drop_order.index("guests") < drop_order.index("rooms")

    def test_no_changes_when_models_match_migrations(self):
        """Models identical to existing migration -> no changes."""
        Post = _make_post()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "0001_initial.py"
            p.write_text(MIG_CREATE_POSTS)
            diff, ops = detect_changes([("0001_initial", p)], _models(Post))
            assert not diff.has_changes, (
                f"False positive! new={diff.new_tables} added={diff.added_fields} "
                f"removed={diff.removed_fields} altered={diff.altered_fields}"
            )
            assert ops == []

    def test_new_model_detected(self):
        """Adding a second model -> only the new table detected."""
        Post = _make_post()
        Comment = _make_comment()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "0001_initial.py"
            p.write_text(MIG_CREATE_POSTS)
            diff, _ = detect_changes([("0001_initial", p)], _models(Post, Comment))
            assert diff.has_changes
            assert "comments" in diff.new_tables
            assert "posts" not in diff.new_tables

    def test_added_field_detected(self):
        """Adding a field -> detected as added_fields."""
        PostBody = _make_post_with_body()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "0001_initial.py"
            p.write_text(MIG_CREATE_POSTS)
            diff, ops = detect_changes([("0001_initial", p)], _models(PostBody))
            assert diff.has_changes
            assert "posts" in diff.added_fields
            assert "body" in diff.added_fields["posts"]
            assert sum(1 for o in ops if isinstance(o, op.AddField)) == 1

    def test_removed_field_detected(self):
        """Removing a field -> detected as removed_fields."""
        PostNoTitle = _make_post_no_title()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "0001_initial.py"
            p.write_text(MIG_CREATE_POSTS)
            diff, ops = detect_changes([("0001_initial", p)], _models(PostNoTitle))
            assert diff.has_changes
            assert "posts" in diff.removed_fields
            assert "title" in diff.removed_fields["posts"]

    def test_removed_model_detected(self):
        """Removing all models -> table removal detected."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "0001_initial.py"
            p.write_text(MIG_CREATE_POSTS)
            diff, _ = detect_changes([("0001_initial", p)], {})
            assert diff.has_changes
            assert "posts" in diff.removed_tables

    def test_double_run_no_false_positive(self):
        """First run generates ops; second run with that migration -> no changes."""
        Post = _make_post()
        models = _models(Post)
        with tempfile.TemporaryDirectory() as d:
            # First run
            diff1, ops1 = detect_changes([], models)
            assert diff1.has_changes

            # Write generated migration
            code = operations_to_code(ops1)
            mig = Path(d) / "0001_auto.py"
            mig.write_text(
                'from aksara.migrations import Migration\n'
                'from aksara.migrations import operations as op\n\n'
                'class Migration(Migration):\n'
                '    dependencies = []\n'
                '    operations = [\n'
                f'{code},\n'
                '    ]\n'
            )

            # Second run
            diff2, ops2 = detect_changes([("0001_auto", mig)], models)
            assert not diff2.has_changes, (
                f"False positive on second run! new={diff2.new_tables} "
                f"added={diff2.added_fields} removed={diff2.removed_fields} "
                f"altered={diff2.altered_fields}"
            )
            assert ops2 == []

    def test_array_fields_preserve_postgresql_array_type(self):
        """Array runtime fields should stay ARRAY columns in generated migrations."""
        PostArray = _make_post_with_array_field()

        diff, ops = detect_changes([], _models(PostArray))

        assert diff.has_changes
        create_table = next(operation for operation in ops if isinstance(operation, op.CreateTable))
        generated_fields = dict(create_table.fields)
        tags_field = generated_fields["tags"]

        assert isinstance(tags_field, op.ArrayField)
        assert tags_field.to_sql() == "TEXT[]"

        code = operations_to_code(ops)
        assert "op.ArrayField(sql_type='TEXT[]')" in code
        assert "TextField" not in code.split('("tags",', 1)[1].split(")", 1)[0]

    def test_required_array_fields_preserve_nullability(self):
        """Array(nullable=False) should generate a NOT NULL array column."""
        class PostRequiredArray(Model):
            tags = fields.Array(item_type=str, nullable=False)

            class Meta:
                table_name = "posts"

        diff, ops = detect_changes([], _models(PostRequiredArray))

        assert diff.has_changes
        create_table = next(
            operation for operation in ops if isinstance(operation, op.CreateTable)
        )
        generated_fields = dict(create_table.fields)

        assert generated_fields["tags"].nullable is False
        assert "NOT NULL" in generated_fields["tags"].to_sql()

        code = operations_to_code(ops)
        assert "op.ArrayField(sql_type='TEXT[]', nullable=False)" in code

    def test_decimal_defaults_are_preserved_in_generated_migrations(self):
        """Decimal runtime defaults should survive CreateTable generation."""
        Invoice = _make_invoice_with_decimal_default()

        diff, ops = detect_changes([], _models(Invoice))

        assert diff.has_changes
        create_table = next(operation for operation in ops if isinstance(operation, op.CreateTable))
        generated_fields = dict(create_table.fields)
        amount_field = generated_fields["amount"]

        assert isinstance(amount_field, op.DecimalField)
        assert amount_field.default == 12.34
        assert "DEFAULT 12.34" in amount_field.to_sql()

        code = operations_to_code(ops)
        assert "op.DecimalField(6, 2, default=12.34)" in code

    def test_stacked_migrations_replay(self):
        """Two sequential migrations replay correctly."""
        PostBody = _make_post_with_body()
        models = _models(PostBody)

        mig2 = (
            'from aksara.migrations import Migration\n'
            'from aksara.migrations import operations as op\n\n'
            'class Migration(Migration):\n'
            '    dependencies = []\n'
            '    operations = [\n'
            '        op.AddField(\n'
            '            table="posts",\n'
            '            name="body",\n'
            '            field=op.TextField(nullable=True),\n'
            '        ),\n'
            '    ]\n'
        )

        with tempfile.TemporaryDirectory() as d:
            m1 = Path(d) / "0001_initial.py"
            m1.write_text(MIG_CREATE_POSTS)
            m2 = Path(d) / "0002_add_body.py"
            m2.write_text(mig2)

            existing = [("0001_initial", m1), ("0002_add_body", m2)]
            diff, ops = detect_changes(existing, models)
            assert not diff.has_changes, (
                f"Stacked replayed state should match! "
                f"altered={diff.altered_fields}"
            )


class TestCodeGeneration:
    """operations_to_code produces valid Python."""

    def test_create_table_code(self):
        ops = [
            op.CreateTable(
                name="users",
                fields=[
                    ("id", op.UUIDField(primary_key=True)),
                    ("email", op.StringField(255, unique=True)),
                ],
            ),
        ]
        code = operations_to_code(ops)
        assert "CreateTable" in code
        assert '"users"' in code
        assert "UUIDField" in code
        assert "StringField" in code

    def test_add_field_code(self):
        ops = [
            op.AddField(table="posts", name="bio", field=op.TextField(nullable=True)),
        ]
        code = operations_to_code(ops)
        assert "AddField" in code
        assert 'table="posts"' in code
        assert 'name="bio"' in code

    def test_remove_field_code(self):
        ops = [
            op.RemoveField(table="posts", name="bio"),
        ]
        code = operations_to_code(ops)
        assert "RemoveField" in code

    def test_drop_table_code(self):
        ops = [
            op.DropTable(name="old_table"),
        ]
        code = operations_to_code(ops)
        assert "DropTable" in code
        assert '"old_table"' in code


class TestStatePrimitives:
    """Low-level state / diff primitives."""

    def test_field_state_to_key_equality(self):
        a = FieldState(name="x", field_type="StringField")
        b = FieldState(name="x", field_type="StringField")
        assert a.to_key() == b.to_key()

    def test_field_state_to_key_type_diff(self):
        a = FieldState(name="x", field_type="StringField")
        b = FieldState(name="x", field_type="IntegerField")
        assert a.to_key() != b.to_key()

    def test_empty_diff_has_no_changes(self):
        from aksara.migrations.autodetector import MigrationDiff
        diff = MigrationDiff()
        assert not diff.has_changes

    def test_diff_with_new_table_has_changes(self):
        from aksara.migrations.autodetector import MigrationDiff
        diff = MigrationDiff(new_tables=["foo"])
        assert diff.has_changes

    def test_build_state_from_models_includes_auto_fields(self):
        """Models auto-generate id, created_at, updated_at."""
        Post = _make_post()
        state = build_state_from_models(_models(Post))
        table = state.tables.get("posts")
        assert table is not None
        assert "id" in table.fields
        assert "created_at" in table.fields
        assert "updated_at" in table.fields
        assert "title" in table.fields
        # id should be UUIDField
        assert table.fields["id"].field_type == "UUIDField"
        assert table.fields["id"].primary_key is True


class TestAlterFieldDetection:
    """Tests for field alteration detection and code generation."""

    def test_nullability_change_detected(self):
        """Changing a field's nullable -> detected as altered."""
        # Migration has title as NOT NULL (default)
        # Model has title as nullable=True
        class PostNullable(Model):
            title = fields.String(max_length=100, nullable=True)
            class Meta:
                table_name = "posts"

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "0001_initial.py"
            p.write_text(MIG_CREATE_POSTS)
            diff, ops = detect_changes([("0001_initial", p)], _models(PostNullable))
            assert diff.has_changes
            assert "posts" in diff.altered_fields
            assert "title" in diff.altered_fields["posts"]
            # Should generate AlterFieldNull
            alter_null_ops = [o for o in ops if isinstance(o, op.AlterFieldNull)]
            assert len(alter_null_ops) >= 1

    def test_alter_field_code_generation(self):
        """AlterFieldNull and AlterFieldDefault generate valid code."""
        test_ops = [
            op.AlterFieldNull(table="posts", name="title", nullable=True),
            op.AlterFieldDefault(table="posts", name="title", new_default="untitled"),
        ]
        code = operations_to_code(test_ops)
        assert "AlterFieldNull" in code
        assert "AlterFieldDefault" in code
        assert 'nullable=True' in code

    def test_alter_field_type_code_generation(self):
        """AlterFieldType generates valid code."""
        test_ops = [
            op.AlterFieldType(
                table="posts",
                name="title",
                new_field=op.TextField(),
            ),
        ]
        code = operations_to_code(test_ops)
        assert "AlterFieldType" in code
        assert "TextField" in code


class TestFieldOpCodeGenEdgeCases:
    """Edge cases for _field_op_to_code."""

    def test_text_field_with_default(self):
        """TextField with default should preserve it in code."""
        ops = [op.AddField(
            table="posts",
            name="bio",
            field=op.TextField(default="hello"),
        )]
        code = operations_to_code(ops)
        assert "default=" in code
        assert "'hello'" in code

    def test_date_field_with_default(self):
        """DateField with default should preserve it in code."""
        ops = [op.AddField(
            table="posts",
            name="birthday",
            field=op.DateField(default="2000-01-01"),
        )]
        code = operations_to_code(ops)
        assert "default=" in code
        assert "'2000-01-01'" in code

    def test_big_integer_field_code(self):
        """BigIntegerField should have proper code gen (not fallback)."""
        ops = [op.AddField(
            table="users",
            name="counter",
            field=op.BigIntegerField(nullable=True, unique=True),
        )]
        code = operations_to_code(ops)
        assert "BigIntegerField" in code
        assert "nullable=True" in code
        assert "unique=True" in code

    def test_extended_field_code_generation_preserves_options(self):
        """Extended FieldOps should not fall back to empty constructor code."""
        test_ops = [
            op.AddField(
                table="posts",
                name="slug",
                field=op.SlugField(max_length=80, unique=True, default="hello"),
            ),
            op.AddField(
                table="posts",
                name="rank",
                field=op.SmallIntegerField(nullable=True, unique=True, default=1),
            ),
            op.AddField(
                table="posts",
                name="publish_time",
                field=op.TimeField(nullable=True, default="09:30:00"),
            ),
            op.AddField(
                table="posts",
                name="window",
                field=op.DurationField(default="1 hour"),
            ),
            op.AddField(
                table="posts",
                name="ip",
                field=op.IPAddressField(unique=True, default="127.0.0.1"),
            ),
            op.AddField(
                table="posts",
                name="payload",
                field=op.BinaryField(nullable=True),
            ),
            op.AddField(
                table="posts",
                name="path",
                field=op.FilePathField(
                    max_length=255,
                    nullable=True,
                    unique=True,
                    default="/tmp/a.txt",
                ),
            ),
        ]

        code = operations_to_code(test_ops)

        assert "op.SlugField(80, unique=True, default='hello')" in code
        assert (
            "op.SmallIntegerField(nullable=True, unique=True, default=1)"
            in code
        )
        assert "op.TimeField(nullable=True, default='09:30:00')" in code
        assert "op.DurationField(default='1 hour')" in code
        assert "op.IPAddressField(unique=True, default='127.0.0.1')" in code
        assert "op.BinaryField(nullable=True)" in code
        assert (
            "op.FilePathField(255, nullable=True, unique=True, "
            "default='/tmp/a.txt')"
        ) in code

    def test_enum_field_code_with_name(self):
        """EnumField preserves enum_name in code gen."""
        ops = [op.AddField(
            table="posts",
            name="status",
            field=op.EnumField(['draft', 'published'], enum_name='Status'),
        )]
        code = operations_to_code(ops)
        assert "EnumField" in code
        assert "Status" in code


class TestForeignKeyConstraintNaming:
    """Tests for FK constraint naming to avoid collisions."""

    def test_fk_constraint_includes_table_name(self):
        """ForeignKeyField constraint should include table name."""
        fk = op.ForeignKeyField("users")
        sql = fk.get_constraint_sql("author_id", "posts")
        assert "fk_posts_author_id" in sql

    def test_fk_constraint_without_table_name(self):
        """ForeignKeyField constraint without table name still works."""
        fk = op.ForeignKeyField("users")
        sql = fk.get_constraint_sql("author_id")
        assert "fk_author_id" in sql

    def test_o2o_constraint_includes_table_name(self):
        """OneToOneField constraint should include table name."""
        o2o = op.OneToOneField("users")
        sql = o2o.get_constraint_sql("user_id", "profiles")
        assert "fk_profiles_user_id" in sql
