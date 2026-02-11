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

from .helpers import (
    get_args,
    get_args_raw,
    get_args_html,
    answer,
    answer_file,
    escape_html,
    escape_quotes,
    get_chat_id,
    get_sender_info,
    get_thread_id,
    relocate_entities,
)

from . import platform
from .restart import restart_kernel
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

try:
    from .raw_html import (
        RawHTMLConverter,
        message_to_html,
        event_to_html,
        extract_raw_html,
        debug_entities,
        save_html_to_file,
        raw_html_converter
    )
    RAW_HTML_AVAILABLE = True
except ImportError as e:
    RAW_HTML_AVAILABLE = False

if RAW_HTML_AVAILABLE:
    __all__.extend([
        'RawHTMLConverter',
        'message_to_html',
        'event_to_html',
        'extract_raw_html',
        'debug_entities',
        'save_html_to_file',
        'raw_html_converter',
        'raw_html'
    ])

__all__.extend([
    'get_args',
    'get_args_raw',
    'get_args_html',
    'answer',
    'answer_file',
    'escape_html',
    'escape_quotes',
    'get_chat_id',
    'get_sender_info',
    'get_thread_id',
    'relocate_entities',
])

__all__.append('RAW_HTML_AVAILABLE')
__all__.append('get_utils_status')
__all__.extend(['restart_kernel'])
