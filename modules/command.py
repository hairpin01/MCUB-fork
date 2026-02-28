# author: @Hairpin00
# version: 1.2.0
# description: Bot command handlers with localization

import asyncio
from telethon import events, Button


def register(kernel):
    bot_client = getattr(kernel, "bot_client", None)

    if bot_client is None:
        kernel.logger.error(
            "command.py: bot_client is None — inline bot token missing or bot not started yet"
        )
        return

    language = kernel.config.get("language", "en")

    strings = {
        "ru": {
            "hello": "Привет! Я бот от MCUB-fork",
            "developers": "Developers:",
            "fork": "fork:",
            "original": "Original:",
            "github_repo": "Репозиторий",
            "original_mcub": "Оригинальный MCUBFB",
            "support": "Поддержка",
            "profile": "Profile:",
            "name": "Name:",
            "prefix": "Prefix:",
            "kernel_version": "Kernel version:",
            "profile_error": "Не удалось получить информацию о профиле.",
            "goodbye": "Прощайте!",
            "bot_removed": "Бот удален из чата",
            "delete_error": "Не удалось удалить бота из чата.",
            "hello_installed": "Привет, MCUB установлен!",
            "mini_guide": "Мини гайд:",
            "prefix_cmd": "Префикс:",
            "logs": "Логи:",
            "info": "Инфо:",
            "ping": "Пинг:",
            "module_management": "Управление модулями:",
            "load": "Загрузить:",
            "remove": "Удалить:",
            "list_modules": "Список:",
            "choose_language": "Choose a language / Выберите язык",
            "setup_completed": "Настройка завершена!",
            "callback_error": "Ошибка Callback:",
            "pong": "Понг!",
            "start_init_error": "Ошибка start_init:",
            "start_error": "Ошибка /start:",
            "init_error": "Ошибка /init:",
            "backup_setup": "Auto-backup setup / Настройка авто-бэкапа",
            "backup_enable": "Enable auto-backup? / Включить авто-бэкап?",
            "backup_interval": "Select interval: / Выберите интервал:",
            "backup_created": "MCUB-backup group created! / Группа MCUB-backup создана!",
            "backup_skip": "Skip / Пропустить",
            "backup_yes": "Yes / Да",
            "backup_no": "No / Нет",
            "backup_enabled": "Auto-backup enabled / Авто-бэкап включен",
            "backup_disabled": "Auto-backup disabled / Авто-бэкап выключен",
        },
        "en": {
            "hello": "Hello! I am a bot from MCUB-fork",
            "developers": "Developers:",
            "fork": "fork:",
            "original": "Original:",
            "github_repo": "Repository",
            "original_mcub": "Original MCUBFB",
            "support": "Support",
            "profile": "Profile:",
            "name": "Name:",
            "prefix": "Prefix:",
            "kernel_version": "Kernel version:",
            "profile_error": "Failed to get profile information.",
            "goodbye": "Goodbye!",
            "bot_removed": "Bot removed from chat",
            "delete_error": "Failed to remove bot from chat.",
            "hello_installed": "Hello, MCUB installed!",
            "mini_guide": "Mini guide:",
            "main_commands": "Main commands:",
            "prefix_cmd": "Prefix:",
            "logs": "Logs:",
            "info": "Info:",
            "ping": "Ping:",
            "module_management": "Module management:",
            "load": "Load:",
            "remove": "Remove:",
            "list_modules": "List repo modules:",
            "choose_language": "Choose a language / Выберите язык",
            "setup_completed": "Setup completed!",
            "callback_error": "Callback error:",
            "pong": "Pong!",
            "start_init_error": "Error start_init:",
            "start_error": "Error /start:",
            "init_error": "Error /init:",
            "backup_setup": "Auto-backup setup / Настройка авто-бэкапа",
            "backup_enable": "Enable auto-backup? / Включить авто-бэкап?",
            "backup_interval": "Select interval: / Выберите интервал:",
            "backup_created": "MCUB-backup group created! / Группа MCUB-backup создана!",
            "backup_skip": "Skip / Пропустить",
            "backup_yes": "Yes / Да",
            "backup_no": "No / Нет",
            "backup_enabled": "Auto-backup enabled / Авто-бэкап включен",
            "backup_disabled": "Auto-backup disabled / Авто-бэкап выключен",
        },
    }

    lang_strings = strings.get(language, strings["en"])

    def is_private_with_bot(event):
        if event.is_private:
            try:
                return not event.sender.bot
            except Exception:
                return True
        return False

    def private_only(func):
        async def wrapper(event):
            if is_private_with_bot(event):
                await func(event)
            else:
                pass

        return wrapper

    async def start_init(kernel):
        try:
            hello_bot = await kernel.db_get("kernel", "HELLO_BOT")
            username = (await kernel.bot_client.get_me()).username

            if hello_bot != "True":
                start_sms = await kernel.client.send_message(username, "/init")
                kernel.logger.info("Initialization completed via start_init")
                await start_sms.delete()
                await kernel.db_set("kernel", "HELLO_BOT", "True")

        except Exception as e:
            kernel.logger.error(f"{lang_strings['start_init_error']}: {e}")

    @bot_client.on(events.NewMessage(pattern="/start"))
    async def start_handler(event):
        try:
            await event.reply(
                file="https://x0.at/ZXNS.mp4",
                message=(
                    f"<b>{lang_strings['hello']}</b>\n"
                    f"<blockquote>{lang_strings['developers']} \n"
                    f"{lang_strings['fork']} @Hairpin01,\n"
                    f"{lang_strings['original']} @Mitrichq</blockquote>"
                ),
                parse_mode="html",
                buttons=[
                    [
                        Button.url(
                            lang_strings["github_repo"],
                            "https://github.com/hairpin01/MCUB-fork",
                        ),
                        Button.url(
                            lang_strings["original_mcub"],
                            "https://github.com/Mitrichdfklwhcluio/MCUBFB",
                        ),
                    ],
                    [
                        Button.url(
                            lang_strings["support"], "https://t.me/+LVnbdp4DNVE5YTFi"
                        )
                    ],
                ],
            )
        except Exception as e:
            kernel.logger.error(f"{lang_strings['start_error']}: {e}")

    @bot_client.on(events.NewMessage(pattern="/profile"))
    async def profile_handler(event):
        try:
            user = event.sender

            user_id = user.id
            first_name = user.first_name or ""
            last_name = user.last_name or ""

            await event.reply(
                message=(
                    f"<b>{lang_strings['profile']}</b>\n"
                    f"<b>{lang_strings['name']}</b> {first_name} {last_name}\n"
                    f"<b>{lang_strings['prefix']}</b> <code>{kernel.custom_prefix}</code>\n"
                    f"<b>{lang_strings['kernel_version']}</b> {kernel.VERSION}"
                ),
                parse_mode="html",
                buttons=[
                    [
                        Button.url(
                            lang_strings["github_repo"],
                            "https://github.com/hairpin01/MCUB-fork",
                        )
                    ]
                ],
            )
        except Exception as e:
            kernel.logger.error(f"{lang_strings['profile_error']}: {e}")
            await event.reply(lang_strings["profile_error"])

    @bot_client.on(events.NewMessage(pattern=r"/init$"))
    @private_only
    async def init_handler(event):
        try:
            if not hasattr(kernel, "ADMIN_ID") or kernel.ADMIN_ID is None or int(event.sender_id) != int(kernel.ADMIN_ID):
                return

            hello_bot = await kernel.db_get("kernel", "HELLO_BOT")

            await bot_client.send_file(event.chat_id, file="https://x0.at/Y4ie.mp4")

            gif_message = await event.respond(
                message=lang_strings["choose_language"],
                buttons=[
                    [
                        Button.inline("RU", b"start_lang_ru"),
                        Button.inline("EN", b"start_lang_en"),
                    ]
                ],
            )
            try:
                await event.delete()
            except Exception:
                pass
            await kernel.db_set(
                "kernel", f"lang_select_{event.sender_id}", str(gif_message.id)
            )

        except Exception as e:
            kernel.logger.error(f"{lang_strings['init_error']}: {e}")

    @bot_client.on(events.NewMessage(pattern="/delete_mcub_bot"))
    async def delete_bot_handler(event):
        try:
            if not event.is_group and not event.is_channel:
                return

            if not kernel.is_admin:
                return

            await event.reply(
                message=f"<b>{lang_strings['goodbye']}</b>",
                parse_mode="html",
            )

            await bot_client.delete_dialog(event.chat_id)

            kernel.logger.info(
                f"{lang_strings['bot_removed']} {event.chat_id} пользователем {event.sender_id}"
            )

        except Exception as e:
            kernel.logger.error(f"{lang_strings['delete_error']}: {e}")
            await event.reply(f"{lang_strings['delete_error']} {e}")

    @bot_client.on(events.CallbackQuery(pattern=r"start_lang_(ru|en)"))
    async def language_handler(event):
        try:
            lang = (
                event.pattern_match.group(1).decode()
                if isinstance(event.pattern_match.group(1), bytes)
                else event.pattern_match.group(1)
            )
            await kernel.db_set("kernel", "language", lang)
            kernel.config["language"] = lang
            kernel.save_config()

            strings_current = strings.get(lang, strings["en"])

            if lang == "ru":
                text = (
                    f"<b>{strings_current['hello_installed']}</b>\n\n"
                    f"<b>{strings_current['mini_guide']}</b>\n"
                    f"<blockquote>{strings_current['prefix_cmd']} <code>.prefix {{новый префикс}}</code>\n"
                    f"{strings_current['logs']} <code>.logs</code>\n"
                    f"{strings_current['info']} <code>.info</code>\n"
                    f"{strings_current['ping']} <code>.ping</code></blockquote>\n\n"
                    f"<b>{strings_current['module_management']}</b>\n"
                    f"<blockquote>{strings_current['load']} <code>.iload</code>\n"
                    f"{strings_current['remove']} <code>.um [название]</code>\n"
                    f"{strings_current['list_modules']} <code>.man</code></blockquote>\n\n"
                )
            else:
                text = (
                    f"<b>{strings_current['hello_installed']}</b>\n\n"
                    f"<b>{strings_current['main_commands']}</b>\n"
                    f"<blockquote>{strings_current['prefix_cmd']} <code>.prefix {{your prefix}}</code>\n"
                    f"{strings_current['logs']} <code>.logs</code>\n"
                    f"{strings_current['info']} <code>.info</code>\n"
                    f"{strings_current['ping']} <code>.ping</code></blockquote>\n\n"
                    f"<b>{strings_current['module_management']}</b>\n"
                    f"<blockquote>{strings_current['load']} <code>.iload</code>\n"
                    f"{strings_current['remove']} <code>.um [name]</code>\n"
                    f"{strings_current['list_modules']} <code>.man</code></blockquote>\n\n"
                )

            await event.edit(
                text,
                parse_mode="html",
                buttons=[
                    Button.url(
                        strings_current["github_repo"],
                        "https://github.com/hairpin01/MCUB-fork",
                    )
                ],
            )

            await event.answer(strings_current["setup_completed"], alert=True)

            await asyncio.sleep(1)

            backup_buttons = [
                [
                    Button.inline("Yes / Да", b"backup_setup_yes"),
                    Button.inline("No / Нет", b"backup_setup_no"),
                ]
            ]

            await bot_client.send_message(
                event.sender_id,
                f"<b>{strings_current['backup_setup']}</b>\n\n{strings_current['backup_enable']}",
                parse_mode="html",
                buttons=backup_buttons,
            )

        except Exception as e:
            kernel.logger.error(f"{lang_strings['callback_error']}: {e}")

    @bot_client.on(events.CallbackQuery(pattern=r"backup_setup_(yes|no)"))
    async def backup_enable_handler(event):
        try:
            enable = event.pattern_match.group(1).decode() == "yes" if isinstance(event.pattern_match.group(1), bytes) else event.pattern_match.group(1) == "yes"

            strings_current = strings.get(kernel.config.get("language", "en"), strings["en"])

            if enable:
                interval_buttons = [
                    [
                        Button.inline("2h", b"backup_interval:2"),
                        Button.inline("4h", b"backup_interval:4"),
                        Button.inline("6h", b"backup_interval:6"),
                    ],
                    [
                        Button.inline("12h", b"backup_interval:12"),
                        Button.inline("24h", b"backup_interval:24"),
                    ],
                    [
                        Button.inline(strings_current["backup_skip"], b"backup_interval_skip"),
                    ]
                ]

                await event.edit(
                    f"<b>{strings_current['backup_setup']}</b>\n\n{strings_current['backup_interval']}",
                    parse_mode="html",
                    buttons=interval_buttons,
                )
            else:
                await event.edit(
                    f"<b>{strings_current['backup_setup']}</b>\n\n{strings_current['backup_disabled']}",
                    parse_mode="html",
                )
                await event.answer(strings_current["backup_disabled"], alert=True)

        except Exception as e:
            kernel.logger.error(f"{lang_strings['callback_error']}: {e}")

    @bot_client.on(events.CallbackQuery(pattern=r"backup_interval:(\d+)"))
    async def backup_interval_handler(event):
        try:
            interval = int(event.pattern_match.group(1).decode() if isinstance(event.pattern_match.group(1), bytes) else event.pattern_match.group(1))

            strings_current = strings.get(kernel.config.get("language", "en"), strings["en"])

            import importlib.util
            spec = importlib.util.find_spec("modules.userbot-backup")
            if spec:
                userbot_backup = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(userbot_backup)
                BackupModule = userbot_backup.BackupModule
                backup_module = BackupModule()
                backup_module.kernel = kernel
                backup_module.client = kernel.client
                backup_module.config = {
                    "backup_chat_id": None,
                    "backup_interval_hours": interval,
                    "last_backup_time": None,
                    "backup_count": 0,
                    "enable_auto_backup": True,
                }

                await kernel.save_module_config("modules.userbot-backup", backup_module.config)

                chat = await backup_module.ensure_backup_chat()

                if chat:
                    await event.edit(
                        f"<b>{strings_current['backup_setup']}</b>\n\n{strings_current['backup_created']}\n\nInterval: {interval}h",
                        parse_mode="html",
                    )
                else:
                    await event.edit(
                        f"<b>{strings_current['backup_setup']}</b>\n\n{strings_current['backup_enabled']} ({interval}h)",
                        parse_mode="html",
                    )

                await event.answer(f"{strings_current['backup_enabled']} ({interval}h)", alert=True)
            else:
                await event.edit("Backup module not found")

        except Exception as e:
            kernel.logger.error(f"{lang_strings['callback_error']}: {e}")

    @bot_client.on(events.CallbackQuery(pattern=r"backup_interval_skip"))
    async def backup_skip_handler(event):
        try:
            strings_current = strings.get(kernel.config.get("language", "en"), strings["en"])

            await event.edit(
                f"<b>{strings_current['backup_setup']}</b>\n\n{strings_current['backup_disabled']}",
                parse_mode="html",
            )
            await event.answer(strings_current["backup_disabled"], alert=True)

        except Exception as e:
            kernel.logger.error(f"{lang_strings['callback_error']}: {e}")

    @bot_client.on(events.NewMessage(pattern=r"^(/ping|пинг$)"))
    async def ping_bot_handler(event):
        await event.reply(
            f"<blockquote>{lang_strings['pong']}</blockquote>", parse_mode="html"
        )

    kernel.client.loop.create_task(start_init(kernel))
