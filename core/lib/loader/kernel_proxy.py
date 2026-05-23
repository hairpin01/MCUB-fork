# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

from types import MappingProxyType
from typing import Any

from ..utils.exceptions import CallInsecure

# Modules with a ModuleKernelProxy cannot read or write these directly.

PROTECTED_KERNEL_NAMES = frozenset(
    {
        "loaded_modules",
        "system_modules",
        "command_handlers",
        "bot_command_handlers",
        "command_owners",
        "bot_command_owners",
        "aliases",
        "command_metadata",
        "command_docs",
        "inline_handlers",
        "inline_handlers_owners",
        "callback_handlers",
        "callback_permissions",
        "inline_callback_map",
        "_inline_temp_map",
        "_inline_temp_uuids",
        "_class_module_instances",
        "_loader",
        "loader",
        # Internal runtime state that modules must not touch
        "current_loading_module",
        "current_loading_module_type",
        "error_load_modules",
        "_log",
        "_inline_cb_lock",
        "MODULES_DIR",
        "MODULES_LOADED_DIR",
        "CONFIG_FILE",
    }
)


PROTECTED_REGISTER_NAMES = frozenset({"kernel", "_kernel"})


# These could be used to hijack, disconnect, or reconfigure the Telegram
# session outside the kernel's lifecycle.

_CLIENT_DANGEROUS_METHODS = frozenset(
    {
        "disconnect",
        "disconnect_coro",
        "reconnect",
        "logout",
        "sign_out",
        "session",
        "session_name",
        "session_path",
        "on",
        "add_event_handler",
        "remove_event_handler",
        "list_event_handlers",
        "flood_sleep_threshold",
        "parse_mode",
        "set_parse_mode",
        "phone_code_hash",
        "phone",
        "authorization_key",
        "unread_count",
        "catch_up",
    }
)

_DB_DANGEROUS_METHODS = frozenset(
    {
        "close",
        "drop_db",
        "delete_db",
        "remove_db",
        "execute",
        "cur",
        "cursor",
        "conn",
        "connection",
        "_conn",
        "_cursor",
        "_close",
    }
)


def _raise_insecure(name: str, module_name: str) -> None:
    raise CallInsecure(name, module_name) from None


