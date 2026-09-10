from __future__ import annotations

import asyncio

import pytest

from aksara.ai.limits import (
    AgentRuntimeBudget,
    AgentRuntimeLimits,
    RuntimeLimitExceeded,
)
from aksara.mcp import (
    AgentInvocationContext,
    ApprovalError,
    ApprovalManager,
    MemoryMCPAuditSink,
    get_agent_invocation_context,
)
from aksara.mcp.audit import safe_argument_summary
from aksara.mcp.context import (
    push_agent_invocation_context,
    reset_agent_invocation_context,
)
from aksara.security.principal import Principal


def _principal(tenant: str = "tenant-a", agent: str = "agent-a") -> Principal:
    return Principal.for_mcp_agent(
        token_id="token-a",
        human_owner_id="owner-a",
        agent_id=agent,
        tenant_id=tenant,
        roles=("agent",),
        scopes=("mcp:write:ticket",),
    )


def test_approval_is_bound_to_arguments_tenant_and_principal() -> None:
    manager = ApprovalManager("a-secret-long-enough-for-tests")
    principal = _principal()
    arguments = {"pk": "one", "status": "closed"}
    token = manager.issue(
        principal=principal,
        tool_name="ticket_update",
        arguments=arguments,
        approved_by="reviewer-1",
    )

    context = manager.verify(
        token,
        principal=principal,
        tool_name="ticket_update",
        arguments={**arguments, "_approval_token": token},
    )
    assert context.approved_by == "reviewer-1"

    cases = [
        (_principal(), "ticket_update", {"pk": "one", "status": "deleted"}, "approval_arguments_mismatch"),
        (_principal("tenant-b"), "ticket_update", arguments, "approval_tenant_mismatch"),
        (_principal(agent="agent-b"), "ticket_update", arguments, "approval_principal_mismatch"),
        (_principal(), "ticket_delete", arguments, "approval_mismatch"),
    ]
    for actor, tool, changed, code in cases:
        with pytest.raises(ApprovalError) as caught:
            manager.verify(token, principal=actor, tool_name=tool, arguments=changed)
        assert caught.value.code == code


def test_rejected_expired_and_invalid_approvals_never_verify() -> None:
    manager = ApprovalManager("approval-secret")
    principal = _principal()
    arguments = {"pk": "one"}
    rejected = manager.issue(
        principal=principal,
        tool_name="ticket_delete",
        arguments=arguments,
        approved_by="reviewer",
        approved=False,
    )
    expired = manager.issue(
        principal=principal,
        tool_name="ticket_delete",
        arguments=arguments,
        approved_by="reviewer",
        ttl_seconds=-1,
    )
    for token, code in ((rejected, "approval_rejected"), (expired, "approval_expired"), ("bad", "approval_invalid")):
        with pytest.raises(ApprovalError) as caught:
            manager.verify(token, principal=principal, tool_name="ticket_delete", arguments=arguments)
        assert caught.value.code == code


def test_argument_summary_has_hashes_and_no_values() -> None:
    summary = safe_argument_summary(
        {"subject": "private customer text", "password": "secret", "_approval_token": "grant"}
    )
    rendered = repr(summary)
    assert "private customer text" not in rendered
    assert "secret" not in rendered
    assert "grant" not in rendered
    assert sorted(summary["fields"]) == ["password", "subject"]


@pytest.mark.asyncio
async def test_invocation_context_is_isolated_between_concurrent_tasks() -> None:
    async def run(name: str) -> tuple[str, str]:
        context = AgentInvocationContext(
            principal=_principal(tenant=name, agent=name),
            request_id=name,
            run_id=name,
            tool_call_id=name,
            tool_name="ticket_list",
            operation="list",
        )
        token = push_agent_invocation_context(context)
        try:
            await asyncio.sleep(0)
            current = get_agent_invocation_context()
            assert current is not None
            return current.principal.tenant_id or "", current.tool_call_id
        finally:
            reset_agent_invocation_context(token)

    assert await asyncio.gather(run("tenant-a"), run("tenant-b")) == [
        ("tenant-a", "tenant-a"),
        ("tenant-b", "tenant-b"),
    ]
    assert get_agent_invocation_context() is None


def test_runtime_budget_enforces_steps_tools_tokens_cost_and_replay() -> None:
    limits = AgentRuntimeLimits(
        max_steps=1,
        max_tool_calls=1,
        token_budget=10,
        cost_budget_usd=0.25,
    )
    budget = AgentRuntimeBudget(limits)
    budget.consume_step()
    budget.consume_tool_call("one")
    budget.consume_usage(tokens=10, cost_usd=0.25)
    for action, code in (
        (budget.consume_step, "max_steps_exceeded"),
        (lambda: budget.consume_tool_call("one"), "repeated_tool_call"),
    ):
        with pytest.raises(RuntimeLimitExceeded) as caught:
            action()
        assert caught.value.code == code
    with pytest.raises(RuntimeLimitExceeded) as caught:
        budget.consume_usage(tokens=1)
    assert caught.value.code == "token_budget_exceeded"
    cost_budget = AgentRuntimeBudget(limits)
    cost_budget.consume_usage(cost_usd=0.25)
    with pytest.raises(RuntimeLimitExceeded) as caught:
        cost_budget.consume_usage(cost_usd=0.01)
    assert caught.value.code == "cost_budget_exceeded"


def test_memory_audit_sink_is_explicitly_process_local() -> None:
    assert MemoryMCPAuditSink().events == []


def test_invocation_context_snapshots_and_deeply_freezes_metadata() -> None:
    metadata = {"audience": "mcp", "nested": {"roles": ["agent"]}}
    principal = Principal.for_mcp_agent(
        token_id="token-a",
        human_owner_id="owner-a",
        agent_id="agent-a",
        tenant_id="tenant-a",
        roles=("agent",),
        scopes=("mcp:write:ticket",),
        metadata=metadata,
    )
    context = AgentInvocationContext(
        principal=principal,
        request_id="request",
        run_id="run",
        tool_call_id="call",
        tool_name="ticket_list",
        operation="list",
        policy_context={"rules": ["tenant"]},
    )
    metadata["audience"] = "changed"
    metadata["nested"]["roles"].append("admin")
    assert context.principal.metadata["audience"] == "mcp"
    assert context.principal.metadata["nested"]["roles"] == ("agent",)
    assert context.policy_context["rules"] == ("tenant",)
    with pytest.raises(TypeError):
        context.policy_context["new"] = "value"
