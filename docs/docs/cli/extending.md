# Application-owned commands

Aksara 0.7.0 does not provide the `Command`, `CommandGroup`, `register_command`,
or `CommandTestCase` APIs shown in older versions of this guide. It does not
automatically discover an application's `commands/` directory or load an
`aksara.commands` entry-point group.

For project-specific administration, write a normal Python command using
`argparse` or your chosen CLI library. Give it its own entry point. A file in
your application does not add a subcommand to the installed `aksara` executable.

## Start with a standalone command

Save this as `greet.py` in your project:

```python title="greet.py"
import argparse


def main():
    parser = argparse.ArgumentParser(description="Greet someone by name.")
    parser.add_argument("name")
    parser.add_argument("--excited", action="store_true")
    args = parser.parse_args()
    suffix = "!" if args.excited else "."
    print(f"Hello, {args.name}{suffix}")


if __name__ == "__main__":
    main()
```

```bash
python greet.py World --excited
python greet.py --help
```

The first invocation prints `Hello, World!`. This uses only Python's standard
library. You can package a real application command under your own
`[project.scripts]` entry once its application lifecycle is defined.

## Add application behavior deliberately

A script that uses Aksara needs the same explicit application configuration and
database lifecycle as other application code. Import your settings and models,
connect the intended database, and close it on failure as well as success.
An administrative process does not automatically acquire the Principal or
tenant of an HTTP request.

For tenant-scoped commands, establish a trusted tenant and use the intended
restricted database role. For user-authorized work, resolve the current actor
and apply the application's permission and policy checks. Do not treat a
command-line identifier as proof of membership or authority.

Use ordinary [migration commands](commands.md) for schema changes. If a command
admits work that must survive retries and worker loss, call the public
[Durable Operations](../advanced/durable-operations.md) interface with the same
application-owned action and resolver registration used by your workers.

## Test the command boundary

Invoke the script in a subprocess and check its exit status, stdout, and stderr.
For commands with database effects, test tenant isolation, denied authority,
rollback, cleanup, and retry behavior where applicable. Keep credentials in
your deployment's environment or secret configuration rather than command
arguments or captured test output.

This is an application-owned extension pattern, not a framework plugin API or
a promise that custom commands inherit Aksara authentication automatically.
