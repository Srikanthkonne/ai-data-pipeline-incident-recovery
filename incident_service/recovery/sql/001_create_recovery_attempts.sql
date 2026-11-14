CREATE TABLE IF NOT EXISTS recovery_attempts (
    recovery_attempt_id BIGSERIAL PRIMARY KEY,

    incident_id BIGINT NOT NULL
        REFERENCES incidents(incident_id),

    action VARCHAR(100) NOT NULL,

    status VARCHAR(50) NOT NULL,

    automatic_execution_allowed BOOLEAN
        NOT NULL DEFAULT FALSE,

    rca_assessment JSONB
        NOT NULL DEFAULT '{}'::jsonb,

    recovery_decision JSONB
        NOT NULL DEFAULT '{}'::jsonb,

    execution_result JSONB,

    validation_result JSONB,

    error_message TEXT,

    started_at TIMESTAMPTZ
        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS
    idx_recovery_attempts_incident_id
ON recovery_attempts(incident_id);

CREATE INDEX IF NOT EXISTS
    idx_recovery_attempts_status
ON recovery_attempts(status);
