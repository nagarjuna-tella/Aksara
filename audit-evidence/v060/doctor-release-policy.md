# Doctor release-policy evidence

Date: 2026-09-09

The deployment and release-candidate policies are intentionally distinct:

- `aksara doctor production-check` exits nonzero for failures and blocks while
  retaining advisory warnings for deployment operators.
- `aksara doctor production-check --release` requires every result to pass,
  requires a security matrix, rejects `planned` or `partial` scenarios, and
  requires covered evidence for every implemented matrix surface.

Focused diagnostics command:

```console
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPYCACHEPREFIX=/tmp/aksara-v060-pycache PYTHONPATH="$PWD" /tmp/aksara-v055-py311/bin/python -m pytest -p pytest_asyncio.plugin -q tests/diagnostics
```

Result: **311 passed, 2 dependency deprecation warnings in 1.08s**.

Safe live CLI command (the release environment supplies its secret):

```console
AKSARA_ENV=production AKSARA_DEBUG=false AKSARA_SECRET_KEY="$AKSARA_RELEASE_SECRET_KEY" AKSARA_SECURITY_MATRIX_PATH=security/security_matrix.release.yml AKSARA_MCP_ENABLED=false AKSARA_STUDIO_EXPOSE_IN_PRODUCTION=false AKSARA_STUDIO_REQUIRE_AUTH=true AKSARA_COOKIE_SECURE=true AKSARA_ADMIN_RATE_LIMIT_ENABLED=true CORS_ALLOW_ALL_ORIGINS=false CORS_ALLOW_CREDENTIALS=false AKSARA_AI_CONSOLE_ENABLED=false AKSARA_AI_ENABLED=false AKSARA_MULTI_TENANT=false aksara doctor production-check --release --format json
```

Result: exit **0**, policy `release-candidate`, status `pass`, 12 passes, no
warnings/failures/blocks, and `release_ready: true`.

The same command with `CORS_ALLOW_ALL_ORIGINS=true` and credentials disabled
produced a Doctor `warn`. Release policy converted that advisory result into
exit **1** with `release_ready: false`. This proves release automation cannot
interpret a warning report as a successful release check.

The edited documentation passed `mkdocs build --strict -f docs/mkdocs.yml` in
3.20s. The committed `security/security_matrix.release.yml` also passed the
strict matrix coverage check.
