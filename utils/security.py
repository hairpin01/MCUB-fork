import os
import stat
import sys
from typing import Iterable, Optional


# Files that must never be readable by group/other
_SENSITIVE_FILES = (
    "user_session.session",
    "inline_bot_session.session",
    "userbot.db",
    "config.json",
)


def lock_file(path: str) -> bool:
    """Set permissions on *path* to 600 (owner r/w only).

    Silently skips non-existent files.
    Works on Linux/macOS; on Windows logs a warning and returns False.

    Returns:
        True  – permissions set (or file does not exist yet).
        False – unsupported platform or OS error.
    """
    if sys.platform == "win32":
        # Windows ACLs are not handled here
        return False

    if not os.path.exists(path):
        return True  # nothing to lock yet; will be locked after creation

    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        return True
    except OSError:
        return False


def lock_sensitive_files(
    extra: Optional[Iterable[str]] = None,
    logger=None,
) -> None:
    """Lock all known sensitive files + any *extra* paths.

    Args:
        extra:  Additional paths to lock (e.g. custom session names).
        logger: Optional logger; falls back to print() if not provided.
    """

    def _log(msg: str) -> None:
        if logger:
            logger.debug(msg)

    if sys.platform == "win32":
        _log("lock_sensitive_files: skipped (Windows)")
        return

    targets = list(_SENSITIVE_FILES)
    if extra:
        targets.extend(extra)

    for path in targets:
        if not os.path.exists(path):
            continue
        ok = lock_file(path)
        _log(f"{'🔒 lock:' if ok else '⚠️ failed'} chmod 600: {path}")


def ensure_locked_after_write(path: str, logger=None) -> None:
    """Call immediately after writing a sensitive file.

    Convenience wrapper around lock_file() that also logs.
    """
    ok = lock_file(path)
    if logger:
        logger.debug(f"{'🔒 lock:' if ok else '⚠️ chmod failed:'} {path}")
