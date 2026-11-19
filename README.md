# Lineage-Aware Autonomous Data Pipeline Incident Detection & Recovery Platform

An AI-assisted data reliability platform that detects data pipeline failures, performs lineage- and runtime-provenance-aware root-cause analysis, executes guarded autonomous recovery using deterministic controls, and provides operational visibility through APIs, metrics, dashboards, audit records, and cloud observability.

The platform combines streaming data engineering, data quality, lineage, incident management, AI-assisted investigation, automated recovery, validation, observability, and AWS cloud execution into a single end-to-end system.

---

## Overview

This project implements an end-to-end data pipeline incident detection and recovery platform.

It brings together the components required to move from detecting a data problem to safely resolving it:

- detect and track supported pipeline incidents
- collect lineage, schema, and runtime evidence
- perform AI-assisted root-cause analysis
- validate RCA conclusions against deterministic evidence
- authorize recovery through explicit policy
- execute allowlisted recovery actions
- validate the recovered system state before resolution
- expose incident and recovery state through APIs, metrics, dashboards, and audit records

The result is a single operational workflow for **detection, diagnosis, recovery, validation, and monitoring** rather than a collection of disconnected remediation scripts.

---

## Problem Statement

Data pipelines can fail because of schema changes, data-quality issues, SLA violations, missing datasets, or upstream processing problems.

Monitoring systems can usually tell an engineer that something failed. They do not necessarily answer:

- what changed
- what caused the failure
- which data assets are affected
- whether the proposed remediation is safe
- whether recovery has already occurred
- whether the recovered state is actually healthy

That evidence is often distributed across quality results, lineage systems, runtime metadata, application state, and logs. Diagnosis and remediation therefore require manual investigation and coordination across multiple tools.

This project addresses that operational gap by connecting the incident lifecycle into one controlled workflow:

**Detection → Diagnosis → Decision → Recovery → Validation → Resolution**

Operational visibility spans the full lifecycle through APIs, metrics, dashboard views, audit records, and cloud telemetry.

---

## System Architecture

```text
Transaction Generator
        ↓
      Kafka
        ↓
 Bronze Storage
   S3 / MinIO
        ↓
 Apache Spark
        ↓
     Silver
        ↓
 Data Quality
    Deequ
        ↓
   Gold / dbt
        ↓
Lineage & Metadata
OpenLineage / Marquez
        ↓
 Neo4j Lineage Graph
        ↓
 Incident Detection
        ↓
 Incident Service
        ↓
Runtime Provenance
        ↓
Normalized RCA Facts
        ↓
AI-Assisted RCA
 Google Gemini
        ↓
Deterministic Guardrails
        ↓
 Recovery Policy
        ↓
Ownership / Lease / Fencing
        ↓
Allowlisted Recovery Execution
        ↓
Post-Recovery Validation
        ↓
Incident Resolution
```

**Cross-cutting operational visibility**

```text
FastAPI Control Plane
        +
Monitoring Dashboard
        +
Application Metrics
        +
Recovery Audit Records
        +
Amazon CloudWatch
```

The recovery layer is execution-backend independent. The same orchestration model can execute locally or through AWS-managed services.

The cloud implementation uses services including:

- Amazon ECS / AWS Fargate
- Amazon RDS PostgreSQL
- Amazon S3
- Amazon EMR Serverless
- Amazon ECR
- AWS Secrets Manager
- AWS IAM
- Amazon CloudWatch
- Terraform

---

## Design Principles

### AI-Assisted Reasoning, Deterministic Recovery Control

AI is used to interpret incident evidence and assist with root-cause analysis.

Recovery authority remains governed by deterministic evidence, explicit policy, allowlisted actions, ownership controls, and post-recovery validation.

The AI component does not receive unrestricted authority to execute infrastructure-changing commands.

AI conclusions are evaluated against evidence such as:

- observed pipeline state
- runtime provenance
- schema evidence
- lineage context
- incident metadata

