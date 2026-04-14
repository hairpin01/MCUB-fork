# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

import functools
import random
import re
import string
import time
import types
import typing

VALID_BUTTON_STYLES = {"danger", "primary", "success"}


class InlineMarkupBuilder:
    """Helper class to build inline markups for hikka compat"""

    def __init__(self):
        self._buttons: typing.List[typing.List[dict]] = []

    def add(
        self,
        text: str,
        callback: typing.Optional[typing.Union[str, typing.Callable]] = None,
        url: typing.Optional[str] = None,
        input: typing.Optional[str] = None,
        **kwargs,
    ) -> "InlineMarkupBuilder":
        button: dict = {"text": text}

        if callback:
            if isinstance(callback, str):
                button["callback"] = callback
            else:
                button["callback"] = callback
        if url:
            button["url"] = url
        if input:
            button["input"] = input

        button.update(kwargs)

        if not self._buttons:
            self._buttons.append([])

        self._buttons[-1].append(button)
        return self

    def row(self) -> "InlineMarkupBuilder":
        self._buttons.append([])
        return self

    def build(self) -> typing.List[typing.List[dict]]:
        return [row for row in self._buttons if row]

    def __iter__(self):
        return iter(self.build())

    def __repr__(self):
        return f"<InlineMarkupBuilder buttons={len(self._buttons)}>"


def generate_markup(
    markup: typing.Optional[
        typing.Union[typing.List[typing.List[dict]], typing.List[dict], dict, str]
    ],
    custom_map: typing.Optional[typing.Dict[str, dict]] = None,
    inline_proxy=None,
    unit_id: typing.Optional[str] = None,
) -> typing.Optional[typing.List[typing.List[dict]]]:
    if not markup:
        return None

    normalized = _normalize_markup(markup, inline_proxy=inline_proxy)
    if not normalized:
        return None

    ttl = getattr(inline_proxy, "_current_form_ttl", 3600) if inline_proxy else 3600

    return process_buttons(
        normalized,
        custom_map=custom_map,
        inline_proxy=inline_proxy,
        unit_id=unit_id,
        ttl=ttl,
    )


def process_buttons(
    buttons: typing.List[typing.List[dict]],
    custom_map: typing.Optional[typing.Dict[str, dict]] = None,
    inline_proxy=None,
    unit_id: typing.Optional[str] = None,
    ttl: int = 3600,
) -> typing.List[typing.List[dict]]:
    if custom_map is None:
        custom_map = getattr(inline_proxy, "_custom_map", None)

    result: typing.List[typing.List[dict]] = []

    for row in _normalize_markup(buttons):
        processed_row: typing.List[dict] = []
        for button in row:
            if not isinstance(button, dict):
                continue

            btn_copy = dict(button)
            _apply_action_button(btn_copy, inline_proxy)

            if "callback" in btn_copy and "_callback_data" not in btn_copy:
                btn_copy["_callback_data"] = _generate_id(30)

            if "input" in btn_copy and "_switch_query" not in btn_copy:
                btn_copy["_switch_query"] = _generate_id(10)

            if (
                custom_map is not None
                and "callback" in btn_copy
                and "_callback_data" in btn_copy
            ):
                custom_map[btn_copy["_callback_data"]] = {
                    "handler": btn_copy["callback"],
                    "always_allow": btn_copy.get("always_allow", []),
                    "args": btn_copy.get("args", ()),
                    "kwargs": btn_copy.get("kwargs", {}),
                    "force_me": bool(btn_copy.get("force_me", False)),
                    "disable_security": bool(btn_copy.get("disable_security", False)),
                    "unit_id": unit_id or btn_copy.get("unit_id"),
                }

                if inline_proxy is not None:
                    kernel = getattr(inline_proxy, "_kernel", None)
                    if kernel is not None:
                        cb_map = getattr(kernel, "inline_callback_map", None)
                        if cb_map is None:
                            cb_map = {}
                            setattr(kernel, "inline_callback_map", cb_map)

                        cb_map[btn_copy["_callback_data"]] = {
                            "handler": btn_copy["callback"],
                            "args": btn_copy.get("args", ()),
                            "kwargs": btn_copy.get("kwargs", {}),
                            "expires_at": time.time() + ttl,
                        }

            result_button = _build_button(btn_copy)
            if result_button:
                processed_row.append(result_button)

        if processed_row:
            result.append(processed_row)

    return result


