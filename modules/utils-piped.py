# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import os
import re
from typing import Any
from telethon import events
import html
import traceback

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
        doc_ru="[text] вывести текст",
        doc_en="[text] print text",
    )
    async def cmd_echo(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event)
            pipe_input = getattr(event, "pipe_input", None) or ""
            text = ""

            if args:
                text = args.replace("{pipe_input}", pipe_input)
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
                                        "r",
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
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
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
        doc_ru="[-l] <pattern> [text] искать текст",
        doc_en="[-l] <pattern> [text] search text",
    )
    async def cmd_grep(self, event: events.NewMessage.Event) -> None:
        try:
            pipe_input = getattr(event, "pipe_input", None) or ""
            args = self.args_raw(event).strip()

            show_line_numbers = False
            if args and re.search(r"(?<!\S)-l(?!\S)", args):
                show_line_numbers = True
                args = re.sub(r"(?<!\S)-l(?!\S)", "", args).strip()

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

            lines = text.splitlines()
            if show_line_numbers:
                matches = [
                    f"{i}: {line}"
                    for i, line in enumerate(lines, start=1)
                    if pattern in line
                ]
            else:
                matches = [line for line in lines if pattern in line]

            result = "\n".join(matches)
            if not matches:
                event.pipe_exit_code = 1
                result = self.strings("no_match")

            if getattr(event, "piped", False):
                event.pipe_output = str(result)
                return

            if not result:
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
        doc_ru="s/<old>/<new>/[g] заменить",
        doc_en="s/<old>/<new>/[g] replace",
    )
    async def cmd_sed(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).strip()
            pipe_input = getattr(event, "pipe_input", None) or ""

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
            if "g" in flags:
                result = re.sub(re.escape(old), new, text, flags=re_flags)
            else:
                result = re.sub(re.escape(old), new, text, count=1, flags=re_flags)

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

                if op == "+":
                    result = num + val
                elif op == "-":
                    result = num - val
                elif op == "*":
                    result = num * val
                else:
                    if val == 0:
                        await self.edit(
                            event, self.strings("div_by_zero"), parse_mode="html"
                        )
                        return
                    result = num / val
            else:
                try:
                    result = eval(expr.replace(" ", ""))  # noqa: S307
                except Exception:
                    if num is not None:
                        result = num
                    else:
                        await self.edit(
                            event, self.strings("calc_usage"), parse_mode="html"
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

            import asyncio

            await asyncio.sleep(seconds)
            await self.edit(event, "ok", parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="sleep", event=event)
