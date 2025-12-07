import asyncio
import time
import sys
import os
import importlib.util
import re
import psutil
import aiohttp
from telethon import TelegramClient, events

VERSION = '0.0.1'
RESTART_FILE = 'restart.tmp'
MODULES_DIR = 'modules'
IMG_DIR = 'img'
loaded_modules = {}
start_time = time.time()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

API_ID = ''
API_HASH = ''
BOT_TOKEN = ''

import sqlite3

bot = TelegramClient('bot_session', API_ID, API_HASH)

@bot.on(events.NewMessage(outgoing=True, pattern=r'\.'))
async def handler(event):
    text = event.text
    
    if text == '.ping':
        start = time.time()
        msg = await event.edit('Pong!')
        end = time.time()
        await msg.edit(f'Pong! {round((end - start) * 1000)}ms')
    
    elif text == '.info':
        await event.delete()
        
        sender = await event.get_sender()
        owner_name = sender.first_name if sender.first_name else 'Unknown'
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://raw.githubusercontent.com/mitrich-dev/UserBotForBot/main/version.txt', timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        latest_version = (await resp.text()).strip()
                        version_status = '✅ Актуальная' if VERSION == latest_version else f'⚠️ Доступна {latest_version}'
                    else:
                        version_status = '❓ Не удалось проверить'
        except:
            version_status = '❓ Не удалось проверить'
        
        uptime_seconds = int(time.time() - start_time)
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        uptime = f'{hours}ч {minutes}м {seconds}с'
        
        process = psutil.Process()
        cpu_percent = process.cpu_percent(interval=0.1)
        ram_mb = process.memory_info().rss / 1024 / 1024
        
        img_path = None
        if os.path.exists(IMG_DIR):
            images = [f for f in os.listdir(IMG_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
            if images:
                img_path = os.path.join(IMG_DIR, images[0])
        
        caption = f'''**Mitrich UserBot for bot**
👤 Владелец: {owner_name}
💻 Версия: {VERSION}
{version_status}
⏱ Аптайм: {uptime}
📊 CPU: {cpu_percent:.1f}%
💾 RAM: {ram_mb:.1f} MB
🟢 Статус: Working'''
        
        if img_path:
            await bot.send_file(event.chat_id, img_path, caption=caption)
        else:
            await bot.send_message(event.chat_id, caption)
    
    elif text == '.restart':
        await event.edit('Перезагрузка...')
        with open(RESTART_FILE, 'w') as f:
            f.write(f'{event.chat_id},{event.id},{time.time()}')
        os.execl(sys.executable, sys.executable, *sys.argv)
    
    elif text == '.im':
        if not event.is_reply:
            await event.edit('❌ Ответьте на .py файл')
            return
        
        reply = await event.get_reply_message()
        if not reply.document or not reply.document.attributes[0].file_name.endswith('.py'):
            await event.edit('❌ Это не .py файл')
            return
        
        await event.edit('📥 Загрузка модуля...')
        
        if not os.path.exists(MODULES_DIR):
            os.makedirs(MODULES_DIR)
        
        file_name = reply.document.attributes[0].file_name
        file_path = os.path.join(MODULES_DIR, file_name)
        await reply.download_media(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            if 'from .. import' in code or 'import loader' in code:
                await event.edit(f'❌ Модуль не совместим. Используйте модули с register(bot)')
                os.remove(file_path)
                return
            
            spec = importlib.util.spec_from_file_location(file_name[:-3], file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[file_name[:-3]] = module
            spec.loader.exec_module(module)
            
            if hasattr(module, 'register'):
                module.register(bot)
                loaded_modules[file_name[:-3]] = module
                await event.edit(f'✅ Модуль {file_name} установлен')
            else:
                await event.edit(f'❌ Модуль должен иметь функцию register(bot)')
                os.remove(file_path)
        except Exception as e:
            await event.edit(f'❌ Ошибка: {str(e)}')
            if os.path.exists(file_path):
                os.remove(file_path)
    
    elif text == '.lm':
        if not loaded_modules:
            await event.edit('📦 Модули не загружены')
            return
        
        msg = '📦 **Загруженные модули:**\n\n'
        for name, module in loaded_modules.items():
            msg += f'• **{name}**\n'
            if os.path.exists(os.path.join(MODULES_DIR, f'{name}.py')):
                with open(os.path.join(MODULES_DIR, f'{name}.py'), 'r', encoding='utf-8') as f:
                    code = f.read()
                    commands = re.findall(r"pattern=r['\"]\^?\\?\.([a-zA-Z0-9_]+)", code)
                    if commands:
                        msg += f'  Команды: {", ".join([f".{cmd}" for cmd in commands])}\n'
            msg += '\n'
        await event.edit(msg)
    
    elif text.startswith('.um '):
        module_name = text.split(maxsplit=1)[1]
        
        if module_name not in loaded_modules:
            await event.edit(f'❌ Модуль {module_name} не найден')
            return
        
        file_path = os.path.join(MODULES_DIR, f'{module_name}.py')
        if os.path.exists(file_path):
            os.remove(file_path)
        
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        del loaded_modules[module_name]
        await event.edit(f'🗑️ Модуль {module_name} удален\n\n⚠️ Перезагрузите юзербот для полного удаления')

async def main():
    await bot.start(bot_token=BOT_TOKEN)
    print('Бот запущен')
    
    if not os.path.exists(MODULES_DIR):
        os.makedirs(MODULES_DIR)
    
    if os.path.exists(MODULES_DIR):
        for file_name in os.listdir(MODULES_DIR):
            if file_name.endswith('.py'):
                try:
                    file_path = os.path.join(MODULES_DIR, file_name)
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                    
                    if 'from .. import' in code or 'import loader' in code:
                        print(f'Пропущен несовместимый модуль: {file_name}')
                        continue
                    
                    spec = importlib.util.spec_from_file_location(file_name[:-3], file_path)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[file_name[:-3]] = module
                    spec.loader.exec_module(module)
                    if hasattr(module, 'register'):
                        module.register(bot)
                        loaded_modules[file_name[:-3]] = module
                        print(f'Загружен модуль: {file_name}')
                    else:
                        print(f'Модуль {file_name} не имеет register(bot)')
                except Exception as e:
                    print(f'Ошибка загрузки {file_name}: {e}')
    
    if os.path.exists(RESTART_FILE):
        with open(RESTART_FILE, 'r') as f:
            chat_id, msg_id, start_time = f.read().split(',')
        os.remove(RESTART_FILE)
        restart_time = round((time.time() - float(start_time)) * 1000)
        await bot.edit_message(int(chat_id), int(msg_id), f'Юзербот перезагружен ✅\nВремя: {restart_time}ms')
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
