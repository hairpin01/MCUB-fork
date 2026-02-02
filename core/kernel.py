# author: @Hairpin00
# version: 1.0.1.9.5
# description: kernel core
# Спасибо @Mitrichq за основу юзербота
# Лицензия? какая лицензия ещё

try:
    from utils.html_parser import parse_html
    from utils.message_helpers import edit_with_html, reply_with_html, send_with_html, send_file_with_html
    HTML_PARSER_AVAILABLE = True
except ImportError as e:
    print(f"=X HTML парсер не загружен: {e}")
    HTML_PARSER_AVAILABLE = False

try:
    from utils.raw_html import RawHTMLConverter
except Exception as e:
    print(e)


try:
    import time
    import sys
    import os
    import importlib.util
    import re
    import json
    import subprocess
    import random
    from pathlib import Path
    import logging
    from logging.handlers import RotatingFileHandler
    import aiosqlite
    from contextlib import asynccontextmanager
    import io
    import html
    import socks
    import traceback
    import psutil
    import aiohttp
    import asyncio
    import aiosqlite
    from collections import OrderedDict
    from datetime import datetime, timedelta
    from telethon import TelegramClient, events, Button
    from telethon.errors import SessionPasswordNeededError
except ImportError as e:
    print(
        "Установите зависимости",
        "pip install -r requirements.txt\n",
        f"{e}"
        )
    import sys
    sys.exit(1)

class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'


class CommandConflictError(Exception):
    """Исключение для конфликта команд"""
    def __init__(self, message, conflict_type=None, command=None):
        super().__init__(message)
        self.conflict_type = conflict_type
        self.command = command


class TTLCache:
    def __init__(self, max_size=1000, ttl=300):
        from collections import OrderedDict
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl

    def set(self, key, value, ttl=None):
        from collections import OrderedDict
        expire_time = time.time() + (ttl if ttl is not None else self.ttl)
        self.cache[key] = (expire_time, value)
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def get(self, key):
        if key in self.cache:
            expire_time, value = self.cache[key]
            if time.time() < expire_time:
                return value
            else:
                del self.cache[key]
        return None

    def clear(self):
        self.cache.clear()

    def size(self):
        return len(self.cache)


class TaskScheduler:
    def __init__(self, kernel):
        self.kernel = kernel
        self.tasks = []
        self.running = False

    async def add_interval_task(self, func, interval_seconds):
        async def wrapper():
            while True:
                await asyncio.sleep(interval_seconds)
                try:
                    await func()
                except Exception as e:
                    self.kernel.log_error(f"Task error: {e}")

        task = asyncio.create_task(wrapper())
        self.tasks.append(task)

    async def add_daily_task(self, func, hour, minute):
        async def wrapper():
            while True:
                now = datetime.now()
                target = now.replace(hour=hour, minute=minute, second=0)
                if now > target:
                    target += timedelta(days=1)

                delay = (target - now).total_seconds()
                await asyncio.sleep(delay)
                await func()

        task = asyncio.create_task(wrapper())
        self.tasks.append(task)


class Register:

    def __init__(self, kernel):
        self.kernel = kernel
        self._methods = {}

    def method(self, func=None):
        if func is None:
            return lambda f: self.method(f)

        import inspect
        module = inspect.getmodule(inspect.stack()[1][0])
        if module:
            if not hasattr(module, 'register'):
                module.register = type('RegisterObject', (), {})()
            module.register.method = func

        return func

    def event(self, event_type, *args, **kwargs):
        # newmessage, messageedited, userupdat, chatupload, inlinequery, callbackquery, raw
        def decorator(handler):
            from telethon import events

            event_class = None
            pattern = None

            if event_type.lower() in ['newmessage', 'message']:
                event_class = events.NewMessage
            elif event_type.lower() in ['messageedited', 'edited']:
                event_class = events.MessageEdited
            elif event_type.lower() in ['messagedeleted', 'deleted']:
                event_class = events.MessageDeleted
            elif event_type.lower() in ['userupdate', 'user']:
                event_class = events.UserUpdate
            elif event_type.lower() in ['chatupload', 'upload']:
                event_class = events.ChatUpload
            elif event_type.lower() in ['inlinequery', 'inline']:
                event_class = events.InlineQuery
            elif event_type.lower() in ['callbackquery', 'callback']:
                event_class = events.CallbackQuery
            elif event_type.lower() in ['raw', 'custom']:
                event_class = events.Raw

            if event_class:
                self.kernel.client.add_event_handler(handler, event_class(*args, **kwargs))

            return handler

        return decorator

    def command(self, pattern, **kwargs):
        # new register command
        def decorator(func):
            cmd = pattern.lstrip('^\\' + self.kernel.custom_prefix)
            if cmd.endswith('$'):
                cmd = cmd[:-1]

            if self.kernel.current_loading_module is None:
                raise ValueError("не установлен текущий модуль для регистрации команд")

            self.kernel.command_handlers[cmd] = func
            self.kernel.command_owners[cmd] = self.kernel.current_loading_module

            # alias: @kernel.register.command('GetRawText', alias='grt', more=more)
            alias = kwargs.get('alias')
            if alias:
                if isinstance(alias, str):
                    self.kernel.aliases[alias] = cmd
                elif isinstance(alias, list):
                    for a in alias:
                        self.kernel.aliases[a] = cmd

            return func

        return decorator

    def bot_command(self, pattern, **kwargs):
        def decorator(func):
            if not pattern.startswith('/'):
                pattern = '/' + pattern # /{command}

            cmd = pattern.lstrip('/').split()[0] if ' ' in pattern else pattern.lstrip('/')

            if self.kernel.current_loading_module is None:
                raise ValueError("не установлен текущий модуль для регистрации бот-команд")

            self.kernel.bot_command_handlers[cmd] = (pattern, func)
            self.kernel.bot_command_owners[cmd] = self.kernel.current_loading_module

            return func

        return decorator

class CallbackPermissionManager:
    def __init__(self):
        # {user_id: {pattern: expiry_time}}
        self.permissions = {}

    def _to_str(self, val):

        if isinstance(val, bytes):
            return val.decode('utf-8')
        return str(val)

    def allow(self, user_id, pattern, duration_seconds=60):
        pattern = self._to_str(pattern)

        expiry = time.time() + duration_seconds
        if user_id not in self.permissions:
            self.permissions[user_id] = {}
        self.permissions[user_id][pattern] = expiry

    def is_allowed(self, user_id, pattern):
        pattern = self._to_str(pattern)
        current_time = time.time()

        if user_id in self.permissions and pattern in self.permissions[user_id]:
            if self.permissions[user_id][pattern] > current_time:
                return True
            else:
                self.prohibit(user_id, pattern) # Срок истёк
        return False

    def prohibit(self, user_id, pattern=None):
        if user_id not in self.permissions: return
        if pattern:
            pattern = self._to_str(pattern)
            if pattern in self.permissions[user_id]:
                del self.permissions[user_id][pattern]
            if not self.permissions[user_id]:
                del self.permissions[user_id]
        else:
            del self.permissions[user_id]

    def cleanup(self):
        current_time = time.time()

        for user_id in list(self.permissions.keys()):
            user_patterns = self.permissions[user_id]

            for pattern in list(user_patterns.keys()):
                if user_patterns[pattern] <= current_time:
                    del user_patterns[pattern]

            if not user_patterns:
                del self.permissions[user_id]

