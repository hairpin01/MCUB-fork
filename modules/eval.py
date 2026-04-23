# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import html
import io
import sys
import time
import traceback
from typing import Any

from telethon import events

import core.lib.loader.module_base as loader
from core.lib.loader.module_base import ModuleBase, command

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
    description = {"ru": "Выполнение Python кода", "en": "Python code execution"}

    strings = {"name": "eval"}

    @command(
        "py",
        doc_ru="<код> выполнить Python код",
        doc_en="<code> execute Python code",
    )
    async def cmd_py(self, event: events.NewMessage.Event) -> None:
        code = html.unescape(self.args_raw(event).strip())
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
            complete = traceback.format_exc()

        sys.stdout = old_stdout
        sys.stderr = old_stderr

        end_time = time.time()
        elapsed = round((end_time - start_time) * 1000, 2)

        code_display = html.escape(code[:1000]) + ("..." if len(code) > 1000 else "")
        result_text = complete if complete else "[no output]"

        if getattr(event, "piped", False):
            await self.edit(event, result_text)
            return

        s = self.strings

        if len(result_text) > 4000:
            result_file = io.BytesIO(result_text.encode("utf-8", errors="replace"))
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
            result_display = html.escape(result_text)
            response = f"""{CUSTOM_EMOJI["🧿"]} <b>{s["code"]}</b>
<blockquote expandable><code>{code_display}</code></blockquote>
{CUSTOM_EMOJI["🧬"]} <b>{s["result_in_message"]}</b>
<blockquote expandable><code>{result_display}</code></blockquote>
<blockquote>{CUSTOM_EMOJI["💠"]} <i>{s["executed_in"]}</i> <code>{elapsed}{s["ms"]}</code></blockquote>"""
            try:
                await self.edit(event, response, as_html=True)
            except Exception:
                pass
