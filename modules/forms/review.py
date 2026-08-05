"""Offline review-record boundary with deterministic deduplication."""

from __future__ import annotations

import hashlib
import json
from typing import Protocol

from modules.forms.models import ReviewRecord


class ReviewSink(Protocol):
    """Accept a review record without prescribing persistence."""

    def record(self, record: ReviewRecord) -> bool:
        ...


class InMemoryReviewSink:
    """Application-aware review sink used by offline orchestration and tests."""

    def __init__(self) -> None:
        self._records: list[ReviewRecord] = []
        self._identities: set[str] = set()

    @property
    def records(self) -> tuple[ReviewRecord, ...]:
        return tuple(self._records)

    def record(self, record: ReviewRecord) -> bool:
        identity = self._identity(record)
        if identity in self._identities:
            return False
        self._identities.add(identity)
        self._records.append(record)
        return True

    @staticmethod
    def _identity(record: ReviewRecord) -> str:
        payload = {
            "answer": record.final_answer,
            "application_id": record.application_id,
            "field_key": record.field_key,
            "job_id": record.job_id,
            "source": record.source.value,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
