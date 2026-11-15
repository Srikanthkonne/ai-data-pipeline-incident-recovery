import signal
from threading import Event

from dotenv import load_dotenv

from incident_service.worker.config import WorkerConfig
from incident_service.worker.recovery_worker import (
    run_forever,
)


def main() -> None:
    # Load local environment before reading worker
    # configuration or initializing the AI provider.
    load_dotenv(".env")

    from incident_service.rca.providers.gemini import (
        gemini_provider,
    )

    config = WorkerConfig.from_env()
    stop_event = Event()

    def handle_shutdown(signum, _frame):
        print(
            f"Shutdown signal received: {signum}",
            flush=True,
        )
        stop_event.set()

    signal.signal(
        signal.SIGINT,
        handle_shutdown,
    )
    signal.signal(
        signal.SIGTERM,
        handle_shutdown,
    )

    print(
        (
            "Incident recovery worker starting "
            f"(poll_interval={config.poll_interval_seconds}s, "
            f"max_per_cycle={config.max_incidents_per_cycle}, "
            f"dry_run={config.dry_run})"
        ),
        flush=True,
    )

    run_forever(
        provider=gemini_provider,
        config=config,
        stop_event=stop_event,
    )

    print(
        "Incident recovery worker stopped.",
        flush=True,
    )


if __name__ == "__main__":
    main()
