# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

# requires: cryptography

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import io
import json
import os
import re
import shutil
import tarfile
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import aiohttp
from telethon.errors import ChannelsTooMuchError
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    EditPhotoRequest,
    InviteToChannelRequest,
)

from core.lib.loader.module_base import ModuleBase, callback, command
from core.lib.loader.module_config import (
    Boolean,
    Choice,
    ConfigValue,
    Integer,
    ModuleConfig,
    Secret,
    String,
)


def _derive_fernet_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte Fernet-compatible key from a password using PBKDF2."""
    import base64

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def _encrypt_file(src: Path, dst: Path, password: str) -> None:
    """Encrypt *src* to *dst* using Fernet/AES with a password-derived key.

    File format: 16-byte salt | ciphertext
    """
    from cryptography.fernet import Fernet

    salt = os.urandom(16)
    key = _derive_fernet_key(password, salt)
    f = Fernet(key)
    with open(src, "rb") as fh:
        data = fh.read()
    token = f.encrypt(data)
    with open(dst, "wb") as fh:
        fh.write(salt + token)


def _decrypt_file(src: Path, password: str) -> bytes:
    """Decrypt a file produced by *_encrypt_file* and return plaintext bytes."""
    from cryptography.fernet import Fernet, InvalidToken

    with open(src, "rb") as fh:
        raw = fh.read()
    salt, token = raw[:16], raw[16:]
    key = _derive_fernet_key(password, salt)
    f = Fernet(key)
    try:
        return f.decrypt(token)
    except InvalidToken as exc:
        raise ValueError("Wrong password or corrupted archive") from exc


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_delay(text: str) -> int | None:
    """Parse '30m' / '2h' / '90s' → seconds. Returns None on failure."""
    m = re.fullmatch(r"(\d+)(s|m|h)", text.strip().lower())
    if not m:
        return None
    val, unit = int(m.group(1)), m.group(2)
    return val * {"s": 1, "m": 60, "h": 3600}[unit]


# Build emoji map at module level so it can be used in the strings dict literal
_E: dict[str, str] = {
    "hourglass": '<tg-emoji emoji-id="5426958067763804056">⏳</tg-emoji>',
    "check": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>',
    "cross": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji>',
    "warning": '<tg-emoji emoji-id="5409235172979672859">⚠️</tg-emoji>',
    "settings": '<tg-emoji emoji-id="5332654441508119011">⚙️</tg-emoji>',
    "clock": '<tg-emoji emoji-id="5326015457155620929">🧳</tg-emoji>',
    "box": '<tg-emoji emoji-id="5399898266265475100">📦</tg-emoji>',
    "refresh": '<tg-emoji emoji-id="5332600281970517875">🔄</tg-emoji>',
    "lock": '<tg-emoji emoji-id="5447644880824181073">🔐</tg-emoji>',
    "cloud": '<tg-emoji emoji-id="5359954476607521990">☁️</tg-emoji>',
    "trash": '<tg-emoji emoji-id="5380186498827373381">🗑️</tg-emoji>',
    "list": '<tg-emoji emoji-id="5411192149058289173">☁️</tg-emoji>',
}


class Backup(ModuleBase):
    name = "userbot-backup"
    version = "2.0.0"
    author = "@Hairpin00"
    description = {
        "ru": "Расширенное резервное копирование",
        "en": "Advanced backup",
    }

    config = ModuleConfig(
        ConfigValue(
            "backup_chat_id",
            None,
            description="Chat ID for storing backups",
            validator=Integer(default=None),
        ),
        ConfigValue(
            "backup_interval_hours",
            12,
            description="Auto-backup interval in hours (1-168)",
            validator=Integer(default=12, min=1, max=168),
        ),
        ConfigValue(
            "last_backup_time",
            None,
            description="Last backup timestamp",
            validator=String(default=None),
        ),
        ConfigValue(
            "backup_count",
            0,
            description="Total number of backups created",
            validator=Integer(default=0, min=0),
        ),
        ConfigValue(
            "enable_auto_backup",
            True,
            description="Enable automatic backups",
            validator=Boolean(default=True),
        ),
        ConfigValue(
            "exclude_patterns",
            "",
            description="Comma-separated glob patterns to exclude (e.g. *.log,*.tmp)",
            validator=String(default=""),
        ),
        ConfigValue(
            "max_backups",
            0,
            description="Max backup files to keep in chat (0 = unlimited)",
            validator=Integer(default=0, min=0),
        ),
        ConfigValue(
            "encryption_password",
            "",
            description="Password for AES archive encryption (empty = disabled)",
            validator=Secret(default=""),
        ),
        ConfigValue(
            "cloud_provider",
            "none",
            description="Cloud storage provider",
            validator=Choice(choices=["none", "yadisk", "gdrive"], default="none"),
        ),
        ConfigValue(
            "cloud_token",
            "",
            description="Cloud OAuth token (Yandex Disk or Google Drive)",
            validator=Secret(default=""),
        ),
        ConfigValue(
            "cloud_also_telegram",
            True,
            description="Also send to Telegram when cloud is enabled",
            validator=Boolean(default=True),
        ),
        ConfigValue(
            "compression_level",
            6,
            description="ZIP compression level (0 = store, 9 = maximum)",
            validator=Integer(default=6, min=0, max=9),
        ),
        ConfigValue(
            "archive_format",
            "zip",
            description="Archive format",
            validator=Choice(choices=["zip", "tar.gz"], default="zip"),
        ),
        ConfigValue(
            "auto_restore_config",
            True,
            description="Attempt to auto-restore config.json on startup if missing",
            validator=Boolean(default=True),
        ),
    )

    strings = {"name": "userbot_backup"}
    # OLD strings removed after migration to langpacks - kept for reference
    """
    _OLD_STRINGS = {
        "ru": {
            "creating_backup": f"{_E['hourglass']} <i>Создаю бэкап...</i>",
            "backup_created": f"{_E['check']} <b>Бэкап создан</b>",
            "backup_failed": f"{_E['cross']} <i><b>Ошибка создания бэкапа</b></i>",
            "reply_to_backup": f"{_E['cross']} <u>Ответьте на сообщение с бэкапом</u>",
            "not_backup_file": f"{_E['cross']} <u>Это не файл бэкапа</u>",
            "restoring": f"{_E['hourglass']} <i>Восстанавливаю...</i>",
            "restored": f"{_E['check']} <b>Восстановлено:</b>",
            "no_files": f"{_E['warning']} <u>Нет файлов для восстановления</u>",
            "restore_error": f"{_E['cross']} Ошибка:",
            "chat_id": "Chat ID:",
            "interval": "Интервал:",
            "auto_backup": "Авто-бэкап:",
            "last_backup": "Последний бэкап:",
            "total_backups": "Всего бэкапов:",
            "commands": "Команды:",
            "set_interval": "Установить интервал бэкапа",
            "enable_disable": "Включить/выключить авто-бэкап",
            "set_chat": "Установить чат для бэкапа",
            "interval_set": f"{_E['check']} Интервал установлен на {{hours}} часов",
            "interval_invalid": f"{_E['cross']} Интервал должен быть от 1 до 168 часов",
            "backup_settings": f"{_E['settings']} Настройки бэкапа",
            "auto_enabled": f"{_E['check']} Авто-бэкап включён",
            "auto_disabled": f"{_E['check']} Авто-бэкап выключен",
            "chat_set": f"{_E['check']} Чат для бэкапа установлен: {{chat_id}}",
            "check_pm": f"{_E['check']} Проверьте ЛС с ботом",
            "bot_not_available": f"{_E['warning']} Бот недоступен. Сначала напишите боту в ЛС.",
            "cant_send_pm": f"{_E['cross']} Не удалось отправить ЛС. Сначала напишите боту",
            "invalid_chat_id": f"{_E['cross']} Неверный ID чата",
            "unknown_command": f"{_E['cross']} Неизвестная команда",
            "select_interval": f"{_E['clock']} Выберите интервал бэкапа:",
            "processing": "🔄 Обработка...",
            "group_created": f"{_E['check']} Группа для бэкапов создана",
            "tip_restore": "подсказка: {prefix}restore для восстановления бэкапа",
            "btn_restore": "🔄 Восстановить",
            "btn_1_hour": "1 час",
            "btn_6_hours": "6 часов",
            "btn_12_hours": "12 часов",
            "btn_24_hours": "24 часа",
            "not_set": "Не установлен",
            "hours": "часов",
            "enabled": "Включён",
            "disabled": "Выключен",
            "invalid_interval": f"{_E['cross']} Неверный интервал",
            "error_processing": f"{_E['cross']} Ошибка обработки",
            "encrypted_note": f"<blockquote>{_E['lock']} Зашифровано</blockquote>",
            "wrong_password": f"{_E['cross']} Неверный пароль или архив повреждён",
            "hash_ok": f"{_E['check']} SHA256 совпадает — файл цел",
            "hash_mismatch": f"<blockquote>{_E['cross']} SHA256 не совпадает — файл повреждён!</blockquote>",
            "hash_unknown": f"{_E['warning']} SHA256 не найден в подписи",
            "cloud_ok": f"{_E['cloud']} {{provider}}: загружено успешно",
            "cloud_fail": f"{_E['cross']} {{provider}}: ошибка загрузки",
            "cleanup_done": f"{_E['trash']} Удалено старых бэкапов: {{count}}",
            "no_backups_found": f"{_E['warning']} Бэкапы не найдены в чате",
            "select_backup": f"{_E['list']} <b>Выберите бэкап для восстановления:</b>",
            "delayed_scheduled": f"{_E['clock']} Бэкап будет создан в <b>{{time}}</b>",
            "invalid_time": f"{_E['cross']} Неверный формат времени. Пример: 30m, 2h, 90s",
            "unknown_arg": f"{_E['cross']} Неизвестный аргумент. Доступно: config, db, modules, in &lt;время&gt;, cleanup",
            "low_disk": f"{_E['warning']} Мало места на диске: нужно ~{{needed}}MB, свободно {{free}}MB",
            "encrypted_restore": f"{_E['lock']} Архив зашифрован. Укажите пароль: <code>{{prefix}}restore_with &lt;пароль&gt;</code>",
            "restore_with_usage": f"{_E['cross']} Использование: <code>{{prefix}}restore_with &lt;пароль&gt;</code>",
        },
        "en": {
            "creating_backup": f"{_E['hourglass']} <i>Creating backup...</i>",
            "backup_created": f"{_E['check']} <b>Backup created</b>",
            "backup_failed": f"{_E['cross']} <b><i>Backup failed</i></b>",
            "reply_to_backup": f"{_E['cross']} <u>Reply to a backup message</u>",
            "not_backup_file": f"{_E['cross']} <u>This is not a backup file</u>",
            "restoring": f"{_E['hourglass']} <i>Restoring...</i>",
            "restored": f"{_E['check']} Restored:",
            "no_files": f"{_E['warning']} No files to restore",
            "restore_error": f"{_E['cross']} Error:",
            "backup_settings": f"{_E['settings']} Backup Settings",
            "chat_id": "Chat ID:",
            "interval": "Interval:",
            "auto_backup": "Auto backup:",
            "last_backup": "Last backup:",
            "total_backups": "Total backups:",
            "commands": "Commands:",
            "set_interval": "Set backup interval",
            "enable_disable": "Enable/disable auto backup",
            "set_chat": "Set backup chat manually",
            "interval_set": f"{_E['check']} Interval set to {{hours}} hours",
            "interval_invalid": f"{_E['cross']} Interval must be between 1 and 168 hours",
            "auto_enabled": f"{_E['check']} Auto backup enabled",
            "auto_disabled": f"{_E['check']} Auto backup disabled",
            "chat_set": f"{_E['check']} Backup chat set to {{chat_id}}",
            "invalid_chat_id": f"{_E['cross']} Invalid chat ID",
            "unknown_command": f"{_E['cross']} Unknown command",
            "select_interval": f"{_E['clock']} Select backup interval:",
            "check_pm": f"{_E['check']} Check your PM with the bot",
            "bot_not_available": f"{_E['warning']} Bot not available. Please start a chat with the bot first.",
            "cant_send_pm": f"{_E['cross']} Can't send PM. Start a chat with the bot first",
            "processing": "🔄 Processing...",
            "group_created": f"{_E['check']} Backup group created",
            "tip_restore": "<blockquote>tip: {prefix}restore to restore a backup</blockquote>",
            "btn_restore": "🔄 Restore",
            "btn_1_hour": "1 hour",
            "btn_6_hours": "6 hours",
            "btn_12_hours": "12 hours",
            "btn_24_hours": "24 hours",
            "not_set": "Not set",
            "hours": "hours",
            "enabled": "Enabled",
            "disabled": "Disabled",
            "invalid_interval": f"{_E['cross']} Invalid interval",
            "error_processing": f"{_E['cross']} Error processing",
            "encrypted_note": f"<blockquote>{_E['lock']} Encrypted</blockquote>",
            "wrong_password": f"{_E['cross']} Wrong password or corrupted archive",
            "hash_ok": f"{_E['check']} SHA256 matches — file is intact",
            "hash_mismatch": f"{_E['cross']} <blockquote>SHA256 mismatch — file may be corrupted!</blockquote>",
            "hash_unknown": f"{_E['warning']} SHA256 not found in message caption",
            "cloud_ok": f"{_E['cloud']} {{provider}}: uploaded successfully",
            "cloud_fail": f"{_E['cross']} {{provider}}: upload failed",
            "cleanup_done": f"{_E['trash']} Deleted {{count}} old backup(s)",
            "no_backups_found": f"{_E['warning']} No backups found in the chat",
            "select_backup": f"{_E['list']} <b>Select a backup to restore:</b>",
            "delayed_scheduled": f"{_E['clock']} Backup scheduled for <b>{{time}}</b>",
            "invalid_time": f"{_E['cross']} Invalid time format. Examples: 30m, 2h, 90s",
            "unknown_arg": f"{_E['cross']} Unknown argument. Available: config, db, modules, in &lt;time&gt;, cleanup",
            "low_disk": f"{_E['warning']} Low disk space: ~{{needed}}MB needed, {{free}}MB free",
            "encrypted_restore": f"{_E['lock']} Archive is encrypted. Provide password: <code>{{prefix}}restore_with &lt;password&gt;</code>",
            "restore_with_usage": f"{_E['cross']} Usage: <code>{{prefix}}restore_with &lt;password&gt;</code>",
        },
    }
    """

    async def on_load(self) -> None:
        await super().on_load()
        self._backup_task: asyncio.Task | None = None
        self._delayed_tasks: list[asyncio.Task] = []

        defaults = {
            "backup_chat_id": None,
            "backup_interval_hours": 12,
            "last_backup_time": None,
            "backup_count": 0,
            "enable_auto_backup": True,
            "exclude_patterns": "",
            "max_backups": 0,
            "encryption_password": "",
            "cloud_provider": "none",
            "cloud_token": "",
            "cloud_also_telegram": True,
            "compression_level": 6,
            "archive_format": "zip",
            "auto_restore_config": True,
        }
        config_dict = await self.kernel.get_module_config(self.name, defaults)
        self.config.from_dict(config_dict)
        clean = {k: v for k, v in self.config.to_dict().items() if v is not None}
        if clean:
            await self.kernel.save_module_config(self.name, clean)
        self.kernel.store_module_config_schema(self.name, self.config)

        await self._schedule_backups()
        await self._auto_restore_config_on_startup()

    async def on_unload(self) -> None:
        if self._backup_task:
            self._backup_task.cancel()
        for task in self._delayed_tasks:
            task.cancel()

    def get_config(self):
        live = getattr(self.kernel, "_live_module_configs", {}).get(self.name)
        return live if live else self.config

    async def save_config(self) -> None:
        cfg = self.get_config()
        if cfg:
            data = cfg.to_dict() if hasattr(cfg, "to_dict") else cfg
            await self.kernel.save_module_config(self.name, data)

    async def _schedule_backups(self) -> None:
        if self._backup_task:
            self._backup_task.cancel()

        cfg = self.get_config()
        if not cfg or not cfg.get("enable_auto_backup", True):
            return

        interval = cfg.get("backup_interval_hours", 12) * 3600

        async def _loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    cfg_check = self.get_config()
                    if cfg_check and cfg_check.get("enable_auto_backup", True):
                        await self.send_backup(manual=False)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    await self.kernel.handle_error(e, source="backup_loop", event=None)
                    await asyncio.sleep(60)

        self._backup_task = asyncio.create_task(_loop())

    async def _auto_restore_config_on_startup(self) -> None:
        cfg = self.get_config()
        if not cfg or not cfg.get("auto_restore_config", True):
            return
        if (Path.cwd() / "config.json").exists():
            return
        backup_chat_id = cfg.get("backup_chat_id")
        if not backup_chat_id:
            return
        try:
            msgs = await self.list_backup_messages(int(backup_chat_id), limit=5)
            if not msgs:
                return
            latest = msgs[0]
            tmp = Path(tempfile.mkdtemp(prefix="mcub_autorestore_"))
            zip_path = tmp / "backup.zip"
            await latest.download_media(zip_path)
            with zipfile.ZipFile(zip_path, "r") as zf:
                for name in zf.namelist():
                    if name.endswith("config.json"):
                        zf.extract(name, tmp)
                        shutil.copy2(tmp / name, Path.cwd() / "config.json")
                        self.log.info("Auto-restored config.json from latest backup")
                        break
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception as e:
            self.log.warning(f"Auto-restore config failed: {e}")

    async def check_disk_space(
        self, paths_to_archive: list[Path]
    ) -> tuple[bool, int, int]:
        estimated = sum(p.stat().st_size for p in paths_to_archive if p.is_file())
        usage = shutil.disk_usage(Path.cwd())
        free = usage.free
        return free >= estimated * 2, estimated, free

    async def _collect_sources(self, components: str | None) -> dict[str, Path]:
        current_dir = Path.cwd()
        sources: dict[str, Path] = {}

        want_config = components in (None, "config")
        want_db = components in (None, "db")
        want_modules = components in (None, "modules")

        if want_config:
            p = current_dir / "config.json"
            if p.exists():
                sources["config.json"] = p

        if want_db:
            api_id = getattr(self.kernel, "API_ID", None)
            api_hash = getattr(self.kernel, "API_HASH", None)
            if api_id and api_hash:
                from utils.security import get_db_path

                p = Path(get_db_path(api_id, api_hash))
            else:
                p = current_dir / "userbot.db"
            if p.exists():
                sources["userbot.db"] = p

        if want_modules:
            p = current_dir / "modules_loaded"
            if p.exists():
                sources["modules_loaded"] = p

        return sources

    def _should_exclude(self, rel_path: str, exclude_patterns: list[str]) -> bool:
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(
                Path(rel_path).name, pattern
            ):
                return True
        return False

    async def create_backup_archive(
        self,
        components: str | None = None,
        archive_format: str = "zip",
        compression_level: int = 6,
        exclude_patterns: list[str] | None = None,
        encryption_password: str | None = None,
    ) -> tuple[Path, str, int, str | None]:
        """Create backup archive. Returns (path, timestamp, size_bytes, sha256)."""
        exclude_patterns = exclude_patterns or []
        temp_dir = Path(tempfile.mkdtemp(prefix="mcub_backup_"))
        backup_dir = temp_dir / "MCUB_backup"
        backup_dir.mkdir(parents=True, exist_ok=True)

        sources = await self._collect_sources(components)

        all_files: list[Path] = []
        for src in sources.values():
            if src.is_file():
                all_files.append(src)
            elif src.is_dir():
                all_files.extend(f for f in src.rglob("*") if f.is_file())

        ok, estimated, free = await self.check_disk_space(all_files)
        if not ok:
            await self.kernel.log_warning(
                f"[Backup] Low disk space: estimated {estimated // 1024}KB needed, "
                f"{free // 1024}KB free. Backup may fail."
            )

        for name, src in sources.items():
            dst = backup_dir / name
            if src.is_file():
                if not self._should_exclude(name, exclude_patterns):
                    shutil.copy2(src, dst)
            elif src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
                for item in src.rglob("*"):
                    if item.is_file():
                        rel = str(item.relative_to(src))
                        if not self._should_exclude(rel, exclude_patterns):
                            target = dst / item.relative_to(src)
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, target)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        comp_suffix = f"_{components}" if components else ""

        if archive_format == "tar.gz":
            archive_name = f"MCUB_backup{comp_suffix}_{timestamp}.tar.gz"
            archive_path = temp_dir / archive_name
            with tarfile.open(archive_path, "w:gz") as tf:
                for item in backup_dir.rglob("*"):
                    if item.is_file():
                        tf.add(item, arcname=item.relative_to(backup_dir))
        else:
            archive_name = f"MCUB_backup{comp_suffix}_{timestamp}.zip"
            archive_path = temp_dir / archive_name
            compress_type = (
                zipfile.ZIP_DEFLATED if compression_level > 0 else zipfile.ZIP_STORED
            )
            with zipfile.ZipFile(
                archive_path, "w", compress_type, compresslevel=compression_level
            ) as zf:
                for item in backup_dir.rglob("*"):
                    if item.is_file():
                        zf.write(item, item.relative_to(backup_dir))

        shutil.rmtree(backup_dir)

        sha256 = _sha256_of_file(archive_path)

        if encryption_password:
            enc_path = archive_path.with_suffix(archive_path.suffix + ".enc")
            _encrypt_file(archive_path, enc_path, encryption_password)
            archive_path.unlink()
            archive_path = enc_path

        size = archive_path.stat().st_size
        return archive_path, timestamp, size, sha256

    async def upload_to_cloud(self, file_path: Path, provider: str, token: str) -> bool:
        if provider == "yadisk":
            return await self._upload_yadisk(file_path, token)
        if provider == "gdrive":
            return await self._upload_gdrive(file_path, token)
        return False

    async def _upload_yadisk(self, file_path: Path, token: str) -> bool:
        filename = file_path.name
        remote_path = f"/MCUB_Backups/{filename}"
        headers = {"Authorization": f"OAuth {token}"}

        async with aiohttp.ClientSession(headers=headers) as session:
            await session.put(
                "https://cloud-api.yandex.net/v1/disk/resources",
                params={"path": "/MCUB_Backups"},
            )
            resp = await session.get(
                "https://cloud-api.yandex.net/v1/disk/resources/upload",
                params={"path": remote_path, "overwrite": "true"},
            )
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(
                    f"Yandex Disk get upload URL failed: {resp.status} {body}"
                )
            upload_url = (await resp.json())["href"]

            with open(file_path, "rb") as fh:
                put_resp = await session.put(upload_url, data=fh)
            if put_resp.status not in (200, 201):
                body = await put_resp.text()
                raise RuntimeError(
                    f"Yandex Disk upload failed: {put_resp.status} {body}"
                )

        return True

    async def _upload_gdrive(self, file_path: Path, token: str) -> bool:
        filename = file_path.name
        headers = {"Authorization": f"Bearer {token}"}

        async with aiohttp.ClientSession(headers=headers) as session:
            query = "name='MCUB_Backups' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            list_data = await (
                await session.get(
                    "https://www.googleapis.com/drive/v3/files",
                    params={"q": query, "fields": "files(id,name)"},
                )
            ).json()
            files = list_data.get("files", [])

            if files:
                folder_id = files[0]["id"]
            else:
                create_data = await (
                    await session.post(
                        "https://www.googleapis.com/drive/v3/files",
                        json={
                            "name": "MCUB_Backups",
                            "mimeType": "application/vnd.google-apps.folder",
                        },
                    )
                ).json()
                folder_id = create_data["id"]

            metadata = json.dumps({"name": filename, "parents": [folder_id]})
            with open(file_path, "rb") as fh:
                file_data = fh.read()

            body = (
                b"--boundary\r\n"
                b"Content-Type: application/json; charset=UTF-8\r\n\r\n"
                + metadata.encode()
                + b"\r\n--boundary\r\n"
                b"Content-Type: application/octet-stream\r\n\r\n"
                + file_data
                + b"\r\n--boundary--"
            )
            upload_resp = await session.post(
                "https://www.googleapis.com/upload/drive/v3/files",
                params={"uploadType": "multipart"},
                data=body,
                headers={
                    **headers,
                    "Content-Type": "multipart/related; boundary=boundary",
                    "Content-Length": str(len(body)),
                },
            )
            if upload_resp.status not in (200, 201):
                body_text = await upload_resp.text()
                raise RuntimeError(
                    f"Google Drive upload failed: {upload_resp.status} {body_text}"
                )

        return True

    async def rotate_old_backups(self, chat_id: int, max_count: int) -> int:
        if max_count <= 0:
            return 0

        backup_msgs = []
        async for msg in self.client.iter_messages(chat_id, limit=500):
            if msg.document and msg.file and msg.file.name:
                name = msg.file.name
                if name.startswith("MCUB_backup") and (
                    name.endswith(".zip")
                    or name.endswith(".tar.gz")
                    or name.endswith(".enc")
                ):
                    backup_msgs.append(msg)

        backup_msgs.sort(key=lambda m: m.date)

        deleted = 0
        while len(backup_msgs) > max_count:
            old = backup_msgs.pop(0)
            try:
                await self.client.delete_messages(chat_id, [old.id])
                deleted += 1
            except Exception as e:
                await self.kernel.handle_error(
                    e, source="rotate_old_backups", event=None
                )

        return deleted

    async def list_backup_messages(self, chat_id: int, limit: int = 15) -> list:
        backup_msgs = []
        async for msg in self.client.iter_messages(chat_id, limit=500):
            if msg.document and msg.file and msg.file.name:
                name = msg.file.name
                if name.startswith("MCUB_backup") and (
                    name.endswith(".zip")
                    or name.endswith(".tar.gz")
                    or name.endswith(".enc")
                ):
                    backup_msgs.append(msg)
                    if len(backup_msgs) >= limit:
                        break
        return backup_msgs

    async def send_backup(
        self,
        manual: bool = False,
        components: str | None = None,
        notify_event=None,
    ) -> bool:
        cfg = self.get_config()

        archive_format = cfg.get("archive_format", "zip") if cfg else "zip"
        compression_level = cfg.get("compression_level", 6) if cfg else 6
        encryption_password = cfg.get("encryption_password") if cfg else None
        if not encryption_password:
            encryption_password = None
        exclude_raw = cfg.get("exclude_patterns", "") if cfg else ""
        exclude_patterns = (
            [p.strip() for p in exclude_raw.split(",") if p.strip()]
            if exclude_raw
            else []
        )
        max_backups = cfg.get("max_backups", 0) if cfg else 0
        cloud_provider = cfg.get("cloud_provider", "none") if cfg else "none"
        cloud_token = cfg.get("cloud_token", "") if cfg else ""

        try:
            chat = await self.ensure_backup_chat()
            if not chat:
                return False

            archive_path, timestamp, _size, sha256 = await self.create_backup_archive(
                components=components,
                archive_format=archive_format,
                compression_level=compression_level,
                exclude_patterns=exclude_patterns,
                encryption_password=encryption_password,
            )

            caption_parts = [self.strings("tip_restore", prefix=self.get_prefix())]
            if sha256:
                caption_parts.append(
                    f"<blockquote><b>SHA256: </b><code>{sha256}</code></blockquote>"
                )
            if encryption_password:
                caption_parts.append(self.strings["encrypted_note"])
            caption = "\n".join(caption_parts)

            cloud_send_tg = True
            if cloud_provider != "none" and cloud_token:
                try:
                    await self.upload_to_cloud(
                        archive_path, cloud_provider, cloud_token
                    )
                except Exception as e:
                    await self.kernel.handle_error(e, source="cloud_upload", event=None)
                cloud_send_tg = cfg.get("cloud_also_telegram", True) if cfg else True

            if cloud_send_tg:
                buttons = [
                    [
                        self.Button.inline(
                            self.strings["btn_restore"],
                            self.restore_callback,
                            data=timestamp,
                        )
                    ]
                ]
                if self.kernel.is_bot_available():
                    try:
                        await self.kernel.bot_client.send_file(
                            chat.id,
                            archive_path,
                            caption=caption,
                            buttons=buttons,
                            parse_mode="html",
                        )
                    except Exception:
                        await self.client.send_file(
                            chat.id, archive_path, caption=caption, parse_mode="html"
                        )
                else:
                    await self.client.send_file(
                        chat.id, archive_path, caption=caption, parse_mode="html"
                    )

            archive_path.unlink(missing_ok=True)
            try:
                archive_path.parent.rmdir()
            except Exception:
                pass

            if cfg:
                cfg["last_backup_time"] = datetime.now().isoformat()
                cfg["backup_count"] = cfg.get("backup_count", 0) + 1
                await self.save_config()

            if max_backups > 0 and cloud_send_tg:
                await self.rotate_old_backups(chat.id, max_backups)

            return True

        except Exception as e:
            await self.kernel.handle_error(e, source="send_backup", event=None)
            return False

    async def ensure_backup_chat(self):
        cfg = self.get_config()
        backup_chat_id = cfg.get("backup_chat_id") if cfg else None

        if backup_chat_id:
            try:
                chat = await self.client.get_entity(int(backup_chat_id))
                if self.kernel.is_bot_available():
                    try:
                        bot_me = await self.kernel.bot_client.get_me()
                        try:
                            await self.kernel.bot_client.get_permissions(
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
                        await self.kernel.handle_error(
                            e, source="check_bot_in_chat", event=None
                        )
                return chat
            except Exception:
                if cfg:
                    cfg["backup_chat_id"] = None

        async for dialog in self.client.iter_dialogs(limit=500):
            if hasattr(dialog.entity, "title") and dialog.entity.title:
                if "backup" in dialog.entity.title.lower():
                    if cfg:
                        cfg["backup_chat_id"] = dialog.entity.id
                        await self.save_config()
                    if self.kernel.is_bot_available():
                        try:
                            bot_me = await self.kernel.bot_client.get_me()
                            await self.client(
                                InviteToChannelRequest(
                                    channel=dialog.entity.id, users=[bot_me.id]
                                )
                            )
                        except Exception as e:
                            await self.kernel.handle_error(
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
            if cfg:
                cfg["backup_chat_id"] = chat_id
                await self.save_config()
            if self.kernel.is_bot_available():
                try:
                    bot_me = await self.kernel.bot_client.get_me()
                    await self.client(
                        InviteToChannelRequest(channel=chat_id, users=[bot_me.id])
                    )
                except Exception as e:
                    await self.kernel.handle_error(
                        e, source="add_bot_to_new", event=None
                    )
            chat = await self.client.get_entity(chat_id)
            await self.client.send_message(
                chat_id, self.strings["group_created"], parse_mode="html"
            )
            await self.set_group_photo(chat_id, "https://x0.at/4Bjx.jpg")
            return chat
        except ChannelsTooMuchError:
            await self.kernel.log_warning(
                "ChannelsTooMuchError: cannot create backup group. "
                "Leave some channels or set an existing group via config."
            )
            return None
        except Exception as e:
            await self.kernel.handle_error(e, source="ensure_backup_chat", event=None)
            return None

    async def set_group_photo(self, chat_id: int, photo_url: str) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(photo_url) as resp:
                    if resp.status == 200:
                        photo_data = await resp.read()
                        content_type = resp.headers.get("Content-Type", "image/jpeg")
                        ext_map = {
                            "image/jpeg": "photo.jpg",
                            "image/jpg": "photo.jpg",
                            "image/png": "photo.png",
                            "image/webp": "photo.jpg",
                        }
                        filename = ext_map.get(
                            content_type.split(";")[0].strip(), "photo.jpg"
                        )
                        buf = io.BytesIO(photo_data)
                        buf.name = filename
                        input_file = await self.client.upload_file(buf)
                        await self.client(
                            EditPhotoRequest(channel=chat_id, photo=input_file)
                        )
        except Exception as e:
            await self.kernel.handle_error(e, source="set_group_photo", event=None)

    async def _restore_from_backup_message(
        self, backup_message, status_event, password: str | None = None
    ) -> bool:
        if (
            not backup_message
            or not getattr(backup_message, "document", None)
            or not getattr(getattr(backup_message, "file", None), "name", "")
        ):
            await status_event.edit(self.strings["not_backup_file"], parse_mode="html")
            return False

        fname = backup_message.file.name
        is_encrypted = fname.endswith(".enc")
        is_valid = fname.startswith("MCUB_backup") and (
            fname.endswith(".zip") or fname.endswith(".tar.gz") or is_encrypted
        )
        if not is_valid:
            await status_event.edit(self.strings["not_backup_file"], parse_mode="html")
            return False

        if is_encrypted and not password:
            cfg = self.get_config()
            password = cfg.get("encryption_password") if cfg else None
            if not password:
                await status_event.edit(
                    self.strings("encrypted_restore", prefix=self.get_prefix()),
                    parse_mode="html",
                )
                return False

        caption = getattr(backup_message, "message", "") or ""
        sha256_from_caption = None
        m = re.search(r"SHA256: ([a-f0-9]{64})", caption)
        if m:
            sha256_from_caption = m.group(1)

        await status_event.edit(self.strings["restoring"], parse_mode="html")
        temp_dir = Path(tempfile.mkdtemp(prefix="restore_"))
        archive_path = temp_dir / fname

        try:
            await backup_message.download_media(archive_path)

            if is_encrypted:
                try:
                    plaintext = _decrypt_file(archive_path, password)
                except ValueError:
                    await status_event.edit(
                        self.strings["wrong_password"], parse_mode="html"
                    )
                    return False
                real_name = fname[:-4]
                decrypted_path = temp_dir / real_name
                with open(decrypted_path, "wb") as fh:
                    fh.write(plaintext)
                archive_path = decrypted_path

                if sha256_from_caption:
                    actual_sha256 = _sha256_of_file(archive_path)
                    if actual_sha256 != sha256_from_caption:
                        await status_event.edit(
                            self.strings["hash_mismatch"], parse_mode="html"
                        )
                        return False

            extract_dir = temp_dir / "extracted"

            if archive_path.name.endswith(".tar.gz"):
                with tarfile.open(archive_path, "r:gz") as tf:
                    tf.extractall(extract_dir)
            else:
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(extract_dir)

            backup_dir = extract_dir / "MCUB_backup"
            if not backup_dir.exists():
                backup_dir = extract_dir

            current_dir = Path.cwd()
            restored: list[str] = []
            api_id = getattr(self.kernel, "API_ID", None)
            api_hash = getattr(self.kernel, "API_HASH", None)

            for item in backup_dir.iterdir():
                if item.name == "userbot.db" and api_id and api_hash:
                    from utils.security import get_db_path

                    target = Path(get_db_path(api_id, api_hash))
                else:
                    target = current_dir / item.name

                if target.exists():
                    backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"{target.name}_backup_{backup_time}"
                    shutil.move(str(target), current_dir / backup_name)
                    restored.append(f"{_E['box']} {item.name} → {backup_name}")

                if item.is_file():
                    shutil.copy2(item, target)
                elif item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)

                restored.append(f"{_E['check']} {item.name}")

            if restored:
                try:
                    await status_event.edit(
                        f"{self.strings['restored']}\n" + "\n".join(restored),
                        parse_mode="html",
                    )
                    cmd = await self.kernel.client.send_message(
                        status_event.chat_id,
                        f"{self.get_prefix()}restart",
                        parse_mode="html",
                    )
                    await self.kernel.process_command(cmd)
                except Exception:
                    pass
                return True

            await status_event.edit(self.strings["no_files"], parse_mode="html")
            return False

        except Exception as e:
            await self.kernel.handle_error(
                e, source="restore_handler", event=status_event
            )
            await status_event.edit(
                f"{self.strings['restore_error']} {e!s}", parse_mode="html"
            )
            return False
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @command(
        "backup",
        doc_en="create backup  [config|db|modules] [in <time>] [cleanup] [cloud]",
        doc_ru="создать бэкап  [config|db|modules] [in <time>] [cleanup] [cloud]",
    )
    async def cmd_backup(self, event) -> None:
        parser = self.args(event)
        args = parser.args

        if args and args[0] == "cleanup":
            cfg = self.get_config()
            backup_chat_id = cfg.get("backup_chat_id") if cfg else None
            if not backup_chat_id:
                await event.edit(self.strings["no_backups_found"], parse_mode="html")
                return
            await event.edit(self.strings["processing"], parse_mode="html")
            max_backups = cfg.get("max_backups", 0) if cfg else 0
            deleted = await self.rotate_old_backups(
                int(backup_chat_id), max_backups or 0
            )
            await event.edit(
                self.strings("cleanup_done", count=deleted), parse_mode="html"
            )
            return

        if args and args[0] == "cloud":
            cfg = self.get_config()
            provider = cfg.get("cloud_provider", "none") if cfg else "none"
            token = cfg.get("cloud_token", "") if cfg else ""
            if provider == "none" or not token:
                await event.edit(
                    f"{_E['cross']} Cloud provider not configured", parse_mode="html"
                )
                return
            await event.edit(self.strings["creating_backup"], parse_mode="html")
            try:
                archive_path, _, _, _ = await self.create_backup_archive(
                    compression_level=cfg.get("compression_level", 6),
                    archive_format=cfg.get("archive_format", "zip"),
                    encryption_password=cfg.get("encryption_password") or None,
                )
                await self.upload_to_cloud(archive_path, provider, token)
                archive_path.unlink(missing_ok=True)
                await event.edit(
                    self.strings("cloud_ok", provider=provider), parse_mode="html"
                )
            except Exception as e:
                await event.edit(
                    self.strings("cloud_fail", provider=provider)
                    + f"\n<code>{e}</code>",
                    parse_mode="html",
                )
            return

        if len(args) >= 2 and args[0] == "in":
            delay_secs = _parse_delay(args[1])
            if delay_secs is None:
                await event.edit(self.strings["invalid_time"], parse_mode="html")
                return
            target_time = (datetime.now() + timedelta(seconds=delay_secs)).strftime(
                "%H:%M"
            )
            await event.edit(
                self.strings("delayed_scheduled", time=target_time), parse_mode="html"
            )
            components = (
                args[2]
                if len(args) >= 3 and args[2] in ("config", "db", "modules")
                else None
            )

            async def _delayed():
                await asyncio.sleep(delay_secs)
                await self.send_backup(manual=True, components=components)

            task = asyncio.create_task(_delayed())
            self._delayed_tasks.append(task)
            return

        components = None
        if args and args[0] in ("config", "db", "modules"):
            components = args[0]
        elif args:
            await event.edit(self.strings["unknown_arg"], parse_mode="html")
            return

        await event.edit(self.strings["creating_backup"], parse_mode="html")
        if await self.send_backup(manual=True, components=components):
            await event.edit(self.strings["backup_created"], parse_mode="html")
        else:
            await event.edit(self.strings["backup_failed"], parse_mode="html")

    @command(
        "restore",
        doc_en="<reply> or list — restore from backup file or show list",
        doc_ru="<ответ> или list — восстановить из бэкапа или показать список",
    )
    async def cmd_restore(self, event) -> None:
        parser = self.args(event)
        args = parser.args

        if args and args[0] == "list":
            cfg = self.get_config()
            backup_chat_id = cfg.get("backup_chat_id") if cfg else None
            if not backup_chat_id:
                await event.edit(self.strings["no_backups_found"], parse_mode="html")
                return
            await event.edit(self.strings["processing"], parse_mode="html")
            msgs = await self.list_backup_messages(int(backup_chat_id), limit=10)
            if not msgs:
                await event.edit(self.strings["no_backups_found"], parse_mode="html")
                return

            buttons = []
            for msg in msgs:
                date_str = msg.date.strftime("%Y-%m-%d %H:%M")
                size_kb = round(msg.document.size / 1024)
                label = f"📦 {date_str} ({size_kb}KB)"
                buttons.append(
                    [
                        self.Button.inline(
                            label, self.restore_pick_callback, data=str(msg.id)
                        )
                    ]
                )

            ok, _ = await self.kernel.inline_form(
                event.chat_id,
                self.strings["select_backup"],
                buttons=buttons,
                parse_mode="html",
            )
            if ok:
                await event.delete()
            return

        if not event.is_reply:
            await event.edit(self.strings["reply_to_backup"], parse_mode="html")
            return

        reply = await event.get_reply_message()
        await self._restore_from_backup_message(reply, event)

    @command(
        "restore_with",
        doc_en="<reply> restore encrypted backup with password",
        doc_ru="<ответ> восстановить зашифрованный бэкап с паролем",
    )
    async def cmd_restore_with(self, event) -> None:
        raw = event.message.text.strip()
        parts = raw.split(maxsplit=1)
        password = parts[1].strip() if len(parts) > 1 else None

        if not password:
            await event.edit(
                self.strings("restore_with_usage", prefix=self.get_prefix()),
                parse_mode="html",
            )
            return
        if not event.is_reply:
            await event.edit(self.strings["reply_to_backup"], parse_mode="html")
            return

        reply = await event.get_reply_message()
        await self._restore_from_backup_message(reply, event, password=password)

    @callback()
    async def backup_interval_callback(self, event, data: Any | None = None) -> None:
        try:
            interval = int(data)
            if 1 <= interval <= 168:
                cfg = self.get_config()
                cfg["backup_interval_hours"] = interval
                await self.save_config()
                await self._schedule_backups()
                await event.answer(
                    self.strings("interval_set", hours=interval), alert=False
                )
                await event.edit(
                    f"{_E['clock']} {self.strings['interval']}: {interval} {self.strings['hours']}",
                    parse_mode="html",
                )
            else:
                await event.answer(self.strings["invalid_interval"], alert=True)
        except Exception as e:
            await self.kernel.handle_error(
                e, source="backup_interval_callback", event=event
            )

    @callback()
    async def restore_callback(self, event, data: Any | None = None) -> None:
        try:
            await event.answer(self.strings["processing"], alert=False)
            backup_message = await event.get_message()
            await self._restore_from_backup_message(backup_message, event)
        except Exception as e:
            await self.kernel.handle_error(e, source="restore_callback", event=event)
            await event.answer(self.strings["error_processing"], alert=True)

    @callback()
    async def restore_pick_callback(self, event, data: Any | None = None) -> None:
        try:
            msg_id = int(data)
            cfg = self.get_config()
            backup_chat_id = cfg.get("backup_chat_id") if cfg else None
            if not backup_chat_id:
                await event.answer(self.strings["no_backups_found"], alert=True)
                return
            await event.answer(self.strings["processing"], alert=False)

            msgs = await self.kernel.client.get_messages(
                int(backup_chat_id), ids=[msg_id]
            )
            if not msgs or not msgs[0]:
                await event.answer(self.strings["not_backup_file"], alert=True)
                return

            await self._restore_from_backup_message(msgs[0], event)
        except Exception as e:
            await self.kernel.handle_error(
                e, source="restore_pick_callback", event=event
            )
            await event.answer(self.strings["error_processing"], alert=True)
