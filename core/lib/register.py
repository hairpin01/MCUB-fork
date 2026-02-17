# author: @Hairpin00
# version: 1.0.1
# description: Registration system for Telegram bot handlers

import inspect
from telethon import events
from typing import Any, Callable, Dict, Optional


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

    def on_load(self, func: Optional[Callable] = None) -> Callable:
        """
        Decorator to register an on-load callback on the module.

        The decorated function is automatically called by the kernel right after
        the module has been fully registered — on both initial startup and every
        subsequent `reload`. Use it for one-time initialisation that must run
        after all commands/handlers are already registered (e.g. fetching data,
        warming up a cache, starting a background task).

        The callback receives the kernel instance as its only argument and can
        be either a regular or an async function.

        Example:
            >>> @kernel.register.on_load()
            >>> async def on_load(kernel):
            >>>     kernel.logger.info("MyModule ready")
            >>>     await some_client.connect()

            >>> # Also works without parentheses:
            >>> @kernel.register.on_load
            >>> async def on_load(kernel):
            >>>     ...
        """
        def decorator(f: Callable) -> Callable:
            caller_frame = inspect.stack()[1][0]
            module = inspect.getmodule(caller_frame)

            if module:
                if not hasattr(module, "register"):
                    module.register = type("RegisterObject", (), {})()

                # Store under a fixed attribute so the kernel can always find it
                module.register.__on_load__ = f

            return f

        if func is None:
            return decorator
        return decorator(func)

    def uninstall(self, func: Optional[Callable] = None) -> Callable:
        """
        Decorator to register an uninstall callback on the module.

        The decorated function will be automatically called by the kernel
        when the module is being unloaded/unregistered (via `um`, `reload`,
        or any other loader operation that calls `unregister_module_commands`).

        Use this to clean up resources, cancel tasks, close connections, etc.

        The callback receives the kernel instance as its only argument and
        can be either a regular or an async function.

        Example:
            >>> @kernel.register.uninstall()
            >>> async def on_unload(kernel):
            >>>     await some_client.close()
            >>>     kernel.logger.info("MyModule cleaned up")

            >>> # Also works without parentheses:
            >>> @kernel.register.uninstall
            >>> async def on_unload(kernel):
            >>>     ...
        """
        def decorator(f: Callable) -> Callable:
            caller_frame = inspect.stack()[1][0]
            module = inspect.getmodule(caller_frame)

            if module:
                # Create module.register object if it doesn't exist yet
                if not hasattr(module, "register"):
                    module.register = type("RegisterObject", (), {})()

                # Store the uninstall callback under a fixed attribute name
                # so the kernel can always find it regardless of function name
                module.register.__uninstall__ = f

            return f

        if func is None:
            return decorator
        return decorator(func)

    def get_registered_methods(self) -> Dict[str, Callable]:
        """
        Get all methods registered through the @method decorator.

        Returns:
            Dictionary mapping method names to their functions
        """
        return self._methods.copy()
