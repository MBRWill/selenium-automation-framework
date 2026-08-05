from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, InvalidOperation
import inspect
import unittest

from modules.forms import (
    AnswerResolver,
    AnswerSource,
    Confidence,
    ControlValidity,
    ExtractionContext,
    FieldConstraints,
    FieldExtractor,
    FieldProcessingStatus,
    FieldWriter,
    FormOrchestrator,
    InMemoryReviewSink,
    OrchestratorStatus,
    ProfileFactResult,
    ProviderResult,
    WriteResult,
    WriteStatus,
)
from modules.forms import orchestrator as orchestrator_module
from test_form_field_io import FakeControl, option


class AutoValidatingControl(FakeControl):
    def snapshot(self):
        self.validity = self._current_validity()
        return super().snapshot()

    def _current_validity(self):
        value_missing = False
        type_mismatch = False
        range_underflow = False
        range_overflow = False
        step_mismatch = False
        too_short = False
        too_long = False
        if self.input_type == "checkbox":
            value_missing = self.required and not bool(self.checked)
        elif self.input_type == "radio" or self.tag_name == "select":
            value_missing = self.required and not any(
                item.selected and item.visible and item.enabled
                for item in self.options
            )
        elif self.input_type == "number":
            token = str(self.current_value or "").strip()
            value_missing = self.required and not token
            try:
                number = Decimal(token) if token else None
            except (InvalidOperation, ValueError):
                number = None
                type_mismatch = bool(token)
            if number is not None:
                constraints = self.constraints
                range_underflow = (
                    constraints.min_value is not None
                    and number < constraints.min_value
                )
                range_overflow = (
                    constraints.max_value is not None
                    and number > constraints.max_value
                )
                if constraints.step is not None:
                    base = constraints.min_value or Decimal("0")
                    step_mismatch = (
                        number - base
                    ) % constraints.step != 0
        else:
            text = str(self.current_value or "")
            value_missing = self.required and not text.strip()
            too_short = (
                self.constraints.min_length is not None
                and len(text) < self.constraints.min_length
            )
            too_long = (
                self.constraints.max_length is not None
                and len(text) > self.constraints.max_length
            )
        invalid = any((
            value_missing,
            type_mismatch,
            range_underflow,
            range_overflow,
            step_mismatch,
            too_short,
            too_long,
        ))
        return ControlValidity(
            browser_valid=not invalid,
            validation_message="Synthetic browser validation" if invalid else "",
            aria_invalid=invalid,
            value_missing=value_missing,
            type_mismatch=type_mismatch,
            range_underflow=range_underflow,
            range_overflow=range_overflow,
            step_mismatch=step_mismatch,
            too_short=too_short,
            too_long=too_long,
        )


class MappingControlProvider:
    def __init__(self, controls=()):
        self.controls = {control.selector: control for control in controls}
        self.requery_calls = 0

    def requery(self, locator):
        self.requery_calls += 1
        return self.controls.get(locator.control_selector)


class FakeProfile:
    def __init__(self, facts=None):
        self.facts = facts or {}
        self.calls = []

    def get_fact(self, profile_key, field):
        self.calls.append((profile_key, field.field_key))
        return self.facts.get(
            profile_key,
            ProfileFactResult(
                found=False,
                verified=False,
                value=None,
                profile_key=profile_key,
                reason_code="profile_fact_missing",
            ),
        )


class FakeAnswerProvider:
    def __init__(self, answers=None, default="Provider answer"):
        self.answers = answers or {}
        self.default = default
        self.requests = []

    def answer(self, request):
        self.requests.append(request)
        response = self.answers.get(request.question, self.default)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, ProviderResult):
            return response
        return ProviderResult(
            answered=response is not None,
            value=response,
            confidence=Confidence.HIGH,
            reason_code="fake_provider_answer",
            request_count=1,
        )


class FalsyReviewSink(InMemoryReviewSink):
    def __bool__(self):
        return False


class RecordingResolver:
    def __init__(self, delegate=None, fail_question=None):
        self.delegate = delegate or AnswerResolver()
        self.fail_question = fail_question
        self.resolve_calls = []
        self.repair_calls = []

    def resolve(self, field, profile, provider):
        self.resolve_calls.append(field.field_key)
        if field.question == self.fail_question:
            raise RuntimeError("synthetic resolver failure")
        return self.delegate.resolve(field, profile, provider)

    def repair(self, request, profile, provider):
        self.repair_calls.append(request)
        return self.delegate.repair(request, profile, provider)


