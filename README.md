# Lineage-Aware Autonomous Data Pipeline Incident Detection & Recovery Platform

An AI-assisted, production-style data reliability platform that detects pipeline failures, performs lineage- and provenance-aware root-cause analysis, and safely executes autonomous recovery using deterministic guardrails.

The system demonstrates a full path from data ingestion to autonomous incident response:

```text
Kafka
↓
Bronze
↓
Silver
↓
Data Quality
↓
Gold
↓
Lineage + Observability
↓
Incident Detection
↓
Root Cause Analysis
↓
Deterministic Recovery Policy
↓
Safe Automated Recovery
↓
Validation
↓
Incident Resolution
```

---

## Project Status

```text

Phase 1 — Core Data Pipeline                         COMPLETE

Phase 2 — Data Quality, Metadata, and Lineage        COMPLETE

Phase 3 — Incident Detection and Recovery            COMPLETE

Phase 3F — Production Hardening                      COMPLETE

Phase 4 — Platformization & Autonomous Operations    COMPLETE

Phase 5A — Execution Adapter Abstraction             COMPLETE

Phase 5B — AWS Cloud Recovery Execution              COMPLETE

Phase 5C — AWS Infrastructure as Code                COMPLETE

Phase 5D — Cloud Control Plane Deployment            COMPLETE

Phase 5E — Terraform CI/CD Checks                    COMPLETE

Phase 5F — AWS Observability Hardening               COMPLETE

Phase 5G — Final Architecture / Documentation        COMPLETE


```

Final autonomous AWS recovery proof:

```text

Incident ID:                 1

Incident Type:               SCHEMA_DRIFT

Recovery Attempt:            4

Recovery Action:             RESTORE_SCHEMA_DRIFT_BACKUP

Execution Backend:           emr-serverless

Storage Backend:             aws-s3

Recovery Status:             COMPLETED

Post-Validation Healthy:     true

Recovery Needed:             false

Final Schema Columns:        15

Remaining Detections:        none

Final Incident Status:       RESOLVED

```

---

# 1. Why This Project Exists

Modern data platforms often detect failures but still depend on engineers to manually:

- identify the affected dataset
- inspect lineage
- determine root cause
- decide whether recovery is safe
- run remediation commands
- verify whether the repair worked
- close the incident

This project explores how much of that workflow can be automated safely.

The design intentionally separates:

```text
AI reasoning
```

from:

```text
infrastructure authority
```

AI assists investigation.

Deterministic controls decide whether recovery is allowed.

---

# 2. Core Design Principle

The platform follows one central rule:

> AI may assist with investigation, but deterministic controls decide whether infrastructure-changing recovery is permitted.

The authority chain is:

```text
Observed Evidence
↓
Runtime Provenance
↓
Lineage Context
↓
Normalized RCA Facts
↓
AI Investigation
↓
Deterministic Guardrails
↓
Deterministic Recovery Policy
↓
Database Ownership
↓
Lease + Fencing
↓
Allowlisted Execution
↓
Post-Recovery Validation
```

The LLM never directly executes arbitrary infrastructure commands.

---

# 3. High-Level Architecture

```mermaid
flowchart TD
    A[Transaction Generator] --> B[Kafka]
    B --> C[Bronze - S3 / MinIO]
    C --> D[Silver - Spark]
    D --> E[Deequ Data Quality]
    E --> F[PostgreSQL DQ Results]
    D --> G[dbt Gold Models]
    D --> H[OpenLineage / Marquez]
    H --> I[Neo4j Lineage Graph]

    E --> J[Incident Detection]
    H --> J
    J --> K[Incident Service]
    K --> L[Runtime Provenance]
    L --> M[Normalized RCA Facts]
    M --> N[Gemini Investigator]
    N --> O[Deterministic Guardrails]
    O --> P[Recovery Policy]
    P --> Q[Recovery Lock + Lease]
    Q --> R[Pre-Recovery Validation]
    R --> S[Execution Fencing]
    S --> T[Allowlisted Recovery Executor]
    T --> U[Post-Recovery Validation]
    U --> V[Incident RESOLVED]
```

---

# 4. Technology Stack

## Data Engineering

```text
Apache Kafka
Apache Spark
PySpark
MinIO / S3A
dbt
DuckDB
Apache Airflow
```

## Data Quality

```text
Amazon Deequ
Custom validation logic
PostgreSQL
```

## Lineage and Observability

```text
OpenLineage
Marquez
Neo4j
```

## Incident Platform

```text
Python
PostgreSQL
JSONB audit records
```

## AI-Assisted RCA

```text
Google Gemini
Provider-neutral AI contract
Deterministic RCA guardrails
```

Validated model:

