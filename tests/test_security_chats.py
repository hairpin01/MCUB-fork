# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from types import SimpleNamespace
from unittest.mock import MagicMock

from core.lib.loader.security import SecurityChats


def _event(chat_id=100, sender_id=42, text="hello", message_id=7):
    message = SimpleNamespace(
        id=message_id,
        chat_id=chat_id,
        sender_id=sender_id,
        raw_text=text,
    )
    return SimpleNamespace(
        chat_id=chat_id,
        sender_id=sender_id,
        message=message,
    )


def test_blacklisted_user_blocks_and_logs_warning():
    logger = MagicMock()
    security = SecurityChats(SimpleNamespace(logger=logger))
    security.blacklist_user(42)

    assert not security.can_process_event(
        _event(chat_id=100, sender_id=42, text=".ping"),
        module="test_module",
        action="watcher",
    )
    logger.warning.assert_called_once_with(
        "[security] blocked blacklisted user user_id=%s chat_id=%s text=%r",
        42,
        100,
        ".ping",
    )


def test_ignore_chat_blocks_only_that_chat():
    security = SecurityChats()
    security.ignore_chat(100)

    assert not security.can_process_event(_event(chat_id=100), action="command")
    assert security.can_process_event(_event(chat_id=200), action="command")


def test_allowed_chats_switch_scope_to_allowlist_mode():
    security = SecurityChats()
    security.set_allowed_chats([100])

    assert security.can_process_event(_event(chat_id=100), action="command")
    assert not security.can_process_event(_event(chat_id=200), action="command")


def test_module_scoped_rules_do_not_affect_other_modules():
    security = SecurityChats()
    security.ignore_chat(100, module="mod_a")

    assert not security.can_process_event(_event(chat_id=100), module="mod_a")
    assert security.can_process_event(_event(chat_id=100), module="mod_b")


def test_missing_chat_id_is_not_blocked_by_chat_allowlist():
    security = SecurityChats()
    security.set_allowed_chats([100])
    event = SimpleNamespace(sender_id=42, message=SimpleNamespace(raw_text="status"))

    assert security.can_process_event(event, action="event:userupdate")
