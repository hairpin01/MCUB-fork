# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import os
import time
from typing import Any

from aiohttp import web

from core.web.auth import require_auth

logger = logging.getLogger(__name__)

# Forbidden config keys for security (blacklist approach)
FORBIDDEN_CONFIG_KEYS = {
    "api_id",
    "api_hash",
    "phone",
    "password",
    "token",
    "secret",
    "key",
    "db_password",
    "database_url",
}


# Error codes
class ErrorCode:
    KERNEL_UNAVAILABLE = "KERNEL_UNAVAILABLE"
    INVALID_JSON = "INVALID_JSON"
    MISSING_FIELD = "MISSING_FIELD"
    COMMAND_NOT_FOUND = "COMMAND_NOT_FOUND"
    ALIAS_NOT_FOUND = "ALIAS_NOT_FOUND"
    CONFIG_KEY_NOT_FOUND = "CONFIG_KEY_NOT_FOUND"
    CONFIG_KEY_FORBIDDEN = "CONFIG_KEY_FORBIDDEN"
    CONFIG_UNAVAILABLE = "CONFIG_UNAVAILABLE"


def _normalize_prefix(prefix: str | None, fallback: str = "/api/ext") -> str:
    value = (prefix or fallback).strip()
    if not value:
        value = fallback
    if not value.startswith("/"):
        value = f"/{value}"
    return value.rstrip("/") or "/"


def _json_success(data: Any, meta: dict | None = None) -> web.Response:
    response = {"data": data}
    if meta:
        response["meta"] = meta
    return web.json_response(response)


def _json_error(
    message: str,
    code: str = "BAD_REQUEST",
    status: int = 400,
    details: list | None = None,
) -> web.Response:
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    return web.json_response({"error": error}, status=status)


def _kernel_ready(app: web.Application) -> tuple[Any, web.Response | None]:
    kernel = app.get("kernel")
    if kernel is None:
        return None, _json_error(
            "Kernel is not available",
            code=ErrorCode.KERNEL_UNAVAILABLE,
            status=503,
        )
    return kernel, None


def _save_kernel_config(kernel: Any) -> None:
    if hasattr(kernel, "save_config") and callable(kernel.save_config):
        try:
            kernel.save_config()
        except Exception as e:
            logger.error("Failed to save kernel config: %s", e, exc_info=True)


def _get_pagination_params(request: web.Request) -> tuple[int, int]:
    try:
        page = max(1, int(request.query.get("page", "1")))
    except (ValueError, TypeError):
        page = 1
    try:
        page_size = min(100, max(1, int(request.query.get("pageSize", "20"))))
    except (ValueError, TypeError):
        page_size = 20
    return page, page_size


def _paginate(items: list, page: int, page_size: int) -> dict:
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "meta": {
            "total": total,
            "page": page,
            "pageSize": page_size,
            "totalPages": total_pages,
        },
    }


@require_auth
async def api_health(request: web.Request) -> web.Response:
    kernel, err = _kernel_ready(request.app)
    if err:
        return err

    return _json_success(
        {
            "service": "mcub-web-api-extender",
            "time": int(time.time()),
            "prefix": getattr(kernel, "custom_prefix", "."),
            "api_prefix": request.app.get("api_extender_prefix"),
        }
    )


@require_auth
async def api_meta(request: web.Request) -> web.Response:
    kernel, err = _kernel_ready(request.app)
    if err:
        return err

    return _json_success(
        {
            "version": getattr(kernel, "VERSION", "unknown"),
            "uptime": time.time() - getattr(kernel, "start_time", time.time()),
            "modules_count": len(getattr(kernel, "loaded_modules", {})),
            "commands_count": len(getattr(kernel, "command_handlers", {})),
            "aliases_count": len(getattr(kernel, "aliases", {})),
        }
    )


@require_auth
async def api_commands(request: web.Request) -> web.Response:
    kernel, err = _kernel_ready(request.app)
    if err:
        return err

    prefix = getattr(kernel, "custom_prefix", ".")
    commands = sorted((getattr(kernel, "command_handlers", {}) or {}).keys())
    page, page_size = _get_pagination_params(request)
    result = _paginate(commands, page, page_size)
    result["prefix"] = prefix

    return _json_success(result["items"], meta=result["meta"])


