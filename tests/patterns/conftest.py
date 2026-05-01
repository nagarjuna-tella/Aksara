import os
import pytest


def pytest_configure(config):
    """Set DATABASE_URL before any module imports during collection."""
    os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")


@pytest.fixture(autouse=True)
def set_database_url_env_var():
    """Ensure DATABASE_URL is set so example settings can be imported."""
    original_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/testdb"
    yield
    if original_db_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original_db_url
