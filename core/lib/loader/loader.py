# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any
import os

from ..utils.exceptions import CommandConflictError

if TYPE_CHECKING:
    from kernel import Kernel

from .archive import ArchiveManager
from .module_base import ModuleBase

_IMPORT_TO_PIP: dict[str, str] = {
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "yaml": "PyYAML",
    "dotenv": "python-dotenv",
    "google.generativeai": "google-generativeai",
    "speech_recognition": "SpeechRecognition",
    "dateutil": "python-dateutil",
    "Crypto": "pycryptodome",
    "usb": "pyusb",
    "gi": "PyGObject",
    "wx": "wxPython",
    "Image": "Pillow",
    "pkg_resources": "setuptools",
}

_NON_INSTALLABLE: set[str] = {
    "os",
    "sys",
    "re",
    "io",
    "math",
    "time",
    "json",
    "uuid",
    "html",
    "http",
    "urllib",
    "email",
    "logging",
    "hashlib",
    "hmac",
    "base64",
    "struct",
    "socket",
    "ssl",
    "threading",
    "multiprocessing",
    "subprocess",
    "asyncio",
    "inspect",
    "traceback",
    "importlib",
    "pathlib",
    "shutil",
    "tempfile",
    "glob",
    "fnmatch",
    "collections",
    "itertools",
    "functools",
    "operator",
    "copy",
    "pprint",
    "textwrap",
    "string",
    "enum",
    "typing",
    "dataclasses",
    "abc",
    "contextlib",
    "warnings",
    "weakref",
    "gc",
    "random",
    "statistics",
    "decimal",
    "fractions",
    "datetime",
    "calendar",
    "zlib",
    "gzip",
    "bz2",
    "lzma",
    "zipfile",
    "tarfile",
    "csv",
    "sqlite3",
    "xml",
    "ftplib",
    "imaplib",
    "smtplib",
    "unittest",
    "doctest",
    "pdb",
    "profile",
    "timeit",
    "signal",
    "platform",
    "sysconfig",
    "site",
    "builtins",
    "tokenize",
    "ast",
    "dis",
    "code",
    "codeop",
    "compileall",
    "py_compile",
}


