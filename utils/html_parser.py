"""
Telegram HTML Parser - Bidirectional HTML ↔ Telegram Entities Converter
Supports parsing HTML to Telegram message entities and converting entities back to HTML.
Fixed: Correctly handles nested entities and multi-byte characters.
"""

import html
from collections import deque
from html.parser import HTMLParser
from typing import Optional, Tuple, List, Dict, Any, Union

from telethon.tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityCode,
    MessageEntityPre, MessageEntityTextUrl, MessageEntityUnderline,
    MessageEntityStrike, MessageEntityBlockquote, MessageEntityCustomEmoji,
    MessageEntitySpoiler, MessageEntityEmail, MessageEntityUrl,
    MessageEntityMention, MessageEntityMentionName, MessageEntityHashtag,
    MessageEntityCashtag, MessageEntityBotCommand, MessageEntityBankCard,
    MessageEntityPhone
)
def _utf16_len(text: str) -> int:
    return len(text.encode('utf-16-le')) // 2

class TelegramHTMLParser(HTMLParser):
    """
    Parses HTML markup and converts it to Telegram message entities.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = ''
        self.entities = []
        self._open_entities = {}
        self._tag_stack = deque()
        self._utf16_offset = 0

    def _utf16_len(self, text: str) -> int:
        return len(text.encode('utf-16-le')) // 2

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        attrs_dict = dict(attrs)
        self._tag_stack.appendleft(tag)

        # Mappings
        if tag in ('b', 'strong'):
            self._open_entities[tag] = MessageEntityBold(self._utf16_offset, 0)
        elif tag in ('i', 'em'):
            self._open_entities[tag] = MessageEntityItalic(self._utf16_offset, 0)
        elif tag == 'u':
            self._open_entities[tag] = MessageEntityUnderline(self._utf16_offset, 0)
        elif tag in ('s', 'del', 'strike'):
            self._open_entities[tag] = MessageEntityStrike(self._utf16_offset, 0)
        elif tag == 'code':
            self._open_entities[tag] = MessageEntityCode(self._utf16_offset, 0)
        elif tag == 'pre':
            lang = attrs_dict.get('language', '')
            self._open_entities[tag] = MessageEntityPre(self._utf16_offset, 0, language=lang)
        elif tag in ('tg-spoiler', 'spoiler'):
            self._open_entities[tag] = MessageEntitySpoiler(self._utf16_offset, 0)
        elif tag == 'blockquote':
            collapsed = 'expandable' in attrs_dict
            self._open_entities[tag] = MessageEntityBlockquote(self._utf16_offset, 0, collapsed=collapsed)
        elif tag == 'a':
            href = attrs_dict.get('href', '')
            if href.startswith('mailto:'):
                self._open_entities[tag] = MessageEntityEmail(self._utf16_offset, 0, url=href[7:])
            elif href:
                self._open_entities[tag] = MessageEntityTextUrl(self._utf16_offset, 0, url=href)
        elif tag == 'tg-emoji':
            emoji_id = attrs_dict.get('emoji-id')
            if emoji_id and emoji_id.isdigit():
                self._open_entities[tag] = MessageEntityCustomEmoji(self._utf16_offset, 0, document_id=int(emoji_id))

    def handle_endtag(self, tag: str) -> None:
        if tag in self._open_entities:
            entity = self._open_entities.pop(tag)
            entity.length = self._utf16_offset - entity.offset
            if entity.length > 0:
                self.entities.append(entity)

        if self._tag_stack and self._tag_stack[0] == tag:
            self._tag_stack.popleft()

    def handle_data(self, data: str) -> None:
        if not data: return
        self.text += data
        self._utf16_offset += self._utf16_len(data)

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        if tag == 'br':
            self.handle_data('\n')

    def close(self) -> None:
        super().close()
        # Sort entities by offset
        self.entities.sort(key=lambda e: (e.offset, -e.length))


class HTMLDecorator:
    """
    Convert Telegram message entities back to HTML markup.
    Now supports nested entities correctly.
    """

    def unparse(self, text: str, entities: List) -> str:
        if not entities:
            return html.escape(text, quote=False)

        utf16_bytes = text.encode('utf-16-le')
        total_len = len(utf16_bytes) // 2

        # Create events for the sweep-line algorithm
        events = []
        for i, entity in enumerate(entities):
            # Start: prioritize outer (longer) entities
            events.append((entity.offset, 'start', -entity.length, i, entity))
            # End: prioritize inner (shorter) entities
            events.append((entity.offset + entity.length, 'end', entity.length, i, entity))

        # Sort events: Position -> Type (end=0 before start=1) -> Priority
        events.sort(key=lambda x: (x[0], 0 if x[1] == 'end' else 1, x[2]))

        result_parts = []
        current_tags = []
        logical_stack = []
        last_pos = 0

        def get_chunk(start, length):
            s = start * 2
            e = (start + length) * 2
            return utf16_bytes[s:e].decode('utf-16-le')

        for pos, event_type, _, _, entity in events:
            if pos > last_pos:
                chunk = get_chunk(last_pos, pos - last_pos)
                result_parts.append(html.escape(chunk, quote=False))
                last_pos = pos

            if event_type == 'start':
                logical_stack.append(entity)
                logical_stack.sort(key=lambda e: -e.length)
            else:
                if entity in logical_stack:
                    logical_stack.remove(entity)

            # Reconcile stack
            common = 0
            for c, l in zip(current_tags, logical_stack):
                if c is l: common += 1
                else: break

            # Close mismatch
            while len(current_tags) > common:
                ent = current_tags.pop()
                result_parts.append(f"</{self._get_tag(ent)}>")

            # Open new
            while len(current_tags) < len(logical_stack):
                ent = logical_stack[len(current_tags)]
                tag, attrs = self._get_tag_attrs(ent, "")
                # Note: We don't have full entity text here easily, so specialized attrs
                # like mailto might need the URL from the entity object itself.
                attr_str = "".join([f' {k}="{v}"' if v is not None else f' {k}' for k, v in attrs.items()])
                result_parts.append(f"<{tag}{attr_str}>")
                current_tags.append(ent)

        if last_pos < total_len:
            result_parts.append(html.escape(get_chunk(last_pos, total_len - last_pos), quote=False))

        while current_tags:
            result_parts.append(f"</{self._get_tag(current_tags.pop())}>")

        return "".join(result_parts)

    def _get_tag(self, entity):
        t, _ = self._get_tag_attrs(entity, "")
        return t

    def _get_tag_attrs(self, entity, text_content):
        attrs = {}
        tag = "span"

        if isinstance(entity, MessageEntityBold): tag = "b"
        elif isinstance(entity, MessageEntityItalic): tag = "i"
        elif isinstance(entity, MessageEntityUnderline): tag = "u"
        elif isinstance(entity, MessageEntityStrike): tag = "s"
        elif isinstance(entity, MessageEntityCode): tag = "code"
        elif isinstance(entity, MessageEntityPre):
            tag = "pre"
            if getattr(entity, 'language', None): attrs['language'] = entity.language
        elif isinstance(entity, MessageEntitySpoiler): tag = "tg-spoiler"
        elif isinstance(entity, MessageEntityBlockquote):
            tag = "blockquote"
            if getattr(entity, 'collapsed', False): attrs['expandable'] = None
        elif isinstance(entity, MessageEntityTextUrl):
            tag = "a"
            attrs['href'] = getattr(entity, 'url', '')
        elif isinstance(entity, MessageEntityEmail):
            tag = "a"
            # If we don't have the text content easily, rely on entity.url if available
            # otherwise this might be slightly inaccurate in reconstruction without context
            attrs['href'] = f"mailto:{getattr(entity, 'url', '')}"
        elif isinstance(entity, MessageEntityCustomEmoji):
            tag = "tg-emoji"
            attrs['emoji-id'] = str(getattr(entity, 'document_id', ''))

        return tag, attrs


def parse_html(html_text: str) -> Tuple[str, List]:
    parser = TelegramHTMLParser()
    parser.feed(html_text)
    parser.close()
    return parser.text, parser.entities

def telegram_to_html(text: str, entities: List) -> str:
    decorator = HTMLDecorator()
    return decorator.unparse(text, entities)

def format_message(text: str, entities: Optional[List] = None, as_html: bool = False) -> Union[str, Tuple[str, List]]:
    if as_html and entities:
        return telegram_to_html(text, entities)
    elif not as_html and ('<' in text and '>' in text):
        return parse_html(text)
    if entities:
        return text, entities
    return text
__all__ = ['TelegramHTMLParser', 'parse_html', 'telegram_to_html', 'format_message', 'HTMLDecorator']
