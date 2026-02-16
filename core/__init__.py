# author: @Hairpin00
# version: 1.1.0
# description: Core package initialization

# Import from lib
from .lib.colors import Colors
from .lib.exceptions import CommandConflictError
from .lib.cache import TTLCache
from .lib.scheduler import TaskScheduler
from .lib.register import Register
from .lib.permissions import CallbackPermissionManager
from .lib.database import DatabaseManager

# Import module configuration system
from .lib.module_config import (
    ModuleConfig,
    ConfigValue,
    Validator,
    Boolean,
    Integer,
    Float,
    String,
    Choice,
    MultiChoice,
    Secret,
    ValidationError,
)

from .version import VersionManager
from .kernel import Kernel

__all__ = [
    "Kernel",
    "Colors",
    "Register",
    "CallbackPermissionManager",
    "TTLCache",
    "TaskScheduler",
    "CommandConflictError",
    "DatabaseManager",
    "VersionManager",
    "ModuleConfig",
    "ConfigValue",
    "Validator",
    "Boolean",
    "Integer",
    "Float",
    "String",
    "Choice",
    "MultiChoice",
    "Secret",
    "ValidationError",
]
