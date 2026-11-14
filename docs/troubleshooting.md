# Troubleshooting Guide

**Project:** AI-Powered Data Pipeline Incident Detection & Recovery Platform
**Scope:** Phase 1–3 implementation and Phase 3 production hardening
**Status:** COMPLETE
**Frozen:** November 14, 2026

---

## 1. Purpose

This guide documents recurring implementation and runtime issues encountered while building the platform.

The goal is to make future debugging faster by preserving:

- symptoms
- likely causes
- diagnostic commands
- fixes
- lessons learned

The guide focuses on real issues observed during development rather than hypothetical failure modes.

---

## 2. Project Root

Expected project root:

```text
/Users/srikanthkonne/Desktop/Projects/ai-data-pipeline-incident-recovery
```

Confirm:

```bash
pwd
```

Expected:

```text
/Users/srikanthkonne/Desktop/Projects/ai-data-pipeline-incident-recovery
```

---

## 3. Python Virtual Environment

Activate:

```bash
source .venv/bin/activate
```

Expected prompt prefix:

```text
(.venv)
```

Verify:

```bash
which python
python --version
```

Host Python version used during development:

```text
Python 3.14.3
```

---

## 4. Docker Environment

Start Docker Desktop first.

Then:

```bash
docker compose start
```

Check services:

```bash
docker compose ps
```

If containers were never created:

```bash
docker compose up -d
```

Safe stop:

```bash
docker compose stop
```

Do not use destructive cleanup commands unless intentionally rebuilding the environment.

Avoid:

```bash
docker compose down -v
docker system prune
```

These can remove persistent project state.

---

## 5. Expected Core Containers

Common services include:

```text
airflow-postgres
pipeline-runner
kafka
minio
marquez-postgres
incident-postgres
neo4j
spark
marquez-api
airflow-init
airflow-scheduler
airflow-webserver
marquez-web
```

Check:

```bash
docker compose ps
```

---

## 6. PostgreSQL Incident Database

Container:

```text
incident-postgres
```

Database:

```text
ecommerce
```

User:

```text
dataengineer
```

Port:

```text
5432
```

Example connection:

```bash
docker exec -it incident-postgres   psql -U dataengineer -d ecommerce
```

---

## 7. psql Shows `(END)`

### Symptom

A query output ends with:

```text
(END)
```

and the terminal appears stuck.

### Cause

The PostgreSQL pager is active.

### Fix

Press:

```text
q
```

Or disable the pager:

```bash
docker exec -it incident-postgres   psql -P pager=off   -U dataengineer   -d ecommerce
```

---

## 8. Shell Shows `heredoc>`

### Symptom

Terminal shows:

```text
heredoc>
```

and waits indefinitely.

### Cause

A heredoc terminator was not entered exactly.

For:

```bash
python - <<'PY'
...
PY
```

the closing:

```text
PY
```

must appear alone on its own line.

### Fix

If stuck:

```text
Ctrl+C
```

Then rerun the command carefully.

---

## 9. Shell Shows `quote>`

### Symptom

Terminal shows:

```text
quote>
```

### Cause

A single quote or double quote was opened but not closed.

This occurred during long Base64 / documentation commands.

### Fix

Press:

```text
Ctrl+C
```

Then rerun a shorter command.

For documentation, prefer downloading a generated Markdown file instead of pasting extremely long encoded commands.

---

## 10. Shell Shows `if function>`

### Symptom

Terminal displays:

```text
if function>
```

### Cause

Python or pseudocode was accidentally pasted directly into zsh.

The shell interprets words such as:

```text
if
function
for
```

as shell syntax.

### Fix

Press:

```text
Ctrl+C
```

Then ensure Python is executed using:

```bash
python - <<'PY'
...
PY
```

or saved in a `.py` file.

---

## 11. Bracketed Paste Characters

### Symptom

Terminal includes characters similar to:

```text
^[[200~
```

### Cause

