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

    async def restart_cmd(event):
        emoji = random.choice(emojis)
        msg = await event.edit(f'🔭 <i>Твой</i> <b>MCUB</b> перезагружается...', parse_mode='html')
        with open(kernel.RESTART_FILE, 'w') as f:
            f.write(f'{event.chat_id},{msg.id},{time.time()}')
        os.execl(sys.executable, sys.executable, *sys.argv)

    async def update_cmd(event):
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

    @kernel.register_command('restart')
    async def restart_handler(event):
        args = event.text.split()

        if '-f' in args:
            await restart_cmd(event)
            return

        try:
            await event.delete()

            if not kernel.config.get('inline_bot_username'):
                error_msg = await event.respond("❌ Инлайн-бот не настроен")
                await asyncio.sleep(5)
                await error_msg.delete()
                return

            await kernel.send_inline(event.chat_id, "restart_confirm")

        except Exception as e:
            await kernel.handle_error(e, source="restart_command", event=event)
            try:
                error_msg = await event.respond("🌩️ Ошибка, смотри логи")
                await asyncio.sleep(5)
                await error_msg.delete()
            except:
                pass

    @kernel.register_command('update')
    async def update_handler(event):
        args = event.text.split()

        if '-f' in args:
            await update_cmd(event)
            return

        try:
            await event.delete()

            if not kernel.config.get('inline_bot_username'):
                error_msg = await event.respond("❌ Инлайн-бот не настроен")
                await asyncio.sleep(5)
                await error_msg.delete()
                return

            await kernel.send_inline(event.chat_id, "update_confirm")

        except Exception as e:
            await kernel.handle_error(e, source="update_command", event=event)
            try:
                error_msg = await event.respond("🌩️ Ошибка, смотри логи")
                await asyncio.sleep(5)
                await error_msg.delete()
            except:
                pass

    @kernel.register_command('stop')
    async def stop_handler(event):
        kernel.shutdown_flag = True
        emoji = random.choice(emojis)
        await event.edit(f'🧲 <b>Твой <i>MCUB</i> останавливается...</b> {emoji}', parse_mode='html')
        await asyncio.sleep(1)
        await client.disconnect()

    @kernel.register_command('rollback')
    async def rollback_handler(event):
        if not os.path.exists(kernel.BACKUP_FILE):
            await event.edit('❌ <b>Бэкап не найден</b>', parse_mode='html')
            return

        msg = await event.edit('🔙 <b>Откатываю к предыдущей версии...</b>', parse_mode='html')

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

    async def inline_restart_handler(event):
        try:
            builder = event.builder.article(
                title='Restart Confirmation',
                description='Подтверждение перезагрузки юзербота',
                text='💠 <i>Перезагрузится?</i>',
                buttons=[
                    [Button.inline('Перезагрузить 🔮', b'updates_restart_yes')]
                ],
                parse_mode='html'
            )
            await event.answer([builder])

        except Exception as e:
            await kernel.handle_error(e, source="inline_restart_handler", event=event)
            builder = event.builder.article(
                'Error',
                text="🌩️ Ошибка при загрузке подтверждения"
            )
            await event.answer([builder])

    async def inline_update_handler(event):
        try:
            builder = event.builder.article(
                title='Update Confirmation',
                description='Подтверждение обновления юзербота',
                text='📡 <i>Обновиться?</i>',
                buttons=[
                    [Button.inline('Обновить 🧪', b'updates_update_yes')]
                ],
                parse_mode='html'
            )
            await event.answer([builder])

        except Exception as e:
            await kernel.handle_error(e, source="inline_update_handler", event=event)
            builder = event.builder.article(
                'Error',
                text="🌩️ Ошибка при загрузке подтверждения"
            )
            await event.answer([builder])

    async def callback_updates_handler(event):
        try:
            data = event.data.decode()

            if data == 'updates_restart_yes':
                message = await event.get_message()
                if not message:
                    await event.answer('❌ Сообщение не найдено')
                    return

                chat = await message.get_chat()
                is_private = hasattr(chat, 'first_name')

                if is_private:
                    if event.sender_id != chat.id:
                        await event.answer('❌ Это не ваше сообщение')
                        return
                else:
                    if not hasattr(chat, 'admin_rights') and not hasattr(chat, 'creator'):
                        await event.answer('❌ Это не ваше сообщение')
                        return

                await event.answer('🔄 Перезагрузка...')

                try:
                    await event.delete()
                except:
                    pass

                if is_private:
                    chat_id = chat.id
                else:
                    chat_id = message.peer_id.channel_id or message.peer_id.chat_id

                msg = await client.send_message(chat_id, '🔭 <i>Твой</i> <b>MCUB</b> перезагружается...', parse_mode='html')

                with open(kernel.RESTART_FILE, 'w') as f:
                    f.write(f'{msg.chat_id},{msg.id},{time.time()}')
                os.execl(sys.executable, sys.executable, *sys.argv)

            elif data == 'updates_update_yes':
                message = await event.get_message()
                if not message:
                    await event.answer('❌ Сообщение не найдено')
                    return

                chat = await message.get_chat()
                is_private = hasattr(chat, 'first_name')

                if is_private:
                    if event.sender_id != chat.id:
                        await event.answer('❌ Это не ваше сообщение')
                        return
                else:
                    if not hasattr(chat, 'admin_rights') and not hasattr(chat, 'creator'):
                        await event.answer('❌ Это не ваше сообщение')
                        return

                await event.answer('📦 Обновление...')

                try:
                    await event.delete()
                except:
                    pass

                if is_private:
                    chat_id = chat.id
                else:
                    chat_id = message.peer_id.channel_id or message.peer_id.chat_id

                msg = await client.send_message(chat_id, '❄️ <b>обновляюсь...</b>', parse_mode='html')

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

        except Exception as e:
            await kernel.handle_error(e, source="callback_updates_handler", event=event)
            await event.answer("🌩️ Ошибка, смотри логи")

    kernel.register_inline_handler('restart_confirm', inline_restart_handler)
    kernel.register_inline_handler('update_confirm', inline_update_handler)
    kernel.register_callback_handler('updates_', callback_updates_handler)

    kernel.cprint(f'{kernel.Colors.GREEN}✅ Модуль updates загружен (с инлайн-подтверждением){kernel.Colors.RESET}')