class Kernel:
    def __init__(self):
        self.VERSION = '1.0.1.9.5'
        self.DB_VERSION = 2
        self.start_time = time.time()
        self.loaded_modules = {}
        self.system_modules = {}
        self.command_handlers = {}
        self.command_owners = {}
        self.custom_prefix = '.' 
        self.aliases = {}
        self.config = {}
        self.client = None
        self.inline_bot = None
        self.catalog_cache = {}
        self.pending_confirmations = {}
        self.shutdown_flag = False
        self.power_save_mode = False
        self.Colors = Colors
        self.db_conn = None
        self.cache = TTLCache(max_size=500, ttl=600)
        self.MODULES_DIR = 'modules'
        self.MODULES_LOADED_DIR = 'modules_loaded'
        self.IMG_DIR = 'img'
        self.LOGS_DIR = 'logs'
        self.CONFIG_FILE = 'config.json'
        self.BACKUP_FILE = 'userbot.py.backup'
        self.ERROR_FILE = 'crash.tmp'
        self.RESTART_FILE = 'restart.tmp'
        self.MODULES_REPO = 'https://raw.githubusercontent.com/hairpin01/repo-MCUB-fork/main/'
        self.UPDATE_REPO = 'https://raw.githubusercontent.com/Mitrichdfklwhcluio/MCUBFB/main/'

        self.register = Register(self)
        self.callback_permissions = CallbackPermissionManager()
        self.inline_handlers = {}
        self.callback_handlers = {}
        self.log_chat_id = None
        self.log_bot_enabled = False

        self.current_loading_module = None
        self.current_loading_module_type = None

        self.load_repositories()
        self.repositories = []
        self.default_repo = self.MODULES_REPO

        self.HTML_PARSER_AVAILABLE = HTML_PARSER_AVAILABLE
        try:
            from utils.emoji_parser import emoji_parser
            self.emoji_parser = emoji_parser
            self.cprint(f'{Colors.GREEN}=> The emoji parser is loaded{Colors.RESET}')

        except ImportError:
            self.emoji_parser = None
            self.cprint(f'{Colors.YELLOW}=X The emoji parser is not loaded{Colors.RESET}')
        if self.HTML_PARSER_AVAILABLE:
            try:
                self.parse_html = parse_html
                self.edit_with_html = lambda event, html, **kwargs: edit_with_html(self, event, html, **kwargs)
                self.reply_with_html = lambda event, html, **kwargs: reply_with_html(self, event, html, **kwargs)
                self.send_with_html = lambda chat_id, html, **kwargs: send_with_html(self, self.client, chat_id, html, **kwargs)
                self.send_file_with_html = lambda chat_id, html, file, **kwargs: send_file_with_html(self, self.client, chat_id, html, file, **kwargs)
                self.cprint(f'{Colors.GREEN}=> HTML парсер загружен{Colors.RESET}')
            except Exception as e:
                self.cprint(f'{Colors.RED}=X Ошибка инициализации HTML парсера: {e}{Colors.RESET}')
                self.HTML_PARSER_AVAILABLE = False

        if not self.HTML_PARSER_AVAILABLE:
            self.parse_html = None
            self.edit_with_html = None
            self.reply_with_html = None
            self.send_with_html = None
            self.send_file_with_html = None
            self.cprint(f'{Colors.YELLOW}=X HTML парсер не загружен{Colors.RESET}')

        self.setup_directories()
        self.load_or_create_config()
        self.logger = self.setup_logging()
        self.middleware_chain = []
        self.scheduler = None
        self.bot_command_handlers = {}
        self.bot_command_owners = {}



    async def init_scheduler(self):
        """Инициализация планировщика задач"""
        class SimpleScheduler:
            def __init__(self, kernel):
                self.kernel = kernel
                self.tasks = []
                self.running = True
                self.task_counter = 0
                self.task_registry = {}  # Реестр задач для управления

            async def add_interval_task(self, func, interval_seconds, task_id=None):
                """Добавление задачи с интервалом"""
                if not self.running:
                    return None

                if task_id is None:
                    task_id = f"task_{self.task_counter}"
                    self.task_counter += 1

                async def wrapper():
                    while self.running and task_id in self.task_registry:
                        await asyncio.sleep(interval_seconds)
                        if not self.running or task_id not in self.task_registry:
                            break
                        try:
                            await func()
                        except Exception as e:
                            self.kernel.log_error(f"Task {task_id} error: {e}")

                task = asyncio.create_task(wrapper())
                self.tasks.append(task)
                self.task_registry[task_id] = {
                    'task': task,
                    'func': func,
                    'interval': interval_seconds,
                    'type': 'interval'
                }
                return task_id

            async def add_daily_task(self, func, hour, minute, task_id=None):
                """Добавление ежедневной задачи"""
                if not self.running:
                    return None

                if task_id is None:
                    task_id = f"daily_{self.task_counter}"
                    self.task_counter += 1

                async def wrapper():
                    while self.running and task_id in self.task_registry:
                        now = datetime.now()
                        target = now.replace(hour=hour, minute=minute, second=0)
                        if now > target:
                            target += timedelta(days=1)

                        delay = (target - now).total_seconds()
                        if delay > 0:
                            await asyncio.sleep(delay)

                        if not self.running or task_id not in self.task_registry:
                            break
                        try:
                            await func()
                        except Exception as e:
                            self.kernel.log_error(f"Task {task_id} error: {e}")

                task = asyncio.create_task(wrapper())
                self.tasks.append(task)
                self.task_registry[task_id] = {
                    'task': task,
                    'func': func,
                    'hour': hour,
                    'minute': minute,
                    'type': 'daily'
                }
                return task_id

            async def add_task(self, func, delay_seconds, task_id=None):
                """Добавление одноразовой задачи"""
                if not self.running:
                    return None

                if task_id is None:
                    task_id = f"once_{self.task_counter}"
                    self.task_counter += 1

                async def wrapper():
                    await asyncio.sleep(delay_seconds)
                    if not self.running or task_id not in self.task_registry:
                        return
                    try:
                        await func()
                    except Exception as e:
                        self.kernel.log_error(f"Task {task_id} error: {e}")
                    finally:
                        self.cancel_task(task_id)

                task = asyncio.create_task(wrapper())
                self.tasks.append(task)
                self.task_registry[task_id] = {
                    'task': task,
                    'func': func,
                    'delay': delay_seconds,
                    'type': 'once'
                }
                return task_id

            def cancel_task(self, task_id):
                """Отмена задачи по ID"""
                if task_id in self.task_registry:
                    task_info = self.task_registry[task_id]
                    task_info['task'].cancel()
                    # Удаляем из списков
                    if task_info['task'] in self.tasks:
                        self.tasks.remove(task_info['task'])
                    del self.task_registry[task_id]
                    return True
                return False

            def cancel_all_tasks(self):
                """Отмена всех задач"""
                self.running = False
                for task_id in list(self.task_registry.keys()):
                    self.cancel_task(task_id)

            def get_tasks(self):
                """Получение списка всех задач"""
                return [
                    {
                        'id': task_id,
                        'type': info['type'],
                        'status': 'running' if info['task'].done() else 'stopped'
                    }
                    for task_id, info in self.task_registry.items()
                ]

        self.scheduler = SimpleScheduler(self)
        self.cprint(f'{self.Colors.GREEN}=> Планировщик инициализирован{self.Colors.RESET}')

    def add_middleware(self, middleware_func):
        self.middleware_chain.append(middleware_func)

    async def process_with_middleware(self, event, handler):
        for middleware in self.middleware_chain:
            result = await middleware(event, handler)
            if result is False:
                return False
        return await handler(event)

    async def get_module_config(self, module_name, default=None):
        config_key = f"module_config_{module_name}"
        config_json = await self.db_get('kernel', config_key)
        if config_json:
            return json.loads(config_json)
        return default or {}

    async def save_module_config(self, module_name, config):
        config_key = f"module_config_{module_name}"
        await self.db_set('kernel', config_key, json.dumps(config))


    async def init_db(self):
        """Инициализация базы данных."""
        import aiosqlite
        try:
            self.db_conn = await aiosqlite.connect('userbot.db')
            await self.create_tables()
            self.cprint(f'{Colors.GREEN}=> База данных инициализирована{Colors.RESET}')
            return True
        except Exception as e:
            self.cprint(f'{Colors.RED}=X Ошибка инициализации БД: {e}{Colors.RESET}')
            return False

    async def create_tables(self):
        """Создание таблиц в БД."""
        await self.db_conn.execute('''
            CREATE TABLE IF NOT EXISTS module_data (
                module TEXT,
                key TEXT,
                value TEXT,
                PRIMARY KEY (module, key)
            )
        ''')
        await self.db_conn.commit()

    async def db_set(self, module, key, value):
        """Store key-value pair for module."""
        if not self.db_conn:
            raise Exception("База данных не инициализирована")

        await self.db_conn.execute(
            'INSERT OR REPLACE INTO module_data VALUES (?, ?, ?)',
            (module, key, str(value))
        )
        await self.db_conn.commit()

    async def db_get(self, module, key):
        """Retrieve value for module."""
        if not self.db_conn:
            raise Exception("База данных не инициализирована")

        cursor = await self.db_conn.execute(
            'SELECT value FROM module_data WHERE module = ? AND key = ?',
            (module, key)
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def db_delete(self, module, key):
        """Delete key from module storage."""
        if not self.db_conn:
            raise Exception("База данных не инициализирована")

        await self.db_conn.execute(
            'DELETE FROM module_data WHERE module = ? AND key = ?',
            (module, key)
        )
        await self.db_conn.commit()

    async def db_query(self, query, parameters):
        """Execute custom SQL query."""
        if not self.db_conn:
            raise Exception("База данных не инициализирована")

        cursor = await self.db_conn.execute(query, parameters)
        rows = await cursor.fetchall()
        return rows


    def setup_logging(self):
        logger = logging.getLogger('kernel')
        logger.setLevel(logging.INFO)

        handler = RotatingFileHandler(
            'logs/kernel.log',
            maxBytes=10*1024*1024,
            backupCount=5
        )
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def log_debug(self, message):
        self.logger.debug(message)

    def log_error(self, message):
        self.logger.error(message)

    def load_repositories(self):
        """Загружает список репозиториев из конфига"""
        self.repositories = self.config.get('repositories', [])

    async def save_repositories(self):
        """Сохраняет список репозиториев в конфиг"""
        self.config['repositories'] = self.repositories
        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def save_config(self):
        """Сохраняет конфигурацию в файл"""
        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def set_loading_module(self, module_name, module_type):
        """Устанавливает текущий загружаемый модуль"""
        self.current_loading_module = module_name
        self.current_loading_module_type = module_type

    def clear_loading_module(self):
        """Очищает информацию о загружаемом модуле"""
        self.current_loading_module = None
        self.current_loading_module_type = None

    def unregister_module_commands(self, module_name):
        """Удаляет все команды модуля"""
        to_remove = []
        for cmd, owner in self.command_owners.items():
            if owner == module_name:
                to_remove.append(cmd)

        for cmd in to_remove:
            del self.command_handlers[cmd]
            del self.command_owners[cmd]

    async def add_repository(self, url):
        """Добавляет новый репозиторий"""
        if url in self.repositories or url == self.default_repo:
            return False, '⛈️ Репозиторий уже существует'

        try:
            modules = await self.get_repo_modules_list(url)
            if modules:
                self.repositories.append(url)
                await self.save_repositories()
                return True, f'🧬 Репозиторий добавлен ({len(modules)} модулей)'
            else:
                return False, '⛈️ Не удалось получить список модулей'
        except:
            return False, '⛈️ Ошибка при проверке репозитория'

    async def remove_repository(self, index):
        """Удаляет репозиторий по индексу"""
        try:
            idx = int(index) - 1
            if 0 <= idx < len(self.repositories):
                removed = self.repositories.pop(idx)
                await self.save_repositories()
                return True, f'🗑️ Репозиторий удален'
            else:
                return False, '⛈️ Неверный индекс'
        except:
            return False, '⛈️ Ошибка удаления'

    async def get_repo_name(self, url):
        """Получает название репозитория из modules.ini"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{url}/name.ini') as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        return content.strip()
        except:
            pass
        return url.split('/')[-2] if '/' in url else url


    async def get_command_description(self, module_name, command):
        if module_name in self.system_modules:
            file_path = f"modules/{module_name}.py"
        elif module_name in self.loaded_modules:
            file_path = f"modules_loaded/{module_name}.py"
        else:
            return '🫨 У команды нету описания'

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
                metadata = await self.get_module_metadata(code)
                return metadata['commands'].get(command, '🫨 У команды нету описания')
        except:
            return '🫨 У команды нету описания'


    def register_command(self, pattern, func=None):
        """Регистрация команды с проверкой конфликтов"""
        cmd = pattern.lstrip('^\\' + self.custom_prefix)
        if cmd.endswith('$'):
            cmd = cmd[:-1]

        if self.current_loading_module is None:
            raise ValueError("Не установлен текущий модуль для регистрации команд")

        if cmd in self.command_handlers:
            existing_owner = self.command_owners.get(cmd)
            if existing_owner in self.system_modules:
                raise CommandConflictError(
                    f"Попытка перезаписать системную команду: {cmd}",
                    conflict_type='system',
                    command=cmd
                )
            else:
                raise CommandConflictError(
                    f"Конфликт команд: {cmd} уже зарегистрирована модулем {existing_owner}",
                    conflict_type='user',
                    command=cmd
                )

        if func:
            self.command_handlers[cmd] = func
            self.command_owners[cmd] = self.current_loading_module
            return func
        else:
            def decorator(f):
                self.command_handlers[cmd] = f
                self.command_owners[cmd] = self.current_loading_module
                return f
            return decorator

    def register_command_bot(self, pattern, func=None):
        """Регистрация команд для бота (начинающихся с /)"""
        if not pattern.startswith('/'):
            pattern = '/' + pattern
        
        # Убираем префикс и параметры для хранения
        cmd = pattern.lstrip('/').split()[0] if ' ' in pattern else pattern.lstrip('/')
        
        if self.current_loading_module is None:
            raise ValueError("Не установлен текущий модуль для регистрации бот-команд")
        
        if cmd in self.bot_command_handlers:
            existing_owner = self.bot_command_owners.get(cmd)
            raise CommandConflictError(
                f"Конфликт бот-команд: {cmd} уже зарегистрирована модулем {existing_owner}",
                conflict_type='bot',
                command=cmd
            )
        
        if func:
            self.bot_command_handlers[cmd] = (pattern, func)
            self.bot_command_owners[cmd] = self.current_loading_module
            return func
        else:
            def decorator(f):
                self.bot_command_handlers[cmd] = (pattern, f)
                self.bot_command_owners[cmd] = self.current_loading_module
                return f
            return decorator
    
    def unregister_module_bot_commands(self, module_name):
        """Удаляет все бот-команды модуля"""
        to_remove = []
        for cmd, owner in self.bot_command_owners.items():
            if owner == module_name:
                to_remove.append(cmd)
        
        for cmd in to_remove:
            del self.bot_command_handlers[cmd]
            del self.bot_command_owners[cmd]
    

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

    def is_bot_available(self):
        """
        Проверяет, доступен ли бот-клиент
        
        Returns:
            bool: True если bot_client существует и авторизован
        """
        return (
            hasattr(self, 'bot_client') and 
            self.bot_client is not None and 
            self.bot_client.is_connected()
        )

    async def inline_query_and_click(self, chat_id, query, bot_username=None,
                                    result_index=0, buttons=None, silent=False,
                                    reply_to=None, **kwargs):
        """
        Выполнение инлайн-запроса и автоматический клик по указанному результату.

        Args:
            chat_id (int): ID чата для отправки
            query (str): Текст инлайн-запроса
            bot_username (str, optional): Username бота для инлайн-запроса
            result_index (int): Индекс результата для клика (по умолчанию 0)
            buttons (list, optional): Дополнительные кнопки в формате словарей
            silent (bool): Отправлять сообщение тихо
            reply_to (int): ID сообщения для ответа
            **kwargs: Дополнительные параметры

        Returns:
            tuple: (success, message) - статус и сообщение

        Example:
            # С кнопками
            success, msg = await kernel.inline_query_and_click(
                chat_id=123456789,
                query='"Привет мир" | [{"text": "Кнопка 1", "type": "callback", "data": "action_1"}]'
            )
        """
        try:

            if not bot_username:
                bot_username = self.config.get('inline_bot_username')
                if not bot_username:
                    raise ValueError("Bot username not specified and not configured in config")

            self.cprint(f'{self.Colors.BLUE}=> Выполняю инлайн-запрос: {query[:100]}... с @{bot_username}{self.Colors.RESET}')


            results = await self.client.inline_query(bot_username, query)

            if not results:
                self.cprint(f'{self.Colors.YELLOW}=? Не найдено инлайн-результатов для запроса: {query[:50]}...{self.Colors.RESET}')
                return False, None


            if result_index >= len(results):
                self.cprint(f'{self.Colors.YELLOW}=> Индекс результата {result_index} выходит за пределы, использую первый результат{self.Colors.RESET}')
                result_index = 0


            result = results[result_index]


            click_kwargs = {}
            if buttons:
                formatted_buttons = []
                for button in buttons:
                    if isinstance(button, dict):
                        btn_text = button.get('text', 'Кнопка')
                        btn_type = button.get('type', 'callback').lower()

                        if btn_type == 'callback':
                            btn_data = button.get('data', '')
                            formatted_buttons.append([Button.inline(btn_text, btn_data.encode())])
                        elif btn_type == 'url':
                            btn_url = button.get('url', button.get('data', ''))
                            formatted_buttons.append([Button.url(btn_text, btn_url)])
                        elif btn_type == 'switch':
                            btn_query = button.get('query', button.get('data', ''))
                            btn_hint = button.get('hint', '')
                            formatted_buttons.append([Button.switch_inline(btn_text, btn_query, btn_hint)])

                if formatted_buttons:
                    click_kwargs['buttons'] = formatted_buttons


            if silent:
                click_kwargs['silent'] = silent
            if reply_to:
                click_kwargs['reply_to'] = reply_to


            click_kwargs.update(kwargs)


            message = await result.click(chat_id, **click_kwargs)

            self.cprint(f'{self.Colors.GREEN}=> Успешно выполнен инлайн-запрос: {query[:50]}...{self.Colors.RESET}')
            return True, message

        except Exception as e:
            self.cprint(f'{self.Colors.RED}=X Ошибка выполнения инлайн-запроса: {e}{self.Colors.RESET}')
            await self.handle_error(e, source="inline_query_and_click")
            return False, None
    
    
    async def manual_inline_example(self, chat_id, query, bot_username=None):
        """
        Manual method for inline query execution with more control.
        
        This method allows full manual control over inline query execution,
        including custom result selection and manual sending.
        
        Args:
            chat_id (int): Target chat ID
            query (str): Inline query text
            bot_username (str, optional): Specific bot username to use
            
        Returns:
            list: List of inline query results or empty list on error
        """
        try:
            if not bot_username:
                bot_username = self.config.get('inline_bot_username')
                if not bot_username:
                    self.cprint(f'{self.Colors.RED}No bot username specified{self.Colors.RESET}')
                    return []
            
            # Get all results
            results = await self.client.inline_query(bot_username, query)
            
            if not results:
                return []
            
            # Return raw results for manual processing
            return results
            
        except Exception as e:
            self.cprint(f'{self.Colors.RED}Manual inline query failed: {e}{self.Colors.RESET}')
            return []
    
    
    async def send_inline_from_config(self, chat_id, query, buttons=None):
        """
        Simplified method that uses configured inline bot.
        
        This is the simplest way to use inline queries when you want
        to use the bot configured in config.json.
        
        Args:
            chat_id (int): Target chat ID
            query (str): Inline query text
            buttons (list, optional): Buttons to attach
            
        Returns:
            bool: Success status
        """
        return await self.inline_query_and_click(
            chat_id=chat_id,
            query=query,
            bot_username=self.config.get('inline_bot_username'),
            buttons=buttons
        )

    def register_inline_handler(self, pattern, handler):
        """Регистрация обработчика инлайн-запросов"""
        try:
            if not hasattr(self, 'inline_handlers'):
                self.inline_handlers = {}
            self.inline_handlers[pattern] = handler
        except Exception as e:
            print(f"=X Error register inline commands: {e}")
            
    def register_callback_handler(self, pattern, handler):
        """Регистрация обработчика callback-кнопок"""
        if not hasattr(self, 'callback_handlers'):
            self.callback_handlers = {}

        try:
            if isinstance(pattern, str):
                pattern = pattern.encode()
            self.callback_handlers[pattern] = handler

            if self.client:
                @self.client.on(events.CallbackQuery(data=pattern))
                async def callback_wrapper(event):
                    try:
                        await handler(event)
                    except Exception as e:
                        await self.handle_error(e, source="callback_handler", event=event)
        except Exception as e:
            self.cprint(f'{self.Colors.RED}=X Ошибка регистрации callback: {e}{self.Colors.RESET}')

    async def log_network(self, message):
        """Логирование сетевых событий"""
        if hasattr(self, 'send_log_message'):
            await self.send_log_message(f"🌐 {message}")

    async def log_error(self, message):
        """Логирование ошибок"""
        if hasattr(self, 'send_log_message'):
            await self.send_log_message(f"🔴 {message}")

    async def log_module(self, message):
        """Логирование событий модулей"""
        if hasattr(self, 'send_log_message'):
            await self.send_log_message(f"⚙️ {message}")

    async def detected_module_type(self, module):
        import inspect

        if hasattr(module, 'register'):
            if hasattr(module.register, 'method') and callable(module.register.method):
                return 'method'

            if callable(module.register):
                sig = inspect.signature(module.register)
                params = list(sig.parameters.keys())

                if len(params) == 1:
                    param_name = params[0]
                    if param_name == 'kernel':
                        return 'new'
                    elif param_name == 'client':
                        return 'old'

                return 'unknown'

        return 'none'

    async def load_module_from_file(self, file_path, module_name, is_system=False):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()

            if 'from .. import' in code or 'import loader' in code:
                return False, 'Несовместимый модуль (Тип: Heroku/hikka модуль)'

            if module_name in sys.modules:
                del sys.modules[module_name]

            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)

            module.kernel = self
            module.client = self.client
            module.custom_prefix = self.custom_prefix

            sys.modules[module_name] = module

            self.set_loading_module(module_name, 'system' if is_system else 'user')
            spec.loader.exec_module(module)


            module_type = await self.detected_module_type(module)

            if module_type == 'method':
                module.register.method(self)
            elif module_type == 'new':
                if hasattr(module, 'register'):
                    module.register(self)
            elif module_type == 'old':
                if hasattr(module, 'register'):
                    module.register(self.client)
            else:
                return False, 'Модуль не имеет функции register'

            if is_system:
                self.system_modules[module_name] = module
            else:
                self.loaded_modules[module_name] = module

            return True, f'Модуль {module_name} загружен ({module_type})'

        except ImportError as e:
            error_msg = str(e)
            match = re.search(r"No module named '([^']+)'", error_msg)
            if match:
                dep = match.group(1)
                return False, f'Требуется зависимость: {dep}. Используйте: pip install {dep}'
            return False, f'Ошибка импорта: {error_msg}'
        except CommandConflictError as e:
            raise e
        except Exception as e:
            return False, f'Ошибка загрузки: {str(e)}'
        finally:
            self.clear_loading_module()

        async def install_from_url(self, url, module_name=None, auto_dependencies=True):
            """
            Установка модуля из URL

            Args:
                url (str): URL модуля
                module_name (str, optional): Имя модуля (если None, извлекается из URL)
                auto_dependencies (bool): Автоматически устанавливать зависимости

            Returns:
                tuple: (success, message)
            """
            import os
            import aiohttp

            try:

                if not module_name:
                    if url.endswith('.py'):
                        module_name = os.path.basename(url)[:-3]
                    else:

                        parts = url.rstrip('/').split('/')
                        module_name = parts[-1]
                        if '.' in module_name:
                            module_name = module_name.split('.')[0]

                if module_name in self.system_modules:
                    return False, f"Модуль: {module_name}, системный"


                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            return False, f"Не удалось скачать модуль (статус: {resp.status})"

                        code = await resp.text()


                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                    f.write(code)
                    temp_path = f.name

                try:

                    dependencies = []
                    if auto_dependencies and 'requires' in code:
                        import re
                        reqs = re.findall(r'# requires: (.+)', code)
                        if reqs:
                            dependencies = [req.strip() for req in reqs[0].split(',')]


                    if dependencies:
                        import subprocess
                        import sys
                        for dep in dependencies:
                            subprocess.run(
                                [sys.executable, '-m', 'pip', 'install', dep],
                                capture_output=True,
                                text=True
                            )


                    success, message = await self.load_module_from_file(temp_path, module_name, False)

                    if success:

                        target_path = os.path.join(self.MODULES_LOADED_DIR, f'{module_name}.py')
                        with open(target_path, 'w', encoding='utf-8') as f:
                            f.write(code)

                        return True, f"Модуль {module_name} успешно установлен из URL"
                    else:
                        return False, f"Ошибка загрузки модуля: {message}"

                finally:

                    import os
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

            except Exception as e:
                return False, f"Ошибка установки из URL: {str(e)}"

    async def send_with_emoji(self, chat_id, text, **kwargs):
        """Универсальная отправка с поддержкой кастомных эмодзи"""
        if not self.emoji_parser or not self.emoji_parser.is_emoji_tag(text):
            return await self.client.send_message(chat_id, text, **kwargs)

        try:
            parsed_text, entities = self.emoji_parser.parse_to_entities(text)

            input_peer = await self.client.get_input_entity(chat_id)
            result = await self.client.send_message(
                input_peer,
                parsed_text,
                entities=entities,
                **{k: v for k, v in kwargs.items() if k != 'entities'}
            )
            return result
        except Exception as e:
            self.cprint(f'{self.Colors.RED}=X Ошибка отправки с эмодзи: {e}{self.Colors.RESET}')
            fallback_text = self.emoji_parser.remove_emoji_tags(text) if self.emoji_parser else text
            return await self.client.send_message(chat_id, fallback_text, **kwargs)

    def format_with_html(self, text, entities):
        """Форматирует текст с сущностями в HTML"""
        if not HTML_PARSER_AVAILABLE:
            return html.escape(text)

        from utils.html_parser import telegram_to_html
        return telegram_to_html(text, entities)


    async def get_module_metadata(self, code):
        """Извлекает метаданные из кода модуля"""
        metadata = {
            'author': 'неизвестен',
            'version': 'X.X.X',
            'description': 'описание отсутствует',
            'commands': {}
        }

        patterns = {
            'author': r'# author:\s*(.+)',
            'version': r'# version:\s*(.+)',
            'description': r'# description:\s*(.+)'
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, code, re.IGNORECASE)
            if match:
                metadata[key] = match.group(1).strip()

        # Ищем команды нового стиля: @kernel.register_command('cmd') с описанием
        # Описание может быть в комментарии на следующей строке
        kernel_patterns = [
            # Формат: @kernel.register_command('cmd')
            #         # описание
            #         async def ...
            r"@kernel\.register_command\('([^']+)'\)\s*\n\s*#\s*(.+?)\s*\n.*?async def",

            # Формат: kernel.register_command('cmd')
            #         # описание
            #         async def ...
            r"kernel\.register_command\('([^']+)'\)\s*\n\s*#\s*(.+?)\s*\n.*?async def",

            # Формат: @kernel.register_command('cmd')  # описание
            #         async def ...
            r"@kernel\.register_command\('([^']+)'\)\s*#\s*(.+?)\s*\n.*?async def",

            # Формат: kernel.register_command('cmd')  # описание
            #         async def ...
            r"kernel\.register_command\('([^']+)'\)\s*#\s*(.+?)\s*\n.*?async def"
        ]

        for pattern in kernel_patterns:
            matches = re.finditer(pattern, code, re.DOTALL)
            for match in matches:
                cmd = match.group(1)
                desc = match.group(2)
                if cmd and desc:
                    metadata['commands'][cmd] = desc.strip()

        # Ищем команды старого стиля
        old_patterns = [
            # Формат: @client.on(events.NewMessage(outgoing=True, pattern=r'\.cmd'))
            #         # описание
            #         async def ...
            r"@client\.on\(events\.NewMessage\(outgoing=True,\s*pattern=r'\\\\.([^']+)'\)\)\s*\n\s*#\s*(.+?)\s*\n.*?async def",

            # Формат: @client.on(events.NewMessage(outgoing=True, pattern=r'\.cmd'))  # описание
            #         async def ...
            r"@client\.on\(events\.NewMessage\(outgoing=True,\s*pattern=r'\\\\.([^']+)'\)\)\s*#\s*(.+?)\s*\n.*?async def"
        ]

        for pattern in old_patterns:
            matches = re.finditer(pattern, code, re.DOTALL)
            for match in matches:
                cmd = match.group(1)
                desc = match.group(2)
                if cmd and desc:
                    metadata['commands'][cmd] = desc.strip()

        return metadata

    async def download_module_from_repo(self, repo_url, module_name):
        """Скачивает модуль из репозитория с проверкой метаданных"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{repo_url}/{module_name}.py') as resp:
                    if resp.status == 200:
                        code = await resp.text()
                        return code
        except:
            pass
        return None

    async def get_repo_modules_list(self, repo_url):
        """Получает список модулей из репозитория"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{repo_url}/modules.ini') as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        modules = [line.strip() for line in content.split('\n') if line.strip()]
                        return modules
        except:
            pass
        return []


    async def send_log_message(self, text, file=None):
        if not self.log_chat_id:
            print(f"[DEBUG] log_chat_id не установлен: {self.log_chat_id}")
            return False

        print(f"[DEBUG] Пытаюсь отправить в лог-чат: {self.log_chat_id}")
        print(f"[DEBUG] Текст: {text[:100]}...")
        print(f"[DEBUG] bot_client существует: {hasattr(self, 'bot_client')}")

        try:
            if hasattr(self, 'bot_client') and self.bot_client and await self.bot_client.is_user_authorized():
                print("[DEBUG] Использую bot_client для отправки")
                client_to_use = self.bot_client
            else:
                print("[DEBUG] Использую основной client для отправки")
                client_to_use = self.client

            if file:
                print(f"[DEBUG] Отправляю файл: {file.name if hasattr(file, 'name') else 'unknown'}")
                await client_to_use.send_file(
                    self.log_chat_id,
                    file,
                    caption=text,
                    parse_mode='html'
                )
            else:
                print("[DEBUG] Отправляю текстовое сообщение")
                await client_to_use.send_message(
                    self.log_chat_id,
                    text,
                    parse_mode='html'
                )
            print("[DEBUG] Сообщение отправлено успешно")
            return True
        except Exception as e:
            print(f"[DEBUG] Ошибка отправки: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def send_error_log(self, error_text, source_file, message_info=""):
        if not self.log_chat_id:
            return

        formatted_error = f'''💠 <b>Source:</b> <code>{source_file}</code>
🔮 <b>Error:</b> <blockquote><code>{error_text[:500]}</code></blockquote>'''

        if message_info:
            formatted_error += f'\n🃏 <b>Message:</b> <code>{message_info[:300]}</code>'
        try:
            await self.send_log_message(formatted_error)
        except:
            self.logger.error(f"Error sending error log: {error_text}")

    async def handle_error(self, error, source="unknown", event=None):
        error_text = str(error)
        error_traceback = ''.join(traceback.format_exception(type(error), error, error.__traceback__))

        formatted_error = f"""💠 <b>Source:</b> <code>{html.escape(source)}</code>
🔮 <b>Error:</b> <blockquote>👉 <code>{html.escape(error_text[:300])}</code></blockquote>
        """

        if event:
            try:
                chat_title = getattr(event.chat, 'title', 'ЛС')
                user_info = await self.get_user_info(event.sender_id) if event.sender_id else "unknown"
                formatted_error += f"\n💬 <b>Message info:</b>\n<blockquote>🪬 <b>User:</b> {user_info}\n⌨️ <b>Text:</b> <code>{html.escape(event.text[:200] if event.text else 'not text')}</code>\n📬 <b>Chat:</b> {chat_title}</blockquote>"
            except:
                pass

        try:
            full_error = f"Ошибка в {source}:\n{error_traceback}"
            self.save_error_to_file(full_error)
            await self.send_log_message(formatted_error)
            print(f"=X {error_traceback}")

            if len(error_traceback) > 500:
                error_file = io.BytesIO(error_traceback.encode('utf-8'))
                error_file.name = f"error_{int(time.time())}.txt"
                await self.send_log_message("📎 <b>Полный трейсбэк во вложении</b>", error_file)

        except Exception as e:
            self.cprint(f'{self.Colors.RED}❌ Не удалось отправить лог ошибки: {e}{self.Colors.RESET}')
            print(f"Оригинальная ошибка: {error_traceback}")

    def save_error_to_file(self, error_text):
        try:
            from pathlib import Path
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d")
            error_file = log_dir / f"errors_{timestamp}.log"

            with open(error_file, 'a', encoding='utf-8') as f:
                f.write(f"\n\n{'='*60}\n")
                f.write(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*60}\n")
                f.write(error_text)
        except:
            pass



    async def get_thread_id(self, event):
        if not event:
            return None

        thread_id = None

        if hasattr(event, 'reply_to') and event.reply_to:
            thread_id = getattr(event.reply_to, 'reply_to_top_id', None)

        if not thread_id and hasattr(event, 'message'):
            thread_id = getattr(event.message, 'reply_to_top_id', None)

        return thread_id

    async def get_user_info(self, user_id):
        try:
            entity = await self.client.get_entity(user_id)

            if hasattr(entity, 'first_name') or hasattr(entity, 'last_name'):
                name = f"{entity.first_name or ''} {entity.last_name or ''}".strip()
                return f"{name} (@{entity.username or 'без username'})"
            elif hasattr(entity, 'title'):
                return f"{entity.title} (чат/канал)"
            else:
                return f"ID: {user_id}"
        except Exception as e:
            return f"ID: {user_id}"

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

    def first_time_setup(self):
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

                try:
                    api_id = int(api_id_input)
                except ValueError:
                    print(f'{Colors.RED}❌ API ID должен быть числом{Colors.RESET}')
                    continue

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

            except KeyboardInterrupt:
                print(f'\n{Colors.RED}❌ Настройка прервана{Colors.RESET}')
                sys.exit(1)

    def cprint(self, text, color=''):
        print(f'{color}{text}{Colors.RESET}')

    def is_admin(self, user_id):
        return hasattr(self, 'ADMIN_ID') and user_id == self.ADMIN_ID

    async def init_client(self):
        import sys
        import platform

        print(f"{self.Colors.CYAN}=- Инициализация MCUB на {platform.system()} (Python {sys.version_info.major}.{sys.version_info.minor})...{self.Colors.RESET}")



        from telethon.sessions import SQLiteSession

        proxy = self.config.get('proxy')


        session = SQLiteSession('user_session')

        self.client = TelegramClient(
            session,
            self.API_ID,
            self.API_HASH,
            proxy=proxy,
            connection_retries=3,
            request_retries=3,
            flood_sleep_threshold=30,
            device_model=f"PC-MCUB-{platform.system()}",
            system_version=f"Python {sys.version}",
            app_version=f"MCUB {self.VERSION}",
            lang_code="en",
            system_lang_code="en-US",
            base_logger=None,
            catch_up=False
        )

        try:
            await self.client.start(
                phone=self.PHONE,
                max_attempts=3
            )

            if not await self.client.is_user_authorized():
                print(f"{self.Colors.RED}=X Не удалось авторизоваться{self.Colors.RESET}")
                return False

            me = await self.client.get_me()
            if not me or not hasattr(me, 'id'):
                print(f"{self.Colors.RED}=X Неверные данные пользователя{self.Colors.RESET}")
                return False

            self.ADMIN_ID = me.id
            print(f"{self.Colors.GREEN}Авторизован как: {me.first_name} (ID: {me.id}){self.Colors.RESET}")
            print(f"{self.Colors.CYAN}📱 Номер: {self.PHONE}{self.Colors.RESET}")

            return True

        except Exception as e:
            print(f"{self.Colors.RED}=X Ошибка инициализации клиента: {e}{self.Colors.RESET}")
            import traceback
            traceback.print_exc()
            return False

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

                    self.set_loading_module(module_name, 'system')
                    spec.loader.exec_module(module)

                    if hasattr(module, 'register'):
                        module.register(self)
                        self.system_modules[module_name] = module
                        self.cprint(f'{Colors.GREEN}=> Загружен системный модуль: {module_name}{Colors.RESET}')
                    else:
                        self.cprint(f'{Colors.YELLOW}=> Модуль {module_name} не имеет функции register{Colors.RESET}')

                except CommandConflictError as e:
                    self.cprint(f'{Colors.RED}=X Ошибка загрузки системного модуля {module_name}: {e}{Colors.RESET}')
                except Exception as e:
                    self.cprint(f'{Colors.RED}=X Ошибка загрузки модуля {file_name}: {e}{Colors.RESET}')
                finally:
                    self.clear_loading_module()

    async def load_user_modules(self):
        files = os.listdir(self.MODULES_LOADED_DIR)

        if 'log_bot.py' in files:
            files.remove('log_bot.py')
            files.insert(0, 'log_bot.py')

        for file_name in files:
            if file_name.endswith('.py'):
                try:
                    module_name = file_name[:-3]
                    file_path = os.path.join(self.MODULES_LOADED_DIR, file_name)

                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    if 'def register(kernel):' in content:
                        spec = importlib.util.spec_from_file_location(module_name, file_path)
                        module = importlib.util.module_from_spec(spec)

                        module.kernel = self
                        module.client = self.client
                        module.custom_prefix = self.custom_prefix

                        sys.modules[module_name] = module

                        self.set_loading_module(module_name, 'user')
                        spec.loader.exec_module(module)

                        if hasattr(module, 'register'):
                            module.register(self)
                            self.loaded_modules[module_name] = module
                            self.cprint(f'{self.Colors.BLUE}=> Модуль загружен {module_name}{self.Colors.RESET}')
                    else:
                        spec = importlib.util.spec_from_file_location(module_name, file_path)
                        module = importlib.util.module_from_spec(spec)

                        sys.modules[module_name] = module
                        self.set_loading_module(module_name, 'user')
                        spec.loader.exec_module(module)

                        if hasattr(module, 'register'):
                            try:
                                module.register(self.client)
                            except:
                                await module.register(self.client)    
                            self.loaded_modules[module_name] = module
                            self.cprint(f'{self.Colors.GREEN}=> Загружен пользовательский модуль (старый стиль): {module_name}{self.Colors.RESET}')

                except CommandConflictError as e:
                    error_msg = f"Конфликт команд при загрузке модуля {file_name}: {e}"
                    self.cprint(f'{self.Colors.RED}=X {error_msg}{self.Colors.RESET}')
                    try:
                        await self.handle_error(e, source=f"load_module_conflict:{file_name}")
                    except:
                        pass

                except Exception as e:
                    error_msg = f"Ошибка загрузки модуля {file_name}: {e}"
                    self.cprint(f'{self.Colors.RED}=X {error_msg}{self.Colors.RESET}')
                    try:
                        await self.handle_error(e, source=f"load_module:{file_name}")
                    except:
                        pass
                finally:
                    self.clear_loading_module()

    def raw_text(self, source: any) -> str:
        try:

            if not hasattr(self, 'html_converter') or self.html_converter is None:
                from utils.raw_html import RawHTMLConverter
                self.html_converter = RawHTMLConverter(keep_newlines=True)


            if isinstance(source, str):
                return html.escape(source).replace('\n', '<br/>')

            return self.html_converter.convert_message(source)

        except Exception as e:
            # Резервный вариант, если что-то пошло не так
            text = getattr(source, 'message', str(source))
            return html.escape(text).replace('\n', '<br/>')

    async def inline_form(self, chat_id, title, fields=None, buttons=None, auto_send=True, **kwargs):
        """
        Создание и отправка инлайн-формы

        Args:
            chat_id (int): ID чата для отправки
            title (str): Заголовок формы
            fields (list/dict, optional): Поля формы
            buttons (list, optional): Кнопки в формате словарей:
                - Для callback: {"text": "Текст", "type": "callback", "data": "callback_data"}
                - Для URL: {"text": "Текст", "type": "url", "url": "https://ссылка"}
                - Для switch: {"text": "Текст", "type": "switch", "query": "запрос", "hint": "подсказка"}
            auto_send (bool): Автоматически отправить форму
            **kwargs: Дополнительные параметры

        Returns:
            tuple: (success, message) или строку запроса

        Example:
            # Простая форма
            await kernel.inline_form(
                chat_id=123456789,
                title="Настройки",
                buttons=[
                    {"text": "Сохранить", "type": "callback", "data": "save_123"},
                    {"text": "Сайт", "type": "url", "url": "https://example.com"},
                    {"text": "Поиск", "type": "switch", "query": "искать", "hint": "Найти..."}
                ]
            )

            # или (не советую)
            await kernel.inline_form(
                chat_id=123456789,
                title="Профиль",
                buttons=[
                    ["Редактировать", "callback", "edit"],
                    ["Сайт", "url", "https://example.com"]
                ]
            )
        """
        try:

            query_parts = [title]


            if fields:
                if isinstance(fields, dict):
                    for field, value in fields.items():
                        query_parts.append(f'{field}: {value}')
                elif isinstance(fields, list):
                    for i, field in enumerate(fields, 1):
                        query_parts.append(f'Поле {i}: {field}')

            base_text = "\n".join(query_parts)

            if buttons:
                json_buttons = []

                for button in buttons:
                    if isinstance(button, dict):
                        json_buttons.append(button)
                    elif isinstance(button, (list, tuple)):
                        if len(button) >= 2:
                            btn_data = {
                                "text": str(button[0])
                            }

                            if len(button) >= 2:
                                btn_type = str(button[1]).lower() if len(button) > 1 else "callback"
                                btn_data["type"] = btn_type

                                if len(button) >= 3:
                                    if btn_type == "callback":
                                        btn_data["data"] = str(button[2])
                                    elif btn_type == "url":
                                        btn_data["url"] = str(button[2])
                                    elif btn_type == "switch":
                                        btn_data["query"] = str(button[2])
                                        if len(button) >= 4:
                                            btn_data["hint"] = str(button[3])
                            json_buttons.append(btn_data)

                if json_buttons:
                    json_str = json.dumps(json_buttons, ensure_ascii=False)
                    query = f'{base_text} | {json_str}'
                else:
                    query = f'{base_text}'
            else:
                query = f'{base_text}'


            if auto_send:
                success, message = await self.inline_query_and_click(
                    chat_id=chat_id,
                    query=query,
                    **kwargs
                )
                return success, message
            else:
                return query

        except Exception as e:
            self.cprint(f'{self.Colors.RED}=X Ошибка создания инлайн-формы: {e}{self.Colors.RESET}')
            await self.handle_error(e, source="create_inline_form")
            return False, None


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

    async def process_bot_command(self, event):
        """Обработка команд бота"""
        text = event.text
        
        if not text.startswith('/'):
            return False
        
        # Получаем команду (первое слово без /)
        cmd = text.split()[0][1:] if ' ' in text else text[1:]
        
        # Убираем @username бота если есть
        if '@' in cmd:
            cmd = cmd.split('@')[0]
        
        if cmd in self.bot_command_handlers:
            pattern, handler = self.bot_command_handlers[cmd]
            await handler(event)
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

    async def setup_inline_bot(self):
        try:
            inline_bot_token = self.config.get('inline_bot_token')
            if not inline_bot_token:
                self.cprint(f'{Colors.YELLOW}=X Инлайн-бот не настроен (отсутствует токен){Colors.RESET}')
                return False

            self.cprint(f'{Colors.BLUE}=- Запускаю инлайн-бота...{Colors.RESET}')


            self.bot_client = TelegramClient(
                'inline_bot_session',
                self.API_ID,
                self.API_HASH,
                timeout=30
            )


            await self.bot_client.start(bot_token=inline_bot_token)

            bot_me = await self.bot_client.get_me()
            bot_username = bot_me.username


            self.config['inline_bot_username'] = bot_username

            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)

            try:
                import sys
                import os
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

                from core_inline.handlers import InlineHandlers
                handlers = InlineHandlers(self, self.bot_client)
                await handlers.register_handlers()

                import asyncio
                asyncio.create_task(self.bot_client.run_until_disconnected())

                self.cprint(f'{Colors.GREEN}=> Инлайн-бот запущен: {bot_username}{Colors.RESET}')
                return True
            except Exception as e:
                self.cprint(f'{Colors.RED}=> Ошибка регистрации обработчиков инлайн-бота: {str(e)}{Colors.RESET}')
                import traceback
                traceback.print_exc()
                return False

        except Exception as e:
            self.cprint(f'{Colors.RED}=X Инлайн-бот не запущен: {str(e)}{Colors.RESET}')
            import traceback
            traceback.print_exc()
            return False

    async def run(self):
        if not self.load_or_create_config():
            if not self.first_time_setup():
                self.cprint(f'{Colors.RED}=X Не удалось настроить юзербот{Colors.RESET}')
                return
        import telethon.errors
        from telethon import TelegramClient

        import logging
        logging.basicConfig(level=logging.WARNING)
        await self.init_scheduler()
        kernel_start_time = time.time()

        if not await self.init_client():
            return

        try:
            await self.init_db()
        except ImportError:
            self.cprint(f'{Colors.YELLOW}Установите: pip install aiosqlite{Colors.RESET}')
        except Exception as e:
            self.cprint(f'{Colors.RED}=X Ошибка инициализации БД: {e}{Colors.RESET}')


        await self.setup_inline_bot()


        if not self.config.get('inline_bot_token'):
            self.cprint(f'{Colors.CYAN}🤖 Начинаем настройку инлайн-бота...{Colors.RESET}')
            from core_inline.bot import InlineBot
            self.inline_bot = InlineBot(self)
            await self.inline_bot.setup()
    

        modules_start_time = time.time()
        await self.load_system_modules()
        await self.load_user_modules()
        modules_end_time = time.time()

        @self.client.on(events.NewMessage(outgoing=True))
        async def message_handler(event):
            premium_emoji_telescope = '<tg-emoji emoji-id="5429283852684124412">🔭</tg-emoji>'
            try:
                await self.process_command(event)
            except Exception as e:
                await self.handle_error(e, source="message_handler", event=event)

                try:
                    await event.edit(f"{premium_emoji_telescope} <b>Ошибка, смотри логи</b>", parse_mode='html')
                except:
                    pass
                    
        if hasattr(self, 'bot_client') and self.bot_client:
            @self.bot_client.on(events.NewMessage(pattern='/'))
            async def bot_command_handler(event):
                try:
                    await self.process_bot_command(event)
                except Exception as e:
                    await self.handle_error(e, source="bot_command_handler", event=event)


        print(f"""
 _    _  ____ _   _ ____   
| \\  / |/ ___| | | | __ )  
| |\\/| | |   | | | |  _ \\  
| |  | | |___| |_| | |_) | 
|_|  |_|\\____|\\___/|____/  
Kernel is load.

