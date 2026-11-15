# Phase 4 — Platformization & Autonomous Operations

## Status

- Phase 4A — Autonomous Incident Worker: COMPLETE
- Phase 4B — Retry / Backoff / Requeue: COMPLETE
- Phase 4C — FastAPI Control Plane: PENDING
- Phase 4D — Metrics / Dashboard: PENDING
- Phase 4E — Integration / Chaos Testing: PENDING
- Phase 4F — CI/CD / Deployment Readiness: PENDING

## Phase 4A — Autonomous Incident Worker

Phase 4A adds an autonomous worker around the hardened Phase 3 recovery engine.

The worker does not replace Phase 3 recovery logic. It delegates recovery to the existing `recover_incident()` orchestrator.

### Flow

Pipeline/Data Failure
→ Incident Created
→ automation_eligible=true
→ Autonomous Worker
→ Phase 3 Recovery Orchestrator
→ RCA + Runtime Provenance
→ Deterministic Recovery Policy
→ Lease / Heartbeat / Fencing
→ Recovery Execution
→ Validation
→ RESOLVED

## Components

- `incident_service/repository.py`
  - `get_automation_candidates()`
- `incident_service/worker/config.py`
- `incident_service/worker/recovery_worker.py`
- `incident_service/worker/main.py`
- `incident_service/worker/__init__.py`

## Automation Eligibility

An incident is eligible only when:

- status is OPEN
- `metadata.automation_eligible=true`
- no previous recovery attempt exists

The automation flag controls worker eligibility only.

It does not authorize infrastructure modification. Automatic recovery authorization remains the responsibility of the deterministic Phase 3 recovery policy.

## At-Most-Once Dispatch

Phase 4A permits one autonomous dispatch per incident.

An incident that already has a recovery attempt is excluded from candidate selection.

Retry, backoff, and requeue semantics are intentionally deferred to Phase 4B.

## Worker Configuration

Environment variables:

- `INCIDENT_WORKER_POLL_INTERVAL_SECONDS`
- `INCIDENT_WORKER_MAX_INCIDENTS_PER_CYCLE`
- `INCIDENT_WORKER_DRY_RUN`

Defaults:

- polling interval: 10 seconds
- max incidents per cycle: 1
- dry run: true

Dry-run is enabled by default.

## Continuous Worker

The worker supports continuous polling and graceful shutdown through SIGINT, SIGTERM, and `threading.Event`.

The executable entry point is:

`python -m incident_service.worker.main`

The worker loads `.env` before initializing the Gemini provider.

## Controlled Dry-Run Validation

Incident 9 was used for the controlled dry-run test.

The worker discovered the eligible incident, but the mock RCA provider deliberately returned insufficient evidence.

Result:

- worker status: COMPLETED
- orchestration status: MANUAL_REVIEW
- action: MANUAL_REVIEW
- automatic execution allowed: false

This proved that worker automation cannot bypass deterministic recovery policy.

## Fail-Closed RCA Validation

A real schema drift using `phase4_autonomous_test_column` created Incident 10.

Recovery Attempt 27 failed during RCA because `GEMINI_API_KEY` was not configured.

Persisted result:

- Incident 10: OPEN
- Recovery Attempt 27: RCA_FAILED
- action: PENDING_RCA
- recovery execution: not performed

The failed attempt was preserved as audit history.

## Successful Real Autonomous Recovery

Silver was restored to the healthy 15-column baseline.

A fresh schema drift was injected:

`phase4_autonomous_retry_column`

The validator confirmed:

- healthy: false
- recovery needed: true
- schema column count: 16
- drift: UNEXPECTED_COLUMN

Incident 11 was created and explicitly marked automation eligible.

The autonomous worker discovered Incident 11 and executed the existing hardened recovery workflow.

Final result:

- Incident 11: RESOLVED
- Recovery Attempt 28: COMPLETED
- action: RESTORE_SCHEMA_DRIFT_BACKUP
- automatic execution allowed: true
- execution status: COMPLETED
- executed: true
- validation healthy: true
- validation recovery needed: false
- final schema column count: 15
- remaining detections: none

Final automation candidate count:

0

## Final Safety Chain

Explicit automation opt-in
→ At-most-once worker dispatch
→ Phase 3 recovery lock
→ AI-assisted RCA
→ Deterministic provenance authority
→ Deterministic recovery policy
→ Lease + heartbeat
→ Execution fencing
→ Per-command fencing
→ Recovery
→ Mandatory validation
→ RESOLVED

The LLM remains advisory.

Deterministic evidence and recovery policy remain authoritative.

## Final Phase 4A Validation

- Silver health: PASS
- 15-column healthy schema: PASS
- Automation queue empty: PASS
- No active recovery attempts: PASS
- Controlled manual-review test: PASS
- Fail-closed RCA audit test: PASS
- Real autonomous recovery E2E: PASS
- Graceful shutdown: PASS
- Python compilation: PASS
- Git whitespace check: PASS
- `.env` ignored: PASS
- Tracked Gemini-secret scan: PASS

