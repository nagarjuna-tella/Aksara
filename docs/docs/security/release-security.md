# Release Security

## Current Status

Aksara includes security diagnostics, adversarial test coverage, and
release-trust workflow preparation. This prepares releases for stronger review,
but it does not constitute an external audit or a production-readiness claim.

## CI Workflows

- `security.yml` runs dependency audit, static analysis, secret scanning,
  security tests, diagnostics tests, fuzz tests, and strict security docs checks
  on pull requests and pushes.
- `release-gate.yml` runs strict release-candidate checks, including the full
  test suite, production diagnostics, package build verification, dependency
  audit, static analysis, secret scanning, SBOM generation, and docs build.
- `codeql.yml` runs GitHub CodeQL analysis for Python.
- `publish.yml` is manual and uses PyPI Trusted Publishing/OIDC with the
  protected `pypi` environment. It does not use API tokens.
- `dependabot.yml` keeps Python and GitHub Actions dependencies visible through
  weekly update pull requests.

## Release Gate Criteria

A release candidate should pass:

- Full tests
- Security tests
- Diagnostics tests
- Bounded fuzz/adversarial tests
- Strict docs build
- Dependency audit for project dependencies
- Static analysis
- Secret scan
- Package build
- `twine check`
- Wheel import verification
- SBOM generation
- `aksara doctor production-check`

Public CI sets `AKSARA_REQUIRE_SECURITY_MATRIX=false` so private
`security/security_matrix.yml` coverage is not required in public workflows.
Private release environments may opt into strict private matrix enforcement with
`AKSARA_REQUIRE_SECURITY_MATRIX=true`.

Bandit currently gates high-severity findings. The existing non-security MD5 ID
generation finding is excluded from the blocking gate; medium and low findings
remain review backlog unless promoted by maintainers.

## Recommended Branch Protection

- Require pull request reviews.
- Require status checks from `security.yml`.
- Require status checks from `release-gate.yml` for release branches or release
  candidates.
- Block force pushes on release branches.
- Require signed commits or signed tags if that is project policy.
- Protect the `pypi` environment before enabling package publication.

## Trusted Publishing Preparation

PyPI Trusted Publishing should be configured in PyPI project settings:

- Publisher: GitHub
- Repository: `nagarjuna-tella/Aksara`
- Workflow: `publish.yml`
- Environment: `pypi`

Publishing remains manual and environment-gated. Do not add PyPI API tokens to
the repository or workflow secrets.

## External Review

External review prep lives in:

- `security/external-review-scope.md`
- `security/hardening-report-template.md`

Before a production-mode claim, the release decision should incorporate external
review findings, accepted risks, and retest notes.

## Production-Mode Claim

A production-mode claim should require:

- No known critical/high security issues
- Production-check passing
- Security/fuzz/diagnostic tests passing
- Release-gate CI passing
- Security docs complete
- External review completed or explicitly scoped
