# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

# author: @Hairpin00
# version: 1.0.6
# description: Update module / Модуль обновлений
import asyncio
import os
import random
import re
import subprocess

import aiohttp

from utils.restart import restart_kernel


def register(kernel):
    client = kernel.client

    language = kernel.config.get("language", "en")

    strings = {
        "ru": {
            "restarting": "Твой <b>{mcub}</b> перезагружается...",
            "restart_log": "Перезагрузка...",
            "already_updated": "✅ <b>Уже последняя версия {version}</b>",
            "git_pull_success": "📝 <b>Git pull успешен!</b>\n\n<code>{output}</code>",
            "update_success": "⚗️ <b>Обновление успешно!</b> {emoji}\nПерезагрузка через 2 секунды...",
            "trying_another_method": "🔧 <b>Пробую другой метод обновления...</b>",
            "updating_to_version": "📥 <b>Обновляю до {version}...</b> {emoji}",
            "update_success_with_backup": "⚗️ <b>Обновление успешно!</b> {emoji}\n\n📦 Бэкап создан\nПерезагрузка...",
            "cant_check_version": "❌ <b>Не удалось проверить версию</b>",
            "cant_get_update": "❌ <b>Не удалось получить обновление</b>",
            "error": "❌ <b>Ошибка:</b> <code>{error}</code>",
            "stopping": "🧲 <b>Твой <i>{mcub}</i> останавливается...</b> {emoji}",
            "backup_not_found": "❌ <b>Бэкап не найден</b>",
            "rolling_back": "🔙 <b>Откатываю к предыдущей версии...</b> <i>{emoji}</i>",
            "rollback_success": "⚗️ <b>Откат завершен!</b> {emoji}\n\nПерезагрузка...",
            "rollback_error": "❌ <b>Ошибка отката:</b> <code>{error}</code>",
        },
        "en": {
            "restarting": "Your <b>{mcub}</b> is restarting...",
            "restart_log": "Restarting...",
            "already_updated": "✅ <b>Already latest version {version}</b>",
            "git_pull_success": "📝 <b>Git pull successful!</b>\n\n<code>{output}</code>",
            "update_success": "⚗️ <b>Update successful!</b> {emoji}\nRestarting in 2 seconds...",
            "trying_another_method": "🔧 <b>Trying another update method...</b>",
            "updating_to_version": "📥 <b>Updating to {version}...</b> {emoji}",
            "update_success_with_backup": "⚗️ <b>Update successful!</b> {emoji}\n\n📦 Backup created\nRestarting...",
            "cant_check_version": "❌ <b>Could not check version</b>",
            "cant_get_update": "❌ <b>Could not get update</b>",
            "error": "❌ <b>Error:</b> <code>{error}</code>",
            "stopping": "🧲 <b>Your <i>{mcub}</i> is stopping...</b> {emoji}",
            "backup_not_found": "❌ <b>Backup not found</b>",
            "rolling_back": "🔙 <b>Rolling back to previous version...</b> <i>{emoji}</i>",
            "rollback_success": "⚗️ <b>Rollback completed!</b> {emoji}\n\nRestarting...",
            "rollback_error": "❌ <b>Rollback error:</b> <code>{error}</code>",
        },
    }

    lang_strings = strings.get(language, strings["en"])

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
            f"{PREMIUM_EMOJI['telescope']} <i>{lang_strings['restarting'].format(mcub=await mcub_handler())}</i>",
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
        try:
            try:
                result = subprocess.run(
                    ["git", "pull", "origin", "main"],
                    capture_output=True,
                    text=True,
                    cwd=os.path.dirname(os.path.abspath(__file__)),
                )
                kernel.logger.debug("run -> 'git pull origin main'")

                if result.returncode == 0:
                    if "Already up to date" in result.stdout:
                        await msg.edit(
                            lang_strings["already_updated"].format(
                                version=kernel.VERSION
                            ),
                            parse_mode="html",
                        )
                        kernel.logger.info("Already up to date")
                        return

                    await msg.edit(
                        lang_strings["git_pull_success"].format(
                            output=result.stdout[:200]
                        ),
                        parse_mode="html",
                    )
                    kernel.logger.info("successfully git pull")
                    await asyncio.sleep(2)

                    emoji = random.choice(emojis)
                    await msg.edit(
                        lang_strings["update_success"].format(emoji=emoji),
                        parse_mode="html",
                    )
                    kernel.logger.info("Restarting...")
                    await asyncio.sleep(2)
                    await restart_kernel(kernel)
                    return

            except Exception:
                pass

            await msg.edit(
                lang_strings["trying_another_method"],
                parse_mode="html",
            )

            UPDATE_REPO = "https://raw.githubusercontent.com/hairpin01/MCUB-fork/main"

            async with aiohttp.ClientSession() as session:
                async with session.get(f"{UPDATE_REPO}/core/kernel.py") as resp:
                    if resp.status == 200:
                        new_code = await resp.text()

                        if "VERSION" in new_code:
                            new_version = re.search(r"VERSION = '([^']+)'", new_code)
                            if new_version and new_version.group(1) != kernel.VERSION:
                                emoji = random.choice(emojis)
                                await msg.edit(
                                    lang_strings["updating_to_version"].format(
                                        version=new_version.group(1), emoji=emoji
                                    ),
                                    parse_mode="html",
                                )

                                kernel_file = os.path.join(
                                    os.path.dirname(os.path.dirname(__file__)),
                                    "kernel.py",
                                )
                                with open(kernel_file, encoding="utf-8") as f:
                                    current_code = f.read()
                                with open(
                                    kernel.BACKUP_FILE, "w", encoding="utf-8"
                                ) as f:
                                    f.write(current_code)

                                with open(kernel_file, "w", encoding="utf-8") as f:
                                    f.write(new_code)

                                emoji = random.choice(emojis)
                                await msg.edit(
                                    lang_strings["update_success_with_backup"].format(
                                        emoji=emoji
                                    ),
                                    parse_mode="html",
                                )
                                await asyncio.sleep(2)
                                await restart_kernel(kernel)
                            else:
                                await msg.edit(
                                    lang_strings["already_updated"].format(
                                        version=kernel.VERSION
                                    ),
                                    parse_mode="html",
                                )
                        else:
                            await msg.edit(
                                lang_strings["cant_check_version"],
                                parse_mode="html",
                            )
                    else:
                        await msg.edit(
                            lang_strings["cant_get_update"],
                            parse_mode="html",
                        )

        except Exception as e:
            await msg.edit(
                lang_strings["error"].format(error=str(e)),
                parse_mode="html",
            )

    @kernel.register.command("stop", doc_en="stop userbot", doc_ru="остановить юзербот")
    async def stop_handler(event):
        kernel.shutdown_flag = True
        emoji = random.choice(emojis)
        await event.edit(
            lang_strings["stopping"].format(mcub=await mcub_handler(), emoji=emoji),
            parse_mode="html",
        )
        await asyncio.sleep(1)
        await kernel.shutdown()

    @kernel.register.command(
        "rollback",
        doc_en="rollback to previous version",
        doc_ru="откатить к предыдущей версии",
    )
    async def rollback_handler(event):
        if not os.path.exists(kernel.BACKUP_FILE):
            await event.edit(lang_strings["backup_not_found"], parse_mode="html")
            return

        msg = await event.edit(
            lang_strings["rolling_back"].format(emoji=random.choice(emojis)),
            parse_mode="html",
        )

        try:
            with open(kernel.BACKUP_FILE, encoding="utf-8") as f:
                backup_code = f.read()

            with open(__file__, "w", encoding="utf-8") as f:
                f.write(backup_code)

            emoji = random.choice(emojis)
            await msg.edit(
                lang_strings["rollback_success"].format(emoji=emoji),
                parse_mode="html",
            )
            await asyncio.sleep(2)
            await restart_kernel(kernel)
        except Exception as e:
            await msg.edit(
                lang_strings["rollback_error"].format(error=str(e)),
                parse_mode="html",
            )
