# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01
# ---- meta data ------ kernel_handlers -------------
# author: @Hairpin00
# description: Handler registration, middleware, modules
# --- meta data end ---------------------------------
from __future__ import annotations

from typing import Any
from collections.abc import Callable

try:
    from telethon import events
except ImportError:
    events = None

try:
    from ..lib.loader.inline import InlineMessage as _InlineMessage
except ImportError:
    _InlineMessage = None


class KernelHandlersMixin:
    """Kernel handlers mixin — handler registration, middleware, module management."""

    def dedupe_event_builders(self, reason: str = "manual") -> list[str]:
        """Remove duplicate Telethon bindings while keeping the newest one."""
        if not getattr(self, "client", None):
            self.logger.debug("[event_builders] skip reason=%r missing-client", reason)
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
                    f"{event_type}:{getattr(callback, '__module__', None)}:"
                    f"{getattr(callback, '__name__', repr(callback))}"
                )
                continue
            seen.add(signature)

        if removed:
            removed.reverse()
            self.logger.warning(
                "[event_builders] deduped reason=%r before=%d after=%d "
                "removed=%r builders=%r",
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
        """Re-register core outgoing command handlers if they disappeared."""
        if not getattr(self, "client", None):
            self.logger.debug("[core_handlers] skip reason=%r missing-client", reason)
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
        has_edit = any(
            cb == self._core_message_handler and type(ev).__name__ == "MessageEdited"
            for ev, cb in builders
        )

        self.logger.debug(
            "[core_handlers] ensure reason=%r has_new=%s has_fallback=%s "
            "has_edit=%s builders=%r",
            reason,
            has_new,
            has_fallback,
            has_edit,
            self._debug_event_builders_snapshot(),
        )

        force_rebind = reason.startswith("reload_")
        if force_rebind:
            before_rebind = self._debug_event_builders_snapshot()
            self.logger.debug(
                "[core_handlers] force-rebind-start reason=%r "
                "has_new=%s has_fallback=%s has_edit=%s builders=%r",
                reason,
                has_new,
                has_fallback,
                has_edit,
                before_rebind,
            )
            self.client.remove_event_handler(
                self._core_message_handler, events.NewMessage()
            )
            if hasattr(self, "_core_fallback_message_handler"):
                self.client.remove_event_handler(
                    self._core_fallback_message_handler, events.NewMessage()
                )
            self.client.remove_event_handler(
                self._core_message_handler, events.MessageEdited()
            )
            self.client.add_event_handler(
                self._core_message_handler, events.NewMessage()
            )
            if hasattr(self, "_core_fallback_message_handler"):
                self.client.add_event_handler(
                    self._core_fallback_message_handler, events.NewMessage()
                )
            self.client.add_event_handler(
                self._core_message_handler, events.MessageEdited()
            )
            self.logger.debug(
                "[core_handlers] force-rebind-done reason=%r "
                "builders_before=%r builders_after=%r",
                reason,
                before_rebind,
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

        if not has_edit:
            self.client.add_event_handler(
                self._core_message_handler, events.MessageEdited()
            )
            self.logger.warning(
                "[core_handlers] restored outgoing MessageEdited handler " "reason=%r",
                reason,
            )

    def ensure_registered_module_handlers(self, reason: str = "manual") -> None:
        """Re-bind tracked module watchers/events if Telethon lost them."""
        if not getattr(self, "client", None):
            return

        builders = getattr(self.client, "_event_builders", []) or []

        def _has_binding(callback, event_obj) -> bool:
            event_type = type(event_obj)
            return any(
                cb == callback and isinstance(ev, event_type) for ev, cb in builders
            )

        restored = []
        central_watchers = []
        central_events = []
        reg_self = getattr(self, "register", None)
        if reg_self:
            central_watchers = getattr(reg_self, "_all_watchers", [])
            central_events = getattr(reg_self, "_all_event_handlers", [])

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
                if client is not self.client:
                    self.logger.debug(
                        "[module_handlers] skip-foreign-client reason=%r "
                        "module=%r watcher=%r event=%r client=%r",
                        reason,
                        module_name,
                        getattr(wrapper, "__name__", repr(wrapper)),
                        type(event_obj).__name__,
                        type(client).__name__,
                    )
                    continue
                if _has_binding(wrapper, event_obj):
                    self.logger.debug(
                        "[module_handlers] watcher-present reason=%r "
                        "module=%r watcher=%r event=%r",
                        reason,
                        module_name,
                        getattr(wrapper, "__name__", repr(wrapper)),
                        type(event_obj).__name__,
                    )
                    continue
                client.add_event_handler(wrapper, event_obj)
                self.logger.debug(
                    "[module_handlers] restored-watcher reason=%r "
                    "module=%r watcher=%r event=%r",
                    reason,
                    module_name,
                    getattr(wrapper, "__name__", repr(wrapper)),
                    type(event_obj).__name__,
                )
                restored.append(
                    f"watcher:{module_name}:{getattr(wrapper, '__name__', repr(wrapper))}"
                )

            for entry in getattr(reg, "__event_handlers__", []):
                handler, event_obj = entry[0], entry[1]
                client = entry[2] if len(entry) > 2 else self.client
                if client is not self.client:
                    self.logger.debug(
                        "[module_handlers] skip-foreign-client reason=%r "
                        "module=%r handler=%r event=%r client=%r",
                        reason,
                        module_name,
                        getattr(handler, "__name__", repr(handler)),
                        type(event_obj).__name__,
                        type(client).__name__,
                    )
                    continue
                if _has_binding(handler, event_obj):
                    self.logger.debug(
                        "[module_handlers] event-present reason=%r "
                        "module=%r handler=%r event=%r",
                        reason,
                        module_name,
                        getattr(handler, "__name__", repr(handler)),
                        type(event_obj).__name__,
                    )
                    continue
                client.add_event_handler(handler, event_obj)
                self.logger.debug(
                    "[module_handlers] restored-event reason=%r "
                    "module=%r handler=%r event=%r",
                    reason,
                    module_name,
                    getattr(handler, "__name__", repr(handler)),
                    type(event_obj).__name__,
                )
                restored.append(
                    f"event:{module_name}:{getattr(handler, '__name__', repr(handler))}"
                )

        seen_watchers = set()
        for entry in central_watchers:
            wrapper, event_obj = entry[0], entry[1]
            meta = entry[3] if len(entry) > 3 else {}
            module_name = meta.get("module", "unknown")
            seen_key = (
                getattr(wrapper, "__name__", repr(wrapper)),
                type(event_obj).__name__,
            )
            if seen_key in seen_watchers:
                continue
            seen_watchers.add(seen_key)
            if _has_binding(wrapper, event_obj):
                continue
            client = entry[2] if len(entry) > 2 else self.client
            client.add_event_handler(wrapper, event_obj)
            restored.append(
                f"central_watcher:{module_name}:{getattr(wrapper, '__name__', repr(wrapper))}"
            )

        seen_events = set()
        for entry in central_events:
            handler, event_obj = entry[0], entry[1]
            seen_key = (
                getattr(handler, "__name__", repr(handler)),
                type(event_obj).__name__,
            )
            if seen_key in seen_events:
                continue
            seen_events.add(seen_key)
            if _has_binding(handler, event_obj):
                continue
            client = entry[2] if len(entry) > 2 else self.client
            client.add_event_handler(handler, event_obj)
            restored.append(
                f"central_event:{getattr(handler, '__name__', repr(handler))}"
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

    def get_command(self, command: str) -> dict:
        """Get command info including handler, owner and docs."""
        return {
            "handler": self.command_handlers.get(command),
            "owner": self.command_owners.get(command),
            "docs": getattr(self, "command_docs", {}).get(command, {}),
        }

    def unregister_module_bot_commands(self, module_name: str) -> None:
        """Remove all bot commands registered by module_name."""
        to_remove = [c for c, o in self.bot_command_owners.items() if o == module_name]
        for cmd in to_remove:
            del self.bot_command_handlers[cmd]
            del self.bot_command_owners[cmd]
            self.logger.debug(f"Removed bot command: {cmd}")

    def register_inline_handler(self, pattern: str, handler: Any) -> None:
        """Register an inline query handler."""
        self._inline.register_inline_handler(pattern, handler)

    def unregister_module_inline_handlers(self, module_name: str) -> None:
        """Remove all inline handlers for a module."""
        self._inline.unregister_module_inline_handlers(module_name)

    def register_callback_handler(self, pattern: str, handler: Any) -> None:
        """Register a callback query handler."""
        self._inline.register_callback_handler(pattern, handler)

    @property
    def InlineMessage(self) -> type[_InlineMessage]:
        """Get the InlineMessage class for editing/deleting inline messages."""
        return _InlineMessage

    def get_module_inline_commands(self, module_name: str) -> list:
        """Get inline commands registered by a module."""
        return self._inline.get_module_inline_commands(module_name)

    async def inline_query_and_click(
        self, chat_id: int, query: str, **kwargs: Any
    ) -> Any:
        """Perform an inline query and click a result."""
        return await self._inline.inline_query_and_click(chat_id, query, **kwargs)

    async def send_inline(
        self, chat_id: int, query: str, buttons: Any | None = None
    ) -> bool:
        """Send an inline result using the configured bot."""
        return await self._inline.send_inline(chat_id, query, buttons)

    async def send_inline_from_config(
        self, chat_id: int, query: str, buttons: Any | None = None
    ) -> Any:
        """Send an inline result using the bot from config."""
        return await self._inline.send_inline_from_config(chat_id, query, buttons)

    async def inline_form(
        self,
        chat_id: int,
        title: str,
        fields: list[dict[str, Any]] | None = None,
        buttons: list[Any] | None = None,
        auto_send=True,
        ttl=200,
        **kwargs,
    ):
        """Create and optionally send an inline form."""
        return await self._inline.inline_form(
            chat_id, title, fields, buttons, auto_send, ttl, **kwargs
        )

    def add_event_middleware(self, middleware_func: Callable):
        """Register an event middleware and bind it to the Telethon client."""
        if middleware_func not in self.middleware_chain:
            self.middleware_chain.append(middleware_func)
        self._sync_client_middlewares()
        return middleware_func

    def remove_event_middleware(self, middleware_func: Callable) -> None:
        """Unregister an event middleware from the kernel and Telethon client."""
        if middleware_func in self.middleware_chain:
            self.middleware_chain.remove(middleware_func)
        if self.client and hasattr(self.client, "remove_event_middleware"):
            try:
                self.client.remove_event_middleware(middleware_func)
            except ValueError:
                pass
        self._event_middleware_ids.discard(id(middleware_func))

    def middleware(self, middleware_func: Callable):
        """Decorator alias for registering an event middleware."""
        return self.add_event_middleware(middleware_func)

    def add_middleware(self, middleware_func: Callable):
        """Backward-compatible alias for event middleware registration."""
        return self.add_event_middleware(middleware_func)

    def add_request_middleware(self, middleware_func: Callable):
        """Register a request middleware and bind it to the Telethon client."""
        if middleware_func not in self.request_middleware_chain:
            self.request_middleware_chain.append(middleware_func)
        self._sync_client_middlewares()
        return middleware_func

    def remove_request_middleware(self, middleware_func: Callable) -> None:
        """Unregister a request middleware from the kernel and Telethon client."""
        if middleware_func in self.request_middleware_chain:
            self.request_middleware_chain.remove(middleware_func)
        if self.client and hasattr(self.client, "remove_request_middleware"):
            try:
                self.client.remove_request_middleware(middleware_func)
            except ValueError:
                pass
        self._request_middleware_ids.discard(id(middleware_func))

    def request_middleware(self, middleware_func: Callable):
        """Decorator alias for request middleware registration."""
        return self.add_request_middleware(middleware_func)

    async def process_with_middleware(self, event: Any, handler: Callable) -> Any:
        """Run event through all middleware, then call handler."""
        if self.client and hasattr(self.client, "_middleware"):
            return await self.client._middleware.process(
                event,
                lambda current_event: handler(current_event),
            )

        for mw in self.middleware_chain:
            if await mw(event, handler) is False:
                return False
        return await handler(event)

    async def init_client(self) -> bool:
        """Initialize and authorize the main Telegram client."""
        ok = await self._client_mgr.init_client()
        if ok:
            self._sync_client_middlewares()
        return ok

    async def setup_inline_bot(self) -> bool:
        """Start the inline bot client if configured."""
        return await self._client_mgr.setup_inline_bot()

    async def safe_connect(self) -> bool:
        """Reconnect the client with exponential back-off."""
        return await self._client_mgr.safe_connect()
