"""
Tests for utils.message_helpers.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telethon.tl.types import MessageEntityBold

import utils.message_helpers as mh


class TestCleanHtmlFallback:
    def test_cleans_tags_and_decodes_entities(self):
        html_text = (
            '<b>Hello</b> <a href="https://example.com">Link</a> '
            '<tg-emoji emoji-id="1">😎</tg-emoji> &amp; <br> done'
        )
        assert mh.clean_html_fallback(html_text) == "Hello Link 😎 & done"

    def test_handles_legacy_img_emoji(self):
        html_text = (
            'x <img src="tg://emoji?id=111" alt="🙂"> '
            '<img src="tg://emoji?id=222"> y'
        )
        assert mh.clean_html_fallback(html_text) == "x 🙂 y"


class TestTruncateTextWithEntities:
    def test_truncates_by_utf16_and_adjusts_entities(self):
        text = "A😀BC"
        entities = [MessageEntityBold(offset=0, length=4)]
        truncated_text, truncated_entities = mh.truncate_text_with_entities(
            text, entities, max_length=3
        )
        assert truncated_text == "A😀"
        assert len(truncated_entities) == 1
        assert truncated_entities[0].offset == 0
        assert truncated_entities[0].length == 3


class TestSendHtmlGeneric:
    @pytest.mark.asyncio
    async def test_success_path_uses_formatting_entities(self, monkeypatch):
        entity = MessageEntityBold(offset=0, length=2)
        monkeypatch.setattr(mh, "parse_html", lambda _html: ("ok", [entity]))

        sent = {}

        async def send_func(text, **kwargs):
            sent["text"] = text
            sent["kwargs"] = kwargs
            return "sent-ok"

        kernel = SimpleNamespace(handle_error=AsyncMock())
        result = await mh._send_html_generic(send_func, "<b>ok</b>", kernel)

        assert result == "sent-ok"
        assert sent["text"] == "ok"
        assert sent["kwargs"]["formatting_entities"] == [entity]
        kernel.handle_error.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fallback_path_cleans_text_and_reports_error(self, monkeypatch):
        def _raise(_html):
            raise ValueError("bad html")

        monkeypatch.setattr(mh, "parse_html", _raise)

        sent = {}

        async def send_func(text, **kwargs):
            sent["text"] = text
            sent["kwargs"] = kwargs
            return "fallback-ok"

        send_func.__name__ = "edit"
        kernel = SimpleNamespace(handle_error=AsyncMock())
        result = await mh._send_html_generic(
            send_func,
            "<b>Hi</b> <tg-emoji emoji-id='1'>😎</tg-emoji>",
            kernel,
        )

        assert result == "fallback-ok"
        assert sent["text"] == "Hi 😎"
        kernel.handle_error.assert_awaited_once()
        assert kernel.handle_error.await_args.kwargs["source"] == "edit_with_html"


class TestWrappers:
    @pytest.mark.asyncio
    async def test_send_with_html_wrapper(self, monkeypatch):
        monkeypatch.setattr(mh, "parse_html", lambda _html: ("body", []))
        kernel = SimpleNamespace(handle_error=AsyncMock())
        client = SimpleNamespace(send_message=AsyncMock(return_value="ok"))

        result = await mh.send_with_html(kernel, client, 123, "<b>body</b>", parse_mode=None)
        assert result == "ok"
        client.send_message.assert_awaited_once_with(
            123,
            "body",
            formatting_entities=[],
            parse_mode=None,
        )

    @pytest.mark.asyncio
    async def test_send_file_with_html_wrapper(self, monkeypatch):
        monkeypatch.setattr(mh, "parse_html", lambda _html: ("cap", []))
        kernel = SimpleNamespace(handle_error=AsyncMock())
        client = SimpleNamespace(send_file=AsyncMock(return_value="ok-file"))

        result = await mh.send_file_with_html(
            kernel,
            client,
            321,
            "<b>cap</b>",
            file="photo.png",
        )
        assert result == "ok-file"
        client.send_file.assert_awaited_once_with(
            321,
            "photo.png",
            caption="cap",
            formatting_entities=[],
        )
