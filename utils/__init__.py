# utils/__init__.py

from .html_parser import (
    TelegramHTMLParser,
    parse_html,
    html_to_telegram,
    telegram_to_html,
    format_message,
    _utf16_len,
    HTMLDecorator
)

from .message_helpers import (
    clean_html_fallback,
    truncate_text_with_entities,
    edit_with_html,
    reply_with_html,
    send_with_html,
    send_file_with_html
)

# Для обратной совместимости
MCUBHTMLParser = TelegramHTMLParser
escape_html = lambda x: x  # Заглушка
