# Releasing

Aksara release publishing should be gated, reproducible, and based on PyPI
Trusted Publishing. This page documents the intended release process; it does
not publish packages by itself.

## Release Candidate Checks

Before a production-mode claim or public release candidate, run the release gate
workflow and confirm these checks pass:

- Full test suite on Python 3.11 and 3.14 at both supported web dependency
  boundaries, with required database tests enabled
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
- Packaged production reference application
- Installed-wheel documentation journey
- SBOM generation

## Evidence for the selected candidate

Record the exact commit, Python/dependency versions, PostgreSQL environment,
commands, results, and artifact hashes. The hosted matrix uses PostgreSQL 16
with pgvector and `AKSARA_REQUIRE_DATABASE_TESTS=1`; a local run on another
PostgreSQL version is useful evidence but does not replace that hosted check.
Database skips are not successful database validation.

Build and exercise the candidate wheel outside the checkout so source imports
cannot hide packaging or public-example failures. Rerun affected checks after
candidate changes. Preserve older release evidence as historical records; do
not relabel a prior commit's results as validation of the new candidate.

For a documentation-only candidate, include executable public examples and
scaffold guidance checks as well as a comparison of production-source changes
against the previous release. Documentation work does not waive runtime
regression checks.

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
checks pass for the exact selected ref and the protected `pypi` environment is
ready. The publish job itself does not rerun the release suite. A named
environment in YAML is not proof that required-reviewer protection has been
configured; verify that setting before dispatch.

Pushing a `v*` tag runs the release-gate workflow; it does not publish a
package. Creating a GitHub Release also does not trigger publication. Package
publication requires a separate manual dispatch of `publish.yml` with the
`confirm` input set to `publish` and the verified release tag selected as the
workflow ref.

The workflow:

1. Checks out the exact ref selected for the manual dispatch.
2. Builds wheel and source distributions from that ref.
3. Runs `twine check`.
4. Publishes through `pypa/gh-action-pypi-publish` using Trusted Publishing.

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
