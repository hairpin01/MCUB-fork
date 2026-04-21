# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

# author: @Hairpin00
# version: 1.0.6
# description: Update module / Модуль обновлений
import asyncio
import os
import random
import subprocess

from utils.restart import restart_kernel


def register(kernel):
    from utils.strings import Strings

    strings = Strings(kernel, {"name": "updates"})

    emojis = [
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

    PREMIUM_EMOJI = {
        "telescope": '<tg-emoji emoji-id="5334904192622403796">🔭</tg-emoji>',
        "alembic": '<tg-emoji emoji-id="5332654441508119011">⚗️</tg-emoji>',
        "package": '<tg-emoji emoji-id="5399898266265475100">📦</tg-emoji>',
    }

    async def mcub_handler():
        me = await kernel.client.get_me()
        mcub_emoji = (
            '<tg-emoji emoji-id="5470015630302287916">🔮</tg-emoji><tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
            if me.premium
            else "MCUB"
        )
        return mcub_emoji

    @kernel.register.command(
        "restart", doc_en="restart userbot", doc_ru="перезапустить юзербот"
    )
    async def restart_handler(event):
        thread_id = None
        if event.reply_to:
            thread_id = getattr(event.reply_to, "reply_to_top_id", None) or getattr(
                event.reply_to, "reply_to_msg_id", None
            )

        msg = await event.edit(
            f"{PREMIUM_EMOJI['telescope']} <i>{strings('restarting').format(mcub=await mcub_handler())}</i>",
            parse_mode="html",
        )
        await restart_kernel(
            kernel,
            chat_id=event.chat_id,
            message_id=msg.id,
            thread_id=thread_id,
        )

    @kernel.register.command(
        "update", doc_en="update MCUB-fork from git", doc_ru="обновить MCUB-fork из git"
    )
    async def update_handler(event):
        msg = await event.edit("❄️")
        kernel.logger.info("Updating MCUB-fork")

        branch = await kernel.version_manager.detect_branch()

        try:
            result = subprocess.run(
                ["git", "pull", "origin", branch],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )
            kernel.logger.debug("run -> 'git pull origin main'")

            if result.returncode == 0:
                if "Already up to date" in result.stdout:
                    await msg.edit(
                        strings("already_updated").format(version=kernel.VERSION),
                        parse_mode="html",
                    )
                    kernel.logger.info("Already up to date")
                    return

                await msg.edit(
                    strings("git_pull_success").format(output=result.stdout[:200]),
                    parse_mode="html",
                )
                kernel.logger.info("successfully git pull")
                await asyncio.sleep(2)

                emoji = random.choice(emojis)
                await msg.edit(
                    strings("update_success").format(emoji=emoji),
                    parse_mode="html",
                )
                kernel.logger.info("Restarting...")
                await asyncio.sleep(2)
                await restart_kernel(kernel)

        except Exception as e:
            await msg.edit(
                strings("error").format(error=str(e)),
                parse_mode="html",
            )

    @kernel.register.command("stop", doc_en="stop userbot", doc_ru="остановить юзербот")
    async def stop_handler(event):
        kernel.shutdown_flag = True
        emoji = random.choice(emojis)
        await event.edit(
            strings("stopping", mcub=await mcub_handler(), emoji=emoji),
            parse_mode="html",
        )
        await asyncio.sleep(1)
        await kernel.shutdown()

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
