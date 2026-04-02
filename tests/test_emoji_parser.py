"""
Tests for utils.emoji_parser.
"""

from types import SimpleNamespace

from telethon.tl.types import MessageEntityBold, MessageEntityCustomEmoji

from utils.emoji_parser import EmojiParser


def _u16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


class TestEmojiParser:
    def test_parse_to_entities_multiple_tags_and_offsets(self):
        source = "X <emoji document_id=1>😀</emoji> Y <emoji document_id=2>🚀</emoji>"
        text, entities = EmojiParser.parse_to_entities(source)

        assert text == "X 😀 Y 🚀"
        assert len(entities) == 2

        assert entities[0].document_id == 1
        assert entities[0].offset == _u16_len("X ")
        assert entities[0].length == _u16_len("😀")

        assert entities[1].document_id == 2
        assert entities[1].offset == _u16_len("X 😀 Y ")
        assert entities[1].length == _u16_len("🚀")

    def test_entities_to_html_escapes_generated_tags(self):
        text = "Hi 😀!"
        entities = [MessageEntityCustomEmoji(offset=3, length=2, document_id=123)]
        html_text = EmojiParser.entities_to_html(text, entities)
        assert "&lt;emoji document_id=123&gt;😀&lt;/emoji&gt;" in html_text

    def test_is_emoji_tag_extract_ids_and_remove_tags(self):
        text = "A <emoji document_id=11>🔴</emoji> B <emoji document_id=22>🟢</emoji>"
        assert EmojiParser.is_emoji_tag(text) is True
        assert EmojiParser.extract_emoji_ids(text) == [11, 22]
        assert EmojiParser.remove_emoji_tags(text) == "A 🔴 B 🟢"

    def test_extract_custom_emoji_entities_filters_only_custom(self):
        msg = SimpleNamespace(
            entities=[
                MessageEntityBold(offset=0, length=1),
                MessageEntityCustomEmoji(offset=1, length=2, document_id=42),
            ]
        )
        result = EmojiParser.extract_custom_emoji_entities(msg)
        assert len(result) == 1
        assert isinstance(result[0], MessageEntityCustomEmoji)
        assert result[0].document_id == 42

    def test_validate_content_and_create_tag(self):
        assert EmojiParser.validate_emoji_content("😀") is True
        assert EmojiParser.validate_emoji_content("abc") is False
        assert EmojiParser.validate_emoji_content("") is False
        assert (
            EmojiParser.create_emoji_tag(999, "🧪")
            == "<emoji document_id=999>🧪</emoji>"
        )
