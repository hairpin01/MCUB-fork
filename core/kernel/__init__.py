# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01
def _mkfallback(name: str):
    return type(f"_{name}Fallback", (), {})


try:
    from core.kernel.standard import Kernel
except Exception:
    Kernel = _mkfallback("Kernel")

try:
    from core.kernel.test_kernel import (
        MockCallback,
        MockEvent,
        MockInlineQuery,
        MockTelegramClient,
        TestKernel,
    )
except Exception:
    MockCallback = _mkfallback("MockCallback")
    MockEvent = _mkfallback("MockEvent")
    MockInlineQuery = _mkfallback("MockInlineQuery")
    MockTelegramClient = _mkfallback("MockTelegramClient")
    TestKernel = _mkfallback("TestKernel")

try:
    from core.lib.base.config import ConfigManager
except Exception:
    ConfigManager = _mkfallback("ConfigManager")
try:
    from core.lib.base.database import DatabaseManager
except Exception:
    DatabaseManager = _mkfallback("DatabaseManager")

try:
    from core.lib.utils.logger import setup_logging
except Exception:
    setup_logging = _mkfallback("setup_logging")

__all__ = [
    "ConfigManager",
    "DatabaseManager",
    "Kernel",
    "MockCallback",
    "MockEvent",
    "MockInlineQuery",
    "MockTelegramClient",
    "TestKernel",
    "setup_logging",
]
