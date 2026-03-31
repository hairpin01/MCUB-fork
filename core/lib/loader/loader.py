from __future__ import annotations
import sys
import re
import asyncio
import inspect
import importlib.util
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Tuple

from ..utils.exceptions import CommandConflictError

if TYPE_CHECKING:
    from kernel import Kernel


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
    "html",
    "urllib",
    "http",
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

    def __init__(self, kernel: "Kernel") -> None:
        self.k = kernel

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

    async def _check_module_compatibility(self, code: str) -> Tuple[bool, str]:
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

    async def install_dependency(self, package_name: str) -> Tuple[bool, str]:
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
    ) -> Tuple[bool, str]:
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
        """Install packages listed in ``# requires:`` comments before loading.

        Args:
            code: Module source code.
            module_name: Used for log messages only.
        """
        reqs = re.findall(
            r"^\s*#\s*requires?:\s*(.+)$", code, re.MULTILINE | re.IGNORECASE
        )
        if not reqs:
            return

        deps = []
        for line in reqs:
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

    async def detect_module_type(self, module) -> str:
        """Detect the registration pattern used by a module.

        Returns:
            'method' | 'new' | 'old' | 'none'
        """
        self.k.logger.debug(
            f"[Loader] detect_module_type start module={getattr(module, '__name__', 'unknown')}"
        )
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
        self, module: Any, module_name: str, is_install: bool = False
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
    ) -> Tuple[bool, str]:
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
            with open(file_path, "r", encoding="utf-8") as f:
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
                        from core.lib.loader.hikka_compat import (
                            load_hikka_module,
                        )
                        import os as _os

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

            k.set_loading_module(module_name, "system" if is_system else "user")

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
            if not await self.register_module(module, mod_type, module_name):
                return False, "Module registration failed"

            if is_system:
                k.system_modules[module_name] = module
                k.logger.info(f"System module loaded: {module_name}")
            else:
                k.loaded_modules[module_name] = module
                k.logger.info(f"User module loaded: {module_name}")

            await self.run_post_load(module, module_name, is_install=True)
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

            return True, f"Module {module_name} loaded ({mod_type} type)"

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
            module_name = file_name[:-3]
            file_path = os.path.join(k.MODULES_DIR, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
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
                    await k._log.log_error_from_exc(
                        f"load_system_module_conflict:{module_name}"
                    )
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
            if not file_name.endswith(".py"):
                continue
            module_name = file_name[:-3]
            file_path = os.path.join(k.MODULES_LOADED_DIR, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
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
                    await k._log.log_error_from_exc(f"load_module_conflict:{file_name}")
                k.error_load_modules += 1
            except Exception as e:
                k.logger.error(f"Error loading module {file_name}: {e}")
                if hasattr(k, "_log") and k._log:
                    await k._log.log_error_from_exc(f"load_module:{file_name}")
                k.error_load_modules += 1
            finally:
                k.clear_loading_module()

    async def install_from_url(
        self,
        url: str,
        module_name: str | None = None,
        auto_dependencies: bool = True,
        expected_hash: str | None = None,
        verify_signature: bool = False,
    ) -> Tuple[bool, str]:
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
        import os
        import tempfile
        import aiohttp
        import hashlib
        from urllib.parse import urlparse

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

                    success, message = await self.load_module_from_file(
                        tmp, module_name, False
                    )
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

    def get_module_path(self, module_name: str) -> str:
        """Return the filesystem path for a module file.

        System modules are resolved from ``MODULES_DIR``; user modules from
        ``MODULES_LOADED_DIR``.

        Args:
            module_name: Bare module name without ``.py`` extension.

        Returns:
            Absolute-ish path string to ``<module_name>.py``.
        """
        import os

        k = self.k
        if module_name in k.system_modules:
            return os.path.join(k.MODULES_DIR, f"{module_name}.py")
        return os.path.join(k.MODULES_LOADED_DIR, f"{module_name}.py")

    def find_module_case_insensitive(
        self, name: str
    ) -> "tuple[str | None, str | None]":
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
        deps: list[str] = []
        for line in reqs:
            for part in line.split(","):
                part = part.strip()
                if not part:
                    continue
                # Accept "pkg_name some_other_pkg" (space-separated) as well
                if " " in part:
                    deps.extend(p.strip() for p in part.split() if p.strip())
                else:
                    deps.append(part)
        # Filter out tokens that don't look like valid pip package specifiers.
        # A valid specifier starts with a letter or digit and contains only
        # alphanumeric, hyphens, underscores, dots, or version operators.
        _dep_re = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?([><=!~].+)?$")
        valid = []
        for dep in deps:
            if dep and _dep_re.match(dep):
                valid.append(dep)
        return valid

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
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            m = re.search(r"#\s*version\s*:\s*(.+)", code, re.IGNORECASE)
            if m:
                return m.group(1).strip()
            m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", code)
            if m:
                return m.group(1).strip()
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
            "commands": {},
            "banner_url": None,
        }

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
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            meta = await self.get_module_metadata(code)
            return meta["commands"].get(command, "🫨 No description")
        except Exception:
            return "🫨 No description"

    def get_module_commands(self, module_name: str) -> Tuple[list, dict, dict]:
        """Get commands, aliases and descriptions for a module.

        Args:
            module_name: Name of the module.

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
            for cmd, owner in k.command_owners.items():
                if owner == module_name:
                    commands.append(cmd)

            for cmd in commands:
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
                    with open(file_path, "r", encoding="utf-8") as f:
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
