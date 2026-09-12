CREATE TABLE IF NOT EXISTS data_quality_results (
    id BIGSERIAL PRIMARY KEY,

    dataset_name VARCHAR(255) NOT NULL,
    check_name VARCHAR(255) NOT NULL,
    metric_name VARCHAR(255) NOT NULL,

    metric_value DOUBLE PRECISION,

    status VARCHAR(30) NOT NULL,

    details TEXT,

    run_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);