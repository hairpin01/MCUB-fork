"""
Telegram HTML Parser - Bidirectional HTML ↔ Telegram Entities Converter
Supports parsing HTML to Telegram message entities and converting entities back to HTML.
"""

import re
import struct
from collections import deque
from html import escape as html_escape
from html.parser import HTMLParser
from typing import Optional, Tuple, List, Dict, Any, Union
from telethon.tl.types import MessageEntityCustomEmoji

class TelegramHTMLParser(HTMLParser):
    """
    Parses HTML markup and converts it to Telegram message entities.
    Handles nested tags, custom emojis, spoilers, and surrogate pairs correctly.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = ''
        self.entities = []

        # Store currently open entities {tag_name: entity}
        self._open_entities = {}

        # Stack for tracking opening order of tags
        self._tag_stack = deque()

        # UTF-16 offset in the final text
        self._utf16_offset = 0

    def _utf16_len(self, text: str) -> int:
        """Calculate length of text in UTF-16 code units."""
        return len(text.encode('utf-16-le')) // 2

    def _add_surrogate(self, text: str) -> str:
        """
        Convert text with characters outside Basic Multilingual Plane (BMP)
        to surrogate pairs for correct offset calculation.
        """
        return ''.join(
            ''.join(chr(y) for y in struct.unpack('<HH', x.encode('utf-16le')))
            if 0x10000 <= ord(x) <= 0x10FFFF else x
            for x in text
        )

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        """Handle opening HTML tags and create corresponding Telegram entities."""
        attrs_dict = dict(attrs)
        self._tag_stack.appendleft(tag)

        # Map HTML tags to Telegram entity types
        entity_map = {
            ('b', 'strong'): ('bold', {}),
            ('i', 'em'): ('italic', {}),
            ('u',): ('underline', {}),
            ('s', 'del'): ('strike', {}),
            ('code',): ('code', {}),
            ('pre',): ('pre', {'language': attrs_dict.get('language', '')}),
            ('tg-spoiler', 'spoiler'): ('spoiler', {}),
            ('blockquote',): ('blockquote', {
                'collapsed': 'expandable' in attrs_dict
            }),
        }

        # Check for link tag
        if tag == 'a':
            href = attrs_dict.get('href', '')
            if href.startswith('mailto:'):
                self._open_entities[tag] = MessageEntityEmail(
                    offset=self._utf16_offset,
                    length=0,
                    url=href[7:]  # Remove 'mailto:' prefix
                )
            elif href:
                self._open_entities[tag] = MessageEntityTextUrl(
                    offset=self._utf16_offset,
                    length=0,
                    url=href
                )
            return

        # Check for custom emoji tag
        if tag == 'tg-emoji':
            emoji_id = attrs_dict.get('emoji-id')
            try:
                document_id = int(emoji_id)
                self._open_entities[tag] = MessageEntityCustomEmoji(
                    offset=self._utf16_offset,
                    length=0,
                    document_id=document_id
                )
            except (ValueError, TypeError):
                pass
            return

        # Check for img tag with emoji (legacy format)
        if tag == 'img':
            src = attrs_dict.get('src', '')
            if src.startswith('tg://emoji?id='):
                try:
                    document_id = int(src.split('=')[1])
                    # Add placeholder text and immediate entity
                    placeholder = attrs_dict.get('alt', '\u2060')
                    start_offset = self._utf16_offset
                    self.handle_data(placeholder)
                    self.entities.append(MessageEntityCustomEmoji(
                        offset=start_offset,
                        length=self._utf16_len(placeholder),
                        document_id=document_id
                    ))
                except (ValueError, IndexError):
                    pass
            return

        # Handle other tags from entity_map
        for tags, (entity_type, extra_args) in entity_map.items():
            if tag in tags:
                entity_class = self._get_entity_class(entity_type)
                if entity_class:
                    entity = entity_class(
                        offset=self._utf16_offset,
                        length=0,
                        **extra_args
                    )
                    self._open_entities[tag] = entity
                break

    def handle_endtag(self, tag: str) -> None:
        """Handle closing HTML tags and finalize corresponding entities."""
        if tag in self._open_entities:
            entity = self._open_entities.pop(tag)
            # Only add entity if it has content
            if entity.length > 0:
                self.entities.append(entity)

        # Clean up tag stack
        if self._tag_stack and self._tag_stack[0] == tag:
            self._tag_stack.popleft()

    def handle_data(self, data: str) -> None:
        """Process text data and update lengths of all open entities."""
        if not data:
            return

        # Add text to output
        self.text += data

        # Calculate UTF-16 length of added text
        text_len = self._utf16_len(data)

        # Update UTF-16 offset for future entities
        self._utf16_offset += text_len

        # Extend length of all open entities
        for entity in self._open_entities.values():
            entity.length += text_len

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        """Handle self-closing tags (like <br/>)."""
        if tag == 'br':
            self.handle_data('\n')

    def _get_entity_class(self, entity_type: str):
        """Map entity type string to Telegram entity class."""
        from telethon.tl.types import (
            MessageEntityBold, MessageEntityItalic, MessageEntityCode,
            MessageEntityPre, MessageEntityTextUrl, MessageEntityUnderline,
            MessageEntityStrike, MessageEntityBlockquote, MessageEntityCustomEmoji,
            MessageEntitySpoiler, MessageEntityEmail, MessageEntityUrl
        )

        type_map = {
            'bold': MessageEntityBold,
            'italic': MessageEntityItalic,
            'code': MessageEntityCode,
            'pre': MessageEntityPre,
            'underline': MessageEntityUnderline,
            'strike': MessageEntityStrike,
            'blockquote': MessageEntityBlockquote,
            'spoiler': MessageEntitySpoiler,
            'email': MessageEntityEmail,
            'url': MessageEntityUrl,
            'text_url': MessageEntityTextUrl,
            'custom_emoji': MessageEntityCustomEmoji,
        }
        return type_map.get(entity_type)

    def close(self) -> None:
        """Finalize parsing and clean up any remaining open entities."""
        super().close()

        # Sort entities by offset (ascending) and length (descending)
        # This ensures proper nesting in Telegram
        self.entities.sort(key=lambda e: (e.offset, -e.length))


def parse_html(html_text: str) -> Tuple[str, List]:
    """
    Parse HTML text into plain text and Telegram message entities.

    Args:
        html_text: HTML-formatted string

    Returns:
        Tuple of (plain_text, entities)
    """
    parser = TelegramHTMLParser()
    parser.feed(html_text)
    parser.close()
    return parser.text, parser.entities


class HTMLDecorator:
    """
    Convert Telegram message entities back to HTML markup.
    This enables bidirectional conversion between HTML and Telegram format.
    """

    @staticmethod
    def apply_entity(entity, text: str) -> str:
        """Apply a single entity to text, converting it to HTML tag."""
        from telethon.tl.types import (
            MessageEntityBold, MessageEntityItalic, MessageEntityUnderline,
            MessageEntityStrike, MessageEntityCode, MessageEntityPre,
            MessageEntitySpoiler, MessageEntityBlockquote, MessageEntityTextUrl,
            MessageEntityEmail, MessageEntityCustomEmoji
        )

        # Map entity types to HTML tags
        if isinstance(entity, MessageEntityBold):
            return f'<b>{text}</b>'
        elif isinstance(entity, MessageEntityItalic):
            return f'<i>{text}</i>'
        elif isinstance(entity, MessageEntityUnderline):
            return f'<u>{text}</u>'
        elif isinstance(entity, MessageEntityStrike):
            return f'<s>{text}</s>'
        elif isinstance(entity, MessageEntityCode):
            return f'<code>{text}</code>'
        elif isinstance(entity, MessageEntityPre):
            if hasattr(entity, 'language') and entity.language:
                return f'<pre language="{entity.language}">{text}</pre>'
            return f'<pre>{text}</pre>'
        elif isinstance(entity, MessageEntitySpoiler):
            return f'<tg-spoiler>{text}</tg-spoiler>'
        elif isinstance(entity, MessageEntityBlockquote):
            if getattr(entity, 'collapsed', False):
                return f'<blockquote expandable>{text}</blockquote>'
            return f'<blockquote>{text}</blockquote>'
        elif isinstance(entity, MessageEntityTextUrl):
            url = getattr(entity, 'url', '')
            return f'<a href="{url}">{text}</a>'
        elif isinstance(entity, MessageEntityEmail):
            email = getattr(entity, 'url', text)
            return f'<a href="mailto:{email}">{text}</a>'
        elif isinstance(entity, MessageEntityCustomEmoji):
            doc_id = getattr(entity, 'document_id', 0)
            return f'<tg-emoji emoji-id="{doc_id}">{text}</tg-emoji>'

        # Default: escape text without formatting
        return html_escape(text, quote=False)

    def unparse(self, text: str, entities: List) -> str:
        """
        Convert plain text with Telegram entities back to HTML markup.

        Args:
            text: Plain text
            entities: List of Telegram message entities

        Returns:
            HTML-formatted string
        """
        if not entities:
            return html_escape(text, quote=False)

        # Sort entities by offset
        entities = sorted(entities, key=lambda e: e.offset)

        # Convert text to UTF-16 code units for accurate positioning
        utf16_text = text.encode('utf-16-le')
        result_parts = []
        last_pos = 0

        for entity in entities:
            # Calculate positions in UTF-16 code units
            start = entity.offset * 2
            end = start + entity.length * 2

            # Add text before entity
            if last_pos < start:
                before_text = utf16_text[last_pos:start].decode('utf-16-le')
                result_parts.append(html_escape(before_text, quote=False))

            # Extract entity text and apply formatting
            entity_text = utf16_text[start:end].decode('utf-16-le')
            result_parts.append(self.apply_entity(entity, entity_text))

            last_pos = end

        # Add remaining text after last entity
        if last_pos < len(utf16_text):
            after_text = utf16_text[last_pos:].decode('utf-16-le')
            result_parts.append(html_escape(after_text, quote=False))

        return ''.join(result_parts)


# Convenience functions for easy use
def html_to_telegram(html_text: str) -> Tuple[str, List]:
    """Convert HTML to Telegram format (text + entities)."""
    return parse_html(html_text)


def telegram_to_html(text: str, entities: List) -> str:
    """Convert Telegram format (text + entities) back to HTML."""
    decorator = HTMLDecorator()
    return decorator.unparse(text, entities)


def format_message(text: str, entities: Optional[List] = None,
                   as_html: bool = False) -> Union[str, Tuple[str, List]]:
    """
    Format message in desired format.

    Args:
        text: Input text (could be HTML or plain)
        entities: Telegram entities (if text is plain)
        as_html: If True, return HTML; if False, return Telegram format

    Returns:
        Formatted message in requested format
    """
    if as_html and entities:
        # Convert Telegram format to HTML
        return telegram_to_html(text, entities)
    elif not as_html and ('<' in text and '>' in text):
        # Convert HTML to Telegram format
        return html_to_telegram(text)

    # Return as-is
    if entities:
        return text, entities
    return text


# Example usage
if __name__ == "__main__":
    # Example 1: Parse HTML to Telegram format
    html_example = """
    <b>Hello</b> <i>world!</i>
    Check out <a href="https://example.com">this link</a>
    <tg-spoiler>Hidden text</tg-spoiler>
    <tg-emoji emoji-id="12345">🎉</tg-emoji>
    """

    text, entities = html_to_telegram(html_example)
    print("Parsed text:", text)
    print("Entities count:", len(entities))

    # Example 2: Convert back to HTML
    restored_html = telegram_to_html(text, entities)
    print("\nRestored HTML:", restored_html)

    # Example 3: Using format_message helper
    formatted = format_message(html_example, as_html=False)
    print("\nFormatted for Telegram:", formatted[0])

def _utf16_len(text: str) -> int:
    """Calculate length of text in UTF-16 code units."""
    return len(text.encode('utf-16-le')) // 2


__all__ = [
    'TelegramHTMLParser',
    'parse_html',
    'html_to_telegram',
    'telegram_to_html',
    'format_message',
    '_utf16_len',
    'HTMLDecorator',
]
