# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""
Tests for utils.git_verify (mandatory commit-signature check for updates).

They run real ``git`` and ``ssh-keygen`` against throw-away repositories and are
skipped when either tool is missing.
"""

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from core.lib.utils import key_guard as kg
from utils import git_verify as gv

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("ssh-keygen") is None,
    reason="git and ssh-keygen are required",
)

WARNING = (
    "The commit signature does not match, installing this update may harm the host."
)


def sh(*args, cwd=None):
    return subprocess.check_output(
        args, cwd=cwd, text=True, stderr=subprocess.DEVNULL
    ).strip()


async def check(env, sha, **kw):
    """check_commit with the production key pin off (these tests use throw-away keys)."""
    kw.setdefault("pin", None)
    return await gv.check_commit(str(env.root), sha, **kw)


def pin_for(path: Path) -> kg.KeyPin:
    raw = path.read_bytes()
    line = next(
        ln for ln in raw.decode().splitlines() if ln.strip() and not ln.startswith("#")
    )
    return kg.KeyPin(hashlib.sha256(raw).hexdigest(), kg.ssh_fingerprint(line))


def keygen(path: Path, comment: str) -> Path:
    sh("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", comment, "-f", str(path))
    return path


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated git config + a repo whose root holds rich-git.pub (trusted key)."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    trusted = keygen(tmp_path / "trusted", "rich-git")
    other = keygen(tmp_path / "other", "attacker")

    repo = tmp_path / "repo"
    sh("git", "init", "-q", "-b", "main", str(repo))
    sh("git", "config", "user.name", "T", cwd=repo)
    sh("git", "config", "user.email", "t@example.com", cwd=repo)
    (repo / gv.TRUSTED_KEY_FILE).write_text(
        "# maintainer key\n" + (tmp_path / "trusted.pub").read_text()
    )

    class Env:
        pass

    e = Env()
    e.root, e.trusted, e.other, e.tmp = repo, trusted, other, tmp_path
    e.n = 0

    def commit(signer=None):
        e.n += 1
        (repo / "f").write_text(str(e.n))
        sh("git", "add", "-A", cwd=repo)
        args = ["git"]
        if signer is not None:
            args += ["-c", "gpg.format=ssh", "-c", f"user.signingkey={signer}"]
            args += ["commit", "-q", "-S", "-m", f"c{e.n}"]
        else:
            args += ["commit", "-q", "-m", f"c{e.n}"]
        sh(*args, cwd=repo)
        return sh("git", "rev-parse", "HEAD", cwd=repo)

    e.commit = commit
    return e


class TestCheckCommit:
    @pytest.mark.asyncio
    async def test_unsigned_commit_is_missing(self, env):
        sha = env.commit()
        res = await check(env, sha)
        assert not res.ok
        assert res.state is gv.SigState.MISSING

    @pytest.mark.asyncio
    async def test_commit_signed_with_trusted_key_is_accepted(self, env):
        sha = env.commit(env.trusted)
        res = await check(env, sha)
        assert res.ok
        assert res.state is gv.SigState.VERIFIED

    @pytest.mark.asyncio
    async def test_commit_signed_with_other_key_is_mismatch(self, env):
        sha = env.commit(env.other)
        res = await check(env, sha)
        assert not res.ok
        assert res.state is gv.SigState.MISMATCH

    @pytest.mark.asyncio
    async def test_tampered_commit_is_mismatch(self, env):
        sha = env.commit(env.trusted)
        raw = sh("git", "cat-file", "commit", sha, cwd=env.root)
        forged = raw.replace("\nc1", "\nc1 TAMPERED", 1)
        assert forged != raw
        f = env.tmp / "forged.txt"
        f.write_text(forged + "\n")
        bad = sh("git", "hash-object", "-t", "commit", "-w", str(f), cwd=env.root)
        res = await check(env, bad)
        assert res.state is gv.SigState.MISMATCH

    @pytest.mark.asyncio
    async def test_host_git_config_cannot_widen_trust(self, env, monkeypatch):
        """A host that trusts the attacker's key in its own git config still fails."""
        allowed = env.tmp / "host_allowed"
        allowed.write_text(f"* {(env.tmp / 'other.pub').read_text()}")
        monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", "gpg.ssh.allowedSignersFile")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(allowed))
        sha = env.commit(env.other)
        res = await check(env, sha)
        assert res.state is gv.SigState.MISMATCH

    @pytest.mark.asyncio
    async def test_missing_key_file_fails_closed(self, env):
        sha = env.commit(env.trusted)
        (env.root / gv.TRUSTED_KEY_FILE).unlink()
        res = await check(env, sha)
        assert not res.ok
        assert res.state is gv.SigState.NO_KEY

    @pytest.mark.asyncio
    async def test_pgp_key_file_is_rejected_not_ignored(self, env):
        sha = env.commit(env.trusted)
        (env.root / gv.TRUSTED_KEY_FILE).write_text(
            "-----BEGIN PGP PUBLIC KEY BLOCK-----\nxxx\n-----END PGP PUBLIC KEY BLOCK-----\n"
        )
        res = await check(env, sha)
        assert res.state is gv.SigState.NO_KEY
        assert "PGP" in res.detail

    @pytest.mark.asyncio
    async def test_missing_ssh_keygen_fails_closed(self, env, monkeypatch):
        sha = env.commit(env.trusted)
        monkeypatch.setattr(gv.shutil, "which", lambda _name: None)
        res = await check(env, sha)
        assert not res.ok
        assert res.state is gv.SigState.NO_VERIFIER

    @pytest.mark.asyncio
    async def test_key_is_read_from_worktree_not_from_the_checked_commit(self, env):
        """A commit that swaps in its own key file must not vouch for itself."""
        sh("git", "add", "-A", cwd=env.root)
        env.commit(env.trusted)  # installed version, trusted key committed
        # attacker commit: replaces rich-git.pub with the attacker key, signs with it
        (env.root / gv.TRUSTED_KEY_FILE).write_text((env.tmp / "other.pub").read_text())
        sha = env.commit(env.other)
        # the installed checkout still has the ORIGINAL key on disk
        (env.root / gv.TRUSTED_KEY_FILE).write_text(
            (env.tmp / "trusted.pub").read_text()
        )
        res = await check(env, sha)
        assert res.state is gv.SigState.MISMATCH

    @pytest.mark.asyncio
    async def test_invalid_sha_is_rejected(self, env):
        with pytest.raises(gv.GitError):
            await gv.check_commit(str(env.root), "--upload-pack=evil")


