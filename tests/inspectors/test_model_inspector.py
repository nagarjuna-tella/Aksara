"""
Tests for aksara.inspectors.models — Model Inspector.

v0.5.21: Model inspection, field/relationship/constraint analysis.
"""

import pytest
from unittest.mock import MagicMock, patch
from aksara.inspectors.models import (
    ModelInspectorField,
    ModelInspectorRelationship,
    ModelInspectorConstraint,
    ModelInspectorSummary,
    inspect_model,
    inspect_all_models,
)


# =============================================================================
# Pydantic model tests
# =============================================================================


class TestModelInspectorField:
    """Tests for ModelInspectorField model."""

    def test_create_minimal(self):
        f = ModelInspectorField(name="id", column_name="id", field_type="AutoField")
        assert f.name == "id"
        assert f.python_type == "Any"
        assert f.nullable is False
        assert f.primary_key is False

    def test_create_full(self):
        f = ModelInspectorField(
            name="email",
            column_name="email",
            field_type="CharField",
            python_type="str",
            nullable=False,
            unique=True,
            has_default=False,
            max_length=255,
            ai_description="User email address",
            ai_sensitive=True,
            auto_generated="Unique; ⚠️ Sensitive",
        )
        assert f.unique is True
        assert f.ai_sensitive is True
        assert f.max_length == 255

    def test_roundtrip(self):
        f = ModelInspectorField(name="x", column_name="x", field_type="IntegerField")
        data = f.model_dump()
        f2 = ModelInspectorField(**data)
        assert f2.name == "x"

    def test_choices(self):
        f = ModelInspectorField(
            name="status",
            column_name="status",
            field_type="CharField",
            choices=["active", "inactive"],
        )
        assert f.choices == ["active", "inactive"]


class TestModelInspectorRelationship:
    """Tests for ModelInspectorRelationship model."""

    def test_fk(self):
        r = ModelInspectorRelationship(
            field_name="author",
            kind="fk",
            target_model="User",
            on_delete="CASCADE",
        )
        assert r.kind == "fk"
        assert r.target_model == "User"

    def test_m2m(self):
        r = ModelInspectorRelationship(
            field_name="tags",
            kind="m2m",
            target_model="Tag",
            through_table="post_tags",
        )
        assert r.through_table == "post_tags"

    def test_roundtrip(self):
        r = ModelInspectorRelationship(field_name="x", kind="fk", target_model="Y")
        data = r.model_dump()
        r2 = ModelInspectorRelationship(**data)
        assert r2.field_name == "x"


class TestModelInspectorConstraint:
    """Tests for ModelInspectorConstraint model."""

    def test_pk_constraint(self):
        c = ModelInspectorConstraint(
            kind="primary_key",
            columns=["id"],
            name="pk_users_id",
            description="Primary key on id",
        )
        assert c.kind == "primary_key"
        assert c.columns == ["id"]

    def test_unique_constraint(self):
        c = ModelInspectorConstraint(
            kind="unique",
            columns=["email"],
        )
        assert c.kind == "unique"

    def test_roundtrip(self):
        c = ModelInspectorConstraint(kind="index", columns=["author_id"])
        data = c.model_dump()
        c2 = ModelInspectorConstraint(**data)
        assert c2.columns == ["author_id"]


class TestModelInspectorSummary:
    """Tests for ModelInspectorSummary model."""

    def test_create_minimal(self):
        s = ModelInspectorSummary(name="User", table_name="users")
        assert s.name == "User"
        assert s.num_fields == 0
        assert s.fields == []
        assert s.comments == []

    def test_create_full(self):
        s = ModelInspectorSummary(
            name="Post",
            table_name="posts",
            app_label="blog",
            num_fields=5,
            num_relationships=1,
            has_timestamps=True,
            pk_field="id",
            pk_type="AutoField",
            fields=[
                ModelInspectorField(name="id", column_name="id", field_type="AutoField", primary_key=True),
            ],
            relationships=[
                ModelInspectorRelationship(field_name="author", kind="fk", target_model="User"),
            ],
            constraints=[
                ModelInspectorConstraint(kind="primary_key", columns=["id"]),
            ],
            ai_description="Blog post model",
            create_table_sql="CREATE TABLE posts (...)",
            comments=["✓ Timestamps detected"],
        )
        assert s.num_relationships == 1
        assert len(s.fields) == 1
        assert len(s.relationships) == 1

    def test_roundtrip(self):
        s = ModelInspectorSummary(name="T", table_name="t")
        data = s.model_dump()
        s2 = ModelInspectorSummary(**data)
        assert s2.name == "T"


