"""Studio test configuration.

Redirects the working directory to a temporary path for every test so that
``save_aihub_settings`` (which writes ``aksara.ai.json`` relative to cwd)
never pollutes the project root and never leaks state between test runs.
"""

import pytest


@pytest.fixture(autouse=True)
def _studio_cwd_isolation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
