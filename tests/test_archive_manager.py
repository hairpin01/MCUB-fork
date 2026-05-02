# SPDX-License-Identifier: MIT

from __future__ import annotations

from unittest.mock import MagicMock

from core.lib.loader.archive import ArchiveManager, ModuleInfo, PyProjectMeta


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
