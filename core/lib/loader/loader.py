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
    "os", "sys", "re", "io", "math", "time", "json", "uuid", "html",
    "http", "urllib", "email", "logging", "hashlib", "hmac", "base64",
    "struct", "socket", "ssl", "threading", "multiprocessing", "subprocess",
    "asyncio", "inspect", "traceback", "importlib", "pathlib", "shutil",
    "tempfile", "glob", "fnmatch", "collections", "itertools", "functools",
    "operator", "copy", "pprint", "textwrap", "string", "enum", "typing",
    "dataclasses", "abc", "contextlib", "warnings", "weakref", "gc",
    "random", "statistics", "decimal", "fractions", "datetime", "calendar",
    "zlib", "gzip", "bz2", "lzma", "zipfile", "tarfile", "csv", "sqlite3",
    "xml", "html", "urllib", "http", "ftplib", "imaplib", "smtplib",
    "unittest", "doctest", "pdb", "profile", "timeit", "signal",
    "platform", "sysconfig", "site", "builtins", "tokenize", "ast",
    "dis", "code", "codeop", "compileall", "py_compile",
}


class ModuleLoader:
    """Handles dynamic loading, registration, and unloading of modules."""

    def __init__(self, kernel: "Kernel") -> None:
        self.k = kernel

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
        if not hasattr(module, "register"):
            return "none"

        if hasattr(module.register, "__dict__"):
            for name, attr in module.register.__dict__.items():
                if callable(attr) and not name.startswith("__"):
                    return "method"

        if callable(module.register):
            params = list(inspect.signature(module.register).parameters.values())
            if len(params) == 1:
                return "new" if params[0].name == "kernel" else "old"

        return "none"

    async def register_module(self, module, module_type: str, module_name: str) -> bool:
        """Call the module's register function according to its type.

        Raises:
            CommandConflictError: Propagated from command registration.
        """
        k = self.k
        try:
            async def _call(fn, arg):
                if inspect.iscoroutinefunction(fn):
                    await fn(arg)
                else:
                    fn(arg)

            if module_type == "method":
                if not (hasattr(module, "register") and hasattr(module.register, "__dict__")):
                    return False
                for name, attr in module.register.__dict__.items():
                    if callable(attr) and not name.startswith("__"):
                        await _call(attr, k)

            elif module_type == "new":
                if not (hasattr(module, "register") and callable(module.register)):
                    return False
                await _call(module.register, k)

            elif module_type == "old":
                if not (hasattr(module, "register") and callable(module.register)):
                    return False
                await _call(module.register, k.client)

            else:
                if not (hasattr(module, "register") and callable(module.register)):
                    return False
                try:
                    await _call(module.register, k)
                except Exception:
                    try:
                        await _call(module.register, k.client)
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

        for loop in getattr(reg, "__loops__", []):
            loop._kernel = k
            if loop.autostart:
                try:
                    loop.start()
                    k.logger.debug(f"Autostarted loop '{loop.func.__name__}' ({module_name})")
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

            ok, msg = await k.version_manager.check_module_compatibility(code)
            if not ok:
                return False, f"Kernel version mismatch: {msg}"

            incompatible = [
                "from .. import", "import loader", "__import__('loader')",
                "from hikkalt import", "from herokult import",
            ]
            for pat in incompatible:
                if pat in code:
                    return False, "Incompatible module (Heroku/hikka style not supported)"

            sys.modules.pop(module_name, None)

            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None:
                return False, f"Cannot create module spec for {module_name}"

            module = importlib.util.module_from_spec(spec)
            module.kernel = k
            module.client = k.client
            module.custom_prefix = k.custom_prefix
            module.__file__ = file_path
            module.__name__ = module_name
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
            if not await self.register_module(module, mod_type, module_name):
                return False, "Module registration failed"

            if is_system:
                k.system_modules[module_name] = module
                k.logger.info(f"System module loaded: {module_name}")
            else:
                k.loaded_modules[module_name] = module
                k.logger.info(f"User module loaded: {module_name}")

            await self.run_post_load(module, module_name, is_install=True)

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
                module = importlib.util.module_from_spec(spec)
                module.kernel = k
                module.client = k.client
                module.custom_prefix = k.custom_prefix
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
                k.error_load_modules += 1
            except Exception as e:
                k.logger.error(f"Error loading system module {file_name}: {e}")
                k.error_load_modules += 1
            finally:
                k.clear_loading_module()

    async def load_user_modules(self) -> None:
        """Load all .py files from the user modules directory."""
        import os
        k = self.k

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
                k.error_load_modules += 1
                try:
                    await k.handle_error(e, source=f"load_module_conflict:{file_name}")
                except Exception:
                    pass
            except Exception as e:
                k.logger.error(f"Error loading module {file_name}: {e}")
                k.error_load_modules += 1
                try:
                    await k.handle_error(e, source=f"load_module:{file_name}")
                except Exception:
                    pass
            finally:
                k.clear_loading_module()

    async def install_from_url(
        self,
        url: str,
        module_name: str | None = None,
        auto_dependencies: bool = True,
    ) -> Tuple[bool, str]:
        """Download a module from *url* and load it.

        Args:
            url: Direct URL to the .py file.
            module_name: Override the module name (default: derived from URL).
            auto_dependencies: Parse and install ``# requires:`` packages.

        Returns:
            (success, message)
        """
        import os
        import tempfile
        import aiohttp
        k = self.k

        try:
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

            ok, msg = await k.version_manager.check_module_compatibility(code)
            if not ok:
                return False, f"Kernel version mismatch: {msg}"

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                tmp = f.name

            try:
                if auto_dependencies:
                    await self.pre_install_requirements(code, module_name)

                success, message = await self.load_module_from_file(tmp, module_name, False)
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

    def unregister_module_commands(self, module_name: str) -> None:
        """Stop loops, remove event handlers, and unregister all commands for a module.

        Args:
            module_name: Name of the module to unregister.
        """
        k = self.k
        module = k.loaded_modules.get(module_name) or k.system_modules.get(module_name)

        if module is not None:
            reg = getattr(module, "register", None)

            for loop in getattr(reg, "__loops__", []):
                try:
                    loop.stop()
                except Exception as e:
                    k.logger.error(f"Error stopping loop in {module_name}: {e}")

            for entry in getattr(reg, "__watchers__", []):
                wrapper, event_obj = entry[0], entry[1]
                client = entry[2] if len(entry) > 2 else k.client
                try:
                    client.remove_event_handler(wrapper, event_obj)
                except Exception as e:
                    k.logger.error(f"Error removing watcher in {module_name}: {e}")

            for entry in getattr(reg, "__event_handlers__", []):
                handler, event_obj = entry[0], entry[1]
                client = entry[2] if len(entry) > 2 else k.client
                try:
                    client.remove_event_handler(handler, event_obj)
                except Exception as e:
                    k.logger.error(f"Error removing event handler in {module_name}: {e}")

        uninstall = getattr(reg, "__uninstall__", None)
        if uninstall is not None:
            try:
                result = uninstall(k)
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        asyncio.ensure_future(result)
                    except RuntimeError:
                        asyncio.run(result)
            except Exception as e:
                k.logger.error(f"Error in uninstall callback of {module_name}: {e}")

        to_remove = [cmd for cmd, owner in k.command_owners.items() if owner == module_name]
        for cmd in to_remove:
            del k.command_handlers[cmd]
            del k.command_owners[cmd]
            k.logger.debug(f"Unregistered command: {cmd}")

        k.unregister_module_inline_handlers(module_name)

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
        }

        for key, pat in {
            "author": r"#\s*author\s*:\s*(.+)",
            "version": r"#\s*version\s*:\s*(.+)",
            "description": r"#\s*description\s*:\s*(.+)",
        }.items():
            m = re.search(pat, code, re.IGNORECASE)
            if m:
                metadata[key] = m.group(1).strip()

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
            description = _comment_before(pos) or _comment_after(pos) or "No description"
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
                    cmd = (match[0] if isinstance(match, tuple) else match).lstrip("\\.")
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
