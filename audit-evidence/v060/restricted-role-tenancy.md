# Restricted-role tenancy evidence

Date: 2026-09-09

This gate ran against the local PostgreSQL `aksara_test` database. The test
creates a temporary login role and asserts that PostgreSQL reports both
`rolsuper = false` and `rolbypassrls = false`. It drops the temporary table and
role during teardown.

Command (credentials supplied through the local environment):

```console
DATABASE_URL="$AKSARA_TEST_DATABASE_URL" AKSARA_REQUIRE_DATABASE_TESTS=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPYCACHEPREFIX=/tmp/aksara-v060-pycache PYTHONPATH="$PWD" /tmp/aksara-v055-py311/bin/python -m pytest -p pytest_asyncio.plugin -vv -x tests/security/test_restricted_role_tenancy.py
```

Result: **1 passed in 0.37s**.

The test proves these behaviors while reusing one physical connection for
tenant A, tenant B, and an unset tenant:

- direct ORM reads expose only the active tenant;
- cross-tenant inserts fail and cross-tenant updates affect zero rows;
- generated API list, retrieve, create, and update operations preserve the
  database boundary;
- `tenant_id` is assigned from the authenticated principal, and a body that
  tries to forge it is rejected;
- an MCP-principal request can discover the route-derived update tool, and the
  described REST operation cannot mutate another tenant;
- `TaskWorker` restores and clears tenant context across A, B, and unset jobs;
- the other tenant's persisted record remains unchanged.

The repository exposes an MCP-shaped tool catalog at `/ai/tools/mcp`; it does
not contain an MCP protocol execution transport. This evidence therefore does
not claim protocol-level MCP authorization.
