# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

# author: @hairpin00
# version: 1.1.0
# description: Language translations module for MCUB
import html
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import aiohttp
import yaml
from telethon import events

from core.langpacks import CUSTOM_LANGPACKS_DIR
from core.lib.loader.module_base import ModuleBase, callback, command
from utils.strings import Strings, get_available_locales, reload_packs

_MAX_LANGPACK_SIZE = 2 * 1024 * 1024
_LOCALE_RE = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}", re.IGNORECASE)
_YAML_SUFFIXES = {".yaml", ".yml"}


class TranslationsModule(ModuleBase):
    name = "translations"
    version = "1.1.0"
    author = "@hairpin00"
    description = {
        "ru": "Пepeключeниe языкa юзepбoтa",
        "uk": "Перемикання мови юзербота",
        "en": "Switch userbot language",
    }

    strings: dict | Strings = {"name": "translations"}

    def _s(self, key: str, **kwargs) -> str:
        """Get a localized string with the English langpack as fallback."""
        text = self.strings.get(key, f"[{key}]")
        return str(text).format(**kwargs) if kwargs else str(text)

    def _language_labels(self) -> dict[str, str]:
        """Return explicitly named language buttons from the active strings."""
        group = self.strings.get("langbutton")
        if group is None or not hasattr(group, "get"):
            return {}

        labels: dict[str, str] = {}
        for locale in get_available_locales():
            # ``btn_`` is the current MCUB spelling; ``button_`` is accepted for
            # third-party packs and for compatibility with the documented form.
            for key in (f"button_{locale}", f"btn_{locale}"):
                value = group.get(key)
                if isinstance(value, str) and value.strip():
                    labels[locale] = value
                    break
        return labels

    def _split_locales(self) -> tuple[list[str], list[str], dict[str, str]]:
        locales = get_available_locales()
        labels = self._language_labels()
        primary = [locale for locale in locales if locale in labels]
        other = [locale for locale in locales if locale not in labels]
        return primary, other, labels

    def _locale_button_rows(
        self, locales: list[str], labels: dict[str, str]
    ) -> list[list]:
        rows: list[list] = []
        row: list = []
        for locale in locales:
            label = labels.get(locale, f"🏴‍☠️ {locale}")
            row.append(self.Button.inline(label, self.cb_lang, data=locale))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        return rows

    def _main_language_buttons(self) -> list[list]:
        primary, _other, labels = self._split_locales()
        rows = self._locale_button_rows(primary, labels)
        rows.append(
            [
                self.Button.inline(
                    self._s("other_languages"),
                    self.cb_other_languages,
                    style="primary",
                )
            ]
        )
        return rows

    def _other_languages_view(self, callback_event) -> tuple[str, list[list]]:
        _primary, other, labels = self._split_locales()
        rows = self._locale_button_rows(other, labels)
        text = f'<b>{self._s("select_other_language")}</b>'
        if not other:
            text += f'\n\n<i>{self._s("no_other_languages")}</i>'

        rows.append(
            [
                self.Button.input(
                    self._s("install_language"),
                    self._install_language_input,
                    placeholder="https://",
                    allow_user=getattr(callback_event, "sender_id", None),
                    style="success",
                    data={"callback_event": callback_event},
                )
            ]
        )
        rows.append(
            [
                self.Button.inline(
                    self._s("back_to_languages"),
                    self.cb_languages_main,
                    style="primary",
                )
            ]
        )
        return text, rows

    @staticmethod
    def _langpack_filename(response: aiohttp.ClientResponse, source_url: str) -> str:
        candidates: list[str] = []
        disposition = response.headers.get("Content-Disposition", "")
        for part in disposition.split(";"):
            key, separator, value = part.strip().partition("=")
            if not separator or key.lower() not in {"filename", "filename*"}:
                continue
            value = value.strip().strip("\"'")
            if key.lower() == "filename*" and "''" in value:
                value = value.split("''", 1)[1]
            candidates.append(unquote(value))

        for candidate_url in (str(response.url), source_url):
            candidates.append(Path(unquote(urlparse(candidate_url).path)).name)

        for candidate in candidates:
            name = Path(candidate).name
            path = Path(name)
            if path.suffix.lower() not in _YAML_SUFFIXES:
                continue
            locale = path.stem.lower()
            if ".." in locale or _LOCALE_RE.fullmatch(locale) is None:
                continue
            return f"{locale}.yaml"

        raise ValueError("URL must point to a .yaml or .yml file")

    async def _download_language(self, url: str) -> tuple[str, Path]:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("only HTTP(S) URLs are supported")

        timeout = aiohttp.ClientTimeout(total=30)
        headers = {"User-Agent": "MCUB-langpack-installer/1.1"}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, allow_redirects=True) as response:
                response.raise_for_status()
                filename = self._langpack_filename(response, url)

                if (response.content_length or 0) > _MAX_LANGPACK_SIZE:
                    raise ValueError("language pack is larger than 2 MiB")

                chunks: list[bytes] = []
                size = 0
                async for chunk in response.content.iter_chunked(64 * 1024):
                    size += len(chunk)
                    if size > _MAX_LANGPACK_SIZE:
                        raise ValueError("language pack is larger than 2 MiB")
                    chunks.append(chunk)

        try:
            text = b"".join(chunks).decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("language pack must be UTF-8") from exc

        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError("downloaded file contains invalid YAML") from exc
        if not isinstance(data, dict) or not data:
            raise ValueError("YAML root must be a non-empty mapping")

        CUSTOM_LANGPACKS_DIR.mkdir(parents=True, exist_ok=True)
        target = CUSTOM_LANGPACKS_DIR / filename
        temporary = target.with_suffix(target.suffix + ".tmp")
        try:
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

        reload_packs()
        return target.stem, target

    async def _install_language_input(
        self, _input_event, text: str, data: dict | None = None
    ) -> None:
        callback_event = (data or {}).get("callback_event")
        if callback_event is None:
            self.log.error("Language input has no callback event to edit")
            return

        url = (text or "").strip()
        if not url:
            return

        try:
            locale, target = await self._download_language(url)
        except Exception as exc:
            self.log.warning("Failed to install language pack: %s", exc)
            _text, buttons = self._other_languages_view(callback_event)
            error = html.escape(str(exc)[:300] or type(exc).__name__)
            await self.edit(
                callback_event,
                self._s("install_language_error", error=error),
                parse_mode="html",
                buttons=buttons,
            )
            return

        labels = self._language_labels()
        label = labels.get(locale, f"🏴‍☠️ {locale}")
        try:
            shown_path = target.relative_to(CUSTOM_LANGPACKS_DIR.parents[2])
        except ValueError:
            shown_path = target
        buttons = [
            [
                self.Button.inline(
                    self._s("use_installed_language", lang=locale),
                    self.cb_lang,
                    data=locale,
                    style="success",
                )
            ],
            [
                self.Button.inline(
                    self._s("other_languages"),
                    self.cb_other_languages,
                    style="primary",
                ),
                self.Button.inline(
                    self._s("back_to_languages"),
                    self.cb_languages_main,
                    style="primary",
                ),
            ],
        ]
        await self.edit(
            callback_event,
            self._s(
                "install_language_success",
                lang=html.escape(locale),
                path=html.escape(str(shown_path)),
            ),
            parse_mode="html",
            buttons=buttons,
        )
        self.log.info("Installed language pack as %s (%s)", label, target)

    @command(
        "setlang",
        doc_ru="[ru/en] - пepeключить язык юзepбoтa",
        doc_en="[ru/en] - switch userbot language",
        doc_uk="[ru/en/uk] - перемкнути мову юзербота",
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
            success = await self.inline(
                event.chat_id,
                f'<b>{self._s("select_language")}</b>',
                buttons=self._main_language_buttons(),
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
    async def cb_languages_main(
        self, call: events.CallbackQuery.Event, data: str | None = None
    ) -> None:
        await self.edit(
            call,
            f'<b>{self._s("select_language")}</b>',
            parse_mode="html",
            buttons=self._main_language_buttons(),
        )
        await call.answer()

    @callback()
    async def cb_other_languages(
        self, call: events.CallbackQuery.Event, data: str | None = None
    ) -> None:
        text, buttons = self._other_languages_view(call)
        await self.edit(call, text, parse_mode="html", buttons=buttons)
        await call.answer()

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
        doc_uk="перезавантажити мовні пакети з диска",
    )
    async def cmd_reloadlang(self, event: events.NewMessage.Event) -> None:
        reload_packs()
        await self.edit(
            event,
            f'<tg-emoji emoji-id="5902002809573740949">✅</tg-emoji> <b>{self._s("reloadlang_done")}</b>',
            parse_mode="html",
        )
