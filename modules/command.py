# author: @Hairpin00
# version: 1.1.0
# description: Bot command handlerss

from telethon import events, Button

def register(kernel):
    bot_client = kernel.bot_client

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
                start_sms = await kernel.client.send_message(username, '/init')
                kernel.logger.info("Выполнена инициализация через start_init")
                await start_sms.delete()
                await kernel.db_set("kernel", "HELLO_BOT", "True")

        except Exception as e:
            kernel.logger.error(f"Ошибка start_init: {e}")

    @bot_client.on(events.NewMessage(pattern="/start"))
    async def start_handler(event):
        try:
            await event.reply(
                file='https://x0.at/ZXNS.mp4',
                message=(
                    "<b>Привет! Я бот от MCUB-fork</b>\n"
                    "<blockquote>Developers: \n"
                    "fork: @Hairpin01,\n"
                    "Original: @Mitrichq</blockquote>"
                ),
                parse_mode="html",
                buttons=[
                    [
                        Button.url("🔭 Репозиторий", "https://github.com/hairpin01/MCUB-fork"),
                        Button.url("🚂 Оригинальный MCUBFB", "https://github.com/Mitrichdfklwhcluio/MCUBFB"),
                    ],
                    [
                        Button.url("🤖 Поддержка", "https://t.me/+LVnbdp4DNVE5YTFi")
                    ]
                ],
            )
        except Exception as e:
            kernel.logger.error(f"Ошибка /start: {e}")


    @bot_client.on(events.NewMessage(pattern="/profile"))
    async def profile_handler(event):
        try:
            user = event.sender

            user_id = user.id
            first_name = user.first_name or ""
            last_name = user.last_name or ""

            await event.reply(
                message=(
                    f"<b>Profile:</b>\n"
                    f"<b>Name:</b> {first_name} {last_name}\n"
                    f"<b>Prefix:</b> <code>{kernel.custom_prefix}</code>\n"
                    f"<b>Kernel version:</b> {kernel.VERSION}"
                ),
                parse_mode="html",
                buttons=[
                    [
                        Button.url("🔭 Репозиторий", "https://github.com/hairpin01/MCUB-fork")
                    ]
                ],
            )
        except Exception as e:
            kernel.logger.error(f"Ошибка /profile: {e}")
            await event.reply("❌ Не удалось получить информацию о профиле.")

    @bot_client.on(events.NewMessage(pattern=r"/init$"))
    @private_only
    async def init_handler(event):
        try:
            if int(event.sender_id) != int(kernel.ADMIN_ID):
                return

            hello_bot = await kernel.db_get("kernel", "HELLO_BOT")

            await bot_client.send_file(
                event.chat_id,
                file="https://x0.at/Y4ie.mp4"
            )

            gif_message = await event.respond(
                message="Choose a language / Выберите язык",
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
            await kernel.db_set("kernel", f"lang_select_{event.sender_id}", str(gif_message.id))

        except Exception as e:
            kernel.logger.error(f"Ошибка /init: {e}")

    @bot_client.on(events.NewMessage(pattern="/delete_mcub_bot"))
    async def delete_bot_handler(event):
        try:
            if not event.is_group and not event.is_channel:
                return

            if not kernel.is_admin:
                return

            await event.reply(
                message=(
                    "<b>👋 Прощайте! (лохи)</b>"
                ),
                parse_mode="html",
            )

            await bot_client.delete_dialog(event.chat_id)

            kernel.logger.info(f"Бот удален из чата {event.chat_id} пользователем {event.sender_id}")

        except Exception as e:
            kernel.logger.error(f"Ошибка /delete_mcub_bot: {e}")
            await event.reply(f"❌ Не удалось удалить бота из чата. {e}")

    @bot_client.on(events.CallbackQuery(pattern=r"start_lang_(ru|en)"))
    async def language_handler(event):
        try:
            lang = event.pattern_match.group(1).decode() if isinstance(
                event.pattern_match.group(1), bytes
                ) else event.pattern_match.group(1)
            await kernel.db_set("kernel", "language", lang)
            kernel.config['language'] = lang
            kernel.save_config()

            if lang == "ru":
                text = (
                    "<b>Привет</b>, MCUB установлен!\n\n"
                    "<b>Мини гайд:</b>\n"
                    "<blockquote>👉 Префикс: <code>.prefix {новый префикс}</code>\n"
                    "👉 Логи: <code>.logs</code>\n"
                    "👉 Инфо: <code>.info</code>\n"
                    "👉 Пинг: <code>.ping</code></blockquote>\n\n"
                    "<b>Управление модулями:</b>\n"
                    "<blockquote>👉 Загрузить: <code>.iload</code>\n"
                    "👉 Удалить: <code>.um [название]</code>\n"
                    "👉 Список: <code>.man</code></blockquote>\n\n"
                )
            else:
                text = (
                    "<b>Hello</b>, MCUB installed!\n\n"
                    "<b>Main commands:</b>\n"
                    "<blockquote>👉 Prefix: <code>.prefix {you prefix}</code>\n"
                    "👉 logs: <code>.logs</code>\n"
                    "👉 Info: <code>.info</code>\n"
                    "👉 Ping: <code>.ping</code></blockquote>\n\n"
                    "<b>Module management:</b>\n"
                    "<blockquote>👉 Load: <code>.iload</code>\n"
                    "👉 Remove: <code>.um [name]</code>\n"
                    "👉 List repo modules: <code>.man</code></blockquote>\n\n"
                )

            msg_id = await kernel.db_get("kernel", f"lang_select_{event.sender_id}")
            if msg_id:
                try:
                    await event.edit(text, parse_mode="html",
                                     buttons=[Button.url("🔭 GitHub", "https://github.com/hairpin01/MCUB-fork")])
                except Exception:
                    await event.respond(text, parse_mode="html")


            await event.answer("Настройка завершена!")

        except Exception as e:
            kernel.logger.error(f"Ошибка Callback: {e}")

    @bot_client.on(events.NewMessage(pattern=r"^(/ping|пинг$)"))
    async def ping_bot_handler(event):
        await event.reply("<blockquote>Понг!</blockquote>", parse_mode='html')


    kernel.client.loop.create_task(start_init(kernel))
