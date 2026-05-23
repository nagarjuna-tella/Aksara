# Security Engineering Artifacts

This directory contains public-safe security engineering artifacts.

## Public Example Matrix

`security_matrix.example.yml` shows the expected structure of a security matrix.
It is intentionally minimal and does not publish private project coverage
details.

## Private Matrix

`security_matrix.yml` is intentionally git-ignored and should be used only for
private/internal coverage tracking if needed.

Projects may maintain a private `security/security_matrix.yml` for diagnostics
or release processes. Do not publish private matrices accidentally.

## Strict Enforcement

By default, a missing private matrix is a warning. Set:

```bash
AKSARA_REQUIRE_SECURITY_MATRIX=true
```

to make a missing or invalid private matrix a blocking diagnostic condition.

## Public Security Docs

Public user-facing security docs live under:

```text
docs/docs/security/
```

## External Review Prep

The following internal/review artifacts support external security review and
release decision-making:

- `external-review-scope.md`
- `hardening-report-template.md`

These files are not production-readiness claims.