class ModuleLoader:
    """Handles dynamic loading, registration, and unloading of modules."""

    def __init__(self, kernel: Kernel) -> None:
        self.k = kernel
        self._archive_mgr = ArchiveManager(kernel)

    def _build_module(self, spec, file_path: str, module_name: str):
        """Create a module object preloaded with kernel context."""
        self.k.logger.debug(
            f"[Loader] _build_module name={module_name} path={file_path}"
        )
        module = importlib.util.module_from_spec(spec)
        module.kernel = self.k
        module.client = self.k.client
        module.custom_prefix = self.k.custom_prefix
        module.__file__ = file_path
        module.__name__ = module_name
        self.k.logger.debug(f"[Loader] _build_module done name={module_name}")
        return module

    def _iter_register_methods(self, register) -> list:
        """Return callable register decorators stored on ``register.__dict__``."""
        if not hasattr(register, "__dict__"):
            return []
        return [
            attr
            for name, attr in register.__dict__.items()
            if callable(attr) and not name.startswith("__")
        ]

    def _get_register_param_name(self, register) -> str | None:
        """Return the only register parameter name, if it is introspectable."""
        if not callable(register):
            return None
        try:
            params = list(inspect.signature(register).parameters.values())
        except (TypeError, ValueError):
            return None
        if len(params) != 1:
            return None
        return params[0].name

    async def _call_register(self, fn, arg) -> None:
        """Invoke sync or async registration callbacks uniformly."""
        if inspect.iscoroutinefunction(fn):
            await fn(arg)
        else:
            fn(arg)

    async def _check_module_compatibility(self, code: str) -> tuple[bool, str]:
        """Proxy compatibility checks through the kernel version manager."""
        return await self.k.version_manager.check_module_compatibility(code)

    def resolve_pip_name(self, import_name: str) -> str:
        """Translate an import name to its pip package name."""
        return _IMPORT_TO_PIP.get(import_name, import_name)

    def is_in_virtualenv(self) -> bool:
        """Return True if running inside a virtual environment."""
        return hasattr(sys, "real_prefix") or (
            hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
        )

    async def install_dependency(self, package_name: str) -> tuple[bool, str]:
        """Install a Python package via pip.

        Args:
            package_name: Import name of the package.

        Returns:
            (success, message)
        """
        try:
            pip_name = self.resolve_pip_name(package_name)
            self.k.logger.info(f"Installing package: {pip_name}")

            cmd = [sys.executable, "-m", "pip", "install", "--quiet", pip_name]

            if not self.is_in_virtualenv() and not (
                hasattr(sys, "geteuid") and sys.geteuid() == 0
            ):
                cmd.append("--user")

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode == 0:
                self.k.logger.info(f"Installed: {pip_name}")
                return True, f"Installed {pip_name}"

            err = stderr.decode().strip()
            self.k.logger.error(f"Failed to install {pip_name}: {err}")

            if "--user" in cmd:
                cmd.remove("--user")
                try:
                    subprocess.check_call(cmd)
                    return True, f"Installed {pip_name}"
                except subprocess.CalledProcessError as e:
                    return False, f"Installation failed: {e}"

            return False, err

        except Exception as e:
            self.k.logger.error(f"Dependency install error: {e}")
            return False, str(e)

    async def handle_missing_dependency(
        self,
        error: ImportError,
        file_path: str,
        module_name: str,
        is_system: bool,
    ) -> tuple[bool, str]:
        """Attempt auto-installation when a module import fails.

        Returns:
            (success, message)
        """
        err_msg = str(error)

        patterns = [
            r"No module named '([^']+)'",
            r"ModuleNotFoundError: No module named '([^']+)'",
            r"cannot import name '([^']+)' from",
            r"ImportError: cannot import name '([^']+)'",
        ]

        missing = None
        for pattern in patterns:
            m = re.search(pattern, err_msg)
            if m:
                missing = m.group(1)
                break

        if not missing:
            return False, f"Import error: {err_msg}"

        self.k.logger.info(f"Missing dependency: {missing}")

        if missing in sys.builtin_module_names:
            return False, f"Missing stdlib module: {missing}"

        if hasattr(self.k, "auto_install_deps") and not self.k.auto_install_deps:
            return False, f"Missing: {missing}. Install with: pip install {missing}"

        ok, msg = await self.install_dependency(missing)
        if ok:
            self.k.logger.info(f"Retrying load after installing {missing}")
            return await self.load_module_from_file(file_path, module_name, is_system)

        return False, f"Failed to install {missing}: {msg}"

    async def pre_install_requirements(self, code: str, module_name: str) -> None:
        """Install packages listed in ``# requires:`` comments or class dependencies before loading.

        Args:
            code: Module source code.
            module_name: Used for log messages only.
        """
        reqs = re.findall(
            r"^\s*#\s*requires?:\s*(.+)$", code, re.MULTILINE | re.IGNORECASE
        )

        class_deps = []
        if re.search(r"class\s+\w+\s*\(\s*ModuleBase\s*\):", code):
            class_match = re.search(
                r"class\s+\w+\s*\(\s*ModuleBase\s*\):(.*?)(?=\n(?:class\s|\Z))",
                code,
                re.DOTALL,
            )
            if class_match:
                class_body = class_match.group(1)
                deps_m = re.search(r"dependencies\s*=\s*\[([^\]]*)\]", class_body)
                if deps_m:
                    deps_str = deps_m.group(1)
                    class_deps = [
                        d.strip().strip("'\"") for d in deps_str.split(",") if d.strip()
                    ]

        all_reqs = list(reqs)
        if class_deps:
            all_reqs.append(", ".join(class_deps))

        deps = []
        for line in all_reqs:
            for dep in line.split(","):
                dep = dep.strip()
                if not dep:
                    continue
                bare = re.split(r"[>=<!]", dep)[0].strip()
                if re.match(r"^[A-Za-z0-9_\-\.]+$", bare):
                    deps.append(dep)

        if not deps:
            return

        self.k.logger.info(f"[{module_name}] Pre-installing requirements: {deps}")
        for dep in deps:
            bare = re.split(r"[>=<!]", dep)[0].strip()
            try:
                __import__(bare.replace("-", "_"))
            except ImportError:
                self.k.logger.info(f"[{module_name}] Installing: {dep}")
                ok, msg = await self.install_dependency(bare)
                if not ok:
                    self.k.logger.warning(
                        f"[{module_name}] Could not install {dep}: {msg}"
                    )

    async def exec_with_auto_deps(
        self,
        spec,
        module,
        file_path: str,
        module_name: str,
        code: str,
        _retry: int = 0,
        _tried: set | None = None,
    ):
        """Execute a module spec, auto-installing missing dependencies on ImportError.

        Retries up to 10 times.
        """
        MAX_RETRIES = 10
        if _tried is None:
            _tried = set()

        try:
            spec.loader.exec_module(module)
            return module
        except (ImportError, ModuleNotFoundError) as e:
            if _retry >= MAX_RETRIES:
                raise

            err = str(e)
            for pat in (
                r"No module named '([^']+)'",
                r"cannot import name '[^']+' from '([^']+)'",
                r"cannot import name '([^']+)'",
            ):
                m = re.search(pat, err)
                if m:
                    missing = m.group(1).split(".")[0]
                    break
            else:
                raise

            has_mapping = missing in _IMPORT_TO_PIP
            if (
                not missing
                or missing in sys.builtin_module_names
                or (missing in _NON_INSTALLABLE and not has_mapping)
            ):
                raise

            pip_name = self.resolve_pip_name(missing)
            if pip_name in _tried:
                raise
            _tried.add(pip_name)

            self.k.logger.info(
                f"[{module_name}] Installing '{pip_name}' "
                f"(attempt {_retry + 1}/{MAX_RETRIES})"
            )
            ok, msg = await self.install_dependency(missing)
            if not ok:
                self.k.logger.error(
                    f"[{module_name}] Could not install '{pip_name}': {msg}"
                )
                raise

            self.k.logger.info(f"[{module_name}] Installed '{pip_name}', reloading...")

            sys.modules.pop(module_name, None)
            new_spec = importlib.util.spec_from_file_location(module_name, file_path)
            if new_spec is None:
                raise ImportError(f"Cannot create spec for {module_name}")

            new_mod = importlib.util.module_from_spec(new_spec)
            new_mod.kernel = self.k
            new_mod.client = self.k.client
            new_mod.custom_prefix = self.k.custom_prefix
            new_mod.__file__ = file_path
            new_mod.__name__ = module_name
            sys.modules[module_name] = new_mod

            return await self.exec_with_auto_deps(
                new_spec, new_mod, file_path, module_name, code, _retry + 1, _tried
            )

    def _find_module_base_class(self, module) -> type | None:
        """Return the first class in *module* that inherits from ModuleBase, or None."""
        for name, obj in inspect.getmembers(module, inspect.isclass):
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

    async def load_module_from_file(
        self,
        file_path: str,
        module_name: str,
        is_system: bool = False,
        is_reload: bool = False,
    ) -> tuple[bool, str]:
        """Load a Python module from *file_path* and register it with the kernel.

        Args:
            file_path: Path to the .py file.
            module_name: Name to register the module under.
            is_system: If True, stores in kernel.system_modules.

        Returns:
            (success, message)

        Raises:
            CommandConflictError: When the module registers a conflicting command.
        """
        k = self.k
        try:
            with open(file_path, encoding="utf-8") as f:
                code = f.read()
            k.logger.debug(
                "[loader.load] start module=%r path=%r system=%s size=%d",
                module_name,
                file_path,
                is_system,
                len(code),
            )

            try:
                from core.lib.loader.hikka_compat import (
                    _detect_module_type,
                    load_hikka_module,
                )

                module_type = _detect_module_type(code)
                if module_type in ("hikka", "geek"):
                    import os as _os

                    abs_path = (
                        file_path
                        if _os.path.isabs(file_path)
                        else _os.path.abspath(file_path)
                    )
                    ok, err, _ = await load_hikka_module(k, abs_path, module_name)
                    return ok, err
            except ImportError:
                pass  # hikka_compat.py not installed, fall through

            ok, msg = await self._check_module_compatibility(code)
            if not ok:
                return False, f"Kernel version mismatch: {msg}"

            incompatible = [
                "from .. import",
                "import loader",
                "__import__('loader')",
                "from hikkalt import",
                "from herokult import",
            ]
            for pat in incompatible:
                if pat in code:
                    try:
                        import os as _os

                        from core.lib.loader.hikka_compat import (
                            load_hikka_module,
                        )

                        abs_path = (
                            file_path
                            if _os.path.isabs(file_path)
                            else _os.path.abspath(file_path)
                        )
                        ok, err, _ = await load_hikka_module(k, abs_path, module_name)
                        return ok, err
                    except ImportError:
                        return (
                            False,
                            "Incompatible module (Heroku/hikka style not supported)",
                        )

            sys.modules.pop(module_name, None)

            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None:
                return False, f"Cannot create module spec for {module_name}"

            module = self._build_module(spec, file_path, module_name)
            sys.modules[module_name] = module

            try:
                module = await self.exec_with_auto_deps(
                    spec, module, file_path, module_name, code
                )
            except ImportError as e:
                return await self.handle_missing_dependency(
                    e, file_path, module_name, is_system
                )
            except SyntaxError as e:
                return False, (
                    f"Syntax error in {Path(file_path).name}: {e.msg}\n"
                    f"  Line {e.lineno}: {e.text}"
                )

            mod_type = await self.detect_module_type(module)
            k.logger.debug(
                "[loader.load] detected module=%r mod_type=%r register=%r",
                module_name,
                mod_type,
                hasattr(module, "register"),
            )

            k.set_loading_module(module_name, "system" if is_system else "user")

            if not await self.register_module(module, mod_type, module_name):
                k.clear_loading_module()
                return False, "Module registration failed"

            class_display_name = None
            if mod_type == "class":
                cls = self._find_module_base_class(module)
                class_display_name = getattr(cls, "name", None) if cls else None

                if (
                    class_display_name
                    and class_display_name != "Unnamed"
                    and class_display_name != module_name
                ):
                    import os

                    old_path = file_path
                    new_path = os.path.join(
                        os.path.dirname(file_path), f"{class_display_name}.py"
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

                    module_name = class_display_name

                k.logger.info(f"Module loaded [class-style]: {module_name}")
                if is_system:
                    k.system_modules[module_name] = module
                else:
                    k.loaded_modules[module_name] = module
            else:
                if is_system:
                    k.system_modules[module_name] = module
                    k.logger.info(f"System module loaded: {module_name}")
                else:
                    k.loaded_modules[module_name] = module
                    k.logger.info(f"User module loaded: {module_name}")

            await self.run_post_load(
                module,
                module_name,
                is_install=not is_reload,
                is_reload=is_reload,
            )
            k.logger.debug(
                "[loader.load] finished module=%r commands=%r aliases=%r",
                module_name,
                [
                    cmd
                    for cmd, owner in k.command_owners.items()
                    if owner == module_name
                ],
                {
                    alias: target
                    for alias, target in k.aliases.items()
                    if target in k.command_handlers
                    and k.command_owners.get(target) == module_name
                },
            )

            if hasattr(module, "init") and callable(module.init):
                try:
                    await module.init()
                except Exception as e:
                    k.logger.error(f"Module {module_name} init() failed: {e}")

            final_module_name = (
                class_display_name if mod_type == "class" else module_name
            )
            return (
                True,
                f"Module {final_module_name} loaded ({mod_type} type)",
                final_module_name,
            )

        except CommandConflictError:
            raise
        except Exception as e:
            k.logger.error(f"Failed to load {module_name}: {e}", exc_info=True)
            if hasattr(k, "_log") and k._log:
                await k._log.log_error_from_exc(f"load_module:{module_name}")
            return False, f"Module loading error: {e}"
        finally:
            k.clear_loading_module()

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
                    except asyncio.TimeoutError:
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
                    except asyncio.TimeoutError:
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
                    except asyncio.TimeoutError:
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
                    except asyncio.TimeoutError:
                        k.logger.warning("log_error_from_exc timed out")
                    except Exception as log_err:
                        k.logger.error(f"log_error_from_exc failed: {log_err}")
                k.error_load_modules += 1
            finally:
                k.clear_loading_module()

    async def _load_package_module(
        self, module_name: str, init_file: str, k: "Kernel"
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

    async def install_from_url(
        self,
        url: str,
        module_name: str | None = None,
        auto_dependencies: bool = True,
        expected_hash: str | None = None,
        verify_signature: bool = False,
    ) -> tuple[bool, str]:
        """Download a module from *url* and load it.

        SECURITY WARNING: Loading code from remote URLs without verification
        can lead to RCE (Remote Code Execution) attacks.

        Args:
            url: Direct URL to the .py file.
            module_name: Override the module name (default: derived from URL).
            auto_dependencies: Parse and install ``# requires:`` packages.
            expected_hash: SHA256 hash to verify module code (optional, recommended).
            verify_signature: If True, require signature verification (not implemented).

        Returns:
            (success, message)
        """
        import hashlib
        import os
        import tempfile
        from urllib.parse import urlparse

        import aiohttp

        k = self.k
        k.logger.debug(
            f"[Loader] install_from_url start url={url} module_name={module_name}"
        )

        TRUSTED_DOMAINS = [
            "raw.githubusercontent.com",
            "github.com",
            "raw.githubusercontentusercontent.com",
        ]

        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            domain = parsed.netloc.lower()
            is_trusted = any(
                host == trusted or host.endswith(f".{trusted}")
                for trusted in TRUSTED_DOMAINS
            )

            if not is_trusted:
                k.logger.warning(
                    f"⚠️ SECURITY: Installing from untrusted domain: {domain}\n"
                    f"   URL: {url}\n"
                    f"   Trusted domains: {', '.join(TRUSTED_DOMAINS)}"
                )

            if not module_name:
                module_name = (
                    os.path.basename(url)[:-3]
                    if url.endswith(".py")
                    else url.rstrip("/").split("/")[-1].split(".")[0]
                )

            if module_name in k.system_modules:
                return False, f"Module '{module_name}' is a system module"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return False, f"Download failed (HTTP {resp.status})"
                    code = await resp.text()

                ok, msg = await self._check_module_compatibility(code)
                if not ok:
                    return False, f"Kernel version mismatch: {msg}"

                if expected_hash:
                    actual_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
                    if actual_hash != expected_hash:
                        k.logger.error(
                            f"⚠️ SECURITY: Hash mismatch for module '{module_name}'!\n"
                            f"   Expected: {expected_hash}\n"
                            f"   Actual:   {actual_hash}"
                        )
                        return False, "Security error: code hash verification failed"

                if verify_signature:
                    k.logger.warning(
                        "⚠️ SECURITY: Signature verification not implemented. "
                        "Module will be loaded without signature check."
                    )

                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".py", delete=False, encoding="utf-8"
                ) as f:
                    f.write(code)
                    tmp = f.name

                try:
                    if auto_dependencies:
                        await self.pre_install_requirements(code, module_name)

                    result = await self.load_module_from_file(tmp, module_name, False)
                    success = result[0]
                    message = result[1] if len(result) >= 2 else ""
                    if success:
                        target = os.path.join(k.MODULES_LOADED_DIR, f"{module_name}.py")
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        with open(target, "w", encoding="utf-8") as f:
                            f.write(code)
                        return True, f"Module '{module_name}' installed from URL"

                    return False, f"Load error: {message}"
                finally:
                    if os.path.exists(tmp):
                        os.remove(tmp)

        except Exception as e:
            return False, f"Install from URL failed: {e}"

    async def install_from_archive(
        self,
        url: str,
        module_name: str | None = None,
        auto_dependencies: bool = True,
    ) -> tuple[bool, str]:
        """Download and install a module from an archive (zip/tar.gz).

        Args:
            url: Direct URL to the archive file.
            module_name: Override the module name (default: derived from URL or pyproject).
            auto_dependencies: Parse and install dependencies from pyproject/requirements.

        Returns:
            (success, message)
        """
        import os
        import shutil

        k = self.k
        k.logger.debug(
            f"[Loader] install_from_archive start url={url} module_name={module_name}"
        )

        archive_bytes = await self._archive_mgr.download(url)
        if not archive_bytes:
            return False, "Failed to download archive"

        if not self._archive_mgr.validate(archive_bytes):
            return False, "Invalid archive: no Python modules found"

        if not module_name:
            temp_dir = os.path.join(k.MODULES_LOADED_DIR, "_temp_archive_extract")
        else:
            temp_dir = os.path.join(k.MODULES_LOADED_DIR, "_temp_archive_extract")

        try:
            result = await self._archive_mgr.extract(archive_bytes, temp_dir)
            if not result.success:
                return False, result.error

            metadata = result.metadata
            pack_type = result.pack_type
            modules = result.modules

            if not module_name:
                module_name = (
                    metadata.name
                    if metadata and metadata.name
                    else url.rstrip("/").split("/")[-1].split(".")[0]
                )

            if module_name in k.system_modules:
                return False, f"Module '{module_name}' is a system module"

            k.logger.debug(
                f"[Loader] archive type={pack_type} modules={[m.name for m in modules]}"
            )

            if auto_dependencies:
                deps = []
                if metadata and metadata.dependencies:
                    deps.extend(metadata.dependencies)
                if not deps:
                    for mod in modules:
                        full_path = os.path.join(temp_dir, mod.file_path)
                        if os.path.exists(full_path):
                            try:
                                with open(full_path, encoding="utf-8") as f:
                                    code = f.read()
                                reqs = re.findall(
                                    r"^\s*#\s*requires?:\s*(.+)$",
                                    code,
                                    re.MULTILINE | re.IGNORECASE,
                                )
                                for line in reqs:
                                    for dep in line.split(","):
                                        dep = dep.strip()
                                        if dep:
                                            bare = re.split(r"[>=<!]", dep)[0].strip()
                                            if re.match(r"^[A-Za-z0-9_\-\.]+$", bare):
                                                deps.append(dep)
                            except Exception:
                                pass

                if deps:
                    k.logger.info(f"[Loader] Installing archive dependencies: {deps}")
                    for dep in deps:
                        bare = re.split(r"[>=<!]", dep)[0].strip()
                        try:
                            __import__(bare.replace("-", "_"))
                        except ImportError:
                            ok, msg = await self.install_dependency(bare)
                            if not ok:
                                k.logger.warning(
                                    f"[Loader] Could not install {dep}: {msg}"
                                )

            target_dir = k.MODULES_LOADED_DIR

            if pack_type == "single":
                main_module = next((m for m in modules if m.is_main), modules[0])
                target_file = os.path.join(target_dir, f"{module_name}.py")
                source_file = os.path.join(temp_dir, main_module.file_path)

                if os.path.exists(target_file):
                    os.remove(target_file)

                # Check if main.py imports from local lib/ directory
                with open(source_file, encoding="utf-8") as f:
                    main_code = f.read()

                has_local_import = (
                    "from . import" in main_code or "from .lib import" in main_code
                )

                if has_local_import:
                    # Copy entire directory structure for single modules with local imports
                    for root, dirs, files in os.walk(temp_dir):
                        rel_dir = os.path.relpath(root, temp_dir)
                        if rel_dir == ".":
                            continue

                        target_subdir = os.path.join(target_dir, module_name, rel_dir)
                        os.makedirs(target_subdir, exist_ok=True)

                        for f in files:
                            if f.endswith(".py"):
                                src = os.path.join(root, f)
                                dst = os.path.join(target_subdir, f)
                                if os.path.exists(dst):
                                    os.remove(dst)
                                shutil.copy2(src, dst)

                    # Create __init__.py in module directory
                    init_file = os.path.join(target_dir, module_name, "__init__.py")
                    if not os.path.exists(init_file):
                        with open(init_file, "w") as f:
                            f.write("")

                    # Update main.py to convert relative imports to absolute
                    main_in_package = os.path.join(
                        target_dir, module_name, "__init__.py"
                    )
                    main_src = os.path.join(temp_dir, main_module.file_path)
                    if os.path.exists(main_src):
                        with open(main_src, encoding="utf-8") as f:
                            content = f.read()
                        content = re.sub(
                            r"from \.([^\s]+) import",
                            f"from {module_name}.\\1 import",
                            content,
                        )
                        content = re.sub(
                            r"from \. import", f"from {module_name} import", content
                        )
                        with open(main_in_package, "w") as f:
                            f.write(content)

                    # Add parent directory to sys.path for proper package import
                    parent_dir = os.path.dirname(target_dir.rstrip("/"))
                    for p in [target_dir, parent_dir]:
                        if p and p not in sys.path:
                            sys.path.insert(0, p)

                    # Ensure package is importable
                    if module_name in sys.modules:
                        del sys.modules[module_name]

                    result = await self.load_module_from_file(
                        main_in_package, module_name, False
                    )
                    success = result[0]
                    msg = result[1] if len(result) >= 2 else ""
                else:
                    shutil.copy2(source_file, target_file)
                    result = await self.load_module_from_file(
                        target_file, module_name, False
                    )
                    success = result[0]
                    msg = result[1] if len(result) >= 2 else ""

                if success:
                    k._module_sources[module_name] = {
                        "url": url,
                        "type": "archive",
                        "pack_type": "single",
                    }
                    await k.save_module_sources()
                    return (
                        True,
                        f"Module '{module_name}' installed from archive",
                        {"loaded": [module_name], "failed": []},
                    )

                return False, f"Load error: {msg}", {"loaded": [], "failed": [msg]}

            else:
                loaded_modules = []
                failed_modules = []

                for mod in modules:
                    target_file = os.path.join(target_dir, f"{mod.name}.py")
                    source_file = os.path.join(temp_dir, mod.file_path)

                    if not os.path.exists(source_file):
                        continue

                    if os.path.exists(target_file):
                        os.remove(target_file)
                    shutil.copy2(source_file, target_file)

                    result = await self.load_module_from_file(
                        target_file, mod.name, False
                    )
                    success = result[0]
                    msg = result[1] if len(result) >= 2 else ""

                    if success:
                        loaded_modules.append(mod.name)
                        k._module_sources[mod.name] = {
                            "url": url,
                            "type": "archive",
                            "pack_type": "pack",
                            "parent_name": module_name,
                        }
                    else:
                        failed_modules.append(f"{mod.name}: {msg}")

                await k.save_module_sources()

                if loaded_modules:
                    msg = f"Installed {len(loaded_modules)} module(s) from pack"
                    if failed_modules:
                        msg += f", failed: {len(failed_modules)}"
                    return (
                        True,
                        msg,
                        {"loaded": loaded_modules, "failed": failed_modules},
                    )

                return False, f"Failed to load any module: {failed_modules}"

        except Exception as e:
            k.logger.error(f"[Loader] install_from_archive error: {e}")
            return False, f"Install from archive failed: {e}"
        finally:
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass

    def is_archive_url(self, url: str) -> bool:
        """Check if URL points to an archive file."""
        url_lower = url.lower()
        return any(
            url_lower.endswith(ext) for ext in [".zip", ".tar.gz", ".tgz", ".tar"]
        )

    async def unregister_module_commands(self, module_name: str) -> None:
        """Stop loops, remove event handlers, and unregister all commands for a module.

        Args:
            module_name: Name of the module to unregister.
        """
        k = self.k

        module = k.loaded_modules.get(module_name) or k.system_modules.get(module_name)

        k.logger.debug(
            "[loader.unregister] start module=%r loaded=%s system=%s commands=%r aliases=%r",
            module_name,
            module_name in k.loaded_modules,
            module_name in k.system_modules,
            [cmd for cmd, owner in k.command_owners.items() if owner == module_name],
            {
                alias: target
                for alias, target in k.aliases.items()
                if k.command_owners.get(target) == module_name
            },
        )

        reg = getattr(module, "register", None) if module is not None else None

        instance = getattr(module, "_class_instance", None)
        if instance is not None:
            if instance._loaded:
                instance._loaded = False
                try:
                    if inspect.iscoroutinefunction(instance.on_unload):
                        await instance.on_unload()
                    else:
                        result = instance.on_unload()
                        if asyncio.iscoroutine(result):
                            await result
                    k.logger.debug(f"on_unload called for class module: {module_name}")
                except Exception as e:
                    k.logger.error(f"on_unload error in {module_name}: {e}")

                cleanup_callback_tokens = getattr(
                    instance, "_cleanup_callback_tokens", None
                )
                if callable(cleanup_callback_tokens):
                    try:
                        cleanup_callback_tokens()
                    except Exception as e:
                        k.logger.error(f"callback cleanup error in {module_name}: {e}")

            if hasattr(k, "_class_module_instances"):
                k._class_module_instances.pop(module_name, None)

            k.logger.debug(
                "[loader.unregister] class module instance removed module=%r",
                module_name,
            )

        if module is not None:
            if reg is None:
                k.logger.debug(
                    "[loader.unregister] no-register module=%r type=%r",
                    module_name,
                    type(module).__name__,
                )

            for loop in getattr(reg, "__loops__", []):
                try:
                    k.logger.debug(
                        "[loader.unregister] stopping loop module=%r loop=%r",
                        module_name,
                        getattr(getattr(loop, "func", None), "__name__", repr(loop)),
                    )
                    loop.stop()
                except Exception as e:
                    k.logger.error(f"Error stopping loop in {module_name}: {e}")

            for entry in getattr(reg, "__watchers__", []):
                wrapper, event_obj = entry[0], entry[1]
                client = entry[2] if len(entry) > 2 else k.client
                try:
                    k.logger.debug(
                        "[loader.unregister] removing watcher module=%r wrapper=%r event=%r client=%r",
                        module_name,
                        getattr(wrapper, "__name__", repr(wrapper)),
                        type(event_obj).__name__,
                        type(client).__name__,
                    )
                    client.remove_event_handler(wrapper, event_obj)
                except Exception as e:
                    k.logger.error(f"Error removing watcher in {module_name}: {e}")

            await asyncio.sleep(0)

            for entry in getattr(reg, "__event_handlers__", []):
                handler, event_obj = entry[0], entry[1]
                client = entry[2] if len(entry) > 2 else k.client
                try:
                    k.logger.debug(
                        "[loader.unregister] removing event module=%r handler=%r event=%r client=%r",
                        module_name,
                        getattr(handler, "__name__", repr(handler)),
                        type(event_obj).__name__,
                        type(client).__name__,
                    )
                    client.remove_event_handler(handler, event_obj)
                except Exception as e:
                    k.logger.error(
                        f"Error removing event handler in {module_name}: {e}"
                    )

        # Remove raw client.on() handlers (Telethon-MCUB automatic tracking)
        try:
            if hasattr(k.client, "remove_module_handlers"):
                k.client.remove_module_handlers(module_name)
            elif hasattr(k.client, "_event_builders") and k.client._event_builders:
                # Fallback for standard Telethon: remove by scanning _event_builders
                module = k.loaded_modules.get(module_name) or k.system_modules.get(
                    module_name
                )
                if module:
                    reg = getattr(module, "register", None)
                    if reg and hasattr(reg, "__event_handlers__"):
                        for entry in reg.__event_handlers__:
                            handler = entry[0]
                            event_obj = entry[1] if len(entry) > 1 else None
                            try:
                                k.client.remove_event_handler(handler, event_obj)
                            except Exception:
                                pass

            if hasattr(k, "bot_client") and k.bot_client:
                if hasattr(k.bot_client, "remove_module_handlers"):
                    k.bot_client.remove_module_handlers(module_name)
                elif (
                    hasattr(k.bot_client, "_event_builders")
                    and k.bot_client._event_builders
                ):
                    # Fallback for standard Telethon bot_client
                    module = k.loaded_modules.get(module_name) or k.system_modules.get(
                        module_name
                    )
                    if module:
                        reg = getattr(module, "register", None)
                        if reg and hasattr(reg, "__event_handlers__"):
                            for entry in reg.__event_handlers__:
                                handler = entry[0]
                                event_obj = entry[1] if len(entry) > 1 else None
                                try:
                                    k.bot_client.remove_event_handler(
                                        handler, event_obj
                                    )
                                except Exception:
                                    pass
        except Exception as e:
            k.logger.error(f"Error removing module raw handlers in {module_name}: {e}")

        uninstall = getattr(reg, "__uninstall__", None)
        if uninstall is not None:
            try:
                result = uninstall(k)
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        asyncio.ensure_future(result)
                    except RuntimeError:
                        k.logger.debug(
                            "[loader.unregister] uninstall-asyncio-run module=%r",
                            module_name,
                        )
                        asyncio.run(result)
            except Exception as e:
                k.logger.error(f"Error in uninstall callback of {module_name}: {e}")
        else:
            if module is None:
                k.logger.debug(
                    "[loader.unregister] missing-module module=%r", module_name
                )
            else:
                k.logger.debug(
                    "[loader.unregister] no-uninstall module=%r",
                    module_name,
                )

        to_remove = [
            cmd for cmd, owner in k.command_owners.items() if owner == module_name
        ]
        k.logger.debug(
            "[loader.unregister] command-removal module=%r to_remove=%r",
            module_name,
            to_remove,
        )
        for cmd in to_remove:
            if cmd in k.command_handlers:
                del k.command_handlers[cmd]
            if cmd in k.command_owners:
                del k.command_owners[cmd]
            k.logger.debug(f"Unregistered command: {cmd}")

        # Unregister bot commands
        if hasattr(k, "bot_command_handlers"):
            bot_to_remove = [
                cmd
                for cmd, owner in k.bot_command_owners.items()
                if owner == module_name
            ]
            for cmd in bot_to_remove:
                if cmd in k.bot_command_handlers:
                    del k.bot_command_handlers[cmd]
                if cmd in k.bot_command_owners:
                    del k.bot_command_owners[cmd]
                k.logger.debug(f"Unregistered bot command: {cmd}")

        # Don't remove aliases on unregister - they persist across reloads
        # aliases_to_remove = [
        #     alias
        #     for alias, target_cmd in k.aliases.items()
        #     if k.command_owners.get(target_cmd) == module_name
        #     or target_cmd in to_remove
        # ]
        # for alias in aliases_to_remove:
        #     del k.aliases[alias]
        #     k.logger.debug(f"Unregistered alias: {alias}")

        if not to_remove:
            k.logger.debug(
                "[loader.unregister] nothing-to-remove module=%r",
                module_name,
            )

        k.unregister_module_inline_handlers(module_name)
        k.logger.debug(
            "[loader.unregister] done module=%r remaining_commands=%r remaining_aliases=%r",
            module_name,
            list(k.command_handlers.keys()),
            dict(k.aliases),
        )

    def remove_module_aliases(
        self, module_name: str, commands_removed: list[str] | None = None
    ) -> None:
        """Remove all aliases pointing to commands owned by a module.

        This is called when a module is permanently uninstalled (um command),
        not when it's just reloaded.

        Args:
            module_name: Name of the module whose aliases should be removed.
            commands_removed: Optional list of commands that were already removed
                from command_owners. If provided, aliases for these commands
                will also be removed.
        """
        k = self.k
        aliases_to_remove = [
            alias
            for alias, target_cmd in k.aliases.items()
            if k.command_owners.get(target_cmd) == module_name
        ]
        if commands_removed:
            for alias, target_cmd in list(k.aliases.items()):
                if target_cmd in commands_removed:
                    aliases_to_remove.append(alias)
        for alias in aliases_to_remove:
            if alias in k.aliases:
                del k.aliases[alias]
                k.logger.debug(f"Removed alias: {alias} (module={module_name})")

    def get_module_path(self, module_name: str) -> str:
        """Return the filesystem path for a module file.

        System modules are resolved from ``MODULES_DIR``; user modules from
        ``MODULES_LOADED_DIR``. For archive packages, returns __init__.py path.

        Args:
            module_name: Module name.

        Returns:
            Absolute path string to the module file.
        """
        import os

        k = self.k
        if module_name in k.system_modules:
            return os.path.join(k.MODULES_DIR, f"{module_name}.py")

        # Check for package directory (archive modules with local imports)
        package_dir = os.path.join(k.MODULES_LOADED_DIR, module_name)
        if os.path.isdir(package_dir):
            init_file = os.path.join(package_dir, "__init__.py")
            if os.path.exists(init_file):
                return init_file

        default_path = os.path.join(k.MODULES_LOADED_DIR, f"{module_name}.py")
        if os.path.exists(default_path):
            return default_path

        # Search for class-style modules by class attribute "name = '...'"
        try:
            for fname in os.listdir(k.MODULES_LOADED_DIR):
                fpath = os.path.join(k.MODULES_LOADED_DIR, fname)
                if not (os.path.isfile(fpath) and fname.endswith(".py")):
                    continue
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        code = f.read()
                    # Look for class with name attribute matching module_name
                    import re

                    # Match: class SomeClass(ModuleBase): ... name = "ModuleName"
                    pattern = (
                        r'class\s+\w+\s*\([^)]*\):[^}]*?name\s*=\s*["\']([^"\']+)["\']'
                    )
                    for match in re.finditer(pattern, code, re.DOTALL):
                        if match.group(1) == module_name:
                            return fpath
                except:
                    pass
        except OSError:
            pass

        return default_path

    @staticmethod
    def pick_localized_text(
        values: dict[str, str] | None,
        lang: str | None,
        fallback: str = "",
    ) -> str:
        """Pick localized text by language with safe fallbacks."""
        if not isinstance(values, dict) or not values:
            return fallback

        normalized = (lang or "en").lower()
        candidates = [normalized]
        if "-" in normalized:
            candidates.append(normalized.split("-", 1)[0])
        candidates.extend(["en", "ru"])

        for key in candidates:
            value = values.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        for value in values.values():
            if isinstance(value, str) and value.strip():
                return value.strip()
        return fallback

    def find_module_case_insensitive(self, name: str) -> tuple[str | None, str | None]:
        """Look up a module by name ignoring case across loaded and system dicts.

        Args:
            name: Module name to search for (case-insensitive).

        Returns:
            ``(actual_name, location)`` where *location* is ``'loaded'`` or
            ``'system'``, or ``(None, None)`` if not found.
        """
        name_lower = name.lower()
        for key in self.k.loaded_modules:
            if key.lower() == name_lower:
                return key, "loaded"
        for key in self.k.system_modules:
            if key.lower() == name_lower:
                return key, "system"
        return None, None

    @staticmethod
    def parse_requires(code: str) -> list:
        """Parse ``# requires: pkg1, pkg2`` comments from module source.

        Unlike :meth:`pre_install_requirements`, this method only *parses*
        the list — it does **not** install anything.

        Args:
            code: Module source code string.

        Returns:
            List of package specifiers (may include version constraints like
            ``requests>=2.28``).
        """
        if "requires" not in code:
            return []
        reqs = re.findall(r"^[ \t]*#[ \t]*requires:[ \t]*(.+)$", code, re.MULTILINE)
        if not reqs:
            return []
        deps = ModuleLoader._extract_dependencies(reqs)
        return ModuleLoader._filter_valid_deps(deps)

    @staticmethod
    def _extract_dependencies(reqs: list) -> list[str]:
        """Extract dependency names from requires lines."""
        deps: list[str] = []
        for line in reqs:
            for part in line.split(","):
                part = part.strip()
                if not part:
                    continue
                if " " in part:
                    deps.extend(p.strip() for p in part.split() if p.strip())
                else:
                    deps.append(part)
        return deps

    @staticmethod
    def _filter_valid_deps(deps: list[str]) -> list[str]:
        """Filter out tokens that don't look like valid pip package specifiers."""
        _dep_re = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?([><=!~].+)?$")
        return [dep for dep in deps if dep and _dep_re.match(dep)]

    async def install_dependencies_batch(
        self,
        dependencies: list,
        log_fn=None,
    ) -> None:
        """Install multiple packages concurrently via pip.

        Uses :meth:`install_dependency` for each package and runs them all in
        parallel with :func:`asyncio.gather`.

        Args:
            dependencies: List of package specifiers to install.
            log_fn: Optional ``(message: str) -> None`` callback for progress
                messages (called from the async tasks, so it must be
                thread-safe or a plain closure).
        """
        if not dependencies:
            return

        async def _install_one(dep: str) -> None:
            if log_fn:
                log_fn(f"=- Installing dependency: {dep}")
            ok, msg = await self.install_dependency(dep)
            if ok:
                if log_fn:
                    log_fn(f"=> Dependency {dep} installed successfully")
            else:
                if log_fn:
                    log_fn(f"=X Error installing {dep}: {msg[:200]}")

        await asyncio.gather(*(_install_one(dep) for dep in dependencies))

    async def get_module_version_from_file(self, file_path: str) -> str:
        try:
            with open(file_path, encoding="utf-8") as f:
                code = f.read()
            m = re.search(r"#\s*version\s*:\s*(.+)", code, re.IGNORECASE)
            if m:
                return m.group(1).strip()
            m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", code)
            if m:
                return m.group(1).strip()
            if re.search(r"class\s+\w+\s*\(\s*ModuleBase\s*\):", code):
                class_match = re.search(
                    r"class\s+(\w+)\s*\(\s*ModuleBase\s*\):(.*?)(?=\n(?:class\s|\Z))",
                    code,
                    re.DOTALL,
                )
                if class_match:
                    class_body = class_match.group(2)
                    version_m = re.search(
                        r"^\s{0,8}version\s*=\s*['\"]([^'\"]+)['\"]",
                        class_body,
                        re.MULTILINE,
                    )
                    if version_m:
                        return version_m.group(1).strip()
            return "?.?.?"
        except Exception:
            return "?.?.?"

    async def get_module_metadata(self, code: str) -> dict:
        """Parse module source code and extract metadata and command descriptions.

        Returns:
            Dict with keys: author, version, description, commands.
        """
        metadata = {
            "author": "unknown",
            "version": "X.X.X",
            "description": "no description",
            "description_i18n": {},
            "commands": {},
            "banner_url": None,
            "is_class_style": False,
        }

        if re.search(r"class\s+\w+\s*\(\s*ModuleBase\s*\):", code):
            class_match = re.search(
                r"class\s+(\w+)\s*\(\s*ModuleBase\s*\):(.*?)(?=\n(?:class\s|\Z))",
                code,
                re.DOTALL,
            )
            if class_match:
                class_body = class_match.group(2)
                metadata["is_class_style"] = True

                name_m = re.search(r"name\s*=\s*['\"]([^'\"]+)['\"]", class_body)
                if name_m:
                    metadata["class_name"] = name_m.group(1)

                version_m = re.search(r"version\s*=\s*['\"]([^'\"]+)['\"]", class_body)
                if version_m:
                    metadata["version"] = version_m.group(1).strip()

                author_m = re.search(r"author\s*=\s*['\"]([^'\"]+)['\"]", class_body)
                if author_m:
                    metadata["author"] = author_m.group(1).strip()

                desc_map_m = re.search(
                    r"description\s*=\s*\{([^}]*)\}", class_body, re.DOTALL
                )
                if desc_map_m:
                    desc_block = desc_map_m.group(1)
                    localized = {}
                    for key, value in re.findall(
                        r"['\"]([a-zA-Z_-]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]",
                        desc_block,
                    ):
                        localized[key.lower()] = value.strip()
                    if localized:
                        metadata["description_i18n"] = localized
                        metadata["description"] = self.pick_localized_text(
                            localized,
                            getattr(getattr(self, "k", None), "config", {}).get(
                                "language", "en"
                            ),
                            metadata["description"],
                        )
                else:
                    desc_text_m = re.search(
                        r"description\s*=\s*['\"]([^'\"]+)['\"]", class_body
                    )
                    if desc_text_m:
                        metadata["description"] = desc_text_m.group(1).strip()

                banner_m = re.search(
                    r"banner_url\s*=\s*['\"]([^'\"]+)['\"]", class_body
                )
                if banner_m:
                    metadata["banner_url"] = banner_m.group(1).strip()

                deps_m = re.search(r"dependencies\s*=\s*\[([^\]]*)\]", class_body)
                if deps_m:
                    deps_str = deps_m.group(1)
                    deps = [
                        d.strip().strip("'\"") for d in deps_str.split(",") if d.strip()
                    ]
                    if deps:
                        metadata["dependencies"] = deps

        for key, pat in {
            "author": r"#\s*author\s*:\s*(.+)",
            "version": r"#\s*version\s*:\s*(.+)",
            "description": r"#\s*description\s*:\s*(.+)",
            "banner_url": r"#\s*banner_url\s*:\s*(.+)",
        }.items():
            m = re.search(pat, code, re.IGNORECASE)
            if m:
                metadata[key] = m.group(1).strip()

        if metadata["author"] == "unknown":
            m = re.search(r"__author__\s*=\s*['\"]([^'\"]+)['\"]", code)
            if m:
                metadata["author"] = m.group(1).strip()
            else:
                m = re.search(r"#\s*meta\s+developer:\s*(.+)", code, re.IGNORECASE)
                if m:
                    metadata["author"] = m.group(1).strip()

        if metadata["version"] == "X.X.X":
            m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", code)
            if m:
                metadata["version"] = m.group(1).strip()
            else:
                m = re.search(
                    r"__version__\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", code
                )
                if m:
                    metadata["version"] = f"{m.group(1)}.{m.group(2)}.{m.group(3)}"

        if metadata["description"] == "no description":
            strings_match = re.search(r"strings\s*=\s*\{([^}]+)\}", code, re.DOTALL)
            if strings_match:
                strings_block = strings_match.group(1)
                for pattern in [
                    r"['\"]desc['\"]\s*:\s*['\"]([^'\"]+)['\"]",
                    r"['\"]description['\"]\s*:\s*['\"]([^'\"]+)['\"]",
                    r"['\"]help['\"]\s*:\s*['\"]([^'\"]+)['\"]",
                ]:
                    desc_m = re.search(pattern, strings_block)
                    if desc_m:
                        metadata["description"] = desc_m.group(1).strip()
                        break

        if metadata["description"] == "no description":
            m = re.search(
                r"class\s+\w+[^:]*:\s*\n(\s*'''(.+?)'''|\s*\"\"\"(.+?)\"\"\")",
                code,
                re.DOTALL,
            )
            if m:
                doc = m.group(2) or m.group(3)
                if doc:
                    metadata["description"] = doc.strip().split("\n")[0].strip()

        if metadata["description"] == "no description":
            m = re.search(
                r"def\s+register\s*\([^)]*\)[^:]*:\s*\n(\s*'''(.+?)'''|\s*\"\"\"(.+?)\"\"\")",
                code,
                re.DOTALL,
            )
            if m:
                doc = m.group(2) or m.group(3)
                if doc:
                    metadata["description"] = doc.strip().split("\n")[0].strip()

        if metadata["banner_url"] is None:
            m = re.search(r"banner\s*=\s*['\"]([^'\"]+)['\"]", code)
            if m:
                metadata["banner_url"] = m.group(1).strip()
            else:
                m = re.search(r"#\s*meta\s+banner:\s*(.+)", code, re.IGNORECASE)
                if m:
                    metadata["banner_url"] = m.group(1).strip()
                else:
                    strings_match = re.search(
                        r"strings\s*=\s*\{([^}]+)\}", code, re.DOTALL
                    )
                    if strings_match:
                        strings_block = strings_match.group(1)
                        for pattern in [
                            r"['\"]banner['\"]\s*:\s*['\"]([^'\"]+)['\"]",
                            r"['\"]pic['\"]\s*:\s*['\"]([^'\"]+)['\"]",
                        ]:
                            banner_m = re.search(pattern, strings_block)
                            if banner_m:
                                metadata["banner_url"] = banner_m.group(1).strip()
                                break

        dec_pattern = (
            r"(@(?:kernel\.register\.command|register\.command|kernel\.register_command"
            r"|kernel\.register\.bot_command|register\.bot_command|client\.on)\s*\([^)]+\))\s*\n"
        )
        call_pattern = r"(kernel\.register_command\s*\([^)]+\))\s*\n"

        positions = []
        for m in re.finditer(dec_pattern, code, re.MULTILINE):
            positions.append((m.start(), m.group(1)))
        for m in re.finditer(call_pattern, code, re.MULTILINE):
            positions.append((m.start(), m.group(1)))
        positions.sort(key=lambda x: x[0])

        def _comment_before(pos):
            lines = code[:pos].splitlines()
            comments = []
            for line in reversed(lines):
                s = line.strip()
                if s.startswith("#"):
                    comments.insert(0, s.lstrip("#").strip())
                elif s:
                    break
            return " ".join(comments) or None

        def _comment_after(pos):
            end = pos + (code[pos:].find(")") + 1)
            remaining = code[end:].lstrip()
            same = re.match(r"#\s*(.+)", remaining.split("\n")[0])
            if same:
                return same.group(1).strip()
            lines = remaining.split("\n")
            comments = []
            for line in lines:
                s = line.strip()
                if s.startswith("#"):
                    comments.append(s.lstrip("#").strip())
                elif s:
                    break
                else:
                    break
            return " ".join(comments) or None

        for pos, decorator in positions:
            m = re.search(r"['\"]([^'\"]+)['\"]", decorator)
            if not m:
                continue
            cmd = m.group(1).lstrip("\\.")
            description = (
                _comment_before(pos) or _comment_after(pos) or "No description"
            )
            metadata["commands"][cmd] = description

        if not metadata["commands"]:
            for pat in (
                r"@kernel\.register\.command\s*\(\s*['\"]([^'\"]+)['\"]",
                r"@register\.command\s*\(\s*['\"]([^'\"]+)['\"]",
                r"@kernel\.register_command\s*\(\s*['\"]([^'\"]+)['\"]",
                r"kernel\.register_command\s*\(\s*['\"]([^'\"]+)['\"]",
                r"@kernel\.register\.bot_command\s*\(\s*['\"]([^'\"]+)['\"]",
                r"@register\.bot_command\s*\(\s*['\"]([^'\"]+)['\"]",
                # Class-style @command decorator
                r"@command\s*\(\s*['\"]([^'\"]+)['\"]",
            ):
                for match in re.findall(pat, code, re.IGNORECASE):
                    cmd = (match[0] if isinstance(match, tuple) else match).lstrip(
                        "\\."
                    )
                    if cmd not in metadata["commands"]:
                        metadata["commands"][cmd] = "No description"

        return metadata

    async def get_command_description(self, module_name: str, command: str) -> str:
        """Return the description for *command* registered by *module_name*.

        Args:
            module_name: Module that owns the command.
            command: Command name without prefix.

        Returns:
            Description string, or a default message if not found.
        """
        import os

        k = self.k

        if module_name in k.system_modules:
            file_path = os.path.join(k.MODULES_DIR, f"{module_name}.py")
        elif module_name in k.loaded_modules:
            file_path = os.path.join(k.MODULES_LOADED_DIR, f"{module_name}.py")
        else:
            return "🫨 No description"

        try:
            with open(file_path, encoding="utf-8") as f:
                code = f.read()
            meta = await self.get_module_metadata(code)
            return meta["commands"].get(command, "🫨 No description")
        except Exception:
            return "🫨 No description"

    def get_module_commands(
        self, module_name: str, lang: str = "ru"
    ) -> tuple[list, dict, dict]:
        """Get commands, aliases and descriptions for a module.

        Args:
            module_name: Name of the module.
            lang: Language for doc (default: ru).

        Returns:
            Tuple of (commands list, aliases dict {cmd: [aliases]}, descriptions dict {cmd: str})
        """
        import os
        import re

        k = self.k
        commands = []
        aliases_info = {}
        descriptions = {}

        module = None
        if module_name in k.system_modules:
            module = k.system_modules[module_name]
        elif module_name in k.loaded_modules:
            module = k.loaded_modules[module_name]

        if module:
            class_instance = getattr(module, "_class_instance", None)
            if class_instance is not None:
                class_name = getattr(type(class_instance), "name", None)
                lookup_names = {module_name}
                if class_name:
                    lookup_names.add(class_name)
            else:
                lookup_names = {module_name}

            for cmd, owner in k.command_owners.items():
                if owner in lookup_names:
                    commands.append(cmd)

            command_docs = getattr(k, "command_docs", {})
            for cmd in commands:
                docs = command_docs.get(cmd, {})
                if docs:
                    descriptions[cmd] = (
                        docs.get(lang) or docs.get("en") or docs.get("ru") or ""
                    )
                else:
                    handler = k.command_handlers.get(cmd)
                    if handler:
                        doc = getattr(handler, "__doc__", None)
                        if doc:
                            descriptions[cmd] = doc.strip()

        file_path = None
        if not commands:
            if module_name in k.system_modules:
                file_path = f"modules/{module_name}.py"
            elif module_name in k.loaded_modules:
                file_path = f"modules_loaded/{module_name}.py"

            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, encoding="utf-8") as f:
                        code = f.read()

                    patterns = [
                        r"@kernel\.register\.command\s*\(\s*['\"]([^'\"]+)['\"]",
                        r"kernel\.register\.command\s*\(\s*['\"]([^'\"]+)['\"]",
                        r"@kernel\.register_command\s*\(\s*['\"]([^'\"]+)['\"]",
                        r"kernel\.register_command\s*\(\s*['\"]([^'\"]+)['\"]",
                        r"register_command\s*\(\s*['\"]([^'\"]+)['\"]",
                        r"pattern\s*=\s*r['\"]\^?\\?\.([a-zA-Z0-9_]+)['\"]",
                        r"pattern\s*=\s*r['\"]\\\\\.([^'\"]+)['\"]",
                    ]

                    for pattern in patterns:
                        found = re.findall(pattern, code)
                        commands.extend(found)

                    def _get_doc_from_code(code: str, func_name: str) -> str | None:
                        pattern = rf"async\s+def\s+{re.escape(func_name)}\s*\([^)]*\)\s*(?:->\s*[^:]+)?\s*:\s*\n(\s*'''(.+?)'''|\s*\"\"\"(.+?)\"\"\")"
                        match = re.search(pattern, code, re.DOTALL)
                        if match:
                            return (match.group(2) or match.group(3)).strip()
                        return None

                    for cmd in commands:
                        if cmd:
                            doc = _get_doc_from_code(code, cmd)
                            if doc:
                                descriptions[cmd] = doc

                except Exception as e:
                    k.logger.error(f"Error parsing commands for {module_name}: {e}")

        seen = set()
        uniq = []
        for c in commands:
            if c and c not in seen:
                seen.add(c)
                uniq.append(c)
        commands = uniq

        for alias, target_cmd in k.aliases.items():
            if target_cmd in commands:
                if target_cmd not in aliases_info:
                    aliases_info[target_cmd] = []
                if alias not in aliases_info[target_cmd]:
                    aliases_info[target_cmd].append(alias)

        return commands, aliases_info, descriptions
