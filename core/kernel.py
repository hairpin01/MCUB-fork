# ---- meta data ------ kernel ----------------------
# author: @Hairpin00
# description: kernel core — main Kernel class
# --- meta data end ---------------------------------
# 🌐 fork MCUBFB: https://github.com/Mitrichdfklwhcluio/MCUBFB
# 🌐 github MCUB-fork: https://github.com/hairpin01/MCUB-fork
# [🌐 https://github.com/hairpin01, 🌐 https://github.com/Mitrichdfklwhcluio, 🌐 https://t.me/HenerTLG]
# ----------------------- end -----------------------

import time
import sys
import os
import re
import json
import random
import asyncio
import html
import traceback
import inspect
import importlib.util
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, Pattern

try:
    import uuid
    import io
    import aiohttp
    import psutil
    import socks
    import logging
    from telethon import TelegramClient, events, Button
    from telethon.tl import types as tl_types
except Exception as e:
    tb = traceback.format_exc()
    print(f"E: {e}\n" f">: {tb}")

    sys.exit(104)
try:
    from .lib.utils.colors import Colors
    from .lib.utils.exceptions import CommandConflictError
    from .lib.time.cache import TTLCache
    from .lib.time.scheduler import TaskScheduler
    from .lib.loader.register import Register
    from .lib.loader.module_config import (
        ModuleConfig,
        ConfigValue,
        Validator,
        Boolean,
        Integer,
        Float,
        String,
        Choice,
        MultiChoice,
        Secret,
        ValidationError,
    )
    from .lib.base.permissions import CallbackPermissionManager
    from .lib.base.database import DatabaseManager
    from .version import VersionManager, VERSION

    from .lib.loader.loader import ModuleLoader
    from .lib.loader.repository import RepositoryManager
    from .lib.utils.logger import KernelLogger, setup_logging
    from .lib.base.config import ConfigManager
    from .lib.base.client import ClientManager
    from .lib.loader.inline import InlineManager
    from .console.shell import Shell
except Exception as error_module:
    tb = traceback.format_exc()
    print("⚠️, Error loaded lib modules!\n" f"🔎, {error_module}!\n" f"🗓, {tb}")
    sys.exit(105)