class ModuleRegisterProxy:
    """Safe register facade for user modules.

    Registration calls still go through the real register object so ownership and
    cleanup stay centralized, but modules cannot use ``register.kernel`` as a
    backdoor to mutable kernel internals.
    """

    _LOCAL_NAMES = frozenset(
        {
            "module_name",
            "is_protected",
            "_deny",
            "__class__",
            "__repr__",
            "__dir__",
        }
    )

    def __init__(self, register: Any, module_name: str) -> None:
        object.__setattr__(self, "_register", register)
        object.__setattr__(self, "_module_name", module_name)

    @property
    def module_name(self) -> str:
        return object.__getattribute__(self, "_module_name")

    def is_protected(self, name: str) -> bool:
        return name in PROTECTED_REGISTER_NAMES or (
            name.startswith("_") and not (name.startswith("__") and name.endswith("__"))
        )

    def _deny(self, name: str) -> None:
        _raise_insecure(name, self.module_name)

    def __getattribute__(self, name: str) -> Any:
        if name == "__dict__":
            _raise_insecure(name, object.__getattribute__(self, "_module_name"))
        if name in object.__getattribute__(self, "_LOCAL_NAMES"):
            return object.__getattribute__(self, name)
        if name in PROTECTED_REGISTER_NAMES or (
            name.startswith("_") and not (name.startswith("__") and name.endswith("__"))
        ):
            _raise_insecure(name, object.__getattribute__(self, "_module_name"))
        return getattr(object.__getattribute__(self, "_register"), name)

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Allow direct Telethon API calls: ``await client(SomeRequest(...))``."""
        return await object.__getattribute__(self, "_client")(*args, **kwargs)

    def __setattr__(self, name: str, value: Any) -> None:
        self._deny(name)

    def __delattr__(self, name: str) -> None:
        self._deny(name)

    def __dir__(self) -> list[str]:
        register = object.__getattribute__(self, "_register")
        names = set(dir(register)) - PROTECTED_REGISTER_NAMES
        names = {
            name
            for name in names
            if not name.startswith("_")
            or (name.startswith("__") and name.endswith("__"))
        }
        names.update({"module_name", "is_protected"})
        return sorted(names)

    def __repr__(self) -> str:
        return f"<ModuleRegisterProxy module={self.module_name!r}>"


class ModuleKernelProxy:
    """Safe kernel facade for native user modules.

    The proxy keeps normal userbot capabilities available (client, db, cache,
    config, logging, inline helpers, subprocess imports via normal builtins) but
    raises ``CallInsecure`` for direct access to mutable core registries.
    """

    _LOCAL_NAMES = frozenset(
        {
            "module_name",
            "register",
            "is_protected",
            "lookup_module",
            "get_loaded_module",
            "iter_loaded_module_names",
            "loaded_module_names",
            "loaded_modules_view",
            "system_modules_view",
            "client",
            "_live_module_configs",
            "remove_inline_callback_tokens",
            "store_inline_callback",
            "allow_inline_callback_user",
            "set_live_module_config",
            "get_live_module_config",
            "_ensure_callback_storage",
            "_get_module_state",
            "_deny",
            "__class__",
            "__repr__",
            "__dir__",
            "MODULES_DIR",
            "MODULES_LOADED_DIR",
        }
    )

    def __init__(self, kernel: Any, module_name: str) -> None:
        object.__setattr__(self, "_kernel", kernel)
        object.__setattr__(self, "_module_name", module_name)
        object.__setattr__(self, "_register_proxy", None)
        object.__setattr__(self, "_client_proxy", None)
        object.__setattr__(self, "_config_proxy", None)
        object.__setattr__(self, "_module_state", {})

    @property
    def module_name(self) -> str:
        return object.__getattribute__(self, "_module_name")

    @property
    def register(self) -> ModuleRegisterProxy:
        cached = object.__getattribute__(self, "_register_proxy")
        if cached is None:
            kernel = object.__getattribute__(self, "_kernel")
            cached = ModuleRegisterProxy(kernel.register, self.module_name)
            object.__setattr__(self, "_register_proxy", cached)
        return cached

    @property
    def client(self) -> ClientProxy:
        """Safe client proxy - blocks destructive Telegram API calls."""
        cached = object.__getattribute__(self, "_client_proxy")
        if cached is None:
            kernel = object.__getattribute__(self, "_kernel")
            cached = ClientProxy(kernel.client, self.module_name)
            object.__setattr__(self, "_client_proxy", cached)
        return cached

    def is_protected(self, name: str) -> bool:
        return name in PROTECTED_KERNEL_NAMES or name.startswith("_")

    def _deny(self, name: str) -> None:
        _raise_insecure(name, self.module_name)

    def lookup_module(self, module_name: str, *, all_loaded: bool = False) -> Any:
        """Lookup a module without exposing mutable kernel registries.

        Args:
            module_name: Name, class name, or module ``__name__`` to lookup.
            all_loaded: When true, only return modules already present in the
                fully loaded module maps (``loaded_modules``/``system_modules``).
                This intentionally ignores in-progress class instances.
        """
        needle = str(module_name).lower()
        kernel = object.__getattribute__(self, "_kernel")

        if not all_loaded:
            for name, instance in getattr(
                kernel, "_class_module_instances", {}
            ).items():
                if (
                    str(name).lower() == needle
                    or str(getattr(instance, "name", "")).lower() == needle
                ):
                    return instance

        for collection_name in ("loaded_modules", "system_modules"):
            for name, module in getattr(kernel, collection_name, {}).items():
                instance = getattr(module, "_class_instance", None)
                target = instance or module
                names = {
                    str(name).lower(),
                    str(getattr(target, "name", "")).lower(),
                    str(getattr(module, "__name__", "")).lower(),
                }
                if needle in names:
                    return target

        compat_allmodules = getattr(kernel, "_hikka_compat_allmodules_proxy", None)
        if (
            not all_loaded
            and compat_allmodules is not None
            and hasattr(compat_allmodules, "lookup")
        ):
            return compat_allmodules.lookup(module_name)

        return None

    def get_loaded_module(self, module_name: str, *, all_loaded: bool = False) -> Any:
        return self.lookup_module(module_name, all_loaded=all_loaded)

    def iter_loaded_module_names(self) -> tuple[str, ...]:
        kernel = object.__getattribute__(self, "_kernel")
        names = set(getattr(kernel, "loaded_modules", {}).keys())
        names.update(getattr(kernel, "system_modules", {}).keys())
        return tuple(sorted(str(name) for name in names))

    @property
    def loaded_module_names(self) -> tuple[str, ...]:
        return self.iter_loaded_module_names()

    @property
    def loaded_modules_view(self) -> MappingProxyType:
        kernel = object.__getattribute__(self, "_kernel")
        return MappingProxyType(dict(getattr(kernel, "loaded_modules", {})))

    @property
    def system_modules_view(self) -> MappingProxyType:
        kernel = object.__getattribute__(self, "_kernel")
        return MappingProxyType(dict(getattr(kernel, "system_modules", {})))

    @property
    def MODULES_DIR(self) -> str:
        return object.__getattribute__(self, "_kernel").MODULES_DIR

    @property
    def MODULES_LOADED_DIR(self) -> str:
        return object.__getattribute__(self, "_kernel").MODULES_LOADED_DIR

    @property
    def _live_module_configs(self) -> MappingProxyType:
        """Read-only compatibility view for modules checking live config.

        Older MCUB/repo modules commonly use
        ``getattr(kernel, "_live_module_configs", {}).get(__name__)``. Keep that
        read path working without exposing the mutable kernel mapping itself.
        Mutations must go through ``set_live_module_config``.
        """
        kernel = object.__getattribute__(self, "_kernel")
        return MappingProxyType(dict(getattr(kernel, "_live_module_configs", {})))

    def _get_module_state(self) -> dict[str, Any]:
        return object.__getattribute__(self, "_module_state")

    def _ensure_callback_storage(self) -> tuple[Any, dict[str, Any]]:
        import threading

        kernel = object.__getattribute__(self, "_kernel")
        lock = getattr(kernel, "_inline_cb_lock", None)
        cb_map = getattr(kernel, "inline_callback_map", None)
        if lock is None:
            lock = threading.Lock()
            kernel._inline_cb_lock = lock
        if cb_map is None:
            cb_map = {}
            kernel.inline_callback_map = cb_map
        return lock, cb_map

    def remove_inline_callback_tokens(
        self, tokens: list[str] | tuple[str, ...]
    ) -> None:
        lock, cb_map = self._ensure_callback_storage()
        with lock:
            for token in tokens:
                cb_map.pop(token, None)

    def store_inline_callback(self, token: str, data: dict[str, Any]) -> None:
        import time

        lock, cb_map = self._ensure_callback_storage()
        with lock:
            now = time.time()
            expired = [
                key
                for key, value in list(cb_map.items())
                if value.get("expires_at") and value["expires_at"] < now
            ]
            for key in expired:
                cb_map.pop(key, None)
            cb_map[token] = data

    def allow_inline_callback_user(
        self, user_id: int, token: str, allow_ttl: int
    ) -> None:
        kernel = object.__getattribute__(self, "_kernel")
        permissions = getattr(kernel, "callback_permissions", None)
        if permissions is None:
            from ..base.permissions import CallbackPermissionManager

            permissions = CallbackPermissionManager()
            kernel.callback_permissions = permissions
        permissions.allow(user_id, token, allow_ttl)

    def set_live_module_config(self, module_name: str, config: Any) -> None:
        kernel = object.__getattribute__(self, "_kernel")
        live_configs = getattr(kernel, "_live_module_configs", None)
        if live_configs is None:
            live_configs = {}
            kernel._live_module_configs = live_configs
        live_configs[module_name] = config

    def get_live_module_config(self, module_name: str, default: Any = None) -> Any:
        kernel = object.__getattribute__(self, "_kernel")
        live_configs = getattr(kernel, "_live_module_configs", None) or {}
        return live_configs.get(module_name, default)

    def __getattribute__(self, name: str) -> Any:
        if name == "__dict__":
            _raise_insecure(name, object.__getattribute__(self, "_module_name"))
        if name in object.__getattribute__(self, "_LOCAL_NAMES"):
            return object.__getattribute__(self, name)
        if name in PROTECTED_KERNEL_NAMES or (
            name.startswith("_") and not (name.startswith("__") and name.endswith("__"))
        ):
            _raise_insecure(name, object.__getattribute__(self, "_module_name"))
        module_state = object.__getattribute__(self, "_module_state")
        if name in module_state:
            return module_state[name]
        return getattr(object.__getattribute__(self, "_kernel"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if (
            name.startswith("_") and not (name.startswith("__") and name.endswith("__"))
        ) or name in PROTECTED_KERNEL_NAMES:
            self._deny(name)
        object.__getattribute__(self, "_module_state")[name] = value

    def __delattr__(self, name: str) -> None:
        self._deny(name)

    def __dir__(self) -> list[str]:
        kernel = object.__getattribute__(self, "_kernel")
        names = set(dir(kernel)) - PROTECTED_KERNEL_NAMES
        names = {
            name
            for name in names
            if not name.startswith("_")
            or (name.startswith("__") and name.endswith("__"))
        }
        names.update(
            {
                "module_name",
                "register",
                "client",
                "is_protected",
                "lookup_module",
                "get_loaded_module",
                "iter_loaded_module_names",
                "loaded_module_names",
                "loaded_modules_view",
                "system_modules_view",
                "MODULES_DIR",
                "MODULES_LOADED_DIR",
                "_live_module_configs",
                "remove_inline_callback_tokens",
                "store_inline_callback",
                "allow_inline_callback_user",
                "set_live_module_config",
                "get_live_module_config",
            }
        )
        return sorted(names)

    def __repr__(self) -> str:
        return f"<ModuleKernelProxy module={self.module_name!r}>"


class ClientProxy:
    """Safe TelegramClient facade for user modules.

    Allows benign Telegram API calls (``send_message``, ``get_entity``,
    ``get_messages``, ``upload_file``, etc.) but blocks destructive operations
    like ``disconnect``, ``logout``, ``session`` access, or direct event
    subscription that should be managed by the kernel.

    The real client is accessible only from kernel/system code; user modules
    receive this proxy as ``module.client``.
    """

    _LOCAL_NAMES = frozenset(
        {
            "module_name",
            "is_safe_method",
            "_deny",
            "__class__",
            "__repr__",
            "__dir__",
        }
    )

    def __init__(self, client: Any, module_name: str) -> None:
        object.__setattr__(self, "_client", client)
        object.__setattr__(self, "_module_name", module_name)

    @property
    def module_name(self) -> str:
        return object.__getattribute__(self, "_module_name")

    @staticmethod
    def is_safe_method(name: str) -> bool:
        """Return True if *name* is a safe client attribute/method for modules."""
        if name.startswith("__") and name.endswith("__"):
            return True
        if name.startswith("_"):
            return False
        if name in ("is_safe_method", "module_name"):
            return True
        return name not in _CLIENT_DANGEROUS_METHODS

    def _deny(self, name: str) -> None:
        _raise_insecure(name, self.module_name)

    def __getattribute__(self, name: str) -> Any:
        if name == "__dict__":
            _raise_insecure(name, object.__getattribute__(self, "_module_name"))
        if name in object.__getattribute__(self, "_LOCAL_NAMES"):
            return object.__getattribute__(self, name)
        # Allow __dunder__ methods through (__class__, __call__, etc.)
        if name.startswith("__") and name.endswith("__"):
            return object.__getattribute__(self, name)
        if not ClientProxy.is_safe_method(name):
            _raise_insecure(name, object.__getattribute__(self, "_module_name"))
        return getattr(object.__getattribute__(self, "_client"), name)

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Allow direct Telethon API calls: ``await client(SomeRequest(...))``."""
        return await object.__getattribute__(self, "_client")(*args, **kwargs)

    def __setattr__(self, name: str, value: Any) -> None:
        self._deny(name)

    def __delattr__(self, name: str) -> None:
        self._deny(name)

    def __dir__(self) -> list[str]:
        client = object.__getattribute__(self, "_client")
        return sorted(name for name in dir(client) if ClientProxy.is_safe_method(name))

    def __repr__(self) -> str:
        return f"<ClientProxy module={self.module_name!r}>"


