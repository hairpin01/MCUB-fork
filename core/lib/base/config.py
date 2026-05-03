# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

import hashlib
import json
import os
import sys
from typing import TYPE_CHECKING, Any

from utils.security import ensure_locked_after_write

if TYPE_CHECKING:
    from kernel import Kernel


class ConfigManager:
    """Handles kernel config file I/O and per-module config stored in the DB."""

    BACKUP_FILENAME = ".backup-config.json"

    def __init__(self, kernel: "Kernel") -> None:
        self.k = kernel
        self._backup_api_hash = ""
        self._previous_config = {}

    def _get_api_hash(self, cfg: dict) -> str:
        """Generate hash from api_id + api_hash for backup folder naming."""
        api_id = cfg.get("api_id")
        api_hash = cfg.get("api_hash", "")
        if not api_id:
            return ""
        combined = f"{api_id}:api_hash"
        return hashlib.md5(combined.encode()).hexdigest()[:16]

    def _get_backup_path(self, cfg: dict) -> str:
        """Get backup file path ~/.MCUB/{hash}/.backup-config.json."""
        api_hash = self._get_api_hash(cfg)
        mcub_dir = os.path.expanduser(f"~/.MCUB/{api_hash}")
        return os.path.join(mcub_dir, self.BACKUP_FILENAME)

    def _save_backup(self, cfg: dict) -> bool:
        """Save config to ~/.MCUB/{hash}/.backup-config.json."""
        try:
            api_hash = self._get_api_hash(cfg)
            if not api_hash:
                return False

            mcub_dir = os.path.expanduser(f"~/.MCUB/{api_hash}")
            os.makedirs(mcub_dir, exist_ok=True)

            backup_path = os.path.join(mcub_dir, self.BACKUP_FILENAME)
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)

            ensure_locked_after_write(backup_path, getattr(self.k, "logger", None))
            self._backup_api_hash = api_hash

            logger = getattr(self.k, "logger", None)
            if logger:
                logger.debug(f"Config backup saved: {backup_path}")
            return True
        except Exception as e:
            logger = getattr(self.k, "logger", None)
            if logger:
                logger.debug(f"Error saving config backup: {e}")
            return False

    def _load_backup(self, cfg: dict) -> dict | None:
        """Load config from ~/.MCUB/{hash}/.backup-config.json."""
        # If we have api_id/api_hash, look in specific folder
        api_hash = self._get_api_hash(cfg)
        if api_hash:
            backup_path = os.path.expanduser(
                f"~/.MCUB/{api_hash}/{self.BACKUP_FILENAME}"
            )
            if os.path.exists(backup_path):
                return self._load_backup_file(backup_path)
            return None

        # No api_hash - search all folders in ~/.MCUB/
        mcub_home = os.path.expanduser("~/.MCUB")
        if not os.path.exists(mcub_home):
            return None

        # Find all backup-config.json files
        for item in os.listdir(mcub_home):
            item_path = os.path.join(mcub_home, item)
            if not os.path.isdir(item_path):
                continue
            backup_path = os.path.join(item_path, self.BACKUP_FILENAME)
            if os.path.exists(backup_path):
                result = self._load_backup_file(backup_path)
                if result:
                    return result
        return None

    def _load_backup_file(self, backup_path: str) -> dict | None:
        """Load and validate a specific backup file."""
        try:
            with open(backup_path, encoding="utf-8") as f:
                backup_cfg = json.load(f)
        except Exception as e:
            logger = getattr(self.k, "logger", None)
            if logger:
                logger.debug(f"[Config] Error loading backup {backup_path}: {e}")
            return None

        errors = self._validate_config(backup_cfg)
        if errors:
            logger = getattr(self.k, "logger", None)
            if logger:
                logger.debug(f"[Config] Backup validation errors: {errors}")
            return None

        return backup_cfg

    def _config_changed(self, old_cfg: dict, new_cfg: dict) -> bool:
        """Check if any config fields changed."""
        if not old_cfg:
            return bool(new_cfg)

        old_keys = set(old_cfg.keys())
        new_keys = set(new_cfg.keys())

        if old_keys != new_keys:
            return True

        for key in old_keys:
            if old_cfg.get(key) != new_cfg.get(key):
                return True

        return False

    def _is_valid_json(self, file_path: str) -> bool:
        """Check if file contains valid JSON."""
        try:
            with open(file_path, encoding="utf-8") as f:
                json.load(f)
            return True
        except (json.JSONDecodeError, FileNotFoundError, OSError):
            return False

    @staticmethod
    def _env_config() -> dict[str, Any]:
        """Return config values provided via environment variables.

        Supported variables:
        - MCUB_API_ID
        - MCUB_API_HASH
        - MCUB_PHONE
        """

        env_config: dict[str, Any] = {}
        if os.environ.get("MCUB_API_ID"):
            env_config["api_id"] = os.environ["MCUB_API_ID"]
        if os.environ.get("MCUB_API_HASH"):
            env_config["api_hash"] = os.environ["MCUB_API_HASH"]
        if os.environ.get("MCUB_PHONE"):
            env_config["phone"] = os.environ["MCUB_PHONE"]
        return env_config

    @staticmethod
    def _validate_config(cfg: dict[str, Any]) -> list[str]:
        """Validate required config fields and basic types.

        Returns a list of human-readable error strings; empty when valid.
        """

        errors: list[str] = []

        for field in ("api_id", "api_hash", "phone"):
            if field not in cfg or cfg.get(field) in (None, ""):
                errors.append(f"Missing required field: {field}")

        if "api_id" in cfg:
            try:
                int(cfg["api_id"])
            except (TypeError, ValueError):
                errors.append("api_id must be an integer")

        if "api_hash" in cfg and not isinstance(cfg["api_hash"], str):
            errors.append("api_hash must be a string")

        if "phone" in cfg and not isinstance(cfg["phone"], str):
            errors.append("phone must be a string")

        if "aliases" in cfg and not isinstance(cfg["aliases"], dict):
            errors.append("aliases must be a mapping")

        if "power_save_mode" in cfg and not isinstance(cfg["power_save_mode"], bool):
            errors.append("power_save_mode must be a boolean")

        return errors

    def load_or_create(self) -> bool:
        """Load config.json if it exists and contains required fields.

        Returns:
            True if config was loaded and is valid.
        """
        k = self.k
        logger = getattr(k, "logger", None)
        if logger:
            logger.debug("[Config] load_or_create start")

        env_config = self._env_config()

        if not os.path.exists(k.CONFIG_FILE):
            if logger:
                logger.debug("Config file not found: %s", k.CONFIG_FILE)

            # Allow headless configuration via environment variables
            if env_config:
                k.config = env_config
                errors = self._validate_config(k.config)
                if errors:
                    for err in errors:
                        print(f"ERROR: {err}")
                    return False
                if logger:
                    logger.debug("Config created from environment variables")
                self.setup()
                self._save_backup(k.config)
                self._previous_config = k.config.copy()
                return True

            return False

        # Load config file
        ensure_locked_after_write(k.CONFIG_FILE, getattr(k, "logger", None))

        try:
            with open(k.CONFIG_FILE, encoding="utf-8") as f:
                k.config = json.load(f)
        except json.JSONDecodeError as e:
            if logger:
                logger.debug(f"[Config] JSON decode error: {e}")

            backup_cfg = self._load_backup({})
            if backup_cfg:
                restore = (
                    input("config.json is corrupted. Load from backup? [Y/n]: ")
                    .strip()
                    .lower()
                )
                if restore in ("", "y", "yes"):
                    k.config = backup_cfg
                    self.setup()

                    # Write restored config to file
                    with open(k.CONFIG_FILE, "w", encoding="utf-8") as f:
                        json.dump(k.config, f, ensure_ascii=False, indent=2)
                    ensure_locked_after_write(k.CONFIG_FILE, k.logger)

                    self._save_backup(k.config)
                    self._previous_config = k.config.copy()
                    print("Config restored from backup")
                    return True

            print(f"Error reading config.json: {e}")
            return False

        if logger:
            logger.debug(
                "Config loaded file=%s keys=%s",
                k.CONFIG_FILE,
                sorted(k.config.keys()),
            )

        # Apply environment overrides (e.g., for containerized deployments)
        if env_config:
            k.config.update(env_config)

        errors = self._validate_config(k.config)
        if not errors:
            if logger:
                logger.debug(
                    "Config contains required fields: %s", sorted(k.config.keys())
                )
                logger.debug("Config validation succeeded")
            self.setup()

            # Save/update backup
            self._save_backup(k.config)
            self._previous_config = k.config.copy()

            if logger:
                logger.debug("[Config] load_or_create success")
            return True

        for err in errors:
            print(f"ERROR: {err}")
        if logger:
            logger.debug("[Config] load_or_create failed - errors: %s", errors)
        return False

    def save(self) -> None:
        """Write the current config dict to config.json."""
        k = self.k
        with open(k.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(k.config, f, ensure_ascii=False, indent=2)
        ensure_locked_after_write(k.CONFIG_FILE, k.logger)
        k.logger.debug("Config saved")

        # Update backup if config changed
        if hasattr(k, "config") and self._backup_api_hash:
            if self._config_changed(self._previous_config, k.config):
                self._save_backup(k.config)
                self._previous_config = k.config.copy()

    def setup(self) -> bool:
        """Apply config values to kernel attributes.

        Returns:
            True on success, False on missing/invalid fields.
        """
        k = self.k
        try:
            k.custom_prefix = k.config.get("command_prefix", ".")
            raw_owner_prefixes = k.config.get("owner_prefixes", {})
            if isinstance(raw_owner_prefixes, dict):
                k.owner_prefixes = {
                    str(owner_id): str(prefix)
                    for owner_id, prefix in raw_owner_prefixes.items()
                    if str(prefix)
                }
            else:
                k.owner_prefixes = {}
            k.aliases = k.config.get("aliases", {})
            k.power_save_mode = k.config.get("power_save_mode", False)
            k.API_ID = int(k.config["api_id"])
            k.API_HASH = str(k.config["api_hash"])
            k.PHONE = str(k.config["phone"])
            k.logger.debug(
                "Config applied prefix=%r aliases=%d power_save=%s language=%r",
                k.custom_prefix,
                len(k.aliases),
                k.power_save_mode,
                k.config.get("language"),
            )
            return True
        except (KeyError, ValueError, TypeError) as e:
            print(f"ERROR: Config error: {e}")
            return False

    def first_time_setup(self) -> bool:
        """Run the interactive first-time setup wizard.

        Writes config.json and calls setup() on success.

        Returns:
            True when config is saved successfully.
        """
        k = self.k

        print(
            """
███╗   ███╗ ██████╗██╗   ██╗██████╗       ███████╗ ██████╗ ██████╗ ██╗  ██╗
████╗ ████║██╔════╝██║   ██║██╔══██╗      ██╔════╝██╔═══██╗██╔══██╗██║ ██╔╝
██╔████╔██║██║     ██║   ██║██████╔╝█████╗█████╗  ██║   ██║██████╔╝█████╔╝
██║╚██╔╝██║██║     ██║   ██║██╔══██╗╚════╝██╔══╝  ██║   ██║██╔══██╗██╔═██╗
██║ ╚═╝ ██║╚██████╗╚██████╔╝██████╔╝      ██║     ╚██████╔╝██║  ██║██║  ██╗
╚═╝     ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝       ╚═╝      ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
1. Go to https://my.telegram.org and login
2. Click on API development tools
3. Create a new application
4. Copy your API ID and API hash
        """
        )

        while True:
            try:
                api_id_raw = input("API ID: ").strip()
                if not api_id_raw.isdigit():
                    print("API ID must be a number\n")
                    continue

                api_hash = input("API HASH: ").strip()
                if not api_hash:
                    print("API HASH cannot be empty\n")
                    continue

                phone = input("Phone number (e.g. +1234567890): ").strip()
                if not phone.startswith("+"):
                    print("Phone must start with + (e.g. +1234567890)\n")
                    continue

                k.config = {
                    "api_id": int(api_id_raw),
                    "api_hash": api_hash,
                    "phone": phone,
                    "command_prefix": ".",
                    "aliases": {},
                    "power_save_mode": False,
                    "2fa_enabled": False,
                    "healthcheck_interval": 30,
                    "developer_chat_id": None,
                    "language": "en",
                    "theme": "default",
                    "proxy": None,
                    "inline_bot_token": None,
                    "inline_bot_username": None,
                    "db_version": k.DB_VERSION,
                }
                with open(k.CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(k.config, f, ensure_ascii=False, indent=2)
                # Lock immediately after first write
                ensure_locked_after_write(k.CONFIG_FILE)
                self.setup()
                print("Config saved")
                return True

            except KeyboardInterrupt:
                print("\nSetup interrupted\n")
                sys.exit(1)

    async def get_module_config(self, module_name: str, default: Any = None) -> dict:
        """Load a module's config dict from the database.

        Args:
            module_name: Module identifier key.
            default: Returned when no config exists (defaults to ``{}``).

        Returns:
            Deserialized config dict.
        """
        k = self.k
        try:
            raw = await k.db_get("module_configs", module_name)
            k.logger.debug(
                "Loaded module config module=%r found=%s bytes=%d",
                module_name,
                bool(raw),
                len(raw) if raw else 0,
            )
            return json.loads(raw) if raw else (default if default is not None else {})
        except Exception as e:
            k.logger.error(f"Error loading config for {module_name}: {e}")
            return default if default is not None else {}

    async def save_module_config(self, module_name: str, config_data: dict) -> bool:
        """Persist a module's config dict to the database.

        Returns:
            True on success.
        """
        k = self.k
        try:
            k.logger.debug(
                "Saving module config module=%r keys=%s",
                module_name,
                sorted(config_data.keys()),
            )
            await k.db_set(
                "module_configs",
                module_name,
                json.dumps(config_data, ensure_ascii=False, indent=2),
            )
            k.logger.debug("Module config saved module=%r", module_name)
            return True
        except Exception as e:
            k.logger.error(f"Error saving config for {module_name}: {e}")
            return False

    async def delete_module_config(self, module_name: str) -> bool:
        """Delete a module's entire config from the database.

        Returns:
            True on success.
        """
        k = self.k
        try:
            k.logger.debug("Deleting module config module=%r", module_name)
            await k.db_delete("module_configs", module_name)
            k.logger.debug("Module config deleted module=%r", module_name)
            return True
        except Exception as e:
            k.logger.error(f"Error deleting config for {module_name}: {e}")
            return False

    async def get_key(self, module_name: str, key: str, default: Any = None) -> Any:
        """Get a single key from a module's config.

        Args:
            module_name: Module identifier.
            key: Config key name.
            default: Fallback value.

        Returns:
            The stored value or *default*.
        """
        config = await self.get_module_config(module_name, {})
        self.k.logger.debug(
            "Config key lookup module=%r key=%r hit=%s",
            module_name,
            key,
            key in config,
        )
        return config.get(key, default)

    async def set_key(self, module_name: str, key: str, value: Any) -> bool:
        """Set a single key in a module's config.

        Returns:
            True on success.
        """
        config = await self.get_module_config(module_name, {})
        config[key] = value
        self.k.logger.debug("Config key set module=%r key=%r", module_name, key)
        return await self.save_module_config(module_name, config)

    async def delete_key(self, module_name: str, key: str) -> bool:
        """Remove a single key from a module's config.

        Returns:
            True on success (or False if the key didn't exist).
        """
        config = await self.get_module_config(module_name, {})
        if key not in config:
            self.k.logger.debug(
                "Config key delete skipped module=%r key=%r reason=missing",
                module_name,
                key,
            )
            return False
        del config[key]
        self.k.logger.debug("Config key deleted module=%r key=%r", module_name, key)
        return await self.save_module_config(module_name, config)

    async def update(self, module_name: str, updates: dict) -> bool:
        """Merge *updates* into a module's existing config.

        Returns:
            True on success.
        """
        config = await self.get_module_config(module_name, {})
        config.update(updates)
        self.k.logger.debug(
            "Config updated module=%r updated_keys=%s",
            module_name,
            sorted(updates.keys()),
        )
        return await self.save_module_config(module_name, config)

    async def get_all_module_names_with_config(self) -> list[str]:
        """Get all module names that have a config stored in DB.

        Returns:
            List of module names with stored configs.
        """
        k = self.k
        try:
            result = await k.db_get_config_modules()
            k.logger.debug("Loaded module config names count=%d", len(result))
            return result
        except Exception as e:
            k.logger.error(f"Error getting module configs list: {e}")
            return []
