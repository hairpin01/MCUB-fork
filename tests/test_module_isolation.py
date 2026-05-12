#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def make_kernel():
    kernel = SimpleNamespace()
    kernel.logger = MagicMock()
    kernel.client = object()
    kernel.bot_client = object()
    kernel.db_manager = object()
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


def test_user_module_gets_kernel_proxy_and_protected_access_raises():
    from core.lib.loader.kernel_proxy import ModuleKernelProxy
    from core.lib.loader.loader import ModuleLoader
    from core.lib.utils.exceptions import CallInsecure

    kernel = make_kernel()
    loader = ModuleLoader(kernel)

    module = loader._build_module(make_spec(), __file__, "test_module", is_system=False)

    assert isinstance(module.kernel, ModuleKernelProxy)
    assert module.client is kernel.client
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


def test_proxy_loaded_module_helpers_are_read_only_and_can_filter_full_loads():
    from core.lib.loader.kernel_proxy import ModuleKernelProxy

    kernel = make_kernel()
    dep_instance = SimpleNamespace(name="DepMod")
    dep_module = SimpleNamespace(__name__="dep_module", _class_instance=dep_instance)
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
    assert proxy.loaded_module_names == ("DepMod",)

    view = proxy.loaded_modules_view
    assert view["DepMod"] is dep_module
    with pytest.raises(TypeError):
        view["x"] = object()


def test_system_module_gets_real_kernel():
    from core.lib.loader.loader import ModuleLoader

    kernel = make_kernel()
    loader = ModuleLoader(kernel)

    module = loader._build_module(
        make_spec(), __file__, "system_module", is_system=True
    )

    assert module.kernel is kernel


@pytest.mark.asyncio
async def test_user_class_module_gets_kernel_and_register_proxies():
    from core.lib.loader.kernel_proxy import ModuleKernelProxy, ModuleRegisterProxy
    from core.lib.loader.loader import ModuleLoader
    from core.lib.loader.module_base import ModuleBase

    class UserClassModule(ModuleBase):
        name = "UserClassModule"
        strings = {"en": {"ok": "ok"}}

    module = SimpleNamespace(UserClassModule=UserClassModule)
    kernel = make_kernel()
    loader = ModuleLoader(kernel)

    assert await loader.register_module(
        module, "class", "user_class_module", is_system=False
    )

    instance = kernel._class_module_instances["UserClassModule"]
    assert isinstance(instance.kernel, ModuleKernelProxy)
    assert isinstance(instance._register, ModuleRegisterProxy)
    assert instance.kernel.module_name == "UserClassModule"
