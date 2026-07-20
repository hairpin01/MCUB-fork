# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""
Tests for inline features
"""

import json
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
    async def test_edit_rich_falls_back_to_edit_message_for_unsupported_peer(self):
        from core.lib.types import InlineMessage

        client = _RichInlineClient(fail_rich=True)
        kernel = SimpleNamespace(client=client, bot_client=None)
        message = InlineMessage(_inline_event(), kernel=kernel)

        result = await message.edit_rich("<b>hello</b>")

        assert result is message
        assert len(client.requests) == 1
        assert len(client.edit_message_calls) == 1
        args, kwargs = client.edit_message_calls[0]
        assert args[1] == "<b>hello</b>"
        assert kwargs["parse_mode"] == "html"