Bracketed-paste escape sequences were included in copied text.

### Fix

Cancel with:

```text
Ctrl+C
```

Paste again using plain text or type the command manually.

---

## 12. `cp: No such file or directory`

### Symptom

Example:

```text
cp: /Users/srikanthkonne/Downloads/file.md:
No such file or directory
```

### Cause

The file has not actually been downloaded yet.

A ChatGPT file link does not automatically place the file in `~/Downloads`.

### Diagnosis

```bash
ls -lt ~/Downloads | head
```

or:

```bash
find ~/Downloads   -maxdepth 1   -iname '*filename*'   -print
```

### Fix

Download the file first.

Then use the exact path returned by `find`.

---

## 13. Markdown File Reported as `data`

### Symptom

```bash
file docs/example.md
```

returns:

```text
data
```

instead of:

```text
Unicode text, UTF-8 text
```

### Cause

The Markdown file contains invalid bytes or was corrupted during generation or copy/paste.

This occurred with:

```text
docs/recovery_architecture.md
docs/production_hardening.md
```

### Diagnosis

```bash
python - <<'PY'
from pathlib import Path

path = Path("docs/example.md")
raw = path.read_bytes()

try:
    raw.decode("utf-8")
    print("UTF-8 OK")
except UnicodeDecodeError as exc:
    print("CORRUPTED:", exc)
PY
```

### Fix

Replace the corrupted file with a clean UTF-8 version.

Verify:

```bash
file docs/example.md
```

Expected:

```text
Unicode text, UTF-8 text
```

---

## 14. Project Integrity Check

To scan main project source and documentation files:

```bash
find incident_service spark failure_injection docs \
  -type f \
  \( -name '*.py' -o -name '*.md' -o -name '*.json' \
     -o -name '*.yaml' -o -name '*.yml' -o -name '*.sql' \
     -o -name '*.toml' -o -name '*.sh' -o -name '*.txt' \) \
  -not -name '*.corrupt.bak' \
  -exec file {} \; \
  | grep ': data$'
```

Expected result:

```text
no output
```

No output means no obvious byte-level corruption was found.

---

## 15. Python Compile Check

Run:

```bash
python -m compileall -q \
  incident_service \
  spark \
  failure_injection
```

Expected:

```text
no output
```

No output means all Python files compiled successfully.

---

## 16. JSON Validation

```bash
python - <<'PY'
from pathlib import Path
import json

bad = []

for path in Path(".").rglob("*.json"):
    if ".venv" in path.parts or ".git" in path.parts:
        continue

    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        bad.append((path, exc))

if not bad:
    print("All JSON files are valid.")
else:
    for path, exc in bad:
        print(path, exc)
PY
```

Expected:

```text
All JSON files are valid.
```

---

## 17. Spark Container Python Type Error

### Symptom

Spark job fails with:

```text
TypeError: 'type' object is not subscriptable
```

### Cause

The Python version inside the Spark container does not support modern built-in generic syntax such as:

```python
dict[str, str]
```

### Fix

Use:

```python
from typing import Dict

observed_schema: Dict[str, str]
```

Alternative:

```python
from __future__ import annotations
```

The project uses `typing.Dict` in Spark-executed code for compatibility.

---

## 18. Spark File Not Found in Container

### Symptom

Spark or Docker cannot find a host-side script.

### Cause

Only:

```text
spark/
```

is mounted into:

```text
/opt/spark/work-dir
```

The directory:

```text
failure_injection/
```

is not mounted into the Spark container.

### Fix

Copy the script manually:

```bash
docker cp   failure_injection/scenarios/restore_schema_drift.py   incident-platform-spark:/tmp/restore_schema_drift.py
```

Then execute it inside the container.

---

## 19. Spark Submit Path

Use:

```text
/opt/spark/bin/spark-submit
```

Example:

```bash
docker exec incident-platform-spark   /opt/spark/bin/spark-submit   /opt/spark/work-dir/jobs/capture_silver_schema.py
```

