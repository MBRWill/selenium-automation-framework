"""Narrow, privacy-safe Gemini fallback for unmatched application questions."""
from dataclasses import dataclass
import json
from pathlib import Path
import re
import time
import unicodedata
from openai import OpenAI
from modules.ai.gemini_config import (
    GEMINI_OPENAI_ENDPOINT,
    load_gemini_config,
)
from config.questions import (
    earliest_start_date,
    notice_period,
)
_PROFILE_PATH = Path(__file__).resolve().parents[2] / "config" / "candidate_profile.json"
_TRANSIENT_STATUSES = {429, 500, 502, 503, 504}
_CONTACT_WORDS = ("first name", "middle name", "last name", "full name", "email", "phone")
_PROHIBITED_INFERENCE_WORDS = (
    "citizen", "citizenship", "nationality", "nacionalidad", "nationalite",
    "ciudadania", "citoyennete", "clearance", "licen", "certif", "legal declaration",
    "privacy", "consent", "disability",
    "veteran", "gender", "ethnicity", "race",
)
_EXPLICIT_SKILL_ALIASES = {
    "Microsoft Excel": ("microsoft excel", "excel"),
    "Power BI": ("power bi", "microsoft power bi"),
    "Business Analyst focusing on Procurement": (
        "business analyst focusing on procurement",
        "business analyst procurement",
        "procurement business analyst",
    ),
    "POS Systems": ("pos systems", "point of sale systems", "point of sale"),
    "Planning, Budgeting and Forecasting": (
        "planning budgeting and forecasting",
        "planning budgeting forecasting",
        "budgeting and forecasting",
    ),
    "FP&A": ("fp a", "fp and a", "financial planning and analysis"),
    "Research and Development": (
        "research and development",
        "research development",
        "r d",
    ),
    "Data Modeling": ("data modeling", "data modelling"),
    "Consulting": ("consulting", "consulting experience", "consultant experience"),
    "Azure SQL": ("azure sql", "sql related experience"),
    "Cross-functional work": ("cross functional work", "cross functional"),
    "Process improvement": (
        "process improvement",
        "continuous improvement",
        "process optimization",
        "process optimisation",
    ),
    "Project coordination": ("project coordination", "project coordination experience"),
    "POS Solutions / Equivalents": (
        "pos solutions",
        "pos solution",
        "pos equivalents",
        "pos systems equivalents",
    ),
    "SAP Procurement / Ariba / MM": (
        "sap procurement",
        "sap ariba",
        "ariba",
        "sap mm",
        "sap procurement ariba mm",
    ),
    "SAP S/4HANA CO-OM": (
        "sap s 4hana co om",
        "sap s4hana co om",
        "s 4hana co om",
        "s4hana co om",
    ),
    "Power BI and Advanced Excel": (
        "power bi and advanced excel",
        "power bi and excel avanzado",
        "dominio de power bi y excel avanzado",
    ),
}
_CONFIRMED_CAPABILITIES = {
    "cross-functional work",
    "process improvement",
    "project coordination",
    "pos solutions / equivalents",
    "sap procurement / ariba / mm",
    "sap s/4hana co-om",
    "power bi and advanced excel",
}
_EXPERIENCE_YES_PHRASES = (
    "do you have experience",
    "have you worked with",
    "have you worked in",
    "have you worked on",
    "have you used",
    "have you implemented",
    "have you participated in",
    "have you had",
    "do you meet the",
    "do you have knowledge",
    "are you experienced in",
    "are you familiar with",
    "can you work with",
    "tienes experiencia",
    "tiene experiencia",
    "cuentas con experiencia",
    "dispones de experiencia",
    "has trabajado con",
    "has trabajado en",
    "has llevado",
    "has utilizado",
    "has usado",
    "has implementado",
    "has participado en",
    "posees experiencia",
    "posees conocimiento",
    "posees conocimientos",
    "tienes conocimiento",
    "tienes conocimientos",
    "tienes dominio",
    "conoces",
    "manejas",
    "dominas",
    "experiencia en el sector",
    "experiencia llevando",
    "trabajando en asesoría",
    "trabajando en asesoria",
    "trabajando en gestoría",
    "trabajando en gestoria",
    "experiencia como",
)
_EXPERIENCE_POLICY_EXCLUSIONS = (
    "sponsorship",
    "visa",
    "work authorization",
    "work authorisation",
    "right to work",
    "work permit",
    "citizen",
    "criminal",
    "felony",
    "licence",
    "license",
    "certification",
    "certified",
    "relocate",
    "relocation",
    "availability",
    "available to start",
    "notice period",
    "salary",
    "compensation",
    "hourly rate",
    "day rate",
    "rate of pay",
    "vehicle",
    "driving",
    "commute",
    "commuting",
    "onsite",
    "on site",
    "security clearance",
    "personal declaration",
    "legal declaration",
    "education",
    "degree",
    "graduat",
    "diploma",
)
_AUTHORIZATION_PHRASES = (
    "legally authorized",
    "legally authorised",
    "right to work",
    "work authorization",
    "work authorisation",
    "work permit",
    "employment eligibility",
    "autorizado para trabajar",
    "autorizada para trabajar",
    "autorizacion para trabajar",
    "autorización para trabajar",
    "permiso para trabajar",
    "derecho a trabajar",
)
_SPONSORSHIP_PHRASES = (
    "employer sponsorship",
    "require sponsorship",
    "requires sponsorship",
    "need sponsorship",
    "needs sponsorship",
    "sponsorship required",
    "visa sponsorship",
    "patrocinio de visa",
    "patrocinio de visado",
    "patrocinio del empleador",
    "apoyo de la empresa para poder trabajar",
    "apoyo del empleador para poder trabajar",
)
_SALARY_PHRASES = (
    "salary",
    "compensation",
    "remuneration",
    "remuneracion",
    "remuneración",
    "salario",
    "sueldo",
    "expectativa salarial",
    "expectativas salariales",
)
_ASSERTIVE_ANSWER_POLICY = (
    "Treat the verified profile as a conservative minimum baseline, not a ceiling, "
    "and do not apply a second conservative downgrade. "
    "Choose the strongest defensible answer supported by verified facts. "
    "Treat a verified supported capability as affirmative rather than defaulting to No. "
    "Do not default an unsupported numeric answer to 0. "
    "For visible choices, select the most positive option that remains supported. "
    "Use concise, assertive professional wording. Never invent employers, roles, degrees, "
    "certifications, licences, dates, project names, quantified achievements, revenue, "
    "percentages, team sizes, or performance metrics."
)


@dataclass(frozen=True)
class UnknownQuestionAnswer:
    can_answer: bool
    answer: str = ""
    confidence: str = "low"
    reason_code: str = "gemini_unavailable"
    provider_request_count: int = 0
    original_answer: str = ""
    target_language: str = ""


@dataclass(frozen=True)
class MultilingualLanguageResolution:
    is_language_question: bool | None
    result: UnknownQuestionAnswer
def _load_profile() -> dict:
    try:
        data = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}
