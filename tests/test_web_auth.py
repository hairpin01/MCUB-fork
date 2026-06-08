# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiohttp import web
from multidict import CIMultiDict

from core.web import app_keys
from core.web.auth import AuthMiddleware, generate_auth_config, hash_token

TOKEN_KEY = "web_panel_" + "token"
TOKEN_HASH_KEY = TOKEN_KEY + "_hash"
VALID_AUTH_VALUE = "sample-value"
INVALID_AUTH_VALUE = "other-value"


class FakeAiohttpApp(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.middlewares = []


def make_auth(
    token: str | None = VALID_AUTH_VALUE, *, setup_mode: bool = False
) -> AuthMiddleware:
    app = {app_keys.KERNEL: SimpleNamespace(config={}), app_keys.SETUP_MODE: setup_mode}
    if token is not None:
        app[app_keys.KERNEL].config[TOKEN_KEY] = token
    return AuthMiddleware(app)  # type: ignore[arg-type]


def test_auth_middleware_is_disabled_without_token():
    auth = make_auth(token=None)

    assert auth.auth_enabled is False
    assert auth.token_hash is None


def test_auth_middleware_accepts_valid_bearer_token():
    auth = make_auth(VALID_AUTH_VALUE)
    request = SimpleNamespace(headers={"Authorization": f"Bearer {VALID_AUTH_VALUE}"})

    assert auth.auth_enabled is True
    assert asyncio.run(auth._authenticate(request)) is True


def test_auth_middleware_rejects_missing_or_invalid_token():
    auth = make_auth(VALID_AUTH_VALUE)

    missing = SimpleNamespace(headers={})
    invalid = SimpleNamespace(headers={"Authorization": f"Bearer {INVALID_AUTH_VALUE}"})

    assert asyncio.run(auth._authenticate(missing)) is False
    assert asyncio.run(auth._authenticate(invalid)) is False


def test_setup_and_bot_paths_stay_public_for_low_friction_setup():
    auth = make_auth(VALID_AUTH_VALUE, setup_mode=True)

    public_paths = [
        "/",
        "/api/setup/state",
        "/api/setup/send_code",
        "/api/bot/save_token",
    ]

    for path in public_paths:
        assert auth._is_public_path(path) is True

    assert auth._is_public_path("/setup/reset") is False
    assert auth._is_public_path("/api/modules") is False


def test_generate_auth_config_hash_matches_token():
    cfg = asyncio.run(generate_auth_config())

    assert cfg[TOKEN_KEY]
    assert cfg[TOKEN_HASH_KEY] == hash_token(cfg[TOKEN_KEY])
    assert cfg[TOKEN_HASH_KEY] != cfg[TOKEN_KEY]


def test_auth_middleware_installs_itself_on_aiohttp_app():
    app = FakeAiohttpApp(
        {app_keys.KERNEL: SimpleNamespace(config={TOKEN_KEY: VALID_AUTH_VALUE})}
    )

    auth = AuthMiddleware(app)  # type: ignore[arg-type]

    assert auth.middleware in app.middlewares


def test_auth_middleware_accepts_hash_only_config():
    app = {
        app_keys.KERNEL: SimpleNamespace(
            config={TOKEN_HASH_KEY: hash_token(VALID_AUTH_VALUE)}
        )
    }

    auth = AuthMiddleware(app)  # type: ignore[arg-type]
    request = SimpleNamespace(headers={"Authorization": f"Bearer {VALID_AUTH_VALUE}"})

    assert auth.auth_enabled is True
    assert auth.token_hash == hash_token(VALID_AUTH_VALUE)
    assert asyncio.run(auth._authenticate(request)) is True


def test_auth_middleware_rejects_protected_request_before_handler():
    auth = make_auth(VALID_AUTH_VALUE)
    request = SimpleNamespace(path="/api/modules", headers=CIMultiDict())
    handler = AsyncMock()

    response = asyncio.run(auth.middleware(request, handler))
    payload = json.loads(response.text)

    assert response.status == 401
    assert "Unauthorized" in payload["error"]
    handler.assert_not_awaited()


def test_auth_middleware_allows_public_request_to_handler():
    auth = make_auth(VALID_AUTH_VALUE, setup_mode=True)
    request = SimpleNamespace(path="/api/setup/state", headers=CIMultiDict())
    handler = AsyncMock(return_value=web.json_response({"ok": True}))

    response = asyncio.run(auth.middleware(request, handler))

    assert response.status == 200
    handler.assert_awaited_once_with(request)


def test_bot_start_and_status_paths_require_auth():
    auth = make_auth(VALID_AUTH_VALUE, setup_mode=True)

    assert auth._is_public_path("/api/bot/verify_token") is True
    assert auth._is_public_path("/api/bot/save_token") is True
    assert auth._is_public_path("/api/bot/auto_create") is True
    assert auth._is_public_path("/api/bot/start") is False
    assert auth._is_public_path("/api/bot/status") is False