---

## 20. Spark S3A Dependencies

Common Hadoop/AWS packages:

```text
org.apache.hadoop:hadoop-aws:3.3.4
com.amazonaws:aws-java-sdk-bundle:1.12.262
```

Example package argument:

```text
--packages
org.apache.hadoop:hadoop-aws:3.3.4,
com.amazonaws:aws-java-sdk-bundle:1.12.262
```

Use the exact package versions already validated by the project.

---

## 21. Spark Ivy Cache Permission Problems

Use:

```text
--conf spark.driver.extraJavaOptions="-Divy.cache.dir=/tmp/.ivy2"
```

and:

```text
--conf spark.jars.ivy=/tmp/.ivy2
```

This avoids dependency-cache permission issues inside the Spark container.

---

## 22. Deequ Dependency Configuration

Validated dependency set:

```text
org.apache.hadoop:hadoop-aws:3.3.4
com.amazon.deequ:deequ:3.0.3-spark-3.5
org.postgresql:postgresql:42.7.4
```

Exclude:

```text
net.sourceforge.f2j:arpack_combined_all
```

This avoids known dependency conflicts.

---

## 23. MinIO S3A Endpoint

Inside containers:

```text
http://minio:9000
```

Do not use the host browser endpoint from Spark container code.

Spark communicates using the Docker service name:

```text
minio
```

---

## 24. Silver Dataset Path

Expected:

```text
s3a://data-platform/silver/transactions
```

Healthy expected schema column count:

```text
15
```

If the validator reports:

```text
16
```

or more columns during schema-drift testing, verify whether an injected column is still present.

---

## 25. Dataset Missing During Validation

### Symptom

Validator returns:

```text
dataset_exists = False
capture_status = MISSING_DATASET
```

### Meaning

The target Silver path does not exist.

This is different from a Spark infrastructure failure.

### Response

Do not treat the target as healthy.

Recovery or operator investigation is required.

---

## 26. Schema Capture Failure

### Symptom

Validator raises:

```text
RecoveryValidationError
```

### Possible causes

- Docker command failure
- Spark failure
- S3A connection failure
- capture script exception
- missing evidence file

### Response

Treat the validation state as unknown.

Do not execute destructive recovery automatically.

The orchestrator should return:

```text
PRECHECK_ERROR
```

if the failure occurs before recovery.

---

## 27. `load_dotenv()` AssertionError

### Symptom

Using:

```python
load_dotenv()
```

from code executed through stdin may raise an assertion error under the host Python version.

### Cause

Automatic `.env` discovery may fail when there is no normal Python source-file stack frame.

### Fix

Use:

```python
load_dotenv(".env")
```

This explicitly identifies the file.

---

## 28. Gemini API Key Not Available

Check:

```bash
python - <<'PY'
import os
print(bool(os.environ.get("GEMINI_API_KEY")))
PY
```

Expected:

```text
True
```

The key may exist only in the current shell session.

Do not hardcode it in source code.

---

## 29. Gemini Provider URL Corruption

### Symptom

The provider fails because the API URL accidentally contains Markdown syntax such as:

```text
[https://...](https://...)
```

### Cause

A URL was copied from rendered Markdown instead of raw source text.

### Fix

The source uses split string fragments:

```python
url = (
    "https"
    "://"
    "generativelanguage.googleapis.com/"
    f"v1beta/models/{model}:generateContent"
)
```

This avoids accidental Markdown auto-link transformation.

---

## 30. Gemini Model

Validated Phase 3 model:

```text
gemini-3.5-flash-lite
```

If changing models, verify provider compatibility before modifying the recovery workflow.

The AI layer remains advisory.

---

## 31. Duplicate Recovery Worker

### Symptom

A second worker attempts recovery while another worker is active.

### Expected result

```text
RECOVERY_ALREADY_IN_PROGRESS
```

