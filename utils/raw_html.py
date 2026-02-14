# author: @Hairpin00
# version: 1.3.0
# description: raw_html for extracting HTML markup from Telethon messages
# Fixed: Line breaks now preserved as \n, improved entity handling

import html
from typing import Optional, Tuple, List, Dict, Any
from telethon.tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityCode,
    MessageEntityPre, MessageEntityTextUrl, MessageEntityUnderline,
    MessageEntityStrike, MessageEntityBlockquote, MessageEntityCustomEmoji,
    MessageEntitySpoiler, MessageEntityEmail, MessageEntityMentionName,
    MessageEntityMention, MessageEntityHashtag, MessageEntityCashtag,
    MessageEntityBotCommand, MessageEntityUrl, MessageEntityBankCard,
    MessageEntityPhone, MessageEntityUnknown
)


class RawHTMLConverter:
    """
    Converter for obtaining full HTML markup from Telethon messages.
    Preserves line breaks as \n characters instead of <br/> tags.
    """

    def __init__(self, preserve_unknown: bool = True):
        """
        Initialize the converter.

        Args:
            preserve_unknown: Whether to preserve unknown entity types
        """
        self.preserve_unknown = preserve_unknown

    def _utf16_slice(self, text: str, offset: int, length: int) -> str:
        """
        Extracts a substring from text considering UTF-16 offsets.

        Args:
            text: Source text
            offset: UTF-16 offset
            length: UTF-16 length

        Returns:
            Extracted substring
        """
        if not text:
            return ""
        try:
            utf16_bytes = text.encode('utf-16-le')
            start_byte = offset * 2
            end_byte = (offset + length) * 2
            if start_byte >= len(utf16_bytes):
                return ""
            end_byte = min(end_byte, len(utf16_bytes))
            if start_byte >= end_byte:
                return ""
            return utf16_bytes[start_byte:end_byte].decode('utf-16-le')
        except Exception:
            # Fallback to regular string slicing
            if offset < len(text):
                return text[offset:min(offset + length, len(text))]
            return ""

    def _escape_html(self, text: str) -> str:
        """
        Escapes HTML special characters while preserving newlines.

        Args:
            text: Text to escape

        Returns:
            HTML-escaped text with preserved newlines
        """
        if not text:
            return ""
        # Unescape first in case text has HTML entities
        text = html.unescape(text) if text else ""
        # Escape HTML special characters
        escaped = html.escape(text, quote=False)
        # Note: Don't replace spaces - they should be preserved as-is
        # The original code replaced '  ' with ' &nbsp;' but this causes
        # issues with leading spaces after newlines
        return escaped

    def _entity_to_html(self, entity: Any, entity_text: str) -> Tuple[str, Dict[str, str], bool]:
        """
        Converts a Telegram entity into HTML tag parameters.

        Args:
            entity: Telegram message entity
            entity_text: Text content of the entity

        Returns:
            Tuple of (tag_name, attributes_dict, is_self_closing)
        """
        attributes = {}
        tag_name = "span"
        is_self_closing = False

        if isinstance(entity, MessageEntityBold):
            tag_name = "b"
        elif isinstance(entity, MessageEntityItalic):
            tag_name = "i"
        elif isinstance(entity, MessageEntityUnderline):
            tag_name = "u"
        elif isinstance(entity, MessageEntityStrike):
            tag_name = "s"
        elif isinstance(entity, MessageEntityCode):
            tag_name = "code"
        elif isinstance(entity, MessageEntityPre):
            tag_name = "pre"
            if hasattr(entity, 'language') and entity.language:
                attributes['language'] = entity.language
        elif isinstance(entity, MessageEntityTextUrl):
            tag_name = "a"
            if hasattr(entity, 'url') and entity.url:
                attributes['href'] = entity.url
        elif isinstance(entity, MessageEntityUrl):
            tag_name = "a"
            if entity_text.startswith(('http://', 'https://', 'ftp://', 'tg://')):
                attributes['href'] = entity_text
        elif isinstance(entity, MessageEntityEmail):
            tag_name = "a"
            attributes['href'] = f"mailto:{entity_text}"
        elif isinstance(entity, MessageEntityCustomEmoji):
            tag_name = "tg-emoji"
            if hasattr(entity, 'document_id'):
                attributes['emoji-id'] = str(entity.document_id)
        elif isinstance(entity, MessageEntitySpoiler):
            tag_name = "tg-spoiler"
        elif isinstance(entity, MessageEntityBlockquote):
            tag_name = "blockquote"
            if hasattr(entity, 'collapsed') and entity.collapsed:
                attributes['expandable'] = "true"
        elif isinstance(entity, MessageEntityMention):
            tag_name = "a"
            if entity_text.startswith('@'):
                attributes['href'] = f"tg://resolve?domain={entity_text[1:]}"
        elif isinstance(entity, MessageEntityMentionName):
            tag_name = "a"
            if hasattr(entity, 'user_id'):
                attributes['href'] = f"tg://user?id={entity.user_id}"
        elif isinstance(entity, MessageEntityHashtag):
            tag_name = "a"
            attributes['class'] = "hashtag"
        elif isinstance(entity, MessageEntityBotCommand):
            tag_name = "code"
        elif isinstance(entity, MessageEntityBankCard):
            tag_name = "code"
        elif isinstance(entity, MessageEntityPhone):
            tag_name = "a"
            # Clean phone number for tel: link
            clean_phone = entity_text.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
            if clean_phone.isdigit():
                attributes['href'] = f"tel:{entity_text}"
        elif isinstance(entity, MessageEntityCashtag):
            tag_name = "span"
            attributes['class'] = "cashtag"
        elif isinstance(entity, MessageEntityUnknown) and self.preserve_unknown:
            tag_name = "span"
            attributes['class'] = "tg-unknown-entity"
            attributes['data-type'] = str(type(entity).__name__)

        return tag_name, attributes, is_self_closing

    def _process_entities(self, text: str, entities: List) -> str:
        """
        Smart entity processing. Builds a clean tag tree,
        avoiding duplication and properly nesting entities.
        Line breaks are preserved as \n characters.

        Args:
            text: Plain text content
            entities: List of Telegram message entities

        Returns:
            HTML-formatted text
        """
        if not entities:
            return self._escape_html(text)

        # Create events for sweep-line algorithm
        # Each event: (position, type, priority, index, entity)
        events = []
        for i, entity in enumerate(entities):
            # Start event: longer entities get higher priority (negative length)
            events.append((entity.offset, 'start', -entity.length, i, entity))
            # End event: shorter entities close first (positive length)
            events.append((entity.offset + entity.length, 'end', entity.length, i, entity))

        # Sort events: Position -> Type (end before start) -> Priority
        events.sort(key=lambda x: (x[0], 0 if x[1] == 'end' else 1, x[2]))

        result_parts = []
        current_tags = []  # Currently open HTML tags
        logical_stack = []  # Entities that should be active
        last_pos = 0

        for pos, event_type, _, _, entity in events:
            # Add text segment before this position
            if pos > last_pos:
                segment = self._utf16_slice(text, last_pos, pos - last_pos)
                if segment:
                    result_parts.append(self._escape_html(segment))
                last_pos = pos

            # Update logical stack based on event type
            if event_type == 'start':
                logical_stack.append(entity)
                # Sort stack: longest entities first (outer tags)
                logical_stack.sort(key=lambda e: -e.length)
            else:  # end
                if entity in logical_stack:
                    logical_stack.remove(entity)

            # Reconcile current tags with logical stack
            # Find common prefix that doesn't need changes
            common_len = 0
            for i in range(min(len(current_tags), len(logical_stack))):
                if current_tags[i] is logical_stack[i]:
                    common_len += 1
                else:
                    break

            # Close extra tags (from the end)
            while len(current_tags) > common_len:
                entity_to_close = current_tags.pop()
                tag_name, _, _ = self._entity_to_html(entity_to_close, "")
                result_parts.append(f"</{tag_name}>")

            # Open new tags
            while len(current_tags) < len(logical_stack):
                entity_to_open = logical_stack[len(current_tags)]
                # Get entity text for attributes that need it
                entity_text = self._utf16_slice(text, entity_to_open.offset, entity_to_open.length)
                tag_name, attrs, _ = self._entity_to_html(entity_to_open, entity_text)

                # Build attributes string
                if attrs:
                    attrs_str = ' ' + ' '.join([f'{k}="{v}"' for k, v in attrs.items()])
                else:
                    attrs_str = ''

                result_parts.append(f"<{tag_name}{attrs_str}>")
                current_tags.append(entity_to_open)

        # Add remaining text after last entity
        total_len = len(text.encode('utf-16-le')) // 2
        if last_pos < total_len:
            segment = self._utf16_slice(text, last_pos, total_len - last_pos)
            if segment:
                result_parts.append(self._escape_html(segment))

        # Close any remaining open tags
        while current_tags:
            entity_to_close = current_tags.pop()
            tag_name, _, _ = self._entity_to_html(entity_to_close, "")
            result_parts.append(f"</{tag_name}>")

        return "".join(result_parts)

    def convert_message(self, message) -> str:
        """
        Convert a Telethon message to HTML markup.

        Args:
            message: Telethon message object

        Returns:
            HTML-formatted text
        """
        if not message:
            return ""

        # Handle messages with media (might have captions)
        if hasattr(message, 'media') and message.media:
            text = getattr(message, 'message', '') or getattr(message, 'text', '') or ''

            # Check for caption in media
            if hasattr(message.media, 'caption'):
                text = message.media.caption or ''

            # Get entities from caption or message
            if hasattr(message.media, 'caption_entities'):
                entities = message.media.caption_entities or []
            elif hasattr(message, 'entities'):
                entities = message.entities or []
            else:
                entities = []
        else:
            # Regular message without media
            text = getattr(message, 'message', '') or getattr(message, 'text', '') or ''
            entities = getattr(message, 'entities', []) or []

        # Ensure text is not None
        text = text or ""

        if not text and not entities:
            return ""

        return self._process_entities(text, entities)

    def convert_event(self, event) -> str:
        """
        Convert a Telethon event to HTML markup.

        Args:
            event: Telethon event object

        Returns:
            HTML-formatted text
        """
        if not event:
            return ""

        if hasattr(event, 'message'):
            return self.convert_message(event.message)
        elif hasattr(event, 'text'):
            text = event.text or ""
            return self._escape_html(text)
        return ""


