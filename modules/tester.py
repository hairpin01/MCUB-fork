import asyncio
import os
import time
import getpass
import socket
import subprocess
from datetime import datetime

try:
    import psutil as _psutil
except ImportError:
    _psutil = None
from telethon.tl.types import InputMediaWebPage
from telethon import functions
from copy import copy
from utils import get_args


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
    language = kernel.config.get("language", "en")

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
            "logs_not_fount_args": "<b>Available argument:</b> <code>clear</code>",
            "logs_clear": "<b>Cleared kernel logs</b>",
            "file_empty": "<b>Is logs empty</b>",
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
            "logs_not_fount_args": "<b>Доступный аргумент: </b><code>clear</code>",
            "logs_clear": "<b>Логи очишены</b>",
            "file_empty": "<b>Логи пустые</b>",
        },
    }

    # Получаем строки для текущего языка
    lang_strings = strings.get(language, strings["en"])

    def t(key, **kwargs):
        """Возвращает локализованную строку с подстановкой значений"""
        if key not in lang_strings:
            return key
        return lang_strings[key].format(**kwargs)

    branch = _detect_branch_sync()

    kernel.config.setdefault("ping_quote_media", False)
    kernel.config.setdefault(
        "ping_banner_url",
        f"https://raw.githubusercontent.com/hairpin01/MCUB-fork/refs/heads/{branch}/img/ping.png",
    )
    kernel.config.setdefault("ping_invert_media", False)
    kernel.config.setdefault("ping_custom_text", None)
    kernel.config.setdefault("ping_start_emoji", CUSTOM_EMOJI["✏️"])

    def resolve_ping_start_emoji() -> str:
        """Resolve configurable start emoji for .ping with sensible fallbacks."""
        raw = kernel.config.get("ping_start_emoji", CUSTOM_EMOJI["✏️"])
        if not isinstance(raw, str):
            return CUSTOM_EMOJI["✏️"]
        value = raw.strip()
        if not value:
            return CUSTOM_EMOJI["✏️"]
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
        """ping"""
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

            custom_text = kernel.config.get("ping_custom_text")
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
                response = f"""<blockquote>{CUSTOM_EMOJI['❄️']} <b>{lang_strings['ping']}:</b> {ping_time} {lang_strings['ms']}</blockquote>
<blockquote>{CUSTOM_EMOJI['❄️']} <b>{lang_strings['uptime']}:</b> {uptime}</blockquote>"""

            banner_url = kernel.config.get("ping_banner_url")
            quote_media = kernel.config.get("ping_quote_media", False)
            invert_media = kernel.config.get("ping_invert_media", False)

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
                if args[0] in "clear":
                    if size_kernel_log == 0:
                        await event.edit(f"{CUSTOM_EMOJI['🗳']} {t('file_empty')}")
                        return

                    with open(kernel_log_path, "w") as f:
                        pass

                    await event.edit(
                        f"{CUSTOM_EMOJI['🗳']} {t('logs_clear')}", parse_mode="html"
                    )
                    return
                else:
                    await event.edit(
                        f"{CUSTOM_EMOJI['🧊']} {t('logs_not_fount_args')}",
                        parse_mode="html",
                    )
                    return

            await event.edit(
                t("logs_sending", printer=CUSTOM_EMOJI["🖨"]), parse_mode="html"
            )
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

            await event.edit(
                f'{CUSTOM_EMOJI["📝"]} <b>{t("logs")}</b> {await mcub_handler()}\n'
                f'<blockquote>{CUSTOM_EMOJI["✏️"]} <b>{t("kernel_version")}</b> {kernel.VERSION}#<a href="{commit_url}">{commit_sha}</a>\n'
                f"{CUSTOM_EMOJI['🛰']} <b>{t('branch')}:</b> {branch}</blockquote>",
                file=kernel_log_path,
                parse_mode="html",
            )
            # await event.delete()

        except Exception as e:
            await event.edit(
                t("error_logs", snowflake=CUSTOM_EMOJI["❄️"]), parse_mode="html"
            )
            await kernel.handle_error(e, source="logs", event=event)

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
