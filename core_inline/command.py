# author: @Hairpin00
# version: 1.0.0
# description: Bot command handlers

from telethon import events, Button
import aiohttp
import json

async def setup_bot_commands(bot_client, kernel):
    """Настройка обработчиков команд бота"""

    @bot_client.on(events.NewMessage(pattern='/start', incoming=True))
    async def start_handler(event):
        """Обработчик команды /start для всех пользователей"""
        try:
            await event.reply(
                #file='https://x0.at/z6Uu.jpg',
                message=(
                    '<b>Привет! я бот от MCUB-fork</b>\n'
                    '<blockquote>Developers: \n'
                    'fork: @Hairpin01,\n'
                    'Original: @Mitrichq</blockquote>'
                ),
                parse_mode='html',
                buttons=[
                    [
                        Button.url('🔭 Репозиторий', 'https://github.com/hairpin01/MCUB-fork'),
                        Button.url('🚂 Оригинальный MCUBFB', 'https://github.com/Mitrichdfklwhcluio/MCUBFB')
                    ]
                ]
            )
        except Exception as e:
            kernel.cprint(f'=X Ошибка обработки /start: {e}', kernel.Colors.RED)
    
    @bot_client.on(events.NewMessage(pattern='/init'))
    async def init_handler(event):
        """Обработчик команды /init только для админа"""
        try:
            
            if event.sender_id != kernel.ADMIN_ID:
                return
            
            
            hello_bot = await kernel.db_get('kernel', 'HELLO_BOT')
            
            if hello_bot != 'True':
                
                await start_handler(event)
                return
            
            
            gif_message = await event.respond(
                file='https://x0.at/Y4ie.mp4',
                message='choose a language',
                buttons=[
                    [Button.inline('RU', b'start_lang_ru'),
                     Button.inline('EN', b'start_lang_en')]
                ]
            )
            
            
            await kernel.db_set('kernel', f'lang_select_{event.sender_id}', str(gif_message.id))
            
        except Exception as e:
            kernel.cprint(f'=X Ошибка обработки /init: {e}', kernel.Colors.RED)
            await event.respond('Произошла ошибка при инициализации.')
    
    @bot_client.on(events.CallbackQuery(pattern=r'start_lang_(ru|en)'))
    async def language_handler(event):
        """Обработчик выбора языка"""
        try:
            if event.sender_id != kernel.ADMIN_ID:
                await event.answer('Эта кнопка только для администратора.', alert=True)
                return
            
            lang = event.pattern_match.group(1).decode() if isinstance(event.pattern_match.group(1), bytes) else event.pattern_match.group(1)
            

            await kernel.db_set('kernel', 'language', lang)
            

            msg_id_key = f'lang_select_{event.sender_id}'
            msg_id = await kernel.db_get('kernel', msg_id_key)
            
            
            if lang == 'ru':
                text = (
                    '<b>Привет</b>, я вижу что ты только поставил MCUB\n'
                    '👉 Мини гайд по командам:\n'
                    '<blockquote>\n'
                    '-> .prefix <ваш желаемый префикс командами>\n'
                    '-> .man <модуль/без аргументов список модулей> \n'
                    '-> .im <реплай> – загрузить модуль\n'
                    '-> .um <модуль> – удалить модуль\n'
                    '-> .dlm <флаги: -s – скачать модуль и выгрузить, -list – список всех модулей. ссылка на модуль или название модуля из репозитория>\n'
                    '</blockquote>\n'
                    '<i>Note: смотрите все команды и модули с помощью .man</i>'
                )
            else:
                text = (
                    '<b>Hello</b>, I see you just installed MCUB\n'
                    '👉 Quick guide to commands:\n'
                    '<blockquote>\n'
                    '-> .prefix <your desired command prefix>\n'
                    '-> .man <module/without arguments list of modules> \n'
                    '-> .im <reply> – load a module\n'
                    '-> .um <module> – unload a module\n'
                    '-> .dlm <flags: -s – download and unload module, -list – list all modules. link to module or module name from repository>\n'
                    '</blockquote>\n'
                    '<i>Note: see all commands and modules with .man</i>'
                )
            
            
            buttons = [
                [Button.url('MCUB', 'https://github.com/hairpin01/MCUB-fork'),
                 Button.url('Modules repo', 'https://github.com/hairpin01/repo-MCUB-fork')]
            ]
            
            
            if msg_id:
                try:
                    await event.client.edit_message(
                        await event.client.get_input_entity(event.chat_id),
                        int(msg_id),
                        text,
                        buttons=buttons,
                        file=None,  
                        parse_mode='html'
                    )
                except:
                    
                    await event.respond(text, buttons=buttons, parse_mode='html')
            else:
                await event.respond(text, buttons=buttons, parse_mode='html')
            
            
            await kernel.db_set('kernel', 'HELLO_BOT', 'False')
            
            
            await kernel.db_delete('kernel', msg_id_key)
            
            await event.answer()
            
        except Exception as e:
            kernel.cprint(f'=X Ошибка обработки выбора языка: {e}', kernel.Colors.RED)
            await event.answer('Произошла ошибка', alert=True)
    
    