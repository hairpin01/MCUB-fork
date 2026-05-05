# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import os
import sys
from typing import TYPE_CHECKING, Any

from ..utils.exceptions import CommandConflictError

if TYPE_CHECKING:
    from kernel import Kernel


class UserLoaderMixin:
    """Mixin for loading user modules."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    async def load_user_modules(self) -> None:
        """Load all .py files from the user modules directory."""
        import os

        k = self.k

        try:
            from core.lib.loader.hikka_compat import is_hikka_module, load_hikka_module

            _hikka_compat = True
        except ImportError:
            _hikka_compat = False

        files = os.listdir(k.MODULES_LOADED_DIR)
        if "log_bot.py" in files:
            files.remove("log_bot.py")
            files.insert(0, "log_bot.py")

        for file_name in files:
            # Check for package directories (modules with local imports)
            module_path = os.path.join(k.MODULES_LOADED_DIR, file_name)
            if os.path.isdir(module_path):
                init_file = os.path.join(module_path, "__init__.py")
                if os.path.exists(init_file):
                    # Check if it's an archive-installed package
                    source_info = k._module_sources.get(file_name, {})
                    if (
                        source_info.get("type") == "archive"
                        and source_info.get("pack_type") == "single"
                    ):
                        try:
                            await self._load_package_module(file_name, init_file, k)
                        except Exception as e:
                            k.logger.error(f"Error loading package {file_name}: {e}")
                            k.error_load_modules += 1
                    continue

            if not file_name.endswith(".py"):
                continue
            module_name = file_name[:-3]
            file_path = os.path.join(k.MODULES_LOADED_DIR, file_name)
            try:
                with open(file_path, encoding="utf-8") as f:
                    code = f.read()

                if _hikka_compat and is_hikka_module(code):
                    k.set_loading_module(module_name, "user")
                    ok, err, _ = await load_hikka_module(
                        k, os.path.abspath(file_path), module_name
                    )
                    if not ok:
                        k.logger.error(f"Error loading module {file_name}: {err}")
                        k.error_load_modules += 1
                    continue

                await self.pre_install_requirements(code, module_name)

                inject_kernel = "def register(kernel):" in code

                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                if inject_kernel:
                    module.kernel = k
                    module.client = k.client
                    module.custom_prefix = k.custom_prefix
                sys.modules[module_name] = module

                k.set_loading_module(module_name, "user")
                module = await self.exec_with_auto_deps(
                    spec, module, file_path, module_name, code
                )

                if not hasattr(module, "register"):
                    cls = self._find_module_base_class(module)
                    if cls is not None:
                        if not inject_kernel:
                            module.kernel = k
                            module.client = k.client
                            module.custom_prefix = k.custom_prefix
                        instance = cls(k, k.client, k.register)
                        if not hasattr(k, "_class_module_instances"):
                            k._class_module_instances = {}
                        k._class_module_instances[module_name] = instance
                        module._class_instance = instance

                        class_display_name = getattr(cls, "name", None)
                        if (
                            class_display_name
                            and class_display_name != "Unnamed"
                            and class_display_name != module_name
                        ):
                            import os

                            old_path = file_path
                            new_path = os.path.join(
                                k.MODULES_LOADED_DIR, f"{class_display_name}.py"
                            )

                            if not os.path.exists(new_path):
                                try:
                                    os.rename(old_path, new_path)
                                    k.logger.info(
                                        f"Renamed module file: {module_name} -> {class_display_name}"
                                    )
                                    file_path = new_path
                                except Exception as e:
                                    k.logger.warning(
                                        f"Failed to rename module file: {e}"
                                    )

                            module_name = class_display_name

                        k.loaded_modules[module_name] = module
                        k.logger.info(
                            f"Module loaded [user class-style]: {module_name}"
                        )
                        await self.run_post_load(module, module_name, is_install=False)
                        continue
                    continue

                if inspect.iscoroutinefunction(module.register):
                    await module.register(k)
                else:
                    module.register(k)

                k.loaded_modules[module_name] = module
                label = "user" if inject_kernel else "user (legacy style)"
                k.logger.info(f"Module loaded [{label}]: {module_name}")
                await self.run_post_load(module, module_name, is_install=False)

            except CommandConflictError as e:
                k.logger.error(f"Command conflict loading {file_name}: {e}")
                if hasattr(k, "_log") and k._log:
                    try:
                        await asyncio.wait_for(
                            k._log.log_error_from_exc(
                                f"load_module_conflict:{file_name}"
                            ),
                            timeout=5.0,
                        )
                    except TimeoutError:
                        k.logger.warning("log_error_from_exc timed out")
                    except Exception as log_err:
                        k.logger.error(f"log_error_from_exc failed: {log_err}")
                k.error_load_modules += 1
            except Exception as e:
                k.logger.error(f"Error loading module {file_name}: {e}")
                if hasattr(k, "_log") and k._log:
                    try:
                        await asyncio.wait_for(
                            k._log.log_error_from_exc(f"load_module:{file_name}"),
                            timeout=5.0,
                        )
                    except TimeoutError:
                        k.logger.warning("log_error_from_exc timed out")
                    except Exception as log_err:
                        k.logger.error(f"log_error_from_exc failed: {log_err}")
                k.error_load_modules += 1
            finally:
                k.clear_loading_module()

    async def _load_package_module(
        self, module_name: str, init_file: str, k: Any
    ) -> None:
        """Load a module that was installed as a package (from archive with local imports)."""
        import sys

        # Add parent directory to sys.path
        parent_dir = os.path.dirname(k.MODULES_LOADED_DIR.rstrip("/"))
        for p in [k.MODULES_LOADED_DIR, parent_dir]:
            if p and p not in sys.path:
                sys.path.insert(0, p)

        # Ensure parent package is importable
        if module_name in sys.modules:
            del sys.modules[module_name]

        # Remove any submodule cached entries
        for mod in list(sys.modules.keys()):
            if mod.startswith(f"{module_name}."):
                del sys.modules[mod]

        spec = importlib.util.spec_from_file_location(module_name, init_file)
        if spec is None:
            raise Exception(f"Cannot create spec for {module_name}")

        module = importlib.util.module_from_spec(spec)
        module.kernel = k
        module.client = k.client
        module.custom_prefix = k.custom_prefix
        module.__file__ = init_file
        module.__name__ = module_name
        sys.modules[module_name] = module

        k.set_loading_module(module_name, "user")

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise Exception(f"Failed to execute module: {e}")

        if not hasattr(module, "register"):
            raise Exception(f"Module {module_name} has no register function")

        if inspect.iscoroutinefunction(module.register):
            await module.register(k)
        else:
            module.register(k)

        k.loaded_modules[module_name] = module
        k.logger.info(f"Module loaded [user (archive package)]: {module_name}")

        await self.run_post_load(module, module_name, is_install=False)
        k.clear_loading_module()
