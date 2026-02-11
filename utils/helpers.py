# author: @Hairpin00
# version: 1.0.0
# description: helper utilities for modules (arguments, replies, files, formatting)

import shlex
import html as html_escape
from typing import List, Optional, Union, Any

from telethon import events
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

    Automatically detects:
        - Inline calls (has `.edit()` method) – uses `edit()`.
        - Regular chat messages – uses `reply()` or kernel's HTML/emoji helpers.
        - File sending – delegates to `answer_file()`.

    Args:
        event: The original event (Telegram message or inline object).
        text: Text to send.
        reply_markup: Inline keyboard (for non‑inline messages).
        file: File to attach (path, URL, bytes, InputDocument).
        as_html: Force interpretation of `text` as HTML.
        as_emoji: Force custom emoji parsing (via `emoji_parser`).
        caption: Caption for the file (if `file` is provided).
        **kwargs: Additional arguments passed to the underlying send/edit method.

    Returns:
        The sent/edited message or inline object.
    """
    kernel = _get_kernel(event)
    is_inline = hasattr(event, 'edit') and callable(event.edit)

    # If a file is provided, delegate to answer_file
    if file:
        return await answer_file(event, file, caption or text, **kwargs)

    # Priority: explicit as_html / as_emoji flags, then auto‑detection

    # 1. HTML mode
    if as_html or (kernel and kernel.HTML_PARSER_AVAILABLE and _looks_like_html(text)):
        if is_inline:
            return await event.edit(text, parse_mode='html', reply_markup=reply_markup, **kwargs)
        else:
            if kernel and hasattr(kernel, 'reply_with_html'):
                return await kernel.reply_with_html(event, text, **kwargs)
            else:
                return await event.reply(text, **kwargs)

    # 2. Custom emoji mode
    if as_emoji or (kernel and kernel.emoji_parser and emoji_parser.is_emoji_tag(text)):
        if is_inline:
            parsed_text, entities = emoji_parser.parse_to_entities(text)
            return await event.edit(parsed_text, entities=entities, reply_markup=reply_markup, **kwargs)
        else:
            if kernel and hasattr(kernel, 'send_with_emoji'):
                return await kernel.send_with_emoji(event.chat_id, text, reply_to=event.id, **kwargs)
            else:
                return await event.reply(text, **kwargs)

    # 3. Plain text
    if is_inline:
        return await event.edit(text, reply_markup=reply_markup, **kwargs)
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

    Supports local paths, URLs, bytes, and Telethon InputDocument.
    Caption can be formatted with HTML or custom emojis.

    Args:
        event: Original event.
        file: File to send.
        caption: Optional caption.
        as_html: Treat caption as HTML.
        as_emoji: Treat caption as custom‑emoji text.
        **kwargs: Additional arguments for `send_file`.

    Returns:
        The sent message.
    """
    kernel = _get_kernel(event)
    is_inline = hasattr(event, 'edit') and callable(event.edit)

    if is_inline:
        # For inline calls, we can't send a file directly; fallback to a text notice.
        return await answer(event, caption or '📎 File attached', file=file, **kwargs)

    # Regular chat – send as a document
    chat_id = event.chat_id
    thread_id = await get_thread_id(event) if hasattr(event, 'client') else None

    # Process caption formatting
    if caption:
        if as_html or (kernel and kernel.HTML_PARSER_AVAILABLE):
            return await kernel.send_file_with_html(
                chat_id, caption, file,
                reply_to=thread_id or event.id,
                **kwargs
            )
        elif as_emoji or (kernel and kernel.emoji_parser):
            return await kernel.send_with_emoji(
                chat_id, caption,
                file=file,
                reply_to=thread_id or event.id,
                **kwargs
            )

    # Plain caption
    return await event.client.send_file(
        chat_id, file,
        caption=caption,
        reply_to=thread_id or event.id,
        **kwargs
    )


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
