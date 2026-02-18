# author: @Hairpin00
# version: 1.0.2
# description: Registration system for Telegram bot handlers

import asyncio
import inspect
import re
from telethon import events
from typing import Any, Callable, Dict, List, Optional, Tuple

class InfiniteLoop:
    """
    Managed background loop tied to a module's lifecycle.

    Created by @kernel.register.loop(). The kernel starts it after the module
    loads (if autostart=True) and stops it automatically on unload.

    Attributes:
        status (bool): True while the loop is running.
    """

    def __init__(
        self,
        func: Callable,
        interval: int,
        autostart: bool,
        wait_before: bool,
    ) -> None:
        self.func = func
        self.interval = interval
        self.autostart = autostart
        self._wait_before = wait_before
        self._task: Optional[asyncio.Task] = None
        self._kernel: Any = None
        self.status: bool = False

    def start(self) -> None:
        """Start the loop. No-op if already running."""
        if self._task and not self._task.done():
            return
        self._task = asyncio.ensure_future(self._run())

    def stop(self) -> None:
        """Stop the loop gracefully."""
        self.status = False
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    async def _run(self) -> None:
        self.status = True
        try:
            while self.status:
                if self._wait_before:
                    await asyncio.sleep(self.interval)
                if not self.status:
                    break
                try:
                    await self.func(self._kernel)
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    if self._kernel:
                        self._kernel.logger.error(
                            f"InfiniteLoop error in '{self.func.__name__}': {exc}"
                        )
                if not self._wait_before:
                    await asyncio.sleep(self.interval)
        finally:
            self.status = False

    def __repr__(self) -> str:
        return (
            f"<InfiniteLoop func={self.func.__name__!r} "
            f"interval={self.interval} running={self.status}>"
        )


def _watcher_passes_filters(event: Any, tags: Dict[str, Any]) -> bool:
    """Return True if *event* satisfies all tag filters."""
    msg = getattr(event, "message", event)

    # outgoing / incoming
    if tags.get("out") and not getattr(msg, "out", False):
        return False
    if tags.get("incoming") and getattr(msg, "out", False):
        return False

    # chat type
    chat = getattr(event, "chat", None)
    is_pm      = bool(chat) and not getattr(chat, "megagroup", False) \
                             and not getattr(chat, "broadcast", False) \
                             and not getattr(chat, "gigagroup", False)
    is_group   = getattr(chat, "megagroup", False) or getattr(chat, "gigagroup", False)
    is_channel = getattr(chat, "broadcast", False)

    if tags.get("only_pm")       and not is_pm:      return False
    if tags.get("no_pm")         and is_pm:          return False
    if tags.get("only_groups")   and not is_group:   return False
    if tags.get("no_groups")     and is_group:       return False
    if tags.get("only_channels") and not is_channel: return False
    if tags.get("no_channels")   and is_channel:     return False

    # media
    media   = getattr(msg, "media", None)
    photo   = media and hasattr(media, "photo")
    video   = media and hasattr(media, "video")
    doc     = media and hasattr(media, "document")
    audio   = doc and getattr(getattr(media, "document", None), "mime_type", "").startswith("audio")
    sticker = doc and any(
        type(a).__name__ == "DocumentAttributeSticker"
        for a in getattr(getattr(media, "document", None), "attributes", [])
    )

    if tags.get("only_media")    and not media:   return False
    if tags.get("no_media")      and media:       return False
    if tags.get("only_photos")   and not photo:   return False
    if tags.get("no_photos")     and photo:       return False
    if tags.get("only_videos")   and not video:   return False
    if tags.get("no_videos")     and video:       return False
    if tags.get("only_audios")   and not audio:   return False
    if tags.get("no_audios")     and audio:       return False
    if tags.get("only_docs")     and not doc:     return False
    if tags.get("no_docs")       and doc:         return False
    if tags.get("only_stickers") and not sticker: return False
    if tags.get("no_stickers")   and sticker:     return False

    # forwards / replies
    fwd   = getattr(msg, "fwd_from", None)
    reply = getattr(msg, "reply_to", None)
    if tags.get("only_forwards") and not fwd:   return False
    if tags.get("no_forwards")   and fwd:       return False
    if tags.get("only_reply")    and not reply: return False
    if tags.get("no_reply")      and reply:     return False

    # text filters
    text = getattr(msg, "text", "") or ""
    if "regex"      in tags and not re.search(tags["regex"], text): return False
    if "startswith" in tags and not text.startswith(tags["startswith"]): return False
    if "endswith"   in tags and not text.endswith(tags["endswith"]):     return False
    if "contains"   in tags and tags["contains"] not in text:           return False

    # sender / chat id filters
    if "from_id" in tags and getattr(event, "sender_id", None) != tags["from_id"]:
        return False
    if "chat_id" in tags and getattr(event, "chat_id", None) != tags["chat_id"]:
        return False

    return True

