# author: @Hairpin00
# version: 1.0.3
# description: backup userbot
import os
import sys
import json
import zipfile
import tempfile
import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest, EditAdminRequest, InviteToChannelRequest

def register(kernel):
    client = kernel.client
    
    BACKUP_CONFIG_FILE = Path(__file__).parent / "backup_config.json"
    DEFAULT_CONFIG = {
        "backup_chat_id": None,
        "backup_interval_hours": 1,
        "last_backup_time": None,
        "backup_count": 0,
        "enable_auto_backup": True,
        "timezone": "UTC"
    }
    
    class BackupModule:
        def __init__(self):
            self.config = self.load_config()
            self.bot_client = None
            self.kernel = kernel
            self.client = kernel.client
        
        def load_config(self):
            if BACKUP_CONFIG_FILE.exists():
                try:
                    with open(BACKUP_CONFIG_FILE, 'r', encoding='utf-8') as f:
                        loaded = json.load(f)
                        config = DEFAULT_CONFIG.copy()
                        config.update(loaded)
                        return config
                except Exception:
                    return DEFAULT_CONFIG.copy()
            return DEFAULT_CONFIG.copy()
        
        def save_config(self):
            with open(BACKUP_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        
        async def init_bot_client(self):
            bot_token = self.kernel.config.get('inline_bot_token')
            if not bot_token:
                return False
            
            try:
                self.bot_client = TelegramClient(
                    'bot_backup_session',
                    self.kernel.API_ID,
                    self.kernel.API_HASH
                )
                await self.bot_client.start(bot_token=bot_token)
                return True
            except Exception:
                return False
        
        async def ensure_backup_chat(self):
            # Сначала проверяем по сохранённому ID
            if self.config["backup_chat_id"]:
                try:
                    chat = await self.client.get_entity(int(self.config["backup_chat_id"]))
                    # Дополнительная проверка, что это действительно группа
                    if hasattr(chat, 'megagroup') and chat.megagroup:
                        return chat
                except Exception:
                    pass
                # Сбрасываем невалидный ID
                self.config["backup_chat_id"] = None
                self.save_config()

            # Ищем среди всех диалогов
            backup_chats = []
            try:
                async for dialog in self.client.iter_dialogs(limit=100):
                    if hasattr(dialog.entity, 'title') and dialog.entity.title:
                        # Ищем по точному названию или частичному
                        title_lower = dialog.entity.title.lower()
                        if 'mcub-backup' in title_lower or 'бекап' in title_lower:
                            backup_chats.append(dialog.entity)
            except Exception as e:
                print(f"Ошибка поиска чата: {e}")

            # Если нашли несколько, берём первый (самый недавний)
            if backup_chats:
                chat = backup_chats[0]
                self.config["backup_chat_id"] = chat.id
                self.save_config()
                return chat

            # Если не нашли, создаём новую
            try:
                result = await self.client(CreateChannelRequest(
                    title="MCUB-backup",
                    about="Автоматические бэкапы MCUB",
                    megagroup=True
                ))

                chat_id = result.chats[0].id
                self.config["backup_chat_id"] = chat_id
                self.save_config()

                await self.client.send_message(
                    chat_id,
                    "🔮 <i>Группа для бэкапов создана</i>\n<blockquote>🧬 <b>здесь будут сохраняться автоматические бэкапы</b></blockquote>",
                    parse_mode='html'
                )

                return await self.client.get_entity(chat_id)
            except Exception as e:
                print(f"Ошибка создания группы: {e}")
                return None
        
        def get_excluded_items(self):
            return [
                'core',
                'modules',
                '.git',
                'img',
                'logs',
                'core_inline',
                '*.session',
                'main.py',
                'README.md',
                'requirements.txt',
                '__pycache__',
                '.gitignore',
                'backup_config.json',
                'tester_config.json',
                'gemini_data'
            ]
        
        def should_exclude(self, path):
            for pattern in self.get_excluded_items():
                if '*' in pattern:
                    if path.name.endswith(pattern.replace('*', '')):
                        return True
                elif path.name == pattern:
                    return True
            return False
        
        async def create_backup_archive(self):
            temp_dir = tempfile.mkdtemp(prefix="mcub_backup_")
            backup_dir = Path(temp_dir) / "MCUB_backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            current_dir = Path.cwd()
            
            for item in current_dir.iterdir():
                if self.should_exclude(item):
                    continue
                
                try:
                    if item.is_file():
                        shutil.copy2(item, backup_dir / item.name)
                    elif item.is_dir():
                        shutil.copytree(item, backup_dir / item.name, ignore=shutil.ignore_patterns(*self.get_excluded_items()))
                except Exception:
                    continue
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_path = Path(temp_dir) / f"MCUB_backup_{timestamp}.zip"
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(backup_dir):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(backup_dir)
                        zipf.write(file_path, arcname)
            
            shutil.rmtree(backup_dir)
            
            zip_size = os.path.getsize(zip_path)
            return zip_path, timestamp, zip_size
        
        async def send_backup(self, manual=False):
            try:
                chat = await self.ensure_backup_chat()
                if not chat:
                    return False
                
                zip_path, timestamp, zip_size = await self.create_backup_archive()
                
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                size_mb = zip_size / (1024 * 1024)
                
                caption = f"""🔮 <i>Бекап создан</i>
<blockquote>📝 <b>время:</b> <mono>{current_time}</mono>
🔬 <b>размер:</b> <mono>{size_mb:.2f} MB</mono>
🎯 <b>тип:</b> <mono>{'ручной' if manual else 'автоматический'}</mono></blockquote>
🧬 <i>Usage</i> <mono>{self.kernel.custom_prefix}restoreall</mono>"""
                
                client_to_use = self.bot_client if self.bot_client else self.client
                
                await client_to_use.send_file(
                    chat.id,
                    zip_path,
                    caption=caption,
                    parse_mode='html'
                )
                
                self.config["last_backup_time"] = current_time
                self.config["backup_count"] = self.config.get("backup_count", 0) + 1
                self.save_config()
                
                os.remove(zip_path)
                return True
            except Exception:
                return False
        
        async def restore_backup(self, message):
            try:
                if not message.document:
                    return False
                
                if not message.file.name.endswith('.zip'):
                    return False
                
                temp_dir = tempfile.mkdtemp(prefix="restore_")
                zip_path = Path(temp_dir) / "backup.zip"
                
                await message.download_media(zip_path)
                
                extract_dir = Path(temp_dir) / "extracted"
                with zipfile.ZipFile(zip_path, 'r') as zipf:
                    zipf.extractall(extract_dir)
                
                backup_dir = extract_dir / "MCUB_backup"
                if not backup_dir.exists():
                    backup_dir = extract_dir
                
                changes = []
                current_dir = Path.cwd()
                
                for item in backup_dir.iterdir():
                    target = current_dir / item.name
                    
                    if target.exists():
                        backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                        backup_name = f"{target.name}_backup_{backup_time}"
                        shutil.move(target, current_dir / backup_name)
                        changes.append(f"📦 <b>{item.name}</b> сохранен как <mono>{backup_name}</mono>")
                    
                    if item.is_file():
                        shutil.copy2(item, target)
                    elif item.is_dir():
                        shutil.copytree(item, target)
                    
                    changes.append(f"✅ <b>{item.name}</b> восстановлен")
                
                shutil.rmtree(temp_dir, ignore_errors=True)
                
                return changes if changes else ["⚠️ <i>В архиве нет данных для восстановления</i>"]
            except Exception as e:
                return [f"❌ <i>Ошибка:</i> <code>{str(e)}</code>"]
    
    backup_module = BackupModule()
    backup_module.client = client
    
    @kernel.register_command('backupall')
    # создать backup
    async def backup_all_handler(event):
        await event.edit("⌛️ <i>Создаю бэкап...</i>", parse_mode='html')
        
        if not backup_module.bot_client:
            await backup_module.init_bot_client()
        
        if await backup_module.send_backup(manual=True):
            await event.edit("✅ <i>Бекап успешно создан</i>", parse_mode='html')
        else:
            await event.edit("❌ <i>Ошибка создания бекапа</i>", parse_mode='html')
    
    @kernel.register_command('restoreall')
    async def restore_all_handler(event):
        if not event.is_reply:
            await event.edit("❌ <i>Ответьте на сообщение с архивом бекапа</i>", parse_mode='html')
            return
        
        reply = await event.get_reply_message()
        
        await event.edit("⌛️ <i>Восстанавливаю бекап...</i>", parse_mode='html')
        
        changes = await backup_module.restore_backup(reply)
        
        if changes:
            changes_text = "\n".join(changes)
            await event.edit(f"✅ <i>Восстановление завершено</i>\n\n{changes_text}", parse_mode='html')
        else:
            await event.edit("❌ <i>Не удалось восстановить бекап</i>", parse_mode='html')
    
    @kernel.register_command('backupset')
    # настройки
    async def backup_settings_handler(event):
        args = event.text.split()
        
        if len(args) < 2:
            config = backup_module.config
            
            last_backup = config['last_backup_time'] or 'никогда'
            
            settings_text = f"""🔮 <i>Настройки бекапов</i>

<blockquote>💬 <b>чат ID:</b> <mono>{config['backup_chat_id'] or 'не установлен'}</mono>
⏰ <b>интервал:</b> <mono>{config['backup_interval_hours']} ч.</mono>
🤖 <b>автобекап:</b> <mono>{'включен' if config['enable_auto_backup'] else 'выключен'}</mono>
📅 <b>последний бекап:</b> <mono>{last_backup}</mono>
🔢 <b>всего бекапов:</b> <mono>{config['backup_count']}</mono></blockquote>

🧬 <i>Команды:</i>
<blockquote>⏰ <code>.backupset interval 2</code> - интервал в часах
🤖 <code>.backupset auto on/off</code> - вкл/выкл автобекап</blockquote>"""
            
            await event.edit(settings_text, parse_mode='html')
            return
        
        command = args[1].lower()
        
        if command == "interval" and len(args) > 2:
            try:
                hours = int(args[2])
                if 1 <= hours <= 24:
                    backup_module.config["backup_interval_hours"] = hours
                    backup_module.save_config()
                    await event.edit(f"✅ <i>Интервал изменен на</i> <mono>{hours} часов</mono>", parse_mode='html')
                else:
                    await event.edit("❌ <i>Интервал должен быть от 1 до 24 часов</i>", parse_mode='html')
            except ValueError:
                await event.edit("❌ <i>Неверный формат числа</i>", parse_mode='html')
        
        elif command == "auto" and len(args) > 2:
            state = args[2].lower()
            if state in ["on", "вкл", "true", "1"]:
                backup_module.config["enable_auto_backup"] = True
                backup_module.save_config()
                await event.edit("✅ <i>Автоматические бекапы включены</i>", parse_mode='html')
            elif state in ["off", "выкл", "false", "0"]:
                backup_module.config["enable_auto_backup"] = False
                backup_module.save_config()
                await event.edit("✅ <i>Автоматические бекапы выключены</i>", parse_mode='html')
            else:
                await event.edit("❌ <i>Используйте:</i> <code>.backupset auto on/off</code>", parse_mode='html')
        
        else:
            await event.edit("❌ <i>Неизвестная команда</i>", parse_mode='html')
    
    async def start_backup_scheduler():
        await asyncio.sleep(10)
        await backup_module.init_bot_client()
    
    asyncio.create_task(start_backup_scheduler())
    
    @kernel.register_command('backuphelp')
    # help
    async def backup_help_handler(event):
        help_text = """🔮 <i>Backup Module Help</i>

<blockquote>💾 <b>.backupall</b> - создать бекап
🔄 <b>.restoreall</b> - восстановить из бекапа
⚙️ <b>.backupset</b> - настройки бекапов</blockquote>

🧬 <i>Что бекапится:</i>
<blockquote>• Все файлы и папки
• Исключения: core, modules, .git, img, logs, core_inline, *.session и другие системные файлы</blockquote>

🔄 <i>Восстановление:</i>
<blockquote>1. Найдите нужный бекап в группе
2. Ответьте <code>.restoreall</code> на архив
3. Старые файлы будут переименованы
4. Файлы из архива будут восстановлены</blockquote>"""
        
        await event.edit(help_text, parse_mode='html')
    
    kernel.cprint(f'{kernel.Colors.GREEN}✅ Загружен модуль: userbot_backup{kernel.Colors.RESET}')