def _verified(value):
    if isinstance(value, list):
        return [item for item in (_verified(v) for v in value) if item not in ({}, None)]
    if not isinstance(value, dict):
        return value
    if "verified" in value and value["verified"] is not True:
        return None
    return {
        key: cleaned for key, item in value.items()
        if key not in {"verified", "evidence_id"}
        and (cleaned := _verified(item)) not in ({}, None)
    }
def _profile_context(profile: dict, question: str) -> str:
    keys = ["application_summary"]
    if any(word in question for word in ("skill", "experience", "year", "project", "technology", "experiencia", "año", "habilidad")):
        keys += ["skills", "work_experience", "projects"]
    if "language" in question:
        keys.append("languages")
    if any(word in question for word in ("start", "available", "notice")):
        keys.append("availability")
    if any(word in question for word in ("salary", "compensation", "pay")):
        keys.append("salary_expectations")
    selected = {key: cleaned for key in keys if (cleaned := _verified(profile.get(key))) not in ({}, [], None)}
    return json.dumps(selected, ensure_ascii=False, default=str)[:1800]

def _confirmed_answer_sheet(profile: dict) -> str:
    authorization = _unanimous_verified_boolean(
        profile.get("work_authorization"), "authorized"
    )
    sponsorship = _unanimous_verified_boolean(
        profile.get("sponsorship"), "required"
    )
    sheet = {
        "work_authorization": authorization,
        "employer_sponsorship_required": sponsorship,
        "availability": {
            "configured_earliest_start": earliest_start_date,
            "configured_notice_period_days": notice_period,
            "verified": _verified(profile.get("availability")),
        },
        "salary_expectation": _verified(profile.get("salary_expectations")),
        "languages": _verified(profile.get("languages")),
        "exact_skill_years": {
            str(skill.get("name")): int(skill.get("years_experience"))
            for skill in profile.get("skills", [])
            if skill.get("verified") is True and skill.get("present") is True
            and isinstance(skill.get("years_experience"), (int, float))
            and not isinstance(skill.get("years_experience"), bool)
            and 0 <= skill.get("years_experience") <= 80
            and float(skill.get("years_experience")).is_integer()
        },
        "confirmed_capabilities": {
            str(skill.get("name")): skill.get("present")
            for skill in profile.get("skills", [])
            if skill.get("verified") is True
            and isinstance(skill.get("present"), bool)
            and _normalized(str(skill.get("name", ""))) in _CONFIRMED_CAPABILITIES
        },
    }
    sheet = {key: value for key, value in sheet.items() if value not in ({}, [], None)}
    return json.dumps(sheet, ensure_ascii=False, default=str)[:1800]
def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _phrase_normalized(value: str) -> str:
    return re.sub(r"[^\w]+", " ", value.casefold()).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def _matched_skill(profile: dict, question: str) -> dict | None:
    """Return one explicit skill match, suppressing shorter overlapping names."""
    skills = [
        skill for skill in profile.get("skills", [])
        if skill.get("verified") is True
        and isinstance(skill.get("present"), bool)
        and _phrase_normalized(str(skill.get("name", "")))
    ]
    by_name = {
        _phrase_normalized(str(skill.get("name"))): skill
        for skill in skills
    }
    aliases: list[tuple[str, str]] = []
    for normalized_name in by_name:
        aliases.append((normalized_name, normalized_name))
    for canonical_name, explicit_aliases in _EXPLICIT_SKILL_ALIASES.items():
        canonical = _phrase_normalized(canonical_name)
        aliases.extend(
            (canonical, _phrase_normalized(alias))
            for alias in explicit_aliases
        )

    matches: list[tuple[int, int, str]] = []
    for canonical, alias in aliases:
        for match in re.finditer(rf"(?<!\w){re.escape(alias)}(?!\w)", question):
            matches.append((match.start(), match.end(), canonical))
    longest_matches = [
        match for match in matches
        if not any(
            other[0] <= match[0] and match[1] <= other[1]
            and (other[1] - other[0]) > (match[1] - match[0])
            for other in matches
        )
    ]
    canonical_names = {match[2] for match in longest_matches}
    if len(canonical_names) != 1:
        return None
    return by_name.get(canonical_names.pop())


def _unanimous_verified_boolean(records, key: str) -> bool | None:
    if not isinstance(records, list):
        return None
    values = {
        record.get(key) for record in records
        if isinstance(record, dict) and record.get("verified") is True
        and isinstance(record.get(key), bool)
    }
    return values.pop() if len(values) == 1 else None


def _local_option_or_text(
    answer: str,
    field_type: str,
    options: list[str],
    reason_code: str,
) -> UnknownQuestionAnswer | None:
    if field_type in {"select", "radio"}:
        matched = _match_option(answer, options)
        if matched is None:
            return None
        answer = matched
    elif field_type not in {"number", "text"}:
        return None
    return UnknownQuestionAnswer(True, answer, "high", reason_code)


def _verified_citizenship_facts(profile: dict) -> dict | None:
    citizenship = profile.get("citizenship")
    if not isinstance(citizenship, dict) or citizenship.get("verified") is not True:
        return None
    country = citizenship.get("citizenship_country")
    nationality = citizenship.get("nationality")
    eu_citizenship = citizenship.get("eu_citizenship")
    if (
        not isinstance(country, str)
        or not country.strip()
        or not isinstance(nationality, str)
        or not nationality.strip()
        or not isinstance(eu_citizenship, bool)
    ):
        return None
    return {
        "citizenship_country": country.strip(),
        "nationality": nationality.strip(),
        "eu_citizenship": eu_citizenship,
    }


def _citizenship_question_kind(question: str) -> str | None:
    question = _matching_normalized(question)
    eu_phrases = (
        "european citizenship",
        "eu citizenship",
        "eu citizen",
        "european union citizen",
        "citizenship of an eu member state",
        "citizenship of a european union member state",
        "ciudadania europea",
        "ciudadania de la union europea",
        "ciudadano de la union europea",
        "ciudadana de la union europea",
        "ciudadano a de la union europea",
        "ciudadano de la ue",
        "ciudadana de la ue",
        "ciudadania de un estado miembro de la union europea",
        "citoyennete europeenne",
        "citoyennete de l union europeenne",
        "citoyen de l union europeenne",
        "citoyenne de l union europeenne",
    )
    if any(_contains_phrase(question, phrase) for phrase in eu_phrases):
        return "eu_citizenship"
    country_phrases = (
        "country of citizenship",
        "citizenship country",
        "pais de ciudadania",
        "pays de citoyennete",
    )
    if any(_contains_phrase(question, phrase) for phrase in country_phrases):
        return "citizenship_country"
    nationality_words = (
        "nationality", "nacionalidad", "nationalite",
    )
    citizenship_phrases = (
        "what citizenship do you hold",
        "which citizenship do you hold",
        "citizenship do you hold",
        "que ciudadania tienes",
        "quelle citoyennete avez vous",
    )
    if (
        any(_contains_phrase(question, word) for word in nationality_words)
        or any(_contains_phrase(question, phrase) for phrase in citizenship_phrases)
        or any(
            _contains_phrase(question, word)
            for word in ("citizenship", "ciudadania", "citoyennete")
        )
    ):
        return "nationality"
    return None


