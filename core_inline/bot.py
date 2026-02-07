import asyncio
import aiohttp
import json
import re
import getpass
import sys
import os
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

    async def create_bot(self):
        self.kernel.logger.info("Настройка инлайн-бота")

        choice = input(
            f"{self.kernel.Colors.YELLOW}1. Автоматически создать бота\n2. Ввести токен вручную\nВыберите (1/2): {self.kernel.Colors.RESET}"
        ).strip()
        await self.kernel.db_set("kernel", "HELLO_BOT", "False")
        if choice == "1":
            await self.auto_create_bot()
        elif choice == "2":
            await self.manual_setup()
        else:
            self.kernel.logger.error("Неверный выбор при создании бота")
            return

    async def auto_create_bot(self):
        try:
            botfather = await self.kernel.client.get_entity("BotFather")

            while True:
                username = input(
                    f"{self.kernel.Colors.YELLOW}Желаемый username для бота (без @): {self.kernel.Colors.RESET}"
                ).strip()

                if not username:
                    self.kernel.logger.error("Пустой username при создании бота")
                    print(f"{self.kernel.Colors.RED}=X Username не может быть пустым{self.kernel.Colors.RESET}")
                    continue

                if not username.endswith(('bot', '_bot', 'Bot', '_Bot')):
                    username += '_bot'
                    self.kernel.logger.info(f"Автоматически добавлен суффикс _bot: {username}")
                    print(f"{self.kernel.Colors.YELLOW}=? Username автоматически изменен на: {username}{self.kernel.Colors.RESET}")

                if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
                    self.kernel.logger.error(f"Некорректный формат username: {username}")
                    continue
                break


            async def wait_for_botfather_response(max_wait=30):
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < max_wait:
                    messages = await self.kernel.client.get_messages(botfather, limit=3)
                    for msg in messages:
                        if hasattr(msg, "text") and msg.text:
                            yield msg
                    await asyncio.sleep(2)

            await self.kernel.client.send_message(botfather, "/newbot")

            await asyncio.sleep(2)

            await self.kernel.client.send_message(botfather, "🪄 MCUB bot")

            await asyncio.sleep(2)

            await self.kernel.client.send_message(botfather, username)


            token = None
            bot_username = None

            async for msg in wait_for_botfather_response(15):
                text = msg.text


                token_match = re.search(r"(\d+:[A-Za-z0-9_-]+)", text)
                if token_match and "token" in text.lower():
                    token = token_match.group(1)
                    self.kernel.logger.debug(f"Найден токен в сообщении BotFather")

                username_match_tme = re.search(r"t\.me/([A-Za-z0-9_]+)", text)
                if username_match_tme:
                    bot_username = username_match_tme.group(1)
                    self.kernel.logger.debug(f"Найден username в t.me ссылке: {bot_username}")

                username_match_at = re.search(r"@([A-Za-z0-9_]+)", text)
                if username_match_at and not bot_username:
                    bot_username = username_match_at.group(1)
                    self.kernel.logger.debug(f"Найден username в @упоминании: {bot_username}")


                if "error" in text.lower() or "invalid" in text.lower():
                    self.kernel.logger.error(f"BotFather вернул ошибку: {text[:100]}")
                    return
            if not bot_username:
                bot_username = username
                self.kernel.logger.info(f"Используем исходный username: {bot_username}")

            if token and bot_username:
                self.token = token
                self.username = bot_username
                self.kernel.logger.info(f"Получен токен для бота @{bot_username}")

                await self.kernel.client.send_message(botfather, "/setdescription")
                await asyncio.sleep(1)
                await self.kernel.client.send_message(botfather, f"@{self.username}")
                await asyncio.sleep(1)
                await self.kernel.client.send_message(
                    botfather,
                    "🌠 I'm a bot from MCUB for inline actions. source code https://github.com/hairpin01/MCUB-fork",
                )
                self.kernel.logger.debug("Установлено описание бота")
                await asyncio.sleep(2)


                await self.kernel.client.send_message(botfather, "/setuserpic")
                await asyncio.sleep(1)
                await self.kernel.client.send_message(botfather, f"@{self.username}")
                await asyncio.sleep(1)

                try:
                    import tempfile

                    async with aiohttp.ClientSession() as session:
                        async with session.get("https://x0.at/4WcE.jpg") as resp:
                            if resp.status == 200:
                                avatar_data = await resp.read()
                                with tempfile.NamedTemporaryFile(
                                    suffix=".jpg", delete=False
                                ) as f:
                                    f.write(avatar_data)
                                    temp_file = f.name

                                await self.kernel.client.send_file(botfather, temp_file)
                                self.kernel.logger.debug("Отправлен аватар бота")
                                await asyncio.sleep(2)

                                import os
                                os.unlink(temp_file)
                except Exception as e:
                    self.kernel.logger.warning(f"Не удалось установить аватар: {e}")

                await self.kernel.client.send_message(botfather, "/setinline")
                await asyncio.sleep(1)
                await self.kernel.client.send_message(botfather, f"@{self.username}")
                await asyncio.sleep(1)
                try:
                    user = getpass.getuser()
                except:
                    user = "user"
                placeholder = f"{user}@MCUB~$ "

                await self.kernel.client.send_message(botfather, placeholder)
                self.kernel.logger.debug(f"Установлен инлайн-плейсхолдер: {placeholder}")
                await asyncio.sleep(2)


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
                self.kernel.logger.debug("Установлены команды бота")
                await asyncio.sleep(2)

                # Сохранение конфигурации
                self.kernel.config["inline_bot_token"] = self.token
                self.kernel.config["inline_bot_username"] = self.username

                with open(self.kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.kernel.config, f, ensure_ascii=False, indent=2)

                self.kernel.logger.info(f"Конфигурация бота сохранена: @{self.username}")
                self.kernel.logger.info("Restart...")

                if self.kernel.client and self.kernel.client.is_connected():
                    await self.kernel.client.disconnect()

                if hasattr(self.kernel, 'bot_client') and self.kernel.bot_client and self.kernel.bot_client.is_connected():
                    await self.kernel.bot_client.disconnect()


                os.execl(sys.executable, sys.executable, *sys.argv)

            else:
                self.kernel.logger.error("Не удалось получить данные бота из ответов BotFather")

        except Exception as e:
            self.kernel.logger.error(f"Ошибка создания бота: {str(e)}", exc_info=True)

    async def manual_setup(self):
        self.kernel.logger.info("Ручная настройка бота")

        while True:
            token = input(
                f"{self.kernel.Colors.YELLOW}Введите токен бота: {self.kernel.Colors.RESET}"
            ).strip()

            if not token:
                self.kernel.logger.error("Пустой токен при ручной настройке")
                continue

            username = input(
                f"{self.kernel.Colors.YELLOW}Введите username бота (без @): {self.kernel.Colors.RESET}"
            ).strip()

            if not username:
                self.kernel.logger.error("Пустой username при ручной настройке")
                continue

            if not username.endswith(('bot', '_bot', 'Bot', '_Bot')):
                self.kernel.logger.warning(f"Username не содержит суффикс bot: {username}")

            if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
                self.kernel.logger.error(f"Некорректный формат username: {username}")
                continue

            break

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.telegram.org/bot{token}/getMe"
                ) as resp:
                    data = await resp.json()

                    if data.get("ok"):
                        bot_info = data.get("result", {})
                        actual_username = bot_info.get("username", "")

                        if actual_username.lower() != username.lower():
                            self.kernel.logger.warning(f"Введенный username ({username}) не совпадает с фактическим ({actual_username})")
                            username = actual_username

                        self.token = token
                        self.username = username

                        self.kernel.config["inline_bot_token"] = token
                        self.kernel.config["inline_bot_username"] = username

                        with open(self.kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                            json.dump(
                                self.kernel.config, f, ensure_ascii=False, indent=2
                            )

                        self.kernel.logger.info(f"Бот проверен и сохранен: @{username}")

                        setup_choice = (
                            input(
                                f"{self.kernel.Colors.YELLOW}Настроить бота через BotFather? (y/n): {self.kernel.Colors.RESET}"
                            )
                            .strip()
                            .lower()
                        )
                        if setup_choice == 'y':
                            await self.configure_bot_manually()

                        await self.start_bot()
                    else:
                        error_desc = data.get("description", "Неизвестная ошибка")
                        self.kernel.logger.error(f"Неверный токен бота: {error_desc}")

        except Exception as e:
            self.kernel.logger.error(f"Ошибка проверки токена: {str(e)}", exc_info=True)

    async def configure_bot_manually(self):
        try:
            self.kernel.logger.info("Настройка бота через BotFather")
            botfather = await self.kernel.client.get_entity("BotFather")

            await self.kernel.client.send_message(botfather, "/setname")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, f"@{self.username}")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, "🪄 MCUB bot")
            self.kernel.logger.debug("Установлено имя бота")
            await asyncio.sleep(2)

            await self.kernel.client.send_message(botfather, "/setdescription")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, f"@{self.username}")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(
                botfather,
                "🌠 I'm a bot from MCUB for inline actions. source code https://github.com/hairpin01/MCUB-fork",
            )
            self.kernel.logger.debug("Установлено описание бота")
            await asyncio.sleep(2)

            await self.kernel.client.send_message(botfather, "/setuserpic")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, f"@{self.username}")
            await asyncio.sleep(1)

            async with aiohttp.ClientSession() as session:
                async with session.get("https://x0.at/4WcE.jpg") as resp:
                    if resp.status == 200:
                        avatar_data = await resp.read()
                        with open("bot_avatar_manual.jpg", "wb") as f:
                            f.write(avatar_data)
                        await self.kernel.client.send_file(
                            botfather, "bot_avatar_manual.jpg"
                        )
                        self.kernel.logger.debug("Установлен аватар бота")
                        import os
                        os.remove("bot_avatar_manual.jpg")
            await asyncio.sleep(2)

            await self.kernel.client.send_message(botfather, "/setinlineplaceholder")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, f"@{self.username}")
            await asyncio.sleep(1)
            try:
                user = getpass.getuser()
            except:
                user = "user"
            placeholder = f"{user}@MCUB~$ "
            await self.kernel.client.send_message(botfather, placeholder)
            self.kernel.logger.debug(f"Установлен инлайн-плейсхолдер: {placeholder}")
            await asyncio.sleep(2)

            self.kernel.logger.info("Бот настроен через BotFather")

        except Exception as e:
            self.kernel.logger.error(f"Ошибка настройки бота: {str(e)}", exc_info=True)

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

            try:
                if not self.bot_client.is_connected():
                    await self.bot_client.connect()

                if not await self.bot_client.is_user_authorized():
                    await self.bot_client.start(bot_token=self.token)

                self.username = (await self.bot_client.get_me()).username

                await self.register_module_commands()

                self.kernel.logger.info(f"=> бот запущен @{self.username}")

            except Exception as e:
                self.kernel.logger.error(f"Ошибка при запуске бота: {e}")



            if not await self.bot_client.is_user_authorized():
                self.kernel.logger.error("Бот не авторизован")
                return

            bot_me = await self.bot_client.get_me()
            self.username = bot_me.username
            self.kernel.config["inline_bot_username"] = self.username


            with open(self.kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.kernel.config, f, ensure_ascii=False, indent=2)


            from .handlers import InlineHandlers

            handlers = InlineHandlers(self.kernel, self.bot_client)
            await handlers.register_handlers()


            await self.register_module_commands()

            self.kernel.logger.info(f"Инлайн-бот запущен @{self.username}")


            # hello_bot = await self.kernel.db_get("kernel", "HELLO_BOT")
            # if hello_bot == "True":
            #     self.kernel.logger.debug("Отправка команды /init боту")
            #     await self.kernel.client.send_message(self.username, "/init")

            asyncio.create_task(self.bot_client.run_until_disconnected())

        except Exception as e:
            self.kernel.logger.error(f"Ошибка запуска инлайн-бота: {str(e)}", exc_info=True)


    async def register_module_commands(self):
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


    async def stop_bot(self):
        if self.bot_client and self.bot_client.is_connected():
            await self.bot_client.disconnect()
            self.kernel.logger.info("Инлайн-бот остановлен")
