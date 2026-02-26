# console/base/display.py
"""
Terminal output helpers for the `base` package manager.
Matches the MCUB Shell color convention (_C class).
"""

from __future__ import annotations

import shutil
import time

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
ITALIC = "\033[3m"

RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
MAGENTA= "\033[95m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"
GREY   = "\033[90m"

SYM_OK    = f"{GREEN}✔{RESET}"
SYM_ERR   = f"{RED}✖{RESET}"
SYM_WARN  = f"{YELLOW}⚠{RESET}"
SYM_INFO  = f"{CYAN}ℹ{RESET}"
SYM_ARROW = f"{CYAN}→{RESET}"
SYM_DASH  = f"{GREY}·{RESET}"
SYM_BULLET= f"{MAGENTA}•{RESET}"
SYM_DL    = f"{BLUE}↓{RESET}"
SYM_INST  = f"{GREEN}⚙{RESET}"
SYM_DEL   = f"{RED}✕{RESET}"
SYM_UPD   = f"{YELLOW}↑{RESET}"
SYM_PKG   = f"{CYAN}📦{RESET}"
SYM_LOCK  = f"{YELLOW}🔒{RESET}"


def _tw() -> int:
    return shutil.get_terminal_size((80, 24)).columns


def ok(msg: str) -> str:
    return f"  {SYM_OK}  {msg}"


def err(msg: str) -> str:
    return f"  {SYM_ERR}  {RED}{msg}{RESET}"


def warn(msg: str) -> str:
    return f"  {SYM_WARN}  {YELLOW}{msg}{RESET}"


def info(msg: str) -> str:
    return f"  {SYM_INFO}  {msg}"


def step(icon: str, msg: str) -> str:
    return f"  {icon}  {msg}"


def h1(msg: str) -> str:
    w   = _tw()
    sep = GREY + "─" * min(w - 2, 60) + RESET
    return f"\n{sep}\n  {BOLD}{CYAN}{msg}{RESET}\n{sep}"


def h2(msg: str) -> str:
    return f"\n  {BOLD}{WHITE}{msg}{RESET}"


def kv(key: str, val: str, kw: int = 14) -> str:
    return f"  {GREY}{key:<{kw}}{RESET} {val}"


def sep() -> str:
    return f"  {GREY}{'─' * min(_tw() - 4, 56)}{RESET}"


def pkg_badge(name: str, version: str = "") -> str:
    v = f"  {GREY}v{version}{RESET}" if version else ""
    return f"{CYAN}{BOLD}{name}{RESET}{v}"


def progress_bar(pct: float, w: int = 30, msg: str = "") -> str:
    """
    Return a single-line progress bar string.
      [████████░░░░░░  68%] Downloading…
    """
    pct   = max(0.0, min(1.0, pct))
    fill  = int(w * pct)
    empty = w - fill
    bar   = (f"{GREEN}" + "█" * fill +
             f"{GREY}" + "░" * empty +
             RESET)
    pct_s = f"{int(pct * 100):3d}%"
    label = f"  {GREY}{msg[:40]}{RESET}" if msg else ""
    return f"  [{bar}] {CYAN}{BOLD}{pct_s}{RESET}{label}"



_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def spinner_frame() -> str:
    return _FRAMES[int(time.time() * 8) % len(_FRAMES)]


def format_pkg_info(meta: dict) -> list[str]:
    """Return a list of lines describing a package (for search/info)."""
    lines = []
    lines.append(kv("Name:",    pkg_badge(meta.get("name", "?"), meta.get("version", ""))))
    lines.append(kv("Author:",  meta.get("author", "unknown")))
    lines.append(kv("Desc:",    meta.get("description", "")))
    pip_deps = meta.get("pip_deps", [])
    sys_deps = meta.get("sys_deps", [])
    if pip_deps:
        lines.append(kv("Pip deps:", ", ".join(pip_deps)))
    if sys_deps:
        lines.append(kv("Sys deps:", ", ".join(sys_deps)))
    return lines


def format_installed_list(packages: list[dict]) -> list[str]:
    """Return a formatted table of installed packages."""
    if not packages:
        return [info("No packages installed.")]
    w_name = max(len(p.get("name", "")) for p in packages) + 2
    lines  = [
        h2("Installed packages"),
        f"  {GREY}{'Name':<{w_name}} {'Version':<10} {'Author':<20} Installed{RESET}",
        f"  {GREY}{'─'*w_name} {'─'*10} {'─'*20} {'─'*19}{RESET}",
    ]
    for p in sorted(packages, key=lambda x: x.get("name", "")):
        n   = p.get("name", "?")
        v   = p.get("version", "?")
        a   = p.get("author", "?")
        ts  = p.get("installed_at", "")[:19]
        lines.append(
            f"  {CYAN}{n:<{w_name}}{RESET} "
            f"{YELLOW}{v:<10}{RESET} "
            f"{WHITE}{a:<20}{RESET} "
            f"{GREY}{ts}{RESET}"
        )
    return lines