class ConfigProxy:
    """Backward-compatible config view for user modules.

    Old modules frequently write their own keys directly into ``kernel.config``
    (``kernel.config["my_key"] = value``).  This proxy preserves that pattern
    for **reads** - it checks a per-module override dict first, then falls
    through to the global kernel config.

    **Writes** are redirected into the module's own override dict so they never
    pollute the global config.  This keeps both old and new modules working
    without risk of one module corrupting another module's or the kernel's
    configuration keys.
    """

    def __init__(self, config: dict[str, Any] | Any, module_name: str) -> None:
        object.__setattr__(self, "_config", config)
        object.__setattr__(self, "_module_name", module_name)
        object.__setattr__(self, "_overrides", {})

    @property
    def module_name(self) -> str:
        return object.__getattribute__(self, "_module_name")

    def _deny(self, name: str) -> None:
        _raise_insecure(name, self.module_name)

    # Reads: override dict first, then global config

    def _merged(self) -> dict[str, Any]:
        """Return a merged view: overrides shadow global config keys."""
        overrides = object.__getattribute__(self, "_overrides")
        config = object.__getattribute__(self, "_config")
        merged = dict(config)
        merged.update(overrides)
        return merged

    def get(self, key: str, default: Any = None) -> Any:
        overrides = object.__getattribute__(self, "_overrides")
        if key in overrides:
            return overrides[key]
        return object.__getattribute__(self, "_config").get(key, default)

    def __getitem__(self, key: str) -> Any:
        overrides = object.__getattribute__(self, "_overrides")
        if key in overrides:
            return overrides[key]
        return object.__getattribute__(self, "_config")[key]

    def __contains__(self, key: str) -> bool:
        overrides = object.__getattribute__(self, "_overrides")
        return key in overrides or key in object.__getattribute__(self, "_config")

    def __len__(self) -> int:
        return len(self._merged())

    def __iter__(self):
        return iter(self._merged())

    def __bool__(self) -> bool:
        return bool(self._merged())

    def keys(self):
        return self._merged().keys()

    def values(self):
        return self._merged().values()

    def items(self):
        return self._merged().items()

    def __str__(self) -> str:
        return str(self._merged())

    def __repr__(self) -> str:
        return f"<ConfigProxy module={self.module_name!r}>"

    # Writes: module-scoped override dict

    def __setitem__(self, key: str, value: Any) -> None:
        object.__getattribute__(self, "_overrides")[key] = value

    def __delitem__(self, key: str) -> None:
        overrides = object.__getattribute__(self, "_overrides")
        if key in overrides:
            del overrides[key]
        else:
            self._deny(f"__delitem__[{key!r}] (global config key)")

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            object.__getattribute__(self, "_overrides")[name] = value

    def update(self, *args, **kwargs) -> None:
        object.__getattribute__(self, "_overrides").update(*args, **kwargs)

    def pop(self, key: str, *args) -> Any:
        overrides = object.__getattribute__(self, "_overrides")
        if key in overrides:
            return overrides.pop(key, *args)
        self._deny(f"pop:{key} (global config key)")

    def popitem(self):
        overrides = object.__getattribute__(self, "_overrides")
        if overrides:
            return overrides.popitem()
        self._deny("popitem (no module-scoped keys)")

    def clear(self) -> None:
        object.__getattribute__(self, "_overrides").clear()

    def setdefault(self, key: str, *args) -> Any:
        overrides = object.__getattribute__(self, "_overrides")
        config = object.__getattribute__(self, "_config")
        if key in overrides:
            return overrides[key]
        if key in config:
            return config[key]
        return overrides.setdefault(key, *args)

    def __ior__(self, other):
        object.__getattribute__(self, "_overrides").update(other)
        return self


