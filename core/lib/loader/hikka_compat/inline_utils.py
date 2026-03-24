import functools
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
        typing.Union[typing.List[typing.List[dict]], typing.List[dict], dict]
    ],
    custom_map: typing.Optional[typing.Dict[str, dict]] = None,
) -> typing.Optional[typing.List[typing.List[dict]]]:
    if not markup:
        return None

    if isinstance(markup, list):
        return markup

    if isinstance(markup, dict):
        return markup.get("buttons", [])

    return None


def process_buttons(
    buttons: typing.List[typing.List[dict]],
    custom_map: typing.Optional[typing.Dict[str, dict]] = None,
) -> typing.List[typing.List[dict]]:
    result: typing.List[typing.List[dict]] = []

    for row in buttons:
        processed_row: typing.List[dict] = []
        for button in row:
            if not isinstance(button, dict):
                continue

            btn_copy = dict(button)

            if "callback" in btn_copy and "_callback_data" not in btn_copy:
                btn_copy["_callback_data"] = _generate_id(30)

            if "input" in btn_copy and "_switch_query" not in btn_copy:
                btn_copy["_switch_query"] = _generate_id(10)

            result_button = _build_button(btn_copy)
            if result_button:
                processed_row.append(result_button)

        if processed_row:
            result.append(processed_row)

    return result


def _generate_id(length: int) -> str:
    import random
    import string

    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


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
    elif "input" in button:
        result["switch_inline_query_current_chat"] = (
            button.get("_switch_query", "") + " "
        )

    return result


class InlineUnit:
    """Base class for inline units"""

    pass


def sanitise_text(text: typing.Optional[str]) -> str:
    if not text:
        return ""

    text = str(text)
    replacements = {
        "<": "&lt;",
        ">": "&gt;",
        "&": "&amp;",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


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
