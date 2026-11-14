CREATE UNIQUE INDEX IF NOT EXISTS
    uq_recovery_attempts_active_incident
ON recovery_attempts(incident_id)
WHERE status IN (
    'STARTED',
    'RECOVERING'
);
