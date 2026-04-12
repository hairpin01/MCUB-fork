from typing import Any, Optional
import threading
import time
import uuid

from telethon import Button


def get_button_emoji(btn: Any) -> Optional[str]:
    if hasattr(btn, "style") and btn.style:
        if hasattr(btn.style, "icon") and btn.style.icon:
            return str(btn.style.icon)
    return None


def build_inline_keyboard_row(buttons: list[Any]) -> list[dict[str, Any]]:
    result = []
    for btn in buttons:
        btn_dict = build_inline_button(btn)
        if btn_dict:
            result.append(btn_dict)
    return result


def build_inline_keyboard(
    rows: list[list[Any]], resize: bool = None, one_time: bool = None
) -> dict[str, Any]:
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


def build_inline_button(btn: Any) -> Optional[dict[str, Any]]:
    from telethon.tl.types import (
        KeyboardButtonCallback,
        KeyboardButtonUrl,
        KeyboardButtonSwitchInline,
        KeyboardButtonRequestPhone,
        KeyboardButtonRequestGeoLocation,
        KeyboardButtonGame,
    )

    emoji = get_button_emoji(btn)

    if isinstance(btn, KeyboardButtonCallback):
        data = btn.data
        callback_data = data.decode() if isinstance(data, bytes) else str(data)
        btn_dict = {
            "text": btn.text,
            "callback_data": callback_data,
        }
        if emoji:
            btn_dict["emoji"] = emoji
        return btn_dict

    elif isinstance(btn, KeyboardButtonUrl):
        btn_dict = {"text": btn.text, "url": btn.url}
        if emoji:
            btn_dict["emoji"] = emoji
        return btn_dict

    elif isinstance(btn, KeyboardButtonSwitchInline):
        btn_dict = {
            "text": btn.text,
            "switch_inline_query": btn.query,
        }
        if emoji:
            btn_dict["emoji"] = emoji
        return btn_dict

    elif isinstance(btn, KeyboardButtonRequestPhone):
        btn_dict = {
            "text": btn.text,
            "request_contact": True,
        }
        if emoji:
            btn_dict["emoji"] = emoji
        return btn_dict

    elif isinstance(btn, KeyboardButtonRequestGeoLocation):
        btn_dict = {
            "text": btn.text,
            "request_location": True,
        }
        if emoji:
            btn_dict["emoji"] = emoji
        return btn_dict

    elif isinstance(btn, KeyboardButtonGame):
        btn_dict = {
            "text": btn.text,
            "callback_game": {},
        }
        if emoji:
            btn_dict["emoji"] = emoji
        return btn_dict

    return {"text": str(btn)}


def build_button_callback(
    text: str, data: str, emoji: Optional[str] = None
) -> dict[str, Any]:
    btn = {"text": text, "callback_data": data}
    if emoji:
        btn["emoji"] = emoji
    return btn


def build_button_url(
    text: str, url: str, emoji: Optional[str] = None
) -> dict[str, Any]:
    btn = {"text": text, "url": url}
    if emoji:
        btn["emoji"] = emoji
    return btn


def cleanup_inline_callback_map(kernel) -> None:
    """Remove expired entries from kernel.inline_callback_map in-place."""

    lock = getattr(kernel, "_inline_cb_lock", None)
    if lock is None:
        return

    with lock:
        cb_map = getattr(kernel, "inline_callback_map", None)
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


def make_cb_button(
    kernel,
    text: str,
    callback,
    *,
    args: Optional[list] = None,
    kwargs: Optional[dict] = None,
    ttl: int = 900,
    token: Optional[str] = None,
    icon: Any = None,
    style: Any = None,
):
    """Create Button.inline with auto-generated callback token.

    Stores mapping in kernel.inline_callback_map with expiry TTL seconds.
    Compatible with the auto-callback dispatcher in core_inline.handlers.
    """

    if not callable(callback):
        raise TypeError("callback must be callable")

    if not hasattr(kernel, "_inline_cb_lock"):
        kernel._inline_cb_lock = threading.Lock()
    lock = kernel._inline_cb_lock

    with lock:
        cb_map = getattr(kernel, "inline_callback_map", None)
        if cb_map is None:
            cb_map = {}
            setattr(kernel, "inline_callback_map", cb_map)

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

    return Button.inline(text, tok.encode(), icon=icon, style=style)


def build_button_switch(
    text: str, query: str, hint: str = "", emoji: Optional[str] = None
) -> dict[str, Any]:
    btn = {"text": text, "switch_inline_query": query}
    if hint:
        btn["switch_inline_query_current_chat"] = hint
    if emoji:
        btn["emoji"] = emoji
    return btn


def build_button_phone(text: str, emoji: Optional[str] = None) -> dict[str, Any]:
    btn = {"text": text, "request_contact": True}
    if emoji:
        btn["emoji"] = emoji
    return btn


def build_button_location(text: str, emoji: Optional[str] = None) -> dict[str, Any]:
    btn = {"text": text, "request_location": True}
    if emoji:
        btn["emoji"] = emoji
    return btn


def build_button_game(text: str, emoji: Optional[str] = None) -> dict[str, Any]:
    btn = {"text": text, "callback_game": {}}
    if emoji:
        btn["emoji"] = emoji
    return btn


def build_input_message_content(
    text: str,
    parse_mode: Optional[str] = None,
    entities: Optional[list[dict[str, Any]]] = None,
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
    parse_mode: Optional[str] = None,
) -> dict[str, Any]:
    keyboard = build_inline_keyboard(buttons)
    result["reply_markup"] = keyboard
    if parse_mode:
        if "input_message_content" not in result:
            result["input_message_content"] = {}
        result["input_message_content"]["parse_mode"] = parse_mode
    return result
