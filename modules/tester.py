# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import asyncio
import getpass
import json
import os
import platform
import random
import re
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from typing import Any

try:
    import psutil as _psutil
except ImportError:
    _psutil = None

from copy import copy

from telethon.tl.functions import PingRequest
from telethon.tl.types import InputMediaWebPage, MessageEntityTextUrl

import utils
from core.lib.loader.module_base import ModuleBase, callback, command
from core.lib.loader.module_config import (
    Boolean,
    ConfigValue,
    DictType,
    ModuleConfig,
    Placeholders,
    String,
)
from utils.strings import Strings


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
    "📝": '<tg-emoji emoji-id="5334882760735598374">📝</tg-emoji>',
    "📁": '<tg-emoji emoji-id="5433653135799228968">📁</tg-emoji>',
    "📚": '<tg-emoji emoji-id="5373098009640836781">📚</tg-emoji>',
    "📖": '<tg-emoji emoji-id="5226512880362332956">📖</tg-emoji>',
    "🖨": '<tg-emoji emoji-id="5386494631112353009">🖨</tg-emoji>',
    "☑️": '<tg-emoji emoji-id="5454096630372379732">☑️</tg-emoji>',
    "💬": '<tg-emoji emoji-id="5465300082628763143">💬</tg-emoji>',
    "🗯": '<tg-emoji emoji-id="5465132703458270101">🗯</tg-emoji>',
    "✏️": '<tg-emoji emoji-id="5334673106202010226">✏️</tg-emoji>',
    "🐢": '<tg-emoji emoji-id="5350813992732338949">🐢</tg-emoji>',
    "🧊": '<tg-emoji emoji-id="5404728536810398694">🧊</tg-emoji>',
    "❄️": '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>',
    "📎": '<tg-emoji emoji-id="5377844313575150051">📎</tg-emoji>',
    "🗳": '<tg-emoji emoji-id="5359741159566484212">🗳</tg-emoji>',
    "📰": '<tg-emoji emoji-id="5433982607035474385">📰</tg-emoji>',
    "🛰": '<tg-emoji emoji-id="5321304062715517873">🛰</tg-emoji>',
}


def _default_dynamic_start_emojis() -> dict[str, str]:
    return {"low_emoji": CUSTOM_EMOJI["🛰"], "high_emoji": CUSTOM_EMOJI["🐢"]}


def _normalize_dynamic_start_emojis(value: Any) -> dict[str, str]:
    default = _default_dynamic_start_emojis()

    if isinstance(value, dict):
        low_emoji = value.get("low_emoji") or default["low_emoji"]
        high_emoji = value.get("high_emoji") or default["high_emoji"]
        return {"low_emoji": str(low_emoji), "high_emoji": str(high_emoji)}

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return default
        try:
            parsed = json.loads(raw)
        except Exception:
            return {"low_emoji": raw, "high_emoji": raw}
        return _normalize_dynamic_start_emojis(parsed)

    return default


class _FakeEventProxy:
    """Proxies an event and logs all method calls and attribute accesses."""

    def __init__(self, original, *, fake_text=None):
        self._orig = original
        self._fake_text = fake_text
        self._call_log = []

    def _log(self, msg):
        self._call_log.append(msg)

    def get_log(self):
        return list(self._call_log)

    def __getattr__(self, name):
        if name == "text" and self._fake_text is not None:
            self._log(f"[ATTR] text -> '{self._fake_text}' (fake)")
            return self._fake_text
        if name.startswith("_"):
            raise AttributeError(name)
        orig_attr = getattr(self._orig, name)
        if not callable(orig_attr):
            self._log(f"[ATTR] {name} = {orig_attr!r}")
            return orig_attr
        if asyncio.iscoroutinefunction(orig_attr):

            async def async_wrapper(*args, **kwargs):
                self._log(f"[CALL] {name}(args={args}, kwargs={kwargs})")
                try:
                    result = await orig_attr(*args, **kwargs)
                    self._log(f"[RESULT] {name} -> {result!r}")
                    return result
                except Exception as e:
                    self._log(f"[ERROR] {name} -> {e}")
                    raise

            return async_wrapper
        else:

            def sync_wrapper(*args, **kwargs):
                self._log(f"[CALL] {name}(args={args}, kwargs={kwargs})")
                try:
                    result = orig_attr(*args, **kwargs)
                    self._log(f"[RESULT] {name} -> {result!r}")
                    return result
                except Exception as e:
                    self._log(f"[ERROR] {name} -> {e}")
                    raise

            return sync_wrapper

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._orig, name, value)


