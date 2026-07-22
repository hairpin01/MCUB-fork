import time

from core_inline.api import (
    CodeInline,
    InlineButton,
    InlineKeyboard,
    build_inline_button,
    build_inline_keyboard,
    code_inline,
    register_inline_callback,
)
from core_inline.handlers import InlineHandlers


class FakeLogger:
    def debug(self, *args, **kwargs):
        pass


class FakeKernel:
    def __init__(self):
        self.logger = FakeLogger()


async def noop_callback(*args, **kwargs):
    return None


def test_inline_button_objects_render_to_plain_keyboard_dicts():
    keyboard = InlineKeyboard().row(
        InlineButton.callback("Open", "open:data"),
        InlineButton.url_button("Docs", "https://example.com", emoji="📚"),
    )

    assert keyboard.to_dict() == {
        "inline_keyboard": [
            [
                {"text": "Open", "callback_data": "open:data"},
                {"text": "Docs", "url": "https://example.com", "emoji": "📚"},
            ]
        ]
    }


def test_build_inline_keyboard_accepts_dicts_and_button_objects():
    assert build_inline_keyboard(
        [
            [
                {"text": "A", "type": "callback", "data": "a"},
                InlineButton.switch("Search", "q", same_peer=True),
            ]
        ]
    ) == {
        "inline_keyboard": [
            [
                {"text": "A", "callback_data": "a"},
                {"text": "Search", "switch_inline_query_current_chat": "q"},
            ]
        ]
    }


def test_register_inline_callback_cleans_expired_entries_and_stores_token():
    kernel = FakeKernel()
    kernel.inline_callback_map = {
        "expired": {
            "handler": noop_callback,
            "args": [],
            "kwargs": {},
            "expires_at": time.time() - 1,
        }
    }

    token = register_inline_callback(
        kernel,
        noop_callback,
        args=[1],
        kwargs={"ok": True},
        ttl=60,
        token="fixed-token",
    )

    assert token == "fixed-token"
    assert "expired" not in kernel.inline_callback_map
    assert kernel.inline_callback_map[token]["handler"] is noop_callback
    assert kernel.inline_callback_map[token]["args"] == [1]
    assert kernel.inline_callback_map[token]["kwargs"] == {"ok": True}


def test_code_inline_facade_creates_action_button_with_registered_callback():
    kernel = FakeKernel()
    ui = code_inline(kernel, ttl=30)

    button = ui.action("Run", noop_callback, token="run-token")

    assert isinstance(ui, CodeInline)
    assert kernel.inline_callback_map["run-token"]["handler"] is noop_callback
    assert build_inline_button(button) == {"text": "Run", "callback_data": "run-token"}


def test_inline_handlers_reuse_core_inline_callback_registry():
    kernel = FakeKernel()
    handler = object.__new__(InlineHandlers)
    handler.kernel = kernel
    handler.lang = {"btn_default": "Button"}

    button = handler._dict_to_button(
        {
            "text": "Run",
            "callback": noop_callback,
            "token": "handler-token",
            "args": [42],
        },
        ttl=30,
    )

    assert build_inline_button(button) == {
        "text": "Run",
        "callback_data": "handler-token",
    }
    assert kernel.inline_callback_map["handler-token"]["handler"] is noop_callback
    assert kernel.inline_callback_map["handler-token"]["args"] == [42]


def test_inline_handlers_build_buttons_dict_accepts_new_button_objects():
    handler = object.__new__(InlineHandlers)

    assert handler.build_buttons_dict(
        [[InlineButton.callback("A", "a"), InlineButton.url_button("B", "https://b")]]
    ) == [[{"text": "A", "callback_data": "a"}, {"text": "B", "url": "https://b"}]]


def test_inline_handlers_normalize_buttons_accepts_keyboard_builder():
    handler = object.__new__(InlineHandlers)
    button = InlineButton.callback("A", "a")
    keyboard = InlineKeyboard().row(button)

    normalized = handler._normalize_buttons(keyboard)

    assert build_inline_button(normalized[0][0]) == {"text": "A", "callback_data": "a"}


def test_inline_handlers_normalize_buttons_accepts_single_level_objects():
    handler = object.__new__(InlineHandlers)
    first = InlineButton.callback("A", "a")
    second = InlineButton.url_button("B", "https://b")

    normalized = handler._normalize_buttons([first, second])

    assert build_inline_button(normalized[0][0]) == {"text": "A", "callback_data": "a"}
    assert build_inline_button(normalized[1][0]) == {"text": "B", "url": "https://b"}


def test_inline_handlers_callback_entry_allow_user_checks_sender():
    assert InlineHandlers._callback_entry_allows_user({"allow_user": 123}, 123)
    assert not InlineHandlers._callback_entry_allows_user({"allow_user": 123}, 456)
    assert InlineHandlers._callback_entry_allows_user({"allow_user": [123, 456]}, 456)
    assert not InlineHandlers._callback_entry_allows_user({"allow_user": [123]}, 456)
    assert InlineHandlers._callback_entry_allows_user({"allow_user": "all"}, 456)
    assert InlineHandlers._callback_entry_allows_user({"allow_all": True}, 456)
    assert not InlineHandlers._callback_entry_allows_user({}, 456)