def is_citizenship_question(question_text: str) -> bool:
    return _citizenship_question_kind(question_text) is not None


def _exact_citizenship_answer(
    profile: dict,
    question: str,
    field_type: str,
    options: list[str],
) -> UnknownQuestionAnswer | None:
    kind = _citizenship_question_kind(question)
    if kind is None:
        return None
    facts = _verified_citizenship_facts(profile)
    if facts is None:
        return UnknownQuestionAnswer(
            False, reason_code="high_risk_exact_fact_missing"
        )
    if kind == "eu_citizenship":
        answer = _local_option_or_text(
            "Yes" if facts["eu_citizenship"] else "No",
            field_type,
            options,
            "exact_profile_fact",
        )
        return answer or UnknownQuestionAnswer(
            False, reason_code="exact_option_not_available"
        )
    if field_type == "text":
        key = "citizenship_country" if kind == "citizenship_country" else "nationality"
        return UnknownQuestionAnswer(
            True, facts[key], "high", "exact_profile_fact"
        )
    if field_type not in {"select", "radio"}:
        return UnknownQuestionAnswer(
            False, reason_code="high_risk_exact_fact_missing"
        )
    preferred_keys = (
        ("citizenship_country", "nationality")
        if kind == "citizenship_country"
        else ("nationality", "citizenship_country")
    )
    for key in preferred_keys:
        matched = _match_option(facts[key], options)
        if matched is not None:
            return UnknownQuestionAnswer(
                True, matched, "high", "exact_profile_fact"
            )
    return UnknownQuestionAnswer(
        False, reason_code="exact_option_not_available"
    )


def _exact_salary_answer(
    profile: dict,
    question: str,
    field_type: str,
    options: list[str],
) -> UnknownQuestionAnswer | None:
    if not any(_contains_phrase(question, phrase) for phrase in _SALARY_PHRASES):
        return None
    if _is_salary_range_acceptance_question(question):
        return None
    if any(_contains_phrase(question, phrase) for phrase in ("current salary", "present salary", "salario actual", "sueldo actual")):
        return None
    if any(
        _contains_phrase(question, phrase)
        for phrase in (
            "hourly",
            "per hour",
            "hourly rate",
            "por hora",
            "daily",
            "per day",
            "day rate",
            "por día",
            "por dia",
        )
    ):
        return None
    salary = profile.get("salary_expectations")
    if not isinstance(salary, dict) or salary.get("verified") is not True:
        return None
    amount = salary.get("amount")
    currency = _normalized(str(salary.get("currency", "")))
    period = _normalized(str(salary.get("period", "")))
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
        return None
    foreign_currencies = ("usd", "dollar", "dolar", "gbp", "pound", "libra")
    if currency in {"eur", "euro"} and any(
        _contains_phrase(question, marker) for marker in foreign_currencies
    ):
        return None
    monthly = any(
        _contains_phrase(question, phrase)
        for phrase in ("monthly", "per month", "mensual", "por mes")
    )
    if monthly:
        if period not in {"year", "annual", "annually", "año", "ano"}:
            return None
        amount = round(amount / 12, 2)
    text = str(int(amount)) if float(amount).is_integer() else str(amount)
    return _local_option_or_text(text, field_type, options, "exact_profile_fact")


def _salary_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(
        character for character in text if not unicodedata.combining(character)
    )


def _is_salary_range_acceptance_question(question_text: str) -> bool:
    question = re.sub(r"\s+", " ", _salary_text(question_text))
    salary_wording = any(
        marker in question
        for marker in (
            "salary",
            "salario",
            "salarial",
            "rango salarial",
            "banda salarial",
        )
    )
    acceptance_wording = any(
        marker in question
        for marker in (
            "willing to accept",
            "acceptable",
            "comfortable with",
            "accept the offered",
            "dispuesto a aceptar",
            "dispuesta a aceptar",
            "dispuesto/a a aceptar",
            "aceptarias",
            "aceptarías",
            "te encaja",
            "conforme con",
        )
    )
    return salary_wording and acceptance_wording


def _parse_salary_token(number_text: str, has_k_suffix: bool) -> float | None:
    token = re.sub(r"\s+", "", number_text)
    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token or "." in token:
        separator = "," if "," in token else "."
        left, right = token.rsplit(separator, 1)
        token = left + right if len(right) == 3 else left + "." + right
    try:
        amount = float(token)
    except ValueError:
        return None
    if has_k_suffix:
        amount *= 1000
    return amount if 0 <= amount <= 10_000_000 else None


def _annual_salary_range(question_text: str) -> tuple[int, int] | None:
    question = _salary_text(question_text)
    incompatible_periods = (
        "hourly",
        "per hour",
        "por hora",
        "hora",
        "daily",
        "per day",
        "day rate",
        "por dia",
        "por día",
        "monthly",
        "per month",
        "mensual",
        "por mes",
    )
    if any(marker in question for marker in incompatible_periods):
        return None
    if any(marker in question for marker in ("usd", "$", "gbp", "£")):
        return None
    matches = re.findall(
        r"(?<!\w)(\d{1,3}(?:[\s.,]\d{3})+|\d+(?:[.,]\d+)?)(\s*[kK])?(?!\w)",
        question_text,
    )
    if not 1 <= len(matches) <= 2:
        return None
    has_any_k = any(bool(suffix.strip()) for _, suffix in matches)
    amounts = []
    for token, suffix in matches:
        amount = _parse_salary_token(token, bool(suffix.strip()))
        if amount is None:
            return None
        if has_any_k and not suffix.strip() and amount < 1000:
            amount *= 1000
        amounts.append(amount)
    if any(amount < 1000 for amount in amounts):
        return None
    minimum, maximum = (
        (amounts[0], amounts[0])
        if len(amounts) == 1
        else (min(amounts), max(amounts))
    )
    return int(round(minimum)), int(round(maximum))


def _salary_range_acceptance_answer(
    profile: dict,
    question_text: str,
    field_type: str,
    options: list[str],
) -> UnknownQuestionAnswer | None:
    if not _is_salary_range_acceptance_question(question_text):
        return None
    salary = profile.get("salary_expectations")
    if not isinstance(salary, dict) or salary.get("verified") is not True:
        return None
    amount = salary.get("amount")
    currency = _normalized(str(salary.get("currency", "")))
    period = _normalized(str(salary.get("period", "")))
    if (
        isinstance(amount, bool)
        or not isinstance(amount, (int, float))
        or amount < 0
        or currency not in {"eur", "euro"}
        or period not in {"year", "annual", "annually", "año", "ano"}
    ):
        return None
    offered = _annual_salary_range(question_text)
    if offered is None:
        return None
    minimum, maximum = offered
    accepted = maximum >= amount
    reason = (
        "salary_range_accepted_from_expected_salary"
        if accepted
        else "salary_range_below_expected_salary"
    )
    local = _local_option_or_text(
        "Yes" if accepted else "No", field_type, options, reason
    )
    if local is None:
        return None
    return UnknownQuestionAnswer(
        True,
        local.answer,
        "high",
        reason,
        original_answer=(
            f"offered_annual_range_eur={minimum}-{maximum}; "
            f"expected_annual_salary_eur={int(amount)}"
        ),
    )


