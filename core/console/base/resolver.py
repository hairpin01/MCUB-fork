"""
Dependency resolver: installs pip packages and checks system programs.

pip packages  → installed with `pip install --break-system-packages`
system tools  → checked with `shutil.which()`; only warnings if missing

Progress is reported via a callback: progress_cb(pct: float, msg: str)
"""
from __future__ import annotations

import asyncio
import importlib
import shutil
import sys
from typing import Callable, List, Optional, Tuple

ProgressCB = Callable[[float, str], None]


class DependencyResolver:

    def __init__(self, progress_cb: Optional[ProgressCB] = None) -> None:
        self._cb = progress_cb or (lambda p, m: None)

    def _report(self, pct: float, msg: str) -> None:
        self._cb(pct, msg)


    async def resolve(
        self,
        pip_deps: List[str],
        sys_deps: List[str],
    ) -> Tuple[bool, List[str]]:
        """
        Check and install all dependencies.

        Returns:
            (all_ok: bool, errors: List[str])
        """
        errors: List[str] = []

        for i, prog in enumerate(sys_deps):
            pct = 0.05 + 0.15 * (i / max(len(sys_deps), 1))
            self._report(pct, f"Checking system program: {prog}")
            if shutil.which(prog):
                self._report(pct, f"  ✔ {prog} found")
            else:
                msg = f"  ⚠ System program '{prog}' not found in PATH"
                self._report(pct, msg)
                errors.append(msg)   # non-fatal

        pip_start = 0.22
        pip_range = 0.60

        for i, pkg in enumerate(pip_deps):
            pct_base = pip_start + pip_range * (i / max(len(pip_deps), 1))
            pct_done = pip_start + pip_range * ((i + 1) / max(len(pip_deps), 1))

            self._report(pct_base, f"Checking pip package: {pkg}")

            if self._is_installed(pkg):
                self._report(pct_done, f"  ✔ {pkg} already installed")
                continue

            self._report(pct_base + 0.01, f"  Installing {pkg}...")
            ok, err_msg = await self._pip_install(pkg)
            if ok:
                self._report(pct_done, f"  ✔ {pkg} installed")
            else:
                msg = f"  ✖ Failed to install {pkg}: {err_msg}"
                self._report(pct_done, msg)
                errors.append(msg)

        total_ok = all("Failed" not in e for e in errors)
        return total_ok, errors

    @staticmethod
    def _is_installed(pkg_name: str) -> bool:
        """Check if a pip package is importable (by module name heuristic)."""
        # Normalise: some packages use dashes, import uses underscores
        global importlib
        mod_name = pkg_name.split("[")[0].replace("-", "_").lower()
        try:
            importlib.import_module(mod_name) # <-- Line 83: Uses global importlib
            return True
        except ImportError:
            pass
        # Try importlib.util for non-importable top-level packages
        try:
            return importlib.util.find_spec(mod_name) is not None # <-- Tries to use local importlib
        except (ModuleNotFoundError, ValueError):
            return False

    @staticmethod
    async def _pip_install(pkg: str) -> Tuple[bool, str]:
        """Run `pip install <pkg> --break-system-packages` asynchronously."""
        cmd = [
            sys.executable, "-m", "pip", "install",
            pkg,
            "--break-system-packages",
            "--quiet",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode == 0:
                return True, ""
            return False, stderr.decode(errors="replace").strip()
        except asyncio.TimeoutError:
            return False, "Timed out after 120s"
        except Exception as e:
            return False, str(e)
