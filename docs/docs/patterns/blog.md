# Blog example

**Application demonstration.** This example teaches a Post–Comment relationship
and explicit publish/moderation actions. It is not a complete authenticated
publishing backend. For a runnable protected application, start with
[Ticket Desk](../getting-started/first-project.md), then adapt its identity and
permission pattern to your content model.

## What is in the example

The bundled example contains `Post` and `Comment`, model serializers, ViewSets,
Admin registrations, and a health endpoint. The source includes actions such
as publish, unpublish, approve, and reject. Tag suggestions use local keyword
extraction; the name does not imply that an LLM is called.

Read the generated `models.py`, `serializers.py`, and `views.py` together.
Their declarations are the example's source, rather than a separate set of
copied models on this page. A new field requires a migration; a serializer or
view change does not automatically update database schema.

## Generate a local copy

First [install Aksara](../getting-started/installation.md) in an activated virtual
environment. Export `DATABASE_URL` for a dedicated local PostgreSQL database;
this example prefers it over `AKSARA_DATABASE_URL`, so keep those values
consistent. Do not use a production database for example migrations.

```bash
aksara startproject blog_demo --template blog
cd blog_demo
aksara makemigrations --app models --output migrations
aksara migrate --migrations-dir migrations
aksara run main:app --host 127.0.0.1 --port 8000
```

The copied modules live at the project root. This is why the migration command
uses `models`, not `app.models`. The domain template does not create a
`pyproject.toml` or `.env`; the generic editable-install instructions printed by
`startproject` do not apply. Use the already installed framework and the shell's
database configuration.

In another terminal, check the running local server:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/openapi.json
```

Open `/docs` to inspect actual routes. Generated updates use `PATCH`, not the
`PUT` route listed in the older guide. OpenAPI describes registration; it does
not prove that every action is authorized or that all custom response behavior
has been exercised.

## Before building on it

A valid unauthenticated POST to `/api/posts/` returns **403** under the released
v0.7.0 behavior. The example's `X-API-Key` helper does not create the server-owned
Principal needed for a generated write. Do not disable permission checks to
make an old seed command succeed.

Custom actions need their own explicit authorization checks under the current
[HTTP action contract](../api/actions.md). A `dependencies` attribute or
`ai_exposed` metadata is not evidence that an action enforces your publishing
roles. Decide who may create drafts, read unpublished content, publish, and
moderate comments before exposing this example beyond local inspection.

The example's custom list handlers are application code, not the universal
pagination contract. Use the [filtering](../api/filtering.md) and
[pagination](../api/pagination.md) references when building a new ViewSet, and
verify the actual HTTP response shape in your application tests.

For a version you can extend with confidence, map Ticket Desk's Ticket–Note
relationship to Post–Comment, then add publish and moderation as explicit,
authorized actions. Use [media guidance](../advanced/media-and-email.md) for
stored uploads and [Durable Operations](../advanced/durable-operations.md) only
when recovery across failure and time is part of the requirement.