class RecordingExtractor:
    def __init__(self, delegate=None):
        self.delegate = delegate or FieldExtractor()
        self.calls = 0

    def extract(self, control, context=None):
        self.calls += 1
        return self.delegate.extract(control, context)

    def validation_issues(self, extracted):
        return self.delegate.validation_issues(extracted)


class RecordingWriter:
    def __init__(self, delegate=None, fail_question=None):
        self.delegate = delegate or FieldWriter()
        self.fail_question = fail_question
        self.requests = []

    def write(self, request, controls):
        self.requests.append(request)
        if request.extracted_field.field.question == self.fail_question:
            raise RuntimeError("synthetic writer failure")
        return self.delegate.write(request, controls)


class FailInitialWriter(RecordingWriter):
    def __init__(self, fail_question=None):
        super().__init__()
        self.fail_initial_question = fail_question
        self.failed_keys = set()

    def write(self, request, controls):
        self.requests.append(request)
        field = request.extracted_field.field
        should_fail = (
            field.field_key not in self.failed_keys
            and (
                self.fail_initial_question is None
                or field.question == self.fail_initial_question
            )
        )
        if should_fail:
            self.failed_keys.add(field.field_key)
            return WriteResult(
                status=WriteStatus.FAILED,
                attempted_value=request.answer_result.value,
                verified_value=field.existing_value,
                changed=False,
                retry_count=1,
                reason_code="synthetic_initial_verification_failed",
            )
        return self.delegate.write(request, controls)


class RaisingControl:
    selector = "#raising"

    def snapshot(self):
        raise RuntimeError("synthetic extraction failure")


def profile_fact(value, key):
    return ProfileFactResult(
        found=True,
        verified=True,
        value=value,
        profile_key=key,
        reason_code="verified_profile_fact",
    )


def make_control(
    question,
    *,
    selector,
    current=None,
    required=True,
    kind="text",
    options=(),
    constraints=FieldConstraints(),
    auto=False,
    validity=ControlValidity(),
):
    control_type = AutoValidatingControl if auto else FakeControl
    tag_name = "select" if kind == "select" else "textarea" if kind == "textarea" else "input"
    input_type = kind if kind in {"number", "radio", "checkbox"} else "text"
    checked = bool(current) if kind == "checkbox" else None
    return control_type(
        tag_name=tag_name,
        input_type=input_type,
        question=question,
        current_value=current,
        required=required,
        checked=checked,
        options=options,
        constraints=constraints,
        validity=validity,
        selector=selector,
    )


def make_orchestrator(
    controls,
    *,
    provider=None,
    profile=None,
    resolver=None,
    extractor=None,
    writer=None,
    control_provider=None,
    review_sink=None,
    max_rounds=2,
):
    control_provider = control_provider or MappingControlProvider(controls)
    return FormOrchestrator(
        extractor=extractor or FieldExtractor(),
        resolver=resolver or AnswerResolver(),
        writer=writer or FieldWriter(),
        profile_provider=profile or FakeProfile(),
        answer_provider=provider,
        control_provider=control_provider,
        review_sink=review_sink,
        max_repair_rounds=max_rounds,
    )


def context(application="application-1"):
    return ExtractionContext(
        application_id=application,
        job_id="job-1",
        company="Example Company",
        job_title="Example Role",
    )


