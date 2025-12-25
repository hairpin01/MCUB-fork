# author: @Hairpin00
# version: 1.0.4
# description: обновление
import asyncio
import os
import sys
import re
import time
import random
import aiohttp
import subprocess
from telethon import events, Button

def register(kernel):
    client = kernel.client

    emojis = ['ಠ_ಠ', '( ཀ ʖ̯ ཀ)', '(◕‿◕✿)', '(つ･･)つ', '༼つ◕_◕༽つ', '(•_•)', '☜(ﾟヮﾟ☜)', '(☞ﾟヮﾟ)☞', 'ʕ•ᴥ•ʔ', '(づ￣ ³￣)づ']

    @kernel.register_command('restart')
    # рестар
    async def restart_handler(event):
        emoji = random.choice(emojis)
        msg = await event.edit(f'🔭 <i>Твой</i> <b>MCUB</b> перезагружается...', parse_mode='html')
        with open(kernel.RESTART_FILE, 'w') as f:
            f.write(f'{event.chat_id},{msg.id},{time.time()}')
        os.execl(sys.executable, sys.executable, *sys.argv)

    @kernel.register_command('update')
    # обновить userbot
    async def update_handler(event):
        msg = await event.edit('❄️')

        try:

            try:
                await msg.edit('❄️ <b>обновляюсь...</b>', parse_mode='html')
                result = subprocess.run(
                    ['git', 'pull', 'origin', 'main'],
                    capture_output=True,
                    text=True,
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )

                if result.returncode == 0:
                    if 'Already up to date' in result.stdout:
                        await msg.edit(f'✅ <b>Уже последняя версия {kernel.VERSION}</b>', parse_mode='html')
                        return

                    await msg.edit(f'📝 <b>Git pull успешен!</b>\n\n<code>{result.stdout[:200]}</code>', parse_mode='html')
                    await asyncio.sleep(2)

                    emoji = random.choice(emojis)
                    await msg.edit(f'⚗️ <b>Обновление успешно!</b> {emoji}\n\nПерезагрузка через 2 секунды...', parse_mode='html')
                    await asyncio.sleep(2)
                    os.execl(sys.executable, sys.executable, *sys.argv)
                    return

            except Exception as git_error:
                pass


            await msg.edit('🔧 <b>пробую другой метод обновления...</b>', parse_mode='html')

            UPDATE_REPO = 'https://raw.githubusercontent.com/hairpin01/MCUB-fork/main'

            async with aiohttp.ClientSession() as session:
                async with session.get(f'{UPDATE_REPO}/core/kernel.py') as resp:
                    if resp.status == 200:
                        new_code = await resp.text()

                        if 'VERSION' in new_code:
                            new_version = re.search(r"VERSION = '([^']+)'", new_code)
                            if new_version and new_version.group(1) != kernel.VERSION:
                                emoji = random.choice(emojis)
                                await msg.edit(f'📥 <b>Обновляю до {new_version.group(1)}...</b> {emoji}', parse_mode='html')

                                with open(__file__, 'r', encoding='utf-8') as f:
                                    current_code = f.read()
                                with open(kernel.BACKUP_FILE, 'w', encoding='utf-8') as f:
                                    f.write(current_code)

                                with open(__file__, 'w', encoding='utf-8') as f:
                                    f.write(new_code)

                                emoji = random.choice(emojis)
                                await msg.edit(f'⚗️ <b>Обновление успешно!</b> {emoji}\n\n📦 Бэкап создан\nПерезагрузка...', parse_mode='html')
                                await asyncio.sleep(2)
                                os.execl(sys.executable, sys.executable, *sys.argv)
                            else:
                                await msg.edit(f'✅ <b>Уже последняя версия {kernel.VERSION}</b>', parse_mode='html')
                        else:
                            await msg.edit('❌ <b>Не удалось проверить версию</b>', parse_mode='html')
                    else:
                        await msg.edit('❌ <b>Не удалось получить обновление</b>', parse_mode='html')

        except Exception as e:
            await msg.edit(f'❌ <b>Ошибка:</b> <code>{str(e)}</code>', parse_mode='html')

    @kernel.register_command('stop')
    # остановить userbot
    async def stop_handler(event):
        kernel.shutdown_flag = True
        emoji = random.choice(emojis)
        await event.edit(f'🧲 <b>Твой <i>MCUB</i> останавливается...</b> {emoji}', parse_mode='html')
        await asyncio.sleep(1)
        await client.disconnect()

    @kernel.register_command('rollback')
    # откатить userbot
    async def rollback_handler(event):
        if not os.path.exists(kernel.BACKUP_FILE):
            await event.edit('❌ <b>Бэкап не найден</b>', parse_mode='html')
            return

        msg = await event.edit('🔙 <b>Откатываю к предыдущей версии...</b> <i>{emojis}</i>', parse_mode='html')

        try:
            with open(kernel.BACKUP_FILE, 'r', encoding='utf-8') as f:
                backup_code = f.read()

            with open(__file__, 'w', encoding='utf-8') as f:
                f.write(backup_code)

            emoji = random.choice(emojis)
            await msg.edit(f'⚗️ <b>Откат завершен!</b> {emoji}\n\nПерезагрузка...', parse_mode='html')
            await asyncio.sleep(2)
            os.execl(sys.executable, sys.executable, *sys.argv)
        except Exception as e:
            await msg.edit(f'❌ <b>Ошибка отката:</b> <code>{str(e)}</code>', parse_mode='html')