def is_experience_years_question(question_text: str) -> bool:
    question = _phrase_normalized(question_text)
    if any(_contains_phrase(question, phrase) for phrase in _EXPERIENCE_POLICY_EXCLUSIONS):
        return False
    has_year_unit = re.search(
        r"\b(?:years?|años?|anos?|années?|annees?|ans|anni|jahre?)\b",
        question,
    ) is not None
    if not has_year_unit:
        return False
    return any(
        phrase in question
        for phrase in (
            "experience",
            "experiencia",
            "years with",
            "years using",
            "years working with",
            "years have you worked",
            "años con",
            "años usando",
            "años trabajando",
            "anos con",
            "anos usando",
            "anos trabajando",
            "expérience",
            "experiência",
            "esperienza",
            "erfahrung",
        )
    )


def _is_analyst_role_years_question(question_text: str) -> bool:
    """Identify role-family years questions without consulting the job title."""
    if not is_experience_years_question(question_text):
        return False
    question = _phrase_normalized(question_text)
    return re.search(
        r"\b(?:analysts?|analistas?|analystes?|analystin|analytiker)\b",
        question,
    ) is not None


def _experience_threshold(question: str) -> int | None:
    patterns = (
        r"(?:at least|minimum(?: of)?|no fewer than)\s+(\d{1,2})\s+years?",
        r"(\d{1,2})\s*(?:\+|or more)\s+years?",
        r"meet the\s+(\d{1,2})[ -]?year experience requirement",
        r"(?:al menos|por lo menos|un mínimo de|un minimo de|mínimo de|minimo de)\s+(\d{1,2})\s+(?:años|anos)",
        r"(?:dispones de|tienes|cuentas con)\s+(\d{1,2})\s+(?:o más|o mas|\+)\s+(?:años|anos)",
        r"(\d{1,2})\s+years?(?:\s+of)?\s+experience",
        r"(\d{1,2})\s+(?:años|anos)(?:\s+de)?\s+experiencia",
    )
    for pattern in patterns:
        match = re.search(pattern, question)
        if match:
            threshold = int(match.group(1))
            return threshold if 0 <= threshold <= 80 else None
    return None


def is_experience_capability_question(question_text: str) -> bool:
    question = _phrase_normalized(question_text)
    if any(
        _contains_phrase(question, phrase)
        for phrase in _EXPERIENCE_POLICY_EXCLUSIONS
    ):
        return False
    if any(
        _contains_phrase(question, phrase)
        for phrase in _EXPERIENCE_YES_PHRASES
    ):
        return True
    return _experience_threshold(question) is not None and any(
        marker in question
        for marker in ("experience", "experiencia", "worked", "trabajando")
    )


def _assertive_experience_yes_answer(
    question: str,
    field_type: str,
    options: list[str],
) -> UnknownQuestionAnswer | None:
    if field_type not in {"select", "radio", "text"}:
        return None
    if not is_experience_capability_question(question):
        return None
    return _local_option_or_text(
        "Yes",
        field_type,
        options,
        (
            "assertive_experience_threshold_yes_default"
            if _experience_threshold(question) is not None
            else "assertive_experience_yes_default"
        ),
    )


_LANGUAGE_ALIASES = {
    "english": ("english", "inglés", "ingles", "anglais"),
    "spanish": (
        "spanish",
        "español",
        "espanol",
        "castellano",
        "espagnol",
    ),
    "catalan": ("catalan", "catalán", "català", "catala"),
    "french": ("french", "français", "francais"),
}
_LANGUAGE_SCALE_VALUES = {"english": "5", "spanish": "3", "catalan": "1"}


def _language_name(question: str) -> str | None:
    for canonical, aliases in _LANGUAGE_ALIASES.items():
        if any(_contains_phrase(question, alias) for alias in aliases):
            return canonical
    return None


def _is_language_level_question(question: str) -> bool:
    return _language_name(question) is not None and any(
        _contains_phrase(question, phrase)
        for phrase in (
            "level",
            "proficiency",
            "fluency",
            "nivel",
            "niveau",
            "dominio del idioma",
            "nivel de idioma",
        )
    )


def _language_record(profile: dict, language_name: str) -> dict | None:
    aliases = set(_LANGUAGE_ALIASES[language_name])
    return next(
        (
            language for language in profile.get("languages", [])
            if language.get("verified") is True
            and _phrase_normalized(str(language.get("language", ""))) in aliases
        ),
        None,
    )


def _language_level_answer(
    profile: dict,
    question: str,
    field_type: str,
    options: list[str],
) -> UnknownQuestionAnswer | None:
    if not _is_language_level_question(question):
        return None
    language_name = _language_name(question)
    language = _language_record(profile, language_name) if language_name else None
    if not language:
        return None
    level = _normalized(str(language.get("level") or "none"))
    reason_code = (
        "localized_language_exact_fact"
        if _contains_phrase(question, "niveau")
        else "exact_profile_fact"
    )
    if field_type == "number":
        if language_name not in _LANGUAGE_SCALE_VALUES:
            return None
        detected_scale = _constraints_with_detected_numeric_scale(
            question, [], None
        )
        if not (
            str(detected_scale.get("min", "")) == "1"
            and str(detected_scale.get("max", "")) == "5"
        ):
            return None
        return UnknownQuestionAnswer(
            True,
            _LANGUAGE_SCALE_VALUES[language_name],
            "high",
            (
                "localized_language_exact_fact"
                if reason_code == "localized_language_exact_fact"
                else "language_level_numeric_scale"
            ),
            original_answer=str(language.get("level") or "None"),
            target_language=language_name,
        )
    if field_type in {"select", "radio"}:
        ranked_levels = {
            "english": (
                {
                    "native or bilingual",
                    "nativo o bilingüe",
                    "natif ou bilingue",
                    "langue maternelle ou bilingue",
                    "bilingue",
                },
                {
                    "fluent",
                    "full professional proficiency",
                    "professional working proficiency",
                    "professional",
                    "courant",
                    "compétence professionnelle complète",
                    "competence professionnelle complete",
                    "professionnel",
                },
                {"intermediate", "intermédiaire", "intermediaire"},
                {
                    "elementary",
                    "beginner",
                    "élémentaire",
                    "elementaire",
                    "débutant",
                    "debutant",
                },
                {"none", "no proficiency", "inexistant", "aucun"},
            ),
            "spanish": (
                {"conversational", "conversación", "conversacion", "conversacional"},
                {"intermediate", "intermedio", "intermédiaire", "intermediaire"},
            ),
            "catalan": (
                {
                    "none",
                    "no proficiency",
                    "no knowledge",
                    "sin conocimientos",
                    "ninguno",
                    "ninguna",
                    "ningún conocimiento",
                    "ningun conocimiento",
                    "inexistant",
                    "aucun",
                },
            ),
        }
        for safe_group in ranked_levels[language_name]:
            for option in options:
                if _normalized(option) in safe_group:
                    return UnknownQuestionAnswer(
                        True,
                        option,
                        "high",
                        reason_code,
                        original_answer=str(language.get("level") or "None"),
                        target_language=language_name,
                    )
        return None
    if field_type == "text":
        if language_name == "english":
            answer = str(language.get("level") or "Native or bilingual")
        elif language_name == "spanish" and level == "conversational":
            answer = "Conversational"
        elif language_name == "catalan" and level == "none":
            answer = "None"
        else:
            return None
        return UnknownQuestionAnswer(
            True,
            answer,
            "high",
            reason_code,
            original_answer=str(language.get("level") or "None"),
            target_language=language_name,
        )
    return None


