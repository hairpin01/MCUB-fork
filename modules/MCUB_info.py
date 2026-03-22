import asyncio
import os
import time
import platform
import psutil
import aiohttp
import getpass
import socket
import re
import subprocess

from utils.platform import get_platform, is_wsl, is_termux
from telethon.tl.types import MessageEntityTextUrl
from telethon import functions
from pathlib import Path
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


def _get_commit_sha_sync(short=True):
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=base_dir,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            return sha[:7] if short else sha
    except Exception:
        pass
    return "unknown"

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
    language = kernel.config.get('language', 'en')

    # Локализованные строки
    strings = {
        'en': {
            'custom_text_error': '<b>Error in custom text format:</b> {error}',
            'quote_mode_error': 'Error in quote mode',
            'send_banner_error': 'Error sending banner',
            'error_see_logs': '{warning} <b>Error, see logs</b>',
        },
        'ru': {
            'custom_text_error': '<b>Ошибка в форматировании кастомного текста:</b> {error}',
            'quote_mode_error': 'Ошибка в режиме цитирования',
            'send_banner_error': 'Ошибка отправки баннера',
            'error_see_logs': '{warning} <b>Ошибка, смотри логи</b>',
        }
    }

    # Получаем строки для текущего языка
    lang_strings = strings.get(language, strings['en'])

    def t(key, **kwargs):
        """Возвращает локализованную строку с подстановкой значений"""
        if key not in lang_strings:
            return key
        return lang_strings[key].format(**kwargs)

    kernel.config.setdefault("info_quote_media", False)
    kernel.config.setdefault(
        "info_banner_url",
        "https://raw.githubusercontent.com/hairpin01/MCUB-fork/refs/heads/main/img/info.png",
    )
    kernel.config.setdefault("info_invert_media", False)
    kernel.config.setdefault("info_custom_text", None)
    kernel.config.setdefault("info_start_emoji", CUSTOM_EMOJI["load"])

    def resolve_info_start_emoji() -> str:
        """Resolve configurable start emoji for .info with sensible fallbacks."""
        raw = kernel.config.get("info_start_emoji", CUSTOM_EMOJI["load"])
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
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    "https://raw.githubusercontent.com/hairpin01/MCUB-fork/main/core/kernel.py"
                ) as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        match = re.search(r"VERSION = '([^']+)'", content)
                        if match:
                            remote_version = match.group(1)
                            if remote_version != kernel.VERSION:
                                return True
            return False
        except (asyncio.TimeoutError, Exception):
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
                if os.path.exists(proc_stat_path) and os.access(proc_stat_path, os.R_OK):
                    with open(proc_stat_path, "r") as f:
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

                if os.path.exists(proc_meminfo_path) and os.access(proc_meminfo_path, os.R_OK):
                    meminfo = {}
                    with open(proc_meminfo_path, "r") as f:
                        for line in f:
                            if ":" in line:
                                key, value = line.split(":", 1)
                                meminfo[key.strip()] = value.strip()

                    if "MemTotal" in meminfo:
                        total = int(meminfo["MemTotal"].split()[0])
                        available = meminfo.get("MemAvailable", meminfo.get("MemFree", "0"))
                        available = int(available.split()[0])
                        used = total - available
                        if total > 0:
                            ram_percent = (used / total) * 100
                            ram_usage = f"{ram_percent:.1f}%"
            except Exception:
                pass

        return cpu_usage, ram_usage

    @kernel.register.command("info")
    async def info_cmd(event):
        try:
            start_time = time.time()
            msg = await event.edit(resolve_info_start_emoji(), parse_mode="html")
            ping_time = round((time.time() - start_time) * 1000, 2)

            core_name  = getattr(kernel, "CORE_NAME", "standard")

            uptime_str = format_uptime(time.time() - kernel.start_time)

            distro_name = "Unknown"
            try:
                if os.path.exists("/etc/os-release"):
                    with open("/etc/os-release", "r") as f:
                        for line in f:
                            if "PRETTY_NAME" in line:
                                distro_name = line.split("=")[1].strip().strip('"')
                                break
                else:
                    distro_name = platform.platform()
            except:
                distro_name = "Linux"

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

            current_platform = get_platform()
            platform_type = f"VDS {CUSTOM_EMOJI['vds']}"
            if is_wsl():
                platform_type = f"WSL {CUSTOM_EMOJI['wsl']}"
            elif is_termux():
                platform_type = f"Termux {CUSTOM_EMOJI['termux']}"

            cpu_usage, ram_usage = get_system_info()
            update_needed = await check_update()

            try:
                system_user = getpass.getuser()
                hostname = socket.gethostname()
            except Exception:
                system_user = hostname = "Unknown"

            update_emoji = CUSTOM_EMOJI["💔"] if update_needed else CUSTOM_EMOJI["🔮"]
            update_text = "Update needed" if update_needed else "No update needed"

            me = await client.get_me()
            user_ids = me.id

            user_emojis = {
                6020965582: '5469888215802482605',
                2037125547: '5467932472379480411',
                779572293: '5470163024989952512',
                8405520863: '5470170528297817805',
                855890735: '5470063433288290290',
            }
            user = f'<tg-emoji emoji-id="{user_emojis.get(user_ids, "5470015630302287916")}">{"Ⓜ️" if user_ids in user_emojis else "🕳"}</tg-emoji>'

            mcub_emoji = (
                f'{user}<tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
                if me.premium
                else "Mitrich UserBot"
            )

            branch = _detect_branch_sync()
            commit_sha = _get_commit_sha_sync()

            custom_text = kernel.config.get("info_custom_text")
            if custom_text:
                try:
                    _known = [
                        "kernel_version", "core_name", "ping_time", "uptime_str",
                        "distro_name", "distro_emoji", "platform_type", "cpu_usage",
                        "ram_usage", "system_user", "hostname", "update_emoji",
                        "update_text", "update_needed", "branch", "commit_sha",
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
                    )
                except Exception as e:
                    await kernel.handle_error(
                        e, source="info_cmd:custom_text_format", event=event
                    )
                    info_text = t('custom_text_error', error=str(e))
            else:
                info_text = f"""<b>{mcub_emoji}</b>
<blockquote>{CUSTOM_EMOJI['🌩️']} <b>Version:</b> <code>{kernel.VERSION}</code>
{CUSTOM_EMOJI['🧩']} <b>Kernel:</b> <code>{core_name}</code>
{f"{CUSTOM_EMOJI['💔']} <b>Update needed</b>" if update_needed else f"{CUSTOM_EMOJI['🔮']} <b>No update needed</b>"}
{CUSTOM_EMOJI['🌐']} <b>Branch:</b> <code>{branch}</code> <b>Build:</b> <code>{commit_sha}</code></blockquote>

<blockquote>{CUSTOM_EMOJI['📡']} <b>Ping:</b> <code>{ping_time} ms</code>
{CUSTOM_EMOJI['🧪']} <b>Uptime:</b> <code>{uptime_str}</code>
{CUSTOM_EMOJI['🔬']} <b>System:</b> {distro_name} {distro_emoji}
{CUSTOM_EMOJI['🧬']} <b>Platform:</b> <code>{platform_type}</code></blockquote>

<blockquote>{CUSTOM_EMOJI['🔷']} <b>CPU:</b> <i>~{cpu_usage}</i>
{CUSTOM_EMOJI['🔶']} <b>RAM:</b> <i>~{ram_usage}</i></blockquote>"""

            banner_url = kernel.config.get("info_banner_url")
            quote_media = kernel.config.get("info_quote_media", False)
            invert_media = kernel.config.get("info_invert_media", False)

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
                t('error_see_logs', warning=CUSTOM_EMOJI['⚠️']), parse_mode="html"
            )
            await kernel.handle_error(e, source="info_cmd", event=event)
