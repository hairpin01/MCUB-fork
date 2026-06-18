#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


def make_kernel():
    kernel = SimpleNamespace()
    kernel.logger = MagicMock()
    kernel.client = MagicMock()
    kernel.client.disconnect = MagicMock()
    kernel.client.logout = MagicMock()
    kernel.client.send_message = MagicMock()
    kernel.client.get_entity = MagicMock()
    kernel.bot_client = object()
    kernel.db_manager = MagicMock()
    kernel.db_manager.get = AsyncMock()
    kernel.db_manager.set = AsyncMock()
    kernel.db_manager.delete = AsyncMock()
    kernel.db_manager.keys = AsyncMock(return_value=[])
    kernel.cache = object()
    kernel.custom_prefix = "."
    kernel.config = {"language": "en"}
    kernel.register = SimpleNamespace(kernel=kernel)
    kernel.loaded_modules = {}
    kernel.system_modules = {}
    kernel.command_handlers = {}
    kernel.bot_command_handlers = {}
    kernel.command_owners = {}
    kernel.bot_command_owners = {}
    kernel.aliases = {}
    kernel._class_module_instances = {}
    kernel._hikka_compat_allmodules_proxy = None
    kernel.current_loading_module = "test_module"
    kernel.current_loading_module_type = "user"
    return kernel


def make_spec(name: str = "test_module"):
    return importlib.util.spec_from_loader(name, loader=None)


class TestModuleKernelProxy:
    """Test that ModuleKernelProxy protects core registries."""

    def test_user_module_gets_kernel_proxy_and_client_proxy(self):
        from core.lib.loader.kernel_proxy import (
            ClientProxy,
            ModuleKernelProxy,
        )
        from core.lib.loader.loader import ModuleLoader
        from core.lib.utils.exceptions import CallInsecure

        kernel = make_kernel()
        loader = ModuleLoader(kernel)

        module = loader._build_module(
            make_spec(), __file__, "test_module", is_system=False
        )

        assert isinstance(module.kernel, ModuleKernelProxy)
        assert isinstance(module.client, ClientProxy)
        assert module.custom_prefix == "."
        assert module.kernel.db_manager is kernel.db_manager
        assert module.kernel.cache is kernel.cache

        for name in (
            "loaded_modules",
            "command_handlers",
            "command_owners",
            "_class_module_instances",
            "__dict__",
        ):
            with pytest.raises(CallInsecure):
                getattr(module.kernel, name)

        with pytest.raises(CallInsecure):
            module.kernel.loaded_modules = {}
        with pytest.raises(CallInsecure):
            del module.kernel.command_handlers
        with pytest.raises(CallInsecure):
            _ = module.kernel.register.kernel

    def test_proxy_client_blocks_dangerous_methods(self):
        from core.lib.loader.kernel_proxy import ClientProxy
        from core.lib.utils.exceptions import CallInsecure

        client = MagicMock()
        proxy = ClientProxy(client, "test_module")

        # Safe methods should work
        # send_message is wrapped to inject parse_mode='html'
        assert callable(proxy.send_message)
        assert proxy.send_message is not client.send_message
        assert proxy.get_entity is client.get_entity

        # Dangerous methods should raise
        for name in (
            "disconnect",
            "logout",
            "session",
            "on",
            "add_event_handler",
            "phone_code_hash",
            "sign_out",
        ):
            with pytest.raises(CallInsecure):
                getattr(proxy, name)

        # Setting attributes should be blocked
        with pytest.raises(CallInsecure):
            proxy.send_message = lambda x: None

        with pytest.raises(CallInsecure):
            proxy.session = object()

        with pytest.raises(CallInsecure):
            proxy._client = object()

        proxy._my_attribute = "my_var"
        assert proxy._my_attribute == "my_var"
        assert "_my_attribute" not in vars(client)

        # Deleting attributes should be blocked
        with pytest.raises(CallInsecure):
            del proxy.send_message

    def test_proxy_loaded_module_helpers_are_read_only_and_can_filter_full_loads(self):
        from core.lib.loader.kernel_proxy import ModuleKernelProxy

        kernel = make_kernel()
        dep_instance = SimpleNamespace(name="DepMod")
        dep_module = SimpleNamespace(
            __name__="dep_module", _class_instance=dep_instance
        )
        kernel.loaded_modules["DepMod"] = dep_module
        kernel._class_module_instances["OnlyConstructed"] = SimpleNamespace(
            name="OnlyConstructed"
        )

        proxy = ModuleKernelProxy(kernel, "caller")

        assert proxy.lookup_module("DepMod") is dep_instance
        assert proxy.lookup_module("DepMod", all_loaded=True) is dep_instance
        assert (
            proxy.get_loaded_module("OnlyConstructed")
            is kernel._class_module_instances["OnlyConstructed"]
        )
        assert proxy.get_loaded_module("OnlyConstructed", all_loaded=True) is None

        view = proxy.loaded_modules_view
        from types import MappingProxyType

        assert isinstance(view, MappingProxyType)
        assert "DepMod" in view

        assert "DepMod" in proxy.iter_loaded_module_names()

    def test_proxy_modules_view_is_mappingproxy(self):
        from types import MappingProxyType

        from core.lib.loader.kernel_proxy import ModuleKernelProxy

        kernel = make_kernel()
        kernel.loaded_modules["A"] = object()
        kernel.system_modules["B"] = object()

        proxy = ModuleKernelProxy(kernel, "checker")
        assert isinstance(proxy.loaded_modules_view, MappingProxyType)
        assert isinstance(proxy.system_modules_view, MappingProxyType)
        assert "A" in proxy.loaded_modules_view
        assert "B" in proxy.system_modules_view

    def test_proxy_dir_hides_protected_names(self):
        from core.lib.loader.kernel_proxy import ModuleKernelProxy

        kernel = make_kernel()
        proxy = ModuleKernelProxy(kernel, "dir_check")
        names = dir(proxy)
        for protected in (
            "loaded_modules",
            "command_handlers",
            "command_owners",
            "_class_module_instances",
        ):
            assert protected not in names
        assert "module_name" in names
        assert "register" in names
        assert "client" in names
        assert "lookup_module" in names
        assert "loaded_modules_view" in names


