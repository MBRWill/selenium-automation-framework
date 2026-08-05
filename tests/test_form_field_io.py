from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import inspect
import unittest

from modules.forms import (
    AnswerResult,
    AnswerSource,
    AnswerStatus,
    Confidence,
    ControlOption,
    ControlSnapshot,
    ControlValidity,
    ExtractionContext,
    FieldConstraints,
    FieldExtractor,
    FieldKind,
    FieldWriter,
    ValidationIssueKind,
    WriteRequest,
    WriteStatus,
)
from modules.forms import controls as controls_module
from modules.forms import extractor as extractor_module
from modules.forms import writer as writer_module


class FakeControl:
    def __init__(
        self,
        *,
        tag_name="input",
        input_type="text",
        question="Synthetic question",
        current_value=None,
        required=False,
        checked=None,
        options=(),
        constraints=FieldConstraints(),
        validity=ControlValidity(),
        attributes=(),
        selector="#field",
    ):
        self.tag_name = tag_name
        self.input_type = input_type
        self.question = question
        self.current_value = current_value
        self.required = required
        self.checked = checked
        self.options = list(options)
        self.constraints = constraints
        self.validity = validity
        self.attributes = tuple(attributes) or (
            ("id", selector.removeprefix("#")),
            ("name", "synthetic-field"),
            ("aria-label", question),
        )
        self.selector = selector
        self.clear_calls = 0
        self.enter_calls = 0
        self.select_calls = 0
        self.click_calls = 0
        self.mutations_to_ignore = 0
        self.ignore_all_mutations = False

    def snapshot(self):
        return ControlSnapshot(
            container_selector="div[data-test-form-element='synthetic']",
            control_selector=self.selector,
            option_selectors=tuple(
                item.selector for item in self.options if item.selector
            ),
            tag_name=self.tag_name,
            input_type=self.input_type,
            labels=(self.question,) if self.question is not None else (),
            accessible_text=self.question or "",
            attributes=self.attributes,
            current_value=self.current_value,
            required=self.required,
            checked=self.checked,
            options=tuple(self.options),
            constraints=self.constraints,
            validity=self.validity,
        )

    def _ignore(self):
        if self.ignore_all_mutations:
            return True
        if self.mutations_to_ignore:
            self.mutations_to_ignore -= 1
            return True
        return False

    def clear_text(self):
        self.clear_calls += 1
        if not self.ignore_all_mutations and self.mutations_to_ignore == 0:
            self.current_value = ""

    def enter_text(self, value):
        self.enter_calls += 1
        if not self._ignore():
            self.current_value = value

    def select_option(self, option_value):
        self.select_calls += 1
        if self._ignore():
            return
        self.options = [
            replace(item, selected=item.value == option_value)
            for item in self.options
        ]
        selected = next(item for item in self.options if item.selected)
        self.current_value = selected.value

    def click_choice(self, option_value):
        self.click_calls += 1
        if self._ignore():
            return
        if self.input_type == "checkbox":
            self.checked = bool(option_value)
            self.current_value = bool(option_value)
            return
        self.options = [
            replace(item, selected=item.value == option_value)
            for item in self.options
        ]
        selected = next(item for item in self.options if item.selected)
        self.current_value = selected.value


class FakeControlProvider:
    def __init__(self, control):
        self.control = control
        self.requery_calls = 0

    def requery(self, locator):
        self.requery_calls += 1
        return self.control


class SequenceControlProvider:
    def __init__(self, controls):
        self.controls = list(controls)
        self.requery_calls = 0

    def requery(self, locator):
        index = min(self.requery_calls, len(self.controls) - 1)
        self.requery_calls += 1
        return self.controls[index]


def option(
    text,
    *,
    value=None,
    selected=False,
    visible=True,
    enabled=True,
    placeholder=False,
):
    value = value or text.casefold().replace(" ", "-")
    return ControlOption(
        text=text,
        value=value,
        selector=f"[data-option='{value}']",
        visible=visible,
        enabled=enabled,
        selected=selected,
        placeholder=placeholder,
    )


