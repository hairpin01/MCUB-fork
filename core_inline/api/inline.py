# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from telethon import Button

CallbackArgs = list[Any] | tuple[Any, ...] | None
CallbackKwargs = dict[str, Any] | None


def _with_emoji(button: dict[str, Any], emoji: str | None) -> dict[str, Any]:
    if emoji:
        button["emoji"] = emoji
    return button


def get_button_emoji(btn: Any) -> str | None:
    if hasattr(btn, "style") and btn.style:
        if hasattr(btn.style, "icon") and btn.style.icon:
            return str(btn.style.icon)
    return None


@dataclass(frozen=True)
class InlineButton:
    """Small declarative button model for inline keyboards.

    This is the readable, MCUB-friendly layer for inline code: modules may build
    buttons as objects instead of remembering raw Telegram dict keys. Existing
    dict buttons and Telethon ``Button.*`` objects remain supported.
    """

    text: str
    type: str = "callback"
    data: str | None = None
    url: str | None = None
    query: str = ""
    hint: str = ""
    emoji: str | None = None
    same_peer: bool = False

    @classmethod
    def callback(
        cls,
        text: str,
        data: str,
        *,
        emoji: str | None = None,
    ) -> "InlineButton":
        return cls(text=text, type="callback", data=data, emoji=emoji)

    @classmethod
    def url_button(
        cls,
        text: str,
        url: str,
        *,
        emoji: str | None = None,
    ) -> "InlineButton":
        return cls(text=text, type="url", url=url, emoji=emoji)

    @classmethod
    def switch(
        cls,
        text: str,
        query: str,
        *,
        hint: str = "",
        same_peer: bool = False,
        emoji: str | None = None,
    ) -> "InlineButton":
        return cls(
            text=text,
            type="switch",
            query=query,
            hint=hint,
            same_peer=same_peer,
            emoji=emoji,
        )

    @classmethod
    def phone(cls, text: str, *, emoji: str | None = None) -> "InlineButton":
        return cls(text=text, type="phone", emoji=emoji)

    @classmethod
    def location(cls, text: str, *, emoji: str | None = None) -> "InlineButton":
        return cls(text=text, type="location", emoji=emoji)

    @classmethod
    def game(cls, text: str, *, emoji: str | None = None) -> "InlineButton":
        return cls(text=text, type="game", emoji=emoji)

    def to_dict(self) -> dict[str, Any]:
        if self.type == "callback":
            return build_button_callback(self.text, self.data or "", self.emoji)
        if self.type == "url":
            return build_button_url(self.text, self.url or "", self.emoji)
        if self.type == "switch":
            return build_button_switch(
                self.text,
                self.query,
                self.hint,
                self.emoji,
                same_peer=self.same_peer,
            )
        if self.type == "phone":
            return build_button_phone(self.text, self.emoji)
        if self.type == "location":
            return build_button_location(self.text, self.emoji)
        if self.type == "game":
            return build_button_game(self.text, self.emoji)
        return _with_emoji({"text": self.text}, self.emoji)


@dataclass
class InlineKeyboard:
    """Declarative inline keyboard builder."""

    rows: list[list[Any]] = field(default_factory=list)

    def row(self, *buttons: Any) -> "InlineKeyboard":
        self.rows.append(list(buttons))
        return self

    def add(self, button: Any, *, new_row: bool = False) -> "InlineKeyboard":
        if new_row or not self.rows:
            self.rows.append([button])
        else:
            self.rows[-1].append(button)
        return self

    def to_dict(self) -> dict[str, Any]:
        return build_inline_keyboard(self.rows)


class CodeInline:
    """Readable facade for common inline operations.

    Use this when module code needs a small, understandable inline flow:

    ```python
    ui = CodeInline(kernel, ttl=600)
    buttons = ui.keyboard().row(
        ui.action("Save", self._save, args=[item_id]),
        ui.close("Close"),
    ).rows
    await ui.form(event.chat_id, "Settings", buttons=buttons)
    ```
    """

    def __init__(self, kernel: Any, *, ttl: int = 900):
        self.kernel = kernel
        self.ttl = ttl

    def action(
        self,
        text: str,
        callback,
        *,
        args: CallbackArgs = None,
        kwargs: CallbackKwargs = None,
        ttl: int | None = None,
        token: str | None = None,
        icon: Any = None,
        style: Any = None,
    ):
        return make_cb_button(
            self.kernel,
            text,
            callback,
            args=list(args or []),
            kwargs=dict(kwargs or {}),
            ttl=self.ttl if ttl is None else ttl,
            token=token,
            icon=icon,
            style=style,
        )

    def callback(self, text: str, data: str, *, icon: Any = None, style: Any = None):
        payload = data.encode() if isinstance(data, str) else data
        return Button.inline(text, payload, icon=icon, style=style)

    def url(self, text: str, url: str):
        return Button.url(text, url)

    def switch(self, text: str, query: str, *, same_peer: bool = True):
        return Button.switch_inline(text, query=query, same_peer=same_peer)

    def close(self, text: str = "✖️ Close", *, data: str = "close"):
        return self.callback(text, data)

    def keyboard(self, *rows: Any) -> InlineKeyboard:
        keyboard = InlineKeyboard()
        for row in rows:
            keyboard.row(*(row if isinstance(row, (list, tuple)) else [row]))
        return keyboard

    async def form(self, chat_id: int, title: str, **kwargs):
        ttl = kwargs.pop("ttl", self.ttl)
        return await self.kernel.inline_form(chat_id, title, ttl=ttl, **kwargs)