If AI output conflicts with deterministic evidence, the deterministic evidence takes precedence.

### Explicit and Allowlisted Recovery

Recovery actions are selected through explicit policy rather than free-form AI-generated commands.

Only supported actions can reach the execution layer.

### Validation Before Resolution

Successful execution does not automatically mean successful recovery.

The resulting data state must independently pass validation before the incident can be resolved.

### Failure-Tolerant Recovery

The recovery workflow is designed to tolerate interrupted or concurrent workers through ownership, leases, heartbeats, fencing, replay protection, retries, and durable state.

### Observable Operations

Incident state, recovery attempts, validation outcomes, failures, and recovery metrics remain visible through application and cloud observability interfaces.

---

## Technology Stack

| Area | Technologies |
|---|---|
| Streaming & Ingestion | Apache Kafka |
| Data Processing | Apache Spark, PySpark |
| Storage | Amazon S3, MinIO |
| Data Quality | Amazon Deequ |
| Transformations | dbt, DuckDB |
| Orchestration | Apache Airflow |
| Metadata & Lineage | OpenLineage, Marquez, Neo4j |
| Incident Platform | Python, PostgreSQL |
| AI-Assisted RCA | Google Gemini |
| API | FastAPI |
| Monitoring & Metrics | Operational Dashboard, application metrics |
| Containerization | Docker, Docker Compose |
| Cloud Platform | AWS |
| Cloud Compute | ECS/Fargate, EMR Serverless |
| Cloud Database | Amazon RDS PostgreSQL |
| Infrastructure as Code | Terraform |
| Secrets & Access Control | AWS Secrets Manager, AWS IAM |
| Cloud Observability | Amazon CloudWatch |
| CI | GitHub Actions |

---

## System Workflow

### Incident Detection

Pipeline and data-quality signals are evaluated and converted into incidents when supported failure conditions are detected.

Supported incident categories include:

- `NULL_SPIKE`
- `SCHEMA_DRIFT`
- `SLA_BREACH`

Schema drift is the primary autonomous-recovery scenario validated end to end.

### AI-Assisted Root Cause Analysis

The RCA layer combines:

- incident metadata
- observed dataset state
- runtime provenance
- lineage context
- normalized RCA facts

These facts are provided to the AI investigator for structured root-cause analysis.

The AI provider is abstracted behind a provider-neutral contract so the incident and recovery workflow is not tightly coupled to one LLM implementation.

### Lineage & Runtime Provenance

OpenLineage and Marquez capture pipeline lineage.

Neo4j provides graph-based dependency information used during diagnosis.

Runtime provenance records deterministic evidence describing relevant changes observed during pipeline execution or controlled failure scenarios.

Together, lineage and runtime provenance provide context for diagnosis and recovery decisions.

### Deterministic Decision Guardrails

AI-generated conclusions are checked against observed evidence before they can influence recovery.

For example, a schema-drift diagnosis can be validated by comparing:

```text
Observed unexpected column
        =
Runtime provenance column
        =
RCA causal column
```

If those facts do not align, autonomous recovery is rejected.

### Operational Monitoring

The platform exposes incident and recovery state through the control-plane API and monitoring interfaces.

Operational visibility includes:

- incident lifecycle state
- recovery attempt state
- validation outcomes
- recovery failure categories
- worker activity
- recovery metrics
- AWS CloudWatch recovery signals

---

## Recovery Architecture

### Recovery Policy

The recovery policy maps normalized and validated RCA facts to explicit recovery actions.

For validated schema drift, the supported recovery action is:

```text
RESTORE_SCHEMA_DRIFT_BACKUP
```

AI confidence alone cannot authorize recovery.

### Recovery Execution

The executor accepts only allowlisted recovery operations.

A schema-drift recovery follows the general flow:

```text
Known-good backup
        ↓
Temporary restore
        ↓
Replace unhealthy Silver dataset
        ↓
Validate restored dataset
```

Execution can use either the local recovery backend or AWS EMR Serverless depending on configuration.

### Recovery Validation

