import asyncio
import os
import time
from telethon import events

def register(kernel):
    client = kernel.client

    @kernel.register_command('ping')
    async def ping_handler(event):
        start_time = time.time()
        msg = await event.edit('❄️')
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

        response = f"<blockquote>❄️ <b>ping:</b> {ping_time} ms</blockquote>\n"
        response += f"<blockquote>❄️ <b>uptime:</b> {uptime}</blockquote>"

        await msg.edit(response, parse_mode='html')

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
