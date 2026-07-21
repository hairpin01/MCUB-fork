# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""Tests for Heroku/Hikka compatibility layer."""

import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestImportsAndConstants:
    """Verify all expected exports exist."""

    def test_import_hikka_compat(self):
        from core.lib.loader import hikka_compat

        assert hikka_compat

    def test_import_security_constants(self):
        from core.lib.loader.hikka_compat.security import (
            ALL,
            EVERYONE,
            GROUP_ADMIN_ADD_ADMINS,
            GROUP_ADMIN_ANY,
            GROUP_ADMIN_BAN_USERS,
            OWNER,
        )

        assert OWNER == 1
        assert EVERYONE == 1 << 13
        assert ALL == (1 << 13) - 1
        assert GROUP_ADMIN_ANY & GROUP_ADMIN_ADD_ADMINS
        assert GROUP_ADMIN_ANY & GROUP_ADMIN_BAN_USERS

    def test_import_security_decorators(self):
        from core.lib.loader.hikka_compat.security import (
            owner,
            pm,
            unrestricted,
        )

        async def dummy():
            pass

        decorated = owner(dummy)
        assert decorated.security & 1

        unrestricted_d = unrestricted(dummy)
        assert unrestricted_d.security & (1 << 13) - 1

        pm_d = pm(dummy)
        assert pm_d.security & (1 << 12)

    def test_import_proxies(self):
        from core.lib.loader.hikka_compat.proxies import (
            PointerDict,
            PointerList,
            SafeAllModulesProxy,
            SafeClientProxy,
            SafeDatabaseProxy,
            SafeInlineProxy,
        )

        assert SafeClientProxy
        assert SafeDatabaseProxy
        assert SafeInlineProxy
        assert SafeAllModulesProxy
        assert PointerList
        assert PointerDict

    def test_import_inline_types(self):
        from core.lib.loader.hikka_compat import (
            BotInlineCall,
            BotMessage,
            InlineCall,
            InlineMessage,
            InlineQuery,
            InlineResults,
            InlineUnit,
        )

        assert InlineMessage
        assert InlineCall
        assert BotInlineCall
        assert BotMessage
        assert InlineQuery
        assert InlineResults
        assert InlineUnit

    def test_import_runtime(self):
        from core.lib.loader.hikka_compat import DbProxy, InlineProxy, Module

        assert DbProxy
        assert InlineProxy
        assert Module


class TestSecurityDecorators:
    """Test security decorators set correct bitmasks."""

    @pytest.fixture
    def dummy(self):
        async def fn():
            pass

        return fn

    def test_owner(self, dummy):
        from core.lib.loader.hikka_compat.security import owner

        result = owner(dummy)
        assert result.security & 1

    def test_group_admin(self, dummy):
        from core.lib.loader.hikka_compat.security import group_admin

        result = group_admin(dummy)
        assert result.security & (1 << 10)

    def test_stack_decorators(self, dummy):
        from core.lib.loader.hikka_compat.security import group_admin, owner

        result = owner(group_admin(dummy))
        assert result.security & 1
        assert result.security & (1 << 10)

    def test_unrestricted_allows_everything(self, dummy):
        from core.lib.loader.hikka_compat.security import ALL, unrestricted

        result = unrestricted(dummy)
        assert result.security & ALL == ALL


