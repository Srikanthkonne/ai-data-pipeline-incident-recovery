CREATE TABLE IF NOT EXISTS incidents (
    incident_id BIGSERIAL PRIMARY KEY,

    incident_type VARCHAR(100) NOT NULL,
    dataset_name VARCHAR(255) NOT NULL,

    source_system VARCHAR(100) NOT NULL,
    severity VARCHAR(30) NOT NULL,

    status VARCHAR(30) NOT NULL DEFAULT 'OPEN',

    title VARCHAR(500) NOT NULL,
    description TEXT,

    detected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ,

    metadata JSONB,

    CONSTRAINT chk_incident_status
        CHECK (
            status IN (
                'OPEN',
                'INVESTIGATING',
                'RECOVERING',
                'RESOLVED'
            )
        ),

    CONSTRAINT chk_incident_severity
        CHECK (
            severity IN (
                'LOW',
                'MEDIUM',
                'HIGH',
                'CRITICAL'
            )
        )
);