# Development tools

Use these commands from your configured project directory. The
[generated reference](../reference/cli-reference.md) contains exact flags; the
[first-project tutorial](../getting-started/first-project.md) supplies a working
application to inspect.

## Inspect registered models

```bash
aksara models --app app.models
aksara models --app app.models --ai
aksara inspect models --help
aksara info
aksara status
```

`models --ai` includes AI metadata, not an authorization decision. Discovery
requires importable model modules. For HTTP routes, inspect your running app's
OpenAPI document (`/openapi.json`) or API documentation (`/docs`); there is no
`aksara routes` command in 0.7.0. OpenAPI describes exposed routes, not proof that
a caller is authorized to use them.

## Run local quality tools

Install the tools you choose in your development environment. These commands
wrap external tools; they do not bundle a universal test or quality policy.

```bash
aksara format --check
aksara lint
aksara typecheck
aksara test tests/ -v --tb=short
aksara test tests/ -x
```

`format` runs Black, `lint` runs Ruff, `typecheck` runs mypy, and `test` passes
arguments through to pytest. `format` without `--check` rewrites files;
`lint --fix` applies Ruff fixes. Use pytest's `-x` for first-failure stopping.
Parallel pytest requires `pytest-xdist` and its `-n` option; `--parallel` and
`--failfast` are not Aksara aliases. Database tests also need isolated databases
or schemas before parallel execution is safe. Coverage options require the
corresponding pytest plugin.

## Inspect data interactively

```bash
aksara shell
aksara shell --no-ipython
```

The shell provides `arun()` for async expressions and uses IPython when
available. Import your model explicitly if it is not in the shell namespace.
Apply your application's tenant scope and authorization rules before querying
real data. An operator shell does not represent an authenticated HTTP caller.

For PostgreSQL administration, use the PostgreSQL client with your deployment's
credential handling. There is no `aksara dbshell` command in 0.7.0.

## Inspect query diagnostics

```bash
aksara db stats --help
aksara db profile --help
aksara inspect queries --help
```

These commands expose their configured inspection surfaces; they do not profile
an arbitrary URL simply because you supply one. Historical `aksara profile` and
`aksara querycount` examples are not available commands. See
[debugging](../debugging/index.md) for runtime instrumentation and its limits.

## Generate code and migrations

Use the [TypeScript guide](../how-to/typescript-client.md) for SDK generation,
including the public 0.7.0 compilation limitation. Model, serializer, and full
CRUD natural-language generators are not registered under `aksara generate`.

For data changes, create and review migration operations using the
[migrations guide](../orm/migrations.md). There is no `makemigrations --empty`
flag. Do not copy Django migration signatures into Aksara migrations.

Fixture import/export (`dumpdata`/`loaddata`), `shell_plus`, and `watch` are not
available CLI commands in 0.7.0. Their absence is not a release commitment to add
them. Use application-owned scripts or existing ecosystem tools where needed.
