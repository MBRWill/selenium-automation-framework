"""Minimal control interaction boundary for extraction and field writing."""

from __future__ import annotations

from typing import Protocol

from modules.forms.models import ControlSnapshot, FieldLocator


class FieldControl(Protocol):
    """Read or mutate one form control without exposing a browser driver."""

    def snapshot(self) -> ControlSnapshot:
        ...

    def clear_text(self) -> None:
        ...

    def enter_text(self, value: str) -> None:
        ...

    def select_option(self, option_value: str) -> None:
        ...

    def click_choice(self, option_value: str | bool) -> None:
        ...


class FieldControlProvider(Protocol):
    """Re-query a live control after page-owned DOM changes."""

    def requery(self, locator: FieldLocator) -> FieldControl | None:
        ...
