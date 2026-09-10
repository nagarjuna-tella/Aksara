"""Focused machine-readable diagnostics for durable operation deployments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from aksara.durable.service import DurableOperationService, _tenant_context
from aksara.durable.types import tenant_scope

DurableDiagnosticStatus = Literal["pass", "warn", "block"]


@dataclass(frozen=True)
class DurableDiagnosticResult:
    id: str
    status: DurableDiagnosticStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DurableDiagnosticReport:
    results: tuple[DurableDiagnosticResult, ...]

    @property
    def release_ready(self) -> bool:
        return all(result.status == "pass" for result in self.results)

    @property
    def has_blocks(self) -> bool:
        return any(result.status == "block" for result in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": "durable-operations",
            "status": "block" if self.has_blocks else (
                "warn" if not self.release_ready else "pass"
            ),
            "release_ready": self.release_ready,
            "results": [
                {
                    "id": result.id,
                    "status": result.status,
                    "message": result.message,
                    "details": result.details,
                }
                for result in self.results
            ],
        }


_REQUIRED_TABLES = (
    "aksara_operations",
    "aksara_operation_commands",
    "aksara_operation_attempts",
    "aksara_operation_idempotency",
    "aksara_operation_approval_decisions",
    "aksara_operation_transitions",
    "aksara_operation_outbox",
    "aksara_operation_effects",
)


async def check_durable_operations(
    service: DurableOperationService,
    *,
    tenant_id: str | None,
) -> DurableDiagnosticReport:
    """Inspect schema, deployment bindings, ownership and bounded storage."""

    scope = tenant_scope(tenant_id)
    results: list[DurableDiagnosticResult] = []
    with _tenant_context(scope):
        async with service.db.acquire() as connection:
            present = {
                row["table_name"]
                for row in await connection.fetch(
                    """
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_name = ANY($1::text[])
                    """,
                    list(_REQUIRED_TABLES),
                )
            }
            missing_tables = sorted(set(_REQUIRED_TABLES) - present)
            task_link = await connection.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'aksara_tasks' AND column_name = 'operation_id'
                )
                """
            )
            if missing_tables or not task_link:
                results.append(
                    DurableDiagnosticResult(
                        id="durable.schema",
                        status="block",
                        message="Durable operation internal migrations are not current.",
                        details={
                            "missing_tables": missing_tables,
                            "task_link_column": bool(task_link),
                        },
                    )
                )
                return DurableDiagnosticReport(tuple(results))
            results.append(
                DurableDiagnosticResult(
                    id="durable.schema",
                    status="pass",
                    message="Durable operation internal schema is current.",
                )
            )

            action_rows = await connection.fetch(
                """
                SELECT DISTINCT action_name, action_version
                FROM aksara_operations
                WHERE tenant_scope = $1
                  AND application_namespace = $2
                  AND state IN ('waiting_for_approval', 'ready', 'running')
                """,
                scope,
                service.application_namespace,
            )
            required_actions = {
                (row["action_name"], row["action_version"]) for row in action_rows
            }
            missing_actions = sorted(required_actions - service.actions.versions())
            results.append(
                DurableDiagnosticResult(
                    id="durable.action_versions",
                    status="block" if missing_actions else "pass",
                    message=(
                        "Nonterminal operations reference unavailable action versions."
                        if missing_actions
                        else "All nonterminal action versions are registered."
                    ),
                    details={"missing": [list(item) for item in missing_actions]},
                )
            )

            resolver_rows = await connection.fetch(
                """
                SELECT DISTINCT resolver_key, resolver_version
                FROM aksara_operations
                WHERE tenant_scope = $1
                  AND application_namespace = $2
                  AND state IN ('waiting_for_approval', 'ready', 'running')
                """,
                scope,
                service.application_namespace,
            )
            required_resolvers = {
                (row["resolver_key"], row["resolver_version"])
                for row in resolver_rows
            }
            missing_resolvers = sorted(
                required_resolvers - service.resolvers.versions()
            )
            results.append(
                DurableDiagnosticResult(
                    id="durable.principal_resolvers",
                    status="block" if missing_resolvers else "pass",
                    message=(
                        "Nonterminal operations reference unavailable principal resolvers."
                        if missing_resolvers
                        else "All nonterminal principal resolvers are registered."
                    ),
                    details={"missing": [list(item) for item in missing_resolvers]},
                )
            )

            backlog = await connection.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE state = 'ready') AS ready,
                    COUNT(*) FILTER (WHERE state = 'waiting_for_approval') AS waiting,
                    COUNT(*) FILTER (
                        WHERE state = 'running' AND lease_expires_at <= clock_timestamp()
                    ) AS expired_leases,
                    COUNT(*) FILTER (WHERE state = 'running') AS running
                FROM aksara_operations
                WHERE tenant_scope = $1 AND application_namespace = $2
                """,
                scope,
                service.application_namespace,
            )
            expired_leases = int(backlog["expired_leases"])
            results.append(
                DurableDiagnosticResult(
                    id="durable.ownership",
                    status="warn" if expired_leases else "pass",
                    message=(
                        "Expired operation leases are waiting for reclaim."
                        if expired_leases
                        else "No expired operation leases are waiting for reclaim."
                    ),
                    details={key: int(backlog[key]) for key in backlog},
                )
            )

            pending_outbox = int(
                await connection.fetchval(
                    """
                    SELECT COUNT(*) FROM aksara_operation_outbox o
                    JOIN aksara_operations p ON p.id = o.operation_id
                    WHERE o.tenant_scope = $1
                      AND p.application_namespace = $2
                      AND o.exported_at IS NULL
                    """,
                    scope,
                    service.application_namespace,
                )
            )
            results.append(
                DurableDiagnosticResult(
                    id="durable.outbox",
                    status="warn" if pending_outbox > 10000 else "pass",
                    message=(
                        "Durable outbox backlog exceeds the operational warning threshold."
                        if pending_outbox > 10000
                        else "Durable outbox backlog is within the operational threshold."
                    ),
                    details={"pending": pending_outbox, "warning_threshold": 10000},
                )
            )

    retention_safe = (
        service.retention_seconds > 0
        and service.idempotency_seconds > 0
        and service.result_retention_seconds > 0
        and service.error_retention_seconds > 0
    )
    results.append(
        DurableDiagnosticResult(
            id="durable.retention",
            status="pass" if retention_safe else "block",
            message=(
                "Durable operation retention windows are configured."
                if retention_safe
                else "Durable operation retention windows must be positive."
            ),
            details={
                "operation_seconds": service.retention_seconds,
                "idempotency_seconds": service.idempotency_seconds,
                "result_seconds": service.result_retention_seconds,
                "error_seconds": service.error_retention_seconds,
            },
        )
    )
    return DurableDiagnosticReport(tuple(results))


__all__ = [
    "DurableDiagnosticReport",
    "DurableDiagnosticResult",
    "DurableDiagnosticStatus",
    "check_durable_operations",
]
