# author: @Hairpin00
# version: 1.0.3
# description: settings
import json
import os
from telethon import events, Button


def register(kernel):
    client = kernel.client

    @kernel.register_command("prefix")
    async def prefix_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f"❌ Использование: {kernel.custom_prefix}prefix [символ]")
            return

        new_prefix = args[1]
        kernel.custom_prefix = new_prefix
        kernel.config["command_prefix"] = new_prefix

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        await event.edit(f"✅ Префикс изменен на `{new_prefix}`")

    @kernel.register_command("alias")
    async def alias_handler(event):
        args = event.text[len(kernel.custom_prefix) + 6 :].strip()
        if "=" not in args:
            await event.edit(
                f"❌ Использование: `{kernel.custom_prefix}alias алиас = команда`"
            )
            return

        parts = args.split("=")
        if len(parts) != 2:
            await event.edit(
                f"❌ Использование: `{kernel.custom_prefix}alias алиас = команда`"
            )
            return

        alias = parts[0].strip()
        command = parts[1].strip()

        kernel.aliases[alias] = command
        kernel.config["aliases"] = kernel.aliases

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        await event.edit(
            f"✅ Алиас создан: `{kernel.custom_prefix}{alias}` → `{kernel.custom_prefix}{command}`"
        )

    @kernel.register_command("2fa")
    async def twofa_handler(event):
        current = kernel.config.get("2fa_enabled", False)
        kernel.config["2fa_enabled"] = not current

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        status = "✅ включена (инлайн-подтверждение)" if not current else "❌ выключена"
        await event.edit(
            f"🔐 Двухфакторная аутентификация {status}\n\n"
            f"Теперь опасные команды требуют подтверждения через кнопки."
        )

    @kernel.register_command("powersave")
    async def powersave_handler(event):
        kernel.power_save_mode = not kernel.power_save_mode
        kernel.config["power_save_mode"] = kernel.power_save_mode

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        status = "🔋 включен" if kernel.power_save_mode else "⚡ выключен"
        features = (
            "\n• Логирование отключено\n• Healthcheck реже в 3 раза\n• Снижена нагрузка"
            if kernel.power_save_mode
            else ""
        )
        await event.edit(f"Режим энергосбережения {status}{features}")

    @kernel.register_command("lang")
    async def lang_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f"❌ Использование: {kernel.custom_prefix}lang [ru/en]")
            return

        new_lang = args[1].lower()
        LANGS = {"ru", "en"}

        if new_lang not in LANGS:
            await event.edit(f'❌ Доступные языки: {", ".join(LANGS)}')
            return

        kernel.config["language"] = new_lang

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        await event.edit(f"✅ Язык изменен на: {new_lang}")

    @kernel.register_command("settings")
    async def settings_handler(event):
        bot_username = kernel.config.get("inline_bot_username")
        if not bot_username:
            await event.edit(
                "❌ Инлайн бот не настроен\nУстановите inline_bot_token в конфиге"
            )
            return

        await event.delete()
        try:
            results = await client.inline_query(bot_username, "settings")
            if results:
                await results[0].click(event.chat_id, reply_to=event.reply_to_msg_id)
            else:
                await client.send_message(event.chat_id, "❌ Нет результатов инлайн")
        except Exception as e:
            await kernel.handle_error(e, source="settings_inline", event=event)
            await client.send_message(event.chat_id, f"❌ Ошибка: {str(e)[:100]}")

    async def settings_inline_handler(event):
        from telethon import Button

        api_protection = kernel.config.get("api_protection", False)
        power_save = kernel.config.get("power_save_mode", False)
        two_fa = kernel.config.get("2fa_enabled", False)

        buttons = [
            [
                Button.inline("reset prefix", b"settings_reset_prefix"),
                Button.inline("reset alias", b"settings_reset_alias"),
                Button.inline(
                    f"{'✅' if api_protection else '❌'} api protection",
                    b"settings_toggle_api",
                ),
            ],
            [
                Button.inline(
                    f"{'✅' if power_save else '❌'} powersave",
                    b"settings_toggle_powersave",
                ),
                Button.inline(
                    f"{'✅' if two_fa else '❌'} 2fa", b"settings_toggle_2fa"
                ),
            ],
            [Button.inline("mcub info", b"settings_mcubinfo")],
            [Button.inline(f"Kernel version: {kernel.VERSION}", b"settings_version")],
        ]

        result = event.builder.article(
            title="Settings",
            description="Userbot settings panel",
            text=f"⚙️ **Userbot Settings**\n\nClick buttons to manage settings:",
            buttons=buttons,
        )
        await event.answer([result])

    async def settings_callback_handler(event):
        data = event.data.decode()

        if data == "settings_reset_prefix":
            kernel.custom_prefix = "."
            kernel.config["command_prefix"] = "."
            with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)
            await event.edit("✅ Prefix reset to `.`")

        elif data == "settings_reset_alias":
            kernel.aliases = {}
            kernel.config["aliases"] = {}
            with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)
            await event.edit("✅ Aliases cleared")

        elif data == "settings_toggle_api":
            current = kernel.config.get("api_protection", False)
            kernel.config["api_protection"] = not current
            with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)
            status = "✅ enabled" if not current else "❌ disabled"
            await event.edit(f"API protection {status}")

        elif data == "settings_toggle_powersave":
            current = kernel.config.get("power_save_mode", False)
            kernel.config["power_save_mode"] = not current
            kernel.power_save_mode = not current
            with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)
            status = "✅ enabled" if not current else "❌ disabled"
            await event.edit(f"Power save mode {status}")

        elif data == "settings_toggle_2fa":
            current = kernel.config.get("2fa_enabled", False)
            kernel.config["2fa_enabled"] = not current
            with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)
            status = "✅ enabled" if not current else "❌ disabled"
            await event.edit(f"2FA {status}")

        elif data == "settings_mcubinfo":
            info_text = (
                "🎭 **Что такое юзербот?**\n\n"
                "Это программа, которая работает через ваш личный аккаунт Telegram, используя клиентский API. "
                "В отличие от обычных ботов (Bot API), юзербот имеет доступ ко всем функциям обычного пользователя - "
                "может отправлять сообщения, управлять группами, автоматизировать действия и многое другое.\n\n"
                "**Преимущества:** Полная автоматизация, неограниченные возможности, гибкость и кастомизация, прямое подключение\n\n"
                "**Главные риски:** Блокировка аккаунта, отсутствие официальной поддержки, ответственность на пользователе, риск для основного аккаунта"
            )
            await event.edit(info_text)

        elif data == "settings_version":
            await event.answer(f"Kernel version: {kernel.VERSION}", alert=True)

        await event.answer()

    @kernel.register_command("mcubinfo")
    async def mcubinfo_cmd(event):
        try:
            await event.edit("🔑", parse_mode="html")
            info_text = (
                "🎭 <b>Что такое юзербот?</b>\n"
                "<blockquote>Это программа, которая работает через ваш личный аккаунт Telegram, используя клиентский API. "
                "В отличие от обычных ботов (<code>Bot API</code>зербот имеет доступ ко всем функциям обычного пользователя — может отправлять сообщения, управлять группами, "
                "автоматизировать действия и многое другое.</blockquote>\n\n"
                "<b>Преимущества:</b> <blockquote><b>Полная автоматизация</b> — можно настроить автоответы, мониторинг чатов, управление каналами и группами\n"
                "<b>Неограниченные возможности</b> — доступ ко всем функциям Telegram, включая те, что недоступны обычным ботам\n"
                "<b>Гибкость и кастомизация</b> — можно писать собственный код под любые задачи\n"
                "•<b>Прямое подключение</b> — работа напрямую с серверами Telegram без лишних промежуточных слоёв.</blockquote>\n\n"
                "🚂 <b>Главные риски и недостатки:</b>\n"
                "<blockquote><b>Блокировка аккаунта</b> — Telegram может заблокировать аккаунт за подозрительную активность (спам, массовые действия)\n"
                "• <b>Отсутствие официальной поддержки</b> — User API не документирован официально, могут быть нестабильности\n"
                "<b>Ответственность на пользователе</b> — за действия бота, нарушающие правила Telegram, отвечает владелец аккаунта\n"
                "<b>Риск для основного аккаунта</b> — рекомендуется использовать отдельный аккаунт для юзербота</blockquote>"
            )

            await event.edit(info_text, parse_mode="html")
        except Exception as e:
            await kernel.handle_error(e, source="mcubinfo_cmd", event=event)
            await event.edit("🌩️ <b>error, check logs</b>", parse_mode="html")

    kernel.register_inline_handler("settings", settings_inline_handler)
    kernel.register_callback_handler("settings_", settings_callback_handler)
