import asyncio
import os
import sys
import re
import time
import aiohttp
from telethon import events, Button

def register(kernel):
    client = kernel.client
    
    UPDATE_REPO = 'https://raw.githubusercontent.com/hairpin01/MCUB-fork/main'
    
    @kernel.register_command('restart')
    async def restart_handler(event):
        await event.edit('🔄 Перезагрузка...')
        with open(kernel.RESTART_FILE, 'w') as f:
            f.write(f'{event.chat_id},{event.id},{time.time()}')
        os.execl(sys.executable, sys.executable, *sys.argv)
    
    @kernel.register_command('update')
    async def update_handler(event):
        await event.edit('🔄 Проверка обновлений...')
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{UPDATE_REPO}/core/kernel.py') as resp:
                    if resp.status == 200:
                        new_code = await resp.text()
                        
                        if 'VERSION' in new_code:
                            new_version = re.search(r"VERSION = '([^']+)'", new_code)
                            if new_version and new_version.group(1) != kernel.VERSION:
                                await event.edit(f'📥 Обновление до {new_version.group(1)}...')
                                
                                with open(__file__, 'r', encoding='utf-8') as f:
                                    current_code = f.read()
                                with open(kernel.BACKUP_FILE, 'w', encoding='utf-8') as f:
                                    f.write(current_code)
                                
                                with open(__file__, 'w', encoding='utf-8') as f:
                                    f.write(new_code)
                                
                                await event.edit(f'✅ Обновлено до {new_version.group(1)}\n📦 Бэкап создан\nПерезагрузка...')
                                await asyncio.sleep(1)
                                os.execl(sys.executable, sys.executable, *sys.argv)
                            else:
                                await event.edit(f'✅ У вас актуальная версия {kernel.VERSION}')
                        else:
                            await event.edit('❌ Не удалось проверить версию')
                    else:
                        await event.edit('❌ Не удалось получить обновление')
        except Exception as e:
            await event.edit(f'❌ Ошибка: {str(e)}')
    
    @kernel.register_command('stop')
    async def stop_handler(event):
        kernel.shutdown_flag = True
        await event.edit('⛔ Остановка юзербота...')
        await asyncio.sleep(1)
        await client.disconnect()
    
    @kernel.register_command('rollback')
    async def rollback_handler(event):
        if not os.path.exists(kernel.BACKUP_FILE):
            await event.edit('❌ Бэкап не найден')
            return
        
        await event.edit('🔄 Откат к предыдущей версии...')
        
        try:
            with open(kernel.BACKUP_FILE, 'r', encoding='utf-8') as f:
                backup_code = f.read()
            
            with open(__file__, 'w', encoding='utf-8') as f:
                f.write(backup_code)
            
            await event.edit('✅ Откат завершен\nПерезагрузка...')
            await asyncio.sleep(1)
            os.execl(sys.executable, sys.executable, *sys.argv)
        except Exception as e:
            await event.edit(f'❌ Ошибка отката: {str(e)}')