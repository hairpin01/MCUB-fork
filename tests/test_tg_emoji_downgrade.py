# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01
# Author: рич белуга (@rich_beluga)

"""Tests for <tg-emoji> -> tg://emoji downgrade (non-Premium accounts)."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock

import pytest

from modules import man
from utils.tg_emoji import (
    account_has_premium,
    downgrade_tg_emoji,
    has_tg_emoji,
    tg_emoji_to_link,
)

_ASSERT = TestCase()

SRC = '<tg-emoji emoji-id="5346022209389372742">🤔</tg-emoji>'
DST = '<a href="tg://emoji?id=5346022209389372742">🤔</a>'


def test_converts_single_tag():
    _ASSERT.assertEqual(tg_emoji_to_link(SRC), DST)


def test_converts_multiple_tags():
    text = f"a {SRC} b " + '<tg-emoji emoji-id="1">👍</tg-emoji>'
    _ASSERT.assertEqual(
        tg_emoji_to_link(text), f'a {DST} b <a href="tg://emoji?id=1">👍</a>'
    )


def test_leaves_plain_text_untouched():
    _ASSERT.assertEqual(
        tg_emoji_to_link("hello <b>world</b>"), "hello <b>world</b>"
    )


def test_accepts_single_quotes_and_case_variants():
    _ASSERT.assertEqual(
        tg_emoji_to_link("<TG-EMOJI EMOJI-ID='42'>x</TG-EMOJI>"),
        '<a href="tg://emoji?id=42">x</a>',
    )


def test_leaves_non_numeric_id_untouched():
    text = "<tg-emoji emoji-id=\"abc\">x</tg-emoji>"
    _ASSERT.assertEqual(tg_emoji_to_link(text), text)


def test_has_tg_emoji():
    _ASSERT.assertTrue(has_tg_emoji(SRC))
    _ASSERT.assertFalse(has_tg_emoji("plain"))
    _ASSERT.assertFalse(has_tg_emoji(None))


def _client(premium=True, fail=False):
    client = SimpleNamespace()
    if fail:
        async def _boom():
            raise RuntimeError("offline")

        client.get_me = _boom
    else:
        client.get_me = AsyncMock(return_value=SimpleNamespace(premium=premium))
    return client


@pytest.mark.asyncio
async def test_premium_account_keeps_tags():
    _ASSERT.assertTrue(await account_has_premium(_client(premium=True)))
    _ASSERT.assertEqual(await downgrade_tg_emoji(SRC, _client(premium=True)), SRC)


@pytest.mark.asyncio
async def test_non_premium_account_converts():
    _ASSERT.assertFalse(await account_has_premium(_client(premium=False)))
    _ASSERT.assertEqual(await downgrade_tg_emoji(SRC, _client(premium=False)), DST)


@pytest.mark.asyncio
async def test_get_me_failure_keeps_original():
    _ASSERT.assertTrue(await account_has_premium(_client(fail=True)))
    _ASSERT.assertTrue(await account_has_premium(None))
    _ASSERT.assertEqual(await downgrade_tg_emoji(SRC, _client(fail=True)), SRC)


@pytest.mark.asyncio
async def test_text_without_tags_skips_get_me():
    client = SimpleNamespace(get_me=AsyncMock())
    _ASSERT.assertEqual(await downgrade_tg_emoji("plain", client), "plain")
    client.get_me.assert_not_called()


def _guest_man_instance(text, premium):
    inst = man.ManModule.__new__(man.ManModule)
    inst.kernel = SimpleNamespace(
        loaded_modules={"m": object()},
        handle_error=AsyncMock(),
    )
    inst.client = _client(premium=premium)
    inst.config = {"man_modules_per_page": 10}
    inst._get_hidden_modules = AsyncMock(return_value=[])
    inst._get_paginated_data = lambda page, **kw: (text, ["btn"])
    inst._generate_detailed_page = AsyncMock(return_value=(text, None))
    return inst


def _guest_event(args=""):
    event = SimpleNamespace(
        guest_args=args,
        reply=AsyncMock(),
    )
    return event


@pytest.mark.asyncio
async def test_guest_man_converts_without_premium():
    inst = _guest_man_instance(f"list {SRC}", premium=False)
    event = _guest_event("")
    await inst.guest_man(event)
    (text,), kwargs = event.reply.call_args
    _ASSERT.assertIn(DST, text)
    _ASSERT.assertNotIn(SRC, text)
    _ASSERT.assertEqual(kwargs["parse_mode"], "html")


@pytest.mark.asyncio
async def test_guest_man_detail_converts_without_premium():
    inst = _guest_man_instance(f"detail {SRC}", premium=False)
    event = _guest_event("terminal")
    await inst.guest_man(event)
    (text,), _kwargs = event.reply.call_args
    _ASSERT.assertIn(DST, text)
    _ASSERT.assertNotIn(SRC, text)


@pytest.mark.asyncio
async def test_guest_man_keeps_tags_with_premium():
    inst = _guest_man_instance(f"list {SRC}", premium=True)
    event = _guest_event("")
    await inst.guest_man(event)
    (text,), _kwargs = event.reply.call_args
    _ASSERT.assertIn(SRC, text)