class Register:
    """
    Central registration system for MCUB module handlers.

    All handlers registered through this class (commands, events, watchers,
    loops) are tracked per-module and cleaned up automatically on unload.

    Attributes:
        kernel: Reference to the main bot kernel.
        _methods: Internal registry of @method-decorated functions.
    """

    def __init__(self, kernel: Any) -> None:
        self.kernel = kernel
        self._methods: Dict[str, Callable] = {}

    @staticmethod
    def _get_or_create_register(module: Any) -> Any:
        if not hasattr(module, "register"):
            module.register = type("RegisterObject", (), {})()
        return module.register

    @staticmethod
    def _ensure_list(reg: Any, attr: str) -> list:
        if not hasattr(reg, attr):
            setattr(reg, attr, [])
        return getattr(reg, attr)

    def method(self, func: Optional[Callable] = None) -> Callable:
        """
        Register a setup function on the module's register object.

        Called during module loading with the kernel as argument.
        The function name is arbitrary.

        Example:
            >>> @kernel.register.method
            >>> async def setup(kernel):
            >>>     kernel.logger.info("module ready")
        """
        def decorator(f: Callable) -> Callable:
            frame = inspect.stack()[1][0]
            module = inspect.getmodule(frame)
            if module:
                reg = self._get_or_create_register(module)
                setattr(reg, f.__name__, f)
                self._methods[f.__name__] = f
            return f

        if func is None:
            return decorator
        return decorator(func)

    def event(self, event_type: str, *args: Any, **kwargs: Any) -> Callable:
        """
        Register a Telegram event handler tracked by the kernel.

        Handlers are stored in ``module.register.__event_handlers__`` and
        removed automatically when the module is unloaded — no zombie
        handlers left behind after ``um`` or ``reload``.

        Args:
            event_type: ``newmessage`` | ``messageedited`` | ``messagedeleted``
                        | ``userupdate`` | ``inlinequery`` | ``callbackquery``
                        | ``raw`` (and short aliases like ``message``,
                        ``edited``, ``callback`` …).
            *args / **kwargs: Forwarded to the Telethon event constructor.

        Example:
            >>> @kernel.register.event("newmessage", pattern=r"hello")
            >>> async def hello(event):
            >>>     await event.reply("Hi!")
        """
        EVENT_TYPE_MAP: Dict[str, Any] = {
            "newmessage":     events.NewMessage,
            "message":        events.NewMessage,
            "messageedited":  events.MessageEdited,
            "edited":         events.MessageEdited,
            "messagedeleted": events.MessageDeleted,
            "deleted":        events.MessageDeleted,
            "userupdate":     events.UserUpdate,
            "user":           events.UserUpdate,
            "inlinequery":    events.InlineQuery,
            "inline":         events.InlineQuery,
            "callbackquery":  events.CallbackQuery,
            "callback":       events.CallbackQuery,
            "raw":            events.Raw,
            "custom":         events.Raw,
        }

        def decorator(handler: Callable) -> Callable:
            key = event_type.lower()
            if key not in EVENT_TYPE_MAP:
                raise ValueError(
                    f"Unknown event type: '{event_type}'. "
                    f"Valid: {', '.join(EVENT_TYPE_MAP)}"
                )
            event_obj = EVENT_TYPE_MAP[key](*args, **kwargs)
            self.kernel.client.add_event_handler(handler, event_obj)

            # track (handler, event_obj) for clean removal
            frame = inspect.stack()[1][0]
            module = inspect.getmodule(frame)
            if module:
                reg = self._get_or_create_register(module)
                tracked: List[Tuple[Callable, Any]] = self._ensure_list(
                    reg, "__event_handlers__"
                )
                tracked.append((handler, event_obj))

            return handler

        return decorator

    def command(self, pattern: str, **kwargs: Any) -> Callable:
        """
        Register a userbot command triggered by the custom prefix.

        Args:
            pattern: Command name. Regex anchors and the prefix are
                     stripped automatically.
            alias:   str or list[str] — alternative trigger names.
            more:    Arbitrary metadata stored in kernel.command_metadata.

        Example:
            >>> @kernel.register.command("ping", alias=["p"])
            >>> async def ping(event):
            >>>     await event.edit("Pong!")
        """
        def decorator(func: Callable) -> Callable:
            cmd = pattern.lstrip("^\\" + self.kernel.custom_prefix)
            if cmd.endswith("$"):
                cmd = cmd[:-1]

            if self.kernel.current_loading_module is None:
                raise ValueError(
                    "No current module set for command registration. "
                    "Commands must be registered from within a module."
                )

            self.kernel.command_handlers[cmd] = func
            self.kernel.command_owners[cmd] = self.kernel.current_loading_module

            alias = kwargs.get("alias")
            if alias:
                if isinstance(alias, str):
                    self.kernel.aliases[alias] = cmd
                elif isinstance(alias, list):
                    for a in alias:
                        self.kernel.aliases[a] = cmd

            more = kwargs.get("more")
            if more:
                if not hasattr(self.kernel, "command_metadata"):
                    self.kernel.command_metadata = {}
                self.kernel.command_metadata[cmd] = more

            return func

        return decorator


    def bot_command(self, pattern: str, **kwargs: Any) -> Callable:
        """
        Register a Telegram native /command (requires inline bot client).

        Example:
            >>> @kernel.register.bot_command("start")
            >>> async def start(event):
            >>>     await event.respond("Hello!")
        """
        def decorator(func: Callable) -> Callable:
            cmd_pattern = ("/" + pattern) if not pattern.startswith("/") else pattern
            cmd = (
                cmd_pattern.lstrip("/").split()[0]
                if " " in cmd_pattern
                else cmd_pattern.lstrip("/")
            )

            if self.kernel.current_loading_module is None:
                raise ValueError(
                    "No current module set for bot command registration."
                )

            self.kernel.bot_command_handlers[cmd] = (pattern, func)
            self.kernel.bot_command_owners[cmd] = self.kernel.current_loading_module
            return func

        return decorator


    def watcher(self, func: Optional[Callable] = None, **tags: Any) -> Callable:
        """
        Register a passive message watcher.

        Watchers are called for every new message (in/out) and cleaned up
        automatically on module unload. Filter events declaratively with
        tag kwargs — no ``if`` boilerplate inside the handler.

        Available tags:
            out, incoming
            only_pm, no_pm
            only_groups, no_groups
            only_channels, no_channels
            only_media, no_media
            only_photos, no_photos
            only_videos, no_videos
            only_audios, no_audios
            only_docs, no_docs
            only_stickers, no_stickers
            only_forwards, no_forwards
            only_reply, no_reply
            regex="pattern"
            startswith="text", endswith="text", contains="text"
            from_id=<int>, chat_id=<int>

        Example:
            >>> @kernel.register.watcher(only_pm=True, no_media=True)
            >>> async def pm_watcher(event):
            >>>     await event.reply("Got it!")

            >>> # No filters — fires on every message:
            >>> @kernel.register.watcher
            >>> async def all_messages(event):
            >>>     ...
        """
        def decorator(f: Callable) -> Callable:
            _tags = dict(tags)

            async def _wrapper(event: Any) -> None:
                if not _watcher_passes_filters(event, _tags):
                    return
                try:
                    await f(event)
                except Exception as exc:
                    self.kernel.logger.error(
                        f"Watcher '{f.__name__}' raised: {exc}"
                    )

            _wrapper.__name__ = f"watcher:{f.__name__}"
            _wrapper.__watcher_original__ = f

            event_obj = events.NewMessage()
            self.kernel.client.add_event_handler(_wrapper, event_obj)

            frame = inspect.stack()[1][0]
            module = inspect.getmodule(frame)
            if module:
                reg = self._get_or_create_register(module)
                wlist: List[Tuple[Callable, Any]] = self._ensure_list(
                    reg, "__watchers__"
                )
                wlist.append((_wrapper, event_obj))

            return f

        if func is not None and callable(func):
            return decorator(func)
        return decorator

    def loop(
        self,
        interval: int = 60,
        autostart: bool = True,
        wait_before: bool = False,
    ) -> Callable:
        """
        Declare a managed background loop on the module.

        The loop is started automatically after the module loads (when
        ``autostart=True``) and stopped on unload — no ``on_load`` /
        ``uninstall`` boilerplate needed.

        The decorated function receives the kernel as its only argument.

        Args:
            interval:    Seconds between iterations.
            autostart:   Start the loop right after the module loads.
            wait_before: Sleep *before* the first iteration instead of after.

        Returns:
            InfiniteLoop — can be used for manual ``start()`` / ``stop()``.

        Example:
            >>> @kernel.register.loop(interval=300)
            >>> async def heartbeat(kernel):
            >>>     await kernel.client.send_message("me", "alive")

            >>> # Manual start/stop:
            >>> @kernel.register.loop(interval=60, autostart=False)
            >>> async def checker(kernel):
            >>>     ...
            >>>
            >>> @kernel.register.command("startcheck")
            >>> async def start_cmd(event):
            >>>     checker.start()
            >>>
            >>> @kernel.register.command("stopcheck")
            >>> async def stop_cmd(event):
            >>>     checker.stop()
        """
        def decorator(f: Callable) -> "InfiniteLoop":
            il = InfiniteLoop(f, interval, autostart, wait_before)

            frame = inspect.stack()[1][0]
            module = inspect.getmodule(frame)
            if module:
                reg = self._get_or_create_register(module)
                loops: List[InfiniteLoop] = self._ensure_list(reg, "__loops__")
                loops.append(il)

            return il

        return decorator

    def on_load(self, func: Optional[Callable] = None) -> Callable:
        """
        Register a callback invoked after the module is fully loaded.

        Called on initial startup and on every ``reload``.
        Receives the kernel as its only argument. Supports async.

        Example:
            >>> @kernel.register.on_load()
            >>> async def setup(kernel):
            >>>     await some_service.connect()
        """
        frame = inspect.stack()[1][0]
        module = inspect.getmodule(frame)

        def decorator(f: Callable) -> Callable:
            if module:
                reg = self._get_or_create_register(module)
                reg.__on_load__ = f
            return f

        if func is None:
            return decorator
        return decorator(func)

    def on_install(self, func: Optional[Callable] = None) -> Callable:
        """
        Register a callback invoked **only the first time** the module is installed.

        Unlike ``on_load``, this is NOT called on ``reload`` — only when the
        module is freshly installed via ``dlm`` / ``loadera``. The kernel stores
        a persistent flag in the module config so subsequent loads skip it.

        Use it for welcome messages, first-run DB migrations, etc.

        Example:
            >>> @kernel.register.on_install()
            >>> async def first_time(kernel):
            >>>     await kernel.client.send_message("me", "Module installed!")
        """
        frame = inspect.stack()[1][0]
        module = inspect.getmodule(frame)

        def decorator(f: Callable) -> Callable:
            if module:
                reg = self._get_or_create_register(module)
                reg.__on_install__ = f
            return f

        if func is None:
            return decorator
        return decorator(func)

    def uninstall(self, func: Optional[Callable] = None) -> Callable:
        """
        Register a cleanup callback invoked when the module is unloaded.

        Triggered by ``um``, ``reload``, or any loader operation that calls
        ``unregister_module_commands``. Use to close connections, cancel
        external tasks, free resources.

        Example:
            >>> @kernel.register.uninstall()
            >>> async def on_unload(kernel):
            >>>     await some_client.close()
        """
        frame = inspect.stack()[1][0]
        module = inspect.getmodule(frame)

        def decorator(f: Callable) -> Callable:
            if module:
                reg = self._get_or_create_register(module)
                reg.__uninstall__ = f
            return f

        if func is None:
            return decorator
        return decorator(func)

    def get_registered_methods(self) -> Dict[str, Callable]:
        """Return a copy of all functions registered via @method."""
        return self._methods.copy()
