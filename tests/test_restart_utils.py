"""
Tests for utils.restart.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from utils import restart as restart_utils


class TestBuildSafeRestartArgs:
    def test_keeps_only_allowed_flags_and_values(self):
        args = restart_utils.build_safe_restart_args(
            argv=[
                "--no-web",
                "--port",
                "8080",
                "--host=0.0.0.0",
                "--unknown",
                "x",
            ],
            entrypoint="/tmp/core/__main__.py",
        )
        assert args == ["-m", "core", "--no-web", "--port", "8080", "--host=0.0.0.0"]

    def test_drops_missing_value_for_proxy_web(self):
        args = restart_utils.build_safe_restart_args(
            argv=["--proxy-web", "--port", "8080"],
            entrypoint="/tmp/core/__main__.py",
        )
        assert args == ["-m", "core", "--port", "8080"]

    def test_keeps_inline_value_for_proxy_web(self):
        args = restart_utils.build_safe_restart_args(
            argv=["--proxy-web=/web", "--core", "zen"],
            entrypoint="/tmp/core/__main__.py",
        )
        assert args == ["-m", "core", "--proxy-web=/web", "--core", "zen"]


class TestSafeRestart:
    def test_safe_restart_execv_with_sanitized_args(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(restart_utils.sys, "executable", "/usr/bin/python3")

        def _fake_execv(executable, argv):
            captured["executable"] = executable
            captured["argv"] = argv

        monkeypatch.setattr(restart_utils.os, "execv", _fake_execv)
        restart_utils.safe_restart(
            argv=["--proxy-web", "--port", "8080"],
            entrypoint="/tmp/core/__main__.py",
        )

        assert captured["executable"] == "/usr/bin/python3"
        assert captured["argv"] == ["/usr/bin/python3", "-m", "core", "--port", "8080"]


class TestWriteRestartFile:
    def test_write_restart_file_with_thread(self, tmp_path: Path):
        restart_file = tmp_path / "restart.tmp"
        restart_utils.write_restart_file(
            str(restart_file), chat_id=1, message_id=2, thread_id=3
        )
        parts = restart_file.read_text(encoding="utf-8").split(",")
        assert parts[0] == "1"
        assert parts[1] == "2"
        assert parts[3] == "3"
        assert float(parts[2]) > 0


class TestRestartKernel:
    @pytest.mark.asyncio
    async def test_restart_kernel_writes_csv_and_closes_resources(
        self, tmp_path: Path, monkeypatch
    ):
        restart_file = tmp_path / "restart.tmp"
        kernel = SimpleNamespace(
            logger=Mock(),
            RESTART_FILE=str(restart_file),
            db_conn=AsyncMock(),
            scheduler=Mock(),
        )
        called = {"restart": False}

        def _fake_restart(argv=None, entrypoint=None):
            called["restart"] = True

        monkeypatch.setattr(restart_utils, "safe_restart", _fake_restart)

        await restart_utils.restart_kernel(
            kernel, chat_id=10, message_id=20, thread_id=30
        )

        assert called["restart"] is True
        kernel.db_conn.close.assert_awaited_once()
        kernel.scheduler.cancel_all_tasks.assert_called_once()

        parts = restart_file.read_text(encoding="utf-8").split(",")
        assert parts[0] == "10"
        assert parts[1] == "20"
        assert parts[3] == "30"

    @pytest.mark.asyncio
    async def test_restart_kernel_without_message_id_does_not_write_file(
        self, tmp_path: Path, monkeypatch
    ):
        restart_file = tmp_path / "restart.tmp"
        kernel = SimpleNamespace(
            logger=Mock(),
            RESTART_FILE=str(restart_file),
            db_conn=None,
            scheduler=None,
        )
        monkeypatch.setattr(
            restart_utils, "safe_restart", lambda argv=None, entrypoint=None: None
        )

        await restart_utils.restart_kernel(kernel, chat_id=10, message_id=None)
        assert restart_file.exists() is False
