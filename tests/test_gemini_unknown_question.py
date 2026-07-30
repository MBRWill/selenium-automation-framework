import contextlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from modules.ai import gemini_unknown_question as gemini


def response(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class StatusError(Exception):
    def __init__(self, status_code):
        super().__init__("sanitized provider failure")
        self.status_code = status_code


class FakeCompletions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return response(outcome)


class FakeClient:
    def __init__(self, outcomes):
        self.chat = SimpleNamespace(completions=FakeCompletions(outcomes))


class GeminiUnknownQuestionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.profile_path = Path(self.temp_dir.name) / "candidate_profile.json"
        self.profile = {
            "application_summary": {
                "text": "Synthetic candidate summary.",
                "verified": True,
                "evidence_id": "summary",
            },
            "skills": [
                {"name": "Microsoft Excel", "years_experience": 7, "present": True, "verified": True, "evidence_id": "skill.excel"},
                {"name": "Python", "years_experience": 4, "present": True, "verified": True, "evidence_id": "skill.python"},
                {"name": "Power BI", "years_experience": 3, "present": True, "verified": True, "evidence_id": "skill.power_bi"},
                {"name": "Microsoft Azure", "years_experience": 2, "present": True, "verified": True, "evidence_id": "skill.microsoft_azure"},
                {"name": "Data Modeling", "years_experience": 5, "present": True, "verified": True, "evidence_id": "skill.data_modeling"},
                {"name": "Consulting", "years_experience": 5, "present": True, "verified": True, "evidence_id": "skill.consulting"},
                {"name": "SQL", "years_experience": 5, "present": True, "verified": True, "evidence_id": "skill.sql"},
                {"name": "Azure SQL", "years_experience": 4, "present": True, "verified": True, "evidence_id": "skill.azure_sql"},
                {"name": "Financial Analysis", "years_experience": 3, "present": True, "verified": True, "evidence_id": "skill.financial_analysis"},
                {"name": "Cross-functional work", "years_experience": None, "present": True, "verified": True, "evidence_id": "skill.cross_functional"},
                {"name": "Process improvement", "years_experience": None, "present": True, "verified": True, "evidence_id": "skill.process_improvement"},
                {"name": "Project coordination", "years_experience": None, "present": True, "verified": True, "evidence_id": "skill.project_coordination"},
                {"name": "Power BI and Advanced Excel", "years_experience": None, "present": True, "verified": True, "evidence_id": "skill.power_bi_advanced_excel"},
                {"name": "SAP Procurement / Ariba / MM", "years_experience": None, "present": False, "verified": True, "evidence_id": "skill.sap_procurement"},
            ],
            "work_experience": [
                {
                    "role": "Synthetic role",
                    "employer": "Synthetic employer",
                    "summary": "Used Python.",
                    "verified": True,
                    "evidence_id": "work",
                }
            ],
            "projects": [],
            "citizenship": {
                "citizenship_country": "China",
                "nationality": "Chinese",
                "eu_citizenship": False,
                "verified": True,
                "evidence_id": "citizenship.synthetic",
            },
            "work_authorization": [
                {
                    "country": "Spain",
                    "authorized": True,
                    "verified": True,
                    "evidence_id": "auth",
                }
            ],
            "sponsorship": [
                {"country": "Spain", "required": False, "verified": True}
            ],
            "salary_expectations": {
                "amount": 32000,
                "currency": "EUR",
                "period": "year",
                "verified": True,
            },
            "availability": {
                "earliest_start_date": "Synthetic availability",
                "notice_period_days": 30,
                "verified": True,
            },
            "application_preferences": {
                "willingness_to_travel": True,
                "work_arrangements": ["Hybrid"],
                "verified": True,
            },
            "languages": [
                {"language": "English", "level": "Professional", "verified": True},
                {"language": "Spanish", "level": "Conversational", "verified": True},
                {"language": "Catalan", "level": None, "verified": True},
            ],
        }
        self.profile_path.write_text(json.dumps(self.profile), encoding="utf-8")
        self.env = patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "synthetic-key", "GEMINI_MODEL": "synthetic-model"},
            clear=False,
        )
        self.path_patch = patch.object(gemini, "_PROFILE_PATH", self.profile_path)
        self.config_patches = [
            patch.object(gemini, "earliest_start_date", "Synthetic availability"),
            patch.object(gemini, "notice_period", 30),
        ]
        self.env.start()
        self.path_patch.start()
        for config_patch in self.config_patches:
            config_patch.start()

    def tearDown(self):
        for config_patch in reversed(self.config_patches):
            config_patch.stop()
        self.path_patch.stop()
        self.env.stop()
        self.temp_dir.cleanup()

    def call(self, outcomes, field_type="text", options=None, text_limit=None, question="Synthetic ordinary career question"):
        client = FakeClient(outcomes)
        with patch.object(gemini, "OpenAI", return_value=client):
            result = gemini.answer_unknown_question(
                question,
                field_type,
                options or [],
                "Synthetic job",
                "Synthetic description",
                text_limit,
            )
        return result, client

    def write_skills(self, skills):
        self.profile["skills"] = skills
        self.profile_path.write_text(json.dumps(self.profile), encoding="utf-8")

    def test_spanish_sql_exact_years_bypasses_gemini(self):
        self.write_skills([{"name": "SQL", "years_experience": 5, "present": True, "verified": True}])
        with patch.object(gemini, "OpenAI") as client_factory:
            result = gemini.answer_unknown_question(
                "¿Cuántos años de experiencia tienes con SQL?", "number", [], "", "", None
            )
        self.assertEqual(result.answer, "5")
        self.assertEqual(result.reason_code, "exact_skill_years")
        self.assertEqual(result.provider_request_count, 0)
        client_factory.assert_not_called()

    def test_english_sql_exact_years_bypasses_gemini(self):
        self.write_skills([{"name": "SQL", "years_experience": 5, "present": True, "verified": True}])
        with patch.object(gemini, "OpenAI") as client_factory:
            result = gemini.answer_unknown_question(
                "How many years of experience do you have with SQL?", "number", [], "", "", None
            )
        self.assertEqual(result.answer, "5")
        client_factory.assert_not_called()

    def test_all_confirmed_skill_years_bypass_gemini(self):
        cases = (
            ("How many years of experience do you have with Microsoft Excel?", "7"),
            ("How many years of experience do you have with Python?", "4"),
            ("How many years of experience do you have with Power BI?", "3"),
            ("How many years of experience do you have with Microsoft Azure?", "2"),
            ("How many years of experience do you have with Data Modeling?", "5"),
            ("How many years of consulting experience do you have?", "5"),
            ("How many years of experience do you have with SQL?", "5"),
            ("How many years of experience do you have with Azure SQL?", "4"),
            ("How many years of Financial Analysis experience do you have?", "3"),
        )
        for question, expected in cases:
            with self.subTest(question=question), patch.object(gemini, "OpenAI") as client_factory:
                result = gemini.answer_unknown_question(
                    question, "number", [], "", "", None
                )
            self.assertEqual(result.answer, expected)
            self.assertEqual(result.reason_code, "exact_skill_years")
            client_factory.assert_not_called()

    def test_experience_years_floor_applies_only_to_unknown_experience_years(self):
        for proposed in (0, ""):
            with self.subTest(proposed=proposed):
                payload = json.dumps({
                    "can_answer": True,
                    "answer": proposed,
                    "confidence": "low",
                })
                result, client = self.call(
                    [payload],
                    "number",
                    question="How many years of experience do you have with Data Governance?",
                )
                self.assertEqual(result.answer, "1")
                self.assertEqual(
                    result.reason_code,
                    "experience_years_minimum_floor",
                )
                self.assertEqual(len(client.chat.completions.calls), 1)

        with patch.object(gemini, "OpenAI") as client_factory:
            exact = gemini.answer_unknown_question(
                "How many years of experience do you have with Power BI?",
                "number",
                [],
                "",
                "",
                None,
            )
        self.assertEqual(exact.answer, "3")
        self.assertEqual(exact.reason_code, "exact_skill_years")
        client_factory.assert_not_called()

    def test_analyst_role_years_use_three_year_minimum_without_provider(self):
        questions = (
            "How many years of experience do you have as a Business Analyst?",
            "How many years have you worked as a BI Analyst?",
            "How many years of experience do you have as a Data Analyst?",
            "¿Cuántos años de experiencia tienes como Analista funcional?",
            "How many years of Procurement-focused Business Analyst experience do you have?",
        )
        for question in questions:
            with self.subTest(question=question), patch.object(
                gemini, "OpenAI"
            ) as client_factory:
                result = gemini.answer_unknown_question(
                    question,
                    "number",
                    [],
                    "Synthetic role",
                    "Synthetic description",
                    None,
                )
            self.assertEqual(result.answer, "3")
            self.assertEqual(
                result.reason_code,
                "analyst_role_years_minimum_floor",
            )
            self.assertEqual(result.provider_request_count, 0)
            client_factory.assert_not_called()

    def test_exact_analyst_role_value_above_floor_is_preserved(self):
        self.write_skills([
            {
                "name": "Business Analyst",
                "years_experience": 5,
                "present": True,
                "verified": True,
            }
        ])
        with patch.object(gemini, "OpenAI") as client_factory:
            result = gemini.answer_unknown_question(
                "How many years of experience do you have as a Business Analyst?",
                "number",
                [],
                "Synthetic role",
                "Synthetic description",
                None,
            )
        self.assertEqual(result.answer, "5")
        self.assertEqual(result.reason_code, "exact_skill_years")
        client_factory.assert_not_called()

    def test_exact_analyst_role_value_below_floor_is_raised_to_three(self):
        self.write_skills([
            {
                "name": "Business Analyst",
                "years_experience": 1,
                "present": True,
                "verified": True,
            }
        ])
        with patch.object(gemini, "OpenAI") as client_factory:
            result = gemini.answer_unknown_question(
                "How many years of experience do you have as a Business Analyst?",
                "number",
                [],
                "Synthetic role",
                "Synthetic description",
                None,
            )
        self.assertEqual(result.answer, "3")
        self.assertEqual(
            result.reason_code,
            "analyst_role_years_minimum_floor",
        )
        self.assertEqual(result.original_answer, "1")
        client_factory.assert_not_called()

    def test_analyst_job_title_does_not_raise_skill_years_floor(self):
        with patch.object(gemini, "OpenAI") as client_factory:
            result = gemini.answer_unknown_question(
                "How many years of experience do you have with BI Tools, ETL and SQL?",
                "number",
                [],
                "Business Analyst",
                "Synthetic description",
                None,
            )
        self.assertEqual(result.answer, "5")
        self.assertEqual(result.reason_code, "exact_skill_years")
        self.assertNotEqual(
            result.reason_code,
            "analyst_role_years_minimum_floor",
        )
        client_factory.assert_not_called()

    def test_java_years_keep_exact_or_generic_non_role_behavior(self):
        self.write_skills([
            {
                "name": "Java",
                "years_experience": 2,
                "present": True,
                "verified": True,
            }
        ])
        with patch.object(gemini, "OpenAI") as client_factory:
            exact = gemini.answer_unknown_question(
                "How many years of Java experience do you have?",
                "number",
                [],
                "Synthetic role",
                "Synthetic description",
                None,
            )
        self.assertEqual(exact.answer, "2")
        self.assertEqual(exact.reason_code, "exact_skill_years")
        client_factory.assert_not_called()

        self.write_skills([])
        generic = gemini.answer_deterministic_question(
            "How many years of Java experience do you have?",
            "number",
            [],
        )
        self.assertEqual(generic.answer, "1")
        self.assertEqual(
            generic.reason_code,
            "experience_years_minimum_floor",
        )

    def test_non_experience_numeric_answers_are_not_floored(self):
        projects, _ = self.call(
            ['{"can_answer":true,"answer":0,"confidence":"low"}'],
            "number",
            question="How many omnichannel Agile projects have you completed?",
        )
        self.assertEqual(projects.answer, "0")
        self.assertNotEqual(
            projects.reason_code,
            "experience_years_minimum_floor",
        )

        salary, _ = self.call(
            ['{"can_answer":true,"answer":0,"confidence":"low"}'],
            "number",
            question="What is your current salary?",
        )
        self.assertEqual(salary.answer, "0")
        self.assertNotEqual(
            salary.reason_code,
            "experience_years_minimum_floor",
        )

    def test_unknown_experience_boolean_defaults_yes_without_provider(self):
        for question, options, expected in (
            ("Do you have experience with Data Governance?", ["Yes", "No"], "Yes"),
            ("¿Tienes experiencia con gobierno de datos?", ["Sí", "No"], "Sí"),
            ("Have you worked with an unfamiliar analytics tool?", ["Oui", "Non"], "Oui"),
        ):
            with self.subTest(question=question), patch.object(gemini, "OpenAI") as client_factory:
                result = gemini.answer_unknown_question(
                    question, "radio", options, "", "", None
                )
            self.assertEqual(result.answer, expected)
            self.assertEqual(
                result.reason_code,
                "assertive_experience_yes_default",
            )
            self.assertEqual(result.provider_request_count, 0)
            client_factory.assert_not_called()

    def test_mapper_engine_and_reviewed_experience_patterns_default_yes(self):
        cases = (
            ("Have you used Mapper Engine?", ["Yes", "No"], "Yes"),
            ("¿Has utilizado Mapper Engine?", ["Sí", "No"], "Sí"),
            ("¿Has trabajado con una herramienta nueva?", ["Yes", "No"], "Yes"),
            ("¿Tienes conocimientos de una plataforma nueva?", ["Yes", "No"], "Yes"),
        )
        for question, options, expected in cases:
            with self.subTest(question=question), patch.object(gemini, "OpenAI") as client_factory:
                result = gemini.answer_unknown_question(
                    question, "radio", options, "", "", None
                )
            self.assertEqual(result.answer, expected)
            self.assertEqual(
                result.reason_code,
                "assertive_experience_yes_default",
            )
            self.assertEqual(result.provider_request_count, 0)
            client_factory.assert_not_called()

    def test_exact_negative_skill_precedes_assertive_experience_default(self):
        with patch.object(gemini, "OpenAI") as client_factory:
            result = gemini.answer_unknown_question(
                "Have you used SAP Ariba?",
                "radio",
                ["Yes", "No"],
                "",
                "",
                None,
            )
        self.assertEqual(result.answer, "No")
        self.assertEqual(result.reason_code, "exact_profile_fact")
        client_factory.assert_not_called()

    def test_threshold_experience_uses_exact_years_when_available(self):
        cases = (
            ("Do you have at least 6 years of experience with SQL?", "No"),
            ("Do you have at least 5 years of experience with SQL?", "Yes"),
            ("¿Tienes por lo menos 5 años de experiencia con SQL?", "Sí"),
        )
        for question, expected in cases:
            with self.subTest(question=question), patch.object(gemini, "OpenAI") as client_factory:
                result = gemini.answer_unknown_question(
                    question, "radio", ["Sí", "No"] if expected == "Sí" else ["Yes", "No"], "", "", None
                )
            self.assertEqual(result.answer, expected)
            self.assertEqual(result.reason_code, "exact_experience_threshold_fact")
            self.assertEqual(result.provider_request_count, 0)
            client_factory.assert_not_called()

    def test_unknown_threshold_and_domain_experience_default_yes(self):
        cases = (
            "¿Tienes al menos 3 años de experiencia como Business Analyst?",
            "¿Tiene experiencia en el sector asegurador?",
            "¿Has llevado contabilidades de empresas de forma autónoma?",
            "¿Tienes por lo menos 3 años de experiencia trabajando en asesoría o gestoría como técnico contable?",
        )
        for question in cases:
            with self.subTest(question=question), patch.object(gemini, "OpenAI") as client_factory:
                result = gemini.answer_unknown_question(
                    question, "radio", ["Yes", "No"], "", "", None
                )
            self.assertEqual(result.answer, "Yes")
            self.assertEqual(
                result.reason_code,
                "assertive_experience_threshold_yes_default"
                if "3 años" in question
                else "assertive_experience_yes_default",
            )
            self.assertEqual(result.provider_request_count, 0)
            client_factory.assert_not_called()

    def test_salary_acceptance_is_compared_and_sponsorship_stays_exact_no(self):
        salary = gemini.answer_deterministic_question(
            "Are you willing to accept a salary range of 30000 to 35000?",
            "radio",
            ["Yes", "No"],
        )
        sponsorship = gemini.answer_deterministic_question(
            "Will you require employer sponsorship?",
            "radio",
            ["Yes", "No"],
        )
        self.assertTrue(salary.can_answer)
        self.assertEqual(
            salary.reason_code,
            "salary_range_accepted_from_expected_salary",
        )
        self.assertEqual(sponsorship.answer, "No")
        self.assertEqual(sponsorship.reason_code, "exact_profile_fact")

    def test_compatible_annual_salary_ranges_are_accepted_locally(self):
        cases = (
            "Are you willing to accept the offered salary range EUR 35000 to EUR 41000?",
            "Is this salary range of 30,000–35,000 EUR acceptable?",
            "Are you comfortable with a salary of 35k–41k?",
            "¿Estás dispuesto/a a aceptar el rango salarial ofrecido entre 35–41k según experiencia aportada?",
            "¿Aceptarías un salario entre 35.000 € a 41.000 €?",
        )
        for question in cases:
            with self.subTest(question=question), patch.object(gemini, "OpenAI") as client_factory:
                result = gemini.answer_unknown_question(
                    question, "radio", ["Yes", "No"], "", "", None
                )
            self.assertEqual(result.answer, "Yes")
            self.assertEqual(
                result.reason_code,
                "salary_range_accepted_from_expected_salary",
            )
            self.assertEqual(result.provider_request_count, 0)
            self.assertIn("offered_annual_range_eur=", result.original_answer)
            self.assertIn("expected_annual_salary_eur=", result.original_answer)
            client_factory.assert_not_called()

    def test_hourly_salary_range_is_not_compared_to_annual_expectation(self):
        result = gemini.answer_deterministic_question(
            "Are you willing to accept an hourly salary range of EUR 20 to EUR 25 per hour?",
            "radio",
            ["Yes", "No"],
        )
        self.assertFalse(result.can_answer)
        self.assertNotEqual(
            result.reason_code,
            "salary_range_accepted_from_expected_salary",
        )

    def test_experience_yes_default_excludes_sensitive_or_factual_questions(self):
        for question in (
            "Do you have experience requiring employer sponsorship?",
            "Do you have a professional certification?",
            "Do you have a driving licence?",
        ):
            with self.subTest(question=question), patch.object(gemini, "OpenAI") as client_factory:
                result = gemini.answer_unknown_question(
                    question, "radio", ["Yes", "No"], "", "", None
                )
            self.assertNotEqual(
                result.reason_code,
                "assertive_experience_yes_default",
            )
            client_factory.assert_not_called()

    def test_spanish_level_and_confirmed_power_bi_capability_are_exact(self):
        for options, expected in (
            (["Basic", "Conversational", "Professional"], "Conversational"),
            (["Básico", "Conversación", "Profesional"], "Conversación"),
            (["Basic", "Intermediate", "Professional"], "Intermediate"),
        ):
            with self.subTest(options=options), patch.object(gemini, "OpenAI") as client_factory:
                result = gemini.answer_unknown_question(
                    "What is your Spanish proficiency level?",
                    "select",
                    options,
                    "",
                    "",
                    None,
                )
            self.assertEqual(result.answer, expected)
            self.assertNotIn(result.answer, {"Professional", "Profesional"})
            client_factory.assert_not_called()

        with patch.object(gemini, "OpenAI") as client_factory:
            unsupported = gemini.answer_unknown_question(
                "What is your Spanish proficiency level?",
                "select",
                ["Basic", "Professional", "Native or bilingual"],
                "",
                "",
                None,
            )
        self.assertFalse(unsupported.can_answer)
        self.assertEqual(unsupported.reason_code, "exact_option_unavailable")
        client_factory.assert_not_called()

        with patch.object(gemini, "OpenAI") as client_factory:
            capability = gemini.answer_unknown_question(
                "¿Tienes dominio de Power BI y Excel avanzado? Sí / No",
                "radio",
                ["Yes", "No"],
                "",
                "",
                None,
            )
        self.assertEqual(capability.answer, "Yes")
        self.assertEqual(capability.reason_code, "exact_profile_fact")
        client_factory.assert_not_called()

    def test_verified_language_numeric_scales_are_local_plain_digits(self):
        cases = (
            ("What is your English level? (1–5)", "5", "Professional"),
            ("What is your Spanish level? (1-5)", "3", "Conversational"),
            ("What is your Catalan level? 1 to 5", "1", "None"),
        )
        for question, expected, original in cases:
            with self.subTest(question=question), patch.object(gemini, "OpenAI") as client_factory:
                result = gemini.answer_unknown_question(
                    question, "number", [], "", "", None
                )
            self.assertEqual(result.answer, expected)
            self.assertEqual(result.original_answer, original)
            self.assertEqual(result.reason_code, "language_level_numeric_scale")
            self.assertEqual(result.provider_request_count, 0)
            client_factory.assert_not_called()

    def test_french_worded_language_questions_use_exact_target_language(self):
        french_options = [
            "Sélectionnez une option",
            "Inexistant",
            "Élémentaire",
            "Intermédiaire",
            "Professionnel",
            "Courant",
            "Natif ou bilingue",
        ]
        cases = (
            ("Quel est votre niveau en Anglais ?", "Natif ou bilingue"),
            ("Quel est votre niveau d’Anglais ?", "Natif ou bilingue"),
            ("Quel est votre niveau en Espagnol ?", "Intermédiaire"),
            ("Quel est votre niveau de Catalan ?", "Inexistant"),
        )
        for question, expected in cases:
            with self.subTest(question=question), patch.object(
                gemini, "OpenAI"
            ) as client_factory:
                result = gemini.answer_unknown_question(
                    question,
                    "select",
                    french_options,
                    "",
                    "",
                    None,
                )
            self.assertEqual(result.answer, expected)
            self.assertEqual(
                result.reason_code,
                "localized_language_exact_fact",
            )
            self.assertEqual(result.provider_request_count, 0)
            client_factory.assert_not_called()

    def test_french_target_without_exact_fact_is_not_treated_as_conflict(self):
        result = gemini.answer_verified_question(
            "Quel est votre niveau en Français ?",
            "select",
            ["Sélectionnez une option", "Inexistant", "Courant"],
        )
        self.assertFalse(result.can_answer)
        self.assertEqual(result.reason_code, "exact_fact_unavailable")

    def test_generic_multilingual_resolver_identifies_question_and_target(self):
        cases = (
            ("What is your English level?", "English"),
            ("¿Cuál es tu nivel de español?", "Spanish"),
            ("Quel est votre niveau en Anglais ?", "English"),
            ("Jaki jest Twój poziom języka angielskiego?", "English"),
            ("Wie gut sind Ihre Deutschkenntnisse?", "German"),
            ("Qual è il tuo livello di inglese?", "English"),
            ("Qual é o seu nível de espanhol?", "Spanish"),
            ("Wat is uw niveau Nederlands?", "Dutch"),
            ("英语水平如何？", "English"),
            ("日本語のレベルはどのくらいですか？", "Japanese"),
        )
        for question, target in cases:
            with self.subTest(question=question):
                payload = json.dumps({
                    "is_language_question": True,
                    "target_language": target,
                    "answer": "High",
                    "confidence": "medium",
                })
                client = FakeClient([payload])
                with patch.object(gemini, "OpenAI", return_value=client):
                    resolution = gemini.resolve_multilingual_language_question(
                        question,
                        "select",
                        ["Low", "High"],
                        True,
                        {"required": "true"},
                        profile=self.profile,
                    )
                self.assertTrue(resolution.is_language_question)
                self.assertTrue(resolution.result.can_answer)
                self.assertEqual(
                    resolution.result.target_language.casefold(),
                    target.casefold(),
                )
                self.assertEqual(resolution.result.answer, "High")
                self.assertEqual(len(client.chat.completions.calls), 1)

    def test_multilingual_payload_is_single_field_and_language_only(self):
        payload = json.dumps({
            "is_language_question": True,
            "target_language": "English",
            "answer": "High",
            "confidence": "medium",
        })
        client = FakeClient([payload])
        with patch.object(gemini, "OpenAI", return_value=client):
            resolution = gemini.resolve_multilingual_language_question(
                "Jaki jest Twój poziom języka angielskiego?",
                "select",
                ["Low", "High"],
                True,
                {"required": "true"},
                profile=self.profile,
            )
        self.assertTrue(resolution.result.can_answer)
        request = client.chat.completions.calls[0]
        prompt = request["messages"][0]["content"]
        self.assertIn("Visible options", prompt)
        self.assertIn("Confirmed language facts", prompt)
        for prohibited in (
            "Synthetic candidate summary",
            "Synthetic employer",
            "work_experience",
            "projects",
            "salary_expectations",
            "work_authorization",
            "sponsorship",
            "job description",
            "job title",
        ):
            self.assertNotIn(prohibited, prompt)

    def test_exact_language_facts_and_english_policy_precede_provider(self):
        cases = (
            (
                "What is your English level?",
                ["Basic", "Professional", "Native or bilingual"],
                "Native or bilingual",
            ),
            (
                "¿Cuál es tu nivel de español?",
                ["Basic", "Conversational", "Professional"],
                "Conversational",
            ),
            (
                "What is your Catalan level?",
                ["None", "Professional"],
                "None",
            ),
        )
        for question, options, expected in cases:
            with self.subTest(question=question), patch.object(
                gemini, "OpenAI"
            ) as client_factory:
                result = gemini.answer_unknown_question(
                    question,
                    "select",
                    options,
                    "Synthetic job",
                    "Synthetic description",
                    None,
                    required=True,
                    constraints={"required": "true"},
                )
            self.assertEqual(result.answer, expected)
            self.assertEqual(result.provider_request_count, 0)
            client_factory.assert_not_called()

    def test_provider_identification_cannot_override_known_language_policy(self):
        cases = (
            (
                "Jaki jest Twój poziom języka angielskiego?",
                "English",
                ["Basic", "Professional", "Native or bilingual"],
                "Basic",
                "Native or bilingual",
            ),
            (
                "Qual é o seu nível de espanhol?",
                "Spanish",
                ["Basic", "Conversational", "Professional"],
                "Professional",
                "Conversational",
            ),
            (
                "Wat is uw niveau Catalaans?",
                "Catalan",
                ["None", "Professional"],
                "Professional",
                "None",
            ),
        )
        for question, target, options, proposed, expected in cases:
            with self.subTest(question=question):
                client = FakeClient([json.dumps({
                    "is_language_question": True,
                    "target_language": target,
                    "answer": proposed,
                    "confidence": "high",
                })])
                with patch.object(gemini, "OpenAI", return_value=client):
                    resolution = gemini.resolve_multilingual_language_question(
                        question,
                        "select",
                        options,
                        True,
                        {"required": "true"},
                        profile=self.profile,
                    )
                self.assertEqual(resolution.result.answer, expected)
                self.assertEqual(resolution.result.provider_request_count, 1)

    def test_unfamiliar_language_uses_only_multilingual_provider_result(self):
        payload = json.dumps({
            "is_language_question": True,
            "target_language": "English",
            "answer": "Zaawansowany",
            "confidence": "medium",
        })
        client = FakeClient([payload])
        with patch.object(gemini, "OpenAI", return_value=client):
            result = gemini.answer_unknown_question(
                "Jaki jest Twój poziom języka angielskiego?",
                "select",
                ["Podstawowy", "Zaawansowany"],
                "Sensitive synthetic job title",
                "Sensitive synthetic job description",
                None,
                required=True,
                constraints={"required": "true"},
            )
        self.assertEqual(result.answer, "Zaawansowany")
        self.assertEqual(
            result.reason_code,
            "multilingual_language_provider_mapping",
        )
        self.assertEqual(result.target_language, "english")
        self.assertEqual(result.provider_request_count, 1)
        self.assertEqual(len(client.chat.completions.calls), 1)
        prompt = client.chat.completions.calls[0]["messages"][0]["content"]
        self.assertNotIn("Sensitive synthetic job title", prompt)
        self.assertNotIn("Sensitive synthetic job description", prompt)

    def test_non_language_classification_continues_existing_fallback(self):
        client = FakeClient([
            json.dumps({
                "is_language_question": False,
                "target_language": "",
                "answer": "",
                "confidence": "high",
            }),
            json.dumps({
                "can_answer": True,
                "answer": "Comfortable",
                "confidence": "medium",
            }),
        ])
        with patch.object(gemini, "OpenAI", return_value=client):
            result = gemini.answer_unknown_question(
                "How comfortable are you with cross-functional work?",
                "select",
                ["Not comfortable", "Comfortable"],
                "Synthetic job",
                "Synthetic description",
                None,
                required=True,
                constraints={"required": "true"},
            )
        self.assertEqual(result.answer, "Comfortable")
        self.assertEqual(result.provider_request_count, 2)
        self.assertEqual(len(client.chat.completions.calls), 2)

    def test_multilingual_option_and_numeric_validation_repair_once(self):
        option_client = FakeClient([
            json.dumps({
                "is_language_question": True,
                "target_language": "German",
                "answer": "Invented option",
                "confidence": "medium",
            }),
            json.dumps({
                "is_language_question": True,
                "target_language": "German",
                "answer": "Fortgeschritten",
                "confidence": "medium",
            }),
        ])
        with patch.object(gemini, "OpenAI", return_value=option_client):
            option_resolution = gemini.resolve_multilingual_language_question(
                "Wie gut sind Ihre Deutschkenntnisse?",
                "select",
                ["Grundkenntnisse", "Fortgeschritten"],
                True,
                {"required": "true"},
                profile=self.profile,
            )
        self.assertEqual(option_resolution.result.answer, "Fortgeschritten")
        self.assertEqual(option_resolution.result.provider_request_count, 2)
        self.assertEqual(len(option_client.chat.completions.calls), 2)

        numeric_client = FakeClient([
            json.dumps({
                "is_language_question": True,
                "target_language": "Japanese",
                "answer": 11,
                "confidence": "medium",
            }),
            json.dumps({
                "is_language_question": True,
                "target_language": "Japanese",
                "answer": 8,
                "confidence": "medium",
            }),
        ])
        with patch.object(gemini, "OpenAI", return_value=numeric_client):
            numeric_resolution = gemini.resolve_multilingual_language_question(
                "日本語のレベルはどのくらいですか？ 1-10",
                "number",
                [],
                True,
                {"type": "number", "min": "1", "max": "10", "step": "1"},
                profile=self.profile,
            )
        self.assertEqual(numeric_resolution.result.answer, "8")
        self.assertEqual(
            numeric_resolution.result.reason_code,
            "multilingual_language_numeric_scale",
        )
        self.assertEqual(numeric_resolution.result.provider_request_count, 2)

    def test_known_english_one_to_ten_scale_uses_valid_scale_maximum(self):
        payload = json.dumps({
            "is_language_question": True,
            "target_language": "English",
            "answer": 10,
            "confidence": "high",
        })
        client = FakeClient([payload])
        with patch.object(gemini, "OpenAI", return_value=client):
            result = gemini.answer_unknown_question(
                "Rate your English level from 1 to 10",
                "number",
                [],
                "Synthetic job",
                "Synthetic description",
                None,
                required=True,
                constraints={"type": "number", "min": "1", "max": "10", "step": "1"},
            )
        self.assertEqual(result.answer, "10")
        self.assertEqual(
            result.reason_code,
            "multilingual_language_numeric_scale",
        )
        self.assertEqual(result.provider_request_count, 1)

    def test_failed_multilingual_mapping_is_typed_after_one_repair(self):
        invalid = json.dumps({
            "is_language_question": True,
            "target_language": "German",
            "answer": "Invented option",
            "confidence": "medium",
        })
        client = FakeClient([invalid, invalid])
        with patch.object(gemini, "OpenAI", return_value=client):
            resolution = gemini.resolve_multilingual_language_question(
                "Wie gut sind Ihre Deutschkenntnisse?",
                "select",
                ["Grundkenntnisse", "Fortgeschritten"],
                True,
                {"required": "true"},
                profile=self.profile,
            )
        self.assertTrue(resolution.is_language_question)
        self.assertFalse(resolution.result.can_answer)
        self.assertEqual(
            resolution.result.reason_code,
            "multilingual_language_mapping_failed",
        )
        self.assertEqual(resolution.result.provider_request_count, 2)

    def test_catalan_none_maps_only_to_safe_visible_option(self):
        with patch.object(gemini, "OpenAI") as client_factory:
            safe = gemini.answer_unknown_question(
                "What is your Catalan proficiency level?",
                "select",
                ["None", "Professional", "Native or bilingual"],
                "",
                "",
                None,
            )
            unsafe = gemini.answer_unknown_question(
                "What is your Catalan proficiency level?",
                "select",
                ["Professional", "Native or bilingual"],
                "",
                "",
                None,
            )
        self.assertEqual(safe.answer, "None")
        self.assertFalse(unsafe.can_answer)
        self.assertEqual(unsafe.reason_code, "exact_option_unavailable")
        client_factory.assert_not_called()

    def test_explicit_skill_aliases_are_narrow_and_longest_match_wins(self):
        cases = (
            ("Years with Excel?", "7"),
            ("Years with Data Modelling?", "5"),
            ("Years of consultant experience?", "5"),
            ("Years of SQL-related experience?", "4"),
        )
        for question, expected in cases:
            with self.subTest(question=question), patch.object(gemini, "OpenAI") as client_factory:
                result = gemini.answer_unknown_question(
                    question, "number", [], "", "", None
                )
            self.assertEqual(result.answer, expected)
            client_factory.assert_not_called()

    def test_azure_sql_never_inherits_sql_substring(self):
        with patch.object(gemini, "OpenAI") as client_factory:
            result = gemini.answer_unknown_question(
                "How many years of experience do you have with Azure SQL?",
                "number",
                [],
                "",
                "",
                None,
            )
        self.assertEqual(result.answer, "4")
        client_factory.assert_not_called()

        self.write_skills([
            {"name": "SQL", "years_experience": 5, "present": True, "verified": True}
        ])
        result, client = self.call(
            ['{"can_answer":true,"answer":2,"confidence":"low"}'],
            "number",
            question="How many years of experience do you have with Azure SQL?",
        )
        self.assertEqual(result.answer, "2")
        self.assertEqual(len(client.chat.completions.calls), 1)

    def test_confirmed_capabilities_answer_yes_without_gemini(self):
        questions = (
            "Do you have cross functional experience?",
            "Do you have continuous improvement experience?",
            "Do you have project coordination experience?",
        )
        for question in questions:
            with self.subTest(question=question), patch.object(gemini, "OpenAI") as client_factory:
                result = gemini.answer_unknown_question(
                    question, "radio", ["Yes", "No"], "", "", None
                )
            self.assertEqual(result.answer, "Yes")
            self.assertEqual(result.reason_code, "exact_profile_fact")
            client_factory.assert_not_called()

    def test_python_without_exact_years_reaches_gemini(self):
        self.write_skills([{"name": "Python", "years_experience": None, "present": True, "verified": True}])
        result, client = self.call(
            ['{"can_answer":true,"answer":3,"confidence":"low"}'],
            "number",
            question="How many years of experience do you have with Python?",
        )
        self.assertEqual(result.answer, "3")
        self.assertEqual(len(client.chat.completions.calls), 1)

    def test_numpy_without_exact_years_reaches_gemini(self):
        self.write_skills([{"name": "NumPy", "years_experience": None, "present": True, "verified": True}])
        result, client = self.call(
            ['{"can_answer":true,"answer":2,"confidence":"low"}'],
            "number",
            question="How many years have you worked with NumPy?",
        )
        self.assertEqual(result.answer, "2")
        self.assertEqual(len(client.chat.completions.calls), 1)

    def test_profile_and_client_are_not_cached_between_questions(self):
        self.write_skills([{"name": "SQL", "years_experience": 5, "present": True, "verified": True}])
        first = gemini.answer_unknown_question("Years with SQL?", "number", [], "", "", None)
        self.write_skills([{"name": "SQL", "years_experience": 2, "present": True, "verified": True}])
        second = gemini.answer_unknown_question("Years with SQL?", "number", [], "", "", None)
        self.assertEqual((first.answer, second.answer), ("5", "2"))

        clients = [FakeClient(['{"can_answer":true,"answer":"A","confidence":"low"}']),
                   FakeClient(['{"can_answer":true,"answer":"B","confidence":"low"}'])]
        with patch.object(gemini, "OpenAI", side_effect=clients) as client_factory:
            one = gemini.answer_unknown_question("Ordinary question one", "text", [], "", "", None)
            two = gemini.answer_unknown_question("Ordinary question two", "text", [], "", "", None)
        self.assertEqual((one.answer, two.answer), ("A", "B"))
        self.assertEqual(client_factory.call_count, 2)

    def test_valid_number_is_normalized(self):
        result, client = self.call(
            ['{"can_answer":true,"answer":4,"confidence":"medium","reason_code":"grounded_ai_answer"}'],
            "number",
        )
        self.assertTrue(result.can_answer)
        self.assertEqual(result.answer, "4")
        self.assertEqual(result.provider_request_count, 1)
        self.assertEqual(len(client.chat.completions.calls), 1)

    def test_fractional_or_implausible_number_is_rejected(self):
        for answer in ("2.5", "-1", "9999"):
            result, _ = self.call(
                [json.dumps({"can_answer": True, "answer": answer, "confidence": "low"})],
                "number",
            )
            self.assertFalse(result.can_answer)
            self.assertEqual(result.reason_code, "invalid_number")

    def test_select_returns_exact_original_option(self):
        result, _ = self.call(
            ['{"can_answer":true,"answer":"  SECOND option ","confidence":"low"}'],
            "select",
            ["First option", "Second Option"],
        )
        self.assertEqual(result.answer, "Second Option")

    def test_invalid_option_is_rejected(self):
        result, _ = self.call(
            ['{"can_answer":true,"answer":"Invented","confidence":"low"}'],
            "radio",
            ["First", "Second"],
        )
        self.assertFalse(result.can_answer)
        self.assertEqual(result.reason_code, "invalid_option")

    def test_malformed_json_gets_one_repair(self):
        result, client = self.call(
            [
                "not-json",
                '{"can_answer":true,"answer":"Grounded text","confidence":"medium"}',
            ]
        )
        self.assertTrue(result.can_answer)
        self.assertEqual(result.provider_request_count, 2)
        self.assertEqual(len(client.chat.completions.calls), 2)

    def test_transient_failure_retries_twice(self):
        with patch.object(gemini.time, "sleep"):
            result, client = self.call(
                [
                    StatusError(503),
                    StatusError(429),
                    '{"can_answer":true,"answer":"Grounded text","confidence":"low"}',
                ]
            )
        self.assertTrue(result.can_answer)
        self.assertEqual(result.provider_request_count, 3)
        self.assertEqual(len(client.chat.completions.calls), 3)

    def test_non_transient_failure_does_not_retry(self):
        result, client = self.call([StatusError(401)])
        self.assertFalse(result.can_answer)
        self.assertEqual(result.reason_code, "provider_request_failed")
        self.assertEqual(result.provider_request_count, 1)
        self.assertEqual(len(client.chat.completions.calls), 1)

    def test_contact_field_never_constructs_client(self):
        with patch.object(gemini, "OpenAI") as client_factory:
            result = gemini.answer_unknown_question(
                "Email address", "text", [], "", "", None
            )
        self.assertFalse(result.can_answer)
        self.assertEqual(result.reason_code, "contact_field_blocked")
        client_factory.assert_not_called()

    def test_authorization_paraphrases_bypass_gemini(self):
        for question in (
            "Do you have the right to work in Spain?",
            "¿Estás autorizado para trabajar en España?",
            "Do you have a work permit for this location?",
        ):
            with self.subTest(question=question):
                with patch.object(gemini, "OpenAI") as client_factory:
                    result = gemini.answer_unknown_question(
                        question, "radio", ["Yes", "No"], "", "", None
                    )
                self.assertEqual(result.answer, "Yes")
                self.assertEqual(result.reason_code, "exact_profile_fact")
                client_factory.assert_not_called()

    def test_sponsorship_paraphrases_bypass_gemini(self):
        for question in (
            "Will you need employer sponsorship now or in the future?",
            "Do you require visa sponsorship?",
        ):
            with self.subTest(question=question):
                with patch.object(gemini, "OpenAI") as client_factory:
                    result = gemini.answer_unknown_question(
                        question, "radio", ["Yes", "No"], "", "", None
                    )
                self.assertEqual(result.answer, "No")
                self.assertEqual(result.reason_code, "exact_profile_fact")
                client_factory.assert_not_called()

    def test_salary_availability_and_language_semantic_mapping(self):
        payload = json.dumps({
            "can_answer": True,
            "answer": "Synthetic availability",
            "confidence": "high",
            "reason_code": "semantic_confirmed_fact",
        })
        result, client = self.call(
            [payload], "text", [], question="When would you be able to join?"
        )
        self.assertEqual(result.answer, "Synthetic availability")
        self.assertEqual(result.reason_code, "semantic_confirmed_fact")
        self.assertEqual(len(client.chat.completions.calls), 1)

        with patch.object(gemini, "OpenAI") as client_factory:
            language = gemini.answer_unknown_question(
                "What is your English fluency?",
                "select",
                ["Basic", "Professional"],
                "",
                "",
                None,
            )
        self.assertEqual(language.answer, "Professional")
        self.assertEqual(language.reason_code, "exact_profile_fact")
        client_factory.assert_not_called()

    def test_annual_salary_paraphrases_use_verified_profile_without_gemini(self):
        for question in (
            "What annual gross salary do you expect?",
            "¿Qué remuneración anual buscas?",
            "¿Cuáles son tus expectativas salariales anuales?",
        ):
            with self.subTest(question=question), patch.object(gemini, "OpenAI") as client_factory:
                result = gemini.answer_unknown_question(
                    question, "number", [], "", "", None
                )
            self.assertEqual(result.answer, "32000")
            self.assertEqual(result.reason_code, "exact_profile_fact")
            client_factory.assert_not_called()

    def test_unmatched_boolean_and_missing_years_do_not_default(self):
        result, client = self.call(
            ['{"can_answer":true,"answer":"Yes","confidence":"medium"}'],
            "radio",
            ["Yes", "No"],
            question="Have you led a regulated manufacturing audit?",
        )
        self.assertEqual(result.answer, "Yes")
        self.assertEqual(len(client.chat.completions.calls), 1)

        self.write_skills([
            {"name": "NumPy", "years_experience": None, "present": True, "verified": True}
        ])
        result, client = self.call(
            ['{"can_answer":false,"answer":"","confidence":"low"}'],
            "number",
            question="How many years have you used NumPy?",
        )
        self.assertFalse(result.can_answer)
        self.assertEqual(len(client.chat.completions.calls), 1)

    def test_confirmed_sheet_is_bounded_allowlisted_and_prompt_prioritizes_semantics(self):
        result, client = self.call(
            ['{"can_answer":true,"answer":"Yes","confidence":"high","reason_code":"semantic_confirmed_fact"}'],
            "radio",
            ["Yes", "No"],
            question="Can your confirmed background support this ordinary requirement?",
        )
        self.assertTrue(result.can_answer)
        prompt = client.chat.completions.calls[0]["messages"][0]["content"]
        for key in ("work_authorization", "employer_sponsorship_required", "availability", "salary_expectation", "languages", "exact_skill_years", "confirmed_capabilities"):
            self.assertIn(key, prompt)
        for stale_key in ("configured_answer", "work_preferences", "general_experience_years"):
            self.assertNotIn(stale_key, prompt)
        for forbidden in ("first_name", "last_name", "email", "phone_number", "street", "API key"):
            self.assertNotIn(forbidden, prompt)
        self.assertIn("translation, paraphrase, or alternate wording", prompt)
        self.assertIn("Decline only if", prompt)
        self.assertIn("not a ceiling", prompt)
        self.assertIn("do not apply a second conservative downgrade", prompt)
        self.assertIn("strongest defensible answer", prompt)
        self.assertIn("Do not default an unsupported numeric answer to 0", prompt)

    def test_high_risk_without_exact_fact_is_not_inferred(self):
        with patch.object(gemini, "OpenAI") as client_factory:
            result = gemini.answer_unknown_question(
                "Do you hold security clearance?", "radio", ["Yes", "No"], "", "", None
            )
        self.assertFalse(result.can_answer)
        self.assertEqual(result.reason_code, "high_risk_exact_fact_missing")
        client_factory.assert_not_called()

    def test_eu_citizenship_is_not_implied_by_authorization_or_sponsorship(self):
        self.profile.pop("citizenship")
        self.profile["location"] = {
            "country": "Spain",
            "verified": True,
        }
        self.profile_path.write_text(
            json.dumps(self.profile), encoding="utf-8"
        )
        with patch.object(gemini, "OpenAI") as client_factory:
            result = gemini.answer_unknown_question(
                "Do you hold a European Citizenship?",
                "radio",
                ["Yes", "No"],
                "",
                "",
                None,
                required=True,
            )
        self.assertFalse(result.can_answer)
        self.assertEqual(result.reason_code, "high_risk_exact_fact_missing")
        self.assertEqual(result.provider_request_count, 0)
        client_factory.assert_not_called()

    def test_verified_eu_citizenship_variants_return_exact_no_locally(self):
        questions = (
            "Do you hold European citizenship?",
            "Are you an EU citizen?",
            "Do you have citizenship of an EU member state?",
            "¿Tienes ciudadanía europea?",
            "¿Eres ciudadano/a de la Unión Europea?",
            "Avez-vous la citoyenneté européenne ?",
        )
        for question in questions:
            with self.subTest(question=question):
                with patch.object(gemini, "OpenAI") as client_factory:
                    result = gemini.answer_unknown_question(
                        question,
                        "radio",
                        ["Yes", "No"],
                        "",
                        "",
                        None,
                        required=True,
                    )
                self.assertTrue(result.can_answer)
                self.assertEqual(result.answer, "No")
                self.assertEqual(result.reason_code, "exact_profile_fact")
                self.assertEqual(result.provider_request_count, 0)
                client_factory.assert_not_called()

    def test_verified_nationality_text_and_country_select_are_exact(self):
        cases = (
            ("What is your nationality?", "text", [], "Chinese"),
            (
                "Country of citizenship",
                "select",
                ["Select an option", "China", "Spain"],
                "China",
            ),
            (
                "Nationality / citizenship",
                "select",
                ["Chinese", "Spanish", "European"],
                "Chinese",
            ),
        )
        for question, field_type, options, expected in cases:
            with self.subTest(question=question):
                with patch.object(gemini, "OpenAI") as client_factory:
                    result = gemini.answer_unknown_question(
                        question,
                        field_type,
                        options,
                        "",
                        "",
                        None,
                        required=True,
                    )
                self.assertTrue(result.can_answer)
                self.assertEqual(result.answer, expected)
                self.assertEqual(result.reason_code, "exact_profile_fact")
                self.assertEqual(result.provider_request_count, 0)
                client_factory.assert_not_called()

    def test_citizenship_missing_visible_option_remains_unresolved(self):
        with patch.object(gemini, "OpenAI") as client_factory:
            result = gemini.answer_unknown_question(
                "Country of citizenship",
                "select",
                ["Select an option", "Spain", "France"],
                "",
                "",
                None,
                required=True,
            )
        self.assertFalse(result.can_answer)
        self.assertEqual(result.reason_code, "exact_option_not_available")
        self.assertEqual(result.provider_request_count, 0)
        client_factory.assert_not_called()

    def test_missing_profile_fails_safely(self):
        self.profile_path.unlink()
        with patch.object(gemini, "OpenAI") as client_factory:
            result = gemini.answer_unknown_question(
                "Ordinary question", "text", [], "", "", None
            )
        self.assertFalse(result.can_answer)
        self.assertEqual(result.reason_code, "profile_unavailable")
        client_factory.assert_not_called()

    def test_text_is_plain_and_length_bounded(self):
        result, _ = self.call(
            ['{"can_answer":true,"answer":"**Grounded** response","confidence":"medium"}'],
            text_limit=8,
        )
        self.assertEqual(result.answer, "Grounded")

    def test_new_path_emits_no_prompt_or_response_output(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result, _ = self.call(
                ['{"can_answer":true,"answer":"Sensitive synthetic answer","confidence":"low"}']
            )
        self.assertTrue(result.can_answer)
        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
