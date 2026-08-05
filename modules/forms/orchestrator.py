"""Offline form orchestration across extraction, resolution, and writing."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable

from modules.forms.controls import FieldControl, FieldControlProvider
from modules.forms.extractor import FieldExtractor
from modules.forms.models import (
    AnswerResult,
    AnswerSource,
    AnswerStatus,
    ExtractedField,
    ExtractionContext,
    FieldProcessingResult,
    FieldProcessingStatus,
    FormPageResult,
    OrchestratorStatus,
    RepairRequest,
    RepairStatus,
    ReviewRecord,
    ValidationIssue,
    WriteRequest,
    WriteResult,
    WriteStatus,
)
from modules.forms.policies import SemanticPolicy, normalize_question
from modules.forms.profile import ProfileFactProvider
from modules.forms.provider import AnswerProvider
from modules.forms.resolver import AnswerResolver
from modules.forms.review import InMemoryReviewSink, ReviewSink
from modules.forms.writer import FieldWriter


@dataclass
class _FieldState:
    index: int
    field_key: str
    extracted: ExtractedField | None = None
    answer_result: AnswerResult | None = None
    write_result: WriteResult | None = None
    validation_issues: tuple[ValidationIssue, ...] = ()
    repair_attempts: int = 0
    review_recorded: bool = False
    status: FieldProcessingStatus = FieldProcessingStatus.FAILED
    reason_code: str = "field_not_processed"
    provider_request_count: int = 0
    valid: bool = False
    protected: bool = False
    type_impossible: bool = False
    retryable: bool = False
    failed: bool = False
    cache_reused: bool = False


class FormOrchestrator:
    """Process all supplied controls without owning page-level behavior."""

    def __init__(
        self,
        extractor: FieldExtractor,
        resolver: AnswerResolver,
        writer: FieldWriter,
        profile_provider: ProfileFactProvider,
        answer_provider: AnswerProvider | None,
        control_provider: FieldControlProvider,
        review_sink: ReviewSink | None = None,
        max_repair_rounds: int = 2,
    ) -> None:
        if max_repair_rounds < 0:
            raise ValueError("max_repair_rounds must not be negative")
        self._extractor = extractor
        self._resolver = resolver
        self._writer = writer
        self._profile_provider = profile_provider
        self._answer_provider = answer_provider
        self._control_provider = control_provider
        self._review_sink = (
            review_sink if review_sink is not None else InMemoryReviewSink()
        )
        self._max_repair_rounds = max_repair_rounds
        self._policy = SemanticPolicy()
        self._active_application_key: str | None = None
        self._completion_cache: dict[
            str, tuple[str, FieldProcessingResult]
        ] = {}

    def process_page(
        self,
        controls: Iterable[FieldControl],
        application_context: ExtractionContext | None = None,
    ) -> FormPageResult:
        context = application_context or ExtractionContext()
        application_key = self._application_key(context)
        if application_key != self._active_application_key:
            self._completion_cache.clear()
            self._active_application_key = application_key

        states: list[_FieldState] = []
        new_review_records: list[ReviewRecord] = []
        for index, control in enumerate(controls):
            states.append(self._initial_field_pass(index, control, context))

        repair_rounds = self._repair_invalid_fields(states, context)
        self._mark_exhausted_repairs(states)

        field_results: list[FieldProcessingResult] = []
        for state in states:
            if state.valid and not state.cache_reused:
                state.review_recorded = self._record_review(
                    state,
                    context,
                    new_review_records,
                )
            result = self._field_result(state)
            field_results.append(result)
            if state.valid and state.extracted is not None:
                signature = self._semantic_signature(state.extracted, context)
                self._completion_cache[state.field_key] = (signature, result)

        status, reason_code = self._page_status(states)
        validation_issues = tuple(
            issue for state in states for issue in state.validation_issues
        )
        unresolved_fields = tuple(
            state.field_key for state in states if not state.valid
        )
        return FormPageResult(
            status=status,
            field_results=tuple(field_results),
            unresolved_fields=unresolved_fields,
            validation_issues=validation_issues,
            review_records=tuple(new_review_records),
            provider_request_count=sum(
                state.provider_request_count for state in states
            ),
            repair_rounds=repair_rounds,
            reason_code=reason_code,
        )

    def _initial_field_pass(
        self,
        index: int,
        control: FieldControl,
        context: ExtractionContext,
    ) -> _FieldState:
        try:
            extracted = self._extractor.extract(control, context)
        except Exception:
            return _FieldState(
                index=index,
                field_key=self._failure_field_key(index, context),
                status=FieldProcessingStatus.FAILED,
                reason_code="field_extraction_failed",
                failed=True,
            )

        field = extracted.field
        signature = self._semantic_signature(extracted, context)
        cached = self._completion_cache.get(field.field_key)
        if cached is not None and cached[0] == signature:
            cached_result = cached[1]
            return _FieldState(
                index=index,
                field_key=field.field_key,
                extracted=extracted,
                answer_result=cached_result.answer_result,
                write_result=self._cache_write_result(cached_result),
                validation_issues=(),
                repair_attempts=0,
                review_recorded=False,
                status=FieldProcessingStatus.VALID,
                reason_code="completed_field_cache_reused",
                valid=True,
                protected=self._policy.classify(field).exact_only,
                cache_reused=True,
            )

        protected = self._policy.classify(field).exact_only
        try:
            answer = self._resolver.resolve(
                field,
                self._profile_provider,
                self._answer_provider,
            )
        except Exception:
            return _FieldState(
                index=index,
                field_key=field.field_key,
                extracted=extracted,
                validation_issues=self._safe_validation_issues(extracted),
                status=FieldProcessingStatus.FAILED,
                reason_code="field_resolution_failed",
                protected=protected,
                failed=True,
            )

        state = _FieldState(
            index=index,
            field_key=field.field_key,
            extracted=extracted,
            answer_result=answer,
            validation_issues=self._safe_validation_issues(extracted),
            status=FieldProcessingStatus.BLOCKED,
            reason_code=answer.reason_code,
            provider_request_count=answer.provider_request_count,
            protected=protected,
        )
        if not answer.accepted:
            if protected:
                state.reason_code = "protected_fact_unavailable"
            elif field.required:
                state.type_impossible = True
                state.reason_code = "required_answer_type_impossible"
            return state

        try:
            write_result = self._writer.write(
                WriteRequest(extracted, answer),
                self._control_provider,
            )
        except Exception:
            state.status = FieldProcessingStatus.FAILED
            state.reason_code = "field_write_failed"
            state.failed = True
            return state
        state.write_result = write_result
        return self._refresh_after_write(state, context, repaired=False)

    def _repair_invalid_fields(
        self,
        states: list[_FieldState],
        context: ExtractionContext,
    ) -> int:
        rounds_used = 0
        for round_number in range(1, self._max_repair_rounds + 1):
            candidates = [
                state
                for state in states
                if state.extracted is not None
                and state.validation_issues
                and not state.valid
                and not state.failed
                and not (
                    state.protected
                    and (
                        state.answer_result is None
                        or not state.answer_result.accepted
                    )
                )
            ]
            if not candidates:
                break
            rounds_used = round_number
            for state in candidates:
                self._repair_field(state, context, round_number)
        return rounds_used

    def _repair_field(
        self,
        state: _FieldState,
        context: ExtractionContext,
        round_number: int,
    ) -> None:
        extracted = state.extracted
        if extracted is None or not state.validation_issues:
            return
        request = RepairRequest(
            field=extracted.field,
            previous_answer=state.answer_result,
            validation_issue=state.validation_issues[0],
            attempt_number=round_number,
        )
        state.repair_attempts += 1
        try:
            repair = self._resolver.repair(
                request,
                self._profile_provider,
                self._answer_provider,
            )
        except Exception:
            state.status = FieldProcessingStatus.FAILED
            state.reason_code = "field_repair_failed"
            state.failed = True
            return

        if repair.answer_result is not None:
            state.provider_request_count += (
                repair.answer_result.provider_request_count
            )
        if repair.status is RepairStatus.RETRY_REQUIRED:
            state.retryable = True
            state.reason_code = repair.reason_code
            self._refresh_extracted_state(state, context)
            return
        if repair.status is RepairStatus.UNRESOLVED or repair.answer_result is None:
            state.status = FieldProcessingStatus.BLOCKED
            state.reason_code = repair.reason_code
            if state.protected:
                state.type_impossible = False
            elif extracted.field.required:
                state.type_impossible = True
            return

        state.answer_result = repair.answer_result
        try:
            state.write_result = self._writer.write(
                WriteRequest(extracted, repair.answer_result),
                self._control_provider,
            )
        except Exception:
            state.status = FieldProcessingStatus.FAILED
            state.reason_code = "field_repair_write_failed"
            state.failed = True
            return
        self._refresh_after_write(state, context, repaired=True)

    def _refresh_after_write(
        self,
        state: _FieldState,
        context: ExtractionContext,
        *,
        repaired: bool,
    ) -> _FieldState:
        if not self._refresh_extracted_state(state, context):
            return state
        write_result = state.write_result
        write_verified = (
            write_result is not None
            and write_result.status
            in {
                WriteStatus.SKIPPED_PRESERVED,
                WriteStatus.WRITTEN,
                WriteStatus.VERIFIED,
            }
        )
        if write_verified and not state.validation_issues:
            state.valid = True
            state.retryable = False
            state.type_impossible = False
            if repaired:
                state.status = FieldProcessingStatus.REPAIRED
                state.reason_code = "field_repaired_and_verified"
            elif (
                state.answer_result is not None
                and state.answer_result.status is AnswerStatus.PRESERVED
            ):
                state.status = FieldProcessingStatus.PRESERVED
                state.reason_code = "field_preserved_and_verified"
            else:
                state.status = FieldProcessingStatus.WRITTEN
                state.reason_code = "field_written_and_verified"
            return state

        state.valid = False
        state.status = FieldProcessingStatus.BLOCKED
        if write_result is not None and write_result.status is WriteStatus.RETRY_REQUIRED:
            state.retryable = True
            state.reason_code = write_result.reason_code
        elif write_result is not None and write_result.status is WriteStatus.FAILED:
            state.reason_code = write_result.reason_code
            state.type_impossible = self._write_type_impossible(write_result)
            state.retryable = (
                bool(state.validation_issues)
                and not state.protected
                and not state.type_impossible
            )
        elif state.validation_issues:
            state.retryable = not state.protected
            state.reason_code = "field_validation_failed"
        return state

    def _mark_exhausted_repairs(self, states: list[_FieldState]) -> None:
        if self._max_repair_rounds == 0:
            return
        for state in states:
            if (
                not state.valid
                and state.retryable
                and state.validation_issues
                and state.repair_attempts >= self._max_repair_rounds
            ):
                state.retryable = False
                state.failed = True
                state.status = FieldProcessingStatus.FAILED
                state.reason_code = "ordinary_repair_budget_exhausted"

    def _refresh_extracted_state(
        self,
        state: _FieldState,
        context: ExtractionContext,
    ) -> bool:
        if state.extracted is None:
            return False
        try:
            control = self._control_provider.requery(state.extracted.locator)
            if control is None:
                state.retryable = True
                state.reason_code = "field_requery_required"
                return False
            refreshed = self._extractor.extract(control, context)
            state.extracted = refreshed
            state.field_key = refreshed.field.field_key
            state.validation_issues = self._safe_validation_issues(refreshed)
            return True
        except Exception:
            state.status = FieldProcessingStatus.FAILED
            state.reason_code = "field_reextraction_failed"
            state.failed = True
            return False

    def _record_review(
        self,
        state: _FieldState,
        context: ExtractionContext,
        new_records: list[ReviewRecord],
    ) -> bool:
        answer = state.answer_result
        extracted = state.extracted
        if answer is None or extracted is None or not answer.accepted:
            return False
        if (
            answer.source not in {AnswerSource.PROVIDER, AnswerSource.DEFAULT}
            and not answer.requires_review
        ):
            return False
        field = extracted.field
        record = ReviewRecord(
            application_id=context.application_id,
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
            validation_message=extracted.validation_state.validation_message,
            provider_request_count=answer.provider_request_count,
        )
        try:
            created = self._review_sink.record(record)
        except Exception:
            return False
        if created:
            new_records.append(record)
        return created

    def _page_status(
        self,
        states: list[_FieldState],
    ) -> tuple[OrchestratorStatus, str]:
        required_states = [
            state
            for state in states
            if state.extracted is None or state.extracted.field.required
        ]
        if any(
            state.protected and not state.valid for state in required_states
        ):
            return (
                OrchestratorStatus.BLOCKED_PROTECTED_FACT,
                "required_protected_fact_blocked",
            )
        if any(
            state.type_impossible and not state.valid
            for state in required_states
        ):
            return (
                OrchestratorStatus.BLOCKED_TYPE_IMPOSSIBLE,
                "required_field_type_impossible",
            )
        if any(
            state.retryable and not state.valid for state in required_states
        ):
            return (
                OrchestratorStatus.RETRY_REQUIRED,
                "required_field_retryable",
            )
        if any(state.failed and not state.valid for state in required_states):
            return OrchestratorStatus.FAILED, "required_field_failed"
        return (
            OrchestratorStatus.READY_FOR_NAVIGATION,
            "all_required_fields_verified",
        )

    @staticmethod
    def _field_result(state: _FieldState) -> FieldProcessingResult:
        return FieldProcessingResult(
            field_key=state.field_key,
            status=state.status,
            answer_result=state.answer_result,
            write_result=state.write_result,
            validation_issues=state.validation_issues,
            repair_attempts=state.repair_attempts,
            review_recorded=state.review_recorded,
            reason_code=state.reason_code,
        )

    def _safe_validation_issues(
        self,
        extracted: ExtractedField,
    ) -> tuple[ValidationIssue, ...]:
        try:
            return self._extractor.validation_issues(extracted)
        except Exception:
            return ()

    @staticmethod
    def _cache_write_result(
        cached: FieldProcessingResult,
    ) -> WriteResult | None:
        answer = cached.answer_result
        if answer is None:
            return None
        return WriteResult(
            status=WriteStatus.VERIFIED,
            attempted_value=answer.value,
            verified_value=answer.value,
            changed=False,
            retry_count=0,
            reason_code="completed_field_cache_reused",
        )

    @staticmethod
    def _write_type_impossible(result: WriteResult) -> bool:
        return result.reason_code in {
            "answer_not_accepted",
            "number_answer_not_numeric",
            "number_answer_violates_constraints",
            "text_answer_wrong_type",
            "required_text_answer_missing",
            "text_answer_violates_constraints",
            "visible_enabled_option_not_found",
            "checkbox_answer_not_boolean",
            "required_checkbox_cannot_be_false",
            "unsupported_field_kind",
        }

    @staticmethod
    def _semantic_signature(
        extracted: ExtractedField,
        context: ExtractionContext,
    ) -> str:
        field = extracted.field
        constraints = field.constraints
        payload = {
            "application_id": context.application_id,
            "constraints": {
                "max_length": constraints.max_length,
                "max_value": str(constraints.max_value),
                "min_length": constraints.min_length,
                "min_value": str(constraints.min_value),
                "pattern": constraints.pattern,
                "step": str(constraints.step),
            },
            "current_value": field.existing_value,
            "field_key": field.field_key,
            "job_id": context.job_id,
            "kind": field.kind.value,
            "question": normalize_question(field.question),
            "validation_message": extracted.validation_state.validation_message,
            "visible_options": tuple(
                normalize_question(option) for option in field.visible_options
            ),
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _application_key(context: ExtractionContext) -> str:
        payload = {
            "application_id": context.application_id,
            "job_id": context.job_id,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _failure_field_key(
        index: int,
        context: ExtractionContext,
    ) -> str:
        payload = f"{context.application_id}|{context.job_id}|{index}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"extraction_failure:{digest[:24]}"
