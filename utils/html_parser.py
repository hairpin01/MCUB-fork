# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""
Telegram HTML Parser - Bidirectional HTML to Telegram Entities Converter
Supports parsing HTML to Telegram message entities and converting entities back to HTML.
Fixed: Correctly handles nested entities, multi-byte characters, and preserves \n line breaks.
"""

import html
from collections import deque
from html.parser import HTMLParser

from telethon.tl.types import (
    MessageEntityBlockquote,
    MessageEntityBold,
    MessageEntityCode,
    MessageEntityCustomEmoji,
    MessageEntityEmail,
    MessageEntityItalic,
    MessageEntityPre,
    MessageEntitySpoiler,
    MessageEntityStrike,
    MessageEntityTextUrl,
    MessageEntityUnderline,
)


def _utf16_len(text: str) -> int:
    """Calculate UTF-16 length of a string."""
    return len(text.encode("utf-16-le")) // 2


def _utf16_slice(text: str, offset: int, length: int) -> str:
    """Extract a substring using UTF-16 offsets."""
    if not text:
        return ""

    try:
        utf16_bytes = text.encode("utf-16-le")
        start_byte = offset * 2
        end_byte = min((offset + length) * 2, len(utf16_bytes))
        if start_byte >= end_byte:
            return ""
        return utf16_bytes[start_byte:end_byte].decode("utf-16-le")
    except Exception:
        if offset < len(text):
            return text[offset : min(offset + length, len(text))]
        return ""


class TelegramHTMLParser(HTMLParser):
    """
    Parses HTML markup and converts it to Telegram message entities.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = ""
        self.entities = []
        self._open_entities = {}
        self._tag_stack = deque()
        self._utf16_offset = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        """Handle opening HTML tags."""
        attrs_dict = dict(attrs)
        self._tag_stack.appendleft(tag)

        # Map HTML tags to Telegram entities
        if tag in ("b", "strong"):
            self._open_entities[tag] = MessageEntityBold(self._utf16_offset, 0)
        elif tag in ("i", "em"):
            self._open_entities[tag] = MessageEntityItalic(self._utf16_offset, 0)
        elif tag == "u":
            self._open_entities[tag] = MessageEntityUnderline(self._utf16_offset, 0)
        elif tag in ("s", "del", "strike"):
            self._open_entities[tag] = MessageEntityStrike(self._utf16_offset, 0)
        elif tag == "code":
            self._open_entities[tag] = MessageEntityCode(self._utf16_offset, 0)
        elif tag == "pre":
            lang = attrs_dict.get("language", "")
            self._open_entities[tag] = MessageEntityPre(
                self._utf16_offset, 0, language=lang
            )
        elif tag in ("tg-spoiler", "spoiler"):
            self._open_entities[tag] = MessageEntitySpoiler(self._utf16_offset, 0)
        elif tag == "blockquote":
            collapsed = "expandable" in attrs_dict
            self._open_entities[tag] = MessageEntityBlockquote(
                self._utf16_offset, 0, collapsed=collapsed
            )
        elif tag == "a":
            href = attrs_dict.get("href", "")
            if href.startswith("mailto:"):
                self._open_entities[tag] = MessageEntityEmail(self._utf16_offset, 0)
            elif href:
                self._open_entities[tag] = MessageEntityTextUrl(
                    self._utf16_offset, 0, url=href
                )
        elif tag == "tg-emoji":
            emoji_id = attrs_dict.get("emoji-id")
            if emoji_id and emoji_id.isdigit():
                self._open_entities[tag] = MessageEntityCustomEmoji(
                    self._utf16_offset, 0, document_id=int(emoji_id)
                )

    def handle_endtag(self, tag: str) -> None:
        """Handle closing HTML tags."""
        if tag in self._open_entities:
            entity = self._open_entities.pop(tag)
            entity.length = self._utf16_offset - entity.offset
            if entity.length > 0:
                self.entities.append(entity)

        if self._tag_stack and self._tag_stack[0] == tag:
            self._tag_stack.popleft()

    def handle_data(self, data: str) -> None:
        """Handle text data between tags."""
        if not data:
            return
        self.text += data
        self._utf16_offset += _utf16_len(data)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        """Handle self-closing tags like <br/>."""
        if tag == "br":
            self.handle_data("\n")

    def close(self) -> None:
        """Finalize parsing and sort entities."""
        super().close()
        # Sort entities by offset, then by length (longer first for proper nesting)
        self.entities.sort(key=lambda e: (e.offset, -e.length))


