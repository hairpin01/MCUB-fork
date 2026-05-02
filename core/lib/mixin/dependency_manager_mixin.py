# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import importlib.util
import os
import re
import subprocess
import sys
from typing import TYPE_CHECKING, Any

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


class DependencyManagerMixin:
    """Mixin for managing module dependencies and auto-installation."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def resolve_pip_name(self, import_name: str) -> str:
        """Convert import name to pip package name."""
        return _IMPORT_TO_PIP.get(import_name, import_name)

    @staticmethod
    def _normalize_requirement(requirement: str) -> tuple[str, str | None]:
        """Return full pip spec and best-effort import hint."""
        req = (requirement or "").strip()
        if not req:
            return "", None

        if req.startswith(("git+", "http://", "https://")):
            egg = None
            if "#egg=" in req:
                egg = req.split("#egg=", 1)[1].split("&", 1)[0].strip()
            return req, egg or None

        base = req.split(";", 1)[0].strip()
        import_hint = re.split(r"[<>=!~\[]", base)[0].strip()
        return req, import_hint or None

    def is_in_virtualenv(self) -> bool:
        """Check if running inside a virtual environment."""
        return hasattr(sys, "real_prefix") or (
            hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
        )

    @staticmethod
    def _extract_dependencies(reqs: list) -> list[str]:
        """Extract valid dependency names from requirements list."""
        deps = []
        for req in reqs:
            req = req.strip()
            if not req:
                continue
            pkg = re.split(r"[<>=!]", req)[0].strip()
            if pkg:
                deps.append(pkg)
        return deps

    @staticmethod
    def _filter_valid_deps(deps: list[str]) -> list[str]:
        """Filter out non-installable modules."""
        return [d for d in deps if d not in _NON_INSTALLABLE]

    async def pre_install_requirements(self, code: str, module_name: str) -> None:
        """Parse # requires: comments and install missing packages."""
        reqs = []
        for line in code.splitlines():
            if line.strip().startswith("#"):
                if "requires:" in line.lower():
                    reqs_line = line.split(":", 1)[1].strip()
                    reqs.extend(r.strip() for r in reqs_line.split(",") if r.strip())

        if not reqs:
            return

        deps = self._extract_dependencies(reqs)
        deps = self._filter_valid_deps(deps)

        if not deps:
            return

        k = self.k
        k.logger.info(f"[{module_name}] Dependencies found: {deps}")

        for dep in deps:
            pip_name = self.resolve_pip_name(dep)
            try:
                importlib.util.find_spec(dep)
                k.logger.debug(f"[{module_name}] {dep} already installed")
            except ImportError:
                k.logger.info(f"[{module_name}] Installing: {pip_name}")
                await self._pip_install(pip_name, module_name)

    async def install_dependencies_batch(
        self,
        requirements: list[str],
        module_name: str = "module",
        log_fn=None,
    ) -> None:
        """Install dependencies from raw requirement strings."""
        if not requirements:
            return

        k = self.k
        seen: set[str] = set()

        for raw_req in requirements:
            pip_spec, import_hint = self._normalize_requirement(raw_req)
            if not pip_spec or pip_spec in seen:
                continue
            seen.add(pip_spec)

            if import_hint and import_hint in _NON_INSTALLABLE:
                continue

            if import_hint:
                try:
                    if importlib.util.find_spec(import_hint) is not None:
                        k.logger.debug(
                            f"[{module_name}] dependency already installed: {import_hint}"
                        )
                        continue
                except Exception:
                    pass

            install_target = pip_spec
            if import_hint and not pip_spec.startswith(("git+", "http://", "https://")):
                install_target = pip_spec.replace(
                    import_hint,
                    self.resolve_pip_name(import_hint),
                    1,
                )

            if log_fn is not None:
                try:
                    log_fn(f"=> Installing dependency: {install_target}")
                except Exception:
                    pass

            await self._pip_install(install_target, module_name)

    async def _pip_install(self, pip_name: str, module_name: str) -> None:
        """Install a pip package with multiple fallback strategies."""
        k = self.k
        strategies = []

        if not self.is_in_virtualenv():
            strategies.append(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    pip_name,
                    "--break-system-packages",
                ]
            )

        strategies.extend(
            [
                [sys.executable, "-m", "pip", "install", pip_name],
                [sys.executable, "-m", "pip3", "install", pip_name],
                ["pip", "install", pip_name],
                ["pip3", "install", pip_name],
            ]
        )

        for i, cmd in enumerate(strategies):
            try:
                k.logger.debug(
                    f"[{module_name}] Trying pip strategy {i+1}: {' '.join(cmd)}"
                )
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    k.logger.info(
                        f"[{module_name}] Installed '{pip_name}' successfully"
                    )
                    return
                else:
                    msg = (
                        stderr.decode("utf-8", errors="replace")
                        if stderr
                        else "Unknown error"
                    )
                    k.logger.debug(f"[{module_name}] Strategy {i+1} failed: {msg}")
            except Exception as e:
                k.logger.debug(f"[{module_name}] Strategy {i+1} exception: {e}")

        raise ImportError(f"Failed to install '{pip_name}' for module '{module_name}'")

    async def exec_with_auto_deps(
        self,
        spec,
        module,
        file_path: str,
        module_name: str,
        code: str,
        _retry: int = 0,
        _tried: set | None = None,
    ) -> Any:
        """Execute module with automatic dependency resolution."""
        if _tried is None:
            _tried = set()

        k = self.k
        _tried.add(module_name)

        try:
            spec.loader.exec_module(module)
            return module
        except ImportError as e:
            if _retry > 3:
                raise

            missing_module = self._extract_missing_module(str(e))
            if missing_module is None or missing_module in _tried:
                raise

            pip_name = self.resolve_pip_name(missing_module)
            k.logger.info(f"[{module_name}] Auto-installing: {pip_name}")

            try:
                await self._pip_install(pip_name, module_name)
            except Exception as install_error:
                k.logger.error(
                    f"[{module_name}] Could not install '{pip_name}': {install_error}"
                )
                raise

            k.logger.info(f"[{module_name}] Installed '{pip_name}', reloading...")

            sys.modules.pop(module_name, None)
            new_spec = importlib.util.spec_from_file_location(module_name, file_path)
            if new_spec is None:
                raise ImportError(f"Cannot create spec for {module_name}")

            new_mod = importlib.util.module_from_spec(new_spec)
            new_mod.kernel = k
            new_mod.client = k.client
            new_mod.custom_prefix = k.custom_prefix
            new_mod.__file__ = file_path
            new_mod.__name__ = module_name
            sys.modules[module_name] = new_mod

            return await self.exec_with_auto_deps(
                new_spec, new_mod, file_path, module_name, code, _retry + 1, _tried
            )

    @staticmethod
    def _extract_missing_module(error_msg: str) -> str | None:
        """Extract module name from ImportError message."""
        patterns = [
            r"No module named '([^']+)'",
            r"cannot import name '([^']+)'",
        ]
        for pattern in patterns:
            match = re.search(pattern, error_msg)
            if match:
                return match.group(1).split(".")[0]
        return None

    async def _check_module_compatibility(self, code: str) -> tuple[bool, str]:
        """Check if module is compatible with current kernel version."""
        if not hasattr(self.k, "version_manager"):
            return True, "OK"
        return await self.k.version_manager.check_module_compatibility(code)
