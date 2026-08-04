"""Typed provider boundary; deliberately contains no browser interface."""

from __future__ import annotations

from typing import Protocol

from modules.forms.models import ProviderRequest, ProviderResult


class AnswerProvider(Protocol):
    """Answer one ordinary field from immutable semantic context."""

    def answer(self, request: ProviderRequest) -> ProviderResult:
        ...