```text
gemini-3.5-flash-lite
```

## Infrastructure

```text

Docker

Docker Compose

Terraform

Amazon VPC

Application Load Balancer

Amazon ECS / AWS Fargate

Amazon ECR

Amazon RDS PostgreSQL

Amazon S3

Amazon EMR Serverless

AWS IAM

AWS Secrets Manager

Amazon CloudWatch Logs

CloudWatch log metric filters

```

---

# 5. Phase 1 — Core Data Pipeline

Phase 1 establishes the ingestion and transformation foundation.

Flow:

```text
Python Transaction Generator
↓
Kafka Topic: transactions
↓
Bronze Storage
↓
Spark Processing
↓
Silver Transactions
```

Kafka topic:

```text
transactions
```

Partitions:

```text
3
```

Bronze storage:

```text
S3 / MinIO
```

Silver location:

```text
s3a://data-platform/silver/transactions
```

---

# 6. Silver Data Model

The healthy Silver dataset contains 15 columns:

```text
transaction_id
customer_id
order_id
payment_id
amount
payment_method
status
event_time
kafka_key
kafka_topic
kafka_partition
kafka_offset
kafka_timestamp
ingestion_timestamp
silver_processed_at
```

Known healthy Phase 3 baseline:

```text
55 rows
15 columns
```

Silver transformation job:

```text
spark/jobs/silver_transactions.py
```

---

# 7. Phase 2 — Data Quality

Phase 2 adds automated quality checks to the Silver layer.

Representative checks include:

```text
Null validation
Uniqueness validation
Positive-value checks
Schema validation
```

Deequ results are persisted into PostgreSQL:

```text
data_quality_results
```

This creates durable evidence that can later be converted into incidents.

---

# 8. Phase 2 — Gold Layer

dbt transforms validated Silver data into analytics-ready models.

Tools:

```text
dbt
DuckDB
```

The Phase 2 implementation includes staging and mart models with validated dbt tests.

---

# 9. Phase 2 — Lineage

Lineage is captured using:

```text
OpenLineage
Marquez
```

Neo4j is used for graph-based lineage analysis and blast-radius reasoning.

This enables questions such as:

```text
Which downstream assets depend on this dataset?
```

and:

```text
What systems are affected by this incident?
```

---

# 10. Phase 3 — Incident Service

The incident service persists detected failures in PostgreSQL.

Core table:

```text
incidents
```

Representative fields:

```text
incident_id
incident_type
dataset_name
source_system
severity
status
title
description
detected_at
resolved_at
metadata
```

Supported lifecycle:

```text
OPEN
↓
INVESTIGATING
↓
RECOVERING
↓
RESOLVED
```

---

# 11. Supported Incident Types

Phase 3 validates multiple incident categories:

```text
NULL_SPIKE
SCHEMA_DRIFT
SLA_BREACH
```

The primary automated-recovery scenario is:

```text
SCHEMA_DRIFT
```

---

# 12. Root Cause Analysis Architecture

RCA combines deterministic evidence with AI-assisted interpretation.

Core modules:

```text
incident_service/rca/facts.py
incident_service/rca/ai_contract.py
incident_service/rca/ai_investigator.py
incident_service/rca/diagnostics/runtime_provenance.py
incident_service/rca/providers/gemini.py
```

Flow:

```text
Incident
+
Lineage
+
Observed Schema
+
Runtime Provenance
↓
Normalized RCA Facts
↓
Gemini Investigator
↓
Deterministic Guardrails
```

---

# 13. Runtime Provenance

Controlled failure injections persist provenance evidence.

Typical evidence:

```text
execution_id
scenario
status
target_dataset
injected_column
injected_value
completed_at
```

Runtime provenance provides deterministic evidence of what changed.

This is especially important when validating AI-generated RCA.

---

# 14. AI Provider Contract

The RCA layer uses a provider-neutral interface.

This keeps orchestration logic independent of any specific LLM provider.

Current real provider:

```text
Google Gemini
```

The provider is responsible for structured investigation output.

The provider does not decide whether infrastructure recovery is authorized.

---

# 15. Deterministic RCA Guardrails

The AI response is checked against deterministic evidence.

For schema drift, a valid causal match may require:

```text
Injected Column
=
Observed Unexpected Column
=
Runtime Provenance Column
```

If AI output disagrees with deterministic evidence:

```text
deterministic evidence wins
```

---

# 16. Recovery Policy

Recovery policy:

```text
incident_service/recovery/policy.py
```

The policy maps normalized RCA facts to deterministic recovery actions.

Validated schema-drift action:

```text
RESTORE_SCHEMA_DRIFT_BACKUP
```

Automatic execution is permitted only when deterministic conditions are satisfied.

