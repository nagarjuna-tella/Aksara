# Install Aksara

Use Python 3.11–3.14 and PostgreSQL. Release CI tests PostgreSQL 16; the local
reference application has also been checked on PostgreSQL 18.4. See
[runtime compatibility](../reference/runtime-compatibility.md) for the tested
Python and FastAPI/Starlette pairs. These are test boundaries, not certification
of every operating system or dependency combination.

## Install into a virtual environment

From a working directory on macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install "aksara-framework==0.7.1"
aksara --version
python -m pip show aksara-framework
```

The distribution is named **aksara-framework**; Python code imports **aksara**.
The CLI and Python package expose the same version. Pin the version you intend
to deploy and review the [upgrade guide](../operations/upgrade-v07.md) before
changing an existing application.

The package installs its declared runtime dependencies, including asyncpg,
FastAPI, Pydantic and Uvicorn. It does not install or start a PostgreSQL server.
The [database setup guide](database-setup.md) covers that separate prerequisite.
No model provider is needed to build a REST application.

## Development tools

For the optional framework development/test tools:

```bash
python -m pip install "aksara-framework[dev]==0.7.1"
```

Quote extras such as `[dev]` so shells do not treat the brackets as a filename
pattern. The extra includes pytest, pytest-asyncio, Hypothesis, Black, Ruff,
mypy and pre-commit. The tutorial gives the smaller application test command
set when you reach that step.

## Work on the framework source

Contributors can install a checkout instead of the published package:

```bash
git clone https://github.com/nagarjuna-tella/Aksara.git aksara-framework-source
cd aksara-framework-source
python -m pip install -e ".[dev]"
```

This installs the checked-out framework and its development dependencies. It
is distinct from installing a generated application. The generated basic
project currently has an editable-packaging limitation; follow its README and
[template setup](patterns.md) rather than assuming the same editable command
works there. Source checkout installation does not select a released version;
inspect the branch and version you are developing.

## Verify the environment

Use the same interpreter for installation, tests and the server. If imports fail:

```bash
python -c "import sys; print(sys.executable)"
python -m pip show aksara-framework
python -c "import aksara; print(aksara.__version__)"
```

A successful import proves the package is installed, not that PostgreSQL,
migrations or application authentication are configured. After completing the
project setup, [Doctor](../diagnostics.md) checks the configured application:

```bash
aksara doctor launch-check
```

## Build the first application

Continue with [First project: a ticket desk](first-project.md). It supplies the
model, migration, authentication adapter, server and tests in one sequence.
Use [project layout](project-layout.md) to locate files and the authoritative
[settings reference](../reference/settings-reference.md) for environment
precedence. Avoid maintaining separate, conflicting configuration recipes.
