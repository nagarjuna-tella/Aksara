"""
Regression tests for Phase 5 bug-hunt findings on the CLI surface.

Each test exercises one of the four confirmed bugs from
`bug-hunt/phase-5-findings.md`. The tests invoke `aksara` CLI commands
via Click's CliRunner and stub out anything that would otherwise reach
the real filesystem or database.
"""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from aksara.cli.main import cli, discover_models


# ─── Fix #1 — dbsetup accepts the documented 2-input flow ─────────────────


class TestDbsetupPromptOrder:
    @patch("aksara.cli.main._read_env_database_url")
    @patch("asyncio.run")
    def test_default_flow_does_not_route_inputs_into_port_prompt(
        self, mock_asyncio_run, mock_read_env
    ):
        """
        Before the fix, `aksara dbsetup` prompted for Host and Port
        before dbname/username, so feeding the documented `mydb\\npostgres\\n`
        sequence aborted with: `Error: 'postgres' is not a valid integer.`
        After the fix, those two inputs feed the dbname + username
        prompts, the integer-coercion error never appears, and the
        command flows past the prompts into the PG-check step.
        """
        mock_read_env.return_value = None
        mock_asyncio_run.return_value = False  # PG check returns False

        runner = CliRunner()
        result = runner.invoke(cli, ["dbsetup"], input="mydb\npostgres\n")

        # The hallmark of the bug was Click rejecting "postgres" as a
        # non-integer port. That message must not appear after the fix.
        assert "not a valid integer" not in result.output
        # We should reach at least the PG reachability step; the mocked
        # PG check returns False so the command exits with the
        # "not reachable" branch but never with a parsing error.
        assert "not running or not reachable" in result.output


# ─── Fix #2 — `aksara info` lists installed_apps including built-ins ──────


class TestAksaraInfoInstalledApps:
    def test_info_lists_installed_apps_with_builtins(self):
        from aksara.conf import settings

        original_apps = list(settings.apps)
        original_installed = list(settings.installed_apps)

        try:
            settings.apps = ["app"]
            settings.installed_apps = [
                "aksara.contrib.auth",
                "aksara.contrib.admin",
                "app",
            ]

            runner = CliRunner()
            result = runner.invoke(cli, ["info"])

            assert result.exit_code == 0
            # All three installed_apps must appear in the section
            # output; prior to the fix, only `settings.apps` (just
            # "app") was printed, hiding the contrib apps.
            assert "aksara.contrib.auth" in result.output
            assert "aksara.contrib.admin" in result.output
            assert "app" in result.output
        finally:
            settings.apps = original_apps
            settings.installed_apps = original_installed


# ─── Fix #3 — `aksara info` reflects production Studio gating ─────────────


class TestAksaraInfoStudioGating:
    def test_studio_marked_disabled_when_production_gating_blocks_it(self):
        from aksara.conf import settings

        original = {
            "debug": settings.debug,
            "enable_studio": getattr(settings, "enable_studio", True),
            "studio_expose_in_production": getattr(
                settings, "studio_expose_in_production", False
            ),
        }

        try:
            # Production-like configuration where Studio is "enabled"
            # in settings but the production gating must veto it.
            settings.debug = False
            settings.enable_studio = True
            settings.studio_expose_in_production = False

            runner = CliRunner()
            result = runner.invoke(cli, ["info"])

            assert result.exit_code == 0
            # Extract the Studio line and confirm it reports disabled.
            studio_lines = [
                line for line in result.output.splitlines()
                if "Studio:" in line
            ]
            assert studio_lines, "Studio line missing from `aksara info` output"
            assert "disabled" in studio_lines[0]
            assert "enabled" not in studio_lines[0]
        finally:
            settings.debug = original["debug"]
            settings.enable_studio = original["enable_studio"]
            settings.studio_expose_in_production = original["studio_expose_in_production"]

    def test_studio_marked_enabled_when_expose_in_production_is_true(self):
        from aksara.conf import settings

        original = {
            "debug": settings.debug,
            "enable_studio": getattr(settings, "enable_studio", True),
            "studio_expose_in_production": getattr(
                settings, "studio_expose_in_production", False
            ),
        }

        try:
            settings.debug = False
            settings.enable_studio = True
            settings.studio_expose_in_production = True

            runner = CliRunner()
            result = runner.invoke(cli, ["info"])

            assert result.exit_code == 0
            studio_lines = [
                line for line in result.output.splitlines()
                if "Studio:" in line
            ]
            assert studio_lines
            assert "enabled" in studio_lines[0]
        finally:
            settings.debug = original["debug"]
            settings.enable_studio = original["enable_studio"]
            settings.studio_expose_in_production = original[
                "studio_expose_in_production"
            ]


# ─── Fix #4 — discover_models walks settings.installed_apps ───────────────


class TestDiscoverModelsHonoursInstalledApps:
    def test_discover_models_attempts_to_import_installed_app_models(self):
        from aksara.conf import settings

        # Build a synthetic installed app with a `.models` submodule
        # and inject it into sys.modules so the import succeeds without
        # touching the filesystem.
        synthetic_root = ModuleType("synthetic_installed_app_fix4")
        synthetic_root.__path__ = []  # type: ignore[attr-defined]
        synthetic_models = ModuleType("synthetic_installed_app_fix4.models")
        synthetic_models.MARKER = "imported"  # type: ignore[attr-defined]
        synthetic_root.models = synthetic_models  # type: ignore[attr-defined]

        sys.modules["synthetic_installed_app_fix4"] = synthetic_root
        sys.modules["synthetic_installed_app_fix4.models"] = synthetic_models

        original_installed = list(settings.installed_apps)
        try:
            settings.installed_apps = [
                *original_installed,
                "synthetic_installed_app_fix4",
            ]

            # Force a reimport via a sentinel attribute that we'll
            # clear, then check discover_models re-touches the module.
            import importlib
            with patch.object(
                importlib, "import_module", wraps=importlib.import_module
            ):
                # discover_models uses the lower-level __import__ rather
                # than importlib, so we patch __builtins__ instead.
                pass

            attempted: list[str] = []
            real_import = __builtins__["__import__"] if isinstance(
                __builtins__, dict
            ) else __builtins__.__import__

            def recording_import(name, *args, **kwargs):
                attempted.append(name)
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=recording_import):
                discover_models(silent=True)

            # discover_models must have probed our synthetic app's
            # .models module — the pre-fix hardcoded shortlist never did.
            assert "synthetic_installed_app_fix4.models" in attempted
        finally:
            settings.installed_apps = original_installed
            sys.modules.pop("synthetic_installed_app_fix4", None)
            sys.modules.pop("synthetic_installed_app_fix4.models", None)