### Cause

The PostgreSQL partial unique index prevents more than one recovery attempt in:

```text
STARTED
RECOVERING
```

for the same incident.

This is expected safety behavior.

---

## 32. Worker Becomes `LEASE_EXPIRED`

### Meaning

The worker stopped refreshing its lease before:

```text
lease_expires_at
```

### Expected behavior

The stale worker must not resume destructive recovery.

A new worker may reclaim the incident.

---

## 33. Heartbeat Cannot Refresh Lease

`refresh_recovery_lease()` returns:

```text
None
```

when:

- the attempt is terminal
- the lease already expired
- the attempt is no longer active

This is intentional.

An expired worker cannot revive itself.

---

## 34. Recovery Fence Rejected

### Symptom

```text
RECOVERY_FENCE_REJECTED
```

### Meaning

The worker no longer owns a valid execution lease.

This is a safety result, not necessarily a bug.

The worker must stop before destructive execution.

---

## 35. Per-Command Fence Rejected

### Symptom

Executor returns:

```text
failure_type = EXECUTION_FENCE_REJECTED
```

### Meaning

Ownership was valid before an earlier command but invalid before a later command.

The executor intentionally stops remaining external side effects.

Audit fields may show:

```text
completed_steps > 0
executed = True
```

This indicates partial execution occurred before fencing stopped the workflow.

---

## 36. Execution Guard Error

### Symptom

```text
failure_type = EXECUTION_GUARD_ERROR
```

### Meaning

The ownership-validation callback itself raised an exception.

The executor stops immediately.

This defaults to safety.

---

## 37. Command Timeout

Recovery commands use bounded execution time.

Current command timeout:

```text
180 seconds
```

If exceeded, the executor raises structured timeout evidence.

Do not silently retry the same side effect without running the pre-recovery validator again.

---

## 38. Structured Recovery Failure

A recovery command failure should persist structured details including:

```text
failure_type
action
command
returncode
stdout_tail
stderr_tail
duration_ms
completed_steps
```

Do not replace structured evidence with only an exception string.

---

## 39. Large Spark Logs

Executor output is intentionally bounded.

Success capture:

```text
4000 characters
```

Failure capture:

```text
2000 characters
```

Audit fields preserve:

```text
stdout_char_count
stderr_char_count
stdout_truncated
stderr_truncated
```

This prevents PostgreSQL JSONB rows from being overwhelmed by Spark logs.

---

## 40. Recovery Already Completed Before Retry

### Symptom

A worker begins but precheck finds:

```text
healthy = True
recovery_needed = False
```

### Expected result

```text
SKIPPED_ALREADY_RECOVERED
```

and attempt status:

```text
ALREADY_RECOVERED
```

This is correct replay-safe behavior.

Do not execute the recovery action again.

---

## 41. Incident Does Not Resolve

Check:

```text
validation_result.healthy
validation_result.recovery_needed
validation_result.remaining_detections
```

Required:

```text
healthy = True
recovery_needed = False
remaining_detections = []
```

If validation fails, the incident must not be marked resolved.

---

## 42. Restore Script Crash Window

The current schema restore performs:

```text
Write temporary restore
↓
Delete current Silver
↓
Rename temporary restore
```

A crash between delete and rename can temporarily leave Silver missing.

The project mitigates this using:

- backup storage
- pre-execution validation
- replay protection
- repeatable restore behavior

The current design is convergent but not a fully atomic distributed filesystem transaction.

---

## 43. Restore Action

Allowlisted action:

```text
RESTORE_SCHEMA_DRIFT_BACKUP
```

Do not dynamically generate arbitrary shell commands from AI output.

Recovery commands must remain deterministic and allowlisted.

---

## 44. Recovery Attempt Stuck in Active State

Check:

```sql
SELECT
    recovery_attempt_id,
    incident_id,
    status,
    heartbeat_at,
    lease_expires_at
FROM recovery_attempts
WHERE status IN ('STARTED', 'RECOVERING');
```

