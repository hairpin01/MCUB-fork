# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""Tests for callback permission manager."""

import re
import pytest
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


class TestPermissionManagerEdgeCases:
    """Test edge cases for permission manager"""

    def test_allow_without_duration(self, monkeypatch):
        now = 8000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "noprefix_")

        assert manager.is_allowed(1, "noprefix_test") is True

    def test_multiple_users_same_permission(self, monkeypatch):
        now = 9000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "shared_", duration_seconds=60)
        manager.allow(2, "shared_", duration_seconds=60)
        manager.allow(3, "shared_", duration_seconds=60)

        assert manager.is_allowed(1, "shared_action") is True
        assert manager.is_allowed(2, "shared_action") is True
        assert manager.is_allowed(3, "shared_action") is True
        assert manager.is_allowed(4, "shared_action") is False

    def test_multiple_patterns_per_user(self, monkeypatch):
        now = 10000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "admin_", duration_seconds=60)
        manager.allow(1, "mod_", duration_seconds=60)
        manager.allow(1, "user_", duration_seconds=60)

        perms = manager.get_user_permissions(1)
        assert "admin_" in perms
        assert "mod_" in perms
        assert "user_" in perms

    def test_prohibit_nonexistent_permission(self, monkeypatch):
        now = 11000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.prohibit(1, "nonexistent_")

        assert manager.get_user_permissions(1) == {}

    def test_is_allowed_nonexistent_user(self, monkeypatch):
        now = 12000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "test_", duration_seconds=60)

        assert manager.is_allowed(999, "test_action") is False

    def test_regex_pattern_matching(self, monkeypatch):
        now = 13000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "action_", duration_seconds=60)

        assert manager.is_allowed(1, "action_1") is True
        assert manager.is_allowed(1, "action_123") is True
        assert manager.is_allowed(1, "other") is False

    def test_remaining_time_at_boundary(self, monkeypatch):
        now = 14000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "test_", duration_seconds=10)

        now = 14015.0
        result = manager.remaining_time(1, "test_")
        assert result is None or result <= 0

    def test_cleanup_empty_manager(self, monkeypatch):
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: 15000.0)

        manager = CallbackPermissionManager()
        removed = manager.cleanup()
        assert removed == 0

    def test_get_all_permissions_empty(self, monkeypatch):
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: 16000.0)

        manager = CallbackPermissionManager()
        assert manager.get_all_permissions() == {}

    def test_expiry_time_nonexistent(self, monkeypatch):
        now = 17000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "test_", duration_seconds=60)

        assert manager.get_expiry_time(999, "nonexistent_") is None

    def test_clear_all_when_empty(self, monkeypatch):
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: 18000.0)

        manager = CallbackPermissionManager()
        manager.clear_all()
        assert manager.get_all_permissions() == {}

    def test_partial_expiration(self, monkeypatch):
        now = 19000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "expire_1", duration_seconds=5)
        manager.allow(1, "expire_2", duration_seconds=10)
        manager.allow(1, "expire_3", duration_seconds=15)

        now = 19006.0
        removed = manager.cleanup()

        assert removed == 1
        assert manager.is_allowed(1, "expire_1_action") is False
        assert manager.is_allowed(1, "expire_2_action") is True
        assert manager.is_allowed(1, "expire_3_action") is True

    def test_allow_updates_existing_permission(self, monkeypatch):
        now = 20000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "test_", duration_seconds=30)

        now = 20010.0
        manager.allow(1, "test_", duration_seconds=60)

        remaining = manager.remaining_time(1, "test_")
        assert remaining >= 59
        assert remaining <= 60

    def test_wildcard_pattern(self, monkeypatch):
        now = 21000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "any", duration_seconds=60)

        assert manager.is_allowed(1, "anything") is True


class TestPermissionManagerConcurrency:
    """Test concurrent access patterns"""

    def test_multiple_allow_calls_same_user(self, monkeypatch):
        now = 22000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()

        for i in range(10):
            manager.allow(1, f"perm_{i}_", duration_seconds=60)

        perms = manager.get_user_permissions(1)
        assert len(perms) == 10

    def test_allow_prohibit_cycle(self, monkeypatch):
        now = 23000.0
        monkeypatch.setattr("core.lib.base.permissions.time.time", lambda: now)

        manager = CallbackPermissionManager()
        manager.allow(1, "cycle_", duration_seconds=60)

        assert manager.is_allowed(1, "cycle_action") is True

        manager.prohibit(1, "cycle_")
        assert manager.is_allowed(1, "cycle_action") is False

        manager.allow(1, "cycle_", duration_seconds=60)
        assert manager.is_allowed(1, "cycle_action") is True
