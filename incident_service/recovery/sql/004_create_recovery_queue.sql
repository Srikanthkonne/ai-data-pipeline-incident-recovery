CREATE TABLE IF NOT EXISTS recovery_queue (
    recovery_queue_id BIGSERIAL PRIMARY KEY,
    incident_id BIGINT NOT NULL
        REFERENCES incidents(incident_id),
    state VARCHAR(30)
        NOT NULL DEFAULT 'READY',
    autonomous_attempt_count INTEGER
        NOT NULL DEFAULT 0,
    max_attempts INTEGER
        NOT NULL DEFAULT 3,
    next_attempt_at TIMESTAMP WITH TIME ZONE
        DEFAULT CURRENT_TIMESTAMP,
    last_recovery_attempt_id BIGINT
        REFERENCES recovery_attempts(recovery_attempt_id),
    last_attempt_status VARCHAR(50),
    last_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE
        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE
        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_recovery_queue_incident
        UNIQUE (incident_id),

    CONSTRAINT chk_recovery_queue_state
        CHECK (
            state IN (
                'READY',
                'PROCESSING',
                'RETRY_WAIT',
                'EXHAUSTED',
                'TERMINAL',
                'COMPLETED'
            )
        ),

    CONSTRAINT chk_recovery_queue_attempt_count
        CHECK (
            autonomous_attempt_count >= 0
        ),

    CONSTRAINT chk_recovery_queue_max_attempts
        CHECK (
            max_attempts > 0
        ),

    CONSTRAINT chk_recovery_queue_attempt_limit
        CHECK (
            autonomous_attempt_count <= max_attempts
        )
);

CREATE INDEX IF NOT EXISTS
    idx_recovery_queue_state_next_attempt_at
ON recovery_queue(
    state,
    next_attempt_at
);
