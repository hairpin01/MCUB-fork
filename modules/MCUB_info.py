# author: @Hairpin00
# version: 1.0.9
# description: Info userbot with improved quote mode

import asyncio
import os
import time
import platform
import psutil
import aiohttp
import getpass
import socket
from telethon.tl.types import MessageEntityTextUrl, InputMediaWebPage
from telethon import functions, types
from pathlib import Path

ZERO_WIDTH_CHAR = "\u2060"

def add_link_preview(text, entities, link):
    if not text or not link:
        return text, entities

    new_text = ZERO_WIDTH_CHAR + text

    new_entities = []

    if entities:
        for entity in entities:
            new_entity = entity
            if hasattr(entity, 'offset'):
                new_entity.offset += 1
            new_entities.append(new_entity)

    link_entity = MessageEntityTextUrl(
        offset=0,
        length=1,
        url=link
    )

    new_entities.append(link_entity)

    return new_text, new_entities

def register(kernel):
    client = kernel.client

    kernel.config.setdefault('info_quote_media', False)
    kernel.config.setdefault('info_banner_url', 'https://raw.githubusercontent.com/hairpin01/MCUB-fork/refs/heads/main/img/info.png')
    kernel.config.setdefault('info_invert_media', False)

    def format_uptime(seconds):
        hours = int(seconds) // 3600
        minutes = (int(seconds) % 3600) // 60
        secs = int(seconds) % 60
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    async def check_update():
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get('https://raw.githubusercontent.com/Mitrichdfklwhcluio/MCUBFB/main/core/kernel.py') as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        import re
                        match = re.search(r"VERSION = '([^']+)'", content)
                        if match:
                            remote_version = match.group(1)
                            if remote_version != kernel.VERSION:
                                return True
            return False
        except asyncio.TimeoutError:
            return False
        except Exception:
            return False

    @kernel.register_command('info')
    # инфо о юзерботе
    async def info_cmd(event):
        try:
            start_time = time.time()
            msg = await event.edit('❄️')
            ping_time = round((time.time() - start_time) * 1000, 2)

            uptime_str = format_uptime(time.time() - kernel.start_time)

            distro_name = "linux"
            try:
                with open('/etc/os-release', 'r') as f:
                    for line in f:
                        if 'PRETTY_NAME' in line:
                            distro_name = line.split('=')[1].strip().strip('"')
                            break
            except:
                pass

            distro_emojis = {
                'arch': '❄️',
                'ubuntu': '🟠',
                'debian': '🔴',
                'mint': '🌿',
                'fedora': '🔵',
                'centos': '🟢'
            }

            distro_emoji = ''
            distro_lower = distro_name.lower()
            for key, emoji in distro_emojis.items():
                if key in distro_lower:
                    distro_emoji = emoji
                    break

            platform_type = "vds 🧩"
            if 'microsoft' in platform.uname().release.lower():
                platform_type = "wsl 🍀"
            elif 'termux' in os.environ.get('PREFIX', ''):
                platform_type = "Termux 🌪️"

            cpu_usage = f"{psutil.cpu_percent(interval=0.1)}%"
            ram = psutil.virtual_memory()
            ram_usage = f"{ram.percent}%"

            update_needed = await check_update()

            system_user = getpass.getuser()
            hostname = socket.gethostname()

            info_text = f"""💠 <b>Mitrich UserBot</b>
<blockquote>🌩️ <b>Version:</b> <code>{kernel.VERSION}</code>
{'💔 <b>An update is needed</b>' if update_needed else '🔮 <b>No update needed</b>'}</blockquote>

<blockquote>📡 <b>Ping:</b> <code>{ping_time} ms</code>
🧪 <b>Uptime:</b> <code>{uptime_str}</code>
🔬 <b>System:</b> {distro_name} {distro_emoji}
🧬 <b>Platform:</b> <code>{platform_type}</code></blockquote>

<blockquote>🔷 <b>CPU:</b> <i>~{cpu_usage}</i>
🔶 <b>RAM:</b> <i>~{ram_usage}</i></blockquote>"""

            banner_url = kernel.config.get('info_banner_url')
            quote_media = kernel.config.get('info_quote_media', False)
            invert_media = kernel.config.get('info_invert_media', False)


            if quote_media and banner_url and banner_url.startswith(('http://', 'https://')):
                try:
                    text, entities = await client._parse_message_text(info_text, 'html')
                    text, entities = add_link_preview(text, entities, banner_url)

                    await msg.delete()

                    try:
                        await client.send_message(
                            entity=await event.get_input_chat(),
                            message=text,
                            formatting_entities=entities,
                            link_preview=True,
                            invert_media=invert_media
                        )
                        return
                    except TypeError as e:
                        if "invert_media" in str(e):
                            await client(functions.messages.SendMessageRequest(
                                peer=await event.get_input_chat(),
                                message=text,
                                entities=entities,
                                invert_media=invert_media,
                                no_webpage=False
                            ))
                            return
                        else:
                            raise

                except Exception as e:
                    await kernel.handle_error(e, source="info_cmd:quote_mode", event=event)

            has_banner = False
            if banner_url:
                if banner_url.startswith(('http://', 'https://')):
                    has_banner = True
                else:
                    if os.path.exists(banner_url):
                        has_banner = True
                    else:
                        current_dir = Path.cwd()
                        possible_paths = [
                            Path(banner_url),
                            current_dir / banner_url,
                            Path(kernel.IMG_DIR) / 'info.png'
                        ]

                        for path in possible_paths:
                            if path.exists():
                                banner_url = str(path)
                                has_banner = True
                                break

            if not has_banner:
                default_banner = os.path.join(kernel.IMG_DIR, 'info.png')
                if os.path.exists(default_banner):
                    banner_url = default_banner
                    has_banner = True

            if has_banner and banner_url:
                await msg.delete()
                try:
                    await event.respond(
                        info_text,
                        file=banner_url,
                        parse_mode='html'
                    )
                except Exception as e:
                    await event.respond(info_text, parse_mode='html')
                    await kernel.handle_error(e, source="info_cmd:send_banner", event=event)
            else:
                await msg.edit(info_text, parse_mode='html')

        except Exception as e:
            await event.edit("🌩️ <b>Ошибка, смотри логи</b>", parse_mode='html')
            await kernel.handle_error(e, source="info_cmd", event=event)
