# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import os
from typing import TYPE_CHECKING, Any
import sys

from ..utils.exceptions import CommandConflictError

if TYPE_CHECKING:
    from kernel import Kernel


class SystemLoaderMixin:
    """Mixin for loading system modules."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    async def load_system_modules(self) -> None:
        """Load all .py files from the system modules directory."""
        import os

        k = self.k

        for file_name in os.listdir(k.MODULES_DIR):
            if not file_name.endswith(".py"):
                continue
            if file_name == "__init__.py":
                # Packaging marker; not an actual system module
                continue
            module_name = file_name[:-3]
            file_path = os.path.join(k.MODULES_DIR, file_name)
            try:
                with open(file_path, encoding="utf-8") as f:
                    code = f.read()

                await self.pre_install_requirements(code, module_name)

                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = self._build_module(spec, file_path, module_name)
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
                            import os

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

                            module_name = class_display_name

                        k.set_loading_module(module_name, "system")

                        instance = cls(k, k.client, k.register)
                        if not hasattr(k, "_class_module_instances"):
                            k._class_module_instances = {}
                        k._class_module_instances[module_name] = instance
                        module._class_instance = instance

                        k.system_modules[module_name] = module
                        k.logger.info(
                            f"System module loaded [class-style]: {module_name}"
                        )
                        await self.run_post_load(module, module_name, is_install=False)
                        continue
                    k.logger.error(f"No register() in system module: {module_name}")
                    k.error_load_modules += 1
                    continue

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
            except Exception as e:
                k.logger.error(f"Error loading system module {file_name}: {e}")
                if hasattr(k, "_log") and k._log:
                    try:
                        await asyncio.wait_for(
                            k._log.log_error_from_exc(
                                f"load_system_module:{file_name}"
                            ),
                            timeout=5.0,
                        )
                    except TimeoutError:
                        k.logger.warning("log_error_from_exc timed out")
                    except Exception as log_err:
                        k.logger.error(f"log_error_from_exc failed: {log_err}")
                k.error_load_modules += 1
            except Exception as e:
                k.logger.error(f"Error loading system module {file_name}: {e}")
                if hasattr(k, "_log") and k._log:
                    await k._log.log_error_from_exc(f"load_system_module:{module_name}")
                k.error_load_modules += 1
            finally:
                k.clear_loading_module()
