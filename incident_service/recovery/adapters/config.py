import os

from dataclasses import dataclass


SUPPORTED_EXECUTION_BACKENDS = {
    "local-docker",
    "emr-serverless",
}


@dataclass(frozen=True)
class RecoveryExecutionConfig:

    backend: str = "local-docker"
    aws_region: str = "us-east-1"
    emr_serverless_application_id: str | None = None
    emr_serverless_execution_role_arn: str | None = None
    emr_serverless_artifact_bucket: str | None = None
    emr_serverless_artifact_prefix: str = (
        "incident-recovery"
    )

    @classmethod
    def from_env(cls) -> "RecoveryExecutionConfig":

        backend = os.getenv(
            "RECOVERY_EXECUTION_BACKEND",
            "local-docker",
        ).strip().lower()

        aws_region = os.getenv(
            "AWS_REGION",
            "us-east-1",
        ).strip()

        application_id = (
            os.getenv(
                "EMR_SERVERLESS_APPLICATION_ID"
            )
            or None
        )

        execution_role_arn = (
            os.getenv(
                "EMR_SERVERLESS_EXECUTION_ROLE_ARN"
            )
            or None
        )

        artifact_bucket = (
            os.getenv(
                "EMR_SERVERLESS_ARTIFACT_BUCKET"
            )
            or None
        )

        artifact_prefix = os.getenv(
            "EMR_SERVERLESS_ARTIFACT_PREFIX",
            "incident-recovery",
        ).strip().strip("/")

        if backend not in SUPPORTED_EXECUTION_BACKENDS:
            raise ValueError(
                "RECOVERY_EXECUTION_BACKEND must be one of: "
                + ", ".join(
                    sorted(
                        SUPPORTED_EXECUTION_BACKENDS
                    )
                )
            )

        if not aws_region:
            raise ValueError(
                "AWS_REGION must not be empty."
            )

        if not artifact_prefix:
            raise ValueError(
                "EMR_SERVERLESS_ARTIFACT_PREFIX "
                "must not be empty."
            )

        if backend == "emr-serverless":
            required = {
                "EMR_SERVERLESS_APPLICATION_ID":
                    application_id,
                "EMR_SERVERLESS_EXECUTION_ROLE_ARN":
                    execution_role_arn,
                "EMR_SERVERLESS_ARTIFACT_BUCKET":
                    artifact_bucket,
            }

            missing = [
                name
                for name, value
                in required.items()
                if not value
            ]

            if missing:
                raise ValueError(
                    "Missing required EMR Serverless "
                    "configuration: "
                    + ", ".join(missing)
                )

        return cls(
            backend=backend,
            aws_region=aws_region,
            emr_serverless_application_id=(
                application_id
            ),
            emr_serverless_execution_role_arn=(
                execution_role_arn
            ),
            emr_serverless_artifact_bucket=(
                artifact_bucket
            ),
            emr_serverless_artifact_prefix=(
                artifact_prefix
            ),
        )


SUPPORTED_STORAGE_BACKENDS = {
    "minio",
    "aws-s3",
}


