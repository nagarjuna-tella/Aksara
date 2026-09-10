# v0.6.1 installed-package baseline

Date: 2026-09-10 (America/Detroit)

This is a reproduction of the first-user path against the public
`aksara-framework==0.6.0` wheel. It records the state before v0.6.1 changes.
Credentials and local database URLs are intentionally omitted.

## Environment

- Host: macOS 26.6.2, arm64
- Isolated interpreter: CPython 3.11.15
- Public package: `aksara-framework==0.6.0`
- Installed MCP SDK: `mcp==2.0.1`
- PostgreSQL server: 18.4, local test service
- Temporary virtual environment: outside the repository
- Temporary generated project: outside the repository

## Commands and results

```bash
python3.11 -m venv /tmp/aksara-v061-published
/tmp/aksara-v061-published/bin/python -m pip install \
  "aksara-framework==0.6.0"
/tmp/aksara-v061-published/bin/python -c \
  "import aksara; print(aksara.__version__)"
/tmp/aksara-v061-published/bin/aksara --help
/tmp/aksara-v061-published/bin/aksara --version
/tmp/aksara-v061-published/bin/aksara startproject published_app
```

- Installation succeeded from PyPI without a source checkout.
- `aksara.__version__`, package metadata, and `aksara --version` all reported
  `0.6.0`.
- CLI help loaded and exposed the documented command groups.
- `startproject` completed and generated an importable project.

The generated model and ViewSet stubs were adapted into a small `Note` CRUD
resource, then the documented database path was exercised:

```bash
aksara makemigrations --app app.models
aksara migrate
aksara doctor launch-check --format json
aksara run main:app --host 127.0.0.1 --port 8765
```

- Migration generation and application succeeded when `DATABASE_URL` was set.
- The application started, `/health` returned 200, and OpenAPI contained the
  generated Note routes.
- `GET /api/notes/` returned an empty paginated result.
- `POST /api/notes/` returned 403 without an authenticated server-resolved
  principal. That denial is expected security behavior, but the generated
  project did not provide or point to the missing authentication step.
- Doctor reached the database and MCP catalog. Its launch result was partial
  because the initial fallback migration was followed by a file migration,
  Studio was disabled, and no optional AI provider was configured.
- SIGINT produced a clean application shutdown and database disconnect.

The official SDK probe used `mcp.client.streamable_http.streamable_http_client`
against `http://127.0.0.1:8765/mcp/`.

- MCP initialization negotiated over Streamable HTTP.
- `tools/list` reached the Aksara server but failed with
  `AuthenticationMiddleware must be installed to access request.user`.
- No tool call was attempted after discovery failed.

## Reproduced truth gaps

### Generated settings do not configure the framework

The scaffold creates an `AKSARA` dictionary and a subclass of the dataclass
`aksara.conf.Settings`. Class attributes on that subclass do not replace the
dataclass constructor defaults. In the generated project, the dictionary says
AI Mode is enabled while both the project settings instance and Aksara's global
settings report `ai_enabled=False`.

The scaffold also creates a separate settings object without calling
`aksara.configure()`. Feature mounting reads Aksara's global settings, so this
teaches two configuration objects with different values.

### Database environment precedence is inconsistent

`aksara.conf.Settings` prefers `AKSARA_DATABASE_URL` and accepts
`DATABASE_URL` as a compatibility alias. Migration CLI options bind only
`DATABASE_URL`. With a generated `.env` present, setting only
`AKSARA_DATABASE_URL` did not override the scaffold URL; the command attempted
the `.env` database instead. Setting both variables made the command succeed.

### The generated MCP path is incomplete

The generated README and welcome material point to `/ai/tools`, but do not
identify `/mcp/` as the client protocol endpoint or explain that
`/ai/tools/mcp` is an HTTP inspection catalog. The scaffold has no example of
server-side credential verification and `Principal` resolution, so the
documented stable MCP journey cannot be completed from the generated project.

### Public AI examples name APIs the wheel does not export

```python
import aksara.ai as ai

assert not hasattr(ai, "AgentRuntime")
assert not hasattr(ai, "Planner")
assert hasattr(ai, "AiPlan")
```

The Agent Runtime and Planner pages present `AgentRuntime(...)` and
`Planner(...)` examples as executable. The wheel exports neither class. The
real surfaces are narrower: prompt-pack execution with in-memory budgets, plan
data models, and deterministic plan handlers. These remain experimental.

### Task identity wording exceeds persisted behavior

The task record persists `tenant_id`, and workers restore that tenant context.
It does not persist or restore the complete `Principal`. The v0.6 stability
contract described both Principal and tenant propagation for task enqueue and
worker paths.

### Public metadata is mostly current; its README inherits documentation drift

PyPI reports version 0.6.0, Python 3.11+, the expected project links, and the
declared MCP 2.0 dependency range. The PyPI long description is sourced from
the repository README, so broad stable/experimental wording and incomplete
first-user MCP guidance are visible on the public package page.

## Classification

| Surface | Baseline classification | Reason |
| --- | --- | --- |
| Core install/import/CLI | EXECUTABLE | Clean PyPI wheel succeeds. |
| Basic scaffold creation | EXECUTABLE | Files are generated and import after DB configuration. |
| Generated settings model | BROKEN | Local dataclass subclass and global settings diverge. |
| REST read path | EXECUTABLE | Generated route returns a paginated response. |
| REST write path in scaffold | UNKNOWN | Correctly requires identity, but scaffold omits the identity journey. |
| `/mcp/` transport | EXECUTABLE | Official client initialization reaches the server. |
| MCP discovery in scaffold | BROKEN | Missing authentication middleware triggers an assertion. |
| `/ai/tools/mcp` | EXECUTABLE | It returns generated tool metadata as HTTP JSON. |
| Documented `AgentRuntime` | STALE | No public class exists. |
| Documented `Planner` | STALE | No public class exists. |
| `AiPlan` and prompt-pack runtime | EXPERIMENTAL | Real APIs exist; durability and provider quality are not stable. |
| Background task tenant restoration | EXECUTABLE | `tenant_id` is persisted and restored. |
| Background task Principal restoration | BROKEN CLAIM | No complete Principal is stored. |
