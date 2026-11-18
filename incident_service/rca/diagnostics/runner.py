from pathlib import Path
from typing import Any

from incident_service.rca.diagnostics.schema_origin import (
    diagnose_schema_column_origin,
)
from incident_service.rca.diagnostics.transformation_trace import (
    diagnose_schema_transformation_trace,
)
from incident_service.rca.diagnostics.runtime_provenance import (
    diagnose_runtime_provenance,
)


BRONZE_SCHEMA_EVIDENCE = Path(
    "spark/evidence/bronze_schema.json"
)


def collect_diagnostic_evidence(
    incident_id: int,
    incident_type: str,
) -> list[dict[str, Any]]:
    """
    Run deterministic diagnostics that are applicable
    to the incident type.

    Diagnostic evidence is separate from causal evidence.
    """
    diagnostics: list[dict[str, Any]] = []

    if incident_type == "SCHEMA_DRIFT":

        # Runtime provenance is durable cloud evidence and
        # must not depend on local Bronze schema artifacts.
        diagnostics.append(
            diagnose_runtime_provenance(
                incident_id=incident_id
            )
        )

        if not BRONZE_SCHEMA_EVIDENCE.exists():
            diagnostics.append(
                {
                    "diagnostic_type":
                        "SCHEMA_COLUMN_ORIGIN",
                    "status":
                        "EVIDENCE_UNAVAILABLE",
                    "reason":
                        "Bronze schema evidence file "
                        "was not available.",
                }
            )

            return diagnostics

        result = diagnose_schema_column_origin(
            incident_id=incident_id
        )

        schema_diagnostics = result[
            "diagnostics"
        ]

        diagnostics.extend(
            schema_diagnostics
        )

        for diagnostic in schema_diagnostics:
            column = diagnostic.get(
                "column"
            )

            if column:
                diagnostics.append(
                    diagnose_schema_transformation_trace(
                        column=column
                    )
                )


    return diagnostics
