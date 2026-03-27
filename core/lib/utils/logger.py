import asyncio
import html
import inspect
import logging
import os
import re
import sys
import traceback
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from logging.handlers import RotatingFileHandler
from types import TracebackType
from typing import IO, TYPE_CHECKING, Protocol, cast, runtime_checkable

from telethon import Button
from telethon.errors import (
    FloodWaitError,
    NetworkMigrateError,
    ServerError,
    TimedOutError,
)

if TYPE_CHECKING:
    from telethon import TelegramClient


@runtime_checkable
class CacheProtocol(Protocol):
    """Protocol for cache objects."""

    def get(self, key: str, default: object = None) -> object: ...
    def set(self, key: str, value: object, ttl: int = ...) -> None: ...


# Configuration constants
_LOG_DIR = "logs"
_LOG_FILE = f"{_LOG_DIR}/kernel.log"
_LOG_MAX_BYTES = 10 * 1024 * 1024
_LOG_BACKUP_COUNT = 5
_DEDUP_TTL = 60
_TRACE_CACHE_TTL = 300
_AUTHORIZATION_CACHE_TTL = 10
_STACK_INSPECT_DEPTH = 10
_MAX_ERROR_TEXT_LEN = 500
_MAX_MESSAGE_INFO_LEN = 300
_MAX_EVENT_TEXT_LEN = 200
_MAX_RETRIES = 2

# Telegram log handler settings
_TELEGRAM_LOG_BATCH_SIZE = 5
_TELEGRAM_LOG_BATCH_INTERVAL = 2.0
_TELEGRAM_LOG_RATE_LIMIT = 10
_TELEGRAM_LOG_RATE_WINDOW = 60

# Regex patterns for sensitive data masking
_EMOJI_ID_RE = re.compile(r'emoji-id=["\'](\d+)["\']', re.IGNORECASE)
_TOKEN_RE = re.compile(
    r"""token(?:['"\s:=]|&#x27;|&quot;)+(?:['"\s]|&#x27;|&quot;)?([A-Za-z0-9_\-:,.]+)""",
    re.IGNORECASE,
)
_API_ID_RE = re.compile(
    r"""api[_-]?id(?:['"\s:=]|&#x27;|&quot;)+(?:['"\s]|&#x27;|&quot;)?(\d+)""",
    re.IGNORECASE,
)
_API_HASH_RE = re.compile(
    r"""api[_-]?hash(?:['"\s:=]|&#x27;|&quot;)+(?:['"\s]|&#x27;|&quot;)?([A-Za-z0-9_-]+)""",
    re.IGNORECASE,
)
_PASSWORD_RE = re.compile(
    r"""password(?:['"\s:=]|&#x27;|&quot;)+(?:['"\s]|&#x27;|&quot;)?([^\s"'&]+)""",
    re.IGNORECASE,
)
_SESSION_RE = re.compile(
    r"""session(?:['"\s:=]|&#x27;|&quot;)+(?:['"\s]|&#x27;|&quot;)?([A-Za-z0-9_-]+)""",
    re.IGNORECASE,
)
_LONG_NUMBERS_RE = re.compile(r"\b\d{10,}\b")
_AUTH_HEADER_RE = re.compile(r"Authorization:\s*.+", re.IGNORECASE)

SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (_TOKEN_RE, 'token="***"'),
    (_API_ID_RE, "api_id=***"),
    (_API_HASH_RE, "api_hash=***"),
    (_PASSWORD_RE, "password=***"),
    (_SESSION_RE, "session=***"),
    (_AUTH_HEADER_RE, "Authorization: ***"),
]


def _mask_long_numbers(m: re.Match[str]) -> str:
    """Mask a long number sequence."""
    return "X" * len(m.group())


def mask_sensitive_data(text: str) -> str:
    """Mask sensitive data in text before HTML escaping."""
    if not text:
        return text

    placeholders: dict[str, str] = {}

    def _stash(m: re.Match[str]) -> str:
        key = f"\x00EMOJIID{len(placeholders)}\x00"
        placeholders[key] = m.group(0)
        return key

    protected = _EMOJI_ID_RE.sub(_stash, text)

    masked = protected
    masked = _LONG_NUMBERS_RE.sub(_mask_long_numbers, masked)
    for pattern, replacement in SENSITIVE_PATTERNS:
        masked = pattern.sub(replacement, masked)

    for key, original in placeholders.items():
        masked = masked.replace(key, original)

    return masked


