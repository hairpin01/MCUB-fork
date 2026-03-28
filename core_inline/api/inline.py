from typing import Any, Optional


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


def build_inline_keyboard(rows: list[list[Any]]) -> dict[str, Any]:
    keyboard = []
    for row in rows:
        if not isinstance(row, list):
            row = [row]
        kb_row = build_inline_keyboard_row(row)
        if kb_row:
            keyboard.append(kb_row)
    return {"inline_keyboard": keyboard}


def build_inline_button(btn: Any) -> Optional[dict[str, Any]]:
    from telethon.tl.types import (
        KeyboardButtonCallback,
        KeyboardButtonUrl,
        KeyboardButtonSwitchInline,
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

    return {"text": str(btn)}


def add_inline_keyboard_to_result(
    result: dict[str, Any],
    buttons: list[list[Any]],
) -> dict[str, Any]:
    keyboard = build_inline_keyboard(buttons)
    result["reply_markup"] = keyboard
    return result