class TestSecurityChecker:
    """Test SecurityChecker runtime permission validation."""

    @pytest.fixture
    def owner_id(self):
        return 12345

    @pytest.fixture
    def sudo_ids(self):
        return [67890, 11111]

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.get.return_value = {}
        return db

    @pytest.fixture
    def checker(self, owner_id, mock_db):
        from core.lib.loader.hikka_compat.security import SecurityChecker

        return SecurityChecker(owner_id=owner_id, db=mock_db)

    def test_owner_is_owner(self, checker, owner_id):
        from core.lib.loader.hikka_compat.security import OWNER

        flags = checker.get_flags(owner_id)
        assert flags & OWNER

    def test_sudo_has_sudo_flag(self, checker, owner_id, sudo_ids):
        from core.lib.loader.hikka_compat.security import SUDO

        checker.sudo = sudo_ids
        for sid in sudo_ids:
            assert checker.get_flags(sid) & SUDO
        assert checker.get_flags(owner_id) & SUDO

    def test_unknown_user_no_flags(self, checker):
        assert checker.get_flags(99999) == 0

    def test_all_users_includes_owner_and_sudo(self, checker, owner_id, sudo_ids):
        checker.sudo = sudo_ids
        users = checker.all_users
        assert owner_id in users
        for sid in sudo_ids:
            assert sid in users

    def test_owner_check_passes(self, checker, owner_id):
        async def cmd():
            pass

        from core.lib.loader.hikka_compat.security import owner

        owner(cmd)
        event = MagicMock()
        event.from_user.id = owner_id
        event.chat_id = owner_id

        import asyncio

        result = asyncio.run(checker.check(cmd, event))
        assert result is True

    def test_unknown_user_check_fails_for_owner_only(self, checker):
        async def cmd():
            pass

        from core.lib.loader.hikka_compat.security import owner

        owner(cmd)
        event = MagicMock()
        event.from_user.id = 99999
        event.chat_id = 99999

        import asyncio

        result = asyncio.run(checker.check(cmd, event))
        assert result is False

    def test_no_security_always_passes(self, checker):
        async def cmd():
            pass

        event = MagicMock()
        event.from_user.id = 99999
        import asyncio

        result = asyncio.run(checker.check(cmd, event))
        assert result is True

    def test_load_from_db(self):
        from core.lib.loader.hikka_compat.security import SecurityChecker

        db = MagicMock()
        db.get.return_value = {"owner": 42, "sudo": [1, 2], "support": [3]}
        checker = SecurityChecker(owner_id=999, db=db)
        assert checker.owner == 42
        assert checker.sudo == [1, 2]
        assert checker.support == [3]


class TestPointerList:
    """Test PointerList - list auto-persisted to DB."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.get.return_value = ["a", "b", "c"]
        return db

    def test_init_from_db(self, mock_db):
        from core.lib.loader.hikka_compat.proxies import PointerList

        pl = PointerList(mock_db, "mod", "key")
        assert list(pl) == ["a", "b", "c"]
        mock_db.get.assert_called_with("mod", "key", None)

    def test_append_saves(self, mock_db):
        from core.lib.loader.hikka_compat.proxies import PointerList

        pl = PointerList(mock_db, "mod", "key")
        pl.append("d")
        assert "d" in pl
        mock_db.set.assert_called_with("mod", "key", ["a", "b", "c", "d"])

    def test_remove_saves(self, mock_db):
        from core.lib.loader.hikka_compat.proxies import PointerList

        pl = PointerList(mock_db, "mod", "key")
        pl.remove("b")
        mock_db.set.assert_called_with("mod", "key", ["a", "c"])

    def test_pop_saves(self, mock_db):
        from core.lib.loader.hikka_compat.proxies import PointerList

        pl = PointerList(mock_db, "mod", "key")
        val = pl.pop(0)
        assert val == "a"
        mock_db.set.assert_called_with("mod", "key", ["b", "c"])

    def test_clear_saves(self, mock_db):
        from core.lib.loader.hikka_compat.proxies import PointerList

        pl = PointerList(mock_db, "mod", "key")
        pl.clear()
        mock_db.set.assert_called_with("mod", "key", [])

    def test_data_property(self, mock_db):
        from core.lib.loader.hikka_compat.proxies import PointerList

        pl = PointerList(mock_db, "mod", "key")
        assert pl.data == ["a", "b", "c"]
        pl.data = ["x", "y"]
        assert list(pl) == ["x", "y"]
        mock_db.set.assert_called_with("mod", "key", ["x", "y"])

    def test_default_when_db_empty(self):
        from core.lib.loader.hikka_compat.proxies import PointerList

        db = MagicMock()

        def _db_get(module, key, default=None):
            return default

        db.get.side_effect = _db_get
        pl = PointerList(db, "mod", "key", default=["d"])
        assert list(pl) == ["d"]


class TestPointerDict:
    """Test PointerDict - dict auto-persisted to DB."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.get.return_value = {"a": 1, "b": 2}
        return db

    def test_init_from_db(self, mock_db):
        from core.lib.loader.hikka_compat.proxies import PointerDict

        pd = PointerDict(mock_db, "mod", "key")
        assert pd["a"] == 1
        assert pd["b"] == 2

    def test_setitem_saves(self, mock_db):
        from core.lib.loader.hikka_compat.proxies import PointerDict

        pd = PointerDict(mock_db, "mod", "key")
        pd["c"] = 3
        mock_db.set.assert_called_with("mod", "key", {"a": 1, "b": 2, "c": 3})

    def test_delitem_saves(self, mock_db):
        from core.lib.loader.hikka_compat.proxies import PointerDict

        pd = PointerDict(mock_db, "mod", "key")
        del pd["a"]
        mock_db.set.assert_called_with("mod", "key", {"b": 2})

    def test_update_saves(self, mock_db):
        from core.lib.loader.hikka_compat.proxies import PointerDict

        pd = PointerDict(mock_db, "mod", "key")
        pd.update({"c": 3, "d": 4})
        mock_db.set.assert_called_with("mod", "key", {"a": 1, "b": 2, "c": 3, "d": 4})


