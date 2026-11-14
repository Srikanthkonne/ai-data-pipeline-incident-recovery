CREATE TABLE IF NOT EXISTS metadata.dataset_schema_snapshots (
    id BIGSERIAL PRIMARY KEY,
    dataset_id BIGINT NOT NULL,
    schema_hash VARCHAR(64) NOT NULL,
    schema_json JSONB NOT NULL,
    first_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    observation_count BIGINT NOT NULL DEFAULT 1,

    CONSTRAINT dataset_schema_snapshots_dataset_fk
        FOREIGN KEY (dataset_id)
        REFERENCES metadata.dataset_registry(id),

    CONSTRAINT dataset_schema_snapshots_identity
        UNIQUE (dataset_id, schema_hash),

    CONSTRAINT dataset_schema_snapshots_observation_count_check
        CHECK (observation_count > 0)
);


CREATE INDEX IF NOT EXISTS idx_dataset_schema_snapshots_dataset_id
    ON metadata.dataset_schema_snapshots(dataset_id);

CREATE INDEX IF NOT EXISTS idx_dataset_schema_snapshots_first_seen
    ON metadata.dataset_schema_snapshots(first_seen_at);
