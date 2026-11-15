from prometheus_client import CollectorRegistry, Gauge, generate_latest

from incident_service.metrics.repository import get_operational_summary


def generate_prometheus_metrics() -> bytes:
    """Render the current operational state in Prometheus format."""
    summary = get_operational_summary()
    registry = CollectorRegistry()

    incidents = Gauge(
        "incident_recovery_incidents",
        "Current number of incidents.",
        registry=registry,
    )
    incidents.set(summary["incidents"]["total"])

    incidents_by_status = Gauge(
        "incident_recovery_incidents_by_status",
        "Current incidents grouped by lifecycle status.",
        ["status"],
        registry=registry,
    )
    for status, count in summary["incidents"]["by_status"].items():
        incidents_by_status.labels(status=status).set(count)

    mttr = Gauge(
        "incident_recovery_mean_time_to_resolution_seconds",
        "Mean time to resolution for resolved incidents in seconds.",
        registry=registry,
    )
    mttr_value = summary["incidents"]["mean_time_to_resolution_seconds"]
    if mttr_value is not None:
        mttr.set(mttr_value)

    attempts = Gauge(
        "incident_recovery_recovery_attempts",
        "Total persisted recovery attempts.",
        registry=registry,
    )
    attempts.set(summary["recovery_attempts"]["total"])

    attempts_by_status = Gauge(
        "incident_recovery_recovery_attempts_by_status",
        "Recovery attempts grouped by status.",
        ["status"],
        registry=registry,
    )
    for status, count in summary["recovery_attempts"]["by_status"].items():
        attempts_by_status.labels(status=status).set(count)

    queue_items = Gauge(
        "incident_recovery_queue_items",
        "Current number of durable recovery queue items.",
        registry=registry,
    )
    queue_items.set(summary["recovery_queue"]["total"])

    queue_by_state = Gauge(
        "incident_recovery_queue_items_by_state",
        "Recovery queue items grouped by state.",
        ["state"],
        registry=registry,
    )
    for state, count in summary["recovery_queue"]["by_state"].items():
        queue_by_state.labels(state=state).set(count)

    autonomous_attempts = Gauge(
        "incident_recovery_autonomous_attempts",
        "Current accumulated autonomous attempt count in recovery_queue.",
        registry=registry,
    )
    autonomous_attempts.set(summary["recovery_queue"]["autonomous_attempts"])

    for metric_name, help_text, key in (
        (
            "incident_recovery_incident_resolution_rate",
            "Fraction of incidents currently resolved.",
            "incident_resolution_rate",
        ),
        (
            "incident_recovery_recovery_attempt_success_rate",
            "Successful non-dry-run recovery attempts divided by all non-dry-run attempts.",
            "recovery_attempt_success_rate",
        ),
        (
            "incident_recovery_queue_completion_rate",
            "Completed queue items divided by terminal queue outcomes.",
            "queue_completion_rate",
        ),
        (
            "incident_recovery_mean_autonomous_attempts_per_queue_item",
            "Mean autonomous attempts across current recovery queue items.",
            "mean_autonomous_attempts_per_queue_item",
        ),
    ):
        gauge = Gauge(
            metric_name,
            help_text,
            registry=registry,
        )
        value = summary["kpis"][key]
        if value is not None:
            gauge.set(value)

    return generate_latest(registry)
