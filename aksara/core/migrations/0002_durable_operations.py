"""Install the internal Durable Authorized Operations substrate."""

from aksara.migrations import Migration as BaseMigration
from aksara.migrations import operations as op


FORWARD_SQL = """
CREATE TABLE aksara_operations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_namespace VARCHAR(255) NOT NULL,
    tenant_id TEXT,
    tenant_scope TEXT NOT NULL,
    action_name VARCHAR(255) NOT NULL,
    action_version VARCHAR(64) NOT NULL,
    executor_type VARCHAR(64) NOT NULL,
    effect_class VARCHAR(40) NOT NULL CHECK (
        effect_class IN (
            'postgres_atomic', 'external_idempotent', 'external_at_least_once',
            'external_nonretryable', 'read_only'
        )
    ),
    command_id UUID NOT NULL UNIQUE,
    resolver_key VARCHAR(255) NOT NULL,
    resolver_version VARCHAR(64) NOT NULL,
    principal_reference JSONB NOT NULL,
    provenance_version INTEGER NOT NULL DEFAULT 1 CHECK (provenance_version > 0),
    principal_reference_hash CHAR(64) NOT NULL,
    canonical_input_hash CHAR(64) NOT NULL,
    idempotency_identity_hash CHAR(64),
    idempotency_scope_hash CHAR(64),
    state VARCHAR(32) NOT NULL CHECK (
        state IN (
            'waiting_for_approval', 'ready', 'running', 'succeeded', 'failed',
            'cancelled', 'expired'
        )
    ),
    state_version BIGINT NOT NULL DEFAULT 1 CHECK (state_version > 0),
    current_attempt_id UUID,
    fence BIGINT NOT NULL DEFAULT 0 CHECK (fence >= 0),
    worker_id VARCHAR(255),
    lease_expires_at TIMESTAMPTZ,
    available_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    deadline_at TIMESTAMPTZ,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    approval_required BOOLEAN NOT NULL DEFAULT FALSE,
    approval_consumed_at TIMESTAMPTZ,
    cancellation_requested_at TIMESTAMPTZ,
    cancellation_requester JSONB,
    cancellation_reason VARCHAR(500),
    result JSONB,
    error JSONB,
    correlation JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    completed_at TIMESTAMPTZ,
    retain_until TIMESTAMPTZ NOT NULL,
    CHECK (deadline_at IS NULL OR deadline_at > created_at),
    CHECK (pg_column_size(principal_reference) <= 32768),
    CHECK (pg_column_size(correlation) <= 32768),
    CHECK (result IS NULL OR pg_column_size(result) <= 131072),
    CHECK (error IS NULL OR pg_column_size(error) <= 65536),
    CHECK (
        (state = 'running' AND current_attempt_id IS NOT NULL AND worker_id IS NOT NULL
            AND lease_expires_at IS NOT NULL)
        OR
        (state <> 'running')
    )
);

CREATE UNIQUE INDEX uq_aksara_operations_idempotency_identity
ON aksara_operations (idempotency_identity_hash)
WHERE idempotency_identity_hash IS NOT NULL;

CREATE INDEX idx_aksara_operations_claim
ON aksara_operations (tenant_scope, state, available_at, created_at)
WHERE state IN ('ready', 'running');

CREATE INDEX idx_aksara_operations_retention
ON aksara_operations (state, retain_until)
WHERE state IN ('succeeded', 'failed', 'cancelled', 'expired');

CREATE TABLE aksara_operation_commands (
    id UUID PRIMARY KEY,
    operation_id UUID NOT NULL UNIQUE REFERENCES aksara_operations(id) ON DELETE CASCADE,
    tenant_scope TEXT NOT NULL,
    serialization_version INTEGER NOT NULL DEFAULT 1 CHECK (serialization_version > 0),
    payload JSONB NOT NULL,
    canonical_input_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (pg_column_size(payload) <= 262144)
);

CREATE TABLE aksara_operation_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_id UUID NOT NULL REFERENCES aksara_operations(id) ON DELETE CASCADE,
    tenant_scope TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal > 0),
    fence BIGINT NOT NULL CHECK (fence > 0),
    worker_id VARCHAR(255) NOT NULL,
    state VARCHAR(20) NOT NULL CHECK (
        state IN ('running', 'succeeded', 'failed', 'abandoned', 'cancelled')
    ),
    lease_expires_at TIMESTAMPTZ NOT NULL,
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    completed_at TIMESTAMPTZ,
    retryable BOOLEAN,
    error_code VARCHAR(100),
    error JSONB,
    usage_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (error IS NULL OR pg_column_size(error) <= 65536),
    CHECK (pg_column_size(usage_summary) <= 32768),
    UNIQUE (operation_id, ordinal),
    UNIQUE (operation_id, fence)
);

ALTER TABLE aksara_operations
ADD CONSTRAINT fk_aksara_operations_current_attempt
FOREIGN KEY (current_attempt_id) REFERENCES aksara_operation_attempts(id)
DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX idx_aksara_operation_attempts_operation
ON aksara_operation_attempts (operation_id, ordinal DESC);

CREATE TABLE aksara_operation_idempotency (
    identity_hash CHAR(64) PRIMARY KEY,
    scope_hash CHAR(64) NOT NULL,
    tenant_scope TEXT NOT NULL,
    operation_id UUID NOT NULL,
    action_name VARCHAR(255) NOT NULL,
    action_version VARCHAR(64) NOT NULL,
    canonical_input_hash CHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_aksara_operation_idempotency_expiry
ON aksara_operation_idempotency (expires_at);

CREATE INDEX idx_aksara_operation_idempotency_scope
ON aksara_operation_idempotency (scope_hash);

CREATE TABLE aksara_operation_approval_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_id UUID NOT NULL REFERENCES aksara_operations(id) ON DELETE CASCADE,
    tenant_scope TEXT NOT NULL,
    state VARCHAR(20) NOT NULL CHECK (
        state IN ('pending', 'approved', 'rejected', 'expired', 'superseded')
    ),
    action_name VARCHAR(255) NOT NULL,
    action_version VARCHAR(64) NOT NULL,
    canonical_input_hash CHAR(64) NOT NULL,
    requester_reference_hash CHAR(64) NOT NULL,
    approver_reference JSONB,
    approver_reference_hash CHAR(64),
    reason VARCHAR(1000),
    expires_at TIMESTAMPTZ NOT NULL,
    decided_at TIMESTAMPTZ,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (approver_reference IS NULL OR pg_column_size(approver_reference) <= 32768)
);

CREATE UNIQUE INDEX uq_aksara_operation_approval_active
ON aksara_operation_approval_decisions (operation_id)
WHERE state IN ('pending', 'approved');

CREATE TABLE aksara_operation_transitions (
    id BIGSERIAL PRIMARY KEY,
    operation_id UUID NOT NULL REFERENCES aksara_operations(id) ON DELETE CASCADE,
    tenant_scope TEXT NOT NULL,
    state_version BIGINT NOT NULL CHECK (state_version > 0),
    from_state VARCHAR(32),
    event VARCHAR(64) NOT NULL,
    to_state VARCHAR(32) NOT NULL,
    reason_code VARCHAR(100),
    actor_reference_hash CHAR(64),
    attempt_id UUID REFERENCES aksara_operation_attempts(id) ON DELETE SET NULL,
    correlation JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (pg_column_size(correlation) <= 32768),
    CHECK (pg_column_size(metadata) <= 32768),
    UNIQUE (operation_id, state_version)
);

CREATE INDEX idx_aksara_operation_transitions_history
ON aksara_operation_transitions (operation_id, id DESC);

CREATE TABLE aksara_operation_outbox (
    id BIGSERIAL PRIMARY KEY,
    operation_id UUID NOT NULL REFERENCES aksara_operations(id) ON DELETE CASCADE,
    tenant_scope TEXT NOT NULL,
    transition_id BIGINT NOT NULL UNIQUE REFERENCES aksara_operation_transitions(id) ON DELETE CASCADE,
    topic VARCHAR(255) NOT NULL DEFAULT 'aksara.operation.transition',
    payload JSONB NOT NULL,
    export_attempts INTEGER NOT NULL DEFAULT 0 CHECK (export_attempts >= 0),
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    exported_at TIMESTAMPTZ,
    claimed_by VARCHAR(255),
    claim_expires_at TIMESTAMPTZ,
    last_error VARCHAR(2000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (pg_column_size(payload) <= 65536)
);

CREATE INDEX idx_aksara_operation_outbox_pending
ON aksara_operation_outbox (tenant_scope, next_attempt_at, id)
WHERE exported_at IS NULL;

CREATE TABLE aksara_operation_effects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_id UUID NOT NULL REFERENCES aksara_operations(id) ON DELETE CASCADE,
    tenant_scope TEXT NOT NULL,
    effect_name VARCHAR(255) NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal > 0),
    effect_class VARCHAR(40) NOT NULL CHECK (
        effect_class IN ('external_idempotent', 'external_at_least_once', 'external_nonretryable')
    ),
    state VARCHAR(32) NOT NULL CHECK (
        state IN ('intent_recorded', 'confirmed', 'failed', 'outcome_unknown')
    ),
    request_hash CHAR(64) NOT NULL,
    downstream_idempotency_key VARCHAR(255),
    last_attempt_id UUID REFERENCES aksara_operation_attempts(id) ON DELETE SET NULL,
    last_fence BIGINT NOT NULL CHECK (last_fence > 0),
    execution_count INTEGER NOT NULL DEFAULT 0 CHECK (execution_count >= 0),
    provider_reference VARCHAR(1000),
    response JSONB,
    error JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    confirmed_at TIMESTAMPTZ,
    CHECK (response IS NULL OR pg_column_size(response) <= 65536),
    CHECK (error IS NULL OR pg_column_size(error) <= 65536),
    UNIQUE (operation_id, effect_name, ordinal)
);

ALTER TABLE aksara_tasks
ADD COLUMN operation_id UUID REFERENCES aksara_operations(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX uq_aksara_tasks_operation_id
ON aksara_tasks (operation_id)
WHERE operation_id IS NOT NULL;

ALTER TABLE aksara_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE aksara_operation_commands ENABLE ROW LEVEL SECURITY;
ALTER TABLE aksara_operation_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE aksara_operation_idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE aksara_operation_approval_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE aksara_operation_transitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE aksara_operation_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE aksara_operation_effects ENABLE ROW LEVEL SECURITY;

ALTER TABLE aksara_operations FORCE ROW LEVEL SECURITY;
ALTER TABLE aksara_operation_commands FORCE ROW LEVEL SECURITY;
ALTER TABLE aksara_operation_attempts FORCE ROW LEVEL SECURITY;
ALTER TABLE aksara_operation_idempotency FORCE ROW LEVEL SECURITY;
ALTER TABLE aksara_operation_approval_decisions FORCE ROW LEVEL SECURITY;
ALTER TABLE aksara_operation_transitions FORCE ROW LEVEL SECURITY;
ALTER TABLE aksara_operation_outbox FORCE ROW LEVEL SECURITY;
ALTER TABLE aksara_operation_effects FORCE ROW LEVEL SECURITY;

CREATE POLICY aksara_operations_tenant_policy ON aksara_operations
USING (tenant_scope = current_setting('aksara.current_tenant_id', true))
WITH CHECK (tenant_scope = current_setting('aksara.current_tenant_id', true));
CREATE POLICY aksara_operation_commands_tenant_policy ON aksara_operation_commands
USING (tenant_scope = current_setting('aksara.current_tenant_id', true))
WITH CHECK (tenant_scope = current_setting('aksara.current_tenant_id', true));
CREATE POLICY aksara_operation_attempts_tenant_policy ON aksara_operation_attempts
USING (tenant_scope = current_setting('aksara.current_tenant_id', true))
WITH CHECK (tenant_scope = current_setting('aksara.current_tenant_id', true));
CREATE POLICY aksara_operation_idempotency_tenant_policy ON aksara_operation_idempotency
USING (tenant_scope = current_setting('aksara.current_tenant_id', true))
WITH CHECK (tenant_scope = current_setting('aksara.current_tenant_id', true));
CREATE POLICY aksara_operation_approvals_tenant_policy ON aksara_operation_approval_decisions
USING (tenant_scope = current_setting('aksara.current_tenant_id', true))
WITH CHECK (tenant_scope = current_setting('aksara.current_tenant_id', true));
CREATE POLICY aksara_operation_transitions_tenant_policy ON aksara_operation_transitions
USING (tenant_scope = current_setting('aksara.current_tenant_id', true))
WITH CHECK (tenant_scope = current_setting('aksara.current_tenant_id', true));
CREATE POLICY aksara_operation_outbox_tenant_policy ON aksara_operation_outbox
USING (tenant_scope = current_setting('aksara.current_tenant_id', true))
WITH CHECK (tenant_scope = current_setting('aksara.current_tenant_id', true));
CREATE POLICY aksara_operation_effects_tenant_policy ON aksara_operation_effects
USING (tenant_scope = current_setting('aksara.current_tenant_id', true))
WITH CHECK (tenant_scope = current_setting('aksara.current_tenant_id', true));
"""


REVERSE_SQL = """
DROP INDEX IF EXISTS uq_aksara_tasks_operation_id;
ALTER TABLE aksara_tasks DROP COLUMN IF EXISTS operation_id;
DROP TABLE IF EXISTS aksara_operation_effects;
DROP TABLE IF EXISTS aksara_operation_outbox;
DROP TABLE IF EXISTS aksara_operation_transitions;
DROP TABLE IF EXISTS aksara_operation_approval_decisions;
DROP TABLE IF EXISTS aksara_operation_idempotency;
ALTER TABLE aksara_operations DROP CONSTRAINT IF EXISTS fk_aksara_operations_current_attempt;
DROP TABLE IF EXISTS aksara_operation_attempts;
DROP TABLE IF EXISTS aksara_operation_commands;
DROP TABLE IF EXISTS aksara_operations;
"""


class Migration(BaseMigration):
    internal = True
    app_label = "aksara.core"
    dependencies = [  # noqa: RUF012
        ("core", "aksara_core_migrations_0001_runtime_tables"),
    ]
    operations = [  # noqa: RUF012
        op.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