AI confidence alone cannot authorize recovery.

---

# 17. Recovery Executor

Recovery executor:

```text
incident_service/recovery/executor.py
```

The executor only supports allowlisted actions.

Schema-drift recovery flow:

```text
Clean Backup
↓
Temporary Restore
↓
Replace Drifted Silver
↓
Validate Restored Dataset
```

Backup path:

```text
s3a://data-platform/failure-backups/schema-drift/silver-transactions
```

Temporary restore path:

```text
s3a://data-platform/failure-temp/schema-drift-restore/silver-transactions
```

---

# 18. Recovery Validation

Validator:

```text
incident_service/recovery/validator.py
```

Schema capture job:

```text
spark/jobs/capture_silver_schema.py
```

Evidence:

```text
spark/evidence/silver_schema.json
```

Healthy validation contract:

```text
dataset_exists = True
capture_status = CAPTURED
healthy = True
recovery_needed = False
remaining_detections = []
schema_column_count = 15
```

An incident is not resolved until this contract passes.

---

# 19. Missing Dataset Handling

The validator explicitly differentiates:

```text
missing dataset
```

from:

```text
Spark / Docker / capture failure
```

Missing dataset:

```text
dataset_exists = False
capture_status = MISSING_DATASET
healthy = False
recovery_needed = True
```

Infrastructure validation failures raise a recovery validation error.

This prevents unknown states from being interpreted as healthy.

---

# 20. Recovery Audit Table

Recovery attempts are persisted in:

```text
recovery_attempts
```

Representative fields:

```text
recovery_attempt_id
incident_id
action
status
automatic_execution_allowed
rca_assessment
recovery_decision
execution_result
validation_result
error_message
started_at
completed_at
heartbeat_at
lease_expires_at
```

This provides a durable recovery audit trail.

---

# 21. Production Hardening

Phase 3F adds production-style protection around automated recovery.

Implemented controls include:

```text
Database-enforced concurrency
Lease-based ownership
Worker heartbeat
Expired-worker reclamation
Execution fencing
Per-command fencing
Replay protection
Structured failures
Bounded audit logs
Mandatory post-recovery validation
```

---

# 22. Concurrency Protection

Only one active recovery attempt may exist per incident.

PostgreSQL partial unique index:

```text
uq_recovery_attempts_active_incident
```

Active statuses:

```text
STARTED
RECOVERING
```

If a second worker attempts recovery:

```text
RECOVERY_ALREADY_IN_PROGRESS
```

The database is the final concurrency authority.

---

# 23. Lease and Heartbeat

Active recovery attempts contain:

```text
heartbeat_at
lease_expires_at
```

Default recovery lease:

```text
300 seconds
```

Heartbeat interval:

```text
60 seconds
```

If a worker crashes:

```text
heartbeat stops
↓
lease expires
↓
attempt becomes LEASE_EXPIRED
↓
another worker may reclaim the incident
```

---

# 24. Execution Fencing

Before destructive recovery begins:

```text
claim_recovery_execution()
```

atomically verifies that the worker still owns a valid lease.

The recovery attempt ID acts as the application-level fencing token.

A stale worker cannot continue destructive execution.

---

# 25. Per-Command Fencing

Ownership is refreshed before each external command.

Example:

```text
Guard
↓
Command 1
↓
Guard
↓
Command 2
```

If ownership is lost before Command 2:

```text
Command 2 does not execute
```

Failure type:

```text
EXECUTION_FENCE_REJECTED
```

This protects multi-command recovery workflows.

---

# 26. Replay Protection

Before execution, the validator checks whether the target still needs recovery.

If another worker already recovered the dataset:

```text
healthy = True
recovery_needed = False
```

the executor is skipped.

Audit status:

```text
ALREADY_RECOVERED
```

This makes recovery replay-safe after ambiguous worker crashes.

---

# 27. Structured Execution Failures

Executor failures are persisted as structured evidence.

Examples:

```text
COMMAND_FAILED
TIMEOUT
EXECUTION_GUARD_ERROR
EXECUTION_FENCE_REJECTED
```

Audit evidence includes:

```text
command
returncode
duration_ms
stdout_tail
stderr_tail
completed_steps
```

---

# 28. Bounded Audit Logs

Spark can produce large logs.

The recovery executor bounds captured output.

Success log limit:

```text
4000 characters
```

Failure log limit:

```text
2000 characters
```

Audit records preserve:

```text
original character count
truncation status
captured tail
```

This keeps PostgreSQL JSONB audit records manageable.

---

# 29. Failure Injection Framework

Controlled failure scenarios are stored under:

```text
failure_injection/scenarios/
```

Failure evidence:

```text
spark/evidence/failure_injections/
```