• Version: {self.VERSION}
• Prefix: {self.custom_prefix}
              """)
        if os.path.exists(self.RESTART_FILE):
            with open(self.RESTART_FILE, 'r') as f:
                data = f.read().split(',')
                if len(data) >= 3:
                    chat_id, msg_id, restart_time = int(data[0]), int(data[1]), float(data[2])
                    os.remove(self.RESTART_FILE)
                    me = await self.client.get_me()

                    mcub_emoji =  '<tg-emoji emoji-id="5470015630302287916">🔮</tg-emoji><tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>' if me.premium else "MCUB"

                    thread_id = int(data[3]) if len(data) >= 4 and data[3].isdigit() else None

                    kbl = round((modules_start_time - kernel_start_time) * 1000, 2)
                    mlfb = round((modules_end_time - modules_start_time) * 1000, 2)

                    emojis = ['ಠ_ಠ', '( ཀ ʖ̯ ཀ)', '(◕‿◕✿)', '(つ･･)つ', '༼つ◕_◕༽つ', '(•_•)', '☜(ﾟヮﾟ☜)', '(☞ﾟヮﾟ)☞', 'ʕ•ᴥ•ʔ', '(づ￣ ³￣)づ']
                    emoji = random.choice(emojis)


                    premium_emoji_alembic = '<tg-emoji emoji-id="5332654441508119011">⚗️</tg-emoji>'
                    premium_emoji_package = '<tg-emoji emoji-id="5399898266265475100">📦</tg-emoji>'

                    total_time = round((time.time() - restart_time) * 1000, 2)

                    if self.client.is_connected():
                        try:

                            await self.client.edit_message(
                                chat_id,
                                msg_id,
                                f'{premium_emoji_alembic} Перезагрузка <b>успешна!</b> {emoji}\n'
                                f'<i>но модули ещё загружаются...</i> <b>KLB:</b> <code>{total_time} ms</code>',
                                parse_mode='html'
                            )

                            await asyncio.sleep(1)

                            await self.client.delete_messages(chat_id, msg_id)


                            send_params = {}
                            if thread_id:
                                send_params['reply_to'] = thread_id

                            await self.client.send_message(
                                chat_id,
                                f'{premium_emoji_package} Твой <b>{mcub_emoji}</b> полностью загрузился!\n'
                                f'<blockquote><b>KBL:</b> <code>{total_time} ms</code>. <b>MLFB:</b> <code>{mlfb} ms</code>.</blockquote>',
                                parse_mode='html',
                                **send_params
                            )
                        except Exception as e:
                            self.cprint(f'{Colors.YELLOW}=X Не удалось отправить сообщение о перезагрузке: {e}{Colors.RESET}')
                            await self.handle_error(e, source="restart")

                    else:
                        self.cprint(f'{Colors.YELLOW}=X Не удалось отправить сообщение о перезагрузке: нет соединения{Colors.RESET}')

        await self.client.run_until_disconnected()
