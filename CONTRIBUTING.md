# Contributing to Aksara

Thanks for your interest in improving Aksara. This guide covers how to set up a
development environment, the conventions the project follows, and what to expect
when you open an issue or pull request.

Aksara is an AI-native async backend framework for PostgreSQL. Because it
generates REST APIs, migrations, Studio surfaces, and MCP tools from your models,
correctness and safety matter more than feature volume — contributions are
weighed against that bar.

## Code of Conduct

This project follows a [Code of Conduct](CODE_OF_CONDUCT.md). By participating,
you agree to uphold it.

## Ways to Contribute

- **Report bugs** — open a bug report with steps to reproduce.
- **Request features** — open a feature request describing the problem first.
- **Improve docs** — fixes to anything under `docs/docs/` are always welcome.
- **Submit code** — bug fixes and features, ideally tied to an existing issue.
- **Report security issues** — do **not** open a public issue. Follow
  [SECURITY.md](SECURITY.md).

## Development Setup

Requirements:

| Dependency | Version |
|------------|---------|
| Python | 3.11+ |
| PostgreSQL | 13+ |

Clone and install with the development extras:

```bash
git clone https://github.com/nagarjuna-tella/Aksara.git
cd Aksara
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Install the git hooks so formatting and linting run before each commit:

```bash
pre-commit install
```

Verify the install:

```bash
aksara --version
```

A running PostgreSQL instance is needed for the test suite. See
[docs/docs/getting-started/installation.md](docs/docs/getting-started/installation.md)
for setup options (Homebrew, apt, Docker).

## Running Tests

The full suite uses `pytest`:

```bash
DATABASE_URL="postgresql://user:pass@localhost:5432/aksara_test" pytest tests/
```

Useful subsets:

```bash
pytest tests/fields* tests/test_fields.py tests/test_fields_new.py tests/test_fields_extended.py
pytest tests/security/
pytest tests/diagnostics/
pytest -m fuzz        # bounded adversarial / property-based tests
```

New code should ship with tests. Bug fixes should include a regression test that
fails before the fix and passes after.

## Code Quality

The project uses Black, Ruff, and mypy. Historical Ruff and mypy debt is
recorded by rule/error code and must only move downward. Run the enforced gate
before pushing:

```bash
python scripts/check_static_baseline.py
```

Format new Python files and focused new code with Black. Run Ruff on new files
directly; when editing a legacy file, review the changed lines and ensure the
repository baseline does not grow. The baseline is not a claim that existing
findings are acceptable forever. See `STATIC_ANALYSIS_BASELINE.md` for the
classification and ratchet policy.

`pre-commit` runs the same baseline command. If it fails, fix the added finding.
Changing `static-analysis-baseline.json` requires explicit review and must never
be used to hide a new violation.

## Commit Messages

Follow the existing [Conventional Commits](https://www.conventionalcommits.org/)
style used in the history:

```
feat(orm): add strict coercion for primitive fields
fix(migrations): harden rename detection
docs: clarify installation steps
test: cover tenant policy edge cases
```

Common types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`. Keep the
subject line concise and explain the *why* in the body when it isn't obvious.

## Pull Requests

1. Check for an existing issue, or open one to discuss the change first.
2. Fork the repo and create a feature branch off `main`.
3. Make your change with tests and updated docs where relevant.
4. Ensure relevant tests pass and `python scripts/check_static_baseline.py`
   remains at or below its reviewed Ruff/mypy baseline.
5. Open a pull request and fill out the template.

Keep pull requests focused — one logical change per PR is easier to review and
land. Larger or architectural changes are best discussed in an issue before you
invest significant time.

User-facing changes should be reflected in [CHANGELOG.md](CHANGELOG.md).

## Documentation

Docs are built with MkDocs and live under `docs/docs/`. Preview locally:

```bash
python -m mkdocs serve -f docs/mkdocs.yml
```

Before opening a docs PR, run the strict build:

```bash
python -m mkdocs build --strict -f docs/mkdocs.yml
```

## Questions

If something here is unclear, open an issue and we'll improve this guide.