class BasicPipelineTests(unittest.TestCase):
    def test_extract_resolve_write_validate_succeeds(self):
        control = make_control("Why this role?", selector="#pipeline", current="", auto=True)
        provider = FakeAnswerProvider({"Why this role?": "Strong fit"})
        result = make_orchestrator([control], provider=provider).process_page([control], context())
        self.assertEqual(result.status, OrchestratorStatus.READY_FOR_NAVIGATION)
        self.assertEqual(control.current_value, "Strong fit")
        self.assertEqual(result.field_results[0].status, FieldProcessingStatus.WRITTEN)

    def test_multiple_valid_fields_are_ready(self):
        controls = [
            make_control("First", selector="#first", current="One"),
            make_control("Second", selector="#second", current="Two"),
        ]
        result = make_orchestrator(controls).process_page(controls, context())
        self.assertEqual(result.status, OrchestratorStatus.READY_FOR_NAVIGATION)
        self.assertTrue(all(item.status is FieldProcessingStatus.PRESERVED for item in result.field_results))

    def test_field_order_does_not_change_stable_outcomes(self):
        first = make_control("First", selector="#order-first", current="One")
        second = make_control("Second", selector="#order-second", current="Two")
        normal = make_orchestrator([first, second]).process_page([first, second], context())
        reversed_result = make_orchestrator([first, second]).process_page([second, first], context())
        normal_map = {item.field_key: item.status for item in normal.field_results}
        reversed_map = {item.field_key: item.status for item in reversed_result.field_results}
        self.assertEqual(normal_map, reversed_map)

    def test_existing_valid_answer_is_preserved(self):
        control = make_control("Existing", selector="#existing", current="Keep")
        result = make_orchestrator([control]).process_page([control], context())
        self.assertEqual(result.field_results[0].answer_result.source, AnswerSource.LINKEDIN)

    def test_preserved_field_does_not_call_provider_or_mutate(self):
        control = make_control("Existing", selector="#preserved", current="Keep")
        provider = FakeAnswerProvider()
        result = make_orchestrator([control], provider=provider).process_page([control], context())
        self.assertEqual(provider.requests, [])
        self.assertEqual((control.clear_calls, control.enter_calls), (0, 0))
        self.assertEqual(result.status, OrchestratorStatus.READY_FOR_NAVIGATION)


class ContinuityTests(unittest.TestCase):
    def test_ordinary_unknown_text_calls_provider_and_continues(self):
        control = make_control("Unknown ordinary question", selector="#unknown", current="", auto=True)
        provider = FakeAnswerProvider(default="Answered")
        result = make_orchestrator([control], provider=provider).process_page([control], context())
        self.assertEqual(len(provider.requests), 1)
        self.assertEqual(result.status, OrchestratorStatus.READY_FOR_NAVIGATION)

    def test_low_confidence_answer_is_accepted_and_reviewed(self):
        control = make_control("Low confidence", selector="#low", current="", auto=True)
        provider = FakeAnswerProvider({
            "Low confidence": ProviderResult(True, "Usable", Confidence.LOW, "provider_uncertain", 1)
        })
        sink = InMemoryReviewSink()
        result = make_orchestrator([control], provider=provider, review_sink=sink).process_page([control], context())
        self.assertEqual(result.status, OrchestratorStatus.READY_FOR_NAVIGATION)
        self.assertEqual(result.field_results[0].answer_result.confidence, Confidence.LOW)
        self.assertEqual(len(result.review_records), 1)

    def test_experience_yes_no_falls_back_after_provider_failure(self):
        control = make_control(
            "Are you comfortable with Python experience?",
            selector="#experience",
            kind="radio",
            options=(option("Yes"), option("No")),
            auto=True,
        )
        provider = FakeAnswerProvider({control.question: RuntimeError("offline")})
        result = make_orchestrator([control], provider=provider).process_page([control], context())
        self.assertEqual(result.field_results[0].answer_result.source, AnswerSource.DEFAULT)
        self.assertEqual(result.field_results[0].answer_result.value, "Yes")
        self.assertEqual(len(result.review_records), 1)

    def test_spanish_preference_falls_back_to_si(self):
        control = make_control(
            "¿Prefieres trabajo remoto?",
            selector="#spanish-preference",
            kind="radio",
            options=(option("Sí"), option("No")),
            auto=True,
        )
        provider = FakeAnswerProvider({control.question: RuntimeError("offline")})
        result = make_orchestrator([control], provider=provider).process_page([control], context())
        self.assertEqual(result.field_results[0].answer_result.value, "Sí")

    def test_initial_failure_does_not_stop_other_field(self):
        invalid = make_control(
            "Invalid ordinary",
            selector="#continuity-invalid",
            current="x",
            constraints=FieldConstraints(min_length=4),
            auto=True,
        )
        valid = make_control("Independent", selector="#continuity-valid", current="Done")
        writer = FailInitialWriter(fail_question="Invalid ordinary")
        provider = FakeAnswerProvider({"Invalid ordinary": "Valid"})
        result = make_orchestrator([invalid, valid], writer=writer, provider=provider).process_page([invalid, valid], context())
        self.assertEqual(result.field_results[1].status, FieldProcessingStatus.PRESERVED)
        self.assertTrue(result.field_results[0].status in {FieldProcessingStatus.REPAIRED, FieldProcessingStatus.WRITTEN})

    def test_initial_validation_error_is_repaired_not_terminal(self):
        control = make_control(
            "Repair short text",
            selector="#repair-continuity",
            current="x",
            constraints=FieldConstraints(min_length=5),
            auto=True,
        )
        writer = FailInitialWriter()
        provider = FakeAnswerProvider({control.question: "Valid"})
        result = make_orchestrator([control], writer=writer, provider=provider).process_page([control], context())
        self.assertEqual(result.status, OrchestratorStatus.READY_FOR_NAVIGATION)
        self.assertEqual(result.field_results[0].status, FieldProcessingStatus.REPAIRED)

    def test_low_confidence_does_not_block_application(self):
        control = make_control("Uncertain", selector="#uncertain", current="", auto=True)
        provider = FakeAnswerProvider({
            "Uncertain": ProviderResult(True, "Answer", Confidence.LOW, "low_confidence", 1)
        })
        result = make_orchestrator([control], provider=provider).process_page([control], context())
        self.assertEqual(result.status, OrchestratorStatus.READY_FOR_NAVIGATION)