def build_inline_keyboard_row(buttons: list[Any]) -> list[dict[str, Any]]:
    result = []
    for btn in buttons:
        btn_dict = build_inline_button(btn)
        if btn_dict:
            result.append(btn_dict)
    return result


def build_inline_keyboard(
    rows: list[list[Any]], resize: bool | None = None, one_time: bool | None = None
) -> dict[str, Any]:
    if isinstance(rows, InlineKeyboard):
        rows = rows.rows

    keyboard = []
    for row in rows:
        if not isinstance(row, list):
            row = [row]
        kb_row = build_inline_keyboard_row(row)
        if kb_row:
            keyboard.append(kb_row)
    result = {"inline_keyboard": keyboard}
    if resize is not None:
        result["resize_keyboard"] = resize
    if one_time is not None:
        result["one_time_keyboard"] = one_time
    return result


def build_inline_button(btn: Any) -> dict[str, Any] | None:
    from telethon.tl.types import (
        KeyboardButtonCallback,
        KeyboardButtonGame,
        KeyboardButtonRequestGeoLocation,
        KeyboardButtonRequestPhone,
        KeyboardButtonSwitchInline,
        KeyboardButtonUrl,
    )

    if isinstance(btn, InlineButton):
        return btn.to_dict()
    if isinstance(btn, dict):
        return _build_button_from_dict(btn)

    emoji = get_button_emoji(btn)

    if isinstance(btn, KeyboardButtonCallback):
        data = btn.data
        callback_data = data.decode() if isinstance(data, bytes) else str(data)
        return _with_emoji(
            {
                "text": btn.text,
                "callback_data": callback_data,
            },
            emoji,
        )

    elif isinstance(btn, KeyboardButtonUrl):
        return _with_emoji({"text": btn.text, "url": btn.url}, emoji)

    elif isinstance(btn, KeyboardButtonSwitchInline):
        query = btn.query or ""
        if getattr(btn, "same_peer", False):
            btn_dict = {
                "text": btn.text,
                "switch_inline_query_current_chat": query,
            }
        else:
            btn_dict = {
                "text": btn.text,
                "switch_inline_query": query,
            }
        return _with_emoji(btn_dict, emoji)

    elif isinstance(btn, KeyboardButtonRequestPhone):
        return _with_emoji(
            {
                "text": btn.text,
                "request_contact": True,
            },
            emoji,
        )

    elif isinstance(btn, KeyboardButtonRequestGeoLocation):
        return _with_emoji(
            {
                "text": btn.text,
                "request_location": True,
            },
            emoji,
        )

    elif isinstance(btn, KeyboardButtonGame):
        return _with_emoji(
            {
                "text": btn.text,
                "callback_game": {},
            },
            emoji,
        )

    return {"text": str(btn)}


def _build_button_from_dict(btn: dict[str, Any]) -> dict[str, Any] | None:
    b_type = str(btn.get("type", "callback")).lower()
    text = str(btn.get("text", ""))
    emoji = btn.get("emoji")

    if b_type == "callback":
        callback_data = btn.get("callback_data", btn.get("data", ""))
        return build_button_callback(text, str(callback_data), emoji)
    if b_type == "url":
        return build_button_url(text, str(btn.get("url", "")), emoji)
    if b_type == "switch":
        return build_button_switch(
            text,
            str(btn.get("query", "")),
            str(btn.get("hint", "")),
            emoji,
            same_peer=bool(btn.get("same_peer", False)),
        )
    if b_type == "phone":
        return build_button_phone(text, emoji)
    if b_type == "location":
        return build_button_location(text, emoji)
    if b_type == "game":
        return build_button_game(text, emoji)
    return _with_emoji({"text": text}, emoji)


def build_button_callback(
    text: str, data: str, emoji: str | None = None
) -> dict[str, Any]:
    return _with_emoji({"text": text, "callback_data": data}, emoji)


