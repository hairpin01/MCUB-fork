import asyncio
import os
import time
import platform
import psutil
import aiohttp
import json
import getpass
import socket
from telethon.tl.types import InputMediaWebPage
from pathlib import Path

def register(kernel):
    client = kernel.client

    kernel.config.setdefault('info_initial_emoji', '❄️')
    kernel.config.setdefault('info_text', """💠 <b>Mitritch UserBot</b>
<blockquote>🌩️ <b>Version:</b> <code>{version}</code>
{update_status}</blockquote>

<blockquote>📡 <b>Ping:</b> <code>{ping_time} ms</code>
🧪 <b>Uptime:</b> <code>{uptime}</code>
🔬 <b>System:</b> {distro_name} {distro_emoji}
🧬 <b>Platform:</b> <code>{platform_type}</code></blockquote>

<blockquote>🔷 <b>CPU:</b> <i>~{cpu_usage}</i>
🔶 <b>RAM:</b> <i>~{ram_usage}</i></blockquote>""")
    kernel.config.setdefault('info_banner_url', None)
    kernel.config.setdefault('info_quote_media', False)
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
    async def info_cmd(event):
        try:
            start_emoji = kernel.config.get('info_initial_emoji', '❄️')
            start_time = time.time()
            msg = await event.edit(start_emoji)
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

            info_template = kernel.config.get('info_text', """💠 <b>Mitritch UserBot</b>
<blockquote>🌩️ <b>Version:</b> <code>{version}</code>
{update_status}</blockquote>

<blockquote>📡 <b>Ping:</b> <code>{ping_time} ms</code>
🧪 <b>Uptime:</b> <code>{uptime}</code>
🔬 <b>System:</b> {distro_name} {distro_emoji}
🧬 <b>Platform:</b> <code>{platform_type}</code></blockquote>

<blockquote>🔷 <b>CPU:</b> <i>~{cpu_usage}</i>
🔶 <b>RAM:</b> <i>~{ram_usage}</i></blockquote>""")

            update_status = '💔 <b>An update is needed</b>' if update_needed else '🔮 <b>No update needed</b>'

            info_text = info_template.format(
                version=kernel.VERSION,
                update_status=update_status,
                ping_time=ping_time,
                uptime=uptime_str,
                distro_name=distro_name,
                distro_emoji=distro_emoji,
                platform_type=platform_type,
                cpu_usage=cpu_usage,
                ram_usage=ram_usage,
                user=system_user,
                hostname=hostname
            )

            banner_url = kernel.config.get('info_banner_url')

            quote_media = kernel.config.get('info_quote_media', False)
            invert_media = kernel.config.get('info_invert_media', False)

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
                banner_sent = False

                if quote_media and banner_url.startswith(('http://', 'https://')):
                    try:
                        banner = InputMediaWebPage(
                            banner_url,
                            force_large_media=True,
                            force_small_media=False
                        )
                        await event.respond(
                            info_text,
                            file=banner,
                            parse_mode='html',
                            invert_media=invert_media
                        )
                        banner_sent = True
                    except Exception as e:
                        try:
                            await event.respond(
                                info_text,
                                file=banner_url,
                                parse_mode='html'
                            )
                            banner_sent = True
                        except Exception as e2:
                            pass
                else:
                    try:
                        await event.respond(
                            info_text,
                            file=banner_url,
                            parse_mode='html'
                        )
                        banner_sent = True
                    except Exception as e:
                        pass

                if not banner_sent:
                    await event.respond(info_text, parse_mode='html')
            else:
                await msg.edit(info_text, parse_mode='html')

        except Exception as e:
            await event.edit("🌩️ <b>Ошибка, смотри логи</b>", parse_mode='html')
            await kernel.handle_error(e, source="info_cmd", event=event)
