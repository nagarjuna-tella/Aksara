# Inspect TypeScript client generation

**Evolving; generated v0.7.0 output has a known type-checking defect.** Aksara can
render a fetch-based CRUD client from ViewSets, but the ticket-desk output does
not currently pass TypeScript 5.9.3. Treat it as generated material to review,
not a production-ready client. The defect requires a separately scoped generator
patch; v0.7.1 documentation work does not change runtime generation.

## Generate from explicit ViewSets

After creating the [first-project ticket desk](../getting-started/first-project.md),
save this file beside `main.py`. It uses the public Python generator and the
same application ViewSet; it does not connect to PostgreSQL.

```python title="generate_client.py"
from pathlib import Path

from aksara.sdk import generate_typescript_sdk
from app.views import TicketViewSet

Path("api.ts").write_text(generate_typescript_sdk([TicketViewSet]))
```

```bash
python generate_client.py
```

The output includes `TicketCreate`, `TicketUpdate`, `TicketRead`, query parameter
interfaces and an `AksaraClient`. Generated methods cover list, get, create,
update and delete. Custom actions and durable-operation endpoints are not
included automatically. Regenerate after changing the model or ViewSet schema.

## Verify before using the output

With TypeScript 5.9.3 available in a development environment:

```bash
tsc --strict --noEmit --lib ES2022,DOM api.ts
```

For the v0.7.0 ticket-desk ViewSet, this fails with:

```text
TS2322: Type 'TicketListParams' is not assignable to type 'Record<string, QueryValue>'.
Index signature for type 'string' is missing in type 'TicketListParams'.
```

Generation succeeding is therefore not sufficient validation. Do not silence
the error with a blanket TypeScript suppression or interpret it as a backend
API failure. Until a generator patch is available and verified, use your
application's existing HTTP client against the [REST API](../api/index.md).

## CLI discovery

The equivalent generator command is:

```bash
aksara generate sdk --views-module app.views --output api.ts
```

Options are `--language typescript` (the only supported language), `--output`
(default `api.ts`), `--views-module` and `--stdout`. The application module must
be importable in the CLI process. In an isolated wheel environment, an
uninstalled `app.views` directory was not discovered by the console command;
it reported `No ViewSets discovered`. The explicit Python script above avoids
that discovery ambiguity without changing framework configuration.

## Client behavior to review

Generated clients accept `baseUrl`, `headers` and a custom `fetch` implementation.
They do not implement login or token refresh. Supply credentials according to
your application's authentication boundary; generated TypeScript types do not
replace server permissions, policy or tenant checks.

The current client uses JSON bodies and PATCH for updates. On a non-success
HTTP response it throws an `Error` containing the status and status text; it
does not preserve structured backend error bodies automatically. The TypeScript
interfaces are static declarations, not runtime response validation. Review
pagination, nullable values, mounted route prefixes and custom serializers for
your actual ViewSets before adopting generated output.
