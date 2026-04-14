# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""
MCUB Debugger - Static analysis tool for MCUB modules.

Detects common errors in module code before runtime.
"""

from debugger.core import ModuleDebugger, SourceAnalyzer
from debugger.rules import RuleRegistry, get_default_rules
from debugger.types import DebugResult, Warning

__version__ = "1.0.0"
__author__ = "@Hairpin00"

__all__ = [
    "ModuleDebugger",
    "DebugResult",
    "Warning",
    "SourceAnalyzer",
    "RuleRegistry",
    "get_default_rules",
]
