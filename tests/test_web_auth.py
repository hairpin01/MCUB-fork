# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from core.web.auth import AuthMiddleware, generate_auth_config, hash_token


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
