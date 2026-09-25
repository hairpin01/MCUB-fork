# SPDX-License-Identifier: MIT
# Copyright (c) 2026 rich_beluga | @rich_beluga

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

__all__ = [
    "DEFAULT_PIN",
    "EXPECTED_FINGERPRINT",
    "EXPECTED_FINGERPRINTS",
    "EXPECTED_SHA256",
    "KEY_FILE_NAME",
    "KeyCheck",
    "KeyIntegrityError",
    "KeyPin",
    "check_key",
    "default_key_path",
    "enforce_or_exit",
    "parse_open_ssh_keys",
    "ssh_fingerprint",
    "verify_key",
]

KEY_FILE_NAME = "mcub.pub"
EXPECTED_SHA256 = "0343d03f26bbd8a66e3db60ddd8cb7f258c9192c1b218ddf77efcdfd22ae3e53"
EXPECTED_FINGERPRINTS = (
    "SHA256:Bz5Taj8nd4MGItbqLSEF8ZxWfog/5OJlMiOgh4lrNQE",
    "SHA256:DyM1/FqUNIw+jZkF0g78G85IVgOJG0ZFkW57prbTFBQ",
)
# Kept for callers that used the original single-fingerprint API.
EXPECTED_FINGERPRINT = EXPECTED_FINGERPRINTS[0]

# A small set of OpenSSH public keys fits comfortably within this limit.
_MAX_KEY_BYTES = 8192
_KEY_TYPE_RE = re.compile(r"^(?:ssh-[a-z0-9]+|ecdsa-sha2-[a-z0-9]+|sk-[a-z0-9@.\-]+)$")
_KEY_DATA_RE = re.compile(r"^[A-Za-z0-9+/]+={0,3}$")


@dataclass(frozen=True)
class KeyPin:
    sha256: str
    fingerprint: str
    additional_fingerprints: tuple[str, ...] = ()

    @property
    def fingerprints(self) -> tuple[str, ...]:
        return (self.fingerprint, *self.additional_fingerprints)


DEFAULT_PIN = KeyPin(
    EXPECTED_SHA256,
    EXPECTED_FINGERPRINTS[0],
    EXPECTED_FINGERPRINTS[1:],
)


@dataclass
class KeyCheck:
    path: Path
    pin: KeyPin
    actual_sha256: str | None = None
    actual_fingerprint: str | None = None
    actual_fingerprints: tuple[str, ...] = ()
    keys: tuple[str, ...] = ()
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


def parse_open_ssh_keys(text: str) -> list[str]:
    """Return canonical ``<type> <base64>`` entries from an OpenSSH key file.

    Blank lines and comments are ignored. Any malformed, PEM, or PGP entry rejects
    the whole file instead of being silently skipped.
    """
    keys: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-----BEGIN"):
            raise ValueError(
                "PGP/PEM keys are not supported, an OpenSSH public key is required"
            )
        parts = line.split()
        if (
            len(parts) < 2
            or not _KEY_TYPE_RE.match(parts[0])
            or not _KEY_DATA_RE.match(parts[1])
        ):
            raise ValueError("not an OpenSSH public key line")
        keys.append(f"{parts[0]} {parts[1]}")
    if not keys:
        raise ValueError("no keys found")
    return keys


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
        keys = parse_open_ssh_keys(raw.decode("utf-8"))
        fingerprints = tuple(ssh_fingerprint(key) for key in keys)
    except UnicodeDecodeError:
        result.problems.append("file is not valid text")
    except ValueError as exc:
        result.problems.append(f"unreadable key: {exc}")
    else:
        result.keys = tuple(keys)
        result.actual_fingerprints = fingerprints
        result.actual_fingerprint = fingerprints[0]
        if sorted(fingerprints) != sorted(pin.fingerprints):
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
    line(
        f"{red}ERROR: {name} is corrupted or has been replaced (integrity check failed).{end}"
    )
    line(f"  file: {check.path}")
    for problem in check.problems:
        line(f"  - {problem}")
    line(f"  sha256:      expected {check.pin.sha256}")
    line(f"               actual   {check.actual_sha256 or 'unavailable'}")
    line(f"  fingerprints: expected {', '.join(check.pin.fingerprints)}")
    actual = ", ".join(check.actual_fingerprints) or "unavailable"
    line(f"                 actual   {actual}")
    line()
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
