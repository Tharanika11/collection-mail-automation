import json
import logging
import time
from typing import Any

from ..config import GEMINI_API_KEY, GEMINI_FALLBACK_MODEL, GEMINI_MODEL, gemini_enabled


logger = logging.getLogger(__name__)

# How many times to retry on transient errors before falling back to rules
_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 2

_client = None


def get_client():
    """
    Lazily creates one reusable Gemini client.
    Import is deferred so the app runs normally when Gemini is disabled.
    """

    global _client

    if not gemini_enabled():
        return None

    if _client is None:
        from google import genai

        _client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Gemini client initialised with model %s", GEMINI_MODEL)

    return _client


def generate_json(
    prompt: str,
    response_schema: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Executes a Gemini prompt and returns parsed JSON.

    Retries up to _MAX_RETRIES times on transient errors (rate limits, 5xx).
    Falls back to the cheaper fallback model on the last retry.
    Returns None when Gemini is disabled, unavailable, or all retries fail,
    which triggers the caller's rule-based fallback logic.
    """

    client = get_client()

    if client is None:
        logger.debug("Gemini is disabled or no API key — using rule-based fallback.")
        return None

    last_error: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        model = GEMINI_FALLBACK_MODEL if attempt == _MAX_RETRIES else GEMINI_MODEL

        try:
            from google.genai import types

            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                ),
            )

            result = json.loads(response.text)
            logger.debug("Gemini responded successfully on attempt %d.", attempt)
            return result

        except Exception as error:
            last_error = error
            is_last_attempt = attempt == _MAX_RETRIES

            if is_last_attempt:
                logger.warning(
                    "Gemini failed after %d attempts. Falling back to rule-based logic. "
                    "Final error: %s",
                    _MAX_RETRIES,
                    error,
                )
            else:
                logger.warning(
                    "Gemini attempt %d/%d failed (%s). Retrying in %ds…",
                    attempt,
                    _MAX_RETRIES,
                    error,
                    _RETRY_DELAY_SECONDS,
                )
                time.sleep(_RETRY_DELAY_SECONDS)

    return None