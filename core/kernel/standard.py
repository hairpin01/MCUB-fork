# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

# ---- meta data ------ kernel ----------------------
# author: @Hairpin00
# description: kernel core — main Kernel class
# --- meta data end ---------------------------------
# 🌐 fork MCUBFB: https://github.com/Mitrichdfklwhcluio/MCUBFB
# 🌐 github MCUB-fork: https://github.com/hairpin01/MCUB-fork
# [🌐 https://github.com/hairpin01, 🌐 https://github.com/Mitrichdfklwhcluio, 🌐 https://t.me/HenerTLG]
# ----------------------- end -----------------------

import asyncio
import html
import importlib.util
import os
import re
import sys
import time
import traceback
from collections.abc import Callable

try:
    from telethon import events

    from core.lib.utils.exceptions import McubTelethonError
except Exception as e:
    tb = traceback.format_exc()
    print(f"E: {e}\n>: {tb}")

    sys.exit(104)
try:
    from telethon import _check_mcub_installation, install_uvloop

    _check_mcub_installation()
except Exception:
    raise McubTelethonError(
        "YOU is not install telethon-mcub, please run: 'pip install -U telethon-mcub' and 'pip uninstall telethon -y'! (or update telethon-mcub)"
    ) from None

try:
    from ..lib.base.client import ClientManager
    from ..lib.base.config import ConfigManager
    from ..lib.base.database import DatabaseManager
    from ..lib.base.permissions import CallbackPermissionManager
    from ..lib.loader.inline import InlineManager
    from ..lib.loader.inline import InlineMessage as _InlineMessage
    from ..lib.loader.loader import ModuleLoader
    from ..lib.loader.register import Register
    from ..lib.loader.repository import RepositoryManager
    from ..lib.time.cache import TTLCache
    from ..lib.time.scheduler import TaskScheduler
    from ..lib.utils.colors import Colors
    from ..lib.utils.exceptions import CommandConflictError
    from ..lib.utils.logger import (
        KernelLogger,
        setup_logging,
        setup_telegram_logging,
    )
    from core.lib.utils.case_insensitive import CaseInsensitiveDict
    from ..version import VERSION, VersionManager
except Exception as error_module:
    tb = traceback.format_exc()
    print(f"⚠️, Error loaded lib modules!\n🔎, {error_module}!\n🗓, {tb}")
    sys.exit(105)

try:
    from utils.html_parser import parse_html
    from utils.message_helpers import (
        edit_with_html,
        reply_with_html,
        send_file_with_html,
        send_with_html,
    )

    HTML_PARSER_AVAILABLE = True
except ImportError as e:
    print(f"=X HTML parser not loaded: {e}")
    HTML_PARSER_AVAILABLE = False

try:
    from utils.restart import restart_kernel
except ImportError:
    restart_kernel = None


