# author: @Hairpin00
# version: 1.2.0
# description: raw_html for extracting HTML markup from Telethon messages

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
    """

    def __init__(self, preserve_unknown: bool = True, keep_newlines: bool = True):
        self.preserve_unknown = preserve_unknown
        self.keep_newlines = keep_newlines

    def _utf16_slice(self, text: str, offset: int, length: int) -> str:
        """Extracts a substring from text considering UTF-16 offsets."""
        if not text:
            return ""
        try:
            utf16_bytes = text.encode('utf-16-le')
            start_byte = offset * 2
            end_byte = (offset + length) * 2
            if start_byte >= len(utf16_bytes): return ""
            end_byte = min(end_byte, len(utf16_bytes))
            if start_byte >= end_byte: return ""
            return utf16_bytes[start_byte:end_byte].decode('utf-16-le')
        except Exception:
            if offset < len(text):
                return text[offset:min(offset + length, len(text))]
            return ""

    def _escape_html_smart(self, text: str) -> str:
        """Escapes text while preserving line breaks."""
        if not text: return ""
        text = html.unescape(text)
        if self.keep_newlines:
            lines = text.split('\n')
            result_lines = []
            for line in lines:
                escaped = html.escape(line).replace('  ', ' &nbsp;')
                result_lines.append(escaped)
            return '<br/>'.join(result_lines)
        else:
            return html.escape(text).replace('  ', ' &nbsp;')

    def _entity_to_html(self, entity: Any, entity_text: str) -> Tuple[str, Dict[str, str], bool]:
        """Converts a Telegram entity into HTML tag parameters."""
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
            if entity_text.replace('+', '').replace('-', '').replace(' ', '').isdigit():
                attributes['href'] = f"tel:{entity_text}"
        elif isinstance(entity, MessageEntityCashtag):
            tag_name = "span"
            attributes['class'] = "cashtag"
        elif isinstance(entity, MessageEntityUnknown) and self.preserve_unknown:
            tag_name = "span"
            attributes['class'] = "tg-unknown-entity"
            attributes['data-type'] = str(type(entity))

        return tag_name, attributes, is_self_closing

    def _process_entities(self, text: str, entities: List) -> str:
        """
        Smart entity processing. Builds a clean tag tree,
        avoiding duplication and block breaks.
        """
        if not entities:
            return self._escape_html_smart(text)

        # 1. Create events: (position, type, sorting priority, index, entity)
        # Sorting priority is important:
        # - END first (to close nested tags before opening new ones)
        # - Long entities (Blockquote) should be "outside" short ones (Bold)
        events = []
        for i, entity in enumerate(entities):
            # start: length priority (longer ones earlier to be higher in stack)
            events.append((entity.offset, 'start', -entity.length, i, entity))
            # end: length priority (short ones earlier to close first)
            events.append((entity.offset + entity.length, 'end', entity.length, i, entity))

        # Sorting: Position -> Type (end before start) -> Length priority
        events.sort(key=lambda x: (x[0], 0 if x[1] == 'end' else 1, x[2]))

        result_parts = []

        # current_tags: tags currently open in the HTML string
        current_tags = []
        # logical_stack: tags that should be active based on event logic
        logical_stack = []

        last_pos = 0

        for pos, event_type, _, _, entity in events:
            # 1. Add text if we've moved forward
            if pos > last_pos:
                segment = self._utf16_slice(text, last_pos, pos - last_pos)
                if segment:
                    result_parts.append(self._escape_html_smart(segment))
                last_pos = pos

            # 2. Update logical stack
            if event_type == 'start':
                logical_stack.append(entity)
                # Sort stack: Longest entities (quotes) should be at the start (outside),
                # shortest (bold) at the end (inside).
                logical_stack.sort(key=lambda e: -e.length)
            else: # end
                if entity in logical_stack:
                    logical_stack.remove(entity)

            # 3. Synchronization (Reconciliation) of HTML tags with logical stack
            # Find common part (prefix) that doesn't need to be touched
            common_len = 0
            for i in range(min(len(current_tags), len(logical_stack))):
                if current_tags[i] == logical_stack[i]:
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
                tag_name, attrs, _ = self._entity_to_html(entity_to_open, "")

                attrs_str = ' '.join([f'{k}="{v}"' for k, v in attrs.items()])
                if attrs_str: attrs_str = ' ' + attrs_str

                result_parts.append(f"<{tag_name}{attrs_str}>")
                current_tags.append(entity_to_open)

        # 4. Write remaining text
        total_len = len(text.encode('utf-16-le')) // 2
        if last_pos < total_len:
            segment = self._utf16_slice(text, last_pos, total_len - last_pos)
            if segment:
                result_parts.append(self._escape_html_smart(segment))

        # 5. Close remaining tags (if any)
        while current_tags:
            entity_to_close = current_tags.pop()
            tag_name, _, _ = self._entity_to_html(entity_to_close, "")
            result_parts.append(f"</{tag_name}>")

        return "".join(result_parts)

    def convert_message(self, message) -> str:
        if hasattr(message, 'media') and message.media:
            text = getattr(message, 'message', '') or getattr(message, 'text', '') or ''

            if hasattr(message.media, 'caption'):
                text = message.media.caption or ''
            if hasattr(message.media, 'caption_entities'):
                entities = message.media.caption_entities or []
            elif hasattr(message, 'entities'):
                entities = message.entities or []
            else:
                entities = []

        else:
            text = getattr(message, 'message', '') or getattr(message, 'text', '') or ''
            entities = getattr(message, 'entities', []) or []

        if not text and not entities:
            return ""
        return self._process_entities(text, entities)

    def convert_event(self, event) -> str:
        if hasattr(event, 'message'):
            return self.convert_message(event.message)
        elif hasattr(event, 'text'):
            return self._escape_html_smart(event.text)
        return ""

def message_to_html(message, detailed: bool = False) -> str:
    converter = RawHTMLConverter(keep_newlines=True)
    html_content = converter.convert_message(message)

    if detailed:
        metadata = []
        if hasattr(message, 'id'): metadata.append(f"Message ID: {message.id}")
        if hasattr(message, 'sender_id'): metadata.append(f"Sender ID: {message.sender_id}")

        if metadata:
            metadata_html = "<div style='color: #666; font-size: 0.9em; border-left: 2px solid #ccc; padding-left: 10px; margin-bottom: 15px;'>"
            metadata_html += "<strong>Metadata:</strong><br/>" + "<br/>".join(metadata)
            metadata_html += "</div>"
            html_content = metadata_html + html_content

    return html_content

def event_to_html(event, detailed: bool = False) -> str:
    converter = RawHTMLConverter(keep_newlines=True)
    return converter.convert_event(event)

def extract_raw_html(message, escape: bool = False) -> str:
    converter = RawHTMLConverter(keep_newlines=True)
    html_content = converter.convert_message(message)
    if escape: return html.escape(html_content)
    return html_content

def debug_entities(message) -> List[Dict]:
    """Debug entities."""
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

    converter = RawHTMLConverter()
    entities_info = []
    for entity in entity_list:
        entities_info.append({
            'type': type(entity).__name__,
            'offset': entity.offset,
            'length': entity.length,
            'text': converter._utf16_slice(text, entity.offset, entity.length)
        })
    return entities_info


raw_html_converter = RawHTMLConverter(keep_newlines=True)

__all__ = ['RawHTMLConverter', 'message_to_html', 'event_to_html', 'extract_raw_html', 'debug_entities', 'raw_html_converter']