class ValidationRepairTests(unittest.TestCase):
    def _repair(self, control, provider_answer):
        writer = FailInitialWriter()
        provider = FakeAnswerProvider({control.question: provider_answer})
        return make_orchestrator([control], writer=writer, provider=provider).process_page([control], context())

    def test_text_too_short_is_repaired(self):
        control = make_control("Short", selector="#short", current="x", constraints=FieldConstraints(min_length=5), auto=True)
        result = self._repair(control, "Valid")
        self.assertEqual(result.field_results[0].status, FieldProcessingStatus.REPAIRED)
        self.assertGreaterEqual(len(control.current_value), 5)

    def test_text_too_long_is_repaired(self):
        control = make_control("Long", selector="#long", current="abcdefgh", constraints=FieldConstraints(max_length=5), auto=True)
        result = self._repair(control, "Valid")
        self.assertEqual(result.status, OrchestratorStatus.READY_FOR_NAVIGATION)
        self.assertLessEqual(len(control.current_value), 5)

    def test_invalid_numeric_type_is_repaired(self):
        control = make_control("Number", selector="#number-type", current="many", kind="number", constraints=FieldConstraints(min_value=Decimal("2")), auto=True)
        result = self._repair(control, "4")
        self.assertEqual(result.field_results[0].status, FieldProcessingStatus.REPAIRED)
        self.assertEqual(control.current_value, "2")

    def test_numeric_min_max_step_issue_is_repaired(self):
        control = make_control(
            "Constrained number",
            selector="#number-constraints",
            current="12",
            kind="number",
            constraints=FieldConstraints(min_value=Decimal("1"), max_value=Decimal("10"), step=Decimal("2")),
            auto=True,
        )
        result = self._repair(control, "9")
        self.assertEqual(result.status, OrchestratorStatus.READY_FOR_NAVIGATION)
        self.assertEqual((Decimal(control.current_value) - Decimal("1")) % Decimal("2"), Decimal("0"))

    def test_missing_select_is_repaired_against_current_options(self):
        control = make_control("Select", selector="#select-repair", kind="select", options=(option("Remote"),), auto=True)
        result = self._repair(control, "Remote")
        self.assertEqual(result.field_results[0].status, FieldProcessingStatus.REPAIRED)
        self.assertTrue(control.options[0].selected)

    def test_radio_not_selected_is_repaired(self):
        control = make_control("Radio preference", selector="#radio-repair", kind="radio", options=(option("Yes"), option("No")), auto=True)
        result = self._repair(control, "Yes")
        self.assertEqual(result.status, OrchestratorStatus.READY_FOR_NAVIGATION)
        self.assertTrue(next(item for item in control.options if item.text == "Yes").selected)

    def test_only_invalid_field_is_repaired(self):
        invalid = make_control("Invalid", selector="#only-invalid", current="x", constraints=FieldConstraints(min_length=4), auto=True)
        valid = make_control("Valid", selector="#already-valid", current="Done")
        resolver = RecordingResolver()
        writer = FailInitialWriter(fail_question="Invalid")
        provider = FakeAnswerProvider({"Invalid": "Good"})
        make_orchestrator([invalid, valid], resolver=resolver, writer=writer, provider=provider).process_page([invalid, valid], context())
        self.assertTrue(resolver.repair_calls)
        self.assertTrue(all(request.field.question == "Invalid" for request in resolver.repair_calls))

    def test_valid_field_is_not_rewritten_during_repair(self):
        invalid = make_control("Invalid", selector="#no-rewrite-invalid", current="x", constraints=FieldConstraints(min_length=4), auto=True)
        valid = make_control("Valid", selector="#no-rewrite-valid", current="Done")
        writer = FailInitialWriter(fail_question="Invalid")
        provider = FakeAnswerProvider({"Invalid": "Good"})
        make_orchestrator([invalid, valid], writer=writer, provider=provider).process_page([invalid, valid], context())
        self.assertEqual((valid.clear_calls, valid.enter_calls), (0, 0))

    def test_repaired_field_is_reextracted_and_revalidated(self):
        control = make_control("Reextract", selector="#reextract", current="x", constraints=FieldConstraints(min_length=4), auto=True)
        extractor = RecordingExtractor()
        result = make_orchestrator([control], extractor=extractor, writer=FailInitialWriter(), provider=FakeAnswerProvider({"Reextract": "Good"})).process_page([control], context())
        self.assertGreaterEqual(extractor.calls, 3)
        self.assertEqual(result.field_results[0].validation_issues, ())

    def test_repair_rounds_are_bounded(self):
        control = make_control(
            "Sticky invalid",
            selector="#sticky",
            current="bad",
            validity=ControlValidity(browser_valid=False, validation_message="Still invalid", aria_invalid=True),
        )
        control.ignore_all_mutations = True
        result = make_orchestrator([control], provider=FakeAnswerProvider(default="Answer"), max_rounds=2).process_page([control], context())
        self.assertLessEqual(result.repair_rounds, 2)
        self.assertLessEqual(result.field_results[0].repair_attempts, 2)

    def test_exhausted_repair_is_structured(self):
        control = make_control(
            "Sticky invalid",
            selector="#exhausted",
            current="bad",
            validity=ControlValidity(browser_valid=False, validation_message="Still invalid", aria_invalid=True),
        )
        control.ignore_all_mutations = True
        result = make_orchestrator([control], provider=FakeAnswerProvider(default="Answer"), max_rounds=2).process_page([control], context())
        self.assertIn(result.status, {OrchestratorStatus.FAILED, OrchestratorStatus.BLOCKED_TYPE_IMPOSSIBLE})
        self.assertEqual(result.field_results[0].reason_code, "ordinary_repair_budget_exhausted")


