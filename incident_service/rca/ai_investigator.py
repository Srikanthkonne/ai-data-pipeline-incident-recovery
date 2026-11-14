from typing import Any, Callable

from incident_service.rca.ai_contract import (
    build_investigator_request,
    validate_investigator_response,
)
from incident_service.rca.facts import (
    build_rca_facts,
)


ProviderCallable = Callable[
    [dict[str, Any]],
    dict[str, Any],
]


def investigate_with_ai(
    incident_id: int,
    provider: ProviderCallable,
) -> dict[str, Any]:
    """
    Run the provider-neutral AI RCA workflow.

    Flow:
        incident
        -> deterministic RCA facts
        -> investigator request
        -> provider
        -> validated RCA response
    """
    facts = build_rca_facts(
        incident_id
    )

    from incident_service.rca.diagnostics.runner import (
        collect_diagnostic_evidence,
    )

    facts["diagnostic_evidence"] = (
        collect_diagnostic_evidence(
            incident_id=incident_id,
            incident_type=facts[
                "incident_type"
            ],
        )
    )

    facts["causal_evidence"] = [
        evidence
        for evidence in facts[
            "diagnostic_evidence"
        ]
        if evidence.get(
            "causal_evidence_eligible"
        )
    ]

    request = build_investigator_request(
        facts
    )

    response = provider(
        request
    )

    validated_response = (
        validate_investigator_response(
            response
        )
    )

    if not facts.get("causal_evidence"):
        validated_response[
            "root_cause_hypothesis"
        ] = "INSUFFICIENT_EVIDENCE"

    affected_components = [
        facts["affected_entity"]["name"]
    ]

    for dependency in facts[
        "downstream_dependencies"
    ]:
        name = dependency["name"]

        if name not in affected_components:
            affected_components.append(
                name
            )

    validated_response[
        "affected_components"
    ] = affected_components

    return {
        "incident_id": incident_id,
        "rca_facts": facts,
        "assessment": validated_response,
    }
