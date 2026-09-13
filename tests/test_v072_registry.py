"""Regression tests for the v0.7.2 canonical model registry contract."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from aksara import Model, fields
from aksara.cli.main import cli
from aksara.contrib.admin import AdminSite
from aksara.migrations.autodetector import build_state_from_models
from aksara.model.base import finalize_relations
from aksara.registry import AmbiguousModelError, ModelRegistry
from aksara.relations import RelationRegistry


@pytest.fixture(autouse=True)
def isolated_registries():
    ModelRegistry.clear()
    RelationRegistry.clear()
    yield
    ModelRegistry.clear()
    RelationRegistry.clear()


def _model(module: str, name: str, table: str):
    return type(
        name,
        (Model,),
        {
            "__module__": module,
            "__tablename__": table,
            "label": fields.String(),
        },
    )


def test_unambiguous_models_keep_the_simple_name_contract():
    account = _model("shop.models", "Account", "shop_accounts")

    assert ModelRegistry.get("Account") is account
    assert ModelRegistry.get("shop.models.Account") is account
    assert ModelRegistry.reference(account) == "Account"
    assert ModelRegistry.all() == {"Account": account}


@pytest.mark.parametrize(
    "modules",
    [("aksara.auth.models", "tenant.models"), ("tenant.models", "aksara.auth.models")],
)
def test_same_named_models_use_qualified_identity_independent_of_import_order(modules):
    first = _model(modules[0], "User", f"{modules[0].split('.')[0]}_users")
    second = _model(modules[1], "User", f"{modules[1].split('.')[0]}_users")
    expected = {
        f"{modules[0]}.User": first,
        f"{modules[1]}.User": second,
    }

    assert dict(ModelRegistry.all()) == dict(sorted(expected.items()))
    assert ModelRegistry.get(f"{modules[0]}.User") is first
    assert ModelRegistry.get(f"{modules[1]}.User") is second
    assert ModelRegistry.reference(first) == f"{modules[0]}.User"
    assert ModelRegistry.reference(second) == f"{modules[1]}.User"
    with pytest.raises(AmbiguousModelError, match="aksara.auth.models.User.*tenant.models.User"):
        ModelRegistry.get("User")


def test_repeated_discovery_replaces_only_the_same_qualified_model():
    original = _model("billing.models", "Invoice", "billing_invoices")
    other = _model("archive.models", "Invoice", "archived_invoices")
    reloaded = _model("billing.models", "Invoice", "billing_invoices")

    assert original is not reloaded
    assert ModelRegistry.get("billing.models.Invoice") is reloaded
    assert ModelRegistry.get("archive.models.Invoice") is other
    assert len(ModelRegistry.all()) == 2


def test_registry_all_remains_a_live_read_only_view_across_collisions():
    view = ModelRegistry.all()
    first = _model("alpha.models", "User", "alpha_users")
    second = _model("beta.models", "User", "beta_users")

    assert set(view) == {"alpha.models.User", "beta.models.User"}
    assert set(view.values()) == {first, second}
    with pytest.raises(TypeError):
        view["User"] = first


def test_lazy_relations_accept_qualified_names_and_reject_ambiguous_simple_names():
    alpha_user = _model("alpha.models", "User", "alpha_users")
    _model("beta.models", "User", "beta_users")

    qualified_post = type(
        "QualifiedPost",
        (Model,),
        {
            "__module__": "blog.models",
            "__tablename__": "qualified_posts",
            "author": fields.ForeignKey("alpha.models.User"),
        },
    )
    ambiguous_post = type(
        "AmbiguousPost",
        (Model,),
        {
            "__module__": "blog.models",
            "__tablename__": "ambiguous_posts",
            "author": fields.ForeignKey("User"),
        },
    )

    assert qualified_post._fields["author"].to_model is alpha_user
    with pytest.raises(AmbiguousModelError):
        _ = ambiguous_post._fields["author"].to_model
    with pytest.raises(AmbiguousModelError):
        ambiguous_post.get_create_table_sql()

    ambiguous_group = type(
        "AmbiguousGroup",
        (Model,),
        {
            "__module__": "teams.models",
            "__tablename__": "ambiguous_groups",
            "members": fields.ManyToMany("User"),
        },
    )
    with pytest.raises(AmbiguousModelError):
        ambiguous_group._m2m_fields["members"].get_join_table_sql()

    with pytest.raises(AmbiguousModelError):
        finalize_relations()


def test_migration_state_keeps_both_same_named_models():
    auth_user = _model("aksara.auth.models", "User", "aksara_users")
    tenant_user = _model("tenant.models", "User", "tenant_users")

    state = build_state_from_models(dict(ModelRegistry.all()))

    assert state.table_names() == {"aksara_users", "tenant_users"}
    assert set(ModelRegistry.all().values()) == {auth_user, tenant_user}


def test_migration_state_rejects_duplicate_table_names():
    _model("alpha.models", "User", "users")
    _model("beta.models", "User", "users")

    with pytest.raises(ValueError, match="Duplicate model table 'users'"):
        build_state_from_models(dict(ModelRegistry.all()))


def test_admin_can_register_both_same_named_models():
    alpha_user = _model("alpha.models", "User", "alpha_users")
    beta_user = _model("beta.models", "User", "beta_users")
    site = AdminSite(name="collision-test")

    site.register(alpha_user, beta_user)

    assert set(site._registry) == {alpha_user, beta_user}


def test_inspection_cli_reports_ambiguous_name_and_qualified_choices():
    _model("alpha.models", "User", "alpha_users")
    _model("beta.models", "User", "beta_users")

    result = CliRunner().invoke(cli, ["inspect", "models", "--model", "User"])

    assert result.exit_code != 0
    assert "ambiguous" in result.output.lower()
    assert "alpha.models.User" in result.output
    assert "beta.models.User" in result.output
