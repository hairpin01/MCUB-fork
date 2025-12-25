import asyncio
import os
import time
import json
import getpass
import socket
from telethon import events
from telethon.tl.types import InputMediaWebPage

def register(kernel):
    client = kernel.client

    kernel.config.setdefault('ping_initial_emoji', '❄️')
    kernel.config.setdefault('ping_text', '''<blockquote>❄️ <b>ping:</b> {ping_time} ms</blockquote>
<blockquote>❄️ <b>uptime:</b> {uptime}</blockquote>''')
    kernel.config.setdefault('ping_banner_url', None)
    kernel.config.setdefault('ping_quote_media', False)
    kernel.config.setdefault('ping_invert_media', False)

    @kernel.register_command('ping')
    async def ping_handler(event):
        try:
            start_emoji = kernel.config.get('ping_initial_emoji', '❄️')
            start_time = time.time()
            msg = await event.edit(start_emoji)
            end_time = time.time()
            ping_time = round((end_time - start_time) * 1000, 2)

            uptime_seconds = int(time.time() - kernel.start_time)
            hours = uptime_seconds // 3600
            minutes = (uptime_seconds % 3600) // 60
            seconds = uptime_seconds % 60

            if hours > 0:
                uptime = f"{hours}ч {minutes}м {seconds}с"
            elif minutes > 0:
                uptime = f"{minutes}м {seconds}с"
            else:
                uptime = f"{seconds}с"

            system_user = getpass.getuser()
            hostname = socket.gethostname()

            response_text = kernel.config.get('ping_text', '''<blockquote>❄️ <b>ping:</b> {ping_time} ms</blockquote>
<blockquote>❄️ <b>uptime:</b> {uptime}</blockquote>''')

            response = response_text.format(
                ping_time=ping_time,
                uptime=uptime,
                user=system_user,
                hostname=hostname
            )

            banner_url = kernel.config.get('ping_banner_url')
            quote_media = kernel.config.get('ping_quote_media', False)
            invert_media = kernel.config.get('ping_invert_media', False)

            if banner_url:
                await msg.delete()
                banner_sent = False

                if quote_media:
                    try:
                        banner = InputMediaWebPage(banner_url, force_large_media=True, force_small_media=False)
                        await event.respond(
                            response,
                            file=banner,
                            parse_mode='html',
                            invert_media=invert_media
                        )
                        banner_sent = True
                    except Exception as e:
                        try:
                            await event.respond(
                                response,
                                file=banner_url,
                                parse_mode='html'
                            )
                            banner_sent = True
                        except Exception as e2:
                            pass
                else:
                    try:
                        await event.respond(
                            response,
                            file=banner_url,
                            parse_mode='html'
                        )
                        banner_sent = True
                    except Exception as e:
                        pass

                if not banner_sent:
                    response += f"\n<a href='{banner_url}'>⁠⁠⁠⁠</a>"
                    await event.respond(response, parse_mode='html')
            else:
                await msg.edit(response, parse_mode='html')
        except Exception as e:
            await event.edit("🌩️ <b>Ошибка, смотри логи</b>", parse_mode='html')
            await kernel.handle_error(e, source="ping", event=event)

    @kernel.register_command('logs')
    async def logs_handler(event):
        if not os.path.exists(kernel.LOGS_DIR):
            await event.edit('📂 Папка с логами не найдена')
            return

        log_files = sorted([f for f in os.listdir(kernel.LOGS_DIR) if f.endswith('.log')])
        if not log_files:
            await event.edit('📝 Логи отсутствуют')
            return

        latest_log = os.path.join(kernel.LOGS_DIR, log_files[-1])
        await event.edit(f'📤 Отправляю логи...')
        await client.send_file(event.chat_id, latest_log, caption=f'📝 Логи за {log_files[-1][:-4]}')
        await event.delete()

    @kernel.register_command('freezing')
    async def freezing_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}freezing [секунды]')
            return

        try:
            seconds = int(args[1])
            if seconds <= 0 or seconds > 60:
                await event.edit('❌ Укажите от 1 до 60 секунд')
                return
        except ValueError:
            await event.edit('❌ Укажите число секунд')
            return

        await event.edit(f'❄️ Замораживаю на {seconds} секунд...')

        if client.is_connected():
            await client.disconnect()

        await asyncio.sleep(seconds)

        await client.connect()
        await event.edit(f'✅ Разморожено после {seconds} секунд')
