# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import html
import io
import os
import subprocess
from datetime import datetime

import aiohttp
from telethon import events
from telethon.tl.functions.channels import EditPhotoRequest
from telethon.tl.functions.messages import (
    AddChatUserRequest,
    CreateChatRequest,
    ExportChatInviteRequest,
)
from telethon.tl.types import InputMediaWebPage, InputUserSelf

from core.lib.loader.module_base import ModuleBase, callback, command, loop


class LogBot(ModuleBase):
    name = "log_bot"
    description: dict[dict[str], dict[str]] = {
        "ru": "Модуль логирования",
        "en": "Log bot module",
    }
    version = "1.1.0"

    strings = {"name": "log_bot"}
    author = "@Hairpin00"

    async def get_git_commit(self):
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "unknown"

    async def get_update_status(self):
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
                return self.lang["git_timeout"]

            code, output = await run_git(["rev-list", "--count", "HEAD..@{u}"])

            if code == 0 and output.isdigit():
                updates_count = int(output)
                if updates_count > 0:
                    return self.lang["updates_available"].format(count=updates_count)

            return self.lang["up_to_date"]

        except Exception as e:
            self.log.error(f"{self.lang['git_error']}: {e}")
            return self.lang["git_error"]

    async def get_new_commits(self):
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
            self.log.error(f"get_new_commits error: {e}")
            return None

    async def notify_new_commits(self, commits, branch):
        """Отправляет уведомление о новых коммитах в лог-чат."""
        if not self.kernel.log_chat_id:
            return

        header = self.lang["new_commits_header"].format(
            count=len(commits), branch=branch
        )

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
                f"<blockquote>{self.lang['and_more_commits'].format(remaining)}</blockquote>"
            )

        text = header + "\n\n" + "\n".join(commit_lines)
        btn = self.Button.inlines(
            self.lang["new_commits_btn"], self.on_update_callback, style="primary"
        )

        update_image_url = "https://raw.githubusercontent.com/hairpin01/MCUB-fork/refs/heads/main/img/update.png"

        try:
            sender = (
                self.kernel.bot_client
                if (
                    self.kernel.bot_client
                    and await self.kernel.bot_client.is_user_authorized()
                )
                else self.kernel.client
            )
            _message_load = await sender.send_message(
                self.kernel.log_chat_id,
                self.strings("banner_load"),
            )

            await _message_load.edit(
                text,
                file=InputMediaWebPage(update_image_url, optional=True),
                invert_media=True,
                parse_mode="html",
                buttons=[[btn]],
            )

        except Exception as e:
            self.kernel.logger.error(f"notify_new_commits error: {e}")

    update_check_interval = 60

    @loop(
        interval=update_check_interval,
        wait_before=True,
    )
    async def update_check_loop(self):
        if not self.kernel.log_chat_id:
            self.kernel.logger.warning(self.lang["update_no_log"])
            return

        try:
            branch = await self.kernel.version_manager.detect_branch()
            commits = await self.get_new_commits()

            if not commits:  # None or []
                return

            newest_sha = commits[0][0]
            last_sha = self.kernel.cache.get("log_bot:last_notified_sha")
            if newest_sha == last_sha:
                return

            await self.notify_new_commits(commits, branch)
            self.kernel.cache.set("log_bot:last_notified_sha", newest_sha)

        except Exception as e:
            self.log.error(f"update_check_loop error: {e}")

    @callback()
    async def on_update_callback(self, call: events.CallbackQuery.Event, data=None):
        await call.answer()
        try:
            await self.edit(self.lang["update_running"], buttons=None, as_html=True)
        except Exception:
            pass
        try:
            repo_path = os.path.dirname(os.path.abspath(__file__))
            branch = await self.kernel.version_manager.detect_branch()
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

            self.kernel.cache.set("log_bot:last_notified_sha", sha)

            await self.edit(
                self.lang["update_done"].format(sha=sha),
                as_html=True,
                buttons=None,
            )
            restart_cmd = await self.kernel.client.send_message(
                self.kernel.log_chat_id, f"{self.kernel.custom_prefix}restart"
            )
            await self.kernel.process_command(restart_cmd)
        except Exception as e:
            await self.edit(
                self.lang["update_error"].format(error=html.escape(str(e))),
                as_html=True,
                buttons=None,
            )

    async def setup_log_chat(self):

        if self.kernel.config.get("log_chat_id"):
            self.kernel.log_chat_id = self.kernel.config["log_chat_id"]
            return True

        self.log.info(
            f"{self.kernel.Colors.YELLOW}{self.lang['setup_log_group']}{self.kernel.Colors.RESET}"
        )

        try:
            async for dialog in self.kernel.client.iter_dialogs():
                if dialog.title and "MCUB-logs" in dialog.title:
                    self.kernel.log_chat_id = dialog.id
                    self.kernel.config["log_chat_id"] = dialog.id
                    self.kernel.save_config()

                    self.log.info(
                        f"{self.kernel.Colors.GREEN}✅ {dialog.title}{self.kernel.Colors.RESET}"
                    )
                    return True
        except Exception as e:
            self.log.error(f"{self.ang['searching_logs']}: {e}")

        self.log.info(
            f"{self.kernel.Colors.YELLOW}{self.lang['creating_log_group']}{self.kernel.Colors.RESET}"
        )

        users_to_invite = [InputUserSelf()]
        bot_entity = None

        if (
            hasattr(self.kernel, "bot_client")
            and self.kernel.bot_client
            and await self.kernel.bot_client.is_user_authorized()
        ):
            try:
                bot_me = await self.kernel.bot_client.get_me()
                bot_entity = await self.kernel.client.get_input_entity(bot_me.username)
                users_to_invite.append(bot_entity)
            except Exception as e:
                self.log.warning(f"{self.lang['bot_prepare_error']}: {e}")

        try:
            me = await self.kernel.client.get_me()
            created = await self.kernel.client(
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
            self.log.debug(f"chat_id:{chat_id}")

            if not chat_id and hasattr(created, "chats") and created.chats:
                chat_id = created.chats[0].id

            if not chat_id:
                self.log.error(
                    f"{self.kernel.Colors.RED}{self.lang['chat_id_error']}{self.kernel.Colors.RESET}"
                )
                return False

            self.kernel.log_chat_id = chat_id
            self.kernel.config["log_chat_id"] = self.kernel.log_chat_id

            self.log.debug(f"Chat created. ID: {self.kernel.log_chat_id}")

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

                            input_file = await self.kernel.client.upload_file(buf)
                            await self.kernel.client(
                                EditPhotoRequest(channel=chat_id, photo=input_file)
                            )
            except Exception as e:
                self.log.warning(
                    f"{self.kernel.Colors.YELLOW}{self.lang['avatar_error']}: {e}{self.kernel.Colors.RESET}"
                )

            try:
                invite = await self.kernel.client(
                    ExportChatInviteRequest(self.kernel.log_chat_id)
                )
                if hasattr(invite, "link"):
                    self.log.info(
                        f"{self.kernel.Colors.GREEN}✅ {invite.link}{self.kernel.Colors.RESET}"
                    )
            except Exception as e:
                self.log.warning(
                    f"{self.kernel.Colors.YELLOW}{self.lang['invite_error']}: {e}{self.kernel.Colors.RESET}"
                )

            if bot_entity and len(users_to_invite) == 1:
                try:
                    await self.kernel.client(
                        AddChatUserRequest(
                            chat_id=self.kernel.log_chat_id,
                            user_id=bot_entity,
                            fwd_limit=0,
                        )
                    )
                    self.log.info(
                        f"{self.kernel.Colors.GREEN}{self.lang['bot_added']}{self.kernel.Colors.RESET}"
                    )
                except Exception as e:
                    self.log.error(
                        f"{self.kernel.Colors.YELLOW}{self.lang['bot_add_error']}: {e}{self.kernel.Colors.RESET}"
                    )

            self.kernel.save_config()

            self.log.info(
                f"{self.kernel.Colors.GREEN}✅ {self.kernel.log_chat_id}{self.kernel.Colors.RESET}"
            )
            return True

        except Exception as e:
            import traceback

            tb = traceback.format_exc
            self.log.error(
                f"{self.kernel.Colors.RED}{self.lang['chat_create_error']}: {e}{self.kernel.Colors.RESET}\n{tb}"
            )

            return False

    @command("log_setup", doc_en="setup logging chat", doc_ru="настроить чат для логов")
    async def log_setup_handler(self, event: events.NewMessage.Event):
        await event.edit(self.lang["log_setup_title"])
        if await self.setup_log_chat():
            await event.edit(
                f"{self.lang['log_setup_success']}\nID: `{self.kernel.log_chat_id}`"
            )
        else:
            await event.edit(self.lang["log_setup_fail"])

    async def mcub_handler(self):
        me = self.kernel.cache.get("log_bot:me")
        if me is None:
            me = await self.kernel.client.get_me()
            self.kernel.cache.set("log_bot:me", me, ttl=3600)
        mcub_emoji = (
            '<tg-emoji emoji-id="5470015630302287916">🔮</tg-emoji><tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
            if me.premium
            else "MCUB"
        )
        return mcub_emoji

    async def send_startup_message(self):
        if not self.kernel.log_chat_id:
            return
        await self.get_git_commit()
        update_status = await self.get_update_status()
        image_url = "https://raw.githubusercontent.com/hairpin01/MCUB-fork/refs/heads/main/img/start_userbot.png"

        branch = await self.kernel.version_manager.detect_branch()
        commit_sha = await self.kernel.version_manager.get_commit_sha()
        commit_url = await self.kernel.version_manager.get_github_commit_url()

        if commit_url:
            commit_display = f'<b><a href="{commit_url}">{update_status}</a></b>'
        else:
            commit_display = f"<b>{update_status}</b>"

        message = f"""<b>{await self.mcub_handler()}</b> <b>{self.kernel.VERSION}</b> {self.lang["started"]}
<blockquote><b><tg-emoji emoji-id="5368585403467048206">🔭</tg-emoji> GitHub commit SHA:</b> <code>{commit_sha}</code>
<tg-emoji emoji-id="5467480195143310096">🎩</tg-emoji> <b>{self.lang["update_status"]}:</b> <i>{commit_display}</i>
<tg-emoji emoji-id="5436275698664759373">🌂</tg-emoji> <b>branch:</b> <code>{branch}</code>
{self.lang('version', version=self.version, name=self.name)}{"" if self.kernel.error_load_modules else "</blockquote>"}"""

        if self.kernel.error_load_modules:
            message += f'\n<tg-emoji emoji-id="5467928559664242360">❗️</tg-emoji> <b>Error load modules:</b> <code>{self.kernel.error_load_modules}</code></blockquote>'

        message += f'\n<tg-emoji emoji-id="5426900601101374618">🧿</tg-emoji> <b><i>{self.lang["prefix"]}:</i></b> <code>{self.kernel.custom_prefix}</code>'
        try:
            if await self.kernel.bot_client.is_user_authorized():
                _message_load = await self.kernel.bot_client.send_message(
                    self.kernel.log_chat_id,
                    self.strings("banner_load"),
                    parse_mode="html",
                )

                await _message_load.edit(
                    message,
                    file=InputMediaWebPage(image_url, optional=True),
                    invert_media=True,
                    parse_mode="html",
                )
                self.log.info(
                    f"{self.kernel.Colors.GREEN}{self.lang['startup_via_bot']}{self.kernel.Colors.RESET}"
                )
            else:
                _message_load = await self.client.send_message(
                    self.kernel.log_chat_id,
                    self.strings("banner_load"),
                    parse_mode="html",
                )

                await _message_load.edit(
                    message,
                    file=InputMediaWebPage(image_url, optional=True),
                    invert_media=True,
                    parse_mode="html",
                )

                self.log.error(
                    f"{self.kernel.Colors.YELLOW}{self.lang['startup_via_userbot']}{self.kernel.Colors.RESET}"
                )
        except Exception as e:
            self.log.error(
                f"{self.kernel.Colors.RED}{self.lang['startup_error']}: {e}{self.kernel.Colors.RESET}"
            )

    async def send_log_message_via_bot(self, text, file=None):
        if not self.kernel.log_chat_id:
            return False
        try:
            if (
                hasattr(self.kernel, "bot_client")
                and self.kernel.bot_client
                and await self.kernel.bot_client.is_user_authorized()
            ):
                client_to_use = self.kernel.bot_client
            else:
                client_to_use = self.kernel.client
            if file:
                await client_to_use.send_file(
                    self.kernel.log_chat_id, file, caption=text, parse_mode="html"
                )
            else:
                await client_to_use.send_message(
                    self.kernel.log_chat_id, text, parse_mode="html"
                )
            return True
        except Exception as e:
            try:
                if client_to_use == self.kernel.bot_client:
                    fallback_client = self.kernel.client
                else:
                    fallback_client = self.kernel.bot_client
                if fallback_client and await fallback_client.is_user_authorized():
                    if file:
                        await fallback_client.send_file(
                            self.kernel.log_chat_id,
                            file,
                            caption=text,
                            parse_mode="html",
                        )
                    else:
                        await fallback_client.send_message(
                            self.kernel.log_chat_id, text, parse_mode="html"
                        )
                    return True
            except Exception:
                pass
            self.log.error(
                f"{self.kernel.Colors.RED}{self.lang['send_log_error']}: {e}{self.kernel.Colors.RESET}"
            )
            return False

    # async def log_info(text):
    #     await send_log_message_via_bot(kernel, f"🧬 {text}")
    #
    # async def log_warning(text):
    #     await send_log_message_via_bot(kernel, f"⚠️ {text}")
    #
    # async def log_error(text):
    #     await send_log_message_via_bot(kernel, f"❌ {text}")
    #
    # async def log_network(text):
    #     await send_log_message_via_bot(kernel, f"✈️ {text}")
    #
    # async def log_module(text):
    #     await send_log_message_via_bot(kernel, f"🧿 {text}")
    #
    # kernel.send_log_message = lambda text, file=None: send_log_message_via_bot(
    #     kernel, text, file
    # )
    # kernel.log_info = log_info
    # kernel.log_warning = log_warning
    # self.kernel.log_error = log_error
    # self.kernel.log_network = log_network
    # self.kernel.log_module = log_module

    async def on_load(self):
        self.lang = self.strings
        await self.setup_log_chat()
        await self.send_startup_message()
