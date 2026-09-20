# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import asyncio
import os
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any

import aiohttp
from telethon.tl.types import InputMediaWebPage

import core.lib.loader.module_base as loader
from core.lib.loader.module_config import (
    ModuleConfig,
    ConfigValue,
    Boolean
)
from utils import restart_kernel, Strings
from core.lib.types import Event, InlineMessage

_VERSION_ATTR_RE = re.compile(
    r"^\s*version\s*=\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
_VERSION_COMMENT_RE = re.compile(
    r"^\s*#\s*version\s*:\s*([0-9][0-9A-Za-z.\-+]*)",
    re.MULTILINE,
)


def _extract_module_version(source_text: str) -> str | None:
    m = _VERSION_ATTR_RE.search(source_text)
    if m:
        return m.group(1)
    m = _VERSION_COMMENT_RE.search(source_text)
    if m:
        return m.group(1)
    return None


DEBUG = False
_WATCHDOG_TICK = 5 if DEBUG else 30  # s: how often the scheduler wakes
_CHECK_INTERVAL = 15 if DEBUG else 600  # s: per-module poll cadence
_MAX_BACKOFF = 3 * 3600  # 3 h: ceiling for exponential backoff
_FETCH_TIMEOUT = aiohttp.ClientTimeout(total=10)
_MAX_CONCURRENT = 3  # parallel HTTP fetches


@dataclass
class _ModState:
    """
    Per-module HTTP-cache + notification state.

    Lives in kernel._upd_states, so it survives hot-reloads of this module
    (dlm / dlmurl).  That's the only reliable fix for the double-notification
    bug: resetting the dict in on_load() was the root cause.
    """

    etag: str | None = None
    last_modified: str | None = None
    notified_version: str | None = None
    failures: int = 0
    next_check_at: float = 0.0


class UpdatesMod(loader.ModuleBase):
    name = "updates"
    description = {
        "ru": "Moдyль oбнoвлeний",
        "en": "Update module",
        "uk": "Модуль оновлень",
    }
    version = "1.1.0"
    author = "@Hairpin00"

    strings: dict | Strings = {"name": "updates"}

    config = ModuleConfig(
        ConfigValue(
            "auto_update",
            False,
            description="auto update module/telethon",
            validator=Boolean(),
        ),
    )

    def _s(self, key: str, **kwargs: Any) -> str:
        return self.strings(key, **kwargs)

    async def on_load(self) -> None:
        await super().on_load()

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
            ">_<",
            "0_o",
        ]
        self.me = await self.kernel.client.get_me()
        self.PREMIUM_EMOJI = {
            "bar": (
                self.strings("material_emoji")("process_bar_pr_1")
                + self.strings("material_emoji")("process_bar_pr_2")
                + self.strings("material_emoji")("process_bar_pr_3")
            ),
            "telescope": self.strings("material_emoji")("load_3"),
            "alembic": '<tg-emoji emoji-id="5332654441508119011">⚗️</tg-emoji>',
            "package": '<tg-emoji emoji-id="5399898266265475100">📦</tg-emoji>',
        }

        if not hasattr(self.kernel, "_upd_states"):
            self.kernel._upd_states: dict[str, _ModState] = {}
        self._states: dict[str, _ModState] = self.kernel._upd_states

        self._active: set[str] = set()  # modules currently being fetched
        self._tasks: set[asyncio.Task] = set()  # live worker tasks
        self._sem = asyncio.Semaphore(_MAX_CONCURRENT)
        self.session = aiohttp.ClientSession()
        await self.update_telethon()

    async def on_unload(self) -> None:
        for task in list(self._tasks):
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        self._tasks.clear()
        self._active.clear()
        await self.session.close()
        await super().on_unload()

    @loader.loop(interval=_WATCHDOG_TICK)
    async def _updates_watchdog(self) -> None:
        """Fires a per-module check task whenever that module is due."""
        sources = getattr(self.kernel, "_module_sources", None) or {}
        loaded = getattr(self.kernel, "loaded_modules", None) or {}
        now = time.monotonic()

        for mod_name, src in list(sources.items()):
            if mod_name not in loaded:
                continue
            if not isinstance(src, dict):
                continue
            url = src.get("url")
            if not url:
                continue
            if mod_name in self._active:
                continue  # already in flight

            state = self._states.setdefault(mod_name, _ModState())
            if now < state.next_check_at:
                continue  # not due yet

            self._active.add(mod_name)
            state.next_check_at = now + _CHECK_INTERVAL

            task = asyncio.create_task(self._run_check(mod_name, url, state))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _run_check(self, mod_name: str, url: str, state: _ModState) -> None:
        """Semaphore-gated wrapper; handles backoff and bookkeeping."""
        try:
            async with self._sem:
                await self._check(mod_name, url, state)
            state.failures = 0
            state.next_check_at = time.monotonic() + _CHECK_INTERVAL
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            state.failures += 1
            backoff = min(_CHECK_INTERVAL * (2**state.failures), _MAX_BACKOFF)
            state.next_check_at = time.monotonic() + backoff
            self.log.warning(
                f"updates: {mod_name}: check failed "
                f"(#{state.failures}, retry in {backoff:.0f}s): {exc}"
            )
        finally:
            self._active.discard(mod_name)

    async def _check(self, mod_name: str, url: str, state: _ModState) -> None:
        """HTTP fetch with conditional request, then version comparison."""

        req_headers: dict[str, str] = {}
        if state.etag:
            req_headers["If-None-Match"] = state.etag
        if state.last_modified:
            req_headers["If-Modified-Since"] = state.last_modified

        async with self.session.get(
            url, headers=req_headers, timeout=_FETCH_TIMEOUT
        ) as resp:
            if resp.status == 304:
                return
            resp.raise_for_status()

            if etag := resp.headers.get("ETag"):
                state.etag = etag
            if lm := resp.headers.get("Last-Modified"):
                state.last_modified = lm

            code = await resp.text(encoding="utf-8", errors="replace")

        remote_ver = _extract_module_version(code)
        if not remote_ver:
            return

        try:
            module_obj = self.require_module(mod_name)
        except LookupError:
            return

        local_ver: str = getattr(module_obj, "version", None) or ""
        author: str = getattr(module_obj, 'author', None) or ""
        meta: dict[str, ...] = await self.kernel._loader.get_module_metadata(code)
        if not local_ver:
            try:
                local_ver = (meta or {}).get("version") or "0.0.0"
            except Exception:
                local_ver = "0.0.0"

        if not author:
            author = meta['author']

        vm = self.kernel.version_manager
        try:
            vm._parse_version(local_ver)
            vm._parse_version(remote_ver)
        except Exception:
            self.log.warning(
                f"updates: {mod_name}: unparseable version "
                f"local={local_ver!r} remote={remote_ver!r}"
            )
            return

        cmp = vm.compare_versions(local_ver, remote_ver)
        if cmp < 0:

            if state.notified_version == remote_ver:
                return
            state.notified_version = remote_ver
            self.log.info(f"updates: {mod_name} {local_ver} → {remote_ver}")
            await self._notify(mod_name, local_ver, remote_ver, url)
        else:
            state.notified_version = None

    async def _notify(
        self,
        mod_name: str,
        local_ver: str,
        remote_ver: str,
        url: str,
        telethon: bool = False,
    ) -> None:
        if telethon:
            mod_name = "Telethon"
        target = getattr(self.kernel, "log_chat_id", None) or self.kernel.ADMIN_ID
        if not target:
            return
        message = await self.subinline.bot.send_rich_message(
            target,
            f"<h1>Update available for <code>{mod_name}</code> "
            f"{await self.mcub_handler()} {'module!' if not telethon else 'lib package!'}</h1><hr/>\n"
            f"""<table>
  <tr>
    <td align="center" valign="middle"><code>{local_ver}</code> <b>→</b> <mark>{remote_ver}</mark></td>
  </tr></table><hr/>\n"""
            f"<aside>{self.PREMIUM_EMOJI['telescope']} {url if not telethon else 'https://github.com/hairpin01/Tehethon-MCUB.git'}<cite>URL</cite></aside><hr/>",
            buttons=[
                [
                    self.Button.inline(
                        self.strings("buttons")("update"),
                        self.cb_update if not telethon else self.cb_update_telethon,
                        data=(mod_name, url),
                        style="success",
                    )
                ]
            ],
        )

        if self.config.get("auto_update"):
            await message.click(0)

    async def update_telethon(self) -> None:
        vm = self.kernel.version_manager

        from telethon import __version__

        yes, result = await vm.is_update_package("Telethon-MCUB", __version__)
        if yes:
            await self._notify(
                "telethon",
                __version__,
                result,
                "pip install -U Telethon-MCUB",
                telethon=True,
            )
        else:
            if result is not None:
                self.log.error(f"Error in update_telethon: {result}")

    @loader.callback()
    async def cb_update(self, call: InlineMessage, data: tuple[str, str]) -> None:
        mod, url = data
        await call.edit_rich(
            f"<h1>updating... {mod}</h1>\n"
            f"<aside>{self.PREMIUM_EMOJI['bar']}</aside>",
        )
        bot = await self.subinline.bot.get_me()
        await self.invoke(
            "dlm",
            args=url,
            chat_id=int(getattr(self.kernel, "log_chat_id", bot.id)),
            reply_to=getattr(call, "reply_to", None),
        )
        await call.edit_rich(
            f"<aside>Success</aside><hr/><p>Update: <mark>{mod} module</mark><p>",
        )

    @loader.callback()
    async def cb_update_telethon(self, call: InlineMessage, data: tuple[str, str]) -> None:
        mod, args = data
        await call.edit_rich(
            f"<h1>updating... {mod}</h1>\n"
            f"<aside>{self.PREMIUM_EMOJI['bar']}</aside>",
        )
        bot = await self.subinline.bot.get_me()
        await self.invoke(
            "t",
            args=args,
            chat_id=int(getattr(self.kernel, "log_chat_id", bot.id)),
            reply_to=getattr(call, "reply_to", None),
        )
        await call.edit_rich(
            f"<aside>Success</aside><hr/><p>Update: <mark>{mod} package</mark></p>",
        )

    async def mcub_handler(self) -> str:
        return (
            '<tg-emoji emoji-id="5470015630302287916">🔮</tg-emoji>'
            '<tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji>'
            '<tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji>'
            '<tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
            if self.me.premium
            else "MCUB"
        )

    @loader.command(
        "restart",
        doc_en="restart userbot",
        doc_ru="пepeзaпycтить юзepбoт",
        doc_uk="перезапустити юзербот",
    )
    async def restart_handler(self, event: Event) -> None:
        thread_id = None
        if event.reply_to:
            thread_id = getattr(event.reply_to, "reply_to_top_id", None) or getattr(
                event.reply_to, "reply_to_msg_id", None
            )
        msg = await event.edit(
            f"<blockquote>{self.PREMIUM_EMOJI['telescope']} "
            f"<i>{self._s('restarting').format(mcub=await self.mcub_handler())}</i></blockquote>",
            parse_mode="html",
        )
        await restart_kernel(
            self.kernel,
            chat_id=event.chat_id,
            message_id=msg.id,
            thread_id=thread_id,
        )

    @loader.command(
        "update",
        doc_en="update MCUB-fork from git",
        doc_ru="oбнoвить MCUB-fork из git",
        doc_uk="оновити MCUB-fork з git",
    )
    async def cmd_update(self, event: Event) -> None:
        msg = await event.edit("❄️")
        self.log.info("Updating MCUB-fork")

        branch = await self.kernel.version_manager.detect_branch()
        thread_id = None
        if event.reply_to:
            thread_id = getattr(event.reply_to, "reply_to_top_id", None) or getattr(
                event.reply_to, "reply_to_msg_id", None
            )

        try:
            repo_path = os.path.dirname(os.path.abspath(__file__))
            proc = await asyncio.create_subprocess_exec(
                "git",
                "pull",
                "origin",
                branch,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=60
                )
            except TimeoutError:
                proc.kill()
                await proc.communicate()
                await msg.edit(
                    self._s("error").format(error="git pull timed out (60s)"),
                    parse_mode="html",
                )
                return

            stdout = stdout_b.decode(errors="replace")

            if proc.returncode == 0:
                if "Already up to date" in stdout:
                    await msg.edit(
                        self._s("already_updated").format(version=self.kernel.VERSION),
                        parse_mode="html",
                    )
                    self.log.info("Already up to date")
                    return

                await msg.edit(
                    self._s("git_pull_success").format(output=stdout[:200]),
                    parse_mode="html",
                )
                self.log.info("git pull succeeded")
                await asyncio.sleep(2)

                await msg.edit(
                    self._s("update_success").format(emoji=secrets.choice(self.emojis)),
                    parse_mode="html",
                    file=InputMediaWebPage(
                        "https://raw.githubusercontent.com/hairpin01/MCUB-fork/refs/heads/main/img/update.png",
                        optional=True,
                    ),
                    invert_media=True,
                )
                self.log.info("Restarting…")
                await asyncio.sleep(2)
                await restart_kernel(
                    self.kernel,
                    chat_id=event.chat_id,
                    message_id=msg.id,
                    thread_id=thread_id,
                )
        except Exception as exc:
            await msg.edit(
                self._s("error").format(error=str(exc)),
                parse_mode="html",
            )

    @loader.command(
        "stop",
        doc_en="stop userbot",
        doc_ru="ocтaнoвить юзepбoт",
        doc_uk="зупинити юзербот",
    )
    async def cmd_stop(self, event: Event) -> None:
        self.kernel.shutdown_flag = True
        await event.edit(
            self._s(
                "stopping",
                mcub=await self.mcub_handler(),
                emoji=secrets.choice(self.emojis),
            ),
            parse_mode="html",
        )
        await asyncio.sleep(1)
        await self.kernel.shutdown()
