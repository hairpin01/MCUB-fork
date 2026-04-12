from __future__ import annotations

# author: @Hairpin00
# version: 1.0.4
# description: settings

import asyncio
import json
import os
import shutil
from telethon import Button

from core.lib.loader.module_config import (
    ModuleConfig,
    ConfigValue,
    Boolean,
)


def register(kernel):
    client = kernel.client

    strings = {
        "ru": {
            "prefix_usage": "❌ Использование: {prefix}setprefix [символ]",
            "prefix_one_char": "❌ <b>Префикс должен быть ровно 1 символом</b>",
            "prefix_changed": '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji><b> Префикс изменен на </b><code>{prefix}</code>, <b>чтобы вернуть, напишите:</b>\n<pre>{prefix}setprefix {prefix_old}</pre>',
            "alias_usage": "❌ Использование: `{prefix}addalias алиас = команда`",
            "alias_created": '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Алиас создан: <code>{prefix}{alias}</code> → <code>{prefix}{command}</code>',
            "alias_target_not_found": "❌ Команда <code>{command}</code> не найдена. Проверьте имя команды.",
            "delalias_usage": "❌ Использование: `{prefix}delalias алиас`",
            "delalias_done": '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Алиас удалён: <code>{prefix}{alias}</code>',
            "delalias_not_found": "❌ Алиас <code>{alias}</code> не найден.",
            "aliases_empty": "📋 Алиасы отсутствуют.",
            "2fa_enabled": '🔐 Двухфакторная аутентификация <tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> включена (инлайн-подтверждение)',
            "2fa_disabled": "🔐 Двухфакторная аутентификация ❌ выключена",
            "powersave_enabled": "🔋 включен",
            "powersave_disabled": "⚡ выключен",
            "powersave_features": "\n• Логирование отключено\n• Healthcheck реже в 3 раза\n• Снижена нагрузка",
            "lang_usage": "❌ Использование: {prefix}lang [ru/en]",
            "lang_available": "❌ Доступные языки: {langs}",
            "lang_changed": '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Язык изменен на: {lang}',
            "inline_bot_not_set": "❌ Инлайн бот не настроен\nУстановите inline_bot_token в конфиге",
            "inline_no_results": "❌ Нет результатов инлайн",
            "inline_error": "❌ Ошибка: {error}",
            "mcubinfo_title": "🎭 **Что такое юзербот?**\n\n",
            "mcubinfo_description": "Это программа, которая работает через ваш личный аккаунт Telegram, используя клиентский API. В отличие от обычных ботов (Bot API), юзербот имеет доступ ко всем функциям обычного пользователя - может отправлять сообщения, управлять группами, автоматизировать действия и многое другое.\n\n",
            "mcubinfo_advantages": "**Преимущества:** Полная автоматизация, неограниченные возможности, гибкость и кастомизация, прямое подключение\n\n",
            "mcubinfo_risks": "**Главные риски:** Блокировка аккаунта, отсутствие официальной поддержки, ответственность на пользователе, риск для основного аккаунта",
            "settings_title": "⚙️ Userbot Settings",
            "prefix_reset": '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Префикс сброшен на `.`',
            "aliases_cleared": '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Алиасы очищены',
            "api_enabled": '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> включена',
            "api_disabled": "❌ отключена",
            "mcubinfo_html": """🎭 <b>Что такое юзербот?</b>
<blockquote expandable>Это программа, которая работает через ваш личный аккаунт Telegram, используя клиентский API. В отличие от обычных ботов (<code>Bot API</code>зербот имеет доступ ко всем функциям обычного пользователя — может отправлять сообщения, управлять группами, автоматизировать действия и многое другое.</blockquote>

<b>Преимущества:</b> <blockquote expandable><b>Полная автоматизация</b> — можно настроить автоответы, мониторинг чатов, управление каналами и группами
<b>Неограниченные возможности</b> — доступ ко всем функциям Telegram, включая те, что недоступны обычным ботам
<b>Гибкость и кастомизация</b> — можно писать собственный код под любые задачи
•<b>Прямое подключение</b> — работа напрямую с серверами Telegram без лишних промежуточных слоёв.</blockquote>

🚂 <b>Главные риски и недостатки:</b>
<blockquote expandable><b>Блокировка аккаунта</b> — Telegram может заблокировать аккаунт за подозрительную активность (спам, массовые действия)
• <b>Отсутствие официальной поддержки</b> — User API не документирован официально, могут быть нестабильности
<b>Ответственность на пользователе</b> — за действия бота, нарушающие правила Telegram, отвечает владелец аккаунта
<b>Риск для основного аккаунта</b> — рекомендуется использовать отдельный аккаунт для юзербота</blockquote>""",
            "mcubinfo_error": "🌩️ <b>error, check logs</b>\nЛог:<pre>{e}<pre>",
            "danger_inline_not_set": "❌ Инлайн бот не настроен\nПодтверждение недоступно",
            "btn_confirm": "✅ Подтвердить",
            "btn_cancel": "✖ Отмена",
            "cleardb_confirm": "⚠️ <b>Удалить базу данных?</b>\n<blockquote>Это просто удалит файл базы данных.</blockquote>",
            "cleardb_done": "✅ База данных удалена: <code>{path}</code>",
            "cleardb_missing": "✅ База данных уже отсутствует: <code>{path}</code>",
            "cleardb_error": "❌ Не удалось удалить базу данных: <code>{error}</code>",
            "clearmodules_confirm": "⚠️ <b>Удалить все загруженные модули?</b>\n<blockquote>Будут удалены все файлы из <code>{path}</code>.</blockquote>",
            "clearmodules_done": "✅ Очищено модулей: <code>{count}</code>",
            "clearmodules_missing": "✅ Каталог <code>{path}</code> уже пуст или отсутствует",
            "clearmodules_error": "❌ Не удалось очистить modules_loaded: <code>{error}</code>",
            "clearcache_confirm": "⚠️ <b>Очистить кэш?</b>\n<blockquote>Ядро и модули могут хранить некоторые вещи в кэше. После очистки часть данных будет пересоздана заново.</blockquote>",
            "clearcache_done": "✅ Кэш очищен",
            "clearcache_error": "❌ Не удалось очистить кэш: <code>{error}</code>",
            "danger_cancelled": "❄️ Действие отменено",
            "btn_russian": "Русский",
            "btn_english": "English",
            "select_language": "🌐 Выберите язык",
        },
        "en": {
            "prefix_usage": "❌ Usage: {prefix}setprefix [symbol]",
            "prefix_one_char": "❌ <b>Prefix must be exactly 1 character</b>",
            "prefix_changed": '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> <b>Prefix changed to </b><code>{prefix}</code>, <b>to restore, type:</b>\n<pre>{prefix}setprefix {prefix_old}</pre>',
            "alias_usage": "❌ Usage: `{prefix}addalias alias = command`",
            "alias_created": '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Alias created: <code>{prefix}{alias}</code> → <code>{prefix}{command}</code>',
            "alias_target_not_found": "❌ Command <code>{command}</code> not found. Check the command name.",
            "delalias_usage": "❌ Usage: `{prefix}delalias alias`",
            "delalias_done": '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Alias deleted: <code>{prefix}{alias}</code>',
            "delalias_not_found": "❌ Alias <code>{alias}</code> not found.",
            "aliases_empty": "📋 No aliases found.",
            "2fa_enabled": '🔐 Two-factor authentication <tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> enabled (inline confirmation)',
            "2fa_disabled": "🔐 Two-factor authentication ❌ disabled",
            "powersave_enabled": "🔋 enabled",
            "powersave_disabled": "⚡ disabled",
            "powersave_features": "\n• Logging disabled\n• Healthcheck 3 times less frequent\n• Reduced load",
            "lang_usage": "❌ Usage: {prefix}lang [ru/en]",
            "lang_available": "❌ Available languages: {langs}",
            "lang_changed": '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Language changed to: {lang}',
            "inline_bot_not_set": "❌ Inline bot not configured\nSet inline_bot_token in config",
            "inline_no_results": "❌ No inline results",
            "inline_error": "❌ Error: {error}",
            "mcubinfo_title": "🎭 What is a userbot?\n\n",
            "mcubinfo_description": "This is a program that works through your personal Telegram account using the client API. Unlike regular bots (Bot API), a userbot has access to all the functions of a regular user - can send messages, manage groups, automate actions and much more.\n\n",
            "mcubinfo_advantages": "**Advantages:** Full automation, unlimited capabilities, flexibility and customization, direct connection\n\n",
            "mcubinfo_risks": "**Main risks:** Account blocking, lack of official support, user responsibility, risk to main account",
            "settings_title": "⚙️ Userbot Settings",
            "prefix_reset": '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Prefix reset to <code>.</code>',
            "aliases_cleared": '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> Aliases cleared',
            "api_enabled": '<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> enabled',
            "api_disabled": "❌ disabled",
            "mcubinfo_html": """🎭 <b>What is a userbot?</b>
<blockquote expandable>This is a program that works through your personal Telegram account using the client API. Unlike regular bots (<code>Bot API</code>), a userbot has access to all the functions of a regular user - can send messages, manage groups, automate actions and much more.</blockquote>

<b>Advantages:</b> <blockquote expandable><b>Full automation</b> - can set up auto-replies, chat monitoring, channel and group management
<b>Unlimited capabilities</b> - access to all Telegram features, including those unavailable to regular bots
<b>Flexibility and customization</b> - can write custom code for any tasks
•<b>Direct connection</b> - work directly with Telegram servers without unnecessary intermediate layers.</blockquote>

🚂 <b>Main risks and disadvantages:</b>
<blockquote expandable><b>Account blocking</b> - Telegram may block an account for suspicious activity (spam, mass actions)
• <b>Lack of official support</b> - User API is not officially documented, may be unstable
<b>User responsibility</b> - the account owner is responsible for bot actions that violate Telegram rules
<b>Risk to main account</b> - recommended to use a separate account for userbot</blockquote>""",
            "mcubinfo_error": "🌩️ <b>error, check logs</b>\nFull Logs: <pre>{e}<pre>",
            "powersave_status": "🔋 Power save mode {status}{features}",
            "select_language": "🌐 Select language",
            "btn_russian": "Русский",
            "btn_english": "English",
            "settings_inline_title": "⚙️ Settings",
            "settings_inline_description": "Userbot settings panel",
            "btn_reset_prefix": "reset prefix",
            "btn_reset_alias": "reset alias",
            "btn_api_protection": "{status} api protection",
            "btn_powersave": "{status} powersave",
            "btn_2fa": "{status} 2fa",
            "btn_mcubinfo": "mcub info",
            "btn_kernel_version": "Kernel version: {version}",
            "api_protection_status": "API protection {status}",
            "2fa_status": "2FA {status}",
            "danger_inline_not_set": "❌ Inline bot is not configured\nConfirmation is unavailable",
            "btn_confirm": "✅ Confirm",
            "btn_cancel": "✖ Cancel",
            "cleardb_confirm": "⚠️ <b>Delete the database?</b>\n<blockquote>This will simply delete the database file.</blockquote>",
            "cleardb_done": "✅ Database deleted: <code>{path}</code>",
            "cleardb_missing": "✅ Database file is already missing: <code>{path}</code>",
            "cleardb_error": "❌ Failed to delete database: <code>{error}</code>",
            "clearmodules_confirm": "⚠️ <b>Delete all loaded modules?</b>\n<blockquote>All files from <code>{path}</code> will be removed.</blockquote>",
            "clearmodules_done": "✅ Removed modules: <code>{count}</code>",
            "clearmodules_missing": "✅ Directory <code>{path}</code> is already empty or missing",
            "clearmodules_error": "❌ Failed to clear modules_loaded: <code>{error}</code>",
            "clearcache_confirm": "⚠️ <b>Clear cache?</b>\n<blockquote>Kernel and modules may store some things in cache. After cleanup, part of the data will be recreated again.</blockquote>",
            "clearcache_done": "✅ Cache cleared",
            "clearcache_error": "❌ Failed to clear cache: <code>{error}</code>",
            "danger_cancelled": "❄️ Action cancelled",
        },
    }

    def _(key, **kwargs):
        text = strings.get(kernel.config.get("language", "en"), strings["en"]).get(
            key, key
        )
        return text.format(**kwargs) if kwargs else text

    config = ModuleConfig(
        ConfigValue(
            "settings_any_prefix",
            False,
            description="Allow multi-character prefixes (bypass 1-char restriction)",
            validator=Boolean(default=False),
        ),
    )

    def get_config():
        live_cfg = getattr(kernel, "_live_module_configs", {}).get(__name__)
        if live_cfg:
            return live_cfg
        return config

    async def startup():
        config_dict = await kernel.get_module_config(
            __name__,
            {"settings_any_prefix": False},
        )
        config.from_dict(config_dict)
        config_dict_clean = {k: v for k, v in config.to_dict().items() if v is not None}
        if config_dict_clean:
            await kernel.save_module_config(__name__, config_dict_clean)
        kernel.store_module_config_schema(__name__, config)

    asyncio.create_task(startup())

    @kernel.register.command("setprefix")
    async def setprefix_handler(event):
        """[prefix] - switch prefix userbot"""
        args = event.text.split()
        if len(args) < 2:
            await event.edit(
                _("prefix_usage", prefix=kernel.custom_prefix), parse_mode="html"
            )
            return
        new_prefix = args[1]
        cfg = get_config()
        any_prefix = cfg.get("settings_any_prefix", False) if cfg else False
        if not any_prefix and len(new_prefix) != 1:
            await event.edit(_("prefix_one_char"), parse_mode="html")
            return
        prefix_old = kernel.custom_prefix
        kernel.custom_prefix = new_prefix
        kernel.config["command_prefix"] = new_prefix

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        await event.edit(
            _("prefix_changed", prefix=new_prefix, prefix_old=prefix_old),
            parse_mode="html",
        )

    @kernel.register.command("addalias")
    async def alias_handler(event):
        """[alias] = [command]"""
        parts_text = event.text.split(None, 1)
        args = parts_text[1].strip() if len(parts_text) > 1 else ""
        if "=" not in args:
            await event.edit(_("alias_usage", prefix=kernel.custom_prefix))
            return

        parts = args.split("=", 1)
        if len(parts) < 2:
            await event.edit(_("alias_usage", prefix=kernel.custom_prefix))
            return

        alias = parts[0].strip()
        command = parts[1].strip()

        if not alias or not command:
            await event.edit(_("alias_usage", prefix=kernel.custom_prefix))
            return

        command_base = command.split()[0]
        if command_base not in kernel.command_handlers:
            await event.edit(
                _("alias_target_not_found", command=command_base),
                parse_mode="html",
            )
            return

        kernel.aliases[alias] = command
        kernel.config["aliases"] = kernel.aliases

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        await event.edit(
            _(
                "alias_created",
                prefix=kernel.custom_prefix,
                alias=alias,
                command=command,
            ),
            parse_mode="html",
        )

    @kernel.register.command("delalias")
    async def delalias_handler(event):
        """[alias] del alias"""
        args = event.text[len(kernel.custom_prefix) + 8 :].strip()
        if not args:
            await event.edit(_("delalias_usage", prefix=kernel.custom_prefix))
            return

        if args not in kernel.aliases:
            await event.edit(
                _("delalias_not_found", alias=args),
                parse_mode="html",
            )
            return

        del kernel.aliases[args]
        kernel.config["aliases"] = kernel.aliases

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        await event.edit(
            _(
                "delalias_done",
                prefix=kernel.custom_prefix,
                alias=args,
            ),
            parse_mode="html",
        )

    @kernel.register.command("aliases")
    async def aliases_handler(event):
        """list all aliases"""
        if not kernel.aliases:
            await event.edit(_("aliases_empty"))
            return

        lines = []
        for alias, target in sorted(kernel.aliases.items()):
            lines.append(
                f"<code>{kernel.custom_prefix}{alias} </code>-><code> {kernel.custom_prefix}{target}</code>"
            )

        text = "\n".join(lines)
        await event.edit(
            f"<blockquote expandable>{text}</blockquote>", parse_mode="html"
        )

    @kernel.register.command("lang")
    async def lang_handler(event):
        """[ru/en] - switch languages userbot"""
        args = event.text.split()
        if len(args) < 2:
            buttons = [
                [
                    Button.inline(_("btn_russian"), "lang:ru"),
                    Button.inline(_("btn_english"), "lang:en"),
                ]
            ]
            success = await kernel.inline_form(
                event.chat_id, _("select_language"), buttons=buttons
            )
            if success:
                await event.delete()

            return
        new_lang = args[1].lower()
        LANGS = {"ru", "en"}

        if new_lang not in LANGS:
            await event.edit(_("lang_available", langs=", ".join(LANGS)))
            return

        kernel.config["language"] = new_lang

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        await event.edit(_("lang_changed", lang=new_lang), parse_mode="html")

    async def _show_danger_confirm(event, action: str, text: str):
        success, form_message = await kernel.inline_form(
            event.chat_id,
            text,
            buttons=[
                [
                    Button.inline(
                        _("btn_confirm"),
                        f"settings_danger:confirm:{action}".encode(),
                        style="danger",
                    ),
                    Button.inline(
                        _("btn_cancel"),
                        b"settings_danger:cancel",
                        style="primary",
                    ),
                ]
            ],
        )
        if success:
            await event.delete()

    def _resolve_db_path() -> str:
        db_manager = getattr(kernel, "db_manager", None)
        if db_manager and hasattr(db_manager, "_resolve_db_file"):
            return os.path.abspath(db_manager._resolve_db_file())
        return os.path.abspath("userbot.db")

    async def _clear_db():
        db_path = _resolve_db_path()
        conn = getattr(kernel, "db_conn", None)
        if conn:
            await conn.close()
            if getattr(kernel, "db_manager", None):
                kernel.db_manager.conn = None

        if not os.path.exists(db_path):
            return _("cleardb_missing", path=db_path)

        os.remove(db_path)
        return _("cleardb_done", path=db_path)

    async def _clear_modules_dir():
        modules_dir = getattr(kernel, "MODULES_LOADED_DIR", "modules_loaded")
        modules_dir = os.path.abspath(modules_dir)
        if not os.path.isdir(modules_dir):
            return _("clearmodules_missing", path=modules_dir)

        deleted = 0
        for name in os.listdir(modules_dir):
            target = os.path.join(modules_dir, name)
            if os.path.isdir(target) and not os.path.islink(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
            deleted += 1

        if deleted == 0:
            return _("clearmodules_missing", path=modules_dir)
        return _("clearmodules_done", count=deleted)

    async def _clear_cache():
        if getattr(kernel, "cache", None):
            kernel.cache.clear()
        return _("clearcache_done")

    @kernel.register.command("cleardb")
    async def cleardb_handler(event):
        """delete db file with inline confirmation"""
        await _show_danger_confirm(event, "db", _("cleardb_confirm"))

    @kernel.register.command("clearmodules")
    async def clearmodules_handler(event):
        """delete all files from modules_loaded"""
        await _show_danger_confirm(
            event,
            "modules",
            _("clearmodules_confirm", path=os.path.abspath(kernel.MODULES_LOADED_DIR)),
        )

    @kernel.register.command("clearcache")
    async def clearcache_handler(event):
        """clear kernel cache"""
        await _show_danger_confirm(event, "cache", _("clearcache_confirm"))

    async def lang_callback_handler(event):
        data = event.data.decode()
        if data.startswith("lang:"):
            lang = data.split(":")[1]
            kernel.config["language"] = lang
            with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)
            await event.edit(_("lang_changed", lang=lang), parse_mode="html")
        await event.answer()

    async def settings_danger_callback_handler(event):
        data = event.data.decode()

        if not data.startswith("settings_danger:confirm:"):
            return

        action = data.rsplit(":", 1)[-1]
        try:
            if action == "db":
                text = await _clear_db()
            elif action == "modules":
                text = await _clear_modules_dir()
            elif action == "cache":
                text = await _clear_cache()
            else:
                await event.answer("Unknown action", alert=True)
                return
        except Exception as e:
            if action == "db":
                text = _("cleardb_error", error=str(e)[:200])
            elif action == "modules":
                text = _("clearmodules_error", error=str(e)[:200])
            else:
                text = _("clearcache_error", error=str(e)[:200])

        await event.edit(text, parse_mode="html", buttons=None)
        await event.answer()

    @kernel.register.command("mcubinfo")
    async def mcubinfo_cmd(event):
        """FAO, 'why userbot'"""
        try:
            await event.edit(
                '<tg-emoji emoji-id="5893368370530621889">🔜</tg-emoji>',
                parse_mode="html",
            )
            info_text = _("mcubinfo_html")
            await event.edit(info_text, parse_mode="html")
        except Exception as e:
            await kernel.handle_error(e, source="mcubinfo_cmd", event=event)
            await event.edit(_("mcubinfo_error"), parse_mode="html")

    kernel.register_callback_handler("lang:", lang_callback_handler)
