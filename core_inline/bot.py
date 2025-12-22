import asyncio
import aiohttp
import json
import re
from telethon import TelegramClient, Button
from telethon.tl.types import InputBotInlineMessageID, InputBotInlineMessageText

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
        print(f'\n{self.kernel.Colors.CYAN}🤖 Настройка инлайн-бота{self.kernel.Colors.RESET}')
        
        choice = input(f'{self.kernel.Colors.YELLOW}1. Автоматически создать бота\n2. Ввести токен вручную\nВыберите (1/2): {self.kernel.Colors.RESET}').strip()
        
        if choice == '1':
            await self.auto_create_bot()
        elif choice == '2':
            await self.manual_setup()
        else:
            print(f'{self.kernel.Colors.RED}❌ Неверный выбор{self.kernel.Colors.RESET}')
            return
    
    async def auto_create_bot(self):
        try:
            botfather = await self.kernel.client.get_entity('BotFather')
            
            username = input(f'{self.kernel.Colors.YELLOW}Желаемый username для бота (без @): {self.kernel.Colors.RESET}').strip()
            
            if not username:
                print(f'{self.kernel.Colors.RED}❌ Username не может быть пустым{self.kernel.Colors.RESET}')
                return
            
            await self.kernel.client.send_message(botfather, '/newbot')
            await asyncio.sleep(1)
            
            await self.kernel.client.send_message(botfather, 'MCUB Inline Bot')
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
                    
                    self.kernel.config['inline_bot_token'] = self.token
                    self.kernel.config['inline_bot_username'] = self.username
                    
                    with open(self.kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
                        json.dump(self.kernel.config, f, ensure_ascii=False, indent=2)
                    
                    print(f'{self.kernel.Colors.GREEN}✅ Инлайн-бот создан: @{self.username}{self.kernel.Colors.RESET}')
                    await self.start_bot()
                else:
                    print(f'{self.kernel.Colors.RED}❌ Не удалось получить данные бота{self.kernel.Colors.RESET}')
            else:
                print(f'{self.kernel.Colors.RED}❌ Не удалось создать бота{self.kernel.Colors.RESET}')
                
        except Exception as e:
            print(f'{self.kernel.Colors.RED}❌ Ошибка создания бота: {str(e)}{self.kernel.Colors.RESET}')
    
    async def manual_setup(self):
        print(f'\n{self.kernel.Colors.YELLOW}📝 Ручная настройка бота{self.kernel.Colors.RESET}')
        
        token = input(f'{self.kernel.Colors.YELLOW}Введите токен бота: {self.kernel.Colors.RESET}').strip()
        username = input(f'{self.kernel.Colors.YELLOW}Введите username бота (без @): {self.kernel.Colors.RESET}').strip()
        
        if not token or not username:
            print(f'{self.kernel.Colors.RED}❌ Все поля обязательны{self.kernel.Colors.RESET}')
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
                        
                        print(f'{self.kernel.Colors.GREEN}✅ Бот проверен и сохранен{self.kernel.Colors.RESET}')
                        await self.start_bot()
                    else:
                        print(f'{self.kernel.Colors.RED}❌ Неверный токен бота{self.kernel.Colors.RESET}')
                        
        except Exception as e:
            print(f'{self.kernel.Colors.RED}❌ Ошибка проверки токена: {str(e)}{self.kernel.Colors.RESET}')
    
    async def start_bot(self):
        if not self.token:
            return
        
        try:
            self.bot_client = TelegramClient('inline_bot_session', 
                                           self.kernel.API_ID, 
                                           self.kernel.API_HASH)
            
            await self.bot_client.start(bot_token=self.token)
            
            from .handlers import InlineHandlers
            handlers = InlineHandlers(self.kernel, self.bot_client)
            await handlers.register_handlers()
            
            print(f'{self.kernel.Colors.GREEN}✅ Инлайн-бот запущен @{self.username}{self.kernel.Colors.RESET}')
            asyncio.create_task(self.bot_client.run_until_disconnected())
            
        except Exception as e:
            print(f'{self.kernel.Colors.RED}❌ Ошибка запуска инлайн-бота: {str(e)}{self.kernel.Colors.RESET}')
    
    async def stop_bot(self):
        if self.bot_client and self.bot_client.is_connected():
            await self.bot_client.disconnect()
