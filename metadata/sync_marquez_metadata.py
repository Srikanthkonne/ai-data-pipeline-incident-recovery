import os
from datetime import datetime
from urllib.parse import quote

import requests

from metadata.repository.datasets import (
    sync_dataset_technical_metadata,
)
from metadata.repository.jobs import (
    sync_job_technical_metadata,
)
from metadata.repository.pipeline_runs import (
    upsert_pipeline_run,
)


MARQUEZ_URL = os.getenv(
    "MARQUEZ_URL",
    "http://localhost:5000",
).rstrip("/")

MARQUEZ_NAMESPACE = os.getenv(
    "MARQUEZ_NAMESPACE",
    "incident-platform",
)


def fetch_marquez_jobs():
    namespace = quote(
        MARQUEZ_NAMESPACE,
        safe="",
    )

    url = (
        f"{MARQUEZ_URL}/api/v1/namespaces/"
        f"{namespace}/jobs"
    )

    response = requests.get(
        url,
        timeout=15,
    )
    response.raise_for_status()

    return response.json().get("jobs", [])


def infer_dataset_layer(dataset_name):
    if not dataset_name:
        return None

    first_part = dataset_name.split("/", 1)[0].upper()

    if first_part in {
        "BRONZE",
        "SILVER",
        "GOLD",
    }:
        return first_part

    return None


def parse_marquez_timestamp(value):
    if not value:
        return None

    parsed = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    # PostgreSQL metadata columns currently use
    # TIMESTAMP WITHOUT TIME ZONE.
    # Marquez timestamps are UTC, so store the
    # equivalent naive UTC datetime.
    return parsed.replace(tzinfo=None)


def sync_dataset(dataset):
    namespace = dataset.get("namespace")
    name = dataset.get("name")

    if not namespace or not name:
        return None

    layer = infer_dataset_layer(name)

    return sync_dataset_technical_metadata(
        namespace=namespace,
        name=name,
        layer=layer,
    )


def sync_job(job):
    inputs = job.get("inputs") or []
    outputs = job.get("outputs") or []

    # Match the Neo4j sync behavior:
    # keep only complete dataset transformations.
    if not inputs or not outputs:
        return False

    job_namespace = job["namespace"]
    job_name = job["name"]

    sync_job_technical_metadata(
        namespace=job_namespace,
        name=job_name,
        job_type=job.get("type"),
    )

    for dataset in inputs:
        sync_dataset(dataset)

    for dataset in outputs:
        sync_dataset(dataset)

    latest_run = job.get("latestRun") or {}

    run_id = latest_run.get("id")

    if run_id:
        upsert_pipeline_run(
            job_namespace=job_namespace,
            job_name=job_name,
            run_id=run_id,
            status=latest_run.get("state", "UNKNOWN"),
            started_at=parse_marquez_timestamp(
                latest_run.get("startedAt")
            ),
            ended_at=parse_marquez_timestamp(
                latest_run.get("endedAt")
            ),
            duration_ms=latest_run.get("durationMs"),
        )

    return True


def main():
    jobs = fetch_marquez_jobs()

    print(
        f"Fetched {len(jobs)} jobs from Marquez"
    )

    synchronized = 0

    for job in jobs:
        if sync_job(job):
            synchronized += 1
            print(
                f"Synced metadata: {job['name']}"
            )
        else:
            print(
                "Skipped incomplete lineage job: "
                f"{job['name']}"
            )

    print(
        "Metadata jobs synchronized: "
        f"{synchronized}"
    )


if __name__ == "__main__":
    main()