class DatabaseProxy:
    """Safe database facade for user modules.

    Allows read/write operations scoped to the calling module's namespace,
    but blocks raw SQL execution, cross-module key access through dangerous
    methods, and database lifecycle operations.

    All keys are automatically prefixed with ``{module_name}:`` so modules
    cannot read or write outside their own namespace through this proxy.
    """

    _LOCAL_NAMES = frozenset(
        {
            "module_name",
            "get",
            "set",
            "delete",
            "contains",
            "keys",
            "_deny",
            "__class__",
            "__repr__",
            "__dir__",
            "_prefix_key",
        }
    )

    def __init__(self, db_manager: Any, module_name: str) -> None:
        object.__setattr__(self, "_db", db_manager)
        object.__setattr__(self, "_module_name", module_name)

    @property
    def module_name(self) -> str:
        return object.__getattribute__(self, "_module_name")

    def _deny(self, name: str) -> None:
        _raise_insecure(name, self.module_name)

    def _prefix_key(self, key: str) -> str:
        return f"{self.module_name}:{key}"

    async def get(self, key: str, default: Any = None) -> Any:
        """Read a value scoped to this module."""
        db = object.__getattribute__(self, "_db")
        return await db.get(self._prefix_key(key), default)

    async def set(self, key: str, value: Any) -> None:
        """Write a value scoped to this module."""
        db = object.__getattribute__(self, "_db")
        await db.set(self._prefix_key(key), value)

    async def delete(self, key: str) -> bool:
        """Delete a key scoped to this module."""
        db = object.__getattribute__(self, "_db")
        return await db.delete(self._prefix_key(key))

    async def contains(self, key: str) -> bool:
        """Check if a key exists in this module's namespace."""
        db = object.__getattribute__(self, "_db")
        try:
            val = await db.get(self._prefix_key(key), ...)
            return val is not ...
        except Exception:
            return False

    async def keys(self, pattern: str | None = None) -> list[str]:
        """Return all key names in this module's namespace, prefix-stripped."""
        db = object.__getattribute__(self, "_db")
        prefix = f"{self.module_name}:"
        all_keys = await db.keys(prefix + (pattern or "*"))
        prefix_len = len(prefix)
        return [k[prefix_len:] for k in all_keys if k.startswith(prefix)]

    def __getattribute__(self, name: str) -> Any:
        if name in object.__getattribute__(self, "_LOCAL_NAMES"):
            return object.__getattribute__(self, name)
        if name in _DB_DANGEROUS_METHODS or (
            name.startswith("_") and not (name.startswith("__") and name.endswith("__"))
        ):
            _raise_insecure(name, object.__getattribute__(self, "_module_name"))
        return getattr(object.__getattribute__(self, "_db"), name)

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Allow direct Telethon API calls: ``await client(SomeRequest(...))``."""
        return await object.__getattribute__(self, "_client")(*args, **kwargs)

    def __setattr__(self, name: str, value: Any) -> None:
        self._deny(name)

    def __delattr__(self, name: str) -> None:
        self._deny(name)

    def __repr__(self) -> str:
        return f"<DatabaseProxy module={self.module_name!r}>"


def get_module_kernel(kernel: Any, module_name: str, is_system: bool) -> Any:
    """Return a proxied kernel for user modules, raw kernel for system."""
    if is_system:
        return kernel
    return ModuleKernelProxy(kernel, module_name)


class EventProxy:
    """Safe Event wrapper for user modules.

    Transparently passes through all attribute reads, writes, deletes, and
    calls to the underlying Telethon event, **except** for .client and
    ._client which are replaced with a  so that the real
    TelegramClient is never exposed to module code.

    This prevents modules from calling destructive client operations
    (disconnect, logout, session access, add_event_handler,
    etc.) through the event object.
    """

    __slots__ = (
        "_proxied_event",
        "_proxy_client_cache",
        "_proxy_kernel",
        "_proxy_module_name",
    )

    def __init__(self, event: Any, module_name: str, kernel: Any) -> None:
        object.__setattr__(self, "_proxied_event", event)
        object.__setattr__(self, "_proxy_module_name", module_name)
        object.__setattr__(self, "_proxy_kernel", kernel)
        object.__setattr__(self, "_proxy_client_cache", None)

    # -- internal helpers ---------------------------------------------------

    def _get_proxy_client(self) -> ClientProxy:
        cache = object.__getattribute__(self, "_proxy_client_cache")
        if cache is None:
            kernel = object.__getattribute__(self, "_proxy_kernel")
            module_name = object.__getattribute__(self, "_proxy_module_name")
            cache = ClientProxy(kernel.client, module_name)
            object.__setattr__(self, "_proxy_client_cache", cache)
        return cache

    # -- attribute access ---------------------------------------------------

    def __getattribute__(self, name: str) -> Any:
        # Intercept .client and ._client - return a proxied version
        if name in ("client", "_client"):
            return object.__getattribute__(self, "_get_proxy_client")()

        # Internal proxy attributes (stored via __slots__)
        if name in EventProxy.__slots__:
            return object.__getattribute__(self, name)

        # Block __dict__ - prevents event.__dict__["_client"] bypass
        if name == "__dict__":
            _raise_insecure(
                name,
                object.__getattribute__(self, "_proxy_module_name"),
            )

        # Everything else → original event
        return getattr(
            object.__getattribute__(self, "_proxied_event"),
            name,
        )

    def __setattr__(self, name: str, value: Any) -> None:
        if name in EventProxy.__slots__:
            object.__setattr__(self, name, value)
            return
        setattr(object.__getattribute__(self, "_proxied_event"), name, value)

    def __delattr__(self, name: str) -> None:
        if name in EventProxy.__slots__:
            raise AttributeError(f"Cannot delete proxy internal attribute: {name}")
        delattr(object.__getattribute__(self, "_proxied_event"), name)

    # -- forwarding dunder methods -----------------------------------------

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Forward event(...) - Telethon raw API calls."""
        return object.__getattribute__(self, "_proxied_event")(*args, **kwargs)

    def __repr__(self) -> str:
        return repr(object.__getattribute__(self, "_proxied_event"))

    def __dir__(self) -> list[str]:
        return dir(object.__getattribute__(self, "_proxied_event"))


