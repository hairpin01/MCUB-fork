# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""
Register protocol - structural type for ``kernel.register``.

Covers every public method documented in ``doc/registration/``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from core.lib.types.event import Event


class Register(Protocol):
    """Registration API - all public methods documented for module developers."""

    def method(self, func: Callable | None = None) -> Callable: ...
    def event(
        self,
        event_type: str,
        *args: Any,
        bot_client: bool = False,
        module: Any = None,
        **kwargs: Any,
    ) -> Callable: ...
    def command(self, pattern: str, **kwargs: Any) -> Callable: ...
    def bot_command(self, pattern: str, **kwargs: Any) -> Callable: ...
    def watcher(
        self,
        func: Callable | None = None,
        bot_client: bool = False,
        module: Any = None,
        **tags: Any,
    ) -> Callable: ...
    def loop(
        self,
        interval: int = 60,
        autostart: bool = True,
        wait_before: bool = False,
        module: Any = None,
    ) -> Callable: ...

    def on_load(self, func: Callable | None = None) -> Callable: ...
    def on_install(self, func: Callable | None = None) -> Callable: ...
    def uninstall(self, func: Callable | None = None) -> Callable: ...

    def inline_temp(
        self,
        func: Callable,
        ttl: int = 300,
        article: Callable | None = None,
        data: Any | None = None,
        allow_user: Any | None = None,
        allow_ttl: int = 100,
    ) -> str: ...

    def get_commands(self) -> dict[str, Callable]: ...
    def get_command(self, command: str) -> dict[str, Any]: ...
    def get_bot_commands(self) -> dict[str, tuple[str, Callable]]: ...
    def get_watchers(self) -> list[dict[str, Any]]: ...
    def get_events(self) -> list[tuple[Callable, Any, Any]]: ...
    def get_loops(self) -> list[Any]: ...

    def unregister_command(self, cmd: str) -> bool: ...
    def unregister_bot_command(self, cmd: str) -> bool: ...

    async def invoke(
        self,
        command: str,
        args: str | None = None,
        chat_id: int | None = None,
        reply_to: int | None = None,
        *,
        prefix: str | None = None,
        original_event: Event | None = None,
    ) -> Any: ...
