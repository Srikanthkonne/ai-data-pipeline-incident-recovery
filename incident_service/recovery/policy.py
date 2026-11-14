from typing import Any


def choose_recovery_action(
    rca_facts: dict[str, Any],
) -> dict[str, Any]:
    """
    Select a deterministic recovery action from
    verified RCA evidence.

    The LLM does not choose executable commands.
    """

    incident_type = rca_facts[
        "incident_type"
    ]

    causal_evidence = rca_facts.get(
        "causal_evidence",
        [],
    )

    if incident_type == "SCHEMA_DRIFT":

        for evidence in causal_evidence:

            if (
                evidence.get(
                    "diagnostic_type"
                )
                == "RUNTIME_PROVENANCE"
                and evidence.get(
                    "runtime_execution_proven"
                )
                is True
                and evidence.get(
                    "scenario"
                )
                == "SCHEMA_DRIFT"
                and evidence.get(
                    "status"
                )
                == "COMPLETED"
            ):
                return {
                    "action":
                        "RESTORE_SCHEMA_DRIFT_BACKUP",

                    "automatic_execution_allowed":
                        True,

                    "reason":
                        "Verified controlled schema-drift "
                        "runtime provenance matched the incident.",

                    "evidence_reference": {
                        "execution_id":
                            evidence[
                                "execution_id"
                            ],
                        "injected_column":
                            evidence[
                                "injected_column"
                            ],
                        "provenance_file":
                            evidence[
                                "provenance_file"
                            ],
                    },
                }

    return {
        "action":
            "MANUAL_REVIEW",

        "automatic_execution_allowed":
            False,

        "reason":
            "No verified recovery policy matched "
            "the available causal evidence.",

        "evidence_reference":
            None,
    }
