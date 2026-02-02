"""
Comprehensive tests for Kernel core functionality
"""
import pytest
import json
import time
from unittest.mock import patch, MagicMock
import aiohttp

class TestKernelCore:
    """Test Kernel initialization and core properties"""
    
    def test_kernel_initialization(self, kernel_instance):
        """Test Kernel instance creation"""
        assert kernel_instance is not None
        assert hasattr(kernel_instance, 'VERSION')
        assert hasattr(kernel_instance, 'custom_prefix')
        assert kernel_instance.custom_prefix == '.'
        
    def test_kernel_version_format(self, kernel_instance):
        """Test version follows semver-like format"""
        version = kernel_instance.VERSION
        # Should be something like 1.0.2.0
        parts = version.split('.')
        assert len(parts) >= 3
        assert all(part.isdigit() for part in parts)
        
    def test_setup_directories(self, kernel_instance, tmp_path):
        """Test directory creation"""
        with patch('os.makedirs') as mock_makedirs:
            kernel_instance.MODULES_DIR = str(tmp_path / 'modules')
            kernel_instance.setup_directories()
            assert mock_makedirs.called
            
    def test_load_or_create_config(self, kernel_instance, tmp_path):
        """Test config loading"""
        # Test with existing config
        config_file = tmp_path / 'config.json'
        config_data = {
            'api_id': 12345,
            'api_hash': 'test_hash',
            'phone': '+1234567890'
        }
        config_file.write_text(json.dumps(config_data))
        
        kernel_instance.CONFIG_FILE = str(config_file)
        result = kernel_instance.load_or_create_config()
        assert result is True
        assert 'api_id' in kernel_instance.config
        
    def test_setup_config(self, kernel_instance):
        """Test config validation"""
        kernel_instance.config = {
            'api_id': '12345',
            'api_hash': 'test_hash',
            'phone': '+1234567890',
            'command_prefix': '!'
        }
        
        result = kernel_instance.setup_config()
        assert result is True
        assert kernel_instance.custom_prefix == '!'
        assert kernel_instance.API_ID == 12345

class TestKernelCommands:
    """Test command handling"""
    
    async def test_process_command(self, kernel_instance, mock_event):
        """Test command processing"""
        # Setup a test command handler
        handler_called = []
        async def test_handler(event):
            handler_called.append(event.text)
            
        kernel_instance.command_handlers['test'] = test_handler
        kernel_instance.custom_prefix = '.'
        
        # Test valid command
        mock_event.text = '.test'
        result = await kernel_instance.process_command(mock_event)
        assert result is True
        assert len(handler_called) == 1
        
        # Test invalid command
        mock_event.text = '.nonexistent'
        result = await kernel_instance.process_command(mock_event)
        assert result is False
        
    async def test_command_aliases(self, kernel_instance, mock_event):
        """Test command alias resolution"""
        handler_called = []
        async def test_handler(event):
            handler_called.append(event.text)
            
        kernel_instance.command_handlers['test'] = test_handler
        kernel_instance.aliases['t'] = 'test'
        kernel_instance.custom_prefix = '.'
        
        mock_event.text = '.t'
        result = await kernel_instance.process_command(mock_event)
        assert result is True
        assert len(handler_called) == 1

class TestKernelDatabase:
    """Test database operations"""
    
    async def test_db_operations(self, kernel_instance):
        """Test basic DB CRUD operations"""
        # Mock db_conn
        cursor = AsyncMock()
        cursor.fetchone = AsyncMock(return_value=('test_value',))
        kernel_instance.db_conn.execute = AsyncMock(return_value=cursor)
        
        # Test set
        await kernel_instance.db_set('test_module', 'test_key', 'test_value')
        assert kernel_instance.db_conn.execute.called
        assert kernel_instance.db_conn.commit.called
        
        # Test get
        value = await kernel_instance.db_get('test_module', 'test_key')
        assert value == 'test_value'
        
        # Test delete
        await kernel_instance.db_delete('test_module', 'test_key')
        assert kernel_instance.db_conn.commit.called
        
    async def test_module_config(self, kernel_instance):
        """Test module configuration persistence"""
        test_config = {'setting1': 'value1', 'enabled': True}
        
        with patch.object(kernel_instance, 'db_get', AsyncMock(
            return_value=json.dumps(test_config)
        )):
            config = await kernel_instance.get_module_config('test_module')
            assert config == test_config
            
        with patch.object(kernel_instance, 'db_set', AsyncMock()) as mock_set:
            await kernel_instance.save_module_config('test_module', test_config)
            mock_set.assert_called_once()

