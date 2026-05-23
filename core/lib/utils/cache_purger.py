# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""Cascading cache purge for MCUB kernel.

Three levels of aggression:

    Level 1 — Safe caches
        Clears TTL, inline sessions, callback maps, docs, metadata.
        All auto-rebuild on next use.  Zero side-effects.

    Level 2 — Extended + stale registries
        Adds stale sys.modules entries, pipe vars, orphan aliases,
        callback permissions, live module configs of unloaded modules.

    Level 3 — Hardcore
        Adds gc.collect(), full sys.modules sweep,
        log queue flush, stale scheduler tasks.
"""

from __future__ import annotations

import gc
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def _dict_clear(obj: Any, attr: str) -> None:
    """Clear *obj.attr* if it is a dict (safe no-op otherwise)."""
    d = getattr(obj, attr, None)
    if isinstance(d, dict):
        d.clear()


def _set_clear(obj: Any, attr: str) -> None:
    s = getattr(obj, attr, None)
    if isinstance(s, set):
        s.clear()


def purge_caches(kernel: Any, level: int = 1) -> dict[str, Any]:
    """Purge kernel caches at *level* (1-3).

    Returns a dict with keys ``{"level", "cleared", "freed_estimate"}``
    describing what was done.
    """
    if not kernel:
        return {"level": level, "cleared": [], "freed_estimate": 0}

    cleared: list[str] = []
    db = getattr(kernel, "db_manager", None)

    # ── Level 1: Safe caches ──────────────────────────────────────────────
    # TTLCache
    ttl = getattr(kernel, "cache", None)
    if ttl and hasattr(ttl, "clear"):
        ttl.clear()
        cleared.append("ttl_cache")

    # Inline sessions
    im = getattr(kernel, "inline_message_manager", None)
    if im and hasattr(im, "_sessions"):
        im._sessions.clear()
        cleared.append("inline_sessions")

    # Callback map
    _dict_clear(kernel, "inline_callback_map")
    cleared.append("inline_callback_map")

    # Hikka-compat inline state (units + custom_map)
    hikka_state = getattr(kernel, "_hikka_compat_inline_state", None)
    if isinstance(hikka_state, dict):
        for _sub in ("units", "custom_map"):
            sub = hikka_state.get(_sub)
            if isinstance(sub, dict):
                sub.clear()
        cleared.append("hikka_compat_inline_state")

    # Hikka-compat inline units direct references (aliases)
    _dict_clear(kernel, "_hikka_compat_inline_units")
    cleared.append("hikka_compat_inline_units")
    _dict_clear(kernel, "_hikka_compat_inline_custom_map")
    cleared.append("hikka_compat_inline_custom_map")

    # Kernel runtime dicts
    for attr in (
        "catalog_cache",
        "pending_confirmations",
        "command_docs",
        "command_metadata",
        "_module_commands_index",
        "_pipe_vars",
        "_pipe_macros",
    ):
        _dict_clear(kernel, attr)
        cleared.append(attr)

    # Module type cache (ModuleDetectorMixin)
    _dict_clear(kernel, "_module_type_cache")
    cleared.append("module_type_cache")

    # Database get cache
    if db and hasattr(db, "_get_cache"):
        _dict_clear(db, "_get_cache")
        cleared.append("db_get_cache")

    # Inline temp registries (ModuleBase class-level — shared across instances)
    for mod_instance in getattr(kernel, "_class_module_instances", {}).values():
        for reg_attr in ("_inline_temp_registry",):
            _dict_clear(mod_instance, reg_attr)
            cleared.append(f"inline_temp:{getattr(mod_instance, 'name', '?')}")

    # ── Level 2: Extended ─────────────────────────────────────────────────
    if level >= 2:
        # Callback permissions
        perms = getattr(kernel, "callback_permissions", None)
        if perms and hasattr(perms, "clear"):
            perms.clear()
            cleared.append("callback_permissions")

        # Live configs of unloaded modules — only keep configs for still-loaded
        live = getattr(kernel, "_live_module_configs", {})
        if live:
            loaded = set(getattr(kernel, "loaded_modules", {})).union(
                getattr(kernel, "system_modules", {})
            )
            for key in list(live):
                if key not in loaded:
                    del live[key]
                    cleared.append(f"live_config_stale:{key}")

        # sys.modules: remove stale user-module entries not in registries
        loaded_names = set(getattr(kernel, "loaded_modules", {}))
        loaded_names.update(getattr(kernel, "system_modules", {}))
        stale_mods = []
        for mod_name, mod in list(sys.modules.items()):
            if mod_name in loaded_names:
                continue
            if mod_name.startswith("mod_") or mod_name.startswith("module_"):
                stale_mods.append(mod_name)
            elif hasattr(mod, "_mcub_module") or hasattr(mod, "register"):
                # Old-style module still hanging around
                file_path = getattr(mod, "__file__", "") or ""
                if "modules_loaded" in file_path or "modules" in file_path:
                    stale_mods.append(mod_name)
        for m in stale_mods:
            sys.modules.pop(m, None)
        if stale_mods:
            cleared.append(f"stale_sys_modules:{len(stale_mods)}")

    # ── Level 3: Hardcore ──────────────────────────────────────────────────
    if level >= 3:
        # Generational GC sweep (all 3 generations)
        for _ in range(3):
            gc.collect(0)
            gc.collect(1)
            gc.collect(2)
        cleared.append("gc_collect")

        # Telegram log queue flush
        from core.lib.utils.logger import _flush_log_queue

        _flush_log_queue()
        cleared.append("log_queue_flush")

        # Event middleware ID set cleanup
        _set_clear(kernel, "_event_middleware_ids")
        _set_clear(kernel, "_request_middleware_ids")
        cleared.append("middleware_id_sets")

        # Telethon entity caches
        for client_attr in ("client", "bot_client"):
            client = getattr(kernel, client_attr, None)
            if client is None:
                continue
            mb_cache = getattr(client, "_mb_entity_cache", None)
            if mb_cache:
                mb_cache.clear()
                cleared.append(f"{client_attr}_mb_entity_cache")
            mg_cache = getattr(client, "_megagroup_cache", None)
            if mg_cache:
                mg_cache.clear()
                cleared.append(f"{client_attr}_megagroup_cache")

        # aiohttp connector cache (default ClientSession connector pool)
        aio_connector = getattr(kernel, "_aiohttp_connector", None)
        if aio_connector is not None:
            try:
                aio_connector._conns.clear()
                aio_connector._cleanup_closed_transports()
                cleared.append("aiohttp_connector")
            except Exception:
                pass

        class_mods = getattr(kernel, "_class_module_instances", {})
        if class_mods:
            for mod_name, inst in list(class_mods.items()):
                _dict_clear(inst, "_inline_temp_registry")
                loops = getattr(inst, "_loops", None)
                if loops and isinstance(loops, dict):
                    loops.clear()
            cleared.append(f"module_inline_clean:{len(class_mods)}")

        # Scheduler task registry
        sched = getattr(kernel, "scheduler", None)
        if sched is not None:
            reg = getattr(sched, "_task_registry", None)
            if reg:
                reg.clear()
                cleared.append("scheduler_registry")

    return {"level": level, "cleared": cleared}