class TestKeyPin:
    """The key file itself must match the pinned sha256 + fingerprint."""

    @pytest.mark.asyncio
    async def test_matching_pin_accepts_valid_signature(self, env):
        sha = env.commit(env.trusted)
        pin = pin_for(env.root / gv.TRUSTED_KEY_FILE)
        res = await check(env, sha, pin=pin)
        assert res.state is gv.SigState.VERIFIED

    @pytest.mark.asyncio
    async def test_production_pin_rejects_a_foreign_key(self, env):
        """Even a correctly signed commit is refused if the key is not the pinned one."""
        sha = env.commit(env.trusted)
        res = await gv.check_commit(str(env.root), sha)  # default = real pin
        assert not res.ok
        assert res.state is gv.SigState.NO_KEY
        assert "integrity" in res.detail

    @pytest.mark.asyncio
    async def test_key_swapped_after_pinning_is_rejected(self, env):
        key_file = env.root / gv.TRUSTED_KEY_FILE
        pin = pin_for(key_file)  # pin taken from the legitimate key
        key_file.write_text((env.tmp / "other.pub").read_text())  # attacker swaps it
        sha = env.commit(env.other)  # ... and signs with the attacker key
        # without the pin the swapped key would happily verify:
        assert (await check(env, sha)).state is gv.SigState.VERIFIED
        # with the pin it is refused:
        res = await check(env, sha, pin=pin)
        assert res.state is gv.SigState.NO_KEY
        assert "sha256 mismatch" in res.detail

    @pytest.mark.asyncio
    async def test_pinned_but_key_file_missing(self, env):
        key_file = env.root / gv.TRUSTED_KEY_FILE
        pin = pin_for(key_file)
        sha = env.commit(env.trusted)
        key_file.unlink()
        res = await check(env, sha, pin=pin)
        assert res.state is gv.SigState.NO_KEY
        assert "file not found" in res.detail


