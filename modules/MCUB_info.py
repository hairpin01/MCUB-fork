# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import getpass
import os
import platform
import socket
import subprocess
import time
from copy import copy
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
from telethon import functions
from telethon.tl.types import InputMediaWebPage, MessageEntityTextUrl

from core.lib.loader.module_base import ModuleBase, command
from core.lib.loader.module_config import (
    Boolean,
    ConfigValue,
    ModuleConfig,
    String,
)


def _detect_branch_sync():
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=base_dir,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "main"


CUSTOM_EMOJI = {
    "load": '<tg-emoji emoji-id="5469913852462242978">🏓</tg-emoji>',
    "arch": '<tg-emoji emoji-id="5361837567463399422">🪩</tg-emoji>',
    "ubuntu": '<tg-emoji emoji-id="5470088387048266598">🐉</tg-emoji>',
    "mint": '<tg-emoji emoji-id="6021351236240938822">🚂</tg-emoji>',
    "fedora": '<tg-emoji emoji-id="5888894642400795884">🛸</tg-emoji>',
    "centos": '<tg-emoji emoji-id="5938472510755444126">🧪</tg-emoji>',
    "vds": '<tg-emoji emoji-id="5471952986970267163">🧩</tg-emoji>',
    "wsl": '<tg-emoji emoji-id="5395325195542078574">🍀</tg-emoji>',
    "termux": '<tg-emoji emoji-id="5300999883996536855">🌪️</tg-emoji>',
    "💠": '<tg-emoji emoji-id="5404366668635865453">💠</tg-emoji>',
    "🌩️": '<tg-emoji emoji-id="5134201302888219205">🌩️</tg-emoji>',
    "💔": '<tg-emoji emoji-id="4915853119839011973">💔</tg-emoji>',
    "🔮": '<tg-emoji emoji-id="5445259009311391329">🔮</tg-emoji>',
    "📡": '<tg-emoji emoji-id="5289698618154955773">📡</tg-emoji>',
    "🧪": '<tg-emoji emoji-id="5208536646932253772">🧪</tg-emoji>',
    "🔬": '<tg-emoji emoji-id="4904936030232117798">🔬</tg-emoji>',
    "🧬": '<tg-emoji emoji-id="5368513458469878442">🧬</tg-emoji>',
    "🔷": '<tg-emoji emoji-id="5406786135382845849">🔷</tg-emoji>',
    "🔶": '<tg-emoji emoji-id="5406792732452613826">🔶</tg-emoji>',
    "🧩": '<tg-emoji emoji-id="5332534105114445343">🧩</tg-emoji>',
    "🌐": '<tg-emoji emoji-id="4906943755644306322">🌐</tg-emoji>',
    "⛔️": '<tg-emoji emoji-id="4918014360267260850">⛔️</tg-emoji>',
    "❌": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji>',
    "⚠️": '<tg-emoji emoji-id="5904692292324692386">⚠️</tg-emoji>',
}

ZERO_WIDTH_CHAR = "\u2060"


