"""Opt-in, non-personal Gemini provider smoke test."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openai import OpenAI

from modules.ai.gemini_config import (
    GEMINI_OPENAI_ENDPOINT,
    GeminiConfig,
    load_gemini_config,
)


def _request_failure_category(error: Exception) -> str:
    status_code = getattr(error, "status_code", None)
    if status_code in {401, 403}:
        return "authentication_or_permission_error"
    if status_code == 429:
        return "rate_limited"
    if isinstance(status_code, int) and status_code >= 500:
        return "provider_unavailable"
    if isinstance(error, (TimeoutError, ConnectionError)):
        return "network_or_timeout_error"
    return "provider_request_error"


def run_smoke_test(
    config: GeminiConfig | None = None,
    *,
    client_factory=None,
    output: Callable[[str], None] = print,
) -> int:
    """Run one explicit provider request without printing secret or response data."""
    resolved = config or load_gemini_config()
    output(f"configured={str(resolved.configured).lower()}")
    output(f"model={resolved.model}")

    if not resolved.configured:
        output("provider_initialization=skipped")
        output("request_result=not_run")
        output(f"request_category={resolved.reason_code}")
        return 0

    factory = client_factory or OpenAI
    try:
        client = factory(
            api_key=resolved.api_key,
            base_url=GEMINI_OPENAI_ENDPOINT,
            max_retries=0,
        )
    except Exception:
        output("provider_initialization=failed")
        output("request_result=not_run")
        output("request_category=provider_initialization_error")
        return 1

    output("provider_initialization=succeeded")
    try:
        client.chat.completions.create(
            model=resolved.model,
            messages=[
                {
                    "role": "user",
                    "content": "Reply with exactly the word OK.",
                }
            ],
            temperature=0,
        )
    except Exception as error:
        output("request_result=failure")
        output(f"request_category={_request_failure_category(error)}")
        return 1

    output("request_result=success")
    output("request_category=none")
    return 0


def main() -> int:
    return run_smoke_test()


if __name__ == "__main__":
    raise SystemExit(main())
