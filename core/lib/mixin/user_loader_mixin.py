# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import os
import sys
import warnings
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from ..utils.exceptions import CommandConflictError

if TYPE_CHECKING:
    pass

# Max modules loaded concurrently. Higher = faster startup but more RAM pressure.
_LOAD_CONCURRENCY = 16

# Memory guard thresholds (Linux /proc/self/statm)
_MEM_SPIKE_MB = 300  # skip module if RSS jumps more than this
_MEM_TOTAL_MAX_MB = 1500  # stop loading if total RSS exceeds this


def _get_rss_mb() -> int | None:
    """Return current RSS in megabytes, or None on non-Linux / error."""
    try:
        with open("/proc/self/statm") as f:
            pages = int(f.read().split()[1])
            return (pages * 4096) // (1024 * 1024)
    except Exception:
        return None


class UserLoaderMixin:
    """Mixin for loading user modules."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    async def load_user_modules(self) -> None:
        """Load all .py files from the user modules directory.

        Two-phase approach for faster startup:
          1. Pre-scan every file for ``# requires:`` deps and install them all
             in parallel before any module is executed.
          2. Load modules concurrently (up to _LOAD_CONCURRENCY at a time) so
             async parts (run_post_load, etc.) can overlap.

        Phase 1 reads every file once and caches the content so that
        Phase 2 (``_load_single_user_module``) does **not** re-read it.
        """
        k = self.k

        if getattr(k, "_lock_loader_user", False):
            raise RuntimeError("The method can only be called once!") from None

        purge_stale_modules = getattr(self, "_purge_stale_loaded_module_entries", None)
        if callable(purge_stale_modules):
            cast(Callable[[], None], purge_stale_modules)()

        # Hikka-compat can be disabled via config for faster startup
        _hikka_compat = getattr(k, "config", {}).get("hikka_compat", True)
        if _hikka_compat:
            try:
                from core.lib.loader.hikka_compat import (
                    is_hikka_module,
                    load_hikka_module,
                )

                _hikka_compat = True
            except ImportError:
                _hikka_compat = False
        else:
            _hikka_compat = False

        files = os.listdir(k.MODULES_LOADED_DIR)
        if "log_bot.py" in files:
            files.remove("log_bot.py")
            files.insert(0, "log_bot.py")

        # Read every .py file once, cache code for phase 2.
        modules_code: list[tuple[str, str]] = []
        code_cache: dict[str, str] = {}  # filename -> code
        for file_name in files:
            module_path = os.path.join(k.MODULES_LOADED_DIR, file_name)
            if os.path.isdir(module_path):
                continue
            if not file_name.endswith(".py"):
                continue
            try:
                with open(module_path, encoding="utf-8") as f:
                    code = f.read()
                modules_code.append((file_name[:-3], code))
                code_cache[file_name] = code
            except OSError:
                pass

        batch_install = getattr(self, "pre_install_requirements_batch", None)
        if callable(batch_install):
            await batch_install(modules_code)

        semaphore = asyncio.Semaphore(_LOAD_CONCURRENCY)

        _memguard = getattr(k, "_memory_guard_enabled", False)

        async def _load_one(file_name: str) -> None:
            async with semaphore:
                nonlocal modules_code

                if _memguard:
                    rss_before = _get_rss_mb()

                cached_code = code_cache.get(file_name)
                await self._load_single_user_module(
                    file_name, k, _hikka_compat, cached_code=cached_code
                )

                if not _memguard:
                    return

                rss_after = _get_rss_mb()
                if rss_before is not None and rss_after is not None:
                    jump = rss_after - rss_before
                    if jump > _MEM_SPIKE_MB:
                        k.logger.error(
                            "[memguard] MODULE %s spike +%d MB "
                            "(total %d MB) - possibly leaking!",
                            file_name,
                            jump,
                            rss_after,
                        )

                if rss_after is not None and rss_after > _MEM_TOTAL_MAX_MB:
                    k.logger.error(
                        "[memguard] ABORT module loading at %s - RSS %d MB exceeds %d MB limit",
                        file_name,
                        rss_after,
                        _MEM_TOTAL_MAX_MB,
                    )
                    raise MemoryError(
                        f"RSS {rss_after} MB > {_MEM_TOTAL_MAX_MB} MB limit"
                    )

        # Package directories first (they have an __init__.py)
        pkg_tasks = []
        file_tasks = []
        for file_name in files:
            module_path = os.path.join(k.MODULES_LOADED_DIR, file_name)
            if os.path.isdir(module_path):
                init_file = os.path.join(module_path, "__init__.py")
                if os.path.exists(init_file):
                    source_info = k._module_sources.get(file_name, {})
                    if (
                        source_info.get("type") == "archive"
                        and source_info.get("pack_type") == "single"
                    ):

                        async def _load_pkg(fn=file_name, init=init_file):
                            async with semaphore:
                                try:
                                    await self._load_package_module(fn, init, k)
                                except Exception as e:
                                    k.logger.error(f"Error loading package {fn}: {e}")
                                    k.error_load_modules += 1
                                    k.error_load_modules_name.append(file_name)

                        pkg_tasks.append(_load_pkg())
                continue
            if not file_name.endswith(".py"):
                continue
            file_tasks.append(_load_one(file_name))

        # Set the lock AFTER building the task lists, not inside the loop.
        # Setting it inside the loop meant the flag was raised after the first
        # iteration, making any subsequent call to load_user_modules() (e.g.
        # a hot-reload) raise RuntimeError even though the first load had not
        # finished yet.
        k._lock_loader_user = True

        try:
            await asyncio.gather(*pkg_tasks, *file_tasks)
        except MemoryError as _mem_err:
            k.logger.error(
                "[memguard] load_user_modules stopped early: %s - "
                "%d of %d modules loaded",
                _mem_err,
                len(k.loaded_modules),
                len(modules_code),
            )

    async def _load_single_user_module(
        self,
        file_name: str,
        k: Any,
        _hikka_compat: bool,
        *,
        cached_code: str | None = None,
    ) -> None:
        """Load one user module file.  Called concurrently from load_user_modules.

        If *cached_code* is provided (from Phase 1), the file is **not** re-read.
        """
        module_name = file_name[:-3]
        file_path = os.path.join(k.MODULES_LOADED_DIR, file_name)

        # Reject forbidden module names before any registration happens
        if hasattr(self, "_raise_forbidden_module_name"):
            try:
                self._raise_forbidden_module_name(module_name, file_path)
            except ValueError:
                k.error_load_modules += 1
                k.error_load_modules_name.append(module_name)
                return

        try:
            if cached_code is not None:
                code = cached_code
            else:
                with open(file_path, encoding="utf-8") as f:
                    code = f.read()

            if _hikka_compat:
                from core.lib.loader.hikka_compat import (
                    is_hikka_module,
                    load_hikka_module,
                )

                if is_hikka_module(code):
                    k.set_loading_module(module_name, "user")
                    ok, err, _ = await load_hikka_module(
                        k, os.path.abspath(file_path), module_name
                    )
                    if not ok:
                        k.logger.error(f"Error loading module {file_name}: {err}")
                        k.error_load_modules += 1
                        k.error_load_modules_name.append(module_name)
                    return

            # Deps were pre-installed in phase 1; this is now a fast no-op for
            # most modules.  It still handles any dep that was missed (e.g. a
            # module added after the initial scan).
            await self.pre_install_requirements(code, module_name)

            inject_kernel = "def register(kernel):" in code

            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)

            from ..loader.kernel_proxy import (
                get_module_client,
                get_module_kernel,
                get_module_register,
            )

            proxied_kernel = get_module_kernel(k, module_name, is_system=False)
            module.kernel = proxied_kernel
            module.client = get_module_client(k, module_name, is_system=False)
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
                        module.kernel = proxied_kernel
                        module.client = get_module_client(
                            k, module_name, is_system=False
                        )
                        module.custom_prefix = k.custom_prefix

                    instance = cls(
                        proxied_kernel,
                        get_module_client(k, module_name, is_system=False),
                        get_module_register(k, module_name, is_system=False),
                    )
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
                        # Sanitize: strip path separators so a module whose
                        # `name` attribute is e.g. "../config" cannot escape
                        # the modules directory and overwrite arbitrary files.
                        class_display_name = os.path.basename(class_display_name).replace(
                            "..", ""
                        ).strip()
                        if not class_display_name:
                            class_display_name = module_name
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
                                k.logger.warning(f"Failed to rename module file: {e}")

                        rename_sys_module = getattr(
                            self, "_rename_sys_module_entry", None
                        )
                        if callable(rename_sys_module):
                            cast(Callable[..., None], rename_sys_module)(
                                module_name, class_display_name, module, file_path
                            )
                        else:
                            sys.modules.pop(module_name, None)
                            sys.modules[class_display_name] = module

                        module_name = class_display_name

                    if hasattr(self, "_raise_forbidden_module_name"):
                        self._raise_forbidden_module_name(module_name, file_path)

                    k.loaded_modules[module_name] = module
                    k.logger.info(f"Module loaded [user class-style]: {module_name}")
                    await self.run_post_load(module, module_name, is_install=False)
                    return
                return

            if inspect.iscoroutinefunction(module.register):
                await module.register(proxied_kernel)
            else:
                module.register(proxied_kernel)

            k.loaded_modules[module_name] = module
            label = "user" if inject_kernel else "user (legacy style)"
            k.logger.info(f"Module loaded [{label}]: {module_name}")
            await self.run_post_load(module, module_name, is_install=False)

        except CommandConflictError as e:
            k.logger.error(f"Command conflict loading {file_name}: {e}")
            self._rollback_orphaned_commands(k, module_name)
            k.error_load_modules += 1
            k.error_load_modules_name.append(module_name)
        except Exception as e:
            k.logger.error(f"Error loading module {file_name}: {e}")
            self._rollback_orphaned_commands(k, module_name)
            k.error_load_modules += 1
            k.error_load_modules_name.append(module_name)
        finally:
            k.clear_loading_module()

    async def _load_package_module(
        self, module_name: str, init_file: str, k: Any
    ) -> None:
        """Load a module that was installed as a package (from archive with local imports)."""

        if hasattr(self, "_raise_forbidden_module_name"):
            try:
                self._raise_forbidden_module_name(module_name, init_file)
            except ValueError:
                k.error_load_modules += 1
                k.error_load_modules_name.append(module_name)
                return

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

        from ..loader.kernel_proxy import (
            get_module_client,
            get_module_kernel,
        )

        proxied_kernel = get_module_kernel(k, module_name, is_system=False)
        module.kernel = proxied_kernel
        module.client = get_module_client(k, module_name, is_system=False)
        module.custom_prefix = k.custom_prefix
        module.__file__ = init_file
        module.__name__ = module_name
        sys.modules[module_name] = module

        k.set_loading_module(module_name, "user")

        try:
            spec.loader.exec_module(module)

            if not hasattr(module, "register"):
                raise Exception(
                    f"Module {module_name} has no register function"
                ) from None

            if inspect.iscoroutinefunction(module.register):
                await module.register(proxied_kernel)
            else:
                module.register(proxied_kernel)

            k.loaded_modules[module_name] = module
            k.logger.info(f"Module loaded [user (archive package)]: {module_name}")

            await self.run_post_load(module, module_name, is_install=False)
        except Exception as e:
            self._rollback_orphaned_commands(k, module_name)
            k.handle_error(
                e,
                message=f"Failed to execute package module {module_name!r}",
            )
            raise Exception(f"Failed to execute module: {e}") from e
        finally:
            k.clear_loading_module()

    def _rollback_orphaned_commands(self, k, module_name: str) -> None:
        """Remove commands registered during a failed module load."""
        if not module_name:
            return
        try:
            for cmd in list(k.command_owners.keys()):
                if k.command_owners.get(cmd) == module_name:
                    k.command_handlers.pop(cmd, None)
                    k.command_owners.pop(cmd, None)
                    k.logger.debug(
                        "[rollback] removed orphan command %r from %r", cmd, module_name
                    )
            bot_owners = getattr(k, "bot_command_owners", None)
            bot_handlers = getattr(k, "bot_command_handlers", None)
            if bot_owners is not None and bot_handlers is not None:
                for cmd in list(bot_owners.keys()):
                    if bot_owners.get(cmd) == module_name:
                        bot_handlers.pop(cmd, None)
                        bot_owners.pop(cmd, None)
        except Exception as e:
            k.handle_error(
                e,
                message=f"Error rolling back orphaned commands for {module_name!r}",
            )
