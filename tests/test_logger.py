"""
Unit tests for logger.py
"""

import asyncio
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open


def _make_telethon_stubs():
    """Create minimal stubs for telethon and its sub-modules."""

    errors_mod = types.ModuleType("telethon.errors")

    class _RPCError(Exception):
        def __init__(self, request=None, message=""):
            super().__init__(message)
            self.request = request

    class FloodWaitError(_RPCError):
        def __init__(self, request=None):
            super().__init__(request, "A wait of 42 seconds is required")
            self.seconds = 42

    class NetworkMigrateError(_RPCError):
        pass

    class ServerError(_RPCError):
        pass

    class TimedOutError(_RPCError):
        pass

    for cls in (
        FloodWaitError,
        NetworkMigrateError,
        ServerError,
        TimedOutError,
        _RPCError,
    ):
        setattr(errors_mod, cls.__name__, cls)

    errors_mod.RPCError = _RPCError

    telethon_mod = types.ModuleType("telethon")

    class _Button:
        @staticmethod
        def inline(text, data=None):
            return {"text": text, "data": data}

    telethon_mod.Button = _Button
    telethon_mod.errors = errors_mod

    sys.modules.setdefault("telethon", telethon_mod)
    sys.modules.setdefault("telethon.errors", errors_mod)

    return telethon_mod, errors_mod


_telethon, _errors = _make_telethon_stubs()

import importlib, os

_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

_logger_mod = importlib.import_module("core.lib.utils.logger")

from core.lib.utils.logger import (  # noqa: E402
    KernelLogger,
    RichException,
    ErrorFormatter,
    TelegramLogHandler,
    _SyncToAsyncBridge,
    setup_logging,
    setup_telegram_logging,
    mask_sensitive_data,
    override_text,
    strip_html,
)
import logging

FloodWaitError = _errors.FloodWaitError
NetworkMigrateError = _errors.NetworkMigrateError
ServerError = _errors.ServerError
TimedOutError = _errors.TimedOutError


def _make_kernel(*, log_chat_id=123456):
    """Return a MagicMock that looks like a minimal Kernel."""
    k = MagicMock()
    k.log_chat_id = log_chat_id
    k.cache.get.return_value = None
    k.cache.set.return_value = None
    k.logger = MagicMock()

    bot = AsyncMock()
    bot.is_user_authorized = AsyncMock(return_value=True)
    bot.send_message = AsyncMock()
    bot.send_file = AsyncMock()
    k.bot_client = bot

    k.client = AsyncMock()
    k.client.send_message = AsyncMock()
    k.client.send_file = AsyncMock()
    return k


def run(coro):
    return asyncio.run(coro)


class TestMaskSensitiveData(unittest.TestCase):
    def test_phone_number_masked(self):
        result = mask_sensitive_data("phone: 79991234567")
        self.assertNotIn("79991234567", result)
        self.assertIn("X" * 11, result)

    def test_token_masked(self):
        result = mask_sensitive_data("token='ABC123xyz'")
        self.assertNotIn("ABC123xyz", result)
        self.assertIn("***", result)

    def test_api_id_masked(self):
        result = mask_sensitive_data("api_id=12345678")
        self.assertNotIn("12345678", result)

    def test_api_hash_masked(self):
        result = mask_sensitive_data("api_hash=deadbeefcafe")
        self.assertNotIn("deadbeefcafe", result)

    def test_password_masked(self):
        result = mask_sensitive_data("password=hunter2")
        self.assertNotIn("hunter2", result)

    def test_session_masked(self):
        result = mask_sensitive_data("session=mysecrettoken")
        self.assertNotIn("mysecrettoken", result)

    def test_authorization_header_masked(self):
        result = mask_sensitive_data("Authorization: Bearer supersecret")
        self.assertNotIn("supersecret", result)

    def test_empty_string_passthrough(self):
        self.assertEqual(mask_sensitive_data(""), "")

    def test_none_passthrough(self):
        self.assertIsNone(mask_sensitive_data(None))

    def test_safe_text_unchanged(self):
        text = "Hello, world!"
        self.assertEqual(mask_sensitive_data(text), text)

    def test_case_insensitive(self):
        result = mask_sensitive_data("TOKEN='XYZ'")
        self.assertNotIn("XYZ", result)


