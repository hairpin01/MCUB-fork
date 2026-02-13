# author: @Hairpin00
# version: 1.0.1.9.5
# description: kernel core
# Спасибо @Mitrichq за основу юзербота
# Лицензия? какая лицензия ещё

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
    print(f"=X HTML парсер не загружен: {e}")
    HTML_PARSER_AVAILABLE = False

try:
    import time
    import sys
    import os
    import importlib.util
    import re
    import json
    import subprocess
    import random
    from pathlib import Path
    import logging
    from logging.handlers import RotatingFileHandler
    import aiosqlite
    from contextlib import asynccontextmanager
    import io
    import html
    import socks
    import traceback
    import psutil
    import aiohttp
    import asyncio
    from collections import OrderedDict, defaultdict
    from datetime import datetime, timedelta
    from telethon import TelegramClient, events, Button
    from telethon.errors import SessionPasswordNeededError
    from typing import (
        Any,
        Callable,
        Dict, List,
        Optional,
        Union,
        Pattern,
        Tuple
    )
    import inspect
    from utils.restart import restart_kernel
    from telethon.tl import types as tl_types
except ImportError as e:
    print("Установите зависимости: pip install -r requirements.txt\n", str(e))
    sys.exit(1)


class Colors:
    """цвета"""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"


class CommandConflictError(Exception):
    """Исключение для конфликта команд"""

    def __init__(self, message, conflict_type=None, command=None):
        super().__init__(message)
        self.conflict_type = conflict_type
        self.command = command

class TTLCache:
    """
    A Time-To-Live (TTL) cache implementation with LRU eviction policy.

    This cache stores key-value pairs with an expiration time. When the cache
    reaches its maximum size, it removes the least recently used item.
    Expired items are automatically removed upon access.

    Attributes:
        max_size (int): Maximum number of items the cache can hold
        ttl (int): Default time-to-live in seconds for cache entries
        cache (OrderedDict): The underlying data storage with LRU ordering
    """

    def __init__(self, max_size: int = 1000, ttl: int = 300) -> None:
        """
        Initialize the TTL cache.

        Args:
            max_size: Maximum number of items the cache can hold (default: 1000)
            ttl: Default time-to-live for cache entries in seconds (default: 300)
        """
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl

    def set(self, key: Any, value: Any, ttl: Optional[int] = None) -> None:
        """
        Add or update a key-value pair in the cache.

        Args:
            key: The key to store
            value: The value to associate with the key
            ttl: Optional custom TTL in seconds. If not provided, uses default TTL

        Note:
            If the cache exceeds max_size after insertion, the least recently
            used item is removed. The new item becomes the most recently used.
        """
        # Calculate expiration time: current time + custom TTL or default TTL
        expire_time = time.time() + (ttl if ttl is not None else self.ttl)

        # Store the key with its expiration time and value
        self.cache[key] = (expire_time, value)

        # Move to end to mark as recently used (OrderedDict maintains insertion order)
        self.cache.move_to_end(key)

        # Remove least recently used item if cache exceeds max size
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def get(self, key: Any) -> Optional[Any]:
        """
        Retrieve a value from the cache by key.

        Args:
            key: The key to look up

        Returns:
            The associated value if found and not expired, None otherwise

        Note:
            If an expired item is found, it is automatically removed from the cache.
        """
        if key not in self.cache:
            return None

        expire_time, value = self.cache[key]

        # Check if the item has expired
        if time.time() <= expire_time:
            # Mark as recently used and return value
            self.cache.move_to_end(key)
            return value
        else:
            # Remove expired item
            del self.cache[key]
            return None

    def clear(self) -> None:
        """
        Remove all items from the cache.
        """
        self.cache.clear()

    def size(self) -> int:
        """
        Get the current number of items in the cache.

        Returns:
            Number of items currently stored in the cache
        """
        return len(self.cache)

    def _cleanup_expired(self) -> None:
        """
        Remove all expired items from the cache.

        Note: This is an internal method that can be called periodically
        to clean up expired items without requiring access attempts.
        """
        current_time = time.time()
        expired_keys = [
            key for key, (expire_time, _) in self.cache.items()
            if current_time >= expire_time
        ]

        for key in expired_keys:
            del self.cache[key]


class TaskScheduler:
    """
    A scheduler for managing periodic and time-based asynchronous tasks.
    This class provides methods to schedule tasks that run at fixed intervals
    or at specific times daily. It integrates with a kernel for error logging
    and supports graceful shutdown of running tasks.
    Attributes:
        kernel: Reference to the main kernel/application for logging and services
        tasks: List of currently scheduled asyncio tasks
        running: Flag indicating whether the scheduler is active
    """
    def __init__(self, kernel: Any) -> None:
        """
        Initialize the task scheduler.

        Args:
            kernel: The main application kernel providing logging and other services
                    Must have a `log_error` method for error reporting.
        """
        self.kernel = kernel
        self.tasks: List[asyncio.Task] = []
        self.running = False

    async def start(self) -> None:
        """Start the task scheduler and mark it as running."""
        self.running = True

    async def stop(self) -> None:
        """
        Stop all scheduled tasks and clean up resources.

        This method cancels all running tasks and waits for them to complete
        cancellation. It should be called before application shutdown.
        """
        self.running = False

        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Wait for all tasks to be cancelled
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        self.tasks.clear()

    async def add_interval_task(self,
                               func: Callable[[], Any],
                               interval_seconds: float) -> None:
        """
        Schedule a function to run at fixed intervals.

        The function will be called repeatedly, waiting for `interval_seconds`
        between the end of one execution and the start of the next.

        Args:
            func: Async function to execute periodically
            interval_seconds: Time interval between executions in seconds

        Example:
            >>> await scheduler.add_interval_task(update_cache, 60.0)
        """
        async def wrapper() -> None:
            """Wrapper function that handles the interval logic and error catching."""
            while self.running:
                try:
                    await asyncio.sleep(interval_seconds)
                    await func()
                except asyncio.CancelledError:
                    # Task was cancelled, break out of the loop
                    break
                except Exception as e:
                    # Log the error but keep the task running
                    error_msg = f"Interval task error in {func.__name__}: {e}\n"
                    error_msg += traceback.format_exc()
                    self.kernel.log_error(error_msg)

        task = asyncio.create_task(wrapper(), name=f"interval_{func.__name__}")
        self.tasks.append(task)

    async def add_daily_task(self,
                            func: Callable[[], Any],
                            hour: int,
                            minute: int) -> None:
        """
        Schedule a function to run daily at a specific time.

        The function will be called every day at the specified hour and minute.
        If the target time has already passed for today, it will run tomorrow.

        Args:
            func: Async function to execute daily
            hour: Hour of the day (0-23) to run the task
            minute: Minute of the hour (0-59) to run the task

        Raises:
            ValueError: If hour or minute values are out of valid range

        Example:
            >>> await scheduler.add_daily_task(send_daily_report, 9, 30)
        """
        # Validate input parameters
        if not (0 <= hour <= 23):
            raise ValueError(f"Hour must be between 0 and 23, got {hour}")
        if not (0 <= minute <= 59):
            raise ValueError(f"Minute must be between 0 and 59, got {minute}")

        async def wrapper() -> None:
            """Wrapper function that handles the daily scheduling and error catching."""
            while self.running:
                try:
                    # Calculate time until next execution
                    now = datetime.now()
                    target_time = now.replace(
                        hour=hour,
                        minute=minute,
                        second=0,
                        microsecond=0
                    )


                    # If target time has passed today, schedule for tomorrow
                    if now >= target_time:
                        target_time += timedelta(days=1)

                    # Calculate delay in seconds
                    delay_seconds = (target_time - now).total_seconds()

                    # Wait until the target time
                    await asyncio.sleep(delay_seconds)

                    # Execute the scheduled function
                    await func()

                    # After execution, wait for the next day
                    # This prevents multiple executions if the function takes time
                    await asyncio.sleep(1)  # Small delay before recalculating

                except asyncio.CancelledError:
                    # Task was cancelled, break out of the loop
                    break
                except Exception as e:
                    # Log the error but keep the task running
                    error_msg = f"Daily task error in {func.__name__}: {e}\n"
                    error_msg += traceback.format_exc()
                    self.kernel.log_error(error_msg)

                    # Wait a bit before retrying to avoid error loops
                    await asyncio.sleep(60)

        task_name = f"daily_{func.__name__}_{hour:02d}:{minute:02d}"
        task = asyncio.create_task(wrapper(), name=task_name)
        self.tasks.append(task)

    def get_active_tasks(self) -> List[asyncio.Task]:
        """
        Get a list of all currently scheduled tasks.

        Returns:
            List of asyncio.Task objects representing scheduled tasks
        """
        return self.tasks.copy()

    def get_task_count(self) -> int:
        """Return the number of currently scheduled tasks."""
        return len(self.tasks)

    async def remove_task(self, task: asyncio.Task) -> bool:
        """
        Remove and cancel a specific task.

        Args:
            task: The task to remove and cancel

        Returns:
            True if the task was found and cancelled, False otherwise
        """
        if task in self.tasks:
            self.tasks.remove(task)
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            return True
        return False


