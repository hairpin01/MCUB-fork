# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01
# author: @Hairpin00, @rich_beluga
# version: 1.5.0
# description: bootloader
from __future__ import annotations

import asyncio
import json
import os
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

sys.path.insert(0, str(Path(__file__).parent.parent))


def _log(message, boot=False, flush=False):
    if boot:
        print(f" [booting]: {message}", flush=flush)
        return None
    print(f" [root]: {message}", flush=flush)


try:
    from core.lib.utils.colors import Colors as _C
except ImportError:

    class _C:  # bare fallback if colors not available yet
        RESET = BOLD = BRIGHT_GREEN = BRIGHT_RED = YELLOW = CYAN = MUTED = (
            BRIGHT_WHITE
        ) = ""

        @staticmethod
        def paint(t, *_):
            return t


def _verify_trust_key() -> None:
    """Refuse to start when the pinned key ``mcub.pub`` is damaged or replaced.

    Runs before the rest of the project is imported. If the guard itself cannot
    be loaded that is also a refusal - otherwise deleting it would disable it.
    """
    try:
        from core.lib.utils.key_guard import enforce_or_exit
    except Exception as exc:
        for text in (
            f"ERROR: the key integrity guard cannot be loaded ({exc!r}).",
            "A key mismatch may be unsafe for the host. Startup aborted.",
        ):
            print(f" [security]: {text}", file=sys.stderr, flush=True)
        sys.exit(1)
    enforce_or_exit()


