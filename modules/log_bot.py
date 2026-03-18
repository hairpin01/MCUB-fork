# author: @Hairpin00
# version: 1.0.1
# description: logs send bot
import io
import os
import time
import subprocess
import asyncio
import json
import html
import aiohttp
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.tl.functions.messages import CreateChatRequest, ExportChatInviteRequest, AddChatUserRequest
from telethon.tl.functions.channels import EditPhotoRequest
from telethon.tl.types import InputUserSelf
from telethon.tl.types import PeerChat


def register(kernel):
    client = kernel.client
    bot_client = kernel.bot_client

    language = kernel.config.get('language', 'en')

    strings = {
        'ru': {
            'git_timeout': '⚠️ Git: тайм-аут (нет сети)',
            'updates_available': '🔄 Доступны обновления ({count})',
            'up_to_date': '✅ Актуальная версия',
            'git_error': '⚠️ Ошибка Git',
            'setup_log_group': '🤖 Настройка лог-группы',
            'searching_logs': 'Error searching logs',
            'creating_log_group': '📝 Создаю лог-группу...',
            'bot_prepare_error': 'Не удалось подготовить бота для добавления',
            'chat_id_error': '❌ Не удалось получить ID созданного чата',
            'avatar_error': '⚠️ Не удалось установить аватарку',
            'invite_error': '⚠️ Не удалось получить ссылку (возможно нет прав)',
            'bot_added': '✅ Бот добавлен',
            'bot_add_error': '⚠️ Не удалось добавить бота постфактум',
            'chat_create_error': '❌ Ошибка создания чата',
            'log_setup_title': 'Настраиваю лог-группу...',
            'log_setup_success': '✅ Лог-группа настроена',
            'log_setup_fail': '❌ Не удалось настроить',
            'test_title': 'Тестирую отправку логов...',
            'test_bot_available': 'Бот доступен',
            'test_bot_not_available': 'Бот недоступен',
            'test_bot_auth': 'Бот авторизован',
            'test_bot_not_auth': 'Бот не авторизован',
            'test_log_chat_id': 'Лог-чат ID',
            'test_not_set': 'не установлен',
            'test_time': 'Время',
            'test_success': '✅ Тестовое сообщение отправлено',
            'test_fail': '❌ Не удалось отправить',
            'test_error': '❌ Ошибка теста',
            'log_status_on': '✅ включен',
            'log_status_off': '❌ выключен',
            'log_not_configured': 'Не настроен',
            'bot_running': '✅ запущен',
            'bot_not_running': '❌ не запущен',
            'errors_sent': '✅ отправляются',
            'errors_not_sent': '❌ не отправляются',
            'log_status_title': 'Статус лог-бота',
            'log_group': 'Лог-группа',
            'bot_sending': 'Отправка через бота',
            'errors': 'Ошибки',
            'startup_via_bot': '✅ Стартовое сообщение через бота',
            'startup_via_userbot': '⚠️ Стартовое сообщение через юзербота',
            'startup_error': '❌ Ошибка отправки',
            'send_log_error': '❌ Не удалось отправить в лог',
            'started': 'started!',
            'update_status': 'Update status',
            'prefix': 'Prefix',
        },
        'en': {
            'git_timeout': '⚠️ Git: timeout (no network)',
            'updates_available': '🔄 Updates available ({count})',
            'up_to_date': '✅ Up to date',
            'git_error': '⚠️ Git error',
            'setup_log_group': '🤖 Setting up log group',
            'searching_logs': 'Error searching logs',
            'creating_log_group': '📝 Creating log group...',
            'bot_prepare_error': 'Failed to prepare bot for adding',
            'chat_id_error': '❌ Failed to get created chat ID',
            'avatar_error': '⚠️ Failed to set avatar',
            'invite_error': '⚠️ Failed to get invite link (no permissions)',
            'bot_added': '✅ Bot added',
            'bot_add_error': '⚠️ Failed to add bot after creation',
            'chat_create_error': '❌ Chat creation error',
            'log_setup_title': 'Setting up log group...',
            'log_setup_success': '✅ Log group configured',
            'log_setup_fail': '❌ Failed to configure',
            'test_title': 'Testing log sending...',
            'test_bot_available': 'Bot available',
            'test_bot_not_available': 'Bot unavailable',
            'test_bot_auth': 'Bot authorized',
            'test_bot_not_auth': 'Bot not authorized',
            'test_log_chat_id': 'Log chat ID',
            'test_not_set': 'not set',
            'test_time': 'Time',
            'test_success': '✅ Test message sent',
            'test_fail': '❌ Failed to send',
            'test_error': '❌ Test error',
            'log_status_on': '✅ enabled',
            'log_status_off': '❌ disabled',
            'log_not_configured': 'Not configured',
            'bot_running': '✅ running',
            'bot_not_running': '❌ not running',
            'errors_sent': '✅ sent',
            'errors_not_sent': '❌ not sent',
            'log_status_title': 'Log bot status',
            'log_group': 'Log group',
            'bot_sending': 'Sending via bot',
            'errors': 'Errors',
            'startup_via_bot': '✅ Startup message via bot',
            'startup_via_userbot': '⚠️ Startup message via userbot',
            'startup_error': '❌ Send error',
            'send_log_error': '❌ Failed to send to log',
            'started': 'started!',
            'update_status': 'Update status',
            'prefix': 'Prefix',
        }
    }

    lang_strings = strings.get(language, strings['en'])

    async def init_bot_client():
        pass

    async def get_git_commit():
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return "unknown"

    async def get_update_status():
        try:

            repo_path = os.path.dirname(os.path.abspath(__file__))

            async def run_git(args):
                process = await asyncio.create_subprocess_exec(
                    "git",
                    *args,
                    cwd=repo_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await process.communicate()
                return process.returncode, stdout.decode().strip()

            try:
                await asyncio.wait_for(run_git(["fetch", "origin"]), timeout=5)
            except asyncio.TimeoutError:
                return lang_strings['git_timeout']

            code, output = await run_git(["rev-list", "--count", "HEAD..@{u}"])

            if code == 0 and output.isdigit():
                updates_count = int(output)
                if updates_count > 0:
                    return lang_strings['updates_available'].format(count=updates_count)

            return lang_strings['up_to_date']

        except Exception as e:
            kernel.logger.error(f"{lang_strings['git_error']}: {e}")
            return lang_strings['git_error']

    async def setup_log_chat():

        if kernel.config.get("log_chat_id"):
            kernel.log_chat_id = kernel.config["log_chat_id"]
            return True

        kernel.logger.info(
            f"{kernel.Colors.YELLOW}{lang_strings['setup_log_group']}{kernel.Colors.RESET}"
        )

        try:
            async for dialog in kernel.client.iter_dialogs():
                if dialog.title and "MCUB-logs" in dialog.title:
                    kernel.log_chat_id = dialog.id
                    kernel.config["log_chat_id"] = dialog.id
                    with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                        json.dump(kernel.config, f, ensure_ascii=False, indent=2)

                    kernel.cprint(
                        f"{kernel.Colors.GREEN}✅ {dialog.title}{kernel.Colors.RESET}"
                    )
                    return True
        except Exception as e:
            kernel.logger.error(f"{lang_strings['searching_logs']}: {e}")

        kernel.logger.info(
            f"{kernel.Colors.YELLOW}{lang_strings['creating_log_group']}{kernel.Colors.RESET}"
        )

        users_to_invite = [InputUserSelf()]
        bot_entity = None

        if (
            hasattr(kernel, "bot_client")
            and kernel.bot_client
            and await kernel.bot_client.is_user_authorized()
        ):
            try:
                bot_me = await kernel.bot_client.get_me()
                bot_entity = await kernel.client.get_input_entity(bot_me.username)
                users_to_invite.append(bot_entity)
            except Exception as e:
                kernel.logger.warning(
                    f"{lang_strings['bot_prepare_error']}: {e}"
                )

        try:
            me = await kernel.client.get_me()
            created = await kernel.client(
                CreateChatRequest(
                    title=f"MCUB-logs [{me.first_name}]", users=users_to_invite
                )
            )

            chat_id = None
            if hasattr(created, "updates") and created.updates:
                for update in created.updates:
                    if hasattr(update, "participants") and hasattr(
                        update.participants, "chat_id"
                    ):
                        chat_id = update.participants.chat_id
                        break
            kernel.logger.debug(f"chat_id:{chat_id}")

            if not chat_id and hasattr(created, "chats") and created.chats:
                chat_id = created.chats[0].id

            if not chat_id:
                kernel.logger.error(
                    f"{kernel.Colors.RED}{lang_strings['chat_id_error']}{kernel.Colors.RESET}"
                )
                return False

            kernel.log_chat_id = chat_id
            kernel.config["log_chat_id"] = kernel.log_chat_id

            kernel.logger.debug(f"Chat created. ID: {kernel.log_chat_id}")

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://x0.at/QHok.jpg") as resp:
                        if resp.status == 200:
                            photo_data = await resp.read()

                            content_type = resp.headers.get("Content-Type", "image/jpeg")
                            ext_map = {
                                "image/jpeg": "photo.jpg",
                                "image/jpg":  "photo.jpg",
                                "image/png":  "photo.png",
                                "image/webp": "photo.jpg",
                                "image/gif":  "photo.gif",
                            }
                            filename = ext_map.get(content_type.split(";")[0].strip(), "photo.jpg")

                            buf = io.BytesIO(photo_data)
                            buf.name = filename

                            input_file = await kernel.client.upload_file(buf)
                            await kernel.client(EditPhotoRequest(channel=chat_id, photo=input_file))
            except Exception as e:
                kernel.logger.warning(
                    f"{kernel.Colors.YELLOW}{lang_strings['avatar_error']}: {e}{kernel.Colors.RESET}"
                )

            try:
                invite = await kernel.client(
                    ExportChatInviteRequest(kernel.log_chat_id)
                )
                if hasattr(invite, "link"):
                    kernel.logger.info(
                        f"{kernel.Colors.GREEN}✅ {invite.link}{kernel.Colors.RESET}"
                    )
            except Exception as e:
                kernel.logger.warning(
                    f"{kernel.Colors.YELLOW}{lang_strings['invite_error']}: {e}{kernel.Colors.RESET}"
                )

            if bot_entity and len(users_to_invite) == 1:
                try:
                    await kernel.client(
                        AddChatUserRequest(
                            chat_id=kernel.log_chat_id, user_id=bot_entity, fwd_limit=0
                        )
                    )
                    kernel.logger.info(
                        f"{kernel.Colors.GREEN}{lang_strings['bot_added']}{kernel.Colors.RESET}"
                    )
                except Exception as e:
                    kernel.logger.error(
                        f"{kernel.Colors.YELLOW}{lang_strings['bot_add_error']}: {e}{kernel.Colors.RESET}"
                    )

            with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)

            kernel.logger.info(
                f"{kernel.Colors.GREEN}✅ {kernel.log_chat_id}{kernel.Colors.RESET}"
            )
            return True

        except Exception as e:
            kernel.logger.error(
                f"{kernel.Colors.RED}{lang_strings['chat_create_error']}: {e}{kernel.Colors.RESET}"
            )
            import traceback

            traceback.print_exc()
            return False

    @kernel.register.command("log_setup")
    async def log_setup_handler(event):
        await event.edit(lang_strings['log_setup_title'])
        if await setup_log_chat():
            await event.edit(f"{lang_strings['log_setup_success']}\nID: `{kernel.log_chat_id}`")
        else:
            await event.edit(lang_strings['log_setup_fail'])

    @kernel.register.command("test_log")
    async def test_log_handler(event):
        try:
            await event.edit(f"<i>{lang_strings['test_title']}</i>", parse_mode="html")
            has_bot = hasattr(kernel, "bot_client") and kernel.bot_client
            bot_auth = has_bot and await kernel.bot_client.is_user_authorized()
            log_chat = kernel.log_chat_id
            test_info = f"""🔧 <b>{lang_strings['log_status_title']}</b>
<blockquote>🤖 <b>{lang_strings['test_bot_available']}:</b> <mono>{lang_strings['test_bot_available'] if has_bot else lang_strings['test_bot_not_available']}</mono>
🔐 <b>{lang_strings['test_bot_auth']}:</b> <mono>{lang_strings['test_bot_auth'] if bot_auth else lang_strings['test_bot_not_auth']}</mono>
💬 <b>{lang_strings['test_log_chat_id']}:</b> <mono>{log_chat or lang_strings['test_not_set']}</mono>
⏰ <b>{lang_strings['test_time']}:</b> <mono>{datetime.now().strftime('%H:%M:%S')}</mono></blockquote>"""
            success = await kernel.send_log_message(test_info)
            if success:
                await event.edit(
                    f"{lang_strings['test_success']}", parse_mode="html"
                )
            else:
                await event.edit(f"{lang_strings['test_fail']}", parse_mode="html")
        except Exception as e:
            await event.edit(
                f"{lang_strings['test_error']}: <code>{html.escape(str(e))}</code>",
                parse_mode="html",
            )

    @kernel.register.command("log_status")
    async def log_status_handler(event):
        status = lang_strings['log_status_on'] if kernel.log_chat_id else lang_strings['log_status_off']
        chat_info = f"`{kernel.log_chat_id}`" if kernel.log_chat_id else lang_strings['log_not_configured']
        bot_status = lang_strings['bot_running'] if bot_client else lang_strings['bot_not_running']
        msg = f"""📊 <b>{lang_strings['log_status_title']}</b>: {status}
<b>{lang_strings['log_group']}:</b> {chat_info}
<b>{lang_strings['bot_sending']}:</b> {bot_status}
<b>{lang_strings['errors']}:</b> {lang_strings['errors_sent'] if kernel.log_chat_id else lang_strings['errors_not_sent']}"""
        await event.edit(msg, parse_mode="html")

    async def send_startup_message():
        if not kernel.log_chat_id:
            return
        commit_hash = await get_git_commit()
        update_status = await get_update_status()
        image_path = None
        if os.path.exists("userbot.png"):
            image_path = "start_userbot.png"
        elif os.path.exists("img/start_userbot.png"):
            image_path = "img/start_userbot.png"
        elif os.path.exists(kernel.IMG_DIR):
            images = [
                f
                for f in os.listdir(kernel.IMG_DIR)
                if f.lower().endswith((".png", ".jpg", ".jpeg"))
            ]
            if images:
                image_path = os.path.join(kernel.IMG_DIR, images[0])
        message = f"""🧬 <b>MCUB</b> {kernel.VERSION} {lang_strings['started']}
<blockquote><b>🔭 GitHub commit SHA:</b> <code>{commit_hash}</code>
🎩 <b>{lang_strings['update_status']}:</b> <i>{update_status}</i></blockquote>
🧿 <b><i>{lang_strings['prefix']}:</i></b> <code>{kernel.custom_prefix}</code>"""
        try:
            if bot_client and await bot_client.is_user_authorized():
                if image_path and os.path.exists(image_path):
                    await bot_client.send_file(
                        kernel.log_chat_id,
                        image_path,
                        caption=message,
                        parse_mode="html",
                    )
                else:
                    await bot_client.send_message(
                        kernel.log_chat_id, message, parse_mode="html"
                    )
                kernel.cprint(
                    f"{kernel.Colors.GREEN}{lang_strings['startup_via_bot']}{kernel.Colors.RESET}"
                )
            else:
                if image_path:
                    await client.send_file(
                        kernel.log_chat_id,
                        image_path,
                        caption=message,
                        parse_mode="html",
                    )
                else:
                    await client.send_message(
                        kernel.log_chat_id, message, parse_mode="html"
                    )
                kernel.cprint(
                    f"{kernel.Colors.YELLOW}{lang_strings['startup_via_userbot']}{kernel.Colors.RESET}"
                )
        except Exception as e:
            kernel.cprint(
                f"{kernel.Colors.RED}{lang_strings['startup_error']}: {e}{kernel.Colors.RESET}"
            )

    async def send_log_message_via_bot(self, text, file=None):
        if not self.log_chat_id:
            return False
        try:
            if (
                hasattr(self, "bot_client")
                and self.bot_client
                and await self.bot_client.is_user_authorized()
            ):
                client_to_use = self.bot_client
            else:
                client_to_use = self.client
            if file:
                await client_to_use.send_file(
                    self.log_chat_id, file, caption=text, parse_mode="html"
                )
            else:
                await client_to_use.send_message(
                    self.log_chat_id, text, parse_mode="html"
                )
            return True
        except Exception as e:
            try:
                if client_to_use == self.bot_client:
                    fallback_client = self.client
                else:
                    fallback_client = self.bot_client
                if fallback_client and await fallback_client.is_user_authorized():
                    if file:
                        await fallback_client.send_file(
                            self.log_chat_id, file, caption=text, parse_mode="html"
                        )
                    else:
                        await fallback_client.send_message(
                            self.log_chat_id, text, parse_mode="html"
                        )
                    return True
            except Exception:
                pass
            self.cprint(
                f"{self.Colors.RED}{lang_strings['send_log_error']}: {e}{self.Colors.RESET}"
            )
            return False

    async def log_info(text):
        await send_log_message_via_bot(kernel, f"🧬 {text}")

    async def log_warning(text):
        await send_log_message_via_bot(kernel, f"⚠️ {text}")

    async def log_error(text):
        await send_log_message_via_bot(kernel, f"❌ {text}")

    async def log_network(text):
        await send_log_message_via_bot(kernel, f"✈️ {text}")

    async def log_module(text):
        await send_log_message_via_bot(kernel, f"🧿 {text}")

    kernel.send_log_message = lambda text, file=None: send_log_message_via_bot(
        kernel, text, file
    )
    kernel.log_info = log_info
    kernel.log_warning = log_warning
    kernel.log_error = log_error
    kernel.log_network = log_network
    kernel.log_module = log_module

    async def initialize():
        await init_bot_client()
        kernel.bot_client = bot_client
        await setup_log_chat()
        await send_startup_message()

    asyncio.create_task(initialize())
