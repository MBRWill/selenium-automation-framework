"""Unified extraction of control snapshots into form domain models."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json

from modules.forms.controls import FieldControl
from modules.forms.models import (
    ControlOption,
    ControlSnapshot,
    ExtractedField,
    ExtractionContext,
    FieldKind,
    FieldLocator,
    FormField,
    ValidationIssue,
    ValidationIssueKind,
    ValidationState,
)
from modules.forms.policies import normalize_question


class FieldExtractor:
    """Convert a safe immutable snapshot into a stable ``FormField``."""

    _STABLE_ATTRIBUTE_NAMES = frozenset({
        "id",
        "name",
        "type",
        "role",
        "autocomplete",
        "aria-describedby",
        "data-test-id",
        "data-test-form-element",
    })
    _PLACEHOLDERS = frozenset({
        "select an option",
        "choose an option",
        "selecciona una opcion",
        "seleccione una opcion",
        "selectionnez une option",
    })

    def extract(
        self,
        control: FieldControl,
        context: ExtractionContext | None = None,
    ) -> ExtractedField:
        snapshot = control.snapshot()
        context = context or ExtractionContext()
        kind = self._field_kind(snapshot)
        question = self._question(snapshot)
        normalized_question = normalize_question(question)
        options = self._selectable_options(snapshot.options)
        existing_value = self._existing_value(snapshot, kind, options)
        stable_attributes = tuple(sorted(
            (name, value)
            for name, value in snapshot.attributes
            if name in self._STABLE_ATTRIBUTE_NAMES and value.strip()
        ))
        locator = FieldLocator(
            container_selector=snapshot.container_selector,
            control_selector=snapshot.control_selector,
            option_selectors=tuple(
                option.selector for option in options if option.selector
            ),
            stable_attributes=stable_attributes,
        )
        visible_options = tuple(option.text for option in options)
        field_key = self._stable_field_key(
            normalized_question=normalized_question,
            kind=kind,
            stable_attributes=stable_attributes,
            visible_options=visible_options,
            context=context,
        )
        validation_state = self._validation_state(
            snapshot=snapshot,
            kind=kind,
            existing_value=existing_value,
        )
        field = FormField(
            field_key=field_key,
            kind=kind,
            question=question,
            required=snapshot.required,
            existing_value=existing_value,
            constraints=snapshot.constraints,
            visible_options=visible_options,
            job_id=context.job_id,
            company=context.company,
            job_title=context.job_title,
        )
        return ExtractedField(
            field=field,
            locator=locator,
            normalized_question=normalized_question,
            validation_state=validation_state,
            safe_metadata=(
                ("tag_name", snapshot.tag_name.casefold()),
                ("input_type", snapshot.input_type.casefold()),
                ("option_count", str(len(visible_options))),
            ),
        )

    def validation_issues(
        self,
        extracted: ExtractedField,
    ) -> tuple[ValidationIssue, ...]:
        """Translate current browser validity into future repair inputs."""
        field = extracted.field
        state = extracted.validation_state
        issue_kinds: list[ValidationIssueKind] = []
        if state.option_required:
            issue_kinds.append(ValidationIssueKind.OPTION_REQUIRED)
        elif state.required_missing:
            issue_kinds.append(ValidationIssueKind.MISSING_VALUE)
        if state.type_mismatch:
            issue_kinds.append(ValidationIssueKind.WRONG_TYPE)
        if state.range_underflow:
            issue_kinds.append(ValidationIssueKind.BELOW_MINIMUM)
        if state.range_overflow:
            issue_kinds.append(ValidationIssueKind.ABOVE_MAXIMUM)
        if state.step_mismatch:
            issue_kinds.append(ValidationIssueKind.STEP_MISMATCH)
        if state.too_short:
            issue_kinds.append(ValidationIssueKind.TEXT_TOO_SHORT)
        if state.too_long:
            issue_kinds.append(ValidationIssueKind.TEXT_TOO_LONG)
        if (
            not state.browser_valid
            and not issue_kinds
        ):
            issue_kinds.append(ValidationIssueKind.UNKNOWN_VALIDATION_ERROR)
        return tuple(
            ValidationIssue(
                field_key=field.field_key,
                issue_kind=kind,
                message=state.validation_message,
                rejected_value=field.existing_value,
                constraints=field.constraints,
                visible_options=field.visible_options,
            )
            for kind in issue_kinds
        )

    @staticmethod
    def _field_kind(snapshot: ControlSnapshot) -> FieldKind:
        tag = snapshot.tag_name.casefold().strip()
        input_type = snapshot.input_type.casefold().strip()
        if tag == "textarea":
            return FieldKind.TEXTAREA
        if tag == "select":
            return FieldKind.SELECT
        if input_type == "number":
            return FieldKind.NUMBER
        if input_type == "radio":
            return FieldKind.RADIO
        if input_type == "checkbox":
            return FieldKind.CHECKBOX
        return FieldKind.TEXT

    @staticmethod
    def _question(snapshot: ControlSnapshot) -> str:
        attributes = dict(snapshot.attributes)
        candidates = (
            *snapshot.labels,
            attributes.get("aria-label", ""),
            snapshot.accessible_text,
        )
        for candidate in candidates:
            cleaned = " ".join(candidate.split())
            if cleaned:
                return cleaned
        return "Unlabelled field"

    def _selectable_options(
        self,
        options: tuple[ControlOption, ...],
    ) -> tuple[ControlOption, ...]:
        return tuple(
            option
            for option in options
            if option.visible
            and option.enabled
            and not option.placeholder
            and normalize_question(option.text) not in self._PLACEHOLDERS
        )

    def _existing_value(
        self,
        snapshot: ControlSnapshot,
        kind: FieldKind,
        options: tuple[ControlOption, ...],
    ) -> str | bool | None:
        if kind is FieldKind.CHECKBOX:
            return bool(snapshot.checked)
        if kind is FieldKind.RADIO:
            selected = next((option for option in options if option.selected), None)
            return selected.text if selected is not None else None
        if kind is FieldKind.SELECT:
            selected = next((option for option in options if option.selected), None)
            if selected is None:
                selected = self._match_option(snapshot.current_value, options)
            return selected.text if selected is not None else None
        if kind is FieldKind.NUMBER:
            return self._numeric_text(snapshot.current_value)
        if snapshot.current_value is None or isinstance(snapshot.current_value, bool):
            return None
        value = str(snapshot.current_value)
        return value if value.strip() else None

    def _validation_state(
        self,
        *,
        snapshot: ControlSnapshot,
        kind: FieldKind,
        existing_value: str | bool | None,
    ) -> ValidationState:
        validity = snapshot.validity
        required_missing = snapshot.required and self._missing_value(
            existing_value, kind
        )
        type_mismatch = validity.type_mismatch or (
            kind is FieldKind.NUMBER
            and snapshot.current_value not in {None, ""}
            and existing_value is None
        )
        option_required = (
            required_missing or validity.value_missing
        ) and kind in {FieldKind.SELECT, FieldKind.RADIO}
        browser_valid = (
            validity.browser_valid
            and not required_missing
            and not validity.value_missing
            and not type_mismatch
            and not validity.range_underflow
            and not validity.range_overflow
            and not validity.step_mismatch
            and not validity.too_short
            and not validity.too_long
        )
        aria_invalid = validity.aria_invalid
        if aria_invalid is None:
            raw_aria_invalid = dict(snapshot.attributes).get("aria-invalid")
            if raw_aria_invalid is not None:
                aria_invalid = raw_aria_invalid.casefold() == "true"
        return ValidationState(
            browser_valid=browser_valid,
            validation_message=" ".join(validity.validation_message.split()),
            aria_invalid=aria_invalid,
            required_missing=required_missing or validity.value_missing,
            type_mismatch=type_mismatch,
            range_underflow=validity.range_underflow,
            range_overflow=validity.range_overflow,
            step_mismatch=validity.step_mismatch,
            too_short=validity.too_short,
            too_long=validity.too_long,
            option_required=option_required,
        )

    @staticmethod
    def _missing_value(
        value: str | bool | None,
        kind: FieldKind,
    ) -> bool:
        if kind is FieldKind.CHECKBOX:
            return value is not True
        return value is None or (isinstance(value, str) and not value.strip())

    @staticmethod
    def _numeric_text(value: str | bool | None) -> str | None:
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
        if not number.is_finite():
            return None
        normalized = format(number, "f")
        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")
        return normalized or "0"

    @staticmethod
    def _match_option(
        value: str | bool | None,
        options: tuple[ControlOption, ...],
    ) -> ControlOption | None:
        if value is None:
            return None
        wanted = normalize_question(str(value))
        return next(
            (
                option
                for option in options
                if wanted in {
                    normalize_question(option.text),
                    normalize_question(option.value),
                }
            ),
            None,
        )

    @staticmethod
    def _stable_field_key(
        *,
        normalized_question: str,
        kind: FieldKind,
        stable_attributes: tuple[tuple[str, str], ...],
        visible_options: tuple[str, ...],
        context: ExtractionContext,
    ) -> str:
        identity = {
            "application_id": context.application_id,
            "job_id": context.job_id,
            "question": normalized_question,
            "kind": kind.value,
            "stable_attributes": stable_attributes,
            "visible_options": tuple(
                normalize_question(option) for option in visible_options
            ),
        }
        encoded = json.dumps(
            identity,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        return f"{kind.value}:{digest[:24]}"
