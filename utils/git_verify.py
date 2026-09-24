# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""Mandatory commit-signature verification for MCUB core (git) updates.

Trust model
-----------
Only commits signed with the OpenSSH key(s) listed in ``rich-git.pub`` (repo
root) are accepted. Everything else - unsigned commits, signatures made by any
other key, tampered commits - is a mismatch.

* The key file is read from the **currently checked-out tree** (the version that
  is already installed), never from the commit being fetched. A commit cannot
  vouch for itself by shipping its own key; rotating the key therefore needs an
  update that is signed with the old one.
* The allowed-signers list is generated from that file and handed to git with
  ``-c gpg.ssh.allowedSignersFile=...``. The host's own git/gpg configuration
  cannot widen the trust.
* Verification can never be skipped silently: a missing/invalid key file or a
  missing ``ssh-keygen`` is reported like a mismatch (fail closed).

Typical flow (used by the ``updates`` and ``log_bot`` modules)::

    target = await fetch_target(repo, branch)     # git fetch + exact SHA
    if not await is_up_to_date(repo, target):
        result = await check_commit(repo, target) # git verify-commit
        if not result.ok:
            ...                                   # warn, let the user decide
    await merge_commit(repo, target)              # merge exactly that SHA

Why an exact SHA instead of ``git pull``: ``pull`` fetches again, so the commit
that gets merged may differ from the one that was verified (the remote can move
in between). Verifying a SHA and merging that same SHA closes the gap.

Acceptance is decided only by the exit code of ``git verify-commit``.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "TRUSTED_KEY_FILE",
    "WARNING",
    "GitError",
    "SigState",
    "VerifyResult",
    "check_commit",
    "fetch_target",
    "is_up_to_date",
    "load_trusted_keys",
    "merge_commit",
]

WARNING = (
    "The commit signature does not match, " "installing this update may harm the host."
)
TRUSTED_KEY_FILE = "mcub.pub"

_PRINCIPAL = "mcub-trusted-signer"
_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_KEY_TYPE_RE = re.compile(r"^(?:ssh-[a-z0-9]+|ecdsa-sha2-[a-z0-9]+|sk-[a-z0-9@.\-]+)$")
_KEY_DATA_RE = re.compile(r"^[A-Za-z0-9+/]+={0,3}$")


class GitError(RuntimeError):
    """A git command failed, timed out, or returned something unexpected."""


class _KeyFileError(Exception):
    """The trusted key file is missing or unusable."""


class SigState(StrEnum):
    VERIFIED = "verified"
    MISSING = "missing"  # the commit carries no signature at all
    MISMATCH = "mismatch"  # signed, but not by a trusted key / signature invalid
    NO_KEY = "no_key"  # trusted key file missing or unusable
    NO_VERIFIER = "no_verifier"  # ssh-keygen is not installed


@dataclass(frozen=True)
class VerifyResult:
    sha: str
    state: SigState
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.state is SigState.VERIFIED

    @property
    def short(self) -> str:
        return self.sha[:12]

    def describe(self) -> str:
        """One line with the technical reason (for the log, not for the chat)."""
        reasons = {
            SigState.VERIFIED: "signature verified",
            SigState.MISSING: "the commit is not signed",
            SigState.MISMATCH: "signed, but not by a key from "
            f"{TRUSTED_KEY_FILE} (or the signature is invalid)",
            SigState.NO_KEY: f"cannot verify: {TRUSTED_KEY_FILE} is unusable",
            SigState.NO_VERIFIER: "cannot verify: ssh-keygen is not installed",
        }
        text = f"commit {self.short}: {reasons[self.state]}"
        return f"{text} ({self.detail})" if self.detail else text


async def _git(
    repo: str,
    *args: str,
    timeout: float,
    config: tuple[str, ...] = (),
) -> tuple[int, str, str]:
    cmd = ["git"]
    for item in config:
        cmd += ["-c", item]
    cmd += list(args)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=repo,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        raise GitError(f"git {args[0]} timed out ({timeout:.0f}s)") from None
    return (
        proc.returncode if proc.returncode is not None else -1,
        out_b.decode(errors="replace").strip(),
        err_b.decode(errors="replace").strip(),
    )


def _require_sha(sha: str) -> str:
    if not _SHA_RE.match(sha or ""):
        raise GitError(f"invalid commit id: {sha!r}")
    return sha


