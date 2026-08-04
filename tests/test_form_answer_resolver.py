from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal
import inspect
import unittest

from modules.forms import (
    AnswerResolver,
    AnswerResult,
    AnswerSource,
    AnswerStatus,
    Confidence,
    FieldConstraints,
    FieldKind,
    FormField,
    ProfileFactResult,
    ProviderResult,
    RepairRequest,
    RepairStatus,
    SemanticCategory,
    SemanticPolicy,
    ValidationIssue,
    ValidationIssueKind,
)
from modules.forms import policies as policies_module
from modules.forms import provider as provider_module
from modules.forms import resolver as resolver_module


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


class FakeProvider:
    def __init__(self, results):
        self.results = list(results)
        self.requests = []

    def answer(self, request):
        self.requests.append(request)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeReviewQueue:
    def __init__(self):
        self.records = []

    def record(self, record):
        self.records.append(record)


def fact(value, key="profile.fact", *, verified=True):
    return ProfileFactResult(
        found=True,
        verified=verified,
        value=value,
        profile_key=key,
        reason_code="verified_profile_fact" if verified else "unverified_profile_fact",
    )


def provider_answer(
    value,
    *,
    confidence=Confidence.HIGH,
    answered=True,
    reason="provider_test_answer",
    requests=1,
):
    return ProviderResult(
        answered=answered,
        value=value,
        confidence=confidence,
        reason_code=reason,
        request_count=requests,
    )


def answer_result(value, *, review=False):
    return AnswerResult(
        status=AnswerStatus.RESOLVED,
        value=value,
        source=AnswerSource.LINKEDIN,
        confidence=Confidence.HIGH,
        reason_code="previous_answer",
        requires_review=review,
    )


def field(
    kind,
    *,
    key="field-1",
    question="Synthetic ordinary application question",
    required=True,
    existing=None,
    constraints=FieldConstraints(),
    options=(),
    exact=False,
    profile_key=None,
    allow_yes=True,
    numeric_default=None,
    context=(),
):
    return FormField(
        field_key=key,
        kind=kind,
        question=question,
        required=required,
        existing_value=existing,
        constraints=constraints,
        visible_options=tuple(options),
        exact_fact_only=exact,
        profile_key=profile_key or ("profile.synthetic" if exact else None),
        allow_yes_no_default=allow_yes,
        numeric_default=numeric_default,
        candidate_context=tuple(context),
        job_id="job-123",
        company="Example Company",
        job_title="Example Role",
    )


def repair_request(
    target,
    issue_kind,
    rejected,
    *,
    message="Synthetic validation message",
    attempt=1,
    previous=None,
    constraints=None,
    options=None,
):
    return RepairRequest(
        field=target,
        previous_answer=previous,
        validation_issue=ValidationIssue(
            field_key=target.field_key,
            issue_kind=issue_kind,
            message=message,
            rejected_value=rejected,
            constraints=constraints or target.constraints,
            visible_options=tuple(target.visible_options if options is None else options),
        ),
        attempt_number=attempt,
    )


