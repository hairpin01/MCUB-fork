# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import json
import os
import shutil

from telethon import events

from core.lib.loader.module_base import ModuleBase, callback, command
from core.lib.loader.module_config import Boolean, ConfigValue, ModuleConfig
from utils.strings import get_available_locales


class SettingsModule(ModuleBase):
    name = "settings"
    version = "1.0.5"
    author = "@hairpin00"
    description = {
        "ru": "Модуль настроек (префикс, алиасы, язык)",
        "en": "Settings module (prefix, aliases, language)",
    }

    strings = {"name": "settings"}

    config = ModuleConfig(
        ConfigValue(
            "settings_any_prefix",
            False,
            description="Allow multi-character prefixes (bypass 1-char restriction)",
            validator=Boolean(default=False),
        ),
    )

    async def on_load(self) -> None:
        config_dict = await self.kernel.get_module_config(
            self.name,
            {"settings_any_prefix": False},
        )
        self.config.from_dict(config_dict)
        config_dict_clean = {
            k: v for k, v in self.config.to_dict().items() if v is not None
        }
        if config_dict_clean:
            await self.kernel.save_module_config(self.name, config_dict_clean)
        self.kernel.store_module_config_schema(self.name, self.config)

    def _s(self, key: str, **kwargs) -> str:
        """Get localized string."""
        text = self.strings(key)
        return text.format(**kwargs) if kwargs else text

    def _get_db_path(self) -> str:
        db_manager = getattr(self.kernel, "db_manager", None)
        if db_manager and hasattr(db_manager, "_resolve_db_file"):
            return os.path.abspath(db_manager._resolve_db_file())
        return os.path.abspath("userbot.db")

    @command(
        "setprefix",
        doc_ru="[префикс] - изменить префикс команд",
        doc_en="[prefix] - change command prefix",
    )
    async def cmd_setprefix(self, event: events.NewMessage.Event) -> None:
        args = self.args_raw(event).split()
        piped = getattr(event, "piped", False)

        if len(args) < 1:
            if piped:
                await self.edit(event, self.kernel.custom_prefix)
                return
            await self.edit(
                event,
                self._s("prefix_usage", prefix=self.kernel.custom_prefix),
                parse_mode="html",
            )
            return

        new_prefix = args[0]
        cfg = self.config
        any_prefix = cfg.get("settings_any_prefix", False) if cfg else False

        if not any_prefix and len(new_prefix) != 1:
            await self.edit(event, self._s("prefix_one_char"), parse_mode="html")
            return

        prefix_old = self.kernel.custom_prefix
        self.kernel.custom_prefix = new_prefix
        self.kernel.config["command_prefix"] = new_prefix
        self.kernel.save_config()

        await self.edit(
            event,
            self._s("prefix_changed", prefix=new_prefix, prefix_old=prefix_old),
            parse_mode="html",
        )

    @command(
        "addalias",
        doc_ru="[алиас]=[команда] - добавить алиас команды",
        doc_en="[alias]=[command] - add command alias",
    )
    async def cmd_addalias(self, event: events.NewMessage.Event) -> None:
        parts_text = event.text.split(None, 1)
        args = parts_text[1].strip() if len(parts_text) > 1 else ""
        if "=" not in args:
            await self.edit(
                event,
                self._s("alias_usage", prefix=self.kernel.custom_prefix),
                parse_mode="html",
            )
            return

        parts = args.split("=", 1)
        if len(parts) < 2:
            await self.edit(
                event,
                self._s("alias_usage", prefix=self.kernel.custom_prefix),
                parse_mode="html",
            )
            return

        alias = parts[0].strip()
        command = parts[1].strip()

        if not alias or not command:
            await self.edit(
                event,
                self._s("alias_usage", prefix=self.kernel.custom_prefix),
                parse_mode="html",
            )
            return

        command_base = command.split()[0]
        if command_base not in self.kernel.command_handlers:
            await self.edit(
                event,
                self._s("alias_target_not_found", command=command_base),
                parse_mode="html",
            )
            return

        self.kernel.aliases[alias] = command
        self.kernel.config["aliases"] = self.kernel.aliases

        with open(self.kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.kernel.config, f, ensure_ascii=False, indent=2)

        await self.edit(
            event,
            self._s(
                "alias_created",
                prefix=self.kernel.custom_prefix,
                alias=alias,
                command=command,
            ),
            parse_mode="html",
        )

    @command(
        "delalias",
        doc_ru="[алиас] - удалить алиас команды",
        doc_en="[alias] - delete command alias",
    )
    async def cmd_delalias(self, event: events.NewMessage.Event) -> None:
        args = event.text[len(self.kernel.custom_prefix) + 8 :].strip()
        if not args:
            await self.edit(
                event,
                self._s("delalias_usage", prefix=self.kernel.custom_prefix),
                parse_mode="html",
            )
            return

        if args not in self.kernel.aliases:
            await self.edit(
                event,
                self._s("delalias_not_found", alias=args),
                parse_mode="html",
            )
            return

        del self.kernel.aliases[args]
        self.kernel.config["aliases"] = self.kernel.aliases

        with open(self.kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.kernel.config, f, ensure_ascii=False, indent=2)

        await self.edit(
            event,
            self._s(
                "delalias_done",
                prefix=self.kernel.custom_prefix,
                alias=args,
            ),
            parse_mode="html",
        )

    @command(
        "aliases",
        doc_ru="показать все алиасы команд",
        doc_en="list all command aliases",
    )
    async def cmd_aliases(self, event: events.NewMessage.Event) -> None:
        piped = getattr(event, "piped", False)

        if not self.kernel.aliases:
            if piped:
                await self.edit(event, "no aliases")
                return
            await self.edit(event, self._s("aliases_empty"))
            return

        lines = []
        for alias, target in sorted(self.kernel.aliases.items()):
            lines.append(f"{alias} -> {target}")

        text = "\n".join(lines)

        if piped:
            await self.edit(event, text)
            return

        lines_html = []
        for alias, target in sorted(self.kernel.aliases.items()):
            lines_html.append(
                f"<code>{self.kernel.custom_prefix}{alias} </code>-><code> {self.kernel.custom_prefix}{target}</code>"
            )

        text_html = "\n".join(lines_html)
        await self.edit(
            event,
            f"<blockquote expandable>{text_html}</blockquote>",
            parse_mode="html",
        )

    @command(
        "lang",
        doc_ru="[ru/en] - сменить язык юзербота",
        doc_en="[ru/en] - switch userbot language",
    )
    async def cmd_lang(self, event: events.NewMessage.Event) -> None:
        args = self.args_raw(event).split()
        piped = getattr(event, "piped", False)

        available_locales = get_available_locales()

        if piped:
            if len(args) < 2:
                await self.edit(event, self.kernel.config.get("language", "en"))
                return
            new_lang = args[1].lower()
            if new_lang not in available_locales:
                await self.edit(event, ", ".join(available_locales))
                return
            self.kernel.config["language"] = new_lang
            self.kernel.save_config()
            await self.edit(event, new_lang)
            return

        if len(args) < 1:
            # Build buttons in rows of 2 using class-style Button
            button_rows = []
            row = []
            for locale in available_locales:
                label = self.strings.get(f"btn_{locale}", f"🏴‍☠️ {locale}")
                row.append(self.Button.inline(label, self.cb_lang, data=locale))
                if len(row) == 2:
                    button_rows.append(row)
                    row = []
            if row:
                button_rows.append(row)
            success = await self.inline(
                event.chat_id,
                self._s("select_language"),
                buttons=button_rows,
            )
            if success:
                await event.delete()
            return

        new_lang = args[0].lower()
        if new_lang not in available_locales:
            await self.edit(event, ", ".join(available_locales))
            return

        self.kernel.config["language"] = new_lang
        self.kernel.save_config()
        await self.edit(
            event,
            self._s("lang_changed", lang=new_lang),
            parse_mode="html",
        )

    @callback()
    async def cb_lang(
        self, call: events.CallbackQuery.Event, data: str | None = None
    ) -> None:
        if data:
            self.kernel.config["language"] = data
            self.kernel.save_config()
            await self.edit(
                call,
                self._s("lang_changed", lang=data),
                parse_mode="html",
            )
        await call.answer()

    async def _show_danger_confirm(self, event, action: str, text: str) -> None:
        success, _form_message = await self.inline(
            event.chat_id,
            text,
            buttons=[
                [
                    self.Button.inline(
                        self._s("btn_confirm"),
                        self.cb_settings_danger,
                        data=action,
                        style="danger",
                    ),
                    self.Button.inline(
                        self._s("btn_cancel"),
                        self.cb_settings_danger,
                        data="cancel",
                        style="primary",
                    ),
                ]
            ],
        )
        if success:
            await event.delete()

    async def _clear_db(self) -> str:
        db_path = self._get_db_path()
        conn = getattr(self.kernel, "db_conn", None)
        if conn:
            await conn.close()
            if getattr(self.kernel, "db_manager", None):
                self.kernel.db_manager.conn = None

        if not os.path.exists(db_path):
            return self._s("cleardb_missing", path=db_path)

        os.remove(db_path)
        return self._s("cleardb_done", path=db_path)

    async def _clear_modules_dir(self) -> str:
        modules_dir = getattr(self.kernel, "MODULES_LOADED_DIR", "modules_loaded")
        modules_dir = os.path.abspath(modules_dir)
        if not os.path.isdir(modules_dir):
            return self._s("clearmodules_missing", path=modules_dir)

        deleted = 0
        for name in os.listdir(modules_dir):
            target = os.path.join(modules_dir, name)
            if os.path.isdir(target) and not os.path.islink(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
            deleted += 1

        if deleted == 0:
            return self._s("clearmodules_missing", path=modules_dir)
        return self._s("clearmodules_done", count=deleted)

    async def _clear_cache(self) -> str:
        if getattr(self.kernel, "cache", None):
            self.kernel.cache.clear()
        return self._s("clearcache_done")

    @command(
        "cleardb",
        doc_ru="удалить файл базы данных",
        doc_en="delete database file",
    )
    async def cmd_cleardb(self, event: events.NewMessage.Event) -> None:
        await self._show_danger_confirm(event, "db", self._s("cleardb_confirm"))

    @command(
        "clearmodules",
        doc_ru="удалить все пользовательские модули",
        doc_en="delete all user modules",
    )
    async def cmd_clearmodules(self, event: events.NewMessage.Event) -> None:
        await self._show_danger_confirm(
            event,
            "modules",
            self._s(
                "clearmodules_confirm",
                path=os.path.abspath(self.kernel.MODULES_LOADED_DIR),
            ),
        )

    @command(
        "clearcache",
        doc_ru="очистить кэш ядра",
        doc_en="clear kernel cache",
    )
    async def cmd_clearcache(self, event: events.NewMessage.Event) -> None:
        await self._show_danger_confirm(event, "cache", self._s("clearcache_confirm"))

    @callback()
    async def cb_settings_danger(
        self, call: events.CallbackQuery.Event, data: str | None = None
    ) -> None:
        if not data or data == "cancel":
            await call.answer()
            return

        try:
            if data == "db":
                text = await self._clear_db()
            elif data == "modules":
                text = await self._clear_modules_dir()
            elif data == "cache":
                text = await self._clear_cache()
            else:
                await call.answer("Unknown action", alert=True)
                return
        except Exception as e:
            if data == "db":
                text = self._s("cleardb_error", error=str(e)[:200])
            elif data == "modules":
                text = self._s("clearmodules_error", error=str(e)[:200])
            else:
                text = self._s("clearcache_error", error=str(e)[:200])

        await self.edit(call, text, parse_mode="html", buttons=None)
        await call.answer()

    @command(
        "mcubinfo",
        doc_ru="что такое юзербот",
        doc_en="what is a userbot",
    )
    async def cmd_mcubinfo(self, event: events.NewMessage.Event) -> None:
        try:
            await self.edit(
                event,
                '<tg-emoji emoji-id="5893368370530621889">🔜</tg-emoji>',
                parse_mode="html",
            )
            info_text = self._s("mcubinfo_html")
            await self.edit(event, info_text, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="mcubinfo", event=event)
            await self.edit(event, self._s("mcubinfo_error"), parse_mode="html")

    @command(
        "piped",
        doc_ru="[on/off] - включить/выключить pipeline",
        doc_en="[on/off] - enable/disable command pipeline",
    )
    async def cmd_piped(self, event: events.NewMessage.Event) -> None:
        if getattr(event, "piped", False):
            await self.edit(event, self.kernel.config.get("piped", False))
            return

        current = self.kernel.config.get("piped", True)
        self.kernel.config["piped"] = not current
        self.kernel.save_config()

        if self.kernel.config["piped"]:
            await self.edit(event, self._s("piped_on"), parse_mode="html")
        else:
            await self.edit(event, self._s("piped_off"), parse_mode="html")
