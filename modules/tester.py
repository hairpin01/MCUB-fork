# author: @Hairpin00
# version: 1.0.4
# description: тестированье, ping, logs...

import asyncio
import os
import time
import json
import getpass
import socket
from telethon.tl.types import MessageEntityTextUrl, InputMediaWebPage
from telethon import functions, types

ZERO_WIDTH_CHAR = "\u2060"

def add_link_preview(text, entities, link):

    if not text or not link:
        return text, entities

    new_text = ZERO_WIDTH_CHAR + text

    new_entities = []

    if entities:
        for entity in entities:
            new_entity = entity
            if hasattr(entity, 'offset'):
                new_entity.offset += 1
            new_entities.append(new_entity)

    link_entity = MessageEntityTextUrl(
        offset=0,
        length=1,
        url=link
    )

    new_entities.append(link_entity)

    return new_text, new_entities

def register(kernel):
    client = kernel.client

    kernel.config.setdefault('ping_quote_media', False)
    kernel.config.setdefault('ping_banner_url', 'https://raw.githubusercontent.com/hairpin01/MCUB-fork/refs/heads/main/img/ping.png')
    kernel.config.setdefault('ping_invert_media', False)

    @kernel.register_command('ping')
    async def ping_handler(event):
        try:
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

            system_user = getpass.getuser()
            hostname = socket.gethostname()

            response = f"""<blockquote>❄️ <b>ping:</b> {ping_time} ms</blockquote>
<blockquote>❄️ <b>uptime:</b> {uptime}</blockquote>"""

            banner_url = kernel.config.get('ping_banner_url')
            quote_media = kernel.config.get('ping_quote_media', False)
            invert_media = kernel.config.get('ping_invert_media', False)


            if quote_media and banner_url and banner_url.startswith(('http://', 'https://')):
                try:

                    text, entities = await client._parse_message_text(response, 'html')

                    text, entities = add_link_preview(text, entities, banner_url)

                    await msg.delete()

                    try:

                        await client.send_message(
                            entity=await event.get_input_chat(),
                            message=text,
                            formatting_entities=entities,
                            link_preview=True,
                            invert_media=invert_media
                        )
                        return
                    except TypeError as e:
                        if "invert_media" in str(e):

                            await client(functions.messages.SendMessageRequest(
                                peer=await event.get_input_chat(),
                                message=text,
                                entities=entities,
                                invert_media=invert_media,
                                no_webpage=False
                            ))
                            return
                        else:
                            raise

                except Exception as e:
                    await kernel.handle_error(e, source="ping:quote_mode", event=event)



            if banner_url:
                await msg.delete()
                banner_sent = False


                if os.path.exists(banner_url):
                    try:
                        await event.respond(
                            response,
                            file=banner_url,
                            parse_mode='html'
                        )
                        banner_sent = True
                    except Exception as e:
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

                    try:
                        text, entities = await client._parse_message_text(response, 'html')
                        text, entities = add_link_preview(text, entities, banner_url)
                        await event.respond(
                            text,
                            formatting_entities=entities,
                            parse_mode=None
                        )
                    except Exception as e:
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