class TestSafeDatabaseProxy:
    """Test SafeDatabaseProxy wraps DB with module namespace."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.get.return_value = "val42"
        return db

    def test_get_uses_module_namespace(self, mock_db):
        from core.lib.loader.hikka_compat.proxies import SafeDatabaseProxy

        sdp = SafeDatabaseProxy(mock_db, "MyModule")
        result = sdp.get("mykey")
        assert result == "val42"
        mock_db.get.assert_called_with("MyModule", "mykey", None)

    def test_set_uses_module_namespace(self, mock_db):
        from core.lib.loader.hikka_compat.proxies import SafeDatabaseProxy

        sdp = SafeDatabaseProxy(mock_db, "MyModule")
        sdp.set("mykey", "newval")
        mock_db.set.assert_called_with("MyModule", "mykey", "newval")

    def test_dict_access(self, mock_db):
        from core.lib.loader.hikka_compat.proxies import SafeDatabaseProxy

        sdp = SafeDatabaseProxy(mock_db, "M")
        assert sdp["mykey"] == "val42"
        sdp["k2"] = "v2"
        mock_db.set.assert_called_with("M", "k2", "v2")

    def test_pointer_list_creation(self, mock_db):
        from core.lib.loader.hikka_compat.proxies import (
            PointerList,
            SafeDatabaseProxy,
        )

        sdp = SafeDatabaseProxy(mock_db, "M")
        pl = sdp.PointerList("lst", default=[1, 2])
        assert isinstance(pl, PointerList)

    def test_pointer_dict_creation(self, mock_db):
        from core.lib.loader.hikka_compat.proxies import (
            PointerDict,
            SafeDatabaseProxy,
        )

        sdp = SafeDatabaseProxy(mock_db, "M")
        pd = sdp.PointerDict("dct", default={"a": 1})
        assert isinstance(pd, PointerDict)


class TestSafeClientProxy:
    """Test SafeClientProxy restricts unsafe operations."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.tg_id = 12345
        client.send_message = AsyncMock()
        client.get_entity = AsyncMock()
        client.get_me = AsyncMock()
        return client

    def test_allowed_methods_pass(self, mock_client):
        from core.lib.loader.hikka_compat.proxies import SafeClientProxy

        scp = SafeClientProxy(mock_client)
        assert scp.send_message == mock_client.send_message
        assert scp.get_entity == mock_client.get_entity

    def test_disallowed_method_raises(self, mock_client):
        from core.lib.loader.hikka_compat.proxies import SafeClientProxy

        scp = SafeClientProxy(mock_client)
        with pytest.raises(AttributeError):
            _ = scp.invite_to_channel

    def test_tg_id_property(self, mock_client):
        from core.lib.loader.hikka_compat.proxies import SafeClientProxy

        scp = SafeClientProxy(mock_client)
        assert scp.tg_id == 12345

    def test_private_attr_raises(self, mock_client):
        from core.lib.loader.hikka_compat.proxies import SafeClientProxy

        scp = SafeClientProxy(mock_client)
        with pytest.raises(AttributeError):
            _ = scp._private_stuff


class TestSafeInlineProxy:
    """Test SafeInlineProxy delegates to InlineProxy."""

    @pytest.fixture
    def mock_inline(self):
        inline = MagicMock()
        inline.form = AsyncMock(return_value=True)
        inline.gallery = AsyncMock(return_value=True)
        inline.list = AsyncMock(return_value=True)
        inline.bot_username = "test_bot"
        return inline

    def test_form_delegation(self, mock_inline):
        from core.lib.loader.hikka_compat.proxies import SafeInlineProxy

        sip = SafeInlineProxy(mock_inline, "M")
        import asyncio

        result = asyncio.run(sip.form("text", 123))
        assert result is True
        mock_inline.form.assert_called_once()

    def test_bot_username(self, mock_inline):
        from core.lib.loader.hikka_compat.proxies import SafeInlineProxy

        sip = SafeInlineProxy(mock_inline, "M")
        assert sip.bot_username == "test_bot"


