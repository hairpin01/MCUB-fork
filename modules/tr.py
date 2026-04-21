# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from telethon import events

from core.lib.loader.module_base import ModuleBase, command
from core.lib.loader.module_config import Choice, ConfigValue, ModuleConfig


class TrModule(ModuleBase):
    name = "tr"
    version = "1.0.3"
    author = "@hairpin00"
    description = {
        "ru": "Переводчик через Google Translate",
        "en": "Translator using Google Translate API",
    }

    strings = {"name": "tr"}

    EMOJI_LOADING = '<tg-emoji emoji-id="5323463142775202324">🏓</tg-emoji>'
    EMOJI_ERROR = '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji>'

    config = ModuleConfig(
        ConfigValue(
            "tr_lang",
            "ru",
            description="Default translation language (e.g., ru, en, es)",
            validator=Choice(
                choices=[
                    "ru",
                    "en",
                    "es",
                    "fr",
                    "de",
                    "it",
                    "pt",
                    "uk",
                    "zh",
                    "ja",
                    "ko",
                    "ar",
                ],
                default="ru",
            ),
        ),
    )

    async def on_load(self) -> None:
        config_dict = await self.kernel.get_module_config(
            self.name,
            {"tr_lang": "ru"},
        )
        self.config.from_dict(config_dict)
        config_dict_clean = {
            k: v for k, v in self.config.to_dict().items() if v is not None
        }
        if config_dict_clean:
            await self.kernel.save_module_config(self.name, config_dict_clean)
        self.kernel.store_module_config_schema(self.name, self.config)

    async def _translate_text(self, text: str, dest: str = "ru") -> str:
        s = self.strings
        try:
            encoded_text = quote(text)
            url = "https://translate.googleapis.com/translate_a/single"

            params = {
                "client": "gtx",
                "sl": "auto",
                "tl": dest,
                "dt": "t",
                "q": encoded_text,
            }

            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{url}?{query_string}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            }

            req = Request(full_url, headers=headers)

            def sync_request():
                try:
                    with urlopen(req, timeout=10) as response:
                        data = response.read()
                        decoded_data = data.decode("utf-8")
                        return json.loads(decoded_data)
                except (URLError, HTTPError) as e:
                    raise Exception(f"{s['network_error']} {e!s}")

            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(None, sync_request)

            if data and len(data) > 0 and data[0]:
                translated_parts = []
                for sentence in data[0]:
                    if sentence and len(sentence) > 0 and sentence[0]:
                        translated_parts.append(str(sentence[0]))
                return "".join(translated_parts)
            else:
                return s["translation_failed"]

        except TimeoutError:
            return s["request_timeout"]
        except json.JSONDecodeError:
            return s["decode_error"]
        except Exception as e:
            return f"{s['translation_error_generic']} {e!s}"

    @command(
        "tr",
        doc_ru="перевести текст через Google Translate",
        doc_en="translate text using Google Translate",
    )
    async def cmd_tr(self, event: events.NewMessage.Event) -> None:
        try:
            s = self.strings
            quote_text = None
            if event.reply_to and hasattr(event.reply_to, "quote_text"):
                quote_text = event.reply_to.quote_text

            args = self.args_raw(event).split()

            cfg = self.config
            target_lang = cfg.get("tr_lang", "ru") if cfg else "ru"
            text_to_translate = None

            if quote_text:
                text_to_translate = quote_text

                if len(args) > 0:
                    lang_arg = args[0]
                    if len(lang_arg) == 2 and lang_arg.isalpha():
                        target_lang = lang_arg
                        if len(args) > 1:
                            text_to_translate = " ".join(args[1:])

            elif not text_to_translate:
                reply = await event.get_reply_message()
                reply_text = reply.text if reply else None

                if len(args) == 0:
                    if reply_text:
                        text_to_translate = reply_text
                    else:
                        await self.edit(event, s["no_args"])
                        return

                elif len(args) == 1:
                    arg1 = args[0]

                    if len(arg1) == 2 and arg1.isalpha():
                        if reply_text:
                            target_lang = arg1
                            text_to_translate = reply_text
                        else:
                            await self.edit(
                                event,
                                f"{self.EMOJI_ERROR} <b>{s['specify_text']}</b>",
                                parse_mode="html",
                            )
                            return
                    else:
                        text_to_translate = arg1

                elif len(args) >= 2:
                    arg1 = args[0]
                    if len(arg1) == 2 and arg1.isalpha():
                        target_lang = arg1
                        text_to_translate = " ".join(args[1:])
                    else:
                        text_to_translate = " ".join(args)

            if not text_to_translate:
                await self.edit(
                    event,
                    f"{self.EMOJI_ERROR} <b>{s['no_text']}</b>",
                    parse_mode="html",
                )
                return

            status_msg = await self.edit(
                event, f"{self.EMOJI_LOADING} <b>{s['loading']}</b>", parse_mode="html"
            )

            translated = await self._translate_text(text_to_translate, target_lang)

            await status_msg.edit(translated)
            return event

        except Exception as e:
            await self.kernel.handle_error(e, source="tr", event=event)
            s = self.strings
            await self.edit(
                event,
                f"{self.EMOJI_ERROR} <b>{s['translation_error']}</b>\n<code>{str(e)[:200]}</code>",
                parse_mode="html",
            )