class HTMLDecorator:
    """
    Convert Telegram message entities back to HTML markup.
    Properly handles nested entities and preserves line breaks as \n.
    """

    def unparse(self, text: str, entities: list) -> str:
        """Convert text with entities to HTML markup."""
        if not entities:
            return html.escape(text, quote=False)

        utf16_bytes = text.encode("utf-16-le")
        total_len = len(utf16_bytes) // 2

        # Create events for the sweep-line algorithm
        events = []
        for i, entity in enumerate(entities):
            # Start: prioritize outer (longer) entities
            events.append((entity.offset, "start", -entity.length, i, entity))
            # End: prioritize inner (shorter) entities to close them first
            events.append(
                (entity.offset + entity.length, "end", entity.length, i, entity)
            )

        # Sort events: Position -> Type (end before start) -> Priority
        events.sort(key=lambda x: (x[0], 0 if x[1] == "end" else 1, x[2]))

        result_parts = []
        current_tags = []
        logical_stack = []
        last_pos = 0

        def get_chunk(start, length):
            """Extract text chunk using UTF-16 offsets."""
            s = start * 2
            e = (start + length) * 2
            return utf16_bytes[s:e].decode("utf-16-le")

        for pos, event_type, _, _, entity in events:
            # Add text before this position
            if pos > last_pos:
                chunk = get_chunk(last_pos, pos - last_pos)
                result_parts.append(html.escape(chunk, quote=False))
                last_pos = pos

            # Update logical stack
            if event_type == "start":
                logical_stack.append(entity)
                # Sort by length (longer entities outside)
                logical_stack.sort(key=lambda e: -e.length)
            else:  # end
                if entity in logical_stack:
                    logical_stack.remove(entity)

            # Reconcile current tags with logical stack
            common = 0
            for c, logical in zip(current_tags, logical_stack, strict=False):
                if c is logical:
                    common += 1
                else:
                    break

            # Close mismatched tags
            while len(current_tags) > common:
                ent = current_tags.pop()
                result_parts.append(f"</{self._get_tag(ent)}>")

            # Open new tags
            while len(current_tags) < len(logical_stack):
                ent = logical_stack[len(current_tags)]
                tag, attrs = self._get_tag_attrs(ent, text)
                attr_str = "".join(
                    [
                        f' {k}="{v}"' if v is not None else f" {k}"
                        for k, v in attrs.items()
                    ]
                )
                result_parts.append(f"<{tag}{attr_str}>")
                current_tags.append(ent)

        # Add remaining text
        if last_pos < total_len:
            result_parts.append(
                html.escape(get_chunk(last_pos, total_len - last_pos), quote=False)
            )

        # Close remaining tags
        while current_tags:
            result_parts.append(f"</{self._get_tag(current_tags.pop())}>")

        return "".join(result_parts)

    def _get_tag(self, entity):
        """Get HTML tag name for an entity."""
        t, _ = self._get_tag_attrs(entity, "")
        return t

    def _get_tag_attrs(self, entity, text_content):
        """Get HTML tag name and attributes for an entity."""
        attrs = {}
        tag = "span"

        if isinstance(entity, MessageEntityBold):
            tag = "b"
        elif isinstance(entity, MessageEntityItalic):
            tag = "i"
        elif isinstance(entity, MessageEntityUnderline):
            tag = "u"
        elif isinstance(entity, MessageEntityStrike):
            tag = "s"
        elif isinstance(entity, MessageEntityCode):
            tag = "code"
        elif isinstance(entity, MessageEntityPre):
            tag = "pre"
            if getattr(entity, "language", None):
                attrs["language"] = entity.language
        elif isinstance(entity, MessageEntitySpoiler):
            tag = "tg-spoiler"
        elif isinstance(entity, MessageEntityBlockquote):
            tag = "blockquote"
            if getattr(entity, "collapsed", False):
                attrs["expandable"] = None
        elif isinstance(entity, MessageEntityTextUrl):
            tag = "a"
            attrs["href"] = getattr(entity, "url", "")
        elif isinstance(entity, MessageEntityEmail):
            tag = "a"
            # Extract email text from the content
            try:
                email_text = _utf16_slice(text_content, entity.offset, entity.length)
                attrs["href"] = f"mailto:{email_text}"
            except Exception:
                attrs["href"] = "mailto:"
        elif isinstance(entity, MessageEntityCustomEmoji):
            tag = "tg-emoji"
            attrs["emoji-id"] = str(getattr(entity, "document_id", ""))

        return tag, attrs


def parse_html(html_text: str) -> tuple[str, list]:
    """
    Parse HTML text and extract Telegram entities.

    Args:
        html_text: HTML-formatted text

    Returns:
        Tuple of (plain_text, entities_list)
    """
    parser = TelegramHTMLParser()
    parser.feed(html_text)
    parser.close()
    return parser.text, parser.entities


def telegram_to_html(text: str, entities: list) -> str:
    """
    Convert Telegram text with entities to HTML markup.

    Args:
        text: Plain text content
        entities: List of Telegram message entities

    Returns:
        HTML-formatted text
    """
    decorator = HTMLDecorator()
    return decorator.unparse(text, entities)


def format_message(
    text: str, entities: list | None = None, as_html: bool = False
) -> str | tuple[str, list]:
    """
    Format a message either as HTML or parse HTML to entities.

    Args:
        text: Message text
        entities: Optional list of entities
        as_html: If True, convert to HTML; if False, parse HTML

    Returns:
        Either HTML string or tuple of (text, entities)
    """
    if as_html and entities:
        return telegram_to_html(text, entities)
    elif not as_html and ("<" in text and ">" in text):
        return parse_html(text)
    if entities:
        return text, entities
    return text


__all__ = [
    "HTMLDecorator",
    "TelegramHTMLParser",
    "_utf16_len",
    "_utf16_slice",
    "format_message",
    "parse_html",
    "telegram_to_html",
]