class TestOverrideText(unittest.TestCase):
    def test_flood_wait_returns_string(self):
        e = FloodWaitError()
        result = override_text(e)
        self.assertIsNotNone(result)
        self.assertIn("42", result)

    def test_network_migrate_returns_string(self):
        result = override_text(NetworkMigrateError())
        self.assertIsNotNone(result)
        self.assertIn("Connection", result)

    def test_server_error_returns_string(self):
        result = override_text(ServerError())
        self.assertIsNotNone(result)
        self.assertIn("Telegram", result)

    def test_timed_out_returns_string(self):
        result = override_text(TimedOutError())
        self.assertIsNotNone(result)

    def test_module_not_found_returns_string(self):
        result = override_text(ModuleNotFoundError("No module named 'foo'"))
        self.assertIsNotNone(result)
        self.assertIn("foo", result)

    def test_generic_exception_returns_none(self):
        self.assertIsNone(override_text(ValueError("whatever")))

    def test_key_error_returns_none(self):
        self.assertIsNone(override_text(KeyError("k")))

    def test_result_is_html_string(self):
        """override_text must always return str or None, never raise."""
        for exc in [
            FloodWaitError(),
            ServerError(),
            TimedOutError(),
            ModuleNotFoundError("x"),
            ValueError("x"),
        ]:
            result = override_text(exc)
            self.assertIn(type(result), (str, type(None)))


class TestRichException(unittest.TestCase):
    def _raise_and_capture(self, exc):
        try:
            raise exc
        except Exception as e:
            return RichException.from_exc_info(type(e), e, e.__traceback__)

    def test_message_is_str(self):
        rich = self._raise_and_capture(ValueError("boom"))
        self.assertIsInstance(rich.message, str)

    def test_full_stack_is_str(self):
        rich = self._raise_and_capture(ValueError("boom"))
        self.assertIsInstance(rich.full_stack, str)

    def test_message_contains_error_text(self):
        rich = self._raise_and_capture(ValueError("unique_boom_string"))
        self.assertIn("unique_boom_string", rich.message)

    def test_full_stack_not_empty(self):
        rich = self._raise_and_capture(RuntimeError("oops"))
        self.assertTrue(len(rich.full_stack) > 0)

    def test_known_error_uses_override(self):
        """FloodWaitError should use override_text, not the generic format."""
        rich = self._raise_and_capture(FloodWaitError())
        # override says "Flood wait" and does NOT include the raw "❓ Error:" block
        self.assertNotIn("❓ <b>Error:</b>", rich.message)

    def test_unknown_error_uses_generic_format(self):
        rich = self._raise_and_capture(ValueError("generic"))
        self.assertIn("❓", rich.message)

    def test_comment_appears_in_message(self):
        try:
            raise RuntimeError("base")
        except RuntimeError as e:
            rich = RichException.from_exc_info(
                type(e), e, e.__traceback__, comment="ctx"
            )
        self.assertIn("ctx", rich.message)

    def test_no_comment_no_crash(self):
        """from_exc_info must not raise when comment is None."""
        try:
            raise RuntimeError("x")
        except RuntimeError as e:
            rich = RichException.from_exc_info(type(e), e, e.__traceback__)
        self.assertIsNotNone(rich)

    def test_html_escaped_in_message(self):
        """< and > in error text must be HTML-escaped."""
        try:
            raise ValueError("<script>alert(1)</script>")
        except ValueError as e:
            rich = RichException.from_exc_info(type(e), e, e.__traceback__)
        self.assertNotIn("<script>", rich.message)

    def test_source_line_in_message(self):
        """Generic exceptions should report filename and line number."""
        rich = self._raise_and_capture(RuntimeError("traceit"))
        # Either 🎯 Source or the file path appears somewhere
        self.assertTrue("🎯" in rich.message or "test_logger" in rich.message)


