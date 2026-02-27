"""
Test configuration and fixtures for MCUB
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Add parent directory to Python path (so core can be imported as a package)
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_client():
    """Mock Telegram client"""
    client = AsyncMock()
    client.is_connected.return_value = True
    client.is_user_authorized.return_value = True
    client.get_me = AsyncMock(return_value=Mock(id=123456789))
    return client


@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    conn = AsyncMock()
    cursor = AsyncMock()
    cursor.fetchone = AsyncMock()
    cursor.fetchall = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value=cursor)
    conn.commit = AsyncMock()
    conn.cursor = AsyncMock(return_value=cursor)
    return conn


@pytest.fixture
def mock_db_manager(mock_db_connection):
    """Mock database manager"""
    db_manager = MagicMock()
    db_manager.conn = mock_db_connection
    db_manager.db_set = AsyncMock()
    db_manager.db_get = AsyncMock(return_value=None)
    db_manager.db_delete = AsyncMock()
    db_manager.db_query = AsyncMock(return_value=[])
    return db_manager


@pytest.fixture
def kernel_instance(mock_client, mock_db_connection, mock_db_manager):
    """Create a Kernel instance with mocked dependencies"""
    with patch("aiosqlite.connect", return_value=mock_db_connection), \
         patch("telethon.TelegramClient", return_value=mock_client), \
         patch("core.kernel.setup_logging"), \
         patch("core.kernel.ConfigManager"), \
         patch("core.kernel.ModuleLoader"), \
         patch("core.kernel.RepositoryManager"), \
         patch("core.kernel.KernelLogger"), \
         patch("core.kernel.ClientManager"), \
         patch("core.kernel.InlineManager"), \
         patch("core.kernel.VersionManager"), \
         patch("core.kernel.DatabaseManager", return_value=mock_db_manager):

        from core.kernel import Kernel

        kernel = Kernel()
        
        # Replace db_manager with our mock
        kernel.db_manager = mock_db_manager
        
        kernel.client = mock_client

        # Mock inline bot
        kernel.bot_client = AsyncMock()
        kernel.bot_client.is_connected.return_value = True

        # Mock configuration
        kernel.config = {
            "api_id": 12345,
            "api_hash": "hash123",
            "phone": "+1234567890",
            "command_prefix": ".",
        }

        # Initialize required attributes
        kernel.ADMIN_ID = 123456789
        kernel.loaded_modules = {}
        kernel.system_modules = {}
        kernel.command_handlers = {}
        kernel.bot_command_handlers = {}

        return kernel


@pytest.fixture
def mock_event():
    """Mock Telethon event"""
    event = AsyncMock()
    event.client = AsyncMock()
    event.chat_id = -1001234567890
    event.sender_id = 987654321
    event.text = ".test"
    event.message = Mock(id=123)
    event.reply_to = None
    event.edit = AsyncMock()
    event.reply = AsyncMock()
    event.delete = AsyncMock()
    return event


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
