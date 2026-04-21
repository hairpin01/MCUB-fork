# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
from telethon import events

from core.lib.loader.module_base import ModuleBase, bot_command, callback


class CommandModule(ModuleBase):
    name = "command"
    version = "1.2.0"
    author = "@hairpin00"
    description = {"ru": "Обработчики команд бота", "en": "Bot command handlers"}

    strings = {"name": "command"}

    async def on_load(self) -> None:
        bot_client = getattr(self.kernel, "bot_client", None)
        if bot_client is None:
            self.log.debug(
                "bot_client not available, skipping bot handler registration"
            )
            return

        try:
            hello_bot = await self.kernel.db_get("kernel", "HELLO_BOT")
            username = (await self.kernel.bot_client.get_me()).username

            if hello_bot != "True":
                start_sms = await self.kernel.client.send_message(username, "/init")
                self.log.info("Initialization completed via start_init")
                await start_sms.delete()
                await self.kernel.db_set("kernel", "HELLO_BOT", "True")
        except Exception as e:
            self.log.error(f"{self.strings['start_init_error']}: {e}")

    @bot_command("start")
    async def cmd_start(self, event: events.NewMessage.Event) -> None:
        self.log.debug(f"start_handler chat_id={getattr(event, 'chat_id', None)}")
        s = self.strings
        await event.reply(
            file="https://x0.at/ZXNS.mp4",
            message=(
                f"<b>{s['hello']}</b>\n"
                f"{s['developers']}\n"
                f"<blockquote>{s['fork']} @Hairpin00\n"
                f"{s['original']} @Mitrichq</blockquote>"
            ),
            parse_mode="html",
            buttons=[
                [
                    self.Button.url(
                        s["github_repo"], "https://github.com/hairpin01/MCUB-fork"
                    ),
                    self.Button.url(
                        s["original_mcub"],
                        "https://github.com/Mitrichdfklwhcluio/MCUBFB",
                    ),
                ],
                [self.Button.url(s["support"], "https://t.me/+LVnbdp4DNVE5YTFi")],
            ],
        )

    @bot_command("profile")
    async def cmd_profile(self, event: events.NewMessage.Event) -> None:
        self.log.debug(f"profile_handler user_id={getattr(event, 'sender_id', None)}")
        s = self.strings
        user = event.sender
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        await event.reply(
            message=(
                f"<b>{s['profile']}</b>\n"
                f"<b>{s['name']}</b> {first_name} {last_name}\n"
                f"<b>{s['prefix']}</b> <code>{self.kernel.custom_prefix}</code>\n"
                f"<b>{s['kernel_version']}</b> {self.kernel.VERSION}"
            ),
            parse_mode="html",
            buttons=[
                [
                    self.Button.url(
                        s["github_repo"], "https://github.com/hairpin01/MCUB-fork"
                    )
                ]
            ],
        )

    @bot_command("init")
    async def cmd_init(self, event: events.NewMessage.Event) -> None:
        s = self.strings
        if not event.is_private or event.sender.bot:
            return
        if (
            not hasattr(self.kernel, "ADMIN_ID")
            or self.kernel.ADMIN_ID is None
            or int(event.sender_id) != int(self.kernel.ADMIN_ID)
        ):
            return

        await self.kernel.bot_client.send_file(
            event.chat_id, file="https://x0.at/Y4ie.mp4"
        )
        gif_message = await self.kernel.bot_client.send_message(
            event.chat_id,
            message=s["choose_language"],
            buttons=[
                [
                    self.Button.inline(
                        "RU",
                        self.cb_language,
                        data="start_lang_ru",
                        style="primary",
                    ),
                    self.Button.inline(
                        "EN",
                        self.cb_language,
                        data="start_lang_en",
                        style="primary",
                    ),
                ]
            ],
            parse_mode="html",
        )
        try:
            await self.client.delete_messages(event.chat_id, [event.message.id])
        except Exception:
            pass

    @bot_command("delete_mcub_bot")
    async def cmd_delete_bot(self, event: events.NewMessage.Event) -> None:
        s = self.strings
        if not event.is_group and not event.is_channel:
            return
        if not self.kernel.is_admin:
            return

        await event.reply(message=f"<b>{s['goodbye']}</b>", parse_mode="html")
        await self.kernel.bot_client.delete_dialog(event.chat_id)

    @bot_command("ping")
    async def cmd_ping(self, event: events.NewMessage.Event) -> None:
        await event.reply(
            '<blockquote><tg-emoji emoji-id="6010179991944305029">☺️</tg-emoji> Pong!</blockquote>',
            parse_mode="html",
        )

    @callback()
    async def cb_language(
        self, event: events.CallbackQuery.Event, data: str | None = None
    ) -> None:
        lang = data.replace("start_lang_", "") if data else "en"

        self.kernel.config["language"] = lang
        self.kernel.save_config()

        # Get original strings dict from class
        strings_dict = type(self).__dict__.get("strings")

        # Create new Strings instance with new language
        from utils.strings import Strings

        if strings_dict:
            self._strings = Strings(self.kernel, strings_dict)

        s = self.strings

        text = (
            f"<b>{self.strings('hello_installed')}</b>\n\n"
            f"<b>{self.strings('main_commands')}</b>\n"
            f"<blockquote>{self.strings('setprefix')} <code>.setprefix {self.strings('new_prefix')}</code>\n"
            f"{self.strings('logs')} <code>.logs</code>\n"
            f"{self.strings('info')} <code>.info</code>\n"
            f"{self.strings('ping')} <code>.ping</code></blockquote>\n\n"
            f"<b>{self.strings('module_management')}</b>\n"
            f"<blockquote>{self.strings('load')} <code>.iload</code>\n"
            f"{self.strings('remove')} <code>.um [{self.strings('module_name')}]</code>\n"
            f"{self.strings('list_modules')} <code>.dlm</code></blockquote>\n\n"
        )

        await event.edit(
            text,
            parse_mode="html",
            buttons=[
                self.Button.url(
                    self.strings("github_repo"),
                    "https://github.com/hairpin01/MCUB-fork",
                )
            ],
        )
        await event.answer(self.strings("setup_completed"), alert=True)

        await asyncio.sleep(1)
        backup_buttons = [
            [
                self.Button.inline(
                    "Yes / Да", self.cb_backup, data="backup_setup_yes", style="success"
                ),
                self.Button.inline(
                    "No / Нет", self.cb_backup, data="backup_setup_no", style="danger"
                ),
            ]
        ]
        await self.kernel.bot_client.send_message(
            event.sender_id,
            f"<b>{self.strings('backup_setup')}</b>\n\n{self.strings('backup_enable')}",
            parse_mode="html",
            buttons=backup_buttons,
        )

    @callback()
    async def cb_backup(
        self, event: events.CallbackQuery.Event, data: str | None = None
    ) -> None:
        s = self.strings
        if not data:
            return

        if data.startswith("backup_setup_"):
            enable = data.replace("backup_setup_", "") == "yes"
            if enable:
                interval_buttons = [
                    [
                        self.Button.inline(
                            "2h",
                            self.cb_backup,
                            data="backup_interval:2",
                            style="primary",
                        ),
                        self.Button.inline(
                            "4h",
                            self.cb_backup,
                            data="backup_interval:4",
                            style="primary",
                        ),
                        self.Button.inline(
                            "6h",
                            self.cb_backup,
                            data="backup_interval:6",
                            style="primary",
                        ),
                    ],
                    [
                        self.Button.inline(
                            "12h",
                            self.cb_backup,
                            data="backup_interval:12",
                            style="primary",
                        ),
                        self.Button.inline(
                            "24h",
                            self.cb_backup,
                            data="backup_interval:24",
                            style="primary",
                        ),
                    ],
                    [
                        self.Button.inline(
                            self.strings("backup_skip"),
                            self.cb_backup,
                            data="backup_skip",
                            style="primary",
                        ),
                    ],
                ]
                await event.edit(
                    f"<b>{s['backup_setup']}</b>\n\n{s['backup_interval']}",
                    parse_mode="html",
                    buttons=interval_buttons,
                )
            else:
                await event.edit(
                    f"<b>{s['backup_setup']}</b>\n\n{s['backup_disabled']}",
                    parse_mode="html",
                )
                await event.answer(s["backup_disabled"], alert=True)

        elif data.startswith("backup_interval:"):
            interval = int(data.replace("backup_interval:", ""))
            backup_mod = self.require_module("userbot-backup")
            if backup_mod:
                mod_name = backup_mod.name
                live_cfg = getattr(self.kernel, "_live_module_configs", {}).get(
                    mod_name
                )
                if live_cfg:
                    live_cfg["backup_interval_hours"] = interval
                    await self.kernel.save_module_config(mod_name, live_cfg.to_dict())
                else:
                    await self.kernel.save_module_config(
                        mod_name,
                        {
                            "backup_chat_id": None,
                            "backup_interval_hours": interval,
                            "last_backup_time": None,
                            "backup_count": 0,
                            "enable_auto_backup": True,
                        },
                    )
                chat = await backup_mod.ensure_backup_chat()
                if chat:
                    await event.edit(
                        f"<b>{s['backup_setup']}</b>\n\n{s['backup_created']}\n\nInterval: {interval}h",
                        parse_mode="html",
                    )
                else:
                    await event.edit(
                        f"<b>{s['backup_setup']}</b>\n\n{s['backup_enabled']} ({interval}h)",
                        parse_mode="html",
                    )
                await event.answer(f"{s['backup_enabled']} ({interval}h)", alert=True)
            else:
                await event.edit(s["backup_not_found"], parse_mode="html")

        elif data == "backup_skip":
            await event.edit(
                f"<b>{s['backup_setup']}</b>\n\n{s['backup_disabled']}",
                parse_mode="html",
            )
            await event.answer(s["backup_disabled"], alert=True)

    @callback()
    async def cb_backup_interval(self, event: events.CallbackQuery.Event) -> None:
        interval = int(
            event.data.decode().replace("backup_interval:", "")
            if isinstance(event.data, bytes)
            else event.data.replace("backup_interval:", "")
        )

        backup_mod = self.require_module("userbot-backup")
        if backup_mod:
            mod_name = backup_mod.name
            live_cfg = getattr(self.kernel, "_live_module_configs", {}).get(mod_name)
            if live_cfg:
                live_cfg["backup_interval_hours"] = interval
                await self.kernel.save_module_config(mod_name, live_cfg.to_dict())
            else:
                await self.kernel.save_module_config(
                    mod_name,
                    {
                        "backup_chat_id": None,
                        "backup_interval_hours": interval,
                        "last_backup_time": None,
                        "backup_count": 0,
                        "enable_auto_backup": True,
                    },
                )

            chat = await backup_mod.ensure_backup_chat()
            if chat:
                await event.edit(
                    f"<b>{self.strings('backup_setup')}</b>\n\n{self.strings('backup_created')}\n\nInterval: {interval}h",
                    parse_mode="html",
                )
            else:
                await event.edit(
                    f"<b>{self.strings('backup_setup')}</b>\n\n{self.strings('backup_enabled')} ({interval}h)",
                    parse_mode="html",
                )
            await event.answer(
                f"{self.strings('backup_enabled')} ({interval}h)", alert=True
            )
        else:
            await event.edit(self.strings("backup_not_found"), parse_mode="html")

    @callback()
    async def cb_backup_skip(self, event: events.CallbackQuery.Event) -> None:
        await event.edit(
            f"<b>{self.strings('backup_setup')}</b>\n\n{self.strings('backup_disabled')}",
            parse_mode="html",
        )
        await event.answer(self.strings("backup_disabled"), alert=True)
