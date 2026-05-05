# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin00

import asyncio
import inspect
from collections.abc import Callable
from typing import Any


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
                {"alias": alias, "doc": doc, "doc_ru": doc_ru, "doc_en": doc_en},
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


def inline_temp(
    func: Callable | None = None,
    *,
    ttl: int = 300,
    allow_user: int | list[int] | str | None = None,
    allow_ttl: int = 100,
    article: Callable | None = None,
    data: Any | None = None,
) -> Callable:
    """
    Class-level decorator for registering temporary inline command handlers.

    When a user enters @bot <uuid> <args>, the article is shown. When they
    send it, the handler is called with (event, args, data).

    Usage::

        from core.lib.loader.module_base import ModuleBase, inline_temp

        class MyModule(ModuleBase):
            @inline_temp(ttl=600)
            async def handle_search(self, event, args, data=None):
                await event.answer(f"Search: {args}")

            @inline_temp(ttl=300, article=lambda e: e.builder.article("Search", text="..."))
            async def handle_search_custom(self, event, args):
                ...
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_inline_temp"):
            f._mcub_inline_temp = []
        f._mcub_inline_temp.append(
            {
                "ttl": ttl,
                "allow_user": allow_user,
                "allow_ttl": allow_ttl,
                "article": article,
                "data": data,
            }
        )
        return f

    if func is not None:
        return decorator(func)
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


def on_uninstall(func: Callable | None = None) -> Callable:
    """
    Class-level decorator for uninstall callback.

    Called when the module is permanently uninstalled (um command).

    Usage::

        from core.lib.loader.module_base import ModuleBase, on_uninstall

        class MyModule(ModuleBase):
            @on_uninstall
            async def cleanup(self):
                await self.client.send_message("me", "Module removed!")
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
    Class-level decorator for registering bot commands.

    Usage::

        from core.lib.loader.module_base import ModuleBase, bot_command

        class MyModule(ModuleBase):
            @bot_command("start", doc_ru="старт", doc_en="start")
            async def cmd_start(self, event):
                await event.answer("Hello from bot!")
    """

    def decorator(func: Callable) -> Callable:
        if not hasattr(func, "_mcub_bot_commands"):
            func._mcub_bot_commands = []
        func._mcub_bot_commands.append(
            (
                pattern,
                {"alias": alias, "doc": doc, "doc_ru": doc_ru, "doc_en": doc_en},
            )
        )
        return func

    return decorator


def owner_only(func: Callable | None = None, *, only_admin: bool = False) -> Callable:
    """
    Class-level decorator to restrict command to owner/admins.

    Usage::

        from core.lib.loader.module_base import ModuleBase, command, owner_only

        class MyModule(ModuleBase):
            @owner_only(only_admin=True)
            @command("admin")
            async def cmd_admin(self, event):
                await event.edit("Admin only!")
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_owner"):
            f._mcub_owner = []
        f._mcub_owner.append({"only_admin": only_admin})
        return f

    if func is not None:
        return decorator(func)
    return decorator


def permissions(
    func: Callable | None = None, *, log_level: str = "error", **perms: Any
) -> Callable:
    """
    Class-level decorator for setting command permissions.

    Usage::

        from core.lib.loader.module_base import ModuleBase, command, permissions

        class MyModule(ModuleBase):
            @permissions(log_level="warning", only_pm=True)
            @command("secure")
            async def cmd_secure(self, event):
                await event.edit("Secure command!")
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_permissions"):
            f._mcub_permissions = []
        f._mcub_permissions.append({"log_level": log_level, **perms})
        return f

    if func is not None:
        return decorator(func)
    return decorator


def error_handler(
    func: Callable | None = None,
    *,
    log_level: str = "error",
    reraise: bool = False,
    message: str | None = None,
) -> Callable:
    """
    Class-level decorator for handling errors in command handlers.

    Usage::

        from core.lib.loader.module_base import ModuleBase, command, error_handler

        class MyModule(ModuleBase):
            @error_handler(log_level="warning", message="Something went wrong")
            @command("risky")
            async def cmd_risky(self, event):
                # This might raise an exception
                await some_risky_operation()
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_error_handler"):
            f._mcub_error_handler = []
        f._mcub_error_handler.append(
            {"log_level": log_level, "reraise": reraise, "message": message}
        )
        return f

    if func is not None:
        return decorator(func)
    return decorator
