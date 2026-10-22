# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""Tests for the terminal message buttons (stdin / exit / next command)."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock

import pytest

from modules import terminal as terminal_module

_ASSERT = TestCase()

CHAT = 100
MESSAGE = 500
ADMIN = 42


class _Cache:
    def __init__(self):
        self.store = {}

    def set(self, key, value, ttl=None):
        self.store[key] = value

    def get(self, key, default=None):
        return self.store.get(key, default)

    def delete(self, key):
        self.store.pop(key, None)


class _Register:
    def __init__(self):
        self.forms = {}

    def command(self, *_args, **_kwargs):
        return lambda func: func

    def guest_command(self, *_args, **_kwargs):
        return lambda func: func

    def inline_temp(self, handler, **kwargs):
        token = f"form{len(self.forms)}"
        self.forms[token] = (handler, kwargs)
        return token


def _kernel():
    kernel = SimpleNamespace(
        client=SimpleNamespace(
            send_message=AsyncMock(),
            edit_message=AsyncMock(),
        ),
        bot_client=SimpleNamespace(edit_message=AsyncMock()),
        logger=SimpleNamespace(
            debug=lambda *a, **kw: None,
            warning=lambda *a, **kw: None,
            error=lambda *a, **kw: None,
        ),
        config={"language": "en"},
        cache=_Cache(),
        is_admin=lambda user_id: user_id == ADMIN,
        inline_callback_map={},
        handle_error=AsyncMock(),
        store_module_config_schema=lambda *a, **kw: None,
        get_module_config=AsyncMock(return_value={}),
        save_module_config=AsyncMock(),
        _live_module_configs={},
    )
    kernel.register = _Register()
    return kernel


def _query(button):
    return button.to_dict()["type"]["query"]


def _callback_data(button):
    return button.to_dict()["type"]["data"]


def _callback_token(button):
    return _callback_data(button).decode()


def _query_key(button, form_id):
    """Split '<form_id> <cache_key> ' into the cache key."""
    parts = _query(button).split(" ")
    assert parts[0] == form_id, _query(button)
    return parts[1]


async def _instance():
    kernel = _kernel()
    terminal_module.register(kernel)
    # register() schedules a config-sync task; let it run before assertions.
    await __import__("asyncio").sleep(0)
    forms = list(kernel.register.forms.items())
    # Two inline forms: stdin (input_form_id) and next command (next_form_id).
    input_form, next_form = forms[0][0], forms[1][0]
    handler, _ = forms[0][1]
    instance = handler.__self__
    instance.input_form_id = input_form
    instance.next_form_id = next_form
    return kernel, instance, input_form, next_form


def test_buttons_are_stdin_plus_exit_while_running():
    async def scenario():
        kernel, instance, input_form, next_form = await _instance()
        buttons = instance._buttons(CHAT, "1", running=True, message_id=MESSAGE)
        _ASSERT.assertEqual(len(buttons), 1)
        _ASSERT.assertEqual(len(buttons[0]), 2)
        stdin, exit_btn = buttons[0]

        # stdin: switch-inline query with a cached target.
        _ASSERT.assertIn("stdin", stdin.text.lower())
        key = _query_key(stdin, input_form)
        _ASSERT.assertEqual(
            kernel.cache.get(key),
            {"chat_id": CHAT, "slot": "1", "message_id": MESSAGE},
        )

        # exit: token callback, no chat/slot in the pressed data.
        _ASSERT.assertTrue(exit_btn.text.endswith("exit"), exit_btn.text)
        _ASSERT.assertEqual(len(_callback_data(exit_btn)), 32)
        entry = kernel.inline_callback_map[_callback_token(exit_btn)]
        _ASSERT.assertEqual(entry["args"], [CHAT, "1"])
        _ASSERT.assertEqual(entry["handler"], instance._on_exit_button)

    __import__("asyncio").run(scenario())


def test_next_command_replaces_exit_when_stopped():
    async def scenario():
        kernel, instance, input_form, next_form = await _instance()
        buttons = instance._buttons(CHAT, "1", running=False, message_id=MESSAGE)
        stdin, next_btn = buttons[0]
        key = _query_key(next_btn, next_form)
        _ASSERT.assertEqual(
            kernel.cache.get(key),
            {"chat_id": CHAT, "slot": "1", "message_id": MESSAGE},
        )
        # No token callback is registered for the stopped state.
        _ASSERT.assertEqual(kernel.inline_callback_map, {})
        _ASSERT.assertIn("stdin", stdin.text.lower())

    __import__("asyncio").run(scenario())


