# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""
Tests for inline features
"""

import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


class _RichInlineClient:
    def __init__(self, *, fail_rich: bool = False) -> None:
        self.fail_rich = fail_rich
        self.requests = []
        self.edit_message_calls = []

    async def __call__(self, request):
        self.requests.append(request)
        if self.fail_rich and getattr(request, "rich_message", None) is not None:
            from telethon.errors import BadRequestError

            raise BadRequestError(request, "RICH_MESSAGE_UNSUPPORTED", 400)
        return object()

    async def edit_message(self, *args, **kwargs):
        self.edit_message_calls.append((args, kwargs))
        return object()


def _inline_event(inline_message_id: str = "1:2:3"):
    return SimpleNamespace(
        data=b"",
        inline_message_id=inline_message_id,
        chat_id=None,
        message_id=None,
        sender_id=None,
        unit_id="",
        edit=AsyncMock(),
        answer=AsyncMock(),
    )


class TestInlineManager:
    """Test InlineManager functionality"""

    @pytest.fixture
    def mock_kernel(self):
        kernel = MagicMock()
        kernel.db_get = AsyncMock(return_value=None)
        kernel.db_set = AsyncMock(return_value=True)
        kernel.db_delete = AsyncMock(return_value=True)
        kernel.logger = MagicMock()
        kernel.ADMIN_ID = 1
        return kernel

    @pytest.fixture
    def inline_manager(self, mock_kernel):
        from core_inline.lib.manager import InlineManager

        return InlineManager(mock_kernel)

    @pytest.mark.asyncio
    async def test_admin_always_allowed(self, inline_manager, mock_kernel):
        """Test that admin is always allowed"""
        result = await inline_manager.is_allowed(1)
        assert result is True

    @pytest.mark.asyncio
    async def test_unknown_user_denied(self, inline_manager):
        """Test that unknown user is denied"""
        result = await inline_manager.is_allowed(999)
        assert result is False

    @pytest.mark.asyncio
    async def test_allow_global_user(self, inline_manager, mock_kernel):
        """Test allowing user globally"""
        mock_kernel.db_get = AsyncMock(return_value=None)

        result = await inline_manager.allow_user(123)
        assert result is True

        mock_kernel.db_set.assert_called_once()
        call_args = mock_kernel.db_set.call_args
        assert call_args[0][0] == "inline_permissions"
        assert call_args[0][1] == "allowed_users"

    @pytest.mark.asyncio
    async def test_allow_specific_command(self, inline_manager, mock_kernel):
        """Test allowing user for specific command"""
        result = await inline_manager.allow_user(456, "ping")
        assert result is True

    @pytest.mark.asyncio
    async def test_deny_user(self, inline_manager, mock_kernel):
        """Test denying user"""
        existing_data = json.dumps({"global": [123, 456], "ping": [789]})
        mock_kernel.db_get = AsyncMock(return_value=existing_data)

        result = await inline_manager.deny_user(123)
        assert result is True

    @pytest.mark.asyncio
    async def test_get_allowed_users(self, inline_manager, mock_kernel):
        """Test getting allowed users"""
        existing_data = json.dumps({"global": [1, 2, 3], "ping": [4, 5]})
        mock_kernel.db_get = AsyncMock(return_value=existing_data)

        global_users = await inline_manager.get_allowed_users()
        assert global_users == [1, 2, 3]

        ping_users = await inline_manager.get_allowed_users("ping")
        assert ping_users == [4, 5]

    @pytest.mark.asyncio
    async def test_clear_all(self, inline_manager, mock_kernel):
        """Test clearing all permissions"""
        result = await inline_manager.clear_all()
        assert result is True
        mock_kernel.db_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_admin_true(self, inline_manager, mock_kernel):
        """Test admin identification"""
        result = await inline_manager.is_admin(1)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_admin_false(self, inline_manager, mock_kernel):
        """Test non-admin returns false"""
        result = await inline_manager.is_admin(999)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_allowed_specific_command(self, inline_manager, mock_kernel):
        """Test allowing user for specific command"""
        existing_data = json.dumps({"global": [1], "ping": [456]})
        mock_kernel.db_get = AsyncMock(return_value=existing_data)

        result = await inline_manager.is_allowed(456, "ping")
        assert result is True

    @pytest.mark.asyncio
    async def test_deny_user_no_data(self, inline_manager, mock_kernel):
        """Test deny when no data exists"""
        mock_kernel.db_get = AsyncMock(return_value=None)
        result = await inline_manager.deny_user(123)
        assert result is False

    @pytest.mark.asyncio
    async def test_deny_user_specific_command(self, inline_manager, mock_kernel):
        """Test denying user from specific command"""
        existing_data = json.dumps({"global": [1], "ping": [456, 789]})
        mock_kernel.db_get = AsyncMock(return_value=existing_data)

        result = await inline_manager.deny_user(456, "ping")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_allowed_users_no_data(self, inline_manager, mock_kernel):
        """Test get allowed users when no data"""
        mock_kernel.db_get = AsyncMock(return_value=None)
        result = await inline_manager.get_allowed_users()
        assert result == []

    @pytest.mark.asyncio
    async def test_allow_user_exception(self, inline_manager, mock_kernel):
        """Test allow_user handles exceptions"""
        mock_kernel.db_get = AsyncMock(side_effect=Exception("DB error"))
        result = await inline_manager.allow_user(123)
        assert result is False

    @pytest.mark.asyncio
    async def test_clear_all_exception(self, inline_manager, mock_kernel):
        """Test clear_all handles exceptions"""
        mock_kernel.db_delete = AsyncMock(side_effect=Exception("DB error"))
        result = await inline_manager.clear_all()
        assert result is False


class TestInlineManagerEdgeCases:
    """Test InlineManager edge cases"""

    @pytest.fixture
    def mock_kernel(self):
        kernel = MagicMock()
        kernel.db_get = AsyncMock(return_value=None)
        kernel.db_set = AsyncMock(return_value=True)
        kernel.db_delete = AsyncMock(return_value=True)
        kernel.logger = MagicMock()
        kernel.ADMIN_ID = 1
        return kernel

    @pytest.fixture
    def inline_manager(self, mock_kernel):
        from core_inline.lib.manager import InlineManager

        return InlineManager(mock_kernel)

    @pytest.mark.asyncio
    async def test_allow_same_user_twice(self, inline_manager, mock_kernel):
        """Test allowing the same user twice doesn't duplicate"""
        mock_kernel.db_get = AsyncMock(return_value=json.dumps({"global": [123]}))
        mock_kernel.db_set = AsyncMock(return_value=True)

        result = await inline_manager.allow_user(123)
        assert result is True

    @pytest.mark.asyncio
    async def test_deny_admin_no_effect(self, inline_manager, mock_kernel):
        """Test denying admin has no effect (admin always allowed)"""
        mock_kernel.db_get = AsyncMock(return_value=json.dumps({"global": []}))

        result = await inline_manager.deny_user(1)
        assert result is False

        is_still_allowed = await inline_manager.is_allowed(1)
        assert is_still_allowed is True

    @pytest.mark.asyncio
    async def test_command_deny_overrides_global_allow(
        self, inline_manager, mock_kernel
    ):
        """Test per-command deny overrides global inline access."""
        storage = {"global": [123]}

        async def db_get(_module, _key):
            return json.dumps(storage)

        async def db_set(_module, _key, value):
            storage.clear()
            storage.update(json.loads(value))
            return True

        mock_kernel.db_get = AsyncMock(side_effect=db_get)
        mock_kernel.db_set = AsyncMock(side_effect=db_set)

        assert await inline_manager.is_allowed(123, command="catalog") is True
        assert await inline_manager.deny_user(123, command="catalog") is True
        assert await inline_manager.is_allowed(123, command="catalog") is False
        assert await inline_manager.is_allowed(123, command="cfg") is True

    @pytest.mark.asyncio
    async def test_allow_command_clears_command_deny(self, inline_manager, mock_kernel):
        """Test allowing command removes a previous per-command deny."""
        storage = {"global": [123], "denied": {"catalog": [123]}}

        async def db_get(_module, _key):
            return json.dumps(storage)

        async def db_set(_module, _key, value):
            storage.clear()
            storage.update(json.loads(value))
            return True

        mock_kernel.db_get = AsyncMock(side_effect=db_get)
        mock_kernel.db_set = AsyncMock(side_effect=db_set)

        assert await inline_manager.is_allowed(123, command="catalog") is False
        assert await inline_manager.allow_user(123, command="catalog") is True
        assert await inline_manager.is_allowed(123, command="catalog") is True
        assert storage.get("denied", {}).get("catalog") is None

    @pytest.mark.asyncio
    async def test_empty_global_list(self, inline_manager, mock_kernel):
        """Test empty global list denies all non-admins"""
        mock_kernel.db_get = AsyncMock(return_value=json.dumps({"global": []}))

        result = await inline_manager.is_allowed(123)
        assert result is False

    @pytest.mark.asyncio
    async def test_user_in_command_but_not_global(self, inline_manager, mock_kernel):
        """Test user allowed for command but not global"""
        mock_kernel.db_get = AsyncMock(
            return_value=json.dumps({"global": [], "specific": [456]})
        )

        result = await inline_manager.is_allowed(456, "specific")
        assert result is True

        result_global = await inline_manager.is_allowed(456)
        assert result_global is False

    @pytest.mark.asyncio
    async def test_allow_everyone_allows_unknown_user_everywhere(
        self, inline_manager, mock_kernel
    ):
        """Test global everyone mode allows any non-admin user."""
        storage = {"global": []}

        async def db_get(_module, _key):
            return json.dumps(storage)

        async def db_set(_module, _key, value):
            storage.clear()
            storage.update(json.loads(value))
            return True

        mock_kernel.db_get = AsyncMock(side_effect=db_get)
        mock_kernel.db_set = AsyncMock(side_effect=db_set)

        assert await inline_manager.allow_everyone("all") is True
        assert await inline_manager.get_everyone_mode() == "all"
        assert await inline_manager.is_allowed(999, context="private") is True
        assert await inline_manager.is_allowed(999, context="groups") is True

    @pytest.mark.asyncio
    async def test_allow_everyone_groups_respects_context(
        self, inline_manager, mock_kernel
    ):
        """Test groups-only everyone mode does not allow private inline queries."""
        mock_kernel.db_get = AsyncMock(
            return_value=json.dumps({"global": [], "everyone": "groups"})
        )

        assert await inline_manager.is_allowed(999, context="groups") is True
        assert await inline_manager.is_allowed(999, context="private") is False
        assert await inline_manager.is_allowed(999) is False

    @pytest.mark.asyncio
    async def test_allow_everyone_pm_respects_context(
        self, inline_manager, mock_kernel
    ):
        """Test PM-only everyone mode does not allow group inline queries."""
        mock_kernel.db_get = AsyncMock(
            return_value=json.dumps({"global": [], "everyone": "pm"})
        )

        assert await inline_manager.is_allowed(999, context="private") is True
        assert await inline_manager.is_allowed(999, context="groups") is False

    @pytest.mark.asyncio
    async def test_deny_everyone_removes_global_flag(self, inline_manager, mock_kernel):
        """Test disabling everyone mode preserves regular user lists."""
        storage = {"global": [123], "everyone": "all"}

        async def db_get(_module, _key):
            return json.dumps(storage)

        async def db_set(_module, _key, value):
            storage.clear()
            storage.update(json.loads(value))
            return True

        mock_kernel.db_get = AsyncMock(side_effect=db_get)
        mock_kernel.db_set = AsyncMock(side_effect=db_set)

        assert await inline_manager.deny_everyone() is True
        assert "everyone" not in storage
        assert storage["global"] == [123]

    @pytest.mark.asyncio
    async def test_corrupted_json_handled(self, inline_manager, mock_kernel):
        """Test corrupted JSON data is handled gracefully"""
        mock_kernel.db_get = AsyncMock(return_value="not valid json {{{")
        result = await inline_manager.get_allowed_users()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_allow_user_zero_id(self, inline_manager, mock_kernel):
        """Test allowing user with ID 0"""
        mock_kernel.db_get = AsyncMock(return_value=None)
        result = await inline_manager.allow_user(0)
        assert result is True

    @pytest.mark.asyncio
    async def test_allow_user_negative_id(self, inline_manager, mock_kernel):
        """Test allowing user with negative ID"""
        mock_kernel.db_get = AsyncMock(return_value=None)
        result = await inline_manager.allow_user(-1)
        assert result is True

    @pytest.mark.asyncio
    async def test_allow_user_large_id(self, inline_manager, mock_kernel):
        """Test allowing user with large ID"""
        mock_kernel.db_get = AsyncMock(return_value=None)
        large_id = 999999999999
        result = await inline_manager.allow_user(large_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_multiple_commands_per_user(self, inline_manager, mock_kernel):
        """Test user can have permissions for multiple commands"""
        existing_data = json.dumps(
            {
                "global": [123],
                "cmd1": [123],
                "cmd2": [123],
                "cmd3": [123],
            }
        )
        mock_kernel.db_get = AsyncMock(return_value=existing_data)

        for cmd in ["cmd1", "cmd2", "cmd3"]:
            result = await inline_manager.is_allowed(123, cmd)
            assert result is True

    @pytest.mark.asyncio
    async def test_empty_command_name(self, inline_manager, mock_kernel):
        """Test allowing user for empty command name"""
        mock_kernel.db_get = AsyncMock(return_value=None)
        result = await inline_manager.allow_user(123, "")
        assert result is True

    @pytest.mark.asyncio
    async def test_special_chars_in_command_name(self, inline_manager, mock_kernel):
        """Test allowing user for command with special characters"""
        mock_kernel.db_get = AsyncMock(return_value=None)

        result = await inline_manager.allow_user(123, "cmd_with_underscore")
        assert result is True

        result2 = await inline_manager.allow_user(123, "cmd-with-dash")
        assert result2 is True


class TestInlineFeatures:
    """Test inline functionality"""

    def test_inline_handler_registration(self):
        """Test inline handler registration"""
        kernel = MagicMock()
        kernel.inline_handlers = {}

        async def inline_handler(event):
            return []

        kernel.inline_handlers["test"] = inline_handler

        assert "test" in kernel.inline_handlers

    def test_callback_handler_registration(self):
        """Test callback handler registration"""
        kernel = MagicMock()
        kernel.callback_handlers = {}

        async def callback_handler(event):
            return

        kernel.callback_handlers["test"] = callback_handler

        assert "test" in kernel.callback_handlers

    def test_multiple_inline_handlers(self):
        """Test multiple inline handlers can be registered"""
        kernel = MagicMock()
        kernel.inline_handlers = {}

        async def handler1(event):
            return []

        async def handler2(event):
            return []

        kernel.inline_handlers["cmd1"] = handler1
        kernel.inline_handlers["cmd2"] = handler2

        assert len(kernel.inline_handlers) == 2

    def test_inline_handler_replaces_existing(self):
        """Test registering same command replaces handler"""
        kernel = MagicMock()
        kernel.inline_handlers = {}

        async def old_handler(event):
            return ["old"]

        async def new_handler(event):
            return ["new"]

        kernel.inline_handlers["test"] = old_handler
        kernel.inline_handlers["test"] = new_handler

        assert kernel.inline_handlers["test"] == new_handler

    @pytest.mark.asyncio
    async def test_marked_hikka_inline_handler_receives_inline_query_args(self):
        """Marked Hikka inline handlers receive InlineQuery regardless of name."""
        from core.lib.loader.hikka_compat.fake_package import mark_hikka_inline_handler
        from core_inline.handlers import InlineHandlers

        seen = {}

        class WikiSearchMod:
            _hikka_compat = True

        async def random_named_handler(self, query):
            seen["query"] = query.query
            seen["args"] = query.args
            return None

        random_name = "JVIUwqidhfaiwdjifojheiwqahjfuoejwaiuofdhjiuwfasdjfipoejwriohi8wqafhjiuordahs98firuje"
        setattr(WikiSearchMod, random_name, random_named_handler)

        kernel = MagicMock()
        method = getattr(WikiSearchMod(), random_name)
        kernel.inline_handlers = {"wiki": mark_hikka_inline_handler(method)}
        kernel.logger = MagicMock()
        kernel._hikka_compat_inline_proxy = None

        handlers = InlineHandlers.__new__(InlineHandlers)
        handlers.kernel = kernel
        handlers._inline_manager = SimpleNamespace(
            is_allowed=AsyncMock(return_value=True)
        )

        event = SimpleNamespace(
            sender_id=123,
            query=SimpleNamespace(query_id="qid", offset=""),
        )

        handled = await handlers._dispatch_inline_handler("wiki", "wiki heroku", event)

        assert handled is False
        assert seen == {"query": "wiki heroku", "args": "heroku"}

    @pytest.mark.asyncio
    async def test_hikka_inline_dict_result_preserves_reply_markup_and_thumb(self):
        """Hikka-style dict inline results keep buttons and thumb metadata."""
        from core.lib.loader.hikka_compat.fake_package import mark_hikka_inline_handler
        from core_inline.handlers import InlineHandlers

        captured = {}
        converted_buttons = [[SimpleNamespace(text="⏱️ PePing")]]
        reply_markup = [{"text": "⏱️ PePing", "callback": AsyncMock()}]

        class InlineProxy:
            def _to_telethon_buttons(self, markup):
                captured["markup"] = markup
                return converted_buttons

        async def ping_handler(query):
            captured["args"] = query.args
            return {
                "title": "Ping",
                "description": "Tap here",
                "message": "pong",
                "thumb": "https://example.com/thumb.jpg",
                "reply_markup": reply_markup,
            }

        article = SimpleNamespace(id="article")
        event = SimpleNamespace(
            sender_id=123,
            query=SimpleNamespace(query_id="qid", offset=""),
            builder=SimpleNamespace(article=MagicMock(return_value=article)),
            answer=AsyncMock(),
        )
        kernel = MagicMock()
        kernel.inline_handlers = {"ping": mark_hikka_inline_handler(ping_handler)}
        kernel.logger = MagicMock()
        kernel._hikka_compat_inline_proxy = InlineProxy()

        handlers = InlineHandlers.__new__(InlineHandlers)
        handlers.kernel = kernel
        handlers._inline_manager = SimpleNamespace(
            is_allowed=AsyncMock(return_value=True)
        )

        handled = await handlers._dispatch_inline_handler("ping", "ping now", event)

        assert handled is True
        assert captured == {"args": "now", "markup": reply_markup}
        event.answer.assert_awaited_once_with([article])

        kwargs = event.builder.article.call_args.kwargs
        assert kwargs["title"] == "Ping"
        assert kwargs["description"] == "Tap here"
        assert kwargs["text"] == "pong"
        assert kwargs["buttons"] is converted_buttons
        assert kwargs["thumb"].url == "https://example.com/thumb.jpg"

    @pytest.mark.asyncio
    async def test_hikka_inline_list_result_preserves_buttons_alias(self):
        """Dict items inside inline result lists keep the buttons alias."""
        from core.lib.loader.hikka_compat.fake_package import mark_hikka_inline_handler
        from core_inline.handlers import InlineHandlers

        captured = {}
        converted_buttons = [[SimpleNamespace(text="Go")]]
        buttons = [[{"text": "Go", "data": "token"}]]

        class InlineProxy:
            def _to_telethon_buttons(self, markup):
                captured["markup"] = markup
                return converted_buttons

        async def catalog_handler(query):
            return [
                {
                    "title": "Catalog",
                    "description": "Open",
                    "text": "body",
                    "buttons": buttons,
                }
            ]

        article = SimpleNamespace(id="article")
        event = SimpleNamespace(
            sender_id=123,
            query=SimpleNamespace(query_id="qid", offset=""),
            builder=SimpleNamespace(article=MagicMock(return_value=article)),
            answer=AsyncMock(),
        )
        kernel = MagicMock()
        kernel.inline_handlers = {"catalog": mark_hikka_inline_handler(catalog_handler)}
        kernel.logger = MagicMock()
        kernel._hikka_compat_inline_proxy = InlineProxy()

        handlers = InlineHandlers.__new__(InlineHandlers)
        handlers.kernel = kernel
        handlers._inline_manager = SimpleNamespace(
            is_allowed=AsyncMock(return_value=True)
        )

        handled = await handlers._dispatch_inline_handler("catalog", "catalog", event)

        assert handled is True
        assert captured == {"markup": buttons}
        event.answer.assert_awaited_once_with([article])

        kwargs = event.builder.article.call_args.kwargs
        assert kwargs["title"] == "Catalog"
        assert kwargs["description"] == "Open"
        assert kwargs["text"] == "body"
        assert kwargs["buttons"] is converted_buttons

    @pytest.mark.asyncio
    async def test_native_suffix_inline_handler_receives_raw_event(self):
        """Native MCUB handlers may also end with _inline_handler."""
        from core_inline.handlers import InlineHandlers

        seen = {}

        class NativeLoader:
            async def _catalog_inline_handler(self, event):
                seen["event"] = event
                seen["text"] = event.text
                return None

        kernel = MagicMock()
        kernel.inline_handlers = {"catalog": NativeLoader()._catalog_inline_handler}
        kernel.logger = MagicMock()
        kernel._hikka_compat_inline_proxy = None

        handlers = InlineHandlers.__new__(InlineHandlers)
        handlers.kernel = kernel
        handlers._inline_manager = SimpleNamespace(
            is_allowed=AsyncMock(return_value=True)
        )

        event = SimpleNamespace(
            text="catalog",
            sender_id=123,
            query=SimpleNamespace(query_id="qid", offset=""),
        )

        handled = await handlers._dispatch_inline_handler("catalog", "catalog", event)

        assert handled is False
        assert seen == {"event": event, "text": "catalog"}

    def test_loader_catalog_inline_owner_is_loader(self):
        """catalog must stay attached to loader even if loading context is stale."""
        from modules.loader import Loader

        callbacks = {}
        kernel = SimpleNamespace(
            current_loading_module="userbot-backup",
            inline_handlers={},
            inline_handlers_owners={},
        )

        def register_inline_handler(pattern, handler):
            kernel.inline_handlers[pattern] = handler
            if kernel.current_loading_module:
                kernel.inline_handlers_owners[pattern] = kernel.current_loading_module

        def register_callback_handler(pattern, handler):
            callbacks[pattern] = handler

        kernel.register_inline_handler = register_inline_handler
        kernel.register_callback_handler = register_callback_handler

        loader_module = Loader.__new__(Loader)
        loader_module.kernel = kernel

        Loader._register_catalog_handlers(loader_module)

        assert "catalog" in kernel.inline_handlers
        assert kernel.inline_handlers_owners["catalog"] == "loader"
        assert "catalog_" in callbacks


class TestInlineButtonCleanupWatcher:
    class _Cache:
        def __init__(self, values=None):
            self.values = values or {}

        def get(self, key):
            return self.values.get(key)

    class _Register:
        def __init__(self):
            self.handlers = []
            self.keys = set()

        def watcher(self, func=None, module=None, **_tags):
            def decorator(f):
                key = (getattr(module, "__name__", ""), f.__name__)
                if key not in self.keys:
                    self.keys.add(key)
                    self.handlers.append(f)
                return f

            return decorator(func) if func is not None else decorator

    def _handlers(self, *, cache=None, inline_bot_user_id=777):
        from core_inline.handlers import InlineHandlers

        handlers = InlineHandlers.__new__(InlineHandlers)
        handlers.kernel = SimpleNamespace(
            cache=cache or self._Cache(),
            register=self._Register(),
            inline_bot_user_id=inline_bot_user_id,
            config={},
            logger=MagicMock(),
        )
        return handlers

    def test_extracts_text_url_btn_targets(self):
        from telethon.tl.types import MessageEntityTextUrl

        handlers = self._handlers()
        message = SimpleNamespace(
            entities=[
                MessageEntityTextUrl(offset=5, length=3, url="tg://btn/form_test"),
                MessageEntityTextUrl(offset=9, length=4, url="https://example.com"),
            ]
        )

        assert handlers._extract_btn_form_ids(message) == ["form_test"]

    def test_checks_form_and_inline_temp_targets(self):
        handlers = self._handlers(cache=self._Cache({"form_test": {"text": "ok"}}))
        assert handlers._inline_btn_target_exists("form_test") is True

        handlers = self._handlers(
            cache=self._Cache({"inline_temp_tmpid": {"handler": object()}})
        )
        assert handlers._inline_btn_target_exists("tmpid") is True

    @pytest.mark.asyncio
    async def test_cleanup_watcher_deletes_admin_message_from_runtime_bot(self):
        from telethon.tl.types import MessageEntityTextUrl

        handlers = self._handlers(cache=self._Cache({"form_test": {"text": "ok"}}))
        handlers.kernel.ADMIN_ID = 1
        handlers._setup_inline_button_cleanup_watcher()

        event = SimpleNamespace(
            sender_id=1,
            message=SimpleNamespace(
                entities=[MessageEntityTextUrl(5, 3, "tg://btn/form_test")],
                via_bot_id=777,
            ),
            delete=AsyncMock(),
        )

        await handlers.kernel.register.handlers[0](event)

        event.delete.assert_awaited_once()

    def test_cleanup_watcher_registers_only_once(self):
        handlers = self._handlers(cache=self._Cache({"form_test": {"text": "ok"}}))

        handlers._setup_inline_button_cleanup_watcher()
        handlers._setup_inline_button_cleanup_watcher()

        assert len(handlers.kernel.register.handlers) == 1

    def test_bot_client_proxy_does_not_probe_on_attribute(self):
        class ClientProxy:
            @property
            def on(self):  # pragma: no cover - must not be touched
                raise AssertionError("proxy .on must not be accessed")

        handlers = self._handlers()
        handlers.bot_client = ClientProxy()

        assert handlers._get_bot_client_on() is None

    @pytest.mark.asyncio
    async def test_cleanup_watcher_keeps_non_admin_messages(self):
        from telethon.tl.types import MessageEntityTextUrl

        handlers = self._handlers(cache=self._Cache({"form_test": {"text": "ok"}}))
        handlers.kernel.ADMIN_ID = 1
        handlers._setup_inline_button_cleanup_watcher()

        event = SimpleNamespace(
            sender_id=2,
            message=SimpleNamespace(
                entities=[MessageEntityTextUrl(5, 3, "tg://btn/form_test")],
                via_bot_id=777,
            ),
            delete=AsyncMock(),
        )

        await handlers.kernel.register.handlers[0](event)

        event.delete.assert_not_awaited()


class TestInlineParsing:
    """Test inline query parsing"""

    def test_button_format_conversion(self):
        """Test button format conversion"""
        buttons = [[{"text": "Btn1", "url": "http://example.com"}]]

        assert len(buttons) == 1
        assert buttons[0][0]["text"] == "Btn1"

    def test_query_string_generation(self):
        """Test query string generation"""
        query = "test query"

        assert isinstance(query, str)
        assert "test" in query.lower()

    def test_json_buttons_in_query(self):
        """Test JSON buttons in inline query"""
        buttons = [{"text": "Click", "data": "callback_data"}]
        json_str = json.dumps(buttons)

        parsed = json.loads(json_str)

        assert parsed[0]["text"] == "Click"

    @pytest.mark.parametrize(
        "query,expected_in_result",
        [
            ("test", True),
            ("", True),
            ("long query text", True),
            ("UPPERCASE", True),
            ("with numbers 123", True),
        ],
    )
    def test_various_queries(self, query, expected_in_result):
        """Test various query formats"""
        assert isinstance(query, str)

    def test_empty_button_list(self):
        """Test empty button list"""
        buttons = []
        json_str = json.dumps(buttons)
        parsed = json.loads(json_str)
        assert parsed == []

    def test_nested_button_structure(self):
        """Test nested button structure"""
        buttons = [
            [{"text": "A", "data": "a"}, {"text": "B", "data": "b"}],
            [{"text": "C", "data": "c"}],
        ]
        json_str = json.dumps(buttons)
        parsed = json.loads(json_str)

        assert len(parsed) == 2
        assert len(parsed[0]) == 2
        assert len(parsed[1]) == 1

    def test_button_with_all_fields(self):
        """Test button with all possible fields"""
        button = {
            "text": "Click Me",
            "data": "callback_id",
            "url": "https://example.com",
            "switch": "query",
        }
        json_str = json.dumps(button)
        parsed = json.loads(json_str)

        assert parsed["text"] == "Click Me"
        assert parsed["data"] == "callback_id"
        assert parsed["url"] == "https://example.com"
        assert parsed["switch"] == "query"


class TestInlinePermissionsData:
    """Test inline permissions data structures"""

    def test_permissions_data_structure(self):
        """Test permissions data structure"""
        data = {
            "global": [1, 2, 3],
            "ping": [1, 4],
            "search": [2, 5],
        }
        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        assert "global" in parsed
        assert isinstance(parsed["global"], list)
        assert 1 in parsed["global"]

    def test_empty_permissions_structure(self):
        """Test empty permissions structure"""
        data = {"global": [], "cmd1": [], "cmd2": []}
        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        assert all(len(v) == 0 for v in parsed.values())

    def test_large_user_list(self):
        """Test large user list in permissions"""
        users = list(range(1000))
        data = {"global": users}
        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        assert len(parsed["global"]) == 1000


class TestCoreInlineMessageRichEdit:
    @pytest.mark.asyncio
    async def test_edit_rich_uses_inline_rich_message_request(self):
        from telethon.tl.functions.messages import EditInlineBotMessageRequest
        from telethon.tl.types import InputRichMessageHTML

        from core.lib.types import InlineMessage

        client = _RichInlineClient()
        kernel = SimpleNamespace(client=client, bot_client=None)
        message = InlineMessage(_inline_event(), kernel=kernel)

        result = await message.edit_rich("<b>hello</b>", text="plain")

        assert result is message
        assert len(client.requests) == 1
        request = client.requests[0]
        assert isinstance(request, EditInlineBotMessageRequest)
        assert request.message == "plain"
        assert isinstance(request.rich_message, InputRichMessageHTML)
        assert request.rich_message.html == "<b>hello</b>"

    @pytest.mark.asyncio
    async def test_edit_rich_prefers_event_edit_rich(self):
        from core.lib.types import InlineMessage

        event = _inline_event()
        event.edit_rich = AsyncMock()
        client = _RichInlineClient()
        kernel = SimpleNamespace(client=client, bot_client=None)
        message = InlineMessage(event, kernel=kernel)

        result = await message.edit_rich("<b>hello</b>")

        assert result is message
        event.edit_rich.assert_awaited_once()
        assert client.requests == []

    @pytest.mark.asyncio
    async def test_edit_rich_raises_by_default_for_unsupported_peer(self):
        from core.lib.types import InlineMessage

        client = _RichInlineClient(fail_rich=True)
        kernel = SimpleNamespace(client=client, bot_client=None)
        message = InlineMessage(_inline_event(), kernel=kernel)

        with pytest.raises(Exception, match="RICH_MESSAGE_UNSUPPORTED"):
            await message.edit_rich("<b>hello</b>")

    @pytest.mark.asyncio
    async def test_edit_rich_can_fall_back_to_edit_message_for_unsupported_peer(self):
        from core.lib.types import InlineMessage

        client = _RichInlineClient(fail_rich=True)
        kernel = SimpleNamespace(client=client, bot_client=None)
        message = InlineMessage(_inline_event(), kernel=kernel)

        result = await message.edit_rich("<b>hello</b>", fallback=True)

        assert result is message
        assert len(client.requests) == 1
        assert len(client.edit_message_calls) == 1
        args, kwargs = client.edit_message_calls[0]
        assert args[1] == "<b>hello</b>"
        assert kwargs["parse_mode"] == "html"


class TestInlineRichForm:
    class _Cache:
        def __init__(self):
            self.values = {}

        def get(self, key):
            return self.values.get(key)

        def set(self, key, value, ttl=None):
            self.values[key] = value

    def _handlers(self):
        from core_inline.handlers import InlineHandlers

        handlers = InlineHandlers.__new__(InlineHandlers)
        handlers.kernel = SimpleNamespace(
            cache=self._Cache(),
            config={},
            logger=MagicMock(),
            inline_callback_map={},
        )
        handlers._form_counter = 0
        handlers._last_cleanup_time = 0.0
        handlers._cleanup_interval = 999999.0
        handlers.lang = {"btn_default": "Button"}
        return handlers

    def test_create_inline_form_stores_rich_payload(self):
        handlers = self._handlers()

        form_id = handlers.create_inline_form(
            "fallback",
            ttl=123,
            parse_mode="html",
            rich_text="<h1>Title</h1>",
            rich_parse_mode="html",
            rich_rtl=True,
            rich_noautolink=True,
        )

        form_data = handlers.get_inline_form(form_id)
        assert form_data["text"] == "fallback"
        assert form_data["parse_mode"] == "html"
        assert form_data["rich_text"] == "<h1>Title</h1>"
        assert form_data["rich_parse_mode"] == "html"
        assert form_data["rich_rtl"] is True
        assert form_data["rich_noautolink"] is True
        assert form_data["_ttl"] == 123

    @pytest.mark.asyncio
    async def test_rich_form_query_uses_builder_rich_article(self):
        from core_inline.handlers import InlineHandlers

        class Builder:
            def __init__(self):
                self.calls = []

            def article(self, title, **kwargs):
                self.calls.append((title, kwargs))
                return SimpleNamespace(title=title, kwargs=kwargs)

        handlers = self._handlers()
        handlers.check_admin = AsyncMock(return_value=True)
        handlers._dispatch_inline_handler = AsyncMock(return_value=False)
        handlers._wrap_aiogram_inline_query = lambda event: event
        handlers._dedup_runtime_event = lambda *_args, **_kwargs: False
        handlers.kernel.cache.values["form_rich"] = {
            "text": "fallback",
            "buttons": None,
            "media": None,
            "media_type": "photo",
            "parse_mode": "html",
            "rich_text": "<h1>Title</h1>",
            "rich_parse_mode": "html",
            "rich_message": None,
            "rich_rtl": True,
            "rich_noautolink": False,
            "rich_files": None,
        }
        builder = Builder()
        event = SimpleNamespace(
            text="form_rich",
            sender_id=1,
            query=SimpleNamespace(query_id=42),
            builder=builder,
            answer=AsyncMock(),
        )

        await InlineHandlers.process_inline_query(handlers, event)

        event.answer.assert_awaited_once()
        title, kwargs = builder.calls[0]
        assert title == "Inline Form"
        assert "text" not in kwargs
        assert "parse_mode" not in kwargs
        assert kwargs["rich_text"] == "<h1>Title</h1>"
        assert kwargs["rich_parse_mode"] == "html"
        assert kwargs["rich_rtl"] is True

    @pytest.mark.asyncio
    async def test_rich_form_query_passes_photo_to_rich_article(self):
        from core_inline.handlers import InlineHandlers

        class Builder:
            def __init__(self):
                self.calls = []

            def article(self, title, **kwargs):
                self.calls.append((title, kwargs))
                return SimpleNamespace(title=title, kwargs=kwargs)

        handlers = self._handlers()
        handlers.check_admin = AsyncMock(return_value=True)
        handlers._dispatch_inline_handler = AsyncMock(return_value=False)
        handlers._wrap_aiogram_inline_query = lambda event: event
        handlers._dedup_runtime_event = lambda *_args, **_kwargs: False
        handlers.kernel.cache.values["form_rich"] = {
            "text": "fallback",
            "buttons": None,
            "media": "https://example.com/pic.jpg",
            "media_type": "photo",
            "parse_mode": "html",
            "rich_text": "<h1>Title</h1>",
            "rich_parse_mode": "html",
            "rich_message": None,
            "rich_rtl": None,
            "rich_noautolink": None,
            "rich_files": None,
        }
        builder = Builder()
        event = SimpleNamespace(
            text="form_rich",
            sender_id=1,
            query=SimpleNamespace(query_id=42),
            builder=builder,
            answer=AsyncMock(),
        )

        await InlineHandlers.process_inline_query(handlers, event)

        event.answer.assert_awaited_once()
        _title, kwargs = builder.calls[0]
        assert kwargs["rich_text"] == "<h1>Title</h1>"
        assert kwargs["thumb"].url == "https://example.com/pic.jpg"
        assert kwargs["content"].url == "https://example.com/pic.jpg"
        assert kwargs["thumb"].mime_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_subinline_rich_form_calls_inline_form_with_rich_payload(self):
        from core.lib.loader.inline import InlineManager

        manager = InlineManager.__new__(InlineManager)
        calls = []

        async def fake_inline_form(**kwargs):
            calls.append(kwargs)
            return True, object()

        manager.inline_form = fake_inline_form

        result = await InlineManager.rich_form(
            manager,
            123,
            "<b>rich</b>",
            ttl=60,
            buttons=[],
        )

        assert result[0] is True
        assert calls[0]["chat_id"] == 123
        assert calls[0]["title"] == "<b>rich</b>"
        assert calls[0]["rich_text"] == "<b>rich</b>"
        assert calls[0]["rich_parse_mode"] == "html"
        assert calls[0]["ttl"] == 60

    @pytest.mark.asyncio
    async def test_rich_form_appends_escaped_callback_page_buttons(self):
        from core.lib.loader.base import RichButtonRow, RichCallbackButton
        from core.lib.loader.inline import InlineManager

        manager = InlineManager.__new__(InlineManager)
        calls = []

        async def fake_inline_form(**kwargs):
            calls.append(kwargs)
            return True, object()

        manager.inline_form = fake_inline_form
        result = await InlineManager.rich_form(
            manager,
            123,
            "<p>Choose</p>",
            buttons=[[{"text": "Normal", "type": "callback", "data": "normal"}]],
            rich_buttons=[
                [RichCallbackButton("Run <now>", 'run"token', "success")],
                RichButtonRow(
                    (RichCallbackButton("Stop", "stop-token", "danger"),), "right"
                ),
            ],
        )

        assert result[0] is True
        assert calls[0]["buttons"] == [
            [{"text": "Normal", "type": "callback", "data": "normal"}]
        ]
        assert calls[0]["rich_text"] == (
            "<p>Choose</p>\n"
            '<tg-button-row align="center"><tg-button type="callback_data" '
            'data="run&quot;token" style="success">Run &lt;now&gt;</tg-button>'
            "</tg-button-row>\n"
            '<tg-button-row align="right"><tg-button type="callback_data" '
            'data="stop-token" style="danger">Stop</tg-button></tg-button-row>'
        )

        try:
            from telethon.extensions.richparser import BlockButtonRow, parse_rich_html
        except ImportError:
            pytest.skip("Telethon-MCUB richparser is unavailable")
        blocks = parse_rich_html(calls[0]["rich_text"])
        rows = [block for block in blocks if isinstance(block, BlockButtonRow)]
        assert len(rows) == 2
        assert rows[0].buttons[0].attrs["data"] == 'run"token'

    @pytest.mark.asyncio
    async def test_rich_public_facades_forward_or_render_rich_buttons_once(self):
        from core.lib.kernel_handlers import KernelHandlersMixin
        from core.lib.loader.base import RichCallbackButton
        from core_inline.api import CodeInline

        spec = RichCallbackButton("Run", "run-token", "success")
        inline = SimpleNamespace(rich_form=AsyncMock(return_value="form"))
        handlers = object.__new__(KernelHandlersMixin)
        handlers._inline = inline

        assert await handlers.rich_form(1, "<p>x</p>", rich_buttons=[spec]) == "form"
        inline.rich_form.assert_awaited_once_with(1, "<p>x</p>", rich_buttons=[spec])

        kernel = SimpleNamespace(rich_form=AsyncMock(return_value="kernel-form"))
        facade = CodeInline(kernel, ttl=77)
        assert (
            await facade.rich_form(2, "<p>x</p>", rich_buttons=[spec]) == "kernel-form"
        )
        kernel.rich_form.assert_awaited_once_with(
            2, "<p>x</p>", ttl=77, rich_buttons=[spec]
        )

        fallback_kernel = SimpleNamespace(
            inline_form=AsyncMock(return_value="fallback")
        )
        fallback = CodeInline(fallback_kernel, ttl=88)
        assert (
            await fallback.rich_form(
                3, "<p>x</p>", text="fallback text", rich_buttons=[spec]
            )
            == "fallback"
        )
        fallback_kernel.inline_form.assert_awaited_once()
        kwargs = fallback_kernel.inline_form.await_args.kwargs
        assert kwargs["ttl"] == 88
        assert kwargs["rich_text"].count("<tg-button-row") == 1
        assert "rich_buttons" not in kwargs
        assert fallback_kernel.inline_form.await_args.args == (3, "fallback text")

    @pytest.mark.asyncio
    async def test_inline_message_edit_rich_renders_buttons_once_and_rejects_invalid_sources(
        self,
    ):
        from core.lib.loader.base import RichCallbackButton
        from core.lib.types.inline_message import InlineMessage

        event = _inline_event()
        event.edit_rich = AsyncMock()
        message = InlineMessage(event)
        specs = [
            RichCallbackButton("One", "one-token"),
            RichCallbackButton("Two", "two-token", "success"),
        ]
        reply_buttons = [[{"text": "Normal", "type": "callback", "data": "normal"}]]

        await message.edit_rich("<p>x</p>", buttons=reply_buttons, rich_buttons=specs)

        event.edit_rich.assert_awaited_once()
        call = event.edit_rich.await_args
        assert call.args[0].count("<tg-button-row") == 1
        assert call.kwargs["buttons"] == reply_buttons
        rich = call.kwargs["rich_message"]
        assert rich.html == call.args[0]
        from telethon.extensions.richparser import BlockButtonRow, parse_rich_html

        rows = [
            block
            for block in parse_rich_html(rich.html)
            if isinstance(block, BlockButtonRow)
        ]
        assert len(rows) == 1
        assert len(rows[0].buttons) == 2

        with pytest.raises(ValueError, match="markdown"):
            await message.edit_rich("<p>x</p>", markdown="x", rich_buttons=specs)
        with pytest.raises(ValueError, match="rich_message"):
            await message.edit_rich(
                "<p>x</p>", rich_message=object(), rich_buttons=specs
            )
        with pytest.raises(TypeError, match="html"):
            await message.edit_rich(markdown="x", rich_buttons=specs)

    @pytest.mark.asyncio
    async def test_rich_form_rejects_invalid_buttons_and_draft_blocks(self):
        from core.lib.loader.base import RichCallbackButton
        from core.lib.loader.inline import InlineManager

        manager = InlineManager.__new__(InlineManager)

        async def fake_inline_form(**_kwargs):
            return True, object()

        manager.inline_form = fake_inline_form
        valid = RichCallbackButton("Run", "run-token")
        with pytest.raises(ValueError, match="cannot be empty"):
            await InlineManager.rich_form(manager, 1, "<p>x</p>", rich_buttons=[])
        with pytest.raises(ValueError, match="at most 8"):
            await InlineManager.rich_form(
                manager, 1, "<p>x</p>", rich_buttons=[valid] * 9
            )
        with pytest.raises(TypeError, match=r"only Button\.rich\.inline"):
            await InlineManager.rich_form(manager, 1, "<p>x</p>", rich_buttons=[{}])
        with pytest.raises(ValueError, match="draft-only"):
            await InlineManager.rich_form(
                manager, 1, '<TG-THINKING \n data-x="1">draft</TG-THINKING>'
            )

        thinking = type("PageBlockThinking", (), {"blocks": []})()
        rich_message = SimpleNamespace(blocks=[SimpleNamespace(blocks=[thinking])])
        with pytest.raises(ValueError, match="PageBlockThinking"):
            await InlineManager.rich_form(manager, 1, rich_message=rich_message)
        unsupported = type("PageBlockUnsupported", (), {"blocks": []})()
        with pytest.raises(ValueError, match="PageBlockUnsupported"):
            await InlineManager.rich_form(
                manager, 1, rich_message=SimpleNamespace(blocks=[unsupported])
            )

    @pytest.mark.asyncio
    async def test_rich_callback_dispatch_uses_existing_inline_handler(self):
        from core.lib.loader.base import ModuleBase
        from core_inline.handlers import InlineHandlers

        class RichButtonsMod(ModuleBase):
            name = "RichDispatchMod"
            strings = {"en": {"name": "Rich dispatch"}}

            async def on_run(self, event, *args, **kwargs):
                seen["event"] = event
                seen["args"] = args
                seen["kwargs"] = kwargs

        kernel = SimpleNamespace(
            logger=MagicMock(),
            config={"language": "en"},
            inline=None,
            inline_callback_map={},
            _inline_cb_lock=threading.Lock(),
            callback_handlers={},
        )
        module = RichButtonsMod(kernel, MagicMock(), MagicMock())
        button = module.Button.rich.inline(
            "Run", handler=module.on_run, args=(1, 2), kwargs={"foo": "bar"}
        )
        seen = {}
        handlers = object.__new__(InlineHandlers)
        handlers.kernel = kernel
        handlers._api_bot = None
        handlers._cb_lock = kernel._inline_cb_lock
        handlers._cleanup_inline_callback_map = lambda: None
        handlers._wrap_aiogram_callback_query = lambda event: event
        handlers._dedup_runtime_event = lambda *_args: False
        handlers._callback_dedup_key = lambda *_args: "callback"
        handlers._should_deliver = lambda *_args: True
        handlers.check_admin = AsyncMock(return_value=True)
        handlers.lang = {
            "no_access": "NO",
            "form_expired": "EXPIRED",
            "critical_error": "ERROR",
        }
        event = _inline_event()
        event.data = button.token.encode()
        event.sender_id = 1

        await handlers.process_callback_query(event)

        assert seen["args"] == (1, 2)
        assert seen["kwargs"] == {"foo": "bar"}
        assert seen["event"].data == button.token.encode()

    @pytest.mark.asyncio
    async def test_inline_handler_watcher_registration_is_guarded_once(self):
        from core_inline.handlers import InlineHandlers

        class Client:
            def __init__(self):
                self._mcub_inline_handlers_registered = False
                self.callbacks = []

            def on(self, event):
                def decorator(handler):
                    self.callbacks.append((event, handler))
                    return handler

                return decorator

        handlers = object.__new__(InlineHandlers)
        handlers.bot_client = Client()
        handlers.kernel = SimpleNamespace(logger=MagicMock())
        handlers._start_cleanup_task = AsyncMock()

        await handlers.register_handlers()
        await handlers.register_handlers()

        assert len(handlers.bot_client.callbacks) == 2

    @pytest.mark.asyncio
    async def test_inline_form_consumes_photo_alias_as_media(self):
        from core.lib.loader.inline import InlineManager

        class Cache:
            def __init__(self):
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def set(self, key, value, ttl=None):
                self.values[key] = value

        manager = InlineManager.__new__(InlineManager)
        manager.k = SimpleNamespace(
            cache=Cache(),
            logger=MagicMock(),
            config={},
            bot_client=None,
            inline_callback_map={},
            session=SimpleNamespace(closed=False),
        )

        form_id = await InlineManager.inline_form(
            manager,
            chat_id=123,
            title="Photo form",
            auto_send=False,
            photo="https://example.com/pic.jpg",
        )

        form_data = manager.k.cache.get(form_id)
        assert form_data["media"] == "https://example.com/pic.jpg"
        assert form_data["media_type"] == "photo"

    @pytest.mark.asyncio
    async def test_inline_form_accepts_event_and_edits_status_message(self):
        from core.lib.loader.inline import InlineManager
        from core.lib.types import InlineMessage

        class Cache:
            def __init__(self):
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def set(self, key, value, ttl=None):
                self.values[key] = value

        class Result:
            def __init__(self):
                self.chat_id = None
                self.kwargs = None

            async def click(self, chat_id, **kwargs):
                self.chat_id = chat_id
                self.kwargs = kwargs
                return SimpleNamespace(id=1, inline_message_id="inline-id")

        result = Result()
        status_message = SimpleNamespace(delete=AsyncMock(), edit=AsyncMock())
        event = SimpleNamespace(
            chat_id=456,
            edit=AsyncMock(return_value=status_message),
        )
        manager = InlineManager.__new__(InlineManager)
        manager.k = SimpleNamespace(
            cache=Cache(),
            logger=MagicMock(),
            config={"inline_bot_username": "bot"},
            client=SimpleNamespace(
                inline_query=AsyncMock(return_value=[result]),
                send_message=AsyncMock(),
            ),
            bot_client=None,
            inline_callback_map={},
            session=SimpleNamespace(closed=False),
            handle_error=AsyncMock(),
        )
        manager.s = lambda key, **kwargs: key

        success, message = await InlineManager.inline_form(
            manager,
            chat_id=event,
            title="Event form",
        )

        assert success is True
        assert isinstance(message, InlineMessage)
        assert message.inline_message_id == "inline-id"
        assert manager.k.cache.get(message.unit_id) is not None
        event.edit.assert_awaited_once()
        manager.k.client.send_message.assert_not_called()
        assert result.chat_id == 456
        status_message.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_module_base_inline_does_not_wrap_inline_message_twice(self):
        from core.lib.loader.base import ModuleBase
        from core.lib.types import InlineMessage

        kernel = SimpleNamespace()
        raw_message = SimpleNamespace(
            inline_message_id="inline-id",
            chat_id=123,
            id=1,
        )
        inline_message = InlineMessage(
            raw_message,
            unit_id="form-id",
            kernel=kernel,
        )
        kernel.inline_form = AsyncMock(return_value=(True, inline_message))
        module = ModuleBase.__new__(ModuleBase)
        module.kernel = kernel

        success, result = await ModuleBase.inline(module, 123, "Form")

        assert success is True
        assert result is inline_message

    @pytest.mark.asyncio
    async def test_inline_query_and_click_strips_form_only_media_kwargs(self):
        from core.lib.loader.inline import InlineManager
        from core.lib.types import InlineMessage

        class Result:
            def __init__(self):
                self.kwargs = None

            async def click(self, chat_id, **kwargs):
                self.kwargs = kwargs
                return SimpleNamespace(id=1, inline_message_id="inline-id")

        result = Result()
        manager = InlineManager.__new__(InlineManager)
        manager.k = SimpleNamespace(
            config={"inline_bot_username": "bot"},
            logger=MagicMock(),
            client=SimpleNamespace(inline_query=AsyncMock(return_value=[result])),
            bot_client=None,
            handle_error=AsyncMock(),
            session=SimpleNamespace(closed=False),
            cache=SimpleNamespace(get=lambda *_: None, set=lambda *_, **__: None),
            inline_callback_map={},
        )

        success, message = await InlineManager.inline_query_and_click(
            manager,
            chat_id=123,
            query="form_1",
            photo="https://example.com/pic.jpg",
            media_type="photo",
            silent=True,
        )

        assert success is True
        assert isinstance(message, InlineMessage)
        assert message.unit_id == "form_1"
        assert message.inline_message_id == "inline-id"
        assert result.kwargs == {"silent": True}

    @pytest.mark.asyncio
    async def test_answer_inline_query_retries_without_parse_mode_on_entity_error(self):
        from core_inline.handlers import InlineHandlers

        class ApiBot:
            async def answer_inline_query(self, **kwargs):
                raise RuntimeError("Bad Request: can't parse InlineQueryResult")

        class Response:
            def __init__(self, payloads):
                self.payloads = payloads

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def json(self):
                return {"ok": True, "result": True}

        class Session:
            def __init__(self):
                self.payloads = []

            def post(self, url, json):
                self.payloads.append(json)
                return Response(self.payloads)

        session = Session()
        handlers = InlineHandlers.__new__(InlineHandlers)
        handlers.kernel = SimpleNamespace(session=session, logger=MagicMock())
        handlers._api_bot = ApiBot()
        handlers._get_api_bot = lambda: handlers._api_bot
        handlers._get_bot_token = lambda: "token"

        result = await InlineHandlers.answer_inline_query_custom(
            handlers,
            inline_query_id="qid",
            results=[
                {
                    "type": "photo",
                    "id": "1",
                    "photo_url": "https://example.com/pic.jpg",
                    "thumbnail_url": "https://example.com/pic.jpg",
                    "caption": "<broken",
                    "parse_mode": "HTML",
                }
            ],
        )

        assert result["ok"] is True
        assert session.payloads[0]["results"][0]["caption"] == "<broken"
        assert "parse_mode" not in session.payloads[0]["results"][0]

    def test_rich_form_normalizes_rich_media_mapping(self):
        from telethon.tl import types

        from core.lib.loader.inline import InlineManager

        photo = types.InputPhoto(1, 2, b"ref")
        document = types.InputDocument(3, 4, b"doc")

        rich_files = InlineManager._normalize_rich_media(
            {
                "hero": photo,
                "file1": document,
            }
        )

        assert isinstance(rich_files[0], types.InputRichFilePhoto)
        assert rich_files[0].id == "hero"
        assert rich_files[0].photo is photo
        assert isinstance(rich_files[1], types.InputRichFileDocument)
        assert rich_files[1].id == "file1"
        assert rich_files[1].document is document

    def test_rich_form_uses_rich_text_media_refs_as_type_hints(self):
        from telethon.tl import types

        from core.lib.loader.inline import InlineManager

        photo = types.InputPhoto(1, 2, b"ref")
        document = types.InputDocument(3, 4, b"doc")

        rich_files = InlineManager._normalize_rich_media(
            {
                "hero": photo,
                "file1": document,
            },
            rich_text=(
                '<a href="tg://photo?id=hero">Photo</a>'
                '<a href="tg://document?id=file1">File</a>'
            ),
        )

        assert isinstance(rich_files[0], types.InputRichFilePhoto)
        assert isinstance(rich_files[1], types.InputRichFileDocument)

    def test_rich_form_rejects_photo_link_document_mismatch_locally(self):
        from telethon.tl import types

        from core.lib.loader.inline import InlineManager

        document = types.InputDocument(3, 4, b"doc")

        with pytest.raises(ValueError, match="referenced as photo"):
            InlineManager._normalize_rich_media(
                {"hero": document},
                rich_text='<a href="tg://photo?id=hero">Photo</a>',
            )

    @pytest.mark.asyncio
    async def test_rich_form_uploads_url_and_rewrites_media_alias(self):
        from telethon.tl import types

        from core.lib.loader.inline import InlineManager

        manager = InlineManager.__new__(InlineManager)
        uploaded = []

        async def fake_upload(media_id, url, media_type):
            uploaded.append((media_id, url, media_type))
            return types.InputRichFileDocument(
                media_id, types.InputDocument(1, 2, b"ref")
            )

        manager._upload_url_as_rich_file = fake_upload

        rich_text, rich_files = await manager._normalize_rich_media_for_form(
            {"hero": "https://x0.at/ctOi.mp4"},
            rich_text='<a href="tg://media?id=hero">Фото</a>',
        )

        assert rich_text == '<a href="tg://video?id=hero">Фото</a>'
        assert uploaded == [("hero", "https://x0.at/ctOi.mp4", "video")]
        assert isinstance(rich_files[0], types.InputRichFileDocument)
        assert rich_files[0].id == "hero"

    @pytest.mark.asyncio
    async def test_rich_form_uploads_photo_url_for_media_alias(self):
        from telethon.tl import types

        from core.lib.loader.inline import InlineManager

        manager = InlineManager.__new__(InlineManager)
        uploaded = []

        async def fake_upload(media_id, url, media_type):
            uploaded.append((media_id, url, media_type))
            return types.InputRichFilePhoto(media_id, types.InputPhoto(1, 2, b"ref"))

        manager._upload_url_as_rich_file = fake_upload

        rich_text, rich_files = await manager._normalize_rich_media_for_form(
            {"hero": "https://example.com/photo.jpg"},
            rich_text='<a href="tg://media?id=hero">Фото</a>',
        )

        assert rich_text == '<a href="tg://photo?id=hero">Фото</a>'
        assert uploaded == [("hero", "https://example.com/photo.jpg", "photo")]
        assert isinstance(rich_files[0], types.InputRichFilePhoto)

    @pytest.mark.asyncio
    async def test_rich_form_uploads_local_paths_with_referenced_type(self, tmp_path):
        from telethon.tl import types

        from core.lib.loader.inline import InlineManager

        photo_path = tmp_path / "люблю-члены.jpg"
        video_path = tmp_path / "clip.mp4"
        photo_path.write_bytes(b"not decoded locally")
        video_path.write_bytes(b"not decoded locally")
        calls = []

        class Client:
            async def _file_to_media(self, source, **kwargs):
                calls.append((source, kwargs))
                return None, object(), False

            async def __call__(self, _request):
                _source, flags = calls[-1]
                if flags["force_document"]:
                    return SimpleNamespace(document=types.InputDocument(1, 2, b"ref"))
                return SimpleNamespace(photo=types.InputPhoto(1, 2, b"ref"))

        manager = InlineManager.__new__(InlineManager)
        manager.k = SimpleNamespace(client=Client())

        photo, photo_type = await manager._make_input_rich_file_for_form(
            {"id": "hero", "media": photo_path}, referenced_type="photo"
        )
        video, video_type = await manager._make_input_rich_file_for_form(
            {"id": "clip", "media": str(video_path)}, referenced_type="video"
        )

        assert isinstance(photo, types.InputRichFilePhoto)
        assert photo.id == "hero"
        assert photo_type == "photo"
        assert isinstance(video, types.InputRichFileDocument)
        assert video.id == "clip"
        assert video_type == "video"
        assert calls == [
            (photo_path, {"force_document": False, "supports_streaming": False}),
            (str(video_path), {"force_document": True, "supports_streaming": True}),
        ]

    @pytest.mark.asyncio
    async def test_rich_form_rejects_invalid_local_paths_and_photo_upload_mismatch(
        self, tmp_path
    ):
        from core.lib.loader.inline import InlineManager

        manager = InlineManager.__new__(InlineManager)
        missing = tmp_path / "missing.jpg"
        with pytest.raises(FileNotFoundError, match="does not exist"):
            await manager._make_input_rich_file_for_form({"id": "x", "media": missing})
        with pytest.raises(IsADirectoryError, match="directory"):
            await manager._make_input_rich_file_for_form({"id": "x", "media": tmp_path})

        class MismatchClient:
            async def _file_to_media(self, *_args, **_kwargs):
                return None, object(), False

            async def __call__(self, _request):
                return SimpleNamespace(document=object())

        manager.k = SimpleNamespace(client=MismatchClient())
        photo_path = tmp_path / "photo.jpg"
        photo_path.write_bytes(b"x")
        with pytest.raises(ValueError, match="did not return a photo"):
            await manager._make_input_rich_file_for_form(
                {"id": "hero", "media": photo_path}, referenced_type="photo"
            )

    @pytest.mark.asyncio
    async def test_rich_form_normalizes_local_asset_path_for_photo_reference(
        self, tmp_path
    ):
        from telethon.tl import types

        from core.lib.loader.inline import InlineManager

        photo_path = tmp_path / "люблю-члены.jpg"
        photo_path.write_bytes(b"x")
        manager = InlineManager.__new__(InlineManager)
        uploaded = []

        async def fake_upload(media_id, source, media_type):
            uploaded.append((media_id, source, media_type))
            return types.InputRichFilePhoto(media_id, types.InputPhoto(1, 2, b"ref"))

        manager._upload_source_as_rich_file = fake_upload
        rich_text, files = await manager._normalize_rich_media_for_form(
            {"hero": photo_path},
            rich_text='<a href="tg://photo?id=hero">Open local photo</a>',
        )

        assert rich_text == '<a href="tg://photo?id=hero">Open local photo</a>'
        assert uploaded == [("hero", photo_path, "photo")]
        assert isinstance(files[0], types.InputRichFilePhoto)

    def test_rich_form_normalizes_rich_media_specs_and_preserves_files(self):
        from telethon.tl import types

        from core.lib.loader.inline import InlineManager

        existing = object()
        photo = types.InputPhoto(1, 2, b"ref")
        document = types.InputDocument(3, 4, b"doc")

        rich_files = InlineManager._normalize_rich_media(
            [
                {"id": "hero", "photo": photo},
                ("doc", document),
            ],
            files=[existing],
        )

        assert rich_files[0] is existing
        assert isinstance(rich_files[1], types.InputRichFilePhoto)
        assert rich_files[1].id == "hero"
        assert isinstance(rich_files[2], types.InputRichFileDocument)
        assert rich_files[2].id == "doc"

    def test_rich_form_rejects_unknown_rich_media(self):
        from core.lib.loader.inline import InlineManager

        with pytest.raises(TypeError):
            InlineManager._normalize_rich_media({"bad": object()})
