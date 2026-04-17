# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import getpass
import os
import platform
import re
import socket
import subprocess
import tempfile
import time
from datetime import datetime
from typing import Any

try:
    import psutil as _psutil
except ImportError:
    _psutil = None

from telethon import functions
from telethon.tl.types import InputMediaWebPage

from core.lib.loader.module_base import ModuleBase, command, callback
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
        "ru": "Тестер модуль (пинг, логи, заморозка)",
        "en": "Tester module (ping, logs, freezing)",
    }

    config = ModuleConfig(
        ConfigValue(
            "quote_media",
            False,
            description="Send media with quote in .ping",
            validator=Boolean(default=False),
        ),
        ConfigValue(
            "invert_media",
            False,
            description="Invert media colors",
            validator=Boolean(default=False),
        ),
        ConfigValue(
            "banner_url",
            "",
            description="Banner image URL for inline preview",
            validator=String(default=""),
        ),
        ConfigValue(
            "custom_text",
            "",
            description=(
                "Custom text for .ping. Available placeholders:\n"
                "{ping_time}, {uptime}, {system_user}, {hostname},\n"
                "{cpu_usage}, {ram_usage}, {branch}, {commit_sha},\n"
                "{now_date}, {now_time}, {now_day}, {now_month},\n"
                "{now_month_name}, {now_year}, {now_weekday},\n"
                "{now_hour}, {now_minute}, {now_second}"
            ),
            validator=String(default=""),
        ),
        ConfigValue(
            "start_emoji",
            "✏️",
            description="Start emoji for .ping",
            validator=String(default="✏️"),
        ),
    )

    strings: dict[str, dict[str, str]] = {
        "en": {
            "error_logs": "{snowflake} <b>Error, see logs</b>",
            "logs_not_found": "{file} File kernel.log not found",
            "logs_sending": "{printer} Sending kernel logs",
            "freezing_usage": "{speech} Usage: {prefix}freezing [seconds]",
            "freezing_range": "{speech} Specify from 1 to 60 seconds",
            "freezing_number": "{speech} Specify number of seconds",
            "freezing_start": "{snowflake} Freezing for {seconds} seconds...",
            "freezing_done": "{check} Unfrozen after {seconds} seconds",
            "custom_text_error": "<b>Error in custom text format:</b> {error}",
            "logs": "Logs",
            "kernel_version": "Kernel Version",
            "ping": "ping",
            "uptime": "uptime",
            "ms": "ms",
            "hours": "h",
            "minutes": "m",
            "seconds": "s",
            "branch": "Branch",
            "logs_not_fount_args": "<b>Available arguments:</b> <code>clear</code>, <code>debug</code>, <code>info</code>, <code>warning</code>, <code>error</code>, <code>critical</code>, <code>all</code>",
            "logs_clear": "<b>Cleared kernel logs</b>",
            "file_empty": "<b>Is logs empty</b>",
            "logs_level_invalid": "<b>Available levels:</b> <code>debug</code>, <code>info</code>, <code>warning</code>, <code>error</code>, <code>critical</code>, <code>all</code>",
            "logs_choose_level": "{paper} <b>Choose log level</b>",
            "logs_choose_desc": "Send only selected records from <code>kernel.log</code>.",
            "logs_level_warning": "{snowflake} <b>Warning</b>\n<blockquote>Logs with level <code>{level}</code> may contain personal information, tokens, chat IDs, message text, and other sensitive data.</blockquote>\n<b>Send anyway?</b>",
            "logs_send_cancelled": "{snowflake} <b>Log sending cancelled</b>",
            "logs_level_caption": '{logs_title} <b>{logs}</b> {mcub}\n<blockquote>{pen} <b>{kernel_version}</b> {version}#<a href="{commit_url}">{commit_sha}</a>\n{satellite} <b>{branch_label}:</b> {branch}\n{printer} <b>Level:</b> <code>{level}</code></blockquote>',
        },
        "ru": {
            "error_logs": "{snowflake} <b>Ошибка, смотри логи</b>",
            "logs_not_found": "{file} Файл kernel.log не найден",
            "logs_sending": "{printer} Отправляю логи kernel",
            "freezing_usage": "{speech} Использование: {prefix}freezing [секунды]",
            "freezing_range": "{speech} Укажите от 1 до 60 секунд",
            "freezing_number": "{speech} Укажите число секунд",
            "freezing_start": "{snowflake} Замораживаю на {seconds} секунд...",
            "freezing_done": "{check} Разморожено после {seconds} секунд",
            "custom_text_error": "<b>Ошибка в форматировании кастомного текста:</b> {error}",
            "logs": "Логи",
            "kernel_version": "Версия ядра",
            "ping": "пинг",
            "uptime": "время работы",
            "ms": "мс",
            "hours": "ч",
            "minutes": "м",
            "seconds": "с",
            "branch": "Ветка",
            "logs_not_fount_args": "<b>Доступные аргументы: </b><code>clear</code>, <code>debug</code>, <code>info</code>, <code>warning</code>, <code>error</code>, <code>critical</code>, <code>all</code>",
            "logs_clear": "<b>Логи очишены</b>",
            "file_empty": "<b>Логи пустые</b>",
            "logs_level_invalid": "<b>Доступные уровни:</b> <code>debug</code>, <code>info</code>, <code>warning</code>, <code>error</code>, <code>critical</code>, <code>all</code>",
            "logs_choose_level": "{paper} <b>Выбери уровень логов</b>",
            "logs_choose_desc": "Отправлю только записи выбранного уровня из <code>kernel.log</code>.",
            "logs_level_warning": "{snowflake} <b>Предупреждение</b>\n<blockquote>Логи уровня <code>{level}</code> могут содержать личную информацию, токены, chat id, текст сообщений и другие чувствительные данные.</blockquote>\n<b>Все равно отправить?</b>",
            "logs_send_cancelled": "{snowflake} <b>Отправка логов отменена</b>",
            "logs_level_caption": '{logs_title} <b>{logs}</b> {mcub}\n<blockquote>{pen} <b>{kernel_version}</b> {version}#<a href="{commit_url}">{commit_sha}</a>\n{satellite} <b>{branch_label}:</b> {branch}\n{printer} <b>Уровень:</b> <code>{level}</code></blockquote>',
        },
    }

    log_level_pattern = re.compile(r"^\d{4}-\d{2}-\d{2} .* \[([A-Z]+)\] ")
    log_level_labels = ["debug", "info", "warning", "error", "critical", "all"]

    def _get_branch(self) -> str:
        return _detect_branch_sync()

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
        if version_info is None:
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

    def _resolve_ping_start_emoji(self) -> str:
        raw = self.config.get("start_emoji") or "✏️"
        if not isinstance(raw, str):
            return "✏️"
        value = raw.strip()
        if not value:
            return "✏️"
        return CUSTOM_EMOJI.get(value, value)

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

    @command("ping", doc_ru="проверить задержку бота", doc_en="check bot latency")
    async def cmd_ping(self, event: Any) -> None:
        try:
            start_time = time.time()
            msg = await event.edit(
                self._resolve_ping_start_emoji(),
                parse_mode="html",
            )
            ping_time = round((time.time() - start_time) * 1000, 2)

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
                )
            else:
                start_emoji = self._resolve_ping_start_emoji()
                response = f"""<blockquote>{start_emoji} <b>{self.strings("ping")}:</b> {ping_time} {self.strings("ms")}</blockquote>
<blockquote>{start_emoji} <b>{self.strings("uptime")}:</b> {uptime}</blockquote>"""

            banner_url = self.config.get("banner_url")
            quote_media = self.config.get("quote_media") or False
            invert_media = self.config.get("invert_media") or False

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
                    await msg.edit(response, file=banner_url, parse_mode="html")
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

    async def _build_custom_text(
        self,
        custom_text: str,
        ping_time: float,
        uptime: str,
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

        version_info = self.cache.get("tester:version_info")
        if version_info:
            branch, commit_sha = version_info[0], version_info[1]
        else:
            branch = await self.kernel.version_manager.detect_branch()
            commit_sha = await self.kernel.version_manager.get_commit_sha()
            self.cache.set("tester:version_info", (branch, commit_sha), ttl=600)

        known = [
            "ping_time",
            "uptime",
            "system_user",
            "hostname",
            "cpu_usage",
            "ram_usage",
            "branch",
            "commit_sha",
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
                ping_time=ping_time,
                uptime=uptime,
                system_user=system_user,
                hostname=hostname,
                cpu_usage=cpu_usage,
                ram_usage=ram_usage,
                branch=branch,
                commit_sha=commit_sha,
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

    def _add_link_preview(self, text: str, entities: list, link: str) -> tuple:
        from copy import copy

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

        from telethon.tl.types import MessageEntityTextUrl

        link_entity = MessageEntityTextUrl(offset=0, length=1, url=link)
        new_entities.append(link_entity)
        return new_text, new_entities

    @command("logs", doc_ru="показать/очистить логи", doc_en="show/clear kernel logs")
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
            f"{self.strings('logs_choose_level', paper=CUSTOM_EMOJI['📰'])}\n{self.strings('logs_choose_desc')}",
            buttons=[
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
            ],
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
                f"{self.strings('logs_choose_level', paper=CUSTOM_EMOJI['📰'])}\n{self.strings('logs_choose_desc')}",
                parse_mode="html",
                buttons=[
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
                            "WARNING",
                            self.cb_logs,
                            data="level:warning",
                            style="primary",
                        ),
                        self.Button.inline(
                            "ERROR", self.cb_logs, data="level:error", style="primary"
                        ),
                    ],
                    [
                        self.Button.inline(
                            "CRITICAL",
                            self.cb_logs,
                            data="level:critical",
                            style="primary",
                        ),
                        self.Button.inline(
                            "ALL", self.cb_logs, data="level:all", style="primary"
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
                            "✅ Send" if self.get_lang() == "en" else "✅ Отправить",
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

    @command("freezing", doc_ru="заморозить юзербот", doc_en="freeze userbot")
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