**PHASE 4A — COMPLETE**

## Phase 4B — Recovery Queue, Retry, Backoff, and Requeue

Phase 4B replaces the Phase 4A at-most-once autonomous dispatch limitation with an explicit durable recovery queue.

The hardened Phase 3 recovery engine remains unchanged. Each real autonomous retry invokes `recover_incident()` again and creates a new immutable recovery attempt.

### Architecture

Incident Created

→ Automation Eligibility

→ Queue Seed

→ READY

→ Atomic Claim

→ PROCESSING

→ Queue Claim Heartbeat

→ Phase 3 `recover_incident()`

→ Outcome Classification

→ COMPLETED / TERMINAL / RETRY_WAIT / EXHAUSTED

### Components

- `incident_service/recovery/queue_repository.py`

- `incident_service/recovery/retry_policy.py`

- `incident_service/recovery/sql/004_create_recovery_queue.sql`

- `incident_service/recovery/sql/005_add_recovery_queue_claim_lease.sql`

- `incident_service/worker/config.py`

- `incident_service/worker/recovery_worker.py`

### Recovery Queue States

The durable recovery queue supports:

- `READY` — immediately eligible for autonomous recovery

- `PROCESSING` — owned by an active worker claim

- `RETRY_WAIT` — retryable failure waiting for `next_attempt_at`

- `EXHAUSTED` — autonomous retry budget consumed

- `TERMINAL` — deterministic non-retryable outcome

- `COMPLETED` — recovery lifecycle successfully closed

The incident table continues to represent business lifecycle state. `recovery_attempts` continues to represent immutable detailed recovery history. `recovery_queue` represents autonomous scheduling and retry state.

### Queue Claiming and Concurrency

Queue claims use an opaque claim token and expiration lease.

Atomic claiming uses PostgreSQL row locking with `FOR UPDATE SKIP LOCKED`, allowing multiple workers to compete without claiming the same queue item.

A claimed queue item stores:

- `claim_token`

- `claimed_at`

- `claim_expires_at`

The worker periodically refreshes the queue claim while Phase 3 recovery is running.

If the queue claim is lost, the stale worker is fenced from changing queue state.

The queue claim token controls worker ownership only. The Phase 3 `recovery_attempt_id` remains the destructive recovery execution fencing token.

### Expired Claim Recovery

Expired `PROCESSING` claims are reclaimed automatically.

If retry budget remains, the queue item returns to `READY`. If the maximum autonomous attempt count has already been reached, it becomes `EXHAUSTED`.

Expired claims retain the consumed autonomous attempt count instead of silently restoring retry budget.

### Retry Classification

Retryable outcomes:

- `RCA_FAILED`

- `EXECUTION_FAILED`

- `VALIDATION_ERROR`

- `VALIDATION_FAILED`

- `LEASE_EXPIRED`

- `RECOVERY_FENCE_REJECTED`

- `RECOVERY_ALREADY_IN_PROGRESS`

- `WORKER_ERROR`

Terminal outcomes:

- `POLICY_FAILED`

- `MANUAL_REVIEW`

- `PRECHECK_ERROR`

Successful outcomes:

- `RESOLVED`

- `COMPLETED`

- `ALREADY_RECOVERED`

Unknown outcomes fail closed as terminal rather than being retried automatically.

### Retry Limits and Backoff

Default autonomous retry limit: 3 attempts.

Default exponential backoff:

- attempt 1: 60 seconds

- attempt 2: 120 seconds

- attempt 3: 240 seconds

Maximum default backoff: 1800 seconds.

Backoff is calculated from the queue autonomous attempt count and capped by configuration.

When the final allowed attempt fails with a retryable outcome, the queue transitions to `EXHAUSTED`.

### Manual Requeue

`manual_requeue_recovery()` allows an operator to reopen an `EXHAUSTED` or `TERMINAL` queue item.

Manual requeue:

- returns the queue item to `READY`

- resets autonomous attempt count to 0

- starts a new bounded autonomous retry window

- preserves the previous recovery-attempt pointer and status

- does not delete immutable recovery audit history

### Dry-Run Semantics

Dry-run processing is non-consuming.

The worker may claim a queue item and invoke Phase 3 in dry-run mode, but `release_recovery_queue_claim()` returns the queue item to `READY` and restores the autonomous attempt counter.

To prevent a continuously running dry-run worker from repeatedly previewing the same `READY` item, `run_forever()` executes exactly one cycle when `dry_run=true`.

### Worker Configuration

Environment variables:

- `INCIDENT_WORKER_POLL_INTERVAL_SECONDS`

- `INCIDENT_WORKER_MAX_INCIDENTS_PER_CYCLE`

- `INCIDENT_WORKER_DRY_RUN`