Validated scenarios include:

```text
Null spike
Schema drift
SLA breach
Concurrency conflict
RCA failure
Policy failure
Lease expiry
Stale worker
Structured executor failure
Replay / idempotency
Per-command fence rejection
```

---

# 30. Final Hardened Regression

The final Phase 3F test injected:

```text
final_hardening_test_column
```

with value:

```text
PHASE_3F_15
```

Observed drifted schema:

```text
16 columns
```

Detection:

```text
UNEXPECTED_COLUMN
```

Incident:

```text
Incident ID: 8
Type: SCHEMA_DRIFT
Severity: HIGH
Status: OPEN
```

---

# 31. Final Provenance Evidence

Execution ID:

```text
87533964-bd6a-4d8a-8253-a6c7da0b9fa5
```

Scenario:

```text
SCHEMA_DRIFT
```

Injected column:

```text
final_hardening_test_column
```

Injected value:

```text
PHASE_3F_15
```

Status:

```text
COMPLETED
```

---

# 32. Final Recovery Result

Real recovery:

```python
result = recover_incident(
    incident_id=8,
    provider=gemini_provider,
    dry_run=False,
)
```

Recovery attempt:

```text
25
```

Decision:

```text
RESTORE_SCHEMA_DRIFT_BACKUP
```

Execution:

```text
COMPLETED
```

Post-validation:

```text
dataset_exists = True
healthy = True
recovery_needed = False
remaining_detections = []
schema_column_count = 15
```

Final incident state:

```text
RESOLVED
```

Active workers:

```text
0
```

---

# 33. Recovery Safety Model

The automated-recovery design uses defense in depth.

```text
Runtime Provenance
+
Lineage
+
AI-Assisted RCA
+
Deterministic Guardrails
+
Deterministic Recovery Policy
+
Database Concurrency
+
Lease / Heartbeat
+
Execution Fencing
+
Per-Command Fencing
+
Replay Protection
+
Allowlisted Commands
+
Mandatory Validation
+
Durable Audit Trail
```

No single safety layer is treated as sufficient.

---

# 34. Repository Structure

Representative project structure:

```text
.
├── incident_service/
│   ├── db.py
│   ├── repository.py
│   ├── rca/
│   │   ├── facts.py
│   │   ├── ai_contract.py
│   │   ├── ai_investigator.py
│   │   ├── diagnostics/
│   │   │   └── runtime_provenance.py
│   │   └── providers/
│   │       └── gemini.py
│   └── recovery/
│       ├── executor.py
│       ├── orchestrator.py
│       ├── policy.py
│       ├── validator.py
│       └── sql/
├── spark/
│   ├── jobs/
│   │   ├── silver_transactions.py
│   │   └── capture_silver_schema.py
│   └── evidence/
├── failure_injection/
│   └── scenarios/
├── docs/
├── docker-compose.yml
└── README.md
```

---

# 35. Phase 3 Documentation

Detailed Phase 3 documentation is available in:

```text
docs/phase_3_incident_recovery.md
```

End-to-end incident detection, RCA, recovery, validation, and project status.

```text
docs/recovery_architecture.md
```

Recovery ownership, lease, fencing, replay protection, and architecture.

```text
docs/production_hardening.md
```

Detailed Phase 3F production-hardening implementation and test evidence.

```text
docs/failure_injection_testing.md
```

Controlled failure scenarios and regression proof.

```text
docs/troubleshooting.md
```

Real implementation issues, diagnostics, fixes, and operational guidance.

---


```text

docs/phase_5_cloud_deployment.md

```

Final AWS architecture, cloud control plane, Terraform/IAM model, autonomous cloud recovery proof, CI validation, and CloudWatch monitoring.

---

# 36. Local Environment

Development environment:

```text
macOS
Apple Silicon
Python 3.14.3
Docker 29.7.2
Docker Compose 5.4.0
Spark 3.5.1
PostgreSQL 16
```

---

# 37. Start the Platform

Start Docker Desktop.

Then:

```bash
docker compose start
```

Check:

```bash
docker compose ps
```

If services have not yet been created:

```bash
docker compose up -d
```

---

# 38. Stop the Platform

Use:

```bash
docker compose stop
```

Avoid destructive commands such as:

```bash
docker compose down -v
docker system prune
```

unless intentionally resetting persistent data.

---

# 39. Python Environment

Activate:

```bash
source .venv/bin/activate
```

Check:

```bash
python --version
```

---

# 40. Spark S3A Packages

Validated package combination:

```text
org.apache.hadoop:hadoop-aws:3.3.4
com.amazonaws:aws-java-sdk-bundle:1.12.262
```

Common Spark configuration:

