import json
import os
import time
from typing import Any

import requests


DEFAULT_MODEL = "gemini-3.5-flash-lite"

RETRYABLE_STATUS_CODES = {
    429,
    500,
    502,
    503,
    504,
}


RCA_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause_hypothesis": {
            "type": "string",
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "supporting_evidence": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "contradicting_evidence": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "missing_evidence": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "recommended_diagnostics": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "affected_components": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
    },
    "required": [
        "root_cause_hypothesis",
        "confidence",
        "supporting_evidence",
        "contradicting_evidence",
        "missing_evidence",
        "recommended_diagnostics",
        "affected_components",
    ],
    "additionalProperties": False,
}


def _extract_output_text(
    response_body: dict[str, Any],
) -> str:
    """
    Extract generated text from a Gemini
    generateContent response.
    """
    candidates = response_body.get(
        "candidates",
        [],
    )

    if not candidates:
        raise RuntimeError(
            "Gemini response contained no candidates."
        )

    parts = (
        candidates[0]
        .get("content", {})
        .get("parts", [])
    )

    text_parts = [
        part["text"]
        for part in parts
        if part.get("text")
    ]

    text = "".join(
        text_parts
    ).strip()

    if not text:
        raise RuntimeError(
            "Gemini response contained no text."
        )

    return text


def gemini_provider(
    request: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute the provider-neutral RCA request using
    Gemini generateContent with structured JSON output.
    """
    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    model = os.getenv(
        "GEMINI_MODEL",
        DEFAULT_MODEL,
    )

    url = (
        "https"
        "://"
        "generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )


    prompt = (
        "Perform the RCA investigation below.\n"
        "Follow every supplied rule.\n"
        "Use only supplied evidence.\n\n"
        + json.dumps(
            request,
            indent=2,
            sort_keys=True,
        )
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt,
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
            "responseMimeType": (
                "application/json"
            ),
            "responseJsonSchema": (
                RCA_RESPONSE_SCHEMA
            ),
        },
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    last_error = None

    for attempt in range(3):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=(10, 90),
            )

        except requests.exceptions.ReadTimeout as exc:
            last_error = exc

            if attempt == 2:
                raise RuntimeError(
                    "Gemini timed out after "
                    "three attempts."
                ) from exc

            time.sleep(
                2 ** attempt
            )
            continue

        if (
            response.status_code
            in RETRYABLE_STATUS_CODES
        ):
            if attempt == 2:
                raise RuntimeError(
                    "Gemini API request failed "
                    f"after retries: "
                    f"HTTP {response.status_code}: "
                    f"{response.text[:1000]}"
                )

            time.sleep(
                2 ** attempt
            )
            continue

        if not response.ok:
            raise RuntimeError(
                "Gemini API request failed: "
                f"HTTP {response.status_code}: "
                f"{response.text[:1000]}"
            )

        response_body = response.json()

        output_text = _extract_output_text(
            response_body
        )

        try:
            return json.loads(
                output_text
            )

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Gemini returned invalid JSON: "
                f"{output_text[:1000]}"
            ) from exc

    raise RuntimeError(
        "Gemini request failed."
    ) from last_error
