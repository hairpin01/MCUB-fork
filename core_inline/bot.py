import asyncio
import aiohttp
import json
import re
import sys
import os
import tempfile
import time
from telethon import TelegramClient, Button, events

class InlineBot:
    def __init__(self, kernel):
        self.kernel = kernel
        self.bot_client = None
        self.token = None
        self.username = None

    async def setup(self):
        self.token = self.kernel.config.get("inline_bot_token")
        self.username = self.kernel.config.get("inline_bot_username")

        if not self.token:
            await self.create_bot()
        else:
            await self.start_bot()

    async def stop_bot(self):
        if self.bot_client and self.bot_client.is_connected():
            await self.bot_client.disconnect()
            self.kernel.logger.info("Инлайн-бот остановлен")

    async def create_bot(self):
        """Диалог создания нового бота или ручного ввода токена."""
        self.kernel.logger.info("Настройка инлайн-бота")
        await self.kernel.db_set("kernel", "HELLO_BOT", "False")

        choice = input(
            f"{self.kernel.Colors.YELLOW}1. Автоматически создать бота\n"
            f"2. Ввести токен вручную\n"
            f"Выберите (1/2): {self.kernel.Colors.RESET}"
        ).strip()

        if choice == "1":
            await self._auto_create_bot()
        elif choice == "2":
            await self._manual_setup()
        else:
            self.kernel.logger.error("Неверный выбор при создании бота")

    async def _auto_create_bot(self):
        try:
            botfather = await self.kernel.client.get_entity("BotFather")

            bot_name = "🪄 MCUB bot"
            username = await self._ask_bot_username()

            await self.kernel.client.send_message(botfather, "/newbot")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, bot_name)
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, username)

            token, actual_username = await self._wait_for_bot_token(botfather, username)
            if not token or not actual_username:
                self.kernel.logger.error("Не удалось получить токен от BotFather")
                return

            self.token = token
            self.username = actual_username

            await self._configure_bot_via_botfather(botfather)

            await self._save_config_and_restart()

        except aiohttp.ClientError as e:
            self.kernel.logger.error(f"Сетевая ошибка при создании бота: {e}")
        except asyncio.TimeoutError:
            self.kernel.logger.error("Таймаут при ожидании ответа от BotFather")
        except Exception as e:
            self.kernel.logger.error(f"Неожиданная ошибка: {e}", exc_info=True)

    async def _manual_setup(self):
        self.kernel.logger.info("Ручная настройка бота")

        while True:
            token = input(
                f"{self.kernel.Colors.YELLOW}Введите токен бота: {self.kernel.Colors.RESET}"
            ).strip()
            if not token:
                self.kernel.logger.error("Токен не может быть пустым")
                continue

            username = input(
                f"{self.kernel.Colors.YELLOW}Введите username бота (без @): {self.kernel.Colors.RESET}"
            ).strip()
            if not username:
                self.kernel.logger.error("Username не может быть пустым")
                continue

            if await self._verify_bot_token(token, username):
                break

        self.token = token
        self.username = username

        self.kernel.config["inline_bot_token"] = token
        self.kernel.config["inline_bot_username"] = username
        with open(self.kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.kernel.config, f, ensure_ascii=False, indent=2)

        setup_choice = input(
            f"{self.kernel.Colors.YELLOW}Настроить бота через BotFather? (y/n): {self.kernel.Colors.RESET}"
        ).strip().lower()
        if setup_choice == 'y':
            try:
                botfather = await self.kernel.client.get_entity("BotFather")
                await self._configure_bot_via_botfather(botfather)
            except Exception as e:
                self.kernel.logger.error(f"Ошибка при настройке через BotFather: {e}")

        await self.start_bot()

    async def _ask_bot_username(self) -> str:
        while True:
            username = input(
                f"{self.kernel.Colors.YELLOW}Желаемый username для бота (без @): {self.kernel.Colors.RESET}"
            ).strip()

            if not username:
                self.kernel.logger.error("Username не может быть пустым")
                print(f"{self.kernel.Colors.RED}=X Username не может быть пустым{self.kernel.Colors.RESET}")
                continue

            if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
                self.kernel.logger.error(f"Некорректный формат username: {username}")
                print(f"{self.kernel.Colors.RED}=X Username должен быть 5-32 символа, только латиница, цифры и _ {self.kernel.Colors.RESET}")
                continue

            if not username.lower().endswith('bot'):
                print(f"{self.kernel.Colors.YELLOW}=? Username бота должен оканчиваться на 'bot'. Текущий: {username}{self.kernel.Colors.RESET}")
                confirm = input(f"{self.kernel.Colors.YELLOW}Продолжить с этим username? (y/n): {self.kernel.Colors.RESET}").strip().lower()
                if confirm != 'y':
                    continue
            return username

    async def _wait_for_bot_token(self, botfather, expected_username, timeout=30):
        start = time.monotonic()
        last_msg_id = 0
        token = None
        actual_username = None

        while time.monotonic() - start < timeout:
            messages = await self.kernel.client.get_messages(botfather, limit=5)
            new_messages = [msg for msg in messages if msg.id > last_msg_id]
            for msg in new_messages:
                last_msg_id = max(last_msg_id, msg.id)
                text = msg.text or ""

                token_match = re.search(r"(\d+:[A-Za-z0-9_-]+)", text)
                if token_match and "token" in text.lower():
                    token = token_match.group(1)
                    self.kernel.logger.debug("Найден токен")

                username_match = re.search(r"t\.me/([A-Za-z0-9_]+)", text)
                if username_match:
                    actual_username = username_match.group(1)
                elif not actual_username:
                    username_match_at = re.search(r"@([A-Za-z0-9_]+)", text)
                    if username_match_at:
                        actual_username = username_match_at.group(1)

                if "error" in text.lower() or "invalid" in text.lower():
                    self.kernel.logger.error(f"BotFather вернул ошибку: {text[:200]}")
                    return None, None

                if token and actual_username:
                    return token, actual_username

            await asyncio.sleep(2)

        self.kernel.logger.error("Таймаут ожидания ответа от BotFather")
        return None, None

    async def _verify_bot_token(self, token, expected_username) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.telegram.org/bot{token}/getMe") as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        bot_info = data["result"]
                        actual_username = bot_info["username"]
                        if actual_username.lower() != expected_username.lower():
                            self.kernel.logger.warning(
                                f"Введённый username ({expected_username}) не совпадает с фактическим ({actual_username})"
                            )
                            expected_username = actual_username
                        self.kernel.logger.info(f"Токен валиден, бот @{actual_username}")
                        return True
                    else:
                        error_desc = data.get("description", "Неизвестная ошибка")
                        self.kernel.logger.error(f"Неверный токен: {error_desc}")
                        return False
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
            self.kernel.logger.error(f"Ошибка при проверке токена: {e}")
            return False

    async def _configure_bot_via_botfather(self, botfather):
        try:
            await self.kernel.client.send_message(botfather, "/setdescription")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, f"@{self.username}")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(
                botfather,
                "🌠 I'm a bot from MCUB for inline actions. source code https://github.com/hairpin01/MCUB-fork",
            )
            self.kernel.logger.debug("Описание установлено")
            await asyncio.sleep(2)

            await self.kernel.client.send_message(botfather, "/setuserpic")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, f"@{self.username}")
            await asyncio.sleep(1)
            await self._send_avatar(botfather)
            await asyncio.sleep(2)

            await self.kernel.client.send_message(botfather, "/setinline")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, f"@{self.username}")
            await asyncio.sleep(1)
            placeholder = "mcub@MCUB~$ "
            await self.kernel.client.send_message(botfather, placeholder)
            self.kernel.logger.debug(f"Инлайн-плейсхолдер установлен: {placeholder}")
            await asyncio.sleep(2)

            # Включение инлайн-фидбека
            await self.kernel.client.send_message(botfather, "/setinlinefeedback")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, f"@{self.username}")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, "Enabled")
            await asyncio.sleep(2)

            await self.kernel.client.send_message(botfather, "/setcommands")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, f"@{self.username}")
            await asyncio.sleep(1)
            commands_text = """start - старт
profile - профиль
ping - пинг
delete_mcub_bot - удалить из чата бота
"""
            await self.kernel.client.send_message(botfather, commands_text)
            self.kernel.logger.debug("Команды установлены")
            await asyncio.sleep(2)

        except Exception as e:
            self.kernel.logger.error(f"Ошибка при настройке бота: {e}", exc_info=True)

    async def _send_avatar(self, botfather):
        """Скачивает и отправляет аватар для бота."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://x0.at/4WcE.jpg") as resp:
                    if resp.status == 200:
                        avatar_data = await resp.read()
                        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                            f.write(avatar_data)
                            temp_path = f.name
                        try:
                            await self.kernel.client.send_file(botfather, temp_path)
                            self.kernel.logger.debug("Аватар отправлен")
                        finally:
                            os.unlink(temp_path)
        except Exception as e:
            self.kernel.logger.warning(f"Не удалось установить аватар: {e}")

    async def _save_config_and_restart(self):
        self.kernel.config["inline_bot_token"] = self.token
        self.kernel.config["inline_bot_username"] = self.username

        with open(self.kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.kernel.config, f, ensure_ascii=False, indent=2)

        self.kernel.logger.info(f"Конфигурация бота сохранена: @{self.username}")
        self.kernel.logger.info("Перезапуск...")

        if self.kernel.client and self.kernel.client.is_connected():
            await self.kernel.client.disconnect()

        if hasattr(self.kernel, 'bot_client') and self.kernel.bot_client and self.kernel.bot_client.is_connected():
            await self.kernel.bot_client.disconnect()

        self.kernel.restart()

    async def start_bot(self):
        if not self.token:
            self.kernel.logger.error("Токен бота не указан")
            return

        try:
            self.kernel.logger.info("Запуск инлайн-бота...")
            self.bot_client = TelegramClient(
                "inline_bot_session",
                self.kernel.API_ID,
                self.kernel.API_HASH,
                timeout=30,
            )

            await self.bot_client.connect()
            if not await self.bot_client.is_user_authorized():
                await self.bot_client.start(bot_token=self.token)

            me = await self.bot_client.get_me()
            self.username = me.username
            self.kernel.config["inline_bot_username"] = self.username
            with open(self.kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.kernel.config, f, ensure_ascii=False, indent=2)

            from .handlers import InlineHandlers
            handlers = InlineHandlers(self.kernel, self.bot_client)
            await handlers.register_handlers()

            await self._register_module_commands()

            self.kernel.logger.info(f"Инлайн-бот запущен @{self.username}")
            asyncio.create_task(self.bot_client.run_until_disconnected())

        except aiohttp.ClientError as e:
            self.kernel.logger.error(f"Сетевая ошибка при запуске бота: {e}")
        except Exception as e:
            self.kernel.logger.error(f"Ошибка запуска инлайн-бота: {e}", exc_info=True)

    async def _register_module_commands(self):
        if not self.bot_client:
            self.kernel.logger.warning("bot_client не инициализирован")
            return

        try:
            registered_count = 0
            for cmd, (pattern, handler) in self.kernel.bot_command_handlers.items():
                async def command_wrapper(event, handler=handler, cmd=cmd):
                    try:
                        self.kernel.logger.debug(f"Выполнение бот-команды: {cmd}")
                        await handler(event)
                    except Exception as e:
                        await self.kernel.handle_error(
                            e, source=f"bot_command:{cmd}", event=event
                        )

                self.bot_client.add_event_handler(
                    command_wrapper, events.NewMessage(pattern=pattern)
                )
                self.kernel.logger.debug(f"Зарегистрирована команда бота: {pattern}")
                registered_count += 1

            self.kernel.logger.info(f"Всего зарегистрировано команд бота: {registered_count}")
        except Exception as e:
            self.kernel.logger.error(f"Ошибка регистрации команд модулей: {e}", exc_info=True)
