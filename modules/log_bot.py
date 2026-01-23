# author: @Hairpin00
# version: 1.0.1
# description: logs send bot
import os
import time
import subprocess
import asyncio
import json
import html
from datetime import datetime
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
            kernel.cprint(f'{kernel.Colors.YELLOW}⚠️ Токен бота не указан{kernel.Colors.RESET}')
            return False
        try:
            bot_client = TelegramClient('bot_session', kernel.API_ID, kernel.API_HASH)
            await bot_client.start(bot_token=bot_token)
            kernel.cprint(f'{kernel.Colors.GREEN}✅ Бот для логов запущен{kernel.Colors.RESET}')
            kernel.bot_client = bot_client
            return True
        except Exception as e:
            kernel.cprint(f'{kernel.Colors.RED}❌ Ошибка запуска бота: {e}{kernel.Colors.RESET}')
            return False

    async def get_git_commit():
        try:
            result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return 'unknown'

    async def get_update_status():
        try:
            result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
            if result.returncode == 0 and result.stdout.strip():
                pass
            result = subprocess.run(['git', 'fetch', 'origin'], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
            result = subprocess.run(['git', 'log', 'HEAD..origin/main', '--oneline'], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
            if result.returncode == 0 and result.stdout.strip():
                return 'Updates are available'
        except:
            pass
        return 'Current version'

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
                    kernel.cprint(f'{kernel.Colors.GREEN}✅ Найден лог-чат: {dialog.title}{kernel.Colors.RESET}')
                    return True
            kernel.cprint(f'{kernel.Colors.YELLOW}📝 Создаю лог-группу...{kernel.Colors.RESET}')
            me = await client.get_me()
            try:
                result = await client.create_dialog(title=f'MCUB-logs [{me.first_name}]', users=[me])
       # create_dialog is metod does not exist
                kernel.log_chat_id = result.id
                kernel.config['log_chat_id'] = result.id
                try:
                    full_chat = await client.get_entity(result.id)
                    try:
                        invite = await client(ExportChatInviteRequest(result.id))
                        if hasattr(invite, 'link'):
                            kernel.cprint(f'{kernel.Colors.GREEN}✅ Ссылка: {invite.link}{kernel.Colors.RESET}')
                    except:
                        pass
                except Exception as e:
                    kernel.cprint(f'{kernel.Colors.YELLOW}⚠️ Не удалось получить ссылку: {e}{kernel.Colors.RESET}')
                if bot_client and await bot_client.is_user_authorized():
                    try:
                        bot_me = await bot_client.get_me()
                        bot_entity = await client.get_entity(bot_me.id)
                        await client.add_chat_users(result.id, [bot_entity])
                        kernel.cprint(f'{kernel.Colors.GREEN}✅ Бот добавлен{kernel.Colors.RESET}')
                    except Exception as e:
                        kernel.cprint(f'{kernel.Colors.YELLOW}⚠️ Не удалось добавить бота: {e}{kernel.Colors.RESET}')
                with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(kernel.config, f, ensure_ascii=False, indent=2)
                kernel.cprint(f'{kernel.Colors.GREEN}✅ Лог-группа создана: {result.id}{kernel.Colors.RESET}')
                return True
            except Exception as e:
                kernel.cprint(f'{kernel.Colors.RED}❌ Ошибка создания: {e}{kernel.Colors.RESET}')
                return False
        except Exception as e:
            kernel.cprint(f'{kernel.Colors.RED}❌ Ошибка настройки: {e}{kernel.Colors.RESET}')
            return False

    @kernel.register_command('log_setup')
    async def log_setup_handler(event):
        await event.edit('🔄 Настраиваю лог-группу...')
        if await setup_log_chat():
            await event.edit(f'✅ Лог-группа настроена\nID: `{kernel.log_chat_id}`')
        else:
            await event.edit('❌ Не удалось настроить')

    @kernel.register_command('test_log')
    async def test_log_handler(event):
        try:
            await event.edit("🧪 <i>Тестирую отправку логов...</i>", parse_mode='html')
            has_bot = hasattr(kernel, 'bot_client') and kernel.bot_client
            bot_auth = has_bot and await kernel.bot_client.is_user_authorized()
            log_chat = kernel.log_chat_id
            test_info = f"""🔧 <b>Тест отправки логов</b>
<blockquote>🤖 <b>Бот доступен:</b> <mono>{'да' if has_bot else 'нет'}</mono>
🔐 <b>Бот авторизован:</b> <mono>{'да' if bot_auth else 'нет'}</mono>
💬 <b>Лог-чат ID:</b> <mono>{log_chat or 'не установлен'}</mono>
⏰ <b>Время:</b> <mono>{datetime.now().strftime('%H:%M:%S')}</mono></blockquote>
🧬 <i>Если это сообщение видно в лог-чате, значит всё работает</i>"""
            success = await kernel.send_log_message(test_info)
            if success:
                await event.edit("✅ <i>Тестовое сообщение отправлено</i>", parse_mode='html')
            else:
                await event.edit("❌ <i>Не удалось отправить</i>", parse_mode='html')
        except Exception as e:
            await event.edit(f"❌ <i>Ошибка теста:</i> <code>{html.escape(str(e))}</code>", parse_mode='html')


    async def send_startup_message():
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
            if bot_client and await bot_client.is_user_authorized():
                if image_path and os.path.exists(image_path):
                    await bot_client.send_file(kernel.log_chat_id, image_path, caption=message, parse_mode='html')
                else:
                    await bot_client.send_message(kernel.log_chat_id, message, parse_mode='html')
                kernel.cprint(f'{kernel.Colors.GREEN}=> Стартовое сообщение через бота{kernel.Colors.RESET}')
            else:
                if image_path:
                    await client.send_file(kernel.log_chat_id, image_path, caption=message, parse_mode='html')
                else:
                    await client.send_message(kernel.log_chat_id, message, parse_mode='html')
                kernel.cprint(f'{kernel.Colors.YELLOW}=? Стартовое сообщение через юзербота{kernel.Colors.RESET}')
        except Exception as e:
            kernel.cprint(f'{kernel.Colors.RED}=X Ошибка отправки: {e}{kernel.Colors.RESET}')

    async def send_log_message_via_bot(self, text, file=None):
        if not self.log_chat_id:
            return False
        try:
            if hasattr(self, 'bot_client') and self.bot_client and await self.bot_client.is_user_authorized():
                client_to_use = self.bot_client
            else:
                client_to_use = self.client
            if file:
                await client_to_use.send_file(self.log_chat_id, file, caption=text, parse_mode='html')
            else:
                await client_to_use.send_message(self.log_chat_id, text, parse_mode='html')
            return True
        except Exception as e:
            try:
                if client_to_use == self.bot_client:
                    fallback_client = self.client
                else:
                    fallback_client = self.bot_client
                if fallback_client and await fallback_client.is_user_authorized():
                    if file:
                        await fallback_client.send_file(self.log_chat_id, file, caption=text, parse_mode='html')
                    else:
                        await fallback_client.send_message(self.log_chat_id, text, parse_mode='html')
                    return True
            except Exception:
                pass
            self.cprint(f'{self.Colors.RED}❌ Не удалось отправить в лог: {e}{self.Colors.RESET}')
            return False

    async def log_info(text):
        # why
        await send_log_message_via_bot(kernel, f"🧬 {text}")

    async def log_warning(text):
        await send_log_message_via_bot(kernel, f"⚠️ {text}")

    async def log_error(text):
        await send_log_message_via_bot(kernel, f"❌ {text}")

    async def log_network(text):
        await send_log_message_via_bot(kernel, f"✈️ {text}")

    async def log_module(text):
        await send_log_message_via_bot(kernel, f"🧿 {text}")

    kernel.send_log_message = lambda text, file=None: send_log_message_via_bot(kernel, text, file)
    kernel.log_info = log_info
    kernel.log_warning = log_warning
    kernel.log_error = log_error
    kernel.log_network = log_network
    kernel.log_module = log_module
    kernel.bot_client = None
    

    async def initialize():
        await init_bot_client()
        kernel.bot_client = bot_client
        await setup_log_chat()
        await send_startup_message()

    asyncio.create_task(initialize())
