# Runs dependency check BEFORE any package-level imports so that
# "python3 -m core" never crashes with ModuleNotFoundError.

import sys
import os

_REQUIREMENTS = [
    ("telethon",       "telethon"),
    ("aiohttp",        "aiohttp"),
    ("aiohttp-jinja2", "aiohttp_jinja2"),
    ("jinja2",         "jinja2"),
    ("psutil",         "psutil"),
    ("aiosqlite",      "aiosqlite"),
    ("PySocks",        "socks"),
]


def _can_import(mod: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(mod) is not None


def _install_missing() -> None:
    import subprocess
    import itertools
    import threading
    import time

    missing = [(pip, mod) for pip, mod in _REQUIREMENTS if not _can_import(mod)]
    if not missing:
        return

    for _, mod in missing:
        print(f"No module named '{mod}'")

    print()

    _stop = threading.Event()

    def _spin():
        frames = ["◜", "◝", "◞", "◟"]
        label  = "Attempting dependencies installation... Just wait"
        for f in itertools.cycle(frames):
            if _stop.is_set():
                break
            sys.stdout.write(f"\r{f}  {label}  {f}")
            sys.stdout.flush()
            time.sleep(0.12)
        sys.stdout.write("\r" + " " * 70 + "\r")
        sys.stdout.flush()

    t = threading.Thread(target=_spin, daemon=True)
    t.start()

    failed = []
    for pip_name, _ in missing:
        ok = False
        last_err = ""
        # try several strategies in order
        strategies = [
            [sys.executable, "-m", "pip", "install", pip_name, "--break-system-packages"],
            [sys.executable, "-m", "pip", "install", pip_name],
            [sys.executable, "-m", "pip", "install", pip_name, "--user"],
            ["pip3", "install", pip_name, "--break-system-packages"],
            ["pip3", "install", pip_name],
            ["pip",  "install", pip_name],
        ]
        for cmd in strategies:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                ok = True
                break
            last_err = (res.stderr or res.stdout or "").strip()

        if not ok:
            _stop.set(); t.join(timeout=1)
            print(f"\n✗  pip failed for '{pip_name}':")
            if last_err:
                print("   " + last_err.replace("\n", "\n   "))
            _stop.clear()
            thread2 = threading.Thread(target=_spin, daemon=True)
            thread2.start()
            t = thread2
            failed.append(pip_name)

    _stop.set()
    t.join(timeout=1)

    if failed:
        print(f"✗  Failed to install: {', '.join(failed)}")
        print("   Run manually:  pip install " + " ".join(failed))
        sys.exit(1)

    print("✓  Dependencies installed\n")

    # Re-execute as: python3 -m <pkg> [original args]
    # sys.argv[0] is __main__.py path when using -m, not the module name
    pkg = __spec__.parent if __spec__ else "core"
    os.execv(sys.executable, [sys.executable, "-m", pkg] + sys.argv[1:])


# Run the check immediately — before any other core.* imports
_install_missing()

from .lib.loader.register import Register  # noqa: E402  (imported for re-export)
