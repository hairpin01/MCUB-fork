# core/kernel.py
import asyncio
import time
import sys
import os
import importlib.util
import re
import psutil
import aiohttp
import json
import subprocess
import inspect
from telethon import TelegramClient, events, Button
import socks

class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'

class Kernel:
    def __init__(self):
        self.VERSION = '2.0.0'
        self.DB_VERSION = 2
        self.start_time = time.time()
        self.loaded_modules = {}
        self.system_modules = {}
        self.command_handlers = {}
        self.custom_prefix = '.'
        self.aliases = {}
        self.config = {}
        self.client = None
        self.inline_bot = None
        self.catalog_cache = {}
        self.pending_confirmations = {}
        self.shutdown_flag = False
        self.power_save_mode = False
        
        self.MODULES_DIR = 'modules'
        self.MODULES_LOADED_DIR = 'modules_loaded'
        self.IMG_DIR = 'img'
        self.LOGS_DIR = 'logs'
        self.CONFIG_FILE = 'config.json'
        self.BACKUP_FILE = 'userbot.py.backup'
        self.ERROR_FILE = 'crash.tmp'
        self.RESTART_FILE = 'restart.tmp'
        self.MODULES_REPO = 'https://raw.githubusercontent.com/Mitrichdfklwhcluio/MCUBFB/main/modules_catalog'
        self.UPDATE_REPO = 'https://raw.githubusercontent.com/Mitrichdfklwhcluio/MCUBFB/main/'
        
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 10
        
        self.setup_directories()
        self.load_config()
    
    def setup_directories(self):
        for directory in [self.MODULES_DIR, self.MODULES_LOADED_DIR, self.IMG_DIR, self.LOGS_DIR]:
            if not os.path.exists(directory):
                os.makedirs(directory)
    
    def load_config(self):
        if not os.path.exists(self.CONFIG_FILE):
            print(f'{Colors.RED}Файл config.json не найден{Colors.RESET}')
            print('Скопируйте config.example.json в config.json и заполните данные')
            sys.exit(1)
        
        with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.custom_prefix = self.config.get('command_prefix', '.')
        self.aliases = self.config.get('aliases', {})
        self.power_save_mode = self.config.get('power_save_mode', False)
        
        try:
            self.API_ID = int(self.config['api_id'])
            self.API_HASH = str(self.config['api_hash'])
            self.PHONE = str(self.config['phone'])
        except (KeyError, ValueError) as e:
            print(f'{Colors.RED}Ошибка в config.json: {e}{Colors.RESET}')
            sys.exit(1)
    
    def cprint(self, text, color=''):
        print(f'{color}{text}{Colors.RESET}')
    
    async def init_client(self):
        proxy = self.config.get('proxy')
        self.client = TelegramClient('user_session', self.API_ID, self.API_HASH, proxy=proxy)
        
        try:
            await self.client.start(phone=self.PHONE)
            self.cprint(f'{Colors.GREEN}✅ MCUB ядро запущено{Colors.RESET}')
            return True
        except Exception as e:
            self.cprint(f'{Colors.RED}❌ Ошибка авторизации: {e}{Colors.RESET}')
            return False
    
    def register_command(self, pattern, func):
        """Регистрация команды в ядре"""
        cmd = pattern.lstrip('^\\' + self.custom_prefix)
        if cmd.endswith('$'):
            cmd = cmd[:-1]
        self.command_handlers[cmd] = func
    
    async def load_system_modules(self):
        """Загрузка системных модулей из modules/"""
        for file_name in os.listdir(self.MODULES_DIR):
            if file_name.endswith('.py'):
                try:
                    module_name = file_name[:-3]
                    file_path = os.path.join(self.MODULES_DIR, file_name)
                    
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    module = importlib.util.module_from_spec(spec)
                    
                    module.kernel = self
                    module.client = self.client
                    module.custom_prefix = self.custom_prefix
                    
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, 'register'):
                        module.register(self)
                        self.system_modules[module_name] = module
                        self.cprint(f'{Colors.GREEN}✅ Загружен системный модуль: {module_name}{Colors.RESET}')
                    
                except Exception as e:
                    self.cprint(f'{Colors.RED}❌ Ошибка загрузки модуля {file_name}: {e}{Colors.RESET}')
    
    async def load_user_modules(self):
        """Загрузка пользовательских модулей из modules_loaded/"""
        for file_name in os.listdir(self.MODULES_LOADED_DIR):
            if file_name.endswith('.py'):
                try:
                    module_name = file_name[:-3]
                    file_path = os.path.join(self.MODULES_LOADED_DIR, file_name)
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                    
                    if 'from .. import' in code or 'import loader' in code:
                        self.cprint(f'{Colors.YELLOW}⚠️ Пропущен несовместимый модуль: {file_name}{Colors.RESET}')
                        continue
                    
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    module = importlib.util.module_from_spec(spec)
                    
                    module.kernel = self
                    module.client = self.client
                    module.custom_prefix = self.custom_prefix
                    
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, 'register'):
                        module.register(self.client)
                        self.loaded_modules[module_name] = module
                        self.cprint(f'{Colors.GREEN}✅ Загружен пользовательский модуль: {module_name}{Colors.RESET}')
                    
                except Exception as e:
                    self.cprint(f'{Colors.RED}❌ Ошибка загрузки модуля {file_name}: {e}{Colors.RESET}')
    
    async def process_command(self, event):
        """Обработка команд через зарегистрированные обработчики"""
        text = event.text
        
        if not text.startswith(self.custom_prefix):
            return False
        
        cmd = text[len(self.custom_prefix):].split()[0] if ' ' in text else text[len(self.custom_prefix):]
        
        if cmd in self.aliases:
            alias_cmd = self.aliases[cmd]
            if alias_cmd in self.command_handlers:
                await self.command_handlers[alias_cmd](event)
                return True
        
        if cmd in self.command_handlers:
            await self.command_handlers[cmd](event)
            return True
        
        return False
    
    async def safe_connect(self):
        while self.reconnect_attempts < self.max_reconnect_attempts:
            if self.shutdown_flag:
                return False
            try:
                if self.client.is_connected():
                    return True
                
                await self.client.connect()
                if await self.client.is_user_authorized():
                    self.reconnect_attempts = 0
                    return True
            except Exception as e:
                self.reconnect_attempts += 1
                await asyncio.sleep(self.reconnect_delay * self.reconnect_attempts)
        
        return False
    
    async def send_inline(self, chat_id, query, buttons=None):
        """Универсальная отправка инлайн-сообщений"""
        bot_username = self.config.get('inline_bot_username')
        if not bot_username:
            return False
        
        try:
            results = await self.client.inline_query(bot_username, query)
            if results:
                if buttons:
                    await results[0].click(chat_id, reply_to=None, buttons=buttons)
                else:
                    await results[0].click(chat_id)
                return True
        except Exception:
            pass
        return False
    
    async def run(self):
        """Запуск ядра"""
        if not await self.init_client():
            return
        
        await self.load_system_modules()
        await self.load_user_modules()
        
        @self.client.on(events.NewMessage(outgoing=True))
        async def message_handler(event):
            await self.process_command(event)
        
        self.cprint(f'{Colors.CYAN}🚀 Ядро готово к работе{Colors.RESET}')
        await self.client.run_until_disconnected()


# main.py (точка входа)
import asyncio
from core.kernel import Kernel

async def main():
    kernel = Kernel()
    await kernel.run()

if __name__ == '__main__':
    asyncio.run(main())