def message_to_html(message, detailed: bool = False) -> str:
    """
    Convert a Telegram message to HTML format.

    Args:
        message: Telethon message object
        detailed: If True, include metadata like message ID and sender ID

    Returns:
        HTML-formatted message
    """
    if not message:
        return ""

    converter = RawHTMLConverter()
    html_content = converter.convert_message(message)

    if detailed:
        metadata = []
        if hasattr(message, 'id'):
            metadata.append(f"Message ID: {message.id}")
        if hasattr(message, 'sender_id'):
            metadata.append(f"Sender ID: {message.sender_id}")
        if hasattr(message, 'date'):
            metadata.append(f"Date: {message.date}")

        if metadata:
            metadata_html = "<div style='color: #666; font-size: 0.9em; border-left: 2px solid #ccc; padding-left: 10px; margin-bottom: 15px;'>"
            metadata_html += "<strong>Metadata:</strong><br/>" + "<br/>".join(metadata)
            metadata_html += "</div>"
            html_content = metadata_html + html_content

    return html_content


def event_to_html(event, detailed: bool = False) -> str:
    """
    Convert a Telegram event to HTML format.

    Args:
        event: Telethon event object
        detailed: If True, include metadata

    Returns:
        HTML-formatted event content
    """
    if not event:
        return ""

    converter = RawHTMLConverter()
    return converter.convert_event(event)


