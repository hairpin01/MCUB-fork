# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмелька | @hairpin00

import asyncio
import copy
import inspect
import logging
from abc import ABC
from typing import Any, Callable

import uuid


class _ModuleLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        module_name = self.extra.get("module_name", "Unnamed")
        return f"[{module_name}] {msg}", kwargs


def command(
    pattern: str,
    *,
    alias: str | list[str] | None = None,
    doc: dict | None = None,
    doc_ru: str | None = None,
    doc_en: str | None = None,
) -> Callable:
    """
    Class-level decorator for registering commands in class-style modules.

    Usage::

        from core.lib.loader.module_base import ModuleBase, command

        class MyModule(ModuleBase):
            @command("hello", doc_ru="привет", doc_en="hello")
            async def cmd_hello(self, event):
                await event.edit("Hello!")
    """

    def decorator(func: Callable) -> Callable:
        if not hasattr(func, "_mcub_commands"):
            func._mcub_commands = []
        func._mcub_commands.append(
            (
                pattern,
                dict(alias=alias, doc=doc, doc_ru=doc_ru, doc_en=doc_en),
            )
        )
        return func

    return decorator


def inline(pattern: str) -> Callable:
    """
    Class-level decorator for registering inline handlers.

    Usage::

        from core.lib.loader.module_base import ModuleBase, command, inline

        class MyModule(ModuleBase):
            @inline("myinline")
            async def inline_handler(self, event):
                await event.answer("Hello!")
    """

    def decorator(func: Callable) -> Callable:
        if not hasattr(func, "_mcub_inline"):
            func._mcub_inline = []
        func._mcub_inline.append(pattern)
        return func

    return decorator


def callback(func: Callable | None = None, *, ttl: int = 900) -> Callable:
    """
    Class-level decorator for callback handlers with auto-generated uuid.

    Usage::

        from core.lib.loader.module_base import ModuleBase, command, callback

        class MyModule(ModuleBase):
            @command("test")
            async def cmd_test(self, event):
                btn = self.callback_button("Click", self.handle_click)
                await event.edit("Test", buttons=[btn])

            @callback(ttl=300)
            async def handle_click(self, event):
                await event.answer("Clicked!")
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_callbacks"):
            f._mcub_callbacks = []
        f._mcub_callbacks.append({"ttl": ttl})
        return f

    if func is not None:
        return decorator(func)
    return decorator


def watcher(
    func: Callable | None = None, *, bot_client: bool = False, **tags: Any
) -> Callable:
    """
    Class-level decorator for registering message watchers.

    Usage::

        from core.lib.loader.module_base import ModuleBase, command, watcher

        class MyModule(ModuleBase):
            @watcher(only_pm=True)
            async def pm_watcher(self, event):
                await event.reply("Got your message!")

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
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_watchers"):
            f._mcub_watchers = []
        f._mcub_watchers.append({"bot_client": bot_client, "tags": tags})
        return f

    if func is not None:
        return decorator(func)
    return decorator


def loop(
    interval: int = 60,
    autostart: bool = True,
    wait_before: bool = False,
) -> Callable:
    """
    Class-level decorator for registering background loops.

    Usage::

        from core.lib.loader.module_base import ModuleBase, command, loop

        class MyModule(ModuleBase):
            @loop(interval=300, autostart=True)
            async def heartbeat(self):
                await self.client.send_message("me", "Still alive!")

            @loop(interval=60, autostart=False)
            async def checker(self):
                ...

            @command("startcheck")
            async def cmd_start(self, event):
                self.checker.start()

    Args:
        interval: Seconds between iterations (default: 60).
        autostart: Start automatically on load (default: True).
        wait_before: Sleep before first iteration (default: False).
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_loops"):
            f._mcub_loops = []
        f._mcub_loops.append(
            {
                "interval": interval,
                "autostart": autostart,
                "wait_before": wait_before,
            }
        )
        return f

    return decorator


def event(
    event_type: str, *args: Any, bot_client: bool = False, **kwargs: Any
) -> Callable:
    """
    Class-level decorator for registering custom event handlers.

    Usage::

        from core.lib.loader.module_base import ModuleBase, event

        class MyModule(ModuleBase):
            @event("chataction", incoming=True)
            async def handle_chat_action(self, event):
                await event.reply("Chat action detected!")

            @event("newmessage", pattern=r"hello")
            async def handle_hello(self, event):
                await event.reply("Hello!")

    Available event types:
        newmessage, message, messageedited, edited, messagedeleted, deleted,
        messageread, read, userupdate, user, chataction, action,
        joinrequest, request, album, inlinequery, inline, callbackquery,
        callback, raw, custom

    Args:
        event_type: Type of event to handle.
        bot_client: Register on bot_client instead of client.
        *args, **kwargs: Forwarded to the Telethon event constructor.
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_events"):
            f._mcub_events = []
        f._mcub_events.append(
            {
                "event_type": event_type,
                "args": args,
                "bot_client": bot_client,
                "kwargs": kwargs,
            }
        )
        return f

    return decorator


