# author: @Hairpin00
# version: 1.0.2
# description: helper utilities for modules (arguments, replies, files, formatting)

import shlex
import html as html_escape
import datetime
import time as time_module
from typing import List, Optional, Union, Any, Dict

from telethon import events, Button
from telethon.tl.custom import Message
from telethon.tl.types import TypeMessageEntity

# Local imports from the same utils package
from .html_parser import telegram_to_html
from .emoji_parser import emoji_parser


def get_args(event: Union[Message, events.NewMessage.Event]) -> List[str]:
    """
    Extract command arguments split by spaces, respecting quotes.

    Args:
        event: The message event or Message object.

    Returns:
        List of arguments. Empty list if no arguments or parsing fails.

    Example:
        >>> args = get_args(event)
        >>> if args:
        ...     first_arg = args[0]
    """
    text = getattr(event, 'text', None) or getattr(event, 'raw_text', '')
    if not text:
        return []

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return []

    try:
        return shlex.split(parts[1])
    except ValueError:
        # Unclosed quotes – treat the remainder as a single argument
        return [parts[1]]


def get_args_raw(event: Union[Message, events.NewMessage.Event]) -> str:
    """
    Return the raw argument string (everything after the command).

    Args:
        event: The message event or Message object.

    Returns:
        String of arguments. Empty string if none.
    """
    text = getattr(event, 'text', None) or getattr(event, 'raw_text', '')
    if not text:
        return ''

    parts = text.split(maxsplit=1)
    return parts[1] if len(parts) > 1 else ''


def get_args_html(event: Union[Message, events.NewMessage.Event]) -> str:
    """
    Return the command arguments with preserved HTML formatting (if any).

    Useful for commands that need to accept formatted input.

    Args:
        event: The message event or Message object.

    Returns:
        Arguments as an HTML string, or empty string if none.
    """
    if not hasattr(event, 'message') or not event.message.entities:
        return get_args_raw(event)

    raw_text = event.raw_text
    prefix = _get_prefix(event)

    try:
        # Find where the command ends (first space after prefix)
        cmd_start = raw_text.index(prefix)
        cmd_end = raw_text.index(' ', cmd_start + 1) + 1
    except (ValueError, IndexError):
        return ''

    args_text = raw_text[cmd_end:]
    entities = event.message.entities

    # Shift entities to match the extracted substring
    shifted_entities = relocate_entities(entities, -cmd_end, args_text)

    return telegram_to_html(args_text, shifted_entities)


async def answer(
    event: Union[Message, events.NewMessage.Event, 'InlineCall', 'InlineMessage'],
    text: str,
    *,
    reply_markup: Optional[Any] = None,
    file: Optional[Any] = None,
    as_html: bool = False,
    as_emoji: bool = False,
    caption: Optional[str] = None,
    **kwargs
) -> Any:
    """
    Universal method to reply to a message, edit an inline message, or send a file.
    """
    kernel = _get_kernel(event)
    is_inline = hasattr(event, 'edit') and callable(event.edit)

    if file:
        return await answer_file(event, file, caption or text, **kwargs)

    # Prepare the `buttons` argument for both edit and reply
    if reply_markup is not None:
        kwargs['buttons'] = reply_markup

    if as_html or (kernel and kernel.HTML_PARSER_AVAILABLE and _looks_like_html(text)):
        if is_inline:
            return await event.edit(text, parse_mode='html', **kwargs)
        else:
            if kernel and hasattr(kernel, 'reply_with_html'):
                return await kernel.reply_with_html(event, text, **kwargs)
            else:
                return await event.reply(text, **kwargs)

    if as_emoji or (kernel and kernel.emoji_parser and emoji_parser.is_emoji_tag(text)):
        if is_inline:
            parsed_text, entities = emoji_parser.parse_to_entities(text)
            return await event.edit(parsed_text, entities=entities, **kwargs)
        else:
            if kernel and hasattr(kernel, 'send_with_emoji'):
                return await kernel.send_with_emoji(event.chat_id, text, reply_to=event.id, **kwargs)
            else:
                return await event.reply(text, **kwargs)
    if is_inline:
        return await event.edit(text, **kwargs)
    else:
        return await event.reply(text, **kwargs)

async def answer_file(
    event: Union[Message, events.NewMessage.Event, 'InlineCall', 'InlineMessage'],
    file: Any,
    caption: Optional[str] = None,
    *,
    as_html: bool = False,
    as_emoji: bool = False,
    **kwargs
) -> Any:
    """
    Send a file in reply to a message.
    """
    kernel = _get_kernel(event)
    is_inline = hasattr(event, 'edit') and callable(event.edit)

    if is_inline:
        # Inline context: cannot send a real file → send a plain text notice without the file
        return await answer(event, caption or None, file=None, **kwargs)

    # Regular chat – send as a document
    chat_id = event.chat_id
    thread_id = await get_thread_id(event) if hasattr(event, 'client') else None
    reply_to = thread_id or event.id

    # Process caption formatting
    if caption:
        if as_html or (kernel and kernel.HTML_PARSER_AVAILABLE):
            return await kernel.send_file_with_html(chat_id, caption, file, reply_to=reply_to, **kwargs)
        elif as_emoji or (kernel and kernel.emoji_parser):
            return await kernel.send_with_emoji(chat_id, caption, file=file, reply_to=reply_to, **kwargs)

    # Plain caption
    return await event.client.send_file(chat_id, file, caption=caption, reply_to=reply_to, **kwargs)

