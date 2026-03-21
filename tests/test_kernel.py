"""
Tests for Kernel - additional functionality
"""

import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch


class TestKernelCore:
    """Test Kernel initialization and core properties"""

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    def test_kernel_initialization(self, mock_db, mock_cfg, mock_log):
        """Test Kernel instance creation"""
        from core.kernel import Kernel

        kernel = Kernel()
        kernel.custom_prefix = "."
        assert kernel is not None
        assert hasattr(kernel, "VERSION")
        assert kernel.custom_prefix == "."

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    def test_kernel_version_format(self, mock_db, mock_cfg, mock_log):
        """Test version follows expected format"""
        from core.kernel import Kernel

        kernel = Kernel()
        version = kernel.VERSION
        parts = version.split(".")
        assert len(parts) >= 3

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    def test_cache_initialization(self, mock_db, mock_cfg, mock_log):
        """Test cache is initialized"""
        from core.kernel import Kernel

        kernel = Kernel()
        assert kernel.cache is not None
        assert hasattr(kernel.cache, "set")
        assert hasattr(kernel.cache, "get")

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    def test_module_registries(self, mock_db, mock_cfg, mock_log):
        """Test module registries are initialized"""
        from core.kernel import Kernel

        kernel = Kernel()
        assert isinstance(kernel.loaded_modules, dict)
        assert isinstance(kernel.system_modules, dict)
        assert isinstance(kernel.command_handlers, dict)

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    def test_directories_setup(self, mock_db, mock_cfg, mock_log, tmp_path):
        """Test directory setup"""
        from core.kernel import Kernel

        kernel = Kernel()
        kernel.MODULES_DIR = str(tmp_path / "modules")
        kernel.setup_directories()

        assert (tmp_path / "modules").exists()

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    def test_register_initialized(self, mock_db, mock_cfg, mock_log):
        """Test register is initialized"""
        from core.kernel import Kernel

        kernel = Kernel()
        assert kernel.register is not None


@pytest.mark.asyncio
class TestKernelScheduler:
    """Test scheduler functionality"""

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    async def test_scheduler_init(self, mock_db, mock_cfg, mock_log):
        """Test scheduler initialization"""
        from core.kernel import Kernel

        kernel = Kernel()
        await kernel.init_scheduler()

        assert kernel.scheduler is not None
        assert kernel.scheduler.running is True

        await kernel.scheduler.stop()

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    async def test_add_scheduled_task(self, mock_db, mock_cfg, mock_log):
        """Test adding scheduled task"""
        from core.kernel import Kernel

        kernel = Kernel()
        await kernel.init_scheduler()

        executed = []

        async def task():
            executed.append(1)

        await kernel.scheduler.add_interval_task(task, 0.2)

        await kernel.scheduler.stop()

        assert kernel.scheduler is not None


class TestKernelCache:
    """Test TTL cache functionality"""

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    def test_cache_basic_operations(self, mock_db, mock_cfg, mock_log):
        """Test cache set/get"""
        from core.kernel import Kernel

        kernel = Kernel()

        kernel.cache.set("key1", "value1")
        assert kernel.cache.get("key1") == "value1"

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    def test_cache_expiration(self, mock_db, mock_cfg, mock_log):
        """Test cache TTL expiration"""
        from core.kernel import Kernel

        kernel = Kernel()

        kernel.cache.set("key2", "value2", ttl=0.1)
        time.sleep(0.2)
        assert kernel.cache.get("key2") is None

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    def test_cache_overwrite(self, mock_db, mock_cfg, mock_log):
        """Test cache value overwrite"""
        from core.kernel import Kernel

        kernel = Kernel()

        kernel.cache.set("key", "value1")
        kernel.cache.set("key", "value2")

        assert kernel.cache.get("key") == "value2"


@pytest.mark.asyncio
class TestKernelCommands:
    """Test command handling"""

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    async def test_command_registration(self, mock_db, mock_cfg, mock_log):
        """Test command handler registration"""
        from core.kernel import Kernel

        kernel = Kernel()

        async def test_handler(event):
            return "test"

        kernel.command_handlers["test"] = test_handler

        assert "test" in kernel.command_handlers

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    async def test_alias_handling(self, mock_db, mock_cfg, mock_log):
        """Test command alias handling"""
        from core.kernel import Kernel

        kernel = Kernel()

        kernel.aliases["t"] = "test"

        assert kernel.aliases.get("t") == "test"

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    async def test_bot_command_handlers(self, mock_db, mock_cfg, mock_log):
        """Test bot command handlers registry"""
        from core.kernel import Kernel

        kernel = Kernel()

        assert isinstance(kernel.bot_command_handlers, dict)