def extract_raw_html(message, escape: bool = False) -> str:
    """
    Extract raw HTML markup from a Telegram message.

    Args:
        message: Telethon message object
        escape: If True, escape the HTML output (for display purposes)

    Returns:
        HTML markup string
    """
    if not message:
        return ""

    converter = RawHTMLConverter()
    html_content = converter.convert_message(message)

    if not html_content:
        return ""

    if escape:
        return html.escape(html_content)
    return html_content


def debug_entities(message) -> List[Dict]:
    """
    Debug helper to inspect message entities.

    Args:
        message: Telethon message object

    Returns:
        List of dictionaries containing entity information
    """
    if not message:
        return []

    # Extract text and entities from message
    if hasattr(message, 'media') and message.media:
        text = getattr(message, 'message', '') or getattr(message, 'text', '') or ''

        if hasattr(message.media, 'caption'):
            text = message.media.caption or ''

        if hasattr(message.media, 'caption_entities'):
            entity_list = message.media.caption_entities or []
        elif hasattr(message, 'entities'):
            entity_list = message.entities or []
        else:
            entity_list = []
    else:
        text = getattr(message, 'message', '') or getattr(message, 'text', '') or ''
        entity_list = getattr(message, 'entities', []) or []

    # Ensure text is not None
    text = text or ""

    # Create debug info for each entity
    converter = RawHTMLConverter()
    entities_info = []
    for entity in entity_list:
        entity_text = converter._utf16_slice(text, entity.offset, entity.length)
        entities_info.append({
            'type': type(entity).__name__,
            'offset': entity.offset,
            'length': entity.length,
            'text': entity_text,
            'repr': repr(entity)
        })

    return entities_info


# Global converter instance for convenience
raw_html_converter = RawHTMLConverter()

__all__ = [
    'RawHTMLConverter',
    'message_to_html',
    'event_to_html',
    'extract_raw_html',
    'debug_entities',
    'raw_html_converter'
]
