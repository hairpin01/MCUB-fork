# ---- meta data ------ kernel ----------------------
# author: @Hairpin00
# description: kernel core — zen edition
# --- meta data end ---------------------------------
# 🌐 fork MCUBFB: https://github.com/Mitrichdfklwhcluio/MCUBFB
# 🌐 github MCUB-fork: https://github.com/hairpin01/MCUB-fork
# [🌐 https://github.com/hairpin01, 🌐 https://github.com/Mitrichdfklwhcluio, 🌐 https://t.me/HenerTLG]
# ----------------------- end -----------------------

"""
Zen Kernel — simple is better than complex.
Flat is better than nested. Readability counts.
"""

import html
import importlib.util
import logging
import os
import re
import signal
import sys
import time
import traceback
import asyncio
from pathlib import Path
from typing import Callable, Dict, Tuple

try:
    from core.lib.utils.exceptions import McubTelethonError
    from telethon import events
except ImportError as e:
    sys.exit(f"[kernel] missing dependency: {e}\nRun: pip install -r requirements.txt")

try:
    from telethon import _check_mcub_installation

    _check_mcub_installation()
except Exception:
    # tb = traceback.format_exc()
    raise McubTelethonError(
        "YOU is not install telethon-mcub, please run: 'pip install telethon-mcub' and 'pip uninstall telethon -y'! (or update telethon-mcub)"
    )

try:
    from ..lib.utils.colors import Colors
    from ..lib.utils.exceptions import CommandConflictError
    from ..lib.time.cache import TTLCache
    from ..lib.time.scheduler import TaskScheduler
    from ..lib.loader.register import Register
    from ..lib.base.permissions import CallbackPermissionManager
    from ..lib.base.database import DatabaseManager
    from ..version import VersionManager, VERSION
    from ..lib.loader.loader import ModuleLoader
    from ..lib.loader.repository import RepositoryManager
    from ..lib.utils.logger import KernelLogger, setup_logging
    from ..lib.base.config import ConfigManager
    from ..lib.base.client import ClientManager
    from ..lib.loader.inline import InlineManager
except ImportError as e:
    sys.exit(
        f"[kernel] failed to import internal modules: {e}\n{traceback.format_exc()}"
    )

try:
    from utils.html_parser import parse_html
    from utils.message_helpers import (
        edit_with_html,
        reply_with_html,
        send_with_html,
        send_file_with_html,
    )

    HTML_PARSER_AVAILABLE = True
except ImportError:
    HTML_PARSER_AVAILABLE = False

try:
    from utils.restart import restart_kernel
except ImportError:
    restart_kernel = None

MAX_ALIAS_DEPTH = 5
MAX_PATTERN_LEN = 256
PATTERN_TIMEOUT_S = 1

_DANGEROUS_PATTERNS = (
    r"\(\.\*\)\+",
    r"\(\.\+\)\+",
    r"\(\.\*\)\*",
    r"\(\.\+\)\*",
    r"\(\.\{\d+,\}\)\+",
    r".*.*.*",
    r"\(\?\=\.\*\)",
)

_RESTART_EMOJIS = [
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

_LOGO = (
    "\n _    _  ____ _   _ ____\n"
    "| \\  / |/ ___| | | | __ )\n"
    "| |\\/| | |   | | | |  _ \\\n"
    "| |  | | |___| |_| | |_) |\n"
    "|_|  |_|\\____|\\___/|____/\n"
)

_STRINGS: Dict[str, Dict[str, str]] = {
    "ru": {
        "success": "Перезагрузка <b>успешна!</b>",
        "loading": "но модули ещё загружаются...",
        "loaded": "Твой <b>{mcub}</b> полностью загрузился!",
        "errors": "Твой <b>{mcub}</b> <b>загрузился c ошибками</b> :(",
    },
    "en": {
        "success": "Reboot <b>successful!</b>",
        "loading": "but modules are still loading...",
        "loaded": "Your <b>{mcub}</b> is fully loaded!",
        "errors": "Your <b>{mcub}</b> <b>loaded with errors</b> :(",
    },
}


def _validate_regex(pattern: str) -> tuple[bool, str]:
    """Return (ok, reason). Rejects overly long or ReDoS-prone patterns."""
    if len(pattern) > MAX_PATTERN_LEN:
        return False, f"pattern too long (max {MAX_PATTERN_LEN})"

    for danger in _DANGEROUS_PATTERNS:
        if re.search(danger, pattern):
            return False, "potentially dangerous regex pattern"

    def _alarm(signum, frame):
        raise TimeoutError

    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(PATTERN_TIMEOUT_S)
    try:
        re.compile(pattern).match("x" * 1000)
    except TimeoutError:
        return False, "pattern too complex (timeout)"
    except re.error as e:
        return False, f"invalid regex: {e}"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)

    return True, "ok"


