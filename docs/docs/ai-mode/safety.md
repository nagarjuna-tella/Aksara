# AI safety boundaries

Aksara separates its stable MCP execution boundary from experimental AI
analysis and code tooling.

## Stable MCP execution

For a generated MCP call, the server resolves a `Principal` from trusted
middleware and checks authentication type, expiry, audience, scope,
permissions, `PolicyEngine`, object access, writable fields, tenant context, and
PostgreSQL RLS where configured. Mutation runs through the generated REST/ORM
transaction path. Structured failures, bounded approval grants, audit events,
cancellation, and in-process limits are part of the MCP boundary retained in v0.7.

Schemas, prompt instructions, hidden fields, and client-supplied tenant values
are not authorization controls. See [MCP](mcp.md) and the
[security boundary](../security/ai-mcp-boundaries.md).

## Experimental code tools

Code generation and patch functions are developer tools. There is no public
`PatchEngine`, `Planner`, or `AgentRuntime` class.

Preview declarative patch requests before application:

```python
from aksara.ai.patch import AiPatchOperation, AiPatchRequest, apply_ai_patches

request = AiPatchRequest(
    reason="Document a model",
    operations=[
        AiPatchOperation(
            type="insert_text",
            path="app/models.py",
            start_line=1,
            text="# Application models\n",
        )
    ],
)
preview = apply_ai_patches(request, project_root=".", preview=True)
assert preview.preview_only
```

Patch validation blocks protected paths, escapes outside the project, invalid
Python syntax, and a bounded set of dangerous code patterns. Application still
requires an explicit `confirm_header="true"`, and developers remain responsible
for reviewing diffs, permissions, tests, and source control.

## Lifetime and ownership

Prompt-call budgets, investigation sessions, and synchronous MCP replay state
are process-local. They do not become durable merely because the application
uses v0.7.0.

[Durable Authorized Operations](../advanced/durable-operations.md) are a separate,
explicitly registered execution path introduced in v0.7.0. They provide persisted
operation identity, current reauthorization, idempotent admission, approval and
cancellation state, fencing, and bounded recovery under their documented
production profile. They do not persist an AI planner, chat session, memory, or
arbitrary provider call.

Long-term audit retention, external approval interfaces, deployment operations,
and external-effect reconciliation remain application responsibilities. Read the
[v0.7 contract](../roadmap/v0-7-stability-contract.md) for exact guarantees and
limits rather than extending synchronous MCP or prompt-runtime claims.

Provider configuration does not certify model quality. Treat model output as
untrusted input and validate it before queries, patches, or side effects.