def _generate_id(length: int) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def _normalize_markup(markup, inline_proxy=None) -> typing.List[typing.List[dict]]:
    if not markup:
        return []

    if isinstance(markup, str):
        units = getattr(inline_proxy, "_units", {}) if inline_proxy is not None else {}
        unit = units.get(markup, {})
        markup = unit.get("buttons", [])

    if isinstance(markup, dict):
        if "buttons" in markup and isinstance(markup["buttons"], list):
            markup = markup["buttons"]
        else:
            return [[markup]]

    if not isinstance(markup, list):
        return []

    if not markup:
        return []

    if any(isinstance(i, dict) for i in markup):
        return [typing.cast(typing.List[dict], markup)]

    normalized: typing.List[typing.List[dict]] = []
    for row in markup:
        if isinstance(row, dict):
            normalized.append([row])
            continue
        if isinstance(row, list):
            normalized.append([btn for btn in row if isinstance(btn, dict)])

    return [row for row in normalized if row]


def _apply_action_button(button: dict, inline_proxy=None) -> None:
    if "callback" in button:
        return

    action = str(button.get("action", "")).lower()
    if not action:
        return

    if action == "close":
        callback = getattr(inline_proxy, "_close_unit_handler", None)
        if callback:
            button["callback"] = callback
        return

    if action == "unload":
        callback = getattr(inline_proxy, "_unload_unit_handler", None)
        if callback:
            button["callback"] = callback
        return

    if action == "answer":
        text = str(button.get("message", ""))
        if not text:
            return

        callback = getattr(inline_proxy, "_answer_unit_handler", None)
        if callback:
            button["callback"] = functools.partial(
                callback,
                show_alert=bool(button.get("show_alert", False)),
                text=text,
            )


def _build_button(button: dict) -> typing.Optional[dict]:
    result: dict = {"text": str(button.get("text", ""))}

    style = button.get("style")
    if style and style in VALID_BUTTON_STYLES:
        result["style"] = style

    emoji_id = button.get("emoji_id")
    if emoji_id:
        result["emoji_id"] = str(emoji_id)

    if "url" in button:
        result["url"] = button["url"]
    elif "callback" in button:
        result["callback_data"] = button.get("_callback_data", "")
    elif "data" in button:
        result["callback_data"] = str(button.get("data", ""))
    elif "input" in button:
        result["switch_inline_query_current_chat"] = (
            button.get("_switch_query", "") + " "
        )
    elif "switch_inline_query_current_chat" in button:
        result["switch_inline_query_current_chat"] = str(
            button.get("switch_inline_query_current_chat", "")
        )
    elif "switch_inline_query" in button:
        result["switch_inline_query"] = str(button.get("switch_inline_query", ""))
    elif "copy" in button:
        result["copy_text"] = str(button.get("copy", ""))
    elif "web_app" in button:
        result["web_app"] = button["web_app"]

    return result


class InlineUnit:
    """Base class for inline units"""

    pass


def sanitise_text(text: typing.Optional[str]) -> str:
    if not text:
        return ""

    text = str(text)
    text = text.replace("\x00", "")
    text = re.sub(r"<tg-emoji[^>]*>(.*?)</tg-emoji>", r"\1", text, flags=re.I | re.S)
    text = re.sub(r"</?emoji[^>]*>", "", text, flags=re.I)
    return text.strip()


def _build_inline_results(
    results: typing.List[dict],
) -> typing.List[dict]:
    processed: typing.List[dict] = []

    for result in results:
        processed_result = _process_single_result(result)
        if processed_result:
            processed.append(processed_result)

    return processed


def _process_single_result(result: dict) -> typing.Optional[dict]:
    if not isinstance(result, dict):
        return None

    mandatory_fields = ["message", "photo", "gif", "video", "file"]
    if not any(field in result for field in mandatory_fields):
        return None

    return {
        "title": result.get("title", ""),
        "description": result.get("description", ""),
        "message": result.get("message", ""),
        "thumb": result.get("thumb"),
        "reply_markup": generate_markup(result.get("reply_markup")),
    }


_inline_utils_mod = types.ModuleType("__hikka_mcub_compat_inline_utils__")
for _name, _val in {
    "InlineMarkupBuilder": InlineMarkupBuilder,
    "generate_markup": generate_markup,
    "process_buttons": process_buttons,
    "sanitise_text": sanitise_text,
    "InlineUnit": InlineUnit,
    "VALID_BUTTON_STYLES": VALID_BUTTON_STYLES,
}.items():
    setattr(_inline_utils_mod, _name, _val)
