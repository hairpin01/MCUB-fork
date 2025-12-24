import time
import sys
import os
import importlib.util
import re
import json
import subprocess
import random
try:
    import html
    import socks
    import traceback
    import psutil
    import aiohttp
    import asyncio
    from datetime import datetime
    from telethon import TelegramClient, events, Button
    from telethon.errors import SessionPasswordNeededError
except ImportError:
    print(
        "Установите зависимости",
        "pip install -r requirements.txt"
        )
    


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
        self.VERSION = '1.0.1.5'
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
        self.Colors = Colors
        
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

        self.inline_handlers = {}
        self.callback_handlers = {}
        self.log_chat_id = None
        self.log_bot_enabled = False


        try:
            from utils.emoji_parser import emoji_parser
            self.emoji_parser = emoji_parser
            self.cprint(f'{Colors.GREEN}The emoji parser is loaded{Colors.RESET}')
        except ImportError:
            self.emoji_parser = None
            self.cprint(f'{Colors.YELLOW}The emoji parser is not loaded{Colors.RESET}')


        try:
            asyncio.create_task(cleanup_old_logs())
        except Exception as e:
            error_msg = f"Error clearnup_old_logs: {e}"
            self.cprint(f'{self.Colors.RED}❌ {error_msg}{self.Colors.RESET}')


        async def cleanup_old_logs():
                """Очистка старых логов"""
                try:
                    log_dir = Path("logs")
                    if not log_dir.exists():
                        return

                    now = time.time()
                    for log_file in log_dir.glob("*.log"):
                        if (now - os.path.getmtime(log_file)) > 30 * 24 * 3600:
                            os.remove(log_file)
                except:
                    pass
    def register_inline_handler(self, pattern, handler):
        self.inline_handlers[pattern] = handler

    def register_callback_handler(self, pattern, handler):
        """Регистрация обработчика callback-кнопок"""
        self.callback_handlers[pattern] = handler
        @self.client.on(events.CallbackQuery(pattern=pattern.encode()))

        async def callback_wrapper(event):
            await handler(event)

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
    
    async def send_with_emoji(self, chat_id, text, **kwargs):
        """
        Отправляет сообщение с поддержкой эмодзи
        Использует низкоуровневый запрос для поддержки кастомных эмодзи
        """
        if not self.emoji_parser or not self.emoji_parser.is_emoji_tag(text):
            return await self.client.send_message(chat_id, text, **kwargs)

        try:

            parsed_text, entities = self.emoji_parser.parse_to_entities(text)


            clean_kwargs = {k: v for k, v in kwargs.items() if k != 'entities'}


            from telethon.tl.functions.messages import SendMessageRequest


            input_peer = await self.client.get_input_entity(chat_id)

            #
            result = await self.client(SendMessageRequest(
                peer=input_peer,
                message=parsed_text,
                entities=entities,
                no_webpage=clean_kwargs.get('link_preview', False),
                silent=clean_kwargs.get('silent', False),
                reply_to_msg_id=clean_kwargs.get('reply_to', None)
            ))

            #
            return await self.client.get_messages(chat_id, ids=[result.id])

        except Exception as e:
            self.cprint(f'{Colors.RED}❌ Ошибка отправки с эмодзи: {e}{Colors.RESET}')
            await self.handle_error(e, source="send_with_emoji", event=event)
            await self.kernel.send_log_err
            fallback_text = self.emoji_parser.remove_emoji_tags(text)
            return await self.client.send_message(chat_id, fallback_text, **kwargs)

    def format_with_emoji(self, text, entities):
        """
        Форматирует текст с сущностями в HTML

        Пример:
        html_text = kernel.format_with_emoji(
            message.text,
            message.entities
        )
        """
        if not self.emoji_parser:
            return html.escape(text)

        return self.emoji_parser.entities_to_html(text, entities)

    async def send_log_message(self, text, file=None):
        """Отправка сообщения в лог-чат"""
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
        """Отправка ошибки в лог-чат с форматированием"""
        if not self.log_chat_id:
            return

        formatted_error = f'''💠 <b>Source:</b> <code>{source_file}</code>
🔮 <b>Error:</b> <blockquote><code>{error_text[:500]}</code></blockquote>'''

        if message_info:
            formatted_error += f'\n🃏 <b>Message:</b> <code>{message_info[:300]}</code>'

        await self.send_log_message(formatted_error)

    async def handle_error(self, error, source="unknown", event=None):
        """Глобальный обработчик ошибок"""
        error_text = str(error)
        error_traceback = ''.join(traceback.format_exception(type(error), error, error.__traceback__))

        # Форматируем сообщение об ошибке
        formatted_error = f"""💠 <b>Source:</b> <code>{html.escape(source)}</code>
🔮 <b>Error:</b> <blockquote>👉 <code>{html.escape(error_text[:300])}</code></blockquote>
        """

        if event:
            try:
                # Добавляем информацию о сообщении
                chat_title = getattr(event.chat, 'title', 'ЛС')
                user_info = await self.get_user_info(event.sender_id) if event.sender_id else "unknown"
                formatted_error += f"\n💬 <b>Message info:</b>\n<blockquote>🪬 <b>User:</b> {user_info}\n⌨️ <b>Text:</b> <code>{html.escape(event.text[:200] if event.text else 'not text')}</code>\n📬 <b>Chat:</b> {chat_title}</blockquote>"
            except:
                pass

        # Отправляем через бота
        try:
            # Полный трейсбэк для отладки
            full_error = f"Ошибка в {source}:\n{error_traceback}"

            # Сохраняем в файл
            self.save_error_to_file(full_error)

            # Отправляем уведомление
            await self.send_log_message(formatted_error)

            # Если есть трейсбэк, отправляем его как файл
            if len(error_traceback) > 500:
                error_file = io.BytesIO(error_traceback.encode('utf-8'))
                error_file.name = f"error_{int(time.time())}.txt"
                await self.send_log_message("📎 <b>Полный трейсбэк во вложении</b>", error_file)

        except Exception as e:
            # Если не удалось отправить, пишем в консоль
            self.cprint(f'{self.Colors.RED}❌ Не удалось отправить лог ошибки: {e}{self.Colors.RESET}')
            print(f"Оригинальная ошибка: {error_traceback}")

    def save_error_to_file(self, error_text):
        """Сохраняем ошибку в файл"""
        try:
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

    async def get_user_info(self, user_id):
        """Получаем информацию о пользователе"""
        try:
            user = await self.client.get_entity(user_id)
            if user.first_name or user.last_name:
                name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                return f"{name} (@{user.username or 'без username'})"
            return f"ID: {user_id}"
        except:
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
    
    async def init_client(self):
        proxy = self.config.get('proxy')
        self.client = TelegramClient('user_session', self.API_ID, self.API_HASH, proxy=proxy)
        
        try:
            await self.client.start(phone=self.PHONE)
            self.cprint(f'{Colors.GREEN}MCUB ядро запущено{Colors.RESET}')
            return True
        except Exception as e:
            self.cprint(f'{Colors.RED}❌ Ошибка авторизации: {e}{Colors.RESET}')
            return False
    
    def register_command(self, pattern, func=None):
        if func:
            cmd = pattern.lstrip('^\\' + self.custom_prefix)
            if cmd.endswith('$'):
                cmd = cmd[:-1]
            self.command_handlers[cmd] = func
            return func
        else:
            def decorator(f):
                cmd = pattern.lstrip('^\\' + self.custom_prefix)
                if cmd.endswith('$'):
                    cmd = cmd[:-1]
                self.command_handlers[cmd] = f
                return f
            return decorator
    
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
        files = os.listdir(self.MODULES_LOADED_DIR)

        # Сначала загружаем log_bot
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
                        spec.loader.exec_module(module)

                        if hasattr(module, 'register'):
                            module.register(self)
                            self.loaded_modules[module_name] = module
                    else:
                        spec = importlib.util.spec_from_file_location(module_name, file_path)
                        module = importlib.util.module_from_spec(spec)

                        sys.modules[module_name] = module
                        spec.loader.exec_module(module)

                        if hasattr(module, 'register'):
                            module.register(self.client)
                            self.loaded_modules[module_name] = module
                            self.cprint(f'{self.Colors.GREEN}✅ Загружен пользовательский модуль (старый стиль): {module_name}{self.Colors.RESET}')

                except Exception as e:
                    error_msg = f"Ошибка загрузки модуля {file_name}: {e}"
                    self.cprint(f'{self.Colors.RED}❌ {error_msg}{self.Colors.RESET}')
                    await self.handle_error(e, source=f"load_module:{file_name}")
    
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
                    if hasattr(self, 'log_network'):
                        await self.log_network("✅ Соединение восстановлено")
                    return True
            except Exception as e:
                self.reconnect_attempts += 1
                if hasattr(self, 'log_network'):
                    await self.log_network(f"✈️ Плохое соединение. Попытка {self.reconnect_attempts}/{self.max_reconnect_attempts}")
                await asyncio.sleep(self.reconnect_delay * self.reconnect_attempts)

        return False

    async def setup_inline_bot(self):
        try:
            from core_inline.bot import InlineBot
            self.inline_bot = InlineBot(self)
            await self.inline_bot.setup()
        except Exception as e:
            self.cprint(f'{Colors.YELLOW}⚠️ Инлайн-бот не запущен: {e}{Colors.RESET}')
    
    async def run(self):
        if not self.load_or_create_config():
            if not self.first_time_setup():
                self.cprint(f'{Colors.RED}❌ Не удалось настроить юзербот{Colors.RESET}')
                return

        kernel_start_time = time.time()

        if not await self.init_client():
            return

        await self.setup_inline_bot()

        modules_start_time = time.time()
        await self.load_system_modules()
        await self.load_user_modules()
        modules_end_time = time.time()

        @self.client.on(events.NewMessage(outgoing=True))
        async def message_handler(event):
            try:
                await self.process_command(event)
            except Exception as e:
                await self.handle_error(e, source="message_handler", event=event)

                try:
                    await event.edit(f"🔭 <b>Ошибка, смотри логи</b>", parse_mode='html')
                except:
                    pass

        self.cprint(f'{Colors.CYAN}The kernel is loaded{Colors.RESET}')

        # Обработка перезагрузки
        if os.path.exists(self.RESTART_FILE):
            with open(self.RESTART_FILE, 'r') as f:
                data = f.read().split(',')
                if len(data) >= 3:
                    chat_id, msg_id, restart_time = data[0], data[1], float(data[2])
                    os.remove(self.RESTART_FILE)

                    kbl = round((modules_start_time - kernel_start_time) * 1000, 2)
                    mlfb = round((modules_end_time - modules_start_time) * 1000, 2)

                    emojis = ['ಠ_ಠ', '( ཀ ʖ̯ ཀ)', '(◕‿◕✿)', '(つ･･)つ', '༼つ◕_◕༽つ', '(•_•)', '☜(ﾟヮﾟ☜)', '(☞ﾟヮﾟ)☞', 'ʕ•ᴥ•ʔ', '(づ￣ ³￣)づ']
                    emoji = random.choice(emojis)

                    total_time = round((time.time() - restart_time) * 1000, 2)

                    if self.client.is_connected():
                        try:
                            # Сначала редактируем старое сообщение
                            await self.client.edit_message(
                                int(chat_id),
                                int(msg_id),
                                f'⚗️ Перезагрузка <b>успешна!</b> {emoji}\n'
                                f'<i>но модули ещё загружаются...</i> <b>CLB:</b> <code>{total_time} ms</code>',
                                parse_mode='html'
                            )

                            # Ждём немного
                            await asyncio.sleep(1)

                            # Удаляем отредактированное сообщение
                            await self.client.delete_messages(int(chat_id), int(msg_id))

                            # Отправляем новое сообщение о полной загрузке
                            await self.client.send_message(
                                int(chat_id),
                                f'📦 Твой <b>MCUB</b> полностью загрузился!\n'
                                f'<blockquote><b>KBL:</b> <code>{kbl} ms</code>. <b>MLFB:</b> <code>{mlfb} ms</code>.</blockquote>',
                                parse_mode='html'
                            )
                        except Exception as e:
                            self.cprint(f'{Colors.YELLOW}⚠️ Не удалось отправить сообщение о перезагрузке: {e}{Colors.RESET}')
                    else:
                        self.cprint(f'{Colors.YELLOW}⚠️ Не удалось отправить сообщение о перезагрузке: нет соединения{Colors.RESET}')

        await self.client.run_until_disconnected()

