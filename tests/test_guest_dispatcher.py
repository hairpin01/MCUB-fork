# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""Tests for guest-mode commands: Register.guest_command + dispatcher."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.lib.loader.dispatcher import CommandDispatcher
from core.lib.loader.register import Register
from core.lib.utils.exceptions import CommandConflictError


def _kernel(owner="mod"):
    kernel = MagicMock()
    kernel.custom_prefix = "."
    kernel.logger_name = "test"
    kernel.system_modules = {}
    kernel.loaded_modules = {owner: object()}
    kernel.current_loading_module = owner
    kernel.guest_handler = {}
    kernel.guest_handler_owners = {}
    kernel.guest_handler_docs = {}
    kernel.config = {"inline_bot_username": "my_bot"}
    kernel.should_deliver_module_event = MagicMock(return_value=True)
    kernel.handle_error = AsyncMock()

    def _set_text(event, text):
        event.text = text

    kernel._set_event_text = _set_text
    return kernel


def _event(text, is_query=True):
    return SimpleNamespace(
        text=text, raw_text=text, is_query=is_query, _client=None, sender_id=1
    )


class TestGuestRegister:
    def test_registers_command_and_aliases(self):
        kernel = _kernel()
        reg = Register(kernel)

        @reg.guest_command("^.hello$", alias=["hi", "hey"], doc_en="Say hello")
        async def hello(event):
            pass

        assert kernel.guest_handler["hello"] is hello
        assert kernel.guest_handler["hi"] is hello
        assert kernel.guest_handler["hey"] is hello
        assert kernel.guest_handler_owners["hi"] == "mod"
        assert kernel.guest_handler_docs["hello"]["en"] == "Say hello"
        # guest commands are NOT regular commands
        assert "hello" not in kernel.command_handlers

    def test_conflict(self):
        kernel = _kernel()
        reg = Register(kernel)

        @reg.guest_command("ping")
        async def a(event):
            pass

        with pytest.raises(CommandConflictError):

            @reg.guest_command("ping")
            async def b(event):
                pass

    def test_requires_module_context(self):
        kernel = _kernel()
        kernel.current_loading_module = None
        with pytest.raises(ValueError):
            Register(kernel).guest_command("x")(lambda e: None)

    def test_unregister_module(self):
        kernel = _kernel()
        reg = Register(kernel)
        reg.guest_command("a", alias="b")(AsyncMock())
        assert sorted(reg.unregister_module_guest_commands("mod")) == ["a", "b"]
        assert kernel.guest_handler == {}

    def test_aliases_are_tracked(self):
        kernel = _kernel()
        reg = Register(kernel)
        reg.guest_command("hello", alias=["hi", "hey"])(AsyncMock())
        assert kernel.guest_handler_aliases == {"hi": "hello", "hey": "hello"}

    def test_unregister_clears_alias_index(self):
        kernel = _kernel()
        reg = Register(kernel)
        reg.guest_command("hello", alias="hi")(AsyncMock())
        assert reg.unregister_guest_command("hello") is True
        assert kernel.guest_handler_aliases == {}
        assert reg.unregister_guest_command("hello") is False

    def test_get_module_guest_commands_folds_aliases(self):
        kernel = _kernel()
        reg = Register(kernel)
        reg.guest_command("hello", alias=["hi"], doc_ru="Привет", doc_en="Say hello")(
            AsyncMock()
        )
        reg.guest_command("bye", doc_en="Bye")(AsyncMock())

        assert reg.get_module_guest_commands("mod", "ru") == [
            ("bye", "Bye", []),
            ("hello", "Привет", ["hi"]),
        ]
        assert reg.get_module_guest_commands("mod", "en")[1][1] == "Say hello"
        assert reg.get_module_guest_commands("other") == []

    def test_loader_unregister_removes_guest_commands(self):
        from core.lib.mixin.module_unloader_mixin import ModuleUnloaderMixin

        kernel = _kernel()
        register = Register(kernel)
        kernel.register = register
        register.guest_command("hello", alias="hi")(AsyncMock())

        assert ModuleUnloaderMixin._unregister_guest_commands(kernel, "mod") == [
            "hello",
            "hi",
        ]
        assert kernel.guest_handler == {}
        assert kernel.guest_handler_aliases == {}


