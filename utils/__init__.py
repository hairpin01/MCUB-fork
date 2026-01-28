
# author: @Hairpin00
# version: 1.0.0
# description: utils package initialization

try:
    from .platform import (
        PlatformDetector,
        get_platform,
        get_platform_info,
        get_platform_name,
        is_termux,
        is_wsl,
        is_vds,
        is_docker,
        is_mobile,
        is_desktop,
        is_virtualized
    )
    PLATFORM_AVAILABLE = True
except ImportError:
    PLATFORM_AVAILABLE = False

try:
    from .html_parser import parse_html, telegram_to_html
    HTML_PARSER_AVAILABLE = True
except ImportError:
    HTML_PARSER_AVAILABLE = False

try:
    from .emoji_parser import emoji_parser
    EMOJI_PARSER_AVAILABLE = True
except ImportError:
    EMOJI_PARSER_AVAILABLE = False

try:
    from .message_helpers import edit_with_html, reply_with_html, send_with_html, send_file_with_html
    MESSAGE_HELPERS_AVAILABLE = True
except ImportError:
    MESSAGE_HELPERS_AVAILABLE = False

# Export platform utilities
if PLATFORM_AVAILABLE:
    __all__ = [
        'PlatformDetector',
        'get_platform',
        'get_platform_info',
        'get_platform_name',
        'is_termux',
        'is_wsl',
        'is_vds',
        'is_docker',
        'is_mobile',
        'is_desktop',
        'is_virtualized',
        'platform'
    ]
else:
    __all__ = []

# Export other utilities if available
if HTML_PARSER_AVAILABLE:
    __all__.extend(['parse_html', 'telegram_to_html', 'html_parser'])

if EMOJI_PARSER_AVAILABLE:
    __all__.extend(['emoji_parser'])

if MESSAGE_HELPERS_AVAILABLE:
    __all__.extend(['edit_with_html', 'reply_with_html', 'send_with_html', 'send_file_with_html', 'message_helpers'])


# Optional: create a main utility function for checking all utils availability
def get_utils_status():
    """Returns the availability status of all utilities"""
    return {
        'platform': PLATFORM_AVAILABLE,
        'html_parser': HTML_PARSER_AVAILABLE,
        'emoji_parser': EMOJI_PARSER_AVAILABLE,
        'message_helpers': MESSAGE_HELPERS_AVAILABLE,
        'version': __version__
    }

# Add the status function to exports if needed
__all__.append('get_utils_status')

# # Для обратной совместимости
# MCUBHTMLParser = TelegramHTMLParser
# escape_html = lambda x: x  # Заглушка