def override_text(exception: Exception) -> str | None:
    """Return a user-friendly HTML string for well-known error types."""
    match exception:
        case TimedOutError() | NetworkMigrateError():
            return "✈️ <b>Connection problems on the server.</b>"
        case ServerError():
            return "📡 <b>Telegram servers are currently experiencing issues.</b>"
        case FloodWaitError() as e:
            return f"✋ <b>Flood wait triggered — retry in {e.seconds}s.</b>"
        case ModuleNotFoundError():
            detail = traceback.format_exception_only(type(exception), exception)[0]
            detail = detail.split(":", 1)[-1].strip()
            return f"📦 <b>Missing module:</b> <code>{html.escape(detail)}</code>"
        case _:
            return None


_LINE_RE = re.compile(r'  File "(.*?)", line ([0-9]+), in (.+)')

_LOGGER_FRAMES = frozenset(
    {
        "handle_error",
        "from_exc_info",
        "log_error_from_exc",
        "_send_error_with_traceback",
        "<module>",
    }
)


class ErrorFormatter:
    """Converts exceptions to HTML messages."""

    @staticmethod
    def format_traceback_line(line: str) -> str:
        """Format a single traceback line to HTML."""
        m = _LINE_RE.search(line)
        if m:
            fn_, ln_, nm_ = m.groups()
            return (
                f"👉 <code>{html.escape(fn_)}:{ln_}</code>"
                f" <b>in</b> <code>{html.escape(nm_)}</code>"
            )
        return f"<code>{html.escape(line)}</code>"

    @classmethod
    def format_full_traceback(cls, raw_tb: str) -> str:
        """Format full traceback to HTML."""
        return "\n".join(map(cls.format_traceback_line, raw_tb.splitlines()))

    @classmethod
    def find_source_location(
        cls, raw_tb: str
    ) -> tuple[str | None, str | None, str | None]:
        """Find deepest file reference for the Source: line."""
        result: tuple[str | None, str | None, str | None] = (None, None, None)
        for line in reversed(raw_tb.splitlines()):
            m = _LINE_RE.search(line)
            if m:
                return cast(tuple[str | None, str | None, str | None], m.groups())
        return result

    @classmethod
    def find_caller_info(cls) -> str:
        """Find information about the calling code."""
        for frame_info in inspect.stack()[:_STACK_INSPECT_DEPTH]:
            fn = frame_info.frame.f_locals.get("self")
            func = frame_info.function
            if fn and func not in _LOGGER_FRAMES:
                return (
                    f'<blockquote><tg-emoji emoji-id="5426900601101374618">🧿</tg-emoji> <b>Cause:</b> <code>{html.escape(func)}</code>'
                    f" of <code>{html.escape(type(fn).__name__)}</code></blockquote>\n"
                )
        return ""

    @classmethod
    def format_exception(
        cls,
        exc_type: type,
        exc_value: Exception,
        tb,
        comment: str | None = None,
    ) -> tuple[str, str]:
        """Format exception to HTML message and masked traceback."""
        raw_tb = "".join(traceback.format_exception(exc_type, exc_value, tb)).replace(
            "Traceback (most recent call last):\n", ""
        )

        filename, lineno, name = cls.find_source_location(raw_tb)
        masked_tb = mask_sensitive_data(raw_tb)
        full_stack_html = cls.format_full_traceback(masked_tb)

        caller_info = cls.find_caller_info()
        override = override_text(exc_value)
        if override:
            comment_part = ""
            if comment:
                safe_comment = mask_sensitive_data(str(comment))
                comment_part = f'\n<blockquote><tg-emoji emoji-id="5465300082628763143">💬</tg-emoji> <b>Message:</b> <code>{html.escape(safe_comment)}</code></blockquote>'
            message = f"{caller_info}{override}{comment_part}"
        else:
            err_only = html.escape(
                mask_sensitive_data(
                    "".join(
                        traceback.format_exception_only(exc_type, exc_value)
                    ).strip()
                )
            )
            src_part = (
                f'<blockquote><tg-emoji emoji-id="5379679518740978720">🎯</tg-emoji> <b>Source:</b> <code>{html.escape(filename or "")}:{lineno or ""}</code>'
                f" <b>in</b> <code>{html.escape(name or '')}</code></blockquote>\n"
                if filename
                else ""
            )
            comment_part = ""
            if comment:
                safe_comment = mask_sensitive_data(str(comment))
                comment_part = f'\n<blockquote><tg-emoji emoji-id="5465300082628763143">💬</tg-emoji> <b>Message:</b> <code>{html.escape(safe_comment)}</code></blockquote>'
            message = (
                f"{caller_info}{src_part}"
                f'<tg-emoji emoji-id="5469903029144657419">❓</tg-emoji> <u><b>Error:</b></u> <pre><code class="language-python">{err_only}</code></pre>'
                f"{comment_part}"
            )

        return message, full_stack_html


