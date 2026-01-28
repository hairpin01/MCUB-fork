# author: @Hairpin00
# version: 1.0.1
# description: utils package initialization

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

from . import platform

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


try:
    from .html_parser import parse_html, telegram_to_html
    __all__.extend(['parse_html', 'telegram_to_html'])
except ImportError:
    pass

try:
    from .emoji_parser import emoji_parser
    __all__.extend(['emoji_parser'])
except ImportError:
    pass

try:
    from .message_helpers import edit_with_html, reply_with_html, send_with_html, send_file_with_html
    __all__.extend(['edit_with_html', 'reply_with_html', 'send_with_html', 'send_file_with_html'])
except ImportError:
    pass

__version__ = '1.0.1'
__author__ = '@Hairpin00'
__description__ = 'MCUB Utils Package'

def get_utils_status():
    """Returns the availability status of all utilities"""
    status = {
        'platform': 'platform' in globals(),
        'html_parser': 'parse_html' in globals(),
        'emoji_parser': 'emoji_parser' in globals(),
        'message_helpers': 'edit_with_html' in globals(),
        'version': __version__
    }
    return status

__all__.append('get_utils_status')

# # Для обратной совместимости
# MCUBHTMLParser = TelegramHTMLParser
# escape_html = lambda x: x  # Заглушка