class SemanticPolicyTests(unittest.TestCase):
    def test_english_and_spanish_categories_are_first_class(self):
        cases = {
            "Are you authorized to work in Spain?": SemanticCategory.WORK_AUTHORIZATION,
            "¿Necesitarás patrocinio de visado?": SemanticCategory.SPONSORSHIP,
            "Are you an EU citizen?": SemanticCategory.EU_CITIZENSHIP,
            "¿Cuál es tu nacionalidad?": SemanticCategory.CITIZENSHIP,
            "Do you hold a security clearance?": SemanticCategory.SECURITY_CLEARANCE,
            "Do you have this certification?": SemanticCategory.CERTIFICATION_POSSESSION,
            "¿Tienes un grado universitario?": SemanticCategory.EDUCATION_POSSESSION,
            "¿Tienes carnet de conducir?": SemanticCategory.DRIVING_LICENCE_POSSESSION,
            "Have you worked for Example before?": SemanticCategory.EMPLOYMENT_HISTORY,
            "Have you ever been employed by Example?": SemanticCategory.EMPLOYMENT_HISTORY,
            "Do you have criminal convictions?": SemanticCategory.LEGAL_CRIMINAL_DECLARATION,
            "Do you have a conflict of interest?": SemanticCategory.LEGAL_CRIMINAL_DECLARATION,
            "What is your expected salary?": SemanticCategory.SALARY_EXACT,
            "¿Cuál es tu nivel de inglés?": SemanticCategory.LANGUAGE_EXACT_LEVEL,
            "Do you speak English?": SemanticCategory.LANGUAGE_EXACT_LEVEL,
            "How many years of experience with Python?": SemanticCategory.ORDINARY_EXPERIENCE,
            "Are you comfortable with on-call work?": SemanticCategory.ORDINARY_CAPABILITY,
            "What location do you prefer?": SemanticCategory.ORDINARY_PREFERENCE,
            "Can you commute to Madrid?": SemanticCategory.COMMUTE,
            "¿Estás dispuesto a reubicarte?": SemanticCategory.RELOCATION,
            "Are you willing to travel?": SemanticCategory.TRAVEL_WILLINGNESS,
            "Send me promotional marketing updates": SemanticCategory.OPTIONAL_MARKETING_CONSENT,
        }
        policy = SemanticPolicy()
        for question, expected in cases.items():
            with self.subTest(question=question):
                actual = policy.classify(field(FieldKind.TEXT, question=question))
                self.assertEqual(actual.category, expected)

    def test_authorization_sponsorship_and_citizenship_are_not_conflated(self):
        policy = SemanticPolicy()
        authorization = policy.classify(field(FieldKind.RADIO, question="Are you legally authorized to work?"))
        sponsorship = policy.classify(field(FieldKind.RADIO, question="Will you require sponsorship?"))
        citizenship = policy.classify(field(FieldKind.RADIO, question="Are you a Spanish citizen?"))
        self.assertEqual(len({authorization.category, sponsorship.category, citizenship.category}), 3)
        self.assertEqual(len({authorization.profile_key, sponsorship.profile_key, citizenship.profile_key}), 3)

    def test_commute_relocation_travel_and_driving_are_not_conflated(self):
        policy = SemanticPolicy()
        questions = (
            "Can you commute to Madrid?",
            "Are you willing to relocate?",
            "Are you willing to travel?",
            "Do you have a driving licence?",
        )
        categories = {
            policy.classify(field(FieldKind.RADIO, question=question)).category
            for question in questions
        }
        self.assertEqual(
            categories,
            {
                SemanticCategory.COMMUTE,
                SemanticCategory.RELOCATION,
                SemanticCategory.TRAVEL_WILLINGNESS,
                SemanticCategory.DRIVING_LICENCE_POSSESSION,
            },
        )

    def test_job_requirement_statement_is_not_candidate_possession(self):
        policy = SemanticPolicy()
        certification = policy.classify(field(FieldKind.TEXT, question="This job requires AWS certification"))
        education = policy.classify(field(FieldKind.TEXT, question="A degree is required for this role"))
        self.assertNotEqual(certification.category, SemanticCategory.CERTIFICATION_POSSESSION)
        self.assertNotEqual(education.category, SemanticCategory.EDUCATION_POSSESSION)

    def test_required_procedural_ack_is_distinct_from_legal_declaration(self):
        policy = SemanticPolicy()
        procedural = policy.classify(field(FieldKind.CHECKBOX, question="I confirm the information is complete", required=True))
        legal = policy.classify(field(FieldKind.CHECKBOX, question="I declare I have no criminal convictions", required=True))
        self.assertEqual(procedural.category, SemanticCategory.REQUIRED_PROCEDURAL_ACKNOWLEDGEMENT)
        self.assertEqual(legal.category, SemanticCategory.LEGAL_CRIMINAL_DECLARATION)


