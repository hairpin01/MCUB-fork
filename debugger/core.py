# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""
MCUB Debugger Core - Main analysis engine.
"""

import ast
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from debugger.rules import RuleRegistry

from debugger.types import Warning, DebugResult


class SourceAnalyzer(ast.NodeVisitor):
    """AST visitor for analyzing Python source code with context awareness."""

    def __init__(self, source: str, file_path: str, rule_registry: "RuleRegistry"):
        self.source = source
        self.source_lines = source.splitlines()
        self.file_path = file_path
        self.rules = rule_registry
        self.warnings: list[Warning] = []
        self.current_function: Optional[str] = None
        self.current_decorators: list[dict] = []
        self.current_line: int = 0
        self._in_async_function: bool = False
        self._function_start_line: int = 0
        self._event_handler_types: set[str] = set()
        self.symbol_stack: List[Dict[str, str]] = [{}]
        self.current_scope = self.symbol_stack[-1]
        self._noqa_lines: set[int] = self._parse_noqa_comments()
        print(f"[DEBUGGER] SourceAnalyzer init file={file_path}")

    def _parse_noqa_comments(self) -> set[int]:
        """Parse # noqa: MCUBxxx comments to ignore specific warnings."""
        noqa_lines = set()
        for i, line in enumerate(self.source_lines, start=1):
            if "# noqa" in line or "#noqa" in line:
                import re

                matches = re.findall(r"MCUB\d+", line)
                noqa_lines.add(i)
        return noqa_lines

    def is_line_noqa(self, lineno: int, rule_id: str = None) -> bool:
        """Check if line should be ignored due to noqa comment."""
        if lineno not in self._noqa_lines:
            return False
        if rule_id is None:
            return True
        line = self.source_lines[lineno - 1] if lineno <= len(self.source_lines) else ""
        return rule_id in line or f"MCUB" in line

    def _push_scope(self):
        self.symbol_stack.append({})
        self.current_scope = self.symbol_stack[-1]

    def _pop_scope(self):
        self.symbol_stack.pop()
        self.current_scope = self.symbol_stack[-1] if self.symbol_stack else {}

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node, is_async=True)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node, is_async=False)
        self.generic_visit(node)

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool
    ) -> None:
        old_function = self.current_function
        old_decorators = self.current_decorators
        old_async = self._in_async_function
        old_start = self._function_start_line

        self.current_function = node.name
        self.current_decorators = [
            self._parse_decorator(d) for d in node.decorator_list
        ]
        self._in_async_function = is_async
        self._function_start_line = node.lineno

        self._push_scope()
        for arg in node.args.args:
            if arg.arg == "event":
                self.current_scope[arg.arg] = "event"
            elif arg.arg == "kernel":
                self.current_scope[arg.arg] = "kernel"
            else:
                self.current_scope[arg.arg] = "unknown"

        self._check_rules(node)
        self._check_event_handlers(node)

        self.generic_visit(node)

        self._pop_scope()

        self.current_function = old_function
        self.current_decorators = old_decorators
        self._in_async_function = old_async
        self._function_start_line = old_start

    def _parse_decorator(self, node: ast.expr) -> dict:
        """Parse a decorator AST node into a dict with name, args, kwargs."""
        if isinstance(node, ast.Call):
            name = self._get_decorator_name(node.func)
            args = []
            kwargs = {}
            for arg in node.args:
                if isinstance(arg, ast.Constant):
                    args.append(arg.value)
                else:
                    args.append(None)
            for kw in node.keywords:
                if isinstance(kw.value, ast.Constant):
                    kwargs[kw.arg] = kw.value.value
                else:
                    kwargs[kw.arg] = None
            return {"name": name, "args": args, "kwargs": kwargs}
        else:
            name = self._get_decorator_name(node)
            return {"name": name, "args": [], "kwargs": {}}

    def _get_decorator_name(self, decorator: ast.expr) -> str:
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            parts = []
            node = decorator
            while isinstance(node, ast.Attribute):
                parts.append(node.attr)
                node = node.value
            if isinstance(node, ast.Name):
                parts.append(node.id)
            return ".".join(reversed(parts))
        elif isinstance(decorator, ast.Call):
            return self._get_decorator_name(decorator.func)
        return "unknown"

    def _check_rules(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for rule in self.rules.get_rules():
            if rule.should_check(self):
                warnings = rule.check(self, node)
                if warnings:
                    for w in warnings:
                        if not self.is_line_noqa(w.line, w.rule_id):
                            if w.function_name is None:
                                w.function_name = node.name
                            if not self._is_duplicate_warning(w):
                                self.warnings.append(w)

    def _is_duplicate_warning(self, warning: "Warning") -> bool:
        for existing in self.warnings:
            if existing.rule_id == warning.rule_id and existing.line == warning.line:
                return True
        return False

    def _check_event_handlers(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        for dec in self.current_decorators:
            name = dec["name"]
            if any(
                x in name
                for x in ["event", "callback", "inline", "command", "watcher", "loop"]
            ):
                self._event_handler_types.add(name)

    def get_line(self, lineno: int) -> str:
        """Get source line (1-indexed)."""
        if 1 <= lineno <= len(self.source_lines):
            return self.source_lines[lineno - 1]
        return ""

    def get_code_snippet(self, lineno: int, context_lines: int = 2) -> str:
        """Get code snippet around a line."""
        lines = []
        start = max(1, lineno - context_lines)
        end = min(len(self.source_lines), lineno + context_lines)

        for i in range(start, end + 1):
            prefix = ">>>" if i == lineno else "    "
            lines.append(f"{prefix} {self.source_lines[i - 1]}")

        return "\n".join(lines)

    def get_decorator_arg(self, decorator_name: str, arg_name: str) -> Any:
        """Get argument value from a decorator if present."""
        for dec in self.current_decorators:
            if dec["name"] == decorator_name:
                return dec["kwargs"].get(arg_name)
        return None

    def has_decorator(self, decorator_name: str) -> bool:
        """Check if the current function has a specific decorator."""
        for dec in self.current_decorators:
            if dec["name"] == decorator_name:
                return True
        return False

    def get_symbol_type(self, name: str) -> Optional[str]:
        """Get the inferred type of a variable in the current scope."""
        for scope in reversed(self.symbol_stack):
            if name in scope:
                return scope[name]
        return None

    def visit_Assign(self, node: ast.Assign):
        """Track variable assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                if isinstance(node.value, ast.Attribute):
                    if (
                        isinstance(node.value.value, ast.Name)
                        and node.value.value.id == "kernel"
                    ):
                        attr = node.value.attr
                        if attr == "client":
                            self.current_scope[var_name] = "client"
                        elif attr == "bot_client":
                            self.current_scope[var_name] = "bot_client"
                        elif attr == "config":
                            self.current_scope[var_name] = "config"
                        else:
                            self.current_scope[var_name] = "kernel." + attr
                    else:
                        self.current_scope[var_name] = "unknown"
                elif isinstance(node.value, ast.Name):
                    sym_type = self.get_symbol_type(node.value.id)
                    self.current_scope[var_name] = sym_type if sym_type else "unknown"
                elif isinstance(node.value, ast.Constant):
                    if node.value.value is None:
                        self.current_scope[var_name] = "None"
                    else:
                        self.current_scope[var_name] = "Constant"
                elif isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Attribute):
                        if node.value.func.attr in (
                            "inline",
                            "url",
                            "switch_inline",
                            "text",
                        ):
                            self.current_scope[var_name] = "Button"
                        elif isinstance(node.value.func.value, ast.Name):
                            if node.value.func.value.id == "Button":
                                self.current_scope[var_name] = "Button"
                            else:
                                self.current_scope[var_name] = "Call"
                        else:
                            self.current_scope[var_name] = "Call"
                    elif isinstance(node.value.func, ast.Name):
                        if "Button" in node.value.func.id:
                            self.current_scope[var_name] = "Button"
                        else:
                            self.current_scope[var_name] = "Call"
                    else:
                        self.current_scope[var_name] = "Call"
                elif isinstance(node.value, ast.List):
                    if node.value.elts:
                        if self._is_button_list(node.value):
                            self.current_scope[var_name] = "ButtonList"
                        else:
                            self.current_scope[var_name] = "List"
                    else:
                        self.current_scope[var_name] = "List"
                elif isinstance(node.value, ast.Dict):
                    self.current_scope[var_name] = "Dict"
                else:
                    self.current_scope[var_name] = "unknown"
        self.generic_visit(node)

    def _is_button_list(self, node: ast.List) -> bool:
        """Check if a list contains Button objects."""
        for elem in node.elts:
            if isinstance(elem, ast.Call):
                if isinstance(elem.func, ast.Attribute):
                    if elem.func.attr in ("inline", "url", "switch_inline", "text"):
                        return True
                elif isinstance(elem.func, ast.Name):
                    if "Button" in elem.func.id:
                        return True
            elif isinstance(elem, ast.List):
                if self._is_button_list(elem):
                    return True
        return False

    def visit_Import(self, node: ast.Import):
        """Track imports."""
        for alias in node.names:
            self.current_scope[alias.asname or alias.name] = "module:" + alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Track from-imports."""
        module = node.module or ""
        for alias in node.names:
            self.current_scope[alias.asname or alias.name] = (
                "module:" + module + "." + alias.name
            )
        self.generic_visit(node)


class ModuleDebugger:
    """Main debugger class for analyzing MCUB modules."""

    def __init__(self, rules: Optional["RuleRegistry"] = None):
        if rules is None:
            from debugger.rules import get_default_rules

            rules = get_default_rules()
        self.rules = rules
        self.results: dict[str, DebugResult] = {}

    def debug_file(self, file_path: str | Path) -> DebugResult:
        """Debug a single module file."""
        start = time.time()

        file_path = Path(file_path)

        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception as e:
            result = DebugResult(
                file_path=str(file_path),
                module_name=file_path.stem,
                errors=[f"Failed to read file: {e}"],
            )
            return result

        result = self._analyze_source(source, str(file_path), file_path.stem)
        result.duration_ms = (time.time() - start) * 1000

        self.results[str(file_path)] = result
        return result

    def debug_directory(
        self, directory: str | Path, pattern: str = "*.py"
    ) -> list[DebugResult]:
        """Debug all Python files in a directory."""
        directory = Path(directory)
        results = []

        for file_path in directory.rglob(pattern):
            if file_path.name.startswith("_"):
                continue
            if "modules_loaded" in file_path.parts:
                continue
            result = self.debug_file(file_path)
            results.append(result)

        return results

    def _analyze_source(
        self, source: str, file_path: str, module_name: str
    ) -> DebugResult:
        """Analyze source code and collect warnings."""
        result = DebugResult(file_path=file_path, module_name=module_name)

        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as e:
            result.errors.append(f"Syntax error: {e}")
            return result

        analyzer = SourceAnalyzer(source, file_path, self.rules)
        analyzer.warnings = []

        try:
            ast.NodeVisitor.generic_visit(analyzer, tree)
        except Exception as e:
            result.errors.append(f"AST analysis error: {e}")

        result.warnings = analyzer.warnings
        result.checked_lines = len(source.splitlines())

        return result

    def print_result(self, result: DebugResult, verbose: bool = False) -> None:
        """Print debug results to console."""
        colors = _get_colors()

        if result.is_clean:
            print(
                f"{colors['green']}OK{colors['reset']} {colors['white']}{result.module_name}{colors['reset']}"
            )
            return

        print(
            f"\n{colors['red']}ISSUE{colors['reset']} {colors['white']}{result.module_name}{colors['reset']} ({colors['dim']}{result.file_path}{colors['reset']})"
        )

        for warning in result.warnings:
            print(warning.format())

        if result.errors:
            print(f"{colors['red']}Errors:{colors['reset']}")
            for error in result.errors:
                print(f"  {colors['red']}*{colors['reset']} {error}")

        print(
            f"\n{colors['dim']}Checked {result.checked_lines} lines in {result.duration_ms:.1f}ms{colors['reset']}"
        )

    def debug_and_print(self, path: str | Path, verbose: bool = True) -> bool:
        """Debug and print results, returns True if issues found."""
        if Path(path).is_file():
            result = self.debug_file(path)
            self.print_result(result, verbose)
            return result.has_warnings or result.has_errors
        else:
            results = self.debug_directory(path)
            has_issues = False

            for result in sorted(results, key=lambda x: x.file_path):
                if result.has_warnings or result.has_errors:
                    has_issues = True
                    self.print_result(result, verbose)
                else:
                    self.print_result(result, verbose)

            return has_issues


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

    return {
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


def debug_module(path: str | Path) -> DebugResult:
    """Quick function to debug a single module."""
    debugger = ModuleDebugger()
    return debugger.debug_file(path)


def debug_modules(path: str | Path) -> list[DebugResult]:
    """Quick function to debug all modules in a directory."""
    debugger = ModuleDebugger()
    return debugger.debug_directory(path)