class CacheAndReviewTests(unittest.TestCase):
    def test_completed_unchanged_field_is_reused(self):
        control = make_control("Cache", selector="#cache", current="", auto=True)
        writer = RecordingWriter()
        provider = FakeAnswerProvider(default="Cached answer")
        orchestrator = make_orchestrator([control], writer=writer, provider=provider)
        orchestrator.process_page([control], context())
        call_count = len(writer.requests)
        second = orchestrator.process_page([control], context())
        self.assertEqual(len(writer.requests), call_count)
        self.assertEqual(second.field_results[0].status, FieldProcessingStatus.VALID)

    def test_provider_not_called_twice_for_unchanged_input(self):
        control = make_control("Provider cache", selector="#provider-cache", current="", auto=True)
        provider = FakeAnswerProvider(default="Answer")
        orchestrator = make_orchestrator([control], provider=provider)
        orchestrator.process_page([control], context())
        orchestrator.process_page([control], context())
        self.assertEqual(len(provider.requests), 1)

    def test_changed_visible_options_invalidate_cache(self):
        control = make_control("Options", selector="#options-cache", kind="select", options=(option("Remote"),), auto=True)
        writer = RecordingWriter()
        provider = FakeAnswerProvider({"Options": "Remote"})
        orchestrator = make_orchestrator([control], writer=writer, provider=provider)
        orchestrator.process_page([control], context())
        first_writes = len(writer.requests)
        control.options.append(option("Hybrid"))
        second = orchestrator.process_page([control], context())
        self.assertGreater(len(writer.requests), first_writes)
        self.assertNotEqual(second.field_results[0].reason_code, "completed_field_cache_reused")

    def test_changed_validation_message_allows_repair_request(self):
        control = make_control("Validation cache", selector="#validation-cache", current="Done")
        resolver = RecordingResolver()
        orchestrator = make_orchestrator([control], resolver=resolver, provider=FakeAnswerProvider(default="Answer"))
        orchestrator.process_page([control], context())
        control.validity = ControlValidity(browser_valid=False, validation_message="New validation", aria_invalid=True)
        orchestrator.process_page([control], context())
        self.assertTrue(resolver.repair_calls)
        self.assertEqual(resolver.repair_calls[-1].validation_issue.message, "New validation")

    def test_review_record_is_created_once(self):
        control = make_control("Review once", selector="#review-once", current="", auto=True)
        sink = InMemoryReviewSink()
        result = make_orchestrator([control], provider=FakeAnswerProvider(default="Answer"), review_sink=sink).process_page([control], context())
        self.assertEqual(len(result.review_records), 1)
        self.assertEqual(len(sink.records), 1)

    def test_falsy_custom_review_sink_is_respected(self):
        control = make_control("Falsy sink", selector="#falsy-sink", current="", auto=True)
        sink = FalsyReviewSink()
        make_orchestrator([control], provider=FakeAnswerProvider(default="Answer"), review_sink=sink).process_page([control], context())
        self.assertEqual(len(sink.records), 1)

    def test_profile_linkedin_and_policy_answers_are_not_reviewed(self):
        preserved = make_control("Preserved", selector="#review-preserved", current="Keep")
        protected = make_control(
            "Are you authorized to work?",
            selector="#review-profile",
            kind="radio",
            options=(option("Yes"), option("No")),
            auto=True,
        )
        policy = make_control(
            "Receive promotional marketing updates",
            selector="#review-policy",
            kind="radio",
            required=False,
            options=(option("Yes"), option("No")),
            auto=True,
        )
        profile = FakeProfile({
            "legal.work_authorization": profile_fact("Yes", "legal.work_authorization")
        })
        sink = InMemoryReviewSink()
        make_orchestrator(
            [preserved, protected, policy],
            profile=profile,
            review_sink=sink,
        ).process_page([preserved, protected, policy], context())
        self.assertEqual(sink.records, ())

    def test_provider_request_count_includes_failed_request_before_default(self):
        control = make_control(
            "Do you prefer remote work?",
            selector="#request-count",
            kind="radio",
            options=(option("Yes"), option("No")),
            auto=True,
        )
        provider = FakeAnswerProvider({control.question: RuntimeError("offline")})
        result = make_orchestrator([control], provider=provider).process_page([control], context())
        self.assertEqual(result.provider_request_count, 1)
        self.assertEqual(result.field_results[0].answer_result.source, AnswerSource.DEFAULT)

    def test_repeated_processing_does_not_duplicate_review(self):
        control = make_control("Review repeat", selector="#review-repeat", current="", auto=True)
        sink = InMemoryReviewSink()
        orchestrator = make_orchestrator([control], provider=FakeAnswerProvider(default="Answer"), review_sink=sink)
        orchestrator.process_page([control], context())
        second = orchestrator.process_page([control], context())
        self.assertEqual(len(sink.records), 1)
        self.assertEqual(second.review_records, ())

    def test_cache_resets_for_new_application(self):
        control = make_control("New application", selector="#new-app", current="", auto=True)
        provider = FakeAnswerProvider(default="Answer")
        orchestrator = make_orchestrator([control], provider=provider)
        orchestrator.process_page([control], context("application-1"))
        control.current_value = ""
        orchestrator.process_page([control], context("application-2"))
        self.assertEqual(len(provider.requests), 2)


