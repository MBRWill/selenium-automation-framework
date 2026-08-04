"""Dependency-injected profile fact boundary for form resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from modules.forms.models import FormField


@dataclass(frozen=True)
class ProfileFactResult:
    found: bool
    verified: bool
    value: str | bool | None
    profile_key: str | None
    reason_code: str


class ProfileFactProvider(Protocol):
    """Look up candidate facts without exposing a storage implementation."""

    def get_fact(
        self,
        profile_key: str,
        field: FormField,
    ) -> ProfileFactResult:
        ...


class MappingProfileFactProvider:
    """Small injectable provider useful to adapters and offline tests."""

    def __init__(self, facts: Mapping[str, ProfileFactResult]) -> None:
        self._facts = dict(facts)

    def get_fact(
        self,
        profile_key: str,
        field: FormField,
    ) -> ProfileFactResult:
        del field
        return self._facts.get(
            profile_key,
            ProfileFactResult(
                found=False,
                verified=False,
                value=None,
                profile_key=profile_key,
                reason_code="profile_fact_missing",
            ),
        )
