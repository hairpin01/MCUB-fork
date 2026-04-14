# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""
MCUB Debugger Types - Shared data types.
"""

import sys
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Warning:
    """Represents a single warning found by the debugger."""

    rule_id: str
    severity: str
    message: str
    file_path: str
    line: int
    column: int
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    code_snippet: str = ""
    fix_suggestion: Optional[str] = None
    function_name: Optional[str] = None

    def format(self) -> str:
        """Format warning for terminal output."""
        colors = _get_colors()

        sep = " " * (self.column - 1) + "~" * max(
            1, (self.end_column or self.column + 1) - self.column
        )

        output = []
        output.append(f"{colors['yellow']}{'─' * 70}{colors['reset']}")
        func_name = (
            self.function_name if self.function_name else self._get_method_name()
        )
        output.append(
            f"{colors['bold']}{colors['yellow']}[WARNING]{colors['reset']} {colors['cyan']}{self.rule_id}{colors['reset']} {colors['dim']}method{colors['reset']} {colors['white']}'{func_name}'{colors['reset']} {colors['dim']}lines {self.line}{colors['reset']}"
        )
        output.append(f"{colors['bold']}Message:{colors['reset']} {self.message}")
        output.append(
            f"{colors['dim']}{self.file_path}:{self.line}:{self.column}{colors['reset']}"
        )
        output.append("")

        if self.code_snippet:
            output.append(
                f"{colors['dim']}|{self.line:4d} {self.code_snippet}{colors['reset']}"
            )
            if sep:
                output.append(f"{colors['red']}|{self.line:4d} {sep}{colors['reset']}")

        if self.fix_suggestion:
            output.append(
                f"{colors['green']}Fix:{colors['reset']} {self.fix_suggestion}"
            )

        output.append(f"{colors['yellow']}{'─' * 70}{colors['reset']}")

        return "\n".join(output)

    def _get_method_name(self) -> str:
        """Extract handler/method name from code context."""
        import re

        if self.code_snippet:
            match = re.search(
                r"@\w+(?:\.\w+)*\s*\n\s*(?:async\s+)?def\s+(\w+)", self.code_snippet
            )
            if match:
                return match.group(1)
            match = re.search(r"(?:async\s+)?def\s+(\w+)", self.code_snippet)
            if match:
                return match.group(1)
        return "unknown"


@dataclass
class DebugResult:
    """Result of debugging a single module."""

    file_path: str
    module_name: str
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    checked_lines: int = 0
    duration_ms: float = 0.0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def is_clean(self) -> bool:
        return not self.has_warnings and not self.has_errors


def _get_colors() -> dict[str, str]:
    """Get terminal color codes."""
    if not sys.stdout.isatty():
        return {
            k: ""
            for k in [
                "red",
                "green",
                "yellow",
                "blue",
                "cyan",
                "white",
                "dim",
                "bold",
                "reset",
                "blink",
            ]
        }

    colors = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "blink": "\033[5m",
    }
    return colors