def resolved(value, *, source=AnswerSource.PROVIDER):
    return AnswerResult(
        status=AnswerStatus.RESOLVED,
        value=value,
        source=source,
        confidence=Confidence.HIGH,
        reason_code="offline_test_answer",
        requires_review=source in {AnswerSource.PROVIDER, AnswerSource.DEFAULT},
    )


def preserved(value):
    return AnswerResult(
        status=AnswerStatus.PRESERVED,
        value=value,
        source=AnswerSource.LINKEDIN,
        confidence=Confidence.HIGH,
        reason_code="valid_linkedin_value",
    )


def extracted(control, context=None):
    return FieldExtractor().extract(control, context)


def write(control, answer, provider=None):
    provider = provider or FakeControlProvider(control)
    request = WriteRequest(
        extracted_field=extracted(control),
        answer_result=answer,
    )
    return FieldWriter().write(request, provider)


class ExtractionTests(unittest.TestCase):
    def test_text_input_extraction(self):
        result = extracted(FakeControl(current_value="Existing"))
        self.assertEqual(result.field.kind, FieldKind.TEXT)
        self.assertEqual(result.field.existing_value, "Existing")

    def test_textarea_extraction(self):
        result = extracted(FakeControl(tag_name="textarea", current_value="Long answer"))
        self.assertEqual(result.field.kind, FieldKind.TEXTAREA)

    def test_number_extraction_with_constraints(self):
        constraints = FieldConstraints(
            min_value=Decimal("1"), max_value=Decimal("10"), step=Decimal("0.5")
        )
        result = extracted(FakeControl(input_type="number", current_value="2.50", constraints=constraints))
        self.assertEqual(result.field.kind, FieldKind.NUMBER)
        self.assertEqual(result.field.existing_value, "2.5")
        self.assertEqual(result.field.constraints, constraints)

    def test_select_extraction_with_visible_options(self):
        control = FakeControl(
            tag_name="select",
            current_value="hybrid",
            options=(option("Remote"), option("Hybrid", selected=True)),
        )
        result = extracted(control)
        self.assertEqual(result.field.visible_options, ("Remote", "Hybrid"))
        self.assertEqual(result.field.existing_value, "Hybrid")

    def test_placeholder_select_is_not_preserved(self):
        control = FakeControl(
            tag_name="select",
            current_value="placeholder",
            required=True,
            options=(
                option("Select an option", value="placeholder", selected=True, placeholder=True),
                option("Remote"),
            ),
        )
        result = extracted(control)
        self.assertIsNone(result.field.existing_value)
        self.assertTrue(result.validation_state.option_required)

    def test_radio_group_extraction(self):
        control = FakeControl(
            input_type="radio",
            current_value="no",
            options=(option("Yes"), option("No", selected=True)),
        )
        result = extracted(control)
        self.assertEqual(result.field.kind, FieldKind.RADIO)
        self.assertEqual(result.field.existing_value, "No")

    def test_checkbox_extraction(self):
        checked = extracted(FakeControl(input_type="checkbox", checked=True))
        unchecked = extracted(FakeControl(input_type="checkbox", checked=False))
        self.assertIs(checked.field.existing_value, True)
        self.assertIs(unchecked.field.existing_value, False)

    def test_required_state_extraction(self):
        result = extracted(FakeControl(required=True, current_value="   "))
        self.assertTrue(result.field.required)
        self.assertTrue(result.validation_state.required_missing)

    def test_existing_value_extraction(self):
        result = extracted(FakeControl(current_value="Keep this"))
        self.assertEqual(result.field.existing_value, "Keep this")

    def test_validation_message_extraction(self):
        validity = ControlValidity(
            browser_valid=False,
            validation_message=" Please enter a valid value. ",
            type_mismatch=True,
        )
        result = extracted(FakeControl(validity=validity))
        self.assertEqual(result.validation_state.validation_message, "Please enter a valid value.")
        issues = FieldExtractor().validation_issues(result)
        self.assertEqual(issues[0].issue_kind, ValidationIssueKind.WRONG_TYPE)

    def test_spanish_question_text_is_preserved(self):
        question = "¿Cuántos años de experiencia tienes?"
        result = extracted(FakeControl(question=question))
        self.assertEqual(result.field.question, question)

    def test_normalized_semantic_question(self):
        result = extracted(FakeControl(question="¿Cuántos años de experiencia tienes?"))
        self.assertEqual(result.normalized_question, "cuantos anos de experiencia tienes")

    def test_hidden_options_are_excluded(self):
        result = extracted(FakeControl(
            tag_name="select",
            options=(option("Visible"), option("Hidden", visible=False)),
        ))
        self.assertEqual(result.field.visible_options, ("Visible",))

    def test_stable_field_identity_across_repeated_extraction(self):
        control = FakeControl(question="Same field", options=(option("Yes"), option("No")))
        context = ExtractionContext(application_id="application-1", job_id="job-1")
        first = extracted(control, context)
        second = extracted(control, context)
        self.assertEqual(first.field.field_key, second.field.field_key)
        self.assertNotIn("hash(", inspect.getsource(extractor_module))

    def test_option_signature_changes_field_identity(self):
        context = ExtractionContext(job_id="job-1")
        first = extracted(FakeControl(input_type="radio", options=(option("Yes"), option("No"))), context)
        second = extracted(FakeControl(input_type="radio", options=(option("Yes"), option("Maybe"))), context)
        self.assertNotEqual(first.field.field_key, second.field.field_key)

    def test_job_context_changes_field_identity(self):
        control = FakeControl(question="Same field")
        first = extracted(control, ExtractionContext(job_id="job-1"))
        second = extracted(control, ExtractionContext(job_id="job-2"))
        self.assertNotEqual(first.field.field_key, second.field.field_key)

    def test_no_control_object_is_stored_in_domain_models(self):
        control = FakeControl(current_value="private long answer " * 20)
        result = extracted(control)
        self.assertFalse(any(isinstance(value, FakeControl) for value in vars(result).values()))
        self.assertNotIn("private long answer", repr(result))
        self.assertNotIn(
            "private long answer",
            repr(ControlValidity(validation_message="private long answer")),
        )
        with self.assertRaises(FrozenInstanceError):
            result.normalized_question = "changed"

    def test_validation_flags_are_available_for_repair_handoff(self):
        validity = ControlValidity(
            browser_valid=False,
            range_underflow=True,
            step_mismatch=True,
            validation_message="Value is invalid",
        )
        result = extracted(FakeControl(input_type="number", current_value="0", validity=validity))
        kinds = {item.issue_kind for item in FieldExtractor().validation_issues(result)}
        self.assertEqual(kinds, {ValidationIssueKind.BELOW_MINIMUM, ValidationIssueKind.STEP_MISMATCH})


