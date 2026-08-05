"""Pure answer resolution and bounded, per-field validation repair."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
import re
from typing import Protocol
import unicodedata

from modules.forms.models import (
    AnswerResult,
    AnswerSource,
    AnswerStatus,
    Confidence,
    FieldConstraints,
    FieldKind,
    FormField,
    ProviderRequest,
    ProviderResult,
    RepairRequest,
    RepairResult,
    RepairStatus,
    ReviewRecord,
    ValidationIssueKind,
)
from modules.forms.policies import PolicyDecision, SemanticPolicy, TruthPolicy, normalize_question
from modules.forms.profile import ProfileFactProvider
from modules.forms.provider import AnswerProvider


class ReviewQueue(Protocol):
    """Accept an immutable record; persistence is outside this milestone."""

    def record(self, record: ReviewRecord) -> None:
        ...


class AnswerResolver:
    """Application-scoped resolver with explicit truth and fallback policy."""

    def __init__(
        self,
        review_queue: ReviewQueue | None = None,
        policy: SemanticPolicy | None = None,
    ) -> None:
        self._review_queue = review_queue
        self._policy = policy or SemanticPolicy()
        self._repair_cache: dict[tuple, RepairResult] = {}
        self._provider_cache: dict[tuple, ProviderResult] = {}
        self._recorded_reviews: set[tuple] = set()

    def resolve(
        self,
        field: FormField,
        profile: ProfileFactProvider,
        provider: AnswerProvider | None,
    ) -> AnswerResult:
        """Resolve one field using the complete, ordered answer policy."""
        decision = self._policy.classify(field)

        # Protected facts are reconciled against verified profile truth even
        # when a syntactically valid value was pre-filled by the page.
        if decision.exact_only:
            exact = self._profile_answer(field, profile, decision)
            if exact is None:
                return self._unresolved(field, "protected_exact_fact_unavailable")
            if self._value_valid(field, field.existing_value) and self._same_value(
                self._canonical_value(field, field.existing_value), exact.value
            ):
                return self._preserved(field)
            return exact

        if self._value_valid(field, field.existing_value):
            return self._preserved(field)

        preset = self._profile_answer(field, profile, decision)
        if preset is not None:
            return preset

        policy_answer = self._policy_answer(field, decision)
        if policy_answer is not None:
            return policy_answer

        proposed: ProviderResult | None = None
        if provider is not None and decision.allow_provider:
            request = self._provider_request(
                field=field,
                rejected_value=field.existing_value,
                previous_answer=None,
                validation_issue_kind=None,
                validation_message="",
                attempt_number=1,
            )
            proposed = self._call_provider(provider, request)
            accepted = self._accepted_provider_answer(field, proposed)
            if accepted is not None:
                self._record_resolution_once(field, accepted)
                return accepted

        fallback = self._final_ordinary_fallback(field, decision, proposed)
        if fallback is not None:
            self._record_resolution_once(field, fallback)
            return fallback
        return self._unresolved(field, "ordinary_answer_unsafe_or_type_impossible")

    def repair(
        self,
        request: RepairRequest,
        profile: ProfileFactProvider,
        provider: AnswerProvider | None,
    ) -> RepairResult:
        """Repair only the field named by the actual validation issue."""
        issue = request.validation_issue
        cache_key = self._repair_cache_key(request)
        cached = self._repair_cache.get(cache_key)
        if cached is not None:
            return cached

        if issue.issue_kind is ValidationIssueKind.VALID:
            result = RepairResult(
                status=RepairStatus.UNCHANGED,
                answer_result=request.previous_answer,
                changed=False,
                reason_code="field_already_valid",
                requires_review=bool(
                    request.previous_answer and request.previous_answer.requires_review
                ),
            )
            self._repair_cache[cache_key] = result
            return result

        field = replace(
            request.field,
            constraints=issue.constraints,
            visible_options=issue.visible_options or request.field.visible_options,
        )
        decision = self._policy.classify(field)

        exact_or_preset = self._profile_answer(field, profile, decision)
        if exact_or_preset is not None:
            return self._finish_repair(
                request, cache_key, exact_or_preset, "verified_profile_repair"
            )
        if decision.exact_only:
            return self._cache_unresolved(
                cache_key, "protected_exact_fact_unavailable"
            )

        policy_answer = self._policy_answer(field, decision)
        if policy_answer is not None:
            return self._finish_repair(
                request, cache_key, policy_answer, policy_answer.reason_code
            )

        if request.attempt_number < 2:
            deterministic = self._deterministic_repair(request, field)
            if deterministic is not None:
                return self._finish_repair(
                    request, cache_key, deterministic, deterministic.reason_code
                )
            result = RepairResult(
                status=RepairStatus.RETRY_REQUIRED,
                answer_result=request.previous_answer,
                changed=False,
                reason_code="ordinary_field_provider_repair_required",
                requires_review=False,
            )
            self._repair_cache[cache_key] = result
            return result

        proposed: ProviderResult | None = None
        if provider is not None and decision.allow_provider:
            provider_request = self._provider_request(
                field=field,
                rejected_value=issue.rejected_value,
                previous_answer=request.previous_answer,
                validation_issue_kind=issue.issue_kind,
                validation_message=issue.message,
                attempt_number=request.attempt_number,
            )
            proposed = self._call_provider(provider, provider_request)
            accepted = self._accepted_provider_answer(field, proposed)
            if accepted is not None:
                return self._finish_repair(
                    request, cache_key, accepted, "provider_validation_repair"
                )

        fallback = self._final_ordinary_fallback(field, decision, proposed)
        if fallback is not None:
            return self._finish_repair(
                request, cache_key, fallback, fallback.reason_code
            )
        return self._cache_unresolved(
            cache_key, "ordinary_repair_unsafe_or_type_impossible"
        )

    def _preserved(self, field: FormField) -> AnswerResult:
        return AnswerResult(
            status=AnswerStatus.PRESERVED,
            value=self._canonical_value(field, field.existing_value),
            source=AnswerSource.LINKEDIN,
            confidence=Confidence.HIGH,
            reason_code="valid_linkedin_value",
            profile_key=field.profile_key,
            requires_review=False,
        )

    def _profile_answer(
        self,
        field: FormField,
        profile: ProfileFactProvider,
        decision: PolicyDecision,
    ) -> AnswerResult | None:
        profile_key = field.profile_key or decision.profile_key
        if not profile_key:
            return None
        try:
            fact = profile.get_fact(profile_key, field)
        except Exception:
            return None
        if not fact.found or not fact.verified or fact.value is None:
            return None
        value = self._canonical_value(field, fact.value)
        if value is None or not self._value_valid(field, value):
            return None
        return AnswerResult(
            status=AnswerStatus.RESOLVED,
            value=value,
            source=AnswerSource.PROFILE,
            confidence=Confidence.HIGH,
            reason_code=fact.reason_code or "verified_profile_fact",
            profile_key=fact.profile_key or profile_key,
            requires_review=False,
        )

    def _policy_answer(
        self,
        field: FormField,
        decision: PolicyDecision,
    ) -> AnswerResult | None:
        if decision.truth_policy is not TruthPolicy.DETERMINISTIC:
            return None
        value = self._canonical_value(field, decision.deterministic_answer)
        if value is None or not self._value_valid(field, value):
            return None
        return self._resolved(value, AnswerSource.POLICY, decision.reason_code)

    def _deterministic_repair(
        self,
        request: RepairRequest,
        field: FormField,
    ) -> AnswerResult | None:
        issue = request.validation_issue
        rejected = issue.rejected_value
        if field.kind is FieldKind.NUMBER:
            repaired = self._compatible_number(
                rejected, field.constraints, field.numeric_default
            )
            if repaired is not None:
                return self._resolved(
                    repaired, AnswerSource.POLICY, "numeric_constraint_repair"
                )
        if field.kind in {FieldKind.TEXT, FieldKind.TEXTAREA} and issue.issue_kind in {
            ValidationIssueKind.TEXT_TOO_SHORT,
            ValidationIssueKind.TEXT_TOO_LONG,
        }:
            repaired = self._compatible_text(rejected, field.constraints)
            if repaired is not None and self._value_valid(field, repaired):
                return self._resolved(
                    repaired, AnswerSource.POLICY, "text_length_repair"
                )
        if field.kind in {FieldKind.SELECT, FieldKind.RADIO}:
            matched = self._match_option(rejected, field.visible_options)
            if matched is not None:
                return self._resolved(
                    matched, AnswerSource.POLICY, "visible_option_remap"
                )
            available = self._available_options(field.visible_options)
            if (
                issue.issue_kind
                in {ValidationIssueKind.MISSING_VALUE, ValidationIssueKind.OPTION_REQUIRED}
                and len(available) == 1
                and (
                    field.allow_yes_no_default
                    or self._normalized(available[0]) not in {"yes", "si"}
                )
            ):
                return self._resolved(
                    available[0],
                    AnswerSource.DEFAULT,
                    "only_visible_option_default",
                    requires_review=True,
                )
        if field.kind is FieldKind.CHECKBOX and field.required and field.allow_yes_no_default:
            return self._resolved(
                True,
                AnswerSource.DEFAULT,
                "required_ordinary_checkbox_default",
                requires_review=True,
            )
        return None

    def _provider_request(
        self,
        *,
        field: FormField,
        rejected_value: str | bool | None,
        previous_answer: AnswerResult | None,
        validation_issue_kind: ValidationIssueKind | None,
        validation_message: str,
        attempt_number: int,
    ) -> ProviderRequest:
        return ProviderRequest(
            field_key=field.field_key,
            question=field.question,
            field_kind=field.kind,
            required=field.required,
            rejected_value=rejected_value,
            previous_answer=previous_answer,
            validation_issue_kind=validation_issue_kind,
            validation_message=validation_message,
            constraints=field.constraints,
            visible_options=field.visible_options,
            candidate_context=field.candidate_context,
            attempt_number=attempt_number,
        )

    def _call_provider(
        self,
        provider: AnswerProvider,
        request: ProviderRequest,
    ) -> ProviderResult:
        key = (
            request.field_key,
            request.field_kind,
            request.validation_issue_kind,
            request.validation_message,
            self._stable_value(request.rejected_value),
            request.constraints,
            request.visible_options,
            request.candidate_context,
        )
        cached = self._provider_cache.get(key)
        if cached is not None:
            return cached
        try:
            result = provider.answer(request)
        except Exception:
            result = ProviderResult(
                answered=False,
                value=None,
                confidence=Confidence.NONE,
                reason_code="provider_request_failed",
                request_count=1,
            )
        self._provider_cache[key] = result
        return result

    def _accepted_provider_answer(
        self,
        field: FormField,
        proposed: ProviderResult | None,
    ) -> AnswerResult | None:
        if proposed is None or not proposed.answered or proposed.value is None:
            return None
        value: str | bool | None
        if field.kind is FieldKind.NUMBER:
            if self._decimal(proposed.value) is None:
                return None
            value = self._compatible_number(proposed.value, field.constraints)
        elif field.kind in {FieldKind.TEXT, FieldKind.TEXTAREA}:
            value = self._compatible_text(proposed.value, field.constraints)
        else:
            value = self._canonical_value(field, proposed.value)
        if value is None or not self._value_valid(field, value):
            return None
        return AnswerResult(
            status=AnswerStatus.RESOLVED,
            value=value,
            source=AnswerSource.PROVIDER,
            confidence=proposed.confidence,
            reason_code=proposed.reason_code or "provider_answer",
            requires_review=True,
            provider_request_count=proposed.request_count,
        )

    def _final_ordinary_fallback(
        self,
        field: FormField,
        decision: PolicyDecision,
        rejected_provider_answer: ProviderResult | None,
    ) -> AnswerResult | None:
        if decision.exact_only:
            return None
        provider_request_count = (
            rejected_provider_answer.request_count
            if rejected_provider_answer is not None
            else 0
        )
        if field.kind is FieldKind.NUMBER:
            value = self._compatible_number(None, field.constraints, field.numeric_default)
            if value is not None:
                return self._resolved(
                    value,
                    AnswerSource.DEFAULT,
                    "provider_non_numeric_value_repaired"
                    if rejected_provider_answer is not None
                    else "numeric_best_effort_default",
                    requires_review=True,
                    provider_request_count=provider_request_count,
                )
        if field.kind in {FieldKind.TEXT, FieldKind.TEXTAREA} and field.required:
            value = self._compatible_text("Not provided", field.constraints)
            if value is not None and self._value_valid(field, value):
                return self._resolved(
                    value,
                    AnswerSource.DEFAULT,
                    "required_text_best_effort_default",
                    requires_review=True,
                    provider_request_count=provider_request_count,
                )
        if field.kind in {FieldKind.SELECT, FieldKind.RADIO}:
            positive = self._positive_option(field.visible_options)
            negative = self._negative_option(field.visible_options)
            is_yes_no = positive is not None and negative is not None
            if positive is not None and decision.allow_yes_no_default:
                return self._resolved(
                    positive,
                    AnswerSource.DEFAULT,
                    "ordinary_yes_default",
                    requires_review=True,
                    provider_request_count=provider_request_count,
                )
            available = self._available_options(field.visible_options)
            if field.required and available and not is_yes_no:
                return self._resolved(
                    available[0],
                    AnswerSource.DEFAULT,
                    "required_visible_option_default",
                    requires_review=True,
                    provider_request_count=provider_request_count,
                )
        if field.kind is FieldKind.CHECKBOX and field.required and decision.allow_yes_no_default:
            return self._resolved(
                True,
                AnswerSource.DEFAULT,
                "required_ordinary_checkbox_default",
                requires_review=True,
                provider_request_count=provider_request_count,
            )
        return None

    def _finish_repair(
        self,
        request: RepairRequest,
        cache_key: tuple,
        answer: AnswerResult,
        reason_code: str,
    ) -> RepairResult:
        result = RepairResult(
            status=RepairStatus.REPAIRED,
            answer_result=answer,
            changed=not self._same_value(
                request.validation_issue.rejected_value, answer.value
            ),
            reason_code=reason_code,
            requires_review=answer.requires_review,
        )
        self._repair_cache[cache_key] = result
        issue = request.validation_issue
        review_context = (
            request.field.field_key,
            issue.issue_kind,
            issue.message,
            self._stable_value(issue.rejected_value),
            issue.constraints,
            issue.visible_options,
        )
        review_field = replace(
            request.field,
            constraints=issue.constraints,
            visible_options=issue.visible_options or request.field.visible_options,
        )
        self._record_review_once(
            review_field, answer, issue.message, review_context
        )
        return result

    def _record_resolution_once(self, field: FormField, answer: AnswerResult) -> None:
        self._record_review_once(field, answer, "", ("initial_resolution", field.field_key))

    def _record_review_once(
        self,
        field: FormField,
        answer: AnswerResult,
        validation_message: str,
        context_key: tuple,
    ) -> None:
        if (
            self._review_queue is None
            or answer.source not in {AnswerSource.PROVIDER, AnswerSource.DEFAULT}
            or not answer.accepted
        ):
            return
        key = (
            context_key,
            self._stable_value(answer.value),
            answer.source,
            answer.reason_code,
        )
        if key in self._recorded_reviews:
            return
        self._recorded_reviews.add(key)
        record = ReviewRecord(
            job_id=field.job_id,
            company=field.company,
            job_title=field.job_title,
            field_key=field.field_key,
            original_question=field.question,
            normalized_question=normalize_question(field.question),
            field_kind=field.kind,
            required=field.required,
            visible_options=field.visible_options,
            final_answer=answer.value,
            source=answer.source,
            confidence=answer.confidence,
            reason_code=answer.reason_code,
            requires_review=answer.requires_review,
            validation_message=validation_message,
            provider_request_count=answer.provider_request_count,
        )
        try:
            self._review_queue.record(record)
        except Exception:
            # Recording is an adapter concern and cannot invalidate an answer.
            return

    def _cache_unresolved(self, cache_key: tuple, reason_code: str) -> RepairResult:
        result = RepairResult(
            status=RepairStatus.UNRESOLVED,
            answer_result=None,
            changed=False,
            reason_code=reason_code,
            requires_review=True,
        )
        self._repair_cache[cache_key] = result
        return result

    @staticmethod
    def _resolved(
        value: str | bool,
        source: AnswerSource,
        reason_code: str,
        *,
        requires_review: bool = False,
        provider_request_count: int = 0,
    ) -> AnswerResult:
        return AnswerResult(
            status=AnswerStatus.RESOLVED,
            value=value,
            source=source,
            confidence=Confidence.LOW if requires_review else Confidence.HIGH,
            reason_code=reason_code,
            requires_review=requires_review,
            provider_request_count=provider_request_count,
        )

    @staticmethod
    def _unresolved(field: FormField, reason_code: str) -> AnswerResult:
        return AnswerResult(
            status=AnswerStatus.UNRESOLVED,
            value=None,
            source=AnswerSource.NONE,
            confidence=Confidence.NONE,
            reason_code=reason_code,
            profile_key=field.profile_key,
            requires_review=True,
        )

    def _canonical_value(
        self, field: FormField, value: str | bool | None
    ) -> str | bool | None:
        if field.kind in {FieldKind.SELECT, FieldKind.RADIO}:
            if isinstance(value, bool):
                return (
                    self._positive_option(field.visible_options)
                    if value
                    else self._negative_option(field.visible_options)
                )
            return self._match_option(value, field.visible_options)
        if field.kind is FieldKind.CHECKBOX:
            return self._checkbox_value(value)
        if field.kind is FieldKind.NUMBER:
            number = self._decimal(value)
            if number is None:
                return None
            normalized = format(number, "f")
            return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized
        if value is None or isinstance(value, bool):
            return None
        return str(value).strip()

    def _value_valid(self, field: FormField, value: str | bool | None) -> bool:
        if value is None or (isinstance(value, str) and not value.strip()):
            return False
        if field.kind is FieldKind.NUMBER:
            number = self._decimal(value)
            if number is None:
                return False
            constraints = field.constraints
            if constraints.min_value is not None and number < constraints.min_value:
                return False
            if constraints.max_value is not None and number > constraints.max_value:
                return False
            if constraints.step is not None:
                base = constraints.min_value or Decimal("0")
                if (number - base) % constraints.step != 0:
                    return False
            return True
        if field.kind in {FieldKind.TEXT, FieldKind.TEXTAREA}:
            text = str(value)
            constraints = field.constraints
            if constraints.min_length is not None and len(text) < constraints.min_length:
                return False
            if constraints.max_length is not None and len(text) > constraints.max_length:
                return False
            if constraints.pattern is not None:
                try:
                    return re.fullmatch(constraints.pattern, text) is not None
                except re.error:
                    return False
            return True
        if field.kind in {FieldKind.SELECT, FieldKind.RADIO}:
            return self._match_option(value, field.visible_options) is not None
        if field.kind is FieldKind.CHECKBOX:
            return self._checkbox_value(value) is not None
        return False

    def _compatible_number(
        self,
        value: str | bool | None,
        constraints: FieldConstraints,
        grounded_default: str | None = None,
    ) -> str | None:
        number = self._decimal(value)
        if number is None:
            number = self._decimal(grounded_default)
        if number is None:
            number = constraints.min_value
        if number is None:
            return None
        lower, upper, step = constraints.min_value, constraints.max_value, constraints.step
        if lower is not None and number < lower:
            number = lower
        if upper is not None and number > upper:
            number = upper
        if step is not None:
            base = lower or Decimal("0")
            quotient = (number - base) / step
            number = base + quotient.to_integral_value(rounding=ROUND_HALF_UP) * step
            if lower is not None and number < lower:
                steps = ((lower - base) / step).to_integral_value(rounding=ROUND_CEILING)
                number = base + steps * step
            if upper is not None and number > upper:
                steps = ((upper - base) / step).to_integral_value(rounding=ROUND_FLOOR)
                number = base + steps * step
        if lower is not None and number < lower:
            return None
        if upper is not None and number > upper:
            return None
        if step is not None and (number - (lower or Decimal("0"))) % step != 0:
            return None
        normalized = format(number, "f")
        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")
        return normalized or "0"

    @staticmethod
    def _decimal(value: str | bool | None) -> Decimal | None:
        if value is None or isinstance(value, bool):
            return None
        token = str(value).strip()
        if not token:
            return None
        if "," in token and "." not in token:
            token = token.replace(",", ".")
        try:
            number = Decimal(token)
        except (InvalidOperation, ValueError):
            return None
        return number if number.is_finite() else None

    @staticmethod
    def _compatible_text(
        value: str | bool | None, constraints: FieldConstraints
    ) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        if constraints.max_length is not None:
            text = text[: constraints.max_length]
        if constraints.min_length is not None and len(text) < constraints.min_length:
            seed = text
            while len(text) < constraints.min_length:
                text += " " + seed
            text = text[: constraints.min_length]
        return text

    def _match_option(
        self, value: str | bool | None, options: tuple[str, ...]
    ) -> str | None:
        wanted = self._normalized(value)
        if not wanted:
            return None
        for option in self._available_options(options):
            if self._normalized(option) == wanted:
                return option
        positive, negative = {"yes", "si", "oui", "ja"}, {"no", "non", "nein"}
        aliases = positive if wanted in positive else negative if wanted in negative else set()
        for option in self._available_options(options):
            if self._normalized(option) in aliases:
                return option
        return None

    def _positive_option(self, options: tuple[str, ...]) -> str | None:
        return next(
            (item for item in self._available_options(options) if self._normalized(item) in {"yes", "si"}),
            None,
        )

    def _negative_option(self, options: tuple[str, ...]) -> str | None:
        return next(
            (item for item in self._available_options(options) if self._normalized(item) in {"no", "non", "nein"}),
            None,
        )

    def _available_options(self, options: tuple[str, ...]) -> tuple[str, ...]:
        placeholders = {
            "",
            "select an option",
            "choose an option",
            "selecciona una opcion",
            "selectionnez une option",
        }
        return tuple(item for item in options if self._normalized(item) not in placeholders)

    @staticmethod
    def _checkbox_value(value: str | bool | None) -> bool | None:
        if isinstance(value, bool):
            return value
        normalized = str(value or "").strip().casefold()
        if normalized in {"true", "checked", "yes", "si", "1"}:
            return True
        if normalized in {"false", "unchecked", "no", "0"}:
            return False
        return None

    @staticmethod
    def _normalized(value: str | bool | None) -> str:
        text = unicodedata.normalize("NFKD", str(value or "").casefold())
        text = "".join(char for char in text if not unicodedata.combining(char))
        return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())

    @staticmethod
    def _same_value(left: object, right: object) -> bool:
        return str(left if left is not None else "").strip().casefold() == str(
            right if right is not None else ""
        ).strip().casefold()

    @staticmethod
    def _stable_value(value: object) -> str:
        return str(value if value is not None else "")

    @staticmethod
    def _repair_cache_key(request: RepairRequest) -> tuple:
        issue = request.validation_issue
        return (
            request.field.field_key,
            issue.issue_kind,
            issue.message,
            str(issue.rejected_value if issue.rejected_value is not None else ""),
            issue.constraints,
            issue.visible_options,
            request.attempt_number,
        )
