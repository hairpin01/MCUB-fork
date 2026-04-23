# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

import time
from unittest.mock import MagicMock

from core.lib.base.permissions import CallbackPermissionManager


class TestCallbackPermissionManager:
    """Test CallbackPermissionManager"""

    def test_allow_single_user(self):
        mgr = CallbackPermissionManager()
        mgr.allow(123456, "test_pattern", 60)

        assert mgr.is_allowed(123456, "test_pattern")
        assert not mgr.is_allowed(999999, "test_pattern")

    def test_allow_multiple_users(self):
        mgr = CallbackPermissionManager()
        mgr.allow(123, "menu_", 60)
        mgr.allow(456, "menu_", 60)

        assert mgr.is_allowed(123, "menu_settings")
        assert mgr.is_allowed(456, "menu_main")
        assert not mgr.is_allowed(789, "menu_")

    def test_is_allowed_prefix_matching(self):
        mgr = CallbackPermissionManager()
        mgr.allow(123456, "menu_", 60)

        assert mgr.is_allowed(123456, "menu_settings")
        assert mgr.is_allowed(123456, "menu_main")
        assert not mgr.is_allowed(123456, "other")

    def test_prohibit_specific_pattern(self):
        mgr = CallbackPermissionManager()
        mgr.allow(123456, "menu_", 60)
        mgr.allow(123456, "settings_", 60)

        mgr.prohibit(123456, "menu_")

        assert not mgr.is_allowed(123456, "menu_settings")
        assert mgr.is_allowed(123456, "settings_edit")

    def test_prohibit_all_for_user(self):
        mgr = CallbackPermissionManager()
        mgr.allow(123456, "menu_", 60)
        mgr.allow(123456, "settings_", 60)

        mgr.prohibit(123456)

        assert not mgr.is_allowed(123456, "menu_")
        assert not mgr.is_allowed(123456, "settings_")

    def test_cleanup_expired(self):
        mgr = CallbackPermissionManager()
        mgr.allow(123456, "short_", 0)

        mgr.cleanup()

        assert not mgr.is_allowed(123456, "short_")

    def test_get_expiry_time(self):
        mgr = CallbackPermissionManager()
        mgr.allow(123456, "pattern_", 60)

        expiry = mgr.get_expiry_time(123456, "pattern_")

        assert expiry is not None
        assert expiry > time.time()

    def test_remaining_time(self):
        mgr = CallbackPermissionManager()
        mgr.allow(123456, "pattern_", 60)

        remaining = mgr.remaining_time(123456, "pattern_")

        assert remaining is not None
        assert 55 <= remaining <= 60

    def test_bytes_pattern(self):
        mgr = CallbackPermissionManager()
        mgr.allow(123456, b"test_", 60)

        assert mgr.is_allowed(123456, "test_data")

    def test_no_permissions_returns_false(self):
        mgr = CallbackPermissionManager()

        assert not mgr.is_allowed(123456, "anything")

    def test_expired_permission_returns_false(self):
        mgr = CallbackPermissionManager()
        mgr.allow(123456, "pattern_", 0)
        time.sleep(0.01)

        assert not mgr.is_allowed(123456, "pattern_")