class TestSendLogMessage(unittest.TestCase):
    def test_returns_true_on_success(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        result = run(kl.send_log_message("hello"))
        self.assertTrue(result)

    def test_uses_bot_client_when_authorized(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        run(kl.send_log_message("hello"))
        k.bot_client.send_message.assert_called_once()
        k.client.send_message.assert_not_called()

    def test_falls_back_to_user_client(self):
        k = _make_kernel()
        k.bot_client.is_user_authorized = AsyncMock(return_value=False)
        kl = KernelLogger(k)
        run(kl.send_log_message("hello"))
        k.client.send_message.assert_called_once()

    def test_returns_false_when_no_log_chat(self):
        k = _make_kernel(log_chat_id=None)
        kl = KernelLogger(k)
        result = run(kl.send_log_message("hello"))
        self.assertFalse(result)
        k.bot_client.send_message.assert_not_called()

    def test_sends_file_when_provided(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        fake_file = b"data"
        run(kl.send_log_message("caption", file=fake_file))
        k.bot_client.send_file.assert_called_once()

    def test_returns_false_on_exception(self):
        k = _make_kernel()
        k.bot_client.send_message = AsyncMock(side_effect=Exception("net error"))
        kl = KernelLogger(k)
        result = run(kl.send_log_message("hello"))
        self.assertFalse(result)


class TestSendWithRetry(unittest.TestCase):
    def test_retries_on_flood_wait(self):
        k = _make_kernel()
        kl = KernelLogger(k)

        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                e = FloodWaitError()
                e.seconds = 0  # don't actually sleep in tests
                raise e

        with patch("asyncio.sleep", new=AsyncMock()):
            result = run(kl._send_with_retry(factory, max_attempts=2))

        self.assertTrue(result)
        self.assertEqual(call_count, 2)

    def test_gives_up_after_max_attempts(self):
        k = _make_kernel()
        kl = KernelLogger(k)

        async def always_flood():
            e = FloodWaitError()
            e.seconds = 0
            raise e

        with patch("asyncio.sleep", new=AsyncMock()):
            result = run(kl._send_with_retry(always_flood, max_attempts=1))

        self.assertFalse(result)

    def test_returns_false_on_generic_exception(self):
        k = _make_kernel()
        kl = KernelLogger(k)

        async def boom():
            raise RuntimeError("net down")

        result = run(kl._send_with_retry(boom))
        self.assertFalse(result)


class TestHandleError(unittest.TestCase):
    def test_sends_message_to_telegram(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        try:
            raise ValueError("test error")
        except ValueError as e:
            run(kl.handle_error(e, source="test_source"))
        k.bot_client.send_message.assert_called_once()

    def test_deduplication_skips_second_call(self):
        k = _make_kernel()
        k.cache.get.return_value = True
        kl = KernelLogger(k)
        try:
            raise ValueError("dup")
        except ValueError as e:
            run(kl.handle_error(e, source="src"))
        k.bot_client.send_message.assert_not_called()

    def test_message_contains_source(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        try:
            raise RuntimeError("boom")
        except RuntimeError as e:
            run(kl.handle_error(e, source="my_module"))

        call_args = k.bot_client.send_message.call_args
        sent_text = call_args[1].get("message") or call_args[0][1]
        self.assertIn("my_module", sent_text)

    def test_no_log_chat_skips_send(self):
        k = _make_kernel(log_chat_id=None)
        kl = KernelLogger(k)
        try:
            raise RuntimeError("x")
        except RuntimeError as e:
            run(kl.handle_error(e, source="src"))
        k.bot_client.send_message.assert_not_called()

    def test_error_id_cached_for_traceback(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        try:
            raise RuntimeError("cache_me")
        except RuntimeError as e:
            run(kl.handle_error(e, source="src"))

        # cache.set must have been called with a tb_err_* key
        set_keys = [call[0][0] for call in k.cache.set.call_args_list]
        tb_keys = [k_ for k_ in set_keys if k_.startswith("tb_err_")]
        self.assertTrue(len(tb_keys) >= 1)

    def test_sensitive_data_masked_in_sent_message(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        try:
            raise RuntimeError("token='supersecret123'")
        except RuntimeError as e:
            run(kl.handle_error(e, source="src"))

        call_args = k.bot_client.send_message.call_args
        sent_text = call_args[1].get("message") or call_args[0][1]
        self.assertNotIn("supersecret123", sent_text)


class TestConvenienceHelpers(unittest.TestCase):
    def _run_helper(self, method_name, message="test message"):
        k = _make_kernel()
        kl = KernelLogger(k)
        run(getattr(kl, method_name)(message))
        return k

    def test_log_network_sends_globe_emoji(self):
        k = self._run_helper("log_network")
        call_args = k.bot_client.send_message.call_args
        text = call_args[1].get("message") or call_args[0][1]
        self.assertIn("🌐", text)

    def test_log_error_async_sends_red_circle(self):
        k = self._run_helper("log_error_async")
        call_args = k.bot_client.send_message.call_args
        text = call_args[1].get("message") or call_args[0][1]
        self.assertIn("🔴", text)

    def test_log_module_sends_gear_emoji(self):
        k = self._run_helper("log_module")
        call_args = k.bot_client.send_message.call_args
        text = call_args[1].get("message") or call_args[0][1]
        self.assertIn("⚙️", text)

    def test_helpers_also_call_file_logger(self):
        k = self._run_helper("log_network")
        k.logger.info.assert_called_once_with("test message")


class TestStripHtml(unittest.TestCase):
    def test_removes_simple_tags(self):
        result = strip_html("<b>bold</b> text")
        self.assertEqual(result, "bold text")

    def test_removes_nested_tags(self):
        result = strip_html("<pre><code>x = 1</code></pre>")
        self.assertEqual(result, "x = 1")

    def test_preserves_text_without_tags(self):
        result = strip_html("plain text")
        self.assertEqual(result, "plain text")

    def test_empty_string(self):
        self.assertEqual(strip_html(""), "")


class TestErrorFormatter(unittest.TestCase):
    def test_format_traceback_line_with_file(self):
        line = '  File "/path/to/file.py", line 42, in main'
        result = ErrorFormatter.format_traceback_line(line)
        self.assertIn("file.py:42", result)
        self.assertIn("main", result)

    def test_format_traceback_line_without_file(self):
        line = "some random line"
        result = ErrorFormatter.format_traceback_line(line)
        self.assertIn("some random line", result)

    def test_format_full_traceback(self):
        raw_tb = (
            '  File "x.py", line 1, in <module>\n  File "y.py", line 2, in <module>'
        )
        result = ErrorFormatter.format_full_traceback(raw_tb)
        self.assertIn("x.py", result)
        self.assertIn("y.py", result)

    def test_find_source_location_returns_first_match(self):
        raw_tb = '  File "a.py", line 10, in foo\n  File "b.py", line 20, in bar'
        result = ErrorFormatter.find_source_location(raw_tb)
        self.assertEqual(result[0], "b.py")
        self.assertEqual(result[1], "20")
        self.assertEqual(result[2], "bar")

    def test_find_source_location_returns_none_for_empty(self):
        self.assertEqual(ErrorFormatter.find_source_location(""), (None, None, None))


class TestTelegramLogHandler(unittest.TestCase):
    def test_queue_size_starts_at_zero(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        handler = TelegramLogHandler(kl, batch_size=5, batch_interval=0.1)
        self.assertEqual(handler.queue_size(), 0)

    def test_emit_adds_to_queue(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        handler = TelegramLogHandler(kl, batch_size=5, batch_interval=0.1)
        handler.emit("test message")
        self.assertEqual(handler.queue_size(), 1)

    def test_emit_ignores_when_shutdown(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        handler = TelegramLogHandler(kl)
        handler._shutdown = True
        handler.emit("test")
        self.assertEqual(handler.queue_size(), 0)

    def test_rate_limit_detection(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        handler = TelegramLogHandler(kl, rate_limit=2, rate_window=60)
        import time

        now = time.time()
        handler._rate_timestamps.extend([now - 10, now - 5])
        self.assertTrue(handler._is_rate_limited(now))

    def test_clean_rate_timestamps_removes_old(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        handler = TelegramLogHandler(kl, rate_window=30)
        import time

        now = time.time()
        handler._rate_timestamps = [now - 100, now - 50, now - 10]
        handler._clean_rate_timestamps(now)
        self.assertEqual(len(handler._rate_timestamps), 1)


class TestSetupTelegramLogging(unittest.TestCase):
    def test_returns_telegram_log_handler(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        logger = logging.getLogger("test_telegram_log")
        logger.handlers = []
        handler = setup_telegram_logging(logger, kl)
        self.assertIsInstance(handler, TelegramLogHandler)

    def test_adds_bridge_handler(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        logger = logging.getLogger("test_bridge_log")
        logger.handlers = []
        setup_telegram_logging(logger, kl)
        self.assertTrue(any(isinstance(h, _SyncToAsyncBridge) for h in logger.handlers))


class TestKernelLoggerProperties(unittest.TestCase):
    def test_log_chat_id_from_kernel(self):
        k = _make_kernel(log_chat_id=999)
        kl = KernelLogger(k)
        self.assertEqual(kl.log_chat_id, 999)

    def test_log_chat_id_explicit_overrides(self):
        k = _make_kernel(log_chat_id=999)
        kl = KernelLogger(k, log_chat_id=888)
        self.assertEqual(kl.log_chat_id, 888)

    def test_client_uses_fallback(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        self.assertEqual(kl.client, k.client)

    def test_client_explicit_overrides(self):
        custom_client = AsyncMock()
        k = _make_kernel()
        kl = KernelLogger(k, client=custom_client)
        self.assertEqual(kl.client, custom_client)

    def test_bot_client_explicit_overrides(self):
        custom_bot = AsyncMock()
        k = _make_kernel()
        kl = KernelLogger(k, bot_client=custom_bot)
        self.assertEqual(kl.bot_client, custom_bot)

    def test_cache_uses_fallback(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        self.assertEqual(kl.cache, k.cache)

    def test_cache_explicit_overrides(self):
        custom_cache = MagicMock()
        k = _make_kernel()
        kl = KernelLogger(k, cache=custom_cache)
        self.assertEqual(kl.cache, custom_cache)


class TestSendErrorLog(unittest.TestCase):
    def test_sends_simple_error(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        run(kl.send_error_log("test error", "test_source"))
        k.bot_client.send_message.assert_called_once()

    def test_respects_max_text_length(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        long_text = "x" * 1000
        run(kl.send_error_log(long_text, "src"))
        call_args = k.bot_client.send_message.call_args
        text = call_args[0][1] if call_args[0] else call_args[1].get("message", "")
        self.assertLessEqual(len(text), 2000)

    def test_no_log_chat_skips_send(self):
        k = _make_kernel(log_chat_id=None)
        kl = KernelLogger(k)
        run(kl.send_error_log("error", "src"))
        k.bot_client.send_message.assert_not_called()


class TestLogErrorFromExc(unittest.TestCase):
    def test_sends_rich_exception(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        try:
            raise ValueError("boom")
        except ValueError:
            run(kl.log_error_from_exc("test_src"))
        k.bot_client.send_message.assert_called_once()

    def test_deduplication_works(self):
        k = _make_kernel()
        k.cache.get.return_value = True
        kl = KernelLogger(k)
        try:
            raise ValueError("dup")
        except ValueError:
            run(kl.log_error_from_exc("src"))
        k.bot_client.send_message.assert_not_called()

    def test_no_exc_info_returns_early(self):
        k = _make_kernel()
        kl = KernelLogger(k)
        result = run(kl.log_error_from_exc("src"))
        k.bot_client.send_message.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
