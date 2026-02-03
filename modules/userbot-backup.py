import os
import json
import zipfile
import tempfile
import asyncio
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from telethon import TelegramClient, Button
from telethon.tl.functions.channels import CreateChannelRequest, InviteToChannelRequest


def register(kernel):
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
                        kernel.log_warning(f"Bot not available for chat {chat.id}")

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
                await self.client.send_message(chat_id, "✅ Backup group created")
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
                            caption=f"tip: <code>{kernel.custom_prefix}restore</code> <i>to restore a backup</i>",
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
                            caption=f"tip: <code>{kernel.custom_prefix}restore</code> <i>to restore a backup</i>",
                            parse_mode="html",
                        )
                else:
                    message = await self.client.send_file(
                        chat.id,
                        zip_path,
                        caption=f"tip: <code>{kernel.custom_prefix}restore</code> <i>to restore a backup</i>",
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

    backup_module = BackupModule()

    @kernel.register_command("backup")
    async def backup_handler(event):
        await event.edit("⌛ Creating backup...")

        if await backup_module.send_backup(manual=True):
            await event.edit("✅ Backup created")
        else:
            await event.edit("❌ Backup failed")

    @kernel.register_command("restore")
    async def restore_handler(event):
        if not event.is_reply:
            await event.edit("❌ Reply to a backup message")
            return

        reply = await event.get_reply_message()

        if not reply.document or not reply.file.name.endswith(".zip"):
            await event.edit("❌ This is not a backup file")
            return

        await event.edit("⌛ Restoring...")

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
                await event.edit("✅ Restored:\n" + "\n".join(restored))
            else:
                await event.edit("⚠️ No files to restore")
        except Exception as e:
            await kernel.handle_error(e, source="restore_handler", event=event)
            await event.edit(f"❌ Error: {str(e)}")

    @kernel.register_command("backupsettings")
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

            settings_text = f"""⚙️ **Backup Settings**
            
**Chat ID:** `{config['backup_chat_id'] or 'Not set'}`
**Interval:** `{config['backup_interval_hours']} hours`
**Auto backup:** `{'Enabled' if config['enable_auto_backup'] else 'Disabled'}`
**Last backup:** `{last_backup}`
**Total backups:** `{config['backup_count']}`

**Commands:**
`.backupsettings interval <hours>` - Set backup interval
`.backupsettings auto on/off` - Enable/disable auto backup
`.backupsettings chat` - Set backup chat manually"""

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
                    await event.edit(f"✅ Interval set to {hours} hours")
                else:
                    await event.edit("❌ Interval must be between 1 and 24 hours")
            except ValueError:
                await event.edit("❌ Invalid number format")

        elif cmd == "auto" and len(args) > 2:
            state = args[2].lower()
            if state in ["on", "true", "1", "yes"]:
                backup_module.config["enable_auto_backup"] = True
                await backup_module.save_config()
                await backup_module.schedule_backups()
                await event.edit("✅ Auto backup enabled")
            elif state in ["off", "false", "0", "no"]:
                backup_module.config["enable_auto_backup"] = False
                await backup_module.save_config()
                await backup_module.schedule_backups()
                await event.edit("✅ Auto backup disabled")
            else:
                await event.edit("❌ Usage: .backupsettings auto on/off")

        elif cmd == "chat" and len(args) > 2:
            try:
                chat_id = int(args[2])
                backup_module.config["backup_chat_id"] = chat_id
                await backup_module.save_config()
                await event.edit(f"✅ Backup chat set to {chat_id}")
            except ValueError:
                await event.edit("❌ Invalid chat ID")
        else:
            await event.edit("❌ Unknown command")

    @kernel.register_command("backuptime")
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
                    user_id, "⏰ **Select backup interval:**", buttons=buttons
                )
                await event.edit("✅ Check your PM with the bot")
            else:
                await event.edit(
                    "⚠️ Bot is not available. Please start a chat with the bot first."
                )
        except Exception as e:
            await event.edit("❌ Can't send PM. Start a chat with the bot first")

    async def backup_interval_callback(event):
        try:
            interval = int(event.data.decode().split(":")[1])

            if 1 <= interval <= 24:
                backup_module.config["backup_interval_hours"] = interval
                await backup_module.save_config()
                await backup_module.schedule_backups()

                await event.answer(f"✅ Interval set to {interval} hours", alert=False)
                await event.edit(f"⏰ Backup interval: {interval} hours")
            else:
                await event.answer("❌ Invalid interval", alert=True)
        except Exception as e:
            await kernel.handle_error(e, source="backup_interval_callback", event=event)

    async def restore_callback(event):
        try:
            await event.answer("⌛ Processing...", alert=False)

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
            await event.answer("❌ Error processing", alert=True)

    kernel.register_callback_handler("backup_interval:", backup_interval_callback)
    kernel.register_callback_handler("restore:", restore_callback)

    asyncio.create_task(backup_module.initialize())
