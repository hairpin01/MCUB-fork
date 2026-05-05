# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01
# ---- meta data ------ kernel_core ----------------
# author: @Hairpin00
# description: Kernel core mixin — initialization, config, registries
# --- meta data end ---------------------------------
from __future__ import annotations

import ast
import html
import importlib.util
import os
import re
import sys
import time
import traceback
from collections.abc import Callable
from typing import Any

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
        "YOU is not install telethon-mcub, please run: "
        "'pip install -U telethon-mcub' and 'pip uninstall telethon -y'! "
        "(or update telethon-mcub)"
    ) from None

try:
    from core.lib.utils.case_insensitive import CaseInsensitiveDict
    from utils.strings import Strings

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
    from ..lib.utils.logger import (
        KernelLogger,
        setup_logging,
        setup_telegram_logging,
    )
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


class KernelCoreMixin:
    """Kernel core mixin — initialization, config, registries, utilities."""

    MAX_PATTERN_LENGTH = 256
    PATTERN_TIMEOUT = 0.1

    def __init__(self) -> None:
        """Initialize kernel core with registries, runtime state, and subsystems."""
        self.VERSION = VERSION
        self.DB_VERSION = 2
        self.start_time = time.time()

        # Initialize all registries, runtime state, paths, and subsystems
        self._init_registries()
        self._init_runtime()
        self._init_paths()
        self._init_subsystems()

        self.logger.debug("[Kernel] __init__ start")

    def _init_registries(self) -> None:
        """Initialize module and command registries."""
        self.loaded_modules = CaseInsensitiveDict()
        self._live_module_configs = CaseInsensitiveDict()
        self.system_modules = CaseInsensitiveDict()
        self.command_handlers = {}
        self.command_owners = {}
        self.command_docs = {}
        self.bot_command_handlers = {}
        self.bot_command_owners = {}
        self.bot_command_docs = {}
        self.inline_handlers = {}
        self.inline_handlers_owners = {}
        self.callback_handlers = {}
        self.aliases = {}
        self._pipe_vars = {}
        self._pipe_macros = {}

        # Script engine (beta)
        try:
            from core.lib.script.engine import ScriptEngine

            self.script_engine = ScriptEngine(self)
        except Exception:
            pass

        # Module source tracking: {module_name: {"url": str, "repo": str or None}}
        self._module_sources = {}

    def _init_runtime(self) -> None:
        """Initialize runtime state."""
        self.custom_prefix = "."
        self.config = {}
        self.client = None
        self.inline_bot = None
        self.catalog_cache = {}
        self.pending_confirmations = {}
        self.shutdown_flag = False
        self.power_save_mode = False
        self.error_load_modules = 0
        self.load_kernel = "kernel"
        self.current_loading_module = None
        self.current_loading_module_type = None
        self.repositories = []
        self.middleware_chain = []
        self.request_middleware_chain = []
        self._event_middleware_ids = set()
        self._request_middleware_ids = set()
        self.scheduler = None
        self.log_chat_id = None
        self.log_bot_enabled = False
        self.inline_message_manager = None

        # Reconnection settings
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = -1
        self.reconnect_delay = 5

        self.Colors = Colors

    def _init_paths(self) -> None:
        """Initialize file and directory paths."""
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

    def _init_subsystems(self) -> None:
        """Initialize core subsystems."""
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

    def _init_html_parser(self) -> None:
        """Initialize HTML parser helpers."""
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
        """Print text wrapped in color and reset."""
        print(f"{color}{text}{Colors.RESET}")

    def is_admin(self, user_id: int) -> bool:
        """Return True if user_id matches the authorized admin."""
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
        msg._mcub_command_processed = True

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
        """Save a module's config to the database."""
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
        """Delete a module's config from the database."""
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
        """Merge updates into a module's config."""
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

    # --- Repository management ---

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
        is_reload: bool = False,
        source_url: str | None = None,
        source_repo: str | None = None,
    ) -> tuple:
        """Load a module from a .py file and register it."""
        result = await self._loader.load_module_from_file(
            file_path, module_name, is_system, is_reload=is_reload
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
        """Stop loops/handlers and unregister all commands for a module."""
        is_system = module_name in self.system_modules
        if is_system and not force:
            raise PermissionError(
                f"Cannot unload system module {module_name}. "
                "Use force=True to override."
            )
        await self._loader.unregister_module_commands(module_name)

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

    def _set_event_text(self, event: Any, text: str) -> None:
        """Set event text on both the event and its inner message object."""
        event.text = text
        if hasattr(event, "message"):
            event.message.message = text
            event.message.text = text

    def raw_text(self, source) -> str:
        """Convert a Telethon message or plain string to HTML-safe text."""
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
        """Format a Telegram message text with entities into HTML."""
        if not text:
            return ""
        if not HTML_PARSER_AVAILABLE:
            return html.escape(text, quote=False)
        from utils.html_parser import telegram_to_html

        return telegram_to_html(text, entities)

    def _get_strings(self) -> Strings:
        _cache_strings = {"name": "kernel"}
        _strings = Strings(self, _cache_strings)
        return _strings

    # --- Topic/chat utilities ---

    def iter_topic_messages(self, entity, topic, *args, **kwargs):
        """Iterate messages from a single forum topic thread."""
        return self.client.iter_topic_messages(entity, topic, *args, **kwargs)

    async def send_to_topic(self, entity, topic, message="", **kwargs):
        """Send a message directly into a forum topic thread."""
        return await self.client.send_to_topic(entity, topic, message, **kwargs)

    async def send_file_to_topic(self, entity, topic, file, **kwargs):
        """Send a file directly into a forum topic thread."""
        return await self.client.send_file_to_topic(entity, topic, file, **kwargs)

    def iter_history_batches(self, entity, *args, **kwargs) -> Any:
        """Iterate history in batches using Telethon-MCUB helpers."""
        return self.client.iter_history_batches(entity, *args, **kwargs)

    async def export_history(self, entity, *, output, **kwargs) -> Any:
        """Export chat history using Telethon-MCUB high-level helpers."""
        return await self.client.export_history(entity, output=output, **kwargs)

    async def restart(self, chat_id=None, message_id=None) -> None:
        """Restart the userbot process, optionally notifying via a message."""
        await restart_kernel(self, chat_id, message_id)

    @property
    def db_conn(self):
        return self.db_manager.conn if self.db_manager else None

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

    async def get_latest_kernel_version(self) -> str:
        return await self.version_manager.get_latest_kernel_version()

    async def _check_kernel_version_compatibility(self, code: str) -> tuple[bool, str]:
        return await self.version_manager.check_module_compatibility(code)

    async def init_scheduler(self) -> None:
        """Initialize and start the task scheduler."""
        self.scheduler = TaskScheduler(self)
        await self.scheduler.start()
        self.logger.info("Scheduler initialized")
