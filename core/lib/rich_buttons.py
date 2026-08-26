# SPDX-License-Identifier: MIT

"""Shared rich page-button specifications, validation, and HTML rendering."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from html import escape as html_escape
from typing import Any

_RICH_BUTTON_STYLES = frozenset({"primary", "danger", "success", "link"})
_RICH_BUTTON_ALIGNMENTS = frozenset({"left", "center", "right"})
_RICH_BUTTON_ATTRS = {
    "callback_data": frozenset({"data", "requires-password"}),
    "url": frozenset({"url"}),
    "web_app": frozenset({"url"}),
    "switch_inline_query": frozenset({"query"}),
    "switch_inline_query_current_chat": frozenset({"query"}),
    "copy_text": frozenset({"text"}),
    "disabled": frozenset(),
    "game": frozenset(),
}


@dataclass(frozen=True, slots=True)
class RichCallbackButton:
    """A callback button rendered inside a Telegram rich-message page."""

    text: str
    token: str
    style: str | None = None


@dataclass(frozen=True, slots=True)
class RichPageButton:
    """An immutable non-callback Telegram rich page-button specification."""

    text: str
    type: str
    attrs: Mapping[str, str] | None = None
    style: str | None = None


@dataclass(frozen=True, slots=True)
class RichButtonRow:
    """A row of :class:`RichCallbackButton` objects with page alignment."""

    buttons: tuple[RichCallbackButton | RichPageButton, ...]
    align: str = "center"


def validate_rich_button(text: str, token: str, style: str | None) -> None:
    if not isinstance(text, str) or not text:
        raise ValueError("rich button text must be a non-empty string")
    if not isinstance(token, str) or not 1 <= len(token.encode("utf-8")) <= 64:
        raise ValueError("rich callback token must be 1..64 UTF-8 bytes")
    if style is not None and style not in _RICH_BUTTON_STYLES:
        raise ValueError(
            "rich button style must be one of: primary, danger, success, link"
        )


def render_rich_button(button: RichCallbackButton) -> str:
    """Render one validated rich callback button without a row wrapper."""
    validate_rich_button(button.text, button.token, button.style)
    return _render_button(
        "callback_data", button.text, {"data": button.token}, button.style
    )


def validate_rich_page_button(button: RichPageButton) -> None:
    validate_rich_button(button.text, "x", button.style)
    if button.type not in _RICH_BUTTON_ATTRS:
        raise ValueError(f"unsupported rich page-button type: {button.type}")
    attrs = button.attrs or {}
    if not isinstance(attrs, Mapping) or set(attrs) - _RICH_BUTTON_ATTRS[button.type]:
        raise ValueError(f"invalid attributes for rich page-button type: {button.type}")
    for name, value in attrs.items():
        if not isinstance(value, str):
            raise TypeError(f"rich page-button attribute {name} must be a string")
    if button.type in {"url", "web_app"}:
        url = attrs.get("url", "")
        if not url.startswith(("https://", "tg://")):
            raise ValueError("rich page-button URL must use https:// or tg://")
    if button.type == "callback_data":
        validate_rich_button(button.text, attrs.get("data", ""), button.style)


def _render_button(
    button_type: str, text: str, attrs: Mapping[str, str], style: str | None
) -> str:
    style_attr = f' style="{html_escape(style, quote=True)}"' if style else ""
    attrs_html = "".join(
        f' {name}="{html_escape(value, quote=True)}"' for name, value in attrs.items()
    )
    return (
        f'<tg-button type="{html_escape(button_type, quote=True)}"'
        f"{attrs_html}{style_attr}>{html_escape(text, quote=True)}</tg-button>"
    )


def render_rich_page_button(button: RichPageButton) -> str:
    validate_rich_page_button(button)
    return _render_button(button.type, button.text, button.attrs or {}, button.style)


def normalize_rich_buttons(rich_buttons: Any) -> list[RichButtonRow]:
    """Normalize rich callback specs into validated page-button rows."""
    if isinstance(rich_buttons, RichButtonRow):
        rows: list[Any] = [rich_buttons]
    elif isinstance(rich_buttons, (list, tuple)):
        if not rich_buttons:
            raise ValueError("rich_buttons cannot be empty")
        if all(
            isinstance(button, (RichCallbackButton, RichPageButton))
            for button in rich_buttons
        ):
            rows = [RichButtonRow(tuple(rich_buttons))]
        else:
            rows = list(rich_buttons)
    else:
        raise TypeError("rich_buttons must be rich button specs or rows")

    normalized = []
    for row in rows:
        if isinstance(row, RichButtonRow):
            buttons, align = row.buttons, row.align
        elif isinstance(row, (list, tuple)):
            buttons, align = tuple(row), "center"
        else:
            raise TypeError("rich_buttons accepts only Button.rich.inline specs")
        if not buttons:
            raise ValueError("rich button rows cannot be empty")
        if len(buttons) > 8:
            raise ValueError("rich button rows support at most 8 buttons")
        if align not in _RICH_BUTTON_ALIGNMENTS:
            raise ValueError("rich button row align must be left, center or right")
        if not all(
            isinstance(button, (RichCallbackButton, RichPageButton))
            for button in buttons
        ):
            raise TypeError("rich_buttons accepts only Button.rich.inline specs")
        for button in buttons:
            if isinstance(button, RichCallbackButton):
                validate_rich_button(button.text, button.token, button.style)
            else:
                validate_rich_page_button(button)
        normalized.append(RichButtonRow(tuple(buttons), align=align))
    return normalized


def render_rich_buttons(rows: Sequence[RichButtonRow]) -> str:
    return "\n".join(
        f'<tg-button-row align="{html_escape(row.align, quote=True)}">'
        f"{''.join(render_rich_button(button) if isinstance(button, RichCallbackButton) else render_rich_page_button(button) for button in row.buttons)}"
        "</tg-button-row>"
        for row in rows
    )


def append_rich_buttons(html: str, rich_buttons: Any) -> str:
    """Append validated page-button rows to HTML rich text."""
    if not isinstance(html, str):
        raise TypeError("rich_text must be a string when rich_buttons are used")
    return f"{html}\n{render_rich_buttons(normalize_rich_buttons(rich_buttons))}"
