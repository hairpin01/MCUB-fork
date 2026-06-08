# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""
Web panel authentication middleware.
"""

import hashlib
import secrets
from collections.abc import Awaitable, Callable

from aiohttp import web

from . import app_keys


def generate_token(length: int = 32) -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """Hash a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


class AuthMiddleware:
    """
    Token-based authentication middleware for aiohttp web panel.

    Supports:
    - Token authentication via Authorization header
    - Bypass for setup wizard endpoints
    - Configurable via config.json
    """

    PUBLIC_PATHS = {
        "/",
        "/static",
        "/static/img",
    }

    PUBLIC_API_PATHS = {
        "/api/setup/send_code",
        "/api/setup/verify_code",
        "/api/setup/qr_login",
        "/api/setup/qr_poll",
        "/api/setup/state",
        "/api/setup/complete",
        "/api/bot/verify_token",
        "/api/bot/save_token",
        "/api/bot/auto_create",
        "/api/setup/prefill",
    }

    def __init__(self, app: web.Application):
        self.app = app
        self.token_hash: str | None = None
        self.auth_enabled: bool = False
        self._setup_auth()
        self.install(app)

    def _setup_auth(self) -> None:
        """Load auth configuration from app state."""
        kernel = self.app.get(app_keys.KERNEL)
        config = {}

        if kernel is not None:
            config = kernel.config
        elif self.app.get(app_keys.SETUP_STATE):
            config_path = "config.json"
            import os

            if os.path.exists(config_path):
                import json

                try:
                    with open(config_path) as f:
                        config = json.load(f)
                except Exception:
                    pass

        web_token = config.get("web_panel_token")
        configured_hash = config.get("web_panel_token_hash")
        self.auth_enabled = bool(web_token or configured_hash)

        if web_token:
            self.token_hash = hash_token(web_token)
        elif configured_hash:
            self.token_hash = configured_hash

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (setup wizard)."""
        if path in self.PUBLIC_PATHS:
            return True
        if path.startswith("/static"):
            return True
        if path in self.PUBLIC_API_PATHS and self.app.get(app_keys.SETUP_MODE, False):
            return True
        return False

    def install(self, app: web.Application) -> None:
        """Install auth middleware into aiohttp app once."""
        middlewares = getattr(app, "middlewares", None)
        if middlewares is None or self.middleware in middlewares:
            return
        middlewares.append(self.middleware)

    @web.middleware
    async def middleware(
        self,
        request: web.Request,
        handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
    ) -> web.StreamResponse:
        """Validate requests before protected handlers run."""
        if not self.auth_enabled:
            return await handler(request)

        if self._is_public_path(request.path):
            return await handler(request)

        if await self._authenticate(request):
            return await handler(request)

        return web.json_response(
            {"error": "Unauthorized. Provide valid token in Authorization header."},
            status=401,
        )

    async def _authenticate(self, request: web.Request) -> bool:
        """Authenticate request using token from Authorization header."""
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return False

        token = auth_header[7:]
        provided_hash = hash_token(token)

        return bool(self.token_hash) and secrets.compare_digest(
            provided_hash, self.token_hash
        )

    async def __call__(self, app: web.Application) -> None:
        """Backward-compatible middleware installer."""
        self.install(app)


def require_auth(func: Callable) -> Callable:
    """
    Decorator to mark a handler as requiring authentication.
    Can be used for additional protection on sensitive endpoints.
    """

    async def wrapper(request: web.Request, *args, **kwargs) -> web.Response:
        auth_middleware = request.app.get(app_keys.AUTH_MIDDLEWARE)
        if auth_middleware and auth_middleware.auth_enabled:
            if not await auth_middleware._authenticate(request):
                return web.json_response({"error": "Unauthorized"}, status=401)
        return await func(request, *args, **kwargs)

    return wrapper


async def generate_auth_config() -> dict:
    """Generate auth configuration for config.json."""
    token = generate_token()
    return {
        "web_panel_token": token,
        "web_panel_token_hash": hash_token(token),
    }
