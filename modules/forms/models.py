"""Immutable domain models for form answering and validation repair."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import json


class FieldKind(str, Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    SELECT = "select"
    RADIO = "radio"
    CHECKBOX = "checkbox"


class AnswerStatus(str, Enum):
    PRESERVED = "preserved"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


class AnswerSource(str, Enum):
    LINKEDIN = "linkedin"
    PROFILE = "profile"
    POLICY = "policy"
    PROVIDER = "provider"
    DEFAULT = "default"
    NONE = "none"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ValidationIssueKind(str, Enum):
    VALID = "valid"
    MISSING_VALUE = "missing_value"
    WRONG_TYPE = "wrong_type"
    BELOW_MINIMUM = "below_minimum"
    ABOVE_MAXIMUM = "above_maximum"
    STEP_MISMATCH = "step_mismatch"
    TEXT_TOO_SHORT = "text_too_short"
    TEXT_TOO_LONG = "text_too_long"
    OPTION_REQUIRED = "option_required"
    OPTION_NOT_AVAILABLE = "option_not_available"
    INVALID_FORMAT = "invalid_format"
    UNKNOWN_VALIDATION_ERROR = "unknown_validation_error"


class RepairStatus(str, Enum):
    UNCHANGED = "unchanged"
    REPAIRED = "repaired"
    RETRY_REQUIRED = "retry_required"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class FieldConstraints:
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    step: Decimal | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None

    def __post_init__(self) -> None:
        if self.step is not None and self.step <= 0:
            raise ValueError("step must be positive")
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError("min_value must not exceed max_value")
        if self.min_length is not None and self.min_length < 0:
            raise ValueError("min_length must not be negative")
        if self.max_length is not None and self.max_length < 0:
            raise ValueError("max_length must not be negative")
        if (
            self.min_length is not None
            and self.max_length is not None
            and self.min_length > self.max_length
        ):
            raise ValueError("min_length must not exceed max_length")


@dataclass(frozen=True)
class FormField:
    field_key: str
    kind: FieldKind
    question: str
    required: bool = False
    existing_value: str | bool | None = None
    constraints: FieldConstraints = FieldConstraints()
    visible_options: tuple[str, ...] = ()
    exact_fact_only: bool = False
    profile_key: str | None = None
    allow_yes_no_default: bool = True
    numeric_default: str | None = None
    candidate_context: tuple[tuple[str, str], ...] = ()
    job_id: str = ""
    company: str = ""
    job_title: str = ""

    def __post_init__(self) -> None:
        if not self.field_key.strip():
            raise ValueError("field_key is required")


@dataclass(frozen=True)
class AnswerResult:
    status: AnswerStatus
    value: str | bool | None
    source: AnswerSource
    confidence: Confidence
    reason_code: str
    profile_key: str | None = None
    requires_review: bool = False
    provider_request_count: int = 0

    @property
    def accepted(self) -> bool:
        return (
            self.status in {AnswerStatus.PRESERVED, AnswerStatus.RESOLVED}
            and self.value is not None
        )


@dataclass(frozen=True)
class ValidationIssue:
    field_key: str
    issue_kind: ValidationIssueKind
    message: str
    rejected_value: str | bool | None
    constraints: FieldConstraints
    visible_options: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.field_key.strip():
            raise ValueError("field_key is required")


@dataclass(frozen=True)
class RepairRequest:
    field: FormField
    previous_answer: AnswerResult | None
    validation_issue: ValidationIssue
    attempt_number: int

    def __post_init__(self) -> None:
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be at least 1")
        if self.field.field_key != self.validation_issue.field_key:
            raise ValueError("validation issue does not belong to field")


@dataclass(frozen=True)
class ProviderRequest:
    field_key: str
    question: str
    field_kind: FieldKind
    required: bool
    rejected_value: str | bool | None
    previous_answer: AnswerResult | None
    validation_issue_kind: ValidationIssueKind | None
    validation_message: str
    constraints: FieldConstraints
    visible_options: tuple[str, ...]
    candidate_context: tuple[tuple[str, str], ...]
    attempt_number: int


@dataclass(frozen=True)
class ProviderResult:
    answered: bool
    value: str | bool | None
    confidence: Confidence
    reason_code: str
    request_count: int = 1

    def __post_init__(self) -> None:
        if self.request_count < 0:
            raise ValueError("request_count must not be negative")


@dataclass(frozen=True)
class RepairResult:
    status: RepairStatus
    answer_result: AnswerResult | None
    changed: bool
    reason_code: str
    requires_review: bool


@dataclass(frozen=True)
class ReviewRecord:
    job_id: str
    company: str
    job_title: str
    field_key: str
    original_question: str
    normalized_question: str
    field_kind: FieldKind
    required: bool
    visible_options: tuple[str, ...]
    final_answer: str | bool
    source: AnswerSource
    confidence: Confidence
    reason_code: str
    requires_review: bool
    validation_message: str
    provider_request_count: int = 0
    review_status: str = "pending"

    def as_excel_row(self) -> dict[str, str]:
        """Return scalar values for a later CSV/Excel persistence adapter."""
        return {
            "job_id": self.job_id,
            "company": self.company,
            "job_title": self.job_title,
            "field_key": self.field_key,
            "original_question": self.original_question,
            "normalized_question": self.normalized_question,
            "field_type": self.field_kind.value,
            "required": str(self.required).lower(),
            "visible_options_json": json.dumps(
                self.visible_options, ensure_ascii=False
            ),
            "final_answer": str(self.final_answer),
            "source": self.source.value,
            "confidence": self.confidence.value,
            "reason_code": self.reason_code,
            "requires_review": str(self.requires_review).lower(),
            "validation_message": self.validation_message,
            "provider_request_count": str(self.provider_request_count),
            "review_status": self.review_status,
        }