def test_buttons_reuse_tokens_for_the_same_message():
    async def scenario():
        _kernel_, instance, _input_form, _next_form = await _instance()
        first = instance._buttons(CHAT, "1", running=True, message_id=MESSAGE)
        second = instance._buttons(CHAT, "1", running=False, message_id=MESSAGE)
        _ASSERT.assertEqual(
            _query(first[0][0]), _query(second[0][0]), "stdin key must be reused"
        )
        _ASSERT.assertEqual(
            instance.button_keys["100:1"]["message_id"], MESSAGE
        )

        # Another message in the same slot gets fresh keys.
        other = instance._buttons(CHAT, "1", running=True, message_id=MESSAGE + 1)
        _ASSERT.assertNotEqual(
            _query(first[0][0]), _query(other[0][0]), "keys must not leak messages"
        )

    __import__("asyncio").run(scenario())


def test_edit_message_ignores_event_of_another_message():
    async def scenario():
        _kernel_, instance, _input_form, _next_form = await _instance()
        stale = SimpleNamespace(id=MESSAGE + 1, edit=AsyncMock())
        instance.events["100:1"] = stale
        _ASSERT.assertIsNone(instance._event_for(CHAT, "1", MESSAGE))

        fresh = SimpleNamespace(id=MESSAGE, edit=AsyncMock())
        instance.events["100:1"] = fresh
        _ASSERT.assertIs(instance._event_for(CHAT, "1", MESSAGE), fresh)

    __import__("asyncio").run(scenario())


def test_exit_button_kills_the_slot():
    async def scenario():
        _kernel_, instance, _input_form, _next_form = await _instance()
        instance.kill_command = AsyncMock()
        await instance._on_exit_button(AsyncMock(), CHAT, "2")
        instance.kill_command.assert_awaited_once_with(CHAT, slot="2")

    __import__("asyncio").run(scenario())


def test_next_command_handler_runs_in_the_same_message():
    async def scenario():
        kernel, instance, _input_form, next_form = await _instance()
        instance.run_command = AsyncMock()
        event_obj = SimpleNamespace(id=MESSAGE, guest_mode=True)
        instance.events["100:2"] = event_obj
        target = {"chat_id": CHAT, "slot": "2", "message_id": MESSAGE}
        kernel.cache.set("k1", target)

        await instance._handle_next(SimpleNamespace(user_id=ADMIN), "k1  echo hi")
        instance.run_command.assert_awaited_once_with(
            CHAT, "echo hi", MESSAGE, slot="2", event=event_obj
        )

        # Non-admin presses are ignored.
        instance.run_command.reset_mock()
        await instance._handle_next(SimpleNamespace(user_id=7), "k1 echo hi")
        instance.run_command.assert_not_awaited()

        # Empty command is ignored.
        await instance._handle_next(SimpleNamespace(user_id=ADMIN), "k1   ")
        instance.run_command.assert_not_awaited()

        # Expired/unknown key is ignored.
        await instance._handle_next(SimpleNamespace(user_id=ADMIN), "nope echo hi")
        instance.run_command.assert_not_awaited()
        _ASSERT.assertEqual(next_form, instance.next_form_id)

    __import__("asyncio").run(scenario())


def test_stdin_handler_still_uses_cached_target():
    async def scenario():
        kernel, instance, _input_form, _next_form = await _instance()
        instance.send_stdin = AsyncMock(return_value=(True, None))
        kernel.cache.set("k2", {"chat_id": CHAT, "slot": "1", "message_id": MESSAGE})

        await instance._handle_input(SimpleNamespace(user_id=ADMIN), "k2 hello")
        instance.send_stdin.assert_awaited_once_with(CHAT, "1", "hello")

        instance.send_stdin.reset_mock()
        await instance._handle_input(SimpleNamespace(user_id=7), "k2 hello")
        instance.send_stdin.assert_not_awaited()

    __import__("asyncio").run(scenario())