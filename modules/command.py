# author: @Hairpin00
# version: 1.2.0
# description: Bot command handlers with localization

from telethon import events, Button


def register(kernel):
    bot_client = kernel.bot_client

    language = kernel.config.get("language", "en")

    strings = {
        "ru": {
            "hello": "Привет! Я бот от MCUB-fork",
            "developers": "Developers:",
            "fork": "fork:",
            "original": "Original:",
            "github_repo": "🔭 Репозиторий",
            "original_mcub": "🚂 Оригинальный MCUBFB",
            "support": "🤖 Поддержка",
            "profile": "Profile:",
            "name": "Name:",
            "prefix": "Prefix:",
            "kernel_version": "Kernel version:",
            "profile_error": "❌ Не удалось получить информацию о профиле.",
            "goodbye": "👋 Прощайте!",
            "bot_removed": "Бот удален из чата",
            "delete_error": "❌ Не удалось удалить бота из чата.",
            "hello_installed": "Привет, MCUB установлен!",
            "hello_installed_en": "Hello, MCUB installed!",
            "mini_guide": "Мини гайд:",
            "main_commands": "Main commands:",
            "prefix_cmd": "Префикс:",
            "prefix_cmd_en": "Prefix:",
            "logs": "Логи:",
            "info": "Инфо:",
            "ping": "Пинг:",
            "module_management": "Управление модулями:",
            "module_management_en": "Module management:",
            "load": "Загрузить:",
            "load_en": "Load:",
            "remove": "Удалить:",
            "list_modules": "Список:",
            "list_modules_en": "List repo modules:",
            "choose_language": "Choose a language / Выберите язык",
            "setup_completed": "Настройка завершена!",
            "callback_error": "Ошибка Callback:",
            "pong": "Понг!",
            "start_init_error": "Ошибка start_init:",
            "start_error": "Ошибка /start:",
            "init_error": "Ошибка /init:",
            "remove_en": "Remove:",
            "remove_ru": "Удалить:",
        },
        "en": {
            "hello": "Hello! I am a bot from MCUB-fork",
            "developers": "Developers:",
            "fork": "fork:",
            "original": "Original:",
            "github_repo": "🔭 Repository",
            "original_mcub": "🚂 Original MCUBFB",
            "support": "🤖 Support",
            "profile": "Profile:",
            "name": "Name:",
            "prefix": "Prefix:",
            "kernel_version": "Kernel version:",
            "profile_error": "❌ Failed to get profile information.",
            "goodbye": "👋 Goodbye!",
            "bot_removed": "Bot removed from chat",
            "delete_error": "❌ Failed to remove bot from chat.",
            "hello_installed": "Hello, MCUB installed!",
            "hello_installed_en": "Hello, MCUB installed!",
            "mini_guide": "Mini guide:",
            "main_commands": "Main commands:",
            "prefix_cmd": "Prefix:",
            "prefix_cmd_en": "Prefix:",
            "logs": "Logs:",
            "info": "Info:",
            "ping": "Ping:",
            "module_management": "Module management:",
            "module_management_en": "Module management:",
            "load": "Load:",
            "load_en": "Load:",
            "remove": "Remove:",
            "remove_en": "Remove:",
            "remove_ru": "Удалить:",
            "list_modules": "List:",
            "list_modules_en": "List repo modules:",
            "choose_language": "Choose a language / Выберите язык",
            "setup_completed": "Setup completed!",
            "callback_error": "Callback error:",
            "pong": "Pong!",
            "start_init_error": "Error start_init:",
            "start_error": "Error /start:",
            "init_error": "Error /init:",
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
            if int(event.sender_id) != int(kernel.ADMIN_ID):
                return

            hello_bot = await kernel.db_get("kernel", "HELLO_BOT")

            await bot_client.send_file(event.chat_id, file="https://x0.at/Y4ie.mp4")

            gif_message = await event.respond(
                message=lang_strings["choose_language"],
                buttons=[
                    [
                        Button.inline("RU 🇷🇺", b"start_lang_ru"),
                        Button.inline("EN 🇺🇸", b"start_lang_en"),
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

            if lang == "ru":
                text = (
                    f"<b>{lang_strings['hello_installed']}</b>\n\n"
                    f"<b>{lang_strings['mini_guide']}</b>\n"
                    f"<blockquote>👉 {lang_strings['prefix_cmd']} <code>.prefix {'{новый префикс'}</code>\n"
                    f"👉 {lang_strings['logs']} <code>.logs</code>\n"
                    f"👉 {lang_strings['info']} <code>.info</code>\n"
                    f"👉 {lang_strings['ping']} <code>.ping</code></blockquote>\n\n"
                    f"<b>{lang_strings['module_management']}</b>\n"
                    f"<blockquote>👉 {lang_strings['load']} <code>.iload</code>\n"
                    f"👉 {lang_strings['remove_ru']} <code>.um [название]</code>\n"
                    f"👉 {lang_strings['list_modules']} <code>.man</code></blockquote>\n\n"
                )
            else:
                text = (
                    f"<b>{lang_strings['hello_installed_en']}</b>\n\n"
                    f"<b>{lang_strings['main_commands']}</b>\n"
                    f"<blockquote>👉 {lang_strings['prefix_cmd_en']} <code>.prefix {'{you prefix'}</code>\n"
                    f"👉 {lang_strings['logs']} <code>.logs</code>\n"
                    f"👉 {lang_strings['info']} <code>.info</code>\n"
                    f"👉 {lang_strings['ping']} <code>.ping</code></blockquote>\n\n"
                    f"<b>{lang_strings['module_management_en']}</b>\n"
                    f"<blockquote>👉 {lang_strings['load_en']} <code>.iload</code>\n"
                    f"👉 {lang_strings['remove_en']} <code>.um [name]</code>\n"
                    f"👉 {lang_strings['list_modules_en']} <code>.man</code></blockquote>\n\n"
                )

            msg_id = await kernel.db_get("kernel", f"lang_select_{event.sender_id}")
            if msg_id:
                try:
                    await event.edit(
                        text,
                        parse_mode="html",
                        buttons=[
                            Button.url(
                                lang_strings["github_repo"],
                                "https://github.com/hairpin01/MCUB-fork",
                            )
                        ],
                    )
                except Exception:
                    await event.respond(text, parse_mode="html")

            await event.answer(lang_strings["setup_completed"])

        except Exception as e:
            kernel.logger.error(f"{lang_strings['callback_error']}: {e}")

    @bot_client.on(events.NewMessage(pattern=r"^(/ping|пинг$)"))
    async def ping_bot_handler(event):
        await event.reply(
            f"<blockquote>{lang_strings['pong']}</blockquote>", parse_mode="html"
        )

    kernel.client.loop.create_task(start_init(kernel))