class TestLoadTrustedKeys:
    def test_parses_comments_blank_lines_and_multiple_keys(self, tmp_path):
        (tmp_path / gv.TRUSTED_KEY_FILE).write_text(
            "# main\n\n"
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAbc rich@host\n"
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIXyz\n"
        )
        assert gv.load_trusted_keys(str(tmp_path)) == [
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAbc",
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIXyz",
        ]

    @pytest.mark.parametrize(
        "content",
        ["", "# only a comment\n", "hello world\n", 'ssh-ed25519 AAAA"; evil\n'],
    )
    def test_rejects_unusable_files(self, tmp_path, content):
        (tmp_path / gv.TRUSTED_KEY_FILE).write_text(content)
        with pytest.raises(gv._KeyFileError):
            gv.load_trusted_keys(str(tmp_path))


class TestFetchAndMerge:
    @pytest.fixture
    def remote(self, tmp_path):
        bare = tmp_path / "remote.git"
        clone = tmp_path / "clone"
        other = tmp_path / "other"
        sh("git", "init", "-q", "--bare", "-b", "main", str(bare))
        for d in (clone, other):
            sh("git", "clone", "-q", str(bare), str(d))
            sh("git", "config", "user.name", "T", cwd=d)
            sh("git", "config", "user.email", "t@example.com", cwd=d)
        (clone / "a").write_text("0")
        sh("git", "add", "-A", cwd=clone)
        sh("git", "commit", "-q", "-m", "base", cwd=clone)
        sh("git", "push", "-q", "origin", "main", cwd=clone)
        sh("git", "pull", "-q", "origin", "main", cwd=other)

        def push(n):
            (other / "a").write_text(str(n))
            sh("git", "commit", "-q", "-am", f"u{n}", cwd=other)
            sh("git", "push", "-q", "origin", "main", cwd=other)
            return sh("git", "rev-parse", "HEAD", cwd=other)

        return clone, push

    @pytest.mark.asyncio
    async def test_up_to_date_and_new_commit(self, remote):
        clone, push = remote
        sha = await gv.fetch_target(str(clone), "main")
        assert await gv.is_up_to_date(str(clone), sha)
        new = push(1)
        sha2 = await gv.fetch_target(str(clone), "main")
        assert sha2 == new
        assert not await gv.is_up_to_date(str(clone), sha2)

    @pytest.mark.asyncio
    async def test_merge_applies_exactly_the_verified_sha(self, remote):
        clone, push = remote
        first = push(1)
        target = await gv.fetch_target(str(clone), "main")
        assert target == first
        push(2)  # the remote moves on after verification
        rc, out, err = await gv.merge_commit(str(clone), target, ff_only=True)
        assert rc == 0, err
        assert sh("git", "rev-parse", "HEAD", cwd=clone) == first

    @pytest.mark.asyncio
    async def test_fetch_failure_raises(self, remote):
        clone, _ = remote
        with pytest.raises(gv.GitError):
            await gv.fetch_target(str(clone), "no-such-branch")

    @pytest.mark.asyncio
    async def test_merge_rejects_option_like_sha(self, remote):
        clone, _ = remote
        with pytest.raises(gv.GitError):
            await gv.merge_commit(str(clone), "--upload-pack=evil")


def test_warning_text_is_stable():
    assert gv.WARNING == WARNING