```text
--conf spark.driver.extraJavaOptions="-Divy.cache.dir=/tmp/.ivy2"
--conf spark.jars.ivy=/tmp/.ivy2
```

---

# 41. Deequ Packages

Validated Deequ configuration:

```text
org.apache.hadoop:hadoop-aws:3.3.4
com.amazon.deequ:deequ:3.0.3-spark-3.5
org.postgresql:postgresql:42.7.4
```

Excluded dependency:

```text
net.sourceforge.f2j:arpack_combined_all
```

---

# 42. MinIO Endpoint

Inside Docker containers:

```text
http://minio:9000
```

---

# 43. PostgreSQL Incident Database

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

---

# 44. Quick Incident Query

```sql
SELECT
    incident_id,
    incident_type,
    dataset_name,
    severity,
    status,
    detected_at,
    resolved_at
FROM incidents
ORDER BY incident_id;
```

---

# 45. Quick Recovery Audit Query

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

---

# 46. Active Recovery Worker Check

```sql
SELECT *
FROM recovery_attempts
WHERE status IN ('STARTED', 'RECOVERING');
```

Healthy final system state:

```text
0 rows
```

---

# 47. Project Integrity Checks

Check main project text files:

```bash
find incident_service spark failure_injection docs   -type f   \( -name '*.py' -o -name '*.md' -o -name '*.json'      -o -name '*.yaml' -o -name '*.yml' -o -name '*.sql'      -o -name '*.toml' -o -name '*.sh' -o -name '*.txt' \)   -exec file {} \;   | grep ': data$'
```

Expected:

```text
no output
```

Compile Python:

```bash
python -m compileall -q   incident_service   spark   failure_injection
```

Expected:

```text
no output
```

---

# 48. Known Design Tradeoff

The current schema restore uses:

```text
write temporary restore
↓
delete current Silver
↓
rename temporary restore
```

This is repeatable and convergent, but it is not a fully atomic distributed filesystem transaction.

A crash between delete and rename can temporarily leave the Silver path missing.

The platform mitigates this through:

```text
backup storage
pre-execution validation
replay protection
lease-based ownership
repeatable recovery
post-recovery validation
```

---

# 49. Future Enhancements

Potential future work includes:

```text
External fencing-token enforcement at the storage / execution layer
Multi-dataset automated recovery
More recovery action types
Automated pull-request remediation
Expanded Neo4j blast-radius analysis
Additional AI providers
Streaming incident detection
Recovery SLO dashboards
Kubernetes deployment
GCP / additional cloud execution adapters
```

---

# 50. What This Project Demonstrates

This project demonstrates practical experience with:

```text
Data ingestion
Streaming systems
Spark processing
Data quality
dbt transformations
Data lineage
Metadata systems
Graph-based dependency analysis
Incident management
AI-assisted root-cause analysis
Deterministic safety controls
Automated recovery
Distributed concurrency
Leases and heartbeats
Fencing
Replay protection
Auditability
Failure injection
Production hardening

Autonomous incident operations

Durable retry / backoff / requeue

FastAPI control-plane design

AWS managed recovery execution

Amazon ECS / Fargate deployment

Amazon RDS persistence

Terraform infrastructure as code

Remote Terraform state and IAM bootstrap separation

Terraform CI validation

CloudWatch logging and recovery metrics

Real autonomous cloud recovery

```

---

# 51. Final Status