try:
    from utils.html_parser import parse_html
    from utils.message_helpers import (
        edit_with_html,
        reply_with_html,
        send_with_html,
        send_file_with_html,
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

    def __init__(self) -> None:
        self.VERSION = VERSION
        self.DB_VERSION = 2
        self.start_time = time.time()

        # Module registries
        self.loaded_modules: dict = {}
        self.system_modules: dict = {}
        self.command_handlers: dict = {}
        self.command_owners: dict = {}
        self.bot_command_handlers: dict = {}
        self.bot_command_owners: dict = {}
        self.inline_handlers: dict = {}
        self.inline_handlers_owners: dict = {}
        self.callback_handlers: dict = {}
        self.aliases: dict = {}

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
        self.scheduler = None
        self.log_chat_id = None
        self.log_bot_enabled = False
        self.inline_message_manager = None

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
        self.setup_directories()
        self._cfg = ConfigManager(self)
        self.load_or_create_config()
        self.logger = setup_logging()

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
        for d in (
            self.MODULES_DIR,
            self.MODULES_LOADED_DIR,
            self.IMG_DIR,
            self.LOGS_DIR,
        ):
            if not os.path.exists(d):
                os.makedirs(d)

    def cprint(self, text: str, color: str = "") -> None:
        """Print *text* wrapped in *color* and reset."""
        print(f"{color}{text}{Colors.RESET}")

    def is_admin(self, user_id: int) -> bool:
        """Return True if *user_id* matches the authorized admin."""
        return hasattr(self, "ADMIN_ID") and user_id == self.ADMIN_ID

    def is_bot_available(self) -> bool:
        """Return True if the inline bot client is connected and ready."""
        return (
            hasattr(self, "bot_client")
            and self.bot_client is not None
            and self.bot_client.is_connected()
        )

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

    async def get_module_config(self, module_name: str, default=None):
        """Load a module's config from the database."""
        return await self._cfg.get_module_config(module_name, default)

    async def save_module_config(self, module_name: str, config_data: dict) -> bool:
        """Save a module's config to the database."""
        return await self._cfg.save_module_config(module_name, config_data)

    async def delete_module_config(self, module_name: str) -> bool:
        """Delete a module's config from the database."""
        return await self._cfg.delete_module_config(module_name)

    async def get_module_config_key(self, module_name: str, key: str, default=None):
        """Get a single config key for a module."""
        return await self._cfg.get_key(module_name, key, default)

    async def set_module_config_key(self, module_name: str, key: str, value) -> bool:
        """Set a single config key for a module."""
        return await self._cfg.set_key(module_name, key, value)

    async def delete_module_config_key(self, module_name: str, key: str) -> bool:
        """Delete a single config key for a module."""
        return await self._cfg.delete_key(module_name, key)

    async def update_module_config(self, module_name: str, updates: dict) -> bool:
        """Merge *updates* into a module's config."""
        return await self._cfg.update(module_name, updates)

    def log_debug(self, message: str) -> None:
        self.logger.debug(message)

    def log_error(self, message: str) -> None:
        """Synchronously log an error to file."""
        self.logger.error(message)

    async def send_log_message(self, text: str, file=None) -> bool:
        """Send a message to the configured log chat."""
        return await self._log.send_log_message(text, file)

    async def send_error_log(
        self, error_text: str, source_file: str, message_info: str = ""
    ) -> None:
        """Format and send an error to the log chat."""
        await self._log.send_error_log(error_text, source_file, message_info)

    async def handle_error(
        self, error: Exception, source: str = "unknown", event=None
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

    def load_repositories(self) -> None:
        """Load repository list from config."""
        self._repo.load()

    async def save_repositories(self) -> None:
        """Save repository list to config."""
        await self._repo.save()

    async def add_repository(self, url: str) -> tuple:
        """Add a repository URL."""
        return await self._repo.add(url)

    async def remove_repository(self, index) -> tuple:
        """Remove a repository by 1-based index."""
        return await self._repo.remove(index)

    async def get_repo_name(self, url: str) -> str:
        """Get the human-readable name for a repository."""
        return await self._repo.get_name(url)

    async def get_repo_modules_list(self, repo_url: str) -> list:
        """Fetch the list of modules from a repository."""
        return await self._repo.get_modules_list(repo_url)

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

    async def detected_module_type(self, module) -> str:
        """Detect the registration pattern of a module."""
        return await self._loader.detect_module_type(module)

    async def load_module_from_file(
        self, file_path: str, module_name: str, is_system: bool = False
    ) -> tuple:
        """Load a module from a .py file and register it."""
        return await self._loader.load_module_from_file(
            file_path, module_name, is_system
        )

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

    def unregister_module_commands(self, module_name: str) -> None:
        """Stop loops/handlers and unregister all commands for a module."""
        self._loader.unregister_module_commands(module_name)

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

    def register_command(self, pattern: str, func=None):
        """Register a userbot command, raising CommandConflictError on collisions.

        Args:
            pattern: Command pattern string (with or without prefix).
            func: Handler function; if None, returns a decorator.
        """
        cmd = pattern.lstrip("^\\" + self.custom_prefix).rstrip("$")

        if self.current_loading_module is None:
            raise ValueError("No loading module context set")

        if cmd in self.command_handlers:
            owner = self.command_owners.get(cmd)
            kind = "system" if owner in self.system_modules else "user"
            raise CommandConflictError(
                f"Command '{cmd}' already registered by '{owner}'",
                conflict_type=kind,
                command=cmd,
            )

        def _register(f):
            self.command_handlers[cmd] = f
            self.command_owners[cmd] = self.current_loading_module
            return f

        return _register(func) if func else _register

    def register_command_bot(self, pattern: str, func=None):
        """Register a bot command (starting with /).

        Args:
            pattern: Command pattern, with or without leading /.
            func: Handler; if None, returns a decorator.
        """
        if not pattern.startswith("/"):
            pattern = "/" + pattern
        cmd = pattern.lstrip("/").split()[0] if " " in pattern else pattern.lstrip("/")

        if self.current_loading_module is None:
            raise ValueError("No loading module context set")

        if cmd in self.bot_command_handlers:
            owner = self.bot_command_owners.get(cmd)
            raise CommandConflictError(
                f"Bot command '/{cmd}' already registered by '{owner}'",
                conflict_type="bot",
                command=cmd,
            )

        def _register(f):
            self.bot_command_handlers[cmd] = (pattern, f)
            self.bot_command_owners[cmd] = self.current_loading_module
            return f

        return _register(func) if func else _register

    def unregister_module_bot_commands(self, module_name: str) -> None:
        """Remove all bot commands registered by *module_name*."""
        to_remove = [c for c, o in self.bot_command_owners.items() if o == module_name]
        for cmd in to_remove:
            del self.bot_command_handlers[cmd]
            del self.bot_command_owners[cmd]
            self.logger.debug(f"Removed bot command: {cmd}")

    def register_inline_handler(self, pattern: str, handler) -> None:
        """Register an inline query handler."""
        self._inline.register_inline_handler(pattern, handler)

    def unregister_module_inline_handlers(self, module_name: str) -> None:
        """Remove all inline handlers for a module."""
        self._inline.unregister_module_inline_handlers(module_name)

    def register_callback_handler(self, pattern, handler) -> None:
        """Register a callback query handler."""
        self._inline.register_callback_handler(pattern, handler)

    async def inline_query_and_click(self, chat_id, query, **kwargs):
        """Perform an inline query and click a result."""
        return await self._inline.inline_query_and_click(chat_id, query, **kwargs)

    async def send_inline(self, chat_id: int, query: str, buttons=None) -> bool:
        """Send an inline result using the configured bot."""
        return await self._inline.send_inline(chat_id, query, buttons)

    async def send_inline_from_config(self, chat_id: int, query: str, buttons=None):
        """Send an inline result using the bot from config."""
        return await self._inline.send_inline_from_config(chat_id, query, buttons)

    async def inline_form(
        self,
        chat_id,
        title,
        fields=None,
        buttons=None,
        auto_send=True,
        ttl=200,
        **kwargs,
    ):
        """Create and optionally send an inline form."""
        return await self._inline.inline_form(
            chat_id, title, fields, buttons, auto_send, ttl, **kwargs
        )

    async def init_client(self) -> bool:
        """Initialize and authorize the main Telegram client."""
        return await self._client_mgr.init_client()

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

    async def db_set(self, module: str, key: str, value) -> None:
        await self.db_manager.db_set(module, key, value)

    async def db_get(self, module: str, key: str):
        return await self.db_manager.db_get(module, key)

    async def db_delete(self, module: str, key: str) -> None:
        await self.db_manager.db_delete(module, key)

    async def db_query(self, query: str, parameters):
        return await self.db_manager.db_query(query, parameters)

    @property
    def db_conn(self):
        return self.db_manager.conn if self.db_manager else None

    async def get_latest_kernel_version(self) -> str:
        return await self.version_manager.get_latest_kernel_version()

    async def _check_kernel_version_compatibility(self, code: str) -> Tuple[bool, str]:
        return await self.version_manager.check_module_compatibility(code)

    async def init_scheduler(self) -> None:
        """Initialize and start the task scheduler."""
        self.scheduler = TaskScheduler(self)
        await self.scheduler.start()
        self.logger.info("Scheduler initialized")

    def add_middleware(self, middleware_func: Callable) -> None:
        """Register a middleware function in the processing chain."""
        self.middleware_chain.append(middleware_func)

    async def process_with_middleware(self, event, handler: Callable):
        """Run *event* through all middleware, then call *handler*."""
        for mw in self.middleware_chain:
            if await mw(event, handler) is False:
                return False
        return await handler(event)

    async def process_command(self, event, depth: int = 0) -> bool:
        """Match and dispatch an outgoing message event to a command handler.

        Resolves aliases recursively (max depth 5).

        Returns:
            True if a handler was called.
        """
        if depth > 5:
            self.logger.error(f"Alias recursion limit reached: {event.text}")
            return False

        text = event.text
        if not text or not text.startswith(self.custom_prefix):
            return False

        cmd = (
            text[len(self.custom_prefix) :].split()[0]
            if " " in text
            else text[len(self.custom_prefix) :]
        )

        if cmd in self.aliases:
            alias = self.aliases[cmd]
            if alias in self.command_handlers:
                await self.command_handlers[alias](event)
                return True
            args = text[len(self.custom_prefix) + len(cmd) :]
            new_text = self.custom_prefix + alias + args
            event.text = new_text
            if hasattr(event, "message"):
                event.message.message = new_text
                event.message.text = new_text
            return await self.process_command(event, depth + 1)

        if cmd in self.command_handlers:
            await self.command_handlers[cmd](event)
            return True

        return False

    async def process_bot_command(self, event) -> bool:
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

    async def get_thread_id(self, event) -> int | None:
        """Extract the thread/topic ID from an event if present.

        Returns:
            Thread ID or None.
        """
        if not event:
            return None
        thread_id = None
        if hasattr(event, "reply_to") and event.reply_to:
            thread_id = getattr(event.reply_to, "reply_to_top_id", None)
        if not thread_id and hasattr(event, "message"):
            thread_id = getattr(event.message, "reply_to_top_id", None)
        return thread_id

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
        if not self.emoji_parser or not self.emoji_parser.is_emoji_tag(text):
            return await self.client.send_message(chat_id, text, **kwargs)
        try:
            parsed, entities = self.emoji_parser.parse_to_entities(text)
            input_peer = await self.client.get_input_entity(chat_id)
            return await self.client.send_message(
                input_peer,
                parsed,
                entities=entities,
                **{k: v for k, v in kwargs.items() if k != "entities"},
            )
        except Exception as e:
            fallback = (
                self.emoji_parser.remove_emoji_tags(text) if self.emoji_parser else text
            )
            return await self.client.send_message(chat_id, fallback, **kwargs)

    def run_panel(self) -> None:
        """Start the aiohttp web panel as a background asyncio task.

        Host and port are resolved from (highest priority first):
          1. kernel.web_host / kernel.web_port  (set by __main__.py CLI args)
          2. MCUB_HOST / MCUB_PORT environment variables
          3. config.json  →  web_panel_host / web_panel_port
          4. Hard-coded defaults: 127.0.0.1 / 8080
        """
        import os

        try:
            from core.web.app import start_web_panel
        except Exception as e:
            self.logger.error(f"Failed to import web panel: {e}")
            return

        host = (
            getattr(self, "web_host", None)
            or os.environ.get("MCUB_HOST")
            or self.config.get("web_panel_host", "127.0.0.1")
        )
        port = int(
            getattr(self, "web_port", None)
            or os.environ.get("MCUB_PORT", 0)
            or self.config.get("web_panel_port", 8080)
        )

        try:
            asyncio.create_task(start_web_panel(self, host, port))
        except Exception as e:
            self.logger.error(f"Failed to start web panel: {e}")

    async def run(self) -> None:
        """setup, connect, load modules, and run until disconnected."""
        import os

        web_enabled = getattr(self, "web_enabled", False) or (
            os.environ.get("MCUB_WEB", "0") == "1"
        )

        if not self.load_or_create_config():
            if web_enabled:
                # Setup wizard already ran in __main__.py (standalone mode).
                # Re-load the freshly written config.json.
                if not self.load_or_create_config():
                    self.logger.error("Config still missing after web setup")
                    return
            else:
                if not self.first_time_setup():
                    self.logger.error("Setup failed")
                    return

        self.load_repositories()
        logging.basicConfig(level=logging.INFO)
        await self.init_scheduler()

        if not await self.init_client():
            return

        # Start the web panel only when explicitly requested
        if web_enabled or self.config.get("web_panel_enabled", False):
            self.run_panel()

        # self.shell = Shell(kernel=self)
        # self.shell.attach_logging()
        # self.shell.attach_stderr()
        # asyncio.ensure_future(self.shell.run())
        try:
            await self.init_db()
        except ImportError:
            self.cprint(f"{Colors.YELLOW}Install: pip install aiosqlite{Colors.RESET}")
        except Exception as e:
            self.cprint(f"{Colors.RED}=X DB init error: {e}{Colors.RESET}")

        await self.setup_inline_bot()

        if not self.config.get("inline_bot_token"):
            from core_inline.bot import InlineBot

            self.inline_bot = InlineBot(self)
            await self.inline_bot.setup()

        @self.client.on(events.NewMessage(outgoing=True))
        async def message_handler(event):
            _tele = '<tg-emoji emoji-id="5429283852684124412">🔭</tg-emoji>'
            _note = '<tg-emoji emoji-id="5334882760735598374">📝</tg-emoji>'
            try:
                await self.process_command(event)
            except Exception as e:
                await self.handle_error(e, source="message_handler", event=event)
                tb = traceback.format_exc()
                if len(tb) > 1000:
                    tb = tb[-1000:] + "\n...(truncated)"
                try:
                    await event.edit(
                        f"{_tele} <b>Call <code>{event.text}</code> failed!</b>\n\n"
                        f"{_note} <b><i>Full log:</i></b>\n<pre>{tb}</pre>",
                        parse_mode="html",
                    )
                except Exception as edit_err:
                    self.logger.error(f"Could not edit error message: {edit_err}")

        modules_start = time.time()
        await self.load_system_modules()
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

        await self.client.run_until_disconnected()

    async def _handle_restart_notification(
        self, modules_start: float, modules_end: float
    ) -> None:
        """Read restart.tmp and send a post-restart status message.

        Args:
            modules_start: Timestamp when module loading began.
            modules_end: Timestamp when module loading finished.
        """
        try:
            with open(self.RESTART_FILE, "r") as f:
                data = f.read().split(",")

            if len(data) < 3:
                os.remove(self.RESTART_FILE)
                return

            chat_id = int(data[0])
            msg_id = int(data[1])
            restart_time = float(data[2])
            thread_id = int(data[3]) if len(data) >= 4 and data[3] else None

            os.remove(self.RESTART_FILE)

            me = await self.client.get_me()
            mcub = (
                '<tg-emoji emoji-id="5470015630302287916">🔮</tg-emoji>' * 4
                if me.premium
                else "MCUB"
            )

            emoji = random.choice(
                [
                    "ಠ_ಠ",
                    "( ཀ ʖ̯ ཀ)",
                    "(◕‿◕✿)",
                    "(つ･･)つ",
                    "༼つ◕_◕༽つ",
                    "(•_•)",
                    "☜(ﾟヮﾟ☜)",
                    "(☞ﾟヮﾟ)☞",
                    "ʕ•ᴥ•ʔ",
                    "(づ￣ ³￣)づ",
                ]
            )

            em_alembic = '<tg-emoji emoji-id="5332654441508119011">⚗️</tg-emoji>'
            em_package = '<tg-emoji emoji-id="5399898266265475100">📦</tg-emoji>'
            em_error = '<tg-emoji emoji-id="5208923808169222461">🥀</tg-emoji>'

            total_ms = round((time.time() - restart_time) * 1000, 2)
            mod_ms = round((modules_end - modules_start) * 1000, 2)

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
                sms = await self.client.edit_message(
                    chat_id,
                    msg_id,
                    f"{em_alembic} {strings('success')} {emoji}\n"
                    f"<i>{strings('loading')}</i> <b>KLB:</b> <code>{total_ms} ms</code>",
                    parse_mode="html",
                )
                await asyncio.sleep(1)

                if not self.error_load_modules:
                    await sms.edit(
                        f"{em_package} {strings('loaded')}\n"
                        f"<blockquote><b>Kernel:</b> <code>{total_ms} ms</code>. "
                        f"<b>Modules:</b> <code>{mod_ms} ms</code>.</blockquote>",
                        parse_mode="html",
                    )
                else:
                    await sms.edit(
                        f"{em_error} {strings('errors')}\n"
                        f"<blockquote><b>Kernel:</b> <code>{total_ms} ms</code>. "
                        f"<b>Module errors:</b> <code>{self.error_load_modules}</code></blockquote>",
                        parse_mode="html",
                    )
            except Exception as e:
                self.logger.error(f"Could not send restart notification: {e}")
                await self.handle_error(e, source="restart")

        except (FileNotFoundError, IOError, ValueError) as e:
            self.logger.error(f"Restart file error: {e}")
            if os.path.exists(self.RESTART_FILE):
                try:
                    os.remove(self.RESTART_FILE)
                except Exception:
                    pass
        except Exception as e:
            self.logger.error(f"Unexpected restart handler error: {e}")