Recovery is followed by an independent validation step.

For the validated schema-drift scenario, a healthy result includes conditions such as:

```text
dataset_exists = true
capture_status = CAPTURED
healthy = true
recovery_needed = false
remaining_detections = []
schema_column_count = expected
```

The incident is resolved only after validation succeeds.

---

## Reliability & Safety

The recovery engine uses multiple independent controls rather than relying on a single safeguard.

### Ownership & Leases

Only one active recovery attempt can own an incident at a time.

Workers maintain ownership through durable lease and heartbeat state.

Expired ownership can be reclaimed safely.

### Fencing & Replay Protection

A worker must prove that it still owns the recovery attempt before destructive execution continues.

Before performing recovery, the platform also checks whether the target state is already healthy.

If recovery has already occurred, duplicate execution is skipped.

### Validation & Auditability

RCA results, policy decisions, recovery execution, validation results, errors, timestamps, and state transitions are persisted for later inspection.

This creates a durable record of how an incident moved from detection to resolution.

---

## Key Design Decisions

### Why AI Assists RCA Instead of Controlling Recovery

AI is useful for interpreting multiple pieces of incident context and producing a structured diagnosis.

Allowing an LLM to directly generate and execute arbitrary remediation commands would introduce unnecessary operational risk.

The platform therefore uses AI for diagnosis while retaining deterministic control over recovery authorization and execution.

### Why Lineage and Runtime Provenance Are Used Together

Lineage answers questions about **dependency relationships**.

Runtime provenance provides evidence about **what changed during execution**.

Using both gives the RCA layer stronger context than relying on logs or an LLM prompt alone.

### Why Recovery Execution Is Abstracted

Recovery orchestration is separated from the underlying execution backend.

This allows the same incident and policy workflow to use local execution during development and AWS EMR Serverless for cloud recovery.

### Why Validation Is Independent of Execution

A command completing successfully does not guarantee that the data platform is healthy.

Separating recovery execution from post-recovery validation prevents an incident from being resolved solely because a remediation command returned successfully.

---

## Platform Outputs

For a supported incident, the platform can produce:

- a persisted incident record
- structured root-cause analysis
- lineage and runtime-provenance context
- an explicit recovery-policy decision
- recovery execution evidence
- post-recovery validation results
- durable recovery and incident audit history
- API and dashboard visibility into incident state
- operational recovery metrics
- final resolution state after successful validation

These outputs make the incident lifecycle inspectable rather than hiding recovery behind a background automation process.

---

## AWS End-to-End Validation

The final cloud validation demonstrated autonomous schema-drift recovery using the deployed AWS control plane and autonomous recovery worker.

```text
Incident Type:          SCHEMA_DRIFT
Recovery Action:        RESTORE_SCHEMA_DRIFT_BACKUP
Execution Backend:      EMR Serverless
Storage Backend:        Amazon S3
Recovery Status:        COMPLETED
Post-Validation:        Healthy
Recovery Needed:        false
Remaining Detections:   none
Final Incident Status:  RESOLVED
```

The validated cloud recovery path was:

```text
Incident
   ↓
Autonomous Recovery Worker
   ↓
RCA + Runtime Provenance
   ↓
Deterministic Policy
   ↓
EMR Serverless Recovery
   ↓
Amazon S3
   ↓
Post-Recovery Validation
   ↓
RESOLVED
```

Amazon CloudWatch recovery metrics provide observability across the cloud recovery workflow.

This validation demonstrates that the recovery workflow operates beyond the local Docker environment using AWS-managed execution and storage.

---

## Repository Structure