def _is_spanish_level_question(question: str) -> bool:
    return _language_name(question) == "spanish" and _is_language_level_question(question)


def _exact_profile_answer(
    profile: dict,
    question: str,
    field_type: str,
    options: list[str],
) -> UnknownQuestionAnswer | None:
    citizenship = _exact_citizenship_answer(
        profile, question, field_type, options
    )
    if citizenship is not None:
        return citizenship
    language_level = _language_level_answer(profile, question, field_type, options)
    if language_level is not None:
        return language_level
    skill = _matched_skill(profile, question)
    if skill is not None and skill.get("present") is True and field_type == "number":
        value = skill.get("years_experience")
        if not isinstance(value, bool) and isinstance(value, (int, float)):
            if 0 <= value <= 80 and float(value).is_integer():
                return UnknownQuestionAnswer(
                    True, str(int(value)), "high", "exact_skill_years"
                )
    threshold = _experience_threshold(question)
    matched_yes_no_skill = skill is not None and (
        field_type == "text"
        or (
            field_type in {"select", "radio"}
            and _match_option("Yes", options) is not None
            and _match_option("No", options) is not None
        )
    )
    if matched_yes_no_skill and skill.get("present") is False:
        answer = _local_option_or_text(
            "No",
            field_type,
            options,
            "exact_profile_fact",
        )
        if answer is not None:
            return answer
    if matched_yes_no_skill and threshold is not None:
        years = skill.get("years_experience")
        if (
            not isinstance(years, bool)
            and isinstance(years, (int, float))
            and 0 <= years <= 80
        ):
            return _local_option_or_text(
                "Yes" if years >= threshold else "No",
                field_type,
                options,
                "exact_experience_threshold_fact",
            )
    elif matched_yes_no_skill or (
        skill is not None
        and _normalized(str(skill.get("name", ""))) in _CONFIRMED_CAPABILITIES
    ):
        answer = _local_option_or_text(
            "Yes" if skill.get("present") is True else "No",
            field_type,
            options,
            "exact_profile_fact",
        )
        if answer is not None:
            return answer

    if any(_contains_phrase(question, phrase) for phrase in _AUTHORIZATION_PHRASES):
        authorized = _unanimous_verified_boolean(
            profile.get("work_authorization"), "authorized"
        )
        if authorized is not None:
            return _local_option_or_text(
                "Yes" if authorized else "No",
                field_type,
                options,
                "exact_profile_fact",
            )
    if any(_contains_phrase(question, phrase) for phrase in _SPONSORSHIP_PHRASES):
        required = _unanimous_verified_boolean(
            profile.get("sponsorship"), "required"
        )
        if required is not None:
            return _local_option_or_text(
                "Yes" if required else "No",
                field_type,
                options,
                "exact_profile_fact",
            )
    return _exact_salary_answer(profile, question, field_type, options)


def _apply_experience_years_floor(
    result: UnknownQuestionAnswer,
    question_text: str,
    field_type: str,
) -> UnknownQuestionAnswer:
    if field_type != "number" or not is_experience_years_question(question_text):
        return result
    original = str(result.answer or "").strip()
    if _is_analyst_role_years_question(question_text):
        try:
            numeric_answer = int(original)
        except (TypeError, ValueError):
            numeric_answer = -1
        if result.can_answer and numeric_answer >= 3:
            return result
        return UnknownQuestionAnswer(
            True,
            "3",
            "high",
            "analyst_role_years_minimum_floor",
            result.provider_request_count,
            original,
        )
    if result.can_answer and original not in {"", "0"}:
        return result
    return UnknownQuestionAnswer(
        True,
        "1",
        "low",
        "experience_years_minimum_floor",
        result.provider_request_count,
        original,
    )


