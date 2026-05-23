# Security Matrix

Aksara uses a **security matrix** (`security_matrix.yml`) as a canonical inventory of generated
surfaces, actors, risks, and adversarial test scenarios. It is used by `aksara doctor security-check`
and `aksara doctor production-check` to validate the security baseline before deployment.

## Public vs private

The public repository includes only `security_matrix.example.yml` — a minimal, non-sensitive
example showing the expected file structure. It is safe to commit.

Projects using Aksara maintain their own **private** `security_matrix.yml` that documents their
actual surfaces, actors, risks, and test coverage. This file:

- Is listed in `.gitignore` (never committed to public repos)
- Lives at `security/security_matrix.yml` relative to the project root
- Is loaded automatically by `aksara doctor security-check`

## Getting started

Copy the example file and customise it for your project:

```bash
cp security/security_matrix.example.yml security/security_matrix.yml
```

Then edit `security/security_matrix.yml` to reflect your actual surfaces, actors, risks, and
adversarial scenarios.

## Requiring the matrix in production

By default, a missing `security_matrix.yml` produces a **warning** (not a blocking error).

To make a missing or invalid matrix a **blocking deployment condition**, set:

```bash
export AKSARA_REQUIRE_SECURITY_MATRIX=true
```

With this flag, `aksara doctor production-check` will exit 1 if `security_matrix.yml` is absent
or fails validation.

## File format

See `security_matrix.example.yml` for the full structure. The matrix supports:

| Section | Description |
|---------|-------------|
| `metadata` | Project name, owner, status, round number |
| `surfaces` | Every generated or exposed data surface |
| `actors` | Every identity type that may call the surfaces |
| `risks` | Identified security risk categories |
| `scenarios` | Adversarial scenarios mapping surfaces, actors, and risks |

Scenario `status` values: `covered`, `partial`, `planned`, `not_applicable`.
