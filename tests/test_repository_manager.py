#!/usr/bin/env python3

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


class FakeResponse:
    def __init__(self, status: int, text: str = "") -> None:
        self.status = status
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def text(self) -> str:
        return self._text


class FakeSession:
    def __init__(self, routes: dict[str, tuple[int, str] | Exception]) -> None:
        self._routes = routes

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def get(self, url: str):
        result = self._routes.get(url, (404, ""))
        if isinstance(result, Exception):
            raise result
        status, text = result
        return FakeResponse(status, text)


def make_kernel(tmp_path=None):
    return SimpleNamespace(
        repositories=[],
        default_repo="https://repo.example/default",
        config={},
        CONFIG_FILE=str(tmp_path / "config.json") if tmp_path else "config.json",
        logger=MagicMock(),
        handle_error=AsyncMock(),
    )


def patch_aiohttp(monkeypatch, routes: dict[str, tuple[int, str] | Exception]) -> None:
    from core.lib.loader import repository as repository_mod

    monkeypatch.setattr(
        repository_mod,
        "aiohttp",
        SimpleNamespace(ClientSession=lambda: FakeSession(routes)),
    )


def test_parse_repo_modules_list_ignores_comments_and_normalizes_py_suffix():
    from core.lib.loader.repository import parse_repo_modules_list

    assert (
        parse_repo_modules_list(
            """
        # comment
        alpha
        beta.py
        gamma.py  # inline comment
        ; another comment
        alpha
        """
        )
        == ["alpha", "beta", "gamma"]
    )


@pytest.mark.asyncio
async def test_get_modules_list_merges_modules_ini_and_full_txt(monkeypatch):
    from core.lib.loader.repository import RepositoryManager

    routes = {
        "https://repo.example/base/modules.ini": (200, "alpha\nbeta.py\n"),
        "https://repo.example/base/full.txt": (200, "beta\ngamma.py\n"),
    }
    patch_aiohttp(monkeypatch, routes)

    manager = RepositoryManager(make_kernel())

    assert await manager.get_modules_list("https://repo.example/base/") == [
        "alpha",
        "beta",
        "gamma",
    ]


@pytest.mark.asyncio
async def test_get_modules_list_uses_full_txt_when_modules_ini_missing(monkeypatch):
    from core.lib.loader.repository import RepositoryManager

    routes = {
        "https://repo.example/base/modules.ini": (404, ""),
        "https://repo.example/base/full.txt": (200, "full-only\nother.py\n"),
    }
    patch_aiohttp(monkeypatch, routes)

    manager = RepositoryManager(make_kernel())

    assert await manager.get_modules_list("https://repo.example/base") == [
        "full-only",
        "other",
    ]


@pytest.mark.asyncio
async def test_get_modules_list_keeps_modules_ini_if_full_txt_errors(monkeypatch):
    from core.lib.loader.repository import RepositoryManager

    routes = {
        "https://repo.example/base/modules.ini": (200, "legacy\n"),
        "https://repo.example/base/full.txt": RuntimeError("network"),
    }
    kernel = make_kernel()
    patch_aiohttp(monkeypatch, routes)

    manager = RepositoryManager(kernel)

    assert await manager.get_modules_list("https://repo.example/base") == ["legacy"]
    kernel.handle_error.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_repository_accepts_full_txt_only(monkeypatch, tmp_path):
    from core.lib.loader.repository import RepositoryManager

    routes = {
        "https://repo.example/base/modules.ini": (404, ""),
        "https://repo.example/base/full.txt": (200, "one\ntwo\n"),
    }
    patch_aiohttp(monkeypatch, routes)

    kernel = make_kernel(tmp_path)
    manager = RepositoryManager(kernel)
    monkeypatch.setattr(manager, "_validate_url", lambda _url: (True, ""))

    ok, message = await manager.add("https://repo.example/base")

    assert ok is True
    assert message == "Repository added (2 modules)"
    assert kernel.repositories == ["https://repo.example/base"]