class WriterPreservationTests(unittest.TestCase):
    def test_matching_preserved_text_causes_no_write(self):
        control = FakeControl(current_value="Keep")
        result = write(control, preserved("Keep"))
        self.assertEqual(result.status, WriteStatus.SKIPPED_PRESERVED)
        self.assertEqual((control.clear_calls, control.enter_calls), (0, 0))

    def test_matching_preserved_select_causes_no_selection(self):
        control = FakeControl(tag_name="select", options=(option("Remote", selected=True), option("Hybrid")))
        result = write(control, preserved("Remote"))
        self.assertEqual(result.status, WriteStatus.SKIPPED_PRESERVED)
        self.assertEqual(control.select_calls, 0)

    def test_matching_selected_radio_causes_no_click(self):
        control = FakeControl(input_type="radio", options=(option("Yes", selected=True), option("No")))
        result = write(control, preserved("Yes"))
        self.assertEqual(result.status, WriteStatus.SKIPPED_PRESERVED)
        self.assertEqual(control.click_calls, 0)

    def test_matching_checkbox_causes_no_click(self):
        control = FakeControl(input_type="checkbox", checked=True)
        result = write(control, preserved(True))
        self.assertEqual(result.status, WriteStatus.SKIPPED_PRESERVED)
        self.assertEqual(control.click_calls, 0)