class Register:
    """
    A comprehensive registration system for Telegram bot handlers.

    This class provides decorators for registering methods, event handlers,
    and commands in a modular Telegram bot system. It integrates with a kernel
    for centralized management of handlers and modules.

    Attributes:
        kernel: Reference to the main bot kernel for registration and management
        _methods: Dictionary storing registered methods for internal use
    """

    def __init__(self, kernel: Any) -> None:
        """
        Initialize the register with a kernel reference.

        Args:
            kernel: The main bot kernel that manages modules and handlers.
                    Must have attributes: client, custom_prefix, current_loading_module,
                    command_handlers, command_owners, aliases, bot_command_handlers,
                    bot_command_owners.
        """
        self.kernel = kernel
        self._methods: Dict[str, Callable] = {}

    def method(self, func: Optional[Callable] = None) -> Callable:
        """
        Decorator to register a method on the module's `register` object.
        The method will be called during module loading with the kernel as argument.
        The function name can be anything (e.g., `setup`, `init`, etc.).
        """
        def decorator(f: Callable) -> Callable:
            caller_frame = inspect.stack()[1][0]
            module = inspect.getmodule(caller_frame)

            if module:
                # Create module.register if it doesn't exist
                if not hasattr(module, "register"):
                    module.register = type("RegisterObject", (), {})()

                # Store the function under its own name
                setattr(module.register, f.__name__, f)

                # Keep internal registry for debugging
                self._methods[f.__name__] = f

            return f

        if func is None:
            return decorator
        return decorator(func)

    def event(self, event_type: str, *args: Any, **kwargs: Any) -> Callable:
        """
        Decorator to register a Telegram event handler.

        Registers a function as a handler for specific Telegram events using
        Telethon's event system. Supports multiple event type aliases.

        Args:
            event_type: Type of event to handle. Supported values:
                - "newmessage", "message": NewMessage events
                - "messageedited", "edited": MessageEdited events
                - "messagedeleted", "deleted": MessageDeleted events
                # - "userupdate", "user": UserUpdate events
                - "inlinequery", "inline": InlineQuery events
                - "callbackquery", "callback": CallbackQuery events
                - "raw", "custom": Raw events
            *args: Positional arguments passed to the Telethon event constructor
            **kwargs: Keyword arguments passed to the Telethon event constructor

        Returns:
            Decorator function that registers the handler

        Example:
            >>> @kernel.register.event("newmessage", pattern=r'hello')
            >>> async def handle_hello(event):
            >>>     await event.reply("Hi there!")
        """
        # Map event type strings to Telethon event classes
        EVENT_TYPE_MAP: Dict[str, Any] = {
            "newmessage": events.NewMessage,
            "message": events.NewMessage,
            "messageedited": events.MessageEdited,
            "edited": events.MessageEdited,
            "messagedeleted": events.MessageDeleted,
            "deleted": events.MessageDeleted,
            "userupdate": events.UserUpdate,
            "user": events.UserUpdate,
            "inlinequery": events.InlineQuery,
            "inline": events.InlineQuery,
            "callbackquery": events.CallbackQuery,
            "callback": events.CallbackQuery,
            "raw": events.Raw,
            "custom": events.Raw,
        }

        def decorator(handler: Callable) -> Callable:
            """Inner decorator that registers the event handler."""
            event_type_lower = event_type.lower()

            if event_type_lower not in EVENT_TYPE_MAP:
                valid_types = ", ".join(EVENT_TYPE_MAP.keys())
                raise ValueError(
                    f"Unknown event type: '{event_type}'. "
                    f"Valid types are: {valid_types}"
                )

            event_class = EVENT_TYPE_MAP[event_type_lower]

            # Register the handler with the Telegram client
            self.kernel.client.add_event_handler(
                handler,
                event_class(*args, **kwargs)
            )

            return handler

        return decorator

    def command(self, pattern: str, **kwargs: Any) -> Callable:
        """
        Decorator to register a custom command for the bot.

        Commands are triggered by the bot's custom prefix (e.g., "!").
        Supports command aliases and module ownership tracking.

        Args:
            pattern: Command pattern to match (can include regex anchors)
            **kwargs: Additional options including:
                - alias: Single string or list of strings for command aliases
                - more: Additional metadata for the command

        Returns:
            Decorator function that registers the command handler

        Raises:
            ValueError: If no current module is set for registration

        Example:
            >>> @kernel.register.command('ping')
            >>> async def ping_command(event):
            >>>     await event.reply("Pong!")
            >>>
            >>> # With alias
            >>> @kernel.register.command('help', alias=['h', 'помощь'])
            >>> async def help_command(event):
            >>>     await event.reply("Help text...")
        """
        def decorator(func: Callable) -> Callable:
            """Inner decorator that registers the command."""
            # Clean the command pattern to get the base command name
            cmd = pattern.lstrip("^\\" + self.kernel.custom_prefix)
            if cmd.endswith("$"):
                cmd = cmd[:-1]

            # Ensure we're registering in the context of a module
            if self.kernel.current_loading_module is None:
                raise ValueError(
                    "No current module set for command registration. "
                    "Commands must be registered from within a module."
                )

            # Register the command handler
            self.kernel.command_handlers[cmd] = func
            self.kernel.command_owners[cmd] = self.kernel.current_loading_module

            # Handle aliases if provided
            alias = kwargs.get("alias")
            if alias:
                if isinstance(alias, str):
                    self.kernel.aliases[alias] = cmd
                elif isinstance(alias, list):
                    for a in alias:
                        self.kernel.aliases[a] = cmd

            # Store additional metadata if provided
            more = kwargs.get("more")
            if more:
                if not hasattr(self.kernel, 'command_metadata'):
                    self.kernel.command_metadata = {}
                self.kernel.command_metadata[cmd] = more

            return func

        return decorator

    def bot_command(self, pattern: str, **kwargs: Any) -> Callable:
        """
        Decorator to register a bot command (Telegram's native /commands).

        These commands appear in Telegram's command menu when users type "/".
        Supports slash commands with optional parameters.

        Args:
            pattern: Command pattern (e.g., "start" or "/start")
            **kwargs: Additional options (currently unused but reserved for future)

        Returns:
            Decorator function that registers the bot command

        Raises:
            ValueError: If no current module is set for registration

        Example:
            >>> @kernel.register.bot_command("start")
            >>> async def start_command(event):
            >>>     await event.reply("Welcome to the bot!")
            >>>
            >>> # With parameters in pattern
            >>> @kernel.register.bot_command("search <query>")
            >>> async def search_command(event):
            >>>     query = event.pattern_match.group('query')
            >>>     await event.reply(f"Searching for {query}...")
        """
        def decorator(func: Callable) -> Callable:
            """Inner decorator that registers the bot command."""
            # Ensure pattern starts with slash for consistency
            if not pattern.startswith("/"):
                cmd_pattern = "/" + pattern
            else:
                cmd_pattern = pattern

            # Extract the base command name (first word after slash)
            cmd = (
                cmd_pattern.lstrip("/").split()[0]
                if " " in cmd_pattern
                else cmd_pattern.lstrip("/")
            )

            # Ensure we're registering in the context of a module
            if self.kernel.current_loading_module is None:
                raise ValueError(
                    "No current module set for bot command registration. "
                    "Bot commands must be registered from within a module."
                )

            # Register the bot command
            self.kernel.bot_command_handlers[cmd] = (pattern, func)
            self.kernel.bot_command_owners[cmd] = self.kernel.current_loading_module

            return func

        return decorator

    def get_registered_methods(self) -> Dict[str, Callable]:
        """
        Get all methods registered through the @method decorator.

        Returns:
            Dictionary mapping method names to their functions
        """
        return self._methods.copy()


class CallbackPermissionManager:
    """
    A manager for granting temporary permissions for callback operations.

    This class provides time-based permission grants with pattern matching.
    It's useful for implementing secure callback systems where users need
    temporary access to specific operations or data patterns.

    Attributes:
        permissions: Nested dictionary storing user permissions
                    Structure: {user_id: {pattern: expiry_time}}
    """

    def __init__(self) -> None:
        """
        Initialize the permission manager with empty permissions.
        """
        # {user_id: {pattern: expiry_time}}
        self.permissions: Dict[int, Dict[str, float]] = defaultdict(dict)

    def _to_str(self, val: Union[str, bytes, Pattern]) -> str:
        """
        Convert various input types to a normalized string pattern.

        Args:
            val: Value to convert. Can be:
                - str: Returned as-is
                - bytes: Decoded from UTF-8
                - Pattern (re.Pattern): Pattern string is extracted
                - Any other type: Converted to string with str()

        Returns:
            Normalized string pattern

        Raises:
            UnicodeDecodeError: If bytes cannot be decoded from UTF-8
        """
        if isinstance(val, bytes):
            return val.decode("utf-8")
        elif isinstance(val, Pattern):
            # Extract pattern string from compiled regex
            return val.pattern
        return str(val)

    def allow(self,
              user_id: int,
              pattern: Union[str, bytes, Pattern],
              duration_seconds: float = 60) -> None:
        """
        Grant temporary permission to a user for a specific pattern.

        The permission will automatically expire after the specified duration.
        Multiple patterns can be granted to the same user.

        Args:
            user_id: User identifier (typically Telegram user ID)
            pattern: Permission pattern (supports prefix matching)
            duration_seconds: How long the permission lasts in seconds (default: 60)

        Example:
            >>> manager.allow(123456, "settings_edit_", duration_seconds=300)
            # User 123456 can access any callback starting with "settings_edit_"
            # for 5 minutes
        """
        pattern_str = self._to_str(pattern)
        expiry_time = time.time() + duration_seconds

        self.permissions[user_id][pattern_str] = expiry_time

    def is_allowed(self,
                   user_id: int,
                   pattern: Union[str, bytes, Pattern]) -> bool:
        """
        Check if a user has permission for a specific pattern.

        The check uses prefix matching: if the requested pattern starts with
        any allowed pattern that hasn't expired, permission is granted.
        Expired permissions are automatically skipped.

        Args:
            user_id: User identifier to check
            pattern: Pattern to check permission for

        Returns:
            True if user has valid permission for the pattern, False otherwise

        Example:
            >>> manager.allow(123456, "menu_", duration_seconds=60)
            >>> manager.is_allowed(123456, "menu_main")  # True
            >>> manager.is_allowed(123456, "settings")   # False
        """
        pattern_str = self._to_str(pattern)
        current_time = time.time()

        # Quick check: user has no permissions
        if user_id not in self.permissions:
            return False

        # Check each allowed pattern for this user
        for allowed_pattern, expiry_time in self.permissions[user_id].items():
            # Skip expired permissions
            if expiry_time <= current_time:
                continue

            # Prefix matching: if requested pattern starts with allowed pattern
            if pattern_str.startswith(allowed_pattern):
                return True

        return False

    def prohibit(self,
                 user_id: int,
                 pattern: Optional[Union[str, bytes, Pattern]] = None) -> None:
        """
        Revoke permission(s) for a user.

        Args:
            user_id: User identifier
            pattern: Specific pattern to revoke. If None, revoke all permissions
                     for this user

        Example:
            >>> manager.allow(123456, "menu_")
            >>> manager.allow(123456, "settings_")
            >>> manager.prohibit(123456, "menu_")  # Revoke only menu permissions
            >>> manager.prohibit(123456)           # Revoke all permissions
        """
        if user_id not in self.permissions:
            return

        if pattern is not None:
            pattern_str = self._to_str(pattern)
            # Remove specific pattern
            if pattern_str in self.permissions[user_id]:
                del self.permissions[user_id][pattern_str]

            # Clean up empty user entry
            if not self.permissions[user_id]:
                del self.permissions[user_id]
        else:
            # Remove all permissions for this user
            del self.permissions[user_id]

    def cleanup(self) -> int:
        """
        Remove all expired permissions across all users.

        This method should be called periodically to free up memory.

        Returns:
            Number of expired permissions removed

        Example:
            >>> expired_count = manager.cleanup()
            >>> print(f"Cleaned up {expired_count} expired permissions")
        """
        current_time = time.time()
        removed_count = 0

        # Iterate over copy of keys to avoid modification during iteration
        for user_id in list(self.permissions.keys()):
            user_patterns = self.permissions[user_id]

            # Find expired patterns for this user
            expired_patterns = [
                pattern for pattern, expiry_time in user_patterns.items()
                if expiry_time <= current_time
            ]

            # Remove expired patterns
            for pattern in expired_patterns:
                del user_patterns[pattern]
                removed_count += 1

            # Remove user entry if no patterns remain
            if not user_patterns:
                del self.permissions[user_id]

        return removed_count

    def get_user_permissions(self, user_id: int) -> Dict[str, float]:
        """
        Get all active permissions for a specific user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary of pattern -> expiry_time for active permissions
            Empty dict if user has no active permissions
        """
        if user_id not in self.permissions:
            return {}

        current_time = time.time()
        # Return only non-expired permissions
        return {
            pattern: expiry_time
            for pattern, expiry_time in self.permissions[user_id].items()
            if expiry_time > current_time
        }

    def get_expiry_time(self,
                       user_id: int,
                       pattern: Union[str, bytes, Pattern]) -> Optional[float]:
        """
        Get the expiry time for a specific user-pattern permission.

        Args:
            user_id: User identifier
            pattern: Permission pattern

        Returns:
            Expiry timestamp in seconds since epoch, or None if permission
            doesn't exist or has expired
        """
        pattern_str = self._to_str(pattern)

        if user_id not in self.permissions:
            return None

        expiry_time = self.permissions[user_id].get(pattern_str)
        if expiry_time is None or expiry_time <= time.time():
            return None

        return expiry_time

    def remaining_time(self,
                      user_id: int,
                      pattern: Union[str, bytes, Pattern]) -> Optional[float]:
        """
        Get remaining time (in seconds) for a specific permission.

        Args:
            user_id: User identifier
            pattern: Permission pattern

        Returns:
            Remaining time in seconds, or None if permission doesn't exist
            or has expired
        """
        expiry_time = self.get_expiry_time(user_id, pattern)
        if expiry_time is None:
            return None

        return max(0.0, expiry_time - time.time())

    def clear_all(self) -> None:
        """
        Clear all permissions for all users.

        This is useful for testing or complete reset of the permission system.
        """
        self.permissions.clear()

    def get_all_permissions(self) -> Dict[int, Dict[str, float]]:
        """
        Get all permissions (including expired ones).

        Returns:
            Complete permissions dictionary
        """
        # Return a deep copy to prevent external modification
        return {
            user_id: patterns.copy()
            for user_id, patterns in self.permissions.items()
        }