def load_trusted_keys(root: str, filename: str = TRUSTED_KEY_FILE) -> list[str]:
    """Read ``<root>/<filename>`` and return ``["<type> <base64>", ...]``.

    Comments and blank lines are ignored, the trailing key comment is dropped.
    Raises ``_KeyFileError`` when nothing usable is found.
    """
    path = os.path.join(root, filename)
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        raise _KeyFileError(f"{path}: {exc.strerror or exc}") from exc
    except UnicodeDecodeError as exc:
        raise _KeyFileError(f"{path}: not a text file") from exc

    keys: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-----BEGIN"):
            raise _KeyFileError(
                f"{path}: PGP/PEM keys are not supported, an OpenSSH public key is required"
            )
        parts = line.split()
        if (
            len(parts) < 2
            or not _KEY_TYPE_RE.match(parts[0])
            or not _KEY_DATA_RE.match(parts[1])
        ):
            raise _KeyFileError(f"{path}: not an OpenSSH public key line")
        keys.append(f"{parts[0]} {parts[1]}")
    if not keys:
        raise _KeyFileError(f"{path}: no keys found")
    return keys


async def fetch_target(repo: str, branch: str, *, timeout: float = 60) -> str:
    """Fetch ``origin/<branch>`` and return the exact commit SHA it points to."""
    rc, out, err = await _git(
        repo, "fetch", "--quiet", "origin", branch, timeout=timeout
    )
    if rc != 0:
        raise GitError(f"git fetch failed (code {rc}): {err or out}")

    rc, out, err = await _git(
        repo, "rev-parse", "--verify", "FETCH_HEAD^{commit}", timeout=15
    )
    if rc != 0:
        raise GitError(f"cannot resolve fetched commit: {err or out}")
    return _require_sha(out)


async def is_up_to_date(repo: str, sha: str) -> bool:
    """True if ``sha`` is already contained in HEAD (nothing to update)."""
    _require_sha(sha)
    rc, out, err = await _git(
        repo, "merge-base", "--is-ancestor", sha, "HEAD", timeout=15
    )
    if rc == 0:
        return True
    if rc == 1:
        return False
    raise GitError(f"git merge-base failed (code {rc}): {err or out}")


async def _has_signature_header(repo: str, sha: str) -> bool:
    rc, out, err = await _git(repo, "cat-file", "commit", sha, timeout=15)
    if rc != 0:
        raise GitError(f"git cat-file failed (code {rc}): {err or out}")
    headers = out.split("\n\n", 1)[0]
    return any(line.startswith("gpgsig") for line in headers.splitlines())


async def check_commit(
    repo: str,
    sha: str,
    *,
    key_file: str = TRUSTED_KEY_FILE,
    timeout: float = 30,
) -> VerifyResult:
    """Verify that ``sha`` is signed by a key listed in ``key_file``.

    Never raises for a verification failure - inspect ``result.ok``. Raises
    ``GitError`` only for invalid input or when git itself cannot be run.
    """
    _require_sha(sha)

    rc, root, err = await _git(repo, "rev-parse", "--show-toplevel", timeout=15)
    if rc != 0:
        raise GitError(f"not a git repository: {err or root}")

    try:
        keys = load_trusted_keys(root, key_file)
    except _KeyFileError as exc:
        return VerifyResult(sha, SigState.NO_KEY, str(exc))

    if shutil.which("ssh-keygen") is None:
        return VerifyResult(sha, SigState.NO_VERIFIER)

    with tempfile.TemporaryDirectory(prefix="mcub-sig-") as tmp:
        signers = os.path.join(tmp, "allowed_signers")
        with open(signers, "w", encoding="utf-8") as fh:
            for key in keys:
                fh.write(f'{_PRINCIPAL} namespaces="git" {key}\n')

        rc, out, err = await _git(
            repo,
            "verify-commit",
            sha,
            timeout=timeout,
            config=(f"gpg.ssh.allowedSignersFile={signers}",),
        )

    if rc == 0:
        return VerifyResult(sha, SigState.VERIFIED)

    detail = " ".join((err or out).split())[:200]
    if not await _has_signature_header(repo, sha):
        return VerifyResult(sha, SigState.MISSING)
    return VerifyResult(sha, SigState.MISMATCH, detail)


async def merge_commit(
    repo: str,
    sha: str,
    *,
    ff_only: bool = False,
    timeout: float = 60,
) -> tuple[int, str, str]:
    """Merge exactly ``sha`` into the current branch. Returns (rc, stdout, stderr)."""
    _require_sha(sha)
    args = ["merge", "--no-edit"]
    if ff_only:
        args.append("--ff-only")
    args.append(sha)
    return await _git(repo, *args, timeout=timeout)
