from __future__ import annotations

# requires:
# author: @Hairpin00
# version: 1.0.3
# description: Python code execution / Выполнение Python кода
import html
import traceback
import sys
import io
import time
from html import unescape

CUSTOM_EMOJI = {
    "🧿": '<tg-emoji emoji-id="5426900601101374618">🧿</tg-emoji>',
    "❌": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji>',
    "🧬": '<tg-emoji emoji-id="5368513458469878442">🧬</tg-emoji>',
    "💠": '<tg-emoji emoji-id="5404366668635865453">💠</tg-emoji>',
}


def register(kernel):
    client = kernel.client

    language = kernel.config.get("language", "en")

    strings = {
        "ru": {
            "code": "Код",
            "result": "Результат",
            "result_file": "Результат отправлен файлом",
            "result_in_message": "Результат в сообщении",
            "executed_in": "Выполнено за",
            "ms": "мс",
        },
        "en": {
            "code": "Code",
            "result": "Result",
            "result_file": "Result sent as file",
            "result_in_message": "Result in message",
            "executed_in": "Executed in",
            "ms": "ms",
        },
    }

    lang_strings = strings.get(language, strings["en"])

    @kernel.register.command(
        "py",
        doc_en="<code> - execute Python code",
        doc_ru="<код> - выполнить Python код",
    )
    async def python_exec_handler(event):
        code = unescape(event.text[len(kernel.custom_prefix) + 2 :].strip())

        start_time = time.time()

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = sys.stderr = output = io.StringIO()
        me = await client.get_me()
        m = event
        bot = kernel.bot_client
        reply = await m.get_reply_message()
        r_text = html.unescape(kernel.raw_text(reply))

        local_vars = {
            "r_text": r_text,
            "r": reply,
            "c": client,
            "m": m,
            "me": me,
            "start_time": start_time,
            "kernel": kernel,
            "k": kernel,
            "client": client,
            "bot": bot,
            "event": event,
            "utils": __import__("utils"),
            "asyncio": __import__("asyncio"),
            "telethon": __import__("telethon"),
            "Button": __import__("telethon").Button,
            "events": __import__("telethon").events,
        }

        try:
            exec(
                "async def __exec():\n    " + "\n    ".join(code.split("\n")),
                local_vars,
            )  # noqa: S102
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

        if len(result_text) > 4000:
            result_file = io.BytesIO(result_text.encode("utf-8", errors="replace"))
            result_file.name = "eval_result.txt"

            response = f"""{CUSTOM_EMOJI["🧿"]} <b>{lang_strings["code"]}</b>
<blockquote expandable><code>{code_display}</code></blockquote>
{CUSTOM_EMOJI["🧬"]} <b>{lang_strings["result_file"]}</b>
<blockquote>{CUSTOM_EMOJI["💠"]} <i>{lang_strings["executed_in"]}</i> <code>{elapsed}{lang_strings["ms"]}</code></blockquote>"""
            try:
                await event.edit(
                    response,
                    file=result_file,
                    parse_mode="html",
                    force_document=True,
                )
            except Exception:
                try:
                    result_file.seek(0)
                except:
                    pass
                try:
                    await client.send_file(
                        event.chat_id,
                        file=result_file,
                        caption=response,
                        parse_mode="html",
                        reply_to=event.id,
                        force_document=True,
                    )
                except:
                    try:
                        await event.edit(response, parse_mode="html")
                    except:
                        pass
        else:
            result_display = html.escape(result_text)
            response = f"""{CUSTOM_EMOJI["🧿"]} <b>{lang_strings["code"]}</b>
<blockquote expandable><code>{code_display}</code></blockquote>
{CUSTOM_EMOJI["🧬"]} <b>{lang_strings["result_in_message"]}</b>
<blockquote expandable><code>{result_display}</code></blockquote>
<blockquote>{CUSTOM_EMOJI["💠"]} <i>{lang_strings["executed_in"]}</i> <code>{elapsed}{lang_strings["ms"]}</code></blockquote>"""
            try:
                await event.edit(response, parse_mode="html")
            except:
                pass
