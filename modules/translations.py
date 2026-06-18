# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

# author: @hairpin00
# version: 1.0.0
# description: Language translations module for MCUB
from telethon import events

from core.lib.loader.module_base import ModuleBase, callback, command
from utils.strings import Strings, get_available_locales, reload_packs


class TranslationsModule(ModuleBase):
    name = "translations"
    version = "1.0.0"
    author = "@hairpin00"
    description = {
        "ru": "Пepeключeниe языкa юзepбoтa",
        "en": "Switch userbot language",
    }

    strings: dict | Strings = {"name": "translations"}

    def _s(self, key: str, **kwargs) -> str:
        """Get localized string."""
        text = self.strings(key)
        return text.format(**kwargs) if kwargs else text

    @command(
        "setlang",
        doc_ru="[ru/en] - пepeключить язык юзepбoтa",
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
            Strings.refresh_all(new_lang)
            await self.edit(event, new_lang)
            return

        if not args:
            button_rows = []
            row = []
            for locale in available_locales:
                label = self.strings("langbutton").get(f"btn_{locale}", f"🏴☠️ {locale}")
                row.append(self.Button.inline(label, self.cb_lang, data=locale))
                if len(row) == 2:
                    button_rows.append(row)
                    row = []
            if row:
                button_rows.append(row)
            success = await self.inline(
                event.chat_id,
                f'<b>{self._s("select_language")}</b>',
                buttons=button_rows,
                reply_to=getattr(event.message, "reply_to", None),
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
        Strings.refresh_all(new_lang)
        await self.edit(
            event,
            f'<b>{self._s("lang_changed", lang=new_lang)}</b>',
            parse_mode="html",
        )

    @callback()
    async def cb_lang(
        self, call: events.CallbackQuery.Event, data: str | None = None
    ) -> None:
        if data:
            self.kernel.config["language"] = data
            self.kernel.save_config()
            Strings.refresh_all(data)
            await self.edit(
                call,
                self._s("lang_changed", lang=data),
                parse_mode="html",
            )
        await call.answer()

    @command(
        "reloadlang",
        doc_ru="пepeзaгpyзить языкoвыe пaкeты c диcкa",
        doc_en="reload language packs from disk",
    )
    async def cmd_reloadlang(self, event: events.NewMessage.Event) -> None:
        reload_packs()
        await self.edit(
            event,
            f'<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> <b>{self._s("reloadlang_done")}</b>',
            parse_mode="html",
        )
