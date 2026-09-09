"""Provision framework runtime tables outside application startup."""

from aksara.migrations import Migration as BaseMigration
from aksara.migrations import operations as op


class Migration(BaseMigration):
    internal = True
    app_label = "aksara.core"
    dependencies = []  # noqa: RUF012
    operations = [  # noqa: RUF012
        op.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS aksara_sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMPTZ NOT NULL
            )
            """,
        ),
        op.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS aksara_content_types (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                app_label VARCHAR(255) NOT NULL,
                model VARCHAR(100) NOT NULL,
                module VARCHAR(255) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_aksara_content_types UNIQUE (app_label, model)
            )
            """,
        ),
        op.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS aksara_tasks (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                task_name VARCHAR(255) NOT NULL,
                queue VARCHAR(100) NOT NULL DEFAULT 'default',
                tenant_id VARCHAR(255),
                payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                available_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                locked_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ,
                last_error TEXT,
                result JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
        ),
        op.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS idx_aksara_tasks_pending
            ON aksara_tasks (queue, status, available_at, created_at)
            """,
        ),
        op.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS aksara_cron_state (
                task_name VARCHAR(255) PRIMARY KEY,
                last_enqueued_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
        ),
    ]
