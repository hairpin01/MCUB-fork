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
import socks
from telethon import TelegramClient, events, Button
from telethon.errors import SessionPasswordNeededError

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
        self.VERSION = '1.0.1'
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
        self.load_or_create_config()
    
    def setup_directories(self):
        for directory in [self.MODULES_DIR, self.MODULES_LOADED_DIR, self.IMG_DIR, self.LOGS_DIR]:
            if not os.path.exists(directory):
                os.makedirs(directory)
    
    def load_or_create_config(self):
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            required_fields = ['api_id', 'api_hash', 'phone']
            if all(field in self.config and self.config[field] for field in required_fields):
                self.setup_config()
                return True
            else:
                print(f'{Colors.RED}❌ Конфиг поврежден или неполный{Colors.RESET}')
                return False
        else:
            return False
    
    def setup_config(self):
        try:
            self.custom_prefix = self.config.get('command_prefix', '.')
            self.aliases = self.config.get('aliases', {})
            self.power_save_mode = self.config.get('power_save_mode', False)
            self.API_ID = int(self.config['api_id'])
            self.API_HASH = str(self.config['api_hash'])
            self.PHONE = str(self.config['phone'])
            return True
        except (KeyError, ValueError, TypeError) as e:
            print(f'{Colors.RED}❌ Ошибка в конфиге: {e}{Colors.RESET}')
            return False
    
    async def first_time_setup(self):
        print(f'\n{Colors.CYAN}⚙️  Первоначальная настройка юзербота{Colors.RESET}\n')
        
        while True:
            try:
                api_id_input = input(f'{Colors.YELLOW}📝 Введите API ID: {Colors.RESET}').strip()
                if not api_id_input.isdigit():
                    print(f'{Colors.RED}❌ API ID должен быть числом{Colors.RESET}')
                    continue
                
                api_hash_input = input(f'{Colors.YELLOW}📝 Введите API HASH: {Colors.RESET}').strip()
                if not api_hash_input:
                    print(f'{Colors.RED}❌ API HASH не может быть пустым{Colors.RESET}')
                    continue
                
                phone_input = input(f'{Colors.YELLOW}📝 Введите номер телефона (формат: +1234567890): {Colors.RESET}').strip()
                if not phone_input.startswith('+'):
                    print(f'{Colors.RED}❌ Номер должен начинаться с +{Colors.RESET}')
                    continue
                
                print(f'\n{Colors.YELLOW}🔄 Проверка данных...{Colors.RESET}')
                
                try:
                    api_id = int(api_id_input)
                except ValueError:
                    print(f'{Colors.RED}❌ API ID должен быть числом{Colors.RESET}')
                    continue
                
                proxy = self.config.get('proxy')
                test_client = TelegramClient('temp_session', api_id, api_hash_input, proxy=proxy)
                
                try:
                    await test_client.connect()
                    
                    if not await test_client.is_user_authorized():
                        print(f'{Colors.YELLOW}📱 Отправка кода на {phone_input}...{Colors.RESET}')
                        
                        sent_code = await test_client.send_code_request(phone_input)
                        code_type = sent_code.type
                        
                        if code_type == 'app':
                            print(f'{Colors.YELLOW}📲 Введите код из приложения Telegram{Colors.RESET}')
                        elif code_type == 'sms':
                            print(f'{Colors.YELLOW}📱 Введите код из SMS{Colors.RESET}')
                        elif code_type == 'call':
                            print(f'{Colors.YELLOW}📞 Введите код из звонка{Colors.RESET}')
                        else:
                            print(f'{Colors.YELLOW}🔑 Введите код{Colors.RESET}')
                        
                        code = input(f'{Colors.YELLOW}🔢 Код: {Colors.RESET}').strip()
                        
                        try:
                            await test_client.sign_in(phone_input, code, phone_code_hash=sent_code.phone_code_hash)
                            print(f'{Colors.GREEN}✅ Первый этап авторизации пройден{Colors.RESET}')
                        except SessionPasswordNeededError:
                            print(f'{Colors.YELLOW}🔐 Требуется пароль двухфакторной аутентификации{Colors.RESET}')
                            password = input(f'{Colors.YELLOW}🔒 Пароль 2FA: {Colors.RESET}').strip()
                            await test_client.sign_in(password=password)
                        
                        if await test_client.is_user_authorized():
                            print(f'{Colors.GREEN}✅ Авторизация успешна{Colors.RESET}')
                        else:
                            print(f'{Colors.RED}❌ Авторизация не удалась{Colors.RESET}')
                            continue
                    
                    me = await test_client.get_me()
                    print(f'{Colors.GREEN}✅ Успешно! Пользователь: {me.first_name}{Colors.RESET}')
                    
                    await test_client.disconnect()
                    
                    self.config = {
                        "api_id": api_id,
                        "api_hash": api_hash_input,
                        "phone": phone_input,
                        "command_prefix": ".",
                        "aliases": {},
                        "power_save_mode": False,
                        "2fa_enabled": False,
                        "healthcheck_interval": 30,
                        "developer_chat_id": None,
                        "language": "ru",
                        "theme": "default",
                        "proxy": None,
                        "inline_bot_token": None,
                        "inline_bot_username": None,
                        "db_version": self.DB_VERSION
                    }
                    
                    with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                        json.dump(self.config, f, ensure_ascii=False, indent=2)
                    
                    self.setup_config()
                    print(f'{Colors.GREEN}✅ Конфиг сохранен{Colors.RESET}')
                    return True
                    
                except Exception as e:
                    print(f'{Colors.RED}❌ Ошибка проверки: {str(e)}{Colors.RESET}')
                    continue
                    
            except KeyboardInterrupt:
                print(f'\n{Colors.RED}❌ Настройка прервана{Colors.RESET}')
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
        cmd = pattern.lstrip('^\\' + self.custom_prefix)
        if cmd.endswith('$'):
            cmd = cmd[:-1]
        self.command_handlers[cmd] = func
    
    async def load_system_modules(self):
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
        if not self.load_or_create_config():
            if not await self.first_time_setup():
                self.cprint(f'{Colors.RED}❌ Не удалось настроить юзербот{Colors.RESET}')
                return
        
        if not await self.init_client():
            return
        
        await self.load_system_modules()
        await self.load_user_modules()
        
        @self.client.on(events.NewMessage(outgoing=True))
        async def message_handler(event):
            await self.process_command(event)
        
        self.cprint(f'{Colors.CYAN}🚀 Ядро готово к работе{Colors.RESET}')
        await self.client.run_until_disconnected()