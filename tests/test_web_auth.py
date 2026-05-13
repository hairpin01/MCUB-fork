# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiohttp import web
from multidict import CIMultiDict

from core.web.auth import AuthMiddleware, generate_auth_config, hash_token


class FakeAiohttpApp(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.middlewares = []


def make_auth(token: str | None = "dev-token") -> AuthMiddleware:
    app = {"kernel": SimpleNamespace(config={})}
    if token is not None:
        app["kernel"].config["web_panel_token"] = token
    return AuthMiddleware(app)  # type: ignore[arg-type]


def test_auth_middleware_is_disabled_without_token():
    auth = make_auth(token=None)

    assert auth.auth_enabled is False
    assert auth.token_hash is None


def test_auth_middleware_accepts_valid_bearer_token():
    auth = make_auth("secret-token")
    request = SimpleNamespace(headers={"Authorization": "Bearer secret-token"})

    assert auth.auth_enabled is True
    assert asyncio.run(auth._authenticate(request)) is True


def test_auth_middleware_rejects_missing_or_invalid_token():
    auth = make_auth("secret-token")

    missing = SimpleNamespace(headers={})
    invalid = SimpleNamespace(headers={"Authorization": "Bearer wrong-token"})

    assert asyncio.run(auth._authenticate(missing)) is False
    assert asyncio.run(auth._authenticate(invalid)) is False


def test_setup_and_bot_paths_stay_public_for_low_friction_setup():
    auth = make_auth("secret-token")

    public_paths = [
        "/",
        "/setup/reset",
        "/api/setup/state",
        "/api/setup/send_code",
        "/api/bot/save_token",
    ]

    for path in public_paths:
        assert auth._is_public_path(path) is True

    assert auth._is_public_path("/api/modules") is False


def test_generate_auth_config_hash_matches_token():
    cfg = asyncio.run(generate_auth_config())

    assert cfg["web_panel_token"]
    assert cfg["web_panel_token_hash"] == hash_token(cfg["web_panel_token"])
    assert cfg["web_panel_token_hash"] != cfg["web_panel_token"]


def test_auth_middleware_installs_itself_on_aiohttp_app():
    app = FakeAiohttpApp(
        {"kernel": SimpleNamespace(config={"web_panel_token": "secret-token"})}
    )

    auth = AuthMiddleware(app)  # type: ignore[arg-type]

    assert auth.middleware in app.middlewares


def test_auth_middleware_accepts_hash_only_config():
    app = {
        "kernel": SimpleNamespace(
            config={"web_panel_token_hash": hash_token("secret-token")}
        )
    }

    auth = AuthMiddleware(app)  # type: ignore[arg-type]
    request = SimpleNamespace(headers={"Authorization": "Bearer secret-token"})

    assert auth.auth_enabled is True
    assert auth.token_hash == hash_token("secret-token")
    assert asyncio.run(auth._authenticate(request)) is True


def test_auth_middleware_rejects_protected_request_before_handler():
    auth = make_auth("secret-token")
    request = SimpleNamespace(path="/api/modules", headers=CIMultiDict())
    handler = AsyncMock()

    response = asyncio.run(auth.middleware(request, handler))
    payload = json.loads(response.text)

    assert response.status == 401
    assert "Unauthorized" in payload["error"]
    handler.assert_not_awaited()


def test_auth_middleware_allows_public_request_to_handler():
    auth = make_auth("secret-token")
    request = SimpleNamespace(path="/api/setup/state", headers=CIMultiDict())
    handler = AsyncMock(return_value=web.json_response({"ok": True}))

    response = asyncio.run(auth.middleware(request, handler))

    assert response.status == 200
    handler.assert_awaited_once_with(request)


def test_bot_start_and_status_paths_require_auth():
    auth = make_auth("secret-token")

    assert auth._is_public_path("/api/bot/verify_token") is True
    assert auth._is_public_path("/api/bot/save_token") is True
    assert auth._is_public_path("/api/bot/auto_create") is True
    assert auth._is_public_path("/api/bot/start") is False
    assert auth._is_public_path("/api/bot/status") is False
