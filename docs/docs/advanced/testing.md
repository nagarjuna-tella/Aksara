# Testing applications

Test application rules without a database where possible, then exercise persistence
and HTTP behavior against a dedicated PostgreSQL database. Aksara does not supply
an automatically isolated pytest database, a factory framework, or automatic
pytest execution of `AksaraTestCase.asyncSetUp()`.

The [first-project tutorial](../getting-started/first-project.md#6-test-the-running-application)
provides complete HTTP tests for the Ticket Desk application. Later chapters add
[relation and validation tests](../tutorials/ticket-desk.md),
[tenant isolation](../tutorials/ticket-desk-tenancy.md),
[background work](../tutorials/ticket-desk-reports.md), and
[durable recovery](../tutorials/ticket-desk-durable.md).
Use these as the integration path alongside the unit tests below.

## Install and run unit tests

In your application's virtual environment:

```bash
python -m pip install aksara-framework pytest pytest-asyncio httpx
```

There is no `aksara-framework[test]` extra in 0.7.0. The `dev` extra contains
framework development tools; an application can install its test dependencies
explicitly instead.

Save the following standalone example as `tests/test_ticket_rules.py`:

```python title="tests/test_ticket_rules.py"
from types import SimpleNamespace

import pytest

from aksara import Model, fields
from aksara.api.serializers import ModelSerializer
from aksara.exceptions import ValidationError
from aksara.permissions import IsAuthenticated
from aksara.testing import create_test_user


class RuleTicket(Model):
    subject = fields.String(max_length=200)
    resolved = fields.Boolean(default=False)


class TicketInput(ModelSerializer):
    class Meta:
        model = RuleTicket
        fields = ["subject", "resolved"]
        read_only_fields = ["resolved"]

    def validate_subject(self, value):
        subject = value.strip()
        if not subject:
            raise ValidationError(
                "Invalid subject", errors={"subject": "A subject is required"}
            )
        return subject


def test_subject_normalization_and_server_owned_field():
    serializer = TicketInput(data={"subject": "  Help  ", "resolved": True})
    assert serializer.is_valid()
    assert serializer.validated_data["subject"] == "Help"
    assert "resolved" not in serializer.validated_data


def test_blank_subject_is_rejected():
    with pytest.raises(ValidationError) as error:
        TicketInput(data={"subject": "  "}).is_valid()
    assert error.value.errors == {"subject": "A subject is required"}


def test_permission_receives_application_identity():
    request = SimpleNamespace(state=SimpleNamespace(user=None))
    permission = IsAuthenticated()
    assert not permission.has_permission(request)
    request.state.user = create_test_user(username="alice")
    assert permission.has_permission(request)
```

```bash
python -m pytest tests/test_ticket_rules.py -q
```

These three tests need no database: they never call `save()` or an ORM query.
The synthetic request deliberately tests a permission predicate. It does not
prove that an HTTP authentication adapter validates a credential or rejects an
inactive account. Add tests for those boundaries using the application's real
adapter, as in the tutorial.

For asynchronous pytest functions, use `@pytest.mark.asyncio` and
`@pytest_asyncio.fixture` for async fixtures, or configure your chosen
pytest-asyncio mode explicitly. Ordinary synchronous serializer and permission
methods should not be awaited.

## Database tests and cleanup

Use a dedicated database such as `aksara_test`, configured through your local
`DATABASE_URL`. Apply the application's migrations before running integration
tests. Never point destructive test cleanup at a production database.

Choose isolation to match the work being tested:

| Test boundary | Suitable isolation |
|---|---|
| One task using the documented transaction context | Roll back that transaction after assertions, on the same pinned connection |
| Requests handled by a running server | Create and delete test-owned records, or use a disposable migrated database/schema |
| Tasks, durable workers, subprocesses, or commit/recovery tests | A disposable migrated database/schema shared by those processes, with explicit cleanup after they stop |
| RLS enforcement | A restricted application role with actual policies; verify denials as that role |

A transaction opened in the test process does not automatically cover another
process, another pool connection, or work scheduled in another task. See
[transactions](../orm/expressions-and-transactions.md) for connection pinning, nested savepoints, and
the prohibition on concurrent use of one transaction connection.

For application fixtures, connect a `Database` explicitly and disconnect it in
`finally`. Own the schema or records you remove. If you use a schema, configure
every participating connection to use it and stop workers before dropping it.
Do not create arbitrary tables instead of applying migrations when the purpose
of the test is to prove that the application can be installed or upgraded.

The tutorial's HTTP tests delete their own tickets in `finally`; their server
uses the configured database. This is record cleanup, not a clean database per
test. Dedicated databases also prevent test runs from changing development data.

## HTTP and authorization assertions

Use the real authentication middleware and send the credential the application
accepts. Include anonymous, invalid-credential, unauthorized-user, and authorized
cases. For tenant applications, also try another tenant's identifiers and forged
server-owned fields. A test header or a constructed user object alone does not
exercise credential verification.

With Starlette's synchronous `TestClient`, enter its context manager to run the
application lifespan and call `client.get()` without `await`. If you use an
async HTTPX ASGI transport, arrange lifespan startup and shutdown explicitly;
transport construction alone does not start the application's database pool.

Assert the route's actual contract. Generated resource collections use a trailing
slash and a paginated response envelope; detail routes have no trailing slash.
The first-project adapter returns 403 for anonymous generated requests. Do not
assume all authentication adapters or custom endpoints use that status. See the
[REST reference](../api/viewsets.md) for the generated contract.

## Scope of `aksara.testing` helpers

The helper module has a narrower contract than a full test framework:

| Helper | Behavior and limit |
|---|---|
| `create_test_user()` | Synchronous in-memory user double; no database record or credential verification |
| `create_test_app()` | Async application construction; optionally applies migrations; the caller still owns lifespan and cleanup |
| `AksaraTestCase` | Plain class with explicit async setup/teardown methods; it is not `unittest.IsolatedAsyncioTestCase` and pytest does not automatically invoke those names |
| `AksaraTestClient` | Synchronous request methods even under its async context manager; `with_user()` adds an `X-Test-User-Id` header, not a production authentication mechanism |
| `test_database()` | With `cleanup=True`, pins same-task `Database` and ORM work to one transaction, rolls it back on every exit, and closes its owned pool |

`AksaraTestCase` does not create a client, implement `authenticate()`, or roll back
every test. `test_database(cleanup=True)` covers database activity performed in
the async task that entered the helper, including nested `atomic()` savepoints.
An independent connection cannot see those uncommitted writes, and the outer
rollback removes them after successful, exceptional, or cancelled exits.

The helper does not automatically place synchronous `TestClient` requests,
separate worker processes, or independently managed database connections inside
that transaction. Use explicit application fixtures and disposable database
schemas for those boundaries. With `cleanup=False`, writes commit normally, but
the helper still closes the pool it created.

There are no public `async_test`, `db_session`, `MigrationTestCase`,
`setup_test_database`, `capture_tasks`, or `mock_ai` helpers in `aksara.testing`.
Use pytest fixtures and your application's own factories or mocks. Mock an
external service at its adapter boundary; keep database constraint, transaction,
RLS, and recovery tests on the real implementation.

## Coverage and test selection

Install coverage support before requesting its pytest options:

```bash
python -m pip install pytest-cov
python -m pytest tests --cov=app --cov-report=term-missing
```

Replace `app` with your application package. Coverage measures executed lines,
not authorization correctness or recovery guarantees. Keep explicit denial and
failure-path assertions.

Custom pytest markers only label tests. Registering a marker named `ci_only`
does not skip anything automatically; use an explicit selection or skip rule.
Keep provider/network tests separate from deterministic application tests and
report skipped prerequisites rather than counting them as proven behavior.