class TestAllowUserParameter:
    """Test allow_user parameter in _make_callback_button"""

    def test_make_callback_button_accepts_allow_user_int(self):
        from core.lib.loader.module_base import ModuleBase

        mock_kernel = MagicMock()
        mock_kernel.inline_callback_map = {}
        mock_kernel.callback_permissions = CallbackPermissionManager()
        mock_kernel._inline_cb_lock = MagicMock()
        mock_kernel._inline_cb_lock.__enter__ = MagicMock(return_value=None)
        mock_kernel._inline_cb_lock.__exit__ = MagicMock(return_value=None)

        module = ModuleBase.__new__(ModuleBase)
        module.kernel = mock_kernel
        module._callback_tokens = []

        async def handler(event):
            pass

        with MagicMock() as lock_cm:
            lock_cm.__enter__ = MagicMock()
            lock_cm.__exit__ = MagicMock()
            mock_kernel._inline_cb_lock = lock_cm

            module._make_callback_button(
                "Click",
                handler,
                allow_user=123456,
                allow_ttl=60,
            )

            assert 123456 in mock_kernel.callback_permissions.permissions

    def test_make_callback_button_accepts_allow_user_list(self):
        from core.lib.loader.module_base import ModuleBase

        mock_kernel = MagicMock()
        mock_kernel.inline_callback_map = {}
        mock_kernel.callback_permissions = CallbackPermissionManager()
        mock_kernel._inline_cb_lock = MagicMock()
        mock_kernel._inline_cb_lock.__enter__ = MagicMock(return_value=None)
        mock_kernel._inline_cb_lock.__exit__ = MagicMock(return_value=None)

        module = ModuleBase.__new__(ModuleBase)
        module.kernel = mock_kernel
        module._callback_tokens = []

        async def handler(event):
            pass

        with MagicMock() as lock_cm:
            lock_cm.__enter__ = MagicMock()
            lock_cm.__exit__ = MagicMock()
            mock_kernel._inline_cb_lock = lock_cm

            module._make_callback_button(
                "Click",
                handler,
                allow_user=[123, 456],
                allow_ttl=30,
            )

            assert 123 in mock_kernel.callback_permissions.permissions
            assert 456 in mock_kernel.callback_permissions.permissions

    def test_make_callback_button_accepts_allow_user_all(self):
        from core.lib.loader.module_base import ModuleBase

        mock_kernel = MagicMock()
        mock_kernel.inline_callback_map = {}
        mock_kernel.callback_permissions = CallbackPermissionManager()
        mock_kernel._inline_cb_lock = MagicMock()
        mock_kernel._inline_cb_lock.__enter__ = MagicMock(return_value=None)
        mock_kernel._inline_cb_lock.__exit__ = MagicMock(return_value=None)

        module = ModuleBase.__new__(ModuleBase)
        module.kernel = mock_kernel
        module._callback_tokens = []

        async def handler(event):
            pass

        with MagicMock() as lock_cm:
            lock_cm.__enter__ = MagicMock()
            lock_cm.__exit__ = MagicMock()
            mock_kernel._inline_cb_lock = lock_cm

            module._make_callback_button(
                "Click",
                handler,
                allow_user="all",
                allow_ttl=100,
            )

            cb_map = mock_kernel.inline_callback_map
            found = False
            for _key, val in cb_map.items():
                if val.get("allow_all"):
                    found = True
                    break

            assert found, "allow_all should be set in callback map"


class TestInlineButtonFactory:
    """Test ButtonFactory.inline with allow_user"""

    def test_inline_button_accepts_allow_user_parameters(self):
        from core.lib.loader.module_base import ModuleBase

        mock_kernel = MagicMock()
        mock_kernel.inline_callback_map = {}
        mock_kernel.callback_permissions = CallbackPermissionManager()
        mock_kernel._inline_cb_lock = MagicMock()

        module = ModuleBase.__new__(ModuleBase)
        module.kernel = mock_kernel
        module._callback_tokens = []

        async def handler(event):
            pass

        factory = ModuleBase.ButtonFactory(module)

        mock_wrap = MagicMock()
        factory._outer._make_callback_button = mock_wrap

        factory.inline("Click", handler, allow_user=123456, allow_ttl=60)

        mock_wrap.assert_called_once()
        kwargs = mock_wrap.call_args.kwargs
        assert kwargs.get("allow_user") == 123456
        assert kwargs.get("allow_ttl") == 60

    def test_inline_button_accepts_allow_user_all(self):
        from core.lib.loader.module_base import ModuleBase

        mock_kernel = MagicMock()
        mock_kernel.inline_callback_map = {}
        mock_kernel.callback_permissions = CallbackPermissionManager()
        mock_kernel._inline_cb_lock = MagicMock()

        module = ModuleBase.__new__(ModuleBase)
        module.kernel = mock_kernel
        module._callback_tokens = []

        async def handler(event):
            pass

        factory = ModuleBase.ButtonFactory(module)

        mock_wrap = MagicMock()
        factory._outer._make_callback_button = mock_wrap

        factory.inline("Click", handler, allow_user="all", allow_ttl=100)

        mock_wrap.assert_called_once()
        kwargs = mock_wrap.call_args.kwargs
        assert kwargs.get("allow_user") == "all"
        assert kwargs.get("allow_ttl") == 100
