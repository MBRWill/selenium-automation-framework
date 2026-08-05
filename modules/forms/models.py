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


class WriteStatus(str, Enum):
    SKIPPED_PRESERVED = "skipped_preserved"
    WRITTEN = "written"
    VERIFIED = "verified"
    RETRY_REQUIRED = "retry_required"
    FAILED = "failed"


class OrchestratorStatus(str, Enum):
    READY_FOR_NAVIGATION = "ready_for_navigation"
    RETRY_REQUIRED = "retry_required"
    BLOCKED_PROTECTED_FACT = "blocked_protected_fact"
    BLOCKED_TYPE_IMPOSSIBLE = "blocked_type_impossible"
    FAILED = "failed"


class FieldProcessingStatus(str, Enum):
    PRESERVED = "preserved"
    WRITTEN = "written"
    REPAIRED = "repaired"
    VALID = "valid"
    BLOCKED = "blocked"
    FAILED = "failed"


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
    application_id: str = ""

    def as_excel_row(self) -> dict[str, str]:
        """Return scalar values for a later CSV/Excel persistence adapter."""
        return {
            "application_id": self.application_id,
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


@dataclass(frozen=True)
class ControlOption:
    text: str
    value: str
    selector: str = ""
    visible: bool = True
    enabled: bool = True
    selected: bool = False
    placeholder: bool = False


@dataclass(frozen=True, repr=False)
class ControlValidity:
    browser_valid: bool = True
    validation_message: str = ""
    aria_invalid: bool | None = None
    value_missing: bool = False
    type_mismatch: bool = False
    range_underflow: bool = False
    range_overflow: bool = False
    step_mismatch: bool = False
    too_short: bool = False
    too_long: bool = False

    def __repr__(self) -> str:
        return (
            "ControlValidity("
            f"browser_valid={self.browser_valid!r}, "
            f"aria_invalid={self.aria_invalid!r}, "
            f"value_missing={self.value_missing!r})"
        )


@dataclass(frozen=True, repr=False)
class ControlSnapshot:
    container_selector: str
    control_selector: str
    option_selectors: tuple[str, ...]
    tag_name: str
    input_type: str
    labels: tuple[str, ...]
    accessible_text: str
    attributes: tuple[tuple[str, str], ...]
    current_value: str | bool | None
    required: bool
    checked: bool | None
    options: tuple[ControlOption, ...]
    constraints: FieldConstraints
    validity: ControlValidity

    def __repr__(self) -> str:
        return (
            "ControlSnapshot("
            f"tag_name={self.tag_name!r}, input_type={self.input_type!r}, "
            f"required={self.required!r}, options={len(self.options)}, "
            f"has_value={self.current_value is not None})"
        )


@dataclass(frozen=True, repr=False)
class FieldLocator:
    container_selector: str
    control_selector: str
    option_selectors: tuple[str, ...] = ()
    stable_attributes: tuple[tuple[str, str], ...] = ()

    _SAFE_ATTRIBUTE_NAMES = frozenset({
        "id",
        "name",
        "type",
        "role",
        "autocomplete",
        "aria-describedby",
        "data-test-id",
        "data-test-form-element",
    })

    def __post_init__(self) -> None:
        selectors = (
            self.container_selector,
            self.control_selector,
            *self.option_selectors,
        )
        if not self.control_selector.strip():
            raise ValueError("control_selector is required")
        if any("<" in item or ">" in item or len(item) > 512 for item in selectors):
            raise ValueError("locators must contain selectors, not page markup")
        if any(name not in self._SAFE_ATTRIBUTE_NAMES for name, _ in self.stable_attributes):
            raise ValueError("stable_attributes contains a non-safe attribute")

    def __repr__(self) -> str:
        return (
            "FieldLocator("
            f"has_container={bool(self.container_selector)!r}, "
            f"option_count={len(self.option_selectors)}, "
            f"stable_attribute_count={len(self.stable_attributes)})"
        )


@dataclass(frozen=True)
class ExtractionContext:
    application_id: str = ""
    job_id: str = ""
    company: str = ""
    job_title: str = ""


@dataclass(frozen=True, repr=False)
class ValidationState:
    browser_valid: bool
    validation_message: str
    aria_invalid: bool | None
    required_missing: bool
    type_mismatch: bool
    range_underflow: bool
    range_overflow: bool
    step_mismatch: bool
    too_short: bool
    too_long: bool
    option_required: bool

    def __repr__(self) -> str:
        return (
            "ValidationState("
            f"browser_valid={self.browser_valid!r}, "
            f"aria_invalid={self.aria_invalid!r}, "
            f"required_missing={self.required_missing!r})"
        )


@dataclass(frozen=True, repr=False)
class ExtractedField:
    field: FormField
    locator: FieldLocator
    normalized_question: str
    validation_state: ValidationState
    safe_metadata: tuple[tuple[str, str], ...] = ()

    def __repr__(self) -> str:
        return (
            "ExtractedField("
            f"field_key={self.field.field_key!r}, kind={self.field.kind.value!r}, "
            f"required={self.field.required!r}, "
            f"has_existing_value={self.field.existing_value is not None})"
        )


@dataclass(frozen=True, repr=False)
class WriteRequest:
    extracted_field: ExtractedField
    answer_result: AnswerResult

    def __repr__(self) -> str:
        return (
            "WriteRequest("
            f"field_key={self.extracted_field.field.field_key!r}, "
            f"status={self.answer_result.status.value!r}, "
            f"source={self.answer_result.source.value!r}, "
            f"answer={_diagnostic_value(self.answer_result.value)})"
        )


@dataclass(frozen=True, repr=False)
class WriteResult:
    status: WriteStatus
    attempted_value: str | bool | None
    verified_value: str | bool | None
    changed: bool
    retry_count: int
    reason_code: str

    def __post_init__(self) -> None:
        if self.retry_count < 0 or self.retry_count > 1:
            raise ValueError("retry_count must be zero or one")

    def __repr__(self) -> str:
        return (
            "WriteResult("
            f"status={self.status.value!r}, "
            f"attempted_value={_diagnostic_value(self.attempted_value)}, "
            f"verified_value={_diagnostic_value(self.verified_value)}, "
            f"changed={self.changed!r}, retry_count={self.retry_count}, "
            f"reason_code={self.reason_code!r})"
        )


def _diagnostic_value(value: str | bool | None) -> str:
    if isinstance(value, bool) or value is None:
        return repr(value)
    return f"<text length={len(str(value))}>"


@dataclass(frozen=True, repr=False)
class FieldProcessingResult:
    field_key: str
    status: FieldProcessingStatus
    answer_result: AnswerResult | None
    write_result: WriteResult | None
    validation_issues: tuple[ValidationIssue, ...]
    repair_attempts: int
    review_recorded: bool
    reason_code: str

    def __post_init__(self) -> None:
        if self.repair_attempts < 0:
            raise ValueError("repair_attempts must not be negative")

    def __repr__(self) -> str:
        return (
            "FieldProcessingResult("
            f"field_key={self.field_key!r}, status={self.status.value!r}, "
            f"has_answer={self.answer_result is not None!r}, "
            f"has_write_result={self.write_result is not None!r}, "
            f"validation_issue_count={len(self.validation_issues)}, "
            f"repair_attempts={self.repair_attempts}, "
            f"review_recorded={self.review_recorded!r}, "
            f"reason_code={self.reason_code!r})"
        )


@dataclass(frozen=True, repr=False)
class FormPageResult:
    status: OrchestratorStatus
    field_results: tuple[FieldProcessingResult, ...]
    unresolved_fields: tuple[str, ...]
    validation_issues: tuple[ValidationIssue, ...]
    review_records: tuple[ReviewRecord, ...]
    provider_request_count: int
    repair_rounds: int
    reason_code: str

    def __post_init__(self) -> None:
        if self.provider_request_count < 0:
            raise ValueError("provider_request_count must not be negative")
        if self.repair_rounds < 0:
            raise ValueError("repair_rounds must not be negative")

    def __repr__(self) -> str:
        return (
            "FormPageResult("
            f"status={self.status.value!r}, "
            f"field_count={len(self.field_results)}, "
            f"unresolved_count={len(self.unresolved_fields)}, "
            f"validation_issue_count={len(self.validation_issues)}, "
            f"review_record_count={len(self.review_records)}, "
            f"provider_request_count={self.provider_request_count}, "
            f"repair_rounds={self.repair_rounds}, "
            f"reason_code={self.reason_code!r})"
        )
