ALTER TABLE recovery_attempts
ADD COLUMN IF NOT EXISTS heartbeat_at
    TIMESTAMP WITH TIME ZONE;

ALTER TABLE recovery_attempts
ADD COLUMN IF NOT EXISTS lease_expires_at
    TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS
    idx_recovery_attempts_lease_expires_at
ON recovery_attempts(lease_expires_at)
WHERE status IN (
    'STARTED',
    'RECOVERING'
);