def build_button_url(text: str, url: str, emoji: str | None = None) -> dict[str, Any]:
    return _with_emoji({"text": text, "url": url}, emoji)


def cleanup_inline_callback_map(kernel) -> None:
    """Remove expired entries from kernel.inline_callback_map in-place."""

    real_kernel = _get_real_kernel(kernel)
    lock = getattr(real_kernel, "_inline_cb_lock", None)
    if lock is None:
        return

    with lock:
        cb_map = getattr(real_kernel, "inline_callback_map", None)
        if not cb_map:
            return

        now = time.time()
        expired = [
            k
            for k, v in list(cb_map.items())
            if v.get("expires_at") and v["expires_at"] < now
        ]
        for k in expired:
            cb_map.pop(k, None)


def register_inline_callback(
    kernel: Any,
    callback,
    *,
    args: CallbackArgs = None,
    kwargs: CallbackKwargs = None,
    ttl: int = 900,
    token: str | None = None,
) -> str:
    """Register a temporary inline callback and return its callback token."""

    if not callable(callback):
        raise TypeError("callback must be callable")

    real_kernel = _get_real_kernel(kernel)

    if not hasattr(real_kernel, "_inline_cb_lock"):
        real_kernel._inline_cb_lock = threading.Lock()
    lock = real_kernel._inline_cb_lock

    with lock:
        cb_map = getattr(real_kernel, "inline_callback_map", None)
        if cb_map is None:
            cb_map = {}
            real_kernel.inline_callback_map = cb_map

        now = time.time()
        expired = [
            k
            for k, v in list(cb_map.items())
            if v.get("expires_at") and v["expires_at"] < now
        ]
        for k in expired:
            cb_map.pop(k, None)

        tok = token or uuid.uuid4().hex
        cb_map[tok] = {
            "handler": callback,
            "args": list(args or []),
            "kwargs": dict(kwargs or {}),
            "expires_at": now + ttl if ttl else None,
        }
        return tok


def _get_real_kernel(kernel: Any) -> Any:
    """Unwrap ModuleKernelProxy to access real kernel internals."""
    if type(kernel).__name__ == "ModuleKernelProxy":
        return object.__getattribute__(kernel, "_kernel")
    return kernel


def make_cb_button(
    kernel,
    text: str,
    callback,
    *,
    args: list | None = None,
    kwargs: dict | None = None,
    ttl: int = 900,
    token: str | None = None,
    icon: Any = None,
    style: Any = None,
):
    """Create Button.inline with auto-generated callback token.

    Stores mapping in kernel.inline_callback_map with expiry TTL seconds.
    Compatible with the auto-callback dispatcher in core_inline.handlers.
    """

    tok = register_inline_callback(
        kernel,
        callback,
        args=args,
        kwargs=kwargs,
        ttl=ttl,
        token=token,
    )
    return Button.inline(text, tok.encode(), icon=icon, style=style)


def code_inline(kernel: Any, *, ttl: int = 900) -> CodeInline:
    """Create the readable CodeInline facade for *kernel*."""

    return CodeInline(kernel, ttl=ttl)


def build_button_switch(
    text: str,
    query: str,
    hint: str = "",
    emoji: str | None = None,
    same_peer: bool = False,
) -> dict[str, Any]:
    btn = {"text": text}
    if same_peer or hint:
        btn["switch_inline_query_current_chat"] = hint or query
    else:
        btn["switch_inline_query"] = query
    return _with_emoji(btn, emoji)


def build_button_phone(text: str, emoji: str | None = None) -> dict[str, Any]:
    return _with_emoji({"text": text, "request_contact": True}, emoji)


def build_button_location(text: str, emoji: str | None = None) -> dict[str, Any]:
    return _with_emoji({"text": text, "request_location": True}, emoji)


def build_button_game(text: str, emoji: str | None = None) -> dict[str, Any]:
    return _with_emoji({"text": text, "callback_game": {}}, emoji)


def build_input_message_content(
    text: str,
    parse_mode: str | None = None,
    entities: list[dict[str, Any]] | None = None,
    disable_web_page_preview: bool = False,
) -> dict[str, Any]:
    content = {"message_text": text}
    if parse_mode:
        content["parse_mode"] = parse_mode
    if entities:
        content["entities"] = entities
    if disable_web_page_preview:
        content["disable_web_page_preview"] = disable_web_page_preview
    return content


def add_inline_keyboard_to_result(
    result: dict[str, Any],
    buttons: list[list[Any]],
    parse_mode: str | None = None,
) -> dict[str, Any]:
    keyboard = build_inline_keyboard(buttons)
    result["reply_markup"] = keyboard
    if parse_mode:
        if "input_message_content" not in result:
            result["input_message_content"] = {}
        result["input_message_content"]["parse_mode"] = parse_mode
    return result