- `INCIDENT_WORKER_MAX_AUTONOMOUS_ATTEMPTS`

- `INCIDENT_WORKER_QUEUE_CLAIM_SECONDS`

- `INCIDENT_WORKER_QUEUE_HEARTBEAT_INTERVAL_SECONDS`

- `INCIDENT_WORKER_RETRY_BASE_SECONDS`

- `INCIDENT_WORKER_RETRY_MAX_SECONDS`

Defaults:

- polling interval: 10 seconds

- max incidents per cycle: 1

- dry run: true

- max autonomous attempts: 3

- queue claim lease: 300 seconds

- queue heartbeat interval: 60 seconds

- retry base: 60 seconds

- retry maximum: 1800 seconds

Configuration validation requires positive values, queue heartbeat shorter than the claim lease, and retry base less than or equal to retry maximum.

### Controlled Phase 4B Validation

Incident 10 was used as the controlled Phase 4B queue fixture.

#### Dry-Run Queue Lifecycle

Incident 10 was manually seeded into an empty recovery queue.

Recovery Attempt 29 produced `DRY_RUN`.

Verified result:

- queue claimed successfully

- recovery execution was not performed

- queue returned to `READY`

- autonomous attempt count returned to 0

- last recovery attempt recorded as 29

- last attempt status recorded as `DRY_RUN`

- Incident 10 remained `OPEN`

#### Retry and Exponential Backoff

A controlled RCA provider deliberately raised `PHASE4B_CONTROLLED_RCA_FAILURE`.

Test-only backoff configuration used 1-second base and 4-second maximum to validate the sequence quickly.

Results:

- Attempt 30: `RCA_FAILED`, count 1, backoff 1 second, queue `RETRY_WAIT`

- Attempt 31: `RCA_FAILED`, count 2, backoff 2 seconds, queue `RETRY_WAIT`

- Attempt 32: `RCA_FAILED`, count 3, backoff 4 seconds, queue `EXHAUSTED`

All three attempts preserved `automatic_execution_allowed=false` and performed no recovery execution.

#### Manual Requeue Validation

The exhausted Incident 10 queue item was manually requeued.

Verified result:

- `EXHAUSTED` → `READY`

- autonomous attempt count 3 → 0

- max attempts remained 3

- previous attempt pointer 32 preserved

- previous status `RCA_FAILED` preserved

- immutable recovery attempts remained intact

#### Successful Queue Completion

A real non-dry-run one-cycle worker execution processed Incident 10 after manual requeue.

Gemini RCA and deterministic policy authorized `RESTORE_SCHEMA_DRIFT_BACKUP`.

Phase 3 pre-execution validation detected that the target Silver dataset was already healthy, so destructive execution was safely skipped.

Recovery Attempt 33 finished as `ALREADY_RECOVERED`.

Final persisted result:

- Incident 10: `RESOLVED`

- queue state: `COMPLETED`

- autonomous attempt count: 1

- last recovery attempt: 33

- last attempt status: `ALREADY_RECOVERED`

- automatic execution allowed: true

- execution status: `SKIPPED_ALREADY_RECOVERED`

- validation healthy: true

- recovery needed: false

This validates idempotent queue completion when the underlying fault has already been remediated.

### Phase 4B Safety Chain

Explicit automation opt-in

→ Durable queue

→ Atomic queue claim

→ Queue lease + heartbeat

→ Queue claim fencing

→ Fresh immutable Phase 3 recovery attempt

→ AI-assisted RCA

→ Deterministic provenance authority

→ Deterministic recovery policy

→ Phase 3 recovery lease + heartbeat

→ Execution fencing

→ Pre-execution replay/idempotency validation

→ Recovery if still required

→ Mandatory validation

→ Retry / terminal / completed queue transition

The LLM remains advisory. Deterministic evidence, policy, fencing, validation, retry limits, and queue ownership remain authoritative.

## Final Phase 4B Validation

- Recovery queue migration: PASS

- Queue claim lease migration: PASS

- Queue repository lifecycle tests: PASS

- Atomic claim / `SKIP LOCKED` design: PASS

- Queue claim heartbeat: PASS

- Stale-token fencing: PASS

- Expired claim reclaim: PASS

- Dry-run non-consuming release: PASS

- Dry-run single-cycle protection: PASS

- Retry classification: PASS

- Exponential backoff: PASS

- Maximum autonomous attempt enforcement: PASS

- `EXHAUSTED` transition: PASS

- Manual requeue: PASS

- Immutable retry audit history: PASS

- `ALREADY_RECOVERED` completion: PASS

- Incident resolution: PASS

- Python compilation: PASS

- Git whitespace check: PASS

**PHASE 4B — COMPLETE**

## Next Phase

Phase 4C will add a FastAPI control plane for incident inspection, recovery queue visibility, operator actions, manual requeue, and recovery status access.