class Kernel:
    """MCUB kernel — orchestrates clients, modules, commands and scheduler."""

    MAX_PATTERN_LENGTH = 256
    PATTERN_TIMEOUT = 0.1

    @staticmethod
    def _validate_regex_pattern(pattern: str) -> tuple[bool, str]:
        """Validate regex pattern for ReDoS protection."""
        if len(pattern) > Kernel.MAX_PATTERN_LENGTH:
            return False, f"Pattern too long (max {Kernel.MAX_PATTERN_LENGTH})"

        dangerous_patterns = [
            r"\(\.\*\)\+",
            r"\(\.\+\)\+",
            r"\(\.\*\)\*",
            r"\(\.\+\)\*",
            r"\(\.\{\d+,\}\)\+",
            r".*.*.*",
            r"\(\?\=\.\*\)",
        ]

        for danger in dangerous_patterns:
            if re.search(danger, pattern):
                return False, "Potentially dangerous regex pattern detected"

        try:
            test_pattern = re.compile(pattern)
            test_string = "x" * 1000
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError()

            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(1)

            try:
                test_pattern.match(test_string)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

        except TimeoutError:
            return False, "Pattern too complex (timeout)"
        except re.error as e:
            return False, f"Invalid regex: {e}"

        return True, "OK"

    def __init__(self) -> None:
        self.VERSION = VERSION
        self.DB_VERSION = 2
        self.start_time = time.time()

        # Module registries
        self.loaded_modules: CaseInsensitiveDict = CaseInsensitiveDict()
        self._live_module_configs: CaseInsensitiveDict = CaseInsensitiveDict()
        self.system_modules: CaseInsensitiveDict = CaseInsensitiveDict()
        self.command_handlers: dict = {}
        self.command_owners: dict = {}
        self.command_docs: dict = {}  # {cmd: {lang: description}}
        self.bot_command_handlers: dict = {}
        self.bot_command_owners: dict = {}
        self.bot_command_docs: dict = {}  # {cmd: {lang: description}}
        self.inline_handlers: dict = {}
        self.inline_handlers_owners: dict = {}
        self.callback_handlers: dict = {}
        self.aliases: dict = {}

        # Module source tracking: {module_name: {"url": str, "repo": str or None}}
        # url: direct URL if installed from URL, None if from module name
        # repo: repo URL if installed from repo, None if from direct URL
        self._module_sources: dict = {}

        # Runtime state
        self.custom_prefix = "."
        self.config: dict = {}
        self.client = None
        self.inline_bot = None
        self.catalog_cache: dict = {}
        self.pending_confirmations: dict = {}
        self.shutdown_flag = False
        self.power_save_mode = False
        self.error_load_modules = 0
        self.current_loading_module = None
        self.current_loading_module_type = None
        self.repositories: list = []
        self.middleware_chain: list = []
        self.request_middleware_chain: list = []
        self._event_middleware_ids: set[int] = set()
        self._request_middleware_ids: set[int] = set()
        self.scheduler = None
        self.log_chat_id = None
        self.log_bot_enabled = False
        self.inline_message_manager = None

        # Reconnection settings
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = -1  # -1 = infinite
        self.reconnect_delay = 5

        self.Colors = Colors

        # Paths
        self.MODULES_DIR = "modules"
        self.MODULES_LOADED_DIR = "modules_loaded"
        self.IMG_DIR = "img"
        self.LOGS_DIR = "logs"
        self.CONFIG_FILE = "config.json"
        self.BACKUP_FILE = "kernel.py.backup"
        self.ERROR_FILE = "crash.tmp"
        self.RESTART_FILE = "restart.tmp"
        self.MODULES_REPO = (
            "https://raw.githubusercontent.com/hairpin01/repo-MCUB-fork/main/"
        )
        self.UPDATE_REPO = "https://raw.githubusercontent.com/hairpin01/MCUB-fork/main/"
        self.default_repo = self.MODULES_REPO

        # Core sub-systems
        self.cache = TTLCache(max_size=500, ttl=600)
        self.register = Register(self)
        self.callback_permissions = CallbackPermissionManager()

        # Setup dirs & config early (logger depends on them)
        self.logger = setup_logging()
        self.setup_directories()
        self.check_dependencies()
        self._cfg = ConfigManager(self)
        self.load_or_create_config()

        # Subsystem managers (delegate objects)
        self._loader = ModuleLoader(self)
        self._repo = RepositoryManager(self)
        self._log = KernelLogger(self)
        self._client_mgr = ClientManager(self)
        self._inline = InlineManager(self)

        self.version_manager = VersionManager(self)
        self.db_manager = DatabaseManager(self)

        # HTML parser helpers
        self.HTML_PARSER_AVAILABLE = HTML_PARSER_AVAILABLE
        self._init_html_parser()

        # Emoji parser
        try:
            from utils.emoji_parser import emoji_parser

            self.emoji_parser = emoji_parser
        except ImportError:
            self.emoji_parser = None
            self.logger.error("=X Emoji parser not loaded")

        self.logger.debug("[Kernel] __init__ start")

    def _init_html_parser(self) -> None:
        if self.HTML_PARSER_AVAILABLE:
            try:
                self.parse_html = parse_html
                self.edit_with_html = lambda event, h, **kw: edit_with_html(
                    self, event, h, **kw
                )
                self.reply_with_html = lambda event, h, **kw: reply_with_html(
                    self, event, h, **kw
                )
                self.send_with_html = lambda cid, h, **kw: send_with_html(
                    self, self.client, cid, h, **kw
                )
                self.send_file_with_html = lambda cid, h, f, **kw: send_file_with_html(
                    self, self.client, cid, h, f, **kw
                )
                self.logger.info("=> HTML parser loaded")
            except Exception as e:
                self.logger.error(f"=X HTML parser init error: {e}")
                self.HTML_PARSER_AVAILABLE = False

        if not self.HTML_PARSER_AVAILABLE:
            self.parse_html = None
            self.edit_with_html = None
            self.reply_with_html = None
            self.send_with_html = None
            self.send_file_with_html = None

    def setup_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.logger.debug("[Kernel] setup_directories start")
        for d in (
            self.MODULES_DIR,
            self.MODULES_LOADED_DIR,
            self.IMG_DIR,
            self.LOGS_DIR,
        ):
            if not os.path.exists(d):
                self.logger.debug(f"[Kernel] Creating directory: {d}")
                os.makedirs(d)
        self.logger.debug("[Kernel] setup_directories done")

    def check_dependencies(self) -> None:
        """Check and install missing dependencies."""
        import itertools
        import subprocess
        import threading
        import time

        _REQUIREMENTS = [
            ("telethon", "telethon"),
            ("aiohttp", "aiohttp"),
            ("aiohttp-jinja2", "aiohttp_jinja2"),
            ("jinja2", "jinja2"),
            ("psutil", "psutil"),
            ("aiosqlite", "aiosqlite"),
            ("PySocks", "socks"),
        ]

        def _can_import(mod: str) -> bool:
            return importlib.util.find_spec(mod) is not None

        missing = [(pip, mod) for pip, mod in _REQUIREMENTS if not _can_import(mod)]
        if not missing:
            return

        for _, mod in missing:
            print(f"No module named '{mod}'")

        print()

        _stop = threading.Event()

        def _spin():
            frames = ["◜", "◝", "◞", "◟"]
            label = "Attempting dependencies installation... Just wait"
            for f in itertools.cycle(frames):
                if _stop.is_set():
                    break
                sys.stdout.write(f"\r{f}  {label}")
                sys.stdout.flush()
                time.sleep(0.12)
            sys.stdout.write("\r" + " " * 70 + "\r")
            sys.stdout.flush()

        t = threading.Thread(target=_spin, daemon=True)
        t.start()

        failed = []
        for pip_name, _ in missing:
            ok = False
            last_err = ""
            strategies = [
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    pip_name,
                    "--break-system-packages",
                ],
                [sys.executable, "-m", "pip", "install", pip_name],
                [sys.executable, "-m", "pip", "install", pip_name, "--user"],
                ["pip3", "install", pip_name, "--break-system-packages"],
                ["pip3", "install", pip_name],
                ["pip", "install", pip_name],
            ]
            for cmd in strategies:
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode == 0:
                    ok = True
                    break
                last_err = (res.stderr or res.stdout or "").strip()

            if not ok:
                _stop.set()
                t.join(timeout=1)
                print(f"\n✗  pip failed for '{pip_name}':")
                if last_err:
                    print("   " + last_err.replace("\n", "\n   "))
                _stop.clear()
                thread2 = threading.Thread(target=_spin, daemon=True)
                thread2.start()
                t = thread2
                failed.append(pip_name)

        _stop.set()
        t.join(timeout=1)

        if failed:
            print(f"✗  Failed to install: {', '.join(failed)}")
            print("   Run manually:  pip install " + " ".join(failed))
            sys.exit(1)

        print("✓  Dependencies installed\n")

    def cprint(self, text: str, color: str = "") -> None:
        """Print *text* wrapped in *color* and reset."""
        print(f"{color}{text}{Colors.RESET}")

    def is_admin(self, user_id: int) -> bool:
        """Return True if *user_id* matches the authorized admin."""
        result = hasattr(self, "ADMIN_ID") and user_id == self.ADMIN_ID
        self.logger.debug(f"[Kernel] is_admin user_id={user_id} result={result}")
        return result

    def should_process_command_event(self, event: Any) -> bool:
        """Accept own command messages even when Telethon loses the out flag."""
        msg = getattr(event, "message", event)
        if getattr(msg, "out", False):
            return True
        return self.is_admin(getattr(event, "sender_id", None))

    def _is_command_event_processed(self, event: Any) -> bool:
        msg = getattr(event, "message", event)
        return bool(getattr(msg, "_mcub_command_processed", False))

    def _mark_command_event_processed(self, event: Any) -> None:
        msg = getattr(event, "message", event)
        setattr(msg, "_mcub_command_processed", True)

    def is_bot_available(self) -> bool:
        """Return True if the inline bot client is connected and ready."""
        has_bot = hasattr(self, "bot_client") and self.bot_client is not None
        is_connected = has_bot and self.bot_client.is_connected()
        self.logger.debug(
            f"[Kernel] is_bot_available has_bot={has_bot} connected={is_connected}"
        )
        return is_connected

    def load_or_create_config(self) -> bool:
        """Load config.json or skip if it doesn't exist yet."""
        return self._cfg.load_or_create()

    def save_config(self) -> None:
        """Persist the current config to disk."""
        self._cfg.save()

    def setup_config(self) -> bool:
        """Apply config values to kernel attributes."""
        return self._cfg.setup()

    def first_time_setup(self) -> bool:
        """Run the interactive first-time setup wizard."""
        return self._cfg.first_time_setup()

    async def get_module_config(self, module_name: str, default: Any = None) -> Any:
        """Load a module's config from the database."""
        self.logger.debug(f"[Kernel] get_module_config module={module_name}")
        result = await self._cfg.get_module_config(module_name, default)
        self.logger.debug(
            f"[Kernel] get_module_config result keys={list(result.keys()) if isinstance(result, dict) else result}"
        )
        return result

    async def save_module_config(self, module_name: str, config_data: dict) -> bool:
        """Save a module's config to the database.

        Args:
            module_name: Name of the module.
            config_data: Configuration dictionary to save.
        """
        self.logger.debug(
            f"[Kernel] save_module_config module={module_name} data={config_data}"
        )
        try:
            result = await self._cfg.save_module_config(module_name, config_data)

            # Update live config schema
            live_cfg = self._live_module_configs.get(module_name)
            if (
                live_cfg
                and hasattr(live_cfg, "_values")
                and isinstance(config_data, dict)
            ):
                for key, value in config_data.items():
                    if key != "__mcub_config__":
                        live_cfg[key] = value

            self.logger.debug(f"[Kernel] save_module_config result={result}")
            return result
        except Exception as e:
            self.logger.error(f"[Kernel] save_module_config error: {e}")
            raise

    def store_module_config_schema(self, module_name: str, config) -> None:
        """Store a live ModuleConfig schema for UI display."""
        self._live_module_configs[module_name] = config

    async def delete_module_config(self, module_name: str) -> bool:
        """Delete a module's config from the database.

        Args:
            module_name: Name of the module.
        """
        return await self._cfg.delete_module_config(module_name)

    async def get_module_config_key(
        self, module_name: str, key: str, default: Any = None
    ) -> Any:
        """Get a single config key for a module."""
        return await self._cfg.get_key(module_name, key, default)

    async def set_module_config_key(
        self, module_name: str, key: str, value: Any
    ) -> bool:
        """Set a single config key for a module."""
        return await self._cfg.set_key(module_name, key, value)

    async def delete_module_config_key(self, module_name: str, key: str) -> bool:
        """Delete a single config key for a module."""
        return await self._cfg.delete_key(module_name, key)

    async def update_module_config(self, module_name: str, updates: dict) -> bool:
        """Merge *updates* into a module's config."""
        return await self._cfg.update(module_name, updates)

    async def get_all_module_names_with_config(self) -> list[str]:
        return await self._cfg.get_all_module_names_with_config()

    def log_debug(self, message: str) -> None:
        self.logger.debug(message)

    def log_error(self, message: str) -> None:
        """Synchronously log an error to file."""
        self.logger.error(message)

    async def send_log_message(self, text: str, file: Any = None) -> bool:
        """Send a message to the configured log chat."""
        return await self._log.send_log_message(text, file)

    async def send_error_log(
        self, error_text: str, source_file: str, message_info: str = ""
    ) -> None:
        """Format and send an error to the log chat."""
        await self._log.send_error_log(error_text, source_file, message_info)

    async def handle_error(
        self, error: Exception, source: str = "unknown", event: Any = None
    ) -> None:
        """Log an error to file and send a report to the log chat."""
        await self._log.handle_error(error, source, event)

    def save_error_to_file(self, error_text: str) -> None:
        """Append an error to logs/kernel.log."""
        self._log.save_error_to_file(error_text)

    async def log_network(self, message: str) -> None:
        """Send a network event to the log chat."""
        await self._log.log_network(message)

    async def log_error_async(self, message: str) -> None:
        """Send an error event to the log chat."""
        await self._log.log_error_async(message)

    async def log_module(self, message: str) -> None:
        """Send a module event to the log chat."""
        await self._log.log_module(message)

    async def log_error_from_exc(self, source: str = "unknown") -> None:
        """Send an error to the log chat using RichException formatting."""
        await self._log.log_error_from_exc(source)

    def load_repositories(self) -> None:
        """Load repository list from config."""
        self.logger.debug("[Kernel] load_repositories start")
        self._repo.load()
        self.logger.debug(
            f"[Kernel] load_repositories done repos={len(self.repositories)}"
        )

    async def save_repositories(self) -> None:
        """Save repository list to config."""
        await self._repo.save()

    async def save_module_sources(self) -> None:
        """Save module sources to database."""
        import json

        try:
            await self.db_set(
                "mcub_internal", "module_sources", json.dumps(self._module_sources)
            )
        except Exception as e:
            self.logger.error(f"Error saving module sources: {e}")

    async def load_module_sources(self) -> None:
        """Load module sources from database."""
        import json

        try:
            data = await self.db_get("mcub_internal", "module_sources")
            if data:
                self._module_sources = json.loads(data)
        except Exception as e:
            self.logger.error(f"Error loading module sources: {e}")

    async def add_repository(self, url: str) -> tuple:
        """Add a repository URL."""
        self.logger.debug(f"[Kernel] add_repository url={url}")
        result = await self._repo.add(url)
        self.logger.debug(f"[Kernel] add_repository result={result}")
        return result

    async def remove_repository(self, index: int) -> tuple:
        """Remove a repository by 1-based index."""
        return await self._repo.remove(index)

    async def get_repo_name(self, url: str) -> str:
        """Get the human-readable name for a repository."""
        return await self._repo.get_name(url)

    async def get_repo_modules_list(self, repo_url: str) -> list[str]:
        """Fetch the list of modules from a repository."""
        self.logger.debug(f"[Kernel] get_repo_modules_list url={repo_url}")
        result = await self._repo.get_modules_list(repo_url)
        self.logger.debug(f"[Kernel] get_repo_modules_list count={len(result)}")
        return result

    async def download_module_from_repo(
        self, repo_url: str, module_name: str
    ) -> str | None:
        """Download module source from a repository."""
        return await self._repo.download_module(repo_url, module_name)

    def set_loading_module(self, module_name: str, module_type: str) -> None:
        """Set the currently-loading module context."""
        self.current_loading_module = module_name
        self.current_loading_module_type = module_type
        self.logger.debug(f"Loading module: {module_name} ({module_type})")

    def clear_loading_module(self) -> None:
        """Clear the loading module context."""
        self.current_loading_module = None
        self.current_loading_module_type = None

    async def detected_module_type(self, module: Any) -> str:
        """Detect the registration pattern of a module."""
        return await self._loader.detect_module_type(module)

    async def load_module_from_file(
        self,
        file_path: str,
        module_name: str,
        is_system: bool = False,
        source_url: str | None = None,
        source_repo: str | None = None,
    ) -> tuple:
        """Load a module from a .py file and register it.

        Args:
            file_path: Path to the module file.
            module_name: Name of the module.
            is_system: Whether this is a system module.
            source_url: URL if installed from direct URL (dlm).
            source_repo: Repo URL if installed from repo (dlm with module name).
        """
        result = await self._loader.load_module_from_file(
            file_path, module_name, is_system
        )

        # Track source if provided
        if result[0] and (source_url or source_repo):
            self._module_sources[module_name] = {"url": source_url, "repo": source_repo}
            await self.save_module_sources()

        return result

    async def install_from_url(
        self, url: str, module_name: str | None = None, auto_dependencies: bool = True
    ) -> tuple:
        """Download and install a module from a URL."""
        return await self._loader.install_from_url(url, module_name, auto_dependencies)

    async def load_system_modules(self) -> None:
        """Load all modules from the system modules directory."""
        await self._loader.load_system_modules()

    async def load_user_modules(self) -> None:
        """Load all modules from the user modules directory."""
        await self._loader.load_user_modules()

    async def unregister_module_commands(
        self, module_name: str, force: bool = False
    ) -> None:
        """Stop loops/handlers and unregister all commands for a module.

        Args:
            module_name: Name of module to unregister.
            force: If True, allows unloading of system modules.
                  If False (default), blocks system module unload.
        """
        is_system = module_name in self.system_modules
        if is_system and not force:
            raise PermissionError(
                f"Cannot unload system module {module_name}. "
                "Use force=True to override."
            )
        await self._loader.unregister_module_commands(module_name)

    def _debug_event_builders_snapshot(self) -> list[str]:
        builders = getattr(self.client, "_event_builders", []) or []
        snapshot = []
        for event_obj, callback in builders:
            snapshot.append(
                f"{type(event_obj).__name__}:{getattr(callback, '__name__', repr(callback))}"
            )
        return snapshot

    def _event_builder_signature(self, event_obj: Any, callback: Any) -> tuple:
        return (
            type(event_obj).__name__,
            getattr(callback, "__module__", None),
            getattr(callback, "__name__", repr(callback)),
            getattr(event_obj, "pattern", None),
            getattr(event_obj, "data", None),
            getattr(event_obj, "chats", None),
            getattr(event_obj, "incoming", None),
            getattr(event_obj, "outgoing", None),
            getattr(event_obj, "from_users", None),
            getattr(event_obj, "forwards", None),
        )

    def dedupe_event_builders(self, reason: str = "manual") -> list[str]:
        """Remove duplicate Telethon bindings while keeping the newest one."""
        if not getattr(self, "client", None):
            self.logger.debug("[event_builders] skip reason=%r missing-client", reason)
            return []

        builders = list(getattr(self.client, "_event_builders", []) or [])
        before_count = len(builders)
        seen = set()
        removed = []
        dedupe_types = {"NewMessage", "MessageEdited"}

        for event_obj, callback in reversed(builders):
            event_type = type(event_obj).__name__
            if event_type not in dedupe_types:
                continue
            signature = self._event_builder_signature(event_obj, callback)
            if signature in seen:
                self.client.remove_event_handler(callback, event_obj)
                removed.append(
                    f"{event_type}:{getattr(callback, '__module__', None)}:{getattr(callback, '__name__', repr(callback))}"
                )
                continue
            seen.add(signature)

        if removed:
            removed.reverse()
            self.logger.warning(
                "[event_builders] deduped reason=%r before=%d after=%d removed=%r builders=%r",
                reason,
                before_count,
                len(getattr(self.client, "_event_builders", []) or []),
                removed,
                self._debug_event_builders_snapshot(),
            )
        else:
            self.logger.debug(
                "[event_builders] no-duplicates reason=%r count=%d",
                reason,
                before_count,
            )

        return removed

    def ensure_core_message_handlers(self, reason: str = "manual") -> None:
        """Re-register core outgoing command handlers if they disappeared."""
        if not getattr(self, "client", None):
            self.logger.debug("[core_handlers] skip reason=%r missing-client", reason)
            return

        if not hasattr(self, "_core_message_handler"):
            self.logger.debug(
                "[core_handlers] skip reason=%r missing=_core_message_handler",
                reason,
            )
            return

        builders = getattr(self.client, "_event_builders", []) or []
        has_new = any(
            cb == self._core_message_handler and type(ev).__name__ == "NewMessage"
            for ev, cb in builders
        )
        has_fallback = any(
            cb == getattr(self, "_core_fallback_message_handler", None)
            and type(ev).__name__ == "NewMessage"
            for ev, cb in builders
        )
        has_edit = any(
            cb == self._core_message_handler and type(ev).__name__ == "MessageEdited"
            for ev, cb in builders
        )

        self.logger.debug(
            "[core_handlers] ensure reason=%r has_new=%s has_fallback=%s has_edit=%s builders=%r",
            reason,
            has_new,
            has_fallback,
            has_edit,
            self._debug_event_builders_snapshot(),
        )

        force_rebind = reason.startswith("reload_")
        if force_rebind:
            before_rebind = self._debug_event_builders_snapshot()
            self.logger.debug(
                "[core_handlers] force-rebind-start reason=%r has_new=%s has_fallback=%s has_edit=%s builders=%r",
                reason,
                has_new,
                has_fallback,
                has_edit,
                before_rebind,
            )
            self.client.remove_event_handler(
                self._core_message_handler, events.NewMessage()
            )
            if hasattr(self, "_core_fallback_message_handler"):
                self.client.remove_event_handler(
                    self._core_fallback_message_handler, events.NewMessage()
                )
            self.client.remove_event_handler(
                self._core_message_handler, events.MessageEdited()
            )
            self.client.add_event_handler(
                self._core_message_handler, events.NewMessage()
            )
            if hasattr(self, "_core_fallback_message_handler"):
                self.client.add_event_handler(
                    self._core_fallback_message_handler, events.NewMessage()
                )
            self.client.add_event_handler(
                self._core_message_handler, events.MessageEdited()
            )
            self.logger.debug(
                "[core_handlers] force-rebind-done reason=%r builders_before=%r builders_after=%r",
                reason,
                before_rebind,
                self._debug_event_builders_snapshot(),
            )
            return

        if not has_new:
            self.client.add_event_handler(
                self._core_message_handler, events.NewMessage()
            )
            self.logger.warning(
                "[core_handlers] restored outgoing NewMessage handler reason=%r",
                reason,
            )

        if hasattr(self, "_core_fallback_message_handler") and not has_fallback:
            self.client.add_event_handler(
                self._core_fallback_message_handler, events.NewMessage()
            )
            self.logger.warning(
                "[core_handlers] restored fallback NewMessage handler reason=%r",
                reason,
            )

        if not has_edit:
            self.client.add_event_handler(
                self._core_message_handler, events.MessageEdited()
            )
            self.logger.warning(
                "[core_handlers] restored outgoing MessageEdited handler reason=%r",
                reason,
            )

    def ensure_registered_module_handlers(self, reason: str = "manual") -> None:
        """Re-bind tracked module watchers/events if Telethon lost them."""
        if not getattr(self, "client", None):
            return

        builders = getattr(self.client, "_event_builders", []) or []

        def _has_binding(callback, event_obj) -> bool:
            event_type = type(event_obj)
            return any(
                cb == callback and isinstance(ev, event_type) for ev, cb in builders
            )

        restored = []
        for module_name, module in {
            **self.loaded_modules,
            **self.system_modules,
        }.items():
            reg = getattr(module, "register", None)
            if reg is None:
                continue

            for entry in getattr(reg, "__watchers__", []):
                wrapper, event_obj = entry[0], entry[1]
                client = entry[2] if len(entry) > 2 else self.client
                if client is not self.client:
                    self.logger.debug(
                        "[module_handlers] skip-foreign-client reason=%r module=%r watcher=%r event=%r client=%r",
                        reason,
                        module_name,
                        getattr(wrapper, "__name__", repr(wrapper)),
                        type(event_obj).__name__,
                        type(client).__name__,
                    )
                    continue
                if _has_binding(wrapper, event_obj):
                    self.logger.debug(
                        "[module_handlers] watcher-present reason=%r module=%r watcher=%r event=%r",
                        reason,
                        module_name,
                        getattr(wrapper, "__name__", repr(wrapper)),
                        type(event_obj).__name__,
                    )
                    continue
                client.add_event_handler(wrapper, event_obj)
                self.logger.debug(
                    "[module_handlers] restored-watcher reason=%r module=%r watcher=%r event=%r",
                    reason,
                    module_name,
                    getattr(wrapper, "__name__", repr(wrapper)),
                    type(event_obj).__name__,
                )
                restored.append(
                    f"watcher:{module_name}:{getattr(wrapper, '__name__', repr(wrapper))}"
                )

            for entry in getattr(reg, "__event_handlers__", []):
                handler, event_obj = entry[0], entry[1]
                client = entry[2] if len(entry) > 2 else self.client
                if client is not self.client:
                    self.logger.debug(
                        "[module_handlers] skip-foreign-client reason=%r module=%r handler=%r event=%r client=%r",
                        reason,
                        module_name,
                        getattr(handler, "__name__", repr(handler)),
                        type(event_obj).__name__,
                        type(client).__name__,
                    )
                    continue
                if _has_binding(handler, event_obj):
                    self.logger.debug(
                        "[module_handlers] event-present reason=%r module=%r handler=%r event=%r",
                        reason,
                        module_name,
                        getattr(handler, "__name__", repr(handler)),
                        type(event_obj).__name__,
                    )
                    continue
                client.add_event_handler(handler, event_obj)
                self.logger.debug(
                    "[module_handlers] restored-event reason=%r module=%r handler=%r event=%r",
                    reason,
                    module_name,
                    getattr(handler, "__name__", repr(handler)),
                    type(event_obj).__name__,
                )
                restored.append(
                    f"event:{module_name}:{getattr(handler, '__name__', repr(handler))}"
                )

        if restored:
            self.logger.warning(
                "[module_handlers] restored reason=%r handlers=%r builders=%r",
                reason,
                restored,
                self._debug_event_builders_snapshot(),
            )
        else:
            self.logger.debug("[module_handlers] ok reason=%r", reason)

    async def _run_module_post_load(
        self, module, module_name: str, is_install: bool = False
    ) -> None:
        """Run post-load hooks: autostart loops, on_load, on_install."""
        await self._loader.run_post_load(module, module_name, is_install)

    async def get_module_metadata(self, code: str) -> dict:
        """Parse module source and extract metadata and command descriptions."""
        return await self._loader.get_module_metadata(code)

    async def get_command_description(self, module_name: str, command: str) -> str:
        """Get the description for a command registered by a module."""
        return await self._loader.get_command_description(module_name, command)

    def get_command(self, command: str) -> dict:
        """Get command info including handler, owner and docs."""
        return {
            "handler": self.command_handlers.get(command),
            "owner": self.command_owners.get(command),
            "docs": getattr(self, "command_docs", {}).get(command, {}),
        }

    def unregister_module_bot_commands(self, module_name: str) -> None:
        """Remove all bot commands registered by *module_name*."""
        to_remove = [c for c, o in self.bot_command_owners.items() if o == module_name]
        for cmd in to_remove:
            del self.bot_command_handlers[cmd]
            del self.bot_command_owners[cmd]
            self.logger.debug(f"Removed bot command: {cmd}")

    def register_inline_handler(self, pattern: str, handler: Any) -> None:
        """Register an inline query handler."""
        self._inline.register_inline_handler(pattern, handler)

    def unregister_module_inline_handlers(self, module_name: str) -> None:
        """Remove all inline handlers for a module."""
        self._inline.unregister_module_inline_handlers(module_name)

    def register_callback_handler(self, pattern: str, handler: Any) -> None:
        """Register a callback query handler."""
        self._inline.register_callback_handler(pattern, handler)

    async def inline_query_and_click(
        self, chat_id: int, query: str, **kwargs: Any
    ) -> Any:
        """Perform an inline query and click a result."""
        return await self._inline.inline_query_and_click(chat_id, query, **kwargs)

    async def send_inline(
        self, chat_id: int, query: str, buttons: Any | None = None
    ) -> bool:
        """Send an inline result using the configured bot."""
        return await self._inline.send_inline(chat_id, query, buttons)

    async def send_inline_from_config(
        self, chat_id: int, query: str, buttons: Any | None = None
    ) -> Any:
        """Send an inline result using the bot from config."""
        return await self._inline.send_inline_from_config(chat_id, query, buttons)

    async def inline_form(
        self,
        chat_id: int,
        title: str,
        fields: list[dict[str, Any]] | None = None,
        buttons: list[Any] | None = None,
        auto_send=True,
        ttl=200,
        **kwargs,
    ):
        """Create and optionally send an inline form."""
        return await self._inline.inline_form(
            chat_id, title, fields, buttons, auto_send, ttl, **kwargs
        )

    @property
    def InlineMessage(self) -> type[_InlineMessage]:
        """Get the InlineMessage class for editing/deleting inline messages.

        Example:
            ```python
            # Get an existing inline message
            msg = self.kernel.InlineMessage.get(form_id)
            if msg:
                await msg.edit("New text")
                await msg.delete()
            ```

        Returns:
            InlineMessage class.
        """
        return _InlineMessage

    def get_module_inline_commands(self, module_name: str) -> list:
        """Get inline commands registered by a module."""
        return self._inline.get_module_inline_commands(module_name)

    async def init_client(self) -> bool:
        """Initialize and authorize the main Telegram client."""
        ok = await self._client_mgr.init_client()
        if ok:
            self._sync_client_middlewares()
        return ok

    async def setup_inline_bot(self) -> bool:
        """Start the inline bot client if configured."""
        return await self._client_mgr.setup_inline_bot()

    async def safe_connect(self) -> bool:
        """Reconnect the client with exponential back-off."""
        return await self._client_mgr.safe_connect()

    async def init_db(self):
        return await self.db_manager.init_db()

    async def create_tables(self):
        await self.db_manager._create_tables()

    async def db_set(self, module: str, key: str, value: Any) -> None:
        await self.db_manager.db_set(module, key, value)

    async def db_get(self, module: str, key: str) -> Any:
        return await self.db_manager.db_get(module, key)

    async def db_delete(self, module: str, key: str) -> None:
        await self.db_manager.db_delete(module, key)

    async def db_query(self, query: str, parameters: Any) -> Any:
        return await self.db_manager.db_query(query, parameters)

    @property
    def db_conn(self):
        return self.db_manager.conn if self.db_manager else None

    def _sync_client_middlewares(self) -> None:
        """Bind kernel middleware to the active Telethon client."""
        if not self.client:
            return

        if hasattr(self.client, "add_event_middleware"):
            for middleware_func in self.middleware_chain:
                middleware_id = id(middleware_func)
                if middleware_id in self._event_middleware_ids:
                    continue
                self.client.add_event_middleware(middleware_func)
                self._event_middleware_ids.add(middleware_id)

        if hasattr(self.client, "add_request_middleware"):
            for middleware_func in self.request_middleware_chain:
                middleware_id = id(middleware_func)
                if middleware_id in self._request_middleware_ids:
                    continue
                self.client.add_request_middleware(middleware_func)
                self._request_middleware_ids.add(middleware_id)

    async def get_latest_kernel_version(self) -> str:
        return await self.version_manager.get_latest_kernel_version()

    async def _check_kernel_version_compatibility(self, code: str) -> tuple[bool, str]:
        return await self.version_manager.check_module_compatibility(code)

    async def init_scheduler(self) -> None:
        """Initialize and start the task scheduler."""
        self.scheduler = TaskScheduler(self)
        await self.scheduler.start()
        self.logger.info("Scheduler initialized")

    def add_event_middleware(self, middleware_func: Callable):
        """Register an event middleware and bind it to the Telethon client."""
        if middleware_func not in self.middleware_chain:
            self.middleware_chain.append(middleware_func)
        self._sync_client_middlewares()
        return middleware_func

    def remove_event_middleware(self, middleware_func: Callable) -> None:
        """Unregister an event middleware from the kernel and Telethon client."""
        if middleware_func in self.middleware_chain:
            self.middleware_chain.remove(middleware_func)
        if self.client and hasattr(self.client, "remove_event_middleware"):
            try:
                self.client.remove_event_middleware(middleware_func)
            except ValueError:
                pass
        self._event_middleware_ids.discard(id(middleware_func))

    def middleware(self, middleware_func: Callable):
        """Decorator alias for registering an event middleware."""
        return self.add_event_middleware(middleware_func)

    def add_middleware(self, middleware_func: Callable):
        """Backward-compatible alias for event middleware registration."""
        return self.add_event_middleware(middleware_func)

    def add_request_middleware(self, middleware_func: Callable):
        """Register a request middleware and bind it to the Telethon client."""
        if middleware_func not in self.request_middleware_chain:
            self.request_middleware_chain.append(middleware_func)
        self._sync_client_middlewares()
        return middleware_func

    def remove_request_middleware(self, middleware_func: Callable) -> None:
        """Unregister a request middleware from the kernel and Telethon client."""
        if middleware_func in self.request_middleware_chain:
            self.request_middleware_chain.remove(middleware_func)
        if self.client and hasattr(self.client, "remove_request_middleware"):
            try:
                self.client.remove_request_middleware(middleware_func)
            except ValueError:
                pass
        self._request_middleware_ids.discard(id(middleware_func))

    def request_middleware(self, middleware_func: Callable):
        """Decorator alias for request middleware registration."""
        return self.add_request_middleware(middleware_func)

    async def process_with_middleware(self, event: Any, handler: Callable) -> Any:
        """Run *event* through all middleware, then call *handler*."""
        if self.client and hasattr(self.client, "_middleware"):
            return await self.client._middleware.process(
                event,
                lambda current_event: handler(current_event),
            )

        for mw in self.middleware_chain:
            if await mw(event, handler) is False:
                return False
        return await handler(event)

    async def process_command(self, event: Any, depth: int = 0) -> bool:
        """Match and dispatch an outgoing message event to a command handler.

        Resolves aliases recursively (max depth 5).

        Returns:
            True if a handler was called.
        """
        if depth > 5:
            self.logger.error(f"Alias recursion limit reached: {event.text}")
            await self.log_error_async(f"Alias recursion limit reached: {event.text}")
            return False

        text = event.text
        self.logger.debug(
            "[process_command] depth=%d text=%r sender=%r chat=%r handlers=%d aliases=%d",
            depth,
            text,
            getattr(event, "sender_id", None),
            getattr(event, "chat_id", None),
            len(self.command_handlers),
            len(self.aliases),
        )
        if not text or not text.startswith(self.custom_prefix):
            self.logger.debug(
                "[process_command] ignored text=%r reason=no_prefix prefix=%r",
                text,
                self.custom_prefix,
            )
            return False

        cmd = (
            text[len(self.custom_prefix) :].split()[0]
            if " " in text
            else text[len(self.custom_prefix) :]
        )

        if cmd in self.aliases:
            alias = self.aliases[cmd]
            self.logger.debug(
                "[process_command] alias-hit cmd=%r target=%r text=%r",
                cmd,
                alias,
                text,
            )
            # Extract just the command name (first word) from alias for the check
            alias_cmd = alias.split()[0] if " " in alias else alias
            if alias_cmd not in self.command_handlers and alias_cmd not in self.aliases:
                self.logger.warning(
                    f"Alias '{cmd}' points to non-existent target '{alias}', "
                    f"executing '{cmd}' directly"
                )
                if cmd in self.command_handlers:
                    await self.command_handlers[cmd](event)
                    return True
                return False
            # Always use recursive text replacement for aliases with args
            args = text[len(self.custom_prefix) + len(cmd) :]
            # Use full alias (with its args) plus user args
            new_text = self.custom_prefix + alias + args
            event.text = new_text
            if hasattr(event, "message"):
                event.message.message = new_text
                event.message.text = new_text
            return await self.process_command(event, depth + 1)

        if cmd in self.command_handlers:
            handler = self.command_handlers[cmd]
            self.logger.debug(
                "[process_command] dispatch cmd=%r owner=%r handler=%r",
                cmd,
                self.command_owners.get(cmd),
                getattr(handler, "__name__", repr(handler)),
            )
            if not callable(handler):
                self.logger.warning(
                    f"Command handler for '{cmd}' is not callable, skipping"
                )
                return False
            await handler(event)
            return True

        self.logger.debug(
            "[process_command] miss cmd=%r known=%r",
            cmd,
            sorted(self.command_handlers.keys()),
        )
        return False

    async def process_bot_command(self, event: Any) -> bool:
        """Dispatch a bot command event to its registered handler.

        Returns:
            True if a handler was called.
        """
        text = event.text
        if not text or not text.startswith("/"):
            return False

        cmd = text.split()[0][1:] if " " in text else text[1:]
        if "@" in cmd:
            cmd = cmd.split("@")[0]

        if cmd in self.bot_command_handlers:
            _, handler = self.bot_command_handlers[cmd]
            await handler(event)
            return True

        return False

    async def get_user_info(self, user_id: int) -> str:
        """Return a formatted string with the user's name and username.

        Falls back to the ID string on any error.
        """
        try:
            entity = await self.client.get_entity(user_id)
            if hasattr(entity, "first_name") or hasattr(entity, "last_name"):
                name = f"{entity.first_name or ''} {entity.last_name or ''}".strip()
                return f"{name} (@{entity.username or 'no username'})"
            if hasattr(entity, "title"):
                return f"{entity.title} (chat/channel)"
            return f"ID: {user_id}"
        except Exception:
            return f"ID: {user_id}"

    async def get_thread_id(self, event: Any) -> int | None:
        """Extract the thread/topic ID from an event if present.

        Returns:
            Thread ID or None.
        """
        if not event:
            return None

        thread_id = getattr(event, "reply_to_top_id", None)
        if not thread_id and hasattr(event, "reply_to") and event.reply_to:
            thread_id = getattr(event.reply_to, "reply_to_top_id", None)

        message = getattr(event, "message", None)
        if not thread_id and message:
            thread_id = getattr(message, "reply_to_top_id", None)
        if not thread_id and message:
            reply_to = getattr(message, "reply_to", None)
            thread_id = getattr(reply_to, "reply_to_top_id", None)

        return thread_id

    def iter_topic_messages(self, entity, topic, *args, **kwargs):
        """Iterate messages from a single forum topic thread."""
        return self.client.iter_topic_messages(entity, topic, *args, **kwargs)

    async def send_to_topic(self, entity, topic, message="", **kwargs):
        """Send a message directly into a forum topic thread."""
        return await self.client.send_to_topic(entity, topic, message, **kwargs)

    async def send_file_to_topic(self, entity, topic, file, **kwargs):
        """Send a file directly into a forum topic thread."""
        return await self.client.send_file_to_topic(entity, topic, file, **kwargs)

    def iter_history_batches(self, entity, *args, **kwargs):
        """Iterate history in batches using Telethon-MCUB helpers."""
        return self.client.iter_history_batches(entity, *args, **kwargs)

    async def export_history(self, entity, *, output, **kwargs):
        """Export chat history using Telethon-MCUB high-level helpers."""
        return await self.client.export_history(entity, output=output, **kwargs)

    async def restart(self, chat_id=None, message_id=None) -> None:
        """Restart the userbot process, optionally notifying via a message."""
        await restart_kernel(self, chat_id, message_id)

    def raw_text(self, source) -> str:
        """Convert a Telethon message or plain string to HTML-safe text.

        Args:
            source: Message object or str.

        Returns:
            HTML string, never None.
        """
        try:
            if source is None:
                return ""
            if not hasattr(self, "html_converter") or self.html_converter is None:
                from utils.raw_html import RawHTMLConverter

                self.html_converter = RawHTMLConverter()
            if isinstance(source, str):
                return html.escape(source, quote=False) if source else ""
            result = self.html_converter.convert_message(source)
            return result if result is not None else ""
        except Exception as e:
            self.logger.error(f"raw_text error: {e}")
            return ""

    def format_with_html(self, text: str, entities) -> str:
        """Format a Telegram message text with entities into HTML.

        Args:
            text: Raw message text.
            entities: Telethon entity list.

        Returns:
            HTML string.
        """
        if not text:
            return ""
        if not HTML_PARSER_AVAILABLE:
            return html.escape(text, quote=False)
        from utils.html_parser import telegram_to_html

        return telegram_to_html(text, entities)

    async def send_with_emoji(self, chat_id: int, text: str, **kwargs):
        """Send a message with custom emoji support.

        Falls back to plain text when the emoji parser is unavailable or fails.

        Args:
            chat_id: Target chat.
            text: Message text, may contain custom emoji tags.

        Returns:
            Sent message object.
        """
        topic = kwargs.pop("topic", None)
        file = kwargs.pop("file", None)
        formatting_entities = kwargs.pop("formatting_entities", None)
        kwargs.pop("entities", None)

        async def send_payload(message_text: str, *, entities=None):
            payload_kwargs = dict(kwargs)
            if entities is not None:
                payload_kwargs["formatting_entities"] = entities

            if topic is not None:
                if file is not None and hasattr(self.client, "send_file_to_topic"):
                    return await self.client.send_file_to_topic(
                        chat_id,
                        topic,
                        file,
                        caption=message_text,
                        **payload_kwargs,
                    )
                if hasattr(self.client, "send_to_topic"):
                    return await self.client.send_to_topic(
                        chat_id,
                        topic,
                        message_text,
                        **payload_kwargs,
                    )

            return await self.client.send_message(
                chat_id,
                message_text,
                file=file,
                topic=topic,
                **payload_kwargs,
            )

        if not self.emoji_parser or not self.emoji_parser.is_emoji_tag(text):
            return await send_payload(text, entities=formatting_entities)

        try:
            parsed, emoji_entities = self.emoji_parser.parse_to_entities(text)
            return await send_payload(parsed, entities=emoji_entities)
        except Exception:
            fallback = (
                self.emoji_parser.remove_emoji_tags(text) if self.emoji_parser else text
            )
            return await send_payload(fallback, entities=formatting_entities)

    async def run_panel(self) -> None:
        """Start web panel. If config.json is missing, run setup wizard first."""
        host = (
            getattr(self, "web_host", None)
            or os.environ.get("MCUB_HOST")
            or (self.config.get("web_panel_host") if self.config else None)
            or "0.0.0.0"
        )
        port = int(
            getattr(self, "web_port", None)
            or os.environ.get("MCUB_PORT")
            or 0
            or (self.config.get("web_panel_port") if self.config else None)
            or 8080
        )

        # Check if we need setup wizard
        # Need setup if: no config OR config exists but no session
        needs_setup = not os.path.exists(self.CONFIG_FILE)
        if not needs_setup:
            # Check if session exists
            from utils.security import session_exists

            api_id = getattr(self, "API_ID", None)
            api_hash = getattr(self, "API_HASH", None)
            session_exists = session_exists(api_id, api_hash)
            needs_setup = not session_exists

        # If config.json doesn't exist or session is missing, start the setup wizard
        if needs_setup:
            try:
                from aiohttp import web

                from core.web.app import create_app

                done = asyncio.Event()
                app = create_app(kernel=None, setup_event=done)
                runner = web.AppRunner(app)
                await runner.setup()
                site = web.TCPSite(runner, host, port)
                await site.start()
                print(f"  🌐  Setup wizard  →  http://{host}:{port}/", flush=True)
                try:
                    await done.wait()
                finally:
                    await runner.cleanup()
                print("\nStarting kernel…\n", flush=True)
            except Exception as e:
                self.logger.error(f"Setup wizard failed: {e}")
                return

        # Start the actual web panel in the background
        try:
            from core.web.app import start_web_panel

            _task = asyncio.create_task(
                start_web_panel(self, host, port)
            )  # noqa: RUF006
        except Exception as e:
            self.logger.error(f"Failed to start web panel: {e}")
            await self.log_error_async(f"Failed to start web panel: {e}")

    async def run(self) -> None:
        """setup, connect, load modules, and run until disconnected."""
        import os
        import logging

        _true = install_uvloop()
        if not _true:
            self.logger.info("failed install uvloop")

        no_web = not getattr(self, "web_enabled", True)  # True if --no-web

        if not no_web:
            web_via_env = os.environ.get("MCUB_WEB", "0") == "1"
            web_via_config = self.config.get("web_panel_enabled", False)
            from utils.security import session_exists

            api_id = getattr(self, "API_ID", None)
            api_hash = getattr(self, "API_HASH", None)
            no_session = not session_exists(api_id, api_hash)
            no_config = not os.path.exists(self.CONFIG_FILE)

            if web_via_env or web_via_config or no_session or no_config:
                await self.run_panel()

        if not self.load_or_create_config():
            if not self.first_time_setup():
                self.logger.error("Setup failed")
                return
        logging.basicConfig(level=logging.DEBUG)

        self.load_repositories()
        await self.init_scheduler()

        if not await self.init_client():
            return
        try:
            await self.init_db()
        except ImportError:
            self.cprint(f"{Colors.YELLOW}Install: pip install aiosqlite{Colors.RESET}")
            await self.log_error_async("DB init failed: aiosqlite not installed")
        except Exception as e:
            self.cprint(f"{Colors.RED}=X DB init error: {e}{Colors.RESET}")
            await self.log_error_async(f"DB init error: {e}")

        await self.setup_inline_bot()

        if not self.config.get("inline_bot_token"):
            from core_inline.bot import InlineBot

            self.inline_bot = InlineBot(self)
            await self.inline_bot.setup()

        kernel_logger = KernelLogger(self)
        telegram_handler = setup_telegram_logging(
            self.logger,
            kernel_logger,
        )
        await telegram_handler.start()

        self._telegram_handler = telegram_handler
        self._kernel_logger = kernel_logger

        # try:
        #     from core.console.shell import Shell
        #
        #     self.shell = Shell(kernel=self)
        #     #self.shell.attach_logging(logging.getLogger())
        #     asyncio.create_task(self.shell.run())
        #     self.logger.debug("[shell] interactive shell task started")
        # except Exception as e:
        #     self.logger.error(f"[shell] failed to start interactive shell: {e}")

        async def _monitor_connection():
            """Monitor connection state and log events."""
            reconnect_count = 0
            while not self.shutdown_flag:
                try:
                    await self.client.disconnected
                    if not self.shutdown_flag and self.client.is_connected():
                        reconnect_count += 1
                        if reconnect_count <= 3 or reconnect_count % 10 == 0:
                            self.logger.warning("Connection problems detected...")
                        elif reconnect_count == 4:
                            self.logger.warning(
                                "Telegram servers may be experiencing issues"
                            )
                except asyncio.CancelledError:
                    break
                except Exception:
                    pass
                await asyncio.sleep(1)

        self._connection_monitor = asyncio.create_task(_monitor_connection())

        async def message_handler(event):
            _tele = '<tg-emoji emoji-id="5429283852684124412">🔭</tg-emoji>'
            _note = '<tg-emoji emoji-id="5334882760735598374">📝</tg-emoji>'
            msg = getattr(event, "message", event)

            if not self.should_process_command_event(event):
                self.logger.debug(
                    "[core_handlers] skip-nonoutgoing handler=message_handler text=%r sender=%r chat=%r out=%r admin=%r",
                    getattr(msg, "text", None),
                    getattr(event, "sender_id", None),
                    getattr(event, "chat_id", None),
                    getattr(msg, "out", False),
                    self.is_admin(getattr(event, "sender_id", None)),
                )
                return

            if self._is_command_event_processed(event):
                self.logger.debug(
                    "[core_handlers] skip-duplicate handler=message_handler text=%r sender=%r chat=%r",
                    getattr(msg, "text", None),
                    getattr(event, "sender_id", None),
                    getattr(event, "chat_id", None),
                )
                return

            self._mark_command_event_processed(event)
            try:
                await self.process_command(event)
            except Exception as e:
                await self.handle_error(e, source="message_handler", event=event)

                from telethon.errors import RPCError

                if isinstance(e, RPCError):
                    cmd_text = html.escape(event.text or "")
                    rpc_msg = html.escape(str(e))
                    try:
                        await event.edit(
                            f"{_tele} <b>Call <code>{cmd_text}</code> failed due to RPC error:</b> "
                            f"<code>{rpc_msg}</code>",
                            parse_mode="html",
                        )
                    except Exception as edit_err:
                        self.logger.error(
                            f"Could not edit RPC error message: {edit_err}"
                        )
                    return

                tb = traceback.format_exc()
                if len(tb) > 1000:
                    tb = tb[-1000:] + "\n...(truncated)"
                safe_cmd = html.escape(event.text or "")
                try:
                    await event.edit(
                        f"{_tele} <b>Call <code>{safe_cmd}</code> failed!</b>\n"
                        f"{_note} <b><i>Full log:</i></b>\n<pre>{tb}</pre>",
                        parse_mode="html",
                    )
                except Exception as edit_err:
                    self.logger.error(f"Could not edit error message: {edit_err}")

        async def fallback_message_handler(event):
            msg = getattr(event, "message", event)
            if not self.should_process_command_event(event):
                return
            if self._is_command_event_processed(event):
                return
            self.logger.warning(
                "[core_handlers] fallback-dispatch handler=fallback_message_handler text=%r sender=%r chat=%r out=%r admin=%r",
                getattr(msg, "text", None),
                getattr(event, "sender_id", None),
                getattr(event, "chat_id", None),
                getattr(msg, "out", False),
                self.is_admin(getattr(event, "sender_id", None)),
            )
            self._mark_command_event_processed(event)
            await self.process_command(event)

        self._core_message_handler = message_handler
        self._core_fallback_message_handler = fallback_message_handler
        self.client.add_event_handler(message_handler, events.NewMessage())
        self.client.add_event_handler(message_handler, events.MessageEdited())
        self.client.add_event_handler(fallback_message_handler, events.NewMessage())
        self.logger.debug(
            "[core_handlers] registered outgoing handlers builders=%r",
            self._debug_event_builders_snapshot(),
        )

        restart_time = None
        if os.path.exists(self.RESTART_FILE):
            try:
                with open(self.RESTART_FILE) as f:
                    data = f.read().split(",")
                if len(data) >= 2:
                    restart_chat_id = int(data[0])
                    restart_msg_id = int(data[1])
                    if len(data) >= 3:
                        restart_time = float(data[2])

                    em_alembic = '<tg-emoji emoji-id="5332654441508119011">⚗️</tg-emoji>'
                    lang = self.config.get("language", "ru")
                    _strings = {
                        "ru": {
                            "success": "Перезагрузка <b>успешна!</b>",
                            "loading": "но модули ещё загружаются...",
                        },
                        "en": {
                            "success": "Reboot <b>successful!</b>",
                            "loading": "but modules are still loading...",
                        },
                    }
                    lang_strings = _strings.get(lang, _strings["en"])
                    strings = (lang_strings["success"], lang_strings["loading"])
                    emoji = "(*.*)"
                    total_ms = (
                        round(time.time() - restart_time, 2) if restart_time else 0
                    )

                    await self.client.edit_message(
                        restart_chat_id,
                        restart_msg_id,
                        f"{em_alembic} {strings[0]} {emoji}\n"
                        f"<i>{strings[1]}</i> <b>Kernel boot:</b><code> {total_ms} </code>s",
                        parse_mode="html",
                    )
            except Exception:
                pass

        modules_start = time.time()
        await self.load_system_modules()
        await self.load_module_sources()
        await self.load_user_modules()
        modules_end = time.time()

        if hasattr(self, "bot_client") and self.bot_client:

            @self.bot_client.on(events.NewMessage(pattern="/"))
            async def bot_command_handler(event):
                try:
                    await self.process_bot_command(event)
                except Exception as e:
                    await self.handle_error(
                        e, source="bot_command_handler", event=event
                    )

        logo = (
            f"\n _    _  ____ _   _ ____\n"
            f"| \\  / |/ ___| | | | __ )\n"
            f"| |\\/| | |   | | | |  _ \\\n"
            f"| |  | | |___| |_| | |_) |\n"
            f"|_|  |_|\\____|\\___/|____/\n"
            f"Kernel loaded.\n\n"
            f"• Version: {self.VERSION}\n"
            f"• Prefix: {self.custom_prefix}\n"
        )
        if self.error_load_modules:
            logo += f"• Module load errors: {self.error_load_modules}\n"
        print(logo)
        self.logger.info("Start MCUB!")
        del logo

        if os.path.exists(self.RESTART_FILE):
            await self._handle_restart_notification(modules_start, modules_end)

        async def _run_with_reconnect():
            """Run client with automatic reconnection and logging."""
            self.reconnect_attempts = 0
            while not self.shutdown_flag:
                try:
                    if self.client.is_connected():
                        await self.client.disconnected
                    else:
                        await self.client.connect()
                        if await self.client.is_user_authorized():
                            await self.log_network("Client reconnected successfully")
                except (KeyboardInterrupt, asyncio.CancelledError):
                    break
                except ConnectionError:
                    self.reconnect_attempts += 1
                    if (
                        self.reconnect_attempts <= 3
                        or self.reconnect_attempts % 10 == 0
                    ):
                        self.logger.warning(
                            f"Connection lost, attempt {self.reconnect_attempts}, retrying..."
                        )
                    elif self.reconnect_attempts == 4:
                        self.logger.warning(
                            "Connection unstable - will continue silently"
                        )
                    await asyncio.sleep(
                        self.reconnect_delay * min(self.reconnect_attempts, 10)
                    )
                except Exception as e:
                    if "failed 5 time" in str(e) or "Task exception" in str(e):
                        continue
                    self.reconnect_attempts += 1
                    self.logger.warning(
                        f"Connection issue ({type(e).__name__}), attempt {self.reconnect_attempts}"
                    )
                    await asyncio.sleep(
                        self.reconnect_delay * min(self.reconnect_attempts, 10)
                    )

        asyncio.get_event_loop().set_exception_handler(lambda loop, ctx: None)

        try:
            await _run_with_reconnect()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Gracefully close all sessions and disconnect clients."""
        import gc

        self.shutdown_flag = True

        if hasattr(self, "_connection_monitor") and self._connection_monitor:
            self._connection_monitor.cancel()
            try:
                await self._connection_monitor
            except asyncio.CancelledError:
                pass

        if self.scheduler:
            try:
                await self.scheduler.stop()
            except Exception:
                pass

        if hasattr(self, "_telegram_handler") and self._telegram_handler:
            try:
                await self._telegram_handler.stop()
            except Exception:
                pass

        if hasattr(self, "bot_client") and self.bot_client:
            try:
                await self.bot_client.disconnect()
            except Exception:
                pass

        try:
            import aiohttp

            for obj in gc.get_objects():
                if isinstance(obj, aiohttp.ClientSession) and not obj.closed:
                    try:
                        await obj.close()
                    except Exception:
                        pass
        except Exception:
            pass

        if self.client and self.client.is_connected():
            try:
                await self.client.disconnect()
            except Exception:
                pass

        await asyncio.sleep(0)

        sys.exit(0)

    async def _handle_restart_notification(
        self, modules_start: float, modules_end: float
    ) -> None:
        """Read restart.tmp and send a post-restart status message.

        Args:
            modules_start: Timestamp when module loading began.
            modules_end: Timestamp when module loading finished.
        """
        try:
            with open(self.RESTART_FILE) as f:
                data = f.read().split(",")

            if len(data) < 3:
                os.remove(self.RESTART_FILE)
                return

            chat_id = int(data[0])
            msg_id = int(data[1])
            restart_time = float(data[2])
            thread_id = int(data[3]) if len(data) >= 4 else None

            os.remove(self.RESTART_FILE)

            me = await self.client.get_me()
            mcub = (
                '<tg-emoji emoji-id="5470015630302287916">🕳️</tg-emoji><tg-emoji emoji-id="5469945764069280010">Ⓜ️</tg-emoji><tg-emoji emoji-id="5469943045354984820">Ⓜ️</tg-emoji><tg-emoji emoji-id="5469879466954098867">Ⓜ️</tg-emoji>'
                if me.premium
                else "MCUB"
            )

            em_package = '<tg-emoji emoji-id="5399898266265475100">📦</tg-emoji>'
            em_error = '<tg-emoji emoji-id="5208923808169222461">🥀</tg-emoji>'

            kernel_s = round(modules_start - restart_time, 2)
            mod_s = round(modules_end - modules_start, 2)

            lang = self.config.get("language", "ru")
            strings = (
                {
                    "ru": {
                        "success": "Перезагрузка <b>успешна!</b>",
                        "loading": "но модули ещё загружаются...",
                        "loaded": f"Твой <b>{mcub}</b> полностью загрузился!",
                        "errors": f"Твой <b>{mcub}</b> <b>загрузился c ошибками</b> :(",
                    },
                    "en": {
                        "success": "Reboot <b>successful!</b>",
                        "loading": "but modules are still loading...",
                        "loaded": f"Your <b>{mcub}</b> is fully loaded!",
                        "errors": f"Your <b>{mcub}</b> <b>loaded with errors</b> :(",
                    },
                }
                .get(lang, {})
                .get
            )

            if not self.client.is_connected():
                return

            try:
                if not self.error_load_modules:
                    msg_text = (
                        f"{em_package} {strings('loaded')}\n"
                        f"<blockquote><b>Kernel:</b><code> {kernel_s} </code>s. "
                        f"<b>Modules:</b><code> {mod_s} </code>s.</blockquote>"
                    )
                else:
                    msg_text = (
                        f"{em_error} {strings('errors')}\n"
                        f"<blockquote><b>Kernel:</b><code> {kernel_s} </code>s. "
                        f"<b>Modules Error:</b><code> {int(self.error_load_modules)} </code>s.</blockquote>"
                    )

                try:
                    await self.client.edit_message(
                        chat_id,
                        msg_id,
                        msg_text,
                        parse_mode="html",
                    )
                except Exception:
                    send_kwargs = {"parse_mode": "html"}
                    if thread_id:
                        send_kwargs["reply_to"] = thread_id
                    await self.client.send_message(chat_id, msg_text, **send_kwargs)
            except Exception as e:
                self.logger.error(f"Could not send restart notification: {e}")
                await self.handle_error(e, source="restart")

        except (OSError, FileNotFoundError, ValueError) as e:
            self.logger.error(f"Restart file error: {e}")
            if os.path.exists(self.RESTART_FILE):
                try:
                    os.remove(self.RESTART_FILE)
                except Exception:
                    pass
        except Exception as e:
            self.logger.error(f"Unexpected restart handler error: {e}")