# =============================================================================
# inspect_model tests
# =============================================================================


def _make_mock_model():
    """Create a mock model class that mimics Aksara Model."""
    model = MagicMock()
    model.__name__ = "TestModel"
    model.__tablename__ = "test_models"
    model.get_create_table_sql = MagicMock(return_value="CREATE TABLE test_models (id SERIAL PRIMARY KEY)")

    id_field = MagicMock()
    id_field.__class__ = type("Integer", (), {})
    id_field.__class__.__name__ = "Integer"
    id_field.name = "id"
    id_field.primary_key = True
    id_field.nullable = False
    id_field.unique = False
    id_field.default = None
    id_field.max_length = None
    id_field.choices = None
    id_field.ai_description = ""
    id_field.ai_sensitive = False

    name_field = MagicMock()
    name_field.__class__ = type("String", (), {})
    name_field.__class__.__name__ = "String"
    name_field.name = "name"
    name_field.primary_key = False
    name_field.nullable = False
    name_field.unique = False
    name_field.default = None
    name_field.max_length = 100
    name_field.choices = None
    name_field.ai_description = ""
    name_field.ai_sensitive = False

    model._fields = {"id": id_field, "name": name_field}
    model._fk_fields = {}
    model._m2m_fields = {}
    model._ai_meta = None
    model.meta = MagicMock()
    model.meta.app_label = "test"

    return model


class TestInspectModel:
    """Tests for inspect_model function."""

    def test_basic_model(self):
        model = _make_mock_model()
        result = inspect_model(model)
        assert result.name == "TestModel"
        assert result.table_name == "test_models"
        assert result.num_fields == 2
        assert result.pk_field == "id"

    def test_field_types(self):
        model = _make_mock_model()
        result = inspect_model(model)
        field_names = {f.name for f in result.fields}
        assert "id" in field_names
        assert "name" in field_names

    def test_pk_constraint_generated(self):
        model = _make_mock_model()
        result = inspect_model(model)
        pk_constraints = [c for c in result.constraints if c.kind == "primary_key"]
        assert len(pk_constraints) == 1

    def test_create_table_sql(self):
        model = _make_mock_model()
        result = inspect_model(model)
        assert "CREATE TABLE" in result.create_table_sql

    def test_no_timestamps(self):
        model = _make_mock_model()
        result = inspect_model(model)
        assert result.has_timestamps is False

    def test_with_timestamps(self):
        model = _make_mock_model()
        created = MagicMock()
        created.__class__ = type("DateTime", (), {})
        created.__class__.__name__ = "DateTime"
        created.name = "created_at"
        created.primary_key = False
        created.nullable = False
        created.unique = False
        created.default = None
        created.max_length = None
        created.choices = None
        created.ai_description = ""
        created.ai_sensitive = False
        created.auto_now_add = True
        created.auto_now = False

        updated = MagicMock()
        updated.__class__ = type("DateTime", (), {})
        updated.__class__.__name__ = "DateTime"
        updated.name = "updated_at"
        updated.primary_key = False
        updated.nullable = False
        updated.unique = False
        updated.default = None
        updated.max_length = None
        updated.choices = None
        updated.ai_description = ""
        updated.ai_sensitive = False
        updated.auto_now_add = False
        updated.auto_now = True

        model._fields["created_at"] = created
        model._fields["updated_at"] = updated
        result = inspect_model(model)
        assert result.has_timestamps is True
        assert any("Timestamps" in c for c in result.comments)

    def test_with_fk(self):
        from aksara.fields import ForeignKey
        model = _make_mock_model()
        target = MagicMock()
        target.__name__ = "Author"
        target.__tablename__ = "authors"
        fk = MagicMock(spec=ForeignKey)
        fk.__class__ = ForeignKey
        fk.name = "author"
        fk._to = target
        fk.on_delete = "CASCADE"
        fk.related_name = None
        fk.nullable = False
        fk.primary_key = False
        fk.unique = False
        fk.default = None
        fk.max_length = None
        fk.choices = None
        fk.ai_description = ""
        fk.ai_sensitive = False
        fk.db_column_name = "author_id"
        model._fields["author"] = fk
        model._fk_fields = {"author": fk}
        result = inspect_model(model)
        assert result.num_relationships == 1
        assert result.relationships[0].kind == "fk"
        assert result.relationships[0].target_model == "Author"

    def test_with_m2m(self):
        from aksara.fields import ManyToMany
        model = _make_mock_model()
        target = MagicMock()
        target.__name__ = "Tag"
        target.__tablename__ = "tags"
        m2m = MagicMock(spec=ManyToMany)
        m2m.__class__ = ManyToMany
        m2m.name = "tags"
        m2m._to = target
        m2m.through_table = None
        m2m.related_name = None
        m2m.primary_key = False
        m2m.nullable = False
        m2m.unique = False
        m2m.default = None
        m2m.max_length = None
        m2m.choices = None
        m2m.ai_description = ""
        m2m.ai_sensitive = False
        model._fields["tags"] = m2m
        model._m2m_fields = {"tags": m2m}
        result = inspect_model(model)
        assert result.num_relationships == 1
        assert result.relationships[0].kind == "m2m"

    def test_ai_meta(self):
        model = _make_mock_model()
        ai_meta = MagicMock()
        ai_meta.ai_description = "Test model for AI"
        ai_meta.ai_agent_exposed = False
        model._ai_meta = ai_meta
        result = inspect_model(model)
        assert result.ai_description == "Test model for AI"
        assert result.ai_agent_exposed is False
        assert any("Not exposed" in c for c in result.comments)

    def test_sensitive_field_comment(self):
        model = _make_mock_model()
        sensitive = MagicMock()
        sensitive.__class__ = type("String", (), {})
        sensitive.__class__.__name__ = "String"
        sensitive.name = "password"
        sensitive.ai_sensitive = True
        sensitive.primary_key = False
        sensitive.nullable = False
        sensitive.unique = False
        sensitive.default = None
        sensitive.max_length = 100
        sensitive.choices = None
        sensitive.ai_description = ""
        model._fields["password"] = sensitive
        result = inspect_model(model)
        assert any("sensitive" in c.lower() for c in result.comments)

    def test_no_fields_warning(self):
        model = MagicMock()
        model.__name__ = "EmptyModel"
        model.__tablename__ = "empty_models"
        model._fields = {}
        model._fk_fields = {}
        model._m2m_fields = {}
        model._ai_meta = None
        model.meta = MagicMock()
        model.meta.app_label = None
        model.get_create_table_sql = MagicMock(side_effect=Exception("no sql"))
        result = inspect_model(model)
        assert any("no fields" in c.lower() for c in result.comments)

    def test_unique_field_constraint(self):
        model = _make_mock_model()
        email = MagicMock()
        email.__class__ = type("String", (), {})
        email.__class__.__name__ = "String"
        email.name = "email"
        email.primary_key = False
        email.nullable = False
        email.unique = True
        email.default = None
        email.max_length = 255
        email.choices = None
        email.ai_description = ""
        email.ai_sensitive = False
        model._fields["email"] = email
        result = inspect_model(model)
        uq = [c for c in result.constraints if c.kind == "unique"]
        assert len(uq) >= 1


