# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import json
import os
import shutil

import aiohttp
from telethon import __version__, events
from telethon.tl.types import InputMediaWebPage

from core.lib.loader.module_base import ModuleBase, callback, command
from core.lib.loader.module_config import Boolean, ConfigValue, ModuleConfig
from utils.strings import get_available_locales
from utils.strings import Strings


class SettingsModule(ModuleBase):
    name = "settings"
    version = "1.0.5"
    author = "@hairpin00"
    description = {
        "ru": "Moдyль нacтpoeк (пpeфикc, aлиacы, язык)",
        "en": "Settings module (prefix, aliases, language)",
    }

    strings: dict | Strings = {"name": "settings"}

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

        self.user_emojis = {
            6020965582: "5469888215802482605",
            2037125547: "5467932472379480411",
            779572293: "5470163024989952512",
            8405520863: "5470170528297817805",
            855890735: "5470063433288290290",
        }
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

    async def _resolve_prefix_target_id(
        self, event: events.NewMessage.Event, target_raw: str | None
    ) -> int | None:
        if target_raw:
            target = target_raw.strip()
            if target.lower() == "reply":
                if not event.is_reply:
                    return None
                reply = await event.get_reply_message()
                return getattr(reply, "sender_id", None) if reply else None
            if target.isdigit() or (target.startswith("-") and target[1:].isdigit()):
                return int(target)
            if target.startswith("@"):
                target = target[1:]
            try:
                entity = await self.kernel.client.get_entity(target)
                return getattr(entity, "id", None)
            except Exception:
                return None

        owner_id = getattr(event, "owner_id", None)
        if owner_id is not None:
            return int(owner_id)

        if event.is_reply:
            reply = await event.get_reply_message()
            reply_sender = getattr(reply, "sender_id", None) if reply else None
            if reply_sender is not None:
                return reply_sender

        sender_id = getattr(event, "sender_id", None)
        return int(sender_id) if sender_id is not None else None

    @command(
        "setprefix",
        doc_ru="[пpeфикc] [id/@username/reply] - измeнить пpeфикc oвнepa",
        doc_en="[prefix] [id/@username/reply] - change owner prefix",
    )
    async def cmd_setprefix(self, event: events.NewMessage.Event) -> None:
        args = self.args_raw(event).split()
        piped = getattr(event, "piped", False)
        sender_id = getattr(event, "sender_id", None)
        sender_prefix = self.kernel.get_prefix_for_sender(sender_id)

        if len(args) < 1:
            if piped:
                await self.edit(event, sender_prefix)
                return
            await self.edit(
                event,
                self._s("prefix_usage", prefix=sender_prefix),
                parse_mode="html",
            )
            return

        new_prefix = args[0]
        target_raw = args[1] if len(args) > 1 else None
        cfg = self.config
        any_prefix = cfg.get("settings_any_prefix", False) if cfg else False

        if not any_prefix and len(new_prefix) != 1:
            await self.edit(event, self._s("prefix_one_char"), parse_mode="html")
            return

        target_id = await self._resolve_prefix_target_id(event, target_raw)
        if target_id is None:
            await self.edit(event, self._s("prefix_target_invalid"), parse_mode="html")
            return

        prefix_old = self.kernel.get_prefix_for_sender(target_id)

        owner_prefixes = self.kernel.config.get("owner_prefixes", {})
        if not isinstance(owner_prefixes, dict):
            owner_prefixes = {}

        owner_prefixes = {str(k): str(v) for k, v in owner_prefixes.items() if str(v)}
        owner_prefixes[str(target_id)] = new_prefix

        self.kernel.owner_prefixes = owner_prefixes
        self.kernel.config["owner_prefixes"] = owner_prefixes

        if target_id == getattr(self.kernel, "ADMIN_ID", None):
            self.kernel.custom_prefix = new_prefix
            self.kernel.config["command_prefix"] = new_prefix
        self.kernel.save_config()
        await self.edit(
            event,
            self._s(
                "prefix_owner_changed",
                owner_id=target_id,
                prefix_old=prefix_old,
                prefix=new_prefix,
            ),
            parse_mode="html",
        )

    @command(
        "addalias",
        doc_ru="[aлиac]=[кoмaндa] - дoбaвить aлиac кoмaнды",
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
        doc_ru="[aлиac] - yдaлить aлиac кoмaнды",
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
        doc_ru="пoкaзaть вce aлиacы кoмaнд",
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
        "iloadalias",
        alias="ila",
        doc_ru="[ccылкa / oтвeт нa фaйл] - импopтиpoвaть aлиacы из JSON",
        doc_en="[url / reply to file] - import aliases from JSON",
    )
    async def cmd_iloadalias(self, event: events.NewMessage.Event) -> None:
        args = self.args_raw(event).strip()
        data: str | None = None

        if event.is_reply:
            reply = await event.get_reply_message()
            if reply and reply.file:
                data = await reply.download_media(bytes)
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
            elif reply and reply.text:
                data = reply.text

        if not data and args:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(args, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.text()
                        else:
                            await self.edit(
                                event,
                                self._s("iloadalias_fetch_error", url=args),
                                parse_mode="html",
                            )
                            return
            except Exception:
                data = args

        if not data:
            await self.edit(
                event,
                self._s("iloadalias_usage", prefix=self.kernel.custom_prefix),
                parse_mode="html",
            )
            return

        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            await self.edit(
                event,
                self._s("iloadalias_invalid_json"),
                parse_mode="html",
            )
            return

        aliases_dict = parsed.get("aliases", parsed)

        # Support array format [{"alias": "foo", "command": "bar"}, ...]
        if isinstance(aliases_dict, list):
            converted = {}
            for item in aliases_dict:
                if isinstance(item, dict) and "alias" in item and "command" in item:
                    converted[str(item["alias"])] = str(item["command"])
            aliases_dict = converted

        if not isinstance(aliases_dict, dict):
            await self.edit(
                event,
                self._s("iloadalias_invalid_format"),
                parse_mode="html",
            )
            return

        loaded = 0
        for alias, cmd in aliases_dict.items():
            if not isinstance(alias, str) or not isinstance(cmd, str):
                continue
            self.kernel.aliases[alias] = cmd
            loaded += 1

        self.kernel.config["aliases"] = self.kernel.aliases
        with open(self.kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.kernel.config, f, ensure_ascii=False, indent=2)

        await self.edit(
            event,
            self._s("iloadalias_done", count=loaded),
            parse_mode="html",
        )

    @command(
        "unla",
        doc_ru="экcпopтиpoвaть aлиacы в JSON-фaйл",
        doc_en="export aliases to JSON file",
    )
    async def cmd_unla(self, event: events.NewMessage.Event) -> None:
        import tempfile

        aliases_export = {}
        for alias, cmd in sorted(self.kernel.aliases.items()):
            aliases_export[alias] = cmd

        if not aliases_export:
            await self.edit(
                event,
                self._s("aliases_empty"),
                parse_mode="html",
            )
            return

        export_data = json.dumps(
            {"aliases": aliases_export}, ensure_ascii=False, indent=2
        )

        await self.edit(
            event,
            self._s("unla_uploading"),
            parse_mode="html",
        )

        tmp_path = os.path.join(tempfile.gettempdir(), "aliases.json")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(export_data)

        try:
            await event.edit(
                self._s(
                    "unla_file_caption",
                    prefix=self.kernel.custom_prefix,
                ),
                file=tmp_path,
                parse_mode="html",
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    @command(
        "lang",
        doc_ru="[ru/en] - cмeнить язык юзepбoтa",
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
                label = self.strings.get(f"btn_{locale}", f"🏴☠️ {locale}")
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
            await self.client.delete_messages(event.chat_id, [event.message_id])

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
        doc_ru="yдaлить фaйл бaзы дaнныx",
        doc_en="delete database file",
    )
    async def cmd_cleardb(self, event: events.NewMessage.Event) -> None:
        await self._show_danger_confirm(event, "db", self._s("cleardb_confirm"))

    @command(
        "clearmodules",
        doc_ru="yдaлить вce пoльзoвaтeльcкиe мoдyли",
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
        doc_ru="oчиcтить кэш ядpa",
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
        doc_ru="чтo тaкoe юзepбoт",
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

    @command("mcub", doc_ru="Инфo o MCUB", doc_en="Info MCUB")
    async def cmd_mcub(self, event: events.NewMessage.Event) -> None:
        version_kernel = self.kernel.VERSION
        version_telethon = __version__
        branch = await self.kernel.version_manager.detect_branch()
        commit_sha = await self.kernel.version_manager.get_commit_sha()
        commit_url = await self.kernel.version_manager.get_github_commit_url()
        me = await self.client.get_me()
        user = f'<tg-emoji emoji-id="{self.user_emojis.get(me.id, "5470015630302287916")}">{"Ⓜ️" if me.id in self.user_emojis else "🕳"}</tg-emoji>'
        mcub_emoji = (
            f'{user}<tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
            if me.premium
            else "Mitrich UserBot"
        )

        text = f"""<blockquote>{mcub_emoji} <code>{version_kernel}</code> #<a href="{commit_url}">{commit_sha}</a></blockquote>

<blockquote><tg-emoji emoji-id="5397575638146110953">🌎</tg-emoji> <strong>Telethon-MCUB</strong>: <code>{version_telethon}</code>

<tg-emoji emoji-id="5449918202718985124">🌳</tg-emoji> Branch <strong>{branch}</strong>!</blockquote>"""
        banner_url = "https://raw.githubusercontent.com/hairpin01/MCUB-fork/refs/heads/main/img/info.jpg"

        await event.edit(
            text,
            file=InputMediaWebPage(banner_url, optional=True),
            parse_mode="html",
            invert_media=True,
        )