class ProtectedFactTests(unittest.TestCase):
    def _protected_control(self, question, selector, selected=None):
        return make_control(
            question,
            selector=selector,
            kind="radio",
            options=(option("Yes", selected=selected == "Yes"), option("No", selected=selected == "No")),
            auto=True,
        )

    def test_work_authorization_uses_exact_profile(self):
        control = self._protected_control("Are you authorized to work?", "#auth")
        profile = FakeProfile({"legal.work_authorization": profile_fact("Yes", "legal.work_authorization")})
        result = make_orchestrator([control], profile=profile).process_page([control], context())
        self.assertEqual(result.field_results[0].answer_result.source, AnswerSource.PROFILE)

    def test_sponsorship_uses_exact_profile(self):
        control = self._protected_control("Do you require sponsorship?", "#sponsor")
        profile = FakeProfile({"legal.requires_sponsorship": profile_fact("No", "legal.requires_sponsorship")})
        result = make_orchestrator([control], profile=profile).process_page([control], context())
        self.assertEqual(result.field_results[0].answer_result.value, "No")

    def test_conflicting_protected_value_is_corrected(self):
        control = self._protected_control("Are you authorized to work?", "#conflict", selected="Yes")
        profile = FakeProfile({"legal.work_authorization": profile_fact("No", "legal.work_authorization")})
        result = make_orchestrator([control], profile=profile).process_page([control], context())
        self.assertEqual(result.field_results[0].answer_result.value, "No")
        self.assertTrue(next(item for item in control.options if item.text == "No").selected)

    def test_protected_fact_never_calls_provider(self):
        control = self._protected_control("Are you a citizen?", "#citizen")
        provider = FakeAnswerProvider(default="Yes")
        make_orchestrator([control], provider=provider).process_page([control], context())
        self.assertEqual(provider.requests, [])

    def test_missing_required_protected_fact_blocks(self):
        control = self._protected_control("Are you a citizen?", "#missing-citizen")
        result = make_orchestrator([control], provider=FakeAnswerProvider(default="Yes")).process_page([control], context())
        self.assertEqual(result.status, OrchestratorStatus.BLOCKED_PROTECTED_FACT)

    def test_missing_protected_fact_does_not_stop_unrelated_field(self):
        protected = self._protected_control("Are you a citizen?", "#blocked-protected")
        ordinary = make_control("Ordinary", selector="#protected-independent", current="", auto=True)
        provider = FakeAnswerProvider({"Ordinary": "Completed"})
        result = make_orchestrator([protected, ordinary], provider=provider).process_page([protected, ordinary], context())
        self.assertEqual(ordinary.current_value, "Completed")
        self.assertEqual(result.field_results[1].status, FieldProcessingStatus.WRITTEN)

    def test_protected_answer_never_uses_yes_fallback(self):
        control = self._protected_control("Are you a citizen?", "#no-fallback")
        result = make_orchestrator([control]).process_page([control], context())
        self.assertIsNone(result.field_results[0].answer_result.value)
        self.assertNotEqual(result.field_results[0].answer_result.source, AnswerSource.DEFAULT)

    def test_exact_identity_fact_never_calls_provider(self):
        control = make_control(
            "What is your legal name?",
            selector="#legal-name",
            current="",
            auto=True,
        )
        provider = FakeAnswerProvider(default="Invented Name")
        result = make_orchestrator([control], provider=provider).process_page([control], context())
        self.assertEqual(result.status, OrchestratorStatus.BLOCKED_PROTECTED_FACT)
        self.assertEqual(provider.requests, [])


