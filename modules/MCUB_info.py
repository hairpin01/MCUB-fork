# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

# author: @Hairpin00
# version: 1.0.0
# description: System and device info module / Модуль информации о системе
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

import psutil
from telethon import functions
from telethon.tl.types import InputMediaWebPage, MessageEntityTextUrl

from core.lib.loader.module_config import (
    Boolean,
    ConfigValue,
    ModuleConfig,
    String,
)
from utils.platform import get_platform, is_termux, is_wsl


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
    "🚫": '<tg-emoji emoji-id="5472267631979405211">🚫</tg-emoji>',
    "⛔️": '<tg-emoji emoji-id="4918014360267260850">⛔️</tg-emoji>',
    "❌": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji>',
    "⚠️": '<tg-emoji emoji-id="5904692292324692386">⚠️</tg-emoji>',
    "🧩": '<tg-emoji emoji-id="5332534105114445343">🧩</tg-emoji>',
    "🌐": '<tg-emoji emoji-id="4906943755644306322">🌐</tg-emoji>',
}

ZERO_WIDTH_CHAR = "\u2060"


def add_link_preview(text, entities, link):
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


def register(kernel):
    client = kernel.client
    language = kernel.config.get("language", "en")

    strings = {
        "en": {
            "custom_text_error": "<b>Error in custom text format:</b> {error}",
            "quote_mode_error": "Error in quote mode",
            "send_banner_error": "Error sending banner",
            "error_see_logs": "{warning} <b>Error, see logs</b>",
        },
        "ru": {
            "custom_text_error": "<b>Ошибка в форматировании кастомного текста:</b> {error}",
            "quote_mode_error": "Ошибка в режиме цитирования",
            "send_banner_error": "Ошибка отправки баннера",
            "error_see_logs": "{warning} <b>Ошибка, смотри логи</b>",
        },
    }

    lang_strings = strings.get(language, strings["en"])

    def t(key, **kwargs):
        if key not in lang_strings:
            return key
        return lang_strings[key].format(**kwargs)

    branch = _detect_branch_sync()

    config = ModuleConfig(
        ConfigValue(
            "info_quote_media",
            False,
            description="Send media in quotes",
            validator=Boolean(default=False),
        ),
        ConfigValue(
            "info_banner_url",
            f"https://raw.githubusercontent.com/hairpin01/MCUB-fork/refs/heads/{branch}/img/info.png",
            description="Banner image URL",
            validator=String(default=""),
        ),
        ConfigValue(
            "info_invert_media",
            False,
            description="Invert media colors",
            validator=Boolean(default=False),
        ),
        ConfigValue(
            "info_custom_text",
            None,
            description="""Custom text for .info. Available placeholders: {kernel_version}, {core_name}, {ping_time}, {uptime_str}, {distro_name}, {distro_emoji}, {platform_type}, {cpu_usage}, {ram_usage}, {system_user}, {hostname}, {update_emoji}, {update_text}, {update_needed}, {branch}, {commit_sha}, {commit_url}, {mcub_emoji}, {user_id}, {me_first_name}, {me_username}, {now_date}, {now_time}, {now_day}, {now_month}, {now_month_name}, {now_year}, {now_weekday}, {now_hour}, {now_minute}, {now_second}""",
            validator=String(default=None),
        ),
        ConfigValue(
            "info_start_emoji",
            CUSTOM_EMOJI["load"],
            description="Emoji for .info start",
            validator=String(default=CUSTOM_EMOJI["load"]),
        ),
    )

    def get_config():
        live_cfg = getattr(kernel, "_live_module_configs", {}).get(__name__)
        if live_cfg:
            return live_cfg
        return config

    async def startup():
        config_dict = await kernel.get_module_config(
            __name__,
            {
                "info_quote_media": False,
                "info_banner_url": f"https://raw.githubusercontent.com/hairpin01/MCUB-fork/refs/heads/{branch}/img/info.png",
                "info_invert_media": False,
                "info_custom_text": None,
                "info_start_emoji": CUSTOM_EMOJI["load"],
            },
        )
        config.from_dict(config_dict)
        await kernel.save_module_config(__name__, config.to_dict())
        kernel.store_module_config_schema(__name__, config)

    asyncio.create_task(startup())

    def resolve_info_start_emoji() -> str:
        """Resolve configurable start emoji for .info with sensible fallbacks."""
        cfg = get_config()
        raw = (
            cfg.get("info_start_emoji", CUSTOM_EMOJI["load"])
            if cfg
            else CUSTOM_EMOJI["load"]
        )
        if not isinstance(raw, str):
            return CUSTOM_EMOJI["load"]
        value = raw.strip()
        if not value:
            return CUSTOM_EMOJI["load"]
        return CUSTOM_EMOJI.get(value, value)

    def format_uptime(seconds):
        seconds = int(seconds)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    async def check_update():
        cached = kernel.cache.get("info:update_needed")
        if cached is not None:
            return cached
        try:
            repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
                return False

            code, output = await run_git(["rev-list", "--count", "HEAD..@{u}"])
            if code == 0 and output.isdigit():
                result = int(output) > 0
                kernel.cache.set("info:update_needed", result, ttl=300)
                return result

            kernel.cache.set("info:update_needed", False, ttl=300)
            return False
        except Exception:
            return False

    def get_system_info():
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

    @kernel.register.command(
        "info",
        doc_en="show userbot info (version, uptime, ping)",
        doc_ru="показать инфо о юзерботе (версия, аптайм, пинг)",
    )
    async def info_cmd(event):
        """no args, info mcub-fork"""
        try:
            start_time = time.time()
            msg = await event.edit(resolve_info_start_emoji(), parse_mode="html")
            ping_time = round((time.time() - start_time) * 1000, 2)

            core_name = getattr(kernel, "CORE_NAME", "standard")

            uptime_str = format_uptime(time.time() - kernel.start_time)

            cfg = get_config()
            custom_text = cfg.get("info_custom_text") if cfg else None

            if custom_text:

                def uses(*keys):
                    return any(f"{{{k}}}" in custom_text for k in keys)

                _now = datetime.now()
                _month_names_ru = [
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
                _month_names_en = [
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
                _weekday_names_ru = [
                    "Понедельник",
                    "Вторник",
                    "Среда",
                    "Четверг",
                    "Пятница",
                    "Суббота",
                    "Воскресенье",
                ]
                _weekday_names_en = [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ]
                _use_ru = language == "ru"
                now_date = _now.strftime("%d.%m.%Y")
                now_time = _now.strftime("%H:%M:%S")
                now_day = _now.strftime("%d")
                now_month = _now.strftime("%m")
                now_month_name = (_month_names_ru if _use_ru else _month_names_en)[
                    _now.month - 1
                ]
                now_year = _now.strftime("%Y")
                now_weekday = (_weekday_names_ru if _use_ru else _weekday_names_en)[
                    _now.weekday()
                ]
                now_hour = _now.strftime("%H")
                now_minute = _now.strftime("%M")
                now_second = _now.strftime("%S")

                # distro_name / distro_emoji
                if uses("distro_name", "distro_emoji"):
                    distro_name = kernel.cache.get("info:distro_name")
                    if distro_name is None:
                        distro_name = "Unknown"
                        try:
                            if os.path.exists("/etc/os-release"):
                                with open("/etc/os-release") as f:
                                    for line in f:
                                        if "PRETTY_NAME" in line:
                                            distro_name = (
                                                line.split("=")[1].strip().strip('"')
                                            )
                                            break
                            else:
                                distro_name = platform.platform()
                        except Exception:
                            distro_name = "Linux"
                        kernel.cache.set("info:distro_name", distro_name)
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
                else:
                    distro_name = distro_emoji = ""

                # platform_type
                if uses("platform_type"):
                    platform_type = kernel.cache.get("info:platform_type")
                    if platform_type is None:
                        get_platform()
                        platform_type = f"VDS {CUSTOM_EMOJI['vds']}"
                        if is_wsl():
                            platform_type = f"WSL {CUSTOM_EMOJI['wsl']}"
                        elif is_termux():
                            platform_type = f"Termux {CUSTOM_EMOJI['termux']}"
                        kernel.cache.set("info:platform_type", platform_type)
                else:
                    platform_type = ""

                # cpu_usage / ram_usage — sync sleep 0.1 s
                if uses("cpu_usage", "ram_usage"):
                    cpu_usage, ram_usage = get_system_info()
                else:
                    cpu_usage = ram_usage = ""

                # update_needed / update_emoji / update_text
                if uses("update_needed", "update_emoji", "update_text"):
                    update_needed = await check_update()
                    update_emoji = (
                        CUSTOM_EMOJI["💔"] if update_needed else CUSTOM_EMOJI["🔮"]
                    )
                    update_text = (
                        "Update needed" if update_needed else "No update needed"
                    )
                else:
                    update_needed = False
                    update_emoji = update_text = ""

                # system_user / hostname
                if uses("system_user", "hostname"):
                    _identity = kernel.cache.get("info:identity")
                    if _identity is None:
                        try:
                            system_user = getpass.getuser()
                            hostname = socket.gethostname()
                        except Exception:
                            system_user = hostname = "Unknown"
                        kernel.cache.set("info:identity", (system_user, hostname))
                    else:
                        system_user, hostname = _identity
                else:
                    system_user = hostname = ""

                # me / user_id / mcub_emoji / me_first_name / me_username — get_me()
                if uses("me_first_name", "me_username", "user_id", "mcub_emoji"):
                    me = kernel.cache.get("info:me")
                    if me is None:
                        me = await client.get_me()
                        kernel.cache.set("info:me", me, ttl=3600)
                    user_ids = me.id
                    _user_emojis = {
                        6020965582: "5469888215802482605",
                        2037125547: "5467932472379480411",
                        779572293: "5470163024989952512",
                        8405520863: "5470170528297817805",
                        855890735: "5470063433288290290",
                    }
                    _user = f'<tg-emoji emoji-id="{_user_emojis.get(user_ids, "5470015630302287916")}">{"Ⓜ️" if user_ids in _user_emojis else "🕳"}</tg-emoji>'
                    mcub_emoji = (
                        f'{_user}<tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
                        if me.premium
                        else "Mitrich UserBot"
                    )
                    me_first_name = me.first_name or ""
                    me_username = f"@{me.username}" if me.username else ""
                else:
                    user_ids = mcub_emoji = me_first_name = me_username = ""

                # branch / commit_sha / commit_url
                if uses("branch", "commit_sha", "commit_url"):
                    _version_info = kernel.cache.get("info:version_info")
                    if _version_info is None:
                        branch = await kernel.version_manager.detect_branch()
                        commit_sha = await kernel.version_manager.get_commit_sha()
                        commit_url = (
                            await kernel.version_manager.get_github_commit_url()
                        )
                        kernel.cache.set(
                            "info:version_info",
                            (branch, commit_sha, commit_url),
                            ttl=600,
                        )
                    else:
                        branch, commit_sha, commit_url = _version_info
                else:
                    branch = commit_sha = commit_url = ""

                try:
                    _known = [
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
                        "update_emoji",
                        "update_text",
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
                    _safe = custom_text.replace("{", "{{").replace("}", "}}")
                    for _k in _known:
                        _safe = _safe.replace("{{" + _k + "}}", "{" + _k + "}")
                    info_text = _safe.format(
                        kernel_version=kernel.VERSION,
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
                        update_emoji=update_emoji,
                        update_text=update_text,
                        update_needed=update_needed,
                        branch=branch,
                        commit_sha=commit_sha,
                        commit_url=commit_url or "",
                        mcub_emoji=mcub_emoji,
                        user_id=user_ids,
                        me_first_name=me_first_name,
                        me_username=me_username,
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
                    await kernel.handle_error(
                        e, source="info_cmd:custom_text_format", event=event
                    )
                    info_text = t("custom_text_error", error=str(e))

            else:
                distro_name = kernel.cache.get("info:distro_name")
                if distro_name is None:
                    distro_name = "Unknown"
                    try:
                        if os.path.exists("/etc/os-release"):
                            with open("/etc/os-release") as f:
                                for line in f:
                                    if "PRETTY_NAME" in line:
                                        distro_name = (
                                            line.split("=")[1].strip().strip('"')
                                        )
                                        break
                        else:
                            distro_name = platform.platform()
                    except Exception:
                        distro_name = "Linux"
                    kernel.cache.set("info:distro_name", distro_name)

                distro_emojis = {
                    "arch": CUSTOM_EMOJI["arch"],
                    "ubuntu": CUSTOM_EMOJI["ubuntu"],
                    "mint": CUSTOM_EMOJI["mint"],
                    "fedora": CUSTOM_EMOJI["fedora"],
                    "centos": CUSTOM_EMOJI["centos"],
                }
                distro_emoji = ""
                distro_lower = distro_name.lower()
                for key, emoji in distro_emojis.items():
                    if key in distro_lower:
                        distro_emoji = emoji
                        break

                platform_type = kernel.cache.get("info:platform_type")
                if platform_type is None:
                    get_platform()
                    platform_type = f"VDS {CUSTOM_EMOJI['vds']}"
                    if is_wsl():
                        platform_type = f"WSL {CUSTOM_EMOJI['wsl']}"
                    elif is_termux():
                        platform_type = f"Termux {CUSTOM_EMOJI['termux']}"
                    kernel.cache.set("info:platform_type", platform_type)

                cpu_usage, ram_usage = get_system_info()
                update_needed = await check_update()

                _identity = kernel.cache.get("info:identity")
                if _identity is None:
                    try:
                        system_user = getpass.getuser()
                        hostname = socket.gethostname()
                    except Exception:
                        system_user = hostname = "Unknown"
                    kernel.cache.set("info:identity", (system_user, hostname))
                else:
                    system_user, hostname = _identity

                update_emoji = (
                    CUSTOM_EMOJI["💔"] if update_needed else CUSTOM_EMOJI["🔮"]
                )
                update_text = "Update needed" if update_needed else "No update needed"

                me = kernel.cache.get("info:me")
                if me is None:
                    me = await client.get_me()
                    kernel.cache.set("info:me", me, ttl=3600)
                user_ids = me.id

                user_emojis = {
                    6020965582: "5469888215802482605",
                    2037125547: "5467932472379480411",
                    779572293: "5470163024989952512",
                    8405520863: "5470170528297817805",
                    855890735: "5470063433288290290",
                }
                user = f'<tg-emoji emoji-id="{user_emojis.get(user_ids, "5470015630302287916")}">{"Ⓜ️" if user_ids in user_emojis else "🕳"}</tg-emoji>'
                mcub_emoji = (
                    f'{user}<tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
                    if me.premium
                    else "Mitrich UserBot"
                )

                _version_info = kernel.cache.get("info:version_info")
                if _version_info is None:
                    branch = await kernel.version_manager.detect_branch()
                    commit_sha = await kernel.version_manager.get_commit_sha()
                    commit_url = await kernel.version_manager.get_github_commit_url()
                    kernel.cache.set(
                        "info:version_info", (branch, commit_sha, commit_url), ttl=600
                    )
                else:
                    branch, commit_sha, commit_url = _version_info

                branch_display = (
                    f'{CUSTOM_EMOJI["🌐"]}<b> Branch: {branch}</b><b><a href="{commit_url}">#{commit_sha}</a></b>'
                    if commit_url
                    else f"{CUSTOM_EMOJI['🌐']}<b> Branch {branch}#{commit_sha}</b>"
                )
                info_text = f"""<b>{mcub_emoji}</b>
<blockquote>{CUSTOM_EMOJI["🌩️"]} <b>Version:</b> <code>{kernel.VERSION}</code>
{CUSTOM_EMOJI["🧩"]} <b>Kernel:</b> <code>{core_name}</code>
{f"{CUSTOM_EMOJI['💔']} <b>Update needed</b>" if update_needed else f"{CUSTOM_EMOJI['🔮']} <b>No update needed</b>"}
{branch_display}</blockquote>

<blockquote>{CUSTOM_EMOJI["📡"]} <b>Ping:</b> <code>{ping_time} ms</code>
{CUSTOM_EMOJI["🧪"]} <b>Uptime:</b> <code>{uptime_str}</code>
{CUSTOM_EMOJI["🔬"]} <b>System:</b> {distro_name} {distro_emoji}
{CUSTOM_EMOJI["🧬"]} <b>Platform:</b> <code>{platform_type}</code></blockquote>

<blockquote>{CUSTOM_EMOJI["🔷"]} <b>CPU:</b> <i>~{cpu_usage}</i>
{CUSTOM_EMOJI["🔶"]} <b>RAM:</b> <i>~{ram_usage}</i></blockquote>"""

            cfg = get_config()
            banner_url = cfg.get("info_banner_url") if cfg else ""
            quote_media = cfg.get("info_quote_media", False) if cfg else False
            invert_media = cfg.get("info_invert_media", False) if cfg else False

            if (
                quote_media
                and banner_url
                and banner_url.startswith(("http://", "https://"))
            ):
                try:
                    text, entities = await client._parse_message_text(info_text, "html")
                    text, entities = add_link_preview(text, entities, banner_url)

                    try:
                        await msg.edit(
                            text,
                            formatting_entities=entities,
                            link_preview=True,
                            invert_media=invert_media,
                        )
                        return
                    except TypeError:
                        await client(
                            functions.messages.EditMessageRequest(
                                peer=await event.get_input_chat(),
                                id=msg.id,
                                message=text,
                                entities=entities,
                                invert_media=invert_media,
                                no_webpage=False,
                            )
                        )
                        return

                except Exception as e:
                    await kernel.handle_error(
                        e, source="info_cmd:quote_mode", event=event
                    )

            has_banner = False
            if banner_url:
                if banner_url.startswith(("http://", "https://")):
                    has_banner = True
                else:
                    if os.path.exists(banner_url):
                        has_banner = True
                    else:
                        current_dir = Path.cwd()
                        possible_paths = [
                            Path(banner_url),
                            current_dir / banner_url,
                            Path(kernel.IMG_DIR) / "info.png",
                        ]

                        for path in possible_paths:
                            if path.exists():
                                banner_url = str(path)
                                has_banner = True
                                break

            if not has_banner:
                default_banner = os.path.join(kernel.IMG_DIR, "info.png")
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
                    await kernel.handle_error(
                        e, source="info_cmd:send_banner", event=event
                    )
            else:
                await msg.edit(info_text, parse_mode="html")

        except Exception as e:
            await event.edit(
                t("error_see_logs", warning=CUSTOM_EMOJI["⚠️"]), parse_mode="html"
            )
            await kernel.handle_error(e, source="info_cmd", event=event)