@dataclass(frozen=True)
class RecoveryStorageConfig:
    backend: str = "minio"

    silver_path: str = (
        "s3a://data-platform/silver/transactions"
    )

    backup_path: str = (
        "s3a://data-platform/"
        "failure-backups/schema-drift/"
        "silver-transactions"
    )

    temp_path: str = (
        "s3a://data-platform/"
        "failure-temp/schema-drift-restore/"
        "silver-transactions"
    )

    schema_evidence_path: str = (
        "/opt/spark/work-dir/evidence/"
        "silver_schema.json"
    )

    dataset_namespace: str = (
        "s3://data-platform"
    )

    dataset_name: str = (
        "silver/transactions"
    )

    minio_endpoint: str = (
        "http://minio:9000"
    )

    @classmethod
    def from_env(cls) -> "RecoveryStorageConfig":
        backend = os.getenv(
            "RECOVERY_STORAGE_BACKEND",
            "minio",
        ).strip().lower()

        silver_path = os.getenv(
            "RECOVERY_SILVER_PATH",
            (
                "s3a://data-platform/"
                "silver/transactions"
            ),
        ).strip()

        backup_path = os.getenv(
            "RECOVERY_BACKUP_PATH",
            (
                "s3a://data-platform/"
                "failure-backups/schema-drift/"
                "silver-transactions"
            ),
        ).strip()

        temp_path = os.getenv(
            "RECOVERY_TEMP_PATH",
            (
                "s3a://data-platform/"
                "failure-temp/"
                "schema-drift-restore/"
                "silver-transactions"
            ),
        ).strip()

        evidence_path = os.getenv(
            "RECOVERY_SCHEMA_EVIDENCE_PATH",
            (
                "/opt/spark/work-dir/evidence/"
                "silver_schema.json"
            ),
        ).strip()

        namespace = os.getenv(
            "RECOVERY_DATASET_NAMESPACE",
            "s3://data-platform",
        ).strip()

        dataset_name = os.getenv(
            "RECOVERY_DATASET_NAME",
            "silver/transactions",
        ).strip()

        minio_endpoint = os.getenv(
            "MINIO_ENDPOINT",
            "http://minio:9000",
        ).strip()

        if backend not in SUPPORTED_STORAGE_BACKENDS:
            raise ValueError(
                "RECOVERY_STORAGE_BACKEND must be "
                "one of: "
                + ", ".join(
                    sorted(
                        SUPPORTED_STORAGE_BACKENDS
                    )
                )
            )

        values = {
            "RECOVERY_SILVER_PATH":
                silver_path,
            "RECOVERY_BACKUP_PATH":
                backup_path,
            "RECOVERY_TEMP_PATH":
                temp_path,
            "RECOVERY_SCHEMA_EVIDENCE_PATH":
                evidence_path,
            "RECOVERY_DATASET_NAMESPACE":
                namespace,
            "RECOVERY_DATASET_NAME":
                dataset_name,
        }

        missing = [
            name
            for name, value in values.items()
            if not value
        ]

        if missing:
            raise ValueError(
                "Recovery storage configuration "
                "must not be empty: "
                + ", ".join(missing)
            )

        if backend == "aws-s3":
            cloud_paths = {
                "RECOVERY_SILVER_PATH":
                    silver_path,
                "RECOVERY_BACKUP_PATH":
                    backup_path,
                "RECOVERY_TEMP_PATH":
                    temp_path,
                "RECOVERY_SCHEMA_EVIDENCE_PATH":
                    evidence_path,
            }

            invalid = [
                name
                for name, value
                in cloud_paths.items()
                if not value.startswith("s3://")
            ]

            if invalid:
                raise ValueError(
                    "AWS S3 recovery paths must "
                    "use s3://: "
                    + ", ".join(invalid)
                )

        return cls(
            backend=backend,
            silver_path=silver_path,
            backup_path=backup_path,
            temp_path=temp_path,
            schema_evidence_path=(
                evidence_path
            ),
            dataset_namespace=namespace,
            dataset_name=dataset_name,
            minio_endpoint=minio_endpoint,
        )

    def environment(
        self,
        *,
        evidence_path: str | None = None,
    ) -> dict[str, str]:
        values = {
            "RECOVERY_STORAGE_BACKEND":
                self.backend,
            "RECOVERY_SILVER_PATH":
                self.silver_path,
            "RECOVERY_BACKUP_PATH":
                self.backup_path,
            "RECOVERY_TEMP_PATH":
                self.temp_path,
            "RECOVERY_SCHEMA_EVIDENCE_PATH": (
                evidence_path
                or self.schema_evidence_path
            ),
            "RECOVERY_DATASET_NAMESPACE":
                self.dataset_namespace,
            "RECOVERY_DATASET_NAME":
                self.dataset_name,
        }

        if self.backend == "minio":
            values["MINIO_ENDPOINT"] = (
                self.minio_endpoint
            )

        return values