class PageStatusTests(unittest.TestCase):
    def test_all_required_valid_is_ready(self):
        control = make_control("Ready", selector="#ready", current="Yes")
        self.assertEqual(make_orchestrator([control]).process_page([control], context()).status, OrchestratorStatus.READY_FOR_NAVIGATION)

    def test_temporary_control_issue_is_retry_required(self):
        control = make_control("Temporary", selector="#temporary", current="Existing")
        missing_provider = MappingControlProvider(())
        result = make_orchestrator([control], control_provider=missing_provider).process_page([control], context())
        self.assertEqual(result.status, OrchestratorStatus.RETRY_REQUIRED)

    def test_missing_exact_fact_status(self):
        control = make_control("Are you a citizen?", selector="#status-protected", kind="radio", options=(option("Yes"), option("No")), auto=True)
        self.assertEqual(make_orchestrator([control]).process_page([control], context()).status, OrchestratorStatus.BLOCKED_PROTECTED_FACT)

    def test_type_impossible_required_field_status(self):
        control = make_control("Required number", selector="#type-impossible", kind="number", current="", auto=True)
        provider = FakeAnswerProvider({"Required number": "many"})
        result = make_orchestrator([control], provider=provider).process_page([control], context())
        self.assertEqual(result.status, OrchestratorStatus.BLOCKED_TYPE_IMPOSSIBLE)

    def test_optional_invalid_field_does_not_block(self):
        control = make_control("Optional select", selector="#optional", kind="select", required=False, options=(), auto=True)
        result = make_orchestrator([control], provider=FakeAnswerProvider({"Optional select": None})).process_page([control], context())
        self.assertEqual(result.status, OrchestratorStatus.READY_FOR_NAVIGATION)