```text
CORE DATA PIPELINE                  COMPLETE
DATA QUALITY                        COMPLETE
GOLD TRANSFORMATIONS                COMPLETE
LINEAGE / OBSERVABILITY             COMPLETE
INCIDENT DETECTION                  COMPLETE
LINEAGE-AWARE RCA                   COMPLETE
GEMINI RCA PROVIDER                 COMPLETE
DETERMINISTIC GUARDRAILS            COMPLETE
AUTOMATED RECOVERY                  COMPLETE
RECOVERY VALIDATION                 COMPLETE
CONCURRENCY HARDENING               COMPLETE
LEASE / HEARTBEAT                   COMPLETE
EXECUTION FENCING                   COMPLETE
PER-COMMAND FENCING                 COMPLETE
REPLAY PROTECTION                   COMPLETE
STRUCTURED AUDITING                 COMPLETE
FAILURE INJECTION                   COMPLETE
FULL REAL END-TO-END RECOVERY       COMPLETE

AUTONOMOUS INCIDENT OPERATIONS      COMPLETE

RETRY / BACKOFF / REQUEUE           COMPLETE

FASTAPI CONTROL PLANE               COMPLETE

METRICS / DASHBOARD                 COMPLETE

INTEGRATION / CHAOS TESTING         COMPLETE

CI/CD / DEPLOYMENT READINESS        COMPLETE

EXECUTION ADAPTER ABSTRACTION       COMPLETE

AWS S3 RECOVERY STORAGE             COMPLETE

AWS EMR SERVERLESS EXECUTION        COMPLETE

CLOUD SCHEMA VALIDATION             COMPLETE

CLOUD RUNTIME PROVENANCE            COMPLETE

REAL CLOUD ORCHESTRATED RECOVERY    COMPLETE

OPT-IN AWS INTEGRATION TEST         COMPLETE

AWS INFRASTRUCTURE AS CODE          COMPLETE

REMOTE TERRAFORM STATE              COMPLETE

IAM BOOTSTRAP SEPARATION            COMPLETE

ECS / FARGATE DEPLOYMENT            COMPLETE

APPLICATION LOAD BALANCER           COMPLETE

AMAZON RDS POSTGRESQL               COMPLETE

AMAZON ECR                          COMPLETE

AWS SECRETS MANAGER                 COMPLETE

AUTONOMOUS CLOUD WORKER             COMPLETE

CLOUD FASTAPI CONTROL PLANE         COMPLETE

TERRAFORM CI VALIDATION             COMPLETE

CLOUDWATCH LOG INTEGRATION          COMPLETE

CLOUDWATCH RECOVERY METRICS         COMPLETE

REAL AUTONOMOUS CLOUD E2E           COMPLETE

FINAL ARCHITECTURE / DOCUMENTATION  IN PROGRESS

PORTFOLIO / DEMO PACKAGING          PENDING
```

**CURRENT PLATFORM STATUS — PHASE 5F COMPLETE / PHASE 5G IN PROGRESS**

---

# 52. Phase 4 — Platformization & Autonomous Operations

Phase 4 converts the hardened Phase 3 recovery engine into an autonomous operational platform.

Phase 4A adds an autonomous incident worker around the existing Phase 3 recovery orchestrator.

Candidate selection requires:

- status = OPEN
- automation_eligible = true
- no previous recovery_attempt

This provides at-most-once autonomous dispatch in Phase 4A. Retry, backoff, and requeue are deferred to Phase 4B.

Real Phase 4A validation:

- Incident 10 → OPEN; Recovery Attempt 27 → RCA_FAILED
- Incident 11 → RESOLVED; Recovery Attempt 28 → COMPLETED
- Recovery action → RESTORE_SCHEMA_DRIFT_BACKUP
- Final Silver → healthy, 15 columns, 0 remaining detections

Detailed documentation: `docs/phase_4_platformization.md`

**PHASE 4A — COMPLETE**

### Phase 4 Platformization Status

- Phase 4A — Autonomous Incident Worker: COMPLETE
- Phase 4B — Retry / Backoff / Requeue: COMPLETE
- Phase 4C — FastAPI Control Plane: COMPLETE
- Phase 4D — Metrics / Dashboard: COMPLETE
- Phase 4E — Integration / Chaos Testing: COMPLETE
- Phase 4F — CI/CD / Deployment Readiness: COMPLETE

Current default regression baseline: **67 passed, 1 skipped**. The skipped test is the explicitly opt-in real AWS integration test.

The API provides `/health`, `/ready`, `/metrics/summary`, `/metrics`, and `/dashboard`.

The autonomous worker is isolated behind the `automation` Compose profile and defaults to `INCIDENT_WORKER_DRY_RUN=true`.

Detailed Phase 4 documentation: `docs/phase_4_platformization.md`
---

# 53. Phase 5 — Cloud-Native Recovery Execution

Phase 5 moves recovery execution from a local-only Docker runtime to a provider-neutral model that supports both local and managed-cloud execution without changing the deterministic recovery policy or incident lifecycle.

## Phase 5A — Execution Adapter Abstraction

Phase 5A introduced a provider-neutral execution contract with three semantic operations:

```text
STAGE_FILE
RUN_SPARK_SCRIPT
FETCH_FILE
```

Supported execution backends:

```text
local-docker
emr-serverless
```

The default remains `local-docker`, preserving the existing Spark + MinIO development path.

**PHASE 5A — COMPLETE**

## Phase 5B — AWS EMR Serverless + Amazon S3

Phase 5B adds a real managed-cloud recovery path using Amazon EMR Serverless, Amazon S3, IAM runtime roles, boto3, Spark, and Parquet.

Supported storage backends:

```text
minio
aws-s3
```

The same schema-drift recovery workflow can therefore run against either:

```text
Local:  Docker + Spark + MinIO
Cloud:  EMR Serverless + Amazon S3
```

### Real Full-Cloud Recovery Proof

A real schema-drift incident was executed through the complete production orchestration path:

```text
Incident ID:             302
Incident Type:           SCHEMA_DRIFT
Initial Status:          OPEN
Recovery Attempt:        201
RCA Provider:            Gemini
Recovery Action:         RESTORE_SCHEMA_DRIFT_BACKUP
Execution Backend:       emr-serverless
Storage Backend:         aws-s3
Recovery Job Run:        00gac3r7sh9vk80b
Execution Status:        COMPLETED
Post-Recovery Healthy:   True
Recovery Needed:         False
Final Schema Columns:    15
Final Incident Status:   RESOLVED
```

The deterministic policy authorized recovery only after runtime provenance proved that the unexpected schema column came from the controlled failure-injection execution.

### Automated Real-AWS Integration Test

The project includes an explicitly opt-in cloud integration test:

```text
tests/integration/test_aws_cloud_recovery.py
```

It is protected by both the `aws_integration` pytest marker and the `RUN_AWS_INTEGRATION_TESTS=1` environment guard, so normal pytest execution does not launch paid AWS resources.

Default regression baseline:

```text
67 passed, 1 skipped
```

Explicit AWS validation result:

```text
1 passed in 421.31s
```

The automated AWS test validates real EMR Serverless schema-drift injection, S3 provenance persistence, cloud schema capture, incident creation, runtime-provenance correlation, and fail-safe restoration of the healthy Silver dataset.

After cleanup, live Silver matched the known-good backup exactly:

```text
Live Silver:     2 objects, 4622 bytes
Healthy Backup:  2 objects, 4622 bytes
```

### Automated AWS Job Evidence

```text
incident-recovery-inject_schema_drift
State: SUCCESS
Execution: 111 seconds
Billed vCPUHour: 0.049
Billed memoryGBHour: 0.243

incident-recovery-capture_silver_schema
State: SUCCESS
Execution: 86 seconds
Billed vCPUHour: 0.041
Billed memoryGBHour: 0.204
```

Combined billed compute for that integration execution:

```text
vCPUHour:      0.090
memoryGBHour:  0.447
storageGBHour: 0.0
```

### Production Storage Note

The current S3 restore uses Hadoop filesystem rename semantics. On Amazon S3, rename is implemented as copy plus delete rather than as an atomic filesystem rename. A production-scale evolution could use versioned dataset pointers, manifest-based publication, or table formats such as Apache Iceberg, Delta Lake, or Hudi for stronger publication guarantees.

**PHASE 5B — COMPLETE**

## Phase 5C — AWS Infrastructure as Code with Terraform

Phase 5C codifies the AWS recovery infrastructure in Terraform so the managed-cloud recovery path is reproducible, reviewable, and protected from configuration drift.

Terraform now manages the existing Phase 5B infrastructure:

```text
Amazon S3 recovery bucket
S3 versioning configuration
S3 server-side encryption
S3 public access block
Amazon EMR Serverless application
EMR Serverless IAM runtime role
Runtime-role S3 access policy
```

The existing AWS resources were imported into Terraform rather than recreated.

Final infrastructure convergence:

```text
No changes. Your infrastructure matches the configuration.
```

Safety and reproducibility controls include:

```text
prevent_destroy on the recovery S3 bucket
prevent_destroy on the EMR Serverless application
prevent_destroy on the EMR runtime IAM role
Terraform state stored in a dedicated versioned S3 backend
Native S3 lockfile locking enabled with use_lockfile = true
Terraform state excluded from Git
Terraform provider lockfile retained
Dedicated Terraform provisioning role
```

The IAM trust policy derives the AWS account ID through `aws_caller_identity` instead of hard-coding it.

Terraform also exposes the non-secret runtime configuration required by the recovery service:

```text
AWS_REGION
RECOVERY_EXECUTION_BACKEND
RECOVERY_STORAGE_BACKEND
EMR_SERVERLESS_APPLICATION_ID
EMR_SERVERLESS_EXECUTION_ROLE_ARN
EMR_SERVERLESS_ARTIFACT_BUCKET
EMR_SERVERLESS_ARTIFACT_PREFIX
```

The helper:

```text
infrastructure/terraform/aws/render_env.py
```

converts those Terraform outputs into `.env`-style configuration without storing AWS credentials or application secrets.

Terraform state is stored remotely in the dedicated backend bucket `incident-recovery-tfstate-275956876816-us-east-1` under `phase5c/terraform.tfstate`. The backend bucket has versioning enabled, AES256 server-side encryption, all four S3 public-access protections enabled, and native S3 state locking via `use_lockfile = true`. The backend bucket is bootstrapped separately so Terraform can use it before managing the application infrastructure.

### Bootstrap and IAM Cleanup