class AnswerResolutionTests(unittest.TestCase):
    def setUp(self):
        self.profile = FakeProfile()

    def test_required_source_categories_exist(self):
        self.assertTrue({"LINKEDIN", "PROFILE", "POLICY", "PROVIDER", "DEFAULT", "NONE"}.issubset(AnswerSource.__members__))

    def test_valid_linkedin_value_is_preserved_without_reprocessing(self):
        target = field(FieldKind.TEXT, existing="Preserved")
        provider = FakeProvider([provider_answer("unused")])
        result = AnswerResolver().resolve(target, self.profile, provider)
        self.assertEqual(result.status, AnswerStatus.PRESERVED)
        self.assertEqual(result.source, AnswerSource.LINKEDIN)
        self.assertEqual(self.profile.calls, [])
        self.assertEqual(provider.requests, [])

    def test_valid_existing_select_and_radio_options_are_preserved(self):
        for kind in (FieldKind.SELECT, FieldKind.RADIO):
            with self.subTest(kind=kind):
                target = field(kind, existing="Hybrid", options=("Remote", "Hybrid"))
                provider = FakeProvider([provider_answer("unused")])
                result = AnswerResolver().resolve(target, self.profile, provider)
                self.assertEqual(result.status, AnswerStatus.PRESERVED)
                self.assertEqual(result.value, "Hybrid")
                self.assertEqual(provider.requests, [])

    def test_invalid_existing_option_is_re_resolved_from_current_options(self):
        target = field(FieldKind.SELECT, existing="Old", options=("Remote", "Hybrid"))
        provider = FakeProvider([provider_answer("Hybrid")])
        result = AnswerResolver().resolve(target, self.profile, provider)
        self.assertEqual(result.value, "Hybrid")
        self.assertEqual(result.source, AnswerSource.PROVIDER)

    def test_protected_fact_corrects_conflicting_prefilled_value(self):
        target = field(FieldKind.RADIO, question="Are you authorized to work in Spain?", existing="Yes", options=("Yes", "No"))
        profile = FakeProfile({"legal.work_authorization": fact("No", "legal.work_authorization")})
        provider = FakeProvider([provider_answer("Yes")])
        result = AnswerResolver().resolve(target, profile, provider)
        self.assertEqual(result.value, "No")
        self.assertEqual(result.source, AnswerSource.PROFILE)
        self.assertEqual(provider.requests, [])

    def test_authorization_and_sponsorship_resolve_from_distinct_profile_facts(self):
        profile = FakeProfile({
            "legal.work_authorization": fact("Yes", "legal.work_authorization"),
            "legal.requires_sponsorship": fact("No", "legal.requires_sponsorship"),
        })
        authorization = field(FieldKind.RADIO, key="auth", question="Are you authorized to work?", options=("Yes", "No"))
        sponsorship = field(FieldKind.RADIO, key="sponsor", question="Do you require sponsorship?", options=("Yes", "No"))
        self.assertEqual(AnswerResolver().resolve(authorization, profile, None).value, "Yes")
        self.assertEqual(AnswerResolver().resolve(sponsorship, profile, None).value, "No")

    def test_missing_or_unverified_protected_fact_never_reaches_provider(self):
        target = field(FieldKind.RADIO, question="Are you a citizen?", options=("Yes", "No"))
        for profile in (FakeProfile(), FakeProfile({"identity.citizenship": fact("Yes", "identity.citizenship", verified=False)})):
            provider = FakeProvider([provider_answer("Yes")])
            result = AnswerResolver().resolve(target, profile, provider)
            self.assertEqual(result.status, AnswerStatus.UNRESOLVED)
            self.assertEqual(provider.requests, [])

    def test_verified_profile_preset_precedes_provider_for_ordinary_field(self):
        target = field(FieldKind.TEXT, profile_key="preferences.location")
        profile = FakeProfile({"preferences.location": fact("Madrid", "preferences.location")})
        provider = FakeProvider([provider_answer("Barcelona")])
        result = AnswerResolver().resolve(target, profile, provider)
        self.assertEqual(result.value, "Madrid")
        self.assertEqual(result.source, AnswerSource.PROFILE)
        self.assertEqual(provider.requests, [])

    def test_ordinary_text_select_and_radio_reach_provider(self):
        cases = (
            field(FieldKind.TEXT, key="text"),
            field(FieldKind.SELECT, key="select", options=("Remote", "Hybrid")),
            field(FieldKind.RADIO, key="radio", options=("Yes", "No")),
        )
        for target, value in zip(cases, ("Answer", "Remote", "No")):
            with self.subTest(kind=target.kind):
                provider = FakeProvider([provider_answer(value)])
                result = AnswerResolver().resolve(target, self.profile, provider)
                self.assertEqual(result.source, AnswerSource.PROVIDER)
                self.assertTrue(result.requires_review)
                self.assertEqual(len(provider.requests), 1)

    def test_low_confidence_provider_answer_is_accepted_for_review(self):
        provider = FakeProvider([provider_answer("Tentative", confidence=Confidence.LOW, reason="provider_uncertain")])
        result = AnswerResolver().resolve(field(FieldKind.TEXT), self.profile, provider)
        self.assertEqual(result.status, AnswerStatus.RESOLVED)
        self.assertEqual(result.confidence, Confidence.LOW)
        self.assertTrue(result.requires_review)

    def test_provider_failure_uses_eligible_yes_fallback(self):
        for question in (
            "Are you comfortable with Python?",
            "Do you prefer remote work?",
        ):
            with self.subTest(question=question):
                target = field(FieldKind.RADIO, question=question, options=("Sí", "No"))
                provider = FakeProvider([RuntimeError("offline failure")])
                result = AnswerResolver().resolve(target, self.profile, provider)
                self.assertEqual(result.value, "Sí")
                self.assertEqual(result.source, AnswerSource.DEFAULT)
                self.assertTrue(result.requires_review)

    def test_number_is_constrained_and_boolean_is_rejected(self):
        constraints = FieldConstraints(min_value=Decimal("2"), max_value=Decimal("8"), step=Decimal("2"))
        target = field(FieldKind.NUMBER, constraints=constraints)
        constrained = AnswerResolver().resolve(target, self.profile, FakeProvider([provider_answer("9")]))
        boolean = AnswerResolver().resolve(target, self.profile, FakeProvider([provider_answer(True)]))
        self.assertEqual(constrained.value, "8")
        self.assertEqual(constrained.source, AnswerSource.PROVIDER)
        self.assertTrue(constrained.requires_review)
        self.assertEqual(boolean.value, "2")
        self.assertEqual(boolean.source, AnswerSource.DEFAULT)

    def test_provider_text_is_repaired_to_length_constraints(self):
        constraints = FieldConstraints(min_length=8, max_length=12)
        result = AnswerResolver().resolve(
            field(FieldKind.TEXT, constraints=constraints),
            self.profile,
            FakeProvider([provider_answer("Short")]),
        )
        self.assertGreaterEqual(len(result.value), 8)
        self.assertLessEqual(len(result.value), 12)

    def test_optional_marketing_is_declined_by_policy_without_provider(self):
        target = field(FieldKind.CHECKBOX, question="Receive promotional marketing messages", required=False)
        provider = FakeProvider([provider_answer(True)])
        result = AnswerResolver().resolve(target, self.profile, provider)
        self.assertIs(result.value, False)
        self.assertEqual(result.source, AnswerSource.POLICY)
        self.assertEqual(provider.requests, [])

    def test_required_procedural_ack_is_explicit_policy_answer(self):
        target = field(FieldKind.CHECKBOX, question="I confirm the information is complete", required=True)
        result = AnswerResolver().resolve(target, self.profile, None)
        self.assertIs(result.value, True)
        self.assertEqual(result.source, AnswerSource.POLICY)

    def test_legal_acknowledgement_is_not_guessed(self):
        target = field(FieldKind.CHECKBOX, question="I declare I have no criminal convictions", required=True)
        provider = FakeProvider([provider_answer(True)])
        result = AnswerResolver().resolve(target, self.profile, provider)
        self.assertEqual(result.status, AnswerStatus.UNRESOLVED)
        self.assertEqual(provider.requests, [])

    def test_provider_receives_candidate_context_and_request_count(self):
        target = field(FieldKind.TEXT, context=(("skills", "Python"),))
        provider = FakeProvider([provider_answer("Answer", requests=2)])
        result = AnswerResolver().resolve(target, self.profile, provider)
        self.assertEqual(provider.requests[0].candidate_context, (("skills", "Python"),))
        self.assertEqual(result.provider_request_count, 2)

    def test_provider_and_default_review_records_are_complete_and_once(self):
        queue = FakeReviewQueue()
        target = field(FieldKind.TEXT, question="Why this role?")
        resolver = AnswerResolver(queue)
        provider = FakeProvider([provider_answer("Because it fits", confidence=Confidence.LOW, requests=1)])
        first = resolver.resolve(target, self.profile, provider)
        second = resolver.resolve(target, self.profile, provider)
        self.assertEqual(first, second)
        self.assertEqual(len(provider.requests), 1)
        self.assertEqual(len(queue.records), 1)
        record = queue.records[0]
        self.assertEqual(record.job_id, "job-123")
        self.assertEqual(record.company, "Example Company")
        self.assertEqual(record.job_title, "Example Role")
        self.assertEqual(record.original_question, "Why this role?")
        self.assertEqual(record.normalized_question, "why this role")
        self.assertEqual(record.final_answer, "Because it fits")
        self.assertEqual(record.confidence, Confidence.LOW)
        self.assertTrue(record.requires_review)
        self.assertEqual(record.as_excel_row()["final_answer"], "Because it fits")


