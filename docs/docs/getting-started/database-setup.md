# Set up PostgreSQL

Aksara uses PostgreSQL through asyncpg. For the tested versions, see
[runtime compatibility](../reference/runtime-compatibility.md). Install the
server using the [PostgreSQL downloads and platform instructions](https://www.postgresql.org/download/),
or use a database supplied by your development environment. Installing the
Python package does not provision PostgreSQL.

Use a database reserved for the tutorial or application. Migrations change its
schema; do not point a new tutorial at unrelated application data.

## Configure a local project

From the generated project directory, the interactive helper can write the
connection URL:

```bash
aksara dbsetup
```

It checks reachability, asks for a database name, username and password, connects
to the maintenance database `postgres`, and creates the requested database if
it is absent. An existing database is retained. The role needs access to the
maintenance database and, for a new database, permission to create it. The
helper does not create application roles or configure production privileges.

`--host` and `--port` choose another server. If `.env` already contains
`DATABASE_URL`, the helper asks before overwriting it; an existing URL can
supply the host and port. Check the selected target rather than assuming that
an overwrite switches servers.

You can instead edit `.env` with credentials supplied by your database
administrator. This is a format example, not a working credential:

```dotenv
DATABASE_URL=postgresql://username:password@localhost:5432/myproject
```

URL-encode special characters in credentials. Keep secrets out of source,
logs and support reports. `AKSARA_DATABASE_URL` takes precedence over
`DATABASE_URL`; use one consistently so an old value cannot redirect commands.
Existing process environment takes precedence over values loaded from `.env`.
A file named `.env.test` or `.env.production` is not selected automatically.
See [settings precedence](../reference/settings-reference.md).

## Verify a connection without changing tables

Save this standalone probe as `check_database.py` in the project directory:

```python title="check_database.py"
import asyncio
from aksara.conf import settings
from aksara.db import Database


async def check_database():
    if not settings.database_url:
        raise RuntimeError("Set AKSARA_DATABASE_URL or DATABASE_URL first")
    db = Database(database_url=settings.database_url, min_size=1, max_size=2)
    try:
        await db.connect()
        assert await db.fetchval("SELECT 1") == 1
        print("Database connection verified")
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(check_database())
```

```bash
python check_database.py
```

This opens and closes its own pool and runs a read-only query. It verifies
connectivity, not migrations, application privileges, RLS or production
readiness. Run it as a separate process: constructing a `Database` also replaces
the process-wide instance used by `Database.get_instance()`.

## Connect the application lifespan

The basic scaffold passes `settings.database_url` into `Aksara(...)`. Keep that
handoff: setting the global URL alone does not start the app's database
lifespan. Its normal startup connects the pool and normal shutdown disconnects
it. Connections acquired by supported database/session/transaction helpers are
returned according to those helpers' ownership rules.

Pool option names differ by interface:

| Interface | Minimum / maximum options |
| --- | --- |
| `configure(...)` / global settings | `pool_min_size`, `pool_max_size` |
| `Aksara(...)` | `min_pool_size`, `max_pool_size` |
| `Database(...)` | `min_size`, `max_size` |

The default minimum and maximum are 5 and 20. Pass the effective settings to
the application constructor explicitly when overriding pool sizes; see the
[canonical configuration example](../reference/settings-reference.md). Budget
connections across all web and worker processes, migrations and administrative
clients. Measure concurrency and pool waits instead of choosing sizes from a
traffic-label table.

Creating another `Database` is not transparent replica routing. It changes the
singleton and requires explicit connection/lifecycle ownership. An independent
connection also does not join an existing atomic transaction. See
[transaction boundaries](../orm/expressions-and-transactions.md).

## Apply migrations and serve

Follow the [first-project tutorial](first-project.md) for its exact model and
migration sequence, or the [domain template instructions](patterns.md) for flat
module copies. Review generated migration files before applying them. A
successful connectivity probe does not mean application tables exist.

Continue to [running your app](running-your-app.md) after migrations and
application authentication are configured.

## Diagnose a connection failure

- **Server unreachable:** check the server process, host, port and network path.
- **Authentication failure:** verify the selected URL, role and PostgreSQL authentication policy. Do not weaken that policy merely to make a probe pass.
- **Database missing:** have the database created by an authorized role, or use the local helper with the required permission.
- **Too many connections:** account for every process's pool and server capacity before changing limits.
- **TLS failure:** use the database provider's certificate and hostname-verification configuration; encryption alone does not establish server identity.

Database connection setup can wrap the underlying error in
`AksaraConnectionError`; inspect the cause privately and redact connection
information before sharing it. The [exception reference](../reference/exceptions.md)
explains the distinction between Aksara and driver errors. Aksara passes the DSN
to asyncpg; do not assume every libpq connection parameter is supported by that
driver.

For production, use the [deployment guide](../tutorials/deployment.md): separate
migration and application roles, restricted privileges, actual RLS policies
where needed, secret management, diagnostics and backups.
