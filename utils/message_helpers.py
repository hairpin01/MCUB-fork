# utils/message_helpers.py
# author: @Hairpin00
# version: 1.2.0
# description: Helpers for sending messages with HTML markup

import re
import html
from .html_parser import parse_html, _utf16_len

def clean_html_fallback(html_text: str) -> str:
    """
    Universal HTML cleanup in case of parsing errors.
    Removes formatting tags, leaving only text.

    Args:
        html_text (str): HTML text to clean

    Returns:
        str: Text without HTML tags
    """
    if not html_text:
        return ""

    # Important: replace emojis first
    # Custom emojis (new syntax)
    text = re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', html_text)

    # Custom emojis (old syntax via img)
    text = re.sub(r'<img[^>]*src="tg://emoji\?id=[^"]+"[^>]*alt="([^"]*)"[^>]*>', r'\1', text)
    text = re.sub(r'<img[^>]*src="tg://emoji\?id=[^"]+"[^>]*>', '', text)

    # Remove all formatting tags (opening and closing)
    # Order is important: closing tags first, then opening ones
    tags_patterns = [
        # Closing tags
        r'</(?:b|strong|i|em|u|s|del|code|pre|blockquote|a|tg-spoiler|spoiler)>',

        # Opening tags (without attributes or with attributes)
        r'<(?:b|strong|i|em|u|s|del|code|tg-spoiler|spoiler)(?:\s[^>]*)?>',

        # Opening tags with attributes
        r'<pre(?:\s[^>]*)?>',
        r'<blockquote(?:\s[^>]*)?>',
        r'<a\s[^>]*>',

        # Self-closing tags
        r'<br(?:\s[^>]*)?>',
    ]

    for pattern in tags_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # Decode HTML entities
    text = html.unescape(text)

    # Remove extra spaces left after tag removal
    text = re.sub(r'\s+', ' ', text).strip()

    return text

def truncate_text_with_entities(text: str, entities: list, max_length: int = 4096):
    """
    Truncates text and entities to fit within Telegram's limit.

    Args:
        text (str): Text to truncate
        entities (list): List of entities
        max_length (int): Maximum text length (default 4096 for Telegram)

    Returns:
        tuple: (truncated text, truncated entities)
    """
    # Check text length in UTF-16
    text_length = _utf16_len(text)

    if text_length <= max_length:
        return text, entities

    # Truncate text
    # Find position where we can safely truncate (by UTF-16 character boundary)
    truncated_text = ""
    current_length = 0

    for char in text:
        char_length = _utf16_len(char)
        if current_length + char_length > max_length:
            break
        truncated_text += char
        current_length += char_length

    # Adjust entities
    truncated_entities = []
    for entity in entities:
        # If entity fits completely within truncated text
        if entity.offset + entity.length <= current_length:
            truncated_entities.append(entity)
        # If entity starts inside but ends outside
        elif entity.offset < current_length:
            # Create a copy of entity with truncated length
            if hasattr(entity, '__dict__'):
                # For most Telethon entities
                entity_dict = entity.__dict__.copy()
                entity_dict['length'] = current_length - entity.offset
                new_entity = entity.__class__(**entity_dict)
                truncated_entities.append(new_entity)

    return truncated_text, truncated_entities

async def _send_html_generic(send_func, html_text: str, kernel, truncate: bool = True, **kwargs):
    """
    Universal function for sending HTML with error handling.

    Args:
        send_func: Send function (event.edit, event.reply, client.send_message)
        html_text (str): HTML text
        kernel: Kernel object for error handling
        truncate (bool): Whether to truncate text by Telegram's limit
        **kwargs: Additional arguments for send_func

    Returns:
        Result of send_func execution
    """
    try:
        text, entities = parse_html(html_text)

        # Truncate text and entities if needed
        if truncate:
            text, entities = truncate_text_with_entities(text, entities)

        return await send_func(text, formatting_entities=entities, **kwargs)
    except Exception as e:
        # Get function name
        source_name = getattr(send_func, '__name__', str(send_func))
        await kernel.handle_error(e, source=f"{source_name}_with_html")

        # Fallback: send cleaned text
        fallback_text = clean_html_fallback(html_text)

        # Truncate fallback text too
        if truncate:
            fallback_text = truncate_text_with_entities(fallback_text, [])[0]

        return await send_func(fallback_text, **kwargs)

async def edit_with_html(kernel, event, html_text: str, truncate: bool = True, **kwargs):
    """
    Edits a message with HTML markup.

    Args:
        kernel: Kernel object
        event: Telethon event
        html_text (str): HTML text to send
        truncate (bool): Whether to truncate text by Telegram's limit (default True)
        **kwargs: Additional arguments for event.edit

    Returns:
        Updated message
    """
    return await _send_html_generic(
        event.edit,
        html_text,
        kernel,
        truncate=truncate,
        **kwargs
    )

async def reply_with_html(kernel, event, html_text: str, truncate: bool = True, **kwargs):
    """
    Replies to a message with HTML markup.

    Args:
        kernel: Kernel object
        event: Telethon event
        html_text (str): HTML text to send
        truncate (bool): Whether to truncate text by Telegram's limit (default True)
        **kwargs: Additional arguments for event.reply

    Returns:
        Sent message
    """
    return await _send_html_generic(
        event.reply,
        html_text,
        kernel,
        truncate=truncate,
        **kwargs
    )

async def send_with_html(kernel, client, chat_id, html_text: str, truncate: bool = True, **kwargs):
    """
    Sends a message with HTML markup.

    Args:
        kernel: Kernel object
        client: Telethon client
        chat_id: Chat ID
        html_text (str): HTML text to send
        truncate (bool): Whether to truncate text by Telegram's limit (default True)
        **kwargs: Additional arguments for client.send_message

    Returns:
        Sent message
    """
    async def send_message(text, **inner_kwargs):
        return await client.send_message(chat_id, text, **inner_kwargs)

    return await _send_html_generic(
        send_message,
        html_text,
        kernel,
        truncate=truncate,
        **kwargs
    )

async def send_file_with_html(kernel, client, chat_id, html_text: str, file, truncate: bool = True, **kwargs):
    """
    Sends a file with HTML caption.

    Args:
        kernel: Kernel object
        client: Telethon client
        chat_id: Chat ID
        html_text (str): HTML caption
        file: File to send
        truncate (bool): Whether to truncate text by Telegram's limit (default True)
        **kwargs: Additional arguments

    Returns:
        Sent message
    """
    async def send_file(text, **inner_kwargs):
        return await client.send_file(
            chat_id,
            file,
            caption=text,
            **inner_kwargs
        )

    # For file captions the limit is 1024 characters
    return await _send_html_generic(
        send_file,
        html_text,
        kernel,
        truncate=truncate,
        **kwargs
    )
