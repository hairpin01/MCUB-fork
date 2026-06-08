# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import os
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from ..utils.exceptions import CommandConflictError

if TYPE_CHECKING:
    pass

_LOAD_CONCURRENCY = 16


class SystemLoaderMixin:
    """Mixin for loading system modules."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    async def load_system_modules(self) -> None:
        """Load all .py files from the system modules directory.

        Two-phase: pre-install all deps in parallel, then load modules
        concurrently (up to _LOAD_CONCURRENCY at a time).

        Phase 1 reads every file once and caches the content so that
        Phase 2 (``_load_single_system_module``) does not re-read it.
        """
        k = self.k

        if getattr(k, "_lock_loader_system", False):
            raise RuntimeError("The method can only be called once!") from None

        files = [
            f
            for f in os.listdir(k.MODULES_DIR)
            if f.endswith(".py") and f != "__init__.py"
        ]

        # Phase 1: batch pre-install all deps + cache file contents
        modules_code: list[tuple[str, str]] = []
        code_cache: dict[str, str] = {}  # filename -> code, avoids re-read
        for file_name in files:
            file_path = os.path.join(k.MODULES_DIR, file_name)
            try:
                with open(file_path, encoding="utf-8") as f:
                    code = f.read()
                modules_code.append((file_name[:-3], code))
                code_cache[file_name] = code
            except OSError:
                pass

        batch_install = getattr(self, "pre_install_requirements_batch", None)
        if callable(batch_install):
            await batch_install(modules_code)

        # Phase 2: load concurrently (pass code_cache so no re-read)
        semaphore = asyncio.Semaphore(_LOAD_CONCURRENCY)

        async def _load_one(file_name: str) -> None:
            async with semaphore:
                cached_code = code_cache.get(file_name)
                await self._load_single_system_module(
                    file_name, k, cached_code=cached_code
                )

        k._lock_loader_system = True

        await asyncio.gather(*[_load_one(f) for f in files])

    async def _load_single_system_module(
        self, file_name: str, k, *, cached_code: str | None = None
    ) -> None:
        """Load one system module file.  Called concurrently from load_system_modules.

        If *cached_code* is provided, the file is **not** re-read from disk.
        """
        module_name = file_name[:-3]
        original_module_name = module_name
        file_path = os.path.join(k.MODULES_DIR, file_name)

        try:
            if cached_code is not None:
                code = cached_code
            else:
                with open(file_path, encoding="utf-8") as f:
                    code = f.read()

            # Resolve canonical module name from # name: header comment
            module_name, file_path = self._resolve_name_from_code(
                code, module_name, file_path, k
            )

            # Reject forbidden module names (now with resolved name)
            if hasattr(self, "_raise_forbidden_module_name"):
                try:
                    self._raise_forbidden_module_name(
                        module_name, file_path, is_system=True
                    )
                except ValueError:
                    k.error_load_modules += 1
                    k.error_load_modules_name.append(module_name)
                    return

            # Deps pre-installed in phase 1; fast no-op for already-installed packages.
            await self.pre_install_requirements(code, module_name)

            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = self._build_module(spec, file_path, module_name, is_system=True)
            sys.modules[module_name] = module

            k.set_loading_module(module_name, "system")
            module = await self.exec_with_auto_deps(
                spec, module, file_path, module_name, code
            )

            if not hasattr(module, "register"):
                cls = self._find_module_base_class(module)
                if cls is not None:
                    class_display_name = getattr(cls, "name", None)

                    if (
                        class_display_name
                        and class_display_name != "Unnamed"
                        and class_display_name != module_name
                        and class_display_name not in k.system_modules
                    ):
                        old_path = file_path
                        new_path = os.path.join(
                            k.MODULES_DIR, f"{class_display_name}.py"
                        )

                        if not os.path.exists(new_path):
                            try:
                                os.rename(old_path, new_path)
                                k.logger.info(
                                    f"Renamed system module file: {module_name} -> {class_display_name}"
                                )
                                file_path = new_path
                            except Exception as e:
                                k.logger.warning(
                                    f"Failed to rename system module file: {e}"
                                )

                        rename_sys_module = getattr(
                            self, "_rename_sys_module_entry", None
                        )
                        if callable(rename_sys_module):
                            cast(Callable[..., None], rename_sys_module)(
                                original_module_name,
                                class_display_name,
                                module,
                                file_path,
                            )
                        else:
                            sys.modules.pop(original_module_name, None)
                            sys.modules[class_display_name] = module

                        module_name = class_display_name

                    if hasattr(self, "_raise_forbidden_module_name"):
                        self._raise_forbidden_module_name(
                            module_name, file_path, is_system=True
                        )

                    k.set_loading_module(module_name, "system")

                    instance = cls(k, k.client, k.register)
                    if not hasattr(k, "_class_module_instances"):
                        k._class_module_instances = {}
                    k._class_module_instances[module_name] = instance
                    module._class_instance = instance

                    k.system_modules[module_name] = module
                    k.logger.info(f"System module loaded [class-style]: {module_name}")
                    await self.run_post_load(module, module_name, is_install=False)
                    return
                k.logger.error(f"No register() in system module: {module_name}")
                k.error_load_modules += 1
                k.error_load_modules_name.append(module_name)
                return

            # Function-style (register-based) modules must have # name: metadata
            has_name_header = self._parse_module_name_from_code(code) is not None
            if not has_name_header:
                k.logger.error(
                    f"System module {module_name} has no # name: metadata - skipping"
                )
                sys.modules.pop(module_name, None)
                k.error_load_modules += 1
                k.error_load_modules_name.append(module_name)
                return

            if inspect.iscoroutinefunction(module.register):
                await module.register(k)
            else:
                module.register(k)

            k.system_modules[module_name] = module
            k.logger.info(f"System module loaded: {module_name}")
            await self.run_post_load(module, module_name, is_install=False)

        except CommandConflictError as e:
            k.logger.error(f"Command conflict loading {module_name}: {e}")
            if hasattr(k, "_log") and k._log:
                try:
                    await asyncio.wait_for(
                        k._log.log_error_from_exc(
                            f"load_system_module_conflict:{module_name}"
                        ),
                        timeout=5.0,
                    )
                except TimeoutError:
                    k.logger.warning("log_error_from_exc timed out")
                except Exception as log_err:
                    k.logger.error(f"log_error_from_exc failed: {log_err}")
            k.error_load_modules += 1
            k.error_load_modules_name.append(file_name)
        except Exception as e:
            k.logger.error(f"Error loading system module {file_name}: {e}")
            # Clean up any commands that might have been registered
            # before the error occurred (e.g. module.register(k) succeeded
            # but loading failed later)
            if hasattr(self, "unregister_module_commands"):
                await self.unregister_module_commands(module_name)
            if hasattr(k, "_log") and k._log:
                try:
                    await asyncio.wait_for(
                        k._log.log_error_from_exc(f"load_system_module:{file_name}"),
                        timeout=5.0,
                    )
                except TimeoutError:
                    k.logger.warning("log_error_from_exc timed out")
                except Exception as log_err:
                    k.logger.error(f"log_error_from_exc failed: {log_err}")
            k.error_load_modules += 1
            k.error_load_modules_name.append(file_name)
        finally:
            k.clear_loading_module()
