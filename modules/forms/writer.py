"""Bounded, type-aware field writing with live verification."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

from modules.forms.controls import FieldControl, FieldControlProvider
from modules.forms.models import (
    AnswerStatus,
    ControlOption,
    ControlSnapshot,
    FieldConstraints,
    FieldKind,
    WriteRequest,
    WriteResult,
    WriteStatus,
)
from modules.forms.policies import normalize_question


class FieldWriter:
    """Write one resolver result, re-querying and retrying at most once."""

    def write(
        self,
        request: WriteRequest,
        controls: FieldControlProvider,
    ) -> WriteResult:
        answer = request.answer_result
        field = request.extracted_field.field
        raw_value = answer.value
        if not answer.accepted or raw_value is None:
            return self._result(
                WriteStatus.FAILED,
                raw_value,
                None,
                False,
                0,
                "answer_not_accepted",
            )

        initial = controls.requery(request.extracted_field.locator)
        if initial is None:
            return self._result(
                WriteStatus.RETRY_REQUIRED,
                raw_value,
                None,
                False,
                0,
                "control_not_available",
            )
        initial_snapshot = initial.snapshot()
        intended, reason_code = self._compatible_value(
            field.kind,
            raw_value,
            initial_snapshot,
            field.required,
        )
        if intended is None:
            return self._result(
                WriteStatus.FAILED,
                raw_value,
                self._current_value(initial_snapshot, field.kind),
                False,
                0,
                reason_code,
            )

        if answer.status is AnswerStatus.PRESERVED:
            current = self._current_value(initial_snapshot, field.kind)
            if self._values_match(field.kind, current, intended) and self._valid(
                initial_snapshot,
                field.kind,
                intended,
                field.required,
            ):
                return self._result(
                    WriteStatus.SKIPPED_PRESERVED,
                    intended,
                    current,
                    False,
                    0,
                    "preserved_value_still_matches",
                )
            return self._result(
                WriteStatus.RETRY_REQUIRED,
                intended,
                current,
                False,
                0,
                "preserved_value_changed",
            )

        changed = False
        last_verified: str | bool | None = None
        failure_reason = "write_verification_failed"
        for retry_count in (0, 1):
            control = controls.requery(request.extracted_field.locator)
            if control is None:
                failure_reason = "control_not_available_after_requery"
                continue
            snapshot = control.snapshot()
            intended, reason_code = self._compatible_value(
                field.kind,
                raw_value,
                snapshot,
                field.required,
            )
            if intended is None:
                return self._result(
                    WriteStatus.FAILED,
                    raw_value,
                    self._current_value(snapshot, field.kind),
                    changed,
                    retry_count,
                    reason_code,
                )
            current = self._current_value(snapshot, field.kind)
            if self._values_match(field.kind, current, intended) and self._valid(
                snapshot,
                field.kind,
                intended,
                field.required,
            ):
                return self._result(
                    WriteStatus.VERIFIED,
                    intended,
                    current,
                    changed,
                    retry_count,
                    "value_already_verified" if not changed else "write_verified",
                )
            try:
                self._write_value(control, snapshot, field.kind, intended)
                changed = True
            except Exception:
                failure_reason = "control_write_failed"
                continue

            verification_control = controls.requery(
                request.extracted_field.locator
            )
            if verification_control is None:
                failure_reason = "verification_control_not_available"
                continue
            verified_snapshot = verification_control.snapshot()
            last_verified = self._current_value(verified_snapshot, field.kind)
            if self._values_match(
                field.kind, last_verified, intended
            ) and self._valid(
                verified_snapshot,
                field.kind,
                intended,
                field.required,
            ):
                return self._result(
                    WriteStatus.VERIFIED,
                    intended,
                    last_verified,
                    changed,
                    retry_count,
                    "write_verified",
                )
            failure_reason = "write_verification_failed"

        return self._result(
            WriteStatus.FAILED,
            intended,
            last_verified,
            changed,
            1,
            failure_reason,
        )

    def _write_value(
        self,
        control: FieldControl,
        snapshot: ControlSnapshot,
        kind: FieldKind,
        intended: str | bool,
    ) -> None:
        if kind in {FieldKind.TEXT, FieldKind.TEXTAREA, FieldKind.NUMBER}:
            control.clear_text()
            control.enter_text(str(intended))
            return
        if kind is FieldKind.SELECT:
            option = self._matching_option(intended, snapshot.options)
            if option is None:
                raise ValueError("select option unavailable")
            control.select_option(option.value)
            return
        if kind is FieldKind.RADIO:
            option = self._matching_option(intended, snapshot.options)
            if option is None:
                raise ValueError("radio option unavailable")
            control.click_choice(option.value)
            return
        if kind is FieldKind.CHECKBOX:
            control.click_choice(bool(intended))
            return
        raise ValueError("unsupported field kind")

    def _compatible_value(
        self,
        kind: FieldKind,
        value: str | bool,
        snapshot: ControlSnapshot,
        required: bool,
    ) -> tuple[str | bool | None, str]:
        if kind is FieldKind.NUMBER:
            number = self._decimal(value)
            if number is None:
                return None, "number_answer_not_numeric"
            if not self._number_valid(number, snapshot.constraints):
                return None, "number_answer_violates_constraints"
            return self._decimal_text(number), "number_answer_compatible"
        if kind in {FieldKind.TEXT, FieldKind.TEXTAREA}:
            if isinstance(value, bool):
                return None, "text_answer_wrong_type"
            text = str(value)
            if required and not text.strip():
                return None, "required_text_answer_missing"
            if not self._text_valid(text, snapshot.constraints):
                return None, "text_answer_violates_constraints"
            return text, "text_answer_compatible"
        if kind in {FieldKind.SELECT, FieldKind.RADIO}:
            option = self._matching_option(value, snapshot.options)
            if option is None:
                return None, "visible_enabled_option_not_found"
            return option.text, "option_answer_compatible"
        if kind is FieldKind.CHECKBOX:
            if not isinstance(value, bool):
                return None, "checkbox_answer_not_boolean"
            if required and value is False:
                return None, "required_checkbox_cannot_be_false"
            return value, "checkbox_answer_compatible"
        return None, "unsupported_field_kind"

    def _valid(
        self,
        snapshot: ControlSnapshot,
        kind: FieldKind,
        intended: str | bool,
        required: bool,
    ) -> bool:
        validity = snapshot.validity
        if (
            not validity.browser_valid
            or validity.aria_invalid is True
            or validity.value_missing
            or validity.type_mismatch
            or validity.range_underflow
            or validity.range_overflow
            or validity.step_mismatch
            or validity.too_short
            or validity.too_long
        ):
            return False
        if kind is FieldKind.NUMBER:
            number = self._decimal(intended)
            return number is not None and self._number_valid(
                number, snapshot.constraints
            )
        if kind in {FieldKind.TEXT, FieldKind.TEXTAREA}:
            return (
                (not required or bool(str(intended).strip()))
                and self._text_valid(str(intended), snapshot.constraints)
            )
        if kind in {FieldKind.SELECT, FieldKind.RADIO}:
            return self._matching_option(intended, snapshot.options) is not None
        if kind is FieldKind.CHECKBOX:
            return isinstance(intended, bool) and (not required or intended)
        return False

    def _current_value(
        self,
        snapshot: ControlSnapshot,
        kind: FieldKind,
    ) -> str | bool | None:
        if kind is FieldKind.CHECKBOX:
            return bool(snapshot.checked)
        if kind is FieldKind.RADIO:
            selected = next(
                (
                    option
                    for option in snapshot.options
                    if option.visible
                    and option.enabled
                    and option.selected
                    and not option.placeholder
                ),
                None,
            )
            if selected is not None:
                return selected.text
            return None
        if kind is FieldKind.SELECT:
            selected = next(
                (
                    option
                    for option in snapshot.options
                    if option.visible
                    and option.enabled
                    and option.selected
                    and not option.placeholder
                ),
                None,
            )
            if selected is not None:
                return selected.text
            matched = self._matching_option(
                snapshot.current_value, snapshot.options
            )
            return matched.text if matched is not None else None
        if kind is FieldKind.NUMBER:
            number = self._decimal(snapshot.current_value)
            return self._decimal_text(number) if number is not None else None
        if snapshot.current_value is None or isinstance(snapshot.current_value, bool):
            return None
        return str(snapshot.current_value)

    def _matching_option(
        self,
        value: str | bool | None,
        options: tuple[ControlOption, ...],
    ) -> ControlOption | None:
        if value is None or isinstance(value, bool):
            return None
        wanted = normalize_question(str(value))
        positive = {"yes", "si", "oui", "ja"}
        negative = {"no", "non", "nein"}
        aliases = positive if wanted in positive else negative if wanted in negative else {wanted}
        return next(
            (
                option
                for option in options
                if option.visible
                and option.enabled
                and not option.placeholder
                and (
                    normalize_question(option.text) in aliases
                    or normalize_question(option.value) in aliases
                )
            ),
            None,
        )

    @staticmethod
    def _values_match(
        kind: FieldKind,
        current: str | bool | None,
        intended: str | bool,
    ) -> bool:
        if kind is FieldKind.CHECKBOX:
            return isinstance(current, bool) and current is intended
        if kind is FieldKind.NUMBER:
            current_number = FieldWriter._decimal(current)
            intended_number = FieldWriter._decimal(intended)
            return (
                current_number is not None
                and intended_number is not None
                and current_number == intended_number
            )
        return normalize_question(str(current or "")) == normalize_question(
            str(intended)
        )

    @staticmethod
    def _decimal(value: str | bool | None) -> Decimal | None:
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
        return number if number.is_finite() else None

    @staticmethod
    def _number_valid(
        number: Decimal,
        constraints: FieldConstraints,
    ) -> bool:
        if constraints.min_value is not None and number < constraints.min_value:
            return False
        if constraints.max_value is not None and number > constraints.max_value:
            return False
        if constraints.step is not None:
            base = constraints.min_value or Decimal("0")
            if (number - base) % constraints.step != 0:
                return False
        return True

    @staticmethod
    def _text_valid(text: str, constraints: FieldConstraints) -> bool:
        if constraints.min_length is not None and len(text) < constraints.min_length:
            return False
        if constraints.max_length is not None and len(text) > constraints.max_length:
            return False
        if constraints.pattern is not None:
            try:
                return re.fullmatch(constraints.pattern, text) is not None
            except re.error:
                return False
        return True

    @staticmethod
    def _decimal_text(number: Decimal) -> str:
        normalized = format(number, "f")
        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")
        return normalized or "0"

    @staticmethod
    def _result(
        status: WriteStatus,
        attempted_value: str | bool | None,
        verified_value: str | bool | None,
        changed: bool,
        retry_count: int,
        reason_code: str,
    ) -> WriteResult:
        return WriteResult(
            status=status,
            attempted_value=attempted_value,
            verified_value=verified_value,
            changed=changed,
            retry_count=retry_count,
            reason_code=reason_code,
        )