class RichException:
    """Holds a formatted HTML message and the full traceback for an exception."""

    def __init__(self, message: str, full_stack: str) -> None:
        self.message = message
        self.full_stack = full_stack

    @classmethod
    def from_exc_info(
        cls,
        exc_type: type,
        exc_value: Exception,
        tb,
        comment: str | None = None,
    ) -> "RichException":
        message, full_stack = ErrorFormatter.format_exception(
            exc_type, exc_value, tb, comment
        )
        return cls(message=message, full_stack=full_stack)


def setup_logging() -> logging.Logger:
    """Create and configure the rotating file logger for the kernel."""
    os.makedirs(_LOG_DIR, exist_ok=True)

    logger = logging.getLogger("kernel")
    logger.setLevel(logging.INFO)

    class _NoiseFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if record.levelno >= logging.ERROR:
                return True
            msg = record.getMessage()
            return "Failed to fetch updates" not in msg and "Sleep" not in msg

    handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    handler.addFilter(_NoiseFilter())
    logger.addHandler(handler)

    telethon_logger = logging.getLogger("telethon")
    telethon_logger.setLevel(logging.WARNING)
    telethon_logger.addFilter(_NoiseFilter())

    return logger


class _SyncToAsyncBridge(logging.Handler):
    """Bridge that forwards sync log records to async TelegramLogHandler."""

    def __init__(self, telegram_handler: "TelegramLogHandler") -> None:
        super().__init__(level=logging.WARNING)
        self._telegram_handler = telegram_handler

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._telegram_handler.emit(msg)
        except Exception:
            self.handleError(record)


def setup_telegram_logging(
    logger: logging.Logger,
    kernel_logger: "KernelLogger",
    *,
    batch_size: int = _TELEGRAM_LOG_BATCH_SIZE,
    batch_interval: float = _TELEGRAM_LOG_BATCH_INTERVAL,
    rate_limit: int = _TELEGRAM_LOG_RATE_LIMIT,
    rate_window: int = _TELEGRAM_LOG_RATE_WINDOW,
) -> "TelegramLogHandler":
    """Attach a TelegramLogHandler to a logger for WARNING and ERROR level messages."""
    handler = TelegramLogHandler(
        kernel_logger,
        batch_size=batch_size,
        batch_interval=batch_interval,
        rate_limit=rate_limit,
        rate_window=rate_window,
    )

    bridge = _SyncToAsyncBridge(handler)
    bridge.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(bridge)
    return handler


if TYPE_CHECKING:
    from kernel import Kernel


