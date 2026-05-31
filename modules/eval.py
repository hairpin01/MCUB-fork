# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations
from utils.strings import Strings

import html
import io
import sys
import time
import traceback
from typing import Any

from telethon import events

import core.lib.loader.module_base as loader
from core.lib.loader.module_base import ModuleBase, command
from core.lib.utils.logger import ErrorFormatter

CUSTOM_EMOJI = {
    "🧿": '<tg-emoji emoji-id="5426900601101374618">🧿</tg-emoji>',
    "❌": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji>',
    "🧬": '<tg-emoji emoji-id="5368513458469878442">🧬</tg-emoji>',
    "💠": '<tg-emoji emoji-id="5404366668635865453">💠</tg-emoji>',
}


class EvalModule(ModuleBase):
    name = "eval"
    version = "1.0.3"
    author = "@hairpin00"
    description = {"ru": "Выпoлнeниe Python кoдa", "en": "Python code execution"}

    strings: dict | Strings = {"name": "eval"}

    @command(
        "py",
        doc_ru="<кoд> выпoлнить Python кoд",
        doc_en="<code> execute Python code",
    )
    async def cmd_py(self, event: events.NewMessage.Event) -> None:
        code = html.unescape(self.args_raw(event).strip()).replace("\u00a0", " ")
        pipe_input = getattr(event, "pipe_input", None) or ""

        if not code and pipe_input:
            code = pipe_input

        start_time = time.time()

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = sys.stderr = output = io.StringIO()

        me = await self.client.get_me()
        m = event
        bot = self.kernel.bot_client
        reply = await m.get_reply_message()
        r_text = html.unescape(self.kernel.raw_text(reply))

        local_vars: dict[str, Any] = {
            "loader": loader,
            "self": self,
            "r_text": r_text,
            "r": reply,
            "c": self.client,
            "m": m,
            "me": me,
            "start_time": start_time,
            "kernel": self.kernel,
            "k": self.kernel,
            "client": self.client,
            "bot": bot,
            "event": event,
            "utils": __import__("utils"),
            "asyncio": __import__("asyncio"),
            "telethon": __import__("telethon"),
            "Button": __import__("telethon").Button,
            "events": __import__("telethon").events,
            "pipe_input": pipe_input,
            "_": pipe_input,
        }

        _tb_raw: str | None = None
        try:
            exec(
                "async def __exec():\n    " + "\n    ".join(code.split("\n")),
                local_vars,
            )
            result = await local_vars["__exec"]()
            complete = output.getvalue()
            if result is not None:
                complete += str(result)
        except Exception:
            _tb_raw = traceback.format_exc()
            _tb_clean = _tb_raw.replace("Traceback (most recent call last):\n", "", 1)
            _tb_lines = [l for l in _tb_clean.split("\n") if l]
            if len(_tb_lines) > 1:
                stack_part = "\n".join(_tb_lines[:-1])
                error_part = _tb_lines[-1]
                complete = ErrorFormatter.format_full_traceback(stack_part) + "\n"
            else:
                error_part = _tb_lines[0] if _tb_lines else "Unknown error"
                complete = ""
            complete += f'{CUSTOM_EMOJI["❌"]} <code>{html.escape(error_part)}</code>'

        sys.stdout = old_stdout
        sys.stderr = old_stderr

        end_time = time.time()
        elapsed = round((end_time - start_time) * 1000, 2)

        code_display = html.escape(code[:1000]) + ("..." if len(code) > 1000 else "")
        result_text = complete if complete else "[no output]"

        if getattr(event, "piped", False):
            await self.edit(event, _tb_raw or result_text)
            return

        s = self.strings

        if len(result_text) > 4000:
            file_content = _tb_raw or result_text
            result_file = io.BytesIO(file_content.encode("utf-8", errors="replace"))
            result_file.name = "eval_result.txt"

            response = f"""{CUSTOM_EMOJI["🧿"]} <b>{s["code"]}</b>
<blockquote expandable><code>{code_display}</code></blockquote>
{CUSTOM_EMOJI["🧬"]} <b>{s["result_file"]}</b>
<blockquote>{CUSTOM_EMOJI["💠"]} <i>{s["executed_in"]}</i> <code>{elapsed}{s["ms"]}</code></blockquote>"""
            try:
                await self.edit(
                    event, response, file=result_file, as_html=True, force_document=True
                )
            except Exception:
                try:
                    result_file.seek(0)
                except Exception:
                    pass
                try:
                    await self.client.send_file(
                        event.chat_id,
                        file=result_file,
                        caption=response,
                        parse_mode="html",
                        reply_to=event.id,
                        force_document=True,
                    )
                except Exception:
                    try:
                        await self.edit(event, response, as_html=True)
                    except Exception:
                        pass
        else:
            if _tb_raw:
                result_block = f"<blockquote expandable>{result_text}</blockquote>"
            else:
                result_block = f"<blockquote expandable><code>{html.escape(result_text)}</code></blockquote>"
            response = f"""{CUSTOM_EMOJI["🧿"]} <b>{s["code"]}</b>
<blockquote expandable><code>{code_display}</code></blockquote>
{CUSTOM_EMOJI["🧬"]} <b>{s["result_in_message"]}</b>
{result_block}
<blockquote>{CUSTOM_EMOJI["💠"]} <i>{s["executed_in"]}</i> <code>{elapsed}{s["ms"]}</code></blockquote>"""
            try:
                await self.edit(event, response, as_html=True)
            except Exception:
                pass