def wrap_event_for_module(event: Any, module_name: str, kernel: Any) -> Any:
    """Wrap a Telethon event in an EventProxy if it looks like an event.

    Returns an EventProxy when the object has a client attribute
    (i.e. it is a Telethon event), otherwise returns the object unchanged.
    This keeps calls that pass non-event objects (pipeline contexts, mock
    events in tests) working without changes.
    """
    # Quick heuristic - Telethon events always have _client / client
    if hasattr(event, "_client") or hasattr(event, "client"):
        return EventProxy(event, module_name, kernel)
    return event


def get_module_register(kernel: Any, module_name: str, is_system: bool) -> Any:
    """Return a proxied register for user modules, raw for system."""
    if is_system:
        return kernel.register
    return ModuleRegisterProxy(kernel.register, module_name)


def get_module_client(kernel: Any, module_name: str, is_system: bool) -> Any:
    """Return a proxied client for user modules, raw for system."""
    if is_system:
        return kernel.client
    return ClientProxy(kernel.client, module_name)


def get_module_config(kernel: Any, module_name: str, is_system: bool) -> Any:
    """Return a read-only config proxy for user modules, raw for system."""
    if is_system:
        return kernel.config
    return ConfigProxy(kernel.config, module_name)


def get_module_db(kernel: Any, module_name: str, is_system: bool) -> Any:
    """Return a scoped database proxy for user modules, raw for system."""
    if is_system:
        return kernel.db_manager
    return DatabaseProxy(kernel.db_manager, module_name)