The bootstrap layer is codified separately under `infrastructure/terraform/bootstrap/` so the application Terraform stack does not manage the IAM role it depends on for provisioning.

The bootstrap stack manages:

```text
IncidentRecoveryBootstrap IAM user
AssumeIncidentRecoveryProvisioner inline policy
SignInLocalDevelopmentAccess managed-policy attachment
IncidentRecoveryProvisioner IAM role
IncidentRecoveryProvisionerPolicy
Terraform-state S3 bucket
State-bucket versioning
State-bucket encryption
State-bucket public-access block
```

Normal infrastructure operations use:

```text
IncidentRecoveryBootstrap
        ↓ sts:AssumeRole
IncidentRecoveryProvisioner
        ↓
Application Terraform / AWS infrastructure
```

The bootstrap stack itself is break-glass/admin-only because it manages the bootstrap identity and provisioner role. Root credentials are not required for normal application Terraform operations.

Bootstrap state is stored separately in the same protected S3 backend under:

```text
bootstrap/terraform.tfstate
```

Both the application stack and bootstrap stack were validated at zero drift after migration to remote state.

Terraform source layout:

```text

infrastructure/terraform/
├── aws/
│   ├── versions.tf
│   ├── backend.tf
│   ├── main.tf
│   ├── variables.tf
│   ├── s3.tf
│   ├── emr.tf
│   ├── iam.tf
│   ├── outputs.tf
│   ├── render_env.py
│   └── .terraform.lock.hcl
└── bootstrap/
    ├── versions.tf
    ├── backend.tf
    ├── main.tf
    ├── variables.tf
    ├── iam.tf
    ├── provisioner_policy.tf
    ├── state_bucket.tf
    └── .terraform.lock.hcl

```

**PHASE 5C — AWS INFRASTRUCTURE AS CODE IMPLEMENTED**

## Phase 5D — Cloud Control Plane Deployment

Phase 5D deploys the Phase 4 control plane and autonomous worker into AWS without changing the existing recovery authority model.

The deployed environment includes:

```text
Application Load Balancer
↓
ECS / Fargate FastAPI control plane
↓
Amazon RDS PostgreSQL 16
↑
ECS / Fargate autonomous recovery worker
```

Container images are stored in Amazon ECR. Application secrets are supplied through AWS Secrets Manager.

The cloud worker continues to use the durable Phase 4 recovery queue and the hardened Phase 3 recovery orchestrator.

### Real Autonomous AWS End-to-End Proof

```text
Incident ID:                 1
Incident Type:               SCHEMA_DRIFT
Recovery Attempt:            4
Recovery Action:             RESTORE_SCHEMA_DRIFT_BACKUP
Automatic Execution:         true
Execution Backend:           emr-serverless
Storage Backend:             aws-s3
Recovery Status:             COMPLETED
Post-Validation Healthy:     true
Recovery Needed:             false
Final Schema Columns:        15
Remaining Detections:        none
Final Incident Status:       RESOLVED
```

Recovery EMR job: `00gadjh5i3f6u00b`

Post-validation schema-capture EMR job: `00gadjimkab5d80b`

Final recovery queue state: `COMPLETED`.

**PHASE 5D — CLOUD CONTROL PLANE DEPLOYMENT COMPLETE**

## Phase 5E — Terraform CI/CD Checks

Phase 5E adds Terraform static validation to the existing GitHub Actions workflow.

Both Terraform stacks are checked using:

```text
terraform fmt -check
terraform init -backend=false -lockfile=readonly
terraform validate
```

The CI workflow intentionally does not perform `terraform plan`, `terraform apply`, or AWS deployment.

**PHASE 5E — TERRAFORM CI/CD CHECKS COMPLETE**

## Phase 5F — AWS Observability Hardening

Phase 5F adds AWS-native recovery visibility around the deployed ECS worker.

CloudWatch log groups:

```text
/ecs/ai-data-pipeline-incident-recovery-dev/api
/ecs/ai-data-pipeline-incident-recovery-dev/worker
/ecs/ai-data-pipeline-incident-recovery-dev/migration
```

Log retention: `14 days`.

CloudWatch metric namespace: `IncidentRecovery/dev`.

Configured recovery metrics:

```text
RecoveryResolvedCount
RCAFailedCount
PolicyFailedCount
ExecutionFailedCount
ValidationErrorCount
ValidationFailedCount
WorkerErrorCount
ClaimLostCount
```

The metric filters were deployed through Terraform and verified live in AWS.

**PHASE 5F — AWS OBSERVABILITY HARDENING COMPLETE**

## Phase 5G — Final Architecture / Documentation

Detailed Phase 5 documentation:

```text
docs/phase_5_cloud_deployment.md
```

**PHASE 5G — COMPLETE**
