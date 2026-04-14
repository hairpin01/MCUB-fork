# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

import hashlib
import os
import shutil
import stat
import sys
from collections.abc import Iterable

__all__ = [
    "atomic_write",
    "audit_permissions",
    "ensure_locked_after_write",
    "get_config_path",
    "get_db_path",
    "get_mcub_dir",
    "get_session_path",
    "get_sessions_dir",
    "is_locked",
    "lock_file",
    "lock_sensitive_files",
    "migrate_sessions_and_db",
    "save_checksum",
    "secure_delete",
    "session_exists",
    "verify_checksum",
]


def is_locked(path: str) -> bool:
    """Returns True if permissions are already 0o600 (owner r/w only)."""
    try:
        return stat.S_IMODE(os.stat(path).st_mode) == 0o600
    except OSError:
        return False


def atomic_write(path: str, data: bytes) -> None:
    """Atomic write: writes to temp file, then rename.

    Uses os.open() with flags to set permissions immediately on creation.
    """
    tmp = path + ".tmp"
    try:
        # Create file with correct permissions immediately (no window)
        fd = os.open(
            tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR
        )
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise


def save_checksum(path: str) -> None:
    """Save SHA256 checksum of a file."""
    if not os.path.exists(path):
        return
    checksum_path = path + ".sha256"
    try:
        with open(path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        with open(checksum_path, "w") as f:
            f.write(file_hash)
        os.chmod(checksum_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    except OSError:
        pass


def verify_checksum(path: str) -> bool:
    """Verify file integrity against stored checksum.

    Returns:
        True - checksum matches or no file
        False - checksum mismatch or file corrupted
    """
    if not os.path.exists(path):
        return True  # No file to verify
    checksum_path = path + ".sha256"
    if not os.path.exists(checksum_path):
        return True  # No checksum to verify
    try:
        with open(path, "rb") as f:
            current_hash = hashlib.sha256(f.read()).hexdigest()
        with open(checksum_path) as f:
            saved_hash = f.read().strip()
        return current_hash == saved_hash
    except OSError:
        return False  # Error = treat as verification failure


def get_mcub_dir(api_id: int, api_hash: str) -> str:
    """Get MCUB data directory based on API credentials.

    Returns:
        Path to $HOME/.MCUB/{hash(API_ID+API_HASH)[:16]}
    """
    key = f"{api_id}{api_hash}"
    instance_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
    mcub_dir = os.path.expanduser(f"~/.MCUB/{instance_hash}")

    # Check for symlink BEFORE creating (symlink attack prevention)
    if os.path.exists(mcub_dir) and os.path.islink(mcub_dir):
        raise PermissionError(f"SECURITY: {mcub_dir} is a symlink! Refusing to use.")

    # umask control for secure directory creation
    old_mask = os.umask(0o077)
    try:
        os.makedirs(mcub_dir, exist_ok=True)
    finally:
        os.umask(old_mask)

    # Protect directory from group/other access
    os.chmod(mcub_dir, stat.S_IRWXU)  # 0o700

    return mcub_dir


def get_sessions_dir(api_id: int, api_hash: str) -> str:
    """Get sessions directory."""
    sessions_dir = os.path.join(get_mcub_dir(api_id, api_hash), "sessions")

    # umask control for secure directory creation
    old_mask = os.umask(0o077)
    try:
        os.makedirs(sessions_dir, exist_ok=True)
    finally:
        os.umask(old_mask)

    os.chmod(sessions_dir, stat.S_IRWXU)  # 0o700
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


def get_db_path(api_id: int | None = None, api_hash: str | None = None) -> str:
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


def get_config_path(api_id: int | None = None, api_hash: str | None = None) -> str:
    """Get full path to the config.json file.

    Args:
        api_id: Telegram API ID
        api_hash: Telegram API Hash

    Returns:
        Full path to config.json file.
    """
    if api_id and api_hash:
        mcub_dir = get_mcub_dir(api_id, api_hash)
        return os.path.join(mcub_dir, "config.json")
    return "config.json"


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
            shutil.move(old_path, new_path)
            # Lock the file after migration
            lock_file(new_path)
            _log(f"[migrate] moved: {old_path} -> {new_path}")
            migrated = True

    old_db_path = os.path.join(os.getcwd(), old_db)
    new_db_path = os.path.join(mcub_dir, old_db)
    if os.path.exists(old_db_path) and not os.path.exists(new_db_path):
        shutil.move(old_db_path, new_db_path)
        # Lock the file after migration
        lock_file(new_db_path)
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
    Checks if already locked to avoid unnecessary syscalls.

    Returns:
        True  – permissions set (or file does not exist yet).
        False – unsupported platform or OS error.
    """
    if sys.platform == "win32":
        # Windows ACLs are not handled here
        return False

    if not os.path.exists(path):
        return True  # nothing to lock yet; will be locked after creation

    # Check if already locked to avoid unnecessary syscalls
    if is_locked(path):
        return True

    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        return True
    except OSError:
        return False


def lock_sensitive_files(
    mcub_dir: str | None = None,
    extra: Iterable[str] | None = None,
    logger=None,
) -> None:
    """Lock all known sensitive files + any *extra* paths.

    Args:
        mcub_dir: MCUB directory for resolving relative paths.
        extra:  Additional paths to lock (e.g. custom session names).
        logger: Optional logger; falls back to print() if not provided.
    """

    def _log(msg: str) -> None:
        if logger:
            logger.debug(msg)
        else:
            print(msg)

    if sys.platform == "win32":
        _log("lock_sensitive_files: skipped (Windows)")
        return

    targets = list(_SENSITIVE_FILES)
    if extra:
        targets.extend(extra)

    for path in targets:
        # Resolve relative paths relative to mcub_dir if provided
        if not os.path.isabs(path) and mcub_dir:
            full_path = os.path.join(mcub_dir, path)
        else:
            full_path = path

        if not os.path.exists(full_path):
            continue
        ok = lock_file(full_path)
        if ok:
            _log(f"🔒 locked: {full_path}")
        else:
            _log(f"⚠️ failed chmod 600: {full_path}")

    # Also lock all .session files in sessions/ subdirectory
    if mcub_dir:
        sessions_dir = os.path.join(mcub_dir, "sessions")
        if os.path.exists(sessions_dir):
            for fname in os.listdir(sessions_dir):
                if fname.endswith(".session"):
                    session_path = os.path.join(sessions_dir, fname)
                    ok = lock_file(session_path)
                    if ok:
                        _log(f"🔒 locked: {session_path}")


def ensure_locked_after_write(path: str, logger=None) -> None:
    """Call immediately after writing a sensitive file.

    Convenience wrapper around lock_file() that also logs.
    """
    ok = lock_file(path)
    if logger:
        logger.debug(f"{'🔒 lock:' if ok else '⚠️ chmod failed:'} {path}")


def secure_delete(path: str, passes: int = 3) -> bool:
    """Securely delete a file by overwriting with random data before deletion.

    Args:
        path: Path to file to securely delete.
        passes: Number of overwrite passes (default 3).

    Returns:
        True if successful, False otherwise.
    """
    if not os.path.exists(path):
        return True

    try:
        file_size = os.path.getsize(path)
        with open(path, "wb") as f:
            for _ in range(passes):
                f.seek(0)
                f.write(os.urandom(file_size))
                f.flush()
                os.fsync(f.fileno())

        # Finally remove the file
        os.remove(path)
        return True
    except OSError:
        return False


def audit_permissions(mcub_dir: str, logger=None) -> dict:
    """Audit all files in MCUB directory for correct permissions.

    Args:
        mcub_dir: MCUB directory to audit.
        logger: Optional logger.

    Returns:
        Dict with 'secure' (list) and 'insecure' (list) file paths.
    """

    def _log(msg: str) -> None:
        if logger:
            logger.debug(msg)
        else:
            print(msg)

    secure = []
    insecure = []

    # Only audit on Unix-like systems
    if sys.platform == "win32":
        _log("audit_permissions: skipped (Windows)")
        return {"secure": secure, "insecure": insecure}

    for root, _dirs, files in os.walk(mcub_dir):
        # Skip .git directory
        if ".git" in root:
            continue

        for name in files:
            path = os.path.join(root, name)
            try:
                mode = stat.S_IMODE(os.stat(path).st_mode)
                # Check if permissions are too open (not 0o600 for files, not 0o700 for dirs)
                if mode & (
                    stat.S_IRGRP
                    | stat.S_IWGRP
                    | stat.S_IXGRP
                    | stat.S_IROTH
                    | stat.S_IWOTH
                    | stat.S_IXOTH
                ):
                    insecure.append(path)
                else:
                    secure.append(path)
            except OSError:
                pass

    if insecure:
        _log(f"audit_permissions: found {len(insecure)} insecure files")
    else:
        _log(f"audit_permissions: all {len(secure)} files are secure")

    return {"secure": secure, "insecure": insecure}