class TestInlineProxyFSM:
    """Test InlineProxy FSM (Finite State Machine)."""

    @pytest.fixture
    def proxy(self):
        from core.lib.loader.hikka_compat.runtime import InlineProxy

        kernel = MagicMock()
        kernel._hikka_compat_inline_state = {}
        return InlineProxy(kernel)

    def test_set_fsm_state(self, proxy):
        assert proxy.set_fsm_state(12345, "waiting_input") is True
        assert proxy.fsm.get("12345") == "waiting_input"

    def test_get_fsm_state(self, proxy):
        proxy.set_fsm_state(12345, "waiting")
        assert proxy.get_fsm_state(12345) == "waiting"

    def test_clear_fsm_state(self, proxy):
        proxy.set_fsm_state(12345, "waiting")
        proxy.set_fsm_state(12345, False)
        assert proxy.get_fsm_state(12345) is False

    def test_get_fsm_state_missing(self, proxy):
        assert proxy.get_fsm_state(99999) is False

    def test_invalid_user_type(self, proxy):
        assert proxy.set_fsm_state(None, "test") is False

    def test_ss_alias(self, proxy):
        assert proxy.ss(123, "state") is True
        assert proxy.gs(123) == "state"


class TestInlineMessage:
    """Test InlineMessage API."""

    @pytest.fixture
    def inline_proxy(self):
        from core.lib.loader.hikka_compat.runtime import InlineProxy

        kernel = MagicMock()
        kernel._hikka_compat_inline_state = {}
        return InlineProxy(kernel)

    def test_inline_message_create(self, inline_proxy):
        from core.lib.loader.hikka_compat.inline_types import InlineMessage

        msg = InlineMessage(
            inline_message_id="test_id",
            unit_id="unit_123",
            inline_proxy=inline_proxy,
            chat_id=12345,
            message_id=678,
        )
        assert msg.inline_message_id == "test_id"
        assert msg.unit_id == "unit_123"
        assert msg.chat_id == 12345
        assert msg.message_id == 678

    def test_inline_message_edit_default_parse_mode(self, inline_proxy):
        from core.lib.loader.hikka_compat.inline_types import InlineMessage

        msg = InlineMessage(
            inline_message_id="test_id",
            unit_id="unit_123",
            inline_proxy=inline_proxy,
        )
        assert msg.default_parse_mode == "html"

    def test_inline_message_delete_returns_false_no_manager(self, inline_proxy):
        from core.lib.loader.hikka_compat.inline_types import InlineMessage

        msg = InlineMessage(
            inline_message_id="test_id",
            unit_id="unit_123",
            inline_proxy=inline_proxy,
        )
        import asyncio

        result = asyncio.run(msg.delete())
        assert result is False

    def test_inline_message_unload_returns_false_no_manager(self, inline_proxy):
        from core.lib.loader.hikka_compat.inline_types import InlineMessage

        msg = InlineMessage(
            inline_message_id="test_id",
            unit_id="unit_123",
            inline_proxy=inline_proxy,
        )
        import asyncio

        result = asyncio.run(msg.unload())
        assert result is False