class MCUBInfoMod(ModuleBase):
    name = "MCUB_info"
    version = "1.0.0"
    author = "@hairpin01"

    async def on_load(self) -> None:
        branch = self._get_branch()
        config_dict = await self.kernel.get_module_config(
            self.name,
            {
                "info_quote_media": False,
                "info_invert_media": False,
                "info_custom_text": "",
                "info_start_emoji": CUSTOM_EMOJI["load"],
                "info_banner_url": f"https://raw.githubusercontent.com/hairpin01/MCUB-fork/refs/heads/{branch}/img/info.png",
            },
        )
        self.config.from_dict(config_dict)
        config_dict_clean = {
            k: v for k, v in self.config.to_dict().items() if v is not None
        }
        if config_dict_clean:
            await self.kernel.save_module_config(self.name, config_dict_clean)
        self.kernel.store_module_config_schema(self.name, self.config)

    description: dict[str, str] = {
        "ru": "Инфо о системе",
        "en": "System info",
    }

    config = ModuleConfig(
        ConfigValue(
            "info_quote_media",
            False,
            description="Send media in quotes",
            validator=Boolean(default=False),
        ),
        ConfigValue(
            "info_invert_media",
            False,
            description="Invert media colors",
            validator=Boolean(default=False),
        ),
        ConfigValue(
            "info_banner_url",
            "",
            description="Banner image URL for inline preview",
            validator=String(default=""),
        ),
        ConfigValue(
            "info_custom_text",
            "",
            description=(
                "Custom text for .info. Available placeholders:\n"
                "{kernel_version}, {core_name}, {ping_time}, {uptime_str},\n"
                "{distro_name}, {distro_emoji}, {platform_type},\n"
                "{cpu_usage}, {ram_usage}, {system_user}, {hostname},\n"
                "{update_needed}, {branch}, {commit_sha}, {commit_url},\n"
                "{mcub_emoji}, {user_id}, {me_first_name}, {me_username},\n"
                "{now_date}, {now_time}, {now_day}, {now_month},\n"
                "{now_month_name}, {now_year}, {now_weekday},\n"
                "{now_hour}, {now_minute}, {now_second}"
            ),
            validator=String(default=""),
        ),
        ConfigValue(
            "info_start_emoji",
            CUSTOM_EMOJI["load"],
            description="Start emoji",
            validator=String(default=CUSTOM_EMOJI["load"]),
        ),
    )

    strings: dict[str, dict[str, str]] = {
        "en": {
            "custom_text_error": "<b>Error in custom text format:</b> {error}",
            "error_see_logs": "{warning} <b>Error, see logs</b>",
        },
        "ru": {
            "custom_text_error": "<b>Ошибка в форматировании:</b> {error}",
            "error_see_logs": "{warning} <b>Ошибка, смотри логи</b>",
        },
    }

    def _get_branch(self) -> str:
        return _detect_branch_sync()

    def _resolve_info_start_emoji(self) -> str:
        try:
            raw = self.config.get("info_start_emoji")
            if not raw:
                return CUSTOM_EMOJI.get("load", "🏓")
            if not isinstance(raw, str):
                return CUSTOM_EMOJI.get("load", "🏓")
            value = raw.strip()
            if not value:
                return CUSTOM_EMOJI.get("load", "🏓")
            return CUSTOM_EMOJI.get(value, value)
        except Exception as e:
            self.log.error(f"Error resolving start emoji: {e}")
            return "🏓"

    def _format_uptime(self, seconds: float) -> str:
        seconds = int(seconds)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    async def _check_update(self) -> bool:
        cached = self.cache.get("info:update_needed")
        if cached is not None:
            return cached

        try:
            repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            process = await asyncio.create_subprocess_exec(
                "git",
                "fetch",
                "origin",
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                await asyncio.wait_for(process.communicate(), timeout=10)
            except TimeoutError:
                return False

            proc = await asyncio.create_subprocess_exec(
                "git",
                "rev-list",
                "--count",
                "HEAD..@{u}",
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0 and stdout.decode().strip().isdigit():
                result = int(stdout.decode().strip()) > 0
                self.cache.set("info:update_needed", result, ttl=300)
                return result

            self.cache.set("info:update_needed", False, ttl=300)
            return False
        except Exception:
            return False

    def _get_system_info(self) -> tuple[str, str]:
        cpu_usage = "N/A"
        ram_usage = "N/A"

        try:
            cpu_usage = f"{psutil.cpu_percent(interval=0.1)}%"
            ram = psutil.virtual_memory()
            ram_usage = f"{ram.percent}%"
        except (PermissionError, Exception):
            proc_stat_path = "/proc/stat"
            proc_meminfo_path = "/proc/meminfo"

            try:
                if os.path.exists(proc_stat_path) and os.access(
                    proc_stat_path, os.R_OK
                ):
                    with open(proc_stat_path) as f:
                        for line in f:
                            if line.startswith("cpu "):
                                parts = line.split()
                                total = sum(int(x) for x in parts[1:])
                                idle = int(parts[4])
                                used = total - idle
                                if total > 0:
                                    cpu_percent = (used / total) * 100
                                    cpu_usage = f"{cpu_percent:.1f}%"
                                break

                if os.path.exists(proc_meminfo_path) and os.access(
                    proc_meminfo_path, os.R_OK
                ):
                    meminfo = {}
                    with open(proc_meminfo_path) as f:
                        for line in f:
                            if ":" in line:
                                key, value = line.split(":", 1)
                                meminfo[key.strip()] = value.strip()

                    if "MemTotal" in meminfo:
                        total = int(meminfo["MemTotal"].split()[0])
                        available = meminfo.get(
                            "MemAvailable", meminfo.get("MemFree", "0")
                        )
                        available = int(available.split()[0])
                        used = total - available
                        if total > 0:
                            ram_percent = (used / total) * 100
                            ram_usage = f"{ram_percent:.1f}%"
            except Exception:
                pass

        return cpu_usage, ram_usage

    def _get_distro(self) -> tuple[str, str]:
        cached = self.cache.get("info:distro_name")
        if cached is not None:
            if isinstance(cached, tuple) and len(cached) == 2:
                return cached
            elif isinstance(cached, str):
                distro_name = cached
            else:
                distro_name = None
        else:
            distro_name = None

        if not distro_name:
            try:
                if os.path.exists("/etc/os-release"):
                    with open("/etc/os-release") as f:
                        for line in f:
                            if "PRETTY_NAME" in line:
                                distro_name = line.split("=")[1].strip().strip('"')
                                break
                else:
                    distro_name = platform.platform()
            except Exception:
                distro_name = "Linux"

            self.cache.set("info:distro_name", distro_name)

        distro_emojis = {
            "arch": CUSTOM_EMOJI["arch"],
            "ubuntu": CUSTOM_EMOJI["ubuntu"],
            "mint": CUSTOM_EMOJI["mint"],
            "fedora": CUSTOM_EMOJI["fedora"],
            "centos": CUSTOM_EMOJI["centos"],
        }
        distro_emoji = ""
        for key, emoji in distro_emojis.items():
            if key in distro_name.lower():
                distro_emoji = emoji
                break

        return distro_name, distro_emoji

    def _get_platform_type(self) -> str:
        cached = self.cache.get("info:platform_type")
        if cached is not None and isinstance(cached, str):
            return cached

        from utils.platform import get_platform, is_termux, is_wsl

        get_platform()
        platform_type = f"VDS {CUSTOM_EMOJI['vds']}"
        if is_wsl():
            platform_type = f"WSL {CUSTOM_EMOJI['wsl']}"
        elif is_termux():
            platform_type = f"Termux {CUSTOM_EMOJI['termux']}"
        self.cache.set("info:platform_type", platform_type)
        return platform_type

    @command("info", doc_ru="показать инфо", doc_en="show info")
    async def cmd_info(self, event: Any) -> None:
        try:
            start_time = time.time()
            msg = await event.edit(
                self._resolve_info_start_emoji(),
                parse_mode="html",
            )
            ping_time = round((time.time() - start_time) * 1000, 2)

            core_name = getattr(self.kernel, "CORE_NAME", "standard")
            uptime_str = self._format_uptime(time.time() - self.kernel.start_time)

            custom_text = str(self.config.get("info_custom_text") or "")

            if custom_text:
                info_text = await self._build_custom_text(
                    custom_text, ping_time, uptime_str, core_name
                )
            else:
                info_text = await self._build_default_text(
                    ping_time, uptime_str, core_name
                )

            banner_url = self.config.get("info_banner_url") or ""
            quote_media = bool(self.config.get("info_quote_media"))
            invert_media = bool(self.config.get("info_invert_media"))

            if (
                banner_url
                and quote_media
                and banner_url.startswith(("http://", "https://"))
            ):
                try:
                    await msg.edit(
                        info_text,
                        file=InputMediaWebPage(banner_url, optional=True),
                        parse_mode="html",
                        invert_media=invert_media,
                    )
                    return
                except Exception as e:
                    self.log.error(f"Info banner error: {e}")

            has_banner = False
            if banner_url:
                if banner_url.startswith(("http://", "https://")):
                    has_banner = True
                elif os.path.exists(banner_url):
                    has_banner = True
                else:
                    default_banner = os.path.join(self.kernel.IMG_DIR, "info.png")
                    if os.path.exists(default_banner):
                        banner_url = default_banner
                        has_banner = True

            if has_banner and banner_url:
                try:
                    if banner_url.startswith(("http://", "https://")):
                        media = InputMediaWebPage(banner_url, optional=True)
                        await msg.edit(
                            info_text,
                            file=media,
                            parse_mode="html",
                            invert_media=invert_media,
                        )
                    else:
                        await msg.edit(
                            info_text,
                            file=banner_url,
                            parse_mode="html",
                            invert_media=invert_media,
                        )
                except Exception as e:
                    await msg.edit(info_text, parse_mode="html")
                    self.log.error(f"Info banner error: {e}")
            else:
                await msg.edit(info_text, parse_mode="html")

        except Exception as e:
            import traceback

            self.log.error(f"Info error: {traceback.format_exc()}")
            try:
                await event.edit(
                    self.strings("error_see_logs", warning=CUSTOM_EMOJI["⚠️"]),
                    parse_mode="html",
                )
            except Exception:
                pass

    async def _build_custom_text(
        self,
        custom_text: str,
        ping_time: float,
        uptime_str: str,
        core_name: str,
    ) -> str:
        now = datetime.now()

        month_names_ru = [
            "Января",
            "Февраля",
            "Марта",
            "Апреля",
            "Мая",
            "Июня",
            "Июля",
            "Августа",
            "Сентября",
            "Октября",
            "Ноября",
            "Декабря",
        ]
        month_names_en = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        weekday_names_ru = [
            "Понедельник",
            "Вторник",
            "Среда",
            "Четверг",
            "Пятница",
            "Суббота",
            "Воскресенье",
        ]
        weekday_names_en = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        use_ru = self.get_lang() == "ru"
        now_date = now.strftime("%d.%m.%Y")
        now_time = now.strftime("%H:%M:%S")
        now_day = now.strftime("%d")
        now_month = now.strftime("%m")
        now_month_name = (month_names_ru if use_ru else month_names_en)[now.month - 1]
        now_year = now.strftime("%Y")
        now_weekday = (weekday_names_ru if use_ru else weekday_names_en)[now.weekday()]
        now_hour = now.strftime("%H")
        now_minute = now.strftime("%M")
        now_second = now.strftime("%S")

        identity = self.cache.get("info:identity")
        if identity is None or not isinstance(identity, tuple) or len(identity) != 2:
            try:
                system_user = getpass.getuser()
                hostname = socket.gethostname()
            except Exception:
                system_user = hostname = "Unknown"
            identity = (system_user, hostname)
            self.cache.set("info:identity", identity)
        else:
            system_user, hostname = identity

        cpu_usage, ram_usage = self._get_system_info()
        update_needed = await self._check_update()

        me = self.cache.get("info:me")
        if me is None:
            me = await self.kernel.client.get_me()
            self.cache.set("info:me", me, ttl=3600)

        user_emojis = {
            6020965582: "5469888215802482605",
            2037125547: "5467932472379480411",
            779572293: "5470163024989952512",
            8405520863: "5470170528297817805",
            855890735: "5470063433288290290",
        }
        user = f'<tg-emoji emoji-id="{user_emojis.get(me.id, "5470015630302287916")}">{"Ⓜ️" if me.id in user_emojis else "🕳"}</tg-emoji>'
        mcub_emoji = (
            f'{user}<tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
            if me.premium
            else "Mitrich UserBot"
        )

        version_info = self.cache.get("info:version_info")
        if version_info and isinstance(version_info, tuple) and len(version_info) == 3:
            branch, commit_sha, commit_url = version_info
        else:
            branch = await self.kernel.version_manager.detect_branch()
            commit_sha = await self.kernel.version_manager.get_commit_sha()
            commit_url = await self.kernel.version_manager.get_github_commit_url()
            version_info = (branch, commit_sha, commit_url)
            self.cache.set("info:version_info", version_info, ttl=600)

        distro_name, distro_emoji = self._get_distro()
        platform_type = self._get_platform_type()

        known = [
            "kernel_version",
            "core_name",
            "ping_time",
            "uptime_str",
            "distro_name",
            "distro_emoji",
            "platform_type",
            "cpu_usage",
            "ram_usage",
            "system_user",
            "hostname",
            "update_needed",
            "branch",
            "commit_sha",
            "commit_url",
            "mcub_emoji",
            "user_id",
            "me_first_name",
            "me_username",
            "now_date",
            "now_time",
            "now_day",
            "now_month",
            "now_month_name",
            "now_year",
            "now_weekday",
            "now_hour",
            "now_minute",
            "now_second",
        ]
        safe = custom_text.replace("{", "{{").replace("}", "}}")
        for k in known:
            safe = safe.replace("{{" + k + "}}", "{" + k + "}")

        try:
            return safe.format(
                kernel_version=self.kernel.VERSION,
                core_name=core_name,
                ping_time=ping_time,
                uptime_str=uptime_str,
                distro_name=distro_name,
                distro_emoji=distro_emoji,
                platform_type=platform_type,
                cpu_usage=cpu_usage,
                ram_usage=ram_usage,
                system_user=system_user,
                hostname=hostname,
                update_needed=update_needed,
                branch=branch,
                commit_sha=commit_sha,
                commit_url=commit_url or "",
                mcub_emoji=mcub_emoji,
                user_id=me.id,
                me_first_name=me.first_name or "",
                me_username=f"@{me.username}" if me.username else "",
                now_date=now_date,
                now_time=now_time,
                now_day=now_day,
                now_month=now_month,
                now_month_name=now_month_name,
                now_year=now_year,
                now_weekday=now_weekday,
                now_hour=now_hour,
                now_minute=now_minute,
                now_second=now_second,
            )
        except Exception as e:
            return self.strings("custom_text_error", error=str(e))

    async def _build_default_text(
        self,
        ping_time: float,
        uptime_str: str,
        core_name: str,
    ) -> str:
        distro_name, distro_emoji = self._get_distro()
        platform_type = self._get_platform_type()
        cpu_usage, ram_usage = self._get_system_info()
        update_needed = await self._check_update()

        identity = self.cache.get("info:identity")
        if identity is None or not isinstance(identity, tuple) or len(identity) != 2:
            try:
                system_user = getpass.getuser()
                hostname = socket.gethostname()
            except Exception:
                system_user = hostname = "Unknown"
            identity = (system_user, hostname)
            self.cache.set("info:identity", identity)
        else:
            system_user, hostname = identity

        me = self.cache.get("info:me")
        if me is None:
            me = await self.kernel.client.get_me()
            self.cache.set("info:me", me, ttl=3600)

        user_emojis = {
            6020965582: "5469888215802482605",
            2037125547: "5467932472379480411",
            779572293: "5470163024989952512",
            8405520863: "5470170528297817805",
            855890735: "5470063433288290290",
        }
        user = f'<tg-emoji emoji-id="{user_emojis.get(me.id, "5470015630302287916")}">{"Ⓜ️" if me.id in user_emojis else "🕳"}</tg-emoji>'
        mcub_emoji = (
            f'{user}<tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
            if me.premium
            else "Mitrich UserBot"
        )

        version_info = self.cache.get("info:version_info")
        if version_info and isinstance(version_info, tuple) and len(version_info) == 3:
            branch, commit_sha, commit_url = version_info
        else:
            branch = await self.kernel.version_manager.detect_branch()
            commit_sha = await self.kernel.version_manager.get_commit_sha()
            commit_url = await self.kernel.version_manager.get_github_commit_url()
            version_info = (branch, commit_sha, commit_url)
            self.cache.set("info:version_info", version_info, ttl=600)

        update_emoji = CUSTOM_EMOJI["💔"] if update_needed else CUSTOM_EMOJI["🔮"]
        update_text = "Update needed" if update_needed else "No update needed"

        branch_display = (
            f'{CUSTOM_EMOJI["🌐"]}<b> Branch: {branch}</b><b><a href="{commit_url}">#{commit_sha}</a></b>'
            if commit_url
            else f"{CUSTOM_EMOJI['🌐']}<b> Branch {branch}#{commit_sha}</b>"
        )

        return f"""<b>{mcub_emoji}</b>
<blockquote>{CUSTOM_EMOJI["🌩️"]} <b>Version:</b> <code>{self.kernel.VERSION}</code>
{CUSTOM_EMOJI["🧩"]} <b>Kernel:</b> <code>{core_name}</code>
{update_emoji} <b>{update_text}</b>
{branch_display}</blockquote>

<blockquote>{CUSTOM_EMOJI["📡"]} <b>Ping:</b> <code>{ping_time} ms</code>
{CUSTOM_EMOJI["🧪"]} <b>Uptime:</b> <code>{uptime_str}</code>
{CUSTOM_EMOJI["🔬"]} <b>System:</b> {distro_name} {distro_emoji}
{CUSTOM_EMOJI["🧬"]} <b>Platform:</b> <code>{platform_type}</code></blockquote>

<blockquote>{CUSTOM_EMOJI["🔷"]} <b>CPU:</b> <i>~{cpu_usage}</i>
{CUSTOM_EMOJI["🔶"]} <b>RAM:</b> <i>~{ram_usage}</i></blockquote>"""

    def _add_link_preview(self, text: str, entities: list, link: str) -> tuple:
        if not text or not link:
            return text, entities

        new_text = ZERO_WIDTH_CHAR + text
        new_entities = []

        if entities:
            for entity in entities:
                new_entity = copy(entity)
                if hasattr(entity, "offset"):
                    new_entity.offset += 1
                new_entities.append(new_entity)

        link_entity = MessageEntityTextUrl(offset=0, length=1, url=link)
        new_entities.append(link_entity)
        return new_text, new_entities