class TextWriterTests(unittest.TestCase):
    def test_text_is_cleared_entered_and_verified(self):
        control = FakeControl(current_value="Old")
        result = write(control, resolved("New answer"))
        self.assertEqual(result.status, WriteStatus.VERIFIED)
        self.assertEqual(control.current_value, "New answer")
        self.assertEqual((control.clear_calls, control.enter_calls), (1, 1))

    def test_textarea_is_written_and_verified(self):
        control = FakeControl(tag_name="textarea", current_value="Old")
        result = write(control, resolved("Updated explanation"))
        self.assertEqual(result.verified_value, "Updated explanation")

    def test_minimum_length_violation_is_rejected(self):
        control = FakeControl(constraints=FieldConstraints(min_length=5))
        result = write(control, resolved("No"))
        self.assertEqual(result.status, WriteStatus.FAILED)
        self.assertEqual(control.enter_calls, 0)

    def test_maximum_length_violation_is_rejected(self):
        control = FakeControl(constraints=FieldConstraints(max_length=4))
        result = write(control, resolved("Too long"))
        self.assertEqual(result.status, WriteStatus.FAILED)

    def test_pattern_violation_is_rejected(self):
        control = FakeControl(constraints=FieldConstraints(pattern=r"[A-Z]{3}"))
        result = write(control, resolved("abc"))
        self.assertEqual(result.status, WriteStatus.FAILED)
        self.assertEqual(control.enter_calls, 0)

    def test_failed_verification_retries_once_only(self):
        control = FakeControl(current_value="Old")
        control.ignore_all_mutations = True
        result = write(control, resolved("New"))
        self.assertEqual(result.status, WriteStatus.FAILED)
        self.assertEqual(result.retry_count, 1)
        self.assertEqual(control.enter_calls, 2)

    def test_dom_requery_succeeds_after_stale_replacement(self):
        stale = FakeControl(current_value="Old")
        stale.ignore_all_mutations = True
        replacement = FakeControl(current_value="Old")
        provider = SequenceControlProvider((stale, stale, replacement, replacement, replacement))
        request = WriteRequest(extracted(stale), resolved("New"))
        result = FieldWriter().write(request, provider)
        self.assertEqual(result.status, WriteStatus.VERIFIED)
        self.assertEqual(result.retry_count, 1)
        self.assertEqual(replacement.current_value, "New")


class NumberWriterTests(unittest.TestCase):
    def test_valid_integer_is_written(self):
        control = FakeControl(input_type="number", current_value="1")
        result = write(control, resolved("5"))
        self.assertEqual(result.verified_value, "5")

    def test_valid_decimal_is_written(self):
        control = FakeControl(
            input_type="number",
            constraints=FieldConstraints(step=Decimal("0.5")),
        )
        result = write(control, resolved("2.5"))
        self.assertEqual(result.status, WriteStatus.VERIFIED)

    def test_boolean_is_rejected(self):
        control = FakeControl(input_type="number")
        result = write(control, resolved(True))
        self.assertEqual(result.status, WriteStatus.FAILED)
        self.assertEqual(control.enter_calls, 0)

    def test_free_text_is_rejected(self):
        control = FakeControl(input_type="number")
        result = write(control, resolved("many"))
        self.assertEqual(result.status, WriteStatus.FAILED)

    def test_minimum_constraint_is_enforced(self):
        control = FakeControl(input_type="number", constraints=FieldConstraints(min_value=Decimal("2")))
        self.assertEqual(write(control, resolved("1")).status, WriteStatus.FAILED)

    def test_maximum_constraint_is_enforced(self):
        control = FakeControl(input_type="number", constraints=FieldConstraints(max_value=Decimal("10")))
        self.assertEqual(write(control, resolved("11")).status, WriteStatus.FAILED)

    def test_step_constraint_is_enforced(self):
        control = FakeControl(
            input_type="number",
            constraints=FieldConstraints(min_value=Decimal("1"), step=Decimal("2")),
        )
        self.assertEqual(write(control, resolved("2")).status, WriteStatus.FAILED)

    def test_written_numeric_value_is_verified(self):
        control = FakeControl(input_type="number", current_value="0")
        result = write(control, resolved("7.00"))
        self.assertEqual(result.status, WriteStatus.VERIFIED)
        self.assertEqual(result.attempted_value, "7")
        self.assertEqual(result.verified_value, "7")


