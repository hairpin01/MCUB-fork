import asyncio
import aiohttp
import json
import re
import getpass
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
        self.kernel.cprint("=- Настройка инлайн-бота", self.kernel.Colors.CYAN)

        choice = input(
            f"{self.kernel.Colors.YELLOW}1. Автоматически создать бота\n2. Ввести токен вручную\nВыберите (1/2): {self.kernel.Colors.RESET}"
        ).strip()

        if choice == "1":
            await self.auto_create_bot()
        elif choice == "2":
            await self.manual_setup()
        else:
            self.kernel.cprint("=X Неверный выбор", self.kernel.Colors.RED)
            return

    async def auto_create_bot(self):
        try:
            botfather = await self.kernel.client.get_entity("BotFather")

            username = input(
                f"{self.kernel.Colors.YELLOW}Желаемый username для бота (без @): {self.kernel.Colors.RESET}"
            ).strip()

            if not username:
                self.kernel.cprint(
                    "=X Username не может быть пустым", self.kernel.Colors.RED
                )
                return

            await self.kernel.client.send_message(botfather, "/newbot")
            await asyncio.sleep(2)

            await self.kernel.client.send_message(botfather, "🪄 MCUB bot")
            await asyncio.sleep(2)

            await self.kernel.client.send_message(botfather, username)
            await asyncio.sleep(3)

            messages = await self.kernel.client.get_messages(botfather, limit=5)

            token = None
            bot_username = None

            for msg in messages:
                if hasattr(msg, "text") and msg.text:
                    text = msg.text

                    token_match = re.search(r"(\d+:[A-Za-z0-9_-]+)", text)
                    if token_match:
                        token = token_match.group(1)

                    username_match_tme = re.search(r"t\.me/([A-Za-z0-9_]+)", text)
                    if username_match_tme:
                        bot_username = username_match_tme.group(1)

                    username_match_at = re.search(r"@([A-Za-z0-9_]+)", text)
                    if username_match_at and not bot_username:
                        bot_username = username_match_at.group(1)

            if not bot_username:
                bot_username = username

            if token and bot_username:
                self.token = token
                self.username = bot_username

                await self.kernel.client.send_message(botfather, "/setdescription")
                await asyncio.sleep(1)
                await self.kernel.client.send_message(botfather, f"@{self.username}")
                await asyncio.sleep(1)
                await self.kernel.client.send_message(
                    botfather,
                    "🌠 I'm a bot from MCUB for inline actions. source code https://github.com/hairpin01/MCUB-fork",
                )
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
                                await asyncio.sleep(2)

                                import os

                                os.unlink(temp_file)
                except Exception as e:
                    self.kernel.cprint(
                        f"=? Не удалось установить аватар: {e}",
                        self.kernel.Colors.YELLOW,
                    )

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
                commands_text = """start - Start the bot
init - Initialize bot (admin only)"""
                await self.kernel.client.send_message(botfather, commands_text)
                await asyncio.sleep(2)

                self.kernel.config["inline_bot_token"] = self.token
                self.kernel.config["inline_bot_username"] = self.username

                with open(self.kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.kernel.config, f, ensure_ascii=False, indent=2)

                self.kernel.cprint(
                    f"=> Инлайн-бот создан: @{self.username}", self.kernel.Colors.GREEN
                )
                self.kernel.cprint(
                    f"=> Токен: {self.token[:10]}...", self.kernel.Colors.CYAN
                )

                await self.start_bot()

            else:
                self.kernel.cprint(
                    "=X Не удалось получить данные бота из ответов BotFather",
                    self.kernel.Colors.RED,
                )
                self.kernel.cprint(
                    "=? Проверьте сообщения от @BotFather вручную",
                    self.kernel.Colors.YELLOW,
                )

        except Exception as e:
            self.kernel.cprint(
                f"=X Ошибка создания бота: {str(e)}", self.kernel.Colors.RED
            )
            import traceback

            traceback.print_exc()

    async def manual_setup(self):
        self.kernel.cprint("=- Ручная настройка бота", self.kernel.Colors.YELLOW)

        token = input(
            f"{self.kernel.Colors.YELLOW}Введите токен бота: {self.kernel.Colors.RESET}"
        ).strip()
        username = input(
            f"{self.kernel.Colors.YELLOW}Введите username бота (без @): {self.kernel.Colors.RESET}"
        ).strip()

        if not token or not username:
            self.kernel.cprint("=X Все поля обязательны", self.kernel.Colors.RED)
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.telegram.org/bot{token}/getMe"
                ) as resp:
                    data = await resp.json()

                    if data.get("ok"):
                        self.token = token
                        self.username = username

                        self.kernel.config["inline_bot_token"] = token
                        self.kernel.config["inline_bot_username"] = username

                        with open(self.kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                            json.dump(
                                self.kernel.config, f, ensure_ascii=False, indent=2
                            )

                        self.kernel.cprint(
                            "=> Бот проверен и сохранен", self.kernel.Colors.GREEN
                        )

                        setup_choice = (
                            input(
                                f"{self.kernel.Colors.YELLOW}Настроить бота через BotFather? (y/n): {self.kernel.Colors.RESET}"
                            )
                            .strip()
                            .lower()
                        )
                        if setup_choice == "y":
                            await self.configure_bot_manually()

                        await self.start_bot()
                    else:
                        self.kernel.cprint(
                            "=X Неверный токен бота", self.kernel.Colors.RED
                        )

        except Exception as e:
            self.kernel.cprint(
                f"=X Ошибка проверки токена: {str(e)}", self.kernel.Colors.RED
            )

    async def configure_bot_manually(self):
        try:
            botfather = await self.kernel.client.get_entity("BotFather")

            await self.kernel.client.send_message(botfather, "/setname")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, f"@{self.username}")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, "🪄 MCUB bot")
            await asyncio.sleep(2)

            await self.kernel.client.send_message(botfather, "/setdescription")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, f"@{self.username}")
            await asyncio.sleep(1)
            await self.kernel.client.send_message(
                botfather,
                "🌠 I'm a bot from MCUB for inline actions. source code https://github.com/hairpin01/MCUB-fork",
            )
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
            await asyncio.sleep(2)

            self.kernel.cprint(
                "=> Бот настроен через BotFather", self.kernel.Colors.GREEN
            )

        except Exception as e:
            self.kernel.cprint(
                f"=X Ошибка настройки бота: {str(e)}", self.kernel.Colors.YELLOW
            )

    async def start_bot(self):
        if not self.token:
            self.kernel.cprint("=X Токен бота не указан", self.kernel.Colors.RED)
            return

        try:
            self.kernel.cprint("=- Запускаю инлайн-бота...", self.kernel.Colors.BLUE)

            self.bot_client = TelegramClient(
                "inline_bot_session",
                self.kernel.API_ID,
                self.kernel.API_HASH,
                timeout=30,
            )

            await self.bot_client.start(bot_token=self.token)

            if not await self.bot_client.is_user_authorized():
                self.kernel.cprint("=X Бот не авторизован", self.kernel.Colors.RED)
                return

            bot_me = await self.bot_client.get_me()
            self.username = bot_me.username

            self.kernel.cprint(
                f"=> Бот авторизован как @{self.username}", self.kernel.Colors.GREEN
            )

            from .handlers import InlineHandlers

            handlers = InlineHandlers(self.kernel, self.bot_client)
            await handlers.register_handlers()

            from .command import setup_bot_commands

            await setup_bot_commands(self.bot_client, self.kernel)

            await self.register_module_commands()

            self.kernel.cprint(
                f"=> Инлайн-бот запущен @{self.username}", self.kernel.Colors.GREEN
            )

            hello_bot = await self.kernel.db_get("kernel", "HELLO_BOT")
            if hello_bot == "True":
                await self.kernel.client.send_message(self.username, "/init")

            asyncio.create_task(self.bot_client.run_until_disconnected())

        except Exception as e:
            self.kernel.cprint(
                f"=X Ошибка запуска инлайн-бота: {str(e)}", self.kernel.Colors.RED
            )
            import traceback

            traceback.print_exc()

    async def register_module_commands(self):
        if not self.bot_client:
            return

        try:
            for cmd, (pattern, handler) in self.kernel.bot_command_handlers.items():

                async def command_wrapper(event, handler=handler, cmd=cmd):
                    try:
                        await handler(event)
                    except Exception as e:
                        await self.kernel.handle_error(
                            e, source=f"bot_command:{cmd}", event=event
                        )

                self.bot_client.add_event_handler(
                    command_wrapper, events.NewMessage(pattern=pattern, incoming=True)
                )
                self.kernel.cprint(
                    f"=> Зарегистрирована команда бота: {pattern}",
                    self.kernel.Colors.CYAN,
                )

            self.kernel.cprint(
                f"=> Всего зарегистрировано команд бота: {len(self.kernel.bot_command_handlers)}",
                self.kernel.Colors.GREEN,
            )

        except Exception as e:
            self.kernel.cprint(
                f"=X Ошибка регистрации команд модулей: {e}", self.kernel.Colors.RED
            )

    async def stop_bot(self):
        if self.bot_client and self.bot_client.is_connected():
            await self.bot_client.disconnect()
            self.kernel.cprint("=> Инлайн-бот остановлен", self.kernel.Colors.YELLOW)
