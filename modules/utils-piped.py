# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import ast
import asyncio
import base64
import html
import json
import operator
import os
import random as _random
import re
import traceback
from typing import Any

from telethon import events

from core.lib.loader.module_base import ModuleBase, command


def _get_text(event, args: str) -> str:
    """Get text from args or pipe_input."""
    if args:
        parts = args.split(None, 1)
        if len(parts) > 1:
            return parts[1]
        return ""
    pipe_input = getattr(event, "pipe_input", None)
    return pipe_input or ""


class UtilsPiped(ModuleBase):
    name = "utils-piped"
    version = "1.0.0"
    author = "@Hairpin00"
    description = {"ru": "Утилиты для конвейера", "en": "Utils for pipeline"}

    strings = {"name": "utils_piped"}

    @command(
        "echo",
        doc_ru="""[text] вывести текст с подстановками (поддерживает {pipe_input[:X]} - пример .man | 1wc -l | .echo <b>модулей: {pipe_input[:50]}, {import [var]} - тоже самое что .man | .export man && .import man | .echo modules: {pipe_input}, пример .man | .export man | .delete && .echo modules {{import man}})""",
        doc_en="[text] display text with substitutions (supports {pipe_input[:X]} - example .man | 1wc -l | .echo <b>modules: {pipe_input[:50]}, {import [var]} - the same as .man | .export man && .import man | .echo modules: {pipe_input}, example .man | .export man | .delete && .echo modules {import man})",
    )
    async def cmd_echo(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event)
            pipe_input = getattr(event, "pipe_input", None) or ""
            pipe_vars = getattr(self.kernel, "_pipe_vars", {})

            # Шаблон подстановки: {import var[:срез]} или {pipe_input[:срез]}
            def replacer(match):
                expr = match.group(1)
                # Проверяем срез
                slice_match = re.match(
                    r"^(import\s+)?([a-zA-Z_.][a-zA-Z0-9_.]*|pipe_input)(?:\[(.*?)\])?$",
                    expr.strip(),
                )
                if not slice_match:
                    return match.group(0)  # оставляем как есть
                _, name, slice_spec = slice_match.groups()
                if name == "pipe_input":
                    value = pipe_input
                else:
                    value = pipe_vars.get(name, "")
                if slice_spec and value:
                    # парсим срез вида [:5] или [2:10] или [::-1]
                    try:
                        parts = slice_spec.split(":")
                        if len(parts) == 1:
                            start = int(parts[0]) if parts[0] else None
                            stop = None
                            step = None
                        elif len(parts) == 2:
                            start = int(parts[0]) if parts[0] else None
                            stop = int(parts[1]) if parts[1] else None
                            step = None
                        elif len(parts) == 3:
                            start = int(parts[0]) if parts[0] else None
                            stop = int(parts[1]) if parts[1] else None
                            step = int(parts[2]) if parts[2] else None
                        else:
                            return match.group(0)
                        # Применяем срез
                        value = value[start:stop:step]
                    except (ValueError, TypeError):
                        pass  # при ошибке оставляем исходную строку
                return value

            if args:
                text = re.sub(r"\{([^}]+)\}", replacer, args)
            else:
                text = pipe_input

            event.no_add_args_to_input = True

            if not text:
                await self.edit(event, "")
                return

            if getattr(event, "piped", False):
                await self.edit(event, text)
                return

            await self.edit(event, text, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="echo", event=event)

    @command(
        "nop",
        doc_ru="ничего не делает",
        doc_en="do nothing",
    )
    async def cmd_nop(self, event: events.NewMessage.Event) -> None:
        try:
            if getattr(event, "piped", False):
                await self.edit(event, "")
        except Exception as e:
            await self.kernel.handle_error(e, source="nop", event=event)

    @command(
        "delete",
        doc_ru="удалить сообщение команды",
        doc_en="delete command message",
    )
    async def cmd_delete(self, event: events.NewMessage.Event) -> None:
        try:
            chat_id = event.chat_id
            message_id = getattr(event, "message_id", None) or event.id
            if chat_id and message_id:
                await self.client.delete_messages(chat_id, [message_id])
        except Exception as e:
            await self.kernel.handle_error(e, source="delete", event=event)

    @command(
        "open",
        doc_ru="<path> открыть файл",
        doc_en="[path] open file",
    )
    async def cmd_open(self, event: events.NewMessage.Event) -> None:

        try:
            pipe_input = (getattr(event, "pipe_input", None) or "").strip()
            args = self.args_raw(event).strip()
            file_path = args or pipe_input
            piped = getattr(event, "piped", False)

            if not file_path:
                reply = getattr(event, "reply_to_msg_id", None)
                chat_id = getattr(event, "chat_id", None)
                if reply and chat_id and self.client:
                    try:
                        msg = await self.client.get_messages(chat_id, ids=reply)
                    except Exception as e:
                        self.log.warning("[open] get_messages failed: %s", e)
                        msg = None

                    if msg:
                        try:
                            file_attr = getattr(msg, "file", None)
                        except Exception:
                            file_attr = None

                        if file_attr:
                            try:
                                downloaded = await self.client.download_media(msg)
                            except Exception as e:
                                tr = traceback.format_exc(e)
                                self.log.warning(
                                    "[open] download_media failed: %s\n%s", e, tr
                                )
                                downloaded = None

                            if downloaded and os.path.exists(downloaded):
                                try:
                                    with open(
                                        downloaded,
                                        encoding="utf-8",
                                        errors="ignore",
                                    ) as f:
                                        content = f.read()
                                    if piped:
                                        html_text = html.unescape(content)
                                        event.pipe_output = html_text
                                    else:
                                        lines = content.split("\n")
                                        await self.edit(
                                            event,
                                            f"{len(lines)} lines",
                                            parse_mode="html",
                                        )
                                finally:
                                    try:
                                        os.unlink(downloaded)
                                    except OSError:
                                        pass
                                return
                event.pipe_exit_code = 1
                await self.edit(event, self.strings("open_usage"), parse_mode="html")
                return

            if not os.path.isabs(file_path):
                file_path = os.path.join(os.getcwd(), file_path)

            if not os.path.exists(file_path):
                event.pipe_exit_code = 1
                await self.edit(
                    event,
                    self.strings("file_not_found", path=file_path),
                    parse_mode="html",
                )
                return

            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                lines = content.split("\n")
                ext = os.path.splitext(file_path)[1] or "—"
                size = os.path.getsize(file_path)

                if piped:
                    await self.edit(event, content)
                else:
                    info = self.strings(
                        "open_info",
                        path=file_path,
                        lines=len(lines),
                        size=size,
                        ext=ext,
                    )
                    await self.edit(event, info, parse_mode="html")
            except Exception as e:
                tr = traceback.format_exc(e)
                self.log.warning("[open] open file failed: %s\n%s", e, tr)
                event.pipe_exit_code = 1
                await self.edit(
                    event,
                    self.strings("file_error", err=str(e)),
                    parse_mode="html",
                )
        except Exception as e:
            event.pipe_exit_code = 1
            await self.kernel.handle_error(e, source="open", event=event)

    @command(
        "write",
        doc_ru="[-n] <path> [text] записать в файл",
        doc_en="[-n] <path> [text] write to file",
    )
    async def cmd_write(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()
            pipe_input = getattr(event, "pipe_input", None) or ""
            append = False

            if args.startswith("-n "):
                append = True
                parts = args[3:].strip().split(None, 1)
            elif args.startswith("-n"):
                append = True
                parts = args[2:].strip().split(None, 1)
            else:
                parts = args.split(None, 1)

            if not parts:
                await self.edit(event, self.strings("write_usage"), parse_mode="html")
                return

            path = parts[0]
            text = parts[1] if len(parts) > 1 else pipe_input

            if not path or not text:
                await self.edit(event, self.strings("write_usage"), parse_mode="html")
                return

            if not os.path.isabs(path):
                path = os.path.join(os.getcwd(), path)

            try:
                dir_name = os.path.dirname(path)
                if dir_name:
                    os.makedirs(dir_name, exist_ok=True)

                mode = "a" if append else "w"
                with open(path, mode, encoding="utf-8") as f:
                    f.write(text)

                await self.edit(
                    event,
                    self.strings("write_ok", path=path),
                    parse_mode="html",
                )
            except Exception as e:
                event.pipe_exit_code = 1
                await self.edit(
                    event,
                    self.strings("write_error", err=str(e)),
                    parse_mode="html",
                )
        except Exception as e:
            event.pipe_exit_code = 1
            await self.kernel.handle_error(e, source="write", event=event)

    @command(
        "export",
        doc_ru="<n> [text] сохранить в переменную",
        doc_en="<n> [text] save to variable",
    )
    async def cmd_export(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()
            pipe_input = getattr(event, "pipe_input", None) or ""

            if not args and not pipe_input:
                await self.edit(event, self.strings("export_usage"), parse_mode="html")
                return

            if not args:
                await self.edit(event, pipe_input)
                return

            parts = args.split(None, 1)
            name = parts[0]
            value = parts[1] if len(parts) > 1 else pipe_input

            if not value:
                await self.edit(event, self.strings("export_usage"), parse_mode="html")
                return

            if not hasattr(self.kernel, "_pipe_vars"):
                self.kernel._pipe_vars = {}
            self.kernel._pipe_vars[name] = value

            await self.edit(
                event,
                self.strings("exported", name=name),
                parse_mode="html",
            )
        except Exception as e:
            await self.kernel.handle_error(e, source="export", event=event)

    @command(
        "import",
        doc_ru="<n> получить переменную",
        doc_en="<n> get variable",
    )
    async def cmd_import(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()

            if not args:
                await self.edit(event, self.strings("import_usage"), parse_mode="html")
                return

            name = args.split()[0]
            pipe_vars = getattr(self.kernel, "_pipe_vars", {})

            if name not in pipe_vars:
                await self.edit(
                    event,
                    self.strings("var_not_found", name=name),
                    parse_mode="html",
                )
                return

            value = pipe_vars[name]

            if getattr(event, "piped", False):
                await self.edit(event, value)
                return

            await self.edit(event, value, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="import", event=event)

    @command(
        "grep",
        doc_ru="[-l] [-v] [-r] <pattern> [text] искать текст; -v инвертировать, -r использовать regex",
        doc_en="[-l] [-v] [-r] <pattern> [text] search text; -v invert match, -r use regex",
    )
    async def cmd_grep(self, event: events.NewMessage.Event) -> None:
        try:
            pipe_input = getattr(event, "pipe_input", None) or ""
            args = self.args_raw(event).strip()

            show_line_numbers = False
            invert = False
            use_regex = False

            for flag, pat in (
                ("-l", r"(?<!\S)-l(?!\S)"),
                ("-v", r"(?<!\S)-v(?!\S)"),
                ("-r", r"(?<!\S)-r(?!\S)"),
            ):
                if args and re.search(pat, args):
                    if flag == "-l":
                        show_line_numbers = True
                    elif flag == "-v":
                        invert = True
                    elif flag == "-r":
                        use_regex = True
                    args = re.sub(pat, "", args).strip()

            if not args:
                if pipe_input:
                    await self.edit(event, pipe_input)
                    return
                await self.edit(event, self.strings("grep_usage"), parse_mode="html")
                return

            pattern = ""
            inline_text = ""
            if args[0] in ("'", '"'):
                quote = args[0]
                end = args.find(quote, 1)
                if end != -1:
                    pattern = args[1:end]
                    inline_text = args[end + 1 :].strip()
                else:
                    pattern = args[1:].strip()
            else:
                parts = args.split(None, 1)
                pattern = parts[0]
                inline_text = parts[1] if len(parts) > 1 else ""

            text = inline_text or pipe_input

            if not text:
                event.pipe_exit_code = 1
                await self.edit(event, self.strings("grep_usage"), parse_mode="html")
                return

            def _line_matches(line: str) -> bool:
                if use_regex:
                    try:
                        return bool(re.search(pattern, line))
                    except re.error:
                        return pattern in line
                return pattern in line

            lines = text.splitlines()
            matched_lines = [
                (i, line)
                for i, line in enumerate(lines, start=1)
                if _line_matches(line) != invert
            ]

            if show_line_numbers:
                result_lines = [f"{i}: {line}" for i, line in matched_lines]
            else:
                result_lines = [line for _, line in matched_lines]

            result = "\n".join(result_lines)
            if not result_lines:
                event.pipe_exit_code = 1
                result = self.strings("no_match")

            if getattr(event, "piped", False):
                event.pipe_output = str(result)
                return

            if not result_lines:
                await self.edit(event, self.strings("no_match"), parse_mode="html")
                return

            await self.edit(event, result)
        except Exception as e:
            await self.kernel.handle_error(e, source="grep", event=event)

    @command(
        "head",
        doc_ru="[-n] [text] первые N строк",
        doc_en="[-n] [text] first N lines",
    )
    async def cmd_head(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event)
            n = 10

            if args.startswith("-"):
                parts = args.split(None, 1)
                try:
                    n = int(parts[0][1:])
                except ValueError:
                    pass
                text = (
                    parts[1]
                    if len(parts) > 1
                    else getattr(event, "pipe_input", "") or ""
                )
            else:
                text = args or getattr(event, "pipe_input", "") or ""

            if not text:
                await self.edit(event, self.strings("head_usage"), parse_mode="html")
                return

            result = "\n".join(text.splitlines()[:n])

            if getattr(event, "piped", False):
                await self.edit(event, result)
                return

            await self.edit(event, result, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="head", event=event)

    @command(
        "tail",
        doc_ru="[-n] [text] последние N строк",
        doc_en="[-n] [text] last N lines",
    )
    async def cmd_tail(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event)
            n = 10

            if args.startswith("-"):
                parts = args.split(None, 1)
                try:
                    n = int(parts[0][1:])
                except ValueError:
                    pass
                text = (
                    parts[1]
                    if len(parts) > 1
                    else getattr(event, "pipe_input", "") or ""
                )
            else:
                text = args or getattr(event, "pipe_input", "") or ""

            if not text:
                await self.edit(event, self.strings("tail_usage"), parse_mode="html")
                return

            result = "\n".join(text.splitlines()[-n:])

            if getattr(event, "piped", False):
                await self.edit(event, result)
                return

            await self.edit(event, result, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="tail", event=event)

    @command(
        "sed",
        doc_ru="[-r] s/<old>/<new>/[gi] заменить; -r — паттерн как regex (иначе plain-текст)",
        doc_en="[-r] s/<old>/<new>/[gi] replace; -r — treat pattern as regex (default: plain text)",
    )
    async def cmd_sed(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()
            pipe_input = getattr(event, "pipe_input", None) or ""

            use_regex = False
            if args.startswith("-r ") or args == "-r":
                use_regex = True
                args = args[2:].strip()

            if not args:
                await self.edit(
                    event, pipe_input or self.strings("sed_usage"), parse_mode="html"
                )
                return

            m = re.match(r"^s/(.*?)/(.*?)/([gi]*)(.*)$", args, re.DOTALL)
            if not m:
                await self.edit(event, self.strings("sed_usage"), parse_mode="html")
                return

            old = m.group(1)
            new = m.group(2)
            flags = m.group(3)
            inline_text = m.group(4).strip()

            text = inline_text or pipe_input

            if not text or not old:
                await self.edit(event, self.strings("sed_usage"), parse_mode="html")
                return

            re_flags = re.IGNORECASE if "i" in flags else 0
            pattern = old if use_regex else re.escape(old)
            try:
                if "g" in flags:
                    result = re.sub(pattern, new, text, flags=re_flags)
                else:
                    result = re.sub(pattern, new, text, count=1, flags=re_flags)
            except re.error as exc:
                event.pipe_exit_code = 1
                await self.edit(
                    event,
                    self.strings("sed_regex_error", err=str(exc)),
                    parse_mode="html",
                )
                return

            if getattr(event, "piped", False):
                await self.edit(event, result)
                return

            await self.edit(event, result, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="sed", event=event)

    @command(
        "wc",
        doc_ru="[-l|-c|-w] [text] посчитать",
        doc_en="[-l|-c|-w] [text] count",
    )
    async def cmd_wc(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event)
            mode = "l"

            if args.startswith("-"):
                if len(args) > 1 and args[1] in "lcw":
                    mode = args[1]
                    text = args[2:].strip() or getattr(event, "pipe_input", "") or ""
                else:
                    text = args or getattr(event, "pipe_input", "") or ""
            else:
                text = args or getattr(event, "pipe_input", "") or ""

            if not text:
                await self.edit(event, self.strings("wc_usage"), parse_mode="html")
                return

            if mode == "l":
                result = str(len(text.splitlines()))
            elif mode == "w":
                result = str(len(text.split()))
            else:  # "c"
                result = str(len(text))

            if getattr(event, "piped", False):
                await self.edit(event, result)
                return

            await self.edit(event, result, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="wc", event=event)

    # ------------------------------------------------------------------
    # Безопасный вычислитель выражений (замена голому eval)
    # ------------------------------------------------------------------
    _SAFE_OPS: dict = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def _safe_eval(self, node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return self._safe_eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in self._SAFE_OPS:
            left = self._safe_eval(node.left)
            right = self._safe_eval(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                raise ValueError("exponent too large")
            return self._SAFE_OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._SAFE_OPS:
            return self._SAFE_OPS[type(node.op)](self._safe_eval(node.operand))
        raise ValueError(f"unsupported expression: {ast.dump(node)}")

    @command(
        "calc",
        doc_ru="<expr> вычислить (e.g. 9*2, /2, +1)",
        doc_en="<expr> calculate (e.g. 9*2, /2, +1)",
    )
    async def cmd_calc(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()
            pipe_input = getattr(event, "pipe_input", None) or ""

            expr = args
            num: float | None = None
            if pipe_input:
                try:
                    num = float(pipe_input)
                except ValueError:
                    pass

            if not expr:
                if num is not None:
                    await self.edit(event, str(int(num) if num == int(num) else num))
                    return
                await self.edit(event, self.strings("calc_usage"), parse_mode="html")
                return

            result: Any

            # Режим «применить оператор к pipe_input»: /2, +1, *3, -5
            if expr[0] in "+-*/":
                op = expr[0]
                try:
                    val = float(expr[1:])
                except ValueError:
                    await self.edit(
                        event, self.strings("calc_usage"), parse_mode="html"
                    )
                    return

                if num is None:
                    await self.edit(
                        event, self.strings("calc_usage"), parse_mode="html"
                    )
                    return

                ops = {
                    "+": operator.add,
                    "-": operator.sub,
                    "*": operator.mul,
                    "/": operator.truediv,
                }
                if op == "/" and val == 0:
                    await self.edit(
                        event, self.strings("div_by_zero"), parse_mode="html"
                    )
                    return
                result = ops[op](num, val)
            else:
                # Полное выражение — безопасный AST-парсер
                try:
                    tree = ast.parse(expr.replace(" ", ""), mode="eval")
                    result = self._safe_eval(tree)
                except (ValueError, ZeroDivisionError, SyntaxError) as exc:
                    if num is not None:
                        result = num
                    else:
                        await self.edit(
                            event,
                            self.strings("calc_error", err=str(exc)),
                            parse_mode="html",
                        )
                        return

            try:
                if isinstance(result, (int, float)) and result == int(result):
                    result_str = str(int(result))
                else:
                    result_str = str(result)
            except (ValueError, OverflowError):
                result_str = str(result)

            if getattr(event, "piped", False):
                await self.edit(event, result_str)
                return

            await self.edit(event, result_str, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="calc", event=event)

    @command(
        "sleep",
        doc_ru="<N> ждать N секунд",
        doc_en="<N> wait N seconds",
    )
    async def cmd_sleep(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()

            if not args:
                await self.edit(event, self.strings("sleep_usage"), parse_mode="html")
                return

            try:
                seconds = float(args)
            except ValueError:
                await self.edit(event, self.strings("sleep_usage"), parse_mode="html")
                return

            await asyncio.sleep(seconds)
            await self.edit(event, "ok", parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="sleep", event=event)

    @command(
        "sort",
        doc_ru="[-r] [-u] [text] сортировать строки",
        doc_en="[-r] [-u] [text] sort lines",
    )
    async def cmd_sort(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()
            pipe_input = getattr(event, "pipe_input", None) or ""

            reverse = False
            unique = False

            while args.startswith("-"):
                flag, _, args = args.partition(" ")
                args = args.strip()
                if "r" in flag:
                    reverse = True
                if "u" in flag:
                    unique = True

            text = args or pipe_input

            if not text:
                await self.edit(event, self.strings("sort_usage"), parse_mode="html")
                return

            lines = text.splitlines()
            if unique:
                seen: set[str] = set()
                deduped: list[str] = []
                for line in lines:
                    if line not in seen:
                        seen.add(line)
                        deduped.append(line)
                lines = deduped

            lines.sort(reverse=reverse)
            result = "\n".join(lines)

            if getattr(event, "piped", False):
                await self.edit(event, result)
                return

            await self.edit(event, result, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="sort", event=event)

    @command(
        "uniq",
        doc_ru="[-c] [text] убрать дублирующиеся строки",
        doc_en="[-c] [text] remove duplicate lines",
    )
    async def cmd_uniq(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()
            pipe_input = getattr(event, "pipe_input", None) or ""

            count_mode = False
            if args.startswith("-c"):
                count_mode = True
                args = args[2:].strip()

            text = args or pipe_input

            if not text:
                await self.edit(event, self.strings("uniq_usage"), parse_mode="html")
                return

            lines = text.splitlines()

            if count_mode:
                from itertools import groupby

                result_lines: list[str] = []
                for key, group in groupby(lines):
                    n = sum(1 for _ in group)
                    result_lines.append(f"{n} {key}")
                result = "\n".join(result_lines)
            else:
                seen_set: set[str] = set()
                unique_lines: list[str] = []
                for line in lines:
                    if line not in seen_set:
                        seen_set.add(line)
                        unique_lines.append(line)
                result = "\n".join(unique_lines)

            if getattr(event, "piped", False):
                await self.edit(event, result)
                return

            await self.edit(event, result, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="uniq", event=event)

    @command(
        "strip",
        doc_ru="[-e] [text] убрать лишние пробелы/строки",
        doc_en="[-e] [text] strip whitespace and blank lines",
    )
    async def cmd_strip(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()
            pipe_input = getattr(event, "pipe_input", None) or ""

            remove_empty = False
            if args.startswith("-e"):
                remove_empty = True
                args = args[2:].strip()

            text = args or pipe_input

            if not text:
                await self.edit(event, self.strings("strip_usage"), parse_mode="html")
                return

            lines = [line.strip() for line in text.splitlines()]
            if remove_empty:
                lines = [line for line in lines if line]

            result = "\n".join(lines)

            if getattr(event, "piped", False):
                await self.edit(event, result)
                return

            await self.edit(event, result, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="strip", event=event)

    @command(
        "b64",
        doc_ru="[-d] [text] base64 encode/decode",
        doc_en="[-d] [text] base64 encode/decode",
    )
    async def cmd_b64(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()
            pipe_input = getattr(event, "pipe_input", None) or ""

            decode = False
            if args.startswith("-d"):
                decode = True
                args = args[2:].strip()

            text = args or pipe_input

            if not text:
                await self.edit(event, self.strings("b64_usage"), parse_mode="html")
                return

            try:
                if decode:
                    result = base64.b64decode(text.encode()).decode(
                        "utf-8", errors="replace"
                    )
                else:
                    result = base64.b64encode(text.encode()).decode()
            except Exception as e:
                event.pipe_exit_code = 1
                await self.edit(
                    event,
                    self.strings("b64_error", err=str(e)),
                    parse_mode="html",
                )
                return

            if getattr(event, "piped", False):
                await self.edit(event, result)
                return

            await self.edit(event, result, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="b64", event=event)

    @command(
        "if",
        doc_ru="<pattern> [text] пропустить если паттерн найден",
        doc_en="<pattern> [text] pass through if pattern found",
    )
    async def cmd_if(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()
            pipe_input = getattr(event, "pipe_input", None) or ""

            if not args:
                event.pipe_exit_code = 1
                await self.edit(event, self.strings("if_usage"), parse_mode="html")
                return

            pattern = ""
            inline_text = ""

            if args[0] in ("'", '"'):
                quote = args[0]
                end = args.find(quote, 1)
                if end != -1:
                    pattern = args[1:end]
                    inline_text = args[end + 1 :].strip()
                else:
                    pattern = args[1:].strip()
            else:
                parts = args.split(None, 1)
                pattern = parts[0]
                inline_text = parts[1] if len(parts) > 1 else ""

            text = inline_text or pipe_input

            if not text:
                event.pipe_exit_code = 1
                await self.edit(event, self.strings("if_usage"), parse_mode="html")
                return

            try:
                matched = bool(re.search(pattern, text))
            except re.error:
                matched = pattern in text

            if matched:
                if getattr(event, "piped", False):
                    await self.edit(event, text)
                else:
                    await self.edit(event, text, parse_mode="html")
            else:
                event.pipe_exit_code = 1
                await self.edit(event, self.strings("if_no_match"), parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="if", event=event)

    @command(
        "repeat",
        doc_ru="<N> [sep] [text] повторить текст N раз",
        doc_en="<N> [sep] [text] repeat text N times",
    )
    async def cmd_repeat(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()
            pipe_input = getattr(event, "pipe_input", None) or ""

            if not args:
                await self.edit(event, self.strings("repeat_usage"), parse_mode="html")
                return

            parts = args.split(None, 2)
            try:
                n = int(parts[0])
            except ValueError:
                await self.edit(event, self.strings("repeat_usage"), parse_mode="html")
                return

            if n < 1 or n > 100:
                await self.edit(event, self.strings("repeat_range"), parse_mode="html")
                return

            sep = "\n"
            text = ""

            if len(parts) >= 2:
                if parts[1].startswith(("'", '"')):
                    quote = parts[1][0]
                    rest = " ".join(parts[1:])
                    end = rest.find(quote, 1)
                    if end != -1:
                        sep = rest[1:end]
                        text = rest[end + 1 :].strip()
                    else:
                        text = parts[2] if len(parts) > 2 else pipe_input
                else:
                    text = " ".join(parts[1:])

            text = text or pipe_input

            if not text:
                await self.edit(event, self.strings("repeat_usage"), parse_mode="html")
                return

            result = sep.join([text] * n)

            if getattr(event, "piped", False):
                await self.edit(event, result)
                return

            await self.edit(event, result, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="repeat", event=event)

    @command(
        "fwd",
        doc_ru="<N> [delay] переслать сообщение N раз (без автора)",
        doc_en="<N> [delay] forward message N times (without author)",
    )
    async def cmd_fwd(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()
            reply_id = getattr(event, "reply_to_msg_id", None)
            chat_id = event.chat_id

            if not reply_id:
                await self.edit(event, self.strings("fwd_no_reply"), parse_mode="html")
                return

            parts = args.split()
            try:
                n = int(parts[0]) if parts else 1
            except ValueError:
                await self.edit(event, self.strings("fwd_usage"), parse_mode="html")
                return

            try:
                delay = float(parts[1]) if len(parts) > 1 else 0.0
            except ValueError:
                delay = 0.0

            if n < 1 or n > 200:
                await self.edit(event, self.strings("fwd_range"), parse_mode="html")
                return

            try:
                msg = await self.client.get_messages(chat_id, ids=reply_id)
            except Exception as e:
                event.pipe_exit_code = 1
                await self.edit(
                    event,
                    self.strings("fwd_get_error", err=str(e)),
                    parse_mode="html",
                )
                return

            if not msg:
                event.pipe_exit_code = 1
                await self.edit(event, self.strings("fwd_no_msg"), parse_mode="html")
                return

            await self.edit(
                event,
                self.strings("fwd_start", n=n),
                parse_mode="html",
            )

            sent = 0
            for i in range(n):
                try:
                    if msg.media:
                        await self.client.send_file(
                            chat_id,
                            file=msg.media,
                            caption=msg.text or "",
                            parse_mode="html",
                        )
                    else:
                        await self.client.send_message(
                            chat_id,
                            msg.text or "",
                            parse_mode="html",
                        )
                    sent += 1
                except Exception as e:
                    self.log.warning("[fwd] send %d/%d failed: %s", i + 1, n, e)

                if delay > 0 and i < n - 1:
                    await asyncio.sleep(delay)

            await self.edit(
                event,
                self.strings("fwd_done", sent=sent, n=n),
                parse_mode="html",
            )
        except Exception as e:
            await self.kernel.handle_error(e, source="fwd", event=event)

    @command(
        "random",
        doc_ru="[-l] [N [M]] случайное число N..M или случайная строка из текста (-l)",
        doc_en="[-l] [N [M]] random number N..M or random line from text (-l)",
    )
    async def cmd_random(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()
            pipe_input = getattr(event, "pipe_input", None) or ""

            pick_line = False
            if re.search(r"(?<!\S)-l(?!\S)", args):
                pick_line = True
                args = re.sub(r"(?<!\S)-l(?!\S)", "", args).strip()

            if pick_line:
                text = args or pipe_input
                if not text:
                    await self.edit(
                        event, self.strings("random_usage"), parse_mode="html"
                    )
                    return
                lines = [l for l in text.splitlines() if l.strip()]
                if not lines:
                    event.pipe_exit_code = 1
                    await self.edit(event, self.strings("no_match"), parse_mode="html")
                    return
                result = _random.choice(lines)
            else:
                parts = args.split(None, 1)
                try:
                    if not parts or not parts[0]:
                        lo, hi = 0, 100
                    elif len(parts) == 1:
                        lo, hi = 0, int(parts[0])
                    else:
                        lo, hi = int(parts[0]), int(parts[1])
                except ValueError:
                    await self.edit(
                        event, self.strings("random_usage"), parse_mode="html"
                    )
                    return
                if lo > hi:
                    lo, hi = hi, lo
                result = str(_random.randint(lo, hi))

            if getattr(event, "piped", False):
                await self.edit(event, result)
                return
            await self.edit(event, result, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="random", event=event)

    @command(
        "json",
        doc_ru=(
            "[-s[ave]] <key1> [key2 ...] извлечь поля из JSON.\n"
            "Без -s: вывести значения через пробел.\n"
            "С -s: сохранить каждое поле как переменную (для .import / {import key}).\n"
            "Поддерживает вложенность через точку: user.name, items.0\n"
            "Без ключей: pretty-print JSON.\n"
            "Пример: .curl ... | .json -s name ip | .echo name: {import name}\nip: {import ip}"
        ),
        doc_en=(
            "[-s[ave]] <key1> [key2 ...] extract fields from JSON.\n"
            "Without -s: print values separated by space.\n"
            "With -s: save each field as a variable (for .import / {import key}).\n"
            "Supports nested keys via dot: user.name, items.0\n"
            "Without keys: pretty-print JSON.\n"
            "Example: .curl ... | .json -s name ip | .echo name: {import name}\nip: {import ip}"
        ),
    )
    async def cmd_json(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()
            pipe_input = getattr(event, "pipe_input", None) or ""

            save_mode = False
            if re.search(r"(?<!\S)-s(?:ave)?(?!\S)", args):
                save_mode = True
                args = re.sub(r"(?<!\S)-s(?:ave)?(?!\S)", "", args).strip()

            keys = args.split() if args else []
            raw = pipe_input

            # Без ключей — pretty-print
            if not keys:
                if not raw:
                    await self.edit(
                        event, self.strings("json_usage"), parse_mode="html"
                    )
                    return
                try:
                    parsed = json.loads(raw)
                    result = json.dumps(parsed, ensure_ascii=False, indent=2)
                except json.JSONDecodeError as exc:
                    event.pipe_exit_code = 1
                    await self.edit(
                        event,
                        self.strings("json_parse_error", err=str(exc)),
                        parse_mode="html",
                    )
                    return
                if getattr(event, "piped", False):
                    await self.edit(event, result)
                    return
                await self.edit(event, result, parse_mode="html")
                return

            if not raw:
                event.pipe_exit_code = 1
                await self.edit(event, self.strings("json_usage"), parse_mode="html")
                return

            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                event.pipe_exit_code = 1
                await self.edit(
                    event,
                    self.strings("json_parse_error", err=str(exc)),
                    parse_mode="html",
                )
                return

            def _get(obj: Any, dotted_key: str) -> str:
                parts = dotted_key.split(".")
                cur = obj
                for part in parts:
                    if isinstance(cur, dict):
                        if part not in cur:
                            raise KeyError(part)
                        cur = cur[part]
                    elif isinstance(cur, list):
                        try:
                            cur = cur[int(part)]
                        except (ValueError, IndexError) as exc:
                            raise KeyError(part) from exc
                    else:
                        raise KeyError(part)
                if isinstance(cur, (dict, list)):
                    return json.dumps(cur, ensure_ascii=False)
                return str(cur) if cur is not None else ""

            values: dict[str, str] = {}
            missing: list[str] = []
            for key in keys:
                try:
                    values[key] = _get(data, key)
                except KeyError:
                    missing.append(key)
                    values[key] = ""

            if save_mode:
                if not hasattr(self.kernel, "_pipe_vars"):
                    self.kernel._pipe_vars = {}
                for key, val in values.items():
                    var_name = key.split(".")[-1]
                    self.kernel._pipe_vars[var_name] = val

                saved = ", ".join(k.split(".")[-1] for k in keys)
                warn = (
                    ("\n" + self.strings("json_missing", keys=", ".join(missing)))
                    if missing
                    else ""
                )

                if getattr(event, "piped", False):
                    # пропускаем pipe_input дальше нетронутым
                    await self.edit(event, pipe_input)
                    return
                await self.edit(
                    event,
                    self.strings("json_saved", names=saved) + warn,
                    parse_mode="html",
                )
                return

            result_parts = [values[k] for k in keys]
            result = " ".join(result_parts)
            if missing:
                warn = self.strings("json_missing", keys=", ".join(missing))
                result = (result + "\n" + warn).strip() if result else warn

            if getattr(event, "piped", False):
                await self.edit(event, result)
                return
            await self.edit(event, result, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="json", event=event)

    @command(
        "get_reply",
        doc_ru="[что извлечь] получить данные из ответа",
        doc_en="[what to extract] get data from reply",
    )
    async def cmd_reply(self, event: events.NewMessage.Event) -> None:
        """
        Retrieves information from a message that has been replied to.
        Without arguments, returns the full text (or caption).
        Arguments:
            text — message text only
            raw - raw text (without HTML entities)
            id — message ID
            sender — sender ID
            chat — chat ID
            date — message timestamp
            media — True/False, whether there is media
        """
        try:
            args = self.args_raw(event).strip().lower()
            reply_msg = await event.get_reply_message()

            if not reply_msg:
                await self.edit(
                    event, self.strings("reply_not_found"), parse_mode="html"
                )
                return

            if args == "text":
                result = reply_msg.text or reply_msg.caption or ""
            elif args == "raw":
                result = reply_msg.raw_text or ""
            elif args == "id":
                result = str(reply_msg.id)
            elif args == "sender":
                result = str(reply_msg.sender_id) if reply_msg.sender_id else ""
            elif args == "chat":
                result = str(reply_msg.chat_id) if reply_msg.chat_id else ""
            elif args == "date":
                result = str(reply_msg.date.timestamp()) if reply_msg.date else ""
            elif args == "media":
                result = "true" if reply_msg.media else "false"
            else:
                result = reply_msg.text or reply_msg.caption or ""

            if getattr(event, "piped", False):
                await self.edit(event, result)
                return

            await self.edit(event, result, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="reply", event=event)
