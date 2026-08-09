import contextlib
import csv
from datetime import datetime
import io
from pathlib import Path
import tempfile
import unittest

from modules.ai.answer_review_queue import AIAnswerReviewQueue, CSV_COLUMNS


class AnswerReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "logs" / "ai_answer_review"
        self.now = lambda: datetime(2026, 7, 25, 12, 34, 56)

    def tearDown(self):
        self.temp_dir.cleanup()

    def queue(self, **kwargs):
        return AIAnswerReviewQueue(
            root=self.root,
            run_id=kwargs.pop("run_id", "synthetic-run"),
            now=self.now,
            **kwargs,
        )

    @staticmethod
    def rows(queue):
        with queue.path.open(encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))

    def record_answer(self, queue, **overrides):
        values = {
            "job_id": "job-1",
            "company": "Synthetic company",
            "job_title": "Synthetic role",
            "question": "Synthetic application question",
            "field_type": "text",
            "required": True,
            "visible_options": [],
            "proposed_answer": "Supported positive answer",
            "reason_code": "grounded_ai_answer",
            "provider_request_count": 1,
            "validation_result": "valid",
            "application_outcome": "answer_filled",
        }
        values.update(overrides)
        return queue.record_answer(**values)

    def test_csv_schema_and_initial_review_fields(self):
        queue = self.queue()
        self.assertTrue(self.record_answer(queue))
        row = self.rows(queue)[0]
        self.assertEqual(tuple(row), CSV_COLUMNS)
        self.assertEqual(row["visible_options"], "[]")
        self.assertEqual(row["review_status"], "pending")
        for field in (
            "corrected_answer",
            "profile_key",
            "profile_action",
            "reviewer_notes",
        ):
            self.assertEqual(row[field], "")
        queue.close()

    def test_observed_zero_year_and_project_answers_are_high_priority(self):
        questions = (
            "eCommerce digital-product Business Analyst years",
            "Number of eCommerce omnichannel Agile projects",
            "Data Governance years",
            "DAMA years",
        )
        queue = self.queue()
        for question in questions:
            self.record_answer(
                queue,
                question=question,
                field_type="number",
                proposed_answer="0",
            )
        rows = self.rows(queue)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["review_priority"] == "high" for row in rows))
        self.assertTrue(all(row["provider_request_count"] == "1" for row in rows))
        queue.close()

    def test_positive_and_stronger_language_answers_remain_normal(self):
        queue = self.queue()
        self.record_answer(queue)
        self.record_answer(
            queue,
            question="Select your language level",
            field_type="select",
            visible_options=["Basic", "Professional", "Fluent"],
            proposed_answer="Fluent",
            reason_code="semantic_confirmed_fact",
        )
        rows = self.rows(queue)
        self.assertEqual(
            [row["review_priority"] for row in rows],
            ["normal", "normal"],
        )
        queue.close()

    def test_repaired_answer_is_recorded_and_exact_fact_conflict_is_high(self):
        queue = self.queue()
        self.record_answer(
            queue,
            proposed_answer="Corrected provider answer",
            provider_request_count=2,
        )
        self.record_answer(
            queue,
            proposed_answer="Conflicting answer",
            conflicts_with_verified_fact=True,
        )
        rows = self.rows(queue)
        self.assertEqual(rows[0]["provider_request_count"], "2")
        self.assertEqual(rows[0]["review_priority"], "normal")
        self.assertEqual(rows[1]["review_priority"], "high")
        queue.close()

    def test_successful_numeric_normalization_is_normal_priority(self):
        queue = self.queue()
        self.record_answer(
            queue,
            question="Expected hourly rate",
            field_type="number",
            proposed_answer="15.38",
            reason_code="numeric_input_normalized",
            reviewer_notes="original_proposed_answer=EUR 15.38",
        )
        row = self.rows(queue)[0]
        self.assertEqual(row["proposed_answer"], "15.38")
        self.assertEqual(row["reason_code"], "numeric_input_normalized")
        self.assertEqual(row["review_priority"], "normal")
        self.assertEqual(
            row["reviewer_notes"],
            "original_proposed_answer=EUR 15.38",
        )
        queue.close()

    def test_language_scale_and_stale_override_repairs_are_recorded_normal(self):
        queue = self.queue()
        self.record_answer(
            queue,
            question="Language level (1-5)",
            field_type="number",
            proposed_answer="3",
            reason_code="language_level_numeric_scale",
            provider_request_count=0,
            record_without_provider=True,
            reviewer_notes="original_answer=Conversational; validation_category=numeric_validation_message",
        )
        self.record_answer(
            queue,
            question="Catalan proficiency level",
            field_type="select",
            visible_options=["None", "Native or bilingual"],
            proposed_answer="None",
            reason_code="stale_preserved_value_overridden",
            provider_request_count=0,
            record_without_provider=True,
            reviewer_notes="original_answer=Native or bilingual; validation_category=verified_fact_conflict",
        )
        rows = self.rows(queue)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["review_priority"] == "normal" for row in rows))
        self.assertEqual(rows[0]["proposed_answer"], "3")
        self.assertEqual(rows[1]["proposed_answer"], "None")
        queue.close()

    def test_failed_invalid_field_repair_is_high_priority(self):
        queue = self.queue()
        self.record_answer(
            queue,
            question="Required numeric level",
            field_type="number",
            proposed_answer="",
            reason_code="invalid_field_repair_failed",
            provider_request_count=1,
            validation_result="validation_failed",
            application_outcome="validation_failed",
            force_high_priority=True,
        )
        row = self.rows(queue)[0]
        self.assertEqual(row["review_priority"], "high")
        self.assertEqual(row["reason_code"], "invalid_field_repair_failed")
        queue.close()

    def test_experience_override_and_threshold_default_are_recorded(self):
        queue = self.queue()
        for reason in (
            "stale_preserved_experience_overridden",
            "ordinary_experience_yes_default",
        ):
            self.record_answer(
                queue,
                question="Synthetic experience threshold question",
                field_type="radio",
                visible_options=["Yes", "No"],
                proposed_answer="Yes",
                reason_code=reason,
                provider_request_count=0,
                record_without_provider=True,
                reviewer_notes="original_answer=No",
            )
        rows = self.rows(queue)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["review_priority"] == "normal" for row in rows))
        queue.close()

    def test_resume_confirmation_and_unconfirmed_attachment_are_prioritized(self):
        queue = self.queue()
        self.record_answer(
            queue,
            question="Attach your resume confirmation",
            field_type="select",
            visible_options=["Yes", "No"],
            proposed_answer="Yes",
            reason_code="resume_attachment_confirmed",
            provider_request_count=0,
            record_without_provider=True,
        )
        queue.record_required_event(
            question="Attach your resume confirmation",
            field_type="select",
            visible_options=["Yes", "No"],
            reason_code="resume_attachment_not_confirmed",
        )
        rows = self.rows(queue)
        self.assertEqual(rows[0]["provider_request_count"], "0")
        self.assertEqual(rows[0]["application_outcome"], "answer_filled")
        self.assertEqual(rows[0]["review_priority"], "normal")
        self.assertEqual(
            rows[1]["application_outcome"], "unresolved_required"
        )
        self.assertEqual(rows[1]["review_priority"], "high")
        queue.close()

    def test_salary_range_acceptance_and_numeric_repair_are_normal_priority(self):
        queue = self.queue()
        self.record_answer(
            queue,
            question="Offered annual salary range acceptance",
            field_type="radio",
            visible_options=["Yes", "No"],
            proposed_answer="Yes",
            reason_code="salary_range_accepted_from_expected_salary",
            provider_request_count=0,
            record_without_provider=True,
            reviewer_notes=(
                "offered_annual_range_eur=35000-41000; "
                "expected_annual_salary_eur=32000"
            ),
        )
        self.record_answer(
            queue,
            question="Expected annual salary",
            field_type="number",
            proposed_answer="32000",
            reason_code="numeric_input_normalized",
            provider_request_count=1,
            validation_result="valid_after_repair",
            application_outcome="answer_filled",
            reviewer_notes="original_answer=32000 EUR annual",
        )
        rows = self.rows(queue)
        self.assertEqual(rows[0]["provider_request_count"], "0")
        self.assertEqual(rows[0]["review_priority"], "normal")
        self.assertIn("offered_annual_range_eur", rows[0]["reviewer_notes"])
        self.assertEqual(rows[1]["provider_request_count"], "1")
        self.assertEqual(rows[1]["validation_result"], "valid_after_repair")
        self.assertEqual(rows[1]["review_priority"], "normal")
        queue.close()

    def test_safety_skip_and_submit_detected_review_are_standalone_events(self):
        queue = self.queue()
        self.assertTrue(queue.record_outcome(
            "safety_warning_skipped",
            job_id="job-1",
            company="Synthetic company",
            job_title="Synthetic role",
            reason_code="job_search_safety_reminder",
        ))
        self.assertTrue(queue.record_outcome(
            "reached_review",
            job_id="job-2",
            company="Synthetic company",
            job_title="Synthetic role",
            reason_code="final_review_detected_from_submit_button",
        ))
        rows = self.rows(queue)
        self.assertEqual(rows[0]["application_outcome"], "safety_warning_skipped")
        self.assertEqual(rows[0]["review_priority"], "high")
        self.assertEqual(
            rows[1]["reason_code"],
            "final_review_detected_from_submit_button",
        )
        self.assertEqual(rows[1]["review_priority"], "normal")
        queue.close()

    def test_required_unresolved_and_invalid_day_rate_are_high_priority(self):
        queue = self.queue()
        queue.record_required_event(
            question="Freelancer availability",
            field_type="select",
            visible_options=["Select an option"],
            reason_code="invalid_option",
        )
        queue.record_required_event(
            question="Day rate",
            field_type="number",
            visible_options=[],
            reason_code="empty_answer",
            validation_result="validation_failed",
            application_outcome="validation_failed",
        )
        self.record_answer(
            queue,
            question="Day rate greater than zero",
            field_type="number",
            proposed_answer="invalid-decimal",
            reason_code="invalid_number",
            validation_result="validation_failed",
            application_outcome="validation_failed",
        )
        rows = self.rows(queue)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["review_priority"] == "high" for row in rows))
        queue.close()

    def test_zero_request_and_preserved_values_are_not_recorded(self):
        queue = self.queue()
        for question, answer in (
            ("Microsoft Excel years", "7"),
            ("Python years", "4"),
            ("SQL years", "5"),
            ("Azure SQL years", "4"),
        ):
            self.assertFalse(self.record_answer(
                queue,
                question=question,
                field_type="number",
                proposed_answer=answer,
                provider_request_count=0,
            ))
        self.assertEqual(self.rows(queue), [])
        queue.close()

    def test_policy_answers_are_recorded_without_provider_requests(self):
        queue = self.queue()
        self.assertTrue(self.record_answer(
            queue,
            question="Do you have experience with a new capability?",
            field_type="radio",
            visible_options=["Yes", "No"],
            proposed_answer="Yes",
            reason_code="ordinary_experience_yes_default",
            provider_request_count=0,
            record_without_provider=True,
        ))
        self.assertTrue(self.record_answer(
            queue,
            question="How many years of experience do you have with a new capability?",
            field_type="number",
            proposed_answer="1",
            reason_code="experience_years_minimum_floor",
            provider_request_count=0,
            record_without_provider=True,
            force_high_priority=True,
            reviewer_notes="original_proposed_answer=0",
        ))
        rows = self.rows(queue)
        self.assertEqual(rows[0]["review_priority"], "normal")
        self.assertEqual(rows[0]["provider_request_count"], "0")
        self.assertEqual(rows[1]["proposed_answer"], "1")
        self.assertEqual(rows[1]["review_priority"], "high")
        self.assertEqual(
            rows[1]["reviewer_notes"],
            "original_proposed_answer=0",
        )
        queue.close()

    def test_yes_default_and_gemini_answers_are_written_once_per_field(self):
        queue = self.queue()
        ordinary = {
            "question": "Do you know an unfamiliar planning tool?",
            "field_type": "radio",
            "visible_options": ["Yes", "No"],
            "proposed_answer": "Yes",
            "reason_code": "ordinary_experience_yes_default",
            "provider_request_count": 0,
            "record_without_provider": True,
        }
        self.assertTrue(self.record_answer(queue, **ordinary))
        self.assertFalse(self.record_answer(queue, **ordinary))
        self.assertTrue(self.record_answer(
            queue,
            question="Describe your working style",
            proposed_answer="Collaborative",
            reason_code="grounded_ai_answer",
            provider_request_count=1,
        ))

        rows = self.rows(queue)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["reason_code"], "ordinary_experience_yes_default")
        self.assertEqual(rows[0]["review_status"], "pending")
        self.assertEqual(rows[0]["corrected_answer"], "")
        self.assertEqual(rows[1]["reason_code"], "grounded_ai_answer")
        queue.close()

    def test_analyst_floor_and_french_language_mapping_are_recorded(self):
        queue = self.queue()
        self.record_answer(
            queue,
            question="Synthetic Business Analyst years question",
            field_type="number",
            proposed_answer="3",
            reason_code="analyst_role_years_minimum_floor",
            provider_request_count=0,
            record_without_provider=True,
            reviewer_notes="original_proposed_answer=1",
        )
        self.record_answer(
            queue,
            question="Synthetic localized English level question",
            field_type="select",
            visible_options=["Inexistant", "Natif ou bilingue"],
            proposed_answer="Natif ou bilingue",
            reason_code="localized_language_exact_fact",
            provider_request_count=0,
            record_without_provider=True,
        )
        rows = self.rows(queue)
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[0]["reason_code"], "analyst_role_years_minimum_floor"
        )
        self.assertEqual(rows[0]["proposed_answer"], "3")
        self.assertEqual(rows[0]["provider_request_count"], "0")
        self.assertEqual(
            rows[1]["reason_code"], "localized_language_exact_fact"
        )
        self.assertEqual(rows[1]["review_priority"], "normal")
        queue.close()

    def test_multilingual_provider_numeric_and_failure_rows_are_recorded(self):
        queue = self.queue()
        self.record_answer(
            queue,
            question="Synthetic multilingual select question",
            field_type="select",
            visible_options=["Low", "High"],
            proposed_answer="High",
            reason_code="multilingual_language_provider_mapping",
            provider_request_count=1,
            reviewer_notes="target_language=english",
        )
        self.record_answer(
            queue,
            question="Synthetic multilingual numeric question",
            field_type="number",
            proposed_answer="8",
            reason_code="multilingual_language_numeric_scale",
            provider_request_count=1,
            reviewer_notes="target_language=japanese",
        )
        self.record_answer(
            queue,
            question="Synthetic unresolved language question",
            field_type="select",
            visible_options=["Low", "High"],
            proposed_answer="",
            reason_code="multilingual_language_mapping_failed",
            provider_request_count=2,
            validation_result="validation_failed",
            application_outcome="unresolved_required",
            reviewer_notes="target_language=german",
        )
        rows = self.rows(queue)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["review_priority"], "normal")
        self.assertEqual(rows[1]["proposed_answer"], "8")
        self.assertEqual(rows[2]["review_priority"], "high")
        self.assertEqual(rows[2]["provider_request_count"], "2")
        self.assertTrue(all("target_language=" in row["reviewer_notes"] for row in rows))
        queue.close()

    def test_rows_survive_a_simulated_exception(self):
        queue = self.queue()
        try:
            self.record_answer(queue, proposed_answer="Durable answer")
            raise RuntimeError("synthetic browser exception")
        except RuntimeError:
            pass
        self.assertTrue(queue.record_run_interrupted())
        rows = self.rows(queue)
        self.assertEqual(rows[0]["proposed_answer"], "Durable answer")
        self.assertEqual(rows[-1]["application_outcome"], "run_interrupted")
        queue.close()

    def test_logger_initialization_failure_is_fail_open(self):
        def failing_opener(*_args, **_kwargs):
            raise OSError("synthetic failure")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            queue = self.queue(opener=failing_opener)
            recorded = self.record_answer(queue)
        self.assertFalse(queue.enabled)
        self.assertFalse(recorded)
        self.assertIn("browser workflow continues", output.getvalue())

    def test_provider_routed_contact_is_fully_redacted(self):
        queue = self.queue()
        self.record_answer(
            queue,
            question="Email address",
            proposed_answer="person@example.invalid",
            visible_options=["person@example.invalid"],
        )
        row = self.rows(queue)[0]
        self.assertEqual(row["question"], "[redacted-contact-question]")
        self.assertEqual(row["proposed_answer"], "[redacted]")
        self.assertEqual(row["visible_options_json"], "[]")
        contents = queue.path.read_text(encoding="utf-8")
        self.assertNotIn("person@example.invalid", contents)
        self.assertNotIn("prompt", CSV_COLUMNS)
        self.assertNotIn("raw_response", CSV_COLUMNS)
        self.assertNotIn("candidate_profile", CSV_COLUMNS)
        queue.close()

    def test_outcome_events_are_appended_only_for_logged_applications(self):
        queue = self.queue()
        self.assertFalse(queue.record_outcome(
            "submitted",
            job_id="job-unknown",
            company="Synthetic company",
            job_title="Synthetic role",
        ))
        self.record_answer(queue)
        self.assertTrue(queue.record_outcome(
            "reached_review",
            job_id="job-1",
            company="Synthetic company",
            job_title="Synthetic role",
        ))
        self.assertTrue(queue.record_outcome(
            "submitted",
            job_id="job-1",
            company="Synthetic company",
            job_title="Synthetic role",
        ))
        self.record_answer(queue, job_id="job-2")
        self.assertTrue(queue.record_outcome(
            "application_discarded",
            job_id="job-2",
            company="Synthetic company",
            job_title="Synthetic role",
            reason_code="required_answer_unavailable",
        ))
        self.assertEqual(
            [row["application_outcome"] for row in self.rows(queue)],
            [
                "answer_filled",
                "reached_review",
                "submitted",
                "answer_filled",
                "application_discarded",
            ],
        )
        self.assertEqual(self.rows(queue)[-1]["review_priority"], "high")
        queue.close()

    def test_failed_question_discard_is_standalone_and_flushed(self):
        queue = self.queue()
        self.assertTrue(queue.record_outcome(
            "application_discarded",
            job_id="job-unresolved",
            company="Synthetic company",
            job_title="Synthetic role",
            reason_code="failed_question_unresolved",
        ))
        rows = self.rows(queue)
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["application_outcome"], "application_discarded"
        )
        self.assertEqual(rows[0]["reason_code"], "failed_question_unresolved")
        self.assertEqual(rows[0]["review_priority"], "high")
        queue.close()

    def test_modal_cleanup_failure_is_standalone_and_sanitized(self):
        queue = self.queue()
        self.assertTrue(queue.record_outcome(
            "application_discarded",
            job_id="job-cleanup",
            company="Synthetic company",
            job_title="Synthetic role",
            reason_code="easy_apply_modal_cleanup_failed",
        ))
        rows = self.rows(queue)
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["reason_code"], "easy_apply_modal_cleanup_failed"
        )
        self.assertEqual(rows[0]["application_outcome"], "application_discarded")
        self.assertEqual(rows[0]["review_priority"], "high")
        self.assertEqual(rows[0]["question"], "")
        self.assertEqual(rows[0]["visible_options_json"], "[]")
        self.assertEqual(rows[0]["proposed_answer"], "")
        queue.close()

    def test_successful_modal_close_requires_existing_application_event(self):
        queue = self.queue()
        self.assertFalse(queue.record_outcome(
            "application_discarded",
            job_id="job-cleanup",
            company="Synthetic company",
            job_title="Synthetic role",
            reason_code="easy_apply_modal_closed",
        ))
        self.record_answer(
            queue,
            job_id="job-cleanup",
            company="Synthetic company",
            job_title="Synthetic role",
        )
        self.assertTrue(queue.record_outcome(
            "application_discarded",
            job_id="job-cleanup",
            company="Synthetic company",
            job_title="Synthetic role",
            reason_code="easy_apply_modal_closed",
        ))
        rows = self.rows(queue)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]["reason_code"], "easy_apply_modal_closed")
        queue.close()

    def test_unresolved_citizenship_records_automatic_discard_not_save(self):
        queue = self.queue()
        self.assertTrue(queue.record_required_event(
            job_id="job-citizenship",
            company="Synthetic company",
            job_title="Synthetic role",
            question="Do you hold a European Citizenship?",
            field_type="radio",
            visible_options=["Yes", "No"],
            reason_code="high_risk_exact_fact_missing",
        ))
        self.assertTrue(queue.record_outcome(
            "application_discarded",
            job_id="job-citizenship",
            company="Synthetic company",
            job_title="Synthetic role",
            reason_code="easy_apply_application_discarded",
        ))
        rows = self.rows(queue)
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[0]["reason_code"], "high_risk_exact_fact_missing"
        )
        self.assertEqual(
            rows[1]["reason_code"], "easy_apply_application_discarded"
        )
        self.assertNotIn("save", rows[1]["reason_code"].casefold())
        queue.close()

    def test_verified_citizenship_no_is_normal_priority_without_provider(self):
        queue = self.queue()
        self.assertTrue(self.record_answer(
            queue,
            question="Do you hold European citizenship?",
            field_type="radio",
            visible_options=["Yes", "No"],
            proposed_answer="No",
            reason_code="exact_profile_fact",
            provider_request_count=0,
            record_without_provider=True,
            force_normal_priority=True,
        ))
        row = self.rows(queue)[0]
        self.assertEqual(row["reason_code"], "exact_profile_fact")
        self.assertEqual(row["provider_request_count"], "0")
        self.assertEqual(row["validation_result"], "valid")
        self.assertEqual(row["review_priority"], "normal")
        queue.close()

    def test_summary_is_aggregate_only_and_profile_is_never_modified(self):
        profile_path = (
            Path(__file__).resolve().parents[1]
            / "config"
            / "candidate_profile.json"
        )
        before = profile_path.read_bytes()
        queue = self.queue()
        self.record_answer(
            queue,
            question="Sensitive synthetic question",
            proposed_answer="Sensitive synthetic answer",
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            queue.print_summary()
        summary = output.getvalue()
        self.assertIn("Provider-backed answers: 1", summary)
        self.assertIn("Review file:", summary)
        self.assertNotIn("Sensitive synthetic question", summary)
        self.assertNotIn("Sensitive synthetic answer", summary)
        queue.close()
        self.assertEqual(profile_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