def method(func: Callable | None = None) -> Callable:
    """
    Class-level decorator for registering generic methods.

    Unlike commands/watchers, methods are not event handlers. They are
    utility functions called during module setup.

    Usage::

        from core.lib.loader.module_base import ModuleBase, method

        class MyModule(ModuleBase):
            @method
            async def setup(self):
                await self._connect_service()
                self.log.info("Setup complete")

    The decorated method is called automatically during module load.
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_methods"):
            f._mcub_methods = []
        f._mcub_methods.append(True)
        return f

    if func is not None:
        return decorator(func)
    return decorator


def on_install(func: Callable | None = None) -> Callable:
    """
    Class-level decorator for one-time install callback.

    Unlike ``on_load``, this is called ONLY on first install, not on reload.

    Usage::

        from core.lib.loader.module_base import ModuleBase, on_install

        class MyModule(ModuleBase):
            @on_install
            async def first_time_setup(self):
                await self.client.send_message("me", "Module installed!")
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_on_install"):
            f._mcub_on_install = []
        f._mcub_on_install.append(True)
        return f

    if func is not None:
        return decorator(func)
    return decorator


def uninstall(func: Callable | None = None) -> Callable:
    """
    Class-level decorator for cleanup callback.

    Called when the module is unloaded (via ``um`` or ``reload``).

    Usage::

        from core.lib.loader.module_base import ModuleBase, uninstall

        class MyModule(ModuleBase):
            @uninstall
            async def cleanup(self):
                await self._close_connections()
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_uninstall"):
            f._mcub_uninstall = []
        f._mcub_uninstall.append(True)
        return f

    if func is not None:
        return decorator(func)
    return decorator


def bot_command(
    pattern: str,
    *,
    alias: str | list[str] | None = None,
    doc: dict | None = None,
    doc_ru: str | None = None,
    doc_en: str | None = None,
) -> Callable:
    """
    Class-level decorator for registering bot commands (via bot account, not userbot).

    Usage::

        from core.lib.loader.module_base import ModuleBase, bot_command

        class MyModule(ModuleBase):
            @bot_command("start", doc_ru="Старт", doc_en="Start")
            async def cmd_start(self, event):
                await event.reply("Hello from bot!")

    Args:
        pattern: Command name without prefix
        alias: Alternative triggers
        doc: Descriptions like {"ru": "...", "en": "..."}
        doc_ru: Russian description shorthand
        doc_en: English description shorthand
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_bot_commands"):
            f._mcub_bot_commands = []
        f._mcub_bot_commands.append(
            {
                "pattern": pattern,
                "alias": alias,
                "doc": doc,
                "doc_ru": doc_ru,
                "doc_en": doc_en,
            }
        )
        return f

    return decorator


def owner(only_admin: bool = False) -> Callable:
    """
    Class-level decorator for owner/admin permission check.

    Usage::

        from core.lib.loader.module_base import ModuleBase, command, owner

        class MyModule(ModuleBase):
            @command("admin")
            @owner(only_admin=True)
            async def cmd_admin(self, event):
                await event.reply("Admin access granted!")

    Args:
        only_admin: If True, only bot admins can use this command
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_owner"):
            f._mcub_owner = []
        f._mcub_owner.append({"only_admin": only_admin})
        return f

    return decorator


def permission(**tags: Any) -> Callable:
    """Apply watcher-style event filters to class-style handlers.

    Supports the same tag names as ``@watcher(...)`` and can be stacked on
    commands, bot commands, watchers, and custom events.
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_permissions"):
            f._mcub_permissions = []
        f._mcub_permissions.append(tags)
        return f

    return decorator


