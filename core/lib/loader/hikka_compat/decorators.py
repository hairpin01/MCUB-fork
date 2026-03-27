import asyncio
import contextlib
import copy
from functools import wraps
from typing import Callable, Optional, Union

from .types import StopLoop


def tds(cls):
    cls.__hikka_module__ = True
    return cls


def tag(*tags, **kwarg_tags):
    """
    Tag function (esp. watchers) with some tags.
    Available tags:
        • no_commands - Ignore all userbot commands in watcher
        • only_commands - Capture only userbot commands in watcher
        • out - Capture only outgoing events
        • in - Capture only incoming events
        • only_messages - Capture only messages (not join events)
        • editable - Capture only messages which can be edited
        • no_media - Capture only messages without media
        • only_media - Capture only messages with media
        • only_photos, only_videos, only_audios, only_docs, only_stickers
        • only_inline, only_channels, only_groups, only_pm, only_reply, only_forwards
        • no_pm, no_channels, no_groups, no_inline, no_stickers, no_docs
        • no_audios, no_videos, no_photos, no_forwards, no_reply, no_mention
        • mention, only_reply
        • startswith, endswith, contains, regex, filter
        • from_id, chat_id, thumb_url, alias, aliases
    """

    def inner(func):
        for _tag in tags:
            setattr(func, _tag, True)
        for _tag, value in kwarg_tags.items():
            setattr(func, _tag, value)
        return func

    return inner


def command(*args, **kwargs):
    def decorator(func):
        func.__hikka_command__ = True
        func.is_command = True
        func.__command_kwargs__ = dict(kwargs)
        if "ru_doc" in kwargs:
            func.__doc_ru__ = kwargs["ru_doc"]
        if "en_doc" in kwargs:
            func.__doc__ = func.__doc__ or kwargs["en_doc"]
        if "alias" in kwargs:
            func.alias = kwargs["alias"]
        if "aliases" in kwargs:
            func.aliases = kwargs["aliases"]
        for k, v in kwargs.items():
            try:
                setattr(func, k, v)
            except (AttributeError, TypeError):
                pass
        return func

    if args and callable(args[0]):
        return decorator(args[0])
    return decorator


def inline_handler(*args, **kwargs):
    def decorator(func):
        func.__hikka_inline_handler__ = True
        func.is_inline_handler = True
        func.__inline_handler_kwargs__ = dict(kwargs)
        for k, v in kwargs.items():
            if k.endswith("_doc"):
                setattr(func, k, v)
            else:
                try:
                    setattr(func, k, v)
                except (AttributeError, TypeError):
                    pass
        return func

    if args and callable(args[0]):
        return decorator(args[0])
    return decorator


def callback_handler(*args, **kwargs):
    def decorator(func):
        func.__hikka_callback_handler__ = True
        func.is_callback_handler = True
        func.__callback_handler_kwargs__ = dict(kwargs)
        for k, v in kwargs.items():
            if k.endswith("_doc"):
                setattr(func, k, v)
            else:
                try:
                    setattr(func, k, v)
                except (AttributeError, TypeError):
                    pass
        return func

    if args and callable(args[0]):
        return decorator(args[0])
    return decorator


def watcher(*args, **kwargs):
    positional_tags = []
    if args and not callable(args[0]):
        positional_tags = list(args)
        args = ()

    def decorator(func):
        func.__hikka_watcher__ = True
        func.is_watcher = True
        merged_kwargs = dict(kwargs)
        for tag_name in positional_tags:
            if isinstance(tag_name, str):
                merged_kwargs.setdefault(tag_name, True)
        func.__watcher_tags__ = tuple(t for t in positional_tags if isinstance(t, str))
        func.__watcher_kwargs__ = merged_kwargs
        for k, v in merged_kwargs.items():
            try:
                setattr(func, k, v)
            except (AttributeError, TypeError):
                pass
        return func

    if args and callable(args[0]):
        return decorator(args[0])
    return decorator


def on(event_type):
    def decorator(func):
        func.__hikka_on_event__ = event_type
        return func

    return decorator


def debug_method(*args, **kwargs):
    """Decorator that marks function as IDM (Internal Debug Method)."""

    def decorator(func):
        func.is_debug_method = True
        for k, v in kwargs.items():
            setattr(func, k, v)
        return func

    if args and callable(args[0]):
        return decorator(args[0])
    return decorator


def raw_handler(*updates):
    """Decorator that marks function as raw telethon events handler."""

    def decorator(func):
        func.is_raw_handler = True
        func.__raw_handler__ = True
        func.updates = updates
        return func

    return decorator


class InfiniteLoop:
    """Class for creating infinite loops in modules."""

    _task = None
    status = False
    module_instance = None

    def __init__(
        self,
        func,
        interval: int = 5,
        autostart: bool = False,
        wait_before: bool = False,
        stop_clause: Optional[str] = None,
    ):
        self.func = func
        self.interval = interval
        self._wait_before = wait_before
        self._stop_clause = stop_clause
        self.autostart = autostart

    def _stop(self, *args, **kwargs):
        if hasattr(self, "_wait_for_stop"):
            self._wait_for_stop.set()

    def _create_task(self, coro):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            coro.close()
            return None
        if loop.is_closed():
            coro.close()
            return None
        return loop.create_task(coro)

    def stop(self, *args, **kwargs):
        if self._task:
            self._wait_for_stop = asyncio.Event()
            self.status = False
            self._task.add_done_callback(self._stop)
            self._task.cancel()
            return self._create_task(self._wait_for_stop.wait())
        return self._create_task(self._stop_placeholder())

    async def _stop_placeholder(self):
        return True

    def start(self, *args, **kwargs):
        if not self._task:
            self._task = asyncio.ensure_future(self.actual_loop(*args, **kwargs))

    async def actual_loop(self, *args, **kwargs):
        while not self.module_instance:
            await asyncio.sleep(0.01)

        if isinstance(self._stop_clause, str) and self._stop_clause:
            self.module_instance.set(self._stop_clause, True)

        self.status = True

        while self.status:
            if self._wait_before:
                await asyncio.sleep(self.interval)

            if (
                isinstance(self._stop_clause, str)
                and self._stop_clause
                and not self.module_instance.get(self._stop_clause, False)
            ):
                break

            try:
                await self.func(self.module_instance, *args, **kwargs)
            except StopLoop:
                break
            except Exception:
                pass

            if not self._wait_before:
                await asyncio.sleep(self.interval)

        if hasattr(self, "_wait_for_stop"):
            self._wait_for_stop.set()
        self.status = False

    def __del__(self):
        with contextlib.suppress(Exception):
            self.stop()


def loop(
    interval: int = 5,
    autostart: bool = False,
    wait_before: bool = False,
    stop_clause: Optional[str] = None,
):
    """
    Create new infinite loop from class method.
    :param interval: Loop iterations delay
    :param autostart: Start loop once module is loaded
    :param wait_before: Insert delay before actual iteration, rather than after
    :param stop_clause: Database key, based on which the loop will run
    """

    def wrapped(func):
        return InfiniteLoop(func, interval, autostart, wait_before, stop_clause)

    return wrapped


class Placeholder:
    """Placeholder class."""

    pass


async def stop_placeholder() -> bool:
    """Stop placeholder function."""
    return True
