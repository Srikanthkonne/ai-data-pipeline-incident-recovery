ALTER TABLE recovery_queue
ADD COLUMN IF NOT EXISTS claim_token
    VARCHAR(100);

ALTER TABLE recovery_queue
ADD COLUMN IF NOT EXISTS claimed_at
    TIMESTAMP WITH TIME ZONE;

ALTER TABLE recovery_queue
ADD COLUMN IF NOT EXISTS claim_expires_at
    TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS
    idx_recovery_queue_claim_expires_at
ON recovery_queue(claim_expires_at)
WHERE state = 'PROCESSING';

ALTER TABLE recovery_queue
DROP CONSTRAINT IF EXISTS
    chk_recovery_queue_processing_claim;

ALTER TABLE recovery_queue
ADD CONSTRAINT
    chk_recovery_queue_processing_claim
CHECK (
    state <> 'PROCESSING'
    OR (
        claim_token IS NOT NULL
        AND claimed_at IS NOT NULL
        AND claim_expires_at IS NOT NULL
    )
);