class TestClientProxy:
    """Test ClientProxy blocks dangerous operations."""

    def test_safe_attributes_pass_through(self):
        from core.lib.loader.kernel_proxy import ClientProxy

        client = MagicMock()
        proxy = ClientProxy(client, "mod")

        # send_message is wrapped to inject parse_mode='html' for Hikka compat
        assert callable(proxy.send_message)
        assert proxy.send_message is not client.send_message
        assert proxy.get_entity is client.get_entity
        assert proxy.get_messages is client.get_messages
        assert proxy.inline_query is client.inline_query
        assert proxy.is_connected is client.is_connected

    def test_dangerous_attributes_raise(self):
        from core.lib.loader.kernel_proxy import ClientProxy
        from core.lib.utils.exceptions import CallInsecure

        client = MagicMock()
        proxy = ClientProxy(client, "mod")

        dangerous = [
            "disconnect",
            "logout",
            "sign_out",
            "session",
            "on",
            "add_event_handler",
            "remove_event_handler",
            "list_event_handlers",
            "phone_code_hash",
            "authorization_key",
        ]
        for name in dangerous:
            with pytest.raises(CallInsecure, match=name):
                getattr(proxy, name)

    def test_dir_excludes_dangerous(self):
        from core.lib.loader.kernel_proxy import ClientProxy

        # Use a real class with Telegram-client-like methods
        class FakeClient:
            def send_message(self):
                pass

            def get_entity(self):
                pass

            def get_messages(self):
                pass

            def disconnect(self):
                pass

            def logout(self):
                pass

        proxy = ClientProxy(FakeClient(), "mod")
        names = dir(proxy)

        assert "send_message" in names
        assert "get_entity" in names
        assert "get_messages" in names
        assert "disconnect" not in names
        assert "logout" not in names
        assert "session" not in names

    def test_repr(self):
        from core.lib.loader.kernel_proxy import ClientProxy

        proxy = ClientProxy(MagicMock(), "my_module")
        assert "my_module" in repr(proxy)


