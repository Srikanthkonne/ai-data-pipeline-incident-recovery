import json
from pathlib import Path

from metadata.repository.schema_snapshots import (
    record_schema_snapshot,
)


DEFAULT_EVIDENCE_PATH = Path(
    "spark/evidence/silver_schema.json"
)


def main():
    with DEFAULT_EVIDENCE_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        evidence = json.load(file)

    snapshot = record_schema_snapshot(
        namespace=evidence["namespace"],
        name=evidence["name"],
        schema=evidence["schema"],
    )

    print("Schema snapshot recorded:")
    print(f"Snapshot ID: {snapshot['id']}")
    print(
        f"Observation count: "
        f"{snapshot['observation_count']}"
    )
    print(
        f"Schema hash: "
        f"{snapshot['schema_hash']}"
    )


if __name__ == "__main__":
    main()
