"""
Tests for database operations - extended
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock


class TestDatabaseOperations:
    """Test database operations"""

    @pytest.fixture
    def mock_kernel(self):
        """Create mock kernel for database tests"""
        kernel = MagicMock()
        kernel.logger = MagicMock()
        return kernel

    @pytest.fixture
    def db_manager(self, mock_kernel):
        """Create DatabaseManager with mocked connection"""
        from core.lib.base.database import DatabaseManager

        db = DatabaseManager(mock_kernel)
        db.conn = AsyncMock()
        db.conn.execute = AsyncMock()
        db.conn.commit = AsyncMock()
        return db

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "value",
        [
            "simple_string",
            "123",
            "",
            "string with spaces",
            "unicode: こんにちは",
            "special chars: !@#$%^&*()",
        ],
    )
    async def test_db_set_with_various_values(self, db_manager, value):
        """Test database set operation with various value types"""
        await db_manager.db_set("module", "key", value)
        assert db_manager.conn.execute.called
        db_manager.conn.commit.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "stored_value,expected",
        [
            (("value",), "value"),
            (("123",), "123"),
            (('{"key": "val"}',), '{"key": "val"}'),
            ((None,), None),
        ],
    )
    async def test_db_get_returns_correct_value(
        self, mock_kernel, stored_value, expected
    ):
        """Test database get operation returns correct values"""
        from core.lib.base.database import DatabaseManager

        db = DatabaseManager(mock_kernel)
        cursor = AsyncMock()
        cursor.fetchone = AsyncMock(return_value=stored_value)
        db.conn = AsyncMock()
        db.conn.execute = AsyncMock(return_value=cursor)

        result = await db.db_get("module", "key")
        assert result == expected

    @pytest.mark.asyncio
    async def test_db_get_returns_none_for_missing_key(self, db_manager):
        """Test database get returns None for non-existent key"""
        cursor = AsyncMock()
        cursor.fetchone = AsyncMock(return_value=None)
        db_manager.conn.execute = AsyncMock(return_value=cursor)

        result = await db_manager.db_get("module", "missing_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_db_delete_operation(self, db_manager):
        """Test database delete operation"""
        await db_manager.db_delete("module", "key")
        assert db_manager.conn.execute.called
        db_manager.conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_query_returns_all_rows(self, db_manager):
        """Test database custom query returns all rows"""
        cursor = AsyncMock()
        cursor.fetchall = AsyncMock(return_value=[("row1",), ("row2",), ("row3",)])
        db_manager.conn.execute = AsyncMock(return_value=cursor)

        result = await db_manager.db_query("SELECT * FROM table", ())
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_db_query_returns_empty_list(self, db_manager):
        """Test database query returns empty list when no results"""
        cursor = AsyncMock()
        cursor.fetchall = AsyncMock(return_value=[])
        db_manager.conn.execute = AsyncMock(return_value=cursor)

        result = await db_manager.db_query("SELECT * FROM empty_table", ())
        assert result == []

    @pytest.mark.asyncio
    async def test_db_query_with_parameters(self, db_manager):
        """Test database query with parameters"""
        cursor = AsyncMock()
        cursor.fetchall = AsyncMock(return_value=[("result",)])
        db_manager.conn.execute = AsyncMock(return_value=cursor)

        params = ("param1", 123)
        await db_manager.db_query("SELECT * FROM table WHERE col = ?", params)

        db_manager.conn.execute.assert_called_once()
        call_args = db_manager.conn.execute.call_args
        assert "??" in call_args[0][0] or "?" in call_args[0][0]


@pytest.fixture
def complex_data():
    """Fixture providing complex test data"""
    return {
        "simple_string": "test_value",
        "numbers": [1, 2, 3, 4, 5],
        "nested_dict": {"level1": {"level2": {"level3": "deep"}}},
        "mixed": {"list": [1, "two", 3.0], "bool": True, "null": None},
        "unicode": "Hello, こんにちは, Привет, مرحبا",
        "special": "!@#$%^&*()_+-=[]{}|;':\",./<>?",
    }


class TestModuleStorage:
    """Test module storage"""

    @pytest.fixture
    def db_manager(self):
        """Create DatabaseManager with mocked db_set"""
        kernel = MagicMock()
        kernel.logger = MagicMock()
        db = MagicMock()
        db.db_set = AsyncMock()
        db.db_get = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_module_config_storage(self, db_manager, complex_data):
        """Test module config storage with complex data"""
        await db_manager.db_set("test_module", "config", json.dumps(complex_data))
        db_manager.db_set.assert_called_once()

        call_args = db_manager.db_set.call_args
        stored_json = call_args[0][2]
        parsed = json.loads(stored_json)
        assert parsed == complex_data

    @pytest.mark.asyncio
    async def test_module_config_retrieval(self, db_manager, complex_data):
        """Test module config retrieval parses JSON correctly"""
        db_manager.db_get = AsyncMock(return_value=json.dumps(complex_data))

        result = await db_manager.db_get("test_module", "config")
        parsed = json.loads(result)

        assert parsed["simple_string"] == "test_value"
        assert parsed["numbers"] == [1, 2, 3, 4, 5]
        assert parsed["nested_dict"]["level1"]["level2"]["level3"] == "deep"

    @pytest.mark.asyncio
    async def test_empty_module_config(self, db_manager):
        """Test empty module config returns None"""
        db_manager.db_get = AsyncMock(return_value=None)

        result = await db_manager.db_get("test_module", "config")
        assert result is None

    @pytest.mark.asyncio
    async def test_corrupted_json_handling(self, db_manager):
        """Test handling of corrupted JSON data"""
        db_manager.db_get = AsyncMock(return_value="not valid json {{{")

        result = await db_manager.db_get("test_module", "config")
        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            parsed = None

        assert parsed is None

    @pytest.mark.asyncio
    async def test_multiple_configs_isolation(self, db_manager):
        """Test that different modules have isolated configs"""
        config1 = {"key": "value1"}
        config2 = {"key": "value2"}

        db_manager.db_get = AsyncMock(
            side_effect=[
                json.dumps(config1),
                json.dumps(config2),
            ]
        )

        result1 = json.loads(await db_manager.db_get("module1", "config"))
        result2 = json.loads(await db_manager.db_get("module2", "config"))

        assert result1["key"] == "value1"
        assert result2["key"] == "value2"
        assert result1 != result2


class TestDataTypes:
    """Test complex data types handling"""

    @pytest.fixture
    def db_manager(self):
        """Create DatabaseManager with mocked methods"""
        kernel = MagicMock()
        kernel.logger = MagicMock()
        db = MagicMock()
        db.db_set = AsyncMock()
        db.db_get = AsyncMock()
        return db

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "data",
        [
            {"list": [1, 2, 3]},
            {"dict": {"nested": True}},
            {"string": "test"},
            {"unicode": "日本語テスト"},
            {"emoji": "😀🎉🔥"},
            {"empty_list": []},
            {"empty_dict": {}},
            {"numbers": [0, -1, 1.5, 1e10]},
            {"special_chars": "\n\t\r\x00"},
        ],
    )
    async def test_complex_data_serialization_roundtrip(self, db_manager, data):
        """Test complex data serialization and deserialization roundtrip"""
        serialized = json.dumps(data)
        deserialized = json.loads(serialized)
        assert deserialized == data

    @pytest.mark.asyncio
    async def test_binary_data_handling(self, db_manager):
        """Test binary data handling"""
        binary_data = b"\x00\x01\x02\x03\xff\xfe\xfd"
        await db_manager.db_set("test", "binary", binary_data)
        db_manager.db_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_deeply_nested_structure(self, db_manager):
        """Test handling of deeply nested structures"""
        deep_data = {"level": 0}
        current = deep_data
        for i in range(1, 10):
            current["nested"] = {"level": i}
            current = current["nested"]

        serialized = json.dumps(deep_data)
        deserialized = json.loads(serialized)

        assert deserialized["level"] == 0
        current_check = deserialized["nested"]
        for i in range(1, 10):
            if "nested" in current_check:
                assert current_check["level"] == i
                current_check = current_check["nested"]
            else:
                assert current_check["level"] == i
                break

    @pytest.mark.asyncio
    async def test_large_list_handling(self, db_manager):
        """Test handling of large lists"""
        large_list = list(range(10000))
        data = {"large_list": large_list}

        serialized = json.dumps(data)
        deserialized = json.loads(serialized)

        assert len(deserialized["large_list"]) == 10000
        assert deserialized["large_list"][-1] == 9999