class KernelLogger:
    """Error logging, log-chat messaging, and error formatting helpers."""

    def __init__(
        self,
        kernel: "Kernel",
        *,
        log_chat_id: int | None = None,
        client: "TelegramClient | None" = None,
        bot_client: "TelegramClient | None" = None,
        cache: object | None = None,
    ) -> None:
        self.k = kernel
        self._log_chat_id = log_chat_id
        self._client = client
        self._bot_client = bot_client
        self._cache = cache

        self._send_lock = asyncio.Lock()
        self._auth_cache: tuple[bool, datetime] | None = None

    @property
    def log_chat_id(self) -> int | None:
        if self._log_chat_id is not None:
            return self._log_chat_id
        return getattr(self.k, "log_chat_id", None)

    @property
    def client(self) -> "TelegramClient":
        return self._client or self.k.client

    @property
    def bot_client(self) -> "TelegramClient | None":
        if self._bot_client is not None:
            return self._bot_client
        return getattr(self.k, "bot_client", None)

    @property
    def cache(self) -> CacheProtocol | None:
        if self._cache is not None:
            return cast(CacheProtocol, self._cache)
        return cast(CacheProtocol | None, getattr(self.k, "cache", None))

    def _has_cache(self) -> bool:
        """Check if cache is available."""
        return self.cache is not None and isinstance(self.cache, CacheProtocol)

    async def _get_client(self) -> "TelegramClient":
        """Pick bot_client when available and authorised, else fall back to user client."""
        now = datetime.now()

        if self._auth_cache is not None:
            is_auth, cached_at = self._auth_cache
            if (now - cached_at).total_seconds() < _AUTHORIZATION_CACHE_TTL:
                if is_auth and self.bot_client:
                    return self.bot_client
                return self.client

        bc = self.bot_client
        if bc:
            try:
                if await bc.is_user_authorized():
                    self._auth_cache = (True, now)
                    return bc
            except (TimedOutError, NetworkMigrateError, ServerError) as e:
                self.k.logger.debug(f"Temporary error checking bot auth: {e}")
                return self.client
            except Exception:
                self._auth_cache = (False, now)
                return self.client

        self._auth_cache = (False, now)
        return self.client

    async def _send_with_retry(
        self,
        coro_factory: Callable[[], Awaitable[None]],
        *,
        max_attempts: int = _MAX_RETRIES,
    ) -> bool:
        """Execute coro_factory() with automatic FloodWait retry."""
        _NETWORK_ERRORS = (
            TimedOutError,
            NetworkMigrateError,
            ServerError,
            ConnectionError,
            OSError,
        )

        for attempt in range(max_attempts + 1):
            try:
                await coro_factory()
                return True
            except FloodWaitError as e:
                if attempt < max_attempts:
                    await asyncio.sleep(e.seconds)
                else:
                    self.k.logger.warning(f"Flood wait exceeded retries: {e.seconds}s")
                    return False
            except _NETWORK_ERRORS as e:
                if attempt < max_attempts:
                    self._auth_cache = None
                    await asyncio.sleep(2**attempt)
                else:
                    self.k.logger.warning(
                        f"Network error after {max_attempts} retries: {e}"
                    )
                    return False
            except Exception as e:
                self.k.logger.error(f"Log message send failed: {e}")
                return False

        return False

    async def send_log_message(self, text: str, file: IO | str | None = None) -> bool:
        """Send a message to the configured log chat."""
        if not self.log_chat_id:
            return False

        client = await self._get_client()
        if not client or not client.is_connected():
            return False

        safe_text = mask_sensitive_data(text)
        async with self._send_lock:

            async def _do_send():
                if file:
                    await client.send_file(
                        self.log_chat_id, file, caption=safe_text, parse_mode="html"
                    )
                else:
                    await client.send_message(
                        self.log_chat_id, safe_text, parse_mode="html"
                    )

            success = await self._send_with_retry(_do_send)
            if not success:
                self.k.logger.warning(f"Failed to send log message: {safe_text[:100]}")
            return success

    async def _send_error_with_traceback(
        self,
        body: str,
        masked_traceback: str,
        *,
        error_id: str | None = None,
    ) -> bool:
        """Send error message with optional traceback button."""
        if not self.log_chat_id:
            return False

        if error_id and self.cache:
            self.cache.set(f"tb_{error_id}", masked_traceback, ttl=_TRACE_CACHE_TTL)

        safe_body = mask_sensitive_data(body)
        async with self._send_lock:
            client = await self._get_client()

            async def _do_send():
                await client.send_message(
                    self.log_chat_id,
                    safe_body,
                    buttons=[Button.inline("🔍 Traceback", data=f"show_tb:{error_id}")],
                    parse_mode="html",
                )

            success = await self._send_with_retry(_do_send)
            if not success:
                self.k.logger.error("Could not send error log")
                self.k.logger.error("Original traceback: %s", masked_traceback[:500])
            return success

    async def send_error_log(
        self,
        error_text: str,
        source_file: str,
        message_info: str = "",
        exc_info: tuple[type, Exception, TracebackType] | None = None,
    ) -> None:
        """Format and send a simple error to the log chat."""
        if not self.log_chat_id:
            return

        safe_error = mask_sensitive_data(error_text[:_MAX_ERROR_TEXT_LEN])
        safe_source = mask_sensitive_data(source_file)
        safe_source_esc = html.escape(safe_source)

        error_id: str | None = None
        masked_tb = ""
        if exc_info:
            error_id = f"err_{uuid.uuid4().hex[:8]}"
            raw_tb = "".join(traceback.format_exception(*exc_info))
            masked_tb = mask_sensitive_data(raw_tb)

        body = (
            f'<blockquote><tg-emoji emoji-id="5379679518740978720">🎯</tg-emoji> <b>Source:</b> <code>{safe_source_esc}</code>\n'
            f'<blockquote><tg-emoji emoji-id="5426900601101374618">🧿</tg-emoji> <b>Error:</b> <code>{html.escape(safe_error)}</code></blockquote>'
            f"</blockquote>"
        )
        if message_info:
            safe_msg = mask_sensitive_data(message_info[:_MAX_MESSAGE_INFO_LEN])
            body += (
                f'\n<tg-emoji emoji-id="5298499667569425533">🃏</tg-emoji> '
                f"<blockquote><b>Message:</b> <code>{html.escape(safe_msg)}</code></blockquote>"
            )

        if error_id:
            await self._send_error_with_traceback(body, masked_tb, error_id=error_id)
        else:
            await self.send_log_message(body)

    async def handle_error(
        self, error: Exception, source: str = "unknown", event=None
    ) -> None:
        """Log an error to file and send a formatted report to the log chat."""
        if not self.log_chat_id:
            return

        cache = self.cache
        signature = f"error:{source}:{type(error).__name__}:{error}"
        if cache and cache.get(signature):
            return
        if cache:
            cache.set(signature, True, ttl=_DEDUP_TTL)

        error_id = f"err_{uuid.uuid4().hex[:8]}"
        exc_info = (type(error), error, error.__traceback__)
        rich = RichException.from_exc_info(*exc_info)

        src_esc = html.escape(source or "unknown", quote=False)
        body = f'<blockquote><tg-emoji emoji-id="5372846474881146350">🔭</tg-emoji> <b>Source Message:</b> <code>{src_esc}</code></blockquote>\n{rich.message}'

        if event:
            try:
                chat_title = getattr(event.chat, "title", "DM")
                user_info = (
                    await self.k.get_user_info(event.sender_id)
                    if event.sender_id
                    else "unknown"
                )
                txt = mask_sensitive_data(event.text or "")[:_MAX_EVENT_TEXT_LEN]
                safe_user_info = mask_sensitive_data(str(user_info))
                safe_chat_title = mask_sensitive_data(str(chat_title))
                body += (
                    f'\n<tg-emoji emoji-id="5298499667569425533">🃏</tg-emoji> <b>Message info:</b>\n'
                    f"<blockquote>🪬 <b>User:</b> {html.escape(safe_user_info)}\n"
                    f"⌨️ <b>Text:</b> <code>{html.escape(txt)}</code>\n"
                    f"📬 <b>Chat:</b> {html.escape(safe_chat_title)}</blockquote>"
                )
            except Exception:
                pass

        safe_stack = mask_sensitive_data(rich.full_stack[:500])
        self.k.logger.error("Error in %s:\n%s", source, safe_stack)

        await self._send_error_with_traceback(body, rich.full_stack, error_id=error_id)

    async def log(self, message: str, emoji: str = "ℹ️") -> None:  # noqa: RUF001
        """Send an event to the log chat and write it to the rotating log file."""
        safe_message = mask_sensitive_data(message)
        success = await self.send_log_message(f"{emoji} {safe_message}")
        if success:
            self.k.logger.info(safe_message)
        else:
            self.k.logger.warning(f"Log message not sent: {safe_message[:100]}")

    async def log_network(self, message: str) -> None:
        """Send a network event to the log chat."""
        await self.log(message, "🌐")

    async def log_error_async(self, message: str) -> None:
        """Send an error event to the log chat."""
        await self.log(message, "🔴")

    async def log_module(self, message: str) -> None:
        """Send a module event to the log chat."""
        await self.log(message, "⚙️")

    async def log_error_from_exc(self, source: str = "unknown") -> None:
        """Send an error to the log chat using RichException for beautiful formatting."""
        exc_info = sys.exc_info()
        exc_type, exc_value, tb = exc_info
        if exc_type is None or exc_value is None:
            return
        if not self.log_chat_id:
            return

        cache = self.cache
        signature = f"error:{source}:{exc_type.__name__}:{exc_value}"
        if cache and cache.get(signature):
            return
        if cache:
            cache.set(signature, True, ttl=_DEDUP_TTL)

        rich = RichException.from_exc_info(exc_type, cast(Exception, exc_value), tb)
        error_id = f"err_{uuid.uuid4().hex[:8]}"

        safe_stack = mask_sensitive_data(rich.full_stack[:500])
        self.k.logger.error("Error in %s:\n%s", source, safe_stack)

        await self._send_error_with_traceback(
            rich.message, rich.full_stack, error_id=error_id
        )


