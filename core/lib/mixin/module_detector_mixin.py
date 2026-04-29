# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING, Any

from ..utils.exceptions import CommandConflictError
from ..loader.module_base import ModuleBase

if TYPE_CHECKING:
    from kernel import Kernel


class ModuleDetectorMixin:
    """Mixin for detecting module types and registering them."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def _build_module(self, spec, file_path: str, module_name: str):
        """Create a module object preloaded with kernel context."""
        import builtins
        import importlib
        import sys

        self.k.logger.debug(
            f"[Loader] _build_module name={module_name} path={file_path}"
        )
        module = importlib.util.module_from_spec(spec)
        module.__file__ = file_path
        module.__name__ = module_name
        module.__builtins__ = builtins
        module.sys = sys
        module.kernel = self.k
        module.client = self.k.client
        module.custom_prefix = self.k.custom_prefix
        self.k.logger.debug(f"[Loader] _build_module done name={module_name}")
        return module

    def _iter_register_methods(self, register) -> list:
        """Return callable register decorators stored on ``register.__dict__``."""
        methods = []
        if not hasattr(register, "__dict__"):
            return methods
        for attr_name in dir(register):
            attr = getattr(register, attr_name)
            if callable(attr) and hasattr(attr, "_is_register_method"):
                methods.append(attr)
        return methods

    def _get_register_param_name(self, register) -> str | None:
        """Get the parameter name expected by the register function."""
        if not callable(register):
            return None
        try:
            sig = inspect.signature(register)
            params = list(sig.parameters.values())
            if params:
                return params[0].name
        except (ValueError, TypeError):
            pass
        return None

    def _find_module_base_class(self, module) -> type | None:
        """Return the first class in *module* that inherits from ModuleBase, or None."""
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, ModuleBase) and obj is not ModuleBase:
                return obj
        return None

    async def detect_module_type(self, module) -> str:
        """Detect the registration pattern used by a module.

        Returns:
            'class' | 'method' | 'new' | 'old' | 'none'
        """
        self.k.logger.debug(
            f"[Loader] detect_module_type start module={getattr(module, '__name__', 'unknown')}"
        )

        if self._find_module_base_class(module) is not None:
            self.k.logger.debug("[Loader] detect_module_type result=class")
            return "class"

        if not hasattr(module, "register"):
            self.k.logger.debug(
                "[Loader] detect_module_type result=none (no register attr)"
            )
            return "none"

        if self._iter_register_methods(module.register):
            self.k.logger.debug("[Loader] detect_module_type result=method")
            return "method"

        param_name = self._get_register_param_name(module.register)
        if param_name == "kernel":
            self.k.logger.debug("[Loader] detect_module_type result=new")
            return "new"
        if param_name is not None:
            self.k.logger.debug("[Loader] detect_module_type result=old")
            return "old"

        self.k.logger.debug("[Loader] detect_module_type result=none")
        return "none"

    async def register_module(self, module, module_type: str, module_name: str) -> bool:
        """Call the module's register function according to its type.

        Raises:
            CommandConflictError: Propagated from command registration.
        """
        k = self.k
        try:
            k.logger.debug(
                "[loader.register_module] module=%r type=%r register=%r",
                module_name,
                module_type,
                getattr(module, "register", None),
            )

            if module_type == "class":
                cls = self._find_module_base_class(module)
                if cls is None:
                    return False

                module_class_name = getattr(cls, "name", module_name)

                saved_loading_module = k.current_loading_module
                k.current_loading_module = module_class_name

                if not hasattr(k, "_class_module_instances"):
                    k._class_module_instances = {}

                old_instance = None
                old_module_file = None
                for fname, inst in list(k._class_module_instances.items()):
                    if getattr(type(inst), "name", None) == module_class_name:
                        old_instance = inst
                        old_module_file = fname
                        break

                if old_instance is not None:
                    k.logger.info(
                        f"[loader] Updating class module '{module_class_name}' "
                        f"(was: {old_module_file}, now: {module_name})"
                    )

                    old_module_obj = k.loaded_modules.get(old_module_file)
                    if old_module_obj is None:
                        for fname, mobj in list(k.loaded_modules.items()):
                            if (
                                getattr(
                                    type(getattr(mobj, "_class_instance", None)),
                                    "name",
                                    None,
                                )
                                == module_class_name
                            ):
                                old_module_obj = mobj
                                old_module_file = fname
                                break

                    await self.unregister_module_commands(old_module_file)
                    if old_module_file in k._class_module_instances:
                        del k._class_module_instances[old_module_file]

                instance = cls(k, k.client, k.register)
                k.logger.debug(
                    "[loader.register_module] class instance created module=%r class=%r",
                    module_name,
                    cls.__name__,
                )
                if not hasattr(k, "_class_module_instances"):
                    k._class_module_instances = {}
                k._class_module_instances[module_name] = instance
                module._class_instance = instance

                k.current_loading_module = saved_loading_module

                return True

            if module_type == "method":
                methods = self._iter_register_methods(getattr(module, "register", None))
                if not methods:
                    return False
                for attr in methods:
                    await self._call_register(attr, k)

            elif module_type == "new":
                if not (hasattr(module, "register") and callable(module.register)):
                    return False
                await self._call_register(module.register, k)

            elif module_type == "old":
                if not (hasattr(module, "register") and callable(module.register)):
                    return False
                await self._call_register(module.register, k.client)

            else:
                if not (hasattr(module, "register") and callable(module.register)):
                    return False
                try:
                    await self._call_register(module.register, k)
                except Exception:
                    try:
                        await self._call_register(module.register, k.client)
                    except Exception:
                        return False

            return True

        except CommandConflictError:
            raise
        except Exception as e:
            k.logger.error(f"Registration failed for {module_name}: {e}")
            raise

    async def _call_register(self, fn, arg) -> None:
        """Invoke sync or async registration callbacks uniformly."""
        if inspect.iscoroutinefunction(fn):
            await fn(arg)
        else:
            fn(arg)

    async def run_post_load(
        self,
        module: Any,
        module_name: str,
        is_install: bool = False,
        is_reload: bool = False,
    ) -> None:
        """Run autostart loops, on_load, and on_install callbacks after registration.

        Args:
            module: The loaded module object.
            module_name: Module name for logging and DB keys.
            is_install: Whether this is the first time the module is installed.
        """
        k = self.k
        reg = getattr(module, "register", None)
        k.logger.debug(
            "[loader.post_load] module=%r install=%s loops=%d watchers=%d events=%d",
            module_name,
            is_install,
            len(getattr(reg, "__loops__", [])),
            len(getattr(reg, "__watchers__", [])),
            len(getattr(reg, "__event_handlers__", [])),
        )

        instance = getattr(module, "_class_instance", None)
        if instance is not None:
            instance._loops.clear()
            for loop in getattr(reg, "__loops__", []):
                loop._kernel = k
                instance._loops.append(loop)
                if loop.autostart:
                    try:
                        loop.start()
                        k.logger.debug(
                            f"Autostarted loop '{loop.func.__name__}' ({module_name})"
                        )
                    except Exception as e:
                        k.logger.error(f"Error autostarting loop in {module_name}: {e}")

            try:
                if inspect.iscoroutinefunction(instance.on_load):
                    await instance.on_load()
                else:
                    result = instance.on_load()
                    if asyncio.iscoroutine(result):
                        await result
                instance._loaded = True
                k.logger.debug(f"on_load called for class module: {module_name}")
            except Exception as e:
                k.logger.error(f"on_load error in {module_name}: {e}")

            if is_reload:
                try:
                    if inspect.iscoroutinefunction(instance.on_reload):
                        await instance.on_reload()
                    else:
                        result = instance.on_reload()
                        if asyncio.iscoroutine(result):
                            await result
                    k.logger.debug(f"on_reload called for class module: {module_name}")
                except Exception as e:
                    k.logger.error(f"on_reload error in {module_name}: {e}")

            if is_install:
                try:
                    if inspect.iscoroutinefunction(instance.on_install):
                        await instance.on_install()
                    else:
                        result = instance.on_install()
                        if asyncio.iscoroutine(result):
                            await result
                    k.logger.debug(f"on_install called for class module: {module_name}")
                except Exception as e:
                    k.logger.error(f"on_install error in {module_name}: {e}")

            return

        for loop in getattr(reg, "__loops__", []):
            loop._kernel = k
            if loop.autostart:
                try:
                    loop.start()
                    k.logger.debug(
                        f"Autostarted loop '{loop.func.__name__}' ({module_name})"
                    )
                except Exception as e:
                    k.logger.error(f"Error autostarting loop in {module_name}: {e}")

        on_load = getattr(reg, "__on_load__", None)
        if on_load is not None:
            try:
                result = on_load(k)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                k.logger.error(f"on_load error in {module_name}: {e}")

        on_install = getattr(reg, "__on_install__", None)
        if on_install is not None and is_install:
            flag = f"__installed__{module_name}"
            already = await k.db_get("mcub_module_flags", flag)
            if not already:
                try:
                    result = on_install(k)
                    if asyncio.iscoroutine(result):
                        await result
                    await k.db_set("mcub_module_flags", flag, "1")
                    k.logger.debug(f"on_install ran for {module_name}")
                except Exception as e:
                    k.logger.error(f"on_install error in {module_name}: {e}")
