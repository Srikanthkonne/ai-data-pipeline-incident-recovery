import json

from incident_service.rca.diagnostics import (
    runtime_provenance,
)


PROVENANCE_URI = (
    "s3://example-bucket/"
    "failure-injections/"
    "schema_drift_cloud-test.json"
)


class FakeBody:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(
            self.payload
        ).encode("utf-8")


class FakeS3Client:
    def __init__(self, payload):
        self.payload = payload

    def get_object(
        self,
        *,
        Bucket,
        Key,
    ):
        assert Bucket == "example-bucket"
        assert Key == (
            "failure-injections/"
            "schema_drift_cloud-test.json"
        )

        return {
            "Body": FakeBody(
                self.payload
            )
        }


def test_runtime_provenance_can_load_s3_evidence(
    monkeypatch,
    tmp_path,
):
    observed_schema = {
        f"column_{index}": "string"
        for index in range(15)
    }

    observed_schema[
        "cloud_worker_test_column"
    ] = "string"

    incident = {
        "incident_id": 9001,
        "incident_type": "SCHEMA_DRIFT",
        "metadata": {
            "captured_at":
                "2026-11-18T17:00:05+00:00",
            "dataset_name":
                "silver/transactions",
            "source_path": (
                "s3://example-bucket/"
                "silver/transactions"
            ),
            "observed_schema":
                observed_schema,
            "detections": [
                {
                    "drift_type":
                        "UNEXPECTED_COLUMN",
                    "column_name":
                        "cloud_worker_test_column",
                }
            ],
            "runtime_provenance_uri":
                PROVENANCE_URI,
        },
    }

    provenance = {
        "execution_id":
            "cloud-test",
        "scenario":
            "SCHEMA_DRIFT",
        "status":
            "COMPLETED",
        "target_dataset":
            "silver/transactions",
        "target_path": (
            "s3://example-bucket/"
            "silver/transactions"
        ),
        "injected_column":
            "cloud_worker_test_column",
        "injected_value":
            "CLOUD_WORKER_TEST",
        "columns_before":
            15,
        "columns_after":
            16,
        "started_at":
            "2026-11-18T16:59:55+00:00",
        "completed_at":
            "2026-11-18T17:00:00+00:00",
    }

    monkeypatch.setattr(
        runtime_provenance,
        "get_incident",
        lambda incident_id: incident,
    )

    monkeypatch.setattr(
        runtime_provenance,
        "PROVENANCE_DIR",
        tmp_path,
    )

    monkeypatch.setattr(
        runtime_provenance.boto3,
        "client",
        lambda service: FakeS3Client(
            provenance
        ),
    )

    result = (
        runtime_provenance
        .diagnose_runtime_provenance(
            incident_id=9001
        )
    )

    assert (
        result["runtime_execution_proven"]
        is True
    )

    assert (
        result["causal_evidence_eligible"]
        is True
    )

    assert result["execution_id"] == (
        "cloud-test"
    )

    assert result["provenance_file"] == (
        PROVENANCE_URI
    )
