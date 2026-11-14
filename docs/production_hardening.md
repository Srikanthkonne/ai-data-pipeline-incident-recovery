# Production Hardening

**Project:** AI-Powered Data Pipeline Incident Detection & Recovery Platform
**Phase:** 3F — Production Hardening
**Status:** COMPLETE
**Frozen:** November 14, 2026

---

## 1. Goal

Phase 3F hardens the automated recovery path so it can safely handle:

- concurrent recovery workers
- worker crashes
- stale leases
- recovery replay
- partial execution
- external command failures
- large Spark logs
- post-recovery validation
- durable auditing

---

## 2. Concurrency Control

Only one active recovery attempt may exist per incident.

Active states:

```text
STARTED
RECOVERING
```

The database enforces this with a partial unique index.

If two workers race for the same incident, only one acquires the recovery attempt.

The losing worker receives:

```text
RECOVERY_ALREADY_IN_PROGRESS
```

The database is the final concurrency authority.

---

## 3. Early Recovery Locking

The recovery attempt is created before RCA begins.

This prevents multiple workers from simultaneously performing:

```text
RCA
↓
Policy
↓
Recovery
```

for the same incident.

If RCA fails:

```text
RCA_FAILED
```

If policy evaluation fails:

```text
POLICY_FAILED
```

Both are terminal states and release active ownership.

---

## 4. Lease-Based Ownership

Each active recovery attempt contains:

```text
heartbeat_at
lease_expires_at
```

Default lease duration:

```text
300 seconds
```

A worker owns recovery only while its lease remains valid.

If the lease expires, the attempt transitions to:

```text
LEASE_EXPIRED
```

Another worker may then safely acquire ownership.

---

## 5. Heartbeat Lifecycle

The recovery orchestrator starts a daemon heartbeat thread.

Default heartbeat interval:

```text
60 seconds
```

The heartbeat periodically calls:

```text
refresh_recovery_lease()
```

A refresh succeeds only when:

```text
status IN (STARTED, RECOVERING)
AND
lease_expires_at > CURRENT_TIMESTAMP
```

Expired workers cannot revive their own lease.

---

## 6. Stale Worker Expiration

Before creating a new recovery attempt, stale active attempts are expired.

Flow:

```text
Worker A crashes
    ↓
Heartbeat stops
    ↓
Lease expires
    ↓
Worker B starts
    ↓
Expired attempt becomes LEASE_EXPIRED
    ↓
Worker B acquires recovery ownership
```

This prevents dead workers from blocking incidents indefinitely.

---

## 7. Execution Fencing

A worker must claim execution immediately before destructive recovery.

The atomic claim requires:

```text
status = STARTED
lease valid
```

Successful claim:

```text
STARTED
↓
RECOVERING
```

If ownership has expired:

```text
claim_recovery_execution() → None
```

and destructive execution is blocked.

The `recovery_attempt_id` functions as the application-level fencing token.

---

## 8. Per-Command Fencing

A single pre-execution fence is not enough for multi-step recovery.

Therefore ownership is refreshed before every external command.

Example:

```text
Guard
↓
docker cp
↓
Guard
↓
spark-submit
```

If the first command succeeds but ownership is lost before the second command:

```text
completed_steps = 1
failure_type = EXECUTION_FENCE_REJECTED
executed = True
```

The second command never executes.

This prevents stale workers from continuing side effects after ownership loss.

---

## 9. Pre-Execution Idempotency Check

Before executing recovery, the validator checks whether recovery is still required.

If the target is already healthy:

```text
recovery_needed = False
```

the executor is skipped.

The audit records:

```text
SKIPPED_ALREADY_RECOVERED
ALREADY_RECOVERED
```

This protects against replay after an ambiguous crash.

---

## 10. Crash-Safe Replay Protection

Possible ambiguous failure:

```text
Worker executes restore
↓
Restore succeeds
↓
Worker crashes before final audit
```

A replacement worker does not blindly execute restore again.

Instead:

