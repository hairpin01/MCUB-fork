import asyncio
import html
import inspect
import logging
import re
import traceback
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from telethon import Button
from telethon.errors import (
    FloodWaitError,
    NetworkMigrateError,
    ServerError,
    TimedOutError,
)

if TYPE_CHECKING:
    from kernel import Kernel

SENSITIVE_PATTERNS = [
    (
        r"(?<!emoji-id=[\"'])\b\d{10,}\b", lambda m: "X" * len(m.group())
    ),  # Long numbers (phone)
    (
        r"""token(?:['"\s:=]|&#x27;|&quot;)+(?:['"\s]|&#x27;|&quot;)?([A-Za-z0-9_-]+)""",
        r'token="***"',
    ),
    (
        r"""api[_-]?id(?:['"\s:=]|&#x27;|&quot;)+(?:['"\s]|&#x27;|&quot;)?(\d+)""",
        r"api_id=***",
    ),
    (
        r"""api[_-]?hash(?:['"\s:=]|&#x27;|&quot;)+(?:['"\s]|&#x27;|&quot;)?([A-Za-z0-9_-]+)""",
        r"api_hash=***",
    ),
    (
        r"""password(?:['"\s:=]|&#x27;|&quot;)+(?:['"\s]|&#x27;|&quot;)?([^\s"'&]+)""",
        r"password=***",
    ),
    (
        r"""session(?:['"\s:=]|&#x27;|&quot;)+(?:['"\s]|&#x27;|&quot;)?([A-Za-z0-9_-]+)""",
        r"session=***",
    ),
    (r"Authorization:\s*.+", "Authorization: ***"),
]


def mask_sensitive_data(text: str) -> str:
    """Mask sensitive data in text."""
    if not text:
        return text
    masked = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)
    return masked


def override_text(exception: Exception) -> Optional[str]:
    """Return a user-friendly HTML string for well-known error types, else None."""
    match exception:
        case TimedOutError() | NetworkMigrateError():
            return "✈️ <b>Connection problems on the server.</b>"
        case ServerError():
            return "📡 <b>Telegram servers are currently experiencing issues. Please try again later.</b>"
        case FloodWaitError() as e:
            return f"✋ <b>Flood wait triggered — retry in {e.seconds}s.</b>"
        case ModuleNotFoundError():
            detail = traceback.format_exception_only(type(exception), exception)[0]
            detail = detail.split(":", 1)[-1].strip()
            return f"📦 <b>Missing module:</b> <code>{html.escape(detail)}</code>"
        case _:
            return None


_LINE_RE = re.compile(r'  File "(.*?)", line ([0-9]+), in (.+)')


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
        comment: Optional[str] = None,
    ) -> "RichException":
        raw_tb = "".join(traceback.format_exception(exc_type, exc_value, tb)).replace(
            "Traceback (most recent call last):\n", ""
        )

        # Find deepest file reference for the "Source:" line
        filename, lineno, name = next(
            (
                _LINE_RE.search(line).groups()
                for line in reversed(raw_tb.splitlines())
                if _LINE_RE.search(line)
            ),
            (None, None, None),
        )

        # HTML-format the full traceback
        def _fmt_line(line: str) -> str:
            m = _LINE_RE.search(line)
            if m:
                fn_, ln_, nm_ = m.groups()
                return (
                    f"👉 <code>{html.escape(fn_)}:{ln_}</code>"
                    f" <b>in</b> <code>{html.escape(nm_)}</code>"
                )
            return f"<code>{html.escape(line)}</code>"

        full_stack_html = "\n".join(_fmt_line(l) for l in raw_tb.splitlines())

        # Try to identify calling method/class from the current call stack
        caller_info = ""
        for frame_info in inspect.stack():
            fn = frame_info.frame.f_locals.get("self")
            func = frame_info.function
            if fn and func not in (
                "handle_error",
                "from_exc_info",
                "log_error_from_exc",
                "<module>",
            ):
                caller_info = (
                    f"<blockquote><tg-emoji emoji-id=\"5426900601101374618\">🧿</tg-emoji> <b>Cause:</b> <code>{html.escape(func)}</code>"
                    f" of <code>{html.escape(type(fn).__name__)}</code></blockquote>\n"
                )
                break

        override = override_text(exc_value)
        if override:
            message = override
        else:
            err_only = html.escape(
                "".join(traceback.format_exception_only(exc_type, exc_value)).strip()
            )
            src_part = (
                f"<blockquote><tg-emoji emoji-id=\"5379679518740978720\">🎯</tg-emoji> <b>Source:</b> <code>{html.escape(filename)}:{lineno}</code>"
                f" <b>in</b> <code>{html.escape(name)}</code></blockquote>\n"
                if filename
                else ""
            )
            comment_part = (
                f"\n<blockquote><tg-emoji emoji-id=\"5465300082628763143\">💬</tg-emoji> <b>Message:</b> <code>{html.escape(str(comment))}</code></blockquote>"
                if comment
                else ""
            )
            message = (
                f"{caller_info}{src_part}"
                f'<tg-emoji emoji-id="5469903029144657419">❓</tg-emoji> <u><b>Error:</b></u> <pre><code class="language-python">{err_only}</code></pre>'
                f"{comment_part}"
            )

        return cls(message=message, full_stack=full_stack_html)


