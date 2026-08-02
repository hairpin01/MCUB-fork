# scope: inline

from __future__ import annotations

from typing import Any

import utils
from core.lib.loader.module_base import ModuleBase, callback, command
from core.lib.loader.module_config import ConfigValue, ModuleConfig, String
from core.lib.types import Event, InlineMessage


class Installation(ModuleBase):
    name = "installation"
    version = "1.2.1"
    author = "@rich_beluga && @hairpin00"
    description = {
        "en": "Installation guide for MCUB-fork",
        "ru": "Гaйд пo ycтaнoвкe MCUB-fork",
        "uk": "Гайд зі встановлення MCUB-fork",
        "rofl": "Гaйд пo ycтaнoвкe paткo MCUB-fork",
    }

    strings: utils.Strings = {"name": "loader"}

    config = ModuleConfig(
        ConfigValue(
            "emoji_arch",
            '<tg-emoji emoji-id="5301033874367717956">👩💻</tg-emoji>',
            'Эмoдзи paздeлa "Arch Linux"',
            validator=String(),
        ),
        ConfigValue(
            "emoji_debian",
            (
                '<tg-emoji emoji-id="5300838891442413975">👩💻</tg-emoji>'
                '<tg-emoji emoji-id="5300985968302498775">👩💻</tg-emoji>'
            ),
            'Эмoдзи paздeлa "Debian/Ubuntu"',
            validator=String(),
        ),
        ConfigValue(
            "emoji_termux",
            '<tg-emoji emoji-id="5300999883996536855">👩💻</tg-emoji>',
            'Эмoдзи paздeлa "Termux"',
            validator=String(),
        ),
        ConfigValue(
            "emoji_tip",
            '<tg-emoji emoji-id="6010326080961910759">❕</tg-emoji>',
            "эмoдзи TIP",
            validator=String(),
        ),
        ConfigValue(
            "emoji_elif",
            '<tg-emoji emoji-id="5300792557335225091">👩💻</tg-emoji>',
            "эмoдзи elif",
            validator=String(),
        ),
        ConfigValue(
            "emoji_venv",
            '<tg-emoji emoji-id="6010053926064232198">🐱</tg-emoji>',
            "эмoдзи VENV",
            validator=String(),
        ),
    )

    _OWNER_EMOJI: dict[int, str] = {
        6020965582: "5469888215802482605",
        2037125547: "5467932472379480411",
        779572293: "5470163024989952512",
        8405520863: "5470170528297817805",
        855890735: "5470063433288290290",
    }

    async def on_load(self) -> None:
        await super().on_load()
        self._me = None
        defaults = {
            "emoji_arch": '<tg-emoji emoji-id="5301033874367717956">👩💻</tg-emoji>',
            "emoji_debian": (
                '<tg-emoji emoji-id="5300838891442413975">👩💻</tg-emoji>'
                '<tg-emoji emoji-id="5300985968302498775">👩💻</tg-emoji>'
            ),
            "emoji_termux": '<tg-emoji emoji-id="5300999883996536855">👩💻</tg-emoji>',
            "emoji_tip": '<tg-emoji emoji-id="6010326080961910759">❕</tg-emoji>',
            "emoji_venv": '<tg-emoji emoji-id="6010053926064232198">🐱</tg-emoji>',
            "emoji_elif": '<tg-emoji emoji-id="5300792557335225091">👩💻</tg-emoji>',
        }
        config_dict = await self.kernel.get_module_config(self.name, defaults)
        self.config.from_dict(config_dict)
        self.kernel.store_module_config_schema(self.name, self.config)
        clean = {k: v for k, v in self.config.to_dict().items() if v is not None}
        if clean:
            await self.kernel.save_module_config(self.name, clean)

        self._OWNER_EMOJI = self.require_module("config", all_loaded=True).USER_EMOJI

    def _get_platform_emoji(self, key: str) -> str:
        cfg_key = {
            "arch": "emoji_arch",
            "debian": "emoji_debian",
            "termux": "emoji_termux",
        }
        return self.config[cfg_key[key]]

    def _message(self, key: str, **kwargs: Any) -> str:
        return self.strings(key, **kwargs)

    async def _get_mcub_emoji(self) -> str:
        if self._me is None:
            self._me = await self.client.get_me()
        me = self._me

        if not getattr(me, "premium", False):
            return "Mitrich UserBot"

        emoji_id = self._OWNER_EMOJI.get(getattr(me, "id", 0))
        if emoji_id is None:
            return '<tg-emoji emoji-id="5470015630302287916">🕳️</tg-emoji><tg-emoji emoji-id="5469945764069280010">Ⓜ️</tg-emoji><tg-emoji emoji-id="5469943045354984820">Ⓜ️</tg-emoji><tg-emoji emoji-id="5469879466954098867">Ⓜ️</tg-emoji>'

        return (
            f'<tg-emoji emoji-id="{emoji_id}">🔮</tg-emoji>'
            '<tg-emoji emoji-id="5469945764069280010">Ⓜ️</tg-emoji>'
            '<tg-emoji emoji-id="5469943045354984820">Ⓜ️</tg-emoji>'
            '<tg-emoji emoji-id="5469879466954098867">Ⓜ️</tg-emoji>'
        )

    def _build_buttons_choose_category(self) -> list[list[Any]]:
        return [
            [
                self.Button.inline(
                    self.strings("phone"),
                    self.on_choose_category,
                    data="phone",
                    allow_user="all",
                ),
                self.Button.inline(
                    self.strings("vds"),
                    self.on_choose_category,
                    data="vds",
                    allow_user="all",
                ),
            ]
        ]

    def _build_buttons(
        self, phone_only=False, vds_only=False, back_only=False
    ) -> list[list[Any]]:

        if phone_only:
            return [
                [
                    self.Button.inline(
                        self.strings("btn_termux"),
                        self.handle_platform,
                        data="termux",
                        allow_user="all",
                    )
                ],
                [
                    self.Button.inline(
                        self.strings("buttons")("back"),
                        self.on_choose_category,
                        data="back",
                        allow_user="all",
                    )
                ],
            ]
        if vds_only:
            return [
                [
                    self.Button.inline(
                        self.strings("btn_arch"),
                        self.handle_platform,
                        data="arch",
                        allow_user="all",
                    ),
                    self.Button.inline(
                        self.strings("btn_debian"),
                        self.handle_platform,
                        data="debian",
                        allow_user="all",
                    ),
                ],
                [
                    self.Button.inline(
                        self.strings("buttons")("back"),
                        self.on_choose_category,
                        data="back",
                        allow_user="all",
                    )
                ],
            ]
        if back_only:
            return [
                [
                    self.Button.inline(
                        self.strings("buttons")("back"),
                        self.on_choose_category,
                        data="back",
                        allow_user="all",
                    )
                ]
            ]

        return [
            [
                self.Button.inline(
                    self.strings("btn_termux"),
                    self.handle_platform,
                    data="termux",
                    allow_user="all",
                ),
                self.Button.inline(
                    self.strings("btn_arch"),
                    self.handle_platform,
                    data="arch",
                    allow_user="all",
                ),
            ],
            [
                self.Button.inline(
                    self.strings("btn_debian"),
                    self.handle_platform,
                    data="debian",
                    allow_user="all",
                ),
            ],
            [
                self.Button.inline(
                    self.strings("buttons")("back"),
                    self.on_choose_category,
                    data="back",
                    allow_user="all",
                )
            ],
        ]

    @callback(ttl=30)
    async def on_click_loading(self, call: InlineMessage, data=None) -> None:
        mcub_emoji = await self._get_mcub_emoji()
        await call.edit(
            self._message("choose_category", mcub_emoji=mcub_emoji),
            buttons=self._build_buttons_choose_category(),
        )

    @callback(ttl=600)
    async def handle_platform(
        self, call: InlineMessage, data: str | None = None
    ) -> None:
        if data not in {"arch", "debian", "termux"}:
            await call.answer(self.strings("unknown_platform"), alert=True)
            return

        await call.edit(
            self._message(
                data,
                emoji=self._get_platform_emoji(data),
                emoji_elif=self.config["emoji_elif"],
                emoji_tip=self.config["emoji_tip"],
                emoji_venv=self.config["emoji_venv"],
            )
            + f'\n\n{self.strings("link")}',
            buttons=self._build_buttons(back_only=True),
            parse_mode="html",
            link_preview=False,
        )
        await call.answer()

    @callback(ttl=900)
    async def on_choose_category(
        self, call: InlineMessage, data: str | None = None
    ) -> None:
        if not data:
            return await call.answer()

        mcub_emoji = await self._get_mcub_emoji()

        if data == "phone":
            await call.edit(
                self._message("choose", mcub_emoji=mcub_emoji),
                buttons=self._build_buttons(phone_only=True),
            )
        elif data == "vds":
            await call.edit(
                self._message("choose", mcub_emoji=mcub_emoji),
                buttons=self._build_buttons(vds_only=True),
            )
        elif data == "back":
            await call.edit(
                self._message("choose_category", mcub_emoji=mcub_emoji),
                buttons=self._build_buttons_choose_category(),
            )
        else:
            await call.answer()

    @command(
        "installation",
        doc_en="MCUB installation guide",
        doc_uk="Гайд зі встановлення MCUB",
        doc_ru="Гaйд пo ycтaнoвкe MCUB",
        doc_linux="man mcub-install",
        doc_rofl="Гaйд пo ycтaнoвкe paткo MCUB",
    )
    async def cmd_installation(self, event: Event) -> None:

        _, message = await self.inline(
            event.chat_id,
            self.strings("loading"),
            buttons=[[self.Button.inline(" ", self.on_click_loading)]],
        )
        if not message:
            return
        await message.click()
        await event.delete()

    @command(
        "support",
        doc_en="Support MCUB",
        doc_uk="Підтримка MCUB",
        doc_ru="Пoддepжкa MCUB",
        doc_linux="support MCUB",
        doc_rofl="Пoддepжкa MCUB (тyдa и пиши)",
    )
    async def cmd_support(self, event: Event) -> None:
        await self.edit(event, self.strings("link"), link_preview=False)

    @command(
        "source",
        doc_en="Source code MCUB-fork",
        doc_uk="Вихідний код MCUB-fork",
        doc_ru="Иcxoдный кoд MCUB-fork",
        doc_linux="git remote get-url origin",
        doc_rofl="Иcxoдники MCUB-fork (мecтo cтpaдaний)",
    )
    async def cmd_source(self, event: Event) -> None:
        await self.edit(event, self.strings("source"), link_preview=False)
