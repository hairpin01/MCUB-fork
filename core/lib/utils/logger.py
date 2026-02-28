import html
import re
import traceback
import uuid
from datetime import datetime
from logging import Logger
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

from telethon import Button

if TYPE_CHECKING:
    from kernel import Kernel


SENSITIVE_PATTERNS = [
    (r'\b\d{10,}\b', lambda m: 'X' * len(m.group())),  # Long numbers (phone)
    (r'token["\s:=]+["\s]?([A-Za-z0-9_-]+)', r'token="***"'),  # Tokens
    (r'api[_-]?id["\s:=]+["\s]?(\d+)', r'api_id=***'),  # API ID
    (r'api[_-]?hash["\s:=]+["\s]?([A-Za-z0-9_-]+)', r'api_hash=***'),  # API Hash
    (r'password["\s:=]+["\s]?([^\s"]+)', r'password=***'),
    (r'session["\s:=]+["\s]?([A-Za-z0-9_-]+)', r'session=***'),
    (r'Authorization:\s*\S+', 'Authorization: ***'),
]


def mask_sensitive_data(text: str) -> str:
    """Mask sensitive data in text."""
    if not text:
        return text
    
    masked = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)
    
    return masked


def setup_logging() -> Logger:
    """Create and configure the rotating file logger for the kernel.

    Returns:
        Configured Logger instance.
    """
    import logging
    logger = logging.getLogger("kernel")
    logger.setLevel(logging.DEBUG)
    handler = RotatingFileHandler(
        "logs/kernel.log", maxBytes=10 * 1024 * 1024, backupCount=5
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(handler)
    return logger


class KernelLogger:
    """Error logging, log-chat messaging, and error formatting helpers."""

    def __init__(self, kernel: "Kernel") -> None:
        self.k = kernel

    async def send_log_message(self, text: str, file=None) -> bool:
        """Send a message to the configured log chat.

        Uses bot_client when available, falls back to the user client.

        Returns:
            True on success, False otherwise.
        """
        k = self.k
        if not k.log_chat_id:
            return False
        try:
            client = (
                k.bot_client
                if (hasattr(k, "bot_client") and k.bot_client
                    and await k.bot_client.is_user_authorized())
                else k.client
            )
            if file:
                await client.send_file(k.log_chat_id, file, caption=text, parse_mode="html")
            else:
                await client.send_message(k.log_chat_id, text, parse_mode="html")
            return True
        except Exception as e:
            k.logger.error(f"Log message send failed: {e}")
            return False

    async def send_error_log(
        self, error_text: str, source_file: str, message_info: str = ""
    ) -> None:
        """Format and send a simple error to the log chat.

        Args:
            error_text: Short error description.
            source_file: File or location where the error occurred.
            message_info: Optional context string.
        """
        k = self.k
        if not k.log_chat_id:
            return

        body = (
            f"💠 <b>Source:</b> <code>{source_file}</code>\n"
            f"🔮 <b>Error:</b> <blockquote><code>{error_text[:500]}</code></blockquote>"
        )
        if message_info:
            body += f"\n🃏 <b>Message:</b> <code>{message_info[:300]}</code>"

        try:
            await self.send_log_message(body)
        except Exception:
            k.logger.error(f"Error sending error log: {error_text}")

    async def handle_error(
        self, error: Exception, source: str = "unknown", event=None
    ) -> None:
        """Log an error to file and send a formatted report to the log chat.

        Deduplicates identical errors within 60 seconds using the cache.

        Args:
            error: The exception instance.
            source: Human-readable description of the error origin.
            event: Optional Telethon event for additional context.
        """
        k = self.k
        signature = f"error:{source}:{type(error).__name__}:{error}"
        if k.cache.get(signature):
            return
        k.cache.set(signature, True, ttl=60)

        error_id = f"err_{uuid.uuid4().hex[:8]}"
        error_text = str(error) or "Unknown error"
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        k.cache.set(f"tb_{error_id}", tb)

        src_esc = html.escape(source or "unknown", quote=False)
        err_esc = html.escape(error_text[:300], quote=False)

        body = (
            f"💠 <b>Source:</b> <code>{src_esc}</code>\n"
            f"🔮 <b>Error:</b> <blockquote>👉 <code>{err_esc}</code></blockquote>"
        )

        if event:
            try:
                chat_title = getattr(event.chat, "title", "DM")
                user_info = (
                    await k.get_user_info(event.sender_id) if event.sender_id else "unknown"
                )
                txt = html.escape((event.text or "")[:200], quote=False)
                body += (
                    f"\n💬 <b>Message info:</b>\n"
                    f"<blockquote>🪬 <b>User:</b> {user_info}\n"
                    f"⌨️ <b>Text:</b> <code>{txt}</code>\n"
                    f"📬 <b>Chat:</b> {chat_title}</blockquote>"
                )
            except Exception:
                pass

        try:
            self.save_error_to_file(f"Error in {source}:\n{mask_sensitive_data(tb)}")
            print(f"=X {tb}")

            client = (
                k.bot_client
                if (hasattr(k, "bot_client") and k.bot_client)
                else k.client
            )
            await client.send_message(
                k.log_chat_id,
                mask_sensitive_data(body),
                buttons=[Button.inline("🔍 Traceback", data=f"show_tb:{error_id}")],
                parse_mode="html",
            )
        except Exception as e:
            k.logger.error(f"Could not send error log: {e}")
            k.logger.error(f"Original error: {mask_sensitive_data(tb)}")

    def save_error_to_file(self, error_text: str) -> None:
        """Append *error_text* to logs/kernel.log with a timestamp header.

        Args:
            error_text: Full traceback or error message.
        """
        k = self.k
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            with open(log_dir / "kernel.log", "a", encoding="utf-8") as f:
                sep = "=" * 60
                f.write(f"\n\n{sep}\n")
                f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{sep}\n{error_text}")
        except Exception as e:
            k.logger.error(f"Error writing to kernel.log: {e}")

    async def log_network(self, message: str) -> None:
        """Send a network event to the log chat.

        Args:
            message: Event description.
        """
        await self.send_log_message(f"🌐 {message}")
        self.k.logger.info(message)

    async def log_error_async(self, message: str) -> None:
        """Send an error event to the log chat.

        Args:
            message: Error description.
        """
        await self.send_log_message(f"🔴 {message}")
        self.k.logger.info(message)

    async def log_module(self, message: str) -> None:
        """Send a module event to the log chat.

        Args:
            message: Event description.
        """
        await self.send_log_message(f"⚙️ {message}")
        self.k.logger.info(message)