class Kernel:
    def __init__(self):
        self.VERSION = "1.0.2.2"
        self.DB_VERSION = 2
        self.start_time = time.time()
        self.loaded_modules = {}
        self.system_modules = {}
        self.command_handlers = {}
        self.command_owners = {}
        self.custom_prefix = "."
        self.aliases = {}
        self.config = {}
        self.client = None
        self.inline_bot = None
        self.catalog_cache = {}
        self.pending_confirmations = {}
        self.shutdown_flag = False
        self.power_save_mode = False
        self.Colors = Colors
        self.db_conn = None
        self.cache = TTLCache(max_size=500, ttl=600)
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
        self.UPDATE_REPO = (
            "https://raw.githubusercontent.com/hairpin01/MCUB-fork/main/"
        )

        self.register = Register(self)
        self.callback_permissions = CallbackPermissionManager()
        self.inline_handlers = {}
        self.callback_handlers = {}
        self.log_chat_id = None
        self.log_bot_enabled = False

        self.current_loading_module = None
        self.current_loading_module_type = None

        # self.load_repositories()
        self.repositories = []
        self.default_repo = self.MODULES_REPO

        self.HTML_PARSER_AVAILABLE = HTML_PARSER_AVAILABLE
        try:
            from utils.emoji_parser import emoji_parser

            self.emoji_parser = emoji_parser

        except ImportError:
            self.emoji_parser = None
            print("=X The emoji parser is not loaded")
        if self.HTML_PARSER_AVAILABLE:
            try:
                self.parse_html = parse_html
                self.edit_with_html = lambda event, html, **kwargs: edit_with_html(
                    self, event, html, **kwargs
                )
                self.reply_with_html = lambda event, html, **kwargs: reply_with_html(
                    self, event, html, **kwargs
                )
                self.send_with_html = lambda chat_id, html, **kwargs: send_with_html(
                    self, self.client, chat_id, html, **kwargs
                )
                self.send_file_with_html = (
                    lambda chat_id, html, file, **kwargs: send_file_with_html(
                        self, self.client, chat_id, html, file, **kwargs
                    )
                )
                print("=> HTML парсер загружен")
            except Exception as e:
                print(f"=X Ошибка инициализации HTML парсера: {e}")
                self.HTML_PARSER_AVAILABLE = False

        if not self.HTML_PARSER_AVAILABLE:
            self.parse_html = None
            self.edit_with_html = None
            self.reply_with_html = None
            self.send_with_html = None
            self.send_file_with_html = None
            self.logger.warning("=X HTML парсер не загружен")

        self.setup_directories()
        self.load_or_create_config()
        self.logger = self.setup_logging()
        self.middleware_chain = []
        self.scheduler = None
        self.bot_command_handlers = {}
        self.bot_command_owners = {}
        self.error_load_modules = 0
        self.inline_handlers_owners = {}
        self._latest_kernel_version_cache = None

    async def init_scheduler(self):
        """Инициализация планировщика задач"""

        class SimpleScheduler:
            def __init__(self, kernel):
                self.kernel = kernel
                self.tasks = []
                self.running = True
                self.task_counter = 0
                self.task_registry = {}  # Реестр задач для управления

            async def add_interval_task(self, func, interval_seconds, task_id=None):
                """Добавление задачи с интервалом"""
                if not self.running:
                    return None

                if task_id is None:
                    task_id = f"task_{self.task_counter}"
                    self.task_counter += 1

                async def wrapper():
                    while self.running and task_id in self.task_registry:
                        await asyncio.sleep(interval_seconds)
                        if not self.running or task_id not in self.task_registry:
                            break
                        try:
                            await func()
                        except Exception as e:
                            self.kernel.log_error(f"Task {task_id} error: {e}")

                task = asyncio.create_task(wrapper())
                self.tasks.append(task)
                self.task_registry[task_id] = {
                    "task": task,
                    "func": func,
                    "interval": interval_seconds,
                    "type": "interval",
                }
                return task_id

            async def add_daily_task(self, func, hour, minute, task_id=None):
                """Добавление ежедневной задачи"""
                if not self.running:
                    return None

                if task_id is None:
                    task_id = f"daily_{self.task_counter}"
                    self.task_counter += 1

                async def wrapper():
                    while self.running and task_id in self.task_registry:
                        now = datetime.now()
                        target = now.replace(hour=hour, minute=minute, second=0)
                        if now > target:
                            target += timedelta(days=1)

                        delay = (target - now).total_seconds()
                        if delay > 0:
                            await asyncio.sleep(delay)

                        if not self.running or task_id not in self.task_registry:
                            break
                        try:
                            await func()
                        except Exception as e:
                            self.kernel.log_error(f"Task {task_id} error: {e}")

                task = asyncio.create_task(wrapper())
                self.tasks.append(task)
                self.task_registry[task_id] = {
                    "task": task,
                    "func": func,
                    "hour": hour,
                    "minute": minute,
                    "type": "daily",
                }
                return task_id

            async def add_task(self, func, delay_seconds, task_id=None):
                """Добавление одноразовой задачи"""
                if not self.running:
                    return None

                if task_id is None:
                    task_id = f"once_{self.task_counter}"
                    self.task_counter += 1

                async def wrapper():
                    await asyncio.sleep(delay_seconds)
                    if not self.running or task_id not in self.task_registry:
                        return
                    try:
                        await func()
                    except Exception as e:
                        self.kernel.log_error(f"Task {task_id} error: {e}")
                    finally:
                        self.cancel_task(task_id)

                task = asyncio.create_task(wrapper())
                self.tasks.append(task)
                self.task_registry[task_id] = {
                    "task": task,
                    "func": func,
                    "delay": delay_seconds,
                    "type": "once",
                }
                return task_id

            def cancel_task(self, task_id):
                """Отмена задачи по ID"""
                if task_id in self.task_registry:
                    task_info = self.task_registry[task_id]
                    task_info["task"].cancel()
                    # Удаляем из списков
                    if task_info["task"] in self.tasks:
                        self.tasks.remove(task_info["task"])
                    del self.task_registry[task_id]
                    return True
                return False

            def cancel_all_tasks(self):
                """Отмена всех задач"""
                self.running = False
                for task_id in list(self.task_registry.keys()):
                    self.cancel_task(task_id)

            def get_tasks(self):
                """Получение списка всех задач"""
                return [
                    {
                        "id": task_id,
                        "type": info["type"],
                        "status": "running" if info["task"].done() else "stopped",
                    }
                    for task_id, info in self.task_registry.items()
                ]

        self.scheduler = SimpleScheduler(self)
        self.logger.info("=> Планировщик инициализирован")

    def add_middleware(self, middleware_func):
        self.middleware_chain.append(middleware_func)

    async def process_with_middleware(self, event, handler):
        for middleware in self.middleware_chain:
            result = await middleware(event, handler)
            if result is False:
                return False
        return await handler(event)

    async def get_module_config(self, module_name, default=None):
        config_key = f"module_config_{module_name}"
        config_json = await self.db_get("kernel", config_key)
        if config_json:
            return json.loads(config_json)
        return default or {}

    async def save_module_config(self, module_name, config):
        config_key = f"module_config_{module_name}"
        await self.db_set("kernel", config_key, json.dumps(config))

    async def init_db(self):
        """Инициализация базы данных."""

        try:
            self.db_conn = await aiosqlite.connect("userbot.db")
            await self.create_tables()
            self.logger.info("=> База данных инициализирована")
            return True
        except Exception as e:
            self.logger.error(f"=X Ошибка инициализации БД: {e}")
            return False

    async def create_tables(self):
        """Создание таблиц в БД."""
        await self.db_conn.execute(
            """
            CREATE TABLE IF NOT EXISTS module_data (
                module TEXT,
                key TEXT,
                value TEXT,
                PRIMARY KEY (module, key)
            )
        """
        )
        await self.db_conn.commit()

    async def db_set(self, module, key, value):
        """Store key-value pair for module."""
        if not self.db_conn:
            raise Exception("База данных не инициализирована")

        await self.db_conn.execute(
            "INSERT OR REPLACE INTO module_data VALUES (?, ?, ?)",
            (module, key, str(value)),
        )
        await self.db_conn.commit()

    async def db_get(self, module, key):
        """Retrieve value for module."""
        if not self.db_conn:
            raise Exception("База данных не инициализирована")

        cursor = await self.db_conn.execute(
            "SELECT value FROM module_data WHERE module = ? AND key = ?", (module, key)
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def db_delete(self, module, key):
        """Delete key from module storage."""
        if not self.db_conn:
            raise Exception("База данных не инициализирована")

        await self.db_conn.execute(
            "DELETE FROM module_data WHERE module = ? AND key = ?", (module, key)
        )
        await self.db_conn.commit()

    async def db_query(self, query, parameters):
        """Execute custom SQL query."""
        if not self.db_conn:
            raise Exception("База данных не инициализирована")

        cursor = await self.db_conn.execute(query, parameters)
        rows = await cursor.fetchall()
        return rows

    def setup_logging(self):

        logger = logging.getLogger("kernel")
        logger.setLevel(logging.DEBUG)

        handler = RotatingFileHandler(
            "logs/kernel.log", maxBytes=10 * 1024 * 1024, backupCount=5
        )
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def log_debug(self, message):
        self.logger.debug(message)

    def log_error(self, message):
        self.logger.error(message)

    def load_repositories(self):
        """Загружает список репозиториев из конфига"""
        self.repositories = self.config.get("repositories", [])
        print(f"load repositorie: {self.repositories}")

    async def save_repositories(self):
        """Сохраняет список репозиториев в конфиг"""
        self.config["repositories"] = self.repositories
        with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
            self.logger.debug("save repositories")

    def save_config(self):
        """Сохраняет конфигурацию в файл"""
        with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
            self.logger.debug("save config")

    @staticmethod
    def _parse_version(version_str: str) -> tuple:
        """
        Parse version string like '1.0.2.1' into tuple of integers.
        Non‑numeric parts are treated as 0.
        """
        parts = []
        for part in version_str.split('.'):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(0)
        return tuple(parts)

    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        """
        Compare two version strings.
        Returns:
            -1 if v1 < v2
             0 if v1 == v2
             1 if v1 > v2
        """
        v1_tuple = Kernel._parse_version(v1)
        v2_tuple = Kernel._parse_version(v2)
        if v1_tuple < v2_tuple:
            return -1
        if v1_tuple > v2_tuple:
            return 1
        return 0

    async def get_latest_kernel_version(self) -> str:
        """Fetch the latest kernel version from the update repository (cached for 1 hour)."""
        if self._latest_kernel_version_cache:
            cache_time, version = self._latest_kernel_version_cache
            if time.time() - cache_time < 3600:
                return version

        url = self.UPDATE_REPO + "version.txt"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        version = (await resp.text()).strip()
                        self._latest_kernel_version_cache = (time.time(), version)
                        return version
        except Exception as e:
            self.logger.error(f"Error fetching latest kernel version: {e}")

        # Fallback to current version
        return self.VERSION

    async def _check_kernel_version_compatibility(self, code: str) -> Tuple[bool, str]:
        """
        Examine module source for '# scop: kernel ...' directives and verify
        that the current kernel version satisfies all requirements.
        Returns (True, "") if compatible, (False, error_message) otherwise.
        """
        lines = code.split('\n')
        directives = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('# scop: kernel'):
                rest = stripped[len('# scop: kernel'):].strip()
                if rest:
                    directives.append(rest)

        if not directives:
            return True, ""

        current_version = self.VERSION
        latest_version = None  # lazy load

        for directive in directives:
            parts = directive.split()
            if not parts:
                continue

            # min <version>
            if parts[0] == 'min':
                if len(parts) >= 2 and parts[1].startswith('v'):
                    required = parts[1][1:]
                    if self._compare_versions(current_version, required) < 0:
                        return False, f"Module requires kernel version ≥ {required}, current is {current_version}"
            # max <version>
            elif parts[0] == 'max':
                if len(parts) >= 2 and parts[1].startswith('v'):
                    required = parts[1][1:]
                    if self._compare_versions(current_version, required) > 0:
                        return False, f"Module requires kernel version ≤ {required}, current is {current_version}"
            # v<version>  or  v[__lastest__]
            else:
                if not parts[0].startswith('v'):
                    continue
                spec = parts[0][1:]  # strip 'v'
                if spec == '[__lastest__]':
                    if latest_version is None:
                        latest_version = await self.get_latest_kernel_version()
                    if self._compare_versions(current_version, latest_version) != 0:
                        return False, f"Module requires the latest kernel version ({latest_version}), but current is {current_version}"
                else:
                    if self._compare_versions(current_version, spec) != 0:
                        return False, f"Module requires kernel version exactly {spec}, but current is {current_version}"

        return True, ""


    def set_loading_module(self, module_name, module_type):
        """Устанавливает текущий загружаемый модуль"""
        self.current_loading_module = module_name
        self.current_loading_module_type = module_type
        self.logger.debug(f"set loading module:{module_name}, {module_type}")

    def clear_loading_module(self):
        """Очищает информацию о загружаемом модуле"""
        self.current_loading_module = None
        self.current_loading_module_type = None
        self.logger.debug("clear loading module")

    def unregister_module_commands(self, module_name):
        """Удаляет все команды модуля"""
        to_remove = []
        for cmd, owner in self.command_owners.items():
            if owner == module_name:
                to_remove.append(cmd)

        for cmd in to_remove:
            del self.command_handlers[cmd]
            del self.command_owners[cmd]
            self.logger.debug(f"del command:{cmd}")
        self.unregister_module_inline_handlers(module_name)

    async def add_repository(self, url):
        """Добавляет новый репозиторий"""
        if url in self.repositories or url == self.default_repo:
            return False, "Репозиторий уже существует"

        try:
            modules = await self.get_repo_modules_list(url)
            if modules:
                self.repositories.append(url)
                await self.save_repositories()
                return True, f"Репозиторий добавлен ({len(modules)} модулей)"
            else:
                return False, "Не удалось получить список модулей"
        except Exception:
            return False, "Ошибка при проверке репозитория"

    async def remove_repository(self, index):
        """Удаляет репозиторий по индексу"""
        try:
            idx = int(index) - 1
            if 0 <= idx < len(self.repositories):
                removed = self.repositories.pop(idx)
                await self.save_repositories()
                self.logger.debug("del repository:YES")
                return True, "Репозиторий удален"
            else:
                return False, "Неверный индекс"
        except Exception as e:
            self.logger.error(f"del repository:{e}")
            return False, f"Ошибка удаления: {e}"

    async def get_repo_name(self, url):
        """Получает название репозитория из modules.ini"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/name.ini") as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        return content.strip()
        except Exception:
            pass
        return url.split("/")[-2] if "/" in url else url

    async def get_command_description(self, module_name, command):
        if module_name in self.system_modules:
            file_path = f"modules/{module_name}.py"
        elif module_name in self.loaded_modules:
            file_path = f"modules_loaded/{module_name}.py"
        else:
            return "🫨 У команды нету описания"

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
                metadata = await self.get_module_metadata(code)
                return metadata["commands"].get(command, "🫨 У команды нету описания")
        except Exception:
            return "🫨 У команды нету описания"

    def register_command(self, pattern, func=None):
        """Регистрация команды с проверкой конфликтов"""
        cmd = pattern.lstrip("^\\" + self.custom_prefix)
        if cmd.endswith("$"):
            cmd = cmd[:-1]

        if self.current_loading_module is None:
            raise ValueError("Не установлен текущий модуль для регистрации команд")

        if cmd in self.command_handlers:
            existing_owner = self.command_owners.get(cmd)
            if existing_owner in self.system_modules:
                self.logger.error(f"Попытка перезаписать системную команду: {cmd}")
                raise CommandConflictError(
                    f"Попытка перезаписать системную команду: {cmd}",
                    conflict_type="system",
                    command=cmd,
                )
            else:
                self.logger.error(
                    f"Конфликт команд: {cmd} уже зарегистрирована модулем {existing_owner}"
                )
                raise CommandConflictError(
                    f"Конфликт команд: {cmd} уже зарегистрирована модулем {existing_owner}",
                    conflict_type="user",
                    command=cmd,
                )

        if func:
            self.command_handlers[cmd] = func
            self.command_owners[cmd] = self.current_loading_module
            return func
        else:

            def decorator(f):
                self.command_handlers[cmd] = f
                self.command_owners[cmd] = self.current_loading_module
                return f

            return decorator

    def register_command_bot(self, pattern, func=None):
        """Регистрация команд для бота (начинающихся с /)"""
        if not pattern.startswith("/"):
            pattern = "/" + pattern

        # Убираем префикс и параметры для хранения
        cmd = pattern.lstrip("/").split()[0] if " " in pattern else pattern.lstrip("/")

        if self.current_loading_module is None:
            raise ValueError("Не установлен текущий модуль для регистрации бот-команд")

        if cmd in self.bot_command_handlers:
            existing_owner = self.bot_command_owners.get(cmd)
            self.logger.error(
                f"Конфликт бот-команд: {cmd} уже зарегистрирована модулем {existing_owner}"
            )
            raise CommandConflictError(
                f"Конфликт бот-команд: {cmd} уже зарегистрирована модулем {existing_owner}",
                conflict_type="bot",
                command=cmd,
            )

        if func:
            self.bot_command_handlers[cmd] = (pattern, func)
            self.bot_command_owners[cmd] = self.current_loading_module
            return func
        else:

            def decorator(f):
                self.bot_command_handlers[cmd] = (pattern, f)
                self.bot_command_owners[cmd] = self.current_loading_module
                return f

            return decorator

    def unregister_module_bot_commands(self, module_name):
        """Удаляет все бот-команды модуля"""
        to_remove = []
        for cmd, owner in self.bot_command_owners.items():
            if owner == module_name:
                to_remove.append(cmd)

        for cmd in to_remove:
            del self.bot_command_handlers[cmd]
            del self.bot_command_owners[cmd]
            self.logger.debug(f"del bot command:{cmd}")

    def setup_directories(self):
        for directory in [
            self.MODULES_DIR,
            self.MODULES_LOADED_DIR,
            self.IMG_DIR,
            self.LOGS_DIR,
        ]:
            if not os.path.exists(directory):
                os.makedirs(directory)

    def load_or_create_config(self):
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                self.config = json.load(f)

            required_fields = ["api_id", "api_hash", "phone"]
            if all(
                field in self.config and self.config[field] for field in required_fields
            ):
                self.setup_config()
                return True
            else:
                print(f"{Colors.RED}❌ Конфиг поврежден или неполный{Colors.RESET}")
                return False
        else:
            return False

    def is_bot_available(self):
        """
        Проверяет, доступен ли бот-клиент

        Returns:
            bool: True если bot_client существует и авторизован
        """
        return (
            hasattr(self, "bot_client")
            and self.bot_client is not None
            and self.bot_client.is_connected()
        )

    async def inline_query_and_click(
        self,
        chat_id,
        query,
        bot_username=None,
        result_index=0,
        buttons=None,
        silent=False,
        reply_to=None,
        **kwargs,
    ):
        """
        Выполнение инлайн-запроса и автоматический клик по указанному результату.

        Args:
            chat_id (int): ID чата для отправки
            query (str): Текст инлайн-запроса
            bot_username (str, optional): Username бота для инлайн-запроса
            result_index (int): Индекс результата для клика (по умолчанию 0)
            buttons (list, optional): Дополнительные кнопки в формате словарей
            silent (bool): Отправлять сообщение тихо
            reply_to (int): ID сообщения для ответа
            **kwargs: Дополнительные параметры

        Returns:
            tuple: (success, message) - статус и сообщение

        Example:
            # С кнопками
            success, msg = await kernel.inline_query_and_click(
                chat_id=123456789,
                query='"Привет мир" | [{"text": "Кнопка 1", "type": "callback", "data": "action_1"}]'
            )
        """
        try:

            if not bot_username:
                bot_username = self.config.get("inline_bot_username")
                if not bot_username:
                    raise ValueError(
                        "Bot username not specified and not configured in config"
                    )

            self.cprint(
                f"{self.Colors.BLUE}=> Выполняю инлайн-запрос: {query[:100]}... с @{bot_username}{self.Colors.RESET}"
            )

            results = await self.client.inline_query(bot_username, query)

            if not results:
                self.logger.warning(
                    f"=? Не найдено инлайн-результатов для запроса: {query[:50]}..."
                )
                return False, None

            if result_index >= len(results):
                self.logger.warning(
                    f"=> Индекс результата {result_index} выходит за пределы, использую первый результат"
                )
                result_index = 0

            result = results[result_index]

            click_kwargs = {}
            if buttons:
                formatted_buttons = []
                for button in buttons:
                    if isinstance(button, dict):
                        btn_text = button.get("text", "Кнопка")
                        btn_type = button.get("type", "callback").lower()

                        if btn_type == "callback":
                            btn_data = button.get("data", "")
                            formatted_buttons.append(
                                [Button.inline(btn_text, btn_data.encode())]
                            )
                        elif btn_type == "url":
                            btn_url = button.get("url", button.get("data", ""))
                            formatted_buttons.append([Button.url(btn_text, btn_url)])
                        elif btn_type == "switch":
                            btn_query = button.get("query", button.get("data", ""))
                            btn_hint = button.get("hint", "")
                            formatted_buttons.append(
                                [Button.switch_inline(btn_text, btn_query, btn_hint)]
                            )

                if formatted_buttons:
                    click_kwargs["buttons"] = formatted_buttons

            if silent:
                click_kwargs["silent"] = silent
            if reply_to:
                click_kwargs["reply_to"] = reply_to

            click_kwargs.update(kwargs)

            message = await result.click(chat_id, **click_kwargs)

            self.logger.info(f"=> Успешно выполнен инлайн-запрос: {query[:50]}...")
            return True, message

        except Exception as e:
            self.logger.error(f"=X Ошибка выполнения инлайн-запроса: {e}")
            await self.handle_error(e, source="inline_query_and_click")
            return False, None

    async def manual_inline_example(self, chat_id, query, bot_username=None):
        """
        Manual method for inline query execution with more control.

        This method allows full manual control over inline query execution,
        including custom result selection and manual sending.

        Args:
            chat_id (int): Target chat ID
            query (str): Inline query text
            bot_username (str, optional): Specific bot username to use

        Returns:
            list: List of inline query results or empty list on error
        """
        try:
            if not bot_username:
                bot_username = self.config.get("inline_bot_username")
                if not bot_username:
                    self.cprint(
                        f"{self.Colors.RED}No bot username specified{self.Colors.RESET}"
                    )
                    return []

            # Get all results
            results = await self.client.inline_query(bot_username, query)

            if not results:
                return []

            # Return raw results for manual processing
            return results

        except Exception as e:
            self.cprint(
                f"{self.Colors.RED}Manual inline query failed: {e}{self.Colors.RESET}"
            )
            return []

    async def restart(self, chat_id=None, message_id=None):
        """
        Перезагружает процесс юзербота.
        Если переданы chat_id и message_id, они сохраняются для уведомления после рестарта.
        """
        await restart_kernel(self, chat_id, message_id)

    async def send_inline_from_config(self, chat_id, query, buttons=None):
        """
        Simplified method that uses configured inline bot.

        This is the simplest way to use inline queries when you want
        to use the bot configured in config.json.

        Args:
            chat_id (int): Target chat ID
            query (str): Inline query text
            buttons (list, optional): Buttons to attach

        Returns:
            bool: Success status
        """
        return await self.inline_query_and_click(
            chat_id=chat_id,
            query=query,
            bot_username=self.config.get("inline_bot_username"),
            buttons=buttons,
        )
    def unregister_module_inline_handlers(self, module_name):
        to_remove = []
        for pattern, owner in self.inline_handlers_owners.items():
            if owner == module_name:
                to_remove.append(pattern)

        for pattern in to_remove:
            del self.inline_handlers[pattern]
            del self.inline_handlers_owners[pattern]
            self.logger.debug(f"del inline handler: {pattern}")

    def register_inline_handler(self, pattern, handler):
        try:
            if not hasattr(self, "inline_handlers"):
                self.inline_handlers = {}
            if not hasattr(self, "inline_handlers_owners"):
                self.inline_handlers_owners = {}
            self.inline_handlers[pattern] = handler
            if self.current_loading_module:
                self.inline_handlers_owners[pattern] = self.current_loading_module
        except Exception as e:
            self.logger.error(f"=X Error register inline commands: {e}")

    def register_callback_handler(self, pattern, handler):
        """Регистрация обработчика callback-кнопок"""
        if not hasattr(self, "callback_handlers"):
            self.callback_handlers = {}

        try:
            if isinstance(pattern, str):
                pattern = pattern.encode()
            self.callback_handlers[pattern] = handler

            if self.client:

                @self.client.on(events.CallbackQuery(data=pattern))
                async def callback_wrapper(event):
                    try:
                        await handler(event)

                    except Exception as e:
                        await self.handle_error(
                            e, source="callback_handler", event=event
                        )

        except Exception as e:
            self.cprint(
                f"{self.Colors.RED}=X Ошибка регистрации callback: {e}{self.Colors.RESET}"
            )

    async def log_network(self, message):
        """Логирование сетевых событий"""
        if hasattr(self, "send_log_message"):
            await self.send_log_message(f"🌐 {message}")
            self.logger.info(message)

    async def log_error(self, message):
        """Логирование ошибок"""
        if hasattr(self, "send_log_message"):
            await self.send_log_message(f"🔴 {message}")
            self.logger.info(message)

    async def log_module(self, message):
        """Логирование событий модулей"""
        if hasattr(self, "send_log_message"):
            await self.send_log_message(f"⚙️ {message}")
            self.logger.info(message)

    async def detected_module_type(self, module):
        """
        Determine the module type based on its registration pattern.
        Returns:
            'method' if module has a register attribute with callable methods,
            'new' if module has a callable register(kernel),
            'old' if module has a callable register(client),
            'none' otherwise.
        """
        if hasattr(module, "register"):
            if hasattr(module.register, "__dict__"):
                for name, attr in module.register.__dict__.items():
                    if callable(attr) and not name.startswith("__"):
                        return "method"

            if callable(module.register):
                sig = inspect.signature(module.register)
                params = list(sig.parameters.keys())
                if len(params) == 1:
                    param_name = params[0]
                    if param_name == "kernel":
                        return "new"
                    elif param_name == "client":
                        return "old"
        return "none"


    async def load_module_from_file(
        self,
        file_path: str,
        module_name: str,
        is_system: bool = False
    ) -> Tuple[bool, str]:
        """
        Dynamically loads a Python module from a file and registers it with the kernel.

        This method handles module loading, dependency management, and integration
        with the bot's ecosystem. It supports different module registration patterns
        and automatic dependency installation.

        Args:
            file_path: Path to the Python module file
            module_name: Name to assign to the loaded module
            is_system: If True, loads as a system module with higher privileges

        Returns:
            Tuple of (success: bool, message: str)

        Raises:
            CommandConflictError: If module introduces conflicting commands
            ImportError: If required dependencies cannot be installed

        Example:
            >>> success, message = await kernel.load_module_from_file(
            ...     "modules/my_module.py",
            ...     "my_module"
            ... )
            >>> if success:
            ...     print(f"Loaded: {message}")
        """
        try:
            # Read the module source code
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()

            compatible, version_msg = await self._check_kernel_version_compatibility(code)
            if not compatible:
                return False, f"Kernel version mismatch: {version_msg}"

            # Check for incompatible module patterns (Heroku/hikka)
            incompatible_patterns = [
                "from .. import",
                "import loader",
                "__import__('loader')",
                "from hikkalt import",
                "from herokult import"
            ]

            for pattern in incompatible_patterns:
                if pattern in code:
                    return False, "Incompatible module type (Heroku/hikka style modules not supported)"

            # Clean up any previous instance of this module
            if module_name in sys.modules:
                # Allow module reloading by removing from sys.modules
                del sys.modules[module_name]

            # Create module specification and object
            spec = importlib.util.spec_from_file_location(
                module_name, file_path
            )
            if spec is None:
                return False, f"Failed to create module spec for {module_name}"

            module = importlib.util.module_from_spec(spec)

            # Inject kernel references into module
            module.kernel = self
            module.client = self.client
            module.custom_prefix = self.custom_prefix
            module.__file__ = file_path
            module.__name__ = module_name

            # Store in sys.modules before execution for proper imports
            sys.modules[module_name] = module

            # Set loading context for command registration
            self.set_loading_module(
                module_name,
                "system" if is_system else "user"
                )

            try:
                # Execute the module
                spec.loader.exec_module(module)
            except ImportError as e:
                # Handle missing dependencies
                return await self._handle_missing_dependency(
                    e,
                    file_path,
                    module_name,
                    is_system
                )
            except SyntaxError as e:
                # Provide detailed syntax error information
                error_msg = f"Syntax error in {Path(file_path).name}: {e.msg}\n"
                error_msg += f"  Line {e.lineno}: {e.text}"
                return False, error_msg

            # Detect module type and register appropriately
            module_type = await self.detected_module_type(module)

            registration_success = await self._register_module(
                module, module_type, module_name
            )

            if not registration_success:
                return False, "Module registration failed"

            # Store module reference
            if is_system:
                self.system_modules[module_name] = module
                self.logger.info(f"System module loaded: {module_name}")
            else:
                self.loaded_modules[module_name] = module
                self.logger.info(f"User module loaded: {module_name}")

            # Initialize module if it has an init function
            if hasattr(module, 'init') and callable(module.init):
                try:
                    await module.init()
                    self.logger.debug(f"Module {module_name} init() executed")
                except Exception as e:
                    self.logger.error(f"Module {module_name} init() failed: {e}")
                    # Continue even if init fails, module is still loaded

            return True, f"Module {module_name} loaded successfully ({module_type} type)"

        except CommandConflictError as e:
            # Re-raise command conflicts for higher-level handling
            raise e
        except Exception as e:
            error_msg = f"Module loading error: {str(e)}"
            self.logger.error(f"Failed to load {module_name}: {e}", exc_info=True)
            return False, error_msg
        finally:
            # Always clear loading context
            self.clear_loading_module()


    async def _handle_missing_dependency(
        self,
        error: ImportError,
        file_path: str,
        module_name: str,
        is_system: bool
    ) -> Tuple[bool, str]:
        """
        Handle missing dependencies by attempting automatic installation.

        Args:
            error: The ImportError that occurred
            file_path: Path to the module file
            module_name: Name of the module being loaded
            is_system: Whether it's a system module

        Returns:
            Tuple of (success: bool, message: str)
        """
        error_msg = str(error)

        # Try to extract module name from various error patterns
        patterns = [
            r"No module named '([^']+)'",
            r"ModuleNotFoundError: No module named '([^']+)'",
            r"cannot import name '([^']+)' from",
            r"ImportError: cannot import name '([^']+)'"
        ]

        missing_dependency = None
        for pattern in patterns:
            match = re.search(pattern, error_msg)
            if match:
                missing_dependency = match.group(1)
                break

        if missing_dependency:
            self.logger.info(f"Missing dependency detected: {missing_dependency}")

            # Check if dependency is a standard library module
            if missing_dependency in sys.builtin_module_names:
                return False, f"Missing standard library module: {missing_dependency}"

            # Ask for installation confirmation (if enabled)
            if hasattr(self, 'auto_install_deps') and not self.auto_install_deps:
                return False, f"Missing dependency: {missing_dependency}. Please install with: pip install {missing_dependency}"

            # Attempt automatic installation
            install_success, install_msg = await self._install_dependency(missing_dependency)

            if install_success:
                # Retry loading the module after successful installation
                self.logger.info(f"Dependency installed, retrying module load: {missing_dependency}")
                return await self.load_module_from_file(file_path, module_name, is_system)
            else:
                return False, f"Failed to install dependency {missing_dependency}: {install_msg}"

        return False, f"Import error: {error_msg}"


    async def _install_dependency(self, package_name: str) -> Tuple[bool, str]:
        """
        Install a Python package using pip.

        Args:
            package_name: Name of the package to install

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            self.logger.info(f"Installing dependency: {package_name}")

            # Use sys.executable to ensure we use the correct Python/pip
            pip_command = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--quiet",  # Reduce output noise
                package_name
            ]

            # Add --user flag if running in system Python without sudo
            if not hasattr(os, 'geteuid') or os.geteuid() != 0:  # Not root
                pip_command.append("--user")

            # Run pip install
            process = await asyncio.create_subprocess_exec(
                *pip_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                self.logger.info(f"Successfully installed {package_name}")
                return True, f"Installed {package_name}"
            else:
                error_msg = stderr.decode().strip()
                self.logger.error(f"Failed to install {package_name}: {error_msg}")

                # Try without --user flag if that was the issue
                if "--user" in pip_command and "Permission denied" in error_msg:
                    self.logger.info("Retrying without --user flag")
                    pip_command.remove("--user")
                    # Retry in synchronous mode (simplified)
                    try:
                        subprocess.check_call(pip_command)
                        return True, f"Installed {package_name}"
                    except subprocess.CalledProcessError as e:
                        return False, f"Installation failed: {e}"

                return False, error_msg

        except Exception as e:
            self.logger.error(f"Error during dependency installation: {e}")
            return False, str(e)

    async def _register_module(self, module, module_type, module_name):
        try:
            if module_type == "method":
                # Execute all callable methods on module.register
                if hasattr(module, "register") and hasattr(module.register, "__dict__"):
                    for name, attr in module.register.__dict__.items():
                        if callable(attr) and not name.startswith("__"):
                            if inspect.iscoroutinefunction(attr):
                                await attr(self)
                            else:
                                attr(self)
                else:
                    return False

            elif module_type == "new":
                if hasattr(module, "register") and callable(module.register):
                    if inspect.iscoroutinefunction(module.register):
                        await module.register(self)
                    else:
                        module.register(self)
                else:
                    return False

            elif module_type == "old":
                if hasattr(module, "register") and callable(module.register):
                    if inspect.iscoroutinefunction(module.register):
                        await module.register(self.client)
                    else:
                        module.register(self.client)
                else:
                    return False

            else:
                # Fallback – try to detect and run
                if hasattr(module, "register") and callable(module.register):
                    try:
                        if inspect.iscoroutinefunction(module.register):
                            await module.register(self)
                        else:
                            module.register(self)
                    except Exception:
                        try:
                            if inspect.iscoroutinefunction(module.register):
                                await module.register(self.client)
                            else:
                                module.register(self.client)
                        except Exception:
                            return False
                else:
                    return False

            return True

        except CommandConflictError:
            raise
        except Exception as e:
            self.logger.error(f"Module registration failed for {module_name}: {e}")
            raise e


    async def install_from_url(self, url, module_name=None, auto_dependencies=True):
        """
        Установка модуля из URL

        Args:
            url (str): URL модуля
            module_name (str, optional): Имя модуля (если None, извлекается из URL)
            auto_dependencies (bool): Автоматически устанавливать зависимости

        Returns:
            tuple: (success, message)
        """
        import os
        import aiohttp

        try:

            if not module_name:
                if url.endswith(".py"):
                    module_name = os.path.basename(url)[:-3]
                else:

                    parts = url.rstrip("/").split("/")
                    module_name = parts[-1]
                    if "." in module_name:
                        module_name = module_name.split(".")[0]

            if module_name in self.system_modules:
                return False, f"Модуль: {module_name}, системный"
                self.logger.debug(f"install_from_url:modules is system {module_name}")

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return (
                            False,
                            f"Не удалось скачать модуль (статус: {resp.status})",
                        )
                        self.logger.warning(
                            f"Не удалось скачать модуль (статус: {resp.status}"
                        )
                    code = await resp.text()

            compatible, version_msg = await self._check_kernel_version_compatibility(code)
            if not compatible:
                return False, f"Kernel version mismatch: {version_msg}"
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                temp_path = f.name

            try:

                dependencies = []
                if auto_dependencies and "requires" in code:
                    import re

                    reqs = re.findall(r"# requires: (.+)", code)
                    if reqs:
                        dependencies = [req.strip() for req in reqs[0].split(",")]

                if dependencies:

                    for dep in dependencies:
                        self.logger.info(f"Установка зависимости: {dep}...")
                        try:
                            process = await asyncio.create_subprocess_exec(
                                sys.executable,
                                "-m",
                                "pip",
                                "install",
                                dep,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                            )
                            stdout, stderr = await process.communicate()

                            if process.returncode == 0:
                                self.logger.info(f"Зависимость {dep} установлена")
                            else:
                                self.logger.error(
                                    f"Ошибка установки {dep}: {stderr.decode()}"
                                )
                                return False, f"Ошибка установки зависимости {dep}"
                        except Exception as e:
                            self.logger.error(f"Ошибка запуска pip: {e}")
                            return False, f"Ошибка запуска pip: {e}"

                success, message = await self.load_module_from_file(
                    temp_path, module_name, False
                )

                if success:

                    target_path = os.path.join(
                        self.MODULES_LOADED_DIR, f"{module_name}.py"
                    )
                    with open(target_path, "w", encoding="utf-8") as f:
                        f.write(code)

                    return True, f"Модуль {module_name} успешно установлен из URL"
                else:
                    return False, f"Ошибка загрузки модуля: {message}"

            finally:

                import os

                if os.path.exists(temp_path):
                    os.remove(temp_path)

        except Exception as e:
            return False, f"Ошибка установки из URL: {str(e)}"

    async def send_with_emoji(self, chat_id, text, **kwargs):
        """Универсальная отправка с поддержкой кастомных эмодзи"""
        if not self.emoji_parser or not self.emoji_parser.is_emoji_tag(text):
            return await self.client.send_message(chat_id, text, **kwargs)

        try:
            parsed_text, entities = self.emoji_parser.parse_to_entities(text)

            input_peer = await self.client.get_input_entity(chat_id)
            result = await self.client.send_message(
                input_peer,
                parsed_text,
                entities=entities,
                **{k: v for k, v in kwargs.items() if k != "entities"},
            )
            self.logger.debug(f"text:{parsed_text}:{input_peer}")
            return result
        except Exception as e:
            self.cprint(
                f"{self.Colors.RED}=X Ошибка отправки с эмодзи: {e}{self.Colors.RESET}"
            )
            fallback_text = (
                self.emoji_parser.remove_emoji_tags(text) if self.emoji_parser else text
            )
            return await self.client.send_message(chat_id, fallback_text, **kwargs)

    def format_with_html(self, text, entities):
        """Форматирует текст с сущностями в HTML"""
        if not HTML_PARSER_AVAILABLE:
            return html.escape(text)

        from utils.html_parser import telegram_to_html

        return telegram_to_html(text, entities)

    async def get_module_metadata(self, code):
        import re
        metadata = {
            "author": "неизвестен",
            "version": "X.X.X",
            "description": "описание отсутствует",
            "commands": {},
        }


        patterns = {
            "author": r"#\s*author\s*:\s*(.+)",
            "version": r"#\s*version\s*:\s*(.+)",
            "description": r"#\s*description\s*:\s*(.+)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, code, re.IGNORECASE)
            if match:
                metadata[key] = match.group(1).strip()


        decorator_pattern = r'(@(?:kernel\.register\.command|register\.command|kernel\.register_command|kernel\.register\.bot_command|register\.bot_command|client\.on)\s*\([^)]+\))\s*\n'
        direct_call_pattern = r'(kernel\.register_command\s*\([^)]+\))\s*\n'

        positions = []
        for match in re.finditer(decorator_pattern, code, re.MULTILINE):
            positions.append((match.start(), match.group(1)))
        for match in re.finditer(direct_call_pattern, code, re.MULTILINE):
            positions.append((match.start(), match.group(1)))
        positions.sort(key=lambda x: x[0])


        def collect_comment_before(pos):
            before_text = code[:pos]
            lines = before_text.splitlines(keepends=True)
            if before_text and not before_text.endswith('\n'):
                lines = lines[:-1]

            comment_lines = []
            for line in reversed(lines):
                stripped = line.strip()
                if stripped.startswith('#'):
                    comment_lines.insert(0, stripped.lstrip('#').strip())
                elif stripped:
                    break
            return ' '.join(comment_lines) if comment_lines else None

        def collect_comment_after(pos, decorator_end=None):
            if decorator_end is None:
                end_match = re.search(r'\)', code[pos:])
                if end_match:
                    decorator_end = pos + end_match.end()
                else:
                    decorator_end = pos

            start = decorator_end
            while start < len(code) and code[start].isspace():
                start += 1

            same_line_match = re.match(r'#\s*(.+)', code[start:].split('\n')[0])
            if same_line_match:
                return same_line_match.group(1).strip()

            remaining = code[start:]
            lines = remaining.split('\n')
            comment_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('#'):
                    comment_lines.append(stripped.lstrip('#').strip())
                elif stripped:
                    break
                else:
                    break
            return ' '.join(comment_lines) if comment_lines else None

        for i, (pos, decorator) in enumerate(positions):
            cmd_name = None
            cmd_match = re.search(r'[\'"]([^\'"]+)[\'"]', decorator)
            if cmd_match:
                cmd_name = cmd_match.group(1)
                if cmd_name.startswith('\\'):
                    cmd_name = cmd_name[1:]
                if cmd_name.startswith('.'):
                    cmd_name = cmd_name[1:]

            if not cmd_name:
                continue

            description = None

            comment_before = collect_comment_before(pos)
            if comment_before:
                description = comment_before
            else:

                comment_after = collect_comment_after(pos)
                if comment_after:
                    description = comment_after

            if description:
                metadata["commands"][cmd_name] = description
            else:
                metadata["commands"][cmd_name] = "🫨 Command has no description"

        if not metadata["commands"]:
            simple_patterns = [
                r'@kernel\.register\.command\s*\(\s*[\'"]([^\'"]+)[\'"]',
                r'@register\.command\s*\(\s*[\'"]([^\'"]+)[\'"]',
                r'@kernel\.register_command\s*\(\s*[\'"]([^\'"]+)[\'"]',
                r'kernel\.register_command\s*\(\s*[\'"]([^\'"]+)[\'"]',
                r'@kernel\.register\.bot_command\s*\(\s*[\'"]([^\'"]+)[\'"]',
                r'@register\.bot_command\s*\(\s*[\'"]([^\'"]+)[\'"]',
                r'@client\.on\s*\([^)]*pattern\s*=\s*r[\'"](\\.[^\'"]+)[\'"]',
            ]
            for pattern in simple_patterns:
                matches = re.findall(pattern, code, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        cmd = match[0]
                    else:
                        cmd = match
                    if cmd.startswith('\\'):
                        cmd = cmd[1:]
                    if cmd.startswith('.'):
                        cmd = cmd[1:]
                    if cmd not in metadata["commands"]:
                        metadata["commands"][cmd] = "🫨 Command has no description"

        return metadata

    async def download_module_from_repo(self, repo_url, module_name):
        """Скачивает модуль из репозитория с проверкой метаданных"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{repo_url}/{module_name}.py") as resp:
                    if resp.status == 200:
                        code = await resp.text()
                        return code
        except Exception:
            pass
        return None

    async def get_repo_modules_list(self, repo_url):
        """Получает список модулей из репозитория"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{repo_url}/modules.ini") as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        modules = [
                            line.strip() for line in content.split("\n") if line.strip()
                        ]
                        return modules
        except Exception:
            pass
        return []

    async def send_log_message(self, text, file=None):
        if not self.log_chat_id:
            print(f"[DEBUG] log_chat_id не установлен: {self.log_chat_id}")
            return False

        print(f"[DEBUG] Пытаюсь отправить в лог-чат: {self.log_chat_id}")
        print(f"[DEBUG] Текст: {text[:100]}...")
        print(f"[DEBUG] bot_client существует: {hasattr(self, 'bot_client')}")

        try:
            if (
                hasattr(self, "bot_client")
                and self.bot_client
                and await self.bot_client.is_user_authorized()
            ):
                print("[DEBUG] Использую bot_client для отправки")
                client_to_use = self.bot_client
            else:
                print("[DEBUG] Использую основной client для отправки")
                client_to_use = self.client

            if file:
                print(
                    f"[DEBUG] Отправляю файл: {file.name if hasattr(file, 'name') else 'unknown'}"
                )
                await client_to_use.send_file(
                    self.log_chat_id, file, caption=text, parse_mode="html"
                )
            else:
                print("[DEBUG] Отправляю текстовое сообщение")
                await client_to_use.send_message(
                    self.log_chat_id, text, parse_mode="html"
                )
            print("[DEBUG] Сообщение отправлено успешно")
            return True
        except Exception as e:
            print(f"[DEBUG] Ошибка отправки: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def send_error_log(self, error_text, source_file, message_info=""):
        if not self.log_chat_id:
            return

        formatted_error = f"""💠 <b>Source:</b> <code>{source_file}</code>
🔮 <b>Error:</b> <blockquote><code>{error_text[:500]}</code></blockquote>"""

        if message_info:
            formatted_error += f"\n🃏 <b>Message:</b> <code>{message_info[:300]}</code>"
        try:
            await self.send_log_message(formatted_error)
        except Exception:
            self.logger.error(f"Error sending error log: {error_text}")

    async def handle_error(self, error, source="unknown", event=None):
        import uuid

        error_signature = f"error:{source}:{type(error).__name__}:{str(error)}"
        if self.cache.get(error_signature):
            return
        self.cache.set(error_signature, True, ttl=60)

        error_id = f"err_{uuid.uuid4().hex[:8]}"
        error_text = str(error)
        error_traceback = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )

        self.cache.set(f"tb_{error_id}", error_traceback)

        formatted_error = (
            f"💠 <b>Source:</b> <code>{html.escape(source)}</code>\n"
            f"🔮 <b>Error:</b> <blockquote>👉 <code>{html.escape(error_text[:300])}</code></blockquote>"
        )

        if event:
            try:
                chat_title = getattr(event.chat, "title", "ЛС")
                user_info = (
                    await self.get_user_info(event.sender_id)
                    if event.sender_id
                    else "unknown"
                )
                formatted_error += (
                    f"\n💬 <b>Message info:</b>\n"
                    f"<blockquote>🪬 <b>User:</b> {user_info}\n"
                    f"⌨️ <b>Text:</b> <code>{html.escape(event.text[:200] if event.text else 'not text')}</code>\n"
                    f"📬 <b>Chat:</b> {chat_title}</blockquote>"
                )
            except Exception:
                pass

        try:
            full_error_log = f"Ошибка в {source}:\n{error_traceback}"
            self.save_error_to_file(full_error_log)
            print(f"=X {error_traceback}")

            buttons = [Button.inline("🔍 Traceback", data=f"show_tb:{error_id}")]

            client_to_use = (
                self.bot_client
                if (hasattr(self, "bot_client") and self.bot_client)
                else self.client
            )

            await client_to_use.send_message(
                self.log_chat_id,
                formatted_error,
                file=None,
                buttons=buttons,
                parse_mode="html",
            )

        except Exception as e:
            self.logger.error(f"Не удалось отправить лог ошибки: {e}")
            self.logger.error(f"Оригинальная ошибка: {error_traceback}")

    def save_error_to_file(self, error_text):
        """save to logs/kernel.log"""
        try:
            from pathlib import Path

            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)

            error_file = log_dir / "kernel.log"

            with open(error_file, "a", encoding="utf-8") as f:
                f.write(f"\n\n{'='*60}\n")
                f.write(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*60}\n")
                f.write(error_text)
        except Exception as e:
            self.logger.error(f"Ошибка при записи в kernel.log: {e}")

    async def get_thread_id(self, event):
        if not event:
            return None

        thread_id = None

        if hasattr(event, "reply_to") and event.reply_to:
            thread_id = getattr(event.reply_to, "reply_to_top_id", None)

        if not thread_id and hasattr(event, "message"):
            thread_id = getattr(event.message, "reply_to_top_id", None)

        return thread_id

    async def get_user_info(self, user_id):
        try:
            entity = await self.client.get_entity(user_id)

            if hasattr(entity, "first_name") or hasattr(entity, "last_name"):
                name = f"{entity.first_name or ''} {entity.last_name or ''}".strip()
                return f"{name} (@{entity.username or 'без username'})"
            elif hasattr(entity, "title"):
                return f"{entity.title} (чат/канал)"
            else:
                return f"ID: {user_id}"
        except Exception:
            return f"ID: {user_id}"

    def setup_config(self):
        try:
            self.custom_prefix = self.config.get("command_prefix", ".")
            self.aliases = self.config.get("aliases", {})
            self.power_save_mode = self.config.get("power_save_mode", False)
            self.API_ID = int(self.config["api_id"])
            self.API_HASH = str(self.config["api_hash"])
            self.PHONE = str(self.config["phone"])
            return True
        except (KeyError, ValueError, TypeError) as e:
            print(f"{Colors.RED}❌ Ошибка в конфиге: {e}{Colors.RESET}")
            return False

    def first_time_setup(self):
        print(f"\n{Colors.CYAN}⚙️  Первоначальная настройка юзербота{Colors.RESET}\n")

        while True:
            try:
                api_id_input = input(
                    f"{Colors.YELLOW}📝 Введите API ID: {Colors.RESET}"
                ).strip()
                if not api_id_input.isdigit():
                    print(f"{Colors.RED}❌ API ID должен быть числом{Colors.RESET}")
                    continue

                api_hash_input = input(
                    f"{Colors.YELLOW}📝 Введите API HASH: {Colors.RESET}"
                ).strip()
                if not api_hash_input:
                    print(f"{Colors.RED}❌ API HASH не может быть пустым{Colors.RESET}")
                    continue

                phone_input = input(
                    f"{Colors.YELLOW}📝 Введите номер телефона (формат: +1234567890): {Colors.RESET}"
                ).strip()
                if not phone_input.startswith("+"):
                    print(f"{Colors.RED}❌ Номер должен начинаться с +{Colors.RESET}")
                    continue

                try:
                    api_id = int(api_id_input)
                except ValueError:
                    print(f"{Colors.RED}❌ API ID должен быть числом{Colors.RESET}")
                    continue

                self.config = {
                    "api_id": api_id,
                    "api_hash": api_hash_input,
                    "phone": phone_input,
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
                    "db_version": self.DB_VERSION,
                }

                with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, ensure_ascii=False, indent=2)

                self.setup_config()
                print(f"{Colors.GREEN}✅ Конфиг сохранен{Colors.RESET}")
                return True

            except KeyboardInterrupt:
                print(f"\n{Colors.RED}❌ Настройка прервана{Colors.RESET}")
                sys.exit(1)

    def cprint(self, text, color=""):
        print(f"{color}{text}{Colors.RESET}")

    def is_admin(self, user_id):
        return hasattr(self, "ADMIN_ID") and user_id == self.ADMIN_ID

    async def init_client(self):
        import sys
        from utils.platform import get_platform_name
        from utils.platform import PlatformDetector

        platform = PlatformDetector()

        self.logger.info(
            f"{self.Colors.CYAN}=- Инициализация MCUB на {get_platform_name()} (Python {sys.version_info.major}.{sys.version_info.minor})...{self.Colors.RESET}"
        )

        from telethon.sessions import SQLiteSession

        proxy = self.config.get("proxy")

        session = SQLiteSession("user_session")

        self.client = TelegramClient(
            session,
            self.API_ID,
            self.API_HASH,
            proxy=proxy,
            connection_retries=3,
            request_retries=3,
            flood_sleep_threshold=30,
            device_model=f"MCUB-{platform.detect()}",
            system_version=f"Python {sys.version}",
            app_version=f"MCUB {self.VERSION}",
            lang_code="en",
            system_lang_code="en-US",
            base_logger=None,
            catch_up=False,
        )

        try:
            await self.client.start(phone=self.PHONE, max_attempts=3)

            if not await self.client.is_user_authorized():
                self.logger.error(
                    f"{self.Colors.RED}=X Не удалось авторизоваться{self.Colors.RESET}"
                )
                return False

            me = await self.client.get_me()
            if not me or not hasattr(me, "id"):
                self.logger.error(
                    f"{self.Colors.RED}=X Неверные данные пользователя{self.Colors.RESET}"
                )
                return False

            self.ADMIN_ID = me.id
            self.logger.info(
                f"{self.Colors.GREEN}Авторизован как: {me.first_name} (ID: {me.id}){self.Colors.RESET}"
            )

            return True

        except Exception as e:
            self.logger.error(
                f"{self.Colors.RED}=X Ошибка инициализации клиента: {e}{self.Colors.RESET}"
            )
            import traceback

            traceback.print_exc()
            return False

    async def load_system_modules(self):
        for file_name in os.listdir(self.MODULES_DIR):
            if file_name.endswith(".py"):
                try:
                    module_name = file_name[:-3]
                    file_path = os.path.join(self.MODULES_DIR, file_name)

                    spec = importlib.util.spec_from_file_location(
                        module_name, file_path
                    )
                    module = importlib.util.module_from_spec(spec)

                    module.kernel = self
                    module.client = self.client
                    module.custom_prefix = self.custom_prefix

                    sys.modules[module_name] = module

                    self.set_loading_module(module_name, "system")
                    spec.loader.exec_module(module)

                    module.register(self)
                    self.system_modules[module_name] = module
                    self.logger.info(
                        f"{Colors.GREEN}=> Загружен системный модуль: {module_name}{Colors.RESET}"
                    )

                except CommandConflictError as e:
                    self.logger.error(
                        f"{Colors.RED}=X Ошибка загрузки системного модуля {module_name}: {e}{Colors.RESET}"
                    )
                    self.error_load_modules += 1
                except Exception as e:
                    self.logger.error(
                        f"{Colors.RED}=X Ошибка загрузки модуля {file_name}: {e}{Colors.RESET}"
                    )
                    self.error_load_modules += 1
                finally:
                    self.clear_loading_module()

    async def load_user_modules(self):
        files = os.listdir(self.MODULES_LOADED_DIR)

        if "log_bot.py" in files:
            files.remove("log_bot.py")
            files.insert(0, "log_bot.py")

        for file_name in files:
            if file_name.endswith(".py"):
                try:
                    module_name = file_name[:-3]
                    file_path = os.path.join(self.MODULES_LOADED_DIR, file_name)

                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    if "def register(kernel):" in content:
                        spec = importlib.util.spec_from_file_location(
                            module_name, file_path
                        )
                        module = importlib.util.module_from_spec(spec)

                        module.kernel = self
                        module.client = self.client
                        module.custom_prefix = self.custom_prefix

                        sys.modules[module_name] = module

                        self.set_loading_module(module_name, "user")
                        spec.loader.exec_module(module)

                        if hasattr(module, "register"):
                            module.register(self)
                            self.loaded_modules[module_name] = module
                            self.logger.info(
                                f"{self.Colors.BLUE}=> Модуль загружен {module_name}{self.Colors.RESET}"
                            )
                    else:
                        spec = importlib.util.spec_from_file_location(
                            module_name, file_path
                        )
                        module = importlib.util.module_from_spec(spec)

                        sys.modules[module_name] = module
                        self.set_loading_module(module_name, "user")
                        spec.loader.exec_module(module)

                        if hasattr(module, "register"):
                            module.register(self.client)

                            self.loaded_modules[module_name] = module
                            self.logger.warning(
                                f"{self.Colors.GREEN}=> Загружен пользовательский модуль (старый стиль): {module_name}{self.Colors.RESET}"
                            )

                except CommandConflictError as e:
                    error_msg = f"Конфликт команд при загрузке модуля {file_name}: {e}"
                    self.logger.error(
                        f"{self.Colors.RED}{error_msg}{self.Colors.RESET}"
                    )
                    self.error_load_modules += 1
                    try:
                        await self.handle_error(
                            e, source=f"load_module_conflict:{file_name}"
                        )
                    except Exception:
                        pass

                except Exception as e:
                    error_msg = f"Ошибка загрузки модуля {file_name}: {e}"
                    self.logger.error(
                        f"{self.Colors.RED}{error_msg}{self.Colors.RESET}"
                    )
                    self.error_load_modules += 1
                    try:
                        await self.handle_error(e, source=f"load_module:{file_name}")
                    except Exception:
                        pass
                finally:
                    self.clear_loading_module()

    def raw_text(self, source: any) -> str:
        try:

            if not hasattr(self, "html_converter") or self.html_converter is None:
                from utils.raw_html import RawHTMLConverter

                self.html_converter = RawHTMLConverter(keep_newlines=True)

            if isinstance(source, str):
                return html.escape(source).replace("\n", "<br/>")
            self.logger.debug(f"raw_text:{self.html_converter.convert_message(source)}")
            return self.html_converter.convert_message(source)

        except Exception:
            # Резервный вариант, если что-то пошло не так
            text = getattr(source, "message", str(source))
            return html.escape(text).replace("\n", "<br/>")

    def _prepare_buttons(self, raw_buttons):
        """
        Преобразует упрощённое описание кнопок в список словарей.
        Поддерживает форматы:
            - список словарей: [{"text": "...", "type": "...", "data": "..."}, ...]
            - список кортежей/списков: [("текст", "тип", "данные", "подсказка"), ...]
        """
        buttons_list = []
        for button in raw_buttons:
            if isinstance(button, dict):
                buttons_list.append(button)
            elif isinstance(button, (list, tuple)):
                if len(button) >= 2:
                    btn_data = {"text": str(button[0])}
                    btn_type = str(button[1]).lower() if len(button) > 1 else "callback"
                    btn_data["type"] = btn_type
                    if len(button) >= 3:
                        if btn_type == "callback":
                            btn_data["data"] = str(button[2])
                        elif btn_type == "url":
                            btn_data["url"] = str(button[2])
                        elif btn_type == "switch":
                            btn_data["query"] = str(button[2])
                            if len(button) >= 4:
                                btn_data["hint"] = str(button[3])
                    buttons_list.append(btn_data)
        return buttons_list

    async def inline_form(self, chat_id, title, fields=None, buttons=None, auto_send=True, ttl=200, **kwargs):
        """
        Создание и отправка инлайн-формы

        Args:
            chat_id (int): ID чата для отправки
            title (str): Заголовок формы
            fields (list/dict, optional): Поля формы (будут преобразованы в текст)
            buttons (optional): Кнопки. Могут быть переданы в двух форматах:
                - Упрощённый: список словарей или кортежей (как раньше)
                - Готовые кнопки Telethon: список списков объектов-кнопок
                (например, [[Button.inline('Текст', b'data')], [Button.url('URL', 'https://...')]])
            auto_send (bool): Автоматически отправить форму
            ttl (int): Время жизни формы в кэше (секунды)
            **kwargs: Дополнительные параметры для inline_query_and_click

        Returns:
            tuple: (success, message) если auto_send=True
            str: ID формы если auto_send=False
        """
        try:
            from core_inline.handlers import InlineHandlers

            # Формируем текст из title и fields
            query_parts = [title]
            if fields:
                if isinstance(fields, dict):
                    for field, value in fields.items():
                        query_parts.append(f"{field}: {value}")
                elif isinstance(fields, list):
                    for i, field in enumerate(fields, 1):
                        query_parts.append(f"Поле {i}: {field}")
            text = "\n".join(query_parts)

            # Определяем все возможные классы кнопок Telethon
            BUTTON_TYPES = tuple(
                getattr(tl_types, name) for name in dir(tl_types)
                if name.startswith('KeyboardButton')
            )

            # Обрабатываем кнопки
            buttons_to_use = None
            if buttons is not None:
                # Проверяем, не являются ли кнопки уже готовыми объектами Telethon
                if (isinstance(buttons, list) and len(buttons) > 0 and
                    all(isinstance(row, list) for row in buttons) and
                    buttons[0] and len(buttons[0]) > 0 and
                    isinstance(buttons[0][0], BUTTON_TYPES)):
                    # Это уже готовая структура кнопок — оставляем как есть
                    buttons_to_use = buttons
                else:
                    # Преобразуем упрощённый формат в список словарей
                    buttons_to_use = self._prepare_buttons(buttons)

            handlers = InlineHandlers(self, self.bot_client)
            form_id = handlers.create_inline_form(text, buttons_to_use, ttl)

            if auto_send:
                success, message = await self.inline_query_and_click(
                    chat_id=chat_id,
                    query=form_id,
                    **kwargs
                )
                return success, message
            else:
                return form_id

        except Exception as e:
            self.logger.error(f"{self.Colors.RED}=X Ошибка создания инлайн-формы: {e}{self.Colors.RESET}")
            await self.handle_error(e, source="inline_form")
            if auto_send:
                return False, None
            else:
                return None
    async def process_command(self, event, depth=0):
            if depth > 5:
                self.logger.error(f"Recursion limit reached for aliases: {event.text}")
                return False
            text = event.text

            if not text.startswith(self.custom_prefix):
                return False

            cmd = (
                text[len(self.custom_prefix) :].split()[0]
                if " " in text
                else text[len(self.custom_prefix) :]
            )
            if cmd in self.aliases:
                alias_content = self.aliases[cmd]

                if alias_content in self.command_handlers:
                    await self.command_handlers[alias_content](event)
                    return True

                else:
                    args = text[len(self.custom_prefix) + len(cmd):]

                    new_text = self.custom_prefix + alias_content + args
                    event.text = new_text
                    if hasattr(event, 'message'):
                        event.message.message = new_text
                        event.message.text = new_text

                    self.logger.debug(f"Alias processed: {cmd} -> {new_text[:50]}...")
                    return await self.process_command(event, depth + 1)

            if cmd in self.command_handlers:
                await self.command_handlers[cmd](event)
                return True

            return False

    async def process_bot_command(self, event):
        """Обработка команд бота"""
        text = event.text

        if not text.startswith("/"):
            return False

        # Получаем команду (первое слово без /)
        cmd = text.split()[0][1:] if " " in text else text[1:]

        # Убираем @username бота если есть
        if "@" in cmd:
            cmd = cmd.split("@")[0]

        if cmd in self.bot_command_handlers:
            pattern, handler = self.bot_command_handlers[cmd]
            await handler(event)
            return True

        return False

    async def safe_connect(self):
        while self.reconnect_attempts < self.max_reconnect_attempts:
            if self.shutdown_flag:
                return False
            try:
                if self.client.is_connected():
                    return True

                await self.client.connect()
                if await self.client.is_user_authorized():
                    self.reconnect_attempts = 0
                    return True
            except Exception:
                self.reconnect_attempts += 1
                await asyncio.sleep(self.reconnect_delay * self.reconnect_attempts)

        return False

    async def send_inline(self, chat_id, query, buttons=None):
        bot_username = self.config.get("inline_bot_username")
        if not bot_username:
            return False

        try:
            results = await self.client.inline_query(bot_username, query)
            if results:
                if buttons:
                    await results[0].click(chat_id, reply_to=None, buttons=buttons)
                else:
                    await results[0].click(chat_id)
                return True
        except Exception:
            pass
        return False

    async def setup_inline_bot(self):
        try:
            inline_bot_token = self.config.get("inline_bot_token")
            if not inline_bot_token:
                self.logger.warning(
                    f"{Colors.YELLOW}Инлайн-бот не настроен (отсутствует токен){Colors.RESET}"
                )
                return False

            self.logger.info("=- Запускаю инлайн-бота...")

            self.bot_client = TelegramClient(
                "inline_bot_session", self.API_ID, self.API_HASH, timeout=30
            )

            await self.bot_client.start(bot_token=inline_bot_token)

            bot_me = await self.bot_client.get_me()
            bot_username = bot_me.username

            self.config["inline_bot_username"] = bot_username

            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)

            try:
                import sys
                import os

                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

                from core_inline.handlers import InlineHandlers

                handlers = InlineHandlers(self, self.bot_client)
                await handlers.register_handlers()


                bot_task = asyncio.create_task(self.bot_client.run_until_disconnected())
                if not hasattr(self, '_background_tasks'):
                    self._background_tasks = []
                self._background_tasks.append(bot_task)

                self.logger.info(f"=> Инлайн-бот запущен: {bot_username}")
                return True
            except Exception as e:
                self.logger.error(
                    f"=> Ошибка регистрации обработчиков инлайн-бота: {str(e)}"
                )
                traceback.print_exc()
                return False

        except Exception as e:
            self.logger.error(
                f"{Colors.RED}=X Инлайн-бот не запущен: {str(e)}{Colors.RESET}"
            )
            traceback.print_exc()
            return False

    async def run(self):
        if not self.load_or_create_config():
            if not self.first_time_setup():
                self.logger.error("=X Не удалось настроить юзербот")
                return

        self.load_repositories()
        logging.basicConfig(level=logging.INFO)
        await self.init_scheduler()
        kernel_start_time = time.time()

        if not await self.init_client():
            return

        try:
            await self.init_db()
        except ImportError:
            self.cprint(
                f"{Colors.YELLOW}Установите: pip install aiosqlite{Colors.RESET}"
            )
        except Exception as e:
            self.cprint(f"{Colors.RED}=X Ошибка инициализации БД: {e}{Colors.RESET}")

        await self.setup_inline_bot()

        if not self.config.get("inline_bot_token"):
            from core_inline.bot import InlineBot

            self.inline_bot = InlineBot(self)
            await self.inline_bot.setup()

        modules_start_time = time.time()
        await self.load_system_modules()
        await self.load_user_modules()
        modules_end_time = time.time()

        @self.client.on(events.NewMessage(outgoing=True))
        # @self.client.on(events.MessageEdited(outgoing=True))
        async def message_handler(event):
            premium_emoji_telescope = (
                '<tg-emoji emoji-id="5429283852684124412">🔭</tg-emoji>'
            )
            premium_emoji_karandash = (
                '<tg-emoji emoji-id="5334882760735598374">📝</tg-emoji>'
            )
            try:
                await self.process_command(event)
            except Exception as e:
                await self.handle_error(e, source="message_handler", event=event)

                error_log = traceback.format_exc()

                if len(error_log) > 1000:
                    error_log = error_log[-1000:] + "\n...(truncated)"

                try:
                    await event.edit(
                        f"{premium_emoji_telescope} <b>Ошибка, смотри логи</b>\n"
                        f"{premium_emoji_karandash} <i>Full Log command:</i>\n"
                        f"<pre>{error_log}</pre>",
                        parse_mode="html",
                    )
                except Exception as edit_err:
                    self.logger.error(
                        f"Не удалось отредактировать сообщение: {edit_err}"
                    )

        if hasattr(self, "bot_client") and self.bot_client:

            @self.bot_client.on(events.NewMessage(pattern="/"))
            async def bot_command_handler(event):
                try:
                    await self.process_bot_command(event)
                    self.logger.debug(f"cmd:{event.text}|{event.id}")
                except Exception as e:
                    await self.handle_error(
                        e, source="bot_command_handler", event=event
                    )

        start_logo = f"""
 _    _  ____ _   _ ____
| \\  / |/ ___| | | | __ )
| |\\/| | |   | | | |  _ \\
| |  | | |___| |_| | |_) |
|_|  |_|\\____|\\___/|____/
Kernel is load.

• Version: {self.VERSION}
• Prefix: {self.custom_prefix}\n"""
        e_l_m = self.error_load_modules
        if e_l_m:
            start_logo += f'• Error load modules: {e_l_m}\n'

        print(start_logo)
        self.logger.debug("start MCUB")
        if os.path.exists(self.RESTART_FILE):
            try:
                with open(self.RESTART_FILE, "r") as f:
                    data = f.read().split(",")
                    if len(data) >= 3:
                        try:
                            chat_id = int(data[0])
                            msg_id = int(data[1])
                            restart_time = float(data[2])
                        except (ValueError, IndexError) as e:
                            self.logger.error(f"=X Некорректные данные в файле перезагрузки: {e}")
                            os.remove(self.RESTART_FILE)
                            return

                        os.remove(self.RESTART_FILE)
                        me = await self.client.get_me()

                        mcub_emoji = (
                            '<tg-emoji emoji-id="5470015630302287916">🔮</tg-emoji><tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
                            if me.premium
                            else "MCUB"
                        )


                        thread_id = None
                        if len(data) >= 4 and data[3]:
                            try:
                                thread_id = int(data[3])
                            except ValueError:
                                self.logger.warning(f"Некорректный thread_id: {data[3]}")
                                thread_id = None

                    mlfb = round((modules_end_time - modules_start_time) * 1000, 2)

                    emojis = [
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
                    emoji = random.choice(emojis)

                    premium_emoji_alembic = (
                        '<tg-emoji emoji-id="5332654441508119011">⚗️</tg-emoji>'
                    )
                    premium_emoji_package = (
                        '<tg-emoji emoji-id="5399898266265475100">📦</tg-emoji>'
                    )
                    premium_emoji_error = (
                        '<tg-emoji emoji-id="5208923808169222461">🥀</tg-emoji>'
                    )

                    total_time = round((time.time() - restart_time) * 1000, 2)

                    restart_strings = {
                        'ru': {
                            'reboot_error': 'Твой <b>{mcub_emoji}</b> <b>загрузился c ошибками</b> :(',
                            'reboot_success': 'Перезагрузка <b>успешна!</b>',
                            'modules_loading': 'но модули ещё загружаются...',
                            'fully_loaded': 'Твой <b>{mcub_emoji}</b> полностью загрузился!',
                            'restart_failed': '=X Не удалось отправить сообщение о перезагрузке: {error}',
                            'no_connection': '=X Не удалось отправить сообщение о перезагрузке: нет соединения'
                        },
                        'en': {
                            'reboot_error': 'Your <b>{mcub_emoji}</b> <b>loaded with errors</b> :(',
                            'reboot_success': 'Reboot <b>successful!</b>',
                            'modules_loading': 'but modules are still loading...',
                            'fully_loaded': 'Your <b>{mcub_emoji}</b> is fully loaded!',
                            'restart_failed': '=X Failed to send restart message: {error}',
                            'no_connection': '=X Failed to send restart message: no connection'
                        }
                    }


                    def get_restart_string(key, **kwargs):
                        language = self.config.get('language', 'ru')
                        strings = restart_strings.get(language, restart_strings['ru'])
                        text = strings.get(key, key)
                        return text.format(**kwargs) if kwargs else text

                    if self.client.is_connected():
                        try:

                            sms = await self.client.edit_message(
                                chat_id,
                                msg_id,
                                f"{premium_emoji_alembic} {get_restart_string('reboot_success')} {emoji}\n"
                                f"<i>{get_restart_string('modules_loading')}</i> <b>KLB:</b> <code>{total_time} ms</code>",
                                parse_mode="html",
                            )

                            await asyncio.sleep(1)

                            # await self.client.delete_messages(chat_id, msg_id)

                            send_params = {}
                            if thread_id:
                                send_params["reply_to"] = thread_id
                            load_error = self.error_load_modules
                            if not load_error:
                                await sms.edit(
                                    f"{premium_emoji_package} {get_restart_string('fully_loaded', mcub_emoji=mcub_emoji)}\n"
                                    f"<blockquote><b>Kernel load:</b> <code>{total_time} ms</code>. <b>Modules load:</b> <code>{mlfb} ms</code>.</blockquote>",
                                    parse_mode="html",
                                )
                            else:
                                await sms.edit(
                                    f"{premium_emoji_error} {get_restart_string('reboot_error', mcub_emoji=mcub_emoji)}\n"
                                    f"<blockquote><b>Kernel load:</b> <code>{total_time} ms</code>. <b>Modules error load:</b> <code>{load_error}</code></blockquote>",
                                    parse_mode="html"
                                )
                        except Exception as e:
                            self.logger.error(
                                f"{get_restart_string('restart_failed', error=e)}{Colors.RESET}"
                            )
                            await self.handle_error(e, source="restart")

                    else:
                        self.cprint(
                            f"{Colors.YELLOW}{get_restart_string('no_connection')}{Colors.RESET}"
                        )
            except FileNotFoundError:
                self.logger.error(f"=X Файл перезагрузки не найден: {self.RESTART_FILE}")
            except IOError as e:
                self.logger.error(f"=X Ошибка чтения файла перезагрузки: {e}")
            except Exception as e:
                self.logger.error(f"=X Непредвиденная ошибка при обработке перезагрузки: {e}")
                if os.path.exists(self.RESTART_FILE):
                    try:
                        os.remove(self.RESTART_FILE)
                    except Exception:
                        pass

        await self.client.run_until_disconnected()
