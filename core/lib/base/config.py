# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

import json
import os
import sys
from typing import TYPE_CHECKING, Any

from utils.security import ensure_locked_after_write

from ..utils.colors import Colors

if TYPE_CHECKING:
    from kernel import Kernel


class ConfigManager:
    """Handles kernel config file I/O and per-module config stored in the DB."""

    def __init__(self, kernel: "Kernel") -> None:
        self.k = kernel

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
                        print(f"{Colors.RED}❌ {err}{Colors.RESET}")
                    return False
                if logger:
                    logger.debug("Config created from environment variables")
                self.setup()
                return True

            return False

        # Tighten permissions on every load (covers files created before this
        # version of the code was deployed)
        ensure_locked_after_write(k.CONFIG_FILE, getattr(k, "logger", None))

        with open(k.CONFIG_FILE, encoding="utf-8") as f:
            k.config = json.load(f)
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
            if logger:
                logger.debug("[Config] load_or_create success")
            return True

        for err in errors:
            print(f"{Colors.RED}❌ {err}{Colors.RESET}")
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

    def setup(self) -> bool:
        """Apply config values to kernel attributes.

        Returns:
            True on success, False on missing/invalid fields.
        """
        k = self.k
        try:
            k.custom_prefix = k.config.get("command_prefix", ".")
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
            print(f"{Colors.RED}❌ Config error: {e}{Colors.RESET}")
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
