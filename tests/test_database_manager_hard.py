"""
Hard tests for core.lib.base.database.DatabaseManager.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.lib.base.database import DatabaseManager


def _make_kernel() -> MagicMock:
    kernel = MagicMock()
    kernel.logger = MagicMock()
    kernel.config = {}
    return kernel


@pytest.mark.asyncio
class TestDatabaseManagerHard:
    async def test_init_db_uses_default_file(self, monkeypatch):
        kernel = _make_kernel()
        if hasattr(kernel, "API_ID"):
            del kernel.API_ID
        if hasattr(kernel, "API_HASH"):
            del kernel.API_HASH
        db = DatabaseManager(kernel)

        conn = AsyncMock()
        connect = AsyncMock(return_value=conn)
        monkeypatch.setattr("core.lib.base.database.aiosqlite.connect", connect)

        ok = await db.init_db()
        assert ok is True
        connect.assert_awaited_once_with("userbot.db")

    async def test_init_db_uses_kernel_db_file(self, monkeypatch):
        kernel = _make_kernel()
        kernel.DB_FILE = "/tmp/custom.db"
        db = DatabaseManager(kernel)

        conn = AsyncMock()
        connect = AsyncMock(return_value=conn)
        monkeypatch.setattr("core.lib.base.database.aiosqlite.connect", connect)

        ok = await db.init_db()
        assert ok is True
        connect.assert_awaited_once_with("/tmp/custom.db")

    async def test_init_db_uses_config_db_file(self, monkeypatch):
        kernel = _make_kernel()
        kernel.config = {"db_file": "/tmp/config.db"}
        db = DatabaseManager(kernel)

        conn = AsyncMock()
        connect = AsyncMock(return_value=conn)
        monkeypatch.setattr("core.lib.base.database.aiosqlite.connect", connect)

        ok = await db.init_db()
        assert ok is True
        connect.assert_awaited_once_with("/tmp/config.db")

    async def test_methods_raise_runtime_error_when_not_initialized(self):
        db = DatabaseManager(_make_kernel())
        with pytest.raises(RuntimeError):
            await db.db_set("mod", "key", "v")
        with pytest.raises(RuntimeError):
            await db.db_get("mod", "key")
        with pytest.raises(RuntimeError):
            await db.db_delete("mod", "key")
        with pytest.raises(RuntimeError):
            await db.db_query("SELECT 1")

    async def test_db_set_casts_value_to_string(self):
        db = DatabaseManager(_make_kernel())
        db.conn = AsyncMock()
        db.conn.execute = AsyncMock()
        db.conn.commit = AsyncMock()

        await db.db_set("mod", "key", 123)

        db.conn.execute.assert_awaited_once_with(
            "INSERT OR REPLACE INTO module_data VALUES (?, ?, ?)",
            ("mod", "key", "123"),
        )
        db.conn.commit.assert_awaited_once()

    async def test_db_query_defaults_and_none_parameters(self):
        db = DatabaseManager(_make_kernel())
        db.conn = AsyncMock()
        cursor = AsyncMock()
        cursor.fetchall = AsyncMock(return_value=[("ok",)])
        db.conn.execute = AsyncMock(return_value=cursor)

        rows = await db.db_query("SELECT 1")
        assert rows == [("ok",)]
        db.conn.execute.assert_awaited_with("SELECT 1", ())

        db.conn.execute.reset_mock()
        rows = await db.db_query("SELECT 1", None)
        assert rows == [("ok",)]
        db.conn.execute.assert_awaited_with("SELECT 1", ())

    async def test_db_query_blocks_write_queries(self):
        db = DatabaseManager(_make_kernel())
        db.conn = AsyncMock()

        with pytest.raises(PermissionError):
            await db.db_query("DELETE FROM module_data WHERE module = ?", ("m",))

    async def test_identifier_validation_blocks_invalid_keys(self):
        db = DatabaseManager(_make_kernel())
        db.conn = AsyncMock()

        with pytest.raises(ValueError):
            await db.db_set("bad module", "k", "v")
        with pytest.raises(ValueError):
            await db.db_get("module", "bad key")