class ValidationRepairTests(unittest.TestCase):
    def setUp(self):
        self.profile = FakeProfile()

    def test_validation_models_are_immutable_and_kinds_complete(self):
        target = field(FieldKind.TEXT)
        issue = repair_request(target, ValidationIssueKind.TEXT_TOO_SHORT, "Hi").validation_issue
        with self.assertRaises(FrozenInstanceError):
            issue.message = "changed"
        required = {"MISSING_VALUE", "WRONG_TYPE", "BELOW_MINIMUM", "ABOVE_MAXIMUM", "STEP_MISMATCH", "TEXT_TOO_SHORT", "TEXT_TOO_LONG", "OPTION_REQUIRED", "OPTION_NOT_AVAILABLE", "INVALID_FORMAT", "UNKNOWN_VALIDATION_ERROR"}
        self.assertTrue(required.issubset(ValidationIssueKind.__members__))

    def test_text_too_short_repaired_to_minimum_length(self):
        target = field(FieldKind.TEXT, constraints=FieldConstraints(min_length=5, max_length=20))
        result = AnswerResolver().repair(repair_request(target, ValidationIssueKind.TEXT_TOO_SHORT, "Hi"), self.profile, None)
        self.assertEqual(result.status, RepairStatus.REPAIRED)
        self.assertGreaterEqual(len(result.answer_result.value), 5)
        self.assertEqual(result.answer_result.source, AnswerSource.POLICY)

    def test_text_too_long_repaired_below_maximum_length(self):
        target = field(FieldKind.TEXTAREA, constraints=FieldConstraints(max_length=5))
        result = AnswerResolver().repair(repair_request(target, ValidationIssueKind.TEXT_TOO_LONG, "abcdefgh"), self.profile, None)
        self.assertEqual(result.answer_result.value, "abcde")

    def test_invalid_number_repaired_to_min_max_step_compatible_value(self):
        constraints = FieldConstraints(min_value=Decimal("1"), max_value=Decimal("10"), step=Decimal("2"))
        target = field(FieldKind.NUMBER, constraints=constraints)
        result = AnswerResolver().repair(repair_request(target, ValidationIssueKind.ABOVE_MAXIMUM, "12"), self.profile, None)
        value = Decimal(result.answer_result.value)
        self.assertGreaterEqual(value, constraints.min_value)
        self.assertLessEqual(value, constraints.max_value)
        self.assertEqual((value - constraints.min_value) % constraints.step, Decimal("0"))

    def test_nonnumeric_provider_result_is_rejected_and_repaired(self):
        constraints = FieldConstraints(min_value=Decimal("2"), max_value=Decimal("10"), step=Decimal("2"))
        target = field(FieldKind.NUMBER, constraints=constraints)
        queue = FakeReviewQueue()
        result = AnswerResolver(queue).repair(
            repair_request(target, ValidationIssueKind.WRONG_TYPE, "not-a-number", attempt=2),
            self.profile,
            FakeProvider([provider_answer("many")]),
        )
        self.assertEqual(result.answer_result.value, "2")
        self.assertEqual(result.answer_result.source, AnswerSource.DEFAULT)
        self.assertEqual(len(queue.records), 1)

    def test_ungrounded_numeric_failure_does_not_invent_zero(self):
        target = field(FieldKind.NUMBER)
        result = AnswerResolver().repair(
            repair_request(target, ValidationIssueKind.WRONG_TYPE, "invalid", attempt=2),
            self.profile,
            FakeProvider([provider_answer("many")]),
        )
        self.assertEqual(result.status, RepairStatus.UNRESOLVED)

    def test_missing_select_maps_to_actual_visible_option(self):
        target = field(FieldKind.SELECT, options=("Select an option", "Remote"))
        result = AnswerResolver().repair(repair_request(target, ValidationIssueKind.OPTION_REQUIRED, ""), self.profile, None)
        self.assertEqual(result.answer_result.value, "Remote")
        self.assertIn(result.answer_result.value, target.visible_options)

    def test_unavailable_option_re_resolves_using_current_options(self):
        target = field(FieldKind.RADIO, options=("Remote", "Hybrid"))
        provider = FakeProvider([provider_answer("Hybrid")])
        result = AnswerResolver().repair(
            repair_request(target, ValidationIssueKind.OPTION_NOT_AVAILABLE, "On-site", attempt=2),
            self.profile,
            provider,
        )
        self.assertEqual(result.answer_result.value, "Hybrid")
        self.assertEqual(provider.requests[0].visible_options, ("Remote", "Hybrid"))

    def test_unknown_error_sends_real_validation_context_to_provider(self):
        constraints = FieldConstraints(min_length=4, max_length=40)
        target = field(FieldKind.TEXT, constraints=constraints, context=(("skill", "Python"),))
        message = "Use the format requested by this employer"
        provider = FakeProvider([provider_answer("Valid answer")])
        result = AnswerResolver().repair(
            repair_request(target, ValidationIssueKind.UNKNOWN_VALIDATION_ERROR, "Rejected", message=message, attempt=2),
            self.profile,
            provider,
        )
        sent = provider.requests[0]
        self.assertEqual(sent.validation_message, message)
        self.assertEqual(sent.field_kind, FieldKind.TEXT)
        self.assertEqual(sent.rejected_value, "Rejected")
        self.assertEqual(sent.constraints, constraints)
        self.assertEqual(sent.candidate_context, (("skill", "Python"),))
        self.assertEqual(result.status, RepairStatus.REPAIRED)

    def test_already_valid_field_is_not_reprocessed(self):
        target = field(FieldKind.TEXT, existing="Already valid")
        previous = answer_result("Already valid")
        provider = FakeProvider([provider_answer("unused")])
        result = AnswerResolver().repair(
            repair_request(target, ValidationIssueKind.VALID, "Already valid", previous=previous),
            self.profile,
            provider,
        )
        self.assertEqual(result.status, RepairStatus.UNCHANGED)
        self.assertIs(result.answer_result, previous)
        self.assertEqual(self.profile.calls, [])
        self.assertEqual(provider.requests, [])

    def test_repeated_identical_validation_is_deduplicated_across_attempt_numbers(self):
        target = field(FieldKind.TEXT)
        provider = FakeProvider([provider_answer("Repaired answer")])
        queue = FakeReviewQueue()
        resolver = AnswerResolver(queue)
        second = repair_request(target, ValidationIssueKind.UNKNOWN_VALIDATION_ERROR, "Rejected", message="Actual error", attempt=2)
        third = RepairRequest(second.field, second.previous_answer, second.validation_issue, 3)
        resolver.repair(second, self.profile, provider)
        resolver.repair(second, self.profile, provider)
        resolver.repair(third, self.profile, provider)
        self.assertEqual(len(provider.requests), 1)
        self.assertEqual(len(queue.records), 1)

    def test_ai_and_default_final_answers_require_review(self):
        provider_result = AnswerResolver().repair(
            repair_request(field(FieldKind.TEXT), ValidationIssueKind.UNKNOWN_VALIDATION_ERROR, "Rejected", attempt=2),
            self.profile,
            FakeProvider([provider_answer("Provider answer", confidence=Confidence.LOW)]),
        )
        default_result = AnswerResolver().repair(
            repair_request(field(FieldKind.RADIO, options=("Sí", "No")), ValidationIssueKind.OPTION_REQUIRED, "", attempt=2),
            self.profile,
            FakeProvider([provider_answer(None, answered=False)]),
        )
        self.assertTrue(provider_result.requires_review)
        self.assertTrue(default_result.requires_review)
        self.assertEqual(default_result.answer_result.value, "Sí")

    def test_protected_facts_remain_verified_exact_only_during_repair(self):
        target = field(FieldKind.RADIO, question="Are you authorized to work?", options=("Yes", "No"))
        provider = FakeProvider([provider_answer("Yes")])
        missing = AnswerResolver().repair(
            repair_request(target, ValidationIssueKind.OPTION_REQUIRED, "", attempt=2),
            self.profile,
            provider,
        )
        self.assertEqual(missing.status, RepairStatus.UNRESOLVED)
        self.assertEqual(provider.requests, [])
        profile = FakeProfile({"legal.work_authorization": fact("No", "legal.work_authorization")})
        repaired = AnswerResolver().repair(
            repair_request(target, ValidationIssueKind.OPTION_REQUIRED, "", attempt=2),
            profile,
            provider,
        )
        self.assertEqual(repaired.answer_result.value, "No")
        self.assertEqual(repaired.answer_result.source, AnswerSource.PROFILE)

    def test_protected_text_is_not_padded_or_truncated(self):
        target = field(FieldKind.TEXT, exact=True, constraints=FieldConstraints(min_length=10, max_length=20))
        profile = FakeProfile({"profile.synthetic": fact("Exact", "profile.synthetic")})
        provider = FakeProvider([provider_answer("Invented replacement")])
        result = AnswerResolver().repair(
            repair_request(target, ValidationIssueKind.TEXT_TOO_SHORT, "Exact", attempt=2),
            profile,
            provider,
        )
        self.assertEqual(result.status, RepairStatus.UNRESOLVED)
        self.assertEqual(provider.requests, [])

    def test_ordinary_failure_is_retryable_not_immediately_terminal(self):
        provider = FakeProvider([provider_answer("Future answer")])
        result = AnswerResolver().repair(
            repair_request(field(FieldKind.TEXT), ValidationIssueKind.UNKNOWN_VALIDATION_ERROR, "Rejected", attempt=1),
            self.profile,
            provider,
        )
        self.assertEqual(result.status, RepairStatus.RETRY_REQUIRED)
        self.assertEqual(provider.requests, [])

    def test_missing_required_ordinary_text_gets_best_effort_valid_answer(self):
        target = field(FieldKind.TEXT, constraints=FieldConstraints(min_length=16, max_length=30))
        result = AnswerResolver().repair(
            repair_request(target, ValidationIssueKind.MISSING_VALUE, "", attempt=2),
            self.profile,
            None,
        )
        self.assertEqual(result.status, RepairStatus.REPAIRED)
        self.assertGreaterEqual(len(result.answer_result.value), 16)
        self.assertLessEqual(len(result.answer_result.value), 30)
        self.assertEqual(result.answer_result.source, AnswerSource.DEFAULT)

    def test_yes_default_can_be_disabled(self):
        target = field(FieldKind.RADIO, options=("Yes", "No"), allow_yes=False)
        result = AnswerResolver().repair(
            repair_request(target, ValidationIssueKind.OPTION_REQUIRED, "", attempt=2),
            self.profile,
            None,
        )
        self.assertEqual(result.status, RepairStatus.UNRESOLVED)

    def test_domain_layer_has_no_browser_or_selenium_dependency(self):
        source = "\n".join(
            inspect.getsource(module).casefold()
            for module in (resolver_module, policies_module, provider_module)
        )
        self.assertNotIn("selenium", source)
        self.assertNotIn("webdriver", source)
        self.assertNotIn("driver.", source)
        self.assertNotIn("submit application", source)


if __name__ == "__main__":
    unittest.main()
