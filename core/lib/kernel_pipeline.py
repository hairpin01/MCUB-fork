# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01
# ---- meta data ------ kernel_pipeline ------------
# author: @Hairpin00
# description: Pipeline execution, regex validation, script engine
# --- meta data end ---------------------------------
from __future__ import annotations

import ast
import concurrent.futures
import os
import re
import traceback


class KernelPipelineMixin:
    """Kernel pipeline mixin - regex validation, pipeline, script engine."""

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

    _AT_PATTERN = re.compile(r"@\{([^}]+)\}")
    _AT_CMD_PATTERN = re.compile(r"@\(([^)]+)\)")

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
        except re.error as e:
            return False, f"Invalid regex: {e}"

        # Run the potentially catastrophic match() in a thread so a timeout can
        # be applied safely.  Using signal.SIGALRM inside an async coroutine is
        # dangerous: the alarm can interrupt asyncio's own epoll/select syscalls,
        # causing spurious InterruptedError in unrelated coroutines.
        test_string = "x" * 1000
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(test_pattern.match, test_string)
                future.result(timeout=KernelPipelineMixin.PATTERN_TIMEOUT)
        except concurrent.futures.TimeoutError:
            return False, "Pattern too complex (timeout)"
        except Exception:
            pass

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

    def _resolve_at(self, match: re.Match, pipe_input: str) -> str:
        """Resolve ``@{...}`` expression to a string value."""
        raw = match.group(1).strip()

        # Extract [slice]
        slice_spec = None
        sm = re.search(r"\[([^\]]*)\]", raw)
        if sm:
            slice_spec = sm.group(1)
            raw = raw[: sm.start()]

        # Extract suffix chain via split-on-`:` (but skip escaped `\:`)
        parts = re.split(r"(?<!\\):", raw)
        expr = parts[0].strip()
        suffixes = parts[1:]

        # Classify expression
        if expr.startswith("env "):
            value = os.environ.get(expr[4:].strip(), "")
        elif expr.startswith("file "):
            path = expr[5:].strip()
            if path.startswith("~/"):
                path = os.environ.get("HOME", "~") + path[1:]
            try:
                with open(
                    os.path.expanduser(path), encoding="utf-8", errors="replace"
                ) as f:
                    value = f.read()
            except (OSError, FileNotFoundError) as e:
                value = None
                self.logger.debug("[pipe] file not readable: %s (%s)", path, e)
        elif expr.startswith("import "):
            key = expr[7:].strip()
            if not self._import_exists(key):
                return match.group(0)  # defer
            value = self._resolve_import(key)
        elif expr == "pipe_input":
            value = pipe_input
        else:
            # bare var name → import
            if not self._import_exists(expr):
                return match.group(0)  # defer
            value = self._resolve_import(expr)

        # Apply suffixes (:filter :-default :?error)
        error_msg = None
        default = None
        filter_names: list[str] = []
        for s in suffixes:
            s = s.replace("\\:", ":")  # unescape
            if s.startswith("?"):
                error_msg = s[1:]
            elif s.startswith("-"):
                default = s[1:]
            elif s:
                filter_names.append(s)

        # Apply default / error
        if value is None or (isinstance(value, str) and not value):
            if error_msg is not None:
                raise ValueError(error_msg)
            if default is not None:
                value = default

        # Apply slice
        if slice_spec is not None and isinstance(value, str) and value:
            try:
                sp = slice_spec.split(":")
                start = int(sp[0]) if sp[0] else None
                stop = int(sp[1]) if len(sp) > 1 and sp[1] else None
                step = int(sp[2]) if len(sp) > 2 and sp[2] else None
                value = value[start:stop:step]
            except (ValueError, TypeError, IndexError):
                pass

        # Apply filters in chain
        if filter_names and isinstance(value, str):
            _FILTER_MAP = {
                "upper": str.upper,
                "lower": str.lower,
                "title": str.title,
                "strip": str.strip,
                "len": lambda v: str(len(v)),
                "reverse": lambda v: v[::-1],
                "split": lambda v: v.splitlines()[0] if v else "",
            }
            for fn in filter_names:
                f = _FILTER_MAP.get(fn)
                if f:
                    value = f(value)

        return str(value) if value is not None else ""

    def _resolve_import(self, key: str) -> str | None:
        """Look up ``key`` in ``_pipe_vars``, supporting dotted access."""
        if key in self._pipe_vars:
            return self._pipe_vars[key]
        # dotted traversal
        value = self._pipe_vars
        for part in key.split("."):
            if isinstance(value, dict):
                value = value.get(part, None)
            else:
                return None
        return value

    def _import_exists(self, key: str) -> bool:
        """Return True when ``key`` can be resolved from ``_pipe_vars``."""
        return self._resolve_import(key) is not None

    def pipe_interpolate(self, text: str, pipe_input: str = "") -> str:
        """Substitute ``@{...}`` placeholders.

        Supported forms::

            @{var}                  import from _pipe_vars
            @{import var}           explicit import
            @{import a.b.c}         dotted key
            @{pipe_input}           pipe input value
            @{pipe_input[0:5]}      with slice
            @{env HOME}             environment variable
            @{file /etc/hostname}   read file
            @{var:upper}            filter (upper/lower/title/strip/len/reverse/split)
            @{var:-default}         default if empty
            @{var:?error msg}       raise ValueError with custom message
            @{file /path[:10]:?err:-fallback}   all combined
        """

        def _replace(m: re.Match) -> str:
            try:
                return self._resolve_at(m, pipe_input)
            except ValueError as exc:
                return str(exc)
            except Exception:
                return m.group(0)

        return self._AT_PATTERN.sub(_replace, text)

    async def async_pipe_interpolate(
        self,
        text: str,
        pipe_input: str = "",
        event: Any = None,
        active_prefix: str = "",
    ) -> str:
        """Like ``pipe_interpolate`` but also resolves ``@(cmd)``."""
        text = self.pipe_interpolate(text, pipe_input)

        if "@(" not in text:
            return text

        dispatcher = getattr(self, "dispatcher", None)
        if dispatcher is None:
            return text

        async def _replace_cmd(m: re.Match) -> str:
            cmd = m.group(1).strip()
            captured: list[str] = []
            chat_id = getattr(event, "chat_id", None) if event else None

            # Skip if parent event has no_owner (like pipeline does)
            if event and hasattr(event, "no_owner"):
                return ""

            # Build proxy event that captures edits
            class _CaptureEvent:
                def __init__(self_):
                    self_.text = cmd
                    self_.piped = True
                    self_.pipe_input = ""
                    self_.pipe_output = None
                    self_.pipe_exit_code = 0
                    self_.no_add_args_to_input = False
                    self_.chat_id = chat_id
                    self_.sender_id = getattr(event, "sender_id", None)
                    self_._captured = captured
                    self_._prefix = active_prefix

                async def edit(self_, new_text: str, *a: Any, **kw: Any) -> None:
                    self_._captured.append(new_text)

                async def respond(self_, *a: Any, **kw: Any) -> None:
                    pass

                async def reply(self_, *a: Any, **kw: Any) -> None:
                    pass

                async def delete(self_) -> None:
                    pass

                def __getattr__(self_, name: str) -> Any:
                    return lambda *a, **kw: None

            proxy = _CaptureEvent()
            try:
                result_flag = await dispatcher.process_command(proxy)
                pipe_code = getattr(proxy, "pipe_exit_code", "?")
                self.logger.debug(
                    "[pipe] @(cmd) %r → captured=%d exit_code=%s result=%s",
                    cmd,
                    len(captured),
                    pipe_code,
                    result_flag,
                )
            except Exception as exc:
                self.logger.debug("[pipe] @(cmd) %r failed: %s", cmd, exc)
                return f"<@ERR:{exc}>"
            if not captured:
                self.logger.debug("[pipe] @(cmd) %r — no output captured", cmd)
                return ""
            return captured[-1]

        matches = list(self._AT_CMD_PATTERN.finditer(text))
        if not matches:
            return text

        parts = []
        last = 0
        for m in matches:
            parts.append(text[last : m.start()])
            parts.append(await _replace_cmd(m))
            last = m.end()
        parts.append(text[last:])

        return "".join(parts)

    async def _execute_pipeline(self, event: Any, pipeline: Any, depth: int) -> bool:
        """Execute a multi-segment pipeline expression."""
        segments = pipeline.segments
        if not segments:
            return False
        if depth > 5:
            self.logger.error(f"Pipeline recursion limit reached: {event.text}")
            await self.log_error_async(
                f"Pipeline recursion limit reached: {event.text}"
            )
            return False
        if hasattr(event, "no_owner"):
            await event.edit(
                f"ignored pipeline command: {event.no_owner()}", parse_mode="html"
            )
            return False

        original_edit = getattr(event, "edit", None)
        original_text = event.text
        original_piped = getattr(event, "piped", False)
        original_pipe_input = getattr(event, "pipe_input", None)
        chat_id = getattr(event, "chat_id", None)

        current_event = event
        pipe_input = None
        exit_code = 0

        for i, seg in enumerate(segments):
            next_seg = segments[i + 1] if i + 1 < len(segments) else None

            if seg.operator == "||":
                expected_exit_code = getattr(seg, "exit_code", None)
                if expected_exit_code is not None:
                    # ||[N] — run only if exit_code == N
                    if exit_code != expected_exit_code:
                        continue
                elif exit_code == 0:
                    continue
            elif seg.operator == "&&":
                pipe_input = None
                if not chat_id:
                    continue
                try:
                    sent = await self.client.send_message(chat_id, seg.command)
                    if not sent:
                        exit_code = 1
                        continue
                    new_ev = self._make_simple_event(sent, seg.command, chat_id)
                    new_ev.pipe_input = None
                    is_piped = next_seg is not None and next_seg.operator == "|"
                    new_ev.piped = is_piped
                    if is_piped:
                        pipe_input = await self._run_and_capture(new_ev, depth + 1)
                    else:
                        await self.process_command(new_ev, depth=depth + 1)
                    exit_code = getattr(new_ev, "pipe_exit_code", 0) or 0
                    current_event = new_ev
                except Exception:
                    exit_code = 1
                continue

            elif seg.operator == "&":
                pipe_input = None
                self._wrap_edit_with_fallback(current_event, chat_id)

            is_piped = next_seg is not None and next_seg.operator == "|"

            cmd_text = seg.command

            # Reconstruct the full command from the base segment.
            if seg.operator == "|>":
                base = self._find_base_command(segments, i)
                cmd_text = (base + " " + seg.command).strip() if base else seg.command

            current_event.piped = is_piped
            current_event.pipe_input = pipe_input

            self._set_event_text(current_event, cmd_text)

            if is_piped:
                pipe_input = await self._run_and_capture(current_event, depth)
                exit_code = getattr(current_event, "pipe_exit_code", 0) or 0
            else:
                if current_event is event and original_edit is not None:
                    current_event.edit = original_edit
                await self.process_command(current_event, depth=depth)
                exit_code = getattr(current_event, "pipe_exit_code", 0) or 0
                pipe_input = None

        event.piped = original_piped
        event.pipe_input = original_pipe_input
        if original_edit is not None:
            event.edit = original_edit
        self._set_event_text(event, original_text)
        return True

    @staticmethod
    def _find_base_command(segments: list, idx: int) -> str | None:
        """Find the base command (first word) for a ``|>`` segment.

        Walks backwards from ``idx`` to locate the nearest preceding
        non-``|>`` segment and returns its first word.
        """
        for j in range(idx - 1, -1, -1):
            prev_op = segments[j].operator
            if prev_op is None or prev_op in ("|", "&&", "||"):
                text = segments[j].command
                return text.split()[0] if text else None
        return None

    def _make_simple_event(self, msg: Any, text: str, chat_id: int) -> Any:
        """Build a lightweight event object wrapping a freshly sent message."""
        kernel = self

        class _SimpleEvent:
            def __init__(inner_self) -> None:
                inner_self.id = getattr(msg, "id", None)
                inner_self.message_id = inner_self.id
                inner_self.chat_id = chat_id
                inner_self.text = text
                inner_self.message = msg
                inner_self.sender_id = getattr(msg, "sender_id", None)
                inner_self.reply_to_msg_id = getattr(msg, "reply_to_msg_id", None)
                inner_self._client = kernel.client
                inner_self.pipe_input = None
                inner_self.pipe_output = None
                inner_self.pipe_exit_code = 0
                inner_self.piped = False
                inner_self.no_add_args_to_input = False

            async def delete(inner_self):
                try:
                    await inner_self._client.delete_messages(
                        inner_self.chat_id, [inner_self.id]
                    )
                except Exception:
                    pass

            async def get_reply_message(inner_self):
                if not inner_self.reply_to_msg_id:
                    return None
                try:
                    return await inner_self._client.get_messages(
                        inner_self.chat_id, ids=inner_self.reply_to_msg_id
                    )
                except Exception:
                    return None

            async def edit(inner_self, new_text, *args, parse_mode=None, **kwargs):
                try:
                    return await inner_self._client.edit_message(
                        inner_self.chat_id,
                        inner_self.id,
                        new_text,
                        parse_mode=parse_mode,
                    )
                except Exception as _err:
                    kernel.logger.debug(
                        "[SimpleEvent.edit] edit failed (%s), falling back to send_message",
                        _err,
                    )
                    try:
                        sent = await inner_self._client.send_message(
                            inner_self.chat_id, new_text, parse_mode=parse_mode
                        )
                        if sent and hasattr(sent, "id"):
                            inner_self.id = sent.id
                            inner_self.message_id = sent.id
                        return sent
                    except Exception:
                        return None

            async def get_sender(inner_self):
                return await inner_self._client.get_entity(inner_self.sender_id)

            async def get_chat(inner_self):
                return await inner_self._client.get_entity(inner_self.chat_id)

        return _SimpleEvent()

    def _wrap_edit_with_fallback(self, ev: Any, chat_id: int) -> None:
        """Wrap ev.edit so that on failure it falls back to send_message."""
        original_edit = getattr(ev, "edit", None)
        kernel = self

        async def _fallback_edit(new_text, *args, parse_mode=None, **kwargs):
            if original_edit is not None:
                try:
                    return await original_edit(
                        new_text, *args, parse_mode=parse_mode, **kwargs
                    )
                except Exception as _err:
                    kernel.logger.debug(
                        "[& edit-fallback] edit failed (%s), sending new message", _err
                    )
            try:
                sent = await kernel.client.send_message(
                    chat_id, new_text, parse_mode=parse_mode
                )
                if sent and hasattr(sent, "id"):
                    ev.id = sent.id
                    ev.message_id = sent.id
                return sent
            except Exception:
                return None
            return None

        ev.edit = _fallback_edit

    async def _run_and_capture(self, ev: Any, depth: int) -> str | None:
        """Run ev through process_command and return the text passed to event.edit."""
        captured = []
        orig_edit = getattr(ev, "edit", None)

        class _FakeMsg:
            async def edit(inner_self, *a, **kw):
                return inner_self

        async def _cap(new_text, *args, **kwargs):
            if isinstance(new_text, str):
                captured.append(new_text)
            return _FakeMsg()

        ev.edit = _cap
        try:
            await self.process_command(ev, depth=depth)
        finally:
            if orig_edit is not None:
                ev.edit = orig_edit
            else:
                try:
                    del ev.edit
                except AttributeError:
                    pass

        explicit = getattr(ev, "pipe_output", None)
        return (
            explicit if explicit is not None else (captured[-1] if captured else None)
        )

    # User/Thread utilities

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

            if self.script_engine is None:
                self.script_engine = ScriptEngine(self)
        except Exception as e:
            self.logger.debug(f"error import script: {e}")
            return f"<b>Error</b> import script.engine: <code>{e}</code>"

        try:
            _ctx, _log_lines = await self.script_engine.run(source, event)
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