def escape_html(text: str) -> str:
    """
    Escape HTML special characters: &, <, >.
    Use this for untrusted user input.
    """
    return html_escape.escape(text)


def escape_quotes(text: str) -> str:
    """
    Escape double quotes for use inside HTML attributes.
    """
    return escape_html(text).replace('"', '&quot;')


def get_chat_id(event: Union[Message, events.NewMessage.Event]) -> int:
    """
    Return the chat ID (without -100 prefix for channels).
    """
    if hasattr(event, 'chat_id'):
        return event.chat_id
    if hasattr(event, 'message') and event.message:
        peer = event.message.peer_id
        if hasattr(peer, 'channel_id'):
            return peer.channel_id
        if hasattr(peer, 'chat_id'):
            return peer.chat_id
        if hasattr(peer, 'user_id'):
            return peer.user_id
    return 0


async def get_sender_info(event: Union[Message, events.NewMessage.Event]) -> str:
    """
    Return a formatted string with the sender's name, username and ID.

    Example: "John Doe (@johndoe) [<code>123456</code>]"
    """
    try:
        sender = await event.get_sender()
        first = sender.first_name or ''
        last = sender.last_name or ''
        name = f"{first} {last}".strip()
        username = f"@{sender.username}" if sender.username else 'no username'
        return f"{name} ({username}) [<code>{sender.id}</code>]"
    except Exception:
        sender_id = getattr(event, 'sender_id', 'unknown')
        return f"ID: {sender_id}"


async def get_thread_id(event: Union[Message, events.NewMessage.Event]) -> Optional[int]:
    """
    Return the thread (topic) ID if the message is in a forum.
    """
    if hasattr(event, 'reply_to') and event.reply_to:
        return getattr(event.reply_to, 'reply_to_top_id', None)
    if hasattr(event, 'message') and event.message.reply_to:
        return getattr(event.message.reply_to, 'reply_to_top_id', None)
    return None


def relocate_entities(
    entities: List[TypeMessageEntity],
    offset: int,
    text: Optional[str] = None
) -> List[TypeMessageEntity]:
    """
    Shift all message entities by `offset` and clamp them to the length of `text`.

    Used when extracting a substring of a formatted message.

    Args:
        entities: List of Telethon MessageEntity objects.
        offset: Number of characters to move the entities (can be negative).
        text: The substring the entities will be applied to (for length clamping).

    Returns:
        A new list of adjusted entities (invalid ones are removed).
    """
    if not entities:
        return []

    result = []
    length = len(text) if text is not None else 0

    for ent in entities:
        # Copy the entity to avoid modifying the original
        ent = ent.copy()
        ent.offset += offset

        if ent.offset < 0:
            ent.length += ent.offset
            ent.offset = 0

        if text is not None and ent.offset + ent.length > length:
            ent.length = length - ent.offset

        if ent.length > 0:
            result.append(ent)

    return result


def _get_prefix(event) -> str:
    """Extract the command prefix from the client (if available)."""
    if hasattr(event, 'client') and hasattr(event.client, 'loader'):
        prefix = event.client.loader.get_prefix()
        if prefix:
            return prefix
    return '.'


def _get_kernel(event):
    """Retrieve the kernel instance from the client, if attached."""
    if hasattr(event, 'client') and hasattr(event.client, 'kernel'):
        return event.client.kernel
    if hasattr(event, '_kernel'):
        return event._kernel
    return None


def _looks_like_html(text: str) -> bool:
    """Heuristic: does the string look like it contains HTML tags?"""
    return '<' in text and '>' in text and any(
        tag in text for tag in ('<b>', '<i>', '<a', '<code', '<pre')
    )


def format_time(seconds: Union[int, float], detailed: bool = False) -> str:
    """
    Format seconds into a human-readable time string.

    Args:
        seconds: Number of seconds.
        detailed: If True, show weeks and days separately.

    Returns:
        Formatted string like "1h 30m" or "1 week 2 days 3 hours"
    """
    if detailed:
        weeks, seconds = divmod(int(seconds), 604800)
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        
        parts = []
        if weeks: parts.append(f"{weeks}w")
        if days: parts.append(f"{days}d")
        if hours: parts.append(f"{hours}h")
        if minutes: parts.append(f"{minutes}m")
        if seconds or not parts: parts.append(f"{seconds}s")
        return " ".join(parts)
    
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s" if secs else f"{minutes}m"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"


