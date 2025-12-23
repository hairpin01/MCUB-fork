import os
import time
import subprocess
import asyncio
import json
from telethon import TelegramClient, events, Button
from telethon.tl.functions.messages import CreateChatRequest, ExportChatInviteRequest
from telethon.tl.types import InputUserSelf
from telethon.tl.types import PeerChat

def register(kernel):
    client = kernel.client

    bot_client = None

    async def init_bot_client():
        nonlocal bot_client

        bot_token = kernel.config.get('inline_bot_token')
        if not bot_token:
            kernel.cprint(f'{kernel.Colors.YELLOW}⚠️ Токен бота не указан в конфиге{kernel.Colors.RESET}')
            return False

        try:
            bot_client = TelegramClient('bot_session', kernel.API_ID, kernel.API_HASH)
            await bot_client.start(bot_token=bot_token)
            kernel.cprint(f'{kernel.Colors.GREEN}✅ Бот для логов запущен{kernel.Colors.RESET}')
            return True
        except Exception as e:
            kernel.cprint(f'{kernel.Colors.RED}❌ Ошибка запуска бота: {e}{kernel.Colors.RESET}')
            return False

    async def get_git_commit():
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return 'unknown'

    async def get_update_status():

        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            if result.returncode == 0 and result.stdout.strip():
                return '⚠️ Есть несохранённые изменения'

            result = subprocess.run(
                ['git', 'fetch', 'origin'],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )

            result = subprocess.run(
                ['git', 'log', 'HEAD..origin/main', '--oneline'],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            if result.returncode == 0 and result.stdout.strip():
                return '🔄 Доступны обновления'
        except:
            pass
        return '✅ Актуальная версия'

    async def setup_log_chat():
        if kernel.config.get('log_chat_id'):
            kernel.log_chat_id = kernel.config['log_chat_id']
            return True

        kernel.cprint(f'{kernel.Colors.YELLOW}🤖 Настройка лог-группы{kernel.Colors.RESET}')

        try:
            async for dialog in client.iter_dialogs():
                if dialog.title and 'MCUB-logs' in dialog.title:
                    kernel.log_chat_id = dialog.id
                    kernel.config['log_chat_id'] = dialog.id

                    with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
                        json.dump(kernel.config, f, ensure_ascii=False, indent=2)

                    kernel.cprint(f'{kernel.Colors.GREEN}✅ Найден существующий лог-чат: {dialog.title}{kernel.Colors.RESET}')
                    return True

            kernel.cprint(f'{kernel.Colors.YELLOW}📝 Создаю новую лог-группу...{kernel.Colors.RESET}')

            me = await client.get_me()

            try:
                result = await client.create_dialog(
                    title=f'MCUB-logs [{me.first_name}]',
                    users=[me]
                )

                # Получаем ID созданной группы
                kernel.log_chat_id = result.id
                kernel.config['log_chat_id'] = result.id

                # Получаем пригласительную ссылку
                try:
                    full_chat = await client.get_entity(result.id)
                    # Получаем ссылку
                    try:
                        invite = await client(ExportChatInviteRequest(result.id))
                        if hasattr(invite, 'link'):
                            kernel.cprint(f'{kernel.Colors.GREEN}✅ Ссылка на группу: {invite.link}{kernel.Colors.RESET}')
                    except:
                        try:
                            invite = await client.get_permissions(result.id)
                            kernel.cprint(f'{kernel.Colors.GREEN}✅ Группа создана{kernel.Colors.RESET}')
                        except:
                            pass

                except Exception as e:
                    kernel.cprint(f'{kernel.Colors.YELLOW}⚠️ Не удалось получить ссылку на группу: {e}{kernel.Colors.RESET}')

                if bot_client and await bot_client.is_user_authorized():
                    try:
                        bot_me = await bot_client.get_me()
                        bot_entity = await client.get_entity(bot_me.id)
                        await client.add_chat_users(result.id, [bot_entity])
                        kernel.cprint(f'{kernel.Colors.GREEN}✅ Бот добавлен в группу{kernel.Colors.RESET}')
                    except Exception as e:
                        kernel.cprint(f'{kernel.Colors.YELLOW}⚠️ Не удалось добавить бота в группу: {e}{kernel.Colors.RESET}')

                with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(kernel.config, f, ensure_ascii=False, indent=2)

                kernel.cprint(f'{kernel.Colors.GREEN}✅ Создана лог-группа: {result.id}{kernel.Colors.RESET}')
                return True

            except Exception as e:
                kernel.cprint(f'{kernel.Colors.RED}❌ Ошибка создания группы: {e}{kernel.Colors.RESET}')
                return False

        except Exception as e:
            kernel.cprint(f'{kernel.Colors.RED}❌ Ошибка настройки лог-группы: {e}{kernel.Colors.RESET}')
            return False

    @kernel.register_command('log_setup')
    async def log_setup_handler(event):
        """Ручная настройка лог-группы"""
        await event.edit('🔄 Настраиваю лог-группу...')

        if await setup_log_chat():
            await event.edit(f'✅ Лог-группа настроена\nID: `{kernel.log_chat_id}`')
        else:
            await event.edit('❌ Не удалось настроить лог-группу')

    @kernel.register_command('log_status')
    async def log_status_handler(event):
        """Статус лог-бота"""
        status = '✅ включен' if kernel.log_chat_id else '❌ выключен'
        chat_info = f'`{kernel.log_chat_id}`' if kernel.log_chat_id else 'Не настроен'
        bot_status = '✅ запущен' if bot_client else '❌ не запущен'

        msg = f'''📊 <b>Статус лог-бота:</b> {status}

<b>Лог-группа:</b> {chat_info}
<b>Отправка через бота:</b> {bot_status}
<b>Ошибки:</b> {'✅ отправляются' if kernel.log_chat_id else '❌ не отправляются'}
'''
        await event.edit(msg, parse_mode='html')

    # Функция отправки стартового сообщения
    async def send_startup_message():
        """Отправка сообщения о запуске в лог-группу через бота"""
        if not kernel.log_chat_id:
            return

        commit_hash = await get_git_commit()
        update_status = await get_update_status()

        image_path = None
        if os.path.exists('userbot.png'):
            image_path = 'start_userbot.png'
        elif os.path.exists('img/start_userbot.png'):
            image_path = 'img/start_userbot.png'
        elif os.path.exists(kernel.IMG_DIR):
            images = [f for f in os.listdir(kernel.IMG_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if images:
                image_path = os.path.join(kernel.IMG_DIR, images[0])

        message = f'''🧬 <b>MCUB</b> {kernel.VERSION} started!
 <blockquote><b>🔭 GitHub commit SHA:</b> <code>{commit_hash}</code>
🎩 <b>Update status:</b> <i>{update_status}</i></blockquote>

🧿 <b><i>Prefix:</i></b> <code>{kernel.custom_prefix}</code>'''

        try:
            # Пытаемся отправить через бота
            if bot_client and await bot_client.is_user_authorized():
                if image_path and os.path.exists(image_path):
                    await bot_client.send_file(
                        kernel.log_chat_id,
                        image_path,
                        caption=message,
                        parse_mode='html'
                    )
                else:
                    await bot_client.send_message(
                        kernel.log_chat_id,
                        message,
                        parse_mode='html'
                    )
                kernel.cprint(f'{kernel.Colors.GREEN}✅ Стартовое сообщение отправлено через бота{kernel.Colors.RESET}')
            else:
                # Если бот не доступен, отправляем через юзербота
                if image_path:
                    await client.send_file(
                        kernel.log_chat_id,
                        image_path,
                        caption=message,
                        parse_mode='html'
                    )
                else:
                    await client.send_message(
                        kernel.log_chat_id,
                        message,
                        parse_mode='html'
                    )
                kernel.cprint(f'{kernel.Colors.YELLOW}⚠️ Стартовое сообщение отправлено через юзербота{kernel.Colors.RESET}')
        except Exception as e:
            kernel.cprint(f'{kernel.Colors.RED}❌ Ошибка отправки стартового сообщения: {e}{kernel.Colors.RESET}')

    # Обновляем функцию send_log_message в ядре
    original_send_log_message = kernel.send_log_message

    async def send_log_message_via_bot(text, image_path=None):
        """Отправка сообщения в лог-чат через бота"""
        if not kernel.log_chat_id:
            return False

        try:
            # Пытаемся отправить через бота
            if bot_client and await bot_client.is_user_authorized():
                if image_path and os.path.exists(image_path):
                    await bot_client.send_file(
                        kernel.log_chat_id,
                        image_path,
                        caption=text,
                        parse_mode='html'
                    )
                else:
                    await bot_client.send_message(
                        kernel.log_chat_id,
                        text,
                        parse_mode='html'
                    )
                return True
            else:
                # Если бот не доступен, используем оригинальную функцию
                return await original_send_log_message(text, image_path)
        except Exception as e:
            kernel.cprint(f'{kernel.Colors.RED}❌ Ошибка отправки через бота: {e}{kernel.Colors.RESET}')
            # Пробуем оригинальную функцию
            return await original_send_log_message(text, image_path)

    # Заменяем функцию в ядре
    kernel.send_log_message = send_log_message_via_bot

    # Запускаем инициализацию при загрузке модуля
    async def initialize():
        # Инициализируем бота
        await init_bot_client()
        # Настраиваем лог-чат
        await setup_log_chat()
        # Отправляем стартовое сообщение
        await send_startup_message()

    asyncio.create_task(initialize())