class TestConfigProxy:
    """Test ConfigProxy provides read-only config view."""

    def test_read_operations_work(self):
        from core.lib.loader.kernel_proxy import ConfigProxy

        config = {"key1": "val1", "key2": 42, "nested": {"a": 1}}
        proxy = ConfigProxy(config, "mod")

        assert proxy["key1"] == "val1"
        assert proxy.get("key2") == 42
        assert proxy.get("missing", "default") == "default"
        assert "key1" in proxy
        assert len(proxy) == 3
        assert list(proxy.keys()) == ["key1", "key2", "nested"]
        assert list(proxy.values()) == ["val1", 42, {"a": 1}]
        assert proxy

    def test_write_operations_go_to_module_scope(self):
        """ConfigProxy writes go to per-module overrides, not global config."""
        from core.lib.loader.kernel_proxy import ConfigProxy

        proxy = ConfigProxy({"a": 1, "existing": "global"}, "mod")

        # Write to module-scoped override
        proxy["a"] = 2
        assert proxy["a"] == 2  # reads from override

        # Global config unchanged
        assert proxy._config["a"] == 1

        # Existing global key still accessible via get
        assert proxy.get("existing") == "global"

        # Module override shadows global
        proxy["existing"] = "module_value"
        assert proxy["existing"] == "module_value"
        assert proxy._config["existing"] == "global"

        # update works
        proxy.update({"b": 2, "c": 3})
        assert proxy["b"] == 2
        assert proxy["c"] == 3

        # pop works for module-scoped keys
        val = proxy.pop("b")
        assert val == 2
        assert "b" not in proxy

        # Deleting a module-scoped key works
        del proxy["c"]
        assert "c" not in proxy

        # clear works (module-scoped overrides only)
        proxy.clear()
        assert "b" not in proxy  # module key gone
        assert proxy.get("a") == 1  # global key still readable
        assert proxy["a"] == 1  # reads from global config

        # Global key still readable after module override clear
        assert proxy["existing"] == "global"

    def test_pop_non_module_key_raises(self):
        """Popping a key that only exists in global config raises."""
        from core.lib.loader.kernel_proxy import ConfigProxy
        from core.lib.utils.exceptions import CallInsecure

        proxy = ConfigProxy({"only_global": 42}, "mod")
        with pytest.raises(CallInsecure):
            proxy.pop("only_global")

    def test_delete_non_module_key_raises(self):
        """Deleting a key that only exists in global config raises."""
        from core.lib.loader.kernel_proxy import ConfigProxy
        from core.lib.utils.exceptions import CallInsecure

        proxy = ConfigProxy({"only_global": 42}, "mod")
        with pytest.raises(CallInsecure):
            del proxy["only_global"]

    def test_empty_config_is_falsy(self):
        from core.lib.loader.kernel_proxy import ConfigProxy

        assert not ConfigProxy({}, "mod")
        assert ConfigProxy({"a": 1}, "mod")

    def test_repr(self):
        from core.lib.loader.kernel_proxy import ConfigProxy

        proxy = ConfigProxy({}, "my_mod")
        assert "my_mod" in repr(proxy)


class TestDatabaseProxy:
    """Test DatabaseProxy scopes operations per module."""

    @pytest.mark.asyncio
    async def test_get_prefixed(self):
        from core.lib.loader.kernel_proxy import DatabaseProxy

        db = MagicMock()
        db.get = AsyncMock(return_value="stored")
        proxy = DatabaseProxy(db, "my_mod")

        result = await proxy.get("some_key")
        db.get.assert_called_once_with("my_mod:some_key", None)
        assert result == "stored"

    @pytest.mark.asyncio
    async def test_set_prefixed(self):
        from core.lib.loader.kernel_proxy import DatabaseProxy

        db = MagicMock()
        db.set = AsyncMock()
        proxy = DatabaseProxy(db, "my_mod")

        await proxy.set("some_key", {"data": 123})
        db.set.assert_called_once_with("my_mod:some_key", {"data": 123})

    @pytest.mark.asyncio
    async def test_delete_prefixed(self):
        from core.lib.loader.kernel_proxy import DatabaseProxy

        db = MagicMock()
        db.delete = AsyncMock(return_value=True)
        proxy = DatabaseProxy(db, "my_mod")

        result = await proxy.delete("some_key")
        db.delete.assert_called_once_with("my_mod:some_key")
        assert result is True

    @pytest.mark.asyncio
    async def test_keys_strips_prefix(self):
        from core.lib.loader.kernel_proxy import DatabaseProxy

        db = MagicMock()
        db.keys = AsyncMock(return_value=["my_mod:a", "my_mod:b", "other:c"])
        proxy = DatabaseProxy(db, "my_mod")

        keys = await proxy.keys()
        assert keys == ["a", "b"]

    def test_dangerous_methods_raise(self):
        from core.lib.loader.kernel_proxy import DatabaseProxy
        from core.lib.utils.exceptions import CallInsecure

        proxy = DatabaseProxy(MagicMock(), "mod")
        for name in ("close", "execute", "cursor", "connection", "_conn"):
            with pytest.raises(CallInsecure):
                getattr(proxy, name)

    def test_repr(self):
        from core.lib.loader.kernel_proxy import DatabaseProxy

        proxy = DatabaseProxy(MagicMock(), "my_db_mod")
        assert "my_db_mod" in repr(proxy)