class TestKernelInline:
    """Test inline functionality"""

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    def test_inline_handlers_init(self, mock_db, mock_cfg, mock_log):
        """Test inline handlers registry"""
        from core.kernel import Kernel

        kernel = Kernel()

        assert isinstance(kernel.inline_handlers, dict)
        assert isinstance(kernel.callback_handlers, dict)


@pytest.mark.asyncio
class TestKernelErrorHandling:
    """Test error handling"""

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    async def test_handle_error_method_exists(self, mock_db, mock_cfg, mock_log):
        """Test handle_error method exists"""
        from core.kernel import Kernel

        kernel = Kernel()

        assert hasattr(kernel, "handle_error") or hasattr(kernel, "log_error")


@pytest.mark.asyncio
class TestKernelTelethonMcubIntegration:
    """Test Telethon-MCUB helper integration exposed by the kernel."""

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    async def test_init_client_binds_pending_middlewares(self, mock_db, mock_cfg, mock_log):
        """Pending middleware should be registered once the client is ready."""
        from core.kernel import Kernel

        kernel = Kernel()

        async def event_middleware(event, next_handler):
            return await next_handler()

        async def request_middleware(request, context, next_handler):
            return await next_handler()

        kernel.middleware_chain.append(event_middleware)
        kernel.request_middleware_chain.append(request_middleware)
        kernel.client = MagicMock()
        kernel.client.add_event_middleware = MagicMock()
        kernel.client.add_request_middleware = MagicMock()
        kernel._client_mgr.init_client = AsyncMock(return_value=True)

        ok = await kernel.init_client()

        assert ok is True
        kernel.client.add_event_middleware.assert_called_once_with(event_middleware)
        kernel.client.add_request_middleware.assert_called_once_with(request_middleware)

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    async def test_process_with_middleware_uses_client_pipeline(self, mock_db, mock_cfg, mock_log):
        """Kernel middleware processing should delegate to Telethon-MCUB pipeline."""
        from core.kernel import Kernel

        kernel = Kernel()
        kernel.client = MagicMock()
        kernel.client._middleware = MagicMock()
        kernel.client._middleware.process = AsyncMock(return_value="processed")

        handler = AsyncMock(return_value="handler")
        result = await kernel.process_with_middleware(MagicMock(), handler)

        assert result == "processed"
        kernel.client._middleware.process.assert_awaited_once()
        handler.assert_not_awaited()

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    async def test_get_thread_id_reads_nested_reply_metadata(self, mock_db, mock_cfg, mock_log):
        """Nested message.reply_to metadata should resolve the forum thread id."""
        from core.kernel import Kernel

        kernel = Kernel()
        event = MagicMock()
        event.reply_to_top_id = None
        event.reply_to = None
        event.message = MagicMock(reply_to_top_id=None)
        event.message.reply_to = MagicMock(reply_to_top_id=77)

        assert await kernel.get_thread_id(event) == 77

    @patch("core.kernel.standard.setup_logging")
    @patch("core.kernel.standard.ConfigManager")
    @patch("core.kernel.standard.DatabaseManager")
    async def test_send_with_emoji_uses_topic_helpers(self, mock_db, mock_cfg, mock_log):
        """Topic-aware sends should route through Telethon-MCUB forum helpers."""
        from core.kernel import Kernel

        kernel = Kernel()
        kernel.emoji_parser = None
        kernel.client = MagicMock()
        kernel.client.send_to_topic = AsyncMock(return_value="topic-message")
        kernel.client.send_file_to_topic = AsyncMock(return_value="topic-file")
        kernel.client.send_message = AsyncMock()

        result = await kernel.send_with_emoji(100, "hello", topic=9)
        file_result = await kernel.send_with_emoji(100, "hello", topic=9, file="demo.bin", silent=True)

        assert result == "topic-message"
        assert file_result == "topic-file"
        kernel.client.send_to_topic.assert_awaited_once_with(100, 9, "hello")
        kernel.client.send_file_to_topic.assert_awaited_once_with(
            100,
            9,
            "demo.bin",
            caption="hello",
            silent=True,
        )
        kernel.client.send_message.assert_not_awaited()