class FailureContainmentTests(unittest.TestCase):
    def test_extractor_exception_is_contained(self):
        result = make_orchestrator([], control_provider=MappingControlProvider()).process_page([RaisingControl()], context())
        self.assertEqual(result.status, OrchestratorStatus.FAILED)
        self.assertEqual(result.field_results[0].reason_code, "field_extraction_failed")

    def test_resolver_exception_is_contained(self):
        control = make_control("Resolver failure", selector="#resolver-failure", current="")
        resolver = RecordingResolver(fail_question="Resolver failure")
        result = make_orchestrator([control], resolver=resolver).process_page([control], context())
        self.assertEqual(result.status, OrchestratorStatus.FAILED)

    def test_writer_exception_is_contained(self):
        control = make_control("Writer failure", selector="#writer-failure", current="", auto=True)
        writer = RecordingWriter(fail_question="Writer failure")
        result = make_orchestrator([control], writer=writer, provider=FakeAnswerProvider(default="Answer")).process_page([control], context())
        self.assertEqual(result.status, OrchestratorStatus.FAILED)

    def test_remaining_fields_process_after_failure(self):
        failing = make_control("Resolver failure", selector="#remaining-failure", current="")
        valid = make_control("Independent", selector="#remaining-valid", current="Done")
        resolver = RecordingResolver(fail_question="Resolver failure")
        result = make_orchestrator([failing, valid], resolver=resolver).process_page([failing, valid], context())
        self.assertEqual(result.field_results[1].status, FieldProcessingStatus.PRESERVED)

    def test_diagnostics_redact_long_private_text(self):
        control = make_control("Private", selector="#private-diagnostic", current="", auto=True)
        private = "private candidate text " * 100
        result = make_orchestrator([control], provider=FakeAnswerProvider(default=private)).process_page([control], context())
        self.assertNotIn("private candidate text", repr(result))
        self.assertNotIn("private candidate text", repr(result.field_results[0]))


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_orchestrator_has_no_selenium_import(self):
        source = inspect.getsource(orchestrator_module).casefold()
        self.assertNotIn("selenium", source)
        self.assertNotIn("webdriver", source)

    def test_orchestrator_has_no_navigation_clicks(self):
        source = inspect.getsource(orchestrator_module).casefold()
        for forbidden in ("click_next(", "click_review(", "submit(", "navigate("):
            self.assertNotIn(forbidden, source)

    def test_orchestrator_has_no_page_lifecycle_behavior(self):
        source = inspect.getsource(orchestrator_module).casefold()
        for forbidden in ("modal.", "window.", "tabs.", "pagination."):
            self.assertNotIn(forbidden, source)

    def test_orchestrator_does_not_write_csv(self):
        source = inspect.getsource(orchestrator_module).casefold()
        for forbidden in ("csv.writer", "dictwriter", "to_csv("):
            self.assertNotIn(forbidden, source)

    def test_orchestrator_does_not_call_provider_directly(self):
        source = inspect.getsource(orchestrator_module).casefold()
        self.assertNotIn("answer_provider.answer", source)
        self.assertNotIn("gemini", source)


if __name__ == "__main__":
    unittest.main()