class TesterMod(ModuleBase):
    name = "tester"
    version = "1.0.0"
    author = "@hairpin00"

    async def on_load(self) -> None:
        branch = _detect_branch_sync()
        config_dict = await self.kernel.get_module_config(
            self.name,
            {
                "quote_media": False,
                "invert_media": False,
                "custom_text": "",
                "start_emoji": "✏️",
                "banner_url": f"https://raw.githubusercontent.com/hairpin01/MCUB-fork/refs/heads/{branch}/img/ping.png",
                "start_banner_url": "",
            },
        )
        utils.register_decorated_placeholders(self.name, self)

        if isinstance(config_dict, dict):
            stored_dynamic_emojis = config_dict.get("start_emoji_dynamically")
            if stored_dynamic_emojis is not None:
                normalized_dynamic_emojis = _normalize_dynamic_start_emojis(
                    stored_dynamic_emojis
                )
                if normalized_dynamic_emojis != stored_dynamic_emojis:
                    config_dict = dict(config_dict)
                    config_dict["start_emoji_dynamically"] = normalized_dynamic_emojis

        self.config.from_dict(config_dict)
        config_dict_clean = {
            k: v for k, v in self.config.to_dict().items() if v is not None
        }
        if config_dict_clean:
            await self.kernel.save_module_config(self.name, config_dict_clean)
        self.kernel.store_module_config_schema(self.name, self.config)

    async def on_unload(self) -> None:
        utils.unregister_scope(self.name)

    description: dict[str, str] = {
        "ru": "Тecтep мoдyль (пинг, лoги, зaмopoзкa)",
        "en": "Tester module (ping, logs, freezing)",
    }

    config = ModuleConfig(
        ConfigValue(
            "quote_media",
            False,
            description="Send media with quote in .ping",
            validator=Boolean(),
        ),
        ConfigValue(
            "invert_media",
            False,
            description="Invert media colors",
            validator=Boolean(),
        ),
        ConfigValue(
            "banner_url",
            "",
            description="Banner image URL for inline preview",
            validator=String(),
        ),
        ConfigValue(
            "start_banner_url",
            "",
            description="Start banner image URL for inline preview",
            validator=String(),
        ),
        ConfigValue(
            "custom_text",
            "",
            description=(
                "Custom text for .ping. Available placeholders:\n"
                "{ping_time}, {raw_ping}, {prev_ping}, {ping_diff}, {timings},\n"
                "{avg_ping}, {min_ping}, {max_ping}, {ping_count},\n"
                "{dynamic_emoji}, {start_emoji}, {uptime}, {system_user}, {hostname},\n"
                "{cpu_usage}, {ram_usage}, {branch}, {commit_sha},\n"
                "{now_date}, {now_time}, {now_day}, {now_month},\n"
                "{now_month_name}, {now_year}, {now_weekday},\n"
                "{now_hour}, {now_minute}, {now_second}\n"
                "Heroku/hikka placeholders supported."
            ),
            validator=Placeholders(placeholder_scope="any"),
        ),
        ConfigValue(
            "start_emoji",
            CUSTOM_EMOJI["✏️"],
            description="Start emoji for .ping",
            validator=String(),
        ),
        ConfigValue(
            "start_emoji_dynamically_enabled",
            False,
            description=(
                "Enable dynamic start_emoji in .ping result: picks low_emoji/high_emoji "
                "from start_emoji_dynamically depending on whether this ping is faster "
                "or slower than your previous average ping. Uses low_emoji until "
                "there's at least one prior measurement."
            ),
            validator=Boolean(),
        ),
        ConfigValue(
            "start_emoji_dynamically",
            _default_dynamic_start_emojis,
            description=(
                "JSON dict with 'low_emoji' (ping faster than avg) and 'high_emoji' "
                "(ping slower than avg) keys. Values accept the same emoji/custom-emoji "
                "shortcuts as start_emoji. Only used when "
                "start_emoji_dynamically_enabled is True."
            ),
            validator=DictType(),
        ),
    )

    strings: dict[str, dict[str, str]] | Strings = {"name": "tester"}

    log_level_pattern = re.compile(r"^\d{4}-\d{2}-\d{2} .* \[([A-Z]+)\] ")
    log_level_labels = ["debug", "info", "warning", "error", "critical", "all"]

    def _normalize_log_level(self, value: str | None) -> str | None:
        if not value:
            return None
        value = value.strip().lower()
        return value if value in self.log_level_labels else None

    def _build_filtered_log(self, level: str, kernel_log_path: str) -> str | None:
        if level == "all":
            return kernel_log_path

        temp_path = os.path.join(tempfile.gettempdir(), f"kernel.{level}.log")
        temp = open(temp_path, "w", encoding="utf-8")
        keep_block = False
        wrote = False
        try:
            with open(kernel_log_path, encoding="utf-8", errors="ignore") as src:
                for line in src:
                    match = self.log_level_pattern.match(line)
                    if match:
                        keep_block = match.group(1).lower() == level
                    if keep_block:
                        temp.write(line)
                        wrote = True
            temp.close()
            if not wrote:
                os.unlink(temp_path)
                return None
            return temp_path
        except Exception:
            try:
                temp.close()
                os.unlink(temp_path)
            except Exception:
                pass
            raise

    async def _resolve_version_info(self):
        version_info = self.cache.get("tester:version_info")
        if (
            version_info is None
            or not isinstance(version_info, tuple)
            or len(version_info) != 3
        ):
            branch = await self.kernel.version_manager.detect_branch()
            commit_sha = await self.kernel.version_manager.get_commit_sha()
            commit_url = await self.kernel.version_manager.get_github_commit_url()
            version_info = (branch, commit_sha, commit_url)
            self.cache.set("tester:version_info", version_info, ttl=600)
        return version_info

    async def _send_logs(self, target: Any, level: str):
        kernel_log_path = os.path.join(self.kernel.LOGS_DIR, "kernel.log")
        if not os.path.exists(kernel_log_path):
            await target.edit(
                self.strings("logs_not_found", file=CUSTOM_EMOJI["📁"]),
                parse_mode="html",
            )
            return

        if os.path.getsize(kernel_log_path) == 0:
            await target.edit(
                f"{CUSTOM_EMOJI['🗳']} {self.strings('file_empty')}",
                parse_mode="html",
            )
            return

        selected_path = self._build_filtered_log(level, kernel_log_path)
        if selected_path is None:
            await target.edit(
                f"{CUSTOM_EMOJI['🗳']} {self.strings('file_empty')}",
                parse_mode="html",
            )
            return

        temporary_file = selected_path != kernel_log_path
        try:
            branch, commit_sha, commit_url = await self._resolve_version_info()
            await target.edit(
                self.strings(
                    "logs_level_caption",
                    logs_title=CUSTOM_EMOJI["📝"],
                    logs=self.strings("logs"),
                    mcub=await self._mcub_handler(),
                    pen=CUSTOM_EMOJI["✏️"],
                    kernel_version=self.strings("kernel_version"),
                    version=self.kernel.VERSION,
                    commit_url=commit_url,
                    commit_sha=commit_sha,
                    satellite=CUSTOM_EMOJI["🛰"],
                    branch_label=self.strings("branch"),
                    branch=branch,
                    printer=CUSTOM_EMOJI["🖨"],
                    level=level.upper(),
                ),
                file=selected_path,
                parse_mode="html",
            )
        finally:
            if temporary_file:
                try:
                    os.unlink(selected_path)
                except OSError:
                    pass

    async def _mcub_handler(self) -> str:
        me = self.cache.get("tester:me")
        if me is None:
            me = await self.kernel.client.get_me()
            self.cache.set("tester:me", me, ttl=3600)
        return (
            '<tg-emoji emoji-id="5470015630302287916">🔮</tg-emoji><tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
            if me.premium
            else "MCUB"
        )

    def _resolve_emoji_value(self, raw: Any) -> str:
        if not isinstance(raw, str):
            return CUSTOM_EMOJI["✏️"]
        value = raw.strip()
        if not value:
            return CUSTOM_EMOJI["✏️"]
        return CUSTOM_EMOJI.get(value, value)

    def _resolve_ping_start_emoji(self) -> str:
        return self._resolve_emoji_value(self.config.get("start_emoji"))

    def _resolve_initial_ping_start_emoji(self) -> str:
        """Resolve the emoji for the first .ping edit before latency is known."""
        if not (self.config.get("start_emoji_dynamically_enabled") or False):
            return self._resolve_ping_start_emoji()

        emojis = self._parse_dynamic_emojis()
        if emojis is None:
            return self._resolve_ping_start_emoji()
        return self._resolve_emoji_value(emojis["low_emoji"])

    def _parse_dynamic_emojis(self) -> dict[str, str] | None:
        raw = self.config.get("start_emoji_dynamically")
        if not raw:
            return None
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        low_emoji = data.get("low_emoji")
        high_emoji = data.get("high_emoji")
        if not low_emoji or not high_emoji:
            return None
        return {"low_emoji": low_emoji, "high_emoji": high_emoji}

    def _resolve_dynamic_start_emoji(
        self, ping_time: float, avg_ping: float | None
    ) -> str:
        """Pick low_emoji/high_emoji vs the running average, falling back to start_emoji."""
        if not (self.config.get("start_emoji_dynamically_enabled") or False):
            return self._resolve_ping_start_emoji()

        emojis = self._parse_dynamic_emojis()
        if emojis is None:
            return self._resolve_ping_start_emoji()
        if avg_ping is None:
            return self._resolve_emoji_value(emojis["low_emoji"])

        chosen = emojis["high_emoji"] if ping_time > avg_ping else emojis["low_emoji"]
        return self._resolve_emoji_value(chosen)

    async def _measure_raw_ping(self) -> float | None:
        """Raw MTProto round-trip (PingRequest) - excludes Telegram's server-side edit/ACL
        processing, unlike the edit()-based {ping_time}."""
        try:
            ping_id = random.getrandbits(63)
            raw_start = time.perf_counter()
            await self.kernel.client(PingRequest(ping_id=ping_id))
            return round((time.perf_counter() - raw_start) * 1000, 2)
        except Exception as e:
            self.log.error(f"Raw ping error: {e}")
            return None

    def _get_cpu_ram(self) -> tuple[str, str]:
        cpu_usage = "N/A"
        ram_usage = "N/A"
        try:
            if _psutil is not None:
                cpu_usage = f"{_psutil.cpu_percent(interval=0.1)}%"
                ram = _psutil.virtual_memory()
                ram_usage = f"{ram.percent}%"
        except Exception:
            pass
        return cpu_usage, ram_usage

    @staticmethod
    def _format_ping_diff(current: float, previous: float | None) -> str:
        if previous is None:
            return "=0"
        diff = round(current - previous, 2)
        if diff > 0:
            return f"+{diff}"
        if diff < 0:
            return f"{diff}"
        return "=0"

    async def _update_ping_stats(self, ping_time: float) -> dict[str, Any]:
        """Persist ping history (self.db) and return prev/diff/avg/min/max for placeholders."""
        stats: dict[str, Any] = {}
        try:
            raw = await self.db.db_get(self.name, "ping_stats")
            if raw:
                stats = json.loads(raw)
        except Exception as e:
            self.log.error(f"Ping stats load error: {e}")
            stats = {}

        prev_ping = stats.get("last")
        diff = self._format_ping_diff(ping_time, prev_ping)

        previous_count = int(stats.get("count", 0))
        previous_total = float(stats.get("sum", 0.0))
        previous_avg = (
            round(previous_total / previous_count, 2) if previous_count > 0 else None
        )

        count = previous_count + 1
        total = previous_total + ping_time
        avg_ping = round(total / count, 2)
        min_ping = round(min(stats.get("min", ping_time), ping_time), 2)
        max_ping = round(max(stats.get("max", ping_time), ping_time), 2)

        new_stats = {
            "last": ping_time,
            "count": count,
            "sum": total,
            "min": min_ping,
            "max": max_ping,
        }
        try:
            await self.db.db_set(self.name, "ping_stats", json.dumps(new_stats))
        except Exception as e:
            self.log.error(f"Ping stats save error: {e}")

        return {
            "prev": prev_ping,
            "diff": diff,
            "previous_avg": previous_avg,
            "avg": avg_ping,
            "min": min_ping,
            "max": max_ping,
            "count": count,
        }

    @command("ping", doc_ru="пpoвepить зaдepжкy бoтa", doc_en="check bot latency")
    async def cmd_ping(self, event: Any) -> None:
        try:
            start_banner_url = self.config.get("start_banner_url")
            banner_url = self.config.get("banner_url")
            quote_media = self.config.get("quote_media") or False
            invert_media = self.config.get("invert_media") or False
            start_time = time.perf_counter()
            start_emoji = self._resolve_initial_ping_start_emoji()
            if quote_media and start_banner_url:
                msg = await event.edit(
                    start_emoji,
                    parse_mode="html",
                    file=InputMediaWebPage(start_banner_url, optional=True),
                    invert_media=invert_media,
                )
            elif start_banner_url:
                msg = await event.edit(
                    start_emoji,
                    parse_mode="html",
                    file=start_banner_url,
                    invert_media=invert_media,
                )
            else:
                msg = await event.edit(
                    start_emoji,
                    parse_mode="html",
                )
            ping_time = round((time.perf_counter() - start_time) * 1000, 2)

            raw_ping, ping_stats = await asyncio.gather(
                self._measure_raw_ping(),
                self._update_ping_stats(ping_time),
            )
            final_emoji = self._resolve_dynamic_start_emoji(
                ping_time, ping_stats["previous_avg"]
            )

            uptime_seconds = int(time.time() - self.kernel.start_time)
            hours = uptime_seconds // 3600
            minutes = (uptime_seconds % 3600) // 60
            seconds = uptime_seconds % 60

            if hours > 0:
                uptime = f"{hours}{self.strings('hours')} {minutes}{self.strings('minutes')} {seconds}{self.strings('seconds')}"
            elif minutes > 0:
                uptime = f"{minutes}{self.strings('minutes')} {seconds}{self.strings('seconds')}"
            else:
                uptime = f"{seconds}{self.strings('seconds')}"

            custom_text = self.config.get("custom_text") or ""
            if custom_text:
                response = await self._build_custom_text(
                    custom_text,
                    ping_time,
                    uptime,
                    ping_stats,
                    raw_ping,
                    final_emoji,
                )
            else:
                start_emoji = final_emoji
                raw_ping_display = (
                    f"{raw_ping} {self.strings('ms')}"
                    if raw_ping is not None
                    else "N/A"
                )
                response = f"""<blockquote>{start_emoji} <b>{self.strings("ping")}:</b> {ping_time} {self.strings("ms")} ({ping_stats["diff"]})</blockquote>
<blockquote>{start_emoji} <b>{self.strings("raw_ping")}:</b> {raw_ping_display}</blockquote>
<blockquote>{start_emoji} <b>{self.strings("uptime")}:</b> {uptime}</blockquote>"""

            if (
                banner_url
                and quote_media
                and banner_url.startswith(("http://", "https://"))
            ):
                try:
                    await msg.edit(
                        response,
                        file=InputMediaWebPage(banner_url, optional=True),
                        parse_mode="html",
                        invert_media=invert_media,
                    )
                    return
                except Exception as e:
                    self.log.error(f"Ping banner error: {e}")

            if banner_url:
                try:
                    await msg.edit(
                        response,
                        file=banner_url,
                        parse_mode="html",
                        invert_media=invert_media,
                    )
                except Exception:
                    try:
                        text, entities = await self.kernel.client._parse_message_text(
                            response, "html"
                        )
                        text, entities = self._add_link_preview(
                            text, entities, banner_url
                        )
                        await msg.edit(
                            text,
                            formatting_entities=entities,
                            parse_mode=None,
                        )
                    except Exception:
                        await msg.edit(response, parse_mode="html")
            else:
                await msg.edit(response, parse_mode="html")

        except Exception as e:
            await event.edit(
                self.strings("error_logs", snowflake=CUSTOM_EMOJI["❄️"]),
                parse_mode="html",
            )
            self.log.error(f"Ping error: {e}")
            await self.kernel.handle_error(e, message='Failed command "ping"')

    async def _build_custom_text(
        self,
        custom_text: str,
        ping_time: float,
        uptime: str,
        ping_stats: dict[str, Any],
        raw_ping: float | None,
        final_emoji: str,
    ) -> str:
        now = datetime.now()

        month_names_ru = [
            "Янвapя",
            "Фeвpaля",
            "Mapтa",
            "Aпpeля",
            "Maя",
            "Июня",
            "Июля",
            "Aвгycтa",
            "Ceнтябpя",
            "Oктябpя",
            "Hoябpя",
            "Дeкaбpя",
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
            "Пoнeдeльник",
            "Втopник",
            "Cpeдa",
            "Чeтвepг",
            "Пятницa",
            "Cyббoтa",
            "Вocкpeceньe",
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

        identity = self.cache.get("tester:identity")
        if identity is None:
            try:
                system_user = getpass.getuser()
                hostname = socket.gethostname()
            except Exception:
                system_user = hostname = "Unknown"
            identity = (system_user, hostname)
            self.cache.set("tester:identity", identity)
        else:
            system_user, hostname = identity

        cpu_usage, ram_usage = self._get_cpu_ram()

        branch, commit_sha, _commit_url = await self._resolve_version_info()
        me = self.cache.get("tester:me")
        if me is None:
            try:
                me = await self.kernel.client.get_me()
                self.cache.set("tester:me", me, ttl=3600)
            except Exception:
                me = None
        me_name = ""
        if me is not None:
            me_name = (
                getattr(me, "first_name", None)
                or getattr(me, "username", None)
                or str(getattr(me, "id", ""))
            )

        try:
            ms = self.strings("ms")
            prev_display = (
                f"{ping_stats['prev']} {ms}" if ping_stats["prev"] is not None else "—"
            )
            raw_ping_display = f"{raw_ping} {ms}" if raw_ping is not None else "N/A"
            timings = (
                f"{ping_time} {ms} ({ping_stats['diff']}) | "
                f"raw {raw_ping_display} | "
                f"avg {ping_stats['avg']} {ms} | "
                f"min {ping_stats['min']} {ms} | "
                f"max {ping_stats['max']} {ms}"
            )
            return await utils.resolve_placeholders(
                self.name,
                custom_text,
                data={
                    "ping_time": ping_time,
                    "ping": ping_time,
                    "raw_ping": raw_ping_display,
                    "dynamic_emoji": final_emoji,
                    "start_emoji": final_emoji,
                    "uptime": uptime,
                    "prev_ping": prev_display,
                    "ping_diff": ping_stats["diff"],
                    "avg_ping": ping_stats["avg"],
                    "min_ping": ping_stats["min"],
                    "max_ping": ping_stats["max"],
                    "ping_count": ping_stats["count"],
                    "timings": timings,
                    "system_user": system_user,
                    "user": system_user,
                    "me": me_name,
                    "hostname": hostname,
                    "cpu_usage": cpu_usage,
                    "cpu": cpu_usage,
                    "ram_usage": ram_usage,
                    "branch": branch,
                    "commit_sha": commit_sha,
                    "build": commit_sha,
                    "version": getattr(self.kernel, "VERSION", ""),
                    "platform": platform.platform(),
                    "os": platform.system() or sys.platform,
                    "kernel": platform.release(),
                    "upd": "",
                    "now_date": now_date,
                    "now_time": now_time,
                    "now_day": now_day,
                    "now_month": now_month,
                    "now_month_name": now_month_name,
                    "now_year": now_year,
                    "now_weekday": now_weekday,
                    "now_hour": now_hour,
                    "now_minute": now_minute,
                    "now_second": now_second,
                },
                strict=False,
            )
        except Exception as e:
            return self.strings("custom_text_error", error=str(e))

    def _add_link_preview(self, text: str, entities: list, link: str) -> tuple:
        if not text or not link:
            return text, entities

        zero_width = "\u2060"
        new_text = zero_width + text
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

    def _logs_level_prompt_text(self) -> str:
        return (
            f"{self.strings('logs_choose_level', paper=CUSTOM_EMOJI['📰'])}"
            + "\n"
            + f"{self.strings('logs_choose_desc')}"
        )

    def _logs_level_buttons(self) -> list:
        return [
            [
                self.Button.inline(
                    "DEBUG", self.cb_logs, data="level:debug", style="primary"
                ),
                self.Button.inline(
                    "INFO", self.cb_logs, data="level:info", style="primary"
                ),
            ],
            [
                self.Button.inline(
                    "WARNING", self.cb_logs, data="level:warning", style="primary"
                ),
                self.Button.inline(
                    "ERROR", self.cb_logs, data="level:error", style="primary"
                ),
            ],
            [
                self.Button.inline(
                    "CRITICAL", self.cb_logs, data="level:critical", style="primary"
                ),
                self.Button.inline(
                    "ALL", self.cb_logs, data="level:all", style="primary"
                ),
            ],
            [
                self.Button.inline(
                    "✖", self.cb_logs, data="tester_logs:cancel", style="danger"
                )
            ],
        ]

    @command("logs", doc_ru="пoкaзaть/oчиcтить лoги", doc_en="show/clear kernel logs")
    async def cmd_logs(self, event: Any) -> None:
        kernel_log_path = os.path.join(self.kernel.LOGS_DIR, "kernel.log")

        if not os.path.exists(kernel_log_path):
            await event.edit(
                self.strings("logs_not_found", file=CUSTOM_EMOJI["📁"]),
                parse_mode="html",
            )
            return

        size_kernel_log = os.path.getsize(kernel_log_path)
        if size_kernel_log == 0:
            await event.edit(
                f"{CUSTOM_EMOJI['🗳']} {self.strings('file_empty')}",
                parse_mode="html",
            )
            return

        args = self.args(event)
        if len(args) > 0:
            arg0 = args.get(0)
            normalized_arg = self._normalize_log_level(arg0)
            if arg0 == "clear":
                with open(kernel_log_path, "w"):
                    pass
                await event.edit(
                    f"{CUSTOM_EMOJI['🗳']} {self.strings('logs_clear')}",
                    parse_mode="html",
                )
                return

            tail = None
            args0 = args.get(0)
            if args0 == "tail":
                if not args.get(1):
                    tail = 20
                else:
                    try:
                        tail = int(args.get(1))
                    except ValueError:
                        tail = 20

                with open(kernel_log_path) as f:
                    lines = f.readlines()

                last_lines = lines[-tail:] if tail <= len(lines) else lines

                output = "".join(last_lines)
                if getattr(event, "piped", False):
                    event.pipe_output = str(output)
                    return
                await event.edit(f"<pre>{output}</pre>", parse_mode="html")
                return

            if not normalized_arg:
                await event.edit(
                    f"{CUSTOM_EMOJI['🧊']} {self.strings('logs_not_fount_args')}",
                    parse_mode="html",
                )
                return

            await event.edit(
                self.strings("logs_sending", printer=CUSTOM_EMOJI["🖨"]),
                parse_mode="html",
            )
            await self._send_logs(event, normalized_arg)
            return

        await self.inline(
            event.chat_id,
            self._logs_level_prompt_text(),
            reply_to=getattr(event.message, "reply_to", None),
            buttons=self._logs_level_buttons(),
        )

    @callback()
    async def cb_logs(self, call: Any, data: str | None = None) -> None:
        data_str = str(data) if data else ""

        if data_str == "cancel" or data_str == "tester_logs:cancel":
            await call.edit(
                self.strings("logs_send_cancelled", snowflake=CUSTOM_EMOJI["❄️"]),
                parse_mode="html",
            )
            return

        if data_str.startswith("confirm:"):
            level = data_str.rsplit(":", 1)[-1]
            if not level:
                await call.answer("Unknown level", alert=True)
                return
            await self._send_logs(call, level)
            return

        if data_str.startswith("back:") or data_str == "tester_logs:back":
            await call.edit(
                self._logs_level_prompt_text(),
                parse_mode="html",
                buttons=self._logs_level_buttons(),
            )
            return

        if not data_str.startswith("level:"):
            return

        level = data_str.rsplit(":", 1)[-1]
        if not level:
            await call.answer("Unknown level", alert=True)
            return

        if level in {"debug", "all"}:
            await call.edit(
                self.strings(
                    "logs_level_warning",
                    snowflake=CUSTOM_EMOJI["❄️"],
                    level=level.upper(),
                ),
                parse_mode="html",
                buttons=[
                    [
                        self.Button.inline(
                            "✅ Send" if self.get_lang() == "en" else "✅ Oтпpaвить",
                            self.cb_logs,
                            data=f"confirm:{level}",
                            style="success",
                        ),
                        self.Button.inline(
                            "↩", self.cb_logs, data="tester_logs:back", style="primary"
                        ),
                    ],
                    [
                        self.Button.inline(
                            "✖", self.cb_logs, data="cancel", style="danger"
                        )
                    ],
                ],
            )
            return

        await self._send_logs(call, level)

    @command("freezing", doc_ru="зaмopoзить юзepбoт", doc_en="freeze userbot")
    async def cmd_freezing(self, event: Any) -> None:
        args_raw = self.args_raw(event).strip()
        if not args_raw:
            await event.edit(
                self.strings(
                    "freezing_usage",
                    speech=CUSTOM_EMOJI["🗯"],
                    prefix=self.get_prefix(),
                ),
                parse_mode="html",
            )
            return

        try:
            seconds = int(args_raw)
            if seconds <= 0 or seconds > 60:
                await event.edit(
                    self.strings("freezing_range", speech=CUSTOM_EMOJI["🗯"]),
                    parse_mode="html",
                )
                return
        except ValueError:
            await event.edit(
                self.strings("freezing_number", speech=CUSTOM_EMOJI["🗯"]),
                parse_mode="html",
            )
            return

        await event.edit(
            self.strings(
                "freezing_start", snowflake=CUSTOM_EMOJI["🧊"], seconds=seconds
            ),
            parse_mode="html",
        )

        client = self.kernel.client
        was_connected = client.is_connected()
        if was_connected:
            client.disconnect()
            await asyncio.sleep(0.5)

        await asyncio.sleep(seconds)

        if was_connected:
            await client.connect()
        await event.edit(
            self.strings("freezing_done", check=CUSTOM_EMOJI["☑️"], seconds=seconds),
            parse_mode="html",
        )

    def _get_handler_location(self, handler) -> str:
        try:
            import inspect

            f = inspect.unwrap(handler)
            loc = inspect.getfile(f)
            _, line = inspect.getsourcelines(f)
            return f"{loc}:{line}"
        except Exception:
            return "?"

    def _format_uptime(self, seconds: float) -> str:
        days, rem = divmod(int(seconds), 86400)
        hours, rem = divmod(rem, 3600)
        mins, secs = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        parts.append(f"{hours}h")
        parts.append(f"{mins}m")
        parts.append(f"{secs}s")
        return " ".join(parts)

    async def _collect_system_info(self) -> list[str]:
        k = self.kernel
        lines: list[str] = []
        lines.append("[system]")
        lines.append(f"- version    : {k.VERSION}")
        lines.append(f"- kernel     : {type(k).__name__}")
        lines.append(
            f"- uptime     : {self._format_uptime(time.time() - k.start_time)}"
        )
        loaded = len(k.loaded_modules)
        system = len(k.system_modules)
        lines.append(f"- modules    : {loaded} user + {system} system")
        try:
            branch = await k.version_manager.detect_branch()
            commit = await k.version_manager.get_commit_sha(short=True)
            lines.append(f"- branch     : {branch}")
            lines.append(f"- commit     : {commit}")
        except Exception:
            pass
        try:
            py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            lines.append(f"- python     : {py_ver}")
        except Exception:
            pass
        if _psutil is not None:
            try:
                mem = _psutil.virtual_memory()
                lines.append(
                    f"- memory     : {mem.used // 1024 // 1024}MB / {mem.total // 1024 // 1024}MB"
                )
            except Exception:
                pass
        return lines

    async def _collect_command_info(
        self, cmd_name: str, handler, full_cmd: str
    ) -> list[str]:
        k = self.kernel
        lines: list[str] = []
        lines.append("[command]")
        lines.append(f"- name       : {full_cmd}")
        module_name = k.command_owners.get(cmd_name, "?")
        lines.append(f"- module     : {module_name}")
        is_system = module_name in k.system_modules
        lines.append(f"- type       : {'system' if is_system else 'user'}")
        loc = self._get_handler_location(handler)
        lines.append(f"- handler    : {loc}")
        alias_target = None
        for alias, target in k.aliases.items():
            if target == cmd_name:
                alias_target = alias
                break
        if alias_target:
            lines.append(f"- alias      : {alias_target}")
        return lines

    async def _collect_event_context(self, event) -> list[str]:
        lines: list[str] = []
        lines.append("[event]")
        try:
            ev_type = type(event).__name__
            lines.append(f"- type       : {ev_type}")
        except Exception:
            pass
        try:
            uid = getattr(event, "sender_id", None)
            if uid is not None:
                lines.append(f"- user_id    : {uid}")
                is_owner = uid == getattr(self.kernel, "owner", None)
                is_admin = self.kernel.is_admin(uid)
                tags = []
                if is_owner:
                    tags.append("owner")
                if is_admin:
                    tags.append("admin")
                if tags:
                    lines.append(f"- access     : {', '.join(tags)}")
        except Exception:
            pass
        try:
            chat_id = getattr(event, "chat_id", None)
            if chat_id is not None:
                lines.append(f"- chat_id    : {chat_id}")
        except Exception:
            pass
        try:
            mid = getattr(event, "id", None)
            if mid is not None:
                lines.append(f"- msg_id     : {mid}")
        except Exception:
            pass
        try:
            text = getattr(event, "text", "")
            if text:
                display = text.replace("\n", "\\n")
                lines.append(f"- text       : {display[:200]}")
        except Exception:
            pass
        try:
            pipe = getattr(event, "pipe_input", None)
            if pipe:
                display = str(pipe)[:100]
                lines.append(f"- pipe       : {display}")
        except Exception:
            pass
        return lines

    async def _collect_db_cache_info(self, module_name: str) -> list[str]:
        lines: list[str] = []
        lines.append("[db_cache]")
        try:
            db = getattr(self.kernel, "db_manager", None)
            if db is not None:
                cache = getattr(db, "_get_cache", {})
                total = len(cache)
                if total:
                    lines.append(f"- entries    : {total}")
                    mc_key = f"module_configs:{module_name}"
                    if mc_key in cache:
                        lines.append(
                            f"- {module_name}_config : {'present' if cache[mc_key] is not None else 'cached empty'}"
                        )
                    else:
                        lines.append(f"- {module_name}_config : not cached")
                else:
                    lines.append("- entries    : 0 (disabled)")
        except Exception:
            pass
        return lines

    async def _collect_permissions(self, event, module_name: str) -> list[str]:
        lines: list[str] = []
        lines.append("[permissions]")
        try:
            uid = getattr(event, "sender_id", None)
            if uid is not None:
                is_owner = uid == getattr(self.kernel, "owner", None)
                is_admin = self.kernel.is_admin(uid)
                lines.append(f"- is_owner   : {is_owner}")
                lines.append(f"- is_admin   : {is_admin}")
        except Exception:
            pass
        try:
            if hasattr(self.kernel, "trusted"):
                from core.lib.base.permissions import check_trust

                trusted = await check_trust(self.kernel, event)
                lines.append(f"- trusted    : {trusted}")
        except Exception:
            pass
        return lines

    @command(
        "teaser",
        doc_ru="тecтиpoвaть кoмaндy c лoгиpoвaниeм",
        doc_en="test a command with logging",
    )
    async def cmd_teaser(self, event) -> None:
        """(cmd) - execute cmd with full logging"""
        args = self.args(event)
        if not args:
            await event.edit(
                self.strings("teaser_no_cmd", prefix=self.get_prefix()),
                parse_mode="html",
            )
            return

        cmd_name = args.get(0)
        prefix = self.get_prefix()
        cmd_args_raw = event.text[len(prefix) + len("teaser ") :]
        full_cmd = cmd_args_raw
        fake_text = prefix + cmd_args_raw

        handler = self.kernel.command_handlers.get(cmd_name)
        if not handler:
            await event.edit(
                self.strings("teaser_cmd_not_found", cmd=cmd_name), parse_mode="html"
            )
            return

        owner = self.kernel.command_owners.get(cmd_name, "")

        kernel_log_path = os.path.join(self.kernel.LOGS_DIR, "kernel.log")
        initial_size = 0
        if os.path.exists(kernel_log_path):
            initial_size = os.path.getsize(kernel_log_path)

        await event.edit(
            self.strings("teaser_recording", cmd=full_cmd), parse_mode="html"
        )

        fake = _FakeEventProxy(event, fake_text=fake_text)
        self.log.info(f"Teaser: executing {full_cmd} with FakeEvent")

        t_start = time.perf_counter()
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(fake)
            else:
                handler(fake)
        except Exception as e:
            self.log.error(f"Teaser: command {full_cmd} error: {e}")
        t_delta = time.perf_counter() - t_start

        sections = await asyncio.gather(
            self._collect_system_info(),
            self._collect_command_info(cmd_name, handler, full_cmd),
            self._collect_event_context(event),
            self._collect_permissions(event, owner),
            self._collect_db_cache_info(owner),
        )

        report_lines: list[str] = []

        for sec_lines in sections:
            if sec_lines:
                report_lines.extend(sec_lines)
                report_lines.append("")

        report_lines.append("[timing]")
        report_lines.append(f"- exec       : {t_delta * 1000:.1f}ms")
        report_lines.append("")

        event_log = fake.get_log()
        report_lines.append("[event_calls]")
        if event_log:
            for entry in event_log:
                report_lines.append(f"- {entry}")
        else:
            report_lines.append("- (none)")
        report_lines.append("")

        new_log_entries = ""
        if os.path.exists(kernel_log_path):
            with open(kernel_log_path, encoding="utf-8", errors="ignore") as f:
                f.seek(initial_size)
                new_log_entries = f.read().strip()

        report_lines.append("[kernel_log]")
        if new_log_entries:
            for line in new_log_entries.split("\n"):
                report_lines.append(f"- {line}")
        else:
            report_lines.append("- (no new entries)")
        report_lines.append("")

        report = "\n".join(report_lines)

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        )
        try:
            tmp.write(report)
            tmp.close()
            try:
                await event.edit(
                    self.strings("teaser_done", cmd=full_cmd),
                    file=tmp.name,
                    parse_mode="html",
                )
            except Exception:
                await event.respond(
                    self.strings("teaser_done", cmd=full_cmd),
                    file=tmp.name,
                    parse_mode="html",
                )
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
