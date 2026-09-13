CREATE SCHEMA IF NOT EXISTS metadata;


CREATE TABLE IF NOT EXISTS metadata.dataset_registry (
    id BIGSERIAL PRIMARY KEY,
    namespace VARCHAR(500) NOT NULL,
    name VARCHAR(500) NOT NULL,
    layer VARCHAR(50),
    owner VARCHAR(255),
    criticality VARCHAR(30) NOT NULL DEFAULT 'MEDIUM',
    sla_minutes INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT dataset_registry_identity
        UNIQUE (namespace, name),

    CONSTRAINT dataset_registry_criticality_check
        CHECK (criticality IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),

    CONSTRAINT dataset_registry_sla_check
        CHECK (sla_minutes IS NULL OR sla_minutes > 0)
);


CREATE TABLE IF NOT EXISTS metadata.job_registry (
    id BIGSERIAL PRIMARY KEY,
    namespace VARCHAR(500) NOT NULL,
    name VARCHAR(500) NOT NULL,
    job_type VARCHAR(100),
    owner VARCHAR(255),
    criticality VARCHAR(30) NOT NULL DEFAULT 'MEDIUM',
    sla_minutes INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT job_registry_identity
        UNIQUE (namespace, name),

    CONSTRAINT job_registry_criticality_check
        CHECK (criticality IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),

    CONSTRAINT job_registry_sla_check
        CHECK (sla_minutes IS NULL OR sla_minutes > 0)
);


CREATE TABLE IF NOT EXISTS metadata.pipeline_runs (
    id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NOT NULL,
    run_id VARCHAR(255) NOT NULL,
    status VARCHAR(30) NOT NULL,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    duration_ms BIGINT,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pipeline_runs_job_fk
        FOREIGN KEY (job_id)
        REFERENCES metadata.job_registry(id),

    CONSTRAINT pipeline_runs_identity
        UNIQUE (job_id, run_id),

    CONSTRAINT pipeline_runs_duration_check
        CHECK (duration_ms IS NULL OR duration_ms >= 0)
);


CREATE INDEX IF NOT EXISTS idx_pipeline_runs_job_id
    ON metadata.pipeline_runs(job_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status
    ON metadata.pipeline_runs(status);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at
    ON metadata.pipeline_runs(started_at);