def setup_logging() -> logging.Logger:
    """Create and configure the rotating file logger for the kernel."""
    logger = logging.getLogger("kernel")
    logger.setLevel(logging.INFO)

    # Suppress noisy low-level update-fetch chatter
    class _NoiseFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            msg = record.getMessage()
            return "Failed to fetch updates" not in msg and "Sleep" not in msg

    handler = RotatingFileHandler(
        "logs/kernel.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    handler.addFilter(_NoiseFilter())
    logger.addHandler(handler)
    return logger


class KernelLogger:
    """Error logging, log-chat messaging, and error formatting helpers."""

    def __init__(self, kernel: "Kernel") -> None:
        self.k = kernel
        self._send_lock: "asyncio.Lock | None" = None

    def _get_lock(self) -> asyncio.Lock:
        """Return the send lock, creating it lazily inside the running loop."""
        if self._send_lock is None:
            self._send_lock = asyncio.Lock()
        return self._send_lock

    async def _get_client(self):
        """Pick bot_client when available and authorised, else fall back to user client."""
        k = self.k
        if (
            hasattr(k, "bot_client")
            and k.bot_client
            and await k.bot_client.is_user_authorized()
        ):
            return k.bot_client
        return k.client

    async def _send_with_retry(self, coro_factory, *, max_attempts: int = 2) -> bool:
        """Execute *coro_factory()* with automatic FloodWait retry.

        Inspired by Heroku's ``_exc_sender`` pattern.

        Args:
            coro_factory: Zero-argument callable that returns a coroutine.
            max_attempts: How many times to retry on flood-wait before giving up.

        Returns:
            True on success, False otherwise.
        """
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
            except Exception as e:
                self.k.logger.error(f"Log message send failed: {e}")
                return False
        return False

    async def send_log_message(self, text: str, file=None) -> bool:
        """Send a message to the configured log chat.

        Uses bot_client when available, falls back to the user client.
        Serialises sends through an asyncio.Lock to prevent race conditions.

        Returns:
            True on success, False otherwise.
        """
        k = self.k
        if not k.log_chat_id:
            return False

        async with self._get_lock():
            client = await self._get_client()

            async def _do_send():
                if file:
                    await client.send_file(
                        k.log_chat_id, file, caption=text, parse_mode="html"
                    )
                else:
                    await client.send_message(k.log_chat_id, text, parse_mode="html")

            return await self._send_with_retry(_do_send)

    async def send_error_log(
        self, error_text: str, source_file: str, message_info: str = ""
    ) -> None:
        """Format and send a simple error to the log chat.

        Args:
            error_text: Short error description.
            source_file: File or location where the error occurred.
            message_info: Optional context string.
        """
        if not self.k.log_chat_id:
            return

        body = (
            f"<blockquote><tg-emoji emoji-id=\"5379679518740978720\">🎯</tg-emoji> <b>Source:</b> <code>{html.escape(source_file)}</code>\n"
            f"<blockquote><tg-emoji emoji-id=\"5426900601101374618\">🧿</tg-emoji> <b>Error:</b> <blockquote><code>{html.escape(error_text[:500])}</code></blockquote>"
        )
        if message_info:
            body += (
                f"\n<tg-emoji emoji-id=\"5298499667569425533\">🃏</tg-emoji> <b>Message:</b> <code>{html.escape(message_info[:300])}</code>"
            )

        await self.send_log_message(body)

    async def handle_error(
        self, error: Exception, source: str = "unknown", event=None
    ) -> None:
        """Log an error to file and send a formatted report to the log chat.

        Deduplicates identical errors within 60 seconds using the cache.
        Uses RichException to produce readable HTML with source location and
        override messages for well-known error types.

        Args:
            error: The exception instance.
            source: Human-readable description of the error origin.
            event: Optional Telethon event for additional context.
        """
        k = self.k

        if not k.log_chat_id:
            return

        # Deduplication
        signature = f"error:{source}:{type(error).__name__}:{error}"
        if k.cache.get(signature):
            return
        k.cache.set(signature, True, ttl=60)

        error_id = f"err_{uuid.uuid4().hex[:8]}"

        # Build rich exception
        exc_info = (type(error), error, error.__traceback__)
        rich = RichException.from_exc_info(*exc_info)
        k.cache.set(f"tb_{error_id}", rich.full_stack)

        src_esc = html.escape(source or "unknown", quote=False)
        body = f"<blockquote><tg-emoji emoji-id=\"5426900601101374618\">🧿</tg-emoji> <b>Source:</b> <code>{src_esc}</code>\n{rich.message}"

        if event:
            try:
                chat_title = getattr(event.chat, "title", "DM")
                user_info = (
                    await k.get_user_info(event.sender_id)
                    if event.sender_id
                    else "unknown"
                )
                txt = html.escape((event.text or "")[:200], quote=False)
                body += (
                    f"\n💬 <b>Message info:</b>\n"
                    f"<blockquote>🪬 <b>User:</b> {user_info}\n"
                    f"⌨️ <b>Text:</b> <code>{txt}</code>\n"
                    f"📬 <b>Chat:</b> {html.escape(str(chat_title))}</blockquote>"
                )
            except Exception:
                pass

        raw_tb = "".join(traceback.format_exception(*exc_info))
        self.save_error_to_file(f"Error in {source}:\n{mask_sensitive_data(raw_tb)}")

        # Send to Telegram with traceback button
        async with self._get_lock():
            client = await self._get_client()

            async def _do_send():
                await client.send_message(
                    k.log_chat_id,
                    mask_sensitive_data(body),
                    buttons=[Button.inline("🔍 Traceback", data=f"show_tb:{error_id}")],
                    parse_mode="html",
                )

            success = await self._send_with_retry(_do_send)
            if not success:
                k.logger.error(f"Could not send error log: {error}")
                k.logger.error(f"Original error: {mask_sensitive_data(raw_tb)}")

    def save_error_to_file(self, error_text: str) -> None:
        """Append *error_text* to logs/kernel.log with a timestamp header.

        Args:
            error_text: Full traceback or error message.
        """
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            with open(log_dir / "kernel.log", "a", encoding="utf-8") as f:
                sep = "=" * 60
                f.write(f"\n\n{sep}\n")
                f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{sep}\n{error_text}")
        except Exception as e:
            self.k.logger.error(f"Error writing to kernel.log: {e}")

    async def log_network(self, message: str) -> None:
        """Send a network event to the log chat."""
        await self.send_log_message(f"🌐 {message}")
        self.k.logger.info(message)

    async def log_error_async(self, message: str) -> None:
        """Send an error event to the log chat."""
        await self.send_log_message(f"🔴 {message}")
        self.k.logger.info(message)

    async def log_module(self, message: str) -> None:
        """Send a module event to the log chat."""
        await self.send_log_message(f"⚙️ {message}")
        self.k.logger.info(message)

    async def log_error_from_exc(self, source: str = "unknown") -> None:
        """Send an error to the log chat using RichException for beautiful formatting."""
        import sys

        exc_type, exc_value, tb = sys.exc_info()
        if exc_type is None:
            return
        k = self.k
        if not k.log_chat_id:
            return
        rich = RichException.from_exc_info(exc_type, exc_value, tb)
        src_esc = html.escape(source, quote=False)
        body = f"<blockquote><tg-emoji emoji-id=\"5321304062715517873\">🛰</tg-emoji> <b>Source:</b> <code>{src_esc}</code></blockquote>\n{rich.message}"
        await self.send_log_message(body)