If the lease has expired, the next recovery acquisition should mark the stale attempt:

```text
LEASE_EXPIRED
```

and allow safe reclamation.

---

## 45. Active Worker Check After Recovery

Expected final query:

```sql
SELECT *
FROM recovery_attempts
WHERE status IN ('STARTED', 'RECOVERING');
```

Expected result after completed recovery:

```text
0 rows
```

If rows remain, inspect their lease timestamps before manually changing state.

---

## 46. Incident Status Check

Example:

```sql
SELECT
    incident_id,
    incident_type,
    severity,
    status,
    detected_at,
    resolved_at
FROM incidents
ORDER BY incident_id;
```

A successful automated recovery should show:

```text
status = RESOLVED
resolved_at IS NOT NULL
```

---

## 47. Recovery Audit Check

Example:

```sql
SELECT
    recovery_attempt_id,
    incident_id,
    action,
    status,
    started_at,
    completed_at,
    heartbeat_at,
    lease_expires_at
FROM recovery_attempts
ORDER BY recovery_attempt_id;
```

A successful real recovery should show:

```text
status = COMPLETED
completed_at IS NOT NULL
```

---

## 48. Final Hardened Regression Reference

Final real test:

```text
Incident ID: 8
Recovery Attempt: 25
Injected Column: final_hardening_test_column
```

Expected final state:

```text
Incident 8 = RESOLVED
Attempt 25 = COMPLETED
Silver columns = 15
healthy = True
recovery_needed = False
active workers = 0
```

Use this as the known-good reference when debugging future changes.

---

## 49. Documentation Corruption Prevention

Do not create very large Markdown documents by pasting huge Base64 strings into the terminal.

Preferred workflow:

```text
Generate file
↓
Download file
↓
Copy into project
↓
Verify with `file`
↓
Verify UTF-8
```

Check:

```bash
file docs/example.md
```

Expected:

```text
Unicode text, UTF-8 text
```

---

## 50. Documentation UTF-8 Validation

```bash
python - <<'PY'
from pathlib import Path

for path in Path("docs").glob("*.md"):
    text = path.read_text(encoding="utf-8")
    print(path, len(text.splitlines()), "UTF-8 OK")
PY
```

Any `UnicodeDecodeError` indicates a corrupted documentation file.

---

## 51. Safe Debugging Order

When something fails, debug in this order:

```text
1. Confirm project directory
2. Confirm .venv
3. Confirm Docker Desktop
4. Confirm docker compose services
5. Confirm target container
6. Confirm target dataset
7. Confirm database state
8. Confirm evidence file
9. Confirm validator
10. Confirm recovery ownership
11. Confirm lease state
12. Confirm execution fence
13. Inspect structured executor evidence
14. Run post-validation
```

This avoids jumping directly to the LLM or recovery executor when the underlying issue is infrastructure.

---

## 52. Recovery Debugging Principle

The most important operational rule is:

```text
Do not retry destructive recovery blindly.
```

Always run the deterministic precheck first.

The precheck determines whether:

```text
recovery is still needed
```

or:

```text
the system is already healthy
```

---

## 53. Authority Principle

When AI output and deterministic evidence disagree:

```text
Deterministic evidence wins.
```

Runtime provenance, validation, database ownership, and allowlisted recovery policy are authoritative.

Gemini output is supporting investigation evidence only.

---

## 54. Final Troubleshooting Status

This guide reflects the major implementation and runtime issues observed through Phase 3.

Known validated project state:

```text
Documentation UTF-8: PASS
Python compilation: PASS
JSON validation: PASS
Schema recovery: PASS
Concurrency protection: PASS
Lease recovery: PASS
Execution fencing: PASS
Replay protection: PASS
Structured auditing: PASS
Full real recovery: PASS
```

**PHASE 3 TROUBLESHOOTING GUIDE — COMPLETE**