# =============================================================================
# inspect_all_models tests
# =============================================================================


class TestInspectAllModels:
    """Tests for inspect_all_models function."""

    def test_returns_list(self):
        result = inspect_all_models()
        assert isinstance(result, list)

    def test_results_are_summaries(self):
        result = inspect_all_models()
        for r in result:
            assert isinstance(r, ModelInspectorSummary)

    @patch("aksara.registry.ModelRegistry")
    def test_with_registered_models(self, mock_registry):
        model = _make_mock_model()
        mock_registry.all.return_value = {"TestModel": model}
        result = inspect_all_models()
        assert len(result) == 1
        assert result[0].name == "TestModel"

    @patch("aksara.registry.ModelRegistry")
    def test_empty_registry(self, mock_registry):
        mock_registry.all.return_value = {}
        result = inspect_all_models()
        assert len(result) == 0

    @patch("aksara.registry.ModelRegistry")
    def test_handles_broken_model(self, mock_registry):
        """Should skip models that raise during inspection."""
        broken = MagicMock()
        broken.__name__ = "Broken"
        broken.__tablename__ = "broken"
        broken._fields = {}
        broken._fk_fields = {}
        broken._m2m_fields = {}
        broken._ai_meta = None
        broken.meta = MagicMock(side_effect=Exception("boom"))
        del broken.meta  # Force attribute error on getattr
        mock_registry.all.return_value = {"Broken": broken}
        # Should not raise
        result = inspect_all_models()
        # May include partially inspected model
        assert isinstance(result, list)
