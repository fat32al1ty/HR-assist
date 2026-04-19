import json
from typing import Any

from openai import APIConnectionError, APIStatusError, OpenAI

from app.core.config import settings
from app.services.openai_usage import record_responses_usage
from app.services.resume_analyzer import DEFAULT_OPENAI_BASE_URL

SYSTEM_PROMPT = """
You are an enterprise vacancy analysis engine.
Extract a structured vacancy profile from provided vacancy text.
Return valid JSON only, matching the schema.
Do not invent facts. Use null or empty arrays where data is missing.
Prefer concise Russian text for summary and recommendations.
First classify whether this content is an actual job vacancy posting.
If it is not a real vacancy (article, landing page, category page, company page, etc.),
set is_vacancy=false, provide vacancy_confidence and rejection_reason.
"""


class VacancyAnalysisUnavailable(RuntimeError):
    pass


def analyze_vacancy_text(text: str) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise VacancyAnalysisUnavailable("OpenAI API key is not configured")

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or DEFAULT_OPENAI_BASE_URL,
        timeout=settings.openai_analysis_timeout_seconds,
    )

    try:
        response = client.responses.create(
            model=settings.openai_analysis_model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text[:60000]},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "vacancy_profile",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "role": {"type": ["string", "null"]},
                            "is_vacancy": {"type": "boolean"},
                            "vacancy_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "rejection_reason": {"type": ["string", "null"]},
                            "seniority": {"type": ["string", "null"]},
                            "employment_type": {"type": ["string", "null"]},
                            "location": {"type": ["string", "null"]},
                            "remote_policy": {"type": ["string", "null"]},
                            "summary": {"type": "string"},
                            "must_have_skills": {"type": "array", "items": {"type": "string"}},
                            "nice_to_have_skills": {"type": "array", "items": {"type": "string"}},
                            "tools": {"type": "array", "items": {"type": "string"}},
                            "domains": {"type": "array", "items": {"type": "string"}},
                            "responsibilities": {"type": "array", "items": {"type": "string"}},
                            "requirements": {"type": "array", "items": {"type": "string"}},
                            "red_flags": {"type": "array", "items": {"type": "string"}},
                            "matching_keywords": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": [
                            "role",
                            "is_vacancy",
                            "vacancy_confidence",
                            "rejection_reason",
                            "seniority",
                            "employment_type",
                            "location",
                            "remote_policy",
                            "summary",
                            "must_have_skills",
                            "nice_to_have_skills",
                            "tools",
                            "domains",
                            "responsibilities",
                            "requirements",
                            "red_flags",
                            "matching_keywords",
                        ],
                    },
                    "strict": True,
                }
            },
        )
    except APIStatusError as error:
        body = str(error)
        if error.status_code == 429 and "insufficient_quota" in body:
            raise VacancyAnalysisUnavailable(
                "OpenAI API quota is exhausted or billing is not enabled for the configured API key."
            ) from error
        raise
    except APIConnectionError as error:
        cause = repr(error.__cause__) if error.__cause__ else str(error)
        raise VacancyAnalysisUnavailable(f"Could not connect to OpenAI API: {cause}") from error

    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    record_responses_usage(input_tokens=input_tokens, output_tokens=output_tokens)

    return json.loads(response.output_text)
