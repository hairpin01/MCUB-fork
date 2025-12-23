import asyncio
import os
import time
import json
from telethon import events
from telethon.tl.types import InputMediaWebPage

def register(kernel):
    client = kernel.client

    # Добавляем дефолтные значения в конфиг если их нет
    kernel.config.setdefault('banner_url', None)
    kernel.config.setdefault('quote_media', False)
    kernel.config.setdefault('invert_media', False)

    async def save_config():
        """Сохранить конфиг в файл"""
        with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

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

        banner_url = kernel.config.get('banner_url')
        quote_media = kernel.config.get('quote_media', False)
        invert_media = kernel.config.get('invert_media', False)

        if banner_url:
            # Если есть баннер, удаляем старое сообщение и отправляем новое с баннером
            await msg.delete()

            if quote_media:
                # Создаем InputMediaWebPage для цитаты медиа
                try:
                    banner = InputMediaWebPage(banner_url, force_large_media=True, force_small_media=False)
                    await event.respond(
                        response,
                        file=banner,
                        parse_mode='html',
                        invert_media=invert_media
                    )
                except:
                    # Fallback - отправляем как обычную ссылку
                    response += f"\n\n🌐 <a href='{banner_url}'>Banner</a>"
                    await event.respond(response, parse_mode='html', link_preview=True)
            else:
                # Отправляем баннер как обычное медиа
                try:
                    await event.respond(
                        response,
                        file=banner_url,
                        parse_mode='html'
                    )
                except:
                    # Если не удалось загрузить баннер, отправляем без него
                    await event.respond(response, parse_mode='html')
        else:
            # Если баннера нет, просто редактируем сообщение
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

    @kernel.register_command('set_banner_url')
    async def set_banner_url_handler(event):
        """Установить URL баннера для команды ping"""
        args = event.text.split()

        if len(args) < 2:
            current = kernel.config.get('banner_url', 'не установлен')
            await event.edit(f'📸 Текущий баннер: {current}\n\n'
                            f'Использование: {kernel.custom_prefix}set_banner_url [url|none]')
            return

        url = args[1].strip()

        if url.lower() == 'none':
            kernel.config['banner_url'] = None
            await save_config()
            await event.edit('✅ Баннер удален')
        elif url.startswith('http://') or url.startswith('https://'):
            kernel.config['banner_url'] = url
            await save_config()
            await event.edit(f'✅ Баннер установлен: {url}')
        else:
            await event.edit('❌ URL должен начинаться с http:// или https://')

    @kernel.register_command('set_quote_media')
    async def set_quote_media_handler(event):
        """Включить/выключить режим цитаты для медиа в ping"""
        args = event.text.split()
        current = kernel.config.get('quote_media', False)

        if len(args) < 2:
            status = 'включен' if current else 'выключен'
            await event.edit(f'🔄 Режим цитаты медиа: {status}\n\n'
                            f'Использование: {kernel.custom_prefix}set_quote_media [on|off|true|false]')
            return

        value = args[1].lower()

        if value in ['on', 'true', '1', 'yes']:
            kernel.config['quote_media'] = True
            await save_config()
            await event.edit('✅ Режим цитаты медиа включен')
        elif value in ['off', 'false', '0', 'no']:
            kernel.config['quote_media'] = False
            await save_config()
            await event.edit('✅ Режим цитаты медиа выключен')
        else:
            await event.edit('❌ Используйте: on/off, true/false, yes/no')

    @kernel.register_command('set_invert_media')
    async def set_invert_media_handler(event):
        """Включить/выключить инвертирование медиа в ping"""
        args = event.text.split()
        current = kernel.config.get('invert_media', False)

        if len(args) < 2:
            status = 'включено' if current else 'выключено'
            await event.edit(f'🔄 Инвертирование медиа: {status}\n\n'
                            f'Использование: {kernel.custom_prefix}set_invert_media [on|off|true|false]')
            return

        value = args[1].lower()

        if value in ['on', 'true', '1', 'yes']:
            kernel.config['invert_media'] = True
            await save_config()
            await event.edit('✅ Инвертирование медиа включено')
        elif value in ['off', 'false', '0', 'no']:
            kernel.config['invert_media'] = False
            await save_config()
            await event.edit('✅ Инвертирование медиа выключено')
        else:
            await event.edit('❌ Используйте: on/off, true/false, yes/no')

    @kernel.register_command('banner_status')
    async def banner_status_handler(event):
        """Показать текущие настройки баннера"""
        banner_url = kernel.config.get('banner_url', 'не установлен')
        quote_media = kernel.config.get('quote_media', False)
        invert_media = kernel.config.get('invert_media', False)

        status_text = f'''📊 <b>Настройки баннера:</b>

<b>URL баннера:</b> <code>{banner_url}</code>
<b>Режим цитаты:</b> {'✅ включен' if quote_media else '❌ выключен'}
<b>Инвертирование:</b> {'✅ включено' if invert_media else '❌ выключено'}
'''

        await event.edit(status_text, parse_mode='html')
