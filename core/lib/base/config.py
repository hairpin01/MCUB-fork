import json
import os
import sys
from typing import TYPE_CHECKING, Any

from ..utils.colors import Colors

if TYPE_CHECKING:
    from kernel import Kernel


class ConfigManager:
    """Handles kernel config file I/O and per-module config stored in the DB."""

    def __init__(self, kernel: "Kernel") -> None:
        self.k = kernel

    def load_or_create(self) -> bool:
        """Load config.json if it exists and contains required fields.

        Returns:
            True if config was loaded and is valid.
        """
        k = self.k
        if not os.path.exists(k.CONFIG_FILE):
            return False

        with open(k.CONFIG_FILE, "r", encoding="utf-8") as f:
            k.config = json.load(f)

        required = ("api_id", "api_hash", "phone")
        if all(k.config.get(field) for field in required):
            self.setup()
            return True

        print(f"{Colors.RED}❌ Config is damaged or incomplete{Colors.RESET}")
        return False

    def save(self) -> None:
        """Write the current config dict to config.json."""
        k = self.k
        with open(k.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(k.config, f, ensure_ascii=False, indent=2)
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
        print("""
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
        """)

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

                phone = input("Phone number (e.g. +1234567890):\n").strip()
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
                    "language": "ru",
                    "theme": "default",
                    "proxy": None,
                    "inline_bot_token": None,
                    "inline_bot_username": None,
                    "db_version": k.DB_VERSION,
                }
                with open(k.CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(k.config, f, ensure_ascii=False, indent=2)
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
            await k.db_set(
                "module_configs",
                module_name,
                json.dumps(config_data, ensure_ascii=False, indent=2),
            )
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
            await k.db_delete("module_configs", module_name)
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
        return config.get(key, default)

    async def set_key(self, module_name: str, key: str, value: Any) -> bool:
        """Set a single key in a module's config.

        Returns:
            True on success.
        """
        config = await self.get_module_config(module_name, {})
        config[key] = value
        return await self.save_module_config(module_name, config)

    async def delete_key(self, module_name: str, key: str) -> bool:
        """Remove a single key from a module's config.

        Returns:
            True on success (or False if the key didn't exist).
        """
        config = await self.get_module_config(module_name, {})
        if key not in config:
            return False
        del config[key]
        return await self.save_module_config(module_name, config)

    async def update(self, module_name: str, updates: dict) -> bool:
        """Merge *updates* into a module's existing config.

        Returns:
            True on success.
        """
        config = await self.get_module_config(module_name, {})
        config.update(updates)
        return await self.save_module_config(module_name, config)
