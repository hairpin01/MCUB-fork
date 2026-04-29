# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01
# ---- meta data ------ kernel_pipeline ------------
# author: @Hairpin00
# description: Pipeline execution, regex validation, script engine
# --- meta data end ---------------------------------
from __future__ import annotations

import ast
import re
import signal
import traceback
from typing import Any


class KernelPipelineMixin:
    """Kernel pipeline mixin — regex validation, pipeline, script engine."""

    MAX_PATTERN_LENGTH = 256
    PATTERN_TIMEOUT = 0.1

    _SAFE_OPS: dict = {
        ast.Add: lambda l, r: l + r,
        ast.Sub: lambda l, r: l - r,
        ast.Mult: lambda l, r: l * r,
        ast.Div: lambda l, r: l / r,
        ast.FloorDiv: lambda l, r: l // r,
        ast.Mod: lambda l, r: l % r,
        ast.Pow: lambda l, r: l**r,
        ast.USub: lambda l: -l,
        ast.UAdd: lambda l: +l,
    }

    _PIPE_SUB_PATTERN = re.compile(
        r"\{\s*(pipe_input|import\s+[a-zA-Z_][a-zA-Z0-9_.]*)\s*(?:\[([^\]]*)\])?\s*\}"
    )

    @staticmethod
    def _validate_regex_pattern(pattern: str) -> tuple[bool, str]:
        """Validate regex pattern for ReDoS protection."""
        if len(pattern) > KernelPipelineMixin.MAX_PATTERN_LENGTH:
            return (
                False,
                f"Pattern too long (max {KernelPipelineMixin.MAX_PATTERN_LENGTH})",
            )

        dangerous_patterns = [
            r"\(\.\*\)\+",
            r"\(\.\+\)\+",
            r"\(\.\*\)\*",
            r"\(\.\+\)\*",
            r"\(\.\{\d+,\}\)\+",
            r".*.*.*",
            r"\(\?\=\.\*\)",
        ]

        for danger in dangerous_patterns:
            if re.search(danger, pattern):
                return False, "Potentially dangerous regex pattern detected"

        try:
            test_pattern = re.compile(pattern)
            test_string = "x" * 1000

            def timeout_handler(signum, frame):
                raise TimeoutError()

            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(1)

            try:
                test_pattern.match(test_string)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

        except TimeoutError:
            return False, "Pattern too complex (timeout)"
        except re.error as e:
            return False, f"Invalid regex: {e}"

        return True, "OK"

    def safe_eval(self, node: ast.AST) -> float:
        """Evaluate a numeric AST expression without using eval().

        Supports: +  -  *  /  //  %  **  and unary +/-.
        Raises ValueError for unsupported nodes or exponents > 1000.
        """
        if isinstance(node, ast.Expression):
            return self.safe_eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in self._SAFE_OPS:
            left = self.safe_eval(node.left)
            right = self.safe_eval(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                raise ValueError("exponent too large")
            return self._SAFE_OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._SAFE_OPS:
            return self._SAFE_OPS[type(node.op)](self.safe_eval(node.operand))
        raise ValueError(f"unsupported expression: {ast.dump(node)}")

    def pipe_interpolate(self, text: str, pipe_input: str = "") -> str:
        """Substitute ``{pipe_input[...]}`` and ``{import var}`` placeholders."""

        def _replace(match: re.Match) -> str:
            expr = match.group(1).strip()
            slice_spec = match.group(2)

            if expr == "pipe_input":
                value = pipe_input
            elif expr.startswith("import "):
                value = self._pipe_vars.get(expr[7:].strip(), "")
            else:
                return match.group(0)

            if slice_spec is not None and value:
                try:
                    parts = slice_spec.split(":")
                    start = int(parts[0]) if parts[0] else None
                    stop = int(parts[1]) if len(parts) > 1 and parts[1] else None
                    step = int(parts[2]) if len(parts) > 2 and parts[2] else None
                    value = value[start:stop:step]
                except (ValueError, TypeError, IndexError):
                    pass

            return value

        return self._PIPE_SUB_PATTERN.sub(_replace, text)

    async def run_script(
        self,
        source: str,
        event,
        *,
        name: str = "unnamed",
        show_result: bool = True,
    ) -> str | None:
        """Execute a MCUB script and optionally display the last output.

        Called by ``cmd_script`` in utils_piped. All scripting logic lives here.
        """
        try:
            from core.lib.script.engine import ScriptEngine, ScriptError
        except Exception as e:
            self.logger.debug(f"error import script: {e}")
            return f"<b>Error</b> import script.engine: <code>{e}</code>"

        try:
            ctx, log_lines = await self.script_engine.run(source, event)
        except ScriptError as exc:
            err_text = f"<b>Script error</b> [{name}]\n<code>{exc}</code>"
            try:
                await event.edit(err_text, parse_mode="html")
            except Exception:
                pass
            self.logger.warning("[run_script] %s: %s", name, exc)
            return None
        except Exception as exc:
            tb = traceback.format_exc()
            self.logger.error("[run_script] unexpected: %s\n%s", exc, tb)
            err_text = f"<b>Script crashed</b> [{name}]\n<code>{exc}</code>"
            try:
                await event.edit(err_text, parse_mode="html")
            except Exception:
                pass
            return None

        # If the script never called event.edit itself, show the last captured output
        interp_output = getattr(self.script_engine, "_last_output", None)
        return interp_output

    def save_script(self, name: str, source: str) -> None:
        """Persist a named script in ``self._pipe_macros``."""
        self._pipe_macros[name] = source

    def load_script(self, name: str) -> str | None:
        """Retrieve a named script body, or None if not found."""
        return self._pipe_macros.get(name)

    def list_scripts(self) -> list[str]:
        """Return sorted list of saved script names."""
        return sorted(self._pipe_macros)
