# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

# author: @Hairpin00
# version: 1.0.1
# description: utils package initialization

from . import platform
from .helpers import (
    answer,
    answer_file,
    escape_html,
    escape_quotes,
    format_date,
    format_relative_time,
    format_time,
    get_admins,
    get_args,
    get_args_html,
    get_args_raw,
    get_chat_id,
    get_lang,
    get_prefix,
    get_sender_info,
    get_thread_id,
    make_button,
    make_buttons,
    pipe_edit,
    relocate_entities,
    resolve_peer,
)
from .platform import (
    PlatformDetector,
    get_platform,
    get_platform_info,
    get_platform_name,
    is_desktop,
    is_docker,
    is_mobile,
    is_termux,
    is_vds,
    is_virtualized,
    is_wsl,
)
from .restart import restart_kernel
from .custom_placeholders import (
    config_placeholders,
    format_placeholders,
    get_placeholders,
    list_placeholder_keys,
    placeholders,
    register_decorated_placeholders,
    register_placeholder,
    resolve_placeholders,
    unregister_scope,
)

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
    from .message_helpers import (
        edit_with_html,
        reply_with_html,
        send_file_with_html,
        send_with_html,
    )

    MESSAGE_HELPERS_AVAILABLE = True
except ImportError:
    MESSAGE_HELPERS_AVAILABLE = False

try:
    from .arg_parser import (
        ArgumentParser,
        ArgumentValidator,
        extract_command,
        parse_arguments,
        parse_kwargs,
        split_args,
    )

    ARG_PARSER_AVAILABLE = True
except ImportError:
    ARG_PARSER_AVAILABLE = False

__all__ = [
    "PlatformDetector",
    "get_platform",
    "get_platform_info",
    "get_platform_name",
    "is_desktop",
    "is_docker",
    "is_mobile",
    "is_termux",
    "is_vds",
    "is_virtualized",
    "is_wsl",
    "platform",
]

if HTML_PARSER_AVAILABLE:
    __all__.extend(["html_parser", "parse_html", "telegram_to_html"])

if EMOJI_PARSER_AVAILABLE:
    __all__.extend(["emoji_parser"])

if MESSAGE_HELPERS_AVAILABLE:
    __all__.extend(
        [
            "edit_with_html",
            "message_helpers",
            "reply_with_html",
            "send_file_with_html",
            "send_with_html",
        ]
    )

if ARG_PARSER_AVAILABLE:
    __all__.extend(
        [
            "ArgumentParser",
            "ArgumentValidator",
            "arg_parser",
            "extract_command",
            "parse_arguments",
            "parse_kwargs",
            "split_args",
        ]
    )

try:
    from .raw_html import (
        RawHTMLConverter,
        debug_entities,
        event_to_html,
        extract_raw_html,
        message_to_html,
        raw_html_converter,
        save_html_to_file,
    )

    RAW_HTML_AVAILABLE = True
except ImportError:
    RAW_HTML_AVAILABLE = False

if RAW_HTML_AVAILABLE:
    __all__.extend(
        [
            "RawHTMLConverter",
            "debug_entities",
            "event_to_html",
            "extract_raw_html",
            "message_to_html",
            "raw_html",
            "raw_html_converter",
            "save_html_to_file",
        ]
    )

__all__.extend(
    [
        "answer",
        "answer_file",
        "escape_html",
        "escape_quotes",
        "format_date",
        "format_relative_time",
        "format_time",
        "get_admins",
        "get_args",
        "get_args_html",
        "get_args_raw",
        "get_chat_id",
        "get_lang",
        "get_prefix",
        "get_sender_info",
        "get_thread_id",
        "make_button",
        "make_buttons",
        "pipe_edit",
        "relocate_entities",
        "resolve_peer",
        "placeholders",
        "register_placeholder",
        "register_decorated_placeholders",
        "unregister_scope",
        "list_placeholder_keys",
        "format_placeholders",
        "config_placeholders",
        "get_placeholders",
        "resolve_placeholders",
    ]
)

__all__.append("RAW_HTML_AVAILABLE")
__all__.append("get_utils_status")
__all__.extend(["restart_kernel"])

from .strings import Strings

__all__.append("Strings")
