# Security Policy

Aksara is moving fast and we take security seriously. If you find something that looks wrong, please tell us we'd rather hear it from you first.

## Supported Versions

We only maintain active security fixes on the current release. If you're on an older version, upgrade first.

| Version | Supported          |
|---------|--------------------|
| 0.5.x   | ✅ Active          |
| < 0.5   | ❌ No longer supported |

## Reporting a Vulnerability

**Please don't open a public issue.** Use GitHub's [private security advisory](../../security/advisories/new) instead, it's visible only to you and the maintainers until a fix is released, then the details are published automatically alongside the patch.

When you report, we'll:

- Acknowledge within **48 hours**
- Target a patch within **7 days** for critical issues
- Credit you in the release notes if you'd like

## What's In Scope

- Authentication or authorisation bypass
- SQL injection or unsafe query construction
- AI prompt injection or unsafe code execution
- Cross-tenant or cross-user data leakage
- Dependency vulnerabilities with a direct exploit path in Aksara

## What's Out of Scope

- Theoretical attacks with no proof of concept
- Vulnerabilities in example apps or documentation
- Issues introduced by deliberate misconfiguration (e.g. running `debug=True` in production)
- Upstream dependency vulnerabilities with no Aksara-specific impact (report those to the upstream project)

## Security Fix History

Past security fixes are documented in [CHANGELOG.md](CHANGELOG.md). Look for `security` entries within each version section.
