# Release Security

## Current Status

Aksara includes security diagnostics and adversarial test coverage, but
release-security automation is still being finalized before production-mode
claims.

## Current Manual Checks

- Full test suite
- Security tests
- Fuzz tests
- Diagnostics tests
- `aksara doctor security-check`
- `aksara doctor production-check`

## Planned Release Gates

- Dependency audit
- Static analysis
- Secret scanning
- SBOM generation
- Provenance
- PyPI Trusted Publishing
- Required production-check
- Optional/private security matrix enforcement
- External review before production-mode claim

## Production-Mode Claim

A production-mode claim should require:

- No known critical/high security issues
- Production-check passing
- Security/fuzz/diagnostic tests passing
- Release-gate CI passing
- Security docs complete
- External review completed or explicitly scoped
