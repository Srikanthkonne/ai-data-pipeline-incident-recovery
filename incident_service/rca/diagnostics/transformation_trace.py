from pathlib import Path
from typing import Any


NORMAL_TRANSFORMATION = Path(
    "spark/jobs/silver_transactions.py"
)

FAILURE_INJECTION = Path(
    "failure_injection/scenarios/"
    "inject_schema_drift.py"
)


def diagnose_schema_transformation_trace(
    column: str,
) -> dict[str, Any]:

    normal_code = NORMAL_TRANSFORMATION.read_text()
    injection_code = FAILURE_INJECTION.read_text()

    normal_reference = column in normal_code
    injection_reference = column in injection_code

    injection_adds_column = (
        injection_reference
        and "withColumn" in injection_code
        and "lit(" in injection_code
    )

    if (
        not normal_reference
        and injection_adds_column
    ):
        conclusion = (
            "COLUMN_MATCHES_CONTROLLED_"
            "FAILURE_INJECTION_CODE"
        )
        evidence_strength = (
            "STRONG_TEST_SCENARIO_EVIDENCE"
        )
    else:
        conclusion = (
            "CODE_PATH_ORIGIN_NOT_NARROWED"
        )
        evidence_strength = (
            "SUPPORTING_NOT_CONCLUSIVE"
        )

    return {
        "diagnostic_type":
            "SCHEMA_TRANSFORMATION_TRACE",
        "column":
            column,
        "normal_transformation_file":
            str(NORMAL_TRANSFORMATION),
        "normal_transformation_reference":
            normal_reference,
        "failure_injection_file":
            str(FAILURE_INJECTION),
        "failure_injection_reference":
            injection_reference,
        "failure_injection_adds_column":
            injection_adds_column,
        "evidence_strength":
            evidence_strength,
        "runtime_execution_proven":
            False,
        "causal_evidence_eligible":
            False,
        "conclusion":
            conclusion,
    }
