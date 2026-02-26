# console/config.py
# Manages console/config.cfg with read/write support.
# Commands can register their own keys via ShellConfig.register().

import configparser
from pathlib import Path
from typing import Any, Optional

_CFG_PATH = Path(__file__).parent / "config.cfg"


class ShellConfig:
    """
    Thin wrapper around configparser with auto-save and key registration.

    Commands can declare their own config keys:
        def run(shell, args):
            shell.cfg.register("mystuff", "timeout", default="30",
                               comment="Seconds to wait before giving up")
            val = shell.cfg.get("mystuff", "timeout", fallback="30")

    Registered keys are written to config.cfg if they are missing,
    so they show up with their comment on first run.
    """

    def __init__(self):
        self._parser = configparser.ConfigParser(allow_no_value=True)
        self._load()

    def _load(self) -> None:
        if _CFG_PATH.exists():
            self._parser.read(_CFG_PATH, encoding="utf-8")

    def _save(self) -> None:
        with open(_CFG_PATH, "w", encoding="utf-8") as fh:
            self._parser.write(fh)

    def get(self, section: str, key: str, fallback: str = "") -> str:
        return self._parser.get(section, key, fallback=fallback)

    def getint(self, section: str, key: str, fallback: int = 0) -> int:
        return self._parser.getint(section, key, fallback=fallback)

    def getfloat(self, section: str, key: str, fallback: float = 0.0) -> float:
        return self._parser.getfloat(section, key, fallback=fallback)

    def getboolean(self, section: str, key: str, fallback: bool = False) -> bool:
        return self._parser.getboolean(section, key, fallback=fallback)

    def set(self, section: str, key: str, value: Any) -> None:
        # Write a value and immediately persist it to disk.
        if not self._parser.has_section(section):
            self._parser.add_section(section)
        self._parser.set(section, key, str(value))
        self._save()

    def register(
        self,
        section: str,
        key: str,
        default: Any,
        comment: Optional[str] = None,
    ) -> None:
        """
        Ensure a key exists in config.cfg.

        If the section or key is missing it is created with `default` and
        an optional inline comment written above it. Already-present keys
        are never overwritten, so users can safely edit the file by hand.

        Example (in a bin/ command):
            shell.cfg.register("stop", "notify_owner", default="true",
                               comment="Send a Telegram message when stopping")
        """
        changed = False

        if not self._parser.has_section(section):
            self._parser.add_section(section)
            changed = True

        if not self._parser.has_option(section, key):
            if comment:
                # configparser treats bare lines (no '=') as no-value keys.
                # We use a comment marker manually injected into the raw text.
                comment_key = f"# {comment}"
                self._parser.set(section, comment_key, None)
            self._parser.set(section, key, str(default))
            changed = True

        if changed:
            self._save()

    def sections(self) -> list:
        return self._parser.sections()

    def options(self, section: str) -> list:
        if not self._parser.has_section(section):
            return []
        return self._parser.options(section)

    def has(self, section: str, key: str) -> bool:
        return self._parser.has_option(section, key)