def _strings(lang: str) -> Dict[str, str]:
    return _STRINGS.get(lang, _STRINGS["en"])


class Kernel:
    """MCUB kernel — zen edition.

    Orchestrates clients, modules, commands and scheduler.
    Simple is better than complex. Readability counts.
    """

    def __init__(self) -> None:
        self.VERSION = VERSION
        self.DB_VERSION = 2
        self.start_time = time.time()
        self.Colors = Colors

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

        self.cache = TTLCache(max_size=500, ttl=600)
        self.register = Register(self)
        self.callback_permissions = CallbackPermissionManager()

        self.setup_directories()
        self.check_dependencies()

        self._cfg = ConfigManager(self)
        self.load_or_create_config()
        self.logger = setup_logging()

        self._loader = ModuleLoader(self)
        self._repo = RepositoryManager(self)
        self._log = KernelLogger(self)
        self._client_mgr = ClientManager(self)
        self._inline = InlineManager(self)

        self.version_manager = VersionManager(self)
        self.db_manager = DatabaseManager(self)

        self.HTML_PARSER_AVAILABLE = HTML_PARSER_AVAILABLE
        self._init_html_parser()
        self._init_emoji_parser()

    def _init_html_parser(self) -> None:
        if not self.HTML_PARSER_AVAILABLE:
            self.parse_html = self.edit_with_html = self.reply_with_html = None
            self.send_with_html = self.send_file_with_html = None
            return
        try:
            self.parse_html = parse_html
            self.edit_with_html = lambda ev, h, **kw: edit_with_html(self, ev, h, **kw)
            self.reply_with_html = lambda ev, h, **kw: reply_with_html(
                self, ev, h, **kw
            )
            self.send_with_html = lambda cid, h, **kw: send_with_html(
                self, self.client, cid, h, **kw
            )
            self.send_file_with_html = lambda cid, h, f, **kw: send_file_with_html(
                self, self.client, cid, h, f, **kw
            )
            self.logger.info("html parser loaded")
        except Exception as e:
            self.logger.error(f"html parser init error: {e}")
            self.HTML_PARSER_AVAILABLE = False

    def _init_emoji_parser(self) -> None:
        try:
            from utils.emoji_parser import emoji_parser

            self.emoji_parser = emoji_parser
        except ImportError:
            self.emoji_parser = None
            self.logger.warning("emoji parser not available")

    def setup_directories(self) -> None:
        for d in (
            self.MODULES_DIR,
            self.MODULES_LOADED_DIR,
            self.IMG_DIR,
            self.LOGS_DIR,
        ):
            Path(d).mkdir(parents=True, exist_ok=True)

    def check_dependencies(self) -> None:
        import subprocess
        import itertools
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

        missing = [
            (pip, mod)
            for pip, mod in _REQUIREMENTS
            if importlib.util.find_spec(mod) is None
        ]
        if not missing:
            return

        for _, mod in missing:
            print(f"  missing: {mod}")

        stop = threading.Event()

        def _spin():
            for f in itertools.cycle("◜◝◞◟"):
                if stop.is_set():
                    break
                sys.stdout.write(f"\r{f}  installing dependencies…  {f}")
                sys.stdout.flush()
                time.sleep(0.12)
            sys.stdout.write("\r" + " " * 60 + "\r")
            sys.stdout.flush()

        spinner = threading.Thread(target=_spin, daemon=True)
        spinner.start()

        failed = []
        for pip_name, _ in missing:
            installed = any(
                subprocess.run(cmd, capture_output=True).returncode == 0
                for cmd in (
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
                    ["pip3", "install", pip_name],
                )
            )
            if not installed:
                failed.append(pip_name)

        stop.set()
        spinner.join(timeout=1)

        if failed:
            sys.exit(
                f"✗  install failed: {', '.join(failed)}\n   run: pip install {' '.join(failed)}"
            )

        print("✓  dependencies ready\n")

    def cprint(self, text: str, color: str = "") -> None:
        print(f"{color}{text}{Colors.RESET}")

    def log_debug(self, message: str) -> None:
        self.logger.debug(message)

    def log_error(self, message: str) -> None:
        self.logger.error(message)

    async def send_log_message(self, text: str, file=None) -> bool:
        return await self._log.send_log_message(text, file)

    async def send_error_log(
        self, error_text: str, source_file: str, message_info: str = ""
    ) -> None:
        await self._log.send_error_log(error_text, source_file, message_info)

    async def handle_error(
        self, error: Exception, source: str = "unknown", event=None
    ) -> None:
        await self._log.handle_error(error, source, event)

    def save_error_to_file(self, error_text: str) -> None:
        self._log.save_error_to_file(error_text)

    async def log_network(self, message: str) -> None:
        await self._log.log_network(message)

    async def log_error_async(self, message: str) -> None:
        await self._log.log_error_async(message)

    async def log_module(self, message: str) -> None:
        await self._log.log_module(message)

    def load_or_create_config(self) -> bool:
        return self._cfg.load_or_create()

    def save_config(self) -> None:
        self._cfg.save()

    def setup_config(self) -> bool:
        return self._cfg.setup()

    def first_time_setup(self) -> bool:
        return self._cfg.first_time_setup()

    async def get_module_config(self, module_name: str, default=None):
        return await self._cfg.get_module_config(module_name, default)

    async def save_module_config(self, module_name: str, config_data: dict) -> bool:
        return await self._cfg.save_module_config(module_name, config_data)

    async def delete_module_config(self, module_name: str) -> bool:
        return await self._cfg.delete_module_config(module_name)

    async def get_module_config_key(self, module_name: str, key: str, default=None):
        return await self._cfg.get_key(module_name, key, default)

    async def set_module_config_key(self, module_name: str, key: str, value) -> bool:
        return await self._cfg.set_key(module_name, key, value)

    async def delete_module_config_key(self, module_name: str, key: str) -> bool:
        return await self._cfg.delete_key(module_name, key)

    async def update_module_config(self, module_name: str, updates: dict) -> bool:
        return await self._cfg.update(module_name, updates)

    def load_repositories(self) -> None:
        self._repo.load()

    async def save_repositories(self) -> None:
        await self._repo.save()

    async def add_repository(self, url: str) -> tuple:
        return await self._repo.add(url)

    async def remove_repository(self, index) -> tuple:
        return await self._repo.remove(index)

    async def get_repo_name(self, url: str) -> str:
        return await self._repo.get_name(url)

    async def get_repo_modules_list(self, repo_url: str) -> list:
        return await self._repo.get_modules_list(repo_url)

    async def download_module_from_repo(
        self, repo_url: str, module_name: str
    ) -> "str | None":
        return await self._repo.download_module(repo_url, module_name)

    def set_loading_module(self, module_name: str, module_type: str) -> None:
        self.current_loading_module = module_name
        self.current_loading_module_type = module_type
        self.logger.debug(f"loading: {module_name} ({module_type})")

    def clear_loading_module(self) -> None:
        self.current_loading_module = None
        self.current_loading_module_type = None

    async def detected_module_type(self, module) -> str:
        return await self._loader.detect_module_type(module)

    async def load_module_from_file(
        self, file_path: str, module_name: str, is_system: bool = False
    ) -> tuple:
        return await self._loader.load_module_from_file(
            file_path, module_name, is_system
        )

    async def install_from_url(
        self, url: str, module_name: "str | None" = None, auto_dependencies: bool = True
    ) -> tuple:
        return await self._loader.install_from_url(url, module_name, auto_dependencies)

    async def load_system_modules(self) -> None:
        await self._loader.load_system_modules()

    async def load_user_modules(self) -> None:
        await self._loader.load_user_modules()

    async def unregister_module_commands(self, module_name: str) -> None:
        await self._loader.unregister_module_commands(module_name)

    def _debug_event_builders_snapshot(self) -> list[str]:
        builders = getattr(self.client, "_event_builders", []) or []
        snapshot = []
        for event_obj, callback in builders:
            snapshot.append(
                f"{type(event_obj).__name__}:{getattr(callback, '__name__', repr(callback))}"
            )
        return snapshot

    def _event_builder_signature(self, event_obj, callback) -> tuple:
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
        if not getattr(self, "client", None):
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
        if not getattr(self, "client", None):
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

        self.logger.debug(
            "[core_handlers] ensure reason=%r has_new=%s has_fallback=%s builders=%r",
            reason,
            has_new,
            has_fallback,
            self._debug_event_builders_snapshot(),
        )

        force_rebind = reason.startswith("reload_")
        if force_rebind:
            self.client.remove_event_handler(
                self._core_message_handler, events.NewMessage()
            )
            if hasattr(self, "_core_fallback_message_handler"):
                self.client.remove_event_handler(
                    self._core_fallback_message_handler, events.NewMessage()
                )
            self.client.add_event_handler(
                self._core_message_handler, events.NewMessage()
            )
            if hasattr(self, "_core_fallback_message_handler"):
                self.client.add_event_handler(
                    self._core_fallback_message_handler, events.NewMessage()
                )
            self.logger.warning(
                "[core_handlers] rebound handlers reason=%r builders=%r",
                reason,
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

    def ensure_registered_module_handlers(self, reason: str = "manual") -> None:
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
                if client is not self.client or _has_binding(wrapper, event_obj):
                    continue
                client.add_event_handler(wrapper, event_obj)
                restored.append(
                    f"watcher:{module_name}:{getattr(wrapper, '__name__', repr(wrapper))}"
                )

            for entry in getattr(reg, "__event_handlers__", []):
                handler, event_obj = entry[0], entry[1]
                client = entry[2] if len(entry) > 2 else self.client
                if client is not self.client or _has_binding(handler, event_obj):
                    continue
                client.add_event_handler(handler, event_obj)
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
        await self._loader.run_post_load(module, module_name, is_install)

    async def get_module_metadata(self, code: str) -> dict:
        return await self._loader.get_module_metadata(code)

    async def get_command_description(self, module_name: str, command: str) -> str:
        return await self._loader.get_command_description(module_name, command)

    def register_command(self, pattern: str, func=None):
        """Register a userbot command.  Raises ValueError / CommandConflictError on bad input."""
        cmd = pattern.lstrip("^\\" + self.custom_prefix).rstrip("$")

        if cmd != pattern:
            ok, reason = _validate_regex(cmd)
            if not ok:
                raise ValueError(f"invalid command pattern: {reason}")

        if self.current_loading_module is None:
            raise ValueError(
                "no loading module context — call set_loading_module first"
            )

        if cmd in self.command_handlers:
            owner = self.command_owners.get(cmd)
            kind = "system" if owner in self.system_modules else "user"
            raise CommandConflictError(
                f"command '{cmd}' already registered by '{owner}'",
                conflict_type=kind,
                command=cmd,
            )

        def _register(f):
            self.command_handlers[cmd] = f
            self.command_owners[cmd] = self.current_loading_module
            return f

        return _register(func) if func else _register

    def register_command_bot(self, pattern: str, func=None):
        """Register a bot command (starting with /)."""
        if not pattern.startswith("/"):
            pattern = "/" + pattern
        cmd = pattern.lstrip("/").split()[0]

        if self.current_loading_module is None:
            raise ValueError("no loading module context")

        if cmd in self.bot_command_handlers:
            owner = self.bot_command_owners.get(cmd)
            raise CommandConflictError(
                f"bot command '/{cmd}' already registered by '{owner}'",
                conflict_type="bot",
                command=cmd,
            )

        def _register(f):
            self.bot_command_handlers[cmd] = (pattern, f)
            self.bot_command_owners[cmd] = self.current_loading_module
            return f

        return _register(func) if func else _register

    def unregister_module_bot_commands(self, module_name: str) -> None:
        for cmd in [c for c, o in self.bot_command_owners.items() if o == module_name]:
            self.bot_command_handlers.pop(cmd, None)
            self.bot_command_owners.pop(cmd, None)

    def register_inline_handler(self, pattern: str, handler) -> None:
        self._inline.register_inline_handler(pattern, handler)

    def unregister_module_inline_handlers(self, module_name: str) -> None:
        self._inline.unregister_module_inline_handlers(module_name)

    def register_callback_handler(self, pattern, handler) -> None:
        self._inline.register_callback_handler(pattern, handler)

    async def inline_query_and_click(self, chat_id, query, **kwargs):
        return await self._inline.inline_query_and_click(chat_id, query, **kwargs)

    async def send_inline(self, chat_id: int, query: str, buttons=None) -> bool:
        return await self._inline.send_inline(chat_id, query, buttons)

    async def send_inline_from_config(self, chat_id: int, query: str, buttons=None):
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
        return await self._inline.inline_form(
            chat_id, title, fields, buttons, auto_send, ttl, **kwargs
        )

    async def init_client(self) -> bool:
        return await self._client_mgr.init_client()

    async def setup_inline_bot(self) -> bool:
        return await self._client_mgr.setup_inline_bot()

    async def safe_connect(self) -> bool:
        return await self._client_mgr.safe_connect()

    def is_admin(self, user_id: int) -> bool:
        return hasattr(self, "ADMIN_ID") and user_id == self.ADMIN_ID

    def should_process_command_event(self, event) -> bool:
        """Accept own command messages even when Telethon loses the out flag."""
        msg = getattr(event, "message", event)
        if getattr(msg, "out", False):
            return True
        return self.is_admin(getattr(event, "sender_id", None))

    def _is_command_event_processed(self, event) -> bool:
        msg = getattr(event, "message", event)
        return bool(getattr(msg, "_mcub_command_processed", False))

    def _mark_command_event_processed(self, event) -> None:
        msg = getattr(event, "message", event)
        setattr(msg, "_mcub_command_processed", True)

    def is_bot_available(self) -> bool:
        return (
            hasattr(self, "bot_client")
            and self.bot_client is not None
            and self.bot_client.is_connected()
        )

    async def init_db(self):
        return await self.db_manager.init_db()

    async def create_tables(self):
        await self.db_manager._create_tables()

    async def db_set(self, module, key, value):
        await self.db_manager.db_set(module, key, value)

    async def db_get(self, module, key):
        return await self.db_manager.db_get(module, key)

    async def db_delete(self, module, key):
        await self.db_manager.db_delete(module, key)

    async def db_query(self, query, parameters):
        return await self.db_manager.db_query(query, parameters)

    @property
    def db_conn(self):
        return self.db_manager.conn if self.db_manager else None

    async def get_latest_kernel_version(self) -> str:
        return await self.version_manager.get_latest_kernel_version()

    async def _check_kernel_version_compatibility(self, code: str) -> Tuple[bool, str]:
        return await self.version_manager.check_module_compatibility(code)

    async def init_scheduler(self) -> None:
        self.scheduler = TaskScheduler(self)
        await self.scheduler.start()
        self.logger.info("scheduler ready")

    def add_middleware(self, middleware_func: Callable) -> None:
        self.middleware_chain.append(middleware_func)

    async def process_with_middleware(self, event, handler: Callable):
        for mw in self.middleware_chain:
            if await mw(event, handler) is False:
                return False
        return await handler(event)

    async def process_command(self, event, depth: int = 0) -> bool:
        """Dispatch an outgoing message to the matching command handler.

        Resolves aliases recursively up to MAX_ALIAS_DEPTH.
        """
        if depth > MAX_ALIAS_DEPTH:
            self.logger.error(f"alias recursion limit reached: {event.text!r}")
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
            args = text[len(self.custom_prefix) + len(cmd) :]
            new_text = self.custom_prefix + alias + args
            self.logger.debug(
                "[process_command] alias-hit cmd=%r target=%r text=%r",
                cmd,
                alias,
                text,
            )
            event.text = new_text
            if hasattr(event, "message"):
                event.message.message = new_text
                event.message.text = new_text
            if alias in self.command_handlers:
                self.logger.debug(
                    "[process_command] alias-direct-dispatch target=%r owner=%r",
                    alias,
                    self.command_owners.get(alias),
                )
                await self.command_handlers[alias](event)
                return True
            return await self.process_command(event, depth + 1)

        if cmd in self.command_handlers:
            self.logger.debug(
                "[process_command] dispatch cmd=%r owner=%r handler=%r",
                cmd,
                self.command_owners.get(cmd),
                getattr(
                    self.command_handlers[cmd],
                    "__name__",
                    repr(self.command_handlers[cmd]),
                ),
            )
            await self.command_handlers[cmd](event)
            return True

        self.logger.debug(
            "[process_command] miss cmd=%r known=%r",
            cmd,
            sorted(self.command_handlers.keys()),
        )
        return False

    async def process_bot_command(self, event) -> bool:
        """Dispatch a bot command to its handler."""
        text = event.text
        if not text or not text.startswith("/"):
            return False

        raw = text.split()[0][1:] if " " in text else text[1:]
        cmd = raw.split("@")[0]

        if cmd in self.bot_command_handlers:
            _, handler = self.bot_command_handlers[cmd]
            await handler(event)
            return True

        return False

    async def get_user_info(self, user_id: int) -> str:
        try:
            entity = await self.client.get_entity(user_id)
            if hasattr(entity, "first_name") or hasattr(entity, "last_name"):
                name = f"{entity.first_name or ''} {entity.last_name or ''}".strip()
                return f"{name} (@{entity.username or 'no username'})"
            if hasattr(entity, "title"):
                return f"{entity.title} (chat/channel)"
        except Exception:
            pass
        return f"ID: {user_id}"

    async def get_thread_id(self, event) -> "int | None":
        if not event:
            return None
        if hasattr(event, "reply_to") and event.reply_to:
            tid = getattr(event.reply_to, "reply_to_top_id", None)
            if tid:
                return tid
        if hasattr(event, "message"):
            return getattr(event.message, "reply_to_top_id", None)
        return None

    async def restart(self, chat_id=None, message_id=None) -> None:
        await restart_kernel(self, chat_id, message_id)

    def raw_text(self, source) -> str:
        if source is None:
            return ""
        if isinstance(source, str):
            return html.escape(source, quote=False)
        try:
            if not getattr(self, "html_converter", None):
                from utils.raw_html import RawHTMLConverter

                self.html_converter = RawHTMLConverter()
            return self.html_converter.convert_message(source) or ""
        except Exception as e:
            self.logger.error(f"raw_text error: {e}")
            return ""

    def format_with_html(self, text: str, entities) -> str:
        if not text:
            return ""
        if not HTML_PARSER_AVAILABLE:
            return html.escape(text, quote=False)
        from utils.html_parser import telegram_to_html

        return telegram_to_html(text, entities)

    async def send_with_emoji(self, chat_id: int, text: str, **kwargs):
        if not self.emoji_parser or not self.emoji_parser.is_emoji_tag(text):
            return await self.client.send_message(chat_id, text, **kwargs)
        try:
            parsed, entities = self.emoji_parser.parse_to_entities(text)
            peer = await self.client.get_input_entity(chat_id)
            return await self.client.send_message(
                peer,
                parsed,
                entities=entities,
                **{k: v for k, v in kwargs.items() if k != "entities"},
            )
        except Exception:
            fallback = self.emoji_parser.remove_emoji_tags(text)
            return await self.client.send_message(chat_id, fallback, **kwargs)

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

        needs_setup = not os.path.exists(self.CONFIG_FILE)
        if not needs_setup:
            session_exists = os.path.exists("user_session.session")
            needs_setup = not session_exists

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

            asyncio.create_task(start_web_panel(self, host, port))
        except Exception as e:
            self.logger.error(f"Failed to start web panel: {e}")

    async def run(self) -> None:
        """Boot sequence: config → scheduler → client → modules → event loop."""
        no_web = not getattr(self, "web_enabled", True)  # True если --no-web

        if not no_web:
            web_via_env = os.environ.get("MCUB_WEB", "0") == "1"
            web_via_config = self.config.get("web_panel_enabled", False)
            no_session = not os.path.exists("user_session.session")
            no_config = not os.path.exists(self.CONFIG_FILE)

            # запускаем панель если: явно включено ИЛИ нет сессии ИЛИ нет конфига
            if web_via_env or web_via_config or no_session or no_config:
                await self.run_panel()

        if not self.load_or_create_config():
            if not self.first_time_setup():
                self.logger.error("setup failed")
                return

        self.load_repositories()
        logging.basicConfig(level=logging.INFO)
        await self.init_scheduler()

        if not await self.init_client():
            return

        try:
            await self.init_db()
        except ImportError:
            self.cprint(f"{Colors.YELLOW}hint: pip install aiosqlite{Colors.RESET}")
        except Exception as e:
            self.cprint(f"{Colors.RED}db init error: {e}{Colors.RESET}")

        await self.setup_inline_bot()

        if not self.config.get("inline_bot_token"):
            from core_inline.bot import InlineBot

            self.inline_bot = InlineBot(self)
            await self.inline_bot.setup()

        async def _on_message(event):
            msg = getattr(event, "message", event)
            if not self.should_process_command_event(event):
                self.logger.debug(
                    "[core_handlers] skip-nonoutgoing handler=_on_message text=%r sender=%r chat=%r out=%r admin=%r",
                    getattr(msg, "text", None),
                    getattr(event, "sender_id", None),
                    getattr(event, "chat_id", None),
                    getattr(msg, "out", False),
                    self.is_admin(getattr(event, "sender_id", None)),
                )
                return
            if self._is_command_event_processed(event):
                self.logger.debug(
                    "[core_handlers] skip-duplicate handler=_on_message text=%r sender=%r chat=%r",
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
                tb = traceback.format_exc()
                if len(tb) > 1000:
                    tb = "…" + tb[-997:]
                try:
                    await event.edit(
                        f"<b>Error in <code>{event.text}</code></b>\n<pre>{tb}</pre>",
                        parse_mode="html",
                    )
                except Exception:
                    pass

        async def _fallback_on_message(event):
            msg = getattr(event, "message", event)
            if not self.should_process_command_event(event):
                return
            if self._is_command_event_processed(event):
                return
            self.logger.warning(
                "[core_handlers] fallback-dispatch handler=_fallback_on_message text=%r sender=%r chat=%r out=%r admin=%r",
                getattr(msg, "text", None),
                getattr(event, "sender_id", None),
                getattr(event, "chat_id", None),
                getattr(msg, "out", False),
                self.is_admin(getattr(event, "sender_id", None)),
            )
            self._mark_command_event_processed(event)
            await self.process_command(event)

        self._core_message_handler = _on_message
        self._core_fallback_message_handler = _fallback_on_message
        self.client.add_event_handler(_on_message, events.NewMessage())
        self.client.add_event_handler(_fallback_on_message, events.NewMessage())
        self.logger.debug(
            "[core_handlers] registered outgoing handlers builders=%r",
            self._debug_event_builders_snapshot(),
        )

        await self._notify_early_restart()

        modules_start = time.time()
        await self.load_system_modules()
        await self.load_user_modules()
        modules_end = time.time()

        if getattr(self, "bot_client", None):

            @self.bot_client.on(events.NewMessage(pattern="/"))
            async def _on_bot_command(event):
                try:
                    await self.process_bot_command(event)
                except Exception as e:
                    await self.handle_error(
                        e, source="bot_command_handler", event=event
                    )

        logo = (
            _LOGO
            + f"Kernel loaded.\n\n• Version: {self.VERSION}\n• Prefix: {self.custom_prefix}\n"
        )
        if self.error_load_modules:
            logo += f"• Module load errors: {self.error_load_modules}\n"
        print(logo)
        self.logger.info("MCUB started")

        await self._handle_restart_notification(modules_start, modules_end)
        await self.client.run_until_disconnected()

    async def _notify_early_restart(self) -> None:
        """Send a 'still loading' notice immediately after connect."""
        if not os.path.exists(self.RESTART_FILE):
            return
        try:
            data = Path(self.RESTART_FILE).read_text().split(",")
            if len(data) < 2:
                return
            chat_id, msg_id = int(data[0]), int(data[1])
            restart_time = float(data[2]) if len(data) >= 3 else None
            lang = self.config.get("language", "ru")
            s = _strings(lang)
            total_ms = (
                round((time.time() - restart_time) * 1000, 2) if restart_time else 0
            )
            em = '<tg-emoji emoji-id="5332654441508119011">⚗️</tg-emoji>'
            await self.client.edit_message(
                chat_id,
                msg_id,
                f"{em} {s['success']} (*.*)\n<i>{s['loading']}</i> <b>KLB:</b> <code>{total_ms} ms</code>",
                parse_mode="html",
            )
        except Exception:
            pass

    async def _handle_restart_notification(
        self, modules_start: float, modules_end: float
    ) -> None:
        """Edit the restart message with final timing after modules are loaded."""
        if not os.path.exists(self.RESTART_FILE):
            return
        try:
            data = Path(self.RESTART_FILE).read_text().split(",")
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

            lang = self.config.get("language", "ru")
            s = _strings(lang)
            total_ms = round((time.time() - restart_time) * 1000, 2)
            mod_ms = round((modules_end - modules_start) * 1000, 2)

            if not self.client.is_connected():
                return

            if self.error_load_modules:
                em = '<tg-emoji emoji-id="5208923808169222461">🥀</tg-emoji>'
                body = (
                    f"{em} {s['errors'].format(mcub=mcub)}\n"
                    f"<blockquote><b>Kernel:</b> <code>{total_ms} ms</code>. "
                    f"<b>Module errors:</b> <code>{self.error_load_modules}</code></blockquote>"
                )
            else:
                em = '<tg-emoji emoji-id="5399898266265475100">📦</tg-emoji>'
                body = (
                    f"{em} {s['loaded'].format(mcub=mcub)}\n"
                    f"<blockquote><b>Kernel:</b> <code>{total_ms} ms</code>. "
                    f"<b>Modules:</b> <code>{mod_ms} ms</code>.</blockquote>"
                )

            try:
                await self.client.edit_message(chat_id, msg_id, body, parse_mode="html")
            except Exception:
                send_kwargs = {"parse_mode": "html"}
                if thread_id:
                    send_kwargs["reply_to"] = thread_id
                await self.client.send_message(chat_id, body, **send_kwargs)

        except (FileNotFoundError, IOError, ValueError) as e:
            self.logger.error(f"restart file error: {e}")
            try:
                os.remove(self.RESTART_FILE)
            except Exception:
                pass
        except Exception as e:
            self.logger.error(f"restart handler error: {e}")
