# Generated API abuse evidence

Date: 2026-09-09

The generated CRUD abuse suite ran against the local PostgreSQL `aksara_test`
database with real tables and persistence.

Command (credentials supplied through the local environment):

```console
DATABASE_URL="$AKSARA_TEST_DATABASE_URL" AKSARA_REQUIRE_DATABASE_TESTS=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPYCACHEPREFIX=/tmp/aksara-v060-pycache PYTHONPATH="$PWD" /tmp/aksara-v055-py311/bin/python -m pytest -p pytest_asyncio.plugin -vv -x tests/security/fuzz/test_openapi_fuzz.py
```

Result: **3 passed in 0.24s**.

The suite verifies invalid scalar types, missing required fields, string and
integer bounds, unknown properties, malformed and nonexistent foreign keys,
malformed JSON, protected fields, and server-owned fields. Every rejected
request returns structured JSON below status 500 and leaves persisted state
unchanged. Anonymous and authenticated-but-forbidden mutations also leave state
unchanged. Generated create and update schemas reject additional properties and
omit server-owned fields.

Combined API, schema, field-policy, tenancy, restricted-role, and abuse
regressions: **105 passed, 2 dependency deprecation warnings in 0.47s**.
