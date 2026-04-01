from .validators import validators
from .config import ConfigValue, ModuleConfig, LibraryConfig
from .runtime import Module, Library
from .decorators import (
    tds,
    tag,
    command,
    inline_handler,
    callback_handler,
    watcher,
    on,
    loop,
    raw_handler,
    debug_method,
    InfiniteLoop,
    Placeholder,
)
from .types import (
    StringLoader,
    LoadError,
    CoreOverwriteError,
    CoreUnloadError,
    SelfUnload,
    SelfSuspend,
    StopLoop,
)
import re
import site

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
    "Module",
    "Library",
    "ModuleConfig",
    "LibraryConfig",
    "ConfigValue",
    "validators",
    "tds",
    "tag",
    "command",
    "loop",
    "InfiniteLoop",
    "Placeholder",
    "watcher",
    "on",
    "inline_handler",
    "callback_handler",
    "raw_handler",
    "debug_method",
    "StringLoader",
    "LoadError",
    "CoreOverwriteError",
    "CoreUnloadError",
    "SelfUnload",
    "SelfSuspend",
    "StopLoop",
    "VALID_PIP_PACKAGES",
    "VALID_APT_PACKAGES",
    "USER_INSTALL",
]