def format_date(timestamp: Union[int, float, datetime.datetime], fmt: str = "%Y-%m-%d %H:%M") -> str:
    """
    Format a timestamp or datetime object to a string.

    Args:
        timestamp: Unix timestamp (int/float) or datetime object.
        fmt: strftime format string.

    Returns:
        Formatted date string.
    """
    if isinstance(timestamp, datetime.datetime):
        dt = timestamp
    else:
        dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime(fmt)


def format_relative_time(timestamp: Union[int, float]) -> str:
    """
    Format a timestamp as relative time (e.g., "5 minutes ago").

    Args:
        timestamp: Unix timestamp.

    Returns:
        Relative time string.
    """
    now = time_module.time()
    diff = now - timestamp

    if diff < 60:
        return "just now"
    elif diff < 3600:
        minutes = int(diff // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif diff < 86400:
        hours = int(diff // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff < 604800:
        days = int(diff // 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif diff < 2592000:
        weeks = int(diff // 604800)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    else:
        return format_date(timestamp)


async def get_admins(event_or_client, chat_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get list of admins in a chat.

    Args:
        event_or_client: Event object or client instance.
        chat_id: Chat ID (uses event.chat_id if not provided).

    Returns:
        List of dicts with admin info (id, name, is_creator, etc.)
    """
    client = getattr(event_or_client, 'client', event_or_client)
    if chat_id is None:
        chat_id = getattr(event_or_client, 'chat_id', None)
    
    if not chat_id:
        return []

    try:
        participants = await client.get_participants(chat_id, filter=lambda x: x.admin_rights is not None or x.creator)
        return [
            {
                "id": p.id,
                "name": f"{p.first_name or ''} {p.last_name or ''}".strip(),
                "username": p.username,
                "is_creator": getattr(p, 'creator', False),
                "is_admin": p.admin_rights is not None,
            }
            for p in participants
        ]
    except Exception:
        return []


async def resolve_peer(client, identifier: Union[str, int]) -> Optional[int]:
    """
    Resolve a username, phone, or peer ID to a user ID.

    Args:
        client: Telethon client instance.
        identifier: Username (with or without @), phone, or numeric ID.

    Returns:
        User ID (int) or None if not found.
    """
    try:
        if isinstance(identifier, int):
            return identifier
        
        identifier = identifier.strip()
        
        if identifier.isdigit():
            return int(identifier)
        
        if identifier.startswith('@'):
            identifier = identifier[1:]
        
        entity = await client.get_entity(identifier)
        return entity.id
    except Exception:
        return None


def make_button(text: str, data: Optional[str] = None, url: Optional[str] = None, 
                switch: Optional[str] = None, same_peer: bool = False) -> Button:
    """
    Create a button with less boilerplate.

    Args:
        text: Button label.
        data: Callback data (for inline buttons).
        url: URL for URL buttons.
        switch: Inline query to switch to.
        same_peer: Use same peer for inline query.

    Returns:
        Telethon Button object.
    """
    if data:
        return Button.inline(text, data.encode() if isinstance(data, str) else data)
    elif url:
        return Button.url(text, url)
    elif switch:
        return Button.switch_inline(text, query=switch, same_peer=same_peer)
    else:
        return Button.text(text)


def make_buttons(buttons: Union[List[Dict[str, Any]], List[List[Dict[str, Any]]]], cols: Optional[int] = None) -> List[List[Button]]:
    """
    Create buttons from a list of dicts.

    Supports two formats:
    1. Flat list with cols (auto-split into rows):
       [{"text": "A", "data": "a"}, {"text": "B", "data": "b"}]
    2. Pre-grouped rows:
       [[{"text": "A", "data": "a"}], [{"text": "B", "data": "b"}]]

    Args:
        buttons: List of button dicts OR list of rows.
                 Each button: {"text": "Label", "data": "..."} or
                             {"text": "Label", "url": "..."} or
                             {"text": "Label", "switch": "query"}
        cols: Buttons per row (only for flat list, default 2).

    Returns:
        List of lists of Button objects.

    Example:
        >>> # Flat list (auto rows)
        >>> make_buttons([{"text": "A", "data": "a"}, {"text": "B", "data": "b"}])
        [[Button, Button]]

        >>> # Pre-grouped
        >>> make_buttons([[{"text": "A", "data": "a"}], [{"text": "B", "data": "b"}]])
        [[Button], [Button]]
    """
    if not buttons:
        return []
    
    first = buttons[0]
    if isinstance(first, list):
        result = []
        for row in buttons:
            button_row = []
            for btn in row:
                button_row.append(make_button(
                    text=btn.get("text", ""),
                    data=btn.get("data"),
                    url=btn.get("url"),
                    switch=btn.get("switch"),
                    same_peer=btn.get("same_peer", False)
                ))
            result.append(button_row)
        return result
    
    if cols is None:
        cols = 2
    
    result = []
    for i in range(0, len(buttons), cols):
        row = []
        for btn in buttons[i:i+cols]:
            row.append(make_button(
                text=btn.get("text", ""),
                data=btn.get("data"),
                url=btn.get("url"),
                switch=btn.get("switch"),
                same_peer=btn.get("same_peer", False)
            ))
        result.append(row)
    return result
