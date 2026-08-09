"""Fail-open local CSV queue for reviewing provider-backed application answers."""

from __future__ import annotations

import csv
from datetime import datetime
import json
import os
from pathlib import Path
import re
import uuid


CSV_COLUMNS = (
    "run_id",
    "timestamp",
    "job_id",
    "company",
    "job_title",
    "question",
    "field_type",
    "required",
    "visible_options",
    "visible_options_json",
    "proposed_answer",
    "reason_code",
    "provider_request_count",
    "validation_result",
    "application_outcome",
    "review_priority",
    "review_status",
    "corrected_answer",
    "profile_key",
    "profile_action",
    "reviewer_notes",
)

_CONTACT_WORDS = (
    "first name",
    "middle name",
    "last name",
    "full name",
    "email",
    "phone",
    "address",
    "street",
    "identity",
)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d .()/-]{6,}\d)(?!\w)")
_VALID_OUTCOMES = {
    "answer_filled",
    "unresolved_required",
    "validation_failed",
    "application_discarded",
    "safety_warning_skipped",
    "reached_review",
    "submitted",
    "run_interrupted",
}


class AIAnswerReviewQueue:
    """Append-only per-run review CSV. All logging operations are fail-open."""

    def __init__(
        self,
        root: Path | None = None,
        run_id: str | None = None,
        now=None,
        opener=open,
    ) -> None:
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self._now = now or datetime.now
        self._opener = opener
        self._file = None
        self._writer = None
        self._reported_failure = False
        self._provider_backed = 0
        self._unresolved_or_validation = 0
        self._high_priority = 0
        self._row_count = 0
        self._application_keys: set[tuple[str, str, str]] = set()
        self._field_keys: set[tuple[str, str, str, str]] = set()
        timestamp = self._now().strftime("%Y-%m-%d_%H%M%S")
        directory = root or (
            Path(__file__).resolve().parents[2] / "logs" / "ai_answer_review"
        )
        self.path = directory / f"{timestamp}_{self.run_id}.csv"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            self._file = self._opener(
                self.path, "x", encoding="utf-8", newline=""
            )
            self._writer = csv.DictWriter(self._file, fieldnames=CSV_COLUMNS)
            self._writer.writeheader()
            self._flush()
        except (OSError, csv.Error, ValueError, TypeError):
            self._disable()

    @property
    def enabled(self) -> bool:
        return self._writer is not None and self._file is not None

    @property
    def counts(self) -> dict[str, int]:
        return {
            "provider_backed": self._provider_backed,
            "unresolved_or_validation": self._unresolved_or_validation,
            "high_priority": self._high_priority,
            "rows": self._row_count,
        }

    def _report_failure(self) -> None:
        if not self._reported_failure:
            print("AI answer review queue logging unavailable; browser workflow continues.")
            self._reported_failure = True

    def _disable(self) -> None:
        file_handle, self._file, self._writer = self._file, None, None
        if file_handle is not None:
            try:
                file_handle.close()
            except OSError:
                pass
        self._report_failure()

    def _flush(self) -> None:
        if self._file is None:
            return
        self._file.flush()
        os.fsync(self._file.fileno())

    @staticmethod
    def _redact_text(value) -> str:
        text = str(value or "")
        text = _EMAIL_RE.sub("[redacted-email]", text)
        return _PHONE_RE.sub("[redacted-phone]", text)

    @staticmethod
    def _is_contact_question(question: str) -> bool:
        normalized = " ".join(str(question).casefold().split())
        return any(word in normalized for word in _CONTACT_WORDS)

    @staticmethod
    def _priority(
        *,
        field_type: str,
        required: bool,
        answer: str,
        validation_result: str,
        application_outcome: str,
        conflicts_with_verified_fact: bool,
        force_high_priority: bool,
    ) -> str:
        normalized_answer = " ".join(str(answer).casefold().split())
        if conflicts_with_verified_fact or force_high_priority:
            return "high"
        if application_outcome in {
            "unresolved_required",
            "validation_failed",
            "application_discarded",
            "safety_warning_skipped",
        }:
            return "high"
        if validation_result in {"unresolved_required", "validation_failed"}:
            return "high"
        if field_type == "number":
            if required and not normalized_answer:
                return "high"
            try:
                if float(normalized_answer) == 0:
                    return "high"
            except (TypeError, ValueError):
                if required:
                    return "high"
        if field_type in {"select", "radio", "boolean"} and normalized_answer in {
            "no",
            "nope",
        }:
            return "high"
        return "normal"

    def _append(self, row: dict) -> bool:
        if not self.enabled:
            return False
        try:
            self._writer.writerow({column: row.get(column, "") for column in CSV_COLUMNS})
            self._flush()
        except (OSError, csv.Error, ValueError, TypeError):
            self._disable()
            return False
        self._row_count += 1
        if int(row.get("provider_request_count") or 0) > 0:
            self._provider_backed += 1
        if (
            row.get("validation_result")
            in {"unresolved_required", "validation_failed"}
            or row.get("application_outcome")
            in {"unresolved_required", "validation_failed", "application_discarded"}
        ):
            self._unresolved_or_validation += 1
        if row.get("review_priority") == "high":
            self._high_priority += 1
        return True

    @staticmethod
    def _field_key(
        job_id: str, company: str, field_type: str, question: str
    ) -> tuple[str, str, str, str]:
        return (
            str(job_id or ""),
            " ".join(str(company or "").casefold().split()),
            str(field_type or "").casefold(),
            " ".join(str(question or "").casefold().split()),
        )

    def record_answer(
        self,
        *,
        job_id: str = "",
        company: str = "",
        job_title: str = "",
        question: str,
        field_type: str,
        required: bool,
        visible_options: list[str] | None,
        proposed_answer: str | None,
        reason_code: str,
        provider_request_count: int,
        validation_result: str,
        application_outcome: str,
        conflicts_with_verified_fact: bool = False,
        record_without_provider: bool = False,
        force_high_priority: bool = False,
        force_normal_priority: bool = False,
        reviewer_notes: str = "",
    ) -> bool:
        if provider_request_count <= 0 and not record_without_provider:
            return False
        field_key = self._field_key(job_id, company, field_type, question)
        if field_key in self._field_keys:
            return False
        if application_outcome not in _VALID_OUTCOMES:
            application_outcome = "validation_failed"
        contact_question = self._is_contact_question(question)
        safe_question = (
            "[redacted-contact-question]"
            if contact_question
            else self._redact_text(question)
        )
        safe_answer = (
            "[redacted]"
            if contact_question
            else self._redact_text(proposed_answer)
        )
        safe_options = [] if contact_question else [
            self._redact_text(option) for option in (visible_options or [])
        ]
        priority = self._priority(
            field_type=field_type,
            required=required,
            answer=safe_answer,
            validation_result=validation_result,
            application_outcome=application_outcome,
            conflicts_with_verified_fact=conflicts_with_verified_fact,
            force_high_priority=force_high_priority,
        )
        if force_normal_priority:
            priority = "normal"
        row = {
            "run_id": self.run_id,
            "timestamp": self._now().isoformat(timespec="seconds"),
            "job_id": str(job_id or ""),
            "company": self._redact_text(company),
            "job_title": self._redact_text(job_title),
            "question": safe_question,
            "field_type": field_type,
            "required": str(bool(required)).lower(),
            "visible_options": json.dumps(safe_options, ensure_ascii=False),
            "visible_options_json": json.dumps(safe_options, ensure_ascii=False),
            "proposed_answer": safe_answer,
            "reason_code": reason_code,
            "provider_request_count": provider_request_count,
            "validation_result": validation_result,
            "application_outcome": application_outcome,
            "review_priority": priority,
            "review_status": "pending",
            "corrected_answer": "",
            "profile_key": "",
            "profile_action": "",
            "reviewer_notes": self._redact_text(reviewer_notes),
        }
        if self._append(row):
            self._field_keys.add(field_key)
            self._application_keys.add((str(job_id), str(company), str(job_title)))
            return True
        return False

    def record_required_event(
        self,
        *,
        job_id: str = "",
        company: str = "",
        job_title: str = "",
        question: str,
        field_type: str,
        visible_options: list[str] | None,
        reason_code: str,
        validation_result: str = "unresolved_required",
        application_outcome: str = "unresolved_required",
    ) -> bool:
        field_key = self._field_key(job_id, company, field_type, question)
        if field_key in self._field_keys:
            return False
        priority = self._priority(
            field_type=field_type,
            required=True,
            answer="",
            validation_result=validation_result,
            application_outcome=application_outcome,
            conflicts_with_verified_fact=False,
            force_high_priority=False,
        )
        contact_question = self._is_contact_question(question)
        row = {
            "run_id": self.run_id,
            "timestamp": self._now().isoformat(timespec="seconds"),
            "job_id": str(job_id or ""),
            "company": self._redact_text(company),
            "job_title": self._redact_text(job_title),
            "question": (
                "[redacted-contact-question]"
                if contact_question
                else self._redact_text(question)
            ),
            "field_type": field_type,
            "required": "true",
            "visible_options": json.dumps(
                [] if contact_question else [
                    self._redact_text(option) for option in (visible_options or [])
                ],
                ensure_ascii=False,
            ),
            "visible_options_json": json.dumps(
                [] if contact_question else [
                    self._redact_text(option) for option in (visible_options or [])
                ],
                ensure_ascii=False,
            ),
            "proposed_answer": "",
            "reason_code": reason_code,
            "provider_request_count": 0,
            "validation_result": validation_result,
            "application_outcome": application_outcome,
            "review_priority": priority,
            "review_status": "pending",
            "corrected_answer": "",
            "profile_key": "",
            "profile_action": "",
            "reviewer_notes": "",
        }
        if self._append(row):
            self._field_keys.add(field_key)
            self._application_keys.add((str(job_id), str(company), str(job_title)))
            return True
        return False

    def record_outcome(
        self,
        application_outcome: str,
        *,
        job_id: str = "",
        company: str = "",
        job_title: str = "",
        reason_code: str = "",
    ) -> bool:
        key = (str(job_id), str(company), str(job_title))
        standalone_reason = reason_code in {
            "failed_question_unresolved",
            "job_search_safety_reminder",
            "final_review_detected_from_submit_button",
            "easy_apply_modal_cleanup_failed",
            "post_apply_success_modal_cleanup_failed",
        }
        if application_outcome not in _VALID_OUTCOMES or (
            key not in self._application_keys and not standalone_reason
        ):
            return False
        priority = self._priority(
            field_type="event",
            required=False,
            answer="",
            validation_result="",
            application_outcome=application_outcome,
            conflicts_with_verified_fact=False,
            force_high_priority=False,
        )
        return self._append({
            "run_id": self.run_id,
            "timestamp": self._now().isoformat(timespec="seconds"),
            "job_id": str(job_id or ""),
            "company": self._redact_text(company),
            "job_title": self._redact_text(job_title),
            "question": "",
            "field_type": "event",
            "required": "false",
            "visible_options": "[]",
            "visible_options_json": "[]",
            "proposed_answer": "",
            "reason_code": reason_code,
            "provider_request_count": 0,
            "validation_result": "",
            "application_outcome": application_outcome,
            "review_priority": priority,
            "review_status": "pending",
            "corrected_answer": "",
            "profile_key": "",
            "profile_action": "",
            "reviewer_notes": "",
        })

    def record_run_interrupted(self) -> bool:
        if self._row_count == 0:
            return False
        return self._append({
            "run_id": self.run_id,
            "timestamp": self._now().isoformat(timespec="seconds"),
            "question": "",
            "field_type": "event",
            "required": "false",
            "visible_options": "[]",
            "visible_options_json": "[]",
            "proposed_answer": "",
            "reason_code": "run_interrupted",
            "provider_request_count": 0,
            "validation_result": "",
            "application_outcome": "run_interrupted",
            "review_priority": "normal",
            "review_status": "pending",
            "corrected_answer": "",
            "profile_key": "",
            "profile_action": "",
            "reviewer_notes": "",
        })

    def print_summary(self) -> None:
        print("AI answer review queue")
        print(f"- Provider-backed answers: {self._provider_backed}")
        print(f"- Unresolved/validation events: {self._unresolved_or_validation}")
        print(f"- High-priority rows: {self._high_priority}")
        print(f"- Review file: {self.path if self.enabled or self.path.exists() else 'unavailable'}")

    def close(self) -> None:
        file_handle, self._file, self._writer = self._file, None, None
        if file_handle is not None:
            try:
                file_handle.flush()
                os.fsync(file_handle.fileno())
                file_handle.close()
            except OSError:
                self._report_failure()
