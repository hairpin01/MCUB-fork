# SPDX-License-Identifier: MIT

from __future__ import annotations

import io
import tarfile
import zipfile
from unittest.mock import MagicMock

import pytest

from core.lib.loader.archive import ArchiveManager, ModuleInfo, PyProjectMeta
from utils.security import safe_extract_archive


def _make_manager() -> ArchiveManager:
    kernel = MagicMock()
    kernel.logger = MagicMock()
    return ArchiveManager(kernel)


def test_detect_type_uses_ast_register_function(tmp_path):
    manager = _make_manager()

    (tmp_path / "a.py").write_text(
        "def register(kernel):\n    pass\n", encoding="utf-8"
    )
    (tmp_path / "b.py").write_text(
        "async def register(kernel):\n    pass\n", encoding="utf-8"
    )

    detected = manager._detect_type(str(tmp_path), PyProjectMeta())

    assert detected == "pack"


def test_find_main_module_supports_modulebase_alias(tmp_path):
    manager = _make_manager()

    (tmp_path / "helper.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "main.py").write_text(
        "import core.lib.loader.module_base as loader\n\n"
        "class Demo(loader.ModuleBase):\n"
        "    name = 'demo'\n",
        encoding="utf-8",
    )

    modules = [
        ModuleInfo(name="helper", file_path="helper.py"),
        ModuleInfo(name="main", file_path="main.py"),
    ]

    main = manager._find_main_module(modules, str(tmp_path))

    assert main is not None
    assert main.name == "main"


def test_safe_extract_archive_blocks_zip_traversal(tmp_path):
    archive_path = tmp_path / "bad.zip"
    target = tmp_path / "target"

    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("../escape.py", "x = 1\n")

    with pytest.raises(ValueError, match="escapes target"):
        safe_extract_archive(archive_path, target)

    assert not (tmp_path / "escape.py").exists()


def test_safe_extract_archive_blocks_tar_symlink(tmp_path):
    archive_path = tmp_path / "bad.tar"
    target = tmp_path / "target"

    with tarfile.open(archive_path, "w") as tf:
        info = tarfile.TarInfo("link.py")
        info.type = tarfile.SYMTYPE
        info.linkname = "../escape.py"
        tf.addfile(info)

    with pytest.raises(ValueError, match="unsafe tar entry"):
        safe_extract_archive(archive_path, target)


def test_safe_extract_archive_extracts_regular_files(tmp_path):
    archive_path = tmp_path / "ok.tar"
    target = tmp_path / "target"
    data = b"x = 1\n"

    with tarfile.open(archive_path, "w") as tf:
        info = tarfile.TarInfo("pkg/mod.py")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))

    safe_extract_archive(archive_path, target)

    assert (target / "pkg" / "mod.py").read_bytes() == data
