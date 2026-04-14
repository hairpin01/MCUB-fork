# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations
import asyncio
import hashlib
import html
import inspect
import io
import logging
import os
import re
import sys
import traceback
import uuid
from collections import deque
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


_LOG_DIR = "logs"
_LOG_FILE = f"{_LOG_DIR}/kernel.log"
_LOG_MAX_BYTES = 10 * 1024 * 1024
_LOG_BACKUP_COUNT = 5
_CONSOLE_LOG_LEVEL = logging.WARNING
_DEDUP_TTL = 60
_TRACE_CACHE_TTL = 300
_AUTHORIZATION_CACHE_TTL = 10
_STACK_INSPECT_DEPTH = 10
_MAX_ERROR_TEXT_LEN = 500
_MAX_MESSAGE_INFO_LEN = 300
_MAX_EVENT_TEXT_LEN = 200
_MAX_RETRIES = 2

# Mute / lifetime / similar
_MUTE_TTL = 3600  # seconds — default "Mute 1h"
_FIRST_SEEN_TTL = 86400  # 24 h — how long we remember first occurrence
_SIMILAR_MAX = 5  # max error IDs stored per source-function slot
_LOG_TAIL_LINES = 50  # lines to attach when an error is critical
_CRITICAL_REPEAT_THRESHOLD = 5  # attach log file after this many repeats

# Telegram log handler settings
_TELEGRAM_LOG_BATCH_SIZE = 5
_TELEGRAM_LOG_BATCH_INTERVAL = 2.0
_TELEGRAM_LOG_RATE_LIMIT = 10
_TELEGRAM_LOG_RATE_WINDOW = 60

_NETWORK_ERRORS = (
    TimedOutError,
    NetworkMigrateError,
    ServerError,
    ConnectionError,
    OSError,
)

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
    masked = _LONG_NUMBERS_RE.sub(_mask_long_numbers, protected)
    for pattern, replacement in SENSITIVE_PATTERNS:
        masked = pattern.sub(replacement, masked)
    for key, original in placeholders.items():
        masked = masked.replace(key, original)

    return masked


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Remove HTML tags for plain text logging."""
    return _HTML_TAG_RE.sub("", text)


def _sig_hash(text: str) -> str:
    """Short, stable MD5 hex digest used as a compact cache key."""
    return hashlib.md5(text.encode()).hexdigest()[:16]


def override_text(exception: Exception) -> str | None:
    """Return a user-friendly HTML string for well-known error types."""
    # Use isinstance — faster and robust against subclassing
    if isinstance(exception, (TimedOutError, NetworkMigrateError)):
        return "✈️ <b>Connection problems on the server.</b>"
    if isinstance(exception, ServerError):
        return "📡 <b>Telegram servers are currently experiencing issues.</b>"
    if isinstance(exception, FloodWaitError):
        seconds = getattr(exception, "seconds", 0)
        return f"✋ <b>Flood wait triggered — retry in {seconds}s.</b>"
    if isinstance(exception, ModuleNotFoundError):
        detail = traceback.format_exception_only(type(exception), exception)[0]
        detail = detail.split(":", 1)[-1].strip()
        return f"📦 <b>Missing module:</b> <code>{html.escape(detail)}</code>"
    return None


class _NoiseFilter(logging.Filter):
    """Suppress noisy telethon messages below ERROR level."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.ERROR:
            return True
        msg = record.getMessage()
        return "Failed to fetch updates" not in msg and "Sleep" not in msg


