# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin00
#
# Thin wrapper for backward compatibility
# All logic moved to decorators.py and base.py

from .base import (
    ModuleBase,
    _ModuleLoggerAdapter,
)
from .decorators import (
    bot_command,
    callback,
    command,
    error_handler,
    event,
    inline,
    inline_temp,
    loop,
    method,
    on_install,
    on_uninstall,
    owner_only,
    permissions,
    watcher,
)

# Alias for backward compatibility with docs
permission = permissions

__all__ = [
    "ModuleBase",
    "_ModuleLoggerAdapter",
    "bot_command",
    "callback",
    "command",
    "error_handler",
    "event",
    "inline",
    "inline_temp",
    "loop",
    "method",
    "on_install",
    "on_uninstall",
    "owner_only",
    "permission",
    "permissions",
    "watcher",
]
