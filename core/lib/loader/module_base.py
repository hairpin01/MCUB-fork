# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin00
#
# Thin wrapper for backward compatibility
# All logic moved to decorators.py and base.py

from .decorators import (  # noqa: F401
    command,
    inline,
    callback,
    watcher,
    loop,
    event,
    inline_temp,
    method,
    on_install,
    on_uninstall,
    bot_command,
    owner_only,
    permissions,
    error_handler,
)

from .base import (  # noqa: F401
    ModuleBase,
    _ModuleLoggerAdapter,
)

__all__ = [
    "command",
    "inline",
    "callback",
    "watcher",
    "loop",
    "event",
    "inline_temp",
    "method",
    "on_install",
    "on_uninstall",
    "bot_command",
    "owner_only",
    "permissions",
    "error_handler",
    "ModuleBase",
    "_ModuleLoggerAdapter",
]
