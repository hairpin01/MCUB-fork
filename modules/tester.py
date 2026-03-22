import asyncio
import os
import time
import getpass
import socket
import subprocess
from telethon.tl.types import MessageEntityTextUrl
from telethon import functions
from copy import copy


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

    async def mcub_handler():
        me = kernel.cache.get('tester:me')
        if me is None:
            me = await kernel.client.get_me()
            kernel.cache.set('tester:me', me, ttl=3600)
        mcub_emoji = (
            '<tg-emoji emoji-id="5470015630302287916">🔮</tg-emoji><tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
            if me.premium
            else "MCUB"
        )
        return mcub_emoji

    @kernel.register.command("ping")
    async def ping_handler(event):
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

            _identity = kernel.cache.get('tester:identity')
            if _identity is None:
                try:
                    system_user = getpass.getuser()
                    hostname = socket.gethostname()
                except Exception:
                    system_user = hostname = "Unknown"
                kernel.cache.set('tester:identity', (system_user, hostname))
            else:
                system_user, hostname = _identity

            custom_text = kernel.config.get("ping_custom_text")
            if custom_text:
                try:
                    _known = ["ping_time", "uptime", "system_user", "hostname"]
                    _safe = custom_text.replace("{", "{{").replace("}", "}}")
                    for _k in _known:
                        _safe = _safe.replace("{{" + _k + "}}", "{" + _k + "}")
                    response = _safe.format(
                        ping_time=ping_time,
                        uptime=uptime,
                        system_user=system_user,
                        hostname=hostname,
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
                    text, entities = await client._parse_message_text(response, "html")
                    text, entities = add_link_preview(text, entities, banner_url)

                    try:
                        await msg.edit(
                            text,
                            formatting_entities=entities,
                            link_preview=True,
                            invert_media=invert_media
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
                        await msg.edit(
                            response, file=banner_url, parse_mode="html"
                        )
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
        try:

            kernel_log_path = os.path.join(kernel.LOGS_DIR, "kernel.log")

            if not os.path.exists(kernel_log_path):
                await event.edit(
                    t("logs_not_found", file=CUSTOM_EMOJI["📁"]), parse_mode="html"
                )
                return

            await event.edit(
                t("logs_sending", printer=CUSTOM_EMOJI["🖨"]), parse_mode="html"
            )

            send_params = {}
            chat = await event.get_chat()
            reply_to = None
            if hasattr(chat, "forum") and chat.forum and event.message.reply_to:
                reply_to = (
                    event.message.reply_to.reply_to_top_id
                    or event.message.reply_to.reply_to_msg_id
                )

            if reply_to:
                send_params["reply_to"] = reply_to

            await event.edit(
                f'{CUSTOM_EMOJI["📝"]} {t("logs")} {await mcub_handler()}\n'
                f'{CUSTOM_EMOJI["✏️"]} {t("kernel_version")} {kernel.VERSION}',
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
