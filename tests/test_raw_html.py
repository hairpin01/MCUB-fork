"""
Hard tests for utils.raw_html.
"""

from types import SimpleNamespace

from telethon.tl.types import (
    MessageEntityBlockquote,
    MessageEntityBold,
    MessageEntityCustomEmoji,
    MessageEntityEmail,
    MessageEntityItalic,
    MessageEntityMention,
    MessageEntityMentionName,
    MessageEntityPhone,
    MessageEntityPre,
    MessageEntitySpoiler,
    MessageEntityTextUrl,
    MessageEntityUnknown,
    MessageEntityUrl,
)

from utils.raw_html import (
    RawHTMLConverter,
    debug_entities,
    event_to_html,
    extract_raw_html,
    message_to_html,
)


def _u16_offset(text: str, codepoint_index: int) -> int:
    return len(text[:codepoint_index].encode("utf-16-le")) // 2


def _u16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


class TestRawHtmlConverter:
    def test_plain_text_escaped_and_newlines_preserved(self):
        converter = RawHTMLConverter()
        msg = SimpleNamespace(message="a < b & c\nnext")
        assert converter.convert_message(msg) == "a &lt; b &amp; c\nnext"

    def test_nested_entities_order_and_reopen(self):
        converter = RawHTMLConverter()
        text = "abcdefghij"
        msg = SimpleNamespace(
            message=text,
            entities=[
                MessageEntityBold(offset=0, length=10),
                MessageEntityItalic(offset=2, length=5),
            ],
        )
        assert converter.convert_message(msg) == "<strong>ab<em>cdefg</em>hij</strong>"

    def test_utf16_offsets_with_surrogate_pairs(self):
        converter = RawHTMLConverter()
        text = "A😀B"
        # emoji takes 2 UTF-16 code units
        msg = SimpleNamespace(
            message=text,
            entities=[
                MessageEntityBold(offset=_u16_offset(text, 1), length=_u16_len("😀"))
            ],
        )
        assert converter.convert_message(msg) == "A<strong>😀</strong>B"

    def test_pre_entity_uses_code_language_class(self):
        converter = RawHTMLConverter()
        msg = SimpleNamespace(
            message="print(1)",
            entities=[MessageEntityPre(offset=0, length=8, language="python")],
        )
        assert (
            converter.convert_message(msg)
            == '<pre><code class="language-python">print(1)</code></pre>'
        )

    def test_blockquote_expandable_boolean_attribute(self):
        converter = RawHTMLConverter()
        msg = SimpleNamespace(
            message="quote",
            entities=[MessageEntityBlockquote(offset=0, length=5, collapsed=True)],
        )
        assert (
            converter.convert_message(msg)
            == "<blockquote expandable>quote</blockquote>"
        )

    def test_links_mention_and_attribute_escaping(self):
        converter = RawHTMLConverter()
        text = "link mail @user name"
        msg = SimpleNamespace(
            message=text,
            entities=[
                MessageEntityTextUrl(offset=0, length=4, url="https://ex.com?a=1&b=2"),
                MessageEntityEmail(offset=5, length=4),
                MessageEntityMention(offset=10, length=5),
                MessageEntityMentionName(offset=16, length=4, user_id=42),
            ],
        )
        assert converter.convert_message(msg) == (
            '<a href="https://ex.com?a=1&amp;b=2">link</a> '
            '<a href="mailto:mail">mail</a> '
            '<a href="tg://resolve?domain=user">@user</a> '
            '<a href="tg://user?id=42">name</a>'
        )

    def test_url_phone_custom_emoji_spoiler_unknown(self):
        converter = RawHTMLConverter()
        text = "site +1 (234) 567-89 😀 xy"
        phone_text = "+1 (234) 567-89"
        emoji_index = text.index("😀")
        phone_index = text.index(phone_text)
        x_index = text.rindex("x")
        y_index = text.rindex("y")
        entities = [
            MessageEntityUrl(offset=0, length=4),
            MessageEntityPhone(
                offset=_u16_offset(text, phone_index),
                length=_u16_len(phone_text),
            ),
            MessageEntityCustomEmoji(
                offset=_u16_offset(text, emoji_index),
                length=_u16_len("😀"),
                document_id=123456789,
            ),
            MessageEntitySpoiler(offset=_u16_offset(text, x_index), length=1),
            MessageEntityUnknown(offset=_u16_offset(text, y_index), length=1),
        ]
        msg = SimpleNamespace(message=text, entities=entities)
        assert converter.convert_message(msg) == (
            '<a href="site">site</a> '
            '<a href="tel:+1 (234) 567-89">+1 (234) 567-89</a> '
            '<tg-emoji emoji-id="123456789">😀</tg-emoji> '
            '<tg-spoiler>x</tg-spoiler><span class="tg-unknown-entity" '
            'data-type="MessageEntityUnknown">y</span>'
        )

    def test_media_caption_and_caption_entities_take_priority(self):
        converter = RawHTMLConverter()
        msg = SimpleNamespace(
            message="fallback",
            entities=[MessageEntityBold(offset=0, length=8)],
            media=SimpleNamespace(
                caption="caption",
                caption_entities=[MessageEntityItalic(offset=0, length=7)],
            ),
        )
        assert converter.convert_message(msg) == "<em>caption</em>"

    def test_convert_event_prefers_event_message(self):
        converter = RawHTMLConverter()
        event = SimpleNamespace(message=SimpleNamespace(message="ok"))
        assert converter.convert_event(event) == "ok"

    def test_convert_event_text_fallback_escapes(self):
        converter = RawHTMLConverter()
        event = SimpleNamespace(text="<tag>")
        assert converter.convert_event(event) == "&lt;tag&gt;"


class TestRawHtmlPublicApi:
    def test_message_to_html_with_detailed_metadata(self):
        msg = SimpleNamespace(
            message="x",
            id=7,
            sender_id=99,
            date="2026-03-04T00:00:00",
        )
        html = message_to_html(msg, detailed=True)
        assert "<strong>Metadata:</strong>" in html
        assert "Message ID: 7" in html
        assert "Sender ID: 99" in html
        assert "Date: 2026-03-04T00:00:00" in html
        assert html.endswith("x")

    def test_event_to_html_uses_converter(self):
        event = SimpleNamespace(text="a & b")
        assert event_to_html(event) == "a &amp; b"

    def test_extract_raw_html_escape_flag(self):
        msg = SimpleNamespace(
            message="x", entities=[MessageEntityBold(offset=0, length=1)]
        )
        assert extract_raw_html(msg) == "<strong>x</strong>"
        assert extract_raw_html(msg, escape=True) == "&lt;strong&gt;x&lt;/strong&gt;"

    def test_debug_entities_returns_sliced_text(self):
        text = "A😀B"
        msg = SimpleNamespace(
            message=text,
            entities=[
                MessageEntityBold(offset=0, length=1),
                MessageEntityBold(offset=_u16_offset(text, 1), length=_u16_len("😀")),
            ],
        )
        info = debug_entities(msg)
        assert len(info) == 2
        assert info[0]["text"] == "A"
        assert info[1]["text"] == "😀"
        assert info[1]["type"] == "MessageEntityBold"
