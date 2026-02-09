# author: @Hairpin00
# version: 1.0.4
# description: settings

import json
import os
from telethon import events, Button
# <tg-emoji emoji-id="5902002809573740949">✅</tg-emoji>
# <tg-emoji emoji-id="5904692292324692386">⚠️</tg-emoji>
# <tg-emoji emoji-id="5893382531037794941">🔎</tg-emoji>
# <tg-emoji emoji-id="5893081007153746175">❌</tg-emoji>
# <tg-emoji emoji-id="5893368370530621889">🔜</tg-emoji>

def register(kernel):
    client = kernel.client

    # Локализованные строки
    strings = {
        'ru': {
            'prefix_usage': '❌ Использование: {prefix}prefix [символ]',
            'prefix_changed': '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji><b> Префикс изменен на </b><code>{prefix}</code>\n <i>чтобы вернуть</i><pre>{prefix}prefix {prefix_old}</pre>',
            'alias_usage': '❌ Использование: `{prefix}alias алиас = команда`',
            'alias_created': '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Алиас создан: <code>{prefix}{alias}</code> → <code>{prefix}{command}</code>',
            '2fa_enabled': '🔐 Двухфакторная аутентификация <tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> включена (инлайн-подтверждение)',
            '2fa_disabled': '🔐 Двухфакторная аутентификация ❌ выключена',
            'powersave_enabled': '🔋 включен',
            'powersave_disabled': '⚡ выключен',
            'powersave_features': '\n• Логирование отключено\n• Healthcheck реже в 3 раза\n• Снижена нагрузка',
            'lang_usage': '❌ Использование: {prefix}lang [ru/en]',
            'lang_available': '❌ Доступные языки: {langs}',
            'lang_changed': '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Язык изменен на: {lang}',
            'inline_bot_not_set': '❌ Инлайн бот не настроен\nУстановите inline_bot_token в конфиге',
            'inline_no_results': '❌ Нет результатов инлайн',
            'inline_error': '❌ Ошибка: {error}',
            'mcubinfo_title': '🎭 **Что такое юзербот?**\n\n',
            'mcubinfo_description': 'Это программа, которая работает через ваш личный аккаунт Telegram, используя клиентский API. В отличие от обычных ботов (Bot API), юзербот имеет доступ ко всем функциям обычного пользователя - может отправлять сообщения, управлять группами, автоматизировать действия и многое другое.\n\n',
            'mcubinfo_advantages': '**Преимущества:** Полная автоматизация, неограниченные возможности, гибкость и кастомизация, прямое подключение\n\n',
            'mcubinfo_risks': '**Главные риски:** Блокировка аккаунта, отсутствие официальной поддержки, ответственность на пользователе, риск для основного аккаунта',
            'settings_title': '⚙️ Userbot Settings',
            'prefix_reset': '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Префикс сброшен на `.`',
            'aliases_cleared': '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Алиасы очищены',
            'api_enabled': '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> включена',
            'api_disabled': '❌ отключена',
            'mcubinfo_html': '''🎭 <b>Что такое юзербот?</b>
<blockquote>Это программа, которая работает через ваш личный аккаунт Telegram, используя клиентский API. В отличие от обычных ботов (<code>Bot API</code>зербот имеет доступ ко всем функциям обычного пользователя — может отправлять сообщения, управлять группами, автоматизировать действия и многое другое.</blockquote>

<b>Преимущества:</b> <blockquote><b>Полная автоматизация</b> — можно настроить автоответы, мониторинг чатов, управление каналами и группами
<b>Неограниченные возможности</b> — доступ ко всем функциям Telegram, включая те, что недоступны обычным ботам
<b>Гибкость и кастомизация</b> — можно писать собственный код под любые задачи
•<b>Прямое подключение</b> — работа напрямую с серверами Telegram без лишних промежуточных слоёв.</blockquote>

🚂 <b>Главные риски и недостатки:</b>
<blockquote><b>Блокировка аккаунта</b> — Telegram может заблокировать аккаунт за подозрительную активность (спам, массовые действия)
• <b>Отсутствие официальной поддержки</b> — User API не документирован официально, могут быть нестабильности
<b>Ответственность на пользователе</b> — за действия бота, нарушающие правила Telegram, отвечает владелец аккаунта
<b>Риск для основного аккаунта</b> — рекомендуется использовать отдельный аккаунт для юзербота</blockquote>''',
            'mcubinfo_error': '🌩️ <b>error, check logs</b>\nЛог:<pre>{e}<pre>'
        },
        'en': {
            'prefix_usage': '❌ Usage: {prefix}prefix [symbol]',
            'prefix_changed': '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> <b>Prefix changed to </b><code>{prefix}</code>\n<pre>{prefix}prefix {prefix_old}</pre>',
            'alias_usage': '❌ Usage: `{prefix}alias alias = command`',
            'alias_created': '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Alias created: <code>{prefix}{alias}</code> → <code>{prefix}{command}</code>',
            '2fa_enabled': '🔐 Two-factor authentication <tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> enabled (inline confirmation)',
            '2fa_disabled': '🔐 Two-factor authentication ❌ disabled',
            'powersave_enabled': '🔋 enabled',
            'powersave_disabled': '⚡ disabled',
            'powersave_features': '\n• Logging disabled\n• Healthcheck 3 times less frequent\n• Reduced load',
            'lang_usage': '❌ Usage: {prefix}lang [ru/en]',
            'lang_available': '❌ Available languages: {langs}',
            'lang_changed': '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Language changed to: {lang}',
            'inline_bot_not_set': '❌ Inline bot not configured\nSet inline_bot_token in config',
            'inline_no_results': '❌ No inline results',
            'inline_error': '❌ Error: {error}',
            'mcubinfo_title': '🎭 What is a userbot?\n\n',
            'mcubinfo_description': 'This is a program that works through your personal Telegram account using the client API. Unlike regular bots (Bot API), a userbot has access to all the functions of a regular user - can send messages, manage groups, automate actions and much more.\n\n',
            'mcubinfo_advantages': '**Advantages:** Full automation, unlimited capabilities, flexibility and customization, direct connection\n\n',
            'mcubinfo_risks': '**Main risks:** Account blocking, lack of official support, user responsibility, risk to main account',
            'settings_title': '⚙️ Userbot Settings',
            'prefix_reset': '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Prefix reset to <code>.</code>',
            'aliases_cleared': '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Aliases cleared',
            'api_enabled': '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> enabled',
            'api_disabled': '❌ disabled',
            'mcubinfo_html': '''🎭 <b>What is a userbot?</b>
<blockquote>This is a program that works through your personal Telegram account using the client API. Unlike regular bots (<code>Bot API</code>), a userbot has access to all the functions of a regular user - can send messages, manage groups, automate actions and much more.</blockquote>

<b>Advantages:</b> <blockquote><b>Full automation</b> - can set up auto-replies, chat monitoring, channel and group management
<b>Unlimited capabilities</b> - access to all Telegram features, including those unavailable to regular bots
<b>Flexibility and customization</b> - can write custom code for any tasks
•<b>Direct connection</b> - work directly with Telegram servers without unnecessary intermediate layers.</blockquote>

🚂 <b>Main risks and disadvantages:</b>
<blockquote><b>Account blocking</b> - Telegram may block an account for suspicious activity (spam, mass actions)
• <b>Lack of official support</b> - User API is not officially documented, may be unstable
<b>User responsibility</b> - the account owner is responsible for bot actions that violate Telegram rules
<b>Risk to main account</b> - recommended to use a separate account for userbot</blockquote>''',
            'mcubinfo_error': '🌩️ <b>error, check logs</b>\nFull Logs: <pre>{e}<pre>'
        }
    }

    # Вспомогательная функция для получения локализованной строки
    def _(key, **kwargs):

        language = kernel.config.get('language', 'ru')
        lang_strings = strings.get(language, strings['ru'])
        text = lang_strings.get(key, key)
        return text.format(**kwargs) if kwargs else text

    @kernel.register.command("prefix")
    async def prefix_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(_('prefix_usage', prefix=kernel.custom_prefix), parse_mode='html')
            return
        prefix_old = kernel.custom_prefix
        new_prefix = args[1]
        kernel.custom_prefix = new_prefix
        kernel.config["command_prefix"] = new_prefix

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        await event.edit(_('prefix_changed', prefix=new_prefix, prefix_old=prefix_old), parse_mode='html')

    @kernel.register.command("alias")
    async def alias_handler(event):
        args = event.text[len(kernel.custom_prefix) + 6 :].strip()
        if "=" not in args:
            await event.edit(_('alias_usage', prefix=kernel.custom_prefix))
            return

        parts = args.split("=")
        if len(parts) != 2:
            await event.edit(_('alias_usage', prefix=kernel.custom_prefix))
            return

        alias = parts[0].strip()
        command = parts[1].strip()

        kernel.aliases[alias] = command
        kernel.config["aliases"] = kernel.aliases

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        await event.edit(_('alias_created', prefix=kernel.custom_prefix, alias=alias, command=command), parse_mode='html')

    @kernel.register.command("2fa")
    async def twofa_handler(event):
        current = kernel.config.get("2fa_enabled", False)
        kernel.config["2fa_enabled"] = not current

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        status = _('2fa_enabled') if not current else _('2fa_disabled')
        await event.edit(
            f"{status}",
            parse_mode='html'
            )

    @kernel.register.command("powersave")
    async def powersave_handler(event):
        kernel.power_save_mode = not kernel.power_save_mode
        kernel.config["power_save_mode"] = kernel.power_save_mode

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        status = _('powersave_enabled') if kernel.power_save_mode else _('powersave_disabled')
        features = _('powersave_features') if kernel.power_save_mode else ""
        await event.edit(f"Режим энергосбережения {status}{features}", parse_mode='html')

    @kernel.register.command("lang")
    async def lang_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(_('lang_usage', prefix=kernel.custom_prefix))
            return

        new_lang = args[1].lower()
        LANGS = {"ru", "en"}

        if new_lang not in LANGS:
            await event.edit(_('lang_available', langs=", ".join(LANGS)))
            return

        kernel.config["language"] = new_lang

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        await event.edit(_('lang_changed', lang=new_lang), parse_mode='html')

    @kernel.register.command("settings")
    async def settings_handler(event):
        bot_username = kernel.config.get("inline_bot_username")
        if not bot_username:
            await event.edit(_('inline_bot_not_set'))
            return

        await event.delete()
        try:
            results = await client.inline_query(bot_username, "settings")
            if results:
                await results[0].click(event.chat_id, reply_to=event.reply_to_msg_id)
            else:
                await client.send_message(event.chat_id, _('inline_no_results'))
        except Exception as e:
            await kernel.handle_error(e, source="settings_inline", event=event)
            await client.send_message(event.chat_id, _('inline_error', error=str(e)[:100]))

    async def settings_inline_handler(event):
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
            text=_('settings_title'),
            buttons=buttons,
            parse_mode='html'
        )
        await event.answer([result])

    async def settings_callback_handler(event):
        data = event.data.decode()

        if data == "settings_reset_prefix":
            kernel.custom_prefix = "."
            kernel.config["command_prefix"] = "."
            with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)
            await event.edit(_('prefix_reset'), parse_mode='html')

        elif data == "settings_reset_alias":
            kernel.aliases = {}
            kernel.config["aliases"] = {}
            with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)
            await event.edit(_('aliases_cleared'), parse_mode='html')

        elif data == "settings_toggle_api":
            current = kernel.config.get("api_protection", False)
            kernel.config["api_protection"] = not current
            with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)
            status = _('api_enabled') if not current else _('api_disabled')
            await event.edit(f"API protection {status}", parse_mode='html')

        elif data == "settings_toggle_powersave":
            current = kernel.config.get("power_save_mode", False)
            kernel.config["power_save_mode"] = not current
            kernel.power_save_mode = not current
            with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)
            status = _('api_enabled') if not current else _('api_disabled')
            await event.edit(f"Power save mode {status}", parse_mode='html')

        elif data == "settings_toggle_2fa":
            current = kernel.config.get("2fa_enabled", False)
            kernel.config["2fa_enabled"] = not current
            with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)
            status = _('api_enabled') if not current else _('api_disabled')
            await event.edit(f"2FA {status}", parse_mode='html')

        elif data == "settings_mcubinfo":
            info_text = (
                _('mcubinfo_title') +
                _('mcubinfo_description') +
                _('mcubinfo_advantages') +
                _('mcubinfo_risks')
            )
            await event.edit(info_text)

        elif data == "settings_version":
            await event.answer(f"Kernel version: {kernel.VERSION}", alert=True)

        await event.answer()

    @kernel.register.command("mcubinfo")
    async def mcubinfo_cmd(event):
        try:
            await event.edit('<tg-emoji emoji-id="5893368370530621889">🔜</tg-emoji>', parse_mode="html")
            info_text = _('mcubinfo_html')
            await event.edit(info_text, parse_mode="html")
        except Exception as e:
            await kernel.handle_error(e, source="mcubinfo_cmd", event=event)
            await event.edit(_('mcubinfo_error'), parse_mode="html")

    kernel.register_inline_handler("settings", settings_inline_handler)
    kernel.register_callback_handler("settings_", settings_callback_handler)
