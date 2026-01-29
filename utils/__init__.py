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

try:
    from .arg_parser import (
        ArgumentParser,
        parse_arguments,
        extract_command,
        split_args,
        parse_kwargs,
        ArgumentValidator
    )
    ARG_PARSER_AVAILABLE = True
except ImportError:
    ARG_PARSER_AVAILABLE = False

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

if HTML_PARSER_AVAILABLE:
    __all__.extend(['parse_html', 'telegram_to_html', 'html_parser'])

if EMOJI_PARSER_AVAILABLE:
    __all__.extend(['emoji_parser'])

if MESSAGE_HELPERS_AVAILABLE:
    __all__.extend(['edit_with_html', 'reply_with_html', 'send_with_html', 'send_file_with_html', 'message_helpers'])

if ARG_PARSER_AVAILABLE:
    __all__.extend([
        'ArgumentParser',
        'parse_arguments',
        'extract_command',
        'split_args',
        'parse_kwargs',
        'ArgumentValidator',
        'arg_parser'
    ])


__all__.append('get_utils_status')
