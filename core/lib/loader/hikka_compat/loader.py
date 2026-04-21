# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

import re
import site

from .config import ConfigValue, LibraryConfig, ModuleConfig
from .decorators import (
    InfiniteLoop,
    Placeholder,
    callback_handler,
    command,
    debug_method,
    inline_handler,
    loop,
    on,
    raw_handler,
    tag,
    tds,
    watcher,
)
from .runtime import Library, Module
from .types import (
    CoreOverwriteError,
    CoreUnloadError,
    LoadError,
    SelfSuspend,
    SelfUnload,
    StopLoop,
    StringLoader,
)
from .validators import validators

VALID_PIP_PACKAGES = re.compile(
    r"# ?scope: ?pip ?((?:[A-Za-z0-9\-_>=<!\[\].]+(?:\s+|$))+)",
    re.MULTILINE,
)
VALID_APT_PACKAGES = re.compile(
    r"# ?scope: ?apt ?((?:[A-Za-z0-9\-_]+(?:\s+|$))+)",
    re.MULTILINE,
)
USER_INSTALL = not getattr(site, "ENABLE_USER_SITE", True)


__all__ = [
    "USER_INSTALL",
    "VALID_APT_PACKAGES",
    "VALID_PIP_PACKAGES",
    "ConfigValue",
    "CoreOverwriteError",
    "CoreUnloadError",
    "InfiniteLoop",
    "Library",
    "LibraryConfig",
    "LoadError",
    "Module",
    "ModuleConfig",
    "Placeholder",
    "SelfSuspend",
    "SelfUnload",
    "StopLoop",
    "StringLoader",
    "callback_handler",
    "command",
    "debug_method",
    "inline_handler",
    "loop",
    "on",
    "raw_handler",
    "tag",
    "tds",
    "validators",
    "watcher",
]
