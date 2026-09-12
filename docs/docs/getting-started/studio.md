# Studio quickstart

!!! warning "Experimental in v0.7.0"
    Studio is optional and disabled in new projects. It is not required for the
    stable ORM, REST, security, task, or MCP paths.

First complete the [First project](first-project.md) path. To inspect that local
project in Studio, set a development-only secret in `.env`:

```dotenv
AKSARA_ENABLE_STUDIO=true
AKSARA_STUDIO_SECRET_TOKEN=replace-with-a-random-local-secret
AKSARA_STUDIO_REQUIRE_AUTH=false
```

This disables Studio credential checking. Keep the development server bound to
loopback and use only a local development dataset. The Studio secret does not
replace authentication. For a shared environment, use the authenticated
[configuration](../studio/configuration.md) instead.

Then restart the app:

```bash
aksara doctor launch-check
aksara dev --host 127.0.0.1
```

Open `http://127.0.0.1:8000/studio/ui`. Studio can inspect models, routes,
queries, migrations, and generated tool metadata. Provider-backed console,
investigation, review, and analysis behavior remains experimental and requires
separate [AI Hub configuration](../ai-mode/hub.md).

Before any production exposure, enable authentication, restrict browser origins
and network access, keep a strong Studio secret, set
`AKSARA_STUDIO_EXPOSE_IN_PRODUCTION=true` deliberately, and pass
`aksara doctor production-check --release`. See
[Studio configuration](../studio/configuration.md).
