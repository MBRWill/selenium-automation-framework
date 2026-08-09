import ast
from pathlib import Path
import re
import unicodedata
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runAiBot2.py"


class NoSuchElementException(Exception):
    pass


class By:
    XPATH = "xpath"
    TAG_NAME = "tag"
    CLASS_NAME = "class"


class Label:
    def __init__(self, text, target=None):
        self.text = text
        self.target = target

    def find_element(self, by, value):
        if by == By.TAG_NAME and value == "span":
            return self
        raise NoSuchElementException()


class Input:
    def __init__(self, value="", attrs=None):
        self.value = value
        self.attrs = attrs or {}
        self.selected = False

    def get_attribute(self, name):
        if name == "value":
            return self.value
        return self.attrs.get(name)

    def get_property(self, name):
        if name == "validationMessage":
            return self.attrs.get("validationMessage", "")
        if name == "validity":
            return self.attrs.get("validity", {})
        return None

    def clear(self):
        self.value = ""

    def send_keys(self, value):
        self.value = str(value)

    def is_selected(self):
        return self.selected


class ValidatingNumericInput(Input):
    def __init__(self, validation_messages):
        super().__init__(attrs={"type": "number", "min": "0", "step": "0.01"})
        self.validation_messages = list(validation_messages)
        self.validation_index = 0
        self.sent_values = []

    def get_property(self, name):
        if name != "validationMessage":
            return None
        if not self.value:
            return self.validation_messages[0] if self.validation_messages else ""
        if self.validation_index < len(self.validation_messages):
            message = self.validation_messages[self.validation_index]
            self.validation_index += 1
            return message
        return self.validation_messages[-1] if self.validation_messages else ""

    def send_keys(self, value):
        super().send_keys(value)
        self.sent_values.append(str(value))


class NumericIntentTextInput(Input):
    def __init__(self, value="", always_invalid=False):
        super().__init__(value, {"type": "text", "aria-required": "true"})
        self.always_invalid = always_invalid
        self.sent_values = []

    def get_property(self, name):
        valid_number = self.value.isdigit() and int(self.value) > 0
        invalid = self.always_invalid or not valid_number
        if name == "validationMessage":
            return "numeric value required" if invalid else ""
        if name == "validity":
            return {"typeMismatch": invalid, "valid": not invalid}
        return None

    def send_keys(self, value):
        super().send_keys(value)
        self.sent_values.append(str(value))


class DeferredNumericSalaryInput(Input):
    def __init__(self):
        super().__init__(attrs={"type": "text", "aria-required": "true"})
        self.sent_values = []

    def get_property(self, name):
        invalid = bool(self.value) and not self.value.isdigit()
        if name == "validationMessage":
            return "Enter a decimal number larger than 0.0" if invalid else ""
        if name == "validity":
            return {"typeMismatch": invalid, "valid": not invalid}
        return None

    def send_keys(self, value):
        super().send_keys(value)
        self.sent_values.append(str(value))


class SelectOption:
    def __init__(self, text, attrs=None):
        self.text = text
        self.attrs = {"value": text}
        self.attrs.update(attrs or {})

    def get_attribute(self, name):
        return self.attrs.get(name)


class SelectControl(Input):
    def __init__(self, options, selected, attrs=None, option_attrs=None):
        super().__init__(attrs=attrs)
        option_attrs = option_attrs or {}
        self.options = [
            SelectOption(option, option_attrs.get(option)) for option in options
        ]
        self.selected = selected

    @property
    def first_selected_option(self):
        return next(option for option in self.options if option.text == self.selected)

    def select_by_visible_text(self, answer):
        if answer not in [option.text for option in self.options]:
            raise NoSuchElementException()
        self.selected = answer


class RadioOption(Input):
    def __init__(self, option_id, text):
        super().__init__(attrs={"id": option_id})
        self.value = text
        self.label = Label(text, self)
        self.group = []


class RadioControl(Input):
    def __init__(self, label, options, attrs=None):
        super().__init__(attrs=attrs)
        self.label = label
        self.options = [RadioOption(f"option-{index}", text) for index, text in enumerate(options)]
        for option in self.options:
            option.group = self.options

    def find_elements(self, by, value):
        return self.options if by == By.TAG_NAME and value == "input" else []


class Question(Input):
    def __init__(
        self, kind, label, control, required=True, validation_message=""
    ):
        super().__init__(attrs={"aria-required": "true" if required else "false"})
        self.kind = kind
        self.label = label
        self.control = control
        self.validation_message = validation_message

    def find_element(self, by, value):
        if by == By.TAG_NAME and value == "label":
            return Label(self.label)
        raise NoSuchElementException()

    def find_elements(self, by, value):
        if self.validation_message and (
            "inline-feedback" in value
            or "error-message" in value
            or 'role="alert"' in value
        ):
            return [SimpleNamespace(
                text=self.validation_message,
                is_displayed=lambda: True,
            )]
        return []


class Modal:
    def __init__(self, questions):
        self.questions = questions

    def find_elements(self, by, value):
        return self.questions


class ClickableButton(Input):
    def __init__(self, text="", displayed=True, enabled=True, attrs=None):
        super().__init__(attrs=attrs)
        self.text = text
        self.displayed = displayed
        self.enabled = enabled
        self.clicked = False

    def is_displayed(self):
        return self.displayed

    def is_enabled(self):
        return self.enabled

    def click(self):
        self.clicked = True


class SafetyDialog:
    def __init__(self, close_button, continue_button, review_button):
        self.close_button = close_button
        self.continue_button = continue_button
        self.review_button = review_button

    def find_elements(self, by, xpath):
        if "Job search safety reminder" in xpath:
            return [SimpleNamespace(text="Job search safety reminder")]
        if "Review job post" in xpath:
            return [self.review_button]
        if "Continue applying" in xpath:
            return [self.continue_button]
        if "artdeco-modal__dismiss" in xpath:
            return [self.close_button]
        return []


class DialogBrowser:
    def __init__(self, dialogs):
        self.dialogs = dialogs
        self.closed = False

    def find_elements(self, by, xpath):
        return self.dialogs if '@role="dialog"' in xpath else []

    def close(self):
        self.closed = True


class CleanupButton(ClickableButton):
    def __init__(self, text="", attrs=None, on_click=None, events=None):
        super().__init__(text=text, attrs=attrs)
        self.on_click = on_click
        self.events = events

    def click(self):
        super().click()
        if self.events is not None:
            self.events.append(self.text or self.get_attribute("aria-label"))
        if self.on_click is not None:
            self.on_click()


class CleanupDialog:
    def __init__(self, text="", buttons=None, displayed=True):
        self.text = text
        self.buttons = buttons or []
        self.displayed = displayed

    def is_displayed(self):
        return self.displayed

    def get_attribute(self, _name):
        return None

    def find_elements(self, by, xpath):
        if by == By.XPATH and ".//button" in xpath:
            return self.buttons
        return []


class CleanupBrowser:
    def __init__(self, easy_modal=None, discard_dialog=None):
        self.easy_modal = easy_modal
        self.discard_dialog = discard_dialog
        self.window_close_called = False

    def find_elements(self, by, xpath):
        if "jobs-easy-apply-modal" in xpath:
            return [self.easy_modal] if self.easy_modal is not None else []
        if '@role="dialog"' in xpath:
            return [self.discard_dialog] if self.discard_dialog is not None else []
        return []

    def close(self):
        self.window_close_called = True


class GenericOverlayBrowser(CleanupBrowser):
    def __init__(self, overlay=None):
        super().__init__(None, None)
        self.overlay = overlay

    def find_elements(self, by, xpath):
        if "jobs-easy-apply-modal" in xpath:
            return []
        if any(marker in xpath for marker in (
            '@role="dialog"',
            "data-test-modal-container",
            "artdeco-modal-overlay",
            '" artdeco-modal "',
        )):
            return [self.overlay] if self.overlay is not None else []
        return []


class AppliedStateJob:
    def __init__(self, applied=False):
        self.applied = applied

    @property
    def text(self):
        return "Applied" if self.applied else "Open"

    def find_elements(self, by, xpath):
        if self.applied and "footer-job-state" in xpath:
            return [SimpleNamespace(
                text="Applied",
                is_displayed=lambda: True,
            )]
        return []


class DelayedCleanupBrowser(CleanupBrowser):
    def __init__(self, easy_modal, discard_dialog, hidden_checks=1):
        super().__init__(easy_modal, discard_dialog)
        self.hidden_checks = hidden_checks
        self.discard_checks = 0

    def find_elements(self, by, xpath):
        if '@role="dialog"' in xpath and self.discard_dialog is not None:
            if not self.discard_dialog.is_displayed():
                return []
            self.discard_checks += 1
            if self.discard_checks <= self.hidden_checks:
                return []
            return [self.discard_dialog]
        return super().find_elements(by, xpath)


class SyntheticJobCard:
    def __init__(self, browser, events):
        self.browser = browser
        self.events = events
        self.clicked = False

    def click(self):
        active_modal = (
            self.browser.easy_modal is not None
            and self.browser.easy_modal.is_displayed()
        )
        active_discard = (
            self.browser.discard_dialog is not None
            and self.browser.discard_dialog.is_displayed()
        )
        overlay = getattr(self.browser, "overlay", None)
        active_overlay = overlay is not None and overlay.is_displayed()
        if active_modal or active_discard or active_overlay:
            raise AssertionError("job card clicked under modal")
        self.clicked = True
        self.events.append("job-card")


class SubmitModal(Modal):
    def __init__(self, questions, submit_button, displayed=True):
        super().__init__(questions)
        self.submit_button = submit_button
        self.displayed = displayed

    def is_displayed(self):
        return self.displayed

    def find_elements(self, by, xpath):
        if "data-test-form-element" in xpath:
            return self.questions
        if "Submit application" in xpath:
            return [self.submit_button]
        return []


class ResumeModal(Modal):
    def __init__(
        self,
        questions,
        selected_cards=None,
        resume_radios=None,
        uploaded_elements=None,
        file_inputs=None,
    ):
        super().__init__(questions)
        self.selected_cards = selected_cards or []
        self.resume_radios = resume_radios or []
        self.uploaded_elements = uploaded_elements or []
        self.file_inputs = file_inputs or []

    def find_elements(self, by, xpath):
        if "data-test-form-element" in xpath:
            return self.questions
        if 'input[@type="radio"' in xpath:
            return self.resume_radios
        if 'input[@type="file"' in xpath:
            return self.file_inputs
        if "@data-selected" in xpath:
            return self.selected_cards
        if '"uploaded"' in xpath:
            return self.uploaded_elements
        return []


class Actions:
    def __init__(self):
        self.element = None
        self.sent_keys = []
        self.on_send_keys = None

    def move_to_element(self, element):
        self.element = element
        return self

    def click(self):
        target = getattr(self.element, "target", self.element)
        for option in getattr(target, "group", []):
            option.selected = False
        target.selected = True
        return self

    def perform(self):
        return self

    def send_keys(self, value):
        self.sent_keys.append(value)
        if self.on_send_keys is not None:
            self.on_send_keys(value)
        return self


def try_xp(element, xpath, click=True):
    if isinstance(element, Question):
        checks = {
            "select": ".//select",
            "radio": "radio-button-form-component",
            "text": "input[@type='text'",
            "number": "input[@type='text'",
            "textarea": ".//textarea",
            "checkbox": "input[@type='checkbox']",
        }
        if checks.get(element.kind, "") in xpath:
            return element.control
        if ".//label[@for]" in xpath:
            return Label(element.label)
        return False
    if isinstance(element, RadioControl):
        if "__title" in xpath:
            return Label(element.label)
        match = re.search(r'@for=\"([^\"]+)', xpath)
        if match:
            return next(option.label for option in element.options if option.get_attribute("id") == match.group(1))
        match = re.search(r"normalize-space\\(\\)='([^']+)", xpath)
        if match:
            return next((option.label for option in element.options if option.label.text == match.group(1)), False)
    return False


