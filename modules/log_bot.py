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
                return "⚠️ Git: тайм-аут (нет сети)"

            code, output = await run_git(["rev-list", "--count", "HEAD..@{u}"])

            if code == 0 and output.isdigit():
                updates_count = int(output)
                if updates_count > 0:
                    return f"🔄 Доступны обновления ({updates_count})"

            return "✅ Актуальная версия"

        except Exception as e:
            kernel.logger.error(f"Ошибка проверки обновлений: {e}")
            return "⚠️ Ошибка Git"

    async def setup_log_chat():

        if kernel.config.get("log_chat_id"):
            kernel.log_chat_id = kernel.config["log_chat_id"]
            return True

        kernel.logger.info(
            f"{kernel.Colors.YELLOW}🤖 Настройка лог-группы{kernel.Colors.RESET}"
        )

        try:
            async for dialog in kernel.client.iter_dialogs():
                if dialog.title and "MCUB-logs" in dialog.title:
                    kernel.log_chat_id = dialog.id
                    kernel.config["log_chat_id"] = dialog.id
                    # Сохраняем конфиг
                    with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                        json.dump(kernel.config, f, ensure_ascii=False, indent=2)

                    kernel.cprint(
                        f"{kernel.Colors.GREEN}✅ Найден лог-чат: {dialog.title}{kernel.Colors.RESET}"
                    )
                    return True
        except Exception as e:
            kernel.logger.error(f"Error searching logs: {e}")

        kernel.logger.info(
            f"{kernel.Colors.YELLOW}📝 Создаю лог-группу...{kernel.Colors.RESET}"
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
                    f"Не удалось подготовить бота для добавления: {e}"
                )

        try:
            me = await kernel.client.get_me()
            # Создаем чат
            created = await kernel.client(
                CreateChatRequest(
                    title=f"MCUB-logs [{me.first_name}]", users=users_to_invite
                )
            )

            # Ищем ID чата в обновлениях
            chat_id = None
            if hasattr(created, "updates") and created.updates:
                for update in created.updates:
                    if hasattr(update, "participants") and hasattr(
                        update.participants, "chat_id"
                    ):
                        chat_id = update.participants.chat_id
                        break
            kernel.logger.debug(f"chat_id:{chat_id}")

            # Резервный поиск ID
            if not chat_id and hasattr(created, "chats") and created.chats:
                chat_id = created.chats[0].id

            if not chat_id:
                kernel.logger.error(
                    f"{kernel.Colors.RED}❌ Не удалось получить ID созданного чата{kernel.Colors.RESET}"
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
                    f"{kernel.Colors.YELLOW}⚠️ Не удалось установить аватарку: {e}{kernel.Colors.RESET}"
                )

            try:
                invite = await kernel.client(
                    ExportChatInviteRequest(kernel.log_chat_id)
                )
                if hasattr(invite, "link"):
                    kernel.logger.info(
                        f"{kernel.Colors.GREEN}✅ Ссылка: {invite.link}{kernel.Colors.RESET}"
                    )
            except Exception as e:
                kernel.logger.warning(
                    f"{kernel.Colors.YELLOW}⚠️ Не удалось получить ссылку (возможно нет прав): {e}{kernel.Colors.RESET}"
                )

            if bot_entity and len(users_to_invite) == 1:
                try:
                    await kernel.client(
                        AddChatUserRequest(
                            chat_id=kernel.log_chat_id, user_id=bot_entity, fwd_limit=0
                        )
                    )
                    kernel.logger.info(
                        f"{kernel.Colors.GREEN}✅ Бот добавлен{kernel.Colors.RESET}"
                    )
                except Exception as e:
                    kernel.logger.error(
                        f"{kernel.Colors.YELLOW}⚠️ Не удалось добавить бота постфактум: {e}{kernel.Colors.RESET}"
                    )

            with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)

            kernel.logger.info(
                f"{kernel.Colors.GREEN}✅ Лог-группа создана: {kernel.log_chat_id}{kernel.Colors.RESET}"
            )
            return True

        except Exception as e:
            kernel.logger.error(
                f"{kernel.Colors.RED}❌ Ошибка создания чата: {e}{kernel.Colors.RESET}"
            )
            import traceback

            traceback.print_exc()
            return False

    @kernel.register.command("log_setup")
    async def log_setup_handler(event):
        await event.edit("🔄 Настраиваю лог-группу...")
        if await setup_log_chat():
            await event.edit(f"✅ Лог-группа настроена\nID: `{kernel.log_chat_id}`")
        else:
            await event.edit("❌ Не удалось настроить")

    @kernel.register.command("test_log")
    async def test_log_handler(event):
        try:
            await event.edit("🧪 <i>Тестирую отправку логов...</i>", parse_mode="html")
            has_bot = hasattr(kernel, "bot_client") and kernel.bot_client
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
                await event.edit(
                    "✅ <i>Тестовое сообщение отправлено</i>", parse_mode="html"
                )
            else:
                await event.edit("❌ <i>Не удалось отправить</i>", parse_mode="html")
        except Exception as e:
            await event.edit(
                f"❌ <i>Ошибка теста:</i> <code>{html.escape(str(e))}</code>",
                parse_mode="html",
            )

    @kernel.register.command("log_status")
    async def log_status_handler(event):
        status = "✅ включен" if kernel.log_chat_id else "❌ выключен"
        chat_info = f"`{kernel.log_chat_id}`" if kernel.log_chat_id else "Не настроен"
        bot_status = "✅ запущен" if bot_client else "❌ не запущен"
        msg = f"""📊 <b>Статус лог-бота:</b> {status}
<b>Лог-группа:</b> {chat_info}
<b>Отправка через бота:</b> {bot_status}
<b>Ошибки:</b> {'✅ отправляются' if kernel.log_chat_id else '❌ не отправляются'}"""
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
        message = f"""🧬 <b>MCUB</b> {kernel.VERSION} started!
<blockquote><b>🔭 GitHub commit SHA:</b> <code>{commit_hash}</code>
🎩 <b>Update status:</b> <i>{update_status}</i></blockquote>
🧿 <b><i>Prefix:</i></b> <code>{kernel.custom_prefix}</code>"""
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
                    f"{kernel.Colors.GREEN}✅ Стартовое сообщение через бота{kernel.Colors.RESET}"
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
                    f"{kernel.Colors.YELLOW}⚠️ Стартовое сообщение через юзербота{kernel.Colors.RESET}"
                )
        except Exception as e:
            kernel.cprint(
                f"{kernel.Colors.RED}❌ Ошибка отправки: {e}{kernel.Colors.RESET}"
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
                f"{self.Colors.RED}❌ Не удалось отправить в лог: {e}{self.Colors.RESET}"
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
