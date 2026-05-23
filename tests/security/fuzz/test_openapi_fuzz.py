from __future__ import annotations

import pytest


pytestmark = [pytest.mark.security, pytest.mark.fuzz]

schemathesis = pytest.importorskip(
    "schemathesis",
    reason=(
        "schemathesis is not installed; OpenAPI fuzzing is optional in Round 5. "
        "Run this skeleton with schemathesis installed against a generated FastAPI app."
    ),
)


@pytest.mark.skip(reason="Round 5 skeleton: no lightweight generated CRUD OpenAPI test app is configured yet.")
def test_openapi_fuzz_no_500s_on_generated_crud_endpoints():
    """Schemathesis entrypoint placeholder for generated CRUD endpoint fuzzing."""


@pytest.mark.skip(reason="Round 5 skeleton: requires a generated CRUD OpenAPI app and schemathesis.")
def test_openapi_fuzz_forbidden_fields_do_not_mutate():
    """Schemathesis security-invariant placeholder for forbidden write fields."""