def load_runtime_functions(
    ai_mock,
    review_queue=None,
    verified_mock=None,
    deterministic_mock=None,
):
    tree = ast.parse(RUNTIME.read_text(encoding="utf-8"))
    wanted = {
        "answer_common_questions",
        "_normalized_form_text",
        "_is_resume_attachment_question",
        "_localized_positive_option",
        "_resume_selected_in_modal",
        "_is_required",
        "_validation_details",
        "_field_constraints",
        "_numeric_intent_from_question",
        "_is_numeric_control",
        "_validation_category",
        "_plain_decimal",
        "_normalize_numeric_input",
        "_browser_numeric_value_is_valid",
        "_fill_numeric_control",
        "_unknown_answer",
        "_answers_match",
        "_is_select_placeholder",
        "_is_positive_answer",
        "_is_negative_answer",
        "_record_answer_review_event",
        "_verified_preserved_answer",
        "_preserved_override_reason",
        "_record_required_review_event",
        "_is_overall_experience_question",
        "_browser_control_is_invalid",
        "_question_label",
        "_linkedin_validation_message",
        "_collect_invalid_required_fields",
        "_form_page_signature",
        "_fill_repair_field",
        "repair_invalid_required_fields",
        "_repair_after_failed_advance",
        "_find_job_search_safety_reminder",
        "_close_job_search_safety_reminder",
        "_element_is_visible",
        "_element_is_enabled",
        "_visible_easy_apply_modals",
        "_control_text",
        "_localized_modal_action",
        "_scoped_action_buttons",
        "_visible_modal_dialogs",
        "_visible_top_level_overlays",
        "_abandonment_confirmation_text",
        "_visible_abandonment_dialogs",
        "_visible_discard_dialogs",
        "_success_confirmation_text",
        "_visible_success_modals",
        "_success_dismiss_buttons",
        "_wait_for_success_modal_absent",
        "_dismiss_confirmed_success_modal",
        "_cleanup_confirmed_success_modal",
        "_post_submit_validation_detected",
        "_job_applied_state_detected",
        "_post_submit_snapshot",
        "_wait_for_post_submit_state",
        "_log_post_submit_state",
        "_easy_apply_blocker_state",
        "_cleanup_easy_apply_modal_once",
        "_cleanup_easy_apply_modal",
        "_classify_visible_overlays",
        "_guard_next_job_click",
        "_visible_enabled_submit_button",
        "_final_review_reached_from_submit_button",
        "_record_review_outcome",
        "answer_questions",
    }
    body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = {
        "WebElement": object,
        "By": By,
        "NoSuchElementException": NoSuchElementException,
        "Select": lambda control: control,
        "try_xp": try_xp,
        "find_by_class": lambda *_: (_ for _ in ()).throw(NoSuchElementException()),
        "actions": Actions(),
        "driver": SimpleNamespace(execute_script=lambda *_: True),
        "Keys": SimpleNamespace(ARROW_DOWN="", ENTER="", ESCAPE="escape"),
        "sleep": lambda _: None,
        "re": re,
        "unicodedata": unicodedata,
        "Decimal": __import__("decimal").Decimal,
        "InvalidOperation": __import__("decimal").InvalidOperation,
        "print_lg": lambda *_args, **_kwargs: None,
        "answer_unknown_question": ai_mock,
        "answer_verified_question": verified_mock or Mock(return_value=SimpleNamespace(
            can_answer=False,
            answer="",
            reason_code="exact_fact_unavailable",
            provider_request_count=0,
        )),
        "answer_deterministic_question": deterministic_mock or Mock(return_value=SimpleNamespace(
            can_answer=False,
            answer="",
            reason_code="exact_fact_unavailable",
            provider_request_count=0,
        )),
        "is_experience_capability_question": lambda label: (
            any(marker in label.casefold() for marker in (
                "experience",
                "experiencia",
                "has llevado",
                "trabajando en asesoría",
                "trabajando en gestoría",
            ))
            and not any(marker in label.casefold() for marker in (
                "salary",
                "sponsorship",
                "visa",
                "authorization",
            ))
        ),
        "is_citizenship_question": lambda label: any(
            marker in label.casefold()
            for marker in (
                "citizen", "citizenship", "nationality",
                "ciudadan", "nacionalidad", "citoyen", "nationalit",
            )
        ),
        "ai_answer_review_queue": review_queue,
        "ai_review_context": {
            "job_id": "job-1",
            "company": "Synthetic company",
            "job_title": "Synthetic job",
        },
        "overwrite_previous_answers": False,
        "require_visa": "Configured visa",
        "gender": "Configured gender",
        "disability_status": "Configured disability",
        "us_citizenship": "Configured authorization",
        "veteran_status": "Configured veteran",
        "years_of_experience": "7",
        "earliest_start_date": "Configured date",
        "phone_number": "Configured phone",
        "street": "Configured street",
        "current_city": "Configured city",
        "full_name": "Configured full name",
        "first_name": "Configured first",
        "middle_name": "Configured middle",
        "last_name": "Configured last",
        "recent_employer": "Configured employer",
        "notice_period_months": "1",
        "notice_period_weeks": "0",
        "notice_period": "30",
        "current_ctc_monthly": "1",
        "current_ctc_lakhs": "2",
        "current_ctc": "3",
        "desired_salary_monthly": "4",
        "desired_salary_lakhs": "5",
        "desired_salary": "6",
        "linkedIn": "Configured link",
        "website": "Configured website",
        "confidence_level": "8",
        "linkedin_headline": "Configured headline",
        "state": "Configured state",
        "zipcode": "Configured postcode",
        "country": "Configured country",
        "linkedin_summary": "Configured summary",
        "cover_letter": "Configured cover letter",
    }
    exec(compile(ast.Module(body=body, type_ignores=[]), str(RUNTIME), "exec"), namespace)
    return namespace


