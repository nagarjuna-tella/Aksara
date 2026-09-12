# Command-line tools

Use the CLI to create a project, manage migrations, run the server, and inspect
application health. Start with the [first-project tutorial](../getting-started/first-project.md)
for a tested sequence with PostgreSQL and authenticated requests.

```bash
aksara --version
aksara --help
aksara migrate --help
aksara doctor --help
```

Choose a task:

| Task | Where to start |
|---|---|
| Create, migrate, and serve an app | [CLI workflows](commands.md) |
| Inspect models or run quality tools | [Development tools](dev-tools.md) |
| Find exact arguments, flags, and parser defaults | [Generated CLI reference](../reference/cli-reference.md) |
| Configure database and application settings | [Settings reference](../reference/settings-reference.md) |
| Check production readiness | [Doctor](../diagnostics.md) |
| Operate ordinary background tasks | [Tasks](../advanced/background-tasks.md) |
| Run durable workers | [Durable Operations](../advanced/durable-operations.md) |
| Explore optional AI commands | [Experimental AI commands](ai-commands.md) |

Global output flags go **before** the command:

```bash
aksara --plain --no-color info
aksara --quiet migrate
```

`--quiet` suppresses non-error Aksara UI output, not subprocess output or Uvicorn
logs. `--plain` disables Rich rendering and animation. `--no-color` and
`--force-color` control terminal colors.

Exit status depends on the command. Click reports invalid arguments as exit 2;
Doctor has its own [policy-specific exit codes](../diagnostics.md). Do not assume
a universal configuration/database/migration error-code table, or that a zero
exit proves application health. Use each command's documented checks.
