"""
PackageManager — the main engine of `base`.

Repository layout expected at BASE_REPO_URL:
  packages.ini                       ← one package name per line
  <pkg>/
    config.cfg                       ← package metadata (PackageConfig format)
    manifest.ini                     ← one src/ filename per line
    <pkg>.bin                        ← file placed into console/bin/<pkg>.py
    src/
      file1.py
      file2.py
      ...

Local layout after install:
  console/packages/
    installed.json                   ← LockFile
    <pkg>/
      config.cfg                     ← copy
      src/
        file1.py
        ...
  console/bin/<pkg>.py               ← the .bin file renamed
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import shutil
import sys
import textwrap
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Tuple
#
# base_dir = Path(__file__).resolve().parent.parent
# if str(base_dir) not in sys.path:
#     sys.path.insert(0, str(base_dir))

import aiohttp

from .config_parser import PackageConfig
from .display       import (
    GREEN, RED, YELLOW, CYAN, GREY, MAGENTA, RESET, BOLD, DIM,
    SYM_OK, SYM_ERR, SYM_WARN, SYM_INFO, SYM_DL, SYM_INST,
    SYM_DEL, SYM_UPD, SYM_PKG, SYM_ARROW,
    ok, err, warn, info, step, h1, h2, kv, sep,
    pkg_badge, progress_bar, format_pkg_info, format_installed_list,
)
from .lockfile      import LockFile
from .resolver      import DependencyResolver


BASE_REPO_URL     = (
    "https://raw.githubusercontent.com/hairpin01/"
    "repo-MCUB-fork/refs/heads/main/base"
)
_CORE             = Path('core')
_CONSOLE_DIR      = _CORE / 'console'
_BIN_DIR          = _CONSOLE_DIR / "bin"
_PACKAGES_DIR     = _CONSOLE_DIR / "packages"
_LOCK_PATH        = _PACKAGES_DIR / "installed.json"

OutputCB = Callable[[str], None]



class PackageManager:
    """
    Async package manager for the MCUB shell.

    All public methods accept an `output` callback (shell.output)
    so they can stream progress without blocking the shell.

    Usage:
        pm = PackageManager()
        await pm.install("studio", output=shell.output)
    """

    TIMEOUT = 30   # HTTP request timeout in seconds

    def __init__(self, repo_url: str = BASE_REPO_URL) -> None:
        self.repo     = repo_url.rstrip("/")
        self._lock    = LockFile(_LOCK_PATH)
        _PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
        _BIN_DIR.mkdir(parents=True, exist_ok=True)

    async def install(
        self,
        name: str,
        output: OutputCB,
        force: bool = False,
    ) -> bool:
        """Download and install a package. Returns True on success."""
        output(h1(f"Installing  {pkg_badge(name)}"))

        if self._lock.is_installed(name) and not force:
            installed = self._lock.get(name)
            output(warn(
                f"'{name}' is already installed "
                f"(v{installed.get('version', '?')}).  "
                f"Use --force to reinstall or 'base update {name}' to upgrade."
            ))
            return False

        return await self._do_install(name, output, verb="install")

    async def update(self, name: str, output: OutputCB) -> bool:
        """Re-download and reinstall a package. Returns True on success."""
        output(h1(f"Updating  {pkg_badge(name)}"))

        if not self._lock.is_installed(name):
            output(err(f"'{name}' is not installed. Run: base install {name}"))
            return False

        old = self._lock.get(name)
        output(info(f"Current version: {YELLOW}{old.get('version', '?')}{RESET}"))

        return await self._do_install(name, output, verb="update")

    async def uninstall(self, name: str, output: OutputCB) -> bool:
        """Remove a package. Returns True on success."""
        output(h1(f"Removing  {pkg_badge(name)}"))

        if not self._lock.is_installed(name):
            output(err(f"'{name}' is not installed."))
            return False

        meta = self._lock.get(name)
        try:
            if meta.get("bin_file"):
                bin_path = _BIN_DIR / f"{name}.py"
                if bin_path.exists():
                    output(step(SYM_DEL, f"Removing bin:  {bin_path}"))
                    bin_path.unlink()

            pkg_dir = _PACKAGES_DIR / name
            if pkg_dir.exists():
                output(step(SYM_DEL, f"Removing dir:  {pkg_dir}"))
                shutil.rmtree(pkg_dir)

            self._lock.remove(name)
            output(ok(f"'{name}' has been removed."))
            return True

        except Exception as e:
            output(err(f"Uninstall failed: {e}"))
            output(err(traceback.format_exc().strip()))
            return False

    async def search(self, query: str, output: OutputCB) -> None:
        """Search available packages in the repository."""
        output(h1(f"Searching:  {CYAN}{query}{RESET}"))
        output(step(SYM_DL, f"Fetching package list from repo..."))

        packages = await self._fetch_packages_ini()
        if packages is None:
            output(err("Could not reach the repository. Check your connection."))
            return

        q = query.lower()
        matches = [p for p in packages if q in p.lower()]

        if not matches:
            output(warn(f"No packages found matching '{query}'."))
            output(info(f"Run 'base list --available' to see all packages."))
            return

        output(info(f"Found {CYAN}{len(matches)}{RESET} package(s):"))
        output("")

        # Fetch config for each match to show description
        for pkg_name in matches:
            cfg = await self._fetch_config(pkg_name)
            if cfg:
                installed = self._lock.is_installed(pkg_name)
                badge     = f"{SYM_OK} " if installed else "   "
                status    = f"{GREEN}installed{RESET}" if installed else f"{GREY}available{RESET}"
                output(f"  {badge}{pkg_badge(pkg_name, cfg.version)}  {GREY}{status}{RESET}")
                if cfg.description:
                    output(f"     {DIM}{cfg.description}{RESET}")
            else:
                output(f"     {pkg_name}")

        output("")
        output(info(f"Run {CYAN}base install <name>{RESET} to install a package."))

    async def list_packages(
        self,
        output: OutputCB,
        show_available: bool = False,
    ) -> None:
        """List installed (and optionally available) packages."""
        installed = self._lock.all_packages()

        if show_available:
            output(h1("Available packages"))
            pkgs = await self._fetch_packages_ini()
            if pkgs is None:
                output(err("Cannot fetch package list from repo."))
            else:
                for p in pkgs:
                    flag = f" {SYM_OK}" if self._lock.is_installed(p) else ""
                    output(f"  {CYAN}{p}{RESET}{flag}")
            output("")

        output(h1("Installed packages"))
        lines = format_installed_list(installed)
        for l in lines:
            output(l)

    async def show(self, name: str, output: OutputCB) -> None:
        """Show detailed information about a package."""
        output(h1(f"Package info:  {pkg_badge(name)}"))

        if self._lock.is_installed(name):
            meta = self._lock.get(name)
            cfg  = PackageConfig.from_dict(meta)
            output(info("Status: " + f"{GREEN}{BOLD}installed{RESET}"))
        else:
            output(info("Status: " + f"{GREY}not installed{RESET}"))
            cfg = await self._fetch_config(name)
            if not cfg:
                output(err(f"Package '{name}' not found in repository."))
                return

        lines = format_pkg_info({
            "name":        cfg.name,
            "version":     cfg.version,
            "author":      cfg.author,
            "description": cfg.description,
            "pip_deps":    cfg.pip_deps,
            "sys_deps":    cfg.sys_deps,
        })
        for l in lines:
            output(l)

        if cfg.src_files:
            output(kv("Source files:", ""))
            for f in cfg.src_files:
                output(f"    {GREY}·{RESET} {f}")
        if cfg.bin_file:
            output(kv("Bin file:", cfg.bin_file))

    async def _do_install(
        self,
        name: str,
        output: OutputCB,
        verb: str = "install",
    ) -> bool:
        pct_log: List[str] = []
        _pct = [0.0]

        def progress(pct: float, msg: str) -> None:
            _pct[0] = pct
            pct_log.append(msg)
            bar = progress_bar(pct, w=28, msg=msg[:42])
            output(bar)

        try:
            progress(0.02, f"Fetching config for '{name}'...")
            cfg = await self._fetch_config(name)
            if not cfg:
                output(err(f"Package '{name}' not found in repository."))
                return False
            progress(0.08, f"Found: {cfg.name} v{cfg.version} by {cfg.author}")

            progress(0.12, "Fetching file manifest...")
            manifest = await self._fetch_manifest(name)
            if manifest is None:
                # Fallback: use src_files from config
                manifest = cfg.src_files
            if not manifest and not cfg.bin_file:
                output(err("Package has no files to install."))
                return False
            progress(0.16, f"Manifest: {len(manifest)} source file(s)")

            if cfg.pip_deps or cfg.sys_deps:
                progress(0.18, f"Resolving dependencies: {cfg.pip_deps + cfg.sys_deps}")
                resolver = DependencyResolver(
                    progress_cb=lambda p, m: progress(0.18 + p * 0.25, m)
                )
                deps_ok, dep_errors = await resolver.resolve(cfg.pip_deps, cfg.sys_deps)
                if dep_errors:
                    for e_msg in dep_errors:
                        output(warn(e_msg))
                progress(0.44, "Dependencies resolved")
            else:
                progress(0.44, "No dependencies")

            pkg_dir = _PACKAGES_DIR / name
            src_dir = pkg_dir / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            progress(0.46, f"Created: {pkg_dir}")

            n_files = len(manifest)
            for i, filename in enumerate(manifest):
                file_pct = 0.46 + 0.26 * ((i + 1) / max(n_files, 1))
                progress(file_pct, f"Downloading src/{filename}")
                content = await self._fetch_text(f"{self.repo}/{name}/src/{filename}")
                if content is None:
                    output(warn(f"  ⚠ Could not download '{filename}' — skipping"))
                    continue
                dest = src_dir / filename
                dest.write_text(content, encoding="utf-8")
                progress(file_pct, f"  ✔ {filename}  ({len(content)} bytes)")

            cfg_copy = pkg_dir / "config.cfg"
            cfg_text = await self._fetch_text(f"{self.repo}/{name}/config.cfg")
            if cfg_text:
                cfg_copy.write_text(cfg_text, encoding="utf-8")

            if cfg.bin_file:
                progress(0.74, f"Downloading bin: {cfg.bin_file}")
                bin_content = await self._fetch_text(
                    f"{self.repo}/{name}/{cfg.bin_file}"
                )
                if bin_content is None:
                    output(warn(f"  ⚠ Bin file '{cfg.bin_file}' not found in repo"))
                else:
                    bin_dest = _BIN_DIR / f"{name}.py"
                    bin_dest.write_text(bin_content, encoding="utf-8")
                    progress(0.78, f"  ✔ Installed bin → {bin_dest}")

            if cfg.entry_file:
                entry_path = src_dir / cfg.entry_file
                if entry_path.exists():
                    progress(0.82, f"Running entry script: {cfg.entry_file}")
                    result = await self._run_entry(entry_path)
                    if result:
                        progress(0.86, f"  ✔ Entry script completed")
                    else:
                        output(warn(f"  ⚠ Entry script returned non-zero"))
                else:
                    output(warn(f"  ⚠ Entry script '{cfg.entry_file}' not found"))

            progress(0.92, "Updating lock file...")
            self._lock.register(
                name        = cfg.name or name,
                version     = cfg.version,
                author      = cfg.author,
                description = cfg.description,
                pip_deps    = cfg.pip_deps,
                sys_deps    = cfg.sys_deps,
                bin_file    = cfg.bin_file,
                src_files   = manifest,
                repo_url    = self.repo,
                entry_file  = cfg.entry_file,
            )

            progress(1.0, f"Package '{name}' {verb}ed successfully!")
            output("")
            output(ok(
                f"{pkg_badge(cfg.name or name, cfg.version)} "
                f"{verb}ed successfully."
            ))
            if cfg.bin_file:
                output(info(f"Run: {CYAN}base shell {name}{RESET} or "
                            f"use it as a shell command"))
            return True

        except aiohttp.ClientError as e:
            output(err(f"Network error: {e}"))
            return False
        except Exception as e:
            output(err(f"Unexpected error: {e}"))
            output(err(traceback.format_exc().strip()))
            return False

    async def _fetch_text(self, url: str) -> Optional[str]:
        """Download URL and return text, or None on error."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)) as r:
                    if r.status == 200:
                        return await r.text(encoding="utf-8", errors="replace")
        except Exception:
            pass
        return None

    async def _fetch_config(self, name: str) -> Optional[PackageConfig]:
        """Fetch and parse a package's config.cfg."""
        text = await self._fetch_text(f"{self.repo}/{name}/config.cfg")
        if text is None:
            return None
        try:
            return PackageConfig.from_text(text)
        except Exception:
            return None

    async def _fetch_manifest(self, name: str) -> Optional[List[str]]:
        """Fetch manifest.ini (one filename per line). Returns None if missing."""
        text = await self._fetch_text(f"{self.repo}/{name}/manifest.ini")
        if text is None:
            return None
        return [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]

    async def _fetch_packages_ini(self) -> Optional[List[str]]:
        """Fetch the repository's root packages.ini."""
        text = await self._fetch_text(f"{self.repo}/packages.ini")
        if text is None:
            return None
        return [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]

    @staticmethod
    async def _run_entry(path: Path) -> bool:
        """
        Execute an entry script in its own process.
        Returns True if exit code is 0.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            return proc.returncode == 0
        except Exception:
            return False
