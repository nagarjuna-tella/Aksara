# Releasing

Aksara release publishing should be gated, reproducible, and based on PyPI
Trusted Publishing. This page documents the intended release process; it does
not publish packages by itself.

## Release Candidate Checks

Before a production-mode claim or public release candidate, run the release gate
workflow and confirm these checks pass:

- Full test suite
- Security tests
- Diagnostics tests
- Bounded fuzz/adversarial tests
- DB-backed migration tests (transactional application, advisory lock, and
  checksum verification) against a real PostgreSQL database
- A migration smoke check: `aksara migrate` and `aksara status` against a
  scratch database, confirming checksum recording and verification
- `AKSARA_SECURITY_MATRIX_PATH=security/security_matrix.release.yml aksara doctor production-check --release`
- Strict docs build
- Dependency audit
- Static analysis
- Secret scan
- Package build
- `twine check`
- Wheel import verification
- SBOM generation

## PyPI Trusted Publishing

The plain production check is a deployment diagnostic: warnings remain
advisory. The `--release` form is the release-candidate gate and fails unless
every diagnostic passes, the matrix contains no planned or partial scenarios,
and each implemented surface has covered evidence.

Configure PyPI Trusted Publishing in the PyPI project settings:

- Publisher: GitHub
- Repository: `nagarjuna-tella/Aksara`
- Workflow: `publish.yml`
- Environment: `pypi`

The publish workflow uses GitHub OIDC and does not require a PyPI API token.
Keep the `pypi` environment protected so maintainers must approve publishing.

## Publish Workflow

Publishing is manual. Use the `Publish Package` workflow only after release-gate
checks pass and the protected `pypi` environment is ready.

The workflow:

1. Builds wheel and source distributions.
2. Runs `twine check`.
3. Publishes through `pypa/gh-action-pypi-publish` using Trusted Publishing.

## Provenance and Signing

Release artifacts should be traceable to:

- Git tag
- GitHub Actions run
- Built wheel and source distribution
- SBOM artifact
- Release notes and changelog entry

Signed tags or commits may be required by project policy before a
production-mode claim.

## What This Does Not Mean

These release gates prepare Aksara for trustworthy releases. They do not replace
external security review and do not constitute a production-readiness claim.
