import asyncio
import os
import time
import getpass
import socket
import subprocess
import tempfile
import re
from datetime import datetime

try:
    import psutil as _psutil
except ImportError:
    _psutil = None
from telethon.tl.types import InputMediaWebPage
from telethon import functions
from telethon import Button
from copy import copy
from utils import get_args
from core.lib.loader.module_config import (
    ModuleConfig,
    ConfigValue,
    Boolean,
    String,
    Choice,
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


def register(kernel):
    client = kernel.client
    branch = _detect_branch_sync()

    # Module config with ModuleConfig
    default_config = {
        "quote_media": False,
        "banner_url": f"https://raw.githubusercontent.com/hairpin01/MCUB-fork/refs/heads/{branch}/img/ping.png",
        "invert_media": False,
        "custom_text": "",
        "start_emoji": "✏️",
    }
    config = ModuleConfig(
        ConfigValue(
            "quote_media",
            False,
            description="Send media with quote in .ping",
            validator=Boolean(default=False),
        ),
        ConfigValue(
            "banner_url",
            f"https://raw.githubusercontent.com/hairpin01/MCUB-fork/refs/heads/{branch}/img/ping.png",
            description="Banner URL for .ping command",
            validator=String(default=""),
        ),
        ConfigValue(
            "invert_media",
            False,
            description="Invert media colors",
            validator=Boolean(default=False),
        ),
        ConfigValue(
            "custom_text",
            "",
            description="Custom text for .ping. Placeholders: {emoji} - start emoji, {ms} - ping ms, {emoji2} - second emoji, {uptime} - uptime, {hours}, {minutes}, {seconds}, {system_user}, {hostname}, {cpu}, {ram}, {ping_time}",
            validator=String(default=""),
        ),
        ConfigValue(
            "start_emoji",
            "✏️",
            description="Emoji at the start of .ping message (supports premium emojis)",
            validator=String(default="✏️"),
        ),
    )

    def get_config():
        """Get live config from kernel or fall back to local config."""
        live_cfg = getattr(kernel, "_live_module_configs", {}).get(__name__)
        if live_cfg:
            return live_cfg
        return config

    @kernel.register.on_load()
    async def load_module_config(k):
        config_dict = await k.get_module_config(__name__, default_config)
        config.from_dict(config_dict)
        if config_dict:
            await k.save_module_config(__name__, config.to_dict())
        k.store_module_config_schema(__name__, config)

    language = kernel.config.get("language", "en")
    log_level_pattern = re.compile(r"^\d{4}-\d{2}-\d{2} .* \[([A-Z]+)\] ")
    log_level_labels = ["debug", "info", "warning", "error", "critical", "all"]

    # Локализованные строки
    strings = {
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
            "quote_mode_error": "Error in quote mode",
            "send_banner_error": "Error sending banner",
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
            "quote_mode_error": "Ошибка в режиме цитирования",
            "send_banner_error": "Ошибка отправки баннера",
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

    # Получаем строки для текущего языка
    lang_strings = strings.get(language, strings["en"])

    def t(key, **kwargs):
        """Возвращает локализованную строку с подстановкой значений"""
        if key not in lang_strings:
            return key
        return lang_strings[key].format(**kwargs)

    def _normalize_log_level(value):
        if not value:
            return None
        value = value.strip().lower()
        return value if value in log_level_labels else None

    def _build_filtered_log(level, kernel_log_path):
        if level == "all":
            return kernel_log_path

        temp_path = os.path.join(tempfile.gettempdir(), f"kernel.{level}.log")
        temp = open(temp_path, "w", encoding="utf-8")
        keep_block = False
        wrote = False
        try:
            with open(kernel_log_path, "r", encoding="utf-8", errors="ignore") as src:
                for line in src:
                    match = log_level_pattern.match(line)
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

    async def _resolve_version_info():
        _version_info = kernel.cache.get("tester:version_info")
        if _version_info is None:
            branch = await kernel.version_manager.detect_branch()
            commit_sha = await kernel.version_manager.get_commit_sha()
            commit_url = await kernel.version_manager.get_github_commit_url()
            kernel.cache.set(
                "tester:version_info", (branch, commit_sha, commit_url), ttl=600
            )
        else:
            branch, commit_sha, commit_url = _version_info
        return branch, commit_sha, commit_url

    async def _send_logs(target, level):
        kernel_log_path = os.path.join(kernel.LOGS_DIR, "kernel.log")
        if not os.path.exists(kernel_log_path):
            await target.edit(
                t("logs_not_found", file=CUSTOM_EMOJI["📁"]), parse_mode="html"
            )
            return

        if os.path.getsize(kernel_log_path) == 0:
            await target.edit(
                f"{CUSTOM_EMOJI['🗳']} {t('file_empty')}", parse_mode="html"
            )
            return

        selected_path = _build_filtered_log(level, kernel_log_path)
        if selected_path is None:
            await target.edit(
                f"{CUSTOM_EMOJI['🗳']} {t('file_empty')}", parse_mode="html"
            )
            return

        temporary_file = selected_path != kernel_log_path
        try:
            branch, commit_sha, commit_url = await _resolve_version_info()
            await target.edit(
                t(
                    "logs_level_caption",
                    logs_title=CUSTOM_EMOJI["📝"],
                    logs=t("logs"),
                    mcub=await mcub_handler(),
                    pen=CUSTOM_EMOJI["✏️"],
                    kernel_version=t("kernel_version"),
                    version=kernel.VERSION,
                    commit_url=commit_url,
                    commit_sha=commit_sha,
                    satellite=CUSTOM_EMOJI["🛰"],
                    branch_label=t("branch"),
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

    def resolve_ping_start_emoji() -> str:
        """Resolve configurable start emoji for .ping with sensible fallbacks."""
        cfg = get_config()
        raw = cfg.get("start_emoji") or "✏️"
        if not isinstance(raw, str):
            return "✏️"
        value = raw.strip()
        if not value:
            return "✏️"
        return CUSTOM_EMOJI.get(value, value)

    def get_cpu_ram():
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

    async def mcub_handler():
        me = kernel.cache.get("tester:me")
        if me is None:
            me = await kernel.client.get_me()
            kernel.cache.set("tester:me", me, ttl=3600)
        mcub_emoji = (
            '<tg-emoji emoji-id="5470015630302287916">🔮</tg-emoji><tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
            if me.premium
            else "MCUB"
        )
        return mcub_emoji

    @kernel.register.command("ping")
    async def ping_handler(event):
        """ping mcub"""
        try:
            start_time = time.time()
            msg = await event.edit(resolve_ping_start_emoji(), parse_mode="html")
            end_time = time.time()
            ping_time = round((end_time - start_time) * 1000, 2)

            uptime_seconds = int(time.time() - kernel.start_time)
            hours = uptime_seconds // 3600
            minutes = (uptime_seconds % 3600) // 60
            seconds = uptime_seconds % 60

            if hours > 0:
                uptime = f"{hours}{lang_strings['hours']} {minutes}{lang_strings['minutes']} {seconds}{lang_strings['seconds']}"
            elif minutes > 0:
                uptime = f"{minutes}{lang_strings['minutes']} {seconds}{lang_strings['seconds']}"
            else:
                uptime = f"{seconds}{lang_strings['seconds']}"

            cfg = get_config()
            custom_text = cfg.get("custom_text") or ""
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

                # system_user / hostname
                if uses("system_user", "hostname"):
                    _identity = kernel.cache.get("tester:identity")
                    if _identity is None:
                        try:
                            system_user = getpass.getuser()
                            hostname = socket.gethostname()
                        except Exception:
                            system_user = hostname = "Unknown"
                        kernel.cache.set("tester:identity", (system_user, hostname))
                    else:
                        system_user, hostname = _identity
                else:
                    system_user = hostname = ""

                # kernel_version / core_name
                kernel_version = kernel.VERSION if uses("kernel_version") else ""
                core_name = (
                    getattr(kernel, "CORE_NAME", "standard")
                    if uses("core_name")
                    else ""
                )

                # cpu / ram
                if uses("cpu_usage", "ram_usage"):
                    cpu_usage, ram_usage = get_cpu_ram()
                else:
                    cpu_usage = ram_usage = ""

                # branch / commit_sha
                if uses("branch", "commit_sha"):
                    _version_info = kernel.cache.get("tester:version_info")
                    if _version_info is None:
                        branch = await kernel.version_manager.detect_branch()
                        commit_sha = await kernel.version_manager.get_commit_sha()
                        kernel.cache.set(
                            "tester:version_info", (branch, commit_sha), ttl=600
                        )
                    else:
                        branch, commit_sha = _version_info
                else:
                    branch = commit_sha = ""

                try:
                    _known = [
                        "ping_time",
                        "uptime",
                        "system_user",
                        "hostname",
                        "kernel_version",
                        "core_name",
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
                    _safe = custom_text.replace("{", "{{").replace("}", "}}")
                    for _k in _known:
                        _safe = _safe.replace("{{" + _k + "}}", "{" + _k + "}")
                    response = _safe.format(
                        ping_time=ping_time,
                        uptime=uptime,
                        system_user=system_user,
                        hostname=hostname,
                        kernel_version=kernel_version,
                        core_name=core_name,
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
                    await kernel.handle_error(
                        e, source="ping:custom_text_format", event=event
                    )
                    response = t("custom_text_error", error=str(e))
            else:
                cfg = get_config()
                start_emoji = resolve_ping_start_emoji()
                response = f"""<blockquote>{start_emoji} <b>{lang_strings["ping"]}:</b> {ping_time} {lang_strings["ms"]}</blockquote>
<blockquote>{start_emoji} <b>{lang_strings["uptime"]}:</b> {uptime}</blockquote>"""

            cfg = get_config()
            banner_url = cfg.get("banner_url")
            quote_media = cfg.get("quote_media") or False
            invert_media = cfg.get("invert_media") or False

            if (
                quote_media
                and banner_url
                and banner_url.startswith(("http://", "https://"))
            ):
                try:
                    try:
                        await msg.edit(
                            response,
                            file=InputMediaWebPage(banner_url, optional=True),
                            parse_mode="html",
                            link_preview=True,
                            invert_media=invert_media,
                        )
                        return
                    except TypeError as e:
                        kernel.logger.error("error: ", e)
                        await client(
                            functions.messages.EditMessageRequest(
                                peer=await event.get_input_chat(),
                                id=msg.id,
                                message=response,
                                parse_mode="html",
                                invert_media=invert_media,
                                no_webpage=False,
                            )
                        )
                        return

                except Exception as e:
                    await kernel.handle_error(e, source="ping:quote_mode", event=event)

            if banner_url:
                banner_sent = False

                chat = await event.get_chat()
                reply_to = None
                if hasattr(chat, "forum") and chat.forum and event.message.reply_to:
                    reply_to = (
                        event.message.reply_to.reply_to_top_id
                        or event.message.reply_to.reply_to_msg_id
                    )

                if os.path.exists(banner_url):
                    try:
                        await msg.edit(response, file=banner_url, parse_mode="html")
                        banner_sent = True
                    except Exception:
                        pass
                else:
                    try:
                        await msg.edit(response, file=banner_url, parse_mode="html")
                        banner_sent = True
                    except Exception:
                        pass

                if not banner_sent:
                    try:
                        text, entities = await client._parse_message_text(
                            response, "html"
                        )
                        text, entities = add_link_preview(text, entities, banner_url)
                        await msg.edit(
                            text, formatting_entities=entities, parse_mode=None
                        )
                    except Exception:
                        await msg.edit(response, parse_mode="html")
            else:
                await msg.edit(response, parse_mode="html")

        except Exception as e:
            await event.edit(
                t("error_logs", snowflake=CUSTOM_EMOJI["❄️"]), parse_mode="html"
            )
            await kernel.handle_error(e, source="ping", event=event)

    @kernel.register.command("logs")
    async def logs_handler(event):
        """[clear] - cleared logs kernel"""
        try:
            kernel_log_path = os.path.join(kernel.LOGS_DIR, "kernel.log")

            if not os.path.exists(kernel_log_path):
                await event.edit(
                    t("logs_not_found", file=CUSTOM_EMOJI["📁"]), parse_mode="html"
                )
                return
            size_kernel_log = os.path.getsize(kernel_log_path)

            if size_kernel_log == 0:
                await event.edit(
                    f"{CUSTOM_EMOJI['🗳']} {t('file_empty')}", parse_mode="html"
                )
                return

            args = get_args(event)
            if args:
                normalized_arg = _normalize_log_level(args[0])
                if args[0] == "clear":
                    if size_kernel_log == 0:
                        await event.edit(f"{CUSTOM_EMOJI['🗳']} {t('file_empty')}")
                        return

                    with open(kernel_log_path, "w") as f:
                        pass

                    await event.edit(
                        f"{CUSTOM_EMOJI['🗳']} {t('logs_clear')}", parse_mode="html"
                    )
                    return
                if not normalized_arg:
                    await event.edit(
                        f"{CUSTOM_EMOJI['🧊']} {t('logs_not_fount_args')}",
                        parse_mode="html",
                    )
                    return

                await event.edit(
                    t("logs_sending", printer=CUSTOM_EMOJI["🖨"]), parse_mode="html"
                )
                await _send_logs(event, normalized_arg)
                return

            success, _ = await kernel.inline_form(
                event.chat_id,
                f"{t('logs_choose_level', paper=CUSTOM_EMOJI['📰'])}\n{t('logs_choose_desc')}",
                buttons=[
                    [
                        Button.inline(
                            "DEBUG", b"tester_logs:level:debug", style="primary"
                        ),
                        Button.inline(
                            "INFO", b"tester_logs:level:info", style="primary"
                        ),
                    ],
                    [
                        Button.inline(
                            "WARNING", b"tester_logs:level:warning", style="primary"
                        ),
                        Button.inline(
                            "ERROR", b"tester_logs:level:error", style="primary"
                        ),
                    ],
                    [
                        Button.inline(
                            "CRITICAL", b"tester_logs:level:critical", style="primary"
                        ),
                        Button.inline("ALL", b"tester_logs:level:all", style="primary"),
                    ],
                    [Button.inline("✖", b"tester_logs:cancel", style="danger")],
                ],
            )
            if success:
                await event.delete()

        except Exception as e:
            await event.edit(
                t("error_logs", snowflake=CUSTOM_EMOJI["❄️"]), parse_mode="html"
            )
            await kernel.handle_error(e, source="logs", event=event)

    async def tester_logs_callback(event):
        try:
            data = (
                event.data.decode()
                if isinstance(event.data, bytes)
                else str(event.data)
            )
            if data == "tester_logs:cancel":
                await event.edit(
                    t("logs_send_cancelled", snowflake=CUSTOM_EMOJI["❄️"]),
                    parse_mode="html",
                    buttons=None,
                )
                return

            if data.startswith("tester_logs:confirm:"):
                level = _normalize_log_level(data.rsplit(":", 1)[-1])
                if not level:
                    await event.answer("Unknown level", alert=True)
                    return
                await _send_logs(event, level)
                return

            if not data.startswith("tester_logs:level:"):
                return

            level = _normalize_log_level(data.rsplit(":", 1)[-1])
            if not level:
                await event.answer("Unknown level", alert=True)
                return

            if level in {"debug", "all"}:
                await event.edit(
                    t(
                        "logs_level_warning",
                        snowflake=CUSTOM_EMOJI["❄️"],
                        level=level.upper(),
                    ),
                    parse_mode="html",
                    buttons=[
                        [
                            Button.inline(
                                "✅ Send" if language == "en" else "✅ Отправить",
                                f"tester_logs:confirm:{level}".encode(),
                                style="success",
                            ),
                            Button.inline("↩", b"tester_logs:back", style="primary"),
                        ],
                        [Button.inline("✖", b"tester_logs:cancel", style="danger")],
                    ],
                )
                return

            await _send_logs(event, level)

        except Exception as e:
            await kernel.handle_error(e, source="tester_logs_callback", event=event)

    async def tester_logs_back_callback(event):
        try:
            await event.edit(
                f"{t('logs_choose_level', paper=CUSTOM_EMOJI['📰'])}\n{t('logs_choose_desc')}",
                parse_mode="html",
                buttons=[
                    [
                        Button.inline(
                            "DEBUG", b"tester_logs:level:debug", style="primary"
                        ),
                        Button.inline(
                            "INFO", b"tester_logs:level:info", style="primary"
                        ),
                    ],
                    [
                        Button.inline(
                            "WARNING", b"tester_logs:level:warning", style="primary"
                        ),
                        Button.inline(
                            "ERROR", b"tester_logs:level:error", style="primary"
                        ),
                    ],
                    [
                        Button.inline(
                            "CRITICAL", b"tester_logs:level:critical", style="primary"
                        ),
                        Button.inline("ALL", b"tester_logs:level:all", style="primary"),
                    ],
                    [Button.inline("✖", b"tester_logs:cancel", style="danger")],
                ],
            )
        except Exception as e:
            await kernel.handle_error(
                e, source="tester_logs_back_callback", event=event
            )

    kernel.register_callback_handler("tester_logs:level:", tester_logs_callback)
    kernel.register_callback_handler("tester_logs:confirm:", tester_logs_callback)
    kernel.register_callback_handler("tester_logs:cancel", tester_logs_callback)
    kernel.register_callback_handler("tester_logs:back", tester_logs_back_callback)

    @kernel.register.command("freezing")
    async def freezing_handler(event):
        """[int] freezing userbot"""
        try:
            args = event.text.split()
            if len(args) < 2:
                await event.edit(
                    t(
                        "freezing_usage",
                        speech=CUSTOM_EMOJI["🗯"],
                        prefix=kernel.custom_prefix,
                    ),
                    parse_mode="html",
                )
                return

            try:
                seconds = int(args[1])
                if seconds <= 0 or seconds > 60:
                    await event.edit(
                        t("freezing_range", speech=CUSTOM_EMOJI["🗯"]), parse_mode="html"
                    )
                    return
            except ValueError:
                await event.edit(
                    t("freezing_number", speech=CUSTOM_EMOJI["🗯"]), parse_mode="html"
                )
                return

            await event.edit(
                t("freezing_start", snowflake=CUSTOM_EMOJI["🧊"], seconds=seconds),
                parse_mode="html",
            )

            was_connected = client.is_connected()
            if was_connected:
                client.disconnect()
                await asyncio.sleep(0.5)

            await asyncio.sleep(seconds)

            if was_connected:
                await client.connect()
            await event.edit(
                t("freezing_done", check=CUSTOM_EMOJI["☑️"], seconds=seconds),
                parse_mode="html",
            )

        except Exception as e:
            await event.edit(
                t("error_logs", snowflake=CUSTOM_EMOJI["❄️"]), parse_mode="html"
            )
            await kernel.handle_error(e, source="freezing", event=event)