@require_auth
async def api_modules(request: web.Request) -> web.Response:
    kernel, err = _kernel_ready(request.app)
    if err:
        return err

    modules = sorted((getattr(kernel, "loaded_modules", {}) or {}).keys())
    page, page_size = _get_pagination_params(request)
    result = _paginate(modules, page, page_size)

    return _json_success(result["items"], meta=result["meta"])


@require_auth
async def api_aliases_list(request: web.Request) -> web.Response:
    kernel, err = _kernel_ready(request.app)
    if err:
        return err

    aliases = dict(sorted((getattr(kernel, "aliases", {}) or {}).items()))
    page, page_size = _get_pagination_params(request)
    items = list(aliases.items())
    result = _paginate(items, page, page_size)

    return _json_success(dict(result["items"]), meta=result["meta"])


@require_auth
async def api_aliases_set(request: web.Request) -> web.Response:
    kernel, err = _kernel_ready(request.app)
    if err:
        return err

    try:
        data = await request.json()
    except Exception:
        return _json_error(
            "Invalid JSON body",
            code=ErrorCode.INVALID_JSON,
            status=400,
        )

    alias = str(data.get("alias", "")).strip()
    command = str(data.get("command", "")).strip()

    if not alias or not command:
        return _json_error(
            "Fields 'alias' and 'command' are required",
            code=ErrorCode.MISSING_FIELD,
            status=400,
            details=[
                {"field": "alias", "message": "Alias cannot be empty"},
                {"field": "command", "message": "Command cannot be empty"},
            ],
        )

    command_name = command.split()[0]
    handlers = getattr(kernel, "command_handlers", {}) or {}
    if command_name not in handlers:
        return _json_error(
            f"Command '{command_name}' not found",
            code=ErrorCode.COMMAND_NOT_FOUND,
            status=404,
        )

    if not hasattr(kernel, "aliases"):
        return _json_error(
            "Kernel does not support aliases",
            code=ErrorCode.KERNEL_UNAVAILABLE,
            status=500,
        )

    kernel.aliases[alias] = command
    logger.info("Alias set: %s -> %s", alias, command)

    if hasattr(kernel, "config") and isinstance(kernel.config, dict):
        kernel.config["aliases"] = kernel.aliases
        _save_kernel_config(kernel)

    return _json_success({"alias": alias, "command": command})


@require_auth
async def api_aliases_delete(request: web.Request) -> web.Response:
    kernel, err = _kernel_ready(request.app)
    if err:
        return err

    alias = request.match_info.get("alias", "").strip()
    if not alias:
        return _json_error(
            "Alias is required",
            code=ErrorCode.MISSING_FIELD,
            status=400,
        )

    if alias not in getattr(kernel, "aliases", {}):
        return _json_error(
            f"Alias '{alias}' not found",
            code=ErrorCode.ALIAS_NOT_FOUND,
            status=404,
        )

    del kernel.aliases[alias]
    logger.info("Alias deleted: %s", alias)

    if hasattr(kernel, "config") and isinstance(kernel.config, dict):
        kernel.config["aliases"] = kernel.aliases
        _save_kernel_config(kernel)

    return _json_success({"deleted": alias})


@require_auth
async def api_prefix_get(request: web.Request) -> web.Response:
    kernel, err = _kernel_ready(request.app)
    if err:
        return err

    return _json_success({"prefix": getattr(kernel, "custom_prefix", ".")})


@require_auth
async def api_prefix_set(request: web.Request) -> web.Response:
    kernel, err = _kernel_ready(request.app)
    if err:
        return err

    try:
        data = await request.json()
    except Exception:
        return _json_error(
            "Invalid JSON body",
            code=ErrorCode.INVALID_JSON,
            status=400,
        )

    new_prefix = str(data.get("prefix", "")).strip()
    if not new_prefix:
        return _json_error(
            "Field 'prefix' is required",
            code=ErrorCode.MISSING_FIELD,
            status=400,
        )

    old_prefix = getattr(kernel, "custom_prefix", ".")
    kernel.custom_prefix = new_prefix
    logger.info("Prefix changed: %s -> %s", old_prefix, new_prefix)

    if hasattr(kernel, "config") and isinstance(kernel.config, dict):
        kernel.config["command_prefix"] = new_prefix
        _save_kernel_config(kernel)

    return _json_success({"old_prefix": old_prefix, "prefix": new_prefix})


