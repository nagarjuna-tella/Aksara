"""
Tenant-aware PostgreSQL connection helpers.

Keeps request-scoped tenant context logic separate from model imports so the
database layer can apply RLS settings without importing the ORM base module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg


TENANT_SETTING_NAME = "aksara.current_tenant_id"
TENANT_POLICY_PREFIX = "aksara_tenant_isolation"


def _quote_identifier(name: str) -> str:
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def get_tenant_policy_name(table_name: str) -> str:
    """Build a stable policy name for a tenant-scoped table."""
    return f"{TENANT_POLICY_PREFIX}_{table_name}"


def build_enable_rls_sql(table_name: str, tenant_column: str = "tenant_id") -> str:
    """Build SQL that enables row-level security for a tenant-scoped table."""
    policy_name = _quote_identifier(get_tenant_policy_name(table_name))
    table = _quote_identifier(table_name)
    tenant_col = _quote_identifier(tenant_column)
    tenant_expr = (
        f"{tenant_col} = NULLIF(current_setting('{TENANT_SETTING_NAME}', true), '')::uuid"
    )
    return (
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY; "
        f"DROP POLICY IF EXISTS {policy_name} ON {table}; "
        f"CREATE POLICY {policy_name} ON {table} USING ({tenant_expr}) WITH CHECK ({tenant_expr})"
    )


def build_disable_rls_sql(table_name: str) -> str:
    """Build SQL that removes tenant RLS protections for a table."""
    policy_name = _quote_identifier(get_tenant_policy_name(table_name))
    table = _quote_identifier(table_name)
    return (
        f"DROP POLICY IF EXISTS {policy_name} ON {table}; "
        f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"
    )


async def apply_tenant_context(connection: "asyncpg.Connection") -> bool:
    """Apply the current tenant to a PostgreSQL connection."""
    from aksara.middleware.context import tenant_id_var

    tenant_id = tenant_id_var.get()
    if not tenant_id:
        return False

    await connection.execute(
        f"SELECT set_config('{TENANT_SETTING_NAME}', $1, false)",
        str(tenant_id),
    )
    return True


async def reset_tenant_context(connection: "asyncpg.Connection") -> None:
    """Clear any previously applied tenant setting from a connection."""
    await connection.execute(
        f"SELECT set_config('{TENANT_SETTING_NAME}', '', false)"
    )


__all__ = [
    "TENANT_SETTING_NAME",
    "apply_tenant_context",
    "build_disable_rls_sql",
    "build_enable_rls_sql",
    "get_tenant_policy_name",
    "reset_tenant_context",
]