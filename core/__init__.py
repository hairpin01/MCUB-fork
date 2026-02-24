# author: @Hairpin00
# version: 1.1.0
# description: Core package initialization

# Import from lib
from .lib.utils.colors import Colors
from .lib.utils.exceptions import CommandConflictError
from .lib.time.cache import TTLCache
from .lib.time.scheduler import TaskScheduler
from .lib.loader.register import Register
from .lib.loader.module_config import (
    ModuleConfig, ConfigValue, Validator, Boolean, Integer,
    Float, String, Choice, MultiChoice, Secret, ValidationError,
)
from .lib.base.permissions import CallbackPermissionManager
from .lib.base.database import DatabaseManager
from .version import VersionManager, VERSION

from .lib.loader.loader import ModuleLoader
from .lib.loader.repository import RepositoryManager
from .lib.utils.logger import KernelLogger, setup_logging
from .lib.base.config import ConfigManager
from .lib.base.client import ClientManager
from .lib.loader.inline import InlineManager

# Import module configuration system
from .lib.loader.module_config import (
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