class MinimalFallbackIntegrationTests(unittest.TestCase):
    def answer(
        self,
        questions,
        ai_mock,
        review_queue=None,
        verified_mock=None,
        deterministic_mock=None,
        modal=None,
    ):
        namespace = load_runtime_functions(
            ai_mock,
            review_queue,
            verified_mock,
            deterministic_mock,
        )
        unresolved = set()
        namespace["answer_questions"](
            modal or Modal(questions),
            set(),
            "Configured city",
            "Synthetic job",
            unresolved,
            "Synthetic description",
        )
        return unresolved

    def test_configured_years_bypasses_gemini(self):
        ai = Mock(side_effect=AssertionError("Gemini must not be called"))
        field = Input(attrs={"type": "text", "aria-required": "true"})
        self.answer([Question("text", "Years of experience", field)], ai)
        self.assertEqual(field.value, "7")
        ai.assert_not_called()

    def test_total_professional_experience_uses_global_years(self):
        for question in (
            "How many total years of professional experience do you have?",
            "¿Cuántos años totales de experiencia profesional tienes?",
        ):
            with self.subTest(question=question):
                ai = Mock(side_effect=AssertionError("Gemini must not be called"))
                field = Input(attrs={"type": "number", "aria-required": "true"})
                self.answer([Question("number", question, field)], ai)
                self.assertEqual(field.value, "7")
                ai.assert_not_called()

    def test_spanish_skill_years_routes_to_profile_helper(self):
        ai = Mock(return_value=SimpleNamespace(can_answer=True, answer="5", reason_code="exact_skill_years"))
        field = Input(attrs={"type": "number", "aria-required": "true"})
        self.answer([Question("number", "¿Cuántos años de experiencia tienes con SQL?", field)], ai)
        self.assertEqual(field.value, "5")
        self.assertNotEqual(field.value, "7")
        ai.assert_called_once()

    def test_missing_skill_scalar_routes_to_gemini_not_global_years(self):
        for question in (
            "How many years of experience do you have with Python?",
            "How many years have you worked with NumPy?",
        ):
            with self.subTest(question=question):
                ai = Mock(return_value=SimpleNamespace(can_answer=True, answer="3", reason_code="grounded_ai_answer"))
                field = Input(attrs={"type": "number", "aria-required": "true"})
                self.answer([Question("number", question, field)], ai)
                self.assertEqual(field.value, "3")
                self.assertNotEqual(field.value, "7")
                ai.assert_called_once()

    def test_existing_contact_values_bypass_gemini(self):
        ai = Mock(side_effect=AssertionError("Gemini must not be called"))
        review_queue = Mock()
        email = SelectControl(["Synthetic email"], "Synthetic email")
        country_code = SelectControl(["Synthetic country code"], "Synthetic country code")
        phone = Input("Synthetic phone", {"type": "text"})
        self.answer(
            [
                Question("select", "Email", email),
                Question("select", "Phone country code", country_code),
                Question("text", "Phone", phone),
            ],
            ai,
            review_queue,
        )
        self.assertEqual(email.selected, "Synthetic email")
        self.assertEqual(country_code.selected, "Synthetic country code")
        self.assertEqual(phone.value, "Synthetic phone")
        ai.assert_not_called()
        review_queue.record_answer.assert_not_called()
        review_queue.record_required_event.assert_not_called()

    def test_provider_backed_answer_is_recorded_once(self):
        review_queue = Mock()
        ai = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="Supported answer",
            reason_code="grounded_ai_answer",
            provider_request_count=1,
        ))
        field = Input(attrs={"type": "text", "aria-required": "true"})
        self.answer(
            [Question("text", "Ordinary unmatched question", field)],
            ai,
            review_queue,
        )
        self.assertEqual(field.value, "Supported answer")
        review_queue.record_answer.assert_called_once()
        call = review_queue.record_answer.call_args.kwargs
        self.assertEqual(call["provider_request_count"], 1)
        self.assertEqual(call["application_outcome"], "answer_filled")

    def test_numeric_currency_and_units_are_removed_only_for_numeric_controls(self):
        for proposed in ("EUR 15.38", "€15.38 per hour"):
            with self.subTest(proposed=proposed):
                review_queue = Mock()
                ai = Mock(return_value=SimpleNamespace(
                    can_answer=True,
                    answer=proposed,
                    reason_code="grounded_ai_answer",
                    provider_request_count=1,
                ))
                field = Input(attrs={
                    "type": "number",
                    "min": "0.0",
                    "step": "0.01",
                    "aria-required": "true",
                })
                unresolved = self.answer(
                    [Question("number", "Expected hourly rate", field)],
                    ai,
                    review_queue,
                )
                self.assertEqual(field.value, "15.38")
                self.assertFalse(unresolved)
                call = review_queue.record_answer.call_args.kwargs
                self.assertEqual(call["proposed_answer"], "15.38")
                self.assertEqual(call["reason_code"], "numeric_input_normalized")
                self.assertIn(proposed, call["reviewer_notes"])
                self.assertFalse(call["force_high_priority"])

        ai = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="EUR 15.38 per hour",
            reason_code="grounded_ai_answer",
            provider_request_count=1,
        ))
        text = Input(attrs={"type": "text", "aria-required": "true"})
        self.answer([Question("text", "Describe your expected rate", text)], ai)
        self.assertEqual(text.value, "EUR 15.38 per hour")

    def test_numeric_normalizer_respects_min_max_and_step(self):
        normalize = load_runtime_functions(Mock())["_normalize_numeric_input"]
        valid = Input(attrs={
            "type": "number",
            "min": "0",
            "max": "100",
            "step": "0.01",
        })
        self.assertEqual(normalize("€15,38 hourly", valid), "15.38")
        self.assertEqual(normalize("USD 15.38/hour", valid), "15.38")
        salary_control = Input(attrs={"type": "number", "min": "0", "step": "1"})
        self.assertEqual(normalize("32000 EUR annual", salary_control), "32000")
        self.assertEqual(normalize("EUR 32000", salary_control), "32000")
        self.assertEqual(normalize("€32,000 per year", salary_control), "32000")
        self.assertEqual(
            normalize("32.000 € brutos anuales", salary_control), "32000"
        )
        self.assertEqual(
            normalize("4 weeks", Input(attrs={"type": "number"})),
            "4",
        )

        below_minimum = Input(attrs={"type": "number", "min": "20"})
        self.assertIsNone(normalize("15.38", below_minimum))

        above_maximum = Input(attrs={"type": "number", "max": "10"})
        self.assertIsNone(normalize("15.38", above_maximum))

        wrong_step = Input(attrs={"type": "number", "step": "1"})
        self.assertIsNone(normalize("15.38", wrong_step))

    def test_unrelated_numeric_zeroes_and_salary_remain_independent(self):
        ai = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="0",
            reason_code="grounded_ai_answer",
            provider_request_count=1,
        ))
        projects = Input(attrs={"type": "number", "aria-required": "true"})
        self.answer(
            [Question("number", "Number of projects completed", projects)],
            ai,
        )
        self.assertEqual(projects.value, "0")

        notice = Input(attrs={"type": "number", "aria-required": "true"})
        self.answer([Question("number", "Notice period in weeks", notice)], Mock())
        self.assertEqual(notice.value, "0")

        salary_ai = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="32000",
            reason_code="exact_profile_fact",
            provider_request_count=0,
        ))
        salary = Input(attrs={"type": "number", "aria-required": "true"})
        self.answer([Question("number", "Expected annual salary", salary)], salary_ai)
        self.assertEqual(salary.value, "32000")

    def test_salary_range_preserved_no_is_overridden_without_provider(self):
        provider = Mock(side_effect=AssertionError(
            "Gemini must not be called for a safe salary comparison"
        ))
        review_queue = Mock()
        exact = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="Sí",
            reason_code="salary_range_accepted_from_expected_salary",
            provider_request_count=0,
            original_answer=(
                "offered_annual_range_eur=35000-41000; "
                "expected_annual_salary_eur=32000"
            ),
        ))
        field = RadioControl(
            "¿Estás dispuesto/a a aceptar el rango salarial ofrecido entre 35–41k?",
            ["Sí", "No"],
        )
        field.options[1].selected = True
        self.answer(
            [Question(
                "radio",
                "¿Estás dispuesto/a a aceptar el rango salarial ofrecido entre 35–41k?",
                field,
            )],
            provider,
            review_queue,
            exact,
        )
        self.assertTrue(field.options[0].selected)
        self.assertFalse(field.options[1].selected)
        provider.assert_not_called()
        call = review_queue.record_answer.call_args.kwargs
        self.assertEqual(
            call["reason_code"],
            "salary_range_accepted_from_expected_salary",
        )
        self.assertEqual(call["provider_request_count"], 0)
        self.assertIn("offered_annual_range_eur=35000-41000", call["reviewer_notes"])
        self.assertFalse(call["force_high_priority"])

    def test_numeric_salary_control_receives_plain_amount(self):
        review_queue = Mock()
        answer = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="32000 EUR annual",
            reason_code="grounded_ai_answer",
            provider_request_count=1,
        ))
        field = Input(attrs={
            "type": "number",
            "min": "0.01",
            "step": "0.01",
            "aria-required": "true",
        })
        unresolved = self.answer(
            [Question("number", "Expected annual salary", field)],
            answer,
            review_queue,
        )
        self.assertEqual(field.value, "32000")
        self.assertFalse(unresolved)
        call = review_queue.record_answer.call_args.kwargs
        self.assertEqual(call["reason_code"], "numeric_input_normalized")
        self.assertEqual(call["provider_request_count"], 1)
        self.assertIn("32000 EUR annual", call["reviewer_notes"])

    def test_deferred_numeric_salary_validation_repairs_after_failed_navigation(self):
        review_queue = Mock()
        answer = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="32000 EUR annual",
            reason_code="exact_profile_fact",
            provider_request_count=0,
        ))
        namespace = load_runtime_functions(answer, review_queue)
        field = DeferredNumericSalaryInput()
        form_question = Question(
            "text", "¿Cuáles son tus expectativas económicas anuales?", field
        )
        modal = Modal([form_question])
        unresolved = set()
        namespace["answer_questions"](
            modal,
            set(),
            "Synthetic city",
            "Synthetic job",
            unresolved,
            "Synthetic description",
        )
        self.assertEqual(field.value, "32000 EUR annual")
        repaired = namespace["repair_invalid_required_fields"](
            modal,
            "Synthetic city",
            "Synthetic job",
            "Synthetic description",
            unresolved,
            set(),
        )
        self.assertTrue(repaired)
        self.assertEqual(field.value, "32000")
        self.assertEqual(field.sent_values, ["32000 EUR annual", "32000"])
        call = review_queue.record_answer.call_args.kwargs
        self.assertEqual(call["reason_code"], "numeric_input_normalized")
        self.assertEqual(call["validation_result"], "valid_after_repair")
        self.assertEqual(call["application_outcome"], "answer_filled")
        self.assertFalse(call["force_high_priority"])

    def test_free_text_salary_answer_is_not_stripped(self):
        answer = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="32000 EUR annual",
            reason_code="exact_profile_fact",
            provider_request_count=0,
        ))
        field = Input(attrs={"maxlength": "100", "aria-required": "true"})
        unresolved = self.answer(
            [Question("textarea", "Describe your salary expectations", field)],
            answer,
        )
        self.assertEqual(field.value, "32000 EUR annual")
        self.assertFalse(unresolved)

    def test_numeric_browser_validation_retries_once_then_continues(self):
        ai = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="EUR 15.38",
            reason_code="grounded_ai_answer",
            provider_request_count=1,
        ))
        field = ValidatingNumericInput(["invalid", ""])
        unresolved = self.answer(
            [Question("number", "Expected hourly rate", field)],
            ai,
        )
        self.assertEqual(field.sent_values, ["15.38", "15.38"])
        self.assertEqual(field.value, "15.38")
        self.assertFalse(unresolved)

    def test_unrecoverable_numeric_validation_is_recorded_and_unresolved(self):
        review_queue = Mock()
        ai = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="EUR 15.38",
            reason_code="grounded_ai_answer",
            provider_request_count=1,
        ))
        field = ValidatingNumericInput(["invalid", "still invalid"])
        unresolved = self.answer(
            [Question("number", "Expected hourly rate", field)],
            ai,
            review_queue,
        )
        self.assertTrue(unresolved)
        review_queue.record_required_event.assert_called_once()
        event = review_queue.record_required_event.call_args.kwargs
        self.assertEqual(event["reason_code"], "numeric_browser_validation_failed")
        self.assertEqual(event["validation_result"], "validation_failed")

    def test_invalid_text_numeric_scale_is_repaired_deterministically_first(self):
        provider = Mock(side_effect=AssertionError("Gemini must not be called"))
        review_queue = Mock()
        deterministic = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="3",
            original_answer="Conversational",
            reason_code="language_level_numeric_scale",
            provider_request_count=0,
        ))
        namespace = load_runtime_functions(
            provider,
            review_queue,
            verified_mock=deterministic,
        )
        field = NumericIntentTextInput("Conversational")
        unresolved = {f"number:{hash('What is your Spanish level? (1–5)')}"}
        signatures = set()
        repaired = namespace["repair_invalid_required_fields"](
            Modal([Question(
                "text", "What is your Spanish level? (1–5)", field
            )]),
            "Synthetic city",
            "Synthetic job",
            "Synthetic description",
            unresolved,
            signatures,
        )
        self.assertTrue(repaired)
        self.assertFalse(unresolved)
        self.assertEqual(field.value, "3")
        provider.assert_not_called()
        call = review_queue.record_answer.call_args.kwargs
        self.assertEqual(call["reason_code"], "language_level_numeric_scale")
        self.assertEqual(call["validation_result"], "valid")

    def test_repair_scans_only_invalid_required_fields_and_calls_single_field_ai(self):
        review_queue = Mock()
        deterministic = Mock(return_value=SimpleNamespace(
            can_answer=False,
            answer="",
            reason_code="exact_fact_unavailable",
            provider_request_count=0,
        ))
        provider = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="4",
            reason_code="grounded_ai_answer",
            provider_request_count=1,
        ))
        namespace = load_runtime_functions(
            provider,
            review_queue,
            verified_mock=deterministic,
        )
        valid = Input("already valid", {"type": "text", "aria-required": "true"})
        invalid = NumericIntentTextInput()
        repaired = namespace["repair_invalid_required_fields"](
            Modal([
                Question("text", "Valid motivation", valid),
                Question("text", "Unknown numeric rating (1-5)", invalid),
            ]),
            "Synthetic city",
            "Synthetic job",
            "Synthetic description",
            set(),
            set(),
        )
        self.assertTrue(repaired)
        self.assertEqual(valid.value, "already valid")
        self.assertEqual(invalid.value, "4")
        deterministic.assert_called_once()
        provider.assert_called_once()
        self.assertEqual(provider.call_args.args[0], "Unknown numeric rating (1-5)")
        self.assertEqual(provider.call_args.args[1], "number")
        call = review_queue.record_answer.call_args.kwargs
        self.assertEqual(call["reason_code"], "provider_invalid_field_repair")
        self.assertEqual(call["provider_request_count"], 1)

    def test_successful_advance_does_not_inspect_or_repair(self):
        namespace = load_runtime_functions(Mock())
        previous = Modal([Question(
            "text", "First page question", Input("filled")
        )])
        current = Modal([Question(
            "text", "Second page question", Input("filled")
        )])
        before_signature = namespace["_form_page_signature"](previous)
        inspect_invalid = Mock(side_effect=AssertionError(
            "Successful navigation must not inspect invalid fields"
        ))
        repair = Mock(side_effect=AssertionError(
            "Successful navigation must not trigger repair"
        ))
        namespace["_collect_invalid_required_fields"] = inspect_invalid
        namespace["repair_invalid_required_fields"] = repair

        result = namespace["_repair_after_failed_advance"](
            current,
            before_signature,
            "Synthetic city",
            "Synthetic job",
            "Synthetic description",
            set(),
            set(),
        )

        self.assertIsNone(result)
        inspect_invalid.assert_not_called()
        repair.assert_not_called()

    def test_failed_advance_triggers_invalid_field_inspection(self):
        namespace = load_runtime_functions(Mock())
        modal = Modal([Question(
            "text", "Unchanged page question", Input("invalid")
        )])
        before_signature = namespace["_form_page_signature"](modal)
        invalid_fields = [{"kind": "text", "label": "Unchanged page question"}]
        inspect_invalid = Mock(return_value=invalid_fields)
        repair = Mock(return_value=True)
        namespace["_collect_invalid_required_fields"] = inspect_invalid
        namespace["repair_invalid_required_fields"] = repair

        result = namespace["_repair_after_failed_advance"](
            modal,
            before_signature,
            "Synthetic city",
            "Synthetic job",
            "Synthetic description",
            set(),
            set(),
        )

        self.assertTrue(result)
        inspect_invalid.assert_called_once_with(modal)
        self.assertIs(repair.call_args.args[-1], invalid_fields)

    def test_linkedin_validation_message_is_collected_with_field_context(self):
        namespace = load_runtime_functions(Mock())
        control = Input("bad value", {"type": "text"})
        fields = namespace["_collect_invalid_required_fields"](Modal([
            Question(
                "text",
                "Validated question",
                control,
                required=False,
                validation_message="Enter a valid value",
            )
        ]))

        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0]["kind"], "text")
        self.assertEqual(fields[0]["label"], "Validated question")
        self.assertEqual(fields[0]["current"], "bad value")
        self.assertEqual(fields[0]["options"], [])
        self.assertEqual(
            fields[0]["validation_message"], "Enter a valid value"
        )

    def test_required_select_and_radio_are_repaired_with_original_operations(self):
        provider = Mock(side_effect=AssertionError(
            "Known corrected options must not call Gemini"
        ))
        deterministic = Mock(side_effect=lambda label, kind, _options, _constraints: SimpleNamespace(
            can_answer=True,
            answer="Second",
            reason_code="exact_profile_fact",
            provider_request_count=0,
        ))
        namespace = load_runtime_functions(
            provider, verified_mock=deterministic
        )
        select = SelectControl(
            ["Select an option", "First", "Second"],
            "Select an option",
            {"aria-required": "true"},
        )
        radio = RadioControl(
            "Required radio", ["First", "Second"], {"aria-required": "true"}
        )
        unresolved = {
            f"select:{hash('Required select')}",
            f"radio:{hash('Required radio')}",
        }

        repaired = namespace["repair_invalid_required_fields"](
            Modal([
                Question("select", "Required select", select),
                Question("radio", "Required radio", radio),
            ]),
            "Synthetic city",
            "Synthetic job",
            "Synthetic description",
            unresolved,
            set(),
        )

        self.assertTrue(repaired)
        self.assertEqual(select.selected, "Second")
        self.assertTrue(radio.options[1].selected)
        self.assertFalse(unresolved)
        provider.assert_not_called()

    def test_failed_repair_is_high_priority_and_page_cannot_loop(self):
        review_queue = Mock()
        deterministic = Mock(return_value=SimpleNamespace(
            can_answer=False,
            answer="",
            reason_code="exact_fact_unavailable",
            provider_request_count=0,
        ))
        provider = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="2",
            reason_code="grounded_ai_answer",
            provider_request_count=1,
        ))
        namespace = load_runtime_functions(
            provider,
            review_queue,
            verified_mock=deterministic,
        )
        field = NumericIntentTextInput(always_invalid=True)
        modal = Modal([Question("text", "Numeric level (1-5)", field)])
        unresolved = set()
        signatures = set()
        first = namespace["repair_invalid_required_fields"](
            modal,
            "Synthetic city",
            "Synthetic job",
            "Synthetic description",
            unresolved,
            signatures,
        )
        second = namespace["repair_invalid_required_fields"](
            modal,
            "Synthetic city",
            "Synthetic job",
            "Synthetic description",
            unresolved,
            signatures,
        )
        self.assertFalse(first)
        self.assertFalse(second)
        provider.assert_called_once()
        self.assertEqual(field.sent_values, ["2", "2"])
        call = review_queue.record_answer.call_args.kwargs
        self.assertEqual(call["reason_code"], "invalid_field_repair_failed")
        self.assertTrue(call["force_high_priority"])
        self.assertEqual(call["validation_result"], "validation_failed")

    def test_experience_policy_answers_with_zero_requests_are_recorded(self):
        review_queue = Mock()
        floor = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="1",
            original_answer="0",
            reason_code="experience_years_minimum_floor",
            provider_request_count=0,
        ))
        field = Input(attrs={"type": "number", "aria-required": "true"})
        self.answer(
            [Question("number", "Years of experience with Data Governance", field)],
            floor,
            review_queue,
        )
        self.assertEqual(field.value, "1")
        call = review_queue.record_answer.call_args.kwargs
        self.assertTrue(call["record_without_provider"])
        self.assertTrue(call["force_high_priority"])
        self.assertIn("original_proposed_answer=0", call["reviewer_notes"])

        review_queue.reset_mock()
        assertive = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="Yes",
            reason_code="ordinary_experience_yes_default",
            provider_request_count=0,
        ))
        radio = RadioControl("Unknown experience", ["Yes", "No"])
        self.answer(
            [Question("radio", "Do you have experience with Data Governance?", radio)],
            assertive,
            review_queue,
        )
        self.assertTrue(radio.options[0].selected)
        call = review_queue.record_answer.call_args.kwargs
        self.assertTrue(call["record_without_provider"])
        self.assertFalse(call["force_high_priority"])

    def test_analyst_role_floor_is_filled_and_recorded_without_provider(self):
        review_queue = Mock()
        floor = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="3",
            original_answer="1",
            reason_code="analyst_role_years_minimum_floor",
            provider_request_count=0,
        ))
        field = Input(attrs={"type": "number", "aria-required": "true"})
        self.answer(
            [Question(
                "number",
                "How many years of experience do you have as a Business Analyst?",
                field,
            )],
            floor,
            review_queue,
        )
        self.assertEqual(field.value, "3")
        call = review_queue.record_answer.call_args.kwargs
        self.assertEqual(
            call["reason_code"], "analyst_role_years_minimum_floor"
        )
        self.assertEqual(call["provider_request_count"], 0)
        self.assertTrue(call["record_without_provider"])

    def test_preserved_one_year_business_analyst_answer_is_raised_to_three(self):
        review_queue = Mock()
        verified = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="3",
            original_answer="1",
            reason_code="analyst_role_years_minimum_floor",
            provider_request_count=0,
        ))
        field = Input("1", {"type": "number", "aria-required": "true"})
        self.answer(
            [Question(
                "number",
                "How many years of Procurement-focused Business Analyst experience do you have?",
                field,
            )],
            Mock(side_effect=AssertionError("Gemini must not be called")),
            review_queue,
            verified,
        )
        self.assertEqual(field.value, "3")
        call = review_queue.record_answer.call_args.kwargs
        self.assertEqual(
            call["reason_code"], "analyst_role_years_minimum_floor"
        )
        self.assertEqual(call["provider_request_count"], 0)

    def test_spanish_level_and_internal_english_yes_no_route_to_profile_helper(self):
        spanish = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="Conversación",
            reason_code="exact_profile_fact",
            provider_request_count=0,
        ))
        level = SelectControl(
            ["Selecciona una opción", "Conversación", "Profesional"],
            "Selecciona una opción",
        )
        self.answer(
            [Question("select", "Spanish proficiency level", level)],
            spanish,
        )
        self.assertEqual(level.selected, "Conversación")
        spanish.assert_called_once()

        capability = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="Yes",
            reason_code="exact_profile_fact",
            provider_request_count=0,
        ))
        radio = RadioControl(
            "Power BI and advanced Excel",
            ["Yes", "No"],
        )
        self.answer(
            [Question(
                "radio",
                "¿Tienes dominio de Power BI y Excel avanzado? Sí / No",
                radio,
            )],
            capability,
        )
        self.assertTrue(radio.options[0].selected)
        capability.assert_called_once()

    def test_stale_language_values_are_narrowly_overridden(self):
        cases = (
            (
                "Catalan proficiency level",
                ["None", "Professional", "Native or bilingual"],
                "Native or bilingual",
                "None",
            ),
            (
                "Spanish proficiency level",
                ["Basic", "Conversational", "Professional"],
                "Professional",
                "Conversational",
            ),
        )
        for question, options, selected, expected in cases:
            with self.subTest(question=question):
                ai = Mock(side_effect=AssertionError("Gemini must not be called"))
                review_queue = Mock()
                verified = Mock(return_value=SimpleNamespace(
                    can_answer=True,
                    answer=expected,
                    reason_code="exact_profile_fact",
                    provider_request_count=0,
                ))
                field = SelectControl(options, selected)
                unresolved = self.answer(
                    [Question("select", question, field)],
                    ai,
                    review_queue,
                    verified,
                )
                self.assertEqual(field.selected, expected)
                self.assertFalse(unresolved)
                ai.assert_not_called()
                call = review_queue.record_answer.call_args.kwargs
                self.assertEqual(
                    call["reason_code"], "stale_preserved_value_overridden"
                )
                self.assertIn(selected, call["reviewer_notes"])
                self.assertFalse(call["force_high_priority"])

    def test_saved_ordinary_experience_answer_has_first_priority(self):
        provider = Mock(side_effect=AssertionError("Gemini must not be called"))
        verified = Mock(side_effect=AssertionError(
            "Saved ordinary experience answer must have first priority"
        ))
        deterministic = Mock(side_effect=AssertionError(
            "Yes default must not replace a saved answer"
        ))
        review_queue = Mock()
        question = "Do you have experience with an unfamiliar platform?"
        field = RadioControl(question, ["Yes", "No"])
        field.options[1].selected = True

        self.answer(
            [Question("radio", question, field)],
            provider,
            review_queue,
            verified,
            deterministic,
        )

        self.assertTrue(field.options[1].selected)
        self.assertFalse(field.options[0].selected)
        provider.assert_not_called()
        verified.assert_not_called()
        deterministic.assert_not_called()
        review_queue.record_answer.assert_not_called()

    def test_exact_threshold_or_negative_no_is_not_overridden(self):
        for reason in ("exact_experience_threshold_fact", "exact_profile_fact"):
            with self.subTest(reason=reason):
                verified = Mock(return_value=SimpleNamespace(
                    can_answer=True,
                    answer="No",
                    reason_code=reason,
                    provider_request_count=0,
                ))
                deterministic = Mock(side_effect=AssertionError(
                    "Assertive fallback must not replace an exact No"
                ))
                field = RadioControl("Do you have at least 6 years of SQL experience?", ["Yes", "No"])
                field.options[1].selected = True
                self.answer(
                    [Question("radio", "Do you have at least 6 years of SQL experience?", field)],
                    Mock(),
                    Mock(),
                    verified,
                    deterministic,
                )
                self.assertTrue(field.options[1].selected)
                deterministic.assert_not_called()

    def test_correct_preserved_language_value_is_unchanged(self):
        ai = Mock(side_effect=AssertionError("Gemini must not be called"))
        review_queue = Mock()
        verified = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="Conversational",
            reason_code="exact_profile_fact",
            provider_request_count=0,
        ))
        field = SelectControl(
            ["Basic", "Conversational", "Professional"], "Conversational"
        )
        unresolved = self.answer(
            [Question("select", "Spanish proficiency level", field)],
            ai,
            review_queue,
            verified,
        )
        self.assertEqual(field.selected, "Conversational")
        self.assertFalse(unresolved)
        review_queue.record_answer.assert_not_called()

    def test_french_language_placeholder_uses_localized_exact_mapping(self):
        localized = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="Natif ou bilingue",
            original_answer="Synthetic verified level",
            reason_code="localized_language_exact_fact",
            provider_request_count=0,
        ))
        review_queue = Mock()
        field = SelectControl(
            [
                "Sélectionnez une option",
                "Inexistant",
                "Intermédiaire",
                "Courant",
                "Natif ou bilingue",
            ],
            "Sélectionnez une option",
            {"aria-required": "true"},
        )
        unresolved = self.answer(
            [Question("select", "Quel est votre niveau en Anglais ?", field)],
            localized,
            review_queue,
        )
        self.assertEqual(field.selected, "Natif ou bilingue")
        self.assertFalse(unresolved)
        call = review_queue.record_answer.call_args.kwargs
        self.assertEqual(call["reason_code"], "localized_language_exact_fact")
        self.assertEqual(call["provider_request_count"], 0)
        self.assertTrue(call["record_without_provider"])

    def test_valid_preserved_french_level_remains_unchanged(self):
        ai = Mock(side_effect=AssertionError("Gemini must not be called"))
        review_queue = Mock()
        verified = Mock(return_value=SimpleNamespace(
            can_answer=False,
            answer="",
            reason_code="exact_fact_unavailable",
            provider_request_count=0,
        ))
        field = SelectControl(
            ["Sélectionnez une option", "Inexistant", "Courant"],
            "Inexistant",
            {"aria-required": "true"},
        )
        unresolved = self.answer(
            [Question("select", "Quel est votre niveau en Français ?", field)],
            ai,
            review_queue,
            verified,
        )
        self.assertEqual(field.selected, "Inexistant")
        self.assertFalse(unresolved)
        ai.assert_not_called()
        review_queue.record_answer.assert_not_called()

    def test_french_placeholder_is_invalid_and_repaired_after_failed_navigation(self):
        localized = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="Natif ou bilingue",
            reason_code="localized_language_exact_fact",
            provider_request_count=0,
        ))
        review_queue = Mock()
        namespace = load_runtime_functions(
            Mock(side_effect=AssertionError("Gemini must not be called")),
            review_queue,
            verified_mock=localized,
        )
        field = SelectControl(
            ["Sélectionnez une option", "Courant", "Natif ou bilingue"],
            "Sélectionnez une option",
            {"aria-required": "true"},
        )
        modal = Modal([
            Question("select", "Quel est votre niveau en Anglais ?", field)
        ])
        unresolved = {f"select:{hash('Quel est votre niveau en Anglais ?')}"}
        self.assertTrue(
            namespace["_is_select_placeholder"]("Sélectionnez une option")
        )
        repaired = namespace["repair_invalid_required_fields"](
            modal,
            "Synthetic city",
            "Synthetic job",
            "Synthetic description",
            unresolved,
            set(),
        )
        self.assertTrue(repaired)
        self.assertFalse(unresolved)
        self.assertEqual(field.selected, "Natif ou bilingue")
        call = review_queue.record_answer.call_args.kwargs
        self.assertEqual(call["reason_code"], "localized_language_exact_fact")
        self.assertEqual(call["validation_result"], "valid")

    def test_dom_placeholder_evidence_overrides_nonempty_selected_text(self):
        namespace = load_runtime_functions(Mock())
        for attrs in (
            {"data-placeholder": "true", "value": "continue"},
            {"disabled": "true", "value": "continue"},
            {"class": "artdeco-placeholder", "value": "continue"},
            {"value": ""},
        ):
            with self.subTest(attrs=attrs):
                field = SelectControl(
                    ["Continue", "High"],
                    "Continue",
                    {"aria-required": "true"},
                    {"Continue": attrs},
                )
                self.assertTrue(
                    namespace["_is_select_placeholder"]("Continue", field)
                )

    def test_unfamiliar_language_provider_mapping_is_filled_and_logged(self):
        provider = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="Zaawansowany",
            target_language="english",
            reason_code="multilingual_language_provider_mapping",
            provider_request_count=1,
        ))
        review_queue = Mock()
        field = SelectControl(
            ["Wybierz opcję", "Podstawowy", "Zaawansowany"],
            "Wybierz opcję",
            {"aria-required": "true"},
        )
        unresolved = self.answer(
            [Question(
                "select",
                "Jaki jest Twój poziom języka angielskiego?",
                field,
            )],
            provider,
            review_queue,
        )
        self.assertEqual(field.selected, "Zaawansowany")
        self.assertFalse(unresolved)
        call = review_queue.record_answer.call_args.kwargs
        self.assertEqual(
            call["reason_code"], "multilingual_language_provider_mapping"
        )
        self.assertEqual(call["provider_request_count"], 1)
        self.assertIn("target_language=english", call["reviewer_notes"])

    def test_failed_multilingual_mapping_is_unresolved_and_logged(self):
        provider = Mock(return_value=SimpleNamespace(
            can_answer=False,
            answer="",
            target_language="german",
            reason_code="multilingual_language_mapping_failed",
            provider_request_count=2,
        ))
        review_queue = Mock()
        field = SelectControl(
            ["Wybierz opcję", "Podstawowy", "Zaawansowany"],
            "Wybierz opcję",
            {"aria-required": "true"},
        )
        unresolved = self.answer(
            [Question(
                "select",
                "Wie gut sind Ihre Deutschkenntnisse?",
                field,
            )],
            provider,
            review_queue,
        )
        self.assertTrue(unresolved)
        self.assertEqual(field.selected, "Wybierz opcję")
        call = review_queue.record_answer.call_args.kwargs
        self.assertEqual(
            call["reason_code"], "multilingual_language_mapping_failed"
        )
        self.assertEqual(call["application_outcome"], "unresolved_required")
        self.assertEqual(call["validation_result"], "validation_failed")

    def test_catalan_without_safe_visible_option_is_unresolved(self):
        ai = Mock(side_effect=AssertionError("Gemini must not be called"))
        review_queue = Mock()
        verified = Mock(return_value=SimpleNamespace(
            can_answer=False,
            answer="",
            reason_code="exact_option_unavailable",
            provider_request_count=0,
        ))
        field = SelectControl(
            ["Professional", "Native or bilingual"], "Native or bilingual"
        )
        unresolved = self.answer(
            [Question("select", "Catalan proficiency level", field)],
            ai,
            review_queue,
            verified,
        )
        self.assertTrue(unresolved)
        self.assertEqual(field.selected, "Native or bilingual")
        ai.assert_not_called()
        event = review_queue.record_required_event.call_args.kwargs
        self.assertEqual(event["reason_code"], "exact_option_unavailable")

    def test_blank_catalan_select_never_uses_generic_proficiency(self):
        ai = Mock(return_value=SimpleNamespace(
            can_answer=False,
            answer="",
            reason_code="exact_option_unavailable",
            provider_request_count=0,
        ))
        field = SelectControl(
            ["Select an option", "Professional", "Native or bilingual"],
            "Select an option",
        )
        unresolved = self.answer(
            [Question("select", "Catalan proficiency level", field)], ai
        )
        self.assertTrue(unresolved)
        self.assertEqual(field.selected, "Select an option")
        ai.assert_called_once()

    def test_other_conflicting_verified_facts_override_preserved_values(self):
        cases = (
            ("Expected annual salary", "60000", "32000"),
            ("How many years of experience do you have with SQL?", "2", "5"),
        )
        for question, current, expected in cases:
            with self.subTest(question=question):
                verified = Mock(return_value=SimpleNamespace(
                    can_answer=True,
                    answer=expected,
                    reason_code="exact_profile_fact",
                    provider_request_count=0,
                ))
                field = Input(current, {"type": "text", "aria-required": "true"})
                self.answer(
                    [Question("text", question, field)],
                    Mock(side_effect=AssertionError("Gemini must not be called")),
                    Mock(),
                    verified,
                )
                self.assertEqual(field.value, expected)

        for question, current, expected in (
            ("Are you legally authorized to work?", "No", "Yes"),
            ("Will you require sponsorship?", "Yes", "No"),
        ):
            with self.subTest(question=question):
                verified = Mock(return_value=SimpleNamespace(
                    can_answer=True,
                    answer=expected,
                    reason_code="exact_profile_fact",
                    provider_request_count=0,
                ))
                field = RadioControl(question, ["Yes", "No"])
                field.options[["Yes", "No"].index(current)].selected = True
                self.answer(
                    [Question("radio", question, field)],
                    Mock(side_effect=AssertionError("Gemini must not be called")),
                    Mock(),
                    verified,
                )
                selected = next(
                    option.label.text for option in field.options if option.selected
                )
                self.assertEqual(selected, expected)

    def test_text_language_scales_submit_plain_digits(self):
        cases = (
            ("What is your English level? (1–5)", "5", "Professional"),
            ("What is your Spanish level? (1-5)", "3", "Conversational"),
            ("What is your Catalan level? 1 a 5", "1", "None"),
        )
        for question, expected, original in cases:
            with self.subTest(question=question):
                review_queue = Mock()
                ai = Mock(return_value=SimpleNamespace(
                    can_answer=True,
                    answer=expected,
                    original_answer=original,
                    reason_code="language_level_numeric_scale",
                    provider_request_count=0,
                ))
                field = NumericIntentTextInput()
                unresolved = self.answer(
                    [Question("text", question, field)], ai, review_queue
                )
                self.assertEqual(field.value, expected)
                self.assertEqual(field.sent_values, [expected])
                self.assertFalse(unresolved)
                call = review_queue.record_answer.call_args.kwargs
                self.assertEqual(call["reason_code"], "language_level_numeric_scale")
                self.assertIn(original, call["reviewer_notes"])
                self.assertFalse(call["force_high_priority"])

    def test_resume_attachment_confirmation_is_localized_and_provider_free(self):
        cases = (
            (
                "Por favor, adjunta tu C.V.",
                ["Selecciona una opción", "Sí", "No"],
                "Sí",
            ),
            (
                "Por favor, adjunta tu C.V.",
                ["Select an option", "Yes", "No"],
                "Yes",
            ),
            (
                "Please attach your resume",
                ["Select an option", "Yes", "No"],
                "Yes",
            ),
        )
        for question, options, expected in cases:
            with self.subTest(question=question, options=options):
                provider = Mock(side_effect=AssertionError(
                    "Gemini must not be called for resume confirmation"
                ))
                review_queue = Mock()
                field = SelectControl(options, options[0])
                form_question = Question("select", question, field)
                modal = ResumeModal(
                    [form_question],
                    selected_cards=[ClickableButton(displayed=True)],
                )
                unresolved = self.answer(
                    [form_question],
                    provider,
                    review_queue,
                    modal=modal,
                )
                self.assertEqual(field.selected, expected)
                self.assertFalse(unresolved)
                provider.assert_not_called()
                call = review_queue.record_answer.call_args.kwargs
                self.assertEqual(call["reason_code"], "resume_attachment_confirmed")
                self.assertEqual(call["provider_request_count"], 0)
                self.assertEqual(call["application_outcome"], "answer_filled")
                self.assertFalse(call["force_high_priority"])

    def test_resume_selection_detects_active_card_radio_and_upload_state(self):
        selected = Input()
        selected.selected = True
        namespace = load_runtime_functions(Mock())
        self.assertTrue(namespace["_resume_selected_in_modal"](
            ResumeModal([], selected_cards=[ClickableButton(displayed=True)])
        ))
        self.assertTrue(namespace["_resume_selected_in_modal"](
            ResumeModal([], resume_radios=[selected])
        ))
        self.assertTrue(namespace["_resume_selected_in_modal"](
            ResumeModal([], uploaded_elements=[ClickableButton(displayed=True)])
        ))

    def test_unconfirmed_resume_stays_unresolved_without_provider(self):
        provider = Mock(side_effect=AssertionError(
            "Gemini must not be called when resume state is unconfirmed"
        ))
        review_queue = Mock()
        options = ["Selecciona una opción", "Sí", "No"]
        field = SelectControl(options, options[0])
        form_question = Question(
            "select", "Por favor, adjunta tu C.V.", field
        )
        modal = ResumeModal([form_question])
        unresolved = self.answer(
            [form_question], provider, review_queue, modal=modal
        )
        self.assertTrue(unresolved)
        self.assertEqual(field.selected, options[0])
        provider.assert_not_called()
        event = review_queue.record_required_event.call_args.kwargs
        self.assertEqual(
            event["reason_code"], "resume_attachment_not_confirmed"
        )
        self.assertEqual(event["application_outcome"], "unresolved_required")

    def test_unconfirmed_resume_repair_pass_never_calls_provider(self):
        provider = Mock(side_effect=AssertionError(
            "Repair must not infer resume attachment"
        ))
        deterministic = Mock(side_effect=AssertionError(
            "Resume attachment must use current-modal UI evidence only"
        ))
        namespace = load_runtime_functions(
            provider,
            deterministic_mock=deterministic,
        )
        options = ["Select an option", "Yes", "No"]
        field = SelectControl(options, options[0])
        form_question = Question(
            "select", "Please attach your resume", field
        )
        unresolved = {f"select:{hash('Please attach your resume')}"}
        repaired = namespace["repair_invalid_required_fields"](
            ResumeModal([form_question]),
            "Synthetic city",
            "Synthetic job",
            "Synthetic description",
            unresolved,
            set(),
        )
        self.assertFalse(repaired)
        self.assertTrue(unresolved)
        provider.assert_not_called()
        deterministic.assert_not_called()

    def test_resume_rule_does_not_answer_unrelated_document_upload(self):
        provider = Mock(return_value=SimpleNamespace(
            can_answer=False,
            answer="",
            reason_code="verified_context_unavailable",
            provider_request_count=0,
        ))
        options = ["Select an option", "Yes", "No"]
        field = SelectControl(options, options[0])
        form_question = Question(
            "select", "Please attach your portfolio document", field
        )
        unresolved = self.answer(
            [form_question],
            provider,
            modal=ResumeModal(
                [form_question],
                selected_cards=[ClickableButton(displayed=True)],
            ),
        )
        self.assertTrue(unresolved)
        self.assertEqual(field.selected, options[0])
        provider.assert_called_once()

    def test_unrelated_number_in_free_text_is_not_numeric_intent(self):
        numeric_intent = load_runtime_functions(Mock())["_numeric_intent_from_question"]
        self.assertFalse(numeric_intent("Describe the last 2 projects you coordinated"))
        self.assertTrue(numeric_intent("Rate your level on a scale of 1 to 5"))

    def test_mapper_engine_assertive_yes_is_selected_and_queued(self):
        for question, options, answer in (
            ("Have you used Mapper Engine?", ["Yes", "No"], "Yes"),
            ("¿Has utilizado Mapper Engine?", ["Yes", "No"], "Yes"),
            ("¿Has trabajado con X?", ["Sí", "No"], "Sí"),
            ("¿Tienes conocimientos de X?", ["Yes", "No"], "Yes"),
        ):
            with self.subTest(question=question):
                review_queue = Mock()
                ai = Mock(return_value=SimpleNamespace(
                    can_answer=True,
                    answer=answer,
                    reason_code="ordinary_experience_yes_default",
                    provider_request_count=0,
                ))
                radio = RadioControl(question, options)
                self.answer(
                    [Question("radio", question, radio)],
                    ai,
                    review_queue,
                )
                self.assertTrue(radio.options[options.index(answer)].selected)
                call = review_queue.record_answer.call_args.kwargs
                self.assertEqual(
                    call["reason_code"],
                    "ordinary_experience_yes_default",
                )
                self.assertTrue(call["record_without_provider"])

    def test_exact_profile_answer_with_zero_requests_is_not_recorded(self):
        review_queue = Mock()
        for question, answer in (
            ("Years with Microsoft Excel?", "7"),
            ("Years with Python?", "4"),
            ("Years with SQL?", "5"),
            ("Years with Azure SQL?", "4"),
        ):
            with self.subTest(question=question):
                ai = Mock(return_value=SimpleNamespace(
                    can_answer=True,
                    answer=answer,
                    reason_code="exact_skill_years",
                    provider_request_count=0,
                ))
                field = Input(attrs={"type": "number", "aria-required": "true"})
                self.answer([Question("number", question, field)], ai, review_queue)
                self.assertEqual(field.value, answer)
        review_queue.record_answer.assert_not_called()

    def test_required_validation_failure_is_recorded_high_level_event(self):
        review_queue = Mock()
        ai = Mock(return_value=SimpleNamespace(
            can_answer=False,
            answer="",
            reason_code="invalid_number",
            provider_request_count=1,
        ))
        field = Input(attrs={"type": "number", "aria-required": "true"})
        unresolved = self.answer(
            [Question("number", "Day rate greater than zero", field)],
            ai,
            review_queue,
        )
        self.assertTrue(unresolved)
        review_queue.record_answer.assert_called_once()
        call = review_queue.record_answer.call_args.kwargs
        self.assertEqual(call["validation_result"], "validation_failed")
        self.assertEqual(call["application_outcome"], "unresolved_required")

    def test_required_unresolved_without_provider_is_recorded(self):
        review_queue = Mock()
        ai = Mock(return_value=SimpleNamespace(
            can_answer=False,
            answer="",
            reason_code="verified_context_unavailable",
            provider_request_count=0,
        ))
        field = SelectControl(["Select an option"], "Select an option")
        unresolved = self.answer(
            [Question("select", "Freelancer availability", field)],
            ai,
            review_queue,
        )
        self.assertTrue(unresolved)
        review_queue.record_answer.assert_not_called()
        review_queue.record_required_event.assert_called_once()

    def test_review_logger_failure_does_not_change_filled_answer(self):
        review_queue = Mock()
        review_queue.record_answer.side_effect = OSError("synthetic logger failure")
        ai = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="Supported answer",
            reason_code="grounded_ai_answer",
            provider_request_count=1,
        ))
        field = Input(attrs={"type": "text", "aria-required": "true"})
        unresolved = self.answer(
            [Question("text", "Ordinary unmatched question", field)],
            ai,
            review_queue,
        )
        self.assertEqual(field.value, "Supported answer")
        self.assertFalse(unresolved)

    def test_unknown_number_uses_gemini_not_generic_years(self):
        ai = Mock(return_value=SimpleNamespace(can_answer=True, answer="4", reason_code="grounded_ai_answer"))
        field = Input(attrs={"type": "number", "aria-required": "true"})
        unresolved = self.answer([Question("number", "Direct reports managed", field)], ai)
        self.assertEqual(field.value, "4")
        self.assertNotEqual(field.value, "7")
        self.assertFalse(unresolved)

    def test_unknown_select_uses_exact_gemini_option(self):
        ai = Mock(return_value=SimpleNamespace(can_answer=True, answer="Second", reason_code="grounded_ai_answer"))
        field = SelectControl(["Select an option", "First", "Second"], "Select an option")
        self.answer([Question("select", "Preferred working style", field)], ai)
        self.assertEqual(field.selected, "Second")

    def test_unknown_radio_does_not_use_first_option_or_authorization(self):
        ai = Mock(return_value=SimpleNamespace(can_answer=True, answer="Second", reason_code="grounded_ai_answer"))
        field = RadioControl("Preferred working style", ["First", "Second"])
        self.answer([Question("radio", "Preferred working style", field)], ai)
        self.assertFalse(field.options[0].selected)
        self.assertTrue(field.options[1].selected)
        ai.assert_called_once()

    def test_protected_exact_fact_uses_local_answer_without_gemini(self):
        provider = Mock(side_effect=AssertionError(
            "Protected exact facts must never call Gemini"
        ))
        exact = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="No",
            reason_code="exact_profile_fact",
            provider_request_count=0,
        ))
        field = RadioControl("EU citizenship", ["Yes", "No"])

        self.answer(
            [Question("radio", "EU citizenship", field)],
            provider,
            deterministic_mock=exact,
        )

        self.assertTrue(field.options[1].selected)
        exact.assert_called_once()
        provider.assert_not_called()

    def test_authorization_radio_uses_profile_helper_before_stale_config(self):
        ai = Mock(return_value=SimpleNamespace(can_answer=True, answer="Yes", reason_code="exact_profile_fact"))
        field = RadioControl("Employment eligibility", ["Yes", "No"])
        self.answer([Question("radio", "Employment eligibility", field)], ai)
        self.assertTrue(field.options[0].selected)
        ai.assert_called_once()

    def test_authorization_paraphrases_route_to_semantic_gemini(self):
        for question in (
            "Do you have the right to work in this country?",
            "¿Tienes permiso para trabajar en este país?",
        ):
            with self.subTest(question=question):
                ai = Mock(return_value=SimpleNamespace(can_answer=True, answer="Yes", reason_code="semantic_confirmed_fact"))
                field = RadioControl(question, ["Yes", "No"])
                self.answer([Question("radio", question, field)], ai)
                self.assertTrue(field.options[0].selected)
                ai.assert_called_once()

    def test_sponsorship_paraphrases_route_to_semantic_gemini(self):
        for question in (
            "Will you need employer support for immigration now or later?",
            "¿Necesitarás apoyo de la empresa para poder trabajar ahora o en el futuro?",
        ):
            with self.subTest(question=question):
                ai = Mock(return_value=SimpleNamespace(can_answer=True, answer="No", reason_code="semantic_confirmed_fact"))
                field = RadioControl(question, ["Yes", "No"])
                self.answer([Question("radio", question, field)], ai)
                self.assertTrue(field.options[1].selected)
                ai.assert_called_once()

    def test_salary_availability_and_language_paraphrases_route_to_gemini(self):
        text_cases = (
            ("¿Qué remuneración anual buscas?", "32000"),
            ("When would you be able to join?", "Synthetic availability"),
        )
        for question, answer in text_cases:
            with self.subTest(question=question):
                ai = Mock(return_value=SimpleNamespace(can_answer=True, answer=answer, reason_code="semantic_confirmed_fact"))
                field = Input(attrs={"type": "text", "aria-required": "true"})
                self.answer([Question("text", question, field)], ai)
                self.assertEqual(field.value, answer)
                ai.assert_called_once()
        ai = Mock(return_value=SimpleNamespace(can_answer=True, answer="Professional", reason_code="semantic_confirmed_fact"))
        field = SelectControl(["Select an option", "Basic", "Professional"], "Select an option")
        self.answer([Question("select", "What is your English fluency?", field)], ai)
        self.assertEqual(field.selected, "Professional")
        ai.assert_called_once()

    def test_confirmed_capabilities_route_to_profile_helper(self):
        for question in (
            "Do you have cross-functional experience?",
            "Do you have process improvement experience?",
            "Do you have project coordination experience?",
        ):
            with self.subTest(question=question):
                ai = Mock(return_value=SimpleNamespace(
                    can_answer=True,
                    answer="Yes",
                    reason_code="exact_profile_fact",
                ))
                field = RadioControl(question, ["Yes", "No"])
                self.answer([Question("radio", question, field)], ai)
                self.assertTrue(field.options[0].selected)
                ai.assert_called_once()

    def test_unknown_boolean_is_not_blanket_yes_or_no(self):
        ai = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="No",
            reason_code="grounded_ai_answer",
        ))
        field = SelectControl(["Select an option", "Yes", "No"], "Select an option")
        self.answer(
            [Question("select", "Have you led a regulated manufacturing audit?", field)],
            ai,
        )
        self.assertEqual(field.selected, "No")
        ai.assert_called_once()

    def test_unknown_required_textarea_is_filled(self):
        ai = Mock(return_value=SimpleNamespace(can_answer=True, answer="Grounded response", reason_code="grounded_ai_answer"))
        field = Input(attrs={"maxlength": "30", "aria-required": "true"})
        unresolved = self.answer([Question("textarea", "Describe your approach", field)], ai)
        self.assertEqual(field.value, "Grounded response")
        self.assertFalse(unresolved)

    def test_invalid_required_answer_marks_application_unresolved(self):
        ai = Mock(return_value=SimpleNamespace(can_answer=False, answer="", reason_code="invalid_option"))
        field = SelectControl(["Select an option", "First"], "Select an option")
        unresolved = self.answer([Question("select", "Unmatched required choice", field)], ai)
        self.assertTrue(unresolved)
        self.assertEqual(field.selected, "Select an option")

    def test_eu_citizenship_without_exact_fact_stays_unresolved(self):
        ai = Mock(return_value=SimpleNamespace(
            can_answer=False,
            answer="",
            reason_code="high_risk_exact_fact_missing",
            provider_request_count=0,
        ))
        review_queue = Mock()
        field = RadioControl(
            "Do you hold a European Citizenship?", ["Yes", "No"]
        )
        unresolved = self.answer(
            [Question(
                "radio",
                "Do you hold a European Citizenship?",
                field,
            )],
            ai,
            review_queue,
        )
        self.assertTrue(unresolved)
        self.assertFalse(any(option.selected for option in field.options))
        ai.assert_called_once()
        event = review_queue.record_required_event.call_args.kwargs
        self.assertEqual(
            event["reason_code"], "high_risk_exact_fact_missing"
        )

    def test_verified_eu_citizenship_no_is_filled_and_reviewed_locally(self):
        local_exact = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="No",
            reason_code="exact_profile_fact",
            provider_request_count=0,
        ))
        review_queue = Mock()
        field = RadioControl(
            "Do you hold European citizenship?", ["Yes", "No"]
        )
        unresolved = self.answer(
            [Question(
                "radio",
                "Do you hold European citizenship?",
                field,
            )],
            local_exact,
            review_queue,
        )
        self.assertFalse(unresolved)
        selected = next(
            option.label.text for option in field.options if option.selected
        )
        self.assertEqual(selected, "No")
        review_queue.record_answer.assert_called_once()
        event = review_queue.record_answer.call_args.kwargs
        self.assertEqual(event["reason_code"], "exact_profile_fact")
        self.assertEqual(event["provider_request_count"], 0)
        self.assertTrue(event["record_without_provider"])
        self.assertTrue(event["force_normal_priority"])

    def test_verified_citizenship_overrides_stale_yes_as_exact_fact(self):
        verified = Mock(return_value=SimpleNamespace(
            can_answer=True,
            answer="No",
            reason_code="exact_profile_fact",
            provider_request_count=0,
        ))
        review_queue = Mock()
        field = RadioControl(
            "Are you an EU citizen?", ["Yes", "No"]
        )
        field.options[0].selected = True
        unresolved = self.answer(
            [Question("radio", "Are you an EU citizen?", field)],
            Mock(side_effect=AssertionError("Provider fallback must not run")),
            review_queue,
            verified,
        )
        self.assertFalse(unresolved)
        selected = next(
            option.label.text for option in field.options if option.selected
        )
        self.assertEqual(selected, "No")
        event = review_queue.record_answer.call_args.kwargs
        self.assertEqual(event["reason_code"], "exact_profile_fact")
        self.assertEqual(event["provider_request_count"], 0)
        self.assertTrue(event["force_normal_priority"])

    def test_optional_checkbox_is_left_unchecked(self):
        ai = Mock()
        field = Input()
        self.answer([Question("checkbox", "Marketing updates", field, required=False)], ai)
        self.assertFalse(field.selected)

    def test_job_search_safety_reminder_uses_only_modal_close(self):
        namespace = load_runtime_functions(Mock())
        close_button = ClickableButton(attrs={"aria-label": "Dismiss"})
        continue_button = ClickableButton("Continue applying")
        review_button = ClickableButton("Review job post")
        browser = DialogBrowser([
            SafetyDialog(close_button, continue_button, review_button)
        ])
        detected, closed = namespace[
            "_close_job_search_safety_reminder"
        ](browser)
        self.assertTrue(detected)
        self.assertTrue(closed)
        self.assertTrue(close_button.clicked)
        self.assertFalse(continue_button.clicked)
        self.assertFalse(review_button.clicked)
        self.assertFalse(browser.closed)

    def test_safety_reminder_without_safe_close_stops_current_application(self):
        namespace = load_runtime_functions(Mock())
        close_button = ClickableButton(displayed=False)
        continue_button = ClickableButton("Continue applying")
        browser = DialogBrowser([
            SafetyDialog(
                close_button,
                continue_button,
                ClickableButton("Review job post"),
            )
        ])
        self.assertEqual(
            namespace["_close_job_search_safety_reminder"](browser),
            (True, False),
        )
        self.assertFalse(continue_button.clicked)
        self.assertFalse(browser.closed)

    def test_easy_apply_cleanup_closes_modal_and_confirms_discard(self):
        events = []
        discard_dialog = CleanupDialog(displayed=False)
        easy_modal = CleanupDialog()
        close_button = CleanupButton("Cerrar", events=events)
        discard_button = CleanupButton("Descartar", events=events)
        easy_modal.buttons = [close_button]
        discard_dialog.buttons = [discard_button]

        def show_discard():
            discard_dialog.displayed = True

        def finish_discard():
            easy_modal.displayed = False
            discard_dialog.displayed = False

        close_button.on_click = show_discard
        discard_button.on_click = finish_discard
        review_queue = Mock()
        namespace = load_runtime_functions(Mock(), review_queue)
        result = namespace["_cleanup_easy_apply_modal"](
            CleanupBrowser(easy_modal, discard_dialog), "job-1"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["reason_code"], "easy_apply_application_discarded")
        self.assertFalse(result["modal_remains_open"])
        self.assertEqual(result["attempt_count"], 1)
        self.assertEqual(events, ["Cerrar", "Descartar"])
        review_queue.record_outcome.assert_called_once()
        self.assertEqual(
            review_queue.record_outcome.call_args.kwargs["reason_code"],
            "easy_apply_application_discarded",
        )

    def test_save_application_dialog_is_recognized_and_discarded(self):
        events = []
        save_dialog = CleanupDialog(
            text="Save this application?", displayed=False
        )
        easy_modal = CleanupDialog(text="Unfinished Easy Apply")
        close_button = CleanupButton("Close", events=events)
        discard_button = CleanupButton("Discard", events=events)
        save_button = CleanupButton("Save", events=events)
        easy_modal.buttons = [close_button]
        save_dialog.buttons = [discard_button, save_button]
        close_button.on_click = lambda: setattr(
            save_dialog, "displayed", True
        )

        def discard_application():
            save_dialog.displayed = False
            easy_modal.displayed = False

        discard_button.on_click = discard_application
        namespace = load_runtime_functions(Mock())
        browser = CleanupBrowser(easy_modal, save_dialog)
        save_dialog.displayed = True
        self.assertIn(
            save_dialog,
            namespace["_visible_abandonment_dialogs"](browser),
        )
        save_dialog.displayed = False
        result = namespace["_cleanup_easy_apply_modal"](browser, "job-1")

        self.assertTrue(
            namespace["_abandonment_confirmation_text"](save_dialog)
        )
        self.assertTrue(result["success"])
        self.assertEqual(
            result["reason_code"], "easy_apply_application_discarded"
        )
        self.assertTrue(discard_button.clicked)
        self.assertFalse(save_button.clicked)
        self.assertFalse(save_dialog.displayed)
        self.assertFalse(easy_modal.displayed)
        self.assertEqual(events, ["Close", "Discard"])

    def test_delayed_save_dialog_is_polled_before_next_job_click(self):
        events = []
        save_dialog = CleanupDialog(
            text="Save your application?", displayed=False
        )
        easy_modal = CleanupDialog(text="Unfinished Easy Apply")
        close_button = CleanupButton("Close", events=events)
        discard_button = CleanupButton("Discard", events=events)
        save_button = CleanupButton("Save", events=events)
        easy_modal.buttons = [close_button]
        save_dialog.buttons = [save_button, discard_button]
        close_button.on_click = lambda: setattr(
            save_dialog, "displayed", True
        )

        def discard_application():
            save_dialog.displayed = False
            easy_modal.displayed = False

        discard_button.on_click = discard_application
        browser = DelayedCleanupBrowser(
            easy_modal, save_dialog, hidden_checks=1
        )
        job_card = SyntheticJobCard(browser, events)
        namespace = load_runtime_functions(Mock())
        result = namespace["_guard_next_job_click"](browser, "job-1")
        if result["success"]:
            job_card.click()

        self.assertTrue(result["success"])
        self.assertGreaterEqual(browser.discard_checks, 2)
        self.assertTrue(job_card.clicked)
        self.assertFalse(save_button.clicked)
        self.assertEqual(events, ["Close", "Discard", "job-card"])

    def test_localized_save_dialog_discards_and_never_saves(self):
        cases = (
            ("Guardar esta solicitud", "Descartar", "Guardar"),
            ("Enregistrer cette candidature", "Abandonner", "Enregistrer"),
            ("Zapisz tę aplikację", "Odrzuć", "Zapisz"),
        )
        for dialog_text, discard_text, save_text in cases:
            with self.subTest(discard=discard_text):
                save_dialog = CleanupDialog(
                    text=dialog_text, displayed=False
                )
                easy_modal = CleanupDialog(text="Unfinished Easy Apply")
                close_button = CleanupButton("Close")
                discard_button = CleanupButton(discard_text)
                save_button = CleanupButton(save_text)
                easy_modal.buttons = [close_button]
                save_dialog.buttons = [save_button, discard_button]
                close_button.on_click = lambda dialog=save_dialog: setattr(
                    dialog, "displayed", True
                )

                def finish(dialog=save_dialog, application=easy_modal):
                    dialog.displayed = False
                    application.displayed = False

                discard_button.on_click = finish
                namespace = load_runtime_functions(Mock())
                result = namespace["_cleanup_easy_apply_modal"](
                    CleanupBrowser(easy_modal, save_dialog), "job-1"
                )
                self.assertTrue(result["success"])
                self.assertTrue(discard_button.clicked)
                self.assertFalse(save_button.clicked)

    def test_historical_success_modal_is_recognized_and_escape_dismisses_it(self):
        success_modal = CleanupDialog(
            text="Your application was sent to Synthetic employer"
        )
        browser = CleanupBrowser(success_modal)
        namespace = load_runtime_functions(Mock())
        namespace["actions"].on_send_keys = lambda _value: setattr(
            success_modal, "displayed", False
        )

        result = namespace["_cleanup_confirmed_success_modal"](
            browser, "job-1"
        )

        self.assertTrue(result["success_confirmation"])
        self.assertTrue(result["success"])
        self.assertFalse(result["modal_remains_open"])
        self.assertEqual(namespace["actions"].sent_keys, ["escape"])
        self.assertEqual(result["reason_code"], "easy_apply_modal_closed")

    def test_success_promotion_uses_not_now_and_never_update_profile(self):
        success_modal = CleanupDialog(
            text="Your application was sent to Synthetic employer"
        )
        update_profile = CleanupButton("Update profile")
        not_now = CleanupButton(
            "Not now",
            on_click=lambda: setattr(success_modal, "displayed", False),
        )
        close = CleanupButton(
            attrs={"aria-label": "Close"},
            on_click=lambda: setattr(success_modal, "displayed", False),
        )
        success_modal.buttons = [update_profile, not_now, close]
        namespace = load_runtime_functions(Mock())
        result = namespace["_cleanup_confirmed_success_modal"](
            CleanupBrowser(success_modal), "job-1"
        )

        self.assertTrue(result["success"])
        self.assertTrue(not_now.clicked)
        self.assertFalse(update_profile.clicked)
        self.assertFalse(close.clicked)

    def test_delayed_generic_success_overlay_is_polled_then_dismissed(self):
        events = []
        success_modal = CleanupDialog(
            text="Your application was sent to agap2 Spain!",
            displayed=False,
        )
        update_profile = CleanupButton("Update profile", events=events)
        not_now = CleanupButton(
            "Not now",
            on_click=lambda: setattr(success_modal, "displayed", False),
            events=events,
        )
        success_modal.buttons = [update_profile, not_now]
        browser = GenericOverlayBrowser(success_modal)
        namespace = load_runtime_functions(Mock())
        poll_count = 0

        def advance_render(_delay):
            nonlocal poll_count
            poll_count += 1
            if poll_count == 2:
                success_modal.displayed = True

        namespace["sleep"] = advance_render
        state = namespace["_wait_for_post_submit_state"](
            browser,
            CleanupDialog(text="Easy Apply", displayed=False),
            AppliedStateJob(False),
            set(),
            timeout_seconds=1,
            poll_seconds=0.1,
        )

        self.assertEqual(state["status"], "success")
        self.assertTrue(state["success_modal_detected"])
        self.assertGreaterEqual(poll_count, 2)
        result = namespace["_cleanup_confirmed_success_modal"](
            browser, "job-1"
        )
        self.assertTrue(result["success"])
        self.assertEqual(events, ["Not now"])
        self.assertFalse(update_profile.clicked)

    def test_generic_artdeco_overlay_is_not_scoped_to_easy_apply_form(self):
        success_modal = CleanupDialog(
            text="Your application was sent to agap2 Spain!"
        )
        browser = GenericOverlayBrowser(success_modal)
        namespace = load_runtime_functions(Mock())

        classification = namespace["_classify_visible_overlays"](browser)
        snapshot = namespace["_post_submit_snapshot"](
            browser,
            CleanupDialog(text="Easy Apply", displayed=False),
            AppliedStateJob(False),
            set(),
        )

        self.assertEqual(classification["success"], [success_modal])
        self.assertEqual(classification["unfinished"], [])
        self.assertEqual(classification["unknown"], [])
        self.assertEqual(snapshot["status"], "success")
        self.assertTrue(snapshot["success_modal_detected"])

    def test_applied_job_state_confirms_success_after_overlay_disappears(self):
        namespace = load_runtime_functions(Mock())
        snapshot = namespace["_post_submit_snapshot"](
            GenericOverlayBrowser(),
            CleanupDialog(text="Easy Apply", displayed=False),
            AppliedStateJob(True),
            set(),
        )

        self.assertEqual(snapshot["status"], "success")
        self.assertFalse(snapshot["success_modal_detected"])
        self.assertTrue(snapshot["applied_state_detected"])
        self.assertEqual(snapshot["visible_overlay_count"], 0)

    def test_success_cleanup_requires_the_actual_overlay_to_disappear(self):
        success_modal = CleanupDialog(text="Your application was sent")

        def remove_only_success_text():
            success_modal.text = "Profile update available"

        not_now = CleanupButton("Not now", on_click=remove_only_success_text)
        success_modal.buttons = [not_now]
        browser = GenericOverlayBrowser(success_modal)
        namespace = load_runtime_functions(Mock())

        result = namespace["_cleanup_confirmed_success_modal"](
            browser, "job-1"
        )

        self.assertTrue(not_now.clicked)
        self.assertFalse(result["success"])
        self.assertTrue(result["modal_remains_open"])
        self.assertEqual(
            result["reason_code"],
            "post_apply_success_modal_cleanup_failed",
        )

    def test_success_modal_is_classified_before_unfinished_discard_cleanup(self):
        success_modal = CleanupDialog(
            text="Application submitted",
        )
        update_profile = CleanupButton("Update profile")
        discard = CleanupButton("Discard")
        not_now = CleanupButton(
            "Not now",
            on_click=lambda: setattr(success_modal, "displayed", False),
        )
        success_modal.buttons = [update_profile, discard, not_now]
        review_queue = Mock()
        namespace = load_runtime_functions(Mock(), review_queue)
        result = namespace["_cleanup_easy_apply_modal"](
            CleanupBrowser(success_modal), "job-1"
        )

        self.assertTrue(result["success_confirmation"])
        self.assertFalse(result["success"])
        self.assertEqual(
            result["reason_code"], "post_apply_success_modal_pending"
        )
        self.assertFalse(discard.clicked)
        self.assertFalse(update_profile.clicked)
        self.assertFalse(not_now.clicked)
        review_queue.record_outcome.assert_not_called()

    def test_next_job_guard_dismisses_success_overlay_before_card_click(self):
        events = []
        success_modal = CleanupDialog(text="Your application was sent")
        not_now = CleanupButton(
            "Not now",
            on_click=lambda: setattr(success_modal, "displayed", False),
            events=events,
        )
        success_modal.buttons = [not_now]
        browser = CleanupBrowser(success_modal)
        job_card = SyntheticJobCard(browser, events)
        namespace = load_runtime_functions(Mock())

        result = namespace["_guard_next_job_click"](browser, "job-1")
        if result["success"]:
            job_card.click()

        self.assertTrue(result["success_confirmation"])
        self.assertTrue(job_card.clicked)
        self.assertEqual(events, ["Not now", "job-card"])

    def test_next_job_waits_for_generic_overlay_disappearance(self):
        events = []
        success_modal = CleanupDialog(
            text="Your application was sent to agap2 Spain!"
        )
        success_modal.buttons = [CleanupButton(
            "Not now",
            on_click=lambda: setattr(success_modal, "displayed", False),
            events=events,
        )]
        browser = GenericOverlayBrowser(success_modal)
        job_card = SyntheticJobCard(browser, events)
        namespace = load_runtime_functions(Mock())

        result = namespace["_guard_next_job_click"](browser, "job-1")
        if result["success"]:
            job_card.click()

        self.assertTrue(result["success"])
        self.assertTrue(job_card.clicked)
        self.assertEqual(events, ["Not now", "job-card"])

    def test_success_dismiss_failure_stays_submitted_and_blocks_next_click(self):
        success_modal = CleanupDialog(text="Your application was sent")
        success_modal.buttons = [CleanupButton("Update profile")]
        browser = CleanupBrowser(success_modal)
        job_card = SyntheticJobCard(browser, [])
        namespace = load_runtime_functions(Mock())

        result = namespace["_guard_next_job_click"](browser, "job-1")
        if result["success"]:
            job_card.click()

        self.assertTrue(result["success_confirmation"])
        self.assertFalse(result["success"])
        self.assertTrue(result["modal_remains_open"])
        self.assertFalse(job_card.clicked)
        self.assertFalse(success_modal.buttons[0].clicked)

    def test_localized_close_and_discard_controls_are_recognized(self):
        namespace = load_runtime_functions(Mock())
        matcher = namespace["_localized_modal_action"]
        for label in (
            "Close", "Dismiss", "Cerrar", "Fermer", "Zamknij",
            "Fechar", "Schließen", "Chiudi", "Sluiten",
        ):
            with self.subTest(action="close", label=label):
                self.assertTrue(matcher(CleanupButton(label), "close"))
        for label in (
            "Discard", "Descartar", "Abandon", "Abandonner", "Odrzuć",
            "Abandonar", "Verwerfen", "Annulla",
        ):
            with self.subTest(action="discard", label=label):
                self.assertTrue(matcher(CleanupButton(label), "discard"))

    def test_cleanup_can_close_without_discard_dialog(self):
        easy_modal = CleanupDialog()
        close_button = CleanupButton(
            attrs={"aria-label": "Dismiss Easy Apply modal"},
            on_click=lambda: setattr(easy_modal, "displayed", False),
        )
        easy_modal.buttons = [close_button]
        namespace = load_runtime_functions(Mock())
        browser = CleanupBrowser(easy_modal)
        result = namespace["_cleanup_easy_apply_modal"](browser, "job-1")
        self.assertTrue(result["success"])
        self.assertEqual(result["reason_code"], "easy_apply_modal_closed")
        self.assertTrue(close_button.clicked)
        self.assertFalse(browser.window_close_called)

    def test_next_job_guard_cleans_before_job_card_click(self):
        events = []
        easy_modal = CleanupDialog()
        close_button = CleanupButton(
            "Close",
            on_click=lambda: setattr(easy_modal, "displayed", False),
            events=events,
        )
        easy_modal.buttons = [close_button]
        browser = CleanupBrowser(easy_modal)
        job_card = SyntheticJobCard(browser, events)
        namespace = load_runtime_functions(Mock())

        result = namespace["_guard_next_job_click"](browser, "job-1")
        if result["success"]:
            job_card.click()

        self.assertTrue(job_card.clicked)
        self.assertEqual(events, ["Close", "job-card"])

    def test_open_discard_dialog_before_next_job_is_resolved_first(self):
        events = []
        easy_modal = CleanupDialog()
        discard_dialog = CleanupDialog(text="Discard application?", displayed=True)
        close_button = CleanupButton("Close", events=events)
        discard_button = CleanupButton("Odrzuć", events=events)
        easy_modal.buttons = [close_button]
        discard_dialog.buttons = [discard_button]

        def finish_discard():
            easy_modal.displayed = False
            discard_dialog.displayed = False

        discard_button.on_click = finish_discard
        browser = CleanupBrowser(easy_modal, discard_dialog)
        namespace = load_runtime_functions(Mock())
        result = namespace["_guard_next_job_click"](browser, "job-1")
        self.assertTrue(result["success"])
        self.assertEqual(events, ["Odrzuć"])
        self.assertFalse(close_button.clicked)

    def test_cleanup_retries_once_then_succeeds(self):
        attempts = []
        easy_modal = CleanupDialog()

        def close_on_second_attempt():
            attempts.append("close")
            if len(attempts) == 2:
                easy_modal.displayed = False

        easy_modal.buttons = [CleanupButton("Close", on_click=close_on_second_attempt)]
        namespace = load_runtime_functions(Mock())
        result = namespace["_cleanup_easy_apply_modal"](
            CleanupBrowser(easy_modal), "job-1"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["attempt_count"], 2)
        self.assertEqual(attempts, ["close", "close"])

    def test_failed_cleanup_blocks_next_click_after_two_attempts(self):
        events = []
        easy_modal = CleanupDialog()
        easy_modal.buttons = [CleanupButton("Close", events=events)]
        browser = CleanupBrowser(easy_modal)
        job_card = SyntheticJobCard(browser, events)
        review_queue = Mock()
        namespace = load_runtime_functions(Mock(), review_queue)

        result = namespace["_guard_next_job_click"](browser, "job-1")
        if result["success"]:
            job_card.click()

        self.assertFalse(result["success"])
        self.assertEqual(result["attempt_count"], 2)
        self.assertEqual(result["reason_code"], "easy_apply_modal_cleanup_failed")
        self.assertTrue(result["modal_remains_open"])
        self.assertFalse(job_card.clicked)
        self.assertEqual(events, ["Close", "Close"])
        self.assertFalse(browser.window_close_called)
        review_queue.record_outcome.assert_called_once()
        self.assertEqual(
            review_queue.record_outcome.call_args.kwargs["reason_code"],
            "easy_apply_modal_cleanup_failed",
        )

    def test_no_modal_guard_is_a_noop_without_review_row(self):
        review_queue = Mock()
        namespace = load_runtime_functions(Mock(), review_queue)
        result = namespace["_guard_next_job_click"](
            CleanupBrowser(), "job-1"
        )
        self.assertTrue(result["success"])
        self.assertFalse(result["cleanup_needed"])
        self.assertEqual(result["attempt_count"], 0)
        review_queue.record_outcome.assert_not_called()

    def test_visible_enabled_submit_button_marks_final_review(self):
        namespace = load_runtime_functions(Mock())
        modal = SubmitModal([], ClickableButton("Submit application"))
        self.assertTrue(
            namespace["_final_review_reached_from_submit_button"](
                modal, set()
            )
        )
        self.assertFalse(
            namespace["_final_review_reached_from_submit_button"](
                modal, {"required:field"}
            )
        )

    def test_hidden_or_disabled_submit_does_not_mark_final_review(self):
        namespace = load_runtime_functions(Mock())
        for button in (
            ClickableButton("Submit application", displayed=False),
            ClickableButton("Submit application", enabled=False),
            ClickableButton(
                "Submit application", attrs={"aria-disabled": "true"}
            ),
        ):
            with self.subTest(button=button):
                self.assertFalse(
                    namespace["_final_review_reached_from_submit_button"](
                        SubmitModal([], button), set()
                    )
                )

    def test_safety_skip_and_submit_final_state_are_wired_before_submission(self):
        source = RUNTIME.read_text(encoding="utf-8")
        self.assertIn('"safety_warning_skipped"', source)
        self.assertIn('"job_search_safety_reminder"', source)
        self.assertIn("except JobSearchSafetyReminder as e:", source)
        safety_except = source[source.index("except JobSearchSafetyReminder as e:"):]
        safety_branch = safety_except.split("except Exception as e:")[0]
        self.assertLess(
            safety_except.index("continue"),
            safety_except.index("except Exception as e:"),
        )
        self.assertIn("failed_job(", safety_branch)
        self.assertIn('"Skipped"', safety_branch)
        self.assertIn("rejected_jobs.add(job_id)", safety_branch)
        self.assertIn("skip_count += 1", safety_branch)
        self.assertIn("_cleanup_easy_apply_modal(driver, job_id)", safety_branch)

        detected = source.index("final_review_detected_from_submit_button")
        guard = source.index(
            "if unresolved_required or not reached_review or current_count >= switch_number:"
        )
        pause = source.index("if errored != \"stuck\" and cur_pause_before_submit:")
        submit = source.index('wait_span_click(driver, "Submit application"')
        self.assertLess(detected, guard)
        self.assertLess(guard, pause)
        self.assertLess(pause, submit)

    def test_submit_guard_and_confirmation_are_present(self):
        source = RUNTIME.read_text(encoding="utf-8")
        self.assertIn("if unresolved_required or not reached_review or current_count >= switch_number:", source)
        self.assertIn("_wait_for_post_submit_state(", source)
        self.assertNotIn('wait_span_click(driver, "Done", 2)', source)
        self.assertLess(source.index("if unresolved_required or not reached_review"), source.index('wait_span_click(driver, "Submit application"'))

    def test_visible_success_is_accounted_once_without_failed_path(self):
        source = RUNTIME.read_text(encoding="utf-8")
        submit = source[source.index(
            'if wait_span_click(driver, "Submit application"'
        ):source.index("# Case 2: Apply externally")]
        self.assertLess(
            submit.index("_wait_for_post_submit_state("),
            submit.index('if post_submit_state["status"] == "success":'),
        )
        self.assertIn('ai_review_context["application_submitted"] = True', submit)
        self.assertEqual(submit.count('_record_review_outcome("submitted")'), 2)
        self.assertIn('if cleanup_result.get("success_confirmation"):', submit)
        success_exception_branch = submit[
            submit.index('if cleanup_result.get("success_confirmation"):'):
            submit.index("else:\n                                print_lg", submit.index('if cleanup_result.get("success_confirmation"):'))
        ]
        self.assertNotIn("failed_count += 1", success_exception_branch)
        self.assertEqual(source.count("easy_applied_count += 1"), 1)
        self.assertEqual(source.count("applied_jobs.add(job_id)"), 1)
        accounting = source.index("easy_applied_count += 1")
        cleanup = source.index(
            "_cleanup_confirmed_success_modal(", accounting
        )
        self.assertLess(accounting, cleanup)

    def test_polling_has_no_accounting_side_effect_and_cleanup_failure_stops(self):
        source = RUNTIME.read_text(encoding="utf-8")
        wait_start = source.index("def _wait_for_post_submit_state(")
        wait_end = source.index("def _log_post_submit_state(", wait_start)
        wait_source = source[wait_start:wait_end]
        self.assertNotIn("easy_applied_count", wait_source)
        self.assertNotIn("failed_count", wait_source)
        self.assertNotIn("applied_jobs.add", wait_source)
        self.assertNotIn("_record_review_outcome", wait_source)

        accounting = source.index("easy_applied_count += 1")
        cleanup = source.index(
            "_cleanup_confirmed_success_modal(", accounting
        )
        cleanup_failure = source.index(
            '"post_apply_success_modal_cleanup_failed"', cleanup
        )
        stop_scan = source.index(
            "stop_current_search_term_scan = True", cleanup_failure
        )
        self.assertLess(accounting, cleanup)
        self.assertLess(cleanup, cleanup_failure)
        self.assertLess(cleanup_failure, stop_scan)
        self.assertNotIn(
            "failed_count += 1", source[accounting:stop_scan]
        )

    def test_pause_confirmation_returns_to_post_submit_wait(self):
        source = RUNTIME.read_text(encoding="utf-8")
        pause_start = source.index(
            'if errored != "stuck" and cur_pause_before_submit:'
        )
        submit = source.index(
            'wait_span_click(driver, "Submit application"', pause_start
        )
        post_submit_wait = source.index(
            "_wait_for_post_submit_state(", submit
        )
        pause_to_wait = source[pause_start:post_submit_wait]
        self.assertIn("pyautogui.confirm(", pause_to_wait)
        self.assertLess(pause_start, submit)
        self.assertLess(submit, post_submit_wait)
        self.assertNotRegex(
            pause_to_wait,
            r"(?m)^\s*(?:return\b|exit\(|driver\.quit)",
        )

    def test_invalid_field_repair_runs_only_after_original_click_fails(self):
        source = RUNTIME.read_text(encoding="utf-8")
        loop = source.index("while next_button:")
        answer = source.index("answer_questions(", loop)
        original_click = source.index("next_button.click()", answer)
        original_buffer = source.index("buffer(click_gap)", original_click)
        repair = source.index(
            "_repair_after_failed_advance(", original_buffer
        )
        retry_click = source.index("next_button.click()", repair)
        self.assertLess(answer, original_click)
        self.assertLess(original_click, original_buffer)
        self.assertLess(original_buffer, repair)
        self.assertLess(repair, retry_click)
        self.assertNotIn(
            "_collect_invalid_required_fields(",
            source[answer:original_click],
        )
        self.assertNotIn("Help Needed", source)
        self.assertNotIn("if pause_at_failed_question:", source)

    def test_repair_retries_the_original_navigation_once(self):
        source = RUNTIME.read_text(encoding="utf-8")
        loop_start = source.index("while next_button:")
        loop_end = source.index(
            "except NoSuchElementException:\n"
            "                                safety_detected",
            loop_start,
        )
        loop = source[loop_start:loop_end]
        repair = loop.index("_repair_after_failed_advance(")
        retry = loop.index("next_button.click()", repair)

        self.assertEqual(loop.count("next_button.click()"), 2)
        self.assertIn("if repair_result is True:", loop)
        self.assertIn("repaired_page_signatures", loop)
        self.assertLess(repair, retry)

    def test_ai_fallback_does_not_own_submit_or_pagination(self):
        source = RUNTIME.read_text(encoding="utf-8")
        unknown = source[
            source.index("def _unknown_answer("):
            source.index("def _answers_match(")
        ]
        repair = source[
            source.index("def _linkedin_validation_message("):
            source.index("# Function to answer the questions for Easy Apply")
        ]
        for section in (unknown, repair):
            self.assertNotIn("Submit application", section)
            self.assertNotIn("jobs-search-pagination", section)
            self.assertNotIn("switch_to", section)
            self.assertNotIn("driver.get", section)
        self.assertNotIn("next_button.click()", repair)

    def test_failed_question_discards_and_continues_without_interaction(self):
        source = RUNTIME.read_text(encoding="utf-8")
        loop = source[source.index("while next_button:"):]
        stuck = loop[loop.index("if next_counter >= 15:"):]
        outer_except = stuck[stuck.index("except Exception as e:"):]
        self.assertIn('"failed_question_unresolved"', stuck)
        self.assertLess(
            stuck.index('"failed_question_unresolved"'),
            stuck.index("raise Exception("),
        )
        self.assertIn("_cleanup_easy_apply_modal(driver, job_id)", outer_except)
        self.assertLess(
            outer_except.index("_cleanup_easy_apply_modal(driver, job_id)"),
            outer_except.index("continue"),
        )
        self.assertNotIn("pyautogui.alert", stuck.split("except Exception as e:")[0])

    def test_all_non_submitted_easy_apply_failures_reach_cleanup(self):
        source = RUNTIME.read_text(encoding="utf-8")
        easy_apply = source[source.index("# Case 1: Easy Apply Button"):]
        for failure_marker in (
            "Required application fields remain unresolved",
            "Submit guard blocked application",
            "Failed to click Submit application",
            "Post-submit confirmation timed out",
            "Job application discarded by user",
        ):
            with self.subTest(failure_marker=failure_marker):
                self.assertIn(failure_marker, easy_apply)
        self.assertEqual(
            easy_apply.count("_cleanup_easy_apply_modal(driver, job_id)"), 2
        )
        self.assertIn("except JobSearchSafetyReminder as e:", easy_apply)
        self.assertIn("except Exception as e:", easy_apply)

    def test_next_job_guard_precedes_job_card_click_and_stops_scan_on_failure(self):
        source = RUNTIME.read_text(encoding="utf-8")
        job_loop = source[source.index("for job in job_listings:"):]
        guard = job_loop.index("_guard_next_job_click(driver, prior_job_id)")
        details = job_loop.index("get_job_main_details(")
        self.assertLess(guard, details)
        self.assertIn('if not cleanup_guard["success"]:', job_loop[:details])
        self.assertIn("stop_current_search_term_scan = True", job_loop[:details])
        self.assertIn("if stop_current_search_term_scan:", job_loop)

    def test_unfinished_cleanup_never_closes_browser_window_or_uses_escape(self):
        source = RUNTIME.read_text(encoding="utf-8")
        start = source.index("def _element_is_visible")
        end = source.index("class JobSearchSafetyReminder", start)
        cleanup_source = source[start:end]
        self.assertNotIn("driver.close", cleanup_source)
        self.assertNotIn("browser.close", cleanup_source)
        self.assertNotIn("driver.quit", cleanup_source)
        unfinished_start = cleanup_source.index(
            "def _cleanup_easy_apply_modal_once"
        )
        unfinished_end = cleanup_source.index(
            "def _cleanup_easy_apply_modal(", unfinished_start
        )
        self.assertNotIn(
            "Keys.ESCAPE", cleanup_source[unfinished_start:unfinished_end]
        )
        success_start = cleanup_source.index(
            "def _dismiss_confirmed_success_modal"
        )
        success_end = cleanup_source.index(
            "def _cleanup_confirmed_success_modal", success_start
        )
        self.assertIn(
            "actions.send_keys(Keys.ESCAPE).perform()",
            cleanup_source[success_start:success_end],
        )
        self.assertNotIn("discard_job", source)

    def test_abandonment_cleanup_never_clicks_save(self):
        source = RUNTIME.read_text(encoding="utf-8")
        abandonment_start = source.index("def _visible_abandonment_dialogs")
        abandonment_end = source.index(
            "def _success_confirmation_text", abandonment_start
        )
        abandonment_source = source[abandonment_start:abandonment_end]
        self.assertIn(
            '_scoped_action_buttons(dialog, "save")', abandonment_source
        )
        self.assertNotIn("save_buttons[0].click()", abandonment_source)

        cleanup_start = source.index("def _cleanup_easy_apply_modal_once")
        cleanup_end = source.index(
            "def _cleanup_easy_apply_modal(", cleanup_start
        )
        unfinished_cleanup = source[cleanup_start:cleanup_end]
        self.assertIn("discard_buttons[0].click()", unfinished_cleanup)
        self.assertNotIn('"save"', unfinished_cleanup)

    def test_pause_before_submit_path_remains_present(self):
        source = RUNTIME.read_text(encoding="utf-8")
        self.assertIn("cur_pause_before_submit = pause_before_submit", source)
        self.assertIn(
            'if errored != "stuck" and cur_pause_before_submit:', source
        )

    def test_full_page_html_is_never_printed(self):
        source = RUNTIME.read_text(encoding="utf-8")
        self.assertNotIn("print_lg(driver.page_source", source)
        self.assertNotRegex(source, r"print(?:_lg)?\([^\n]*(?:outerHTML|innerHTML)")
        self.assertIn("full page diagnostics suppressed", source)

    def test_unresolved_state_is_created_inside_each_easy_apply_application(self):
        source = RUNTIME.read_text(encoding="utf-8")
        initialized = source.index("unresolved_required = set()")
        page_loop = source.index("while next_button:", initialized)
        answer_call = source.index("answer_questions(", page_loop)
        self.assertLess(initialized, page_loop)
        self.assertLess(page_loop, answer_call)
        self.assertEqual(source.count("unresolved_required = set()"), 1)

    def test_old_unsafe_fallbacks_and_v3_are_absent(self):
        source = RUNTIME.read_text(encoding="utf-8")
        self.assertNotIn("select.select_by_index(randint", source)
        self.assertNotIn("ele = options[0]", source)
        self.assertNotIn("modules.ai.v3", source)
        self.assertNotIn(
            "any(word in label.lower() for word in ['experiencia', 'tienes', 'has'])",
            source,
        )
        fallback = source[source.index("if answer == \"\":", source.index("# Check if it's a text question")):]
        self.assertNotIn("answer = years_of_experience", fallback.split("# Check if it's a textarea question")[0])
        self.assertNotIn("if 'experience' in label or 'years' in label", source)

    def test_expected_salary_branch_cannot_use_stale_config_value(self):
        source = RUNTIME.read_text(encoding="utf-8")
        salary_branch = source[
            source.index("elif 'salary' in label"):
            source.index("elif 'linkedin' in label")
        ]
        expected_salary_branch = salary_branch[salary_branch.index("else:"):]
        self.assertIn("_unknown_answer(", expected_salary_branch)
        self.assertNotIn("desired_salary", expected_salary_branch)

    def test_review_queue_hooks_do_not_change_application_state_machine(self):
        source = RUNTIME.read_text(encoding="utf-8")
        self.assertIn("ai_answer_review_queue = AIAnswerReviewQueue()", source)
        self.assertIn(
            '_record_review_outcome(\n                                    "reached_review", final_review_reason',
            source,
        )
        self.assertIn('_record_review_outcome("submitted")', source)
        self.assertIn('"application_discarded"', source)
        self.assertIn("ai_answer_review_queue.print_summary()", source)
        self.assertLess(
            source.index(
                '_record_review_outcome(\n                                    "reached_review", final_review_reason'
            ),
            source.index('wait_span_click(driver, "Submit application"'),
        )


if __name__ == "__main__":
    unittest.main()
