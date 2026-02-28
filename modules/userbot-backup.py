import io
import os
import json
import zipfile
import tempfile
import asyncio
import shutil
import aiohttp
from datetime import datetime, timedelta
from pathlib import Path
from telethon import TelegramClient, Button
from telethon.tl.functions.channels import CreateChannelRequest, InviteToChannelRequest, EditPhotoRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest


def register(kernel):
    language = kernel.config.get('language', 'en')

    strings = {
        'ru': {
            'creating_backup': '⌛ Creating backup...',
            'backup_created': '✅ Backup created',
            'backup_failed': '❌ Backup failed',
            'reply_to_backup': '❌ Reply to a backup message',
            'not_backup_file': '❌ This is not a backup file',
            'restoring': '⌛ Restoring...',
            'restored': '✅ Restored:',
            'no_files': '⚠️ No files to restore',
            'restore_error': '❌ Error:',
            'backup_settings': '⚙️ Backup Settings',
            'chat_id': 'Chat ID:',
            'interval': 'Interval:',
            'auto_backup': 'Auto backup:',
            'last_backup': 'Last backup:',
            'total_backups': 'Total backups:',
            'commands': 'Commands:',
            'set_interval': 'Set backup interval',
            'enable_disable': 'Enable/disable auto backup',
            'set_chat': 'Set backup chat manually',
            'interval_set': '✅ Interval set to {hours} hours',
            'interval_invalid': '❌ Interval must be between 1 and 24 hours',
            'auto_enabled': '✅ Auto backup enabled',
            'auto_disabled': '✅ Auto backup disabled',
            'chat_set': '✅ Backup chat set to {chat_id}',
            'invalid_chat_id': '❌ Invalid chat ID',
            'unknown_command': '❌ Unknown command',
            'select_interval': '⏰ Select backup interval:',
            'check_pm': '✅ Check your PM with the bot',
            'bot_not_available': '⚠️ Bot is not available. Please start a chat with the bot first.',
            'cant_send_pm': '❌ Can\'t send PM. Start a chat with the bot first',
            'processing': '⌛ Processing...',
            'group_created': '✅ Backup group created',
            'tip_restore': 'tip: {prefix}restore to restore a backup',
        },
        'en': {
            'creating_backup': '⌛ Creating backup...',
            'backup_created': '✅ Backup created',
            'backup_failed': '❌ Backup failed',
            'reply_to_backup': '❌ Reply to a backup message',
            'not_backup_file': '❌ This is not a backup file',
            'restoring': '⌛ Restoring...',
            'restored': '✅ Restored:',
            'no_files': '⚠️ No files to restore',
            'restore_error': '❌ Error:',
            'backup_settings': '⚙️ Backup Settings',
            'chat_id': 'Chat ID:',
            'interval': 'Interval:',
            'auto_backup': 'Auto backup:',
            'last_backup': 'Last backup:',
            'total_backups': 'Total backups:',
            'commands': 'Commands:',
            'set_interval': 'Set backup interval',
            'enable_disable': 'Enable/disable auto backup',
            'set_chat': 'Set backup chat manually',
            'interval_set': '✅ Interval set to {hours} hours',
            'interval_invalid': '❌ Interval must be between 1 and 24 hours',
            'auto_enabled': '✅ Auto backup enabled',
            'auto_disabled': '✅ Auto backup disabled',
            'chat_set': '✅ Backup chat set to {chat_id}',
            'invalid_chat_id': '❌ Invalid chat ID',
            'unknown_command': '❌ Unknown command',
            'select_interval': '⏰ Select backup interval:',
            'check_pm': '✅ Check your PM with the bot',
            'bot_not_available': '⚠️ Bot is not available. Please start a chat with the bot first.',
            'cant_send_pm': '❌ Can\'t send PM. Start a chat with the bot first',
            'processing': '⌛ Processing...',
            'group_created': '✅ Backup group created',
            'tip_restore': 'tip: {prefix}restore to restore a backup',
        }
    }

    lang_strings = strings.get(language, strings['en'])

    class BackupModule:
        def __init__(self):
            self.kernel = kernel
            self.client = kernel.client
            self.config = {}
            self.backup_task = None

        async def initialize(self):
            self.config = await kernel.get_module_config(
                __name__,
                {
                    "backup_chat_id": None,
                    "backup_interval_hours": 12,
                    "last_backup_time": None,
                    "backup_count": 0,
                    "enable_auto_backup": True,
                },
            )

            await self.schedule_backups()

        async def schedule_backups(self):
            if self.backup_task:
                self.backup_task.cancel()

            if not self.config["enable_auto_backup"]:
                return

            interval = self.config["backup_interval_hours"] * 3600

            async def backup_loop():
                while True:
                    try:
                        await asyncio.sleep(interval)
                        if self.config["enable_auto_backup"]:
                            await self.send_backup(manual=False)
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        await kernel.handle_error(e, source="backup_loop", event=None)
                        await asyncio.sleep(60)

            self.backup_task = asyncio.create_task(backup_loop())

        async def ensure_backup_chat(self):
            if self.config["backup_chat_id"]:
                try:
                    chat = await self.client.get_entity(
                        int(self.config["backup_chat_id"])
                    )

                    if kernel.is_bot_available():
                        try:
                            bot_me = await kernel.bot_client.get_me()
                            try:
                                await kernel.bot_client.get_permissions(
                                    chat.id, bot_me.id
                                )
                            except Exception:
                                await self.client(
                                    InviteToChannelRequest(
                                        channel=chat.id, users=[bot_me.id]
                                    )
                                )
                                await asyncio.sleep(2)
                        except Exception as e:
                            await kernel.handle_error(
                                e, source="check_bot_in_chat", event=None
                            )
                    else:
                        await kernel.log_warning(f"Bot not available for chat {chat.id}")

                    return chat
                except Exception:
                    self.config["backup_chat_id"] = None

            async for dialog in self.client.iter_dialogs(limit=100):
                if hasattr(dialog.entity, "title") and dialog.entity.title:
                    if "backup" in dialog.entity.title.lower():
                        self.config["backup_chat_id"] = dialog.entity.id
                        await self.save_config()

                        if kernel.is_bot_available():
                            try:
                                bot_me = await kernel.bot_client.get_me()
                                await self.client(
                                    InviteToChannelRequest(
                                        channel=dialog.entity.id, users=[bot_me.id]
                                    )
                                )
                            except Exception as e:
                                await kernel.handle_error(
                                    e, source="add_bot_to_existing", event=None
                                )

                        return dialog.entity

            try:
                result = await self.client(
                    CreateChannelRequest(
                        title="MCUB Backups",
                        about="Automatic MCUB backups storage",
                        megagroup=True,
                    )
                )

                chat_id = result.chats[0].id
                self.config["backup_chat_id"] = chat_id
                await self.save_config()

                if kernel.is_bot_available():
                    try:
                        bot_me = await kernel.bot_client.get_me()
                        await self.client(
                            InviteToChannelRequest(channel=chat_id, users=[bot_me.id])
                        )
                    except Exception as e:
                        await kernel.handle_error(
                            e, source="add_bot_to_new", event=None
                        )

                chat = await self.client.get_entity(chat_id)
                await self.client.send_message(chat_id, lang_strings['group_created'])

                await self.set_group_photo(chat_id, "https://x0.at/4Bjx.jpg")

                return chat
            except Exception as e:
                await kernel.handle_error(e, source="ensure_backup_chat", event=None)
                return None

        async def create_backup_archive(self):
            temp_dir = tempfile.mkdtemp(prefix="mcub_backup_")
            backup_dir = Path(temp_dir) / "MCUB_backup"
            backup_dir.mkdir(parents=True, exist_ok=True)

            current_dir = Path.cwd()

            config_file = current_dir / "config.json"
            if config_file.exists():
                shutil.copy2(config_file, backup_dir / "config.json")

            modules_dir = current_dir / "modules_loaded"
            if modules_dir.exists():
                shutil.copytree(modules_dir, backup_dir / "modules_loaded")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_path = Path(temp_dir) / f"MCUB_backup_{timestamp}.zip"

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
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

                if kernel.is_bot_available():
                    try:
                        message = await kernel.bot_client.send_file(
                            chat.id,
                            zip_path,
                            caption=lang_strings['tip_restore'].format(prefix=kernel.custom_prefix),
                            buttons=Button.inline("🔄 Restore", f"restore:{timestamp}"),
                            parse_mode="html",
                        )
                    except Exception as e:
                        kernel.log_warning(
                            f"Failed to send backup via bot: {e}, trying via main client"
                        )
                        message = await self.client.send_file(
                            chat.id,
                            zip_path,
                            caption=lang_strings['tip_restore'].format(prefix=kernel.custom_prefix),
                            parse_mode="html",
                        )
                else:
                    message = await self.client.send_file(
                        chat.id,
                        zip_path,
                        caption=lang_strings['tip_restore'].format(prefix=kernel.custom_prefix),
                        parse_mode="html",
                    )

                self.config["last_backup_time"] = datetime.now().isoformat()
                self.config["backup_count"] = self.config.get("backup_count", 0) + 1
                await self.save_config()

                os.remove(zip_path)
                return True
            except Exception as e:
                await kernel.handle_error(e, source="send_backup", event=None)
                return False

        async def save_config(self):
            await kernel.save_module_config(__name__, self.config)

        async def set_group_photo(self, chat_id, photo_url):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(photo_url) as resp:
                        if resp.status == 200:
                            photo_data = await resp.read()

                            # Determine extension from Content-Type header;
                            # fall back to .jpg — Telegram requires a known image ext.
                            content_type = resp.headers.get("Content-Type", "image/jpeg")
                            ext_map = {
                                "image/jpeg": "photo.jpg",
                                "image/jpg":  "photo.jpg",
                                "image/png":  "photo.png",
                                "image/webp": "photo.jpg",
                                "image/gif":  "photo.gif",
                            }
                            filename = ext_map.get(content_type.split(";")[0].strip(), "photo.jpg")
                            import io as _io
                            buf = _io.BytesIO(photo_data)
                            buf.name = filename

                            input_file = await self.client.upload_file(buf)
                            await self.client(EditPhotoRequest(channel=chat_id, photo=input_file))
            except Exception as e:
                await kernel.handle_error(e, source="set_group_photo", event=None)

    backup_module = BackupModule()

    @kernel.register.command("backup")
    async def backup_handler(event):
        await event.edit(lang_strings['creating_backup'])

        if await backup_module.send_backup(manual=True):
            await event.edit(lang_strings['backup_created'])
        else:
            await event.edit(lang_strings['backup_failed'])

    @kernel.register.command("restore")
    async def restore_handler(event):
        if not event.is_reply:
            await event.edit(lang_strings['reply_to_backup'])
            return

        reply = await event.get_reply_message()

        if not reply.document or not reply.file.name.endswith(".zip"):
            await event.edit(lang_strings['not_backup_file'])
            return

        await event.edit(lang_strings['restoring'])

        temp_dir = tempfile.mkdtemp(prefix="restore_")
        zip_path = Path(temp_dir) / "backup.zip"

        try:
            await reply.download_media(zip_path)

            extract_dir = Path(temp_dir) / "extracted"
            with zipfile.ZipFile(zip_path, "r") as zipf:
                zipf.extractall(extract_dir)

            backup_dir = extract_dir / "MCUB_backup"
            if not backup_dir.exists():
                backup_dir = extract_dir

            current_dir = Path.cwd()
            restored = []

            for item in backup_dir.iterdir():
                target = current_dir / item.name

                if target.exists():
                    backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"{target.name}_backup_{backup_time}"
                    shutil.move(target, current_dir / backup_name)
                    restored.append(f"📦 {item.name} → {backup_name}")

                if item.is_file():
                    shutil.copy2(item, target)
                elif item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)

                restored.append(f"✅ {item.name}")

            shutil.rmtree(temp_dir, ignore_errors=True)

            if restored:
                await event.edit(f"{lang_strings['restored']}\n" + "\n".join(restored))
            else:
                await event.edit(lang_strings['no_files'])
        except Exception as e:
            await kernel.handle_error(e, source="restore_handler", event=event)
            await event.edit(f"{lang_strings['restore_error']} {str(e)}")

    @kernel.register.command("backupsettings")
    async def backup_settings_handler(event):
        args = event.text.split()

        if len(args) == 1:
            config = backup_module.config

            last_backup = config["last_backup_time"]
            if last_backup:
                last_backup = datetime.fromisoformat(last_backup).strftime(
                    "%Y-%m-%d %H:%M"
                )
            else:
                last_backup = "Never"

            settings_text = f"""⚙️ **{lang_strings['backup_settings']}**

**{lang_strings['chat_id']}** `{config['backup_chat_id'] or 'Not set'}`
**{lang_strings['interval']}** `{config['backup_interval_hours']} hours`
**{lang_strings['auto_backup']}** `{'Enabled' if config['enable_auto_backup'] else 'Disabled'}`
**{lang_strings['last_backup']}** `{last_backup}`
**{lang_strings['total_backups']}** `{config['backup_count']}`

**{lang_strings['commands']}**
`.backupsettings interval <hours>` - {lang_strings['set_interval']}
`.backupsettings auto on/off` - {lang_strings['enable_disable']}
`.backupsettings chat` - {lang_strings['set_chat']}"""

            await event.edit(settings_text)
            return

        cmd = args[1].lower()

        if cmd == "interval" and len(args) > 2:
            try:
                hours = int(args[2])
                if 1 <= hours <= 24:
                    backup_module.config["backup_interval_hours"] = hours
                    await backup_module.save_config()
                    await backup_module.schedule_backups()
                    await event.edit(lang_strings['interval_set'].format(hours=hours))
                else:
                    await event.edit(lang_strings['interval_invalid'])
            except ValueError:
                await event.edit(lang_strings['interval_invalid'])

        elif cmd == "auto" and len(args) > 2:
            state = args[2].lower()
            if state in ["on", "true", "1", "yes"]:
                backup_module.config["enable_auto_backup"] = True
                await backup_module.save_config()
                await backup_module.schedule_backups()
                await event.edit(lang_strings['auto_enabled'])
            elif state in ["off", "false", "0", "no"]:
                backup_module.config["enable_auto_backup"] = False
                await backup_module.save_config()
                await backup_module.schedule_backups()
                await event.edit(lang_strings['auto_disabled'])
            else:
                await event.edit(f"❌ {lang_strings['api_protection_usage']} .backupsettings auto on/off")

        elif cmd == "chat" and len(args) > 2:
            try:
                chat_id = int(args[2])
                backup_module.config["backup_chat_id"] = chat_id
                await backup_module.save_config()
                await event.edit(lang_strings['chat_set'].format(chat_id=chat_id))
            except ValueError:
                await event.edit(lang_strings['invalid_chat_id'])
        else:
            await event.edit(lang_strings['unknown_command'])

    @kernel.register.command("backuptime")
    async def backup_time_handler(event):
        user_id = event.sender_id

        buttons = [
            [Button.inline("1 hour", "backup_interval:1")],
            [Button.inline("6 hours", "backup_interval:6")],
            [Button.inline("12 hours", "backup_interval:12")],
            [Button.inline("24 hours", "backup_interval:24")],
        ]

        try:
            if kernel.is_bot_available():
                await kernel.bot_client.send_message(
                    user_id, f"⏰ **{lang_strings['select_interval']}**", buttons=buttons
                )
                await event.edit(lang_strings['check_pm'])
            else:
                await event.edit(lang_strings['bot_not_available'])
        except Exception as e:
            await event.edit(lang_strings['cant_send_pm'])

    async def backup_interval_callback(event):
        try:
            interval = int(event.data.decode().split(":")[1])

            if 1 <= interval <= 24:
                backup_module.config["backup_interval_hours"] = interval
                await backup_module.save_config()
                await backup_module.schedule_backups()

                await event.answer(f"✅ {lang_strings['interval_set'].format(hours=interval)}", alert=False)
                await event.edit(f"⏰ {lang_strings['interval']}: {interval} hours")
            else:
                await event.answer("❌ Invalid interval", alert=True)
        except Exception as e:
            await kernel.handle_error(e, source="backup_interval_callback", event=event)

    async def restore_callback(event):
        try:
            await event.answer(lang_strings['processing'], alert=False)

            message = await event.get_message()

            class MockEvent:
                def __init__(self, msg):
                    self.is_reply = True
                    self.message = msg
                    self.sender_id = event.sender_id
                    self.chat_id = event.chat_id
                    self.text = f"{kernel.custom_prefix}restore"

                async def get_reply_message(self):
                    return self.message

                async def edit(self, text):
                    await event.edit(text)

            mock_event = MockEvent(message)

            await restore_handler(mock_event)

        except Exception as e:
            await kernel.handle_error(e, source="restore_callback", event=event)
            await event.answer(lang_strings['error_processing'], alert=True)

    kernel.register_callback_handler("backup_interval:", backup_interval_callback)
    kernel.register_callback_handler("restore:", restore_callback)

    asyncio.create_task(backup_module.initialize())