def error_handler(
    *,
    log_level: str = "error",
    reraise: bool = False,
    message: str | None = None,
) -> Callable:
    """Decorator for automatic error handling in module methods.

    Catches exceptions and logs them with optional custom message.
    Can optionally reraise the exception after logging.

    Args:
        log_level: Logging level for the error ("error", "warning", "info")
        reraise: If True, reraise the exception after logging
        message: Custom error message template (supports {exc}, {func}, {module})

    Example:
        @error_handler(log_level="warning", message="Command {func} failed: {exc}")
        async def cmd_test(self, event):
            ...
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_error_handler"):
            f._mcub_error_handler = []
        f._mcub_error_handler.append(
            {"log_level": log_level, "reraise": reraise, "message": message}
        )
        return f

    return decorator


class ModuleBase(ABC):
    """
    Base class for class-style MCUB modules.

    Example::

        from core.lib.loader.module_base import ModuleBase, command, watcher, loop

        class MyModule(ModuleBase):
            name = "MyModule"
            version = "1.0.0"

            @command("hello", doc_ru="привет")
            async def cmd_hello(self, event):
                await event.edit("Hello!")

            @watcher(only_pm=True)
            async def pm_watcher(self, event):
                await event.reply("Got it!")

            @loop(interval=300)
            async def heartbeat(self):
                await self.client.send_message("me", "alive")

            @event("chataction")
            async def on_join(self, event):
                await event.reply("Welcome!")

            async def on_load(self):
                self.log.info("Loaded")

            async def on_unload(self):
                self.log.info("Unloaded")
    """

    name: str = "Unnamed"
    version: str = "1.0.0"
    author: str = "unknown"
    description: dict = {}
    dependencies: list = []
    banner_url: str | None = None

    strings: dict = {}

    config: Any = None

    _cmd_registry: list = []
    _inline_registry: list = []
    _callback_registry: list = []
    _watcher_registry: list = []
    _loop_registry: list = []
    _event_registry: list = []
    _method_registry: list = []
    _on_install_registry: list = []
    _uninstall_registry: list = []
    _bot_cmd_registry: list = []
    _owner_registry: list = []
    _permission_registry: list = []
    _error_handler_registry: list = []

    def __getattribute__(self, name: str) -> Any:
        if name == "config":
            try:
                return object.__getattribute__(self, "_get_config")()
            except AttributeError:
                pass
        if name == "strings":
            try:
                return object.__getattribute__(self, "_get_strings")()
            except AttributeError:
                pass
        return object.__getattribute__(self, name)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._cmd_registry = []
        cls._inline_registry = []
        cls._callback_registry = []
        cls._watcher_registry = []
        cls._loop_registry = []
        cls._event_registry = []
        cls._method_registry = []
        cls._on_install_registry = []
        cls._uninstall_registry = []
        cls._bot_cmd_registry = []
        cls._owner_registry = []
        cls._permission_registry = []
        cls._error_handler_registry = []

        for name_attr, attr in cls.__dict__.items():
            if not callable(attr):
                continue
            if hasattr(attr, "_mcub_commands"):
                for pattern, kwargs_cmd in attr._mcub_commands:
                    cls._cmd_registry.append((pattern, attr, kwargs_cmd))
            if hasattr(attr, "_mcub_inline"):
                for pattern in attr._mcub_inline:
                    cls._inline_registry.append((pattern, attr))
            if hasattr(attr, "_mcub_callbacks"):
                for cb_info in attr._mcub_callbacks:
                    cls._callback_registry.append((attr, cb_info["ttl"]))
            if hasattr(attr, "_mcub_watchers"):
                for watcher_info in attr._mcub_watchers:
                    cls._watcher_registry.append(
                        (attr, watcher_info["bot_client"], watcher_info["tags"])
                    )
            if hasattr(attr, "_mcub_loops"):
                for loop_info in attr._mcub_loops:
                    cls._loop_registry.append(
                        (
                            attr,
                            loop_info["interval"],
                            loop_info["autostart"],
                            loop_info["wait_before"],
                        )
                    )
            if hasattr(attr, "_mcub_events"):
                for event_info in attr._mcub_events:
                    cls._event_registry.append(
                        (
                            attr,
                            event_info["event_type"],
                            event_info["args"],
                            event_info["bot_client"],
                            event_info["kwargs"],
                        )
                    )
            if hasattr(attr, "_mcub_methods"):
                cls._method_registry.append(attr)
            if hasattr(attr, "_mcub_on_install"):
                cls._on_install_registry.append(attr)
            if hasattr(attr, "_mcub_uninstall"):
                cls._uninstall_registry.append(attr)
            if hasattr(attr, "_mcub_bot_commands"):
                for cmd_info in attr._mcub_bot_commands:
                    cls._bot_cmd_registry.append((attr, cmd_info))
            if hasattr(attr, "_mcub_owner"):
                for owner_info in attr._mcub_owner:
                    cls._owner_registry.append((attr, owner_info))
            if hasattr(attr, "_mcub_permissions"):
                for permission_info in attr._mcub_permissions:
                    cls._permission_registry.append((attr, permission_info))
            if hasattr(attr, "_mcub_error_handler"):
                for handler_info in attr._mcub_error_handler:
                    cls._error_handler_registry.append((attr, handler_info))

    def __init__(self, kernel: Any, client: Any, register: Any) -> None:
        self.kernel = kernel
        self.client = client
        self._register = register

        self.log = kernel.logger
        self.db = kernel.db_manager
        self.cache = kernel.cache

        self._loaded = False
        self._loops = []
        self._watchers = []
        self._uninstall_funcs = []
        self._on_install_funcs = []
        self._method_funcs = []

        self._config = None
        self.name = type(self).name
        self.log = _ModuleLoggerAdapter(kernel.logger, {"module_name": self.name})

        module_class = type(self)
        for klass in module_class.__mro__:
            if "config" in klass.__dict__:
                val = klass.__dict__["config"]
                if not isinstance(val, property):
                    self._config = val
                    break

        self._strings = None
        module_class = type(self)
        strings_dict = None
        for klass in module_class.__mro__:
            if "strings" in klass.__dict__:
                val = klass.__dict__["strings"]
                if not isinstance(val, property):
                    strings_dict = val
                    break
        if strings_dict and len(strings_dict) > 0:
            try:
                kernel.logger.debug(
                    f"[strings] Found strings_dict keys: {list(strings_dict.keys())}"
                )
                from utils.strings import Strings

                if all(isinstance(v, dict) for v in strings_dict.values()):
                    problems = Strings.validate(strings_dict)
                    for problem in problems:
                        self.log.warning(f"strings validation: {problem}")

                self._strings = Strings(
                    self.kernel,
                    copy.deepcopy(strings_dict),
                )
                kernel.logger.debug(
                    f"[strings] Init OK for {self.name}: locale={self._strings.locale}, keys={list(self._strings.keys())}"
                )
            except Exception as e:
                import traceback

                kernel.logger.error(
                    f"[strings] FAIL to init {self.name}: {e}\n{traceback.format_exc()}"
                )
                self._strings = None
        else:
            kernel.logger.debug(
                f"[strings] NO strings_dict for {self.name} MRO={[k.__name__ for k in module_class.__mro__]}"
            )
            self._strings = None

        owner_map = {}
        for func, owner_info in type(self)._owner_registry:
            owner_map[func.__name__] = owner_info

        permission_map: dict[str, dict[str, Any]] = {}
        for func, permission_info in type(self)._permission_registry:
            permission_map.setdefault(func.__name__, {}).update(permission_info)

        error_handler_map: dict[str, dict[str, Any]] = {}
        for func, handler_info in type(self)._error_handler_registry:
            error_handler_map[func.__name__] = handler_info

        for pattern, func, kwargs_cmd in type(self)._cmd_registry:
            method_name = func.__name__

            async def wrapper(
                event: Any,
                f=func,
                instance=self,
                permission_tags=permission_map.get(method_name),
                error_handler=error_handler_map.get(method_name),
            ) -> None:
                if permission_tags and not instance._passes_permission_tags(
                    event, permission_tags
                ):
                    return
                if error_handler:
                    return await instance._run_with_error_handler(
                        f, instance, event, error_handler
                    )
                return await f(instance, event)

            wrapper.__original__ = func

            if method_name in owner_map:
                only_admin = owner_map[method_name].get("only_admin", False)

                async def owner_wrapper(
                    event: Any, f=wrapper, only_admin=only_admin
                ) -> None:
                    admin_id = getattr(self.kernel, "ADMIN_ID", None)
                    sender_id = getattr(event, "sender_id", None)
                    if admin_id is None or sender_id is None:
                        return

                    is_admin = int(sender_id) == int(admin_id)
                    if only_admin:
                        if not is_admin:
                            return
                    else:
                        no_owner_method = getattr(event, "no_owner", None)
                        if no_owner_method is not None and no_owner_method():
                            return
                        if not is_admin:
                            return

                    return await f(event)

                owner_wrapper.__original__ = func
                self._register.command(pattern, **kwargs_cmd)(owner_wrapper)
            else:
                self._register.command(pattern, **kwargs_cmd)(wrapper)

        for pattern, func in type(self)._inline_registry:

            async def inline_wrapper(event: Any, f=func) -> None:
                return await f(self, event)

            inline_wrapper.__original__ = func
            self.kernel.register_inline_handler(pattern, inline_wrapper)

        for func, ttl in type(self)._callback_registry:
            self._register_callback(func, ttl)

        for func, interval, autostart, wait_before in type(self)._loop_registry:
            self._register_loop(func, interval, autostart, wait_before)

        for func, bot_client, tags in type(self)._watcher_registry:
            self._register_watcher(
                func,
                bot_client,
                permission_tags=permission_map.get(func.__name__),
                **tags,
            )

        for func, event_type, args, bot_client, kwargs in type(self)._event_registry:
            self._register_event(
                func,
                event_type,
                *args,
                bot_client=bot_client,
                permission_tags=permission_map.get(func.__name__),
                **kwargs,
            )

        for func in type(self)._method_registry:
            self._method_funcs.append(func)

        for func in type(self)._on_install_registry:
            self._on_install_funcs.append(func)

        for func in type(self)._uninstall_registry:
            self._uninstall_funcs.append(func)

        for func, cmd_info in type(self)._bot_cmd_registry:
            kwargs_cmd = {
                "alias": cmd_info.get("alias"),
                "doc": cmd_info.get("doc"),
                "doc_ru": cmd_info.get("doc_ru"),
                "doc_en": cmd_info.get("doc_en"),
            }
            kwargs_cmd = {k: v for k, v in kwargs_cmd.items() if v is not None}

            async def wrapper(
                event: Any,
                f=func,
                permission_tags=permission_map.get(func.__name__),
            ) -> None:
                if permission_tags and not self._passes_permission_tags(
                    event, permission_tags
                ):
                    return
                return await f(self, event)

            wrapper.__original__ = func
            self._register.bot_command(cmd_info["pattern"], **kwargs_cmd)(wrapper)

    def _register_event(
        self,
        func: Callable,
        event_type: str,
        *args: Any,
        bot_client: bool = False,
        permission_tags: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Register a custom event handler via register.py."""
        user_module = self._get_user_module()
        if user_module and not hasattr(user_module, "register"):
            user_module.register = type("RegisterObject", (), {})()

        async def bound_wrapper(event: Any) -> None:
            if permission_tags and not self._passes_permission_tags(
                event, permission_tags
            ):
                return
            return await func(self, event)

        bound_wrapper.__original__ = func
        bound_wrapper.__bound_instance__ = self

        self._register.event(
            event_type, *args, bot_client=bot_client, module=user_module, **kwargs
        )(bound_wrapper)

    def _register_loop(
        self, func: Callable, interval: int, autostart: bool, wait_before: bool
    ) -> Any:
        """Register a background loop via register.py."""
        user_module = self._get_user_module()
        if user_module and not hasattr(user_module, "register"):
            user_module.register = type("RegisterObject", (), {})()

        async def bound_wrapper() -> None:
            return await func(self)

        bound_wrapper.__original__ = func
        bound_wrapper.__bound_instance__ = self

        loop = self._register.loop(
            interval, autostart, wait_before, module=user_module
        )(bound_wrapper)
        self._loops.append(loop)
        setattr(self, func.__name__, loop)
        return loop

    def _register_watcher(
        self,
        func: Callable,
        bot_client: bool = False,
        permission_tags: dict[str, Any] | None = None,
        **tags: Any,
    ) -> None:
        """Register a message watcher via register.py."""
        user_module = self._get_user_module()
        if user_module and not hasattr(user_module, "register"):
            user_module.register = type("RegisterObject", (), {})()

        async def bound_wrapper(event: Any) -> None:
            if permission_tags and not self._passes_permission_tags(
                event, permission_tags
            ):
                return
            return await func(self, event)

        bound_wrapper.__original__ = func
        bound_wrapper.__bound_instance__ = self
        self._watchers.append(bound_wrapper)

        self._register.watcher(
            bound_wrapper, bot_client=bot_client, module=user_module, **tags
        )

    def _get_user_module(self) -> Any:
        """Get the user's module that contains this class."""
        import sys

        return sys.modules.get(type(self).__module__)

    def _passes_permission_tags(self, event: Any, tags: dict[str, Any]) -> bool:
        from core.lib.loader.register import _watcher_passes_filters

        try:
            return _watcher_passes_filters(event, tags)
        except Exception as e:
            self.log.warning(f"permission filter failed for {tags}: {e}")
            return False

    async def _run_with_error_handler(
        self,
        func: Callable,
        instance: Any,
        event: Any,
        handler_config: dict[str, Any],
    ) -> None:
        """Run a function with error handling based on decorator config."""
        try:
            return await func(instance, event)
        except Exception as e:
            log_level = handler_config.get("log_level", "error")
            reraise = handler_config.get("reraise", False)
            message_template = handler_config.get("message")

            log_msg = (
                message_template.format(
                    exc=str(e),
                    func=func.__name__,
                    module=self.name,
                )
                if message_template
                else f"Error in {func.__name__}: {e}"
            )

            log_func = getattr(self.log, log_level, self.log.error)
            log_func(log_msg)

            if reraise:
                raise

    def get_prefix(self) -> str:
        return getattr(self.kernel, "custom_prefix", ".")

    def get_lang(self) -> str:
        config = getattr(self.kernel, "config", {})
        getter = getattr(config, "get", None)
        if callable(getter):
            return getter("language", "ru") or "ru"
        return "ru"

    def args(self, event: Any) -> Any:
        import utils

        text = getattr(event, "text", None) or getattr(event, "raw_text", "") or ""
        return utils.parse_arguments(text, prefix=self.get_prefix())

    def args_raw(self, event: Any) -> str:
        import utils

        return utils.get_args_raw(event)

    def args_html(self, event: Any) -> str:
        import utils

        return utils.get_args_html(event)

    async def answer(self, event: Any, text: str, **kwargs: Any) -> Any:
        import utils

        return await utils.answer(event, text, **kwargs)

    async def edit(self, event: Any, text: str, **kwargs: Any) -> Any:
        reply_markup = kwargs.pop("reply_markup", None)
        as_html = kwargs.pop("as_html", False)
        if reply_markup is not None:
            kwargs["buttons"] = reply_markup
        if hasattr(event, "edit") and callable(event.edit):
            if as_html:
                return await event.edit(text, parse_mode="html", **kwargs)
            return await event.edit(text, **kwargs)
        return await self.answer(
            event, text, reply_markup=reply_markup, as_html=as_html, **kwargs
        )

    async def reply(self, event: Any, text: str, **kwargs: Any) -> Any:
        reply_markup = kwargs.pop("reply_markup", None)
        as_html = kwargs.pop("as_html", False)
        if reply_markup is not None:
            kwargs["buttons"] = reply_markup
        if as_html and hasattr(self.kernel, "reply_with_html"):
            return await self.kernel.reply_with_html(event, text, **kwargs)
        if hasattr(event, "reply") and callable(event.reply):
            if as_html:
                kwargs["parse_mode"] = "html"
            return await event.reply(text, **kwargs)
        return await self.answer(
            event, text, reply_markup=reply_markup, as_html=as_html, **kwargs
        )

    async def inline(
        self,
        chat_id: int | Any,
        title: str,
        fields: list[dict[str, Any]] | None = None,
        buttons: list[Any] | None = None,
        auto_send: bool = True,
        ttl: int = 200,
        **kwargs,
    ) -> Any:
        """Send an inline form message.

        Args:
            chat_id: Target chat ID
            title: Form title text
            fields: Optional form fields (list of {"key": "...", "value": "..."})
            buttons: Button layout
            auto_send: If True, send immediately; if False, return form for editing
            ttl: Time-to-live for callback buttons
            **kwargs: Additional args passed to kernel.inline_form

        Returns:
            Inline form result or message

        Example:
            await self.inline(event.chat_id, "Menu", buttons=[[btn]])
        """
        return await self.kernel.inline_form(
            chat_id,
            title,
            fields=fields,
            buttons=buttons,
            auto_send=auto_send,
            ttl=ttl,
            **kwargs,
        )

    def lookup_module(self, module_name: str) -> Any:
        needle = str(module_name).lower()

        class_instances = getattr(self.kernel, "_class_module_instances", {}) or {}
        for name, instance in class_instances.items():
            if (
                str(name).lower() == needle
                or str(getattr(instance, "name", "")).lower() == needle
            ):
                return instance

        for collection_name in ("loaded_modules", "system_modules"):
            collection = getattr(self.kernel, collection_name, {}) or {}
            for name, module in collection.items():
                instance = getattr(module, "_class_instance", None)
                target = instance or module
                names = {
                    str(name).lower(),
                    str(getattr(target, "name", "")).lower(),
                    str(getattr(module, "__name__", "")).lower(),
                }
                if needle in names:
                    return target

        compat_allmodules = getattr(self.kernel, "_hikka_compat_allmodules_proxy", None)
        if compat_allmodules is not None and hasattr(compat_allmodules, "lookup"):
            return compat_allmodules.lookup(module_name)

        return None

    def require_module(self, module_name: str) -> Any:
        module = self.lookup_module(module_name)
        if module is None:
            raise LookupError(f"Required module '{module_name}' is not loaded")
        return module

    def _cleanup_callback_tokens(self) -> None:
        tokens = getattr(self, "_callback_tokens", None) or []
        cb_map = getattr(self.kernel, "inline_callback_map", None)
        lock = getattr(self.kernel, "_inline_cb_lock", None)
        if not tokens or cb_map is None or lock is None:
            return

        with lock:
            for tok in tokens:
                cb_map.pop(tok, None)
        self._callback_tokens = []

    def _register_callback(self, func: Callable, ttl: int) -> None:
        """Register a callback handler with auto-generated uuid."""
        if not hasattr(self.kernel, "inline_callback_map"):
            import threading

            self.kernel._inline_cb_lock = threading.Lock()
            self.kernel.inline_callback_map = {}

        raw_func = getattr(func, "__original__", func)
        instance = self

        async def wrapper(event: Any, *args: Any, **kwargs: Any) -> None:
            return await raw_func(instance, event)

        wrapper.__original__ = func
        wrapper._ttl = ttl
        wrapper._is_class_callback = True
        wrapper._bound_instance = self

        tok = uuid.uuid4().hex
        import threading
        import time

        lock = getattr(self.kernel, "_inline_cb_lock")
        cb_map = self.kernel.inline_callback_map

        with lock:
            now = time.time()
            expired = [
                k
                for k, v in list(cb_map.items())
                if v.get("expires_at") and v["expires_at"] < now
            ]
            for k in expired:
                cb_map.pop(k, None)

            cb_map[tok] = {
                "handler": wrapper,
                "args": [],
                "kwargs": {},
                "expires_at": now + ttl if ttl else None,
            }

        self._callback_tokens = getattr(self, "_callback_tokens", [])
        self._callback_tokens.append(tok)

    class ButtonFactory:
        """Button factory for creating various button types.

        Usage::

            class MyModule(ModuleBase):
                @command("test")
                async def cmd_test(self, event):
                    await event.edit("Test", buttons=[
                        self.Button.inline("Click", self.handle_click),
                        self.Button.url("Link", "https://example.com"),
                        self.Button.text("Text"),
                        self.Button.switch("Search", "query"),
                        self.Button.url("New Tab", "https://example.com", new_tab=True),
                    ])

                async def handle_click(self, event):
                    await event.answer("Clicked!")
        """

        def __init__(self, outer: Any) -> None:
            self._outer = outer
            self._telethon_button = __import__("telethon", fromlist=["Button"]).Button

        def inline(
            self,
            text: str,
            callback_func: Callable,
            *,
            ttl: int = 900,
            allow_user: int | list[int] | str | None = None,
            allow_ttl: int = 100,
            args: tuple = (),
            kwargs: dict | None = None,
            data: dict | None = None,
            pass_event: bool = True,
            auto_answer: bool | None = None,
            icon: int | None = None,
            style: Any = None,
            **btn_kwargs,
        ) -> Any:
            """Create an inline/callback button."""
            btn = self._outer._make_callback_button(
                text,
                callback_func,
                ttl=ttl,
                allow_user=allow_user,
                allow_ttl=allow_ttl,
                args=args,
                kwargs=kwargs,
                data=data,
                pass_event=pass_event,
                auto_answer=auto_answer,
                style=style,
                icon=icon,
            )
            return btn

        def url(
            self,
            text: str,
            url: str,
            *,
            icon: int | None = None,
            style: Any = None,
        ) -> Any:
            """Create a URL button."""
            return self._telethon_button.url(text, url, style=style, icon=icon)

        def text(
            self,
            text: str,
            *,
            resize: bool = True,
            selective: bool = False,
            icon: int | None = None,
            style: Any = None,
        ) -> Any:
            """Create a text button."""
            return self._telethon_button.text(
                text, resize=resize, selective=selective, style=style, icon=icon
            )

        def switch(
            self,
            text: str,
            query: str = "",
            *,
            same_peer: bool = True,
            icon: int | None = None,
            style: Any = None,
        ) -> Any:
            """Create a switch button."""
            return self._telethon_button.switch(
                text, query, same_peer=same_peer, style=style, icon=icon
            )

        def copy(
            self,
            text: str = "Copy",
            *,
            payload: bytes | None = None,
            icon: int | None = None,
            style: Any = None,
        ) -> Any:
            """Create a copy button."""
            return self._telethon_button.copy(
                text, payload=payload, style=style, icon=icon
            )

        def request_phone(
            self,
            text: str = "Share Phone",
            *,
            request_title: str | None = None,
            icon: int | None = None,
            style: Any = None,
        ) -> Any:
            """Create a request phone button."""
            return self._telethon_button.request_phone(
                text, request_title=request_title, style=style, icon=icon
            )

        def request_location(
            self,
            text: str = "Share Location",
            *,
            request_title: str | None = None,
            live_period: int | None = None,
            icon: int | None = None,
            style: Any = None,
        ) -> Any:
            """Create a request location button."""
            return self._telethon_button.request_location(
                text,
                request_title=request_title,
                live_period=live_period,
                style=style,
                icon=icon,
            )

        def request_poll(
            self,
            text: str = "Create Poll",
            *,
            request_title: str | None = None,
            quiz: bool = False,
            icon: int | None = None,
            style: Any = None,
        ) -> Any:
            """Create a request poll button."""
            return self._telethon_button.request_poll(
                text, request_title=request_title, quiz=quiz, style=style, icon=icon
            )

        def game(
            self,
            text: str,
            *,
            game: Any = None,
            icon: int | None = None,
            style: Any = None,
        ) -> Any:
            """Create a game button."""
            return (
                self._telethon_button.game(text, game=game, style=style, icon=icon)
                if game
                else self._telethon_button.game(text, style=style, icon=icon)
            )

        def unknown(
            self,
            data: bytes,
            text: str = "Button",
            *,
            icon: int | None = None,
            style: Any = None,
        ) -> Any:
            """Create an unknown/custom button."""
            return self._telethon_button.unknown(text, data, style=style, icon=icon)

        def mention(
            self,
            text: str,
            user: int | str | None = None,
            *,
            icon: int | None = None,
            style: Any = None,
        ) -> Any:
            """Create a mention button."""
            return self._telethon_button.mention(
                text, user=user, style=style, icon=icon
            )

        def with_icon(self, btn: Any, icon: int) -> Any:
            """Add icon to an existing button - DEPRECATED: use icon parameter directly."""
            return btn

        def style(self, btn: Any, style: Any) -> Any:
            """Apply style to an existing button - DEPRECATED: use style parameter directly."""
            return btn

    @property
    def Button(self) -> "ModuleBase.ButtonFactory":
        """Access button factory for creating various button types."""
        if not hasattr(self, "_button_factory"):
            button_class = getattr(type(self), "ButtonFactory", None)
            if isinstance(button_class, type) and issubclass(
                button_class, ModuleBase.ButtonFactory
            ):
                self._button_factory = button_class(self)
            else:
                self._button_factory = ModuleBase.ButtonFactory(self)
        return self._button_factory

    def callback_button(
        self,
        text: str,
        callback_func: Callable,
        *,
        ttl: int = 900,
        args: tuple = (),
        kwargs: dict | None = None,
        data: dict | None = None,
        pass_event: bool = True,
        auto_answer: bool | None = None,
        **button_kwargs,
    ) -> Any:
        """Create a callback button with auto-generated token."""
        return self._make_callback_button(
            text,
            callback_func,
            ttl=ttl,
            args=args,
            kwargs=kwargs,
            data=data,
            pass_event=pass_event,
            auto_answer=auto_answer,
            **button_kwargs,
        )

    def _make_callback_button(
        self,
        text: str,
        callback_func: Callable,
        *,
        ttl: int = 900,
        allow_user: int | list[int] | str | None = None,
        allow_ttl: int = 100,
        args: tuple = (),
        kwargs: dict | None = None,
        data: dict | None = None,
        pass_event: bool = True,
        auto_answer: bool | None = None,
        style: Any = None,
        icon: int | None = None,
        **button_kwargs,
    ) -> Any:
        """Internal method to create callback button."""
        from telethon import Button
        import threading
        import time

        if not hasattr(self.kernel, "inline_callback_map"):
            self.kernel._inline_cb_lock = threading.Lock()
            self.kernel.inline_callback_map = {}

        if not hasattr(self.kernel, "callback_permissions"):
            from core.lib.base.permissions import CallbackPermissionManager

            self.kernel.callback_permissions = CallbackPermissionManager()

        raw_func = getattr(callback_func, "__original__", callback_func)
        instance = self
        _kwargs = kwargs or {}
        _data = data or {}
        is_bound_method = (
            inspect.ismethod(raw_func)
            and getattr(raw_func, "__self__", None) is not None
        )
        accepts_var_kw = False
        accepts_data_kw = False
        try:
            sig = inspect.signature(raw_func)
            accepts_var_kw = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            )
            accepts_data_kw = "data" in sig.parameters
        except (TypeError, ValueError):
            pass

        tok = uuid.uuid4().hex

        lock = getattr(self.kernel, "_inline_cb_lock")
        cb_map = self.kernel.inline_callback_map

        with lock:
            now = time.time()
            expired = [
                k
                for k, v in list(cb_map.items())
                if v.get("expires_at") and v["expires_at"] < now
            ]
            for k in expired:
                cb_map.pop(k, None)

        async def wrapper(event: Any, *a: Any, **kw: Any) -> None:
            call_kwargs = dict(kw)
            if accepts_data_kw and "data" not in call_kwargs:
                call_kwargs["data"] = _data or None
            elif _data and accepts_var_kw and "data" not in call_kwargs:
                call_kwargs["data"] = _data
            if pass_event:
                if is_bound_method:
                    result = raw_func(event, *a, **call_kwargs)
                else:
                    result = raw_func(instance, event, *a, **call_kwargs)
            else:
                if is_bound_method:
                    result = raw_func(*a, **call_kwargs)
                else:
                    result = raw_func(instance, *a, **call_kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            if auto_answer is not None:
                await event.answer(auto_answer)

        with lock:
            cb_map[tok] = {
                "handler": wrapper,
                "args": args,
                "kwargs": _kwargs,
                "data": _data,
                "expires_at": now + ttl if ttl else None,
                "auto_answer": auto_answer,
                "allow_user": allow_user,
            }

        if allow_user is not None:
            if allow_user == "all":
                cb_map[tok]["allow_all"] = True
            elif isinstance(allow_user, int):
                self.kernel.callback_permissions.allow(allow_user, tok, allow_ttl)
            elif isinstance(allow_user, list):
                for uid in allow_user:
                    self.kernel.callback_permissions.allow(uid, tok, allow_ttl)

        self._callback_tokens = getattr(self, "_callback_tokens", [])
        self._callback_tokens.append(tok)

        return Button.inline(
            text, tok.encode(), style=style, icon=icon, **button_kwargs
        )

    async def on_load(self) -> None:
        """Called after the module is fully loaded.

        NOTE: If you use @method decorator, those methods are called automatically
        during module load. Override on_load() for additional initialization.
        """
        if self._config is not None:
            try:
                get_config = getattr(self.kernel, "get_module_config", None)
                if get_config:
                    saved = await get_config(self.name)
                    if saved:
                        self._config.from_dict(saved)
                if not hasattr(self.kernel, "_live_module_configs"):
                    self.kernel._live_module_configs = {}
                self.kernel._live_module_configs[self.name] = self._config
            except Exception as e:
                self.log.warning(f"Failed to load config for {self.name}: {e}")

        for func in self._method_funcs:
            try:
                result = func(self)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                self.log.error(
                    f"@method error in {type(self).__name__}.{func.__name__}: {e}"
                )

    async def on_install(self) -> None:
        """Called only on first install (not on reload).

        Override this method for one-time setup, or use @on_install decorator.
        """
        for func in self._on_install_funcs:
            try:
                result = func(self)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                self.log.error(
                    f"@on_install error in {type(self).__name__}.{func.__name__}: {e}"
                )

    async def on_reload(self) -> None:
        """Called after the module is reloaded via the loader reload flow."""

    async def on_config_update(self, key: str, old_value: Any, new_value: Any) -> None:
        """Called when kernel config is updated.

        Override to handle config changes at runtime.

        Args:
            key: Config key that changed
            old_value: Previous value
            new_value: New value
        """
        pass

    async def on_language_change(self, new_lang: str) -> None:
        """Called when the bot language changes.

        Override to handle language switch at runtime.

        Args:
            new_lang: New language code (e.g., "ru", "en")
        """
        pass

    async def on_unload(self) -> None:
        """Called before the module is unloaded.

        NOTE: If you use @uninstall decorator, those methods are called automatically.
        Override on_unload() for additional cleanup.
        """
        for func in self._uninstall_funcs:
            try:
                result = func(self)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                self.log.error(
                    f"@uninstall error in {type(self).__name__}.{func.__name__}: {e}"
                )

    @property
    def config(self) -> Any:
        """Expose config object to module methods."""
        return self._get_config()

    def _get_config(self) -> Any:
        return self._config

    @property
    def strings(self) -> Any:
        """Expose strings object to module methods."""
        return self._get_strings()

    def _get_strings(self) -> Any:
        from utils.strings import Strings

        if isinstance(self._strings, dict):
            strings_dict = copy.deepcopy(self._strings)

            flat_keys = {k for k, v in strings_dict.items() if isinstance(v, str)}
            if flat_keys:
                self.log.debug(
                    f"[strings] Flat mode detected for {self.name}, expanding to all locales"
                )
                expanded = {}
                for lang in ("ru", "en", "uk", "de", "es", "fr", "it", "pt"):
                    expanded[lang] = {k: v for k, v in strings_dict.items()}
                strings_dict = expanded

            self._strings = Strings(self.kernel, strings_dict)
        if self._strings is None:
            self.kernel.logger.error(
                f"[FATAL] {self.name}.strings is None! "
                f"type(self).__name__={type(self).__name__}, "
                f"class has strings={'strings' in type(self).__dict__}"
            )
            raise AttributeError(
                f"strings is not initialized for {self.name}. "
                "Make sure the module defines 'strings' as a class dict attribute."
            )
        self.kernel.logger.debug(
            f"[strings] Access {self.name}.strings: type={type(self._strings).__name__} loc={getattr(self._strings, 'locale', 'N/A')}"
        )
        return self._strings

    async def save_config(self) -> None:
        """Save config to database when it changes."""
        if self._config is not None:
            try:
                save_config = getattr(self.kernel, "save_module_config", None)
                if save_config:
                    await save_config(self.name, self._config.to_dict())
                if hasattr(self.kernel, "_live_module_configs"):
                    self.kernel._live_module_configs[self.name] = self._config
            except Exception as e:
                self.log.warning(f"Failed to save config for {self.name}: {e}")

    async def import_lib(self, url: str, *, name: str | None = None) -> Any:
        """
        Download and import external library from URL.

        Downloads Python code from URL and imports it as a module.
        Useful for importing shared libraries like xlib.

        Args:
            url: URL to download the library from.
            name: Optional module name (defaults to last path component).

        Returns:
            Imported module.

        Examples:
            self.xlib = await self.import_lib("https://raw.githubusercontent.com/...")
            text = self.xlib.format_size(1024)
        """
        import sys
        import types
        import urllib.request

        if name is None:
            name = url.split("/")[-1]
            if name.endswith(".py"):
                name = name[:-3]
            elif not name:
                name = "xlib"

        try:
            with urllib.request.urlopen(url) as response:
                code = response.read().decode("utf-8")

            module = types.ModuleType(name)
            sys.modules[name] = module

            exec(code, module.__dict__)
            self.log.info(f"Imported library: {name} from {url}")
            return module

        except Exception as e:
            self.log.error(f"Failed to import lib {name}: {e}")
            raise
