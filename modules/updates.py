# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import os
import random
import subprocess

from telethon import events
from telethon.tl.types import InputMediaWebPage

import core.lib.loader.module_base as loader
from utils.restart import restart_kernel


class UpdatesMod(loader.ModuleBase):
    name = "updates"
    description = {"ru": "Модуль обновлений", "en": "Update module"}
    version = "1.0.6"
    author = "@Hairpin00"

    strings = {"name": "updates"}

    async def on_load(self):
        self.emojis = [
            "ಠ_ಠ",
            "( ཀ ʖ̯ ཀ)",
            "(◕‿◕✿)",
            "(つ･･)つ",
            "༼つ◕_◕༽つ",
            "(•_•)",
            "☜(ﾟヮﾟ☜)",
            "(☞ﾟヮﾟ)☞",
            "ʕ•ᴥ•ʔ",
            "(づ￣ ³￣)づ",
        ]

        self.PREMIUM_EMOJI = {
            "telescope": '<tg-emoji emoji-id="5334904192622403796">🔭</tg-emoji>',
            "alembic": '<tg-emoji emoji-id="5332654441508119011">⚗️</tg-emoji>',
            "package": '<tg-emoji emoji-id="5399898266265475100">📦</tg-emoji>',
        }

    async def mcub_handler(self) -> str:
        me = await self.kernel.client.get_me()
        mcub_emoji = (
            '<tg-emoji emoji-id="5470015630302287916">🔮</tg-emoji><tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
            if me.premium
            else "MCUB"
        )
        return mcub_emoji

    @loader.command("restart", doc_en="restart userbot", doc_ru="перезапустить юзербот")
    async def restart_handler(self, event: events.NewMessage.Event):
        thread_id = None
        if event.reply_to:
            thread_id = getattr(event.reply_to, "reply_to_top_id", None) or getattr(
                event.reply_to, "reply_to_msg_id", None
            )

        msg = await event.edit(
            f"{self.PREMIUM_EMOJI['telescope']} <i>{self.strings('restarting').format(mcub=await self.mcub_handler())}</i>",
            parse_mode="html",
        )
        await restart_kernel(
            self.kernel,
            chat_id=event.chat_id,
            message_id=msg.id,
            thread_id=thread_id,
        )

    @loader.command(
        "update", doc_en="update MCUB-fork from git", doc_ru="обновить MCUB-fork из git"
    )
    async def cmd_update(self, event: events.NewMessage.Event):
        msg = await event.edit("❄️")
        self.log.info("Updating MCUB-fork")

        branch = await self.kernel.version_manager.detect_branch()
        thread_id = None
        if event.reply_to:
            thread_id = getattr(event.reply_to, "reply_to_top_id", None) or getattr(
                event.reply_to, "reply_to_msg_id", None
            )

        try:
            result = subprocess.run(
                ["git", "pull", "origin", branch],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )
            self.log.debug("run -> 'git pull origin main'")

            if result.returncode == 0:
                if "Already up to date" in result.stdout:
                    await msg.edit(
                        self.strings("already_updated").format(
                            version=self.kernel.VERSION
                        ),
                        parse_mode="html",
                    )
                    self.log.info("Already up to date")
                    return

                await msg.edit(
                    self.strings("git_pull_success").format(output=result.stdout[:200]),
                    parse_mode="html",
                )
                self.log.info("successfully git pull")
                await asyncio.sleep(2)

                emoji = random.choice(self.emojis)
                await msg.edit(
                    self.strings("update_success").format(emoji=emoji),
                    parse_mode="html",
                    file=InputMediaWebPage(
                        "https://raw.githubusercontent.com/hairpin01/MCUB-fork/refs/heads/main/img/update.png",
                        optional=True,
                    ),
                    invert_media=True,
                )
                self.log.info("Restarting...")
                await asyncio.sleep(2)
                await restart_kernel(
                    self.kernel,
                    chat_id=event.chat_id,
                    message_id=msg.id,
                    thread_id=thread_id,
                )

        except Exception as e:
            await msg.edit(
                self.strings("error").format(error=str(e)),
                parse_mode="html",
            )

    @loader.command("stop", doc_en="stop userbot", doc_ru="остановить юзербот")
    async def cmd_stop(self, event: events.NewMessage.Event):
        self.kernel.shutdown_flag = True
        emoji = random.choice(self.emojis)
        await event.edit(
            self.strings("stopping", mcub=await self.mcub_handler(), emoji=emoji),
            parse_mode="html",
        )
        await asyncio.sleep(1)
        await self.kernel.shutdown()

    # потом переделаю ---
    # async def rollback_handler(event):
    #     if not os.path.exists(kernel.BACKUP_FILE):
    #         await event.edit(strings("backup_not_found"), parse_mode="html")
    #         return
    #
    #     msg = await event.edit(
    #         strings("rolling_back").format(emoji=random.choice(emojis)),
    #         parse_mode="html",
    #     )
    #
    #     try:
    #         with open(kernel.BACKUP_FILE, encoding="utf-8") as f:
    #             backup_code = f.read()
    #
    #         with open(__file__, "w", encoding="utf-8") as f:
    #             f.write(backup_code)
    #
    #         emoji = random.choice(emojis)
    #         await msg.edit(
    #             strings("rollback_success").format(emoji=emoji),
    #             parse_mode="html",
    #         )
    #         await asyncio.sleep(2)
    #         await restart_kernel(kernel)
    #     except Exception as e:
    #         await msg.edit(
    #             strings("rollback_error").format(error=str(e)),
    #             parse_mode="html",
    #         )
