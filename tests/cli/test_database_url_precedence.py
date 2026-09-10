"""CLI database discovery follows the same precedence as Settings."""

from __future__ import annotations

import click

from aksara.cli.main import _tasks_db, migrate


def test_migrate_prefers_namespaced_database_url() -> None:
    option = next(parameter for parameter in migrate.params if parameter.name == "database_url")
    assert option.envvar == ["AKSARA_DATABASE_URL", "DATABASE_URL"]


def test_click_resolves_first_configured_database_alias(monkeypatch) -> None:
    monkeypatch.setenv("AKSARA_DATABASE_URL", "postgresql://namespaced.example/db")
    monkeypatch.setenv("DATABASE_URL", "postgresql://compatible.example/db")
    option = next(parameter for parameter in migrate.params if parameter.name == "database_url")
    assert option.value_from_envvar(click.Context(migrate)) == "postgresql://namespaced.example/db"


def test_task_cli_database_uses_namespaced_value(monkeypatch) -> None:
    monkeypatch.setenv("AKSARA_DATABASE_URL", "postgresql://namespaced.example/db")
    monkeypatch.setenv("DATABASE_URL", "postgresql://compatible.example/db")
    database = _tasks_db()
    assert database.database_url == "postgresql://namespaced.example/db"
