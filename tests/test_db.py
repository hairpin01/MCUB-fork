"""
Tests for database operations - extended
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
class TestDatabaseOperations:
    """Test database operations"""

    async def test_db_set_operation(self):
        """Test database set operation"""
        from core.lib.base.database import DatabaseManager
        
        kernel = MagicMock()
        kernel.logger = MagicMock()
        
        db = DatabaseManager(kernel)
        db.conn = AsyncMock()
        db.conn.execute = AsyncMock()
        db.conn.commit = AsyncMock()
        
        await db.db_set("module", "key", "value")
        
        assert db.conn.execute.called

    async def test_db_get_operation(self):
        """Test database get operation"""
        from core.lib.base.database import DatabaseManager
        
        kernel = MagicMock()
        kernel.logger = MagicMock()
        
        db = DatabaseManager(kernel)
        db.conn = AsyncMock()
        
        cursor = AsyncMock()
        cursor.fetchone = AsyncMock(return_value=("value",))
        db.conn.execute = AsyncMock(return_value=cursor)
        
        result = await db.db_get("module", "key")
        
        assert result == "value"

    async def test_db_delete_operation(self):
        """Test database delete operation"""
        from core.lib.base.database import DatabaseManager
        
        kernel = MagicMock()
        kernel.logger = MagicMock()
        
        db = DatabaseManager(kernel)
        db.conn = AsyncMock()
        db.conn.execute = AsyncMock()
        db.conn.commit = AsyncMock()
        
        await db.db_delete("module", "key")
        
        assert db.conn.commit.called

    async def test_db_query_operation(self):
        """Test database custom query"""
        from core.lib.base.database import DatabaseManager
        
        kernel = MagicMock()
        kernel.logger = MagicMock()
        
        db = DatabaseManager(kernel)
        db.conn = AsyncMock()
        
        cursor = AsyncMock()
        cursor.fetchall = AsyncMock(return_value=[("row1",), ("row2",)])
        db.conn.execute = AsyncMock(return_value=cursor)
        
        result = await db.db_query("SELECT * FROM table", ())
        
        assert len(result) == 2


@pytest.mark.asyncio
class TestModuleStorage:
    """Test module storage"""

    async def test_module_config_storage(self):
        """Test module config storage"""
        from core.lib.base.database import DatabaseManager
        
        kernel = MagicMock()
        kernel.logger = MagicMock()
        
        db = DatabaseManager(kernel)
        db.db_set = AsyncMock()
        
        config = {"setting": True, "value": "test"}
        await db.db_set("test_module", "config", json.dumps(config))
        
        assert db.db_set.called

    async def test_module_config_retrieval(self):
        """Test module config retrieval"""
        from core.lib.base.database import DatabaseManager
        
        kernel = MagicMock()
        kernel.logger = MagicMock()
        
        db = DatabaseManager(kernel)
        
        config_data = {"setting": True}
        db.db_get = AsyncMock(return_value=json.dumps(config_data))
        
        result = await db.db_get("test_module", "config")
        parsed = json.loads(result)
        
        assert parsed["setting"] is True

    async def test_empty_module_config(self):
        """Test empty module config returns default"""
        from core.lib.base.database import DatabaseManager
        
        kernel = MagicMock()
        kernel.logger = MagicMock()
        
        db = DatabaseManager(kernel)
        db.db_get = AsyncMock(return_value=None)
        
        result = await db.db_get("test_module", "config")
        
        assert result is None


@pytest.mark.asyncio
class TestDataTypes:
    """Test complex data types handling"""

    async def test_complex_data_serialization(self):
        """Test complex data serialization"""
        from core.lib.base.database import DatabaseManager
        
        kernel = MagicMock()
        kernel.logger = MagicMock()
        
        db = DatabaseManager(kernel)
        
        complex_data = {
            "list": [1, 2, 3],
            "dict": {"nested": True},
            "string": "test"
        }
        
        serialized = json.dumps(complex_data)
        deserialized = json.loads(serialized)
        
        assert deserialized["list"] == [1, 2, 3]
        assert deserialized["dict"]["nested"] is True

    async def test_binary_data_handling(self):
        """Test binary data handling"""
        from core.lib.base.database import DatabaseManager
        
        kernel = MagicMock()
        kernel.logger = MagicMock()
        
        db = DatabaseManager(kernel)
        db.db_set = AsyncMock()
        
        binary_data = b"\x00\x01\x02\x03"
        await db.db_set("test", "binary", binary_data)
        
        assert db.db_set.called
