import asyncio
import aiohttp
import json
import re
import getpass
from telethon import TelegramClient, Button

class InlineBot:
    def __init__(self, kernel):
        self.kernel = kernel
        self.bot_client = None
        self.token = None
        self.username = None
        
    async def setup(self):
        self.token = self.kernel.config.get('inline_bot_token')
        self.username = self.kernel.config.get('inline_bot_username')
        
        if not self.token:
            await self.create_bot()
        else:
            await self.start_bot()
            
    async def create_bot(self):
        self.kernel.cprint('=- Настройка инлайн-бота', self.kernel.Colors.CYAN)
        
        choice = input(f'{self.kernel.Colors.YELLOW}1. Автоматически создать бота\n2. Ввести токен вручную\nВыберите (1/2): {self.kernel.Colors.RESET}').strip()
        
        if choice == '1':
            await self.auto_create_bot()
        elif choice == '2':
            await self.manual_setup()
        else:
            self.kernel.cprint('=X Неверный выбор', self.kernel.Colors.RED)
            return
    
    async def auto_create_bot(self):
        try:
            botfather = await self.kernel.client.get_entity('BotFather')
            
            username = input(f'{self.kernel.Colors.YELLOW}Желаемый username для бота (без @): {self.kernel.Colors.RESET}').strip()
            
            if not username:
                self.kernel.cprint('=X Username не может быть пустым', self.kernel.Colors.RED)
                return
            
            await self.kernel.client.send_message(botfather, '/newbot')
            await asyncio.sleep(1)
            
            await self.kernel.client.send_message(botfather, '🪄 MCUB bot')
            await asyncio.sleep(1)
            
            await self.kernel.client.send_message(botfather, username)
            await asyncio.sleep(2)
            
            messages = await self.kernel.client.get_messages(botfather, limit=1)
            
            if messages and 'token' in messages[0].text.lower():
                token_match = re.search(r'(\d+:[A-Za-z0-9_-]+)', messages[0].text)
                username_match = re.search(r'@([A-Za-z0-9_]+bot)', messages[0].text)
                
                if token_match and username_match:
                    self.token = token_match.group(1)
                    self.username = username_match.group(1)
                    
                    # Устанавливаем описание
                    await self.kernel.client.send_message(botfather, '/setdescription')
                    await asyncio.sleep(1)
                    await self.kernel.client.send_message(botfather, f'@{self.username}')
                    await asyncio.sleep(1)
                    await self.kernel.client.send_message(botfather, '🌠 I\'m a bot from MCUB for inline actions. source code https://github.com/hairpin01/MCUB-fork')
                    await asyncio.sleep(1)
                    
                    # Устанавливаем аватарку
                    await self.kernel.client.send_message(botfather, '/setuserpic')
                    await asyncio.sleep(1)
                    await self.kernel.client.send_message(botfather, f'@{self.username}')
                    await asyncio.sleep(1)
                    
                    # Скачиваем и отправляем аватар
                    async with aiohttp.ClientSession() as session:
                        async with session.get('https://x0.at/4WcE.jpg') as resp:
                            if resp.status == 200:
                                avatar_data = await resp.read()
                                with open('bot_avatar.jpg', 'wb') as f:
                                    f.write(avatar_data)
                                await self.kernel.client.send_file(botfather, 'bot_avatar.jpg')
                                import os
                                os.remove('bot_avatar.jpg')
                    await asyncio.sleep(2)
                    
                    # Устанавливаем плейсхолдер инлайн-режима
                    await self.kernel.client.send_message(botfather, '/setinlineplaceholder')
                    await asyncio.sleep(1)
                    await self.kernel.client.send_message(botfather, f'@{self.username}')
                    await asyncio.sleep(1)
                    
                    try:
                        user = getpass.getuser()
                    except:
                        user = 'user'
                    placeholder = f'{user}@MCUB~$ '
                    await self.kernel.client.send_message(botfather, placeholder)
                    await asyncio.sleep(1)
                    
                    
                    await self.kernel.client.send_message(botfather, '/setinline')
                    await asyncio.sleep(1)
                    await self.kernel.client.send_message(botfather, f'@{self.username}')
                    await asyncio.sleep(1)
                    await self.kernel.client.send_message(botfather, 'inline')
                    await asyncio.sleep(1)
                    
                    
                    await self.kernel.client.send_message(botfather, '/setinlinefeedback')
                    await asyncio.sleep(1)
                    await self.kernel.client.send_message(botfather, f'@{self.username}')
                    await asyncio.sleep(1)
                    await self.kernel.client.send_message(botfather, 'Enabled')
                    await asyncio.sleep(1)
                    
                    
                    await self.kernel.client.send_message(botfather, '/setcommands')
                    await asyncio.sleep(1)
                    await self.kernel.client.send_message(botfather, f'@{self.username}')
                    await asyncio.sleep(1)
                    commands_text = "start - Start the bot"
                    await self.kernel.client.send_message(botfather, commands_text)
                    
                    self.kernel.config['inline_bot_token'] = self.token
                    self.kernel.config['inline_bot_username'] = self.username
                    
                    with open(self.kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
                        json.dump(self.kernel.config, f, ensure_ascii=False, indent=2)
                    
                    self.kernel.cprint(f'=> Инлайн-бот создан: @{self.username}', self.kernel.Colors.GREEN)
                    await self.start_bot()
                    
                else:
                    self.kernel.cprint('=X Не удалось получить данные бота', self.kernel.Colors.RED)
            else:
                self.kernel.cprint('=X Не удалось создать бота', self.kernel.Colors.RED)
                
        except Exception as e:
            self.kernel.cprint(f'=X Ошибка создания бота: {str(e)}', self.kernel.Colors.RED)
            import traceback
            traceback.print_exc()
    
    async def manual_setup(self):
        self.kernel.cprint('=- Ручная настройка бота', self.kernel.Colors.YELLOW)
        
        token = input(f'{self.kernel.Colors.YELLOW}Введите токен бота: {self.kernel.Colors.RESET}').strip()
        username = input(f'{self.kernel.Colors.YELLOW}Введите username бота (без @): {self.kernel.Colors.RESET}').strip()
        
        if not token or not username:
            self.kernel.cprint('=X Все поля обязательны', self.kernel.Colors.RED)
            return
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'https://api.telegram.org/bot{token}/getMe') as resp:
                    data = await resp.json()
                    
                    if data.get('ok'):
                        self.token = token
                        self.username = username
                        
                        self.kernel.config['inline_bot_token'] = token
                        self.kernel.config['inline_bot_username'] = username
                        
                        with open(self.kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
                            json.dump(self.kernel.config, f, ensure_ascii=False, indent=2)
                        
                        self.kernel.cprint('=> Бот проверен и сохранен', self.kernel.Colors.GREEN)
                        
                        
                        setup_choice = input(f'{self.kernel.Colors.YELLOW}Настроить бота через BotFather? (y/n): {self.kernel.Colors.RESET}').strip().lower()
                        if setup_choice == 'y':
                            await self.configure_bot_manually()
                        
                        await self.start_bot()
                    else:
                        self.kernel.cprint('=X Неверный токен бота', self.kernel.Colors.RED)
                        
        except Exception as e:
            self.kernel.cprint(f'=X Ошибка проверки токена: {str(e)}', self.kernel.Colors.RED)
    
    async def configure_bot_manually(self):
        """Ручная настройка бота через BotFather"""
        try:
            botfather = await self.kernel.client.get_entity('BotFather')
            
            
            await self.kernel.client.send_message(botfather, '/setname')
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, f'@{self.username}')
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, '🪄 MCUB bot')
            await asyncio.sleep(2)
            
            
            await self.kernel.client.send_message(botfather, '/setdescription')
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, f'@{self.username}')
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, '🌠 I\'m a bot from MCUB for inline actions. source code https://github.com/hairpin01/MCUB-fork')
            await asyncio.sleep(2)
            
            
            await self.kernel.client.send_message(botfather, '/setuserpic')
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, f'@{self.username}')
            await asyncio.sleep(1)
            
            async with aiohttp.ClientSession() as session:
                async with session.get('https://x0.at/4WcE.jpg') as resp:
                    if resp.status == 200:
                        avatar_data = await resp.read()
                        with open('bot_avatar_manual.jpg', 'wb') as f:
                            f.write(avatar_data)
                        await self.kernel.client.send_file(botfather, 'bot_avatar_manual.jpg')
                        import os
                        os.remove('bot_avatar_manual.jpg')
            await asyncio.sleep(2)
            
            
            await self.kernel.client.send_message(botfather, '/setinlineplaceholder')
            await asyncio.sleep(1)
            await self.kernel.client.send_message(botfather, f'@{self.username}')
            await asyncio.sleep(1)
            try:
                user = getpass.getuser()
            except:
                user = 'user'
            placeholder = f'{user}@MCUB~$ '
            await self.kernel.client.send_message(botfather, placeholder)
            await asyncio.sleep(2)
            
            self.kernel.cprint('=> Бот настроен через BotFather', self.kernel.Colors.GREEN)
            
        except Exception as e:
            self.kernel.cprint(f'=X Ошибка настройки бота: {str(e)}', self.kernel.Colors.YELLOW)
    
    async def start_bot(self):
        if not self.token:
            return
        
        try:
            self.bot_client = TelegramClient('inline_bot_session', 
                                           self.kernel.API_ID, 
                                           self.kernel.API_HASH)
            
            await self.bot_client.start(bot_token=self.token)
            
            # Регистрируем обработчики инлайн-запросов
            from .handlers import InlineHandlers
            handlers = InlineHandlers(self.kernel, self.bot_client)
            await handlers.register_handlers()
            
            # Регистрируем команды бота
            from .command import setup_bot_commands
            setup_bot_commands(self.bot_client, self.kernel)
            
            self.kernel.cprint(f'=> Инлайн-бот запущен @{self.username}', self.kernel.Colors.GREEN)
            
            # Проверяем, нужно ли отправить приветствие
            hello_bot = await self.kernel.db_get('kernel', 'HELLO_BOT')
            if hello_bot == 'True':
                # Отправляем /init от имени клиента
                await self.kernel.client.send_message(self.username, '/init')
            
            
            asyncio.create_task(self.bot_client.run_until_disconnected())
            
        except Exception as e:
            self.kernel.cprint(f'=X Ошибка запуска инлайн-бота: {str(e)}', self.kernel.Colors.RED)
            import traceback
            traceback.print_exc()
    
    async def stop_bot(self):
        if self.bot_client and self.bot_client.is_connected():
            await self.bot_client.disconnect()