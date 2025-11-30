# hostinfo.py - Информация о хостинге юзербота

import platform
import psutil
import sys
from telethon import events

def register(client):
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.host$'))
    async def host_handler(event):
        # Система
        system = platform.system()
        system_emoji = {"Windows": "🪟", "Linux": "🐧", "Darwin": "🍎"}.get(system, "💻")
        
        # Версия ОС
        os_version = platform.version()
        release = platform.release()
        
        # Архитектура
        arch = platform.machine()
        
        # Python
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.patch}"
        
        # Процессор
        cpu_name = platform.processor() or "Unknown"
        cpu_cores = psutil.cpu_count(logical=False)
        cpu_threads = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq()
        cpu_freq_str = f"{cpu_freq.current:.0f} MHz" if cpu_freq else "N/A"
        
        # RAM
        ram = psutil.virtual_memory()
        ram_total = ram.total / (1024**3)
        ram_used = ram.used / (1024**3)
        ram_percent = ram.percent
        
        # Диск
        disk = psutil.disk_usage('/')
        disk_total = disk.total / (1024**3)
        disk_used = disk.used / (1024**3)
        disk_percent = disk.percent
        
        # Имя устройства
        hostname = platform.node()
        
        result = f"""{system_emoji} **Информация о хостинге**

🖥 **Устройство:** `{hostname}`
💻 **Система:** {system} {release}
🏗 **Архитектура:** {arch}
🐍 **Python:** {python_version}

⚙️ **Процессор:**
• Модель: `{cpu_name}`
• Ядра: {cpu_cores} физ. / {cpu_threads} логич.
• Частота: {cpu_freq_str}

💾 **Оперативная память:**
• Всего: {ram_total:.1f} GB
• Использовано: {ram_used:.1f} GB ({ram_percent}%)

💿 **Диск:**
• Всего: {disk_total:.1f} GB
• Использовано: {disk_used:.1f} GB ({disk_percent}%)

📱 **Приложение:** Telethon UserBot
🔧 **Интерпретатор:** {sys.executable}"""
        
        await event.edit(result)