class TestInlineCall:
    """Test InlineCall (callback handler) API."""

    @pytest.fixture
    def inline_proxy(self):
        from core.lib.loader.hikka_compat.runtime import InlineProxy

        kernel = MagicMock()
        kernel._hikka_compat_inline_state = {}
        return InlineProxy(kernel)

    def test_inline_call_create(self, inline_proxy):
        from core.lib.loader.hikka_compat.inline_types import InlineCall

        call = InlineCall(
            call_data="btn_data",
            unit_id="unit_1",
            inline_proxy=inline_proxy,
            from_user_id=12345,
        )
        assert call.data == "btn_data"
        assert call.unit_id == "unit_1"
        assert call.from_user.id == 12345

    def test_inline_call_answer_no_original(self, inline_proxy):
        from core.lib.loader.hikka_compat.inline_types import InlineCall

        call = InlineCall(
            call_data="data",
            unit_id="u1",
            inline_proxy=inline_proxy,
        )
        import asyncio

        result = asyncio.run(call.answer("ok"))
        assert result is None
        assert call._answered is True

    def test_inline_call_answer_callback(self, inline_proxy):
        from core.lib.loader.hikka_compat.inline_types import InlineCall

        mock_orig = MagicMock()
        mock_orig.answer = AsyncMock()

        call = InlineCall(
            call_data="data",
            unit_id="u1",
            inline_proxy=inline_proxy,
            original_call=mock_orig,
        )
        import asyncio

        asyncio.run(call.answer("ok", show_alert=True))
        mock_orig.answer.assert_called_once_with(text="ok", show_alert=True, url=None)

    def test_inline_call_edit(self, inline_proxy):
        from core.lib.loader.hikka_compat.inline_types import InlineCall

        call = InlineCall(
            call_data="data",
            unit_id="u1",
            inline_proxy=inline_proxy,
            inline_message_id="mid",
        )
        import asyncio

        result = asyncio.run(call.edit("new text"))
        assert isinstance(result, object)

    def test_inline_call_delete_no_message(self, inline_proxy):
        from core.lib.loader.hikka_compat.inline_types import InlineCall

        call = InlineCall(
            call_data="data",
            unit_id="u1",
            inline_proxy=inline_proxy,
        )
        import asyncio

        result = asyncio.run(call.delete())
        assert result is False

    def test_inline_call_unload(self, inline_proxy):
        from core.lib.loader.hikka_compat.inline_types import InlineCall

        call = InlineCall(
            call_data="data",
            unit_id="u1",
            inline_proxy=inline_proxy,
        )
        import asyncio

        result = asyncio.run(call.unload())
        assert result is False

    def test_answer_callback_property(self, inline_proxy):
        from core.lib.loader.hikka_compat.inline_types import InlineCall

        call = InlineCall(
            call_data="data",
            unit_id="u1",
            inline_proxy=inline_proxy,
        )
        assert callable(call.answer_callback)
        assert callable(call.answer)


class TestBotInlineCall:
    """Test BotInlineCall inherits from InlineCall."""

    def test_bot_inline_call_init(self):
        from core.lib.loader.hikka_compat.inline_types import BotInlineCall

        mock_event = MagicMock()
        mock_event.data = b"btn_data"
        mock_event.inline_message_id = "im_id"
        mock_event.from_user.id = 42

        proxy = MagicMock()
        proxy._custom_map = {}

        call = BotInlineCall(
            event=mock_event,
            inline_proxy=proxy,
            unit_id="u1",
        )
        assert call.data == "btn_data"
        assert call.unit_id == "u1"
        assert call.from_user.id == 42


class TestInlineQuery:
    """Test InlineQuery."""

    def test_inline_query_from_original(self):
        from core.lib.loader.hikka_compat.inline_types import InlineQuery

        mock_orig = MagicMock()
        mock_orig.query_id = "qid"
        mock_orig.query = "test query args"
        mock_orig.offset = "0"
        mock_orig.from_user.id = 42
        mock_orig.from_user.username = "tester"

        iq = InlineQuery(inline_query=mock_orig)
        assert iq.query == "test query args"
        assert iq.args == "query args"
        assert iq.offset == "0"
        assert iq.from_user.id == 42

    def test_inline_query_manual_init(self):
        from core.lib.loader.hikka_compat.inline_types import InlineQuery

        iq = InlineQuery(
            query_id="qid",
            query="test",
            user_id=42,
        )
        assert iq.query_id == "qid"
        assert iq.query == "test"
        assert iq.from_user.id == 42

    def test_inline_query_answer(self):
        from core.lib.loader.hikka_compat.inline_types import InlineQuery

        iq = InlineQuery(query_id="qid", query="t")
        import asyncio

        result = asyncio.run(iq.answer(None))
        assert result is None

    def test_inline_query_e400_shortcut_answers_error_article(self):
        from core.lib.loader.hikka_compat.inline_types import InlineQuery

        mock_event = MagicMock()
        mock_event.answer = AsyncMock()
        iq = InlineQuery(query_id="qid", query="wiki", original_event=mock_event)
        import asyncio

        asyncio.run(iq.e400())

        mock_event.answer.assert_awaited_once()
        results = mock_event.answer.await_args.args[0]
        assert mock_event.answer.await_args.kwargs["cache_time"] == 0
        assert len(results) == 1
        assert results[0]["title"] == "🚫 400"
        assert "Bad request" in results[0]["description"]
        assert results[0]["message"]
        assert results[0]["thumbnail_url"]

    def test_inline_query_e404_and_builder_shortcuts(self):
        from core.lib.loader.hikka_compat.inline_types import InlineQuery

        mock_event = MagicMock()
        mock_event.answer = AsyncMock()
        iq = InlineQuery(
            query_id="qid", query="wiki missing", original_event=mock_event
        )
        import asyncio

        asyncio.run(iq.e404())
        asyncio.run(iq.builder.e400())

        assert mock_event.answer.await_count == 2
        first_results = mock_event.answer.await_args_list[0].args[0]
        second_results = mock_event.answer.await_args_list[1].args[0]
        assert first_results[0]["title"] == "🚫 404"
        assert first_results[0]["description"] == "No results found"
        assert second_results[0]["title"] == "🚫 400"


