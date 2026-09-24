# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""Integrity guard for the pinned trust key ``mcub.pub``.

``mcub.pub`` is the trust anchor for commit-signature verification during
updates (see ``utils.git_verify``). If that file is damaged or swapped, every
signature check built on it is meaningless, so MCUB refuses to start.

Two independent pins must both match:

* SHA-256 of the raw file bytes  (``sha256sum mcub.pub``)
* SSH key fingerprint            (``ssh-keygen -l -f mcub.pub``)

The fingerprint is computed here in pure Python, so the guard needs neither
``ssh-keygen`` nor any third-party package and runs before the rest of the
project is imported.

Rotating the key
----------------
Replace ``mcub.pub`` and update ``EXPECTED_SHA256`` / ``EXPECTED_FINGERPRINT``
below in the same commit (sign it with the *old* key so installed copies accept
it). The two values come from the commands quoted above.

Limits
------
The pins live in the repository next to the code that checks them, so this
detects corruption and a swapped key file; it cannot defend against someone who
can rewrite the source tree itself.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

__all__ = [
    "DEFAULT_PIN",
    "EXPECTED_FINGERPRINT",
    "EXPECTED_SHA256",
    "KEY_FILE_NAME",
    "KeyCheck",
    "KeyIntegrityError",
    "KeyPin",
    "check_key",
    "default_key_path",
    "enforce_or_exit",
    "ssh_fingerprint",
    "verify_key",
]

KEY_FILE_NAME = "mcub.pub"
EXPECTED_SHA256 = "ed94355f672e4163aa39232d865b790a8c0676ed3d74da5f65a2a87a46ca89a0"
EXPECTED_FINGERPRINT = "SHA256:Bz5Taj8nd4MGItbqLSEF8ZxWfog/5OJlMiOgh4lrNQE"

# A real OpenSSH public key line is ~100 bytes; anything this large is damage.
_MAX_KEY_BYTES = 8192


@dataclass(frozen=True)
class KeyPin:
    sha256: str
    fingerprint: str


DEFAULT_PIN = KeyPin(EXPECTED_SHA256, EXPECTED_FINGERPRINT)


@dataclass
class KeyCheck:
    path: Path
    pin: KeyPin
    actual_sha256: str | None = None
    actual_fingerprint: str | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


class KeyIntegrityError(RuntimeError):
    """The pinned key file is missing, damaged, or not the expected key."""

    def __init__(self, check: KeyCheck) -> None:
        self.check = check
        super().__init__(
            f"{check.path.name}: integrity check failed ({'; '.join(check.problems)})"
        )


def default_key_path() -> Path:
    """``<repo root>/mcub.pub`` (this file is ``<root>/core/lib/utils/``)."""
    return Path(__file__).resolve().parents[3] / KEY_FILE_NAME


def ssh_fingerprint(key_line: str) -> str:
    """OpenSSH-style ``SHA256:...`` fingerprint of one public-key line.

    Equivalent to ``ssh-keygen -l -f``. Raises ``ValueError`` when the line is
    not a well-formed OpenSSH public key.
    """
    parts = key_line.split()
    if len(parts) < 2:
        raise ValueError("not an OpenSSH public key line")
    key_type, b64 = parts[0], parts[1]
    try:
        blob = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("key data is not valid base64") from exc
    if len(blob) < 4:
        raise ValueError("key blob is truncated")
    n = int.from_bytes(blob[:4], "big")
    if len(blob) < 4 + n:
        raise ValueError("key blob is truncated")
    if blob[4 : 4 + n].decode("ascii", "replace") != key_type:
        raise ValueError("key type does not match the key data")
    digest = hashlib.sha256(blob).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def _same(a: str | None, b: str) -> bool:
    return a is not None and hmac.compare_digest(a.encode(), b.encode())


def check_key(path: Path | str | None = None, pin: KeyPin = DEFAULT_PIN) -> KeyCheck:
    """Check ``path`` against ``pin``. Never raises; inspect ``result.problems``."""
    key_path = Path(path) if path is not None else default_key_path()
    result = KeyCheck(path=key_path, pin=pin)

    try:
        with open(key_path, "rb") as fh:
            raw = fh.read(_MAX_KEY_BYTES + 1)
    except FileNotFoundError:
        result.problems.append("file not found")
        return result
    except OSError as exc:
        result.problems.append(f"cannot read file: {exc.strerror or exc}")
        return result

    if len(raw) > _MAX_KEY_BYTES:
        result.problems.append("file is unexpectedly large")
        return result

    result.actual_sha256 = hashlib.sha256(raw).hexdigest()
    if not _same(result.actual_sha256, pin.sha256):
        result.problems.append("sha256 mismatch")

    try:
        lines = [
            ln.strip()
            for ln in raw.decode("utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        if len(lines) != 1:
            raise ValueError(f"expected exactly one key line, found {len(lines)}")
        result.actual_fingerprint = ssh_fingerprint(lines[0])
    except UnicodeDecodeError:
        result.problems.append("file is not valid text")
    except ValueError as exc:
        result.problems.append(f"unreadable key: {exc}")
    else:
        if not _same(result.actual_fingerprint, pin.fingerprint):
            result.problems.append("fingerprint mismatch")

    return result


def verify_key(path: Path | str | None = None, pin: KeyPin = DEFAULT_PIN) -> KeyCheck:
    """Like ``check_key`` but raises ``KeyIntegrityError`` on any problem."""
    result = check_key(path, pin)
    if not result.ok:
        raise KeyIntegrityError(result)
    return result


def _report(check: KeyCheck, stream: TextIO) -> None:
    red = "\033[1;31m" if getattr(stream, "isatty", lambda: False)() else ""
    end = "\033[0m" if red else ""

    def line(text: str = "") -> None:
        print(f" [security]: {text}", file=stream)

    name = check.path.name
    line(f"{red}ОШИБКА: ключ {name} повреждён или подменён.{end}")
    line(
        f"{red}ERROR: {name} is corrupted or has been replaced (integrity check failed).{end}"
    )
    line(f"  файл / file: {check.path}")
    for problem in check.problems:
        line(f"  - {problem}")
    line(f"  sha256:      expected {check.pin.sha256}")
    line(f"               actual   {check.actual_sha256 or 'unavailable'}")
    line(f"  fingerprint: expected {check.pin.fingerprint}")
    line(f"               actual   {check.actual_fingerprint or 'unavailable'}")
    line()
    line(
        f"{red}Несоответствие ключа может быть небезопасным для хоста. Запуск отменён.{end}"
    )
    line(f"{red}A key mismatch may be unsafe for the host. Startup aborted.{end}")
    stream.flush()


def enforce_or_exit(
    path: Path | str | None = None,
    pin: KeyPin = DEFAULT_PIN,
    *,
    stream: TextIO | None = None,
    exit_code: int = 1,
) -> KeyCheck:
    """Return normally if the key is intact; otherwise print why and exit."""
    result = check_key(path, pin)
    if not result.ok:
        _report(result, stream if stream is not None else sys.stderr)
        raise SystemExit(exit_code)
    return result
