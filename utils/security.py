import os
import stat
import sys
from typing import Iterable, Optional


def get_mcub_dir(api_id: int, api_hash: str) -> str:
    """Get MCUB data directory based on API credentials.

    Returns:
        Path to $HOME/.MCUB/{hash(API_ID+API_HASH)[:16]}
    """
    import hashlib

    key = f"{api_id}{api_hash}"
    instance_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
    mcub_dir = os.path.expanduser(f"~/.MCUB/{instance_hash}")

    os.makedirs(mcub_dir, exist_ok=True)
    return mcub_dir


def get_sessions_dir(api_id: int, api_hash: str) -> str:
    """Get sessions directory."""
    sessions_dir = os.path.join(get_mcub_dir(api_id, api_hash), "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    return sessions_dir


def session_exists(api_id: int, api_hash: str) -> bool:
    """Check if session file exists in new or old location."""
    if api_id and api_hash:
        sessions_dir = get_sessions_dir(api_id, api_hash)
        if os.path.exists(f"{sessions_dir}/user_session.session"):
            return True
    return os.path.exists("user_session.session")


def get_session_path(name: str, api_id: int, api_hash: str) -> str:
    """Get full path for a session file.

    Args:
        name: Session name (e.g., "user_session", "_mcub_setup_tmp")
        api_id: Telegram API ID
        api_hash: Telegram API Hash

    Returns:
        Full path to session file.
    """
    if api_id and api_hash:
        sessions_dir = get_sessions_dir(api_id, api_hash)
        return f"{sessions_dir}/{name}"
    return name


def get_db_path(api_id: int = None, api_hash: str = None) -> str:
    """Get full path to the database file.

    Args:
        api_id: Telegram API ID
        api_hash: Telegram API Hash

    Returns:
        Full path to database file.
    """
    if api_id and api_hash:
        mcub_dir = get_mcub_dir(api_id, api_hash)
        return os.path.join(mcub_dir, "userbot.db")
    return "userbot.db"


def migrate_sessions_and_db(api_id: int, api_hash: str, logger=None) -> bool:
    """Migrate old session files and database to new location.

    Returns:
        True if migration happened, False otherwise.
    """
    mcub_dir = get_mcub_dir(api_id, api_hash)
    sessions_dir = get_sessions_dir(api_id, api_hash)

    old_sessions = [
        "user_session.session",
        "user_session.session-journal",
        "inline_bot_session.session",
        "inline_bot_session.session-journal",
    ]

    old_db = "userbot.db"

    migrated = False

    def _log(msg: str):
        if logger:
            logger.debug(msg)
        else:
            print(msg)

    for sess in old_sessions:
        old_path = os.path.join(os.getcwd(), sess)
        new_path = os.path.join(sessions_dir, sess)
        if os.path.exists(old_path) and not os.path.exists(new_path):
            import shutil

            shutil.move(old_path, new_path)
            _log(f"[migrate] moved: {old_path} -> {new_path}")
            migrated = True

    old_db_path = os.path.join(os.getcwd(), old_db)
    new_db_path = os.path.join(mcub_dir, old_db)
    if os.path.exists(old_db_path) and not os.path.exists(new_db_path):
        import shutil

        shutil.move(old_db_path, new_db_path)
        _log(f"[migrate] moved: {old_db_path} -> {new_db_path}")
        migrated = True

    return migrated


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