class TestGuestDispatch:
    @pytest.mark.asyncio
    async def test_dispatches_and_strips_username(self):
        kernel = _kernel()
        handler = AsyncMock()
        kernel.guest_handler["hello"] = handler
        kernel.guest_handler_owners["hello"] = "mod"
        d = CommandDispatcher(kernel)

        event = _event("@My_Bot hello big world")
        await d.guest_message_handler(event)

        handler.assert_awaited_once()
        assert event.text == "hello big world"
        assert event.guest_command == "hello"
        assert event.guest_args == "big world"
        assert event.guest_argv == ["big", "world"]

    @pytest.mark.asyncio
    async def test_mention_after_command(self):
        kernel = _kernel()
        handler = AsyncMock()
        kernel.guest_handler["hello"] = handler
        kernel.guest_handler_owners["hello"] = "mod"
        d = CommandDispatcher(kernel)

        event = _event("hello @my_bot x")
        await d.guest_message_handler(event)

        handler.assert_awaited_once()
        assert event.guest_args == "x"

    @pytest.mark.asyncio
    async def test_unknown_command_ignored(self):
        kernel = _kernel()
        handler = AsyncMock()
        kernel.guest_handler["hello"] = handler
        kernel.guest_handler_owners["hello"] = "mod"
        await CommandDispatcher(kernel).guest_message_handler(_event("@my_bot nope"))
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_posted_message_is_not_a_query(self):
        kernel = _kernel()
        handler = AsyncMock()
        kernel.guest_handler["hello"] = handler
        kernel.guest_handler_owners["hello"] = "mod"
        await CommandDispatcher(kernel).guest_message_handler(
            _event("@my_bot hello", is_query=False)
        )
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stale_owner_is_pruned(self):
        kernel = _kernel()
        handler = AsyncMock()
        kernel.guest_handler["hello"] = handler
        kernel.guest_handler_owners["hello"] = "gone"
        await CommandDispatcher(kernel).guest_message_handler(_event("@my_bot hello"))
        handler.assert_not_awaited()
        assert "hello" not in kernel.guest_handler

    @pytest.mark.asyncio
    async def test_non_admin_is_skipped(self):
        kernel = _kernel()
        kernel.is_admin.return_value = False
        handler = AsyncMock()
        kernel.guest_handler["hello"] = handler
        kernel.guest_handler_owners["hello"] = "mod"
        await CommandDispatcher(kernel).guest_message_handler(_event("@my_bot hello"))
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_admin_is_dispatched(self):
        kernel = _kernel()
        kernel.is_admin.return_value = True
        handler = AsyncMock()
        kernel.guest_handler["hello"] = handler
        kernel.guest_handler_owners["hello"] = "mod"
        await CommandDispatcher(kernel).guest_message_handler(_event("@my_bot hello"))
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_kernel_without_is_admin_is_allowed(self):
        kernel = _kernel()
        del kernel.is_admin
        handler = AsyncMock()
        kernel.guest_handler["hello"] = handler
        kernel.guest_handler_owners["hello"] = "mod"
        await CommandDispatcher(kernel).guest_message_handler(_event("@my_bot hello"))
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_security_block(self):
        kernel = _kernel()
        kernel.should_deliver_module_event.return_value = False
        handler = AsyncMock()
        kernel.guest_handler["hello"] = handler
        kernel.guest_handler_owners["hello"] = "mod"
        await CommandDispatcher(kernel).guest_message_handler(_event("@my_bot hello"))
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handler_error_goes_to_kernel(self):
        kernel = _kernel()
        kernel.guest_handler["boom"] = AsyncMock(side_effect=RuntimeError("x"))
        kernel.guest_handler_owners["boom"] = "mod"
        await CommandDispatcher(kernel).guest_message_handler(_event("@my_bot boom"))
        kernel.handle_error.assert_awaited_once()


class TestGuestRegisterHandler:
    def test_idempotent_registration(self, monkeypatch):
        import core.lib.loader.dispatcher as mod

        class FakeGuest:
            pass

        monkeypatch.setattr(mod.events, "GuestMessage", FakeGuest, raising=False)
        kernel = _kernel()
        client = MagicMock()
        client._event_builders = []
        client.add_event_handler.side_effect = (
            lambda cb, ev: client._event_builders.append((ev, cb))
        )
        d = CommandDispatcher(kernel)

        assert d.register_guest(client) is True
        assert d.register_guest(client) is False
        assert client.add_event_handler.call_count == 1

    def test_no_client_is_noop(self, monkeypatch):
        import core.lib.loader.dispatcher as mod

        monkeypatch.setattr(mod.events, "GuestMessage", object, raising=False)
        kernel = _kernel()
        kernel.bot_client = None
        assert CommandDispatcher(kernel).register_guest() is False


class TestModuleBaseDecorator:
    def test_decorator_collected_in_registry(self):
        from core.lib.loader.module_base import ModuleBase, guest_command

        class M(ModuleBase):
            @guest_command("hello", alias="hi", doc_en="x")
            async def g(self, event):
                pass

        assert len(M._guest_cmd_registry) == 1
        pattern, func, meta = M._guest_cmd_registry[0]
        assert pattern == "hello" and func.__name__ == "g"
        assert meta["alias"] == "hi"