@require_auth
async def api_config_get(request: web.Request) -> web.Response:
    kernel, err = _kernel_ready(request.app)
    if err:
        return err

    key = request.query.get("key", "").strip()
    if not key:
        return _json_error(
            "Query param 'key' is required",
            code=ErrorCode.MISSING_FIELD,
            status=400,
        )

    config = getattr(kernel, "config", {}) or {}
    if key not in config:
        return _json_error(
            f"Config key '{key}' not found",
            code=ErrorCode.CONFIG_KEY_NOT_FOUND,
            status=404,
        )

    return _json_success({"key": key, "value": config[key]})


@require_auth
async def api_config_set(request: web.Request) -> web.Response:
    kernel, err = _kernel_ready(request.app)
    if err:
        return err

    try:
        data = await request.json()
    except Exception:
        return _json_error(
            "Invalid JSON body",
            code=ErrorCode.INVALID_JSON,
            status=400,
        )

    key = str(data.get("key", "")).strip()
    value = data.get("value")

    if not key:
        return _json_error(
            "Field 'key' is required",
            code=ErrorCode.MISSING_FIELD,
            status=400,
        )

    if key in FORBIDDEN_CONFIG_KEYS:
        return _json_error(
            f"Config key '{key}' is forbidden",
            code=ErrorCode.CONFIG_KEY_FORBIDDEN,
            status=403,
        )

    if not hasattr(kernel, "config") or not isinstance(kernel.config, dict):
        return _json_error(
            "Kernel config is unavailable",
            code=ErrorCode.CONFIG_UNAVAILABLE,
            status=500,
        )

    old_value = kernel.config.get(key)
    kernel.config[key] = value
    logger.info("Config key '%s' changed: %s -> %s", key, old_value, value)

    _save_kernel_config(kernel)

    return _json_success({"key": key, "value": value})


@require_auth
async def api_routes(request: web.Request) -> web.Response:
    routes = []
    for route in request.app.router.routes():
        info = route.get_info()
        path = info.get("path") or info.get("formatter") or "<dynamic>"
        routes.append({"method": route.method, "path": path})

    routes.sort(key=lambda item: (item["path"], item["method"]))
    page, page_size = _get_pagination_params(request)
    result = _paginate(routes, page, page_size)

    return _json_success(result["items"], meta=result["meta"])


def _register_routes(app: web.Application, prefix: str) -> None:
    app.router.add_get(f"{prefix}/health", api_health)
    app.router.add_get(f"{prefix}/meta", api_meta)
    app.router.add_get(f"{prefix}/routes", api_routes)
    app.router.add_get(f"{prefix}/commands", api_commands)
    app.router.add_get(f"{prefix}/modules", api_modules)
    app.router.add_get(f"{prefix}/aliases", api_aliases_list)
    app.router.add_post(f"{prefix}/aliases", api_aliases_set)
    app.router.add_delete(f"{prefix}/aliases/{{alias}}", api_aliases_delete)
    app.router.add_get(f"{prefix}/prefix", api_prefix_get)
    app.router.add_post(f"{prefix}/prefix", api_prefix_set)
    app.router.add_get(f"{prefix}/config", api_config_get)
    app.router.add_post(f"{prefix}/config", api_config_set)


def setup(app: web.Application, kernel: Any) -> None:
    config_prefix = None
    if kernel is not None and hasattr(kernel, "config"):
        ext_cfg = kernel.config.get("web_api_extender")
        if isinstance(ext_cfg, dict):
            config_prefix = ext_cfg.get("prefix")

    env_prefix = os.environ.get("MCUB_WEB_API_PREFIX")
    prefix = _normalize_prefix(env_prefix or config_prefix or "/api/ext")

    app["api_extender_prefix"] = prefix

    _register_routes(app, prefix)

    # Extra compatibility paths: old clients can call the same API via /api/ext/v1
    if not prefix.endswith("/v1"):
        _register_routes(app, f"{prefix}/v1")
