# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""
Tests for core.lib.utils.key_guard (pinned mcub.pub integrity check) and for
the bootloader refusing to start when the key does not match.
"""

import io
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from core.lib.utils import key_guard as kg

REPO_ROOT = Path(__file__).resolve().parent.parent
HAS_SSH_KEYGEN = shutil.which("ssh-keygen") is not None
needs_ssh_keygen = pytest.mark.skipif(not HAS_SSH_KEYGEN, reason="ssh-keygen required")


def make_key(path: Path, comment: str = "test") -> Path:
    subprocess.check_call(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", comment, "-f", str(path)]
    )
    return path.with_suffix(".pub") if path.suffix else Path(str(path) + ".pub")


@pytest.fixture
def real_key(tmp_path) -> Path:
    """A private copy of the real, correctly pinned key."""
    dst = tmp_path / kg.KEY_FILE_NAME
    shutil.copyfile(REPO_ROOT / kg.KEY_FILE_NAME, dst)
    return dst


class TestRealKey:
    def test_repo_key_matches_both_pins(self):
        res = kg.check_key()
        assert res.ok, res.problems
        assert res.actual_sha256 == kg.EXPECTED_SHA256
        assert res.actual_fingerprint == kg.EXPECTED_FINGERPRINT

    def test_pinned_values_are_the_published_ones(self):
        assert (
            kg.EXPECTED_SHA256
            == "ed94355f672e4163aa39232d865b790a8c0676ed3d74da5f65a2a87a46ca89a0"
        )
        assert (
            kg.EXPECTED_FINGERPRINT
            == "SHA256:Bz5Taj8nd4MGItbqLSEF8ZxWfog/5OJlMiOgh4lrNQE"
        )

    def test_default_path_is_repo_root(self):
        assert kg.default_key_path() == REPO_ROOT / kg.KEY_FILE_NAME

    @needs_ssh_keygen
    def test_pin_agrees_with_ssh_keygen(self):
        out = subprocess.check_output(
            ["ssh-keygen", "-l", "-f", str(REPO_ROOT / kg.KEY_FILE_NAME)], text=True
        )
        assert out.split()[1] == kg.EXPECTED_FINGERPRINT


class TestDetection:
    def test_intact_copy_passes(self, real_key):
        assert kg.check_key(real_key).ok

    def test_changed_comment_breaks_only_sha256(self, real_key):
        real_key.write_text(real_key.read_text().replace("znullv2", "someone"))
        res = kg.check_key(real_key)
        assert res.problems == ["sha256 mismatch"]

    def test_trailing_newline_breaks_sha256_but_not_fingerprint(self, real_key):
        real_key.write_bytes(real_key.read_bytes() + b"\n")
        res = kg.check_key(real_key)
        assert res.problems == ["sha256 mismatch"]
        assert res.actual_fingerprint == kg.EXPECTED_FINGERPRINT

    def test_damaged_key_data_breaks_both(self, real_key):
        text = real_key.read_text()
        real_key.write_text(
            text.replace("AAAAC3NzaC1lZDI1NTE5AAAAIIQW", "AAAAC3NzaC1lZDI1NTE5AAAAIIQX")
        )
        res = kg.check_key(real_key)
        assert "sha256 mismatch" in res.problems
        assert "fingerprint mismatch" in res.problems

    @needs_ssh_keygen
    def test_a_different_valid_key_is_rejected(self, real_key, tmp_path):
        other = make_key(tmp_path / "other")
        real_key.write_text(other.read_text())
        res = kg.check_key(real_key)
        assert "sha256 mismatch" in res.problems
        assert "fingerprint mismatch" in res.problems
        assert not res.ok

    @needs_ssh_keygen
    def test_two_keys_in_one_file_are_rejected(self, real_key, tmp_path):
        other = make_key(tmp_path / "other")
        real_key.write_text(real_key.read_text() + other.read_text())
        res = kg.check_key(real_key)
        assert not res.ok
        assert any("exactly one key" in p for p in res.problems)

    def test_missing_file(self, tmp_path):
        res = kg.check_key(tmp_path / "nope.pub")
        assert res.problems == ["file not found"]
        assert res.actual_sha256 is None

    def test_directory_instead_of_file(self, tmp_path):
        (tmp_path / "mcub.pub").mkdir()
        res = kg.check_key(tmp_path / "mcub.pub")
        assert not res.ok

    def test_empty_file(self, tmp_path):
        p = tmp_path / "mcub.pub"
        p.write_bytes(b"")
        res = kg.check_key(p)
        assert not res.ok
        assert "sha256 mismatch" in res.problems

    def test_binary_garbage(self, tmp_path):
        p = tmp_path / "mcub.pub"
        p.write_bytes(b"\xff\xfe\x00\x01" * 50)
        res = kg.check_key(p)
        assert "file is not valid text" in res.problems

    def test_huge_file_is_not_slurped(self, tmp_path):
        p = tmp_path / "mcub.pub"
        p.write_bytes(b"A" * 100_000)
        res = kg.check_key(p)
        assert res.problems == ["file is unexpectedly large"]

    def test_key_type_must_match_key_data(self, real_key):
        real_key.write_text(real_key.read_text().replace("ssh-ed25519", "ssh-rsa", 1))
        res = kg.check_key(real_key)
        assert any("key type" in p for p in res.problems)

    def test_verify_key_raises_with_details(self, real_key):
        real_key.write_bytes(b"x")
        with pytest.raises(kg.KeyIntegrityError) as exc:
            kg.verify_key(real_key)
        assert exc.value.check.problems


@needs_ssh_keygen
class TestFingerprintMatchesOpenSSH:
    @pytest.mark.parametrize(
        "args",
        [["-t", "ed25519"], ["-t", "rsa", "-b", "2048"], ["-t", "ecdsa", "-b", "256"]],
    )
    def test_same_as_ssh_keygen(self, tmp_path, args):
        priv = tmp_path / "k"
        subprocess.check_call(
            ["ssh-keygen", "-q", *args, "-N", "", "-C", "c", "-f", str(priv)]
        )
        pub = Path(str(priv) + ".pub")
        want = subprocess.check_output(["ssh-keygen", "-l", "-f", str(pub)], text=True)
        assert kg.ssh_fingerprint(pub.read_text()) == want.split()[1]

    @pytest.mark.parametrize("line", ["", "ssh-ed25519", "ssh-ed25519 !!!notbase64!!!"])
    def test_rejects_malformed_lines(self, line):
        with pytest.raises(ValueError):
            kg.ssh_fingerprint(line)


class TestEnforceOrExit:
    def test_silent_when_intact(self):
        buf = io.StringIO()
        res = kg.enforce_or_exit(stream=buf)
        assert res.ok
        assert buf.getvalue() == ""

    def test_prints_details_and_exits_on_mismatch(self, real_key):
        real_key.write_text("garbage\n")
        buf = io.StringIO()
        with pytest.raises(SystemExit) as exc:
            kg.enforce_or_exit(real_key, stream=buf)
        assert exc.value.code == 1
        out = buf.getvalue()
        assert "повреждён" in out
        assert "corrupted" in out
        assert "небезопасным для хоста" in out
        assert "unsafe for the host" in out
        assert kg.EXPECTED_SHA256 in out
        assert kg.EXPECTED_FINGERPRINT in out


@pytest.fixture
def boot_dir(tmp_path):
    """A throw-away copy of the bootloader (core/ + mcub.pub)."""
    shutil.copytree(
        REPO_ROOT / "core",
        tmp_path / "core",
        ignore=shutil.ignore_patterns("__pycache__", "web"),
    )
    shutil.copyfile(REPO_ROOT / kg.KEY_FILE_NAME, tmp_path / kg.KEY_FILE_NAME)
    return tmp_path


def boot(cwd: Path):
    """Run the real bootloader entry point far enough to pass (or hit) the guard."""
    return subprocess.run(
        [sys.executable, "-m", "core", "--clear-default-core"],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
    )


class TestStartupRefusal:
    def test_intact_key_lets_startup_continue(self, boot_dir):
        r = boot(boot_dir)
        assert r.returncode == 0, r.stderr
        assert "[security]" not in r.stderr
        assert "No default core was set" in r.stdout

    def test_tampered_key_refuses_to_start(self, boot_dir):
        key = boot_dir / kg.KEY_FILE_NAME
        key.write_text(key.read_text().replace("znullv2", "evil"))
        r = boot(boot_dir)
        assert r.returncode == 1
        assert "No default core was set" not in r.stdout
        assert "повреждён" in r.stderr
        assert "unsafe for the host" in r.stderr
        assert "небезопасным для хоста" in r.stderr
        assert kg.EXPECTED_SHA256 in r.stderr

    def test_missing_key_refuses_to_start(self, boot_dir):
        (boot_dir / kg.KEY_FILE_NAME).unlink()
        r = boot(boot_dir)
        assert r.returncode == 1
        assert "file not found" in r.stderr

    def test_removing_the_guard_does_not_disable_it(self, boot_dir):
        (boot_dir / "core" / "lib" / "utils" / "key_guard.py").unlink()
        r = boot(boot_dir)
        assert r.returncode == 1
        assert "cannot be loaded" in r.stderr
        assert "No default core was set" not in r.stdout