class TestFactoryHelpers:
    """Test get_module_* helpers return proxies for user modules."""

    def test_get_module_kernel_proxies_user(self):
        from core.lib.loader.kernel_proxy import (
            ModuleKernelProxy,
            get_module_kernel,
        )

        kernel = make_kernel()
        proxy = get_module_kernel(kernel, "test", is_system=False)
        assert isinstance(proxy, ModuleKernelProxy)

    def test_get_module_kernel_returns_raw_for_system(self):
        from core.lib.loader.kernel_proxy import get_module_kernel

        kernel = make_kernel()
        result = get_module_kernel(kernel, "test", is_system=True)
        assert result is kernel

    def test_get_module_client_proxies_user(self):
        from core.lib.loader.kernel_proxy import (
            ClientProxy,
            get_module_client,
        )

        kernel = make_kernel()
        proxy = get_module_client(kernel, "test", is_system=False)
        assert isinstance(proxy, ClientProxy)

    def test_get_module_client_returns_raw_for_system(self):
        from core.lib.loader.kernel_proxy import get_module_client

        kernel = make_kernel()
        result = get_module_client(kernel, "test", is_system=True)
        assert result is kernel.client

    def test_get_module_register_proxies_user(self):
        from core.lib.loader.kernel_proxy import (
            ModuleRegisterProxy,
            get_module_register,
        )

        kernel = make_kernel()
        proxy = get_module_register(kernel, "test", is_system=False)
        assert isinstance(proxy, ModuleRegisterProxy)

    def test_get_module_register_returns_raw_for_system(self):
        from core.lib.loader.kernel_proxy import get_module_register

        kernel = make_kernel()
        result = get_module_register(kernel, "test", is_system=True)
        assert result is kernel.register

    def test_get_module_config_proxies_user(self):
        from core.lib.loader.kernel_proxy import (
            ConfigProxy,
            get_module_config,
        )

        kernel = make_kernel()
        proxy = get_module_config(kernel, "test", is_system=False)
        assert isinstance(proxy, ConfigProxy)

    def test_get_module_config_returns_raw_for_system(self):
        from core.lib.loader.kernel_proxy import get_module_config

        kernel = make_kernel()
        result = get_module_config(kernel, "test", is_system=True)
        assert result is kernel.config

    def test_get_module_db_proxies_user(self):
        from core.lib.loader.kernel_proxy import (
            DatabaseProxy,
            get_module_db,
        )

        kernel = make_kernel()
        proxy = get_module_db(kernel, "test", is_system=False)
        assert isinstance(proxy, DatabaseProxy)

    def test_get_module_db_returns_raw_for_system(self):
        from core.lib.loader.kernel_proxy import get_module_db

        kernel = make_kernel()
        result = get_module_db(kernel, "test", is_system=True)
        assert result is kernel.db_manager


class TestUserLoadsViaProxiedKernel:
    """Test that user_loader_mixin assigns proxied objects."""

    def test_inject_kernel_path_gets_proxy(self):
        """The inject_kernel=True path must get proxied kernel, not raw k."""
        from core.lib.loader.kernel_proxy import (
            ClientProxy,
            ModuleKernelProxy,
            get_module_client,
            get_module_kernel,
        )

        k = make_kernel()
        proxy_kernel = get_module_kernel(k, "test_mod", is_system=False)
        proxy_client = get_module_client(k, "test_mod", is_system=False)

        assert isinstance(proxy_kernel, ModuleKernelProxy)
        assert isinstance(proxy_client, ClientProxy)

        # Verify the proxy chain
        assert isinstance(proxy_kernel.client, ClientProxy)
        assert proxy_kernel.client is not proxy_client  # lazy-init creates new instance
        assert proxy_kernel.client.module_name == proxy_client.module_name