class SelectWriterTests(unittest.TestCase):
    def test_exact_visible_option_is_selected(self):
        control = FakeControl(tag_name="select", options=(option("Remote"), option("Hybrid")))
        result = write(control, resolved("Hybrid"))
        self.assertEqual(result.status, WriteStatus.VERIFIED)
        self.assertEqual(control.select_calls, 1)

    def test_accent_normalized_option_maps_si_to_si(self):
        control = FakeControl(tag_name="select", options=(option("Si"), option("No")))
        result = write(control, resolved("Sí"))
        self.assertEqual(result.verified_value, "Si")

    def test_missing_option_fails_safely(self):
        control = FakeControl(tag_name="select", options=(option("Remote"), option("Hybrid")))
        result = write(control, resolved("On-site"))
        self.assertEqual(result.status, WriteStatus.FAILED)

    def test_first_option_is_not_selected_when_matching_fails(self):
        control = FakeControl(tag_name="select", options=(option("First"), option("Second")))
        write(control, resolved("Missing"))
        self.assertEqual(control.select_calls, 0)
        self.assertFalse(any(item.selected for item in control.options))

    def test_disabled_or_hidden_option_is_rejected(self):
        for candidate in (
            option("Unavailable", enabled=False),
            option("Unavailable", visible=False),
        ):
            with self.subTest(candidate=candidate):
                control = FakeControl(tag_name="select", options=(candidate, option("Other")))
                self.assertEqual(write(control, resolved("Unavailable")).status, WriteStatus.FAILED)

    def test_selection_verification_is_required(self):
        control = FakeControl(tag_name="select", options=(option("Remote"), option("Hybrid")))
        control.ignore_all_mutations = True
        result = write(control, resolved("Hybrid"))
        self.assertEqual(result.status, WriteStatus.FAILED)
        self.assertEqual(control.select_calls, 2)


class RadioWriterTests(unittest.TestCase):
    def test_yes_maps_to_visible_yes(self):
        control = FakeControl(input_type="radio", options=(option("Yes"), option("No")))
        self.assertEqual(write(control, resolved("Yes")).verified_value, "Yes")

    def test_yes_maps_to_visible_si(self):
        control = FakeControl(input_type="radio", options=(option("Sí"), option("No")))
        self.assertEqual(write(control, resolved("Yes")).verified_value, "Sí")

    def test_no_maps_to_visible_no(self):
        control = FakeControl(input_type="radio", options=(option("Sí"), option("No")))
        self.assertEqual(write(control, resolved("No")).verified_value, "No")

    def test_selected_state_is_verified(self):
        control = FakeControl(input_type="radio", options=(option("Yes"), option("No")))
        result = write(control, resolved("No"))
        self.assertTrue(next(item for item in control.options if item.text == "No").selected)
        self.assertEqual(result.status, WriteStatus.VERIFIED)

    def test_verification_failure_retries_once(self):
        control = FakeControl(input_type="radio", options=(option("Yes"), option("No")))
        control.mutations_to_ignore = 1
        result = write(control, resolved("Yes"))
        self.assertEqual(result.status, WriteStatus.VERIFIED)
        self.assertEqual(result.retry_count, 1)
        self.assertEqual(control.click_calls, 2)

    def test_already_correct_protected_answer_is_not_clicked(self):
        control = FakeControl(input_type="radio", options=(option("Yes"), option("No", selected=True)))
        result = write(control, resolved("No", source=AnswerSource.PROFILE))
        self.assertEqual(result.status, WriteStatus.VERIFIED)
        self.assertEqual(control.click_calls, 0)

    def test_conflicting_value_is_corrected_by_profile_answer(self):
        control = FakeControl(input_type="radio", options=(option("Yes", selected=True), option("No")))
        result = write(control, resolved("No", source=AnswerSource.PROFILE))
        self.assertEqual(result.verified_value, "No")
        self.assertEqual(control.click_calls, 1)


