from typing import Any


REQUIRED_RCA_FIELDS = {
    "root_cause_hypothesis",
    "confidence",
    "supporting_evidence",
    "contradicting_evidence",
    "missing_evidence",
    "recommended_diagnostics",
    "affected_components",
}


def build_investigator_request(
    rca_facts: dict[str, Any],
) -> dict[str, Any]:
    """
    Build the provider-neutral request sent to an
    AI root-cause investigator.
    """
    return {
        "task": (
            "Analyze the supplied deterministic incident facts and "
            "produce a root-cause assessment."
        ),
        "rules": [
            (
                "Use only the supplied evidence. Do not invent "
                "logs, metrics, deployments, failures, or causes."
            ),
            (
                "Distinguish observed facts from hypotheses."
            ),
            (
                "Do not treat lineage adjacency or upstream dependency "
                "as proof that a component caused the incident."
            ),
            (
                "If the evidence does not establish a root cause, "
                "set root_cause_hypothesis to INSUFFICIENT_EVIDENCE."
            ),
            (
                "Confidence must be a number from 0.0 to 1.0."
            ),
            (
                "Recommended diagnostics must target missing evidence "
                "that could confirm or reject the hypothesis."
            ),
        ],
        "required_output": {
            "root_cause_hypothesis": "string",
            "confidence": "number between 0.0 and 1.0",
            "supporting_evidence": "list[string]",
            "contradicting_evidence": "list[string]",
            "missing_evidence": "list[string]",
            "recommended_diagnostics": "list[string]",
            "affected_components": "list[string]",
        },
        "rca_facts": rca_facts,
    }


def validate_investigator_response(
    response: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate the provider-independent RCA response.
    """
    missing_fields = (
        REQUIRED_RCA_FIELDS
        - response.keys()
    )

    if missing_fields:
        raise ValueError(
            "AI RCA response is missing fields: "
            + ", ".join(sorted(missing_fields))
        )

    confidence = response["confidence"]

    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0.0 <= confidence <= 1.0
    ):
        raise ValueError(
            "confidence must be between 0.0 and 1.0"
        )

    list_fields = (
        "supporting_evidence",
        "contradicting_evidence",
        "missing_evidence",
        "recommended_diagnostics",
        "affected_components",
    )

    for field in list_fields:
        if not isinstance(response[field], list):
            raise ValueError(
                f"{field} must be a list"
            )

    if not isinstance(
        response["root_cause_hypothesis"],
        str,
    ):
        raise ValueError(
            "root_cause_hypothesis must be a string"
        )

    return response
