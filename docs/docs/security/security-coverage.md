# Security Coverage

Aksara uses structured security coverage tracking to map generated surfaces,
actor types, risk categories, and adversarial scenarios.

## Public Example Matrix

The public repository includes:

```text
security/security_matrix.example.yml
```

This file demonstrates the structure of the matrix without publishing internal
project coverage details.

## Private/Internal Matrix

Projects may maintain a private:

```text
security/security_matrix.yml
```

This file can be used by diagnostics and release processes. By default, a
missing private matrix is a warning. To make it required:

```bash
AKSARA_REQUIRE_SECURITY_MATRIX=true
```

With this flag, missing or invalid private matrix data becomes a blocking
diagnostic condition.

## Covered Test Areas

- Authentication and principal resolution
- Field-level permissions
- Tenant isolation
- MCP credential validation
- Runtime payload enforcement
- Filters and ordering
- Pagination
- Serializer payloads
- Migration defaults and identifiers
- Malformed and oversized payloads
- Release-gate package build verification
- Dependency audit, static analysis, secret scanning, and SBOM generation

## Limitations

- OpenAPI fuzzing requires optional tooling.
- Private matrix enforcement is optional unless
  `AKSARA_REQUIRE_SECURITY_MATRIX=true`.
- Release gates prepare release trust but do not replace external review.
- External security review is planned before a production-mode claim.
