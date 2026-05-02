# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import inspect
import re
from collections.abc import Callable
from typing import Any

_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")
_TOKEN_RE = re.compile(r"\{([A-Za-z0-9_]+)\}")

_REGISTRY: dict[str, dict[str, dict[str, Any]]] = {}


def _validate_key(key: str) -> None:
    if not isinstance(key, str) or not _KEY_RE.fullmatch(key):
        raise ValueError("Invalid placeholder key. Use: letters, digits, underscore")


def placeholders(
    key: str,
    *,
    timeout: int | float | None = None,
    description: str | None = None,
    cache_ttl: int | float | None = None,
    required: bool = False,
    on_error: str = "keep",
):
    """Decorator that marks method/function as placeholder provider."""

    _validate_key(key)
    if on_error not in {"keep", "empty", "raise"}:
        raise ValueError("on_error must be one of: keep, empty, raise")

    def decorator(func: Callable):
        meta = list(getattr(func, "__custom_placeholders__", []))
        meta.append(
            {
                "key": key,
                "timeout": timeout,
                "description": description,
                "cache_ttl": cache_ttl,
                "required": required,
                "on_error": on_error,
            }
        )
        setattr(func, "__custom_placeholders__", meta)
        return func

    return decorator


def register_placeholder(
    scope: str,
    key: str,
    callback: Callable,
    *,
    timeout: int | float | None = None,
    description: str | None = None,
    cache_ttl: int | float | None = None,
    required: bool = False,
    on_error: str = "keep",
) -> None:
    _validate_key(key)
    if on_error not in {"keep", "empty", "raise"}:
        raise ValueError("on_error must be one of: keep, empty, raise")
    if scope not in _REGISTRY:
        _REGISTRY[scope] = {}
    _REGISTRY[scope][key] = {
        "callback": callback,
        "timeout": timeout,
        "description": description,
        "cache_ttl": cache_ttl,
        "required": required,
        "on_error": on_error,
    }


def register_decorated_placeholders(scope: str, owner: Any) -> int:
    """Register all @placeholders methods from owner under scope."""

    count = 0
    for attr in dir(owner):
        bound = getattr(owner, attr, None)
        if bound is None or not callable(bound):
            continue
        func = getattr(bound, "__func__", bound)
        metas = getattr(func, "__custom_placeholders__", None)
        if not metas:
            continue
        for meta in metas:
            register_placeholder(
                scope,
                meta["key"],
                bound,
                timeout=meta.get("timeout"),
                description=meta.get("description"),
                cache_ttl=meta.get("cache_ttl"),
                required=bool(meta.get("required", False)),
                on_error=meta.get("on_error", "keep"),
            )
            count += 1
    return count


def unregister_scope(scope: str) -> int:
    removed = len(_REGISTRY.get(scope, {}))
    _REGISTRY.pop(scope, None)
    return removed


def list_placeholder_keys(scope: str) -> list[str]:
    return sorted(_REGISTRY.get(scope, {}).keys())


def format_placeholders(scope: str) -> str:
    return ", ".join(f"{{{key}}}" for key in list_placeholder_keys(scope))


def config_placeholders(scope: str) -> str | None:
    items = _REGISTRY.get(scope, {})
    if not items:
        return None
    return "\n".join(
        f"{{{key}}} - {meta.get('description') or 'No docs'}"
        for key, meta in sorted(items.items(), key=lambda item: item[0])
    )


async def _invoke(callback: Callable, data: dict[str, Any]) -> Any:
    try:
        result = callback(data)
    except TypeError:
        result = callback()
    if inspect.isawaitable(result):
        return await result
    return result


async def get_placeholders(
    scope: str,
    data: dict[str, Any] | None,
    custom_message: str | None,
    *,
    custom_values: dict[str, Any] | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    if data is None:
        data = {}
    custom_values = custom_values or {}
    if custom_message is None:
        return data

    tokens = {m.group(1) for m in _TOKEN_RE.finditer(str(custom_message))}
    scope_items = _REGISTRY.get(scope, {})

    for token in tokens:
        if token in custom_values:
            data[token] = str(custom_values[token])
            continue

        meta = scope_items.get(token)
        if meta is None:
            if strict:
                raise KeyError(f"Unknown placeholder: {{{token}}}")
            continue

        timeout = meta.get("timeout")
        on_error = meta.get("on_error", "keep")
        try:
            coro = _invoke(meta["callback"], data)
            value = await asyncio.wait_for(coro, timeout) if timeout else await coro
            data[token] = str(value)
        except Exception:
            if strict or on_error == "raise":
                raise
            if on_error == "empty":
                data[token] = ""

    if strict:
        missing_required = [
            key
            for key, meta in scope_items.items()
            if meta.get("required")
            and f"{{{key}}}" in str(custom_message)
            and key not in data
        ]
        if missing_required:
            raise KeyError(
                f"Missing required placeholders: {', '.join(sorted(missing_required))}"
            )

    return data


async def resolve_placeholders(
    scope: str,
    template: str,
    *,
    data: dict[str, Any] | None = None,
    custom_values: dict[str, Any] | None = None,
    strict: bool = False,
) -> str:
    context = await get_placeholders(
        scope,
        data or {},
        template,
        custom_values=custom_values,
        strict=strict,
    )

    def repl(match: re.Match[str]) -> str:
        token = match.group(1)
        if token in context:
            return str(context[token])
        if strict:
            raise KeyError(f"Unknown placeholder: {{{token}}}")
        return match.group(0)

    return _TOKEN_RE.sub(repl, str(template or ""))
