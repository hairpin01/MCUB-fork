# author: 123
# version: 1.0.0
# description: Run JavaScript/TypeScript code via node/ts-node

import asyncio
import os
import tempfile

from utils import get_args_raw, escape_html

RUNNERS = {'js': ('node', '.js', 'JavaScript', 'javascript'),
           'ts': ('ts-node', '.ts', 'TypeScript', 'typescript')}


def register(kernel):
    language = kernel.config.get('language', 'en')

    strings = {
        'ru': {
            'no_code':    'Передай код аргументом или ответь на сообщение с кодом.',
            'running':    'Выполняю...',
            'success':    'OK',
            'error':      'Ошибка',
            'no_output':  '(нет вывода)',
            'mode_usage': 'Использование: <code>{p}js mode &lt;js|ts&gt;</code>',
            'mode_set':   'Режим изменён на: <code>{mode}</code>',
            'help': (
                '<b>Запуск JS/TS</b>\n'
                '<code>{p}js &lt;код&gt;</code> — выполнить код\n'
                'Ответь на сообщение с кодом командой <code>{p}js</code>\n'
                '<code>{p}js mode &lt;js|ts&gt;</code> — переключить режим\n'
                '<i>TypeScript требует ts-node: <code>npm i -g ts-node typescript</code></i>'
            ),
        },
        'en': {
            'no_code':    'Provide code as an argument or reply to a message with code.',
            'running':    'Running...',
            'success':    'OK',
            'error':      'Error',
            'no_output':  '(no output)',
            'mode_usage': 'Usage: <code>{p}js mode &lt;js|ts&gt;</code>',
            'mode_set':   'Mode set to: <code>{mode}</code>',
            'help': (
                '<b>JS/TS runner</b>\n'
                '<code>{p}js &lt;code&gt;</code> — run inline code\n'
                'Reply to a message containing code with <code>{p}js</code>\n'
                '<code>{p}js mode &lt;js|ts&gt;</code> — switch between JS and TS\n'
                '<i>TypeScript requires ts-node: <code>npm i -g ts-node typescript</code></i>'
            ),
        },
    }

    s = strings.get(language, strings['en'])
    p = kernel.custom_prefix
    TIMEOUT = 10
    MODULE = 'compile_js'

    async def get_mode():
        mode = await kernel.db_get(MODULE, 'mode')
        return mode if mode in RUNNERS else 'js'

    async def get_code(event):
        raw = get_args_raw(event)
        if raw:
            return raw
        reply = await event.get_reply_message()
        if reply and reply.text:
            return reply.text
        return None

    async def run_js(code, mode):
        runner, ext, _, _ = RUNNERS[mode]
        with tempfile.NamedTemporaryFile(suffix=ext, mode='w',
                                         delete=False, encoding='utf-8') as f:
            f.write(code)
            path = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                runner, path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
            return proc.returncode, stdout.decode(), stderr.decode()
        except FileNotFoundError:
            return -1, '', f'{runner}: not found. Install Node.js / ts-node.'
        except asyncio.TimeoutError:
            proc.kill()
            return -1, '', f'Timeout ({TIMEOUT}s)'
        finally:
            os.unlink(path)

    def build_output(code, mode, returncode, stdout, stderr):
        _, _, label, lang_id = RUNNERS[mode]
        status = s['success'] if returncode == 0 else s['error']
        out = (stdout or stderr or s['no_output']).strip()
        return (
            f'<b>{label}</b> — <b>{escape_html(status)}</b>\n'
            f'<pre language="{lang_id}">{escape_html(code[:300])}</pre>\n'
            f'<pre>{escape_html(out[:2000])}</pre>'
        )

    @kernel.register.command('js', alias=['ts', 'node'])
    async def js_handler(event):
        try:
            raw = get_args_raw(event)

            if raw:
                parts = raw.split()

                if parts[0] == 'help':
                    await event.edit(s['help'].format(p=p), parse_mode='html')
                    return

                if parts[0] == 'mode':
                    if len(parts) < 2 or parts[1] not in RUNNERS:
                        await event.edit(s['mode_usage'].format(p=p), parse_mode='html')
                        return
                    await kernel.db_set(MODULE, 'mode', parts[1])
                    await event.edit(s['mode_set'].format(mode=parts[1]), parse_mode='html')
                    return

            code = await get_code(event)
            if not code:
                await event.edit(s['no_code'], parse_mode='html')
                return

            mode = await get_mode()
            await event.edit(s['running'], parse_mode='html')
            rc, stdout, stderr = await run_js(code, mode)
            await event.edit(build_output(code, mode, rc, stdout, stderr), parse_mode='html')

        except Exception as e:
            await kernel.handle_error(e, source='compile_js:js_handler', event=event)
