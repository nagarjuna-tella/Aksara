"""Durable operation deployment diagnostics."""

from __future__ import annotations

from uuid import uuid4

import pytest

from aksara.durable import (
    DurableAction,
    DurableActionRegistry,
    DurableOperationService,
    EffectClass,
    PrincipalReference,
    PrincipalResolution,
    PrincipalResolverRegistry,
    check_durable_operations,
)
from aksara.durable.service import _tenant_context
from aksara.durable.types import tenant_scope
from aksara.security.principal import Principal


async def _handler(_context, command):
    return command


@pytest.mark.asyncio
async def test_diagnostics_report_schema_and_registered_deployment(durable_db):
    tenant = str(uuid4())
    actions = DurableActionRegistry()
    actions.register(
        DurableAction(
            name="diagnostic.action",
            version="1",
            handler=_handler,
            effect_class=EffectClass.READ_ONLY,
        )
    )
    resolvers = PrincipalResolverRegistry()
    resolvers.register(
        "diagnostic",
        "1",
        lambda _reference: PrincipalResolution.resolved(
            Principal.for_user("user-1", tenant_id=tenant)
        ),
    )
    service = DurableOperationService(
        durable_db,
        application_namespace="diagnostic-tests",
        actions=actions,
        resolvers=resolvers,
        retention_seconds=60,
        idempotency_seconds=60,
    )
    await service.admit(
        "diagnostic.action",
        "1",
        {},
        PrincipalReference(
            resolver_key="diagnostic",
            resolver_version="1",
            identity_namespace="tests",
            principal_kind="user",
            subject_id="user-1",
            tenant_id=tenant,
        ),
    )

    report = await check_durable_operations(service, tenant_id=tenant)

    with _tenant_context(tenant_scope(tenant)):
        index_rows = await durable_db.fetch(
            """
            SELECT indexname FROM pg_indexes
            WHERE schemaname = current_schema()
              AND indexname = ANY($1::text[])
            """,
            [
                "idx_aksara_operations_waiting_deadline",
                "idx_aksara_operation_approvals_pending_expiry",
            ],
        )

    assert report.release_ready is True
    assert {row["indexname"] for row in index_rows} == {
        "idx_aksara_operations_waiting_deadline",
        "idx_aksara_operation_approvals_pending_expiry",
    }
    assert report.to_dict()["status"] == "pass"
    assert {result.id for result in report.results} == {
        "durable.schema",
        "durable.action_versions",
        "durable.principal_resolvers",
        "durable.ownership",
        "durable.outbox",
        "durable.retention",
    }


@pytest.mark.asyncio
async def test_diagnostics_block_missing_deployed_action_and_resolver(durable_db):
    tenant = str(uuid4())
    populated_actions = DurableActionRegistry()
    populated_actions.register(
        DurableAction(
            name="diagnostic.missing",
            version="7",
            handler=_handler,
            effect_class=EffectClass.READ_ONLY,
        )
    )
    populated_resolvers = PrincipalResolverRegistry()
    populated_resolvers.register(
        "missing-later",
        "3",
        lambda _reference: Principal.anonymous(),
    )
    populated = DurableOperationService(
        durable_db,
        application_namespace="diagnostic-tests",
        actions=populated_actions,
        resolvers=populated_resolvers,
        retention_seconds=60,
        idempotency_seconds=60,
    )
    await populated.admit(
        "diagnostic.missing",
        "7",
        {},
        PrincipalReference(
            resolver_key="missing-later",
            resolver_version="3",
            identity_namespace="tests",
            principal_kind="user",
            subject_id="user-1",
            tenant_id=tenant,
        ),
    )
    empty = DurableOperationService(
        durable_db,
        application_namespace="diagnostic-tests",
        actions=DurableActionRegistry(),
        resolvers=PrincipalResolverRegistry(),
        retention_seconds=60,
        idempotency_seconds=60,
    )

    report = await check_durable_operations(empty, tenant_id=tenant)

    assert report.has_blocks is True
    by_id = {result.id: result for result in report.results}
    assert by_id["durable.action_versions"].status == "block"
    assert by_id["durable.principal_resolvers"].status == "block"
