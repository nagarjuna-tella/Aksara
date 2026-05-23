# Security Policy

Aksara takes security seriously. If you find something that looks wrong, please
report it privately so maintainers can investigate before details are public.

## Supported Versions

Security fixes are maintained on the current release line. Upgrade to the latest
available version before reporting a vulnerability unless the issue is specific
to an older release.

| Version | Supported |
|---------|-----------|
| 0.5.x (current) | Active security fixes |
| < 0.5 | Not supported |

A formal long-term supported-version policy has not been finalized.

## Reporting a Vulnerability

Please do not open a public issue for security reports.

Use GitHub's [private security advisory](../../security/advisories/new) when
available. If private advisories are unavailable for your fork or environment,
contact the project maintainers privately through the existing project contact
channels.

When reporting, include:

- Affected version or commit
- Steps to reproduce
- Expected and observed behavior
- Security impact and any affected surfaces
- Whether the issue is already public

## Security Posture

Aksara includes security diagnostics, runtime field-level enforcement for covered
generated write paths, tenant-aware policy checks, MCP credential hardening
helpers, bounded adversarial tests for generated surfaces, and release-trust
workflow preparation for dependency audit, static analysis, secret scanning,
SBOM generation, package build verification, and PyPI Trusted Publishing.

Aksara does not currently make a blanket production-readiness claim. Users should
run production diagnostics, review the hardening guide, and evaluate release
gate results before deployment.

## Security Documentation

Public security documentation lives under:

- [Security Overview](docs/docs/security/overview.md)
- [Production Hardening](docs/docs/security/production-hardening.md)
- [Security Coverage](docs/docs/security/security-coverage.md)
- [Release Security](docs/docs/security/release-security.md)

## Private Security Matrix

The public repository includes `security/security_matrix.example.yml` to show
the expected matrix structure without publishing private project coverage
details.

Private projects or release processes may maintain
`security/security_matrix.yml`. That file is intentionally git-ignored and
should not be published accidentally.

By default, a missing private matrix is a warning. To make a missing or invalid
private matrix a blocking diagnostic condition, set:

```bash
AKSARA_REQUIRE_SECURITY_MATRIX=true
```

## Disclosure and Patch Expectations

- Critical issues such as authentication bypass, SQL injection, or cross-tenant
  data leakage are prioritized for urgent fixes.
- High-impact issues such as unsafe generated-surface exposure, field-level
  authorization bypass, or Studio/MCP exposure are prioritized for near-term
  patches.
- Lower-impact issues are handled through the regular release process.

Security fixes are documented in [CHANGELOG.md](CHANGELOG.md) when released.
