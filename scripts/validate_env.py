import argparse
import os
import sys
from pathlib import Path

from dotenv import dotenv_values


REQUIRED = {
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "MARQUEZ_DB_PASSWORD",
    "NEO4J_PASSWORD",
    "AIRFLOW_DB_PASSWORD",
    "AIRFLOW_ADMIN_USERNAME",
    "AIRFLOW_ADMIN_PASSWORD",
}

SECRET_NAMES = {
    "POSTGRES_PASSWORD",
    "MINIO_ROOT_PASSWORD",
    "MARQUEZ_DB_PASSWORD",
    "NEO4J_PASSWORD",
    "AIRFLOW_DB_PASSWORD",
    "AIRFLOW_ADMIN_PASSWORD",
    "GEMINI_API_KEY",
}

PLACEHOLDERS = {
    "",
    "change_me",
    "changeme",
    "replace_me",
    "replace-with-real-secret",
}

POSITIVE_INTS = {
    "POSTGRES_PORT": 5432,
    "INCIDENT_WORKER_MAX_INCIDENTS_PER_CYCLE": 1,
    "INCIDENT_WORKER_MAX_AUTONOMOUS_ATTEMPTS": 3,
    "INCIDENT_WORKER_QUEUE_CLAIM_SECONDS": 300,
    "INCIDENT_WORKER_RETRY_BASE_SECONDS": 60,
    "INCIDENT_WORKER_RETRY_MAX_SECONDS": 1800,
}

POSITIVE_FLOATS = {
    "INCIDENT_WORKER_POLL_INTERVAL_SECONDS": 10.0,
    "INCIDENT_WORKER_QUEUE_HEARTBEAT_INTERVAL_SECONDS": 60.0,
}

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def read_bool(value: str, name: str, errors: list[str]) -> bool | None:
    normalized = value.strip().lower()

    if normalized in TRUE_VALUES:
        return True

    if normalized in FALSE_VALUES:
        return False

    errors.append(f"{name}: must be a boolean value")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate deployment environment without printing secret values."
    )
    parser.add_argument(
        "--file",
        default=".env",
        help="Environment file to validate (default: .env)",
    )
    parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="Allow placeholder secrets when validating .env.example",
    )
    args = parser.parse_args()

    env_path = Path(args.file)

    if not env_path.exists():
        print(f"ERROR: environment file not found: {env_path}")
        return 1

    config = {
        key: value
        for key, value in dotenv_values(env_path).items()
        if value is not None
    }

    # Explicit process environment takes precedence.
    for key in set(config) | REQUIRED | SECRET_NAMES:
        if key in os.environ:
            config[key] = os.environ[key]

    errors: list[str] = []
    warnings: list[str] = []

    for name in sorted(REQUIRED):
        value = str(config.get(name, "")).strip()

        if not value:
            errors.append(f"{name}: required value is missing")
            continue

        if (
            name in SECRET_NAMES
            and value.lower() in PLACEHOLDERS
            and not args.allow_placeholders
        ):
            errors.append(f"{name}: placeholder secret must be replaced")

    parsed_ints: dict[str, int] = {}

    for name, default in POSITIVE_INTS.items():
        raw = str(config.get(name, default)).strip()

        try:
            value = int(raw)
        except ValueError:
            errors.append(f"{name}: must be an integer")
            continue

        if value <= 0:
            errors.append(f"{name}: must be greater than zero")
            continue

        parsed_ints[name] = value

    parsed_floats: dict[str, float] = {}

    for name, default in POSITIVE_FLOATS.items():
        raw = str(config.get(name, default)).strip()

        try:
            value = float(raw)
        except ValueError:
            errors.append(f"{name}: must be numeric")
            continue

        if value <= 0:
            errors.append(f"{name}: must be greater than zero")
            continue

        parsed_floats[name] = value

    dry_run = read_bool(
        str(config.get("INCIDENT_WORKER_DRY_RUN", "true")),
        "INCIDENT_WORKER_DRY_RUN",
        errors,
    )

    claim_seconds = parsed_ints.get(
        "INCIDENT_WORKER_QUEUE_CLAIM_SECONDS"
    )
    heartbeat_seconds = parsed_floats.get(
        "INCIDENT_WORKER_QUEUE_HEARTBEAT_INTERVAL_SECONDS"
    )

    if (
        claim_seconds is not None
        and heartbeat_seconds is not None
        and heartbeat_seconds >= claim_seconds
    ):
        errors.append(
            "INCIDENT_WORKER_QUEUE_HEARTBEAT_INTERVAL_SECONDS: "
            "must be shorter than the queue claim lease"
        )

    retry_base = parsed_ints.get(
        "INCIDENT_WORKER_RETRY_BASE_SECONDS"
    )
    retry_max = parsed_ints.get(
        "INCIDENT_WORKER_RETRY_MAX_SECONDS"
    )

    if (
        retry_base is not None
        and retry_max is not None
        and retry_base > retry_max
    ):
        errors.append(
            "INCIDENT_WORKER_RETRY_BASE_SECONDS: "
            "must not exceed retry max"
        )

    threshold_raw = str(
        config.get("NULL_SPIKE_THRESHOLD", "0.05")
    ).strip()

    try:
        threshold = float(threshold_raw)
        if not 0.0 <= threshold <= 1.0:
            errors.append(
                "NULL_SPIKE_THRESHOLD: must be between 0 and 1"
            )
    except ValueError:
        errors.append("NULL_SPIKE_THRESHOLD: must be numeric")

    gemini_key = str(
        config.get("GEMINI_API_KEY", "")
    ).strip()

    gemini_missing = (
        not gemini_key
        or gemini_key.lower() in PLACEHOLDERS
    )

    if dry_run is False and gemini_missing:
        errors.append(
            "GEMINI_API_KEY: required when "
            "INCIDENT_WORKER_DRY_RUN=false"
        )
    elif dry_run is True and gemini_missing:
        warnings.append(
            "GEMINI_API_KEY is not configured; "
            "acceptable while worker dry-run is enabled"
        )

    if errors:
        print("Environment validation FAILED.")
        for error in errors:
            print(f"ERROR: {error}")

        for warning in warnings:
            print(f"WARNING: {warning}")

        return 1

    print("Environment validation PASSED.")
    print(
        "Worker mode:",
        "DRY_RUN" if dry_run else "AUTONOMOUS",
    )

    for warning in warnings:
        print(f"WARNING: {warning}")

    print("Secret values were not displayed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