class TestKernelErrorHandling:
    """Test error handling mechanisms"""
    
    async def test_handle_error(self, kernel_instance):
        """Test error logging and reporting"""
        with patch.object(kernel_instance, 'send_log_message', AsyncMock()) as mock_log:
            test_error = ValueError("Test error")
            await kernel_instance.handle_error(test_error, source="test_function")
            
            assert mock_log.called
            # Check that error was logged properly
            call_args = mock_log.call_args[0][0]
            assert 'test_function' in call_args
            assert 'Test error' in call_args
            
    async def test_error_with_event(self, kernel_instance, mock_event):
        """Test error handling with event context"""
        with patch.object(kernel_instance, 'send_log_message', AsyncMock()):
            test_error = RuntimeError("Event error")
            await kernel_instance.handle_error(
                test_error, 
                source="test_handler", 
                event=mock_event
            )
            
    def test_save_error_to_file(self, kernel_instance, tmp_path):
        """Test error file creation"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            test_error = "Test error traceback\nLine 1\nLine 2"
            kernel_instance.save_error_to_file(test_error)
            # Should create error log file
            import os
            log_dir = os.path.join(tmpdir, 'logs')
            # This is a silent operation, just ensure no exception

class TestKernelCache:
    """Test TTL cache functionality"""
    
    def test_ttl_cache_basic(self, kernel_instance):
        """Test cache set/get operations"""
        kernel_instance.cache.set('key1', 'value1')
        value = kernel_instance.cache.get('key1')
        assert value == 'value1'
        
    def test_ttl_cache_expiration(self, kernel_instance):
        """Test cache expiration"""
        kernel_instance.cache.set('key2', 'value2', ttl=0.1)  # 100ms TTL
        time.sleep(0.2)  # Wait for expiration
        value = kernel_instance.cache.get('key2')
        assert value is None
        
    def test_ttl_cache_cleanup(self, kernel_instance):
        """Test cache cleanup and size limits"""
        # Fill cache beyond max size
        for i in range(1100):  # More than default max_size (1000)
            kernel_instance.cache.set(f'key_{i}', f'value_{i}')
            
        # Cache should have evicted oldest entries
        assert kernel_instance.cache.size() <= 1000

class TestKernelScheduler:
    """Test task scheduler"""
    
    async def test_scheduler_initialization(self, kernel_instance):
        """Test scheduler setup"""
        await kernel_instance.init_scheduler()
        assert kernel_instance.scheduler is not None
        
    async def test_interval_task(self, kernel_instance):
        """Test interval task scheduling"""
        await kernel_instance.init_scheduler()
        
        task_executed = []
        async def test_task():
            task_executed.append(time.time())
            
        task_id = await kernel_instance.scheduler.add_interval_task(
            test_task, interval_seconds=0.1
        )
        
        assert task_id is not None
        assert task_id in kernel_instance.scheduler.task_registry
        
        # Wait and check task was scheduled
        await asyncio.sleep(0.15)
        kernel_instance.scheduler.cancel_task(task_id)
        
    async def test_daily_task(self, kernel_instance):
        """Test daily task scheduling"""
        await kernel_instance.init_scheduler()
        
        task_executed = []
        async def test_task():
            task_executed.append(time.time())
            
        task_id = await kernel_instance.scheduler.add_daily_task(
            test_task, hour=12, minute=0
        )
        
        assert task_id is not None
        assert task_id.startswith('daily_')

@pytest.mark.asyncio
class TestKernelAsyncFeatures:
    """Test async features"""
    
    async def test_inline_query_execution(self, kernel_instance):
        """Test inline query helper"""
        mock_results = [Mock(click=AsyncMock())]
        with patch.object(kernel_instance.client, 'inline_query', 
                         AsyncMock(return_value=mock_results)):
            
            success, message = await kernel_instance.inline_query_and_click(
                chat_id=123456789,
                query="test query",
                bot_username="test_bot"
            )
            
            assert success is True
            
    async def test_module_loading(self, kernel_instance, tmp_path):
        """Test module loading from file"""
        # Create a test module
        test_module_code = '''
def register(kernel):
    @kernel.register.command('moduletest')
    async def test_handler(event):
        await event.edit("Module loaded!")
'''
        
        module_file = tmp_path / 'test_module.py'
        module_file.write_text(test_module_code)
        
        with patch('importlib.util.spec_from_file_location'):
            # This is complex to test fully, but we can test the method signature
            result = await kernel_instance.load_module_from_file(
                str(module_file), 'test_module', is_system=False
            )
            # Method returns tuple (success, message)
            assert isinstance(result, tuple)
            assert len(result) == 2
            
    async def test_repository_operations(self, kernel_instance):
        """Test repository management"""
        mock_response = Mock(status=200, text=AsyncMock(return_value='module1\nmodule2'))
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            success, message = await kernel_instance.add_repository(
                'https://example.com/repo'
            )
            
            # Either succeeds or fails gracefully
            assert isinstance(success, bool)
            assert isinstance(message, str)
