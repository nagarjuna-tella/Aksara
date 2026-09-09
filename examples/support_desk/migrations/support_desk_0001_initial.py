"""Create the initial support desk schema and enforce tenant RLS."""

from typing import ClassVar

from aksara.db.tenant_context import build_disable_rls_sql, build_enable_rls_sql
from aksara.migrations import Migration
from aksara.migrations import operations as op


def _enable_and_force_rls(table: str) -> op.RunSQL:
    return op.RunSQL(
        sql=f"{build_enable_rls_sql(table)}; ALTER TABLE \"{table}\" FORCE ROW LEVEL SECURITY",
        reverse_sql=f"ALTER TABLE \"{table}\" NO FORCE ROW LEVEL SECURITY; {build_disable_rls_sql(table)}",
    )


class Migration(Migration):
    dependencies: ClassVar[list] = []

    operations: ClassVar[list] = [
        op.CreateTable(
            name="support_organizations",
            fields=[
                ("name", op.StringField(160)),
                ("slug", op.StringField(80, unique=True)),
                ("id", op.UUIDField(primary_key=True)),
                ("created_at", op.DateTimeField(auto_now_add=True)),
                ("updated_at", op.DateTimeField(auto_now=True)),
            ],
        ),
        op.CreateTable(
            name="support_agents",
            fields=[
                ("tenant_id", op.UUIDField()),
                ("name", op.StringField(120)),
                ("email", op.StringField(255)),
                ("role", op.StringField(40, default="agent")),
                ("is_active", op.BooleanField(default=True)),
                ("id", op.UUIDField(primary_key=True)),
                ("created_at", op.DateTimeField(auto_now_add=True)),
                ("updated_at", op.DateTimeField(auto_now=True)),
            ],
            indexes=[
                op.IndexOp(
                    name="idx_support_agents_tenant",
                    table="support_agents",
                    columns=["tenant_id"],
                ),
            ],
        ),
        _enable_and_force_rls("support_agents"),
        op.CreateTable(
            name="support_tickets",
            fields=[
                ("tenant_id", op.UUIDField()),
                ("subject", op.StringField(200)),
                ("description", op.TextField()),
                ("status", op.StringField(32, default="open")),
                (
                    "assigned_to_id",
                    op.ForeignKeyField(
                        "support_agents",
                        on_delete="SET NULL",
                        nullable=True,
                    ),
                ),
                ("id", op.UUIDField(primary_key=True)),
                ("created_at", op.DateTimeField(auto_now_add=True)),
                ("updated_at", op.DateTimeField(auto_now=True)),
            ],
            indexes=[
                op.IndexOp(
                    name="idx_support_tickets_tenant_status",
                    table="support_tickets",
                    columns=["tenant_id", "status"],
                ),
            ],
        ),
        _enable_and_force_rls("support_tickets"),
        op.CreateTable(
            name="support_delivery_attempts",
            fields=[
                ("tenant_id", op.UUIDField()),
                (
                    "ticket_id",
                    op.ForeignKeyField("support_tickets", on_delete="CASCADE"),
                ),
                ("attempts", op.IntegerField(default=0)),
                ("delivered", op.BooleanField(default=False)),
                ("last_error", op.TextField(nullable=True)),
                ("id", op.UUIDField(primary_key=True)),
                ("created_at", op.DateTimeField(auto_now_add=True)),
                ("updated_at", op.DateTimeField(auto_now=True)),
            ],
            indexes=[
                op.IndexOp(
                    name="idx_support_delivery_tenant_ticket",
                    table="support_delivery_attempts",
                    columns=["tenant_id", "ticket_id"],
                ),
            ],
        ),
        _enable_and_force_rls("support_delivery_attempts"),
    ]
