import os
from urllib.parse import quote

import requests
from neo4j import GraphDatabase


MARQUEZ_URL = os.getenv("MARQUEZ_URL", "http://localhost:5000").rstrip("/")
MARQUEZ_NAMESPACE = os.getenv("MARQUEZ_NAMESPACE", "incident-platform")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


def fetch_marquez_jobs():
    namespace = quote(MARQUEZ_NAMESPACE, safe="")

    url = (
        f"{MARQUEZ_URL}/api/v1/namespaces/"
        f"{namespace}/jobs"
    )

    response = requests.get(url, timeout=15)
    response.raise_for_status()

    return response.json().get("jobs", [])


def sync_job(tx, job):
    inputs = job.get("inputs") or []
    outputs = job.get("outputs") or []

    # Keep only complete dataset transformations.
    # This avoids Spark internal jobs that expose only an input
    # or only an output and would add noise to the lineage graph.
    if not inputs or not outputs:
        return False

    job_namespace = job["namespace"]
    job_name = job["name"]

    latest_run = job.get("latestRun") or {}

    tx.run(
        """
        MERGE (j:Job {
            namespace: $namespace,
            name: $name
        })
        SET
            j.type = $type,
            j.latest_run_state = $latest_run_state,
            j.updated_at = $updated_at
        """,
        namespace=job_namespace,
        name=job_name,
        type=job.get("type"),
        latest_run_state=latest_run.get("state"),
        updated_at=job.get("updatedAt"),
    )

    for dataset in inputs:
        tx.run(
            """
            MERGE (d:Dataset {
                namespace: $dataset_namespace,
                name: $dataset_name
            })
            MERGE (j:Job {
                namespace: $job_namespace,
                name: $job_name
            })
            MERGE (d)-[:INPUT_TO]->(j)
            """,
            dataset_namespace=dataset["namespace"],
            dataset_name=dataset["name"],
            job_namespace=job_namespace,
            job_name=job_name,
        )

    for dataset in outputs:
        tx.run(
            """
            MERGE (j:Job {
                namespace: $job_namespace,
                name: $job_name
            })
            MERGE (d:Dataset {
                namespace: $dataset_namespace,
                name: $dataset_name
            })
            MERGE (j)-[:OUTPUTS]->(d)
            """,
            job_namespace=job_namespace,
            job_name=job_name,
            dataset_namespace=dataset["namespace"],
            dataset_name=dataset["name"],
        )

    return True


def main():
    if not NEO4J_PASSWORD:
        raise RuntimeError(
            "NEO4J_PASSWORD is not set. "
            "Load the project .env before running the sync."
        )

    jobs = fetch_marquez_jobs()

    print(f"Fetched {len(jobs)} jobs from Marquez")

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
    )

    synced = 0

    try:
        driver.verify_connectivity()

        with driver.session() as session:
            for job in jobs:
                was_synced = session.execute_write(sync_job, job)

                if was_synced:
                    synced += 1
                    print(f"Synced: {job['name']}")
                else:
                    print(
                        "Skipped incomplete lineage job: "
                        f"{job['name']}"
                    )

    finally:
        driver.close()

    print(f"Lineage jobs synchronized: {synced}")


if __name__ == "__main__":
    main()
