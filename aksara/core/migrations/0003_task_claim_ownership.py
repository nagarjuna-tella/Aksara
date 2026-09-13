"""Add lease ownership and fencing to ordinary background tasks."""

from aksara.migrations import Migration as BaseMigration
from aksara.migrations import operations as op

FORWARD_SQL = """
ALTER TABLE aksara_tasks
ADD COLUMN IF NOT EXISTS locked_by VARCHAR(255),
ADD COLUMN IF NOT EXISTS claim_token UUID,
ADD COLUMN IF NOT EXISTS lock_expires_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_aksara_tasks_running_lease
ON aksara_tasks (lock_expires_at, id)
WHERE status = 'running';
"""


REVERSE_SQL = """
DROP INDEX IF EXISTS idx_aksara_tasks_running_lease;
ALTER TABLE aksara_tasks DROP COLUMN IF EXISTS lock_expires_at;
ALTER TABLE aksara_tasks DROP COLUMN IF EXISTS claim_token;
ALTER TABLE aksara_tasks DROP COLUMN IF EXISTS locked_by;
"""


class Migration(BaseMigration):
    internal = True
    app_label = "aksara.core"
    dependencies = [  # noqa: RUF012
        ("core", "aksara_core_migrations_0002_durable_operations"),
    ]
    operations = [  # noqa: RUF012
        op.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