_RAW_LOG_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \[")


class TelegramLogHandler:
    """Async handler that sends ERROR logs to Telegram with flood protection."""

    def __init__(
        self,
        kernel_logger: KernelLogger,
        *,
        batch_size: int = _TELEGRAM_LOG_BATCH_SIZE,
        batch_interval: float = _TELEGRAM_LOG_BATCH_INTERVAL,
        rate_limit: int = _TELEGRAM_LOG_RATE_LIMIT,
        rate_window: int = _TELEGRAM_LOG_RATE_WINDOW,
        dedup_ttl: int = _DEDUP_TTL,
    ) -> None:
        self._kernel_logger = kernel_logger
        self._batch_size = batch_size
        self._batch_interval = batch_interval
        self._rate_limit = rate_limit
        self._rate_window = rate_window
        self._dedup_ttl = dedup_ttl

        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._shutdown = False

        self._rate_timestamps: list[float] = []

    async def start(self) -> None:
        """Start the background worker task."""
        if self._task is None or self._task.done():
            self._shutdown = False
            self._task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        """Stop the handler gracefully."""
        self._shutdown = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def emit(self, message: str) -> None:
        """Queue a log message for sending (thread-safe)."""
        if self._shutdown:
            return
        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            pass
        except Exception:
            pass

    def queue_size(self) -> int:
        """Get current queue size for debugging."""
        return self._queue.qsize()

    def _clean_rate_timestamps(self, now: float) -> None:
        """Remove timestamps outside the rate window."""
        cutoff = now - self._rate_window
        while self._rate_timestamps and self._rate_timestamps[0] < cutoff:
            self._rate_timestamps.pop(0)

    def _is_rate_limited(self, now: float) -> bool:
        """Check if rate limit is exceeded."""
        self._clean_rate_timestamps(now)
        return len(self._rate_timestamps) >= self._rate_limit

    async def _worker(self) -> None:
        """Background worker that processes queued messages."""
        batch: list[str] = []

        while not self._shutdown:
            try:
                try:
                    message = await asyncio.wait_for(
                        self._queue.get(), timeout=self._batch_interval
                    )
                    batch.append(message)

                    if len(batch) >= self._batch_size:
                        await self._flush_batch(batch)
                        batch = []
                except TimeoutError:
                    if batch:
                        await self._flush_batch(batch)
                        batch = []

            except asyncio.CancelledError:
                if batch:
                    await self._flush_batch(batch)
                raise
            except Exception:
                pass

    async def _flush_batch(self, batch: list[str]) -> None:
        """Send accumulated messages to Telegram with deduplication."""
        if not batch:
            return

        cache = self._kernel_logger.cache
        seen: set[str] = set()
        unique_messages: list[str] = []

        for msg in batch:
            safe_msg = mask_sensitive_data(msg)
            if not safe_msg.strip():
                continue

            sig = f"tlog:{safe_msg}"

            if cache and cache.get(sig):
                continue

            if sig in seen:
                continue

            seen.add(sig)
            unique_messages.append(safe_msg)

            if cache:
                cache.set(sig, True, ttl=self._dedup_ttl)

        if not unique_messages:
            return

        now = datetime.now().timestamp()
        self._clean_rate_timestamps(now)

        if len(self._rate_timestamps) >= self._rate_limit:
            return

        if unique_messages:
            self._rate_timestamps.append(now)

        if len(unique_messages) == 1:
            text = f"<code>{html.escape(unique_messages[0])}</code>"
        else:
            lines = [
                f"<code>{html.escape(line)}</code>"
                for line in unique_messages[: self._batch_size]
            ]
            text = "\n".join(lines)
            if len(unique_messages) > self._batch_size:
                text += f"\n<blockquote>... and {len(unique_messages) - self._batch_size} more errors</blockquote>"

        await self._kernel_logger.send_log_message(text)
