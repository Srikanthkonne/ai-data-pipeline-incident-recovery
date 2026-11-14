import threading

from typing import Any, Callable

from incident_service.repository import (
    get_incident,
    update_incident_status,
)
from incident_service.rca.ai_investigator import (
    investigate_with_ai,
)
from incident_service.recovery.policy import (
    choose_recovery_action,
)
from incident_service.recovery.executor import (
    RecoveryExecutionError,
    execute_recovery_action,
)
from incident_service.recovery.validator import (
    RecoveryValidationError,
    validate_schema_drift_recovery,
)
from incident_service.recovery.repository import (
    DEFAULT_RECOVERY_LEASE_SECONDS,
    RecoveryAlreadyInProgressError,
    claim_recovery_execution,
    create_recovery_attempt,
    refresh_recovery_lease,
    update_recovery_attempt,
)


RECOVERY_HEARTBEAT_INTERVAL_SECONDS = 60


class RecoveryHeartbeat:
    """
    Periodically refresh an active recovery lease.

    If the process terminates, this daemon thread
    terminates with it and the lease can eventually
    be reclaimed by another worker.
    """

    def __init__(
        self,
        recovery_attempt_id: int,
        *,
        interval_seconds: float = (
            RECOVERY_HEARTBEAT_INTERVAL_SECONDS
        ),
        lease_seconds: int = (
            DEFAULT_RECOVERY_LEASE_SECONDS
        ),
    ) -> None:

        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds must be "
                "greater than 0."
            )

        if lease_seconds <= 0:
            raise ValueError(
                "lease_seconds must be "
                "greater than 0."
            )

        if interval_seconds >= lease_seconds:
            raise ValueError(
                "heartbeat interval must be "
                "shorter than the recovery lease."
            )

        self.recovery_attempt_id = (
            recovery_attempt_id
        )

        self.interval_seconds = (
            interval_seconds
        )

        self.lease_seconds = lease_seconds

        self._stop_event = threading.Event()

        self._thread = threading.Thread(
            target=self._run,
            name=(
                "recovery-heartbeat-"
                f"{recovery_attempt_id}"
            ),
            daemon=True,
        )

        self.last_error = None

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        if self._thread.is_alive():
            self._thread.join(
                timeout=2
            )

    def _run(self) -> None:
        while not self._stop_event.wait(
            self.interval_seconds
        ):
            try:
                refreshed = (
                    refresh_recovery_lease(
                        recovery_attempt_id=
                            self.recovery_attempt_id,
                        lease_seconds=
                            self.lease_seconds,
                    )
                )

            except Exception as exc:
                self.last_error = exc
                return

            # A terminal attempt cannot be refreshed.
            # Stop the heartbeat naturally.
            if refreshed is None:
                return


class RecoveryOrchestrationError(RuntimeError):
    pass


VALIDATORS = {
    "RESTORE_SCHEMA_DRIFT_BACKUP":
        validate_schema_drift_recovery,
}


