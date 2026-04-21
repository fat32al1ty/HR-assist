from typing import Any

from openai import APIConnectionError, APIStatusError, OpenAI

from app.core.config import settings
from app.services.openai_usage import record_embeddings_usage
from app.services.resume_analyzer import DEFAULT_OPENAI_BASE_URL


class EmbeddingUnavailable(RuntimeError):
    pass


def create_embedding(text: str) -> list[float]:
    if not settings.openai_api_key:
        raise EmbeddingUnavailable("OpenAI API key is not configured")

    client_options: dict[str, Any] = {
        "api_key": settings.openai_api_key,
        "timeout": settings.openai_analysis_timeout_seconds,
        "base_url": settings.openai_base_url or DEFAULT_OPENAI_BASE_URL,
    }
    client = OpenAI(**client_options)

    try:
        response = client.embeddings.create(
            model=settings.openai_embedding_model,
            input=text[:24000],
        )
    except APIStatusError as error:
        body = str(error)
        if error.status_code == 429 and "insufficient_quota" in body:
            raise EmbeddingUnavailable(
                "OpenAI API quota is exhausted or billing is not enabled for the configured API key. "
                "Check the OpenAI project billing, limits, and API key."
            ) from error
        raise
    except APIConnectionError as error:
        cause = repr(error.__cause__) if error.__cause__ else str(error)
        raise EmbeddingUnavailable(
            f"Could not connect to OpenAI embeddings API: {cause}"
        ) from error

    usage = getattr(response, "usage", None)
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    record_embeddings_usage(input_tokens=prompt_tokens)

    vector = response.data[0].embedding
    if len(vector) != settings.vector_size:
        raise EmbeddingUnavailable(
            f"Embedding vector size mismatch: expected {settings.vector_size}, got {len(vector)}"
        )
    return vector
