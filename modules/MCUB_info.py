# requires: psutil, aiohttp

import asyncio
import os
import time
import platform
import psutil
import aiohttp
import json
from telethon.tl.types import InputMediaWebPage
from pathlib import Path

def register(kernel):
    client = kernel.client
    
    kernel.config.setdefault('info_banner_url', None)
    kernel.config.setdefault('info_quote_media', False)
    kernel.config.setdefault('info_invert_media', False)

    async def save_config():
        with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

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

            info_text = f"""💠 <b>Mitritch UserBot</b>
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

            has_banner = False
            if banner_url:
                if banner_url.startswith(('http://', 'https://')):
                    has_banner = True
                else:
                    # Проверяем существование файла
                    if os.path.exists(banner_url):
                        has_banner = True
                    else:
                        # Пробуем найти относительно текущей директории
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
            
            # Если баннер не указан, проверяем стандартный путь
            if not has_banner:
                default_banner = os.path.join(kernel.IMG_DIR, 'info.png')
                if os.path.exists(default_banner):
                    banner_url = default_banner
                    has_banner = True

            if has_banner and banner_url:
                await msg.delete()
                
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
                    except Exception as e:
                        await kernel.handle_error(e, source="info_cmd_banner", event=event)
                        await event.respond(info_text, parse_mode='html')
                else:
                    try:
                        # Для обычных файлов не используем invert_media
                        await event.respond(
                            info_text,
                            file=banner_url,
                            parse_mode='html'
                        )
                    except Exception as e:
                        await kernel.handle_error(e, source="info_cmd_banner", event=event)
                        await event.respond(info_text, parse_mode='html')
            else:
                await msg.edit(info_text, parse_mode='html')
                
        except Exception as e:
            await event.edit("🌩️ <b>Ошибка, смотри логи</b>", parse_mode='html')
            await kernel.handle_error(e, source="info_cmd", event=event)

    @kernel.register_command('set_info_banner_url')
    async def set_info_banner_url_handler(event):
        try:
            args = event.text.split()
            
            if len(args) < 2:
                current = kernel.config.get('info_banner_url', 'не установлен')
                await event.edit(f'📸 <b>Текущий баннер:</b> <code>{current}</code>\n\nИспользование: <code>{kernel.custom_prefix}set_info_banner_url [url|none]</code>', parse_mode='html')
                return

            url = args[1].strip()

            if url.lower() == 'none':
                kernel.config['info_banner_url'] = None
                await save_config()
                await event.edit('✅ <b>Баннер удален</b>', parse_mode='html')
            else:
                # Проверяем, является ли путь локальным файлом
                if not url.startswith(('http://', 'https://')):
                    if os.path.exists(url):
                        kernel.config['info_banner_url'] = url
                    else:
                        # Пробуем найти файл относительно текущей директории
                        current_dir = Path.cwd()
                        possible_paths = [
                            Path(url),
                            current_dir / url,
                            Path(kernel.IMG_DIR) / url
                        ]
                        
                        found = False
                        for path in possible_paths:
                            if path.exists():
                                kernel.config['info_banner_url'] = str(path)
                                found = True
                                break
                        
                        if not found:
                            await event.edit('❌ <b>Файл не найден</b>', parse_mode='html')
                            return
                else:
                    kernel.config['info_banner_url'] = url
                
                await save_config()
                await event.edit(f'✅ <b>Баннер установлен:</b> <code>{kernel.config["info_banner_url"]}</code>', parse_mode='html')
        except Exception as e:
            await event.edit("🌩️ <b>Ошибка, смотри логи</b>", parse_mode='html')
            await kernel.handle_error(e, source="set_info_banner_url", event=event)

    @kernel.register_command('set_info_quote_media')
    async def set_info_quote_media_handler(event):
        try:
            args = event.text.split()
            current = kernel.config.get('info_quote_media', False)

            if len(args) < 2:
                status = 'включен' if current else 'выключен'
                await event.edit(f'🔄 <b>Режим цитаты медиа:</b> {status}\n\nИспользование: <code>{kernel.custom_prefix}set_info_quote_media [on|off]</code>', parse_mode='html')
                return

            value = args[1].lower()

            if value in ['on', 'true', '1', 'yes']:
                kernel.config['info_quote_media'] = True
                await save_config()
                await event.edit('✅ <b>Режим цитаты медиа включен</b>', parse_mode='html')
            elif value in ['off', 'false', '0', 'no']:
                kernel.config['info_quote_media'] = False
                await save_config()
                await event.edit('✅ <b>Режим цитаты медиа выключен</b>', parse_mode='html')
            else:
                await event.edit('❌ <b>Используйте: on/off, true/false, yes/no</b>', parse_mode='html')
        except Exception as e:
            await event.edit("🌩️ <b>Ошибка, смотри логи</b>", parse_mode='html')
            await kernel.handle_error(e, source="set_info_quote_media", event=event)

    @kernel.register_command('set_info_invert_media')
    async def set_info_invert_media_handler(event):
        try:
            args = event.text.split()
            current = kernel.config.get('info_invert_media', False)

            if len(args) < 2:
                status = 'включено' if current else 'выключено'
                await event.edit(f'🔄 <b>Инвертирование медиа:</b> {status}\n\nИспользование: <code>{kernel.custom_prefix}set_info_invert_media [on|off]</code>', parse_mode='html')
                return

            value = args[1].lower()

            if value in ['on', 'true', '1', 'yes']:
                kernel.config['info_invert_media'] = True
                await save_config()
                await event.edit('✅ <b>Инвертирование медиа включено</b>', parse_mode='html')
            elif value in ['off', 'false', '0', 'no']:
                kernel.config['info_invert_media'] = False
                await save_config()
                await event.edit('✅ <b>Инвертирование медиа выключено</b>', parse_mode='html')
            else:
                await event.edit('❌ <b>Используйте: on/off, true/false, yes/no</b>', parse_mode='html')
        except Exception as e:
            await event.edit("🌩️ <b>Ошибка, смотри логи</b>", parse_mode='html')
            await kernel.handle_error(e, source="set_info_invert_media", event=event)