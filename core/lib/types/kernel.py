# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""
Kernel protocol — structural type for the MCUB kernel.

The production ``Kernel`` class (``core.kernel.standard``) composes four
mixins (core, handlers, pipeline, lifecycle).  User modules receive a
``ModuleKernelProxy`` that delegates most ``__getattr__`` lookups to the
real kernel while blocking dangerous attributes.

This protocol describes only what modules can **actually** access through
the proxy — the public, non-protected surface of the real kernel.

Usage::

    from core.lib.types import Kernel

    async def setup(k: Kernel) -> None:
        k.logger.info("kernel v%s", k.VERSION)
        cfg = await k.get_module_config("my_mod")
"""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from core.lib.types.client import Client
    from core.lib.types.event import Event
    from core.lib.types.register import Register


class Kernel(Protocol):
    """MCUB kernel — only the API actually visible to user modules.

    Blocked by ModuleKernelProxy (registries, dangerous methods) or absent
    from the real kernel are NOT included here.
    """

    VERSION: str
    CORE_NAME: str  # set by core/__main__.py after kernel init
    logger: logging.Logger
    custom_prefix: str

    MODULES_DIR: str
    MODULES_LOADED_DIR: str
    CONFIG_FILE: str

    client: Client
    bot_client: Client | None

    @property
    def inline_manager(self) -> Any: ...

    config: dict[str, Any]
    cache: Any

    @property
    def module_name(self) -> str: ...

    @property
    def register(self) -> Register: ...

    @property
    def loaded_modules_view(self) -> MappingProxyType: ...

    @property
    def system_modules_view(self) -> MappingProxyType: ...

    @property
    def loaded_module_names(self) -> tuple[str, ...]: ...

    def lookup_module(self, module_name: str, *, all_loaded: bool = False) -> Any: ...
    def get_loaded_module(
        self, module_name: str, *, all_loaded: bool = False
    ) -> Any: ...
    def iter_loaded_module_names(self) -> tuple[str, ...]: ...

    async def shutdown(self) -> None: ...
    async def restart(
        self, chat_id: int | None = None, message_id: int | None = None
    ) -> None: ...

    async def process_command(self, event: Event, depth: int = 0) -> bool: ...
    async def process_bot_command(self, event: Event) -> bool: ...
    def should_process_command_event(self, event: Event) -> bool: ...

    async def get_module_config(self, module_name: str, default: Any = None) -> Any: ...
    async def save_module_config(self, module_name: str, config_data: dict) -> bool: ...
    def get_prefix_for_sender(self, sender_id: int) -> str: ...

    def store_inline_callback(self, token: str, data: dict[str, Any]) -> None: ...
    def remove_inline_callback_tokens(
        self, tokens: list[str] | tuple[str, ...]
    ) -> None: ...
    def allow_inline_callback_user(
        self, user_id: int, token: str, allow_ttl: int
    ) -> None: ...
    def set_live_module_config(self, module_name: str, config: Any) -> None: ...
    def get_live_module_config(self, module_name: str, default: Any = None) -> Any: ...

    def is_admin(self, user_id: int) -> bool: ...
    async def get_thread_id(self, event: Event) -> int | None: ...

    async def handle_error(
        self,
        error: Exception,
        message: str | None = None,
        event: Event | None = None,
    ) -> None: ...
    async def log_module(self, message: str) -> None: ...

    def raw_text(self, source: Any) -> str: ...
    def format_with_html(self, text: str, entities: Any) -> str: ...

    def pipe_interpolate(self, text: str, pipe_input: str = "") -> str: ...
    async def async_pipe_interpolate(
        self,
        text: str,
        pipe_input: str = "",
        event: Event | None = None,
        active_prefix: str = "",
    ) -> str: ...

    async def send_to_topic(
        self, entity: Any, topic: int, message: str = "", **kwargs: Any
    ) -> Any: ...
    async def send_file_to_topic(
        self, entity: Any, topic: int, file: Any, **kwargs: Any
    ) -> Any: ...

    def is_bot_available(self) -> bool: ...

    async def send_with_emoji(self, chat_id: int, text: str, **kwargs: Any) -> Any: ...
