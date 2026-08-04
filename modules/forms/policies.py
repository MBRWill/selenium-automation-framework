"""Central English/Spanish truth and fallback policy classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import unicodedata

from modules.forms.models import FormField


class SemanticCategory(str, Enum):
    WORK_AUTHORIZATION = "work_authorization"
    SPONSORSHIP = "sponsorship"
    CITIZENSHIP = "citizenship"
    EU_CITIZENSHIP = "eu_citizenship"
    SECURITY_CLEARANCE = "security_clearance"
    CERTIFICATION_POSSESSION = "certification_possession"
    EDUCATION_POSSESSION = "education_possession"
    DRIVING_LICENCE_POSSESSION = "driving_licence_possession"
    EMPLOYMENT_HISTORY = "employment_history"
    LEGAL_CRIMINAL_DECLARATION = "legal_criminal_declaration"
    SALARY_EXACT = "salary_exact"
    LANGUAGE_EXACT_LEVEL = "language_exact_level"
    ORDINARY_EXPERIENCE = "ordinary_experience"
    ORDINARY_CAPABILITY = "ordinary_capability"
    ORDINARY_PREFERENCE = "ordinary_preference"
    COMMUTE = "commute"
    RELOCATION = "relocation"
    TRAVEL_WILLINGNESS = "travel_willingness"
    OPTIONAL_MARKETING_CONSENT = "optional_marketing_consent"
    REQUIRED_PROCEDURAL_ACKNOWLEDGEMENT = (
        "required_procedural_acknowledgement"
    )
    UNKNOWN = "unknown"


class TruthPolicy(str, Enum):
    EXACT_PROFILE = "exact_profile"
    DETERMINISTIC = "deterministic"
    ORDINARY = "ordinary"


@dataclass(frozen=True)
class PolicyDecision:
    category: SemanticCategory
    truth_policy: TruthPolicy
    profile_key: str | None
    deterministic_answer: str | bool | None
    allow_provider: bool
    allow_yes_no_default: bool
    reason_code: str

    @property
    def exact_only(self) -> bool:
        return self.truth_policy is TruthPolicy.EXACT_PROFILE


def normalize_question(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", without_marks.casefold()).split())


class SemanticPolicy:
    """Classify form semantics before profile/provider/default selection."""

    _EXACT_PROFILE_KEYS = {
        SemanticCategory.WORK_AUTHORIZATION: "legal.work_authorization",
        SemanticCategory.SPONSORSHIP: "legal.requires_sponsorship",
        SemanticCategory.CITIZENSHIP: "identity.citizenship",
        SemanticCategory.EU_CITIZENSHIP: "identity.eu_citizenship",
        SemanticCategory.SECURITY_CLEARANCE: "legal.security_clearance",
        SemanticCategory.CERTIFICATION_POSSESSION: "qualifications.certifications",
        SemanticCategory.EDUCATION_POSSESSION: "education.verified",
        SemanticCategory.DRIVING_LICENCE_POSSESSION: "qualifications.driving_licence",
        SemanticCategory.EMPLOYMENT_HISTORY: "employment.history",
        SemanticCategory.LEGAL_CRIMINAL_DECLARATION: "legal.criminal_declaration",
        SemanticCategory.SALARY_EXACT: "compensation.salary",
        SemanticCategory.LANGUAGE_EXACT_LEVEL: "languages.verified_level",
    }

    def classify(self, field: FormField) -> PolicyDecision:
        text = normalize_question(field.question)
        category = self._category(text, field.required)

        if field.exact_fact_only:
            return self._exact(
                category,
                field.profile_key or self._EXACT_PROFILE_KEYS.get(category),
                "field_marked_exact_only",
            )
        if category in self._EXACT_PROFILE_KEYS:
            return self._exact(
                category,
                field.profile_key or self._EXACT_PROFILE_KEYS[category],
                f"{category.value}_requires_verified_profile",
            )
        if category is SemanticCategory.OPTIONAL_MARKETING_CONSENT:
            return PolicyDecision(
                category=category,
                truth_policy=TruthPolicy.DETERMINISTIC,
                profile_key=None,
                deterministic_answer=False,
                allow_provider=False,
                allow_yes_no_default=False,
                reason_code="optional_marketing_declined",
            )
        if category is SemanticCategory.REQUIRED_PROCEDURAL_ACKNOWLEDGEMENT:
            return PolicyDecision(
                category=category,
                truth_policy=TruthPolicy.DETERMINISTIC,
                profile_key=None,
                deterministic_answer=True,
                allow_provider=False,
                allow_yes_no_default=False,
                reason_code="required_procedural_acknowledged",
            )
        return PolicyDecision(
            category=category,
            truth_policy=TruthPolicy.ORDINARY,
            profile_key=field.profile_key,
            deterministic_answer=None,
            allow_provider=True,
            allow_yes_no_default=field.allow_yes_no_default,
            reason_code=f"{category.value}_ordinary_policy",
        )

    @staticmethod
    def _exact(
        category: SemanticCategory,
        profile_key: str | None,
        reason_code: str,
    ) -> PolicyDecision:
        return PolicyDecision(
            category=category,
            truth_policy=TruthPolicy.EXACT_PROFILE,
            profile_key=profile_key,
            deterministic_answer=None,
            allow_provider=False,
            allow_yes_no_default=False,
            reason_code=reason_code,
        )

    def _category(self, text: str, required: bool) -> SemanticCategory:
        if self._contains(
            text,
            "criminal",
            "conviction",
            "felony",
            "legal declaration",
            "conflict of interest",
            "non compete",
            "government official",
            "delito",
            "antecedentes penales",
            "conflicto de intereses",
            "declaracion legal",
        ):
            return SemanticCategory.LEGAL_CRIMINAL_DECLARATION
        if self._contains(text, "eu citizen", "european union citizen", "ciudadano de la ue", "ciudadania ue"):
            return SemanticCategory.EU_CITIZENSHIP
        if self._contains(text, "sponsor", "sponsorship", "patrocinio", "visado de trabajo"):
            return SemanticCategory.SPONSORSHIP
        if self._contains(text, "authorized to work", "authorised to work", "legally work", "work authorization", "work authorisation", "permiso de trabajo", "autorizado para trabajar", "derecho a trabajar"):
            return SemanticCategory.WORK_AUTHORIZATION
        if self._contains(text, "citizen", "citizenship", "nationality", "ciudadano", "ciudadania", "nacionalidad"):
            return SemanticCategory.CITIZENSHIP
        if self._contains(text, "security clearance", "government clearance", "habilitacion de seguridad", "autorizacion de seguridad"):
            return SemanticCategory.SECURITY_CLEARANCE
        if self._contains(text, "driver license", "driving licence", "driving license", "carnet de conducir", "permiso de conducir"):
            return SemanticCategory.DRIVING_LICENCE_POSSESSION
        if self._candidate_possession(text) and self._contains(text, "certification", "certificate", "certified", "certificacion", "certificado"):
            return SemanticCategory.CERTIFICATION_POSSESSION
        if self._candidate_possession(text) and self._contains(text, "degree", "diploma", "bachelor", "master", "doctorate", "titulo universitario", "licenciatura", "grado universitario"):
            return SemanticCategory.EDUCATION_POSSESSION
        if self._contains(text, "have you worked", "ever worked", "ever been employed", "previously employed", "employment history", "worked for", "has trabajado", "historial laboral", "empleado anteriormente"):
            return SemanticCategory.EMPLOYMENT_HISTORY
        if self._contains(text, "salary", "compensation", "salario", "remuneracion"):
            return SemanticCategory.SALARY_EXACT
        if self._contains(text, "language level", "level of english", "level of spanish", "english proficiency", "spanish proficiency", "do you speak english", "do you speak spanish", "fluent in", "nivel de idioma", "nivel de ingles", "nivel de espanol", "hablas ingles", "hablas espanol"):
            return SemanticCategory.LANGUAGE_EXACT_LEVEL
        if self._contains(text, "marketing", "newsletter", "promotional", "comunicaciones comerciales", "publicidad"):
            return SemanticCategory.OPTIONAL_MARKETING_CONSENT
        if required and self._contains(text, "acknowledge", "confirm the information", "certify the information", "confirmo la informacion", "declaro que la informacion", "acepto continuar"):
            return SemanticCategory.REQUIRED_PROCEDURAL_ACKNOWLEDGEMENT
        if self._contains(text, "commute", "commuting", "desplazarte", "desplazamiento"):
            return SemanticCategory.COMMUTE
        if self._contains(text, "relocate", "relocation", "reubicarte", "mudarte"):
            return SemanticCategory.RELOCATION
        if self._contains(text, "willing to travel", "travel requirement", "dispuesto a viajar", "disponibilidad para viajar"):
            return SemanticCategory.TRAVEL_WILLINGNESS
        if self._contains(text, "years of experience", "experience with", "experiencia con", "anos de experiencia"):
            return SemanticCategory.ORDINARY_EXPERIENCE
        if self._contains(text, "comfortable with", "able to", "can you", "capable of", "puedes", "capaz de"):
            return SemanticCategory.ORDINARY_CAPABILITY
        if self._contains(text, "prefer", "preference", "preferred", "prefieres", "preferencia"):
            return SemanticCategory.ORDINARY_PREFERENCE
        return SemanticCategory.UNKNOWN

    @staticmethod
    def _contains(text: str, *phrases: str) -> bool:
        return any(phrase in text for phrase in phrases)

    @staticmethod
    def _candidate_possession(text: str) -> bool:
        return any(phrase in text for phrase in (
            "do you have",
            "have you obtained",
            "are you certified",
            "do you hold",
            "tienes",
            "posees",
            "cuentas con",
            "estas certificado",
        ))
