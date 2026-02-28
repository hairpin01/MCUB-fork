# Backward compatibility shim - re-exports from core/kernel/
from core.kernel.standard import Kernel
from core.lib.base.database import DatabaseManager
from core.lib.base.config import ConfigManager
from core.lib.utils.logger import setup_logging
from core.kernel.test_kernel import TestKernel, MockEvent, MockCallback, MockInlineQuery, MockTelegramClient

# Re-export exceptions etc. if needed
try:
    from core.kernel.standard import CommandConflictError
except ImportError:
    pass

__all__ = [
    "Kernel",
    "DatabaseManager",
    "ConfigManager", 
    "setup_logging",
    "TestKernel",
    "MockEvent",
    "MockCallback",
    "MockInlineQuery",
    "MockTelegramClient",
]
