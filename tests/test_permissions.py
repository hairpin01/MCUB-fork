"""Tests for callback permission manager."""

import re

from core.lib.base.permissions import CallbackPermissionManager


class TestCallbackPermissionManager:
    def test_to_str_supports_multiple_input_types(self):
        manager = CallbackPermissionManager()

        assert manager._to_str("menu_") == "menu_"
        assert manager._to_str(b"menu_") == "menu_"
        assert manager._to_str(re.compile(r"menu_\d+")) == r"menu_\d+"
        assert manager._to_str(123) == "123"

    def test_allow_and_is_allowed_prefix_matching(self, monkeypatch):
        now = 1000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "menu_", duration_seconds=60)

        assert manager.is_allowed(1, "menu_open") is True
        assert manager.is_allowed(1, "settings_open") is False
        assert manager.is_allowed(999, "menu_open") is False

    def test_is_allowed_respects_expiration(self, monkeypatch):
        now = 2000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "menu_", duration_seconds=10)

        now = 2015.0
        assert manager.is_allowed(1, "menu_open") is False

    def test_prohibit_specific_pattern_and_all_user_permissions(self, monkeypatch):
        now = 3000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "menu_", duration_seconds=60)
        manager.allow(1, "settings_", duration_seconds=60)

        manager.prohibit(1, "menu_")
        assert manager.is_allowed(1, "menu_open") is False
        assert manager.is_allowed(1, "settings_open") is True

        manager.prohibit(1)
        assert manager.get_user_permissions(1) == {}

    def test_cleanup_removes_only_expired_permissions(self, monkeypatch):
        now = 4000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "short_", duration_seconds=10)
        manager.allow(1, "long_", duration_seconds=100)
        manager.allow(2, "short_", duration_seconds=10)

        now = 4011.0
        removed = manager.cleanup()

        assert removed == 2
        assert manager.is_allowed(1, "short_action") is False
        assert manager.is_allowed(1, "long_action") is True
        assert manager.get_user_permissions(2) == {}

    def test_get_user_permissions_returns_only_active(self, monkeypatch):
        now = 5000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "active_", duration_seconds=60)
        manager.allow(1, "expired_", duration_seconds=5)

        now = 5006.0
        result = manager.get_user_permissions(1)

        assert "active_" in result
        assert "expired_" not in result

    def test_get_expiry_time_and_remaining_time(self, monkeypatch):
        now = 6000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "menu_", duration_seconds=90)

        expiry = manager.get_expiry_time(1, "menu_")
        assert expiry == 6090.0
        assert manager.remaining_time(1, "menu_") == 90.0

        now = 6100.0
        assert manager.get_expiry_time(1, "menu_") is None
        assert manager.remaining_time(1, "menu_") is None

    def test_clear_all_and_get_all_permissions_copy(self, monkeypatch):
        now = 7000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "menu_", duration_seconds=60)

        snapshot = manager.get_all_permissions()
        snapshot[1]["menu_"] = 1.0

        original = manager.get_all_permissions()
        assert original[1]["menu_"] == 7060.0

        manager.clear_all()
        assert manager.get_all_permissions() == {}