def recover_incident(
    incident_id: int,
    provider: Callable[
        [dict[str, Any]],
        dict[str, Any],
    ],
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Orchestrate RCA, deterministic recovery policy,
    allowlisted execution, validation, incident
    lifecycle transitions, and recovery auditing.
    """

    incident = get_incident(
        incident_id
    )

    if not incident:
        raise RecoveryOrchestrationError(
            f"Incident {incident_id} was not found."
        )

    status_before = incident["status"]

    if not dry_run:
        if status_before == "RESOLVED":
            raise RecoveryOrchestrationError(
                f"Incident {incident_id} "
                "is already RESOLVED."
            )

        if status_before not in {
            "OPEN",
            "INVESTIGATING",
            "RECOVERING",
        }:
            raise RecoveryOrchestrationError(
                "Unsupported incident status "
                f"for recovery: {status_before}"
            )

    # Acquire the recovery slot BEFORE running RCA.
    # This prevents duplicate workers from running
    # diagnostics or calling the AI provider.
    try:
        attempt = create_recovery_attempt(
            incident_id=incident_id,
            action="PENDING_RCA",
            status="STARTED",
            automatic_execution_allowed=False,
            rca_assessment={},
            recovery_decision={},
        )

    except RecoveryAlreadyInProgressError:
        return {
            "incident_id":
                incident_id,
            "recovery_attempt_id":
                None,
            "orchestration_status":
                "RECOVERY_ALREADY_IN_PROGRESS",
            "dry_run":
                dry_run,
            "database_status_before":
                status_before,
            "database_status_after":
                status_before,
            "rca_assessment":
                None,
            "recovery_decision":
                None,
            "execution":
                None,
            "validation":
                None,
        }

    recovery_attempt_id = attempt[
        "recovery_attempt_id"
    ]

    heartbeat = RecoveryHeartbeat(
        recovery_attempt_id
    )
    heartbeat.start()

    try:
        # Run RCA only after this worker owns the
        # active recovery slot.
        try:
            rca = investigate_with_ai(
                incident_id=incident_id,
                provider=provider,
            )

        except Exception as exc:
            audit = update_recovery_attempt(
                recovery_attempt_id=
                    recovery_attempt_id,
                status="RCA_FAILED",
                error_message=str(exc),
            )

            return {
                "incident_id":
                    incident_id,
                "recovery_attempt_id":
                    recovery_attempt_id,
                "orchestration_status":
                    "RCA_FAILED",
                "dry_run":
                    dry_run,
                "database_status_before":
                    status_before,
                "database_status_after":
                    status_before,
                "rca_assessment":
                    None,
                "recovery_decision":
                    None,
                "execution":
                    None,
                "validation":
                    None,
                "error":
                    str(exc),
                "audit":
                    audit,
            }

        try:
            decision = choose_recovery_action(
                rca["rca_facts"]
            )

        except Exception as exc:
            audit = update_recovery_attempt(
                recovery_attempt_id=
                    recovery_attempt_id,
                status="POLICY_FAILED",
                rca_assessment=
                    rca["assessment"],
                error_message=str(exc),
            )

            return {
                "incident_id":
                    incident_id,
                "recovery_attempt_id":
                    recovery_attempt_id,
                "orchestration_status":
                    "POLICY_FAILED",
                "dry_run":
                    dry_run,
                "database_status_before":
                    status_before,
                "database_status_after":
                    status_before,
                "rca_assessment":
                    rca["assessment"],
                "recovery_decision":
                    None,
                "execution":
                    None,
                "validation":
                    None,
                "error":
                    str(exc),
                "audit":
                    audit,
            }

        # Populate the same audit row with the RCA
        # and deterministic recovery decision.
        update_recovery_attempt(
            recovery_attempt_id=
                recovery_attempt_id,
            status="STARTED",
            action=decision.get(
                "action",
                "UNKNOWN",
            ),
            automatic_execution_allowed=bool(
                decision.get(
                    "automatic_execution_allowed",
                    False,
                )
            ),
            rca_assessment=
                rca["assessment"],
            recovery_decision=
                decision,
        )

        if dry_run:
            if not decision.get(
                "automatic_execution_allowed",
                False,
            ):
                audit = update_recovery_attempt(
                    recovery_attempt_id=
                        recovery_attempt_id,
                    status="MANUAL_REVIEW",
                )

                return {
                    "incident_id":
                        incident_id,
                    "recovery_attempt_id":
                        recovery_attempt_id,
                    "orchestration_status":
                        "MANUAL_REVIEW",
                    "dry_run":
                        True,
                    "database_status_before":
                        status_before,
                    "database_status_after":
                        status_before,
                    "rca_assessment":
                        rca["assessment"],
                    "recovery_decision":
                        decision,
                    "execution":
                        None,
                    "validation":
                        None,
                    "audit":
                        audit,
                }

            execution = execute_recovery_action(
                decision,
                dry_run=True,
            )

            audit = update_recovery_attempt(
                recovery_attempt_id=
                    recovery_attempt_id,
                status="DRY_RUN",
                execution_result=execution,
            )

            return {
                "incident_id":
                    incident_id,
                "recovery_attempt_id":
                    recovery_attempt_id,
                "orchestration_status":
                    "DRY_RUN",
                "dry_run":
                    True,
                "database_status_before":
                    status_before,
                "database_status_after":
                    status_before,
                "rca_assessment":
                    rca["assessment"],
                "recovery_decision":
                    decision,
                "execution":
                    execution,
                "validation":
                    None,
                "audit":
                    audit,
            }

        current_status = status_before

        if current_status == "OPEN":
            update_incident_status(
                incident_id=incident_id,
                new_status="INVESTIGATING",
            )

            current_status = "INVESTIGATING"

        if not decision.get(
            "automatic_execution_allowed",
            False,
        ):
            audit = update_recovery_attempt(
                recovery_attempt_id=
                    recovery_attempt_id,
                status="MANUAL_REVIEW",
            )

            return {
                "incident_id":
                    incident_id,
                "recovery_attempt_id":
                    recovery_attempt_id,
                "orchestration_status":
                    "MANUAL_REVIEW",
                "dry_run":
                    False,
                "database_status_before":
                    status_before,
                "database_status_after":
                    current_status,
                "rca_assessment":
                    rca["assessment"],
                "recovery_decision":
                    decision,
                "execution":
                    None,
                "validation":
                    None,
                "audit":
                    audit,
            }

        # --------------------------------------------------
        # PRE-EXECUTION IDEMPOTENCY CHECK
        # --------------------------------------------------

        validator = VALIDATORS.get(
            decision["action"]
        )

        if validator is None:
            message = (
                "No validator registered for "
                f"recovery action: "
                f"{decision['action']}"
            )

            audit = update_recovery_attempt(
                recovery_attempt_id=
                    recovery_attempt_id,
                status="PRECHECK_ERROR",
                error_message=message,
            )

            return {
                "incident_id":
                    incident_id,
                "recovery_attempt_id":
                    recovery_attempt_id,
                "orchestration_status":
                    "PRECHECK_ERROR",
                "dry_run":
                    False,
                "database_status_before":
                    status_before,
                "database_status_after":
                    current_status,
                "rca_assessment":
                    rca["assessment"],
                "recovery_decision":
                    decision,
                "execution":
                    None,
                "validation":
                    None,
                "validation_error":
                    message,
                "audit":
                    audit,
            }

        try:
            precheck = validator()

        except RecoveryValidationError as exc:
            audit = update_recovery_attempt(
                recovery_attempt_id=
                    recovery_attempt_id,
                status="PRECHECK_ERROR",
                error_message=str(exc),
            )

            return {
                "incident_id":
                    incident_id,
                "recovery_attempt_id":
                    recovery_attempt_id,
                "orchestration_status":
                    "PRECHECK_ERROR",
                "dry_run":
                    False,
                "database_status_before":
                    status_before,
                "database_status_after":
                    current_status,
                "rca_assessment":
                    rca["assessment"],
                "recovery_decision":
                    decision,
                "execution":
                    None,
                "validation":
                    None,
                "validation_error":
                    str(exc),
                "audit":
                    audit,
            }

        # If the target is already healthy, a prior
        # worker may have completed the external
        # recovery but crashed before auditing it.
        # Do not replay the destructive action.
        if not precheck.get(
            "recovery_needed",
            not precheck.get(
                "healthy",
                False,
            ),
        ):
            ownership = refresh_recovery_lease(
                recovery_attempt_id=
                    recovery_attempt_id,
                lease_seconds=
                    DEFAULT_RECOVERY_LEASE_SECONDS,
            )

            if ownership is None:
                return {
                    "incident_id":
                        incident_id,
                    "recovery_attempt_id":
                        recovery_attempt_id,
                    "orchestration_status":
                        "RECOVERY_FENCE_REJECTED",
                    "dry_run":
                        False,
                    "database_status_before":
                        status_before,
                    "database_status_after":
                        current_status,
                    "rca_assessment":
                        rca["assessment"],
                    "recovery_decision":
                        decision,
                    "execution":
                        None,
                    "validation":
                        precheck,
                }

            skipped_execution = {
                "action":
                    decision["action"],
                "status":
                    "SKIPPED_ALREADY_RECOVERED",
                "executed":
                    False,
                "reason":
                    (
                        "Pre-execution validation "
                        "confirmed the target is "
                        "already healthy."
                    ),
            }

            if current_status == "INVESTIGATING":
                update_incident_status(
                    incident_id=incident_id,
                    new_status="RECOVERING",
                )

                current_status = "RECOVERING"

            final_incident = (
                update_incident_status(
                    incident_id=incident_id,
                    new_status="RESOLVED",
                )
            )

            audit = update_recovery_attempt(
                recovery_attempt_id=
                    recovery_attempt_id,
                status="ALREADY_RECOVERED",
                execution_result=
                    skipped_execution,
                validation_result=
                    precheck,
            )

            return {
                "incident_id":
                    incident_id,
                "recovery_attempt_id":
                    recovery_attempt_id,
                "orchestration_status":
                    "ALREADY_RECOVERED",
                "dry_run":
                    False,
                "database_status_before":
                    status_before,
                "database_status_after":
                    final_incident["status"],
                "rca_assessment":
                    rca["assessment"],
                "recovery_decision":
                    decision,
                "execution":
                    skipped_execution,
                "validation":
                    precheck,
                "resolved_at":
                    final_incident[
                        "resolved_at"
                    ],
                "audit":
                    audit,
            }

        # --------------------------------------------------
        # RECOVERY IS STILL REQUIRED
        # --------------------------------------------------

        # Cross the destructive execution boundary
        # only if this recovery attempt still owns
        # a valid lease.
        execution_claim = claim_recovery_execution(
            recovery_attempt_id=
                recovery_attempt_id,
            lease_seconds=
                DEFAULT_RECOVERY_LEASE_SECONDS,
        )

        if execution_claim is None:
            return {
                "incident_id":
                    incident_id,
                "recovery_attempt_id":
                    recovery_attempt_id,
                "orchestration_status":
                    "RECOVERY_FENCE_REJECTED",
                "dry_run":
                    False,
                "database_status_before":
                    status_before,
                "database_status_after":
                    current_status,
                "rca_assessment":
                    rca["assessment"],
                "recovery_decision":
                    decision,
                "execution":
                    None,
                "validation":
                    precheck,
            }

        if current_status == "INVESTIGATING":
            update_incident_status(
                incident_id=incident_id,
                new_status="RECOVERING",
            )

            current_status = "RECOVERING"

        try:
            def execution_guard() -> bool:
                refreshed = refresh_recovery_lease(
                    recovery_attempt_id=
                        recovery_attempt_id,
                    lease_seconds=
                        DEFAULT_RECOVERY_LEASE_SECONDS,
                )

                return refreshed is not None

            execution = execute_recovery_action(
                decision,
                dry_run=False,
                execution_guard=
                    execution_guard,
            )

        except RecoveryExecutionError as exc:
            audit = update_recovery_attempt(
                recovery_attempt_id=
                    recovery_attempt_id,
                status="EXECUTION_FAILED",
                execution_result=
                    exc.details or None,
                error_message=str(exc),
            )

            return {
                "incident_id":
                    incident_id,
                "recovery_attempt_id":
                    recovery_attempt_id,
                "orchestration_status":
                    "EXECUTION_FAILED",
                "dry_run":
                    False,
                "database_status_before":
                    status_before,
                "database_status_after":
                    current_status,
                "rca_assessment":
                    rca["assessment"],
                "recovery_decision":
                    decision,
                "execution_error":
                    str(exc),
                "validation":
                    None,
                "audit":
                    audit,
            }

        update_recovery_attempt(
            recovery_attempt_id=
                recovery_attempt_id,
            status="RECOVERING",
            execution_result=execution,
        )

        try:
            validation = validator()

        except RecoveryValidationError as exc:
            audit = update_recovery_attempt(
                recovery_attempt_id=
                    recovery_attempt_id,
                status="VALIDATION_ERROR",
                execution_result=execution,
                error_message=str(exc),
            )

            return {
                "incident_id":
                    incident_id,
                "recovery_attempt_id":
                    recovery_attempt_id,
                "orchestration_status":
                    "VALIDATION_ERROR",
                "dry_run":
                    False,
                "database_status_before":
                    status_before,
                "database_status_after":
                    current_status,
                "rca_assessment":
                    rca["assessment"],
                "recovery_decision":
                    decision,
                "execution":
                    execution,
                "validation_error":
                    str(exc),
                "audit":
                    audit,
            }

        if not validation.get(
            "healthy",
            False,
        ):
            audit = update_recovery_attempt(
                recovery_attempt_id=
                    recovery_attempt_id,
                status="VALIDATION_FAILED",
                execution_result=execution,
                validation_result=validation,
            )

            return {
                "incident_id":
                    incident_id,
                "recovery_attempt_id":
                    recovery_attempt_id,
                "orchestration_status":
                    "VALIDATION_FAILED",
                "dry_run":
                    False,
                "database_status_before":
                    status_before,
                "database_status_after":
                    current_status,
                "rca_assessment":
                    rca["assessment"],
                "recovery_decision":
                    decision,
                "execution":
                    execution,
                "validation":
                    validation,
                "audit":
                    audit,
            }

        final_incident = update_incident_status(
            incident_id=incident_id,
            new_status="RESOLVED",
        )

        audit = update_recovery_attempt(
            recovery_attempt_id=
                recovery_attempt_id,
            status="COMPLETED",
            execution_result=execution,
            validation_result=validation,
        )

        return {
            "incident_id":
                incident_id,
            "recovery_attempt_id":
                recovery_attempt_id,
            "orchestration_status":
                "RESOLVED",
            "dry_run":
                False,
            "database_status_before":
                status_before,
            "database_status_after":
                final_incident["status"],
            "rca_assessment":
                rca["assessment"],
            "recovery_decision":
                decision,
            "execution":
                execution,
            "validation":
                validation,
            "resolved_at":
                final_incident["resolved_at"],
            "audit":
                audit,
        }

    finally:
        heartbeat.stop()