class CheckboxWriterTests(unittest.TestCase):
    def test_explicit_true_checks_box(self):
        control = FakeControl(input_type="checkbox", checked=False)
        result = write(control, resolved(True, source=AnswerSource.POLICY))
        self.assertIs(result.verified_value, True)
        self.assertEqual(control.click_calls, 1)

    def test_explicit_false_unchecks_box(self):
        control = FakeControl(input_type="checkbox", checked=True)
        result = write(control, resolved(False, source=AnswerSource.POLICY))
        self.assertIs(result.verified_value, False)
        self.assertEqual(control.click_calls, 1)

    def test_optional_unchecked_box_remains_unchanged(self):
        control = FakeControl(input_type="checkbox", checked=False, required=False)
        result = write(control, resolved(False, source=AnswerSource.POLICY))
        self.assertEqual(result.status, WriteStatus.VERIFIED)
        self.assertFalse(result.changed)
        self.assertEqual(control.click_calls, 0)

    def test_checked_state_is_verified(self):
        control = FakeControl(input_type="checkbox", checked=False)
        control.ignore_all_mutations = True
        result = write(control, resolved(True, source=AnswerSource.POLICY))
        self.assertEqual(result.status, WriteStatus.FAILED)
        self.assertEqual(control.click_calls, 2)


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_writer_never_calls_answer_provider_or_gemini(self):
        source = inspect.getsource(writer_module).casefold()
        self.assertNotIn("answerprovider", source)
        self.assertNotIn("gemini", source)

    def test_control_protocol_has_no_navigation_surface(self):
        source = inspect.getsource(controls_module).casefold()
        for forbidden in ("navigate", "tabs", "windows", "driver.quit", "javascript"):
            self.assertNotIn(forbidden, source)

    def test_writer_contains_no_navigation_or_submission_action(self):
        source = inspect.getsource(writer_module).casefold()
        for forbidden in (
            "navigate(",
            "click_next(",
            "click_review(",
            "submit(",
            "pagination.",
        ):
            self.assertNotIn(forbidden, source)

    def test_writer_contains_no_modal_or_window_logic(self):
        source = inspect.getsource(writer_module).casefold()
        self.assertNotIn("modal", source)
        self.assertNotIn("window", source)

    def test_domain_modules_have_no_selenium_dependency(self):
        source = "\n".join(
            inspect.getsource(module).casefold()
            for module in (controls_module, extractor_module, writer_module)
        )
        self.assertNotIn("selenium", source)
        self.assertNotIn("webdriver", source)

    def test_write_diagnostics_redact_long_answers(self):
        control = FakeControl()
        request = WriteRequest(extracted(control), resolved("private answer " * 50))
        result = FieldWriter().write(request, FakeControlProvider(control))
        self.assertNotIn("private answer", repr(request))
        self.assertNotIn("private answer", repr(result))


if __name__ == "__main__":
    unittest.main()
