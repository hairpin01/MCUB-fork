# requires: telethon>=1.24
# author: @Hairpin00
# version: 1.0.7
# description: тестированье, ping, logs с премиум эмодзи и поддержкой топиков

import asyncio
import os
import time
import json
import getpass
import socket
from telethon.tl.types import MessageEntityTextUrl, InputMediaWebPage
from telethon import functions, types

# premium emoji dictionary
CUSTOM_EMOJI = {
    '📝': '<tg-emoji emoji-id="5334882760735598374">📝</tg-emoji>',
    '📁': '<tg-emoji emoji-id="5433653135799228968">📁</tg-emoji>',
    '📚': '<tg-emoji emoji-id="5373098009640836781">📚</tg-emoji>',
    '📖': '<tg-emoji emoji-id="5226512880362332956">📖</tg-emoji>',
    '🖨': '<tg-emoji emoji-id="5386494631112353009">🖨</tg-emoji>',
    '☑️': '<tg-emoji emoji-id="5454096630372379732">☑️</tg-emoji>',
    '💬': '<tg-emoji emoji-id="5465300082628763143">💬</tg-emoji>',
    '🗯': '<tg-emoji emoji-id="5465132703458270101">🗯</tg-emoji>',
    '✏️': '<tg-emoji emoji-id="5334673106202010226">✏️</tg-emoji>',
    '🐢': '<tg-emoji emoji-id="5350813992732338949">🐢</tg-emoji>',
    '🧊': '<tg-emoji emoji-id="5404728536810398694">🧊</tg-emoji>',
    '❄️': '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>',
    '📎': '<tg-emoji emoji-id="5377844313575150051">📎</tg-emoji>',
    '🗳': '<tg-emoji emoji-id="5359741159566484212">🗳</tg-emoji>',
    '📰': '<tg-emoji emoji-id="5433982607035474385">📰</tg-emoji>',
}

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
    # ping
    async def ping_handler(event):
        try:
            start_time = time.time()
            msg = await event.edit(CUSTOM_EMOJI['✏️'], parse_mode='html')
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

            response = f"""<blockquote>{CUSTOM_EMOJI['❄️']} <b>ping:</b> {ping_time} ms</blockquote>
<blockquote>{CUSTOM_EMOJI['❄️']} <b>uptime:</b> {uptime}</blockquote>"""

            banner_url = kernel.config.get('ping_banner_url')
            quote_media = kernel.config.get('ping_quote_media', False)
            invert_media = kernel.config.get('ping_invert_media', False)

            if quote_media and banner_url and banner_url.startswith(('http://', 'https://')):
                try:
                    text, entities = await client._parse_message_text(response, 'html')
                    text, entities = add_link_preview(text, entities, banner_url)

                    await msg.delete()

                    # Проверяем, является ли чат супергруппой с топиками
                    chat = await event.get_chat()
                    reply_to = None
                    if hasattr(chat, 'forum') and chat.forum and event.message.reply_to:
                        reply_to = event.message.reply_to.reply_to_top_id or event.message.reply_to.reply_to_msg_id

                    try:
                        if reply_to:
                            await client.send_message(
                                entity=await event.get_input_chat(),
                                message=text,
                                formatting_entities=entities,
                                link_preview=True,
                                invert_media=invert_media,
                                reply_to=reply_to
                            )
                        else:
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
                            if reply_to:
                                await client(functions.messages.SendMessageRequest(
                                    peer=await event.get_input_chat(),
                                    message=text,
                                    entities=entities,
                                    invert_media=invert_media,
                                    no_webpage=False,
                                    reply_to_msg_id=reply_to
                                ))
                            else:
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

                # Проверяем, является ли чат супергруппой с топиками
                chat = await event.get_chat()
                reply_to = None
                if hasattr(chat, 'forum') and chat.forum and event.message.reply_to:
                    reply_to = event.message.reply_to.reply_to_top_id or event.message.reply_to.reply_to_msg_id

                if os.path.exists(banner_url):
                    try:
                        if reply_to:
                            await event.respond(
                                response,
                                file=banner_url,
                                parse_mode='html',
                                reply_to=reply_to
                            )
                        else:
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
                        if reply_to:
                            await event.respond(
                                response,
                                file=banner_url,
                                parse_mode='html',
                                reply_to=reply_to
                            )
                        else:
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
                        if reply_to:
                            await event.respond(
                                text,
                                formatting_entities=entities,
                                parse_mode=None,
                                reply_to=reply_to
                            )
                        else:
                            await event.respond(
                                text,
                                formatting_entities=entities,
                                parse_mode=None
                            )
                    except Exception as e:
                        if reply_to:
                            await event.respond(response, parse_mode='html', reply_to=reply_to)
                        else:
                            await event.respond(response, parse_mode='html')
            else:
                await msg.edit(response, parse_mode='html')

        except Exception as e:
            await event.edit(f"{CUSTOM_EMOJI['❄️']} <b>Ошибка, смотри логи</b>", parse_mode='html')
            await kernel.handle_error(e, source="ping", event=event)

    @kernel.register_command('logs')
    # logs
    async def logs_handler(event):
        try:
            if not os.path.exists(kernel.LOGS_DIR):
                await event.edit(f'{CUSTOM_EMOJI["📁"]} Папка с логами не найдена')
                return

            log_files = sorted([f for f in os.listdir(kernel.LOGS_DIR) if f.endswith('.log')])
            if not log_files:
                await event.edit(f'{CUSTOM_EMOJI["📝"]} Логи отсутствуют')
                return

            latest_log = os.path.join(kernel.LOGS_DIR, log_files[-1])
            await event.edit(f'{CUSTOM_EMOJI["🖨"]} Отправляю логи...')

            # Проверяем, является ли чат супергруппой с топиками
            chat = await event.get_chat()
            reply_to = None
            if hasattr(chat, 'forum') and chat.forum and event.message.reply_to:
                reply_to = event.message.reply_to.reply_to_top_id or event.message.reply_to.reply_to_msg_id

            if reply_to:
                await client.send_file(
                    event.chat_id,
                    latest_log,
                    caption=f'{CUSTOM_EMOJI["📝"]} Логи за {log_files[-1][:-4]}',
                    reply_to=reply_to
                )
            else:
                await client.send_file(
                    event.chat_id,
                    latest_log,
                    caption=f'{CUSTOM_EMOJI["📝"]} Логи за {log_files[-1][:-4]}'
                )
            await event.delete()

        except Exception as e:
            await event.edit(f"{CUSTOM_EMOJI['❄️']} <b>Ошибка, смотри логи</b>", parse_mode='html')
            await kernel.handle_error(e, source="logs", event=event)

    @kernel.register_command('freezing')
    # freezing
    async def freezing_handler(event):
        try:
            args = event.text.split()
            if len(args) < 2:
                await event.edit(f'{CUSTOM_EMOJI["🗯"]} Использование: {kernel.custom_prefix}freezing [секунды]')
                return

            try:
                seconds = int(args[1])
                if seconds <= 0 or seconds > 60:
                    await event.edit(f'{CUSTOM_EMOJI["🗯"]} Укажите от 1 до 60 секунд')
                    return
            except ValueError:
                await event.edit(f'{CUSTOM_EMOJI["🗯"]} Укажите число секунд')
                return

            await event.edit(f'{CUSTOM_EMOJI["🧊"]} Замораживаю на {seconds} секунд...')

            if client.is_connected():
                await client.disconnect()

            await asyncio.sleep(seconds)

            await client.connect()
            await event.edit(f'{CUSTOM_EMOJI["☑️"]} Разморожено после {seconds} секунд')

        except Exception as e:
            await event.edit(f"{CUSTOM_EMOJI['❄️']} <b>Ошибка, смотри логи</b>", parse_mode='html')
            await kernel.handle_error(e, source="freezing", event=event)
