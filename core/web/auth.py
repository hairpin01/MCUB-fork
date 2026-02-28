"""
Web panel authentication middleware.
"""

import hashlib
import secrets
import time
from typing import Callable, Optional

from aiohttp import web


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
        "/setup/reset",
    }
    
    PUBLIC_API_PATHS = {
        "/api/setup/send_code",
        "/api/setup/verify_code",
        "/api/setup/state",
        "/api/setup/complete",
        "/api/bot/verify_token",
        "/api/bot/save_token",
        "/api/bot/auto_create",
    }
    
    def __init__(self, app: web.Application):
        self.app = app
        self.token_hash: Optional[str] = None
        self.auth_enabled: bool = False
        self._setup_auth()
    
    def _setup_auth(self) -> None:
        """Load auth configuration from app state."""
        kernel = self.app.get("kernel")
        config = {}
        
        if kernel is not None:
            config = kernel.config
        elif self.app.get("setup_state"):
            config_path = "config.json"
            import os
            if os.path.exists(config_path):
                import json
                try:
                    with open(config_path, "r") as f:
                        config = json.load(f)
                except Exception:
                    pass
        
        web_token = config.get("web_panel_token")
        self.auth_enabled = bool(web_token)
        
        if web_token:
            self.token_hash = hash_token(web_token)
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (setup wizard)."""
        if path in self.PUBLIC_PATHS:
            return True
        if path.startswith("/static"):
            return True
        if path in self.PUBLIC_API_PATHS:
            return True
        if path.startswith("/api/setup") or path.startswith("/api/bot"):
            return True
        return False
    
    async def _authenticate(self, request: web.Request) -> bool:
        """Authenticate request using token from Authorization header."""
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return False
        
        token = auth_header[7:]
        provided_hash = hash_token(token)
        
        return provided_hash == self.token_hash
    
    async def __call__(self, app: web.Application) -> None:
        """Middleware factory."""
        @web.middleware
        async def auth_middleware(request: web.Request, handler: Callable) -> web.Response:
            if not self.auth_enabled:
                return await handler(request)
            
            if self._is_public_path(request.path):
                return await handler(request)
            
            if await self._authenticate(request):
                return await handler(request)
            
            return web.json_response(
                {"error": "Unauthorized. Provide valid token in Authorization header."},
                status=401
            )
        
        app.middlewares.append(auth_middleware)


def require_auth(func: Callable) -> Callable:
    """
    Decorator to mark a handler as requiring authentication.
    Can be used for additional protection on sensitive endpoints.
    """
    async def wrapper(request: web.Request, *args, **kwargs) -> web.Response:
        auth_middleware = request.app.get("auth_middleware")
        if auth_middleware and auth_middleware.auth_enabled:
            if not await auth_middleware._authenticate(request):
                return web.json_response(
                    {"error": "Unauthorized"},
                    status=401
                )
        return await func(request, *args, **kwargs)
    return wrapper


async def generate_auth_config() -> dict:
    """Generate auth configuration for config.json."""
    token = generate_token()
    return {
        "web_panel_token": token,
        "web_panel_token_hash": hash_token(token),
    }