```text
.
├── airflow/             Airflow DAGs and orchestration
├── api/                 FastAPI control plane
├── dashboard/           Operational monitoring dashboard
├── data_generator/      Synthetic transaction generation
├── dbt/                 Analytics transformations
├── docs/                Detailed technical documentation
├── failure_injection/   Controlled failure scenarios
├── incident_service/    Incident detection, RCA, policy, recovery, and worker logic
├── infrastructure/      Terraform and AWS infrastructure
├── kafka/               Kafka configuration
├── lineage/             Neo4j lineage integration
├── marquez/             OpenLineage / Marquez configuration
├── metadata/            Metadata persistence
├── scripts/             Utility and operational scripts
├── spark/               Spark processing and validation jobs
├── tests/               Unit and integration tests
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Getting Started

### Prerequisites

For local execution:

- Git
- Python 3.14
- Docker with Docker Compose

For AWS infrastructure and cloud deployment workflows:

- Terraform 1.6+
- AWS CLI

### Clone the Repository

```bash
git clone https://github.com/Srikanthkonne/lineage-aware-autonomous-data-recovery.git
cd lineage-aware-autonomous-data-recovery
```

### Configure Environment

Create a local environment file from the provided template:

```bash
cp .env.example .env
```

Update the required local configuration and credentials.

Do not commit `.env`.

### Install Dependencies

Create and activate a virtual environment:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
```

Install the project dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Verify the environment:

```bash
python -m pip check
```

### Start the Platform

Start the local services:

```bash
docker compose up -d
```

Check service state:

```bash
docker compose ps
```

### Stop the Platform

```bash
docker compose stop
```

---

## Testing

The repository includes:

- unit tests
- integration tests
- failure-injection testing
- recovery validation
- AWS integration validation
- Terraform CI validation

Run the Python test suite with:

```bash
pytest
```

Detailed failure-injection and production-hardening evidence is maintained under `docs/`.

---

## AWS Deployment

The deployed cloud control plane follows this general architecture:

```text
Application Load Balancer
        ↓
Amazon ECS / AWS Fargate
        ↓
FastAPI Control Plane
        +
Autonomous Recovery Worker
        ↓
Amazon RDS PostgreSQL
        ↓
Amazon EMR Serverless
        ↓
Amazon S3
```

Operational visibility is provided through:

- FastAPI incident and recovery endpoints
- application recovery metrics
- monitoring dashboard views
- Amazon CloudWatch logs
- CloudWatch recovery metric filters

Supporting infrastructure includes:

- Amazon ECR
- AWS IAM
- AWS Secrets Manager
- Terraform remote state

Infrastructure is managed through Terraform with separate bootstrap and application-level authority.

See [`docs/phase_5_cloud_deployment.md`](docs/phase_5_cloud_deployment.md) for the detailed AWS architecture, IAM model, recovery execution flow, CI validation, and observability design.

---

## Known Tradeoffs

The current schema-restore workflow uses a temporary restore followed by replacement of the unhealthy Silver dataset.

The operation is repeatable and convergent, but the replacement is not equivalent to a fully atomic distributed-filesystem transaction.

The design mitigates this limitation through:

- known-good backup storage
- pre-execution validation
- lease-based ownership
- execution fencing
- replay protection
- repeatable recovery
- post-recovery validation

This tradeoff is intentionally documented rather than hidden behind the automation layer.

---

## Documentation

Detailed implementation and operational documentation is maintained separately from the README:

- [`docs/phase_3_incident_recovery.md`](docs/phase_3_incident_recovery.md) — incident detection, RCA, recovery, and validation
- [`docs/recovery_architecture.md`](docs/recovery_architecture.md) — recovery ownership, leases, fencing, replay protection, and recovery architecture
- [`docs/production_hardening.md`](docs/production_hardening.md) — production-hardening controls
- [`docs/failure_injection_testing.md`](docs/failure_injection_testing.md) — controlled failure scenarios and regression evidence
- [`docs/phase_4_platformization.md`](docs/phase_4_platformization.md) — autonomous worker, API, monitoring, and control-plane platformization
- [`docs/phase_5_cloud_deployment.md`](docs/phase_5_cloud_deployment.md) — AWS architecture, Terraform/IAM model, cloud recovery, CI, and observability
- [`docs/troubleshooting.md`](docs/troubleshooting.md) — implementation and operational troubleshooting