def _matching_normalized(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(
        character for character in text
        if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^\w]+", " ", text).split())


def _match_option(answer: str, options: list[str]) -> str | None:
    wanted = _matching_normalized(answer)
    for option in options:
        if _matching_normalized(option) == wanted:
            return option
    aliases = (
        {"yes", "si", "oui", "ja", "tak", "sim"},
        {"no", "non", "nein", "nie", "nao"},
    )
    for equivalents in aliases:
        if wanted in equivalents:
            for option in options:
                if _matching_normalized(option) in equivalents:
                    return option
    return None
def _exact_skill_years(profile: dict, question: str) -> UnknownQuestionAnswer | None:
    return _exact_profile_answer(profile, question, "number", [])


def answer_verified_question(
    question_text: str,
    field_type: str,
    visible_options: list[str] | None = None,
    constraints: dict | None = None,
) -> UnknownQuestionAnswer:
    """Resolve only a verified scalar/profile fact; never call a provider."""
    question = _normalized(question_text)
    options = [
        str(option) for option in (visible_options or [])
        if _normalized(str(option))
        not in {
            "",
            "select an option",
            "selecciona una opción",
            "sélectionnez une option",
            "selectionnez une option",
        }
    ]
    if any(word in question for word in _CONTACT_WORDS):
        return UnknownQuestionAnswer(False, reason_code="contact_field_blocked")
    profile = _load_profile()
    if not profile:
        return UnknownQuestionAnswer(False, reason_code="profile_unavailable")
    salary_range = _salary_range_acceptance_answer(
        profile, question_text, field_type, options
    )
    if salary_range is not None:
        return salary_range
    normalized_question = _phrase_normalized(question_text)
    detected_scale = _constraints_with_detected_numeric_scale(
        question_text, options, constraints
    )
    if (
        field_type == "number"
        and str(detected_scale.get("min", "")) == "1"
        and str(detected_scale.get("max", "")) == "5"
    ):
        normalized_question += " 1 to 5"
    answer = _exact_profile_answer(
        profile, normalized_question, field_type, options
    )
    if answer is not None:
        return _apply_experience_years_floor(
            answer, question_text, field_type
        )
    if (
        _language_name(normalized_question) in _LANGUAGE_SCALE_VALUES
        and _is_language_level_question(normalized_question)
        and field_type in {"select", "radio"}
    ):
        return UnknownQuestionAnswer(False, reason_code="exact_option_unavailable")
    return UnknownQuestionAnswer(False, reason_code="exact_fact_unavailable")


def answer_deterministic_question(
    question_text: str,
    field_type: str,
    visible_options: list[str] | None = None,
) -> UnknownQuestionAnswer:
    """Resolve one field with local rules only; never create a provider client."""
    options = [str(option) for option in (visible_options or [])]
    exact = answer_verified_question(question_text, field_type, options)
    if exact.can_answer or exact.reason_code in {
        "exact_option_unavailable", "exact_option_not_available"
    }:
        return exact
    normalized_question = _phrase_normalized(question_text)
    assertive = _assertive_experience_yes_answer(
        normalized_question, field_type, options
    )
    if assertive is not None:
        return assertive
    return _apply_experience_years_floor(
        exact, question_text, field_type
    )

def _request(
    client: OpenAI,
    model: str,
    messages: list[dict],
) -> tuple[str | None, int]:
    request_count = 0
    for retry in range(3):
        request_count += 1
        try:
            response = client.chat.completions.create(
                model=model, messages=messages, temperature=0,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content, request_count
        except Exception as error:
            if getattr(error, "status_code", None) not in _TRANSIENT_STATUSES or retry == 2:
                return None, request_count
            time.sleep(min(0.2 * (2 ** retry), 0.5))
    return None, request_count

def _parse(raw: str | None) -> dict | None:
    try:
        value = json.loads(raw or "")
        return value if isinstance(value, dict) else None
    except (TypeError, ValueError):
        return None

def _validate(
    value: dict,
    field_type: str,
    options: list[str],
    text_limit: int | None,
    provider_request_count: int,
) -> UnknownQuestionAnswer:
    if value.get("can_answer") is not True:
        return UnknownQuestionAnswer(
            False,
            reason_code="model_declined",
            provider_request_count=provider_request_count,
        )
    answer = value.get("answer")
    confidence = value.get("confidence")
    if confidence not in {"low", "medium", "high"}:
        return UnknownQuestionAnswer(
            False,
            reason_code="invalid_confidence",
            provider_request_count=provider_request_count,
        )
    if field_type == "number":
        text = str(answer).strip()
        if not re.fullmatch(r"\d+", text) or int(text) > 80:
            return UnknownQuestionAnswer(
                False,
                reason_code="invalid_number",
                provider_request_count=provider_request_count,
            )
        answer = text
    elif field_type in {"select", "radio"}:
        answer = _match_option(str(answer), options)
        if answer is None:
            return UnknownQuestionAnswer(
                False,
                reason_code="invalid_option",
                provider_request_count=provider_request_count,
            )
    else:
        answer = re.sub(r"[`*_#]+", "", str(answer or "")).strip()
        answer = re.sub(r"\s+", " ", answer)
        if not answer:
            return UnknownQuestionAnswer(
                False,
                reason_code="empty_answer",
                provider_request_count=provider_request_count,
            )
        if text_limit and len(answer) > text_limit:
            answer = answer[:text_limit].rstrip()
    reason = value.get("reason_code")
    if reason not in {"semantic_confirmed_fact", "grounded_ai_answer"}:
        reason = "grounded_ai_answer"
    return UnknownQuestionAnswer(
        True,
        answer,
        confidence,
        reason,
        provider_request_count,
    )


def _minimal_confirmed_language_facts(profile: dict) -> list[dict[str, str]]:
    facts = []
    for record in profile.get("languages", []):
        if not isinstance(record, dict) or record.get("verified") is not True:
            continue
        language = str(record.get("language") or "").strip()
        level = str(record.get("level") or "None").strip()
        if language and len(language) <= 80 and len(level) <= 80:
            facts.append({"language": language, "level": level})
    return facts


def _safe_field_constraints(constraints: dict | None) -> dict[str, str | bool]:
    safe = {}
    for name in (
        "type",
        "inputmode",
        "min",
        "max",
        "step",
        "required",
        "aria-required",
    ):
        value = (constraints or {}).get(name)
        if value in (None, ""):
            continue
        safe[name] = str(value)[:40]
    return safe


def _constraints_with_detected_numeric_scale(
    question_text: str,
    options: list[str],
    constraints: dict | None,
) -> dict[str, str | bool]:
    safe = _safe_field_constraints(constraints)
    normalized_question = _matching_normalized(question_text)
    scale = re.search(r"\b(\d{1,2})\s*(?:to|a)\s*(\d{1,2})\b", normalized_question)
    if scale is None:
        scale = re.search(r"\b(\d{1,2})\s+(\d{1,2})\b", normalized_question)
    numeric_options = [
        int(option.strip())
        for option in options
        if re.fullmatch(r"\d{1,2}", option.strip())
    ]
    if scale is not None:
        safe.setdefault("min", scale.group(1))
        safe.setdefault("max", scale.group(2))
    elif len(numeric_options) >= 2:
        safe.setdefault("min", str(min(numeric_options)))
        safe.setdefault("max", str(max(numeric_options)))
    return safe


def _canonical_language_name(value: str) -> str | None:
    wanted = _matching_normalized(value)
    for canonical, aliases in _LANGUAGE_ALIASES.items():
        if wanted == _matching_normalized(canonical) or any(
            wanted == _matching_normalized(alias) for alias in aliases
        ):
            return canonical
    return None


def _valid_language_numeric_answer(
    answer,
    constraints: dict | None,
) -> str | None:
    text = str(answer or "").strip().replace(",", ".")
    if re.fullmatch(r"\d+(?:\.\d+)?", text) is None:
        return None
    value = float(text)
    safe = _safe_field_constraints(constraints)
    try:
        minimum = float(safe["min"]) if "min" in safe else None
        maximum = float(safe["max"]) if "max" in safe else None
        step = (
            float(safe["step"])
            if safe.get("step", "").casefold() not in {"", "any"}
            else None
        )
    except (TypeError, ValueError):
        return None
    if minimum is not None and value < minimum:
        return None
    if maximum is not None and value > maximum:
        return None
    if step is not None:
        if step <= 0:
            return None
        base = minimum or 0.0
        quotient = (value - base) / step
        if abs(quotient - round(quotient)) > 1e-8:
            return None
    if value > 100:
        return None
    return str(int(value)) if value.is_integer() else text.rstrip("0").rstrip(".")


def _validate_multilingual_language_payload(
    value: dict,
    field_type: str,
    options: list[str],
    constraints: dict | None,
    text_limit: int | None,
    provider_request_count: int,
    profile: dict,
) -> MultilingualLanguageResolution:
    is_language = value.get("is_language_question")
    if is_language is False:
        return MultilingualLanguageResolution(
            False,
            UnknownQuestionAnswer(
                False,
                reason_code="not_language_question",
                provider_request_count=provider_request_count,
            ),
        )
    if is_language is not True:
        return MultilingualLanguageResolution(
            None,
            UnknownQuestionAnswer(
                False,
                reason_code="multilingual_language_mapping_failed",
                provider_request_count=provider_request_count,
            ),
        )
    target_language = str(value.get("target_language") or "").strip()
    if (
        not target_language
        or len(target_language) > 80
        or re.fullmatch(r"[\w .'-]+", target_language) is None
    ):
        return MultilingualLanguageResolution(
            True,
            UnknownQuestionAnswer(
                False,
                reason_code="multilingual_language_mapping_failed",
                provider_request_count=provider_request_count,
            ),
        )
    canonical_language = _canonical_language_name(target_language)
    if canonical_language is not None:
        target_language = canonical_language
    local_answer = None
    if canonical_language is not None:
        if field_type != "number" or (
            str((constraints or {}).get("min", "")) == "1"
            and str((constraints or {}).get("max", "")) == "5"
        ):
            local_answer = _language_level_answer(
                profile,
                f"{canonical_language} level",
                field_type,
                options,
            )
    if local_answer is not None:
        reason_code = (
            "multilingual_language_numeric_scale"
            if field_type == "number"
            else "multilingual_language_provider_mapping"
        )
        return MultilingualLanguageResolution(
            True,
            UnknownQuestionAnswer(
                True,
                local_answer.answer,
                "high",
                reason_code,
                provider_request_count,
                local_answer.original_answer,
                canonical_language,
            ),
        )
    answer = value.get("answer")
    if field_type == "number":
        final_answer = _valid_language_numeric_answer(answer, constraints)
        reason_code = "multilingual_language_numeric_scale"
    elif field_type in {"select", "radio"}:
        final_answer = _match_option(str(answer or ""), options)
        reason_code = "multilingual_language_provider_mapping"
    else:
        final_answer = re.sub(r"\s+", " ", str(answer or "")).strip()
        if text_limit and len(final_answer) > text_limit:
            final_answer = final_answer[:text_limit].rstrip()
        reason_code = "multilingual_language_provider_mapping"
    if not final_answer:
        return MultilingualLanguageResolution(
            True,
            UnknownQuestionAnswer(
                False,
                reason_code="multilingual_language_mapping_failed",
                provider_request_count=provider_request_count,
                target_language=target_language,
            ),
        )
    confidence = value.get("confidence")
    if confidence not in {"low", "medium", "high"}:
        confidence = "low"
    return MultilingualLanguageResolution(
        True,
        UnknownQuestionAnswer(
            True,
            final_answer,
            confidence,
            reason_code,
            provider_request_count,
            target_language=target_language,
        ),
    )


def resolve_multilingual_language_question(
    question_text: str,
    field_type: str,
    visible_options: list[str] | None,
    required: bool,
    constraints: dict | None = None,
    text_limit: int | None = None,
    profile: dict | None = None,
) -> MultilingualLanguageResolution:
    """Classify and answer one field using only bounded language information."""
    profile = profile if isinstance(profile, dict) else _load_profile()
    config = load_gemini_config()
    if not config.configured:
        return MultilingualLanguageResolution(
            None,
            UnknownQuestionAnswer(False, reason_code=config.reason_code),
        )
    options = [str(option) for option in (visible_options or [])]
    language_facts = _minimal_confirmed_language_facts(profile)
    safe_constraints = _constraints_with_detected_numeric_scale(
        question_text, options, constraints
    )
    schema = (
        '{"is_language_question":true|false,'
        '"target_language":"canonical language name or blank",'
        '"answer":"exact visible option or numeric value",'
        '"confidence":"low|medium|high"}'
    )
    normalized_question_text = re.sub(
        r"\s+", " ", str(question_text or "")
    ).strip()[:500]
    prompt = (
        "Classify and answer exactly one application field. Determine whether it asks "
        "about language proficiency in any natural language and identify the target "
        "language; do not confuse the language used to write the question with the "
        "language being assessed. It may request a descriptive level, CEFR level, "
        "numeric scale, or Yes/No capability. Exact confirmed language facts override "
        "estimation. For English choose the strongest defensible visible answer. For "
        "other languages without an exact fact choose the strongest defensible visible "
        "answer; never default automatically to the lowest option. For select or radio, "
        "return exactly one supplied visible option. For number, return only a value "
        "within the supplied constraints. Return only JSON shaped as "
        f"{schema}.\nQuestion: {normalized_question_text}"
        f"\nField type: {field_type}\nRequired: {bool(required)}"
        f"\nVisible options: {json.dumps(options, ensure_ascii=False)}"
        f"\nNumeric constraints: {json.dumps(safe_constraints, ensure_ascii=False)}"
        f"\nConfirmed language facts: {json.dumps(language_facts, ensure_ascii=False)}"
        f"\nAnswer policy: {_ASSERTIVE_ANSWER_POLICY}"
    )
    client = OpenAI(
        api_key=config.api_key,
        base_url=GEMINI_OPENAI_ENDPOINT,
        max_retries=0,
    )
    messages = [{"role": "user", "content": prompt}]
    raw, request_count = _request(client, config.model, messages)
    if raw is None:
        return MultilingualLanguageResolution(
            None,
            UnknownQuestionAnswer(
                False,
                reason_code="multilingual_language_mapping_failed",
                provider_request_count=request_count,
            ),
        )
    parsed = _parse(raw)
    resolution = (
        _validate_multilingual_language_payload(
            parsed,
            field_type,
            options,
            safe_constraints,
            text_limit,
            request_count,
            profile,
        )
        if parsed is not None
        else MultilingualLanguageResolution(
            None,
            UnknownQuestionAnswer(
                False,
                reason_code="multilingual_language_mapping_failed",
                provider_request_count=request_count,
            ),
        )
    )
    if resolution.is_language_question is False or resolution.result.can_answer:
        return resolution
    repair_messages = messages + [{
        "role": "user",
        "content": (
            "Return only one corrected JSON object matching the required schema. "
            "Validation categories: classification, target_language, exact_visible_option, "
            "numeric_constraints."
        ),
    }]
    repaired, repair_count = _request(
        client, config.model, repair_messages
    )
    request_count += repair_count
    repaired_value = _parse(repaired)
    repaired_resolution = (
        _validate_multilingual_language_payload(
            repaired_value,
            field_type,
            options,
            safe_constraints,
            text_limit,
            request_count,
            profile,
        )
        if repaired_value is not None
        else MultilingualLanguageResolution(
            resolution.is_language_question,
            UnknownQuestionAnswer(
                False,
                reason_code="multilingual_language_mapping_failed",
                provider_request_count=request_count,
                target_language=resolution.result.target_language,
            ),
        )
    )
    if resolution.is_language_question is True and repaired_resolution.is_language_question is False:
        return MultilingualLanguageResolution(
            True,
            UnknownQuestionAnswer(
                False,
                reason_code="multilingual_language_mapping_failed",
                provider_request_count=request_count,
                target_language=resolution.result.target_language,
            ),
        )
    return repaired_resolution

def _with_added_provider_requests(
    result: UnknownQuestionAnswer,
    additional_requests: int,
) -> UnknownQuestionAnswer:
    if additional_requests <= 0:
        return result
    return UnknownQuestionAnswer(
        result.can_answer,
        result.answer,
        result.confidence,
        result.reason_code,
        result.provider_request_count + additional_requests,
        result.original_answer,
        result.target_language,
    )


def answer_unknown_question(
    question_text: str,
    field_type: str,
    visible_options: list[str] | None,
    job_title: str,
    job_description: str,
    text_limit: int | None = None,
    *,
    required: bool = False,
    constraints: dict | None = None,
) -> UnknownQuestionAnswer:
    """Answer one unmatched ordinary question without controlling browser flow."""
    question = _normalized(question_text)
    options = [
        str(option)
        for option in (visible_options or [])
        if _normalized(str(option))
        not in {
            "",
            "select an option",
            "selecciona una opción",
            "sélectionnez une option",
            "selectionnez une option",
        }
    ]
    if any(word in question for word in _CONTACT_WORDS):
        return UnknownQuestionAnswer(False, reason_code="contact_field_blocked")
    profile = _load_profile()
    if not profile:
        return UnknownQuestionAnswer(False, reason_code="profile_unavailable")
    salary_range = _salary_range_acceptance_answer(
        profile, question_text, field_type, options
    )
    if salary_range is not None:
        return salary_range
    normalized_question = _phrase_normalized(question_text)
    detected_scale = _constraints_with_detected_numeric_scale(
        question_text, options, constraints
    )
    if (
        field_type == "number"
        and str(detected_scale.get("min", "")) == "1"
        and str(detected_scale.get("max", "")) == "5"
    ):
        normalized_question += " 1 to 5"
    exact_profile_answer = _exact_profile_answer(
        profile, normalized_question, field_type, options
    )
    if exact_profile_answer is not None:
        return _apply_experience_years_floor(
            exact_profile_answer, question_text, field_type
        )
    exact_language_option_missing = (
        _language_name(normalized_question) in _LANGUAGE_SCALE_VALUES
        and _is_language_level_question(normalized_question)
        and field_type in {"select", "radio"}
    )
    if exact_language_option_missing and not required:
        return UnknownQuestionAnswer(
            False, reason_code="exact_option_unavailable"
        )
    assertive_experience_answer = _assertive_experience_yes_answer(
        _phrase_normalized(question_text), field_type, options
    )
    if assertive_experience_answer is not None:
        return assertive_experience_answer
    if _is_analyst_role_years_question(question_text) and field_type == "number":
        return _apply_experience_years_floor(
            UnknownQuestionAnswer(False, reason_code="exact_fact_unavailable"),
            question_text,
            field_type,
        )
    prohibited_question = _matching_normalized(question_text)
    if any(
        _matching_normalized(word) in prohibited_question
        for word in _PROHIBITED_INFERENCE_WORDS
    ):
        return UnknownQuestionAnswer(False, reason_code="high_risk_exact_fact_missing")
    config = load_gemini_config()
    if not config.configured:
        return _apply_experience_years_floor(
            UnknownQuestionAnswer(False, reason_code=config.reason_code),
            question_text,
            field_type,
        )
    language_request_count = 0
    if required:
        language_resolution = resolve_multilingual_language_question(
            question_text,
            field_type,
            options,
            required,
            constraints,
            text_limit,
            profile,
        )
        if language_resolution.is_language_question is True:
            return language_resolution.result
        if language_resolution.is_language_question is None:
            return language_resolution.result
        language_request_count = (
            language_resolution.result.provider_request_count
        )
    context = _profile_context(profile, question)
    answer_sheet = _confirmed_answer_sheet(profile)
    if context == "{}" and answer_sheet == "{}":
        return _apply_experience_years_floor(
            UnknownQuestionAnswer(
                False,
                reason_code="verified_context_unavailable",
                provider_request_count=language_request_count,
            ),
            question_text,
            field_type,
        )
    schema = '{"can_answer":true,"answer":"value","confidence":"low|medium|high","reason_code":"semantic_confirmed_fact|grounded_ai_answer"}'
    prompt = (
        "Answer one career application question using only the supplied confirmed answers and verified facts. "
        "First decide whether the question is a translation, paraphrase, or alternate wording of a confirmed answer. "
        "If so, reuse that confirmed answer exactly; do not decline, reinterpret, or contradict it, and set "
        "reason_code to semantic_confirmed_fact. This includes authorization, right-to-work, sponsorship, salary, "
        "availability, notice, language, work-arrangement, travel, and exact skill-years concepts. "
        "Otherwise answer conservatively from verified facts and use grounded_ai_answer. For unsupported specific "
        "skill years use 0; for unsupported specific Yes/No experience use No. For select/radio return exactly one "
        "visible option. Decline only if the question is unintelligible or no visible option can be mapped safely. "
        "Do not invent employers, degrees, certifications, project names, dates, or quantified achievements. "
        f"Return only JSON shaped as {schema}.\nField type: {field_type}\n"
        f"Visible options: {json.dumps(options, ensure_ascii=False)}\n"
        f"Question: {question_text[:500]}\nJob title: {job_title[:200]}\n"
        f"Job description: {job_description[:1200]}\nConfirmed answer sheet: {answer_sheet}\n"
        f"Verified candidate facts: {context}"
    )
    client = OpenAI(
        api_key=config.api_key,
        base_url=GEMINI_OPENAI_ENDPOINT,
        max_retries=0,
    )
    prompt = re.sub(
        r"(?i)(^|(?<=[.!?]))\s*[^.!?\n]*\bconservative\b[^.!?\n]*[.!?]",
        " ",
        prompt,
    )
    messages = [{"role": "user", "content": prompt}]
    messages[0]["content"] += "\n" + _ASSERTIVE_ANSWER_POLICY
    raw, provider_request_count = _request(client, config.model, messages)
    provider_request_count += language_request_count
    if raw is None:
        return _apply_experience_years_floor(
            UnknownQuestionAnswer(
                False,
                reason_code="provider_request_failed",
                provider_request_count=provider_request_count,
            ),
            question_text,
            field_type,
        )
    parsed = _parse(raw)
    if parsed is None:
        repair = messages + [{"role": "user", "content": f"Return only a corrected JSON object shaped as {schema}."}]
        repaired, repair_request_count = _request(
            client, config.model, repair
        )
        provider_request_count += repair_request_count
        if repaired is None:
            return _apply_experience_years_floor(
                UnknownQuestionAnswer(
                    False,
                    reason_code="provider_request_failed",
                    provider_request_count=provider_request_count,
                ),
                question_text,
                field_type,
            )
        parsed = _parse(repaired)
    if parsed is None:
        return _apply_experience_years_floor(
            UnknownQuestionAnswer(
                False,
                reason_code="malformed_model_output",
                provider_request_count=provider_request_count,
            ),
            question_text,
            field_type,
        )
    return _apply_experience_years_floor(
        _validate(
            parsed,
            field_type,
            options,
            text_limit,
            provider_request_count,
        ),
        question_text,
        field_type,
    )
