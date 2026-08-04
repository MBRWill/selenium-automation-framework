"""Centralized, environment-only Gemini runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping


DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_OPENAI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/openai/"
)


@dataclass(frozen=True, repr=False)
class GeminiConfig:
    """Resolved Gemini settings with secret-safe diagnostics."""

    configured: bool
    api_key: str | None
    model: str
    reason_code: str

    def __repr__(self) -> str:
        key_state = "<redacted>" if self.api_key else "None"
        return (
            "GeminiConfig("
            f"configured={self.configured!r}, "
            f"api_key={key_state}, "
            f"model={self.model!r}, "
            f"reason_code={self.reason_code!r})"
        )

    __str__ = __repr__

    def diagnostics(self) -> dict[str, bool | str]:
        """Return fields that are safe to print or log."""
        return {
            "configured": self.configured,
            "model": self.model,
            "reason_code": self.reason_code,
        }


def load_gemini_config(
    environ: Mapping[str, str] | None = None,
) -> GeminiConfig:
    """Resolve Gemini settings without loading files or logging secrets."""
    source = os.environ if environ is None else environ
    api_key = str(source.get("GEMINI_API_KEY", "") or "").strip()
    model = (
        str(source.get("GEMINI_MODEL", "") or "").strip()
        or DEFAULT_GEMINI_MODEL
    )
    if not api_key:
        return GeminiConfig(
            configured=False,
            api_key=None,
            model=model,
            reason_code="gemini_api_key_missing",
        )
    return GeminiConfig(
        configured=True,
        api_key=api_key,
        model=model,
        reason_code="gemini_configured",
    )