class TestInlineResults:
    """Test InlineResults."""

    def test_inline_results_empty(self):
        from core.lib.loader.hikka_compat.inline_types import InlineResults

        ir = InlineResults()
        assert len(ir) == 0

    def test_inline_results_add_article(self):
        from core.lib.loader.hikka_compat.inline_types import InlineResults

        ir = InlineResults()
        ir.add_article(
            title="Test",
            description="Desc",
            text="Hello",
            parse_mode="html",
        )
        assert len(ir) == 1


class TestUtils:
    """Test hikka_compat utility functions."""

    def test_rand(self):
        from core.lib.loader.hikka_compat.utils import _Utils

        r1 = _Utils.rand(8)
        r2 = _Utils.rand(8)
        assert len(r1) == 8
        assert len(r2) == 8
        assert r1 != r2  # almost certainly different

    def test_escape_html(self):
        from core.lib.loader.hikka_compat.utils import _Utils

        assert _Utils.escape_html("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"
        assert _Utils.escape_html("normal") == "normal"

    def test_chunks(self):
        from core.lib.loader.hikka_compat.utils import _Utils

        result = _Utils.chunks([1, 2, 3, 4, 5], 2)
        assert result == [[1, 2], [3, 4], [5]]

    def test_check_url_valid(self):
        from core.lib.loader.hikka_compat.utils import _Utils

        assert _Utils.check_url("https://example.com")
        assert _Utils.check_url("http://example.com/path?q=1")

    def test_check_url_invalid(self):
        from core.lib.loader.hikka_compat.utils import _Utils

        assert not _Utils.check_url("not-a-url")
        assert not _Utils.check_url("")

    def test_get_kwargs(self):
        from core.lib.loader.hikka_compat.utils import _Utils

        def sample(a, b, c=3):
            return _Utils.get_kwargs()

        kwargs = sample(1, 2, c=5)
        assert kwargs.get("a") == 1
        assert kwargs.get("b") == 2
        assert kwargs.get("c") == 5

    def test_dnd_mutes_and_archives_peer(self):
        from core.lib.loader.hikka_compat.utils import _Utils

        class FakeClient:
            def __init__(self):
                self.calls = []
                self.edit_folder = AsyncMock()

            async def __call__(self, request):
                self.calls.append(request)
                return object()

        client = FakeClient()
        import asyncio

        assert asyncio.run(_Utils.dnd(client, "@FHeta_robot", archive=True)) is True
        assert len(client.calls) == 1
        client.edit_folder.assert_awaited_once_with("@FHeta_robot", 1)

    def test_get_topic(self):
        from core.lib.loader.hikka_compat.utils import _Utils

        msg = MagicMock()
        msg.reply_to = None
        assert _Utils.get_topic(msg) is None

        msg.reply_to = MagicMock()
        msg.reply_to.reply_to_top_id = 10
        assert _Utils.get_topic(msg) == 10

    def test_get_git_hash(self):
        from core.lib.loader.hikka_compat.utils import _Utils

        result = _Utils.get_git_hash()
        # Should either be a hash string or False (if no git)
        assert result is False or isinstance(result, str)


class TestRuntimeModuleUI:
    """Test pre-ready UI compatibility helpers for Heroku modules."""

    @staticmethod
    def make_kernel():
        return types.SimpleNamespace(
            logger=MagicMock(),
            client=MagicMock(),
            bot_client=None,
            config={},
            aliases={},
            _loader=None,
            loaded_modules={},
            system_modules={},
            command_handlers={},
            command_owners={},
            inline_handlers={},
            inline_handlers_owners={},
            callback_handlers={},
            ADMIN_ID=12345,
            db_manager=None,
            _hikka_compat_allmodules_proxy=None,
            _hikka_compat_inline_proxy=None,
        )

    def test_module_bind_installs_sibling_ui_class(self):
        from core.lib.loader.hikka_compat.runtime import Module

        module_name = "tests.fake_hikka_ui_module"
        fake_module = types.ModuleType(module_name)

        class FakeUI:
            def __init__(self, main):
                self.main = main

            def emoji(self, key: str) -> str:
                return self.main.THEMES[self.main.config["theme"]][key]

        fake_module.FakeUI = FakeUI
        sys.modules[module_name] = fake_module
        try:

            class Fake(Module):
                __module__ = module_name
                strings = {"name": "Fake"}
                config = {"theme": "default"}
                THEMES = {"default": {"search": "🔍"}}

            instance = Fake()
            instance._mcub_bind(self.make_kernel(), module_name="Fake")

            assert isinstance(instance.ui, FakeUI)
            assert instance.ui.emoji("search") == "🔍"
        finally:
            sys.modules.pop(module_name, None)

    def test_module_bind_installs_fallback_ui_emoji(self):
        from core.lib.loader.hikka_compat.runtime import Module

        class ThemeOnly(Module):
            strings = {"name": "ThemeOnly"}
            config = {"theme": "winter"}
            THEMES = {"winter": {"search": "❄️"}}

        instance = ThemeOnly()
        instance._mcub_bind(self.make_kernel(), module_name="ThemeOnly")

        assert instance.ui.emoji("search") == "❄️"
        assert instance.ui.emoji("missing") == ""


class TestRuntimeLibraryCompat:
    """Test Heroku loader.Library compatibility."""

    @staticmethod
    def make_kernel():
        client = MagicMock()
        client.tg_id = 12345
        return types.SimpleNamespace(
            logger=MagicMock(),
            client=client,
            bot_client=None,
            config={},
            aliases={},
            _loader=None,
            loaded_modules={},
            system_modules={},
            command_handlers={},
            command_owners={},
            inline_handlers={},
            inline_handlers_owners={},
            callback_handlers={},
            ADMIN_ID=12345,
            db_manager=None,
            _hikka_compat_allmodules_proxy=None,
            _hikka_compat_inline_proxy=None,
        )

    def test_allmodules_commands_exposes_kernel_aliases(self):
        from core.lib.loader.hikka_compat.runtime import _AllModulesStub

        async def dlm_handler(event):
            return event

        kernel = self.make_kernel()
        kernel.command_handlers["dlm"] = dlm_handler
        kernel.aliases["dlmod"] = "dlm"

        allmodules = _AllModulesStub(kernel)

        assert allmodules.commands["dlmod"] is dlm_handler
        assert allmodules.commands["dlm"] is dlm_handler
        assert not hasattr(allmodules, "_raw_kernel")

    def test_import_lib_supports_heroku_relative_loader_import(self, monkeypatch):
        import asyncio

        from core.lib.loader.hikka_compat import runtime
        from core.lib.loader.hikka_compat.runtime import Module

        code = """
from .. import loader

class RemoteLib(loader.Library):
    async def init(self):
        self.ready = True
"""

        class FakeResponse:
            def raise_for_status(self):
                return None

            async def text(self):
                return code

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakeSession:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            def get(self, url):
                assert url == "https://example.com/remote_lib.py"
                return FakeResponse()

        monkeypatch.setattr(runtime.aiohttp, "ClientSession", FakeSession)

        module = Module()
        module._mcub_bind(self.make_kernel(), module_name="Importer")
        lib = asyncio.run(module.import_lib("https://example.com/remote_lib.py"))

        assert lib.name == "RemoteLib"
        assert lib.ready is True
        assert lib.__class__.__module__.startswith("heroku.libraries.")
        assert module.allmodules.lookup("Remote") is lib

    def test_library_config_and_update_semantics(self):
        import asyncio

        from core.lib.loader.hikka_compat.config import ConfigValue, LibraryConfig
        from core.lib.loader.hikka_compat.runtime import (
            Library,
            _AllModulesStub,
            _register_library_object,
        )

        kernel = self.make_kernel()
        allmodules = _AllModulesStub(kernel)
        allmodules.db.set("ConfigLib", "__config__", {"enabled": False})

        class ConfigLib(Library):
            version = (1, 0, 0)
            strings = {"name": "ConfigLib", "hello": "hi"}
            config = LibraryConfig(
                ConfigValue("enabled", True),
            )

            async def init(self):
                self.initialized = True

            async def on_lib_update(self, new_lib):
                self.updated_to = new_lib.version

        old = asyncio.run(
            _register_library_object(kernel, allmodules, ConfigLib(), "https://old")
        )
        assert old.initialized is True
        assert old.config["enabled"] is False
        assert old.strings("hello") == "hi"
        assert allmodules.lookup("Config") is old

        NewConfigLib = type(
            "ConfigLib",
            (Library,),
            {
                "version": (2, 0, 0),
                "init": lambda self: setattr(self, "initialized", True),
            },
        )

        new = asyncio.run(
            _register_library_object(kernel, allmodules, NewConfigLib(), "https://new")
        )

        assert new is not old
        assert old.updated_to == (2, 0, 0)
        assert allmodules.libraries == [new]

    def test_load_hikka_module_accepts_library_only_file(self, tmp_path):
        import asyncio

        from core.lib.loader.hikka_compat.fake_package import load_hikka_module

        module_path = tmp_path / "shared_lib.py"
        module_path.write_text(
            """
from .. import loader

class SharedLib(loader.Library):
    async def init(self):
        self.ready = True
""",
            encoding="utf-8",
        )

        kernel = self.make_kernel()
        ok, msg, extra = asyncio.run(
            load_hikka_module(kernel, str(module_path), "shared_lib")
        )

        assert ok is True
        assert "SharedLib" in msg
        assert extra["library"] == "SharedLib"
        assert kernel._hikka_compat_libraries[0].ready is True
        assert kernel.loaded_modules == {}


class TestDbProxy:
    """Test DbProxy (heroku-style database access)."""

    @pytest.fixture
    def kernel(self):
        k = MagicMock()
        k.client = MagicMock()
        k.db_manager = MagicMock()
        k.db_manager._resolve_db_file.return_value = ":memory:"
        k.logger = MagicMock()

        async def db_set(module, key, value):
            return True

        k.db_set = db_set
        return k

    def test_db_proxy_get_set(self, kernel):
        from core.lib.loader.hikka_compat.runtime import DbProxy

        db = DbProxy(kernel, "TestModule")
        db.set("mykey", "myvalue")
        assert db.get("mykey") == "myvalue"

    def test_db_proxy_get_default(self, kernel):
        from core.lib.loader.hikka_compat.runtime import DbProxy

        db = DbProxy(kernel, "TestModule")
        assert db.get("nonexistent", "default") == "default"

    def test_db_proxy_dict_access(self, kernel):
        from core.lib.loader.hikka_compat.runtime import DbProxy

        db = DbProxy(kernel, "TestModule")
        db["key1"] = "val1"
        assert db["key1"] == "val1"

    def test_db_proxy_contains(self, kernel):
        from core.lib.loader.hikka_compat.runtime import DbProxy

        db = DbProxy(kernel, "TestModule")
        db["exists"] = "yes"
        assert "exists" in db
        assert "no" not in db

    def test_isolated_namespaces(self, kernel):
        from core.lib.loader.hikka_compat.runtime import DbProxy

        db1 = DbProxy(kernel, "ModuleA")
        db2 = DbProxy(kernel, "ModuleB")
        db1.set("key", "val_a")
        db2.set("key", "val_b")
        assert db1.get("key") == "val_a"
        assert db2.get("key") == "val_b"


class TestInlineProxyFormGalleryList:
    """Test InlineProxy high-level API methods."""

    @pytest.fixture
    def kernel(self):
        k = MagicMock()
        k._hikka_compat_inline_state = {}
        k.logger = MagicMock()
        k._inline = None
        return k

    @pytest.fixture
    def proxy(self, kernel):
        from core.lib.loader.hikka_compat.runtime import InlineProxy

        return InlineProxy(kernel)

    def test_bot_properties(self, proxy):
        bot = proxy.bot
        assert bot is not None
        assert proxy._bot is bot
        assert proxy.bot_id is None
        assert proxy.bot_username is None