@dataclass
class KernelMeta:
    """
    Protocol declaration for kernel modules.

    Each kernel declares ``__kernel_meta__`` at module level so the
    bootloader knows how to load it without hardcoding class/method names:

    .. code-block:: python

        # core/kernel/my_kernel.py
        __kernel_meta__ = {
            "class_name": "MyKernel",   # class to instantiate
            "entry": "run",         # async entry-point method
            "name":  "My Kernel",   # display label
            "version": "1.0.0",
            "description": "Does great things",
        }
        # Or: __kernel_meta__ = KernelMeta(class_name="MyKernel", ...)

    KernelZip: put the same fields in ``__meta__.json`` at the zip root
    (for fast discovery without importing) and/or in ``__kernel_meta__``
    inside ``kernel.py`` (authoritative at boot time).

    All fields are **optional** — missing ones fall back to the defaults
    below, so legacy kernels without ``__kernel_meta__`` keep working.
    """

    class_name: str = "Kernel"  # class to instantiate
    entry: str = "run"  # async method called as entry point
    name: str = ""  # human-readable display label
    version: str = "0.0.0"
    description: str = ""

    @classmethod
    def from_module(cls, mod: ModuleType) -> "KernelMeta":
        """Read ``__kernel_meta__`` from an imported module."""
        raw = getattr(mod, "__kernel_meta__", None)
        if raw is None:
            return cls()
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, dict):
            return cls(
                **{k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
            )
        return cls()

    @classmethod
    def from_dict(cls, data: dict) -> "KernelMeta":
        """Build from a plain dict (e.g. parsed ``__meta__.json``)."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def display(self, fallback_name: str = "") -> str:
        """One-liner for the interactive core listing."""
        label = self.name or fallback_name
        ver = f" v{self.version}" if self.version not in ("", "0.0.0") else ""
        desc = f" — {self.description}" if self.description else ""
        return f"{label}{ver}{desc}" if (label or ver or desc) else ""


_KZIP_EXT = frozenset({".kzip", ".zip", ".kernelzip"})


@dataclass
class KernelEntry:
    """Represents a single discovered kernel (module or KernelZip)."""

    name: str
    path: Path
    is_zip: bool = False
    meta: KernelMeta = field(default_factory=KernelMeta)

    @property
    def kind(self) -> str:
        return "kzip" if self.is_zip else "module"


def _get_available_cores() -> dict[str, KernelEntry]:
    """
    Scan ``kernel/`` and return ``{name: KernelEntry}``, sorted.

    Priority when a ``.py`` and a ``.kzip`` share the same stem:
    the ``.py`` module wins (native > packaged).
    """
    core_dir = Path(__file__).parent / "kernel"
    if not core_dir.exists():
        return {}

    out: dict[str, KernelEntry] = {}

    for item in sorted(core_dir.iterdir()):
        if item.name.startswith("_") or item.suffix != ".py":
            continue
        out[item.stem] = KernelEntry(name=item.stem, path=item)

    for item in sorted(core_dir.iterdir()):
        if item.name.startswith("_") or item.suffix not in _KZIP_EXT:
            continue
        if item.stem in out:
            continue  # .py takes priority
        out[item.stem] = KernelEntry(
            name=item.stem,
            path=item,
            is_zip=True,
            meta=_read_kzip_fast_meta(item),
        )

    return out


def _read_kzip_fast_meta(zip_path: Path) -> KernelMeta:
    """
    Read ``__meta__.json`` from a KernelZip **without importing it**.

    This is the cheap fast-path used during discovery so the interactive
    core listing can show names/versions without loading any kernel code.
    The authoritative meta is ``__kernel_meta__`` inside ``kernel.py``,
    which is read after the kernel is actually selected and imported.
    """
    try:
        with zipfile.ZipFile(zip_path) as zf:
            if "__meta__.json" in zf.namelist():
                return KernelMeta.from_dict(json.loads(zf.read("__meta__.json")))
    except Exception:
        pass
    return KernelMeta()


_DEFAULT_CORE_FILE = Path(__file__).parent / ".default_core"


def _get_default_core() -> str | None:
    if _DEFAULT_CORE_FILE.exists():
        v = _DEFAULT_CORE_FILE.read_text().strip()
        return v or None
    return None


def _set_default_core(core: str) -> None:
    _DEFAULT_CORE_FILE.write_text(core)
    _log(
        f"{_C.BRIGHT_GREEN}{_C.BOLD}✓  Default core set to:{_C.RESET}"
        f" {_C.BRIGHT_WHITE}{core!r}{_C.RESET}",
        flush=True,
    )
    _log(f"{_C.MUTED}   (saved to -> {_DEFAULT_CORE_FILE}){_C.RESET}", flush=True)


def _clear_default_core() -> None:
    if _DEFAULT_CORE_FILE.exists():
        _DEFAULT_CORE_FILE.unlink()
        _log(f"{_C.BRIGHT_GREEN}{_C.BOLD}✓  Default core cleared{_C.RESET}", flush=True)
    else:
        _log(f"{_C.MUTED}  No default core was set{_C.RESET}", flush=True)


def _import_kernel_module(entry: KernelEntry) -> ModuleType:
    """Import and return the kernel module for *entry*."""
    if entry.is_zip:
        return _import_from_kzip(entry)
    from importlib import import_module

    return import_module(f"core.kernel.{entry.name}")


def _import_from_kzip(entry: KernelEntry) -> ModuleType:
    """
    Import ``kernel.py`` from a KernelZip archive.

    **KernelZip layout** (zip root)::

        {name}.kzip         <- the archive itself
         - kernel.py        <- required — main module
         - __meta__.json    <- optional — fast-discovery metadata
         - <helpers>/       <- optional — any extra modules
            - *.py

    The archive is permanently added to ``sys.path`` for the process
    lifetime so that intra-zip imports (``from helpers.util import x``)
    keep working after the kernel has started.  On failure the path entry
    is removed and an ``ImportError`` is raised.
    """
    import importlib

    zip_str = str(entry.path)
    unique_mod = f"_kzip_{entry.name}"

    if unique_mod in sys.modules:
        return sys.modules[unique_mod]

    # Keep the zip on sys.path so intra-zip helper imports work at runtime.
    if zip_str not in sys.path:
        sys.path.insert(0, zip_str)

    try:
        mod = importlib.import_module("kernel")
    except ImportError as exc:
        if zip_str in sys.path:
            sys.path.remove(zip_str)
        raise ImportError(
            f"KernelZip '{entry.path.name}': 'kernel.py' not found inside archive"
        ) from exc

    # Re-register under a collision-safe name so a second kzip can also
    # expose a 'kernel' module without shadowing this one.
    sys.modules[unique_mod] = mod
    sys.modules.pop("kernel", None)
    mod.__name__ = unique_mod
    return mod


def _parse_args():
    import argparse

    p = argparse.ArgumentParser(description="MCUB Kernel")
    p.add_argument(
        "--no-web",
        dest="no_web",
        action="store_true",
        default=os.environ.get("MCUB_NO_WEB", "0") == "1",
        help="Disable the web panel (env: MCUB_NO_WEB=1). Panel is ON by default.",
    )
    p.add_argument(
        "--proxy-web",
        dest="proxy_web",
        default=os.environ.get("MCUB_PROXY_WEB", ""),
        help="Enable web proxy at specified path (e.g., /web or /). Use env: MCUB_PROXY_WEB=/web",
    )
    p.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCUB_PORT", 8080)),
        help="Web panel port (default: 8080, env: MCUB_PORT)",
    )
    p.add_argument(
        "--host",
        default=os.environ.get("MCUB_HOST", "127.0.0.1"),
        help="Web panel host (default: 127.0.0.1, env: MCUB_HOST)",
    )
    p.add_argument(
        "--core",
        dest="core",
        default=None,
        help="Kernel core to use for this launch.",
    )
    p.add_argument(
        "--set-default-core",
        dest="set_default_core",
        metavar="CORE",
        default=None,
        help="Save CORE as the default for future launches, then exit.",
    )
    p.add_argument(
        "--clear-default-core",
        dest="clear_default_core",
        action="store_true",
        default=False,
        help="Remove the saved default core, then exit.",
    )
    return p.parse_args()


async def _main() -> None:
    args = _parse_args()
    _verify_trust_key()
    web_enabled = not args.no_web
    available = _get_available_cores()  # dict[name → KernelEntry]
    core_names = list(available.keys())

    if args.clear_default_core:
        _clear_default_core()
        sys.exit(0)

    if args.set_default_core:
        core = args.set_default_core
        if not core_names:
            _log(
                f"{_C.BRIGHT_RED}{_C.BOLD}Error:{_C.RESET}{_C.BRIGHT_RED} No kernel cores found!{_C.RESET}",
                flush=True,
                boot=True,
            )
            sys.exit(1)
        if core not in available:
            _log(
                f"{_C.BRIGHT_RED}{_C.BOLD}Error:{_C.RESET}{_C.BRIGHT_RED} Core '{core}' not found.{_C.RESET}",
                flush=True,
                boot=True,
            )
            _log(
                f"{_C.MUTED}Available: {_C.RESET}"
                + _C.paint(", ".join(core_names), _C.CYAN),
                flush=True,
                boot=True,
            )
            sys.exit(1)
        _set_default_core(core)
        sys.exit(0)

    if not core_names:
        _log("Error: No kernel cores found!", flush=True, boot=True)
        sys.exit(1)

    selected = args.core or _get_default_core()

    if selected is None:
        if "standard" in available:
            selected = "standard"
        elif len(core_names) == 1:
            selected = core_names[0]
        else:
            _log(f"{_C.MUTED}Available cores:{_C.RESET}", flush=True, boot=True)
            for n, e in available.items():
                tag = _C.paint(f"[{e.kind}]", _C.MUTED)
                info = e.meta.display(n)
                tail = f"  {_C.CYAN}{info}{_C.RESET}" if info else ""
                _log(
                    f"  {_C.BRIGHT_WHITE}{n:<18}{_C.RESET} {tag}{tail}",
                    flush=True,
                    boot=True,
                )
            _log("", flush=True, boot=True)
            _log(
                "Tip: --set-default-core <name> to skip this prompt",
                flush=True,
                boot=True,
            )
            saved = _get_default_core()
            hint = f" [{saved}]" if saved else f" [{core_names[0]}]"
            answer = input(f"          Select core{hint}: ").strip()
            selected = answer or saved or core_names[0]

    if selected not in available:
        _log(
            f"{_C.BRIGHT_RED}{_C.BOLD}Error:{_C.RESET}{_C.BRIGHT_RED}"
            f" Kernel '{selected}' not found!{_C.RESET}",
            flush=True,
            boot=True,
        )
        _log(
            f"{_C.MUTED}Available: {_C.RESET}"
            + _C.paint(", ".join(core_names), _C.CYAN),
            flush=True,
            boot=True,
        )
        sys.exit(1)

    core_entry = available[selected]

    _log(
        f"{_C.MUTED}=>{_C.RESET} Load {_C.BRIGHT_WHITE}{_C.BOLD}"
        f"{core_entry.kind}:{selected}{_C.RESET}\n",
        flush=True,
        boot=True,
    )
    try:
        mod = _import_kernel_module(core_entry)
    except ImportError as exc:
        _log(
            f"{_C.BRIGHT_RED}{_C.BOLD}Error:{_C.RESET}{_C.BRIGHT_RED} {exc}{_C.RESET}",
            flush=True,
            boot=True,
        )
        sys.exit(1)

    meta = KernelMeta.from_module(mod)

    KernelClass = getattr(mod, meta.class_name, None)
    if KernelClass is None:
        _log(
            f"{_C.BRIGHT_RED}{_C.BOLD}Error:{_C.RESET}{_C.BRIGHT_RED}"
            f" Protocol violation: class {meta.class_name!r} not found"
            f" in kernel '{selected}'{_C.RESET}",
            flush=True,
            boot=True,
        )
        sys.exit(1)

    kernel = KernelClass()
    _log(f"Kernel: {kernel}", boot=True)

    kernel.CORE_NAME = selected
    kernel.web_enabled = web_enabled
    kernel.web_host = args.host
    kernel.web_port = args.port
    kernel.proxy_web = args.proxy_web
    _log(f"Booting with args: {args}", boot=True)

    entry_fn = getattr(kernel, meta.entry, None)
    if entry_fn is None:
        _log(
            f"{_C.BRIGHT_RED}{_C.BOLD}Error:{_C.RESET}{_C.BRIGHT_RED}"
            f" Protocol violation: entry method {meta.entry!r} not found"
            f" on {meta.class_name}{_C.RESET}",
            flush=True,
            boot=True,
        )
        sys.exit(1)

    try:
        await entry_fn()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass

    _log("Bye!")


def main() -> None:
    """Entry point for console_scripts."""
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass

    _log("Bye!")
