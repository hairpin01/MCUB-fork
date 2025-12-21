import os
import sys
import json
import zipfile
import tempfile
import asyncio
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
import time

try:
    from tabfix import TabFixAPI, TabFixConfig
except ImportError:
    try:
        from tabfix_tool import TabFixAPI, TabFixConfig
    except ImportError:
        print("❌ TabFix не установлен. Установите: pip install tabfix-tool")

from telethon import events, Button, TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.tl.types import ChatAdminRights, InputPeerUser

# Импортируем нужные модули для APScheduler с обработкой временных зон
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.jobstores.memory import MemoryJobStore
    import pytz
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False
    print("❌ APScheduler не установлен. Установите: pip install apscheduler pytz")


def register(client):
    BACKUP_CONFIG_FILE = Path(__file__).parent / "backup_config.json"
    DEFAULT_CONFIG = {
        "backup_chat_id": None,
        "backup_interval_hours": 1,
        "modules_path": "modules",
        "config_path": "config.json",
        "last_backup_time": None,
        "backup_count": 0,
        "enable_auto_backup": True,
        "timezone": "UTC"  # Добавляем настройку временной зоны
    }
    
    if HAS_APSCHEDULER:
        # Создаем планировщик с UTC временной зоной по умолчанию
        try:
            scheduler = AsyncIOScheduler(
                jobstores={'default': MemoryJobStore()},
                timezone=timezone.utc  # Используем UTC по умолчанию
            )
        except:
            # Если не удалось с UTC, пробуем системную зону
            scheduler = AsyncIOScheduler()
    else:
        scheduler = None
    
    backup_task = None
    
    class BackupModule:
        def __init__(self, client):
            self.client = client
            self.config = self.load_config()
            self.bot_path = Path.cwd()
            
        def load_config(self):
            if BACKUP_CONFIG_FILE.exists():
                try:
                    with open(BACKUP_CONFIG_FILE, 'r', encoding='utf-8') as f:
                        loaded = json.load(f)
                        config = DEFAULT_CONFIG.copy()
                        config.update(loaded)
                        
                        # Проверяем и корректируем временную зону
                        if "timezone" not in config:
                            config["timezone"] = "UTC"
                        
                        return config
                except Exception as e:
                    print(f"Ошибка загрузки конфига: {e}")
                    return DEFAULT_CONFIG.copy()
            return DEFAULT_CONFIG.copy()
            
        def save_config(self):
            with open(BACKUP_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        
        def get_timezone(self):
            """Получаем объект временной зоны из конфига"""
            try:
                if HAS_APSCHEDULER:
                    tz_str = self.config.get("timezone", "UTC")
                    if tz_str.upper() == "UTC":
                        return timezone.utc
                    return pytz.timezone(tz_str)
                return timezone.utc
            except Exception as e:
                print(f"Ошибка временной зоны '{self.config.get('timezone', 'UTC')}': {e}, использую UTC")
                return timezone.utc
        
        def get_current_time(self):
            """Получаем текущее время с учетом временной зоны"""
            tz = self.get_timezone()
            if hasattr(tz, 'localize'):
                # Для pytz временных зон
                return datetime.now(tz)
            else:
                # Для стандартных timezone
                return datetime.now(tz)
        
        def format_datetime(self, dt=None):
            """Форматируем дату-время для отображения"""
            if dt is None:
                dt = self.get_current_time()
            
            try:
                # Пробуем форматировать с часовым поясом
                if hasattr(dt, 'tzinfo') and dt.tzinfo:
                    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
                else:
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                return dt.strftime("%Y-%m-%d %H:%M:%S")
        
        async def ensure_backup_chat(self):
            if self.config["backup_chat_id"]:
                try:
                    chat = await self.client.get_entity(int(self.config["backup_chat_id"]))
                    return chat
                except:
                    pass
            
            try:
                result = await self.client(CreateChannelRequest(
                    title="🤖 Бэкапы бота",
                    about="Автоматические бэкапы модулей и конфигурации бота",
                    megagroup=True
                ))
                
                chat_id = result.chats[0].id
                self.config["backup_chat_id"] = chat_id
                self.save_config()
                
                me = await self.client.get_me()
                
                try:
                    from telethon.tl.functions.channels import EditAdminRequest
                    rights = ChatAdminRights(
                        change_info=True,
                        post_messages=True,
                        edit_messages=True,
                        delete_messages=True,
                        ban_users=True,
                        invite_users=True,
                        pin_messages=True,
                        add_admins=True,
                        manage_call=True
                    )
                    
                    await self.client(EditAdminRequest(
                        channel=chat_id,
                        user_id=me.id,
                        admin_rights=rights,
                        rank="Бэкап-менеджер"
                    ))
                except:
                    pass
                
                await self.client.send_message(
                    chat_id,
                    "✅ **Группа для бэкапов создана!**\n\n"
                    "Здесь будут сохраняться автоматические бэкапы модулей и конфигурации бота."
                )
                
                return await self.client.get_entity(chat_id)
                
            except Exception as e:
                print(f"Ошибка создания чата: {e}")
                return None
        
        def get_modules_path(self):
            modules_path = Path(self.config["modules_path"])
            if not modules_path.is_absolute():
                modules_path = self.bot_path / modules_path
            return modules_path
        
        def get_config_path(self):
            config_path = Path(self.config["config_path"])
            if not config_path.is_absolute():
                config_path = self.bot_path / config_path
            return config_path
        
        def format_json_file(self, filepath: Path) -> bool:
            try:
                if not filepath.exists():
                    return False
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                config = TabFixConfig(format_json=True)
                api = TabFixAPI(config=config)
                
                processed, result = api.process_string(content, filepath)
                
                if result.changed:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(processed)
                    return True
                return True
            except:
                return False
        
        async def create_backup_archive(self):
            temp_dir = tempfile.mkdtemp(prefix="backup_")
            backup_dir = Path(temp_dir) / "backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            modules_path = self.get_modules_path()
            config_path = self.get_config_path()
            
            if modules_path.exists() and modules_path.is_dir():
                modules_backup = backup_dir / "modules"
                shutil.copytree(modules_path, modules_backup)
            
            if config_path.exists():
                config_backup = backup_dir / "config.json"
                shutil.copy2(config_path, config_backup)
                
                self.format_json_file(config_backup)
            
            current_time = self.get_current_time()
            timestamp = current_time.strftime("%Y%m%d_%H%M%S")
            zip_path = Path(temp_dir) / f"backup_{timestamp}.zip"
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(backup_dir):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(backup_dir)
                        zipf.write(file_path, arcname)
            
            shutil.rmtree(backup_dir)
            return zip_path, timestamp
        
        async def send_backup(self, manual: bool = False):
            try:
                chat = await self.ensure_backup_chat()
                if not chat:
                    return False
                
                zip_path, timestamp = await self.create_backup_archive()
                
                stats = []
                modules_path = self.get_modules_path()
                config_path = self.get_config_path()
                
                if modules_path.exists():
                    module_files = list(modules_path.rglob("*.py"))
                    stats.append(f"📦 Модулей: {len(module_files)}")
                
                if config_path.exists():
                    config_size = config_path.stat().st_size
                    stats.append(f"⚙️ Конфиг: {config_size / 1024:.1f} KB")
                
                current_time = self.get_current_time()
                caption = (
                    f"📊 **Бэкап бота**\n"
                    f"⏰ {self.format_datetime(current_time)}\n"
                    f"{'🔧 Ручной' if manual else '🤖 Авто'} бэкап\n\n"
                    f"{chr(10).join(stats) if stats else '⚠️ Файлы не найдены'}\n\n"
                    f"💾 **Использование:**\n"
                    f"1. Скачайте архив\n"
                    f"2. Ответьте `.restoreall` на это сообщение\n"
                    f"3. Бэкап будет восстановлен\n\n"
                    f"🆔 `{timestamp}`"
                )
                
                await self.client.send_file(
                    chat.id,
                    zip_path,
                    caption=caption,
                    parse_mode='html'
                )
                
                self.config["last_backup_time"] = current_time.isoformat()
                self.config["backup_count"] = self.config.get("backup_count", 0) + 1
                self.save_config()
                
                os.remove(zip_path)
                return True
                
            except Exception as e:
                print(f"Ошибка отправки бэкапа: {e}")
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
                
                modules_backup = extract_dir / "modules"
                config_backup = extract_dir / "config.json"
                
                changes = []
                
                if modules_backup.exists() and modules_backup.is_dir():
                    modules_path = self.get_modules_path()
                    
                    if modules_path.exists():
                        current_time = self.get_current_time()
                        backup_modules = modules_path.with_name(f"{modules_path.name}_backup_{current_time.strftime('%Y%m%d_%H%M%S')}")
                        shutil.move(modules_path, backup_modules)
                        changes.append(f"📦 Модули сохранены в: `{backup_modules.name}`")
                    
                    shutil.copytree(modules_backup, modules_path)
                    changes.append("✅ Модули восстановлены")
                
                if config_backup.exists():
                    config_path = self.get_config_path()
                    
                    if config_path.exists():
                        current_time = self.get_current_time()
                        backup_config = config_path.with_name(f"{config_path.stem}_backup_{current_time.strftime('%Y%m%d_%H%M%S')}{config_path.suffix}")
                        shutil.move(config_path, backup_config)
                        changes.append(f"⚙️ Конфиг сохранен в: `{backup_config.name}`")
                    
                    shutil.copy2(config_backup, config_path)
                    changes.append("✅ Конфиг восстановлен")
                    
                    self.format_json_file(config_path)
                
                shutil.rmtree(temp_dir, ignore_errors=True)
                
                return changes if changes else ["⚠️ В архиве нет данных для восстановления"]
                
            except Exception as e:
                print(f"Ошибка восстановления: {e}")
                return [f"❌ Ошибка: {str(e)}"]
        
        async def start_auto_backup(self):
            if not self.config["enable_auto_backup"] or not HAS_APSCHEDULER:
                return
            
            async def backup_job():
                if self.config["enable_auto_backup"]:
                    await self.send_backup(manual=False)
            
            try:
                scheduler.add_job(
                    backup_job,
                    'interval',
                    hours=self.config["backup_interval_hours"],
                    id='auto_backup',
                    replace_existing=True,
                    timezone=self.get_timezone()  # Указываем временную зону
                )
                
                if not scheduler.running:
                    scheduler.start()
            except Exception as e:
                print(f"Ошибка запуска планировщика: {e}")
                # Пробуем запустить без указания временной зоны
                try:
                    scheduler.add_job(
                        backup_job,
                        'interval',
                        hours=self.config["backup_interval_hours"],
                        id='auto_backup',
                        replace_existing=True
                    )
                    
                    if not scheduler.running:
                        scheduler.start()
                except Exception as e2:
                    print(f"Не удалось запустить планировщик: {e2}")
    
        async def stop_auto_backup(self):
            try:
                if scheduler:
                    scheduler.remove_job('auto_backup')
            except:
                pass
    
    backup_module = BackupModule(client)
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.backupall$'))
    async def backup_all_handler(event):
        await event.edit("⏳ Создаю бэкап...")
        
        if await backup_module.send_backup(manual=True):
            await event.edit("✅ Бэкап успешно создан и отправлен в группу!")
        else:
            await event.edit("❌ Ошибка создания бэкапа")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.restoreall$'))
    async def restore_all_handler(event):
        if not event.is_reply:
            await event.edit("**Ошибка:** Ответьте на сообщение с архивом бэкапа")
            return
        
        reply = await event.get_reply_message()
        
        await event.edit("⏳ Восстанавливаю бэкап...")
        
        changes = await backup_module.restore_backup(reply)
        
        if changes:
            changes_text = "\n".join(changes)
            await event.edit(f"✅ **Восстановление завершено:**\n\n{changes_text}")
        else:
            await event.edit("❌ Не удалось восстановить бэкап")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.backupset(?:\s+(.*))?$'))
    async def backup_settings_handler(event):
        args = event.pattern_match.group(1) or ""
        
        if not args:
            config = backup_module.config
            
            # Форматируем время последнего бэкапа
            last_backup = config['last_backup_time'] or 'никогда'
            if last_backup != 'никогда':
                try:
                    dt = datetime.fromisoformat(last_backup)
                    last_backup = backup_module.format_datetime(dt)
                except:
                    pass
            
            settings_text = (
                f"⚙️ **Настройки бэкапов:**\n\n"
                f"• ID чата: `{config['backup_chat_id'] or 'не установлен'}`\n"
                f"• Интервал: {config['backup_interval_hours']} ч.\n"
                f"• Автобэкап: {'включен' if config['enable_auto_backup'] else 'выключен'}\n"
                f"• Временная зона: {config.get('timezone', 'UTC')}\n"
                f"• Путь к модулям: `{config['modules_path']}`\n"
                f"• Путь к конфигу: `{config['config_path']}`\n"
                f"• Последний бэкап: {last_backup}\n"
                f"• Всего бэкапов: {config['backup_count']}\n\n"
                f"**Команды:**\n"
                f"`.backupset interval 2` - интервал в часах\n"
                f"`.backupset auto on/off` - вкл/выкл автобэкап\n"
                f"`.backupset timezone UTC` - установить временную зону\n"
                f"`.backupset path modules новый_путь`\n"
                f"`.backupset path config новый_путь`"
            )
            await event.edit(settings_text)
            return
        
        args_list = args.split()
        command = args_list[0].lower() if args_list else ""
        
        if command == "interval" and len(args_list) > 1:
            try:
                hours = int(args_list[1])
                if 1 <= hours <= 24:
                    backup_module.config["backup_interval_hours"] = hours
                    backup_module.save_config()
                    
                    await backup_module.stop_auto_backup()
                    await backup_module.start_auto_backup()
                    
                    await event.edit(f"✅ Интервал авто-бэкапа изменен на {hours} часов")
                else:
                    await event.edit("❌ Интервал должен быть от 1 до 24 часов")
            except ValueError:
                await event.edit("❌ Неверный формат числа")
        
        elif command == "auto" and len(args_list) > 1:
            state = args_list[1].lower()
            if state in ["on", "вкл", "true", "1"]:
                backup_module.config["enable_auto_backup"] = True
                backup_module.save_config()
                await backup_module.start_auto_backup()
                await event.edit("✅ Автоматические бэкапы включены")
            elif state in ["off", "выкл", "false", "0"]:
                backup_module.config["enable_auto_backup"] = False
                backup_module.save_config()
                await backup_module.stop_auto_backup()
                await event.edit("✅ Автоматические бэкапы выключены")
            else:
                await event.edit("❌ Используйте: `.backupset auto on/off`")
        
        elif command == "timezone" and len(args_list) > 1:
            if not HAS_APSCHEDULER:
                await event.edit("❌ APScheduler не установлен. Установите: pip install apscheduler pytz")
                return
                
            tz_name = args_list[1]
            try:
                # Проверяем, что временная зона существует
                import pytz
                if tz_name.upper() == "UTC":
                    tz = timezone.utc
                else:
                    tz = pytz.timezone(tz_name)
                
                backup_module.config["timezone"] = tz_name
                backup_module.save_config()
                
                await backup_module.stop_auto_backup()
                await backup_module.start_auto_backup()
                
                await event.edit(f"✅ Временная зона изменена на {tz_name}")
            except pytz.UnknownTimeZoneError:
                await event.edit(f"❌ Неизвестная временная зона: {tz_name}\n"
                               f"Доступные зоны: UTC, Europe/Moscow, Europe/London, Asia/Tokyo и т.д.")
            except Exception as e:
                await event.edit(f"❌ Ошибка установки временной зоны: {e}")
        
        elif command == "path" and len(args_list) > 2:
            path_type = args_list[1].lower()
            new_path = args_list[2]
            
            if path_type == "modules":
                backup_module.config["modules_path"] = new_path
                backup_module.save_config()
                await event.edit(f"✅ Путь к модулям изменен на: `{new_path}`")
            
            elif path_type == "config":
                backup_module.config["config_path"] = new_path
                backup_module.save_config()
                await event.edit(f"✅ Путь к конфигу изменен на: `{new_path}`")
            
            else:
                await event.edit("❌ Используйте: `.backupset path modules/config новый_путь`")
        
        else:
            await event.edit("❌ Неизвестная команда. Используйте `.backupset` без аргументов для справки")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.backupnow$'))
    async def backup_now_handler(event):
        await event.edit("⏳ Создаю бэкап...")
        
        if await backup_module.send_backup(manual=True):
            await event.edit("✅ Бэкап успешно создан и отправлен в группу!")
        else:
            await event.edit("❌ Ошибка создания бэкапа")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.backupchat$'))
    async def backup_chat_handler(event):
        try:
            chat = await backup_module.ensure_backup_chat()
            if chat:
                try:
                    from telethon.tl.functions.messages import ExportChatInviteRequest
                    result = await client(ExportChatInviteRequest(chat))
                    invite_link = result.link
                except:
                    invite_link = "не удалось получить ссылку"
                
                await event.edit(
                    f"✅ **Группа для бэкапов:**\n\n"
                    f"• Название: {chat.title}\n"
                    f"• ID: `{chat.id}`\n"
                    f"• Приглашение: {invite_link}\n\n"
                    f"📎 Сохраните эту информацию!"
                )
            else:
                await event.edit("❌ Не удалось создать/найти группу")
        except Exception as e:
            await event.edit(f"❌ Ошибка: {str(e)}")
    
    async def start_backup_scheduler():
        await asyncio.sleep(5)
        await backup_module.start_auto_backup()
        print("✅ Модуль бэкапов запущен")
    
    client.loop.create_task(start_backup_scheduler())
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.backuphelp$'))
    async def backup_help_handler(event):
        help_text = (
            "📖 **Backup Module Help**\n\n"
            "**Основные команды:**\n"
            "`.backupall` - создать бэкап\n"
            "`.backupnow` - создать бэкап (синоним)\n"
            "`.restoreall` - восстановить из бэкапа (ответ на архив)\n"
            "`.backupchat` - показать инфо о группе бэкапов\n"
            "`.backupset` - настройки бэкапов\n\n"
            "**Настройки (.backupset):**\n"
            "`.backupset interval ЧАСЫ` - интервал авто-бэкапа (1-24)\n"
            "`.backupset auto on/off` - вкл/выкл авто-бэкап\n"
            "`.backupset timezone ЗОНА` - временная зона (UTC, Europe/Moscow и т.д.)\n"
            "`.backupset path modules ПУТЬ` - путь к модулям\n"
            "`.backupset path config ПУТЬ` - путь к конфигу\n\n"
            "**Что бэкапится:**\n"
            "• Все файлы из папки modules/*\n"
            "• Файл config.json (автоформатируется)\n\n"
            "**Восстановление:**\n"
            "1. Найдите нужный бэкап в группе\n"
            "2. Ответьте `.restoreall` на архив\n"
            "3. Старые файлы будут переименованы\n"
            "4. Файлы из архива будут восстановлены"
        )
        await event.edit(help_text)
    
    print("✅ Модуль бэкапов загружен")
