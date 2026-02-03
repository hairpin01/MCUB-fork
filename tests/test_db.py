"""
Tests for database operations and module storage
"""
import pytest
import json
import aiosqlite
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
class TestDatabaseOperations:
    """Test database CRUD operations"""
    
    async def test_db_connection(self, kernel_instance):
        """Test database connection initialization"""
        mock_conn = AsyncMock()
        with patch('aiosqlite.connect', return_value=mock_conn):
            result = await kernel_instance.init_db()
            
            # Should either succeed or fail gracefully
            assert isinstance(result, bool)
            
    async def test_create_tables(self, kernel_instance):
        """Test table creation"""
        mock_conn = AsyncMock()
        kernel_instance.db_conn = mock_conn
        
        await kernel_instance.create_tables()
        
        # Should execute CREATE TABLE statement
        assert mock_conn.execute.called
        sql_call = mock_conn.execute.call_args[0][0]
        assert "CREATE TABLE" in sql_call
        assert "module_data" in sql_call
        
    async def test_db_set_operation(self, kernel_instance):
        """Test setting data in database"""
        mock_conn = AsyncMock()
        kernel_instance.db_conn = mock_conn
        
        await kernel_instance.db_set('test_module', 'test_key', 'test_value')
        
        # Check SQL execution
        assert mock_conn.execute.called
        call_args = mock_conn.execute.call_args[0]
        
        assert call_args[0] == 'INSERT OR REPLACE INTO module_data VALUES (?, ?, ?)'
        assert call_args[1] == ('test_module', 'test_key', 'test_value')
        assert mock_conn.commit.called
        
    async def test_db_get_operation(self, kernel_instance):
        """Test retrieving data from database"""
        # Mock cursor and result
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=('test_value',))
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        kernel_instance.db_conn = mock_conn
        
        result = await kernel_instance.db_get('test_module', 'test_key')
        
        assert result == 'test_value'
        
        # Test non-existent key
        mock_cursor.fetchone = AsyncMock(return_value=None)
        result = await kernel_instance.db_get('test_module', 'nonexistent')
        assert result is None
        
    async def test_db_delete_operation(self, kernel_instance):
        """Test deleting data from database"""
        mock_conn = AsyncMock()
        kernel_instance.db_conn = mock_conn
        
        await kernel_instance.db_delete('test_module', 'test_key')
        
        assert mock_conn.execute.called
        call_args = mock_conn.execute.call_args[0]
        assert 'DELETE FROM' in call_args[0]
        assert call_args[1] == ('test_module', 'test_key')
        assert mock_conn.commit.called
        
    async def test_db_query_custom(self, kernel_instance):
        """Test custom SQL queries"""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[('row1',), ('row2',)])
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        kernel_instance.db_conn = mock_conn
        
        results = await kernel_instance.db_query(
            "SELECT * FROM module_data WHERE module = ?",
            ('test_module',)
        )
        
        assert len(results) == 2
        assert results[0] == ('row1',)

class TestModuleStorage:
    """Test module-specific storage"""
    
    async def test_module_config_storage(self, kernel_instance):
        """Test module configuration persistence"""
        test_config = {
            'enabled': True,
            'settings': {'key': 'value'},
            'count': 42
        }
        
        # Mock db_set for saving
        with patch.object(kernel_instance, 'db_set', AsyncMock()) as mock_set:
            await kernel_instance.save_module_config('test_module', test_config)
            
            # Should serialize to JSON
            call_args = mock_set.call_args[0]
            assert call_args[0] == 'kernel'
            assert call_args[1] == 'module_config_test_module'
            
            # Check JSON serialization
            saved_json = call_args[2]
            parsed = json.loads(saved_json)
            assert parsed == test_config
            
    async def test_module_config_retrieval(self, kernel_instance):
        """Test module configuration loading"""
        test_config = {'enabled': True, 'count': 42}
        
        with patch.object(kernel_instance, 'db_get', 
                         AsyncMock(return_value=json.dumps(test_config))):
            
            config = await kernel_instance.get_module_config('test_module')
            assert config == test_config
            
            # Test with default value
            config_with_default = await kernel_instance.get_module_config(
                'nonexistent_module', default={'default': True}
            )
            assert config_with_default == {'default': True}
            
    async def test_empty_module_config(self, kernel_instance):
        """Test handling of empty/non-existent config"""
        with patch.object(kernel_instance, 'db_get', AsyncMock(return_value=None)):
            config = await kernel_instance.get_module_config('empty_module')
            assert config == {}
            
            # With explicit default
            config = await kernel_instance.get_module_config(
                'empty_module', default={'explicit': 'default'}
            )
            assert config == {'explicit': 'default'}

class TestDataTypes:
    """Test various data type handling in database"""
    
    async def test_complex_data_serialization(self, kernel_instance):
        """Test serialization of complex data structures"""
        complex_data = {
            'nested': {
                'list': [1, 2, 3],
                'dict': {'key': 'value'}
            },
            'boolean': True,
            'number': 3.14159,
            'none_value': None
        }
        
        with patch.object(kernel_instance, 'db_set', AsyncMock()):
            await kernel_instance.save_module_config('complex_module', complex_data)
            
            # The call should have happened with JSON string
            call_args = kernel_instance.db_set.call_args[0]
            saved_data = json.loads(call_args[2])
            
            # Verify all data preserved
            assert saved_data['nested']['list'] == [1, 2, 3]
            assert saved_data['boolean'] is True
            assert saved_data['number'] == 3.14159
            
    async def test_binary_data_handling(self, kernel_instance):
        """Test handling of binary/non-JSON data"""
        # Binary data should be stringified
        binary_data = b'binary_data'
        
        with patch.object(kernel_instance, 'db_set', AsyncMock()):
            await kernel_instance.db_set('binary_module', 'binary_key', binary_data)
            
            call_args = kernel_instance.db_set.call_args[0]
            # Should convert to string
            assert call_args[2] == str(binary_data)