```text
Precheck
↓
Dataset already healthy
↓
Skip recovery
↓
Resolve incident
```

This makes the workflow convergent even when execution outcome is uncertain.

---

## 11. Structured Failure Auditing

Recovery failures use:

```text
RecoveryExecutionError
```

The exception carries structured details.

Possible fields:

```text
action
status
executed
failure_type
failed_command
returncode
timeout_seconds
completed_steps
logs
```

Supported failure categories include:

```text
COMMAND_FAILED
TIMEOUT
EXECUTION_GUARD_ERROR
EXECUTION_FENCE_REJECTED
```

---

## 12. Command Timeout Protection

Each external recovery command has a bounded timeout.

Current timeout:

```text
180 seconds
```

A timeout produces:

```text
failure_type = TIMEOUT
```

and structured audit evidence.

This prevents indefinitely hanging recovery commands.

---

## 13. Bounded Audit Logs

Spark processes may generate very large stdout and stderr streams.

Audit payloads therefore store only bounded log tails.

Successful execution:

```text
MAX_CAPTURED_LOG_CHARS = 4000
```

Failure execution:

```text
MAX_ERROR_LOG_CHARS = 2000
```

The audit also stores:

```text
stdout_char_count
stderr_char_count
stdout_truncated
stderr_truncated
```

This protects PostgreSQL JSONB storage from uncontrolled growth.

---

## 14. Partial Execution Semantics

When ownership is lost after one or more commands already executed:

```text
executed = bool(completed_steps)
```

Therefore:

```text
completed_steps = 0
→ executed = False

completed_steps > 0
→ executed = True
```

This makes the audit accurately distinguish between:

- no side effect
- partial side effect
- complete execution

---

## 15. Post-Recovery Validation

Execution success alone does not resolve the incident.

The validator must confirm:

```text
dataset_exists = True
healthy = True
recovery_needed = False
remaining_detections = []
schema_column_count = 15
```

Only then may the incident transition to:

```text
RESOLVED
```

---

## 16. Terminal Recovery States

Terminal states include:

```text
COMPLETED
EXECUTION_FAILED
VALIDATION_FAILED
VALIDATION_ERROR
MANUAL_REVIEW
DRY_RUN
RCA_FAILED
POLICY_FAILED
LEASE_EXPIRED
PRECHECK_ERROR
ALREADY_RECOVERED
```

Terminal attempts receive:

```text
completed_at
```

---

## 17. Hardened End-to-End Regression

Final production-hardening regression:

```text
Incident ID: 8
Incident Type: SCHEMA_DRIFT
Injected Column: final_hardening_test_column
Recovery Attempt: 25
```

The complete workflow successfully executed:

```text
Detection
↓
RCA
↓
Runtime Provenance
↓
Deterministic Policy
↓
Concurrency Lock
↓
Lease + Heartbeat
↓
Precheck
↓
Execution Fence
↓
Per-Command Fence
↓
Spark Restore
↓
Post-Recovery Validation
↓
RESOLVED
```

Final database state:

```text
Incident 8 = RESOLVED
Recovery Attempt 25 = COMPLETED
validation_healthy = true
recovery_needed = false
schema_column_count = 15
error_message = NULL
```

---

## 18. Worker Cleanup Verification

After recovery:

```sql
SELECT *
FROM recovery_attempts
WHERE status IN ('STARTED', 'RECOVERING');
```

returned:

```text
0 rows
```

This confirmed:

```text
No active recovery workers
No stale STARTED attempt
No stale RECOVERING attempt
No active recovery lock
```

---

## 19. Production Hardening Summary

Phase 3F provides:

```text
Database concurrency control
Early ownership locking
Lease lifecycle
Heartbeat lifecycle
Stale-worker expiration
Execution fencing
Per-command fencing
Crash-safe replay protection
Pre-execution idempotency validation
Structured failure auditing
Bounded command logs
Command timeout protection
Post-recovery validation
Durable recovery audit
Full hardened end-to-end regression
```

**PHASE 3F — COMPLETE**