class _WarningConsoleFilter(logging.Filter):
    """Allow only warning-and-above records to the terminal."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= _CONSOLE_LOG_LEVEL


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
        for line in reversed(raw_tb.splitlines()):
            m = _LINE_RE.search(line)
            if m:
                return cast(tuple[str | None, str | None, str | None], m.groups())
        return (None, None, None)

    @classmethod
    def find_caller_info(cls) -> str:
        """Find information about the calling code."""
        for frame_info in inspect.stack()[:_STACK_INSPECT_DEPTH]:
            fn = frame_info.frame.f_locals.get("self")
            func = frame_info.function
            if fn and func not in _LOGGER_FRAMES:
                return (
                    f'<blockquote><tg-emoji emoji-id="5426900601101374618">🧿</tg-emoji>'
                    f" <b>Cause:</b> <code>{html.escape(func)}</code>"
                    f" of <code>{html.escape(type(fn).__name__)}</code></blockquote>\n"
                )
        return ""

    @classmethod
    def format_exception(
        cls,
        exc_type: type,
        exc_value: Exception,
        tb: TracebackType | None,
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
                comment_part = (
                    f'\n<blockquote><tg-emoji emoji-id="5465300082628763143">💬</tg-emoji>'
                    f" <b>Message:</b> <code>{html.escape(safe_comment)}</code></blockquote>"
                )
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
                f'<blockquote><tg-emoji emoji-id="5379679518740978720">🎯</tg-emoji>'
                f' <b>Source:</b> <code>{html.escape(filename or "")}:{lineno or ""}</code>'
                f" <b>in</b> <code>{html.escape(name or '')}</code></blockquote>\n"
                if filename
                else ""
            )
            comment_part = ""
            if comment:
                safe_comment = mask_sensitive_data(str(comment))
                comment_part = (
                    f'\n<blockquote><tg-emoji emoji-id="5465300082628763143">💬</tg-emoji>'
                    f" <b>Message:</b> <code>{html.escape(safe_comment)}</code></blockquote>"
                )
            message = (
                f"{caller_info}{src_part}"
                f'<tg-emoji emoji-id="5469903029144657419">❓</tg-emoji>'
                f' <u><b>Error:</b></u> <pre><code class="language-python">{err_only}</code></pre>'
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
        tb: TracebackType | None,
        comment: str | None = None,
    ) -> "RichException":
        message, full_stack = ErrorFormatter.format_exception(
            exc_type, exc_value, tb, comment
        )
        return cls(message=message, full_stack=full_stack)


def setup_logging() -> logging.Logger:
    """Create and configure the rotating file logger for the kernel."""
    os.makedirs(_LOG_DIR, exist_ok=True)

    root_logger = logging.getLogger()
    kernel_logger = logging.getLogger("kernel")
    mcub_logger = logging.getLogger("mcub")

    root_logger.setLevel(logging.DEBUG)
    kernel_logger.setLevel(logging.DEBUG)
    mcub_logger.setLevel(logging.DEBUG)

    log_path = os.path.abspath(_LOG_FILE)
    handler = None
    for existing in root_logger.handlers:
        if (
            isinstance(existing, RotatingFileHandler)
            and os.path.abspath(getattr(existing, "baseFilename", "")) == log_path
        ):
            handler = existing
            break

    if handler is None:
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
        root_logger.addHandler(handler)

    console_handler = None
    for existing in root_logger.handlers:
        if getattr(existing, "_mcub_console_handler", False):
            console_handler = existing
            break

    if console_handler is None:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler._mcub_console_handler = True
        console_handler.setLevel(_CONSOLE_LOG_LEVEL)
        console_handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        )
        console_handler.addFilter(_NoiseFilter())
        console_handler.addFilter(_WarningConsoleFilter())
        root_logger.addHandler(console_handler)

    telethon_logger = logging.getLogger("telethon")
    telethon_logger.setLevel(logging.WARNING)
    telethon_logger.addFilter(_NoiseFilter())

    return kernel_logger


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

    def _is_duplicate(self, signature: str, ttl: int = _DEDUP_TTL) -> bool:
        """Return True if this signature was seen recently; register it if not."""
        cache = self.cache
        if not cache:
            return False
        if cache.get(signature):
            return True
        cache.set(signature, True, ttl=ttl)
        return False

    def _is_muted(self, error_type: str, source: str) -> bool:
        """Return True if this error type+source is currently muted."""
        cache = self.cache
        return bool(cache and cache.get(f"mute:{error_type}:{source}"))

    def mute_error(self, error_type: str, source: str, ttl: int = _MUTE_TTL) -> None:
        """Suppress a specific error type+source for *ttl* seconds."""
        cache = self.cache
        if cache:
            cache.set(f"mute:{error_type}:{source}", True, ttl=ttl)

    def _get_lifetime_info(self, sig_key: str) -> str:
        """Return an HTML blockquote showing first-seen time and occurrence count.

        Side effect: increments the counter stored in the cache.
        Returns an empty string if this is the first occurrence.
        """
        cache = self.cache
        if not cache:
            return ""

        now = datetime.now().timestamp()
        first_key = f"first_seen:{sig_key}"
        count_key = f"err_count:{sig_key}"

        first_seen = cache.get(first_key)
        raw_count = cache.get(count_key)
        count = int(raw_count) + 1 if raw_count else 1  # type: ignore[arg-type]
        cache.set(count_key, count, ttl=_FIRST_SEEN_TTL)

        if first_seen is None:
            cache.set(first_key, now, ttl=_FIRST_SEEN_TTL)
            return ""

        elapsed = int(now - float(first_seen))  # type: ignore[arg-type]
        if elapsed < 60:
            human = f"{elapsed}s"
        elif elapsed < 3600:
            human = f"{elapsed // 60}m"
        else:
            human = f"{elapsed // 3600}h {(elapsed % 3600) // 60}m"

        return (
            f"<blockquote>⏱️ <b>First seen:</b> {human} ago"
            f" <b>(×{count})</b></blockquote>\n"
        )

    def _track_similar(self, source_func: str, error_id: str) -> int:
        """Record *error_id* under *source_func* and return the total stored count."""
        cache = self.cache
        if not cache:
            return 0
        key = f"similar:{_sig_hash(source_func)}"
        existing: list[str] = list(cache.get(key) or [])  # type: ignore[arg-type]
        if error_id not in existing:
            existing.append(error_id)
        existing = existing[-_SIMILAR_MAX:]
        cache.set(key, existing, ttl=_TRACE_CACHE_TTL)
        return len(existing)

    def get_similar_errors_by_hash(self, func_hash: str) -> list[str]:
        """Return recent error_ids for a source function identified by *func_hash*."""
        cache = self.cache
        if not cache:
            return []
        return list(cache.get(f"similar:{func_hash}") or [])  # type: ignore[arg-type]

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
            except _NETWORK_ERRORS as e:
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
        """Execute *coro_factory()* with automatic FloodWait / network retry."""
        for attempt in range(max_attempts + 1):
            try:
                await coro_factory()
                return True
            except Exception as e:
                if isinstance(e, FloodWaitError):
                    if attempt < max_attempts:
                        await asyncio.sleep(getattr(e, "seconds", 0))
                    else:
                        self.k.logger.warning(
                            f"Flood wait exceeded retries: {getattr(e, 'seconds', 0)}s"
                        )
                        return False
                elif isinstance(e, _NETWORK_ERRORS):
                    if attempt < max_attempts:
                        self._auth_cache = None
                        await asyncio.sleep(2**attempt)
                    else:
                        self.k.logger.warning(
                            f"Network error after {max_attempts} retries: {e}"
                        )
                        return False
                else:
                    self.k.logger.error(f"Log message send failed: {e}")
                    return False
        return False

    async def send_log_message(self, text: str, file: IO | str | None = None) -> bool:
        """Send a message to the configured log chat."""
        if not self.log_chat_id:
            return False

        # Resolve client BEFORE the lock — authorisation check may be a network call
        client = await self._get_client()
        if not client or not client.is_connected():
            return False

        safe_text = mask_sensitive_data(text)
        async with self._send_lock:

            async def _do_send() -> None:
                if file:
                    await client.send_file(
                        self.log_chat_id, file, caption=safe_text, parse_mode="html"
                    )
                else:
                    await client.send_message(
                        self.log_chat_id, safe_text, parse_mode="html"
                    )

            success = await self._send_with_retry(_do_send)
            return success

    async def _send_error_with_traceback(
        self,
        body: str,
        masked_traceback: str,
        *,
        error_id: str | None = None,
        error_type: str | None = None,
        source: str | None = None,
        source_func: str | None = None,
    ) -> bool:
        """Send an error message with Traceback / Similar / Mute buttons."""
        if not self.log_chat_id:
            return False

        if error_id and self.cache:
            self.cache.set(f"tb_{error_id}", masked_traceback, ttl=_TRACE_CACHE_TTL)

        buttons: list[Button] = []

        if error_id:
            buttons.append(Button.inline("🔍 Traceback", data=f"show_tb:{error_id}"))

        if source_func and error_id:
            count = self._track_similar(source_func, error_id)
            if count > 1:
                buttons.append(
                    Button.inline(
                        f"📋 Similar ({count})",
                        data=f"find_similar:{_sig_hash(source_func)}",
                    )
                )

        if error_type and source:
            buttons.append(
                Button.inline("🔕 Mute 1h", data=f"mute_err:{error_type}:{source}")
            )

        safe_body = mask_sensitive_data(body)

        # Resolve client BEFORE acquiring the lock
        client = await self._get_client()

        async with self._send_lock:

            async def _do_send() -> None:
                await client.send_message(
                    self.log_chat_id,
                    safe_body,
                    buttons=[buttons] if buttons else None,
                    parse_mode="html",
                )

            success = await self._send_with_retry(_do_send)
            if not success:
                self.k.logger.error("Could not send error log")
                self.k.logger.error(
                    "Original traceback: %s", strip_html(masked_traceback[:500])
                )
            return success

    async def _maybe_attach_log_file(self, source: str, repeat_count: int) -> None:
        """Attach the tail of kernel.log once an error crosses the repeat threshold."""
        if repeat_count < _CRITICAL_REPEAT_THRESHOLD:
            return
        if not os.path.exists(_LOG_FILE):
            return
        try:
            with open(_LOG_FILE, encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
            tail = "".join(lines[-_LOG_TAIL_LINES:])
            caption = (
                f"📎 <b>Log tail</b> (last {_LOG_TAIL_LINES} lines) "
                f"<blockquote> <code>{html.escape(mask_sensitive_data(source))}</code></blockquote>"
            )
            file_obj = io.BytesIO(tail.encode("utf-8"))
            file_obj.name = "kernel_tail.log"
            await self.send_log_message(caption, file=file_obj)
        except Exception as exc:
            self.k.logger.warning(f"Could not attach log file: {exc}")

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
        safe_source = html.escape(mask_sensitive_data(source_file))

        error_id: str | None = None
        masked_tb = ""
        if exc_info:
            error_id = f"err_{uuid.uuid4().hex[:8]}"
            raw_tb = "".join(traceback.format_exception(*exc_info))
            masked_tb = mask_sensitive_data(raw_tb)

        body = (
            f'<blockquote><tg-emoji emoji-id="5379679518740978720">🎯</tg-emoji>'
            f" <b>Source:</b> <code>{safe_source}</code>\n"
            f'<blockquote><tg-emoji emoji-id="5426900601101374618">🧿</tg-emoji>'
            f" <b>Error:</b> <code>{html.escape(safe_error)}</code></blockquote>"
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
        self,
        error: Exception,
        source: str = "unknown",
        event=None,
    ) -> None:
        """Log an error to file and send a formatted report to the log chat."""
        if not self.log_chat_id:
            return

        error_type = type(error).__name__

        if self._is_muted(error_type, source):
            self.k.logger.debug(f"Muted error suppressed: {error_type} in {source}")
            return

        signature = f"error:{source}:{error_type}:{error}"
        sig_key = _sig_hash(signature)
        if self._is_duplicate(signature):
            return

        error_id = f"err_{uuid.uuid4().hex[:8]}"
        lifetime_html = self._get_lifetime_info(sig_key)

        exc_info = (type(error), error, error.__traceback__)
        rich = RichException.from_exc_info(*exc_info)
        _, _, source_func = ErrorFormatter.find_source_location(rich.full_stack)

        src_esc = html.escape(mask_sensitive_data(source or "unknown"), quote=False)
        body = (
            f'<blockquote><tg-emoji emoji-id="5372846474881146350">🔭</tg-emoji>'
            f" <b>Source Message:</b> <code>{src_esc}</code></blockquote>\n"
            f"{lifetime_html}{rich.message}"
        )

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
                    f'\n<tg-emoji emoji-id="5298499667569425533">🃏</tg-emoji>'
                    f" <b>Message info:</b>\n"
                    f"<blockquote>🪬 <b>User:</b> {html.escape(safe_user_info)}\n"
                    f"⌨️ <b>Text:</b> <code>{html.escape(txt)}</code>\n"
                    f"📬 <b>Chat:</b> {html.escape(safe_chat_title)}</blockquote>"
                )
            except Exception:
                pass

        safe_stack = strip_html(mask_sensitive_data(rich.full_stack[:500]))

        # Read repeat count BEFORE _get_lifetime_info increments it again
        raw_count = self.cache.get(f"err_count:{sig_key}") if self.cache else 0
        repeat_count = int(raw_count or 0)

        await self._send_error_with_traceback(
            body,
            rich.full_stack,
            error_id=error_id,
            error_type=error_type,
            source=source,
            source_func=source_func,
        )
        await self._maybe_attach_log_file(source, repeat_count)

    async def log(self, message: str, emoji: str = "ℹ️") -> None:  # noqa: RUF001
        """Send an event to the log chat and write it to the rotating log file."""
        # mask_sensitive_data is called once here; send_log_message does NOT mask again
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
        exc_type, exc_value, tb = sys.exc_info()
        if exc_type is None or exc_value is None:
            return
        if not self.log_chat_id:
            return

        error_type = exc_type.__name__

        if self._is_muted(error_type, source):
            self.k.logger.debug(f"Muted error suppressed: {error_type} in {source}")
            return

        signature = f"error:{source}:{error_type}:{exc_value}"
        sig_key = _sig_hash(signature)
        if self._is_duplicate(signature):
            return

        rich = RichException.from_exc_info(exc_type, cast(Exception, exc_value), tb)
        error_id = f"err_{uuid.uuid4().hex[:8]}"
        lifetime_html = self._get_lifetime_info(sig_key)
        _, _, source_func = ErrorFormatter.find_source_location(rich.full_stack)

        body = f"{lifetime_html}{rich.message}"

        safe_stack = strip_html(mask_sensitive_data(rich.full_stack[:500]))

        raw_count = self.cache.get(f"err_count:{sig_key}") if self.cache else 0
        repeat_count = int(raw_count or 0)

        await self._send_error_with_traceback(
            body,
            rich.full_stack,
            error_id=error_id,
            error_type=error_type,
            source=source,
            source_func=source_func,
        )
        await self._maybe_attach_log_file(source, repeat_count)


_RAW_LOG_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \[")


class TelegramLogHandler:
    """Async handler that sends WARNING/ERROR logs to Telegram with flood protection."""

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

        # deque for O(1) left-pop vs list's O(n)
        self._rate_timestamps: deque[float] = deque()

    async def start(self) -> None:
        """Start the background worker task."""
        if self._task is None or self._task.done():
            self._shutdown = False
            self._task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        """Stop the handler gracefully, flushing any remaining messages."""
        self._shutdown = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        # Drain queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def emit(self, message: str) -> None:
        """Queue a log message for sending (safe to call from sync code)."""
        if self._shutdown:
            return
        try:
            self._queue.put_nowait(message)
        except Exception:
            pass

    def queue_size(self) -> int:
        """Return current queue depth (useful for debugging)."""
        return self._queue.qsize()

    def _clean_rate_timestamps(self, now: float) -> None:
        """Evict timestamps outside the current rate window."""
        cutoff = now - self._rate_window
        while self._rate_timestamps and self._rate_timestamps[0] < cutoff:
            self._rate_timestamps.popleft()  # O(1) with deque

    def _is_rate_limited(self, now: float) -> bool:
        """Return True when the rate limit has been reached."""
        self._clean_rate_timestamps(now)
        return len(self._rate_timestamps) >= self._rate_limit

    async def _worker(self) -> None:
        """Background task: collect messages into batches and flush them."""
        batch: list[str] = []

        while not self._shutdown:
            try:
                try:
                    message = await asyncio.wait_for(
                        self._queue.get(), timeout=self._batch_interval
                    )
                    batch.append(message)

                    # Greedily drain whatever is already in the queue
                    while not self._queue.empty() and len(batch) < self._batch_size:
                        batch.append(self._queue.get_nowait())

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
        """Deduplicate, rate-check, and send a batch of messages to Telegram."""
        if not batch:
            return

        cache = self._kernel_logger.cache
        seen: set[str] = set()
        unique_messages: list[str] = []

        for msg in batch:
            safe_msg = mask_sensitive_data(msg)
            if not safe_msg.strip():
                continue

            sig = f"tlog:{_sig_hash(safe_msg)}"
            if sig in seen:
                continue
            if cache and cache.get(sig):
                continue

            seen.add(sig)
            unique_messages.append(safe_msg)
            if cache:
                cache.set(sig, True, ttl=self._dedup_ttl)

        if not unique_messages:
            return

        now = datetime.now().timestamp()
        if self._is_rate_limited(now):
            return

        self._rate_timestamps.append(now)

        if len(unique_messages) == 1:
            text = (
                f"<blockquote expandable>"
                f"<code>{html.escape(unique_messages[0])}</code>"
                f"</blockquote>"
            )
        else:
            lines = [html.escape(line) for line in unique_messages[: self._batch_size]]
            text = (
                "<blockquote expandable>\n<code>"
                + "\n".join(lines)
                + "\n</code></blockquote>"
            )
            overflow = len(unique_messages) - self._batch_size
            if overflow > 0:
                text += f"\n<blockquote><code>... and {overflow} more errors</code></blockquote>"

        await self._kernel_logger.send_log_message(text)
