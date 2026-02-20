# requires: telethon>=1.24
# author: @Hairpin00
# version: 1.0.3
# description: Python code execution
import html
import traceback
import sys
import io
import time


CUSTOM_EMOJI = {
    "🧿": '<tg-emoji emoji-id="5426900601101374618">🧿</tg-emoji>',
    "❌": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji>',
    "🧬": '<tg-emoji emoji-id="5368513458469878442">🧬</tg-emoji>',
    "💠": '<tg-emoji emoji-id="5404366668635865453">💠</tg-emoji>',
}


def register(kernel):
    client = kernel.client

    language = kernel.config.get('language', 'en')

    strings = {
        'ru': {
            'code': 'Код',
            'result': 'Результат',
            'executed_in': 'Выполнено за',
            'ms': 'мс',
        },
        'en': {
            'code': 'Code',
            'result': 'Result',
            'executed_in': 'Executed in',
            'ms': 'ms',
        }
    }

    lang_strings = strings.get(language, strings['en'])

    @kernel.register.command("py")
    async def python_exec_handler(event):
        code = event.text[len(kernel.custom_prefix) + 2 :].strip()

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
                f"async def __exec():\n    " + "\n    ".join(code.split("\n")),
                local_vars,
            )
            result = await local_vars["__exec"]()
            complete = output.getvalue()
            if result is not None:
                complete += str(result)
        except Exception as e:
            complete = traceback.format_exc()

        sys.stdout = old_stdout
        sys.stderr = old_stderr

        end_time = time.time()
        elapsed = round((end_time - start_time) * 1000, 2)

        code_display = html.escape(code[:1000]) + ("..." if len(code) > 1000 else "")
        complete_display = html.escape(complete[:2000]) + (
            "..." if len(complete) > 2000 else ""
        )

        response = f"""{CUSTOM_EMOJI['🧿']} <b>{lang_strings['code']}</b>
<blockquote><code>{code_display}</code></blockquote>
{CUSTOM_EMOJI['🧬']} <b>{lang_strings['result']}</b>
<blockquote><code>{complete_display}</code></blockquote>
<blockquote>{CUSTOM_EMOJI['💠']} <i>{lang_strings['executed_in']}</i> <code>{elapsed}{lang_strings['ms']}</code></blockquote>"""
        try:
            await event.edit(response, parse_mode="html")
        except:
            pass
