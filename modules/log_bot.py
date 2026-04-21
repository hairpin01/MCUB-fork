# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import html

# author: @Hairpin00
# version: 1.0.1
# description: Log bot module / Модуль логирования
import io
import json
import os
import subprocess
from datetime import datetime

import aiohttp
from telethon import Button
from telethon.tl.functions.channels import EditPhotoRequest
from telethon.tl.functions.messages import (
    AddChatUserRequest,
    CreateChatRequest,
    ExportChatInviteRequest,
)
from telethon.tl.types import InputUserSelf

from utils.strings import Strings


def register(kernel):
    client = kernel.client
    bot_client = kernel.bot_client

    kernel.config.get("language", "en")

    strings_data = {"name": "log_bot"}
    strings = Strings(kernel, strings_data)
    lang = strings._active

    async def init_bot_client():
        pass

    async def get_git_commit():
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return "unknown"

    async def get_update_status():
        try:
            repo_path = os.path.dirname(os.path.abspath(__file__))

            async def run_git(args):
                process = await asyncio.create_subprocess_exec(
                    "git",
                    *args,
                    cwd=repo_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await process.communicate()
                return process.returncode, stdout.decode().strip()

            try:
                await asyncio.wait_for(run_git(["fetch", "origin"]), timeout=5)
            except TimeoutError:
                return lang["git_timeout"]

            code, output = await run_git(["rev-list", "--count", "HEAD..@{u}"])

            if code == 0 and output.isdigit():
                updates_count = int(output)
                if updates_count > 0:
                    return lang["updates_available"].format(count=updates_count)

            return lang["up_to_date"]

        except Exception as e:
            kernel.logger.error(f"{lang['git_error']}: {e}")
            return lang["git_error"]

    async def get_new_commits():
        """Возвращает список новых коммитов (sha, subject, author, time) относительно HEAD."""
        try:
            repo_path = os.path.dirname(os.path.abspath(__file__))

            async def run_git(args):
                process = await asyncio.create_subprocess_exec(
                    "git",
                    *args,
                    cwd=repo_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await process.communicate()
                return process.returncode, stdout.decode().strip()

            try:
                await asyncio.wait_for(run_git(["fetch", "origin"]), timeout=10)
            except TimeoutError:
                return None

            code, output = await run_git(
                [
                    "log",
                    "HEAD..@{u}",
                    "--format=%h\x1f%s\x1f%an\x1f%ci",
                ]
            )
            if code != 0 or not output:
                return []

            commits = []
            for line in output.splitlines():
                parts = line.split("\x1f", 3)
                if len(parts) == 4:
                    sha, subject, author, date_str = parts
                    try:
                        dt = datetime.fromisoformat(date_str.strip())
                        time_str = dt.strftime("%d.%m %H:%M")
                    except Exception:
                        time_str = date_str.strip()[:16]
                    commits.append(
                        (sha.strip(), subject.strip(), author.strip(), time_str)
                    )
            return commits

        except Exception as e:
            kernel.logger.error(f"get_new_commits error: {e}")
            return None

    async def notify_new_commits(commits, branch):
        """Отправляет уведомление о новых коммитах в лог-чат."""
        if not kernel.log_chat_id:
            return

        header = lang["new_commits_header"].format(count=len(commits), branch=branch)

        MAX_COMMITS = 5
        commit_lines = []
        for sha, subject, author, time_str in commits[:MAX_COMMITS]:
            commit_lines.append(
                f"<blockquote expandable><code>{sha}</code> {html.escape(subject)} | "
                f"{html.escape(author)} | {time_str}</blockquote>"
            )

        remaining = len(commits) - MAX_COMMITS
        if remaining > 0:
            commit_lines.append(
                f"<blockquote>{lang['and_more_commits'].format(remaining)}</blockquote>"
            )

        text = header + "\n\n" + "\n".join(commit_lines)
        btn = Button.inline(lang["new_commits_btn"], data=b"do_update", style="primary")

        update_image_path = None
        for candidate in [
            "img/update.png",
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "img", "update.png"
            ),
        ]:
            if os.path.exists(candidate):
                update_image_path = candidate
                break

        try:
            sender = (
                bot_client
                if (bot_client and await bot_client.is_user_authorized())
                else client
            )
            if update_image_path:
                await sender.send_file(
                    kernel.log_chat_id,
                    update_image_path,
                    caption=text,
                    parse_mode="html",
                    buttons=[[btn]],
                )
            else:
                await sender.send_message(
                    kernel.log_chat_id,
                    text,
                    parse_mode="html",
                    buttons=[[btn]],
                )
        except Exception as e:
            kernel.logger.error(f"notify_new_commits error: {e}")

    update_check_interval = 60

    @kernel.register.loop(
        interval=update_check_interval,
        wait_before=True,
    )
    async def update_check_loop(kernel):
        if not kernel.log_chat_id:
            kernel.logger.warning(lang["update_no_log"])
            return

        try:
            branch = await kernel.version_manager.detect_branch()
            commits = await get_new_commits()

            if not commits:  # None or []
                return

            newest_sha = commits[0][0]
            last_sha = kernel.cache.get("log_bot:last_notified_sha")
            if newest_sha == last_sha:
                return

            await notify_new_commits(commits, branch)
            kernel.cache.set("log_bot:last_notified_sha", newest_sha)

        except Exception as e:
            kernel.logger.error(f"update_check_loop error: {e}")

    @kernel.register.event("callbackquery", bot_client=True, pattern=b"do_update")
    async def on_update_callback(event):
        await event.answer()
        try:
            await event.edit(lang["update_running"], buttons=None, parse_mode="html")
        except Exception:
            pass
        try:
            repo_path = os.path.dirname(os.path.abspath(__file__))
            branch = await kernel.version_manager.detect_branch()
            proc = await asyncio.create_subprocess_exec(
                "git",
                "pull",
                "--ff-only",
                "origin",
                branch,
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_pull, stderr_pull = await asyncio.wait_for(
                proc.communicate(), timeout=30
            )
            if proc.returncode != 0:
                error_msg = stderr_pull.decode().strip() or stdout_pull.decode().strip()
                raise Exception(
                    f"git pull failed (code {proc.returncode}): {error_msg}"
                )

            proc2 = await asyncio.create_subprocess_exec(
                "git",
                "rev-parse",
                "--short",
                "HEAD",
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout2, _ = await proc2.communicate()
            sha = stdout2.decode().strip() or "?"

            kernel.cache.set("log_bot:last_notified_sha", sha)

            await event.edit(
                lang["update_done"].format(sha=sha),
                parse_mode="html",
                buttons=None,
            )
            restart_cmd = await kernel.client.send_message(
                kernel.log_chat_id, f"{kernel.custom_prefix}restart"
            )
            await kernel.process_command(restart_cmd)
        except Exception as e:
            await event.edit(
                lang["update_error"].format(error=html.escape(str(e))),
                parse_mode="html",
                buttons=None,
            )

    async def setup_log_chat():

        if kernel.config.get("log_chat_id"):
            kernel.log_chat_id = kernel.config["log_chat_id"]
            return True

        kernel.logger.info(
            f"{kernel.Colors.YELLOW}{lang['setup_log_group']}{kernel.Colors.RESET}"
        )

        try:
            async for dialog in kernel.client.iter_dialogs():
                if dialog.title and "MCUB-logs" in dialog.title:
                    kernel.log_chat_id = dialog.id
                    kernel.config["log_chat_id"] = dialog.id
                    with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                        json.dump(kernel.config, f, ensure_ascii=False, indent=2)

                    kernel.logger.info(
                        f"{kernel.Colors.GREEN}✅ {dialog.title}{kernel.Colors.RESET}"
                    )
                    return True
        except Exception as e:
            kernel.logger.error(f"{lang['searching_logs']}: {e}")

        kernel.logger.info(
            f"{kernel.Colors.YELLOW}{lang['creating_log_group']}{kernel.Colors.RESET}"
        )

        users_to_invite = [InputUserSelf()]
        bot_entity = None

        if (
            hasattr(kernel, "bot_client")
            and kernel.bot_client
            and await kernel.bot_client.is_user_authorized()
        ):
            try:
                bot_me = await kernel.bot_client.get_me()
                bot_entity = await kernel.client.get_input_entity(bot_me.username)
                users_to_invite.append(bot_entity)
            except Exception as e:
                kernel.logger.warning(f"{lang['bot_prepare_error']}: {e}")

        try:
            me = await kernel.client.get_me()
            created = await kernel.client(
                CreateChatRequest(
                    title=f"MCUB-logs [{me.first_name}]", users=users_to_invite
                )
            )

            chat_id = None
            if hasattr(created, "updates") and created.updates:
                for update in created.updates:
                    if hasattr(update, "participants") and hasattr(
                        update.participants, "chat_id"
                    ):
                        chat_id = update.participants.chat_id
                        break
            kernel.logger.debug(f"chat_id:{chat_id}")

            if not chat_id and hasattr(created, "chats") and created.chats:
                chat_id = created.chats[0].id

            if not chat_id:
                kernel.logger.error(
                    f"{kernel.Colors.RED}{lang['chat_id_error']}{kernel.Colors.RESET}"
                )
                return False

            kernel.log_chat_id = chat_id
            kernel.config["log_chat_id"] = kernel.log_chat_id

            kernel.logger.debug(f"Chat created. ID: {kernel.log_chat_id}")

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://x0.at/QHok.jpg") as resp:
                        if resp.status == 200:
                            photo_data = await resp.read()

                            content_type = resp.headers.get(
                                "Content-Type", "image/jpeg"
                            )
                            ext_map = {
                                "image/jpeg": "photo.jpg",
                                "image/jpg": "photo.jpg",
                                "image/png": "photo.png",
                                "image/webp": "photo.jpg",
                                "image/gif": "photo.gif",
                            }
                            filename = ext_map.get(
                                content_type.split(";")[0].strip(), "photo.jpg"
                            )

                            buf = io.BytesIO(photo_data)
                            buf.name = filename

                            input_file = await kernel.client.upload_file(buf)
                            await kernel.client(
                                EditPhotoRequest(channel=chat_id, photo=input_file)
                            )
            except Exception as e:
                kernel.logger.warning(
                    f"{kernel.Colors.YELLOW}{lang['avatar_error']}: {e}{kernel.Colors.RESET}"
                )

            try:
                invite = await kernel.client(
                    ExportChatInviteRequest(kernel.log_chat_id)
                )
                if hasattr(invite, "link"):
                    kernel.logger.info(
                        f"{kernel.Colors.GREEN}✅ {invite.link}{kernel.Colors.RESET}"
                    )
            except Exception as e:
                kernel.logger.warning(
                    f"{kernel.Colors.YELLOW}{lang['invite_error']}: {e}{kernel.Colors.RESET}"
                )

            if bot_entity and len(users_to_invite) == 1:
                try:
                    await kernel.client(
                        AddChatUserRequest(
                            chat_id=kernel.log_chat_id, user_id=bot_entity, fwd_limit=0
                        )
                    )
                    kernel.logger.info(
                        f"{kernel.Colors.GREEN}{lang['bot_added']}{kernel.Colors.RESET}"
                    )
                except Exception as e:
                    kernel.logger.error(
                        f"{kernel.Colors.YELLOW}{lang['bot_add_error']}: {e}{kernel.Colors.RESET}"
                    )

            with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)

            kernel.logger.info(
                f"{kernel.Colors.GREEN}✅ {kernel.log_chat_id}{kernel.Colors.RESET}"
            )
            return True

        except Exception as e:
            kernel.logger.error(
                f"{kernel.Colors.RED}{lang['chat_create_error']}: {e}{kernel.Colors.RESET}"
            )
            import traceback

            traceback.print_exc()
            return False

    @kernel.register.command(
        "log_setup", doc_en="setup logging chat", doc_ru="настроить чат для логов"
    )
    async def log_setup_handler(event):
        await event.edit(lang["log_setup_title"])
        if await setup_log_chat():
            await event.edit(f"{lang['log_setup_success']}\nID: `{kernel.log_chat_id}`")
        else:
            await event.edit(lang["log_setup_fail"])

    @kernel.register.command(
        "test_log", doc_en="test log sending", doc_ru="тест отправки логов"
    )
    async def test_log_handler(event):
        try:
            await event.edit(f"<i>{lang['test_title']}</i>", parse_mode="html")
            has_bot = hasattr(kernel, "bot_client") and kernel.bot_client
            bot_auth = has_bot and await kernel.bot_client.is_user_authorized()
            log_chat = kernel.log_chat_id
            test_info = f"""🔧 <b>{lang["log_status_title"]}</b>
<blockquote>🤖 <b>{lang["test_bot_available"]}:</b> <mono>{lang["test_bot_available"] if has_bot else lang["test_bot_not_available"]}</mono>
🔐 <b>{lang["test_bot_auth"]}:</b> <mono>{lang["test_bot_auth"] if bot_auth else lang["test_bot_not_auth"]}</mono>
💬 <b>{lang["test_log_chat_id"]}:</b> <mono>{log_chat or lang["test_not_set"]}</mono>
⏰ <b>{lang["test_time"]}:</b> <mono>{datetime.now().strftime("%H:%M:%S")}</mono></blockquote>"""
            success = await kernel.send_log_message(test_info)
            if success:
                await event.edit(f"{lang['test_success']}", parse_mode="html")
            else:
                await event.edit(f"{lang['test_fail']}", parse_mode="html")
        except Exception as e:
            await event.edit(
                f"{lang['test_error']}: <code>{html.escape(str(e))}</code>",
                parse_mode="html",
            )

    @kernel.register.command(
        "log_status", doc_en="show logging status", doc_ru="показать статус логирования"
    )
    async def log_status_handler(event):
        status = lang["log_status_on"] if kernel.log_chat_id else lang["log_status_off"]
        chat_info = (
            f"`{kernel.log_chat_id}`"
            if kernel.log_chat_id
            else lang["log_not_configured"]
        )
        bot_status = lang["bot_running"] if bot_client else lang["bot_not_running"]
        msg = f"""📊 <b>{lang["log_status_title"]}</b>: {status}
<b>{lang["log_group"]}:</b> {chat_info}
<b>{lang["bot_sending"]}:</b> {bot_status}
<b>{lang["errors"]}:</b> {lang["errors_sent"] if kernel.log_chat_id else lang["errors_not_sent"]}"""
        await event.edit(msg, parse_mode="html")

    async def mcub_handler():
        me = kernel.cache.get("log_bot:me")
        if me is None:
            me = await kernel.client.get_me()
            kernel.cache.set("log_bot:me", me, ttl=3600)
        mcub_emoji = (
            '<tg-emoji emoji-id="5470015630302287916">🔮</tg-emoji><tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
            if me.premium
            else "MCUB"
        )
        return mcub_emoji

    async def send_startup_message():
        if not kernel.log_chat_id:
            return
        await get_git_commit()
        update_status = await get_update_status()
        image_path = None
        if os.path.exists("userbot.png"):
            image_path = "start_userbot.png"
        elif os.path.exists("img/start_userbot.png"):
            image_path = "img/start_userbot.png"
        elif os.path.exists(kernel.IMG_DIR):
            images = [
                f
                for f in os.listdir(kernel.IMG_DIR)
                if f.lower().endswith((".png", ".jpg", ".jpeg"))
            ]
            if images:
                image_path = os.path.join(kernel.IMG_DIR, images[0])

        branch = await kernel.version_manager.detect_branch()
        commit_sha = await kernel.version_manager.get_commit_sha()
        commit_url = await kernel.version_manager.get_github_commit_url()

        if commit_url:
            commit_display = f'<b><a href="{commit_url}">{update_status}</a></b>'
        else:
            commit_display = f"<b>{update_status}</b>"

        message = f"""<b>{await mcub_handler()}</b> <b>{kernel.VERSION}</b> {lang["started"]}
<blockquote><b><tg-emoji emoji-id="5368585403467048206">🔭</tg-emoji> GitHub commit SHA:</b> <code>{commit_sha}</code>
<tg-emoji emoji-id="5467480195143310096">🎩</tg-emoji> <b>{lang["update_status"]}:</b> <i>{commit_display}</i>
<tg-emoji emoji-id="5436275698664759373">🌂</tg-emoji> <b>branch:</b> <code>{branch}</code>{"" if kernel.error_load_modules else "</blockquote>"}"""

        if kernel.error_load_modules:
            message += f'\n<tg-emoji emoji-id="5467928559664242360">❗️</tg-emoji> <b>Error load modules:</b> <code>{kernel.error_load_modules}</code></blockquote>'

        message += f'\n<tg-emoji emoji-id="5426900601101374618">🧿</tg-emoji> <b><i>{lang["prefix"]}:</i></b> <code>{kernel.custom_prefix}</code>'
        try:
            if bot_client and await bot_client.is_user_authorized():
                if image_path and os.path.exists(image_path):
                    await bot_client.send_file(
                        kernel.log_chat_id,
                        image_path,
                        caption=message,
                        parse_mode="html",
                    )
                else:
                    await bot_client.send_message(
                        kernel.log_chat_id, message, parse_mode="html"
                    )
                kernel.logger.info(
                    f"{kernel.Colors.GREEN}{lang['startup_via_bot']}{kernel.Colors.RESET}"
                )
            else:
                if image_path:
                    await client.send_file(
                        kernel.log_chat_id,
                        image_path,
                        caption=message,
                        parse_mode="html",
                    )
                else:
                    await client.send_message(
                        kernel.log_chat_id, message, parse_mode="html"
                    )
                kernel.cprint(
                    f"{kernel.Colors.YELLOW}{lang['startup_via_userbot']}{kernel.Colors.RESET}"
                )
        except Exception as e:
            kernel.cprint(
                f"{kernel.Colors.RED}{lang['startup_error']}: {e}{kernel.Colors.RESET}"
            )

    async def send_log_message_via_bot(self, text, file=None):
        if not self.log_chat_id:
            return False
        try:
            if (
                hasattr(self, "bot_client")
                and self.bot_client
                and await self.bot_client.is_user_authorized()
            ):
                client_to_use = self.bot_client
            else:
                client_to_use = self.client
            if file:
                await client_to_use.send_file(
                    self.log_chat_id, file, caption=text, parse_mode="html"
                )
            else:
                await client_to_use.send_message(
                    self.log_chat_id, text, parse_mode="html"
                )
            return True
        except Exception as e:
            try:
                if client_to_use == self.bot_client:
                    fallback_client = self.client
                else:
                    fallback_client = self.bot_client
                if fallback_client and await fallback_client.is_user_authorized():
                    if file:
                        await fallback_client.send_file(
                            self.log_chat_id, file, caption=text, parse_mode="html"
                        )
                    else:
                        await fallback_client.send_message(
                            self.log_chat_id, text, parse_mode="html"
                        )
                    return True
            except Exception:
                pass
            self.cprint(
                f"{self.Colors.RED}{lang['send_log_error']}: {e}{self.Colors.RESET}"
            )
            return False

    async def log_info(text):
        await send_log_message_via_bot(kernel, f"🧬 {text}")

    async def log_warning(text):
        await send_log_message_via_bot(kernel, f"⚠️ {text}")

    async def log_error(text):
        await send_log_message_via_bot(kernel, f"❌ {text}")

    async def log_network(text):
        await send_log_message_via_bot(kernel, f"✈️ {text}")

    async def log_module(text):
        await send_log_message_via_bot(kernel, f"🧿 {text}")

    kernel.send_log_message = lambda text, file=None: send_log_message_via_bot(
        kernel, text, file
    )
    kernel.log_info = log_info
    kernel.log_warning = log_warning
    kernel.log_error = log_error
    kernel.log_network = log_network
    kernel.log_module = log_module

    @kernel.register.on_load()
    async def initialize(kernel):
        kernel.bot_client = bot_client
        await setup_log_chat()
        await send_startup_message()
